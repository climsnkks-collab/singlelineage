# COMPANION-MAGE — repeated motion v2, cross-version fixture repair

**SOURCE_COMPLETE / WRITER_RELEASED**. source_ready=true, test_ready=false,
run_ready=false, selected=false, runtime=UNRUN. All seven product files are
**byte-identical to immutable v1**. This descendant changes focused verification
only. No common/Test/client/API/queue/ACTIVE, live processes, ports, runtime copies
or Store files were touched. V1 and its queued parents remain untouched.

## Diagnosis

The inherited cancellation-injection fixture shared its Task across test cases.
For `cancel_begin_write`, it called `Task.cancel()`. The actual product's
synchronous `cancelling()` guard then manually raised CancelledError before any
suspension. That caught exception did not consume the event-loop cancellation.
The fixture called `uncancel()` immediately in its finally block. Python3.12.14
still delivered the scheduled CancelledError on the later queue-wait case's
first actual suspension; Python3.13.14 rescinded it. The resulting later failure
was cancellation contamination, not a premature product commit or queue0 policy
change.

`diagnose_fixture.py` reproduces this difference with a minimal isolated Task:
original cleanup leaks on 3.12 and is clear on 3.13; deliver-before-uncancel
cleanup is clear on both. The versioned diagnosis JSON files preserve actual
observations.

The new verifier runs each fault case in its own Task. When the injecting Task
has an outstanding cancellation count, its cleanup first suspends and consumes
that scheduled cancellation, then clears the counter. This is only fixture
cleanup after the actual product result was captured. Each parent Task is checked
for no cancellation leakage. No exception from a real Broker admission or queue
guard is swallowed, reclassified or converted to PASS.

The actual Broker `_send` fixture still requires the exact original eventual-zero
assertion: two sample/checkpoint rounds, policy.drained after the last checkpoint,
and COMMITTED only after actual queue==0. Invalid queue, cancellation, failed
delivery, retained pending/UNKNOWN, nonidentical wire, ordinary NPC gates,
sequential COMMITTED admission and all existing source checks remain active.

## Parents and verification

`parents.json`: absolute paths/full SHA256/length for v1's seven products,
verifier and manifest. `manifest.json`: exact v2 products and verifier pin.
Product `.diff` files are empty; only `verify_focused.py.diff` changes behavior.
`build_source.py` verifies exact v1 parents and reproduces this descendant.
The original sequential LOCAL policy, Player f2 UNKNOWN, typed4E40/tombstone,
Controller defaults and server-only success boundaries remain as recorded in
v1's HANDOFF.

Both actual interpreter runs passed **137 focused checks**:

- Bundled Python **3.12.14**:
  `C:/Users/Chansol/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`;
  result `verification-python3.12.14.json`.
- System Python **3.13.14**: `python`;
  result `verification-python3.13.14.json`.

Run `build_source.py`, then `diagnose_fixture.py` and `verify_focused.py` with
each interpreter from project root. Each version writes separate bounded JSON
evidence and does not overwrite the other version's result.

These remain cold imports and isolated exact-code checks, not live authority,
transport, Store, native or packet PASS. Test readiness still requires owner/root
review, coherent downstream SourceSeal cohort selection and the repeated-motion
normal packet caller/RUN. V1's existing integration boundary is unchanged.
