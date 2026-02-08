#!/usr/bin/env node
const fs = require('fs');
const path = require('path');

const basePath = '/Users/kodyw/Projects/localFirstTools-main';
process.chdir(basePath);

// Create directories
const dirs = [
    'apps/archive/thought-cascade',
    'apps/archive/ferrofluid-wordsmith',
    'apps/archive/smoke-words'
];

dirs.forEach(d => {
    fs.mkdirSync(d, { recursive: true });
    console.log(`Created: ${d}`);
});

// Copy files
const files = [
    {src: 'apps/generative-art/thought-cascade.html', dst: 'apps/archive/thought-cascade/v1.html'},
    {src: 'apps/generative-art/ferrofluid-wordsmith.html', dst: 'apps/archive/ferrofluid-wordsmith/v1.html'},
    {src: 'apps/generative-art/smoke-words.html', dst: 'apps/archive/smoke-words/v1.html'}
];

files.forEach(({src, dst}) => {
    if (fs.existsSync(src)) {
        fs.copyFileSync(src, dst);
        const stats = fs.statSync(dst);
        console.log(`${dst}: ${stats.size} bytes`);
    } else {
        console.log(`Source not found: ${src}`);
    }
});

console.log("\nFinal file sizes:");
files.forEach(({dst}) => {
    if (fs.existsSync(dst)) {
        const stats = fs.statSync(dst);
        console.log(`${dst}: ${stats.size} bytes`);
    }
});
