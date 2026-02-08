// combat/enemy-ai.js - Enemy behavior patterns and A* pathfinding
// Global EnemyAI object for Depths of the Abyss

const EnemyAI = {
  pathCache: new Map(), // Cache A* paths
  pathCacheTimeout: 0.5,

  update(enemy, dt) {
    if (!enemy || enemy.hp <= 0) {
      if (enemy && enemy.state !== 'dead') {
        this.die(enemy);
      }
      return;
    }

    // Update timers
    if (enemy.attackCooldown > 0) enemy.attackCooldown -= dt;
    if (enemy.stateTimer > 0) enemy.stateTimer -= dt;
    if (enemy.knockbackTimer > 0) {
      enemy.x += enemy.knockbackX * dt;
      enemy.y += enemy.knockbackY * dt;
      enemy.knockbackTimer -= dt;
      if (enemy.knockbackTimer <= 0) {
        enemy.knockbackX = 0;
        enemy.knockbackY = 0;
      }
    }

    // Update status effects
    this.updateStatusEffects(enemy, dt);

    // Handle time warp slow
    let speedMultiplier = 1.0;
    if (enemy.timeWarpDuration > 0) {
      enemy.timeWarpDuration -= dt;
      speedMultiplier = enemy.timeWarpSlow || 1.0;
    }

    // Check if stunned
    const stunned = enemy.statusEffects.some(e => e.type === 'stun');
    if (stunned) {
      enemy.vx = 0;
      enemy.vy = 0;
      return;
    }

    // Decay hit flash
    if (enemy.hitFlash > 0) {
      enemy.hitFlash -= dt * 5;
    }

    const p = G.player;
    const distToPlayer = Util.dist(enemy.x, enemy.y, p.x, p.y);
    const tilePos = TileMap.pixelToTile(enemy.x, enemy.y);

    // Check if player is visible (fog of war)
    const canSeePlayer = Fog.isVisible(tilePos.x, tilePos.y) && distToPlayer <= enemy.chaseRadius;

    // State machine
    switch(enemy.state) {
      case 'idle':
        this.handleIdle(enemy, p, distToPlayer, canSeePlayer, dt, speedMultiplier);
        break;

      case 'patrol':
        this.handlePatrol(enemy, p, distToPlayer, canSeePlayer, dt, speedMultiplier);
        break;

      case 'chase':
        this.handleChase(enemy, p, distToPlayer, canSeePlayer, dt, speedMultiplier);
        break;

      case 'attack':
        this.handleAttack(enemy, p, distToPlayer, dt);
        break;

      case 'flee':
        this.handleFlee(enemy, p, dt, speedMultiplier);
        break;

      case 'dead':
        break;
    }

    // Behavior-specific logic
    this.executeBehavior(enemy, p, distToPlayer, dt, speedMultiplier);
  },

  handleIdle(enemy, player, dist, canSee, dt, speedMult) {
    // Alert when player in range and visible
    if (canSee && dist <= enemy.alertRadius) {
      enemy.state = 'chase';
      this.alertNearby(enemy);
    }

    // Patrol behavior transitions to patrol state
    if (enemy.behavior === 'patrol' && enemy.patrolPath.length > 0) {
      enemy.state = 'patrol';
    }
  },

  handlePatrol(enemy, player, dist, canSee, dt, speedMult) {
    // Alert when player close
    if (canSee && dist <= enemy.alertRadius) {
      enemy.state = 'chase';
      this.alertNearby(enemy);
      return;
    }

    // Move along patrol path
    if (enemy.patrolPath.length === 0) {
      enemy.state = 'idle';
      return;
    }

    const target = enemy.patrolPath[enemy.patrolIndex];
    const targetX = target.x * TILE_SIZE + TILE_SIZE / 2;
    const targetY = target.y * TILE_SIZE + TILE_SIZE / 2;

    const distToTarget = Util.dist(enemy.x, enemy.y, targetX, targetY);

    if (distToTarget < 10) {
      // Reached waypoint
      enemy.patrolIndex = (enemy.patrolIndex + 1) % enemy.patrolPath.length;
    } else {
      // Move toward waypoint
      const angle = Util.angle(enemy.x, enemy.y, targetX, targetY);
      enemy.vx = Math.cos(angle) * enemy.speed * speedMult;
      enemy.vy = Math.sin(angle) * enemy.speed * speedMult;

      enemy.x += enemy.vx * dt;
      enemy.y += enemy.vy * dt;
    }
  },

  handleChase(enemy, player, dist, canSee, dt, speedMult) {
    // Attack when in range
    if (dist <= enemy.attackRange) {
      enemy.state = 'attack';
      return;
    }

    // Lose aggro if player too far or not visible
    if (!canSee || dist > enemy.chaseRadius * 1.5) {
      enemy.state = enemy.behavior === 'patrol' ? 'patrol' : 'idle';
      enemy.path = [];
      return;
    }

    // Pathfind to player
    if (!enemy.pathTimer || enemy.pathTimer <= 0) {
      enemy.path = this.pathfind(enemy.x, enemy.y, player.x, player.y);
      enemy.pathTimer = this.pathCacheTimeout;
    } else {
      enemy.pathTimer -= dt;
    }

    // Follow path
    if (enemy.path && enemy.path.length > 0) {
      const target = enemy.path[0];
      const targetX = target.x * TILE_SIZE + TILE_SIZE / 2;
      const targetY = target.y * TILE_SIZE + TILE_SIZE / 2;

      const distToWaypoint = Util.dist(enemy.x, enemy.y, targetX, targetY);

      if (distToWaypoint < 10) {
        enemy.path.shift(); // Reached waypoint
      } else {
        const angle = Util.angle(enemy.x, enemy.y, targetX, targetY);
        enemy.vx = Math.cos(angle) * enemy.speed * speedMult;
        enemy.vy = Math.sin(angle) * enemy.speed * speedMult;

        enemy.x += enemy.vx * dt;
        enemy.y += enemy.vy * dt;
      }
    } else {
      // No path - move directly (swarm behavior)
      const angle = Util.angle(enemy.x, enemy.y, player.x, player.y);
      enemy.vx = Math.cos(angle) * enemy.speed * speedMult;
      enemy.vy = Math.sin(angle) * enemy.speed * speedMult;

      enemy.x += enemy.vx * dt;
      enemy.y += enemy.vy * dt;
    }
  },

  handleAttack(enemy, player, dist, dt) {
    // Move back to chase if player out of range
    if (dist > enemy.attackRange * 1.2) {
      enemy.state = 'chase';
      return;
    }

    // Attack cooldown
    if (enemy.attackCooldown <= 0) {
      this.attack(enemy, player);
      enemy.attackCooldown = enemy.attackSpeed || 1.0;
    }
  },

  handleFlee(enemy, player, dt, speedMult) {
    // Flee away from player
    const angle = Util.angle(player.x, player.y, enemy.x, enemy.y);
    enemy.vx = Math.cos(angle) * enemy.speed * 1.5 * speedMult;
    enemy.vy = Math.sin(angle) * enemy.speed * 1.5 * speedMult;

    enemy.x += enemy.vx * dt;
    enemy.y += enemy.vy * dt;

    // Return to idle after state timer expires
    if (enemy.stateTimer <= 0) {
      enemy.state = 'idle';
    }
  },

  executeBehavior(enemy, player, dist, dt, speedMult) {
    switch(enemy.behavior) {
      case 'swarm':
        // Faster in groups
        const nearbyAllies = G.enemies.filter(e => {
          return e.type === enemy.type && Util.dist(e.x, e.y, enemy.x, enemy.y) < TILE_SIZE * 3;
        }).length;
        if (nearbyAllies > 2) {
          enemy.speed *= 1.2;
        }
        break;

      case 'ranged':
        // Maintain distance
        if (dist < TILE_SIZE * 4 && enemy.state === 'chase') {
          enemy.state = 'flee';
          enemy.stateTimer = 1.0;
        }
        break;

      case 'ambush':
        // Stay hidden until player very close
        if (enemy.state === 'idle' && dist < TILE_SIZE * 2) {
          enemy.state = 'chase';
          // Surprise attack with bonus damage
          enemy.nextAttackBonus = 2.0;
        }
        break;

      case 'guard':
        // Don't chase far from spawn
        if (enemy.spawnX && enemy.spawnY) {
          const distFromSpawn = Util.dist(enemy.x, enemy.y, enemy.spawnX, enemy.spawnY);
          if (distFromSpawn > TILE_SIZE * 5) {
            enemy.state = 'idle';
            enemy.path = this.pathfind(enemy.x, enemy.y, enemy.spawnX, enemy.spawnY);
          }
        }
        break;
    }
  },

  attack(enemy, target) {
    const isRanged = enemy.behavior === 'ranged' || enemy.type === 'archer' || enemy.type === 'mage';

    if (isRanged) {
      // Create projectile
      const angle = Util.angle(enemy.x, enemy.y, target.x, target.y);
      const projectile = {
        x: enemy.x,
        y: enemy.y,
        vx: Math.cos(angle) * 250,
        vy: Math.sin(angle) * 250,
        damage: enemy.damage,
        element: enemy.element || ELEMENT.PHYSICAL,
        speed: 250,
        lifetime: 2.0,
        owner: 'enemy',
        sprite: enemy.type
      };

      G.projectiles.push(projectile);
      SFX.playSFX('enemy_attack');
    } else {
      // Melee attack - damage handled in collision system
      SFX.playSFX('enemy_attack');
    }

    // Apply attack bonus (ambush)
    if (enemy.nextAttackBonus) {
      enemy.damage *= enemy.nextAttackBonus;
      enemy.nextAttackBonus = null;
    }
  },

  takeDamage(enemy, amount, element, knockbackX, knockbackY) {
    if (enemy.hp <= 0) return;

    // Apply defense
    let finalDamage = amount - (enemy.defense || 0);

    // Apply element resistance/weakness
    const multiplier = this.getElementMultiplier(element, enemy.element);
    finalDamage *= multiplier;

    // Death mark doubles damage
    if (enemy.deathMark) {
      finalDamage *= 2;
    }

    finalDamage = Math.max(1, Math.floor(finalDamage));

    // Apply damage
    enemy.hp -= finalDamage;

    // Visual feedback
    enemy.hitFlash = 0.15;

    // Knockback
    if (knockbackX !== undefined && knockbackY !== undefined) {
      const angle = Math.atan2(knockbackY, knockbackX);
      const force = 100;
      enemy.knockbackX = Math.cos(angle) * force;
      enemy.knockbackY = Math.sin(angle) * force;
      enemy.knockbackTimer = 0.15;
    }

    // Floating damage text
    const color = multiplier > 1 ? '#FFAA00' : '#FF4444';
    Combat.spawnFloatingText(enemy.x, enemy.y - 20, '-' + finalDamage, color);

    // Alert nearby enemies
    if (enemy.state === 'idle' || enemy.state === 'patrol') {
      enemy.state = 'chase';
      this.alertNearby(enemy);
    }

    // Death
    if (enemy.hp <= 0) {
      this.die(enemy);
    }
  },

  die(enemy) {
    enemy.state = 'dead';
    enemy.hp = 0;

    // Play sound
    SFX.playSFX('enemy_death');

    // Award XP
    const xp = enemy.xpReward || 10;
    Player.addXP(xp);

    // Drop loot
    this.dropLoot(enemy);

    // Update stats
    G.player.totalKills++;

    // Remove from array (will be handled by game loop)
    setTimeout(() => {
      const index = G.enemies.indexOf(enemy);
      if (index > -1) G.enemies.splice(index, 1);
    }, 500);
  },

  dropLoot(enemy) {
    // Random loot based on enemy type and elite status
    const lootRoll = Math.random();

    if (lootRoll < enemy.lootChance) {
      const loot = {
        x: enemy.x,
        y: enemy.y,
        type: 'item',
        item: this.generateLootItem(enemy)
      };

      if (!G.lootDrops) G.lootDrops = [];
      G.lootDrops.push(loot);
    }

    // Gold drop
    const gold = Util.randInt(5, 15) * (enemy.elite ? 2 : 1);
    G.player.gold += gold;
  },

  generateLootItem(enemy) {
    const floor = G.currentFloor || 1;

    // Elite enemies drop better loot
    const rarityBonus = enemy.elite ? 1 : 0;

    // 60% weapon, 30% armor, 10% consumable
    const typeRoll = Math.random();

    if (typeRoll < 0.6) {
      return generateWeapon(floor, rarityBonus);
    } else if (typeRoll < 0.9) {
      const slot = Util.pick(['head', 'chest', 'legs', 'boots', 'gloves', 'ring', 'amulet']);
      return this.generateArmor(floor, slot, rarityBonus);
    } else {
      // Consumables - return a simple consumable object
      return {
        type: 'consumable',
        name: Util.pick(['Health Potion', 'Mana Potion', 'Stamina Potion']),
        effect: 'heal',
        amount: 50
      };
    }
  },

  generateArmor(floor, slot, rarityBonus) {
    // Simplified armor generation
    const baseDefense = 5 + floor * 2;
    const rarity = Math.min(RARITY.LEGENDARY, rarityBonus + Math.floor(Math.random() * 3));

    return {
      type: 'armor',
      slot: slot,
      defense: Math.floor(baseDefense * (1 + rarity * 0.3)),
      rarity: rarity,
      resistance: {}, // Empty resistance object by default
      name: Util.pick(['Iron', 'Steel', 'Mythril', 'Dragon', 'Abyssal']) + ' ' +
            slot.charAt(0).toUpperCase() + slot.slice(1)
    };
  },

  alertNearby(enemy) {
    const alertRadius = TILE_SIZE * 4;

    G.enemies.forEach(e => {
      if (e === enemy) return;
      if (e.state === 'dead') return;

      const dist = Util.dist(enemy.x, enemy.y, e.x, e.y);
      if (dist <= alertRadius) {
        if (e.state === 'idle' || e.state === 'patrol') {
          e.state = 'chase';
        }
      }
    });
  },

  updateStatusEffects(enemy, dt) {
    if (!enemy.statusEffects) enemy.statusEffects = [];

    for (let i = enemy.statusEffects.length - 1; i >= 0; i--) {
      const effect = enemy.statusEffects[i];
      effect.timer += dt;

      // Tick damage
      if ((effect.type === 'poison' || effect.type === 'burn' || effect.type === 'bleed') &&
          effect.timer >= effect.tickInterval) {
        enemy.hp -= effect.tickDamage;
        effect.timer = 0;
        Combat.spawnFloatingText(enemy.x, enemy.y - 10, '-' + effect.tickDamage, '#884488');

        if (enemy.hp <= 0) {
          this.die(enemy);
        }
      }

      // Remove expired
      effect.duration -= dt;
      if (effect.duration <= 0) {
        enemy.statusEffects.splice(i, 1);
      }
    }
  },

  getElementMultiplier(attackElement, defenderElement) {
    // Element effectiveness
    const effectiveness = {
      [ELEMENT.FIRE]: { [ELEMENT.ICE]: 1.5, [ELEMENT.LIGHTNING]: 0.75 },
      [ELEMENT.ICE]: { [ELEMENT.LIGHTNING]: 1.5, [ELEMENT.FIRE]: 0.75 },
      [ELEMENT.LIGHTNING]: { [ELEMENT.FIRE]: 1.5, [ELEMENT.ICE]: 0.75 }
    };

    return effectiveness[attackElement]?.[defenderElement] || 1.0;
  },

  spawn(type, x, y, elite, floor) {
    const template = ENEMY_TYPES[type];
    if (!template) return null;

    const floorMultiplier = 1 + (floor || 1) * 0.1;

    const enemy = {
      id: 'enemy_' + Date.now() + '_' + Math.random(),
      type: type,
      name: template.name,
      x: x,
      y: y,
      spawnX: x,
      spawnY: y,
      vx: 0, vy: 0,
      w: 24, h: 24,
      hp: template.hp * floorMultiplier * (elite ? 1.5 : 1),
      maxHp: template.hp * floorMultiplier * (elite ? 1.5 : 1),
      damage: template.damage * floorMultiplier * (elite ? 1.3 : 1),
      speed: template.speed,
      defense: template.defense || 0,
      element: template.element || ELEMENT.PHYSICAL,
      behavior: template.behavior || 'chase',
      state: 'idle',
      alertRadius: template.alertRadius || TILE_SIZE * 6,
      chaseRadius: template.chaseRadius || TILE_SIZE * 10,
      attackRange: template.attackRange || TILE_SIZE,
      attackCooldown: 0,
      attackSpeed: template.attackSpeed || 1.0,
      facing: DIR.DOWN,
      path: [],
      pathTimer: 0,
      patrolPath: template.patrolPath || [],
      patrolIndex: 0,
      hitFlash: 0,
      knockbackX: 0, knockbackY: 0, knockbackTimer: 0,
      statusEffects: [],
      elite: elite || false,
      xpReward: template.xpReward * (elite ? 2 : 1),
      lootChance: template.lootChance * (elite ? 1.5 : 1),
      spriteData: template.spriteData,
      stateTimer: 0
    };

    return enemy;
  },

  pathfind(startX, startY, endX, endY) {
    // A* pathfinding
    const startTile = TileMap.pixelToTile(startX, startY);
    const endTile = TileMap.pixelToTile(endX, endY);

    // Check if end is walkable
    if (!TileMap.isWalkable(endTile.x, endTile.y)) {
      return [];
    }

    const openSet = [];
    const closedSet = new Set();
    const cameFrom = new Map();
    const gScore = new Map();
    const fScore = new Map();

    const startKey = startTile.x + ',' + startTile.y;
    const endKey = endTile.x + ',' + endTile.y;

    gScore.set(startKey, 0);
    fScore.set(startKey, this.heuristic(startTile, endTile));
    openSet.push({ x: startTile.x, y: startTile.y, f: fScore.get(startKey) });

    let iterations = 0;
    const maxIterations = 200;

    while (openSet.length > 0 && iterations < maxIterations) {
      iterations++;

      // Find node with lowest fScore
      openSet.sort((a, b) => a.f - b.f);
      const current = openSet.shift();
      const currentKey = current.x + ',' + current.y;

      // Reached goal
      if (currentKey === endKey) {
        return this.reconstructPath(cameFrom, current);
      }

      closedSet.add(currentKey);

      // Check neighbors
      const neighbors = [
        { x: current.x + 1, y: current.y },
        { x: current.x - 1, y: current.y },
        { x: current.x, y: current.y + 1 },
        { x: current.x, y: current.y - 1 }
      ];

      for (const neighbor of neighbors) {
        const neighborKey = neighbor.x + ',' + neighbor.y;

        if (closedSet.has(neighborKey)) continue;
        if (!TileMap.isWalkable(neighbor.x, neighbor.y)) continue;

        const tentativeGScore = gScore.get(currentKey) + 1;

        if (!gScore.has(neighborKey) || tentativeGScore < gScore.get(neighborKey)) {
          cameFrom.set(neighborKey, current);
          gScore.set(neighborKey, tentativeGScore);
          const h = this.heuristic(neighbor, endTile);
          fScore.set(neighborKey, tentativeGScore + h);

          if (!openSet.find(n => n.x === neighbor.x && n.y === neighbor.y)) {
            openSet.push({ x: neighbor.x, y: neighbor.y, f: fScore.get(neighborKey) });
          }
        }
      }
    }

    // No path found
    return [];
  },

  heuristic(a, b) {
    // Manhattan distance
    return Math.abs(a.x - b.x) + Math.abs(a.y - b.y);
  },

  reconstructPath(cameFrom, current) {
    const path = [{ x: current.x, y: current.y }];

    let currentKey = current.x + ',' + current.y;

    while (cameFrom.has(currentKey)) {
      const prev = cameFrom.get(currentKey);
      path.unshift({ x: prev.x, y: prev.y });
      currentKey = prev.x + ',' + prev.y;
    }

    return path;
  },

  renderAll(ctx, camera) {
    G.enemies.forEach(enemy => {
      if (enemy.state === 'dead') return;

      // Only render if visible
      const tilePos = TileMap.pixelToTile(enemy.x, enemy.y);
      if (!Fog.isVisible(tilePos.x, tilePos.y)) return;

      this.render(enemy, ctx, camera);
    });
  },

  render(enemy, ctx, camera) {
    const screenPos = Camera.worldToScreen(enemy.x, enemy.y);

    ctx.save();

    // Draw shadow
    ctx.fillStyle = 'rgba(0, 0, 0, 0.3)';
    ctx.beginPath();
    ctx.ellipse(screenPos.x, screenPos.y + 8, 10, 4, 0, 0, Math.PI * 2);
    ctx.fill();

    // Flash white when hit
    if (enemy.hitFlash > 0) {
      ctx.fillStyle = '#FFFFFF';
    } else {
      // Enemy color by type
      ctx.fillStyle = this.getEnemyColor(enemy);
    }

    // Elite glow effect
    if (enemy.elite) {
      ctx.shadowBlur = 15;
      ctx.shadowColor = '#FFD700';
    }

    // Draw body
    ctx.fillRect(screenPos.x - 10, screenPos.y - 10, 20, 20);

    // Draw head
    ctx.beginPath();
    ctx.arc(screenPos.x, screenPos.y - 14, 5, 0, Math.PI * 2);
    ctx.fill();

    ctx.shadowBlur = 0;

    // HP bar if damaged
    if (enemy.hp < enemy.maxHp) {
      const barWidth = 30;
      const barHeight = 4;
      const hpPercent = enemy.hp / enemy.maxHp;

      ctx.fillStyle = '#222222';
      ctx.fillRect(screenPos.x - barWidth / 2, screenPos.y - 25, barWidth, barHeight);

      ctx.fillStyle = enemy.elite ? '#FFD700' : '#FF4444';
      ctx.fillRect(screenPos.x - barWidth / 2, screenPos.y - 25, barWidth * hpPercent, barHeight);
    }

    // Status effect icons
    if (enemy.statusEffects && enemy.statusEffects.length > 0) {
      enemy.statusEffects.forEach((effect, i) => {
        const iconX = screenPos.x - 10 + i * 8;
        const iconY = screenPos.y - 30;

        ctx.fillStyle = this.getStatusColor(effect.type);
        ctx.fillRect(iconX, iconY, 6, 6);
      });
    }

    ctx.restore();
  },

  getEnemyColor(enemy) {
    const colors = {
      goblin: '#44AA44',
      skeleton: '#AAAAAA',
      zombie: '#668844',
      spider: '#884488',
      ghost: '#4488AA',
      archer: '#AA8844',
      mage: '#8844AA',
      warrior: '#AA4444'
    };

    return colors[enemy.type] || '#666666';
  },

  getStatusColor(type) {
    const colors = {
      poison: '#44FF44',
      burn: '#FF4444',
      freeze: '#4444FF',
      stun: '#FFD700',
      bleed: '#AA0000'
    };

    return colors[type] || '#888888';
  }
};
