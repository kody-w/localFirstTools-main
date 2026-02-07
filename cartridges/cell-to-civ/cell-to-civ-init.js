// ============================================================
// CELL TO CIVILIZATION - INIT
// Evolve from paramecium to spacefaring species
// ============================================================

if (mode === 'init') {
  // Procedural name generator
  G.syllables = ['za','ri','ko','mu','tha','vel','ix','on','ar','pe','lu','shi','en','da','fi','go','na','te','wo','by'];
  G.genName = function(n) {
    var s = '';
    for (var i = 0; i < (n||2); i++) s += G.syllables[Math.floor(Math.random() * G.syllables.length)];
    return s.charAt(0).toUpperCase() + s.slice(1);
  };

  // Core state
  G.era = 1;
  G.time = 0;        // billions of years elapsed
  G.speed = 1;
  G.paused = false;
  G.over = false;
  G.won = false;
  G.speciesName = G.genName(3);
  G.history = [];
  G.shake = 0;
  G.flash = 0;
  G.flashC = '#fff';
  G.transition = 0;  // era transition timer
  G.transMsg = '';
  G.particles = [];
  G.showStats = false;

  // Camera
  G.cam = { x: 128, y: 112, zoom: 1, tz: 1, tx: 128, ty: 112 };

  // ─── ERA 1: PRIMORDIAL ───
  G.cell = {
    x: 128, y: 112,
    vx: 0, vy: 0,
    energy: 50,
    size: 4,
    speed: 1.5,
    armor: 0,
    flagella: 0,
    toxin: 0,
    photo: 0
  };
  G.pop = 1;
  G.divCount = 0;
  G.mutations = [];
  G.mutChoice = null; // active mutation choice popup

  // Food particles
  G.food = [];
  for (var i = 0; i < 30; i++) {
    G.food.push({
      x: Math.random() * 256,
      y: Math.random() * 224,
      size: 1 + Math.random() * 2,
      vx: (Math.random() - 0.5) * 0.3,
      vy: (Math.random() - 0.5) * 0.3
    });
  }

  // Predators
  G.predators = [];
  for (var i = 0; i < 3; i++) {
    G.predators.push({
      x: Math.random() * 256,
      y: Math.random() * 224,
      vx: (Math.random() - 0.5) * 0.8,
      vy: (Math.random() - 0.5) * 0.8,
      size: 6,
      hp: 3
    });
  }

  // ─── ERA 2: ORGANISM ───
  G.creature = { x: 128, y: 112, vx: 0, vy: 0, stamina: 100, maxSt: 100 };
  G.organisms = []; // other creatures in ecosystem
  G.territory = [];

  // ─── ERA 3: TRIBAL ───
  G.units = [];
  G.buildings = [];
  G.res = { food: 50, wood: 0, stone: 0 };
  G.techs = [];
  G.allTechs = ['fire','tools','pottery','weapons','agriculture','writing','wheel'];
  G.enemies = [];
  G.selected = [];
  G.buildMenu = false;
  G.buildOpts = [
    { name: 'Hut', cost: { wood: 10 }, icon: 'H' },
    { name: 'Fire Pit', cost: { wood: 5, stone: 2 }, icon: 'F' },
    { name: 'Totem', cost: { stone: 8 }, icon: 'T' },
    { name: 'Wall', cost: { stone: 5 }, icon: 'W' }
  ];
  G.tribeName = G.genName(2) + ' Clan';

  // ─── ERA 4: CIVILIZATION ───
  G.cities = [];
  G.hexes = [];
  G.civRes = { food: 100, prod: 50, gold: 20, science: 0 };
  G.civTechs = [];
  G.allCivTechs = ['agriculture','writing','mathematics','engineering','philosophy','astronomy','rocketry'];
  G.civResearching = null;
  G.civResProgress = 0;
  G.aiCivs = [];
  G.diplomacy = {}; // civId -> 'neutral'|'trade'|'war'
  G.hexW = 16;
  G.hexH = 14;
  // Generate hex grid
  for (var hx = 0; hx < 16; hx++) {
    for (var hy = 0; hy < 16; hy++) {
      var r = Math.random();
      var terrain = r < 0.15 ? 'water' : r < 0.3 ? 'forest' : r < 0.4 ? 'mountain' : r < 0.5 ? 'desert' : 'plains';
      var hasRes = Math.random() < 0.15;
      G.hexes.push({
        hx: hx, hy: hy,
        terrain: terrain,
        resource: hasRes ? (Math.random() < 0.5 ? 'iron' : 'gems') : null,
        owner: null,
        building: null
      });
    }
  }

  // ─── ERA 5: STELLAR ───
  G.ship = { x: 128, y: 112, vx: 0, vy: 0, fuel: 100 };
  G.planets = [];
  G.stars = [];
  G.colonies = [];
  G.signalFound = false;
  // Generate star system
  for (var i = 0; i < 40; i++) {
    G.stars.push({ x: Math.random() * 256, y: Math.random() * 224, b: 0.3 + Math.random() * 0.7 });
  }
  var numPlanets = 4 + Math.floor(Math.random() * 5);
  for (var i = 0; i < numPlanets; i++) {
    var dist = 30 + i * 22 + Math.random() * 10;
    var angle = Math.random() * Math.PI * 2;
    var types = ['rocky','gas','ice','volcanic','ocean'];
    G.planets.push({
      dist: dist,
      angle: angle,
      speed: 0.002 / (1 + i * 0.3),
      type: types[Math.floor(Math.random() * types.length)],
      size: 3 + Math.floor(Math.random() * 5),
      name: G.genName(2) + (Math.random() < 0.5 ? ' Prime' : ' ' + (i+1)),
      colonized: false,
      compatible: 0, // set based on mutations later
      hasSignal: i === numPlanets - 1
    });
  }

  // Calculate planet compatibility from mutations
  G.planets.forEach(function(p) {
    var compat = 50;
    G.mutations.forEach(function(m) {
      if (m === 'armor' && p.type === 'rocky') compat += 15;
      if (m === 'photosynthesis' && p.type === 'ocean') compat += 20;
      if (m === 'toxin' && p.type === 'volcanic') compat += 15;
      if (m === 'flagella' && p.type === 'gas') compat += 10;
      if (m === 'size' && p.type === 'ice') compat += 10;
    });
    p.compatible = Math.min(100, compat);
  });

  // Mutation options pool
  G.mutPool = [
    { id: 'speed', name: '+Speed', desc: 'Faster movement', icon: '»' },
    { id: 'size', name: '+Size', desc: 'Larger cells', icon: '●' },
    { id: 'armor', name: 'Armor', desc: 'Resist damage', icon: '◆' },
    { id: 'flagella', name: 'Flagella', desc: 'Better turning', icon: '~' },
    { id: 'photosynthesis', name: 'Photo', desc: 'Passive energy', icon: '☀' },
    { id: 'toxin', name: 'Toxin', desc: 'Damage predators', icon: '!' }
  ];

  G.kcd = 0; // key cooldown
  G.selIdx = 0; // menu selection index

  // Log first history event
  G.history.push({ era: 1, time: 0, event: G.speciesName + ' emerges in the primordial soup' });
}
