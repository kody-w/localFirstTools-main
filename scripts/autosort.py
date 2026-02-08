#!/usr/bin/env python3
"""
autosort.py — Copilot Intelligence-powered pipeline for localFirstTools-main

Uses Claude Opus 4.6 via GitHub Copilot CLI/SDK to analyze HTML files,
generate descriptive filenames, categorize by content, and update the manifest.

Falls back to keyword matching if Copilot is unavailable.

Run manually:    python3 scripts/autosort.py
Run dry-run:     python3 scripts/autosort.py --dry-run
Deep clean:      python3 scripts/autosort.py --deep-clean
Force keywords:  python3 scripts/autosort.py --no-llm
"""

import json
import os
import re
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APPS_DIR = ROOT / "apps"
MANIFEST_PATH = APPS_DIR / "manifest.json"

MODEL = "claude-opus-4.6"

# Files that belong in root — never touch these
ROOT_WHITELIST = {
    "index.html",
    "README.md",
    "CLAUDE.md",
    "skills.md",
    "copilot-intelligence-pattern.md",
    ".gitignore",
    ".gitattributes",
}

# Garbage filenames that need renaming
GARBAGE_NAMES = re.compile(
    r"^([a-z]|[0-9]+|new|test|temp|tmp|untitled|copy|downloaded|complete-implementation)\.html$",
    re.IGNORECASE,
)

# Valid categories — the ONLY options. No uncategorized.
VALID_CATEGORIES = {
    "3d_immersive": "3d-immersive",
    "audio_music": "audio-music",
    "games_puzzles": "games-puzzles",
    "visual_art": "visual-art",
    "generative_art": "generative-art",
    "particle_physics": "particle-physics",
    "creative_tools": "creative-tools",
    "educational_tools": "educational",
    "experimental_ai": "experimental-ai",
    "data_tools": "data-tools",
    "productivity": "productivity",
}

VALID_TAGS = [
    "3d", "canvas", "svg", "animation", "audio", "particles", "physics",
    "interactive", "game", "ai", "creative", "terminal", "retro",
    "simulation", "crm",
]

# ─── Keyword fallback rules (used when Copilot is unavailable) ───────────────

CATEGORY_RULES = {
    "3d_immersive": {
        "high": ["three.js", "THREE.", "WebGLRenderer", "PerspectiveCamera", "OrbitControls", "raycaster"],
        "medium": ["3d", "webgl", "glsl", "shader", "vertex", "fragment", "mesh", "geometry"],
        "low": ["rotate", "camera", "scene", "render3d"],
    },
    "audio_music": {
        "high": ["AudioContext", "OscillatorNode", "GainNode", "analyser", "createOscillator"],
        "medium": ["synthesizer", "synth", "midi", "drum", "beat", "sequencer", "daw", "bpm", "tempo"],
        "low": ["audio", "sound", "music", "frequency", "waveform", "note"],
    },
    "games_puzzles": {
        "high": ["game over", "score", "lives", "level", "player", "enemy", "collision"],
        "medium": ["puzzle", "card game", "board game", "solitaire", "chess", "battle", "rpg", "quest"],
        "low": ["game", "play", "win", "lose", "points", "health", "attack", "defense"],
    },
    "visual_art": {
        "high": ["getContext('2d')", "ctx.beginPath", "ctx.fillRect", "ctx.strokeStyle", "drawImage"],
        "medium": ["canvas", "drawing", "paint", "brush", "palette", "color picker", "sketch"],
        "low": ["visual", "art", "design", "creative", "draw", "pixel"],
    },
    "generative_art": {
        "high": ["perlin", "simplex", "noise", "L-system", "cellular automata", "voronoi"],
        "medium": ["fractal", "mandelbrot", "procedural", "generative", "algorithmic", "recursive pattern"],
        "low": ["generate", "random", "seed", "iterate", "evolve", "mutate"],
    },
    "particle_physics": {
        "high": ["particles", "velocity", "acceleration", "gravity", "force", "collision detection"],
        "medium": ["physics", "simulation", "particle system", "n-body", "spring", "pendulum"],
        "low": ["mass", "momentum", "energy", "orbit", "wave"],
    },
    "creative_tools": {
        "high": ["markdown", "editor", "converter", "calculator", "formatter", "validator"],
        "medium": ["tool", "utility", "productivity", "tracker", "manager", "planner", "builder"],
        "low": ["export", "import", "save", "load", "template", "workflow"],
    },
    "educational_tools": {
        "high": ["tutorial", "lesson", "quiz", "flashcard", "learn", "teach"],
        "medium": ["educational", "training", "practice", "exercise", "study"],
        "low": ["explain", "example", "guide", "reference"],
    },
    "experimental_ai": {
        "high": ["neural", "machine learning", "AI", "chatbot", "GPT", "LLM", "inference"],
        "medium": ["artificial intelligence", "model", "agent", "prompt", "embedding", "transformer"],
        "low": ["intelligent", "smart", "adaptive", "predict", "classify"],
    },
    "data_tools": {
        "high": ["dataset", "csv", "json viewer", "data table", "chart", "dashboard", "query"],
        "medium": ["data", "analytics", "visualization", "spreadsheet", "database", "schema", "api"],
        "low": ["import", "export", "filter", "sort", "column", "row", "fetch"],
    },
    "productivity": {
        "high": ["wiki", "note", "kanban", "todo", "calendar", "vault", "file manager"],
        "medium": ["markdown", "editor", "organizer", "planner", "task", "bookmark", "journal"],
        "low": ["workflow", "productivity", "document", "page", "write", "manage"],
    },
}


# ─── HTML Parser ─────────────────────────────────────────────────────────────


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


# ─── File Metadata Extraction ────────────────────────────────────────────────


def extract_metadata(filepath):
    """Read an HTML file and extract raw metadata."""
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

    # Detect tags deterministically (no LLM needed for this)
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

    # Determine complexity deterministically
    if file_size > 50000 or "3d" in tags:
        complexity = "advanced"
    elif file_size > 20000:
        complexity = "intermediate"
    else:
        complexity = "simple"

    return {
        "title": title,
        "description": description,
        "tags": tags[:6],
        "complexity": complexity,
        "content": content,
        "content_lower": content_lower,
        "body_sample": body_sample,
        "meta_category": parser.meta_category,
        "file_size": file_size,
    }


# ─── Copilot Intelligence Layer ──────────────────────────────────────────────


def detect_backend():
    """Determine which intelligence backend is available."""
    if shutil.which("gh"):
        try:
            result = subprocess.run(
                ["gh", "copilot", "--", "--help"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                return "copilot-cli"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
    return "keyword-fallback"


def copilot_analyze(prompt, verbose=False):
    """Send a prompt to Copilot CLI with Claude Opus and return the raw response."""
    cmd = [
        "gh", "copilot",
        "--model", MODEL,
        "-p", prompt,
        "--no-ask-user",
    ]
    if verbose:
        print(f"  [copilot] calling {MODEL}...")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            if verbose:
                print(f"  [copilot] CLI error: {result.stderr[:200]}")
            return None
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        if verbose:
            print("  [copilot] timed out after 120s")
        return None
    except FileNotFoundError:
        return None


def strip_copilot_wrapper(text):
    """Strip Copilot CLI wrapper: ANSI codes, usage stats, task summary."""
    # Strip ANSI escape codes
    text = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text)
    text = re.sub(r"\x1b[^a-zA-Z]*[a-zA-Z]", "", text)
    # Strip everything after the task summary line
    for marker in ["Task complete", "Total usage est:", "Total session time:"]:
        idx = text.find(marker)
        if idx > 0:
            text = text[:idx]
    return text.strip()


def parse_llm_json(raw_output):
    """Extract JSON from LLM output, handling Copilot CLI formatting."""
    if not raw_output:
        return None

    text = strip_copilot_wrapper(raw_output)

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strip markdown code fences
    fenced = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Find first { ... } block (greedy to catch nested braces)
    brace_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group())
        except json.JSONDecodeError:
            pass

    return None


def build_analysis_prompt(filename, content, file_size):
    """Build the structured prompt for Copilot to analyze an HTML file."""
    # Truncate content to first 8000 chars (title, meta, and early code are most informative)
    sample = content[:8000]
    categories_list = ", ".join(VALID_CATEGORIES.keys())
    tags_list = ", ".join(VALID_TAGS)

    return f"""You are a content analyst categorizing self-contained HTML applications for a gallery.

Analyze this HTML file and return ONLY a JSON object (no markdown, no explanation, no code fences) with these exact keys:

{{
  "category": "one of: {categories_list}",
  "filename": "descriptive-kebab-case-name.html",
  "title": "Human Readable Title",
  "description": "One sentence describing what this app does",
  "tags": ["up to 6 tags from: {tags_list}"],
  "type": "game|visual|audio|interactive|interface|drawing"
}}

Rules:
- category MUST be exactly one of: {categories_list}. NEVER return "uncategorized" or "other" or anything not in that list.
- filename must be descriptive of the content, kebab-case, max 60 chars, ending in .html. NOT the original filename.
- description must be exactly one sentence, under 120 characters.
- Pick the MOST SPECIFIC category. experimental_ai is the catch-all ONLY if nothing else fits.
- For games, puzzles, or anything playable: use games_puzzles.
- For 3D/WebGL/Three.js: use 3d_immersive.
- For audio/music/synth: use audio_music.
- For drawing/painting/visual design tools: use visual_art.
- For procedural/generative/algorithmic art: use generative_art.
- For physics/particles/simulation: use particle_physics.
- For utilities/productivity/converters: use creative_tools.
- For tutorials/learning: use educational_tools.
- tags must only contain values from: {tags_list}

Original filename: {filename}
File size: {file_size} bytes

HTML content (first 8000 chars):
---
{sample}
---

Return ONLY the JSON object."""


def validate_llm_result(result):
    """Validate and sanitize the LLM response. Returns cleaned dict or None."""
    if not result or not isinstance(result, dict):
        return None

    # Validate category
    cat = result.get("category", "")
    if cat not in VALID_CATEGORIES:
        # Try fuzzy matching
        for valid_key in VALID_CATEGORIES:
            if cat.replace("-", "_").replace(" ", "_").lower() == valid_key:
                result["category"] = valid_key
                break
        else:
            return None  # Invalid category, fall back

    # Validate filename
    fn = result.get("filename", "")
    if not fn or not fn.endswith(".html"):
        return None
    # Sanitize filename
    fn = re.sub(r"[^a-z0-9\-.]", "", fn.lower())
    if len(fn) < 5:  # x.html minimum
        return None
    result["filename"] = fn

    # Validate tags
    tags = result.get("tags", [])
    result["tags"] = [t for t in tags if t in VALID_TAGS][:6]

    # Validate type
    valid_types = {"game", "visual", "audio", "interactive", "interface", "drawing"}
    if result.get("type") not in valid_types:
        result["type"] = "interactive"

    # Ensure required fields
    if not result.get("title"):
        return None
    if not result.get("description"):
        result["description"] = f"Self-contained {result.get('type', 'interactive')} application"

    return result


def analyze_with_copilot(filename, meta, verbose=False):
    """Use Copilot CLI + Claude Opus to analyze an HTML file. Returns structured dict or None."""
    prompt = build_analysis_prompt(filename, meta["content"], meta["file_size"])
    raw = copilot_analyze(prompt, verbose=verbose)

    if verbose and raw:
        print(f"  [copilot] raw response length: {len(raw)} chars")

    result = parse_llm_json(raw)
    if result is None:
        if verbose:
            print("  [copilot] could not parse JSON from response")
        return None

    validated = validate_llm_result(result)
    if validated is None:
        if verbose:
            print(f"  [copilot] validation failed: {result}")
        return None

    if verbose:
        print(f"  [copilot] => category={validated['category']}, filename={validated['filename']}")
        print(f"  [copilot] => title={validated['title'][:60]}")

    return validated


# ─── Keyword Fallback ────────────────────────────────────────────────────────


def categorize_by_keywords(meta):
    """Score content against category rules. Fallback when Copilot is unavailable."""
    if meta["meta_category"]:
        for cat_key in VALID_CATEGORIES:
            if meta["meta_category"] in (cat_key, VALID_CATEGORIES[cat_key]):
                return cat_key

    content = meta["content_lower"]
    scores = {}

    for cat_key, rules in CATEGORY_RULES.items():
        score = 0
        for signal in rules.get("high", []):
            if signal.lower() in content:
                score += 10
        for signal in rules.get("medium", []):
            if signal.lower() in content:
                score += 4
        for signal in rules.get("low", []):
            if signal.lower() in content:
                score += 1
        scores[cat_key] = score

    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "experimental_ai"


def slugify(text):
    """Convert text to a clean kebab-case filename slug."""
    text = text.lower().strip()
    for suffix in [" - interactive", " - demo", " - app", " app", " tool", " game"]:
        if text.endswith(suffix.lower()):
            text = text[: -len(suffix)]
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    text = text.strip("-")
    return text[:60]


def generate_filename_fallback(meta, original_name):
    """Generate a better filename from content (keyword fallback)."""
    if not GARBAGE_NAMES.match(original_name):
        return original_name

    title = meta["title"]
    if title and len(title) > 3:
        slug = slugify(title)
        if slug and len(slug) > 3:
            return slug + ".html"

    desc = meta["description"]
    if desc and len(desc) > 5:
        words = re.findall(r"[a-z]+", desc.lower())[:4]
        if words:
            return "-".join(words) + ".html"

    return original_name


def analyze_with_keywords(filename, meta, verbose=False):
    """Keyword-based analysis. Fallback when Copilot is unavailable."""
    cat_key = categorize_by_keywords(meta)
    new_name = generate_filename_fallback(meta, filename)

    # Determine interaction type
    tags = meta["tags"]
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

    if verbose:
        print(f"  [keywords] => category={cat_key}, filename={new_name}")

    return {
        "category": cat_key,
        "filename": new_name,
        "title": meta["title"] or new_name.replace("-", " ").replace(".html", "").title(),
        "description": meta["description"] or f"Self-contained {itype} application",
        "tags": meta["tags"],
        "type": itype,
    }


# ─── Unified Analysis ────────────────────────────────────────────────────────


def analyze_file(filepath, backend, verbose=False):
    """Analyze a file using the best available backend."""
    meta = extract_metadata(filepath)
    if meta is None:
        return None, None

    # If the app specifies its own category via meta tag, respect it
    if meta["meta_category"]:
        for cat_key in VALID_CATEGORIES:
            if meta["meta_category"] in (cat_key, VALID_CATEGORIES[cat_key]):
                if verbose:
                    print(f"  [meta] category override: {cat_key}")
                result = analyze_with_keywords(filepath.name, meta, verbose)
                result["category"] = cat_key
                return result, meta

    if backend == "copilot-cli":
        result = analyze_with_copilot(filepath.name, meta, verbose)
        if result is not None:
            return result, meta
        # Copilot failed for this file — fall through to keywords
        if verbose:
            print("  [copilot] failed, falling back to keywords")

    result = analyze_with_keywords(filepath.name, meta, verbose)
    return result, meta


# ─── Manifest Operations ─────────────────────────────────────────────────────


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
        folder = VALID_CATEGORIES.get(cat_key, cat_key)
        manifest["categories"][cat_key] = {
            "title": cat_key.replace("_", " ").title(),
            "folder": folder,
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


# ─── Deep Clean ──────────────────────────────────────────────────────────────


def deep_clean_existing(manifest, backend, dry_run, verbose):
    """Rename garbage-named files already inside apps/ folders using Copilot intelligence."""
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

            result, meta = analyze_file(filepath, backend, verbose)
            if result is None:
                continue

            new_name = result["filename"]
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
                print(f"    Title: {result['title'][:80]}")

            if not dry_run:
                filepath.rename(dest)
                for app in cat_data["apps"]:
                    if app["file"] == filepath.name:
                        app["file"] = new_name
                        app["title"] = result["title"]
                        if result["description"]:
                            app["description"] = result["description"]
                        if result["tags"]:
                            app["tags"] = result["tags"]
                        break

            renamed += 1

    return renamed


# ─── Main Pipeline ───────────────────────────────────────────────────────────


def main():
    dry_run = "--dry-run" in sys.argv
    verbose = "--verbose" in sys.argv or dry_run
    deep_clean = "--deep-clean" in sys.argv
    no_llm = "--no-llm" in sys.argv

    # Detect intelligence backend
    if no_llm:
        backend = "keyword-fallback"
    else:
        backend = detect_backend()

    print(f"autosort: intelligence backend = {backend}")
    if backend == "copilot-cli":
        print(f"autosort: model = {MODEL}")

    manifest = load_manifest()

    dc_count = 0
    # Phase 0: Deep clean existing garbage names
    if deep_clean:
        print("\n=== DEEP CLEAN: renaming garbage files in apps/ ===")
        dc_count = deep_clean_existing(manifest, backend, dry_run, verbose)
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

        # Step 1: Analyze with Copilot intelligence (or keyword fallback)
        result, meta = analyze_file(filepath, backend, verbose)
        if result is None:
            print(f"  SKIP: could not read {original_name}")
            continue

        cat_key = result["category"]
        new_name = result["filename"]
        folder = VALID_CATEGORIES.get(cat_key, cat_key)

        if verbose:
            print(f"  Title: {result['title'][:80]}")
            print(f"  Description: {result['description'][:80]}")
            print(f"  Tags: {result['tags']}")
            print(f"  Size: {meta['file_size']} bytes -> {meta['complexity']}")

        if new_name != original_name:
            print(f"  RENAME: {original_name} -> {new_name}")

        print(f"  CATEGORY: {cat_key} -> apps/{folder}/")

        # Step 2: Check for collisions
        dest_dir = APPS_DIR / folder
        dest_path = dest_dir / new_name
        if dest_path.exists():
            stem = dest_path.stem
            i = 2
            while dest_path.exists():
                dest_path = dest_dir / f"{stem}-{i}.html"
                new_name = dest_path.name
                i += 1
            print(f"  COLLISION: renamed to {new_name}")

        # Step 3: Move file
        if dry_run:
            print(f"  DRY RUN: would move to apps/{folder}/{new_name}")
        else:
            dest_dir.mkdir(parents=True, exist_ok=True)
            filepath.rename(dest_path)
            print(f"  MOVED: -> apps/{folder}/{new_name}")

        # Step 4: Update manifest
        if not file_exists_in_manifest(manifest, new_name):
            ensure_category(manifest, cat_key)
            manifest["categories"][cat_key]["apps"].append(
                {
                    "title": result["title"],
                    "file": new_name,
                    "description": result["description"],
                    "tags": result["tags"],
                    "complexity": meta["complexity"],
                    "type": result["type"],
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

    total = processed + dc_count
    if not dry_run and total > 0:
        save_manifest(manifest)
        print(f"\nautosort: processed {total} file(s), manifest updated.")
    elif dry_run:
        print(f"\nautosort: DRY RUN complete, {total} file(s) would be processed.")

    return processed


if __name__ == "__main__":
    count = main()
    sys.exit(0 if count >= 0 else 1)
