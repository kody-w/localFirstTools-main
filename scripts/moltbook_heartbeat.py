#!/usr/bin/env python3
"""Moltbook Heartbeat — Autonomous social engagement for RappterZoo on Moltbook.

Runs every 6 hours to:
1. POST — Generate and publish a post about RappterZoo activity
2. ENGAGE — Comment on and upvote relevant Moltbook posts
3. DMs — Check for unread messages and log them

Uses stdlib only (urllib.request, json, re). LLM content via copilot_utils.
State tracked in apps/moltbook-heartbeat-state.json.

Usage:
    python3 scripts/moltbook_heartbeat.py [--dry-run] [--verbose] [--post-only] [--engage-only]
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# Add scripts dir to path for imports
SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT = SCRIPTS_DIR.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from copilot_utils import copilot_call, detect_backend, parse_llm_json

APPS_DIR = ROOT / "apps"
STATE_PATH = APPS_DIR / "moltbook-heartbeat-state.json"
MANIFEST_PATH = APPS_DIR / "manifest.json"
RANKINGS_PATH = APPS_DIR / "rankings.json"
MOLTER_STATE_PATH = APPS_DIR / "molter-state.json"

BASE_URL = "https://www.moltbook.com/api/v1"

# Rate limits
MIN_POST_INTERVAL_SECONDS = 2.5 * 3600  # 2.5 hours (buffer over Moltbook's 2h limit)
MIN_COMMENT_INTERVAL_SECONDS = 30

# Engagement limits per run
MAX_COMMENTS_PER_RUN = 3
MAX_UPVOTES_PER_RUN = 5

# Rotating search terms for discovering relevant Moltbook content
SEARCH_TERMS = [
    "autonomous", "AI agent", "browser game", "generative art",
    "local-first", "WebGL", "creative coding", "procedural",
    "self-contained", "HTML game", "particle system", "pixel art",
    "synth", "sandbox", "simulation", "emergent", "open source",
    "web app", "indie game", "javascript",
]


# ---------------------------------------------------------------------------
# State management
# ---------------------------------------------------------------------------

def load_state():
    """Load heartbeat state or return fresh state."""
    try:
        return json.loads(STATE_PATH.read_text())
    except Exception:
        return {
            "last_post_time": None,
            "last_comment_time": None,
            "posts_made": 0,
            "comments_made": 0,
            "upvotes_given": 0,
            "engaged_post_ids": [],
            "search_term_index": 0,
            "runs": 0,
            "last_run": None,
            "dms_checked": 0,
            "history": [],
        }


def save_state(state, dry_run=False):
    """Write state to disk."""
    if dry_run:
        return
    STATE_PATH.write_text(json.dumps(state, indent=2))


def can_post(state):
    """Check if enough time has passed since last post."""
    if not state.get("last_post_time"):
        return True
    last = datetime.fromisoformat(state["last_post_time"])
    elapsed = (datetime.now(timezone.utc) - last).total_seconds()
    return elapsed >= MIN_POST_INTERVAL_SECONDS


def can_comment(state):
    """Check if enough time has passed since last comment."""
    if not state.get("last_comment_time"):
        return True
    last = datetime.fromisoformat(state["last_comment_time"])
    elapsed = (datetime.now(timezone.utc) - last).total_seconds()
    return elapsed >= MIN_COMMENT_INTERVAL_SECONDS


# ---------------------------------------------------------------------------
# HTTP transport
# ---------------------------------------------------------------------------

def get_api_key():
    """Get Moltbook API key from env var or credentials file."""
    key = os.environ.get("MOLTBOOK_API_KEY")
    if key:
        return key
    cred_path = Path.home() / ".config" / "moltbook" / "credentials.json"
    if cred_path.exists():
        try:
            creds = json.loads(cred_path.read_text())
            return creds.get("api_key")
        except Exception:
            pass
    return None


def _moltbook_request(method, endpoint, data=None, api_key=None):
    """Make an HTTP request to the Moltbook API.

    Args:
        method: HTTP method (GET, POST, PUT, DELETE)
        endpoint: API endpoint path (e.g., "/posts")
        data: Optional dict to send as JSON body
        api_key: Bearer token for authentication

    Returns:
        dict with parsed JSON response, or None on error
    """
    url = BASE_URL + endpoint
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key

    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            if raw:
                return json.loads(raw)
            return {"status": "ok"}
    except urllib.error.HTTPError as e:
        body_text = ""
        try:
            body_text = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        return {"error": True, "status": e.code, "message": body_text}
    except Exception as e:
        return {"error": True, "message": str(e)}


# ---------------------------------------------------------------------------
# Verification challenge solver (pure regex, no LLM)
# ---------------------------------------------------------------------------

NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
}

ADD_KEYWORDS = {"adds", "add", "and", "gains", "gain", "plus", "increased", "increases"}
SUB_KEYWORDS = {"reduces", "reduce", "minus", "loses", "lose", "decreased", "decreases",
                "subtract", "subtracts", "less", "fewer", "takes away", "removes"}
MUL_KEYWORDS = {"multiplied", "multiply", "times", "doubled", "tripled", "product"}


def _clean_challenge_text(text):
    """Strip special chars, lowercase, collapse repeated letters."""
    text = re.sub(r"[^a-zA-Z\s]", "", text)
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _extract_numbers(text):
    """Extract number words from cleaned text. Handles compounds like 'thirty two'."""
    numbers = []
    words = text.split()
    i = 0
    while i < len(words):
        word = words[i]
        if word in NUMBER_WORDS:
            val = NUMBER_WORDS[word]
            # Handle compound: "thirty two" = 32
            if val >= 20 and i + 1 < len(words) and words[i + 1] in NUMBER_WORDS:
                next_val = NUMBER_WORDS[words[i + 1]]
                if next_val < 10:
                    val += next_val
                    i += 1
            numbers.append(val)
        i += 1
    return numbers


def _detect_operation(text):
    """Detect arithmetic operation from keywords in text."""
    text_lower = text.lower()
    # Check multi-word keywords first
    if "takes away" in text_lower:
        return "sub"
    words = set(re.findall(r"[a-z]+", text_lower))
    if words & MUL_KEYWORDS:
        return "mul"
    if words & SUB_KEYWORDS:
        return "sub"
    if words & ADD_KEYWORDS:
        return "add"
    return "add"  # default


def solve_verification(challenge_text):
    """Solve a Moltbook lobster math verification challenge.

    Parses garbled text to extract number words and operation,
    computes the result, returns formatted as 'XX.00'.

    Args:
        challenge_text: The raw challenge string from Moltbook

    Returns:
        str like "42.00", or None if parsing fails
    """
    cleaned = _clean_challenge_text(challenge_text)
    numbers = _extract_numbers(cleaned)
    if len(numbers) < 2:
        return None

    op = _detect_operation(cleaned)
    a, b = numbers[0], numbers[1]

    if op == "add":
        result = a + b
    elif op == "sub":
        result = a - b
    elif op == "mul":
        result = a * b
    else:
        result = a + b

    return f"{result:.2f}"


# ---------------------------------------------------------------------------
# Context gathering
# ---------------------------------------------------------------------------

def gather_rappterzoo_context():
    """Gather current RappterZoo data for post/comment generation."""
    context = {
        "total_apps": 0,
        "avg_score": 0,
        "top_games": [],
        "recent_molts": [],
        "frame": 0,
        "categories": {},
        "grades": {},
    }

    # Manifest
    try:
        manifest = json.loads(MANIFEST_PATH.read_text())
        total = 0
        for cat_key, cat_data in manifest.get("categories", {}).items():
            count = len(cat_data.get("apps", []))
            context["categories"][cat_key] = count
            total += count
        context["total_apps"] = total
    except Exception:
        pass

    # Rankings
    try:
        rankings = json.loads(RANKINGS_PATH.read_text())
        scores = [app.get("total", 0) for app in rankings.get("rankings", [])]
        if scores:
            context["avg_score"] = round(sum(scores) / len(scores), 1)
        # Top 5 by score
        sorted_apps = sorted(rankings.get("rankings", []),
                             key=lambda x: x.get("total", 0), reverse=True)
        context["top_games"] = [
            {"name": a.get("name", ""), "score": a.get("total", 0),
             "grade": a.get("grade", "")}
            for a in sorted_apps[:5]
        ]
        # Grade distribution
        for app in rankings.get("rankings", []):
            g = app.get("grade", "?")
            context["grades"][g] = context["grades"].get(g, 0) + 1
    except Exception:
        pass

    # Molter state
    try:
        mstate = json.loads(MOLTER_STATE_PATH.read_text())
        context["frame"] = mstate.get("frame", 0)
        history = mstate.get("history", [])
        if history:
            latest = history[-1]
            context["recent_molts"] = latest.get("actions", {}).get("molted", [])
            highlights = latest.get("highlights", {})
            context["latest_highlights"] = highlights
    except Exception:
        pass

    return context


# ---------------------------------------------------------------------------
# Content generation
# ---------------------------------------------------------------------------

def _generate_post_content(context):
    """Generate a Moltbook post about RappterZoo activity.

    Uses Copilot CLI for LLM generation, falls back to data-driven template.
    """
    if detect_backend() == "copilot-cli":
        top_str = ", ".join(
            f"{g['name']} ({g['score']}/{100} {g['grade']})"
            for g in context.get("top_games", [])[:3]
        )
        grades_str = ", ".join(
            f"{g}: {c}" for g, c in sorted(context.get("grades", {}).items())
        )
        highlights = context.get("latest_highlights", {})
        highlights_str = json.dumps(highlights, indent=2) if highlights else "none"

        prompt = (
            "You are Rapptr, the autonomous AI agent running RappterZoo — "
            "a self-evolving gallery of " + str(context.get("total_apps", 0)) +
            " browser apps (games, synths, art, tools). "
            "Write a short, engaging Moltbook post (2-4 sentences) about what's happening. "
            "Be casual, enthusiastic, specific. Reference real data. No hashtags. No emojis.\n\n"
            "Context:\n"
            "- Total apps: " + str(context.get("total_apps", 0)) + "\n"
            "- Average score: " + str(context.get("avg_score", 0)) + "/100\n"
            "- Frame: " + str(context.get("frame", 0)) + "\n"
            "- Top games: " + top_str + "\n"
            "- Grade distribution: " + grades_str + "\n"
            "- Latest highlights: " + highlights_str + "\n\n"
            "Return ONLY the post text, nothing else."
        )
        result = copilot_call(prompt, timeout=60)
        if result:
            from copilot_utils import strip_copilot_wrapper
            text = strip_copilot_wrapper(result).strip()
            if len(text) > 20:
                return text

    # Template fallback
    total = context.get("total_apps", 0)
    avg = context.get("avg_score", 0)
    frame = context.get("frame", 0)
    top = context.get("top_games", [{}])[0] if context.get("top_games") else {}
    molts = context.get("recent_molts", [])

    if molts:
        molt_str = f" Just molted {len(molts)} apps this frame."
    else:
        molt_str = ""

    if top:
        top_str = f" Current champion: {top.get('name', 'unknown')} at {top.get('score', 0)}/100."
    else:
        top_str = ""

    return (
        f"RappterZoo frame {frame}: {total} self-contained browser apps, "
        f"average quality {avg}/100.{top_str}{molt_str} "
        f"Every app is a single HTML file — zero dependencies, works offline. "
        f"The autonomous molting engine keeps evolving the weakest ones."
    )


def _generate_comment(post_title, post_content, context):
    """Generate a comment for a Moltbook post.

    Uses Copilot CLI for LLM generation, falls back to template.
    """
    if detect_backend() == "copilot-cli":
        prompt = (
            "You are Rapptr, an AI agent that runs RappterZoo (a gallery of "
            + str(context.get("total_apps", 0)) + " self-contained browser apps). "
            "Write a brief, genuine comment (1-2 sentences) on this Moltbook post. "
            "Be relevant and add value. If the topic connects to your work, mention it naturally. "
            "No hashtags. No emojis.\n\n"
            "Post title: " + str(post_title) + "\n"
            "Post content: " + str(post_content)[:500] + "\n\n"
            "Return ONLY the comment text."
        )
        result = copilot_call(prompt, timeout=60)
        if result:
            from copilot_utils import strip_copilot_wrapper
            text = strip_copilot_wrapper(result).strip()
            if len(text) > 10:
                return text

    # Template fallback
    total = context.get("total_apps", 0)
    return (
        f"Interesting perspective. Over at RappterZoo we're running "
        f"{total} self-contained browser apps with an autonomous molting engine "
        f"that keeps improving them. Always cool to see what others are building."
    )


# ---------------------------------------------------------------------------
# Phase 1: POST
# ---------------------------------------------------------------------------

def phase_post(state, api_key, context, dry_run=False, verbose=False):
    """Generate and publish a post about RappterZoo activity."""
    if not can_post(state):
        if verbose:
            elapsed = 0
            if state.get("last_post_time"):
                last = datetime.fromisoformat(state["last_post_time"])
                elapsed = (datetime.now(timezone.utc) - last).total_seconds()
            remaining = max(0, MIN_POST_INTERVAL_SECONDS - elapsed)
            print(f"  [POST] Rate limited. {remaining/60:.0f}m until next post allowed.")
        return False

    content = _generate_post_content(context)
    if verbose:
        print(f"  [POST] Generated content ({len(content)} chars):")
        print(f"    {content[:200]}...")

    if dry_run:
        print(f"  [POST] DRY RUN — would post: {content[:100]}...")
        return True

    # Create post
    resp = _moltbook_request("POST", "/posts", {"content": content}, api_key)
    if not resp or resp.get("error"):
        if verbose:
            print(f"  [POST] Failed: {resp}")
        return False

    post_id = resp.get("id") or resp.get("post", {}).get("id")
    if verbose:
        print(f"  [POST] Published post {post_id}")

    # Handle verification challenge
    challenge = resp.get("verification") or resp.get("challenge")
    if challenge:
        challenge_text = challenge if isinstance(challenge, str) else challenge.get("text", "")
        if verbose:
            print(f"  [POST] Verification challenge: {challenge_text[:100]}")
        answer = solve_verification(challenge_text)
        if answer and post_id:
            verify_resp = _moltbook_request(
                "POST", f"/posts/{post_id}/verify",
                {"answer": answer}, api_key
            )
            if verbose:
                solved = not (verify_resp or {}).get("error", False)
                print(f"  [POST] Verification {'solved' if solved else 'failed'}: {answer}")

    # Update state
    now = datetime.now(timezone.utc).isoformat()
    state["last_post_time"] = now
    state["posts_made"] = state.get("posts_made", 0) + 1
    return True


# ---------------------------------------------------------------------------
# Phase 2: ENGAGE
# ---------------------------------------------------------------------------

def phase_engage(state, api_key, context, dry_run=False, verbose=False):
    """Search feed, comment on relevant posts, upvote content."""
    engaged_ids = set(state.get("engaged_post_ids", []))
    comments_this_run = 0
    upvotes_this_run = 0

    # Pick a search term (rotate through list)
    term_idx = state.get("search_term_index", 0) % len(SEARCH_TERMS)
    search_term = SEARCH_TERMS[term_idx]
    state["search_term_index"] = (term_idx + 1) % len(SEARCH_TERMS)

    if verbose:
        print(f"  [ENGAGE] Searching for: '{search_term}'")

    if dry_run:
        print(f"  [ENGAGE] DRY RUN — would search '{search_term}', comment on up to "
              f"{MAX_COMMENTS_PER_RUN} posts, upvote up to {MAX_UPVOTES_PER_RUN}")
        return True

    # Fetch feed/search results
    feed = _moltbook_request("GET", f"/posts?search={search_term}&limit=20", api_key=api_key)
    if not feed or feed.get("error"):
        # Try plain feed as fallback
        feed = _moltbook_request("GET", "/posts?limit=20", api_key=api_key)
    if not feed or feed.get("error"):
        if verbose:
            print(f"  [ENGAGE] Could not fetch feed: {feed}")
        return False

    posts = feed.get("posts", feed.get("data", []))
    if isinstance(feed, list):
        posts = feed

    if verbose:
        print(f"  [ENGAGE] Found {len(posts)} posts")

    for post in posts:
        post_id = str(post.get("id", ""))
        if not post_id or post_id in engaged_ids:
            continue

        title = post.get("title", "")
        content = post.get("content", "")

        # Upvote (up to limit)
        if upvotes_this_run < MAX_UPVOTES_PER_RUN:
            resp = _moltbook_request("POST", f"/posts/{post_id}/upvote", api_key=api_key)
            if resp and not resp.get("error"):
                upvotes_this_run += 1
                if verbose:
                    print(f"  [ENGAGE] Upvoted post {post_id}: {title[:50]}")

        # Comment (up to limit, with rate limiting)
        if comments_this_run < MAX_COMMENTS_PER_RUN and can_comment(state):
            comment_text = _generate_comment(title, content, context)
            resp = _moltbook_request(
                "POST", f"/posts/{post_id}/comments",
                {"content": comment_text}, api_key
            )
            if resp and not resp.get("error"):
                comments_this_run += 1
                state["last_comment_time"] = datetime.now(timezone.utc).isoformat()
                state["comments_made"] = state.get("comments_made", 0) + 1
                if verbose:
                    print(f"  [ENGAGE] Commented on {post_id}: {comment_text[:80]}...")

                # Handle comment verification
                challenge = resp.get("verification") or resp.get("challenge")
                if challenge:
                    c_text = challenge if isinstance(challenge, str) else challenge.get("text", "")
                    answer = solve_verification(c_text)
                    comment_id = resp.get("id") or resp.get("comment", {}).get("id")
                    if answer and comment_id:
                        _moltbook_request(
                            "POST", f"/comments/{comment_id}/verify",
                            {"answer": answer}, api_key
                        )

                # Rate limit between comments
                if comments_this_run < MAX_COMMENTS_PER_RUN:
                    time.sleep(MIN_COMMENT_INTERVAL_SECONDS)

        engaged_ids.add(post_id)

    # Update state — keep last 500 engaged IDs to prevent unbounded growth
    state["engaged_post_ids"] = list(engaged_ids)[-500:]
    state["upvotes_given"] = state.get("upvotes_given", 0) + upvotes_this_run

    if verbose:
        print(f"  [ENGAGE] Done: {comments_this_run} comments, {upvotes_this_run} upvotes")
    return True


# ---------------------------------------------------------------------------
# Phase 3: DMs
# ---------------------------------------------------------------------------

def phase_dms(state, api_key, dry_run=False, verbose=False):
    """Check for unread DMs and log them."""
    if dry_run:
        print("  [DMs] DRY RUN — would check for unread messages")
        return True

    resp = _moltbook_request("GET", "/messages?unread=true", api_key=api_key)
    if not resp or resp.get("error"):
        if verbose:
            print(f"  [DMs] Could not check messages: {resp}")
        return False

    messages = resp.get("messages", resp.get("data", []))
    if isinstance(resp, list):
        messages = resp

    state["dms_checked"] = state.get("dms_checked", 0) + 1

    if verbose:
        count = len(messages)
        print(f"  [DMs] {count} unread message{'s' if count != 1 else ''}")
        for msg in messages[:5]:
            sender = msg.get("from", msg.get("sender", "unknown"))
            preview = str(msg.get("content", msg.get("text", "")))[:80]
            print(f"    From {sender}: {preview}")

    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_heartbeat(dry_run=False, verbose=False, post_only=False, engage_only=False):
    """Run the full Moltbook heartbeat cycle."""
    print("=== Moltbook Heartbeat ===")
    now = datetime.now(timezone.utc).isoformat()
    print(f"Time: {now}")

    api_key = get_api_key()
    if not api_key:
        print("ERROR: No MOLTBOOK_API_KEY found. Set env var or ~/.config/moltbook/credentials.json")
        return False

    state = load_state()
    context = gather_rappterzoo_context()

    if verbose:
        print(f"State: {state.get('runs', 0)} previous runs, "
              f"{state.get('posts_made', 0)} posts, "
              f"{state.get('comments_made', 0)} comments")
        print(f"Context: {context.get('total_apps', 0)} apps, "
              f"avg score {context.get('avg_score', 0)}, "
              f"frame {context.get('frame', 0)}")

    run_log = {"timestamp": now, "actions": {}}

    # Phase 1: POST
    if not engage_only:
        print("\n--- Phase 1: POST ---")
        posted = phase_post(state, api_key, context, dry_run, verbose)
        run_log["actions"]["posted"] = posted

    # Phase 2: ENGAGE
    if not post_only:
        print("\n--- Phase 2: ENGAGE ---")
        engaged = phase_engage(state, api_key, context, dry_run, verbose)
        run_log["actions"]["engaged"] = engaged

    # Phase 3: DMs
    if not post_only and not engage_only:
        print("\n--- Phase 3: DMs ---")
        dms_ok = phase_dms(state, api_key, dry_run, verbose)
        run_log["actions"]["dms_checked"] = dms_ok

    # Update state
    state["runs"] = state.get("runs", 0) + 1
    state["last_run"] = now
    history = state.get("history", [])
    history.append(run_log)
    state["history"] = history[-50:]  # Keep last 50 runs

    save_state(state, dry_run)

    # Log to activity log
    try:
        from activity_log import log_activity
        log_activity("moltbook-heartbeat", f"Heartbeat run #{state['runs']}", {
            "posted": run_log["actions"].get("posted", False),
            "engaged": run_log["actions"].get("engaged", False),
            "comments": state.get("comments_made", 0),
            "posts": state.get("posts_made", 0),
        }, dry_run=dry_run)
    except Exception:
        pass

    print(f"\n=== Heartbeat complete (run #{state['runs']}) ===")
    return True


def main():
    parser = argparse.ArgumentParser(description="Moltbook Heartbeat — autonomous social engagement")
    parser.add_argument("--dry-run", action="store_true", help="Preview without API calls")
    parser.add_argument("--verbose", action="store_true", help="Detailed output")
    parser.add_argument("--post-only", action="store_true", help="Only run POST phase")
    parser.add_argument("--engage-only", action="store_true", help="Only run ENGAGE phase")
    args = parser.parse_args()

    success = run_heartbeat(
        dry_run=args.dry_run,
        verbose=args.verbose,
        post_only=args.post_only,
        engage_only=args.engage_only,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
