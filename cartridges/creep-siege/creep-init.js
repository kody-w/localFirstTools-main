// ============================================================
// CREEP SIEGE: ANCIENT OFFENSIVE - INIT
// Reverse tower defense — you ARE the creep wave
// Dota-inspired: lanes, creep types, tower tiers, evolve system
// ============================================================

if (mode === 'init') {
  // Grid: 16x14 tiles, each 16px
  G.GW = 16; G.GH = 14; G.TS = 16;
  G.wave = 1; G.maxWave = 20;
  G.phase = 'spawn'; // spawn | battle | evolve | victory | defeat
  G.gold = 50; G.totalGold = 50;
  G.score = 0;
  G.lives = 3; // creeps that must reach end to win wave
  G.reached = 0;
  G.waveTimer = 0;
  G.shake = 0; G.flash = 0; G.flashC = '#fff';
  G.kcd = 0; G.selIdx = 0;
  G.particles = [];
  G.dmgNums = [];
  G.showEvolve = false;

  // ─── MAP GRID ───
  // 0=path, 1=wall, 2=spawn, 3=base(goal)
  // Generate a winding path with lanes (Dota-style 3 lanes)
  G.grid = [];
  for (var y = 0; y < G.GH; y++) {
    G.grid[y] = [];
    for (var x = 0; x < G.GW; x++) G.grid[y][x] = 1;
  }

  // Carve 3 lanes: top, mid, bottom
  // Top lane: row 1-2, goes right
  for (var x = 0; x < G.GW; x++) { G.grid[1][x] = 0; G.grid[2][x] = 0; }
  // Mid lane: row 6-7, goes right
  for (var x = 0; x < G.GW; x++) { G.grid[6][x] = 0; G.grid[7][x] = 0; }
  // Bot lane: row 11-12, goes right
  for (var x = 0; x < G.GW; x++) { G.grid[11][x] = 0; G.grid[12][x] = 0; }
  // Connecting corridors (jungle paths)
  // Left jungle: x=3, connect top-mid
  for (var y = 2; y <= 6; y++) G.grid[y][3] = 0;
  // Left jungle: x=4, connect mid-bot
  for (var y = 7; y <= 11; y++) G.grid[y][4] = 0;
  // Right jungle: x=12, connect top-mid
  for (var y = 2; y <= 6; y++) G.grid[y][12] = 0;
  // Right jungle: x=11, connect mid-bot
  for (var y = 7; y <= 11; y++) G.grid[y][11] = 0;
  // Mid shortcut
  for (var y = 3; y <= 5; y++) G.grid[y][8] = 0;
  for (var y = 8; y <= 10; y++) G.grid[y][8] = 0;

  // Spawn points (left edge)
  G.grid[1][0] = 2; G.grid[6][0] = 2; G.grid[11][0] = 2;
  // Base/goal (right edge)
  G.grid[1][15] = 3; G.grid[7][15] = 3; G.grid[12][15] = 3;

  // Pathfinding: precompute BFS from each path cell to nearest goal
  G.flowField = [];
  for (var y = 0; y < G.GH; y++) {
    G.flowField[y] = [];
    for (var x = 0; x < G.GW; x++) G.flowField[y][x] = null;
  }

  // BFS from all goal cells
  var queue = [];
  var visited = [];
  for (var y = 0; y < G.GH; y++) { visited[y] = []; for (var x = 0; x < G.GW; x++) visited[y][x] = false; }
  for (var y = 0; y < G.GH; y++) {
    for (var x = 0; x < G.GW; x++) {
      if (G.grid[y][x] === 3) { queue.push({x:x, y:y, dist:0}); visited[y][x] = true; G.flowField[y][x] = {dx:0, dy:0, dist:0}; }
    }
  }
  var dirs = [{dx:1,dy:0},{dx:-1,dy:0},{dx:0,dy:1},{dx:0,dy:-1}];
  while (queue.length > 0) {
    var cur = queue.shift();
    for (var d = 0; d < 4; d++) {
      var nx = cur.x + dirs[d].dx, ny = cur.y + dirs[d].dy;
      if (nx >= 0 && nx < G.GW && ny >= 0 && ny < G.GH && !visited[ny][nx] && G.grid[ny][nx] !== 1) {
        visited[ny][nx] = true;
        G.flowField[ny][nx] = { dx: -dirs[d].dx, dy: -dirs[d].dy, dist: cur.dist + 1 };
        queue.push({x:nx, y:ny, dist:cur.dist+1});
      }
    }
  }

  // ─── TOWERS (AI-placed) ───
  G.towers = [];
  G.towerTypes = {
    arrow:   { name:'Arrow',   dmg:8,  rate:30, range:48,  color:'#44aaff', projSpd:4, projC:'#88ccff', slow:0 },
    cannon:  { name:'Cannon',  dmg:25, rate:60, range:40,  color:'#ff8844', projSpd:2.5, projC:'#ffaa44', slow:0, splash:20 },
    frost:   { name:'Frost',   dmg:5,  rate:40, range:52,  color:'#88ffff', projSpd:3, projC:'#aaffff', slow:0.5 },
    venom:   { name:'Venom',   dmg:3,  rate:35, range:44,  color:'#44ff44', projSpd:3, projC:'#88ff88', slow:0, dot:4 },
    arcane:  { name:'Arcane',  dmg:15, rate:50, range:56,  color:'#cc44ff', projSpd:3.5, projC:'#dd88ff', slow:0, manaburn:1 }
  };
  G.projectiles = [];

  // ─── CREEP TYPES (player spawns) ───
  G.creeps = [];
  G.creepTypes = [
    { id:'melee',  name:'Melee Creep',  icon:'♟', hp:40,  speed:0.8, cost:5,  armor:1, magic:0, reward:3, desc:'Balanced fighter' },
    { id:'ranged', name:'Ranged Creep',  icon:'♜', hp:25,  speed:0.7, cost:7,  armor:0, magic:1, reward:4, desc:'Magic resistant' },
    { id:'siege',  name:'Siege Creep',   icon:'♞', hp:80,  speed:0.5, cost:12, armor:3, magic:0, reward:6, desc:'Heavy armor tank' },
    { id:'speed',  name:'Phase Creep',   icon:'♝', hp:20,  speed:1.5, cost:8,  armor:0, magic:0, reward:5, desc:'Blazing speed' },
    { id:'mega',   name:'Mega Creep',    icon:'♛', hp:150, speed:0.4, cost:25, armor:2, magic:2, reward:12, desc:'Unstoppable force' }
  ];

  // ─── EVOLUTION TREE ───
  // After each wave, pick 1 of 3 random evolutions
  G.evolutions = [];
  G.evoPool = [
    { id:'hp1',      name:'Vitality+',    desc:'All creeps +15% HP',       icon:'♥', apply:function(){G.creepTypes.forEach(function(c){c.hp=Math.ceil(c.hp*1.15)})} },
    { id:'hp2',      name:'Vitality++',   desc:'All creeps +25% HP',       icon:'♥♥', apply:function(){G.creepTypes.forEach(function(c){c.hp=Math.ceil(c.hp*1.25)})} },
    { id:'spd1',     name:'Swiftness+',   desc:'All creeps +15% speed',    icon:'»', apply:function(){G.creepTypes.forEach(function(c){c.speed*=1.15})} },
    { id:'arm1',     name:'Armor+',       desc:'All creeps +1 armor',      icon:'◆', apply:function(){G.creepTypes.forEach(function(c){c.armor+=1})} },
    { id:'arm2',     name:'Armor++',      desc:'All creeps +2 armor',      icon:'◆◆', apply:function(){G.creepTypes.forEach(function(c){c.armor+=2})} },
    { id:'mag1',     name:'Magic Shell',  desc:'All creeps +1 magic res',  icon:'✧', apply:function(){G.creepTypes.forEach(function(c){c.magic+=1})} },
    { id:'regen1',   name:'Regen',        desc:'Creeps heal 1hp/sec',      icon:'♻', apply:function(){G._regen=(G._regen||0)+1} },
    { id:'thorns',   name:'Thorns',       desc:'Towers take 5 dmg on hit', icon:'⚡', apply:function(){G._thorns=(G._thorns||0)+5} },
    { id:'gold1',    name:'Plunder',      desc:'+5 gold per wave',         icon:'$', apply:function(){G._bonusGold=(G._bonusGold||0)+5} },
    { id:'discount', name:'Efficiency',   desc:'Creep costs -20%',         icon:'↓', apply:function(){G.creepTypes.forEach(function(c){c.cost=Math.max(1,Math.ceil(c.cost*0.8))})} },
    { id:'splash1',  name:'Scatter',      desc:'Creeps split into 2 on death', icon:'÷', apply:function(){G._splitOnDeath=(G._splitOnDeath||0)+1} },
    { id:'invis',    name:'Shadow Walk',  desc:'Phase Creeps get 2s invis on spawn', icon:'◌', apply:function(){G._invisTime=(G._invisTime||0)+120} },
    { id:'mega1',    name:'Ancient Power',desc:'Mega Creeps +50% HP',      icon:'♛+', apply:function(){var m=G.creepTypes.find(function(c){return c.id==='mega'});if(m)m.hp=Math.ceil(m.hp*1.5)} },
    { id:'lifesteal',name:'Vampiric',     desc:'Creeps heal 20% of tower dmg taken', icon:'🦇', apply:function(){G._lifesteal=(G._lifesteal||0)+0.2} }
  ];
  G.evoChoices = null; // 3 choices shown between waves

  // ─── AI TOWER PLACEMENT STRATEGY ───
  // The AI analyzes which creep types you're using and places counters
  G.aiMemory = { melee:0, ranged:0, siege:0, speed:0, mega:0 };
  G._regen = 0; G._thorns = 0; G._bonusGold = 0;
  G._splitOnDeath = 0; G._invisTime = 0; G._lifesteal = 0;

  // Spawn queue for current wave
  G.spawnQueue = [];
  G.spawnTimer = 0;
  G.spawnLane = 1; // 0=top, 1=mid, 2=bot
  G.laneRows = [1, 6, 11]; // y-row for each lane spawn

  // Place initial towers for wave 1
  G.placeTowers = function(w) {
    // AI selects tower types based on memory
    var budget = 2 + Math.floor(w * 1.5);
    var spots = [];
    // Find wall cells adjacent to path
    for (var y = 0; y < G.GH; y++) {
      for (var x = 0; x < G.GW; x++) {
        if (G.grid[y][x] !== 1) continue;
        var adj = false;
        for (var d = 0; d < 4; d++) {
          var nx = x+dirs[d].dx, ny = y+dirs[d].dy;
          if (nx>=0&&nx<G.GW&&ny>=0&&ny<G.GH&&G.grid[ny][nx]===0) adj = true;
        }
        if (adj && !G.towers.some(function(t){return t.gx===x&&t.gy===y})) spots.push({x:x,y:y});
      }
    }
    // Shuffle spots
    for (var i = spots.length - 1; i > 0; i--) { var j = Math.floor(Math.random()*(i+1)); var t=spots[i]; spots[i]=spots[j]; spots[j]=t; }

    // Pick tower types to counter player
    var typeKeys = Object.keys(G.towerTypes);
    for (var i = 0; i < Math.min(budget, spots.length); i++) {
      var s = spots[i];
      // Counter logic: lots of siege → venom/arcane, lots of speed → frost, lots of ranged → cannon
      var pick = 'arrow';
      if (G.aiMemory.siege > G.aiMemory.melee && Math.random() < 0.6) pick = 'venom';
      else if (G.aiMemory.speed > 3 && Math.random() < 0.5) pick = 'frost';
      else if (G.aiMemory.ranged > G.aiMemory.melee && Math.random() < 0.4) pick = 'arcane';
      else if (G.aiMemory.mega > 2 && Math.random() < 0.5) pick = 'cannon';
      else pick = typeKeys[Math.floor(Math.random() * typeKeys.length)];

      var tt = G.towerTypes[pick];
      G.towers.push({
        gx: s.x, gy: s.y,
        x: s.x * G.TS + G.TS/2, y: s.y * G.TS + G.TS/2,
        type: pick, hp: 60 + w * 10, maxHp: 60 + w * 10,
        dmg: Math.ceil(tt.dmg * (1 + w * 0.12)),
        rate: Math.max(10, tt.rate - Math.floor(w * 0.5)),
        range: tt.range + Math.floor(w * 0.5),
        color: tt.color, projSpd: tt.projSpd, projC: tt.projC,
        slow: tt.slow, dot: tt.dot || 0, splash: tt.splash || 0,
        manaburn: tt.manaburn || 0,
        cooldown: 0
      });
    }
  };

  // Place wave 1 towers
  G.placeTowers(1);

  // Wave completion tracking
  G.waveCreepsAlive = 0;
  G.waveComplete = false;
}
