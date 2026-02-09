// ============================================================
// DUNGEON CRAWL: DEPTHS OF RUIN - UPDATE
// Turn-based movement, combat, item pickup, stairs
// ============================================================

if (mode === 'update') {
  G.kcd = Math.max(0, G.kcd - 1);
  G.shake = Math.max(0, G.shake - 0.5);
  G.flash = Math.max(0, G.flash - 1);
  G.msgTimer = Math.max(0, G.msgTimer - 1);

  // Particles
  G.particles = G.particles.filter(function(p) {
    p.x += p.vx; p.y += p.vy; p.life--;
    return p.life > 0;
  });

  // ═══════════════════════════════════════
  // DEAD
  // ═══════════════════════════════════════
  if (G.phase === 'dead') {
    if ((K(' ') || K('Enter')) && G.kcd <= 0) {
      // Restart
      G.floor = 1; G.turn = 0;
      G.p.hp = 30; G.p.maxHp = 30; G.p.atk = 5; G.p.def = 1;
      G.p.xp = 0; G.p.lvl = 1; G.p.xpNext = 12;
      G.p.gold = 0; G.p.inv = []; G.p.weapon = null; G.p.armor = null;
      G.p.kills = 0; G.p.maxFloor = 1;
      G.phase = 'play';
      G.genFloor(1);
      G.calcFOV();
      G.msg = 'You descend once more...';
      G.msgTimer = 120;
      G.kcd = 15;
    }
    return;
  }

  // ═══════════════════════════════════════
  // VICTORY
  // ═══════════════════════════════════════
  if (G.phase === 'victory') {
    if ((K(' ') || K('Enter')) && G.kcd <= 0) {
      G.floor = 1; G.turn = 0;
      G.p.hp = 30; G.p.maxHp = 30; G.p.atk = 5; G.p.def = 1;
      G.p.xp = 0; G.p.lvl = 1; G.p.xpNext = 12;
      G.p.gold = 0; G.p.inv = []; G.p.weapon = null; G.p.armor = null;
      G.p.kills = 0; G.p.maxFloor = 1;
      G.phase = 'play';
      G.genFloor(1);
      G.calcFOV();
      G.msg = 'A new adventure begins...';
      G.msgTimer = 120;
      G.kcd = 15;
    }
    return;
  }

  // ═══════════════════════════════════════
  // INVENTORY
  // ═══════════════════════════════════════
  if (G.phase === 'inventory') {
    if ((K('i') || K('Escape')) && G.kcd <= 0) {
      G.phase = 'play'; G.kcd = 12; return;
    }
    if (G.p.inv.length === 0) return;

    if ((K('w') || K('ArrowUp')) && G.kcd <= 0) {
      G.selIdx = (G.selIdx + G.p.inv.length - 1) % G.p.inv.length; G.kcd = 8; snd.beep();
    }
    if ((K('s') || K('ArrowDown')) && G.kcd <= 0) {
      G.selIdx = (G.selIdx + 1) % G.p.inv.length; G.kcd = 8; snd.beep();
    }
    if ((K(' ') || K('Enter')) && G.kcd <= 0) {
      var item = G.p.inv[G.selIdx];
      if (item.category === 'potion') {
        if (item.type === 'heal') {
          G.p.hp = Math.min(G.p.maxHp, G.p.hp + item.stat);
          G.msg = 'Healed ' + item.stat + ' HP';
        } else if (item.type === 'buff_atk') {
          G.p.atk += item.stat;
          G.msg = 'Attack +' + item.stat + '!';
        } else if (item.type === 'buff_def') {
          G.p.def += item.stat;
          G.msg = 'Defense +' + item.stat + '!';
        }
        G.p.inv.splice(G.selIdx, 1);
        G.flash = 8; G.flashC = '#44ff88';
        snd.pickup();
      } else if (item.category === 'weapon') {
        if (G.p.weapon) G.p.inv.push(G.p.weapon);
        G.p.weapon = item;
        G.p.inv.splice(G.selIdx, 1);
        G.msg = 'Equipped ' + item.name;
        snd.score();
      } else if (item.category === 'armor') {
        if (G.p.armor) G.p.inv.push(G.p.armor);
        G.p.armor = item;
        G.p.inv.splice(G.selIdx, 1);
        G.msg = 'Equipped ' + item.name;
        snd.score();
      }
      G.msgTimer = 90;
      if (G.selIdx >= G.p.inv.length) G.selIdx = Math.max(0, G.p.inv.length - 1);
      G.kcd = 12;
    }
    // Drop item
    if (K('d') && G.kcd <= 0 && G.p.inv.length > 0) {
      var dropped = G.p.inv.splice(G.selIdx, 1)[0];
      G.items.push({ x: G.p.x, y: G.p.y, item: dropped });
      G.msg = 'Dropped ' + dropped.name;
      G.msgTimer = 60;
      if (G.selIdx >= G.p.inv.length) G.selIdx = Math.max(0, G.p.inv.length - 1);
      G.kcd = 12;
      snd.beep();
    }
    return;
  }

  // ═══════════════════════════════════════
  // PLAY — Turn-based movement
  // ═══════════════════════════════════════
  if (G.phase !== 'play') return;

  // Open inventory
  if (K('i') && G.kcd <= 0) {
    G.phase = 'inventory'; G.selIdx = 0; G.kcd = 12; snd.beep(); return;
  }

  // Wait in place (skip turn)
  var moved = false;
  var dx = 0, dy = 0;

  if ((K('w') || K('ArrowUp')) && G.kcd <= 0) { dy = -1; moved = true; }
  if ((K('s') || K('ArrowDown')) && G.kcd <= 0) { dy = 1; moved = true; }
  if ((K('a') || K('ArrowLeft')) && G.kcd <= 0) { dx = -1; moved = true; }
  if ((K('d') || K('ArrowRight')) && G.kcd <= 0) { dx = 1; moved = true; }
  if (K('.') && G.kcd <= 0) { moved = true; } // wait

  if (!moved) return;
  G.kcd = 8;

  var nx = G.p.x + dx;
  var ny = G.p.y + dy;

  // Bounds check
  if (nx < 0 || nx >= G.MW || ny < 0 || ny >= G.MH) return;

  // Wall collision
  if (G.map[ny][nx] === G.T_WALL) return;

  // ─── COMBAT: check for monster at target ───
  var target = null;
  for (var i = 0; i < G.monsters.length; i++) {
    if (G.monsters[i].x === nx && G.monsters[i].y === ny) { target = G.monsters[i]; break; }
  }

  if (target) {
    // Player attacks
    var pAtk = G.p.atk + (G.p.weapon ? G.p.weapon.stat : 0);
    var dmg = Math.max(1, pAtk - target.def + Math.floor(Math.random() * 3) - 1);
    target.hp -= dmg;
    G.msg = 'Hit ' + target.name + ' for ' + dmg + ' dmg';
    G.msgTimer = 60;
    snd.hit();
    G.shake = 3;
    // Blood particles
    for (var i = 0; i < 6; i++)
      G.particles.push({ x: nx * G.TS + G.TS/2, y: ny * G.TS + G.TS/2, vx: (Math.random()-0.5)*3, vy: (Math.random()-0.5)*3, life: 15, c: '#cc2222', s: 2 });

    if (target.hp <= 0) {
      // Kill
      G.p.xp += target.xp;
      G.p.gold += target.gold;
      G.p.kills++;
      G.msg = target.name + ' slain! +' + target.xp + 'xp +' + target.gold + 'g';
      G.msgTimer = 90;
      snd.explode();
      // Death burst
      for (var i = 0; i < 12; i++)
        G.particles.push({ x: nx * G.TS + G.TS/2, y: ny * G.TS + G.TS/2, vx: (Math.random()-0.5)*5, vy: (Math.random()-0.5)*5, life: 20, c: target.color, s: 2 });
      // Remove monster
      G.monsters = G.monsters.filter(function(m) { return m !== target; });
      // Drop loot chance
      if (Math.random() < 0.25) {
        var loot = G.genLoot(G.floor);
        G.items.push({ x: nx, y: ny, item: loot });
      }
      // Level up check
      if (G.p.xp >= G.p.xpNext) G.levelUp();
    }
  } else {
    // Move player
    G.p.x = nx;
    G.p.y = ny;

    // ─── TILE INTERACTIONS ───
    var tile = G.map[ny][nx];

    // Stairs
    if (tile === G.T_STAIR) {
      if (K(' ') || K('Enter')) {
        // Actually handled separately — just show prompt
      }
      G.msg = 'Stairs down. Press > to descend';
      G.msgTimer = 60;
    }

    // Chest
    if (tile === G.T_CHEST) {
      G.map[ny][nx] = G.T_FLOOR;
      var loot = G.genLoot(G.floor);
      if (loot.category === 'gold') {
        G.p.gold += loot.stat;
        G.msg = 'Found ' + loot.name + '!';
      } else {
        G.p.inv.push(loot);
        G.msg = 'Found ' + loot.name + '!';
      }
      G.msgTimer = 90;
      G.flash = 8; G.flashC = '#ffcc00';
      snd.score();
      for (var i = 0; i < 8; i++)
        G.particles.push({ x: nx * G.TS + G.TS/2, y: ny * G.TS + G.TS/2, vx: (Math.random()-0.5)*3, vy: (Math.random()-0.5)*3, life: 18, c: '#ffcc00', s: 2 });
    }

    // Trap
    if (tile === G.T_TRAP) {
      G.map[ny][nx] = G.T_FLOOR; // disarm after trigger
      var trapDmg = 3 + Math.floor(G.floor * 1.5);
      var defReduce = (G.p.armor ? G.p.armor.stat : 0);
      trapDmg = Math.max(1, trapDmg - Math.floor(defReduce / 2));
      G.p.hp -= trapDmg;
      G.msg = 'Trap! Took ' + trapDmg + ' damage!';
      G.msgTimer = 90;
      G.shake = 6; G.flash = 10; G.flashC = '#ff4444';
      snd.tone(200, 0.08, 0.06, 'sawtooth');
    }

    // Pick up ground items
    for (var i = G.items.length - 1; i >= 0; i--) {
      var gi = G.items[i];
      if (gi.x === nx && gi.y === ny) {
        if (gi.item.category === 'gold') {
          G.p.gold += gi.item.stat;
          G.msg = 'Picked up ' + gi.item.name;
        } else if (G.p.inv.length < 8) {
          G.p.inv.push(gi.item);
          G.msg = 'Picked up ' + gi.item.name;
        } else {
          G.msg = 'Inventory full!';
          G.msgTimer = 60;
          continue; // don't remove
        }
        G.items.splice(i, 1);
        G.msgTimer = 60;
        snd.pickup();
      }
    }
  }

  // ─── DESCEND STAIRS ───
  if (K('>') || K('.')) {
    if (G.map[G.p.y][G.p.x] === G.T_STAIR) {
      G.floor++;
      if (G.floor > G.p.maxFloor) G.p.maxFloor = G.floor;
      if (G.floor > 12) {
        // Victory!
        G.phase = 'victory';
        G.msg = 'You escaped the dungeon!';
        snd.win();
        G.kcd = 30;
        return;
      }
      G.genFloor(G.floor);
      G.calcFOV();
      G.msg = 'Descended to floor ' + G.floor;
      G.msgTimer = 90;
      G.flash = 12; G.flashC = '#4488ff';
      snd.tone(300, 0.06, 0.04);
      G.kcd = 15;
      return;
    }
  }

  G.turn++;

  // ═══════════════════════════════════════
  // MONSTER TURNS
  // ═══════════════════════════════════════
  G.calcFOV();

  for (var i = 0; i < G.monsters.length; i++) {
    var m = G.monsters[i];

    // Wake up if in FOV
    if (G.fov[m.y] && G.fov[m.y][m.x]) {
      m.awake = true;
      m.lastSawX = G.p.x;
      m.lastSawY = G.p.y;
    }

    if (!m.awake) continue;

    // Simple pathfinding toward player (or last known position)
    var goalX = G.fov[m.y] && G.fov[m.y][m.x] ? G.p.x : m.lastSawX;
    var goalY = G.fov[m.y] && G.fov[m.y][m.x] ? G.p.y : m.lastSawY;

    if (goalX < 0) continue;

    var mdx = 0, mdy = 0;
    var ddx = goalX - m.x;
    var ddy = goalY - m.y;

    // Move toward goal (prefer larger axis)
    if (Math.abs(ddx) >= Math.abs(ddy)) {
      mdx = ddx > 0 ? 1 : (ddx < 0 ? -1 : 0);
    } else {
      mdy = ddy > 0 ? 1 : (ddy < 0 ? -1 : 0);
    }

    var mnx = m.x + mdx;
    var mny = m.y + mdy;

    // Adjacent to player? Attack!
    if (mnx === G.p.x && mny === G.p.y) {
      var mDmg = Math.max(1, m.atk - G.p.def - (G.p.armor ? G.p.armor.stat : 0) + Math.floor(Math.random() * 2));
      G.p.hp -= mDmg;
      G.msg = m.name + ' hits you for ' + mDmg + '!';
      G.msgTimer = 60;
      G.shake = 4;
      snd.tone(150, 0.06, 0.05, 'sawtooth');
      for (var j = 0; j < 4; j++)
        G.particles.push({ x: G.p.x * G.TS + G.TS/2, y: G.p.y * G.TS + G.TS/2, vx: (Math.random()-0.5)*3, vy: (Math.random()-0.5)*3, life: 12, c: '#ff4444', s: 2 });

      if (G.p.hp <= 0) {
        G.phase = 'dead';
        G.msg = 'Slain by ' + m.name + ' on floor ' + G.floor;
        G.msgTimer = 9999;
        snd.die();
        G.kcd = 30;
        return;
      }
      continue;
    }

    // Check if move target is valid
    if (mnx >= 0 && mnx < G.MW && mny >= 0 && mny < G.MH &&
        G.map[mny][mnx] !== G.T_WALL) {
      // Don't stack on other monsters
      var blocked = false;
      for (var j = 0; j < G.monsters.length; j++) {
        if (j !== i && G.monsters[j].x === mnx && G.monsters[j].y === mny) { blocked = true; break; }
      }
      if (!blocked) {
        m.x = mnx;
        m.y = mny;
      }
    }

    // If reached last known pos and can't see player, go idle
    if (m.x === m.lastSawX && m.y === m.lastSawY && !(G.fov[m.y] && G.fov[m.y][m.x])) {
      m.awake = false;
      m.lastSawX = -1; m.lastSawY = -1;
    }
  }
}
