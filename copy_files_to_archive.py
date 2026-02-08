#!/usr/bin/env python3
import os
import shutil

base_path = '/Users/kodyw/Projects/localFirstTools-main'
os.chdir(base_path)

# Create directories
dirs = [
    'apps/archive/thought-cascade',
    'apps/archive/ferrofluid-wordsmith',
    'apps/archive/smoke-words'
]

for d in dirs:
    os.makedirs(d, exist_ok=True)
    print(f'Created: {d}')

# Copy files
files = [
    ('apps/generative-art/thought-cascade.html', 'apps/archive/thought-cascade/v1.html'),
    ('apps/generative-art/ferrofluid-wordsmith.html', 'apps/archive/ferrofluid-wordsmith/v1.html'),
    ('apps/generative-art/smoke-words.html', 'apps/archive/smoke-words/v1.html')
]

for src, dst in files:
    if os.path.exists(src):
        shutil.copy2(src, dst)
        size = os.path.getsize(dst)
        print(f'{dst}: {size} bytes')
    else:
        print(f'Source not found: {src}')

print("\nFile sizes:")
for _, dst in files:
    if os.path.exists(dst):
        size = os.path.getsize(dst)
        print(f"{dst}: {size} bytes")
