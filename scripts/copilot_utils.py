"""
copilot_utils.py -- Shared utilities for Copilot CLI intelligence pipelines.

Consolidates common functions used by autosort.py, app.py, and molt.py:
- Backend detection (gh copilot availability)
- Copilot CLI invocation
- Response parsing (JSON, HTML, stripping wrappers)
- Manifest I/O
"""

import json
import re
import shutil
import subprocess
import time
from pathlib import Path

MODEL = "claude-opus-4.6"

ROOT = Path(__file__).resolve().parent.parent
APPS_DIR = ROOT / "apps"
MANIFEST_PATH = APPS_DIR / "manifest.json"

VALID_CATEGORIES = {
    "3d_immersive": "3d-immersive",
    "audio_music": "audio-music",
    "games_puzzles": "games-puzzles",
    "visual_art": "visual-art",
    "generative_art": "generative-art",
    "particle_physics": "particle-physics",
    "creative_tools": "creative-tools",
    "educational_tools": "educational",
    "experimental_ai": "experimental-ai",
}


def detect_backend():
    """Determine which intelligence backend is available."""
    if shutil.which("gh"):
        try:
            result = subprocess.run(
                ["gh", "copilot", "--", "--help"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                return "copilot-cli"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
    return "unavailable"


def copilot_call(prompt, timeout=120):
    """Send a prompt to Copilot CLI with Claude Opus and return the raw response.
    
    For large prompts (>100KB), writes to a temp file to avoid OS ARG_MAX limits.
    """
    import tempfile
    # For prompts under 100KB, pass as -p argument (fast path)
    if len(prompt) < 100_000:
        cmd = [
            "gh", "copilot",
            "--model", MODEL,
            "-p", prompt,
            "--no-ask-user",
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout,
            )
            if result.returncode != 0:
                return None
            return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None
    else:
        # Large prompts: write to temp file and reference it in prompt
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, prefix="molt_prompt_"
        ) as f:
            f.write(prompt)
            tmp_path = f.name
        try:
            meta_prompt = (
                f"Read the file at {tmp_path} and follow the instructions inside it exactly. "
                f"Return ONLY the improved HTML as instructed in that file."
            )
            cmd = [
                "gh", "copilot",
                "--model", MODEL,
                "-p", meta_prompt,
                "--allow-all",
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout,
            )
            if result.returncode != 0:
                return None
            return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None
        finally:
            try:
                Path(tmp_path).unlink()
            except OSError:
                pass


def adaptive_timeout(prompt):
    """Return timeout in seconds scaled to prompt size.

    Base 120s + 1s per KB of prompt, minimum 120s.
    """
    kb = len(prompt) / 1024
    return int(max(120, 120 + kb))


def copilot_call_with_retry(prompt, timeout=None, max_retries=3):
    """Call Copilot CLI with retry and exponential backoff.

    - Retries up to max_retries times on None or empty responses
    - Uses adaptive timeout based on prompt size unless explicit timeout given
    - Exponential backoff: 2s, 4s, 8s between retries
    """
    effective_timeout = timeout if timeout is not None else adaptive_timeout(prompt)
    for attempt in range(max_retries):
        result = copilot_call(prompt, timeout=effective_timeout)
        if result and result.strip():
            return result
        if attempt < max_retries - 1:
            delay = 2 ** (attempt + 1)  # 2, 4, 8...
            time.sleep(delay)
    return None


def strip_copilot_wrapper(text):
    """Strip Copilot CLI wrapper: ANSI codes, usage stats, task summary."""
    text = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text)
    text = re.sub(r"\x1b[^a-zA-Z]*[a-zA-Z]", "", text)
    for marker in ["Task complete", "Total usage est:", "Total session time:"]:
        idx = text.find(marker)
        if idx > 0:
            text = text[:idx]
    return text.strip()


def parse_llm_json(raw_output):
    """Extract JSON from LLM output, handling Copilot CLI formatting."""
    if not raw_output:
        return None

    text = strip_copilot_wrapper(raw_output)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fenced = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1).strip())
        except json.JSONDecodeError:
            pass

    brace_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group())
        except json.JSONDecodeError:
            pass

    return None


def parse_llm_html(raw_output):
    """Extract HTML from LLM output, stripping wrapper and code fences."""
    if not raw_output:
        return None
    text = strip_copilot_wrapper(raw_output)
    # Remove markdown code fences if present
    fenced = re.search(r"```(?:html)?\s*\n(.*?)\n```", text, re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    # If it looks like HTML already (starts with < or DOCTYPE), return as-is
    stripped = text.strip()
    if stripped.lower().startswith("<!doctype") or stripped.startswith("<"):
        return stripped
    return text


def load_manifest():
    """Load the manifest or create a fresh one."""
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH) as f:
            return json.load(f)
    return {"categories": {}, "meta": {"version": "1.0", "lastUpdated": ""}}


def save_manifest(manifest):
    """Write manifest atomically."""
    from datetime import date

    manifest["meta"]["lastUpdated"] = date.today().isoformat()
    tmp = MANIFEST_PATH.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(manifest, f, indent=2)
    tmp.replace(MANIFEST_PATH)
