// transitions.js
// Floor transitions, boss intros, screen fades, death/victory transitions

const Transitions = {
  active: false,
  type: null,
  progress: 0,
  duration: 1.0,
  callback: null,
  callbackFired: false,
  data: {},

  start(type, duration, callback, data) {
    this.active = true;
    this.type = type;
    this.progress = 0;
    this.duration = duration;
    this.callback = callback;
    this.callbackFired = false;
    this.data = data || {};
    G.gameState = STATE.TRANSITION;
  },

  update(dt) {
    if (!this.active) return;

    this.progress += dt / this.duration;

    // Fire callback at midpoint
    if (this.progress >= 0.5 && !this.callbackFired && this.callback) {
      this.callback();
      this.callbackFired = true;
    }

    // End transition
    if (this.progress >= 1.0) {
      this.end();
    }
  },

  end() {
    this.active = false;
    this.type = null;

    // Restore game state
    if (G.gameState === STATE.TRANSITION) {
      G.gameState = STATE.PLAYING;
    }
  },

  render(ctx) {
    if (!this.active) return;

    switch (this.type) {
      case 'floorTransition':
        this.renderFloorTransition(ctx);
        break;
      case 'bossIntro':
        this.renderBossIntro(ctx);
        break;
      case 'fadeIn':
        this.renderFadeIn(ctx);
        break;
      case 'fadeOut':
        this.renderFadeOut(ctx);
        break;
      case 'deathTransition':
        this.renderDeathTransition(ctx);
        break;
      case 'victoryTransition':
        this.renderVictoryTransition(ctx);
        break;
    }
  },

  renderFloorTransition(ctx) {
    const w = G.canvas.width;
    const h = G.canvas.height;

    const easeProgress = this.easeInOutCubic(this.progress);

    // Iris transition
    const maxRadius = Math.sqrt(w * w + h * h) / 2;
    let radius;

    if (this.progress < 0.5) {
      // Close iris
      radius = maxRadius * (1.0 - easeProgress * 2);
    } else {
      // Open iris
      radius = maxRadius * ((easeProgress - 0.5) * 2);
    }

    // Draw black fill with circular cutout
    ctx.save();
    ctx.fillStyle = '#000000';

    if (this.progress < 0.5) {
      // Closing - draw black ring
      ctx.beginPath();
      ctx.rect(0, 0, w, h);
      ctx.arc(w / 2, h / 2, radius, 0, Math.PI * 2, true);
      ctx.fill();
    } else {
      // Opening - draw expanding black with hole
      ctx.beginPath();
      ctx.rect(0, 0, w, h);
      ctx.arc(w / 2, h / 2, radius, 0, Math.PI * 2, true);
      ctx.fill();
    }

    // Show floor text during black
    if (this.progress > 0.4 && this.progress < 0.6) {
      const textAlpha = this.progress < 0.5
        ? (this.progress - 0.4) * 10
        : (0.6 - this.progress) * 10;

      ctx.globalAlpha = textAlpha;

      const floorNum = this.data.floor || G.currentFloor;
      const theme = getFloorTheme(floorNum);

      ctx.font = 'bold 48px serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillStyle = theme.color || '#ffffff';
      ctx.shadowBlur = 20;
      ctx.shadowColor = theme.color || '#ffffff';
      ctx.fillText(`Floor ${floorNum}`, w / 2, h / 2 - 30);

      ctx.font = 'italic 28px serif';
      ctx.fillText(theme.name, w / 2, h / 2 + 20);
    }

    ctx.restore();
  },

  renderBossIntro(ctx) {
    const w = G.canvas.width;
    const h = G.canvas.height;

    const easeProgress = this.easeInOutCubic(this.progress);

    // Cinematic letterbox bars
    const barHeight = h * 0.15 * easeProgress;

    ctx.fillStyle = '#000000';
    ctx.fillRect(0, 0, w, barHeight);
    ctx.fillRect(0, h - barHeight, w, barHeight);

    // Boss name animation
    if (this.progress > 0.2 && this.progress < 0.8) {
      const textProgress = (this.progress - 0.2) / 0.6;
      const textAlpha = textProgress < 0.5
        ? textProgress * 2
        : 1.0 - (textProgress - 0.5) * 2;

      ctx.save();
      ctx.globalAlpha = textAlpha;

      const bossName = this.data.bossName || 'BOSS';

      ctx.font = 'bold 56px serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillStyle = '#ff3333';
      ctx.shadowBlur = 30;
      ctx.shadowColor = '#ff0000';
      ctx.fillText(bossName, w / 2, h / 2);

      ctx.font = 'italic 24px serif';
      ctx.fillStyle = '#ffffff';
      ctx.shadowBlur = 10;
      ctx.fillText('BOSS FIGHT', w / 2, h / 2 + 60);

      ctx.restore();
    }

    // Screen shake effect
    if (this.progress > 0.6 && this.progress < 0.8 && window.Camera) {
      const shakeIntensity = 10;
      const shake = (this.progress - 0.6) / 0.2;
      const shakeAmount = shakeIntensity * (1.0 - shake);
      Camera.shake(shakeAmount, 0.2);
    }
  },

  renderFadeIn(ctx) {
    const w = G.canvas.width;
    const h = G.canvas.height;

    const alpha = 1.0 - this.easeInOutQuad(this.progress);

    ctx.fillStyle = Util.rgba(0, 0, 0, alpha);
    ctx.fillRect(0, 0, w, h);
  },

  renderFadeOut(ctx) {
    const w = G.canvas.width;
    const h = G.canvas.height;

    const alpha = this.easeInOutQuad(this.progress);

    ctx.fillStyle = Util.rgba(0, 0, 0, alpha);
    ctx.fillRect(0, 0, w, h);
  },

  renderDeathTransition(ctx) {
    const w = G.canvas.width;
    const h = G.canvas.height;

    const easeProgress = this.easeInOutQuad(this.progress);

    // Red vignette intensifying
    const vignetteAlpha = 0.7 * easeProgress;

    const grad = ctx.createRadialGradient(w / 2, h / 2, w * 0.3, w / 2, h / 2, w * 0.7);
    grad.addColorStop(0, Util.rgba(0, 0, 0, 0));
    grad.addColorStop(1, Util.rgba(150, 0, 0, vignetteAlpha));

    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, w, h);

    // Darken entire screen
    ctx.fillStyle = Util.rgba(0, 0, 0, easeProgress * 0.5);
    ctx.fillRect(0, 0, w, h);

    // Show death screen at end
    if (this.progress > 0.8) {
      HUD.renderDeathOverlay(ctx);
    }
  },

  renderVictoryTransition(ctx) {
    const w = G.canvas.width;
    const h = G.canvas.height;

    const easeProgress = this.easeInOutCubic(this.progress);

    // Golden light expanding
    const radius = Math.sqrt(w * w + h * h) * easeProgress;

    const grad = ctx.createRadialGradient(w / 2, h / 2, 0, w / 2, h / 2, radius);
    grad.addColorStop(0, Util.rgba(255, 215, 0, 0.8));
    grad.addColorStop(0.5, Util.rgba(255, 215, 0, 0.3));
    grad.addColorStop(1, Util.rgba(0, 0, 0, 0));

    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, w, h);

    // Victory text flash
    if (this.progress > 0.3 && this.progress < 0.6) {
      const textProgress = (this.progress - 0.3) / 0.3;
      const textAlpha = Math.sin(textProgress * Math.PI);

      ctx.save();
      ctx.globalAlpha = textAlpha;

      ctx.font = 'bold 64px serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillStyle = '#ffcc00';
      ctx.shadowBlur = 40;
      ctx.shadowColor = '#ffcc00';
      ctx.fillText('VICTORY', w / 2, h / 2);

      ctx.restore();
    }

    // Fade to ending screen
    if (this.progress > 0.7) {
      const fadeAlpha = (this.progress - 0.7) / 0.3;
      ctx.fillStyle = Util.rgba(0, 0, 0, fadeAlpha);
      ctx.fillRect(0, 0, w, h);
    }

    // Show ending screen at end
    if (this.progress > 0.9) {
      const ending = this.data.ending || 'true';
      HUD.renderVictory(ctx, ending);
    }
  },

  // Easing functions
  easeInOutQuad(t) {
    return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
  },

  easeInOutCubic(t) {
    return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
  },

  easeOutElastic(t) {
    const c4 = (2 * Math.PI) / 3;
    return t === 0 ? 0 : t === 1 ? 1 : Math.pow(2, -10 * t) * Math.sin((t * 10 - 0.75) * c4) + 1;
  }
};
