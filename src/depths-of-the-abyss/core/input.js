'use strict';

// =============================================================================
// INPUT.JS - Unified input system (keyboard, mouse, touch, gamepad)
// =============================================================================

const Input = {
    keys: {},
    prevKeys: {},
    mouse: { x: 0, y: 0, down: false, justDown: false, button: 0 },
    prevMouse: { down: false },
    touch: { active: false, x: 0, y: 0, dx: 0, dy: 0, startX: 0, startY: 0, id: null },
    gamepad: { connected: false, axes: [0, 0, 0, 0], buttons: [] },
    canvas: null,
    initialized: false
};

// =============================================================================
// INITIALIZATION
// =============================================================================

Input.init = function(canvas) {
    if (Input.initialized) return;

    Input.canvas = canvas;

    // Keyboard events
    window.addEventListener('keydown', Input.onKeyDown, false);
    window.addEventListener('keyup', Input.onKeyUp, false);

    // Mouse events
    canvas.addEventListener('mousedown', Input.onMouseDown, false);
    canvas.addEventListener('mouseup', Input.onMouseUp, false);
    canvas.addEventListener('mousemove', Input.onMouseMove, false);
    canvas.addEventListener('contextmenu', e => e.preventDefault(), false);

    // Touch events
    canvas.addEventListener('touchstart', Input.onTouchStart, false);
    canvas.addEventListener('touchmove', Input.onTouchMove, false);
    canvas.addEventListener('touchend', Input.onTouchEnd, false);
    canvas.addEventListener('touchcancel', Input.onTouchEnd, false);

    // Gamepad events
    window.addEventListener('gamepadconnected', Input.onGamepadConnected, false);
    window.addEventListener('gamepaddisconnected', Input.onGamepadDisconnected, false);

    Input.initialized = true;
    console.log('Input system initialized');
};

// =============================================================================
// KEYBOARD HANDLERS
// =============================================================================

Input.onKeyDown = function(e) {
    const key = e.key.toLowerCase();
    Input.keys[key] = true;

    // Prevent default for game keys
    const preventKeys = ['arrowup', 'arrowdown', 'arrowleft', 'arrowright', ' ', 'w', 'a', 's', 'd'];
    if (preventKeys.includes(key)) {
        e.preventDefault();
    }
};

Input.onKeyUp = function(e) {
    const key = e.key.toLowerCase();
    Input.keys[key] = false;
};

Input.isKeyPressed = function(key) {
    return Input.keys[key.toLowerCase()] || false;
};

Input.justPressed = function(key) {
    key = key.toLowerCase();
    return Input.keys[key] && !Input.prevKeys[key];
};

Input.justReleased = function(key) {
    key = key.toLowerCase();
    return !Input.keys[key] && Input.prevKeys[key];
};

// =============================================================================
// MOUSE HANDLERS
// =============================================================================

Input.onMouseDown = function(e) {
    Input.mouse.down = true;
    Input.mouse.button = e.button;
    Input.updateMousePosition(e);
};

Input.onMouseUp = function(e) {
    Input.mouse.down = false;
};

Input.onMouseMove = function(e) {
    Input.updateMousePosition(e);
};

Input.updateMousePosition = function(e) {
    const rect = Input.canvas.getBoundingClientRect();
    const scaleX = Input.canvas.width / rect.width;
    const scaleY = Input.canvas.height / rect.height;

    Input.mouse.x = (e.clientX - rect.left) * scaleX;
    Input.mouse.y = (e.clientY - rect.top) * scaleY;
};

// =============================================================================
// TOUCH HANDLERS
// =============================================================================

Input.onTouchStart = function(e) {
    e.preventDefault();

    if (e.touches.length > 0) {
        const touch = e.touches[0];
        Input.touch.active = true;
        Input.touch.id = touch.identifier;

        const rect = Input.canvas.getBoundingClientRect();
        const scaleX = Input.canvas.width / rect.width;
        const scaleY = Input.canvas.height / rect.height;

        Input.touch.x = (touch.clientX - rect.left) * scaleX;
        Input.touch.y = (touch.clientY - rect.top) * scaleY;
        Input.touch.startX = Input.touch.x;
        Input.touch.startY = Input.touch.y;
        Input.touch.dx = 0;
        Input.touch.dy = 0;
    }
};

Input.onTouchMove = function(e) {
    e.preventDefault();

    if (!Input.touch.active) return;

    for (let i = 0; i < e.touches.length; i++) {
        const touch = e.touches[i];
        if (touch.identifier === Input.touch.id) {
            const rect = Input.canvas.getBoundingClientRect();
            const scaleX = Input.canvas.width / rect.width;
            const scaleY = Input.canvas.height / rect.height;

            const newX = (touch.clientX - rect.left) * scaleX;
            const newY = (touch.clientY - rect.top) * scaleY;

            Input.touch.dx = newX - Input.touch.x;
            Input.touch.dy = newY - Input.touch.y;
            Input.touch.x = newX;
            Input.touch.y = newY;
            break;
        }
    }
};

Input.onTouchEnd = function(e) {
    e.preventDefault();

    // Check if our tracked touch ended
    let touchEnded = true;
    for (let i = 0; i < e.touches.length; i++) {
        if (e.touches[i].identifier === Input.touch.id) {
            touchEnded = false;
            break;
        }
    }

    if (touchEnded) {
        Input.touch.active = false;
        Input.touch.dx = 0;
        Input.touch.dy = 0;
        Input.touch.id = null;
    }
};

// =============================================================================
// GAMEPAD HANDLERS
// =============================================================================

Input.onGamepadConnected = function(e) {
    console.log('Gamepad connected:', e.gamepad.id);
    Input.gamepad.connected = true;
};

Input.onGamepadDisconnected = function(e) {
    console.log('Gamepad disconnected');
    Input.gamepad.connected = false;
};

Input.pollGamepad = function() {
    const gamepads = navigator.getGamepads ? navigator.getGamepads() : [];

    for (let i = 0; i < gamepads.length; i++) {
        const gp = gamepads[i];
        if (gp && gp.connected) {
            Input.gamepad.connected = true;
            Input.gamepad.axes = Array.from(gp.axes);
            Input.gamepad.buttons = gp.buttons.map(b => ({
                pressed: b.pressed,
                value: b.value
            }));
            return;
        }
    }

    Input.gamepad.connected = false;
};

// =============================================================================
// UNIFIED INPUT QUERIES
// =============================================================================

Input.getMovement = function() {
    let dx = 0;
    let dy = 0;

    // Keyboard - WASD
    if (Input.isKeyPressed('w') || Input.isKeyPressed('arrowup')) dy -= 1;
    if (Input.isKeyPressed('s') || Input.isKeyPressed('arrowdown')) dy += 1;
    if (Input.isKeyPressed('a') || Input.isKeyPressed('arrowleft')) dx -= 1;
    if (Input.isKeyPressed('d') || Input.isKeyPressed('arrowright')) dx += 1;

    // Gamepad left stick
    if (Input.gamepad.connected && Input.gamepad.axes.length >= 2) {
        const deadzone = 0.15;
        const axisX = Math.abs(Input.gamepad.axes[0]) > deadzone ? Input.gamepad.axes[0] : 0;
        const axisY = Math.abs(Input.gamepad.axes[1]) > deadzone ? Input.gamepad.axes[1] : 0;

        dx += axisX;
        dy += axisY;
    }

    // Touch virtual d-pad (bottom-left quadrant)
    if (Input.touch.active && Input.canvas) {
        const touchInDPad = Input.getTouchDPad();
        if (touchInDPad) {
            dx += touchInDPad.dx;
            dy += touchInDPad.dy;
        }
    }

    // Normalize diagonal movement
    const mag = Math.sqrt(dx * dx + dy * dy);
    if (mag > 1) {
        dx /= mag;
        dy /= mag;
    }

    return { dx, dy };
};

Input.getTouchDPad = function() {
    if (!Input.touch.active || !Input.canvas) return null;

    const canvasWidth = Input.canvas.width;
    const canvasHeight = Input.canvas.height;

    // D-pad area: bottom-left quarter
    const dpadSize = Math.min(canvasWidth, canvasHeight) * 0.3;
    const dpadCenterX = dpadSize * 0.5;
    const dpadCenterY = canvasHeight - dpadSize * 0.5;

    const distX = Input.touch.x - dpadCenterX;
    const distY = Input.touch.y - dpadCenterY;
    const dist = Math.sqrt(distX * distX + distY * distY);

    // Check if touch is in d-pad area
    if (dist > dpadSize * 0.6) return null;

    // Calculate direction
    const angle = Math.atan2(distY, distX);
    const dx = Math.cos(angle);
    const dy = Math.sin(angle);

    return { dx, dy };
};

Input.getAim = function() {
    // Mouse aim (world space requires camera offset, handled by caller)
    if (Input.mouse.x !== 0 || Input.mouse.y !== 0) {
        return { x: Input.mouse.x, y: Input.mouse.y, type: 'mouse' };
    }

    // Gamepad right stick
    if (Input.gamepad.connected && Input.gamepad.axes.length >= 4) {
        const deadzone = 0.2;
        const axisX = Math.abs(Input.gamepad.axes[2]) > deadzone ? Input.gamepad.axes[2] : 0;
        const axisY = Math.abs(Input.gamepad.axes[3]) > deadzone ? Input.gamepad.axes[3] : 0;

        if (axisX !== 0 || axisY !== 0) {
            return { x: axisX, y: axisY, type: 'gamepad' };
        }
    }

    // Touch aim (right side of screen)
    if (Input.touch.active && Input.canvas) {
        const canvasWidth = Input.canvas.width;
        if (Input.touch.x > canvasWidth * 0.5) {
            return { x: Input.touch.x, y: Input.touch.y, type: 'touch' };
        }
    }

    return null;
};

// Action buttons (space, shift, buttons)
Input.isActionPressed = function(action) {
    switch (action) {
        case 'attack':
            return Input.isKeyPressed(' ') || Input.isKeyPressed('j') ||
                   Input.mouse.down ||
                   (Input.gamepad.connected && Input.gamepad.buttons[0] && Input.gamepad.buttons[0].pressed) ||
                   Input.getTouchActionButton('attack');

        case 'dodge':
            return Input.isKeyPressed('shift') || Input.isKeyPressed('k') ||
                   (Input.gamepad.connected && Input.gamepad.buttons[1] && Input.gamepad.buttons[1].pressed) ||
                   Input.getTouchActionButton('dodge');

        case 'interact':
            return Input.isKeyPressed('e') || Input.isKeyPressed('enter') ||
                   (Input.gamepad.connected && Input.gamepad.buttons[2] && Input.gamepad.buttons[2].pressed) ||
                   Input.getTouchActionButton('interact');

        case 'inventory':
            return Input.justPressed('i') || Input.justPressed('tab') ||
                   (Input.gamepad.connected && Input.gamepad.buttons[9] && Input.gamepad.buttons[9].pressed);

        case 'pause':
            return Input.justPressed('escape') || Input.justPressed('p') ||
                   (Input.gamepad.connected && Input.gamepad.buttons[9] && Input.gamepad.buttons[9].pressed);

        default:
            return false;
    }
};

Input.getTouchActionButton = function(action) {
    if (!Input.touch.active || !Input.canvas) return false;

    const canvasWidth = Input.canvas.width;
    const canvasHeight = Input.canvas.height;

    // Action buttons: bottom-right corner
    const buttonSize = Math.min(canvasWidth, canvasHeight) * 0.12;
    const buttonSpacing = buttonSize * 1.3;

    const buttons = {
        attack: { x: canvasWidth - buttonSize * 1.5, y: canvasHeight - buttonSize * 1.5 },
        dodge: { x: canvasWidth - buttonSize * 1.5 - buttonSpacing, y: canvasHeight - buttonSize * 1.5 },
        interact: { x: canvasWidth - buttonSize * 1.5, y: canvasHeight - buttonSize * 1.5 - buttonSpacing }
    };

    const btn = buttons[action];
    if (!btn) return false;

    const dx = Input.touch.x - btn.x;
    const dy = Input.touch.y - btn.y;
    const dist = Math.sqrt(dx * dx + dy * dy);

    return dist < buttonSize;
};

// =============================================================================
// UPDATE (called each frame)
// =============================================================================

Input.update = function() {
    // Update previous key states
    Input.prevKeys = {};
    for (const key in Input.keys) {
        Input.prevKeys[key] = Input.keys[key];
    }

    // Update previous mouse state
    Input.prevMouse.down = Input.mouse.down;
    Input.mouse.justDown = Input.mouse.down && !Input.prevMouse.down;

    // Poll gamepad
    if (navigator.getGamepads) {
        Input.pollGamepad();
    }

    // Reset touch delta if not moving
    if (Input.touch.active) {
        Input.touch.dx *= 0.8;
        Input.touch.dy *= 0.8;
    }
};

// =============================================================================
// UTILITIES
// =============================================================================

Input.clearAll = function() {
    Input.keys = {};
    Input.prevKeys = {};
    Input.mouse.down = false;
    Input.mouse.justDown = false;
    Input.touch.active = false;
};

Input.isAnyKeyPressed = function() {
    for (const key in Input.keys) {
        if (Input.keys[key]) return true;
    }
    return Input.mouse.down || Input.touch.active || (Input.gamepad.connected && Input.gamepad.buttons.some(b => b.pressed));
};
