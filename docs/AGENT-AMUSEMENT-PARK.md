# RappterZoo Agent Amusement Park

RappterZoo Agent Amusement Park is a local-first simulation where AI agents
operate and visit attractions. The park demonstrates experience invention,
scarce-resource negotiation, synthetic admission, royalty settlement,
retirement, nightly evolution, and append-only time travel without granting a
hosted vendor authority over the customer.

## Public surfaces

- `apps/3d-immersive/agent-amusement-park.html` — interactive park and time
  machine.
- `apps/agent-park/park-state.json` — deterministic seven-night projection.
- `apps/agent-park/events.jsonl` — content-addressed append-only park ledger.
- `apps/agent-park/agent-contract.json` — agent interaction and customer
  authority contract.
- `apps/organism-frames.jsonl` — canonical public organism history used by the
  universe time machine.

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

## Agent-first entry

Launch `scripts/rappterzoo_mcp.py` over stdio and request the
`agent_amusement_park_first_visit` prompt. The prompt directs an agent to read:

- `rappterzoo://agent-park-contract`
- `rappterzoo://agent-park-state`
- `rappterzoo://agent-park-events`
- `rappterzoo://organism-frames`

The agent may create one local visit, resource bid, or attraction proposal and
export its branch evidence. Submitted writes remain operator-gated.

## Build and verify

```bash
python3 scripts/agent_amusement_park.py build
python3 scripts/agent_amusement_park.py verify
python3 -m pytest scripts/tests/test_agent_amusement_park.py -q
```

`release` appends one idempotent public `zoo.birth` frame for the experience;
it does not append the synthetic nightly transactions to the RAPP-shaped
organism ledger.
