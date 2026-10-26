# COMPANION-MAGE — local native panel surface, exact-input blocker

**WRITER_RELEASED. Panel implementation was not started. source_ready:false / test_ready:false / runtime_ready:false / ui_ready:false / RUN_COMMAND:null.** The assigned fallback applies: the exact selected native consumer is deliberately ephemeral and supplies no safe display transfer to the owner. No placeholder window, copied display cache, dummy native model, or OPEN/CLOSE claim was introduced.

## Exact evidence

Inputs are immutable selected-model-pair-v2 manifest `99f9c29f6c9829cf8683ff13ea13ab83aa20b3664e395b96b8f0b893fec5e967` and native-owner-mailbox-v1 manifest `92ae28a78af8d80d27719bd787736a22b73f04f188f760bdb69625d58433aeb3`. `input-pins.json` records absolute paths, full SHA256 and sizes of inspected files. Native selected bytes come from paired v1, as specified by v2; the original mailbox bytes are the same selected dependency.

- `local-ui-selected-model-pair-v1/ui_selected_display.hpp:59-66` explicitly says the consumer is ephemeral and a later UI needs a separately reviewed revocation/expiry contract. `ConsumeEphemeral` parses into a stack `Projection`, clears it, and returns only validity.
- `local-ui-selected-model-pair-v1/ui_transport.hpp:81-87` invokes that consumer and clears the frame. The only published snapshot is sequence plus validation history, expressly never live authority (`:15`). Neither pointer nor owned model reaches the established owner thread.
- `local-ui-selected-model-pair-v2/local_ui_channel.py:562-593` encodes genuine Host.view display values: phase/reason, support state/reason/enabled/rule count, at most eight names/levels and request sequence. No per-model expiration, revocation epoch or owner-publication receipt is encoded. The 30-second transport lifetime is a channel bound, not permission to cache a selected model for 30 seconds; the original 250ms owner evidence freshness also cannot be invented as a display lease.
- `local_ui_channel.py:607-635` creates the view within the actual row operation and rechecks current references/owner after WriteFile. The producer can revoke/burn an attempt after bytes already reached native. This was safe specifically because native retained no projection. A cache would create a new cross-thread lifetime problem.
- `ui_transport.hpp:56` clears authentication and validation history at session exit, but has no display publication/withdrawal or owner wake path. Native cannot close a nonexistent panel through that code. Observing an atomic authentication boolean alone supplies neither a model nor an ordered lifetime/revocation contract.
- `local-native-ui-owner-mailbox-v1/ui_owner_mailbox.hpp:8-9` accepts only value-copied `Checkpoint(sequence, tag)`. Its callback never receives a projection. OwnerProcessed means dispatcher processing only. Its Closed receipt describes the message-only dispatcher, requiring actual DestroyWindow return, WM_NCDESTROY and callback depth zero; it is not a companion-panel CLOSE receipt.

## Consequence and smallest dependency

A genuine panel requires a new, reviewed selected-display publication contract connecting the one-attempt IO worker and established owner. It must own bounded immutable display bytes (not a stack pointer), establish the display validity/expiry rule without inventing authority from sequence/history, serialize replacement/withdrawal, prevent revoked or expired publications from being rendered, clear display on withdrawal, and wake owner cleanup without changing original game message forwarding or input. Revocation detected after server delivery and native session exit must terminate publication. The exact invalidation latency and behavior while owner is stalled must be explicit; no off-thread User32 cleanup or timeout-to-CLOSED claim can replace an owner run.

Only after that dependency is selected can an owner-thread `WS_EX_NOACTIVATE` read-only surface consume it. It needs its own actual creation/render and DestroyWindow/WM_NCDESTROY/callback-drain receipts. Commands remain absent or disabled until a selected fresh command transport exists. No mailbox receipt or parser success may stand in for these receipts. Whether a small standalone surface can be created with a synthetic test model is unrelated to safely displaying this selected ephemeral Host model, so such a fake integration was not produced.

The blocker is in these exact inputs, not a general impossibility or a new user approval gate. Main can assign the missing publication contract as a separate owned descendant and review it before a real surface implementation. Existing independent authorized work can continue.

## Verification and preserved boundaries

`python -B work/local_original_session/implementation-companion/local-ui-panel-surface-v1/verify_contract.py` performs bounded exact-parent/source-contract inspection and compares all inspected input hashes before/after. `verification.json` gives the result. Native compile and Win32 message-loop tests are NOT RUN because no native source was added or changed; earlier parser/mailbox results are not rebranded as panel tests. Game/DLL/pipe/port/Job/focus/input execution is zero, panel OPEN/CLOSE remain UNKNOWN, owned resources0.

Only this new private report directory was written. Original game/common/Test/queue/ACTIVE, existing private source/evidence and dirty checkout were preserved. No branch/worktree/commit, queue publication, new chat or external message was created by this worker. Main reviews and owns any queue action.
