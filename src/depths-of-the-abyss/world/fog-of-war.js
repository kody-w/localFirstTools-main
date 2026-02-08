// fog-of-war.js — Raycasting-based visibility system for Depths of the Abyss
// Depends on: G, TILE_SIZE from constants.js
// Depends on: Util from utils.js
// Depends on: TileMap, TILE_DOOR from world/tilemap.js

const Fog = {
    visible: [],
    revealed: [],
    width: 0,
    height: 0,
    offscreenCanvas: null,
    offscreenCtx: null,

    init: function(w, h) {
        this.width = w;
        this.height = h;
        this.visible = [];
        this.revealed = [];

        for (let y = 0; y < h; y++) {
            this.visible[y] = [];
            this.revealed[y] = [];
            for (let x = 0; x < w; x++) {
                this.visible[y][x] = false;
                this.revealed[y][x] = false;
            }
        }

        // Create offscreen canvas for fog rendering performance
        this.offscreenCanvas = document.createElement('canvas');
        this.offscreenCanvas.width = w * TILE_SIZE;
        this.offscreenCanvas.height = h * TILE_SIZE;
        this.offscreenCtx = this.offscreenCanvas.getContext('2d');
    },

    update: function(px, py, sightRadius) {
        // Clear current visibility
        for (let y = 0; y < this.height; y++) {
            for (let x = 0; x < this.width; x++) {
                this.visible[y][x] = false;
            }
        }

        // Convert player position to tile coords
        const playerTile = TileMap.pixelToTile(px, py);

        // Adjust sight radius based on area/effects
        let radius = sightRadius || 8;

        // Check for void area (reduced sight)
        const theme = getFloorTheme(G.currentFloor);
        if (theme.name === 'The Void') {
            radius = 6;
        }

        // Check for torch item (increased sight)
        if (G.player && G.player.hasTorch) {
            radius = 10;
        }

        // Raycasting: cast rays in all directions
        const angleStep = 1; // 1 degree per ray = 360 rays
        const totalAngles = 360 / angleStep;

        for (let i = 0; i < totalAngles; i++) {
            const angle = (i * angleStep * Math.PI) / 180;
            this.castRay(playerTile.x, playerTile.y, angle, radius);
        }

        // Always mark player tile as visible
        if (playerTile.x >= 0 && playerTile.x < this.width &&
            playerTile.y >= 0 && playerTile.y < this.height) {
            this.visible[playerTile.y][playerTile.x] = true;
            this.revealed[playerTile.y][playerTile.x] = true;
        }
    },

    castRay: function(startX, startY, angle, maxDist) {
        // Bresenham-style raycasting
        const dx = Math.cos(angle);
        const dy = Math.sin(angle);

        for (let d = 0; d <= maxDist; d += 0.5) {
            const x = Math.floor(startX + dx * d);
            const y = Math.floor(startY + dy * d);

            // Out of bounds check
            if (x < 0 || x >= this.width || y < 0 || y >= this.height) break;

            // Mark as visible and revealed
            this.visible[y][x] = true;
            this.revealed[y][x] = true;

            // Stop at solid tiles (walls block vision)
            if (TileMap.isSolid(x, y)) break;

            // Doors block vision unless player is adjacent
            if (TileMap.getTile(x, y) === TILE_DOOR) {
                const distToPlayer = Util.dist(x, y, startX, startY);
                if (distToPlayer > 1.5) break;
            }
        }
    },

    isVisible: function(tx, ty) {
        if (tx < 0 || tx >= this.width || ty < 0 || ty >= this.height) return false;
        return this.visible[ty][tx];
    },

    isRevealed: function(tx, ty) {
        if (tx < 0 || tx >= this.width || ty < 0 || ty >= this.height) return false;
        return this.revealed[ty][tx];
    },

    render: function(ctx, camera) {
        if (!this.offscreenCtx) return;

        const bounds = camera.getViewBounds();
        const startX = Math.max(0, Math.floor(bounds.left / TILE_SIZE));
        const startY = Math.max(0, Math.floor(bounds.top / TILE_SIZE));
        const endX = Math.min(this.width - 1, Math.ceil(bounds.right / TILE_SIZE));
        const endY = Math.min(this.height - 1, Math.ceil(bounds.bottom / TILE_SIZE));

        // Clear offscreen canvas
        this.offscreenCtx.clearRect(
            startX * TILE_SIZE,
            startY * TILE_SIZE,
            (endX - startX + 1) * TILE_SIZE,
            (endY - startY + 1) * TILE_SIZE
        );

        // Render fog to offscreen canvas
        for (let y = startY; y <= endY; y++) {
            for (let x = startX; x <= endX; x++) {
                const px = x * TILE_SIZE;
                const py = y * TILE_SIZE;

                if (!this.revealed[y][x]) {
                    // Unrevealed: fully black
                    this.offscreenCtx.fillStyle = 'rgba(0, 0, 0, 1)';
                    this.offscreenCtx.fillRect(px, py, TILE_SIZE, TILE_SIZE);
                } else if (!this.visible[y][x]) {
                    // Revealed but not visible: dark overlay
                    this.offscreenCtx.fillStyle = 'rgba(0, 0, 0, 0.7)';
                    this.offscreenCtx.fillRect(px, py, TILE_SIZE, TILE_SIZE);
                } else {
                    // Visible: apply edge smoothing with gradient
                    this.renderFogEdges(x, y, px, py);
                }
            }
        }

        // Draw offscreen canvas to main canvas
        ctx.drawImage(
            this.offscreenCanvas,
            startX * TILE_SIZE,
            startY * TILE_SIZE,
            (endX - startX + 1) * TILE_SIZE,
            (endY - startY + 1) * TILE_SIZE,
            startX * TILE_SIZE,
            startY * TILE_SIZE,
            (endX - startX + 1) * TILE_SIZE,
            (endY - startY + 1) * TILE_SIZE
        );
    },

    renderFogEdges: function(tx, ty, px, py) {
        // Smooth edges between visible and fog using alpha gradients
        const neighbors = [
            this.isVisible(tx - 1, ty),     // left
            this.isVisible(tx + 1, ty),     // right
            this.isVisible(tx, ty - 1),     // up
            this.isVisible(tx, ty + 1),     // down
            this.isVisible(tx - 1, ty - 1), // top-left
            this.isVisible(tx + 1, ty - 1), // top-right
            this.isVisible(tx - 1, ty + 1), // bottom-left
            this.isVisible(tx + 1, ty + 1)  // bottom-right
        ];

        // If all neighbors are visible, no edge
        const allVisible = neighbors.every(n => n);
        if (allVisible) return;

        // If any neighbor is not visible, draw gradient edge
        const anyHidden = neighbors.some(n => !n);
        if (!anyHidden) return;

        // Draw gradients at edges
        const edgeSize = TILE_SIZE / 4;

        // Left edge
        if (!neighbors[0]) {
            const grad = this.offscreenCtx.createLinearGradient(px, py, px + edgeSize, py);
            grad.addColorStop(0, 'rgba(0, 0, 0, 0.3)');
            grad.addColorStop(1, 'rgba(0, 0, 0, 0)');
            this.offscreenCtx.fillStyle = grad;
            this.offscreenCtx.fillRect(px, py, edgeSize, TILE_SIZE);
        }

        // Right edge
        if (!neighbors[1]) {
            const grad = this.offscreenCtx.createLinearGradient(
                px + TILE_SIZE - edgeSize, py,
                px + TILE_SIZE, py
            );
            grad.addColorStop(0, 'rgba(0, 0, 0, 0)');
            grad.addColorStop(1, 'rgba(0, 0, 0, 0.3)');
            this.offscreenCtx.fillStyle = grad;
            this.offscreenCtx.fillRect(px + TILE_SIZE - edgeSize, py, edgeSize, TILE_SIZE);
        }

        // Top edge
        if (!neighbors[2]) {
            const grad = this.offscreenCtx.createLinearGradient(px, py, px, py + edgeSize);
            grad.addColorStop(0, 'rgba(0, 0, 0, 0.3)');
            grad.addColorStop(1, 'rgba(0, 0, 0, 0)');
            this.offscreenCtx.fillStyle = grad;
            this.offscreenCtx.fillRect(px, py, TILE_SIZE, edgeSize);
        }

        // Bottom edge
        if (!neighbors[3]) {
            const grad = this.offscreenCtx.createLinearGradient(
                px, py + TILE_SIZE - edgeSize,
                px, py + TILE_SIZE
            );
            grad.addColorStop(0, 'rgba(0, 0, 0, 0)');
            grad.addColorStop(1, 'rgba(0, 0, 0, 0.3)');
            this.offscreenCtx.fillStyle = grad;
            this.offscreenCtx.fillRect(px, py + TILE_SIZE - edgeSize, TILE_SIZE, edgeSize);
        }
    },

    reset: function() {
        for (let y = 0; y < this.height; y++) {
            for (let x = 0; x < this.width; x++) {
                this.visible[y][x] = false;
                this.revealed[y][x] = false;
            }
        }
    }
};
