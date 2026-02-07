#!/usr/bin/env python3
"""
autosort.py — Data-sloshing pipeline for localFirstTools-main

Catches HTML files dropped in root, analyzes content, renames garbage filenames,
categorizes by content, moves to apps/<category>/, and updates manifest.json.

Run manually:  python3 scripts/autosort.py
Run dry-run:   python3 scripts/autosort.py --dry-run
"""

import json
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APPS_DIR = ROOT / "apps"
MANIFEST_PATH = APPS_DIR / "manifest.json"

# Files that belong in root — never touch these
ROOT_WHITELIST = {
    "index.html",
    "README.md",
    "CLAUDE.md",
    "skills.md",
    ".gitignore",
    ".gitattributes",
}

# Garbage filenames that need renaming (single chars, numbers, generic names)
GARBAGE_NAMES = re.compile(
    r"^([a-z]|[0-9]+|new|test|temp|tmp|untitled|copy|downloaded|complete-implementation)\.html$",
    re.IGNORECASE,
)

# Category detection keywords (weighted)
CATEGORY_RULES = {
    "3d_immersive": {
        "folder": "3d-immersive",
        "signals": {
            "high": ["three.js", "THREE.", "WebGLRenderer", "PerspectiveCamera", "OrbitControls", "raycaster"],
            "medium": ["3d", "webgl", "glsl", "shader", "vertex", "fragment", "mesh", "geometry"],
            "low": ["rotate", "camera", "scene", "render3d"],
        },
    },
    "audio_music": {
        "folder": "audio-music",
        "signals": {
            "high": ["AudioContext", "OscillatorNode", "GainNode", "analyser", "createOscillator"],
            "medium": ["synthesizer", "synth", "midi", "drum", "beat", "sequencer", "daw", "bpm", "tempo"],
            "low": ["audio", "sound", "music", "frequency", "waveform", "note"],
        },
    },
    "games_puzzles": {
        "folder": "games-puzzles",
        "signals": {
            "high": ["game over", "score", "lives", "level", "player", "enemy", "collision"],
            "medium": ["puzzle", "card game", "board game", "solitaire", "chess", "battle", "rpg", "quest"],
            "low": ["game", "play", "win", "lose", "points", "health", "attack", "defense"],
        },
    },
    "visual_art": {
        "folder": "visual-art",
        "signals": {
            "high": ["getContext('2d')", "ctx.beginPath", "ctx.fillRect", "ctx.strokeStyle", "drawImage"],
            "medium": ["canvas", "drawing", "paint", "brush", "palette", "color picker", "sketch"],
            "low": ["visual", "art", "design", "creative", "draw", "pixel"],
        },
    },
    "generative_art": {
        "folder": "generative-art",
        "signals": {
            "high": ["perlin", "simplex", "noise", "L-system", "cellular automata", "voronoi"],
            "medium": ["fractal", "mandelbrot", "procedural", "generative", "algorithmic", "recursive pattern"],
            "low": ["generate", "random", "seed", "iterate", "evolve", "mutate"],
        },
    },
    "particle_physics": {
        "folder": "particle-physics",
        "signals": {
            "high": ["particles", "velocity", "acceleration", "gravity", "force", "collision detection"],
            "medium": ["physics", "simulation", "particle system", "n-body", "spring", "pendulum"],
            "low": ["mass", "momentum", "energy", "orbit", "wave"],
        },
    },
    "creative_tools": {
        "folder": "creative-tools",
        "signals": {
            "high": ["markdown", "editor", "converter", "calculator", "formatter", "validator"],
            "medium": ["tool", "utility", "productivity", "tracker", "manager", "planner", "builder"],
            "low": ["export", "import", "save", "load", "template", "workflow"],
        },
    },
    "educational_tools": {
        "folder": "educational",
        "signals": {
            "high": ["tutorial", "lesson", "quiz", "flashcard", "learn", "teach"],
            "medium": ["educational", "training", "practice", "exercise", "study"],
            "low": ["explain", "example", "guide", "reference"],
        },
    },
    "experimental_ai": {
        "folder": "experimental-ai",
        "signals": {
            "high": ["neural", "machine learning", "AI", "chatbot", "GPT", "LLM", "inference"],
            "medium": ["artificial intelligence", "model", "agent", "prompt", "embedding", "transformer"],
            "low": ["intelligent", "smart", "adaptive", "predict", "classify"],
        },
    },
}


class HeadExtractor(HTMLParser):
    """Extract title, description, and body text from HTML."""

    def __init__(self):
        super().__init__()
        self.title = ""
        self.description = ""
        self.in_title = False
        self.in_style = False
        self.in_script = False
        self.body_text = []
        self.meta_category = ""

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "title":
            self.in_title = True
        elif tag == "style":
            self.in_style = True
        elif tag == "script":
            self.in_script = True
        elif tag == "meta":
            name = attrs_dict.get("name", "").lower()
            content = attrs_dict.get("content", "")
            if name == "description":
                self.description = content
            elif name == "category":
                self.meta_category = content

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        elif tag == "style":
            self.in_style = False
        elif tag == "script":
            self.in_script = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        elif not self.in_style and not self.in_script:
            text = data.strip()
            if text:
                self.body_text.append(text)


def extract_metadata(filepath):
    """Read an HTML file and extract metadata."""
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None

    parser = HeadExtractor()
    try:
        parser.feed(content)
    except Exception:
        pass

    title = parser.title.strip()
    description = parser.description.strip()
    body_sample = " ".join(parser.body_text[:200])
    file_size = filepath.stat().st_size

    # Detect tags
    tags = []
    content_lower = content.lower()
    tag_checks = {
        "3d": ["three.js", "webgl", "3d"],
        "canvas": ["getcontext", "<canvas"],
        "svg": ["<svg", "createelementns"],
        "animation": ["requestanimationframe", "animation", "@keyframes"],
        "audio": ["audiocontext", "oscillator", "<audio"],
        "particles": ["particle", "emitter"],
        "physics": ["velocity", "gravity", "collision"],
        "interactive": ["addeventlistener", "onclick", "touch"],
        "game": ["score", "game over", "player", "level"],
        "ai": ["neural", "ai", "machine learning", "gpt"],
        "creative": ["draw", "paint", "brush", "palette"],
        "terminal": ["terminal", "console", "command"],
        "retro": ["retro", "pixel", "8-bit", "emulat"],
        "simulation": ["simulat", "ecosystem", "evolv"],
        "crm": ["crm", "salesforce", "dynamics"],
    }
    for tag, keywords in tag_checks.items():
        if any(kw in content_lower for kw in keywords):
            tags.append(tag)

    # Determine complexity
    if file_size > 50000 or "3d" in tags:
        complexity = "advanced"
    elif file_size > 20000:
        complexity = "intermediate"
    else:
        complexity = "simple"

    # Determine interaction type
    if "game" in tags:
        itype = "game"
    elif "audio" in tags:
        itype = "audio"
    elif "canvas" in tags or "svg" in tags:
        itype = "visual"
    elif "creative" in tags:
        itype = "drawing"
    else:
        itype = "interactive"

    return {
        "title": title,
        "description": description,
        "tags": tags[:6],
        "complexity": complexity,
        "type": itype,
        "content": content,
        "content_lower": content_lower,
        "body_sample": body_sample,
        "meta_category": parser.meta_category,
        "file_size": file_size,
    }


def categorize(meta):
    """Score content against category rules and return best match."""
    # If the app specifies its own category via meta tag, respect it
    if meta["meta_category"]:
        for cat_key in CATEGORY_RULES:
            if meta["meta_category"] in (cat_key, CATEGORY_RULES[cat_key]["folder"]):
                return cat_key

    content = meta["content_lower"]
    scores = {}

    for cat_key, rules in CATEGORY_RULES.items():
        score = 0
        for signal in rules["signals"].get("high", []):
            if signal.lower() in content:
                score += 10
        for signal in rules["signals"].get("medium", []):
            if signal.lower() in content:
                score += 4
        for signal in rules["signals"].get("low", []):
            if signal.lower() in content:
                score += 1
        scores[cat_key] = score

    best = max(scores, key=scores.get)
    # Always assign a real category — never uncategorized.
    # If nothing scored, default to experimental_ai as the broadest bucket.
    return best if scores[best] > 0 else "experimental_ai"


def slugify(text):
    """Convert text to a clean kebab-case filename slug."""
    text = text.lower().strip()
    # Remove common suffixes
    for suffix in [" - interactive", " - demo", " - app", " app", " tool", " game"]:
        if text.endswith(suffix.lower()):
            text = text[: -len(suffix)]
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    text = text.strip("-")
    return text[:60]  # cap length


def generate_filename(meta, original_name):
    """Generate a better filename from content if the original is garbage."""
    if not GARBAGE_NAMES.match(original_name):
        return original_name  # filename is fine

    # Try title first
    title = meta["title"]
    if title and len(title) > 3:
        slug = slugify(title)
        if slug and len(slug) > 3:
            return slug + ".html"

    # Try description
    desc = meta["description"]
    if desc and len(desc) > 5:
        # Take first few meaningful words
        words = re.findall(r"[a-z]+", desc.lower())[:4]
        if words:
            return "-".join(words) + ".html"

    # Fall back to original
    return original_name


def load_manifest():
    """Load the manifest or create a fresh one."""
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH) as f:
            return json.load(f)
    return {"categories": {}, "meta": {"version": "1.0", "lastUpdated": ""}}


def save_manifest(manifest):
    """Write manifest atomically."""
    from datetime import date

    manifest["meta"]["lastUpdated"] = date.today().isoformat()
    tmp = MANIFEST_PATH.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(manifest, f, indent=2)
    tmp.replace(MANIFEST_PATH)


def ensure_category(manifest, cat_key):
    """Ensure category exists in manifest."""
    if cat_key not in manifest["categories"]:
        rules = CATEGORY_RULES.get(cat_key, {})
        manifest["categories"][cat_key] = {
            "title": cat_key.replace("_", " ").title(),
            "folder": rules.get("folder", cat_key),
            "color": "#71717a",
            "count": 0,
            "apps": [],
        }


def file_exists_in_manifest(manifest, filename):
    """Check if a filename already exists in any category."""
    for cat in manifest["categories"].values():
        for app in cat["apps"]:
            if app["file"] == filename:
                return True
    return False


def deep_clean_existing(manifest, dry_run, verbose):
    """Rename garbage-named files already inside apps/ folders."""
    renamed = 0
    for cat_key, cat_data in manifest["categories"].items():
        folder = cat_data["folder"]
        cat_dir = APPS_DIR / folder
        if not cat_dir.exists():
            continue
        for filepath in sorted(cat_dir.iterdir()):
            if not filepath.suffix == ".html":
                continue
            if not GARBAGE_NAMES.match(filepath.name):
                continue

            meta = extract_metadata(filepath)
            if meta is None:
                continue

            new_name = generate_filename(meta, filepath.name)
            if new_name == filepath.name:
                continue

            dest = cat_dir / new_name
            if dest.exists():
                stem = dest.stem
                i = 2
                while dest.exists():
                    dest = cat_dir / f"{stem}-{i}.html"
                    new_name = dest.name
                    i += 1

            print(f"  DEEP CLEAN: apps/{folder}/{filepath.name} -> {new_name}")
            if verbose:
                print(f"    Title: {meta['title'][:80]}")

            if not dry_run:
                filepath.rename(dest)
                # Update manifest entry
                for app in cat_data["apps"]:
                    if app["file"] == filepath.name:
                        app["file"] = new_name
                        if meta["title"] and len(meta["title"]) > 3:
                            app["title"] = meta["title"]
                        if meta["description"]:
                            app["description"] = meta["description"]
                        break

            renamed += 1

    return renamed


def main():
    dry_run = "--dry-run" in sys.argv
    verbose = "--verbose" in sys.argv or dry_run
    deep_clean = "--deep-clean" in sys.argv

    manifest = load_manifest()

    # Phase 0: Deep clean existing garbage names
    if deep_clean:
        print("=== DEEP CLEAN: renaming garbage files in apps/ ===")
        dc_count = deep_clean_existing(manifest, dry_run, verbose)
        if dc_count:
            print(f"\nDeep clean: {dc_count} file(s) renamed")
        else:
            print("Deep clean: no garbage names found")

    # Find HTML files in root that don't belong
    root_html = [
        f
        for f in ROOT.iterdir()
        if f.suffix in (".html", ".htm")
        and f.name not in ROOT_WHITELIST
        and f.name != "index.html"
        and f.is_file()
    ]

    if not root_html and not deep_clean:
        print("autosort: root is clean, nothing to do.")
        return 0

    if root_html:
        print(f"\n=== AUTOSORT: {len(root_html)} file(s) in root to process ===")
    processed = 0

    for filepath in sorted(root_html):
        original_name = filepath.name
        print(f"\n--- Processing: {original_name} ---")

        # Step 1: Extract metadata
        meta = extract_metadata(filepath)
        if meta is None:
            print(f"  SKIP: could not read {original_name}")
            continue

        if verbose:
            print(f"  Title: {meta['title'][:80]}")
            print(f"  Description: {meta['description'][:80]}")
            print(f"  Tags: {meta['tags']}")
            print(f"  Size: {meta['file_size']} bytes -> {meta['complexity']}")

        # Step 2: Rename if garbage filename
        new_name = generate_filename(meta, original_name)
        if new_name != original_name:
            print(f"  RENAME: {original_name} -> {new_name}")
        else:
            new_name = original_name

        # Step 3: Categorize
        cat_key = categorize(meta)
        folder = CATEGORY_RULES.get(cat_key, {}).get("folder", cat_key)
        print(f"  CATEGORY: {cat_key} -> apps/{folder}/")

        # Step 4: Check for collisions
        dest_dir = APPS_DIR / folder
        dest_path = dest_dir / new_name
        if dest_path.exists():
            # Append suffix to avoid collision
            stem = dest_path.stem
            i = 2
            while dest_path.exists():
                dest_path = dest_dir / f"{stem}-{i}.html"
                new_name = dest_path.name
                i += 1
            print(f"  COLLISION: renamed to {new_name}")

        # Step 5: Move file
        if dry_run:
            print(f"  DRY RUN: would move to apps/{folder}/{new_name}")
        else:
            dest_dir.mkdir(parents=True, exist_ok=True)
            filepath.rename(dest_path)
            print(f"  MOVED: -> apps/{folder}/{new_name}")

        # Step 6: Update manifest
        if not file_exists_in_manifest(manifest, new_name):
            ensure_category(manifest, cat_key)
            manifest["categories"][cat_key]["apps"].append(
                {
                    "title": meta["title"] or new_name.replace("-", " ").replace(".html", "").title(),
                    "file": new_name,
                    "description": meta["description"] or f"Self-contained {meta['type']} application",
                    "tags": meta["tags"],
                    "complexity": meta["complexity"],
                    "type": meta["type"],
                    "featured": False,
                    "created": __import__("datetime").date.today().isoformat(),
                }
            )
            manifest["categories"][cat_key]["count"] = len(
                manifest["categories"][cat_key]["apps"]
            )
            if verbose:
                print(f"  MANIFEST: added entry")

        processed += 1

    total = processed + (dc_count if deep_clean else 0)
    if not dry_run and total > 0:
        save_manifest(manifest)
        print(f"\nautosort: processed {total} file(s), manifest updated.")
    elif dry_run:
        print(f"\nautosort: DRY RUN complete, {total} file(s) would be processed.")

    return processed


if __name__ == "__main__":
    count = main()
    sys.exit(0 if count >= 0 else 1)
