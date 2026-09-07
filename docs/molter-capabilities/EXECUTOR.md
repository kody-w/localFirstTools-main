# Bounded Copilot input reader

`scripts/copilot_utils.py` still returns response text or `None`, and keeps
the existing retry interface and default model. Callers must supply all required
context in the prompt. They must not rely on the model reading the source
checkout, following its custom instructions, editing files, or invoking tools
on their behalf.

## Why this boundary exists

The previous large-prompt path added `--allow-all` so the model could read a
temporary file. Prompt size must not grant filesystem, command or network
authority. Moving that input outside the argument vector is necessary for
large and multibyte prompts, but it is not permission to run an agent freely.

Every request now uses the same restricted path:

1. Create a private scratch directory and an empty input Git repository.
   Clear inherited Git redirection/configuration when initializing it. This
   prevents a caller's `TMPDIR` from accidentally inheriting a parent
   repository's configuration or hooks.
2. Write the UTF-8 prompt into that input repository. Keep the temporary
   `COPILOT_HOME` and output capture outside the directory exposed to the model.
3. Expose only the `view` tool and add only the owned input directory.
   Deny command, write and URL tools; disable built-in MCP servers, custom
   instructions, remote session export and automatic CLI updates.
4. Capture output privately, enforce timeout and byte limits, and stop the
   owned invocation process tree before removing scratch state.

There is no `--allow-all` fallback for unsupported CLI options or unavailable
authentication. Those conditions produce failure. Existing authentication and
provider configuration remain the operator's responsibility; the helper does
not obtain new credentials or change account/repository settings.

## Measured scope and limitations

The installed CLI was exercised with a prompt larger than 150 KB. An owned
sibling canary outside the input directory was denied. A controlled mutation
granting only that canary directory made it readable, demonstrating that the
restriction was not a green-but-vacuous assertion.

Do not describe this as zero-tool inference: the explicit input reader is
available. Do not assume an empty `--available-tools` argument provides a useful
input-delivery contract. In isolated programmatic calls, file-reference text
alone did not provide the prompt contents to a tool-free response.

One retry attempt means one CLI invocation, not exactly one provider API
round-trip. Reading supplied context may require another model turn. The
caller still controls the invocation timeout and retry count.

Limits are 8 MiB of UTF-8 prompt data, 8 MiB of returned response data, and
64 KiB of captured diagnostics. Output is captured in private temporary files
and checked before loading it into memory. Polling and cleanup are not an
operating-system resource quota or sandbox. The CLI binary, configured model
provider, host environment and authentication transport remain trusted
dependencies. Model output is untrusted and must still pass candidate
qualification and review.

Failures log their category or exit code, not raw prompts, responses,
diagnostics or credential values. Scratch state is removed rather than
published. Proposal-level failure receipts must preserve their own safe
diagnostics without treating missing model output as an improvement.

## Regressions

The existing pytest runner exercises command construction for small, large and
multibyte prompts; inherited broad grants and Git redirection; temporary state
cleanup; unavailable setup; output/diagnostic limits; invalid output; timeout
and descendant termination; and the unchanged retry API:

```sh
python3 -m pytest -m '' -q \
  scripts/tests/test_copilot_boundary.py \
  scripts/tests/test_copilot_retry.py
```

The source-capsule proposal pipeline remains POSIX-oriented. Its integrity
checks do not establish an OS sandbox, authenticated model execution,
application usefulness or deployment.
