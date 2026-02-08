// Progression System — XP, leveling, stat allocation, skill points
// Defines global Progression object
// Dependencies: G, STATE, Util from utils.js, SFX from audio.js
//               ABILITY_DEFS, SKILL_TREES, canUnlockAbility from data/abilities.js
//               Player from combat/player.js, Camera from world/camera.js

const Progression = {
  difficultyMults: {
    easy: 0.8,
    normal: 1.0,
    hard: 1.5
  },

  init() {
    G.player.xp = 0;
    G.player.level = 1;
    G.player.nextLevelXP = 50;
    G.player.statPoints = 0;
    G.player.skillPoints = 0;
    G.player.stats = {
      str: 0,
      dex: 0,
      int: 0,
      vit: 0
    };
    G.player.unlockedAbilities = [];
    G.player.equippedAbilities = [null, null, null, null]; // 4 hotbar slots
  },

  addXP(amount) {
    const difficulty = G.difficulty || 'normal';
    const mult = this.difficultyMults[difficulty];
    const xpGained = Math.floor(amount * mult);

    G.player.xp += xpGained;

    // Show XP gain floating text
    if (window.HUD) {
      HUD.addFloatingText(G.player.x, G.player.y - 20, '+' + xpGained + ' XP', '#ffff44', 18);
    }

    // Check for level up
    while (G.player.xp >= G.player.nextLevelXP) {
      this.levelUp();
    }
  },

  levelUp() {
    G.player.xp -= G.player.nextLevelXP;
    G.player.level++;

    // Award stat points and skill points
    G.player.statPoints += 3;
    G.player.skillPoints += 1;

    // Increase base stats
    const oldMaxHp = G.player.maxHp;
    const oldMaxMana = G.player.maxMana;
    const oldMaxStamina = G.player.maxStamina;

    G.player.maxHp += 10;
    G.player.maxMana += 5;
    G.player.maxStamina += 5;

    // Restore to full
    G.player.hp = G.player.maxHp;
    G.player.mana = G.player.maxMana;
    G.player.stamina = G.player.maxStamina;

    // Calculate next level XP threshold
    G.player.nextLevelXP = 50 + G.player.level * 30;

    // Visual and audio feedback
    SFX.playSound('player_levelup');
    if (window.Camera) {
      Camera.shake(3, 0.2);
    }
    if (window.FX) {
      FX.levelup(G.player.x, G.player.y);
    }
    if (window.HUD) {
      HUD.addFloatingText(G.player.x, G.player.y - 24, 'LEVEL UP!', '#ffff00', 24);
    }

    // Log level up
    console.log(`Level up! Now level ${G.player.level}`);
  },

  allocateStat(stat) {
    if (G.player.statPoints <= 0) return false;
    if (!['str', 'dex', 'int', 'vit'].includes(stat)) return false;

    G.player.statPoints--;
    G.player.stats[stat]++;

    // Apply stat bonuses
    this.applyStatBonuses();

    SFX.playSound('stat_allocate');
    if (window.HUD) {
      const statNames = {
        str: 'Strength',
        dex: 'Dexterity',
        int: 'Intelligence',
        vit: 'Vitality'
      };
      HUD.addFloatingText(G.player.x, G.player.y - 16, '+1 ' + statNames[stat], '#44ff44', 18);
    }

    return true;
  },

  applyStatBonuses() {
    const stats = G.player.stats;

    // Strength: +2 melee damage, +1% crit damage per point
    const strBonus = {
      damage: stats.str * 2,
      critDamage: stats.str * 0.01
    };

    // Dexterity: +0.1 speed, +2% crit chance, +3 stamina per point
    const dexBonus = {
      speed: stats.dex * 0.1,
      critChance: stats.dex * 0.02,
      stamina: stats.dex * 3
    };

    // Intelligence: +3% spell damage, +5 mana, +1% cooldown reduction per point
    const intBonus = {
      spellDamage: stats.int * 0.03,
      mana: stats.int * 5,
      cooldownReduction: stats.int * 0.01
    };

    // Vitality: +8 maxHp, +2 defense, +1 hp regen per point
    const vitBonus = {
      hp: stats.vit * 8,
      defense: stats.vit * 2,
      hpRegen: stats.vit * 1
    };

    // Apply bonuses to player
    G.player.damage = (G.player.baseDamage || 10) + strBonus.damage;
    G.player.critDamageMult = 1.5 + strBonus.critDamage;
    G.player.speed = (G.player.baseSpeed || 3) + dexBonus.speed;
    G.player.critChance = 0.05 + dexBonus.critChance;
    G.player.maxStamina = (G.player.baseMaxStamina || 100) + dexBonus.stamina;
    G.player.spellDamageMult = 1.0 + intBonus.spellDamage;
    G.player.maxMana = (G.player.baseMaxMana || 50) + intBonus.mana;
    G.player.cooldownReduction = intBonus.cooldownReduction;
    G.player.maxHp = (G.player.baseMaxHp || 100) + vitBonus.hp;
    G.player.defense = (G.player.baseDefense || 5) + vitBonus.defense;
    G.player.hpRegen = vitBonus.hpRegen;

    // Cap current values to new max
    G.player.hp = Math.min(G.player.hp, G.player.maxHp);
    G.player.mana = Math.min(G.player.mana, G.player.maxMana);
    G.player.stamina = Math.min(G.player.stamina, G.player.maxStamina);
  },

  unlockAbility(abilityId) {
    if (!window.ABILITY_DEFS) return false;

    const ability = ABILITY_DEFS[abilityId];
    if (!ability) return false;

    // Check if already unlocked
    if (G.player.unlockedAbilities.includes(abilityId)) return false;

    // Check prerequisites
    if (ability.requires && ability.requires.length > 0) {
      const hasPrereqs = ability.requires.every(reqId =>
        G.player.unlockedAbilities.includes(reqId)
      );
      if (!hasPrereqs) {
        if (window.HUD) {
          HUD.addFloatingText(G.player.x, G.player.y - 16, 'Prerequisites not met', '#ff4444', 18);
        }
        return false;
      }
    }

    // Check skill point cost
    const tier = ability.tier || 1;
    const cost = tier;

    if (G.player.skillPoints < cost) {
      if (window.HUD) {
        HUD.addFloatingText(G.player.x, G.player.y - 16, 'Not enough skill points', '#ff4444', 18);
      }
      return false;
    }

    // Unlock ability
    G.player.skillPoints -= cost;
    G.player.unlockedAbilities.push(abilityId);

    // Apply passive effects immediately
    if (ability.passive) {
      this.applyPassiveAbility(ability);
    }

    SFX.playSound('ability_unlock');
    if (window.HUD) {
      HUD.addFloatingText(G.player.x, G.player.y - 16, 'Unlocked: ' + ability.name, '#44ff44', 18);
    }
    if (window.FX) {
      FX.magic(G.player.x, G.player.y, '#ffff00');
    }

    return true;
  },

  applyPassiveAbility(ability) {
    // Apply passive bonuses to player stats
    if (ability.effects) {
      for (const effect in ability.effects) {
        const value = ability.effects[effect];
        if (effect === 'maxHp') G.player.maxHp += value;
        if (effect === 'maxMana') G.player.maxMana += value;
        if (effect === 'maxStamina') G.player.maxStamina += value;
        if (effect === 'defense') G.player.defense += value;
        if (effect === 'damage') G.player.damage += value;
        if (effect === 'speed') G.player.speed += value;
        if (effect === 'critChance') G.player.critChance += value;
        if (effect === 'critDamage') G.player.critDamageMult += value;
      }
    }
  },

  equipAbility(abilityId, slot) {
    if (slot < 0 || slot > 3) return false;
    if (!G.player.unlockedAbilities.includes(abilityId)) return false;

    const ability = ABILITY_DEFS[abilityId];
    if (!ability || ability.passive) return false; // Can't equip passive abilities

    G.player.equippedAbilities[slot] = abilityId;
    SFX.playSound('menu_select');

    return true;
  },

  getXPProgress() {
    return {
      current: G.player.xp,
      needed: G.player.nextLevelXP,
      percent: G.player.xp / G.player.nextLevelXP
    };
  },

  getStatBonuses() {
    const stats = G.player.stats;

    return {
      str: {
        damage: stats.str * 2,
        critDamage: stats.str * 1
      },
      dex: {
        speed: stats.dex * 0.1,
        critChance: stats.dex * 2,
        stamina: stats.dex * 3
      },
      int: {
        spellDamage: stats.int * 3,
        mana: stats.int * 5,
        cooldownReduction: stats.int * 1
      },
      vit: {
        hp: stats.vit * 8,
        defense: stats.vit * 2,
        hpRegen: stats.vit * 1
      }
    };
  },

  getFloorDifficultyMult(floor) {
    const difficulty = G.difficulty || 'normal';
    let baseMult = 1.0;

    if (floor >= 21) baseMult = 2.5;
    else if (floor >= 16) baseMult = 2.0;
    else if (floor >= 11) baseMult = 1.6;
    else if (floor >= 6) baseMult = 1.3;

    // Hard mode additional multiplier
    if (difficulty === 'hard') {
      baseMult *= 1.3;
    }

    return baseMult;
  },

  calculateScore() {
    const floor = G.currentFloor || 1;
    const kills = G.player.kills || 0;
    const bossKills = G.player.bossKills || 0;
    const time = G.playTime || 0; // in seconds
    const deaths = G.player.deaths || 0;
    const difficulty = G.difficulty || 'normal';

    let score = 0;

    // Floor reached (100 points per floor)
    score += floor * 100;

    // Kills (10 points each)
    score += kills * 10;

    // Boss kills (500 points each)
    score += bossKills * 500;

    // Time bonus (lose 1 point per 10 seconds)
    score -= Math.floor(time / 10);

    // Death penalty (lose 200 points per death)
    score -= deaths * 200;

    // Difficulty bonus
    if (difficulty === 'hard') {
      score *= 1.5;
    } else if (difficulty === 'easy') {
      score *= 0.7;
    }

    // Ensure score is not negative
    score = Math.max(0, Math.floor(score));

    G.score = score;
    return score;
  }
};
