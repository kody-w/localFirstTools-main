#!/usr/bin/env python3
"""
cartridge-build.py -- Compile cartridge source directories into cartridge JSON.

Takes a source directory containing a cartridge.json manifest and separate .js
game files, and compiles them into a single cartridge JSON file compatible with
the ECS console emulator.

Usage:
  python3 scripts/cartridge-build.py cartridges/cell-to-civ/
  python3 scripts/cartridge-build.py cartridges/cell-to-civ/ --output apps/games-puzzles/cartridges/
  python3 scripts/cartridge-build.py --all                    # Build all source dirs
  python3 scripts/cartridge-build.py --list                   # List buildable cartridges
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CARTRIDGES_SRC = ROOT / "cartridges"
CARTRIDGES_OUT = ROOT / "apps" / "games-puzzles" / "cartridges"


def strip_js(code):
    """Strip comments and collapse whitespace for cartridge code field."""
    # Remove single-line comments (but not URLs with //)
    code = re.sub(r'(?<!:)//[^\n]*', '', code)
    # Remove multi-line comments
    code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
    # Collapse multiple newlines into single newline
    code = re.sub(r'\n\s*\n', '\n', code)
    # Strip leading/trailing whitespace per line
    lines = [line.strip() for line in code.split('\n') if line.strip()]
    return '\n'.join(lines)


def load_game_code(src_dir, game):
    """Load game code from either inline 'code' or external 'src' files."""
    if "code" in game and game["code"]:
        return game["code"]

    if "src" not in game:
        raise ValueError(f"Game '{game.get('id', '?')}' has neither 'code' nor 'src'")

    src = game["src"]

    # src can be a single file or a list of files to concatenate
    if isinstance(src, str):
        files = [src]
    else:
        files = src

    parts = []
    for f in files:
        path = src_dir / f
        if not path.exists():
            raise FileNotFoundError(f"Source file not found: {path}")
        parts.append(path.read_text(encoding="utf-8"))

    combined = '\n'.join(parts)
    return strip_js(combined)


def build_cartridge(src_dir, output_dir=None):
    """Build a single cartridge from its source directory."""
    src_dir = Path(src_dir)
    output_dir = Path(output_dir) if output_dir else CARTRIDGES_OUT

    manifest_path = src_dir / "cartridge.json"
    if not manifest_path.exists():
        print(f"ERROR: No cartridge.json found in {src_dir}")
        return False

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    console_id = manifest.get("console", src_dir.name)

    print(f"Building: {manifest.get('name', console_id)}")

    # Process each game
    for i, game in enumerate(manifest.get("games", [])):
        game_id = game.get("id", f"game-{i}")
        try:
            code = load_game_code(src_dir, game)
            game["code"] = code
            # Remove src field from output
            game.pop("src", None)
            print(f"  ✓ {game_id}: {len(code)} chars")
        except (FileNotFoundError, ValueError) as e:
            print(f"  ✗ {game_id}: {e}")
            return False

    # Write output
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{console_id}.json"
    output_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"  → {output_path} ({output_path.stat().st_size:,} bytes)")
    return True


def find_source_dirs():
    """Find all cartridge source directories (dirs containing cartridge.json)."""
    dirs = []
    for p in CARTRIDGES_SRC.iterdir():
        if p.is_dir() and (p / "cartridge.json").exists():
            dirs.append(p)
    return sorted(dirs)


def main():
    args = sys.argv[1:]

    if "--list" in args:
        dirs = find_source_dirs()
        if not dirs:
            print("No buildable cartridge source directories found.")
        for d in dirs:
            manifest = json.loads((d / "cartridge.json").read_text())
            games = len(manifest.get("games", []))
            print(f"  {d.name}/  ({manifest.get('name', '?')}, {games} games)")
        return 0

    if "--all" in args:
        dirs = find_source_dirs()
        if not dirs:
            print("No buildable cartridge source directories found.")
            return 1
        ok = all(build_cartridge(d) for d in dirs)
        return 0 if ok else 1

    # Parse --output
    output_dir = None
    if "--output" in args:
        idx = args.index("--output")
        if idx + 1 < len(args):
            output_dir = args[idx + 1]
            args = [a for a in args if a != "--output" and a != output_dir]

    positional = [a for a in args if not a.startswith("--")]
    if not positional:
        print("Usage: cartridge-build.py <source-dir> [--output <dir>]")
        print("       cartridge-build.py --all")
        print("       cartridge-build.py --list")
        return 1

    src_dir = Path(positional[0])
    if not src_dir.is_absolute():
        src_dir = ROOT / src_dir

    ok = build_cartridge(src_dir, output_dir)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
