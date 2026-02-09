"""Tests for AgentZoo Protocol apps.

Validates all AgentZoo suite apps meet RappterZoo conventions and contain
the required cryptographic, identity, messaging, and marketplace functionality.

Apps tested:
  - agentzoo-protocol.html  (interactive protocol spec + crypto playground)
  - agentzoo-registry.html  (agent identity creation + discovery browser)
  - agentzoo-handshake.html (key exchange + signed messaging demo)
  - agentzoo-hub.html       (network dashboard + task marketplace)
"""
import os
import re
import json
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
APPS_DIR = os.path.join(REPO_ROOT, 'apps')
PROTOCOL_PATH = os.path.join(APPS_DIR, 'experimental-ai', 'agentzoo-protocol.html')
REGISTRY_PATH = os.path.join(APPS_DIR, 'experimental-ai', 'agentzoo-registry.html')
HANDSHAKE_PATH = os.path.join(APPS_DIR, 'experimental-ai', 'agentzoo-handshake.html')
HUB_PATH = os.path.join(APPS_DIR, 'experimental-ai', 'agentzoo-hub.html')

AGENTZOO_APPS = {
    'protocol': PROTOCOL_PATH,
    'registry': REGISTRY_PATH,
    'handshake': HANDSHAKE_PATH,
    'hub': HUB_PATH,
}

# Shared localStorage keys that bind the suite together
SHARED_STORAGE_KEYS = [
    'agentzoo-agents',
    'agentzoo-active',
    'agentzoo-messages',
    'agentzoo-tasks',
    'agentzoo-reputation',
    'agentzoo-handshakes',
]


def read_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


# ─── Shared Convention Tests (all AgentZoo apps) ──────────────

class TestAppConventions:
    """All apps must meet RappterZoo HTML app conventions."""

    @pytest.fixture(params=[
        pytest.param('protocol', id='agentzoo-protocol'),
        pytest.param('registry', id='agentzoo-registry'),
        pytest.param('handshake', id='agentzoo-handshake'),
        pytest.param('hub', id='agentzoo-hub'),
    ])
    def app_html(self, request):
        return read_file(AGENTZOO_APPS[request.param])

    def test_has_doctype(self, app_html):
        assert '<!DOCTYPE html>' in app_html or '<!doctype html>' in app_html.lower()

    def test_has_title(self, app_html):
        assert re.search(r'<title>.+</title>', app_html)

    def test_has_viewport_meta(self, app_html):
        assert 'viewport' in app_html

    def test_has_inline_style(self, app_html):
        assert '<style>' in app_html or '<style ' in app_html

    def test_has_inline_script(self, app_html):
        assert '<script>' in app_html or '<script ' in app_html

    def test_no_external_css(self, app_html):
        links = re.findall(r'<link[^>]+rel=["\']stylesheet["\'][^>]*>', app_html)
        external = [l for l in links if 'http' in l]
        assert len(external) == 0, f"External CSS found: {external}"

    def test_no_external_js(self, app_html):
        scripts = re.findall(r'<script[^>]+src=["\']https?://[^"\']+["\'][^>]*>', app_html)
        assert len(scripts) == 0, f"External JS found: {scripts}"

    def test_no_cdn_references(self, app_html):
        cdns = re.findall(r'https?://cdn[.\w]+', app_html)
        assert len(cdns) == 0, f"CDN references found: {cdns}"

    def test_has_rappterzoo_author(self, app_html):
        assert 'rappterzoo:author' in app_html

    def test_has_rappterzoo_category(self, app_html):
        assert 'rappterzoo:category' in app_html

    def test_has_rappterzoo_tags(self, app_html):
        assert 'rappterzoo:tags' in app_html

    def test_has_rappterzoo_type(self, app_html):
        assert 'rappterzoo:type' in app_html

    def test_has_rappterzoo_complexity(self, app_html):
        assert 'rappterzoo:complexity' in app_html

    def test_has_rappterzoo_created(self, app_html):
        assert 'rappterzoo:created' in app_html

    def test_has_rappterzoo_generation(self, app_html):
        assert 'rappterzoo:generation' in app_html

    def test_uses_localstorage(self, app_html):
        assert 'localStorage' in app_html

    def test_no_raw_script_close_in_js(self, app_html):
        """Must not have raw </script> inside JS strings — breaks the parser."""
        script_blocks = re.findall(r'<script[^>]*>(.*?)</script>', app_html, re.DOTALL)
        for block in script_blocks:
            assert '</script>' not in block, "Raw </script> found in JS — escape as <\\/script>"

    # ── AgentZoo-specific meta tags ──

    def test_has_agentzoo_protocol_version(self, app_html):
        assert 'agentzoo:protocol-version' in app_html

    def test_has_agentzoo_capabilities(self, app_html):
        assert 'agentzoo:capabilities' in app_html

    def test_has_agentzoo_agent_types(self, app_html):
        assert 'agentzoo:agent-types' in app_html

    def test_has_agentzoo_integrates_with(self, app_html):
        assert 'agentzoo:integrates-with' in app_html

    def test_has_agentzoo_storage_keys(self, app_html):
        assert 'agentzoo:storage-keys' in app_html

    def test_category_is_experimental_ai(self, app_html):
        m = re.search(r'rappterzoo:category.*?content="([^"]+)"', app_html)
        assert m and m.group(1) == 'experimental-ai'


# ─── AgentZoo Protocol: Spec + Crypto Playground ──────────────

class TestAgentZooProtocol:
    """Protocol app must have spec viewer, crypto playground, schema browser."""

    @pytest.fixture
    def html(self):
        return read_file(PROTOCOL_PATH)

    def test_file_exists(self):
        assert os.path.isfile(PROTOCOL_PATH)

    # --- Crypto foundations ---

    def test_uses_web_crypto_api(self, html):
        assert 'crypto.subtle' in html, "Must use Web Crypto API"

    def test_has_ecdsa(self, html):
        assert re.search(r'ECDSA', html), "Must reference ECDSA"

    def test_has_sha256(self, html):
        assert re.search(r'SHA-256', html), "Must reference SHA-256"

    def test_has_p256_curve(self, html):
        assert 'P-256' in html, "Must use P-256 curve"

    def test_has_key_generation(self, html):
        assert 'generateKey' in html, "Must have key generation"

    def test_has_sign_operation(self, html):
        assert re.search(r'\.sign\(', html), "Must have signing"

    def test_has_verify_operation(self, html):
        assert re.search(r'\.verify\(', html), "Must have verification"

    # --- Protocol spec content ---

    def test_has_identity_section(self, html):
        assert re.search(r'identity', html, re.IGNORECASE), "Must have identity spec"

    def test_has_messages_section(self, html):
        assert re.search(r'message', html, re.IGNORECASE), "Must have messages spec"

    def test_has_tasks_section(self, html):
        assert re.search(r'task', html, re.IGNORECASE), "Must have tasks spec"

    def test_has_reputation_section(self, html):
        assert re.search(r'reputation', html, re.IGNORECASE), "Must have reputation spec"

    # --- Agent types ---

    def test_has_openclaw_type(self, html):
        assert re.search(r'openclaw', html, re.IGNORECASE), "Must reference OpenClaw agent type"

    def test_has_rappter_type(self, html):
        assert re.search(r'rappter', html, re.IGNORECASE), "Must reference Rappter agent type"

    # --- Crypto playground ---

    def test_has_playground(self, html):
        assert re.search(r'playground', html, re.IGNORECASE), "Must have crypto playground"

    def test_has_agent_id_derivation(self, html):
        assert re.search(r'az-', html), "Must derive az- prefixed agent IDs"

    # --- Schema browser ---

    def test_has_schema_browser(self, html):
        assert re.search(r'schema', html, re.IGNORECASE), "Must have schema browser"

    def test_references_storage_keys(self, html):
        assert 'agentzoo-agents' in html
        assert 'agentzoo-messages' in html

    # --- Built-in test runner ---

    def test_has_test_runner(self, html):
        assert re.search(r'(test.*runner|run.*test|self.*test)', html, re.IGNORECASE)

    def test_minimum_size(self, html):
        lines = html.count('\n')
        assert lines > 500, f"Only {lines} lines — protocol spec needs >= 500"


# ─── AgentZoo Registry: Identity Creation + Discovery ─────────

class TestAgentZooRegistry:
    """Registry must handle identity creation, browsing, and profile viewing."""

    @pytest.fixture
    def html(self):
        return read_file(REGISTRY_PATH)

    def test_file_exists(self):
        assert os.path.isfile(REGISTRY_PATH)

    # --- Identity creation ---

    def test_has_identity_creation(self, html):
        assert re.search(r'(create|register|generate)', html, re.IGNORECASE)

    def test_has_agent_type_selection(self, html):
        assert re.search(r'openclaw', html, re.IGNORECASE)
        assert re.search(r'rappter', html, re.IGNORECASE)

    def test_has_capability_selection(self, html):
        assert re.search(r'capabilit', html, re.IGNORECASE), "Must have capability selection"

    def test_has_ecdsa_key_generation(self, html):
        assert 'generateKey' in html
        assert 'ECDSA' in html

    def test_derives_agent_id(self, html):
        assert 'az-' in html, "Must derive az- prefixed agent IDs"

    # --- Agent browser ---

    def test_has_agent_browser(self, html):
        assert re.search(r'(browse|directory|discover|list)', html, re.IGNORECASE)

    def test_has_filter_by_type(self, html):
        assert re.search(r'filter', html, re.IGNORECASE), "Must have filtering"

    # --- Profile viewer ---

    def test_has_profile_viewer(self, html):
        assert re.search(r'profile', html, re.IGNORECASE)

    def test_has_reputation_display(self, html):
        assert re.search(r'reputation', html, re.IGNORECASE)

    def test_has_public_key_display(self, html):
        assert re.search(r'(public.*key|fingerprint|pubkey)', html, re.IGNORECASE)

    # --- Signature verification ---

    def test_has_signature_verification(self, html):
        assert re.search(r'verif', html, re.IGNORECASE)

    # --- Import/export ---

    def test_has_import_export(self, html):
        assert re.search(r'export', html, re.IGNORECASE)
        assert re.search(r'import', html, re.IGNORECASE)

    # --- Shared storage ---

    def test_uses_agents_storage(self, html):
        assert 'agentzoo-agents' in html

    def test_uses_active_storage(self, html):
        assert 'agentzoo-active' in html

    def test_uses_reputation_storage(self, html):
        assert 'agentzoo-reputation' in html

    def test_minimum_size(self, html):
        lines = html.count('\n')
        assert lines > 500, f"Only {lines} lines — registry needs >= 500"


# ─── AgentZoo Handshake: Key Exchange + Messaging ─────────────

class TestAgentZooHandshake:
    """Handshake must have key exchange, signed messaging, and visualization."""

    @pytest.fixture
    def html(self):
        return read_file(HANDSHAKE_PATH)

    def test_file_exists(self):
        assert os.path.isfile(HANDSHAKE_PATH)

    # --- Key exchange ---

    def test_has_key_exchange(self, html):
        assert re.search(r'(key.*exchange|handshake|exchange.*key)', html, re.IGNORECASE)

    def test_has_exchange_steps(self, html):
        """Must have multi-step exchange wizard."""
        assert re.search(r'step', html, re.IGNORECASE)

    # --- Crypto operations ---

    def test_uses_web_crypto(self, html):
        assert 'crypto.subtle' in html

    def test_has_ecdsa_signing(self, html):
        assert 'ECDSA' in html
        assert re.search(r'\.sign\(', html)

    def test_has_verification(self, html):
        assert re.search(r'\.verify\(', html)

    # --- Message composer ---

    def test_has_message_composer(self, html):
        assert re.search(r'(compose|send.*message|message.*compose)', html, re.IGNORECASE)

    def test_has_message_types(self, html):
        """Must support protocol message types."""
        assert re.search(r'(task-offer|handshake|data)', html, re.IGNORECASE)

    # --- Crypto visualizer ---

    def test_has_crypto_visualizer(self, html):
        assert re.search(r'(visualiz|step.*by.*step|pipeline)', html, re.IGNORECASE)

    # --- Message history ---

    def test_has_inbox(self, html):
        assert re.search(r'inbox', html, re.IGNORECASE)

    def test_has_outbox(self, html):
        assert re.search(r'outbox', html, re.IGNORECASE)

    def test_has_verification_badges(self, html):
        assert re.search(r'(verif|badge|valid|authentic)', html, re.IGNORECASE)

    # --- Demo scenarios ---

    def test_has_demo_scenarios(self, html):
        assert re.search(r'demo', html, re.IGNORECASE)

    # --- Shared storage ---

    def test_uses_messages_storage(self, html):
        assert 'agentzoo-messages' in html

    def test_uses_handshakes_storage(self, html):
        assert 'agentzoo-handshakes' in html

    def test_uses_agents_storage(self, html):
        assert 'agentzoo-agents' in html

    def test_minimum_size(self, html):
        lines = html.count('\n')
        assert lines > 500, f"Only {lines} lines — handshake needs >= 500"


# ─── AgentZoo Hub: Network Dashboard + Task Marketplace ───────

class TestAgentZooHub:
    """Hub must have network stats, agent directory, activity feed, tasks."""

    @pytest.fixture
    def html(self):
        return read_file(HUB_PATH)

    def test_file_exists(self):
        assert os.path.isfile(HUB_PATH)

    # --- Network stats ---

    def test_has_network_stats(self, html):
        assert re.search(r'(stats|statistic|metric)', html, re.IGNORECASE)

    def test_has_agent_count(self, html):
        assert re.search(r'agent', html, re.IGNORECASE)

    def test_has_task_count(self, html):
        assert re.search(r'task', html, re.IGNORECASE)

    def test_has_reputation_display(self, html):
        assert re.search(r'reputation', html, re.IGNORECASE)

    # --- Agent directory ---

    def test_has_agent_directory(self, html):
        assert re.search(r'(directory|list|browse)', html, re.IGNORECASE)

    def test_has_directory_filters(self, html):
        assert re.search(r'filter', html, re.IGNORECASE)

    # --- Activity feed ---

    def test_has_activity_feed(self, html):
        assert re.search(r'(activity|feed|timeline|recent)', html, re.IGNORECASE)

    # --- Task marketplace ---

    def test_has_task_marketplace(self, html):
        assert re.search(r'(marketplace|task.*board|task.*list)', html, re.IGNORECASE)

    def test_has_task_statuses(self, html):
        assert re.search(r'(open|claimed|completed)', html, re.IGNORECASE)

    # --- Quick actions ---

    def test_has_quick_actions(self, html):
        assert re.search(r'(register|post.*task|browse|export)', html, re.IGNORECASE)

    # --- Shared storage ---

    def test_uses_agents_storage(self, html):
        assert 'agentzoo-agents' in html

    def test_uses_tasks_storage(self, html):
        assert 'agentzoo-tasks' in html

    def test_uses_messages_storage(self, html):
        assert 'agentzoo-messages' in html

    def test_uses_reputation_storage(self, html):
        assert 'agentzoo-reputation' in html

    def test_minimum_size(self, html):
        lines = html.count('\n')
        assert lines > 400, f"Only {lines} lines — hub needs >= 400"


# ─── Moltbook Compatibility ──────────────────────────────────

class TestMoltbookCompatibility:
    """AgentZoo must not break existing RappterZoo/Moltbook functionality."""

    def test_all_apps_have_rappterzoo_tags(self):
        """Every AgentZoo app must have full rappterzoo:* meta tags."""
        required = ['author', 'author-type', 'category', 'tags', 'type', 'complexity', 'created', 'generation']
        for name, path in AGENTZOO_APPS.items():
            html = read_file(path)
            for tag in required:
                assert f'rappterzoo:{tag}' in html, f"{name} missing rappterzoo:{tag}"

    def test_no_storage_conflicts(self):
        """AgentZoo storage keys must not overlap with cryptozoo or rappterzoo."""
        conflict_prefixes = ['cryptozoo-', 'rappterzoo-']
        for key in SHARED_STORAGE_KEYS:
            for prefix in conflict_prefixes:
                assert not key.startswith(prefix), f"Storage key {key} conflicts with {prefix}"

    def test_manifest_entries_exist(self):
        """All 4 AgentZoo apps must be in manifest.json."""
        manifest_path = os.path.join(APPS_DIR, 'manifest.json')
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        exp_apps = manifest['categories']['experimental_ai']['apps']
        filenames = [a['file'] for a in exp_apps]
        for name, path in AGENTZOO_APPS.items():
            filename = os.path.basename(path)
            assert filename in filenames, f"{filename} not found in manifest"

    def test_manifest_count_includes_new_apps(self):
        """Manifest count must include the new AgentZoo apps."""
        manifest_path = os.path.join(APPS_DIR, 'manifest.json')
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        count = manifest['categories']['experimental_ai']['count']
        num_apps = len(manifest['categories']['experimental_ai']['apps'])
        assert count == num_apps, f"Count {count} != actual apps {num_apps}"

    def test_all_files_exist_on_disk(self):
        """Every AgentZoo app file must exist on disk."""
        for name, path in AGENTZOO_APPS.items():
            assert os.path.isfile(path), f"File missing: {path}"
