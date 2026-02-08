#!/usr/bin/env python3
"""Write the EvoMon: 3D World Generator HTML game to apps/3d-immersive/."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APPS_DIR = ROOT / "apps"
MANIFEST_PATH = APPS_DIR / "manifest.json"

EVOMON_PATTERN = re.compile(r"evomon-.*\.html$")

# Category folder mapping
CATEGORY_FOLDERS = {
    "3d-immersive", "audio-music", "creative-tools", "educational",
    "experimental-ai", "games-puzzles", "generative-art",
    "particle-physics", "visual-art",
}


def find_evomon_apps():
    """Find all evomon-* HTML files (excluding archives)."""
    apps = []
    for cat_dir in APPS_DIR.iterdir():
        if cat_dir.is_dir() and cat_dir.name in CATEGORY_FOLDERS:
            for f in cat_dir.glob("evomon-*.html"):
                if "archive" not in str(f):
                    apps.append(f)
    return sorted(apps)


def score_dimension_structural(html):
    """Score structural quality (0-15)."""
    score = 0
    if "<!DOCTYPE html>" in html or "<!doctype html>" in html:
        score += 3
    if 'name="viewport"' in html:
        score += 3
    if "<title>" in html:
        score += 3
    if "<style>" in html:
        score += 3
    if "<script>" in html:
        score += 3
    return min(score, 15)


def score_dimension_scale(html, file_size):
    """Score scale (0-10)."""
    lines = html.count("\n") + 1
    score = 0
    if lines >= 500:
        score += 2
    if lines >= 1000:
        score += 2
    if lines >= 1500:
        score += 1
    if file_size >= 15000:
        score += 2
    if file_size >= 30000:
        score += 2
    if file_size >= 50000:
        score += 1
    return min(score, 10)


def score_dimension_systems(html):
    """Score systems complexity (0-20)."""
    checks = [
        ("canvas", "canvas" in html.lower() or "getContext" in html),
        ("gameloop", "requestAnimationFrame" in html or "setInterval" in html),
        ("audio", "AudioContext" in html or "Web Audio" in html or "createOscillator" in html),
        ("storage", "localStorage" in html),
        ("procedural", "Math.random" in html or "noise" in html.lower() or "seed" in html.lower()),
        ("input", "addEventListener" in html and ("keydown" in html or "keyup" in html)),
        ("collision", "collision" in html.lower() or "intersect" in html.lower() or "overlap" in html.lower()),
        ("particles", "particle" in html.lower()),
        ("statemachine", "state" in html.lower() and ("switch" in html or "'menu'" in html or '"menu"' in html)),
        ("classes", "class " in html and "constructor" in html),
    ]
    return min(sum(2 for _, hit in checks if hit), 20)


def score_dimension_completeness(html):
    """Score completeness (0-15)."""
    checks = [
        ("pause", "pause" in html.lower() and ("Escape" in html or "ESC" in html.upper())),
        ("gameover", "game over" in html.lower() or "gameOver" in html or "game_over" in html),
        ("scoring", "score" in html.lower()),
        ("progression", "level" in html.lower() or "evolv" in html.lower() or "xp" in html.lower()),
        ("titlescreen", "title" in html.lower() and ("screen" in html.lower() or "menu" in html.lower())),
        ("hud", "hud" in html.lower() or "HUD" in html or "health" in html.lower()),
        ("tutorial", "tutorial" in html.lower() or "instruction" in html.lower() or "how to" in html.lower()),
    ]
    hits = sum(1 for _, hit in checks if hit)
    return min(int(hits * 15 / 7), 15)


def score_dimension_playability(html):
    """Score playability (0-25)."""
    checks = [
        ("screenshake", "shake" in html.lower()),
        ("feedback", "flash" in html.lower() or "feedback" in html.lower()),
        ("combo", "combo" in html.lower() or "chain" in html.lower()),
        ("difficulty", "difficulty" in html.lower() or "easy" in html.lower() and "hard" in html.lower()),
        ("enemyai", "enemy" in html.lower() or "opponent" in html.lower()),
        ("boss", "boss" in html.lower()),
        ("entities", html.lower().count("class ") >= 5),
        ("abilities", "abilit" in html.lower() or "skill" in html.lower() or "power" in html.lower()),
        ("touch", "touchstart" in html or "touchmove" in html),
        ("controls", "keydown" in html and "keyup" in html),
        ("restart", "restart" in html.lower()),
        ("highscore", "highscore" in html.lower() or "high score" in html.lower() or "best" in html.lower()),
    ]
    hits = sum(1 for _, hit in checks if hit)
    return min(int(hits * 25 / 12), 25)


def score_dimension_polish(html):
    """Score polish (0-15)."""
    checks = [
        ("animations", "animation" in html.lower() or "transition" in html.lower() or "@keyframes" in html),
        ("gradients", "gradient" in html.lower()),
        ("shadows", "shadow" in html.lower()),
        ("responsive", "@media" in html or "100vw" in html or "100vh" in html),
        ("colors", len(re.findall(r"#[0-9a-fA-F]{3,8}", html)) >= 5),
        ("effects", "glow" in html.lower() or "blur" in html.lower() or "opacity" in html),
    ]
    hits = sum(1 for _, hit in checks if hit)
    return min(int(hits * 15 / 6), 15)


def score_app(filepath):
    """Score an evomon app on all 6 dimensions. Returns dict."""
    html = filepath.read_text(encoding="utf-8", errors="replace")
    file_size = filepath.stat().st_size

    structural = score_dimension_structural(html)
    scale = score_dimension_scale(html, file_size)
    systems = score_dimension_systems(html)
    completeness = score_dimension_completeness(html)
    playability = score_dimension_playability(html)
    polish = score_dimension_polish(html)
    total = structural + scale + systems + completeness + playability + polish

    return {
        "file": filepath.name,
        "path": str(filepath.relative_to(ROOT)),
        "category": filepath.parent.name,
        "lines": html.count("\n") + 1,
        "size": file_size,
        "structural": structural,
        "scale": scale,
        "systems": systems,
        "completeness": completeness,
        "playability": playability,
        "polish": polish,
        "total": total,
        "weak_dims": _find_weak_dims(structural, scale, systems, completeness, playability, polish),
    }


def _find_weak_dims(structural, scale, systems, completeness, playability, polish):
    """Identify the 2-3 weakest dimensions by % of max."""
    dims = [
        ("structural", structural, 15),
        ("scale", scale, 10),
        ("systems", systems, 20),
        ("completeness", completeness, 15),
        ("playability", playability, 25),
        ("polish", polish, 15),
    ]
    by_pct = sorted(dims, key=lambda d: d[1] / d[2])
    return [(name, val, mx) for name, val, mx in by_pct[:3]]


def print_scorecard(scores):
    """Print a formatted scorecard for all evomon apps."""
    print("\n╔══════════════════════════════════════════════════════════════════════╗")
    print("║                    EVOMON FRANCHISE HEALTH                          ║")
    print("╠══════════════════════════════════════════════════════════════════════╣")

    header = f"{'File':<35} {'Str':>3} {'Scl':>3} {'Sys':>3} {'Cmp':>3} {'Ply':>3} {'Pol':>3} {'TOT':>4}"
    print(f"║ {header} ║")
    print("╠══════════════════════════════════════════════════════════════════════╣")

    for s in sorted(scores, key=lambda x: x["total"]):
        row = (
            f"{s['file']:<35} "
            f"{s['structural']:>3} {s['scale']:>3} {s['systems']:>3} "
            f"{s['completeness']:>3} {s['playability']:>3} {s['polish']:>3} "
            f"{s['total']:>4}"
        )
        print(f"║ {row} ║")

    avg = sum(s["total"] for s in scores) / len(scores) if scores else 0
    print("╠══════════════════════════════════════════════════════════════════════╣")
    print(f"║ {'Apps: ' + str(len(scores)):<25} {'Avg Score: ' + f'{avg:.1f}/100':<25}       ║")
    print("╚══════════════════════════════════════════════════════════════════════╝")

    # Show weak dimensions for lowest-scoring apps
    weak = [s for s in scores if s["total"] < 70]
    if weak:
        print("\n🔻 Apps needing evolution:")
        for s in sorted(weak, key=lambda x: x["total"]):
            dims = ", ".join(f"{n}={v}/{m}" for n, v, m in s["weak_dims"])
            print(f"  {s['file']}: {s['total']}/100 — weak: {dims}")


def print_molt_instructions(scores):
    """Print instructions for running the evomon-molter subagent."""
    weak = [s for s in sorted(scores, key=lambda x: x["total"]) if s["total"] < 75]
    if not weak:
        print("\n✅ All evomon apps score 75+. Consider breeding new apps instead.")
        return

    print("\n🧬 To molt the EvoMon franchise, invoke the evomon-molter subagent:")
    print("   /agent evomon-molter")
    print(f"\n   Priority targets ({len(weak)} apps below 75):")
    for s in weak:
        dims = ", ".join(f"{n}" for n, v, m in s["weak_dims"])
        print(f"   • {s['path']}: {s['total']}/100 (improve: {dims})")


def main():
    parser = argparse.ArgumentParser(description="EvoMon franchise autonomous molter")
    parser.add_argument("--molt", action="store_true", help="Trigger molt cycle via evomon-molter agent")
    parser.add_argument("--status", action="store_true", help="Show franchise health scorecard")
    parser.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    parser.add_argument("--verbose", action="store_true", help="Show detailed scoring")
    args = parser.parse_args()

    apps = find_evomon_apps()
    if not apps:
        print("❌ No evomon-* apps found under apps/")
        sys.exit(1)

    print(f"🔍 Found {len(apps)} EvoMon apps")

    scores = [score_app(f) for f in apps]
    print_scorecard(scores)

    if args.verbose:
        for s in sorted(scores, key=lambda x: x["total"]):
            print(f"\n  {s['file']} ({s['category']}):")
            print(f"    {s['lines']} lines, {s['size']:,} bytes")
            for name, val, mx in s["weak_dims"]:
                pct = int(val / mx * 100)
                print(f"    ⚠️  {name}: {val}/{mx} ({pct}%)")

    if args.molt and not args.dry_run:
        print_molt_instructions(scores)
        print("\n⚡ To run autonomously, invoke: /agent evomon-molter")
    elif args.molt and args.dry_run:
        print("\n[DRY RUN] Would invoke evomon-molter subagent for molt cycle")
        print_molt_instructions(scores)
    elif args.status:
        # Just the scorecard (already printed above)
        pass
    else:
        print_molt_instructions(scores)


if __name__ == "__main__":
    main()
