// combat/boss-ai.js - Multi-phase boss encounter system
// Global BossAI object for Depths of the Abyss

const BossAI = {
  activeTelegraphs: [],

  update(boss, dt) {
    if (!boss || boss.hp <= 0) {
      if (boss && boss.state !== 'dead') {
        this.onDeath(boss);
      }
      return;
    }

    // Check phase transitions
    this.checkPhaseTransition(boss);

    // Update timers
    if (boss.attackCooldown > 0) boss.attackCooldown -= dt;
    if (boss.specialTimer > 0) boss.specialTimer -= dt;
    if (boss.knockbackTimer > 0) {
      boss.x += boss.knockbackX * dt;
      boss.y += boss.knockbackY * dt;
      boss.knockbackTimer -= dt;
      if (boss.knockbackTimer <= 0) {
        boss.knockbackX = 0;
        boss.knockbackY = 0;
      }
    }

    // Decay hit flash
    if (boss.hitFlash > 0) {
      boss.hitFlash -= dt * 5;
    }

    // Execute attack pattern
    this.executePattern(boss, dt);

    // Update telegraphs
    for (let i = this.activeTelegraphs.length - 1; i >= 0; i--) {
      const telegraph = this.activeTelegraphs[i];
      telegraph.timer += dt;

      if (telegraph.timer >= telegraph.delay) {
        // Execute telegraphed attack
        this.executeTelegraph(telegraph);
        this.activeTelegraphs.splice(i, 1);
      }
    }
  },

  checkPhaseTransition(boss) {
    const hpPercent = boss.hp / boss.maxHp;

    // Check if crossed phase threshold
    if (boss.phase < boss.maxPhases) {
      // phase 1 -> check threshold[0] (0.7)
      // phase 2 -> check threshold[1] (0.4)
      // phase 3 -> check threshold[2] (0.15)
      const thresholdIndex = boss.phase - 1;

      if (thresholdIndex < boss.phaseThresholds.length) {
        const nextThreshold = boss.phaseThresholds[thresholdIndex];

        if (hpPercent <= nextThreshold) {
          this.transitionPhase(boss);
        }
      }
    }
  },

  transitionPhase(boss) {
    boss.phase++;

    // Visual feedback
    Camera.shake(15, 0.5);
    SFX.playSFX('boss_phase_change');

    // Brief invulnerability
    boss.invincible = true;
    setTimeout(() => { boss.invincible = false; }, 1000);

    // Dialogue
    // boss.phase was just incremented, so phase 2 uses index 0, phase 3 uses index 1, etc.
    const dialogueIndex = boss.phase - 2;
    if (boss.dialogue.phaseChange && boss.dialogue.phaseChange[dialogueIndex]) {
      const msg = boss.dialogue.phaseChange[dialogueIndex];
      Combat.spawnFloatingText(boss.x, boss.y - 50, msg, '#FFD700');
    }

    // Phase-specific mechanics
    this.onPhaseChange(boss);
  },

  onPhaseChange(boss) {
    switch(boss.bossId) {
      case 'grave_warden':
        if (boss.phase === 2) {
          // Summon 3 skeletons
          for (let i = 0; i < 3; i++) {
            const angle = (i / 3) * Math.PI * 2;
            const x = boss.x + Math.cos(angle) * TILE_SIZE * 3;
            const y = boss.y + Math.sin(angle) * TILE_SIZE * 3;
            const skeleton = EnemyAI.spawn('skeleton', x, y, false, G.currentFloor);
            G.enemies.push(skeleton);
          }
        } else if (boss.phase === 3) {
          // Enraged - faster attacks
          boss.attackSpeed *= 0.7;
        }
        break;

      case 'mycelium_king':
        if (boss.phase === 2) {
          // Split into 3 copies
          this.createMyceliumCopies(boss);
        }
        break;

      case 'infernal_colossus':
        if (boss.phase === 3) {
          // Floor becomes lava
          boss.lavaFloor = true;
        }
        break;

      case 'abyss_incarnate':
        if (boss.phase === 3) {
          // Copy player abilities
          boss.copiedAbilities = G.player.equippedAbilities.slice();
        }
        break;
    }
  },

  executePattern(boss, dt) {
    const p = G.player;

    // Boss-specific attack patterns
    switch(boss.bossId) {
      case 'grave_warden':
        this.graveWardenPattern(boss, p, dt);
        break;

      case 'mycelium_king':
        this.myceliumKingPattern(boss, p, dt);
        break;

      case 'infernal_colossus':
        this.infernalColossusPattern(boss, p, dt);
        break;

      case 'glacial_sovereign':
        this.glacialSovereignPattern(boss, p, dt);
        break;

      case 'abyss_incarnate':
        this.abyssIncarnatePattern(boss, p, dt);
        break;

      default:
        this.genericBossPattern(boss, p, dt);
    }
  },

  graveWardenPattern(boss, player, dt) {
    if (boss.attackCooldown > 0) return;

    const dist = Util.dist(boss.x, boss.y, player.x, player.y);

    if (boss.phase === 1) {
      // Sword combo (3-hit) or shield charge
      const roll = Math.random();

      if (roll < 0.6) {
        this.swordCombo(boss, player);
      } else {
        this.shieldCharge(boss, player);
      }
    } else if (boss.phase === 2) {
      // Ground slam AoE
      this.groundSlam(boss);
    } else {
      // Phase 3: faster attacks + combos
      this.swordCombo(boss, player);
      if (Math.random() < 0.3) {
        setTimeout(() => this.groundSlam(boss), 500);
      }
    }

    boss.attackCooldown = boss.attackSpeed;
  },

  myceliumKingPattern(boss, player, dt) {
    if (boss.attackCooldown > 0) return;

    if (boss.phase === 1) {
      // Spore cloud or vine grab
      const roll = Math.random();

      if (roll < 0.5) {
        this.sporeCloud(boss);
      } else {
        this.vineGrab(boss, player);
      }
    } else if (boss.phase === 3) {
      // Mushroom cage + toxic rain
      this.mushroomCage(boss);
      setTimeout(() => this.toxicRain(boss), 1000);
    }

    boss.attackCooldown = boss.attackSpeed;
  },

  infernalColossusPattern(boss, player, dt) {
    if (boss.attackCooldown > 0) return;

    if (boss.phase === 1) {
      // Fire breath or magma ball
      const roll = Math.random();

      if (roll < 0.5) {
        this.fireBreath(boss, player);
      } else {
        this.magmaBall(boss, player);
      }
    } else if (boss.phase === 2) {
      // Meteor rain
      this.meteorRain(boss);
    } else {
      // Phase 3: body slam
      this.bodySlam(boss, player);
    }

    boss.attackCooldown = boss.attackSpeed;
  },

  glacialSovereignPattern(boss, player, dt) {
    if (boss.attackCooldown > 0) return;

    if (boss.phase === 1) {
      // Ice lance barrage or frost nova
      const roll = Math.random();

      if (roll < 0.5) {
        this.iceLanceBarrage(boss, player);
      } else {
        this.frostNova(boss);
      }
    } else if (boss.phase === 2) {
      // Time freeze
      this.timeFreeze(boss, player);
    } else {
      // Phase 3: blizzard
      this.blizzard(boss);
    }

    boss.attackCooldown = boss.attackSpeed;
  },

  abyssIncarnatePattern(boss, player, dt) {
    if (boss.attackCooldown > 0) return;

    if (boss.phase === 1) {
      // Void beam or shadow orbs
      const roll = Math.random();

      if (roll < 0.5) {
        this.voidBeam(boss, player);
      } else {
        this.shadowOrbs(boss, player);
      }
    } else if (boss.phase === 2) {
      // Copy random previous boss attacks
      this.copyBossAttack(boss, player);
    } else if (boss.phase === 3) {
      // Mirror player abilities
      this.mirrorPlayerAbility(boss, player);
    } else {
      // Phase 4: all elements
      this.elementalBarrage(boss, player);
    }

    boss.attackCooldown = boss.attackSpeed;
  },

  genericBossPattern(boss, player, dt) {
    if (boss.attackCooldown > 0) return;

    const dist = Util.dist(boss.x, boss.y, player.x, player.y);

    if (dist < TILE_SIZE * 2) {
      // Melee attack - use Player.takeDamage instead of Combat.applyDamage (which doesn't exist)
      Player.takeDamage(boss.damage, boss.element, boss.x, boss.y);
    }

    boss.attackCooldown = boss.attackSpeed;
  },

  // BOSS ATTACK IMPLEMENTATIONS

  swordCombo(boss, player) {
    // 3-hit combo
    for (let i = 0; i < 3; i++) {
      setTimeout(() => {
        const hitbox = {
          x: boss.x + (player.x - boss.x) * 0.5,
          y: boss.y + (player.y - boss.y) * 0.5,
          w: TILE_SIZE * 2,
          h: TILE_SIZE * 2
        };

        if (Combat.checkCollision(hitbox, G.player)) {
          Player.takeDamage(boss.damage * (1 + i * 0.2), ELEMENT.PHYSICAL, boss.x, boss.y);
        }

        SFX.playSFX('boss_slash');
      }, i * 300);
    }
  },

  shieldCharge(boss, player) {
    const angle = Util.angle(boss.x, boss.y, player.x, player.y);
    const distance = TILE_SIZE * 4;

    // Charge in direction
    boss.knockbackX = Math.cos(angle) * 400;
    boss.knockbackY = Math.sin(angle) * 400;
    boss.knockbackTimer = 0.5;

    Camera.shake(10, 0.3);
    SFX.playSFX('boss_charge');
  },

  groundSlam(boss) {
    // Telegraphed AoE
    const telegraph = {
      x: boss.x,
      y: boss.y,
      radius: TILE_SIZE * 3,
      damage: boss.damage * 1.5,
      element: ELEMENT.PHYSICAL,
      delay: 0.8,
      timer: 0,
      boss: boss
    };

    this.activeTelegraphs.push(telegraph);
    SFX.playSFX('boss_telegraph');
  },

  sporeCloud(boss) {
    const aoe = {
      x: boss.x,
      y: boss.y,
      radius: TILE_SIZE * 2.5,
      damage: boss.damage * 0.5,
      element: ELEMENT.POISON,
      owner: 'boss',
      lifetime: 3.0,
      timer: 0,
      tickInterval: 0.5
    };

    if (!G.aoeEffects) G.aoeEffects = [];
    G.aoeEffects.push(aoe);

    SFX.playSFX('poison_cloud');
  },

  vineGrab(boss, player) {
    const dist = Util.dist(boss.x, boss.y, player.x, player.y);

    if (dist < TILE_SIZE * 5) {
      // Root player for 1 second
      Combat.applyStatusEffect(player, {
        type: 'stun',
        duration: 1.0,
        tickDamage: 0,
        tickInterval: 0
      });

      Combat.spawnFloatingText(player.x, player.y - 20, 'ROOTED!', '#44AA44');
      SFX.playSFX('vine_grab');
    }
  },

  mushroomCage(boss) {
    // Walls close in (not implemented - visual only)
    Camera.shake(12, 0.4);
    SFX.playSFX('mushroom_cage');
  },

  toxicRain(boss) {
    // Random AoEs
    for (let i = 0; i < 5; i++) {
      setTimeout(() => {
        const x = boss.x + Util.randFloat(-TILE_SIZE * 4, TILE_SIZE * 4);
        const y = boss.y + Util.randFloat(-TILE_SIZE * 4, TILE_SIZE * 4);

        const telegraph = {
          x: x,
          y: y,
          radius: TILE_SIZE,
          damage: boss.damage * 0.7,
          element: ELEMENT.POISON,
          delay: 0.5,
          timer: 0
        };

        this.activeTelegraphs.push(telegraph);
      }, i * 200);
    }

    SFX.playSFX('toxic_rain');
  },

  fireBreath(boss, player) {
    const angle = Util.angle(boss.x, boss.y, player.x, player.y);

    // Cone attack (3 projectiles)
    for (let i = -1; i <= 1; i++) {
      const spreadAngle = angle + (i * 0.3);

      const projectile = {
        x: boss.x,
        y: boss.y,
        vx: Math.cos(spreadAngle) * 200,
        vy: Math.sin(spreadAngle) * 200,
        damage: boss.damage,
        element: ELEMENT.FIRE,
        speed: 200,
        lifetime: 1.5,
        owner: 'boss',
        sprite: 'fire'
      };

      G.projectiles.push(projectile);
    }

    SFX.playSFX('fire_breath');
  },

  magmaBall(boss, player) {
    const angle = Util.angle(boss.x, boss.y, player.x, player.y);

    const projectile = {
      x: boss.x,
      y: boss.y,
      vx: Math.cos(angle) * 250,
      vy: Math.sin(angle) * 250,
      damage: boss.damage * 1.5,
      element: ELEMENT.FIRE,
      speed: 250,
      lifetime: 2.0,
      owner: 'boss',
      sprite: 'magma',
      explodeRadius: TILE_SIZE * 2
    };

    G.projectiles.push(projectile);
    SFX.playSFX('magma_ball');
  },

  meteorRain(boss) {
    // 3 telegraphed AoEs
    for (let i = 0; i < 3; i++) {
      setTimeout(() => {
        const x = boss.x + Util.randFloat(-TILE_SIZE * 5, TILE_SIZE * 5);
        const y = boss.y + Util.randFloat(-TILE_SIZE * 5, TILE_SIZE * 5);

        const telegraph = {
          x: x,
          y: y,
          radius: TILE_SIZE * 2,
          damage: boss.damage * 2,
          element: ELEMENT.FIRE,
          delay: 1.0,
          timer: 0
        };

        this.activeTelegraphs.push(telegraph);
        SFX.playSFX('meteor_incoming');
      }, i * 500);
    }
  },

  bodySlam(boss, player) {
    const angle = Util.angle(boss.x, boss.y, player.x, player.y);

    // Jump to player position
    boss.x = player.x + Math.cos(angle) * TILE_SIZE * 2;
    boss.y = player.y + Math.sin(angle) * TILE_SIZE * 2;

    // AoE damage
    const aoe = {
      x: boss.x,
      y: boss.y,
      radius: TILE_SIZE * 3,
      damage: boss.damage * 2,
      element: ELEMENT.PHYSICAL,
      owner: 'boss',
      lifetime: 0.3,
      timer: 0
    };

    if (!G.aoeEffects) G.aoeEffects = [];
    G.aoeEffects.push(aoe);

    Camera.shake(20, 0.5);
    SFX.playSFX('body_slam');
  },

  iceLanceBarrage(boss, player) {
    // 5 projectiles
    for (let i = 0; i < 5; i++) {
      setTimeout(() => {
        const angle = Util.angle(boss.x, boss.y, player.x, player.y);

        const projectile = {
          x: boss.x,
          y: boss.y,
          vx: Math.cos(angle) * 300,
          vy: Math.sin(angle) * 300,
          damage: boss.damage * 0.8,
          element: ELEMENT.ICE,
          speed: 300,
          lifetime: 2.0,
          owner: 'boss',
          sprite: 'ice_lance'
        };

        G.projectiles.push(projectile);
        SFX.playSFX('ice_lance');
      }, i * 150);
    }
  },

  frostNova(boss) {
    // Ring AoE
    const telegraph = {
      x: boss.x,
      y: boss.y,
      radius: TILE_SIZE * 4,
      damage: boss.damage,
      element: ELEMENT.ICE,
      delay: 0.6,
      timer: 0,
      ring: true
    };

    this.activeTelegraphs.push(telegraph);
    SFX.playSFX('frost_nova');
  },

  timeFreeze(boss, player) {
    // Slow player for 3 seconds
    Combat.applyStatusEffect(player, {
      type: 'freeze',
      duration: 3.0,
      speedMultiplier: 0.5,
      tickDamage: 0,
      tickInterval: 0
    });

    Combat.spawnFloatingText(player.x, player.y - 20, 'TIME FREEZE!', '#4444FF');
    SFX.playSFX('time_freeze');
  },

  blizzard(boss) {
    // Screen-wide damage ticks
    boss.blizzardActive = true;
    boss.blizzardDuration = 5.0;

    SFX.playSFX('blizzard');
  },

  voidBeam(boss, player) {
    // Sweeping laser
    const startAngle = Util.angle(boss.x, boss.y, player.x, player.y);

    for (let i = 0; i < 10; i++) {
      setTimeout(() => {
        const sweepAngle = startAngle + (i / 10) * Math.PI / 2;

        const telegraph = {
          x: boss.x,
          y: boss.y,
          angle: sweepAngle,
          length: TILE_SIZE * 8,
          damage: boss.damage,
          element: ELEMENT.DARK,
          delay: 0.1,
          timer: 0,
          beam: true
        };

        this.activeTelegraphs.push(telegraph);
      }, i * 100);
    }

    SFX.playSFX('void_beam');
  },

  shadowOrbs(boss, player) {
    // Homing projectiles
    for (let i = 0; i < 5; i++) {
      setTimeout(() => {
        const angle = (i / 5) * Math.PI * 2;

        const projectile = {
          x: boss.x,
          y: boss.y,
          vx: Math.cos(angle) * 150,
          vy: Math.sin(angle) * 150,
          damage: boss.damage * 0.6,
          element: ELEMENT.DARK,
          speed: 150,
          lifetime: 3.0,
          owner: 'boss',
          sprite: 'shadow_orb',
          homing: player
        };

        G.projectiles.push(projectile);
      }, i * 200);
    }

    SFX.playSFX('shadow_orbs');
  },

  copyBossAttack(boss, player) {
    // Random attack from previous bosses
    const attacks = [
      () => this.groundSlam(boss),
      () => this.sporeCloud(boss),
      () => this.fireBreath(boss, player),
      () => this.iceLanceBarrage(boss, player)
    ];

    const attack = Util.pick(attacks);
    attack();
  },

  mirrorPlayerAbility(boss, player) {
    // Use player's equipped ability
    if (boss.copiedAbilities && boss.copiedAbilities.length > 0) {
      const abilityId = Util.pick(boss.copiedAbilities.filter(a => a !== null));
      if (abilityId) {
        // Simplified - just trigger effect
        SFX.playSFX('ability_cast');
        Combat.spawnFloatingText(boss.x, boss.y - 30, 'MIMIC!', '#AA44FF');
      }
    }
  },

  elementalBarrage(boss, player) {
    // All elements
    const elements = [ELEMENT.FIRE, ELEMENT.ICE, ELEMENT.LIGHTNING, ELEMENT.DARK];

    elements.forEach((element, i) => {
      setTimeout(() => {
        const angle = Util.angle(boss.x, boss.y, player.x, player.y);

        const projectile = {
          x: boss.x,
          y: boss.y,
          vx: Math.cos(angle) * 280,
          vy: Math.sin(angle) * 280,
          damage: boss.damage,
          element: element,
          speed: 280,
          lifetime: 2.0,
          owner: 'boss',
          sprite: 'elemental'
        };

        G.projectiles.push(projectile);
      }, i * 250);
    });

    SFX.playSFX('elemental_barrage');
  },

  createMyceliumCopies(boss) {
    // Create 2 copies (boss + 2 copies = 3 total)
    for (let i = 0; i < 2; i++) {
      const angle = ((i + 1) / 3) * Math.PI * 2;
      const x = boss.x + Math.cos(angle) * TILE_SIZE * 4;
      const y = boss.y + Math.sin(angle) * TILE_SIZE * 4;

      const copy = {
        ...boss,
        x: x,
        y: y,
        isCopy: true,
        hp: 1,
        maxHp: 1
      };

      G.enemies.push(copy);
    }
  },

  executeTelegraph(telegraph) {
    if (telegraph.beam) {
      // Beam attack
      const dist = Util.dist(telegraph.x, telegraph.y, G.player.x, G.player.y);
      const playerAngle = Util.angle(telegraph.x, telegraph.y, G.player.x, G.player.y);
      const angleDiff = Math.abs(playerAngle - telegraph.angle);

      if (dist < telegraph.length && angleDiff < 0.2) {
        Player.takeDamage(telegraph.damage, telegraph.element, telegraph.x, telegraph.y);
      }
    } else {
      // AoE attack
      const dist = Util.dist(telegraph.x, telegraph.y, G.player.x, G.player.y);

      if (dist <= telegraph.radius) {
        Player.takeDamage(telegraph.damage, telegraph.element, telegraph.x, telegraph.y);
      }
    }

    Camera.shake(8, 0.2);
    SFX.playSFX('boss_impact');
  },

  spawnBoss(bossId, x, y, floor) {
    const bossDef = BOSS_DEFS[bossId];
    if (!bossDef) return null;

    const boss = {
      isBoss: true,
      bossId: bossId,
      name: bossDef.name,
      x: x,
      y: y,
      vx: 0, vy: 0,
      w: 48, h: 48,
      hp: bossDef.hp,
      maxHp: bossDef.hp,
      damage: bossDef.damage,
      speed: bossDef.speed,
      defense: bossDef.defense,
      element: bossDef.element,
      phase: 1,
      maxPhases: bossDef.maxPhases || 3,
      phaseThresholds: bossDef.phaseThresholds || [0.7, 0.4, 0.15],
      attackPattern: bossDef.attackPattern || [],
      patternIndex: 0,
      attackCooldown: 0,
      attackSpeed: bossDef.attackSpeed || 2.0,
      specialTimer: 0,
      specialCooldown: 5,
      dialogue: bossDef.dialogue || { intro: '', phaseChange: [], death: '' },
      arena: bossDef.arena || { x: x - TILE_SIZE * 8, y: y - TILE_SIZE * 8, w: TILE_SIZE * 16, h: TILE_SIZE * 16 },
      hitFlash: 0,
      knockbackX: 0, knockbackY: 0, knockbackTimer: 0,
      invincible: false,
      state: 'active'
    };

    // Set as active boss
    G.bossActive = boss;

    // Play roar
    SFX.playSFX('boss_roar');

    // Camera shake
    Camera.shake(10, 0.3);

    // Dialogue
    if (boss.dialogue.intro) {
      Combat.spawnFloatingText(boss.x, boss.y - 60, boss.dialogue.intro, '#FFD700');
    }

    return boss;
  },

  onDeath(boss) {
    boss.state = 'dead';
    boss.hp = 0;

    // Play death sound
    SFX.playSFX('boss_death');

    // Camera shake
    Camera.shake(25, 0.8);

    // Dialogue
    if (boss.dialogue.death) {
      Combat.spawnFloatingText(boss.x, boss.y - 60, boss.dialogue.death, '#FF4444');
    }

    // Drop legendary loot
    for (let i = 0; i < 3; i++) {
      const loot = {
        x: boss.x + Util.randFloat(-TILE_SIZE, TILE_SIZE),
        y: boss.y + Util.randFloat(-TILE_SIZE, TILE_SIZE),
        type: 'item',
        item: generateWeapon(G.currentFloor, RARITY.LEGENDARY)
      };

      if (!G.lootDrops) G.lootDrops = [];
      G.lootDrops.push(loot);
    }

    // Award massive XP
    Player.addXP(boss.maxHp);

    // Update stats
    if (!G.runStats) G.runStats = {};
    if (!G.runStats.bossesKilled) G.runStats.bossesKilled = 0;
    G.runStats.bossesKilled++;

    // Clear active boss
    G.bossActive = null;

    // Spawn stairs (not implemented here)
  },

  render(boss, ctx, camera) {
    if (!boss || boss.state === 'dead') return;

    const screenPos = Camera.worldToScreen(boss.x, boss.y);

    ctx.save();

    // Draw shadow
    ctx.fillStyle = 'rgba(0, 0, 0, 0.4)';
    ctx.beginPath();
    ctx.ellipse(screenPos.x, screenPos.y + 20, 30, 10, 0, 0, Math.PI * 2);
    ctx.fill();

    // Flash white when hit
    if (boss.hitFlash > 0) {
      ctx.fillStyle = '#FFFFFF';
    } else {
      // Boss color changes per phase
      ctx.fillStyle = this.getPhaseColor(boss);
    }

    // Phase-specific aura
    ctx.shadowBlur = 20 + boss.phase * 5;
    ctx.shadowColor = this.getPhaseColor(boss);

    // Draw large boss body
    ctx.fillRect(screenPos.x - 24, screenPos.y - 24, 48, 48);

    // Draw head
    ctx.beginPath();
    ctx.arc(screenPos.x, screenPos.y - 30, 15, 0, Math.PI * 2);
    ctx.fill();

    ctx.shadowBlur = 0;

    ctx.restore();

    // Draw telegraphs
    this.renderTelegraphs(ctx, camera);
  },

  getPhaseColor(boss) {
    const colors = {
      1: '#AA4444',
      2: '#AA8844',
      3: '#8844AA',
      4: '#4444AA'
    };

    return colors[boss.phase] || '#AA4444';
  },

  renderTelegraphs(ctx, camera) {
    this.activeTelegraphs.forEach(telegraph => {
      const screenPos = Camera.worldToScreen(telegraph.x, telegraph.y);
      const progress = telegraph.timer / telegraph.delay;

      ctx.save();
      ctx.globalAlpha = 0.3 + progress * 0.4;

      if (telegraph.beam) {
        // Draw beam line
        ctx.strokeStyle = '#FF0000';
        ctx.lineWidth = 4;
        ctx.beginPath();
        ctx.moveTo(screenPos.x, screenPos.y);
        const endX = screenPos.x + Math.cos(telegraph.angle) * telegraph.length;
        const endY = screenPos.y + Math.sin(telegraph.angle) * telegraph.length;
        ctx.lineTo(endX, endY);
        ctx.stroke();
      } else {
        // Draw AoE circle
        ctx.strokeStyle = '#FF0000';
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.arc(screenPos.x, screenPos.y, telegraph.radius, 0, Math.PI * 2);
        ctx.stroke();
      }

      ctx.restore();
    });
  }
};
