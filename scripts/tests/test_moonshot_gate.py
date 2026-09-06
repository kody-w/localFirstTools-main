"""Mutation and end-to-end tests for the Organism Observatory moonshot gate."""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import moonshot_gate as gate


FIXTURE_COMPONENT_CSS = """
* { box-sizing: border-box; }
html, body { margin: 0; max-width: 100%; background: var(--cp-bg); color: var(--cp-text); }
body { font-family: "Segoe UI", Aptos, Calibri, -apple-system, BlinkMacSystemFont, sans-serif; }
main { width: min(72rem, 100%); margin: 0 auto; padding: 1rem; }
.controls { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(12rem, 100%), 1fr)); gap: 0.5rem; }
.panel { border: 1px solid var(--cp-border); background: var(--cp-surface); padding: 1rem; }
button, input, select { min-height: 44px; border: 1px solid var(--cp-border); background: var(--cp-surface); color: var(--cp-text); }
:focus-visible { outline: 3px solid var(--cp-accent); }
@media (max-width: 480px) { main { width: min(100%, 390px); padding: 0.5rem; } }
@media (prefers-reduced-motion: reduce) { * { transition-duration: 0s; } }
"""

FIXTURE_SCRIPT = r"""
"use strict";
const mode = document.getElementById("kindMode");
const filter = document.getElementById("searchInput");
const list = document.getElementById("items");
const status = document.getElementById("integrity");
const exportButton = document.getElementById("exportButton");
const tamperButton = document.getElementById("tamperButton");
const restoreButton = document.getElementById("restoreButton");
const playButton = document.getElementById("playButton");
const fileInput = document.getElementById("fileInput");
let frames = [];
let organisms = [];
let playing = false;
let lastTick = performance.now();
let elapsed = 0;

function render() {
  const query = filter.value.trim().toLowerCase();
  const values = mode.value === "organisms"
    ? organisms
    : frames.map((frame) => frame.kind + " " + frame.payload.event_id);
  list.textContent = "";
  values.filter((value) => value.toLowerCase().includes(query)).forEach((value) => {
    const row = document.createElement("div");
    row.dataset.frame = "true";
    row.textContent = value;
    list.appendChild(row);
  });
}

function animationLoop(now) {
  const delta = now - lastTick;
  lastTick = now;
  if (playing) {
    elapsed += delta;
    document.body.dataset.playhead = String(Math.floor(elapsed));
  }
  requestAnimationFrame(animationLoop);
}

function exportData() {
  const blob = new Blob([JSON.stringify({ frames })], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "organism-observatory.json";
  anchor.click();
}

mode.addEventListener("change", render);
filter.addEventListener("input", render);
tamperButton.addEventListener("click", () => { status.textContent = "DRIFT"; });
restoreButton.addEventListener("click", () => { status.textContent = "VALID"; });
exportButton.addEventListener("click", exportData);
playButton.addEventListener("click", () => {
  playing = !playing;
  playButton.setAttribute("aria-pressed", String(playing));
});
fileInput.addEventListener("change", async () => {
  if (fileInput.files[0]) await fileInput.files[0].text();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "ArrowRight") mode.value = "organisms";
});

Promise.all([
  fetch("../organism-frames.jsonl").then((response) => response.text()),
  fetch("../organism-frames.json").then((response) => response.json())
]).then((values) => {
  frames = values[1].frames;
  organisms = values[1].organisms.map((item) => item.id);
  render();
  status.textContent = "VALID";
  document.body.dataset.ready = "true";
  exportButton.disabled = false;
  tamperButton.disabled = false;
  restoreButton.disabled = false;
});
requestAnimationFrame(animationLoop);
"""


def _perfect_html():
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'">
  <script>
  %s
  </script>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Organism Observatory</title>
  <style>
  %s
  %s
  </style>
</head>
<body data-ready="false" data-playhead="0" tabindex="-1">
  <main>
    <h1>Organism Observatory</h1>
    <p>Only public-metadata is rendered. Private GODD media and biometric values are excluded.</p>
    <div id="integrity" data-integrity-status role="status" aria-live="polite">LOADING</div>
    <section class="panel controls" aria-label="Observatory controls">
      <label for="kindMode">View mode</label>
      <select id="kindMode" data-control="mode" aria-label="View mode">
        <option value="frames">Frames</option>
        <option value="organisms">Organisms</option>
      </select>
      <label for="searchInput">Filter frames</label>
      <input id="searchInput" data-control="filter" type="search" aria-label="Filter frames">
      <button id="playButton" type="button" aria-pressed="false">Play playback</button>
      <button id="tamperButton" data-action="tamper" type="button" disabled>Tamper chain</button>
      <button id="restoreButton" data-action="restore" type="button" disabled>Restore ledger</button>
      <button id="exportButton" data-action="export" type="button" disabled>Export JSON</button>
      <label for="fileInput">Import projection</label>
      <input id="fileInput" type="file" accept=".json,.jsonl,application/json,application/x-ndjson" aria-label="Import projection">
      <button id="helpButton" type="button">Keyboard help</button>
    </section>
    <section id="items" class="panel" aria-live="polite"></section>
  </main>
  <script>
  %s
  </script>
</body>
</html>
""" % (
        gate.THEME_SCRIPT,
        gate.THEME_VARIABLES,
        FIXTURE_COMPONENT_CSS,
        FIXTURE_SCRIPT,
    )


def _payload(event_id, event):
    return {
        "schema": "rappterzoo-organism-frame/1",
        "event_id": event_id,
        "event": event,
        "organism": "rappterzoo",
        "display_name": "RappterZoo",
        "organism_type": "neighborhood",
        "neighborhood": "rappterzoo",
        "visibility": "public-metadata",
    }


def _frame(seq, kind, utc, payload, previous):
    frame = {
        "spec": "rapp/1",
        "kind": kind,
        "stream_id": "net:rappterzoo",
        "seq": seq,
        "utc": utc,
        "payload": payload,
        "payload_hash": gate.hash_value(gate.PARTICLE_SPACE, payload),
        "frame_hash": "0" * 64,
        "prev": previous["payload_hash"] if previous else None,
        "prev_wave": previous["frame_hash"] if previous else None,
        "sig": None,
    }
    preimage = {
        key: value
        for key, value in frame.items()
        if key not in {"frame_hash", "sig"}
    }
    frame["frame_hash"] = gate.hash_value(gate.WAVE_SPACE, preimage)
    return frame


def _frames():
    first = _frame(
        0,
        "zoo.snapshot",
        "2026-08-15T17:06:24.449Z",
        _payload("fixture:0", "bootstrap"),
        None,
    )
    second = _frame(
        1,
        "zoo.observation",
        "2026-08-15T17:06:25.449Z",
        _payload("fixture:1", "observation"),
        first,
    )
    return [first, second]


def _write_fixture(root):
    app_dir = root / "apps/3d-immersive"
    well_known = root / ".well-known"
    app_dir.mkdir(parents=True)
    well_known.mkdir()
    (app_dir / "organism-observatory.html").write_text(
        _perfect_html(),
        encoding="utf-8",
    )
    frames = _frames()
    ledger = b"".join(gate.canonical_bytes(frame) + b"\n" for frame in frames)
    (root / gate.LEDGER_RELATIVE).write_bytes(ledger)
    (root / gate.PROJECTION_RELATIVE).write_text(
        json.dumps(gate.expected_projection(frames), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "3d_immersive": {
            "title": "3D & Immersive Worlds",
            "folder": "3d-immersive",
            "count": 1,
            "apps": [
                {
                    "title": "Organism Observatory",
                    "file": "organism-observatory.html",
                    "description": "Verified public organism ledger explorer.",
                    "tags": ["organism", "ledger"],
                }
            ],
        }
    }
    (root / "apps/manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    feed = {
        "dataFeedElement": [
            {
                "item": {
                    "name": "Organism Observatory",
                    "url": (
                        "https://example.test/apps/3d-immersive/"
                        "organism-observatory.html"
                    ),
                }
            }
        ]
    }
    (root / "apps/feed.json").write_text(json.dumps(feed), encoding="utf-8")
    (root / "apps/feed.xml").write_text(
        """<?xml version="1.0"?><rss><channel><item>
<title>Organism Observatory</title>
<link>https://example.test/apps/3d-immersive/organism-observatory.html</link>
<guid>https://example.test/apps/3d-immersive/organism-observatory.html</guid>
</item></channel></rss>""",
        encoding="utf-8",
    )
    (well_known / "feeddata-general").write_text(
        json.dumps(
            {
                "url": "https://example.test/apps/feed.json",
                "contentUrl": "https://example.test/apps/feed.json",
            }
        ),
        encoding="utf-8",
    )
    (well_known / "feeddata-toc").write_text(
        json.dumps(
            {
                "dataset": [
                    {"url": "https://example.test/apps/feed.json"},
                    {"url": "https://example.test/apps/manifest.json"},
                    {"url": "https://example.test/apps/organism-frames.json"},
                    {"url": "https://example.test/apps/organism-frames.jsonl"},
                ],
                "hasPart": {
                    "url": (
                        "https://example.test/apps/3d-immersive/"
                        "organism-observatory.html"
                    )
                },
            }
        ),
        encoding="utf-8",
    )


class FixtureRepo:
    def __enter__(self):
        self.temporary = tempfile.TemporaryDirectory(
            prefix=".moonshot-gate-",
            dir=str(Path(__file__).resolve().parent),
        )
        self.root = Path(self.temporary.name)
        _write_fixture(self.root)
        return self.root

    def __exit__(self, exc_type, exc_value, traceback):
        self.temporary.cleanup()


def _checks(root):
    return {item.name: item for item in gate.run_static_checks(root)}


def _replace(path, old, new):
    source = path.read_text(encoding="utf-8")
    assert old in source
    path.write_text(source.replace(old, new, 1), encoding="utf-8")


def _mutate(root, mutation):
    app = root / gate.APP_RELATIVE
    if mutation == "missing-app":
        app.unlink()
    elif mutation == "theme-script":
        _replace(app, 'get("scoutTheme")', 'get("otherTheme")')
    elif mutation == "theme-variables":
        _replace(app, "--cp-bg: #f7f4ef", "--cp-bg: #f7f4ee")
    elif mutation == "hardcoded-color":
        _replace(app, "</style>", ".broken { color: #123456; }</style>")
    elif mutation == "dynamic-code":
        _replace(app, '"use strict";', '"use strict"; eval("1");')
    elif mutation == "csp":
        _replace(app, "connect-src 'self'", "connect-src *")
    elif mutation == "data-url":
        _replace(
            app,
            'fetch("../organism-frames.jsonl")',
            'fetch("https://example.test/organism-frames.jsonl")',
        )
    elif mutation == "manifest":
        path = root / "apps/manifest.json"
        _replace(path, "organism-observatory.html", "missing.html")
    elif mutation == "feeds":
        for relative in ("apps/feed.json", "apps/feed.xml"):
            _replace(
                root / relative,
                "organism-observatory.html",
                "missing.html",
            )
    elif mutation == "discovery":
        _replace(
            root / ".well-known/feeddata-toc",
            "organism-frames.jsonl",
            "missing.jsonl",
        )
    elif mutation == "ledger":
        path = root / gate.LEDGER_RELATIVE
        path.write_bytes(path.read_bytes().replace(b"fixture:1", b"fixture:X", 1))
    elif mutation == "projection":
        path = root / gate.PROJECTION_RELATIVE
        value = json.loads(path.read_text(encoding="utf-8"))
        value["total_frame_count"] += 1
        path.write_text(json.dumps(value), encoding="utf-8")
    elif mutation == "privacy":
        path = root / gate.PROJECTION_RELATIVE
        value = json.loads(path.read_text(encoding="utf-8"))
        value["privacy"]["biometric_values"] = "included"
        path.write_text(json.dumps(value), encoding="utf-8")
    elif mutation == "accessibility":
        _replace(app, 'aria-label="Import projection"', "")
        _replace(app, '<label for="fileInput">Import projection</label>', "")
    elif mutation == "io-tamper":
        _replace(app, '"DRIFT"', '"BROKEN"')
    elif mutation == "wall-clock":
        source = app.read_text(encoding="utf-8").replace(
            "performance.now()",
            "Date.now()",
        )
        app.write_text(source, encoding="utf-8")
    elif mutation == "responsive":
        _replace(app, "@media (max-width: 480px)", "@media (max-width: 980px)")
    else:
        raise AssertionError("unknown mutation " + mutation)


@pytest.mark.parametrize(
    "mutation,expected_failure",
    [
        ("missing-app", "app.measurable"),
        ("theme-script", "theme.script"),
        ("theme-variables", "theme.variables"),
        ("hardcoded-color", "styles.token-colors"),
        ("dynamic-code", "security.no-dynamic-code"),
        ("csp", "security.csp"),
        ("data-url", "data.same-origin-urls"),
        ("manifest", "registration.manifest"),
        ("feeds", "registration.feeds"),
        ("discovery", "registration.discovery"),
        ("ledger", "ledger.exact-chain"),
        ("projection", "projection.exact"),
        ("privacy", "privacy.public-only"),
        ("accessibility", "controls.accessibility"),
        ("io-tamper", "controls.io-tamper"),
        ("wall-clock", "playback.wall-clock"),
        ("responsive", "responsive.static"),
    ],
)
def test_static_mutations_turn_major_assertions_red(mutation, expected_failure):
    with FixtureRepo() as root:
        assert all(item.passed for item in gate.run_static_checks(root))
        _mutate(root, mutation)
        checks = _checks(root)
        assert not checks[expected_failure].passed


def test_playwright_absence_is_a_failure_not_a_skip(monkeypatch):
    with FixtureRepo() as root:
        original = shutil.which
        monkeypatch.setattr(
            gate.shutil,
            "which",
            lambda name: None if name == "node" else original(name),
        )
        results = gate.run_browser_checks(root)
        assert results
        assert all(not item.passed for item in results)
        assert all("unavailable" in item.detail for item in results)


def test_missing_playwright_package_is_a_failure_not_a_skip(monkeypatch):
    with FixtureRepo() as root:
        original = gate.subprocess.run

        def missing_playwright(*args, **kwargs):
            command = args[0]
            if "require.resolve('playwright')" in command:
                return subprocess.CompletedProcess(
                    command,
                    1,
                    stdout="",
                    stderr="Cannot find module 'playwright'",
                )
            return original(*args, **kwargs)

        monkeypatch.setattr(gate.subprocess, "run", missing_playwright)
        results = gate.run_browser_checks(root)
        assert results
        assert all(not item.passed for item in results)
        assert all("Playwright is unavailable" in item.detail for item in results)


def _mutate_runtime(root, mutation):
    app = root / gate.APP_RELATIVE
    if mutation == "ready":
        _replace(
            app,
            'status.textContent = "VALID";\n  document.body.dataset.ready = "true";',
            'status.textContent = "LOADING";',
        )
    elif mutation == "console":
        _replace(app, '"use strict";', '"use strict"; console.error("mutation");')
    elif mutation == "playback":
        _replace(
            app,
            "elapsed += delta;",
            "elapsed += 0;",
        )
    elif mutation == "mode-filter":
        _replace(
            app,
            'mode.addEventListener("change", render);',
            'mode.addEventListener("change", () => {});',
        )
    elif mutation == "keyboard":
        source = app.read_text(encoding="utf-8")
        source = source.replace("<button ", '<button tabindex="-1" ')
        source = source.replace("<select ", '<select tabindex="-1" ')
        source = source.replace("<input ", '<input tabindex="-1" ')
        app.write_text(source, encoding="utf-8")
    elif mutation == "tamper":
        _replace(
            app,
            'status.textContent = "DRIFT"',
            'status.textContent = "VALID"',
        )
    elif mutation == "export":
        _replace(
            app,
            'exportButton.addEventListener("click", exportData);',
            'exportButton.addEventListener("click", () => {});',
        )
    elif mutation == "mobile":
        _replace(
            app,
            '<section id="items"',
            '<div data-mobile-mutation style="width: 600px">wide</div><section id="items"',
        )
    else:
        raise AssertionError("unknown runtime mutation " + mutation)


def test_browser_fixture_satisfies_every_runtime_assertion():
    with FixtureRepo() as root:
        results = gate.run_browser_checks(
            root,
            ready_timeout_ms=3000,
            playwright_cwd=REPO_ROOT,
        )
        assert all(item.passed for item in results), {
            item.name: item.detail for item in results if not item.passed
        }


@pytest.mark.parametrize(
    "mutation,expected_failure",
    [
        ("ready", "runtime.ready-network-errors"),
        ("console", "runtime.ready-network-errors"),
        ("playback", "runtime.playback-wall-clock"),
        ("mode-filter", "runtime.mode-filter"),
        ("keyboard", "runtime.keyboard"),
        ("tamper", "runtime.tamper-restore"),
        ("export", "runtime.export"),
        ("mobile", "runtime.mobile-390x844"),
    ],
)
def test_browser_mutations_turn_runtime_assertions_red(
    mutation,
    expected_failure,
):
    with FixtureRepo() as root:
        _mutate_runtime(root, mutation)
        checks = {
            item.name: item
            for item in gate.run_browser_checks(
                root,
                ready_timeout_ms=3000,
                playwright_cwd=REPO_ROOT,
            )
        }
        assert not checks[expected_failure].passed


EXPANDED_SOURCE_FILES = (
    "scripts/rappterzoo_mcp.py",
    "scripts/build_syndication.py",
    "scripts/rappterzoo_sync.py",
    "scripts/attention_portal.py",
    "scripts/organism_ledger.py",
    "skill.md",
    "heartbeat.md",
    "skill.json",
    ".well-known/mcp.json",
    "apps/attention/policy.json",
    "apps/attention/prompt-contract.json",
)


class ExpandedRepo:
    def __enter__(self):
        self.temporary = tempfile.TemporaryDirectory(
            prefix=".moonshot-expanded-",
            dir=str(Path(__file__).resolve().parent),
        )
        self.root = Path(self.temporary.name)
        for relative in EXPANDED_SOURCE_FILES:
            source = REPO_ROOT / relative
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(str(source), str(target))
        return self.root

    def __exit__(self, exc_type, exc_value, traceback):
        self.temporary.cleanup()


class UiRepo:
    def __enter__(self):
        self.temporary = tempfile.TemporaryDirectory(
            prefix=".moonshot-ui-",
            dir=str(Path(__file__).resolve().parent),
        )
        self.root = Path(self.temporary.name)
        for relative in ("index.html", "apps/data-tools/digg.html"):
            source = REPO_ROOT / relative
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(str(source), str(target))
        app_dir = self.root / "apps/demo"
        archive_dir = self.root / "apps/archive"
        app_dir.mkdir(parents=True)
        archive_dir.mkdir(parents=True)
        (app_dir / "fixture.html").write_text(
            """<!DOCTYPE html><html lang="en"><head>
<meta name="viewport" content="width=device-width">
<title>Fixture App</title></head><body><main>Fixture app</main></body></html>""",
            encoding="utf-8",
        )
        manifest = {
            "categories": {
                "demo": {
                    "title": "Demo",
                    "folder": "demo",
                    "color": "#123456",
                    "count": 1,
                    "apps": [{
                        "title": "Fixture App",
                        "file": "fixture.html",
                        "description": "Fixture gallery application.",
                        "tags": ["fixture"],
                        "complexity": "simple",
                        "type": "interactive",
                        "featured": True,
                        "created": "2026-08-15",
                        "generation": 1,
                    }],
                }
            }
        }
        (self.root / "apps/manifest.json").write_text(
            json.dumps(manifest),
            encoding="utf-8",
        )
        (archive_dir / "manifest.json").write_text("{}", encoding="utf-8")
        community = {
            "players": [],
            "comments": {},
            "ratings": {},
            "activity": [],
            "onlineSchedule": {},
        }
        (self.root / "apps/community.json").write_text(
            json.dumps(community),
            encoding="utf-8",
        )
        for name, value in (
            ("ghost-state.json", {}),
            ("agents.json", {"agents": []}),
            ("activity-log.json", []),
        ):
            (self.root / "apps" / name).write_text(
                json.dumps(value),
                encoding="utf-8",
            )
        frames = _frames()
        (self.root / "apps/organism-frames.json").write_text(
            json.dumps(gate.expected_projection(frames)),
            encoding="utf-8",
        )
        (self.root / "apps/organism-frames.jsonl").write_bytes(
            b"".join(gate.canonical_bytes(frame) + b"\n" for frame in frames)
        )
        index = self.root / "index.html"
        source = index.read_text(encoding="utf-8")
        source = source.replace(
            "</style>",
            """@media(max-width:768px){
.sidebar-toggle,.player-chip,.sort-tab,.vote-btn,.post-footer button,
.post-footer a,.sub-link{min-width:44px;min-height:44px}
}
</style>""",
            1,
        )
        index.write_text(source, encoding="utf-8")
        return self.root

    def __exit__(self, exc_type, exc_value, traceback):
        self.temporary.cleanup()


def _repair_static_mcp(root):
    surface = gate._runtime_mcp_surface(root)
    path = root / ".well-known/mcp.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    initialized = surface["initialize"]
    value["protocol_version"] = initialized["protocolVersion"]
    value["server_info"] = initialized["serverInfo"]
    value["tools"] = surface["tools"]
    value["prompts"] = surface["prompts"]
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    package_path = root / "skill.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    package["version"] = initialized["serverInfo"]["version"]
    package_path.write_text(json.dumps(package, indent=2, sort_keys=True) + "\n")


def _repair_first_use_resource(root):
    path = root / "scripts/rappterzoo_mcp.py"
    source = path.read_text(encoding="utf-8")
    marker = 'RESOURCE_MAP = {\n'
    assert marker in source
    source = source.replace(
        marker,
        marker
        + '    "rappterzoo://syndication-index": (\n'
        + '        "apps/syndication/index.json", "application/json"\n'
        + "    ),\n",
        1,
    )
    path.write_text(source, encoding="utf-8")


def _build_syndication_fixture(root):
    builder = gate._load_module(
        root / "scripts/build_syndication.py",
        "test_builder",
    )
    gate._write_build_fixture(root, builder)
    builder.build(root, "https://example.invalid/zoo/")
    return builder


def test_expanded_missing_file_mutation_turns_red():
    with ExpandedRepo() as root:
        _build_syndication_fixture(root)
        assert gate.check_expanded_files(root).passed
        (root / "heartbeat.md").unlink()
        assert not gate.check_expanded_files(root).passed


def test_expanded_mcp_drift_mutation_turns_red():
    with ExpandedRepo() as root:
        _repair_static_mcp(root)
        assert gate.check_mcp_parity(root).passed
        path = root / ".well-known/mcp.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["tools"][0]["name"] = "drifted_tool"
        path.write_text(json.dumps(value))
        assert not gate.check_mcp_parity(root).passed


@pytest.mark.parametrize("mutation", ["metadata", "runtime"])
def test_expanded_default_write_mutation_turns_red(mutation):
    with ExpandedRepo() as root:
        assert gate.check_mcp_writes_default(root).passed
        if mutation == "metadata":
            path = root / "skill.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["moltbot"]["mcp"]["writes_default"] = True
            path.write_text(json.dumps(value))
        else:
            path = root / "scripts/rappterzoo_mcp.py"
            _replace(
                path,
                'writes_enabled = os.environ.get("RAPPTERZOO_MCP_WRITES") == "1"',
                "writes_enabled = True",
            )
        assert not gate.check_mcp_writes_default(root).passed


def test_expanded_first_use_heartbeat_mutation_turns_red():
    with ExpandedRepo() as root:
        _repair_first_use_resource(root)
        assert gate.check_mcp_first_use(root).passed
        path = root / "heartbeat.md"
        _replace(
            path,
            "rappterzoo_sync.py status",
            "sync status unavailable",
        )
        assert not gate.check_mcp_first_use(root).passed


def test_expanded_delta_rewrite_and_feed_id_mutations_turn_red():
    with ExpandedRepo() as root:
        _build_syndication_fixture(root)
        assert gate.check_syndication_chain(root).passed
        assert gate.check_syndication_feed_ids(root).passed
        index = json.loads(
            (root / "apps/syndication/index.json").read_text()
        )
        delta = root / "apps/syndication" / index["deltas"][0]["path"]
        delta.write_bytes(delta.read_bytes() + b" ")
        assert not gate.check_syndication_chain(root).passed
    with ExpandedRepo() as root:
        _build_syndication_fixture(root)
        feed_path = root / "apps/syndication/feed.json"
        feed = json.loads(feed_path.read_text())
        feed["items"][0]["id"] = "urn:sha256:" + ("0" * 64)
        feed_path.write_text(json.dumps(feed))
        assert not gate.check_syndication_feed_ids(root).passed


def test_expanded_non_idempotent_builder_mutation_turns_red():
    with ExpandedRepo() as root:
        assert gate.check_syndication_idempotence(root).passed
        path = root / "scripts/build_syndication.py"
        _replace(
            path,
            "if path.exists() and path.read_bytes() == data:\n"
            "        return False",
            "if False:\n"
            "        return False",
        )
        assert not gate.check_syndication_idempotence(root).passed


@pytest.mark.parametrize("mutation", ["tamper-accept", "overlay-destroy"])
def test_expanded_sync_safety_mutations_turn_red(mutation):
    with ExpandedRepo() as root:
        assert gate.check_sync_adversarial(root).passed
        path = root / "scripts/rappterzoo_sync.py"
        if mutation == "tamper-accept":
            _replace(
                path,
                'if len(data) != entry["size"]:',
                "if False:",
            )
            _replace(
                path,
                'if sha256_bytes(data) != entry["sha256"]:',
                "if False:",
            )
            _replace(
                path,
                "if stable_json_bytes(delta) != data:",
                "if False:",
            )
        else:
            _replace(
                path,
                "effective.update({\n"
                '        row["path"]: row["sha256"]\n'
                "        for row in local_rows\n"
                "    })",
                "effective.update({})",
            )
        assert not gate.check_sync_adversarial(root).passed


def test_expanded_attention_budget_mutation_turns_red():
    with ExpandedRepo() as root:
        assert gate.check_attention_contracts(root).passed
        path = root / "apps/attention/policy.json"
        value = json.loads(path.read_text())
        value["attention_budget"] = value["candidate_budget"] + 1
        path.write_text(json.dumps(value))
        assert not gate.check_attention_contracts(root).passed


def test_expanded_selected_only_lineage_mutation_turns_red():
    with ExpandedRepo() as root:
        assert gate.check_attention_lineage(root).passed
        path = root / "scripts/attention_portal.py"
        _replace(
            path,
            "if not consumed_ids.issubset(selected_ids):",
            "if False:",
        )
        assert not gate.check_attention_lineage(root).passed


@pytest.mark.parametrize("mutation", ["writer-collision", "dimensions"])
def test_expanded_shard_dimension_mutations_turn_red(mutation):
    with ExpandedRepo() as root:
        assert gate.check_attention_shards_dimensions(root).passed
        if mutation == "writer-collision":
            path = root / "scripts/attention_portal.py"
            _replace(
                path,
                "if existing != record:\n"
                "            raise AttentionError(",
                "if False:\n"
                "            raise AttentionError(",
            )
        else:
            path = root / "scripts/build_syndication.py"
            _replace(
                path,
                '"dimension_ids": sorted(set(dimension_ids))',
                '"dimension_ids": []',
            )
        assert not gate.check_attention_shards_dimensions(root).passed


@pytest.mark.parametrize("mutation", ["unauthorized-lease", "live-proof"])
def test_expanded_fold_safety_mutations_turn_red(mutation):
    with ExpandedRepo() as root:
        assert gate.check_fold_safety(root).passed
        path = root / "scripts/build_syndication.py"
        if mutation == "unauthorized-lease":
            source = path.read_text(encoding="utf-8")
            assert '"authorization",' in source
            path.write_text(
                source.replace(
                    '"authorization",',
                    '"notauthorization",',
                ),
                encoding="utf-8",
            )
        else:
            _replace(
                path,
                "if object_kind in synthetic_cycle_kinds "
                "and not synthetic_test_mode:",
                "if False:",
            )
        assert not gate.check_fold_safety(root).passed


def _ui_checks(root):
    return {
        item.name: item
        for item in gate.run_gallery_digg_browser_checks(
            root,
            ready_timeout_ms=6000,
            playwright_cwd=REPO_ROOT,
        )
    }


def test_gallery_bridge_syntax_mutation_turns_red():
    with UiRepo() as root:
        assert gate.check_gallery_bridge_syntax(root).passed
        path = root / "index.html"
        _replace(
            path,
            'else if(cmd==="step"){result=api.step?api.step(e.data.n||1):null}',
            'else if(cmd==="step"){result=api.step?api.step(e.data.n||1):null',
        )
        assert not gate.check_gallery_bridge_syntax(root).passed


def test_gallery_digg_runtime_fixture_passes():
    with UiRepo() as root:
        checks = _ui_checks(root)
        assert all(item.passed for item in checks.values()), {
            name: item.detail
            for name, item in checks.items()
            if not item.passed
        }


@pytest.mark.parametrize(
    "mutation,expected_failure",
    [
        ("offline-cache", "gallery.offline-cache"),
        ("gallery-storage", "gallery.storage-denied"),
        ("voting", "gallery.voting-live"),
        ("mobile-targets", "gallery.mobile-targets"),
        ("gallery-actions", "gallery.mobile-targets"),
        ("bridge-runtime", "gallery.iframe-bridge-runtime"),
        ("digg-storage", "digg.storage-denied"),
        ("digg-canvas", "digg.canvas-accessible-state"),
    ],
)
def test_gallery_digg_runtime_mutations_turn_red(
    mutation,
    expected_failure,
):
    with UiRepo() as root:
        index = root / "index.html"
        digg = root / "apps/data-tools/digg.html"
        if mutation == "offline-cache":
            _replace(
                index,
                "catch(function(){return cachedJson(url,fallback)})",
                "catch(function(){return Promise.resolve(fallback)})",
            )
        elif mutation == "gallery-storage":
            _replace(
                index,
                "  /* STATE */",
                "  localStorage.getItem('moonshot-storage-probe');\n"
                "  /* STATE */",
            )
        elif mutation == "voting":
            _replace(
                index,
                "setMyVote(app.stem,current===requested?0:requested);",
                "setMyVote(app.stem,current);",
            )
        elif mutation == "mobile-targets":
            _replace(
                index,
                "</style>",
                """@media(max-width:768px){
.vote-btn{min-width:28px!important;min-height:28px!important}
}
</style>""",
            )
        elif mutation == "gallery-actions":
            _replace(
                index,
                "</style>",
                """@media(max-width:768px){
#glass-gallery-root button{min-width:28px!important;min-height:28px!important;width:28px!important;height:28px!important;padding:0!important}
}
</style>""",
            )
        elif mutation == "bridge-runtime":
            _replace(
                index,
                "iframe.contentWindow.__rz_bridged=true;",
                "iframe.contentWindow.__rz_bridged=false;",
            )
        elif mutation == "digg-storage":
            _replace(
                digg,
                "  'use strict';",
                "  'use strict';\n"
                "  localStorage.getItem('moonshot-storage-probe');",
            )
        elif mutation == "digg-canvas":
            _replace(
                digg,
                'aria-label="Animated append-only organism hash chain, '
                'playing. Press Space or click to pause."',
                "",
            )
        checks = _ui_checks(root)
        assert not checks[expected_failure].passed


def test_gallery_digg_playwright_absence_fails_closed(monkeypatch):
    with UiRepo() as root:
        original = shutil.which
        monkeypatch.setattr(
            gate.shutil,
            "which",
            lambda name: None if name == "node" else original(name),
        )
        results = gate.run_gallery_digg_browser_checks(root)
        assert results
        assert all(not item.passed for item in results)


@pytest.mark.slow
def test_real_observatory_passes_the_complete_gate():
    results = gate.run_gate(REPO_ROOT)
    assert all(item.passed for item in results), {
        item.name: item.detail for item in results if not item.passed
    }
