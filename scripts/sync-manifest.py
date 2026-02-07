#!/usr/bin/env python3
"""
sync-manifest.py — Sync rappterzoo:* meta tags from HTML posts into manifest.json

Posts are source of truth; manifest is derived. HTML files without rappterzoo tags
are preserved in the manifest unchanged (backward compat).

Usage:
    python3 scripts/sync-manifest.py             # update manifest in place
    python3 scripts/sync-manifest.py --dry-run    # preview changes only
"""

import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APPS_DIR = ROOT / "apps"
MANIFEST_PATH = APPS_DIR / "manifest.json"

VALID_CATEGORIES = {
    "3d_immersive",
    "audio_music",
    "games_puzzles",
    "visual_art",
    "generative_art",
    "particle_physics",
    "creative_tools",
    "educational_tools",
    "experimental_ai",
}

# Map category keys to folder names
CATEGORY_FOLDERS = {
    "3d_immersive": "3d-immersive",
    "audio_music": "audio-music",
    "games_puzzles": "games-puzzles",
    "visual_art": "visual-art",
    "generative_art": "generative-art",
    "particle_physics": "particle-physics",
    "creative_tools": "creative-tools",
    "educational_tools": "educational",
    "experimental_ai": "experimental-ai",
}


def _extract_meta(html, name):
    """Extract content attribute from <meta name="..." content="...">."""
    pattern = re.compile(
        r'<meta\s+name\s*=\s*["\']' + re.escape(name) + r'["\']\s+content\s*=\s*["\']([^"\']*)["\']',
        re.IGNORECASE,
    )
    m = pattern.search(html)
    if m:
        return m.group(1).strip()
    # Also handle content before name
    pattern2 = re.compile(
        r'<meta\s+content\s*=\s*["\']([^"\']*)["\']' + r'\s+name\s*=\s*["\']' + re.escape(name) + r'["\']',
        re.IGNORECASE,
    )
    m2 = pattern2.search(html)
    return m2.group(1).strip() if m2 else None


def _extract_title(html):
    """Extract text from <title>...</title>."""
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else None


def parse_post(html, filename):
    """Extract rappterzoo meta tags from HTML and return a manifest-ready dict.

    Returns None if no rappterzoo tags are found (non-rappterzoo app).
    """
    category = _extract_meta(html, "rappterzoo:category")
    if category is None:
        return None

    if category not in VALID_CATEGORIES:
        print(f"  WARNING: {filename} has invalid category '{category}', skipping", file=sys.stderr)
        return None

    title = _extract_title(html) or filename
    description = _extract_meta(html, "description") or ""
    tags_raw = _extract_meta(html, "rappterzoo:tags") or ""
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
    app_type = _extract_meta(html, "rappterzoo:type") or "interactive"
    complexity = _extract_meta(html, "rappterzoo:complexity") or "intermediate"
    created = _extract_meta(html, "rappterzoo:created") or str(date.today())
    generation_raw = _extract_meta(html, "rappterzoo:generation")
    generation = int(generation_raw) if generation_raw and generation_raw.isdigit() else 0
    featured = False  # derived from manifest or manual curation, not from meta tags

    return {
        "title": title,
        "file": filename,
        "description": description,
        "tags": tags,
        "type": app_type,
        "complexity": complexity,
        "category": category,
        "created": created,
        "generation": generation,
        "featured": featured,
    }


def scan_posts():
    """Walk apps/ subfolders and parse all HTML files with rappterzoo tags."""
    posts = []
    for folder in sorted(APPS_DIR.iterdir()):
        if not folder.is_dir() or folder.name == "archive":
            continue
        for html_file in sorted(folder.glob("*.html")):
            try:
                content = html_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            result = parse_post(content, html_file.name)
            if result is not None:
                posts.append(result)
    return posts


def sync_manifest(posts, manifest, dry_run=False):
    """Merge rappterzoo posts into manifest. Returns (updated_manifest, changes_list)."""
    changes = []
    categories = manifest.get("categories", {})

    # Index existing apps by (category_key, filename) for quick lookup
    existing = {}
    for cat_key, cat_data in categories.items():
        folder = cat_data.get("folder", "")
        for app in cat_data.get("apps", []):
            existing[(cat_key, app["file"])] = app

    # Track which files are rappterzoo-managed per category
    rappterzoo_files = {}  # cat_key -> set of filenames
    for post in posts:
        cat_key = post["category"]
        rappterzoo_files.setdefault(cat_key, set()).add(post["file"])

    # Apply rappterzoo posts
    for post in posts:
        cat_key = post["category"]
        filename = post["file"]
        key = (cat_key, filename)

        # Build the manifest entry (without category, which is structural)
        entry = {
            "title": post["title"],
            "file": post["file"],
            "description": post["description"],
            "tags": post["tags"],
            "complexity": post["complexity"],
            "type": post["type"],
            "featured": post["featured"],
            "created": post["created"],
        }
        if post["generation"] > 0:
            entry["generation"] = post["generation"]

        if key in existing:
            old = existing[key]
            # Preserve featured flag from existing manifest
            entry["featured"] = old.get("featured", False)
            # Preserve any extra fields from existing entry
            for k, v in old.items():
                if k not in entry:
                    entry[k] = v
            if _entry_differs(old, entry):
                changes.append(("update", cat_key, filename, entry))
                existing[key] = entry
            else:
                existing[key] = entry
        else:
            changes.append(("add", cat_key, filename, entry))
            existing[key] = entry

    if not dry_run and changes:
        # Only rebuild categories that have rappterzoo changes
        changed_cats = {cat_key for _, cat_key, _, _ in changes}
        for cat_key in changed_cats:
            cat_data = categories.get(cat_key)
            if cat_data is None:
                continue
            managed = rappterzoo_files.get(cat_key, set())
            # Keep non-rappterzoo apps untouched
            non_rappterzoo = [a for a in cat_data.get("apps", []) if a["file"] not in managed]
            # Add rappterzoo apps
            rappterzoo_apps = [
                existing[(cat_key, f)]
                for f in sorted(managed)
                if (cat_key, f) in existing
            ]
            cat_data["apps"] = sorted(
                non_rappterzoo + rappterzoo_apps, key=lambda a: a.get("title", "")
            )
            cat_data["count"] = len(cat_data["apps"])

        manifest["meta"]["lastUpdated"] = str(date.today())

    return manifest, changes


def _entry_differs(old, new):
    """Check if two manifest entries differ in any meaningful way."""
    keys = set(old.keys()) | set(new.keys())
    for k in keys:
        if old.get(k) != new.get(k):
            return True
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Sync rappterzoo:* meta tags from HTML posts into manifest.json"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would change without modifying manifest.json",
    )
    args = parser.parse_args()

    if not MANIFEST_PATH.exists():
        print(f"ERROR: {MANIFEST_PATH} not found", file=sys.stderr)
        sys.exit(1)

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    posts = scan_posts()

    print(f"Scanned {len(posts)} rappterzoo post(s)")

    manifest, changes = sync_manifest(posts, manifest, dry_run=args.dry_run)

    if not changes:
        print("No changes needed.")
        return

    for action, cat_key, filename, entry in changes:
        folder = CATEGORY_FOLDERS.get(cat_key, cat_key)
        if action == "add":
            print(f"  ADD  apps/{folder}/{filename}")
        else:
            print(f"  UPD  apps/{folder}/{filename}")

    if args.dry_run:
        print(f"\nDry run: {len(changes)} change(s) would be applied.")
    else:
        MANIFEST_PATH.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"\nApplied {len(changes)} change(s) to {MANIFEST_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
