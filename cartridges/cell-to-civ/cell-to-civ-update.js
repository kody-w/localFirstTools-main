// ============================================================
// CELL TO CIVILIZATION - UPDATE
// ============================================================

if (mode === 'update') {
  if (G.over || G.won) return;
  if (G.transition > 0) { G.transition--; return; }

  G.kcd = Math.max(0, G.kcd - 1);
  G.shake = Math.max(0, G.shake - 0.5);
  G.flash = Math.max(0, G.flash - 2);
  var spd = G.speed * (dt || 0.016) * 60;
  G.time += 0.00001 * spd;

  // Update particles
  G.particles = G.particles.filter(function(p) {
    p.x += p.vx; p.y += p.vy; p.vy += (p.grav || 0);
    p.life--; return p.life > 0;
  });

  // Speed controls
  if (K('1')) G.speed = 1;
  if (K('2')) G.speed = 2;
  if (K('3')) G.speed = 5;
  if (K('4')) G.speed = 10;
  if (K('Tab') && G.kcd <= 0) { G.showStats = !G.showStats; G.kcd = 15; }

  // ─── MUTATION CHOICE POPUP ───
  if (G.mutChoice) {
    if ((K('w') || K('ArrowUp')) && G.kcd <= 0) { G.selIdx = 0; G.kcd = 10; snd.beep(); }
    if ((K('s') || K('ArrowDown')) && G.kcd <= 0) { G.selIdx = 1; G.kcd = 10; snd.beep(); }
    if ((K(' ') || K('Enter')) && G.kcd <= 0) {
      var chosen = G.mutChoice[G.selIdx];
      G.mutations.push(chosen.id);
      G.history.push({ era: G.era, time: G.time, event: 'Mutation: ' + chosen.name });
      // Apply mutation
      if (chosen.id === 'speed') G.cell.speed += 0.3;
      if (chosen.id === 'size') G.cell.size += 1;
      if (chosen.id === 'armor') G.cell.armor += 1;
      if (chosen.id === 'flagella') G.cell.flagella += 1;
      if (chosen.id === 'photosynthesis') G.cell.photo += 1;
      if (chosen.id === 'toxin') G.cell.toxin += 1;
      G.mutChoice = null;
      G.kcd = 15;
      G.flash = 20; G.flashC = '#3ddc84';
      snd.score();
      // Burst particles
      for (var i = 0; i < 12; i++)
        G.particles.push({ x: G.cell.x, y: G.cell.y, vx: (Math.random()-0.5)*4, vy: (Math.random()-0.5)*4, life: 20, c: '#3ddc84', s: 2, grav: 0 });
    }
    return;
  }

  // ═══════════════════════════════════════
  // ERA 1: PRIMORDIAL
  // ═══════════════════════════════════════
  if (G.era === 1) {
    var c = G.cell;
    var ms = c.speed * (1 + c.flagella * 0.15);

    // Movement
    if (K('a') || K('ArrowLeft')) c.vx -= ms * 0.2;
    if (K('d') || K('ArrowRight')) c.vx += ms * 0.2;
    if (K('w') || K('ArrowUp')) c.vy -= ms * 0.2;
    if (K('s') || K('ArrowDown')) c.vy += ms * 0.2;
    c.vx *= 0.92; c.vy *= 0.92;
    c.x += c.vx * spd; c.y += c.vy * spd;
    c.x = Math.max(4, Math.min(252, c.x));
    c.y = Math.max(4, Math.min(220, c.y));

    // Passive energy from photosynthesis
    c.energy += c.photo * 0.05 * spd;

    // Food
    G.food.forEach(function(f) {
      f.x += f.vx * spd; f.y += f.vy * spd;
      if (f.x < 0 || f.x > 256) f.vx *= -1;
      if (f.y < 0 || f.y > 224) f.vy *= -1;
      var dx = c.x - f.x, dy = c.y - f.y;
      if (Math.sqrt(dx*dx + dy*dy) < c.size + f.size) {
        c.energy += 8 + f.size * 2;
        f.x = Math.random() * 256; f.y = Math.random() * 224;
        snd.pickup();
        for (var i = 0; i < 4; i++)
          G.particles.push({ x: f.x, y: f.y, vx: (Math.random()-0.5)*3, vy: (Math.random()-0.5)*3, life: 12, c: '#3ddc84', s: 1.5, grav: 0 });
      }
    });

    // Predators
    G.predators.forEach(function(p) {
      // Chase player
      var dx = c.x - p.x, dy = c.y - p.y;
      var dist = Math.sqrt(dx*dx + dy*dy);
      if (dist > 0 && dist < 120) {
        p.vx += (dx / dist) * 0.06 * spd;
        p.vy += (dy / dist) * 0.06 * spd;
      }
      p.vx *= 0.97; p.vy *= 0.97;
      p.x += p.vx * spd; p.y += p.vy * spd;
      if (p.x < 0 || p.x > 256) p.vx *= -1;
      if (p.y < 0 || p.y > 224) p.vy *= -1;

      if (dist < c.size + p.size) {
        if (c.toxin > 0) {
          p.hp -= c.toxin * 0.5;
          if (p.hp <= 0) {
            p.x = Math.random() * 256; p.y = Math.random() * 224; p.hp = 3;
            c.energy += 15;
            G.shake = 5;
            snd.explode();
          }
        } else {
          c.energy -= (8 - c.armor * 2);
          G.shake = 8;
          snd.tone(150, 0.08, 0.06, 'sawtooth');
        }
      }
    });

    // Energy cap and death
    c.energy = Math.min(100, c.energy);
    if (c.energy <= 0) { G.over = true; snd.die(); return; }

    // Cell division
    if (c.energy >= 100) {
      c.energy = 50;
      G.pop++;
      G.divCount++;
      snd.tone(500, 0.06, 0.05);
      for (var i = 0; i < 8; i++)
        G.particles.push({ x: c.x, y: c.y, vx: (Math.random()-0.5)*5, vy: (Math.random()-0.5)*5, life: 25, c: '#4af', s: 2, grav: 0 });

      // Mutation every 5 divisions
      if (G.divCount % 5 === 0) {
        var pool = G.mutPool.slice();
        var a = pool.splice(Math.floor(Math.random() * pool.length), 1)[0];
        var b = pool.splice(Math.floor(Math.random() * pool.length), 1)[0];
        G.mutChoice = [a, b];
        G.selIdx = 0;
      }

      // Add more predators as pop grows
      if (G.pop % 15 === 0 && G.predators.length < 8) {
        G.predators.push({ x: Math.random() * 256, y: Math.random() * 224, vx: 0, vy: 0, size: 6 + G.pop * 0.1, hp: 3 + Math.floor(G.pop / 10) });
      }
    }

    // Camera zoom out as pop grows
    G.cam.tz = Math.max(0.5, 1 - G.pop * 0.005);

    // ERA TRANSITION → Organism
    if (G.pop >= 50) {
      G.era = 2;
      G.transition = 90;
      G.transMsg = 'ERA 2: ORGANISM';
      G.flash = 40; G.flashC = '#5a8a3a';
      G.history.push({ era: 2, time: G.time, event: 'Multicellular life emerges' });
      snd.win();
      // Spawn ecosystem
      for (var i = 0; i < 8; i++) {
        G.organisms.push({
          x: Math.random() * 256, y: Math.random() * 224,
          vx: (Math.random()-0.5)*1, vy: (Math.random()-0.5)*1,
          size: 3 + Math.random() * 4,
          type: Math.random() < 0.5 ? 'prey' : 'predator',
          hp: 5, energy: 50
        });
      }
      G.cam.tz = 1;
    }
  }

  // ═══════════════════════════════════════
  // ERA 2: ORGANISM
  // ═══════════════════════════════════════
  if (G.era === 2) {
    var cr = G.creature;
    var ms = G.cell.speed * 1.2;

    // Movement with stamina
    var sprint = K('f') || K('Enter');
    var moveSpd = sprint && cr.stamina > 0 ? ms * 1.8 : ms;
    if (sprint && cr.stamina > 0) cr.stamina -= 0.3 * spd;
    else cr.stamina = Math.min(cr.maxSt, cr.stamina + 0.1 * spd);

    if (K('a') || K('ArrowLeft')) cr.vx -= moveSpd * 0.15;
    if (K('d') || K('ArrowRight')) cr.vx += moveSpd * 0.15;
    if (K('w') || K('ArrowUp')) cr.vy -= moveSpd * 0.15;
    if (K('s') || K('ArrowDown')) cr.vy += moveSpd * 0.15;
    cr.vx *= 0.93; cr.vy *= 0.93;
    cr.x += cr.vx * spd; cr.y += cr.vy * spd;
    cr.x = Math.max(8, Math.min(248, cr.x));
    cr.y = Math.max(8, Math.min(216, cr.y));

    // Photosynthesis passive energy in organism era
    G.cell.energy += G.cell.photo * 0.03 * spd;
    G.cell.energy = Math.min(100, G.cell.energy);

    // Organisms AI
    G.organisms.forEach(function(o) {
      var dx = cr.x - o.x, dy = cr.y - o.y;
      var dist = Math.sqrt(dx*dx + dy*dy);
      if (o.type === 'prey' && dist < 80) {
        o.vx -= (dx / dist) * 0.04 * spd; // flee
        o.vy -= (dy / dist) * 0.04 * spd;
      } else if (o.type === 'predator' && dist < 100) {
        o.vx += (dx / dist) * 0.03 * spd; // chase
        o.vy += (dy / dist) * 0.03 * spd;
      }
      o.vx += (Math.random() - 0.5) * 0.1;
      o.vy += (Math.random() - 0.5) * 0.1;
      o.vx *= 0.96; o.vy *= 0.96;
      o.x += o.vx * spd; o.y += o.vy * spd;
      if (o.x < 4 || o.x > 252) o.vx *= -1;
      if (o.y < 4 || o.y > 220) o.vy *= -1;

      if (dist < G.cell.size + o.size + 4) {
        if (o.type === 'prey') {
          G.cell.energy += 12;
          G.pop += 2;
          o.x = Math.random() * 256; o.y = Math.random() * 224;
          o.hp = 5;
          snd.pickup();
          for (var j = 0; j < 5; j++)
            G.particles.push({ x: o.x, y: o.y, vx: (Math.random()-0.5)*3, vy: (Math.random()-0.5)*3, life: 15, c: '#8B4513', s: 2, grav: 0.05 });
        } else {
          G.cell.energy -= (5 - G.cell.armor);
          G.shake = 6;
          snd.tone(180, 0.06, 0.05, 'sawtooth');
        }
      }
    });

    // Reproduce
    if (G.cell.energy >= 100) {
      G.cell.energy = 50;
      G.pop += 5;
      snd.tone(600, 0.05, 0.04);
      // Spawn new ecosystem creature
      if (G.organisms.length < 16) {
        G.organisms.push({
          x: Math.random() * 256, y: Math.random() * 224,
          vx: 0, vy: 0, size: 3 + Math.random() * 3,
          type: Math.random() < 0.6 ? 'prey' : 'predator',
          hp: 5, energy: 50
        });
      }
    }

    if (G.cell.energy <= 0) { G.over = true; snd.die(); return; }

    // ERA TRANSITION → Tribal
    if (G.pop >= 100) {
      G.era = 3;
      G.transition = 90;
      G.transMsg = 'ERA 3: TRIBAL';
      G.flash = 40; G.flashC = '#ff8844';
      G.history.push({ era: 3, time: G.time, event: G.tribeName + ' forms tribal society' });
      snd.win();
      // Spawn initial units
      for (var i = 0; i < 8; i++) {
        G.units.push({
          x: 100 + Math.random() * 56, y: 90 + Math.random() * 44,
          role: i < 3 ? 'gatherer' : i < 5 ? 'hunter' : i < 7 ? 'builder' : 'scout',
          tx: 128, ty: 112, hp: 10, maxHp: 10, carrying: 0
        });
      }
      // Spawn enemy tribe
      for (var i = 0; i < 4; i++) {
        G.enemies.push({
          x: 200 + Math.random() * 40, y: 30 + Math.random() * 40,
          hp: 8, maxHp: 8, vx: 0, vy: 0, atkCd: 0
        });
      }
      G.cam.tz = 1;
    }
  }

  // ═══════════════════════════════════════
  // ERA 3: TRIBAL
  // ═══════════════════════════════════════
  if (G.era === 3) {
    // Click/key to move selected units
    // Build menu toggle
    if (K('b') && G.kcd <= 0) { G.buildMenu = !G.buildMenu; G.selIdx = 0; G.kcd = 15; snd.beep(); }

    if (G.buildMenu) {
      if ((K('w') || K('ArrowUp')) && G.kcd <= 0) { G.selIdx = (G.selIdx + G.buildOpts.length - 1) % G.buildOpts.length; G.kcd = 10; snd.beep(); }
      if ((K('s') || K('ArrowDown')) && G.kcd <= 0) { G.selIdx = (G.selIdx + 1) % G.buildOpts.length; G.kcd = 10; snd.beep(); }
      if ((K(' ') || K('Enter')) && G.kcd <= 0) {
        var opt = G.buildOpts[G.selIdx];
        var canBuild = true;
        for (var rk in opt.cost) { if ((G.res[rk] || 0) < opt.cost[rk]) canBuild = false; }
        if (canBuild) {
          for (var rk in opt.cost) G.res[rk] -= opt.cost[rk];
          G.buildings.push({ x: 100 + Math.random() * 56, y: 90 + Math.random() * 44, type: opt.name, icon: opt.icon });
          G.buildMenu = false;
          G.kcd = 15;
          snd.score();
          G.history.push({ era: 3, time: G.time, event: 'Built ' + opt.name });
          // Building a Totem can trigger tech discovery
          if (opt.name === 'Totem') {
            var avail = G.allTechs.filter(function(t) { return G.techs.indexOf(t) === -1; });
            if (avail.length > 0) {
              var tech = avail[Math.floor(Math.random() * avail.length)];
              G.techs.push(tech);
              G.history.push({ era: 3, time: G.time, event: 'Discovered: ' + tech });
              G.flash = 25; G.flashC = '#ffaa00';
            }
          }
        } else {
          snd.tone(100, 0.05, 0.05);
        }
      }
      return; // pause game while in build menu
    }

    // Unit AI
    G.units.forEach(function(u) {
      // Move toward target
      var dx = u.tx - u.x, dy = u.ty - u.y;
      var dist = Math.sqrt(dx*dx + dy*dy);
      if (dist > 2) {
        u.x += (dx / dist) * 1.2 * spd;
        u.y += (dy / dist) * 1.2 * spd;
      }

      // Role behavior
      if (u.role === 'gatherer' && dist < 5) {
        G.res.food += 0.02 * spd;
        G.res.wood += 0.015 * spd;
        // Wander to new gather point
        if (Math.random() < 0.005) {
          u.tx = 20 + Math.random() * 216;
          u.ty = 20 + Math.random() * 184;
        }
      }
      if (u.role === 'builder' && dist < 5) {
        G.res.stone += 0.01 * spd;
        G.res.wood += 0.01 * spd;
        if (Math.random() < 0.005) { u.tx = 60 + Math.random() * 136; u.ty = 60 + Math.random() * 104; }
      }
      if (u.role === 'scout') {
        if (Math.random() < 0.01) { u.tx = Math.random() * 256; u.ty = Math.random() * 224; }
        // Scouts can discover tech
        if (Math.random() < 0.0005 * spd) {
          var avail = G.allTechs.filter(function(t) { return G.techs.indexOf(t) === -1; });
          if (avail.length > 0) {
            var tech = avail[Math.floor(Math.random() * avail.length)];
            G.techs.push(tech);
            G.history.push({ era: 3, time: G.time, event: 'Scout discovered: ' + tech });
            G.flash = 25; G.flashC = '#ffaa00';
            snd.score();
          }
        }
      }
      if (u.role === 'hunter') {
        // Hunt nearest enemy
        var nearest = null, nd = 999;
        G.enemies.forEach(function(e) {
          var d2 = Math.abs(u.x-e.x) + Math.abs(u.y-e.y);
          if (d2 < nd) { nd = d2; nearest = e; }
        });
        if (nearest && nd < 100) {
          u.tx = nearest.x; u.ty = nearest.y;
          if (nd < 10) {
            nearest.hp -= 0.1 * spd;
            if (nearest.hp <= 0) {
              G.res.food += 10;
              nearest.x = 190 + Math.random() * 50; nearest.y = 20 + Math.random() * 50;
              nearest.hp = nearest.maxHp;
              snd.hit();
            }
          }
        } else {
          if (Math.random() < 0.005) { u.tx = 20 + Math.random() * 216; u.ty = 20 + Math.random() * 184; }
        }
      }
    });

    // Enemy AI
    G.enemies.forEach(function(e) {
      e.vx += (Math.random() - 0.5) * 0.2;
      e.vy += (Math.random() - 0.5) * 0.2;
      e.vx *= 0.95; e.vy *= 0.95;
      // Occasionally raid toward center
      if (Math.random() < 0.002) { e.vx += (128 - e.x) * 0.01; e.vy += (112 - e.y) * 0.01; }
      e.x += e.vx * spd; e.y += e.vy * spd;
      e.x = Math.max(4, Math.min(252, e.x)); e.y = Math.max(4, Math.min(220, e.y));

      // Attack nearby units
      G.units.forEach(function(u) {
        if (Math.abs(e.x - u.x) + Math.abs(e.y - u.y) < 12) {
          u.hp -= 0.05 * spd;
          if (u.hp <= 0) { u.x = 128; u.y = 112; u.hp = u.maxHp; G.shake = 4; snd.tone(120, 0.06, 0.05); }
        }
      });
    });

    // Unit select with keys (cycle roles)
    if (K('r') && G.kcd <= 0) {
      // Cycle selected role
      var roles = ['gatherer','hunter','builder','scout'];
      G.selIdx = (G.selIdx + 1) % roles.length;
      // Move all of that role to cursor area
      var role = roles[G.selIdx];
      G.units.forEach(function(u) {
        if (u.role === role) { u.tx = mx || 128; u.ty = my || 112; }
      });
      G.kcd = 15;
      snd.beep();
    }

    // Population from food
    if (G.res.food >= 30 && G.units.length < 20) {
      G.res.food -= 30;
      G.units.push({
        x: 128, y: 112,
        role: ['gatherer','hunter','builder','scout'][Math.floor(Math.random()*4)],
        tx: 100 + Math.random() * 56, ty: 90 + Math.random() * 44,
        hp: 10, maxHp: 10, carrying: 0
      });
    }

    // ERA TRANSITION → Civilization
    if (G.techs.length >= 5) {
      G.era = 4;
      G.transition = 90;
      G.transMsg = 'ERA 4: CIVILIZATION';
      G.flash = 40; G.flashC = '#daa520';
      G.history.push({ era: 4, time: G.time, event: G.speciesName + ' founds first city' });
      snd.win();
      // Found first city at center
      var ch = G.hexes.find(function(h) { return h.hx === 8 && h.hy === 8; });
      if (ch) { ch.owner = 'player'; ch.building = 'city'; }
      G.cities.push({ name: G.genName(2), hx: 8, hy: 8, pop: 100 });
      // AI civ
      G.aiCivs.push({ name: G.genName(2), hx: 2, hy: 2, cities: 1 });
      var ah = G.hexes.find(function(h) { return h.hx === 2 && h.hy === 2; });
      if (ah) { ah.owner = 'ai'; ah.building = 'city'; }
      G.diplomacy['ai0'] = 'neutral';
      G.cam.tz = 0.6;
    }
  }

  // ═══════════════════════════════════════
  // ERA 4: CIVILIZATION
  // ═══════════════════════════════════════
  if (G.era === 4) {
    // Scroll map
    if (K('a') || K('ArrowLeft')) G.cam.tx -= 2 * spd;
    if (K('d') || K('ArrowRight')) G.cam.tx += 2 * spd;
    if (K('w') || K('ArrowUp')) G.cam.ty -= 2 * spd;
    if (K('s') || K('ArrowDown')) G.cam.ty += 2 * spd;
    G.cam.tx = Math.max(0, Math.min(256, G.cam.tx));
    G.cam.ty = Math.max(0, Math.min(256, G.cam.ty));

    // Resources from cities
    G.cities.forEach(function(c) {
      G.civRes.food += 0.03 * spd;
      G.civRes.prod += 0.02 * spd;
      G.civRes.gold += 0.01 * spd;
      c.pop += 0.01 * spd;
    });

    // Research
    if (G.civResearching) {
      G.civRes.science += 0.015 * spd;
      G.civResProgress += 0.015 * spd;
      if (G.civResProgress >= 1) {
        G.civTechs.push(G.civResearching);
        G.history.push({ era: 4, time: G.time, event: 'Researched: ' + G.civResearching });
        G.flash = 25; G.flashC = '#daa520';
        snd.score();
        if (G.civResearching === 'rocketry') {
          G.era = 5;
          G.transition = 100;
          G.transMsg = 'ERA 5: STELLAR';
          G.flash = 50; G.flashC = '#8844ff';
          G.history.push({ era: 5, time: G.time, event: G.speciesName + ' reaches for the stars' });
          snd.win();
          // Recalculate planet compatibility with final mutations
          G.planets.forEach(function(p) {
            var compat = 50;
            G.mutations.forEach(function(m) {
              if (m === 'armor' && p.type === 'rocky') compat += 15;
              if (m === 'photosynthesis' && p.type === 'ocean') compat += 20;
              if (m === 'toxin' && p.type === 'volcanic') compat += 15;
              if (m === 'flagella' && p.type === 'gas') compat += 10;
              if (m === 'size' && p.type === 'ice') compat += 10;
            });
            p.compatible = Math.min(100, compat);
          });
          G.cam.tz = 1;
        }
        G.civResearching = null;
        G.civResProgress = 0;
      }
    }

    // Build menu for research
    if (K('b') && G.kcd <= 0 && !G.civResearching) {
      G.buildMenu = !G.buildMenu;
      G.selIdx = 0;
      G.kcd = 15;
      snd.beep();
    }

    if (G.buildMenu && !G.civResearching) {
      var avail = G.allCivTechs.filter(function(t) { return G.civTechs.indexOf(t) === -1; });
      if ((K('w') || K('ArrowUp')) && G.kcd <= 0) { G.selIdx = (G.selIdx + avail.length - 1) % avail.length; G.kcd = 10; snd.beep(); }
      if ((K('s') || K('ArrowDown')) && G.kcd <= 0) { G.selIdx = (G.selIdx + 1) % avail.length; G.kcd = 10; snd.beep(); }
      if ((K(' ') || K('Enter')) && G.kcd <= 0 && avail.length > 0) {
        G.civResearching = avail[G.selIdx];
        G.civResProgress = 0;
        G.buildMenu = false;
        G.kcd = 15;
        snd.tone(400, 0.05, 0.04);
        G.history.push({ era: 4, time: G.time, event: 'Began researching: ' + G.civResearching });
      }
      return;
    }

    // Expand: claim adjacent hexes with E key
    if (K('e') && G.kcd <= 0 && G.civRes.gold >= 10) {
      var claimed = false;
      for (var i = 0; i < G.hexes.length && !claimed; i++) {
        var h = G.hexes[i];
        if (h.owner !== null) continue;
        // Check adjacency to owned hex
        for (var j = 0; j < G.hexes.length; j++) {
          var o = G.hexes[j];
          if (o.owner === 'player' && Math.abs(o.hx - h.hx) <= 1 && Math.abs(o.hy - h.hy) <= 1) {
            h.owner = 'player';
            G.civRes.gold -= 10;
            claimed = true;
            snd.pickup();
            break;
          }
        }
      }
      G.kcd = 15;
    }

    // AI civ slowly expands
    if (Math.random() < 0.001 * spd) {
      for (var i = 0; i < G.hexes.length; i++) {
        var h = G.hexes[i];
        if (h.owner !== null) continue;
        for (var j = 0; j < G.hexes.length; j++) {
          var o = G.hexes[j];
          if (o.owner === 'ai' && Math.abs(o.hx - h.hx) <= 1 && Math.abs(o.hy - h.hy) <= 1) {
            h.owner = 'ai'; break;
          }
        }
        if (h.owner === 'ai') break;
      }
    }
  }

  // ═══════════════════════════════════════
  // ERA 5: STELLAR
  // ═══════════════════════════════════════
  if (G.era === 5) {
    var sh = G.ship;
    // Ship movement
    if (K('a') || K('ArrowLeft')) sh.vx -= 0.15;
    if (K('d') || K('ArrowRight')) sh.vx += 0.15;
    if (K('w') || K('ArrowUp')) sh.vy -= 0.15;
    if (K('s') || K('ArrowDown')) sh.vy += 0.15;
    sh.vx *= 0.97; sh.vy *= 0.97;
    sh.x += sh.vx * spd; sh.y += sh.vy * spd;
    sh.x = Math.max(8, Math.min(248, sh.x));
    sh.y = Math.max(8, Math.min(216, sh.y));

    // Orbit planets
    G.planets.forEach(function(p) {
      p.angle += p.speed * spd;
      p.cx = 128 + Math.cos(p.angle) * p.dist;
      p.cy = 112 + Math.sin(p.angle) * p.dist;

      // Colonize nearby planet
      var dx = sh.x - p.cx, dy = sh.y - p.cy;
      var dist = Math.sqrt(dx*dx + dy*dy);
      if (dist < p.size + 6 && !p.colonized) {
        if ((K(' ') || K('Enter')) && G.kcd <= 0) {
          if (p.compatible > 40) {
            p.colonized = true;
            G.colonies.push(p.name);
            G.history.push({ era: 5, time: G.time, event: 'Colonized ' + p.name });
            G.flash = 20; G.flashC = '#8844ff';
            snd.score();
            if (p.hasSignal) {
              G.signalFound = true;
              G.history.push({ era: 5, time: G.time, event: 'SIGNAL DETECTED from distant galaxy!' });
            }
          } else {
            snd.tone(100, 0.08, 0.06);
          }
          G.kcd = 20;
        }
      }
    });

    // VICTORY
    if (G.signalFound && G.colonies.length >= 3) {
      G.won = true;
      G.history.push({ era: 5, time: G.time, event: G.speciesName + ' achieves galactic contact. Victory!' });
      snd.win();
    }
  }

  // Smooth camera
  G.cam.x += (G.cam.tx - G.cam.x) * 0.08;
  G.cam.y += (G.cam.ty - G.cam.y) * 0.08;
  G.cam.zoom += (G.cam.tz - G.cam.zoom) * 0.05;
}
