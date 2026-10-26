# Allied Player publication — private source v2

WRITER_RELEASED / SOURCE_ONLY / runtime UNRUN / `test_ready:false`.
Writer: GPT-6.1 Sol / medium (the v1 high label was inaccurate).
Only this v2 directory was written; released v1 remains byte-for-byte preserved. Shared/frozen sources, queue, Test client/API,
validation accounts, ports, processes, game and REA were untouched.

## v2 owner snapshot correction

Exact direct parent is released v1 manifest365f5d8e and
allied_player_publication.py d3f581cf7f16affffde31d2d95ff79918bbf8f36d037dd5918636008982a6e67.
`CompanionController.experience_participant` obtains a fresh OwnerSnapshot from
`_owner_now()`. The former `record.owner is owner` check wrongly refused that
valid read. `server_snapshot` now compares actual connection, lease and lifetime
by identity, and character/actor/map/grid/alive by value. Actor UID and generation
identity remain required. It still calls RootPlayers.current(record), then the
existing `_resource(host, supplied_owner, lease)` path which checks the supplied
owner through RootPlayers.operation and rereads the actual RESOURCE.

The bounded new check loads the original frozen OwnerSnapshot DTO, verifies a
fresh equivalent DTO is accepted and changed lifetime/lease/connection/character/
map is refused. AST inspection confirms the current→owner comparison→actual
RESOURCE/operation calls remain. These synthetic DTO checks claim no current
lease admission, registered actor, send receipt or runtime PASS. Exact v1 diffs
are adjacent. Broker/root/Peer/Server bytes are unchanged from v1.

## Product delta

`allied_player_publication.py` implements a root-owned typed Player registry
and concrete `AlliedPlayerPort`, separate from NPC spawns. Root `Setup` accepts
one sealed `allied_player_source`, binds it only from original registration,
and closes it without asserting client absence. No default summon or request
opcode was introduced.

Explicit LOCAL account UID policy is **0x30000000..0x3000ffff**. It is disjoint
from NPC 0x20000000 and ITEM 0x40000000 domains. Issuance holds the original root,
inventory/character/realm locks, rejects imported PCs/next cursor, all readable
account/child inventory UIDs and NPC spawn collisions, then reserves one UID
in `allied-player-uid-state.json` under its account OS lock/CAS/atomic replacement.
The durable cursor advances before DTO registration. Later failure, dismissal
or restart never rewinds it. Generation is a new retained object per issued
registration. `foreign` admits a Player alias only for the exact current typed
record; PC creation/import explicitly refuses the reserved range. A drained
Remove stops that alias from being admitted.

Registration requires actual same-account direct and companion CharacterLease,
other saved class3 mage, selected owner/selection/lifetime, actual canonical
provider binding/current task and original held row operation. It reads the
mage's already installed child RESOURCE through the existing document validator
and digest under the existing canonical lock. It adds no RESOURCE seed/writer,
fake Binding, or selected-player status substitution. `server_snapshot` rereads
that actual RESOURCE and registered placement/generation, not the prior actor DTO.

Placement is an explicit first-publication LOCAL policy: co-locate the new
Player at the actual owner's current map/grid, direction0. This grants no
occupancy/edge/movement authority. Complete Actor fields are constructed afresh
with the issued UID and actual saved name; Actor16 is true. Frozen mage DTO and
appearance producers validate the full fields and apply SPR734/1186. The full
SelfInfo used solely as codec validation context has actual INFO/local scalar
fields plus the four actual RESOURCE values; it is **not** called a current full
SelfInfo and is never emitted as 4E38. No self actor frame is copied/retagged.

Broker's exact parent05b93b8e has additive typed Player4E96/4E40 admission and
`allied_player_operation`. An already registered frame cannot use generic
`_send` without that typed operation. The original policy, writer.write,
writer.drain, checkpoint, queue-zero and policy sent-count path remains the
transport owner. Registry phases advance REGISTERED→RESERVED→WRITE_ATTEMPTED→
DRAINED at those actual source edges. Failed/ambiguous writes retain their
phase and spent UID; no receipt or ACK is fabricated. Existing self/NPC/Remove
branches remain outside the additive exact-identity branch. The existing
4E40 encoder is reused only as a common field1 wire encoder, never as NPC
registration/death authority.

## Honest lifetime results

Drained spawn returns an ActorSnapshot with `pose=None`; snapshot returns None
until a real original client lookup/pose producer exists. The controller can
remain AWAITING_POSE. MOVE refuses explicitly. Remove drain returns absent=False;
only a record positively never sent can return absent=True. Unknown/attempted
spawn and exact-world teardown remain unresolved and retain the lease. Closed
socket/server/new selection does not prove original lookup absence.

## Exact sources and integration boundary

`selection-delta.json` contains full parent/input/product SHA256 and sizes.
Main parents:

- Broker `scoped-product-router-integration-v2/broker.py`:
  `05b93b8ec8a625309ff9e25c0ddc45d676599d0b6667474548c0bf0b168006e8`.
- Root `npc-uid-issuer-integration-v1/item_uid_namespace_root.py`:
  `71efaa40aa2e14aed3637bb2cb03bb170572e81d7798fd571d8abc8691a5cf4c`.

The original non-allied character pin is preserved. Allied opt-in requires
the exact frozen v5 realm766310cb and its canonical character-state module,
because the old CharacterStore has no real companion lease producer. Two
parent diffs are adjacent. Exact original packet_peer/packet_server bytes were
copied beside the private Broker to retain the known neighbor/co_filename
contract; neither file was edited. This directory is not a runnable server SKU.

Root integration must select the existing v5 host/character/Factory/Broker
lifecycle descendants once, carry the sealed allied source through existing
same-account selected-scope Setup recreation, and add the one plain allied
module before root import. The supplied parent Broker alone does not install
CompanionHost hooks. The required inputs and existing cold-call signatures are
listed in selection-delta; no mutable runtime enable path is provided here.

## Verification and packet scenario

`python work/local_original_session/implementation-companion/allied-publication-source-v2/verify_source.py`
passed the fresh owner DTO boundary check and syntax plus the isolated Windows durable cursor's fresh/restart/discarded
attempt, exhaustion and wrong-policy preservation checks. No live root/lease/
registration/send receipt was mocked or claimed by that check. Actual changed
Broker/namespace hunks were inspected. `verification.json` states its limits.

`scenario.json` reuses packet-test-client-v5/API and the existing mage-scope
normal CREATE/WORLD/current/fresh caller and full-copy input manifest. Required
play order is normal login/roster→direct owner's actual WORLD/current→packetless
selection of a saved other mage→**actual user-triggered summon**→registered4E96
receiver/server current→actual dismiss→4E40 drain/absence distinction→original
client/server/Plan close with FIRST and partial saves preserved.

The first unconfirmed action is the actual summon input producer: existing
Host.command is reached by an unsupplied native ATS callback, not a known C2S
request. Calling the handler/controller directly or inventing that callback is
forbidden. A verified saved other-mage full account copy and coherent final
source selection are also not yet supplied. Therefore no misleading failure-only
run_feature.py/runtime command was added and no packet test was dispatched.
`test_ready` stays false. Root should retain these exact missing inputs rather
than reconstruct a scenario or claim registration/NativeUI/pose/absence PASS.
