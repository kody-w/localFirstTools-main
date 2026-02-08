// Particle System — Pooled particle effects for visual flair
// Defines global FX object
// Dependencies: G, ELEMENT, Util from utils.js, Camera from world/camera.js

const FX = {
  pool: [],
  activeCount: 0,
  maxParticles: 500,

  init() {
    this.pool = [];
    this.activeCount = 0;

    // Pre-allocate particle pool
    for (let i = 0; i < this.maxParticles; i++) {
      this.pool.push({
        active: false,
        x: 0,
        y: 0,
        vx: 0,
        vy: 0,
        life: 0,
        maxLife: 1,
        size: 4,
        color: '#ffffff',
        alpha: 1,
        gravity: 0,
        friction: 1,
        shape: 'circle',
        rotation: 0,
        rotSpeed: 0
      });
    }
  },

  spawn(x, y, vx, vy, life, size, color, options = {}) {
    // Find inactive particle
    let particle = null;
    for (let i = 0; i < this.pool.length; i++) {
      if (!this.pool[i].active) {
        particle = this.pool[i];
        break;
      }
    }

    // If pool exhausted, reuse oldest particle
    if (!particle) {
      particle = this.pool[0];
    }

    // Initialize particle
    particle.active = true;
    particle.x = x;
    particle.y = y;
    particle.vx = vx;
    particle.vy = vy;
    particle.life = life;
    particle.maxLife = life;
    particle.size = size;
    particle.color = color;
    particle.alpha = 1;
    particle.gravity = options.gravity || 0;
    particle.friction = options.friction || 1;
    particle.shape = options.shape || 'circle';
    particle.rotation = options.rotation || 0;
    particle.rotSpeed = options.rotSpeed || 0;

    this.activeCount++;
  },

  update(dt) {
    for (let i = 0; i < this.pool.length; i++) {
      const p = this.pool[i];
      if (!p.active) continue;

      // Move
      p.x += p.vx * dt;
      p.y += p.vy * dt;

      // Apply gravity
      p.vy += p.gravity * dt;

      // Apply friction
      p.vx *= p.friction;
      p.vy *= p.friction;

      // Update rotation
      p.rotation += p.rotSpeed * dt;

      // Decrease life
      p.life -= dt;

      // Fade alpha and shrink based on remaining life
      const lifePercent = p.life / p.maxLife;
      p.alpha = lifePercent;
      p.size = p.size * (0.5 + lifePercent * 0.5);

      // Deactivate if dead
      if (p.life <= 0) {
        p.active = false;
        this.activeCount--;
      }
    }
  },

  render(ctx, camera) {
    for (let i = 0; i < this.pool.length; i++) {
      const p = this.pool[i];
      if (!p.active) continue;

      // Skip if not on screen
      if (!Camera.isOnScreen(p.x, p.y, p.size * 2, p.size * 2)) continue;

      const screenX = p.x - camera.x;
      const screenY = p.y - camera.y;

      ctx.save();
      ctx.globalAlpha = p.alpha;
      ctx.fillStyle = p.color;
      ctx.translate(screenX, screenY);
      ctx.rotate(p.rotation);

      // Draw shape
      if (p.shape === 'circle') {
        ctx.beginPath();
        ctx.arc(0, 0, p.size, 0, Math.PI * 2);
        ctx.fill();
      } else if (p.shape === 'square') {
        ctx.fillRect(-p.size, -p.size, p.size * 2, p.size * 2);
      } else if (p.shape === 'triangle') {
        ctx.beginPath();
        ctx.moveTo(0, -p.size);
        ctx.lineTo(p.size, p.size);
        ctx.lineTo(-p.size, p.size);
        ctx.closePath();
        ctx.fill();
      } else if (p.shape === 'star') {
        this.drawStar(ctx, 0, 0, 5, p.size, p.size / 2);
      }

      ctx.restore();
    }
  },

  drawStar(ctx, x, y, spikes, outerRadius, innerRadius) {
    let rot = Math.PI / 2 * 3;
    let step = Math.PI / spikes;

    ctx.beginPath();
    ctx.moveTo(x, y - outerRadius);

    for (let i = 0; i < spikes; i++) {
      ctx.lineTo(x + Math.cos(rot) * outerRadius, y + Math.sin(rot) * outerRadius);
      rot += step;
      ctx.lineTo(x + Math.cos(rot) * innerRadius, y + Math.sin(rot) * innerRadius);
      rot += step;
    }

    ctx.closePath();
    ctx.fill();
  },

  // Preset emitter functions
  blood(x, y) {
    for (let i = 0; i < 15; i++) {
      const angle = Math.random() * Math.PI * 2;
      const speed = Util.randFloat(30, 80);
      this.spawn(
        x, y,
        Math.cos(angle) * speed,
        Math.sin(angle) * speed,
        Util.randFloat(0.3, 0.6),
        Util.randFloat(2, 4),
        '#8b0000',
        { gravity: 200, friction: 0.95, shape: 'circle' }
      );
    }
  },

  sparks(x, y) {
    for (let i = 0; i < 20; i++) {
      const angle = Math.random() * Math.PI * 2;
      const speed = Util.randFloat(80, 150);
      this.spawn(
        x, y,
        Math.cos(angle) * speed,
        Math.sin(angle) * speed,
        Util.randFloat(0.2, 0.4),
        Util.randFloat(1, 3),
        Util.pick(['#ffff00', '#ffffff', '#ffaa00']),
        { gravity: 0, friction: 0.98, shape: 'circle' }
      );
    }
  },

  fire(x, y) {
    for (let i = 0; i < 12; i++) {
      const angle = -Math.PI / 2 + Util.randFloat(-0.3, 0.3);
      const speed = Util.randFloat(20, 50);
      this.spawn(
        x + Util.randFloat(-4, 4), y,
        Math.cos(angle) * speed,
        Math.sin(angle) * speed,
        Util.randFloat(0.5, 1.0),
        Util.randFloat(3, 6),
        Util.pick(['#ff4400', '#ff6600', '#ffaa00', '#ff8800']),
        { gravity: -50, friction: 0.97, shape: 'circle' }
      );
    }
  },

  smoke(x, y) {
    for (let i = 0; i < 8; i++) {
      const angle = -Math.PI / 2 + Util.randFloat(-0.2, 0.2);
      const speed = Util.randFloat(10, 30);
      this.spawn(
        x + Util.randFloat(-6, 6), y,
        Math.cos(angle) * speed,
        Math.sin(angle) * speed,
        Util.randFloat(1.0, 2.0),
        Util.randFloat(4, 8),
        Util.pick(['#666666', '#888888', '#555555']),
        { gravity: -20, friction: 0.99, shape: 'circle' }
      );
    }
  },

  magic(x, y, color) {
    for (let i = 0; i < 25; i++) {
      const angle = Math.random() * Math.PI * 2;
      const speed = Util.randFloat(40, 100);
      this.spawn(
        x, y,
        Math.cos(angle) * speed,
        Math.sin(angle) * speed,
        Util.randFloat(0.4, 0.8),
        Util.randFloat(2, 4),
        color,
        { gravity: 0, friction: 0.95, shape: 'star', rotSpeed: Util.randFloat(-5, 5) }
      );
    }
  },

  ice(x, y) {
    for (let i = 0; i < 18; i++) {
      const angle = Math.random() * Math.PI * 2;
      const speed = Util.randFloat(50, 100);
      this.spawn(
        x, y,
        Math.cos(angle) * speed,
        Math.sin(angle) * speed,
        Util.randFloat(0.4, 0.7),
        Util.randFloat(2, 5),
        Util.pick(['#00ffff', '#aaffff', '#88eeff']),
        { gravity: 0, friction: 0.96, shape: 'triangle', rotation: angle }
      );
    }
  },

  poison(x, y) {
    for (let i = 0; i < 10; i++) {
      const angle = -Math.PI / 2 + Util.randFloat(-0.4, 0.4);
      const speed = Util.randFloat(15, 40);
      this.spawn(
        x + Util.randFloat(-4, 4), y,
        Math.cos(angle) * speed,
        Math.sin(angle) * speed,
        Util.randFloat(0.6, 1.2),
        Util.randFloat(3, 6),
        Util.pick(['#00ff00', '#44ff44', '#88ff44']),
        { gravity: -30, friction: 0.98, shape: 'circle' }
      );
    }
  },

  lightning(x, y) {
    for (let i = 0; i < 15; i++) {
      const angle = Math.random() * Math.PI * 2;
      const speed = Util.randFloat(100, 200);
      this.spawn(
        x, y,
        Math.cos(angle) * speed,
        Math.sin(angle) * speed,
        Util.randFloat(0.1, 0.2),
        Util.randFloat(2, 4),
        Util.pick(['#ffffff', '#aaffff']),
        { gravity: 0, friction: 0.9, shape: 'circle' }
      );
    }
  },

  heal(x, y) {
    for (let i = 0; i < 20; i++) {
      const angle = -Math.PI / 2 + Util.randFloat(-0.5, 0.5);
      const speed = Util.randFloat(20, 60);
      this.spawn(
        x + Util.randFloat(-8, 8), y,
        Math.cos(angle) * speed,
        Math.sin(angle) * speed,
        Util.randFloat(0.5, 1.0),
        Util.randFloat(2, 4),
        '#00ff44',
        { gravity: -40, friction: 0.97, shape: 'star', rotSpeed: Util.randFloat(-3, 3) }
      );
    }
  },

  levelup(x, y) {
    for (let i = 0; i < 40; i++) {
      const angle = Math.random() * Math.PI * 2;
      const speed = Util.randFloat(60, 150);
      this.spawn(
        x, y,
        Math.cos(angle) * speed,
        Math.sin(angle) * speed,
        Util.randFloat(0.6, 1.2),
        Util.randFloat(3, 6),
        '#ffff00',
        { gravity: -20, friction: 0.96, shape: 'star', rotSpeed: Util.randFloat(-8, 8) }
      );
    }
  },

  death(x, y, color) {
    for (let i = 0; i < 30; i++) {
      const angle = Math.random() * Math.PI * 2;
      const speed = Util.randFloat(40, 120);
      this.spawn(
        x, y,
        Math.cos(angle) * speed,
        Math.sin(angle) * speed,
        Util.randFloat(0.4, 0.8),
        Util.randFloat(3, 6),
        color,
        { gravity: 150, friction: 0.95, shape: 'square' }
      );
    }
  },

  dust(x, y) {
    for (let i = 0; i < 5; i++) {
      const angle = Math.random() * Math.PI * 2;
      const speed = Util.randFloat(10, 30);
      this.spawn(
        x + Util.randFloat(-4, 4), y,
        Math.cos(angle) * speed,
        Math.sin(angle) * speed,
        Util.randFloat(0.3, 0.6),
        Util.randFloat(1, 2),
        '#8b7355',
        { gravity: 0, friction: 0.98, shape: 'circle' }
      );
    }
  },

  dash(x, y, angle) {
    for (let i = 0; i < 8; i++) {
      const speed = Util.randFloat(-20, -60);
      this.spawn(
        x, y,
        Math.cos(angle) * speed,
        Math.sin(angle) * speed,
        Util.randFloat(0.2, 0.4),
        Util.randFloat(2, 4),
        '#ffffff',
        { gravity: 0, friction: 0.95, shape: 'circle' }
      );
    }
  },

  explosion(x, y, radius, color) {
    const count = Math.floor(radius / 2);
    for (let i = 0; i < count; i++) {
      const angle = Math.random() * Math.PI * 2;
      const speed = Util.randFloat(50, 150);
      this.spawn(
        x, y,
        Math.cos(angle) * speed,
        Math.sin(angle) * speed,
        Util.randFloat(0.4, 0.8),
        Util.randFloat(4, 8),
        color,
        { gravity: 50, friction: 0.94, shape: 'circle' }
      );
    }
  },

  loot(x, y, rarity) {
    const color = window.RARITY_COLORS ? RARITY_COLORS[rarity] : '#ffffff';
    for (let i = 0; i < 12; i++) {
      const angle = Math.random() * Math.PI * 2;
      const speed = Util.randFloat(20, 60);
      this.spawn(
        x, y,
        Math.cos(angle) * speed,
        Math.sin(angle) * speed,
        Util.randFloat(0.5, 0.8),
        Util.randFloat(2, 4),
        color,
        { gravity: 0, friction: 0.97, shape: 'star', rotSpeed: Util.randFloat(-5, 5) }
      );
    }
  },

  campfire(x, y) {
    // Continuous fire + smoke + embers (called each frame)
    if (Math.random() < 0.3) {
      const angle = -Math.PI / 2 + Util.randFloat(-0.2, 0.2);
      const speed = Util.randFloat(15, 35);
      this.spawn(
        x + Util.randFloat(-6, 6), y,
        Math.cos(angle) * speed,
        Math.sin(angle) * speed,
        Util.randFloat(0.4, 0.8),
        Util.randFloat(3, 5),
        Util.pick(['#ff4400', '#ff6600', '#ffaa00']),
        { gravity: -40, friction: 0.97, shape: 'circle' }
      );
    }

    if (Math.random() < 0.1) {
      const angle = -Math.PI / 2 + Util.randFloat(-0.15, 0.15);
      const speed = Util.randFloat(8, 20);
      this.spawn(
        x + Util.randFloat(-8, 8), y - 10,
        Math.cos(angle) * speed,
        Math.sin(angle) * speed,
        Util.randFloat(0.8, 1.5),
        Util.randFloat(4, 7),
        '#555555',
        { gravity: -15, friction: 0.99, shape: 'circle' }
      );
    }

    if (Math.random() < 0.05) {
      const angle = -Math.PI / 2 + Util.randFloat(-0.4, 0.4);
      const speed = Util.randFloat(30, 60);
      this.spawn(
        x, y,
        Math.cos(angle) * speed,
        Math.sin(angle) * speed,
        Util.randFloat(0.5, 1.0),
        Util.randFloat(1, 2),
        '#ffaa00',
        { gravity: -10, friction: 0.98, shape: 'circle' }
      );
    }
  },

  void(x, y) {
    for (let i = 0; i < 15; i++) {
      const angle = Math.random() * Math.PI * 2;
      const speed = Util.randFloat(20, 60);
      this.spawn(
        x, y,
        Math.cos(angle) * speed,
        Math.sin(angle) * speed,
        Util.randFloat(0.6, 1.2),
        Util.randFloat(3, 6),
        Util.pick(['#4400ff', '#000000', '#6600aa']),
        { gravity: 0, friction: 0.96, shape: 'circle', rotSpeed: Util.randFloat(-4, 4) }
      );
    }
  },

  critical(x, y) {
    for (let i = 0; i < 20; i++) {
      const angle = Math.random() * Math.PI * 2;
      const speed = Util.randFloat(60, 120);
      this.spawn(
        x, y,
        Math.cos(angle) * speed,
        Math.sin(angle) * speed,
        Util.randFloat(0.3, 0.6),
        Util.randFloat(4, 7),
        '#ffff00',
        { gravity: 0, friction: 0.94, shape: 'star', rotSpeed: Util.randFloat(-10, 10) }
      );
    }
  },

  parry(x, y) {
    for (let i = 0; i < 16; i++) {
      const angle = (i / 16) * Math.PI * 2;
      const speed = 80;
      this.spawn(
        x, y,
        Math.cos(angle) * speed,
        Math.sin(angle) * speed,
        Util.randFloat(0.3, 0.5),
        Util.randFloat(2, 4),
        '#ffffff',
        { gravity: 0, friction: 0.92, shape: 'circle' }
      );
    }
  }
};
