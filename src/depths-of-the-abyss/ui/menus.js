// menus.js
// Pause menu, inventory screen, skill tree, crafting UI

const Menus = {
  pauseIndex: 0,
  invCursor: { x: 0, y: 0 },
  invTab: 0, // 0=items, 1=equipment, 2=stats
  skillCursor: { tree: 0, tier: 0, slot: 0 },
  craftCursor: 0,
  tooltipItem: null,
  selectedStat: 0,
  craftRecipes: [],
  scrollOffset: 0,

  init() {
    this.pauseIndex = 0;
    this.invCursor = { x: 0, y: 0 };
    this.invTab = 0;
    this.skillCursor = { tree: 0, tier: 0, slot: 0 };
    this.craftCursor = 0;
    this.tooltipItem = null;
    this.selectedStat = 0;
    this.craftRecipes = [];
    this.scrollOffset = 0;
  },

  update(dt) {
    if (G.gameState === STATE.PAUSED) {
      this.updatePause();
    } else if (G.gameState === STATE.INVENTORY) {
      this.updateInventory();
    } else if (G.gameState === STATE.SKILL_TREE) {
      this.updateSkillTree();
    } else if (G.gameState === STATE.CRAFTING) {
      this.updateCrafting();
    }
  },

  togglePause() {
    if (G.gameState === STATE.PLAYING) {
      G.gameState = STATE.PAUSED;
      G.paused = true;
      SFX.playSound('menu_select');
    } else if (G.gameState === STATE.PAUSED) {
      G.gameState = STATE.PLAYING;
      G.paused = false;
      SFX.playSound('menu_select');
    }
  },

  openInventory() {
    G.gameState = STATE.INVENTORY;
    this.invTab = 0;
    this.invCursor = { x: 0, y: 0 };
    SFX.playSound('menu_select');
  },

  openSkillTree() {
    G.gameState = STATE.SKILL_TREE;
    this.skillCursor = { tree: 0, tier: 0, slot: 0 };
    SFX.playSound('menu_select');
  },

  openCrafting() {
    G.gameState = STATE.CRAFTING;
    this.craftCursor = 0;
    this.craftRecipes = Crafting.getAvailableRecipes();
    SFX.playSound('menu_select');
  },

  updatePause() {
    const menuItems = ['Resume', 'Save Game', 'Settings', 'Quit to Title'];

    if (Input.justPressed('ArrowDown') || Input.justPressed('KeyS')) {
      this.pauseIndex = (this.pauseIndex + 1) % menuItems.length;
      SFX.playSound('menu_hover');
    }
    if (Input.justPressed('ArrowUp') || Input.justPressed('KeyW')) {
      this.pauseIndex = (this.pauseIndex - 1 + menuItems.length) % menuItems.length;
      SFX.playSound('menu_hover');
    }

    if (Input.justPressed('Enter') || Input.justPressed('Space')) {
      SFX.playSound('menu_select');
      if (this.pauseIndex === 0) {
        this.togglePause();
      } else if (this.pauseIndex === 1) {
        Save.saveGame();
        HUD.addFloatingText(G.player.x, G.player.y - 50, 'Game Saved!', '#00ff00', 24);
      } else if (this.pauseIndex === 2) {
        // Settings (placeholder)
      } else if (this.pauseIndex === 3) {
        G.gameState = STATE.TITLE;
        TitleScreen.init();
      }
    }

    if (Input.justPressed('Escape') || Input.justPressed('KeyP')) {
      this.togglePause();
    }
  },

  updateInventory() {
    if (Input.justPressed('Escape') || Input.justPressed('KeyI')) {
      G.gameState = STATE.PLAYING;
      SFX.playSound('menu_select');
      return;
    }

    // Tab switching
    if (Input.justPressed('Tab')) {
      this.invTab = (this.invTab + 1) % 3;
      SFX.playSound('menu_hover');
    }

    if (this.invTab === 0) {
      // Items tab - grid navigation
      if (Input.justPressed('ArrowRight') || Input.justPressed('KeyD')) {
        this.invCursor.x = Math.min(this.invCursor.x + 1, 4);
        SFX.playSound('menu_hover');
      }
      if (Input.justPressed('ArrowLeft') || Input.justPressed('KeyA')) {
        this.invCursor.x = Math.max(this.invCursor.x - 1, 0);
        SFX.playSound('menu_hover');
      }
      if (Input.justPressed('ArrowDown') || Input.justPressed('KeyS')) {
        this.invCursor.y = Math.min(this.invCursor.y + 1, 3);
        SFX.playSound('menu_hover');
      }
      if (Input.justPressed('ArrowUp') || Input.justPressed('KeyW')) {
        this.invCursor.y = Math.max(this.invCursor.y - 1, 0);
        SFX.playSound('menu_hover');
      }

      const idx = this.invCursor.y * 5 + this.invCursor.x;
      const item = G.player.inventory[idx];
      this.tooltipItem = item || null;

      if (Input.justPressed('KeyE') && item) {
        Inventory.equipItem(idx);
      }
      if (Input.justPressed('KeyU') && item) {
        Inventory.useItem(idx);
      }
      if (Input.justPressed('KeyD') && item) {
        Inventory.dropItem(idx);
      }
    } else if (this.invTab === 2) {
      // Stats tab
      const stats = ['str', 'dex', 'vit', 'int'];
      if (Input.justPressed('ArrowDown') || Input.justPressed('KeyS')) {
        this.selectedStat = (this.selectedStat + 1) % stats.length;
        SFX.playSound('menu_hover');
      }
      if (Input.justPressed('ArrowUp') || Input.justPressed('KeyW')) {
        this.selectedStat = (this.selectedStat - 1 + stats.length) % stats.length;
        SFX.playSound('menu_hover');
      }
      if (Input.justPressed('Enter') || Input.justPressed('Space')) {
        if (G.player.statPoints > 0) {
          Progression.allocateStat(stats[this.selectedStat]);
        }
      }
    }
  },

  updateSkillTree() {
    if (Input.justPressed('Escape') || Input.justPressed('KeyK')) {
      G.gameState = STATE.PLAYING;
      SFX.playSound('menu_select');
      return;
    }

    // Navigate trees (left/right)
    if (Input.justPressed('ArrowRight') || Input.justPressed('KeyD')) {
      this.skillCursor.tree = (this.skillCursor.tree + 1) % 3;
      SFX.playSound('menu_hover');
    }
    if (Input.justPressed('ArrowLeft') || Input.justPressed('KeyA')) {
      this.skillCursor.tree = (this.skillCursor.tree - 1 + 3) % 3;
      SFX.playSound('menu_hover');
    }

    // Navigate tiers (up/down)
    if (Input.justPressed('ArrowDown') || Input.justPressed('KeyS')) {
      this.skillCursor.tier = Math.min(this.skillCursor.tier + 1, 2);
      SFX.playSound('menu_hover');
    }
    if (Input.justPressed('ArrowUp') || Input.justPressed('KeyW')) {
      this.skillCursor.tier = Math.max(this.skillCursor.tier - 1, 0);
      SFX.playSound('menu_hover');
    }

    // Navigate slots within tier
    if (Input.justPressed('Tab')) {
      this.skillCursor.slot = (this.skillCursor.slot + 1) % 3;
      SFX.playSound('menu_hover');
    }

    // Unlock ability
    if (Input.justPressed('Enter') || Input.justPressed('Space')) {
      const trees = ['warrior', 'mage', 'rogue'];
      const treeName = trees[this.skillCursor.tree];
      const tier = this.skillCursor.tier;
      const slot = this.skillCursor.slot;
      const abilityId = SKILL_TREES[treeName][tier][slot];

      if (canUnlockAbility(abilityId)) {
        Progression.unlockAbility(abilityId);
      }
    }

    // Equip ability
    if (Input.justPressed('KeyE')) {
      const trees = ['warrior', 'mage', 'rogue'];
      const treeName = trees[this.skillCursor.tree];
      const tier = this.skillCursor.tier;
      const slot = this.skillCursor.slot;
      const abilityId = SKILL_TREES[treeName][tier][slot];

      if (G.player.unlockedAbilities.includes(abilityId)) {
        // Find first empty hotbar slot
        for (let i = 0; i < 4; i++) {
          if (!G.player.equippedAbilities[i]) {
            Progression.equipAbility(abilityId, i);
            break;
          }
        }
      }
    }
  },

  updateCrafting() {
    if (Input.justPressed('Escape') || Input.justPressed('KeyC')) {
      G.gameState = STATE.PLAYING;
      SFX.playSound('menu_select');
      return;
    }

    if (Input.justPressed('ArrowDown') || Input.justPressed('KeyS')) {
      this.craftCursor = Math.min(this.craftCursor + 1, this.craftRecipes.length - 1);
      SFX.playSound('menu_hover');
    }
    if (Input.justPressed('ArrowUp') || Input.justPressed('KeyW')) {
      this.craftCursor = Math.max(this.craftCursor - 1, 0);
      SFX.playSound('menu_hover');
    }

    if (Input.justPressed('Enter') || Input.justPressed('Space')) {
      const recipe = this.craftRecipes[this.craftCursor];
      if (recipe && Crafting.canCraft(recipe.id)) {
        Crafting.craft(recipe.id);
        this.craftRecipes = Crafting.getAvailableRecipes();
      }
    }
  },

  renderPause(ctx) {
    const w = G.canvas.width;
    const h = G.canvas.height;

    // Dark backdrop
    ctx.fillStyle = 'rgba(0, 0, 0, 0.75)';
    ctx.fillRect(0, 0, w, h);

    // PAUSED header
    ctx.font = 'bold 48px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = '#ffcc00';
    ctx.shadowBlur = 15;
    ctx.shadowColor = '#ffcc00';
    ctx.fillText('PAUSED', w / 2, 100);
    ctx.shadowBlur = 0;

    // Menu items
    const menuItems = ['Resume', 'Save Game', 'Settings', 'Quit to Title'];
    const startY = h / 2 - 50;
    const itemHeight = 50;

    ctx.font = 'bold 28px sans-serif';
    for (let i = 0; i < menuItems.length; i++) {
      const y = startY + i * itemHeight;
      const isSelected = (i === this.pauseIndex);

      if (isSelected) {
        ctx.fillStyle = '#ffcc00';
        ctx.fillText('>', w / 2 - 120, y);
      }

      ctx.fillStyle = isSelected ? '#ffffff' : '#888888';
      ctx.fillText(menuItems[i], w / 2, y);
    }
  },

  renderInventory(ctx) {
    const w = G.canvas.width;
    const h = G.canvas.height;

    // Dark backdrop
    ctx.fillStyle = 'rgba(0, 0, 0, 0.85)';
    ctx.fillRect(0, 0, w, h);

    // Header
    ctx.font = 'bold 32px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillStyle = '#ffcc00';
    ctx.fillText('INVENTORY', w / 2, 40);

    // Tabs
    const tabs = ['Items', 'Equipment', 'Stats'];
    const tabWidth = 120;
    const tabY = 80;
    const tabStartX = w / 2 - (tabs.length * tabWidth) / 2;

    ctx.font = 'bold 20px sans-serif';
    for (let i = 0; i < tabs.length; i++) {
      const tabX = tabStartX + i * tabWidth;
      const isSelected = (i === this.invTab);

      ctx.fillStyle = isSelected ? 'rgba(80, 80, 80, 0.9)' : 'rgba(40, 40, 40, 0.7)';
      ctx.fillRect(tabX, tabY, tabWidth - 10, 40);

      ctx.fillStyle = isSelected ? '#ffffff' : '#888888';
      ctx.textAlign = 'center';
      ctx.fillText(tabs[i], tabX + tabWidth / 2 - 5, tabY + 25);
    }

    if (this.invTab === 0) {
      this.renderItemsTab(ctx);
    } else if (this.invTab === 1) {
      this.renderEquipmentTab(ctx);
    } else if (this.invTab === 2) {
      this.renderStatsTab(ctx);
    }
  },

  renderItemsTab(ctx) {
    const w = G.canvas.width;
    const gridX = 50;
    const gridY = 150;
    const slotSize = 60;
    const spacing = 10;

    // Grid
    for (let y = 0; y < 4; y++) {
      for (let x = 0; x < 5; x++) {
        const idx = y * 5 + x;
        const sx = gridX + x * (slotSize + spacing);
        const sy = gridY + y * (slotSize + spacing);
        const isSelected = (this.invCursor.x === x && this.invCursor.y === y);

        const item = G.player.inventory[idx];

        // Slot background
        ctx.fillStyle = 'rgba(40, 40, 40, 0.8)';
        ctx.fillRect(sx, sy, slotSize, slotSize);

        if (item) {
          // Item icon
          const rarityColor = RARITY_COLORS[item.rarity] || '#888888';
          ctx.fillStyle = rarityColor;
          ctx.fillRect(sx + 10, sy + 10, slotSize - 20, slotSize - 20);

          // Type indicator
          ctx.font = 'bold 16px sans-serif';
          ctx.fillStyle = '#ffffff';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(item.type[0].toUpperCase(), sx + slotSize / 2, sy + slotSize / 2);

          // Rarity border
          ctx.strokeStyle = rarityColor;
          ctx.lineWidth = 2;
          ctx.strokeRect(sx, sy, slotSize, slotSize);
        } else {
          ctx.strokeStyle = '#444444';
          ctx.lineWidth = 1;
          ctx.strokeRect(sx, sy, slotSize, slotSize);
        }

        // Selection border
        if (isSelected) {
          ctx.strokeStyle = '#ffcc00';
          ctx.lineWidth = 3;
          ctx.strokeRect(sx - 2, sy - 2, slotSize + 4, slotSize + 4);
        }
      }
    }

    // Item details panel
    if (this.tooltipItem) {
      this.renderItemDetails(ctx, this.tooltipItem, w - 350, gridY);
    }

    // Instructions
    ctx.font = '16px sans-serif';
    ctx.fillStyle = '#cccccc';
    ctx.textAlign = 'left';
    ctx.fillText('[E] Equip  [U] Use  [D] Drop', gridX, gridY + 4 * (slotSize + spacing) + 30);
  },

  renderEquipmentTab(ctx) {
    const w = G.canvas.width;
    const h = G.canvas.height;

    ctx.font = '20px sans-serif';
    ctx.fillStyle = '#ffffff';
    ctx.textAlign = 'center';
    ctx.fillText('Equipment slots coming soon...', w / 2, h / 2);
  },

  renderStatsTab(ctx) {
    const w = G.canvas.width;
    const startY = 150;

    const stats = [
      { name: 'Strength', key: 'str', value: G.player.stats.str },
      { name: 'Dexterity', key: 'dex', value: G.player.stats.dex },
      { name: 'Vitality', key: 'vit', value: G.player.stats.vit },
      { name: 'Intelligence', key: 'int', value: G.player.stats.int }
    ];

    ctx.font = 'bold 24px sans-serif';
    ctx.fillStyle = '#ffcc00';
    ctx.textAlign = 'center';
    ctx.fillText(`Stat Points Available: ${G.player.statPoints}`, w / 2, startY - 30);

    ctx.font = '22px sans-serif';
    for (let i = 0; i < stats.length; i++) {
      const y = startY + i * 50;
      const isSelected = (i === this.selectedStat);

      ctx.fillStyle = isSelected ? '#ffffff' : '#888888';
      ctx.textAlign = 'left';
      ctx.fillText(`${stats[i].name}: ${stats[i].value}`, w / 2 - 150, y);

      if (isSelected && G.player.statPoints > 0) {
        ctx.fillStyle = '#ffcc00';
        ctx.fillText('[+]', w / 2 + 80, y);
      }
    }

    ctx.font = '16px sans-serif';
    ctx.fillStyle = '#cccccc';
    ctx.textAlign = 'center';
    ctx.fillText('Press ENTER to allocate points', w / 2, startY + stats.length * 50 + 40);
  },

  renderItemDetails(ctx, item, x, y) {
    const panelWidth = 300;
    const panelHeight = 300;

    // Panel background
    ctx.fillStyle = 'rgba(40, 40, 40, 0.95)';
    ctx.fillRect(x, y, panelWidth, panelHeight);

    const rarityColor = RARITY_COLORS[item.rarity] || '#888888';
    ctx.strokeStyle = rarityColor;
    ctx.lineWidth = 2;
    ctx.strokeRect(x, y, panelWidth, panelHeight);

    // Item name
    ctx.font = 'bold 22px sans-serif';
    ctx.fillStyle = rarityColor;
    ctx.textAlign = 'left';
    ctx.fillText(item.name, x + 10, y + 30);

    // Type and rarity
    ctx.font = '16px sans-serif';
    ctx.fillStyle = '#cccccc';
    ctx.fillText(`${item.type} - ${item.rarity}`, x + 10, y + 55);

    // Stats
    let detailY = y + 85;
    ctx.font = '18px sans-serif';

    if (item.damage) {
      ctx.fillStyle = '#ff6666';
      ctx.fillText(`Damage: +${item.damage}`, x + 10, detailY);
      detailY += 25;
    }
    if (item.defense) {
      ctx.fillStyle = '#6666ff';
      ctx.fillText(`Defense: +${item.defense}`, x + 10, detailY);
      detailY += 25;
    }
    if (item.hp) {
      ctx.fillStyle = '#66ff66';
      ctx.fillText(`HP: +${item.hp}`, x + 10, detailY);
      detailY += 25;
    }

    // Description
    ctx.font = '14px sans-serif';
    ctx.fillStyle = '#aaaaaa';
    const desc = item.description || 'A mysterious item.';
    const lines = this.wrapText(ctx, desc, panelWidth - 20);
    for (let line of lines) {
      ctx.fillText(line, x + 10, detailY);
      detailY += 20;
    }
  },

  renderSkillTree(ctx) {
    const w = G.canvas.width;
    const h = G.canvas.height;

    // Dark backdrop
    ctx.fillStyle = 'rgba(0, 0, 0, 0.85)';
    ctx.fillRect(0, 0, w, h);

    // Header
    ctx.font = 'bold 32px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillStyle = '#ffcc00';
    ctx.fillText('SKILL TREE', w / 2, 40);

    ctx.font = '18px sans-serif';
    ctx.fillText(`Skill Points: ${G.player.skillPoints}`, w / 2, 75);

    const treeNames = ['Warrior', 'Mage', 'Rogue'];
    const treeColors = ['#ff6666', '#6666ff', '#66ff66'];
    const treeData = ['warrior', 'mage', 'rogue'];

    const treeWidth = 250;
    const startX = (w - 3 * treeWidth) / 2;
    const startY = 120;

    for (let t = 0; t < 3; t++) {
      const tx = startX + t * treeWidth;
      const isSelectedTree = (this.skillCursor.tree === t);

      // Tree header
      ctx.font = 'bold 24px sans-serif';
      ctx.fillStyle = isSelectedTree ? treeColors[t] : '#888888';
      ctx.textAlign = 'center';
      ctx.fillText(treeNames[t], tx + treeWidth / 2, startY);

      // Draw tiers
      for (let tier = 0; tier < 3; tier++) {
        const ty = startY + 50 + tier * 120;

        for (let slot = 0; slot < 3; slot++) {
          const nodeX = tx + 30 + slot * 75;
          const nodeY = ty;

          const abilityId = SKILL_TREES[treeData[t]][tier][slot];
          const abilityDef = ABILITY_DEFS[abilityId];
          const isUnlocked = G.player.unlockedAbilities.includes(abilityId);
          const canUnlock = canUnlockAbility(abilityId);
          const isSelected = (isSelectedTree && this.skillCursor.tier === tier && this.skillCursor.slot === slot);

          // Node circle
          ctx.beginPath();
          ctx.arc(nodeX, nodeY, 25, 0, Math.PI * 2);

          if (isUnlocked) {
            ctx.fillStyle = treeColors[t];
          } else if (canUnlock) {
            ctx.fillStyle = 'rgba(100, 100, 100, 0.7)';
            const pulse = Math.sin(G.time * 3) * 0.3 + 0.7;
            ctx.shadowBlur = 10 * pulse;
            ctx.shadowColor = treeColors[t];
          } else {
            ctx.fillStyle = 'rgba(60, 60, 60, 0.5)';
          }

          ctx.fill();

          if (isSelected) {
            ctx.strokeStyle = '#ffcc00';
            ctx.lineWidth = 3;
            ctx.stroke();
          }

          ctx.shadowBlur = 0;

          // Ability initial
          ctx.font = 'bold 16px sans-serif';
          ctx.fillStyle = '#ffffff';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(abilityDef.name[0], nodeX, nodeY);
        }
      }
    }

    // Selected ability details
    const trees = ['warrior', 'mage', 'rogue'];
    const treeName = trees[this.skillCursor.tree];
    const tier = this.skillCursor.tier;
    const slot = this.skillCursor.slot;
    const abilityId = SKILL_TREES[treeName][tier][slot];
    const abilityDef = ABILITY_DEFS[abilityId];

    if (abilityDef) {
      const detailY = startY + 400;
      ctx.font = 'bold 22px sans-serif';
      ctx.fillStyle = treeColors[this.skillCursor.tree];
      ctx.textAlign = 'center';
      ctx.fillText(abilityDef.name, w / 2, detailY);

      ctx.font = '16px sans-serif';
      ctx.fillStyle = '#cccccc';
      ctx.fillText(abilityDef.description, w / 2, detailY + 30);

      ctx.fillStyle = '#ffcc00';
      ctx.fillText(`Cost: ${abilityDef.cost || 1} SP | Cooldown: ${abilityDef.cooldown}s`, w / 2, detailY + 55);

      ctx.font = '14px sans-serif';
      ctx.fillText('[ENTER] Unlock  [E] Equip', w / 2, detailY + 85);
    }
  },

  renderCrafting(ctx) {
    const w = G.canvas.width;
    const h = G.canvas.height;

    // Dark backdrop
    ctx.fillStyle = 'rgba(0, 0, 0, 0.85)';
    ctx.fillRect(0, 0, w, h);

    // Header
    ctx.font = 'bold 32px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillStyle = '#ffcc00';
    ctx.fillText('CRAFTING', w / 2, 40);

    if (this.craftRecipes.length === 0) {
      ctx.font = '20px sans-serif';
      ctx.fillStyle = '#888888';
      ctx.fillText('No recipes available', w / 2, h / 2);
      return;
    }

    // Recipe list
    const listX = 50;
    const listY = 100;
    const itemHeight = 40;

    ctx.font = '18px sans-serif';
    ctx.textAlign = 'left';

    for (let i = 0; i < this.craftRecipes.length; i++) {
      const recipe = this.craftRecipes[i];
      const y = listY + i * itemHeight;
      const isSelected = (i === this.craftCursor);
      const canCraft = Crafting.canCraft(recipe.id);

      if (isSelected) {
        ctx.fillStyle = 'rgba(80, 80, 80, 0.8)';
        ctx.fillRect(listX - 10, y - 20, 400, itemHeight - 5);
      }

      ctx.fillStyle = canCraft ? '#ffffff' : '#888888';
      ctx.fillText(recipe.name, listX, y);

      if (!canCraft) {
        ctx.fillStyle = '#ff6666';
        ctx.fillText('[Missing materials]', listX + 250, y);
      }
    }

    // Recipe details
    if (this.craftRecipes[this.craftCursor]) {
      this.renderRecipeDetails(ctx, this.craftRecipes[this.craftCursor], w - 350, listY);
    }
  },

  renderRecipeDetails(ctx, recipe, x, y) {
    const panelWidth = 300;

    ctx.fillStyle = 'rgba(40, 40, 40, 0.95)';
    ctx.fillRect(x, y, panelWidth, 350);

    ctx.strokeStyle = '#ffcc00';
    ctx.lineWidth = 2;
    ctx.strokeRect(x, y, panelWidth, 350);

    ctx.font = 'bold 20px sans-serif';
    ctx.fillStyle = '#ffcc00';
    ctx.textAlign = 'left';
    ctx.fillText(recipe.name, x + 10, y + 30);

    ctx.font = '16px sans-serif';
    ctx.fillStyle = '#cccccc';
    ctx.fillText('Required Materials:', x + 10, y + 60);

    let detailY = y + 90;
    for (let mat of recipe.materials) {
      const has = Crafting.getMaterialCount(mat.id);
      const color = has >= mat.count ? '#66ff66' : '#ff6666';

      ctx.fillStyle = color;
      const materialName = mat.id.replace(/_/g, ' ');
      ctx.fillText(`${materialName}: ${has}/${mat.count}`, x + 20, detailY);
      detailY += 25;
    }

    ctx.font = '14px sans-serif';
    ctx.fillStyle = '#ffcc00';
    ctx.fillText('[ENTER] to craft', x + 10, y + 320);
  },

  renderTooltip(ctx, item, x, y) {
    const boxWidth = 250;
    const boxHeight = 150;

    ctx.fillStyle = 'rgba(20, 20, 20, 0.95)';
    ctx.fillRect(x, y, boxWidth, boxHeight);

    const rarityColor = RARITY_COLORS[item.rarity] || '#888888';
    ctx.strokeStyle = rarityColor;
    ctx.lineWidth = 2;
    ctx.strokeRect(x, y, boxWidth, boxHeight);

    ctx.font = 'bold 18px sans-serif';
    ctx.fillStyle = rarityColor;
    ctx.textAlign = 'left';
    ctx.fillText(item.name, x + 10, y + 25);

    ctx.font = '14px sans-serif';
    ctx.fillStyle = '#aaaaaa';
    ctx.fillText(`${item.type} - ${item.rarity}`, x + 10, y + 45);
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
