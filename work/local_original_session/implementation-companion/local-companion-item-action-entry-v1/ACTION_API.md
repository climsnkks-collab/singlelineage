# COMPANION-MAGE own ITEM/GEAR action ingress candidate

**WRITER_RELEASED; source_ready=false; test_ready=false; ui_ready=false; action_ready=false; RUN_COMMAND=null.** `companion_item_action_entry.py` defines a concrete typed coordination contract and an uninstalled refusal entry. It does not implement the final native interface. Every well-shaped entry returns `ItemUiUnavailable(status='UNAVAILABLE', action_admitted=False, saved=False)` before any read/callee/native/packet/Store operation. Its `native_opened=False` means this result supplies no OPEN evidence; it is not a statement about another window's actual state. Existing reads/PASS remain reusable within their original scope.

## Exact first blocker and source compatibility

The accepted inventory read port `local-companion-items-panel-port-v1/manifest.json` is SHA256 `963a446e22eb59b27d337b8319aa7ef0ac729b682a13d8199eed8bc0b03c2dbc`. Its `companion_item_target_view.py` is `c9c7c088f77587dd0207eae6e24685552c817b5d0831a13a083021ed27b51a04`; it hard-pins old Host `5c56104199997441567e7078b8e3f9fc9f8f2e22fd18d39fffc737d489d02731` and Core `86c0d7d13a9649840cc875c8368b96d9ef698c02dd1241fcd1998063be14c0e9`. Its constructor also pins the actual final interface's `open_items` function/code and its read requires a direct synchronous call from that exact method while the original Host owns the row operation.

The later LOCAL click-open bridge Host is `d16376c297b008e27f999fa3ddc6b57df6f6df4693ccbc263d1334deaaad6da8` and `companion_local_open.py` is `3b1c8604ac05e019166f9489d13dad7fe3d4fff9774e5f7649fc9d295353b86e`. They require a selected, exact `NativeOpenEndpoint` and real typed receipt. The old read-port constructor refuses this different Host; this candidate does not weaken or replace the literal. Native `local-ui-panel-owner-v3/ui_owner_panel.hpp` has actual owner-window/paint primitives, but own equipment/inventory is disabled and no item rows, selected-row input, item-section receipt or item action transport exists. A settings-window OPEN alone does not establish an inventory/equipment section OPEN/render. Therefore no safe final action entry can be enabled now. A paired, selected Host/native-section/interface + ITEM/GEAR source family must close these exact edges. Full absolute paths, lengths and hashes are in `input-pins.json`; no sibling was edited.

## Concrete final interface surface

These exact candidate signatures are implemented in the Python file, with refusal only:

```python
async def open_items(self, *, panel, kind, character_lease, actor, owner)
async def select_item(self, *, panel, kind, rows, item_uid,
                      character_lease, actor, owner, ui_epoch)
async def item_action(self, *, panel, kind, selection, action, quantity,
                      destination, character_lease, actor, owner, ui_epoch)
```

`kind` is exactly `inventory|equipment`; `action` is `use|equip|unequip|transfer`. Positive `quantity` and `item_uid` are exact int, never bool. Native rows select the owner-issued actual item UID; a row index, display label, item template ID or arbitrary client UID is not custody. `destination` is None for use/equip/unequip. Transfer requires an owner-issued current destination object identifying an admitted same-account member/custody; a numeric UID or user mapping alone is insufficient. No guessed companion packet/opcode is defined here. These callbacks are not yet routed by Host.command: its existing inventory/equipment branches call only `open_items`. A future source-owned selected-row ingress must route select/action separately through the same live row operation and actual native controls.

The current Host caller intentionally supplies no epoch argument to `open_items`. The final interface must find the single state whose panel is the identical object, then recover its original ui_epoch and active objects inside that current Host operation. It must not add an epoch parameter and silently break the existing caller. For later callbacks the native section retains that exact epoch and source-issued rows/selection. No callback may infer epoch/generation from an integer or revive it after resummon, dismissal, actor generation change, section redraw, scope change or close.

## ITEM/GEAR callee contract owners can implement independently

`CompanionItemsCallee` is a typing Protocol only, not a duck-typed runtime admission API. ITEM owns inventory/custody/quantity/transfer/Use and canonical same-account writes. GEAR owns actual companion GearState/current, slots and Equip/Unequip. Final composition selects each exact source and its owner-published nominal result types. It must never initialize a pretend empty GearState or replace the selected direct player's UID/frame. ITEM and GEAR publish exact source module/path/SHA and method/result class names to Root; unavailable callee pins stay null in this artifact.

```python
def read_items_locked(self, *, ui: CompanionItemUiContext,
                      kind: Literal['inventory','equipment']) -> object
def select_item_locked(self, *, ui: CompanionItemUiContext,
                       kind: Literal['inventory','equipment'],
                       rows: object, item_uid: int) -> object
def prepare_item_action_locked(self, *, ui: CompanionItemUiContext,
                               kind: Literal['inventory','equipment'],
                               selection: object,
                               action: Literal['use','equip','unequip','transfer'],
                               quantity: int, destination: object | None) -> object
def observe_item_action_locked(self, *, ui: CompanionItemUiContext,
                               plan: object) -> object
```

`CompanionItemUiContext` fields are `host, writer, row, state, ui_epoch, active, character_lease, actor, actor_generation, owner, panel, panel_open, native_open_receipt, native_items_receipt`. They retain original object identities only. The dataclass is public data, **not authority**; constructing one does not authorize any callee. Owners must recheck their own exact original source issuer, live Host row/state/selection, same epoch, exact active identity and `controller.is_current(active)`, exact lease/actor/actor.generation/owner, owner connection/direct account and actual native current receipts. Do not trust nominal context type alone. No current binding is retained in a numeric DTO or supplied by JSON. All four methods are synchronous inside the existing row operation: no await/network/row reentry may split admission checks.

Return contracts to be implemented by source owners (the `object` annotations intentionally do not invent owner token classes):

| Method | Required owner-issued result and limits |
| --- | --- |
| read_items_locked | Immutable owner nominal rows receipt with kind, actual companion/member UID, same canonical account, actual inventory or GearState/current revision and frame digest, source identity, and same native section/epoch. Data only; no write authority. Gear absence returns unavailable, never zero equipment. |
| select_item_locked | Owner-issued nominal selection linked by identity to those current rows, actual item UID/current quantity/custody and current canonical member/gear revision. Stale or absent UID refuses. Selection does not consume/write/save. |
| prepare_item_action_locked | Owner-issued nominal one-use plan/admission bound to that selection, exact action/Q/destination and expected canonical inventory/Gear/current revisions. Checks actual item eligibility and custody. No mutation, packet send, save or optimistic PASS. Missing route is UNAVAILABLE before plan issuance. |
| observe_item_action_locked | Owner-issued nominal terminal/current result for the identical plan: received original request/decoder-router handling, actual response, canonical quantity/custody/equipment delta and save/readback/fresh restore evidence as applicable. It must preserve actual first error, pending/unknown and original partial state. |

The interface may show `PENDING` only for actual retained issued native/packet work. `UNAVAILABLE` means the required route/section/callee was absent before admission, with zero action sent. Once anything may have been sent, timeout, owner stall, missing response, stale epoch, disconnect, indeterminate write or failed save is `UNKNOWN`/the original failure, never `UNAVAILABLE` as proof of no write, never automatic retry/rollback. OPEN/read/render/plan/transport-return alone is not `COMMITTED` or `SAVED`. A section receipt must prove its actual same current native owner window plus native section generation/render and source-issued displayed rows; a settings display Checkpoint or read snapshot is insufficient.

## Normal packet execution boundary

`prepare_item_action_locked` is deliberately a prepare-only admission API. A future selected native/normal-session sender must consume the exact plan after the original Host row operation has released; it must not recursively send a normal packet and wait while holding that lock. The original decoder/router reacquires the normal operation and the owner validates live plan/current/custody/CAS again before mutation. A selected companion action carrier/consumption edge is not provided here. No new game opcode, direct handler call, synthetic session or selected-profile substitution is authorized by this Protocol. Owners can implement read/selection/write-admission/current and receipt types now without guessing UI; the real packet carrier/source selection is still an explicit missing dependency. Save remains the actual owner's existing transaction/Store contract, not an extra UI file write.

Inventory/equipment rendering must first use an actual section open/render receipt; for a future native section that needs rows before painting, a separately owned data-only read may prepare immutable rows, but no `CompanionItemUiContext` with admitted action or fake rendered receipt may be minted. Its API must be published by the owner rather than bypassing the original direct-interface read-port guard.

## Verification and ownership

`python -B .../verify_readonly.py` checks exact artifact/input pins, compiles only the new module in memory, checks signatures and executes only its local refusals/shape rejection. It creates no real source Host, native receipt, session, ITEM/GEAR authority or Store fixture. These checks prove refusal/schema only; packet/runtime/UI/save remain UNRUN. No game, ports, focus, Store copy, original/common/client/API/queue/ACTIVE write, branch, worktree or commit. Main reviews and supplies this coordination contract to ITEM/GEAR; this worker does not message those user chats or enqueue.
