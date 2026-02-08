"""
content_identity.py -- Adaptive Content Identity Engine.

THE MEDIUM IS THE MESSAGE. This module looks at any HTML file and discovers
what it IS, what it does well, what it does poorly, and how it could be
better at being itself. No fixed rubrics. No game-specific scoring.
The LLM figures out quality from the content.

LLM-only: if Copilot CLI is unavailable, returns None.
No data is better than bad data.
"""

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Optional

from copilot_utils import (
    APPS_DIR,
    ROOT,
    copilot_call,
    detect_backend,
    parse_llm_json,
    strip_copilot_wrapper,
)

IDENTITY_CACHE = APPS_DIR / "content-identities.json"


def _file_hash(content: str) -> str:
    """SHA-256 fingerprint for cache invalidation."""
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def _load_cache() -> dict:
    """Load cached identities or return empty dict."""
    if IDENTITY_CACHE.exists():
        try:
            return json.loads(IDENTITY_CACHE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_cache(cache: dict):
    """Write cache atomically."""
    tmp = IDENTITY_CACHE.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(cache, f, indent=2)
    tmp.replace(IDENTITY_CACHE)


ANALYZE_PROMPT = """\
You are a content analyst. Given an HTML file, produce a JSON identity document.
Do NOT assume this is a game. It could be anything: a music tool, drawing app,
data visualizer, educational tool, art generator, physics sim, calculator,
or something entirely new that doesn't have a name yet.

Look at what the code ACTUALLY DOES, not what you think it should be.

Return ONLY valid JSON with exactly these fields:

{{
  "medium": "<what this thing IS in 2-5 words, e.g. 'ambient music synthesizer', 'fractal explorer', 'platformer game', 'markdown editor'>",
  "purpose": "<what it DOES for the user in one sentence>",
  "techniques": ["<list of technical approaches used, e.g. 'Web Audio API', 'Canvas 2D', 'CSS Grid layout', 'requestAnimationFrame loop'>"],
  "strengths": ["<what this does WELL for what it is, 3-5 items>"],
  "weaknesses": ["<what would make this better AT BEING WHAT IT IS, 3-5 items>"],
  "improvement_vectors": [
    "<most impactful improvement, specific and actionable>",
    "<second most impactful>",
    "<third most impactful>"
  ],
  "craft_score": <0-20 integer: how sophisticated are the techniques for what this IS>,
  "completeness_score": <0-15 integer: does this feel finished or like a demo>,
  "engagement_score": <0-25 integer: would someone spend 10+ minutes with this>
}}

SCORING GUIDANCE (adapt to what the content IS):
- craft_score: A synth with 1 oscillator = low. A synth with FM synthesis, filters, LFOs = high.
  A game with basic movement = low. A game with physics, particles, audio = high.
  Judge sophistication relative to the medium, not against games specifically.
- completeness_score: Does it have everything you'd expect? A drawing tool without undo = incomplete.
  A game without game-over = incomplete. A visualizer without controls = incomplete.
  Judge completeness relative to what this thing is trying to be.
- engagement_score: Would someone actually USE this? Is it compelling? Does it reward exploration?
  A toy that's fun for 30 seconds = low. Something you'd bookmark = high.

Filename: {filename}
Content:
---
{content}
---

Return ONLY the JSON object. No explanation."""


def analyze(filepath, content=None, use_cache=True) -> Optional[dict]:
    """Analyze an HTML file and return its Content Identity.

    Returns None if LLM is unavailable. No data is better than bad data.

    Args:
        filepath: Path to the HTML file
        content: Optional pre-read content (avoids re-reading)
        use_cache: If True, check/update the identity cache

    Returns:
        Content Identity dict or None if LLM unavailable
    """
    filepath = Path(filepath)

    if content is None:
        if not filepath.exists():
            return None
        content = filepath.read_text(encoding="utf-8", errors="replace")

    fingerprint = _file_hash(content)

    # Check cache
    if use_cache:
        cache = _load_cache()
        key = str(filepath.relative_to(ROOT)) if str(filepath).startswith(str(ROOT)) else str(filepath)
        cached = cache.get(key)
        if cached and cached.get("fingerprint") == fingerprint:
            return cached

    # LLM-only: if unavailable, return None
    backend = detect_backend()
    if backend == "unavailable":
        return None

    prompt = ANALYZE_PROMPT.format(
        filename=filepath.name,
        content=content[:80000],  # Cap at 80K chars to stay under prompt limits
    )

    raw = copilot_call(prompt, timeout=90)
    identity = parse_llm_json(raw)

    if not identity:
        return None

    # Validate required fields
    required = ["medium", "purpose", "techniques", "strengths", "weaknesses",
                "improvement_vectors", "craft_score", "completeness_score", "engagement_score"]
    if not all(k in identity for k in required):
        return None

    # Clamp scores
    identity["craft_score"] = max(0, min(20, int(identity.get("craft_score", 0))))
    identity["completeness_score"] = max(0, min(15, int(identity.get("completeness_score", 0))))
    identity["engagement_score"] = max(0, min(25, int(identity.get("engagement_score", 0))))

    # Add metadata
    identity["fingerprint"] = fingerprint
    identity["analyzed"] = date.today().isoformat()
    identity["file"] = filepath.name

    # Update cache
    if use_cache:
        cache = _load_cache()
        key = str(filepath.relative_to(ROOT)) if str(filepath).startswith(str(ROOT)) else str(filepath)
        cache[key] = identity
        _save_cache(cache)

    return identity


def analyze_bulk(filepaths, use_cache=True, verbose=False) -> dict:
    """Analyze multiple files, returning a dict of filepath -> identity.

    Skips files where LLM is unavailable (returns partial results).
    """
    results = {}
    backend = detect_backend()
    if backend == "unavailable":
        if verbose:
            print("⚠ Copilot CLI unavailable — cannot analyze. No data is better than bad data.")
        return results

    for i, fp in enumerate(filepaths):
        fp = Path(fp)
        if verbose:
            print(f"  [{i+1}/{len(filepaths)}] Analyzing {fp.name}...")
        identity = analyze(fp, use_cache=use_cache)
        if identity:
            results[str(fp)] = identity
        elif verbose:
            print(f"    ⚠ Failed to analyze {fp.name}")

    return results


def get_improvement_vector(filepath, content=None) -> Optional[str]:
    """Get the single most impactful improvement for a file.

    Convenience method for the molt pipeline.
    Returns None if LLM unavailable.
    """
    identity = analyze(filepath, content=content)
    if not identity:
        return None
    vectors = identity.get("improvement_vectors", [])
    return vectors[0] if vectors else None


def get_adaptive_scores(filepath, content=None) -> Optional[dict]:
    """Get the three adaptive dimension scores for a file.

    Returns dict with craft_score, completeness_score, engagement_score
    or None if LLM unavailable.
    """
    identity = analyze(filepath, content=content)
    if not identity:
        return None
    return {
        "craft_score": identity["craft_score"],
        "completeness_score": identity["completeness_score"],
        "engagement_score": identity["engagement_score"],
        "medium": identity["medium"],
    }


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    import sys

    args = sys.argv[1:]
    verbose = "--verbose" in args
    json_output = "--json" in args
    args = [a for a in args if not a.startswith("--")]

    if not args:
        print("Usage: python3 content_identity.py <file_or_dir> [--verbose] [--json]")
        print("  Analyzes HTML files and outputs their Content Identity.")
        print("  LLM-only: requires gh copilot CLI.")
        sys.exit(1)

    target = Path(args[0])

    if target.is_file():
        identity = analyze(target)
        if identity:
            if json_output:
                print(json.dumps(identity, indent=2))
            else:
                print(f"📄 {identity['file']}")
                print(f"   Medium: {identity['medium']}")
                print(f"   Purpose: {identity['purpose']}")
                print(f"   Techniques: {', '.join(identity['techniques'])}")
                print(f"   Strengths: {', '.join(identity['strengths'])}")
                print(f"   Weaknesses: {', '.join(identity['weaknesses'])}")
                print(f"   Improvement vectors:")
                for v in identity['improvement_vectors']:
                    print(f"     → {v}")
                print(f"   Scores: craft={identity['craft_score']}/20  "
                      f"completeness={identity['completeness_score']}/15  "
                      f"engagement={identity['engagement_score']}/25")
        else:
            print("⚠ Could not analyze (LLM unavailable or parse failed)")
            sys.exit(1)

    elif target.is_dir():
        files = sorted(target.glob("*.html"))
        if not files:
            print(f"No HTML files in {target}")
            sys.exit(1)
        results = analyze_bulk(files, verbose=verbose)
        if json_output:
            print(json.dumps(results, indent=2))
        else:
            for fp, identity in results.items():
                print(f"📄 {identity['file']:40s}  {identity['medium']:30s}  "
                      f"craft={identity['craft_score']:2d}  "
                      f"complete={identity['completeness_score']:2d}  "
                      f"engage={identity['engagement_score']:2d}")
            print(f"\nAnalyzed {len(results)}/{len(files)} files")
    else:
        print(f"Not found: {target}")
        sys.exit(1)


if __name__ == "__main__":
    main()
