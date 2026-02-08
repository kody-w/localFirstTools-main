#!/usr/bin/env python3
import os
import shutil

os.chdir('/Users/kodyw/Projects/localFirstTools-main')

# Create directories
dirs = [
    'apps/archive/thought-cascade',
    'apps/archive/ferrofluid-wordsmith',
    'apps/archive/smoke-words'
]

for d in dirs:
    os.makedirs(d, exist_ok=True)
    print(f"Created directory: {d}")

# Copy files
files = [
    ('apps/generative-art/thought-cascade.html', 'apps/archive/thought-cascade/v1.html'),
    ('apps/generative-art/ferrofluid-wordsmith.html', 'apps/archive/ferrofluid-wordsmith/v1.html'),
    ('apps/generative-art/smoke-words.html', 'apps/archive/smoke-words/v1.html')
]

for src, dst in files:
    if os.path.exists(src):
        shutil.copy2(src, dst)
        print(f"Copied: {src} -> {dst}")
    else:
        print(f"ERROR: Source file not found: {src}")

# Verify
print("\nVerification:")
for _, dst in files:
    if os.path.exists(dst):
        size = os.path.getsize(dst)
        print(f'✓ {dst} exists ({size} bytes)')
    else:
        print(f'✗ {dst} NOT FOUND')
