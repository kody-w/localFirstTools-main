"""Tests for CryptoZoo blockchain platform apps.

Validates all CryptoZoo suite apps meet RappterZoo conventions and contain
the required cryptographic, blockchain, and financial functionality.

Apps tested:
  - cryptozoo-network.html  (core blockchain node)
  - cryptozoo-wallet.html   (dedicated wallet)
  - cryptozoo-exchange.html (DEX order book)
  - cryptozoo-explorer.html (block explorer)
  - datazoo-hub.html        (platform hub portal)
"""
import os
import re
import json
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
APPS_DIR = os.path.join(REPO_ROOT, 'apps')
CRYPTOZOO_PATH = os.path.join(APPS_DIR, 'experimental-ai', 'cryptozoo-network.html')
WALLET_PATH = os.path.join(APPS_DIR, 'experimental-ai', 'cryptozoo-wallet.html')
EXCHANGE_PATH = os.path.join(APPS_DIR, 'experimental-ai', 'cryptozoo-exchange.html')
EXPLORER_PATH = os.path.join(APPS_DIR, 'experimental-ai', 'cryptozoo-explorer.html')
DATAZOO_HUB_PATH = os.path.join(APPS_DIR, 'creative-tools', 'datazoo-hub.html')

# All CryptoZoo suite apps
CRYPTO_APPS = {
    'network': CRYPTOZOO_PATH,
    'wallet': WALLET_PATH,
    'exchange': EXCHANGE_PATH,
    'explorer': EXPLORER_PATH,
}

# Shared localStorage keys that bind the suite together
SHARED_STORAGE_KEYS = [
    'cryptozoo-chain',
    'cryptozoo-wallet',
    'cryptozoo-utxos',
    'cryptozoo-mempool',
]


def read_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


# ─── Shared Convention Tests (all CryptoZoo apps + DataZoo Hub) ─

class TestAppConventions:
    """All apps must meet RappterZoo HTML app conventions."""

    @pytest.fixture(params=[
        pytest.param('network', id='cryptozoo-network'),
        pytest.param('wallet', id='cryptozoo-wallet'),
        pytest.param('exchange', id='cryptozoo-exchange'),
        pytest.param('explorer', id='cryptozoo-explorer'),
        pytest.param('datazoo-hub', id='datazoo-hub'),
    ])
    def app_html(self, request):
        if request.param == 'datazoo-hub':
            return read_file(DATAZOO_HUB_PATH)
        return read_file(CRYPTO_APPS[request.param])

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
            # Raw </script> in JS would prematurely close the tag
            assert '</script>' not in block, "Raw </script> found in JS — escape as <\\/script>"


# ─── CryptoZoo Network: Core Blockchain Node ────────────────────

class TestCryptoZooNetwork:
    """Core node must have real cryptography, UTXO model, merkle trees."""

    @pytest.fixture
    def html(self):
        return read_file(CRYPTOZOO_PATH)

    def test_file_exists(self):
        assert os.path.isfile(CRYPTOZOO_PATH)

    # --- Crypto foundations ---

    def test_uses_web_crypto_api(self, html):
        """Must use crypto.subtle for real cryptographic operations."""
        assert 'crypto.subtle' in html, "Must use Web Crypto API (crypto.subtle)"

    def test_has_ecdsa_signing(self, html):
        """Must use ECDSA for transaction signing."""
        assert re.search(r'ECDSA', html), "Must reference ECDSA algorithm"

    def test_has_sha256_hashing(self, html):
        """Must use SHA-256 for block hashing."""
        assert re.search(r'SHA-256', html), "Must reference SHA-256"

    def test_has_merkle_tree(self, html):
        """Must compute merkle root for transaction integrity."""
        assert re.search(r'merkle', html, re.IGNORECASE), "Must have merkle tree implementation"

    def test_has_merkle_root_in_block(self, html):
        """Block structure must include merkleRoot field."""
        assert 'merkleRoot' in html, "Blocks must contain merkleRoot"

    # --- UTXO model ---

    def test_has_utxo_model(self, html):
        """Must implement UTXO (unspent transaction output) model."""
        assert re.search(r'utxo', html, re.IGNORECASE), "Must implement UTXO model"

    def test_has_transaction_inputs_outputs(self, html):
        """Transactions must have inputs and outputs arrays."""
        assert re.search(r'(inputs|txInputs)', html), "Transactions need inputs"
        assert re.search(r'(outputs|txOutputs)', html), "Transactions need outputs"

    # --- Blockchain ---

    def test_has_blockchain_data_structure(self, html):
        assert re.search(r'(blockchain|chain|blocks)\s*[=:\[]', html, re.IGNORECASE)

    def test_has_block_structure(self, html):
        for field in ['index', 'timestamp', 'prevHash', 'nonce']:
            assert field in html, f"Block missing field: {field}"

    def test_has_genesis_block(self, html):
        assert re.search(r"(genesis|'0'\.repeat\(64\)|\"0\"\.repeat\(64\))", html, re.IGNORECASE)

    def test_has_chain_validation(self, html):
        """Must validate the chain (hash linkage, merkle roots, signatures)."""
        assert re.search(r'(isValidChain|validateChain|verifyChain)', html)

    # --- Mining ---

    def test_has_proof_of_work(self, html):
        assert 'nonce' in html
        assert re.search(r'difficulty', html, re.IGNORECASE)

    def test_has_difficulty_adjustment(self, html):
        assert re.search(r'(adjustDifficulty|DIFFICULTY_ADJUST)', html)

    def test_has_halving(self, html):
        assert re.search(r'(halving|HALVING)', html, re.IGNORECASE)

    def test_has_max_supply(self, html):
        assert re.search(r'(MAX_SUPPLY|maxSupply|21[,_]?000[,_]?000)', html)

    # --- Wallet ---

    def test_has_key_pair_generation(self, html):
        """Must generate ECDSA key pairs via Web Crypto API."""
        assert re.search(r'generateKey', html), "Must use crypto.subtle.generateKey"

    def test_has_key_export(self, html):
        """Must export keys as JWK for localStorage persistence."""
        assert re.search(r'(exportKey|jwk|JWK)', html), "Must export keys as JWK"

    def test_has_transaction_signing(self, html):
        """Must sign transactions with private key."""
        assert re.search(r'(\.sign\(|signTransaction|signTx)', html)

    def test_has_signature_verification(self, html):
        """Must verify transaction signatures."""
        assert re.search(r'(\.verify\(|verifySignature|verifySig)', html)

    # --- Shared storage ---

    def test_uses_shared_chain_key(self, html):
        """Must use cryptozoo-chain localStorage key for cross-app compatibility."""
        assert 'cryptozoo-chain' in html

    def test_uses_shared_wallet_key(self, html):
        assert 'cryptozoo-wallet' in html

    def test_uses_shared_mempool_key(self, html):
        assert 'cryptozoo-mempool' in html

    # --- UI ---

    def test_has_zoocoin_branding(self, html):
        assert re.search(r'(ZooCoin|ZOO)', html)

    def test_has_block_explorer_view(self, html):
        assert re.search(r'(explorer|block.*view)', html, re.IGNORECASE)

    def test_has_mempool(self, html):
        assert re.search(r'(mempool|pending)', html, re.IGNORECASE)

    def test_has_import_export(self, html):
        assert re.search(r'(export|import|backup)', html, re.IGNORECASE)

    def test_has_network_nodes(self, html):
        assert re.search(r'(node|peer|network)', html, re.IGNORECASE)

    def test_minimum_size(self, html):
        lines = html.count('\n')
        assert lines > 800, f"Only {lines} lines — core node needs ≥800"

    def test_category_is_experimental_ai(self, html):
        m = re.search(r'rappterzoo:category.*?content="([^"]+)"', html)
        assert m and m.group(1) == 'experimental-ai'


# ─── CryptoZoo Wallet ──────────────────────────────────────────

class TestCryptoZooWallet:
    """Dedicated wallet for key management, signing, and balance."""

    @pytest.fixture
    def html(self):
        return read_file(WALLET_PATH)

    def test_file_exists(self):
        assert os.path.isfile(WALLET_PATH)

    def test_has_ecdsa_key_generation(self, html):
        """Must generate ECDSA key pairs."""
        assert re.search(r'(generateKey|ECDSA)', html)

    def test_has_key_import_export(self, html):
        """Must import/export keys as JWK."""
        assert re.search(r'(exportKey|importKey|JWK|jwk)', html)

    def test_has_address_derivation(self, html):
        """Must derive address from public key."""
        assert re.search(r'(address|deriveAddress|publicKey)', html, re.IGNORECASE)

    def test_has_transaction_creation(self, html):
        """Must create and sign transactions."""
        assert re.search(r'(transaction|createTx|sendTx)', html, re.IGNORECASE)

    def test_has_balance_display(self, html):
        """Must show UTXO-based balance."""
        assert re.search(r'balance', html, re.IGNORECASE)

    def test_has_address_book(self, html):
        """Must have address book or contact management."""
        assert re.search(r'(address.?book|contact|recipient)', html, re.IGNORECASE)

    def test_has_transaction_history(self, html):
        """Must display transaction history."""
        assert re.search(r'(history|transaction.*list|recent)', html, re.IGNORECASE)

    def test_uses_shared_storage_keys(self, html):
        """Must share localStorage with other CryptoZoo apps."""
        assert 'cryptozoo-wallet' in html
        assert 'cryptozoo-chain' in html

    def test_has_backup_restore(self, html):
        """Must support key backup/restore."""
        assert re.search(r'(backup|restore|export|import)', html, re.IGNORECASE)

    def test_minimum_size(self, html):
        lines = html.count('\n')
        assert lines > 400, f"Only {lines} lines — wallet needs ≥400"

    def test_category_is_experimental_ai(self, html):
        m = re.search(r'rappterzoo:category.*?content="([^"]+)"', html)
        assert m and m.group(1) == 'experimental-ai'

    def test_has_zoocoin_branding(self, html):
        assert re.search(r'(ZooCoin|ZOO)', html)


# ─── CryptoZoo Exchange ────────────────────────────────────────

class TestCryptoZooExchange:
    """DEX with order book, matching, and trade history."""

    @pytest.fixture
    def html(self):
        return read_file(EXCHANGE_PATH)

    def test_file_exists(self):
        assert os.path.isfile(EXCHANGE_PATH)

    def test_has_order_book(self, html):
        """Must implement an order book with buy/sell orders."""
        assert re.search(r'(order.?book|orderBook|orders)', html, re.IGNORECASE)

    def test_has_buy_sell_orders(self, html):
        """Must support both buy and sell orders."""
        assert re.search(r'buy', html, re.IGNORECASE)
        assert re.search(r'sell', html, re.IGNORECASE)

    def test_has_match_engine(self, html):
        """Must have order matching logic."""
        assert re.search(r'(match|fill|execute)', html, re.IGNORECASE)

    def test_has_trade_history(self, html):
        """Must display completed trade history."""
        assert re.search(r'(trade.*history|completed.*trade|recent.*trade)', html, re.IGNORECASE)

    def test_has_price_display(self, html):
        """Must show current price or last trade price."""
        assert re.search(r'price', html, re.IGNORECASE)

    def test_has_canvas_or_chart(self, html):
        """Must have price chart visualization."""
        assert re.search(r'(canvas|chart|graph)', html, re.IGNORECASE)

    def test_uses_shared_storage_keys(self, html):
        """Must share localStorage with other CryptoZoo apps."""
        assert 'cryptozoo-chain' in html
        assert 'cryptozoo-orders' in html

    def test_has_wallet_integration(self, html):
        """Must read wallet balance for trading."""
        assert re.search(r'(wallet|balance|cryptozoo-wallet)', html, re.IGNORECASE)

    def test_minimum_size(self, html):
        lines = html.count('\n')
        assert lines > 400, f"Only {lines} lines — exchange needs ≥400"

    def test_category_is_experimental_ai(self, html):
        m = re.search(r'rappterzoo:category.*?content="([^"]+)"', html)
        assert m and m.group(1) == 'experimental-ai'

    def test_has_zoocoin_branding(self, html):
        assert re.search(r'(ZooCoin|ZOO)', html)


# ─── CryptoZoo Explorer ────────────────────────────────────────

class TestCryptoZooExplorer:
    """Block explorer with chain browsing and merkle verification."""

    @pytest.fixture
    def html(self):
        return read_file(EXPLORER_PATH)

    def test_file_exists(self):
        assert os.path.isfile(EXPLORER_PATH)

    def test_has_block_browsing(self, html):
        """Must display individual blocks with details."""
        assert re.search(r'(block.*detail|block.*info|block.*view)', html, re.IGNORECASE)

    def test_has_transaction_browsing(self, html):
        """Must display transaction details."""
        assert re.search(r'(transaction.*detail|tx.*detail|transaction.*view)', html, re.IGNORECASE)

    def test_has_address_lookup(self, html):
        """Must look up address balances and transaction history."""
        assert re.search(r'(address.*lookup|address.*search|address.*view)', html, re.IGNORECASE)

    def test_has_search(self, html):
        """Must have search by hash, address, or block number."""
        assert re.search(r'search', html, re.IGNORECASE)

    def test_has_chain_stats(self, html):
        """Must display chain statistics."""
        assert re.search(r'(stats|statistics|chain.*height|total.*supply)', html, re.IGNORECASE)

    def test_has_merkle_verification(self, html):
        """Must verify or display merkle proofs."""
        assert re.search(r'merkle', html, re.IGNORECASE)

    def test_uses_shared_chain_key(self, html):
        """Must read the shared blockchain from localStorage."""
        assert 'cryptozoo-chain' in html

    def test_minimum_size(self, html):
        lines = html.count('\n')
        assert lines > 400, f"Only {lines} lines — explorer needs ≥400"

    def test_category_is_experimental_ai(self, html):
        m = re.search(r'rappterzoo:category.*?content="([^"]+)"', html)
        assert m and m.group(1) == 'experimental-ai'

    def test_has_zoocoin_branding(self, html):
        assert re.search(r'(ZooCoin|ZOO)', html)


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
        assert re.search(r'RappterZoo', html)

    def test_references_cryptozoo(self, html):
        assert re.search(r'CryptoZoo', html)

    def test_has_dimension_cards_or_sections(self, html):
        assert re.search(r'(dimension|portal|realm|zone)', html, re.IGNORECASE)

    def test_has_platform_stats(self, html):
        assert re.search(r'(stats|statistics|metric|count)', html, re.IGNORECASE)

    def test_has_navigation_links(self, html):
        assert re.search(r'(href|navigate|link|portal)', html, re.IGNORECASE)

    def test_category_is_creative_tools(self, html):
        m = re.search(r'rappterzoo:category.*?content="([^"]+)"', html)
        assert m and m.group(1) == 'creative-tools'

    def test_minimum_size(self, html):
        lines = html.count('\n')
        assert lines > 200, f"Only {lines} lines — too small for a platform hub"
