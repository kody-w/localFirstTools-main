// ============================================================
// CREEP SIEGE: ANCIENT OFFENSIVE - DRAW
// ============================================================

if (mode === 'draw') {
  var sx = G.shake > 0 ? (Math.random()-0.5)*G.shake*2 : 0;
  var sy = G.shake > 0 ? (Math.random()-0.5)*G.shake*2 : 0;
  O.save(); O.translate(sx, sy);

  cls('#0a1a0a');

  // ═══════════════════════════════════════
  // DRAW MAP GRID
  // ═══════════════════════════════════════
  for (var y = 0; y < G.GH; y++) {
    for (var x = 0; x < G.GW; x++) {
      var cell = G.grid[y][x];
      var px = x * G.TS, py = y * G.TS;
      if (cell === 1) {
        // Wall - dark with subtle texture
        O.fillStyle = (x + y) % 2 === 0 ? '#1a2a1a' : '#152515';
        O.fillRect(px, py, G.TS, G.TS);
      } else if (cell === 0) {
        // Path - Dota-style dirt lane
        O.fillStyle = '#2a2215';
        O.fillRect(px, py, G.TS, G.TS);
        O.fillStyle = '#332a1a';
        O.fillRect(px + 1, py + 1, G.TS - 2, G.TS - 2);
        // Lane markings
        if (y === 1 || y === 6 || y === 11) {
          O.fillStyle = 'rgba(255,200,100,0.05)';
          O.fillRect(px, py + G.TS - 1, G.TS, 1);
        }
      } else if (cell === 2) {
        // Spawn point - green glow
        O.fillStyle = '#1a3a1a';
        O.fillRect(px, py, G.TS, G.TS);
        O.fillStyle = 'rgba(68,255,68,' + (0.2 + Math.sin(G.waveTimer * 0.05) * 0.1) + ')';
        O.fillRect(px + 2, py + 2, G.TS - 4, G.TS - 4);
      } else if (cell === 3) {
        // Goal - red ancient
        O.fillStyle = '#2a1a1a';
        O.fillRect(px, py, G.TS, G.TS);
        O.fillStyle = 'rgba(255,68,68,' + (0.3 + Math.sin(G.waveTimer * 0.03) * 0.15) + ')';
        O.fillRect(px + 1, py + 1, G.TS - 2, G.TS - 2);
        txt('⚑', px + G.TS/2, py + G.TS/2, 8, '#ff4444');
      }
    }
  }

  // ─── Lane labels ───
  var laneNames = ['TOP', 'MID', 'BOT'];
  var laneYs = [1, 6, 11];
  for (var i = 0; i < 3; i++) {
    var ly = laneYs[i] * G.TS + G.TS;
    O.fillStyle = 'rgba(255,255,255,0.08)';
    txt(laneNames[i], 3, ly, 5, 'rgba(255,255,255,0.15)', 'left');
  }

  // ═══════════════════════════════════════
  // DRAW TOWERS
  // ═══════════════════════════════════════
  G.towers.forEach(function(t) {
    if (t.hp <= 0) return;
    // Base
    O.fillStyle = '#333';
    O.fillRect(t.x - 5, t.y - 5, 10, 10);
    // Tower body
    O.fillStyle = t.color;
    O.fillRect(t.x - 4, t.y - 6, 8, 8);
    // Turret top
    O.fillStyle = t.color;
    O.fillRect(t.x - 2, t.y - 8, 4, 3);
    // Range indicator (subtle)
    if (G.phase === 'spawn') {
      O.strokeStyle = 'rgba(255,255,255,0.04)';
      O.beginPath(); O.arc(t.x, t.y, t.range, 0, Math.PI*2); O.stroke();
    }
    // HP bar
    if (t.hp < t.maxHp) {
      O.fillStyle = '#333'; O.fillRect(t.x-5, t.y+6, 10, 2);
      O.fillStyle = t.hp/t.maxHp > 0.5 ? '#44ff44' : '#ff4444';
      O.fillRect(t.x-5, t.y+6, Math.floor(10*t.hp/t.maxHp), 2);
    }
  });

  // ═══════════════════════════════════════
  // DRAW PROJECTILES
  // ═══════════════════════════════════════
  G.projectiles.forEach(function(p) {
    O.fillStyle = p.color;
    O.fillRect(p.x - 1.5, p.y - 1.5, 3, 3);
    // Trail
    O.fillStyle = p.color + '44';
    O.fillRect(p.x - p.vx - 1, p.y - p.vy - 1, 2, 2);
  });

  // ═══════════════════════════════════════
  // DRAW CREEPS
  // ═══════════════════════════════════════
  G.creeps.forEach(function(c) {
    if (c.hp <= 0) return;
    // Invis
    if (c.invisTimer > 0) {
      O.globalAlpha = 0.2;
    }
    // Shadow
    O.fillStyle = 'rgba(0,0,0,0.3)';
    O.fillRect(c.x - 3, c.y + 3, 6, 2);
    // Body color by type
    var colors = { melee:'#cc8844', ranged:'#4488cc', siege:'#888888', speed:'#88ff88', mega:'#ff4488', split:'#aa6644' };
    O.fillStyle = colors[c.type] || '#aa8844';
    // Body
    if (c.type === 'mega') {
      O.fillRect(c.x - 5, c.y - 6, 10, 10);
      O.fillStyle = '#ff88aa';
      O.fillRect(c.x - 3, c.y - 8, 6, 3);
    } else if (c.type === 'siege') {
      O.fillRect(c.x - 4, c.y - 4, 8, 8);
      O.fillStyle = '#aaa';
      O.fillRect(c.x - 5, c.y - 2, 10, 4);
    } else {
      O.fillRect(c.x - 3, c.y - 4, 6, 7);
      O.fillStyle = '#ffccaa';
      O.fillRect(c.x - 2, c.y - 6, 4, 3);
    }
    // Slow indicator
    if (c.slowTimer > 0) {
      O.strokeStyle = '#88ffff'; O.lineWidth = 1;
      O.strokeRect(c.x - 4, c.y - 5, 8, 9);
    }
    // DoT indicator
    if (c.dotTimer > 0) {
      O.fillStyle = 'rgba(68,255,68,0.4)';
      O.fillRect(c.x - 1, c.y - 7, 2, 2);
    }
    O.globalAlpha = 1;
    // HP bar
    if (c.hp < c.maxHp) {
      O.fillStyle = '#333'; O.fillRect(c.x - 5, c.y - 9, 10, 2);
      O.fillStyle = c.hp / c.maxHp > 0.5 ? '#44ff44' : (c.hp / c.maxHp > 0.25 ? '#ffaa00' : '#ff4444');
      O.fillRect(c.x - 5, c.y - 9, Math.max(1, Math.floor(10 * c.hp / c.maxHp)), 2);
    }
  });

  // ═══════════════════════════════════════
  // PARTICLES & DMG NUMBERS
  // ═══════════════════════════════════════
  G.particles.forEach(function(p) {
    O.fillStyle = p.c || '#fff';
    O.fillRect(p.x - (p.s||1)/2, p.y - (p.s||1)/2, p.s||1, p.s||1);
  });
  G.dmgNums.forEach(function(d) {
    txt(String(d.v), d.x, d.y, 7, d.c);
  });

  // ═══════════════════════════════════════
  // FLASH OVERLAY
  // ═══════════════════════════════════════
  if (G.flash > 0) {
    O.fillStyle = G.flashC + Math.min(255,Math.floor(G.flash*5)).toString(16).padStart(2,'0');
    O.fillRect(0, 0, RW, RH);
  }

  // ═══════════════════════════════════════
  // HUD: TOP BAR
  // ═══════════════════════════════════════
  rect(0, 0, RW, 12, 'rgba(0,0,0,0.7)');
  txt('Wave ' + G.wave + '/' + G.maxWave, 40, 7, 7, '#ff4444', 'left');
  txt('Gold: ' + G.gold, 110, 7, 7, '#daa520', 'left');
  txt('Score: ' + G.score, 180, 7, 7, '#aaa', 'left');
  // Lives indicator
  for (var i = 0; i < G.lives; i++) {
    txt('⚑', RW - 8 - i * 10, 7, 6, i < G.reached ? '#44ff44' : '#444');
  }

  // ═══════════════════════════════════════
  // SPAWN PHASE UI
  // ═══════════════════════════════════════
  if (G.phase === 'spawn') {
    G.waveTimer += (dt||0.016)*60;

    // Lane selector
    for (var i = 0; i < 3; i++) {
      var ly = G.laneRows[i] * G.TS;
      if (i === G.spawnLane) {
        O.strokeStyle = 'rgba(68,255,68,0.6)';
        O.lineWidth = 2;
        O.strokeRect(0, ly - 1, 16, G.TS * 2 + 2);
        txt('►', 8, ly + G.TS, 10, '#44ff44');
      }
    }

    // Spawn queue count per lane
    var qCounts = [0,0,0];
    G.spawnQueue.forEach(function(sq) { qCounts[sq.lane]++; });
    for (var i = 0; i < 3; i++) {
      if (qCounts[i] > 0) {
        txt('×' + qCounts[i], 22, G.laneRows[i] * G.TS + G.TS, 6, '#44ff44', 'left');
      }
    }

    // Bottom panel: creep selector
    rect(0, RH - 42, RW, 42, 'rgba(0,0,0,0.85)');
    O.strokeStyle = '#444'; O.lineWidth = 1;
    O.strokeRect(0, RH - 42, RW, 1);

    var panelY = RH - 38;
    txt('DEPLOY CREEPS', RW/2, panelY, 7, '#ff4444');
    panelY += 10;

    for (var i = 0; i < G.creepTypes.length; i++) {
      var ct = G.creepTypes[i];
      var bx = 8 + i * 50;
      var sel = i === G.selIdx;
      var afford = G.gold >= ct.cost;

      rect(bx, panelY, 46, 22, sel ? 'rgba(255,68,68,0.2)' : 'rgba(40,40,40,0.5)');
      if (sel) { O.strokeStyle = '#ff4444'; O.strokeRect(bx, panelY, 46, 22); }

      txt(ct.icon, bx + 8, panelY + 8, 8, afford ? '#fff' : '#555');
      txt(ct.name.split(' ')[0], bx + 23, panelY + 7, 5, sel ? '#fff' : '#aaa', 'left');
      txt(ct.cost + 'g', bx + 23, panelY + 15, 5, afford ? '#daa520' : '#664400', 'left');
    }

    // Instructions
    txt('A/D Select · W/S Lane · Space Queue · F Launch', RW/2, RH - 4, 5, '#666');

    // Queue display
    if (G.spawnQueue.length > 0) {
      txt('Queue: ' + G.spawnQueue.length + ' creeps', RW/2, panelY - 5, 6, '#888');
    }
  }

  // ═══════════════════════════════════════
  // EVOLVE PHASE UI
  // ═══════════════════════════════════════
  if (G.phase === 'evolve' && G.evoChoices) {
    O.fillStyle = 'rgba(0,0,0,0.85)';
    O.fillRect(0, 0, RW, RH);

    txt('WAVE ' + G.wave + ' COMPLETE!', RW/2, 25, 12, '#44ff44');
    txt(G.reached + ' creeps breached the ancient', RW/2, 40, 7, '#aaa');
    txt('━━━ EVOLVE ━━━', RW/2, 58, 8, '#ff4444');

    for (var i = 0; i < 3; i++) {
      var evo = G.evoChoices[i];
      var y = 75 + i * 40;
      var sel = i === G.selIdx;

      rect(30, y - 10, 196, 32, sel ? 'rgba(255,68,68,0.2)' : 'rgba(30,30,30,0.8)');
      if (sel) { O.strokeStyle = '#ff4444'; O.lineWidth = 1; O.strokeRect(30, y - 10, 196, 32); }

      txt(evo.icon, 50, y + 2, 10, sel ? '#ff8888' : '#888');
      txt(evo.name, 72, y - 2, 8, sel ? '#fff' : '#aaa', 'left');
      txt(evo.desc, 72, y + 10, 6, sel ? '#ccc' : '#777', 'left');
    }

    txt('W/S + Enter to choose', RW/2, RH - 15, 6, '#666');

    // Show current evolutions
    if (G.evolutions.length > 0) {
      txt('Evolved: ' + G.evolutions.join(', '), RW/2, RH - 6, 5, '#553333');
    }
  }

  // ═══════════════════════════════════════
  // BATTLE PHASE HUD
  // ═══════════════════════════════════════
  if (G.phase === 'battle') {
    G.waveTimer += (dt||0.016)*60;
    // Progress bar: creeps remaining
    var total = G.waveCreepsAlive + G.creeps.length;
    rect(0, RH - 6, RW, 6, 'rgba(0,0,0,0.6)');
    if (total > 0) {
      rect(0, RH - 6, Math.floor(RW * G.creeps.length / Math.max(1, total)), 6, 'rgba(255,68,68,0.4)');
    }
    txt('Alive: ' + G.creeps.length + ' | Breached: ' + G.reached + '/' + G.lives, RW/2, RH - 3, 5, '#aaa');
  }

  // ═══════════════════════════════════════
  // VICTORY / DEFEAT
  // ═══════════════════════════════════════
  if (G.phase === 'victory') {
    O.fillStyle = 'rgba(0,0,0,0.8)';
    O.fillRect(0, 0, RW, RH);
    txt('ANCIENT DESTROYED', RW/2, RH/2 - 30, 14, '#ff4444');
    txt('All 20 waves conquered!', RW/2, RH/2 - 10, 8, '#aaa');
    txt('Final Score: ' + G.score, RW/2, RH/2 + 10, 10, '#daa520');
    txt('Evolutions: ' + G.evolutions.length, RW/2, RH/2 + 28, 7, '#888');
    // List evolutions
    var ey = RH/2 + 42;
    G.evolutions.forEach(function(e, i) {
      if (i > 5) return;
      txt(e, 50 + (i % 6) * 28, ey, 5, '#ff8888');
    });
  }

  if (G.phase === 'defeat') {
    O.fillStyle = 'rgba(0,0,0,0.8)';
    O.fillRect(0, 0, RW, RH);
    txt('CREEPS VANQUISHED', RW/2, RH/2 - 15, 14, '#444');
    txt('Wave ' + G.wave + ' proved too much', RW/2, RH/2 + 5, 8, '#888');
    txt('Score: ' + G.score, RW/2, RH/2 + 25, 10, '#daa520');
  }

  O.restore();

  // Console HUD
  var phaseNames = { spawn:'DEPLOY', battle:'BATTLE', evolve:'EVOLVE', victory:'VICTORY', defeat:'DEFEAT' };
  hud('Wave ' + G.wave + '/' + G.maxWave + ' | ' + phaseNames[G.phase] + ' | Gold:' + G.gold + ' | Score:' + G.score);
  controls(G.phase==='spawn' ? 'A/D Creep · W/S Lane · Space Queue · F Launch' : G.phase==='evolve' ? 'W/S + Enter Choose' : 'Watch the battle!');
}
