'use strict';

// =============================================================================
// GAME-LOOP.JS - Main engine loop and state machine (MUST BE LOADED LAST)
// =============================================================================
// Depends on ALL other modules being loaded first.
// Initializes the game engine and runs the requestAnimationFrame loop.

const Engine = {
    canvas: null,
    ctx: null,
    lastTime: 0,
    running: false,
    fpsTimer: 0,
    fpsCount: 0,
    currentFPS: 0
};

// =============================================================================
// INITIALIZATION
// =============================================================================

Engine.init = function() {
    // Canvas setup
    Engine.canvas = document.getElementById('gameCanvas');
    Engine.ctx = Engine.canvas.getContext('2d');
    G.canvas = Engine.canvas;
    G.ctx = Engine.ctx;

    // Resize canvas to window
    Engine.resize();
    window.addEventListener('resize', Engine.resize);

    // Initialize all subsystems
    Input.init(Engine.canvas);
    SFX.init();
    FX.init();
    Fog.init(100, 80);
    Lighting.init(100 * TILE_SIZE, 80 * TILE_SIZE);
    Camera.init(Engine.canvas);
    Minimap.init();

    // Load settings and high scores
    const settings = Save.loadSettings();
    G.difficulty = settings.difficulty || 'Normal';
    const hs = Save.loadHighScore();
    G.highScore = hs.score || 0;
    G.deepestFloor = hs.deepestFloor || 1;

    // Initialize title screen
    TitleScreen.init();
    G.gameState = STATE.TITLE;

    // Resume audio on first user interaction
    const resumeAudio = function() {
        SFX.resume();
        document.removeEventListener('click', resumeAudio);
        document.removeEventListener('keydown', resumeAudio);
        document.removeEventListener('touchstart', resumeAudio);
    };
    document.addEventListener('click', resumeAudio);
    document.addEventListener('keydown', resumeAudio);
    document.addEventListener('touchstart', resumeAudio);

    // Start the loop
    Engine.running = true;
    Engine.lastTime = performance.now();
    requestAnimationFrame(Engine.loop);
};

// =============================================================================
// CANVAS RESIZE
// =============================================================================

Engine.resize = function() {
    Engine.canvas.width = window.innerWidth;
    Engine.canvas.height = window.innerHeight;
    if (Camera.init) {
        Camera.viewW = Engine.canvas.width;
        Camera.viewH = Engine.canvas.height;
    }
};

// =============================================================================
// MAIN LOOP
// =============================================================================

Engine.loop = function(timestamp) {
    if (!Engine.running) return;

    // Delta time (capped at 50ms to prevent spiral of death)
    const rawDt = (timestamp - Engine.lastTime) / 1000;
    const dt = Math.min(rawDt, 0.05);
    Engine.lastTime = timestamp;
    G.dt = dt;
    G.time += dt;
    G.frameCount++;

    // FPS counter
    Engine.fpsTimer += dt;
    Engine.fpsCount++;
    if (Engine.fpsTimer >= 1.0) {
        Engine.currentFPS = Engine.fpsCount;
        Engine.fpsCount = 0;
        Engine.fpsTimer = 0;
    }

    // Update
    Engine.update(dt);

    // Render
    Engine.render();

    // Clear per-frame input state
    Input.update();

    // Next frame
    requestAnimationFrame(Engine.loop);
};

// =============================================================================
// UPDATE STATE MACHINE
// =============================================================================

Engine.update = function(dt) {
    switch (G.gameState) {
        case STATE.TITLE:
            TitleScreen.update(dt);
            // Check if title screen started a new game
            if (G.gameState === STATE.PLAYING && !G.player) {
                Engine.startNewGame();
            }
            break;

        case STATE.PLAYING:
            Engine.updatePlaying(dt);
            break;

        case STATE.PAUSED:
            Menus.update(dt);
            break;

        case STATE.INVENTORY:
            Menus.update(dt);
            break;

        case STATE.SKILL_TREE:
            Menus.update(dt);
            break;

        case STATE.CRAFTING:
            Menus.update(dt);
            break;

        case STATE.DIALOGUE:
            Dialogue.update(dt);
            break;

        case STATE.DEATH:
            Engine.updateDeath(dt);
            break;

        case STATE.GAME_OVER:
            Engine.updateGameOver(dt);
            break;

        case STATE.VICTORY:
            Engine.updateVictory(dt);
            break;

        case STATE.TRANSITION:
            Transitions.update(dt);
            break;

        case STATE.BOSS_INTRO:
            Transitions.update(dt);
            break;
    }
};

// =============================================================================
// PLAYING STATE UPDATE
// =============================================================================

Engine.updatePlaying = function(dt) {
    // Track play time
    G.totalPlayTime += dt;

    // Handle pause toggle
    if (Input.justPressed('Escape') || Input.justPressed('p') || Input.justPressed('P')) {
        Menus.togglePause();
        return;
    }

    // Handle inventory toggle
    if (Input.justPressed('i') || Input.justPressed('I')) {
        Menus.openInventory();
        return;
    }

    // Handle skill tree toggle
    if (Input.justPressed('k') || Input.justPressed('K')) {
        Menus.openSkillTree();
        return;
    }

    // Handle crafting (only at campfire)
    if (Input.justPressed('c') || Input.justPressed('C')) {
        if (Engine.isNearCampfire()) {
            Menus.openCrafting();
            return;
        }
    }

    // Handle minimap toggle
    if (Input.justPressed('Tab')) {
        Minimap.toggle();
    }

    // Handle ability hotkeys (1-4)
    if (window.AbilitySystem && AbilitySystem.cast && G.player.equippedAbilities) {
        for (let i = 0; i < 4; i++) {
            if (Input.justPressed(String(i + 1))) {
                const abilityId = G.player.equippedAbilities[i];
                if (abilityId) {
                    AbilitySystem.cast(abilityId, G.player);
                }
            }
        }
    }

    // Handle attack
    if ((Input.justPressed(' ') || Input.justPressed('Space') || (Input.mouse && Input.mouse.justDown)) && window.Player && Player.attack) {
        Player.attack();
    }

    // Handle dodge roll
    if ((Input.justPressed('Shift') || Input.justPressed('ShiftLeft') || Input.justPressed('ShiftRight')) && window.Player && Player.dodge) {
        Player.dodge();
    }

    // Handle interact / parry
    if (Input.justPressed('e') || Input.justPressed('E')) {
        if (!Engine.tryInteract() && window.Player && Player.parry) {
            Player.parry();
        }
    }

    // Update game systems
    if (window.Player && Player.update) {
        Player.update(dt);
    }

    // Update all enemies
    if (G.enemies) {
        for (let i = G.enemies.length - 1; i >= 0; i--) {
            const enemy = G.enemies[i];
            if (enemy.hp <= 0) {
                G.enemies.splice(i, 1);
                continue;
            }
            if (enemy.isBoss && window.BossAI && BossAI.update) {
                BossAI.update(enemy, dt);
            } else if (window.EnemyAI && EnemyAI.update) {
                EnemyAI.update(enemy, dt);
            }
        }
    }

    // Update combat (collision detection, projectiles, damage)
    if (window.Combat && Combat.update) {
        Combat.update(dt);
    }

    // Update ability system (cooldowns, active effects)
    if (window.AbilitySystem && AbilitySystem.update) {
        AbilitySystem.update(dt);
    }

    // Update inventory (ground item pickups)
    Inventory.pickupNearby();

    // Update progression
    Progression.calculateScore();

    // Update fog of war
    if (G.player && TileMap && TileMap.width > 0) {
        const ptx = Math.floor(G.player.x / TILE_SIZE);
        const pty = Math.floor(G.player.y / TILE_SIZE);
        const sightRadius = G.currentFloor >= 21 ? 6 : (G.player.hasTorch ? 10 : 8);
        if (window.Fog && Fog.update) {
            Fog.update(ptx, pty, sightRadius);
        }
    }

    // Update lighting
    if (window.Lighting && Lighting.update) {
        Lighting.update(dt);
        if (G.player) {
            // Player light follows player
            Lighting.playerLight = { x: G.player.x, y: G.player.y, radius: 96, color: '#fff8e0', intensity: 0.6, flicker: true };
        }
    }

    // Update camera
    if (G.player) {
        Camera.follow(G.player, dt);
    }
    Camera.update(dt);

    // Update particles
    FX.update(dt);

    // Update HUD
    HUD.update(dt);

    // Update floating texts
    for (let i = G.floatingTexts.length - 1; i >= 0; i--) {
        const ft = G.floatingTexts[i];
        ft.life -= dt;
        ft.y -= 40 * dt; // float upward
        if (ft.life <= 0) {
            G.floatingTexts.splice(i, 1);
        }
    }

    // Combo timer decay
    if (G.combo > 0) {
        G.comboTimer -= dt;
        if (G.comboTimer <= 0) {
            G.combo = 0;
            G.comboTimer = 0;
        }
    }

    // Campfire proximity effects
    if (Engine.isNearCampfire()) {
        // Slow HP regen at campfire
        if (G.player.hp < G.player.maxHp) {
            G.player.hp = Math.min(G.player.maxHp, G.player.hp + 5 * dt);
        }
    }
};

// =============================================================================
// DEATH / GAME OVER / VICTORY UPDATES
// =============================================================================

Engine.updateDeath = function(dt) {
    // Wait for input to restart or quit
    if (Input.justPressed('Enter') || Input.justPressed('Return')) {
        // Try to load campfire save
        const campfire = Save.loadCampfire();
        if (campfire) {
            Engine.restoreFromCampfire(campfire);
        } else {
            // Full restart - new run
            Engine.startNewGame();
        }
    }
    if (Input.justPressed('Escape')) {
        G.gameState = STATE.TITLE;
        TitleScreen.init();
    }
    FX.update(dt);
};

Engine.updateGameOver = function(dt) {
    if (Input.justPressed('Enter') || Input.justPressed('Return')) {
        // Save high score, restart
        Save.saveHighScore(G.score, G.currentFloor);
        Save.resetGame();
        G.gameState = STATE.TITLE;
        TitleScreen.init();
    }
    FX.update(dt);
};

Engine.updateVictory = function(dt) {
    if (Input.justPressed('Enter') || Input.justPressed('Return')) {
        Save.saveHighScore(G.score, G.currentFloor);
        Save.resetGame();
        G.gameState = STATE.TITLE;
        TitleScreen.init();
    }
    FX.update(dt);
};

// =============================================================================
// RENDER
// =============================================================================

Engine.render = function() {
    const ctx = Engine.ctx;
    const w = Engine.canvas.width;
    const h = Engine.canvas.height;

    // Clear canvas
    ctx.fillStyle = CANVAS_BG;
    ctx.fillRect(0, 0, w, h);

    switch (G.gameState) {
        case STATE.TITLE:
            TitleScreen.render(ctx);
            break;

        case STATE.PLAYING:
        case STATE.PAUSED:
        case STATE.INVENTORY:
        case STATE.SKILL_TREE:
        case STATE.CRAFTING:
        case STATE.DIALOGUE:
            Engine.renderGameWorld(ctx);

            // Overlay menus
            if (G.gameState === STATE.PAUSED) Menus.renderPause(ctx);
            if (G.gameState === STATE.INVENTORY) Menus.renderInventory(ctx);
            if (G.gameState === STATE.SKILL_TREE) Menus.renderSkillTree(ctx);
            if (G.gameState === STATE.CRAFTING) Menus.renderCrafting(ctx);
            if (G.gameState === STATE.DIALOGUE) Dialogue.render(ctx);
            break;

        case STATE.DEATH:
            Engine.renderGameWorld(ctx);
            HUD.renderDeathOverlay(ctx);
            break;

        case STATE.GAME_OVER:
            Engine.renderGameWorld(ctx);
            HUD.renderGameOver(ctx);
            break;

        case STATE.VICTORY:
            Engine.renderGameWorld(ctx);
            HUD.renderVictory(ctx, Engine.currentEnding);
            break;

        case STATE.TRANSITION:
        case STATE.BOSS_INTRO:
            Engine.renderGameWorld(ctx);
            Transitions.render(ctx);
            break;
    }

    // FPS counter (debug)
    const settings = Save.loadSettings();
    if (settings.showFPS) {
        ctx.fillStyle = 'rgba(0,255,0,0.7)';
        ctx.font = '12px monospace';
        ctx.textAlign = 'left';
        ctx.fillText('FPS: ' + Engine.currentFPS, 5, h - 5);
    }
};

// =============================================================================
// WORLD RENDERING
// =============================================================================

Engine.renderGameWorld = function(ctx) {
    if (!G.player || !TileMap.width) return;

    ctx.save();

    // Apply camera transform
    Camera.applyTransform(ctx);

    // Render tilemap (floor and walls)
    if (window.TileMap && TileMap.render) {
        TileMap.render(ctx, Camera);
    }

    // Render tile decorations
    if (window.TileMap && TileMap.renderDecor) {
        TileMap.renderDecor(ctx, Camera);
    }

    // Render ground items
    if (window.Inventory && Inventory.renderGroundItems) {
        Inventory.renderGroundItems(ctx, Camera);
    }

    // Render enemies
    if (window.EnemyAI && EnemyAI.renderAll) {
        EnemyAI.renderAll(ctx, Camera);
    }

    // Render boss (if active)
    if (G.bossActive && window.BossAI && BossAI.render) {
        BossAI.render(G.bossActive, ctx, Camera);
    }

    // Render player
    if (window.Player && Player.render) {
        Player.render(ctx, Camera);
    }

    // Render weapon swings
    if (window.Weapons && Weapons.renderSwing) {
        Weapons.renderSwing(ctx, G.player, Camera);
    }

    // Render projectiles
    if (window.Combat && Combat.renderProjectiles) {
        Combat.renderProjectiles(ctx, Camera);
    }

    // Render ability effects
    if (window.AbilitySystem && AbilitySystem.renderEffects) {
        AbilitySystem.renderEffects(ctx, Camera);
    }

    // Render particles (world-space)
    if (window.FX && FX.render) {
        FX.render(ctx, Camera);
    }

    // Render fog of war
    if (window.Fog && Fog.render) {
        Fog.render(ctx, Camera);
    }

    // Render lighting overlay
    if (window.Lighting && Lighting.render) {
        Lighting.render(ctx, Camera);
    }

    ctx.restore();

    // Screen-space UI (after camera reset)
    HUD.render(ctx);

    // Minimap
    if (Minimap.visible) {
        Minimap.render(ctx);
    }
};

// =============================================================================
// GAME START / FLOOR GENERATION
// =============================================================================

Engine.startNewGame = function() {
    // Initialize player
    if (window.Player && Player.init) {
        Player.init();
    }

    G.gameState = STATE.PLAYING;
    G.currentFloor = 1;
    G.seed = Date.now();
    G.enemies = [];
    G.projectiles = [];
    G.items = [];
    G.particles = [];
    G.floatingTexts = [];
    G.bossActive = null;
    G.combo = 0;
    G.comboTimer = 0;
    G.score = 0;
    G.kills = 0;
    G.time = 0;
    G.totalPlayTime = 0;
    G.storyChoices = [];
    G.flags = {};
    G.runStats = {
        damageDealt: 0, damageTaken: 0, itemsFound: 0,
        enemiesKilled: 0, bossesKilled: 0, floorsCleared: 0,
        parries: 0, dodges: 0, healsUsed: 0,
        skillsUnlocked: 0, deathCount: 0
    };

    // Give starting weapon
    if (window.generateWeapon && window.Inventory) {
        const starterSword = generateWeapon(1, 0);
        if (starterSword) {
            Inventory.addItem(starterSword);
            Inventory.equipItem(0);
        }
    }

    // Generate first floor
    Engine.generateFloor(1);

    // Start ambient audio
    if (window.getFloorTheme && window.SFX && SFX.playAmbient) {
        const theme = getFloorTheme(1);
        SFX.playAmbient(theme.name);
    }

    // Brief fade-in
    if (window.Transitions && Transitions.start) {
        Transitions.start('fadeIn', 1.0, null, {});
    }
};

Engine.generateFloor = function(floor) {
    G.currentFloor = floor;

    // Generate dungeon
    const mapW = Math.min(80 + Math.floor(floor / 5) * 5, 100);
    const mapH = Math.min(60 + Math.floor(floor / 5) * 4, 80);

    if (window.TileMap && TileMap.init) {
        TileMap.init(mapW, mapH);
    }

    if (window.Dungeon && Dungeon.generate) {
        Dungeon.generate(floor, G.seed + floor * 1000);
    }

    // Reset fog for new floor
    if (window.Fog && Fog.init) {
        Fog.init(mapW, mapH);
    }

    // Reset lighting
    if (window.Lighting && Lighting.init) {
        Lighting.init(mapW * TILE_SIZE, mapH * TILE_SIZE);
    }

    // Place torches on walls near rooms
    if (window.TileMap && TileMap.rooms && window.Lighting && Lighting.addLight) {
        for (const room of TileMap.rooms) {
            // Place torches at room entrances
            const cx = room.x + Math.floor(room.w / 2);
            const cy = room.y + Math.floor(room.h / 2);
            Lighting.addLight(cx * TILE_SIZE, cy * TILE_SIZE, 128, '#ffa040', 0.5, true);
        }
    }

    // Place campfire lights
    if (window.TileMap && TileMap.getTile && window.Lighting && Lighting.addLight) {
        for (let y = 0; y < mapH; y++) {
            for (let x = 0; x < mapW; x++) {
                if (TileMap.getTile(x, y) === 6) { // TILE_CAMPFIRE
                    Lighting.addLight(x * TILE_SIZE + TILE_SIZE / 2, y * TILE_SIZE + TILE_SIZE / 2, 160, '#ff8020', 0.8, true);
                }
            }
        }
    }

    // Spawn enemies
    if (window.Dungeon && Dungeon.placeEnemies) {
        Dungeon.placeEnemies(floor, G.difficulty);
    }

    // Place player at stairs up / spawn point
    if (window.Dungeon && Dungeon.spawnPoint && G.player) {
        G.player.x = Dungeon.spawnPoint.x * TILE_SIZE + TILE_SIZE / 2;
        G.player.y = Dungeon.spawnPoint.y * TILE_SIZE + TILE_SIZE / 2;
    }

    // Clear projectiles and particles
    G.projectiles = [];
    G.items = [];
    if (window.FX && FX.init) {
        FX.init();
    }

    // Update ambient
    if (window.getFloorTheme && window.SFX && SFX.playAmbient) {
        const theme = getFloorTheme(floor);
        SFX.playAmbient(theme.name);
    }

    // Update deepest floor
    if (floor > G.deepestFloor) {
        G.deepestFloor = floor;
    }

    // Update run stats
    if (floor > 1) {
        G.runStats.floorsCleared++;
    }
};

Engine.descendStairs = function() {
    const nextFloor = G.currentFloor + 1;

    if (nextFloor > G.maxFloor) {
        // Victory! Determine ending
        Engine.triggerVictory();
        return;
    }

    // Check if next floor is a boss floor
    const isBossFloor = (nextFloor % 5 === 0);

    // Floor transition
    if (window.Transitions && Transitions.start) {
        Transitions.start('floorTransition', 2.0, function() {
            Engine.generateFloor(nextFloor);
        }, { floor: nextFloor, theme: window.getFloorTheme ? getFloorTheme(nextFloor).name : 'Unknown' });
    } else {
        Engine.generateFloor(nextFloor);
    }
};

// =============================================================================
// INTERACTION
// =============================================================================

Engine.tryInteract = function() {
    if (!G.player) return false;

    const ptx = Math.floor(G.player.x / TILE_SIZE);
    const pty = Math.floor(G.player.y / TILE_SIZE);

    // Check adjacent tiles for interactables
    const facingDir = G.player.facing || 0;
    const dirOffsets = [
        { dx: 0, dy: -1 }, // up
        { dx: 1, dy: 0 },  // right
        { dx: 0, dy: 1 },  // down
        { dx: -1, dy: 0 }  // left
    ];
    const offset = dirOffsets[facingDir] || { dx: 0, dy: 0 };

    const checkPositions = [
        { x: ptx, y: pty },
        { x: ptx + offset.dx, y: pty + offset.dy }
    ];

    if (window.TileMap && TileMap.getTile) {
        for (const pos of checkPositions) {
            const tile = TileMap.getTile(pos.x, pos.y);

            if (tile === 4) { // TILE_STAIRS_DOWN
                Engine.descendStairs();
                return true;
            }

            if (tile === 6) { // TILE_CAMPFIRE
                // Save at campfire
                G.player.hp = G.player.maxHp;
                G.player.mana = G.player.maxMana;
                G.player.stamina = G.player.maxStamina;
                if (window.Save) {
                    Save.saveCampfire();
                    Save.saveGame();
                }
                if (window.SFX && SFX.playSound) {
                    SFX.playSound('campfire_rest');
                }
                if (window.HUD && HUD.addFloatingText) {
                    HUD.addFloatingText(G.player.x, G.player.y - 20, 'Campfire Rest - Saved!', '#ffa040', 18);
                }
                return true;
            }

            if (tile === 7) { // TILE_CHEST
                TileMap.setTile(pos.x, pos.y, 1); // Change to floor
                if (window.SFX && SFX.playSound) {
                    SFX.playSound('chest_open');
                }
                if (window.Inventory && Inventory.spawnLoot) {
                    Inventory.spawnLoot(pos.x * TILE_SIZE + TILE_SIZE / 2, pos.y * TILE_SIZE + TILE_SIZE / 2, G.currentFloor, 0.5);
                }
                G.runStats.itemsFound++;
                return true;
            }

            if (tile === 10) { // TILE_BOSS_GATE
                // Check if all enemies on floor are dead (except boss)
                const nonBossEnemies = G.enemies.filter(e => !e.isBoss);
                if (nonBossEnemies.length === 0) {
                    TileMap.setTile(pos.x, pos.y, 1); // Open gate
                    if (window.SFX && SFX.playSound) {
                        SFX.playSound('door_open');
                    }

                    // Start boss intro if boss exists
                    if (G.bossActive && window.Transitions && Transitions.start) {
                        Transitions.start('bossIntro', 3.0, null, { boss: G.bossActive });
                    }
                    return true;
                } else {
                    if (window.HUD && HUD.addFloatingText) {
                        HUD.addFloatingText(G.player.x, G.player.y - 20, 'Defeat all enemies first!', '#ff4444', 14);
                    }
                    return true;
                }
            }
        }
    }

    // Check for NPC interaction
    if (G.npcs && window.NPC_DIALOGUES && window.Dialogue && Dialogue.start) {
        for (const npc of G.npcs) {
            const dist = Math.hypot(G.player.x - npc.x, G.player.y - npc.y);
            if (dist < TILE_SIZE * 2) {
                // Start dialogue
                if (NPC_DIALOGUES[npc.dialogueId]) {
                    Dialogue.start(NPC_DIALOGUES[npc.dialogueId]);
                    return true;
                }
            }
        }
    }

    return false;
};

Engine.isNearCampfire = function() {
    if (!G.player || !window.TileMap || !TileMap.getTile) return false;
    const ptx = Math.floor(G.player.x / TILE_SIZE);
    const pty = Math.floor(G.player.y / TILE_SIZE);

    for (let dy = -1; dy <= 1; dy++) {
        for (let dx = -1; dx <= 1; dx++) {
            if (TileMap.getTile(ptx + dx, pty + dy) === 6) return true;
        }
    }
    return false;
};

// =============================================================================
// CAMPFIRE RESTORE
// =============================================================================

Engine.restoreFromCampfire = function(campfireData) {
    G.currentFloor = campfireData.floor;
    G.gameState = STATE.PLAYING;

    // Re-init player with saved data
    if (window.Player && Player.init) {
        Player.init();
        G.player.hp = campfireData.playerHp || G.player.maxHp;
        G.player.maxHp = campfireData.playerMaxHp || G.player.maxHp;
        G.player.mana = campfireData.playerMana || G.player.maxMana;
        G.player.maxMana = campfireData.playerMaxMana || G.player.maxMana;
        G.player.level = campfireData.playerLevel || 1;
        G.player.xp = campfireData.playerXp || 0;
        G.player.inventory = campfireData.inventory || [];
        G.player.equipment = campfireData.equipment || {};
        G.player.gold = campfireData.gold || 0;
    }

    G.flags = campfireData.flags || {};
    G.storyChoices = campfireData.storyChoices || [];

    G.runStats.deathCount++;

    // Regenerate the floor
    Engine.generateFloor(G.currentFloor);

    if (window.Transitions && Transitions.start) {
        Transitions.start('fadeIn', 1.0, null, {});
    }
};

// =============================================================================
// VICTORY / ENDINGS
// =============================================================================

Engine.triggerVictory = function() {
    // Determine ending based on story choices
    Engine.currentEnding = Engine.determineEnding();

    if (window.Save && Save.saveHighScore) {
        Save.saveHighScore(G.score, G.currentFloor);
    }

    if (window.Transitions && Transitions.start) {
        Transitions.start('victoryTransition', 3.0, function() {
            G.gameState = STATE.VICTORY;
        }, { ending: Engine.currentEnding });
    } else {
        G.gameState = STATE.VICTORY;
    }
};

Engine.determineEnding = function() {
    const choices = G.storyChoices;

    // Check ENDINGS array for matching requirements
    if (typeof ENDINGS !== 'undefined') {
        for (const ending of ENDINGS) {
            if (ending.requirements && typeof ending.requirements === 'function') {
                if (ending.requirements(choices, G.flags)) {
                    return ending;
                }
            }
        }
    }

    // Default ending
    return {
        id: 'sealed_gate',
        name: 'The Sealed Gate',
        title: 'The Abyss is Sealed',
        description: 'You sealed the darkness below. The world above is safe once more.',
        epilogue: 'The hero emerged from the depths, forever changed. The gate was sealed, and peace returned to the land. But deep below, something still stirs...'
    };
};

// =============================================================================
// BOOT
// =============================================================================

// Start when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', Engine.init);
} else {
    Engine.init();
}
