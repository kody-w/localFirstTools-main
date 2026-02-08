// combat/weapons.js - Weapon mechanics, swing arcs, attack patterns, hit detection
// Global Weapons object for Depths of the Abyss

const Weapons = {
  activeSwings: [], // Track active weapon swings

  startAttack(player, weapon) {
    const swing = {
      player: player,
      weapon: weapon,
      progress: 0,
      duration: weapon.attackSpeed || 0.3,
      type: weapon.type,
      hitEntities: new Set(), // Track entities already hit by this swing
      comboHit: (G.combo % 3) + 1 // 1, 2, or 3
    };

    this.activeSwings.push(swing);

    // Handle ranged weapons (bow, staff)
    if (weapon.type === 'bow' || weapon.type === 'staff') {
      this.fireProjectile(player, weapon);
    }
  },

  updateAttack(player, dt) {
    // Update all active swings
    for (let i = this.activeSwings.length - 1; i >= 0; i--) {
      const swing = this.activeSwings[i];
      swing.progress += dt / swing.duration;

      if (swing.progress >= 1.0) {
        this.activeSwings.splice(i, 1);
      }
    }
  },

  getSwingArc(weapon, facing, progress) {
    // Calculate arc polygon for rendering based on weapon type and progress
    const baseAngle = this.getFacingAngle(facing);
    const arc = weapon.arc || 90;
    const range = weapon.range || 40;

    // Different sweep patterns per weapon type
    let startAngle, endAngle;

    switch(weapon.type) {
      case 'sword':
        // 90° arc sweep
        startAngle = baseAngle - (arc / 2) + (progress * arc);
        endAngle = startAngle + 20;
        break;

      case 'axe':
        // 120° arc, slower
        startAngle = baseAngle - 60 + (progress * 120);
        endAngle = startAngle + 30;
        break;

      case 'dagger':
        // Quick 45° stab
        startAngle = baseAngle - 10;
        endAngle = baseAngle + 10;
        break;

      case 'spear':
        // Narrow 30° thrust
        startAngle = baseAngle - 15;
        endAngle = baseAngle + 15;
        break;

      case 'hammer':
        // 90° arc + ground pound on 3rd hit
        startAngle = baseAngle - 45 + (progress * 90);
        endAngle = startAngle + 25;
        break;

      case 'scythe':
        // 180° sweep
        startAngle = baseAngle - 90 + (progress * 180);
        endAngle = startAngle + 40;
        break;

      default:
        startAngle = baseAngle - (arc / 2) + (progress * arc);
        endAngle = startAngle + 20;
    }

    return {
      startAngle: startAngle * Math.PI / 180,
      endAngle: endAngle * Math.PI / 180,
      range: range
    };
  },

  getFacingAngle(facing) {
    // Convert direction to degrees (0 = right, 90 = down)
    switch(facing) {
      case DIR.RIGHT: return 0;
      case DIR.DOWN: return 90;
      case DIR.LEFT: return 180;
      case DIR.UP: return 270;
      default: return 0;
    }
  },

  renderSwing(ctx, player, camera) {
    const p = player;

    if (!p.attacking || !p.weapon) return;

    const screenPos = Camera.worldToScreen(p.x, p.y);

    // Find active swing for this player
    const swing = this.activeSwings.find(s => s.player === p);
    if (!swing) return;

    const arc = this.getSwingArc(swing.weapon, p.facing, swing.progress);

    ctx.save();

    // Weapon color based on rarity
    const rarityColors = {
      [RARITY.COMMON]: '#888888',
      [RARITY.UNCOMMON]: '#44FF44',
      [RARITY.RARE]: '#4444FF',
      [RARITY.EPIC]: '#AA44FF',
      [RARITY.LEGENDARY]: '#FFAA00'
    };

    const color = rarityColors[swing.weapon.rarity] || '#888888';

    // Draw swing arc trail
    ctx.strokeStyle = color;
    ctx.lineWidth = 4;
    ctx.globalAlpha = 0.7 - (swing.progress * 0.5);

    ctx.beginPath();
    ctx.arc(screenPos.x, screenPos.y, arc.range, arc.startAngle, arc.endAngle);
    ctx.stroke();

    // Draw slash effect - curved line with fade
    ctx.strokeStyle = '#FFFFFF';
    ctx.lineWidth = 2;
    ctx.globalAlpha = 0.8 - swing.progress;

    const midAngle = (arc.startAngle + arc.endAngle) / 2;
    const slashX = screenPos.x + Math.cos(midAngle) * arc.range;
    const slashY = screenPos.y + Math.sin(midAngle) * arc.range;

    ctx.beginPath();
    ctx.moveTo(screenPos.x, screenPos.y);
    ctx.lineTo(slashX, slashY);
    ctx.stroke();

    // Draw combo counter indicator
    if (G.combo > 0) {
      ctx.globalAlpha = 1.0;
      ctx.fillStyle = '#FFD700';
      ctx.font = 'bold 14px monospace';
      ctx.textAlign = 'center';
      ctx.fillText(swing.comboHit + '!', screenPos.x, screenPos.y - 30);
    }

    ctx.restore();
  },

  fireProjectile(player, weapon) {
    const p = player;

    // Calculate projectile direction based on aim or facing
    const aim = Input.getAim();
    let angle;

    if (aim.x !== 0 || aim.y !== 0) {
      angle = Math.atan2(aim.y, aim.x);
    } else {
      // Use facing direction
      switch(p.facing) {
        case DIR.RIGHT: angle = 0; break;
        case DIR.DOWN: angle = Math.PI / 2; break;
        case DIR.LEFT: angle = Math.PI; break;
        case DIR.UP: angle = -Math.PI / 2; break;
        default: angle = 0;
      }
    }

    const speed = weapon.type === 'bow' ? 400 : 300;
    const damage = this.getDamage(weapon, player, 1).damage;

    this.createProjectile(p.x, p.y, angle, weapon, damage);

    // Play sound
    if (weapon.type === 'bow') {
      SFX.playSFX('arrow_shoot');
    } else {
      SFX.playSFX('magic_cast');
    }
  },

  createProjectile(x, y, angle, weapon, damage) {
    const projectile = {
      x: x,
      y: y,
      vx: Math.cos(angle) * (weapon.type === 'bow' ? 400 : 300),
      vy: Math.sin(angle) * (weapon.type === 'bow' ? 400 : 300),
      damage: damage,
      element: weapon.element || ELEMENT.PHYSICAL,
      speed: weapon.type === 'bow' ? 400 : 300,
      lifetime: 2.0,
      owner: 'player',
      sprite: weapon.type,
      weapon: weapon,
      piercing: weapon.type === 'spear'
    };

    G.projectiles.push(projectile);
  },

  getDamage(weapon, player, comboHit) {
    const p = player;

    // Base weapon damage
    let baseDamage = weapon.damage || 10;

    // Add player stat scaling
    if (weapon.type === 'staff') {
      // Magic weapons scale with INT
      baseDamage += p.int * 0.5;
    } else {
      // Physical weapons scale with STR
      baseDamage += p.str * 0.5;
    }

    // Critical hit check
    const critRoll = Math.random();
    const isCritical = critRoll < p.critChance;

    if (isCritical) {
      baseDamage *= p.critMultiplier;
    }

    // Combo multiplier
    const comboMultipliers = [1.0, 1.2, 1.5];
    const comboIndex = Math.min(comboHit - 1, 2);
    baseDamage *= comboMultipliers[comboIndex];

    // Special weapon type bonuses
    switch(weapon.type) {
      case 'dagger':
        // Daggers can chain combo
        if (comboHit === 3) baseDamage *= 1.3;
        break;

      case 'hammer':
        // Hammer has ground pound AoE on 3rd hit
        if (comboHit === 3) {
          this.triggerGroundPound(player);
        }
        break;

      case 'axe':
        // Axe has higher base damage
        baseDamage *= 1.15;
        break;

      case 'spear':
        // Spear has longer range but lower damage
        baseDamage *= 0.9;
        break;
    }

    return {
      damage: Math.floor(baseDamage),
      isCritical: isCritical,
      element: weapon.element || ELEMENT.PHYSICAL,
      comboHit: comboHit
    };
  },

  triggerGroundPound(player) {
    // Create AoE damage effect
    const aoe = {
      x: player.x,
      y: player.y,
      radius: TILE_SIZE * 2,
      damage: player.weapon.damage * 1.5,
      element: ELEMENT.PHYSICAL,
      owner: 'player',
      lifetime: 0.3,
      timer: 0
    };

    if (!G.aoeEffects) G.aoeEffects = [];
    G.aoeEffects.push(aoe);

    // Screen shake
    Camera.shake(15, 0.4);

    // Play sound
    SFX.playSFX('ground_slam');
  },

  getElementMultiplier(attackElement, defenderElement) {
    // Element effectiveness: fire>ice>lightning>fire
    const effectiveness = {
      [ELEMENT.FIRE]: { [ELEMENT.ICE]: 1.5, [ELEMENT.LIGHTNING]: 0.75 },
      [ELEMENT.ICE]: { [ELEMENT.LIGHTNING]: 1.5, [ELEMENT.FIRE]: 0.75 },
      [ELEMENT.LIGHTNING]: { [ELEMENT.FIRE]: 1.5, [ELEMENT.ICE]: 0.75 },
      [ELEMENT.POISON]: {},
      [ELEMENT.DARK]: {},
      [ELEMENT.PHYSICAL]: {}
    };

    return effectiveness[attackElement]?.[defenderElement] || 1.0;
  },

  // Weapon type definitions with attack patterns
  getWeaponPattern(type) {
    const patterns = {
      sword: {
        arc: 90,
        range: 40,
        speed: 0.3,
        comboChain: true,
        maxCombo: 3
      },
      axe: {
        arc: 120,
        range: 45,
        speed: 0.5,
        comboChain: true,
        maxCombo: 2
      },
      dagger: {
        arc: 45,
        range: 30,
        speed: 0.2,
        comboChain: true,
        maxCombo: 5
      },
      spear: {
        arc: 30,
        range: 60,
        speed: 0.35,
        comboChain: false,
        maxCombo: 1
      },
      hammer: {
        arc: 90,
        range: 50,
        speed: 0.6,
        comboChain: true,
        maxCombo: 3,
        aoeOnFinisher: true
      },
      staff: {
        arc: 0,
        range: 200,
        speed: 0.4,
        ranged: true,
        manaCost: 10
      },
      bow: {
        arc: 0,
        range: 300,
        speed: 0.5,
        ranged: true,
        chargeable: true
      },
      scythe: {
        arc: 180,
        range: 55,
        speed: 0.45,
        comboChain: true,
        maxCombo: 2
      }
    };

    return patterns[type] || patterns.sword;
  }
};
