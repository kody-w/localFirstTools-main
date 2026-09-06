# Preserved source-capsule capability

This is the reusable **source-capsule@1.0.3** implementation from
[`kody-w/localFirstTools#24`](https://github.com/kody-w/localFirstTools/pull/24),
commit `aa6b9e28745d64cc5a16154a3506a494112ee701`, not the old application or
scheduler. The original project-relative layout remains **inside this directory**.
The manifest's raw SHA-256 is:

```text
e6f639a6d9c0625d3857f872e979e415b92dc4811902156d686ae8db885b3b45
```

All six manifest artifacts, the registry implementation/test and the exact
RAPP pin are unchanged. [`upstream.json`](upstream.json) inventories imported
bytes; [`NOTICE`](NOTICE) preserves attribution and explains the upstream
license declaration. No historical reports, registry labels, use counts,
scheduler state, policies, requests, or web UI are imported.

## Run and validate

From the containing repository root:

```sh
python3 -B scripts/capabilities/source_capsule/verify_vendor.py
python3 -B scripts/capabilities/source_capsule/check_port.py
python3 -B -m scripts.capabilities.source_capsule --help
```

Requires Python 3, Git and POSIX; verified on macOS with Python 3.14.4 and
Git 2.50.1. No installed Python dependencies or network fallback are needed.
`verify_vendor.py` checks integrity only. `check_port.py` explicitly authorizes
trusted local test processes and disposable writes **inside this package**.
It runs 58 unchanged original tests (11 contracts, 22 package, 25 registry) and
4 port tests. Missing cases, skips, expected failures and incomplete runs fail.

The port tests actually copy the nested package into a disposable local Git
fixture, transport committed bytes despite dirty source, preserve CRLF and
executable modes, qualify with the unchanged manifest, execute its exact replay,
record a real RAPP receipt, and build/verify/search its registry projection.
They also mutate source pins and receipts and test authority/output refusals.
All fixture registry states are discarded; these are **not target application
qualification, independent adoption, publishing or deployment evidence**.

## Stable CLI and Python interfaces

The direct CLI is `scripts/capability_package.py` **relative to this package
root**, with `pack`, `restore`, `qualify`, and `verify` unchanged. For example,
after entering this directory, given a reviewed sibling checkout `../source`,
its complete `$commit`, and write/process authority already granted:

```sh
manifest=landgrab/autocomplete/capabilities/manifests/source-capsule.json
mkdir -p results/check-work
export TMPDIR="$PWD/results/check-work" TMP="$PWD/results/check-work" TEMP="$PWD/results/check-work"
export PYTHONDONTWRITEBYTECODE=1
python3 -B scripts/capability_package.py qualify \
  --root . --manifest "$manifest" --repo ../source \
  --ref "$commit" --repository owner/source --path app.py \
  --workflow local-transport --capsule results/capsule.json \
  --report results/qualification.json --allow-checks
python3 scripts/capability_package.py verify --root . \
  --manifest "$manifest" --repo ../source --capsule results/capsule.json \
  --report results/qualification.json --replay --allow-checks
```

Use fresh capsule/report filenames for every qualification. `pack --repo …
--ref … --repository … --path … --output …` writes a capsule relative to the
current directory; `restore --capsule … --destination …` restores only into a
new directory whose parent already exists. Repeat `--path` to select files.

From the containing repository root, imports do not change CWD, run checks,
load a reference, or install global module aliases:

```python
from scripts.capabilities.source_capsule import (
    ROOT, MANIFEST, RAPP_REFERENCE_DIR,
    capability_package, capability_contracts, capability_registry,
    autocomplete_frames,
)

# Read committed sources without writing a capsule:
capsule = capability_package.pack_sources(checkout, commit, "owner/source", paths)
# Explicit caller-authorized write:
restored = capability_package.restore_capsule(capsule, new_destination)
```

`ROOT` is an absolute `Path`; `MANIFEST` is the relative manifest string;
`RAPP_REFERENCE_DIR` is the bundled export `Path`. For CLI-compatible Python
calls use `capability_package.main(argv) -> int`. For structured results,
`args = capability_package.parser().parse_args(argv)` followed by
`capability_package.qualify(args) -> dict` or `verify(args) -> dict` retains the
same contract. Qualification arguments include `root`, `manifest`, `repo`,
`ref`, `repository`, `path`, `workflow`, `capsule`, `report`, `allow_checks`;
verification uses the common location fields plus `replay`, `allow_checks`.

`--root` is the **implementation/package root**, not the caller's source repo.
Checks execute there. `--repo` is a normalized relative label and may select a
sibling or ancestor (e.g. `../../..` for the containing repo). Selected capsule
paths, by contrast, must be explicit committed regular files: no traversal,
symlinks, private paths, uncommitted additions, or non-UTF-8 bytes. Limits are
32 files, 4 MiB raw source and 8 MiB encoded JSON.

Replay is the exact 15-element `report["replay_argv"]`, rooted at `"."`; its
manifest path, checkout label and output paths are bound. Validate with
`capability_contracts.validate_source_replay(argv, capability_package.ENTRYPOINT)`
and execute unchanged with `cwd=ROOT` (or the complete relocated package copy).
Do not append `--help`, substitute a checkout label or rewrite output paths.
Moving the package intact is supported; changing its internal layout is not.

## Reference and registry

`vendor/rapp-1/` contains only the pin-verified `rapp.py`, `rapp_check.py`,
`SPEC.md`, and unchanged MIT `LICENSE` from
`kody-w/rapp-1@eb50008011447f5e69372ac22a1755f0978d15ed`.
`autocomplete_frames.Reference` accepts this plain source export: it checks all
three hashes and executes those exact bytes. **No reference Git checkout or
fabricated Git identity is needed.** The unchanged pin is
`landgrab/autocomplete/rapp-reference.json`; its rev-15 identity is authoritative
despite the reference Python docstring's older rev-14 wording.

The full gate also supports an explicit existing canonical checkout/export:

```sh
python3 -B scripts/capabilities/source_capsule/check_port.py --rapp-dir /path/to/rapp-1
```

Both the original external checkout and bundled-export invocations are tested.
The runner sets `RAPP_REFERENCE_DIR` for the unchanged registry tests and directs
`tempfile` scratch locally. Direct original unittest runs must set that variable
and a local `TMPDIR` themselves; missing reference coverage is an error.

Original registry APIs remain `build_registry`, `verify_registry`,
`search_registry`, and `write_registry`; its CLI is
`scripts/capability_registry.py {build,verify,search} --help`. Build/verify take
the implementation `--root`, `--manifest "$manifest"` (or `--manifests DIR`),
and, for an existing evidence store, `--store PATH --rapp-dir vendor/rapp-1`.
Build additionally needs `--output PATH`; verify needs `--registry PATH`.
Without evidence only an explicitly unqualified `built` projection is possible.
Evidence-backed status requires real canonically verified RAPP frames, the
actual successful replay, and complete manifest/dependency artifact attestations
in the same frame. Registry **search is projection-only**, never fresh proof.

## Authority and limitations

Authorize writes **before** invoking `qualify`: even without `--allow-checks`,
it writes a capsule and a failed report. That flag only permits declared process
checks. `verify` requires **both** `--replay --allow-checks`; although reports
remain unchanged, fresh restore/check fixtures need a writable implementation
root. Use a complete private package copy when the installed root is read-only.

Checks are trusted local processes, **not a sandbox**. `network: none` is a
declaration, not OS network isolation; callers must review commands and grant
authority independently. Guards are not a general secret scanner. Qualification
proves selected committed-source transport/restore and its own evaluators, not
application functionality. Unsigned hashes and receipts do not authenticate
authorship, repository ownership, trusted time or publication. No model,
scheduler, push, merge, deployment, or approval workflow is bundled or started
implicitly.

The only packaging additions are import entrypoints, integrity/validation
drivers, port tests and metadata. None patches or relaxes the pinned code.
