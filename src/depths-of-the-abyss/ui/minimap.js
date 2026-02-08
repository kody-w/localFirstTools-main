// minimap.js
// Corner minimap with fog of war

const Minimap = {
  visible: true,
  size: 160,
  scale: 4,
  canvas: null,
  ctx: null,
  needsRedraw: true,
  lastPlayerTile: { x: -1, y: -1 },

  init() {
    this.visible = true;
    this.size = 160;
    this.needsRedraw = true;
    this.lastPlayerTile = { x: -1, y: -1 };

    // Create offscreen canvas
    this.canvas = document.createElement('canvas');
    this.canvas.width = this.size;
    this.canvas.height = this.size;
    this.ctx = this.canvas.getContext('2d');
  },

  toggle() {
    this.visible = !this.visible;
    SFX.playSound('menu_select');
  },

  update() {
    if (!TileMap || !TileMap.tiles) return;

    // Check if player moved to new tile
    const playerTileX = Math.floor(G.player.x / TILE_SIZE);
    const playerTileY = Math.floor(G.player.y / TILE_SIZE);

    if (playerTileX !== this.lastPlayerTile.x || playerTileY !== this.lastPlayerTile.y) {
      this.needsRedraw = true;
      this.lastPlayerTile.x = playerTileX;
      this.lastPlayerTile.y = playerTileY;
    }

    // Redraw minimap if needed
    if (this.needsRedraw && this.visible) {
      this.redrawMinimap();
      this.needsRedraw = false;
    }
  },

  redrawMinimap() {
    if (!TileMap || !TileMap.tiles) return;

    const mapWidth = TileMap.width;
    const mapHeight = TileMap.height;

    // Calculate scale to fit entire map
    this.scale = Math.min(this.size / mapWidth, this.size / mapHeight);

    const ctx = this.ctx;
    ctx.clearRect(0, 0, this.size, this.size);

    // Dark background
    ctx.fillStyle = '#000000';
    ctx.fillRect(0, 0, this.size, this.size);

    // Draw tiles
    for (let y = 0; y < mapHeight; y++) {
      for (let x = 0; x < mapWidth; x++) {
        const tile = TileMap.tiles[y][x];
        const isRevealed = Fog.isRevealed(x, y);
        const isVisible = Fog.isVisible(x, y);

        if (!isRevealed) {
          // Hidden - stay black
          continue;
        }

        const px = x * this.scale;
        const py = y * this.scale;

        let color = '#000000';

        if (tile === 1) {
          // Wall
          color = isVisible ? '#666666' : '#333333';
        } else if (tile === 0) {
          // Floor
          color = isVisible ? '#444444' : '#222222';
        } else if (tile === 2) {
          // Door
          color = isVisible ? '#8b4513' : '#4a2511';
        } else if (tile === 3) {
          // Stairs
          color = isVisible ? '#ffffff' : '#888888';
        } else if (tile === 4) {
          // Campfire
          color = isVisible ? '#ff8800' : '#884400';
        } else if (tile === 5) {
          // Chest
          color = isVisible ? '#ffcc00' : '#886600';
        } else if (tile === 6) {
          // Boss gate
          color = isVisible ? '#ff0000' : '#880000';
        }

        ctx.fillStyle = color;
        ctx.fillRect(px, py, Math.ceil(this.scale), Math.ceil(this.scale));
      }
    }

    // Draw enemies (red dots)
    if (G.enemies) {
      for (let enemy of G.enemies) {
        const ex = Math.floor(enemy.x / TILE_SIZE);
        const ey = Math.floor(enemy.y / TILE_SIZE);

        if (Fog.isVisible(ex, ey)) {
          const px = ex * this.scale;
          const py = ey * this.scale;

          ctx.fillStyle = '#ff3333';
          ctx.fillRect(px, py, Math.max(2, this.scale), Math.max(2, this.scale));
        }
      }
    }

    // Draw boss (large red dot)
    if (G.boss && G.bossActive) {
      const bx = Math.floor(G.boss.x / TILE_SIZE);
      const by = Math.floor(G.boss.y / TILE_SIZE);

      if (Fog.isVisible(bx, by)) {
        const px = bx * this.scale;
        const py = by * this.scale;

        ctx.fillStyle = '#ff0000';
        ctx.fillRect(px - 1, py - 1, Math.max(4, this.scale * 2), Math.max(4, this.scale * 2));
      }
    }
  },

  render(ctx) {
    if (!this.visible || !TileMap || !TileMap.tiles) return;

    const w = G.canvas.width;
    const h = G.canvas.height;
    const margin = 10;
    const x = w - this.size - margin;
    const y = h - this.size - margin;

    // Semi-transparent background
    ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
    ctx.fillRect(x - 5, y - 5, this.size + 10, this.size + 10);

    // Draw minimap
    ctx.drawImage(this.canvas, x, y);

    // Border
    ctx.strokeStyle = '#666666';
    ctx.lineWidth = 2;
    ctx.strokeRect(x - 5, y - 5, this.size + 10, this.size + 10);

    // Player position (bright green blinking dot)
    const playerTileX = Math.floor(G.player.x / TILE_SIZE);
    const playerTileY = Math.floor(G.player.y / TILE_SIZE);

    const px = x + playerTileX * this.scale;
    const py = y + playerTileY * this.scale;

    const blink = Math.sin(G.time * 5) * 0.5 + 0.5;
    ctx.fillStyle = Util.rgba(0, 255, 0, blink);
    ctx.fillRect(px - 1, py - 1, 3, 3);

    // Viewport rectangle
    const zoom = Camera.zoom || 1.0;
    const viewWidthTiles = (G.canvas.width / zoom) / TILE_SIZE;
    const viewHeightTiles = (G.canvas.height / zoom) / TILE_SIZE;

    const viewX = x + (Camera.x / TILE_SIZE - viewWidthTiles / 2) * this.scale;
    const viewY = y + (Camera.y / TILE_SIZE - viewHeightTiles / 2) * this.scale;
    const viewW = viewWidthTiles * this.scale;
    const viewH = viewHeightTiles * this.scale;

    ctx.strokeStyle = 'rgba(255, 255, 255, 0.5)';
    ctx.lineWidth = 1;
    ctx.strokeRect(viewX, viewY, viewW, viewH);

    // Tab hint
    ctx.font = '12px sans-serif';
    ctx.fillStyle = '#888888';
    ctx.textAlign = 'right';
    ctx.textBaseline = 'top';
    ctx.fillText('[Tab] Toggle', w - margin - 5, y - 20);
  }
};
