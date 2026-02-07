#!/usr/bin/env python3
"""Game Rankings Generator.

Scans all HTML game files, scores them on multiple quality dimensions,
and publishes rankings.json for the public leaderboard page.

Usage:
    python3 scripts/rank_games.py              # Generate rankings.json
    python3 scripts/rank_games.py --verbose     # Show per-game breakdown
    python3 scripts/rank_games.py --push        # Generate + git add/commit/push

Output: apps/rankings.json (served via GitHub Pages as CDN)
"""

import json
import os
import re
import sys
import hashlib
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APPS_DIR = ROOT / "apps"
MANIFEST = APPS_DIR / "manifest.json"
OUTPUT = APPS_DIR / "rankings.json"

# Categories that contain games
GAME_CATEGORIES = {
    "games_puzzles": "games-puzzles",
    "3d_immersive": "3d-immersive",
    "experimental_ai": "experimental-ai",
}

# Scan ALL categories
ALL_CATEGORIES = {
    "games_puzzles": "games-puzzles",
    "3d_immersive": "3d-immersive",
    "audio_music": "audio-music",
    "creative_tools": "creative-tools",
    "experimental_ai": "experimental-ai",
    "generative_art": "generative-art",
    "particle_physics": "particle-physics",
    "visual_art": "visual-art",
}


def score_structural(content: str) -> dict:
    """Score structural quality (0-20)."""
    score = 0
    details = []
    if "<!DOCTYPE html>" in content or "<!doctype html>" in content:
        score += 4
        details.append("doctype")
    if '<meta name="viewport"' in content:
        score += 3
        details.append("viewport")
    if "<title>" in content and "</title>" in content:
        t = re.search(r"<title>(.*?)</title>", content)
        if t and len(t.group(1).strip()) > 2:
            score += 3
            details.append("title")
    if "<style>" in content and "</style>" in content:
        score += 3
        details.append("inline-css")
    if "<script>" in content and "</script>" in content:
        score += 3
        details.append("inline-js")
    ext = bool(re.search(r'(src|href)="https?://', content))
    if not ext:
        score += 4
        details.append("no-ext-deps")
    return {"score": min(score, 20), "max": 20, "details": details}


def score_scale(content: str) -> dict:
    """Score scale/ambition (0-15)."""
    lines = content.count("\n") + 1
    size_kb = len(content) / 1024
    score = 0
    details = []
    if lines >= 2000:
        score += 8
        details.append(f"{lines}L")
    elif lines >= 1000:
        score += 5
        details.append(f"{lines}L")
    elif lines >= 500:
        score += 3
        details.append(f"{lines}L")
    else:
        details.append(f"{lines}L-small")

    if 40 <= size_kb <= 200:
        score += 7
        details.append(f"{size_kb:.0f}KB-optimal")
    elif size_kb > 200:
        score += 5
        details.append(f"{size_kb:.0f}KB-large")
    elif 20 <= size_kb < 40:
        score += 4
        details.append(f"{size_kb:.0f}KB")
    else:
        score += 1
        details.append(f"{size_kb:.0f}KB-tiny")
    return {"score": min(score, 15), "max": 15, "details": details}


def score_systems(content: str) -> dict:
    """Score game systems depth (0-30)."""
    score = 0
    details = []
    checks = {
        "canvas": (r"canvas|getContext\(['\"]2d['\"]\)|WebGL", 4),
        "game-loop": (r"requestAnimationFrame", 4),
        "audio": (r"AudioContext|webkitAudioContext|createOscillator", 4),
        "saves": (r"localStorage\.(set|get)Item", 4),
        "procedural": (r"Math\.random|seed|noise|procedural", 2),
        "input": (r"addEventListener\(['\"]key|addEventListener\(['\"]mouse|addEventListener\(['\"]touch", 3),
        "collision": (r"collisi|intersect|overlap|hitTest|bounds", 2),
        "particles": (r"particle|emitter|spawn.*particle", 2),
        "state-machine": (r"gameState|state\s*===?\s*['\"]|switch\s*\(\s*state", 3),
        "classes": (r"\bclass\s+[A-Z]\w+", 2),
    }
    for name, (pattern, points) in checks.items():
        if re.search(pattern, content, re.IGNORECASE):
            score += points
            details.append(name)
    return {"score": min(score, 30), "max": 30, "details": details}


def score_completeness(content: str) -> dict:
    """Score game completeness (0-20)."""
    score = 0
    details = []
    checks = {
        "pause": (r"pause|paused|isPaused", 3),
        "game-over": (r"game.?over|gameOver|game_over|you (died|lose|lost|win|won)", 3),
        "scoring": (r"\bscore\b.*\+|score\s*[+=]|updateScore|addScore", 3),
        "progression": (r"level|wave|stage|round|floor|depth", 2),
        "title-screen": (r"title.?screen|main.?menu|start.?game|startGame|showMenu", 3),
        "hud": (r"drawHUD|renderHUD|updateHUD|hud|health.?bar|score.?display", 2),
        "endings": (r"ending|victory|defeat|you (saved|escaped|conquered)", 2),
        "tutorial": (r"tutorial|instructions|how to play|controls", 2),
    }
    for name, (pattern, points) in checks.items():
        if re.search(pattern, content, re.IGNORECASE):
            score += points
            details.append(name)
    return {"score": min(score, 20), "max": 20, "details": details}


def score_polish(content: str) -> dict:
    """Score visual/audio polish (0-15)."""
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
            score += points
            details.append(name)
    return {"score": min(score, 15), "max": 15, "details": details}


def compute_fingerprint(content: str) -> str:
    """Fast content fingerprint for change detection."""
    return hashlib.md5(content.encode()[:8192]).hexdigest()[:12]


def score_game(filepath: Path, content: str = None) -> dict:
    """Score a single game file across all dimensions."""
    if content is None:
        content = filepath.read_text(errors="replace")

    structural = score_structural(content)
    scale = score_scale(content)
    systems = score_systems(content)
    completeness = score_completeness(content)
    polish = score_polish(content)

    total = (
        structural["score"]
        + scale["score"]
        + systems["score"]
        + completeness["score"]
        + polish["score"]
    )
    max_total = 100

    # Extract title from content
    title_match = re.search(r"<title>(.*?)</title>", content)
    title = title_match.group(1).strip() if title_match else filepath.stem.replace("-", " ").title()

    lines = content.count("\n") + 1
    size_kb = len(content) / 1024

    return {
        "file": filepath.name,
        "title": title,
        "score": min(total, max_total),
        "grade": grade_from_score(min(total, max_total)),
        "lines": lines,
        "size_kb": round(size_kb, 1),
        "fingerprint": compute_fingerprint(content),
        "dimensions": {
            "structural": structural,
            "scale": scale,
            "systems": systems,
            "completeness": completeness,
            "polish": polish,
        },
    }


def grade_from_score(score: int) -> str:
    if score >= 90:
        return "S"
    elif score >= 80:
        return "A"
    elif score >= 65:
        return "B"
    elif score >= 50:
        return "C"
    elif score >= 35:
        return "D"
    else:
        return "F"


def load_manifest() -> dict:
    """Load manifest for category/metadata info."""
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text())
    return {"categories": {}}


def build_rankings(verbose: bool = False) -> dict:
    """Scan all apps and build complete rankings."""
    manifest = load_manifest()
    all_games = []
    category_stats = {}

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
                    continue  # Skip tiny/empty files

                result = score_game(f, content)
                result["category"] = cat_key
                result["category_folder"] = folder
                result["path"] = f"apps/{folder}/{f.name}"
                cat_games.append(result)

                if verbose:
                    dims = result["dimensions"]
                    print(
                        f"  [{result['grade']}] {result['score']:3d}/100  "
                        f"S:{dims['structural']['score']}/{dims['structural']['max']} "
                        f"Sc:{dims['scale']['score']}/{dims['scale']['max']} "
                        f"Sy:{dims['systems']['score']}/{dims['systems']['max']} "
                        f"C:{dims['completeness']['score']}/{dims['completeness']['max']} "
                        f"P:{dims['polish']['score']}/{dims['polish']['max']}  "
                        f"{result['title'][:40]}"
                    )
            except Exception as e:
                if verbose:
                    print(f"  [ERR] {f.name}: {e}")

        if cat_games:
            scores = [g["score"] for g in cat_games]
            category_stats[cat_key] = {
                "count": len(cat_games),
                "avg_score": round(sum(scores) / len(scores), 1),
                "top_score": max(scores),
                "folder": folder,
                "title": manifest.get("categories", {}).get(cat_key, {}).get("title", cat_key),
            }
            all_games.extend(cat_games)

        if verbose and cat_games:
            scores = [g["score"] for g in cat_games]
            print(f"\n  {cat_key}: {len(cat_games)} apps, avg {sum(scores)/len(scores):.1f}\n")

    # Sort by score descending
    all_games.sort(key=lambda g: g["score"], reverse=True)

    # Assign ranks
    for i, game in enumerate(all_games):
        game["rank"] = i + 1

    # Grade distribution
    grade_dist = {}
    for g in all_games:
        grade_dist[g["grade"]] = grade_dist.get(g["grade"], 0) + 1

    # Score histogram (buckets of 10)
    histogram = {}
    for g in all_games:
        bucket = (g["score"] // 10) * 10
        label = f"{bucket}-{bucket+9}"
        histogram[label] = histogram.get(label, 0) + 1

    scores = [g["score"] for g in all_games]
    rankings = {
        "generated": datetime.now().isoformat(),
        "total_apps": len(all_games),
        "summary": {
            "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
            "median_score": sorted(scores)[len(scores) // 2] if scores else 0,
            "top_10_avg": round(sum(scores[:10]) / min(10, len(scores)), 1) if scores else 0,
            "grade_distribution": grade_dist,
            "score_histogram": histogram,
        },
        "categories": category_stats,
        "rankings": all_games,
    }

    return rankings


def main():
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    push = "--push" in sys.argv

    if verbose:
        print("Scanning all app categories...\n")

    rankings = build_rankings(verbose=verbose)

    OUTPUT.write_text(json.dumps(rankings, indent=2))
    print(f"\nWrote {OUTPUT} ({rankings['total_apps']} apps ranked)")
    print(f"  Avg: {rankings['summary']['avg_score']} | "
          f"Median: {rankings['summary']['median_score']} | "
          f"Top 10 avg: {rankings['summary']['top_10_avg']}")
    print(f"  Grades: {rankings['summary']['grade_distribution']}")

    if push:
        import subprocess
        subprocess.run(["git", "add", str(OUTPUT)], cwd=ROOT)
        subprocess.run(
            ["git", "commit", "-m", f"Update rankings.json ({rankings['total_apps']} apps)"],
            cwd=ROOT,
        )
        subprocess.run(["git", "push"], cwd=ROOT)
        print("  Pushed to remote.")


if __name__ == "__main__":
    main()
