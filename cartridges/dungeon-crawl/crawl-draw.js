// ============================================================
// DUNGEON CRAWL: DEPTHS OF RUIN - DRAW
// ============================================================

if (mode === 'draw') {
  var sx = G.shake > 0 ? (Math.random()-0.5) * G.shake * 2 : 0;
  var sy = G.shake > 0 ? (Math.random()-0.5) * G.shake * 2 : 0;
  O.save();
  O.translate(sx, sy);

  cls('#0a0a12');

  // Camera offset to center on player
  var camX = G.p.x * G.TS - RW / 2 + G.TS / 2;
  var camY = G.p.y * G.TS - RH / 2 + G.TS / 2;
  // Clamp camera
  camX = Math.max(0, Math.min(G.MW * G.TS - RW, camX));
  camY = Math.max(0, Math.min(G.MH * G.TS - RH, camY));

  O.save();
  O.translate(-camX, -camY);

  // Tile colors
  var wallC = '#1a1a2e';
  var wallHL = '#222244';
  var floorC = '#2a2a3a';
  var doorC = '#886644';
  var stairC = '#44aaff';
  var chestC = '#ffaa00';
  var trapC = '#663333';

  // ─── DRAW MAP ───
  for (var y = 0; y < G.MH; y++) {
    for (var x = 0; x < G.MW; x++) {
      var px = x * G.TS;
      var py = y * G.TS;
      // Skip if off screen
      if (px + G.TS < camX || px > camX + RW || py + G.TS < camY || py > camY + RH) continue;

      var visible = G.fov[y] && G.fov[y][x];
      var explored = G.seen[y] && G.seen[y][x];

      if (!explored) continue;

      var tile = G.map[y][x];
      var alpha = visible ? 1.0 : 0.35;

      if (tile === G.T_WALL) {
        // Walls with slight variation
        var shade = ((x * 7 + y * 13) % 3 === 0) ? wallHL : wallC;
        O.fillStyle = shade;
        O.globalAlpha = alpha;
        O.fillRect(px, py, G.TS, G.TS);
        // Wall edge highlight
        if (y + 1 < G.MH && G.map[y+1][x] !== G.T_WALL) {
          O.fillStyle = '#333355';
          O.fillRect(px, py + G.TS - 1, G.TS, 1);
        }
      } else if (tile === G.T_FLOOR) {
        O.fillStyle = floorC;
        O.globalAlpha = alpha;
        O.fillRect(px, py, G.TS, G.TS);
        // Floor dots for texture
        if ((x + y) % 5 === 0) {
          O.fillStyle = '#333348';
          O.fillRect(px + 3, py + 3, 1, 1);
        }
      } else if (tile === G.T_DOOR) {
        O.fillStyle = floorC;
        O.globalAlpha = alpha;
        O.fillRect(px, py, G.TS, G.TS);
        O.fillStyle = doorC;
        O.fillRect(px + 1, py + 1, G.TS - 2, G.TS - 2);
        O.fillStyle = '#aa8855';
        O.fillRect(px + 3, py + 3, 2, 2);
      } else if (tile === G.T_STAIR) {
        O.fillStyle = floorC;
        O.globalAlpha = alpha;
        O.fillRect(px, py, G.TS, G.TS);
        // Draw stairs icon
        O.fillStyle = stairC;
        O.fillRect(px + 1, py + 5, 6, 2);
        O.fillRect(px + 2, py + 3, 5, 2);
        O.fillRect(px + 3, py + 1, 4, 2);
      } else if (tile === G.T_CHEST) {
        O.fillStyle = floorC;
        O.globalAlpha = alpha;
        O.fillRect(px, py, G.TS, G.TS);
        if (visible) {
          O.fillStyle = chestC;
          O.fillRect(px + 1, py + 2, 6, 4);
          O.fillStyle = '#cc8800';
          O.fillRect(px + 1, py + 2, 6, 1);
          O.fillStyle = '#ffdd44';
          O.fillRect(px + 3, py + 3, 2, 2);
        }
      } else if (tile === G.T_TRAP) {
        O.fillStyle = floorC;
        O.globalAlpha = alpha;
        O.fillRect(px, py, G.TS, G.TS);
        // Traps barely visible
        if (visible) {
          O.fillStyle = trapC;
          O.fillRect(px + 2, py + 2, 1, 1);
          O.fillRect(px + 5, py + 5, 1, 1);
          O.fillRect(px + 2, py + 5, 1, 1);
          O.fillRect(px + 5, py + 2, 1, 1);
        }
      }
      O.globalAlpha = 1.0;
    }
  }

  // ─── GROUND ITEMS ───
  G.items.forEach(function(gi) {
    if (!G.fov[gi.y] || !G.fov[gi.y][gi.x]) return;
    var px = gi.x * G.TS;
    var py = gi.y * G.TS;
    var ic = gi.item.category === 'weapon' ? '#aaddff' :
             gi.item.category === 'armor' ? '#88aacc' :
             gi.item.category === 'potion' ? '#44ff88' : '#ffcc00';
    O.fillStyle = ic;
    O.fillRect(px + 2, py + 2, 4, 4);
    O.fillStyle = 'rgba(255,255,255,0.3)';
    O.fillRect(px + 3, py + 2, 1, 1);
  });

  // ─── MONSTERS ───
  G.monsters.forEach(function(m) {
    if (!G.fov[m.y] || !G.fov[m.y][m.x]) return;
    var px = m.x * G.TS;
    var py = m.y * G.TS;
    // Body
    O.fillStyle = m.color;
    O.fillRect(px + 1, py + 1, G.TS - 2, G.TS - 2);
    // Icon letter
    O.fillStyle = '#fff';
    O.font = '6px monospace';
    O.textAlign = 'center';
    O.fillText(m.icon, px + G.TS / 2, py + G.TS - 1);
    // HP bar if damaged
    if (m.hp < m.maxHp) {
      var barW = G.TS - 2;
      O.fillStyle = '#333';
      O.fillRect(px + 1, py - 2, barW, 2);
      O.fillStyle = m.hp > m.maxHp * 0.5 ? '#44ff44' : m.hp > m.maxHp * 0.25 ? '#ffaa00' : '#ff4444';
      O.fillRect(px + 1, py - 2, Math.floor(barW * m.hp / m.maxHp), 2);
    }
  });

  // ─── PLAYER ───
  var ppx = G.p.x * G.TS;
  var ppy = G.p.y * G.TS;
  // Glow
  O.fillStyle = 'rgba(255,153,68,0.15)';
  O.beginPath();
  O.arc(ppx + G.TS/2, ppy + G.TS/2, G.TS, 0, Math.PI*2);
  O.fill();
  // Body
  O.fillStyle = '#ff9944';
  O.fillRect(ppx + 1, ppy + 1, G.TS - 2, G.TS - 2);
  // Face
  O.fillStyle = '#fff';
  O.fillRect(ppx + 2, ppy + 2, 1, 1);
  O.fillRect(ppx + 5, ppy + 2, 1, 1);
  // Weapon indicator
  if (G.p.weapon) {
    O.fillStyle = '#aaddff';
    O.fillRect(ppx + G.TS, ppy + 2, 2, 4);
  }
  // Armor indicator
  if (G.p.armor) {
    O.strokeStyle = '#88aacc';
    O.lineWidth = 1;
    O.strokeRect(ppx, ppy, G.TS, G.TS);
  }

  // ─── PARTICLES ───
  G.particles.forEach(function(p) {
    O.fillStyle = p.c || '#fff';
    O.fillRect(p.x - (p.s||1)/2, p.y - (p.s||1)/2, p.s || 1, p.s || 1);
  });

  O.restore(); // camera transform

  // ═══════════════════════════════════════
  // HUD OVERLAY
  // ═══════════════════════════════════════

  // Top bar
  rect(0, 0, RW, 14, 'rgba(0,0,0,0.75)');
  // HP bar
  rect(2, 3, 50, 4, '#331111');
  rect(2, 3, Math.max(0, Math.floor(50 * G.p.hp / G.p.maxHp)), 4, G.p.hp > G.p.maxHp * 0.3 ? '#cc3333' : '#ff2222');
  txt(G.p.hp + '/' + G.p.maxHp, 27, 8, 5, '#ff9999');
  // XP bar
  rect(2, 9, 50, 2, '#111133');
  rect(2, 9, Math.floor(50 * G.p.xp / G.p.xpNext), 2, '#4444cc');
  // Stats
  txt('Lv' + G.p.lvl, 60, 5, 5, '#ffcc44', 'left');
  txt('Atk:' + (G.p.atk + (G.p.weapon ? G.p.weapon.stat : 0)), 85, 5, 5, '#ff8844', 'left');
  txt('Def:' + (G.p.def + (G.p.armor ? G.p.armor.stat : 0)), 120, 5, 5, '#4488ff', 'left');
  txt('$' + G.p.gold, 155, 5, 5, '#ffcc00', 'left');
  txt('F' + G.floor, 180, 5, 5, '#4488ff', 'left');
  txt('T' + G.turn, 200, 5, 5, '#888', 'left');
  // Equipped
  if (G.p.weapon) txt(G.p.weapon.icon, 230, 5, 5, '#aaddff', 'left');
  if (G.p.armor) txt(G.p.armor.icon, 240, 5, 5, '#88aacc', 'left');

  // Message bar
  if (G.msgTimer > 0) {
    var msgAlpha = G.msgTimer > 30 ? 1 : G.msgTimer / 30;
    rect(0, RH - 14, RW, 14, 'rgba(0,0,0,' + (0.7 * msgAlpha) + ')');
    txt(G.msg, RW / 2, RH - 7, 6, 'rgba(200,200,200,' + msgAlpha + ')');
  }

  // ═══════════════════════════════════════
  // FLASH OVERLAY
  // ═══════════════════════════════════════
  if (G.flash > 0) {
    O.fillStyle = G.flashC;
    O.globalAlpha = G.flash / 20;
    O.fillRect(0, 0, RW, RH);
    O.globalAlpha = 1.0;
  }

  // ═══════════════════════════════════════
  // INVENTORY SCREEN
  // ═══════════════════════════════════════
  if (G.phase === 'inventory') {
    O.fillStyle = 'rgba(0,0,0,0.85)';
    O.fillRect(0, 0, RW, RH);
    txt('INVENTORY', RW/2, 16, 10, '#ff9944');

    // Equipped section
    txt('── Equipped ──', RW/2, 32, 6, '#888');
    var wName = G.p.weapon ? G.p.weapon.name + ' (+' + G.p.weapon.stat + ' atk)' : '(none)';
    var aName = G.p.armor ? G.p.armor.name + ' (+' + G.p.armor.stat + ' def)' : '(none)';
    txt('Weapon: ' + wName, RW/2, 42, 6, '#aaddff');
    txt('Armor:  ' + aName, RW/2, 52, 6, '#88aacc');

    // Bag
    txt('── Bag (' + G.p.inv.length + '/8) ──', RW/2, 68, 6, '#888');
    if (G.p.inv.length === 0) {
      txt('Empty', RW/2, 82, 6, '#555');
    } else {
      for (var i = 0; i < G.p.inv.length; i++) {
        var item = G.p.inv[i];
        var y = 80 + i * 14;
        var sel = i === G.selIdx;
        var ic = item.category === 'weapon' ? '#aaddff' :
                 item.category === 'armor' ? '#88aacc' :
                 item.category === 'potion' ? '#44ff88' : '#ffcc00';
        txt((sel ? '> ' : '  ') + item.icon + ' ' + item.name, 80, y, 6, sel ? '#ffcc00' : ic, 'left');
        if (item.category === 'weapon') txt('+' + item.stat + ' atk', 210, y, 5, '#888', 'left');
        else if (item.category === 'armor') txt('+' + item.stat + ' def', 210, y, 5, '#888', 'left');
        else if (item.category === 'potion') txt('+' + item.stat, 210, y, 5, '#888', 'left');
      }
    }
    txt('Enter=Use/Equip  D=Drop  I=Close', RW/2, RH - 10, 5, '#666');
  }

  // ═══════════════════════════════════════
  // DEATH SCREEN
  // ═══════════════════════════════════════
  if (G.phase === 'dead') {
    O.fillStyle = 'rgba(0,0,0,0.8)';
    O.fillRect(0, 0, RW, RH);
    txt('YOU HAVE PERISHED', RW/2, RH/2 - 40, 14, '#cc2222');
    txt(G.msg, RW/2, RH/2 - 15, 7, '#aaa');
    txt('━━━ EPITAPH ━━━', RW/2, RH/2 + 5, 6, '#666');
    txt('Level ' + G.p.lvl + ' Adventurer', RW/2, RH/2 + 18, 7, '#ffcc44');
    txt('Deepest Floor: ' + G.p.maxFloor, RW/2, RH/2 + 30, 6, '#4488ff');
    txt('Monsters Slain: ' + G.p.kills, RW/2, RH/2 + 40, 6, '#cc4444');
    txt('Gold Hoarded: ' + G.p.gold, RW/2, RH/2 + 50, 6, '#ffcc00');
    txt('Turns Survived: ' + G.turn, RW/2, RH/2 + 60, 6, '#888');
    txt('Press Enter to try again', RW/2, RH/2 + 80, 6, '#666');
  }

  // ═══════════════════════════════════════
  // VICTORY SCREEN
  // ═══════════════════════════════════════
  if (G.phase === 'victory') {
    O.fillStyle = 'rgba(0,0,0,0.85)';
    O.fillRect(0, 0, RW, RH);
    txt('DUNGEON CONQUERED', RW/2, 30, 14, '#ffcc00');
    txt('You escaped the Depths of Ruin!', RW/2, 50, 7, '#aaa');
    txt('━━━ LEGEND ━━━', RW/2, 70, 6, '#888');
    txt('Level ' + G.p.lvl + ' Adventurer', RW/2, 86, 8, '#ffcc44');
    txt('All ' + G.p.maxFloor + ' Floors Cleared', RW/2, 100, 6, '#4488ff');
    txt('Monsters Slain: ' + G.p.kills, RW/2, 114, 6, '#cc4444');
    txt('Gold Hoarded: ' + G.p.gold, RW/2, 126, 6, '#ffcc00');
    txt('Turns Taken: ' + G.turn, RW/2, 138, 6, '#888');
    // Equipment summary
    if (G.p.weapon) txt('Weapon: ' + G.p.weapon.name, RW/2, 156, 6, '#aaddff');
    if (G.p.armor) txt('Armor: ' + G.p.armor.name, RW/2, 168, 6, '#88aacc');
    txt('Press Enter to play again', RW/2, 195, 6, '#666');
  }

  O.restore(); // shake transform

  // Bottom bar
  hud('Floor ' + G.floor + ' | Lv' + G.p.lvl + ' | HP:' + G.p.hp + '/' + G.p.maxHp + ' | Kills:' + G.p.kills + ' | $' + G.p.gold);
  controls('WASD Move · I Inventory · . Wait · > Descend');
}
