// Inventory System — Item management, equipment, ground items, loot drops
// Defines global Inventory object
// Dependencies: G, STATE, TILE_SIZE, ELEMENT, RARITY, RARITY_COLORS from constants.js
//               Util from utils.js, SFX from audio.js
//               WEAPON_TYPES, ARMOR_TYPES, CONSUMABLES, MATERIALS, generateWeapon, LOOT_TABLES from data/items.js
//               Player from combat/player.js, Camera from world/camera.js

const Inventory = {
  maxInventory: 20,
  groundItems: [], // {item, x, y, bobTimer}

  init() {
    G.player.inventory = [];
    G.player.equipped = {
      weapon: null,
      helmet: null,
      chest: null,
      legs: null,
      boots: null,
      amulet: null,
      ring: null
    };
    this.groundItems = [];
  },

  addItem(item) {
    // Check if stackable and already exists
    if (item.stackable) {
      const existing = G.player.inventory.find(i => i.id === item.id);
      if (existing) {
        existing.count = (existing.count || 1) + (item.count || 1);
        SFX.playSound('pickup_item');
        return true;
      }
    }

    // Check inventory capacity
    if (G.player.inventory.length >= this.maxInventory) {
      // Show "Inventory Full" floating text
      if (window.HUD) {
        HUD.addFloatingText(G.player.x, G.player.y - 16, 'Inventory Full', '#ff4444', 18);
      }
      return false;
    }

    // Add to inventory
    G.player.inventory.push(item);
    SFX.playSound('pickup_item');
    return true;
  },

  removeItem(index) {
    if (index >= 0 && index < G.player.inventory.length) {
      G.player.inventory.splice(index, 1);
    }
  },

  removeItemById(id, count = 1) {
    let remaining = count;
    for (let i = G.player.inventory.length - 1; i >= 0 && remaining > 0; i--) {
      const item = G.player.inventory[i];
      if (item.id === id) {
        if (item.stackable && item.count > 1) {
          const removeAmount = Math.min(item.count, remaining);
          item.count -= removeAmount;
          remaining -= removeAmount;
          if (item.count <= 0) {
            this.removeItem(i);
          }
        } else {
          this.removeItem(i);
          remaining--;
        }
      }
    }
  },

  equipItem(index) {
    const item = G.player.inventory[index];
    if (!item || (item.type !== 'weapon' && item.type !== 'armor')) {
      return;
    }

    const slot = item.slot;
    const currentEquipped = G.player.equipped[slot];

    // Swap items
    if (currentEquipped) {
      G.player.inventory[index] = currentEquipped;
    } else {
      this.removeItem(index);
    }

    G.player.equipped[slot] = item;
    this.recalculateStats();
    SFX.playSound('equip_item');
  },

  unequipItem(slot) {
    const item = G.player.equipped[slot];
    if (!item) return;

    if (this.addItem(item)) {
      G.player.equipped[slot] = null;
      this.recalculateStats();
    }
  },

  useItem(index) {
    const item = G.player.inventory[index];
    if (!item || item.type !== 'consumable') return;

    let consumed = false;

    switch (item.id) {
      case 'health_potion':
        Player.heal(50);
        consumed = true;
        break;

      case 'mana_potion':
        G.player.mana = Math.min(G.player.maxMana, G.player.mana + 30);
        consumed = true;
        break;

      case 'stamina_tonic':
        G.player.stamina = Math.min(G.player.maxStamina, G.player.stamina + 50);
        consumed = true;
        break;

      case 'antidote':
        // Remove poison and burn effects
        G.player.statusEffects = G.player.statusEffects.filter(e => e.type !== 'poison' && e.type !== 'burn');
        consumed = true;
        break;

      case 'fire_bomb':
        // AoE fire damage at cursor (or player position if no cursor)
        const bombX = Input.mouse ? Input.mouse.worldX : G.player.x;
        const bombY = Input.mouse ? Input.mouse.worldY : G.player.y;
        this.createAoEDamage(bombX, bombY, 64, 30, ELEMENT.FIRE);
        if (window.FX) FX.fire(bombX, bombY);
        SFX.playSound('explosion');
        consumed = true;
        break;

      case 'ice_shard':
        // Freeze nearby enemies for 2s
        if (window.EnemyManager) {
          const nearbyEnemies = EnemyManager.enemies.filter(e => {
            const dist = Math.hypot(e.x - G.player.x, e.y - G.player.y);
            return dist < 96;
          });
          nearbyEnemies.forEach(enemy => {
            enemy.statusEffects = enemy.statusEffects || [];
            enemy.statusEffects.push({ type: 'freeze', duration: 2.0 });
          });
          if (window.FX) FX.ice(G.player.x, G.player.y);
        }
        consumed = true;
        break;

      case 'scroll_of_return':
        // Teleport to last campfire
        if (G.lastCampfire) {
          G.player.x = G.lastCampfire.x;
          G.player.y = G.lastCampfire.y;
          if (window.FX) FX.magic(G.player.x, G.player.y, '#00ffff');
          SFX.playSound('teleport');
          consumed = true;
        }
        break;

      case 'elixir_of_power':
        // +25% damage for 30s
        G.player.statusEffects = G.player.statusEffects || [];
        G.player.statusEffects.push({ type: 'power', duration: 30.0, mult: 1.25 });
        if (window.FX) FX.magic(G.player.x, G.player.y, '#ff00ff');
        consumed = true;
        break;
    }

    if (consumed) {
      SFX.playSound('use_item');
      if (item.stackable && item.count > 1) {
        item.count--;
      } else {
        this.removeItem(index);
      }
    }
  },

  createAoEDamage(x, y, radius, damage, element) {
    // Apply damage to all enemies in radius
    if (!window.EnemyManager) return;

    EnemyManager.enemies.forEach(enemy => {
      const dist = Math.hypot(enemy.x - x, enemy.y - y);
      if (dist < radius) {
        if (window.Combat) {
          Combat.damageEnemy(enemy, damage, element);
        } else {
          enemy.hp -= damage;
        }
      }
    });

    if (window.FX) {
      FX.explosion(x, y, radius, element === ELEMENT.FIRE ? '#ff4400' : '#4488ff');
    }
    if (window.Camera) {
      Camera.shake(5, 0.3);
    }
  },

  dropItem(index) {
    const item = G.player.inventory[index];
    if (!item) return;

    this.groundItems.push({
      item: item,
      x: G.player.x,
      y: G.player.y,
      bobTimer: 0
    });

    this.removeItem(index);
    SFX.playSound('drop_item');
  },

  getGroundItems() {
    return this.groundItems.filter(gi => {
      const dist = Math.hypot(gi.x - G.player.x, gi.y - G.player.y);
      return dist < TILE_SIZE * 2;
    });
  },

  pickupNearby() {
    for (let i = this.groundItems.length - 1; i >= 0; i--) {
      const gi = this.groundItems[i];
      const dist = Math.hypot(gi.x - G.player.x, gi.y - G.player.y);
      if (dist < TILE_SIZE) {
        if (this.addItem(gi.item)) {
          this.groundItems.splice(i, 1);
        }
      }
    }
  },

  spawnLoot(x, y, floor, rarityBoost = 0) {
    if (!window.LOOT_TABLES) return;

    const table = LOOT_TABLES[Math.min(floor, LOOT_TABLES.length - 1)];
    const numItems = Util.randInt(table.minItems, table.maxItems);

    for (let i = 0; i < numItems; i++) {
      let item = null;
      const roll = Math.random();

      if (roll < table.weaponChance) {
        item = generateWeapon(floor, rarityBoost);
      } else if (roll < table.weaponChance + table.armorChance) {
        item = this.generateArmor(floor, rarityBoost);
      } else if (roll < table.weaponChance + table.armorChance + table.consumableChance) {
        item = this.generateConsumable();
      } else {
        item = this.generateMaterial(floor);
      }

      if (item) {
        const offsetX = Util.randFloat(-16, 16);
        const offsetY = Util.randFloat(-16, 16);
        this.groundItems.push({
          item: item,
          x: x + offsetX,
          y: y + offsetY,
          bobTimer: Math.random() * Math.PI * 2
        });

        if (window.FX) {
          FX.loot(x + offsetX, y + offsetY, item.rarity);
        }
      }
    }
  },

  generateArmor(floor, rarityBoost = 0) {
    const slots = ['helmet', 'chest', 'legs', 'boots', 'amulet', 'ring'];
    const slot = Util.pick(slots);
    const armorType = ARMOR_TYPES[slot] ? Util.pick(ARMOR_TYPES[slot]) : null;
    if (!armorType) return null;

    const rarity = Math.min(4, Math.max(0, Math.floor(floor / 5) + Util.randInt(-1, 1) + rarityBoost));

    return {
      id: `${armorType.id}_${Date.now()}_${Math.random()}`,
      name: `${Object.keys(RARITY)[rarity]} ${armorType.name}`,
      type: 'armor',
      slot: slot,
      rarity: rarity,
      stats: {
        defense: armorType.defense * (1 + rarity * 0.3),
        hp: armorType.hp || 0,
        mana: armorType.mana || 0,
        stamina: armorType.stamina || 0
      },
      element: armorType.element || ELEMENT.PHYSICAL,
      description: armorType.description,
      spriteColor: RARITY_COLORS[rarity],
      stackable: false
    };
  },

  generateConsumable() {
    const consumable = Util.pick(CONSUMABLES);
    return {
      id: consumable.id,
      name: consumable.name,
      type: 'consumable',
      rarity: consumable.rarity,
      description: consumable.description,
      spriteColor: consumable.color,
      stackable: true,
      count: 1
    };
  },

  generateMaterial(floor) {
    const material = Util.pick(MATERIALS);
    return {
      id: material.id,
      name: material.name,
      type: 'material',
      rarity: material.rarity,
      description: material.description,
      spriteColor: material.color,
      stackable: true,
      count: Util.randInt(1, 3)
    };
  },

  recalculateStats() {
    // Reset to base stats
    const base = {
      defense: 5,
      damage: 10,
      maxHp: 100,
      maxMana: 50,
      maxStamina: 100,
      fireResist: 0,
      iceResist: 0,
      lightningResist: 0,
      darkResist: 0,
      poisonResist: 0
    };

    // Add equipment bonuses
    for (const slot in G.player.equipped) {
      const item = G.player.equipped[slot];
      if (item && item.stats) {
        base.defense += item.stats.defense || 0;
        base.damage += item.stats.damage || 0;
        base.maxHp += item.stats.hp || 0;
        base.maxMana += item.stats.mana || 0;
        base.maxStamina += item.stats.stamina || 0;
        base.fireResist += item.stats.fireResist || 0;
        base.iceResist += item.stats.iceResist || 0;
        base.lightningResist += item.stats.lightningResist || 0;
        base.darkResist += item.stats.darkResist || 0;
        base.poisonResist += item.stats.poisonResist || 0;
      }
    }

    // Apply to player
    G.player.defense = base.defense;
    G.player.damage = base.damage;
    G.player.maxHp = base.maxHp;
    G.player.maxMana = base.maxMana;
    G.player.maxStamina = base.maxStamina;
    G.player.fireResist = base.fireResist;
    G.player.iceResist = base.iceResist;
    G.player.lightningResist = base.lightningResist;
    G.player.darkResist = base.darkResist;
    G.player.poisonResist = base.poisonResist;

    // Cap HP/mana/stamina to new max
    G.player.hp = Math.min(G.player.hp, G.player.maxHp);
    G.player.mana = Math.min(G.player.mana, G.player.maxMana);
    G.player.stamina = Math.min(G.player.stamina, G.player.maxStamina);
  },

  sortInventory(mode = 'rarity') {
    if (mode === 'rarity') {
      G.player.inventory.sort((a, b) => b.rarity - a.rarity);
    } else if (mode === 'type') {
      G.player.inventory.sort((a, b) => a.type.localeCompare(b.type));
    } else if (mode === 'name') {
      G.player.inventory.sort((a, b) => a.name.localeCompare(b.name));
    }
  },

  renderGroundItems(ctx, camera) {
    const time = Date.now() / 1000;

    this.groundItems.forEach(gi => {
      gi.bobTimer += 0.05;
      const bobOffset = Math.sin(gi.bobTimer) * 4;

      const screenX = gi.x - camera.x;
      const screenY = gi.y - camera.y + bobOffset;

      // Skip if off-screen
      if (!Camera.isOnScreen(gi.x, gi.y, 32, 32)) return;

      // Rarity glow underneath
      const glowColor = RARITY_COLORS[gi.item.rarity];
      ctx.fillStyle = Util.rgba(glowColor, 0.3);
      ctx.beginPath();
      ctx.arc(screenX, screenY + 6, 10, 0, Math.PI * 2);
      ctx.fill();

      // Item sprite (colored square)
      ctx.fillStyle = gi.item.spriteColor || glowColor;
      ctx.fillRect(screenX - 6, screenY - 6, 12, 12);

      // Border
      ctx.strokeStyle = glowColor;
      ctx.lineWidth = 1;
      ctx.strokeRect(screenX - 6, screenY - 6, 12, 12);

      // Proximity label
      const dist = Math.hypot(gi.x - G.player.x, gi.y - G.player.y);
      if (dist < TILE_SIZE * 2) {
        ctx.fillStyle = '#ffffff';
        ctx.font = '10px monospace';
        ctx.textAlign = 'center';
        ctx.fillText(gi.item.name, screenX, screenY - 16);
      }
    });
  }
};
