# Mutating apps without pretending they are deployed

The existing `autonomous_frame.py` controller can prepare one mutation for
review. It does not start another scheduler, publish to `main`, close agent
issues, or append a successful public organism observation for unaccepted work.
Legacy `molt`/`molter` filenames and schemas remain compatible; user-facing
terminology is **mutating** and **mutation**.

## The boundary

```text
committed input -> one candidate -> local checks -> preserved review handoff
                                                     |
                         explicit operator verification and normal review
                                                     |
                               approval -> merge -> separately observed deployment
```

The source-capsule implementation is imported unchanged from
[kody-w/localFirstTools#24](https://github.com/kody-w/localFirstTools/pull/24).
Its manifest, source, evaluator and reference pins are recorded under
[`scripts/capabilities/source_capsule/`](../../scripts/capabilities/source_capsule/).
The old scheduler, job state, historical usage counts and registry labels are
not imported.

That capability proves selected committed-source transport and replay. It does
not prove application usefulness, authenticate repository ownership or authorize
publication. Candidate structural checks and real browser outcomes are separate
evidence. The public ledger remains `structural-unverified`.

## Prepare one candidate

Use a pristine Git worktree: source preparation refuses dirty, untracked,
ignored, hidden-index and symlinked inputs. Do not delete your development
dependencies to satisfy that rule; create an isolated worktree instead.
The output must be a new, privately owned directory outside every source
worktree and Git storage. Its parent must already exist.

From that source worktree:

```sh
base=$(git rev-parse HEAD)
python3 -B scripts/autonomous_frame.py \
  --prepare-proposal /absolute/owned-artifacts/proposal \
  --base "$base" --repository kody-w/localFirstTools-main \
  --target cyber-timer.html \
  --candidate-file /absolute/owned-input/cyber-timer.html \
  --objective "Keep elapsed time accurate and all controls reachable." \
  --dry-run
```

The dry-run is a read-only plan. Remove `--dry-run` to qualify and preserve the
supplied candidate. Alternatively, omit `--candidate-file` and explicitly use
`--allow-model` for one bounded rewrite/CLI attempt. Do not combine the two
input modes.

Without `--target`, selection uses the existing committed ranking/generation
policy and admits at most one app. The candidate core keeps its conservative
100,000-byte exclusive model-prompt ceiling even though the shared input reader
can deliver larger prompts. Failed, unchanged, metadata-only and rejected work
is not a useful mutation.

Model execution needs an installed, authenticated, compatible Copilot CLI.
This feature does not provision credentials or increase account permissions.
See [the executor boundary](EXECUTOR.md) for the scoped input reader, byte and
time limits, and the distinction between a CLI attempt and provider API calls.

## Preserve and replay the exact handoff

A prepared directory contains the complete patch, base-bound candidate Git
bundle, pinned capability implementation and reference, qualification report,
one RAPP-bound replay, registry projection, and hashes of all retained files.
No source checkout, implementation `.git`, or machine-local Git alternates are
needed after preparation.

Plain GitHub artifact ZIPs do not preserve file permissions, and hidden files
can be omitted. Package the verified directory first:

```sh
python3 -B scripts/mutation_handoff.py pack \
  /absolute/owned-artifacts/proposal /absolute/owned-artifacts/proposal.tar \
  --repo /absolute/source-worktree --base "$base" \
  --repository kody-w/localFirstTools-main

python3 -B scripts/mutation_handoff.py unpack \
  /absolute/owned-artifacts/proposal.tar /absolute/owned-artifacts/restored \
  --repo /absolute/source-worktree --base "$base" \
  --repository kody-w/localFirstTools-main
```

Unpacking rejects traversal, links, special files, duplicate entries, unsafe
modes, oversized content and mismatched hashes. Execution-support bytes must
match the committed producer package before archived code can be evaluated.
It never overwrites an existing destination.

`verify` and `status` inspect archived integrity/RAPP/registry evidence without
rerunning checks or models:

```sh
python3 -B scripts/molter_capabilities.py verify \
  /absolute/owned-artifacts/restored \
  --repo /absolute/source-worktree --base "$base" \
  --repository kody-w/localFirstTools-main
```

A fresh transport replay is an explicit, separate operation:

```sh
python3 -B scripts/mutation_handoff.py replay \
  /absolute/owned-artifacts/restored \
  --repo /absolute/source-worktree --base "$base" \
  --repository kody-w/localFirstTools-main --allow-checks
```

Replay reconstructs the original candidate at the report-bound `../source`
location and executes the unchanged 15-element replay command. It does not
rewrite the report, mint a new qualification/registry entry, generate an app,
or modify the preserved directory. The supplied checkout must contain the
historical base objects; there is no network fallback.

## Operator review is a different authority

Archived proof can remain valid after the current checkout changes. Readiness
to apply is stricter:

```sh
python3 -B scripts/molter_capabilities.py verify \
  /absolute/owned-artifacts/restored \
  --repo /absolute/clean-review-worktree --base "$base" \
  --repository kody-w/localFirstTools-main --require-current-base
```

Then inspect `proposal.patch`, the actual app, the declared checks and the
complete change scope. An authorized operator can import the original candidate
commit into a new review branch:

```sh
git -C /absolute/clean-review-worktree fetch \
  /absolute/owned-artifacts/restored/candidate.bundle \
  refs/heads/molter-proposal:refs/heads/review-mutation
git -C /absolute/clean-review-worktree switch review-mutation
```

This is an explicit local application, not merge approval. Submit the reviewed
branch through the repository's ordinary process. The adapter cannot attest
that a PR exists, has been approved, has merged, or is served by GitHub Pages.
Branch protection and independent review remain required.

## Failure and retention

Concurrent callers cannot both acquire an attempt. Interrupted directories
retain request/progress evidence, report recovery state, and refuse automatic
retry. A terminal result can be verified and reused without regenerating work.
Do not delete an interrupted directory just to make the same operation run
again.

The scheduled workflow binds to its exact committed input and keeps a verified
cache. Cache loss is not proof of a new task: known completed work blocks
automatic regeneration and points the operator toward the preserved artifact.
Unverifiable history fails closed.

Only completed, qualified handoffs are exported. Failed or interrupted runs
export safe outcome metadata rather than raw prompts, worker diagnostics or
retained Git staging. The existing remote writer-lock still needs the original
`contents: write` permission; the candidate path receives no new publication
authority.

Actions artifacts have a finite retention window, not infinite durability.
An accepted result and its relevant evidence must be promoted into maintained
Git history. The committed [pilot archive](pilot/proposal.tar) is one such
durable reference artifact, not a new accepted ledger event.

## Real pilot and acceptance

The [pilot case](pilot-case.json) records a real Cyber Timer defect: one delayed
callback after 61 elapsed seconds displayed `24:59` instead of `23:59`.
The supplied candidate also fixes completed-cycle restart and narrow-screen
clipping. Its eight browser groups run against the actual HTML without network
access.

The committed archive binds source base
`27f08a6a0ea928ae678288becada60569d85a2b8`, candidate commit
`18b60e437f85b25d774dd3556f2ee112cb0a36c3`, and request
`c3e7307980e6d56f3ae00bde8a5774826c9f57dca8ade38a22c68a3ab8b6ea96`.
The pipeline consumed supplied source; it did not invoke a model to produce
that candidate. Its single real registry use is `proven`, not invented
cross-repository adoption.

The accompanying [history bundle](pilot/history.bundle) preserves the exact
recorded commits across squash merges and feature-branch deletion. Its
[metadata](pilot/history.json) pins the bytes and the already-published
`0a6b9843f86e95587c31af0095f4bd440cd3042e` anchor. If a fresh checkout lacks
the pilot base, verify that pin and restore the history **into an isolated
review checkout**, without changing its working files:

```sh
git -C /absolute/clean-review-worktree bundle verify /absolute/pilot/history.bundle
git -C /absolute/clean-review-worktree fetch /absolute/pilot/history.bundle \
  refs/heads/review/cyber-timer-mutation:refs/remotes/mutation-pilot/verified
```

Do not silently fetch a missing anchor from a remote. Restore it through an
explicit trusted repository checkout first. Historical object availability
does not make an old patch ready to apply to today's HEAD.

```sh
python3 -B scripts/capabilities/source_capsule/check_port.py
python3 -B scripts/check_molter_capabilities.py
```

The [acceptance contract](acceptance.json) requires named executable cases.
Missing cases, missing reports, skipped cases and timeouts cannot pass.
Real qualification/replay cases are kept distinct from explicitly unqualified
fault fixtures. An independent read-only critic is still required before
handoff.
