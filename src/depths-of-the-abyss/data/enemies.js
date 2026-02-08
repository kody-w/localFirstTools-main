// enemies.js - Enemy, boss, and spawn table definitions for Depths of the Abyss
// Depends on: constants.js (ELEMENT), utils.js (Util)

// Enemy type definitions organized by area with varied behaviors and AI strategies
const ENEMY_TYPES = {
  // SUNKEN CRYPT (Floors 1-5) - Tutorial area enemies
  skeleton_warrior: {
    id: 'skeleton_warrior',
    name: 'Skeleton Warrior',
    type: 'undead_melee',
    hp: 40,
    damage: 8,
    speed: 60,
    behavior: 'patrol', // walks back and forth, chases on sight
    patrolRange: 150,
    aggroRange: 200,
    element: ELEMENT.PHYSICAL,
    xpReward: 15,
    lootChance: 0.3,
    attacks: [
      { name: 'Slash', damage: 8, cooldown: 1.0, range: 60 }
    ],
    resistances: { dark: 0.5, light: -0.5 },
    spriteData: { color: '#E5E5DC', size: 32, shape: 'humanoid' },
    description: 'Reanimated bones with basic combat strategy. Easy to defeat.'
  },

  zombie_shambler: {
    id: 'zombie_shambler',
    name: 'Zombie Shambler',
    type: 'undead_slow',
    hp: 60,
    damage: 12,
    speed: 30,
    behavior: 'chase', // always moves toward player, slow
    aggroRange: 250,
    element: ELEMENT.DARK,
    xpReward: 18,
    lootChance: 0.25,
    attacks: [
      { name: 'Bite', damage: 12, cooldown: 1.5, range: 50, effect: 'poison' }
    ],
    resistances: { poison: 1.0, fire: -0.3 },
    spriteData: { color: '#556B2F', size: 34, shape: 'humanoid' },
    description: 'Slow but tanky opponent. Poisonous bite attack.'
  },

  giant_rat: {
    id: 'giant_rat',
    name: 'Giant Rat',
    type: 'beast_swarm',
    hp: 25,
    damage: 6,
    speed: 90,
    behavior: 'swarm', // attacks in groups, flanks player
    aggroRange: 180,
    element: ELEMENT.PHYSICAL,
    xpReward: 10,
    lootChance: 0.2,
    attacks: [
      { name: 'Gnaw', damage: 6, cooldown: 0.7, range: 40 }
    ],
    resistances: {},
    spriteData: { color: '#8B4513', size: 24, shape: 'quadruped' },
    description: 'Fast and dangerous in groups. Low health but high speed.'
  },

  crypt_spider: {
    id: 'crypt_spider',
    name: 'Crypt Spider',
    type: 'beast_ambush',
    hp: 35,
    damage: 10,
    speed: 75,
    behavior: 'ambush', // hides on ceiling, drops on player
    aggroRange: 150,
    element: ELEMENT.POISON,
    xpReward: 20,
    lootChance: 0.4,
    attacks: [
      { name: 'Venom Bite', damage: 10, cooldown: 1.2, range: 50, effect: 'poison' },
      { name: 'Web Shot', damage: 0, cooldown: 3.0, range: 200, effect: 'slow' }
    ],
    resistances: { poison: 1.0 },
    spriteData: { color: '#2F4F4F', size: 28, shape: 'spider' },
    description: 'Ambush predator with web attacks to slow victims.'
  },

  ghost_wisp: {
    id: 'ghost_wisp',
    name: 'Ghost Wisp',
    type: 'spirit_ranged',
    hp: 30,
    damage: 15,
    speed: 50,
    behavior: 'ranged', // keeps distance, fires projectiles
    aggroRange: 300,
    attackRange: 250,
    element: ELEMENT.ARCANE,
    xpReward: 25,
    lootChance: 0.35,
    attacks: [
      { name: 'Spirit Bolt', damage: 15, cooldown: 1.5, range: 250, projectile: true }
    ],
    resistances: { physical: 0.5, arcane: 0.5 },
    spriteData: { color: '#E0FFFF', size: 26, shape: 'wisp', glow: true },
    description: 'Ethereal ranged opponent. Resistant to physical damage.'
  },

  // FUNGAL CAVERNS (Floors 6-10) - Medium difficulty
  mushroom_golem: {
    id: 'mushroom_golem',
    name: 'Mushroom Golem',
    type: 'construct_tank',
    hp: 120,
    damage: 18,
    speed: 40,
    behavior: 'guard', // defends area, slow but tough
    aggroRange: 200,
    element: ELEMENT.NATURE,
    xpReward: 40,
    lootChance: 0.5,
    attacks: [
      { name: 'Slam', damage: 18, cooldown: 2.0, range: 70, effect: 'stun' },
      { name: 'Spore Cloud', damage: 5, cooldown: 5.0, range: 150, effect: 'poison', aoe: true }
    ],
    resistances: { physical: 0.3, poison: 1.0, fire: -0.5 },
    spriteData: { color: '#8B4789', size: 48, shape: 'golem' },
    description: 'Tanky guardian that releases toxic spores. Weak to fire.'
  },

  spore_cloud: {
    id: 'spore_cloud',
    name: 'Spore Cloud',
    type: 'elemental_hazard',
    hp: 50,
    damage: 8,
    speed: 20,
    behavior: 'patrol',
    patrolRange: 100,
    aggroRange: 150,
    element: ELEMENT.POISON,
    xpReward: 15,
    lootChance: 0.3,
    attacks: [
      { name: 'Toxic Aura', damage: 8, cooldown: 0.5, range: 80, continuous: true }
    ],
    resistances: { physical: 0.8, poison: 1.0 },
    spriteData: { color: '#9370DB', size: 40, shape: 'cloud', opacity: 0.7 },
    description: 'Floating hazard with continuous poison damage aura.'
  },

  cave_bat_swarm: {
    id: 'cave_bat_swarm',
    name: 'Cave Bat Swarm',
    type: 'beast_flying',
    hp: 40,
    damage: 12,
    speed: 120,
    behavior: 'swarm',
    aggroRange: 250,
    element: ELEMENT.PHYSICAL,
    xpReward: 22,
    lootChance: 0.25,
    attacks: [
      { name: 'Dive Attack', damage: 12, cooldown: 0.8, range: 60 }
    ],
    resistances: {},
    spriteData: { color: '#4B0082', size: 20, shape: 'bat', flying: true },
    description: 'Fast flying enemies that dive-bomb in swarms.'
  },

  fungal_zombie: {
    id: 'fungal_zombie',
    name: 'Fungal Zombie',
    type: 'undead_infected',
    hp: 80,
    damage: 16,
    speed: 45,
    behavior: 'chase',
    aggroRange: 200,
    element: ELEMENT.DARK,
    xpReward: 30,
    lootChance: 0.4,
    attacks: [
      { name: 'Infected Bite', damage: 16, cooldown: 1.3, range: 55, effect: 'poison' },
      { name: 'Explode', damage: 30, cooldown: 0, range: 100, onDeath: true, aoe: true }
    ],
    resistances: { poison: 1.0, dark: 0.5 },
    spriteData: { color: '#556B2F', size: 36, shape: 'humanoid', infected: true },
    description: 'Infected undead that explodes on death. Keep distance!'
  },

  toxic_slime: {
    id: 'toxic_slime',
    name: 'Toxic Slime',
    type: 'ooze_split',
    hp: 60,
    damage: 10,
    speed: 35,
    behavior: 'chase',
    aggroRange: 180,
    element: ELEMENT.POISON,
    xpReward: 25,
    lootChance: 0.35,
    attacks: [
      { name: 'Acid Touch', damage: 10, cooldown: 1.0, range: 50, effect: 'poison' }
    ],
    resistances: { physical: 0.5, poison: 1.0 },
    onDeathEffect: 'split', // splits into 2 smaller slimes
    spriteData: { color: '#32CD32', size: 32, shape: 'blob' },
    description: 'Ooze that splits into smaller copies when killed.'
  },

  // LAVA DEPTHS (Floors 11-15) - High difficulty
  fire_imp: {
    id: 'fire_imp',
    name: 'Fire Imp',
    type: 'demon_ranged',
    hp: 70,
    damage: 22,
    speed: 85,
    behavior: 'ranged',
    aggroRange: 300,
    attackRange: 280,
    element: ELEMENT.FIRE,
    xpReward: 45,
    lootChance: 0.45,
    attacks: [
      { name: 'Fireball', damage: 22, cooldown: 1.2, range: 280, projectile: true, element: 'fire' },
      { name: 'Flame Dash', damage: 15, cooldown: 3.0, range: 150, dash: true }
    ],
    resistances: { fire: 1.0, ice: -0.8 },
    spriteData: { color: '#FF4500', size: 30, shape: 'imp', glow: true },
    description: 'Agile demon that hurls fireballs and dashes through flames.'
  },

  lava_elemental: {
    id: 'lava_elemental',
    name: 'Lava Elemental',
    type: 'elemental_tank',
    hp: 150,
    damage: 28,
    speed: 30,
    behavior: 'guard',
    aggroRange: 220,
    element: ELEMENT.FIRE,
    xpReward: 60,
    lootChance: 0.6,
    attacks: [
      { name: 'Molten Strike', damage: 28, cooldown: 1.8, range: 80 },
      { name: 'Lava Pool', damage: 15, cooldown: 4.0, range: 200, aoe: true, duration: 5 }
    ],
    resistances: { fire: 1.0, physical: 0.4, ice: -1.0 },
    spriteData: { color: '#FF6347', size: 52, shape: 'elemental', glow: true },
    description: 'Living lava with devastating area attacks. Extreme fire resistance.'
  },

  magma_wyrm: {
    id: 'magma_wyrm',
    name: 'Magma Wyrm',
    type: 'beast_elite',
    hp: 180,
    damage: 32,
    speed: 55,
    behavior: 'chase',
    aggroRange: 250,
    element: ELEMENT.FIRE,
    xpReward: 70,
    lootChance: 0.65,
    attacks: [
      { name: 'Bite', damage: 32, cooldown: 1.5, range: 90 },
      { name: 'Fire Breath', damage: 40, cooldown: 4.0, range: 200, cone: 60, aoe: true }
    ],
    resistances: { fire: 1.0, physical: 0.3 },
    spriteData: { color: '#DC143C', size: 60, shape: 'wyrm' },
    description: 'Elite serpent with cone fire breath. High health and damage.'
  },

  ember_knight: {
    id: 'ember_knight',
    name: 'Ember Knight',
    type: 'undead_armored',
    hp: 140,
    damage: 26,
    speed: 65,
    behavior: 'patrol',
    patrolRange: 180,
    aggroRange: 230,
    element: ELEMENT.FIRE,
    xpReward: 55,
    lootChance: 0.55,
    attacks: [
      { name: 'Flaming Slash', damage: 26, cooldown: 1.3, range: 85, element: 'fire' },
      { name: 'Shield Bash', damage: 18, cooldown: 2.5, range: 70, effect: 'stun' }
    ],
    resistances: { physical: 0.4, fire: 0.8 },
    spriteData: { color: '#B22222', size: 42, shape: 'knight', armored: true },
    description: 'Armored warrior wreathed in flames. Can stun with shield.'
  },

  ash_phantom: {
    id: 'ash_phantom',
    name: 'Ash Phantom',
    type: 'spirit_teleport',
    hp: 90,
    damage: 24,
    speed: 70,
    behavior: 'ambush',
    aggroRange: 280,
    element: ELEMENT.FIRE,
    xpReward: 50,
    lootChance: 0.5,
    attacks: [
      { name: 'Phase Strike', damage: 24, cooldown: 1.6, range: 100, teleport: true },
      { name: 'Ember Cloud', damage: 12, cooldown: 3.5, range: 150, aoe: true }
    ],
    resistances: { physical: 0.6, fire: 0.8 },
    spriteData: { color: '#CD853F', size: 38, shape: 'phantom', translucent: true },
    description: 'Teleporting spirit that phases in and out of reality.'
  },

  // FROZEN ABYSS (Floors 16-20) - Very high difficulty
  ice_wraith: {
    id: 'ice_wraith',
    name: 'Ice Wraith',
    type: 'spirit_freeze',
    hp: 100,
    damage: 30,
    speed: 80,
    behavior: 'ranged',
    aggroRange: 300,
    attackRange: 270,
    element: ELEMENT.ICE,
    xpReward: 65,
    lootChance: 0.55,
    attacks: [
      { name: 'Ice Shard', damage: 30, cooldown: 1.1, range: 270, projectile: true, effect: 'slow' },
      { name: 'Frost Nova', damage: 20, cooldown: 4.0, range: 180, aoe: true, effect: 'freeze' }
    ],
    resistances: { ice: 1.0, fire: -0.9 },
    spriteData: { color: '#87CEEB', size: 34, shape: 'wraith', glow: true },
    description: 'Frozen spirit that slows and freezes opponents.'
  },

  frost_golem: {
    id: 'frost_golem',
    name: 'Frost Golem',
    type: 'construct_colossus',
    hp: 220,
    damage: 35,
    speed: 35,
    behavior: 'guard',
    aggroRange: 200,
    element: ELEMENT.ICE,
    xpReward: 80,
    lootChance: 0.7,
    attacks: [
      { name: 'Frozen Fist', damage: 35, cooldown: 2.0, range: 90, effect: 'slow' },
      { name: 'Blizzard', damage: 25, cooldown: 6.0, range: 250, aoe: true, duration: 6 }
    ],
    resistances: { ice: 1.0, physical: 0.5, fire: -0.8 },
    spriteData: { color: '#B0E0E6', size: 58, shape: 'golem', icy: true },
    description: 'Massive ice construct. Creates blizzard zones.'
  },

  crystal_spider: {
    id: 'crystal_spider',
    name: 'Crystal Spider',
    type: 'beast_ambush_elite',
    hp: 110,
    damage: 28,
    speed: 90,
    behavior: 'ambush',
    aggroRange: 170,
    element: ELEMENT.ICE,
    xpReward: 70,
    lootChance: 0.65,
    attacks: [
      { name: 'Crystal Bite', damage: 28, cooldown: 1.0, range: 55, critical: 0.3 },
      { name: 'Ice Web', damage: 10, cooldown: 2.5, range: 220, effect: 'freeze', projectile: true }
    ],
    resistances: { ice: 0.8, physical: 0.3 },
    spriteData: { color: '#ADD8E6', size: 32, shape: 'spider', crystalline: true },
    description: 'Crystallized spider with high critical hit chance.'
  },

  frozen_revenant: {
    id: 'frozen_revenant',
    name: 'Frozen Revenant',
    type: 'undead_boss_mini',
    hp: 200,
    damage: 40,
    speed: 60,
    behavior: 'chase',
    aggroRange: 280,
    element: ELEMENT.ICE,
    xpReward: 90,
    lootChance: 0.75,
    attacks: [
      { name: 'Frost Blade', damage: 40, cooldown: 1.4, range: 95, combo: 3 },
      { name: 'Ice Prison', damage: 0, cooldown: 8.0, range: 150, effect: 'freeze', duration: 3 },
      { name: 'Frozen Aura', damage: 15, cooldown: 0.5, range: 120, continuous: true }
    ],
    resistances: { ice: 1.0, dark: 0.5, fire: -1.0 },
    spriteData: { color: '#4682B4', size: 46, shape: 'revenant', frozen: true },
    description: 'Powerful undead with combo attacks and freeze abilities. Mini-boss tier.'
  },

  blizzard_wolf: {
    id: 'blizzard_wolf',
    name: 'Blizzard Wolf',
    type: 'beast_pack',
    hp: 95,
    damage: 32,
    speed: 110,
    behavior: 'swarm',
    aggroRange: 260,
    element: ELEMENT.ICE,
    xpReward: 60,
    lootChance: 0.5,
    attacks: [
      { name: 'Frozen Bite', damage: 32, cooldown: 0.9, range: 65, effect: 'slow' },
      { name: 'Howl', damage: 0, cooldown: 10.0, range: 400, effect: 'summon_pack' }
    ],
    resistances: { ice: 0.9 },
    spriteData: { color: '#F0F8FF', size: 36, shape: 'wolf' },
    description: 'Pack hunter that summons allies with its howl.'
  },

  // THE VOID (Floors 21-25) - Maximum difficulty, endgame
  void_walker: {
    id: 'void_walker',
    name: 'Void Walker',
    type: 'eldritch_assassin',
    hp: 140,
    damage: 45,
    speed: 100,
    behavior: 'ambush',
    aggroRange: 320,
    element: ELEMENT.VOID,
    xpReward: 100,
    lootChance: 0.7,
    attacks: [
      { name: 'Void Strike', damage: 45, cooldown: 1.2, range: 80, critical: 0.4 },
      { name: 'Teleport Strike', damage: 60, cooldown: 3.0, range: 300, teleport: true },
      { name: 'Reality Tear', damage: 35, cooldown: 5.0, range: 200, projectile: true }
    ],
    resistances: { physical: 0.4, arcane: 0.5, void: 1.0 },
    spriteData: { color: '#191970', size: 40, shape: 'humanoid', voidform: true },
    description: 'Assassin from beyond. Teleports and deals massive burst damage.'
  },

  shadow_assassin: {
    id: 'shadow_assassin',
    name: 'Shadow Assassin',
    type: 'eldritch_stealth',
    hp: 120,
    damage: 50,
    speed: 115,
    behavior: 'ambush',
    aggroRange: 100,
    element: ELEMENT.DARK,
    xpReward: 110,
    lootChance: 0.75,
    attacks: [
      { name: 'Backstab', damage: 100, cooldown: 2.0, range: 60, backstabMultiplier: 2.0 },
      { name: 'Shadow Step', damage: 35, cooldown: 1.5, range: 200, teleport: true },
      { name: 'Vanish', damage: 0, cooldown: 8.0, range: 0, effect: 'stealth', duration: 4 }
    ],
    resistances: { physical: 0.3, dark: 0.8 },
    spriteData: { color: '#2F4F4F', size: 38, shape: 'rogue', shadowy: true },
    description: 'Master of stealth. Devastating backstab attacks from invisibility.'
  },

  eldritch_horror: {
    id: 'eldritch_horror',
    name: 'Eldritch Horror',
    type: 'eldritch_aberration',
    hp: 250,
    damage: 55,
    speed: 50,
    behavior: 'chase',
    aggroRange: 350,
    element: ELEMENT.VOID,
    xpReward: 130,
    lootChance: 0.8,
    attacks: [
      { name: 'Tentacle Lash', damage: 55, cooldown: 1.6, range: 140, multi: 3 },
      { name: 'Madness Aura', damage: 20, cooldown: 0.5, range: 180, continuous: true, effect: 'confuse' },
      { name: 'Void Pulse', damage: 70, cooldown: 6.0, range: 300, aoe: true }
    ],
    resistances: { physical: 0.5, arcane: 0.6, void: 1.0 },
    spriteData: { color: '#4B0082', size: 64, shape: 'horror', tentacles: true },
    description: 'Massive aberration with multiple attacks and sanity-draining aura.'
  },

  abyss_watcher: {
    id: 'abyss_watcher',
    name: 'Abyss Watcher',
    type: 'eldritch_sentinel',
    hp: 200,
    damage: 48,
    speed: 75,
    behavior: 'patrol',
    patrolRange: 250,
    aggroRange: 300,
    element: ELEMENT.VOID,
    xpReward: 120,
    lootChance: 0.75,
    attacks: [
      { name: 'Void Blade', damage: 48, cooldown: 1.3, range: 100, combo: 4 },
      { name: 'Eye Beam', damage: 60, cooldown: 4.0, range: 400, beam: true },
      { name: 'Summon Minions', damage: 0, cooldown: 12.0, range: 0, effect: 'summon_void_spawn' }
    ],
    resistances: { physical: 0.4, all: 0.3 },
    spriteData: { color: '#000080', size: 50, shape: 'sentinel', eyes: true },
    description: 'Guardian of the deep. Fires devastating eye beams and summons minions.'
  },

  null_entity: {
    id: 'null_entity',
    name: 'Null Entity',
    type: 'eldritch_void',
    hp: 180,
    damage: 52,
    speed: 90,
    behavior: 'chase',
    aggroRange: 330,
    element: ELEMENT.VOID,
    xpReward: 140,
    lootChance: 0.85,
    attacks: [
      { name: 'Existence Drain', damage: 52, cooldown: 1.4, range: 90, lifesteal: 0.5 },
      { name: 'Null Zone', damage: 30, cooldown: 5.0, range: 220, aoe: true, effect: 'silence', duration: 4 },
      { name: 'Phase Shift', damage: 0, cooldown: 3.0, range: 0, effect: 'invulnerable', duration: 2 }
    ],
    resistances: { all: 0.5 },
    spriteData: { color: '#0D0D0D', size: 44, shape: 'entity', distorted: true },
    description: 'Being of pure void. Drains life and becomes invulnerable periodically.'
  }
};

// Boss definitions with multi-phase mechanics and dialogue
const BOSS_DEFS = {
  grave_warden: {
    id: 'grave_warden',
    name: 'The Grave Warden',
    type: 'boss_undead',
    floor: 5,
    baseHp: 500,
    element: ELEMENT.DARK,
    xpReward: 300,
    phases: [
      {
        hp_threshold: 1.0,
        behavior: 'patrol',
        speed: 65,
        attacks: [
          { name: 'Heavy Slash', damage: 35, cooldown: 1.8, range: 110 },
          { name: 'Shield Block', damage: 0, cooldown: 4.0, effect: 'defense_up', duration: 3 }
        ]
      },
      {
        hp_threshold: 0.6,
        behavior: 'chase',
        speed: 75,
        attacks: [
          { name: 'Skeleton Summon', damage: 0, cooldown: 8.0, effect: 'summon_skeletons', count: 3 },
          { name: 'Spinning Slash', damage: 45, cooldown: 2.5, range: 140, aoe: true }
        ],
        special_moves: ['summon_reinforcements']
      },
      {
        hp_threshold: 0.25,
        behavior: 'chase',
        speed: 85,
        attacks: [
          { name: 'Ground Slam', damage: 60, cooldown: 3.0, range: 200, aoe: true, effect: 'stun' },
          { name: 'Death Charge', damage: 70, cooldown: 5.0, range: 300, dash: true },
          { name: 'Grave Aura', damage: 15, cooldown: 0.5, range: 150, continuous: true }
        ],
        special_moves: ['enrage']
      }
    ],
    dialogue: {
      intro: "You dare disturb the eternal rest of these halls?",
      phase_change: ["The dead rise at my command!", "You cannot stop the inevitable!"],
      death: "The crypt... crumbles..."
    },
    lootTable: 'boss_loot',
    spriteData: { color: '#4A4A4A', size: 80, shape: 'knight', boss: true }
  },

  mycelium_king: {
    id: 'mycelium_king',
    name: 'Mycelium King',
    type: 'boss_fungal',
    floor: 10,
    baseHp: 800,
    element: ELEMENT.NATURE,
    xpReward: 500,
    phases: [
      {
        hp_threshold: 1.0,
        behavior: 'guard',
        speed: 50,
        attacks: [
          { name: 'Spore Spray', damage: 30, cooldown: 2.0, range: 180, cone: 90, effect: 'poison' },
          { name: 'Root Grasp', damage: 25, cooldown: 4.0, range: 200, effect: 'slow', duration: 3 }
        ]
      },
      {
        hp_threshold: 0.5,
        behavior: 'chase',
        speed: 60,
        attacks: [
          { name: 'Split Form', damage: 0, cooldown: 1.0, effect: 'create_clone', count: 2 },
          { name: 'Mushroom Cage', damage: 40, cooldown: 6.0, range: 150, effect: 'trap', duration: 4 }
        ],
        special_moves: ['split_into_copies']
      },
      {
        hp_threshold: 0.2,
        behavior: 'chase',
        speed: 70,
        attacks: [
          { name: 'Fungal Explosion', damage: 80, cooldown: 7.0, range: 300, aoe: true },
          { name: 'Toxic Bloom', damage: 50, cooldown: 3.0, range: 200, aoe: true, effect: 'poison' },
          { name: 'Regeneration', damage: 0, cooldown: 10.0, effect: 'heal', value: 100 }
        ],
        special_moves: ['mushroom_cage_ultimate']
      }
    ],
    dialogue: {
      intro: "The network spans forever. You are but a single cell.",
      phase_change: ["I am legion. I am everywhere.", "The spores will consume all!"],
      death: "The mycelium... never... truly... dies..."
    },
    lootTable: 'boss_loot',
    spriteData: { color: '#8B4789', size: 90, shape: 'fungal_mass', boss: true }
  },

  infernal_colossus: {
    id: 'infernal_colossus',
    name: 'Infernal Colossus',
    type: 'boss_demon',
    floor: 15,
    baseHp: 1200,
    element: ELEMENT.FIRE,
    xpReward: 750,
    phases: [
      {
        hp_threshold: 1.0,
        behavior: 'guard',
        speed: 45,
        attacks: [
          { name: 'Fire Breath', damage: 50, cooldown: 3.0, range: 250, cone: 75, element: 'fire' },
          { name: 'Molten Fist', damage: 60, cooldown: 2.0, range: 120 }
        ]
      },
      {
        hp_threshold: 0.65,
        behavior: 'chase',
        speed: 55,
        attacks: [
          { name: 'Meteor Rain', damage: 40, cooldown: 6.0, range: 400, aoe: true, multi: 8 },
          { name: 'Flame Wave', damage: 55, cooldown: 4.0, range: 300, wave: true }
        ],
        special_moves: ['meteor_bombardment']
      },
      {
        hp_threshold: 0.3,
        behavior: 'chase',
        speed: 65,
        attacks: [
          { name: 'Lava Conversion', damage: 30, cooldown: 1.0, range: 500, effect: 'floor_lava', continuous: true },
          { name: 'Inferno', damage: 100, cooldown: 8.0, range: 350, aoe: true },
          { name: 'Magma Eruption', damage: 80, cooldown: 5.0, range: 200, aoe: true, multi: 4 }
        ],
        special_moves: ['floor_becomes_lava']
      }
    ],
    dialogue: {
      intro: "Burn. Everything burns.",
      phase_change: ["The earth itself shall melt!", "WITNESS TRUE INFERNO!"],
      death: "The flames... dim... but never... extinguish..."
    },
    lootTable: 'boss_loot',
    spriteData: { color: '#FF4500', size: 100, shape: 'colossus', boss: true, flames: true }
  },

  glacial_sovereign: {
    id: 'glacial_sovereign',
    name: 'Glacial Sovereign',
    type: 'boss_ice',
    floor: 20,
    baseHp: 1500,
    element: ELEMENT.ICE,
    xpReward: 1000,
    phases: [
      {
        hp_threshold: 1.0,
        behavior: 'ranged',
        speed: 60,
        attacks: [
          { name: 'Ice Lance Barrage', damage: 45, cooldown: 1.5, range: 350, projectile: true, multi: 3 },
          { name: 'Frost Shield', damage: 0, cooldown: 6.0, effect: 'shield', value: 200 }
        ]
      },
      {
        hp_threshold: 0.6,
        behavior: 'chase',
        speed: 70,
        attacks: [
          { name: 'Time Freeze', damage: 0, cooldown: 12.0, range: 500, effect: 'freeze_time', duration: 4 },
          { name: 'Glacial Spike', damage: 70, cooldown: 3.0, range: 300, projectile: true, pierce: true },
          { name: 'Ice Prison', damage: 0, cooldown: 8.0, range: 180, effect: 'freeze', duration: 5 }
        ],
        special_moves: ['time_freeze']
      },
      {
        hp_threshold: 0.25,
        behavior: 'chase',
        speed: 80,
        attacks: [
          { name: 'Eternal Blizzard', damage: 35, cooldown: 1.0, range: 600, aoe: true, continuous: true },
          { name: 'Absolute Zero', damage: 150, cooldown: 10.0, range: 250, aoe: true, effect: 'freeze' },
          { name: 'Ice Clone', damage: 0, cooldown: 15.0, effect: 'summon_ice_clone' }
        ],
        special_moves: ['blizzard_phase']
      }
    ],
    dialogue: {
      intro: "All will be still. All will be frozen. Forever.",
      phase_change: ["Time itself bows to winter's will.", "Witness eternity in ice!"],
      death: "The thaw... begins... at last..."
    },
    lootTable: 'boss_loot',
    spriteData: { color: '#87CEEB', size: 95, shape: 'sovereign', boss: true, crowned: true }
  },

  abyss_incarnate: {
    id: 'abyss_incarnate',
    name: 'The Abyss Incarnate',
    type: 'boss_final',
    floor: 25,
    baseHp: 2500,
    element: ELEMENT.VOID,
    xpReward: 2000,
    phases: [
      {
        hp_threshold: 1.0,
        behavior: 'chase',
        speed: 75,
        attacks: [
          { name: 'Elemental Barrage', damage: 50, cooldown: 2.0, range: 300, projectile: true, element: 'all' },
          { name: 'Void Slash', damage: 65, cooldown: 1.5, range: 130, combo: 5 },
          { name: 'Gravity Well', damage: 40, cooldown: 5.0, range: 250, aoe: true, effect: 'pull' }
        ]
      },
      {
        hp_threshold: 0.75,
        behavior: 'chase',
        speed: 85,
        attacks: [
          { name: 'Summon Champions', damage: 0, cooldown: 20.0, effect: 'summon_mini_bosses', count: 2 },
          { name: 'Reality Fracture', damage: 70, cooldown: 4.0, range: 350, aoe: true },
          { name: 'Void Storm', damage: 45, cooldown: 1.0, range: 400, continuous: true }
        ],
        special_moves: ['summon_previous_bosses']
      },
      {
        hp_threshold: 0.5,
        behavior: 'chase',
        speed: 95,
        attacks: [
          { name: 'Mirror Strike', damage: 80, cooldown: 2.0, range: 150, copies_player_ability: true },
          { name: 'Abyss Gaze', damage: 60, cooldown: 3.0, range: 500, beam: true },
          { name: 'Dimensional Rift', damage: 90, cooldown: 6.0, range: 300, aoe: true, effect: 'teleport_random' }
        ],
        special_moves: ['copies_player_abilities']
      },
      {
        hp_threshold: 0.2,
        behavior: 'chase',
        speed: 110,
        attacks: [
          { name: 'True Form Unleashed', damage: 100, cooldown: 1.2, range: 200, multi: 4 },
          { name: 'Oblivion Wave', damage: 120, cooldown: 7.0, range: 600, aoe: true, wave: true },
          { name: 'Consume Reality', damage: 80, cooldown: 0.8, range: 180, lifesteal: 0.8 },
          { name: 'End of All', damage: 200, cooldown: 15.0, range: 500, aoe: true, ultimate: true }
        ],
        special_moves: ['true_form', 'world_ending_attack']
      }
    ],
    dialogue: {
      intro: "I am the void between stars. The silence after the scream. The end of all things.",
      phase_change: [
        "You face not a creature, but concept itself.",
        "I have worn the faces of gods. You show me yours.",
        "WITNESS THE ABYSS!"
      ],
      death: "Perhaps... you have... earned... victory..."
    },
    lootTable: 'boss_loot',
    finalBoss: true,
    spriteData: { color: '#000000', size: 120, shape: 'eldritch_god', boss: true, phases: 4 }
  }
};

// Spawn tables for floor-based enemy generation with difficulty scaling
const SPAWN_TABLES = {
  // Returns weighted enemy list for given floor and difficulty
  getSpawnTable(floor, difficulty = 'medium') {
    const difficultyMults = { easy: 0.7, medium: 1.0, hard: 1.4, elite: 1.8 };
    const mult = difficultyMults[difficulty] || 1.0;

    let enemies = [];

    // Sunken Crypt (1-5)
    if (floor <= 5) {
      enemies = [
        { id: 'skeleton_warrior', weight: 35, hpMult: mult, damageMult: mult },
        { id: 'zombie_shambler', weight: 25, hpMult: mult, damageMult: mult },
        { id: 'giant_rat', weight: 30, hpMult: mult, damageMult: mult },
        { id: 'crypt_spider', weight: 15, hpMult: mult, damageMult: mult },
        { id: 'ghost_wisp', weight: 10, hpMult: mult, damageMult: mult }
      ];
    }
    // Fungal Caverns (6-10)
    else if (floor <= 10) {
      enemies = [
        { id: 'mushroom_golem', weight: 20, hpMult: mult, damageMult: mult },
        { id: 'spore_cloud', weight: 25, hpMult: mult, damageMult: mult },
        { id: 'cave_bat_swarm', weight: 30, hpMult: mult, damageMult: mult },
        { id: 'fungal_zombie', weight: 20, hpMult: mult, damageMult: mult },
        { id: 'toxic_slime', weight: 25, hpMult: mult, damageMult: mult },
        { id: 'skeleton_warrior', weight: 10, hpMult: mult * 1.2, damageMult: mult * 1.2 }
      ];
    }
    // Lava Depths (11-15)
    else if (floor <= 15) {
      enemies = [
        { id: 'fire_imp', weight: 30, hpMult: mult, damageMult: mult },
        { id: 'lava_elemental', weight: 20, hpMult: mult, damageMult: mult },
        { id: 'magma_wyrm', weight: 15, hpMult: mult, damageMult: mult },
        { id: 'ember_knight', weight: 25, hpMult: mult, damageMult: mult },
        { id: 'ash_phantom', weight: 20, hpMult: mult, damageMult: mult }
      ];
    }
    // Frozen Abyss (16-20)
    else if (floor <= 20) {
      enemies = [
        { id: 'ice_wraith', weight: 25, hpMult: mult, damageMult: mult },
        { id: 'frost_golem', weight: 20, hpMult: mult, damageMult: mult },
        { id: 'crystal_spider', weight: 20, hpMult: mult, damageMult: mult },
        { id: 'frozen_revenant', weight: 15, hpMult: mult, damageMult: mult },
        { id: 'blizzard_wolf', weight: 25, hpMult: mult, damageMult: mult }
      ];
    }
    // The Void (21-25)
    else {
      enemies = [
        { id: 'void_walker', weight: 25, hpMult: mult, damageMult: mult },
        { id: 'shadow_assassin', weight: 20, hpMult: mult, damageMult: mult },
        { id: 'eldritch_horror', weight: 15, hpMult: mult, damageMult: mult },
        { id: 'abyss_watcher', weight: 20, hpMult: mult, damageMult: mult },
        { id: 'null_entity', weight: 20, hpMult: mult, damageMult: mult }
      ];
    }

    // Add elite variant chance (small probability, 1.5x stats, better loot)
    if (difficulty !== 'elite' && Math.random() < 0.1) {
      enemies.forEach(e => {
        if (Math.random() < 0.15) {
          e.isElite = true;
          e.hpMult *= 1.5;
          e.damageMult *= 1.5;
          e.lootBoost = 1;
        }
      });
    }

    return enemies;
  },

  // Get boss for specific floor
  getBoss(floor) {
    if (floor === 5) return 'grave_warden';
    if (floor === 10) return 'mycelium_king';
    if (floor === 15) return 'infernal_colossus';
    if (floor === 20) return 'glacial_sovereign';
    if (floor === 25) return 'abyss_incarnate';
    return null;
  }
};
