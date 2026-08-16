"""Tests for the static syndication builder and local-first sync client."""

import hashlib
import json
import shutil
import sys
import threading
from contextlib import contextmanager
from email.utils import formatdate
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse
from xml.etree import ElementTree

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import build_syndication as builder
import rappterzoo_sync as sync_client


def make_frame(
    sequence,
    previous=None,
    kind="zoo.observation",
    event="test-frame",
    payload_updates=None,
):
    payload = {
        "display_name": "Test Zoo",
        "event": event,
        "event_id": "test-frame:{}".format(sequence),
        "organism": "test-zoo",
        "schema": builder.FRAME_SCHEMA,
        "visibility": "public-metadata",
    }
    payload.update(payload_updates or {})
    frame = {
        "frame_hash": "0" * 64,
        "kind": kind,
        "payload": payload,
        "payload_hash": builder.frame_hash_value(
            builder.PARTICLE_SPACE,
            payload,
        ),
        "prev": previous["payload_hash"] if previous else None,
        "prev_wave": previous["frame_hash"] if previous else None,
        "seq": sequence,
        "sig": None,
        "spec": "rapp/1",
        "stream_id": "net:rappterzoo",
        "utc": "2026-08-15T{:02d}:00:00.000Z".format(sequence),
    }
    wave = {
        key: value
        for key, value in frame.items()
        if key not in {"frame_hash", "sig"}
    }
    frame["frame_hash"] = builder.frame_hash_value(
        builder.WAVE_SPACE,
        wave,
    )
    return frame


def make_fair_release_frame(previous):
    return make_frame(
        previous["seq"] + 1,
        previous,
        kind="zoo.observation",
        event="agent-worlds-fair-release",
        payload_updates={
            "app_file": "agent-worlds-fair.html",
            "approval_basis": (
                "verified-github-actions-oidc-attestation"
            ),
            "approval_evidence": {
                "actor": "release-operator",
                "attestation_sha256": "a" * 64,
                "aud": "rappterzoo-agent-fair-release",
                "environment": "agent-fair-production",
                "event_name": "workflow_dispatch",
                "exp": 1786840000,
                "iss": "https://token.actions.githubusercontent.com",
                "nbf": 1786750000,
                "ref": "refs/heads/main",
                "repository": "kody-w/localFirstTools-main",
                "run_id": "123456789",
                "workflow_ref": (
                    "kody-w/localFirstTools-main/.github/workflows/"
                    "agent-fair-release.yml@refs/heads/main"
                ),
            },
            "assurance": "unsigned-structural-unverified",
            "customer_approved": True,
            "display_name": "Agent World's Fair",
            "district_digest": builder.AGENT_FAIR_BASE_DISTRICT_DIGEST,
            "event_id": builder.AGENT_FAIR_RELEASE_EVENT_ID,
            "fair_bundle_digest": builder.AGENT_FAIR_BASE_BUNDLE_DIGEST,
            "fair_event_head": builder.AGENT_FAIR_BASE_EVENT_HEAD,
            "organism": builder.AGENT_FAIR_DISTRICT_ID,
            "organism_type": "agent-worlds-fair-district",
            "release_candidate_digest": (
                builder.AGENT_FAIR_RELEASE_CANDIDATE_DIGEST
            ),
            "winner_submission_ids": builder.AGENT_FAIR_WINNERS,
        },
    )


def rehash_frame(frame):
    frame["payload_hash"] = builder.frame_hash_value(
        builder.PARTICLE_SPACE,
        frame["payload"],
    )
    wave = {
        key: value
        for key, value in frame.items()
        if key not in {"frame_hash", "sig"}
    }
    frame["frame_hash"] = builder.frame_hash_value(
        builder.WAVE_SPACE,
        wave,
    )


def write_ledger(root, count=2):
    frames = []
    previous = None
    for sequence in range(count):
        frame = make_frame(sequence, previous)
        frames.append(frame)
        previous = frame
    ledger = root / "apps" / "organism-frames.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_bytes(
        b"".join(
            builder.canonical_frame_bytes(frame) + b"\n"
            for frame in frames
        )
    )
    return frames


def write_frames(root, frames):
    ledger = root / "apps" / "organism-frames.jsonl"
    ledger.write_bytes(
        b"".join(
            builder.canonical_frame_bytes(frame) + b"\n"
            for frame in frames
        )
    )


def release_agent_fair(root):
    frames = builder.read_ledger(root / "apps" / "organism-frames.jsonl")
    release = make_fair_release_frame(frames[-1])
    write_frames(root, frames + [release])
    return release


def write_manifest(root, app_names=("alpha.html", "beta.html")):
    folder = root / "apps" / "demo"
    folder.mkdir(parents=True, exist_ok=True)
    apps = []
    for index, name in enumerate(app_names):
        data = (
            "<!DOCTYPE html><title>{0}</title>"
            "<main data-index=\"{1}\">{0}</main>\n"
        ).format(name, index).encode("utf-8")
        (folder / name).write_bytes(data)
        apps.append({
            "complexity": "simple",
            "created": "2026-08-15",
            "description": "Fixture {}".format(name),
            "featured": False,
            "file": name,
            "tags": ["fixture", "local-first"],
            "title": "Fixture {}".format(name),
            "type": "interactive",
        })
    manifest = {
        "categories": {
            "demo": {
                "apps": apps,
                "color": "fixture",
                "count": len(apps),
                "folder": "demo",
                "title": "Demo",
            }
        },
        "meta": {
            "lastUpdated": "2026-08-15",
            "version": "1.0",
        },
    }
    (root / "apps" / "manifest.json").write_bytes(
        builder.stable_json_bytes(manifest)
    )
    return manifest


def make_repo(tmp_path, app_names=("alpha.html", "beta.html"), frames=2):
    root = tmp_path / "repo"
    root.mkdir(parents=True)
    manifest = write_manifest(root, app_names)
    ledger_frames = write_ledger(root, frames)
    return root, manifest, ledger_frames


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    path.write_bytes(builder.stable_json_bytes(value))


class StaticFixtureServer:
    def __init__(self, root):
        self.root = root.resolve()
        self.requests = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, _format, *args):
                return

            def do_GET(self):
                parsed = urlparse(self.path)
                relative = unquote(parsed.path).lstrip("/")
                target = (outer.root / relative).resolve()
                try:
                    target.relative_to(outer.root)
                except ValueError:
                    self.send_error(403)
                    return
                if not target.is_file():
                    self.send_error(404)
                    return
                data = target.read_bytes()
                etag = '"{}"'.format(hashlib.sha256(data).hexdigest())
                last_modified = formatdate(
                    target.stat().st_mtime,
                    usegmt=True,
                )
                outer.requests.append({
                    "if_modified_since": self.headers.get(
                        "If-Modified-Since"
                    ),
                    "if_none_match": self.headers.get("If-None-Match"),
                    "path": parsed.path,
                })
                if_none_match = self.headers.get("If-None-Match")
                if_modified_since = self.headers.get("If-Modified-Since")
                not_modified = (
                    if_none_match == etag
                    if if_none_match is not None
                    else if_modified_since == last_modified
                )
                if not_modified:
                    self.send_response(304)
                    self.send_header("ETag", etag)
                    self.send_header("Last-Modified", last_modified)
                    self.end_headers()
                    return
                content_type = "application/json"
                if target.suffix == ".html":
                    content_type = "text/html; charset=utf-8"
                elif target.suffix == ".xml":
                    content_type = "application/atom+xml"
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("ETag", etag)
                self.send_header("Last-Modified", last_modified)
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )

    @property
    def base_url(self):
        return "http://127.0.0.1:{}/".format(
            self.server.server_address[1]
        )

    @property
    def index_url(self):
        return self.base_url + "apps/syndication/index.json"

    def start(self):
        self.thread.start()
        return self

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


@contextmanager
def serving(root):
    server = StaticFixtureServer(root).start()
    try:
        yield server
    finally:
        server.close()


def build_served(root, server, synthetic_test_mode=False):
    return builder.build(
        root,
        server.base_url,
        synthetic_test_mode=synthetic_test_mode,
    )


def mutate_app(root, name="alpha.html"):
    path = root / "apps" / "demo" / name
    path.write_bytes(path.read_bytes() + b"<!-- changed -->\n")


def remove_manifest_app(root, name):
    manifest_path = root / "apps" / "manifest.json"
    manifest = read_json(manifest_path)
    category = manifest["categories"]["demo"]
    category["apps"] = [
        app
        for app in category["apps"]
        if app["file"] != name
    ]
    category["count"] = len(category["apps"])
    write_json(manifest_path, manifest)


def copy_agent_park(root):
    target = root / "apps" / "agent-park"
    target.mkdir(parents=True)
    source_events = [
        json.loads(line)
        for line in (
            ROOT / "apps" / "agent-park" / "events.jsonl"
        ).read_text().splitlines()[:47]
    ]
    write_park_events(target, source_events)
    shutil.copyfile(
        ROOT / "apps" / "agent-park" / "agent-contract.json",
        target / "agent-contract.json",
    )
    ledger_bytes = (target / "events.jsonl").read_bytes()
    state = {
        "agent_contract": "agent-contract.json",
        "economy": {
            "balanced": True,
            "real_money": False,
        },
        "event_ledger": {
            "event_count": len(source_events),
            "head": source_events[-1]["event_hash"],
            "path": "events.jsonl",
            "sha256": hashlib.sha256(ledger_bytes).hexdigest(),
        },
        "night_count": 7,
        "park_id": "park.rappterzoo-agent-amusement-park",
        "schema": "rappterzoo-agent-amusement-park/1",
        "visibility": "public-metadata",
    }
    write_json(target / "park-state.json", state)
    return target


def copy_agent_fair(root):
    target = root / "apps" / "agent-fair"
    target.mkdir(parents=True)
    for name in (
        "agent-contract.json",
        "district.json",
        "events.jsonl",
        "fair-state.json",
    ):
        shutil.copyfile(
            ROOT / "apps" / "agent-fair" / name,
            target / name,
        )
    return target


def read_fair_events(target):
    return [
        json.loads(line)
        for line in (target / "events.jsonl").read_text().splitlines()
        if line
    ]


def write_fair_events(target, events):
    data = builder.agent_fair_event_ledger_bytes(events)
    (target / "events.jsonl").write_bytes(data)
    return data


def append_fair_event(events):
    event = {
        "fair_id": builder.AGENT_FAIR_ID,
        "kind": "fair.audit",
        "payload": {
            "result": "future-customer-approved-prefix-growth",
        },
        "prev": events[-1]["event_hash"],
        "schema": builder.AGENT_FAIR_EVENT_SCHEMA,
        "seq": len(events),
        "utc": "2026-08-16T12:23:00.000Z",
        "visibility": "public-metadata",
    }
    event["payload_hash"] = builder.frame_hash_value(
        builder.AGENT_FAIR_PAYLOAD_SPACE,
        event["payload"],
    )
    event["event_hash"] = builder.frame_hash_value(
        builder.AGENT_FAIR_EVENT_SPACE,
        event,
    )
    return events + [event]


def rebind_fair_bundle(target, update_contract_bundle=True):
    events = read_fair_events(target)
    state = read_json(target / "fair-state.json")
    contract = read_json(target / "agent-contract.json")
    district = read_json(target / "district.json")
    event_bytes = builder.agent_fair_event_ledger_bytes(events)
    state["event_ledger"].update({
        "event_count": len(events),
        "head": events[-1]["event_hash"],
        "sha256": hashlib.sha256(event_bytes).hexdigest(),
    })

    projected_contract = json.loads(json.dumps(contract))
    projected_contract["integrity"].pop("bundle_digest", None)
    projected_contract["integrity"].pop("contract_digest", None)
    contract_digest = builder.frame_hash_value(
        builder.AGENT_FAIR_CONTRACT_SPACE,
        projected_contract,
    )
    contract["integrity"]["contract_digest"] = contract_digest

    district["integrity"]["contract_digest"] = contract_digest
    projected_district = json.loads(json.dumps(district))
    projected_district["integrity"].pop("bundle_digest", None)
    projected_district["integrity"].pop("district_digest", None)
    district_digest = builder.frame_hash_value(
        builder.AGENT_FAIR_DISTRICT_SPACE,
        projected_district,
    )
    district["integrity"]["district_digest"] = district_digest

    state["agent_contract"]["contract_digest"] = contract_digest
    state["district"]["district_digest"] = district_digest
    state["district"]["resource_totals"] = json.loads(
        json.dumps(district["resource_totals"])
    )
    state["integrity"]["contract_digest"] = contract_digest
    state["integrity"]["district_digest"] = district_digest
    projected_state = json.loads(json.dumps(state))
    projected_state["integrity"].pop("bundle_digest", None)
    projected_state["integrity"].pop("state_digest", None)
    state_digest = builder.frame_hash_value(
        builder.AGENT_FAIR_STATE_SPACE,
        projected_state,
    )
    state["integrity"]["state_digest"] = state_digest
    bundle_digest = builder.frame_hash_value(
        builder.AGENT_FAIR_BUNDLE_SPACE,
        {
            "contract_digest": contract_digest,
            "district_digest": district_digest,
            "event_count": len(events),
            "event_head": events[-1]["event_hash"],
            "event_ledger_sha256": hashlib.sha256(
                event_bytes
            ).hexdigest(),
            "state_digest": state_digest,
        },
    )
    state["integrity"]["bundle_digest"] = bundle_digest
    district["integrity"]["bundle_digest"] = bundle_digest
    if update_contract_bundle:
        contract["integrity"]["bundle_digest"] = bundle_digest
    write_json(target / "fair-state.json", state)
    if update_contract_bundle:
        write_json(target / "agent-contract.json", contract)
    write_json(target / "district.json", district)
    return state, contract, district


def read_park_events(target):
    return [
        json.loads(line)
        for line in (target / "events.jsonl").read_text().splitlines()
        if line
    ]


def write_park_events(target, events):
    data = b"".join(
        builder.canonical_frame_bytes(event) + b"\n"
        for event in events
    )
    (target / "events.jsonl").write_bytes(data)
    return data


def update_park_state(
    target,
    events,
    agent_contract=None,
    bundle_digest=None,
):
    state_path = target / "park-state.json"
    state = read_json(state_path)
    ledger_bytes = (target / "events.jsonl").read_bytes()
    state["event_ledger"].update({
        "event_count": len(events),
        "head": events[-1]["event_hash"],
        "sha256": hashlib.sha256(ledger_bytes).hexdigest(),
    })
    if agent_contract is not None:
        state["agent_contract"] = agent_contract
    if bundle_digest is not None:
        state.setdefault("integrity", {})["bundle_digest"] = bundle_digest
    state["night_count"] = 7
    write_json(state_path, state)


def migrate_agent_park_v2(target):
    source = ROOT / "apps" / "agent-park"
    events = [
        json.loads(line)
        for line in (source / "events.jsonl").read_text().splitlines()
        if line
    ]
    assert len(events) > builder.AGENT_PARK_SEASON1_EVENT_COUNT
    write_park_events(target, events)
    contract = read_json(source / "agent-contract-v2.json")
    write_json(target / "agent-contract-v2.json", contract)
    write_json(target / "park-state.json", read_json(source / "park-state.json"))
    return events, contract


def rehash_v2_contract(contract):
    projected = json.loads(json.dumps(contract))
    projected["integrity"].pop("bundle_digest")
    projected["integrity"].pop("contract_digest")
    contract["integrity"]["contract_digest"] = builder.frame_hash_value(
        "rappterzoo/agent-park-contract/2",
        projected,
    )


def rewrite_v2_bundle_for_events(target, events):
    ledger_bytes = (target / "events.jsonl").read_bytes()
    ledger_digest = hashlib.sha256(ledger_bytes).hexdigest()
    contract_path = target / "agent-contract-v2.json"
    contract = read_json(contract_path)
    contract["seasons"]["season_2"]["event_count"] = (
        len(events) - builder.AGENT_PARK_SEASON1_EVENT_COUNT
    )
    contract["seasons"]["season_2"]["head"] = events[-1]["event_hash"]
    rehash_v2_contract(contract)

    state_path = target / "park-state.json"
    state = read_json(state_path)
    state["event_ledger"].update({
        "event_count": len(events),
        "head": events[-1]["event_hash"],
        "sha256": ledger_digest,
    })
    state["seasons"][1].update({
        "event_count": len(events) - builder.AGENT_PARK_SEASON1_EVENT_COUNT,
        "head": events[-1]["event_hash"],
        "last_seq": len(events) - 1,
    })
    projected_state = json.loads(json.dumps(state))
    projected_state["integrity"].pop("bundle_digest", None)
    projected_state["integrity"].pop("state_digest", None)
    state_digest = builder.frame_hash_value(
        builder.AGENT_PARK_STATE_V2_HASH_SPACE,
        projected_state,
    )
    state["integrity"]["state_digest"] = state_digest
    bundle_digest = builder.frame_hash_value(
        builder.AGENT_PARK_BUNDLE_V2_HASH_SPACE,
        {
            "contract_digest": contract["integrity"]["contract_digest"],
            "event_count": len(events),
            "event_head": events[-1]["event_hash"],
            "event_ledger_sha256": ledger_digest,
            "state_digest": state_digest,
        },
    )
    contract["integrity"]["bundle_digest"] = bundle_digest
    state["integrity"]["bundle_digest"] = bundle_digest
    write_json(contract_path, contract)
    write_json(state_path, state)


def rechain_park_events(events):
    result = []
    previous = None
    for sequence, source in enumerate(events):
        event = json.loads(json.dumps(source))
        event["seq"] = sequence
        event["prev"] = previous["event_hash"] if previous else None
        payload_space = (
            builder.AGENT_PARK_PAYLOAD_SPACE
            if event["schema"] == builder.AGENT_PARK_EVENT_SCHEMA
            else builder.AGENT_PARK_PAYLOAD_SPACE_V2
        )
        event_space = (
            builder.AGENT_PARK_EVENT_SPACE
            if event["schema"] == builder.AGENT_PARK_EVENT_SCHEMA
            else builder.AGENT_PARK_EVENT_SPACE_V2
        )
        event["payload_hash"] = builder.frame_hash_value(
            payload_space,
            event["payload"],
        )
        projected = {
            key: value
            for key, value in event.items()
            if key != "event_hash"
        }
        event["event_hash"] = builder.frame_hash_value(
            event_space,
            projected,
        )
        result.append(event)
        previous = event
    return result


def append_park_event(events):
    event = {
        "kind": "park.night-open",
        "park_id": "park.rappterzoo-agent-amusement-park",
        "payload": {
            "night": 8,
            "result": "future-customer-approved-append",
        },
        "prev": events[-1]["event_hash"],
        "schema": builder.AGENT_PARK_EVENT_SCHEMA_V2,
        "season": 2,
        "season_seq": len(events) - builder.AGENT_PARK_SEASON1_EVENT_COUNT,
        "seq": len(events),
        "utc": (
            "2026-08-23T00:00:00.000Z"
            if len(events) == builder.AGENT_PARK_SEASON1_EVENT_COUNT
            else "2026-08-30T00:00:00.000Z"
        ),
        "visibility": "public-metadata",
    }
    event["payload_hash"] = builder.frame_hash_value(
        builder.AGENT_PARK_PAYLOAD_SPACE_V2,
        event["payload"],
    )
    event["event_hash"] = builder.frame_hash_value(
        builder.AGENT_PARK_EVENT_SPACE_V2,
        event,
    )
    return events + [event]


def delta_paths(root):
    return sorted((root / "apps" / "syndication" / "deltas").glob("*.json"))


def delta_path_for_sequence(root, sequence):
    index = read_json(root / "apps" / "syndication" / "index.json")
    digest = index["deltas"][sequence]["sha256"]
    return root / "apps" / "syndication" / "deltas" / (digest + ".json")


def downgrade_chain_to_profile9(root, base_url):
    output = root / "apps" / "syndication"
    index_path = output / "index.json"
    snapshot_path = output / "snapshot.json"
    index = read_json(index_path)
    old_entry = index["deltas"][0]
    delta = read_json(output / old_entry["path"])
    delta["profile"] = builder.PROFILE_V9
    delta_bytes = builder.stable_json_bytes(delta)
    digest = hashlib.sha256(delta_bytes).hexdigest()
    (output / "deltas" / (digest + ".json")).write_bytes(delta_bytes)
    entry = builder._delta_entry(delta, digest, delta_bytes, base_url)

    snapshot = read_json(snapshot_path)
    snapshot["profile"] = builder.PROFILE_V9
    snapshot["head"] = {
        "path": entry["path"],
        "sequence": 0,
        "sha256": digest,
        "url": entry["url"],
    }
    snapshot["checkpoint"]["delta_sha256"] = digest
    snapshot["checkpoint"]["next_frame_challenge_seed"] = entry["block"][
        "next_frame_challenge_seed"
    ]
    write_json(snapshot_path, snapshot)

    index["profile"] = builder.PROFILE_V9
    index["deltas"] = [entry]
    index["head"] = dict(snapshot["head"])
    index["next_frame_challenge_seed"] = entry["block"][
        "next_frame_challenge_seed"
    ]
    snapshot_bytes = snapshot_path.read_bytes()
    index["snapshot"].update({
        "sha256": hashlib.sha256(snapshot_bytes).hexdigest(),
        "size": len(snapshot_bytes),
    })
    write_json(index_path, index)


def append_data_delta(root, base_url, descriptors):
    output = root / "apps" / "syndication"
    index_path = output / "index.json"
    index = read_json(index_path)
    sequence = len(index["deltas"])
    previous = index["deltas"][-1]["sha256"]
    changes = {
        "app_tombstones": [],
        "app_upserts": [],
        "data_tombstones": [],
        "data_upserts": descriptors,
        "frame_appends": [],
    }
    proof = builder.proof_of_fold_metadata(changes)
    delta = {
        "changes": changes,
        "challenge_state_machine": builder.CHALLENGE_STATE_MACHINE,
        "created_at": "2026-08-23T00:00:00.000Z",
        "frame_control": builder.frame_control_metadata(changes, proof),
        "frame_control_schema": builder.FRAME_CONTROL_SCHEMA,
        "profile": builder.PROFILE,
        "previous_delta": previous,
        "proof_of_fold": proof,
        "rollout": builder.SOAK_ROLLOUT,
        "schema": builder.DELTA_SCHEMA,
        "segments": builder.segment_metadata(changes),
        "sequence": sequence,
        "since_seq": sequence - 1,
        "stream_id": builder.STREAM_ID,
        "transparency": builder.TRANSPARENCY_MODEL,
        "through_seq": sequence,
    }
    delta_bytes = builder.stable_json_bytes(delta)
    digest = hashlib.sha256(delta_bytes).hexdigest()
    (output / "deltas" / (digest + ".json")).write_bytes(delta_bytes)
    entry = builder._delta_entry(delta, digest, delta_bytes, base_url)
    index["deltas"].append(entry)
    index["delta_count"] = len(index["deltas"])
    index["cursor"]["head_seq"] = sequence
    index["head"] = {
        "path": entry["path"],
        "sequence": sequence,
        "sha256": digest,
        "url": entry["url"],
    }
    index["next_frame_challenge_seed"] = entry["block"][
        "next_frame_challenge_seed"
    ]
    index["updated"] = delta["created_at"]
    write_json(index_path, index)
    return entry


def published_feed_ids(root):
    syndication = root / "apps" / "syndication"
    atom = ElementTree.parse(str(syndication / "feed.xml")).getroot()
    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    atom_ids = [
        node.text
        for node in atom.findall("atom:entry/atom:id", namespace)
    ]
    json_ids = [
        item["id"]
        for item in read_json(syndication / "feed.json")["items"]
    ]
    return atom_ids, json_ids


def test_initial_build_covers_manifest_and_exact_frames(tmp_path):
    root, manifest, frames = make_repo(tmp_path)
    result = builder.build(root, "https://example.test/zoo/")
    snapshot = read_json(root / "apps" / "syndication" / "snapshot.json")
    index = read_json(root / "apps" / "syndication" / "index.json")
    delta = read_json(delta_paths(root)[0])
    atom = ElementTree.parse(
        str(root / "apps" / "syndication" / "feed.xml")
    ).getroot()
    json_feed = read_json(
        root / "apps" / "syndication" / "feed.json"
    )

    assert result["active_apps"] == 2
    assert result["delta_count"] == 1
    assert snapshot["frames"] == frames
    assert delta["changes"]["frame_appends"] == frames
    assert len(snapshot["apps"]) == sum(
        len(category["apps"])
        for category in manifest["categories"].values()
    )
    descriptor = snapshot["apps"][0]
    app_bytes = (root / descriptor["path"]).read_bytes()
    assert descriptor["sha256"] == hashlib.sha256(app_bytes).hexdigest()
    assert descriptor["content_id"] == "sha256:" + descriptor["sha256"]
    assert descriptor["size"] == len(app_bytes)
    assert descriptor["url"].startswith("https://example.test/zoo/apps/")
    assert descriptor["metadata"]["app"]["file"] in {
        "alpha.html",
        "beta.html",
    }
    assert descriptor["verification"] == {
        "algorithm": "sha256",
        "required": True,
    }
    assert index["cursor"] == {
        "head_seq": 0,
        "initial_since_seq": -1,
        "kind": "immutable-since-seq",
        "reset_policy": "reject",
    }
    assert index["rate_budget"]["live_heartbeat_interval_seconds"] == 1800
    assert index["rate_budget"]["legacy_documented_interval_seconds"] == 14400
    assert index["pinning"]["mutable_skill_references"] == "reject-unpinned"
    assert index["transparency"]["publisher_authority"] == "centralized"
    assert index["transparency"]["consensus"] == "none"
    assert index["transparency"]["mining"] is False
    assert index["transparency"]["token"] is False
    assert index["transparency"]["analogy"] == (
        "bitcoin-inspired-append-only-block-sequencing"
    )
    assert "one subscriber creates one independent replica" in (
        index["transparency"]["custody"]
    )
    assert delta["since_seq"] == -1
    assert delta["through_seq"] == 0
    assert delta["segments"] == builder.segment_metadata(delta["changes"])
    assert index["deltas"][0]["block"]["resulting_head"] == {
        "sequence": 0,
        "sha256": index["deltas"][0]["sha256"],
    }
    assert index["deltas"][0]["block"][
        "next_frame_challenge_seed"
    ] == builder.next_challenge_seed(index["deltas"][0]["sha256"])
    assert index["deltas"][0]["block"]["consensus"] == "none"
    assert index["deltas"][0]["block"]["rollout"] == builder.SOAK_ROLLOUT
    assert index["deltas"][0]["block"]["proof_of_fold"] == {
        "acceptance": "centralized-publisher-assembler",
        "cycles": [],
        "frame_control_mode": "observer",
        "status": "disabled-observer",
        "synthetic_test_only": False,
    }
    assert index["rollout"]["default_frame_control_mode"] == "observer"
    assert index["rollout"]["allowed_frame_control_modes"] == [
        "observer",
        "assigned",
    ]
    assert index["rollout"]["future_frame_control_mode"] == "proof-of-fold"
    assert index["frame_control_schema"]["public_soak_allowed"] == [
        "observer",
        "assigned",
    ]
    assert index["deltas"][0]["block"]["frame_control"] == {
        "lease_required": False,
        "mode": "observer",
        "proof_race": False,
    }
    assert index["rollout"]["live_race"] is False
    assert index["rollout"]["compute_incentive"] is False
    assert index["rollout"]["synthetic_proofs"] == "tests-only"
    assert index["challenge_state_machine"]["current_state"] == "observer"
    assert "winner" not in json.dumps(index).lower()
    assert index["deltas"][0]["segment_hashes"] == {
        key: value["sha256"]
        for key, value in delta["segments"].items()
        if key in {"apps", "data", "frames"}
    }
    assert index["snapshot"]["sha256"] == hashlib.sha256(
        (root / "apps" / "syndication" / "snapshot.json").read_bytes()
    ).hexdigest()
    assert atom.tag == "{http://www.w3.org/2005/Atom}feed"
    assert json_feed["version"] == "https://jsonfeed.org/version/1.1"
    assert index["atom"]["path"] == "feed.xml"
    assert index["json_feed"]["path"] == "feed.json"
    assert published_feed_ids(root) == (
        ["urn:sha256:" + index["deltas"][0]["sha256"]],
        ["urn:sha256:" + index["deltas"][0]["sha256"]],
    )


def test_idempotent_rebuild_does_not_append_or_rewrite(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    first = builder.build(root)
    paths = [
        root / "apps" / "syndication" / "feed.xml",
        root / "apps" / "syndication" / "feed.json",
        root / "apps" / "syndication" / "index.json",
        root / "apps" / "syndication" / "snapshot.json",
        *delta_paths(root),
    ]
    before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths}
    second = builder.build(root)
    after = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths}

    assert first["delta_count"] == second["delta_count"] == 1
    assert second["delta_created"] is False
    assert second["written"] == {
        "feed_json": False,
        "feed_xml": False,
        "index": False,
        "snapshot": False,
    }
    assert before == after


def test_profile9_history_upgrades_to_profile10_and_syncs(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    state_dir = tmp_path / "state"
    with serving(root) as server:
        build_served(root, server)
        downgrade_chain_to_profile9(root, server.base_url)
        mutate_app(root)
        result = build_served(root, server)
        synced = sync_client.sync_repository(
            state_dir,
            server.index_url,
            fetch_apps=True,
        )

    index = read_json(root / "apps" / "syndication" / "index.json")
    assert result["delta_count"] == 2
    assert [entry["profile"] for entry in index["deltas"]] == [
        builder.PROFILE_V9,
        builder.PROFILE,
    ]
    assert index["profile"] == builder.PROFILE
    assert synced["applied_deltas"] == 2
    assert sync_client.status(state_dir)["deltas"] == 2


def test_builder_rejects_snapshot_poisoned_with_future_descriptor(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    builder.build(root)
    mutate_app(root, "alpha.html")
    app_path = root / "apps" / "demo" / "alpha.html"
    future_bytes = app_path.read_bytes()
    future_hash = hashlib.sha256(future_bytes).hexdigest()
    snapshot_path = root / "apps" / "syndication" / "snapshot.json"
    snapshot = read_json(snapshot_path)
    descriptor = next(
        item
        for item in snapshot["apps"]
        if item["path"] == "apps/demo/alpha.html"
    )
    descriptor["content_id"] = "sha256:" + future_hash
    descriptor["sha256"] = future_hash
    descriptor["size"] = len(future_bytes)
    write_json(snapshot_path, snapshot)

    with pytest.raises(
        builder.SyndicationError,
        match="snapshot apps disagrees with immutable delta replay",
    ):
        builder.build(root)
    assert len(delta_paths(root)) == 1


def test_actual_change_appends_delta_and_preserves_old_bytes(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    builder.build(root)
    old_path = delta_paths(root)[0]
    old_bytes = old_path.read_bytes()
    mutate_app(root)
    result = builder.build(root)
    index = read_json(root / "apps" / "syndication" / "index.json")
    new_delta = read_json(delta_path_for_sequence(root, 1))

    assert result["delta_count"] == 2
    assert old_path.read_bytes() == old_bytes
    assert index["deltas"][1]["previous_delta"] == index["deltas"][0]["sha256"]
    assert [
        item["path"]
        for item in new_delta["changes"]["app_upserts"]
    ] == ["apps/demo/alpha.html"]
    assert new_delta["changes"]["frame_appends"] == []
    atom_ids, json_ids = published_feed_ids(root)
    expected_ids = [
        "urn:sha256:" + entry["sha256"]
        for entry in reversed(index["deltas"])
    ]
    assert atom_ids == json_ids == expected_ids


def test_builder_rejects_rewritten_immutable_delta(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    builder.build(root)
    delta = delta_paths(root)[0]
    delta.write_bytes(delta.read_bytes() + b" ")
    with pytest.raises(builder.SyndicationError, match="rewritten"):
        builder.build(root)


def test_attention_frames_and_public_group_objects_sync_generically(tmp_path):
    root, _manifest, frames = make_repo(tmp_path)
    attention_frame = make_frame(
        2,
        frames[-1],
        kind="zoo.attention",
        event="attention",
    )
    mutation_frame = make_frame(
        3,
        attention_frame,
        kind="zoo.mutation",
        event="mutation",
    )
    dimension_frame = make_frame(
        4,
        mutation_frame,
        kind="zoo.dimension",
        event="dimension",
    )
    frames.extend([
        attention_frame,
        mutation_frame,
        dimension_frame,
    ])
    write_frames(root, frames)
    group = {
        "comments": [{
            "body": "Selected public observation",
            "comment_id": "comment-1",
            "selected": True,
            "visibility": "public",
        }],
        "group_id": "attention-group-1",
        "schema": "rappterzoo-attention-group/1",
        "visibility": "public-metadata",
    }
    attention_path = root / "apps" / "attention" / "group-1.json"
    attention_path.parent.mkdir(parents=True)
    attention_path.write_bytes(builder.stable_json_bytes(group))
    hot_dimension = {
        "base_record_id": "record-rare-1",
        "branch": "hot",
        "dimension_id": "dimension-hot-1",
        "drift": {
            "changed_fields": ["salience"],
            "score_delta": "positive",
        },
        "schema": "rappterzoo-dimension/1",
        "visibility": "public-metadata",
    }
    cold_dimension = {
        "base_record_id": "record-rare-1",
        "branch": "cold",
        "dimension_id": "dimension-cold-1",
        "drift": {
            "changed_fields": ["confidence"],
            "score_delta": "negative",
        },
        "schema": "rappterzoo-dimension/1",
        "visibility": "public-metadata",
    }
    hot_path = root / "apps" / "attention" / "z-hot.json"
    cold_path = root / "apps" / "attention" / "a-cold.json"
    hot_path.write_bytes(builder.stable_json_bytes(hot_dimension))
    cold_path.write_bytes(builder.stable_json_bytes(cold_dimension))
    state_dir = tmp_path / "state"

    with serving(root) as server:
        build_served(root, server)
        metadata_result = sync_client.sync_repository(
            state_dir,
            server.index_url,
        )
        result = sync_client.sync_repository(
            state_dir,
            server.index_url,
            fetch_apps=True,
        )

    snapshot = read_json(
        root / "apps" / "syndication" / "snapshot.json"
    )
    delta = read_json(delta_path_for_sequence(root, 0))
    local_dimension = tmp_path / "local-hot.json"
    local_dimension.write_bytes(b'{"local_overlay":true}\n')
    sync_client.add_local_app(
        state_dir,
        local_dimension,
        "apps/attention/z-hot.json",
        "Local Hot Overlay",
    )
    listed = sync_client.list_data_objects(state_dir)
    current = sync_client.status(state_dir)
    materialized = tmp_path / "attention-materialized"
    sync_client.materialize(state_dir, materialized)

    assert [frame["kind"] for frame in snapshot["frames"][-3:]] == [
        "zoo.attention",
        "zoo.mutation",
        "zoo.dimension",
    ]
    assert delta["changes"]["frame_appends"] == frames
    assert len(snapshot["data_objects"]) == 3
    assert len(delta["changes"]["data_upserts"]) == 3
    assert metadata_result["fetched_objects"] == 0
    assert result["not_modified"] is True
    assert result["fetched_objects"] == 5
    assert current["attention_data_objects"] == 3
    assert current["frames"] == 5
    assert [item["kind"] for item in listed] == [
        "attention-dimension-object",
        "attention-dimension-object",
        "attention-group-object",
    ]
    assert [
        item["metadata"].get("branches_present")
        for item in listed[:2]
    ] == [["hot"], ["cold"]]
    assert all(
        item["metadata"]["merge_order"] == ["hot", "cold"]
        for item in listed[:2]
    )
    assert all("drift_sha256" in item["metadata"] for item in listed[:2])
    assert listed[0]["overlayed"] is True
    assert listed[1]["overlayed"] is False
    assert "comments" not in listed[2]["metadata"]
    assert (
        materialized / "apps" / "attention" / "group-1.json"
    ).read_bytes() == attention_path.read_bytes()
    assert (
        materialized / "apps" / "attention" / "z-hot.json"
    ).read_bytes() == local_dimension.read_bytes()
    assert (
        materialized / "apps" / "attention" / "a-cold.json"
    ).read_bytes() == cold_path.read_bytes()


def test_looking_glass_scene_round_trips_as_public_data(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    scene = {
        "dimensions": [
            {"id": dimension}
            for dimension in (
                "payload",
                "lineage",
                "attention",
                "mutation",
                "app",
                "neighborhood",
                "syndication",
            )
        ],
        "experience_id": "looking-glass-inside-one-hash",
        "integrity": {
            "algorithm": "sha256",
            "scene_digest": "a" * 64,
        },
        "schema": "rappterzoo-looking-glass-scene/1",
        "target_frame": {
            "frame_hash": "b" * 64,
        },
        "visibility": "public-metadata",
    }
    scene_path = root / "apps" / "looking-glass" / "hash-scene.json"
    scene_path.parent.mkdir(parents=True)
    scene_path.write_bytes(builder.stable_json_bytes(scene))
    state_dir = tmp_path / "state"

    with serving(root) as server:
        build_served(root, server)
        result = sync_client.sync_repository(
            state_dir,
            server.index_url,
            fetch_apps=True,
        )

    objects = sync_client.list_data_objects(state_dir)
    descriptor = next(
        item
        for item in objects
        if item["kind"] == "looking-glass-scene-object"
    )
    assert result["fetched_objects"] == 3
    assert descriptor["path"] == "apps/looking-glass/hash-scene.json"
    assert descriptor["metadata"]["dimension_count"] == 7
    assert descriptor["metadata"]["scene_digest"] == "a" * 64
    assert descriptor["metadata"]["target_frame_hash"] == "b" * 64


def test_agent_worlds_fair_prepared_then_released_delta_is_atomic(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    copy_agent_fair(root)
    state_dir = tmp_path / "state"

    with serving(root) as server:
        prepared_result = build_served(root, server)
        prepared_delta = read_json(delta_path_for_sequence(root, 0))
        prepared_snapshot = read_json(
            root / "apps" / "syndication" / "snapshot.json"
        )
        prepared_sync = sync_client.sync_repository(
            state_dir,
            server.index_url,
        )
        prepared_status = sync_client.status(state_dir)

        release = release_agent_fair(root)
        released_result = build_served(root, server)
        released_delta = read_json(delta_path_for_sequence(root, 1))
        released_index = read_json(
            root / "apps" / "syndication" / "index.json"
        )
        released_sync = sync_client.sync_repository(
            state_dir,
            server.index_url,
        )
        cached_sync = sync_client.sync_repository(
            state_dir,
            server.index_url,
        )
    offline_status = sync_client.status(state_dir)

    assert prepared_result["delta_created"] is True
    assert prepared_delta["changes"]["app_upserts"]
    assert not [
        item
        for item in prepared_delta["changes"]["data_upserts"]
        if item["kind"] == "agent-worlds-fair-object"
    ]
    assert not [
        frame
        for frame in prepared_delta["changes"]["frame_appends"]
        if frame["payload"]["event"] == "agent-worlds-fair-release"
    ]
    assert not [
        item
        for item in prepared_snapshot["data_objects"]
        if item["kind"] == "agent-worlds-fair-object"
    ]
    assert prepared_sync["fetched_objects"] == 0
    assert prepared_status["profile"] == builder.PROFILE
    assert prepared_status["agent_worlds_fair_release"]["status"] == (
        "not-replicated"
    )
    assert prepared_status["agent_worlds_fair_release"][
        "offline_verified"
    ] is False

    fair_upserts = [
        item
        for item in released_delta["changes"]["data_upserts"]
        if item["kind"] == "agent-worlds-fair-object"
    ]
    fair_frames = [
        frame
        for frame in released_delta["changes"]["frame_appends"]
        if frame["payload"]["event"] == "agent-worlds-fair-release"
    ]
    assert released_result["delta_created"] is True
    assert {
        item["metadata"]["resource_type"]
        for item in fair_upserts
    } == {"agent-contract", "district", "event-ledger", "state"}
    assert fair_frames == [release]
    assert released_sync["applied_deltas"] == 1
    assert released_sync["fetched_objects"] == 4
    assert released_sync["cached_objects"] == 0
    assert released_sync["verified_objects"] == 4
    assert released_sync["profile"] == builder.PROFILE
    assert cached_sync["not_modified"] is True
    assert cached_sync["fetched_objects"] == 0
    assert cached_sync["cached_objects"] == 4
    assert cached_sync["verified_objects"] == 4
    assert len([
        item
        for item in sync_client.list_data_objects(state_dir)
        if item["kind"] == "agent-worlds-fair-object"
    ]) == 4
    release_status = offline_status["agent_worlds_fair_release"]
    assert offline_status["profile"] == builder.PROFILE
    assert release_status["status"] == "structural-only"
    assert release_status["official_source"] is False
    assert release_status["structural_verified"] is True
    assert release_status["offline_verified"] is False
    assert release_status["prepared_bundle_status"] == (
        "release-ready-awaiting-customer-approval"
    )
    assert release_status["candidate_digest"] == (
        builder.AGENT_FAIR_RELEASE_CANDIDATE_DIGEST
    )
    assert release_status["release_candidate_in_replica"] is False
    assert release_status["replicated_resource_types"] == [
        "agent-contract",
        "district",
        "event-ledger",
        "state",
    ]
    assert release_status["release_frame"]["frame_hash"] == (
        release["frame_hash"]
    )
    assert release_status["release_delta"] == {
        "sequence": 1,
        "sha256": released_index["deltas"][1]["sha256"],
    }

    connection = sync_client.connect_state(state_dir)
    try:
        sync_client._set_meta(
            connection,
            "source_url",
            sync_client.DEFAULT_INDEX_URL,
        )
        connection.commit()
    finally:
        connection.close()
    forged_official = sync_client.status(state_dir)[
        "agent_worlds_fair_release"
    ]
    assert forged_official["official_source"] is True
    assert forged_official["offline_verified"] is False
    assert forged_official["status"] == "invalid-local-replica"
    assert any(
        "does not match its pin" in error
        for error in forged_official["errors"]
    )


def test_agent_worlds_fair_invalid_release_blocks_prepared_build(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    copy_agent_fair(root)
    frames = builder.read_ledger(root / "apps" / "organism-frames.jsonl")
    invalid_release = make_fair_release_frame(frames[-1])
    invalid_release["payload"]["approval_evidence"].pop("actor")
    rehash_frame(invalid_release)
    write_frames(root, frames + [invalid_release])

    with pytest.raises(
        builder.SyndicationError,
        match="OIDC approval evidence",
    ):
        builder.build(root)
    assert not (root / "apps" / "syndication").exists()


@pytest.mark.parametrize("mutation", ["missing-frame", "missing-resource"])
def test_sync_rejects_non_atomic_agent_worlds_fair_release(
    tmp_path,
    mutation,
):
    root, _manifest, _frames = make_repo(tmp_path)
    copy_agent_fair(root)
    builder.build(root, "https://example.test/zoo/")
    release_agent_fair(root)
    builder.build(root, "https://example.test/zoo/")
    delta = read_json(delta_path_for_sequence(root, 1))
    if mutation == "missing-frame":
        delta["changes"]["frame_appends"] = []
    else:
        district = next(
            item
            for item in delta["changes"]["data_upserts"]
            if item["metadata"].get("resource_type") == "district"
        )
        delta["changes"]["data_upserts"].remove(district)
    delta["segments"] = builder.segment_metadata(delta["changes"])
    delta["frame_control"] = builder.frame_control_metadata(
        delta["changes"],
        delta["proof_of_fold"],
    )
    delta_bytes = builder.stable_json_bytes(delta)
    digest = hashlib.sha256(delta_bytes).hexdigest()
    entry = builder._delta_entry(
        delta,
        digest,
        delta_bytes,
        "https://example.test/zoo/",
    )

    with pytest.raises(sync_client.SyncError, match="atomically"):
        sync_client.validate_delta(
            delta_bytes,
            entry,
            builder.STREAM_ID,
        )


def test_sync_rejects_release_outside_oidc_window(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    copy_agent_fair(root)
    builder.build(root, "https://example.test/zoo/")
    release_agent_fair(root)
    builder.build(root, "https://example.test/zoo/")
    delta = read_json(delta_path_for_sequence(root, 1))
    release = next(
        frame
        for frame in delta["changes"]["frame_appends"]
        if frame["payload"].get("event") == "agent-worlds-fair-release"
    )
    evidence = release["payload"]["approval_evidence"]
    evidence["nbf"] = evidence["exp"] - 1
    rehash_frame(release)
    delta["segments"] = builder.segment_metadata(delta["changes"])
    delta["frame_control"] = builder.frame_control_metadata(
        delta["changes"],
        delta["proof_of_fold"],
    )
    delta_bytes = builder.stable_json_bytes(delta)
    digest = hashlib.sha256(delta_bytes).hexdigest()
    entry = builder._delta_entry(
        delta,
        digest,
        delta_bytes,
        "https://example.test/zoo/",
    )
    with pytest.raises(
        sync_client.SyncError,
        match="OIDC approval evidence",
    ):
        sync_client.validate_delta(
            delta_bytes,
            entry,
            builder.STREAM_ID,
        )


def test_agent_worlds_fair_fixture_roundtrip_and_overlay(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    copy_agent_fair(root)
    release_agent_fair(root)
    state_dir = tmp_path / "state"

    with serving(root) as server:
        build_served(root, server)
        result = sync_client.sync_repository(
            state_dir,
            server.index_url,
        )

    fair_objects = [
        item
        for item in sync_client.list_data_objects(state_dir)
        if item["kind"] == "agent-worlds-fair-object"
    ]
    assert result["fetched_objects"] == 4
    assert {
        item["metadata"]["resource_type"]
        for item in fair_objects
    } == {"agent-contract", "district", "event-ledger", "state"}
    ledger = next(
        item
        for item in fair_objects
        if item["metadata"]["resource_type"] == "event-ledger"
    )
    state = next(
        item
        for item in fair_objects
        if item["metadata"]["resource_type"] == "state"
    )
    assert ledger["metadata"]["event_count"] == 23
    assert ledger["metadata"]["event_head"] == (
        builder.AGENT_FAIR_BASE_EVENT_HEAD
    )
    assert state["metadata"]["winner_submission_ids"] == (
        builder.AGENT_FAIR_WINNERS
    )

    overlay = tmp_path / "fair-state-overlay.json"
    overlay.write_bytes(b'{"local_overlay":true}\n')
    sync_client.add_local_app(
        state_dir,
        overlay,
        "apps/agent-fair/fair-state.json",
        "Local Fair State",
    )
    listed = sync_client.list_data_objects(state_dir)
    overlaid = next(
        item
        for item in listed
        if item["path"] == "apps/agent-fair/fair-state.json"
    )
    assert overlaid["overlayed"] is True


def test_agent_worlds_fair_offline_status_detects_cache_corruption(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    copy_agent_fair(root)
    release_agent_fair(root)
    state_dir = tmp_path / "state"
    with serving(root) as server:
        build_served(root, server)
        sync_client.sync_repository(state_dir, server.index_url)

    state = next(
        item
        for item in sync_client.list_data_objects(state_dir)
        if item["kind"] == "agent-worlds-fair-object"
        and item["metadata"]["resource_type"] == "state"
    )
    sync_client._object_path(
        state_dir,
        state["sha256"],
    ).write_bytes(b"corrupt")
    release = sync_client.status(state_dir)["agent_worlds_fair_release"]
    assert release["status"] == "invalid-local-replica"
    assert release["offline_verified"] is False
    assert "corrupt cached fair resource state" in release["errors"]


@pytest.mark.parametrize(
    "resource_type",
    ["event-ledger", "state", "agent-contract", "district"],
)
def test_agent_worlds_fair_tampered_objects_are_rejected(
    tmp_path,
    resource_type,
):
    root, _manifest, _frames = make_repo(tmp_path)
    target = copy_agent_fair(root)
    descriptors = builder.build_public_data_descriptors(
        root,
        "https://example.test/zoo/",
    )
    descriptor = next(
        item
        for item in descriptors
        if item["metadata"].get("resource_type") == resource_type
        and item["kind"] == "agent-worlds-fair-object"
    )
    if resource_type == "event-ledger":
        events = read_fair_events(target)
        events[2]["payload"]["submission"]["submission_id"] = (
            "submission.tampered"
        )
        write_fair_events(target, events)
        path = target / "events.jsonl"
    else:
        path = target / {
            "state": "fair-state.json",
            "agent-contract": "agent-contract.json",
            "district": "district.json",
        }[resource_type]
        value = read_json(path)
        if resource_type == "state":
            value["winners"] = list(reversed(value["winners"]))
        elif resource_type == "agent-contract":
            value["local_proposals"]["canonical_mutation"] = True
        else:
            value["pavilions"][0]["lineage"][
                "submission_event_hash"
            ] = "0" * 64
        write_json(path, value)

    with pytest.raises(builder.SyndicationError):
        builder.build(root)
    with pytest.raises(sync_client.SyncError):
        sync_client._validate_descriptor_object(
            path.read_bytes(),
            sync_client.validate_data_descriptor(descriptor),
        )


@pytest.mark.parametrize("mutation", ["truncation", "fork", "equal-utc"])
def test_agent_worlds_fair_chain_rejects_history_mutations(
    tmp_path,
    mutation,
):
    root, _manifest, _frames = make_repo(tmp_path)
    target = copy_agent_fair(root)
    events = read_fair_events(target)
    if mutation == "truncation":
        events = events[:-1]
    elif mutation == "fork":
        events[5]["prev"] = "0" * 64
        projected = {
            key: value
            for key, value in events[5].items()
            if key != "event_hash"
        }
        events[5]["event_hash"] = builder.frame_hash_value(
            builder.AGENT_FAIR_EVENT_SPACE,
            projected,
        )
    else:
        events[-1]["utc"] = events[-2]["utc"]
        projected = {
            key: value
            for key, value in events[-1].items()
            if key != "event_hash"
        }
        events[-1]["event_hash"] = builder.frame_hash_value(
            builder.AGENT_FAIR_EVENT_SPACE,
            projected,
        )

    with pytest.raises(builder.SyndicationError):
        builder.validate_agent_fair_event_ledger(events)
    with pytest.raises(sync_client.SyncError):
        sync_client.validate_agent_fair_event_ledger(events)


@pytest.mark.parametrize(
    "mutation",
    ["over-cap-district", "unsafe-proposal", "missing-winner-lineage"],
)
def test_agent_worlds_fair_resealed_semantic_mutations_fail(
    tmp_path,
    mutation,
):
    root, _manifest, _frames = make_repo(tmp_path)
    target = copy_agent_fair(root)
    update_contract = mutation == "unsafe-proposal"
    if mutation == "unsafe-proposal":
        contract_path = target / "agent-contract.json"
        contract = read_json(contract_path)
        contract["local_proposals"]["canonical_mutation"] = True
        write_json(contract_path, contract)
    else:
        district_path = target / "district.json"
        district = read_json(district_path)
        if mutation == "over-cap-district":
            district["pavilions"][3]["resource_request"]["compute"] = 32
            district["resource_totals"]["compute"] = 98
        else:
            district["pavilions"][0]["lineage"][
                "vote_event_hashes"
            ].pop()
        write_json(district_path, district)
    rebind_fair_bundle(
        target,
        update_contract_bundle=update_contract,
    )

    with pytest.raises(builder.SyndicationError):
        builder.build(root)


def test_agent_worlds_fair_allows_coherent_exact_prefix_growth(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    target = copy_agent_fair(root)
    release_agent_fair(root)
    state_dir = tmp_path / "state"

    with serving(root) as server:
        build_served(root, server)
        sync_client.sync_repository(state_dir, server.index_url)
        before = {
            item["metadata"]["resource_type"]: item
            for item in sync_client.list_data_objects(state_dir)
            if item["kind"] == "agent-worlds-fair-object"
        }

        events = append_fair_event(read_fair_events(target))
        write_fair_events(target, events)
        rebind_fair_bundle(target, update_contract_bundle=False)
        assert build_served(root, server)["delta_created"] is True
        result = sync_client.sync_repository(
            state_dir,
            server.index_url,
        )

    after = {
        item["metadata"]["resource_type"]: item
        for item in sync_client.list_data_objects(state_dir)
        if item["kind"] == "agent-worlds-fair-object"
    }
    assert result["applied_deltas"] == 1
    assert after["event-ledger"]["metadata"]["event_count"] == 24
    assert after["agent-contract"]["sha256"] == (
        before["agent-contract"]["sha256"]
    )
    assert after["state"]["sha256"] != before["state"]["sha256"]
    assert after["district"]["sha256"] != before["district"]["sha256"]
    assert after["state"]["metadata"]["bundle_digest"] == (
        after["district"]["metadata"]["bundle_digest"]
    )


def test_agent_worlds_fair_conditional_repair_and_rollback(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    target = copy_agent_fair(root)
    release_agent_fair(root)
    state_dir = tmp_path / "state"

    with serving(root) as server:
        build_served(root, server)
        sync_client.sync_repository(state_dir, server.index_url)
        contract = next(
            item
            for item in sync_client.list_data_objects(state_dir)
            if item["kind"] == "agent-worlds-fair-object"
            and item["metadata"]["resource_type"] == "agent-contract"
        )
        cached_contract = sync_client._object_path(
            state_dir,
            contract["sha256"],
        )
        cached_contract.write_bytes(b"corrupt")
        repaired = sync_client.sync_repository(
            state_dir,
            server.index_url,
        )
        assert hashlib.sha256(cached_contract.read_bytes()).hexdigest() == (
            contract["sha256"]
        )

        events = append_fair_event(read_fair_events(target))
        write_fair_events(target, events)
        rebind_fair_bundle(target, update_contract_bundle=False)
        build_served(root, server)
        before_failure = sync_client.status(state_dir)
        (target / "events.jsonl").write_bytes(
            (target / "events.jsonl").read_bytes() + b" "
        )
        with pytest.raises(sync_client.SyncError):
            sync_client.sync_repository(state_dir, server.index_url)

    after_failure = sync_client.status(state_dir)
    assert repaired["not_modified"] is True
    assert repaired["fetched_objects"] == 1
    assert repaired["fetched_data_objects"] == 1
    assert repaired["cached_objects"] == 3
    assert repaired["verified_objects"] == 4
    assert repaired["profile"] == builder.PROFILE
    assert after_failure["agent_worlds_fair_release"][
        "structural_verified"
    ] is True
    assert after_failure["agent_worlds_fair_release"][
        "offline_verified"
    ] is False
    assert after_failure["head_sha256"] == before_failure["head_sha256"]
    assert after_failure["deltas"] == before_failure["deltas"]
    index_requests = [
        request
        for request in server.requests
        if request["path"].endswith("/index.json")
    ]
    assert index_requests[1]["if_none_match"]
    assert any(
        request["path"].endswith("/apps/agent-fair/agent-contract.json")
        for request in server.requests
    )


def test_agent_worlds_fair_profile9_replay_and_tombstone_rejection(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    copy_agent_fair(root)
    release_agent_fair(root)
    state_dir = tmp_path / "state"

    with serving(root) as server:
        build_served(root, server)
        downgrade_chain_to_profile9(root, server.base_url)
        assert builder.build(
            root,
            server.base_url,
        )["delta_created"] is True
        result = sync_client.sync_repository(
            state_dir,
            server.index_url,
        )
        assert result["applied_deltas"] == 2

    delta_path = delta_path_for_sequence(root, 0)
    delta = read_json(delta_path)
    descriptor = next(
        item
        for item in delta["changes"]["data_upserts"]
        if item["kind"] == "agent-worlds-fair-object"
        and item["metadata"]["resource_type"] == "district"
    )
    delta["profile"] = builder.PROFILE_V9
    delta["changes"]["data_upserts"].remove(descriptor)
    delta["changes"]["data_tombstones"] = [{
        "descriptor": descriptor,
        "path": descriptor["path"],
        "reason": "forbidden-fair-removal",
        "removed_at": delta["created_at"],
        "sequence": delta["sequence"],
    }]
    delta["segments"] = builder.segment_metadata(delta["changes"])
    delta_bytes = builder.stable_json_bytes(delta)
    digest = hashlib.sha256(delta_bytes).hexdigest()
    entry = builder._delta_entry(
        delta,
        digest,
        delta_bytes,
        "https://example.test/zoo/",
    )
    with pytest.raises(sync_client.SyncError, match="cannot be tombstoned"):
        sync_client.validate_delta(
            delta_bytes,
            entry,
            builder.STREAM_ID,
        )
    with pytest.raises(builder.SyndicationError, match="cannot be tombstoned"):
        builder.replay_immutable_deltas([delta])


def test_agent_worlds_fair_path_and_privacy_fail_closed(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    target = copy_agent_fair(root)
    candidate = target / "release-candidate.json"
    candidate.write_bytes(b'{"credential":"non-public-candidate"}\n')
    descriptors = builder.build_public_data_descriptors(
        root,
        "https://example.test/zoo/",
    )
    assert {
        item["path"]
        for item in descriptors
        if item["kind"] == "agent-worlds-fair-object"
    } == {
        "apps/agent-fair/agent-contract.json",
        "apps/agent-fair/district.json",
        "apps/agent-fair/events.jsonl",
        "apps/agent-fair/fair-state.json",
    }

    extra = target / "nested" / "extra.json"
    extra.parent.mkdir()
    extra.write_bytes(builder.stable_json_bytes({
        "schema": "rappterzoo-agent-worlds-fair-state/1",
        "visibility": "public-metadata",
    }))
    with pytest.raises(
        builder.SyndicationError,
        match="unknown agent fair public object",
    ):
        builder.build(root)

    extra.unlink()
    contract_path = target / "agent-contract.json"
    contract = read_json(contract_path)
    contract["credential"] = "must-not-publish"
    write_json(contract_path, contract)
    with pytest.raises(builder.SyndicationError, match="sensitive key"):
        builder.build(root)


def test_agent_worlds_fair_release_frame_requires_oidc_authority():
    candidate = read_json(
        ROOT / "apps" / "agent-fair" / "release-candidate.json"
    )
    assert candidate["candidate_digest"] == (
        builder.AGENT_FAIR_RELEASE_CANDIDATE_DIGEST
    )
    base = make_frame(0)
    release = make_fair_release_frame(base)

    assert builder.validate_frames([base, release]) == [base, release]
    assert sync_client.validate_frames(
        [base, release],
        None,
        set(),
    ) == release


@pytest.mark.parametrize(
    "mutation",
    [
        "candidate",
        "missing-claim",
        "fixed-claim",
        "leading-zero-run-id",
        "time-range",
        "attestation",
        "extra-key",
    ],
)
def test_agent_worlds_fair_release_authority_mutations_fail(mutation):
    base = make_frame(0)
    release = make_fair_release_frame(base)
    evidence = release["payload"]["approval_evidence"]
    if mutation == "candidate":
        release["payload"]["release_candidate_digest"] = "0" * 64
    elif mutation == "missing-claim":
        evidence.pop("actor")
    elif mutation == "fixed-claim":
        evidence["repository"] = "fork/example"
    elif mutation == "leading-zero-run-id":
        evidence["run_id"] = "0123456789"
    elif mutation == "time-range":
        evidence["exp"] = evidence["nbf"]
    elif mutation == "attestation":
        evidence["attestation_sha256"] = "0" * 64
    else:
        release["payload"]["unexpected"] = True
    rehash_frame(release)

    with pytest.raises(
        builder.SyndicationError,
        match="OIDC approval evidence",
    ):
        builder.validate_frames([base, release])
    with pytest.raises(
        sync_client.SyncError,
        match="OIDC approval evidence",
    ):
        sync_client.validate_frames([base, release], None, set())


def test_agent_amusement_park_round_trips_as_public_data(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    copy_agent_park(root)
    state_dir = tmp_path / "state"

    with serving(root) as server:
        build_served(root, server)
        result = sync_client.sync_repository(
            state_dir,
            server.index_url,
            fetch_apps=True,
        )

    objects = [
        item
        for item in sync_client.list_data_objects(state_dir)
        if item["kind"] == "agent-amusement-park-object"
    ]
    assert result["fetched_objects"] == 5
    assert [item["metadata"]["resource_type"] for item in objects] == [
        "agent-contract-v1",
        "event-ledger",
        "state",
    ]
    state = next(
        item
        for item in objects
        if item["metadata"]["resource_type"] == "state"
    )
    ledger = next(
        item
        for item in objects
        if item["metadata"]["resource_type"] == "event-ledger"
    )
    assert state["metadata"]["night_count"] == 7
    assert state["metadata"]["event_head"] == ledger["metadata"]["event_head"]


def test_agent_park_v2_migration_preserves_v1_and_grows_one_chain(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    target = copy_agent_park(root)
    builder.build(root)
    first_snapshot = read_json(
        root / "apps" / "syndication" / "snapshot.json"
    )
    v1_before = next(
        item
        for item in first_snapshot["data_objects"]
        if item["path"] == "apps/agent-park/agent-contract.json"
    )
    events, contract = migrate_agent_park_v2(target)

    result = builder.build(root)
    snapshot = read_json(root / "apps" / "syndication" / "snapshot.json")
    migrated = [
        item
        for item in snapshot["data_objects"]
        if item["kind"] == "agent-amusement-park-object"
    ]
    v1_after = next(
        item
        for item in migrated
        if item["path"] == "apps/agent-park/agent-contract.json"
    )
    state = next(
        item
        for item in migrated
        if item["metadata"]["resource_type"] == "state"
    )
    ledger = next(
        item
        for item in migrated
        if item["metadata"]["resource_type"] == "event-ledger"
    )
    v2 = next(
        item
        for item in migrated
        if item["metadata"]["resource_type"] == "agent-contract-v2"
    )

    assert result["delta_count"] == 2
    assert len(events) == 94
    assert hashlib.sha256(
        (target / "events.jsonl").read_bytes()
    ).hexdigest() == (
        "bfefe99e73fd89bc4f435dd3dfd9c4a5b784788017e406a79fe92194273351bf"
    )
    assert v1_after == v1_before
    assert {
        item["metadata"]["resource_type"]
        for item in migrated
    } == {
        "agent-contract-v1",
        "agent-contract-v2",
        "event-ledger",
        "state",
    }
    assert state["metadata"]["agent_contract"] == "agent-contract-v2.json"
    assert state["metadata"]["event_count"] == ledger["metadata"]["event_count"]
    assert state["metadata"]["event_head"] == ledger["metadata"]["event_head"]
    assert state["metadata"]["bundle_digest"] == v2["metadata"]["bundle_digest"]
    assert (
        v2["metadata"]["action_limit"]
        == builder.AGENT_PARK_V2_ACTION_LIMIT
    )
    assert v2["metadata"]["mcp_mapping"] == contract["mcp_mapping"]
    assert v2["metadata"]["season2_event_count"] == 47
    assert v2["metadata"]["season2_head"] == events[-1]["event_hash"]


def test_agent_park_exact_season1_prefix_is_mandatory(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    target = copy_agent_park(root)
    events = read_park_events(target)
    assert len(events) == 47
    assert hashlib.sha256(
        write_park_events(target, events)
    ).hexdigest() == builder.AGENT_PARK_SEASON1_PREFIX_SHA256

    events[3]["payload"]["night"] = 99
    rewritten = append_park_event(rechain_park_events(events))
    with pytest.raises(
        builder.SyndicationError,
        match="Season 1 prefix",
    ):
        builder.validate_agent_park_event_ledger(rewritten)
    with pytest.raises(
        sync_client.SyncError,
        match="Season 1 prefix",
    ):
        sync_client.validate_agent_park_event_ledger(rewritten)


@pytest.mark.parametrize(
    "field",
    ["canonicalization_and_hashing", "mcp_mapping", "action_limit"],
)
def test_agent_park_v2_contract_fields_are_fail_closed(tmp_path, field):
    root, _manifest, _frames = make_repo(tmp_path)
    target = copy_agent_park(root)
    _events, contract = migrate_agent_park_v2(target)
    if field == "canonicalization_and_hashing":
        contract[field]["hash_domains"]["contract_v2"] = (
            "rappterzoo/agent-park-contract/unscoped\n"
        )
    elif field == "mcp_mapping":
        contract[field]["tools"]["visit"] = "unbounded_remote_write"
    else:
        contract[field]["max_local_actions_per_mcp_session"] = 101
    rehash_v2_contract(contract)
    write_json(target / "agent-contract-v2.json", contract)

    with pytest.raises(
        builder.SyndicationError,
        match="contract v2",
    ):
        builder.build(root)


def test_actual_agent_park_v2_hash_spec_is_accepted():
    contract = read_json(
        ROOT / "apps" / "agent-park" / "agent-contract-v2.json"
    )
    hashing = contract["canonicalization_and_hashing"]

    builder._validate_agent_park_v2_hashing(hashing)
    sync_client._validate_agent_park_v2_hashing(hashing)


@pytest.mark.parametrize(
    "mutation",
    [
        "remove-domain",
        "change-domain",
        "remove-preimage",
        "change-preimage",
    ],
)
def test_agent_park_v2_hash_spec_requires_every_exact_entry(mutation):
    contract = read_json(
        ROOT / "apps" / "agent-park" / "agent-contract-v2.json"
    )
    hashing = contract["canonicalization_and_hashing"]
    if mutation == "remove-domain":
        hashing["hash_domains"].pop("full_export_v2")
    elif mutation == "change-domain":
        hashing["hash_domains"]["full_export_v2"] = (
            "rappterzoo/agent-park-full-export/3\n"
        )
    elif mutation == "remove-preimage":
        hashing["preimages"].pop("full_export_content_digest")
    else:
        hashing["preimages"]["local_action_hash"]["bytes"][0] = (
            "mcp_local_branch_json(action excluding action_hash)"
        )

    with pytest.raises(
        builder.SyndicationError,
        match="contract v2 hash spec",
    ):
        builder._validate_agent_park_v2_hashing(hashing)
    with pytest.raises(
        sync_client.SyncError,
        match="contract v2 hash spec",
    ):
        sync_client._validate_agent_park_v2_hashing(hashing)


def test_agent_park_v2_state_replacement_requires_ledger_growth(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    target = copy_agent_park(root)
    builder.build(root)
    original = read_park_events(target)
    _events, _contract = migrate_agent_park_v2(target)
    write_park_events(target, original)
    update_park_state(
        target,
        original,
        agent_contract="agent-contract-v2.json",
        bundle_digest="b" * 64,
    )

    with pytest.raises(
        builder.SyndicationError,
        match="invalid.*state|growth",
    ):
        builder.build(root)


def test_agent_park_v1_contract_stays_immutable_during_v2_growth(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    target = copy_agent_park(root)
    builder.build(root)
    migrate_agent_park_v2(target)
    v1_path = target / "agent-contract.json"
    v1 = read_json(v1_path)
    v1["integrity"]["contract_digest"] = "c" * 64
    write_json(v1_path, v1)

    with pytest.raises(
        builder.SyndicationError,
        match="immutable",
    ):
        builder.build(root)


def test_agent_park_v2_sync_304_cache_repair_and_rollback(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    target = copy_agent_park(root)
    state_dir = tmp_path / "state"
    with serving(root) as server:
        build_served(root, server)
        sync_client.sync_repository(
            state_dir,
            server.index_url,
            fetch_apps=True,
        )
        initial = sync_client.status(state_dir)
        migrate_agent_park_v2(target)
        build_served(root, server)
        migrated = sync_client.sync_repository(
            state_dir,
            server.index_url,
        )
        objects = sync_client.list_data_objects(state_dir)
        v2 = next(
            item
            for item in objects
            if item["metadata"].get("resource_type")
            == "agent-contract-v2"
        )
        cached_v2 = sync_client._object_path(state_dir, v2["sha256"])
        cached_v2.write_bytes(b"corrupt")
        repaired = sync_client.sync_repository(
            state_dir,
            server.index_url,
            fetch_apps=True,
        )
        repaired_v2_sha256 = hashlib.sha256(
            cached_v2.read_bytes()
        ).hexdigest()

        mutate_app(root)
        build_served(root, server)
        v2_path = target / "agent-contract-v2.json"
        v2_path.write_bytes(v2_path.read_bytes() + b" ")
        cached_v2.unlink()
        before_failure = sync_client.status(state_dir)
        with pytest.raises(sync_client.SyncError):
            sync_client.sync_repository(
                state_dir,
                server.index_url,
                fetch_apps=True,
            )

    after_failure = sync_client.status(state_dir)
    assert initial["deltas"] == 1
    assert migrated["applied_deltas"] == 1
    assert migrated["fetched_objects"] == 3
    assert migrated["cached_objects"] == 1
    assert migrated["verified_objects"] == 4
    assert repaired["not_modified"] is True
    assert repaired_v2_sha256 == v2["sha256"]
    assert after_failure["head_sha256"] == before_failure["head_sha256"]
    assert after_failure["deltas"] == before_failure["deltas"]


def test_historical_park_descriptor_metadata_normalizes_for_replay():
    legacy = {}
    for path in sorted(
        (ROOT / "apps" / "syndication" / "deltas").glob("*.json")
    ):
        delta = read_json(path)
        for descriptor in delta["changes"].get("data_upserts", []):
            metadata = descriptor.get("metadata", {})
            resource_type = metadata.get("resource_type")
            if (
                descriptor.get("path")
                == "apps/agent-park/agent-contract.json"
                and resource_type == "agent-contract"
            ):
                legacy["contract"] = descriptor
            if (
                descriptor.get("path")
                == "apps/agent-park/park-state.json"
                and metadata.get("schema")
                == "rappterzoo-agent-amusement-park/1"
            ):
                legacy["state"] = descriptor
    assert set(legacy) == {"contract", "state"}
    contract = sync_client.validate_data_descriptor(legacy["contract"])
    state = sync_client.validate_data_descriptor(legacy["state"])
    assert contract["metadata"]["resource_type"] == "agent-contract-v1"
    assert state["metadata"]["agent_contract"] == "agent-contract.json"


def test_agent_park_ledger_allows_only_valid_prefix_growth(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    target = copy_agent_park(root)
    builder.build(root)
    events, _contract = migrate_agent_park_v2(target)
    event = events[-1]

    result = builder.build(root)
    snapshot = read_json(root / "apps" / "syndication" / "snapshot.json")
    descriptor = next(
        item
        for item in snapshot["data_objects"]
        if item["path"] == "apps/agent-park/events.jsonl"
    )
    assert result["delta_created"] is True
    assert descriptor["metadata"]["event_count"] == len(events)
    assert descriptor["metadata"]["event_head"] == event["event_hash"]

    mutated = json.loads(json.dumps(events))
    mutated[3]["payload"]["night"] = 99
    with pytest.raises(
        builder.SyndicationError,
        match="payload hash mismatch",
    ):
        builder.validate_agent_park_event_ledger(mutated)
    with pytest.raises(
        sync_client.SyncError,
        match="payload hash mismatch",
    ):
        sync_client.validate_agent_park_event_ledger(mutated)


def test_agent_park_v2_allows_future_growth_but_rejects_fork(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    target = copy_agent_park(root)
    builder.build(root)
    events, _contract = migrate_agent_park_v2(target)
    builder.build(root)

    events = append_park_event(events)
    write_park_events(target, events)
    rewrite_v2_bundle_for_events(target, events)
    assert builder.build(root)["delta_created"] is True

    forked = json.loads(json.dumps(events))
    forked[50]["payload"]["season"] = 99
    forked = rechain_park_events(forked)
    write_park_events(target, forked)
    rewrite_v2_bundle_for_events(target, forked)
    with pytest.raises(
        builder.SyndicationError,
        match="valid prefix growth",
    ):
        builder.build(root)


def test_agent_park_event_structure_hashes_and_links_are_strict(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    target = copy_agent_park(root)
    original = read_park_events(target)
    mutations = []

    bad_utc = json.loads(json.dumps(original))
    bad_utc[2]["utc"] = "not-a-time"
    mutations.append(rechain_park_events(bad_utc))

    bad_kind = json.loads(json.dumps(original))
    bad_kind[2]["kind"] = "Park Night Open"
    mutations.append(rechain_park_events(bad_kind))

    bad_prev = json.loads(json.dumps(original))
    bad_prev[2]["prev"] = "0" * 64
    projected = {
        key: value
        for key, value in bad_prev[2].items()
        if key != "event_hash"
    }
    bad_prev[2]["event_hash"] = builder.frame_hash_value(
        builder.AGENT_PARK_EVENT_SPACE,
        projected,
    )
    mutations.append(bad_prev)

    bad_hash = json.loads(json.dumps(original))
    bad_hash[2]["event_hash"] = "0" * 64
    mutations.append(bad_hash)

    for events in mutations:
        with pytest.raises(builder.SyndicationError):
            builder.validate_agent_park_event_ledger(events)
        with pytest.raises(sync_client.SyncError):
            sync_client.validate_agent_park_event_ledger(events)


@pytest.mark.parametrize("season", [1, 2])
def test_agent_park_event_timestamps_must_strictly_increase(
    tmp_path,
    season,
):
    root, _manifest, _frames = make_repo(tmp_path)
    target = copy_agent_park(root)
    events = read_park_events(target)
    if season == 2:
        events, _contract = migrate_agent_park_v2(target)
    events[-1]["utc"] = events[-2]["utc"]
    events = rechain_park_events(events)

    with pytest.raises(
        builder.SyndicationError,
        match="strictly increasing",
    ):
        builder.validate_agent_park_event_ledger(events)
    with pytest.raises(
        sync_client.SyncError,
        match="strictly increasing",
    ):
        sync_client.validate_agent_park_event_ledger(events)


def test_agent_park_state_must_match_ledger_head_count_and_digest(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    target = copy_agent_park(root)
    state_path = target / "park-state.json"
    state = read_json(state_path)
    state["event_ledger"]["head"] = "0" * 64
    state["event_ledger"]["sha256"] = "1" * 64
    write_json(state_path, state)

    with pytest.raises(
        builder.SyndicationError,
        match="state.*ledger",
    ):
        builder.build(root)


def test_agent_park_growth_requires_coherent_state_advance(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    target = copy_agent_park(root)
    builder.build(root)
    events = append_park_event(read_park_events(target))
    write_park_events(target, events)

    with pytest.raises(
        builder.SyndicationError,
        match="state.*ledger",
    ):
        builder.build(root)


@pytest.mark.parametrize("mutation", ["fork", "reorder", "truncate", "remove"])
def test_agent_park_rejects_non_prefix_history_changes(tmp_path, mutation):
    root, _manifest, _frames = make_repo(tmp_path)
    target = copy_agent_park(root)
    builder.build(root)
    events = read_park_events(target)

    if mutation == "fork":
        events[3]["payload"]["night"] = 99
        events = rechain_park_events(events)
        write_park_events(target, events)
        update_park_state(target, events)
    elif mutation == "reorder":
        events[3], events[4] = events[4], events[3]
        events = rechain_park_events(events)
        write_park_events(target, events)
        update_park_state(target, events)
    elif mutation == "truncate":
        events = events[:-1]
        write_park_events(target, events)
        update_park_state(target, events)
    else:
        (target / "events.jsonl").unlink()
        (target / "park-state.json").unlink()

    with pytest.raises(
        builder.SyndicationError,
        match="agent park|immutable",
    ):
        builder.build(root)


def test_sync_rejects_agent_park_state_ledger_metadata_divergence(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    target = copy_agent_park(root)
    state_dir = tmp_path / "state"
    with serving(root) as server:
        build_served(root, server)
        sync_client.sync_repository(
            state_dir,
            server.index_url,
            fetch_apps=True,
        )
        descriptors = builder.build_public_data_descriptors(
            root,
            server.base_url,
        )
        state = next(
            descriptor
            for descriptor in descriptors
            if descriptor["metadata"].get("resource_type") == "state"
        )
        state = json.loads(json.dumps(state))
        state["metadata"]["event_head"] = "0" * 64
        append_data_delta(root, server.base_url, [state])

        with pytest.raises(
            sync_client.SyncError,
            match="state.*ledger",
        ):
            sync_client.sync_repository(state_dir, server.index_url)

    assert sync_client.status(state_dir)["head_sequence"] == "0"
    assert (target / "events.jsonl").is_file()


def test_sync_rejects_agent_park_fork_before_checkpoint_advance(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    target = copy_agent_park(root)
    state_dir = tmp_path / "state"
    with serving(root) as server:
        build_served(root, server)
        sync_client.sync_repository(
            state_dir,
            server.index_url,
            fetch_apps=True,
        )
        initial = sync_client.status(state_dir)
        events, _contract = migrate_agent_park_v2(target)
        descriptors = [
            descriptor
            for descriptor in builder.build_public_data_descriptors(
                root,
                server.base_url,
            )
            if descriptor["metadata"].get("resource_type") in {
                "agent-contract-v2",
                "event-ledger",
                "state",
            }
        ]
        events[3]["payload"]["night"] = 99
        events = rechain_park_events(events)
        write_park_events(target, events)
        rewrite_v2_bundle_for_events(target, events)
        for descriptor in descriptors:
            resource_type = descriptor["metadata"]["resource_type"]
            object_path = root / descriptor["path"]
            object_bytes = object_path.read_bytes()
            descriptor["sha256"] = hashlib.sha256(
                object_bytes
            ).hexdigest()
            descriptor["size"] = len(object_bytes)
            descriptor["content_id"] = "sha256:" + descriptor["sha256"]
            if resource_type == "event-ledger":
                descriptor["metadata"]["event_count"] = len(events)
                descriptor["metadata"]["event_head"] = events[-1][
                    "event_hash"
                ]
            else:
                descriptor["metadata"] = builder._agent_park_metadata(
                    read_json(object_path),
                    descriptor["path"],
                )
        append_data_delta(root, server.base_url, descriptors)

        with pytest.raises(
            sync_client.SyncError,
            match="prefix|fork",
        ):
            sync_client.sync_repository(state_dir, server.index_url)

    current = sync_client.status(state_dir)
    assert current["head_sequence"] == initial["head_sequence"] == "0"
    assert current["head_sha256"] == initial["head_sha256"]


def test_attention_comment_privacy_and_object_immutability(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    attention_path = root / "apps" / "attention" / "group-unsafe.json"
    attention_path.parent.mkdir(parents=True)
    unsafe = {
        "comments": [{
            "body": "Must not escape",
            "comment_id": "comment-private",
            "selected": False,
            "visibility": "public",
        }],
        "group_id": "unsafe",
        "visibility": "public-metadata",
    }
    attention_path.write_bytes(builder.stable_json_bytes(unsafe))
    with pytest.raises(
        builder.SyndicationError,
        match="unselected or non-public comment body",
    ):
        builder.build(root)
    with pytest.raises(
        sync_client.SyncError,
        match="unselected or non-public comment body",
    ):
        sync_client.validate_public_data_bytes(
            attention_path.read_bytes(),
            "application/json",
        )

    safe = {
        "comments": [{
            "body": "Selected",
            "comment_id": "comment-selected",
            "selected": True,
            "visibility": "public",
        }],
        "group_id": "safe",
        "visibility": "public-metadata",
    }
    attention_path.write_bytes(builder.stable_json_bytes(safe))
    builder.build(root)
    safe["comments"][0]["body"] = "Changed in place"
    attention_path.write_bytes(builder.stable_json_bytes(safe))
    with pytest.raises(
        builder.SyndicationError,
        match="immutable attention data object changed",
    ):
        builder.build(root)


def test_explicit_false_privacy_policy_is_public_but_true_is_rejected():
    safe = {
        "private_media_in_public_ledger": False,
        "pulse_persisted": False,
        "visibility": "public-metadata",
    }
    builder.validate_public_data_value(safe)
    sync_client.validate_public_data_value(safe)
    unsafe = dict(safe)
    unsafe["private_media_in_public_ledger"] = True
    with pytest.raises(
        builder.SyndicationError,
        match="sensitive key",
    ):
        builder.validate_public_data_value(unsafe)
    with pytest.raises(
        sync_client.SyncError,
        match="sensitive key",
    ):
        sync_client.validate_public_data_value(unsafe)


def test_false_token_policy_is_public_but_credentials_are_rejected():
    safe_policy = {
        "consensus": "none",
        "token": False,
        "visibility": "public-metadata",
    }
    builder.validate_public_data_value(safe_policy)
    sync_client.validate_public_data_value(safe_policy)
    none_policy = {
        "consensus": "none",
        "token": "none",
        "visibility": "public-metadata",
    }
    builder.validate_public_data_value(none_policy)
    sync_client.validate_public_data_value(none_policy)
    for unsafe in (
        {"token": "secret", "visibility": "public-metadata"},
        {"access_token": False, "visibility": "public-metadata"},
        {"client_secret": "secret", "visibility": "public-metadata"},
    ):
        with pytest.raises(builder.SyndicationError):
            builder.validate_public_data_value(unsafe)
        with pytest.raises(sync_client.SyncError):
            sync_client.validate_public_data_value(unsafe)


def test_dimension_requires_base_branch_and_drift_metadata(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    dimension_path = root / "apps" / "attention" / "dimension.json"
    dimension_path.parent.mkdir(parents=True)
    dimension_path.write_bytes(builder.stable_json_bytes({
        "base_record_id": "record-1",
        "branch": "hot",
        "dimension_id": "dimension-1",
        "schema": "rappterzoo-dimension/1",
        "visibility": "public-metadata",
    }))
    with pytest.raises(
        builder.SyndicationError,
        match="lacks drift metadata",
    ):
        builder.build(root)


def test_fold_shards_publish_only_public_accepted_provenance(tmp_path):
    root, _manifest, frames = make_repo(tmp_path)
    accepted_frame = make_frame(
        2,
        frames[-1],
        kind="zoo.dimension",
        event="dimension",
        payload_updates={
            "assembler_status": "accepted",
            "frame_control": {"mode": "assigned"},
            "lease_id": "lease-1",
            "main_append": True,
            "shard_id": "shard-1",
        },
    )
    frames.append(accepted_frame)
    write_frames(root, frames)
    shard_dir = root / "apps" / "shards"
    shard_dir.mkdir(parents=True)
    objects = {
        "01-assignment.json": {
            "assignment_id": "assignment-1",
            "frame_control": {"mode": "assigned"},
            "kind": "fold-shard-assignment",
            "shard_id": "shard-1",
            "visibility": "public-metadata",
        },
        "02-lease.json": {
            "kind": "fold-shard-lease",
            "frame_control": {"mode": "assigned"},
            "lease_id": "lease-1",
            "lease_bounds": {
                "expires_at": "2026-08-15T20:00:00.000Z",
                "max_items": 4,
            },
            "shard_id": "shard-1",
            "visibility": "public-metadata",
        },
        "03-result.json": {
            "assembler_status": "accepted",
            "frame_control": {"mode": "assigned"},
            "kind": "fold-shard-result",
            "main_append": True,
            "lease_id": "lease-1",
            "provenance": {
                "source_content_ids": ["sha256:source-1"],
            },
            "result_id": "result-1",
            "shard_id": "shard-1",
            "visibility": "public-metadata",
        },
        "04-dimension.json": {
            "assembler_status": "accepted",
            "base_record_id": "record-1",
            "branch": "hot",
            "dimension_id": "shard-dimension-1",
            "drift": {"field": "salience", "direction": "up"},
            "frame_control": {"mode": "assigned"},
            "kind": "fold-shard-dimension",
            "main_append": True,
            "lease_id": "lease-1",
            "provenance": {
                "source_content_ids": ["sha256:source-1"],
            },
            "shard_id": "shard-1",
            "visibility": "public-metadata",
        },
        "05-rejected.json": {
            "assembler_status": "rejected",
            "frame_control": {"mode": "assigned"},
            "kind": "fold-shard-result",
            "main_append": False,
            "shard_id": "shard-1",
            "visibility": "public-metadata",
        },
        "06-private.json": {
            "assignment_id": "assignment-private",
            "endpoint_url": "https://private.invalid/worker",
            "kind": "fold-shard-assignment",
            "frame_control": {"mode": "assigned"},
            "private_input": "not publishable",
            "shard_id": "shard-private",
            "visibility": "public-metadata",
        },
    }
    for name, value in objects.items():
        (shard_dir / name).write_bytes(
            builder.stable_json_bytes(value)
        )
    state_dir = tmp_path / "state"
    with serving(root) as server:
        build_served(root, server)
        result = sync_client.sync_repository(
            state_dir,
            server.index_url,
            fetch_apps=True,
        )
    snapshot = read_json(
        root / "apps" / "syndication" / "snapshot.json"
    )
    shard_index = read_json(
        root / "apps" / "syndication" / "index.json"
    )
    listed = sync_client.list_data_objects(state_dir)
    current = sync_client.status(state_dir)
    exported_path = tmp_path / "shard-export.json"
    sync_client.export_state(state_dir, exported_path)
    exported = read_json(exported_path)

    shard_objects = [
        item
        for item in snapshot["data_objects"]
        if item["kind"].startswith("fold-shard-")
    ]
    assert [item["kind"] for item in shard_objects] == [
        "fold-shard-assignment",
        "fold-shard-lease",
        "fold-shard-result-object",
        "fold-shard-dimension-object",
    ]
    assert all(
        item["metadata"]["isolated_shard_provenance"] is True
        for item in shard_objects
    )
    assert all(
        "endpoint" not in json.dumps(item).lower()
        and "private_input" not in json.dumps(item).lower()
        for item in shard_objects
    )
    assert not any(
        item["path"].endswith("05-rejected.json")
        or item["path"].endswith("06-private.json")
        for item in snapshot["data_objects"]
    )
    assert result["fetched_objects"] == 6
    assert shard_index["deltas"][0]["block"]["frame_control"] == {
        "lease_required": True,
        "mode": "assigned",
        "proof_race": False,
    }
    assert current["shard_provenance"] == 4
    assert [item["kind"] for item in listed] == [
        "fold-shard-assignment",
        "fold-shard-lease",
        "fold-shard-result-object",
        "fold-shard-dimension-object",
    ]
    assert len(exported["shard_provenance"]) == 4


def test_fold_shard_frames_require_assembler_acceptance():
    genesis = make_frame(0)
    candidate = make_frame(
        1,
        genesis,
        kind="zoo.dimension",
        event="dimension",
        payload_updates={
            "assembler_status": "rejected",
            "frame_control": {"mode": "proof-of-fold"},
            "lease_id": "lease-rejected",
            "main_append": False,
            "shard_id": "shard-rejected",
        },
    )
    with pytest.raises(
        builder.SyndicationError,
        match="assigned lease and assembler acceptance",
    ):
        builder.validate_frames([genesis, candidate])
    with pytest.raises(
        sync_client.SyncError,
        match="assigned lease and assembler acceptance",
    ):
        sync_client.validate_frames(
            [genesis, candidate],
            None,
            set(),
        )


def test_proof_of_fold_block_broadcast_apply_and_witness(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    fold_dir = root / "apps" / "fold"
    fold_dir.mkdir(parents=True)
    accepted = {
        "01-challenge.json": {
            "assembler_status": "accepted",
            "challenge_id": "challenge-1",
            "frame_control": {"mode": "proof-of-fold"},
            "kind": "fold-challenge",
            "main_append": True,
            "shard_id": "shard-cycle-1",
            "visibility": "public-metadata",
        },
        "02-proof.json": {
            "assembler_status": "accepted",
            "challenge_id": "challenge-1",
            "frame_control": {"mode": "proof-of-fold"},
            "kind": "fold-proof",
            "main_append": True,
            "proof_id": "proof-1",
            "shard_id": "shard-cycle-1",
            "visibility": "public-metadata",
        },
        "03-award.json": {
            "assembler_status": "accepted",
            "award_id": "award-1",
            "challenge_id": "challenge-1",
            "control_id": "control-1",
            "frame_control": {"mode": "proof-of-fold"},
            "kind": "fold-control-award",
            "main_append": True,
            "shard_id": "shard-cycle-1",
            "visibility": "public-metadata",
        },
        "04-action.json": {
            "action_id": "action-1",
            "action_receipt_id": "action-receipt-1",
            "assembler_status": "accepted",
            "challenge_id": "challenge-1",
            "frame_control": {"mode": "proof-of-fold"},
            "kind": "fold-action-receipt",
            "main_append": True,
            "shard_id": "shard-cycle-1",
            "visibility": "public-metadata",
        },
    }
    for name, value in accepted.items():
        (fold_dir / name).write_bytes(
            builder.stable_json_bytes(value)
        )
    (fold_dir / "05-rejected.json").write_bytes(
        builder.stable_json_bytes({
            "assembler_status": "rejected",
            "challenge_id": "challenge-1",
            "frame_control": {"mode": "proof-of-fold"},
            "kind": "fold-proof",
            "main_append": False,
            "participant_secret": "never-publish",
            "proof_id": "proof-rejected",
            "shard_id": "shard-cycle-1",
            "visibility": "public-metadata",
        })
    )
    (fold_dir / "06-private.json").write_bytes(
        builder.stable_json_bytes({
            "assembler_status": "accepted",
            "challenge_id": "challenge-1",
            "frame_control": {"mode": "proof-of-fold"},
            "kind": "fold-proof",
            "main_append": True,
            "participant_secret": "never-publish",
            "proof_id": "proof-private",
            "shard_id": "shard-cycle-1",
            "visibility": "public-metadata",
        })
    )
    state_dir = tmp_path / "state"
    receipt_path = tmp_path / "cycle-witness.json"
    with serving(root) as server:
        build_served(root, server, synthetic_test_mode=True)
        with pytest.raises(
            sync_client.SyncError,
            match="disabled during public soak",
        ):
            sync_client.sync_repository(
                tmp_path / "default-state",
                server.index_url,
                fetch_apps=True,
            )
        synced = sync_client.sync_repository(
            state_dir,
            server.index_url,
            fetch_apps=True,
            allow_synthetic_proofs=True,
        )
        witnessed = sync_client.emit_witness_receipt(
            state_dir,
            receipt_path,
        )

    index = read_json(root / "apps" / "syndication" / "index.json")
    entry = index["deltas"][0]
    block = entry["block"]
    cycle = block["proof_of_fold"]["cycles"][0]
    json_feed = read_json(root / "apps" / "syndication" / "feed.json")
    atom = ElementTree.parse(
        str(root / "apps" / "syndication" / "feed.xml")
    ).getroot()
    namespace = {
        "atom": "http://www.w3.org/2005/Atom",
        "rappterzoo": (
            "https://kody-w.github.io/"
            "localFirstTools-main/ns/syndication"
        ),
    }
    atom_block = json.loads(
        atom.find(
            "atom:entry/rappterzoo:block",
            namespace,
        ).text
    )
    snapshot = read_json(
        root / "apps" / "syndication" / "snapshot.json"
    )
    paths = {
        item["path"]
        for item in snapshot["data_objects"]
    }
    current = sync_client.status(state_dir)
    witness = read_json(receipt_path)

    assert block["model"] == builder.BLOCK_MODEL
    assert block["consensus"] == "none"
    assert block["mining"] is False
    assert block["token"] is False
    assert block["rollout"]["default_frame_control_mode"] == "observer"
    assert block["frame_control"]["mode"] == "proof-of-fold"
    assert block["frame_control"]["proof_race"] is False
    assert block["proof_of_fold"]["status"] == "synthetic-test-only"
    assert block["proof_of_fold"]["synthetic_test_only"] is True
    assert block["resulting_head"]["sha256"] == entry["sha256"]
    assert block["next_frame_challenge_seed"] == (
        builder.next_challenge_seed(entry["sha256"])
    )
    assert cycle["challenge_id"] == "challenge-1"
    assert len(cycle["proof_receipts"]) == 1
    assert len(cycle["control_award_receipts"]) == 1
    assert len(cycle["action_receipts"]) == 1
    assert json_feed["items"][0]["_rappterzoo"]["block"] == block
    assert atom_block == block
    assert not any(path.endswith("05-rejected.json") for path in paths)
    assert not any(path.endswith("06-private.json") for path in paths)
    assert "participant_secret" not in json.dumps(snapshot).lower()
    assert synced["applied_deltas"] == 1
    assert current["blocks"] == 1
    assert current["next_frame_challenge_seed"] == (
        block["next_frame_challenge_seed"]
    )
    assert witnessed["head_sha256"] == entry["sha256"]
    assert witness["statement"]["next_frame_challenge_seed"] == (
        block["next_frame_challenge_seed"]
    )


def test_public_soak_excludes_live_proof_race_objects(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    fold_dir = root / "apps" / "fold"
    fold_dir.mkdir(parents=True)
    for name, value in {
        "challenge.json": {
            "assembler_status": "accepted",
            "challenge_id": "live-challenge",
            "kind": "fold-challenge",
            "main_append": True,
            "shard_id": "live-shard",
            "visibility": "public-metadata",
        },
        "proof.json": {
            "assembler_status": "accepted",
            "challenge_id": "live-challenge",
            "kind": "fold-proof",
            "main_append": True,
            "proof_id": "live-proof",
            "shard_id": "live-shard",
            "visibility": "public-metadata",
        },
    }.items():
        (fold_dir / name).write_bytes(builder.stable_json_bytes(value))

    builder.build(root)
    snapshot = read_json(
        root / "apps" / "syndication" / "snapshot.json"
    )
    index = read_json(root / "apps" / "syndication" / "index.json")
    paths = {item["path"] for item in snapshot["data_objects"]}

    assert "apps/fold/challenge.json" not in paths
    assert "apps/fold/proof.json" not in paths
    assert index["deltas"][0]["block"]["proof_of_fold"]["cycles"] == []
    assert index["deltas"][0]["block"]["proof_of_fold"]["status"] == (
        "disabled-observer"
    )
    assert index["rollout"]["activation"] == (
        "explicit-future-owner-gate-required"
    )


def test_sync_uses_conditional_get_and_304(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    state_dir = tmp_path / "state"
    with serving(root) as server:
        build_served(root, server)
        first = sync_client.sync_repository(
            state_dir,
            server.index_url,
        )
        second = sync_client.sync_repository(
            state_dir,
            server.index_url,
            fetch_apps=True,
        )

    assert first["applied_deltas"] == 1
    assert first["not_modified"] is False
    assert second["applied_deltas"] == 0
    assert second["not_modified"] is True
    assert second["fetched_apps"] == 2
    index_requests = [
        request
        for request in server.requests
        if request["path"].endswith("/index.json")
    ]
    assert index_requests[-1]["if_none_match"]
    synced_status = sync_client.status(state_dir)
    assert synced_status["deltas"] == 1
    assert synced_status["objects"] == 2
    assert synced_status["acknowledgements"] == 1
    assert (
        synced_status["rate_budget"]["recommended_min_sync_interval_seconds"]
        == 1800
    )


def test_304_fetch_apps_repairs_missing_and_corrupt_cache(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    state_dir = tmp_path / "state"
    with serving(root) as server:
        build_served(root, server)
        sync_client.sync_repository(
            state_dir,
            server.index_url,
            fetch_apps=True,
        )
        apps = sync_client.list_apps(state_dir)
        missing = sync_client._object_path(state_dir, apps[0]["sha256"])
        corrupt = sync_client._object_path(state_dir, apps[1]["sha256"])
        missing.unlink()
        corrupt.write_bytes(b"corrupt")

        result = sync_client.sync_repository(
            state_dir,
            server.index_url,
            fetch_apps=True,
        )

    assert result["not_modified"] is True
    assert result["fetched_objects"] == 2
    for app in apps:
        cached = sync_client._object_path(state_dir, app["sha256"])
        assert hashlib.sha256(cached.read_bytes()).hexdigest() == app["sha256"]


def test_duplicate_and_concurrent_syncs_are_idempotent(tmp_path, monkeypatch):
    root, _manifest, _frames = make_repo(tmp_path)
    state_dir = tmp_path / "state"
    errors = []
    results = []
    barrier = threading.Barrier(2)
    original_fetch = sync_client.fetch_url

    def synchronized_fetch(url, headers=None, max_bytes=sync_client.MAX_DELTA_BYTES):
        if url.endswith("/index.json") and not headers:
            try:
                barrier.wait(timeout=0.5)
            except threading.BrokenBarrierError:
                pass
        return original_fetch(url, headers=headers, max_bytes=max_bytes)

    monkeypatch.setattr(sync_client, "fetch_url", synchronized_fetch)
    with serving(root) as server:
        build_served(root, server)

        def run_sync():
            try:
                results.append(
                    sync_client.sync_repository(
                        state_dir,
                        server.index_url,
                    )
                )
            except Exception as error:
                errors.append(error)

        threads = [threading.Thread(target=run_sync) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

    assert errors == []
    assert len(results) == 2
    assert sorted(result["applied_deltas"] for result in results) == [0, 1]
    assert sum(result["not_modified"] for result in results) == 1
    current = sync_client.status(state_dir)
    assert current["deltas"] == 1
    assert current["frames"] == 2


def test_sync_rejects_delta_byte_tamper(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    state_dir = tmp_path / "state"
    with serving(root) as server:
        build_served(root, server)
        delta_paths(root)[0].write_bytes(
            delta_paths(root)[0].read_bytes() + b" "
        )
        with pytest.raises(
            sync_client.SyncError,
            match="content (hash|size)",
        ):
            sync_client.sync_repository(state_dir, server.index_url)
    assert sync_client.status(state_dir)["deltas"] == 0


def test_sync_rejects_replay_and_gap(tmp_path):
    replay_root, _manifest, _frames = make_repo(tmp_path / "replay")
    with serving(replay_root) as server:
        build_served(replay_root, server)
        index_path = replay_root / "apps" / "syndication" / "index.json"
        index = read_json(index_path)
        index["deltas"].append(dict(index["deltas"][0]))
        index["delta_count"] = 2
        index["head"] = {
            "sequence": 0,
            "sha256": index["deltas"][-1]["sha256"],
        }
        write_json(index_path, index)
        with pytest.raises(sync_client.SyncError, match="replay, gap"):
            sync_client.sync_repository(
                tmp_path / "replay-state",
                server.index_url,
            )

    gap_root, _manifest, _frames = make_repo(tmp_path / "gap")
    with serving(gap_root) as server:
        build_served(gap_root, server)
        index_path = gap_root / "apps" / "syndication" / "index.json"
        index = read_json(index_path)
        index["deltas"][0]["sequence"] = 1
        index["head"]["sequence"] = 1
        write_json(index_path, index)
        with pytest.raises(sync_client.SyncError, match="replay, gap"):
            sync_client.sync_repository(
                tmp_path / "gap-state",
                server.index_url,
            )


def test_sync_rejects_wrong_previous_delta(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    with serving(root) as server:
        build_served(root, server)
        mutate_app(root)
        build_served(root, server)
        index_path = root / "apps" / "syndication" / "index.json"
        index = read_json(index_path)
        index["deltas"][1]["previous_delta"] = "0" * 64
        write_json(index_path, index)
        with pytest.raises(sync_client.SyncError, match="bad link"):
            sync_client.sync_repository(
                tmp_path / "state",
                server.index_url,
            )


def test_sync_rejects_cross_stream_delta_graft(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    state_dir = tmp_path / "state"
    with serving(root) as server:
        build_served(root, server)
        index_path = root / "apps" / "syndication" / "index.json"
        index = read_json(index_path)
        original_entry = index["deltas"][0]
        original_delta_path = (
            root / "apps" / "syndication" / original_entry["path"]
        )
        delta = read_json(original_delta_path)
        delta["stream_id"] = "https://evil.invalid/other-stream/"
        data = builder.stable_json_bytes(delta)
        digest = hashlib.sha256(data).hexdigest()
        graft_path = (
            root / "apps" / "syndication" / "deltas"
            / (digest + ".json")
        )
        graft_path.write_bytes(data)
        entry = dict(original_entry)
        entry["sha256"] = digest
        entry["path"] = "deltas/{}.json".format(digest)
        entry["size"] = len(data)
        entry["url"] = (
            server.base_url
            + "apps/syndication/deltas/{}.json".format(digest)
        )
        entry["block"] = builder.block_metadata(delta, digest)
        index["deltas"] = [entry]
        index["head"] = {
            "path": entry["path"],
            "sequence": 0,
            "sha256": digest,
            "url": entry["url"],
        }
        index["next_frame_challenge_seed"] = entry["block"][
            "next_frame_challenge_seed"
        ]
        write_json(index_path, index)

        with pytest.raises(
            sync_client.SyncError,
            match="delta metadata mismatch",
        ):
            sync_client.sync_repository(state_dir, server.index_url)
    assert sync_client.status(state_dir)["deltas"] == 0


def test_sync_rejects_since_seq_and_segment_hash_mutations(tmp_path):
    since_root, _manifest, _frames = make_repo(tmp_path / "since")
    with serving(since_root) as server:
        build_served(since_root, server)
        index_path = since_root / "apps" / "syndication" / "index.json"
        index = read_json(index_path)
        index["deltas"][0]["since_seq"] = 0
        write_json(index_path, index)
        with pytest.raises(sync_client.SyncError, match="replay, gap"):
            sync_client.sync_repository(
                tmp_path / "since-state",
                server.index_url,
            )

    segment_root, _manifest, _frames = make_repo(tmp_path / "segment")
    with serving(segment_root) as server:
        build_served(segment_root, server)
        index_path = segment_root / "apps" / "syndication" / "index.json"
        index = read_json(index_path)
        index["deltas"][0]["segment_hashes"]["apps"] = "0" * 64
        write_json(index_path, index)
        with pytest.raises(sync_client.SyncError, match="segment hash"):
            sync_client.sync_repository(
                tmp_path / "segment-state",
                server.index_url,
            )


def test_sync_rejects_unpinned_descriptor():
    descriptor = {
        "metadata": {},
        "path": "apps/demo/unpinned.html",
        "sha256": "0" * 64,
        "size": 1,
        "url": "https://example.test/unpinned.html",
    }
    with pytest.raises(sync_client.SyncError, match="unpinned"):
        sync_client.validate_descriptor(descriptor)


def test_sync_refuses_silent_cursor_reset(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    state_dir = tmp_path / "state"
    with serving(root) as server:
        build_served(root, server)
        mutate_app(root)
        build_served(root, server)
        sync_client.sync_repository(state_dir, server.index_url)
        index_path = root / "apps" / "syndication" / "index.json"
        index = read_json(index_path)
        index["deltas"] = index["deltas"][:1]
        index["delta_count"] = 1
        first = index["deltas"][0]
        index["head"] = {
            "path": first["path"],
            "sequence": first["sequence"],
            "sha256": first["sha256"],
            "url": first["url"],
        }
        index["cursor"]["head_seq"] = 0
        index["next_frame_challenge_seed"] = first["block"][
            "next_frame_challenge_seed"
        ]
        write_json(index_path, index)
        with pytest.raises(sync_client.SyncError, match="rolled back"):
            sync_client.sync_repository(state_dir, server.index_url)
    assert sync_client.status(state_dir)["deltas"] == 2


def test_independent_witness_receipts_and_fork_evidence(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    state_a = tmp_path / "replica-a"
    state_b = tmp_path / "replica-b"
    receipt_a_path = tmp_path / "witness-a.json"
    receipt_b_path = tmp_path / "witness-b.json"
    with serving(root) as server:
        build_served(root, server)
        sync_client.sync_repository(state_a, server.index_url)
        sync_client.sync_repository(state_b, server.index_url)
        witness_a = sync_client.emit_witness_receipt(
            state_a,
            receipt_a_path,
        )
        witness_b = sync_client.emit_witness_receipt(
            state_b,
            receipt_b_path,
        )
        receipt_a = read_json(receipt_a_path)
        receipt_b = read_json(receipt_b_path)
        assert witness_a["head_sha256"] == witness_b["head_sha256"]
        assert witness_a["witness_id"] != witness_b["witness_id"]
        for receipt in (receipt_a, receipt_b):
            statement = receipt["statement"]
            assert receipt["statement_sha256"] == hashlib.sha256(
                builder.stable_json_bytes(statement)
            ).hexdigest()
            assert statement["authority"]["consensus"] == "none"
            assert statement["authority"]["publisher_authority"] == "centralized"
            assert statement["authority"]["quorum"] == "not-configured"
            assert statement["authority"]["token"] is False
            assert statement["authority"]["mining"] is False

        index_path = root / "apps" / "syndication" / "index.json"
        index = read_json(index_path)
        fork_hash = "1" * 64
        index["deltas"][0]["sha256"] = fork_hash
        index["deltas"][0]["path"] = "deltas/{}.json".format(fork_hash)
        index["head"]["sha256"] = fork_hash
        index["head"]["path"] = index["deltas"][0]["path"]
        index["deltas"][0]["block"]["resulting_head"]["sha256"] = (
            fork_hash
        )
        index["deltas"][0]["block"][
            "next_frame_challenge_seed"
        ] = builder.next_challenge_seed(fork_hash)
        index["next_frame_challenge_seed"] = index["deltas"][0]["block"][
            "next_frame_challenge_seed"
        ]
        write_json(index_path, index)
        with pytest.raises(
            sync_client.SyncError,
            match="fork/drift evidence",
        ):
            sync_client.sync_repository(state_a, server.index_url)

    assert sync_client.status(state_a)["witnesses"] == 1
    assert sync_client.status(state_b)["witnesses"] == 1


def test_fetch_apps_rejects_hash_mismatch_and_rolls_back(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    state_dir = tmp_path / "state"
    with serving(root) as server:
        build_served(root, server)
        app_path = root / "apps" / "demo" / "alpha.html"
        changed = bytearray(app_path.read_bytes())
        changed[-2] = changed[-2] ^ 1
        app_path.write_bytes(bytes(changed))
        with pytest.raises(sync_client.SyncError, match="object (size|hash) mismatch"):
            sync_client.sync_repository(
                state_dir,
                server.index_url,
                fetch_apps=True,
            )
    result = sync_client.status(state_dir)
    assert result["deltas"] == 0
    assert result["active_apps"] == 0


def test_partial_object_fetch_failure_removes_staged_cache(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    state_dir = tmp_path / "state"
    with serving(root) as server:
        build_served(root, server)
        mutate_app(root, "beta.html")
        with pytest.raises(
            sync_client.SyncError,
            match="object size mismatch|response exceeds byte limit",
        ):
            sync_client.sync_repository(
                state_dir,
                server.index_url,
                fetch_apps=True,
            )

    objects_dir = state_dir / "objects"
    cached = [
        path
        for path in objects_dir.rglob("*")
        if path.is_file()
    ] if objects_dir.exists() else []
    assert cached == []
    assert sync_client.status(state_dir)["objects"] == 0


def test_storage_transaction_failure_rolls_back_database_and_cache(
    tmp_path,
    monkeypatch,
):
    root, _manifest, _frames = make_repo(tmp_path)
    state_dir = tmp_path / "state"
    original_set_meta = sync_client._set_meta

    def fail_last_sync(connection, key, value):
        if key == "last_sync":
            raise RuntimeError("injected storage transaction failure")
        return original_set_meta(connection, key, value)

    monkeypatch.setattr(sync_client, "_set_meta", fail_last_sync)
    with serving(root) as server:
        build_served(root, server)
        with pytest.raises(
            RuntimeError,
            match="injected storage transaction failure",
        ):
            sync_client.sync_repository(
                state_dir,
                server.index_url,
                fetch_apps=True,
            )

    current = sync_client.status(state_dir)
    assert current["deltas"] == 0
    assert current["active_apps"] == 0
    assert current["frames"] == 0
    assert current["objects"] == 0
    objects_dir = state_dir / "objects"
    assert not objects_dir.exists() or not any(
        path.is_file()
        for path in objects_dir.rglob("*")
    )


def test_multiple_delta_failure_rolls_back_entire_apply(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    state_dir = tmp_path / "state"
    with serving(root) as server:
        build_served(root, server)
        mutate_app(root)
        build_served(root, server)
        second_delta = delta_path_for_sequence(root, 1)
        second_delta.write_bytes(second_delta.read_bytes() + b" ")
        with pytest.raises(
            sync_client.SyncError,
            match="content (hash|size)",
        ):
            sync_client.sync_repository(state_dir, server.index_url)
    result = sync_client.status(state_dir)
    assert result["deltas"] == 0
    assert result["active_apps"] == 0
    assert result["frames"] == 0


def test_tombstone_preserves_local_overlay_and_materializes_it(tmp_path):
    root, _manifest, _frames = make_repo(
        tmp_path,
        app_names=("alpha.html",),
    )
    state_dir = tmp_path / "state"
    local_file = tmp_path / "local-alpha.html"
    local_file.write_bytes(b"<title>Local overlay</title>\n")
    with serving(root) as server:
        build_served(root, server)
        sync_client.sync_repository(
            state_dir,
            server.index_url,
            fetch_apps=True,
        )
        sync_client.add_local_app(
            state_dir,
            local_file,
            "apps/demo/alpha.html",
            "Local Alpha",
        )
        remove_manifest_app(root, "alpha.html")
        build_served(root, server)
        sync_client.sync_repository(state_dir, server.index_url)

    result = sync_client.status(state_dir)
    apps = sync_client.list_apps(state_dir)
    output = tmp_path / "materialized"
    sync_client.materialize(state_dir, output)
    exported_path = tmp_path / "export.json"
    acknowledgement = sync_client.acknowledge(
        state_dir,
        note="reviewed-locally",
    )
    sync_client.export_state(state_dir, exported_path)
    exported = read_json(exported_path)

    assert result["removed_apps"] == 1
    assert result["local_apps"] == 1
    assert apps == [{
        "deleted": False,
        "metadata": {
            "source_name": "local-alpha.html",
            "title": "Local Alpha",
        },
        "origin": "local-overlay",
        "path": "apps/demo/alpha.html",
        "sha256": hashlib.sha256(local_file.read_bytes()).hexdigest(),
        "size": len(local_file.read_bytes()),
        "url": None,
    }]
    assert (
        output / "apps" / "demo" / "alpha.html"
    ).read_bytes() == local_file.read_bytes()
    assert exported["schema"] == "rappterzoo-local-sync-export/1"
    assert len(exported["tombstones"]) == 1
    assert len(exported["local_apps"]) == 1
    assert acknowledgement["note"] == "reviewed-locally"
    assert exported["acknowledgements"][-1]["note"] == "reviewed-locally"


def test_data_tombstone_preserves_local_overlay(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    public_path = root / "apps" / "attention" / "overlay.json"
    public_path.parent.mkdir(parents=True)
    public_path.write_bytes(builder.stable_json_bytes({
        "group_id": "overlay",
        "schema": "rappterzoo-attention-group/1",
        "visibility": "public-metadata",
    }))
    local_file = tmp_path / "local-overlay.json"
    local_file.write_bytes(b'{"local_overlay":true}\n')
    state_dir = tmp_path / "state"

    with serving(root) as server:
        build_served(root, server)
        sync_client.sync_repository(
            state_dir,
            server.index_url,
            fetch_apps=True,
        )
        sync_client.add_local_app(
            state_dir,
            local_file,
            "apps/attention/overlay.json",
            "Local Data Overlay",
        )
        public_path.unlink()
        build_served(root, server)
        sync_client.sync_repository(state_dir, server.index_url)

    removed = sync_client.list_data_objects(
        state_dir,
        include_removed=True,
    )
    overlay = next(
        item
        for item in removed
        if item["path"] == "apps/attention/overlay.json"
    )
    output = tmp_path / "data-overlay-materialized"
    sync_client.materialize(state_dir, output)
    assert overlay["deleted"] is True
    assert overlay["overlayed"] is True
    assert (
        output / "apps" / "attention" / "overlay.json"
    ).read_bytes() == local_file.read_bytes()


def test_public_data_bounds_paths_and_safe_false_privacy(tmp_path):
    nested = {}
    cursor = nested
    for _depth in range(66):
        cursor["child"] = {}
        cursor = cursor["child"]
    nested_bytes = builder.stable_json_bytes(nested)
    with pytest.raises(
        builder.SyndicationError,
        match="nesting",
    ):
        builder.parse_public_data_bytes(
            nested_bytes,
            ".json",
            "apps/attention/nested.json",
        )
    with pytest.raises(sync_client.SyncError, match="nesting"):
        sync_client.validate_public_data_bytes(
            nested_bytes,
            "application/json",
        )

    oversized = b" " * (builder.MAX_PUBLIC_DATA_BYTES + 1)
    with pytest.raises(builder.SyndicationError, match="four MiB"):
        builder.parse_public_data_bytes(
            oversized,
            ".json",
            "apps/attention/oversized.json",
        )
    with pytest.raises(sync_client.SyncError, match="four MiB"):
        sync_client.validate_public_data_bytes(
            oversized,
            "application/json",
        )

    parser_bomb = (
        ("[" * 1100) + "0" + ("]" * 1100)
    ).encode("ascii")
    with pytest.raises(
        builder.SyndicationError,
        match="invalid JSON|nesting",
    ):
        builder.parse_public_data_bytes(
            parser_bomb,
            ".json",
            "apps/attention/parser-bomb.json",
        )
    with pytest.raises(
        sync_client.SyncError,
        match="invalid JSON|nesting",
    ):
        sync_client.validate_public_data_bytes(
            parser_bomb,
            "application/json",
        )

    safe = {
        "privateMediaInPublicLedger": False,
        "pulsePersisted": False,
        "token": False,
        "visibility": "public-metadata",
    }
    builder.validate_public_data_value(safe)
    sync_client.validate_public_data_value(safe)
    for unsafe in (
        {"privateMediaInPublicLedger": True},
        {"pulsePersisted": True},
        {"pulsePersisted": 0},
    ):
        with pytest.raises(builder.SyndicationError, match="sensitive key"):
            builder.validate_public_data_value(unsafe)
        with pytest.raises(sync_client.SyncError, match="sensitive key"):
            sync_client.validate_public_data_value(unsafe)

    descriptor = {
        "content_id": "sha256:" + ("0" * 64),
        "metadata": {},
        "path": "../escape.html",
        "sha256": "0" * 64,
        "size": 1,
        "url": "https://example.test/escape.html",
        "verification": {
            "algorithm": "sha256",
            "required": True,
        },
    }
    with pytest.raises(sync_client.SyncError, match="unsafe app path"):
        sync_client.validate_descriptor(descriptor)

    local_file = tmp_path / "local.html"
    local_file.write_bytes(b"<title>local</title>\n")
    with pytest.raises(sync_client.SyncError, match="unsafe app path"):
        sync_client.add_local_app(
            tmp_path / "state",
            local_file,
            "../escape.html",
        )


def test_frame_safe_false_privacy_declarations_require_false():
    safe = make_frame(
        0,
        payload_updates={
            "privateMediaInPublicLedger": False,
            "pulsePersisted": False,
        },
    )
    builder.validate_frames([safe])
    sync_client.validate_frames([safe], None, set())

    for key, value in (
        ("privateMediaInPublicLedger", True),
        ("pulsePersisted", True),
        ("pulsePersisted", 0),
    ):
        frame = make_frame(0, payload_updates={key: value})
        with pytest.raises(builder.SyndicationError, match="forbidden key"):
            builder.validate_frames([frame])
        with pytest.raises(sync_client.SyncError, match="forbidden key"):
            sync_client.validate_frames([frame], None, set())


def test_frame_privacy_mutation_is_rejected_even_when_rehashed(tmp_path):
    root, _manifest, frames = make_repo(tmp_path, frames=1)
    state_dir = tmp_path / "state"
    with serving(root) as server:
        build_served(root, server)
        sync_client.sync_repository(state_dir, server.index_url)

        bad_frame = make_frame(1, frames[0])
        bad_frame["payload"]["private"] = "not-public"
        bad_frame["payload_hash"] = builder.frame_hash_value(
            builder.PARTICLE_SPACE,
            bad_frame["payload"],
        )
        wave = {
            key: value
            for key, value in bad_frame.items()
            if key not in {"frame_hash", "sig"}
        }
        bad_frame["frame_hash"] = builder.frame_hash_value(
            builder.WAVE_SPACE,
            wave,
        )
        index_path = root / "apps" / "syndication" / "index.json"
        index = read_json(index_path)
        previous = index["deltas"][-1]["sha256"]
        delta = {
            "changes": {
                "app_tombstones": [],
                "app_upserts": [],
                "data_tombstones": [],
                "data_upserts": [],
                "frame_appends": [bad_frame],
            },
            "challenge_state_machine": builder.CHALLENGE_STATE_MACHINE,
            "created_at": bad_frame["utc"],
            "frame_control": None,
            "frame_control_schema": builder.FRAME_CONTROL_SCHEMA,
            "profile": builder.PROFILE,
            "previous_delta": previous,
            "proof_of_fold": None,
            "rollout": builder.SOAK_ROLLOUT,
            "schema": builder.DELTA_SCHEMA,
            "segments": None,
            "sequence": 1,
            "since_seq": 0,
            "stream_id": builder.STREAM_ID,
            "transparency": builder.TRANSPARENCY_MODEL,
            "through_seq": 1,
        }
        delta["proof_of_fold"] = builder.proof_of_fold_metadata(
            delta["changes"]
        )
        delta["frame_control"] = builder.frame_control_metadata(
            delta["changes"],
            delta["proof_of_fold"],
        )
        delta["segments"] = builder.segment_metadata(delta["changes"])
        data = builder.stable_json_bytes(delta)
        digest = hashlib.sha256(data).hexdigest()
        delta_path = (
            root / "apps" / "syndication" / "deltas"
            / (digest + ".json")
        )
        delta_path.write_bytes(data)
        entry = {
            "app_tombstones": 0,
            "app_upserts": 0,
            "block": builder.block_metadata(delta, digest),
            "created_at": bad_frame["utc"],
            "frame_appends": 1,
            "path": "deltas/{}.json".format(digest),
            "previous_delta": previous,
            "profile": builder.PROFILE,
            "sequence": 1,
            "segment_hashes": {
                "apps": delta["segments"]["apps"]["sha256"],
                "data": delta["segments"]["data"]["sha256"],
                "frames": delta["segments"]["frames"]["sha256"],
            },
            "sha256": digest,
            "since_seq": 0,
            "size": len(data),
            "through_seq": 1,
            "url": server.base_url
            + "apps/syndication/deltas/{}.json".format(digest),
        }
        index["deltas"].append(entry)
        index["delta_count"] = 2
        index["head"] = {
            "path": entry["path"],
            "sequence": 1,
            "sha256": digest,
            "url": entry["url"],
        }
        index["cursor"]["head_seq"] = 1
        index["next_frame_challenge_seed"] = entry["block"][
            "next_frame_challenge_seed"
        ]
        write_json(index_path, index)

        with pytest.raises(sync_client.SyncError, match="forbidden key"):
            sync_client.sync_repository(state_dir, server.index_url)
    assert sync_client.status(state_dir)["deltas"] == 1
