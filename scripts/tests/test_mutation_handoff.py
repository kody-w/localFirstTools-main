"""Archive adversaries cannot turn transport into filesystem or code authority."""

import copy
import io
from pathlib import Path
import sys
import tarfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import molter_capabilities as proposals
import mutation_handoff as handoff


ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "docs/molter-capabilities/pilot/proposal.tar"
BINDING = {"repo": ROOT, "base": "27f08a6a0ea928ae678288becada60569d85a2b8",
           "repository": "kody-w/localFirstTools-main"}


def archive(tmp_path, members):
    target = tmp_path / "test.tar"
    with tarfile.open(target, "w", format=tarfile.PAX_FORMAT) as output:
        for item, body in members:
            output.addfile(item, io.BytesIO(body) if item.isfile() else None)
    return target


@pytest.mark.parametrize("name", ["../escape", "/absolute", "a/../escape", "a//b", ".git/config"])
def test_unsafe_archive_paths_are_rejected(tmp_path, name):
    member = tarfile.TarInfo(name)
    member.size, member.mode = 1, 0o600
    with pytest.raises((proposals.ProposalError, tarfile.TarError)):
        handoff._archive_files(archive(tmp_path, [(member, b"x")]))
    assert not (tmp_path.parent / "escape").exists()


@pytest.mark.parametrize("kind", [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE, tarfile.CHRTYPE])
def test_archive_links_and_special_files_are_rejected(tmp_path, kind):
    member = tarfile.TarInfo("alias")
    member.type, member.linkname = kind, "../elsewhere"
    with pytest.raises(proposals.ProposalError, match="regular files"):
        handoff._archive_files(archive(tmp_path, [(member, b"")]))


def test_duplicate_members_are_rejected(tmp_path):
    member = tarfile.TarInfo("receipt.json")
    member.size, member.mode = 2, 0o600
    with pytest.raises(proposals.ProposalError, match="duplicate"):
        handoff._archive_files(archive(tmp_path, [(member, b"{}"), (copy.copy(member), b"{}")]))


def test_oversized_declared_member_is_rejected_before_expansion(tmp_path):
    member = tarfile.TarInfo("huge")
    member.size, member.mode = proposals.MAX_ARTIFACT_BYTES + 1, 0o600
    target = tmp_path / "huge.tar"
    target.write_bytes(member.tobuf() + b"\0" * 1024)
    with pytest.raises(proposals.ProposalError, match="size or mode"):
        handoff._archive_files(target)


@pytest.mark.parametrize("mode", [0o666, 0o4755])
def test_unsafe_permissions_are_rejected(tmp_path, mode):
    member = tarfile.TarInfo("unsafe")
    member.size, member.mode = 1, mode
    with pytest.raises(proposals.ProposalError, match="size or mode"):
        handoff._archive_files(archive(tmp_path, [(member, b"x")]))


def test_resealed_execution_support_is_rejected_before_writes(tmp_path, monkeypatch):
    files, modes = handoff._archive_files(ARCHIVE)
    name = "capability/tests/__init__.py"
    files[name] = b"raise RuntimeError('untrusted execution support')\n"
    receipt = proposals._json(files["receipt.json"])
    record = next(item for item in receipt["artifacts"] if item["path"] == name)
    record.update(bytes=len(files[name]), sha256=proposals.digest(files[name]))
    receipt.pop("integrity_sha256")
    receipt["integrity_sha256"] = proposals.digest(proposals.json_bytes(receipt))
    files["receipt.json"] = proposals.json_bytes(receipt)
    members = []
    for path, body in files.items():
        member = tarfile.TarInfo(path)
        member.size, member.mode = len(body), modes[path]
        members.append((member, body))
    target = archive(tmp_path, members)
    destination = tmp_path / "untrusted"
    monkeypatch.setattr(proposals, "verify_proposal", lambda *args, **kwargs: pytest.fail("imported before code pin check"))
    with pytest.raises(proposals.ProposalError, match="execution support"):
        handoff.unpack_proposal(target, destination, **BINDING)
    assert not destination.exists()


def test_unpack_never_overwrites_an_existing_destination(tmp_path):
    destination = tmp_path / "existing"
    destination.mkdir()
    marker = destination / "keep"
    marker.write_text("original")
    with pytest.raises(proposals.ProposalError, match="already exists"):
        handoff.unpack_proposal(ARCHIVE, destination, **BINDING)
    assert marker.read_text() == "original"


def test_replay_without_authority_fails_before_reading_or_execution(monkeypatch):
    monkeypatch.setattr(handoff, "_prepared", lambda *args: pytest.fail("replay began without permission"))
    with pytest.raises(proposals.ProposalError, match="allow-checks"):
        handoff.replay_proposal("unused", **BINDING)
