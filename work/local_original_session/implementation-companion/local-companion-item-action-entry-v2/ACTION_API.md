# COMPANION-MAGE ITEM/GEAR ingress v2 — product panel and packet paths

**WRITER_RELEASED / source_ready=false / test_ready=false / ui_ready=false / action_ready=false / runtime UNRUN / RUN_COMMAND=null.** This is a new immutable descendant of v1 manifest `e7b3611a6d9d2433769c24f8019219eebf25f6eb4a0784b42152e407f4adf9de`. V1 remains preserved. Its requirement to supply native section/render receipts for every ITEM call was too broad. Those receipts apply to the product panel branch only. Direct-packet tests require no native renderer, OPEN, panel, ui_epoch or fake UI receipt.

## Two distinct source-owned ingress contexts

`CompanionItemUiContext` retains `host, writer, row, state, ui_epoch, active, character_lease, actor, actor_generation, owner, panel, panel_open, native_open_receipt, native_items_receipt`. It is for the actual product panel branch: before actionable native row selection or write admission, the final selected interface checks current real settings OPEN and actual own-items section/render receipts for the same panel, current rows and epoch. A settings display publication or immutable inventory snapshot is not such a receipt. Data-only reads needed to populate a section remain reads, not action admission.

`CompanionPacketActionContext` retains **no native/UI fields**:

```python
carrier_source, carrier, received_request, received_plan,
session, direct_selection, world_receipt,
host, writer, row, state, active, character_lease,
actor, actor_generation, owner
```

The exact selected real packet carrier issues these observations only after normal session/login, character selection and WORLD completion, followed by actual request reception through the existing decoder/router. `received_plan` identifies the real carrier's source-issued received operation, not a future ITEM write plan. Owners validate the actual carrier issuer/SourceModule/methods, real session/writer/selection/WORLD, request and received-plan identity/current/consumption, original locked row/state, live active lease/actor/actor generation/owner connection and account, current item custody and Store CAS. There is no UI prerequisite in this branch. Public dataclasses, dictionaries, UIDs, hashes, caller-made instances or claimed type alone issue no authority.

`CompanionActionContext = CompanionItemUiContext | CompanionPacketActionContext` is a typing union. Each owner must select its validation branch from the exact nominal context type **and** its own verified source issuer/current. Subclass/duck-type fallback and dropping checks for an unknown variant are forbidden. No selected player's UID/frame may be relabelled as the companion, and no fake empty GearState may replace actual UID2/current.

## Exact interface and four synchronous owner callee signatures

Product interface signatures remain unchanged from v1, currently refusal only:

```python
async def open_items(self, *, panel, kind, character_lease, actor, owner)
async def select_item(self, *, panel, kind, rows, item_uid,
                      character_lease, actor, owner, ui_epoch)
async def item_action(self, *, panel, kind, selection, action, quantity,
                      destination, character_lease, actor, owner, ui_epoch)
```

The existing Host supplies no epoch keyword to `open_items`; the future actual interface recovers it from the identical current panel/state while the original row operation is held. Host does not yet route select/action. None of these methods is installed by this candidate.

Both source owners implement the following concrete `CompanionItemsCallee` API. **V2 changes keyword `ui` to `context` and adds `kind` to observe**; don't combine the v1 and v2 call signatures.

```python
def read_items_locked(self, *, context: CompanionActionContext,
                      kind: Literal['inventory','equipment']) -> object
def select_item_locked(self, *, context: CompanionActionContext,
                       kind: Literal['inventory','equipment'],
                       rows: object, item_uid: int) -> object
def prepare_item_action_locked(self, *, context: CompanionActionContext,
                               kind: Literal['inventory','equipment'],
                               selection: object,
                               action: Literal['use','equip','unequip','transfer'],
                               quantity: int, destination: object | None) -> object
def observe_item_action_locked(self, *, context: CompanionActionContext,
                               kind: Literal['inventory','equipment'],
                               plan: object) -> object
```

`CompanionPacketActionEntry` exposes those exact four synchronous signatures with the narrower `CompanionPacketActionContext` argument. It currently refuses with `ItemPacketUnavailable(reason='COMPANION_ITEM_ACTUAL_PACKET_CARRIER_SOURCE_UNAVAILABLE', plan_issued=False, action_admitted=False, saved=False)` before accessing context, issuing a plan, calling a callee, sending a packet or touching Store. It is neither a handler/router nor a carrier. It does not implement the Protocol by dispatching to a direct handler. `CompanionItemActionEntry` remains the separate native-branch refusal candidate. `kind` is exactly inventory/equipment. `item_uid` and positive quantity are exact int, not bool. Transfer destination must eventually be an owner-issued live same-account destination, not a UID/mapping; nontransfer destination is None.

ITEM owns canonical inventory, custody, quantities, Use/transfer and actual persistence. GEAR owns actual companion GearState/current, Equip/Unequip and slot effects. Each publishes its selected source module/path/SHA, exact methods and nominal rows/selection/plan/result classes to Root. `object` return annotations deliberately leave those token classes to their owner; this contract does not mint substitutes. All four calls remain synchronous in the existing operation; no network await or recursive row acquisition is inserted.

| API | Owner result and required meaning |
| --- | --- |
| read | Immutable nominal rows receipt for exact actual companion/account, inventory or Gear current revision/frame digest and issuer/current; UI branch also relates display generation/epoch, packet branch relates actual received read operation. No write authority. |
| select | Owner-issued nominal selection tied by identity to current rows/item UID/Q/custody and revisions. Packet selection follows actual received carrier input; no render is needed. Selection consumes/writes nothing. |
| prepare | Owner-issued one-use action plan tied to selection, exact action/Q/destination, live admission and original Store CAS. No plan is issued until an actual selected carrier/consumption route is supplied. No mutation/send/save occurs merely by preparing. |
| observe | Nominal current/terminal result for that exact plan and branch: actual received original request, decoder/router processing, response, canonical item/Gear effect, actual Store persistence/readback/fresh restore as applicable; preserves the original first error/partial/unknown. |

## Normal packet execution and honest outcomes

Packet testing performs normal login → character selection → WORLD → source-owned received read → row selection → prepare/admission → original request handling → response/state/save observation. Local no-wire selections are recorded as such and linked to the next real request values. The exact companion carrier/opcode and source issuer are currently missing, so this sequence is a contract, not an executable new route or claimed success.

When prepare is called from the received operation itself, the actual existing router must own subsequent consumption at its original processing edge; no recursive handler call is introduced. When a native branch prepares a future outbound request, the normal sender waits until the Host row operation releases before sending; the actual decoder/router then rechecks live plan/current/custody/CAS under its original operation. The selected source family must state which edge it implements. No invented opcode, synthetic session, direct handler invocation, forced owner/current state, PC UID relabel or ownership/CAS removal is permitted. Renderer absence is not a packet failure or a reason to manufacture a native receipt.

`UNAVAILABLE` is returned only before an action/plan was issued because the real route/source was absent. `PENDING` requires actual retained issued work. After possible emission or mutation, timeout, missing response, disconnect, epoch/current retirement, owner stall, indeterminate persistence or uncertain consumption stays `UNKNOWN` or the original failure, retaining plan/raw/partial evidence without retry/rollback/clear. Packet mode never manufactures native evidence. OPEN, rows, selection, prepared plan or transport-return alone cannot mean COMMITTED/SAVED. Save uses the original owner transaction/Store contract, never an extra UI save file.

## Exact first blockers, pins and verification

Packet branch first blocker: **no actual selected companion action carrier source/received-plan issuer/decoder-router consumption edge is supplied**. ITEM/GEAR may implement their source-owned two-variant validation/read/current/custody/CAS APIs now; this candidate issues no action plan meanwhile. Native renderer work is not a dependency of those packet APIs/tests.

Panel branch first blockers remain the unselected own-items section/control/receipt route plus source compatibility: accepted readonly port manifest `963a446e22eb59b27d337b8319aa7ef0ac729b682a13d8199eed8bc0b03c2dbc`, source `c9c7c088f77587dd0207eae6e24685552c817b5d0831a13a083021ed27b51a04`, hard-pins Host `5c56104199997441567e7078b8e3f9fc9f8f2e22fd18d39fffc737d489d02731` and Core `86c0d7d13a9649840cc875c8368b96d9ef698c02dd1241fcd1998063be14c0e9`; LOCAL-open Host `d16376c297b008e27f999fa3ddc6b57df6f6df4693ccbc263d1334deaaad6da8` differs. Native owner-v3 own-items controls are disabled. No literal/guard was changed. Full original/parent paths, lengths and hashes are in `input-pins.json`; new source hash is in manifest/HANDOFF.

Read-only post-final `python -B .../verify_readonly.py` checks exact pins/new in-memory compile, seven entry signatures, packet context absence of native fields, local panel refusals/quantity rejection and packet refusals without a renderer. It proves schema/refusal only, not authority or a received packet. No live Host/Store/native fixture, game, Test, ports, focus, Store copy, original/common/client/API/queue/ACTIVE edits, branch/worktree or commit. Only this new private folder is owned. Main reviews/supplies/queues; writer and execution resources are released.
