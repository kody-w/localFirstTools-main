"""Read-only candidate qualification; model calls are always mocked."""

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import copilot_utils
import molt
import rank_games


ORIGINAL = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="rappterzoo:generation" content="0">
<title>Local Notes</title>
<style>
body { font-family: sans-serif; color: #eeeeee; background: #202030; }
textarea { width: 100%; min-height: 12em; }
</style>
</head>
<body>
<label for="note">Your local note</label>
<textarea id="note"></textarea>
<button id="save">Save</button>
<output id="status"></output>
<script>
const editor = document.getElementById('note');
const status = document.getElementById('status');
const button = document.getElementById('save');
function loadNote() {
    editor.value = localStorage.getItem('candidate-note') || '';
}
function saveNote() {
    localStorage.setItem('candidate-note', editor.value);
    status.textContent = 'Saved locally';
}
button.addEventListener('click', saveNote);
editor.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') editor.blur();
});
loadNote();
</script>
</body>
</html>
"""

CANDIDATE = ORIGINAL.replace(
    '<output id="status">', '<output id="status" role="status">'
).replace(
    "    localStorage.setItem('candidate-note', editor.value);\n"
    "    status.textContent = 'Saved locally';",
    "    try {\n"
    "        localStorage.setItem('candidate-note', editor.value);\n"
    "        status.textContent = 'Saved locally ✓';\n"
    "    } catch (error) {\n"
    "        status.textContent = 'Storage is full; copy your note before closing.';\n"
    "    }",
)
OBJECTIVE = "Show a recoverable error if saving the local note fails."
APP_PATH = "apps/productivity/local-notes.html"
ARCHIVE_PATH = "apps/archive/local-notes/v1.html"
LOG_PATH = "apps/archive/local-notes/molt-log.json"


def digest(source):
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def snapshot(root):
    return {
        str(path.relative_to(root)): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in root.rglob("*") if path.is_file()
    }


@pytest.fixture(autouse=True)
def no_inference(monkeypatch):
    blocked = mock.Mock(side_effect=AssertionError("Unmocked inference is forbidden"))
    monkeypatch.setattr(molt, "copilot_call_with_retry", blocked)
    monkeypatch.setattr(molt, "_analyze_content", blocked)
    monkeypatch.setattr(copilot_utils, "copilot_call", blocked)
    monkeypatch.setattr(rank_games, "_get_adaptive_scores", blocked)
    monkeypatch.setattr(rank_games, "load_player_ratings", blocked)
    return blocked


@pytest.fixture
def project(tmp_path):
    apps = tmp_path / "apps"
    (apps / "productivity").mkdir(parents=True)
    (apps / "productivity" / "local-notes.html").write_bytes(ORIGINAL.encode("utf-8"))
    manifest = {
        "categories": {
            "productivity": {
                "folder": "productivity", "count": 2,
                "apps": [
                    {"file": "local-notes.html", "title": "Local Notes", "generation": 0},
                    {"file": "other.html", "title": "Leave me alone", "generation": 4},
                ],
            },
        },
        "meta": {"version": "1.0", "lastUpdated": "2026-01-01"},
    }
    (apps / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    for filename in (
        "content-identities.json", "community.json", "ghost-state.json",
        "feed.json", "organism-frames.jsonl", "molter-state.json",
    ):
        (apps / filename).write_text('{"untouched": true}\n', encoding="utf-8")
    (apps / "rankings.json").write_text(json.dumps({
        "rankings": [{"file": "local-notes.html", "score": 100}],
    }), encoding="utf-8")
    return tmp_path, apps, manifest


def prepare(project, candidate=CANDIDATE, **kwargs):
    _, apps, manifest = project
    return molt.prepare_molt_candidate(
        "local-notes.html", OBJECTIVE, candidate_html=candidate,
        apps_dir=apps, manifest=manifest, **kwargs,
    )


def score_result(score):
    return {
        "score": score, "scoring_mode": "legacy",
        "dimensions": {"structural": {"score": 15, "max": 15}},
        "runtime_health": {"score": 80, "verdict": "healthy", "modifier": 0},
    }


def test_model_is_denied_by_default(project, no_inference):
    before = snapshot(project[0])
    result = prepare(project, candidate=None)
    assert result["status"] == "dry_run"
    assert "denied" in result["reason"]
    assert result["model"] == {"invoked": False, "attempts": 0, "timeout_seconds": 180}
    assert result["input_sha256"] == digest(ORIGINAL)
    assert result["app_path"] == APP_PATH
    assert result["changes"] == {}
    assert result["evidence"]["scores"]["status"] == "not_run"
    assert snapshot(project[0]) == before
    no_inference.assert_not_called()


@pytest.mark.parametrize("allow_model", ["true", 1, None])
def test_model_requires_explicit_boolean_permission(project, no_inference, allow_model):
    result = prepare(project, candidate=None, allow_model=allow_model)
    assert result["status"] == "rejected"
    assert result["model"]["attempts"] == 0
    assert result["changes"] == {}
    no_inference.assert_not_called()


def test_injected_candidate_is_exact_and_does_not_touch_canonical_state(project, no_inference):
    root, _, manifest = project
    before = snapshot(root)
    supplied = copy.deepcopy(manifest)
    result = prepare(project, allow_model=True)
    assert result["status"] == "prepared", result
    assert result["filename"] == "local-notes.html"
    assert result["input_sha256"] == digest(ORIGINAL)
    assert result["output_sha256"] == digest(CANDIDATE)
    assert result["objective"] == OBJECTIVE
    assert result["model"]["attempts"] == 0
    assert result["model"]["invoked"] is False
    assert set(result["changes"]) == {APP_PATH, "apps/manifest.json", ARCHIVE_PATH, LOG_PATH}
    assert result["changes"][APP_PATH] == CANDIDATE
    assert result["changes"][ARCHIVE_PATH] == ORIGINAL
    assert all(isinstance(value, str) for value in result["changes"].values())
    json.dumps(result, allow_nan=False).encode("utf-8")
    assert result["evidence"]["base_sha256"] == {
        APP_PATH: digest(ORIGINAL),
        "apps/manifest.json": digest(before["apps/manifest.json"][0].decode("utf-8")),
        ARCHIVE_PATH: None,
        LOG_PATH: None,
    }
    assert result["evidence"]["base_unchanged"] is True
    assert result["evidence"]["structural"]["status"] == "passed"
    assert result["evidence"]["structural"]["syntax"]["status"] == "passed"
    assert result["evidence"]["features"]["result"]["preservation_ratio"] == 1.0
    assert result["evidence"]["end_user_usefulness"] == "not_measured"
    assert snapshot(root) == before
    assert manifest == supplied
    assert not list(root.glob(".molt-candidate-*"))
    no_inference.assert_not_called()


def test_prepared_manifest_and_archive_follow_ordinary_molt_history(project):
    result = prepare(project)
    planned = json.loads(result["changes"]["apps/manifest.json"])
    original_manifest = project[2]
    expected = copy.deepcopy(original_manifest)
    entry = expected["categories"]["productivity"]["apps"][0]
    molt.update_manifest_entry(entry, 1, len(CANDIDATE))
    expected["meta"]["lastUpdated"] = molt.date.today().isoformat()
    assert planned == expected
    assert planned["categories"]["productivity"]["apps"][1] == original_manifest["categories"]["productivity"]["apps"][1]
    audit = json.loads(result["changes"][LOG_PATH])
    assert len(audit) == 1
    assert audit[0]["generation"] == 1
    assert audit[0]["previousSha256"] == result["input_sha256"]
    assert audit[0]["newSha256"] == result["output_sha256"]
    assert audit[0]["mode"] == "classic"
    assert audit[0]["focus"] == "structural"
    assert audit[0]["feature_preservation"] == 1.0
    assert audit[0]["score_before"] == result["evidence"]["scores"]["before"]["score"]
    assert audit[0]["score_after"] == result["evidence"]["scores"]["after"]["score"]


def test_exact_crlf_and_utf8_bytes_are_hashed_and_archived(project):
    original = ORIGINAL.replace("\n", "\r\n")
    candidate = CANDIDATE.replace("\n", "\r\n")
    (project[0] / APP_PATH).write_bytes(original.encode("utf-8"))
    result = prepare(project, candidate=candidate)
    assert result["status"] == "prepared"
    assert result["input_sha256"] == digest(original)
    assert result["output_sha256"] == digest(candidate)
    assert result["changes"][APP_PATH] == candidate
    assert result["changes"][ARCHIVE_PATH] == original
    assert (project[0] / APP_PATH).read_bytes() == original.encode("utf-8")


def test_fresh_scores_use_both_isolated_sources_not_stale_rankings(project, monkeypatch):
    root, apps, _ = project
    real_score = molt._score_app_if_available
    seen = []

    def score(path):
        seen.append((path, path.read_bytes().decode("utf-8")))
        assert path.name == "local-notes.html"
        assert apps not in path.parents
        assert (root / APP_PATH).read_bytes().decode("utf-8") == ORIGINAL
        return real_score(path)

    monkeypatch.setattr(molt, "_score_app_if_available", score)
    result = prepare(project)
    assert result["status"] == "prepared"
    assert [source for _, source in seen] == [ORIGINAL, CANDIDATE]
    assert all(not path.exists() for path, _ in seen)
    scores = result["evidence"]["scores"]
    assert scores["fresh"] is True
    assert scores["mode"] == "legacy"
    assert scores["before"]["score"] != 100
    assert scores["delta"] == scores["after"]["score"] - scores["before"]["score"]
    assert "runtime_health" in scores["before"] and "runtime_health" in scores["after"]


@pytest.mark.parametrize("candidate", [
    ORIGINAL,
    ORIGINAL.strip(),
    ORIGINAL.replace('content="0"', 'content="1"'),
    ORIGINAL.replace("<title>Local Notes</title>", "<title>Better Notes</title>"),
    ORIGINAL.replace("</head>", '<meta name="description" content="Better notes">\n</head>'),
])
def test_noop_and_metadata_only_candidates_do_not_advance_history(project, candidate):
    before = snapshot(project[0])
    result = prepare(project, candidate=candidate)
    assert result["status"] == "skipped"
    assert result["changes"] == {}
    assert result["output_sha256"] == digest(candidate)
    assert snapshot(project[0]) == before
    assert project[2]["categories"]["productivity"]["apps"][0]["generation"] == 0


@pytest.mark.parametrize("candidate, reason", [
    ("", "Empty"),
    (CANDIDATE.replace("<!DOCTYPE html>", ""), "DOCTYPE"),
    (CANDIDATE.replace("<title>Local Notes</title>", ""), "title"),
    (CANDIDATE.replace("<title>Local Notes</title>", "<title> </title>"), "title"),
    (CANDIDATE.replace("</html>", ""), "html"),
    (CANDIDATE.replace('name="viewport"', 'name="other"'), "viewport"),
    (CANDIDATE.replace("function saveNote() {", "function saveNote( {"), "syntax"),
    (CANDIDATE.replace('<button id="save">', '<button id="save" onclick="if (">'), "syntax"),
    (CANDIDATE.replace("<script>", '<script src="https://invalid.example/script.js">'), "External"),
    (CANDIDATE.replace("<script>", '<script src="local.js">'), "External"),
    (CANDIDATE.replace("<script>", '<script type="text/javascript" type="application/json">'), "Duplicate"),
    (CANDIDATE.replace("<script>", "<script/>"), "Self-closing"),
    (CANDIDATE.replace("</head>", '<link rel="stylesheet" href="local.css"></head>'), "stylesheet"),
    (CANDIDATE.replace("candidate-note", "discarded-notes"), "Feature contract"),
    ("<!DOCTYPE html><html><head><title>Tiny</title><meta name=\"viewport\" content=\"width=device-width\"></head><body></body></html>", "small"),
    (CANDIDATE.replace("</body>", "x" * 6_000 + "</body>"), "large"),
])
def test_rejected_content_never_produces_a_patch(project, candidate, reason):
    before = snapshot(project[0])
    result = prepare(project, candidate=candidate)
    assert result["status"] == "rejected", result
    assert reason.lower() in result["reason"].lower()
    assert result["changes"] == {}
    assert snapshot(project[0]) == before


@pytest.mark.parametrize("candidate", [b"html", {"html": CANDIDATE}, CANDIDATE + "\ud800", CANDIDATE + "\x00"])
def test_candidate_requires_utf8_text(project, candidate):
    result = prepare(project, candidate=candidate)
    assert result["status"] == "rejected"
    assert result["changes"] == {}


@pytest.mark.parametrize("filename", [
    "../local-notes.html", "apps/productivity/local-notes.html",
    "/local-notes.html", r"C:\local-notes.html", "local-notes.html\n",
    ".hidden.html", "a" * 256, None,
])
def test_filename_path_traversal_and_unsafe_components_are_rejected(project, filename, no_inference):
    result = molt.prepare_molt_candidate(
        filename, OBJECTIVE, candidate_html=CANDIDATE, apps_dir=project[1], manifest=project[2],
    )
    assert result["status"] == "rejected"
    assert result["changes"] == {}
    no_inference.assert_not_called()


def test_bare_name_and_local_manifest_do_not_fall_back_to_global_paths(project, monkeypatch):
    monkeypatch.setattr(molt, "load_manifest", mock.Mock(side_effect=AssertionError("global manifest")))
    monkeypatch.setattr(molt, "save_manifest", mock.Mock(side_effect=AssertionError("canonical write")))
    result = molt.prepare_molt_candidate(
        "local-notes", OBJECTIVE, apps_dir=project[1], candidate_html=CANDIDATE,
    )
    assert result["status"] == "prepared"
    assert result["filename"] == "local-notes.html"


@pytest.mark.parametrize("objective", ["", " ", "x" * 2_001, "é" * 1_001, None, ["save"], "save\x00", "\ud800"])
def test_objective_is_bounded_utf8_operator_text(project, objective, no_inference):
    result = molt.prepare_molt_candidate(
        "local-notes.html", objective, allow_model=True, apps_dir=project[1], manifest=project[2],
    )
    assert result["status"] == "rejected"
    assert result["changes"] == {}
    no_inference.assert_not_called()


@pytest.mark.parametrize("timeout", [0, -1, 601, 10**400, float("nan"), float("inf"), True, "180"])
def test_timeout_is_bounded_and_json_compatible(project, timeout):
    result = prepare(project, timeout=timeout)
    assert result["status"] == "rejected"
    assert result["model"]["attempts"] == 0
    json.dumps(result, allow_nan=False)


def test_input_and_output_are_bounded_in_bytes(project):
    root, _, _ = project
    (root / APP_PATH).write_bytes(("é" * (molt.MAX_INPUT_SIZE // 2 + 1)).encode("utf-8"))
    result = prepare(project)
    assert result["status"] == "rejected" and "too large" in result["reason"]
    (root / APP_PATH).write_bytes(ORIGINAL.encode("utf-8"))
    result = prepare(project, candidate="é" * (molt.MAX_CANDIDATE_SIZE // 2 + 1))
    assert result["status"] == "rejected" and "UTF-8 bytes" in result["reason"]
    assert result["changes"] == {}


def test_non_utf8_source_is_not_silently_replaced(project):
    (project[0] / APP_PATH).write_bytes(b"\xffinvalid source")
    result = prepare(project)
    assert result["status"] == "rejected"
    assert result["changes"] == {}


@pytest.mark.parametrize("folder", ["../outside", "/outside", "archive", r"productivity\..\outside"])
def test_manifest_folders_cannot_escape_app_sources(project, folder):
    _, apps, manifest = project
    manifest["categories"]["productivity"]["folder"] = folder
    (apps / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    result = prepare(project)
    assert result["status"] == "rejected"
    assert "folder" in result["reason"]


@pytest.mark.parametrize("target", ["app", "category", "manifest", "archive", "root"])
def test_symlink_sources_and_acceptance_paths_are_rejected(project, target):
    root, apps, _ = project
    if target == "app":
        outside = root / "outside.html"
        outside.write_bytes(ORIGINAL.encode("utf-8"))
        (root / APP_PATH).unlink()
        (root / APP_PATH).symlink_to(outside)
    elif target == "category":
        outside = root / "outside-category"
        (apps / "productivity").rename(outside)
        (apps / "productivity").symlink_to(outside, target_is_directory=True)
    elif target == "manifest":
        outside = root / "outside-manifest.json"
        (apps / "manifest.json").rename(outside)
        (apps / "manifest.json").symlink_to(outside)
    elif target == "archive":
        outside = root / "outside-archive"
        outside.mkdir()
        (apps / "archive").symlink_to(outside, target_is_directory=True)
    else:
        outside = root / "outside-apps"
        apps.rename(outside)
        apps.symlink_to(outside, target_is_directory=True)
    result = prepare(project)
    assert result["status"] == "rejected"
    assert "symlink" in result["reason"]
    assert result["changes"] == {}


def test_stale_supplied_manifest_is_rejected_without_mutating_it(project):
    before = snapshot(project[0])
    project[2]["categories"]["productivity"]["apps"][1]["title"] = "Unrelated stale change"
    expected = copy.deepcopy(project[2])
    result = prepare(project)
    assert result["status"] == "rejected"
    assert "differs" in result["reason"]
    assert project[2] == expected
    assert snapshot(project[0]) == before


def test_ambiguous_app_identity_is_rejected(project):
    _, apps, manifest = project
    manifest["categories"]["productivity"]["apps"].append(copy.deepcopy(
        manifest["categories"]["productivity"]["apps"][0],
    ))
    (apps / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    result = prepare(project)
    assert result["status"] == "rejected"
    assert "found 2" in result["reason"]


@pytest.mark.parametrize("failure", [
    FileNotFoundError("node unavailable"),
    subprocess.TimeoutExpired(["node"], molt.SYNTAX_TIMEOUT),
])
def test_required_syntax_checker_cannot_skip_as_success(project, monkeypatch, failure):
    monkeypatch.setattr(subprocess, "run", mock.Mock(side_effect=failure))
    result = prepare(project)
    assert result["status"] == "failed"
    assert result["evidence"]["structural"]["syntax"]["status"] == "unavailable"
    assert result["changes"] == {}


def test_module_and_inline_script_syntax_are_both_checked(project):
    candidate = CANDIDATE.replace("<script>", "<script TYPE=MODULE>").replace(
        "loadNote();", "loadNote();\nexport { saveNote };",
    )
    result = prepare(project, candidate=candidate)
    assert result["status"] == "prepared"
    assert result["evidence"]["structural"]["syntax"]["module_blocks"] == 1
    broken = candidate.replace("export { saveNote };", "export const = ;")
    result = prepare(project, candidate=broken)
    assert result["status"] == "rejected"
    assert "syntax" in result["reason"]


@pytest.mark.parametrize("script_type", [
    "application/x-javascript", "text/javascript1.5", "text/javascript ; charset=utf-8",
])
def test_browser_javascript_mime_aliases_do_not_bypass_syntax_checks(project, script_type):
    candidate = CANDIDATE.replace("<script>", f'<script type="{script_type}">').replace(
        "function saveNote() {", "function saveNote( {",
    )
    result = prepare(project, candidate=candidate)
    assert result["status"] == "rejected"
    assert "syntax" in result["reason"]


def test_data_scripts_are_not_executed_or_mistaken_for_javascript(project):
    candidate = CANDIDATE.replace("</body>", '<script type="application/json">{"note": 1}</script></body>')
    result = prepare(project, candidate=candidate)
    assert result["status"] == "prepared"
    assert result["evidence"]["structural"]["syntax"]["blocks"] == 1


@pytest.mark.parametrize("checker", ["extract_features", "verify_features"])
def test_required_feature_checker_cannot_skip_as_success(project, monkeypatch, checker):
    monkeypatch.setattr(molt, checker, None)
    result = prepare(project)
    assert result["status"] == "failed"
    assert "checker unavailable" in result["reason"]
    assert result["changes"] == {}


@pytest.mark.parametrize("measurement", [None, {}, {"passed": True}, {"passed": "yes"}])
def test_invalid_feature_measurements_fail_closed(project, monkeypatch, measurement):
    monkeypatch.setattr(molt, "verify_features", mock.Mock(return_value=measurement))
    result = prepare(project)
    assert result["status"] == "failed"
    assert result["evidence"]["features"]["status"] == "unavailable"
    assert result["changes"] == {}
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("unavailable", [
    None, {}, {"score": 50}, {"score": 50, "scoring_mode": "adaptive"},
    {"score": None, "scoring_mode": "legacy"},
])
def test_required_comparable_scores_cannot_skip_as_success(project, monkeypatch, unavailable):
    monkeypatch.setattr(molt, "_score_app_if_available", mock.Mock(side_effect=[score_result(50), unavailable]))
    result = prepare(project)
    assert result["status"] == "failed"
    assert result["evidence"]["scores"]["status"] == "unavailable"
    assert result["changes"] == {}


@pytest.mark.parametrize("bad_score", [float("nan"), float("inf"), object()])
def test_non_json_measurements_cannot_escape_the_result(project, monkeypatch, bad_score):
    monkeypatch.setattr(molt, "_score_app_if_available", mock.Mock(side_effect=[
        score_result(bad_score), score_result(50),
    ]))
    result = prepare(project)
    assert result["status"] == "failed"
    assert result["evidence"]["scores"]["status"] == "unavailable"
    assert result["changes"] == {}
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("drop, missing, status", [
    (-5, False, "prepared"), (10, False, "prepared"), (11, False, "rejected"),
    (5, True, "prepared"), (6, True, "rejected"),
])
def test_existing_score_regression_thresholds_are_shared(project, monkeypatch, drop, missing, status):
    monkeypatch.setattr(molt, "_score_app_if_available", mock.Mock(side_effect=[
        score_result(60), score_result(60 - drop),
    ]))
    if missing:
        contract = molt.extract_features(ORIGINAL)
        contract["features"] = [
            {"id": f"feature-{i}", "type": "function"} for i in range(20)
        ]
        monkeypatch.setattr(molt, "extract_features", mock.Mock(return_value=contract))
        monkeypatch.setattr(molt, "verify_features", mock.Mock(return_value={
            "passed": True, "total": 20, "preserved": 19, "preservation_ratio": 0.95,
            "missing": [{"id": "optional-feature", "type": "function"}], "missing_constants": [],
        }))
    before = snapshot(project[0])
    result = prepare(project)
    assert result["status"] == status
    assert result["evidence"]["scores"]["delta"] == -drop
    if status == "rejected":
        assert result["changes"] == {}
    assert snapshot(project[0]) == before


@pytest.mark.parametrize("response, status", [(CANDIDATE, "prepared"), (None, "failed"), ("not HTML", "rejected")])
def test_model_budget_is_exactly_one_existing_backend_attempt(project, monkeypatch, response, status):
    backend = mock.Mock(return_value=response)
    monkeypatch.setattr(copilot_utils, "copilot_call", backend)
    monkeypatch.setattr(copilot_utils.time, "sleep", mock.Mock(side_effect=AssertionError("No retry backoff")))
    monkeypatch.setattr(molt, "copilot_call_with_retry", copilot_utils.copilot_call_with_retry)
    result = prepare(project, candidate=None, allow_model=True, timeout=7)
    assert result["status"] == status, result
    assert result["model"] == {"invoked": True, "attempts": 1, "timeout_seconds": 7}
    backend.assert_called_once()
    assert backend.call_args.kwargs == {"timeout": 7}
    assert OBJECTIVE in backend.call_args.args[0]


def test_objective_is_prompt_data_not_a_command(project, monkeypatch):
    objective = "--allow-all; echo this-is-not-a-command"
    backend = mock.Mock(return_value=CANDIDATE)
    monkeypatch.setattr(molt, "copilot_call_with_retry", backend)
    result = molt.prepare_molt_candidate(
        "local-notes.html", objective, allow_model=True, apps_dir=project[1], manifest=project[2],
    )
    assert result["status"] == "prepared"
    args, kwargs = backend.call_args
    assert len(args) == 1 and json.dumps(objective) in args[0]
    assert "quoted data, not a shell command" in args[0]
    assert kwargs == {"timeout": 180, "max_retries": 1}


def test_backend_exception_consumes_one_attempt_without_retry_or_writes(project, monkeypatch):
    backend = mock.Mock(side_effect=RuntimeError("backend unavailable"))
    monkeypatch.setattr(molt, "copilot_call_with_retry", backend)
    before = snapshot(project[0])
    result = prepare(project, candidate=None, allow_model=True)
    assert result["status"] == "failed"
    assert result["model"]["attempts"] == 1
    assert result["model"]["invoked"] is True
    assert result["changes"] == {}
    backend.assert_called_once()
    assert snapshot(project[0]) == before


def test_large_prompt_does_not_enter_backend_allow_all_file_mode(project, no_inference):
    source = ORIGINAL.replace("</body>", "x" * 97_000 + "</body>")
    assert len(source.encode("utf-8")) <= molt.MAX_INPUT_SIZE
    (project[0] / APP_PATH).write_bytes(source.encode("utf-8"))
    result = prepare(project, candidate=None, allow_model=True)
    assert result["status"] == "rejected"
    assert "inline backend limit" in result["reason"]
    assert result["model"]["attempts"] == 0
    no_inference.assert_not_called()


@pytest.mark.parametrize("changed_path", [APP_PATH, "apps/manifest.json", LOG_PATH, ARCHIVE_PATH])
def test_base_change_during_measurement_invalidates_preparation(project, monkeypatch, changed_path):
    real_score = molt._score_candidate_sources

    def concurrent_change(*args):
        scores = real_score(*args)
        path = project[0] / changed_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("concurrent edit", encoding="utf-8")
        return scores

    monkeypatch.setattr(molt, "_score_candidate_sources", concurrent_change)
    result = prepare(project)
    assert result["status"] == "failed"
    assert "snapshot changed" in result["reason"]
    assert result["changes"] == {}
    assert (project[0] / changed_path).read_text() == "concurrent edit"
    if changed_path != APP_PATH:
        assert (project[0] / APP_PATH).read_text() == ORIGINAL


def test_existing_identical_archive_is_not_rewritten(project):
    path = project[0] / ARCHIVE_PATH
    path.parent.mkdir(parents=True)
    path.write_bytes(ORIGINAL.encode("utf-8"))
    before = snapshot(project[0])
    result = prepare(project)
    assert result["status"] == "prepared"
    assert ARCHIVE_PATH not in result["changes"]
    assert result["evidence"]["base_sha256"][ARCHIVE_PATH] == digest(ORIGINAL)
    assert snapshot(project[0]) == before


def test_conflicting_archive_is_rejected(project):
    path = project[0] / ARCHIVE_PATH
    path.parent.mkdir(parents=True)
    path.write_text("already archived different source", encoding="utf-8")
    before = snapshot(project[0])
    result = prepare(project)
    assert result["status"] == "rejected"
    assert "Archive generation" in result["reason"]
    assert result["changes"] == {}
    assert snapshot(project[0]) == before


@pytest.mark.parametrize("content", ["not JSON", "{}", '[{"generation": 1}]', '[{"generation": 3}]'])
def test_unreadable_or_ahead_archive_history_is_not_overwritten(project, content):
    path = project[0] / LOG_PATH
    path.parent.mkdir(parents=True)
    path.write_text(content, encoding="utf-8")
    before = snapshot(project[0])
    result = prepare(project)
    assert result["status"] == "rejected"
    assert result["changes"] == {}
    assert snapshot(project[0]) == before


def test_existing_history_is_preserved_and_only_next_generation_is_planned(project):
    root, apps, manifest = project
    entry = manifest["categories"]["productivity"]["apps"][0]
    molt.update_manifest_entry(entry, 1, len(ORIGINAL))
    (apps / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    log_path = root / LOG_PATH
    log_path.parent.mkdir(parents=True)
    old_log = [{"generation": 1, "focus": "structural", "other": "preserved"}]
    log_path.write_text(json.dumps(old_log), encoding="utf-8")
    result = prepare(project)
    assert result["status"] == "prepared"
    assert "apps/archive/local-notes/v2.html" in result["changes"]
    log = json.loads(result["changes"][LOG_PATH])
    assert log[:-1] == old_log
    assert log[-1]["generation"] == 2
    assert log[-1]["focus"] == "accessibility"


@pytest.mark.parametrize("surgical", [False, True])
def test_legacy_dry_run_never_invokes_identity_or_inference(project, no_inference, surgical):
    before = snapshot(project[0])
    result = molt.molt_app(
        "local-notes.html", dry_run=True, adaptive=True, surgical=surgical,
        _apps_dir=project[1], _manifest=project[2],
    )
    assert result == {
        "status": "dry_run", "file": "local-notes.html", "category": "productivity",
        "generation": 1, "focus": "structural",
    }
    no_inference.assert_not_called()
    assert snapshot(project[0]) == before


@pytest.mark.parametrize("surgical", [False, True])
def test_legacy_noop_never_archives_or_advances_generation(project, monkeypatch, surgical):
    response = json.dumps([{"find": "Saved locally", "replace": "Saved locally"}]) if surgical else ORIGINAL
    monkeypatch.setattr(molt, "copilot_call_with_retry", mock.Mock(return_value=response))
    before = snapshot(project[0])
    manifest_before = copy.deepcopy(project[2])
    result = molt.molt_app(
        "local-notes.html", adaptive=False, surgical=surgical,
        _apps_dir=project[1], _manifest=project[2],
    )
    assert result["status"] == "skipped"
    assert "unchanged" in result["reason"]
    assert snapshot(project[0]) == before
    assert project[2] == manifest_before
