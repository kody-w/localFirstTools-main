#!/usr/bin/env python3
import os, shutil
base = os.path.dirname(os.path.abspath(__file__))
dirs = ['text-to-speech-choir', 'picasso-bowl', 'neuai-installer-wizard']
for d in dirs:
    os.makedirs(os.path.join(base, d), exist_ok=True)
src_dir = os.path.join(os.path.dirname(base), 'experimental-ai')
copies = [
    ('text-to-speech-choir.html', 'text-to-speech-choir/v1.html'),
    ('picasso-bowl.html', 'picasso-bowl/v1.html'),
    ('neuai-installer-wizard.html', 'neuai-installer-wizard/v1.html'),
]
for src, dst in copies:
    shutil.copy2(os.path.join(src_dir, src), os.path.join(base, dst))
    print(f"Copied {src} -> {dst}")
print("Done!")
