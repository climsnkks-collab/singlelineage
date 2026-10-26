# COMP-04B current kill → native dual-credit boundary

This is a completed caller/input contract, not a native award implementation or
runtime-ready trial. The existing COMBAT split arithmetic and reader remain
owned by COMBAT. No second split formula, award schema or native API is added.

## Existing real contacts

The exact existing `split-exp-v1/AlliedKillReader.current_kill_locked(result)`
validates the source-issued nominal `AlliedAttackResult` through
`AlliedAttackSession.current_result_locked(writer, result)`, actor current and
`AlliedLedger.kill_locked(operation)`. Its `RegisteredKillRead` contains the
original result and KillReceipt, distinct owner/companion UIDs, actor and target
UIDs, accepted ordinal and original operation ID. It is read data only.

That existing reader pins **admission-v2** actor/session/ledger/NPC. It cannot be
installed against admission-v3 or Core6041 motion by changing a dictionary path
or passing current metadata. COMBAT owns the coherent successor reader. The
exact caller takes that real registered result during the same original held
operation; reading it later or reconstructing a receipt is inadmissible.

The current Host `after_attack_locked(writer, service, accepted_before)` is the
**PC attack** death hook: it accepts `broker._attack_session.last_hp_result` and
the original accepted PC KillReceipt, then calls `characters.award_kill`.
It is not an AlliedAttackResult consumer. The selected character-state
`CanonicalCharacterStore.award_kill(source, *, npc_uid, npc_generation, operation_id, total_experience,
companion_lease=None, eligible=True)` writes character-file progression and
alternates an odd EXP between recipients (3/2, then 2/3). It does not retain each
recipient's 0.5 in native PROGRESSION, and it does not atomically join native
growth RESOURCE. This route must not be repurposed or described as the requested
native split. Existing results and saved character records remain unchanged.

## Missing native producer and required caller phase

The old `split-exp-v1/NATIVE_REQUIREMENTS.md` supplies the real existing
Core6041 `BatchStore.prepare/commit`, `ParticipantChange` and
`DocumentCapability` signatures. Those are reused without re-analysis.
Core6041's current capability/participant rules do not supply the required two
PROGRESSION + restored per-recipient halfcarry + growth RESOURCE transaction.
The exact extension symbol/schema and writer have **not** been supplied in this
Source set; `required-contact.json` records this explicitly. Do not assign it to
an unrelated proceeds/Factory/BOOK writer based on a similar module name.

Required source owner input is one native issued capability covering the real
same-account current bindings and original registered kill/once identity, both
saved PROGRESSION revisions/digests and genuine typed halfcarry, applicable
growth RESOURCE, one reservation/atomic commit, partial/UNKNOWN preservation,
duplicate refusal and fresh restored read. Its actual callable/signature must
be supplied by its owner. No proposed method name here is a working callee.

The companion caller can then consume the coherent COMBAT current-kill read,
pass its **original identities** to that actual native producer during the
original operation, and expose only the source-issued committed delivery and
restored values. Native PREPARE and COMMIT must revalidate the original current
proof; a cached `RegisteredKillRead` is not a persistent authorization token.

## Scenario/RUN readiness

Normal login/selection/WORLD → legitimate first summon → lawful ASSIST or
same-operation DEFEND target/current → real automatically repeated own-speed
lethal attack → original registered KillReceipt → actual native dual-credit
producer → original delivery/Store/strictclose → normal fresh reads of both
recipients and saved carry. A pool of 5 initially grants 2/2 and retains 0.5/0.5;
the next 5 grants 3/3 and consumes the carries, under the same native once/CAS
authority. This is the already-confirmed human policy, not a new formula.

No executable gameplay RUN exists before the native producer, coherent reader
and actual kill/cadence transport are supplied. `test_ready:false` and
`run_ready:false` are deliberate. Source paths/symbols/phase/required values and
the first blocked action are complete in `required-contact.json`; integration
must route the missing source to its actual existing owner, then return the
completed producer for this caller's next private successor. No direct handler
test, dual separate commits, fake carry defaults or legacy parity migration.

First failure keeps the original native commit/partial status, raw error,
current/FIRST/UIDburn and both saved beneficiaries unchanged except for genuine
native effects. No retry, refund, reset or fabricated cleanup success.
