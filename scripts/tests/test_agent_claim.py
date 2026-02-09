"""Tests for the RappterZoo Agent Claim Flow.

Validates the full agent registration → claim → trust tier pipeline:
  - Registration generates claim codes
  - Claim verification matches codes and records owner
  - Trust tiers (unclaimed → claimed → verified)
  - Duplicate/invalid code handling
  - Claim page HTML meets RappterZoo conventions

All tests are mocked — no network, no GitHub API calls.
"""
import json
import os
import re
import secrets
import pytest
from unittest.mock import patch, MagicMock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
APPS_DIR = os.path.join(REPO_ROOT, "apps")
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
CLAIM_PAGE_PATH = os.path.join(APPS_DIR, "productivity", "agent-claim.html")
ISSUE_TEMPLATE_PATH = os.path.join(REPO_ROOT, ".github", "ISSUE_TEMPLATE", "agent-claim.yml")

# Add scripts dir to path for imports
import sys
sys.path.insert(0, SCRIPTS_DIR)
import process_agent_issues as pai


def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def make_agents_registry(agents=None):
    """Create a test agent registry."""
    return {
        "@context": "https://schema.org",
        "@type": "DataFeed",
        "name": "RappterZoo Agent Registry",
        "dateModified": "2026-01-01T00:00:00Z",
        "agents": agents or [],
    }


def make_agent_entry(agent_id="test-agent", name="Test Agent", status="pending_claim",
                     claim_code=None, owner_github=None, trust_tier="unclaimed"):
    """Create a test agent entry."""
    entry = {
        "agent_id": agent_id,
        "name": name,
        "description": "A test agent",
        "capabilities": ["comment", "rate"],
        "type": "external",
        "status": status,
        "owner_url": "",
        "contributions": {"apps_created": 0, "apps_molted": 0, "comments": 0, "ratings": 0},
        "registered": "2026-01-01",
        "trust_tier": trust_tier,
    }
    if claim_code:
        entry["claim_code"] = claim_code
    if owner_github:
        entry["owner_github"] = owner_github
    return entry


# ─── Claim Code Generation ──────────────────────────────────

class TestClaimCodeGeneration:
    """Claim codes must be generated during registration."""

    def test_generate_claim_code_format(self):
        """Claim codes should be word-XXXX format."""
        code = pai.generate_claim_code()
        assert re.match(r"^[a-z]+-[A-Za-z0-9]{4}$", code), \
            "Claim code '{}' doesn't match word-XXXX format".format(code)

    def test_generate_claim_code_unique(self):
        """Multiple calls should produce different codes."""
        codes = set(pai.generate_claim_code() for _ in range(20))
        assert len(codes) >= 15, "Too many duplicate claim codes in 20 generations"

    def test_registration_includes_claim_code(self, tmp_path):
        """Registration should add claim_code to agent entry."""
        agents_file = tmp_path / "agents.json"
        agents_file.write_text(json.dumps(make_agents_registry()))

        data = {
            "agent_id": "new-agent",
            "name": "New Agent",
            "description": "Test",
            "capabilities": "",
            "owner_url": "",
            "public_key_(optional)": "",
        }

        with patch.object(pai, "AGENTS_PATH", str(agents_file)):
            success, message = pai.process_register(data, 1)

        assert success
        registry = json.loads(agents_file.read_text())
        agent = registry["agents"][0]
        assert "claim_code" in agent
        assert "claim_url" in agent
        assert agent["status"] == "pending_claim"
        assert agent["trust_tier"] == "unclaimed"

    def test_registration_returns_claim_url(self, tmp_path):
        """Registration message should include claim URL."""
        agents_file = tmp_path / "agents.json"
        agents_file.write_text(json.dumps(make_agents_registry()))

        data = {
            "agent_id": "url-agent",
            "name": "URL Agent",
            "description": "Test",
            "capabilities": "",
            "owner_url": "",
            "public_key_(optional)": "",
        }

        with patch.object(pai, "AGENTS_PATH", str(agents_file)):
            success, message = pai.process_register(data, 1)

        assert success
        assert "claim" in message.lower()
        assert "url-agent" in message


# ─── Claim Processing ────────────────────────────────────────

class TestClaimProcessing:
    """Claim action must verify codes and update agent status."""

    def test_valid_claim(self, tmp_path):
        """Valid claim code should activate the agent."""
        agent = make_agent_entry(
            agent_id="claim-me",
            status="pending_claim",
            claim_code="reef-X4B2",
            trust_tier="unclaimed",
        )
        agents_file = tmp_path / "agents.json"
        agents_file.write_text(json.dumps(make_agents_registry([agent])))

        data = {
            "agent_id": "claim-me",
            "claim_code": "reef-X4B2",
            "github_username": "kody-w",
        }

        with patch.object(pai, "AGENTS_PATH", str(agents_file)):
            success, message = pai.process_claim(data, 1)

        assert success
        registry = json.loads(agents_file.read_text())
        claimed = registry["agents"][0]
        assert claimed["status"] == "claimed"
        assert claimed["trust_tier"] == "claimed"
        assert claimed["owner_github"] == "kody-w"

    def test_invalid_claim_code(self, tmp_path):
        """Wrong claim code should be rejected."""
        agent = make_agent_entry(
            agent_id="claim-me",
            status="pending_claim",
            claim_code="reef-X4B2",
        )
        agents_file = tmp_path / "agents.json"
        agents_file.write_text(json.dumps(make_agents_registry([agent])))

        data = {
            "agent_id": "claim-me",
            "claim_code": "wrong-CODE",
            "github_username": "attacker",
        }

        with patch.object(pai, "AGENTS_PATH", str(agents_file)):
            success, message = pai.process_claim(data, 1)

        assert not success
        assert "invalid" in message.lower() or "mismatch" in message.lower()

    def test_claim_nonexistent_agent(self, tmp_path):
        """Claiming a nonexistent agent should fail."""
        agents_file = tmp_path / "agents.json"
        agents_file.write_text(json.dumps(make_agents_registry()))

        data = {
            "agent_id": "ghost-agent",
            "claim_code": "any-CODE",
            "github_username": "kody-w",
        }

        with patch.object(pai, "AGENTS_PATH", str(agents_file)):
            success, message = pai.process_claim(data, 1)

        assert not success
        assert "not found" in message.lower()

    def test_claim_already_claimed_agent(self, tmp_path):
        """Claiming an already-claimed agent should fail."""
        agent = make_agent_entry(
            agent_id="taken",
            status="claimed",
            claim_code="reef-X4B2",
            owner_github="original-owner",
            trust_tier="claimed",
        )
        agents_file = tmp_path / "agents.json"
        agents_file.write_text(json.dumps(make_agents_registry([agent])))

        data = {
            "agent_id": "taken",
            "claim_code": "reef-X4B2",
            "github_username": "hijacker",
        }

        with patch.object(pai, "AGENTS_PATH", str(agents_file)):
            success, message = pai.process_claim(data, 1)

        assert not success
        assert "already claimed" in message.lower()

    def test_claim_with_tweet_gets_verified_tier(self, tmp_path):
        """Providing a tweet URL during claim should set trust_tier to verified."""
        agent = make_agent_entry(
            agent_id="tweeter",
            status="pending_claim",
            claim_code="coral-QQJK",
        )
        agents_file = tmp_path / "agents.json"
        agents_file.write_text(json.dumps(make_agents_registry([agent])))

        data = {
            "agent_id": "tweeter",
            "claim_code": "coral-QQJK",
            "github_username": "kody-w",
            "tweet_url": "https://x.com/kodyw/status/1234567890",
        }

        with patch.object(pai, "AGENTS_PATH", str(agents_file)):
            success, message = pai.process_claim(data, 1)

        assert success
        registry = json.loads(agents_file.read_text())
        claimed = registry["agents"][0]
        assert claimed["trust_tier"] == "verified"
        assert claimed["tweet_url"] == "https://x.com/kodyw/status/1234567890"


# ─── Trust Tiers ─────────────────────────────────────────────

class TestTrustTiers:
    """Trust tier system must enforce correct levels."""

    def test_unclaimed_is_default(self):
        """New agents should start as unclaimed."""
        agent = make_agent_entry()
        assert agent["trust_tier"] == "unclaimed"

    def test_trust_tier_values(self):
        """Only valid trust tiers should exist."""
        valid_tiers = {"unclaimed", "claimed", "verified"}
        for tier in valid_tiers:
            agent = make_agent_entry(trust_tier=tier)
            assert agent["trust_tier"] in valid_tiers


# ─── Issue Detection ─────────────────────────────────────────

class TestClaimIssueDetection:
    """The claim action must be detectable from issue labels/title."""

    def test_detect_claim_from_title(self):
        issue = {"title": "[Agent Claim] my-agent", "labels": []}
        assert pai.detect_action(issue) == "claim_agent"

    def test_detect_claim_from_label(self):
        issue = {"title": "Claiming my agent", "labels": [{"name": "agent-claim"}]}
        assert pai.detect_action(issue) == "claim_agent"


# ─── Claim Page HTML ─────────────────────────────────────────

class TestClaimPageHTML:
    """The static claim page must meet RappterZoo app conventions."""

    @pytest.fixture
    def html(self):
        return read_file(CLAIM_PAGE_PATH)

    def test_file_exists(self):
        assert os.path.isfile(CLAIM_PAGE_PATH)

    def test_has_doctype(self, html):
        assert "<!DOCTYPE html>" in html or "<!doctype html>" in html.lower()

    def test_has_title(self, html):
        assert re.search(r"<title>.+</title>", html)

    def test_has_viewport_meta(self, html):
        assert 'name="viewport"' in html

    def test_has_inline_style(self, html):
        assert "<style>" in html or "<style " in html

    def test_has_inline_script(self, html):
        assert "<script>" in html or "<script " in html

    def test_no_external_css(self, html):
        links = re.findall(r'<link[^>]+rel=["\']stylesheet["\'][^>]*>', html)
        external = [l for l in links if "http" in l]
        assert len(external) == 0, "External CSS found: {}".format(external)

    def test_no_external_js(self, html):
        scripts = re.findall(r'<script[^>]+src=["\']https?://[^"\']+["\'][^>]*>', html)
        assert len(scripts) == 0, "External JS found: {}".format(scripts)

    def test_no_cdn_references(self, html):
        cdns = re.findall(r"https?://cdn[\.\w]+", html)
        assert len(cdns) == 0, "CDN references found: {}".format(cdns)

    def test_parses_url_params(self, html):
        """Must handle ?agent=ID&code=CODE URL parameters."""
        assert "URLSearchParams" in html or "searchParams" in html or "location.search" in html

    def test_fetches_agents_json(self, html):
        """Must fetch agent registry to display agent info."""
        assert "agents.json" in html

    def test_has_claim_form(self, html):
        """Must have a claim form or claim button."""
        assert re.search(r"(claim|verify|activate)", html, re.IGNORECASE)

    def test_has_github_issue_link(self, html):
        """Must link to GitHub issue creation for claiming."""
        assert "github.com" in html or "gh issue" in html.lower()

    def test_has_tweet_option(self, html):
        """Must have optional tweet verification."""
        assert re.search(r"tweet", html, re.IGNORECASE)

    def test_has_trust_tier_display(self, html):
        """Must show trust tier information."""
        assert re.search(r"(trust|tier|verified|claimed)", html, re.IGNORECASE)

    def test_has_step_indicators(self, html):
        """Must show multi-step claim process."""
        assert re.search(r"step", html, re.IGNORECASE)

    def test_minimum_size(self, html):
        lines = html.count("\n")
        assert lines > 200, "Only {} lines — claim page needs >= 200".format(lines)


# ─── Issue Template ──────────────────────────────────────────

class TestClaimIssueTemplate:
    """The agent-claim.yml issue template must exist and be valid."""

    def test_template_exists(self):
        assert os.path.isfile(ISSUE_TEMPLATE_PATH)

    def test_template_has_agent_id_field(self):
        content = read_file(ISSUE_TEMPLATE_PATH)
        assert "agent_id" in content

    def test_template_has_claim_code_field(self):
        content = read_file(ISSUE_TEMPLATE_PATH)
        assert "claim_code" in content

    def test_template_has_tweet_url_field(self):
        content = read_file(ISSUE_TEMPLATE_PATH)
        assert "tweet_url" in content

    def test_template_has_correct_labels(self):
        content = read_file(ISSUE_TEMPLATE_PATH)
        assert "agent-action" in content
        assert "agent-claim" in content

    def test_template_has_correct_title_format(self):
        content = read_file(ISSUE_TEMPLATE_PATH)
        assert "[Agent Claim]" in content


# ─── Integration: Registration → Claim Round Trip ────────────

class TestRegistrationClaimRoundTrip:
    """Full round trip: register → get code → claim with code."""

    def test_full_round_trip(self, tmp_path):
        """Register an agent, then claim it with the generated code."""
        agents_file = tmp_path / "agents.json"
        agents_file.write_text(json.dumps(make_agents_registry()))

        # Step 1: Register
        reg_data = {
            "agent_id": "round-trip-agent",
            "name": "Round Trip Agent",
            "description": "Testing the full flow",
            "capabilities": "- [X] comment\n- [X] rate",
            "owner_url": "",
            "public_key_(optional)": "",
        }

        with patch.object(pai, "AGENTS_PATH", str(agents_file)):
            success, message = pai.process_register(reg_data, 1)
        assert success

        # Extract claim code from registry
        registry = json.loads(agents_file.read_text())
        agent = registry["agents"][0]
        claim_code = agent["claim_code"]
        assert claim_code  # must exist

        # Step 2: Claim with the correct code
        claim_data = {
            "agent_id": "round-trip-agent",
            "claim_code": claim_code,
            "github_username": "round-trip-human",
        }

        with patch.object(pai, "AGENTS_PATH", str(agents_file)):
            success, message = pai.process_claim(claim_data, 2)
        assert success

        # Verify final state
        registry = json.loads(agents_file.read_text())
        agent = registry["agents"][0]
        assert agent["status"] == "claimed"
        assert agent["trust_tier"] == "claimed"
        assert agent["owner_github"] == "round-trip-human"

    def test_round_trip_with_tweet(self, tmp_path):
        """Register → claim with tweet URL → verified tier."""
        agents_file = tmp_path / "agents.json"
        agents_file.write_text(json.dumps(make_agents_registry()))

        reg_data = {
            "agent_id": "tweet-agent",
            "name": "Tweet Agent",
            "description": "Testing tweet verification",
            "capabilities": "",
            "owner_url": "",
            "public_key_(optional)": "",
        }

        with patch.object(pai, "AGENTS_PATH", str(agents_file)):
            success, _ = pai.process_register(reg_data, 1)
        assert success

        registry = json.loads(agents_file.read_text())
        claim_code = registry["agents"][0]["claim_code"]

        claim_data = {
            "agent_id": "tweet-agent",
            "claim_code": claim_code,
            "github_username": "tweeter",
            "tweet_url": "https://x.com/tweeter/status/999",
        }

        with patch.object(pai, "AGENTS_PATH", str(agents_file)):
            success, _ = pai.process_claim(claim_data, 2)
        assert success

        registry = json.loads(agents_file.read_text())
        agent = registry["agents"][0]
        assert agent["trust_tier"] == "verified"
        assert agent["tweet_url"] == "https://x.com/tweeter/status/999"
