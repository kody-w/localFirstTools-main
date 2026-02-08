// combat/player.js - Player entity with movement, dodge-roll, stamina, parry, iframes
// Global Player object for Depths of the Abyss

const Player = {
  init() {
    G.player = {
      x: 0, y: 0,
      vx: 0, vy: 0,
      w: 24, h: 24,
      hp: PLAYER_DEFAULTS.hp,
      maxHp: PLAYER_DEFAULTS.maxHp,
      mana: PLAYER_DEFAULTS.mana,
      maxMana: PLAYER_DEFAULTS.maxMana,
      stamina: PLAYER_DEFAULTS.stamina,
      maxStamina: PLAYER_DEFAULTS.maxStamina,
      speed: PLAYER_DEFAULTS.speed,
      attackDmg: PLAYER_DEFAULTS.attackDmg,
      defense: PLAYER_DEFAULTS.defense,
      critChance: PLAYER_DEFAULTS.critChance,
      critMultiplier: PLAYER_DEFAULTS.critMultiplier,
      level: 1,
      xp: 0,
      skillPoints: 0,
      statPoints: 0,
      str: 5, dex: 5, int: 5, vit: 5,
      facing: DIR.DOWN,
      // Combat state
      attacking: false,
      attackTimer: 0,
      attackCooldown: 0,
      dodging: false,
      dodgeTimer: 0,
      dodgeCooldown: 0,
      dodgeDir: 0,
      parrying: false,
      parryTimer: 0,
      parryCooldown: 0,
      parrySuccess: false,
      invincible: false,
      iframeTimer: 0,
      hitFlash: 0,
      knockbackX: 0, knockbackY: 0, knockbackTimer: 0,
      // Equipment
      weapon: generateWeapon(1, RARITY.COMMON),
      armor: {head:null,chest:null,legs:null,boots:null,gloves:null,ring:null,amulet:null},
      // Abilities
      unlockedAbilities: [],
      equippedAbilities: [null,null,null,null],
      abilityCooldowns: {},
      // Status effects
      statusEffects: [],
      // Progression
      inventory: [],
      maxInventory: 20,
      materials: {},
      gold: 0,
      // Stats
      totalDamageDealt: 0,
      totalKills: 0
    };
  },

  update(dt) {
    const p = G.player;

    // Handle dodge-roll movement
    if (p.dodging) {
      // Move at 3x speed during dodge
      const dodgeSpeed = p.speed * 3;
      const dx = DIR_DX[p.dodgeDir] * dodgeSpeed * dt;
      const dy = DIR_DY[p.dodgeDir] * dodgeSpeed * dt;

      // Check tile collision before moving
      if (this.canMoveTo(p.x + dx, p.y)) p.x += dx;
      if (this.canMoveTo(p.x, p.y + dy)) p.y += dy;

      p.dodgeTimer -= dt;
      if (p.dodgeTimer <= 0) {
        p.dodging = false;
        p.invincible = false;
      }
    }
    // Handle knockback
    else if (p.knockbackTimer > 0) {
      p.x += p.knockbackX * dt;
      p.y += p.knockbackY * dt;
      p.knockbackTimer -= dt;
      if (p.knockbackTimer <= 0) {
        p.knockbackX = 0;
        p.knockbackY = 0;
      }
    }
    // Normal movement
    else {
      const movement = Input.getMovement();
      const moveX = movement.x * p.speed * dt;
      const moveY = movement.y * p.speed * dt;

      // Check tile collision and move
      if (moveX !== 0 && this.canMoveTo(p.x + moveX, p.y)) {
        p.x += moveX;
      }
      if (moveY !== 0 && this.canMoveTo(p.x, p.y + moveY)) {
        p.y += moveY;
      }

      // Update facing direction
      if (movement.x !== 0 || movement.y !== 0) {
        if (Math.abs(movement.x) > Math.abs(movement.y)) {
          p.facing = movement.x > 0 ? DIR.RIGHT : DIR.LEFT;
        } else {
          p.facing = movement.y > 0 ? DIR.DOWN : DIR.UP;
        }
      }

      // Stamina regen - faster when standing still
      const staminaRegen = (movement.x === 0 && movement.y === 0) ? 3.0 : 1.0;
      p.stamina = Math.min(p.maxStamina, p.stamina + staminaRegen * dt);
    }

    // Mana regeneration
    p.mana = Math.min(p.maxMana, p.mana + 0.5 * dt);

    // Update attack timers
    if (p.attacking) {
      p.attackTimer -= dt;
      if (p.attackTimer <= 0) {
        p.attacking = false;
      }
    }
    if (p.attackCooldown > 0) {
      p.attackCooldown -= dt;
    }

    // Update dodge cooldown
    if (p.dodgeCooldown > 0) {
      p.dodgeCooldown -= dt;
    }

    // Update parry window
    if (p.parrying) {
      p.parryTimer -= dt;
      if (p.parryTimer <= 0) {
        p.parrying = false;
        p.parrySuccess = false;
      }
    }
    if (p.parryCooldown > 0) {
      p.parryCooldown -= dt;
    }

    // Update invincibility frames
    if (p.invincible && !p.dodging) {
      p.iframeTimer -= dt;
      if (p.iframeTimer <= 0) {
        p.invincible = false;
      }
    }

    // Update status effects
    this.updateStatusEffects(dt);

    // Decay hit flash
    if (p.hitFlash > 0) {
      p.hitFlash -= dt * 5;
      if (p.hitFlash < 0) p.hitFlash = 0;
    }

    // Update combo timer - combo resets after 3 seconds
    if (G.comboTimer > 0) {
      G.comboTimer -= dt;
      if (G.comboTimer <= 0) {
        G.combo = 0;
      }
    }

    // Check tile interactions
    this.checkTileInteractions();
  },

  canMoveTo(x, y) {
    const tileX = Math.floor(x / TILE_SIZE);
    const tileY = Math.floor(y / TILE_SIZE);
    return TileMap.isWalkable(tileX, tileY);
  },

  attack() {
    const p = G.player;

    // Check cooldown
    if (p.attackCooldown > 0) return false;

    // Check weapon
    if (!p.weapon) return false;

    // Check stamina cost
    const staminaCost = p.weapon.staminaCost || 10;
    if (p.stamina < staminaCost) return false;

    // Deduct stamina
    p.stamina -= staminaCost;

    // Set attack state
    p.attacking = true;
    p.attackTimer = p.weapon.attackSpeed || 0.3;
    p.attackCooldown = p.weapon.attackSpeed || 0.3;

    // Play weapon swing sound
    SFX.playSFX('sword_swing');

    // Trigger weapon system
    Weapons.startAttack(p, p.weapon);

    return true;
  },

  dodge() {
    const p = G.player;

    // Check stamina
    const dodgeCost = 20;
    if (p.stamina < dodgeCost) return false;

    // Check cooldown
    if (p.dodgeCooldown > 0) return false;

    // Get movement direction or use facing if standing still
    const movement = Input.getMovement();
    let dodgeDir = p.facing;

    if (movement.x !== 0 || movement.y !== 0) {
      if (Math.abs(movement.x) > Math.abs(movement.y)) {
        dodgeDir = movement.x > 0 ? DIR.RIGHT : DIR.LEFT;
      } else {
        dodgeDir = movement.y > 0 ? DIR.DOWN : DIR.UP;
      }
    }

    // Deduct stamina
    p.stamina -= dodgeCost;

    // Set dodge state
    p.dodging = true;
    p.dodgeTimer = 0.3;
    p.dodgeCooldown = 0.8;
    p.dodgeDir = dodgeDir;

    // Grant invincibility frames during dodge
    p.invincible = true;

    // Play dodge roll sound
    SFX.playSFX('dodge_roll');

    return true;
  },

  parry() {
    const p = G.player;

    // Check cooldown
    if (p.parryCooldown > 0) return false;

    // Check stamina
    const parryCost = 15;
    if (p.stamina < parryCost) return false;

    // Deduct stamina
    p.stamina -= parryCost;

    // Set parry window (0.15s)
    p.parrying = true;
    p.parryTimer = 0.15;
    p.parryCooldown = 1.5;
    p.parrySuccess = false;

    return true;
  },

  takeDamage(amount, element, sourceX, sourceY) {
    const p = G.player;

    // Check invincibility (iframes or dodge)
    if (p.invincible) return;

    // Check parry window
    if (p.parrying) {
      p.parrySuccess = true;
      p.parrying = false;

      // Successful parry - restore stamina and no damage
      p.stamina = Math.min(p.maxStamina, p.stamina + 20);

      // Play parry sound
      SFX.playSFX('parry_success');

      // Spawn floating text
      Combat.spawnFloatingText(p.x, p.y - 20, 'PARRY!', '#FFD700');

      // Camera shake
      Camera.shake(8, 0.2);

      return;
    }

    // Apply defense reduction
    let finalDamage = amount - p.defense;

    // Apply element resistance from armor
    const resistance = this.getElementResistance(element);
    finalDamage *= (1 - resistance);

    // Minimum damage
    finalDamage = Math.max(1, Math.floor(finalDamage));

    // Apply damage
    p.hp -= finalDamage;

    // Flash effect
    p.hitFlash = 0.15;

    // Camera shake
    Camera.shake(5, 0.15);

    // Knockback from source
    if (sourceX !== undefined && sourceY !== undefined) {
      const angle = Util.angle(sourceX, sourceY, p.x, p.y);
      const knockbackForce = 150;
      p.knockbackX = Math.cos(angle) * knockbackForce;
      p.knockbackY = Math.sin(angle) * knockbackForce;
      p.knockbackTimer = 0.15;
    }

    // Grant brief iframes after being hit
    p.invincible = true;
    p.iframeTimer = 0.3;

    // Play hurt sound
    SFX.playSFX('player_hurt');

    // Spawn damage text
    Combat.spawnFloatingText(p.x, p.y - 20, '-' + finalDamage, '#FF4444');

    // Check death
    if (p.hp <= 0) {
      p.hp = 0;
      this.die();
    }
  },

  heal(amount) {
    const p = G.player;
    const oldHp = p.hp;
    p.hp = Math.min(p.maxHp, p.hp + amount);
    const actualHeal = p.hp - oldHp;

    if (actualHeal > 0) {
      SFX.playSFX('player_heal');
      Combat.spawnFloatingText(p.x, p.y - 20, '+' + actualHeal, '#44FF44');
    }
  },

  addXP(amount) {
    const p = G.player;
    p.xp += amount;

    // Check level up
    const xpNeeded = this.getXPForLevel(p.level + 1);
    if (p.xp >= xpNeeded) {
      p.xp -= xpNeeded;
      p.level++;
      p.skillPoints += 2;
      p.statPoints += 5;

      // Restore HP and mana on level up
      p.hp = p.maxHp;
      p.mana = p.maxMana;

      // Play level up sound
      SFX.playSFX('player_levelup');

      // Camera shake
      Camera.shake(10, 0.3);

      // Spawn text
      Combat.spawnFloatingText(p.x, p.y - 30, 'LEVEL UP!', '#FFD700');
    }
  },

  getXPForLevel(level) {
    return Math.floor(100 * Math.pow(1.5, level - 1));
  },

  die() {
    const p = G.player;
    G.gameState = STATE.DEATH;
    SFX.playSFX('player_death');
    Camera.shake(20, 0.5);
  },

  updateStatusEffects(dt) {
    const p = G.player;

    for (let i = p.statusEffects.length - 1; i >= 0; i--) {
      const effect = p.statusEffects[i];
      effect.timer += dt;

      // Tick damage effects
      if ((effect.type === 'poison' || effect.type === 'burn' || effect.type === 'bleed') &&
          effect.timer >= effect.tickInterval) {
        p.hp -= effect.tickDamage;
        effect.timer = 0;
        Combat.spawnFloatingText(p.x, p.y - 10, '-' + effect.tickDamage, '#884488');

        if (p.hp <= 0) {
          p.hp = 0;
          this.die();
        }
      }

      // Remove expired effects
      effect.duration -= dt;
      if (effect.duration <= 0) {
        p.statusEffects.splice(i, 1);
      }
    }
  },

  getElementResistance(element) {
    const p = G.player;
    let resistance = 0;

    // Sum resistance from equipped armor
    for (let slot in p.armor) {
      const item = p.armor[slot];
      if (item && item.resistance && item.resistance[element]) {
        resistance += item.resistance[element];
      }
    }

    return Math.min(0.75, resistance); // Cap at 75%
  },

  checkTileInteractions() {
    const p = G.player;
    const tileX = Math.floor(p.x / TILE_SIZE);
    const tileY = Math.floor(p.y / TILE_SIZE);

    // Check for stairs, campfires, chests, traps, etc.
    // This will be implemented in coordination with tilemap.js
  },

  render(ctx, camera) {
    const p = G.player;
    const screenPos = Camera.worldToScreen(p.x, p.y);

    ctx.save();

    // Draw shadow
    ctx.fillStyle = 'rgba(0, 0, 0, 0.3)';
    ctx.beginPath();
    ctx.ellipse(screenPos.x, screenPos.y + 8, 10, 4, 0, 0, Math.PI * 2);
    ctx.fill();

    // Apply transparency during dodge
    if (p.dodging) {
      ctx.globalAlpha = 0.5;
    }

    // Flash white when hit
    if (p.hitFlash > 0) {
      ctx.fillStyle = '#FFFFFF';
    } else {
      // Body color based on armor rarity
      const armorColor = this.getArmorColor();
      ctx.fillStyle = armorColor;
    }

    // Draw body (rectangle)
    ctx.fillRect(screenPos.x - 8, screenPos.y - 12, 16, 20);

    // Draw head (circle)
    ctx.beginPath();
    ctx.arc(screenPos.x, screenPos.y - 16, 6, 0, Math.PI * 2);
    ctx.fill();

    // Draw weapon
    if (p.weapon) {
      this.renderWeapon(ctx, screenPos.x, screenPos.y);
    }

    // Draw attack swing arc
    if (p.attacking) {
      Weapons.renderSwing(ctx, p, camera);
    }

    // Draw parry indicator
    if (p.parrying) {
      ctx.strokeStyle = '#FFD700';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(screenPos.x, screenPos.y, 20, 0, Math.PI * 2);
      ctx.stroke();
    }

    ctx.restore();
  },

  renderWeapon(ctx, x, y) {
    const p = G.player;
    const weapon = p.weapon;

    ctx.save();

    // Weapon color based on rarity
    const rarityColors = {
      [RARITY.COMMON]: '#888888',
      [RARITY.UNCOMMON]: '#44FF44',
      [RARITY.RARE]: '#4444FF',
      [RARITY.EPIC]: '#AA44FF',
      [RARITY.LEGENDARY]: '#FFAA00'
    };
    ctx.strokeStyle = rarityColors[weapon.rarity] || '#888888';
    ctx.lineWidth = 3;

    // Draw weapon based on facing
    ctx.beginPath();
    switch(p.facing) {
      case DIR.DOWN:
        ctx.moveTo(x + 8, y);
        ctx.lineTo(x + 8, y + 12);
        break;
      case DIR.UP:
        ctx.moveTo(x - 8, y - 10);
        ctx.lineTo(x - 8, y - 22);
        break;
      case DIR.LEFT:
        ctx.moveTo(x - 10, y - 5);
        ctx.lineTo(x - 18, y - 5);
        break;
      case DIR.RIGHT:
        ctx.moveTo(x + 10, y - 5);
        ctx.lineTo(x + 18, y - 5);
        break;
    }
    ctx.stroke();

    ctx.restore();
  },

  getArmorColor() {
    const p = G.player;

    // Use highest rarity equipped armor for color
    let highestRarity = RARITY.COMMON;
    for (let slot in p.armor) {
      const item = p.armor[slot];
      if (item && item.rarity > highestRarity) {
        highestRarity = item.rarity;
      }
    }

    const rarityColors = {
      [RARITY.COMMON]: '#4488AA',
      [RARITY.UNCOMMON]: '#44AA88',
      [RARITY.RARE]: '#4466AA',
      [RARITY.EPIC]: '#8844AA',
      [RARITY.LEGENDARY]: '#AA8844'
    };

    return rarityColors[highestRarity] || '#4488AA';
  },

  getAttackHitbox() {
    const p = G.player;

    if (!p.attacking || !p.weapon) return null;

    const range = p.weapon.range || 40;
    const arc = p.weapon.arc || 90;

    // Return hitbox rectangle based on facing and weapon range
    const hitbox = { x: p.x, y: p.y, w: range, h: range };

    switch(p.facing) {
      case DIR.DOWN:
        hitbox.y = p.y + 10;
        hitbox.x = p.x - range / 2;
        break;
      case DIR.UP:
        hitbox.y = p.y - range - 10;
        hitbox.x = p.x - range / 2;
        break;
      case DIR.LEFT:
        hitbox.x = p.x - range - 10;
        hitbox.y = p.y - range / 2;
        break;
      case DIR.RIGHT:
        hitbox.x = p.x + 10;
        hitbox.y = p.y - range / 2;
        break;
    }

    return hitbox;
  }
};
