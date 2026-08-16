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


def delta_paths(root):
    return sorted((root / "apps" / "syndication" / "deltas").glob("*.json"))


def delta_path_for_sequence(root, sequence):
    index = read_json(root / "apps" / "syndication" / "index.json")
    digest = index["deltas"][sequence]["sha256"]
    return root / "apps" / "syndication" / "deltas" / (digest + ".json")


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


def test_agent_amusement_park_round_trips_as_public_data(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    source = ROOT / "apps" / "agent-park"
    target = root / "apps" / "agent-park"
    shutil.copytree(source, target)
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
        "agent-contract",
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


def test_agent_park_ledger_allows_only_valid_prefix_growth(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    source = ROOT / "apps" / "agent-park"
    target = root / "apps" / "agent-park"
    shutil.copytree(source, target)
    builder.build(root)
    events_path = target / "events.jsonl"
    events = [
        json.loads(line)
        for line in events_path.read_text().splitlines()
        if line
    ]
    payload = {
        "night": 8,
        "result": "future-customer-approved-append",
    }
    event = {
        "kind": "park.night-open",
        "park_id": "park.rappterzoo-agent-amusement-park",
        "payload": payload,
        "payload_hash": builder.frame_hash_value(
            builder.AGENT_PARK_PAYLOAD_SPACE,
            payload,
        ),
        "prev": events[-1]["event_hash"],
        "schema": builder.AGENT_PARK_EVENT_SCHEMA,
        "seq": len(events),
        "utc": "2026-08-23T00:00:00.000Z",
        "visibility": "public-metadata",
    }
    event["event_hash"] = builder.frame_hash_value(
        builder.AGENT_PARK_EVENT_SPACE,
        event,
    )
    events.append(event)
    events_path.write_bytes(
        b"".join(
            builder.canonical_frame_bytes(item) + b"\n"
            for item in events
        )
    )

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


def test_sync_rejects_delta_byte_tamper(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    state_dir = tmp_path / "state"
    with serving(root) as server:
        build_served(root, server)
        delta_paths(root)[0].write_bytes(
            delta_paths(root)[0].read_bytes() + b" "
        )
        with pytest.raises(sync_client.SyncError, match="content hash"):
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


def test_multiple_delta_failure_rolls_back_entire_apply(tmp_path):
    root, _manifest, _frames = make_repo(tmp_path)
    state_dir = tmp_path / "state"
    with serving(root) as server:
        build_served(root, server)
        mutate_app(root)
        build_served(root, server)
        second_delta = delta_path_for_sequence(root, 1)
        second_delta.write_bytes(second_delta.read_bytes() + b" ")
        with pytest.raises(sync_client.SyncError, match="content hash"):
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
        write_json(index_path, index)

        with pytest.raises(sync_client.SyncError, match="forbidden key"):
            sync_client.sync_repository(state_dir, server.index_url)
    assert sync_client.status(state_dir)["deltas"] == 1
