// items.js - Weapon, armor, consumable, and loot definitions for Depths of the Abyss
// Depends on: constants.js (G, RARITY, RARITY_COLORS, ELEMENT), utils.js (Util)

// Base weapon type definitions with combat stats
const WEAPON_TYPES = {
  rusty_sword: {
    id: 'rusty_sword',
    name: 'Rusty Sword',
    type: 'melee_balanced',
    baseDamage: 15,
    speed: 1.2, // attacks per second
    range: 80, // pixels
    staminaCost: 10,
    element: ELEMENT.PHYSICAL,
    swingArc: 90, // degrees
    description: 'A balanced weapon for beginners. Medium damage and speed.',
    spriteColor: '#8B7355',
    bonusStats: { critical: 0.05 }
  },
  battle_axe: {
    id: 'battle_axe',
    name: 'Battle Axe',
    type: 'melee_heavy',
    baseDamage: 35,
    speed: 0.6,
    range: 90,
    staminaCost: 20,
    element: ELEMENT.PHYSICAL,
    swingArc: 120,
    description: 'Slow but devastating. Wide sweeping attacks.',
    spriteColor: '#C0C0C0',
    bonusStats: { cleave: 0.3 }
  },
  dagger: {
    id: 'dagger',
    name: 'Dagger',
    type: 'melee_fast',
    baseDamage: 8,
    speed: 2.5,
    range: 50,
    staminaCost: 5,
    element: ELEMENT.PHYSICAL,
    swingArc: 45,
    description: 'Lightning fast strikes. Bonus critical chance.',
    spriteColor: '#B8860B',
    bonusStats: { critical: 0.25, combo: 1.2 }
  },
  spear: {
    id: 'spear',
    name: 'Spear',
    type: 'melee_reach',
    baseDamage: 18,
    speed: 1.0,
    range: 140,
    staminaCost: 12,
    element: ELEMENT.PHYSICAL,
    swingArc: 30,
    description: 'Extended reach for safe engagement.',
    spriteColor: '#8B4513',
    bonusStats: { pierce: 0.2 }
  },
  war_hammer: {
    id: 'war_hammer',
    name: 'War Hammer',
    type: 'melee_crusher',
    baseDamage: 45,
    speed: 0.4,
    range: 75,
    staminaCost: 25,
    element: ELEMENT.PHYSICAL,
    swingArc: 60,
    description: 'Crushingly powerful. Chance to stun enemies.',
    spriteColor: '#696969',
    bonusStats: { stun: 0.3, armorBreak: 0.4 }
  },
  staff: {
    id: 'staff',
    name: 'Arcane Staff',
    type: 'magic_channeler',
    baseDamage: 20,
    speed: 0.8,
    range: 100,
    staminaCost: 0,
    manaCost: 15,
    element: ELEMENT.ARCANE,
    swingArc: 360,
    description: 'Channels magical power. Uses mana instead of stamina.',
    spriteColor: '#9370DB',
    bonusStats: { spellPower: 1.3, manaRegen: 0.1 }
  },
  bow: {
    id: 'bow',
    name: 'Hunter Bow',
    type: 'ranged_projectile',
    baseDamage: 22,
    speed: 1.5,
    range: 400,
    staminaCost: 15,
    element: ELEMENT.PHYSICAL,
    swingArc: 15,
    description: 'Fires arrows at distant targets. Requires line of sight.',
    spriteColor: '#8B4513',
    bonusStats: { pierce: 0.3, headshot: 2.0 }
  },
  scythe: {
    id: 'scythe',
    name: 'Soul Scythe',
    type: 'melee_lifesteal',
    baseDamage: 28,
    speed: 0.7,
    range: 110,
    staminaCost: 18,
    element: ELEMENT.DARK,
    swingArc: 150,
    description: 'Reaps life from enemies. Heals wielder on hit.',
    spriteColor: '#2F4F4F',
    bonusStats: { lifesteal: 0.15, critical: 0.1 }
  }
};

// Generate weapon instance with rarity scaling and floor-based upgrades
function generateWeapon(typeId, rarity, floor) {
  const base = WEAPON_TYPES[typeId];
  if (!base) return null;

  // Rarity multipliers for weapon stats
  const rarityMults = [1.0, 1.3, 1.7, 2.2, 3.0]; // common to legendary
  const rarityMult = rarityMults[rarity];

  // Floor scaling for power progression (10% per 5 floors)
  const floorMult = 1 + (Math.floor(floor / 5) * 0.1);

  const weapon = {
    id: `${typeId}_${rarity}_${floor}`,
    type: 'weapon',
    baseType: typeId,
    name: `${RARITY[rarity]} ${base.name}`,
    rarity: rarity,
    damage: Math.floor(base.baseDamage * rarityMult * floorMult),
    speed: base.speed * (1 + rarity * 0.05), // slight speed increase per rarity
    range: base.range,
    staminaCost: Math.max(5, base.staminaCost - rarity * 2),
    manaCost: base.manaCost || 0,
    element: base.element,
    swingArc: base.swingArc,
    description: base.description,
    color: RARITY_COLORS[rarity],
    spriteColor: base.spriteColor,
    bonusStats: { ...base.bonusStats },
    equipped: false,
    durability: 100
  };

  // Add random bonus stats based on rarity
  if (rarity >= 1) weapon.bonusStats.damage = 1 + rarity * 0.1;
  if (rarity >= 2) weapon.bonusStats[Util.pick(['critical', 'speed', 'lifesteal'])] = 0.05 + rarity * 0.05;
  if (rarity >= 3) weapon.bonusStats.allStats = 1.15;
  if (rarity >= 4) weapon.bonusStats.legendary = true;

  return weapon;
}

// Armor slot definitions
const ARMOR_TYPES = {
  head: {
    id: 'head',
    name: 'Helmet',
    slot: 'head',
    baseDefense: 8,
    bonuses: { hp: 20 },
    variants: ['Leather Cap', 'Iron Helm', 'Knight Helmet', 'Obsidian Crown', 'Abyssal Mask']
  },
  chest: {
    id: 'chest',
    name: 'Chestplate',
    slot: 'chest',
    baseDefense: 15,
    bonuses: { hp: 50 },
    variants: ['Leather Armor', 'Chainmail', 'Plate Armor', 'Dragonscale Mail', 'Voidplate']
  },
  legs: {
    id: 'legs',
    name: 'Leg Armor',
    slot: 'legs',
    baseDefense: 12,
    bonuses: { stamina: 20 },
    variants: ['Leather Pants', 'Chain Leggings', 'Plate Greaves', 'Runestone Legs', 'Abyssal Greaves']
  },
  boots: {
    id: 'boots',
    name: 'Boots',
    slot: 'boots',
    baseDefense: 6,
    bonuses: { speed: 1.1 },
    variants: ['Worn Boots', 'Traveler Boots', 'Steel Sabatons', 'Swift Boots', 'Void Walkers']
  },
  gloves: {
    id: 'gloves',
    name: 'Gloves',
    slot: 'gloves',
    baseDefense: 5,
    bonuses: { attackSpeed: 1.05 },
    variants: ['Cloth Gloves', 'Leather Gloves', 'Gauntlets', 'Assassin Gloves', 'Abyssal Grasp']
  },
  ring: {
    id: 'ring',
    name: 'Ring',
    slot: 'ring',
    baseDefense: 0,
    bonuses: { critical: 0.05, damage: 1.1 },
    variants: ['Copper Ring', 'Silver Ring', 'Gold Ring', 'Ruby Ring', 'Void Ring']
  },
  amulet: {
    id: 'amulet',
    name: 'Amulet',
    slot: 'amulet',
    baseDefense: 0,
    bonuses: { mana: 50, resist: 0.1 },
    variants: ['Simple Pendant', 'Stone Amulet', 'Crystal Charm', 'Enchanted Amulet', 'Abyssal Talisman']
  }
};

// Generate armor piece with rarity tiers
function generateArmor(slotId, rarity, floor) {
  const base = ARMOR_TYPES[slotId];
  if (!base) return null;

  const rarityMults = [1.0, 1.4, 1.9, 2.5, 3.5];
  const rarityMult = rarityMults[rarity];
  const floorMult = 1 + (Math.floor(floor / 5) * 0.15);

  const armor = {
    id: `${slotId}_${rarity}_${floor}`,
    type: 'armor',
    slot: slotId,
    name: `${base.variants[rarity]}`,
    rarity: rarity,
    defense: Math.floor(base.baseDefense * rarityMult * floorMult),
    bonuses: {},
    color: RARITY_COLORS[rarity],
    equipped: false
  };

  // Scale bonuses by rarity
  for (let stat in base.bonuses) {
    armor.bonuses[stat] = base.bonuses[stat] * rarityMult;
  }

  // Add extra resistance based on rarity
  if (rarity >= 1) armor.bonuses.resist = 0.05 + rarity * 0.03;
  if (rarity >= 3) armor.bonuses.hp = (armor.bonuses.hp || 0) + 30;
  if (rarity >= 4) armor.bonuses.allResist = 0.15;

  return armor;
}

// Consumable item definitions with effects
const CONSUMABLES = {
  health_potion: {
    id: 'health_potion',
    name: 'Health Potion',
    type: 'consumable',
    effect: 'healPlayer',
    effectValue: 50,
    description: 'Restores 50 HP instantly.',
    rarity: 0,
    stackable: true,
    maxStack: 5,
    color: '#DC143C'
  },
  mana_potion: {
    id: 'mana_potion',
    name: 'Mana Potion',
    type: 'consumable',
    effect: 'restoreMana',
    effectValue: 50,
    description: 'Restores 50 mana instantly.',
    rarity: 0,
    stackable: true,
    maxStack: 5,
    color: '#1E90FF'
  },
  stamina_tonic: {
    id: 'stamina_tonic',
    name: 'Stamina Tonic',
    type: 'consumable',
    effect: 'restoreStamina',
    effectValue: 100,
    description: 'Fully restores stamina.',
    rarity: 0,
    stackable: true,
    maxStack: 5,
    color: '#32CD32'
  },
  antidote: {
    id: 'antidote',
    name: 'Antidote',
    type: 'consumable',
    effect: 'curePoison',
    effectValue: 1,
    description: 'Cures poison and toxic effects.',
    rarity: 0,
    stackable: true,
    maxStack: 3,
    color: '#9ACD32'
  },
  fire_bomb: {
    id: 'fire_bomb',
    name: 'Fire Bomb',
    type: 'consumable',
    effect: 'throwFireBomb',
    effectValue: 100,
    description: 'Throw an explosive fire bomb. 100 damage in area.',
    rarity: 1,
    stackable: true,
    maxStack: 3,
    color: '#FF4500'
  },
  ice_shard: {
    id: 'ice_shard',
    name: 'Ice Shard',
    type: 'consumable',
    effect: 'throwIceShard',
    effectValue: 60,
    description: 'Launch a freezing projectile. Slows enemies.',
    rarity: 1,
    stackable: true,
    maxStack: 3,
    color: '#87CEEB'
  },
  scroll_of_return: {
    id: 'scroll_of_return',
    name: 'Scroll of Return',
    type: 'consumable',
    effect: 'returnToCampfire',
    effectValue: 1,
    description: 'Instantly return to the last campfire.',
    rarity: 2,
    stackable: true,
    maxStack: 1,
    color: '#FFD700'
  },
  elixir_of_power: {
    id: 'elixir_of_power',
    name: 'Elixir of Power',
    type: 'consumable',
    effect: 'buffAllStats',
    effectValue: 1.5,
    effectDuration: 30,
    description: 'Grants 50% damage boost and power-up for 30 seconds.',
    rarity: 3,
    stackable: false,
    maxStack: 1,
    color: '#FF00FF'
  }
};

// Crafting material definitions
const MATERIALS = {
  bone: {
    id: 'bone',
    name: 'Bone Fragment',
    type: 'material',
    description: 'Common crafting material from undead enemies.',
    rarity: 0,
    stackable: true,
    color: '#F5F5DC'
  },
  iron_ore: {
    id: 'iron_ore',
    name: 'Iron Ore',
    type: 'material',
    description: 'Used to upgrade weapons and armor.',
    rarity: 0,
    stackable: true,
    color: '#A9A9A9'
  },
  dark_crystal: {
    id: 'dark_crystal',
    name: 'Dark Crystal',
    type: 'material',
    description: 'Resonates with abyssal energy. Rare material.',
    rarity: 2,
    stackable: true,
    color: '#4B0082'
  },
  fungal_essence: {
    id: 'fungal_essence',
    name: 'Fungal Essence',
    type: 'material',
    description: 'Extracted from mushroom enemies.',
    rarity: 1,
    stackable: true,
    color: '#9370DB'
  },
  ember_dust: {
    id: 'ember_dust',
    name: 'Ember Dust',
    type: 'material',
    description: 'Hot to the touch. From fire enemies.',
    rarity: 1,
    stackable: true,
    color: '#FF6347'
  },
  frost_shard: {
    id: 'frost_shard',
    name: 'Frost Shard',
    type: 'material',
    description: 'Never melts. From frozen enemies.',
    rarity: 1,
    stackable: true,
    color: '#B0E0E6'
  },
  void_fragment: {
    id: 'void_fragment',
    name: 'Void Fragment',
    type: 'material',
    description: 'Reality bends around it. Very rare.',
    rarity: 3,
    stackable: true,
    color: '#191970'
  },
  ancient_relic: {
    id: 'ancient_relic',
    name: 'Ancient Relic',
    type: 'material',
    description: 'Legendary crafting material. Boss drops only.',
    rarity: 4,
    stackable: true,
    color: '#FFD700'
  }
};

// Loot generation tables for floor-based progression
const LOOT_TABLES = {
  common_chest: {
    minItems: 1,
    maxItems: 2,
    chances: {
      weapon: 0.3,
      armor: 0.3,
      consumable: 0.8,
      material: 0.6
    }
  },
  rare_chest: {
    minItems: 2,
    maxItems: 4,
    chances: {
      weapon: 0.5,
      armor: 0.5,
      consumable: 1.0,
      material: 0.8
    },
    rarityBoost: 1
  },
  boss_loot: {
    minItems: 3,
    maxItems: 5,
    chances: {
      weapon: 0.8,
      armor: 0.8,
      consumable: 0.5,
      material: 1.0
    },
    rarityBoost: 2,
    guaranteedRare: true
  },
  elite_enemy: {
    minItems: 1,
    maxItems: 2,
    chances: {
      weapon: 0.4,
      armor: 0.4,
      consumable: 0.3,
      material: 0.7
    },
    rarityBoost: 1
  }
};

// Generate loot drops based on floor and rarity boost
function generateLoot(floor, rarityBoost = 0, tableType = 'common_chest') {
  const table = LOOT_TABLES[tableType];
  if (!table) return [];

  const loot = [];
  const itemCount = Util.randInt(table.minItems, table.maxItems);

  for (let i = 0; i < itemCount; i++) {
    let itemType = null;

    // Roll for item type
    const roll = Math.random();
    if (roll < table.chances.weapon) itemType = 'weapon';
    else if (roll < table.chances.weapon + table.chances.armor) itemType = 'armor';
    else if (roll < table.chances.weapon + table.chances.armor + table.chances.consumable) itemType = 'consumable';
    else if (roll < table.chances.weapon + table.chances.armor + table.chances.consumable + table.chances.material) itemType = 'material';

    if (!itemType) continue;

    // Determine rarity (higher floors = better loot)
    let rarity = 0;
    const rarityRoll = Math.random() + (floor / 50) + (rarityBoost * 0.2);
    if (rarityRoll > 0.9) rarity = 4; // legendary
    else if (rarityRoll > 0.7) rarity = 3; // epic
    else if (rarityRoll > 0.5) rarity = 2; // rare
    else if (rarityRoll > 0.3) rarity = 1; // uncommon

    if (table.guaranteedRare && rarity < 2) rarity = 2;

    // Generate item
    let item = null;
    if (itemType === 'weapon') {
      const weaponKeys = Object.keys(WEAPON_TYPES);
      const weaponType = weaponKeys[Util.randInt(0, weaponKeys.length - 1)];
      item = generateWeapon(weaponType, rarity, floor);
    } else if (itemType === 'armor') {
      const armorKeys = Object.keys(ARMOR_TYPES);
      const armorSlot = armorKeys[Util.randInt(0, armorKeys.length - 1)];
      item = generateArmor(armorSlot, rarity, floor);
    } else if (itemType === 'consumable') {
      const consumableKeys = Object.keys(CONSUMABLES);
      const consumableId = consumableKeys[Util.randInt(0, consumableKeys.length - 1)];
      item = { ...CONSUMABLES[consumableId], count: 1 };
    } else if (itemType === 'material') {
      const materialKeys = Object.keys(MATERIALS);
      const materialId = materialKeys[Util.randInt(0, materialKeys.length - 1)];
      item = { ...MATERIALS[materialId], count: Util.randInt(1, 3) };
    }

    if (item) loot.push(item);
  }

  return loot;
}

// Equipment management utilities
const EQUIPMENT_UTILS = {
  // Get total defense from all equipped armor
  getTotalDefense(inventory) {
    let total = 0;
    for (let item of inventory) {
      if (item.type === 'armor' && item.equipped) {
        total += item.defense || 0;
      }
    }
    return total;
  },

  // Get all equipped items
  getEquippedItems(inventory) {
    return inventory.filter(item => item.equipped);
  },

  // Equip an item (unequip others in same slot)
  equipItem(inventory, itemId) {
    const item = inventory.find(i => i.id === itemId);
    if (!item) return false;

    // Unequip items in same slot
    if (item.type === 'weapon') {
      inventory.forEach(i => { if (i.type === 'weapon') i.equipped = false; });
    } else if (item.type === 'armor') {
      inventory.forEach(i => { if (i.type === 'armor' && i.slot === item.slot) i.equipped = false; });
    }

    item.equipped = true;
    return true;
  },

  // Calculate total stat bonuses from equipped items
  getStatBonuses(inventory) {
    const bonuses = {
      hp: 0,
      mana: 0,
      stamina: 0,
      defense: 0,
      damage: 1.0,
      speed: 1.0,
      critical: 0,
      resist: 0,
      lifesteal: 0
    };

    for (let item of inventory) {
      if (!item.equipped) continue;

      if (item.bonuses) {
        for (let stat in item.bonuses) {
          if (bonuses[stat] !== undefined) {
            if (typeof bonuses[stat] === 'number' && bonuses[stat] < 1) {
              bonuses[stat] += item.bonuses[stat];
            } else if (stat === 'damage' || stat === 'speed') {
              bonuses[stat] *= item.bonuses[stat];
            } else {
              bonuses[stat] += item.bonuses[stat];
            }
          }
        }
      }

      if (item.bonusStats) {
        for (let stat in item.bonusStats) {
          if (bonuses[stat] !== undefined) {
            bonuses[stat] += item.bonusStats[stat];
          }
        }
      }
    }

    return bonuses;
  }
};
