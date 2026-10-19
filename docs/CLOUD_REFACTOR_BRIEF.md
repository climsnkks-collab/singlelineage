# Cloud refactor brief — 2026-10-20

This assignment changes only the structure of existing code. New gameplay or
feature implementation is outside scope. The local coordinator continues the
NPC and item implementation independently and owns integration and game tests.

## Frozen baseline and delivery

- Repository: https://github.com/climsnkks-collab/singlelineage
- Frozen baseline: the source snapshot commit containing this brief. The
  coordinator supplies the full SHA in the cloud task before work starts.
- Create `codex/observer-window-refactor` from that exact SHA in the cloud
  checkout. Return a separate PR, or a unified patch with exact parent and
  changed blob hashes if PR creation is unavailable. Do not merge or push main.

## Owned change scope

- `tools/clone_observer/core.py`: refactor only the existing `public_window`
  serialization function and small private helpers it needs. Consolidate the
  repeated bounded child traversal into clear, locally named logic if it
  improves readability. Preserve operation/error behavior for supported input.
- `tools/clone_observer/tests.py`: focused fake-only regression cases for the
  same serialization contract. Do not replace or weaken existing assertions.
- No new framework, dependency, mass formatting, broad rename or optimization.

Preserve every returned key, value, collection order, hash, string slicing
bound and allowlist decision. In particular: 240 title characters, 64 class
characters, first 64 children, 480 static-text characters, known public title
and class handling, exact launcher-message matching with existing whitespace
handling, unknown-text hashes, Edit/ComboBox text exclusion, and Default IME
role detection. Preserve missing keys, unknown class aggregation and optional
`owned_member` handling. Keep constants and `observe` entirely unchanged.

## Verification and evidence

Read the existing tests first. The existing suite imports Windows adapters and
contains current-process native query checks, so it is not a portable fake-only
suite. Report that limitation; do not run native checks in the cloud or invent
platform shims. Add direct serializer checks that do not
need Windows, native processes, games, ports, private files or assets. Cover
known/unknown classes and titles, duplicate child classes, text exclusions,
Static known/unknown text and ordering, truncation, IME and optional metadata.
For portable checks, loading `core.py` directly with standard `importlib` is
allowed; do not import Windows adapters. A new serializer-only test module
`tools/clone_observer/public_window_tests.py` is also within ownership if needed.
Do not invent permissive production fallback behavior to make tests run.
Report exact commands, counts, failures, and skipped/platform-dependent checks.
The coordinator inspects the actual diff and performs any necessary local
verification before integrating. No game launch is required for this scope.

## Public snapshot limits and exclusions

This repository contains selected source and documentation only. Original
executables/resources, saves, run logs, private source evidence, extracted
anchor `.inc` arrays and external Native vendor sources remain local. Their
absence is an explicit public snapshot limitation; never request or upload
them for this refactor. Full game execution and source-evidence validations
are not established by cloud unit tests.

Do not modify `.gitignore`, other docs, any launcher/broker/runner, Native,
memory/ABI/wire contracts, security/launch/permission policy, NPC/item/life
modules, `work/`, or private ownership/state/handoff files. No local computer
access, REA, foreground input, new feature, merge, deployment, or original-data
upload is authorized by this assignment.
