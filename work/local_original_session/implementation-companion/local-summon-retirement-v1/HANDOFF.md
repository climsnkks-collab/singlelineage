# LOCAL summon retirement — no source-backed absence producer

WRITER_RELEASED / SOURCE_ONLY / runtime UNRUN / **test_ready:false**.
Owned directory: `implementation-companion/local-summon-retirement-v1/` only.
No product candidate was made: the selected source cannot issue the receipt
needed to release an emitted companion lease truthfully. No common/Test source,
server, game, port, profile, Store, packet client/API, native patch or REA runtime
was changed or started. Existing unrelated worktree changes were preserved.

## Result

**A server-side 4E40 drain, packet completion, registry removal or socket close
cannot close this existing Controller lease under its selected contract.**
The missing input is positive absence of this exact published actor generation
from the original client lookup stores, or positive destruction of that actor's
exact original client world. Neither receipt has a producer in the inspected
Allied/Controller/Host/PacketPeer source. There is no existing 4E40 client ACK in
these selected source contacts; none is invented or required as a new protocol.

This is a bounded source conclusion, not proof that the original client has no
other possible lifecycle protocol. A future existing-source observation can
supply the positive fact without adding an ACK. Until then, emitted/ambiguous
actors retain their lease and UNKNOWN; clean close/fresh must not be claimed.

## Exact source path

1. Allied `companion-allied-account-v5-v1/allied_player_publication.py`
   **d1490b4e** binds the actual account companion CharacterLease, direct owner,
   selected row/Binding, selection and distinct actor UID/generation in its
   PlayerRegistration. `spawn` publishes the real 4E96 through Broker `_send`.
2. `RootPlayers.send_phase` advances REGISTERED -> RESERVED -> WRITE_ATTEMPTED
   -> DRAINED from original policy row identity, pending opcode/size, send count
   and queue zero. This proves server write/drain. It does not inspect original
   client actor storage, and `RootPlayers.close` explicitly retains unknown
   records rather than issuing client absence.
3. `AlliedPlayerPort.remove` has one valid positive absence case: the actor is
   still REGISTERED and positively never emitted. After a DRAINED spawn it
   registers/sends the real UID-bound 4E40 once and returns
   `RemovalResult(record.removal_phase == 'DRAINED', False)`. A partial spawn
   phase is refused by `ALLIED_AMBIGUOUS_SPAWN_PRESERVED`. Retried cleanup does
   not resubmit an already registered removal. `retire_owner` is literal False.
4. Selected v5 `companion.py` defines `RemovalResult.absent` as exact generation
   absence in original lookup stores or positive never-emitted proof. Its
   Controller `_retire_locked` releases the companion CharacterLease only when
   `removed.absent` or positive `retire_owner(owner=retained_owner)` is true.
   Otherwise it records UNKNOWN/COMPANION_REMOVAL_UNCONFIRMED and retains the
   lease. `confirm_owner_retired` explicitly excludes socket close or a changed
   selected UID as proof of destruction.
5. The new hotkey Host **f361027d** retains the old Host retirement methods
   exactly by AST. `_retire` requires EMPTY/CLOSED, and `selection_retired`
   requires that result before releasing the direct lease. A new local hotkey
   helper does not change any of those facts.
6. New `local-summon-server-route-v1` keeps original Broker `_send` and `_serve`
   AST exact. Cleanup tries Host.connection_closing before server-world cleanup,
   records a real failure if retirement is unknown, then performs PacketPeer /
   realm / writer cleanup and invokes Host.connection_retired. Reordering those
   steps would not itself prove original client world destruction.
7. PacketPeer is explicitly server-side accepted TCP authority. `reply_drained`
   and `complete_request` collect actual server opcode/count/send intervals;
   `close_session` removes its server current/sample/world/selection references.
   The common v5 packet client reads frames and that same completion receipt.
   Neither operation is a native actor registry/selection observer or destruction
   receipt. Received 4E40 bytes remain transport evidence.

All ten exact inputs, SHA256 values and function spans are in
`source-evidence.json`. These are actual selected source contacts; no dummy
actor registry, fake receipt callback, second owner or test wrapper was added.

## REA285 reuse and precise missing contact

Reuse `run285_allied_native_publication_retirement_identity/source/contract.md`
**85043083** and its existing main review. Original 4E96 f2 -> SpawnInfo[0] ->
Actor+18/Player.slot8 and original 4E40 -> 4E700 -> 61650 connect the wire UID to
the retained matching Actor and component cleanup. They identify possible
observation locations; they do not issue a runtime current/generation receipt.

In particular, 61650 removes the first UID match in +8A8/+8C0 and retains the
matching Actor during cleanup. Lookup 627B0 also searches +8D8. That source does
not guarantee all three vectors lack the UID, all duplicate UID nodes disappear,
or all external strong references vanish. Actor UID alone and account cursor
nonreuse do not prove same client world/session/native instance. Interaction
I30=0 is also distinct from I70 clear or already-entered invoke completion.

The required future observation is one of:

- After the original ordered spawn/removal writes settle, a source-bound read
  of the **same client world and published generation** establishes absence in
  its original lookup stores, while rejecting replacement/current mismatch and
  retaining UNKNOWN on a failed/partial read or outstanding ambiguous write.
- An actual source-bound lifetime receipt proves the **exact old client world**
  associated with the retained owner/selection/generation was destroyed, after
  prior sends can no longer publish into it.

These describe the already selected port contract, not a new implementation,
mandatory handshake or enlarged test system. Actual172 NPC UID absence cannot
be reused as evidence that a newly summoned Player generation is absent. The
optional custom click callback's invoke retirement gap in REA285 is separate;
this review does not make implementing a click hook a plain-summon prerequisite.

## Integration consequence and minimal next verification

The first normal F101 request can still be exercised by the independent new
caller as a **bounded partial trial**: real login/roster/ROOT WORLD -> packetless
LOCAL hotkey intent -> one empty F101 -> actual 4E96/issued actor UID/current
lease/RESOURCE. Its real spawn DRAINED/AWAITING_POSE can be recorded. That does
not qualify the complete summon/dismiss/reuse lifecycle as ready.

With the selected d149 port, cleanup after emitted spawn reaches UNKNOWN and
Host COMPANION_RETIREMENT_UNKNOWN; preserve the raw first error, UID burn,
partial Store and retained leases. This is a source prediction, **not an actual
observed run**. Do not clear the guard, release the lease from a server-only
dictionary, replace absent=False, change the meaning of RemovalResult, skip
close validation or call Host/controller directly from a trial.

Once a real lifetime producer is supplied, only the changed normal summon ->
original removal -> actual positive absence/destruction -> release -> strict
close path needs verification, using the existing v5 caller/flow. Keep partial
or ambiguous removal UNKNOWN and preserve current/owner checks. No runtime
RUN_COMMAND is supplied here because this report has no executable candidate.

## Focused checks

One bounded source inspection passed: exact Allied d149 and Host f361 hashes;
REA285 contract hash; original Host four retirement methods AST unchanged;
original Broker `_send` and `_serve` AST unchanged in the new route; and literal
False owner retirement in the selected Allied source. Source syntax was parsed
without importing product modules. Ten file pins/function spans were persisted.
No game/port/profile/Store or repeated prior successful protocol test ran.
