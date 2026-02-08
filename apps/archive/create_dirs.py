#!/usr/bin/env python3
import os

base = os.path.dirname(os.path.abspath(__file__))
dirs = ['color-theory-lab', 'math-visualizer', 'ragdoll-physics']

for d in dirs:
    path = os.path.join(base, d)
    os.makedirs(path, exist_ok=True)
    print(f"Created: {path}")

print("Done!")
