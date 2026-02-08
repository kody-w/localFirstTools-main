// combat/collision.js - Collision detection, damage calculation, projectile management
// Global Combat object for Depths of the Abyss

const Combat = {
  floatingTexts: [],

  update(dt) {
    const p = G.player;

    // 1. Player weapon vs enemies
    if (p.attacking) {
      const hitbox = Player.getAttackHitbox();

      if (hitbox) {
        // Find active swing
        const swing = Weapons.activeSwings.find(s => s.player === p);

        G.enemies.forEach(enemy => {
          if (enemy.hp <= 0) return;

          // Check if already hit by this swing
          if (swing && swing.hitEntities.has(enemy.id)) return;

          // Check collision
          if (this.checkCollision(hitbox, enemy)) {
            // Calculate damage
            const damageData = Weapons.getDamage(p.weapon, p, swing ? swing.comboHit : 1);

            // Apply damage
            const knockbackX = enemy.x - p.x;
            const knockbackY = enemy.y - p.y;
            EnemyAI.takeDamage(enemy, damageData.damage, damageData.element, knockbackX, knockbackY);

            // Track hit
            if (swing) {
              swing.hitEntities.add(enemy.id);
            }

            // Increment combo
            G.combo++;
            G.comboTimer = 3.0;

            // Play hit sound
            this.playHitSound(p.weapon.type);

            // Spawn particles
            this.spawnHitParticles(enemy.x, enemy.y, damageData.element);

            // Critical text
            if (damageData.isCritical) {
              this.spawnFloatingText(enemy.x, enemy.y - 30, 'CRITICAL!', '#FFD700');
            }

            // Camera shake on hit
            Camera.shake(3, 0.1);

            // Track damage dealt
            p.totalDamageDealt += damageData.damage;
          }
        });

        // Check boss hit
        if (G.bossActive && G.bossActive.hp > 0) {
          if (this.checkCollision(hitbox, G.bossActive)) {
            if (!swing || !swing.hitEntities.has('boss')) {
              const damageData = Weapons.getDamage(p.weapon, p, swing ? swing.comboHit : 1);

              if (!G.bossActive.invincible) {
                G.bossActive.hp -= damageData.damage;
                G.bossActive.hitFlash = 0.15;

                this.spawnFloatingText(G.bossActive.x, G.bossActive.y - 40, '-' + damageData.damage, '#FF4444');

                if (damageData.isCritical) {
                  this.spawnFloatingText(G.bossActive.x, G.bossActive.y - 50, 'CRITICAL!', '#FFD700');
                }

                G.combo++;
                G.comboTimer = 3.0;

                this.playHitSound(p.weapon.type);
                Camera.shake(5, 0.15);

                p.totalDamageDealt += damageData.damage;
              }

              if (swing) swing.hitEntities.add('boss');
            }
          }
        }
      }
    }

    // 2. Enemy attacks vs player
    G.enemies.forEach(enemy => {
      if (enemy.state !== 'attack') return;
      if (enemy.attackCooldown > 0.1) return; // Only check at start of attack

      const dist = Util.dist(enemy.x, enemy.y, p.x, p.y);

      if (dist <= enemy.attackRange) {
        // Create hitbox
        const hitbox = {
          x: enemy.x - enemy.attackRange / 2,
          y: enemy.y - enemy.attackRange / 2,
          w: enemy.attackRange,
          h: enemy.attackRange
        };

        if (this.checkCollision(hitbox, p)) {
          Player.takeDamage(enemy.damage, enemy.element, enemy.x, enemy.y);
        }
      }
    });

    // Boss melee attacks
    if (G.bossActive && G.bossActive.state === 'attack') {
      const dist = Util.dist(G.bossActive.x, G.bossActive.y, p.x, p.y);

      if (dist <= TILE_SIZE * 3) {
        const hitbox = {
          x: G.bossActive.x - TILE_SIZE * 1.5,
          y: G.bossActive.y - TILE_SIZE * 1.5,
          w: TILE_SIZE * 3,
          h: TILE_SIZE * 3
        };

        if (this.checkCollision(hitbox, p)) {
          Player.takeDamage(G.bossActive.damage, G.bossActive.element, G.bossActive.x, G.bossActive.y);
        }
      }
    }

    // 3. Update and collide projectiles
    this.updateProjectiles(dt);

    // 4. Update and apply AoE effects
    this.updateAoEEffects(dt);

    // 5. Update floating text
    this.updateFloatingTexts(dt);

    // Update weapon swings
    Weapons.updateAttack(p, dt);
  },

  checkCollision(a, b) {
    // AABB overlap test
    // Handle both center-based entities and corner-based hitboxes

    // If 'a' has explicit x,y,w,h as corners (like hitboxes from getAttackHitbox)
    // we check if it's a corner-based box by seeing if w,h exist
    let aLeft, aRight, aTop, aBottom;

    if (a.w !== undefined && a.h !== undefined) {
      // Could be either center-based or corner-based
      // Player.getAttackHitbox() returns corner-based {x,y,w,h}
      // Check if this is a hitbox (has larger dimensions than entity size)
      if (a.w > 50 || a.h > 50) {
        // Likely a corner-based hitbox from getAttackHitbox
        aLeft = a.x;
        aRight = a.x + a.w;
        aTop = a.y;
        aBottom = a.y + a.h;
      } else {
        // Center-based entity
        aLeft = a.x - a.w / 2;
        aRight = a.x + a.w / 2;
        aTop = a.y - a.h / 2;
        aBottom = a.y + a.h / 2;
      }
    } else {
      // Default to center-based with 24x24 size
      aLeft = a.x - 12;
      aRight = a.x + 12;
      aTop = a.y - 12;
      aBottom = a.y + 12;
    }

    let bLeft, bRight, bTop, bBottom;

    if (b.w !== undefined && b.h !== undefined) {
      // Center-based entity (player, enemy, projectile)
      bLeft = b.x - b.w / 2;
      bRight = b.x + b.w / 2;
      bTop = b.y - b.h / 2;
      bBottom = b.y + b.h / 2;
    } else {
      // Default
      bLeft = b.x - 12;
      bRight = b.x + 12;
      bTop = b.y - 12;
      bBottom = b.y + 12;
    }

    // Overlap detection
    return !(aRight < bLeft || aLeft > bRight || aBottom < bTop || aTop > bBottom);
  },

  calculateDamage(baseDamage, attackerStats, defenderStats, element, critChance) {
    // Base damage calculation
    let finalDamage = baseDamage;

    // Add attacker stat scaling
    if (attackerStats) {
      if (element === ELEMENT.PHYSICAL) {
        finalDamage += attackerStats.str * 0.5;
      } else {
        finalDamage += attackerStats.int * 0.5;
      }
    }

    // Critical hit check
    const critRoll = Math.random();
    const isCritical = critRoll < (critChance || 0.1);

    if (isCritical) {
      const critMultiplier = attackerStats?.critMultiplier || 2.0;
      finalDamage *= critMultiplier;
    }

    // Combo multiplier
    const comboMultipliers = [1.0, 1.2, 1.5, 1.8, 2.0];
    const comboLevel = Math.min(G.combo, 4);
    finalDamage *= comboMultipliers[comboLevel];

    // Element effectiveness
    if (defenderStats && defenderStats.element) {
      const elementMultiplier = this.getElementMultiplier(element, defenderStats.element);
      finalDamage *= elementMultiplier;
    }

    // Apply defense
    if (defenderStats && defenderStats.defense) {
      finalDamage -= defenderStats.defense;
    }

    // Minimum damage
    finalDamage = Math.max(1, Math.floor(finalDamage));

    return {
      damage: finalDamage,
      isCritical: isCritical,
      element: element
    };
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

  applyKnockback(entity, fromX, fromY, force) {
    const angle = Util.angle(fromX, fromY, entity.x, entity.y);

    entity.knockbackX = Math.cos(angle) * force;
    entity.knockbackY = Math.sin(angle) * force;
    entity.knockbackTimer = 0.15;
  },

  applyStatusEffect(entity, effect) {
    if (!entity.statusEffects) entity.statusEffects = [];

    // Check if effect already exists
    const existing = entity.statusEffects.find(e => e.type === effect.type);

    if (existing) {
      // Refresh duration
      existing.duration = Math.max(existing.duration, effect.duration);
    } else {
      // Add new effect
      entity.statusEffects.push({
        type: effect.type,
        duration: effect.duration,
        tickDamage: effect.tickDamage || 0,
        tickInterval: effect.tickInterval || 1.0,
        timer: 0,
        source: effect.source || 'unknown'
      });
    }
  },

  updateProjectiles(dt) {
    if (!G.projectiles) G.projectiles = [];

    for (let i = G.projectiles.length - 1; i >= 0; i--) {
      const proj = G.projectiles[i];

      // Update homing
      if (proj.homing) {
        const target = proj.homing;
        const angle = Util.angle(proj.x, proj.y, target.x, target.y);
        const turnSpeed = 0.1;

        const currentAngle = Math.atan2(proj.vy, proj.vx);
        const newAngle = Util.lerp(currentAngle, angle, turnSpeed);

        proj.vx = Math.cos(newAngle) * proj.speed;
        proj.vy = Math.sin(newAngle) * proj.speed;
      }

      // Move projectile
      proj.x += proj.vx * dt;
      proj.y += proj.vy * dt;

      // Decrement lifetime
      proj.lifetime -= dt;
      if (proj.lifetime <= 0) {
        G.projectiles.splice(i, 1);
        continue;
      }

      // Check bounds (off map)
      const tileX = Math.floor(proj.x / TILE_SIZE);
      const tileY = Math.floor(proj.y / TILE_SIZE);

      if (!TileMap.isWalkable(tileX, tileY)) {
        // Hit wall
        if (!proj.piercing) {
          this.spawnHitParticles(proj.x, proj.y, proj.element);
          SFX.playSFX('projectile_impact');
          G.projectiles.splice(i, 1);
          continue;
        }
      }

      // Check collision
      if (proj.owner === 'player') {
        // Player projectile vs enemies
        let hit = false;

        G.enemies.forEach(enemy => {
          if (hit) return;
          if (enemy.hp <= 0) return;

          if (this.checkCollision(proj, enemy)) {
            // Apply damage
            const knockbackX = enemy.x - proj.x;
            const knockbackY = enemy.y - proj.y;
            EnemyAI.takeDamage(enemy, proj.damage, proj.element, knockbackX, knockbackY);

            // Effects
            this.spawnHitParticles(proj.x, proj.y, proj.element);
            SFX.playSFX('projectile_impact');

            // Explode if has radius
            if (proj.explodeRadius) {
              this.createExplosion(proj.x, proj.y, proj.explodeRadius, proj.damage * 0.7, proj.element);
            }

            hit = true;

            if (!proj.piercing) {
              G.projectiles.splice(i, 1);
            }
          }
        });

        // Check boss
        if (!hit && G.bossActive && G.bossActive.hp > 0) {
          if (this.checkCollision(proj, G.bossActive)) {
            if (!G.bossActive.invincible) {
              G.bossActive.hp -= proj.damage;
              G.bossActive.hitFlash = 0.15;

              this.spawnFloatingText(G.bossActive.x, G.bossActive.y - 40, '-' + proj.damage, '#FF4444');
            }

            this.spawnHitParticles(proj.x, proj.y, proj.element);
            SFX.playSFX('projectile_impact');

            if (proj.explodeRadius) {
              this.createExplosion(proj.x, proj.y, proj.explodeRadius, proj.damage * 0.7, proj.element);
            }

            if (!proj.piercing) {
              G.projectiles.splice(i, 1);
            }
          }
        }
      } else {
        // Enemy/boss projectile vs player
        if (this.checkCollision(proj, G.player)) {
          Player.takeDamage(proj.damage, proj.element, proj.x, proj.y);

          this.spawnHitParticles(proj.x, proj.y, proj.element);
          SFX.playSFX('projectile_impact');

          if (proj.explodeRadius) {
            this.createExplosion(proj.x, proj.y, proj.explodeRadius, proj.damage * 0.7, proj.element);
          }

          if (!proj.piercing) {
            G.projectiles.splice(i, 1);
          }
        }
      }
    }
  },

  updateAoEEffects(dt) {
    if (!G.aoeEffects) G.aoeEffects = [];

    for (let i = G.aoeEffects.length - 1; i >= 0; i--) {
      const aoe = G.aoeEffects[i];

      // Handle delay
      if (aoe.delay) {
        aoe.delay -= dt;
        continue;
      }

      aoe.timer += dt;

      // Tick damage
      if (aoe.tickInterval && aoe.timer >= aoe.tickInterval) {
        // Damage all entities in radius
        const dist = Util.dist(aoe.x, aoe.y, G.player.x, G.player.y);

        if (dist <= aoe.radius) {
          Player.takeDamage(aoe.damage, aoe.element, aoe.x, aoe.y);
        }

        aoe.timer = 0;
      }

      // Decrement lifetime
      aoe.lifetime -= dt;

      if (aoe.lifetime <= 0) {
        // On expire, damage entities in radius
        if (!aoe.tickInterval) {
          // Instant damage
          const distToPlayer = Util.dist(aoe.x, aoe.y, G.player.x, G.player.y);

          if (aoe.owner !== 'player' && distToPlayer <= aoe.radius) {
            Player.takeDamage(aoe.damage, aoe.element, aoe.x, aoe.y);
          }

          if (aoe.owner === 'player') {
            G.enemies.forEach(enemy => {
              const dist = Util.dist(aoe.x, aoe.y, enemy.x, enemy.y);
              if (dist <= aoe.radius) {
                const knockbackX = enemy.x - aoe.x;
                const knockbackY = enemy.y - aoe.y;
                EnemyAI.takeDamage(enemy, aoe.damage, aoe.element, knockbackX, knockbackY);
              }
            });
          }
        }

        G.aoeEffects.splice(i, 1);
      }
    }
  },

  createExplosion(x, y, radius, damage, element) {
    const aoe = {
      x: x,
      y: y,
      radius: radius,
      damage: damage,
      element: element,
      owner: 'player',
      lifetime: 0.3,
      timer: 0
    };

    if (!G.aoeEffects) G.aoeEffects = [];
    G.aoeEffects.push(aoe);

    Camera.shake(10, 0.3);
    SFX.playSFX('explosion');
  },

  spawnHitParticles(x, y, element) {
    // Simple particle spawn (visual feedback)
    // Particles system would be in render or separate module
    if (!G.particles) G.particles = [];

    const color = this.getElementColor(element);

    for (let i = 0; i < 5; i++) {
      const angle = Math.random() * Math.PI * 2;
      const speed = 50 + Math.random() * 50;

      G.particles.push({
        x: x,
        y: y,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed,
        lifetime: 0.3,
        color: color,
        size: 2 + Math.random() * 2
      });
    }
  },

  getElementColor(element) {
    const colors = {
      [ELEMENT.FIRE]: '#FF4444',
      [ELEMENT.ICE]: '#4444FF',
      [ELEMENT.LIGHTNING]: '#FFFF44',
      [ELEMENT.POISON]: '#44FF44',
      [ELEMENT.DARK]: '#AA44AA',
      [ELEMENT.PHYSICAL]: '#AAAAAA'
    };

    return colors[element] || '#FFFFFF';
  },

  playHitSound(weaponType) {
    const sounds = {
      sword: 'sword_hit',
      axe: 'axe_hit',
      dagger: 'dagger_hit',
      spear: 'spear_hit',
      hammer: 'hammer_hit',
      staff: 'magic_hit',
      bow: 'arrow_hit',
      scythe: 'slash_hit'
    };

    const sound = sounds[weaponType] || 'hit';
    SFX.playSFX(sound);
  },

  spawnFloatingText(x, y, text, color) {
    this.floatingTexts.push({
      x: x,
      y: y,
      text: text,
      color: color,
      lifetime: 1.0,
      vy: -30
    });
  },

  updateFloatingTexts(dt) {
    for (let i = this.floatingTexts.length - 1; i >= 0; i--) {
      const text = this.floatingTexts[i];

      text.y += text.vy * dt;
      text.lifetime -= dt;

      if (text.lifetime <= 0) {
        this.floatingTexts.splice(i, 1);
      }
    }
  },

  renderProjectiles(ctx, camera) {
    if (!G.projectiles) return;

    G.projectiles.forEach(proj => {
      const screenPos = Camera.worldToScreen(proj.x, proj.y);

      ctx.save();

      // Different visuals per projectile type
      switch(proj.sprite) {
        case 'bow':
        case 'knife':
          // Arrow/knife - thin line
          ctx.strokeStyle = '#888888';
          ctx.lineWidth = 2;

          const angle = Math.atan2(proj.vy, proj.vx);
          const length = 12;

          ctx.beginPath();
          ctx.moveTo(screenPos.x - Math.cos(angle) * length, screenPos.y - Math.sin(angle) * length);
          ctx.lineTo(screenPos.x + Math.cos(angle) * length, screenPos.y + Math.sin(angle) * length);
          ctx.stroke();
          break;

        case 'fireball':
        case 'magma':
          // Fireball - orange circle + trail
          ctx.fillStyle = '#FF6600';
          ctx.shadowBlur = 15;
          ctx.shadowColor = '#FF6600';
          ctx.beginPath();
          ctx.arc(screenPos.x, screenPos.y, 6, 0, Math.PI * 2);
          ctx.fill();
          break;

        case 'ice_lance':
          // Ice shard - blue diamond
          ctx.fillStyle = '#4488FF';
          ctx.shadowBlur = 10;
          ctx.shadowColor = '#4488FF';
          ctx.beginPath();
          ctx.moveTo(screenPos.x, screenPos.y - 8);
          ctx.lineTo(screenPos.x + 4, screenPos.y);
          ctx.lineTo(screenPos.x, screenPos.y + 8);
          ctx.lineTo(screenPos.x - 4, screenPos.y);
          ctx.closePath();
          ctx.fill();
          break;

        case 'arcane_missile':
          // Purple orb
          ctx.fillStyle = '#AA44FF';
          ctx.shadowBlur = 12;
          ctx.shadowColor = '#AA44FF';
          ctx.beginPath();
          ctx.arc(screenPos.x, screenPos.y, 5, 0, Math.PI * 2);
          ctx.fill();
          break;

        case 'shadow_orb':
          // Dark orb
          ctx.fillStyle = '#442288';
          ctx.shadowBlur = 10;
          ctx.shadowColor = '#442288';
          ctx.beginPath();
          ctx.arc(screenPos.x, screenPos.y, 6, 0, Math.PI * 2);
          ctx.fill();
          break;

        default:
          // Generic projectile
          const color = this.getElementColor(proj.element);
          ctx.fillStyle = color;
          ctx.beginPath();
          ctx.arc(screenPos.x, screenPos.y, 4, 0, Math.PI * 2);
          ctx.fill();
      }

      ctx.restore();
    });
  },

  renderFloatingTexts(ctx, camera) {
    this.floatingTexts.forEach(text => {
      const screenPos = Camera.worldToScreen(text.x, text.y);

      ctx.save();
      ctx.globalAlpha = text.lifetime;
      ctx.fillStyle = text.color;
      ctx.font = 'bold 14px monospace';
      ctx.textAlign = 'center';
      ctx.strokeStyle = '#000000';
      ctx.lineWidth = 3;

      ctx.strokeText(text.text, screenPos.x, screenPos.y);
      ctx.fillText(text.text, screenPos.x, screenPos.y);

      ctx.restore();
    });
  },

  renderParticles(ctx, camera) {
    if (!G.particles) return;

    for (let i = G.particles.length - 1; i >= 0; i--) {
      const particle = G.particles[i];

      particle.x += particle.vx * G.dt;
      particle.y += particle.vy * G.dt;
      particle.lifetime -= G.dt;

      if (particle.lifetime <= 0) {
        G.particles.splice(i, 1);
        continue;
      }

      const screenPos = Camera.worldToScreen(particle.x, particle.y);

      ctx.save();
      ctx.globalAlpha = particle.lifetime / 0.3;
      ctx.fillStyle = particle.color;
      ctx.beginPath();
      ctx.arc(screenPos.x, screenPos.y, particle.size, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }
  }
};
