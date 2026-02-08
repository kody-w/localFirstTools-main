"""Tests for DataZoo platform apps: CryptoZoo Network + DataZoo Hub.

Validates both HTML apps meet RappterZoo conventions and contain
required functionality.
"""
import os
import re
import json
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CRYPTOZOO_PATH = os.path.join(REPO_ROOT, 'apps', 'experimental-ai', 'cryptozoo-network.html')
DATAZOO_HUB_PATH = os.path.join(REPO_ROOT, 'apps', 'creative-tools', 'datazoo-hub.html')


def read_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


# ─── Shared Convention Tests ────────────────────────────────────

class TestAppConventions:
    """Both apps must meet RappterZoo HTML app conventions."""

    @pytest.fixture(params=[
        pytest.param('cryptozoo', id='cryptozoo'),
        pytest.param('datazoo-hub', id='datazoo-hub'),
    ])
    def app_html(self, request):
        path = CRYPTOZOO_PATH if request.param == 'cryptozoo' else DATAZOO_HUB_PATH
        return read_file(path)

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


# ─── CryptoZoo-Specific Tests ──────────────────────────────────

class TestCryptoZooNetwork:
    """CryptoZoo must have blockchain, mining, wallet, and transaction features."""

    @pytest.fixture
    def html(self):
        return read_file(CRYPTOZOO_PATH)

    def test_file_exists(self):
        assert os.path.isfile(CRYPTOZOO_PATH)

    def test_has_blockchain_data_structure(self, html):
        """Must define a blockchain/chain array or class."""
        assert re.search(r'(blockchain|chain|blocks)\s*[=:]', html, re.IGNORECASE)

    def test_has_block_structure(self, html):
        """Blocks must have index, timestamp, hash, previousHash."""
        for field in ['index', 'timestamp', 'hash', 'previousHash']:
            assert field in html, f"Block missing field: {field}"

    def test_has_mining_logic(self, html):
        """Must have proof-of-work mining with nonce/difficulty."""
        assert 'nonce' in html
        assert re.search(r'difficulty', html, re.IGNORECASE)

    def test_has_hash_computation(self, html):
        """Must compute SHA-256 hashes (Web Crypto or manual)."""
        assert re.search(r'(SHA-256|sha256|crypto\.subtle)', html, re.IGNORECASE)

    def test_has_wallet_system(self, html):
        """Must have wallet with address and balance."""
        assert re.search(r'wallet', html, re.IGNORECASE)
        assert re.search(r'(address|balance)', html, re.IGNORECASE)

    def test_has_transactions(self, html):
        """Must support creating transactions."""
        assert re.search(r'transaction', html, re.IGNORECASE)

    def test_has_genesis_block(self, html):
        """Must create a genesis block."""
        assert re.search(r'genesis', html, re.IGNORECASE)

    def test_has_zoocoin_branding(self, html):
        """Must reference ZooCoin or ZOO token."""
        assert re.search(r'(ZooCoin|ZOO)', html)

    def test_has_block_explorer_view(self, html):
        """Must have a block explorer or chain viewer."""
        assert re.search(r'(explorer|block.*view|chain.*view|block.*list)', html, re.IGNORECASE)

    def test_has_mining_button_or_trigger(self, html):
        """Must have UI to trigger mining."""
        assert re.search(r'(mine|mining)', html, re.IGNORECASE)

    def test_has_network_nodes(self, html):
        """Must simulate network nodes or peers."""
        assert re.search(r'(node|peer|network)', html, re.IGNORECASE)

    def test_has_mempool(self, html):
        """Must have a pending transaction pool."""
        assert re.search(r'(mempool|pending)', html, re.IGNORECASE)

    def test_has_import_export(self, html):
        """Must support blockchain data import/export."""
        assert re.search(r'(export|import|download|backup)', html, re.IGNORECASE)

    def test_minimum_size(self, html):
        """Crypto network app should be substantial (>500 lines)."""
        lines = html.count('\n')
        assert lines > 500, f"Only {lines} lines — too small for a crypto network"

    def test_category_is_experimental_ai(self, html):
        m = re.search(r'rappterzoo:category.*?content="([^"]+)"', html)
        assert m and m.group(1) == 'experimental-ai'


# ─── DataZoo Hub-Specific Tests ─────────────────────────────────

class TestDataZooHub:
    """DataZoo Hub must be a portal linking zoo dimensions."""

    @pytest.fixture
    def html(self):
        return read_file(DATAZOO_HUB_PATH)

    def test_file_exists(self):
        assert os.path.isfile(DATAZOO_HUB_PATH)

    def test_has_datazoo_branding(self, html):
        assert re.search(r'DataZoo', html)

    def test_references_rappterzoo(self, html):
        """Must link/reference the RappterZoo dimension."""
        assert re.search(r'RappterZoo', html)

    def test_references_cryptozoo(self, html):
        """Must link/reference the CryptoZoo dimension."""
        assert re.search(r'CryptoZoo', html)

    def test_has_dimension_cards_or_sections(self, html):
        """Must show zoo dimensions as distinct sections."""
        assert re.search(r'(dimension|portal|realm|zone)', html, re.IGNORECASE)

    def test_has_platform_stats(self, html):
        """Must display platform-wide statistics."""
        assert re.search(r'(stats|statistics|metric|count)', html, re.IGNORECASE)

    def test_has_navigation_links(self, html):
        """Must have navigation to child dimensions."""
        assert re.search(r'(href|navigate|link|portal)', html, re.IGNORECASE)

    def test_category_is_creative_tools(self, html):
        m = re.search(r'rappterzoo:category.*?content="([^"]+)"', html)
        assert m and m.group(1) == 'creative-tools'

    def test_minimum_size(self, html):
        """Hub should be a meaningful app (>200 lines)."""
        lines = html.count('\n')
        assert lines > 200, f"Only {lines} lines — too small for a platform hub"
