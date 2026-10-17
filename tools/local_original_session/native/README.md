# CP49 source-check diagnostics

`python -B tools/local_original_session/native/prepare.py` creates a fresh
`work/local_original_session/native-build` with two generated include overlays.
The wrapper uses MSVC `include_alias` to compile the existing CP49 implementation
and its original dependencies without modifying or copying the frozen tree.

Run the generated `build.cmd` from the project root to build a separate
`own-login-bridge-cp49.dll`. It retains the existing CP49 compiler flags,
`guard_template.asm`, `.def`, exported ABI and import filename. This workflow
does not install, load or run that DLL. Product integration owns runtime copies
and its accepted DLL hash profile.

The generated `compile-fixture.cmd` compiles the existing KEY/VERSION mock
against the same overlays with `/c /W4 /WX`. It neither links nor executes the
fixture. The original fixture and its recorded native results remain unchanged.

Only `connect-probe-*.json` and `sender-probe-*.json` gain two bounded fields:

| Field | Meaning |
|---|---|
| `source_check_step=0` | No original-source check reached, or invalid anchor size. |
| `source_check_step=1` | Existing Executable check failed. |
| `source_check_step=2` | Executable passed; existing SafeCopy failed. |
| `source_check_step=3`, passed=false | Existing memcmp found a mismatch. |
| `source_check_step=3`, passed=true | All three existing checks passed. |

`source_check_passed` is always boolean. Existing binding stage and failed-record
fields identify whether this was the current edge or another all9 record.
No new memory query/read, address, byte content, retry, bypass or cached admission
is introduced. Guards retain their original short-circuit order and outcomes.
The generator reverses every declared edit and checks equality to the original
logical source. Frozen source files, candidates and installed DLLs are preserved.

MSVC include routing reference: [include_alias pragma](https://learn.microsoft.com/en-us/cpp/preprocessor/include-alias?view=msvc-170).

## Sibling product

`python -B tools/local_original_session/native/prepare.py --sibling-product`
creates a separate `work/local_original_session/native-sibling` without
regenerating `native-build`. It reuses CP72's import-name-only validator with
`own-login-bridge-dg49.dll` as its destination. Only the two 26-byte name ranges
at offsets 39145184 and 39146224 change; the actual difference is four bytes.
The candidate remains named `native-login.candidate.bin` in this build output.
Product integration may copy it to the existing clone's `LC.guard.exe`.

This mode aliases one additional identity header whose sole SHA literal matches
the new candidate. The generated `.def` changes only its `LIBRARY` basename;
all 27 export declarations remain identical. Its generated build recipe emits
`own-login-bridge-dg49.dll` beside the candidate. Existing CP49 source has no
runtime dependency on its old module basename; successful loading under the
new name still requires actual product verification by the main session.
The original CP69 candidate, CP49 DLL, CONTROL and earlier diagnostic build are
preserved. No guard condition or initial validation workaround is added here.

## Connect role separation

`python -B tools/local_original_session/native/prepare.py --connect-role-fix`
creates `native-connect-fix`. Candidate bytes and the dg49 import name match
the sibling product. This mode changes one admission decision: a current Connect
whose complete own `VerifyOriginal` succeeds may retain its wrapper despite an
unrelated all9 source check failing, provided an earlier complete all9 publication
in this DLL lifetime has the same image base and identical cached Connect target.

The explicit `all_roles_verified_base` marker is written only after the existing
all9 validation, generation check and seven-target publication succeed. Key-role
publication cannot set it. The production `allow_current_connect` helper checks
the current fresh result, record 0, stage 2, failed record 1..8 and that prior
publication under the existing binding lock. It neither publishes a new target
nor replaces the current Connect's own source check. Existing duplicate-connect,
Sender and Init handling remain unchanged. Failure reason/stage remain visible.

Connect records add `current_original_verified`, `prior_all_roles_verified` and
`connect_role_revalidated`, all booleans. `build-connect-fixture.cmd` builds a
small fixture calling the production helper directly: one allowed case and four
refusals for missing marker despite Key publication, failed own validation,
another generation and a changed cached target. The build does not execute it.
The main session owns independent review and any fixture or game execution.

## Existing memory-query observation

`python -B tools/local_original_session/native/prepare.py --memory-query-diagnostics`
creates a new `native-memory-query` output using the same candidate, dg49 name
and Connect role fix. This diagnostic delta preserves every admission decision,
publication and short-circuit order. The previous output directories are retained.

`Executable` caches its existing single `VirtualQuery` result in thread-local
storage. It adds no query, game-memory read, retry or bypass. The cache contains
return size, failed-query error, state/protect/type, requested span, region size,
whether the existing region checks ran, and their outcome. It retains no address
or original bytes. Category values are 0 unobserved, 1 empty span, 2 span overflow,
3 query failed, 4 not committed, 5 guard, 6 noaccess, 7 region overflow,
8 span outside region, 9 excluded protection, and 10 Executable passed.
`PAGE_EXECUTE` remains excluded exactly as before; actual failure evidence must
identify the relevant category and protection before considering a guard change.

Two independently claimed, fixed-size diagnostics use the existing fresh context
validation and create-only output path: `source-check-first-failure.json` records
the first old9 source refusal, and `selected-source-check-failure.json` records
the first current Selected source refusal even if a constructor failed earlier.
Each includes PID/birth/candidate SHA, time/thread, current record, binding stage,
failed record and source step. The snapshots occur immediately after the own
check or inside the all9 failure branch, before Connect preservation and later
fallback checks can replace the thread-local observation. A category of 10 with
source step 2 or 3 means Executable passed and SafeCopy or memcmp failed.

Only the DLL and existing KEY fixture are compiled by the worker. No DLL,
fixture or game execution is part of this preparation; runtime integration and
source review remain with the main session.

## One bounded source-read retry

`python -B tools/local_original_session/native/prepare.py --source-read-retry`
creates `native-source-retry`. It preserves the previous diagnostic build and
the existing Connect-only, ConnectedDuplicate and CountsSender policies. The
new path never accepts PAGE_NOACCESS as executable.

After the complete current caller/mapping/unwind/leaf/IAT prefix succeeds,
VerifyOriginal may retain base/original metadata with wrapper zero. A separate
prefix flag authorizes considering a retry only for an Executable refusal.
The production helper additionally requires prior complete old9 publication,
identical published base and role target, a full query result, exact MEM_IMAGE /
MEM_COMMIT / PAGE_NOACCESS, the verified allocation base and complete source span
inside both image and query region. It checks the publication under the existing
lock before reading, after reading and after full revalidation.

Each probe invocation owns its budget on the native C++ stack, so application
exception-handler reentry cannot reset its budget. It may attempt one SafeCopy
per unique original source address. Constructor records4/5/6 share one address
and one budget entry. A local
volatile digest keeps the entire copied span observable to the optimizer without
exposing its contents. A returned copy then requires the complete original
VerifyOriginal again for the current edge, or the original Executable / SafeCopy /
memcmp sequence for an all9 span. Current-edge retry preserves the latest
VerifyOriginal failure, including fresh caller/leaf/IAT failures; a successful
read followed by a publication conflict returns GenerationConflict with wrapper
zero. Only an ineligible or failed read keeps the initial source refusal.
Any refusal leaves the existing policy in
control; no new target is published outside the old complete all9 success block.
This mode adds only bounded reads and repeated existing validation, and writes
no page protection. Whether application exception handling activates a page on
a read fault remains UNKNOWN until actual execution.

`source-read-retry-record-N.json` records the first attempted invocation for
each old9 record; Selected record2 is also emitted if no read was eligible.
`retry_attempted` and `retry_full_verified` describe the bounded reads and their
full revalidation; `guard_wrapper_selected` separately reports the overall guard
result under the preserved policy. Failed original-source diagnostics remain.
`build-source-retry-fixture.cmd` builds a production-helper fixture with24 checks:
successful verification, repeated/aliased spans, thirteen eligibility refusals,
read failure, failed full verification and publication changes during reading
and verification, latest prefix-failure preservation, post-proof conflict and
an independent nested invocation budget. The build does not execute it. The main owns source review,
fixture execution and any one-run native experiment.

## Fresh verified connected duplicate

`python -B tools/local_original_session/native/prepare.py --verified-connected-duplicate`
creates `native-verified-duplicate`, adding a third reversible source overlay for
the ABI implementation. NativeProbeFrame, exports, ASM and original-only target
publication stay unchanged. The source-read retry helper, latest-failure handling
and invocation-local budget remain identical to `native-source-retry`.

The first Connect consumes the original one-shot taskFrame. A later Connect may
still come from the same live original task, including a new tick while Connected.
The new verified task scope separately borrows a genuine retained manager key0
socket pair. It requires the known selected callable, Selected/Connected phase,
a safely read matching manager, and a rechecked owner. Connected requires the
held socket object and control to match the caller's established socket pair.
The frame is invalid inside a nested other task and restores the previous live
scope before the new Held pair is released, on both normal and exception exits.

The new duplicate predicate requires a fresh Bound Connect result, exact original
caller/leaf/target, prior all9 publication and identical cached Connect target,
same live task/manager/socket/control, Connected with a prior connect attempt,
no own-limit refusal, requested port14030, and the actual peer127.0.0.1:14030.
It rechecks proof and ownership after querying the peer. The probe posts a
distinct private claim; the bridge consumes it and repeats those checks against
the actual call arguments. Lost proof returns false without another original
Connect. First Connect, foreign owner, wrong phase and nonlocal peer remain
outside this bypass. No new original callable is published or invoked.

`fresh_verified_duplicate` is emitted independently in connect probe and caller
diagnostics. `source_mismatch_override` keeps its legacy meaning and the old
NoAccess/ConnectedDuplicate/CountsSender fallback behavior remains unchanged.
`build-verified-duplicate-fixture.cmd` builds29 production-helper checks including
negative ownership/phase/origin/peer/proof cases, post-peer changes, nested/EH
scope restoration, claimed-proof loss with zero original calls, and retained
Connected socket pair/refcount checks and early one-shot cleanup if the extra
getter throws. Compilation does not execute the fixture.

## Duplicate diagnostics only

`--duplicate-diagnostics` creates `native-duplicate-diagnostics`. Its delta from
the verified duplicate build changes safe scalar output only: no guard result,
admission rule, original invocation order, game-memory read or query is added.
The unchanged29-check fixture result is reused and no fixture execution is part
of preparing this diagnostic output.

Connect probes add `fresh_duplicate_input_port`, `verified_task_scope_present`,
`fresh_duplicate_reason` and `fresh_duplicate_owner_bits`. Reasons are0 pass,
1 invalid fresh result/readiness,2 base,3 original target,4 caller,5 leaf,
6 frame target,7 input port,8 prior proof,9 owner before peer,10 peer,
11 proof after peer,12 owner after peer,99 not evaluated. Owner bits are set in
the existing short-circuit order:1 ready/base,2 same task,4 same manager,
8 held object equals argument,16 held object equals established socket,
32 same nonempty control,64 Connected,128 connect attempted,256 limit clear.
A missing bit and later bits identify the first refused owner condition.

Three create-only series are limited to8 files each: `selected-task-probe-N.json`
records record7 guard/dispatch outcome; `selected-task-entry-N.json` confirms C++
entry before eligibility/getter work; `selected-task-scope-N.json` records the
borrow result and whether each frame was armed immediately before original Task.
Borrow reasons are0 success,1 unknown task/invalid span/manager copy failure,
2 manager/owner recheck refusal before getter,3 pair/owner refusal after getter,
99 not observed. PID/birth/candidate SHA and thread link these files to the fresh
run. No pointer, original byte, socket payload or arbitrary object data is output.

`selected_task_matches=false` on the first Connect does not prove missing Task
dispatch: that existing field compares the active held control against the
caller's socket control before OriginalConnectThenObserve establishes it. The
own-connect result is emitted only after actual own capture in that observer.
Input port14000 remains a separate unconfirmed explanation for the new
predicate's refusal; actual peer14030 alone does not establish the input value.
