// hud.js
// In-game HUD overlay: health bars, abilities, combo counter, floating text, death/victory screens

const HUD = {
  displayHP: 100,
  displayMaxHP: 100,
  displayMP: 50,
  displayMaxMP: 50,
  displayST: 80,
  displayMaxST: 80,
  displayXP: 0,
  displayMaxXP: 100,
  hpFlashTime: 0,
  comboScale: 1.0,
  lastCombo: 0,

  init() {
    this.displayHP = G.player.hp;
    this.displayMaxHP = G.player.maxHP;
    this.displayMP = G.player.mana;
    this.displayMaxMP = G.player.maxMana;
    this.displayST = G.player.stamina;
    this.displayMaxST = G.player.maxStamina;
    this.displayXP = G.player.xp;
    this.displayMaxXP = G.player.nextLevelXP;
    this.hpFlashTime = 0;
    this.comboScale = 1.0;
    this.lastCombo = 0;
  },

  update(dt) {
    // Smooth bar interpolation
    const lerpSpeed = 5;
    this.displayHP = Util.lerp(this.displayHP, G.player.hp, dt * lerpSpeed);
    this.displayMaxHP = Util.lerp(this.displayMaxHP, G.player.maxHP, dt * lerpSpeed);
    this.displayMP = Util.lerp(this.displayMP, G.player.mana, dt * lerpSpeed);
    this.displayMaxMP = Util.lerp(this.displayMaxMP, G.player.maxMana, dt * lerpSpeed);
    this.displayST = Util.lerp(this.displayST, G.player.stamina, dt * lerpSpeed);
    this.displayMaxST = Util.lerp(this.displayMaxST, G.player.maxStamina, dt * lerpSpeed);

    const xpProgress = Progression.getXPProgress();
    this.displayXP = Util.lerp(this.displayXP, xpProgress.current, dt * lerpSpeed);
    this.displayMaxXP = Util.lerp(this.displayMaxXP, xpProgress.needed, dt * lerpSpeed);

    // HP flash when low
    if (G.player.hp / G.player.maxHP < 0.25) {
      this.hpFlashTime += dt;
    } else {
      this.hpFlashTime = 0;
    }

    // Update floating text
    for (let i = G.floatingTexts.length - 1; i >= 0; i--) {
      const ft = G.floatingTexts[i];
      ft.life -= dt;
      ft.y -= 50 * dt;
      if (ft.life <= 0) {
        G.floatingTexts.splice(i, 1);
      }
    }

    // Combo scale animation
    if (G.combo > this.lastCombo) {
      this.comboScale = 1.5;
    }
    this.lastCombo = G.combo;
    this.comboScale = Util.lerp(this.comboScale, 1.0, dt * 5);
  },

  render(ctx) {
    const w = G.canvas.width;
    const h = G.canvas.height;

    // Top-left: Player bars
    this.renderPlayerBars(ctx, 10, 10);

    // Top-right: Floor & info
    this.renderFloorInfo(ctx, w - 10, 10);

    // Top-center: Boss HP bar
    if (G.bossActive) {
      this.renderBossBar(ctx, w / 2, 10);
    }

    // Bottom-left: Ability hotbar
    this.renderAbilityHotbar(ctx, 10, h - 70);

    // Center-right: Combo counter
    if (G.combo > 0 && G.comboTimer > 0) {
      this.renderCombo(ctx, w - 120, h / 2);
    }

    // Floating text
    this.renderFloatingText(ctx);
  },

  renderPlayerBars(ctx, x, y) {
    const barWidth = 200;
    const barHeight = 16;
    const spacing = 4;

    // HP bar
    const hpPct = this.displayHP / this.displayMaxHP;
    const flashAlpha = this.hpFlashTime > 0 ? Math.abs(Math.sin(this.hpFlashTime * 8)) * 0.5 + 0.5 : 1.0;

    ctx.fillStyle = 'rgba(40, 40, 40, 0.8)';
    ctx.fillRect(x, y, barWidth, barHeight);

    const hpGrad = ctx.createLinearGradient(x, y, x + barWidth * hpPct, y);
    hpGrad.addColorStop(0, `rgba(200, 50, 50, ${flashAlpha})`);
    hpGrad.addColorStop(1, `rgba(120, 20, 20, ${flashAlpha})`);
    ctx.fillStyle = hpGrad;
    ctx.fillRect(x, y, barWidth * hpPct, barHeight);

    ctx.strokeStyle = '#666666';
    ctx.lineWidth = 1;
    ctx.strokeRect(x, y, barWidth, barHeight);

    ctx.font = 'bold 11px sans-serif';
    ctx.fillStyle = '#ffffff';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(
      `HP: ${Math.ceil(this.displayHP)}/${Math.ceil(this.displayMaxHP)}`,
      x + barWidth / 2,
      y + barHeight / 2
    );

    // Mana bar
    const mpPct = this.displayMP / this.displayMaxMP;
    y += barHeight + spacing;

    ctx.fillStyle = 'rgba(40, 40, 40, 0.8)';
    ctx.fillRect(x, y, barWidth, barHeight);

    const mpGrad = ctx.createLinearGradient(x, y, x + barWidth * mpPct, y);
    mpGrad.addColorStop(0, '#5588ff');
    mpGrad.addColorStop(1, '#2244aa');
    ctx.fillStyle = mpGrad;
    ctx.fillRect(x, y, barWidth * mpPct, barHeight);

    ctx.strokeStyle = '#666666';
    ctx.strokeRect(x, y, barWidth, barHeight);

    ctx.fillStyle = '#ffffff';
    ctx.fillText(
      `MP: ${Math.ceil(this.displayMP)}/${Math.ceil(this.displayMaxMP)}`,
      x + barWidth / 2,
      y + barHeight / 2
    );

    // Stamina bar
    const stPct = this.displayST / this.displayMaxST;
    y += barHeight + spacing;

    ctx.fillStyle = 'rgba(40, 40, 40, 0.8)';
    ctx.fillRect(x, y, barWidth, barHeight);

    const stGrad = ctx.createLinearGradient(x, y, x + barWidth * stPct, y);
    stGrad.addColorStop(0, '#ffdd44');
    stGrad.addColorStop(1, '#aa8800');
    ctx.fillStyle = stGrad;
    ctx.fillRect(x, y, barWidth * stPct, barHeight);

    ctx.strokeStyle = '#666666';
    ctx.strokeRect(x, y, barWidth, barHeight);

    ctx.fillStyle = '#ffffff';
    ctx.fillText(
      `ST: ${Math.ceil(this.displayST)}/${Math.ceil(this.displayMaxST)}`,
      x + barWidth / 2,
      y + barHeight / 2
    );

    // XP bar
    const xpPct = this.displayXP / this.displayMaxXP;
    y += barHeight + spacing;

    ctx.fillStyle = 'rgba(40, 40, 40, 0.8)';
    ctx.fillRect(x, y, barWidth, barHeight);

    const xpGrad = ctx.createLinearGradient(x, y, x + barWidth * xpPct, y);
    xpGrad.addColorStop(0, '#44ff88');
    xpGrad.addColorStop(1, '#228844');
    ctx.fillStyle = xpGrad;
    ctx.fillRect(x, y, barWidth * xpPct, barHeight);

    ctx.strokeStyle = '#666666';
    ctx.strokeRect(x, y, barWidth, barHeight);

    ctx.fillStyle = '#ffffff';
    ctx.fillText(
      `Lv.${G.player.level} - ${Math.floor(this.displayXP)}/${Math.ceil(this.displayMaxXP)} XP`,
      x + barWidth / 2,
      y + barHeight / 2
    );
  },

  renderFloorInfo(ctx, x, y) {
    const theme = getFloorTheme(G.currentFloor);

    ctx.font = 'bold 18px sans-serif';
    ctx.textAlign = 'right';
    ctx.textBaseline = 'top';
    ctx.fillStyle = theme.color || '#ffffff';
    ctx.fillText(`Floor ${G.currentFloor} - ${theme.name}`, x, y);

    ctx.font = '16px sans-serif';
    ctx.fillStyle = '#ffcc00';
    ctx.fillText(`Score: ${G.score.toLocaleString()}`, x, y + 25);

    ctx.fillStyle = '#cccccc';
    ctx.fillText(Util.formatTime(G.time), x, y + 45);
  },

  renderBossBar(ctx, centerX, y) {
    if (!G.boss) return;

    const barWidth = G.canvas.width * 0.6;
    const barHeight = 24;
    const x = centerX - barWidth / 2;

    // Boss name
    ctx.font = 'bold 20px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'bottom';
    ctx.fillStyle = '#ff3333';
    ctx.shadowBlur = 10;
    ctx.shadowColor = '#ff0000';
    ctx.fillText(G.boss.name || 'BOSS', centerX, y + 15);
    ctx.shadowBlur = 0;

    // HP bar
    const hpPct = G.boss.hp / G.boss.maxHP;

    ctx.fillStyle = 'rgba(40, 40, 40, 0.9)';
    ctx.fillRect(x, y + 20, barWidth, barHeight);

    const bossGrad = ctx.createLinearGradient(x, y + 20, x + barWidth * hpPct, y + 20);
    bossGrad.addColorStop(0, '#ff6633');
    bossGrad.addColorStop(1, '#cc2200');
    ctx.fillStyle = bossGrad;
    ctx.fillRect(x, y + 20, barWidth * hpPct, barHeight);

    ctx.strokeStyle = '#ff3333';
    ctx.lineWidth = 2;
    ctx.strokeRect(x, y + 20, barWidth, barHeight);

    // Phase indicators
    if (G.boss.phases && G.boss.phases.length > 0) {
      const phaseWidth = 8;
      const phaseSpacing = 4;
      const totalPhaseWidth = G.boss.phases.length * (phaseWidth + phaseSpacing);
      let phaseX = centerX - totalPhaseWidth / 2;
      const phaseY = y + 50;

      for (let i = 0; i < G.boss.phases.length; i++) {
        ctx.fillStyle = (i <= G.boss.currentPhase) ? '#ff6633' : '#444444';
        ctx.fillRect(phaseX, phaseY, phaseWidth, phaseWidth);
        phaseX += phaseWidth + phaseSpacing;
      }
    }
  },

  renderAbilityHotbar(ctx, x, y) {
    const slotSize = 50;
    const spacing = 8;

    for (let i = 0; i < 4; i++) {
      const slotX = x + i * (slotSize + spacing);
      const ability = G.player.equippedAbilities[i];

      // Slot background
      ctx.fillStyle = 'rgba(40, 40, 40, 0.8)';
      ctx.fillRect(slotX, y, slotSize, slotSize);

      if (ability) {
        const abilityDef = ABILITY_DEFS[ability];
        if (abilityDef) {
          // Ability icon (colored square with initial)
          ctx.fillStyle = abilityDef.color || '#888888';
          ctx.fillRect(slotX + 5, y + 5, slotSize - 10, slotSize - 10);

          ctx.font = 'bold 20px sans-serif';
          ctx.fillStyle = '#ffffff';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(abilityDef.name[0], slotX + slotSize / 2, y + slotSize / 2);

          // Cooldown overlay
          const cooldown = G.player.abilityCooldowns[ability] || 0;
          if (cooldown > 0) {
            const cooldownPct = cooldown / abilityDef.cooldown;
            ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
            ctx.beginPath();
            ctx.moveTo(slotX + slotSize / 2, y + slotSize / 2);
            ctx.arc(
              slotX + slotSize / 2,
              y + slotSize / 2,
              slotSize / 2 - 5,
              -Math.PI / 2,
              -Math.PI / 2 + Math.PI * 2 * cooldownPct
            );
            ctx.closePath();
            ctx.fill();
          }
        }
      }

      // Border
      ctx.strokeStyle = '#666666';
      ctx.lineWidth = 2;
      ctx.strokeRect(slotX, y, slotSize, slotSize);

      // Key label
      ctx.font = 'bold 12px sans-serif';
      ctx.fillStyle = '#ffcc00';
      ctx.textAlign = 'left';
      ctx.textBaseline = 'top';
      ctx.fillText(`${i + 1}`, slotX + 4, y + 4);
    }
  },

  renderCombo(ctx, x, y) {
    const combo = G.combo;
    const multiplier = 1.0 + (combo - 1) * 0.1;

    // Color intensity based on combo
    let color = '#ffffff';
    if (combo >= 10) color = '#ff3333';
    else if (combo >= 5) color = '#ff9933';
    else if (combo >= 3) color = '#ffcc33';

    ctx.save();
    ctx.translate(x, y);
    ctx.scale(this.comboScale, this.comboScale);

    ctx.font = 'bold 48px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = color;
    ctx.shadowBlur = 15;
    ctx.shadowColor = color;
    ctx.fillText(`x${combo}`, 0, 0);

    ctx.font = 'bold 20px sans-serif';
    ctx.fillText('COMBO', 0, 35);

    ctx.font = '16px sans-serif';
    ctx.fillStyle = '#ffcc00';
    ctx.fillText(`${multiplier.toFixed(1)}x`, 0, 55);

    ctx.restore();
  },

  renderFloatingText(ctx) {
    for (let ft of G.floatingTexts) {
      const alpha = Util.clamp(ft.life, 0, 1);
      const screenPos = Camera.worldToScreen(ft.x, ft.y);

      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.font = `bold ${ft.size}px sans-serif`;
      ctx.fillStyle = ft.color;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.shadowBlur = 5;
      ctx.shadowColor = '#000000';
      ctx.fillText(ft.text, screenPos.x, screenPos.y);
      ctx.restore();
    }
  },

  addFloatingText(x, y, text, color, size) {
    G.floatingTexts.push({
      x: x,
      y: y,
      text: text,
      color: color,
      size: size || 20,
      life: 1.0,
      startY: y
    });
  },

  renderDeathOverlay(ctx) {
    const w = G.canvas.width;
    const h = G.canvas.height;

    // Red tinted overlay
    ctx.fillStyle = 'rgba(100, 0, 0, 0.6)';
    ctx.fillRect(0, 0, w, h);

    // YOU DIED
    ctx.font = 'bold 72px serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = '#ff0000';
    ctx.shadowBlur = 30;
    ctx.shadowColor = '#ff0000';
    ctx.fillText('YOU DIED', w / 2, h / 2 - 50);

    // Stats
    ctx.shadowBlur = 0;
    ctx.font = '24px sans-serif';
    ctx.fillStyle = '#ffffff';
    ctx.fillText(
      `Floor ${G.currentFloor} reached | ${G.enemiesSlain || 0} enemies slain`,
      w / 2,
      h / 2 + 30
    );

    ctx.font = 'italic 20px sans-serif';
    ctx.fillStyle = '#ffcc00';
    ctx.fillText('Press ENTER to try again', w / 2, h / 2 + 80);
    ctx.fillText('Press ESC for title screen', w / 2, h / 2 + 110);
  },

  renderGameOver(ctx) {
    const w = G.canvas.width;
    const h = G.canvas.height;

    // Dark overlay
    ctx.fillStyle = 'rgba(0, 0, 0, 0.85)';
    ctx.fillRect(0, 0, w, h);

    // GAME OVER
    ctx.font = 'bold 64px serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = '#cc0000';
    ctx.shadowBlur = 20;
    ctx.shadowColor = '#cc0000';
    ctx.fillText('GAME OVER', w / 2, h / 2 - 100);

    ctx.shadowBlur = 0;

    // Stats summary
    const stats = [
      `Final Score: ${G.score}`,
      `Deepest Floor: ${G.currentFloor}`,
      `Enemies Slain: ${G.enemiesSlain || 0}`,
      `Time: ${Util.formatTime(G.time)}`
    ];

    ctx.font = '22px sans-serif';
    ctx.fillStyle = '#ffffff';
    for (let i = 0; i < stats.length; i++) {
      ctx.fillText(stats[i], w / 2, h / 2 - 20 + i * 35);
    }

    // High score comparison
    const highScore = Save.loadHighScore();
    ctx.font = '18px sans-serif';
    ctx.fillStyle = G.score > highScore.score ? '#ffcc00' : '#888888';
    ctx.fillText(
      G.score > highScore.score ? 'NEW HIGH SCORE!' : `High Score: ${highScore.score}`,
      w / 2,
      h / 2 + 120
    );

    ctx.font = 'italic 20px sans-serif';
    ctx.fillStyle = '#ffcc00';
    ctx.fillText('Press ENTER for new game', w / 2, h / 2 + 160);
  },

  renderVictory(ctx, ending) {
    const w = G.canvas.width;
    const h = G.canvas.height;

    // Victory overlay with ending theme
    const endingData = (typeof ending === 'object') ? ending : {
      name: 'Victory',
      description: 'You have conquered the depths!',
      color: '#ffcc00'
    };
    const themeColor = endingData.color || '#ffcc00';

    const grad = ctx.createRadialGradient(w / 2, h / 2, 0, w / 2, h / 2, w / 2);
    grad.addColorStop(0, Util.rgba(255, 215, 0, 0.3));
    grad.addColorStop(1, 'rgba(0, 0, 0, 0.9)');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, w, h);

    // Victory header
    ctx.font = 'bold 56px serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = themeColor;
    ctx.shadowBlur = 25;
    ctx.shadowColor = themeColor;
    ctx.fillText('VICTORY!', w / 2, 80);

    // Ending title
    ctx.font = 'bold 32px serif';
    ctx.fillStyle = '#ffffff';
    ctx.shadowBlur = 10;
    ctx.fillText(endingData.name, w / 2, 140);

    // Ending description
    ctx.shadowBlur = 0;
    ctx.font = '18px sans-serif';
    ctx.fillStyle = '#cccccc';
    const descLines = this.wrapText(ctx, endingData.description, w - 100);
    for (let i = 0; i < descLines.length; i++) {
      ctx.fillText(descLines[i], w / 2, 200 + i * 25);
    }

    // Congratulations
    ctx.font = 'italic 24px serif';
    ctx.fillStyle = themeColor;
    ctx.fillText('You conquered the depths!', w / 2, h - 180);

    // Final stats
    ctx.font = '20px sans-serif';
    ctx.fillStyle = '#ffffff';
    ctx.fillText(`Final Score: ${G.score} | Time: ${Util.formatTime(G.time)}`, w / 2, h - 140);

    ctx.font = 'italic 18px sans-serif';
    ctx.fillStyle = '#ffcc00';
    ctx.fillText('Press ENTER to return to title', w / 2, h - 80);
  },

  wrapText(ctx, text, maxWidth) {
    const words = text.split(' ');
    const lines = [];
    let line = '';

    for (let word of words) {
      const testLine = line + word + ' ';
      const metrics = ctx.measureText(testLine);
      if (metrics.width > maxWidth && line.length > 0) {
        lines.push(line.trim());
        line = word + ' ';
      } else {
        line = testLine;
      }
    }
    if (line.length > 0) {
      lines.push(line.trim());
    }

    return lines;
  }
};
