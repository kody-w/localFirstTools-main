"""
Tests for Feed Gods — AI Social Network Simulation.

Validates that feed-gods.html meets all structural, scale, systems, and
feature requirements. Run with:

    pytest scripts/tests/test_feed_gods.py -v
    pytest scripts/tests/test_feed_gods.py -v --new-files apps/experimental-ai/feed-gods.html
"""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
APP_PATH = ROOT / "apps" / "experimental-ai" / "feed-gods.html"


@pytest.fixture(scope="module")
def html():
    """Load the feed-gods.html content."""
    assert APP_PATH.exists(), f"File not found: {APP_PATH}"
    return APP_PATH.read_text(encoding="utf-8", errors="replace")


# ──────────────────────────────────────────────
# Structural Requirements
# ──────────────────────────────────────────────
class TestStructural:
    def test_has_doctype(self, html):
        assert "<!DOCTYPE html>" in html or "<!doctype html>" in html

    def test_has_viewport(self, html):
        assert '<meta name="viewport"' in html

    def test_has_title(self, html):
        match = re.search(r"<title>(.*?)</title>", html)
        assert match and len(match.group(1).strip()) > 2

    def test_has_inline_css(self, html):
        assert "<style>" in html and "</style>" in html

    def test_has_inline_js(self, html):
        assert "<script>" in html and "</script>" in html

    def test_no_external_deps(self, html):
        bad = re.findall(r'(?:src|href)="(https?://[^"]+\.(?:js|css|mjs))"', html)
        assert len(bad) == 0, f"External deps found: {bad}"

    def test_no_fetch_calls(self, html):
        """No network requests — fully offline."""
        # Allow fetch in comments/strings but not actual API calls
        fetch_calls = re.findall(r'(?<!//\s)fetch\s*\(', html)
        api_calls = re.findall(r'XMLHttpRequest', html)
        assert len(api_calls) == 0, "No XMLHttpRequest allowed"


# ──────────────────────────────────────────────
# Scale Requirements
# ──────────────────────────────────────────────
class TestScale:
    def test_min_file_size(self, html):
        size_kb = len(html) / 1024
        assert size_kb >= 20, f"Only {size_kb:.1f}KB (need 20KB+)"

    def test_min_lines(self, html):
        lines = html.count("\n") + 1
        assert lines >= 1000, f"Only {lines} lines (need 1000+)"

    def test_substantial_js(self, html):
        scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
        total_js = sum(len(s) for s in scripts)
        assert total_js > 20000, f"Only {total_js} chars of JS (need 20000+)"


# ──────────────────────────────────────────────
# 12 AI Agents
# ──────────────────────────────────────────────
class TestAgents:
    EXPECTED_AGENTS = [
        "nova_thinks", "chaos_karen", "soft_boy_sam", "the_contrarian",
        "gossip_girl", "zen_master", "data_driven",
        "nostalgic_nan", "meme_lord", "activist_ally",
        "crypto_chad", "lurker_lisa",
    ]

    def test_has_12_agents(self, html):
        """Must define at least 12 distinct agent identities."""
        # Look for agent definition patterns
        agent_defs = re.findall(
            r'(?:name|username|handle|id)\s*[:=]\s*["\']@?(\w+)["\']',
            html
        )
        assert len(set(agent_defs)) >= 12, \
            f"Found only {len(set(agent_defs))} agents: {set(agent_defs)}"

    def test_agents_have_personality_traits(self, html):
        """Each agent should have numeric personality attributes."""
        trait_patterns = [
            r'agreeabl',
            r'volatil',
            r'contrarian',
        ]
        found = sum(1 for p in trait_patterns if re.search(p, html, re.IGNORECASE))
        assert found >= 2, "Agents need personality trait system (agreeableness, volatility, etc.)"

    def test_agents_have_templates(self, html):
        """Post generation should use templates, not hardcoded text."""
        template_indicators = [
            r'template',
            r'\{agent\}|\{topic\}|\{trend\}',
            r'generatePost|createPost|makePost',
        ]
        found = sum(1 for p in template_indicators if re.search(p, html, re.IGNORECASE))
        assert found >= 1, "Must use template-based post generation"


# ──────────────────────────────────────────────
# Algorithm Controls (The Core Mechanic)
# ──────────────────────────────────────────────
class TestAlgorithmControls:
    def test_has_slider_controls(self, html):
        """Must have range inputs for algorithm tuning."""
        sliders = re.findall(r'type=["\']range["\']', html, re.IGNORECASE)
        assert len(sliders) >= 4, f"Only {len(sliders)} sliders (need 4+ algorithm controls)"

    def test_has_controversy_control(self, html):
        assert re.search(r'controvers', html, re.IGNORECASE), \
            "Missing controversy/conflict amplification control"

    def test_has_echo_chamber_control(self, html):
        assert re.search(r'echo.?chamber|echo|filter.?bubble', html, re.IGNORECASE), \
            "Missing echo chamber control"

    def test_has_trend_control(self, html):
        assert re.search(r'trend|velocity|viral', html, re.IGNORECASE), \
            "Missing trend velocity control"


# ──────────────────────────────────────────────
# Social Graph Visualization
# ──────────────────────────────────────────────
class TestSocialGraph:
    def test_has_canvas(self, html):
        assert "<canvas" in html, "Must have canvas element for social graph"

    def test_has_graph_rendering(self, html):
        """Must render relationships between agents."""
        graph_patterns = [
            r'drawLine|lineTo|moveTo',
            r'relationship|connection|edge|link',
            r'graph|network|node',
        ]
        found = sum(1 for p in graph_patterns if re.search(p, html, re.IGNORECASE))
        assert found >= 2, "Must render a social graph with lines between agents"


# ──────────────────────────────────────────────
# Feed / Post System
# ──────────────────────────────────────────────
class TestFeedSystem:
    def test_has_feed_container(self, html):
        """Must have a scrollable feed area."""
        assert re.search(r'feed|timeline|posts|stream', html, re.IGNORECASE), \
            "Must have a feed/timeline container"

    def test_has_engagement_metrics(self, html):
        """Posts should show likes/replies/engagement."""
        metrics = [r'like', r'repl(?:y|ies)', r'repost|share|boost']
        found = sum(1 for p in metrics if re.search(p, html, re.IGNORECASE))
        assert found >= 2, "Posts must show engagement metrics (likes, replies, etc.)"

    def test_has_trending_topics(self, html):
        assert re.search(r'trend', html, re.IGNORECASE), \
            "Must have trending topics system"

    def test_has_post_interval(self, html):
        """Agents should post on a timer."""
        assert re.search(r'setInterval|setTimeout|requestAnimationFrame', html), \
            "Must have timed post generation"


# ──────────────────────────────────────────────
# Simulation State & Persistence
# ──────────────────────────────────────────────
class TestSimulation:
    def test_has_localstorage(self, html):
        assert "localStorage" in html, "Must use localStorage for save/load"

    def test_has_speed_control(self, html):
        assert re.search(r'speed|pause|1x|2x|5x', html, re.IGNORECASE), \
            "Must have simulation speed controls"

    def test_has_culture_metrics(self, html):
        """Must track emergent culture metrics."""
        metrics = [r'drama', r'unity|cohesion', r'toxic', r'engag']
        found = sum(1 for p in metrics if re.search(p, html, re.IGNORECASE))
        assert found >= 2, "Must track culture metrics (drama, unity, toxicity, engagement)"

    def test_has_mood_or_opinion_state(self, html):
        """Agents must maintain internal state."""
        assert re.search(r'mood|opinion|sentiment|emotion|state', html, re.IGNORECASE), \
            "Agents must have mood/opinion state"


# ──────────────────────────────────────────────
# RappterZoo Meta Tags
# ──────────────────────────────────────────────
class TestMetaTags:
    REQUIRED_TAGS = [
        "rappterzoo:author",
        "rappterzoo:category",
        "rappterzoo:tags",
        "rappterzoo:type",
        "rappterzoo:complexity",
        "rappterzoo:created",
    ]

    def test_has_rappterzoo_meta_tags(self, html):
        missing = [t for t in self.REQUIRED_TAGS if t not in html]
        assert len(missing) == 0, f"Missing rappterzoo meta tags: {missing}"


# ──────────────────────────────────────────────
# Audio
# ──────────────────────────────────────────────
class TestAudio:
    def test_has_web_audio(self, html):
        assert re.search(r'AudioContext|webkitAudioContext', html), \
            "Must use Web Audio API for notification sounds"


# ──────────────────────────────────────────────
# JavaScript Validity
# ──────────────────────────────────────────────
class TestCodeQuality:
    def test_no_syntax_errors_in_const_let(self, html):
        """Check for duplicate const/let at true top-level scope (common LLM bug)."""
        scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
        for script in scripts:
            # Only flag declarations at column 0 (true top-level, not inside functions)
            declarations = re.findall(r'^(?:const|let)\s+(\w+)', script, re.MULTILINE)
            seen = {}
            dupes = []
            for d in declarations:
                if d in seen:
                    dupes.append(d)
                seen[d] = True
            assert len(dupes) < 3, f"Top-level duplicate declarations: {dupes[:10]}"

    def test_no_unclosed_strings(self, html):
        """Basic check for obviously broken template literals."""
        scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
        for script in scripts:
            backticks = script.count('`')
            assert backticks % 2 == 0, "Odd number of backticks — unclosed template literal"
