#!/usr/bin/env python3
"""Compile and verify the recursive scene inside one public organism hash."""

import argparse
import copy
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import organism_ledger


ROOT = Path(__file__).resolve().parent.parent
LEDGER_PATH = ROOT / "apps" / "organism-frames.jsonl"
PROJECTION_PATH = ROOT / "apps" / "organism-frames.json"
MANIFEST_PATH = ROOT / "apps" / "manifest.json"
ATTENTION_DIR = ROOT / "apps" / "attention"
SYNDICATION_DIR = ROOT / "apps" / "syndication"
SCENE_PATH = ROOT / "apps" / "looking-glass" / "hash-scene.json"

SCENE_SCHEMA = "rappterzoo-looking-glass-scene/1"
SCENE_HASH_DOMAIN = b"rappterzoo/looking-glass-scene/1\n"
TARGET_EVENT_ID = "creature-birth:dogg.looking-glass-watchtower"
TARGET_FRAME_HASH = (
    "eb2594f6e0a425cd0013f6adff1988721efe7e0384f7dcee5cf51f2627621942"
)
APP_FILE = "looking-glass-inside-one-hash.html"
APP_PATH = "apps/3d-immersive/" + APP_FILE
APP_TITLE = "Looking Glass: Inside One Hash"
APP_URL = (
    "https://kody-w.github.io/localFirstTools-main/"
    + APP_PATH
)
DIMENSION_IDS = [
    "payload",
    "lineage",
    "attention",
    "mutation",
    "app",
    "neighborhood",
    "syndication",
]
APP_METADATA = {
    "title": APP_TITLE,
    "file": APP_FILE,
    "description": (
        "Dive through one real Watchtower frame hash as an infinite recursive "
        "scene whose seven dimensions remain traceable to public source data."
    ),
    "tags": [
        "looking-glass",
        "hash",
        "recursive-zoom",
        "rapp1",
        "organism-ledger",
        "dogg",
        "lineage",
        "syndication",
    ],
    "complexity": "advanced",
    "type": "visual",
    "featured": True,
    "created": "2026-08-15",
    "generation": 1,
}


class LookingGlassError(ValueError):
    pass


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as error:
        raise LookingGlassError(
            "cannot read {}: {}".format(path, error)
        ) from error


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(
        "{}.tmp.{}".format(path.name, os.getpid())
    )
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(
                value,
                handle,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temporary), str(path))
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _canonical_digest(value: Any) -> str:
    return hashlib.sha256(
        SCENE_HASH_DOMAIN + organism_ledger.canonical_bytes(value)
    ).hexdigest()


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _dimension_digest(value: Any) -> str:
    return hashlib.sha256(
        b"rappterzoo/looking-glass-dimension/1\n"
        + organism_ledger.canonical_bytes(value)
    ).hexdigest()


def _public_frame_summary(frame: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "frame_hash": frame["frame_hash"],
        "kind": frame["kind"],
        "payload_hash": frame["payload_hash"],
        "seq": frame["seq"],
        "utc": frame["utc"],
    }


def _manifest_app(manifest: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    category = manifest.get("categories", {}).get("3d_immersive", {})
    for app in category.get("apps", []):
        if app.get("file") == APP_FILE:
            return copy.deepcopy(app)
    return None


def _walk_for_frame(value: Any, frame_hash: str) -> bool:
    if type(value) is dict:
        if value.get("frame_hash") == frame_hash:
            return True
        return any(
            _walk_for_frame(item, frame_hash)
            for item in value.values()
        )
    if isinstance(value, list):
        return any(_walk_for_frame(item, frame_hash) for item in value)
    return False


def _containing_delta(
    syndication_dir: Path,
    frame_hash: str,
) -> Tuple[Dict[str, Any], str]:
    delta_dir = syndication_dir / "deltas"
    for path in sorted(delta_dir.glob("*.json")):
        value = _load_json(path)
        if _walk_for_frame(value, frame_hash):
            return value, path.stem
    raise LookingGlassError(
        "target frame is absent from immutable syndication deltas"
    )


def _direct_attention_objects(
    attention_dir: Path,
    frame_hash: str,
) -> List[Dict[str, Any]]:
    result = []
    for path in sorted(attention_dir.rglob("*.json")):
        value = _load_json(path)
        if _walk_for_frame(value, frame_hash):
            result.append({
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": _file_digest(path),
            })
    return result


def _direct_mutation_frames(
    frames: Sequence[Dict[str, Any]],
    frame_hash: str,
) -> List[Dict[str, Any]]:
    result = []
    for frame in frames:
        if frame.get("kind") != "zoo.mutation":
            continue
        if _walk_for_frame(frame.get("payload", {}), frame_hash):
            result.append(_public_frame_summary(frame))
    return result


def _source(
    path: str,
    digest: str,
    url: str,
) -> Dict[str, str]:
    return {
        "path": path,
        "sha256": digest,
        "url": url,
    }


def _dimension(
    identifier: str,
    title: str,
    status: str,
    source_digest: str,
    facts: Dict[str, Any],
    sources: List[Dict[str, str]],
) -> Dict[str, Any]:
    value = {
        "depth": DIMENSION_IDS.index(identifier),
        "facts": facts,
        "id": identifier,
        "sources": sources,
        "status": status,
        "title": title,
    }
    value["source_digest"] = source_digest
    value["dimension_digest"] = _dimension_digest(value)
    return value


def _scene_without_digest(scene: Dict[str, Any]) -> Dict[str, Any]:
    value = copy.deepcopy(scene)
    value["integrity"]["scene_digest"] = None
    return value


def build_scene(root: Path = ROOT) -> Dict[str, Any]:
    ledger_path = root / "apps" / "organism-frames.jsonl"
    manifest_path = root / "apps" / "manifest.json"
    attention_dir = root / "apps" / "attention"
    syndication_dir = root / "apps" / "syndication"
    frames = organism_ledger.read_frames(ledger_path)
    target = next(
        (
            frame
            for frame in frames
            if frame["payload"].get("event_id") == TARGET_EVENT_ID
        ),
        None,
    )
    if target is None or target["frame_hash"] != TARGET_FRAME_HASH:
        raise LookingGlassError("the pinned Watchtower birth frame drifted")
    target_index = frames.index(target)
    previous = frames[target_index - 1] if target_index else None
    successor = (
        frames[target_index + 1]
        if target_index + 1 < len(frames)
        else None
    )
    manifest = _load_json(manifest_path)
    manifest_app = _manifest_app(manifest)
    delta, delta_id = _containing_delta(
        syndication_dir,
        target["frame_hash"],
    )
    syndication_index = _load_json(syndication_dir / "index.json")
    attention_sources = []
    for name in (
        "policy.json",
        "prompt-contract.json",
        "frame-control.json",
    ):
        path = attention_dir / name
        attention_sources.append(
            _source(
                "apps/attention/" + name,
                _file_digest(path),
                "../attention/" + name,
            )
        )
    direct_attention = _direct_attention_objects(
        attention_dir,
        target["frame_hash"],
    )
    direct_mutations = _direct_mutation_frames(
        frames,
        target["frame_hash"],
    )
    policy = _load_json(attention_dir / "policy.json")
    frame_control = _load_json(attention_dir / "frame-control.json")

    payload_facts = {
        "capabilities": target["payload"].get("capabilities", []),
        "display_name": target["payload"]["display_name"],
        "event": target["payload"]["event"],
        "event_id": target["payload"]["event_id"],
        "kennel": target["payload"]["kennel"],
        "organism": target["payload"]["organism"],
        "organism_type": target["payload"]["organism_type"],
        "visibility": target["payload"]["visibility"],
    }
    lineage_facts = {
        "contiguous": True,
        "previous": (
            _public_frame_summary(previous)
            if previous is not None
            else None
        ),
        "successor": (
            _public_frame_summary(successor)
            if successor is not None
            else None
        ),
        "target": _public_frame_summary(target),
    }
    attention_facts = {
        "attention_budget": policy["attention_budget"],
        "candidate_budget": policy["candidate_budget"],
        "direct_object_count": len(direct_attention),
        "direct_objects": direct_attention,
        "selection_algorithm": policy["selection_algorithm"],
        "statement": (
            "No public attention group directly references this birth frame."
            if not direct_attention
            else "Public attention objects directly reference this frame."
        ),
    }
    mutation_facts = {
        "direct_frame_count": len(direct_mutations),
        "direct_frames": direct_mutations,
        "frame_control_mode": frame_control["mode"],
        "source_frame_immutable": True,
        "statement": (
            "No direct mutation frame references this birth frame."
            if not direct_mutations
            else "Direct mutation lineage is present."
        ),
    }
    app_facts = {
        "file": APP_FILE,
        "manifest_registered": manifest_app is not None,
        "metadata": manifest_app or APP_METADATA,
        "portal": "organism-observatory.html",
        "title": APP_TITLE,
    }
    neighborhood_facts = {
        "front_door": (
            "https://kody-w.github.io/localFirstTools-main/"
        ),
        "kennel": target["payload"]["kennel"],
        "name": target["payload"]["neighborhood"],
        "organism": target["payload"]["organism"],
        "stream_id": target["stream_id"],
    }
    syndication_facts = {
        "containing_delta": delta_id,
        "containing_delta_profile": delta.get("profile") or "legacy",
        "containing_delta_sequence": delta["sequence"],
        "static_atom": syndication_index["atom"]["url"],
        "static_json_feed": syndication_index["json_feed"]["url"],
    }

    dimensions = [
        _dimension(
            "payload",
            "Packet of light",
            "observed",
            target["payload_hash"],
            payload_facts,
            [
                _source(
                    "apps/organism-frames.jsonl#seq=51",
                    target["frame_hash"],
                    "../organism-frames.jsonl",
                )
            ],
        ),
        _dimension(
            "lineage",
            "Append-only ancestry",
            "verified-contiguous",
            _dimension_digest(lineage_facts),
            lineage_facts,
            [
                _source(
                    "apps/organism-frames.jsonl#seq=50:52",
                    _dimension_digest(lineage_facts),
                    "../organism-frames.jsonl",
                )
            ],
        ),
        _dimension(
            "attention",
            "Bounded attention aperture",
            (
                "observed"
                if direct_attention
                else "contract-visible-not-observed"
            ),
            _dimension_digest(attention_facts),
            attention_facts,
            attention_sources,
        ),
        _dimension(
            "mutation",
            "Mutation horizon",
            (
                "observed"
                if direct_mutations
                else "immutable-no-direct-mutation"
            ),
            _dimension_digest(mutation_facts),
            mutation_facts,
            [
                _source(
                    "apps/organism-frames.jsonl#target-mutation-lineage",
                    _dimension_digest(mutation_facts),
                    "../organism-frames.jsonl",
                ),
                attention_sources[2],
            ],
        ),
        _dimension(
            "app",
            "The scene that looks back",
            "registered" if manifest_app is not None else "candidate",
            _dimension_digest(app_facts),
            app_facts,
            [
                _source(
                    "apps/manifest.json#file=" + APP_FILE,
                    _dimension_digest(app_facts),
                    "../manifest.json",
                )
            ],
        ),
        _dimension(
            "neighborhood",
            "RappterZoo public neighborhood",
            "observed-public",
            _dimension_digest(neighborhood_facts),
            neighborhood_facts,
            [
                _source(
                    "index.html#neighborhood=rappterzoo",
                    _dimension_digest(neighborhood_facts),
                    "../../index.html",
                )
            ],
        ),
        _dimension(
            "syndication",
            "Static delta broadcast",
            "content-addressed",
            delta_id,
            syndication_facts,
            [
                _source(
                    "apps/syndication/deltas/{}.json".format(delta_id),
                    delta_id,
                    "../syndication/deltas/{}.json".format(delta_id),
                ),
            ],
        ),
    ]

    scene = {
        "dimensions": dimensions,
        "generated_from": {
            "event_id": TARGET_EVENT_ID,
            "frame_hash": target["frame_hash"],
            "payload_hash": target["payload_hash"],
            "seq": target["seq"],
            "stream_id": target["stream_id"],
            "utc": target["utc"],
        },
        "integrity": {
            "dimension_count": len(dimensions),
            "frame_valid": True,
            "rapp_acceptance": "structural-unverified",
            "scene_digest": None,
        },
        "privacy_proof": {
            "excluded_categories": [
                "local-only-plane",
                "raw-camera-binary",
                "face-identity-template",
                "biometric-value",
                "pulse-value",
            ],
            "forbidden_key_hits": [],
            "public_data_only": True,
            "zero_nonpublic_records": True,
        },
        "recursion": {
            "cycle": DIMENSION_IDS,
            "hash_bytes": list(bytes.fromhex(target["frame_hash"])),
            "levels_per_cycle": len(DIMENSION_IDS),
            "visual_depth": 64,
        },
        "schema": SCENE_SCHEMA,
        "status": "public-structural-view",
        "target_frame": copy.deepcopy(target),
    }
    scene["integrity"]["scene_digest"] = _canonical_digest(
        _scene_without_digest(scene)
    )
    return scene


def verify_scene(
    scene: Dict[str, Any],
    root: Path = ROOT,
) -> Dict[str, Any]:
    if scene.get("schema") != SCENE_SCHEMA:
        raise LookingGlassError("scene has the wrong schema")
    if scene.get("status") != "public-structural-view":
        raise LookingGlassError("scene status is invalid")
    dimensions = scene.get("dimensions")
    if (
        not isinstance(dimensions, list)
        or [item.get("id") for item in dimensions] != DIMENSION_IDS
    ):
        raise LookingGlassError("scene dimensions are incomplete or reordered")
    if scene.get("generated_from", {}).get("frame_hash") != TARGET_FRAME_HASH:
        raise LookingGlassError("scene is bound to the wrong frame")
    if scene.get("target_frame", {}).get("frame_hash") != TARGET_FRAME_HASH:
        raise LookingGlassError("embedded target frame is wrong")
    organism_ledger.verify_frames(
        organism_ledger.read_frames(root / "apps" / "organism-frames.jsonl")
    )
    frames = organism_ledger.read_frames(
        root / "apps" / "organism-frames.jsonl"
    )
    target = next(
        (
            frame
            for frame in frames
            if frame["payload"].get("event_id") == TARGET_EVENT_ID
        ),
        None,
    )
    if target is None or scene["target_frame"] != target:
        raise LookingGlassError("embedded target frame is stale or mutated")
    for dimension in dimensions:
        projected = copy.deepcopy(dimension)
        digest = projected.pop("dimension_digest", None)
        if digest != _dimension_digest(projected):
            raise LookingGlassError(
                "dimension digest mismatch: {}".format(dimension.get("id"))
            )
    expected_digest = _canonical_digest(_scene_without_digest(scene))
    if scene["integrity"]["scene_digest"] != expected_digest:
        raise LookingGlassError("scene digest mismatch")
    forbidden = organism_ledger._find_forbidden_key(scene)
    if forbidden:
        raise LookingGlassError(
            "scene contains forbidden public key: {}".format(forbidden)
        )
    if scene["privacy_proof"] != {
        "excluded_categories": [
            "local-only-plane",
            "raw-camera-binary",
            "face-identity-template",
            "biometric-value",
            "pulse-value",
        ],
        "forbidden_key_hits": [],
        "public_data_only": True,
        "zero_nonpublic_records": True,
    }:
        raise LookingGlassError("scene privacy proof drifted")
    syndication = next(
        item
        for item in dimensions
        if item["id"] == "syndication"
    )
    delta_id = syndication["facts"]["containing_delta"]
    delta_path = (
        root
        / "apps"
        / "syndication"
        / "deltas"
        / "{}.json".format(delta_id)
    )
    if (
        not delta_path.is_file()
        or _file_digest(delta_path) != delta_id
        or not _walk_for_frame(_load_json(delta_path), TARGET_FRAME_HASH)
    ):
        raise LookingGlassError("immutable syndication source is invalid")
    manifest = _load_json(root / "apps" / "manifest.json")
    app_dimension = next(
        item for item in dimensions if item["id"] == "app"
    )
    if (
        app_dimension["facts"].get("manifest_registered")
        and _manifest_app(manifest) is None
    ):
        raise LookingGlassError("registered portal app is absent")
    return {
        "dimension_count": len(dimensions),
        "frame_hash": TARGET_FRAME_HASH,
        "scene_digest": expected_digest,
        "valid": True,
    }


def verify_scene_sources(
    scene: Dict[str, Any],
    root: Path = ROOT,
) -> Dict[str, Any]:
    result = verify_scene(scene, root)
    expected = build_scene(root)
    if scene != expected:
        raise LookingGlassError(
            "immutable scene source drift detected; publish a versioned "
            "scene instead of overwriting historical evidence"
        )
    result["sources_current"] = True
    return result


def write_scene(
    root: Path = ROOT,
    scene_path: Optional[Path] = None,
) -> Dict[str, Any]:
    target = scene_path or (root / "apps" / "looking-glass" / "hash-scene.json")
    if target.is_file():
        scene = _load_json(target)
        verify_scene_sources(scene, root)
        return scene
    scene = build_scene(root)
    _atomic_json(target, scene)
    verify_scene_sources(scene, root)
    return scene


def append_portal_frame(
    root: Path = ROOT,
    utc: Optional[str] = None,
) -> Dict[str, Any]:
    scene_path = root / "apps" / "looking-glass" / "hash-scene.json"
    scene = _load_json(scene_path)
    verify_scene_sources(scene, root)
    manifest = _load_json(root / "apps" / "manifest.json")
    if _manifest_app(manifest) is None:
        raise LookingGlassError("portal app is not registered in the manifest")
    payload = {
        "app_file": APP_FILE,
        "dimensions": DIMENSION_IDS,
        "display_name": APP_TITLE,
        "event": "dimension-portal",
        "event_id": "experience-birth:looking-glass-inside-one-hash",
        "kennel": "dogg-pound",
        "neighborhood": "rappterzoo",
        "organism": "dogg.looking-glass-watchtower",
        "organism_type": "dogg",
        "public_data_only": True,
        "scene_digest": scene["integrity"]["scene_digest"],
        "schema": "rappterzoo-organism-frame/1",
        "source_frame_hash": TARGET_FRAME_HASH,
        "visibility": "public-metadata",
    }
    return organism_ledger.append_frame(
        "zoo.observation",
        payload,
        utc=utc,
        ledger_path=root / "apps" / "organism-frames.jsonl",
        projection_path=root / "apps" / "organism-frames.json",
    )


def main() -> int:
    parser = argparse.ArgumentParser(prog="looking-glass-hash")
    parser.add_argument(
        "command",
        choices=("build", "verify", "release"),
    )
    parser.add_argument("--utc")
    arguments = parser.parse_args()
    try:
        if arguments.command == "build":
            scene = write_scene()
            result = {
                "scene_digest": scene["integrity"]["scene_digest"],
                "written": str(SCENE_PATH),
            }
        elif arguments.command == "verify":
            result = verify_scene_sources(_load_json(SCENE_PATH))
        else:
            scene = write_scene()
            frame = append_portal_frame(utc=arguments.utc)
            result = {
                "frame_hash": frame["frame_hash"],
                "frame_seq": frame["seq"],
                "scene_digest": scene["integrity"]["scene_digest"],
            }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (
        LookingGlassError,
        organism_ledger.LedgerError,
        OSError,
        ValueError,
    ) as error:
        print(
            json.dumps({"ok": False, "error": str(error)}),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
