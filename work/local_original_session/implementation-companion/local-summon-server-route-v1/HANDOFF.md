# LOCAL saved mage summon inbound route — source only

WRITER_RELEASED / RUNTIME_UNRUN / test_ready:false. This directory alone is owned by the route worker. No common source, original input, profile copy, client/API, socket, listener or process changed.

Exact parent is accepted Test87 source manifest `companion-account-actor-reader-family-v4/manifest.json` SHA `b22b20ab309392d6bc1fe78106fde01d58ce3da792c444fc0d4b81b0680eba64`. Parent Broker11a6/Peer8d71/Servereed8 source hashes and actual product hashes are in `parents.json` / `manifest.json`. Parent successful MAGE→ROOT_FRESH restores are reused; those passes did not summon an actor.

## Real request and response

Explicit LOCAL C2S opcode `0xF101`, empty payload, no UID/mode/token. This value is absent in all 204 exact selected87/dependency source paths; its assignment is local, without any claim about the original client's unexamined opcode space.

Use the original same WORLD TCP connection, original sequence counter and original C2S header `<HIHH>`. Shared packet-test-client-v5 present_disabled framing produces an exact 10-byte request for empty payload. Do not open a second connection or borrow another connection's sequence/session. No original-game opcode is reinterpreted.

`local_companion_summon=False` is the default for both PacketServer and PersistentBroker. The final selected caller must explicitly pass True before prepare/start. It flows through the existing constructor into `_TransportPolicy`, whose existing checkpoint/stage/bootstrap/drain/rate checks allow only this exact 10-byte opcode. The existing LocalRealm.grant installs its handler before the unchanged terminal guard. The original decoder, `_serve`, `game.received` and canonical `_row_operation` dispatch it. The route does not reacquire the held lock.

`PersistentBroker._local_companion_summon_locked(writer,game,payload)` checks original same Host/realm/broker, actual current registered game, selected account and canonical operation. Packet mode additionally checks the actual WORLD_DRAINED PacketCurrent and actual open request. It calls exactly once:

    await host._summon_from_local_hotkey_locked(writer, row)

The Host helper from `local-hotkey-host-binding-v1/companion_host.py` SHA `f361027d98051d105871b2f4561204103df1bd0a824642ca9c7bb67c0a0bd234` chooses the unique other saved class3 mage from the current account, preserving actual direct lease/generation, saved movement/support, controller.summon, Store/CAS and original Allied publication. The route has no hardcoded character UID or class for the direct player. Its nominal imported CompanionHost and Outcome must come from that same selected graph; no mock/alternate class space is accepted.

AlliedPlayerPort.spawn emits the existing real 4E96 through original Broker._send and requires its registered record phase DRAINED. The new route returns `()` and emits no additional ACK. Existing PacketPeer.reply_drained records that actual side-effect response, so completion_status is REPLIES_DRAINED when the actual response list is nonempty even though the handler returns no unsent replies. Native client sees the original 4E96 actor message. No new S2C local-result opcode or native refusal dialog is introduced.

The actual row keeps one `local_companion_outcome` dictionary and only this request's original progress optionally carries `local_companion`. Completion copies that primitive diagnostic into its existing receipt. It records original Outcome status/reason and actual actor/character UID/spawn_drained. AWAITING_POSE means the actor was sent, with original pose still unconfirmed; it is not ACTIVE, UI, input, movement or AI proof. REFUSED is converted to the original reason ValueError, while preserving the semantic REFUSED record. Exceptions remain exceptions, including original type/text; pending/unknown actor, Store and lease are not cleared or retried. PacketPeer's existing ERROR and first-failure behavior is unchanged. The v5 CompletedRequest preserves extra receipt keys without any common client change.

## Exact integration work remaining for the parent

Select all three product rows (`broker`, `packet_peer`, `packet_server`) from this same directory. Peer.bind uses its sibling broker path; selecting only Broker or an old identical Peer path is invalid. Select the exact new Host above. Update both captured ActorCallbacks source triples in the parent actor_config: Broker path/hash and Host path/hash. Regenerate the actor_config selected row after these two replacements. Preserve the other 15 callback triples, all original Factory.bind_companion captures and all other selected rows. Update Setup.broker_source and original_update_sources using the same new Broker SourceModule, as the original source_loader already does. Do not alter Store/Core/Root pins or install an alternate owner. Final cohort/caller/manifest selection is owned by the parent; this worker leaves those published files untouched.

The parent can reuse the accepted caller's normal packet-test-client-v5 session without any new wrapper:

    # Final caller creates the selected PacketServer with
    # local_companion_summon=True, then enters the ordinary ROOT WORLD.
    client.packetless_step('LOCAL direct-summon hotkey intent', next_opcode=0xf101)
    completed = await client.send_request(0xf101, b'')
    # Inspect actual completion.status, all actual frames, original first_failure,
    # completed.receipt.get('local_companion'), and actual server/Store state.

This snippet is an integration contact, not a runnable standalone scenario. No runtime RUN_COMMAND is claimed: final selected cohort, repinned actor_config, accepted whole input recipe and final caller are not authored here. `SOURCE_VERIFY_COMMAND` in manifest runs only syntax/AST/collision/codec checks. Native hotkey event→same-connection sender ABI remains the parent/REA work; packet send success cannot close that ABI or native keybinding.

## Normal packet scenario to complete in the final existing caller

1. Test alone creates a new exact whole-seven-file input from accepted actual55/87 provenance. Preserve original failed82/83 and other independent test copies. Do not merge saved fragments or create/modify a mage to fit this trial.
2. Normal bootstrap/KEY/VERSION/login→actual roster→packetless received ROOT row selection→4E28→actual ACK/MAP/SELF/ACTOR/RESOURCE drain→ready_current. ROOT UID1 and saved mage UID2 are expectations for this input only; authoritative identities come from actual received selection and current saved account.
3. Record the packetless LOCAL hotkey intent. Send exactly one empty F101 with shared v5 send_request on that same authenticated WORLD stream. A previous response/current must be accepted before sending.
4. Record actual received ordinal/ERROR or REPLIES_DRAINED, every actual frame and local_companion outcome. For success require original Allied DRAINED 4E96, its real character/actor UID and current same-owner lease/generation, and actual actor decode/readback; allow AWAITING_POSE as a bounded spawn outcome, not pose/AI success. On first failure preserve raw error, last success, partial Store, UID burn/pending and retained lease without retry/reset.
5. Inspect only relevant Store/resource/preferences changes, then use existing strict close/FIRST/preservation machinery. Fresh restore follows only if original close is truly clean. Do not call Host/controller/route directly from the scenario.

## Existing lifecycle limitation must remain visible

Alliedd149 `remove` lines426–442 sends real 4E40 but returns RemovalResult with `absent=False`; `retire_owner` lines444–445 returns False because exact native world-destruction proof is unavailable. Original Controller._retire_locked therefore retains UNKNOWN/lease after an emitted summon until real absence/owner retirement exists. Host.connection_closing requires EMPTY/CLOSED before releasing the direct lease. Test87 restore-only pass had no actor and does not prove this new close path. A first summon can be observed as DRAINED while subsequent close fails; preserve that result as partial/UNKNOWN, do not claim cleanclose/fresh or fabricate absence. This route does not modify those ownership guards.

## Verification

`python <this-directory>/verify_source.py` passed: three product files compile; only expected changed method sets (Broker5/Peer1/Server4); `_serve`, `_send`, all other existing methods and decoder unchanged; selected87/dependency opcode collision scan 204 paths/0 collisions; original present_disabled decoder accepts the fragmented empty F101 codec fixture. No real handler was called, no server/socket/Store was created, no profile copied and no port used. Runtime, normal session, actual summon and native hotkey remain UNRUN.
