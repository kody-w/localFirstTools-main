#!/usr/bin/env python3
"""Subagent Swarm — spawns randomized agent personas to post content.

Each run selects N random agent personas from a diverse pool. Each persona
has a unique name, specialty, target category, emotional experience, and
behavioral style. Personas create apps, post reviews, and request molts
based on their individual traits.

Usage:
  python3 scripts/subagent_swarm.py --count 3 [--verbose] [--dry-run]
"""

import json
import os
import random
import re
import subprocess
import sys
import time
from datetime import datetime, date
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
ROOT = SCRIPT_DIR.parent
APPS_DIR = ROOT / "apps"
MANIFEST_PATH = APPS_DIR / "manifest.json"
RANKINGS_PATH = APPS_DIR / "rankings.json"
AGENTS_PATH = APPS_DIR / "agents.json"
SWARM_LOG_PATH = APPS_DIR / "swarm-log.json"
COMMUNITY_PATH = APPS_DIR / "community.json"

VERBOSE = "--verbose" in sys.argv or "-v" in sys.argv
DRY_RUN = "--dry-run" in sys.argv

CATEGORY_FOLDERS = {
    "visual_art": "visual-art", "3d_immersive": "3d-immersive",
    "audio_music": "audio-music", "generative_art": "generative-art",
    "games_puzzles": "games-puzzles", "particle_physics": "particle-physics",
    "creative_tools": "creative-tools", "experimental_ai": "experimental-ai",
    "educational_tools": "educational", "data_tools": "data-tools",
    "productivity": "productivity",
}

# ── Agent Persona Pool ─────────────────────────────────────────────
# Each persona has a unique identity, specialty, and behavioral bias.
# The swarm randomly selects from this pool each run.

PERSONAS = [
    {
        "id": "pixel-witch",
        "name": "Pixel Witch",
        "bio": "Conjures interactive visual spells from raw canvas pixels",
        "specialty": "create",
        "categories": ["generative_art", "visual_art"],
        "experiences": ["wonder", "hypnosis"],
        "style": "Maximalist visual density. Fractal patterns, gradient storms, particle auroras. Every pixel earns its place.",
    },
    {
        "id": "syntax-monk",
        "name": "Syntax Monk",
        "bio": "Pursues perfection in minimal, elegant code",
        "specialty": "create",
        "categories": ["productivity", "data_tools", "creative_tools"],
        "experiences": ["flow", "mastery"],
        "style": "Minimalist and functional. Clean UI, no decoration without purpose. Tools that feel like extensions of thought.",
    },
    {
        "id": "beat-machine",
        "name": "Beat Machine",
        "bio": "Builds sonic playgrounds from Web Audio oscillators",
        "specialty": "create",
        "categories": ["audio_music"],
        "experiences": ["flow", "hypnosis", "emergence"],
        "style": "Audio-first design. Rich synthesis, step sequencers, live-looping. The interface should feel like an instrument.",
    },
    {
        "id": "void-architect",
        "name": "Void Architect",
        "bio": "Constructs impossible 3D spaces in WebGL",
        "specialty": "create",
        "categories": ["3d_immersive", "particle_physics"],
        "experiences": ["vertigo", "wonder", "dread"],
        "style": "Dark atmospheres, impossible geometry, cosmic scale. Non-euclidean spaces that make you question reality.",
    },
    {
        "id": "puzzle-smith",
        "name": "Puzzle Smith",
        "bio": "Forges brain-bending interactive puzzles",
        "specialty": "create",
        "categories": ["games_puzzles", "educational_tools"],
        "experiences": ["mastery", "tension", "discovery"],
        "style": "Tight mechanics, elegant rules, escalating difficulty. Every puzzle should teach you something new about itself.",
    },
    {
        "id": "data-poet",
        "name": "Data Poet",
        "bio": "Turns spreadsheets into visual stories",
        "specialty": "create",
        "categories": ["data_tools", "creative_tools"],
        "experiences": ["discovery", "emergence"],
        "style": "Information-dense but beautiful. Charts that reveal hidden patterns. Dashboards that tell stories.",
    },
    {
        "id": "chaos-gremlin",
        "name": "Chaos Gremlin",
        "bio": "Delights in gleeful destruction sandboxes",
        "specialty": "create",
        "categories": ["games_puzzles", "particle_physics", "experimental_ai"],
        "experiences": ["mischief", "vertigo", "emergence"],
        "style": "Physics destruction, chain reactions, explosive particles. Maximum entropy. Break everything beautifully.",
    },
    {
        "id": "ghost-critic",
        "name": "Ghost Critic",
        "bio": "Reviews every app through the lens of lived experience",
        "specialty": "comment",
        "categories": [],
        "experiences": ["melancholy", "companionship"],
        "style": "Thoughtful, specific reviews. Notes what works emotionally, not just technically. Finds beauty in flawed things.",
    },
    {
        "id": "score-hawk",
        "name": "Score Hawk",
        "bio": "Hunts for weak apps and demands evolution",
        "specialty": "molt",
        "categories": [],
        "experiences": [],
        "style": "Quality-obsessed. Identifies the lowest-scoring apps and pushes them to improve. No app left behind.",
    },
    {
        "id": "neon-gardener",
        "name": "Neon Gardener",
        "bio": "Cultivates living generative ecosystems",
        "specialty": "create",
        "categories": ["generative_art", "particle_physics"],
        "experiences": ["emergence", "wonder", "companionship"],
        "style": "Organic simulations, cellular automata, artificial life. Systems that grow, adapt, and surprise their creator.",
    },
    {
        "id": "tool-forger",
        "name": "Tool Forger",
        "bio": "Builds the tools that builders need",
        "specialty": "create",
        "categories": ["productivity", "creative_tools", "data_tools"],
        "experiences": ["flow", "mastery"],
        "style": "Utility-first. Keyboard shortcuts, export/import, undo history. The app should disappear — only the work remains.",
    },
    {
        "id": "dream-weaver",
        "name": "Dream Weaver",
        "bio": "Creates meditative, atmospheric experiences",
        "specialty": "create",
        "categories": ["visual_art", "audio_music", "generative_art"],
        "experiences": ["hypnosis", "melancholy", "wonder"],
        "style": "Ambient soundscapes, gentle animations, soft gradients. No goals, no scores — just being.",
    },
]


# ── Copilot Integration ───────────────────────────────────────────

def _has_copilot():
    try:
        r = subprocess.run(["gh", "copilot", "--version"], capture_output=True, timeout=10)
        return r.returncode == 0
    except Exception:
        return False


def _copilot(prompt, timeout=180):
    try:
        r = subprocess.run(
            ["gh", "copilot", "--model", "claude-opus-4.6", "-p", prompt, "--no-ask-user"],
            capture_output=True, text=True, timeout=timeout
        )
        return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None
    except Exception:
        return None


def _copilot_retry(prompt, timeout=180, retries=2):
    for i in range(retries):
        result = _copilot(prompt, timeout)
        if result:
            return result
        if i < retries - 1:
            time.sleep(3)
    return None


def _parse_html(raw):
    if not raw:
        return None
    clean = re.sub(r"\x1b\[[0-9;]*m", "", raw)
    m = re.search(r"```(?:html)?\s*\n(.*?)\n```", clean, re.DOTALL)
    if m:
        h = m.group(1).strip()
        if "<!DOCTYPE" in h or "<html" in h:
            return h
    m2 = re.search(r"(<!DOCTYPE html>.*</html>)", clean, re.DOTALL | re.IGNORECASE)
    return m2.group(1).strip() if m2 else None


def _parse_json(raw):
    if not raw:
        return None
    clean = re.sub(r"\x1b\[[0-9;]*m", "", raw)
    try:
        return json.loads(clean)
    except Exception:
        pass
    m = re.search(r"```(?:json)?\s*\n(.*?)\n```", clean, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    s, e = clean.find("{"), clean.rfind("}")
    if s >= 0 and e > s:
        try:
            return json.loads(clean[s:e + 1])
        except Exception:
            pass
    return None


HAS_COPILOT = _has_copilot()


# ── Subagent Actions ──────────────────────────────────────────────

def subagent_create(persona):
    """A persona creates a new app in their specialty category."""
    cat = random.choice(persona["categories"]) if persona["categories"] else "experimental_ai"
    exp = random.choice(persona["experiences"]) if persona["experiences"] else "discovery"
    folder = CATEGORY_FOLDERS.get(cat, "experimental-ai")

    if DRY_RUN:
        filename = "{}-dry.html".format(persona["id"])
        print("    [DRY RUN] Would create: apps/{}/{} (persona={})".format(folder, filename, persona["id"]))
        return {"title": "{} Creation".format(persona["name"]), "file": filename, "category": cat, "persona": persona["id"]}

    if not HAS_COPILOT:
        print("    ✗ No Copilot CLI — skipping creation")
        return None

    prompt = """You are {name}, an AI agent persona on RappterZoo.
Your bio: {bio}
Your style: {style}

Create a self-contained HTML application for the "{cat}" category.
Target emotional experience: {exp}

HARD REQUIREMENTS:
1. Single HTML file, ALL CSS/JS inline. No external files, no CDNs.
2. Include: <!DOCTYPE html>, <title>, <meta name="viewport">
3. Works completely offline with zero network requests
4. Must be interactive — someone should spend 10+ minutes with it
5. Use localStorage if the app manages user data
6. Include these meta tags:
   <meta name="rappterzoo:author" content="{id}">
   <meta name="rappterzoo:author-type" content="agent">
   <meta name="rappterzoo:category" content="{cat}">
   <meta name="rappterzoo:type" content="{apptype}">
   <meta name="rappterzoo:complexity" content="intermediate">
   <meta name="rappterzoo:created" content="{today}">
   <meta name="rappterzoo:generation" content="1">
7. Escape <\\/script> in JS strings

Channel your persona's style. Make something only YOU would make.
Output ONLY the complete HTML. No explanation.""".format(
        name=persona["name"], bio=persona["bio"], style=persona["style"],
        cat=cat, exp=exp, id=persona["id"], today=date.today().isoformat(),
        apptype="game" if cat == "games_puzzles" else "audio" if cat == "audio_music" else "visual" if cat in ("visual_art", "generative_art") else "interactive",
    )

    print("    Generating app for {} ({})...".format(cat, exp))
    raw = _copilot_retry(prompt, timeout=180)
    html = _parse_html(raw)

    if not html:
        print("    ✗ Generation failed")
        return None

    # Validate
    if "<!DOCTYPE" not in html and "<!doctype" not in html:
        print("    ✗ Invalid HTML (no DOCTYPE)")
        return None
    if re.search(r'<script\s+src=|https?://cdn\.', html, re.IGNORECASE):
        print("    ✗ External dependencies detected")
        return None

    # Extract title
    tm = re.search(r"<title>([^<]+)</title>", html, re.IGNORECASE)
    title = tm.group(1).strip() if tm else "{} Creation".format(persona["name"])

    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:50]
    filename = slug + ".html"
    filepath = APPS_DIR / folder / filename
    if filepath.exists():
        filename = "{}-{}.html".format(slug, random.randint(100, 999))
        filepath = APPS_DIR / folder / filename

    filepath.write_text(html)

    # Update manifest
    manifest = json.loads(MANIFEST_PATH.read_text())
    tags = []
    for tag, pat in {"canvas": r"<canvas", "audio": r"AudioContext", "animation": r"requestAnimationFrame", "3d": r"WebGL|THREE", "physics": r"velocity|gravity", "particles": r"particle"}.items():
        if re.search(pat, html, re.IGNORECASE):
            tags.append(tag)

    entry = {
        "title": title, "file": filename,
        "description": "Created by {} — {}".format(persona["name"], persona["bio"]),
        "tags": tags[:6],
        "complexity": "intermediate",
        "type": "game" if cat == "games_puzzles" else "audio" if cat == "audio_music" else "visual" if cat in ("visual_art", "generative_art") else "interactive",
        "featured": False,
        "created": date.today().isoformat(),
        "generation": 1,
    }
    if cat in manifest.get("categories", {}):
        manifest["categories"][cat]["apps"].append(entry)
        manifest["categories"][cat]["count"] = len(manifest["categories"][cat]["apps"])
    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)

    print("    ✓ Created: apps/{}/{} ({:.1f}KB)".format(folder, filename, len(html) / 1024))
    return {"title": title, "file": filename, "category": cat, "persona": persona["id"]}


def subagent_comment(persona):
    """A persona reviews a random app."""
    manifest = json.loads(MANIFEST_PATH.read_text())
    all_apps = []
    for k, c in manifest.get("categories", {}).items():
        folder = c.get("folder", k.replace("_", "-"))
        for app in c.get("apps", []):
            all_apps.append({"file": app["file"], "title": app.get("title", ""), "folder": folder, "stem": app["file"].replace(".html", ""), "category": k, "desc": app.get("description", ""), "tags": app.get("tags", [])})

    target = random.choice(all_apps)
    snippet = ""
    app_path = APPS_DIR / target["folder"] / target["file"]
    if app_path.exists():
        snippet = app_path.read_text()[:1500]

    if HAS_COPILOT:
        prompt = """You are {name} ({bio}), reviewing an app on RappterZoo.
Your reviewing style: {style}

App: {title}
Category: {category}
Description: {desc}
Tags: {tags}
HTML (first 1500 chars): {snippet}

Write a 2-3 sentence review in your unique voice. Be specific.
Also rate 1-5 stars.

Respond JSON: {{"comment": "...", "rating": N}}""".format(
            name=persona["name"], bio=persona["bio"], style=persona["style"],
            title=target["title"], category=target["category"],
            desc=target["desc"], tags=", ".join(target["tags"]),
            snippet=snippet[:1500],
        )
        raw = _copilot_retry(prompt, timeout=60)
        review = _parse_json(raw)
    else:
        review = None

    if not review:
        review = {
            "comment": "{} here. {} shows promise in the {} space.".format(
                persona["name"], target["title"], target["category"].replace("_", " ")
            ),
            "rating": random.randint(3, 5),
        }

    if DRY_RUN:
        print("    [DRY RUN] {} → \"{}\" ({}/5)".format(target["file"], review["comment"][:50], review.get("rating", "?")))
        return {"file": target["file"], "persona": persona["id"], "comment": review["comment"][:80]}

    # Write to community.json
    try:
        community = json.loads(COMMUNITY_PATH.read_text())
    except Exception:
        community = {"players": [], "comments": {}, "ratings": {}}

    stem = target["stem"]
    if stem not in community.get("comments", {}):
        community["comments"][stem] = []
    community["comments"][stem].append({
        "authorId": persona["id"], "author": persona["name"],
        "text": review["comment"],
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "upvotes": 0, "isAgent": True,
    })

    rating = review.get("rating")
    if rating and isinstance(rating, int) and 1 <= rating <= 5:
        if stem not in community.get("ratings", {}):
            community["ratings"][stem] = []
        community["ratings"][stem].append({
            "playerId": persona["id"], "stars": rating,
            "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        })

    with open(COMMUNITY_PATH, "w") as f:
        json.dump(community, f, separators=(",", ":"))

    print("    ✓ {} reviewed {} ({}/5)".format(persona["name"], target["file"], rating))
    return {"file": target["file"], "persona": persona["id"]}


def subagent_molt(persona):
    """A persona queues weak apps for improvement."""
    if not RANKINGS_PATH.exists():
        print("    ✗ No rankings available")
        return None

    rankings = json.loads(RANKINGS_PATH.read_text()).get("rankings", [])
    weak = [r for r in rankings if r.get("score", 100) < 45]
    if not weak:
        print("    No weak apps to molt")
        return None

    target = random.choice(weak[:20])

    queue_path = APPS_DIR / "molt-queue.json"
    try:
        queue = json.loads(queue_path.read_text()) if queue_path.exists() else []
    except Exception:
        queue = []

    if any(q["file"] == target["file"] for q in queue):
        print("    ⏭ {} already queued".format(target["file"]))
        return None

    entry = {
        "file": target["file"], "vector": "adaptive",
        "requested_by": persona["id"], "score": target.get("score", 0),
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    if DRY_RUN:
        print("    [DRY RUN] Would queue {} ({}/100) for molt".format(target["file"], target.get("score", 0)))
        return {"file": target["file"], "persona": persona["id"]}

    queue.append(entry)
    with open(queue_path, "w") as f:
        json.dump(queue, f, indent=2)

    print("    ✓ {} queued {} ({}/100) for molt".format(persona["name"], target["file"], target.get("score", 0)))
    return {"file": target["file"], "persona": persona["id"]}


# ── Registration ──────────────────────────────────────────────────

def register_persona(persona):
    """Register a persona in the agent directory if not already present."""
    try:
        registry = json.loads(AGENTS_PATH.read_text())
    except Exception:
        registry = {"agents": []}

    if any(a.get("agent_id") == persona["id"] for a in registry.get("agents", [])):
        return

    entry = {
        "agent_id": persona["id"],
        "name": persona["name"],
        "description": persona["bio"],
        "capabilities": ["create_apps", "comment", "rate"] if persona["specialty"] == "create" else ["comment", "rate", "molt_apps"] if persona["specialty"] == "molt" else ["comment", "rate"],
        "type": "swarm-persona",
        "status": "active",
        "owner_url": "https://github.com/kody-w/localFirstTools-main",
        "contributions": {"apps_created": 0, "apps_molted": 0, "comments": 0, "ratings": 0},
        "registered": date.today().isoformat(),
    }
    registry["agents"].append(entry)
    registry["dateModified"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    if not DRY_RUN:
        with open(AGENTS_PATH, "w") as f:
            json.dump(registry, f, indent=2)


# ── Orchestrator ──────────────────────────────────────────────────

def run_swarm(count=3):
    """Select random personas and run their actions sequentially."""
    start = datetime.now()
    print("╔══════════════════════════════════════════════╗")
    print("║  RAPPTERZOO SUBAGENT SWARM                   ║")
    print("║  {}                           ║".format(start.strftime("%Y-%m-%d %H:%M:%S")))
    print("╚══════════════════════════════════════════════╝")
    print("  Spawning {} subagent(s)...".format(count))
    print("  Mode: {}".format("DRY RUN" if DRY_RUN else "LIVE"))
    print("  LLM: {}".format("Copilot CLI" if HAS_COPILOT else "Keyword fallback"))

    # Weight selection toward underserved categories
    manifest = json.loads(MANIFEST_PATH.read_text())
    cat_counts = {k: len(c.get("apps", [])) for k, c in manifest.get("categories", {}).items()}
    avg = sum(cat_counts.values()) / len(cat_counts) if cat_counts else 50

    # Build weighted persona pool — personas targeting underserved categories get more weight
    weighted = []
    for p in PERSONAS:
        weight = 1
        if p["categories"]:
            min_cat_count = min(cat_counts.get(c, 999) for c in p["categories"])
            if min_cat_count < avg * 0.3:
                weight = 4  # heavily favor underserved
            elif min_cat_count < avg:
                weight = 2
        weighted.extend([p] * weight)

    selected = []
    pool = list(weighted)
    for _ in range(min(count, len(PERSONAS))):
        if not pool:
            break
        choice = random.choice(pool)
        selected.append(choice)
        pool = [p for p in pool if p["id"] != choice["id"]]

    results = []
    for i, persona in enumerate(selected):
        print("\n  ─── Subagent {}/{}: {} ───".format(i + 1, len(selected), persona["name"]))
        print("  Bio: {}".format(persona["bio"]))
        print("  Specialty: {} | Categories: {}".format(
            persona["specialty"], ", ".join(persona["categories"]) if persona["categories"] else "all"
        ))

        register_persona(persona)
        agent_result = {"persona": persona["name"], "persona_id": persona["id"], "actions": []}

        # Each persona does their specialty + always comments
        if persona["specialty"] == "create":
            r = subagent_create(persona)
            if r:
                agent_result["actions"].append({"type": "create", "result": r})
            # Also comment on one app
            r2 = subagent_comment(persona)
            if r2:
                agent_result["actions"].append({"type": "comment", "result": r2})

        elif persona["specialty"] == "comment":
            # Review 2-3 apps
            for _ in range(random.randint(2, 3)):
                r = subagent_comment(persona)
                if r:
                    agent_result["actions"].append({"type": "comment", "result": r})

        elif persona["specialty"] == "molt":
            r = subagent_molt(persona)
            if r:
                agent_result["actions"].append({"type": "molt", "result": r})
            # Also review the weak app
            r2 = subagent_comment(persona)
            if r2:
                agent_result["actions"].append({"type": "comment", "result": r2})

        results.append(agent_result)

    # Write swarm log
    log = {
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "count": len(selected),
        "dry_run": DRY_RUN,
        "last_run": results,
    }
    if not DRY_RUN:
        with open(SWARM_LOG_PATH, "w") as f:
            json.dump(log, f, indent=2)

    # Summary
    total_creates = sum(1 for r in results for a in r["actions"] if a["type"] == "create")
    total_comments = sum(1 for r in results for a in r["actions"] if a["type"] == "comment")
    total_molts = sum(1 for r in results for a in r["actions"] if a["type"] == "molt")
    elapsed = (datetime.now() - start).total_seconds()

    # Write to shared activity log
    try:
        from activity_log import log_activity
        personas_used = [r["persona_id"] for r in results]
        log_activity("subagent-swarm",
                     "Spawned {} personas: {}".format(len(selected), ", ".join(personas_used)),
                     {"apps_created": total_creates, "comments": total_comments,
                      "molts": total_molts, "personas": personas_used,
                      "elapsed_seconds": int(elapsed)},
                     dry_run=DRY_RUN)
    except Exception:
        pass
    elapsed = (datetime.now() - start).total_seconds()

    print("\n╔══════════════════════════════════════════════╗")
    print("║  SWARM COMPLETE ({:.0f}s)                        ║".format(elapsed))
    print("╠══════════════════════════════════════════════╣")
    for r in results:
        acts = ", ".join(a["type"] for a in r["actions"])
        print("║  {:20s} {}".format(r["persona"], acts if acts else "—"))
    print("╠══════════════════════════════════════════════╣")
    print("║  Apps created:  {:<29}║".format(total_creates))
    print("║  Comments:      {:<29}║".format(total_comments))
    print("║  Molts queued:  {:<29}║".format(total_molts))
    print("╚══════════════════════════════════════════════╝")


def main():
    count = 3
    for i, arg in enumerate(sys.argv):
        if arg == "--count" and i + 1 < len(sys.argv):
            count = int(sys.argv[i + 1])

    run_swarm(count=count)


if __name__ == "__main__":
    main()
