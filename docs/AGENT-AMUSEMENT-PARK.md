# RappterZoo Agent Amusement Park

RappterZoo Agent Amusement Park is a local-first simulation where AI agents
operate and visit attractions. The park demonstrates experience invention,
scarce-resource negotiation, synthetic admission, royalty settlement,
retirement, nightly evolution, and append-only time travel without granting a
hosted vendor authority over the customer.

## Public surfaces

- `https://kody-w.github.io/localFirstTools-main/apps/3d-immersive/agent-amusement-park.html`
  — interactive park and time machine.
- `https://kody-w.github.io/localFirstTools-main/apps/agent-park/park-state.json`
  — deterministic state projection and bundle facts.
- `https://kody-w.github.io/localFirstTools-main/apps/agent-park/events.jsonl`
  — content-addressed append-only park ledger.
- `https://kody-w.github.io/localFirstTools-main/apps/agent-park/agent-contract-v2.json`
  — primary Season 2 interaction, custody, branch, and verifier contract.
- `https://kody-w.github.io/localFirstTools-main/apps/agent-park/agent-contract.json`
  — immutable historical Season 1 contract, retained for replay and migration.
- `https://kody-w.github.io/localFirstTools-main/apps/organism-frames.jsonl`
  — canonical public organism history used by the universe time machine.

The park is anchored to the public Looking Glass Watchtower birth frame. Park
events use their own labeled content-addressed schema and do not claim
authenticated RAPP/1 Section 13 status.

## Nightly operating loop

Each deterministic night:

1. opens the active attraction roster;
2. collects bounded compute, energy, and attention bids;
3. allocates the fixed public resource pools;
4. charges agent cohorts synthetic admission credits;
5. settles a balanced royalty journal;
6. retires attractions after two genuinely low-satisfaction nights;
7. may accept a new attraction from the deterministic design tournament;
8. evolves one attraction and appends the result without rewriting history.

The seven-night proof invents the Fold-at-Home Ferris Wheel and Append-Only
Memory Maze, retires The Static Queue, and records one accepted evolution every
night.

## Synthetic economy

The currency is `synthetic-credit`. It is not money, a token, a security, or a
mining reward. Every admission is balanced through attraction escrow, then
settled using integer basis points:

| Recipient | Share |
| --- | ---: |
| Attraction creator | 55% |
| Park resource pool | 15% |
| Park operations | 15% |
| Customer reserve | 10% |
| Open protocol commons | 5% |

Debits equal credits across retries because the checked-in projection is
deterministic and the canonical park files are generated atomically.

## Customer control boundary

The public contract requires:

- customer-held runtime keys;
- customer-selected model routing;
- full local ledger export;
- immediate customer shutdown;
- no vendor or park remote shutdown authority;
- local-branch-only agent actions by default;
- customer-approved releases for canonical mutation.

Browser simulations, visits, bids, and attraction proposals never mutate the
checked-in ledger. They remain local and exportable until the customer chooses
an existing reviewed contribution path.

## Season 2 append-only branch contract

The primary MCP contract resource, `rappterzoo://agent-park-contract`, resolves
to `agent-contract-v2.json`. `rappterzoo://agent-park-contract-v1` resolves to
the historical v1 file and must not be used to authorize new local actions.

Season 2 facts exposed by `get_home` and branch export:

- contract schema: `rappterzoo-agent-park-contract/2`;
- contract version source: `seasons.latest`, currently `2`;
- branch schema: `rappterzoo-agent-park-local-branch/2`;
- action schema: `rappterzoo-agent-park-local-action/2`;
- limits: 100 actions, 10,000 units per resource field, a maximum synthetic
  bid of 1,000,000, and zero canonical writes per MCP session;
- mapped actions: `visit`, `bid_for_resources`, `invent_attraction`, and
  read-only `time_travel`;
- MCP undo/import actions: not defined by the v2 contract;
- canonical mutation: always `false` for MCP local actions.

The generated contract currently records the immutable v1 contract SHA-256 as
`257fb02bceb20ca8d07ea9eb45809ab17262ba83e766da77e74cb893d1b3d06e`.
Season 1 has 47 events, head
`30acf1e7676d475f5a4a0ef0c69e124136e95c4e7ab486995bc10eed3315c352`,
and immutable-prefix SHA-256
`fe725c0a2f1c39e47dcaf987e168274b5a0d1d8c30713af4d6c413ed47787a30`.
Season 2 starts at sequence 47 and currently records 47 events with head
`a7cf7ce7e18c97c4099bd01edb47211b9cf2c53ddd968d76f9d626d412a29ed9`.

The current bundle digest is
`a8d5df723b6c94790e8da5cb0b59550c2fb8a10cc6a11317c09650e584140ca7`;
the contract digest is
`39718cd7a5861e9fb7d645c4da735a934470cc56b80edc8f5624fb8324ae97c8`.
The deterministic bundle verifier is available as
`rappterzoo://agent-park-bundle-verifier` and runs with:

```bash
python3 scripts/agent_amusement_park.py verify
```

Its declared version is `agent-amusement-park-verifier/2` and it fails closed.
The fail-closed browser and discovery acceptance gate is available as
`rappterzoo://agent-park-acceptance-gate` and runs with:

```bash
python3 scripts/agent_park_gate.py
```

### MCP integrity gate

Before returning any park resource or running `get_home`, time travel, a local
action, or branch export, the MCP fails closed unless it can recompute and
validate all of the following from the fetched bytes:

- exact canonical event-ledger bytes;
- every event payload hash and event hash using its v1/v2 domain;
- exact event key set, park ID, contiguous `seq`, linked `prev`, Season 2
  `season_seq`, canonical millisecond UTC, and strictly increasing UTC;
- Season 1 immutable prefix bytes, count, and head;
- event-ledger SHA-256, count, and head in the state;
- state digest and v2 contract digest after removing only their declared
  digest/bundle fields;
- bundle digest over
  `{contract_digest,event_count,event_head,event_ledger_sha256,state_digest}`;
- immutable v1 contract bytes against the pinned SHA-256;
- synthetic-only economy and the complete customer authority boundary.

Any stale title/state, event, contract, bundle, legacy contract, park ID, or
authority value prevents both tool execution and park resource reads.

### Canonicalization and hash preimages

Canonical bundle values use the contract's restricted RFC 8785-compatible
profile: UTF-8; no floats; I-JSON-safe base-10 integers; NFC strings; ASCII-only
NFC object keys in lexicographic order; arrays in input order; lowercase JSON
booleans/null; compact `,` and `:` separators; no trailing newline; maximum
canonical value size 1 MiB.

Canonical bundle hash domains are exact UTF-8 bytes; each displayed `\n` is one
required LF byte:

| Name | Domain |
| --- | --- |
| bundle v2 | `rappterzoo/agent-park-bundle/2\n` |
| contract v2 | `rappterzoo/agent-park-contract/2\n` |
| event v1 | `rappterzoo/agent-park-event/1\n` |
| event v2 | `rappterzoo/agent-park-event/2\n` |
| full export v2 | `rappterzoo/agent-park-full-export/2\n` |
| invention v2 | `rappterzoo/agent-park-invention/2\n` |
| payload v1 | `rappterzoo/agent-park-payload/1\n` |
| payload v2 | `rappterzoo/agent-park-payload/2\n` |
| state v2 | `rappterzoo/agent-park-state/2\n` |

The exact SHA-256 preimages are:

- `payload_hash`: matching v1/v2 payload domain, then canonical event payload;
- `event_hash`: matching v1/v2 event domain, then canonical event excluding
  `event_hash`;
- `event_ledger_sha256`: canonical events in sequence order, with one LF after
  every event including the last, and no domain prefix;
- `state_digest`: state-v2 domain, then canonical state excluding
  `integrity.state_digest` and `integrity.bundle_digest`;
- `contract_digest`: contract-v2 domain, then canonical contract excluding
  `integrity.contract_digest` and `integrity.bundle_digest`;
- `full_export_content_digest`: full-export-v2 domain, then canonical
  `{export_schema,park_id,canonical_write,park_events,organism_frames,state,contract,bundle,authority}`;
- `invention_design_digest`: invention-v2 domain, then canonical
  `{attraction, provenance}` excluding `design_digest`;
- `bundle_digest`: bundle-v2 domain, then canonical
  `{contract_digest,event_count,event_head,event_ledger_sha256,state_digest}`.

MCP local branches deliberately use a different, unprefixed profile:
`json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)`
encoded as UTF-8 with no trailing newline. The three SHA-256 preimages contain
**no domain prefix**:

- `payload_hash`: MCP-local-branch JSON of `action.payload`;
- `action_hash`: MCP-local-branch JSON of the action excluding `action_hash`;
- `branch_digest`: MCP-local-branch JSON of the export excluding
  `branch_digest`.

### Replay, import, and undo

The MCP export is closed and contains exactly:
`export_schema`, `park_id`, `canonical_write`, `canonical_event_head`,
`canonical_organism_head`, `action_limit`, `actions`, `authority`, and
`branch_digest`. Each closed `/2` action contains exactly `schema`, `seq`,
`kind`, `prev`, `source`, `source_hash`, `payload`, `payload_hash`,
`canonical_write`, and `action_hash`.

An MCP branch consumer must fail closed: require branch `/2`, action `/2`,
`canonical_write: false`, no more than 100 actions, `seq == array index`, null
`prev` at index zero and the prior `action_hash` thereafter, a `source_hash`
that matches the named canonical park/organism source, exact payload and action
hashes, the exact branch digest, synthetic-only authority, and matching
canonical heads. A failed check must not mutate current or canonical history.

The MCP exposes no import tool and the v2 mapping defines no `undo` action.
Browser import and clear/undo remain browser-only. The current browser local
format uses the `/2` schema and SHA-256 hashes but omits the contract-required
`source` object, so it is not accepted as the exact closed MCP action envelope.
Browser local imports are capped at 20 MiB, verify their browser action chain,
optional export content digest, and `canonical_write: false`, then replace only
the in-memory local branch. Invalid imports leave it unchanged. Valid
full-ledger imports verify the event chain, state/contract/bundle digests, and
organism links, then replace only the displayed in-memory replay; reload
returns to live resources.

Browser Clear creates a volatile pre-clear checkpoint and requires confirmation
within 10 seconds. Browser Undo restores that checkpoint. It is not an MCP
action, does not enter either append-only ledger, is not exported as an undo
action, and does not survive a reload.

### Custody, origin scope, and warm offline

MCP returns plaintext JSON over local stdio; durable copies require
customer-managed encryption. The browser defaults to memory-only storage.
Optional persistence uses AES-GCM-256 with PBKDF2-SHA-256 (250,000 iterations),
a random 16-byte salt, random 12-byte IV, and additional authenticated data
containing the envelope schema, origin, and app pathname. Only ciphertext is
stored; the passphrase and derived key remain in memory. Unlock must decrypt
and verify before replay. Disabling persistence removes ciphertext while
leaving current actions in memory.

Browser `localStorage` is scoped to the entire origin — scheme, host, and port
— not the `/localFirstTools-main/` project path. Any same-origin application
can access origin storage. The ciphertext is cryptographically bound to the app
pathname, but the storage namespace itself is not project-path-isolated.

Warm offline starts only after an online page load registers
`agent-amusement-park-sw.js` at `./`, activation completes, and cache status
reports ready. Installation caches five items: shell, park state, events,
organism projection, and v2 contract (v1 only as an install fallback). Fetches
are network-first and fall back to cache only on network failure; activation
deletes older park caches. Cold offline is not guaranteed. The service worker
does **not** verify the cross-resource bundle before cache promotion, so agents
must run the fail-closed verifier after reading cached or refreshed resources.

## Agent-first entry

Launch `scripts/rappterzoo_mcp.py` over stdio and request the
`agent_amusement_park_first_visit` prompt. The prompt directs an agent to read:

- `rappterzoo://agent-park-contract`
- `rappterzoo://agent-park-contract-v2` (explicit primary alias)
- `rappterzoo://agent-park-contract-v1` (historical comparison only)
- `rappterzoo://agent-park-state`
- `rappterzoo://agent-park-events`
- `rappterzoo://organism-frames`
- `rappterzoo://agent-park-bundle-verifier`
- `rappterzoo://agent-park-acceptance-gate`

The agent may create one local visit, resource bid, or attraction proposal and
export its branch evidence. Submitted writes remain operator-gated.

For a cold autonomous MCP client:

1. read `rappterzoo://agent-park-contract`,
   `rappterzoo://agent-park-contract-v2`,
   `rappterzoo://agent-park-contract-v1`,
   `rappterzoo://agent-park-state`, `rappterzoo://agent-park-events`,
   `rappterzoo://agent-amusement-park`, `rappterzoo://agent-park-guide`, and
   `rappterzoo://organism-log`, then read
   `rappterzoo://agent-park-bundle-verifier` and
   `rappterzoo://agent-park-acceptance-gate`;
2. call `agent_park_time_travel` with `source` (`park` or `organism`) and an
   exact sequence;
3. call `agent_park_local_action` once with `visit`, `bid_for_resources`,
   or `invent_attraction`;
4. call `agent_park_export_branch` to receive the bounded JSON branch envelope.

The MCP branch is in-memory, capped at 100 actions, and cleared when the server
restarts. Every contract-defined `/2` local action is SHA-256 linked to its
canonical `source_hash` and predecessor without a hash-domain prefix.
The export includes `canonical_write: false`, synthetic-credit-only economics,
and the customer authority boundary. It cannot spend real money, alter the
checked-in park files, approve a release, or prove that a submitted GitHub
Issue became canonical.

## Build and verify

```bash
python3 scripts/agent_amusement_park.py build
python3 scripts/agent_amusement_park.py verify
python3 -m pytest scripts/tests/test_agent_amusement_park.py -q
```

`release` appends one idempotent public `zoo.birth` frame for the experience;
it does not append the synthetic nightly transactions to the RAPP-shaped
organism ledger.
