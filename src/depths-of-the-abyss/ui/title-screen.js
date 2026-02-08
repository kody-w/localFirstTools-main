// title-screen.js
// Animated title screen with menu navigation, particles, and controls overlay

const TitleScreen = {
  titleAlpha: 0,
  menuIndex: 0,
  particles: [],
  showControls: false,
  showCredits: false,
  menuHoverY: -1,
  particleTime: 0,

  init() {
    this.titleAlpha = 0;
    this.menuIndex = 0;
    this.particles = [];
    this.showControls = false;
    this.showCredits = false;
    this.menuHoverY = -1;
    this.particleTime = 0;

    // Initialize background particles
    for (let i = 0; i < 50; i++) {
      this.particles.push({
        x: Math.random() * G.canvas.width,
        y: Math.random() * G.canvas.height,
        size: Math.random() * 2 + 1,
        speed: Math.random() * 20 + 10,
        alpha: Math.random() * 0.3 + 0.1
      });
    }
  },

  getMenuItems() {
    const difficultyName = G.difficulty || 'Normal';
    const items = [
      { label: 'New Game', enabled: true },
      { label: 'Continue', enabled: Save.hasSave() },
      { label: 'Controls', enabled: true },
      { label: `Difficulty: ${difficultyName}`, enabled: true }
    ];
    return items;
  },

  update(dt) {
    // Fade in title
    this.titleAlpha = Util.clamp(this.titleAlpha + dt * 0.5, 0, 1);

    // Animate particles
    this.particleTime += dt;
    for (let p of this.particles) {
      p.y -= p.speed * dt;
      if (p.y < -10) {
        p.y = G.canvas.height + 10;
        p.x = Math.random() * G.canvas.width;
      }
    }

    // Handle controls overlay
    if (this.showControls) {
      if (Input.justPressed('Escape') || Input.justPressed('KeyI') ||
          Input.justPressed('KeyC') || Input.justPressed('KeyK') ||
          Input.justPressed('Enter') || Input.justPressed('Space')) {
        this.showControls = false;
        SFX.playSound('menu_select');
      }
      return;
    }

    const items = this.getMenuItems();

    // Mouse hover
    if (Input.mouse.y > 0) {
      const menuStartY = G.canvas.height / 2 + 60;
      const itemHeight = 50;
      const idx = Math.floor((Input.mouse.y - menuStartY) / itemHeight);
      if (idx >= 0 && idx < items.length && items[idx].enabled) {
        if (this.menuIndex !== idx) {
          this.menuIndex = idx;
          SFX.playSound('menu_hover');
        }
      }
    }

    // Keyboard navigation
    if (Input.justPressed('ArrowDown') || Input.justPressed('KeyS')) {
      do {
        this.menuIndex = (this.menuIndex + 1) % items.length;
      } while (!items[this.menuIndex].enabled);
      SFX.playSound('menu_hover');
    }
    if (Input.justPressed('ArrowUp') || Input.justPressed('KeyW')) {
      do {
        this.menuIndex = (this.menuIndex - 1 + items.length) % items.length;
      } while (!items[this.menuIndex].enabled);
      SFX.playSound('menu_hover');
    }

    // Selection
    if (Input.justPressed('Enter') || Input.justPressed('Space')) {
      this.selectMenuItem();
    }

    // Mouse click
    if (Input.mouse.clicked) {
      const menuStartY = G.canvas.height / 2 + 60;
      const itemHeight = 50;
      const idx = Math.floor((Input.mouse.y - menuStartY) / itemHeight);
      if (idx >= 0 && idx < items.length && items[idx].enabled && idx === this.menuIndex) {
        this.selectMenuItem();
      }
    }
  },

  selectMenuItem() {
    const items = this.getMenuItems();
    const item = items[this.menuIndex];

    SFX.playSound('menu_select');

    if (item.label === 'New Game') {
      this.startGame();
    } else if (item.label === 'Continue') {
      this.continueGame();
    } else if (item.label === 'Controls') {
      this.showControls = true;
    } else if (item.label.startsWith('Difficulty:')) {
      this.cycleDifficulty();
    }
  },

  startGame() {
    Save.resetGame();
    G.gameState = STATE.PLAYING;
    // Floor generation will be handled by main game loop
    Transitions.start('fadeOut', 0.5, () => {
      // Game initialization happens here
    }, {});
  },

  continueGame() {
    if (Save.hasSave()) {
      Save.loadGame();
      G.gameState = STATE.PLAYING;
      Transitions.start('fadeIn', 0.5, null, {});
    }
  },

  cycleDifficulty() {
    const difficulties = ['Easy', 'Normal', 'Hard'];
    const current = G.difficulty || 'Normal';
    const idx = difficulties.indexOf(current);
    const nextIdx = (idx + 1) % difficulties.length;
    G.difficulty = difficulties[nextIdx];

    Save.saveSettings();
  },

  render(ctx) {
    const w = G.canvas.width;
    const h = G.canvas.height;

    // Background gradient
    const grad = ctx.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, '#1a0033');
    grad.addColorStop(0.5, '#0d001a');
    grad.addColorStop(1, '#000000');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, w, h);

    // Background particles
    ctx.save();
    for (let p of this.particles) {
      ctx.fillStyle = Util.rgba(150, 100, 180, p.alpha);
      ctx.fillRect(p.x, p.y, p.size, p.size);
    }
    ctx.restore();

    // Title
    ctx.save();
    ctx.globalAlpha = this.titleAlpha;

    const titleY = h * 0.3;
    const pulse = Math.sin(G.time * 2) * 0.1 + 0.9;

    // Title glow
    ctx.shadowBlur = 30 * pulse;
    ctx.shadowColor = '#cc0000';

    ctx.font = 'bold 56px serif';
    ctx.fillStyle = '#cc3333';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    const titleText = 'DEPTHS OF THE ABYSS';
    const letterSpacing = 8;
    let totalWidth = ctx.measureText(titleText.replace(/ /g, '')).width + (titleText.length - 1) * letterSpacing;
    let startX = (w - totalWidth) / 2;

    for (let i = 0; i < titleText.length; i++) {
      ctx.fillText(titleText[i], startX, titleY);
      startX += ctx.measureText(titleText[i]).width + letterSpacing;
    }

    // Subtitle
    ctx.shadowBlur = 10;
    ctx.shadowColor = '#660000';
    ctx.font = 'italic 20px serif';
    ctx.fillStyle = '#999999';
    ctx.fillText('A Dark Fantasy Roguelike', w / 2, titleY + 60);

    ctx.restore();

    // Menu items
    const items = this.getMenuItems();
    const menuStartY = h / 2 + 60;
    const itemHeight = 50;

    ctx.font = 'bold 28px sans-serif';
    ctx.textAlign = 'center';

    for (let i = 0; i < items.length; i++) {
      const y = menuStartY + i * itemHeight;
      const isSelected = (i === this.menuIndex);
      const isEnabled = items[i].enabled;

      ctx.save();

      if (isSelected) {
        const scale = 1.0 + Math.sin(G.time * 4) * 0.05;
        ctx.translate(w / 2, y);
        ctx.scale(scale, scale);
        ctx.translate(-w / 2, -y);

        ctx.fillStyle = isEnabled ? '#ffcc00' : '#666666';
        ctx.shadowBlur = 15;
        ctx.shadowColor = '#ffaa00';

        // Arrow indicator
        ctx.font = 'bold 28px sans-serif';
        ctx.fillText('>', w / 2 - 150, y);
      } else {
        ctx.fillStyle = isEnabled ? '#cccccc' : '#444444';
      }

      ctx.fillText(items[i].label, w / 2, y);
      ctx.restore();
    }

    // High score
    const highScore = Save.loadHighScore();
    ctx.font = '18px sans-serif';
    ctx.fillStyle = '#888888';
    ctx.textAlign = 'center';
    ctx.fillText(
      `High Score: ${highScore.score} | Deepest Floor: ${highScore.deepestFloor}`,
      w / 2,
      h - 40
    );

    // Controls overlay
    if (this.showControls) {
      this.renderControlsOverlay(ctx);
    }
  },

  renderControlsOverlay(ctx) {
    const w = G.canvas.width;
    const h = G.canvas.height;

    // Dark backdrop
    ctx.fillStyle = 'rgba(0, 0, 0, 0.85)';
    ctx.fillRect(0, 0, w, h);

    ctx.fillStyle = '#ffffff';
    ctx.textAlign = 'center';

    // Header
    ctx.font = 'bold 32px sans-serif';
    ctx.fillText('HOW TO PLAY', w / 2, 60);

    ctx.font = '20px sans-serif';
    ctx.textAlign = 'left';

    const controls = [
      'WASD / Arrow Keys - Move',
      'Space - Attack',
      'Shift - Dodge Roll',
      'E - Interact / Parry',
      'I - Inventory',
      'K - Skill Tree',
      'C - Crafting (at campfire)',
      'P / Esc - Pause',
      '1-4 - Use Abilities',
      'Tab - Toggle Minimap',
      '',
      'Touch Controls:',
      'Left side - Virtual joystick for movement',
      'Right side - Attack, dodge, ability buttons'
    ];

    const startY = 120;
    for (let i = 0; i < controls.length; i++) {
      ctx.fillText(controls[i], w / 2 - 250, startY + i * 30);
    }

    // Close instruction
    ctx.font = 'italic 18px sans-serif';
    ctx.fillStyle = '#ffcc00';
    ctx.textAlign = 'center';
    ctx.fillText('Press any key to close', w / 2, h - 40);
  }
};
