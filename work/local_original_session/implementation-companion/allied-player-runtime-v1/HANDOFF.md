# Allied Player runtime v1 — publication authority boundary

WRITER_RELEASED / SOURCE_ONLY / `test_ready:false` / runtime UNRUN.
This directory contains exact source evidence and the first missing producer.
No executable stub/registry, product mutation, queue, port, socket, Store,
Test copy, game or REA operation was created. Frozen sibling features and
common/Test sources were read only.

## Progress from prior inputs

The numeric LOCAL mage appearance and full DTO are available from the frozen
LocalMageDtoProducer and MageWorldSource. Their required inputs remain the
actual same-character canonical INFO/current RESOURCE plus independently issued
actor UID/current placement. Direct selected mage CREATE/WORLD source does not
issue a second live actor while its direct owner remains selected.

Existing REA216 confirms nonself Actor16=true with differing UID dispatches
48510→C24A0 Player; common MOVE and Remove consumers also exist. This is enough
to distinguish a real Player DTO from Monster. It does not establish live
registration, client pose or absence for this new companion.

## First exact missing server boundary

CompanionActorPort.spawn must publish the new Player via the existing sender.
The selected LocalRealm.validate_reply at broker.py1401 accepts 4E96 only when
it is the exact selected self world frame, or when _npc_spawns is nonempty and
_validate_npc_reply authorizes that exact NPC frame. Its alternative failure is
EXACT_LOCAL_WORLD_REQUIRED. There is no allied Player registration/delivery
owner in this source. PacketPeer consumes the same realm/Broker authority;
encoding bytes alone cannot create a current actor or authorize _send.

The NPC issuer's durable monotonic cursor 0x20000000..0x2000ffff is legitimate
but nominally tied to source_roster_combat/npc_client_recipe/NpcSpawn and root
foreign classification. Borrowing that cursor or renaming NpcSpawn would
publish a Monster authority as a Player. A fresh independent private counter
cannot reserve the shared account namespace against PCs/items/NPCs or provide
root foreign rejection. No new UID range was silently reserved.

Therefore no actor was issued or registered and no ActorSnapshot with claimed
spawn_drained was produced. Existing default prewrite refusal is preserved.

## Single next source contact

The root-owned LocalRealm needs one additive **allied Player registration and
delivery producer**, adjacent to its existing _validate_npc_reply/current
registration path, consumed by the existing _send. It must bind all of:

- Same-account real class3 canonical character lease and direct owner lease;
  exact current owner world/connection operation and no self UID copying.
- Shared-root reserved monotonic live UID distinct from PC/item/NPC domains;
  no rollback/reuse after attempted publication, plus fresh generation token.
- Frozen mage full DTO from that character's current RESOURCE and actual
  placement, Actor16=true, actual issued actor UID/name/appearance.
- Exact registered frame/operation identity, existing reserve/write/drain and
  COMMITTED/attempted/unknown distinctions. Server registration and confirmed
  client pose are separate results.

This is the first missing producer, not an existing method name or an invented
packet. Supplying it lets the implementation build the concrete actor port
against real owner code. A callback whose implementation does not exist, an
independent dictionary, relaxed validate_reply or fabricated receipt would not
complete this boundary, so none is provided as product implementation.

## Remove and teardown must remain truthful

4E40 exists and its original consumer is 4E700→61650, but current selected
validate_reply admits it only through the NPC death notification owner.
The existing NPC source explicitly marks drained Remove as a local tombstone,
not observed client lookup absence. v5 RemovalResult.absent requires actual
same-generation lookup absence or positive never-emitted proof. Merely draining
4E40 cannot release the canonical companion lease.

Likewise a closed socket, changed selected character, closed server or a new
world object does not prove the exact previous client world was destroyed.
retire_owner must consume that positive original lifetime proof. snapshot must
return actual source-backed client pose or remain unknown; server_snapshot must
read the registered current actor and its real RESOURCE under the existing row
scope rather than copy the previous ActorSnapshot. step cannot send until
current source-backed edge/occupancy/move authority exists.

## Future runnable and current limits

Once publication authority exists: normal login/roster/direct-owner WORLD ->
select an actually saved same-account other class3 mage -> existing controller
lease acquisition -> actual shared UID registration -> full4E96 send/drain ->
truthful server current; client pose may still be unknown/AWAITING_POSE ->
normal dismiss4E40 under the same operation -> real absence or exact teardown
proof -> lease release. First failure preserves pending/unknown state. No fake
summon packet, selected UID substitution or direct handler invocation is valid.

There is no runtime scenario/RUN_COMMAND while that authority is missing;
test_ready stays false. source-evidence.json pins eleven actual sources and
22 function spans; bounded AST/source inspection verified the exact current
self/NPC-only gates. Existing protocol/DTO successes are reused. No new
runtime/Factory/Store/packet/native success is claimed.
