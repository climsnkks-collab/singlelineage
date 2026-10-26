# Packet original WORLD Frame DATA API v3

Source/API component ready; **source_ready=true, test_ready=false, runtime=UNRUN**.
No ITEM carrier/context/action/caller/RUN or game/Store runtime is supplied here.
Root alone selects a coherent source graph and dispatches; Test alone executes.

Selected parent is frozen packet settings v1/v2, Hostd149 and the genuine Peer
accepted tuple. Realm `_world_frames` contains outbound S2C frames; original
Peer `_world` retains row/game/selection/mover/sent watermark only. Neither is
the original C2S WORLD decoder Frame. No suitable old retained input is reused
or mislabeled. Original `_world` tuple shape/identity and all old operations stay.

## Single Peer-owned original input

`packet_peer.PacketWorldFrameData` is an immutable DATA record, issued only by
the actual selected Peer. It is not a capability merely because it has that type.
The one private map `_world_input_frames` is owned by the same accepted Peer.

1. Original Broker decoder -> game handler -> response/drain calls the original
   Peer `drained(row,game,frame,replies)` with that exact Frame argument. After
   all original drain/WORLD guards and original `_world` tuple publication,
   this descendant retains **that object**, accepted tuple, row/writer/game/
   selection/mover/world tuple and original received ordinal. Frame construction,
   re-decoding, copying, retransmission and `_packet_frame` replacement are absent.
2. At the existing synchronous `complete_request`, outside the released row lock,
   only the actual original WORLD_DRAINED completion can seal that record once.
   It requires the same retained Frame to still be `row['_packet_frame']`, the
   same WORLD tuple and original ordinal, and no prior completion. The record
   retains the actual generated packet_completed dict identity and its bounded
   scalar/opcode signature. There is no new request/task/row acquisition.
3. Later F101 and other normal packets retain their original `_packet_frame`,
   progress, request-open/RECEIVED flags, current ordinal and completion behavior.
   They do not overwrite the separate WORLD input. A historical WORLD ordinal
   is never substituted for the current last-request ordinal.
4. Selection preparation retires a prior record. The ordinary drained edge
   retires it when the source game/selection changes, including successful
   Restart clearing selection. An error completion or actual close also retires
   it; close does so before callbacks. A stale retained object held elsewhere
   is never accepted as current by the map-backed getter.

Within a genuine issued PacketCurrent's **already held original** row scope:

```python
record = peer.world_frame_data_for(current)
```

This getter reuses original `check_current`, requires the original canonical
operation task/lock and exact issued current, then validates map membership and
same accepted tuple, writer/row/game/selection/mover/WORLD receipt. It requires
the original completed WORLD input Frame and ordinal (positive and no later than
the current policy ordinal), original WORLD_DRAINED completion and unchanged
completion signature. It returns that actual Peer-owned record. It acquires no
lock, performs no save, constructs no Frame/current/receipt and grants no claim.

## Existing LOCAL principal current data

Use the selected v3 `PacketSettingsIssuer.current_data_locked(principal)` inside
its existing original row operation, with the real server-issued LOCAL principal.
All v1 accepted endpoint/owner/lease/actor-generation and canonical checks remain.

| CurrentData field | Meaning |
| --- | --- |
| `world_frame` | exact original C2S WORLD Frame held in the selected Peer map |
| `world_frame_data` | same actual `PacketWorldFrameData` returned by the Peer getter |
| `world_received_ordinal` | original WORLD received ordinal, separate from latest request |
| `world_frame_availability` | `SOURCE_RETAINED_ORIGINAL_WORLD_FRAME` only after that real getter succeeds |
| `world_receipt` | unchanged actual Peer `_world` tuple; not a Frame or a new completion |
| `last_frame` / `received_ordinal` | unchanged actual latest `_packet_frame` / current policy ordinal (e.g. F101) |
| `provider_scope` | **existing field remains actual Binding (`provider._bound`)**, despite its historical name |
| `provider_owned_scope` | actual `binding.owned_scope`, same object as current `provider._scope` |

The original RootPlayers.operation already calls the provider's real
`_selected_current(binding)`, which validates `_scope`, task/thread, writer/row/
lock/peer, generation and actual owned scope. v3 reads that binding.owned_scope
and confirms it is the current provider._scope/nonNone. It does not create,
replace or reacquire a scope. All current data/scope use ends when the original
row operation ends; the original WORLD input itself survives only its selected
world lifetime. Do not relabel `provider_scope` Binding as e660's owned tuple.

## Remaining ITEM/Root boundary

This source removes only the previously missing retained original WORLD Frame
DATA and supplies the correctly named actual owned-scope DATA. It does not
implement Root e660 `CompanionItemCarrier.current_locked`, typed packet action
context/received_request/received_plan, semantic executor, direct router->sync
claims/await consume/terminal retirement, or read/select/prepare caller/RUN.
Those require the actual ITEM/Root source owners. A DATA record, historical
WORLD completion, F101 completion or nonNone scope is no request-open/RECEIVED/
ITEM claim, no allowed action and no successful read/select/prepare result.

Canonical class/level remain source-qualified require_current record facts.
Current form/appearance barrier, weapon barrier and pending-action snapshot are
still UNAVAILABLE. Native Host53b/UI input/render/fresh and effective combat are
separate. Original account-v5 Core86 source family and all other source pins are
preserved; this API does not join another Core/class space by inference.

Focused inverse/pin/syntax checks and pure signature metadata probes only are
recorded in verification.json. No original WORLD Frame, receipt or current was
synthesized for verification. Actual capture -> F101 -> getter/retirement remains
an unobserved runtime path, to be exercised by a separately completed Test caller.
