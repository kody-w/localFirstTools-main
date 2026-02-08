// dungeon-gen.js — Procedural dungeon generation for Depths of the Abyss
// Depends on: G, STATE, TILE_SIZE, FLOOR_THEMES from constants.js
// Depends on: Util from utils.js
// Depends on: ENEMY_TYPES, BOSS_DEFS, SPAWN_TABLES from data/enemies.js
// Depends on: LOOT_TABLES from data/items.js
// Depends on: TileMap and tile constants from world/tilemap.js

// BSP (Binary Space Partition) node for procedural dungeon generation
class BSPNode {
    constructor(x, y, w, h) {
        this.x = x;
        this.y = y;
        this.w = w;
        this.h = h;
        this.left = null;
        this.right = null;
        this.room = null; // {x, y, w, h}
    }

    // Recursive split for procedural generation
    split(minSize, rng) {
        if (this.left || this.right) return false;

        // Determine split direction based on aspect ratio with some randomness
        const splitH = rng() > 0.5;

        if (this.w > this.h && this.w / this.h >= 1.25) {
            // Wide room, split vertically
            return this.splitVertical(minSize, rng);
        } else if (this.h > this.w && this.h / this.w >= 1.25) {
            // Tall room, split horizontally
            return this.splitHorizontal(minSize, rng);
        } else {
            // Square-ish, random split
            return splitH ? this.splitHorizontal(minSize, rng) : this.splitVertical(minSize, rng);
        }
    }

    splitHorizontal(minSize, rng) {
        if (this.h < minSize * 2) return false;

        const split = Math.floor(minSize + rng() * (this.h - minSize * 2));
        this.left = new BSPNode(this.x, this.y, this.w, split);
        this.right = new BSPNode(this.x, this.y + split, this.w, this.h - split);
        return true;
    }

    splitVertical(minSize, rng) {
        if (this.w < minSize * 2) return false;

        const split = Math.floor(minSize + rng() * (this.w - minSize * 2));
        this.left = new BSPNode(this.x, this.y, split, this.h);
        this.right = new BSPNode(this.x + split, this.y, this.w - split, this.h);
        return true;
    }

    getLeaves() {
        if (!this.left && !this.right) return [this];

        const leaves = [];
        if (this.left) leaves.push(...this.left.getLeaves());
        if (this.right) leaves.push(...this.right.getLeaves());
        return leaves;
    }

    getRoom() {
        return this.room;
    }
}

const Dungeon = {
    root: null,
    spawnPoint: {x: 0, y: 0},
    stairsDown: {x: 0, y: 0},
    campfire: {x: 0, y: 0},
    bossGate: {x: 0, y: 0},
    bossArena: null,

    generate: function(floor, seed) {
        // Procedural dungeon generation pipeline
        // Uses seeded RNG for deterministic generation
        Util.seedRandom(seed);
        const rng = Math.random;

        // Calculate map size based on floor (scales up)
        const baseW = 80;
        const baseH = 60;
        const scale = 1 + Math.floor(floor / 10) * 0.25;
        const mapW = Math.floor(baseW * scale);
        const mapH = Math.floor(baseH * scale);

        // Initialize tilemap
        TileMap.init(mapW, mapH);

        // 1. BSP Generation
        const minLeafSize = 8;
        this.root = new BSPNode(1, 1, mapW - 2, mapH - 2);
        this.splitBSP(this.root, minLeafSize, rng);

        // 2. Carve rooms in leaves
        const leaves = this.root.getLeaves();
        const rooms = [];
        for (let i = 0; i < leaves.length; i++) {
            const leaf = leaves[i];
            const room = this.carveRoom(leaf, rng);
            leaf.room = room;
            rooms.push(room);
        }
        TileMap.rooms = rooms;

        // 3. Connect rooms with corridors
        this.connectRooms(this.root, rng);

        // 4. Place doors at corridor-room junctions
        this.placeDoors(rooms);

        // 5. Special rooms
        this.placeSpecialTiles(rooms, floor, rng);

        // 6. Decoration pass
        this.placeDecorations(rooms, floor, rng);

        return {
            spawn: this.spawnPoint,
            stairs: this.stairsDown,
            campfire: this.campfire
        };
    },

    splitBSP: function(node, minSize, rng) {
        // Recursive procedural BSP splitting
        if (node.split(minSize, rng)) {
            this.splitBSP(node.left, minSize, rng);
            this.splitBSP(node.right, minSize, rng);
        }
    },

    carveRoom: function(leaf, rng) {
        // Procedural room carving within BSP leaf
        const minW = 4;
        const minH = 4;
        const maxW = leaf.w - 1;
        const maxH = leaf.h - 1;

        const w = Math.floor(minW + rng() * (maxW - minW));
        const h = Math.floor(minH + rng() * (maxH - minH));
        const x = leaf.x + Math.floor(rng() * (leaf.w - w));
        const y = leaf.y + Math.floor(rng() * (leaf.h - h));

        // Fill room with floor, surround with walls
        for (let ry = y - 1; ry <= y + h; ry++) {
            for (let rx = x - 1; rx <= x + w; rx++) {
                if (rx === x - 1 || rx === x + w || ry === y - 1 || ry === y + h) {
                    if (TileMap.getTile(rx, ry) === TILE_VOID) {
                        TileMap.setTile(rx, ry, TILE_WALL);
                    }
                } else {
                    TileMap.setTile(rx, ry, TILE_FLOOR);
                }
            }
        }

        return {x, y, w, h};
    },

    connectRooms: function(node, rng) {
        // Recursively connect sibling rooms with L-shaped corridors (procedural)
        if (!node.left || !node.right) return;

        this.connectRooms(node.left, rng);
        this.connectRooms(node.right, rng);

        const leftRooms = node.left.getLeaves().map(l => l.room).filter(r => r);
        const rightRooms = node.right.getLeaves().map(l => l.room).filter(r => r);

        if (leftRooms.length === 0 || rightRooms.length === 0) return;

        const leftRoom = leftRooms[Math.floor(rng() * leftRooms.length)];
        const rightRoom = rightRooms[Math.floor(rng() * rightRooms.length)];

        const leftCenter = {
            x: leftRoom.x + Math.floor(leftRoom.w / 2),
            y: leftRoom.y + Math.floor(leftRoom.h / 2)
        };
        const rightCenter = {
            x: rightRoom.x + Math.floor(rightRoom.w / 2),
            y: rightRoom.y + Math.floor(rightRoom.h / 2)
        };

        // L-shaped corridor
        if (rng() > 0.5) {
            this.carveCorridor(leftCenter.x, leftCenter.y, rightCenter.x, leftCenter.y);
            this.carveCorridor(rightCenter.x, leftCenter.y, rightCenter.x, rightCenter.y);
        } else {
            this.carveCorridor(leftCenter.x, leftCenter.y, leftCenter.x, rightCenter.y);
            this.carveCorridor(leftCenter.x, rightCenter.y, rightCenter.x, rightCenter.y);
        }
    },

    carveCorridor: function(x1, y1, x2, y2) {
        // Procedural corridor carving
        const minX = Math.min(x1, x2);
        const maxX = Math.max(x1, x2);
        const minY = Math.min(y1, y2);
        const maxY = Math.max(y1, y2);

        for (let x = minX; x <= maxX; x++) {
            for (let y = minY; y <= maxY; y++) {
                if (TileMap.getTile(x, y) === TILE_VOID || TileMap.getTile(x, y) === TILE_WALL) {
                    TileMap.setTile(x, y, TILE_FLOOR);
                }
                // Add walls around corridor
                for (let dx = -1; dx <= 1; dx++) {
                    for (let dy = -1; dy <= 1; dy++) {
                        if (dx === 0 && dy === 0) continue;
                        const nx = x + dx;
                        const ny = y + dy;
                        if (TileMap.getTile(nx, ny) === TILE_VOID) {
                            TileMap.setTile(nx, ny, TILE_WALL);
                        }
                    }
                }
            }
        }
    },

    placeDoors: function(rooms) {
        // Place doors at corridor-room junctions
        for (let i = 0; i < rooms.length; i++) {
            const room = rooms[i];

            // Check perimeter for corridor connections
            for (let x = room.x; x < room.x + room.w; x++) {
                this.tryPlaceDoor(x, room.y - 1);
                this.tryPlaceDoor(x, room.y + room.h);
            }
            for (let y = room.y; y < room.y + room.h; y++) {
                this.tryPlaceDoor(room.x - 1, y);
                this.tryPlaceDoor(room.x + room.w, y);
            }
        }
    },

    tryPlaceDoor: function(x, y) {
        if (TileMap.getTile(x, y) !== TILE_WALL) return;

        // Check if this wall connects a room to a corridor
        let floorCount = 0;
        const neighbors = [
            TileMap.getTile(x - 1, y),
            TileMap.getTile(x + 1, y),
            TileMap.getTile(x, y - 1),
            TileMap.getTile(x, y + 1)
        ];

        for (let i = 0; i < neighbors.length; i++) {
            if (neighbors[i] === TILE_FLOOR) floorCount++;
        }

        if (floorCount >= 2) {
            TileMap.setTile(x, y, TILE_DOOR);
        }
    },

    placeSpecialTiles: function(rooms, floor, rng) {
        if (rooms.length === 0) return;

        // Spawn point: center of first room (or stairs up on floor > 1)
        const firstRoom = rooms[0];
        this.spawnPoint = {
            x: (firstRoom.x + Math.floor(firstRoom.w / 2)) * TILE_SIZE + TILE_SIZE / 2,
            y: (firstRoom.y + Math.floor(firstRoom.h / 2)) * TILE_SIZE + TILE_SIZE / 2
        };

        if (floor > 1) {
            const tx = firstRoom.x + Math.floor(firstRoom.w / 2);
            const ty = firstRoom.y + Math.floor(firstRoom.h / 2);
            TileMap.setTile(tx, ty, TILE_STAIRS_UP);
        }

        // Stairs down: farthest room from spawn
        let maxDist = 0;
        let stairsRoom = rooms[rooms.length - 1];
        for (let i = 0; i < rooms.length; i++) {
            const room = rooms[i];
            const cx = (room.x + Math.floor(room.w / 2)) * TILE_SIZE;
            const cy = (room.y + Math.floor(room.h / 2)) * TILE_SIZE;
            const dist = Util.dist(this.spawnPoint.x, this.spawnPoint.y, cx, cy);
            if (dist > maxDist) {
                maxDist = dist;
                stairsRoom = room;
            }
        }

        const stairsTx = stairsRoom.x + Math.floor(stairsRoom.w / 2);
        const stairsTy = stairsRoom.y + Math.floor(stairsRoom.h / 2);
        TileMap.setTile(stairsTx, stairsTy, TILE_STAIRS_DOWN);
        this.stairsDown = {x: stairsTx, y: stairsTy};

        // Boss floor special handling
        if (floor % 5 === 0) {
            this.generateBossArena(floor, stairsRoom, rng);
        }

        // Campfire: medium-sized room (not first or last)
        if (rooms.length > 2) {
            const campfireRoom = rooms[1 + Math.floor(rng() * (rooms.length - 2))];
            const cfx = campfireRoom.x + Math.floor(campfireRoom.w / 2);
            const cfy = campfireRoom.y + Math.floor(campfireRoom.h / 2);
            TileMap.setTile(cfx, cfy, TILE_CAMPFIRE);
            this.campfire = {x: cfx, y: cfy};
        }

        // Chests: 2-4 in random rooms
        const chestCount = 2 + Math.floor(rng() * 3);
        for (let i = 0; i < chestCount; i++) {
            const room = rooms[Math.floor(rng() * rooms.length)];
            const cx = room.x + 1 + Math.floor(rng() * (room.w - 2));
            const cy = room.y + 1 + Math.floor(rng() * (room.h - 2));
            if (TileMap.getTile(cx, cy) === TILE_FLOOR) {
                TileMap.setTile(cx, cy, TILE_CHEST);
            }
        }

        // Traps: 3-6 in corridors and large rooms
        const trapCount = 3 + Math.floor(rng() * 4);
        for (let i = 0; i < trapCount; i++) {
            const room = rooms[Math.floor(rng() * rooms.length)];
            const tx = room.x + 1 + Math.floor(rng() * (room.w - 2));
            const ty = room.y + 1 + Math.floor(rng() * (room.h - 2));
            if (TileMap.getTile(tx, ty) === TILE_FLOOR) {
                TileMap.setTile(tx, ty, TILE_TRAP);
            }
        }

        // Water pools (Fungal Caverns / Frozen Abyss themes)
        const theme = getFloorTheme(floor);
        if (theme.name === 'Fungal Caverns' || theme.name === 'Frozen Abyss') {
            const poolCount = 1 + Math.floor(rng() * 3);
            for (let i = 0; i < poolCount; i++) {
                const room = rooms[Math.floor(rng() * rooms.length)];
                const poolSize = 2 + Math.floor(rng() * 3);
                const px = room.x + 1 + Math.floor(rng() * (room.w - poolSize - 1));
                const py = room.y + 1 + Math.floor(rng() * (room.h - poolSize - 1));

                for (let dx = 0; dx < poolSize; dx++) {
                    for (let dy = 0; dy < poolSize; dy++) {
                        if (TileMap.getTile(px + dx, py + dy) === TILE_FLOOR) {
                            TileMap.setTile(px + dx, py + dy, TILE_WATER);
                        }
                    }
                }
            }
        }
    },

    generateBossArena: function(floor, stairsRoom, rng) {
        // Create boss arena for boss floors (5, 10, 15, 20, 25)
        const arenaW = 20;
        const arenaH = 15;
        const arenaX = Math.max(2, TileMap.width - arenaW - 2);
        const arenaY = Math.max(2, Math.floor(TileMap.height / 2 - arenaH / 2));

        this.bossArena = {x: arenaX, y: arenaY, w: arenaW, h: arenaH};

        // Carve arena
        for (let y = arenaY - 1; y <= arenaY + arenaH; y++) {
            for (let x = arenaX - 1; x <= arenaX + arenaW; x++) {
                if (x === arenaX - 1 || x === arenaX + arenaW ||
                    y === arenaY - 1 || y === arenaY + arenaH) {
                    TileMap.setTile(x, y, TILE_WALL);
                } else {
                    TileMap.setTile(x, y, TILE_FLOOR);
                }
            }
        }

        // Place boss gate at entrance
        const gateX = arenaX - 1;
        const gateY = arenaY + Math.floor(arenaH / 2);
        TileMap.setTile(gateX, gateY, TILE_BOSS_GATE);
        this.bossGate = {x: gateX, y: gateY};

        // Connect to main dungeon via corridor
        const connectionX = stairsRoom.x + Math.floor(stairsRoom.w / 2);
        const connectionY = stairsRoom.y + Math.floor(stairsRoom.h / 2);
        this.carveCorridor(connectionX, connectionY, gateX - 1, gateY);

        // Place pillars for cover
        const pillarPositions = [
            {x: arenaX + 4, y: arenaY + 4},
            {x: arenaX + arenaW - 5, y: arenaY + 4},
            {x: arenaX + 4, y: arenaY + arenaH - 5},
            {x: arenaX + arenaW - 5, y: arenaY + arenaH - 5}
        ];

        for (let i = 0; i < pillarPositions.length; i++) {
            const pos = pillarPositions[i];
            TileMap.setTile(pos.x, pos.y, TILE_WALL);
            TileMap.setTile(pos.x + 1, pos.y, TILE_WALL);
            TileMap.setTile(pos.x, pos.y + 1, TILE_WALL);
            TileMap.setTile(pos.x + 1, pos.y + 1, TILE_WALL);
        }
    },

    placeDecorations: function(rooms, floor, rng) {
        // Procedural decoration placement
        for (let i = 0; i < rooms.length; i++) {
            const room = rooms[i];
            const decorCount = Math.floor(rng() * 5);

            for (let j = 0; j < decorCount; j++) {
                const dx = room.x + Math.floor(rng() * room.w);
                const dy = room.y + Math.floor(rng() * room.h);

                if (TileMap.getTile(dx, dy) !== TILE_FLOOR) continue;

                const decorType = Math.floor(rng() * 3);
                let decor = null;

                if (decorType === 0) {
                    // Crack
                    decor = {
                        type: 'crack',
                        x1: Math.floor(rng() * TILE_SIZE),
                        y1: Math.floor(rng() * TILE_SIZE),
                        x2: Math.floor(rng() * TILE_SIZE),
                        y2: Math.floor(rng() * TILE_SIZE)
                    };
                } else if (decorType === 1) {
                    // Moss
                    decor = {
                        type: 'moss',
                        x: Math.floor(rng() * (TILE_SIZE - 8)),
                        y: Math.floor(rng() * (TILE_SIZE - 8)),
                        w: 4 + Math.floor(rng() * 6),
                        h: 4 + Math.floor(rng() * 6)
                    };
                } else {
                    // Bones
                    decor = {
                        type: 'bones',
                        x: Math.floor(rng() * (TILE_SIZE - 6)),
                        y: Math.floor(rng() * (TILE_SIZE - 6))
                    };
                }

                TileMap.decor[dy][dx] = decor;
            }
        }
    },

    getSpawnPositions: function(floor, count) {
        // Get valid enemy spawn positions (procedural distribution)
        const positions = [];
        const rooms = TileMap.rooms;

        // Avoid spawn area (first room)
        const spawnTile = TileMap.pixelToTile(this.spawnPoint.x, this.spawnPoint.y);
        const safeRadius = 10;

        let attempts = 0;
        while (positions.length < count && attempts < count * 10) {
            attempts++;

            const room = rooms[Math.floor(Math.random() * rooms.length)];
            const tx = room.x + 1 + Math.floor(Math.random() * (room.w - 2));
            const ty = room.y + 1 + Math.floor(Math.random() * (room.h - 2));

            // Check if tile is walkable and not near spawn
            if (!TileMap.isWalkable(tx, ty)) continue;
            const dist = Util.dist(tx, ty, spawnTile.x, spawnTile.y);
            if (dist < safeRadius) continue;

            // Check if not too close to other spawns
            let tooClose = false;
            for (let i = 0; i < positions.length; i++) {
                const other = positions[i];
                if (Util.dist(tx, ty, other.x, other.y) < 3) {
                    tooClose = true;
                    break;
                }
            }
            if (tooClose) continue;

            positions.push({x: tx, y: ty});
        }

        return positions;
    },

    placeEnemies: function(floor, difficulty) {
        // Procedural enemy placement using spawn tables
        if (!SPAWN_TABLES) return [];

        const table = SPAWN_TABLES[floor] || SPAWN_TABLES[1];
        const baseCount = 8 + floor * 2;
        const difficultyMult = difficulty === 'easy' ? 0.7 : difficulty === 'hard' ? 1.5 : 1;
        const count = Math.floor(baseCount * difficultyMult);

        const positions = this.getSpawnPositions(floor, count);
        const enemies = [];

        for (let i = 0; i < positions.length; i++) {
            const pos = positions[i];
            const roll = Math.random();
            let enemyType = table[0].type;

            // Select enemy type based on spawn weights (procedural)
            let cumulative = 0;
            for (let j = 0; j < table.length; j++) {
                cumulative += table[j].weight;
                if (roll <= cumulative) {
                    enemyType = table[j].type;
                    break;
                }
            }

            enemies.push({
                type: enemyType,
                x: pos.x * TILE_SIZE + TILE_SIZE / 2,
                y: pos.y * TILE_SIZE + TILE_SIZE / 2
            });
        }

        // Place boss on boss floors
        if (floor % 5 === 0 && this.bossArena && BOSS_DEFS) {
            // Find boss for this floor
            let bossType = null;
            for (let bossId in BOSS_DEFS) {
                if (BOSS_DEFS[bossId].floor === floor) {
                    bossType = bossId;
                    break;
                }
            }

            // Fallback to first boss if no match
            if (!bossType) {
                bossType = 'grave_warden';
            }

            const bossX = (this.bossArena.x + Math.floor(this.bossArena.w / 2)) * TILE_SIZE + TILE_SIZE / 2;
            const bossY = (this.bossArena.y + Math.floor(this.bossArena.h / 2)) * TILE_SIZE + TILE_SIZE / 2;

            enemies.push({
                type: bossType,
                x: bossX,
                y: bossY,
                isBoss: true
            });
        }

        return enemies;
    }
};
