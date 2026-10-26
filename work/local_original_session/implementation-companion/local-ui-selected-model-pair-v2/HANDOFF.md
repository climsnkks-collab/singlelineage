# COMPANION-MAGE — selected display model v2, owner-query minimization

**WRITER_RELEASED / source_ready:false / test_ready:false / runtime_ready:false / RUN_COMMAND:null.** This new private directory only. Immutable queued/final v1, common/Test/queue/ACTIVE/source/save files and main dirty checkout were not written. No game, DLL, pipe, TCP port, focus/input, Job or native process was started; no branch/worktree/commit. Owned resources0.

## Concrete change from v1

v1 manifest full SHA `20f02e31fef2666bbd7e641f769c8a678dd7b9bb04aaa0b85a0056f42ebe7877` is the exact immutable parent. `parent-pins.json` pins its relevant source/evidence and the original pure transport policy. v2 retains 185 cohort rows, changing only launcher/Broker/click to private descendants; 182 source rows remain path/bytes/SHA identical. Launcher changes only its exact transport hash; click changes only its exact Broker hash. Original NativeOwner/Factory classes, NativeInput gate, one-use pipe/process identity, sequence/deadline/cancel/unknown retention and native wire/parser are unchanged.

The actual selected Broker's `_poll_checkpoint` already awaits `_checkpoint`, which obtains original `_sample` evidence and consumes it through the original policy. It previously discarded that return. v2 captures that exact local return and immediately invokes the existing channel row checkpoint inside the same `_poll_checkpoint`/original `_row_operation` and empty-decoder branch. No intermediate companion tick/await, evidence cache, restamp, new sample, boolean proof, task or lock is introduced. The old later idle hook after `companion.tick_locked` is removed. This placement projects the current server state before that existing tick; native still immediately discards its transient display projection and has no selected cache/panel to become stale after a later tick. The after-replies hook remains exactly where v1 placed it, after original replies/drains and companion tick.

Inspection of `_send` confirmed it performs many internal write/drain samples but returns no owner sample, including empty reply paths. The outer frame's `sample` can predate awaited sends/ticks, so v2 does **not** treat that local as a post-replies proof. The post-replies hook passes no checkpoint sample and uses a fresh original guard at actual delivery.

`_capture_locked` keeps every v1 current Host/row/task/direct/held lease/actor generation/epoch/RESOURCE/owner/issued-pipe reference and native process authentication check. The sole removed operation is its redundant `owner.guard_exact_sync(dict(row['peer']))`. Captures therefore do not enumerate the TCP table. A channel with neither bound attempt nor pending request now does no additional idle capture. A bound attempt without a request still checks its current references once and revokes changed selections/epochs, without another TCP query.

For a pending display response, the synchronous Host.view/encode after-check and prewrite reference check are combined. It captures before projection, immediately before write, and after the OS write: three reference/current captures instead of four. No await or callback publication exists in that synchronous window.

Only `_delivery_owner_current` can perform the new TCP query. Immediately before delivery it accepts the actual original poll sample only when exact OwnerSample type, original owner/handles/Job, actual row/policy connection/peer tuple, live identity flags and original timestamp are valid. It uses the unchanged `policy.FRESH_NS=250000000` and consumes the same sample/timestamp with the original pure policy checkpoint. Missing or expired genuine evidence instead calls the original `NativeOwner.guard_exact_sync` once. Malformed, replaced-owner, false, future or caller-boolean evidence refuses; it does not fall back to a permissive proof.

After any known complete or zero-byte busy WriteFile, v2 recaptures current server references and **always** performs a new original guard, because the OS write may block despite no asyncio yield. It never reuses prewrite evidence across that boundary. Failed postwrite owner/current checks burn the attempt and do not increment model success. Positive partial/ambiguous writes immediately burn the same attempt without retry or success, retaining the existing failure semantics. A zero-byte busy write remains pending only after the fresh postwrite guard, and the next genuine row reprojects/rechecks everything.

Thus added TCP query counts from this model path are:

| Path | New model TCP queries |
|---|---:|
| Idle, no display delivery | 0 |
| Idle delivery, original poll sample still fresh at prewrite | 1 after WriteFile |
| Idle delivery, original poll sample expired | 1 prewrite +1 postwrite |
| Post-replies delivery, no original returned proof | 1 prewrite +1 postwrite |

These counts are source/state-machine results, **not measured runtime speed or game performance**. Existing Broker checkpoints continue their original work. No guard/FRESH_NS/source ownership or original game packet policy was weakened.

## Verification and limits

`python -B work/local_original_session/implementation-companion/local-ui-selected-model-pair-v2/build_source.py`

`python -B work/local_original_session/implementation-companion/local-ui-selected-model-pair-v2/verify.py`

`python -B work/local_original_session/implementation-companion/local-ui-selected-model-pair-v2/finalize.py`

Actual **PASS73**. Exact parent/new pins; whole Broker inverse AST restores v1; launcher and click only exact source hash edits; original current/reference checker differs solely by removal of TCP query; unchanged encoder/authentication/lifetime methods; source proof's direct `_checkpoint` call path; synthetic guard counters for fresh/stale/postreply/idle; malformed proof refusal; zero-byte postwrite guard; partial unknown burn; postwrite owner exit and projection/reference replacement all checked. Fixtures use pure policy OwnerSample objects and fake guard counters only. They do not instantiate NativeOwner, invoke genuine `_capture_locked`, inspect TCP/pipe, create a game owner or establish runtime authority.

The exact native v1 transport/display/bootstrap/mailbox/ABI sources and original v1 MSVC compile/PASS109/21 parser cases are reused by absolute pins. No native source changed, so compile/parser/OS scenarios were not repeated. No v2 native DLL/receipt/NativeInput was supplied or selected. The parent's original paired-native gate remains intact in both main/run_session; no feature/game Test RUN exists. Actual admitted Host/row/model delivery, native panel/render/OPEN/CLOSE, selected UI commands and runtime timing remain UNRUN/UNKNOWN. A future command still needs fresh server admission; the display wire carries no UID/action authority and native keeps no selected projection cache.

Main reviews the actual delta and queues/selects it. This worker did not edit the queue or advance readiness. v1 remains preserved; v2 is an immutable private source descendant with truthful false feature flags.
