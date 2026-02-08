#!/usr/bin/env python3
import os
import shutil

# Change to the working directory
os.chdir('/Users/kodyw/Projects/localFirstTools-main')

# Step 1: Create directories
dirs = [
    'apps/archive/thought-cascade',
    'apps/archive/ferrofluid-wordsmith',
    'apps/archive/smoke-words'
]

for d in dirs:
    os.makedirs(d, exist_ok=True)
    print(f'✓ Created directory: {d}')

# Step 2: Copy files
files = [
    ('apps/generative-art/thought-cascade.html', 'apps/archive/thought-cascade/v1.html'),
    ('apps/generative-art/ferrofluid-wordsmith.html', 'apps/archive/ferrofluid-wordsmith/v1.html'),
    ('apps/generative-art/smoke-words.html', 'apps/archive/smoke-words/v1.html')
]

for src, dst in files:
    shutil.copy2(src, dst)
    print(f'✓ Copied {src} → {dst}')

# Step 3: Verify all files exist
print('\n=== VERIFICATION ===')
for _, dst in files:
    if os.path.exists(dst):
        size = os.path.getsize(dst)
        print(f'✓ {dst} exists (size: {size} bytes)')
    else:
        print(f'✗ {dst} MISSING')

print('\nAll archive files created successfully!')
