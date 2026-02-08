// camera.js — Camera system with smooth follow, shake, zoom for Depths of the Abyss
// Depends on: G, TILE_SIZE from constants.js
// Depends on: Util from utils.js
// Depends on: TileMap from world/tilemap.js

const Camera = {
    x: 0,
    y: 0,
    targetX: 0,
    targetY: 0,
    zoom: 1.0,
    targetZoom: 1.0,
    shakeX: 0,
    shakeY: 0,
    shakeIntensity: 0,
    shakeDuration: 0,
    shakeMaxDuration: 0,
    viewportWidth: 0,
    viewportHeight: 0,
    smoothing: 0.08,

    init: function(canvas) {
        this.viewportWidth = canvas.width;
        this.viewportHeight = canvas.height;
        this.x = 0;
        this.y = 0;
        this.targetX = 0;
        this.targetY = 0;
        this.zoom = 1.0;
        this.targetZoom = 1.0;
        this.shakeX = 0;
        this.shakeY = 0;
        this.shakeIntensity = 0;
        this.shakeDuration = 0;
    },

    follow: function(entity, dt) {
        if (!entity) return;

        // Calculate target position (center entity in viewport)
        this.targetX = entity.x - this.viewportWidth / (2 * this.zoom);
        this.targetY = entity.y - this.viewportHeight / (2 * this.zoom);

        // Clamp to map bounds
        const maxX = TileMap.width * TILE_SIZE - this.viewportWidth / this.zoom;
        const maxY = TileMap.height * TILE_SIZE - this.viewportHeight / this.zoom;

        this.targetX = Util.clamp(this.targetX, 0, Math.max(0, maxX));
        this.targetY = Util.clamp(this.targetY, 0, Math.max(0, maxY));

        // Smooth lerp to target
        this.x = Util.lerp(this.x, this.targetX, this.smoothing);
        this.y = Util.lerp(this.y, this.targetY, this.smoothing);
    },

    shake: function(intensity, duration) {
        this.shakeIntensity = Math.max(this.shakeIntensity, intensity);
        this.shakeDuration = Math.max(this.shakeDuration, duration);
        this.shakeMaxDuration = duration;
    },

    updateShake: function(dt) {
        if (this.shakeDuration <= 0) {
            this.shakeX = 0;
            this.shakeY = 0;
            this.shakeIntensity = 0;
            this.shakeMaxDuration = 0;
            return;
        }

        // Decay shake duration
        this.shakeDuration -= dt;
        if (this.shakeDuration < 0) {
            this.shakeDuration = 0;
        }

        // Linear intensity decay based on remaining duration
        const progress = this.shakeMaxDuration > 0 ? this.shakeDuration / this.shakeMaxDuration : 0;
        const currentIntensity = this.shakeIntensity * progress;

        // Random offset within current intensity range
        this.shakeX = (Math.random() - 0.5) * 2 * currentIntensity;
        this.shakeY = (Math.random() - 0.5) * 2 * currentIntensity;
    },

    setZoom: function(zoom, smooth) {
        zoom = Util.clamp(zoom, 0.5, 2.0);

        if (smooth) {
            this.targetZoom = zoom;
        } else {
            this.zoom = zoom;
            this.targetZoom = zoom;
        }
    },

    updateZoom: function(dt) {
        if (Math.abs(this.zoom - this.targetZoom) > 0.01) {
            this.zoom = Util.lerp(this.zoom, this.targetZoom, 0.1);
        } else {
            this.zoom = this.targetZoom;
        }
    },

    worldToScreen: function(wx, wy) {
        return {
            x: (wx - this.x) * this.zoom + this.shakeX,
            y: (wy - this.y) * this.zoom + this.shakeY
        };
    },

    screenToWorld: function(sx, sy) {
        return {
            x: (sx - this.shakeX) / this.zoom + this.x,
            y: (sy - this.shakeY) / this.zoom + this.y
        };
    },

    isOnScreen: function(wx, wy, margin) {
        margin = margin || 0;
        const viewLeft = this.x - margin;
        const viewRight = this.x + this.viewportWidth / this.zoom + margin;
        const viewTop = this.y - margin;
        const viewBottom = this.y + this.viewportHeight / this.zoom + margin;

        return wx >= viewLeft && wx <= viewRight && wy >= viewTop && wy <= viewBottom;
    },

    getViewBounds: function() {
        return {
            left: this.x,
            top: this.y,
            right: this.x + this.viewportWidth / this.zoom,
            bottom: this.y + this.viewportHeight / this.zoom
        };
    },

    update: function(dt) {
        // Combined update: shake, zoom
        this.updateShake(dt);
        this.updateZoom(dt);
    },

    applyTransform: function(ctx) {
        ctx.save();
        ctx.scale(this.zoom, this.zoom);
        ctx.translate(-this.x + this.shakeX / this.zoom, -this.y + this.shakeY / this.zoom);
    },

    resetTransform: function(ctx) {
        ctx.restore();
    }
};
