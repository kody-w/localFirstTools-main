// ============================================================
// CREEP SIEGE: ANCIENT OFFENSIVE - UPDATE
// ============================================================

if (mode === 'update') {
  if (G.phase === 'victory' || G.phase === 'defeat') return;
  G.kcd = Math.max(0, G.kcd - 1);
  G.shake = Math.max(0, G.shake - 0.4);
  G.flash = Math.max(0, G.flash - 2);
  var spd = (dt || 0.016) * 60;

  // Particles
  G.particles = G.particles.filter(function(p) {
    p.x += p.vx; p.y += p.vy; p.vy += (p.grav || 0); p.life--; return p.life > 0;
  });
  G.dmgNums = G.dmgNums.filter(function(d) { d.y -= 0.5; d.life--; return d.life > 0; });

  // ═══════════════════════════════════════
  // SPAWN PHASE: Pick creeps to send
  // ═══════════════════════════════════════
  if (G.phase === 'spawn') {
    // Lane select
    if ((K('w') || K('ArrowUp')) && G.kcd <= 0) {
      G.spawnLane = (G.spawnLane + 2) % 3; G.kcd = 10; snd.beep();
    }
    if ((K('s') || K('ArrowDown')) && G.kcd <= 0) {
      G.spawnLane = (G.spawnLane + 1) % 3; G.kcd = 10; snd.beep();
    }

    // Creep type select
    if ((K('a') || K('ArrowLeft')) && G.kcd <= 0) {
      G.selIdx = (G.selIdx + G.creepTypes.length - 1) % G.creepTypes.length; G.kcd = 10; snd.beep();
    }
    if ((K('d') || K('ArrowRight')) && G.kcd <= 0) {
      G.selIdx = (G.selIdx + 1) % G.creepTypes.length; G.kcd = 10; snd.beep();
    }

    // Queue creep
    if ((K(' ') || K('Enter')) && G.kcd <= 0) {
      var ct = G.creepTypes[G.selIdx];
      if (G.gold >= ct.cost) {
        G.gold -= ct.cost;
        G.spawnQueue.push({ type: ct.id, lane: G.spawnLane });
        G.aiMemory[ct.id] = (G.aiMemory[ct.id] || 0) + 1;
        snd.pickup();
        G.kcd = 8;
      } else {
        snd.tone(100, 0.05, 0.05); G.kcd = 15;
      }
    }

    // Launch wave
    if (K('f') && G.spawnQueue.length > 0 && G.kcd <= 0) {
      G.phase = 'battle';
      G.reached = 0;
      G.waveCreepsAlive = G.spawnQueue.length;
      G.spawnTimer = 0;
      G.waveComplete = false;
      snd.tone(300, 0.1, 0.08);
      G.kcd = 20;
    }
    return;
  }

  // ═══════════════════════════════════════
  // EVOLVE PHASE: Pick evolution
  // ═══════════════════════════════════════
  if (G.phase === 'evolve') {
    if (!G.evoChoices) {
      // Pick 3 random evolutions
      var pool = G.evoPool.slice();
      // Shuffle
      for (var i = pool.length - 1; i > 0; i--) { var j = Math.floor(Math.random()*(i+1)); var t=pool[i]; pool[i]=pool[j]; pool[j]=t; }
      G.evoChoices = pool.slice(0, 3);
      G.selIdx = 0;
    }

    if ((K('w') || K('ArrowUp')) && G.kcd <= 0) { G.selIdx = (G.selIdx + 2) % 3; G.kcd = 10; snd.beep(); }
    if ((K('s') || K('ArrowDown')) && G.kcd <= 0) { G.selIdx = (G.selIdx + 1) % 3; G.kcd = 10; snd.beep(); }
    if ((K(' ') || K('Enter')) && G.kcd <= 0) {
      var chosen = G.evoChoices[G.selIdx];
      chosen.apply();
      G.evolutions.push(chosen.id);
      G.evoChoices = null;
      G.flash = 20; G.flashC = '#ff4444';
      snd.score();

      // Next wave setup
      G.wave++;
      if (G.wave > G.maxWave) {
        G.phase = 'victory'; G.score += G.gold * 10;
        snd.win(); return;
      }
      G.gold += 30 + G.wave * 5 + (G._bonusGold || 0);
      G.totalGold += 30 + G.wave * 5 + (G._bonusGold || 0);
      G.spawnQueue = [];
      // AI places new towers
      G.placeTowers(G.wave);
      G.phase = 'spawn';
      G.kcd = 20;
    }
    return;
  }

  // ═══════════════════════════════════════
  // BATTLE PHASE
  // ═══════════════════════════════════════
  if (G.phase === 'battle') {
    // Spawn from queue
    G.spawnTimer -= spd;
    if (G.spawnTimer <= 0 && G.spawnQueue.length > 0) {
      var sq = G.spawnQueue.shift();
      var ct = G.creepTypes.find(function(c) { return c.id === sq.type; });
      if (ct) {
        var ly = G.laneRows[sq.lane];
        var creep = {
          x: 4, y: ly * G.TS + G.TS / 2,
          gx: 0, gy: ly,
          hp: ct.hp, maxHp: ct.hp,
          speed: ct.speed,
          armor: ct.armor, magic: ct.magic,
          type: ct.id, icon: ct.icon,
          reward: ct.reward,
          slowTimer: 0, dotTimer: 0, dotDmg: 0,
          invisTimer: ct.id === 'speed' ? (G._invisTime || 0) : 0
        };
        G.creeps.push(creep);
      }
      G.spawnTimer = 15; // frames between spawns
    }

    // ─── Update creeps ───
    G.creeps.forEach(function(c) {
      // Slow effect
      var spdMult = 1;
      if (c.slowTimer > 0) { c.slowTimer -= spd; spdMult = 0.5; }
      // DoT
      if (c.dotTimer > 0) { c.dotTimer -= spd; c.hp -= c.dotDmg * (dt || 0.016); }
      // Invis countdown
      if (c.invisTimer > 0) c.invisTimer -= spd;
      // Regen
      if (G._regen > 0) c.hp = Math.min(c.maxHp, c.hp + G._regen * (dt || 0.016));

      // Follow flow field
      var gx = Math.floor(c.x / G.TS);
      var gy = Math.floor(c.y / G.TS);
      gx = Math.max(0, Math.min(G.GW - 1, gx));
      gy = Math.max(0, Math.min(G.GH - 1, gy));
      c.gx = gx; c.gy = gy;

      var flow = G.flowField[gy] && G.flowField[gy][gx];
      if (flow) {
        var tx = (gx + flow.dx) * G.TS + G.TS / 2;
        var ty = (gy + flow.dy) * G.TS + G.TS / 2;
        var dx = tx - c.x, dy = ty - c.y;
        var dist = Math.sqrt(dx * dx + dy * dy);
        if (dist > 1) {
          c.x += (dx / dist) * c.speed * spdMult * spd;
          c.y += (dy / dist) * c.speed * spdMult * spd;
        }
      }

      // Reached the goal?
      if (G.grid[gy] && G.grid[gy][gx] === 3) {
        c.hp = 0;
        G.reached++;
        G.score += 50 * G.wave;
        snd.score();
        G.flash = 10; G.flashC = '#44ff44';
        for (var i = 0; i < 8; i++)
          G.particles.push({ x:c.x, y:c.y, vx:(Math.random()-0.5)*4, vy:(Math.random()-0.5)*4, life:20, c:'#44ff44', s:2, grav:0 });
      }
    });

    // ─── Tower AI: target + shoot ───
    G.towers.forEach(function(t) {
      t.cooldown = Math.max(0, t.cooldown - spd);
      if (t.cooldown > 0 || t.hp <= 0) return;

      // Find nearest visible creep in range
      var best = null, bd = 9999;
      G.creeps.forEach(function(c) {
        if (c.hp <= 0 || c.invisTimer > 0) return;
        var dx = c.x - t.x, dy = c.y - t.y;
        var dist = Math.sqrt(dx*dx + dy*dy);
        if (dist < t.range && dist < bd) { best = c; bd = dist; }
      });

      if (best) {
        t.cooldown = t.rate;
        // Fire projectile
        var dx = best.x - t.x, dy = best.y - t.y;
        var dist = Math.sqrt(dx*dx + dy*dy);
        G.projectiles.push({
          x: t.x, y: t.y,
          vx: (dx/dist) * t.projSpd, vy: (dy/dist) * t.projSpd,
          dmg: t.dmg, color: t.projC,
          slow: t.slow, dot: t.dot, splash: t.splash, manaburn: t.manaburn,
          life: 60, owner: t
        });
      }
    });

    // ─── Projectile collision ───
    G.projectiles = G.projectiles.filter(function(p) {
      p.x += p.vx * spd; p.y += p.vy * spd; p.life -= spd;

      // Hit creep?
      for (var i = 0; i < G.creeps.length; i++) {
        var c = G.creeps[i];
        if (c.hp <= 0) continue;
        var dx = p.x - c.x, dy = p.y - c.y;
        if (Math.sqrt(dx*dx + dy*dy) < 8) {
          // Apply damage (reduced by armor for physical, magic res for magic)
          var dmg = p.dmg;
          if (p.manaburn) dmg = Math.max(1, dmg - c.magic * 3);
          else dmg = Math.max(1, dmg - c.armor * 2);

          c.hp -= dmg;
          G.dmgNums.push({ x:c.x, y:c.y-8, v:Math.floor(dmg), life:25, c:'#ff4444' });

          // Slow
          if (p.slow > 0) c.slowTimer = Math.max(c.slowTimer, 60);
          // DoT
          if (p.dot > 0) { c.dotTimer = 90; c.dotDmg = p.dot; }

          // Splash damage
          if (p.splash > 0) {
            G.creeps.forEach(function(c2) {
              if (c2 === c || c2.hp <= 0) return;
              var d2 = Math.sqrt((c2.x-p.x)*(c2.x-p.x)+(c2.y-p.y)*(c2.y-p.y));
              if (d2 < p.splash) {
                var sd = Math.max(1, Math.floor(dmg * 0.5));
                c2.hp -= sd;
                G.dmgNums.push({ x:c2.x, y:c2.y-8, v:sd, life:20, c:'#ff8844' });
              }
            });
            // Splash visual
            for (var j = 0; j < 6; j++)
              G.particles.push({ x:p.x, y:p.y, vx:(Math.random()-0.5)*3, vy:(Math.random()-0.5)*3, life:12, c:'#ff8844', s:2, grav:0 });
          }

          // Thorns: damage tower
          if (G._thorns > 0 && p.owner) {
            p.owner.hp -= G._thorns;
            G.dmgNums.push({ x:p.owner.x, y:p.owner.y-8, v:G._thorns, life:20, c:'#ffff44' });
          }

          // Lifesteal
          if (G._lifesteal > 0) {
            c.hp = Math.min(c.maxHp, c.hp + dmg * G._lifesteal);
          }

          // Particle
          G.particles.push({ x:c.x, y:c.y, vx:(Math.random()-0.5)*2, vy:-1-Math.random()*2, life:10, c:p.color, s:2, grav:0.1 });
          snd.tone(350 + Math.random()*100, 0.02, 0.02);
          return false; // destroy projectile
        }
      }
      return p.life > 0;
    });

    // ─── Remove dead creeps ───
    G.creeps = G.creeps.filter(function(c) {
      if (c.hp <= 0) {
        G.waveCreepsAlive--;
        // Split on death evolution
        if (G._splitOnDeath > 0 && c.type !== 'split') {
          for (var s = 0; s < G._splitOnDeath; s++) {
            G.creeps.push({
              x: c.x + (Math.random()-0.5)*8, y: c.y + (Math.random()-0.5)*8,
              gx: c.gx, gy: c.gy,
              hp: Math.ceil(c.maxHp * 0.3), maxHp: Math.ceil(c.maxHp * 0.3),
              speed: c.speed * 1.2, armor: 0, magic: 0,
              type: 'split', icon: '·', reward: 0,
              slowTimer: 0, dotTimer: 0, dotDmg: 0, invisTimer: 0
            });
            G.waveCreepsAlive++;
          }
        }
        // Death particles
        for (var i = 0; i < 5; i++)
          G.particles.push({ x:c.x, y:c.y, vx:(Math.random()-0.5)*3, vy:(Math.random()-0.5)*3, life:15, c:'#ff4444', s:1.5, grav:0.05 });
        return false;
      }
      return true;
    });

    // ─── Remove dead towers ───
    G.towers = G.towers.filter(function(t) {
      if (t.hp <= 0) {
        G.score += 25;
        for (var i = 0; i < 6; i++)
          G.particles.push({ x:t.x, y:t.y, vx:(Math.random()-0.5)*3, vy:-Math.random()*3, life:20, c:t.color, s:2, grav:0.1 });
        snd.explode();
        return false;
      }
      return true;
    });

    // ─── Check wave end ───
    if (G.spawnQueue.length === 0 && G.creeps.length === 0 && !G.waveComplete) {
      G.waveComplete = true;
      if (G.reached >= G.lives) {
        // Wave won!
        G.score += G.reached * 100;
        G.gold += G.reached * 5;
        G.flash = 20; G.flashC = '#44ff44';
        snd.win();
        // Go to evolve phase
        G.phase = 'evolve';
      } else {
        // Wave failed — you can retry
        G.score += G.reached * 30;
        G.flash = 15; G.flashC = '#ff4444';
        G.shake = 8;
        snd.die();
        // Refund some gold and retry
        G.gold += 15;
        G.spawnQueue = [];
        G.phase = 'spawn';
      }
    }
  }
}
