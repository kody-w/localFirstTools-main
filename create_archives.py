#!/usr/bin/env python3
"""
Archive setup script to create directories and copy files for archiving.
"""

import os
import shutil
from pathlib import Path

def main():
    base_path = Path("/Users/kodyw/Projects/localFirstTools-main")
    archive_base = base_path / "apps" / "archive"
    
    # Create directories
    dirs = [
        "markdown-editor-live",
        "circuit-simulator", 
        "cylinder-composer"
    ]
    
    print("Creating archive directories...")
    for dir_name in dirs:
        dir_path = archive_base / dir_name
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"✓ Created: {dir_path}")
    
    # Copy files
    files_to_copy = [
        ("apps/creative-tools/markdown-editor-live.html", "apps/archive/markdown-editor-live/v1.html"),
        ("apps/creative-tools/circuit-simulator.html", "apps/archive/circuit-simulator/v1.html"),
        ("apps/audio-music/cylinder-composer.html", "apps/archive/cylinder-composer/v1.html")
    ]
    
    print("\nCopying files...")
    for src, dst in files_to_copy:
        src_path = base_path / src
        dst_path = base_path / dst
        if src_path.exists():
            shutil.copy2(src_path, dst_path)
            print(f"✓ Copied: {src} -> {dst}")
        else:
            print(f"✗ ERROR: Source file not found: {src_path}")
            return False
    
    print("\n" + "="*60)
    print("Archives created successfully!")
    print("="*60)
    
    print("\nVerifying files:")
    for dir_name in dirs:
        dir_path = archive_base / dir_name
        files = list(dir_path.glob("*"))
        print(f"\n{dir_path}:")
        for file_path in files:
            if file_path.is_file():
                size = file_path.stat().st_size
                print(f"  - {file_path.name} ({size:,} bytes)")
    
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
