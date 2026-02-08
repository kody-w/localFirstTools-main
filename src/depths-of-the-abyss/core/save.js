'use strict';

// =============================================================================
// SAVE.JS - Save/load system using localStorage
// =============================================================================

const Save = {
    SLOT_KEY: 'depths_save',
    SETTINGS_KEY: 'depths_settings',
    HIGHSCORE_KEY: 'depths_highscore',
    CAMPFIRE_KEY: 'depths_campfire'
};

// =============================================================================
// GAME SAVE/LOAD
// =============================================================================

Save.saveGame = function() {
    if (!G || !G.player) {
        console.warn('Cannot save: game state not initialized');
        return false;
    }

    try {
        const saveData = {
            version: '1.0.0',
            timestamp: Date.now(),
            gameState: G.gameState,
            difficulty: G.difficulty,
            difficultyLevel: G.difficultyLevel,
            currentFloor: G.currentFloor,
            seed: G.seed,
            time: G.time,
            totalPlayTime: G.totalPlayTime,
            score: G.score,
            kills: G.kills,

            player: {
                x: G.player.x,
                y: G.player.y,
                hp: G.player.hp,
                maxHp: G.player.maxHp,
                mana: G.player.mana,
                maxMana: G.player.maxMana,
                stamina: G.player.stamina,
                maxStamina: G.player.maxStamina,
                level: G.player.level,
                xp: G.player.xp,
                xpToLevel: G.player.xpToLevel,
                attackDmg: G.player.attackDmg,
                defense: G.player.defense,
                speed: G.player.speed,
                inventory: G.player.inventory || [],
                equipment: G.player.equipment || {},
                skills: G.player.skills || [],
                unlockedSkills: G.player.unlockedSkills || [],
                gold: G.player.gold || 0
            },

            storyChoices: G.storyChoices,
            flags: G.flags,
            runStats: G.runStats,
            lastCampfire: G.lastCampfire
        };

        localStorage.setItem(Save.SLOT_KEY, JSON.stringify(saveData));
        console.log('Game saved successfully');
        return true;
    } catch (e) {
        console.error('Failed to save game:', e);
        return false;
    }
};

Save.loadGame = function() {
    try {
        const saveJson = localStorage.getItem(Save.SLOT_KEY);
        if (!saveJson) {
            console.log('No save data found');
            return null;
        }

        const saveData = JSON.parse(saveJson);

        // Restore game state
        G.gameState = saveData.gameState || STATE.TITLE;
        G.difficulty = saveData.difficulty || DIFFICULTY.NORMAL;
        G.difficultyLevel = saveData.difficultyLevel || 1;
        G.currentFloor = saveData.currentFloor || 1;
        G.seed = saveData.seed || Date.now();
        G.time = saveData.time || 0;
        G.totalPlayTime = saveData.totalPlayTime || 0;
        G.score = saveData.score || 0;
        G.kills = saveData.kills || 0;
        G.storyChoices = saveData.storyChoices || [];
        G.flags = saveData.flags || {};
        G.runStats = saveData.runStats || {};
        G.lastCampfire = saveData.lastCampfire || null;

        // Restore player (Note: actual Player object creation handled by game init)
        const playerData = saveData.player;

        console.log('Game loaded successfully from', new Date(saveData.timestamp));
        return playerData;
    } catch (e) {
        console.error('Failed to load game:', e);
        return null;
    }
};

Save.hasSave = function() {
    return localStorage.getItem(Save.SLOT_KEY) !== null;
};

Save.deleteSave = function() {
    try {
        localStorage.removeItem(Save.SLOT_KEY);
        localStorage.removeItem(Save.CAMPFIRE_KEY);
        console.log('Save deleted');
        return true;
    } catch (e) {
        console.error('Failed to delete save:', e);
        return false;
    }
};

// =============================================================================
// HIGH SCORE / STATS
// =============================================================================

Save.saveHighScore = function(score, floor) {
    try {
        const current = Save.loadHighScore();

        const newData = {
            highScore: Math.max(current.highScore, score),
            deepestFloor: Math.max(current.deepestFloor, floor),
            lastUpdated: Date.now()
        };

        localStorage.setItem(Save.HIGHSCORE_KEY, JSON.stringify(newData));
        G.highScore = newData.highScore;
        G.deepestFloor = newData.deepestFloor;

        console.log('High score saved:', newData);
        return true;
    } catch (e) {
        console.error('Failed to save high score:', e);
        return false;
    }
};

Save.loadHighScore = function() {
    try {
        const json = localStorage.getItem(Save.HIGHSCORE_KEY);
        if (!json) {
            return { highScore: 0, deepestFloor: 0, lastUpdated: null };
        }

        const data = JSON.parse(json);
        return {
            highScore: data.highScore || 0,
            deepestFloor: data.deepestFloor || 0,
            lastUpdated: data.lastUpdated || null
        };
    } catch (e) {
        console.error('Failed to load high score:', e);
        return { highScore: 0, deepestFloor: 0, lastUpdated: null };
    }
};

// =============================================================================
// SETTINGS
// =============================================================================

Save.saveSettings = function(settings) {
    try {
        const data = {
            volume: settings.volume !== undefined ? settings.volume : 0.6,
            sfxVolume: settings.sfxVolume !== undefined ? settings.sfxVolume : 0.8,
            musicVolume: settings.musicVolume !== undefined ? settings.musicVolume : 0.5,
            difficulty: settings.difficulty || DIFFICULTY.NORMAL,
            controlScheme: settings.controlScheme || 'default',
            showFPS: settings.showFPS !== undefined ? settings.showFPS : false,
            screenShake: settings.screenShake !== undefined ? settings.screenShake : true,
            particles: settings.particles !== undefined ? settings.particles : true
        };

        localStorage.setItem(Save.SETTINGS_KEY, JSON.stringify(data));
        console.log('Settings saved');
        return true;
    } catch (e) {
        console.error('Failed to save settings:', e);
        return false;
    }
};

Save.loadSettings = function() {
    try {
        const json = localStorage.getItem(Save.SETTINGS_KEY);
        if (!json) {
            return {
                volume: 0.6,
                sfxVolume: 0.8,
                musicVolume: 0.5,
                difficulty: DIFFICULTY.NORMAL,
                controlScheme: 'default',
                showFPS: false,
                screenShake: true,
                particles: true
            };
        }

        return JSON.parse(json);
    } catch (e) {
        console.error('Failed to load settings:', e);
        return {};
    }
};

// =============================================================================
// CAMPFIRE CHECKPOINT SAVE
// =============================================================================

Save.saveCampfire = function() {
    if (!G || !G.player) {
        console.warn('Cannot save campfire: game state not initialized');
        return false;
    }

    try {
        const campfireData = {
            timestamp: Date.now(),
            floor: G.currentFloor,
            playerHp: G.player.hp,
            playerMaxHp: G.player.maxHp,
            playerMana: G.player.mana,
            playerMaxMana: G.player.maxMana,
            playerLevel: G.player.level,
            playerXp: G.player.xp,
            inventory: G.player.inventory || [],
            equipment: G.player.equipment || {},
            gold: G.player.gold || 0,
            flags: G.flags,
            storyChoices: G.storyChoices
        };

        localStorage.setItem(Save.CAMPFIRE_KEY, JSON.stringify(campfireData));
        G.lastCampfire = campfireData;

        console.log('Campfire checkpoint saved');
        return true;
    } catch (e) {
        console.error('Failed to save campfire:', e);
        return false;
    }
};

Save.loadCampfire = function() {
    try {
        const json = localStorage.getItem(Save.CAMPFIRE_KEY);
        if (!json) {
            console.log('No campfire save found');
            return null;
        }

        const data = JSON.parse(json);
        console.log('Campfire checkpoint loaded from floor', data.floor);
        return data;
    } catch (e) {
        console.error('Failed to load campfire:', e);
        return null;
    }
};

Save.hasCampfire = function() {
    return localStorage.getItem(Save.CAMPFIRE_KEY) !== null;
};

Save.deleteCampfire = function() {
    try {
        localStorage.removeItem(Save.CAMPFIRE_KEY);
        G.lastCampfire = null;
        return true;
    } catch (e) {
        console.error('Failed to delete campfire:', e);
        return false;
    }
};

// =============================================================================
// RESET / NEW GAME
// =============================================================================

Save.resetGame = function() {
    console.log('Resetting game to new game state');

    // Clear game state
    G.gameState = STATE.TITLE;
    G.currentFloor = 1;
    G.player = null;
    G.enemies = [];
    G.projectiles = [];
    G.items = [];
    G.particles = [];
    G.lights = [];
    G.npcs = [];
    G.dungeon = null;
    G.time = 0;
    G.dt = 0;
    G.frameCount = 0;
    G.bossActive = null;
    G.dialogueQueue = [];
    G.floatingTexts = [];
    G.score = 0;
    G.kills = 0;
    G.totalPlayTime = 0;
    G.seed = Date.now();
    G.storyChoices = [];
    G.flags = {};
    G.combo = 0;
    G.comboTimer = 0;
    G.lastCampfire = null;

    // Reset run stats
    G.runStats = {
        damageDealt: 0,
        damageTaken: 0,
        itemsFound: 0,
        enemiesKilled: 0,
        bossesKilled: 0,
        floorsCleared: 0,
        parries: 0,
        dodges: 0,
        healsUsed: 0,
        skillsUnlocked: 0,
        deathCount: 0
    };

    // Clear campfire but keep high scores
    Save.deleteCampfire();

    return true;
};

Save.newGame = function(difficulty) {
    Save.resetGame();
    G.difficulty = difficulty || DIFFICULTY.NORMAL;
    G.gameState = STATE.PLAYING;
    console.log('Starting new game on', G.difficulty, 'difficulty');
    return true;
};

Save.restart = function() {
    console.log('Restarting game');
    Save.resetGame();
    return true;
};

// =============================================================================
// IMPORT / EXPORT JSON
// =============================================================================

Save.exportJSON = function() {
    try {
        const exportData = {
            save: localStorage.getItem(Save.SLOT_KEY),
            settings: localStorage.getItem(Save.SETTINGS_KEY),
            highscore: localStorage.getItem(Save.HIGHSCORE_KEY),
            campfire: localStorage.getItem(Save.CAMPFIRE_KEY),
            exportDate: new Date().toISOString()
        };

        const json = JSON.stringify(exportData, null, 2);
        const blob = new Blob([json], { type: 'application/json' });
        const url = URL.createObjectURL(blob);

        const a = document.createElement('a');
        a.href = url;
        a.download = 'depths-save-' + Date.now() + '.json';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        console.log('Save exported successfully');
        return true;
    } catch (e) {
        console.error('Failed to export save:', e);
        return false;
    }
};

Save.importJSON = function(jsonString) {
    try {
        const importData = JSON.parse(jsonString);

        if (importData.save) {
            localStorage.setItem(Save.SLOT_KEY, importData.save);
        }
        if (importData.settings) {
            localStorage.setItem(Save.SETTINGS_KEY, importData.settings);
        }
        if (importData.highscore) {
            localStorage.setItem(Save.HIGHSCORE_KEY, importData.highscore);
        }
        if (importData.campfire) {
            localStorage.setItem(Save.CAMPFIRE_KEY, importData.campfire);
        }

        console.log('Save imported successfully from', importData.exportDate);
        return true;
    } catch (e) {
        console.error('Failed to import save:', e);
        return false;
    }
};

// =============================================================================
// UTILITIES
// =============================================================================

Save.getSaveInfo = function() {
    try {
        const saveJson = localStorage.getItem(Save.SLOT_KEY);
        if (!saveJson) return null;

        const saveData = JSON.parse(saveJson);
        return {
            timestamp: saveData.timestamp,
            floor: saveData.currentFloor,
            difficulty: saveData.difficulty,
            playTime: saveData.totalPlayTime,
            score: saveData.score,
            playerLevel: saveData.player ? saveData.player.level : 1
        };
    } catch (e) {
        console.error('Failed to get save info:', e);
        return null;
    }
};

Save.clearAllData = function() {
    try {
        localStorage.removeItem(Save.SLOT_KEY);
        localStorage.removeItem(Save.SETTINGS_KEY);
        localStorage.removeItem(Save.HIGHSCORE_KEY);
        localStorage.removeItem(Save.CAMPFIRE_KEY);
        console.log('All save data cleared');
        return true;
    } catch (e) {
        console.error('Failed to clear data:', e);
        return false;
    }
};
