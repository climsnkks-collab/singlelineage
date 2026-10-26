# LOCAL packet companion settings candidate

PRIVATE / WRITER_RELEASED. source_ready=false, test_ready=false, run_ready=false,
ui_ready=false. Runtime sidecar issuance, game, CAS and Store calls are UNRUN/0.
Root's explicit readiness decision applies even though the source connector and
candidate caller exist. Root alone reviews/selects; Test alone executes/copies.

`companion_packet_settings.PacketSettingsIssuer(server=actual_packet_server,
source=actual_SourceModule, client_source=actual_packet_client_SourceModule)`
is the sole issuer. `await issuer.open_for(original_PacketFlowClient)` admits
only the original client class, normal WORLD_DRAINED flow and the inverse
client/accepted socket tuple. It requires genuine server-issued current, account,
original held canonical operation, real F101/one 4E96 DRAINED completion and
current server actor/owner/direct+mage leases/generation/registration. No numeric
UID, supplied row, native epoch, UI click or caller-created principal is admitted.

The selected Peer itself retains its existing `_accepted` tuple, the exact
principal object and random nonce, issuer and live LOCAL endpoint/transport.
It rechecks those at each action. One endpoint is issued per actual accepted
writer, including after channel UNKNOWN/CLOSED; the once marker retires only
when the real packet session closes, whose accepted authority then also retires.
The Peer closes and joins the issued LOCAL channel on actual session teardown.

The anonymous OS socketpair is a **separate LOCAL capability channel** transferred
to the trusted packet runner. It opens no public listener and adds no original
game opcode. Socketpair construction is deferred until genuine admission.
No 4F02, LRS1/native UI key, click overlay, Store seed or Host.command is used.
The initial preferences/revision and every command/result cross authenticated,
length-framed JSON bytes (maximum2048B; real IO timeout2s). Independent request
and result HMAC domains, exact principal, monotone sequence and one in-flight
action reject forgery/reflection/replay. Credentials and nonce are not logged.

After opening:

```python
initial = await channel.receive_initial()  # authenticated revision/current values
saved = await channel.command(mode='ASSIST', engagement_distance=1,
                              expected_revision=initial['revision'])
await channel.close()
```

`decode_settings` is the actual shared settings decoder. It accepts only explicit
PASSIVE/ASSIST/DEFEND and distance1..8 with exact expected revision. The server
uses one existing Broker `_row_operation`, authenticates current principal again,
then `apply_settings_locked` consumes only that exact decoded command in the
channel server task. Existing `companion_combat.save_settings` calls the original
CanonicalCharacterStore CAS/atomic writer; genuine persisted `require_current`
readback must equal the exact mage combat-preference/revision delta before a
PREFERENCES_SAVED result is serialized. Source code preserves every other field.
No damage, attack, ITEM, RESOURCE, movement-mode writer or target is implemented.

`channel.report()` retains both original server and peer errors, burned sequence,
CAS_STARTED / CAS_RETURNED_READBACK_UNCONFIRMED attempts and positively observed
readbacks. UNKNOWN forbids another command or reissue. A returned CAS or positive
readback is retained if later publication/close fails; it is never rolled back,
replayed or renamed an authenticated peer success. Actual partial files remain.
PREFERENCES_SAVED describes persisted preferences, never effective combat/UI.

## Source-owned current data API

Within a fresh **original** `broker._row_operation(principal.writer,principal.row)`:

```python
data = issuer.current_data_locked(issuer.principal)
```

This requires the exact retained principal, live issued channel and source Peer,
current world/selection, original row/provider scope, real registration/actor
generation and same direct/mage leases. It returns genuine objects, not JSON
capabilities or a request-open/consume claim. Validity ends with that row scope.

| CurrentData field | Actual provenance / limit |
| --- | --- |
| packet_current, game, row, selection | selected Peer.current_for, actual accepted writer and registry |
| world_receipt | genuine Peer `_world` tuple (row/game/selection/mover/sent watermark), **not a WORLD Frame** |
| last_frame | actual retained `row['_packet_frame']`, exact original decoder Frame; at issuance it is F101 |
| last_completion, received_ordinal | actual matching packet_completed / policy.received; copied read-only metadata |
| provider_scope | exact current original canonical provider `_bound`, valid only in held operation |
| owner, lease, registration, actor_generation | current controller server participant / actual RootPlayers operation and original binding generation |
| character | source-qualified canonical require_current record from RootPlayers.operation; class=`['class']`, level=`['progression']['level']` |
| world_frame | None: selected Peer has replaced `_packet_frame` with F101 and does not retain original WORLD Frame |
| request_open | false; latest completed packet data grants no request-open/RECEIVED/claim/consume authority |

Original WORLD Frame is **UNAVAILABLE** after F101. The current API consequently
does **not** complete ITEM pending-action read/select/prepare's required original
WORLD Frame input. Never reconstruct one or call an issuer with synthetic input.
Source-qualified class/level are canonical record facts only. Current form or
appearance transformation barrier, weapon barrier and pending-action snapshot
are **UNAVAILABLE** in this source. Spawn4E96 sprite is not current form evidence.
No missing attribute, normal-form default, empty pending snapshot or alternate
ITEM source is supplied. ITEM/Root action integration remains separate/unready.

Future native UI may reuse this real decoder and the same existing canonical
combat writer **only after** its actual Host53b native OPEN/input/current boundary
and exact coherent source binding are independently complete. Packet principal
or preference-save success supplies no native display/epoch/click authority.
The packet `apply_settings_locked` method itself is intentionally server-task
and packet-principal scoped; do not call it as a fake UI input or test success.
