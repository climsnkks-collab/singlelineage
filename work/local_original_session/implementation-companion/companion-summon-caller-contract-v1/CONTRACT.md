# LOCAL summon caller contract — source finding

**No legitimate packet summon sequence is supplied today.** The reviewed account-click graph contains the summon consumer and real Allied publication callee, but its incoming producer is the missing actual ATS interface callback. `test_ready:false`, runtime UNRUN. A generic packet sender cannot substitute for a missing decoder/route/encoder.

Source paths/hashes and exact method ranges are pinned in source-contract.json. Short labels below identify the selected files, not alternate implementations.

## 1. Confirmed entry and missing producer

Selected Host `companion-account-click-host-v1/companion_host.py`:

| Contact | Source line | Contract |
|---|---:|---|
| Bootstrap.attach | 235 | A supplied actual interface binds its retained hotkey to Host.open_from_hotkey. No global polling or packet is created. |
| open_from_hotkey | 433–441 | Resolves the actual writer/claim, acquires original row operation and opens the same panel. |
| _open_panel_locked | 485–493 | Requires non-None interface; calls interface.open(ATS, model, on_command=...) with captured actual selected state/ui_epoch. |
| _refresh_panel | 407–417 | Existing interface.render receives a new callback for the retained state/epoch. |
| command | 497–515 | Under original row operation, checks expected_state/ui_epoch, then action='summon' and values={'character_uid'} or {'character_uid','mode'} call the controller. |

**First missing producer:** the actual source-owned interface.open/render implementation that produces and retains that on_command invocation, or a separately established real inbound normal packet decoder/route/encoder reaching the same authorized command. Neither is supplied in this graph. Host:485 requires interface and emits `COMPANION_ISOLATED_ATS_WINDOW_CONTRACT_UNAVAILABLE` when absent. Original extracted v5 Host:333–350/354–372 uses the same interface/on_command/summon entry. Its tests directly call Host.command; that is a test seam, not a packet producer.

Selected Broker contains no summon or Host.command call. Its companion route is only `game.routes[0x4f13]`, Broker:1165–1174, invoking Feature.dispatch_locked. Feature:75–105 first requires experience_participant, actual by_lease PlayerRegistration, original root.current, DRAINED, same writer/lease/selection/generation. Feature:117–124 consumes the registered **actor UID**, opens the existing actor panel and returns an empty response tuple. It cannot create the first actor, accept saved character UID2 as an issued actor UID, or bootstrap a summon. No summon opcode or 4F14 response is established here.

## 2. Required normal ROOT / UID2 roles

The source-supported intent is normal KEY/VERSION/login/INFO → select actual ROOT UID1 via original4E28 → WORLD/current → retained panel chooses existing account mage UID2 → summon callback. Choosing UID2 in that panel is a companion target choice; no packet encoder for this choice/command is supplied.

Selecting UID2 through another4E28 is ordinary **direct** mage play. It does not summon UID2. Controller:405–410 and CharacterStore.acquire:311–318 require an existing class3 character different from the direct owner's UID, a current direct owner lease and no conflicting active role. With this saved account ROOT1/class0 and mage2/class3, direct ROOT1 can target mage2. Direct mage2 cannot summon itself or class0 ROOT1. There is no requirement to play UID2 first merely to acquire the already saved row/RESOURCE. Normal account scope/retirement must remain genuine whenever direct selection changes.

Host.selection_started:271–294 acquires the direct lease and constructs an EMPTY controller with real actor port. Host.current_owner:364–392 requires actual mover/position, selected UID, HP Resource status, alive owner and exact selected/player-life lifetime. A saved row alone is not this current owner.

## 3. Actual summon consumer to registration

Original v5 controller is exactly the selected controller bytes:

1. `CompanionController.summon`, controller:398–457: requires real nonclosed empty lifetime, live current owner, valid other class3 saved character UID. Optional mode is None or explicit FOLLOW. It obtains the genuine `role='companion'` CharacterLease owned by current direct lease with a new generation, re-reads canonical character under lease and validates movement preferences/map. Explicit FOLLOW updates those preferences through original expected-revision CAS; omitted mode uses saved settings.
2. controller:438 calls `await port.spawn(character,lease,owner)`; caller must not call this or Host.command directly.
3. `AlliedPlayerPort.spawn`, Allied:377–392, calls RootPlayers.prepare and stores actual record by lease. `operation`, Allied:99–135, checks registered same Setup/root/Host/Realm, current owner/direct lease/account, genuine companion lease and actual provider._bound/current task/selected binding/locked original row.
4. `RootPlayers.prepare`, Allied:264–302, reads live account Batch RESOURCE and scans live member collisions under original root/inventory/character/realm locks; it reserves a separate allied UID, derives actual saved mage INFO and original DTO projection and constructs the original4E96 wire. It creates a real PlayerRegistration with new generation, owner, lease, selection, row/binding and placement, inserts it in root.records and validates current.
5. spawn sends4E96 through original Broker._send with actual record/row operation lock, requires record.phase DRAINED and returns actual ActorSnapshot. Character UID2 and allocated server actor UID are distinct identities. Actual issuance, drain and captured generation must supply later click values; no fixed UID is a legal replacement.

## 4. Experience/current, response and Store boundary

`_publish`, controller:308–314, marks server-current and selects ACTIVE only when pose/motion permits; the present port returns pose=None, so publication normally yields AWAITING_POSE. `experience_participant`, controller:333–379, is a read-only eligibility query, not an actor producer. It requires retained actor/lease and ACTIVE or AWAITING_POSE, rechecks owner/current twice and reads exactly `port.server_snapshot`. Allied.server_snapshot:409–420 validates the real registration/generation/owner and reads live current RESOURCE; alive/same-map/drained are required. Pose is deliberately not an XP predicate. This does not establish movement, full active support, CAST, AI or UI success.

Host.command returns the controller's Outcome to its interface callback, then refreshes the retained panel. There is no supplied C2S summon request or matching S2C command reply. Only the source's actual4E96 publication and real drain/current state can establish emitted actor observation; no fabricated reply/panel success is allowed.

Summon does not seed SKILL or duplicate RESOURCE. Allied reads the one root account-v5 live RESOURCE participant, not child history/origins. Its original `_reserve`, Allied:219–261, uses distinct durable `allied-player-uid-state.json` plus lock, CAS/readback and monotonic burn; it does not reuse the account item cursor. Explicit FOLLOW may CAS saved character preferences. Any future actual trial must preserve those real Store/file deltas and raw first failure; publication/retirement/absence/clean close cannot be assumed from source. No Store or cursor operation ran in this task.

## 5. Runnable determination

Common packet-test-client-v5 `send_request`, client:393–403, validates actual ready_current and sends a supplied opcode/payload through existing server completion. It does not invent the summon route or retain interface callback state. Therefore no legitimate summon call can be emitted by a standalone packet caller on the supplied graph without directly calling handlers/Host/controller or providing a fake interface. No caller/RUN_COMMAND is supplied.

The reviewed graph also still reports explicit Scope actor-mode forwarding and Feature lifetime/interface blockers. They remain independent prerequisites; solving them alone does not create an inbound summon producer. This task does not modify any of those sources or reinterpret a setting click as summon. Source proof is8 focused static checks; zero product imports/objects/runtime/packets/ports/save writes.
