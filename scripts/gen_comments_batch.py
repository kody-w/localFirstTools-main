#!/usr/bin/env python3
"""Worker script: generate LLM comments for a slice of apps.

Usage: python3 scripts/gen_comments_batch.py <start> <end> <output_file>

Reads manifest, takes apps[start:end], calls Copilot CLI in batches of 5,
writes results to output_file as JSON.
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from copilot_utils import copilot_call, parse_llm_json


def build_batch_prompt(batch):
    apps_data = []
    for app_info in batch:
        app = app_info["app"]
        apps_data.append({
            "file": app["file"],
            "title": app.get("title", ""),
            "description": app.get("description", ""),
            "tags": app.get("tags", []),
            "complexity": app.get("complexity", "intermediate"),
            "type": app.get("type", "interactive"),
            "category": app_info["catTitle"],
            "generation": app.get("generation", 0),
        })

    return f"""You are generating realistic community discussion comments for a browser game arcade called RappterZoo.

For each app below, generate 6-8 unique comments that a real player community would write. Comments must:
- React to the SPECIFIC app's actual content, tags, mechanics, and type
- Sound like real forum/reddit posts — casual, varied tone, some short some long
- Include 1-2 constructive criticisms or suggestions (not everything positive)
- Include 1-2 replies that respond to a previous comment in the thread
- NEVER repeat the full app title in every comment — use "it", "this", or a short name
- Vary between technical observations, emotional reactions, comparisons, and casual chat
- Be lowercase informal style (like reddit/discord)

Return a JSON object mapping each app's "file" to an array of comment objects:
{{
  "filename.html": [
    {{"text": "comment text", "reply_to": null}},
    {{"text": "reply text", "reply_to": 0}},
    ...
  ],
  ...
}}

"reply_to" is the 0-based index of the comment being replied to, or null for top-level.

Apps to generate comments for:
{json.dumps(apps_data, indent=2)}

Return ONLY the JSON. No explanation."""


def main():
    start = int(sys.argv[1])
    end = int(sys.argv[2])
    output_file = sys.argv[3]

    manifest = json.loads((ROOT / "apps" / "manifest.json").read_text())

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
    print(f"[Worker] Processing apps[{start}:{end}] = {len(my_apps)} apps")

    results = {}
    batch_size = 5
    successes = 0
    failures = 0

    for i in range(0, len(my_apps), batch_size):
        batch = my_apps[i:i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(my_apps) + batch_size - 1) // batch_size

        print(f"[Worker] Batch {batch_num}/{total_batches} ({len(batch)} apps)...")

        prompt = build_batch_prompt(batch)
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

        # Rate limit between batches
        time.sleep(2)

    Path(output_file).write_text(json.dumps(results, indent=2))
    print(f"[Worker] Done: {successes} succeeded, {failures} failed -> {output_file}")


if __name__ == "__main__":
    main()
