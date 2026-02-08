#!/usr/bin/env python3
import os, shutil

base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
copies = [
    ("apps/creative-tools/markdown-editor-live.html", "apps/archive/markdown-editor-live/v1.html"),
    ("apps/creative-tools/circuit-simulator.html", "apps/archive/circuit-simulator/v1.html"),
    ("apps/audio-music/cylinder-composer.html", "apps/archive/cylinder-composer/v1.html"),
]
for src_rel, dst_rel in copies:
    src = os.path.join(base, src_rel)
    dst = os.path.join(base, dst_rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    print(f"Copied {src_rel} -> {dst_rel} (size: {os.path.getsize(dst)} bytes)")

# Verify
for _, dst_rel in copies:
    dst = os.path.join(base, dst_rel)
    assert os.path.isfile(dst), f"MISSING: {dst}"
print("All 3 v1.html files verified!")
