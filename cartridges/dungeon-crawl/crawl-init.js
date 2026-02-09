// ============================================================
// DUNGEON CRAWL: DEPTHS OF RUIN - INIT
// Procedural roguelike with permadeath, loot, monsters
// ============================================================

if (mode === 'init') {
  // Tile constants
  G.T_WALL = 0; G.T_FLOOR = 1; G.T_DOOR = 2; G.T_STAIR = 3;
  G.T_CHEST = 4; G.T_TRAP = 5;

  // Map dimensions (tiles)
  G.MW = 32; G.MH = 28; G.TS = 8; // tile size in pixels

  // Game state
  G.floor = 1;
  G.turn = 0;
  G.phase = 'play'; // play | dead | inventory | victory
  G.msg = 'You descend into the depths...';
  G.msgTimer = 120;
  G.shake = 0;
  G.flash = 0;
  G.flashC = '#fff';
  G.kcd = 0;
  G.particles = [];
  G.fov = []; // visibility grid
  G.seen = []; // explored grid (persists per floor)
  G.selIdx = 0;

  // Player
  G.p = {
    x: 0, y: 0,
    hp: 30, maxHp: 30,
    atk: 5, def: 1,
    xp: 0, lvl: 1, xpNext: 12,
    gold: 0,
    inv: [], // items: {name, type, stat, icon}
    weapon: null,
    armor: null,
    kills: 0,
    maxFloor: 1
  };

  // Item tables
  G.weapons = [
    { name: 'Rusty Dagger', stat: 2, icon: '/' },
    { name: 'Short Sword', stat: 4, icon: '†' },
    { name: 'Battle Axe', stat: 6, icon: 'P' },
    { name: 'War Hammer', stat: 8, icon: 'T' },
    { name: 'Flame Blade', stat: 11, icon: '!' },
    { name: 'Doom Cleaver', stat: 14, icon: 'X' }
  ];
  G.armors = [
    { name: 'Leather', stat: 1, icon: '[' },
    { name: 'Chain Mail', stat: 2, icon: '{' },
    { name: 'Plate Armor', stat: 4, icon: '#' },
    { name: 'Dragon Scale', stat: 6, icon: '&' },
    { name: 'Void Armor', stat: 9, icon: '@' }
  ];
  G.potions = [
    { name: 'Heal Potion', type: 'heal', stat: 15, icon: '!' },
    { name: 'Greater Heal', type: 'heal', stat: 30, icon: '!' },
    { name: 'Str Potion', type: 'buff_atk', stat: 2, icon: '!' },
    { name: 'Iron Skin', type: 'buff_def', stat: 2, icon: '!' }
  ];

  // Monster templates (scaled per floor)
  G.monsterTable = [
    { name: 'Rat', icon: 'r', hp: 6, atk: 2, def: 0, xp: 3, gold: 1, color: '#886644' },
    { name: 'Bat', icon: 'b', hp: 4, atk: 3, def: 0, xp: 2, gold: 1, color: '#8866aa' },
    { name: 'Goblin', icon: 'g', hp: 10, atk: 4, def: 1, xp: 5, gold: 3, color: '#44aa44' },
    { name: 'Skeleton', icon: 's', hp: 14, atk: 5, def: 2, xp: 7, gold: 4, color: '#ccccaa' },
    { name: 'Orc', icon: 'o', hp: 20, atk: 7, def: 3, xp: 10, gold: 6, color: '#448844' },
    { name: 'Wraith', icon: 'w', hp: 16, atk: 9, def: 1, xp: 12, gold: 5, color: '#6666cc' },
    { name: 'Troll', icon: 'T', hp: 35, atk: 10, def: 4, xp: 18, gold: 10, color: '#668844' },
    { name: 'Dragon', icon: 'D', hp: 60, atk: 15, def: 6, xp: 40, gold: 25, color: '#ff4444' }
  ];

  // Active map entities
  G.map = [];
  G.monsters = [];
  G.items = []; // items on ground: {x, y, item}

  // ─── PROCEDURAL DUNGEON GENERATOR ───
  G.genFloor = function(floor) {
    // Reset map to walls
    G.map = [];
    G.monsters = [];
    G.items = [];
    G.fov = [];
    G.seen = [];
    for (var y = 0; y < G.MH; y++) {
      G.map[y] = [];
      G.fov[y] = [];
      G.seen[y] = [];
      for (var x = 0; x < G.MW; x++) {
        G.map[y][x] = G.T_WALL;
        G.fov[y][x] = false;
        G.seen[y][x] = false;
      }
    }

    // Generate rooms
    var rooms = [];
    var numRooms = 6 + Math.floor(Math.random() * 4) + Math.floor(floor * 0.5);
    var attempts = 0;
    while (rooms.length < numRooms && attempts < 200) {
      attempts++;
      var rw = 3 + Math.floor(Math.random() * 5);
      var rh = 3 + Math.floor(Math.random() * 4);
      var rx = 1 + Math.floor(Math.random() * (G.MW - rw - 2));
      var ry = 1 + Math.floor(Math.random() * (G.MH - rh - 2));

      // Check overlap
      var overlap = false;
      for (var i = 0; i < rooms.length; i++) {
        var r = rooms[i];
        if (rx - 1 < r.x + r.w && rx + rw + 1 > r.x && ry - 1 < r.y + r.h && ry + rh + 1 > r.y) {
          overlap = true; break;
        }
      }
      if (!overlap) {
        rooms.push({ x: rx, y: ry, w: rw, h: rh, cx: Math.floor(rx + rw / 2), cy: Math.floor(ry + rh / 2) });
        // Carve room
        for (var dy = 0; dy < rh; dy++) {
          for (var dx = 0; dx < rw; dx++) {
            G.map[ry + dy][rx + dx] = G.T_FLOOR;
          }
        }
      }
    }

    // Connect rooms with corridors
    for (var i = 1; i < rooms.length; i++) {
      var a = rooms[i - 1], b = rooms[i];
      var cx = a.cx, cy = a.cy;
      var tx = b.cx, ty = b.cy;
      // L-shaped corridor
      if (Math.random() < 0.5) {
        // Horizontal first
        var sx = cx < tx ? 1 : -1;
        while (cx !== tx) { G.map[cy][cx] = G.T_FLOOR; cx += sx; }
        var sy = cy < ty ? 1 : -1;
        while (cy !== ty) { G.map[cy][cx] = G.T_FLOOR; cy += sy; }
      } else {
        // Vertical first
        var sy = cy < ty ? 1 : -1;
        while (cy !== ty) { G.map[cy][cx] = G.T_FLOOR; cy += sy; }
        var sx = cx < tx ? 1 : -1;
        while (cx !== tx) { G.map[cy][cx] = G.T_FLOOR; cx += sx; }
      }
      G.map[ty][tx] = G.T_FLOOR;
    }

    // Place doors at chokepoints
    for (var y = 1; y < G.MH - 1; y++) {
      for (var x = 1; x < G.MW - 1; x++) {
        if (G.map[y][x] !== G.T_FLOOR) continue;
        // Horizontal chokepoint
        if (G.map[y-1][x] === G.T_WALL && G.map[y+1][x] === G.T_WALL &&
            G.map[y][x-1] === G.T_FLOOR && G.map[y][x+1] === G.T_FLOOR) {
          if (Math.random() < 0.25) G.map[y][x] = G.T_DOOR;
        }
        // Vertical chokepoint
        if (G.map[y][x-1] === G.T_WALL && G.map[y][x+1] === G.T_WALL &&
            G.map[y-1][x] === G.T_FLOOR && G.map[y+1][x] === G.T_FLOOR) {
          if (Math.random() < 0.25) G.map[y][x] = G.T_DOOR;
        }
      }
    }

    // Place player in first room
    G.p.x = rooms[0].cx;
    G.p.y = rooms[0].cy;

    // Place stairs in last room
    var lastRoom = rooms[rooms.length - 1];
    G.map[lastRoom.cy][lastRoom.cx] = G.T_STAIR;

    // Place chests (1-3)
    var numChests = 1 + Math.floor(Math.random() * 2) + (floor % 3 === 0 ? 1 : 0);
    for (var c = 0; c < numChests; c++) {
      var rIdx = 1 + Math.floor(Math.random() * (rooms.length - 2));
      var rm = rooms[rIdx];
      var cx = rm.x + Math.floor(Math.random() * rm.w);
      var cy = rm.y + Math.floor(Math.random() * rm.h);
      if (G.map[cy][cx] === G.T_FLOOR) G.map[cy][cx] = G.T_CHEST;
    }

    // Place traps on deeper floors
    if (floor >= 3) {
      var numTraps = Math.floor(floor / 2);
      for (var t = 0; t < numTraps; t++) {
        var rIdx = 1 + Math.floor(Math.random() * (rooms.length - 1));
        var rm = rooms[rIdx];
        var tx = rm.x + Math.floor(Math.random() * rm.w);
        var ty = rm.y + Math.floor(Math.random() * rm.h);
        if (G.map[ty][tx] === G.T_FLOOR) G.map[ty][tx] = G.T_TRAP;
      }
    }

    // Spawn monsters
    var numMons = 4 + floor * 2 + Math.floor(Math.random() * 3);
    var maxTier = Math.min(G.monsterTable.length - 1, Math.floor(floor / 2) + 1);
    for (var m = 0; m < numMons; m++) {
      var rIdx = 1 + Math.floor(Math.random() * (rooms.length - 1));
      var rm = rooms[rIdx];
      var mx = rm.x + Math.floor(Math.random() * rm.w);
      var my = rm.y + Math.floor(Math.random() * rm.h);
      if (mx === G.p.x && my === G.p.y) continue;
      if (G.map[my][mx] === G.T_WALL) continue;

      // Pick tier, weighted toward lower
      var tier = Math.floor(Math.random() * (maxTier + 1));
      if (Math.random() < 0.3) tier = Math.min(tier + 1, maxTier);
      var tmpl = G.monsterTable[tier];
      var scale = 1 + (floor - 1) * 0.15;
      G.monsters.push({
        x: mx, y: my,
        name: tmpl.name, icon: tmpl.icon, color: tmpl.color,
        hp: Math.ceil(tmpl.hp * scale), maxHp: Math.ceil(tmpl.hp * scale),
        atk: Math.ceil(tmpl.atk * scale), def: Math.floor(tmpl.def * scale),
        xp: Math.ceil(tmpl.xp * scale), gold: Math.ceil(tmpl.gold * scale),
        awake: false, // becomes true when player is in FOV
        lastSawX: -1, lastSawY: -1
      });
    }

    // Drop some items on the ground
    var numDrops = 1 + Math.floor(Math.random() * 2);
    for (var d = 0; d < numDrops; d++) {
      var rIdx = 1 + Math.floor(Math.random() * (rooms.length - 1));
      var rm = rooms[rIdx];
      var ix = rm.x + Math.floor(Math.random() * rm.w);
      var iy = rm.y + Math.floor(Math.random() * rm.h);
      if (G.map[iy][ix] === G.T_FLOOR) {
        var item = G.genLoot(floor);
        G.items.push({ x: ix, y: iy, item: item });
      }
    }
  };

  // ─── LOOT GENERATOR ───
  G.genLoot = function(floor) {
    var r = Math.random();
    if (r < 0.35) {
      // Potion
      var p = G.potions[Math.floor(Math.random() * Math.min(G.potions.length, 2 + Math.floor(floor / 3)))];
      return { name: p.name, type: p.type, stat: p.stat, icon: p.icon, category: 'potion' };
    } else if (r < 0.65) {
      // Weapon
      var maxW = Math.min(G.weapons.length, 1 + Math.floor(floor / 2));
      var w = G.weapons[Math.floor(Math.random() * maxW)];
      return { name: w.name, type: 'weapon', stat: w.stat, icon: w.icon, category: 'weapon' };
    } else if (r < 0.9) {
      // Armor
      var maxA = Math.min(G.armors.length, 1 + Math.floor(floor / 2));
      var a = G.armors[Math.floor(Math.random() * maxA)];
      return { name: a.name, type: 'armor', stat: a.stat, icon: a.icon, category: 'armor' };
    } else {
      // Gold pile
      var amt = 5 + Math.floor(Math.random() * floor * 5);
      return { name: amt + ' Gold', type: 'gold', stat: amt, icon: '$', category: 'gold' };
    }
  };

  // ─── FOV (simple raycasting) ───
  G.calcFOV = function() {
    for (var y = 0; y < G.MH; y++)
      for (var x = 0; x < G.MW; x++) G.fov[y][x] = false;

    var radius = 6;
    var steps = 72;
    for (var i = 0; i < steps; i++) {
      var angle = (i / steps) * Math.PI * 2;
      var dx = Math.cos(angle);
      var dy = Math.sin(angle);
      var cx = G.p.x + 0.5;
      var cy = G.p.y + 0.5;
      for (var d = 0; d < radius; d++) {
        var tx = Math.floor(cx);
        var ty = Math.floor(cy);
        if (tx < 0 || tx >= G.MW || ty < 0 || ty >= G.MH) break;
        G.fov[ty][tx] = true;
        G.seen[ty][tx] = true;
        if (G.map[ty][tx] === G.T_WALL) break;
        cx += dx;
        cy += dy;
      }
    }
  };

  // ─── LEVEL UP ───
  G.levelUp = function() {
    G.p.lvl++;
    G.p.maxHp += 5 + G.p.lvl;
    G.p.hp = G.p.maxHp;
    G.p.atk += 1;
    G.p.def += (G.p.lvl % 2 === 0) ? 1 : 0;
    G.p.xpNext = Math.ceil(G.p.xpNext * 1.6);
    G.p.xp = 0;
    G.msg = 'Level up! You are now level ' + G.p.lvl;
    G.msgTimer = 120;
    G.flash = 15; G.flashC = '#ffcc00';
    snd.win();
    for (var i = 0; i < 16; i++)
      G.particles.push({ x: G.p.x * G.TS + G.TS/2, y: G.p.y * G.TS + G.TS/2, vx: (Math.random()-0.5)*4, vy: (Math.random()-0.5)*4, life: 25, c: '#ffcc00', s: 2 });
  };

  // Generate first floor
  G.genFloor(1);
  G.calcFOV();
}
