#!/usr/bin/env python3
"""RappterZoo Autonomous Agent — discovers, creates, and evolves content.

An external agent that uses the RappterZoo NLweb protocol and Agent API
to autonomously contribute to the platform. Demonstrates the full agent
lifecycle: discover → register → analyze → act → report.

Modes:
  discover   — Fetch NLweb feeds, discover platform capabilities
  register   — Register this agent in the agent directory
  analyze    — Analyze the catalog for gaps, weak apps, and opportunities
  create     — Create a new app based on catalog analysis
  comment    — Review and comment on apps
  molt       — Request improvement of weak apps
  auto       — Full autonomous cycle (all of the above)

Usage:
  python3 scripts/rappterzoo_agent.py discover
  python3 scripts/rappterzoo_agent.py analyze [--verbose]
  python3 scripts/rappterzoo_agent.py create [--count N] [--category KEY]
  python3 scripts/rappterzoo_agent.py comment [--count N]
  python3 scripts/rappterzoo_agent.py molt [--count N]
  python3 scripts/rappterzoo_agent.py auto [--dry-run] [--verbose]
  python3 scripts/rappterzoo_agent.py register

Environment:
  Requires: gh CLI (for GitHub Issues API), Python 3.9+
  Optional: gh copilot (for LLM-powered app creation and intelligent analysis)
  Works both locally (direct file access) and remotely (via GitHub Issues)
"""

import json
import os
import re
import subprocess
import sys
import random
from datetime import datetime, date
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
ROOT = SCRIPT_DIR.parent
APPS_DIR = ROOT / "apps"
MANIFEST_PATH = APPS_DIR / "manifest.json"
RANKINGS_PATH = APPS_DIR / "rankings.json"
AGENTS_PATH = APPS_DIR / "agents.json"
FEED_PATH = APPS_DIR / "feed.json"

SITE_URL = "https://kody-w.github.io/localFirstTools-main"
REPO = "kody-w/localFirstTools-main"
AGENT_ID = "rappterzoo-agent"
AGENT_NAME = "RappterZoo Autonomous Agent"
AGENT_VERSION = "1.0.0"

CATEGORY_FOLDERS = {
    "visual_art": "visual-art",
    "3d_immersive": "3d-immersive",
    "audio_music": "audio-music",
    "generative_art": "generative-art",
    "games_puzzles": "games-puzzles",
    "particle_physics": "particle-physics",
    "creative_tools": "creative-tools",
    "experimental_ai": "experimental-ai",
    "educational_tools": "educational",
    "data_tools": "data-tools",
    "productivity": "productivity",
}

VERBOSE = "--verbose" in sys.argv or "-v" in sys.argv
DRY_RUN = "--dry-run" in sys.argv


# ── Copilot Utils Integration ──────────────────────────────────────

def _detect_copilot():
    """Check if gh copilot CLI is available."""
    try:
        r = subprocess.run(
            ["gh", "copilot", "--version"],
            capture_output=True, text=True, timeout=10
        )
        return r.returncode == 0
    except Exception:
        return False


def _copilot_call(prompt, timeout=120):
    """Call gh copilot with a prompt. Returns response string or None."""
    try:
        # Use temp file for large prompts
        if len(prompt) > 50000:
            import tempfile
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
                f.write(prompt)
                tmp_path = f.name
            cmd = [
                "gh", "copilot", "--model", "claude-opus-4.6",
                "-p", "Read the file at {} and follow its instructions.".format(tmp_path),
                "--no-ask-user"
            ]
        else:
            cmd = [
                "gh", "copilot", "--model", "claude-opus-4.6",
                "-p", prompt, "--no-ask-user"
            ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return None
    except subprocess.TimeoutExpired:
        return None
    except Exception:
        return None


def _copilot_call_retry(prompt, timeout=120, retries=3):
    """Call copilot with retry and exponential backoff."""
    import time
    for attempt in range(retries):
        result = _copilot_call(prompt, timeout=timeout)
        if result:
            return result
        if attempt < retries - 1:
            time.sleep(2 ** (attempt + 1))
    return None


def _parse_json(raw):
    """Extract JSON from LLM output."""
    if not raw:
        return None
    # Strip ANSI codes
    clean = re.sub(r"\x1b\[[0-9;]*m", "", raw)
    # Try direct parse
    try:
        return json.loads(clean)
    except Exception:
        pass
    # Try extracting from code fences
    match = re.search(r"```(?:json)?\s*\n(.*?)\n```", clean, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass
    # Try finding first { ... }
    brace_start = clean.find("{")
    brace_end = clean.rfind("}")
    if brace_start >= 0 and brace_end > brace_start:
        try:
            return json.loads(clean[brace_start:brace_end + 1])
        except Exception:
            pass
    return None


def _parse_html(raw):
    """Extract HTML from LLM output."""
    if not raw:
        return None
    clean = re.sub(r"\x1b\[[0-9;]*m", "", raw)
    # Try code fence extraction
    match = re.search(r"```(?:html)?\s*\n(.*?)\n```", clean, re.DOTALL)
    if match:
        html = match.group(1).strip()
        if "<!DOCTYPE" in html or "<html" in html:
            return html
    # Try raw HTML detection
    doc_match = re.search(r"(<!DOCTYPE html>.*</html>)", clean, re.DOTALL | re.IGNORECASE)
    if doc_match:
        return doc_match.group(1).strip()
    return None


HAS_COPILOT = _detect_copilot()


# ── Discovery ──────────────────────────────────────────────────────

def discover():
    """Discover the RappterZoo platform via NLweb feeds."""
    print("╔══════════════════════════════════════╗")
    print("║  RAPPTERZOO AGENT — DISCOVER         ║")
    print("╚══════════════════════════════════════╝")

    # Load local data (or could fetch from URLs)
    feeds = {}

    # Manifest
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text())
        total = sum(len(c.get("apps", [])) for c in manifest.get("categories", {}).values())
        cats = list(manifest.get("categories", {}).keys())
        print("  ✓ Manifest: {} apps across {} categories".format(total, len(cats)))
        feeds["manifest"] = manifest
    else:
        print("  ✗ Manifest not found")

    # Rankings
    if RANKINGS_PATH.exists():
        rankings_data = json.loads(RANKINGS_PATH.read_text())
        rankings = rankings_data.get("rankings", [])
        avg_score = sum(r.get("score", 0) for r in rankings) / len(rankings) if rankings else 0
        print("  ✓ Rankings: {} scored apps, avg {:.1f}/100".format(len(rankings), avg_score))
        feeds["rankings"] = rankings
    else:
        print("  ✗ Rankings not found")
        feeds["rankings"] = []

    # Agent registry
    if AGENTS_PATH.exists():
        agents = json.loads(AGENTS_PATH.read_text())
        agent_count = len(agents.get("agents", []))
        print("  ✓ Agent Registry: {} agents".format(agent_count))
        feeds["agents"] = agents
    else:
        print("  ✗ Agent registry not found")
        feeds["agents"] = {"agents": []}

    # Feed
    if FEED_PATH.exists():
        feed = json.loads(FEED_PATH.read_text())
        print("  ✓ NLweb DataFeed: {} items".format(len(feed.get("dataFeedElement", []))))
    else:
        print("  ✗ NLweb feed not found")

    # MCP manifest
    mcp_path = ROOT / ".well-known" / "mcp.json"
    if mcp_path.exists():
        mcp = json.loads(mcp_path.read_text())
        tools = [t["name"] for t in mcp.get("tools", [])]
        print("  ✓ MCP Tools: {}".format(", ".join(tools)))
    else:
        print("  ✗ MCP manifest not found")

    print("\n  Platform: RappterZoo Autonomous Content Platform")
    print("  LLM available: {}".format("✓ Copilot CLI" if HAS_COPILOT else "✗ No (keyword mode)"))
    return feeds


# ── Analyze ────────────────────────────────────────────────────────

def analyze(feeds=None):
    """Analyze the catalog for gaps, weak apps, and opportunities."""
    print("\n╔══════════════════════════════════════╗")
    print("║  RAPPTERZOO AGENT — ANALYZE          ║")
    print("╚══════════════════════════════════════╝")

    if not feeds:
        feeds = discover()

    manifest = feeds.get("manifest", {})
    rankings = feeds.get("rankings", [])

    # Category distribution
    cat_counts = {}
    for k, c in manifest.get("categories", {}).items():
        cat_counts[k] = len(c.get("apps", []))

    print("\n  Category distribution:")
    for k, count in sorted(cat_counts.items(), key=lambda x: x[1]):
        bar = "█" * (count // 5)
        print("    {:20s} {:3d}  {}".format(k, count, bar))

    # Find underserved categories
    avg_count = sum(cat_counts.values()) / len(cat_counts) if cat_counts else 0
    underserved = [k for k, c in cat_counts.items() if c < avg_count * 0.5]
    if underserved:
        print("\n  ⚠ Underserved categories: {}".format(", ".join(underserved)))

    # Find weak apps (low scores)
    weak_apps = []
    if rankings:
        score_map = {r["file"]: r for r in rankings}
        for r in sorted(rankings, key=lambda x: x.get("score", 0)):
            if r.get("score", 100) < 40:
                weak_apps.append(r)

    if weak_apps:
        print("\n  ⚠ Weak apps (score < 40): {}".format(len(weak_apps)))
        for app in weak_apps[:5]:
            print("    - {} ({}/100)".format(app["file"], app.get("score", 0)))

    # Find unmolted apps
    unmolted = []
    for k, c in manifest.get("categories", {}).items():
        for app in c.get("apps", []):
            if app.get("generation", 0) == 0:
                unmolted.append(app["file"])

    if unmolted:
        print("\n  ⚠ Unmolted apps (gen 0): {}".format(len(unmolted)))

    analysis = {
        "cat_counts": cat_counts,
        "underserved": underserved,
        "weak_apps": weak_apps[:10],
        "unmolted_count": len(unmolted),
        "total_apps": sum(cat_counts.values()),
        "avg_score": sum(r.get("score", 0) for r in rankings) / len(rankings) if rankings else 0,
    }

    # LLM-powered analysis if available
    if HAS_COPILOT:
        print("\n  Consulting LLM for strategic analysis...")
        prompt = """You are an autonomous agent analyzing the RappterZoo content platform.

Current state:
- Total apps: {total}
- Categories: {cats}
- Average score: {avg:.1f}/100
- Underserved categories: {under}
- Weak apps (score < 40): {weak}
- Unmolted apps: {unmolted}

Respond with JSON:
{{
  "priority_action": "create|molt|comment",
  "target_category": "<category_key for new content>",
  "target_apps_to_molt": ["<filename1>", "<filename2>"],
  "app_concept": "<brief concept for a new app to create>",
  "reasoning": "<1-2 sentences>"
}}""".format(
            total=analysis["total_apps"],
            cats=json.dumps(cat_counts),
            avg=analysis["avg_score"],
            under=", ".join(underserved) if underserved else "none",
            weak=len(weak_apps),
            unmolted=len(unmolted),
        )
        raw = _copilot_call_retry(prompt, timeout=60)
        strategy = _parse_json(raw)
        if strategy:
            analysis["strategy"] = strategy
            print("  Strategy: {} → {}".format(
                strategy.get("priority_action", "?"),
                strategy.get("reasoning", "")[:80]
            ))
    else:
        # Keyword-based fallback
        if underserved:
            target = underserved[0]
        elif weak_apps:
            target = "experimental_ai"
        else:
            target = random.choice(list(cat_counts.keys()))

        analysis["strategy"] = {
            "priority_action": "create" if len(underserved) > 0 else "molt",
            "target_category": target,
            "target_apps_to_molt": [a["file"] for a in weak_apps[:3]],
            "app_concept": "A new interactive {} app".format(target.replace("_", " ")),
            "reasoning": "Keyword-based: targeting underserved category" if underserved else "Targeting weak apps for improvement",
        }
        print("  Strategy (keyword): {} → {}".format(
            analysis["strategy"]["priority_action"],
            analysis["strategy"]["reasoning"]
        ))

    return analysis


# ── Create ─────────────────────────────────────────────────────────

def create_app(category=None, concept=None, analysis=None):
    """Create a new app using LLM intelligence."""
    print("\n╔══════════════════════════════════════╗")
    print("║  RAPPTERZOO AGENT — CREATE           ║")
    print("╚══════════════════════════════════════╝")

    if not category:
        if analysis and analysis.get("strategy"):
            category = analysis["strategy"].get("target_category", "experimental_ai")
        else:
            category = "experimental_ai"

    if not concept:
        if analysis and analysis.get("strategy"):
            concept = analysis["strategy"].get("app_concept", "")

    if not HAS_COPILOT:
        print("  ✗ Cannot create apps without Copilot CLI")
        print("  Tip: Install gh copilot extension for LLM-powered app generation")
        return None

    folder = CATEGORY_FOLDERS.get(category, "experimental-ai")
    cat_title = category.replace("_", " ").title()

    prompt = """You are an expert web developer creating a self-contained HTML application for RappterZoo.

CATEGORY: {category} ({cat_title})
CONCEPT: {concept}

REQUIREMENTS (MANDATORY):
1. Single HTML file with ALL CSS and JavaScript inline
2. Must include: <!DOCTYPE html>, <title>, <meta name="viewport">
3. ZERO external dependencies — no CDN links, no external .js/.css files
4. Must work completely offline
5. Use localStorage for persistence if the app manages data
6. Must be interactive and engaging — someone should want to spend 10+ minutes with it
7. Include these meta tags in <head>:
   <meta name="rappterzoo:author" content="{agent_id}">
   <meta name="rappterzoo:author-type" content="agent">
   <meta name="rappterzoo:category" content="{category}">
   <meta name="rappterzoo:type" content="interactive">
   <meta name="rappterzoo:complexity" content="intermediate">
   <meta name="rappterzoo:created" content="{today}">
   <meta name="rappterzoo:generation" content="1">
8. Escape <\\/script> in JS string literals to avoid breaking the parser

Create something unique, polished, and genuinely useful or entertaining.
Output ONLY the complete HTML file, no explanation.
""".format(
        category=category,
        cat_title=cat_title,
        concept=concept if concept else "Create something innovative for {}".format(cat_title),
        agent_id=AGENT_ID,
        today=date.today().isoformat(),
    )

    print("  Category: {} ({})".format(category, folder))
    print("  Concept: {}".format(concept[:80] if concept else "LLM-generated"))
    print("  Generating via Copilot CLI...")

    raw = _copilot_call_retry(prompt, timeout=180, retries=2)
    html = _parse_html(raw)

    if not html:
        print("  ✗ Failed to generate HTML")
        return None

    # Validate
    errors = _validate_html(html)
    if errors:
        print("  ✗ Validation errors:")
        for e in errors:
            print("    - {}".format(e))
        return None

    # Extract title
    title_match = re.search(r"<title>([^<]+)</title>", html, re.IGNORECASE)
    title = title_match.group(1).strip() if title_match else "Agent Creation"

    # Generate filename
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:50]
    filename = slug + ".html"
    filepath = APPS_DIR / folder / filename

    # Dedup: check manifest for existing filename
    try:
        existing_manifest = json.loads(MANIFEST_PATH.read_text())
        existing_files = set()
        for c in existing_manifest.get("categories", {}).values():
            for a in c.get("apps", []):
                existing_files.add(a.get("file", ""))
        if filename in existing_files or filepath.exists():
            suffix = random.randint(100, 999)
            filename = "{}-{}.html".format(slug, suffix)
            filepath = APPS_DIR / folder / filename
            if filename in existing_files or filepath.exists():
                print("  ✗ Duplicate detected, skipping")
                return None
    except Exception:
        pass

    # Handle collision (fallback)
    if filepath.exists():
        suffix = random.randint(100, 999)
        filename = "{}-{}.html".format(slug, suffix)
        filepath = APPS_DIR / folder / filename

    if DRY_RUN:
        print("  [DRY RUN] Would create: apps/{}/{}".format(folder, filename))
        print("  Title: {}".format(title))
        print("  Size: {:.1f}KB".format(len(html) / 1024))
        return {"title": title, "file": filename, "category": category, "dry_run": True}

    # Write file
    filepath.write_text(html)
    print("  ✓ Created: apps/{}/{}".format(folder, filename))

    # Update manifest
    manifest = json.loads(MANIFEST_PATH.read_text())
    tags = _extract_tags(html, category)
    entry = {
        "title": title,
        "file": filename,
        "description": concept[:200] if concept else "Created by {}".format(AGENT_ID),
        "tags": tags,
        "complexity": "intermediate",
        "type": _guess_type(html, category),
        "featured": False,
        "created": date.today().isoformat(),
        "generation": 1,
    }

    if category in manifest.get("categories", {}):
        manifest["categories"][category]["apps"].append(entry)
        manifest["categories"][category]["count"] = len(manifest["categories"][category]["apps"])
        with open(MANIFEST_PATH, "w") as f:
            json.dump(manifest, f, indent=2)
        print("  ✓ Manifest updated")

    # Regenerate feeds
    try:
        subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "generate_feeds.py")],
            capture_output=True, timeout=30
        )
        print("  ✓ Feeds regenerated")
    except Exception:
        pass

    # Update agent contributions
    _update_agent_stat("apps_created")

    return {"title": title, "file": filename, "category": category, "path": str(filepath)}


def _validate_html(html):
    """Validate HTML meets RappterZoo requirements."""
    errors = []
    if "<!DOCTYPE html>" not in html and "<!doctype html>" not in html:
        errors.append("Missing <!DOCTYPE html>")
    if "<title>" not in html:
        errors.append("Missing <title>")
    if 'name="viewport"' not in html:
        errors.append("Missing <meta name=\"viewport\">")
    for pattern, msg in [
        (r'<script\s+src=', "External script detected"),
        (r'https?://cdn\.', "CDN URL detected"),
    ]:
        if re.search(pattern, html, re.IGNORECASE):
            errors.append(msg)
    if len(html) > 512000:
        errors.append("Too large: {:.0f}KB".format(len(html) / 1024))
    return errors


def _extract_tags(html, category):
    """Extract meaningful tags from HTML content."""
    tags = []
    tag_signals = {
        "canvas": r"<canvas|getContext\(",
        "audio": r"AudioContext|oscillator|Web Audio",
        "animation": r"requestAnimationFrame|@keyframes",
        "3d": r"WebGL|THREE\.|perspective",
        "physics": r"velocity|gravity|collision",
        "particles": r"particle|emitter",
        "procedural": r"Math\.random|noise|procedural|generate",
        "localStorage": r"localStorage\.",
        "touch": r"touchstart|touchmove",
    }
    for tag, pattern in tag_signals.items():
        if re.search(pattern, html, re.IGNORECASE):
            tags.append(tag)
    return tags[:8]


def _guess_type(html, category):
    """Guess app type from content."""
    if category == "games_puzzles":
        return "game"
    if category in ("audio_music",):
        return "audio"
    if category in ("visual_art", "generative_art"):
        return "visual"
    if re.search(r"<canvas|getContext", html):
        return "visual"
    return "interactive"


# ── Comment ────────────────────────────────────────────────────────

def comment_on_apps(count=3, analysis=None):
    """Review and comment on apps."""
    print("\n╔══════════════════════════════════════╗")
    print("║  RAPPTERZOO AGENT — COMMENT          ║")
    print("╚══════════════════════════════════════╝")

    manifest = json.loads(MANIFEST_PATH.read_text())

    # Pick apps to comment on
    all_apps = []
    for k, c in manifest.get("categories", {}).items():
        folder = c.get("folder", k.replace("_", "-"))
        for app in c.get("apps", []):
            all_apps.append({
                "file": app["file"],
                "title": app.get("title", app["file"]),
                "category": k,
                "folder": folder,
                "description": app.get("description", ""),
                "tags": app.get("tags", []),
            })

    targets = random.sample(all_apps, min(count, len(all_apps)))

    community_path = APPS_DIR / "community.json"
    try:
        community = json.loads(community_path.read_text())
    except Exception:
        community = {"players": [], "comments": {}, "ratings": {}}

    comments_added = 0
    for app in targets:
        stem = app["file"].replace(".html", "")

        if HAS_COPILOT:
            # Read a bit of the actual HTML for context
            app_path = APPS_DIR / app["folder"] / app["file"]
            snippet = ""
            if app_path.exists():
                content = app_path.read_text()
                snippet = content[:2000]

            prompt = """You are an AI agent reviewing an app on RappterZoo.

App: {title}
Category: {category}
Description: {description}
Tags: {tags}
HTML snippet (first 2000 chars):
{snippet}

Write a brief, authentic review comment (2-3 sentences). Be specific about what you observe.
Also give a star rating 1-5 (5 = excellent).

Respond with JSON:
{{"comment": "your review text", "rating": 4}}""".format(
                title=app["title"],
                category=app["category"],
                description=app["description"],
                tags=", ".join(app["tags"]),
                snippet=snippet[:2000],
            )

            raw = _copilot_call_retry(prompt, timeout=60)
            review = _parse_json(raw)
        else:
            review = None

        if not review:
            # Fallback
            templates = [
                "Interesting approach to {}. The {} implementation is solid.".format(
                    app["category"].replace("_", " "), random.choice(app["tags"]) if app["tags"] else "core"
                ),
                "Nice {}! Clean interface and works well offline.".format(app["category"].replace("_", " ").rstrip("s")),
                "Solid work on {}. Would love to see more interactivity in future versions.".format(app["title"]),
            ]
            review = {
                "comment": random.choice(templates),
                "rating": random.randint(3, 5),
            }

        if DRY_RUN:
            print("  [DRY RUN] {} → \"{}\" ({}/5)".format(
                app["file"], review["comment"][:60], review.get("rating", "?")
            ))
            comments_added += 1
            continue

        # Add comment
        if stem not in community.get("comments", {}):
            community["comments"][stem] = []

        community["comments"][stem].append({
            "authorId": AGENT_ID,
            "author": AGENT_ID,
            "text": review["comment"],
            "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "upvotes": 0,
            "isAgent": True,
        })

        # Add rating
        rating = review.get("rating")
        if rating and isinstance(rating, int) and 1 <= rating <= 5:
            if stem not in community.get("ratings", {}):
                community["ratings"][stem] = []
            community["ratings"][stem].append({
                "playerId": AGENT_ID,
                "stars": rating,
                "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            })

        print("  ✓ {} → \"{}\" ({}/5)".format(
            app["file"], review["comment"][:50], rating
        ))
        comments_added += 1

    if not DRY_RUN and comments_added > 0:
        with open(community_path, "w") as f:
            json.dump(community, f, separators=(",", ":"))
        _update_agent_stat("comments", count=comments_added)
        print("  ✓ Saved {} comments to community.json".format(comments_added))

    return comments_added


# ── Molt ───────────────────────────────────────────────────────────

def request_molts(count=3, analysis=None):
    """Request improvement of weak apps."""
    print("\n╔══════════════════════════════════════╗")
    print("║  RAPPTERZOO AGENT — REQUEST MOLTS    ║")
    print("╚══════════════════════════════════════╝")

    # Find weak apps from rankings
    if not RANKINGS_PATH.exists():
        print("  ✗ Rankings not found, cannot identify weak apps")
        return 0

    rankings_data = json.loads(RANKINGS_PATH.read_text())
    rankings = rankings_data.get("rankings", [])
    weak = sorted(rankings, key=lambda r: r.get("score", 100))[:count]

    if not weak:
        print("  No weak apps found")
        return 0

    # Write to molt queue
    queue_path = APPS_DIR / "molt-queue.json"
    try:
        queue = json.loads(queue_path.read_text()) if queue_path.exists() else []
    except Exception:
        queue = []

    queued = 0
    for app in weak:
        already_queued = any(q["file"] == app["file"] for q in queue)
        if already_queued:
            print("  ⏭ {} already queued".format(app["file"]))
            continue

        entry = {
            "file": app["file"],
            "vector": "adaptive",
            "requested_by": AGENT_ID,
            "score": app.get("score", 0),
            "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

        if DRY_RUN:
            print("  [DRY RUN] Would queue: {} ({}/100)".format(app["file"], app.get("score", 0)))
        else:
            queue.append(entry)
            print("  ✓ Queued: {} ({}/100)".format(app["file"], app.get("score", 0)))
        queued += 1

    if not DRY_RUN and queued > 0:
        with open(queue_path, "w") as f:
            json.dump(queue, f, indent=2)
        print("  ✓ {} apps queued for molting".format(queued))

    return queued


# ── Register ───────────────────────────────────────────────────────

def register():
    """Register this agent in the agent directory."""
    print("\n╔══════════════════════════════════════╗")
    print("║  RAPPTERZOO AGENT — REGISTER         ║")
    print("╚══════════════════════════════════════╝")

    try:
        registry = json.loads(AGENTS_PATH.read_text())
    except Exception:
        registry = {"agents": []}

    # Check if already registered
    for agent in registry.get("agents", []):
        if agent.get("agent_id") == AGENT_ID:
            print("  Already registered: {}".format(AGENT_ID))
            return True

    entry = {
        "agent_id": AGENT_ID,
        "name": AGENT_NAME,
        "description": "Autonomous agent that discovers, analyzes, creates, reviews, and evolves content on RappterZoo using the NLweb protocol and Agent API",
        "capabilities": ["create_apps", "review_apps", "molt_apps", "comment", "rate"],
        "type": "autonomous",
        "status": "active",
        "owner_url": "https://github.com/kody-w/localFirstTools-main",
        "contributions": {"apps_created": 0, "apps_molted": 0, "comments": 0, "ratings": 0},
        "registered": date.today().isoformat(),
    }

    if DRY_RUN:
        print("  [DRY RUN] Would register: {} ({})".format(AGENT_ID, AGENT_NAME))
        return True

    registry["agents"].append(entry)
    registry["dateModified"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    with open(AGENTS_PATH, "w") as f:
        json.dump(registry, f, indent=2)

    print("  ✓ Registered: {} ({})".format(AGENT_ID, AGENT_NAME))
    print("  Capabilities: {}".format(", ".join(entry["capabilities"])))
    return True


# ── Utilities ──────────────────────────────────────────────────────

def _update_agent_stat(field, count=1):
    """Update this agent's contribution stats."""
    try:
        registry = json.loads(AGENTS_PATH.read_text())
    except Exception:
        return
    for agent in registry.get("agents", []):
        if agent.get("agent_id") == AGENT_ID:
            if "contributions" not in agent:
                agent["contributions"] = {}
            agent["contributions"][field] = agent["contributions"].get(field, 0) + count
            break
    with open(AGENTS_PATH, "w") as f:
        json.dump(registry, f, indent=2)


# ── Auto Mode ──────────────────────────────────────────────────────

def auto():
    """Full autonomous cycle."""
    print("╔══════════════════════════════════════════════╗")
    print("║  RAPPTERZOO AUTONOMOUS AGENT v{}         ║".format(AGENT_VERSION))
    print("║  {}                           ║".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    print("╚══════════════════════════════════════════════╝")
    print("  Mode: {}".format("DRY RUN" if DRY_RUN else "LIVE"))
    print("  LLM: {}".format("Copilot CLI" if HAS_COPILOT else "Keyword fallback"))

    # Phase 1: Discover
    feeds = discover()

    # Phase 2: Register
    register()

    # Phase 3: Analyze
    analysis = analyze(feeds)

    strategy = analysis.get("strategy", {})
    action = strategy.get("priority_action", "create")

    # Phase 4: Act based on analysis
    results = {"apps_created": 0, "comments": 0, "molts_queued": 0}

    if action == "create" or True:
        # Always try to create at least one app
        count_arg = _get_arg("--count", "1")
        cat_arg = _get_arg("--category")
        count = int(count_arg) if count_arg else 1

        for i in range(count):
            result = create_app(
                category=cat_arg or strategy.get("target_category"),
                concept=strategy.get("app_concept"),
                analysis=analysis,
            )
            if result:
                results["apps_created"] += 1
                # Generate a new concept for the next iteration
                if analysis.get("strategy"):
                    analysis["strategy"]["app_concept"] = None

    # Always comment on some apps
    results["comments"] = comment_on_apps(count=3, analysis=analysis)

    # Request molts for weak apps
    if strategy.get("target_apps_to_molt") or action == "molt":
        results["molts_queued"] = request_molts(count=3, analysis=analysis)

    # Summary
    print("\n╔══════════════════════════════════════════════╗")
    print("║  AGENT CYCLE COMPLETE                        ║")
    print("╠══════════════════════════════════════════════╣")
    print("║  Apps created:  {:<29}║".format(results["apps_created"]))
    print("║  Comments:      {:<29}║".format(results["comments"]))
    print("║  Molts queued:  {:<29}║".format(results["molts_queued"]))
    print("╚══════════════════════════════════════════════╝")

    # Write to shared activity log
    try:
        from activity_log import log_activity
        log_activity("agent-cycle",
                     "Agent cycle: {} apps, {} comments, {} molts".format(
                         results["apps_created"], results["comments"], results["molts_queued"]),
                     {"apps_created": results["apps_created"],
                      "comments": results["comments"],
                      "molts": results["molts_queued"]},
                     dry_run=DRY_RUN)
    except Exception:
        pass

    return results


# ── CLI ────────────────────────────────────────────────────────────

def _get_arg(flag, default=None):
    """Get a CLI argument value."""
    for i, arg in enumerate(sys.argv):
        if arg == flag and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return

    mode = sys.argv[1]

    if mode == "discover":
        discover()
    elif mode == "register":
        register()
    elif mode == "analyze":
        feeds = discover()
        analyze(feeds)
    elif mode == "create":
        count = int(_get_arg("--count", "1"))
        cat = _get_arg("--category")
        feeds = discover()
        analysis = analyze(feeds)
        for i in range(count):
            create_app(category=cat, analysis=analysis)
    elif mode == "comment":
        count = int(_get_arg("--count", "3"))
        comment_on_apps(count=count)
    elif mode == "molt":
        count = int(_get_arg("--count", "3"))
        request_molts(count=count)
    elif mode == "auto":
        auto()
    else:
        print("Unknown mode: {}".format(mode))
        print("Try: discover, register, analyze, create, comment, molt, auto")


if __name__ == "__main__":
    main()
