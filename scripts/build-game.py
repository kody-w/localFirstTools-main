#!/usr/bin/env python3
"""build-game.py -- Compile modular game source into a single HTML file.

Reads a build.json manifest from a source directory, concatenates CSS and JS
modules in dependency order, injects them into an HTML shell template, validates
the output, and writes a single self-contained HTML file.

Usage:
    python3 scripts/build-game.py src/<game>/              # Build game
    python3 scripts/build-game.py src/<game>/ --manifest    # Build + update manifest.json
    python3 scripts/build-game.py src/<game>/ --dry-run     # Validate without writing
    python3 scripts/build-game.py src/<game>/ --verbose     # Show module details
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APPS_DIR = ROOT / "apps"
MANIFEST = APPS_DIR / "manifest.json"


def load_build_config(src_dir):
    """Load build.json from source directory."""
    config_path = src_dir / "build.json"
    if not config_path.exists():
        print(f"ERROR: No build.json found in {src_dir}")
        sys.exit(1)
    return json.loads(config_path.read_text(encoding="utf-8"))


def read_module(src_dir, filepath):
    """Read a single module file relative to src_dir."""
    full_path = src_dir / filepath
    if not full_path.exists():
        print(f"ERROR: Module not found: {full_path}")
        sys.exit(1)
    return full_path.read_text(encoding="utf-8")


def build_css(src_dir, css_files, verbose=False):
    """Concatenate CSS modules."""
    parts = []
    for f in css_files:
        content = read_module(src_dir, f)
        if verbose:
            print(f"  CSS: {f} ({len(content):,} chars)")
        parts.append(f"/* === {f} === */")
        parts.append(content)
    return "\n".join(parts)


def build_js(src_dir, js_files, verbose=False):
    """Concatenate JS modules in dependency order."""
    parts = []
    for f in js_files:
        content = read_module(src_dir, f)
        if verbose:
            lines = content.count("\n") + 1
            print(f"  JS:  {f} ({lines} lines, {len(content):,} chars)")
        parts.append(f"// === {f} ===")
        parts.append(content)
    return "\n".join(parts)


def validate_output(content):
    """Validate the compiled HTML meets all app requirements."""
    errors = []
    warnings = []

    # Required structural elements
    if "<!DOCTYPE html>" not in content and "<!doctype html>" not in content:
        errors.append("Missing <!DOCTYPE html>")
    if '<meta name="viewport"' not in content:
        errors.append("Missing viewport meta tag")
    if "<title>" not in content:
        errors.append("Missing <title> tag")
    if "<canvas" not in content:
        warnings.append("No <canvas> element found")
    if "AudioContext" not in content and "webkitAudioContext" not in content:
        warnings.append("No AudioContext found")
    if "localStorage" not in content:
        warnings.append("No localStorage usage found")

    # Must not have external dependencies
    ext_refs = re.findall(r'(src|href)="(https?://[^"]+)"', content)
    for attr, url in ext_refs:
        errors.append(f"External dependency: {attr}=\"{url}\"")

    return errors, warnings


def build_game(src_dir, dry_run=False, verbose=False, update_manifest=False):
    """Build a single game from its source directory."""
    config = load_build_config(src_dir)

    name = config.get("name", src_dir.name)
    output_category = config["output"]["category"]
    output_file = config["output"]["file"]
    shell_path = config.get("shell", "shell.html")

    print(f"Building: {name}")

    # Read shell template
    shell = read_module(src_dir, shell_path)

    # Build CSS
    css_files = config.get("css", [])
    css_content = build_css(src_dir, css_files, verbose) if css_files else ""

    # Build JS
    js_files = config.get("js", [])
    js_content = build_js(src_dir, js_files, verbose) if js_files else ""

    # Inject into shell
    output = shell.replace("{{CSS}}", css_content).replace("{{JS}}", js_content)

    # Validate
    errors, warnings = validate_output(output)
    for e in errors:
        print(f"  ERROR: {e}")
    for w in warnings:
        if verbose:
            print(f"  WARN: {w}")

    if errors:
        print(f"  Build FAILED with {len(errors)} error(s)")
        return False

    # Stats
    lines = output.count("\n") + 1
    size_kb = len(output.encode("utf-8")) / 1024
    print(f"  Output: {lines:,} lines, {size_kb:.0f} KB")
    print(f"  Modules: {len(css_files)} CSS + {len(js_files)} JS = {len(css_files) + len(js_files)} total")

    if dry_run:
        print("  (dry-run, not writing)")
        return True

    # Write output
    # Map manifest category key to folder name
    folder_map = {
        "games_puzzles": "games-puzzles",
        "3d_immersive": "3d-immersive",
        "audio_music": "audio-music",
        "creative_tools": "creative-tools",
        "experimental_ai": "experimental-ai",
        "generative_art": "generative-art",
        "particle_physics": "particle-physics",
        "visual_art": "visual-art",
        "educational_tools": "educational",
    }
    folder = folder_map.get(output_category, output_category)
    out_dir = APPS_DIR / folder
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / output_file

    out_path.write_text(output, encoding="utf-8")
    print(f"  Wrote: {out_path}")

    # Update manifest if requested
    if update_manifest:
        manifest_entry = config.get("manifest", {})
        if manifest_entry:
            update_manifest_json(output_category, output_file, manifest_entry)

    return True


def update_manifest_json(category, filename, entry):
    """Add or update an entry in manifest.json."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    cats = manifest.get("categories", {})
    cat = cats.get(category, {"apps": []})
    apps = cat.get("apps", [])

    # Check if entry already exists
    existing = None
    for i, app in enumerate(apps):
        if app.get("file") == filename:
            existing = i
            break

    new_entry = {
        "title": entry.get("title", filename.replace(".html", "").replace("-", " ").title()),
        "file": filename,
        "description": entry.get("description", ""),
        "tags": entry.get("tags", []),
        "complexity": entry.get("complexity", "advanced"),
        "type": entry.get("type", "game"),
        "featured": entry.get("featured", False),
        "created": entry.get("created", "2026-02-07"),
    }

    if existing is not None:
        apps[existing] = new_entry
        print(f"  Updated manifest entry for {filename}")
    else:
        apps.append(new_entry)
        cat["count"] = len(apps)
        print(f"  Added manifest entry for {filename}")

    cat["apps"] = apps
    cats[category] = cat
    manifest["categories"] = cats

    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"  Manifest validated OK ({len(apps)} apps in {category})")


def main():
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    verbose = "--verbose" in args or "-v" in args
    update_manifest_flag = "--manifest" in args

    positional = [a for a in args if not a.startswith("--")]
    if not positional:
        print("Usage: build-game.py <source-dir> [--dry-run] [--manifest] [--verbose]")
        return 1

    src_dir = Path(positional[0])
    if not src_dir.is_absolute():
        src_dir = ROOT / src_dir

    ok = build_game(src_dir, dry_run=dry_run, verbose=verbose, update_manifest=update_manifest_flag)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
