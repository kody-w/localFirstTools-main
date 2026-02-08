"""
Tests for the content identity engine (scripts/content_identity.py).

All LLM calls are mocked -- no network needed.
"""

import json
import tempfile
from pathlib import Path
from unittest import mock

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from content_identity import (
    _file_hash,
    _load_cache,
    _save_cache,
    analyze,
    analyze_bulk,
    get_adaptive_scores,
    get_improvement_vector,
    ANALYZE_PROMPT,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

SAMPLE_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FM Synthesizer</title>
<style>
  body { margin: 0; background: #111; color: #eee; font-family: monospace; }
  .knob { width: 60px; height: 60px; border-radius: 50%; background: #333; }
</style>
</head>
<body>
<h1>FM Synthesizer</h1>
<div id="controls"></div>
<canvas id="waveform" width="400" height="200"></canvas>
<script>
  const ctx = new AudioContext();
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  const analyser = ctx.createAnalyser();
  osc.connect(gain);
  gain.connect(analyser);
  analyser.connect(ctx.destination);
  osc.type = 'sine';
  osc.frequency.value = 440;
  osc.start();

  const canvas = document.getElementById('waveform');
  const canvasCtx = canvas.getContext('2d');
  function drawWaveform() {
    requestAnimationFrame(drawWaveform);
    const data = new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteTimeDomainData(data);
    canvasCtx.clearRect(0, 0, canvas.width, canvas.height);
    canvasCtx.beginPath();
    for (let i = 0; i < data.length; i++) {
      const x = (i / data.length) * canvas.width;
      const y = (data[i] / 128.0) * (canvas.height / 2);
      i === 0 ? canvasCtx.moveTo(x, y) : canvasCtx.lineTo(x, y);
    }
    canvasCtx.stroke();
  }
  drawWaveform();
</script>
</body>
</html>"""

MOCK_IDENTITY = {
    "medium": "FM synthesizer",
    "purpose": "Create and visualize FM synthesis tones with real-time waveform display",
    "techniques": ["Web Audio API", "Canvas 2D", "requestAnimationFrame", "FM synthesis"],
    "strengths": ["Real-time waveform visualization", "Clean audio signal chain", "Responsive canvas rendering"],
    "weaknesses": ["No frequency control UI", "Single oscillator only", "No preset save/load"],
    "improvement_vectors": [
        "Add knob controls for frequency, gain, and FM modulation depth",
        "Implement preset save/load via localStorage",
        "Add multiple oscillator support for richer sound"
    ],
    "craft_score": 12,
    "completeness_score": 6,
    "engagement_score": 8,
}


# ─── Tests ───────────────────────────────────────────────────────────────────


def test_file_hash_deterministic():
    h1 = _file_hash("hello world")
    h2 = _file_hash("hello world")
    assert h1 == h2
    assert len(h1) == 16


def test_file_hash_different_content():
    h1 = _file_hash("hello")
    h2 = _file_hash("world")
    assert h1 != h2


def test_cache_roundtrip(tmp_path):
    """Cache save/load cycle."""
    import content_identity
    old_cache = content_identity.IDENTITY_CACHE
    content_identity.IDENTITY_CACHE = tmp_path / "test-cache.json"
    try:
        data = {"apps/test.html": {"medium": "test", "fingerprint": "abc123"}}
        _save_cache(data)
        loaded = _load_cache()
        assert loaded == data
    finally:
        content_identity.IDENTITY_CACHE = old_cache


def test_load_cache_missing(tmp_path):
    """Missing cache file returns empty dict."""
    import content_identity
    old_cache = content_identity.IDENTITY_CACHE
    content_identity.IDENTITY_CACHE = tmp_path / "nonexistent.json"
    try:
        assert _load_cache() == {}
    finally:
        content_identity.IDENTITY_CACHE = old_cache


@mock.patch("content_identity.detect_backend", return_value="copilot-cli")
@mock.patch("content_identity.copilot_call")
def test_analyze_returns_identity(mock_call, mock_backend, tmp_path):
    """analyze() returns a valid Content Identity when LLM responds."""
    mock_call.return_value = json.dumps(MOCK_IDENTITY)

    html_file = tmp_path / "synth.html"
    html_file.write_text(SAMPLE_HTML)

    result = analyze(html_file, use_cache=False)

    assert result is not None
    assert result["medium"] == "FM synthesizer"
    assert result["craft_score"] == 12
    assert result["completeness_score"] == 6
    assert result["engagement_score"] == 8
    assert "fingerprint" in result
    assert "analyzed" in result
    assert len(result["improvement_vectors"]) == 3
    mock_call.assert_called_once()


@mock.patch("content_identity.detect_backend", return_value="unavailable")
def test_analyze_returns_none_when_no_llm(mock_backend, tmp_path):
    """analyze() returns None when LLM is unavailable. No data > bad data."""
    html_file = tmp_path / "test.html"
    html_file.write_text(SAMPLE_HTML)

    result = analyze(html_file, use_cache=False)
    assert result is None


@mock.patch("content_identity.detect_backend", return_value="copilot-cli")
@mock.patch("content_identity.copilot_call", return_value="not valid json at all")
def test_analyze_returns_none_on_bad_json(mock_call, mock_backend, tmp_path):
    """analyze() returns None when LLM returns unparseable response."""
    html_file = tmp_path / "test.html"
    html_file.write_text(SAMPLE_HTML)

    result = analyze(html_file, use_cache=False)
    assert result is None


@mock.patch("content_identity.detect_backend", return_value="copilot-cli")
@mock.patch("content_identity.copilot_call")
def test_analyze_clamps_scores(mock_call, mock_backend, tmp_path):
    """Scores are clamped to valid ranges."""
    bad_scores = {**MOCK_IDENTITY, "craft_score": 99, "completeness_score": -5, "engagement_score": 50}
    mock_call.return_value = json.dumps(bad_scores)

    html_file = tmp_path / "test.html"
    html_file.write_text(SAMPLE_HTML)

    result = analyze(html_file, use_cache=False)
    assert result["craft_score"] == 20  # clamped to max
    assert result["completeness_score"] == 0  # clamped to min
    assert result["engagement_score"] == 25  # clamped to max


@mock.patch("content_identity.detect_backend", return_value="copilot-cli")
@mock.patch("content_identity.copilot_call")
def test_analyze_rejects_missing_fields(mock_call, mock_backend, tmp_path):
    """analyze() rejects responses missing required fields."""
    incomplete = {"medium": "test", "purpose": "test"}  # missing many fields
    mock_call.return_value = json.dumps(incomplete)

    html_file = tmp_path / "test.html"
    html_file.write_text(SAMPLE_HTML)

    result = analyze(html_file, use_cache=False)
    assert result is None


@mock.patch("content_identity.detect_backend", return_value="copilot-cli")
@mock.patch("content_identity.copilot_call")
def test_analyze_uses_cache(mock_call, mock_backend, tmp_path):
    """Second call uses cache, doesn't call LLM again."""
    import content_identity
    old_cache = content_identity.IDENTITY_CACHE
    content_identity.IDENTITY_CACHE = tmp_path / "cache.json"
    old_root = content_identity.ROOT
    content_identity.ROOT = tmp_path

    try:
        mock_call.return_value = json.dumps(MOCK_IDENTITY)
        html_file = tmp_path / "synth.html"
        html_file.write_text(SAMPLE_HTML)

        # First call: hits LLM
        r1 = analyze(html_file, use_cache=True)
        assert r1 is not None
        assert mock_call.call_count == 1

        # Second call: uses cache
        r2 = analyze(html_file, use_cache=True)
        assert r2 is not None
        assert mock_call.call_count == 1  # no additional call
    finally:
        content_identity.IDENTITY_CACHE = old_cache
        content_identity.ROOT = old_root


@mock.patch("content_identity.detect_backend", return_value="copilot-cli")
@mock.patch("content_identity.copilot_call")
def test_get_improvement_vector(mock_call, mock_backend, tmp_path):
    """get_improvement_vector() returns the top improvement."""
    mock_call.return_value = json.dumps(MOCK_IDENTITY)
    html_file = tmp_path / "test.html"
    html_file.write_text(SAMPLE_HTML)

    vector = get_improvement_vector(html_file)
    assert vector is not None
    assert "knob controls" in vector.lower() or "frequency" in vector.lower()


@mock.patch("content_identity.detect_backend", return_value="copilot-cli")
@mock.patch("content_identity.copilot_call")
def test_get_adaptive_scores(mock_call, mock_backend, tmp_path):
    """get_adaptive_scores() returns the three dimension scores."""
    mock_call.return_value = json.dumps(MOCK_IDENTITY)
    html_file = tmp_path / "test.html"
    html_file.write_text(SAMPLE_HTML)

    scores = get_adaptive_scores(html_file)
    assert scores is not None
    assert scores["craft_score"] == 12
    assert scores["completeness_score"] == 6
    assert scores["engagement_score"] == 8
    assert scores["medium"] == "FM synthesizer"


@mock.patch("content_identity.detect_backend", return_value="unavailable")
def test_analyze_bulk_empty_when_no_llm(mock_backend, tmp_path):
    """analyze_bulk() returns empty when LLM unavailable."""
    html_file = tmp_path / "test.html"
    html_file.write_text(SAMPLE_HTML)

    results = analyze_bulk([html_file])
    assert results == {}


def test_analyze_nonexistent_file():
    """analyze() returns None for nonexistent file."""
    result = analyze(Path("/nonexistent/file.html"), use_cache=False)
    assert result is None


def test_prompt_is_content_agnostic():
    """The analysis prompt does NOT assume games."""
    # The prompt should explicitly disclaim game assumptions
    assert "Do NOT assume this is a game" in ANALYZE_PROMPT
    assert "could be anything" in ANALYZE_PROMPT
    # Scoring dimensions should not be game-specific
    for term in ["playability", "game loop", "game over"]:
        assert term not in ANALYZE_PROMPT.lower()
