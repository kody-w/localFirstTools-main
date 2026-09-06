#!/usr/bin/env python3
"""Transport or explicitly replay a prepared mutation; never submit or apply it."""

import argparse
import io
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tarfile
import tempfile

import molter_capabilities as proposals


MAX_ARCHIVE_BYTES = proposals.MAX_PROPOSAL_BYTES + 2 * 1024 * 1024


def _prepared(directory, binding):
    result = proposals.verify_proposal(directory, **binding)
    proposals.require(result["status"] == "prepared" and result["qualified"] is True,
                      "only a qualified prepared proposal can be transported or replayed", "blocked")
    root = proposals.output_path(directory, Path(binding["repo"]).absolute())
    return root, result


def _trusted_package(files, repo, base):
    expected = proposals._package_inputs(repo, base, None)
    for name, body in expected.items():
        proposals.require(files.get("capability/" + name) == body,
                          "archived execution support differs from the committed producer package")


def _records(root):
    records = proposals.inventory(root)
    receipt = root / "receipt.json"
    info = receipt.stat()
    proposals.require(info.st_uid == os.getuid() and info.st_nlink == 1
                      and not stat.S_IMODE(info.st_mode) & 0o7022,
                      "unsafe receipt ownership or mode")
    body = proposals.read(receipt)
    records.append({"path": "receipt.json", "bytes": len(body),
                    "sha256": proposals.digest(body), "mode": stat.S_IMODE(info.st_mode)})
    return sorted(records, key=lambda record: record["path"])


def pack_proposal(directory, archive, **binding):
    root, result = _prepared(directory, binding)
    output = proposals.output_path(archive, Path(binding["repo"]).absolute())
    proposals.require(root not in output.parents and output != root,
                      "archive must be outside the preserved proposal")
    proposals.require(not output.exists(), "archive destination already exists")
    records = _records(root)
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as bundle:
        for record in records:
            name = proposals.relative(record["path"]).as_posix()
            body = proposals.read(root / name)
            proposals.require(len(body) == record["bytes"]
                              and proposals.digest(body) == record["sha256"],
                              "artifact changed while packaging")
            mode = record["mode"]
            proposals.require(type(mode) is int and 0 <= mode <= 0o777 and not mode & 0o022,
                              "unsafe artifact permissions")
            member = tarfile.TarInfo(name)
            member.size, member.mode, member.mtime = len(body), mode, 0
            member.uid = member.gid = 0
            member.uname = member.gname = ""
            bundle.addfile(member, io.BytesIO(body))
            proposals.require(buffer.tell() <= MAX_ARCHIVE_BYTES, "archive exceeds byte bound")
    body = buffer.getvalue()
    proposals.require(len(body) <= MAX_ARCHIVE_BYTES and _records(root) == records,
                      "archive exceeded its bound or source changed")
    proposals.write_new(output, body)
    return {"status": "packed", "request_id": result["request_id"],
            "archive_sha256": proposals.digest(body), "bytes": len(body),
            "deployment_verified": False}


def _archive_files(archive):
    raw = proposals.read(proposals.absolute(archive), MAX_ARCHIVE_BYTES)
    files, modes, total = {}, {}, 0
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as bundle:
        for member in bundle:
            name = proposals.relative(member.name).as_posix()
            proposals.require(member.isfile() and not member.issparse()
                              and set(member.pax_headers) <= {"path"},
                              "archive supports regular files only")
            proposals.require(name not in files and len(files) <= proposals.MAX_ARTIFACTS,
                              "duplicate archive member or file bound exceeded")
            proposals.require(0 <= member.size <= proposals.MAX_ARTIFACT_BYTES
                              and 0 <= member.mode <= 0o777 and not member.mode & 0o022,
                              "unsafe archive size or mode")
            total += member.size
            proposals.require(total <= MAX_ARCHIVE_BYTES, "archive expansion exceeds bound")
            stream = bundle.extractfile(member)
            proposals.require(stream is not None, "archive member has no content")
            body = stream.read(member.size + 1)
            proposals.require(len(body) == member.size, "archive member length differs")
            files[name], modes[name] = body, member.mode
    proposals.require("receipt.json" in files, "archive receipt is missing")
    receipt = proposals._json(files["receipt.json"])
    proposals.require(files["receipt.json"] == proposals.json_bytes(receipt)
                      and receipt.get("schema") == "molter-review-proposal/v1",
                      "archive receipt is not canonical")
    proposals.require(receipt.get("integrity_sha256") == proposals.digest(proposals.json_bytes(
        {key: value for key, value in receipt.items() if key != "integrity_sha256"})),
        "archive receipt integrity differs")
    records = receipt.get("artifacts")
    proposals.require(isinstance(records, list), "archive artifact inventory is missing")
    names = [proposals.relative(record["path"]).as_posix() for record in records]
    proposals.require(len(names) == len(set(names)) and set(files) == set(names) | {"receipt.json"},
                      "archive members differ from the receipt")
    for record in records:
        name = record["path"]
        proposals.require(len(files[name]) == record["bytes"]
                          and proposals.digest(files[name]) == record["sha256"]
                          and modes[name] == record["mode"],
                          "archive bytes or permissions differ from the receipt")
    return files, modes


def unpack_proposal(archive, directory, **binding):
    repo, base, _ = proposals.bind_source(binding["repo"], binding["base"], binding["repository"],
                                         require_current=False)
    output = proposals.output_path(directory, repo)
    proposals.require(not output.exists(), "unpack destination already exists")
    files, modes = _archive_files(archive)
    _trusted_package(files, repo, base)
    output.mkdir(mode=0o700)
    try:
        for name, body in files.items():
            target = output / proposals.relative(name)
            proposals.write_new(target, body)
            target.chmod(modes[name])
        result = proposals.verify_proposal(output, **binding)
        proposals.require(result["status"] == "prepared", "unpacked proposal is not qualified")
    except (ValueError, OSError, KeyError, TypeError, tarfile.TarError):
        shutil.rmtree(output)
        raise
    return {**result, "transport": "unpacked", "deployment_verified": False}


def replay_proposal(directory, *, allow_checks=False, **binding):
    proposals.require(allow_checks is True, "replay requires explicit --allow-checks", "blocked")
    root, result = _prepared(directory, binding)
    repo, base, _ = proposals.bind_source(binding["repo"], binding["base"], binding["repository"],
                                         require_current=False)
    before = _records(root)
    package = {record["path"]: proposals.read(root / record["path"])
               for record in before if record["path"].startswith("capability/")}
    _trusted_package(package, repo, base)
    context = proposals._json(proposals.read(root / "qualification-context.json"))
    with tempfile.TemporaryDirectory(prefix=".mutation-replay-", dir=root.parent) as temporary:
        work = Path(temporary).resolve()
        for name, body in package.items():
            proposals.write_new(work / proposals.relative(name), body)
        proposals.write_new(work / "qualification-context.json", proposals.json_bytes(context))
        source = work / "source"
        proposals._stage_source(repo, base, source, context["app_path"], context["target"])
        proposals.git(source, "fetch", "--quiet", "--no-tags", str(root / "candidate.bundle"),
                      "refs/heads/molter-proposal:refs/heads/replay")
        proposals.git(source, "checkout", "--quiet", "--detach", context["candidate_commit"])
        proposals.require(proposals.git(source, "rev-parse", "HEAD^{tree}").decode().strip()
                          == context["candidate_tree"], "restored candidate tree differs")
        measurement = proposals._worker("replay", work, work / "qualification-context.json", timeout=330)
        proposals.require(measurement.get("replayed") is True, "transport replay did not pass")
    proposals.require(_records(root) == before, "replay changed the preserved artifact")
    return {"status": "replayed", "request_id": result["request_id"],
            "measurement": measurement, "preserved_artifacts_unchanged": True,
            "new_qualification_or_registry_entry": False, "deployment_verified": False}


def main(argv=None):
    parser = proposals.JsonArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True, parser_class=proposals.JsonArgumentParser)
    for name in ("pack", "unpack", "replay"):
        command = commands.add_parser(name)
        command.add_argument("source")
        if name != "replay":
            command.add_argument("destination")
        else:
            command.add_argument("--allow-checks", action="store_true")
        command.add_argument("--repo", required=True)
        command.add_argument("--base", required=True)
        command.add_argument("--repository", required=True)
    try:
        args = parser.parse_args(argv)
        binding = dict(repo=args.repo, base=args.base, repository=args.repository)
        if args.command == "pack":
            result = pack_proposal(args.source, args.destination, **binding)
        elif args.command == "unpack":
            result = unpack_proposal(args.source, args.destination, **binding)
        else:
            result = replay_proposal(args.source, allow_checks=args.allow_checks, **binding)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ValueError, OSError, KeyError, TypeError, tarfile.TarError) as error:
        print(json.dumps({"status": "blocked", "reason": str(error), "deployment_verified": False}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
