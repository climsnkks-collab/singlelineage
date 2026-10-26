# COMPANION-MAGE actor configuration v1

WRITER_RELEASED. Private standalone source wiring is ready for main review.
`run_ready:false`, `test_ready:false`, runtime **UNRUN**. No queue or Test message.

`companion_actor_config.py` supplies `build_callbacks(...)`. It constructs the
existing `LocalMageDtoProducer` from the exact list.spr, the real
`MageWorldSource` using **session.world/session.wire identities**, and two
ordinary function callbacks owned by the configuration module:

- `actor_factory(broker, host)` checks the same real Host/realm/store and returns
  the existing exact `AlliedPlayerPort` with that DTO source, profile and UTC
  clock. It supplies no substitute actor, registration, native pose or ATS UI.
- `direct_world_for(record)` uses actual `store.select(record['name'])` and
  UID/same-record checks before `MageWorldSource.direct_world_for`. This is a
  complete class3 SelfInfo/Actor seed, retaining original subsequent RESOURCE
  restore semantics. Non-class3 uses the explicitly supplied, source-pinned
  original callback. No class0 dict/profile fallback is manufactured.

## Installation contract

Use the final selected graph's modules, **same account CharacterStore later
used by Host**, selected world_profile, and the existing class0 full DTO
callback plus its actual Factory `SourceModule` as `legacy_source_pin`:

```python
callbacks = actor_config.build_callbacks(
    modules=modules, store=actual_account_store, world_profile=world_profile,
    legacy_direct_world_for=existing_full_direct_callback,
    legacy_source_pin=existing_callback_source_pin)
configuration = host_module.CompanionBootstrap(
    actor_factory=callbacks.actor_factory,
    direct_world_for=callbacks.direct_world_for,
    shared=actual_shared_configuration,
    interface=actual_native_interface_if_available)
```

Capture the configuration module itself by its manifest path/hash as a Factory
`SourceModule`. Also capture each `(module,path,sha256)` in
`callbacks.source_triples` with the existing `SourceModule` and the supplied
`legacy_source_pin`; deduplicate by module identity against the eight required
companion modules/other selected sources before `bind_companion`. Capturing
only mage_world while callbacks belong to this module fails Factory's
`COMPANION_NATIVE_CALLBACK_SOURCE_REQUIRED`. The legacy callback's code module
must also be captured despite the outer callback belonging here. The native
interface/shared configuration and their exact captured modules remain owned
by the real runtime configuration, and are not supplied by this unit.

The config expects the exact existing allied v2, mage-world-v1, appearance and
character_state source selections in `manifest.json`. No loader, Factory,
Host, Broker or root source is changed. The existing initial cohort was used
only for cold imports; it is not promoted to a coherent runnable selection.

## Verification and remaining boundary

Run from the repository root:

```powershell
python work/local_original_session/implementation-companion/companion-actor-config-v1/verify_cold.py
```

Five cold checks PASS in `verification.json`: real pinned DTO constructors,
both callback code module identities, existing Host bootstrap acceptance,
real AlliedPlayerPort signature compatibility and original session codec
identity/no account created. A real CharacterStore object points at a never
created path; no store is read or written. The verifier's legacy callback is
explicitly a never-executed fixture, not a candidate runtime callback.
Actor factory/direct callback/Host attachment/Factory bind were not executed.
Existing DTO pure semantic checks are reused from mage-world-v1 rather than
rerunning full fixtures or packet scenarios.

`companion-summon-input-v1/input-source.json` is pinned as input evidence only;
its approved full saved account has direct UID1/class0 and mage UID2/class3.
No saved file was opened, copied or modified by this unit. Test must make its
own new full copy when a coherent summon runtime exists. Actual summon and
dismiss/native input, current client pose/absence, full runtime config and its
normal-player packet scenario remain unverified. No RUN_COMMAND for game
execution is claimed and this unit must not be queued as `test_ready:true`.

Only this new directory was written. Existing dirty/untracked shared files
and current main branch were preserved; no branch/worktree was created.
