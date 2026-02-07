#!/usr/bin/env python3
"""
app.py — Local API server for Data Slosh HTML Quality Pipeline

Bridges the Data Slosh browser UI to the Copilot CLI + Claude Opus intelligence
backend used by autosort.py. Exposes two endpoints:

  POST /api/analyze   — Classify HTML: filename, category, title, description, tags
  POST /api/rewrite   — Full AI rewrite: improved HTML + metadata suggestions

Requires:
  - gh CLI with Copilot extension installed
  - Flask + flask-cors (pip install flask flask-cors)

Run:
  python3 scripts/app.py
  python3 scripts/app.py --port 8080
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

MODEL = "claude-opus-4.6"

ROOT = Path(__file__).resolve().parent.parent
APPS_DIR = ROOT / "apps"

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

VALID_TAGS = [
    "3d", "canvas", "svg", "animation", "audio", "particles", "physics",
    "interactive", "game", "ai", "creative", "terminal", "retro",
    "simulation", "crm", "visualization", "drawing", "generative",
]


# ─── Copilot CLI Integration (reused from autosort.py) ──────────────────────


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


def copilot_call(prompt):
    """Send a prompt to Copilot CLI with Claude Opus and return the raw response."""
    cmd = [
        "gh", "copilot",
        "--model", MODEL,
        "-p", prompt,
        "--no-ask-user",
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
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


def parse_llm_text(raw_output):
    """Extract text content from LLM output, stripping wrapper."""
    if not raw_output:
        return None
    text = strip_copilot_wrapper(raw_output)
    # Remove markdown code fences if the whole response is wrapped
    if text.startswith("```"):
        fenced = re.search(r"```(?:html)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if fenced:
            return fenced.group(1).strip()
    return text


def validate_analysis(result):
    """Validate and sanitize the LLM analysis response."""
    if not result or not isinstance(result, dict):
        return None

    cat = result.get("category", "")
    if cat not in VALID_CATEGORIES:
        for valid_key in VALID_CATEGORIES:
            if cat.replace("-", "_").replace(" ", "_").lower() == valid_key:
                result["category"] = valid_key
                break
        else:
            result["category"] = "experimental_ai"

    fn = result.get("filename", "")
    if not fn or not fn.endswith(".html"):
        result["filename"] = "untitled.html"
    else:
        fn = re.sub(r"[^a-z0-9\-.]", "", fn.lower())
        result["filename"] = fn if len(fn) >= 5 else "untitled.html"

    tags = result.get("tags", [])
    result["tags"] = [t for t in tags if t in VALID_TAGS][:6]

    valid_types = {"game", "visual", "audio", "interactive", "interface", "drawing"}
    if result.get("type") not in valid_types:
        result["type"] = "interactive"

    if not result.get("title"):
        result["title"] = "Untitled App"
    if not result.get("description"):
        result["description"] = f"Self-contained {result['type']} application"

    return result


# ─── Prompts ─────────────────────────────────────────────────────────────────


def build_analyze_prompt(html, filename, analysis_context=None):
    """Build prompt for classification (filename, category, metadata)."""
    sample = html[:8000]
    categories_list = ", ".join(VALID_CATEGORIES.keys())
    tags_list = ", ".join(VALID_TAGS)

    context_block = ""
    if analysis_context:
        context_block = f"""
Data Slosh Quality Analysis:
- Score: {analysis_context.get('score', '?')}/100
- Errors: {analysis_context.get('errors', '?')}
- Warnings: {analysis_context.get('warnings', '?')}
- Failed rules: {', '.join(analysis_context.get('failedRules', []))}
"""

    return f"""You are a content analyst categorizing self-contained HTML applications for a gallery.
{context_block}
Analyze this HTML file and return ONLY a JSON object (no markdown, no explanation, no code fences) with these exact keys:

{{
  "category": "one of: {categories_list}",
  "filename": "descriptive-kebab-case-name.html",
  "title": "Human Readable Title",
  "description": "One sentence describing what this app does",
  "tags": ["up to 6 tags from: {tags_list}"],
  "type": "game|visual|audio|interactive|interface|drawing",
  "complexity": "simple|intermediate|advanced"
}}

Rules:
- category MUST be exactly one of: {categories_list}
- filename must be descriptive of the content, kebab-case, max 60 chars, ending in .html
- description must be exactly one sentence, under 120 characters
- Pick the MOST SPECIFIC category. experimental_ai is catch-all ONLY if nothing else fits
- For games/puzzles: games_puzzles. For 3D/WebGL/Three.js: 3d_immersive
- For audio/music/synth: audio_music. For drawing/painting: visual_art
- For procedural/generative art: generative_art. For physics sims: particle_physics
- For utilities/productivity: creative_tools. For learning: educational_tools
- tags must only contain values from: {tags_list}

Original filename: {filename}

HTML content (first 8000 chars):
---
{sample}
---

Return ONLY the JSON object."""


def build_rewrite_prompt(html, filename, analysis_context=None, metadata=None):
    """Build prompt for structured improvement instructions (NOT full HTML rewrite).

    Returns JSON with specific fixes to apply, rather than the full rewritten file.
    This avoids output size limits in the Copilot CLI.
    """
    sample = html[:8000]

    context_block = ""
    if analysis_context:
        failed = ', '.join(analysis_context.get('failedRules', []))
        context_block = f"""
Data Slosh Quality Analysis:
- Score: {analysis_context.get('score', '?')}/100
- Failed rules: {failed}
"""

    metadata_block = ""
    if metadata:
        metadata_block = f"""
AI Classification:
- Title: {metadata.get('title', '?')}
- Category: {metadata.get('category', '?')}
- Description: {metadata.get('description', '?')}
"""

    categories_list = ", ".join(VALID_CATEGORIES.keys())
    tags_list = ", ".join(VALID_TAGS)

    return f"""You are an expert HTML quality engineer analyzing a self-contained HTML application.
{context_block}{metadata_block}
Analyze this HTML and return ONLY a JSON object (no markdown, no explanation, no code fences) with improvement instructions:

{{
  "category": "one of: {categories_list}",
  "filename": "descriptive-kebab-case-name.html",
  "title": "Best title for this app",
  "description": "One-sentence description under 120 chars",
  "tags": ["up to 6 tags from: {tags_list}"],
  "type": "game|visual|audio|interactive|interface|drawing",
  "complexity": "simple|intermediate|advanced",
  "metaDescription": "content attribute for <meta name=description>",
  "improvements": [
    "Description of each specific quality fix needed"
  ],
  "externalDepsFound": ["list any external CDN URLs that need to be removed/inlined"],
  "securityIssues": ["any hardcoded API keys or secrets found"],
  "accessibilityNotes": "brief note on ARIA/accessibility improvements needed"
}}

Rules:
- category MUST be one of: {categories_list}. experimental_ai is catch-all.
- filename: descriptive, kebab-case, max 60 chars, .html extension
- description: one sentence under 120 chars
- improvements: list SPECIFIC fixes (e.g. "Add <meta charset=UTF-8> after <head>", "Remove console.log on line ~45")
- tags from: {tags_list}

Original filename: {filename}

HTML (first 8000 chars):
---
{sample}
---

Return ONLY the JSON object."""


# ─── API Routes ──────────────────────────────────────────────────────────────


@app.route("/api/health", methods=["GET"])
def health():
    """Health check + backend detection."""
    backend = detect_backend()
    return jsonify({
        "status": "ok",
        "backend": backend,
        "model": MODEL if backend == "copilot-cli" else None,
    })


@app.route("/api/analyze", methods=["POST"])
def analyze():
    """Classify HTML: returns filename, category, title, description, tags, type."""
    data = request.get_json()
    if not data or "html" not in data:
        return jsonify({"error": "Missing 'html' field"}), 400

    html = data["html"]
    filename = data.get("filename", "untitled.html")
    analysis_context = data.get("analysis", None)

    backend = detect_backend()
    if backend != "copilot-cli":
        return jsonify({"error": "Copilot CLI not available", "backend": backend}), 503

    prompt = build_analyze_prompt(html, filename, analysis_context)
    raw = copilot_call(prompt)

    result = parse_llm_json(raw)
    if result is None:
        return jsonify({"error": "Could not parse LLM response"}), 502

    validated = validate_analysis(result)
    if validated is None:
        return jsonify({"error": "LLM response failed validation"}), 502

    # Add category folder for convenience
    validated["categoryFolder"] = VALID_CATEGORIES.get(
        validated["category"], validated["category"]
    )

    return jsonify(validated)


@app.route("/api/rewrite", methods=["POST"])
def rewrite():
    """AI-powered quality analysis: returns structured improvement instructions + metadata.

    Single LLM call that returns classification + specific fix instructions as JSON.
    The browser-side Improver applies the fixes locally (no full HTML rewrite via CLI).
    """
    data = request.get_json()
    if not data or "html" not in data:
        return jsonify({"error": "Missing 'html' field"}), 400

    html = data["html"]
    filename = data.get("filename", "untitled.html")
    analysis_context = data.get("analysis", None)

    backend = detect_backend()
    if backend != "copilot-cli":
        return jsonify({"error": "Copilot CLI not available", "backend": backend}), 503

    # Single LLM call for classification + improvement instructions
    prompt = build_rewrite_prompt(html, filename, analysis_context)
    raw = copilot_call(prompt)

    result = parse_llm_json(raw)
    if result is None:
        return jsonify({"error": "Could not parse LLM response"}), 502

    validated = validate_analysis(result)
    if validated is None:
        return jsonify({"error": "LLM response failed validation"}), 502

    # Build response with all fields the frontend expects
    response = {
        "metadata": validated,
        "suggestedFilename": validated.get("filename", filename),
        "suggestedCategory": validated.get("category", "experimental_ai"),
        "categoryFolder": VALID_CATEGORIES.get(
            validated.get("category", ""), "experimental-ai"
        ),
        "suggestedTitle": validated.get("title", ""),
        "suggestedDescription": validated.get("description", ""),
        "suggestedTags": validated.get("tags", []),
        "suggestedType": validated.get("type", "interactive"),
        "suggestedComplexity": validated.get("complexity", "intermediate"),
        "improvements": validated.get("improvements", []),
        "externalDepsFound": validated.get("externalDepsFound", []),
        "securityIssues": validated.get("securityIssues", []),
        "accessibilityNotes": validated.get("accessibilityNotes", ""),
        "metaDescription": validated.get("metaDescription", ""),
    }

    return jsonify(response)


# ─── Main ────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    port = 5000
    if "--port" in sys.argv:
        idx = sys.argv.index("--port")
        if idx + 1 < len(sys.argv):
            port = int(sys.argv[idx + 1])

    backend = detect_backend()
    print(f"Data Slosh API Server")
    print(f"  Backend: {backend}")
    print(f"  Model:   {MODEL if backend == 'copilot-cli' else 'N/A (keyword fallback)'}")
    print(f"  URL:     http://localhost:{port}")
    print(f"\nEndpoints:")
    print(f"  GET  /api/health   — Backend status")
    print(f"  POST /api/analyze  — Classify HTML (filename, category, tags)")
    print(f"  POST /api/rewrite  — Full AI rewrite + classification")
    print()

    app.run(host="127.0.0.1", port=port, debug=True)
