// lighting.js — Dynamic lighting system for Depths of the Abyss
// Depends on: G, TILE_SIZE from constants.js
// Depends on: Util from utils.js

const Lighting = {
    lights: [],
    darkOverlay: null,
    darkCtx: null,
    nextId: 0,
    playerLight: null,

    init: function(w, h) {
        this.lights = [];
        this.nextId = 0;

        // Create offscreen canvas for darkness overlay
        this.darkOverlay = document.createElement('canvas');
        this.darkOverlay.width = w * TILE_SIZE;
        this.darkOverlay.height = h * TILE_SIZE;
        this.darkCtx = this.darkOverlay.getContext('2d');
    },

    addLight: function(x, y, radius, color, intensity, flicker) {
        const light = {
            id: this.nextId++,
            x: x,
            y: y,
            radius: radius,
            baseRadius: radius,
            color: color || '#ffffff',
            intensity: intensity || 1,
            flicker: flicker || false,
            flickerOffset: Math.random() * Math.PI * 2,
            flickerFreq: 2 + Math.random() * 3,
            type: 'static'
        };

        this.lights.push(light);
        return light.id;
    },

    removeLight: function(id) {
        this.lights = this.lights.filter(l => l.id !== id);
    },

    update: function(dt) {
        // Update flicker animations
        for (let i = 0; i < this.lights.length; i++) {
            const light = this.lights[i];

            if (light.flicker) {
                // Oscillate radius with sin wave
                const t = G.time * light.flickerFreq + light.flickerOffset;
                const flickerAmount = Math.sin(t) * 0.2 + Math.sin(t * 2) * 0.1;
                light.radius = light.baseRadius * (1 + flickerAmount);
            }
        }

        // Update player light position
        if (this.playerLight && G.player) {
            const playerLight = this.lights.find(l => l.id === this.playerLight);
            if (playerLight) {
                playerLight.x = G.player.x;
                playerLight.y = G.player.y;
            }
        }
    },

    render: function(ctx, camera) {
        if (!this.darkCtx) return;

        const bounds = camera.getViewBounds();

        // Fill dark overlay with near-black
        this.darkCtx.fillStyle = 'rgba(0, 0, 0, 0.85)';
        this.darkCtx.fillRect(0, 0, this.darkOverlay.width, this.darkOverlay.height);

        // Apply floor theme ambient tint
        const theme = getFloorTheme(G.currentFloor);
        if (theme.ambient) {
            this.darkCtx.fillStyle = theme.ambient;
            this.darkCtx.globalAlpha = 0.1;
            this.darkCtx.fillRect(0, 0, this.darkOverlay.width, this.darkOverlay.height);
            this.darkCtx.globalAlpha = 1;
        }

        // Cut out holes for lights using destination-out composite
        this.darkCtx.globalCompositeOperation = 'destination-out';

        for (let i = 0; i < this.lights.length; i++) {
            const light = this.lights[i];

            // Skip lights outside viewport
            if (light.x < bounds.left - light.radius * 2 ||
                light.x > bounds.right + light.radius * 2 ||
                light.y < bounds.top - light.radius * 2 ||
                light.y > bounds.bottom + light.radius * 2) {
                continue;
            }

            // Draw radial gradient hole
            const grad = this.darkCtx.createRadialGradient(
                light.x, light.y, 0,
                light.x, light.y, light.radius * TILE_SIZE
            );

            const alpha = light.intensity;
            grad.addColorStop(0, 'rgba(255, 255, 255, ' + alpha + ')');
            grad.addColorStop(0.6, 'rgba(255, 255, 255, ' + (alpha * 0.5) + ')');
            grad.addColorStop(1, 'rgba(255, 255, 255, 0)');

            this.darkCtx.fillStyle = grad;
            this.darkCtx.fillRect(
                light.x - light.radius * TILE_SIZE,
                light.y - light.radius * TILE_SIZE,
                light.radius * TILE_SIZE * 2,
                light.radius * TILE_SIZE * 2
            );
        }

        // Reset composite operation
        this.darkCtx.globalCompositeOperation = 'source-over';

        // Draw colored light glows on top
        for (let i = 0; i < this.lights.length; i++) {
            const light = this.lights[i];

            if (light.color === '#ffffff') continue; // Skip white lights

            // Skip lights outside viewport
            if (light.x < bounds.left - light.radius * 2 ||
                light.x > bounds.right + light.radius * 2 ||
                light.y < bounds.top - light.radius * 2 ||
                light.y > bounds.bottom + light.radius * 2) {
                continue;
            }

            // Draw colored glow
            const grad = this.darkCtx.createRadialGradient(
                light.x, light.y, 0,
                light.x, light.y, light.radius * TILE_SIZE
            );

            const rgb = this.hexToRgb(light.color);
            const alpha = light.intensity * 0.3;

            grad.addColorStop(0, 'rgba(' + rgb.r + ',' + rgb.g + ',' + rgb.b + ',' + alpha + ')');
            grad.addColorStop(0.6, 'rgba(' + rgb.r + ',' + rgb.g + ',' + rgb.b + ',' + (alpha * 0.5) + ')');
            grad.addColorStop(1, 'rgba(' + rgb.r + ',' + rgb.g + ',' + rgb.b + ', 0)');

            this.darkCtx.fillStyle = grad;
            this.darkCtx.fillRect(
                light.x - light.radius * TILE_SIZE,
                light.y - light.radius * TILE_SIZE,
                light.radius * TILE_SIZE * 2,
                light.radius * TILE_SIZE * 2
            );
        }

        // Draw dark overlay to main canvas
        ctx.drawImage(this.darkOverlay, 0, 0);
    },

    createTorchLight: function(x, y) {
        // Wall torch preset
        return this.addLight(x, y, 4, '#ff8800', 0.9, true);
    },

    createCampfireLight: function(x, y) {
        // Campfire preset (larger, warmer)
        return this.addLight(x, y, 6, '#ffaa00', 1.0, true);
    },

    createMagicLight: function(x, y, element) {
        // Colored magic light based on element
        let color = '#ffffff';
        let radius = 5;

        switch(element) {
            case 'ice':
            case 'frost':
                color = '#88ccff';
                break;
            case 'poison':
            case 'toxic':
                color = '#88ff88';
                break;
            case 'void':
            case 'shadow':
                color = '#aa88ff';
                break;
            case 'fire':
            case 'lava':
                color = '#ff4400';
                radius = 6;
                break;
            case 'lightning':
                color = '#ffff00';
                break;
        }

        return this.addLight(x, y, radius, color, 0.8, true);
    },

    createPlayerLight: function() {
        // Dim light that follows player
        if (G.player) {
            this.playerLight = this.addLight(
                G.player.x,
                G.player.y,
                3,
                '#ffffff',
                0.5,
                false
            );
            return this.playerLight;
        }
        return null;
    },

    clear: function() {
        this.lights = [];
        this.nextId = 0;
        this.playerLight = null;
    },

    hexToRgb: function(hex) {
        const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
        return result ? {
            r: parseInt(result[1], 16),
            g: parseInt(result[2], 16),
            b: parseInt(result[3], 16)
        } : {r: 255, g: 255, b: 255};
    }
};
