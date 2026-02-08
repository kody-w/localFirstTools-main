// abilities.js - Skill tree and ability definitions for Depths of the Abyss
// Depends on: constants.js (ELEMENT), utils.js (Util)

// Three skill tree branches: WARRIOR (red), MAGE (blue), ROGUE (green)
const SKILL_TREES = {
  warrior: {
    id: 'warrior',
    name: 'Warrior',
    description: 'Master of melee combat, heavy armor, and devastating power. High HP and damage.',
    color: '#DC143C',
    icon: 'sword',
    passive_bonuses: {
      base: { hp: 20, defense: 5, melee_damage: 1.1 },
      per_level: { hp: 10, defense: 2, melee_damage: 1.02 }
    }
  },
  mage: {
    id: 'mage',
    name: 'Mage',
    description: 'Arcane spellcaster with powerful ranged magic. High mana and spell damage.',
    color: '#1E90FF',
    icon: 'staff',
    passive_bonuses: {
      base: { mana: 50, spell_damage: 1.2, cooldown_reduction: 0.05 },
      per_level: { mana: 15, spell_damage: 1.03, cooldown_reduction: 0.01 }
    }
  },
  rogue: {
    id: 'rogue',
    name: 'Rogue',
    description: 'Swift assassin specializing in critical strikes and evasion. High speed and crit chance.',
    color: '#32CD32',
    icon: 'dagger',
    passive_bonuses: {
      base: { crit_chance: 0.1, dodge_distance: 1.2, item_find: 0.1 },
      per_level: { crit_chance: 0.02, dodge_distance: 1.05, item_find: 0.02 }
    }
  }
};

// Complete ability definitions for all three trees
const ABILITY_DEFS = {
  // ===== WARRIOR TREE =====
  // Tier 1: Basic combat abilities
  power_strike: {
    id: 'power_strike',
    name: 'Power Strike',
    tree: 'warrior',
    tier: 1,
    manaCost: 0,
    staminaCost: 20,
    cooldown: 3.0,
    duration: 0,
    damage: 50,
    damageMultiplier: 1.3,
    element: ELEMENT.PHYSICAL,
    aoe: false,
    range: 100,
    description: 'Powerful melee strike dealing 30% bonus damage. Low cooldown for sustained DPS.',
    effect: 'melee_power_attack',
    prerequisites: [],
    unlockLevel: 1,
    skillPointCost: 1
  },

  iron_skin: {
    id: 'iron_skin',
    name: 'Iron Skin',
    tree: 'warrior',
    tier: 1,
    manaCost: 0,
    staminaCost: 30,
    cooldown: 15.0,
    duration: 8.0,
    damage: 0,
    element: ELEMENT.PHYSICAL,
    aoe: false,
    range: 0,
    description: 'Harden your body, gaining 20% defense boost for 8 seconds. Essential for tanking.',
    effect: 'buff_defense',
    effectValue: 1.2,
    prerequisites: [],
    unlockLevel: 1,
    skillPointCost: 1
  },

  berserker_rage: {
    id: 'berserker_rage',
    name: 'Berserker Rage',
    tree: 'warrior',
    tier: 1,
    manaCost: 0,
    staminaCost: 0,
    cooldown: 0,
    duration: 0,
    damage: 0,
    element: ELEMENT.PHYSICAL,
    aoe: false,
    range: 0,
    description: 'Passive: Gain 30% attack speed and movement speed when below 30% HP. High-risk, high-reward.',
    effect: 'passive_low_hp_buff',
    effectValue: 1.3,
    passive: true,
    prerequisites: [],
    unlockLevel: 1,
    skillPointCost: 1
  },

  // Tier 2: Advanced warrior skills
  whirlwind: {
    id: 'whirlwind',
    name: 'Whirlwind',
    tree: 'warrior',
    tier: 2,
    manaCost: 0,
    staminaCost: 40,
    cooldown: 8.0,
    duration: 2.0,
    damage: 35,
    damagePerTick: 35,
    element: ELEMENT.PHYSICAL,
    aoe: true,
    range: 120,
    description: 'Spin rapidly for 2 seconds, hitting all nearby enemies. Great for crowd control.',
    effect: 'aoe_spin_attack',
    prerequisites: ['power_strike'],
    unlockLevel: 5,
    skillPointCost: 2
  },

  shield_bash: {
    id: 'shield_bash',
    name: 'Shield Bash',
    tree: 'warrior',
    tier: 2,
    manaCost: 0,
    staminaCost: 25,
    cooldown: 6.0,
    duration: 0,
    damage: 40,
    element: ELEMENT.PHYSICAL,
    aoe: false,
    range: 80,
    description: 'Bash enemies with your shield, dealing damage and stunning for 2 seconds. Combo setup.',
    effect: 'stun_attack',
    stunDuration: 2.0,
    prerequisites: ['iron_skin'],
    unlockLevel: 5,
    skillPointCost: 2
  },

  war_cry: {
    id: 'war_cry',
    name: 'War Cry',
    tree: 'warrior',
    tier: 2,
    manaCost: 0,
    staminaCost: 35,
    cooldown: 20.0,
    duration: 10.0,
    damage: 0,
    element: ELEMENT.PHYSICAL,
    aoe: true,
    range: 300,
    description: 'Rally allies with a mighty shout. Increases damage by 25% and defense by 15% for 10 seconds.',
    effect: 'buff_allies',
    buffStats: { damage: 1.25, defense: 1.15 },
    prerequisites: ['berserker_rage'],
    unlockLevel: 5,
    skillPointCost: 2
  },

  // Tier 3: Ultimate warrior abilities
  earthquake: {
    id: 'earthquake',
    name: 'Earthquake',
    tree: 'warrior',
    tier: 3,
    manaCost: 0,
    staminaCost: 60,
    cooldown: 30.0,
    duration: 0,
    damage: 150,
    element: ELEMENT.PHYSICAL,
    aoe: true,
    range: 400,
    description: 'Slam the ground, creating a massive shockwave. Stuns all enemies hit for 3 seconds.',
    effect: 'ultimate_aoe_stun',
    stunDuration: 3.0,
    prerequisites: ['whirlwind', 'shield_bash'],
    unlockLevel: 12,
    skillPointCost: 3
  },

  undying_will: {
    id: 'undying_will',
    name: 'Undying Will',
    tree: 'warrior',
    tier: 3,
    manaCost: 0,
    staminaCost: 0,
    cooldown: 180.0,
    duration: 0,
    damage: 0,
    element: ELEMENT.PHYSICAL,
    aoe: false,
    range: 0,
    description: 'Passive: Survive a lethal hit once with 1 HP. 3 minute cooldown. Critical for boss fights.',
    effect: 'passive_death_save',
    prerequisites: ['iron_skin', 'war_cry'],
    unlockLevel: 12,
    skillPointCost: 3
  },

  titans_grip: {
    id: 'titans_grip',
    name: "Titan's Grip",
    tree: 'warrior',
    tier: 3,
    manaCost: 0,
    staminaCost: 0,
    cooldown: 0,
    duration: 0,
    damage: 0,
    element: ELEMENT.PHYSICAL,
    aoe: false,
    range: 0,
    description: 'Passive: Dual wield two-handed weapons or equip weapon in both hands for 40% damage bonus.',
    effect: 'passive_dual_wield',
    damageBonus: 1.4,
    passive: true,
    prerequisites: ['power_strike', 'whirlwind'],
    unlockLevel: 12,
    skillPointCost: 3
  },

  // ===== MAGE TREE =====
  // Tier 1: Basic spells
  fireball: {
    id: 'fireball',
    name: 'Fireball',
    tree: 'mage',
    tier: 1,
    manaCost: 25,
    staminaCost: 0,
    cooldown: 2.0,
    duration: 0,
    damage: 60,
    element: ELEMENT.FIRE,
    aoe: false,
    range: 350,
    description: 'Launch a flaming projectile at your target. Basic ranged spell with good damage.',
    effect: 'projectile_fireball',
    projectileSpeed: 300,
    prerequisites: [],
    unlockLevel: 1,
    skillPointCost: 1
  },

  frost_shield: {
    id: 'frost_shield',
    name: 'Frost Shield',
    tree: 'mage',
    tier: 1,
    manaCost: 30,
    staminaCost: 0,
    cooldown: 12.0,
    duration: 6.0,
    damage: 0,
    element: ELEMENT.ICE,
    aoe: false,
    range: 0,
    description: 'Create an ice barrier that absorbs 150 damage. Reflects 20% damage to attackers.',
    effect: 'shield_absorb',
    absorbAmount: 150,
    reflectPercent: 0.2,
    prerequisites: [],
    unlockLevel: 1,
    skillPointCost: 1
  },

  mana_surge: {
    id: 'mana_surge',
    name: 'Mana Surge',
    tree: 'mage',
    tier: 1,
    manaCost: 0,
    staminaCost: 0,
    cooldown: 0,
    duration: 0,
    damage: 0,
    element: ELEMENT.ARCANE,
    aoe: false,
    range: 0,
    description: 'Passive: Increase mana regeneration by 50%. Essential for spell-heavy builds.',
    effect: 'passive_mana_regen',
    regenBonus: 1.5,
    passive: true,
    prerequisites: [],
    unlockLevel: 1,
    skillPointCost: 1
  },

  // Tier 2: Advanced magic
  lightning_chain: {
    id: 'lightning_chain',
    name: 'Lightning Chain',
    tree: 'mage',
    tier: 2,
    manaCost: 40,
    staminaCost: 0,
    cooldown: 5.0,
    duration: 0,
    damage: 70,
    element: ELEMENT.LIGHTNING,
    aoe: false,
    range: 300,
    description: 'Electrocute target and chain to 3 nearby enemies. Effective against groups.',
    effect: 'chain_lightning',
    chainTargets: 3,
    chainRange: 150,
    prerequisites: ['fireball'],
    unlockLevel: 5,
    skillPointCost: 2
  },

  teleport: {
    id: 'teleport',
    name: 'Teleport',
    tree: 'mage',
    tier: 2,
    manaCost: 35,
    staminaCost: 0,
    cooldown: 8.0,
    duration: 0,
    damage: 0,
    element: ELEMENT.ARCANE,
    aoe: false,
    range: 250,
    description: 'Instantly blink to target location. Grants 1 second invulnerability. Excellent escape.',
    effect: 'blink_teleport',
    invulnDuration: 1.0,
    prerequisites: ['frost_shield'],
    unlockLevel: 5,
    skillPointCost: 2
  },

  arcane_missile: {
    id: 'arcane_missile',
    name: 'Arcane Missile',
    tree: 'mage',
    tier: 2,
    manaCost: 30,
    staminaCost: 0,
    cooldown: 4.0,
    duration: 0,
    damage: 50,
    element: ELEMENT.ARCANE,
    aoe: false,
    range: 400,
    description: 'Fire a homing missile that never misses. Fires 3 missiles in a chain. Great DPS.',
    effect: 'homing_missile',
    missileCount: 3,
    prerequisites: ['mana_surge'],
    unlockLevel: 5,
    skillPointCost: 2
  },

  // Tier 3: Ultimate spells
  meteor_strike: {
    id: 'meteor_strike',
    name: 'Meteor Strike',
    tree: 'mage',
    tier: 3,
    manaCost: 80,
    staminaCost: 0,
    cooldown: 25.0,
    duration: 0,
    damage: 200,
    element: ELEMENT.FIRE,
    aoe: true,
    range: 500,
    description: 'Call down a massive meteor, dealing huge AoE damage. Leaves burning ground for 5 seconds.',
    effect: 'ultimate_meteor',
    burnDuration: 5.0,
    burnDamage: 20,
    aoeRadius: 180,
    prerequisites: ['fireball', 'lightning_chain'],
    unlockLevel: 12,
    skillPointCost: 3
  },

  time_warp: {
    id: 'time_warp',
    name: 'Time Warp',
    tree: 'mage',
    tier: 3,
    manaCost: 60,
    staminaCost: 0,
    cooldown: 40.0,
    duration: 6.0,
    damage: 0,
    element: ELEMENT.ARCANE,
    aoe: true,
    range: 300,
    description: 'Slow all enemies in area by 70% for 6 seconds. Gain 30% speed boost. Boss utility.',
    effect: 'time_manipulation',
    slowPercent: 0.7,
    selfSpeedBonus: 1.3,
    prerequisites: ['teleport', 'arcane_missile'],
    unlockLevel: 12,
    skillPointCost: 3
  },

  elemental_mastery: {
    id: 'elemental_mastery',
    name: 'Elemental Mastery',
    tree: 'mage',
    tier: 3,
    manaCost: 0,
    staminaCost: 0,
    cooldown: 0,
    duration: 0,
    damage: 0,
    element: ELEMENT.ARCANE,
    aoe: false,
    range: 0,
    description: 'Passive: Gain 30% resistance to all elements. Spells deal 20% more damage. Master caster.',
    effect: 'passive_element_master',
    resistAll: 0.3,
    spellDamageBonus: 1.2,
    passive: true,
    prerequisites: ['mana_surge', 'frost_shield'],
    unlockLevel: 12,
    skillPointCost: 3
  },

  // ===== ROGUE TREE =====
  // Tier 1: Basic rogue skills
  backstab: {
    id: 'backstab',
    name: 'Backstab',
    tree: 'rogue',
    tier: 1,
    manaCost: 0,
    staminaCost: 20,
    cooldown: 3.0,
    duration: 0,
    damage: 80,
    damageMultiplier: 2.0,
    element: ELEMENT.PHYSICAL,
    aoe: false,
    range: 70,
    description: 'Strike from behind for double damage. Bonus critical chance. Positioning matters.',
    effect: 'backstab_attack',
    backstabAngle: 90,
    bonusCrit: 0.5,
    prerequisites: [],
    unlockLevel: 1,
    skillPointCost: 1
  },

  poison_blade: {
    id: 'poison_blade',
    name: 'Poison Blade',
    tree: 'rogue',
    tier: 1,
    manaCost: 0,
    staminaCost: 15,
    cooldown: 1.0,
    duration: 6.0,
    damage: 30,
    dotDamage: 10,
    element: ELEMENT.POISON,
    aoe: false,
    range: 60,
    description: 'Coat your weapon in poison. Attacks deal 10 poison damage per second for 6 seconds.',
    effect: 'apply_poison_dot',
    prerequisites: [],
    unlockLevel: 1,
    skillPointCost: 1
  },

  quick_step: {
    id: 'quick_step',
    name: 'Quick Step',
    tree: 'rogue',
    tier: 1,
    manaCost: 0,
    staminaCost: 15,
    cooldown: 4.0,
    duration: 0,
    damage: 0,
    element: ELEMENT.PHYSICAL,
    aoe: false,
    range: 150,
    description: 'Dash quickly in any direction. 50% faster than normal dodge. Low cooldown mobility.',
    effect: 'quick_dash',
    dashSpeed: 1.5,
    prerequisites: [],
    unlockLevel: 1,
    skillPointCost: 1
  },

  // Tier 2: Advanced rogue techniques
  shadow_step: {
    id: 'shadow_step',
    name: 'Shadow Step',
    tree: 'rogue',
    tier: 2,
    manaCost: 0,
    staminaCost: 30,
    cooldown: 7.0,
    duration: 0,
    damage: 60,
    element: ELEMENT.DARK,
    aoe: false,
    range: 200,
    description: 'Teleport behind target enemy and strike. Guaranteed critical hit. Assassin core ability.',
    effect: 'teleport_backstab',
    guaranteedCrit: true,
    critMultiplier: 2.5,
    prerequisites: ['backstab'],
    unlockLevel: 5,
    skillPointCost: 2
  },

  fan_of_knives: {
    id: 'fan_of_knives',
    name: 'Fan of Knives',
    tree: 'rogue',
    tier: 2,
    manaCost: 0,
    staminaCost: 35,
    cooldown: 8.0,
    duration: 0,
    damage: 45,
    element: ELEMENT.PHYSICAL,
    aoe: true,
    range: 180,
    description: 'Throw knives in a cone, hitting all enemies. 8 knives, each with independent crit chance.',
    effect: 'cone_knife_attack',
    knifeCount: 8,
    coneAngle: 90,
    prerequisites: ['poison_blade'],
    unlockLevel: 5,
    skillPointCost: 2
  },

  smoke_bomb: {
    id: 'smoke_bomb',
    name: 'Smoke Bomb',
    tree: 'rogue',
    tier: 2,
    manaCost: 0,
    staminaCost: 40,
    cooldown: 15.0,
    duration: 4.0,
    damage: 0,
    element: ELEMENT.DARK,
    aoe: true,
    range: 150,
    description: 'Vanish in smoke, becoming invisible for 4 seconds. Break on attack. Perfect escape.',
    effect: 'stealth_invisibility',
    breakOnAttack: true,
    prerequisites: ['quick_step'],
    unlockLevel: 5,
    skillPointCost: 2
  },

  // Tier 3: Ultimate rogue abilities
  death_mark: {
    id: 'death_mark',
    name: 'Death Mark',
    tree: 'rogue',
    tier: 3,
    manaCost: 0,
    staminaCost: 50,
    cooldown: 20.0,
    duration: 0,
    damage: 250,
    element: ELEMENT.DARK,
    aoe: false,
    range: 100,
    description: 'Mark target for death. Massive single-target damage. Guaranteed critical strike. Boss killer.',
    effect: 'execute_attack',
    guaranteedCrit: true,
    critMultiplier: 3.0,
    bonusDamageOnLowHp: 1.5,
    prerequisites: ['backstab', 'shadow_step'],
    unlockLevel: 12,
    skillPointCost: 3
  },

  shadow_clone: {
    id: 'shadow_clone',
    name: 'Shadow Clone',
    tree: 'rogue',
    tier: 3,
    manaCost: 0,
    staminaCost: 60,
    cooldown: 45.0,
    duration: 15.0,
    damage: 0,
    element: ELEMENT.DARK,
    aoe: false,
    range: 0,
    description: 'Create a clone that mimics your attacks at 60% damage. Draws enemy aggro. Lasts 15 seconds.',
    effect: 'summon_clone',
    cloneDamage: 0.6,
    cloneHealth: 200,
    prerequisites: ['smoke_bomb', 'fan_of_knives'],
    unlockLevel: 12,
    skillPointCost: 3
  },

  master_thief: {
    id: 'master_thief',
    name: 'Master Thief',
    tree: 'rogue',
    tier: 3,
    manaCost: 0,
    staminaCost: 0,
    cooldown: 0,
    duration: 0,
    damage: 0,
    element: ELEMENT.PHYSICAL,
    aoe: false,
    range: 0,
    description: 'Passive: 40% better loot drops, 25% increased gold, and 20% chance to steal enemy items on hit.',
    effect: 'passive_loot_bonus',
    lootBonus: 1.4,
    goldBonus: 1.25,
    stealChance: 0.2,
    passive: true,
    prerequisites: ['poison_blade', 'quick_step'],
    unlockLevel: 12,
    skillPointCost: 3
  }
};

// Ability system utilities
const ABILITY_SYSTEM = {
  // Check if player can unlock ability
  canUnlockAbility(abilityId, unlockedAbilities, playerLevel) {
    const ability = ABILITY_DEFS[abilityId];
    if (!ability) return false;

    // Check level requirement
    if (playerLevel < ability.unlockLevel) return false;

    // Check if already unlocked
    if (unlockedAbilities.includes(abilityId)) return false;

    // Check prerequisites
    for (let prereq of ability.prerequisites) {
      if (!unlockedAbilities.includes(prereq)) return false;
    }

    return true;
  },

  // Get skill point cost for ability tier
  getAbilityCost(tier) {
    const costs = [0, 1, 2, 3]; // tier 0-3
    return costs[tier] || 0;
  },

  // Calculate total passive bonuses from skill tree
  getPassiveBonuses(tree, playerLevel, unlockedAbilities) {
    const treeData = SKILL_TREES[tree];
    if (!treeData) return {};

    const bonuses = { ...treeData.passive_bonuses.base };

    // Add per-level bonuses
    for (let stat in treeData.passive_bonuses.per_level) {
      const perLevel = treeData.passive_bonuses.per_level[stat];
      if (typeof perLevel === 'number' && perLevel < 1) {
        bonuses[stat] = (bonuses[stat] || 0) + (perLevel * playerLevel);
      } else {
        bonuses[stat] = (bonuses[stat] || 1) * Math.pow(perLevel, playerLevel);
      }
    }

    // Add passive ability bonuses
    for (let abilityId of unlockedAbilities) {
      const ability = ABILITY_DEFS[abilityId];
      if (ability && ability.passive && ability.tree === tree) {
        if (ability.regenBonus) bonuses.mana_regen = (bonuses.mana_regen || 1) * ability.regenBonus;
        if (ability.resistAll) bonuses.resist_all = (bonuses.resist_all || 0) + ability.resistAll;
        if (ability.spellDamageBonus) bonuses.spell_damage = (bonuses.spell_damage || 1) * ability.spellDamageBonus;
        if (ability.damageBonus) bonuses.damage = (bonuses.damage || 1) * ability.damageBonus;
        if (ability.lootBonus) bonuses.loot = (bonuses.loot || 1) * ability.lootBonus;
        if (ability.goldBonus) bonuses.gold = (bonuses.gold || 1) * ability.goldBonus;
        if (ability.effectValue) bonuses.low_hp_buff = ability.effectValue;
      }
    }

    return bonuses;
  },

  // Get all abilities for a tree sorted by tier
  getTreeAbilities(tree) {
    const abilities = [];
    for (let id in ABILITY_DEFS) {
      if (ABILITY_DEFS[id].tree === tree) {
        abilities.push(ABILITY_DEFS[id]);
      }
    }
    return abilities.sort((a, b) => a.tier - b.tier);
  },

  // Calculate ability damage with player stats
  calculateAbilityDamage(ability, playerStats) {
    let damage = ability.damage || 0;

    // Apply damage multiplier
    if (ability.damageMultiplier) {
      damage *= ability.damageMultiplier;
    }

    // Apply stat bonuses
    if (ability.tree === 'warrior' && playerStats.melee_damage) {
      damage *= playerStats.melee_damage;
    } else if (ability.tree === 'mage' && playerStats.spell_damage) {
      damage *= playerStats.spell_damage;
    } else if (ability.tree === 'rogue' && playerStats.damage) {
      damage *= playerStats.damage;
    }

    // Critical strike chance and multiplier
    let critChance = playerStats.crit_chance || 0;
    if (ability.bonusCrit) critChance += ability.bonusCrit;
    if (ability.guaranteedCrit) critChance = 1.0;

    if (Math.random() < critChance) {
      const critMult = ability.critMultiplier || 2.0;
      damage *= critMult;
    }

    return Math.floor(damage);
  },

  // Get cooldown with reduction
  getAbilityCooldown(ability, playerStats) {
    let cooldown = ability.cooldown || 0;
    const reduction = playerStats.cooldown_reduction || 0;
    return cooldown * (1 - reduction);
  }
};
