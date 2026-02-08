#!/usr/bin/env python3
"""
gene_jackpot_builder.py — Companion to Gene Jackpot slot machine.

Reads build requests from localStorage (via JSON export) or a queue file,
and builds actual HTML apps using Copilot CLI.

Usage:
    # Export queue from browser: copy localStorage['gene-jackpot-queue'] to a file
    python3 scripts/gene_jackpot_builder.py --queue queue.json
    python3 scripts/gene_jackpot_builder.py --queue queue.json --dry-run
    python3 scripts/gene_jackpot_builder.py --queue queue.json --limit 3
"""

import json
import sys
import os
import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

try:
    from copilot_utils import copilot_call, parse_llm_html, detect_backend
except ImportError:
    copilot_call = None


def load_queue(queue_path):
    """Load build queue from JSON file."""
    with open(queue_path) as f:
        return json.load(f)


def build_prompt(item):
    """Build a Copilot CLI prompt from a queue item."""
    parents = item.get("parents", [])
    parent_names = [p["title"] for p in parents]
    techniques = [t["tech"] for t in item.get("techniques", [])]
    experience = item.get("experience", "discovery")
    tags = item.get("tags", [])
    name = item.get("name", "Unnamed")
    desc = item.get("description", "")
    category = item.get("category", "experimental_ai")

    prompt = f"""Create a complete, self-contained HTML app called "{name}".

CONCEPT: {desc}

PARENT APPS (DNA donors): {', '.join(parent_names)}

TARGET EXPERIENCE: {experience}
The app should evoke the feeling of "{experience}" in the user.

INHERITED TECHNIQUES (must use at least 6):
{chr(10).join('- ' + t for t in techniques[:10])}

TAGS: {', '.join(tags)}

REQUIREMENTS:
- Single self-contained HTML file, ALL CSS and JS inline
- Zero external dependencies, no CDNs, no fetch calls
- Must include: <!DOCTYPE html>, <title>, <meta name="viewport">
- Must work offline
- Use localStorage for any persistence
- Include these meta tags:
  <meta name="rappterzoo:author" content="RappterZoo">
  <meta name="rappterzoo:author-type" content="agent">
  <meta name="rappterzoo:category" content="{category.replace('_', '-')}">
  <meta name="rappterzoo:tags" content="{','.join(tags)}">
  <meta name="rappterzoo:type" content="interactive">
  <meta name="rappterzoo:complexity" content="advanced">
  <meta name="rappterzoo:created" content="2026-02-08">
  <meta name="rappterzoo:generation" content="1">
  <meta name="rappterzoo:parents" content="{','.join(p['file'] for p in parents)}">
  <meta name="rappterzoo:experience" content="{experience}">

OUTPUT: Return ONLY the complete HTML file, nothing else."""

    return prompt


def build_app(item, dry_run=False, verbose=False):
    """Build one app from a queue item."""
    name = item.get("name", "Unnamed")
    category = item.get("category", "experimental_ai")
    folder = category.replace("_", "-")

    # Generate filename
    slug = name.lower()
    for ch in " _:—–()[]{}":
        slug = slug.replace(ch, "-")
    slug = "-".join(part for part in slug.split("-") if part)[:60]
    filename = slug + ".html"
    filepath = REPO_ROOT / "apps" / folder / filename

    print(f"\n{'='*60}")
    print(f"Building: {name}")
    print(f"  File:       {filepath}")
    print(f"  Category:   {category}")
    print(f"  Experience: {item.get('experience', '?')}")
    print(f"  Parents:    {', '.join(p['title'][:25] for p in item.get('parents', []))}")
    print(f"  Techniques: {len(item.get('techniques', []))}")

    if dry_run:
        print("  [DRY RUN] Skipping build")
        return filename

    if not copilot_call:
        print("  [ERROR] copilot_utils not available")
        return None

    prompt = build_prompt(item)
    if verbose:
        print(f"  Prompt length: {len(prompt)} chars")

    result = copilot_call(prompt)
    if not result:
        print("  [ERROR] No response from Copilot CLI")
        return None

    html = parse_llm_html(result)
    if not html:
        print("  [ERROR] Could not parse HTML from response")
        return None

    # Validate basics
    if "<!DOCTYPE" not in html[:100].upper():
        print("  [WARN] Missing DOCTYPE")

    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(html, encoding="utf-8")
    print(f"  [OK] Written {len(html)} bytes to {filepath}")

    # Add to manifest
    add_to_manifest(filename, item, category)

    return filename


def add_to_manifest(filename, item, category):
    """Add the new app to manifest.json."""
    manifest_path = REPO_ROOT / "apps" / "manifest.json"
    m = json.loads(manifest_path.read_text())
    cats = m["categories"]
    if category not in cats:
        print(f"  [WARN] Category {category} not in manifest")
        return

    # Check for duplicates
    for app in cats[category]["apps"]:
        if app["file"] == filename:
            print(f"  [SKIP] Already in manifest")
            return

    cats[category]["apps"].append({
        "title": item.get("name", filename.replace(".html", "")),
        "file": filename,
        "description": item.get("description", "")[:200],
        "tags": item.get("tags", [])[:8],
        "complexity": "advanced",
        "type": "interactive",
        "featured": False,
        "created": "2026-02-08",
        "generation": 1
    })
    cats[category]["count"] = len(cats[category]["apps"])

    manifest_path.write_text(json.dumps(m, indent=2) + "\n")
    print(f"  [OK] Added to manifest ({category}: {cats[category]['count']} apps)")


def main():
    parser = argparse.ArgumentParser(description="Build apps from Gene Jackpot queue")
    parser.add_argument("--queue", required=True, help="Path to queue JSON file")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be built")
    parser.add_argument("--limit", type=int, default=0, help="Max apps to build (0=all)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    queue = load_queue(args.queue)
    print(f"Gene Jackpot Builder")
    print(f"Queue: {len(queue)} items")

    if not args.dry_run:
        backend = detect_backend() if detect_backend else None
        if not backend:
            print("[WARN] No Copilot CLI backend detected. Use --dry-run to preview.")

    limit = args.limit if args.limit > 0 else len(queue)
    built = []
    for i, item in enumerate(queue[:limit]):
        result = build_app(item, dry_run=args.dry_run, verbose=args.verbose)
        if result:
            built.append(result)

    print(f"\n{'='*60}")
    print(f"Done. Built {len(built)}/{min(limit, len(queue))} apps.")
    if built:
        print("Files:")
        for f in built:
            print(f"  {f}")


if __name__ == "__main__":
    main()
