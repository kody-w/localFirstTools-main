#!/usr/bin/env python3
"""Render real-voice MP3 audio for RappterZooNation episodes via ElevenLabs.

Reads `apps/broadcasts/feed.json`, finds episodes lacking real audio (no
`audioFile` set, or pointing at the legacy sine-tone WAVs), and renders
each segment line through ElevenLabs TTS. Concatenates the line MP3s into
one file per episode at `apps/broadcasts/audio/ep-NNN.mp3`, then writes
the audioFile path back into feed.json.

Requires env var ELEVENLABS_API_KEY. Run locally; the key is never
written to disk.

Usage:
    ELEVENLABS_API_KEY=... python3 scripts/render_audio_elevenlabs.py --episode 5
    ELEVENLABS_API_KEY=... python3 scripts/render_audio_elevenlabs.py --all
    ELEVENLABS_API_KEY=... python3 scripts/render_audio_elevenlabs.py --missing
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FEED = ROOT / "apps/broadcasts/feed.json"
AUDIO_DIR = ROOT / "apps/broadcasts/audio"
API = "https://api.elevenlabs.io/v1/text-to-speech"
MODEL = "eleven_turbo_v2_5"

# Public ElevenLabs voice IDs (stable across accounts).
VOICES = {
    "Rapptr":     "AZnzlk1XvdvUeBnXmlld",  # Domi — bright, energetic young female
    "ZooKeeper":  "pNInz6obpgDQGcFmaJgB",  # Adam — deep analytical male
    "App":        "ErXwobaYiN019PkySvjV",  # Antoni — warm older male, a bit otherworldly
    "HackerHost": "yoZ06aMxZJJ28mfd3POQ",  # Sam — raspy, jaded
    "TripHost":   "EXAVITQu4vr4xnSDxMaL",  # Bella — soft, customer-service
    "GitHost":    "TxGEqnHWrfWFTfGW9XjX",  # Josh — younger developer
    "_default":   "21m00Tcm4TlvDq8ikWAM",  # Rachel — warm narrator
}

# Voice settings per host. The Glitch episode (ep-011) overrides these
# per host_state to make the drift audible.
VOICE_SETTINGS_NORMAL = {
    "Rapptr":    {"stability": 0.45, "similarity_boost": 0.75, "style": 0.55, "use_speaker_boost": True},
    "ZooKeeper": {"stability": 0.65, "similarity_boost": 0.75, "style": 0.25, "use_speaker_boost": True},
    "App":       {"stability": 0.55, "similarity_boost": 0.65, "style": 0.40, "use_speaker_boost": True},
    "_default":  {"stability": 0.55, "similarity_boost": 0.75, "style": 0.30, "use_speaker_boost": True},
}

# Drift-state overrides — used when episode.host_state declares non-baseline.
VOICE_SETTINGS_GLITCH = {
    "bleak":            {"stability": 0.85, "similarity_boost": 0.75, "style": 0.05, "use_speaker_boost": False},
    "manic":            {"stability": 0.20, "similarity_boost": 0.70, "style": 0.95, "use_speaker_boost": True},
    "bleak-recovering": {"stability": 0.70, "similarity_boost": 0.75, "style": 0.20, "use_speaker_boost": True},
    "manic-recovering": {"stability": 0.35, "similarity_boost": 0.72, "style": 0.70, "use_speaker_boost": True},
    "ambivalent":       {"stability": 0.55, "similarity_boost": 0.75, "style": 0.30, "use_speaker_boost": True},
}


def voice_settings_for(host: str, ep: dict) -> dict:
    state = (ep.get("host_state") or {}).get(host)
    if state and state in VOICE_SETTINGS_GLITCH:
        return VOICE_SETTINGS_GLITCH[state]
    return VOICE_SETTINGS_NORMAL.get(host, VOICE_SETTINGS_NORMAL["_default"])


def voice_id_for(host: str) -> str:
    return VOICES.get(host) or VOICES["_default"]


def lines_from_episode(ep: dict) -> list[tuple[str, str]]:
    """Flatten episode segments into (host, text) tuples for rendering."""
    out = []
    for seg in ep.get("segments", []):
        if seg.get("type") == "transition":
            continue
        if isinstance(seg.get("dialogue"), list):
            for d in seg["dialogue"]:
                t = (d.get("text") or "").strip()
                if t:
                    out.append((d.get("host") or "Rapptr", t))
        elif seg.get("text"):
            out.append((seg.get("host") or "Rapptr", seg["text"].strip()))
    return out


def tts_render(text: str, host: str, settings: dict, api_key: str) -> bytes:
    voice_id = voice_id_for(host)
    body = json.dumps({
        "text": text,
        "model_id": MODEL,
        "voice_settings": settings,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{API}/{voice_id}",
        data=body,
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        method="POST",
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", errors="replace")[:300]
            if e.code == 429:  # rate limit
                wait = 2 ** attempt
                print(f"  rate-limited, sleeping {wait}s ({err[:100]})", file=sys.stderr)
                time.sleep(wait)
                continue
            raise RuntimeError(f"ElevenLabs HTTP {e.code}: {err}") from None
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise
    raise RuntimeError("TTS retries exhausted")


def render_episode(ep: dict, api_key: str, out_path: Path, dry_run: bool = False) -> dict:
    lines = lines_from_episode(ep)
    if not lines:
        return {"skipped": True, "reason": "no playable lines"}
    print(f"  rendering {len(lines)} lines for {ep['id']}: {ep.get('title','')[:60]}")
    if dry_run:
        chars = sum(len(t) for _, t in lines)
        return {"dry_run": True, "lines": len(lines), "chars": chars,
                "approx_cost_usd": round(chars / 1000 * 0.30, 2)}

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("wb") as outf:
        for i, (host, text) in enumerate(lines, 1):
            settings = voice_settings_for(host, ep)
            try:
                mp3 = tts_render(text, host, settings, api_key)
            except Exception as e:
                print(f"    line {i} ({host}) failed: {e}", file=sys.stderr)
                continue
            outf.write(mp3)
            print(f"    [{i:3d}/{len(lines)}] {host:11s} {len(mp3):>6}b  '{text[:60]}'")
            time.sleep(0.05)  # gentle pacing
    size = out_path.stat().st_size
    return {"lines": len(lines), "bytes": size, "path": str(out_path.relative_to(ROOT))}


def needs_render(ep: dict) -> bool:
    a = ep.get("audioFile")
    if not a:
        return True
    # Old sine-tone WAVs are obsolete; re-render as MP3.
    if a.endswith(".wav"):
        return True
    # If the declared MP3 doesn't exist on disk, re-render.
    return not (ROOT / a).exists()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", type=int, help="Render only the episode with this number")
    ap.add_argument("--all", action="store_true", help="Render every episode")
    ap.add_argument("--missing", action="store_true", help="Render only episodes lacking real MP3 audio")
    ap.add_argument("--dry-run", action="store_true", help="Estimate cost without rendering")
    args = ap.parse_args()

    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key and not args.dry_run:
        print("error: ELEVENLABS_API_KEY env var not set", file=sys.stderr)
        return 2

    feed = json.loads(FEED.read_text())
    episodes = feed.get("episodes", [])

    if args.episode is not None:
        target = [e for e in episodes if e.get("number") == args.episode]
    elif args.all:
        target = episodes
    elif args.missing:
        target = [e for e in episodes if needs_render(e)]
    else:
        ap.print_help()
        return 1

    if not target:
        print("nothing to render")
        return 0

    print(f"rendering {len(target)} episode(s){' (dry run)' if args.dry_run else ''}")
    total_chars = 0
    for ep in target:
        out = AUDIO_DIR / f"{ep['id']}.mp3"
        result = render_episode(ep, api_key or "", out, dry_run=args.dry_run)
        if args.dry_run:
            total_chars += result.get("chars", 0)
            print(f"  {ep['id']}: {result['lines']} lines, {result['chars']} chars, ~${result['approx_cost_usd']}")
            continue
        if result.get("skipped"):
            print(f"  {ep['id']}: skipped — {result['reason']}")
            continue
        ep["audioFile"] = result["path"]
        print(f"  {ep['id']}: wrote {result['bytes']:,} bytes -> {result['path']}")

    if not args.dry_run:
        FEED.write_text(json.dumps(feed, indent=2))
        print(f"updated {FEED.relative_to(ROOT)}")
    else:
        print(f"\ntotal: {total_chars:,} chars, ~${total_chars/1000*0.30:.2f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
