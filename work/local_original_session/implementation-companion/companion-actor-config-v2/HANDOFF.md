# COMPANION-MAGE actor configuration v2

WRITER_RELEASED. New immutable private descendant of actor-config-v1; v1 and
all selected/shared sources remain untouched. `source_ready:true`,
`run_ready:false`, `test_ready:false`, runtime **UNRUN**.

## Change

The external legacy callback is now optional. Call
`build_callbacks(modules=modules, store=actual_realm.store,
world_profile=actual_realm.world_profile, realm=actual_realm)` before selected
sessions/world or movement exist. The exact selected
`companion-cohort-v2/product/broker.py` LocalRealm and exact canonical
`companion-ack-realm-v1/realm.py` CharacterStore types are required.

`LocalRealm._initialize` originally obtains and validates full DTOs from
actor_hook/spawn_hook, then retains them in `_self_fields/_actor_fields` with
`profile_uid/profile_name`. v2 copies these full dictionaries to a frozen
RootProfile at cold configuration time. Original class0 source policy is
UID1/class0/gender0; v2 requires the actual saved account row to match that
identity and the retained profile UID/name. It does not create a DTO, replace
stats, alter UID/name/appearance, or borrow selected status/current RESOURCE.
The returned original DTOs remain **pre-WORLD seeds** for the existing Host's
normal RESOURCE restoration, not claims of current HP/MP or native pose.

The callback checks record and fresh actual account row UID/name/class/gender
against that retained root identity and returns fresh copies of unchanged full
DTOs through the original world codec validation. Selecting a different class0
character, a changed saved identity, wrong realm/store/profile, a started realm
or source mismatch is refused. Later Host profile changes do not corrupt the
retained original root seed. Class3 continues through exactly the v1 real
store.select/full MageWorldSource path. An explicitly supplied external legacy
callback remains supported when `realm=None`; providing both sources fails.

Exact broker, canonical realm and the selected actor_hook **or** spawn_hook
modules are sealed once and included in `source_triples`. This configuration
module and both returned function callbacks retain their real module identity.
Main must capture this module by manifest pin and add/deduplicate the returned
source triples using existing Factory SourceModule, along with existing
required companion/shared/native source modules. No new loader/wrapper is
introduced. `legacy_source_pin` is None in the realm-derived path.

## Checks

```powershell
python work/local_original_session/implementation-companion/companion-actor-config-v2/verify_cold.py
```

Eight cold/pure checks PASS in verification.json. The five v1 cold contacts are
retained; three new checks cover complete fixture DTO preservation/immutable
capture, record UID/name/class/gender mismatch rejection and saved-row mismatch
rejection. Fixture literals are clearly marked and are not a fake realm or
runtime actor. No actual realm construction/realm-derived callback, Host
attach, actor issuance, Factory bind, normal packets, ports or saves were
executed. Existing v1 class3 semantic checks are reused.

`parent.diff` contains only the real v1->v2 module delta. manifest.json pins the
parent, exact source graph/realm/hooks, existing input evidence and artifacts.
The original passed account copy remains Test-owned and untouched. Actual
source-bound summon/dismiss/native callback and coherent runtime selection
remain pending; this private source must not be registered test_ready:true.

No queue/root/Test message. Only this new directory was written, on existing
main with unrelated dirty/untracked files preserved.
