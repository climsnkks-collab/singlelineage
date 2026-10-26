# COMPANION-MAGE — combined private Broker v1

State: **SOURCE_COMPLETE / WRITER_RELEASED**. source_ready=true,
test_ready=false, run_ready=false, selected=false, runtime=UNRUN.

Owned files are confined to this directory. The existing dirty main checkout,
queued v5 trial, original/common/Test/client/API/queue/ACTIVE and all saves,
runtime outputs, processes and ports are untouched. No runtime or packet test
has been performed. Main owns review and any later queue selection.

The combined Broker is `ad4030062c236ce329ad5ac32b667b21fb93bcbd84b8f76fc36845892fa1c17e`
(411945 bytes). Exact products and their paths are in `manifest.json`:

- Navigation: `3ac1a431e1d97bcd6928e9dcde51d22f274df5045255e08efad9d338c30fc620`.
- Motion: `bac668ba29034ef1442303a8f8600921ca8a6021cd7ed51b9d924c869368026a`.
- Registry: `617d6049bc0d6e86aca4806fda5077351d2dafd52a7dac5d4d27e7c7d74f0add`, byte-identical to motion parent.

## Exact composition

`parents.json` fixes the common v4 Broker
`8fe7b3e26c4ae510184604624160445a0c6b28291daafc8feac92be4d3f7a7cc`,
v5 removal-policy Broker
`b1fdf585df3f6ab7a38f89f8e10c99badc9892fe7c250a935995abd56f5f6904`,
and motion Broker
`c422517ebe9e934c0425aaf833efca081f604d747654df9ffb8f66561a48e09d`.

`build_source.py` applies the exact four v4→v5 removal-policy hunks to the
motion Broker, with unique context matching and an exact inverse check.
It only repins the resulting Broker SHA in navigation/motion and the resulting
navigation SHA in motion. Registry remains unchanged. The three Broker diffs
show the result against each input, and per-module diffs show only those pins.

`composition-proof.json` records full method AST comparisons. Against v4 or
motion, only `_TransportPolicy.begin_write`, `PersistentBroker._policy_sample`
and `_send` change. Against v5, only `_send` changes. Removing the exact
removal-policy branch from the combined `_send` restores the motion method;
removing it from v5 restores the v4 method. Reversing the pin substitutions
restores navigation/motion parent bytes. All other methods retain their exact
AST; no 4E96, NPC or ordinary 4E40 admission is widened.

The exact typed RESERVED 4E40 admission and the exclusive initial one-step
typed 4E2C send coexist. Motion's original begin/attempt/write/drain/commit,
pending-safe cancellation/error/UNKNOWN behavior and NPC gate separation are
preserved. Existing current/250ms freshness, Store contracts and retained
leases are unchanged. No caller, Controller, config, Source family selection,
timer, UID, current sample or native/client success claim has been added.

## Bounded verification

- `python work/local_original_session/implementation-companion/local-allied-combined-broker-v1/build_source.py`
  reproduces products and proves exact input hashes, inverse deltas and AST boundaries.
- `python work/local_original_session/implementation-companion/local-allied-combined-broker-v1/verify_motion.py`
  passes 87 existing focused checks: source pins/cold imports, actual SourceSeal
  registry admission, original pending model, exact `_send` order, errors and
  cancellations, retained UNKNOWN/pending, exclusive identical frame, ordinary
  NPC gates and actual zero queue before commit. Result: `verification.json`.
- `python work/local_original_session/implementation-companion/local-allied-combined-broker-v1/verify_removal.py`
  passes 10 checks, reuses 183 existing cold imports, cold-imports the actual
  combined Broker and exercises its real `begin_write` with an isolated record
  and checkpoint double. Missing capability, wrong type, feature off, replay,
  foreign record and equal-but-nonidentical wire are rejected. Result:
  `verification-removal.json`.

These are isolated source/control-flow checks, without live session/current,
RootPlayers/Resource authority, real transport, game, Store, native state or
runtime PASS. The existing v5 import graph is cold scaffolding only; its
runtime config is not claimed as a combined cohort.

## Remaining owner work

Complete Port/Controller/scheduler/feature config, exact complete SourceSeal
cohort and the normal packet caller/RUN before test_ready may become true.
Navigation/motion still require the exact later-current Allied source
`3e87aec85aa85444571e2f4ff4b79613e23db3d9a4ebbd978723e7d050475dee`;
the queued v5 trial selects `bf517611...`, and neither has been silently
substituted or declared a compatible finished cohort here. Corresponding
consumers must be selected and repinned by their owners. Existing actual
137/138 findings and v5 runtime UNRUN boundary remain unchanged.
