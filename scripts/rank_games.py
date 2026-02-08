#!/usr/bin/env python3
"""App Rankings Generator.

Scores all HTML apps on universal + adaptive quality dimensions.

Universal dimensions (regex, fast, always available):
  - Structural (15): DOCTYPE, viewport, title, inline CSS/JS, no ext deps
  - Scale (10): Line count, file size
  - Polish (15): Animations, gradients, shadows, responsive, colors, effects

Adaptive dimensions (LLM-assessed, content-aware):
  - Craft (20): How sophisticated are the techniques for what this IS
  - Completeness (15): Does this feel finished for what it's trying to be
  - Engagement (25): Would someone spend 10+ minutes with this

THE MEDIUM IS THE MESSAGE: a synth is scored on synth quality, a game on
game quality, a drawing tool on drawing quality. The LLM figures out what
quality means for each piece of content.

If LLM is unavailable, only universal dimensions are scored (40/100 max).
Legacy regex-based game dimensions (systems/completeness/playability) are
kept as fallback when LLM is unavailable, labeled as "legacy" in output.

Usage:
    python3 scripts/rank_games.py              # Generate rankings.json
    python3 scripts/rank_games.py --verbose     # Show per-app breakdown
    python3 scripts/rank_games.py --push        # Generate + commit + push
    python3 scripts/rank_games.py --legacy      # Force legacy game-only scoring
"""

import json
import re
import sys
import hashlib
from datetime import datetime
from pathlib import Path

try:
    from runtime_verify import verify_app as _verify_app
except ImportError:
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        from runtime_verify import verify_app as _verify_app
    except ImportError:
        _verify_app = None

try:
    from content_identity import get_adaptive_scores as _get_adaptive_scores
except ImportError:
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from content_identity import get_adaptive_scores as _get_adaptive_scores
    except ImportError:
        _get_adaptive_scores = None

ROOT = Path(__file__).resolve().parent.parent
APPS_DIR = ROOT / "apps"
MANIFEST = APPS_DIR / "manifest.json"
OUTPUT = APPS_DIR / "rankings.json"
PLAYER_RATINGS = APPS_DIR / "player-ratings.json"

ALL_CATEGORIES = {
    "games_puzzles": "games-puzzles",
    "3d_immersive": "3d-immersive",
    "audio_music": "audio-music",
    "creative_tools": "creative-tools",
    "experimental_ai": "experimental-ai",
    "generative_art": "generative-art",
    "particle_physics": "particle-physics",
    "visual_art": "visual-art",
    "educational_tools": "educational",
}


def score_structural(content: str) -> dict:
    """Structural quality (0-15)."""
    score = 0
    details = []
    if "<!DOCTYPE html>" in content or "<!doctype html>" in content:
        score += 3; details.append("doctype")
    if '<meta name="viewport"' in content:
        score += 2; details.append("viewport")
    if "<title>" in content and "</title>" in content:
        t = re.search(r"<title>(.*?)</title>", content)
        if t and len(t.group(1).strip()) > 2:
            score += 2; details.append("title")
    if "<style>" in content and "</style>" in content:
        score += 2; details.append("inline-css")
    if "<script>" in content and "</script>" in content:
        score += 2; details.append("inline-js")
    ext = bool(re.search(r'(src|href)="https?://', content))
    if not ext:
        score += 4; details.append("no-ext-deps")
    return {"score": min(score, 15), "max": 15, "details": details}


def score_scale(content: str) -> dict:
    """Scale and ambition (0-10)."""
    lines = content.count("\n") + 1
    size_kb = len(content) / 1024
    score = 0
    details = []
    if lines >= 2000:
        score += 5; details.append(f"{lines}L")
    elif lines >= 1000:
        score += 3; details.append(f"{lines}L")
    elif lines >= 500:
        score += 2; details.append(f"{lines}L")
    else:
        details.append(f"{lines}L-small")

    if 40 <= size_kb <= 200:
        score += 5; details.append(f"{size_kb:.0f}KB-optimal")
    elif size_kb > 200 and lines >= 2000:
        score += 5; details.append(f"{size_kb:.0f}KB-ambitious")
    elif size_kb > 200:
        score += 3; details.append(f"{size_kb:.0f}KB-large")
    elif 20 <= size_kb < 40:
        score += 3; details.append(f"{size_kb:.0f}KB")
    else:
        score += 1; details.append(f"{size_kb:.0f}KB-tiny")
    return {"score": min(score, 10), "max": 10, "details": details}


def score_systems(content: str) -> dict:
    """Game systems depth (0-20)."""
    score = 0
    details = []
    checks = {
        "canvas": (r"canvas|getContext\(['\"]2d['\"]\)|WebGL", 3),
        "game-loop": (r"requestAnimationFrame", 3),
        "audio": (r"AudioContext|webkitAudioContext|createOscillator", 3),
        "saves": (r"localStorage\.(set|get)Item", 3),
        "procedural": (r"Math\.random|seed|noise|procedural", 1),
        "input": (r"addEventListener\(['\"]key|addEventListener\(['\"]mouse|addEventListener\(['\"]touch", 2),
        "collision": (r"collisi|intersect|overlap|hitTest|bounds", 1),
        "particles": (r"particle|emitter|spawn.*particle", 1),
        "state-machine": (r"gameState|state\s*===?\s*['\"]|switch\s*\(\s*state", 2),
        "classes": (r"\bclass\s+[A-Z]\w+", 1),
    }
    for name, (pattern, points) in checks.items():
        if re.search(pattern, content, re.IGNORECASE):
            score += points; details.append(name)
    return {"score": min(score, 20), "max": 20, "details": details}


def score_completeness(content: str) -> dict:
    """Game completeness (0-15)."""
    score = 0
    details = []
    checks = {
        "pause": (r"pause|paused|isPaused", 2),
        "game-over": (r"game.?over|gameOver|game_over|you (died|lose|lost|win|won)", 2),
        "scoring": (r"\bscore\b.*\+|score\s*[+=]|updateScore|addScore", 2),
        "progression": (r"level|wave|stage|round|floor|depth", 2),
        "title-screen": (r"title.?screen|main.?menu|start.?game|startGame|showMenu", 2),
        "hud": (r"drawHUD|renderHUD|updateHUD|hud|health.?bar|score.?display", 1),
        "endings": (r"ending|victory|defeat|you (saved|escaped|conquered)", 2),
        "tutorial": (r"tutorial|instructions|how to play|controls", 2),
    }
    for name, (pattern, points) in checks.items():
        if re.search(pattern, content, re.IGNORECASE):
            score += points; details.append(name)
    return {"score": min(score, 15), "max": 15, "details": details}


def score_playability(content: str) -> dict:
    """How fun/playable the game likely is (0-25). The big one."""
    score = 0
    details = []

    # --- Feedback & Juice (7 pts) ---
    # Screen shake / camera effects on impact
    if re.search(r"shake|camera.*offset|screen.*shake|vibrat", content, re.IGNORECASE):
        score += 2; details.append("screen-shake")
    # Hit feedback (flash, blink, invincible frames)
    if re.search(r"hit.*flash|damage.*flash|invincib|blink|knockback|recoil", content, re.IGNORECASE):
        score += 2; details.append("hit-feedback")
    # Combo / multiplier / streak system
    if re.search(r"combo|multiplier|streak|chain|critical", content, re.IGNORECASE):
        score += 2; details.append("combo-system")
    # Sound variety (multiple distinct sound functions or play calls)
    sound_calls = len(re.findall(r"play(?:Sound|SFX|Audio|Note|Tone)\s*\(|\.play\s*\(|createOscillator", content))
    if sound_calls >= 5:
        score += 1; details.append(f"sound-variety({sound_calls})")

    # --- Difficulty & Challenge (5 pts) ---
    # Difficulty settings
    if re.search(r"difficulty|easy|medium|hard|normal|challenge|difficultyLevel", content, re.IGNORECASE):
        score += 2; details.append("difficulty-settings")
    # Adaptive / scaling difficulty
    if re.search(r"speed.*\+|faster|harder|increase.*difficult|ramp|escalat|scale.*difficult", content, re.IGNORECASE):
        score += 1; details.append("scaling-difficulty")
    # Enemy AI / pathfinding / behavior
    if re.search(r"enemy|opponent|ai\b|pathfind|chase|patrol|behavior|strategy", content, re.IGNORECASE):
        score += 1; details.append("enemy-ai")
    # Boss / elite / miniboss
    if re.search(r"\bboss\b|elite|miniboss|boss.*fight|final.*boss", content, re.IGNORECASE):
        score += 1; details.append("boss-fights")

    # --- Variety & Content (5 pts) ---
    # Multiple entity/enemy types
    entity_types = len(set(re.findall(r"type:\s*['\"](\w+)['\"]|entityType|enemyType|class\s+(\w*(?:Enemy|Monster|Creature|Unit|Character))", content)))
    if entity_types >= 3:
        score += 2; details.append(f"entity-variety({entity_types})")
    elif entity_types >= 1:
        score += 1; details.append(f"entity-variety({entity_types})")
    # Weapons / abilities / spells / skills
    if re.search(r"weapon|spell|ability|skill|power.?up|upgrade|inventory|item|equip", content, re.IGNORECASE):
        score += 1; details.append("abilities")
    # Multiple levels/maps/worlds
    level_refs = len(re.findall(r"level\s*[\[=]|map\s*[\[=]|world\s*[\[=]|zone|biome|area|room", content, re.IGNORECASE))
    if level_refs >= 5:
        score += 2; details.append(f"level-variety({level_refs})")
    elif level_refs >= 2:
        score += 1; details.append(f"level-variety({level_refs})")

    # --- Controls & Responsiveness (4 pts) ---
    # Both keydown AND keyup (responsive controls, not just keydown)
    if re.search(r"keydown", content) and re.search(r"keyup", content):
        score += 2; details.append("responsive-controls")
    elif re.search(r"keydown|keypress", content):
        score += 1; details.append("basic-controls")
    # Touch/mobile support
    if re.search(r"touchstart|touchmove|touchend|ontouchstart", content, re.IGNORECASE):
        score += 1; details.append("touch-support")
    # Mouse + keyboard (dual input)
    has_mouse = bool(re.search(r"addEventListener\(['\"]mouse|onclick|click", content))
    has_keys = bool(re.search(r"addEventListener\(['\"]key", content))
    if has_mouse and has_keys:
        score += 1; details.append("dual-input")

    # --- Replayability & Session (4 pts) ---
    # Multiple endings or win conditions
    ending_refs = len(re.findall(r"ending|victory|you (win|won|saved|escaped)|game.*complete|congratulation", content, re.IGNORECASE))
    if ending_refs >= 3:
        score += 2; details.append(f"multi-ending({ending_refs})")
    elif ending_refs >= 1:
        score += 1; details.append(f"ending({ending_refs})")
    # Quick restart
    if re.search(r"restart|reset.*game|new.*game|play.*again|try.*again", content, re.IGNORECASE):
        score += 1; details.append("quick-restart")
    # High score / leaderboard / personal best
    if re.search(r"high.?score|best.?score|leaderboard|personal.?best|record", content, re.IGNORECASE):
        score += 1; details.append("high-scores")

    return {"score": min(score, 25), "max": 25, "details": details}


def score_polish(content: str) -> dict:
    """Visual/audio polish (0-15)."""
    score = 0
    details = []
    checks = {
        "animations": (r"transition|animation|@keyframes|animate|tween|ease", 2),
        "gradients": (r"gradient|linearGradient|radialGradient", 2),
        "shadows": (r"shadow|boxShadow|text-shadow|dropShadow", 1),
        "responsive": (r"@media|resize|innerWidth|responsive", 2),
        "colors": (r"hsl\(|rgba\(|#[0-9a-f]{6}", 2),
        "effects": (r"blur|glow|shake|flash|pulse|ripple|wave", 2),
        "smooth": (r"lerp|interpolat|smooth|delta.*time|deltaTime|dt\b", 2),
        "accessibility": (r"aria-|role=|tabindex|focus.*visible", 2),
    }
    for name, (pattern, points) in checks.items():
        if re.search(pattern, content, re.IGNORECASE):
            score += points; details.append(name)
    return {"score": min(score, 15), "max": 15, "details": details}


def compute_fingerprint(content: str) -> str:
    return hashlib.md5(content.encode()[:8192]).hexdigest()[:12]


def load_player_ratings() -> dict:
    """Load crowd-sourced player ratings if available."""
    if PLAYER_RATINGS.exists():
        try:
            data = json.loads(PLAYER_RATINGS.read_text())
            return data.get("ratings", {})
        except Exception:
            pass
    return {}


def grade_from_score(score: int) -> str:
    if score >= 90: return "S"
    elif score >= 80: return "A"
    elif score >= 65: return "B"
    elif score >= 50: return "C"
    elif score >= 35: return "D"
    else: return "F"


def score_game(filepath: Path, content: str = None, player_ratings: dict = None, legacy: bool = False) -> dict:
    """Score a single app file across universal + adaptive dimensions.

    When LLM is available and legacy=False, uses content_identity for
    adaptive scoring (craft/completeness/engagement). Falls back to
    legacy regex-based game dimensions when LLM is unavailable.
    """
    if content is None:
        content = filepath.read_text(errors="replace")

    structural = score_structural(content)
    scale = score_scale(content)
    polish = score_polish(content)

    # Adaptive scoring: LLM-assessed, content-aware dimensions
    adaptive = None
    if not legacy and _get_adaptive_scores is not None:
        try:
            adaptive = _get_adaptive_scores(filepath, content)
        except Exception:
            pass

    if adaptive:
        # Adaptive mode: universal (40) + LLM-assessed (60) = 100
        craft = {"score": adaptive["craft_score"], "max": 20, "details": [f"medium:{adaptive.get('medium', 'unknown')}"]}
        completeness = {"score": adaptive["completeness_score"], "max": 15, "details": ["llm-assessed"]}
        engagement = {"score": adaptive["engagement_score"], "max": 25, "details": ["llm-assessed"]}
        raw_total = (
            structural["score"] + scale["score"] + polish["score"]
            + craft["score"] + completeness["score"] + engagement["score"]
        )
        dimensions = {
            "structural": structural,
            "scale": scale,
            "craft": craft,
            "completeness": completeness,
            "engagement": engagement,
            "polish": polish,
        }
        scoring_mode = "adaptive"
    else:
        # Legacy mode: regex-based game dimensions
        systems = score_systems(content)
        completeness = score_completeness(content)
        playability = score_playability(content)
        raw_total = (
            structural["score"] + scale["score"] + systems["score"]
            + completeness["score"] + playability["score"] + polish["score"]
        )
        dimensions = {
            "structural": structural,
            "scale": scale,
            "systems": systems,
            "completeness": completeness,
            "playability": playability,
            "polish": polish,
        }
        scoring_mode = "legacy"

    # Runtime health modifier: penalize broken apps, reward verified-healthy ones
    # This catches games that score well on feature detection but crash on load
    runtime_health = None
    health_modifier = 0
    try:
        if _verify_app is None:
            raise ImportError("runtime_verify not available")
        health_result = _verify_app(filepath)
        health_score = health_result["health_score"]
        verdict = health_result["verdict"]
        runtime_health = {
            "score": health_score,
            "verdict": verdict,
            "modifier": 0,
        }
        if verdict == "broken":
            # Broken apps get a significant penalty (up to -15)
            health_modifier = -min(15, max(5, (70 - health_score) // 5))
            runtime_health["modifier"] = health_modifier
        elif verdict == "fragile":
            # Fragile apps get a mild penalty (up to -5)
            health_modifier = -min(5, max(1, (60 - health_score) // 10))
            runtime_health["modifier"] = health_modifier
        elif verdict == "healthy" and health_score >= 85:
            # Verified-healthy apps get a small bonus (up to +3)
            health_modifier = min(3, (health_score - 85) // 5)
            runtime_health["modifier"] = health_modifier
    except Exception:
        pass  # Runtime verify unavailable — no modifier

    # Player rating bonus: up to 5 bonus points if rated 5 stars
    # This means crowd favorites can push past purely algorithmic scores
    player_data = None
    player_bonus = 0
    if player_ratings:
        key = filepath.name
        if key in player_ratings:
            pr = player_ratings[key]
            avg_rating = pr.get("avg", 0)
            num_ratings = pr.get("count", 0)
            # Only apply bonus if enough ratings (min 3)
            if num_ratings >= 3:
                player_bonus = round(avg_rating)  # 0-5 bonus
                player_data = {"avg": avg_rating, "count": num_ratings, "bonus": player_bonus}

    total = max(0, min(raw_total + player_bonus + health_modifier, 100))

    title_match = re.search(r"<title>(.*?)</title>", content)
    title = title_match.group(1).strip() if title_match else filepath.stem.replace("-", " ").title()
    lines = content.count("\n") + 1
    size_kb = len(content) / 1024

    result = {
        "file": filepath.name,
        "title": title,
        "score": total,
        "algo_score": raw_total,
        "grade": grade_from_score(total),
        "scoring_mode": scoring_mode,
        "lines": lines,
        "size_kb": round(size_kb, 1),
        "fingerprint": compute_fingerprint(content),
        "dimensions": dimensions,
    }
    if player_data:
        result["player_rating"] = player_data
    if runtime_health:
        result["runtime_health"] = runtime_health

    return result


def score_single_app(filepath) -> dict:
    """Score a single app file and return a compact result.

    Convenience wrapper for molt_pipeline.py and other callers that need
    per-file scoring without building full rankings.

    Args:
        filepath: Path or str to an HTML app file.

    Returns:
        dict with keys: score, grade, dimensions (each with score/max/details),
        size_bytes, lines, title.
    """
    filepath = Path(filepath)
    content = filepath.read_text(errors="replace")
    full = score_game(filepath, content)
    return {
        "score": full["score"],
        "grade": full["grade"],
        "title": full["title"],
        "lines": full["lines"],
        "size_bytes": len(content),
        "dimensions": {
            dim: {"score": data["score"], "max": data["max"]}
            for dim, data in full["dimensions"].items()
        },
    }


def load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text())
    return {"categories": {}}


def build_rankings(verbose: bool = False, legacy: bool = False) -> dict:
    manifest = load_manifest()
    player_ratings = load_player_ratings()
    all_games = []
    category_stats = {}

    if verbose:
        mode_label = "legacy (regex)" if legacy else "adaptive (LLM + regex)"
        print(f"  Scoring mode: {mode_label}\n")

    for cat_key, folder in ALL_CATEGORIES.items():
        cat_dir = APPS_DIR / folder
        if not cat_dir.exists():
            continue

        cat_games = []
        html_files = sorted(cat_dir.glob("*.html"))

        for f in html_files:
            try:
                content = f.read_text(errors="replace")
                if len(content) < 500:
                    continue

                result = score_game(f, content, player_ratings, legacy=legacy)
                result["category"] = cat_key
                result["category_folder"] = folder
                result["path"] = f"apps/{folder}/{f.name}"
                cat_games.append(result)

                if verbose:
                    dims = result["dimensions"]
                    pr = result.get("player_rating")
                    pr_str = f" R:{pr['avg']:.1f}({pr['count']})" if pr else ""
                    mode_tag = "A" if result.get("scoring_mode") == "adaptive" else "L"
                    if "craft" in dims:
                        print(
                            f"  [{result['grade']}][{mode_tag}] {result['score']:3d}/100  "
                            f"St:{dims['structural']['score']}/{dims['structural']['max']} "
                            f"Sc:{dims['scale']['score']}/{dims['scale']['max']} "
                            f"Cr:{dims['craft']['score']}/{dims['craft']['max']} "
                            f"Co:{dims['completeness']['score']}/{dims['completeness']['max']} "
                            f"En:{dims['engagement']['score']}/{dims['engagement']['max']} "
                            f"Po:{dims['polish']['score']}/{dims['polish']['max']}"
                            f"{pr_str}  "
                            f"{result['title'][:35]}"
                        )
                    else:
                        print(
                            f"  [{result['grade']}][{mode_tag}] {result['score']:3d}/100  "
                            f"St:{dims['structural']['score']}/{dims['structural']['max']} "
                            f"Sc:{dims['scale']['score']}/{dims['scale']['max']} "
                            f"Sy:{dims['systems']['score']}/{dims['systems']['max']} "
                            f"Co:{dims['completeness']['score']}/{dims['completeness']['max']} "
                            f"Pl:{dims['playability']['score']}/{dims['playability']['max']} "
                            f"Po:{dims['polish']['score']}/{dims['polish']['max']}"
                            f"{pr_str}  "
                            f"{result['title'][:35]}"
                        )
            except Exception as e:
                if verbose:
                    print(f"  [ERR] {f.name}: {e}")

        if cat_games:
            scores = [g["score"] for g in cat_games]
            # Engagement score (adaptive) or playability (legacy)
            engage_key = "engagement" if "engagement" in cat_games[0].get("dimensions", {}) else "playability"
            engage_scores = [g["dimensions"].get(engage_key, {}).get("score", 0) for g in cat_games]
            category_stats[cat_key] = {
                "count": len(cat_games),
                "avg_score": round(sum(scores) / len(scores), 1),
                "avg_engagement": round(sum(engage_scores) / len(engage_scores), 1),
                "top_score": max(scores),
                "folder": folder,
                "title": manifest.get("categories", {}).get(cat_key, {}).get("title", cat_key),
            }
            all_games.extend(cat_games)

        if verbose and cat_games:
            scores = [g["score"] for g in cat_games]
            print(f"\n  {cat_key}: {len(cat_games)} apps, avg {sum(scores)/len(scores):.1f}\n")

    # Sort by total score descending
    all_games.sort(key=lambda g: g["score"], reverse=True)

    for i, game in enumerate(all_games):
        game["rank"] = i + 1

    grade_dist = {}
    for g in all_games:
        grade_dist[g["grade"]] = grade_dist.get(g["grade"], 0) + 1

    histogram = {}
    for g in all_games:
        bucket = (g["score"] // 10) * 10
        label = f"{bucket}-{bucket+9}"
        histogram[label] = histogram.get(label, 0) + 1

    # Engagement scores (adaptive) or playability (legacy)
    engage_key = "engagement" if all_games and "engagement" in all_games[0].get("dimensions", {}) else "playability"
    engage_scores = [g["dimensions"].get(engage_key, {}).get("score", 0) for g in all_games]

    # Runtime health summary
    health_verdicts = {}
    for g in all_games:
        rh = g.get("runtime_health")
        if rh:
            v = rh["verdict"]
            health_verdicts[v] = health_verdicts.get(v, 0) + 1

    # Scoring mode summary
    mode_counts = {}
    for g in all_games:
        m = g.get("scoring_mode", "legacy")
        mode_counts[m] = mode_counts.get(m, 0) + 1

    # Top engagement (most compelling apps regardless of type)
    by_engagement = sorted(all_games, key=lambda g: g["dimensions"].get(engage_key, {}).get("score", 0), reverse=True)
    top_engaging = [
        {"rank": i+1, "file": g["file"], "title": g["title"],
         "engagement": g["dimensions"].get(engage_key, {}).get("score", 0),
         "medium": g["dimensions"].get("craft", {}).get("details", ["unknown"])[0] if "craft" in g["dimensions"] else "legacy",
         "score": g["score"], "grade": g["grade"], "path": g["path"]}
        for i, g in enumerate(by_engagement[:20])
    ]

    rankings = {
        "generated": datetime.now().isoformat(),
        "total_apps": len(all_games),
        "has_player_ratings": bool(player_ratings),
        "scoring_modes": mode_counts,
        "summary": {
            "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
            "median_score": sorted(scores)[len(scores) // 2] if scores else 0,
            "top_10_avg": round(sum(scores[:10]) / min(10, len(scores)), 1) if scores else 0,
            "avg_engagement": round(sum(engage_scores) / len(engage_scores), 1) if engage_scores else 0,
            "grade_distribution": grade_dist,
            "score_histogram": histogram,
            "runtime_health": health_verdicts,
        },
        "categories": category_stats,
        "top_engaging": top_engaging,
        # Keep legacy key for backward compat
        "top_playable": top_engaging,
        "rankings": all_games,
    }

    return rankings


def main():
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    push = "--push" in sys.argv
    legacy = "--legacy" in sys.argv

    if verbose:
        print("Scanning all app categories...\n")

    rankings = build_rankings(verbose=verbose, legacy=legacy)

    OUTPUT.write_text(json.dumps(rankings, indent=2))
    modes = rankings.get("scoring_modes", {})
    mode_str = ", ".join(f"{k}:{v}" for k, v in modes.items())
    print(f"\nWrote {OUTPUT} ({rankings['total_apps']} apps ranked, modes: {mode_str})")
    print(f"  Avg: {rankings['summary']['avg_score']} | "
          f"Median: {rankings['summary']['median_score']} | "
          f"Top 10 avg: {rankings['summary']['top_10_avg']}")
    print(f"  Avg Engagement: {rankings['summary']['avg_engagement']}/25")
    print(f"  Grades: {rankings['summary']['grade_distribution']}")
    print(f"  Player ratings: {'loaded' if rankings['has_player_ratings'] else 'none'}")
    rh = rankings['summary'].get('runtime_health', {})
    if rh:
        print(f"  Runtime Health: healthy:{rh.get('healthy',0)} fragile:{rh.get('fragile',0)} broken:{rh.get('broken',0)}")

    if rankings.get("top_engaging"):
        print(f"\n  Most Engaging:")
        for g in rankings["top_engaging"][:5]:
            medium = g.get("medium", "")
            print(f"    [{g['grade']}] Engage:{g['engagement']}/25  {g['title'][:35]}  ({medium})")

    if push:
        import subprocess
        dist = rankings["summary"]["grade_distribution"]
        msg = (
            f"chore: update rankings.json ({rankings['total_apps']} apps scored)\n\n"
            f"Avg: {rankings['summary']['avg_score']} | "
            f"Engagement: {rankings['summary']['avg_engagement']}/25 | "
            f"Top 10: {rankings['summary']['top_10_avg']}\n"
            f"Grades: S:{dist.get('S',0)} A:{dist.get('A',0)} "
            f"B:{dist.get('B',0)} C:{dist.get('C',0)} "
            f"D:{dist.get('D',0)} F:{dist.get('F',0)}\n\n"
            f"Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
        )
        subprocess.run(["git", "add", str(OUTPUT)], cwd=ROOT)
        # Also commit player-ratings.json if it exists
        if PLAYER_RATINGS.exists():
            subprocess.run(["git", "add", str(PLAYER_RATINGS)], cwd=ROOT)
        result = subprocess.run(
            ["git", "commit", "-m", msg],
            cwd=ROOT, capture_output=True, text=True,
        )
        if result.returncode == 0:
            subprocess.run(["git", "push"], cwd=ROOT)
            print("  Published rankings to GitHub Pages.")
        else:
            print(f"  No changes to commit: {result.stdout.strip()}")


if __name__ == "__main__":
    main()
