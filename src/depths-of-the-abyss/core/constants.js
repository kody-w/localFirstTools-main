'use strict';

// =============================================================================
// CONSTANTS.JS - Master game state and constants
// =============================================================================

// Tile and rendering constants
const TILE_SIZE = 32;
const CANVAS_BG = '#0a0a12';
const VIEW_TILES_X = 25;
const VIEW_TILES_Y = 19;

// Game state enum
const STATE = {
    LOADING: 'loading',
    TITLE: 'title',
    PLAYING: 'playing',
    PAUSED: 'paused',
    INVENTORY: 'inventory',
    SKILL_TREE: 'skill_tree',
    CRAFTING: 'crafting',
    DIALOGUE: 'dialogue',
    DEATH: 'death',
    GAME_OVER: 'game_over',
    VICTORY: 'victory',
    TRANSITION: 'transition',
    BOSS_INTRO: 'boss_intro'
};

// Difficulty levels
const DIFFICULTY = { EASY: 'easy', NORMAL: 'normal', HARD: 'hard' };

// Difficulty scaling multipliers
const DIFFICULTY_MULTIPLIERS = {
    easy: { enemyHp: 0.7, enemyDmg: 0.8, xpGain: 1.2, dropRate: 1.3 },
    normal: { enemyHp: 1.0, enemyDmg: 1.0, xpGain: 1.0, dropRate: 1.0 },
    hard: { enemyHp: 1.5, enemyDmg: 1.4, xpGain: 0.8, dropRate: 0.85 }
};

// Damage types / elements
const ELEMENT = { PHYSICAL: 0, FIRE: 1, ICE: 2, LIGHTNING: 3, POISON: 4, DARK: 5, ARCANE: 6, NATURE: 7, VOID: 8 };

const ELEMENT_NAMES = ['Physical', 'Fire', 'Ice', 'Lightning', 'Poison', 'Dark', 'Arcane', 'Nature', 'Void'];
const ELEMENT_COLORS = ['#ccc', '#f44', '#4cf', '#ff4', '#8c4', '#a4f', '#94f', '#6a6', '#111'];

// Item rarities
const RARITY = { COMMON: 0, UNCOMMON: 1, RARE: 2, EPIC: 3, LEGENDARY: 4 };
const RARITY_COLORS = { 0: '#888', 1: '#4a4', 2: '#48f', 3: '#a4f', 4: '#fa0' };
const RARITY_NAMES = ['Common', 'Uncommon', 'Rare', 'Epic', 'Legendary'];

// Direction enum
const DIR = { UP: 0, RIGHT: 1, DOWN: 2, LEFT: 3 };
const DIR_DX = [0, 1, 0, -1];
const DIR_DY = [-1, 0, 1, 0];

// Player defaults
const PLAYER_DEFAULTS = {
    maxHp: 100,
    maxMana: 50,
    maxStamina: 80,
    speed: 3.5,
    attackDmg: 10,
    defense: 2,
    critChance: 0.05,
    critMultiplier: 2.0,
    dodgeStamina: 25,
    dodgeDuration: 0.3,
    dodgeCooldown: 0.5,
    parryWindow: 0.15,
    parryStamina: 15,
    iframeDuration: 0.5,
    xpToLevel: level => 50 + level * 30,
    hpRegen: 0.1,
    manaRegen: 1.0,
    staminaRegen: 20
};

// Stat growth per level
const STAT_GROWTH = {
    hp: 10,
    mana: 5,
    stamina: 5,
    attack: 2,
    defense: 1
};

// Damage formula: (attackDmg * multiplier) - (defense * 0.5)
function calcDamage(attackDmg, defense, multiplier = 1.0) {
    const raw = attackDmg * multiplier;
    const reduced = Math.max(1, raw - (defense * 0.5));
    return Math.floor(reduced);
}

// XP curve
function getXPForLevel(level) {
    return 50 + level * 30 + Math.floor(level * level * 5);
}

// Enemy stat scaling per floor
function getEnemyStats(baseHp, baseDmg, floor, difficulty) {
    const floorScale = 1 + (floor - 1) * 0.15;
    const diffMult = DIFFICULTY_MULTIPLIERS[difficulty];
    return {
        hp: Math.floor(baseHp * floorScale * diffMult.enemyHp),
        dmg: Math.floor(baseDmg * floorScale * diffMult.enemyDmg)
    };
}

// Spawn rate tables per floor range
const SPAWN_RATES = [
    { floors: [1, 5], enemyCount: [3, 6], eliteChance: 0.1, bossFloor: 5 },
    { floors: [6, 10], enemyCount: [4, 8], eliteChance: 0.15, bossFloor: 10 },
    { floors: [11, 15], enemyCount: [5, 10], eliteChance: 0.2, bossFloor: 15 },
    { floors: [16, 20], enemyCount: [6, 12], eliteChance: 0.25, bossFloor: 20 },
    { floors: [21, 25], enemyCount: [8, 15], eliteChance: 0.3, bossFloor: 25 }
];

function getSpawnRate(floor) {
    for (const rate of SPAWN_RATES) {
        if (floor >= rate.floors[0] && floor <= rate.floors[1]) return rate;
    }
    return SPAWN_RATES[SPAWN_RATES.length - 1];
}

// Floor themes
const FLOOR_THEMES = [
    {
        name: 'Sunken Crypt',
        floors: [1, 5],
        colors: { wall: '#2a2a3a', floor: '#1a1a28', accent: '#4a6a5a' },
        ambient: 'drip'
    },
    {
        name: 'Fungal Caverns',
        floors: [6, 10],
        colors: { wall: '#2a3a2a', floor: '#1a281a', accent: '#6aaa4a' },
        ambient: 'wind'
    },
    {
        name: 'Lava Depths',
        floors: [11, 15],
        colors: { wall: '#3a2020', floor: '#281818', accent: '#aa4a2a' },
        ambient: 'rumble'
    },
    {
        name: 'Frozen Abyss',
        floors: [16, 20],
        colors: { wall: '#202a3a', floor: '#182028', accent: '#4a8aaa' },
        ambient: 'wind'
    },
    {
        name: 'The Void',
        floors: [21, 25],
        colors: { wall: '#1a1020', floor: '#0a0818', accent: '#8a4aaa' },
        ambient: 'void'
    }
];

function getFloorTheme(floor) {
    for (const t of FLOOR_THEMES) {
        if (floor >= t.floors[0] && floor <= t.floors[1]) return t;
    }
    return FLOOR_THEMES[FLOOR_THEMES.length - 1];
}

// G = master game state, reset on new game
const G = {
    gameState: STATE.TITLE,
    difficulty: DIFFICULTY.NORMAL,
    difficultyLevel: 1,

    // Game entities
    player: null,
    enemies: [],
    projectiles: [],
    items: [],
    particles: [],
    lights: [],
    npcs: [],

    // Dungeon state
    currentFloor: 1,
    maxFloor: 25,
    dungeon: null,
    roomsCleared: 0,

    // Camera
    camera: { x: 0, y: 0, vx: 0, vy: 0 },

    // Time tracking
    time: 0,
    dt: 0,
    lastTime: 0,
    paused: false,
    frameCount: 0,

    // Active systems
    bossActive: null,
    dialogueQueue: [],
    floatingTexts: [],

    // Score tracking
    score: 0,
    kills: 0,
    highScore: 0,
    deepestFloor: 0,
    totalPlayTime: 0,

    // RNG seed
    seed: Date.now(),

    // Story progression
    storyChoices: [],
    flags: {},

    // Combo system
    combo: 0,
    comboTimer: 0,
    comboDecayRate: 1.5,
    maxCombo: 0,

    // Campfire checkpoint
    lastCampfire: null,

    // Run statistics
    runStats: {
        damageDealt: 0,
        damageTaken: 0,
        itemsFound: 0,
        enemiesKilled: 0,
        bossesKilled: 0,
        floorsCleared: 0,
        parries: 0,
        dodges: 0,
        healsUsed: 0,
        skillsUnlocked: 0,
        deathCount: 0
    }
};

// Item type enum
const ITEM_TYPE = {
    WEAPON: 'weapon',
    ARMOR: 'armor',
    CONSUMABLE: 'consumable',
    MATERIAL: 'material',
    KEY: 'key',
    RUNE: 'rune'
};

// Weapon subtypes
const WEAPON_TYPE = {
    SWORD: 'sword',
    AXE: 'axe',
    DAGGER: 'dagger',
    BOW: 'bow',
    STAFF: 'staff',
    SPEAR: 'spear'
};

// Status effects
const STATUS = {
    BURNING: { name: 'Burning', color: '#f44', dmgPerSec: 5 },
    FROZEN: { name: 'Frozen', color: '#4cf', slowPercent: 0.5 },
    SHOCKED: { name: 'Shocked', color: '#ff4', stunChance: 0.3 },
    POISONED: { name: 'Poisoned', color: '#8c4', dmgPerSec: 3 },
    BLEEDING: { name: 'Bleeding', color: '#c44', dmgPerSec: 8 },
    REGENERATING: { name: 'Regenerating', color: '#4c4', healPerSec: 5 },
    HASTE: { name: 'Haste', color: '#fc4', speedBonus: 0.3 },
    SHIELDED: { name: 'Shielded', color: '#48f', damageReduction: 0.5 }
};

// Collision layers
const LAYER = {
    FLOOR: 0,
    WALL: 1,
    PIT: 2,
    DOOR: 3,
    CHEST: 4,
    CAMPFIRE: 5,
    STAIRS: 6,
    ENEMY: 7,
    PLAYER: 8,
    PROJECTILE: 9,
    ITEM: 10,
    NPC: 11
};
