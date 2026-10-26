# COMPANION-MAGE — v4 unlocked native drawing / revoke correction

**WRITER_RELEASED / primitive_source_ready:true / feature source_ready:false / test_ready:false / ui_ready:false / runtime_ready:false / RUN_COMMAND:null.** This corrects Main's concrete v3 review finding. v3 manifest `265e99d685c25914bcdcbd63574f30435c0d475c29d2d532c48b88ea134eb3a1` and all v3 files remain frozen and unqueued. v4 is a new native candidate only; no product OPEN bridge, settings command or save is implemented.

## Exact correction

v3 DrawOnOwner held the publication lock across UTF conversion and GDI TextOutW. An off-thread Withdraw/IO Revoke could therefore wait for slow/reentrant native drawing. That behavior is not accepted as a bounded revoke guarantee. v4 moves every conversion/GDI call outside publication locks.

`ui_display_publication.hpp::DrawOnOwner` first allocates an owning Projection on the owner stack. Under one short lock it checks current owner/live/expiry and copies the fixed model plus epoch, sequence and actual expiry deadline. It releases the lock before UTF conversion, formatting or GDI. The stack is independent of publication storage and is not a borrowed pointer. Worker withdrawal zeroes the publication without waiting for drawing. The old value may exist only as that active call's owned stack copy; a scope destructor zeroes the entire Projection on every exit, and individual text temporaries are zeroed after use. Nothing is cached across calls.

After drawing, a second short lock expires/checks the exact current epoch/live/owner/deadline. A revoke/replacement/expiry during drawing makes the returned draw receipt noncurrent. `ui_owner_panel.hpp::PaintOnOwner` retains its existing second publication check and full-client erase on a noncurrent result before any current display receipt. It now counts `stale_erases` only after actual successful FillRect and EndPaint; current draw receipt also requires actual EndPaint success. This is native evidence, not a success flag set by test code. Already displayed pixels still cannot be cleared off-thread while owner is parked; the contract is invalid authority immediately, erase before accepting the resumed paint, and UNKNOWN close until actual owner destruction.

All GDI/User32 executes on the established owner and outside the publication lock. The unchanged pure owner visitor remains restricted to bounded pure computation. No model/reference escapes the draw call. The original one-attempt30s/16 requests/250ms LOCAL retention, no automatic refresh/reissue, private OpenIntent constructor and absent product bridge remain. Actual CreateWindowEx, NOACTIVATE/control disabling, DestroyWindow/WM_NCDESTROY/callback-drain proof are preserved. Original forwarding/F101/ABI/IO ownership and all unmodified parent files are byte-identical copies; only compile alias destinations/build output path move to v4.

## Focused actual verification

Production translation unit MSVC x64 `/std:c++17 /W4 /WX /c`: PASS. Actual compiler dependencies include v4 publication, panel, original private host/lifecycle and original game source dependencies. No DLL is linked/loaded or paired NativeInput selected.

Two actual isolated native child processes, **46 checks PASS**:

1. Publication Withdraw while the owner is paused inside genuine WM_PAINT after the first successful native TextOutW.
2. Existing IO lifecycle Revoke at that same point, exercising panel metadata revoke plus publication withdrawal.

The test seam is compiled only with `LOCAL_PANEL_PRIMITIVE_TEST` and `LOCAL_PANEL_SLOW_DRAW_TEST` in `slow_draw_checks.cpp`. It creates a genuine owner window on a new non-input desktop, uses the existing test-only intent factory and actual message hook, then waits immediately after a successful real GDI output. Production defines neither flag. It does not fake paint/OPEN/CLOSE receipts. Worker withdrawal must return while the owner remains paused and before the worker signals owner resume. A 2s safety timeout fails rather than impersonating successful resume. Both runs completed withdrawal in the recorded GetTickCount64 resolution of0ms (a bounded test observation, not general runtime performance). It then verifies actual stale-pixel erase/EndPaint, no current draw receipt, owner-stack erase path, actual owner DestroyWindow/WM_NCDESTROY/callback drain, and resource/desktop cleanup. No input desktop switch, game, focus action or input simulation occurs.

The v3 96-check nonfocus window lifecycle/typed pending/expiry/negative receipt evidence and production private-constructor C2248 result are reused only for unchanged contracts by exact parent pins. They are not described as v4 tests. The new46 checks cover the changed drawing/revoke path; no repeated full game or parent scenario is added.

Build commands: `cmd /c work\local_original_session\implementation-companion\local-ui-panel-owner-v4\build.cmd`; focused test build `cmd /c work\local_original_session\implementation-companion\local-ui-panel-owner-v4\check_slow_draw.cmd`. `test-runs.json` records exact actual EXE/fixture pins and argv; `isolated-verification.json` preserves bounded raw results. Post-final verifier `python -B work/local_original_session/implementation-companion/local-ui-panel-owner-v4/verify.py` only reads/hashes/inspects recorded evidence, never rebuilds, runs native code, regenerates files or writes bytecode.

## Unchanged first product blocker

The source-backed 4F13 companion click calls Host `_open_from_actor_click_locked` and currently returns empty S2C. Frozen old Host still assumes synchronous `interface.open(layout='ATS')`/non-None. A selected Host descendant must replace that with separate LOCAL pending issued intent and actual asynchronous native receipt. Exact NativeOpenEndpoint submit/read/revoke and production `local_ui_selected_open::Bridge` must prove current issued object/row/selection/direct and companion leases/actor generation/owner/session/ui_epoch, associate actual native display epoch plus display sequence, and retain UNKNOWN/no retry on uncertain delivery. intent_sequence and display_sequence differ. No displayed model/boolean/Checkpoint may mint OPEN. v4 leaves that bridge unimplemented and never auto-opens from model receipt. Parent HANDOFF has the detailed API and proof boundary unchanged.

Final settings still require real mode changes, own equipment/inventory, basic combat settings and saving. Disabled controls are not completion; attack-magic policy remains later work. Actual game panel OPEN/CLOSE/render/focus/settings/save remain UNKNOWN/UNIMPLEMENTED. The single-use/short retention primitive is not a reusable settings UI.

Only this new private directory was written. Frozen v3/publication/producer/native input, original/common/Test/queue/ACTIVE and dirty checkout are preserved; no branch/worktree/commit or queue publication. Isolated EXEs/windows/hooks/desktops closed, owned resources0. Main reviews/queues this replacement; v3 is preserved, not overwritten.
