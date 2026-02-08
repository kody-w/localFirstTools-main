// combat/abilities.js - Runtime ability casting system
// Global AbilitySystem object for Depths of the Abyss

const AbilitySystem = {
  activeEffects: [], // Active buffs, debuffs, channeled abilities
  cooldowns: {},

  cast(abilityId, player) {
    const p = player;

    // Get ability definition
    const abilityDef = ABILITY_DEFS[abilityId];
    if (!abilityDef) return false;

    // Check cooldown
    if (this.cooldowns[abilityId] > 0) return false;

    // Check mana cost
    if (p.mana < abilityDef.manaCost) return false;

    // Check stamina cost
    if (abilityDef.staminaCost && p.stamina < abilityDef.staminaCost) return false;

    // Deduct costs
    p.mana -= abilityDef.manaCost;
    if (abilityDef.staminaCost) p.stamina -= abilityDef.staminaCost;

    // Set cooldown
    this.cooldowns[abilityId] = abilityDef.cooldown;

    // Execute ability
    this.executeAbility(abilityId, abilityDef, player);

    // Play cast sound
    SFX.playSFX('ability_cast');

    return true;
  },

  executeAbility(abilityId, def, player) {
    const p = player;

    // Dispatch to specific ability handlers
    switch(abilityId) {
      // WARRIOR ABILITIES
      case 'powerStrike':
        this.powerStrike(p);
        break;
      case 'ironSkin':
        this.ironSkin(p);
        break;
      case 'berserkerRage':
        this.berserkerRage(p);
        break;
      case 'whirlwind':
        this.whirlwind(p);
        break;
      case 'shieldBash':
        this.shieldBash(p);
        break;
      case 'warCry':
        this.warCry(p);
        break;
      case 'earthquake':
        this.earthquake(p);
        break;

      // MAGE ABILITIES
      case 'fireball':
        this.fireball(p);
        break;
      case 'frostShield':
        this.frostShield(p);
        break;
      case 'manaSurge':
        this.manaSurge(p);
        break;
      case 'lightningChain':
        this.lightningChain(p);
        break;
      case 'teleport':
        this.teleport(p);
        break;
      case 'arcaneMissile':
        this.arcaneMissile(p);
        break;
      case 'meteorStrike':
        this.meteorStrike(p);
        break;
      case 'timeWarp':
        this.timeWarp(p);
        break;

      // ROGUE ABILITIES
      case 'backstab':
        this.backstab(p);
        break;
      case 'poisonBlade':
        this.poisonBlade(p);
        break;
      case 'shadowStep':
        this.shadowStep(p);
        break;
      case 'fanOfKnives':
        this.fanOfKnives(p);
        break;
      case 'smokeBomb':
        this.smokeBomb(p);
        break;
      case 'deathMark':
        this.deathMark(p);
        break;
      case 'shadowClone':
        this.shadowClone(p);
        break;
    }
  },

  // WARRIOR ABILITIES
  powerStrike(player) {
    this.addBuff(player, {
      type: 'powerStrike',
      duration: 3.0,
      damageMultiplier: 1.5
    });
    Combat.spawnFloatingText(player.x, player.y - 20, 'POWER!', '#FF4444');
  },

  ironSkin(player) {
    this.addBuff(player, {
      type: 'ironSkin',
      duration: 5.0,
      damageReduction: 0.5
    });
    Combat.spawnFloatingText(player.x, player.y - 20, 'IRON SKIN!', '#888888');
  },

  berserkerRage(player) {
    if (player.hp / player.maxHp > 0.3) return;

    this.addBuff(player, {
      type: 'berserkerRage',
      duration: 8.0,
      speedMultiplier: 1.5,
      damageMultiplier: 1.3
    });
    Combat.spawnFloatingText(player.x, player.y - 20, 'RAGE!', '#FF0000');
    Camera.shake(10, 0.3);
  },

  whirlwind(player) {
    const radius = TILE_SIZE * 3;

    // Hit all enemies in radius
    G.enemies.forEach(enemy => {
      const dist = Util.dist(player.x, player.y, enemy.x, enemy.y);
      if (dist <= radius) {
        const damage = player.weapon.damage * 0.8;
        EnemyAI.takeDamage(enemy, damage, ELEMENT.PHYSICAL, player.x - enemy.x, player.y - enemy.y);
      }
    });

    Camera.shake(12, 0.4);
    SFX.playSFX('whirlwind');
  },

  shieldBash(player) {
    // Find enemy in front
    const range = TILE_SIZE * 2;
    const facing = player.facing;

    G.enemies.forEach(enemy => {
      const dist = Util.dist(player.x, player.y, enemy.x, enemy.y);
      if (dist <= range) {
        // Check if in front
        const dx = enemy.x - player.x;
        const dy = enemy.y - player.y;

        let inFront = false;
        if (facing === DIR.RIGHT && dx > 0) inFront = true;
        if (facing === DIR.LEFT && dx < 0) inFront = true;
        if (facing === DIR.DOWN && dy > 0) inFront = true;
        if (facing === DIR.UP && dy < 0) inFront = true;

        if (inFront) {
          Combat.applyStatusEffect(enemy, {
            type: 'stun',
            duration: 2.0,
            tickDamage: 0,
            tickInterval: 0
          });
          Combat.spawnFloatingText(enemy.x, enemy.y - 20, 'STUNNED', '#FFD700');
        }
      }
    });

    SFX.playSFX('shield_bash');
  },

  warCry(player) {
    const radius = TILE_SIZE * 4;

    G.enemies.forEach(enemy => {
      const dist = Util.dist(player.x, player.y, enemy.x, enemy.y);
      if (dist <= radius) {
        enemy.state = 'flee';
        enemy.stateTimer = 3.0;
        Combat.spawnFloatingText(enemy.x, enemy.y - 20, 'FEARED', '#AA44AA');
      }
    });

    Camera.shake(15, 0.4);
    SFX.playSFX('war_cry');
  },

  earthquake(player) {
    const radius = TILE_SIZE * 5;
    const damage = player.weapon.damage * 2.5;

    G.enemies.forEach(enemy => {
      const dist = Util.dist(player.x, player.y, enemy.x, enemy.y);
      if (dist <= radius) {
        EnemyAI.takeDamage(enemy, damage, ELEMENT.PHYSICAL, player.x - enemy.x, player.y - enemy.y);
      }
    });

    Camera.shake(20, 0.5);
    SFX.playSFX('earthquake');
  },

  // MAGE ABILITIES
  fireball(player) {
    const aim = Input.getAim();
    const angle = Math.atan2(aim.y, aim.x);

    const projectile = {
      x: player.x,
      y: player.y,
      vx: Math.cos(angle) * 300,
      vy: Math.sin(angle) * 300,
      damage: 30 + player.int,
      element: ELEMENT.FIRE,
      speed: 300,
      lifetime: 2.0,
      owner: 'player',
      sprite: 'fireball',
      explodeRadius: TILE_SIZE * 1.5
    };

    G.projectiles.push(projectile);
    SFX.playSFX('fireball_cast');
  },

  frostShield(player) {
    this.addBuff(player, {
      type: 'frostShield',
      duration: 10.0,
      absorb: 50,
      slowAttackers: true
    });
    Combat.spawnFloatingText(player.x, player.y - 20, 'FROST SHIELD!', '#4444FF');
  },

  manaSurge(player) {
    this.addBuff(player, {
      type: 'manaSurge',
      duration: 10.0,
      manaRegenMultiplier: 2.0
    });
    Combat.spawnFloatingText(player.x, player.y - 20, 'MANA SURGE!', '#4488FF');
  },

  lightningChain(player) {
    // Find nearest 3 enemies
    const targets = this.findNearestEnemies(player, 3, TILE_SIZE * 6);

    targets.forEach((enemy, index) => {
      const damage = (25 + player.int) * Math.pow(0.8, index); // Reduced damage per chain
      setTimeout(() => {
        EnemyAI.takeDamage(enemy, damage, ELEMENT.LIGHTNING, 0, 0);
        SFX.playSFX('lightning_strike');
      }, index * 100);
    });

    Combat.spawnFloatingText(player.x, player.y - 20, 'CHAIN LIGHTNING!', '#FFFF00');
  },

  teleport(player) {
    const distance = TILE_SIZE * 5;
    const facing = player.facing;

    let dx = 0, dy = 0;
    switch(facing) {
      case DIR.RIGHT: dx = distance; break;
      case DIR.LEFT: dx = -distance; break;
      case DIR.DOWN: dy = distance; break;
      case DIR.UP: dy = -distance; break;
    }

    // Check if destination is walkable
    const destX = player.x + dx;
    const destY = player.y + dy;

    if (TileMap.isWalkable(Math.floor(destX / TILE_SIZE), Math.floor(destY / TILE_SIZE))) {
      player.x = destX;
      player.y = destY;
      SFX.playSFX('teleport');
      Combat.spawnFloatingText(player.x, player.y - 20, 'BLINK!', '#AA44FF');
    }
  },

  arcaneMissile(player) {
    const targets = this.findNearestEnemies(player, 3, TILE_SIZE * 8);

    targets.forEach((enemy, index) => {
      setTimeout(() => {
        const angle = Util.angle(player.x, player.y, enemy.x, enemy.y);
        const projectile = {
          x: player.x,
          y: player.y,
          vx: Math.cos(angle) * 250,
          vy: Math.sin(angle) * 250,
          damage: 15 + player.int * 0.5,
          element: ELEMENT.PHYSICAL,
          speed: 250,
          lifetime: 3.0,
          owner: 'player',
          sprite: 'arcane_missile',
          homing: enemy
        };
        G.projectiles.push(projectile);
      }, index * 150);
    });

    SFX.playSFX('arcane_cast');
  },

  meteorStrike(player) {
    const aim = Input.getAim();
    const targetX = player.x + aim.x * TILE_SIZE * 3;
    const targetY = player.y + aim.y * TILE_SIZE * 3;

    // Delayed AoE
    const aoe = {
      x: targetX,
      y: targetY,
      radius: TILE_SIZE * 3,
      damage: 60 + player.int * 2,
      element: ELEMENT.FIRE,
      owner: 'player',
      lifetime: 0.5,
      timer: 0,
      delay: 1.5,
      telegraph: true
    };

    if (!G.aoeEffects) G.aoeEffects = [];
    G.aoeEffects.push(aoe);

    SFX.playSFX('meteor_incoming');
  },

  timeWarp(player) {
    G.enemies.forEach(enemy => {
      enemy.timeWarpSlow = 0.3; // Move at 30% speed
      enemy.timeWarpDuration = 5.0;
    });

    Combat.spawnFloatingText(player.x, player.y - 20, 'TIME WARP!', '#8844FF');
    SFX.playSFX('time_warp');
  },

  // ROGUE ABILITIES
  backstab(player) {
    const target = this.findNearestEnemies(player, 1, TILE_SIZE * 4)[0];
    if (!target) return;

    // Teleport behind target
    const angle = Util.angle(player.x, player.y, target.x, target.y);
    player.x = target.x - Math.cos(angle) * TILE_SIZE;
    player.y = target.y - Math.sin(angle) * TILE_SIZE;

    // Deal 3x damage
    const damage = player.weapon.damage * 3;
    EnemyAI.takeDamage(target, damage, ELEMENT.PHYSICAL, 0, 0);

    Combat.spawnFloatingText(target.x, target.y - 20, 'BACKSTAB!', '#FF4444');
    SFX.playSFX('backstab');
  },

  poisonBlade(player) {
    this.addBuff(player, {
      type: 'poisonBlade',
      duration: 10.0,
      attackCount: 5,
      poisonDuration: 3.0
    });
    Combat.spawnFloatingText(player.x, player.y - 20, 'POISON BLADE!', '#44FF44');
  },

  shadowStep(player) {
    const target = this.findNearestEnemies(player, 1, TILE_SIZE * 6)[0];
    if (!target) return;

    // Teleport behind target
    const angle = Util.angle(player.x, player.y, target.x, target.y);
    player.x = target.x - Math.cos(angle) * TILE_SIZE;
    player.y = target.y - Math.sin(angle) * TILE_SIZE;

    SFX.playSFX('shadow_step');
    Combat.spawnFloatingText(player.x, player.y - 20, 'SHADOW STEP!', '#4444AA');
  },

  fanOfKnives(player) {
    const numKnives = 8;
    const facing = player.facing;
    const baseAngle = this.getFacingAngle(facing);

    for (let i = 0; i < numKnives; i++) {
      const spread = 60; // degrees
      const angle = (baseAngle - spread/2 + (i / numKnives) * spread) * Math.PI / 180;

      const projectile = {
        x: player.x,
        y: player.y,
        vx: Math.cos(angle) * 350,
        vy: Math.sin(angle) * 350,
        damage: player.weapon.damage * 0.6,
        element: ELEMENT.PHYSICAL,
        speed: 350,
        lifetime: 1.0,
        owner: 'player',
        sprite: 'knife'
      };

      G.projectiles.push(projectile);
    }

    SFX.playSFX('fan_of_knives');
  },

  smokeBomb(player) {
    const radius = TILE_SIZE * 4;

    G.enemies.forEach(enemy => {
      const dist = Util.dist(player.x, player.y, enemy.x, enemy.y);
      if (dist <= radius) {
        enemy.state = 'idle';
        enemy.alertRadius = 0; // Lose aggro
        setTimeout(() => { enemy.alertRadius = TILE_SIZE * 6; }, 3000);
      }
    });

    this.addBuff(player, {
      type: 'invisible',
      duration: 3.0
    });

    Combat.spawnFloatingText(player.x, player.y - 20, 'SMOKE!', '#666666');
    SFX.playSFX('smoke_bomb');
  },

  deathMark(player) {
    const target = this.findNearestEnemies(player, 1, TILE_SIZE * 6)[0];
    if (!target) return;

    target.deathMark = true;
    target.deathMarkDuration = 5.0;

    Combat.spawnFloatingText(target.x, target.y - 20, 'MARKED!', '#FF0000');
    SFX.playSFX('death_mark');
  },

  shadowClone(player) {
    const clone = {
      x: player.x - TILE_SIZE,
      y: player.y,
      type: 'shadow_clone',
      hp: 1,
      maxHp: 1,
      duration: 8.0,
      isDecoy: true
    };

    G.enemies.push(clone);
    Combat.spawnFloatingText(clone.x, clone.y - 20, 'CLONE!', '#4444AA');
    SFX.playSFX('shadow_clone');
  },

  // Helper methods
  addBuff(entity, buff) {
    this.activeEffects.push({
      entity: entity,
      buff: buff,
      timer: 0
    });
  },

  findNearestEnemies(player, count, maxDistance) {
    const enemies = G.enemies.filter(e => {
      const dist = Util.dist(player.x, player.y, e.x, e.y);
      return dist <= maxDistance && e.hp > 0;
    });

    enemies.sort((a, b) => {
      const distA = Util.dist(player.x, player.y, a.x, a.y);
      const distB = Util.dist(player.x, player.y, b.x, b.y);
      return distA - distB;
    });

    return enemies.slice(0, count);
  },

  getFacingAngle(facing) {
    switch(facing) {
      case DIR.RIGHT: return 0;
      case DIR.DOWN: return 90;
      case DIR.LEFT: return 180;
      case DIR.UP: return 270;
      default: return 0;
    }
  },

  update(dt) {
    // Update cooldowns
    for (let abilityId in this.cooldowns) {
      if (this.cooldowns[abilityId] > 0) {
        this.cooldowns[abilityId] -= dt;
      }
    }

    // Update active effects
    for (let i = this.activeEffects.length - 1; i >= 0; i--) {
      const effect = this.activeEffects[i];
      effect.timer += dt;
      effect.buff.duration -= dt;

      if (effect.buff.duration <= 0) {
        this.activeEffects.splice(i, 1);
      }
    }
  },

  renderEffects(ctx, camera) {
    // Render active ability visuals
    this.activeEffects.forEach(effect => {
      const entity = effect.entity;
      const screenPos = Camera.worldToScreen(entity.x, entity.y);

      // Draw buff auras
      ctx.save();
      ctx.globalAlpha = 0.3;

      switch(effect.buff.type) {
        case 'ironSkin':
          ctx.strokeStyle = '#888888';
          ctx.lineWidth = 3;
          ctx.beginPath();
          ctx.arc(screenPos.x, screenPos.y, 25, 0, Math.PI * 2);
          ctx.stroke();
          break;

        case 'frostShield':
          ctx.strokeStyle = '#4444FF';
          ctx.lineWidth = 3;
          ctx.beginPath();
          ctx.arc(screenPos.x, screenPos.y, 25, 0, Math.PI * 2);
          ctx.stroke();
          break;

        case 'berserkerRage':
          ctx.strokeStyle = '#FF0000';
          ctx.lineWidth = 4;
          ctx.beginPath();
          ctx.arc(screenPos.x, screenPos.y, 30, 0, Math.PI * 2);
          ctx.stroke();
          break;
      }

      ctx.restore();
    });
  }
};
