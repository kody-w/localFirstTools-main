"""Tests for CryptoZoo + AgentZoo Economy Crossover apps.

Validates all three economy bridge apps meet RappterZoo conventions and
contain the required cross-suite functionality:
  - agentzoo-wallet-bridge.html  (identity bridge + wallet link)
  - agentzoo-bounty-board.html   (task marketplace + escrow)
  - agentzoo-economy.html        (economy analytics dashboard)
"""
import os
import re
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
APPS_DIR = os.path.join(REPO_ROOT, 'apps')
BRIDGE_PATH = os.path.join(APPS_DIR, 'experimental-ai', 'agentzoo-wallet-bridge.html')
BOUNTY_PATH = os.path.join(APPS_DIR, 'experimental-ai', 'agentzoo-bounty-board.html')
ECONOMY_PATH = os.path.join(APPS_DIR, 'experimental-ai', 'agentzoo-economy.html')

ECONOMY_APPS = {
    'bridge': BRIDGE_PATH,
    'bounty': BOUNTY_PATH,
    'economy': ECONOMY_PATH,
}


def read_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


# ─── Shared Convention Tests (all 3 economy apps) ─────────────

class TestEconomyConventions:
    """All economy apps must meet RappterZoo HTML app conventions."""

    @pytest.fixture(params=[
        pytest.param('bridge', id='wallet-bridge'),
        pytest.param('bounty', id='bounty-board'),
        pytest.param('economy', id='economy-dashboard'),
    ])
    def app_html(self, request):
        return read_file(ECONOMY_APPS[request.param])

    def test_file_exists(self, app_html):
        assert len(app_html) > 0

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

    def test_has_rappterzoo_author(self, app_html):
        assert 'rappterzoo:author' in app_html

    def test_has_rappterzoo_category(self, app_html):
        m = re.search(r'rappterzoo:category.*?content="([^"]+)"', app_html)
        assert m and m.group(1) == 'experimental-ai'

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

    def test_has_identity_bridge_functions(self, app_html):
        """All economy apps must have az-to-zoo address conversion."""
        assert re.search(r'azToZoo', app_html), "Must have azToZoo function"
        assert re.search(r'zooToAz', app_html), "Must have zooToAz function"

    def test_no_raw_script_close_in_js(self, app_html):
        script_blocks = re.findall(r'<script[^>]*>(.*?)</script>', app_html, re.DOTALL)
        for block in script_blocks:
            assert '</script>' not in block, "Raw </script> in JS — escape as <\\/script>"


# ─── Wallet Bridge Tests ──────────────────────────────────────

class TestWalletBridge:
    """Wallet bridge must link az- identity to zoo1 wallet."""

    @pytest.fixture
    def html(self):
        return read_file(BRIDGE_PATH)

    def test_file_exists(self):
        assert os.path.isfile(BRIDGE_PATH)

    def test_has_address_derivation(self, html):
        """Must derive zoo1 address from public key via SHA-256."""
        assert re.search(r'deriveZooAddress', html)

    def test_reads_agentzoo_active(self, html):
        """Must read currently active agent."""
        assert 'agentzoo-active' in html

    def test_reads_agentzoo_agents(self, html):
        """Must read agent registry."""
        assert 'agentzoo-agents' in html

    def test_reads_cryptozoo_wallet(self, html):
        """Must read CryptoZoo wallet for key linking."""
        assert 'cryptozoo-wallet' in html

    def test_reads_cryptozoo_utxos(self, html):
        """Must read UTXOs for balance."""
        assert 'cryptozoo-utxos' in html

    def test_has_balance_display(self, html):
        """Must show ZooCoin balance."""
        assert re.search(r'balance', html, re.IGNORECASE)

    def test_has_send_functionality(self, html):
        """Must allow sending ZooCoin by az- ID."""
        assert re.search(r'(send|transfer)', html, re.IGNORECASE)

    def test_has_receive_functionality(self, html):
        """Must show receive address."""
        assert re.search(r'receive', html, re.IGNORECASE)

    def test_has_transaction_history(self, html):
        """Must show filtered transaction history."""
        assert re.search(r'history', html, re.IGNORECASE)

    def test_has_link_wallet_setup(self, html):
        """Must have wallet linking/setup flow."""
        assert re.search(r'(link|setup|connect)', html, re.IGNORECASE)

    def test_has_identity_card(self, html):
        """Must display unified identity card (az- + zoo1)."""
        assert re.search(r'az-', html) and re.search(r'zoo1', html)

    def test_writes_cryptozoo_mempool(self, html):
        """Must write to mempool for outgoing transactions."""
        assert 'cryptozoo-mempool' in html

    def test_minimum_size(self, html):
        lines = html.count('\n')
        assert lines > 500, f"Only {lines} lines — wallet bridge needs 500+"


# ─── Bounty Board Tests ──────────────────────────────────────

class TestBountyBoard:
    """Bounty board must have ZooCoin escrow and real payments."""

    @pytest.fixture
    def html(self):
        return read_file(BOUNTY_PATH)

    def test_file_exists(self):
        assert os.path.isfile(BOUNTY_PATH)

    def test_has_escrow_system(self, html):
        """Must implement escrow for bounty payments."""
        assert re.search(r'escrow', html, re.IGNORECASE)

    def test_has_escrow_storage_key(self, html):
        """Must use agentzoo-escrow localStorage key."""
        assert 'agentzoo-escrow' in html

    def test_reads_agentzoo_tasks(self, html):
        """Must read task marketplace."""
        assert 'agentzoo-tasks' in html

    def test_reads_agentzoo_reputation(self, html):
        """Must read reputation for poster display."""
        assert 'agentzoo-reputation' in html

    def test_reads_cryptozoo_utxos(self, html):
        """Must check balance before posting bounty."""
        assert 'cryptozoo-utxos' in html

    def test_has_post_bounty_flow(self, html):
        """Must allow posting new bounties."""
        assert re.search(r'(post.*bounty|create.*bounty|new.*bounty)', html, re.IGNORECASE)

    def test_has_claim_flow(self, html):
        """Must allow claiming bounties."""
        assert re.search(r'claim', html, re.IGNORECASE)

    def test_has_verify_release_flow(self, html):
        """Must verify work and release payment."""
        assert re.search(r'(verify|release)', html, re.IGNORECASE)

    def test_has_refund_flow(self, html):
        """Must support refunding abandoned bounties."""
        assert re.search(r'refund', html, re.IGNORECASE)

    def test_has_capability_check(self, html):
        """Must check agent capabilities before allowing claims."""
        assert re.search(r'capabilit', html, re.IGNORECASE)

    def test_has_bounty_stats(self, html):
        """Must show stats bar (open bounties, ZOO in escrow, completed)."""
        assert re.search(r'(open.*bounti|in.*escrow|completed)', html, re.IGNORECASE)

    def test_writes_cryptozoo_mempool(self, html):
        """Must create blockchain tx when releasing payment."""
        assert 'cryptozoo-mempool' in html

    def test_minimum_size(self, html):
        lines = html.count('\n')
        assert lines > 500, f"Only {lines} lines — bounty board needs 500+"


# ─── Economy Dashboard Tests ─────────────────────────────────

class TestEconomyDashboard:
    """Economy dashboard must show analytics and leaderboards."""

    @pytest.fixture
    def html(self):
        return read_file(ECONOMY_PATH)

    def test_file_exists(self):
        assert os.path.isfile(ECONOMY_PATH)

    def test_uses_chart_js(self, html):
        """Must use Chart.js CDN for visualizations."""
        assert re.search(r'chart\.js', html, re.IGNORECASE)

    def test_is_read_only(self, html):
        """Dashboard must be read-only — no setItem calls (except Chart.js internals)."""
        # Extract script blocks and check for setItem (excluding CDN scripts)
        script_blocks = re.findall(r'<script>(.*?)<\/script>', html, re.DOTALL)
        for block in script_blocks:
            assert 'localStorage.setItem' not in block, "Economy dashboard should be read-only"

    def test_has_network_stats(self, html):
        """Must show total agents, supply, active bounties."""
        assert re.search(r'(agents|agent.*count|total.*agent)', html, re.IGNORECASE)

    def test_has_earnings_breakdown(self, html):
        """Must show earnings by category (tasks, mining, transfers)."""
        assert re.search(r'earning', html, re.IGNORECASE)

    def test_has_leaderboard(self, html):
        """Must have reputation-weighted leaderboard."""
        assert re.search(r'leaderboard', html, re.IGNORECASE)

    def test_has_gini_coefficient(self, html):
        """Must calculate wealth concentration."""
        assert re.search(r'gini', html, re.IGNORECASE)

    def test_has_transaction_velocity(self, html):
        """Must track transaction velocity (tx/day)."""
        assert re.search(r'velocit', html, re.IGNORECASE)

    def test_reads_agentzoo_escrow(self, html):
        assert 'agentzoo-escrow' in html

    def test_reads_cryptozoo_chain(self, html):
        assert 'cryptozoo-chain' in html

    def test_reads_cryptozoo_utxos(self, html):
        assert 'cryptozoo-utxos' in html

    def test_reads_agentzoo_agents(self, html):
        assert 'agentzoo-agents' in html

    def test_reads_agentzoo_reputation(self, html):
        assert 'agentzoo-reputation' in html

    def test_minimum_size(self, html):
        lines = html.count('\n')
        assert lines > 400, f"Only {lines} lines — economy dashboard needs 400+"
