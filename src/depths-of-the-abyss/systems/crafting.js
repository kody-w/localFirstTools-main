// Crafting System — Recipe-based crafting at campfires
// Defines global Crafting object
// Dependencies: G, Util from utils.js, SFX from audio.js
//               CONSUMABLES, MATERIALS from data/items.js
//               Inventory from systems/inventory.js

const RECIPES = [
  {
    id: 'iron_sword',
    name: 'Iron Sword',
    result: { itemId: 'iron_sword', count: 1, type: 'weapon' },
    materials: [{ id: 'iron_ore', count: 3 }],
    minFloor: 1,
    description: 'A basic but reliable iron blade'
  },
  {
    id: 'health_potion',
    name: 'Health Potion',
    result: { itemId: 'health_potion', count: 1, type: 'consumable' },
    materials: [{ id: 'fungal_essence', count: 2 }],
    minFloor: 1,
    description: 'Restores 50 HP'
  },
  {
    id: 'mana_potion',
    name: 'Mana Potion',
    result: { itemId: 'mana_potion', count: 1, type: 'consumable' },
    materials: [
      { id: 'dark_crystal', count: 1 },
      { id: 'fungal_essence', count: 1 }
    ],
    minFloor: 1,
    description: 'Restores 30 mana'
  },
  {
    id: 'fire_bomb',
    name: 'Fire Bomb',
    result: { itemId: 'fire_bomb', count: 1, type: 'consumable' },
    materials: [
      { id: 'ember_dust', count: 2 },
      { id: 'iron_ore', count: 1 }
    ],
    minFloor: 3,
    description: 'Explosive AoE fire damage'
  },
  {
    id: 'frost_shield_scroll',
    name: 'Frost Shield Scroll',
    result: { itemId: 'frost_shield', count: 1, type: 'consumable' },
    materials: [{ id: 'frost_shard', count: 3 }],
    minFloor: 5,
    description: 'Temporary ice armor buff'
  },
  {
    id: 'poison_antidote',
    name: 'Poison Antidote',
    result: { itemId: 'antidote', count: 1, type: 'consumable' },
    materials: [{ id: 'fungal_essence', count: 3 }],
    minFloor: 2,
    description: 'Cures poison and burn effects'
  },
  {
    id: 'dark_blade',
    name: 'Dark Blade',
    result: { itemId: 'dark_blade', count: 1, type: 'weapon' },
    materials: [
      { id: 'dark_crystal', count: 3 },
      { id: 'iron_ore', count: 2 }
    ],
    minFloor: 8,
    description: 'Sword infused with dark energy'
  },
  {
    id: 'ember_armor',
    name: 'Ember Armor',
    result: { itemId: 'ember_chest', count: 1, type: 'armor' },
    materials: [
      { id: 'ember_dust', count: 3 },
      { id: 'iron_ore', count: 2 }
    ],
    minFloor: 6,
    description: 'Chest armor with fire resistance'
  },
  {
    id: 'frost_amulet',
    name: 'Frost Amulet',
    result: { itemId: 'frost_amulet', count: 1, type: 'armor' },
    materials: [
      { id: 'frost_shard', count: 2 },
      { id: 'dark_crystal', count: 1 }
    ],
    minFloor: 7,
    description: 'Amulet with ice resistance'
  },
  {
    id: 'void_shard_dagger',
    name: 'Void Shard Dagger',
    result: { itemId: 'void_dagger', count: 1, type: 'weapon' },
    materials: [
      { id: 'void_fragment', count: 2 },
      { id: 'dark_crystal', count: 2 }
    ],
    minFloor: 15,
    description: 'Legendary dagger from the void'
  },
  {
    id: 'ancient_ring',
    name: 'Ancient Ring',
    result: { itemId: 'ancient_ring', count: 1, type: 'armor' },
    materials: [
      { id: 'ancient_relic', count: 1 },
      { id: 'dark_crystal', count: 2 }
    ],
    minFloor: 12,
    description: 'Ring with all-stat bonuses'
  },
  {
    id: 'stamina_tonic',
    name: 'Stamina Tonic',
    result: { itemId: 'stamina_tonic', count: 1, type: 'consumable' },
    materials: [
      { id: 'fungal_essence', count: 1 },
      { id: 'ember_dust', count: 1 }
    ],
    minFloor: 3,
    description: 'Restores 50 stamina'
  },
  {
    id: 'elixir_of_power',
    name: 'Elixir of Power',
    result: { itemId: 'elixir_of_power', count: 1, type: 'consumable' },
    materials: [
      { id: 'ancient_relic', count: 1 },
      { id: 'ember_dust', count: 2 },
      { id: 'frost_shard', count: 1 }
    ],
    minFloor: 10,
    description: '+25% damage for 30 seconds'
  },
  {
    id: 'scroll_of_return',
    name: 'Scroll of Return',
    result: { itemId: 'scroll_of_return', count: 1, type: 'consumable' },
    materials: [{ id: 'void_fragment', count: 1 }],
    minFloor: 8,
    description: 'Teleport to last campfire'
  },
  {
    id: 'master_key',
    name: 'Master Key',
    result: { itemId: 'master_key', count: 1, type: 'key_item' },
    materials: [
      { id: 'ancient_relic', count: 2 },
      { id: 'void_fragment', count: 1 }
    ],
    minFloor: 18,
    description: 'Opens locked chests'
  }
];

const Crafting = {
  getAvailableRecipes() {
    const floor = G.currentFloor || 1;
    return RECIPES.filter(recipe => {
      if (recipe.minFloor > floor) return false;
      return this.canCraft(recipe.id);
    });
  },

  canCraft(recipeId) {
    const recipe = RECIPES.find(r => r.id === recipeId);
    if (!recipe) return false;

    // Check if player has all required materials
    for (const mat of recipe.materials) {
      const count = this.getMaterialCount(mat.id);
      if (count < mat.count) return false;
    }

    return true;
  },

  craft(recipeId) {
    const recipe = RECIPES.find(r => r.id === recipeId);
    if (!recipe || !this.canCraft(recipeId)) return null;

    // Consume materials
    for (const mat of recipe.materials) {
      Inventory.removeItemById(mat.id, mat.count);
    }

    // Create result item
    const resultItem = this.createResultItem(recipe.result);

    // Add to inventory
    if (Inventory.addItem(resultItem)) {
      SFX.playSound('craft_success');
      if (window.HUD) {
        HUD.addFloatingText(G.player.x, G.player.y - 16, 'Crafted: ' + recipe.name, '#44ff44', 18);
      }
      return resultItem;
    }

    return null;
  },

  createResultItem(result) {
    const baseItem = {
      id: result.itemId,
      name: '',
      type: result.type,
      rarity: 1,
      description: '',
      spriteColor: '#cccccc'
    };

    // Populate from data based on type
    if (result.type === 'consumable') {
      const consumable = CONSUMABLES.find(c => c.id === result.itemId);
      if (consumable) {
        baseItem.name = consumable.name;
        baseItem.description = consumable.description;
        baseItem.rarity = consumable.rarity;
        baseItem.spriteColor = consumable.color;
        baseItem.stackable = true;
        baseItem.count = result.count || 1;
      }
    } else if (result.type === 'weapon') {
      // Generate crafted weapon
      baseItem.name = this.getCraftedWeaponName(result.itemId);
      baseItem.slot = 'weapon';
      baseItem.stats = this.getCraftedWeaponStats(result.itemId);
      baseItem.element = this.getCraftedWeaponElement(result.itemId);
      baseItem.description = 'A crafted weapon';
      baseItem.rarity = 2; // Uncommon
      baseItem.spriteColor = RARITY_COLORS[2];
    } else if (result.type === 'armor') {
      // Generate crafted armor
      baseItem.name = this.getCraftedArmorName(result.itemId);
      baseItem.slot = this.getCraftedArmorSlot(result.itemId);
      baseItem.stats = this.getCraftedArmorStats(result.itemId);
      baseItem.element = this.getCraftedArmorElement(result.itemId);
      baseItem.description = 'A crafted armor piece';
      baseItem.rarity = 2; // Uncommon
      baseItem.spriteColor = RARITY_COLORS[2];
    } else if (result.type === 'key_item') {
      baseItem.name = this.getCraftedKeyItemName(result.itemId);
      baseItem.description = 'A special crafted item';
      baseItem.rarity = 3; // Rare
      baseItem.spriteColor = RARITY_COLORS[3];
    }

    return baseItem;
  },

  getCraftedWeaponName(id) {
    const names = {
      iron_sword: 'Iron Sword',
      dark_blade: 'Dark Blade',
      void_dagger: 'Void Shard Dagger'
    };
    return names[id] || 'Crafted Weapon';
  },

  getCraftedWeaponStats(id) {
    const stats = {
      iron_sword: { damage: 15 },
      dark_blade: { damage: 25, mana: 10 },
      void_dagger: { damage: 35, stamina: 15 }
    };
    return stats[id] || { damage: 10 };
  },

  getCraftedWeaponElement(id) {
    const elements = {
      iron_sword: ELEMENT.PHYSICAL,
      dark_blade: ELEMENT.DARK,
      void_dagger: ELEMENT.DARK
    };
    return elements[id] || ELEMENT.PHYSICAL;
  },

  getCraftedArmorName(id) {
    const names = {
      ember_chest: 'Ember Armor',
      frost_amulet: 'Frost Amulet',
      ancient_ring: 'Ancient Ring'
    };
    return names[id] || 'Crafted Armor';
  },

  getCraftedArmorSlot(id) {
    const slots = {
      ember_chest: 'chest',
      frost_amulet: 'amulet',
      ancient_ring: 'ring'
    };
    return slots[id] || 'chest';
  },

  getCraftedArmorStats(id) {
    const stats = {
      ember_chest: { defense: 10, fireResist: 25 },
      frost_amulet: { defense: 5, iceResist: 30 },
      ancient_ring: { hp: 20, mana: 10, stamina: 10, defense: 3 }
    };
    return stats[id] || { defense: 5 };
  },

  getCraftedArmorElement(id) {
    const elements = {
      ember_chest: ELEMENT.FIRE,
      frost_amulet: ELEMENT.ICE,
      ancient_ring: ELEMENT.PHYSICAL
    };
    return elements[id] || ELEMENT.PHYSICAL;
  },

  getCraftedKeyItemName(id) {
    const names = {
      master_key: 'Master Key'
    };
    return names[id] || 'Key Item';
  },

  getMaterialCount(materialId) {
    let total = 0;
    G.player.inventory.forEach(item => {
      if (item.id === materialId) {
        total += item.count || 1;
      }
    });
    return total;
  },

  getAllMaterials() {
    const materials = {};

    G.player.inventory.forEach(item => {
      if (item.type === 'material') {
        if (!materials[item.id]) {
          materials[item.id] = {
            name: item.name,
            count: 0,
            color: item.spriteColor
          };
        }
        materials[item.id].count += item.count || 1;
      }
    });

    return Object.entries(materials).map(([id, data]) => ({
      id,
      name: data.name,
      count: data.count,
      color: data.color
    }));
  }
};
