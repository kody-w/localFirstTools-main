// ============================================================
// CELL TO CIVILIZATION - DRAW
// ============================================================

if (mode === 'draw') {
  // Camera shake offset
  var sx = G.shake > 0 ? (Math.random()-0.5) * G.shake * 2 : 0;
  var sy = G.shake > 0 ? (Math.random()-0.5) * G.shake * 2 : 0;
  O.save();
  O.translate(sx, sy);

  // Era color palettes
  var palettes = {
    1: { bg: '#0a1e2e', bg2: '#0d2a3a', accent: '#3ddc84', dim: '#1a4a5a' },
    2: { bg: '#1a2a0a', bg2: '#2a3a1a', accent: '#8B4513', dim: '#3a4a2a' },
    3: { bg: '#2a1a0a', bg2: '#3a2a1a', accent: '#ff8844', dim: '#4a3a2a' },
    4: { bg: '#1a1a0a', bg2: '#2a2a1a', accent: '#daa520', dim: '#3a3a2a' },
    5: { bg: '#0a0a1e', bg2: '#0d0d2a', accent: '#8844ff', dim: '#1a1a3a' }
  };
  var pal = palettes[G.era];

  // ═══════════════════════════════════════
  // ERA 1: PRIMORDIAL
  // ═══════════════════════════════════════
  if (G.era === 1) {
    cls(pal.bg);
    // Water current effect
    for (var i = 0; i < 15; i++) {
      var wx = (i * 40 + G.time * 8000) % (RW + 60) - 30;
      var wy = 20 + i * 15;
      O.fillStyle = 'rgba(30,80,100,0.15)';
      O.fillRect(wx, wy, 30, 1);
    }

    // Food
    G.food.forEach(function(f) {
      O.fillStyle = '#3ddc84';
      O.beginPath(); O.arc(f.x, f.y, f.size, 0, Math.PI*2); O.fill();
      O.fillStyle = 'rgba(61,220,132,0.2)';
      O.beginPath(); O.arc(f.x, f.y, f.size + 2, 0, Math.PI*2); O.fill();
    });

    // Predators
    G.predators.forEach(function(p) {
      O.fillStyle = '#ff4466';
      O.beginPath(); O.arc(p.x, p.y, p.size, 0, Math.PI*2); O.fill();
      O.fillStyle = 'rgba(255,68,102,0.2)';
      O.beginPath(); O.arc(p.x, p.y, p.size + 3, 0, Math.PI*2); O.fill();
      // Eyes
      O.fillStyle = '#fff';
      O.fillRect(p.x - 2, p.y - 2, 2, 2);
      O.fillRect(p.x + 1, p.y - 2, 2, 2);
    });

    // Player cell
    var c = G.cell;
    // Bioluminescent glow
    O.fillStyle = 'rgba(0,180,255,0.1)';
    O.beginPath(); O.arc(c.x, c.y, c.size + 8, 0, Math.PI*2); O.fill();
    O.fillStyle = 'rgba(0,200,255,0.2)';
    O.beginPath(); O.arc(c.x, c.y, c.size + 4, 0, Math.PI*2); O.fill();
    // Cell body
    O.fillStyle = '#00ccff';
    O.beginPath(); O.arc(c.x, c.y, c.size, 0, Math.PI*2); O.fill();
    // Nucleus
    O.fillStyle = '#0088cc';
    O.beginPath(); O.arc(c.x + 1, c.y, c.size * 0.4, 0, Math.PI*2); O.fill();
    // Flagella visual
    if (c.flagella > 0) {
      O.strokeStyle = '#00aaff';
      O.lineWidth = 1;
      O.beginPath();
      O.moveTo(c.x - c.size, c.y);
      O.quadraticCurveTo(c.x - c.size - 6, c.y + Math.sin(G.time * 5000) * 4, c.x - c.size - 10, c.y);
      O.stroke();
    }
    // Armor visual
    if (c.armor > 0) {
      O.strokeStyle = 'rgba(200,200,255,0.5)';
      O.lineWidth = c.armor;
      O.beginPath(); O.arc(c.x, c.y, c.size + 2, 0, Math.PI*2); O.stroke();
    }

    // Colony dots (show population visually)
    for (var i = 0; i < Math.min(G.pop - 1, 30); i++) {
      var a = (i / 30) * Math.PI * 2 + G.time * 1000;
      var d = 12 + i * 0.5;
      var cx2 = c.x + Math.cos(a) * d;
      var cy2 = c.y + Math.sin(a) * d;
      O.fillStyle = 'rgba(0,200,255,0.3)';
      O.beginPath(); O.arc(cx2, cy2, 1.5, 0, Math.PI*2); O.fill();
    }

    // HUD
    rect(0, 0, RW, 14, 'rgba(0,0,0,0.6)');
    // Energy bar
    rect(4, 3, 60, 6, '#1a3a4a');
    rect(4, 3, Math.floor(60 * c.energy / 100), 6, c.energy > 25 ? '#3ddc84' : '#ff4466');
    txt('E', 2, 7, 6, '#aaa', 'left');
    txt('Pop: ' + G.pop, 80, 7, 6, '#00ccff', 'left');
    txt('Div: ' + G.divCount, 130, 7, 6, '#aaa', 'left');
    // Mutations
    var mutStr = '';
    G.mutations.forEach(function(m) { mutStr += m.charAt(0).toUpperCase(); });
    if (mutStr) txt('M:' + mutStr, RW - 4, 7, 6, '#3ddc84', 'right');
  }

  // ═══════════════════════════════════════
  // ERA 2: ORGANISM
  // ═══════════════════════════════════════
  if (G.era === 2) {
    cls(pal.bg);
    // Ground texture
    for (var i = 0; i < 20; i++) {
      O.fillStyle = 'rgba(60,80,30,0.15)';
      O.fillRect((i * 37 + 5) % RW, (i * 23 + 3) % RH, 3, 2);
    }

    // Organisms
    G.organisms.forEach(function(o) {
      O.fillStyle = o.type === 'prey' ? '#66aa44' : '#cc4444';
      O.beginPath(); O.arc(o.x, o.y, o.size, 0, Math.PI*2); O.fill();
      O.fillStyle = '#fff';
      O.fillRect(o.x - 1, o.y - 1, 2, 1);
      O.fillRect(o.x + 1, o.y - 1, 2, 1);
    });

    // Player creature (blob shaped by mutations)
    var cr = G.creature;
    var blobSize = G.cell.size + 4;
    // Glow
    O.fillStyle = 'rgba(100,200,100,0.15)';
    O.beginPath(); O.arc(cr.x, cr.y, blobSize + 6, 0, Math.PI*2); O.fill();
    // Body segments
    O.fillStyle = '#44aa66';
    O.beginPath(); O.arc(cr.x, cr.y, blobSize, 0, Math.PI*2); O.fill();
    O.fillStyle = '#338855';
    O.beginPath(); O.arc(cr.x - 2, cr.y + 2, blobSize * 0.6, 0, Math.PI*2); O.fill();
    // Eyes
    O.fillStyle = '#fff';
    O.fillRect(cr.x - 3, cr.y - 3, 3, 2);
    O.fillRect(cr.x + 1, cr.y - 3, 3, 2);
    O.fillStyle = '#000';
    O.fillRect(cr.x - 2, cr.y - 3, 1, 1);
    O.fillRect(cr.x + 2, cr.y - 3, 1, 1);

    // HUD
    rect(0, 0, RW, 14, 'rgba(0,0,0,0.6)');
    rect(4, 3, 50, 3, '#1a3a1a');
    rect(4, 3, Math.floor(50 * G.cell.energy / 100), 3, '#3ddc84');
    rect(4, 8, 50, 3, '#1a1a3a');
    rect(4, 8, Math.floor(50 * G.creature.stamina / G.creature.maxSt), 3, '#4488ff');
    txt('Pop: ' + G.pop, 70, 7, 6, '#aaa', 'left');
    txt('F=Sprint', RW - 4, 7, 6, '#888', 'right');
  }

  // ═══════════════════════════════════════
  // ERA 3: TRIBAL
  // ═══════════════════════════════════════
  if (G.era === 3) {
    cls(pal.bg);
    // Ground
    for (var i = 0; i < 30; i++) {
      O.fillStyle = i % 3 === 0 ? 'rgba(80,60,30,0.2)' : 'rgba(50,80,30,0.15)';
      O.fillRect((i * 41 + 7) % RW, (i * 31 + 11) % RH, 4, 3);
    }

    // Buildings
    G.buildings.forEach(function(b) {
      if (b.type === 'Hut') { O.fillStyle = '#8B6914'; rect(b.x-5, b.y-6, 10, 10, '#8B6914'); O.fillStyle='#654'; O.fillRect(b.x-6,b.y-8,12,3); }
      else if (b.type === 'Fire Pit') { O.fillStyle = '#ff6600'; O.fillRect(b.x-2,b.y-2,4,4); O.fillStyle='#ff3300'; O.fillRect(b.x-1,b.y-4,2,3); }
      else if (b.type === 'Totem') { O.fillStyle = '#aaa'; O.fillRect(b.x-1,b.y-8,3,12); O.fillStyle='#daa520'; O.fillRect(b.x-3,b.y-9,7,3); }
      else if (b.type === 'Wall') { O.fillStyle = '#888'; O.fillRect(b.x-6,b.y-1,12,3); }
      txt(b.icon, b.x, b.y - 12, 6, '#ddd');
    });

    // Units
    G.units.forEach(function(u) {
      var rc = u.role === 'gatherer' ? '#44aa44' : u.role === 'hunter' ? '#cc4444' : u.role === 'builder' ? '#aa8844' : '#4488cc';
      O.fillStyle = rc;
      O.fillRect(u.x - 3, u.y - 4, 6, 8);
      O.fillStyle = '#ffccaa';
      O.fillRect(u.x - 2, u.y - 7, 4, 4);
      // HP bar
      if (u.hp < u.maxHp) {
        rect(u.x - 4, u.y - 10, 8, 2, '#333');
        rect(u.x - 4, u.y - 10, Math.floor(8 * u.hp / u.maxHp), 2, '#44ff44');
      }
    });

    // Enemies
    G.enemies.forEach(function(e) {
      O.fillStyle = '#882222';
      O.fillRect(e.x - 3, e.y - 4, 6, 8);
      O.fillStyle = '#cc8888';
      O.fillRect(e.x - 2, e.y - 7, 4, 4);
      rect(e.x - 4, e.y - 10, 8, 2, '#333');
      rect(e.x - 4, e.y - 10, Math.floor(8 * e.hp / e.maxHp), 2, '#ff4444');
    });

    // HUD
    rect(0, 0, RW, 14, 'rgba(0,0,0,0.6)');
    txt('F:' + Math.floor(G.res.food), 8, 7, 6, '#44aa44', 'left');
    txt('W:' + Math.floor(G.res.wood), 55, 7, 6, '#8B6914', 'left');
    txt('S:' + Math.floor(G.res.stone), 100, 7, 6, '#888', 'left');
    txt('Tech:' + G.techs.length + '/5', 145, 7, 6, '#ffaa00', 'left');
    txt('Units:' + G.units.length, 195, 7, 6, '#aaa', 'left');
    txt('B=Build R=Roles', RW / 2, RH - 6, 6, '#888');

    // Build menu overlay
    if (G.buildMenu) {
      rect(60, 40, 136, 100, 'rgba(0,0,0,0.85)');
      O.strokeStyle = '#ff8844'; O.strokeRect(60, 40, 136, 100);
      txt('BUILD', 128, 50, 8, '#ff8844');
      G.buildOpts.forEach(function(opt, i) {
        var y = 66 + i * 18;
        var sel = i === G.selIdx;
        var costStr = '';
        for (var rk in opt.cost) costStr += rk.charAt(0).toUpperCase() + ':' + opt.cost[rk] + ' ';
        txt((sel ? '> ' : '  ') + opt.icon + ' ' + opt.name, 90, y, 7, sel ? '#ffcc00' : '#aaa', 'left');
        txt(costStr, 200, y, 6, '#888', 'right');
      });
    }

    // Tech progress
    if (G.techs.length > 0) {
      rect(0, RH - 14, RW, 14, 'rgba(0,0,0,0.5)');
      txt('Techs: ' + G.techs.join(', '), RW/2, RH - 7, 6, '#ffaa00');
    }
  }

  // ═══════════════════════════════════════
  // ERA 4: CIVILIZATION
  // ═══════════════════════════════════════
  if (G.era === 4) {
    cls(pal.bg);

    // Hex grid
    var ox = G.cam.x - 128, oy = G.cam.y - 112;
    G.hexes.forEach(function(h) {
      var px = h.hx * G.hexW - ox;
      var py = h.hy * G.hexH + (h.hx % 2 ? G.hexH/2 : 0) - oy;
      if (px < -20 || px > RW + 20 || py < -20 || py > RH + 20) return;

      var tc = { water: '#1a3a5a', forest: '#1a4a1a', mountain: '#4a4a4a', desert: '#5a4a2a', plains: '#3a4a2a' };
      O.fillStyle = tc[h.terrain] || '#2a2a2a';
      O.fillRect(px, py, G.hexW - 1, G.hexH - 1);

      if (h.owner === 'player') { O.fillStyle = 'rgba(218,165,32,0.25)'; O.fillRect(px, py, G.hexW-1, G.hexH-1); }
      if (h.owner === 'ai') { O.fillStyle = 'rgba(255,68,68,0.2)'; O.fillRect(px, py, G.hexW-1, G.hexH-1); }
      if (h.building === 'city') { txt('⌂', px + G.hexW/2, py + G.hexH/2, 8, h.owner === 'player' ? '#daa520' : '#ff4466'); }
      if (h.resource) { txt(h.resource === 'iron' ? '⛏' : '◆', px + G.hexW/2, py + G.hexH/2 + 4, 5, '#aaa'); }
    });

    // HUD
    rect(0, 0, RW, 20, 'rgba(0,0,0,0.7)');
    txt('F:' + Math.floor(G.civRes.food), 10, 7, 6, '#44aa44', 'left');
    txt('P:' + Math.floor(G.civRes.prod), 50, 7, 6, '#aa8844', 'left');
    txt('G:' + Math.floor(G.civRes.gold), 90, 7, 6, '#daa520', 'left');
    txt('S:' + Math.floor(G.civRes.science), 130, 7, 6, '#4488ff', 'left');

    if (G.civResearching) {
      txt('Researching: ' + G.civResearching, RW/2, 15, 6, '#daa520');
      rect(170, 2, 50, 4, '#333');
      rect(170, 2, Math.floor(50 * G.civResProgress), 4, '#daa520');
    } else {
      txt('B=Research', RW - 4, 7, 6, '#888', 'right');
    }

    txt('E=Expand(10g) WASD=Scroll', RW/2, RH - 6, 6, '#888');

    // Research menu
    if (G.buildMenu && !G.civResearching) {
      var avail = G.allCivTechs.filter(function(t) { return G.civTechs.indexOf(t) === -1; });
      rect(50, 30, 156, 20 + avail.length * 16, 'rgba(0,0,0,0.9)');
      O.strokeStyle = '#daa520'; O.strokeRect(50, 30, 156, 20 + avail.length * 16);
      txt('RESEARCH', 128, 40, 8, '#daa520');
      avail.forEach(function(t, i) {
        var y = 56 + i * 16;
        var sel = i === G.selIdx;
        var done = G.civTechs.indexOf(t) >= 0;
        txt((sel ? '> ' : '  ') + t, 75, y, 7, sel ? '#ffcc00' : done ? '#666' : '#aaa', 'left');
      });
    }

    // Researched techs
    if (G.civTechs.length > 0) {
      rect(0, RH - 14, RW, 14, 'rgba(0,0,0,0.5)');
      txt(G.civTechs.join(' → '), RW/2, RH - 7, 6, '#daa520');
    }
  }

  // ═══════════════════════════════════════
  // ERA 5: STELLAR
  // ═══════════════════════════════════════
  if (G.era === 5) {
    cls(pal.bg);

    // Stars
    G.stars.forEach(function(s) {
      O.fillStyle = 'rgba(255,255,255,' + (s.b * 0.6) + ')';
      O.fillRect(s.x, s.y, s.b > 0.7 ? 2 : 1, s.b > 0.7 ? 2 : 1);
    });

    // Sun
    O.fillStyle = '#ffcc00';
    O.beginPath(); O.arc(128, 112, 8, 0, Math.PI*2); O.fill();
    O.fillStyle = 'rgba(255,200,0,0.15)';
    O.beginPath(); O.arc(128, 112, 14, 0, Math.PI*2); O.fill();

    // Orbits and planets
    G.planets.forEach(function(p) {
      // Orbit line
      O.strokeStyle = 'rgba(255,255,255,0.05)';
      O.beginPath(); O.arc(128, 112, p.dist, 0, Math.PI*2); O.stroke();

      var px = p.cx || 128, py = p.cy || 112;
      var tc = { rocky: '#aa8866', gas: '#cc8844', ice: '#88ccff', volcanic: '#ff6644', ocean: '#4488cc' };
      O.fillStyle = tc[p.type] || '#aaa';
      O.beginPath(); O.arc(px, py, p.size, 0, Math.PI*2); O.fill();
      if (p.colonized) {
        O.strokeStyle = '#3ddc84'; O.lineWidth = 1;
        O.beginPath(); O.arc(px, py, p.size + 3, 0, Math.PI*2); O.stroke();
        txt('✓', px, py - p.size - 4, 5, '#3ddc84');
      }
      if (p.hasSignal && !G.signalFound) {
        O.strokeStyle = 'rgba(136,68,255,' + (0.3 + Math.sin(G.time * 10000) * 0.3) + ')';
        O.lineWidth = 1;
        O.beginPath(); O.arc(px, py, p.size + 6 + Math.sin(G.time * 5000) * 3, 0, Math.PI*2); O.stroke();
      }
      // Label on hover proximity
      var dx = G.ship.x - px, dy = G.ship.y - py;
      if (Math.sqrt(dx*dx+dy*dy) < p.size + 20) {
        txt(p.name, px, py + p.size + 8, 5, '#ccc');
        txt(p.type + ' ' + p.compatible + '%', px, py + p.size + 15, 5, p.compatible > 60 ? '#3ddc84' : p.compatible > 40 ? '#ffaa00' : '#ff4466');
      }
    });

    // Ship
    var sh = G.ship;
    O.fillStyle = '#aaddff';
    O.beginPath();
    O.moveTo(sh.x, sh.y - 5);
    O.lineTo(sh.x - 4, sh.y + 4);
    O.lineTo(sh.x + 4, sh.y + 4);
    O.fill();
    // Engine glow
    O.fillStyle = 'rgba(100,200,255,0.3)';
    O.beginPath(); O.arc(sh.x, sh.y + 5, 3, 0, Math.PI*2); O.fill();

    // HUD
    rect(0, 0, RW, 14, 'rgba(0,0,0,0.6)');
    txt('Colonies: ' + G.colonies.length + '/' + G.planets.length, 10, 7, 6, '#8844ff', 'left');
    if (G.signalFound) txt('SIGNAL FOUND!', RW/2, 7, 7, '#ff44ff');
    txt('Space=Colonize', RW - 4, 7, 6, '#888', 'right');
  }

  // ═══════════════════════════════════════
  // PARTICLES (all eras)
  // ═══════════════════════════════════════
  G.particles.forEach(function(p) {
    O.fillStyle = p.c || '#fff';
    O.fillRect(p.x - (p.s||1)/2, p.y - (p.s||1)/2, p.s || 1, p.s || 1);
  });

  // ═══════════════════════════════════════
  // FLASH OVERLAY
  // ═══════════════════════════════════════
  if (G.flash > 0) {
    O.fillStyle = G.flashC + Math.floor(G.flash * 4).toString(16).padStart(2,'0');
    O.fillRect(0, 0, RW, RH);
  }

  // ═══════════════════════════════════════
  // ERA TRANSITION OVERLAY
  // ═══════════════════════════════════════
  if (G.transition > 0) {
    var alpha = Math.min(1, G.transition / 30);
    O.fillStyle = 'rgba(0,0,0,' + (alpha * 0.85) + ')';
    O.fillRect(0, 0, RW, RH);
    var tAlpha = G.transition > 60 ? (90 - G.transition) / 30 : G.transition > 30 ? 1 : G.transition / 30;
    txt(G.transMsg, RW/2, RH/2 - 10, 14, 'rgba(255,255,255,' + tAlpha + ')');
    var eraYear = G.time * 4; // billions of years
    txt(eraYear.toFixed(1) + ' billion years', RW/2, RH/2 + 10, 8, 'rgba(200,200,200,' + tAlpha * 0.7 + ')');
  }

  // ═══════════════════════════════════════
  // MUTATION CHOICE POPUP
  // ═══════════════════════════════════════
  if (G.mutChoice) {
    O.fillStyle = 'rgba(0,0,0,0.8)';
    O.fillRect(0, 0, RW, RH);
    txt('MUTATION', RW/2, 50, 12, '#3ddc84');
    txt('Choose an adaptation:', RW/2, 65, 7, '#aaa');
    for (var i = 0; i < 2; i++) {
      var m = G.mutChoice[i];
      var y = 90 + i * 40;
      var sel = i === G.selIdx;
      rect(50, y - 12, 156, 30, sel ? 'rgba(61,220,132,0.2)' : 'rgba(50,50,80,0.5)');
      if (sel) { O.strokeStyle = '#3ddc84'; O.strokeRect(50, y - 12, 156, 30); }
      txt(m.icon + ' ' + m.name, 90, y - 2, 9, sel ? '#3ddc84' : '#aaa', 'left');
      txt(m.desc, 90, y + 10, 6, '#888', 'left');
    }
    txt('W/S + Enter', RW/2, 175, 6, '#666');
  }

  // ═══════════════════════════════════════
  // TIMELINE BAR (top)
  // ═══════════════════════════════════════
  if (!G.mutChoice && G.transition <= 0) {
    rect(0, RH - 3, RW, 3, '#111');
    var progress = Math.min(1, G.era / 5);
    var barC = pal.accent;
    rect(0, RH - 3, Math.floor(RW * progress), 3, barC);
    // Era markers
    for (var e = 1; e <= 5; e++) {
      var ex = Math.floor((e / 5) * RW);
      O.fillStyle = G.era >= e ? barC : '#333';
      O.fillRect(ex - 1, RH - 4, 2, 5);
    }
  }

  // ═══════════════════════════════════════
  // STATS PANEL
  // ═══════════════════════════════════════
  if (G.showStats) {
    rect(20, 20, 216, 150, 'rgba(0,0,0,0.9)');
    O.strokeStyle = pal.accent; O.strokeRect(20, 20, 216, 150);
    txt(G.speciesName, 128, 32, 10, pal.accent);
    txt('Era ' + G.era + ' | Pop: ' + G.pop, 128, 46, 7, '#aaa');
    txt('Time: ' + (G.time * 4).toFixed(2) + ' Byr', 128, 58, 7, '#888');
    txt('Mutations: ' + G.mutations.join(', '), 128, 70, 6, '#3ddc84');
    txt('Speed: ' + G.speed + 'x', 128, 82, 7, '#888');
    // History (last 6 events)
    var startY = 96;
    var recent = G.history.slice(-6);
    recent.forEach(function(h, i) {
      txt(h.event, 128, startY + i * 10, 5, '#777');
    });
    txt('Tab=Close | 1-4=Speed', 128, 164, 6, '#555');
  }

  // ═══════════════════════════════════════
  // GAME OVER / VICTORY
  // ═══════════════════════════════════════
  if (G.over) {
    O.fillStyle = 'rgba(0,0,0,0.7)';
    O.fillRect(0, 0, RW, RH);
    txt('EXTINCTION', RW/2, RH/2 - 15, 16, '#ff4466');
    txt(G.speciesName + ' perished', RW/2, RH/2 + 5, 8, '#aaa');
    txt('Era ' + G.era + ' | ' + (G.time * 4).toFixed(1) + ' Byr', RW/2, RH/2 + 20, 7, '#888');
  }

  if (G.won) {
    O.fillStyle = 'rgba(0,0,0,0.75)';
    O.fillRect(0, 0, RW, RH);
    txt('GALACTIC CONTACT', RW/2, 30, 14, '#8844ff');
    txt(G.speciesName + ' has reached the stars', RW/2, 48, 7, '#ccc');
    txt('━━━ EVOLUTIONARY TIMELINE ━━━', RW/2, 65, 6, '#888');
    var hy = 78;
    G.history.forEach(function(h, i) {
      if (i > 12) return; // fit on screen
      txt('Era ' + h.era + ': ' + h.event, RW/2, hy + i * 10, 5, '#aaa');
    });
    if (G.history.length > 13) txt('... and ' + (G.history.length - 13) + ' more events', RW/2, hy + 130, 5, '#666');
    txt('Mutations: ' + G.mutations.join(' → '), RW/2, RH - 20, 6, '#3ddc84');
  }

  O.restore();

  // Bottom bar
  var eraNames = { 1: 'Primordial', 2: 'Organism', 3: 'Tribal', 4: 'Civilization', 5: 'Stellar' };
  hud(G.speciesName + ' | Era ' + G.era + ': ' + eraNames[G.era] + ' | ' + (G.time * 4).toFixed(1) + ' Byr | Pop: ' + G.pop + ' | ' + G.speed + 'x');
  controls('WASD Move · Tab Stats · 1-4 Speed · B Build · Space/Enter Action');
}
