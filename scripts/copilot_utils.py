"""
copilot_utils.py -- Shared utilities for Copilot CLI intelligence pipelines.

Consolidates common functions used by autosort.py, app.py, and molt.py:
- Backend detection (gh copilot availability)
- Copilot CLI invocation
- Response parsing (JSON, HTML, stripping wrappers)
- Manifest I/O
"""

import json
import logging
import math
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path

MODEL = "claude-opus-4.6"
MAX_PROMPT_BYTES = 8 * 1024 * 1024
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_ERROR_BYTES = 64 * 1024
POSIX = os.name == "posix"
LOGGER = logging.getLogger(__name__)

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


def _stop_inference(process):
    if POSIX:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    elif process.poll() is None:
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=5, check=True,
        )
    process.wait(timeout=5)


def _run_inference(command, *, cwd, env, timeout, scratch):
    """Capture privately on disk; never retain oversized output in memory."""
    with tempfile.TemporaryFile(dir=scratch) as output, tempfile.TemporaryFile(dir=scratch) as errors:
        process = subprocess.Popen(
            command,
            cwd=str(cwd),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=errors,
            start_new_session=POSIX,
        )
        deadline = time.monotonic() + timeout
        try:
            while True:
                if os.fstat(output.fileno()).st_size > MAX_RESPONSE_BYTES:
                    LOGGER.warning("Copilot response exceeded the byte limit.")
                    return None
                if os.fstat(errors.fileno()).st_size > MAX_ERROR_BYTES:
                    LOGGER.warning("Copilot diagnostics exceeded the byte limit.")
                    return None
                result = process.poll()
                if result is not None:
                    if result != 0:
                        LOGGER.warning("Copilot inference failed with exit code %s; output is not logged.", result)
                        return None
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    LOGGER.warning("Copilot inference exceeded its timeout.")
                    return None
                try:
                    process.wait(timeout=min(0.1, remaining))
                except subprocess.TimeoutExpired:
                    continue
            if os.fstat(errors.fileno()).st_size > MAX_ERROR_BYTES:
                LOGGER.warning("Copilot diagnostics exceeded the byte limit.")
                return None
            output.seek(0)
            data = output.read(MAX_RESPONSE_BYTES + 1)
            if len(data) > MAX_RESPONSE_BYTES:
                LOGGER.warning("Copilot response exceeded the byte limit.")
                return None
            try:
                response = data.decode("utf-8").strip()
            except UnicodeDecodeError:
                LOGGER.warning("Copilot returned invalid UTF-8.")
                return None
            if not response:
                LOGGER.warning("Copilot returned an empty response.")
                return None
            return response
        finally:
            _stop_inference(process)


def copilot_call(prompt, timeout=120):
    """Return model text with only a reader for the private input repository.

    Callers must include required context. Command, write, network and MCP tools
    are unavailable; prompt length never grants more authority. CLI path/tool
    restrictions are not an operating-system sandbox.
    """
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("Copilot requires a nonempty text prompt")
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Copilot requires a finite positive timeout")
    data = prompt.encode("utf-8")
    if len(data) > MAX_PROMPT_BYTES:
        LOGGER.warning("Copilot prompt exceeded the byte limit.")
        return None
    try:
        with tempfile.TemporaryDirectory(prefix="molter-inference-") as temporary:
            scratch = Path(temporary)
            work = scratch / "input"
            work.mkdir()
            env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
            env.pop("COPILOT_CUSTOM_INSTRUCTIONS_DIRS", None)
            env.pop("COPILOT_ASSISTED_APPROVAL", None)
            env["COPILOT_ALLOW_ALL"] = "false"
            env["COPILOT_AUTO_UPDATE"] = "false"
            env["COPILOT_HOME"] = str(scratch / "home")
            env["GIT_CONFIG_GLOBAL"] = os.devnull
            env["GIT_CONFIG_NOSYSTEM"] = "1"
            # A caller's TMPDIR may itself be inside a repository with hooks.
            initialized = subprocess.run(
                ["git", "init", "--quiet", "--template=", str(work)],
                env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=15, check=False,
            )
            if initialized.returncode != 0:
                LOGGER.warning("Copilot could not isolate its inference repository.")
                return None
            (work / "prompt.txt").write_bytes(data)
            command = [
                "gh", "copilot", "--", "-C", str(work),
                "--model", MODEL,
                "--available-tools=view", "--add-dir", str(work),
                "--deny-tool=shell", "--deny-tool=write", "--deny-tool=url",
                "--disable-builtin-mcps", "--disallow-temp-dir",
                "--no-custom-instructions", "--no-bash-env",
                "--no-remote-export", "--no-auto-update",
                "--no-ask-user", "--no-color", "--log-level", "none", "--silent",
                "-p", (
                    "Read only the supplied prompt file at " + str(work / "prompt.txt") + ". "
                    "Follow its instructions and return only the requested response. "
                    "Do not read other files."
                ),
            ]
            return _run_inference(
                command, cwd=work, env=env, timeout=timeout, scratch=scratch,
            )
    except (OSError, subprocess.TimeoutExpired):
        LOGGER.warning("Copilot could not start or use its private inference workspace.")
        return None


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
