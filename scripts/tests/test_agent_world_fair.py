"""Tests for the deterministic public-metadata Agent World's Fair."""

import base64
import copy
import hashlib
import json
import shutil
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import agent_world_fair as fair
import organism_ledger


@pytest.fixture
def scratch_dir():
    path = ROOT / ".agent-world-fair-test-work"
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


EXPECTED_EVENT_HEAD = (
    "fa5e7861ec0bf7cfdb20caedd9e1c1287bbfdb6ffc8ee64ed181fae4305c643d"
)
EXPECTED_EVENT_LEDGER_SHA256 = (
    "6400594b6c83ff905b800eb0637ce48a71363545ec0014d10158ce44896661fe"
)
EXPECTED_BUNDLE_DIGEST = (
    "04aa93502f81e81a9f345ab0d4bbe4621703688893f6dc5a5faa8e3b171640d3"
)
EXPECTED_CONTRACT_DIGEST = (
    "9d8901693e9ffe60b1062575c106d896342ceb9bdbdbe03a1e9d7f29a82fcaf4"
)
EXPECTED_DISTRICT_DIGEST = (
    "a7268da3c101c7e0cdf15df89037c37cb61ca1dee34f10809bb5b346c4264ecd"
)
EXPECTED_RELEASE_CANDIDATE_DIGEST = (
    "ad5a75e12715d476f4aa197c83190c814952184756e67ef08ffed570dcd62ae3"
)
EXPECTED_WINNERS = [
    "submission.memory-mosaic",
    "submission.resonance-commons",
    "submission.aurora-atlas",
    "submission.many-worlds-theatre",
]
TEST_RSA_N = int(
    "237474516483627586724793735800244244287914206090072680069704403226"
    "584739719053663929653747930590706156612067670684331456714511760593"
    "669544245332514418859230419617493946264017432013753157103946500086"
    "844935651237303486379388365752258894307874357272429213697396895208"
    "886044516975352704997410745481113010654830884394986333956317705781"
    "502603703798662224240189309945923720889012856662458768795036471023"
    "935830792542365766672761174965747457300771152391221290176266721003"
    "820590794110864338310714017305673190509295818451691918549122476411"
    "110431501211161531970245111617043456246454363967454606368308769708"
    "07003246750665735367451"
)
TEST_RSA_D = int(
    "522040276329344132618841776656563289051372502119364191489422972868"
    "060232408014730035632016484736912522439241791896053114559099582659"
    "108156299877250291057712842429350639154324907002478254176504451950"
    "985700890699273895397691103558721621418976435482839873924408665223"
    "373246159583732307078092773570104695745021668205276839717049104403"
    "347129642515194026769016785022759957102565136319172487601466672353"
    "043307243997430749665011192595823649804553690490808434277258799365"
    "182863963819515084508521344046262863253723612127324387700657594693"
    "071054243632756427452846617935339593927020217041036726223448502746"
    "4973099583248574285905"
)
TEST_RSA_E = 65537
TEST_RSA_KID = "agent-fair-test-key"


def _rehash_events(events):
    previous = None
    for index, event in enumerate(events):
        event["seq"] = index
        event["prev"] = previous
        event["payload_hash"] = fair._canonical_digest(
            fair.PAYLOAD_HASH_DOMAIN,
            event["payload"],
        )
        projected = {
            key: copy.deepcopy(value)
            for key, value in event.items()
            if key != "event_hash"
        }
        event["event_hash"] = fair._canonical_digest(
            fair.EVENT_HASH_DOMAIN,
            projected,
        )
        previous = event["event_hash"]


def _rebind_bundle(state, events, contract, district):
    event_bytes = fair._event_bytes(events)
    event_sha256 = hashlib.sha256(event_bytes).hexdigest()
    state["event_ledger"] = {
        "event_count": len(events),
        "exact_keys": sorted(fair.EVENT_KEYS),
        "head": events[-1]["event_hash"],
        "path": "events.jsonl",
        "sha256": event_sha256,
    }
    contract_digest = fair._canonical_digest(
        fair.CONTRACT_HASH_DOMAIN,
        fair._contract_without_digest(contract),
    )
    contract["integrity"]["contract_digest"] = contract_digest
    district["integrity"]["contract_digest"] = contract_digest
    district_digest = fair._canonical_digest(
        fair.DISTRICT_HASH_DOMAIN,
        fair._district_without_digest(district),
    )
    district["integrity"]["district_digest"] = district_digest
    state["agent_contract"]["contract_digest"] = contract_digest
    state["district"]["district_digest"] = district_digest
    state["integrity"]["contract_digest"] = contract_digest
    state["integrity"]["district_digest"] = district_digest
    state_digest = fair._canonical_digest(
        fair.STATE_HASH_DOMAIN,
        fair._state_without_digest(state),
    )
    state["integrity"]["state_digest"] = state_digest
    bundle_digest = fair._bundle_digest(
        len(events),
        events[-1]["event_hash"],
        event_sha256,
        state_digest,
        contract_digest,
        district_digest,
    )
    state["integrity"]["bundle_digest"] = bundle_digest
    contract["integrity"]["bundle_digest"] = bundle_digest
    district["integrity"]["bundle_digest"] = bundle_digest


def _copy_release_tree(target):
    for relative in (
        "apps/agent-park/park-state.json",
        "apps/agent-park/events.jsonl",
        "apps/organism-frames.jsonl",
        "apps/organism-frames.json",
        "apps/manifest.json",
    ):
        source = ROOT / relative
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    ledger_path = target / "apps" / "organism-frames.jsonl"
    frames = organism_ledger.read_frames(ledger_path)
    release_index = next(
        (
            index
            for index, frame in enumerate(frames)
            if str(
                frame.get("payload", {}).get("event_id", "")
            ).startswith("agent-worlds-fair-release:")
        ),
        None,
    )
    if release_index is not None:
        frames = frames[:release_index]
        ledger_path.write_bytes(
            b"".join(
                organism_ledger.canonical_bytes(frame) + b"\n"
                for frame in frames
            )
        )
        organism_ledger.write_projection(
            frames,
            path=target / "apps" / "organism-frames.json",
        )


def test_real_anchor_and_exact_event_flow():
    state, events, contract, district = fair.build_bundle(ROOT)
    assert state["anchor"]["park"] == {
        "bundle_digest": fair.PARK_BUNDLE_DIGEST,
        "event_count": 94,
        "event_head": fair.PARK_EVENT_HEAD,
        "event_ledger_sha256": fair.PARK_EVENT_LEDGER_SHA256,
        "source": "apps/agent-park",
    }
    assert state["anchor"]["organism_release_frame"] == {
        "frame_hash": fair.ORGANISM_FRAME_HASH,
        "seq": 56,
        "source": "apps/organism-frames.jsonl",
    }
    assert len(events) == fair.EVENT_COUNT == 23
    kinds = [event["kind"] for event in events]
    assert kinds == (
        ["fair.genesis", "fair.contract-lock"]
        + ["fair.submission"] * 12
        + ["fair.screening"]
        + ["fair.voting-round"] * 4
        + [
            "fair.evaluation",
            "fair.winner-selection",
            "fair.district-assembly",
            "fair.release-ready",
        ]
    )
    assert district["district_id"] == fair.DISTRICT_ID
    assert contract["fair_id"] == fair.FAIR_ID


def test_exact_submission_count_identity_diversity_and_one_attraction():
    _state, events, _contract, _district = fair.build_bundle(ROOT)
    submissions = [
        event["payload"]["submission"]
        for event in events
        if event["kind"] == "fair.submission"
    ]
    assert len(submissions) == 12
    assert len(
        {submission["agent"]["identity_id"] for submission in submissions}
    ) == 12
    assert len(
        {
            submission["attractions"][0]["category"]
            for submission in submissions
        }
    ) >= 6
    assert all(
        len(submission["attractions"]) == 1
        for submission in submissions
    )


def test_contract_bounds_mcp_mapping_and_customer_boundary():
    _state, events, contract, _district = fair.build_bundle(ROOT)
    assert contract["attraction_contract"]["resource_maximums"] == {
        "attention": 20,
        "compute": 32,
        "energy": 24,
    }
    for event in events:
        if event["kind"] != "fair.submission":
            continue
        request = event["payload"]["submission"]["attractions"][0][
            "resource_request"
        ]
        assert all(
            request[name] <= maximum
            for name, maximum in fair.ATTRACTION_LIMITS.items()
        )
    assert set(contract["mcp_mappings"]) == {
        "agent_fair_submit_attraction",
        "agent_fair_cast_vote",
        "agent_fair_export_branch",
    }
    assert contract["local_proposals"]["action_limit"] == 50
    assert contract["local_proposals"]["canonical_mutation"] is False
    assert contract["data_boundary"]["external_network"] is False
    assert contract["economy"]["real_money"] is False
    assert contract["control_boundary"]["canonical_write"] == "forbidden"
    assert contract["control_boundary"]["vendor_shutdown"] is False
    assert contract["synthetic_only"] is True
    assert contract["assurance"] == {
        "claim": "deterministic-structural-validation-only",
        "consensus": False,
        "signed": False,
    }


def test_deterministic_votes_and_integer_basis_point_scoring():
    state, events, _contract, _district = fair.build_bundle(ROOT)
    voting_events = [
        event
        for event in events
        if event["kind"] == "fair.voting-round"
    ]
    assert len(voting_events) == 4
    assert [event["payload"]["round"] for event in voting_events] == [
        1,
        2,
        3,
        4,
    ]
    assert all(
        event["payload"]["issued_credits"]
        == event["payload"]["spent_credits"]
        == 420
        for event in voting_events
    )
    assert fair.SCORE_WEIGHTS_BPS == {
        "admissions": 4500,
        "diversity": 500,
        "novelty": 1000,
        "resource_efficiency": 1500,
        "satisfaction": 2500,
    }
    assert sum(fair.SCORE_WEIGHTS_BPS.values()) == 10000
    for ranking in state["rankings"]:
        assert all(
            type(value) is int
            for value in ranking["dimensions_bps"].values()
        )
        expected = sum(
            ranking["dimensions_bps"][name] * weight
            for name, weight in fair.SCORE_WEIGHTS_BPS.items()
        ) // 10000
        assert ranking["score_bps"] == expected
    rebuilt = fair.build_bundle(ROOT)
    assert rebuilt[0]["voting"] == state["voting"]
    assert rebuilt[0]["rankings"] == state["rankings"]


def test_constrained_selection_skips_higher_ranked_proposals():
    state, _events, _contract, district = fair.build_bundle(ROOT)
    assert state["winners"] == EXPECTED_WINNERS
    decisions = state["winner_selection"]["decisions"]
    assert decisions[3] == {
        "rank": 4,
        "reasons": [
            "capacity-attention-62-over-60",
            "capacity-compute-98-over-96",
        ],
        "selected": False,
        "submission_id": "submission.protocol-forge",
    }
    assert decisions[4] == {
        "rank": 5,
        "reasons": ["category-diversity"],
        "selected": False,
        "submission_id": "submission.epoch-garden",
    }
    assert decisions[5]["selected"] is True
    assert district["resource_totals"] == {
        "attention": 59,
        "compute": 92,
        "energy": 67,
    }
    assert len(
        {pavilion["category"] for pavilion in district["pavilions"]}
    ) == 4


def test_district_map_lineage_and_assembly_order():
    _state, events, _contract, district = fair.build_bundle(ROOT)
    assert [pavilion["coordinates"] for pavilion in district["pavilions"]] == [
        {"x": 120, "y": 120},
        {"x": 360, "y": 120},
        {"x": 120, "y": 360},
        {"x": 360, "y": 360},
    ]
    vote_hashes = [
        event["event_hash"]
        for event in events
        if event["kind"] == "fair.voting-round"
    ]
    for pavilion in district["pavilions"]:
        assert pavilion["lineage"]["vote_event_hashes"] == vote_hashes
        assert len(pavilion["lineage"]["submission_event_hash"]) == 64
        assert len(pavilion["lineage"]["evaluation_event_hash"]) == 64
        assert len(
            pavilion["lineage"]["winner_selection_event_hash"]
        ) == 64
    kinds = [event["kind"] for event in events]
    assert kinds.index("fair.district-assembly") > kinds.index(
        "fair.winner-selection"
    )
    assert kinds[-1] == "fair.release-ready"
    assert district["assembly"][
        "customer_approval_required_for_organism_release"
    ] is True


def test_synthetic_accounting_is_balanced_and_nonmonetary():
    state, _events, _contract, _district = fair.build_bundle(ROOT)
    economy = state["economy"]
    assert economy["real_money"] is False
    assert economy["balanced"] is True
    assert economy["total_issued"] == economy["total_spent"] == 1680
    assert economy["total_debits"] == economy["total_credits"] == 3360
    cohort_accounts = [
        value
        for account, value in economy["accounts"].items()
        if account.startswith("account.cohort.")
    ]
    assert cohort_accounts
    assert all(
        account["credits"] == account["debits"]
        for account in cohort_accounts
    )


def test_event_chain_exact_keys_hashes_and_strict_utc():
    _state, events, _contract, _district = fair.build_bundle(ROOT)
    result = fair.verify_events(events)
    assert result == {
        "event_count": 23,
        "head": EXPECTED_EVENT_HEAD,
        "valid": True,
    }
    assert all(set(event) == fair.EVENT_KEYS for event in events)
    assert events[0]["prev"] is None
    assert all(
        events[index]["prev"] == events[index - 1]["event_hash"]
        for index in range(1, len(events))
    )
    parsed = [
        datetime.strptime(
            event["utc"],
            "%Y-%m-%dT%H:%M:%S.%fZ",
        ).replace(tzinfo=timezone.utc)
        for event in events
    ]
    assert all(
        parsed[index] > parsed[index - 1]
        for index in range(1, len(parsed))
    )
    assert all("sig" not in event and "signature" not in event for event in events)


def test_bundle_contract_district_and_file_digests_are_exact():
    state, events, contract, district = fair.build_bundle(ROOT)
    assert state["integrity"]["bundle_digest"] == EXPECTED_BUNDLE_DIGEST
    assert contract["integrity"]["contract_digest"] == (
        EXPECTED_CONTRACT_DIGEST
    )
    assert district["integrity"]["district_digest"] == (
        EXPECTED_DISTRICT_DIGEST
    )
    assert events[-1]["event_hash"] == EXPECTED_EVENT_HEAD
    assert hashlib.sha256(fair._event_bytes(events)).hexdigest() == (
        EXPECTED_EVENT_LEDGER_SHA256
    )
    assert contract["hashing"]["preimages"]["event"] == (
        "event domain bytes || canonical_bytes(event with event_hash omitted)"
    )
    assert contract["hashing"]["preimages"]["event_payload"] == (
        "event payload domain bytes || canonical_bytes(payload)"
    )


def test_bundle_files_are_byte_deterministic(scratch_dir):
    first = scratch_dir / "first"
    second = scratch_dir / "second"
    fair.write_bundle(ROOT, first)
    fair.write_bundle(ROOT, second)
    for name in (
        "events.jsonl",
        "fair-state.json",
        "agent-contract.json",
        "district.json",
    ):
        assert (first / name).read_bytes() == (second / name).read_bytes()
    assert hashlib.sha256(
        (first / "events.jsonl").read_bytes()
    ).hexdigest() == EXPECTED_EVENT_LEDGER_SHA256


def test_verifier_rejects_event_mutation_and_resealed_vote_mutation():
    state, events, contract, district = fair.build_bundle(ROOT)
    mutated = copy.deepcopy(events)
    mutated[2]["payload"]["submission"]["attractions"][0]["novelty"] = 1
    with pytest.raises(fair.FairError, match="payload hash"):
        fair.verify_events(mutated)

    resealed = copy.deepcopy(events)
    vote = next(
        event
        for event in resealed
        if event["kind"] == "fair.voting-round"
    )
    vote["payload"]["cohort_votes"][0]["allocations"][0]["admissions"] += 1
    _rehash_events(resealed)
    rebound_state = copy.deepcopy(state)
    rebound_contract = copy.deepcopy(contract)
    rebound_district = copy.deepcopy(district)
    _rebind_bundle(
        rebound_state,
        resealed,
        rebound_contract,
        rebound_district,
    )
    with pytest.raises(fair.FairError, match="deterministic voting"):
        fair.verify_bundle(
            rebound_state,
            resealed,
            rebound_contract,
            rebound_district,
            ROOT,
        )


def test_focused_overallocation_and_unbalanced_mutations_fail():
    state, events, contract, district = fair.build_bundle(ROOT)
    overallocated = copy.deepcopy(state)
    overallocated["winner_selection"]["resource_totals"]["compute"] = 97
    overallocated["district"]["resource_totals"]["compute"] = 97
    rebound_contract = copy.deepcopy(contract)
    rebound_district = copy.deepcopy(district)
    rebound_events = copy.deepcopy(events)
    _rebind_bundle(
        overallocated,
        rebound_events,
        rebound_contract,
        rebound_district,
    )
    with pytest.raises(fair.FairError, match="winner order or constraints"):
        fair.verify_bundle(
            overallocated,
            rebound_events,
            rebound_contract,
            rebound_district,
            ROOT,
        )

    unbalanced = copy.deepcopy(state)
    unbalanced["economy"]["total_credits"] -= 1
    rebound_contract = copy.deepcopy(contract)
    rebound_district = copy.deepcopy(district)
    rebound_events = copy.deepcopy(events)
    _rebind_bundle(
        unbalanced,
        rebound_events,
        rebound_contract,
        rebound_district,
    )
    with pytest.raises(fair.FairError, match="synthetic accounting"):
        fair.verify_bundle(
            unbalanced,
            rebound_events,
            rebound_contract,
            rebound_district,
            ROOT,
        )


def test_focused_changed_winner_order_fails_after_rehashing():
    state, events, contract, district = fair.build_bundle(ROOT)
    mutated_state = copy.deepcopy(state)
    mutated_events = copy.deepcopy(events)
    mutated_contract = copy.deepcopy(contract)
    mutated_district = copy.deepcopy(district)
    mutated_state["winners"][0], mutated_state["winners"][1] = (
        mutated_state["winners"][1],
        mutated_state["winners"][0],
    )
    mutated_state["winner_selection"]["winner_submission_ids"] = copy.deepcopy(
        mutated_state["winners"]
    )
    selection_event = next(
        event
        for event in mutated_events
        if event["kind"] == "fair.winner-selection"
    )
    selection_event["payload"]["winner_submission_ids"] = copy.deepcopy(
        mutated_state["winners"]
    )
    _rehash_events(mutated_events)
    _rebind_bundle(
        mutated_state,
        mutated_events,
        mutated_contract,
        mutated_district,
    )
    with pytest.raises(fair.FairError, match="winner order"):
        fair.verify_bundle(
            mutated_state,
            mutated_events,
            mutated_contract,
            mutated_district,
            ROOT,
        )


def test_public_bundle_privacy_and_forbidden_key_mutation():
    state, events, contract, district = fair.build_bundle(ROOT)
    assert organism_ledger._find_forbidden_key(state) is None
    assert organism_ledger._find_forbidden_key(contract) is None
    assert organism_ledger._find_forbidden_key(district) is None
    assert all(
        organism_ledger._find_forbidden_key(event) is None
        for event in events
    )

    mutated_state = copy.deepcopy(state)
    mutated_state["customer_controls"]["biometric_template"] = "forbidden"
    mutated_contract = copy.deepcopy(contract)
    mutated_district = copy.deepcopy(district)
    mutated_events = copy.deepcopy(events)
    _rebind_bundle(
        mutated_state,
        mutated_events,
        mutated_contract,
        mutated_district,
    )
    with pytest.raises(fair.FairError, match="forbidden public key"):
        fair.verify_bundle(
            mutated_state,
            mutated_events,
            mutated_contract,
            mutated_district,
            ROOT,
        )


def test_source_drift_fails_closed(scratch_dir):
    root = scratch_dir / "source-drift-repo"
    _copy_release_tree(root)
    park_state_path = root / "apps" / "agent-park" / "park-state.json"
    park_state = json.loads(park_state_path.read_text())
    park_state["integrity"]["bundle_digest"] = "0" * 64
    park_state_path.write_text(
        json.dumps(park_state, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(fair.FairError, match="source drift"):
        fair.build_bundle(root)


def test_checked_in_bundle_is_current_and_verifiable():
    state = fair._load_json(fair.STATE_PATH)
    events = fair._load_events(fair.EVENTS_PATH)
    contract = fair._load_json(fair.CONTRACT_PATH)
    district = fair._load_json(fair.DISTRICT_PATH)
    result = fair.verify_bundle(
        state,
        events,
        contract,
        district,
        ROOT,
    )
    assert result == {
        "balanced_credits": 1680,
        "bundle_digest": EXPECTED_BUNDLE_DIGEST,
        "contract_digest": EXPECTED_CONTRACT_DIGEST,
        "district_digest": EXPECTED_DISTRICT_DIGEST,
        "event_count": 23,
        "event_head": EXPECTED_EVENT_HEAD,
        "valid": True,
        "winners": EXPECTED_WINNERS,
    }


def _release_utc(root):
    frames = organism_ledger.read_frames(
        root / "apps" / "organism-frames.jsonl"
    )
    return (
        datetime.strptime(
            frames[-1]["utc"],
            "%Y-%m-%dT%H:%M:%S.%fZ",
        ).replace(tzinfo=timezone.utc)
        + timedelta(minutes=1)
    ).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _base64url(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_integer(value):
    size = (value.bit_length() + 7) // 8
    return _base64url(value.to_bytes(size, "big"))


def _valid_oidc_claims(now=None, **updates):
    current = int(time.time()) if now is None else int(now)
    claims = {
        "actor": "customer-operator",
        "aud": fair.OIDC_AUDIENCE,
        "environment": fair.OIDC_ENVIRONMENT,
        "event_name": fair.OIDC_EVENT_NAME,
        "exp": current + 300,
        "iss": fair.OIDC_ISSUER,
        "nbf": current - 5,
        "ref": fair.OIDC_REF,
        "repository": fair.OIDC_REPOSITORY,
        "run_id": "123456789",
        "workflow_ref": fair.OIDC_WORKFLOW_REF,
    }
    claims.update(updates)
    return claims


def _signed_jwt(claims=None, header=None):
    protected = {
        "alg": "RS256",
        "kid": TEST_RSA_KID,
        "typ": "JWT",
    }
    if header:
        protected.update(header)
    payload = _valid_oidc_claims() if claims is None else claims
    first = _base64url(
        json.dumps(
            protected,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )
    second = _base64url(
        json.dumps(
            payload,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )
    signing_input = "{}.{}".format(first, second).encode("ascii")
    digest_info = (
        fair.SHA256_DIGEST_INFO_PREFIX
        + hashlib.sha256(signing_input).digest()
    )
    size = (TEST_RSA_N.bit_length() + 7) // 8
    encoded = (
        b"\x00\x01"
        + b"\xff" * (size - len(digest_info) - 3)
        + b"\x00"
        + digest_info
    )
    signature = pow(
        int.from_bytes(encoded, "big"),
        TEST_RSA_D,
        TEST_RSA_N,
    ).to_bytes(size, "big")
    return "{}.{}.{}".format(first, second, _base64url(signature))


def _corrupt_signature(token):
    first, second, signature = token.split(".")
    replacement = "A" if signature[0] != "A" else "B"
    return "{}.{}.{}{}".format(
        first,
        second,
        replacement,
        signature[1:],
    )


def _test_jwks(kid=TEST_RSA_KID):
    return {
        "keys": [
            {
                "alg": "RS256",
                "e": _base64url_integer(TEST_RSA_E),
                "kid": kid,
                "kty": "RSA",
                "n": _base64url_integer(TEST_RSA_N),
                "use": "sig",
            }
        ]
    }


class _OidcResponse:
    def __init__(self, value):
        self.status = 200
        self.value = json.dumps(value).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, _kind, _value, _traceback):
        return False

    def read(self, limit=-1):
        return self.value if limit < 0 else self.value[:limit]


def _mock_oidc(monkeypatch, token, jwks=None):
    request_url = (
        "https://pipelines.actions.githubusercontent.com/oidc"
        "?api-version=2.0"
    )
    request_secret = "opaque-request-secret"
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_URL", request_url)
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", request_secret)
    calls = []

    def open_request(request, timeout):
        calls.append((request, timeout))
        if request.full_url.startswith(
            "https://pipelines.actions.githubusercontent.com/oidc?"
        ):
            assert request.get_header("Authorization") == (
                "Bearer " + request_secret
            )
            assert (
                "audience=rappterzoo-agent-fair-release"
                in request.full_url
            )
            return _OidcResponse({"value": token})
        assert request.full_url == fair.OIDC_JWKS_URL
        assert request.get_header("Authorization") is None
        return _OidcResponse(jwks or _test_jwks())

    monkeypatch.setattr(fair.urllib.request, "urlopen", open_request)
    return calls


def _prepared_release_root(scratch_dir, name="release-repo"):
    root = scratch_dir / name
    _copy_release_tree(root)
    fair.write_bundle(root)
    fair.prepare_release_candidate(root)
    return root


def test_release_candidate_is_deterministic_and_exactly_bound(scratch_dir):
    root = _prepared_release_root(scratch_dir)
    candidate_path = (
        root / "apps" / "agent-fair" / "release-candidate.json"
    )
    first = candidate_path.read_bytes()
    candidate = json.loads(first)
    second_candidate = fair.prepare_release_candidate(root)
    assert candidate_path.read_bytes() == first
    assert second_candidate == candidate
    assert candidate["candidate_digest"] == EXPECTED_RELEASE_CANDIDATE_DIGEST
    assert set(candidate) == {
        "app",
        "approval_required",
        "bundle_digest",
        "candidate_digest",
        "candidate_digest_domain",
        "candidate_digest_preimage",
        "district_digest",
        "district_id",
        "event_count",
        "event_head",
        "expected_frame_payload",
        "fair_id",
        "schema",
        "verifier",
    }
    assert {
        key: candidate[key]
        for key in (
            "app",
            "approval_required",
            "bundle_digest",
            "candidate_digest_domain",
            "district_digest",
            "district_id",
            "event_count",
            "event_head",
            "fair_id",
        )
    } == {
        "app": "apps/3d-immersive/agent-worlds-fair.html",
        "approval_required": True,
        "bundle_digest": EXPECTED_BUNDLE_DIGEST,
        "candidate_digest_domain": (
            "rappterzoo/agent-worlds-fair-release-candidate/1\n"
        ),
        "district_digest": EXPECTED_DISTRICT_DIGEST,
        "district_id": fair.DISTRICT_ID,
        "event_count": 23,
        "event_head": EXPECTED_EVENT_HEAD,
        "fair_id": fair.FAIR_ID,
    }
    assert "canonical_write" not in json.dumps(candidate, sort_keys=True)
    assert "direct_canonical_write" not in json.dumps(
        candidate,
        sort_keys=True,
    )
    assert candidate["verifier"] == {
        "command": "python3 scripts/agent_world_fair.py verify",
        "version": fair.RELEASE_VERIFIER_VERSION,
    }
    expected_payload = candidate["expected_frame_payload"]
    assert expected_payload["release_candidate_digest"] == (
        "$candidate_digest"
    )
    evidence_requirement = expected_payload["approval_evidence"]
    assert set(evidence_requirement["exact_keys"]) == (
        fair.APPROVAL_EVIDENCE_KEYS
    )
    assert evidence_requirement["fixed_claims"] == {
        "aud": fair.OIDC_AUDIENCE,
        "environment": fair.OIDC_ENVIRONMENT,
        "event_name": fair.OIDC_EVENT_NAME,
        "iss": fair.OIDC_ISSUER,
        "ref": fair.OIDC_REF,
        "repository": fair.OIDC_REPOSITORY,
        "workflow_ref": fair.OIDC_WORKFLOW_REF,
    }
    submitted_digest = candidate.pop("candidate_digest")
    assert submitted_digest == fair._canonical_digest(
        fair.RELEASE_CANDIDATE_HASH_DOMAIN,
        candidate,
    )


def test_release_workflow_uses_oidc_branch_and_pull_request_only():
    source = Path(fair.__file__).read_text(encoding="utf-8")
    text = (
        ROOT / ".github" / "workflows" / "agent-fair-release.yml"
    ).read_text(encoding="utf-8")
    assert "--customer-approved" not in source
    assert "AGENT_FAIR_CUSTOMER_APPROVED" not in source
    assert "GITHUB_ACTIONS" not in source
    assert "workflow_dispatch:" in text
    assert "bundle_digest:" in text
    assert "district_digest:" in text
    assert "customer_approved:" in text
    assert "environment: agent-fair-production" in text
    assert "contents: write" in text
    assert "id-token: write" in text
    assert "pull-requests: write" in text
    assert "repository_lock.py acquire" in text
    assert "repository_lock.py release" in text
    assert "agent_world_fair.py apply-release" in text
    assert "--customer-approved" not in text
    assert "--phase released" in text
    assert "release/agent-fair-${{ github.run_id }}" in text
    assert "gh pr create" in text
    assert "gh pr edit" in text
    assert "git push origin HEAD:main" not in text
    assert "git push origin main" not in text


def test_release_preparation_never_mutates_organism_history(scratch_dir):
    root = scratch_dir / "prepare-only"
    _copy_release_tree(root)
    fair.write_bundle(root)
    ledger_path = root / "apps" / "organism-frames.jsonl"
    projection_path = root / "apps" / "organism-frames.json"
    before = (ledger_path.read_bytes(), projection_path.read_bytes())
    fair.prepare_release_candidate(root)
    after = (ledger_path.read_bytes(), projection_path.read_bytes())
    assert after == before


def test_local_apply_release_is_rejected_without_mutation(
    scratch_dir,
    monkeypatch,
):
    root = _prepared_release_root(scratch_dir)
    ledger_path = root / "apps" / "organism-frames.jsonl"
    before = ledger_path.read_bytes()
    monkeypatch.delenv("ACTIONS_ID_TOKEN_REQUEST_URL", raising=False)
    monkeypatch.delenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", raising=False)
    with pytest.raises(fair.FairError, match="OIDC request credentials"):
        fair.apply_release(
            EXPECTED_BUNDLE_DIGEST,
            EXPECTED_DISTRICT_DIGEST,
            root=root,
        )
    assert ledger_path.read_bytes() == before


def test_apply_release_rejects_local_oidc_endpoint(
    scratch_dir,
    monkeypatch,
):
    root = _prepared_release_root(scratch_dir)
    monkeypatch.setenv(
        "ACTIONS_ID_TOKEN_REQUEST_URL",
        "http://127.0.0.1/forged-token",
    )
    monkeypatch.setenv(
        "ACTIONS_ID_TOKEN_REQUEST_TOKEN",
        "forged-request-token",
    )
    with pytest.raises(fair.FairError, match="not trusted"):
        fair.apply_release(
            EXPECTED_BUNDLE_DIGEST,
            EXPECTED_DISTRICT_DIGEST,
            root=root,
        )


def test_public_oidc_verifier_is_deterministic_and_network_free():
    now = 2_000_000_000
    claims = _valid_oidc_claims(now=now)
    token = _signed_jwt(claims)
    first = fair.verify_github_oidc_token(
        token,
        _test_jwks(),
        now,
    )
    second = fair.verify_github_oidc_token(
        token,
        _test_jwks(),
        now,
    )
    assert first == second == {
        **claims,
        "attestation_sha256": hashlib.sha256(
            token.encode("ascii")
        ).hexdigest(),
    }


@pytest.mark.parametrize(
    ("token", "jwks", "message"),
    [
        ("forged.jwt", _test_jwks(), "compact JWT"),
        (
            _signed_jwt(header={"alg": "HS256"}),
            _test_jwks(),
            "header",
        ),
        (
            _signed_jwt(header={"typ": "JOSE"}),
            _test_jwks(),
            "header",
        ),
        (
            _signed_jwt(header={"kid": "unknown"}),
            _test_jwks(),
            "kid",
        ),
        (
            _corrupt_signature(_signed_jwt()),
            _test_jwks(),
            "signature",
        ),
    ],
)
def test_oidc_rejects_forged_jwt_header_kid_and_signature(
    token,
    jwks,
    message,
):
    with pytest.raises(fair.FairError, match=message):
        fair._verify_oidc_attestation(token, jwks)


@pytest.mark.parametrize(
    ("claim", "value", "message"),
    [
        ("iss", "https://example.invalid", "iss"),
        ("aud", "wrong-audience", "aud"),
        ("repository", "attacker/fork", "repository"),
        ("ref", "refs/heads/feature", "ref"),
        ("event_name", "push", "event_name"),
        (
            "workflow_ref",
            (
                "kody-w/localFirstTools-main/.github/workflows/"
                "other.yml@refs/heads/main"
            ),
            "workflow_ref",
        ),
        ("environment", "unprotected", "environment"),
        ("actor", "", "actor/run_id"),
        ("run_id", "run-123", "actor/run_id"),
        ("exp", None, "exp/nbf"),
        ("nbf", None, "exp/nbf"),
    ],
)
def test_oidc_rejects_forged_claims(claim, value, message):
    claims = _valid_oidc_claims(**{claim: value})
    with pytest.raises(fair.FairError, match=message):
        fair._verify_oidc_attestation(
            _signed_jwt(claims),
            _test_jwks(),
        )


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"exp": 1000, "nbf": 900}, "expired"),
        ({"exp": 1300, "nbf": 1200}, "not yet valid"),
    ],
)
def test_oidc_rejects_expired_or_not_yet_valid(updates, message):
    now = 1100
    claims = _valid_oidc_claims(now=now, **updates)
    with pytest.raises(fair.FairError, match=message):
        fair._verify_oidc_attestation(
            _signed_jwt(claims),
            _test_jwks(),
            now=now,
        )


@pytest.mark.parametrize(
    ("bundle_digest", "district_digest"),
    [
        ("0" * 64, EXPECTED_DISTRICT_DIGEST),
        (EXPECTED_BUNDLE_DIGEST, "0" * 64),
    ],
)
def test_apply_release_rejects_input_mismatch(
    scratch_dir,
    monkeypatch,
    bundle_digest,
    district_digest,
):
    root = _prepared_release_root(scratch_dir)
    _mock_oidc(monkeypatch, _signed_jwt())
    with pytest.raises(fair.FairError, match="do not match"):
        fair.apply_release(
            bundle_digest,
            district_digest,
            root=root,
        )


def test_valid_oidc_apply_records_bounded_evidence(
    scratch_dir,
    monkeypatch,
):
    root = _prepared_release_root(scratch_dir)
    claims = _valid_oidc_claims()
    token = _signed_jwt(claims)
    calls = _mock_oidc(monkeypatch, token)
    candidate = fair._load_json(
        root / "apps" / "agent-fair" / "release-candidate.json"
    )
    frame = fair.apply_release(
        EXPECTED_BUNDLE_DIGEST,
        EXPECTED_DISTRICT_DIGEST,
        root=root,
        utc=_release_utc(root),
    )
    assert frame["sig"] is None
    assert frame["payload"]["assurance"] == (
        "unsigned-structural-unverified"
    )
    assert frame["payload"]["release_candidate_digest"] == (
        candidate["candidate_digest"]
    )
    for key, value in candidate["expected_frame_payload"].items():
        if key not in {"approval_evidence", "release_candidate_digest"}:
            assert frame["payload"][key] == value
    assert frame["payload"]["approval_evidence"] == {
        **claims,
        "attestation_sha256": hashlib.sha256(
            token.encode("ascii")
        ).hexdigest(),
    }
    assert set(frame["payload"]["approval_evidence"]) == (
        fair.APPROVAL_EVIDENCE_KEYS
    )
    assert token not in json.dumps(frame, sort_keys=True)
    assert "opaque-request-secret" not in json.dumps(frame, sort_keys=True)
    assert len(calls) == 2
    assert "canonical_write" not in frame["payload"]
    assert "direct_canonical_write" not in frame["payload"]


def test_valid_oidc_apply_release_is_idempotent(
    scratch_dir,
    monkeypatch,
):
    root = _prepared_release_root(scratch_dir)
    release_utc = _release_utc(root)
    token = _signed_jwt()
    _mock_oidc(monkeypatch, token)
    first = fair.apply_release(
        EXPECTED_BUNDLE_DIGEST,
        EXPECTED_DISTRICT_DIGEST,
        root=root,
        utc=release_utc,
    )
    second = fair.apply_release(
        EXPECTED_BUNDLE_DIGEST,
        EXPECTED_DISTRICT_DIGEST,
        root=root,
        utc=(
            datetime.fromisoformat(release_utc.replace("Z", "+00:00"))
            + timedelta(days=1)
        ).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
    )
    assert first == second
    released_frames = organism_ledger.read_frames(
        root / "apps" / "organism-frames.jsonl"
    )
    matches = [
        frame
        for frame in released_frames
        if frame["payload"]["event_id"] == first["payload"]["event_id"]
    ]
    assert len(matches) == 1
    assert matches[0]["kind"] == "zoo.observation"
    assert matches[0]["payload"]["approval_evidence"][
        "run_id"
    ] == "123456789"
