#!/usr/bin/env python3
"""Worker script: generate fresh LLM comments for a slice of apps.

Usage: python3 scripts/gen_comments_batch.py <start> <end> <output_file>

NO CACHE. Every run generates fresh unique content via Copilot CLI.
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from copilot_utils import copilot_call, parse_llm_json


def build_batch_prompt(batch, rankings_data):
    apps_data = []
    for app_info in batch:
        app = app_info["app"]
        score, grade = 0, "?"
        if rankings_data:
            for r in rankings_data.get("rankings", []):
                if r.get("file") == app["file"]:
                    score = r.get("score", 0)
                    grade = r.get("grade", "?")
                    break
        apps_data.append({
            "file": app["file"],
            "title": app.get("title", ""),
            "description": app.get("description", ""),
            "tags": app.get("tags", []),
            "complexity": app.get("complexity", "intermediate"),
            "type": app.get("type", "interactive"),
            "category": app_info["catTitle"],
            "score": score,
            "grade": grade,
            "generation": app.get("generation", 0),
        })

    return f"""Generate unique comment threads for {len(apps_data)} apps in the RappterZoo browser game arcade.

APPS:
{json.dumps(apps_data, indent=2)}

For EACH app, generate 6-8 comments. Return a JSON object mapping filename to comment array:
{{
  "filename.html": [
    {{"author": "unique_username", "text": "unique comment", "reply_to": null}},
    {{"author": "other_user", "text": "unique reply", "reply_to": 0}},
    ...
  ]
}}

CRITICAL RULES:
- EVERY comment and username must be COMPLETELY UNIQUE — never reused
- React to each app's ACTUAL score, tags, type, and mechanics
- Include constructive criticism for low-scoring apps (score < 60)
- 60% top-level, 40% replies referencing the parent
- Casual lowercase reddit/discord voice, 15-100 words each
- Don't spam the full title — use "it", "this", short names
- Include one [ArcadeKeeper] moderator review per app with actual score/grade
- Generate unique usernames for each commenter (gaming style: l33t, underscores, etc)

Return ONLY the JSON. No explanation."""


def main():
    start = int(sys.argv[1])
    end = int(sys.argv[2])
    output_file = sys.argv[3]

    manifest = json.loads((ROOT / "apps" / "manifest.json").read_text())
    rankings_path = ROOT / "apps" / "rankings.json"
    rankings_data = json.loads(rankings_path.read_text()) if rankings_path.exists() else None

    apps_list = []
    for cat_key, cat_data in manifest["categories"].items():
        for app in cat_data.get("apps", []):
            apps_list.append({
                "app": app,
                "catKey": cat_key,
                "catTitle": cat_data.get("title", cat_key),
                "folder": cat_data.get("folder", cat_key),
            })

    my_apps = apps_list[start:end]
    print(f"[Worker] Processing apps[{start}:{end}] = {len(my_apps)} apps (FRESH, no cache)")

    results = {}
    batch_size = 5
    successes = 0
    failures = 0

    for i in range(0, len(my_apps), batch_size):
        batch = my_apps[i:i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(my_apps) + batch_size - 1) // batch_size

        print(f"[Worker] Batch {batch_num}/{total_batches} ({len(batch)} apps)...")

        prompt = build_batch_prompt(batch, rankings_data)
        raw = copilot_call(prompt, timeout=90)
        parsed = parse_llm_json(raw) if raw else None

        if parsed and isinstance(parsed, dict):
            for app_info in batch:
                filename = app_info["app"]["file"]
                stem = filename.replace(".html", "")
                if filename in parsed:
                    results[stem] = parsed[filename]
                    successes += 1
                elif stem in parsed:
                    results[stem] = parsed[stem]
                    successes += 1
                else:
                    failures += 1
        else:
            failures += len(batch)
            print(f"[Worker] Batch {batch_num} failed to parse")

        time.sleep(2)

    Path(output_file).write_text(json.dumps(results, indent=2))
    print(f"[Worker] Done: {successes} succeeded, {failures} failed -> {output_file}")


if __name__ == "__main__":
    main()
