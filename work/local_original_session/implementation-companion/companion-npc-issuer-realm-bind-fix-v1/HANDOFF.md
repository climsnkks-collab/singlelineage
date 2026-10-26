# COMPANION-MAGE unissued NPC Setup input correction v1

WRITER_RELEASED. source_ready:true / run_ready:true / test_ready:true applies only
to the prepared RESOURCE Host/root WORLD/lifetime trial. Actual runtime is UNRUN.
This new private directory is the only write scope. Main reviews/enqueues; Test
alone prepares the new whole copy, owns 12000/14030 and executes.

The actual first failure is pinned in manifest.parents.actual_F1_result:
integration-1/packet-companion-resource-host-world-actual-v1/
resource-host-world-result.json SHA0a1b1f9f7798ccc35fb4989198c3fc6fe72909ecc2db10d2ac03e20a20848703.
Original prepare failed NPC_UID_ORIGINAL_REALM_BIND_ONCE_REQUIRED with C2S0;
last success was genuine RESOURCE-only Plan/cold actor bind. Host/WORLD were not
reached. The failed result/partial files/copy are preserved, not reset or relabeled.

## Finding and exact correction

The failed caller selects npc_issuer_source=triple('npc_uid_issuer') in its genuine
root Setup, but never invokes the original issue_roster_cold and supplies no NPC
spawns. The original Issuer constructor leaves source=None. Original Setup.register
then invokes its selected issuer.bind, whose existing one-bind guard correctly
requires source is not None. This is an unissued-input error, not evidence that a
source/module guard should be relaxed.

Bounded fresh-process verification separately confirms the selected root package
attribute, sys.modules binding and _SELF_MODULE are the same nominal module;
Setup.register and Issuer.bind retain their original globals/code file identities;
root's NPC/allied module objects are the selected nominal objects. A genuine cold
former Setup reproduces source=None without issue/owner/registration. A genuine
corrected Setup validates through its original check and keeps its real allied
RootPlayers/source seal while npc_issuer and npc_issuer_seal are None. Original
PacketRealmOptions defaults to an empty NPC spawn tuple.

Only one caller argument changes:

    npc_issuer_source=triple('npc_uid_issuer')  ->  npc_issuer_source=None

This uses the original optional Setup input for this explicitly NPC-free trial.
Every other caller byte is identical to companion-resource-host-world-trial-v1/
run_feature.py SHA571ff94983550d8a5ad2e117a7c32d5182c8c9483e2669a18fc23b5d5b3590fd.
run_feature.parent.diff contains the exact one-hunk change. Inverse reconstruction
is checked. Strict BEFORE/AFTER close fault classification, first-error/raw stack,
partial Store, clean-owner gates and fresh-only-after-clean behavior are intact.

All 185 selected product rows, loader/dependencies, exact Broker/Peer/Server sibling
tuple, rebind92b source, RESOURCE Factory33ff, allied/root/issuer guards and common
client-v5/API remain unchanged. No NPC issuer bind need/check is deleted, skipped
or patched. With no configured issuer, original foreign() still refuses NPC-range
authority and npc_issued_current still requires an actual issuer. No roster/UID is
fabricated, issued, reserved or stored. A future actual NPC trial must supply its
original genuine roster issuance path; this caller-specific correction does not
change that contract or a common default.

## Executable trial and input

Test creates a NEW independent complete seven-file copy of the original passed
packet-mage-class3-input-v1 account. input-source.json is byte-identical to the
parent and pins all seven files plus actual CREATE/WORLD/fresh acquisition evidence.
Do not CREATE again, use the failed copy, overlay/reset/link a profile or modify the
original acquisition. The caller refuses original/incomplete/changed/linked copies
and existing result/artifact prefixes. Supply a new output in an existing owned
directory outside all profiles:

```powershell
powershell -NoProfile -File "C:\Users\Chansol\Documents\ChatGPT\싱글리니지\work\local_original_session\implementation-companion\companion-npc-issuer-realm-bind-fix-v1\RUN_COMMAND.ps1" -Copy "<Test NEW whole seven-file absolute directory>" -Result "<Test NEW absolute result.json outside profiles>"
```

Normal sequence is the original parent caller: actual saved UUID/root selection ->
cold original realm expectations -> genuine RESOURCE-only/no-SKILL Plan and allied
Setup -> actor-only bind before prepare -> original new runtime Broker/root/Host/
AlliedPlayerPort -> normal KEY/VERSION/login/INFO -> packetless root choice ->
4E28/WORLD_DRAINED/0964/current -> original locked direct CharacterLease/RESOURCE
observations -> unchanged original seven files/partial Store artifacts -> original
client/server/Plan/Host/namespace close -> same-copy one fresh owner only after
first clean success. Fresh must have different actual Host/Port identities and
restore the same root Store/current. The strict success label remains
RESOURCE_HOST_WORLD_FRESH_PASS only after both complete observations and closes.
The scenario is prepared, not a runtime pass.

## Verification and limits

verify_nominal.py performs read-only original source imports/cold Setup checks.
verify_source.py reuses the parent's exact-source/AST/CLI verification plus the
one-argument inverse check. All parent/runtime/artifact pins and input file hashes
are checked. The original seven file bytes and whole directory listing remain
unchanged after nominal checks. CLI --help is the only caller execution here.

No actual Realm/registered owner/Plan/Host/Broker/server/port/game execution, account
copy, UID/Store write, callback/handler direct invocation or transport simulation
occurs in this fix preparation. No Host/WORLD, postbind/stale/one-bind, fresh,
summon/dismiss/support/AI/Native UI or normal Quit success is claimed. The prior
actual failure remains a failed prepare with unclean-owner result, not a pass.
