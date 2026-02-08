'use strict';

// =============================================================================
// AUDIO.JS - Procedural audio system using Web Audio API
// =============================================================================

const SFX = {
    ctx: null,
    masterGain: null,
    compressor: null,
    volume: 0.6,
    sfxVolume: 0.8,
    musicVolume: 0.5,
    ambientSource: null,
    ambientGain: null,
    initialized: false
};

// =============================================================================
// INITIALIZATION
// =============================================================================

SFX.init = function() {
    if (SFX.initialized) return;

    try {
        // Support both standard and webkit AudioContext
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        SFX.ctx = new AudioContext();

        // Master gain node
        SFX.masterGain = SFX.ctx.createGain();
        SFX.masterGain.gain.value = SFX.volume;

        // Compressor to prevent clipping
        SFX.compressor = SFX.ctx.createDynamicsCompressor();
        SFX.compressor.threshold.value = -20;
        SFX.compressor.knee.value = 10;
        SFX.compressor.ratio.value = 12;
        SFX.compressor.attack.value = 0.003;
        SFX.compressor.release.value = 0.25;

        SFX.masterGain.connect(SFX.compressor);
        SFX.compressor.connect(SFX.ctx.destination);

        SFX.initialized = true;
        console.log('Audio system initialized');
    } catch (e) {
        console.warn('Web Audio API not supported:', e);
    }
};

SFX.resume = function() {
    if (SFX.ctx && SFX.ctx.state === 'suspended') {
        SFX.ctx.resume();
    }
};

SFX.setVolume = function(vol) {
    SFX.volume = Util.clamp(vol, 0, 1);
    if (SFX.masterGain) {
        SFX.masterGain.gain.value = SFX.volume;
    }
};

// =============================================================================
// CORE SOUND GENERATION
// =============================================================================

SFX.playSound = function(name) {
    if (!SFX.initialized || !SFX.ctx) return;
    SFX.resume();

    const soundFunc = SFX.sounds[name];
    if (soundFunc) {
        soundFunc();
    } else {
        console.warn('Sound not found:', name);
    }
};

SFX.playSFX = function(name) {
    SFX.playSound(name);
};

// =============================================================================
// SOUND EFFECT LIBRARY (30+ sounds)
// =============================================================================

SFX.sounds = {};

// --- WEAPON SOUNDS ---

SFX.sounds.sword_swing = function() {
    const now = SFX.ctx.currentTime;
    const osc = SFX.ctx.createOscillator();
    const gain = SFX.ctx.createGain();
    const filter = SFX.ctx.createBiquadFilter();

    osc.type = 'sawtooth';
    osc.frequency.setValueAtTime(200, now);
    osc.frequency.exponentialRampToValueAtTime(80, now + 0.1);

    filter.type = 'lowpass';
    filter.frequency.value = 600;

    gain.gain.setValueAtTime(0.3 * SFX.sfxVolume, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.1);

    osc.connect(filter);
    filter.connect(gain);
    gain.connect(SFX.masterGain);

    osc.start(now);
    osc.stop(now + 0.1);
};

SFX.sounds.sword_hit = function() {
    const now = SFX.ctx.currentTime;
    const osc = SFX.ctx.createOscillator();
    const gain = SFX.ctx.createGain();

    osc.type = 'square';
    osc.frequency.setValueAtTime(150, now);
    osc.frequency.exponentialRampToValueAtTime(50, now + 0.15);

    gain.gain.setValueAtTime(0.4 * SFX.sfxVolume, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.15);

    osc.connect(gain);
    gain.connect(SFX.masterGain);

    osc.start(now);
    osc.stop(now + 0.15);
};

SFX.sounds.axe_hit = function() {
    const now = SFX.ctx.currentTime;
    const osc = SFX.ctx.createOscillator();
    const gain = SFX.ctx.createGain();
    const filter = SFX.ctx.createBiquadFilter();

    osc.type = 'sawtooth';
    osc.frequency.setValueAtTime(100, now);
    osc.frequency.exponentialRampToValueAtTime(30, now + 0.2);

    filter.type = 'lowpass';
    filter.frequency.value = 400;

    gain.gain.setValueAtTime(0.5 * SFX.sfxVolume, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.2);

    osc.connect(filter);
    filter.connect(gain);
    gain.connect(SFX.masterGain);

    osc.start(now);
    osc.stop(now + 0.2);
};

SFX.sounds.bow_shot = function() {
    const now = SFX.ctx.currentTime;
    const osc = SFX.ctx.createOscillator();
    const gain = SFX.ctx.createGain();

    osc.type = 'sine';
    osc.frequency.setValueAtTime(800, now);
    osc.frequency.exponentialRampToValueAtTime(200, now + 0.08);

    gain.gain.setValueAtTime(0.2 * SFX.sfxVolume, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.08);

    osc.connect(gain);
    gain.connect(SFX.masterGain);

    osc.start(now);
    osc.stop(now + 0.08);
};

SFX.sounds.arrow_hit = function() {
    const now = SFX.ctx.currentTime;
    const osc = SFX.ctx.createOscillator();
    const gain = SFX.ctx.createGain();

    osc.type = 'triangle';
    osc.frequency.setValueAtTime(600, now);
    osc.frequency.exponentialRampToValueAtTime(100, now + 0.1);

    gain.gain.setValueAtTime(0.25 * SFX.sfxVolume, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.1);

    osc.connect(gain);
    gain.connect(SFX.masterGain);

    osc.start(now);
    osc.stop(now + 0.1);
};

// --- SPELL SOUNDS ---

SFX.sounds.fireball_cast = function() {
    const now = SFX.ctx.currentTime;
    const osc1 = SFX.ctx.createOscillator();
    const osc2 = SFX.ctx.createOscillator();
    const gain = SFX.ctx.createGain();

    osc1.type = 'triangle';
    osc1.frequency.setValueAtTime(300, now);
    osc1.frequency.exponentialRampToValueAtTime(600, now + 0.2);

    osc2.type = 'sawtooth';
    osc2.frequency.setValueAtTime(150, now);
    osc2.frequency.exponentialRampToValueAtTime(300, now + 0.2);

    gain.gain.setValueAtTime(0.3 * SFX.sfxVolume, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.2);

    osc1.connect(gain);
    osc2.connect(gain);
    gain.connect(SFX.masterGain);

    osc1.start(now);
    osc2.start(now);
    osc1.stop(now + 0.2);
    osc2.stop(now + 0.2);
};

SFX.sounds.fireball_explode = function() {
    const now = SFX.ctx.currentTime;
    const osc = SFX.ctx.createOscillator();
    const gain = SFX.ctx.createGain();
    const filter = SFX.ctx.createBiquadFilter();

    osc.type = 'sawtooth';
    osc.frequency.setValueAtTime(200, now);
    osc.frequency.exponentialRampToValueAtTime(40, now + 0.3);

    filter.type = 'lowpass';
    filter.frequency.setValueAtTime(2000, now);
    filter.frequency.exponentialRampToValueAtTime(200, now + 0.3);

    gain.gain.setValueAtTime(0.5 * SFX.sfxVolume, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.3);

    osc.connect(filter);
    filter.connect(gain);
    gain.connect(SFX.masterGain);

    osc.start(now);
    osc.stop(now + 0.3);
};

SFX.sounds.ice_spell = function() {
    const now = SFX.ctx.currentTime;
    const osc = SFX.ctx.createOscillator();
    const gain = SFX.ctx.createGain();
    const filter = SFX.ctx.createBiquadFilter();

    osc.type = 'sine';
    osc.frequency.setValueAtTime(1200, now);
    osc.frequency.exponentialRampToValueAtTime(400, now + 0.25);

    filter.type = 'highpass';
    filter.frequency.value = 800;

    gain.gain.setValueAtTime(0.25 * SFX.sfxVolume, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.25);

    osc.connect(filter);
    filter.connect(gain);
    gain.connect(SFX.masterGain);

    osc.start(now);
    osc.stop(now + 0.25);
};

SFX.sounds.lightning_spell = function() {
    const now = SFX.ctx.currentTime;
    const osc = SFX.ctx.createOscillator();
    const gain = SFX.ctx.createGain();

    osc.type = 'square';
    osc.frequency.setValueAtTime(2000, now);
    osc.frequency.exponentialRampToValueAtTime(100, now + 0.12);

    gain.gain.setValueAtTime(0.35 * SFX.sfxVolume, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.12);

    osc.connect(gain);
    gain.connect(SFX.masterGain);

    osc.start(now);
    osc.stop(now + 0.12);
};

SFX.sounds.poison_cloud = function() {
    const now = SFX.ctx.currentTime;
    const osc = SFX.ctx.createOscillator();
    const gain = SFX.ctx.createGain();
    const filter = SFX.ctx.createBiquadFilter();

    osc.type = 'sawtooth';
    osc.frequency.setValueAtTime(80, now);
    osc.frequency.exponentialRampToValueAtTime(120, now + 0.4);

    filter.type = 'bandpass';
    filter.frequency.value = 400;

    gain.gain.setValueAtTime(0.2 * SFX.sfxVolume, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.4);

    osc.connect(filter);
    filter.connect(gain);
    gain.connect(SFX.masterGain);

    osc.start(now);
    osc.stop(now + 0.4);
};

// --- PLAYER ACTIONS ---

SFX.sounds.dodge_roll = function() {
    const now = SFX.ctx.currentTime;
    const osc = SFX.ctx.createOscillator();
    const gain = SFX.ctx.createGain();

    osc.type = 'triangle';
    osc.frequency.setValueAtTime(120, now);
    osc.frequency.exponentialRampToValueAtTime(60, now + 0.15);

    gain.gain.setValueAtTime(0.2 * SFX.sfxVolume, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.15);

    osc.connect(gain);
    gain.connect(SFX.masterGain);

    osc.start(now);
    osc.stop(now + 0.15);
};

SFX.sounds.parry_success = function() {
    const now = SFX.ctx.currentTime;
    const osc = SFX.ctx.createOscillator();
    const gain = SFX.ctx.createGain();

    osc.type = 'sine';
    osc.frequency.setValueAtTime(800, now);
    osc.frequency.exponentialRampToValueAtTime(1200, now + 0.2);

    gain.gain.setValueAtTime(0.4 * SFX.sfxVolume, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.2);

    osc.connect(gain);
    gain.connect(SFX.masterGain);

    osc.start(now);
    osc.stop(now + 0.2);
};

SFX.sounds.shield_block = function() {
    const now = SFX.ctx.currentTime;
    const osc = SFX.ctx.createOscillator();
    const gain = SFX.ctx.createGain();

    osc.type = 'square';
    osc.frequency.setValueAtTime(180, now);
    osc.frequency.exponentialRampToValueAtTime(90, now + 0.18);

    gain.gain.setValueAtTime(0.35 * SFX.sfxVolume, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.18);

    osc.connect(gain);
    gain.connect(SFX.masterGain);

    osc.start(now);
    osc.stop(now + 0.18);
};

// --- PLAYER STATUS ---

SFX.sounds.player_hurt = function() {
    const now = SFX.ctx.currentTime;
    const osc = SFX.ctx.createOscillator();
    const gain = SFX.ctx.createGain();

    osc.type = 'sawtooth';
    osc.frequency.setValueAtTime(400, now);
    osc.frequency.exponentialRampToValueAtTime(150, now + 0.2);

    gain.gain.setValueAtTime(0.35 * SFX.sfxVolume, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.2);

    osc.connect(gain);
    gain.connect(SFX.masterGain);

    osc.start(now);
    osc.stop(now + 0.2);
};

SFX.sounds.player_death = function() {
    const now = SFX.ctx.currentTime;
    const osc = SFX.ctx.createOscillator();
    const gain = SFX.ctx.createGain();
    const filter = SFX.ctx.createBiquadFilter();

    osc.type = 'sawtooth';
    osc.frequency.setValueAtTime(300, now);
    osc.frequency.exponentialRampToValueAtTime(40, now + 1.0);

    filter.type = 'lowpass';
    filter.frequency.setValueAtTime(1000, now);
    filter.frequency.exponentialRampToValueAtTime(100, now + 1.0);

    gain.gain.setValueAtTime(0.5 * SFX.sfxVolume, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 1.0);

    osc.connect(filter);
    filter.connect(gain);
    gain.connect(SFX.masterGain);

    osc.start(now);
    osc.stop(now + 1.0);
};

SFX.sounds.player_heal = function() {
    const now = SFX.ctx.currentTime;
    const osc = SFX.ctx.createOscillator();
    const gain = SFX.ctx.createGain();

    osc.type = 'sine';
    osc.frequency.setValueAtTime(400, now);
    osc.frequency.exponentialRampToValueAtTime(800, now + 0.3);

    gain.gain.setValueAtTime(0.25 * SFX.sfxVolume, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.3);

    osc.connect(gain);
    gain.connect(SFX.masterGain);

    osc.start(now);
    osc.stop(now + 0.3);
};

SFX.sounds.player_levelup = function() {
    const now = SFX.ctx.currentTime;
    const notes = [523.25, 659.25, 783.99]; // C5, E5, G5

    notes.forEach((freq, i) => {
        const osc = SFX.ctx.createOscillator();
        const gain = SFX.ctx.createGain();

        osc.type = 'sine';
        osc.frequency.value = freq;

        const startTime = now + i * 0.15;
        gain.gain.setValueAtTime(0.3 * SFX.sfxVolume, startTime);
        gain.gain.exponentialRampToValueAtTime(0.01, startTime + 0.4);

        osc.connect(gain);
        gain.connect(SFX.masterGain);

        osc.start(startTime);
        osc.stop(startTime + 0.4);
    });
};

// --- ENEMY SOUNDS ---

SFX.sounds.enemy_hurt = function() {
    const now = SFX.ctx.currentTime;
    const osc = SFX.ctx.createOscillator();
    const gain = SFX.ctx.createGain();

    osc.type = 'square';
    osc.frequency.setValueAtTime(250, now);
    osc.frequency.exponentialRampToValueAtTime(100, now + 0.15);

    gain.gain.setValueAtTime(0.25 * SFX.sfxVolume, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.15);

    osc.connect(gain);
    gain.connect(SFX.masterGain);

    osc.start(now);
    osc.stop(now + 0.15);
};

SFX.sounds.enemy_death = function() {
    const now = SFX.ctx.currentTime;
    const osc = SFX.ctx.createOscillator();
    const gain = SFX.ctx.createGain();

    osc.type = 'sawtooth';
    osc.frequency.setValueAtTime(200, now);
    osc.frequency.exponentialRampToValueAtTime(30, now + 0.5);

    gain.gain.setValueAtTime(0.3 * SFX.sfxVolume, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.5);

    osc.connect(gain);
    gain.connect(SFX.masterGain);

    osc.start(now);
    osc.stop(now + 0.5);
};

SFX.sounds.enemy_alert = function() {
    const now = SFX.ctx.currentTime;
    const osc = SFX.ctx.createOscillator();
    const gain = SFX.ctx.createGain();

    osc.type = 'square';
    osc.frequency.setValueAtTime(300, now);
    osc.frequency.exponentialRampToValueAtTime(500, now + 0.1);

    gain.gain.setValueAtTime(0.2 * SFX.sfxVolume, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.1);

    osc.connect(gain);
    gain.connect(SFX.masterGain);

    osc.start(now);
    osc.stop(now + 0.1);
};

SFX.sounds.enemy_attack = function() {
    const now = SFX.ctx.currentTime;
    const osc = SFX.ctx.createOscillator();
    const gain = SFX.ctx.createGain();

    osc.type = 'sawtooth';
    osc.frequency.setValueAtTime(180, now);
    osc.frequency.exponentialRampToValueAtTime(90, now + 0.18);

    gain.gain.setValueAtTime(0.28 * SFX.sfxVolume, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.18);

    osc.connect(gain);
    gain.connect(SFX.masterGain);

    osc.start(now);
    osc.stop(now + 0.18);
};

// --- BOSS SOUNDS ---

SFX.sounds.boss_roar = function() {
    const now = SFX.ctx.currentTime;
    const osc = SFX.ctx.createOscillator();
    const gain = SFX.ctx.createGain();
    const filter = SFX.ctx.createBiquadFilter();

    osc.type = 'sawtooth';
    osc.frequency.setValueAtTime(80, now);
    osc.frequency.exponentialRampToValueAtTime(40, now + 0.8);

    filter.type = 'lowpass';
    filter.frequency.value = 300;

    gain.gain.setValueAtTime(0.6 * SFX.sfxVolume, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.8);

    osc.connect(filter);
    filter.connect(gain);
    gain.connect(SFX.masterGain);

    osc.start(now);
    osc.stop(now + 0.8);
};

SFX.sounds.boss_stomp = function() {
    const now = SFX.ctx.currentTime;
    const osc = SFX.ctx.createOscillator();
    const gain = SFX.ctx.createGain();

    osc.type = 'sine';
    osc.frequency.setValueAtTime(60, now);
    osc.frequency.exponentialRampToValueAtTime(30, now + 0.3);

    gain.gain.setValueAtTime(0.7 * SFX.sfxVolume, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.3);

    osc.connect(gain);
    gain.connect(SFX.masterGain);

    osc.start(now);
    osc.stop(now + 0.3);
};

SFX.sounds.boss_phase_change = function() {
    const now = SFX.ctx.currentTime;
    const osc = SFX.ctx.createOscillator();
    const gain = SFX.ctx.createGain();

    osc.type = 'square';
    osc.frequency.setValueAtTime(100, now);
    osc.frequency.exponentialRampToValueAtTime(400, now + 0.6);

    gain.gain.setValueAtTime(0.4 * SFX.sfxVolume, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.6);

    osc.connect(gain);
    gain.connect(SFX.masterGain);

    osc.start(now);
    osc.stop(now + 0.6);
};

// --- ITEM / UI SOUNDS ---

SFX.sounds.pickup_item = function() {
    const now = SFX.ctx.currentTime;
    const osc = SFX.ctx.createOscillator();
    const gain = SFX.ctx.createGain();

    osc.type = 'sine';
    osc.frequency.setValueAtTime(600, now);
    osc.frequency.exponentialRampToValueAtTime(900, now + 0.1);

    gain.gain.setValueAtTime(0.25 * SFX.sfxVolume, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.1);

    osc.connect(gain);
    gain.connect(SFX.masterGain);

    osc.start(now);
    osc.stop(now + 0.1);
};

SFX.sounds.equip_item = function() {
    const now = SFX.ctx.currentTime;
    const osc = SFX.ctx.createOscillator();
    const gain = SFX.ctx.createGain();

    osc.type = 'triangle';
    osc.frequency.value = 440;

    gain.gain.setValueAtTime(0.2 * SFX.sfxVolume, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.12);

    osc.connect(gain);
    gain.connect(SFX.masterGain);

    osc.start(now);
    osc.stop(now + 0.12);
};

SFX.sounds.craft_success = function() {
    const now = SFX.ctx.currentTime;
    const notes = [523.25, 698.46]; // C5, F5

    notes.forEach((freq, i) => {
        const osc = SFX.ctx.createOscillator();
        const gain = SFX.ctx.createGain();

        osc.type = 'sine';
        osc.frequency.value = freq;

        const startTime = now + i * 0.1;
        gain.gain.setValueAtTime(0.25 * SFX.sfxVolume, startTime);
        gain.gain.exponentialRampToValueAtTime(0.01, startTime + 0.2);

        osc.connect(gain);
        gain.connect(SFX.masterGain);

        osc.start(startTime);
        osc.stop(startTime + 0.2);
    });
};

SFX.sounds.menu_select = function() {
    const now = SFX.ctx.currentTime;
    const osc = SFX.ctx.createOscillator();
    const gain = SFX.ctx.createGain();

    osc.type = 'sine';
    osc.frequency.value = 440;

    gain.gain.setValueAtTime(0.15 * SFX.sfxVolume, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.08);

    osc.connect(gain);
    gain.connect(SFX.masterGain);

    osc.start(now);
    osc.stop(now + 0.08);
};

SFX.sounds.menu_back = function() {
    const now = SFX.ctx.currentTime;
    const osc = SFX.ctx.createOscillator();
    const gain = SFX.ctx.createGain();

    osc.type = 'sine';
    osc.frequency.value = 330;

    gain.gain.setValueAtTime(0.15 * SFX.sfxVolume, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.08);

    osc.connect(gain);
    gain.connect(SFX.masterGain);

    osc.start(now);
    osc.stop(now + 0.08);
};

// --- WORLD SOUNDS ---

SFX.sounds.door_open = function() {
    const now = SFX.ctx.currentTime;
    const osc = SFX.ctx.createOscillator();
    const gain = SFX.ctx.createGain();

    osc.type = 'sawtooth';
    osc.frequency.setValueAtTime(150, now);
    osc.frequency.exponentialRampToValueAtTime(100, now + 0.3);

    gain.gain.setValueAtTime(0.25 * SFX.sfxVolume, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.3);

    osc.connect(gain);
    gain.connect(SFX.masterGain);

    osc.start(now);
    osc.stop(now + 0.3);
};

SFX.sounds.chest_open = function() {
    const now = SFX.ctx.currentTime;
    const osc = SFX.ctx.createOscillator();
    const gain = SFX.ctx.createGain();

    osc.type = 'triangle';
    osc.frequency.setValueAtTime(200, now);
    osc.frequency.exponentialRampToValueAtTime(400, now + 0.25);

    gain.gain.setValueAtTime(0.3 * SFX.sfxVolume, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.25);

    osc.connect(gain);
    gain.connect(SFX.masterGain);

    osc.start(now);
    osc.stop(now + 0.25);
};

SFX.sounds.campfire_rest = function() {
    const now = SFX.ctx.currentTime;
    const osc = SFX.ctx.createOscillator();
    const gain = SFX.ctx.createGain();

    osc.type = 'sine';
    osc.frequency.value = 220;

    gain.gain.setValueAtTime(0.2 * SFX.sfxVolume, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.5);

    osc.connect(gain);
    gain.connect(SFX.masterGain);

    osc.start(now);
    osc.stop(now + 0.5);
};

// --- COMBO / SPECIAL ---

SFX.sounds.combo_hit = function() {
    const now = SFX.ctx.currentTime;
    const osc = SFX.ctx.createOscillator();
    const gain = SFX.ctx.createGain();

    osc.type = 'sine';
    osc.frequency.setValueAtTime(500, now);
    osc.frequency.exponentialRampToValueAtTime(800, now + 0.12);

    gain.gain.setValueAtTime(0.3 * SFX.sfxVolume, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.12);

    osc.connect(gain);
    gain.connect(SFX.masterGain);

    osc.start(now);
    osc.stop(now + 0.12);
};

SFX.sounds.critical_hit = function() {
    const now = SFX.ctx.currentTime;
    const osc = SFX.ctx.createOscillator();
    const gain = SFX.ctx.createGain();

    osc.type = 'square';
    osc.frequency.setValueAtTime(1000, now);
    osc.frequency.exponentialRampToValueAtTime(500, now + 0.2);

    gain.gain.setValueAtTime(0.4 * SFX.sfxVolume, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.2);

    osc.connect(gain);
    gain.connect(SFX.masterGain);

    osc.start(now);
    osc.stop(now + 0.2);
};

// =============================================================================
// AMBIENT AUDIO
// =============================================================================

SFX.playAmbient = function(theme) {
    SFX.stopAmbient();

    if (!SFX.ctx) return;

    const now = SFX.ctx.currentTime;
    const osc = SFX.ctx.createOscillator();
    const gain = SFX.ctx.createGain();

    SFX.ambientGain = gain;
    gain.gain.value = 0.1 * SFX.musicVolume;

    // Theme-based frequencies
    const themeFreqs = {
        drip: 60,
        wind: 80,
        rumble: 40,
        void: 30
    };

    osc.type = 'sine';
    osc.frequency.value = themeFreqs[theme] || 60;

    osc.connect(gain);
    gain.connect(SFX.masterGain);

    osc.start(now);
    SFX.ambientSource = osc;
};

SFX.stopAmbient = function() {
    if (SFX.ambientSource) {
        SFX.ambientSource.stop();
        SFX.ambientSource = null;
    }
};
