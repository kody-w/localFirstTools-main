#!/usr/bin/env python3
"""
Setup script to create archive directories and copy files.
"""
import os
import shutil
from pathlib import Path

def main():
    base_path = Path("/Users/kodyw/Projects/localFirstTools-main")
    source_dir = base_path / "apps" / "experimental-ai"
    archive_dir = base_path / "apps" / "archive"
    
    files_to_copy = [
        ("text-to-speech-choir.html", "text-to-speech-choir", "v1.html"),
        ("picasso-bowl.html", "picasso-bowl", "v1.html"),
        ("neuai-installer-wizard.html", "neuai-installer-wizard", "v1.html"),
    ]
    
    print("Creating directories and copying files...\n")
    
    for source_file, dest_subdir, dest_filename in files_to_copy:
        # Create destination directory
        dest_path = archive_dir / dest_subdir
        dest_path.mkdir(parents=True, exist_ok=True)
        
        # Copy file
        source_full_path = source_dir / source_file
        dest_full_path = dest_path / dest_filename
        
        if source_full_path.exists():
            shutil.copy2(source_full_path, dest_full_path)
            print(f"✓ Copied: {source_file} → {dest_subdir}/{dest_filename}")
        else:
            print(f"✗ Source not found: {source_file}")
    
    # Verification
    print("\n=== Verification ===")
    for source_file, dest_subdir, dest_filename in files_to_copy:
        dest_full_path = archive_dir / dest_subdir / dest_filename
        if dest_full_path.exists():
            size = dest_full_path.stat().st_size
            size_kb = size / 1024
            print(f"✓ {dest_subdir}/{dest_filename} ({size_kb:.1f} KB, {size} bytes)")
        else:
            print(f"✗ {dest_subdir}/{dest_filename} NOT FOUND")

if __name__ == "__main__":
    main()
