#!/usr/bin/env python3
"""
buzzsaw_pipeline.py -- Production pipeline utilities for Buzzsaw v3.

Provides functions for the hybrid buzzsaw architecture:
- Dynamic deduplication (scan manifest instead of static list)
- Quality gate (score new apps, reject below threshold)
- Category balancing (find underserved categories, weight generation)
- Feedback loop (load top-scoring apps as few-shot examples)
- Community injection (generate stub community entries for new apps)

All functions are pure/testable with dependency injection. No network calls.
"""

import json
import random
import re
from datetime import date, datetime
from pathlib import Path

from copilot_utils import (
    APPS_DIR,
    MANIFEST_PATH,
    VALID_CATEGORIES,
    load_manifest,
    save_manifest,
)

# ──────────────────────────────────────────────
# P1: Dynamic Deduplication
# ──────────────────────────────────────────────

def get_existing_titles(manifest=None):
    """Return a set of lowercased titles already in the manifest.

    Args:
        manifest: Pre-loaded manifest dict. If None, loads from disk.

    Returns:
        set of lowercase title strings.
    """
    if manifest is None:
        manifest = load_manifest()
    titles = set()
    for cat_data in manifest.get("categories", {}).values():
        for app in cat_data.get("apps", []):
            titles.add(app.get("title", "").lower().strip())
    return titles


def get_existing_files(manifest=None):
    """Return a set of filenames already in the manifest.

    Args:
        manifest: Pre-loaded manifest dict. If None, loads from disk.

    Returns:
        set of filename strings (e.g. 'my-game.html').
    """
    if manifest is None:
        manifest = load_manifest()
    files = set()
    for cat_data in manifest.get("categories", {}).values():
        for app in cat_data.get("apps", []):
            files.add(app.get("file", ""))
    return files


def is_duplicate(title, filename, manifest=None):
    """Check if a game with this title or filename already exists.

    Args:
        title: Proposed game title.
        filename: Proposed filename (e.g. 'my-game.html').
        manifest: Pre-loaded manifest dict.

    Returns:
        True if duplicate found.
    """
    if manifest is None:
        manifest = load_manifest()
    titles = get_existing_titles(manifest)
    files = get_existing_files(manifest)
    return title.lower().strip() in titles or filename in files


def deduplicate_concepts(concepts, manifest=None):
    """Filter out concepts that duplicate existing manifest entries.

    Args:
        concepts: List of dicts with 'title' and 'filename' keys.
        manifest: Pre-loaded manifest dict.

    Returns:
        List of non-duplicate concepts.
    """
    if manifest is None:
        manifest = load_manifest()
    titles = get_existing_titles(manifest)
    files = get_existing_files(manifest)
    result = []
    for c in concepts:
        t = c.get("title", "").lower().strip()
        f = c.get("filename", "")
        if t not in titles and f not in files:
            result.append(c)
            titles.add(t)
            files.add(f)
    return result


# ──────────────────────────────────────────────
# P1: Quality Gate
# ──────────────────────────────────────────────

DEFAULT_GAME_THRESHOLD = 50
DEFAULT_APP_THRESHOLD = 40


def score_app(filepath):
    """Score an HTML app using rank_games.py dimensions.

    Args:
        filepath: Path to HTML file.

    Returns:
        dict with 'score' (0-100), 'grade', 'dimensions', 'passed', 'threshold'.
    """
    from rank_games import score_game
    filepath = Path(filepath)
    content = filepath.read_text(errors="replace")
    result = score_game(filepath, content)
    is_game = "games-puzzles" in str(filepath)
    threshold = DEFAULT_GAME_THRESHOLD if is_game else DEFAULT_APP_THRESHOLD
    result["passed"] = result["score"] >= threshold
    result["threshold"] = threshold
    return result


def quality_gate(filepath, threshold=None):
    """Run quality gate on a file. Returns (passed: bool, report: dict).

    Args:
        filepath: Path to HTML file.
        threshold: Override minimum score. If None, uses category default.

    Returns:
        Tuple of (passed, report_dict).
    """
    result = score_app(filepath)
    if threshold is not None:
        result["passed"] = result["score"] >= threshold
        result["threshold"] = threshold
    return result["passed"], result


def quality_gate_batch(filepaths, threshold=None):
    """Run quality gate on multiple files.

    Args:
        filepaths: List of Path objects.
        threshold: Override minimum score.

    Returns:
        dict with 'passed', 'failed', 'results' keys.
    """
    passed = []
    failed = []
    results = {}
    for fp in filepaths:
        fp = Path(fp)
        ok, report = quality_gate(fp, threshold)
        results[fp.name] = report
        if ok:
            passed.append(fp)
        else:
            failed.append(fp)
    return {"passed": passed, "failed": failed, "results": results}


# ──────────────────────────────────────────────
# P2: Category Balancing
# ──────────────────────────────────────────────

def get_category_counts(manifest=None):
    """Return dict of category_key -> app count.

    Args:
        manifest: Pre-loaded manifest dict.

    Returns:
        dict mapping category keys to integer counts.
    """
    if manifest is None:
        manifest = load_manifest()
    counts = {}
    for cat_key, cat_data in manifest.get("categories", {}).items():
        counts[cat_key] = len(cat_data.get("apps", []))
    return counts


def get_underserved_categories(manifest=None, top_n=3):
    """Return the N categories with the fewest apps.

    Args:
        manifest: Pre-loaded manifest dict.
        top_n: Number of categories to return.

    Returns:
        List of (category_key, count) tuples, sorted ascending.
    """
    counts = get_category_counts(manifest)
    sorted_cats = sorted(counts.items(), key=lambda x: x[1])
    return sorted_cats[:top_n]


def suggest_category_distribution(num_games, manifest=None):
    """Suggest how many games to create per category for balance.

    Allocates proportionally more to underserved categories.

    Args:
        num_games: Total games to distribute.
        manifest: Pre-loaded manifest dict.

    Returns:
        dict of category_key -> suggested count.
    """
    counts = get_category_counts(manifest)
    if not counts:
        return {"games_puzzles": num_games}

    max_count = max(counts.values()) if counts else 1
    # Inverse weight: categories with fewer apps get more weight
    weights = {}
    for cat, count in counts.items():
        weights[cat] = max(1, max_count - count + 1)

    total_weight = sum(weights.values())
    distribution = {}
    allocated = 0
    items = sorted(weights.items(), key=lambda x: -x[1])

    for cat, w in items:
        share = max(0, round(num_games * w / total_weight))
        distribution[cat] = share
        allocated += share

    # Distribute remainder to most underserved
    remainder = num_games - allocated
    if remainder > 0 and items:
        distribution[items[0][0]] += remainder
    elif remainder < 0:
        # Over-allocated: trim from largest
        for cat, _ in reversed(items):
            if distribution[cat] > 0 and remainder < 0:
                trim = min(distribution[cat], -remainder)
                distribution[cat] -= trim
                remainder += trim

    # Remove zero entries
    return {k: v for k, v in distribution.items() if v > 0}


# ──────────────────────────────────────────────
# P2: Feedback Loop
# ──────────────────────────────────────────────

RANKINGS_PATH = APPS_DIR / "rankings.json"


def load_rankings(rankings_path=None):
    """Load the rankings.json file.

    Args:
        rankings_path: Path to rankings file. Defaults to apps/rankings.json.

    Returns:
        dict or None if file doesn't exist.
    """
    path = rankings_path or RANKINGS_PATH
    if Path(path).exists():
        return json.loads(Path(path).read_text())
    return None


def get_top_apps(n=5, category=None, rankings_path=None):
    """Return the top N highest-scoring apps as reference examples.

    Args:
        n: Number of top apps to return.
        category: If set, filter to this category key.
        rankings_path: Path to rankings file.

    Returns:
        List of dicts with 'file', 'title', 'score', 'category' keys.
    """
    rankings = load_rankings(rankings_path)
    if not rankings:
        return []

    apps = []
    for cat_key, cat_data in rankings.get("categories", {}).items():
        if category and cat_key != category:
            continue
        for app in cat_data.get("apps", []):
            apps.append({
                "file": app.get("file", ""),
                "title": app.get("title", ""),
                "score": app.get("score", 0),
                "grade": app.get("grade", "?"),
                "category": cat_key,
            })

    apps.sort(key=lambda x: x["score"], reverse=True)
    return apps[:n]


def build_feedback_prompt_section(top_apps, max_examples=3):
    """Build a prompt section showing top-scoring apps as quality examples.

    Args:
        top_apps: List from get_top_apps().
        max_examples: Max examples to include.

    Returns:
        String to embed in generation prompts.
    """
    if not top_apps:
        return ""

    lines = [
        "QUALITY REFERENCE — These are the highest-rated apps in the gallery.",
        "Study what makes them excellent and aim to match or exceed their quality:",
        "",
    ]
    for app in top_apps[:max_examples]:
        lines.append(
            f"  - \"{app['title']}\" (Score: {app['score']}/100, Grade: {app['grade']}) "
            f"— {app['category']}/{app['file']}"
        )

    lines.append("")
    lines.append("Your game should achieve at least a B grade (70+/100) across all 6 dimensions:")
    lines.append("  Structural (15), Scale (10), Systems (20), Completeness (15), Playability (25), Polish (15)")
    return "\n".join(lines)


# ──────────────────────────────────────────────
# P3: Community Injection
# ──────────────────────────────────────────────

COMMUNITY_PATH = APPS_DIR / "community.json"

# NPC name pools for generating comments
NPC_FIRST_NAMES = [
    "Pixel", "Byte", "Nova", "Glitch", "Echo", "Cipher", "Neon", "Blaze",
    "Storm", "Vex", "Drift", "Flux", "Rune", "Zap", "Spark", "Arc",
]
NPC_LAST_NAMES = [
    "Runner", "Walker", "Coder", "Hacker", "Builder", "Smith", "Knight",
    "Fox", "Wolf", "Hawk", "Bear", "Phoenix", "Dragon", "Tiger",
]

COMMENT_TEMPLATES = [
    "This is incredible! The {feature} really blew my mind.",
    "Wow, {feature} is so smooth. Great work!",
    "I've been playing this for an hour straight. Love the {feature}.",
    "The {feature} gives this such a unique feel. Bookmarked!",
    "Really polished. The {feature} alone makes it worth checking out.",
    "Not bad! Would love to see more {feature} in future updates.",
    "This is what the gallery needs more of. {feature} is next level.",
    "Just showed this to my friend, they couldn't believe the {feature}.",
]

FEATURE_POOL = [
    "procedural generation", "sound design", "particle effects",
    "color palette", "game loop", "physics engine", "AI behavior",
    "save system", "difficulty curve", "visual feedback", "animations",
    "level design", "combo system", "progression system", "atmosphere",
]


def generate_community_entries(app_titles, num_comments_per_app=3, num_ratings_per_app=5, seed=None):
    """Generate stub community data for new apps.

    Args:
        app_titles: List of (filename, title) tuples for new apps.
        num_comments_per_app: Comments to generate per app.
        num_ratings_per_app: Ratings to generate per app.
        seed: Random seed for determinism.

    Returns:
        dict with 'comments' and 'ratings' keys, ready to merge into community.json.
    """
    rng = random.Random(seed)
    comments = []
    ratings = {}

    for filename, title in app_titles:
        # Generate comments
        for _ in range(num_comments_per_app):
            npc = rng.choice(NPC_FIRST_NAMES) + " " + rng.choice(NPC_LAST_NAMES)
            template = rng.choice(COMMENT_TEMPLATES)
            feature = rng.choice(FEATURE_POOL)
            comments.append({
                "app": filename,
                "author": npc,
                "text": template.format(feature=feature),
                "timestamp": datetime.now().isoformat(),
            })

        # Generate ratings (3-5 stars, weighted toward 4)
        app_ratings = []
        for _ in range(num_ratings_per_app):
            rating = rng.choices([3, 4, 5], weights=[2, 5, 3])[0]
            app_ratings.append(rating)
        ratings[filename] = {
            "ratings": app_ratings,
            "avg": round(sum(app_ratings) / len(app_ratings), 2),
            "count": len(app_ratings),
        }

    return {"comments": comments, "ratings": ratings}


# ──────────────────────────────────────────────
# Validation Utilities
# ──────────────────────────────────────────────

def validate_html_file(filepath):
    """Run structural validation on an HTML file.

    Args:
        filepath: Path to the HTML file.

    Returns:
        dict with 'passed' (bool), 'checks' (list of check results),
        'failures' (list of failure descriptions).
    """
    filepath = Path(filepath)
    if not filepath.exists():
        return {"passed": False, "checks": [], "failures": ["File does not exist"]}

    content = filepath.read_text(errors="replace")
    size = len(content)
    lines = content.count("\n") + 1
    checks = []
    failures = []

    # 1. File exists (already confirmed)
    checks.append({"name": "exists", "passed": True})

    # 2. Minimum size (20KB)
    size_ok = size >= 20480
    checks.append({"name": "size", "passed": size_ok, "value": size})
    if not size_ok:
        failures.append(f"File too small: {size} bytes (need 20480+)")

    # 3. Minimum lines (500)
    lines_ok = lines >= 500
    checks.append({"name": "lines", "passed": lines_ok, "value": lines})
    if not lines_ok:
        failures.append(f"Too few lines: {lines} (need 500+)")

    # 4. DOCTYPE
    has_doctype = "<!DOCTYPE html>" in content or "<!doctype html>" in content
    checks.append({"name": "doctype", "passed": has_doctype})
    if not has_doctype:
        failures.append("Missing <!DOCTYPE html>")

    # 5. No external deps
    ext_deps = re.findall(r'(?:src|href)="(https?://[^"]+\.(?:js|css|mjs))"', content)
    no_ext = len(ext_deps) == 0
    checks.append({"name": "no_external_deps", "passed": no_ext, "value": ext_deps})
    if not no_ext:
        failures.append(f"External dependencies: {ext_deps}")

    # 6. localStorage
    has_storage = "localStorage" in content
    checks.append({"name": "localStorage", "passed": has_storage})
    if not has_storage:
        failures.append("Missing localStorage usage")

    return {
        "passed": len(failures) == 0,
        "checks": checks,
        "failures": failures,
        "size": size,
        "lines": lines,
    }


def build_fix_prompt(filepath, failures):
    """Build a targeted fix prompt based on specific validation failures.

    Args:
        filepath: Path to the HTML file.
        failures: List of failure description strings.

    Returns:
        String prompt for Copilot CLI to fix the issues.
    """
    failure_list = "\n".join(f"  - {f}" for f in failures)
    return (
        f"The HTML game file has the following issues:\n"
        f"{failure_list}\n\n"
        f"Fix ONLY these specific issues while keeping all existing game logic intact.\n"
        f"If the file is too small, add more game systems (procedural generation, "
        f"more enemy types, upgrade system, achievement system).\n"
        f"If localStorage is missing, add a complete save/load system.\n"
        f"If DOCTYPE is missing, add it at the top.\n"
        f"Output ONLY the complete fixed HTML file, no markdown fences or explanation."
    )


# ──────────────────────────────────────────────
# Manifest Helpers
# ──────────────────────────────────────────────

def add_apps_to_manifest(app_entries, category_key="games_puzzles", manifest=None):
    """Add multiple app entries to the manifest.

    Args:
        app_entries: List of dicts with title, file, description, tags, etc.
        category_key: Manifest category key.
        manifest: Pre-loaded manifest. If None, loads from disk.

    Returns:
        Updated manifest dict (also saves to disk).
    """
    if manifest is None:
        manifest = load_manifest()

    cat = manifest.get("categories", {}).get(category_key, {})
    apps = cat.get("apps", [])

    existing_files = {a["file"] for a in apps}
    added = 0
    for entry in app_entries:
        if entry["file"] not in existing_files:
            apps.append(entry)
            existing_files.add(entry["file"])
            added += 1

    cat["apps"] = apps
    cat["count"] = len(apps)
    manifest.setdefault("categories", {})[category_key] = cat

    save_manifest(manifest)
    return manifest


def make_manifest_entry(title, filename, description="", tags=None,
                        complexity="advanced", app_type="game"):
    """Create a manifest entry dict for a new app.

    Args:
        title: Display title.
        filename: HTML filename.
        description: One-line description.
        tags: List of tag strings.
        complexity: simple|intermediate|advanced.
        app_type: game|visual|audio|interactive|interface.

    Returns:
        dict ready for manifest apps array.
    """
    return {
        "title": title,
        "file": filename,
        "description": description,
        "tags": tags or ["canvas", "game", "interactive"],
        "complexity": complexity,
        "type": app_type,
        "featured": False,
        "created": date.today().isoformat(),
    }
