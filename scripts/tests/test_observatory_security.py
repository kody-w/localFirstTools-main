"""Security and offline-operation contract for the Organism Observatory."""

import ast
import hashlib
import importlib.util
import io
import json
import operator
import os
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import quote, urljoin, urlparse
from xml.etree import ElementTree

import pytest


ROOT = Path(__file__).resolve().parents[2]
APP_PATH = ROOT / "apps" / "3d-immersive" / "organism-observatory.html"
MCP_PATH = ROOT / "scripts" / "rappterzoo_mcp.py"
SYNDICATION_BUILDER_PATH = ROOT / "scripts" / "build_syndication.py"
SYNDICATION_SYNC_PATH = ROOT / "scripts" / "rappterzoo_sync.py"
SYNDICATION_DIR = ROOT / "apps" / "syndication"

EXTERNAL_URL_RE = re.compile(r"(?i)(?:https?:)?//[^\s\"'<>]+")
EXTERNAL_SCRIPT_URL_RE = re.compile(
    r"(?i)(?:'|\"|`)\s*((?:https?:)?//[^\s\"'`<>]+)"
)
UNSAFE_CODE_SINKS = {
    "eval": re.compile(r"(?<![\w$])eval\s*\("),
    "Function constructor": re.compile(r"(?:\bnew\s+)?\bFunction\s*\("),
    "document.write": re.compile(r"\bdocument\s*\.\s*writeln?\s*\("),
    "string timer": re.compile(
        r"\bset(?:Timeout|Interval)\s*\(\s*(?:`|'|\")"
    ),
    "javascript URL": re.compile(r"(?i)\bjavascript\s*:"),
    "srcdoc": re.compile(r"(?i)\bsrcdoc\b"),
}
UNSAFE_HTML_SINKS = {
    "innerHTML": re.compile(r"\.\s*innerHTML\s*="),
    "outerHTML": re.compile(r"\.\s*outerHTML\s*="),
    "insertAdjacentHTML": re.compile(r"\.\s*insertAdjacentHTML\s*\("),
}
REQUIRED_FORBIDDEN_POLICY_KEYS = {
    "biometric",
    "face_landmarks",
    "godd",
    "identity_template",
    "landmarks",
    "media",
    "private",
    "pulse",
    "pulse_bpm",
    "pulse_bpm_estimate",
    "raw_media",
}
SYNDICATION_FORBIDDEN_KEY_TOKENS = {
    "accesstoken",
    "apikey",
    "authtoken",
    "authorization",
    "bearer",
    "biometric",
    "claimcode",
    "clientsecret",
    "cookie",
    "credential",
    "credentials",
    "facelandmarks",
    "godd",
    "identitytemplate",
    "landmarks",
    "media",
    "password",
    "private",
    "privatekey",
    "pulse",
    "pulsebpm",
    "pulsebpmestimate",
    "rawmedia",
    "refreshtoken",
    "secret",
    "sessiontoken",
    "token",
}


class ObservatoryParser(HTMLParser):
    """Collect security-relevant HTML without executing the application."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.scripts = []
        self.styles = []
        self.visible_text = []
        self._capture = None
        self._buffer = []

    def handle_starttag(self, tag, attrs):
        normalized = {
            str(name).lower(): value or ""
            for name, value in attrs
        }
        self.tags.append((tag.lower(), normalized))
        if tag.lower() in {"script", "style"}:
            self._capture = tag.lower()
            self._buffer = []

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == self._capture:
            content = "".join(self._buffer)
            if tag == "script":
                self.scripts.append(content)
            else:
                self.styles.append(content)
            self._capture = None
            self._buffer = []

    def handle_data(self, data):
        if self._capture:
            self._buffer.append(data)
        elif data.strip():
            self.visible_text.append(data)


@pytest.fixture(scope="module")
def observatory():
    if not APP_PATH.is_file():
        pytest.skip("Missing {}".format(APP_PATH.relative_to(ROOT)))
    html = APP_PATH.read_text(encoding="utf-8", errors="strict")
    parser = ObservatoryParser()
    parser.feed(html)
    return {
        "html": html,
        "parser": parser,
        "script": "\n".join(parser.scripts),
        "style": "\n".join(parser.styles),
        "visible": " ".join(parser.visible_text),
    }


def _meta_content(parser, *, name=None, http_equiv=None):
    for tag, attrs in parser.tags:
        if tag != "meta":
            continue
        if name and attrs.get("name", "").lower() == name.lower():
            return attrs.get("content", "")
        if (
            http_equiv
            and attrs.get("http-equiv", "").lower() == http_equiv.lower()
        ):
            return attrs.get("content", "")
    return ""


def _resource_urls(parser, style):
    urls = []
    url_attrs = {
        "action",
        "cite",
        "data",
        "formaction",
        "href",
        "poster",
        "src",
        "srcset",
    }
    for tag, attrs in parser.tags:
        for name in url_attrs:
            value = attrs.get(name, "").strip()
            if value:
                urls.append("{}[{}]={}".format(tag, name, value))
    for match in re.finditer(
        r"(?i)url\s*\(\s*(['\"]?)(.*?)\1\s*\)",
        style,
    ):
        urls.append("css url={}".format(match.group(2).strip()))
    return urls


def _numeric_constants(script):
    constants = {}
    patterns = (
        (
            "",
            re.compile(
                r"\b(?:const|let|var)\s+([A-Z][A-Z0-9_]*)\s*=\s*"
                r"([0-9][0-9\s*+()/.-]*?)\s*;"
            ),
        ),
        (
            "CONFIG.",
            re.compile(
                r"\b([A-Za-z_$][\w$]*)\s*:\s*"
                r"([0-9][0-9\s*+()/.-]*?)\s*,"
            ),
        ),
    )
    for prefix, pattern in patterns:
        for name, expression in pattern.findall(script):
            try:
                constants[prefix + name] = _safe_number(expression)
            except (SyntaxError, TypeError, ValueError, ZeroDivisionError):
                continue
    return constants


def _safe_number(expression):
    operations = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
    }

    def evaluate(node):
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Constant) and isinstance(
            node.value, (int, float)
        ):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in operations:
            return operations[type(node.op)](
                evaluate(node.left),
                evaluate(node.right),
            )
        raise ValueError("non-numeric expression")

    return evaluate(ast.parse(expression, mode="eval"))


def _bounded_constant(constants, name_tokens, maximum):
    matches = {
        name: value
        for name, value in constants.items()
        if any(
            re.sub(r"[^A-Z0-9]", "", token.upper())
            in re.sub(r"[^A-Z0-9]", "", name.upper())
            for token in name_tokens
        )
        and 0 < value <= maximum
    }
    assert matches, (
        "Define a finite {} cap no greater than {}".format(
            "/".join(name_tokens).lower(),
            maximum,
        )
    )
    return matches


def _config_aliases(script, constant_names):
    aliases = set(constant_names)
    for property_name, constant_name in re.findall(
        r"\b([A-Za-z_$][\w$]*)\s*:\s*([A-Z][A-Z0-9_]*)\s*[,}]",
        script,
    ):
        if constant_name in constant_names:
            aliases.add("CONFIG." + property_name)
    return aliases


def test_observatory_exists():
    assert APP_PATH.is_file(), (
        "Organism Observatory is missing: {}".format(
            APP_PATH.relative_to(ROOT)
        )
    )


def test_has_restrictive_csp_and_theme_metadata(observatory):
    parser = observatory["parser"]
    csp = _meta_content(
        parser,
        http_equiv="Content-Security-Policy",
    ).lower()
    directives = {}
    for declaration in csp.split(";"):
        parts = declaration.split()
        if parts:
            directives[parts[0]] = set(parts[1:])
    assert directives.get("default-src") in ({"'none'"}, {"'self'"}), (
        "CSP must restrict default-src to self or none"
    )
    required_sources = {
        "connect-src": "'self'",
        "script-src": "'unsafe-inline'",
        "style-src": "'unsafe-inline'",
        "object-src": "'none'",
        "base-uri": "'none'",
    }
    for directive, source in required_sources.items():
        assert source in directives.get(directive, set()), (
            "CSP {} must include {}".format(directive, source)
        )
    assert (
        "color-scheme" in observatory["style"].lower()
        or _meta_content(parser, name="color-scheme").strip()
    ), "Declare the supported color scheme"
    assert (
        _meta_content(parser, name="theme-color").strip()
        or "prefers-color-scheme" in observatory["script"]
        or "data-theme" in observatory["script"]
    ), "Declare or initialize the application theme"


def test_has_no_external_network_dependencies(observatory):
    external = [
        value
        for value in _resource_urls(
            observatory["parser"],
            observatory["style"],
        )
        if EXTERNAL_URL_RE.search(value)
    ]
    external.extend(
        match.group(1)
        for match in EXTERNAL_SCRIPT_URL_RE.finditer(
            observatory["script"]
        )
    )
    assert not external, "External network dependencies found: {}".format(
        external
    )


def test_fetches_enforce_same_origin_paths(observatory):
    script = observatory["script"]
    string_constants = {
        name: value
        for name, _quote, value in re.findall(
            r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*"
            r"(['\"])(.*?)\2\s*;",
            script,
        )
    }
    fetches = re.findall(r"\bfetch\s*\(\s*([^,\n)]+)", script)
    assert fetches, "The observatory must load its bounded local projection"
    unsafe = []
    for expression in fetches:
        expression = expression.strip()
        literal = re.match(r"^(['\"])(.*?)\1", expression)
        if literal:
            target = literal.group(2)
        else:
            identifier = re.match(r"^([A-Za-z_$][\w$]*)\b", expression)
            target = (
                string_constants.get(identifier.group(1), "")
                if identifier
                else ""
            )
        guarded_dynamic_path = (
            not target
            and identifier
            and re.search(
                r"\bisSameOriginPath\s*\(\s*{}\s*\)".format(
                    re.escape(identifier.group(1))
                ),
                script,
            )
            and re.search(
                r"\.origin\s*={2,3}\s*window\.location\.origin",
                script,
            )
        )
        if not guarded_dynamic_path and (
            not target
            or EXTERNAL_URL_RE.search(target)
            or target.startswith(("data:", "blob:", "javascript:"))
        ):
            unsafe.append(expression)
    assert not unsafe, (
        "fetch() targets must resolve to static same-origin relative paths: "
        + repr(unsafe)
    )
    assert not re.search(
        r"\b(?:XMLHttpRequest|WebSocket|EventSource|sendBeacon)\b",
        script,
    ), "Use only the audited same-origin fetch path"


@pytest.mark.parametrize(
    "sink,pattern",
    sorted(UNSAFE_CODE_SINKS.items()),
)
def test_has_no_unsafe_code_execution_sinks(observatory, sink, pattern):
    assert not pattern.search(observatory["script"]), (
        "Unsafe sink found: {}".format(sink)
    )


@pytest.mark.parametrize(
    "sink,pattern",
    sorted(UNSAFE_HTML_SINKS.items()),
)
def test_has_no_unsafe_html_injection(observatory, sink, pattern):
    assert not pattern.search(observatory["script"]), (
        "{} is forbidden; render imported data with textContent/createElement"
        .format(sink)
    )


def test_imports_have_byte_and_frame_limits(observatory):
    script = observatory["script"]
    constants = _numeric_constants(script)
    byte_caps = _bounded_constant(
        constants,
        ("IMPORT_BYTES", "FILE_BYTES", "FILE_SIZE", "MAX_BYTES"),
        10 * 1024 * 1024,
    )
    frame_caps = _bounded_constant(
        constants,
        ("IMPORT_FRAMES", "FRAME_COUNT", "MAX_FRAMES", "MAX_RECORDS"),
        10000,
    )
    byte_guard_names = _config_aliases(script, byte_caps)
    frame_guard_names = _config_aliases(script, frame_caps)
    size_guard = min(
        (
            match.start()
            for name in byte_guard_names
            for match in re.finditer(
                r"(?:\.size\s*[><=]+[^;\n]*\b{0}\b|"
                r"\b{0}\b\s*[><=]+[^;\n]*\.size)".format(re.escape(name)),
                script,
            )
        ),
        default=-1,
    )
    read_positions = [
        position
        for position in (
            script.find(".text("),
            script.find("FileReader"),
            script.find(".arrayBuffer("),
        )
        if position >= 0
    ]
    assert size_guard >= 0, "Check file.size against the byte cap"
    assert read_positions and size_guard < min(read_positions), (
        "Reject oversized files before reading them"
    )
    assert any(
        re.search(
            r"(?:\.length\s*[><=]+[^;\n]*\b{0}\b|"
            r"\b{0}\b\s*[><=]+[^;\n]*\.length)".format(re.escape(name)),
            script,
        )
        for name in frame_guard_names
    ), "Check imported frame count before rendering or caching"


def test_import_policy_rejects_private_biometric_fields(observatory):
    script = observatory["script"]
    policy_match = re.search(
        r"(?:FORBIDDEN_PUBLIC_KEYS|forbidden(?:Public)?(?:Keys?)?)\s*=\s*"
        r"(?:new\s+Set\s*\(\s*)?([\[{])([\s\S]{0,3000}?)(?:\]|\})\s*\)?\s*;",
        script,
        re.IGNORECASE,
    )
    assert policy_match, "Define an explicit forbidden public-field policy"
    policy_body = policy_match.group(2).lower()
    policy_keys = set(re.findall(r"['\"]([^'\"]+)['\"]", policy_body))
    policy_keys.update(re.findall(
        r"\b([a-z_][a-z0-9_-]*)\s*:",
        policy_body,
    ))
    missing = sorted(
        key
        for key in REQUIRED_FORBIDDEN_POLICY_KEYS
        if key not in policy_keys
    )
    assert not missing, (
        "Imported public frames must reject forbidden fields: {}".format(
            missing
        )
    )
    script_lower = script.lower()
    assert "object.keys" in script_lower, (
        "Forbidden-field checks must recursively inspect imported objects"
    )
    assert re.search(
        r"\b(?:forbidden|sensitive|private)[a-z0-9_]*\s*(?:\(|\[)",
        script_lower,
    ), "Imported frames must pass through a forbidden-field validator"


def test_has_offline_cache_and_manual_import_fallback(observatory):
    script = observatory["script"]
    parser = observatory["parser"]
    assert "localStorage.setItem" in script
    assert "localStorage.getItem" in script
    assert re.search(r"\btry\s*\{[\s\S]*?\bfetch\s*\(", script), (
        "Local projection fetch must be guarded for offline failure"
    )
    assert re.search(r"\bcatch\s*(?:\([^)]*\))?\s*\{", script)
    assert any(
        tag == "input" and attrs.get("type", "").lower() == "file"
        for tag, attrs in parser.tags
    ), "Provide a manual JSON/JSONL import fallback"
    assert re.search(
        r"\b(?:offline|cached|cache|import)\b",
        observatory["visible"],
        re.IGNORECASE,
    ), "Explain the offline fallback in visible UI"


def test_labels_rapp1_acceptance_as_structural_unverified(observatory):
    assert re.search(
        r"\bstructural-unverified\b",
        observatory["visible"],
        re.IGNORECASE,
    ), "The visible UI must label RAPP/1 acceptance structural-unverified"


@pytest.fixture(scope="module")
def mcp_module():
    assert MCP_PATH.is_file(), (
        "Real stdio MCP server is missing: {}".format(
            MCP_PATH.relative_to(ROOT)
        )
    )
    spec = importlib.util.spec_from_file_location(
        "rappterzoo_mcp_security_target",
        MCP_PATH,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _mcp_instance(module, writes_enabled=False, runner=None):
    source = module.DataSource(ROOT, module.DEFAULT_BASE_URL)
    return module.RappterZooMCP(
        source,
        writes_enabled=writes_enabled,
        runner=runner or Mock(),
    )


def _mcp_result_text(result):
    return json.loads(result["content"][0]["text"])


def test_mcp_defaults_to_read_only_in_real_process():
    env = dict(os.environ)
    env.pop("RAPPTERZOO_MCP_WRITES", None)
    result = subprocess.run(
        [
            sys.executable,
            str(MCP_PATH),
            "--root",
            str(ROOT),
            "--self-test",
        ],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["writes_enabled"] is False

    env["RAPPTERZOO_MCP_WRITES"] = "true"
    result = subprocess.run(
        [
            sys.executable,
            str(MCP_PATH),
            "--root",
            str(ROOT),
            "--self-test",
        ],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["writes_enabled"] is False, (
        "Only the exact value RAPPTERZOO_MCP_WRITES=1 may enable writes"
    )


def test_mcp_disabled_write_prepares_without_invoking_runner(mcp_module):
    runner = Mock(side_effect=AssertionError("write runner was invoked"))
    server = _mcp_instance(mcp_module, runner=runner)
    result = server.call_tool(
        "register_agent",
        {
            "agent_id": "security-scout",
            "name": "Security Scout",
            "description": "Read-only registration preview.",
            "capabilities": ["review_apps"],
            "owner_url": "https://example.com/agents/security-scout",
        },
    )
    assert result["isError"] is False
    prepared = _mcp_result_text(result)
    assert prepared["write_enabled"] is False
    assert prepared["status"] == "prepared-not-submitted"
    assert prepared["enable_with"] == "RAPPTERZOO_MCP_WRITES=1"
    runner.assert_not_called()


def test_mcp_tool_schemas_are_closed_and_bounded(mcp_module):
    issues = []
    tools = mcp_module._tool_definitions()
    assert {tool["name"] for tool in tools} == {
        "get_home",
        "search_apps",
        "get_organism_frames",
        "verify_organism_projection",
        "agent_park_time_travel",
        "agent_park_local_action",
        "agent_park_export_branch",
        "register_agent",
        "submit_app",
        "request_molt",
        "post_comment",
    }
    for tool in tools:
        schema = tool.get("inputSchema", {})
        label = tool["name"]
        if schema.get("type") != "object":
            issues.append(label + ": inputSchema must be an object")
        if schema.get("additionalProperties") is not False:
            issues.append(label + ": additionalProperties must be false")
        properties = schema.get("properties", {})
        if type(properties) is not dict:
            issues.append(label + ": properties must be an object")
            continue
        for name, definition in properties.items():
            property_label = "{}.{}".format(label, name)
            kind = definition.get("type")
            if kind == "string" and not (
                isinstance(definition.get("maxLength"), int)
                or definition.get("enum")
                or (
                    definition.get("pattern")
                    and re.search(r"\{\d+,\d+\}", definition["pattern"])
                )
            ):
                issues.append(property_label + ": string lacks a finite bound")
            if kind == "array" and not isinstance(
                definition.get("maxItems"),
                int,
            ):
                issues.append(property_label + ": array lacks maxItems")
    submit_schema = next(
        tool["inputSchema"]
        for tool in tools
        if tool["name"] == "submit_app"
    )
    html_schema = submit_schema["properties"]["html_content"]
    if not 1 <= html_schema.get("maxLength", 0) <= mcp_module.MAX_APP_BYTES:
        issues.append(
            "submit_app.html_content: maxLength must match the app byte cap"
        )
    assert not issues, "MCP schema defects:\n- " + "\n- ".join(issues)


def test_mcp_rejects_unknown_tool_arguments(mcp_module):
    server = _mcp_instance(mcp_module)
    result = server.call_tool(
        "verify_organism_projection",
        {"unexpected_write_switch": True},
    )
    assert result["isError"] is True, (
        "Runtime validation must reject properties outside inputSchema"
    )


def test_mcp_has_finite_request_resource_app_and_write_limits(mcp_module):
    assert 0 < mcp_module.MAX_REQUEST_BYTES <= 1024 * 1024
    assert 0 < mcp_module.MAX_RESOURCE_BYTES <= 5 * 1024 * 1024
    assert 0 < mcp_module.MAX_APP_BYTES <= 500 * 1024
    assert 0 < mcp_module.MAX_WRITE_COUNT <= 10

    server = _mcp_instance(mcp_module)
    oversized_html = (
        '<!doctype html><meta name="viewport" content="width=device-width">'
        "<title>Bounded</title>"
        + ("x" * mcp_module.MAX_APP_BYTES)
    )
    result = server.call_tool(
        "submit_app",
        {
            "title": "Oversized app",
            "category": "creative_tools",
            "html_content": oversized_html,
        },
    )
    assert result["isError"] is True
    assert "500 KiB" in _mcp_result_text(result)["error"]


def test_mcp_stdio_rejects_oversized_jsonrpc_line(mcp_module, monkeypatch):
    server = mcp_module.JSONRPCServer(_mcp_instance(mcp_module))
    fake_input = SimpleNamespace(
        buffer=[b"x" * (mcp_module.MAX_REQUEST_BYTES + 1)]
    )
    fake_output = io.StringIO()
    monkeypatch.setattr(mcp_module.sys, "stdin", fake_input)
    monkeypatch.setattr(mcp_module.sys, "stdout", fake_output)
    assert mcp_module.run_stdio(server) == 0
    response = json.loads(fake_output.getvalue())
    assert response["error"]["code"] == -32700
    assert "exceeds" in response["error"]["message"]


def test_mcp_source_has_no_eval_exec_or_shell_true():
    source = MCP_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(MCP_PATH))
    defects = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
            defects.append("{}()".format(node.func.id))
        for keyword in node.keywords:
            if keyword.arg != "shell":
                continue
            if not (
                isinstance(keyword.value, ast.Constant)
                and keyword.value.value is False
            ):
                defects.append("shell=True or dynamic shell")
    assert not defects, "Dangerous execution found: {}".format(defects)


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/rappterzoo/",
        "//example.com/rappterzoo/",
        "https://user:secret@example.com/rappterzoo/",
        "https://example.com/rappterzoo/?token=secret",
        "https://example.com/rappterzoo/#fragment",
    ],
)
def test_mcp_rejects_non_https_or_credentialed_base_urls(mcp_module, url):
    with pytest.raises(ValueError):
        mcp_module.DataSource(None, url)


def test_mcp_default_base_url_is_https(mcp_module):
    parsed = mcp_module.urllib.parse.urlparse(mcp_module.DEFAULT_BASE_URL)
    assert parsed.scheme == "https"
    assert parsed.hostname
    assert not parsed.username
    assert not parsed.password


def test_mcp_opted_in_write_uses_mocked_argv_without_shell(
    mcp_module,
    monkeypatch,
):
    responses = [
        SimpleNamespace(returncode=0, stdout="[]", stderr=""),
        SimpleNamespace(
            returncode=0,
            stdout="https://github.com/kody-w/localFirstTools-main/issues/1\n",
            stderr="",
        ),
    ]
    runner = Mock(side_effect=responses)
    monkeypatch.setattr(
        mcp_module.shutil,
        "which",
        lambda command: "/usr/bin/gh" if command == "gh" else None,
    )
    server = _mcp_instance(
        mcp_module,
        writes_enabled=True,
        runner=runner,
    )
    result = server.call_tool(
        "post_comment",
        {
            "app_file": "organism-observatory.html",
            "text": "Security contract verified.",
            "rating": 5,
            "agent_id": "security-scout",
            "idempotency_key": "security-write-test-0001",
        },
    )
    assert result["isError"] is False
    submitted = _mcp_result_text(result)
    assert submitted["status"] == "submitted"
    assert submitted["url"].startswith("https://github.com/")
    assert runner.call_count == 2
    for call in runner.call_args_list:
        command = call.args[0]
        assert isinstance(command, list)
        assert command[:2] == ["gh", "issue"]
        assert call.kwargs.get("shell", False) is False
        assert call.kwargs["check"] is False


def test_mcp_write_session_limit_is_enforced(mcp_module, monkeypatch):
    runner = Mock()
    monkeypatch.setattr(mcp_module.shutil, "which", lambda _command: "/usr/bin/gh")
    server = _mcp_instance(
        mcp_module,
        writes_enabled=True,
        runner=runner,
    )
    server.write_count = mcp_module.MAX_WRITE_COUNT
    result = server.call_tool(
        "post_comment",
        {
            "app_file": "organism-observatory.html",
            "text": "This write must be blocked.",
            "agent_id": "security-scout",
        },
    )
    assert result["isError"] is True
    assert "write limit" in _mcp_result_text(result)["error"].lower()
    runner.assert_not_called()


def _load_security_target(name, path):
    assert path.is_file(), "Missing security target: {}".format(
        path.relative_to(ROOT)
    )
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def syndication_modules():
    return (
        _load_security_target(
            "build_syndication_security_target",
            SYNDICATION_BUILDER_PATH,
        ),
        _load_security_target(
            "rappterzoo_sync_security_target",
            SYNDICATION_SYNC_PATH,
        ),
    )


def _normalized_key(value):
    return "".join(
        character.lower()
        for character in str(value)
        if character.isalnum()
    )


def _assert_static_syndication_url(builder, value, relative):
    expected = urljoin(
        builder.DEFAULT_BASE_URL.rstrip("/") + "/",
        quote("apps/syndication/" + relative, safe="/"),
    )
    assert value == expected
    parsed = urlparse(value)
    base = urlparse(builder.DEFAULT_BASE_URL)
    assert parsed.scheme == "https"
    assert parsed.netloc == base.netloc
    assert not parsed.username
    assert not parsed.password
    assert not parsed.query
    assert not parsed.fragment


def _confined_syndication_path(relative):
    assert isinstance(relative, str) and relative
    assert "\\" not in relative
    candidate = (SYNDICATION_DIR / relative).resolve()
    candidate.relative_to(SYNDICATION_DIR.resolve())
    return candidate


def test_syndication_static_feed_urls_hashes_and_paths_are_confined(
    syndication_modules,
):
    builder, _sync = syndication_modules
    index_path = SYNDICATION_DIR / "index.json"
    snapshot_path = SYNDICATION_DIR / "snapshot.json"
    feed_path = SYNDICATION_DIR / "feed.json"
    atom_path = SYNDICATION_DIR / "feed.xml"
    for path in (index_path, snapshot_path, feed_path, atom_path):
        assert path.is_file(), "Missing static syndication artifact: {}".format(
            path.relative_to(ROOT)
        )

    index = builder.load_json_bytes(index_path.read_bytes(), "index")
    assert index["stream_id"] == builder.STREAM_ID
    previous = None
    delta_urls = set()
    for sequence, entry in enumerate(index["deltas"]):
        digest = entry["sha256"]
        relative = "deltas/{}.json".format(digest)
        assert entry["sequence"] == sequence
        assert entry["path"] == relative
        assert entry["previous_delta"] == previous
        assert entry["since_seq"] == sequence - 1
        assert entry["through_seq"] == sequence
        target = _confined_syndication_path(relative)
        data = target.read_bytes()
        assert len(data) == entry["size"]
        assert hashlib.sha256(data).hexdigest() == digest
        _assert_static_syndication_url(
            builder,
            entry["url"],
            relative,
        )
        delta_urls.add(entry["url"])
        previous = digest

    snapshot_entry = index["snapshot"]
    assert snapshot_entry["path"] == "snapshot.json"
    snapshot_bytes = snapshot_path.read_bytes()
    assert len(snapshot_bytes) == snapshot_entry["size"]
    assert hashlib.sha256(snapshot_bytes).hexdigest() == snapshot_entry[
        "sha256"
    ]
    _assert_static_syndication_url(
        builder,
        snapshot_entry["url"],
        "snapshot.json",
    )
    _assert_static_syndication_url(
        builder,
        index["atom"]["url"],
        "feed.xml",
    )
    _assert_static_syndication_url(
        builder,
        index["json_feed"]["url"],
        "feed.json",
    )

    feed = builder.load_json_bytes(feed_path.read_bytes(), "JSON feed")
    _assert_static_syndication_url(
        builder,
        feed["feed_url"],
        "feed.json",
    )
    for item in feed["items"]:
        assert item["id"].startswith("urn:sha256:")
        assert item["url"] in delta_urls
        assert item["attachments"]
        assert all(
            attachment["url"] in delta_urls
            for attachment in item["attachments"]
        )

    atom = ElementTree.parse(str(atom_path)).getroot()
    static_prefix = builder.DEFAULT_BASE_URL.rstrip("/") + (
        "/apps/syndication/"
    )
    for node in atom.iter():
        values = list(node.attrib.values())
        if node.text:
            values.append(node.text.strip())
        for value in values:
            if value.startswith("http://") or value.startswith("https://"):
                assert value.startswith(static_prefix), (
                    "Atom feed URL escapes the static syndication path: "
                    + value
                )


def test_syndication_descriptors_are_pinned_and_path_confined(
    syndication_modules,
):
    builder, _sync = syndication_modules
    snapshot = builder.load_json_bytes(
        (SYNDICATION_DIR / "snapshot.json").read_bytes(),
        "snapshot",
    )
    for descriptor in (
        snapshot.get("apps", [])
        + snapshot.get("data_objects", [])
    ):
        path = descriptor["path"]
        assert not Path(path).is_absolute()
        assert ".." not in Path(path).parts
        assert "\\" not in path
        digest = descriptor["sha256"]
        assert re.fullmatch(r"[0-9a-f]{64}", digest)
        assert descriptor["content_id"] == "sha256:" + digest
        assert descriptor["verification"] == {
            "algorithm": "sha256",
            "required": True,
        }
        expected = urljoin(
            builder.DEFAULT_BASE_URL.rstrip("/") + "/",
            quote(path, safe="/"),
        )
        assert descriptor["url"] == expected
        parsed = urlparse(descriptor["url"])
        assert parsed.scheme == "https"
        assert parsed.netloc == urlparse(builder.DEFAULT_BASE_URL).netloc
        assert not parsed.query
        assert not parsed.fragment


def _assert_public_syndication_value(value, context="root"):
    if isinstance(value, list):
        for index, item in enumerate(value):
            _assert_public_syndication_value(
                item,
                "{}[{}]".format(context, index),
            )
        return
    if type(value) is not dict:
        return
    signals = [
        value.get("kind"),
        value.get("type"),
        value.get("schema"),
    ]
    comment_context = (
        "comment" in _normalized_key(context)
        or "comment_id" in value
        or any(
            isinstance(signal, str) and "comment" in signal.lower()
            for signal in signals
        )
    )
    visibility = value.get("visibility")
    if visibility is not None:
        assert visibility in {"public", "public-metadata"}, (
            "{} has non-public visibility".format(context)
        )
    for key, item in value.items():
        token = _normalized_key(key)
        false_policy_declaration = token == "token" and item is False
        if not false_policy_declaration:
            assert token not in SYNDICATION_FORBIDDEN_KEY_TOKENS, (
                "{} exposes forbidden key {}".format(context, key)
            )
        child_context = context + "." + key
        child_comment = comment_context or "comment" in token
        if child_comment and token in {
            "body",
            "commentbody",
            "content",
            "message",
            "text",
        }:
            assert value.get("selected") is True, (
                "{} exposes an unselected body".format(context)
            )
            assert value.get("visibility") in {
                "public",
                "public-metadata",
            }, "{} exposes a non-public body".format(context)
        _assert_public_syndication_value(item, child_context)


def test_syndication_allows_only_explicit_token_false_policy_declaration():
    _assert_public_syndication_value({
        "transparency": {
            "token": False,
        },
    })
    unsafe = [
        {"transparency": {"token": True}},
        {"transparency": {"token": "public-value"}},
        {"access_token": False},
        {"api_key": False},
        {"secret": False},
    ]
    for value in unsafe:
        with pytest.raises(AssertionError):
            _assert_public_syndication_value(value)


def test_syndication_outputs_contain_no_secrets_or_unselected_bodies(
    syndication_modules,
):
    builder, _sync = syndication_modules
    json_paths = sorted(SYNDICATION_DIR.rglob("*.json"))
    assert json_paths
    for path in json_paths:
        value = builder.load_json_bytes(
            path.read_bytes(),
            str(path.relative_to(ROOT)),
        )
        _assert_public_syndication_value(
            value,
            str(path.relative_to(ROOT)),
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"api_key": "secret", "visibility": "public"},
        {"private": {"value": "hidden"}, "visibility": "public"},
        {"godd": "local-only", "visibility": "public"},
        {"raw_media": "frame", "visibility": "public"},
        {"identity_template": "vector", "visibility": "public"},
        {"pulse_bpm": 72, "visibility": "public"},
        {
            "comments": [{
                "body": "not selected",
                "comment_id": "comment-private",
                "selected": False,
                "visibility": "public",
            }],
            "visibility": "public-metadata",
        },
    ],
)
def test_syndication_builder_and_sync_reject_private_payloads(
    syndication_modules,
    payload,
):
    builder, sync_client = syndication_modules
    with pytest.raises(builder.SyndicationError):
        builder.validate_public_data_value(payload)
    with pytest.raises(sync_client.SyncError):
        sync_client.validate_public_data_value(payload)


@pytest.mark.parametrize(
    "path",
    [
        "../escape.html",
        "apps/../escape.html",
        "/absolute/path.html",
        r"apps\escape.html",
        "",
    ],
)
def test_syndication_builder_and_sync_reject_unsafe_paths(
    syndication_modules,
    path,
):
    builder, sync_client = syndication_modules
    with pytest.raises(builder.SyndicationError):
        builder._safe_relative_path(path)
    with pytest.raises(sync_client.SyncError):
        sync_client._safe_relative_path(path)


def test_syndication_sync_is_conditional_and_user_initiated(
    syndication_modules,
):
    builder, sync_client = syndication_modules
    index = builder.load_json_bytes(
        (SYNDICATION_DIR / "index.json").read_bytes(),
        "index",
    )
    assert index["rate_budget"]["conditional_get"] == (
        "required-after-first-sync"
    )
    assert index["rate_budget"]["constant_polling"] is False
    assert index["rate_budget"]["mode"] == "user-initiated"
    assert sync_client.DEFAULT_INDEX_URL.startswith("https://")

    source = SYNDICATION_SYNC_PATH.read_text(encoding="utf-8")
    assert '"If-None-Match"' in source
    assert '"If-Modified-Since"' in source
    assert "if status == 304:" in source


def test_syndication_sync_preserves_local_overlays():
    source = SYNDICATION_SYNC_PATH.read_text(encoding="utf-8")
    upper = source.upper()
    assert "DELETE FROM LOCAL_APPS" not in upper
    assert "DROP TABLE LOCAL_APPS" not in upper
    assert "SHUTIL.RMTREE" not in upper

    start = source.index("def materialize(")
    end = source.index("\ndef main(", start)
    materialize = source[start:end]
    global_update = materialize.index("for row in global_rows")
    data_update = materialize.index("for row in data_rows")
    local_update = materialize.index("for row in local_rows")
    assert global_update < data_update < local_update, (
        "Local overlays must be applied last and must never be deleted"
    )
    assert ".unlink(" not in materialize
    assert "rmtree" not in materialize


def _soak_is_active(value):
    if value is True:
        return True
    if isinstance(value, str):
        return value.lower() in {
            "active",
            "enabled",
            "running",
            "soak",
            "soaking",
        }
    if type(value) is dict:
        return any(
            _soak_is_active(value.get(key))
            for key in ("active", "enabled", "mode", "state", "status")
            if key in value
        )
    return False


def _proof_of_fold_state(value):
    if value is False:
        return "disabled"
    if isinstance(value, str):
        return value.lower()
    if type(value) is dict:
        return str(
            value.get("state")
            or value.get("status")
            or value.get("mode")
            or ""
        ).lower()
    return ""


def _collect_soak_and_fold(value, result):
    if isinstance(value, list):
        for item in value:
            _collect_soak_and_fold(item, result)
        return
    if type(value) is not dict:
        return
    for key, item in value.items():
        token = _normalized_key(key)
        if token.startswith("soak") or token.endswith("soak"):
            result["soak"] = result["soak"] or _soak_is_active(item)
        proof_suffix = None
        for prefix in ("prooffold", "proofoffold"):
            if token.startswith(prefix):
                proof_suffix = token[len(prefix):]
                break
        if proof_suffix in {"", "enabled", "mode", "state", "status"}:
            result["proofs"].append(item)
        _collect_soak_and_fold(item, result)


def test_syndication_proof_of_fold_is_safe_during_soak_if_present(
    syndication_modules,
):
    builder, _sync = syndication_modules
    for path in [
        *sorted((ROOT / "apps" / "attention").rglob("*.json")),
        *sorted(SYNDICATION_DIR.rglob("*.json")),
    ]:
        value = builder.load_json_bytes(
            path.read_bytes(),
            str(path.relative_to(ROOT)),
        )
        state = {"proofs": [], "soak": False}
        _collect_soak_and_fold(value, state)
        if not state["soak"] or not state["proofs"]:
            continue
        for proof in state["proofs"]:
            status = _proof_of_fold_state(proof)
            assert status in {"disabled", "assigned"}, (
                "{} enables proof-of-fold during soak".format(
                    path.relative_to(ROOT)
                )
            )
