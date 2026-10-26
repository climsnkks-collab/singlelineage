# Allied removal-only sealed RESOURCE reader v1

WRITER_RELEASED. Component source candidate supplied; test_ready:false; runtimeUNRUN.
No Core/Resource/ITEM/Broker/Host/Factory/caller/queue/public selection is changed.
Exact own parent Allied74053112d7ea75fe654b82ed9a335a721cd1fe1bd4c91bd2b282d8d6c55c17b7.
Mandatory COMBAT same-frame-resource-removal-v2/API.md8f03fce2 was read fully.
Full input and resulting candidate identities are in pins.json / manifest.json.

## Concrete source-owned API

`RootPlayers.begin_removal_resource_read(record, wire) -> RemovalResourceRead`

Call inside the genuine NEW later selected row operation, AFTER original Allied
`send_phase(..., RESERVED)` and current checkpoint, BEFORE Resource parent registration
and BEFORE policy.begin_write. `record` is the original drained PlayerRegistration;
wire must be `record.removal` with original npc_death.validate_frame result
(0x4e40, record.uid). Retained publication Binding is never changed or reused.
The fresh binding must differ from selected_binding but retain generation/writer/UID/
row/operation-lock/selection and live direct+companion leases via removal_current.

The issuer invokes original nonpending removal_current/_resource, original status.current,
and original Store._current under the original Store/character/realm locks. It captures
actual companion RESOURCE row bytes/revision/digest, actual Store._raw, exact path,
selected binding, pre-registration direct status Snapshot, actual source/provider/Store/
locks/Root/Setup and wire/policy/sent/transport/task/thread/registration identities.
No publication resource_digest is substituted as authority. No account dictionary is
returned to a caller, no arbitrary UID argument exists, and no current is fabricated.

`RemovalResourceRead.attach(parent) -> None`

Call synchronously AFTER the genuine Resource `SameFrameResourceCurrent` parent has
been registered as hp._same_frame_current AND its original Core native projection cap
has been returned, still BEFORE begin_write. This method admits only the exact class
from the selected ResourceOwner module, its actual registered parent, original native
DeliveryCapability, current binding, one exact removal wire, task/transport/thread and
captured policy/sent/preimage/Snapshot. It runs original Core `_delivery_current` at
BEFORE_WRITE_CHECKPOINT and original live removal_current/status.current again.

Required COMBAT continuation: preserve the existing nominal SameFrameResourceCurrent
class/consume/validate_snapshot/native owner-dispatch path, adding its distinct typed
removal proof/issuer. Its removal proof must use the captured BEFORE-registration
Snapshot and fresh binding, preserving the drained publication selected_binding as an
immutable separate anchor. The own Allied read does not prescribe a foreign producer
name and does not claim existing Resource255 accepts removal: it does not.

`RemovalResourceRead.validate_pending(record, binding) -> True`

This method is called by Allied removal_current ONLY when the actual row policy opcode
is 0x4e40. It consumes only the issued read already indexed by this RootPlayers and
registered original record. It requires attached actual Resource parent/cap still in
DRAIN_PENDING, original publication DRAINED, removal RESERVED or WRITE_ATTEMPTED,
exact binding/selection/row/lock/writer/wire/transport/task/thread and unchanged sent.
The original RootPlayers.operation (including real Host.current_owner/status.current,
original provider._selected_current and direct+companion require_current) STILL RUNS
before dispatch and twice within this method. The foreign Resource parent supplies the
original direct-UID Snapshot through native cap validation; Allied never manufactures it.

Under original locks, native Core `_delivery_current(..., DRAIN_PENDING)` validates
actual cap registration, original owner callback, source/Store state and disk/preimage,
selected current, exact wire/index/transport/task/thread/phase/drain/sent. The own seam
then requires Store._raw and native raw equal captured preimage, exact captured linked
RESOURCE row bytes/revision/digest and unchanged actual direct status Snapshot.
It never calls Store._current, provider.current or ordinary _resource while pending.
The Core BATCH_PENDING_TRANSPORT_REFUSED guard is unchanged. This native validated
whole-preimage comparison is used only to validate the previously admitted concrete
linked row; it grants no linked Binding, participant capability or account-current API.

The Resource validate_memory callback must remain original native validation of its
own typed parent/proof. Do not recursively call Allied.validate/removal_current or this
reader from the native owner callback: Allied calls the existing native validator.

`RemovalResourceRead.retire() -> None`

Always retire from original sender/Resource finally, including failed parent issuance
or attach. Read retirement is current-free and does not retire the native cap itself.
Retire native parent/cap with the original Resource cleanup too. RootPlayers.close also
releases retained read slots; no ownership/absence claim is made by either cleanup.
Do not leave a read indexed after failed construction or reuse it for another operation.

## Required original sender sequence (foreign; not implemented here)

1. Original fresh row checkpoint / Allied RESERVED; capture read.
2. Capture direct Snapshot BEFORE parent registration (reader does this normally).
   Resource removal issuer creates its typed removal proof using that same actual
   Snapshot, then original native cap/open_projection_read and `read.attach(parent)`.
3. Original policy.begin_write; parent.consume(BEGIN_WRITE) BEFORE Allied WRITE_ATTEMPTED.
4. Original pending boundaries use parent.consume(DRAIN_PENDING); Allied validation
   then admits only the exact sealed pending4E40 read instead of Store._current recursion.
5. Original policy.drained; parent.consume(AFTER_DRAIN) immediately BEFORE Allied DRAINED.
   Nonpending removal_current returns to original _resource; the pending reader is not
   used to authorize a new phase or a future request.
6. Original finally retires parent/cap and read current-free on success or failure.

The candidate exposes no public snapshot property: the Resource issuer must obtain its
own original status.current normally BEFORE registering its parent, and attach verifies
identity with the Snapshot captured by this reader. No getter or synthetic snapshot is
needed. Capture and parent issuance remain synchronous in the same task/locked operation.

## Review/limits

Ordinary _resource/operation/current/for_frame/validate/send_phase and AlliedPlayerPort
are exact parent AST. Only RootPlayers init, removal_current pending dispatch and close
change, plus the new nominal read API/types. Original PlayerRegistration is unchanged.
Focused 20 source/negative checks PASS; no positive pending runtime is manufactured.
Resource255 remains spawn-only; source-ready graph/updated exact Allied SourceSeal,
Resource removal descendant/native proof, sender/finally/direct pins and caller selection
remain foreign integration work. Existing actual103/111/116/125 failures/partial state,
UID burns and preserved Store files are unchanged. No runtime, copy, game, port or REA.
A drained4E40 remains absent=False; retire_owner=False / Controller UNKNOWN / retained
lease. No native actor absence, clean restart/quit, cleanup or gameplay PASS is claimed.

Verify only: `python -B work/local_original_session/implementation-companion/local-f101-removal-pending-resource-reader-v1/verify_focused.py`.
