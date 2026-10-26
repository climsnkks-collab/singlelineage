# COMPANION-MAGE post-drain retirement current v1

WRITER_RELEASED / source_ready:true / test_ready:false / run_ready:false / runtime:UNRUN.

Private fragment only. Exact parent d1490b4e97c1c0e585f129563b4c5d42c77df89d80c26ef1520ca2f2f867a1cb; source and all dependency pins are in manifest.json; parent.diff is the complete delta. Original shared/Core/Test/queue/input/copies/UID cursor are unchanged.

RootPlayers.current remains AST-identical: original 4E96 publication still requires its exact Binding identity. New removal_current admits only a typed recorded DRAINED registration; original operation revalidates installed Root/Host, actual direct/companion leases, owner lifetime, live selected row/task/lock and fresh Binding. The retained and new Bindings must share actual selected generation, writer, canonical character UID and row lock; selection and row identities must match registration. Original _resource revalidates live same-account Store/RESOURCE uid/digest/revision/path and nonpending account under original locks. Registration Binding/generation/row/lease are never replaced. Resource digest can legitimately change after publication; no old digest is relabelled current.

Only exact removal-frame identity uses this predicate in Broker validation/send-phase through for_frame. Initial 4E96 keeps exact current. remove additionally requires original typed ActorSnapshot with exact retained actor UID/generation/lease character UID and spawn_drained. Removal is assigned once before the original single _send; an uncertain send is not retried. Existing ordered policy RESERVED -> WRITE_ATTEMPTED -> DRAINED remains unchanged. The never-emitted REGISTERED branch retains its old strict current and positive never-emitted proof.

A drained removal still returns RemovalResult(drained, False). Original Controller source16f5 uses absent=False -> retire_owner=False -> UNKNOWN/COMPANION_REMOVAL_UNCONFIRMED, retains lease and actor, then original Host strict retirement rejects COMPANION_RETIREMENT_UNKNOWN. No native actor absence or clean close is claimed.

## Close context and remaining first blockers

See close-trace.json. A normal Quit/Restart invokes before_retire_locked inside the genuine selected row operation before marking realm Quit/Restart. This source fragment permits later-operation removal there, but remains runtime UNRUN and cannot cleanly close without native absence.

The actual116 server.close teardown is a separate blocked path: Broker._serve finally calls connection_closing outside the original selected operation; canonical_operation_task is None, and explicit close sets _closing=True before cleanup. Host._row refuses COMPANION_CURRENT_BROKER_OPERATION_REQUIRED before Allied can send. This fragment does not change Broker/Host and cannot make teardown send 4E40. A genuine owned row/selection operation before teardown would need separate owner implementation; fabricating a scope, rebinding the record or relaxing guards is not accepted. Later COMPANION_UNRETIRED_CHARACTER_LEASE remains expected preserved evidence.

First native absence missing: original-client same actor UID + exact actor generation lookup/vector absence, or exact owning-world destruction proof. snapshot=None and retire_owner=False are unchanged. Packet drain, EOF and selecting another character do not supply that proof. actual116 first ALLIED_CURRENT_GENERATION_REQUIRED, FAILED history, AWAITING_POSE and retained lease remain unchanged.

## Focused checks

Run `python -B work/local_original_session/implementation-companion/local-f101-retirement-current-v1/verify_focused.py`: 15 source/isolated-predicate checks PASS. New Binding with same generation is admitted only for removal; original current/spawn reject it. Changed selected generation/selection/writer/UID/lock/phase/resource path and original Store refusal reject. Methods outside the two stated changes plus one new method are AST-identical, including allocator, current, operation, _resource, send_phase, close, snapshot/server_snapshot and retire_owner.

Isolated predicates use explicit doubles only to test local comparisons; these are not real Root/Store/Host ownership or direct-packet results. No game, server, port, copies, UID reset, original input mutation, REA or Test dispatch ran. No updated whole cohort/caller/NEW legitimate copy exists here; test_ready remains false. Prepared caller v3 is only pinned/reference unchanged and does not select this source fragment yet.
