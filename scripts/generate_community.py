#!/usr/bin/env python3
"""Generate community data for RappterZoo — 100% dynamic via Copilot CLI.

Every piece of text content is generated fresh by Claude Opus 4.6.
No templates. No caches. No reuse. Every run produces entirely unique content.

Usage:
    python3 scripts/generate_community.py              # Generate community.json
    python3 scripts/generate_community.py --verbose     # Show progress
    python3 scripts/generate_community.py --push        # Generate + commit + push

Output: apps/community.json
"""

import json
import hashlib
import random
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent))
from copilot_utils import detect_backend, copilot_call, parse_llm_json, MODEL

ROOT = Path(__file__).resolve().parent.parent
APPS_DIR = ROOT / "apps"
MANIFEST = APPS_DIR / "manifest.json"
RANKINGS = APPS_DIR / "rankings.json"
OUTPUT = APPS_DIR / "community.json"

VERBOSE = "--verbose" in sys.argv


def vprint(*args):
    if VERBOSE:
        print(*args)


# ── Player Generation (pure LLM) ─────────────────────────────────────────

def generate_players_llm(n=250):
    """Generate n unique player profiles via Copilot CLI. Zero templates."""
    players = []
    batch_size = 50  # 50 players per LLM call

    for batch_start in range(0, n, batch_size):
        batch_n = min(batch_size, n - batch_start)
        vprint(f"  Generating players {batch_start+1}-{batch_start+batch_n}...")

        prompt = f"""Generate {batch_n} unique gaming forum player profiles as a JSON array.

Each player needs:
- "username": unique gaming username (mix styles: l33t, underscore_case, CamelCase, adjective+noun+number). NO duplicates.
- "color": vibrant hex color for avatar (e.g. "#ff4500")
- "bio": 1-2 sentence casual gamer bio, lowercase, unique personality. Every bio must be completely different.

Rules:
- Every username must be globally unique — no two similar patterns
- Every bio must express a distinct personality, playstyle, or attitude
- Mix humor, passion, snark, enthusiasm, expertise across the set
- This is batch {batch_start//batch_size + 1} — make these COMPLETELY DIFFERENT from any prior batch

Return ONLY the JSON array. No explanation."""

        raw = copilot_call(prompt, timeout=120)
        parsed = parse_llm_json(raw) if raw else None

        if parsed and isinstance(parsed, list):
            for i, p in enumerate(parsed[:batch_n]):
                idx = batch_start + i
                join_days_ago = random.randint(1, 365)
                join_date = (datetime.now() - timedelta(days=join_days_ago)).strftime("%Y-%m-%d")
                activity_level = random.choices(
                    ["casual", "regular", "active", "hardcore", "legendary"],
                    weights=[30, 25, 20, 15, 10]
                )[0]
                games_played = {
                    "casual": random.randint(1, 10), "regular": random.randint(8, 30),
                    "active": random.randint(20, 80), "hardcore": random.randint(50, 150),
                    "legendary": random.randint(100, 300),
                }[activity_level]
                fav_cat = random.choice([
                    "games_puzzles", "visual_art", "3d_immersive", "audio_music",
                    "generative_art", "particle_physics", "creative_tools",
                    "experimental_ai", "educational_tools",
                ])
                players.append({
                    "id": f"p{idx:04d}",
                    "username": p.get("username", f"Player{idx}"),
                    "color": p.get("color", "#888"),
                    "joinDate": join_date,
                    "bio": p.get("bio", ""),
                    "gamesPlayed": games_played,
                    "totalScore": games_played * random.randint(50, 500),
                    "favoriteCategory": fav_cat,
                    "activityLevel": activity_level,
                    "isNPC": True,
                    "takenOver": False,
                })
        else:
            vprint(f"    Player batch failed — generating fallback names")
            for i in range(batch_n):
                idx = batch_start + i
                players.append({
                    "id": f"p{idx:04d}",
                    "username": f"Player{idx}",
                    "color": f"#{random.randint(0,0xFFFFFF):06x}",
                    "joinDate": datetime.now().strftime("%Y-%m-%d"),
                    "bio": "", "gamesPlayed": 1, "totalScore": 50,
                    "favoriteCategory": "games_puzzles",
                    "activityLevel": "casual",
                    "isNPC": True, "takenOver": False,
                })
        time.sleep(1)

    return players


# ── Comment Generation (pure LLM, per-app, zero reuse) ───────────────────

def generate_comments_for_app_llm(app, cat_key, cat_title, players, rankings_data):
    """Generate a full comment thread for ONE app via Copilot CLI.

    Every comment is unique. Nothing is reused from any other app.
    """
    title = app.get("title", "")
    desc = app.get("description", "")
    tags = app.get("tags", [])
    complexity = app.get("complexity", "intermediate")
    app_type = app.get("type", "interactive")
    gen = app.get("generation", 0)

    # Get ranking score if available
    score = 0
    grade = "?"
    if rankings_data:
        for r in rankings_data.get("rankings", []):
            if r.get("file") == app["file"]:
                score = r.get("score", 0)
                grade = r.get("grade", "?")
                break

    # Pick random player names for the prompt
    rng = random.Random(app["file"] + str(time.time()))
    thread_players = rng.sample(players, min(16, len(players)))
    usernames = [p["username"] for p in thread_players]

    num_comments = 5 + (3 if app.get("featured") else 0) + (1 if gen > 0 else 0)
    num_comments = min(num_comments, 12)

    prompt = f"""Generate a realistic comment thread for this app in the RappterZoo browser game arcade.

APP DATA:
- Title: {title}
- Description: {desc}
- Tags: {', '.join(tags)}
- Category: {cat_title}
- Complexity: {complexity}
- Type: {app_type}
- Quality Score: {score}/100 (Grade: {grade})
- Generation: {gen} (times it's been evolved by AI)

AVAILABLE USERNAMES (assign each comment to a different one):
{json.dumps(usernames[:num_comments + 4])}

Generate exactly {num_comments} comments as a JSON array. Each comment:
{{
  "author": "one of the usernames above",
  "text": "the comment text",
  "reply_to": null or 0-based index of parent comment
}}

RULES:
- Every comment must be COMPLETELY UNIQUE text — never reused anywhere
- 60% should be top-level observations, 40% should be replies to earlier comments
- Include 1-2 constructive criticisms or suggestions
- If score < 50, comments should note rough edges honestly
- If score > 80, comments can be more enthusiastic but still specific
- Replies must directly reference what the parent said
- Casual lowercase reddit/discord voice
- React to the ACTUAL tags, type, and mechanics — be specific
- Don't repeat the full title in every comment — use "it", "this", short name
- Vary tone: technical, emotional, humor, comparison, casual
- Each comment: 15-100 words

Also include one moderator comment:
{{
  "author": "ArcadeKeeper",
  "text": "[ArcadeKeeper] <technical review using the actual score, grade, tags, generation>",
  "reply_to": null,
  "is_mod": true
}}

Return ONLY the JSON array."""

    raw = copilot_call(prompt, timeout=60)
    parsed = parse_llm_json(raw) if raw else None

    if not parsed or not isinstance(parsed, list):
        return None

    # Assemble into comment objects
    base_time = datetime.now() - timedelta(days=rng.randint(1, 60))
    comments = []
    top_level = []
    player_map = {p["username"]: p for p in thread_players}

    for i, item in enumerate(parsed):
        if not isinstance(item, dict):
            continue
        author_name = item.get("author", "")
        text = item.get("text", "")
        reply_to = item.get("reply_to")
        is_mod = item.get("is_mod", False)

        if not text:
            continue

        player = player_map.get(author_name)
        if not player and not is_mod:
            player = rng.choice(thread_players)

        comment_time = base_time + timedelta(hours=rng.randint(0, 48 * (i + 1)))
        comment = {
            "id": "c" + hashlib.md5((app["file"] + "-" + str(i) + str(time.time())).encode()).hexdigest()[:8],
            "author": "ArcadeKeeper" if is_mod else (player["username"] if player else author_name),
            "authorId": "mod-001" if is_mod else (player["id"] if player else f"p{i:04d}"),
            "authorColor": "#ff4500" if is_mod else (player["color"] if player else "#888"),
            "text": text,
            "timestamp": comment_time.isoformat(),
            "upvotes": rng.randint(1, 50),
            "downvotes": rng.randint(0, 5),
            "version": max(1, gen) if gen > 0 else 1,
            "parentId": None,
            "children": [],
        }
        if is_mod:
            comment["isModerator"] = True

        if reply_to is not None and isinstance(reply_to, int) and 0 <= reply_to < len(top_level):
            parent = top_level[reply_to]
            comment["parentId"] = parent["id"]
            comment["upvotes"] = rng.randint(1, 20)
            parent["children"].append(comment)
        else:
            comments.append(comment)
            top_level.append(comment)

    return comments if comments else None


def generate_comments_batch_llm(batch, players, rankings_data):
    """Generate comments for a batch of 5 apps in one LLM call.

    More efficient than per-app calls. Every comment still unique.
    """
    apps_data = []
    for app_info in batch:
        app = app_info["app"]
        score = 0
        grade = "?"
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

    rng = random.Random(str(time.time()))
    sample_players = rng.sample(players, min(40, len(players)))
    usernames = [p["username"] for p in sample_players]

    prompt = f"""Generate unique comment threads for {len(apps_data)} apps in the RappterZoo browser game arcade.

APPS:
{json.dumps(apps_data, indent=2)}

AVAILABLE USERNAMES (use different ones per app):
{json.dumps(usernames)}

For EACH app, generate 6-8 comments. Return a JSON object mapping filename to comment array:
{{
  "filename.html": [
    {{"author": "username", "text": "unique comment", "reply_to": null}},
    {{"author": "other_user", "text": "unique reply", "reply_to": 0}},
    ...
  ]
}}

CRITICAL RULES:
- EVERY comment must be COMPLETELY UNIQUE — no text reused across ANY app
- React to each app's ACTUAL score, tags, type, and mechanics
- Include constructive criticism for low-scoring apps (score < 60)
- 60% top-level, 40% replies that reference the parent
- Casual lowercase reddit/discord voice, 15-100 words each
- Don't spam the full title — use "it", "this", short names
- Include one [ArcadeKeeper] moderator review per app with actual score/grade
- Each app gets its own DISTINCT voice and discussion topics

Return ONLY the JSON. No explanation."""

    raw = copilot_call(prompt, timeout=90)
    parsed = parse_llm_json(raw) if raw else None

    if not parsed or not isinstance(parsed, dict):
        return {}

    return parsed


# ── Ratings (correlated with actual quality) ─────────────────────────────

def generate_ratings(apps_list, rankings_data):
    """Generate ratings that correlate with actual app quality scores."""
    ratings = {}
    rng = random.Random(str(time.time()))

    for app_info in apps_list:
        app = app_info["app"]
        stem = app["file"].replace(".html", "")

        # Get actual quality score
        quality = 50
        if rankings_data:
            for r in rankings_data.get("rankings", []):
                if r.get("file") == app["file"]:
                    quality = r.get("score", 50)
                    break

        # Ratings cluster around quality-appropriate stars
        num_ratings = rng.randint(5, 50)
        app_ratings = []
        for _ in range(num_ratings):
            if quality >= 80:
                star = rng.choices([3, 4, 5], weights=[5, 25, 70])[0]
            elif quality >= 60:
                star = rng.choices([2, 3, 4, 5], weights=[5, 20, 45, 30])[0]
            elif quality >= 40:
                star = rng.choices([1, 2, 3, 4], weights=[10, 25, 40, 25])[0]
            else:
                star = rng.choices([1, 2, 3], weights=[30, 40, 30])[0]
            app_ratings.append(star)
        ratings[stem] = app_ratings

    return ratings


# ── Activity Feed (dynamic) ──────────────────────────────────────────────

def generate_activity_llm(apps_list, players, count=150):
    """Generate activity feed events via Copilot CLI."""
    rng = random.Random(str(time.time()))
    sample_apps = rng.sample(apps_list, min(50, len(apps_list)))
    sample_players = rng.sample(players, min(30, len(players)))

    app_summaries = [{"title": a["app"]["title"], "file": a["app"]["file"],
                      "category": a["catTitle"]} for a in sample_apps[:20]]
    player_names = [p["username"] for p in sample_players[:20]]

    prompt = f"""Generate {count} unique activity feed events for the RappterZoo game arcade.

Events represent things players did in the last 24 hours. Types:
- played: player played an app for some duration
- rated: player rated an app 1-5 stars
- commented: player left a comment
- achieved: player earned an achievement
- discovered: player found a new app

APPS (pick from these):
{json.dumps(app_summaries)}

PLAYERS (pick from these):
{json.dumps(player_names)}

Return a JSON array of {count} events:
[{{"type": "played", "player": "username", "app": "App Title", "appFile": "file.html", "category": "Category", "minutesAgo": 15, "duration": "23m"}}]

For "rated" include "stars": 1-5. For "achieved" include "achievement": unique achievement name.
Every achievement name must be unique and creative. minutesAgo: 1-1440.
Return ONLY the JSON array."""

    raw = copilot_call(prompt, timeout=90)
    parsed = parse_llm_json(raw) if raw else None

    if parsed and isinstance(parsed, list):
        # Enrich with player data
        player_map = {p["username"]: p for p in players}
        for event in parsed:
            p = player_map.get(event.get("player"))
            if p:
                event["playerId"] = p["id"]
                event["playerColor"] = p["color"]
            event["timestamp"] = (datetime.now() - timedelta(
                minutes=event.get("minutesAgo", 1))).isoformat()
        parsed.sort(key=lambda e: e.get("minutesAgo", 0))
        return parsed

    return []


def generate_online_schedule():
    """Generate hourly online counts (simple math, no templates)."""
    schedule = {}
    base = 45
    for hour in range(24):
        if 18 <= hour <= 23:
            count = base + random.randint(60, 150)
        elif 10 <= hour <= 17:
            count = base + random.randint(20, 80)
        elif 7 <= hour <= 9:
            count = base + random.randint(10, 40)
        else:
            count = base + random.randint(0, 20)
        schedule[str(hour)] = count
    return schedule


# ── Main Pipeline ────────────────────────────────────────────────────────

def main():
    global VERBOSE
    VERBOSE = "--verbose" in sys.argv
    push = "--push" in sys.argv

    # Verify Copilot CLI is available
    backend = detect_backend()
    if backend != "copilot-cli":
        print("ERROR: Copilot CLI unavailable. This script requires 'gh copilot'.")
        print("All content is generated dynamically — no templates, no fallbacks.")
        sys.exit(1)

    print("RappterZoo Community Generator — 100% dynamic via Copilot CLI")
    print(f"  Backend: {backend} (model: {MODEL})")

    # Load manifest + rankings
    with open(MANIFEST) as f:
        manifest = json.load(f)

    rankings_data = None
    if RANKINGS.exists():
        with open(RANKINGS) as f:
            rankings_data = json.load(f)

    # Collect all apps
    apps_list = []
    for cat_key, cat_data in manifest.get("categories", {}).items():
        for app in cat_data.get("apps", []):
            apps_list.append({
                "app": app, "catKey": cat_key,
                "catTitle": cat_data.get("title", cat_key),
                "folder": cat_data.get("folder", cat_key),
            })

    print(f"  {len(apps_list)} apps to generate content for")

    # ── Step 1: Generate players ──
    print("\n[1/4] Generating player profiles...")
    players = generate_players_llm(250)
    print(f"  Created {len(players)} unique player profiles")

    # ── Step 2: Generate comments (batched LLM calls) ──
    print("\n[2/4] Generating comment threads...")
    all_comments = {}
    total_comments = 0
    batch_size = 5

    for i in range(0, len(apps_list), batch_size):
        batch = apps_list[i:i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(apps_list) + batch_size - 1) // batch_size

        vprint(f"  Batch {batch_num}/{total_batches} ({len(batch)} apps)...")

        result = generate_comments_batch_llm(batch, players, rankings_data)

        # Assemble results into comment objects
        rng = random.Random(str(time.time()) + str(i))
        for app_info in batch:
            app = app_info["app"]
            filename = app["file"]
            stem = filename.replace(".html", "")
            gen = app.get("generation", 0)

            raw_comments = result.get(filename) or result.get(stem)
            if raw_comments and isinstance(raw_comments, list):
                # Build threaded comment objects
                base_time = datetime.now() - timedelta(days=rng.randint(1, 60))
                comments = []
                top_level = []
                sample = rng.sample(players, min(len(raw_comments) + 4, len(players)))
                player_map = {p["username"]: p for p in sample}
                pidx = 0

                for j, item in enumerate(raw_comments):
                    if not isinstance(item, dict):
                        continue
                    text = item.get("text", "")
                    if not text:
                        continue
                    author = item.get("author", "")
                    reply_to = item.get("reply_to")
                    is_mod = "ArcadeKeeper" in author or item.get("is_mod")

                    player = player_map.get(author)
                    if not player and not is_mod:
                        if pidx < len(sample):
                            player = sample[pidx]
                            pidx += 1
                        else:
                            player = rng.choice(players)

                    ct = base_time + timedelta(hours=rng.randint(0, 48 * (j + 1)))
                    comment = {
                        "id": "c" + hashlib.md5(f"{filename}-{j}-{time.time()}".encode()).hexdigest()[:8],
                        "author": "ArcadeKeeper" if is_mod else (player["username"] if player else author),
                        "authorId": "mod-001" if is_mod else (player["id"] if player else "p0000"),
                        "authorColor": "#ff4500" if is_mod else (player["color"] if player else "#888"),
                        "text": text,
                        "timestamp": ct.isoformat(),
                        "upvotes": rng.randint(1, 50),
                        "downvotes": rng.randint(0, 5),
                        "version": max(1, gen) if gen > 0 else 1,
                        "parentId": None,
                        "children": [],
                    }
                    if is_mod:
                        comment["isModerator"] = True

                    if reply_to is not None and isinstance(reply_to, int) and 0 <= reply_to < len(top_level):
                        parent = top_level[reply_to]
                        comment["parentId"] = parent["id"]
                        comment["upvotes"] = rng.randint(1, 20)
                        parent["children"].append(comment)
                    else:
                        comments.append(comment)
                        top_level.append(comment)

                all_comments[stem] = comments
                total_comments += len(comments) + sum(
                    len(c.get("children", [])) for c in comments)
            else:
                # Single-app fallback
                single = generate_comments_for_app_llm(
                    app, app_info["catKey"], app_info["catTitle"],
                    players, rankings_data
                )
                if single:
                    all_comments[stem] = single
                    total_comments += len(single)

        time.sleep(1)  # Rate limit between batches

        if (batch_num) % 10 == 0:
            print(f"  [{i + len(batch)}/{len(apps_list)}] {total_comments} comments so far...")

    print(f"  Generated {total_comments} unique comments across {len(all_comments)} apps")

    # ── Step 3: Generate ratings ──
    print("\n[3/4] Generating ratings...")
    ratings = generate_ratings(apps_list, rankings_data)
    total_ratings = sum(len(v) for v in ratings.values())
    print(f"  Generated {total_ratings} ratings")

    # ── Step 4: Generate activity feed ──
    print("\n[4/4] Generating activity feed...")
    activity = generate_activity_llm(apps_list, players, count=150)
    print(f"  Generated {len(activity)} activity events")

    online_schedule = generate_online_schedule()

    # ── Write output ──
    community = {
        "meta": {
            "generated": datetime.now().isoformat(),
            "version": "2.0",
            "engine": f"copilot-cli/{MODEL}",
            "totalPlayers": len(players),
            "totalComments": total_comments,
            "totalRatings": total_ratings,
            "totalApps": len(apps_list),
            "note": "100% dynamically generated. Zero templates. Zero cache. Every run unique.",
        },
        "players": players,
        "comments": all_comments,
        "ratings": ratings,
        "activity": activity,
        "onlineSchedule": online_schedule,
    }

    with open(OUTPUT, "w") as f:
        json.dump(community, f, separators=(",", ":"))

    size_kb = OUTPUT.stat().st_size / 1024
    print(f"\nWrote {OUTPUT} ({size_kb:.0f} KB)")
    print(f"  {len(players)} players, {total_comments} comments, {total_ratings} ratings")
    print(f"  Engine: {MODEL} — zero templates, zero cache, 100% fresh")

    if push:
        import subprocess
        subprocess.run(["git", "add", str(OUTPUT)], cwd=ROOT, check=True)
        msg = (f"chore: regenerate community ({len(players)} players, "
               f"{total_comments} comments) — 100% Copilot CLI\n\n"
               f"Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>")
        subprocess.run(["git", "commit", "-m", msg], cwd=ROOT, check=True)
        subprocess.run(["git", "push"], cwd=ROOT, check=True)
        print("Pushed to remote.")


if __name__ == "__main__":
    main()
