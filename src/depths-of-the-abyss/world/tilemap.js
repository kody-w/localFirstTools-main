// tilemap.js — Tile rendering and collision for Depths of the Abyss
// Depends on: G (state), STATE, TILE_SIZE, FLOOR_THEMES, getFloorTheme() from constants.js
// Depends on: Util from utils.js

// Tile type constants
const TILE_VOID = 0;
const TILE_FLOOR = 1;
const TILE_WALL = 2;
const TILE_DOOR = 3;
const TILE_STAIRS_DOWN = 4;
const TILE_STAIRS_UP = 5;
const TILE_CAMPFIRE = 6;
const TILE_CHEST = 7;
const TILE_TRAP = 8;
const TILE_WATER = 9;
const TILE_BOSS_GATE = 10;

const TileMap = {
    tiles: [],
    width: 0,
    height: 0,
    rooms: [],
    decor: [], // Cached decorations per tile
    chests: [], // Track chest states {x, y, opened}
    traps: [], // Track trap states {x, y, triggered}

    init: function(width, height) {
        this.width = width;
        this.height = height;
        this.tiles = [];
        this.decor = [];
        this.rooms = [];
        this.chests = [];
        this.traps = [];

        for (let y = 0; y < height; y++) {
            this.tiles[y] = [];
            this.decor[y] = [];
            for (let x = 0; x < width; x++) {
                this.tiles[y][x] = TILE_VOID;
                this.decor[y][x] = null;
            }
        }
    },

    setTile: function(x, y, type) {
        if (x < 0 || x >= this.width || y < 0 || y >= this.height) return;
        this.tiles[y][x] = type;

        // Track special tiles
        if (type === TILE_CHEST) {
            if (!this.chests.find(c => c.x === x && c.y === y)) {
                this.chests.push({x, y, opened: false});
            }
        } else if (type === TILE_TRAP) {
            if (!this.traps.find(t => t.x === x && t.y === y)) {
                this.traps.push({x, y, triggered: false});
            }
        }
    },

    getTile: function(x, y) {
        if (x < 0 || x >= this.width || y < 0 || y >= this.height) return TILE_VOID;
        return this.tiles[y][x];
    },

    isWalkable: function(x, y) {
        const tile = this.getTile(x, y);
        return tile === TILE_FLOOR || tile === TILE_DOOR ||
               tile === TILE_STAIRS_DOWN || tile === TILE_STAIRS_UP ||
               tile === TILE_CAMPFIRE || tile === TILE_TRAP || tile === TILE_WATER;
    },

    isSolid: function(x, y) {
        const tile = this.getTile(x, y);
        return tile === TILE_VOID || tile === TILE_WALL || tile === TILE_BOSS_GATE;
    },

    pixelToTile: function(px, py) {
        return {
            x: Math.floor(px / TILE_SIZE),
            y: Math.floor(py / TILE_SIZE)
        };
    },

    tileToPixel: function(tx, ty) {
        return {
            x: tx * TILE_SIZE,
            y: ty * TILE_SIZE
        };
    },

    render: function(ctx, camera) {
        const bounds = camera.getViewBounds();
        const startX = Math.max(0, Math.floor(bounds.left / TILE_SIZE));
        const startY = Math.max(0, Math.floor(bounds.top / TILE_SIZE));
        const endX = Math.min(this.width - 1, Math.ceil(bounds.right / TILE_SIZE));
        const endY = Math.min(this.height - 1, Math.ceil(bounds.bottom / TILE_SIZE));

        const theme = getFloorTheme(G.currentFloor);

        for (let y = startY; y <= endY; y++) {
            for (let x = startX; x <= endX; x++) {
                const tile = this.tiles[y][x];
                const px = x * TILE_SIZE;
                const py = y * TILE_SIZE;

                // Skip void
                if (tile === TILE_VOID) continue;

                // Base tile rendering
                ctx.fillStyle = this.getTileColor(tile, theme);
                ctx.fillRect(px, py, TILE_SIZE, TILE_SIZE);

                // Special rendering per tile type
                switch(tile) {
                    case TILE_WALL:
                        this.renderWall(ctx, px, py, theme);
                        break;
                    case TILE_DOOR:
                        this.renderDoor(ctx, px, py, theme);
                        break;
                    case TILE_STAIRS_DOWN:
                        this.renderStairs(ctx, px, py, theme, true);
                        break;
                    case TILE_STAIRS_UP:
                        this.renderStairs(ctx, px, py, theme, false);
                        break;
                    case TILE_CAMPFIRE:
                        this.renderCampfire(ctx, px, py);
                        break;
                    case TILE_CHEST:
                        this.renderChest(ctx, px, py, x, y);
                        break;
                    case TILE_TRAP:
                        this.renderTrap(ctx, px, py, x, y);
                        break;
                    case TILE_WATER:
                        this.renderWater(ctx, px, py);
                        break;
                    case TILE_BOSS_GATE:
                        this.renderBossGate(ctx, px, py);
                        break;
                }
            }
        }
    },

    getTileColor: function(tile, theme) {
        switch(tile) {
            case TILE_FLOOR: return theme.floor;
            case TILE_WALL: return theme.wall;
            case TILE_DOOR: return theme.door;
            case TILE_STAIRS_DOWN: return theme.floor;
            case TILE_STAIRS_UP: return theme.floor;
            case TILE_CAMPFIRE: return theme.floor;
            case TILE_CHEST: return theme.floor;
            case TILE_TRAP: return theme.floor;
            case TILE_WATER: return '#1a3d5c';
            case TILE_BOSS_GATE: return '#4a0000';
            default: return '#000';
        }
    },

    renderWall: function(ctx, px, py, theme) {
        // 3D effect: darker top, lighter bottom
        const grad = ctx.createLinearGradient(px, py, px, py + TILE_SIZE);
        grad.addColorStop(0, this.darkenColor(theme.wall, 0.7));
        grad.addColorStop(1, this.lightenColor(theme.wall, 1.2));
        ctx.fillStyle = grad;
        ctx.fillRect(px, py, TILE_SIZE, TILE_SIZE);

        // Edge highlight
        ctx.strokeStyle = this.lightenColor(theme.wall, 1.3);
        ctx.lineWidth = 1;
        ctx.strokeRect(px + 0.5, py + 0.5, TILE_SIZE - 1, TILE_SIZE - 1);
    },

    renderDoor: function(ctx, px, py, theme) {
        // Door frame
        ctx.fillStyle = theme.door;
        ctx.fillRect(px + 4, py, TILE_SIZE - 8, TILE_SIZE);
        ctx.fillRect(px, py + 4, TILE_SIZE, TILE_SIZE - 8);

        // Frame outline
        ctx.strokeStyle = this.darkenColor(theme.door, 0.8);
        ctx.lineWidth = 2;
        ctx.strokeRect(px + 2, py + 2, TILE_SIZE - 4, TILE_SIZE - 4);
    },

    renderStairs: function(ctx, px, py, theme, down) {
        const centerX = px + TILE_SIZE / 2;
        const centerY = py + TILE_SIZE / 2;
        const arrowSize = 8;

        ctx.fillStyle = down ? '#888' : '#666';
        ctx.beginPath();
        if (down) {
            // Down arrow
            ctx.moveTo(centerX, centerY + arrowSize);
            ctx.lineTo(centerX - arrowSize, centerY - arrowSize);
            ctx.lineTo(centerX + arrowSize, centerY - arrowSize);
        } else {
            // Up arrow
            ctx.moveTo(centerX, centerY - arrowSize);
            ctx.lineTo(centerX - arrowSize, centerY + arrowSize);
            ctx.lineTo(centerX + arrowSize, centerY + arrowSize);
        }
        ctx.closePath();
        ctx.fill();
    },

    renderCampfire: function(ctx, px, py) {
        const centerX = px + TILE_SIZE / 2;
        const centerY = py + TILE_SIZE / 2;

        // Animated flicker using G.time
        const flicker = Math.sin(G.time * 5) * 0.3 + 0.7;
        const radius = 6 + Math.sin(G.time * 8) * 2;

        // Fire glow
        const grad = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, radius * 2);
        grad.addColorStop(0, 'rgba(255, 180, 0, ' + (flicker * 0.8) + ')');
        grad.addColorStop(0.5, 'rgba(255, 100, 0, ' + (flicker * 0.4) + ')');
        grad.addColorStop(1, 'rgba(255, 50, 0, 0)');
        ctx.fillStyle = grad;
        ctx.fillRect(centerX - radius * 2, centerY - radius * 2, radius * 4, radius * 4);

        // Fire core
        ctx.fillStyle = flicker > 0.8 ? '#ffff00' : '#ff8800';
        ctx.beginPath();
        ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
        ctx.fill();
    },

    renderChest: function(ctx, px, py, tx, ty) {
        const chest = this.chests.find(c => c.x === tx && c.y === ty);
        const opened = chest ? chest.opened : false;

        if (opened) {
            // Just render as floor after opened
            return;
        }

        // Golden chest
        const grad = ctx.createLinearGradient(px, py, px, py + TILE_SIZE);
        grad.addColorStop(0, '#ffdd00');
        grad.addColorStop(0.5, '#ffaa00');
        grad.addColorStop(1, '#ff8800');
        ctx.fillStyle = grad;
        ctx.fillRect(px + 6, py + 8, TILE_SIZE - 12, TILE_SIZE - 10);

        // Highlight
        ctx.strokeStyle = '#ffff88';
        ctx.lineWidth = 1;
        ctx.strokeRect(px + 7, py + 9, TILE_SIZE - 14, TILE_SIZE - 12);
    },

    renderTrap: function(ctx, px, py, tx, ty) {
        const trap = this.traps.find(t => t.x === tx && t.y === ty);
        const triggered = trap ? trap.triggered : false;
        const hasTrapSight = G.player && G.player.trapSight;

        if (!triggered && !hasTrapSight) {
            // Invisible until triggered or player has trap sight
            return;
        }

        // Red warning pattern
        ctx.strokeStyle = triggered ? '#ff0000' : '#aa0000';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(px + TILE_SIZE / 2, py + 4);
        ctx.lineTo(px + TILE_SIZE - 4, py + TILE_SIZE - 4);
        ctx.lineTo(px + 4, py + TILE_SIZE - 4);
        ctx.closePath();
        ctx.stroke();
    },

    renderWater: function(ctx, px, py) {
        // Animated wave effect using sin
        const wave1 = Math.sin(G.time * 2 + px * 0.1) * 0.1 + 0.9;
        const wave2 = Math.cos(G.time * 3 + py * 0.1) * 0.1 + 0.9;
        const brightness = wave1 * wave2;

        const baseColor = [26, 61, 92]; // #1a3d5c
        const r = Math.floor(baseColor[0] * brightness);
        const g = Math.floor(baseColor[1] * brightness);
        const b = Math.floor(baseColor[2] * brightness);

        ctx.fillStyle = 'rgb(' + r + ',' + g + ',' + b + ')';
        ctx.fillRect(px, py, TILE_SIZE, TILE_SIZE);

        // Reflection shimmer
        const shimmer = Math.sin(G.time * 4 + px * 0.2 + py * 0.2);
        if (shimmer > 0.7) {
            ctx.fillStyle = 'rgba(100, 150, 200, 0.3)';
            ctx.fillRect(px + 8, py + 8, TILE_SIZE - 16, TILE_SIZE - 16);
        }
    },

    renderBossGate: function(ctx, px, py) {
        // Red pulsing glow
        const pulse = Math.sin(G.time * 3) * 0.3 + 0.7;

        const grad = ctx.createRadialGradient(
            px + TILE_SIZE / 2, py + TILE_SIZE / 2, 0,
            px + TILE_SIZE / 2, py + TILE_SIZE / 2, TILE_SIZE
        );
        grad.addColorStop(0, 'rgba(255, 0, 0, ' + (pulse * 0.6) + ')');
        grad.addColorStop(1, 'rgba(74, 0, 0, 1)');
        ctx.fillStyle = grad;
        ctx.fillRect(px, py, TILE_SIZE, TILE_SIZE);

        // Gate bars
        ctx.strokeStyle = '#ff0000';
        ctx.lineWidth = 3;
        for (let i = 0; i < 4; i++) {
            ctx.beginPath();
            ctx.moveTo(px + i * 8 + 4, py);
            ctx.lineTo(px + i * 8 + 4, py + TILE_SIZE);
            ctx.stroke();
        }
    },

    renderDecor: function(ctx, camera) {
        const bounds = camera.getViewBounds();
        const startX = Math.max(0, Math.floor(bounds.left / TILE_SIZE));
        const startY = Math.max(0, Math.floor(bounds.top / TILE_SIZE));
        const endX = Math.min(this.width - 1, Math.ceil(bounds.right / TILE_SIZE));
        const endY = Math.min(this.height - 1, Math.ceil(bounds.bottom / TILE_SIZE));

        for (let y = startY; y <= endY; y++) {
            for (let x = startX; x <= endX; x++) {
                const decor = this.decor[y][x];
                if (!decor) continue;

                const px = x * TILE_SIZE;
                const py = y * TILE_SIZE;

                ctx.globalAlpha = 0.3;
                ctx.fillStyle = '#333';

                switch(decor.type) {
                    case 'crack':
                        // Floor crack
                        ctx.beginPath();
                        ctx.moveTo(px + decor.x1, py + decor.y1);
                        ctx.lineTo(px + decor.x2, py + decor.y2);
                        ctx.strokeStyle = '#222';
                        ctx.lineWidth = 1;
                        ctx.stroke();
                        break;
                    case 'moss':
                        // Moss patch
                        ctx.fillStyle = '#1a3d1a';
                        ctx.fillRect(px + decor.x, py + decor.y, decor.w, decor.h);
                        break;
                    case 'bones':
                        // Small bones
                        ctx.fillStyle = '#888';
                        ctx.fillRect(px + decor.x, py + decor.y, 4, 2);
                        ctx.fillRect(px + decor.x + 2, py + decor.y + 3, 2, 4);
                        break;
                }

                ctx.globalAlpha = 1;
            }
        }
    },

    interact: function(tx, ty) {
        const tile = this.getTile(tx, ty);

        switch(tile) {
            case TILE_CHEST:
                return this.openChest(tx, ty);
            case TILE_CAMPFIRE:
                return this.useCampfire(tx, ty);
            case TILE_STAIRS_DOWN:
                return this.descendStairs();
            case TILE_TRAP:
                return this.triggerTrap(tx, ty);
        }

        return null;
    },

    openChest: function(tx, ty) {
        const chest = this.chests.find(c => c.x === tx && c.y === ty);
        if (!chest || chest.opened) return null;

        chest.opened = true;
        this.setTile(tx, ty, TILE_FLOOR); // Becomes floor after opening

        return {type: 'chest', x: tx, y: ty};
    },

    useCampfire: function(tx, ty) {
        return {type: 'campfire', x: tx, y: ty};
    },

    descendStairs: function() {
        return {type: 'stairs_down'};
    },

    triggerTrap: function(tx, ty) {
        const trap = this.traps.find(t => t.x === tx && t.y === ty);
        if (!trap) return null;

        if (!trap.triggered) {
            trap.triggered = true;
            return {type: 'trap', x: tx, y: ty, damage: 10 + G.currentFloor * 2};
        }

        return null;
    },

    darkenColor: function(color, factor) {
        const hex = color.replace('#', '');
        const r = Math.floor(parseInt(hex.substring(0, 2), 16) * factor);
        const g = Math.floor(parseInt(hex.substring(2, 4), 16) * factor);
        const b = Math.floor(parseInt(hex.substring(4, 6), 16) * factor);
        return '#' + this.toHex(r) + this.toHex(g) + this.toHex(b);
    },

    lightenColor: function(color, factor) {
        const hex = color.replace('#', '');
        const r = Math.min(255, Math.floor(parseInt(hex.substring(0, 2), 16) * factor));
        const g = Math.min(255, Math.floor(parseInt(hex.substring(2, 4), 16) * factor));
        const b = Math.min(255, Math.floor(parseInt(hex.substring(4, 6), 16) * factor));
        return '#' + this.toHex(r) + this.toHex(g) + this.toHex(b);
    },

    toHex: function(n) {
        const hex = n.toString(16);
        return hex.length === 1 ? '0' + hex : hex;
    }
};
