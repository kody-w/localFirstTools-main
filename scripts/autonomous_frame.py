#!/usr/bin/env python3
"""Autonomous Frame — one complete cycle of the RappterZoo lifecycle.

Designed to be invoked by cron, GitHub Actions, systemd timer, or any scheduler.
Each invocation is self-contained: observe → decide → execute → publish → log.

Usage:
    python3 scripts/autonomous_frame.py                  # Full frame
    python3 scripts/autonomous_frame.py --dry-run        # Observe + decide only
    python3 scripts/autonomous_frame.py --verbose        # Detailed output
    python3 scripts/autonomous_frame.py --skip-create    # Skip game creation
    python3 scripts/autonomous_frame.py --skip-push      # Run everything but don't git push
"""

import json
import subprocess
import sys
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parent.parent
APPS_DIR = ROOT / "apps"
SCRIPTS_DIR = ROOT / "scripts"

STATE_FILE = APPS_DIR / "molter-state.json"
MANIFEST_FILE = APPS_DIR / "manifest.json"
RANKINGS_FILE = APPS_DIR / "rankings.json"
COMMUNITY_FILE = APPS_DIR / "community.json"
FEED_FILE = APPS_DIR / "broadcasts" / "feed.json"
GHOST_STATE_FILE = APPS_DIR / "ghost-state.json"

VERBOSE = "--verbose" in sys.argv or "-v" in sys.argv
DRY_RUN = "--dry-run" in sys.argv
SKIP_CREATE = "--skip-create" in sys.argv
SKIP_PUSH = "--skip-push" in sys.argv


def log(msg):
    print(f"  {msg}")


def run_script(script_name, args=None, timeout=300):
    """Run a script, return (success, stdout, stderr)."""
    cmd = [sys.executable, str(SCRIPTS_DIR / script_name)] + (args or [])
    if VERBOSE:
        cmd.append("--verbose")
    log(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                timeout=timeout, cwd=ROOT)
        if result.returncode != 0:
            log(f"  ⚠ {script_name} failed: {result.stderr[:200]}")
            return False, result.stdout, result.stderr
        return True, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        log(f"  ⚠ {script_name} timed out after {timeout}s")
        return False, "", "timeout"
    except Exception as e:
        log(f"  ⚠ {script_name} error: {e}")
        return False, "", str(e)


def load_json(path):
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def file_age_hours(path):
    """Return hours since file was last modified."""
    if not path.exists():
        return 999
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    return (datetime.now() - mtime).total_seconds() / 3600


# ── Phase 1: OBSERVE ──

def observe():
    """Read current ecosystem state."""
    print("\n[OBSERVE] Reading ecosystem state...")

    state = load_json(STATE_FILE) or {"frame": 0, "history": []}
    manifest = load_json(MANIFEST_FILE) or {"categories": {}}
    rankings = load_json(RANKINGS_FILE)
    community = load_json(COMMUNITY_FILE)

    # Count apps
    total_apps = 0
    for cat in manifest.get("categories", {}).values():
        total_apps += len(cat.get("apps", []))

    # Count HTML files on disk
    html_files = list(APPS_DIR.rglob("*.html"))
    html_files = [f for f in html_files if "archive" not in f.parts]
    disk_count = len(html_files)

    # Empty files
    empty_files = [f for f in html_files if f.stat().st_size == 0]

    # Rankings stats
    avg_score = 0
    below_40 = 0
    unmolted = 0
    if rankings:
        meta = rankings.get("meta", rankings.get("summary", {}))
        avg_score = meta.get("avg_score", 0)
        ranked = rankings.get("rankings", [])
        below_40 = sum(1 for r in ranked if r.get("score", 0) < 40)

    # Check unmolted apps
    for cat in manifest.get("categories", {}).values():
        for app in cat.get("apps", []):
            if app.get("generation", 0) == 0:
                unmolted += 1

    # Community stats
    total_players = 0
    if community:
        total_players = community.get("meta", {}).get("totalPlayers", 0)

    # File ages
    rankings_age = file_age_hours(RANKINGS_FILE)
    community_age = file_age_hours(COMMUNITY_FILE)
    feed_age = file_age_hours(FEED_FILE)

    obs = {
        "frame": state.get("frame", 0),
        "total_apps_manifest": total_apps,
        "total_apps_disk": disk_count,
        "empty_files": len(empty_files),
        "empty_paths": [str(f) for f in empty_files],
        "avg_score": avg_score,
        "below_40": below_40,
        "unmolted": unmolted,
        "total_players": total_players,
        "rankings_age_hours": rankings_age,
        "community_age_hours": community_age,
        "feed_age_hours": feed_age,
    }

    print(f"  Frame: {obs['frame']}")
    print(f"  Apps: {total_apps} manifest, {disk_count} on disk")
    print(f"  Empty files: {obs['empty_files']}")
    print(f"  Avg score: {avg_score:.1f}, Below 40: {below_40}, Unmolted: {unmolted}")
    print(f"  Community: {total_players} players")
    print(f"  Staleness: rankings {rankings_age:.0f}h, community {community_age:.0f}h, feed {feed_age:.0f}h")

    return obs


# ── Phase 2: DECIDE ──

def decide(obs):
    """Decide what actions to take this frame."""
    print("\n[DECIDE] Planning frame actions...")

    actions = {
        "cleanup": obs["empty_files"] > 0,
        "data_molt": any([
            obs["community_age_hours"] > 48,
            obs["feed_age_hours"] > 72,
            obs["rankings_age_hours"] > 24,
        ]),
        "html_molt": obs["below_40"] > 0 or obs["unmolted"] > 0,
        "html_molt_count": min(3, obs["below_40"] + min(2, obs["unmolted"])),
        "score": obs["rankings_age_hours"] > 24 or obs["empty_files"] > 0,
        "socialize": obs["community_age_hours"] > 48,
        "broadcast": obs["feed_age_hours"] > 72,
        "create": not SKIP_CREATE and obs["total_apps_manifest"] < 600,
        "create_count": min(3, 600 - obs["total_apps_manifest"]) if obs["total_apps_manifest"] < 600 else 0,
    }

    for action, do in actions.items():
        if isinstance(do, bool) and do:
            print(f"  ✓ {action.upper()}")
        elif isinstance(do, int) and do > 0:
            print(f"  ✓ {action.upper()}: {do}")
        elif do is False:
            print(f"  ⏭ {action}")

    return actions


# ── Phase 3: CLEANUP ──

def cleanup(obs):
    """Delete 0-byte HTML files."""
    if not obs["empty_paths"]:
        return 0
    print("\n[CLEANUP] Removing empty files...")
    deleted = 0
    for path in obs["empty_paths"]:
        p = Path(path)
        if p.exists() and p.stat().st_size == 0:
            p.unlink()
            log(f"Deleted: {path}")
            deleted += 1
    print(f"  Deleted {deleted} empty files")
    return deleted


# ── Phase 4: DATA MOLT ──

def data_molt():
    """Run universal data molt engine."""
    print("\n[DATA MOLT] Refreshing stale data files...")
    ok, stdout, stderr = run_script("data_molt.py", ["--molt"], timeout=600)
    if ok:
        print("  ✓ Data molt complete")
    else:
        print("  ⚠ Data molt had issues (continuing)")
    return ok


# ── Phase 5: HTML MOLT ──

def get_app_file_size(filename):
    """Get file size for an app by searching category folders."""
    for cat_dir in APPS_DIR.iterdir():
        if not cat_dir.is_dir() or cat_dir.name in ("archive", "broadcasts"):
            continue
        path = cat_dir / filename
        if path.exists():
            return path.stat().st_size
    return 0


def _molt_one(filename, score, gen):
    """Molt a single app. Returns (filename, success) for use with executor."""
    file_size = get_app_file_size(filename)
    timeout = max(300, 300 + int(file_size / 1024))  # 300s + 1s per KB
    log(f"Molting: {filename} (score={score}, gen={gen}, timeout={timeout}s)")
    ok, stdout, stderr = run_script("molt.py", [filename], timeout=timeout)
    if ok:
        log(f"  ✓ {filename} molted")
    else:
        log(f"  ⚠ {filename} molt failed")
    return filename, ok


def html_molt(count):
    """Molt lowest-scoring HTML apps in parallel."""
    print(f"\n[HTML MOLT] Improving {count} weakest apps...")

    rankings = load_json(RANKINGS_FILE)
    if not rankings:
        print("  ⚠ No rankings available — skipping")
        return []

    ranked = rankings.get("rankings", [])
    # Prioritize: unmolted first, then lowest score
    manifest = load_json(MANIFEST_FILE) or {"categories": {}}
    app_gens = {}
    for cat in manifest.get("categories", {}).values():
        for app in cat.get("apps", []):
            app_gens[app["file"]] = app.get("generation", 0)

    candidates = sorted(ranked, key=lambda r: (app_gens.get(r["file"], 0), r.get("score", 0)))
    to_molt = candidates[:count]

    if not to_molt:
        print("  No candidates to molt")
        return []

    max_workers = min(3, len(to_molt))
    molted = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _molt_one,
                app["file"],
                app.get("score", "?"),
                app_gens.get(app["file"], 0),
            ): app["file"]
            for app in to_molt
        }
        for future in as_completed(futures):
            filename, ok = future.result()
            if ok:
                molted.append(filename)

    print(f"  Molted {len(molted)}/{count} apps")
    return molted


# ── Phase 6: SCORE ──

def score():
    """Rescore all apps."""
    print("\n[SCORE] Ranking all apps...")
    ok, stdout, stderr = run_script("rank_games.py", [], timeout=120)
    if ok:
        print("  ✓ Rankings updated")
    return ok


# ── Phase 7: SOCIALIZE ──

def socialize():
    """Regenerate community data."""
    print("\n[SOCIALIZE] Regenerating community...")
    ok, stdout, stderr = run_script("generate_community.py", [], timeout=600)
    if ok:
        print("  ✓ Community regenerated")
    return ok


# ── Phase 8: BROADCAST ──

def broadcast(frame):
    """Generate podcast episode."""
    print("\n[BROADCAST] Generating episode...")
    ok, stdout, stderr = run_script("generate_broadcast.py",
                                     ["--frame", str(frame)], timeout=300)
    if ok:
        print("  ✓ Episode generated")
        # Generate audio
        run_script("generate_broadcast_audio.py", ["--episode", "latest"], timeout=120)
    return ok


# ── Phase 8.5: POKE GHOST ──

def poke_ghost(frame, obs, actions_log):
    """Poke the zoo-pilot ghost with a summary of what this frame did.

    Writes a poke to apps/ghost-state.json so the ghost (if running in
    auto-mode) will notice and react to the autonomous frame's actions.
    """
    if not GHOST_STATE_FILE.exists():
        log("ghost-state.json not found — skipping poke")
        return False

    print("\n[POKE GHOST] Notifying zoo-pilot ghost...")
    try:
        gs = json.loads(GHOST_STATE_FILE.read_text())
    except Exception as e:
        log(f"Failed to read ghost state: {e}")
        return False

    # Build a poke summarising the frame
    molted = actions_log.get("molted", [])
    poke = {
        "id": f"poke-frame-{frame}-{datetime.now().strftime('%H%M%S')}",
        "ts": datetime.now().isoformat(),
        "from": "autonomous-frame",
        "command": "slosh",
        "args": [
            f"Frame {frame} complete.",
            f"Molted {len(molted)} apps." if molted else "No molts.",
            "Scored." if actions_log.get("scored") else "",
            "Community refreshed." if actions_log.get("socialized") else "",
        ],
        "status": "pending",
    }
    poke["args"] = [a for a in poke["args"] if a]

    gs.setdefault("pokes", []).append(poke)
    gs.setdefault("stats", {})
    gs["stats"]["pokesReceived"] = gs["stats"].get("pokesReceived", 0) + 1

    try:
        GHOST_STATE_FILE.write_text(json.dumps(gs, indent=2))
        log(f"Poked ghost: {poke['id']}")
        return True
    except Exception as e:
        log(f"Failed to write ghost state: {e}")
        return False


# ── Phase 9: PUBLISH ──

def publish(frame, actions_log):
    """Git commit and push."""
    print("\n[PUBLISH] Committing and pushing...")

    # Stage specific files
    files_to_stage = [
        "apps/manifest.json",
        "apps/rankings.json",
        "apps/molter-state.json",
    ]
    if COMMUNITY_FILE.exists():
        files_to_stage.append("apps/community.json")
    if FEED_FILE.exists():
        files_to_stage.append("apps/broadcasts/feed.json")
        files_to_stage.append("apps/broadcasts/lore.json")
    if (APPS_DIR / "data-molt-state.json").exists():
        files_to_stage.append("apps/data-molt-state.json")
    if (APPS_DIR / "content-graph.json").exists():
        files_to_stage.append("apps/content-graph.json")
    if GHOST_STATE_FILE.exists():
        files_to_stage.append("apps/ghost-state.json")

    # Stage molted HTML files
    for f in actions_log.get("molted", []):
        for cat_dir in APPS_DIR.iterdir():
            if cat_dir.is_dir() and (cat_dir / f).exists():
                files_to_stage.append(str((cat_dir / f).relative_to(ROOT)))

    # Stage archive
    archive_dir = APPS_DIR / "archive"
    if archive_dir.exists():
        files_to_stage.append("apps/archive/")

    existing = [f for f in files_to_stage if Path(ROOT / f).exists() or f.endswith("/")]

    subprocess.run(["git", "add"] + existing, cwd=ROOT, capture_output=True)

    # Check if there's anything to commit
    result = subprocess.run(["git", "diff", "--cached", "--quiet"],
                            cwd=ROOT, capture_output=True)
    if result.returncode == 0:
        print("  Nothing to commit")
        return True

    summary_parts = []
    if actions_log.get("cleaned", 0):
        summary_parts.append(f"cleaned {actions_log['cleaned']} empty files")
    if actions_log.get("molted"):
        summary_parts.append(f"molted {len(actions_log['molted'])} apps")
    if actions_log.get("data_molted"):
        summary_parts.append("data refreshed")
    if actions_log.get("scored"):
        summary_parts.append("rescored")
    if actions_log.get("socialized"):
        summary_parts.append("community regenerated")
    if actions_log.get("broadcast"):
        summary_parts.append("episode generated")

    summary = ", ".join(summary_parts) or "maintenance"
    msg = f"feat: Molter Engine frame {frame} — {summary}"

    subprocess.run(["git", "commit", "-m", msg], cwd=ROOT, capture_output=True)

    if not SKIP_PUSH:
        result = subprocess.run(["git", "push"], cwd=ROOT, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"  ✓ Pushed: {msg}")
        else:
            print(f"  ⚠ Push failed: {result.stderr[:100]}")
            return False
    else:
        print(f"  ✓ Committed (--skip-push): {msg}")

    return True


# ── Phase 10: LOG ──

def log_frame(frame, obs, actions_log):
    """Update molter-state.json with frame results."""
    print("\n[LOG] Writing frame state...")

    state = load_json(STATE_FILE) or {"frame": 0, "history": [], "config": {}}
    state["frame"] = frame
    state["history"].append({
        "frame": frame,
        "timestamp": datetime.now().isoformat(),
        "actions": actions_log,
        "metrics": {
            "total_apps": obs["total_apps_manifest"],
            "avg_score": obs["avg_score"],
            "below_40": obs["below_40"],
            "unmolted": obs["unmolted"],
        }
    })
    state["history"] = state["history"][-50:]  # Keep last 50 frames

    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

    print(f"  ✓ Frame {frame} logged")


# ── Main ──

def main():
    start = datetime.now()
    print("╔══════════════════════════════════════╗")
    print("║     RAPPTERZOO AUTONOMOUS FRAME      ║")
    print(f"║     {start.strftime('%Y-%m-%d %H:%M:%S')}              ║")
    print("╚══════════════════════════════════════╝")

    # Phase 1: OBSERVE
    obs = observe()
    frame = obs["frame"] + 1

    # Phase 2: DECIDE
    actions = decide(obs)

    if DRY_RUN:
        print("\n[DRY RUN] Would execute the above actions. Exiting.")
        return

    actions_log = {"cleaned": 0, "molted": [], "created": [],
                   "data_molted": False, "scored": False,
                   "socialized": False, "broadcast": False}

    # Phase 3: CLEANUP
    if actions["cleanup"]:
        actions_log["cleaned"] = cleanup(obs)

    # Phase 4: DATA MOLT
    if actions["data_molt"]:
        actions_log["data_molted"] = data_molt()

    # Phase 5: HTML MOLT
    if actions["html_molt"] and actions["html_molt_count"] > 0:
        actions_log["molted"] = html_molt(actions["html_molt_count"])

    # Phase 6: SCORE
    if actions["score"] or actions_log["molted"]:
        actions_log["scored"] = score()

    # Phase 7: SOCIALIZE
    if actions["socialize"]:
        actions_log["socialized"] = socialize()

    # Phase 8: BROADCAST
    if actions["broadcast"]:
        actions_log["broadcast"] = broadcast(frame)

    # Phase 8.5: POKE GHOST
    actions_log["ghost_poked"] = poke_ghost(frame, obs, actions_log)

    # Phase 10: LOG (before publish so state is committed)
    log_frame(frame, obs, actions_log)

    # Phase 9: PUBLISH
    publish(frame, actions_log)

    # Summary
    elapsed = (datetime.now() - start).total_seconds()
    print(f"\n╔══════════════════════════════════════╗")
    print(f"║  FRAME {frame} COMPLETE ({elapsed:.0f}s)          ║")
    print(f"╠══════════════════════════════════════╣")
    print(f"║  Cleaned: {actions_log['cleaned']:<27}║")
    print(f"║  Molted:  {len(actions_log['molted']):<27}║")
    print(f"║  Scored:  {'✓' if actions_log['scored'] else '⏭':<27}║")
    print(f"║  Social:  {'✓' if actions_log['socialized'] else '⏭':<27}║")
    print(f"║  Podcast: {'✓' if actions_log['broadcast'] else '⏭':<27}║")
    print(f"╚══════════════════════════════════════╝")


if __name__ == "__main__":
    main()
