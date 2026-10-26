# COMPANION-MAGE click router contact plan v1

WRITER_RELEASED / PLAN_ONLY / runtime UNRUN / test_ready:false.
The existing main branch and unrelated dirty files were inspected read-only. This unit writes only this new directory. No parser, handler, packet sender, source clone, queue message, server, socket, port, saved copy or native execution was created.

## Source boundary

Exact complete parents are companion-cohort-v2 and actor-click-v1. manifest.json pins all consumed current source bytes and the three partial REA270 artifacts. This is an implementation contact map, not a selected runnable cohort. Existing cold 22-check PASS/181 imports and host source fixture results are reused; they were not replayed.

REA270 actor contract joins normal Pet/Summoned construction -> same Info -> Interaction+8 same Actor -> selector20. Installer contract conditionally installs B8710: selector20 with 42EC0 result absent or result+98 nonzero. Present result/+98zero does not install that callback. Its caller uses Interaction+38, whose active pointer is Interaction+70; B9990 dispatches the same Actor to B8710. This does not produce a server current generation.

reply-reuse.json contains primary-supplied context that the request is LIN::CS_SUMMON_STAT_REQ / 0x4F13, one required field1 uint32 from targetActor.virtual8 low32, no separate action field. Its own status is DIRECT_REQUEST_RESPONSE_JOIN_UNKNOWN; that worker explicitly did not reverify the request. At capture time the primary installer contract still says packet schema/guard unfinalized and no top-level final HANDOFF exists. Therefore this unit does not promote that context to an implemented contract. A summon-stat request does not itself prove a settings open or a response opcode. Never borrow NPC 4E43/action15 or invent a 4F14 reply/ACK.

## Exact minimal insertion contacts

| Existing source | Contact and minimal eventual change |
|---|---|
| tools/local_entry_server/codecs.py:91-115 | ClientPlaintextDecoder already accepts generic C2S header10/present_disabled, validates exact padding/length and emits Frame.payload. No new decoder/framer is required. |
| cohort-v2/product/broker.py:247-319 | _TransportPolicy.received_frame currently admits typed feature extensions. Add only an attached typed source-backed click feature header admission when final schema exists, retaining checkpoint, stage/rx_boot/tx_boot, pending drain, size, rate and real received counter. Do not add an unrestricted opcode to the frozen policy. |
| tools/local_game_session/session.py:144-148 | GameSession.received resolves same writer/registry and dispatches routes[frame.opcode]. No global dispatcher change required. |
| cohort-v2/product/broker.py:677,1065-1159 | LocalRealm.grant registers per-writer routes before its terminal_guard wrapping loop. Add exact click route here after genuine installed Host/source check, so settings fatal/quit/player-life guards also apply. Preserve ordinary selection/login/WORLD callbacks. |
| cohort-v2/product/broker.py:2148-2172,5682-5828 | _serve invokes policy admission and game.received under its original _row_operation, then _send, PacketPeer.handled/drained and complete_request after unlock. Keep this ownership/completion chain unchanged. |
| actor-click-v1/.../companion_host.py:343-382 | open_from_actor_click currently acquires _row_operation and validates same writer/current actor UID/generation/lease before _open_panel_locked. Factor those existing checks into an explicitly locked helper in a private descendant; native callback keeps acquiring the outer scope and delegates to the same helper. Packet route already owns scope and must call the locked helper, never await the public locking entry. |
| allied-publication-source-v2/allied_player_publication.py:307-314,412-423 | PublicationRoot.current validates exact typed registered record/current state,row,binding,selection. AlliedPlayerPort.server_snapshot rechecks root and actor UID/generation/owner, refuses removal, reports publication drain. Resolve generation from same writer's existing registered actor/current participant only. Never decode/create generation from wire. |
| cohort-v2/product/packet_peer.py:283-341 | Existing receipt stages already record actual request, replies and HANDLED_NO_REPLY. No feature-specific Peer change. No-reply completion cannot establish that native panel opened. |
| cohort-v2/product/packet_server.py:41-86,205-289 | Retain selected_sources/_Sources and actual Plan prepare/hooks. New module/source pins must enter the same exact coherent loader graph. Keep Broker/Peer/Server co-location contract; do not clone Test server implementation. |
| packet-test-client-v5/packet_client.py:234,299,328,393,456,542 | Reuse normal_session -> actual roster/enter_world -> ready_current -> packetless_step only for genuine packetless selections -> send_request. Existing send_request handles generic opcode/payload and all actual receipts/frames; no common client/API edit needed. |

The locking split is necessary: existing _row_operation rejects canonical reentry with BATCH_OPERATION_SCOPE_ALREADY_ACTIVE; with no canonical provider the legacy asyncio.Lock would block. Calling open_from_actor_click directly from game.routes is therefore invalid. Do not release the outer lock or use a new task to evade it. A locked helper must preserve the same _row, writer, current/lease identity and panel epoch checks.

## Proposed bounded private files/hunks when the contract is final

1. New companion_actor_click.py pure request parser/typed route feature in this owned directory, only after final primary schema/guards are pinned. Reuse existing bounded protobuf parser, require exact field occurrence/type/range under the finalized policy. Report malformed/unsupported target/foreign writer/stale or removed generation as refusal, without panel creation. The accepted UID must equal the same current drained registered actor. Field presence and duplicate/unknown handling must follow source-backed/local documented policy, not guessed protobuf permissiveness.
2. Private descendant companion_host.py: one extraction of current actor-click body into locked helper; public native callback delegates while holding original row operation. No alternate panel state, settings storage or UI epoch.
3. Private descendant broker.py: typed source-bound header admission plus per-writer route before terminal wrapping, sharing original row operation. Route must not manufacture a generation, lease, registration or native owner. Bind only after finalized meaning of CS_SUMMON_STAT_REQ and panel/response boundary is established. If request only asks stats, implement that narrow source-backed behavior rather than mislabeling it settings open.
4. Private coherent cohort/loader metadata selects exact new files and adjusts only actual direct pin contacts. Preserve original neighboring Broker/Peer/Server function-source contract. Do not mutate prior cohorts or Test-owned client/API/ready_current.
5. Feature caller leaf/scenario using the existing common client, with exact sources and RUN_COMMAND only after genuine summon + native panel binding exists. Do not publish a runnable command while its inputs are null.

## Concrete minimum future caller order and verdict

Input must be a new Test-owned whole copy of the existing successful saved class3 mage account, preserving its actual acquired files/UIDs. Normal VERSION/bootstrap/0263/roster -> selected actual direct character -> original 4E28 -> exact WORLD prefix and ready_current -> genuine user-triggered summon protocol -> real separate mage lease/registered actor publication and send/drain. Missing summon contract is the first currently unsupported action; no direct Host/controller summon may replace it.

Only then record original selection/callback condition, obtain actual target UID from same server-issued registration and source-supported uint32 encoding, send the finalized request with common client.send_request. Record receipt ordinal/status/raw frames and first original error/partial Store. If expected S2C join remains unknown, mark response UNKNOWN; empty replies/HANDLED_NO_REPLY cannot be upgraded to protocol or native settings success. If a genuine native panel binding exists, verify same panel/epoch separately, then one supported configuration action and exact Store/fresh readback. Close via existing normal_session/Test owner lifecycle; preserve FIRST and partial saves without reset/retry/regrant.

Minimum source verification after implementation: parse/compile changed files; pure finalized-wire parser cases; exact malformed/stale/foreign-generation refusal at the existing source fixture boundary; one lock integration check proving single original operation and same panel body. These are source-only checks. A real trial must traverse actual decoder/router rather than direct handler calls. Existing successful login/mage acquisition/cold imports remain reusable evidence, not new runtime results.

runtime_command:null / run_ready:false / test_ready:false. Remaining blockers: primary final request + response contract; genuine summon input; original native ATS/panel owner; account-child Host/Factory lifetime. No game/client screen/render/input or settings success is claimed.
