# COMPANION-MAGE — server pose step v2 default admission correction

State: **SOURCE_COMPLETE / WRITER_RELEASED**. source_ready=true (bounded source),
test_ready=false, run_ready=false, selected=false, runtime=UNRUN.

Immutable new descendant of `local-allied-server-pose-step-v1/`. No v1,
common/original/Test/queue/ACTIVE or runtime changes. No game, save copies,
listeners, processes or packets. `parents.json` records six exact v1 product
parents, the tombstone Allied reference and required unchanged motion Broker.
`manifest.json` records six exact product hashes; `.diff` files show exact v1
deltas. `build_private.py` reproduces all six products.

## Correction

The sole behavior delta from v1 is `AlliedPlayerPort.server_snapshot`.
An initial exact `pose_policy == 'LOCAL_SERVER_POSE_ONE_STEP'` branch checks the
real retained registration/lease/actor identity and projects `_server_actor`,
which still admits the typed motion through actual later-current/current
RESOURCE before reporting committed coordinates.

After that branch, the complete original tombstone-parent method body is
preserved verbatim and AST-equivalent. Default policy therefore retains original
`root.current(record)` → `_same_owner(record.owner, owner)` plus UID/generation
checks → original `_resource(host, owner, lease)` ordering. It does not call
later_resource or broaden owner admission. Registration/removal-unavailable
returns remain original.

Other unconditional default changes were reviewed: v1 Controller/Host products
are byte-identical here; default pose admission still uses original CLIENT_POSE;
Port spawn/snapshot/step retain their existing None-policy branches. Additional
later-current methods remain unused by the default snapshot. New policy/cache
fields do not replace default authority. All other Port methods are AST-identical
to v1. Original retirement/UNKNOWN semantics remain intact.

Allied's corrected hash propagates only through exact Allied pins in registry,
navigation and motion, then the resulting registry/navigation direct pins.
Unchanged external Broker remains motion-broker-v1 `c422517e...`. Separate
removal v5 `b1fdf585...` is not composed here. The v1 documented final Broker
composition/graph/normal packet caller/RUN blockers remain, so test_ready=false.

## Focused verification

```powershell
python work/local_original_session/implementation-companion/local-allied-server-pose-step-v2/verify_focused.py
```

**47 source/isolated-model checks PASS**, runtime UNRUN. Includes v1 bounded
checks, byte/hash/syntax/direct pins; exact parent AST for the default snapshot
after removing only the opt-in branch; unchanged v1 Controller/Host and all other
Port methods; isolated default original-current/resource ordering, foreign-owner
refusal before resource read, and opt-in committed coordinate projection.
The actual `_server_actor`/typed motion path remains source-bound and unchanged
from v1. Isolated doubles prove method/control behavior only, not live leases,
RESOURCE, transport/Store commitment, runtime movement, native pose or ACK.
