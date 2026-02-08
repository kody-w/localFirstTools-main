#!/usr/bin/env python3
"""Generate WAV audio files for RappterZooNation podcast episodes.

Creates ambient audio tracks with distinct tones per host and transition jingles.
The podcast player syncs the transcript to audio cues.

Usage:
    python3 scripts/generate_broadcast_audio.py                    # Generate for latest episode
    python3 scripts/generate_broadcast_audio.py --episode N        # Generate for episode N
    python3 scripts/generate_broadcast_audio.py --all              # Generate for all episodes
    python3 scripts/generate_broadcast_audio.py --verbose          # Show details

Output: apps/broadcasts/audio/ep-NNN.wav
"""

import array
import json
import math
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APPS_DIR = ROOT / "apps"
FEED_FILE = APPS_DIR / "broadcasts" / "feed.json"
AUDIO_DIR = APPS_DIR / "broadcasts" / "audio"

VERBOSE = "--verbose" in sys.argv or "-v" in sys.argv

SAMPLE_RATE = 8000  # Low rate — this is ambient, not speech
CHANNELS = 1
BITS_PER_SAMPLE = 16

# Host voice characteristics
HOST_TONES = {
    "Rapptr": {"base_freq": 440, "color": "bright", "speed": 1.2},
    "ZooKeeper": {"base_freq": 220, "color": "warm", "speed": 0.9},
}

JINGLE_FREQS = [261.63, 329.63, 392.00, 523.25]  # C4 E4 G4 C5
TRANSITION_FREQ = 880


def log(msg):
    if VERBOSE:
        print(f"  [audio] {msg}")


def generate_sine(freq, duration, amplitude=0.3):
    """Generate sine wave samples using array for speed."""
    n = int(SAMPLE_RATE * duration)
    twopi_f_over_sr = 2.0 * math.pi * freq / SAMPLE_RATE
    fade = min(int(SAMPLE_RATE * 0.02), n // 4)
    out = array.array('f', [0.0] * n)
    for i in range(n):
        env = 1.0
        if i < fade:
            env = i / fade
        elif i > n - fade:
            env = (n - i) / fade
        out[i] = amplitude * env * math.sin(twopi_f_over_sr * i)
    return out


def generate_speech_tone(text, host):
    """Generate tonal representation of speech — fast version."""
    tone = HOST_TONES.get(host, HOST_TONES["Rapptr"])
    base_freq = tone["base_freq"]
    speed = tone["speed"]
    words = len(text.split())
    duration = max(0.3, words / (150 / 60) / speed)

    # Cap duration to keep file size reasonable
    duration = min(duration, 8.0)

    n = int(SAMPLE_RATE * duration)
    syllable_rate = max(1, words * 1.5 * speed)
    syllable_period = max(1, n / syllable_rate)
    twopi_over_sr = 2.0 * math.pi / SAMPLE_RATE
    fade = min(int(SAMPLE_RATE * 0.03), n // 4)

    out = array.array('f', [0.0] * n)
    is_warm = tone["color"] == "warm"

    for i in range(n):
        sp = (i % int(syllable_period)) / syllable_period
        freq = base_freq * (1 + 0.04 * math.sin(sp * 6.28 * 3))
        senv = 0.5 + 0.5 * math.sin(6.28 * i / syllable_period)
        env = 1.0
        if i < fade:
            env = i / fade
        elif i > n - fade:
            env = (n - i) / fade
        amp = 0.12 * env * senv
        s = amp * math.sin(twopi_over_sr * freq * i)
        if is_warm:
            s += 0.04 * env * senv * math.sin(twopi_over_sr * freq * 0.5 * i)
        else:
            s += 0.02 * env * senv * math.sin(twopi_over_sr * freq * 2 * i)
        out[i] = s

    return out, duration


def generate_jingle(duration=1.5):
    """Generate the show jingle (arpeggiated chord)."""
    n = int(SAMPLE_RATE * duration)
    out = array.array('f', [0.0] * n)
    note_dur = duration / len(JINGLE_FREQS)

    for j, freq in enumerate(JINGLE_FREQS):
        start = int(j * note_dur * SAMPLE_RATE)
        note = generate_sine(freq, note_dur, amplitude=0.2)
        for i in range(len(note)):
            idx = start + i
            if idx < n:
                out[idx] += note[i]
    return out


def generate_transition():
    """Short transition beep."""
    return generate_sine(TRANSITION_FREQ, 0.1, amplitude=0.12)


def silence(duration):
    """Generate silence."""
    return array.array('f', [0.0] * int(SAMPLE_RATE * duration))


def concat(*arrs):
    """Concatenate arrays."""
    result = array.array('f')
    for a in arrs:
        result.extend(a)
    return result


def samples_to_wav(samples, filepath):
    """Write samples to a WAV file."""
    # Find max for normalization
    max_val = max((abs(s) for s in samples), default=1.0)
    if max_val < 0.001:
        max_val = 1.0
    scale = 32767.0 / max_val if max_val > 1.0 else 32767.0

    # Pack all PCM data at once
    pcm = struct.pack(f"<{len(samples)}h", *(
        max(-32768, min(32767, int(s * scale))) for s in samples
    ))

    data_size = len(pcm)
    file_size = 36 + data_size
    byte_rate = SAMPLE_RATE * CHANNELS * BITS_PER_SAMPLE // 8
    block_align = CHANNELS * BITS_PER_SAMPLE // 8

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", file_size, b"WAVE",
        b"fmt ", 16, 1, CHANNELS,
        SAMPLE_RATE, byte_rate, block_align, BITS_PER_SAMPLE,
        b"data", data_size,
    )

    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "wb") as f:
        f.write(header)
        f.write(pcm)

    size_kb = (44 + data_size) / 1024
    dur_sec = len(samples) / SAMPLE_RATE
    log(f"Wrote {filepath} ({size_kb:.1f} KB, {dur_sec:.1f}s)")


def generate_episode_audio(episode):
    """Generate audio for a single episode."""
    ep_id = episode["id"]
    segments = episode.get("segments", [])
    filepath = AUDIO_DIR / f"{ep_id}.wav"

    parts = [generate_jingle(), silence(0.3)]

    for seg in segments:
        seg_type = seg.get("type", "")

        if seg_type == "transition":
            parts.extend([silence(0.2), generate_transition(), silence(0.2)])
            continue

        if seg_type in ("intro", "outro"):
            text = seg.get("text", "")
            if text:
                tone, _ = generate_speech_tone(text, seg.get("host", "Rapptr"))
                parts.extend([tone, silence(0.2)])

        if seg_type in ("review", "roast"):
            parts.extend([generate_transition(), silence(0.2)])
            for line in seg.get("dialogue", []):
                text = line.get("text", "")
                if text:
                    tone, _ = generate_speech_tone(text, line.get("host", "Rapptr"))
                    parts.extend([tone, silence(0.15)])

    parts.extend([silence(0.3), generate_jingle(duration=2.0)])

    all_samples = concat(*parts)
    samples_to_wav(all_samples, filepath)
    duration_sec = len(all_samples) / SAMPLE_RATE
    print(f"Generated audio: {filepath.name} ({duration_sec:.1f}s, {len(all_samples)*2/1024:.0f} KB)")
    return filepath


def main():
    args = sys.argv[1:]

    if not FEED_FILE.exists():
        print("ERROR: feed.json not found. Run generate_broadcast.py first.")
        sys.exit(1)

    with open(FEED_FILE) as f:
        feed = json.load(f)

    episodes = feed.get("episodes", [])
    if not episodes:
        print("ERROR: No episodes in feed.json")
        sys.exit(1)

    target_ep = None
    generate_all = "--all" in args

    for i, arg in enumerate(args):
        if arg == "--episode" and i + 1 < len(args):
            val = args[i + 1]
            if val == "latest":
                target_ep = episodes[-1]["number"]
            else:
                target_ep = int(val)

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    if generate_all:
        for ep in episodes:
            generate_episode_audio(ep)
    elif target_ep is not None:
        ep = next((e for e in episodes if e["number"] == target_ep), None)
        if ep:
            generate_episode_audio(ep)
        else:
            print(f"ERROR: Episode {target_ep} not found")
            sys.exit(1)
    else:
        generate_episode_audio(episodes[-1])


if __name__ == "__main__":
    main()
