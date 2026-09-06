#!/usr/bin/env python3
"""Prepare one immutable, base-bound Molter review handoff; never publish it.

prepare/verify/status require --repo, --base and --repository. A prepared
directory contains a complete patch, a base-prerequisite Git bundle, candidate
checks, and a real replay-qualified source-capsule registry. Archived verification
uses the historical commit, not current checkout content. --require-current-base
additionally checks readiness. Neither verification nor a duplicate request reruns
qualification checks or models.
Unsigned hashes detect corruption, not coordinated forgery or human approval.
"""

import argparse
from contextlib import redirect_stdout
from datetime import date
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys

sys.dont_write_bytecode = True


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "scripts/capabilities/source_capsule"
MANIFEST = "landgrab/autocomplete/capabilities/manifests/source-capsule.json"
PIN = "landgrab/autocomplete/rapp-reference.json"
REFERENCE = "vendor/rapp-1"
PACKAGE_SUPPORT = {
    ".gitignore", "NOTICE", "README.md", "__init__.py", "__main__.py", "check_port.py",
    "notices/localFirstTools-AGENTS.md", "scripts/__init__.py", "tests/__init__.py",
    "tests/test_capability_registry.py", "tests/test_port.py", "upstream.json", "verify_vendor.py",
    "vendor/rapp-1/LICENSE", "vendor/rapp-1/SPEC.md", "vendor/rapp-1/rapp.py", "vendor/rapp-1/rapp_check.py",
}
MANIFEST_SHA256 = "e6f639a6d9c0625d3857f872e979e415b92dc4811902156d686ae8db885b3b45"
RAPP_COMMIT = "eb50008011447f5e69372ac22a1755f0978d15ed"
DEFAULT_OBJECTIVE = "Improve this app while preserving its existing features."
MAX_APP_BYTES = 4 * 1024 * 1024
MAX_CHANGE_BYTES = 12 * 1024 * 1024
MAX_ARTIFACT_BYTES = 32 * 1024 * 1024
MAX_PROPOSAL_BYTES = 96 * 1024 * 1024
MAX_ARTIFACTS = 256
TIMEOUT = 180
REPOSITORY = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9][A-Za-z0-9._-]{0,99}")
LIMITATIONS = [
    "Prepared is local review work, not submitted, accepted, merged, or deployed.",
    "Source-capsule proves selected committed UTF-8 source transport and replay, not app-runtime usefulness.",
    "Candidate checks are bounded structural, feature-preservation and comparable-score observations, not browser proof.",
    "Checks are trusted local processes, not a sandbox or an OS-enforced network restriction.",
    "Unsigned hashes and RAPP lineage are integrity evidence, not authenticated approval or protection from coordinated forgery.",
    "The candidate bundle requires the exact source base; no network fallback or automatic delivery exists.",
]


class ProposalError(ValueError):
    def __init__(self, reason, status="rejected"):
        super().__init__(reason)
        self.status = status


def require(condition, reason, status="rejected"):
    if not condition:
        raise ProposalError(reason, status)


def digest(body):
    return hashlib.sha256(body).hexdigest()


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def _pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, "duplicate JSON member")
        result[key] = value
    return result


def _bad_constant(_):
    raise ProposalError("non-finite JSON value")


def _json(body):
    return json.loads(body, object_pairs_hook=_pairs, parse_constant=_bad_constant)


def no_symlinks(path):
    for part in (*reversed(path.parents), path):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        require(not stat.S_ISLNK(info.st_mode), "symlink path refused")


def absolute(value):
    raw = Path(value).absolute()
    require(not any(ord(char) < 32 or ord(char) == 127 for char in str(raw)), "unsafe filesystem path")
    no_symlinks(raw)
    return Path(os.path.abspath(raw))


def relative(value):
    require(isinstance(value, str) and 0 < len(value) <= 512, "invalid relative path")
    require("\\" not in value and ":" not in value
            and not any(ord(c) < 32 or ord(c) == 127 for c in value), "unsafe relative path")
    require(all(part not in {"", ".", "..", ".git"} for part in value.split("/")),
            "unsafe relative path")
    path = PurePosixPath(value)
    require(not path.is_absolute() and path.as_posix() == value, "unsafe relative path")
    return path


def read(path, limit=MAX_ARTIFACT_BYTES):
    no_symlinks(path)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    with os.fdopen(os.open(path, flags), "rb") as handle:
        before = os.fstat(handle.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_size <= limit, "unsafe or oversized file")
        body = handle.read(limit + 1)
        after = os.fstat(handle.fileno())
    require(len(body) <= limit and (before.st_size, before.st_mtime_ns) ==
            (after.st_size, after.st_mtime_ns), "file changed during read or exceeded bound")
    return body


def write_new(path, body):
    no_symlinks(path)
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    no_symlinks(path)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(path, flags, 0o600), "wb") as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())


def environment():
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("GIT_") and key not in {"PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP"}}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0", GIT_NO_REPLACE_OBJECTS="1",
               GIT_NO_LAZY_FETCH="1", GIT_ALLOW_PROTOCOL="file",
               PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1")
    return env


def git(repo, *args, input=None, timeout=60):
    completed = subprocess.run(
        ["git", "--no-optional-locks", "--literal-pathspecs", "-c", "core.hooksPath=" + os.devnull,
         "-c", "core.fsmonitor=false", "-c", "core.autocrlf=false",
         "-c", "core.attributesFile=" + os.devnull, "-C", str(repo), *args],
        input=input, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment(),
        timeout=timeout, check=False,
    )
    require(completed.returncode == 0,
            "local git operation failed: " + " ".join(args[:2]) + ": "
            + completed.stderr.decode("utf-8", errors="replace")[:400], "failed")
    return completed.stdout


def blob(repo, base, name, optional=False):
    relative(name)
    raw = git(repo, "ls-tree", "-z", base, "--", name)
    if not raw:
        require(optional, "required committed source is missing: " + name, "blocked")
        return None, None
    metadata, selected = raw.rstrip(b"\0").split(b"\t", 1)
    mode, kind, oid = metadata.decode("ascii").split()
    require(selected.decode("utf-8") == name and kind == "blob" and mode in {"100644", "100755"},
            "source must be a committed regular file: " + name)
    size = int(git(repo, "cat-file", "-s", oid))
    require(size <= MAX_ARTIFACT_BYTES, "committed source exceeds bound")
    body = git(repo, "cat-file", "blob", oid)
    require(len(body) == size, "committed source size mismatch")
    body.decode("utf-8")
    return body, mode


def bind_source(repo, base, repository, *, require_current=True):
    repo = absolute(repo)
    require(repo.is_dir(), "source repository is missing", "blocked")
    require(REPOSITORY.fullmatch(repository or "") and not repository.lower().endswith(".git"),
            "repository must be an explicit public owner/name")
    require(re.fullmatch(r"[0-9a-f]{7,64}", base or ""), "base must be an explicit Git commit hash")
    require(absolute(git(repo, "rev-parse", "--show-toplevel").decode().strip()) == repo,
            "--repo must be the source worktree root")
    commit = git(repo, "rev-parse", "--verify", base + "^{commit}").decode().strip()
    if require_current:
        require(git(repo, "rev-parse", "HEAD").decode().strip() == commit, "stale base: source HEAD differs")
        dirty = git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all",
                    "--ignored=matching", "--ignore-submodules=none")
        require(not dirty, "source must be clean and committed, including untracked and ignored files")
        flags = git(repo, "ls-files", "-v", "-z").split(b"\0")
        require(all(not item or item.startswith(b"H ") for item in flags),
                "source index must not hide modifications with assume-unchanged or skip-worktree flags")
    return repo, commit, git(repo, "rev-parse", commit + "^{tree}").decode().strip()


def output_path(value, repo):
    path = absolute(value)
    common = absolute(repo / git(repo, "rev-parse", "--git-common-dir").decode().strip())
    worktrees = [
        absolute(item[len(b"worktree "):].decode("utf-8"))
        for item in git(repo, "worktree", "list", "--porcelain", "-z").split(b"\0")
        if item.startswith(b"worktree ")
    ]
    require(all(path != protected and protected not in path.parents and path not in protected.parents
                for protected in (repo, common, *worktrees)),
            "proposal directory must be outside canonical source, linked worktrees and Git storage")
    require(path.parent.is_dir(), "proposal parent directory must already exist")
    for directory in (path.parent, path) if path.exists() else (path.parent,):
        info = directory.stat()
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid()
                and not info.st_mode & 0o022, "proposal directory must be owned and not writable by others")
    return path


def select_app(repo, base, target):
    raw, _ = blob(repo, base, "apps/manifest.json")
    manifest = _json(raw)
    if target is None:
        from autonomous_frame import select_molt_candidates

        ranked, _ = blob(repo, base, "apps/rankings.json", optional=True)
        choices = select_molt_candidates(_json(ranked) if ranked else {}, manifest, 1)
        require(choices, "no ranked app candidate", "blocked")
        target = choices[0]["file"]
    relative(target)
    require("/" not in target and target.endswith(".html"), "target must be one HTML filename")
    matches = [(key, category, app) for key, category in manifest.get("categories", {}).items()
               for app in category.get("apps", []) if app.get("file") == target]
    require(len(matches) == 1, "target must have one manifest entry")
    key, category, app = matches[0]
    folder = category.get("folder")
    relative(folder)
    require("/" not in folder and folder not in {"archive", "broadcasts"}, "unsafe app category")
    path = "apps/" + folder + "/" + target
    body, _ = blob(repo, base, path)
    require(0 < len(body) <= MAX_APP_BYTES, "target is empty or exceeds app bound")
    generation = app.get("generation", 0)
    require(type(generation) is int and 0 <= generation < 100000, "invalid app generation")
    return target, path, manifest, key, app, body


def inventory(root):
    result, total = [], 0
    pending = [root]
    while pending:
        directory = pending.pop()
        no_symlinks(directory)
        for path in sorted(directory.iterdir()):
            no_symlinks(path)
            info = path.stat()
            name = path.relative_to(root).as_posix()
            if name == "receipt.json":
                continue
            relative(name)
            require(info.st_uid == os.getuid() and not info.st_mode & 0o022,
                    "artifact is not privately owned")
            if path.is_dir():
                pending.append(path)
                require(len(pending) <= MAX_ARTIFACTS and len(path.parts) - len(root.parts) <= 16,
                        "artifact directory bound exceeded")
                continue
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "unsafe artifact type or hardlink")
            body = read(path)
            total += len(body)
            result.append({"path": name, "bytes": len(body), "sha256": digest(body),
                           "mode": stat.S_IMODE(info.st_mode)})
            require(len(result) <= MAX_ARTIFACTS and total <= MAX_PROPOSAL_BYTES, "proposal exceeds bounds")
    return sorted(result, key=lambda item: item["path"])


def _summary(receipt, noop=False, readiness=False):
    return {key: receipt[key] for key in (
        "status", "reason", "request_id", "repository", "base_commit", "target", "app_path",
        "qualified", "qualification", "candidate_commit", "delivery", "deployment_verified",
    )} | {"noop": noop, "receipt": "receipt.json", "patch": receipt.get("patch"),
         "bundle": receipt.get("bundle"),
         "base_readiness": {"checked": readiness, "matches_required_base": True if readiness else None}}


def _adapter_identity():
    return {name: digest(read(Path(__file__).with_name(name)))
            for name in ("molter_capabilities.py", "molter_capability_worker.py")}


def _verify_adapter_identity(proposal, repo, base, expected):
    require(isinstance(expected, dict)
            and set(expected) == {"molter_capabilities.py", "molter_capability_worker.py"},
            "invalid producing-adapter identity")
    for name, sha in expected.items():
        saved = proposal / "adapter" / name
        if saved.exists():
            body = read(saved)
        else:
            # Older v1 artifacts can bind the producer through their original source commit.
            body, _ = blob(repo, base, "scripts/" + name, optional=True)
        require(body is not None and digest(body) == sha, "archived producing-adapter bytes differ")


def _receipt(root, request, status, reason, validate=None, **extra):
    value = {
        "schema": "molter-review-proposal/v1", "status": status, "reason": reason,
        "request_id": digest(json_bytes(request)), "repository": request["repository"],
        "base_commit": request["base_commit"], "target": request["target"],
        "app_path": request["app_path"], "qualified": False, "qualification": None,
        "candidate_commit": None, "deployment_verified": False,
        "delivery": {"state": "not_submitted", "externally_submitted": False, "deployment_verified": False},
        "limitations": LIMITATIONS, **extra,
    }
    value["artifacts"] = inventory(root)
    value["integrity_sha256"] = digest(json_bytes(value))
    if validate is not None:
        validate(value)
        require(inventory(root) == value["artifacts"], "artifacts changed during final verification", "failed")
    write_new(root / "receipt.json", json_bytes(value))
    return value


def _package_inputs(repo, base, rapp_ref):
    raw, _ = blob(repo, base, PACKAGE + "/" + MANIFEST)
    require(digest(raw) == MANIFEST_SHA256, "pinned source-capsule manifest differs")
    manifest = _json(raw)
    require(manifest["id"] == "source-capsule" and manifest["version"] == "1.0.3"
            and not manifest["reuses"], "unexpected pinned capability contract")
    names = {MANIFEST, PIN, "scripts/capability_registry.py"} | PACKAGE_SUPPORT
    names.update(item["path"] for item in manifest["artifacts"])
    committed = {
        name.decode("utf-8")[len(PACKAGE) + 1:]
        for name in git(repo, "ls-tree", "-r", "--name-only", "-z", base, "--", PACKAGE).split(b"\0") if name
    }
    require(committed == names, "committed capability package has missing or undeclared files", "blocked")
    files = {name: blob(repo, base, PACKAGE + "/" + name)[0] for name in sorted(names)}
    require(sum(map(len, files.values())) <= MAX_CHANGE_BYTES, "capability package exceeds bound")
    for item in manifest["artifacts"]:
        require(digest(files[item["path"]]) == item["sha256"]
                and len(files[item["path"]]) == item["bytes"], "pinned capability artifact differs")
    pin = _json(files[PIN])
    require(pin["commit"] == RAPP_COMMIT
            and set(pin["files"]) == {"rapp.py", "rapp_check.py", "SPEC.md"}, "unexpected RAPP pin")
    for name, sha in pin["files"].items():
        body = files[REFERENCE + "/" + name]
        require(digest(body) == sha, "RAPP reference bytes differ from pin")
        if rapp_ref is not None:
            require(read(absolute(rapp_ref) / name) == body, "external RAPP reference differs from bundled pin")
    return files


def _worker(action, proposal, context, timeout=TIMEOUT + 30):
    work = proposal / "check-work"
    work.mkdir(mode=0o700)
    env = environment()
    env.update(TMPDIR=str(work), TMP=str(work), TEMP=str(work))
    try:
        try:
            completed = subprocess.run(
                [sys.executable, "-B", str(Path(__file__).with_name("molter_capability_worker.py")),
                 action, "--proposal", str(proposal), "--context", str(context)],
                cwd=proposal, env=env, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            _worker_observation(proposal, action, exc.stdout or b"", exc.stderr or b"", None, timeout)
            raise ProposalError("isolated " + action + " worker timed out", "failed") from exc
        _worker_observation(proposal, action, completed.stdout, completed.stderr, completed.returncode, timeout)
        if completed.stderr:
            print(completed.stderr.decode("utf-8", errors="replace")[:2000], file=sys.stderr)
        require(completed.returncode == 0, "isolated " + action + " worker failed", "failed")
        require(len(completed.stdout) <= MAX_ARTIFACT_BYTES and len(completed.stderr) <= MAX_ARTIFACT_BYTES,
                "worker output exceeded bound", "failed")
        return _json(completed.stdout)
    finally:
        shutil.rmtree(work)


def _worker_observation(proposal, action, stdout, stderr, code, timeout):
    observation = {"action": action, "exit_code": code, "timed_out": code is None, "timeout_seconds": timeout}
    for name, body in (("stdout", stdout), ("stderr", stderr)):
        path = "diagnostics/" + action + "." + name + ".txt"
        write_new(proposal / path, body[:MAX_ARTIFACT_BYTES])
        observation[name] = {"path": path, "bytes": len(body), "sha256": digest(body),
                             "truncated": len(body) > MAX_ARTIFACT_BYTES}
    write_new(proposal / ("diagnostics/" + action + ".json"), json_bytes(observation))


def _init_git(root):
    git(root, "init", "--quiet")
    git(root, "config", "user.name", "Molter proposal")
    git(root, "config", "user.email", "molter-proposal@localhost")
    git(root, "config", "commit.gpgSign", "false")


def _stage_source(repo, base, root, app_path, target):
    root.mkdir(mode=0o700)
    _init_git(root)
    common = absolute(repo / git(repo, "rev-parse", "--git-common-dir").decode().strip())
    write_new(root / ".git/objects/info/alternates", (str(common / "objects") + "\n").encode())
    git(root, "config", "core.sparseCheckout", "true")
    git(root, "config", "core.sparseCheckoutCone", "false")
    write_new(root / ".git/info/attributes", b"* -text -filter -ident -working-tree-encoding\n")
    patterns = ["/scripts/", "/apps/manifest.json", "/" + app_path,
                "/apps/archive/" + Path(target).stem + "/"]
    write_new(root / ".git/info/sparse-checkout", ("\n".join(patterns) + "\n").encode())
    git(root, "update-ref", "HEAD", base)
    git(root, "read-tree", "-mu", base)
    require(not git(root, "status", "--porcelain=v1", "--untracked-files=all"), "staged source is not clean")


def _stage_package(proposal, files):
    root = proposal / "capability"
    root.mkdir(mode=0o700)
    for name, body in files.items():
        write_new(root / relative(name), body)
    _init_git(root)
    git(root, "add", "--", *sorted(files))
    git(root, "commit", "--quiet", "-m", "Pinned source-capsule implementation and RAPP reference")
    commit = git(root, "rev-parse", "HEAD").decode().strip()
    git(root, "bundle", "create", str(proposal / "capability.bundle"), "HEAD")
    return commit


def _manifest_delta(before, after, category_key, target, new_size):
    previous = next(app for app in before["categories"][category_key]["apps"] if app["file"] == target)
    updated = next(app for app in after["categories"][category_key]["apps"] if app["file"] == target)
    allowed = {"generation", "lastMolted", "moltHistory"}
    require({k: v for k, v in previous.items() if k not in allowed}
            == {k: v for k, v in updated.items() if k not in allowed}, "unrelated app manifest changes")
    generation = previous.get("generation", 0) + 1
    require(updated.get("generation") == generation, "manifest generation delta is not one")
    date.fromisoformat(updated["lastMolted"])
    require(updated.get("moltHistory") == previous.get("moltHistory", []) + [
        {"gen": generation, "date": updated["lastMolted"], "size": new_size}
    ], "manifest history is not the necessary single append")
    restored = _json(json_bytes(after))
    apps = restored["categories"][category_key]["apps"]
    apps[apps.index(updated)] = previous
    require(restored == before, "unrelated manifest modifications")


def validate_candidate(result, repo, request, manifest, category_key, app, original):
    require(isinstance(result, dict), "invalid candidate response", "failed")
    status = result.get("status")
    require(status == "prepared", "candidate " + str(status) + ": " + str(result.get("reason", "")),
            status if status in {"rejected", "failed"} else "blocked")
    require(result.get("filename") == request["target"] and result.get("app_path") == request["app_path"]
            and result.get("objective") == request["objective"], "candidate request binding differs")
    changes = result.get("changes")
    require(isinstance(changes, dict) and 1 <= len(changes) <= 4
            and request["app_path"] in changes, "candidate is empty or metadata-only")
    stem = Path(request["target"]).stem
    archive = "apps/archive/" + stem + "/"
    allowed = {request["app_path"], "apps/manifest.json",
               archive + "v" + str(app.get("generation", 0)) + ".html", archive + "molt-log.json"}
    require(set(changes) <= allowed, "candidate contains undeclared paths")
    bodies = {}
    for name, text in changes.items():
        relative(name)
        require(isinstance(text, str) and "\x00" not in text, "candidate must contain UTF-8 text")
        bodies[name] = text.encode("utf-8")
    require(sum(len(body) for body in bodies.values()) <= MAX_CHANGE_BYTES, "candidate exceeds total bound")
    updated = bodies[request["app_path"]]
    require(0 < len(updated) <= MAX_APP_BYTES and updated != original, "app is empty or unchanged")
    strip_metadata = lambda body: re.sub(
        rb"\s+", b"", re.sub(rb"<!--.*?-->|<meta\b[^>]*>", b"", body, flags=re.DOTALL | re.IGNORECASE))
    require(strip_metadata(updated) != strip_metadata(original), "app change is metadata-only")
    require(result.get("input_sha256") == digest(original) and result.get("output_sha256") == digest(updated),
            "candidate app hash mismatch")
    model = result.get("model", {})
    require(type(model.get("invoked")) is bool and type(model.get("attempts")) is int
            and 0 <= model["attempts"] <= 1 and model["invoked"] == (model["attempts"] == 1)
            and model.get("timeout_seconds") == request["timeout_seconds"], "candidate model bounds differ")
    require(request["allow_model"] or not model["invoked"], "model invocation was not authorized")
    require(isinstance(result.get("evidence"), dict) and result["evidence"], "candidate has no validation evidence")
    if "apps/manifest.json" in bodies:
        _manifest_delta(manifest, _json(bodies["apps/manifest.json"]), category_key, request["target"], len(updated))
    records = []
    for name, body in sorted(bodies.items()):
        previous, mode = blob(repo, request["base_commit"], name, optional=True)
        require(body != previous, "unchanged paths must not be declared")
        if name.startswith(archive) and name.endswith(".html"):
            require(previous is None and body == original, "archive must newly preserve the exact input app")
        if name == archive + "molt-log.json":
            old = _json(previous) if previous else []
            new = _json(body)
            require(isinstance(old, list) and isinstance(new, list) and new[:-1] == old
                    and len(new) == len(old) + 1 and isinstance(new[-1], dict), "archive log must be append-only")
        records.append({"path": name, "input_sha256": digest(previous) if previous is not None else None,
                        "output_sha256": digest(body), "bytes": len(body), "mode": mode or "100644"})
    return bodies, records


def _make_patch(proposal, request, bodies, records):
    source = proposal / "source"
    for record in records:
        name = record["path"]
        path = source / relative(name)
        no_symlinks(path)
        path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        if path.exists():
            path.unlink()
        write_new(path, bodies[name])
        path.chmod(int(record["mode"][-3:], 8))
        write_new(proposal / "changes" / name, bodies[name])
    git(source, "add", "--sparse", "--", *sorted(bodies))
    changed = git(source, "diff", "--cached", "--name-only", "-z", request["base_commit"]).decode().split("\0")
    require(sorted(name for name in changed if name) == sorted(bodies), "staged patch has undeclared changes")
    git(source, "diff", "--cached", "--check")
    git(source, "commit", "--quiet", "-m", "Molter review candidate: " + request["target"])
    commit = git(source, "rev-parse", "HEAD").decode().strip()
    require(git(source, "rev-parse", "HEAD^").decode().strip() == request["base_commit"], "candidate parent differs")
    for record in records:
        committed, mode = blob(source, commit, record["path"])
        require(committed == bodies[record["path"]] and mode == record["mode"],
                "Git candidate does not contain the declared exact bytes and mode")
    patch = git(source, "diff", "--binary", "--full-index", "--no-ext-diff", "--no-textconv",
                request["base_commit"], commit, "--")
    require(patch and len(patch) <= MAX_ARTIFACT_BYTES, "complete candidate patch exceeds bound or is empty")
    write_new(proposal / "proposal.patch", patch)
    git(source, "apply", "--reverse", "--check", "--cached", str(proposal / "proposal.patch"))
    git(source, "update-ref", "refs/heads/molter-proposal", commit)
    git(source, "bundle", "create", str(proposal / "candidate.bundle"),
        "refs/heads/molter-proposal", "^" + request["base_commit"])
    return commit, git(source, "rev-parse", "HEAD^{tree}").decode().strip()


def _cleanup_staging(proposal):
    for path in (proposal / "source", proposal / "capability/.git"):
        if path.exists():
            no_symlinks(path)
            shutil.rmtree(path)


def verify_proposal(proposal_dir, *, repo, base, repository, require_current_base=False,
                    _fixture=None, _pending_receipt=None):
    """Verify archived proof; opt into current-base readiness without applying it."""
    require(type(require_current_base) is bool, "readiness must be an explicit Boolean")
    repo, commit, tree = bind_source(repo, base, repository, require_current=require_current_base)
    proposal = output_path(proposal_dir, repo)
    require(proposal.is_dir() and (proposal / "request.json").is_file()
            and (_pending_receipt is not None or (proposal / "receipt.json").is_file()),
            "proposal is incomplete or interrupted", "failed")
    request_raw = read(proposal / "request.json")
    request = _json(request_raw)
    if _pending_receipt is not None:
        require(not (proposal / "receipt.json").exists(), "terminal receipt already exists")
    receipt_raw = (json_bytes(_pending_receipt) if _pending_receipt is not None
                   else read(proposal / "receipt.json"))
    receipt = _json(receipt_raw)
    require(request_raw == json_bytes(request) and receipt_raw == json_bytes(receipt), "proposal JSON bytes changed")
    require(receipt.get("integrity_sha256") == digest(json_bytes(
        {key: value for key, value in receipt.items() if key != "integrity_sha256"})), "receipt integrity mismatch")
    require(request.get("base_commit") == commit and request.get("base_tree") == tree
            and request.get("repository") == repository.casefold(), "proposal source/base binding differs")
    require(request.get("schema") == "molter-review-request/v1"
            and receipt.get("schema") == "molter-review-proposal/v1", "unsupported proposal schema")
    _verify_adapter_identity(proposal, repo, commit, request.get("adapter"))
    require(receipt.get("request_id") == digest(request_raw), "immutable request identity mismatch")
    require(all(receipt.get(key) == request.get(key)
                for key in ("repository", "base_commit", "target", "app_path")),
            "receipt request projection differs")
    require(receipt.get("artifacts") == inventory(proposal), "proposal artifacts are missing, tampered or undeclared")
    require(receipt.get("delivery") == {"state": "not_submitted", "externally_submitted": False,
                                      "deployment_verified": False}
            and receipt.get("deployment_verified") is False, "adapter cannot attest submission or deployment")
    require(receipt.get("status") in {"prepared", "fixture_prepared", "rejected", "failed", "blocked"},
            "unsupported proposal state")
    require(type(receipt.get("qualified")) is bool
            and receipt["qualified"] == (receipt["status"] == "prepared"), "proposal qualification state differs")
    if receipt["status"] in {"prepared", "fixture_prepared"}:
        target, app_path, manifest, key, app, original = select_app(repo, commit, request["target"])
        require(app_path == request["app_path"] and receipt.get("target") == target, "proposal target differs")
        result = _json(read(proposal / "candidate-result.json"))
        require(result.get("change_paths") == [item["path"] for item in receipt["changes"]],
                "candidate declared paths differ")
        result["changes"] = {item["path"]: read(proposal / "changes" / relative(item["path"])).decode("utf-8")
                             for item in receipt["changes"]}
        _, records = validate_candidate(result, repo, request, manifest, key, app, original)
        require(records == receipt["changes"], "candidate path fingerprints differ")
        if require_current_base:
            git(repo, "apply", "--check", "--cached", str(proposal / "proposal.patch"))
        git(repo, "bundle", "verify", str(proposal / "candidate.bundle"))
        heads = git(repo, "bundle", "list-heads", str(proposal / "candidate.bundle")).decode().strip()
        require(heads == receipt["candidate_commit"] + " refs/heads/molter-proposal", "bundle candidate binding differs")
        context = _json(read(proposal / "qualification-context.json"))
        require(context == {**request, "request_id": receipt["request_id"],
                            "candidate_commit": receipt["candidate_commit"],
                            "candidate_tree": receipt["candidate_tree"],
                            "implementation_commit": receipt["implementation_commit"]},
                "qualification context binding differs")
        if receipt["status"] == "fixture_prepared":
            require(_fixture is not None and request["fixture"] == _fixture.identity
                    and receipt["qualified"] is False, "fixture evidence is not real capability qualification")
            _fixture.verify(proposal, context)
        else:
            require(_fixture is None and request["fixture"] is None and receipt["qualified"] is True,
                    "real qualification cannot use fixture evidence")
            # This worker only validates retained reports/RAPP/registry; it never executes checks.
            qualification = _verify_worker(proposal)
            require(qualification == receipt["qualification"], "qualification projection differs")
            implementation_heads = git(repo, "bundle", "list-heads", str(proposal / "capability.bundle")).decode().strip()
            require(implementation_heads == receipt["implementation_commit"] + " HEAD",
                    "capability implementation bundle binding differs")
            git(repo, "bundle", "verify", str(proposal / "capability.bundle"))
            capsule = _json(read(proposal / "capability/handoff/source.json"))
            app_record = next(item for item in records if item["path"] == app_path)
            require(capsule["origin"] == {"repository": request["repository"],
                                          "commit": receipt["candidate_commit"],
                                          "tree": receipt["candidate_tree"]}
                    and len(capsule["files"]) == 1
                    and capsule["files"][0] == {
                        "path": app_path, "mode": app_record["mode"], "sha256": app_record["output_sha256"],
                        "bytes": app_record["bytes"], "text": result["changes"][app_path],
                    },
                    "selected-source capsule differs from complete proposal")
    return _summary(receipt, readiness=require_current_base)


def _verify_worker(proposal):
    completed = subprocess.run(
        [sys.executable, "-B", str(Path(__file__).with_name("molter_capability_worker.py")),
         "verify", "--proposal", str(proposal), "--context", str(proposal / "qualification-context.json")],
        cwd=proposal, env=environment(), stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, check=False,
    )
    require(completed.returncode == 0, "retained RAPP/registry verification failed: "
            + completed.stderr.decode("utf-8", errors="replace")[:400], "failed")
    return _json(completed.stdout)


def prepare_proposal(proposal_dir, *, repo, base, repository, target=None, candidate_file=None,
                     allow_model=False, objective=DEFAULT_OBJECTIVE, rapp_ref=None, dry_run=False, _fixture=None):
    """Preserve at most one review candidate. No publishers, timers or acceptance-ledger writes.

    Tests may explicitly supply _fixture (identity/prepare/qualify/verify); such
    artifacts are fixture_prepared and can never become a qualified proposal.
    """
    repo, commit, tree = bind_source(repo, base, repository)
    proposal = output_path(proposal_dir, repo)
    target, app_path, manifest, key, app, original = select_app(repo, commit, target)
    require(isinstance(objective, str) and 0 < len(objective) <= 2048
            and not any(ord(char) < 32 for char in objective), "objective must be bounded plain text")
    require(type(allow_model) is bool and not (candidate_file is not None and allow_model),
            "choose an operator candidate or explicit model opt-in, not both")
    supplied = read(absolute(candidate_file), MAX_APP_BYTES) if candidate_file is not None else None
    if supplied is not None:
        supplied.decode("utf-8")
    request = {
        "schema": "molter-review-request/v1", "repository": repository.casefold(),
        "base_commit": commit, "base_tree": tree, "target": target, "app_path": app_path,
        "objective": objective, "candidate_sha256": digest(supplied) if supplied is not None else None,
        "allow_model": allow_model, "timeout_seconds": TIMEOUT,
        "capability_manifest_sha256": MANIFEST_SHA256, "rapp_commit": RAPP_COMMIT,
        "adapter": _adapter_identity(),
        "fixture": _fixture.identity if _fixture is not None else None,
    }
    if proposal.exists():
        existing = verify_proposal(proposal, repo=repo, base=commit, repository=repository,
                                   require_current_base=True, _fixture=_fixture)
        require(existing["request_id"] == digest(json_bytes(request)), "proposal directory belongs to another request")
        return {**existing, "noop": True}
    if dry_run:
        return {
            "status": "dry_run", "reason": "read-only plan; no generation, qualification or delivery",
            "request_id": digest(json_bytes(request)), "request": request, "qualified": False,
            "deployment_verified": False, "would_prepare": supplied is not None or allow_model,
        }
    proposal.mkdir(mode=0o700)
    write_new(proposal / "request.json", json_bytes(request))
    for name, sha in request["adapter"].items():
        body = read(Path(__file__).with_name(name))
        require(digest(body) == sha, "adapter changed during request creation", "failed")
        write_new(proposal / "adapter" / name, body)
    if supplied is not None:
        write_new(proposal / "candidate-input.html", supplied)
    try:
        require(supplied is not None or allow_model, "candidate file or explicit --allow-model is required", "blocked")
        files = _package_inputs(repo, commit, rapp_ref) if _fixture is None else None
        implementation = _stage_package(proposal, files) if files is not None else None
        _stage_source(repo, commit, proposal / "source", app_path, target)
        if _fixture is None:
            _worker("preflight", proposal, proposal / "request.json")
        before = git(proposal / "source", "status", "--porcelain=v1", "--untracked-files=all")
        require(not before, "capability preflight modified its source snapshot")
        result = (_worker("candidate", proposal, proposal / "request.json") if _fixture is None
                  else _fixture.prepare(proposal / "source", request, supplied))
        after = git(proposal / "source", "status", "--porcelain=v1", "--untracked-files=all",
                    "--ignored=matching")
        require(before == after, "candidate preparation modified its source snapshot")
        require(git(proposal / "source", "rev-parse", "HEAD").decode().strip() == commit,
                "candidate preparation changed its base")
        require(isinstance(result, dict), "invalid candidate result", "failed")
        write_new(proposal / "candidate-result.json", json_bytes({
            **{k: v for k, v in result.items() if k != "changes"},
            "change_paths": sorted(result["changes"]) if isinstance(result.get("changes"), dict) else None,
        }))
        bodies, records = validate_candidate(result, repo, request, manifest, key, app, original)
        candidate_commit, candidate_tree = _make_patch(proposal, request, bodies, records)
        context = {**request, "request_id": digest(json_bytes(request)),
                   "candidate_commit": candidate_commit, "candidate_tree": candidate_tree,
                   "implementation_commit": implementation}
        write_new(proposal / "qualification-context.json", json_bytes(context))
        qualification = (_worker("qualify", proposal, proposal / "qualification-context.json", timeout=420)
                         if _fixture is None else _fixture.qualify(proposal, context))
        require(_fixture is not None or qualification.get("qualified") is True, "source qualification did not pass", "failed")
        require(_fixture is None or (qualification.get("kind") == "test_fixture"
                                     and qualification.get("qualified") is False),
                "fixture evidence must never claim real qualification", "failed")
        bind_source(repo, commit, repository)
        _cleanup_staging(proposal)
        receipt = _receipt(
            proposal, request, "prepared" if _fixture is None else "fixture_prepared",
            "local review candidate preserved; submission and deployment are not established",
            validate=lambda pending: verify_proposal(
                proposal, repo=repo, base=commit, repository=repository,
                require_current_base=True, _fixture=_fixture, _pending_receipt=pending,
            ),
            qualified=_fixture is None, qualification=qualification, changes=records,
            candidate_commit=candidate_commit, candidate_tree=candidate_tree,
            implementation_commit=implementation, patch="proposal.patch", bundle="candidate.bundle",
        )
        return _summary(receipt, readiness=True)
    except Exception as exc:
        if (proposal / "receipt.json").exists():
            raise
        _cleanup_staging(proposal)
        status = exc.status if isinstance(exc, ProposalError) else "failed"
        receipt = _receipt(proposal, request, status, str(exc))
        return _summary(receipt)


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ProposalError(message, "blocked")


def parser():
    cli = JsonArgumentParser(description=__doc__)
    sub = cli.add_subparsers(dest="command", required=True, parser_class=JsonArgumentParser)
    for command in ("prepare", "verify", "status"):
        child = sub.add_parser(command)
        child.add_argument("proposal")
        child.add_argument("--repo", required=True)
        child.add_argument("--base", required=True)
        child.add_argument("--repository", required=True)
        if command == "prepare":
            child.add_argument("--target")
            child.add_argument("--candidate-file")
            child.add_argument("--allow-model", action="store_true")
            child.add_argument("--objective", default=DEFAULT_OBJECTIVE)
            child.add_argument("--rapp-ref")
            child.add_argument("--dry-run", action="store_true")
        else:
            child.add_argument("--require-current-base", action="store_true",
                               help="also require clean current HEAD and check patch application; never apply")
    return cli


def main(argv=None):
    try:
        args = parser().parse_args(argv)
        kwargs = dict(repo=args.repo, base=args.base, repository=args.repository)
        with redirect_stdout(sys.stderr):
            if args.command == "prepare":
                result = prepare_proposal(
                    args.proposal, **kwargs, target=args.target, candidate_file=args.candidate_file,
                    allow_model=args.allow_model, objective=args.objective, rapp_ref=args.rapp_ref, dry_run=args.dry_run,
                )
            else:
                result = verify_proposal(args.proposal, **kwargs, require_current_base=args.require_current_base)
        print(json.dumps(result, sort_keys=True, ensure_ascii=False))
        return 0 if result["status"] in {"prepared", "dry_run"} else 1
    except Exception as exc:
        result = {"status": exc.status if isinstance(exc, ProposalError) else "failed",
                  "reason": str(exc), "qualified": False, "deployment_verified": False}
        print(json.dumps(result, sort_keys=True))
        print("molter proposal: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
