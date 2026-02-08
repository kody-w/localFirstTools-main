'use strict';

// =============================================================================
// UTILS.JS - Utility functions and helpers
// =============================================================================

const Util = {};

// =============================================================================
// RANDOM NUMBER GENERATION
// =============================================================================

// Seeded random using xorshift128
Util.seedState = { x: 123456789, y: 362436069, z: 521288629, w: 88675123 };

Util.seedRandom = function(seed) {
    if (seed === undefined) seed = Date.now();
    Util.seedState.x = seed || 123456789;
    Util.seedState.y = 362436069;
    Util.seedState.z = 521288629;
    Util.seedState.w = 88675123;

    return function() {
        const t = Util.seedState.x ^ (Util.seedState.x << 11);
        Util.seedState.x = Util.seedState.y;
        Util.seedState.y = Util.seedState.z;
        Util.seedState.z = Util.seedState.w;
        Util.seedState.w = Util.seedState.w ^ (Util.seedState.w >> 19) ^ (t ^ (t >> 8));
        return (Util.seedState.w >>> 0) / 4294967296;
    };
};

Util.randInt = function(min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
};

Util.randFloat = function(min, max) {
    return Math.random() * (max - min) + min;
};

Util.pick = function(array) {
    return array[Math.floor(Math.random() * array.length)];
};

Util.shuffle = function(array) {
    const arr = array.slice();
    for (let i = arr.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [arr[i], arr[j]] = [arr[j], arr[i]];
    }
    return arr;
};

Util.weightedPick = function(items, weights) {
    const total = weights.reduce((sum, w) => sum + w, 0);
    let rand = Math.random() * total;
    for (let i = 0; i < items.length; i++) {
        rand -= weights[i];
        if (rand <= 0) return items[i];
    }
    return items[items.length - 1];
};

// =============================================================================
// MATH UTILITIES
// =============================================================================

Util.clamp = function(val, min, max) {
    return Math.max(min, Math.min(max, val));
};

Util.lerp = function(a, b, t) {
    return a + (b - a) * t;
};

Util.lerpAngle = function(a, b, t) {
    const diff = ((b - a + Math.PI) % (Math.PI * 2)) - Math.PI;
    return a + diff * t;
};

Util.smoothStep = function(edge0, edge1, x) {
    const t = Util.clamp((x - edge0) / (edge1 - edge0), 0, 1);
    return t * t * (3 - 2 * t);
};

Util.map = function(value, inMin, inMax, outMin, outMax) {
    return outMin + (outMax - outMin) * ((value - inMin) / (inMax - inMin));
};

// =============================================================================
// EASING FUNCTIONS
// =============================================================================

Util.easeOutQuad = function(t) {
    return t * (2 - t);
};

Util.easeInQuad = function(t) {
    return t * t;
};

Util.easeInOutCubic = function(t) {
    return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
};

Util.easeOutElastic = function(t) {
    const c4 = (2 * Math.PI) / 3;
    return t === 0 ? 0 : t === 1 ? 1 : Math.pow(2, -10 * t) * Math.sin((t * 10 - 0.75) * c4) + 1;
};

Util.easeOutBounce = function(t) {
    const n1 = 7.5625;
    const d1 = 2.75;
    if (t < 1 / d1) {
        return n1 * t * t;
    } else if (t < 2 / d1) {
        return n1 * (t -= 1.5 / d1) * t + 0.75;
    } else if (t < 2.5 / d1) {
        return n1 * (t -= 2.25 / d1) * t + 0.9375;
    } else {
        return n1 * (t -= 2.625 / d1) * t + 0.984375;
    }
};

// =============================================================================
// GEOMETRY & SPATIAL
// =============================================================================

Util.dist = function(x1, y1, x2, y2) {
    const dx = x2 - x1;
    const dy = y2 - y1;
    return Math.sqrt(dx * dx + dy * dy);
};

Util.distSq = function(x1, y1, x2, y2) {
    const dx = x2 - x1;
    const dy = y2 - y1;
    return dx * dx + dy * dy;
};

Util.angle = function(x1, y1, x2, y2) {
    return Math.atan2(y2 - y1, x2 - x1);
};

Util.pointInRect = function(px, py, rx, ry, rw, rh) {
    return px >= rx && px <= rx + rw && py >= ry && py <= ry + rh;
};

Util.rectsOverlap = function(a, b) {
    return !(a.x + a.w < b.x || b.x + b.w < a.x || a.y + a.h < b.y || b.y + b.h < a.y);
};

Util.circlesOverlap = function(x1, y1, r1, x2, y2, r2) {
    const distSq = Util.distSq(x1, y1, x2, y2);
    const radSum = r1 + r2;
    return distSq < radSum * radSum;
};

Util.lineIntersectsRect = function(x1, y1, x2, y2, rx, ry, rw, rh) {
    // Liang-Barsky algorithm
    const dx = x2 - x1;
    const dy = y2 - y1;
    let t0 = 0, t1 = 1;

    const clipT = (p, q) => {
        if (p === 0) return q >= 0;
        const r = q / p;
        if (p < 0) {
            if (r > t1) return false;
            if (r > t0) t0 = r;
        } else {
            if (r < t0) return false;
            if (r < t1) t1 = r;
        }
        return true;
    };

    if (!clipT(-dx, x1 - rx)) return false;
    if (!clipT(dx, rx + rw - x1)) return false;
    if (!clipT(-dy, y1 - ry)) return false;
    if (!clipT(dy, ry + rh - y1)) return false;

    return true;
};

// =============================================================================
// SMOOTH CAMERA FOLLOW (smoothDamp with delta time)
// =============================================================================

Util.smoothDamp = function(current, target, velocity, smoothTime, dt, maxSpeed = Infinity) {
    smoothTime = Math.max(0.0001, smoothTime);
    const omega = 2 / smoothTime;
    const x = omega * dt;
    const exp = 1 / (1 + x + 0.48 * x * x + 0.235 * x * x * x);
    let change = current - target;
    const originalTo = target;
    const maxChange = maxSpeed * smoothTime;
    change = Util.clamp(change, -maxChange, maxChange);
    target = current - change;
    const temp = (velocity.val + omega * change) * dt;
    velocity.val = (velocity.val - omega * temp) * exp;
    let output = target + (change + temp) * exp;

    if ((originalTo - current > 0) === (output > originalTo)) {
        output = originalTo;
        velocity.val = (output - originalTo) / dt;
    }

    return output;
};

// =============================================================================
// COLOR UTILITIES
// =============================================================================

Util.hslToRgb = function(h, s, l) {
    h = h % 360;
    s = Util.clamp(s, 0, 1);
    l = Util.clamp(l, 0, 1);

    const c = (1 - Math.abs(2 * l - 1)) * s;
    const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
    const m = l - c / 2;

    let r = 0, g = 0, b = 0;

    if (h < 60) { r = c; g = x; b = 0; }
    else if (h < 120) { r = x; g = c; b = 0; }
    else if (h < 180) { r = 0; g = c; b = x; }
    else if (h < 240) { r = 0; g = x; b = c; }
    else if (h < 300) { r = x; g = 0; b = c; }
    else { r = c; g = 0; b = x; }

    return [
        Math.round((r + m) * 255),
        Math.round((g + m) * 255),
        Math.round((b + m) * 255)
    ];
};

Util.rgba = function(r, g, b, a = 1) {
    return `rgba(${r},${g},${b},${a})`;
};

Util.hexToRgb = function(hex) {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result ? {
        r: parseInt(result[1], 16),
        g: parseInt(result[2], 16),
        b: parseInt(result[3], 16)
    } : null;
};

Util.lerpColor = function(color1, color2, t) {
    const c1 = Util.hexToRgb(color1);
    const c2 = Util.hexToRgb(color2);
    if (!c1 || !c2) return color1;

    const r = Math.round(Util.lerp(c1.r, c2.r, t));
    const g = Math.round(Util.lerp(c1.g, c2.g, t));
    const b = Math.round(Util.lerp(c1.b, c2.b, t));

    return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
};

// =============================================================================
// STRING & FORMATTING
// =============================================================================

Util.formatTime = function(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
};

Util.formatNumber = function(num) {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toString();
};

Util.capitalize = function(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
};

// =============================================================================
// MISC UTILITIES
// =============================================================================

Util.deepCopy = function(obj) {
    return JSON.parse(JSON.stringify(obj));
};

Util.debounce = function(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
};

Util.uuid = function() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
};
