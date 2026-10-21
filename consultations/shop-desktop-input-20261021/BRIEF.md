# SHOP input / owned desktop proof: focused implementation consultation

Scope is one complete feature: preserve a legacy Windows client's original NPC interaction, menu, BUY/list/confirm, local-server transaction and independent client inventory observation, then clean up the same run. Only our Python controller excerpt is public. No original binaries, proprietary client source, raw reverse-engineering output, user saves, private logs or credentials are supplied. This is not a project-wide strategy review.

## Confirmed boundary

The local backend's original decoders/menu/list/trade/atomic Store commit/transport DRAINED/current inventory adoption and cleanup are exercised in source fixtures; they are not actual game UI success. A driver preserves receive ordinal/publication/selection correlation, then independently reads client inventory scalars after adoption. The actual game can log in, select, enter the world, restore inventory, and produce a fresh framebuffer capture on an owned non-input desktop. Root directly measures a fresh capture and supplies explicit client pixels; there are no default coordinates.

The retained process handle, process creation identity, original image identity, Job membership and HWND ownership are checked. The desktop is retained by a lease, not recreated for input. The original input desktop is never switched or given focus. A short-lived controller helper joins that existing desktop and uses the window DPI context. Helper desktop/DPI context restore in finally. Window containment is checked via EnumDesktopWindows on the owned desktop, IsWindow, GetWindowThreadProcessId matching the expected UI TID and retained process PID, and a retained-owner/native HWND check. Mouse Move/Down/Up are queued only after these checks, with partial UP cleanup if necessary.

A normal existing command bridge already posts to the same owned HWND after helper join + window/TID/PID/current-owner/non-input checks. Mouse click additionally demands GetThreadDesktop(target UI TID) to return a readable handle naming that desktop. The command bridge does not perform that remote-thread desktop query. This difference is source fact, not permission to delete validation.

## Three blocked implementation attempts and limits of attribution

A: a controller-side external current geometry query could not establish the desktop query. No point or click. We moved geometry query to the retained desktop helper and preserved its identity/DPI checks.

B: the owned query/capture match and directly measured point succeeded, but click failed PRIVATE_CREATED_THREAD_DESKTOP_MISMATCH before any mouse message. The error did not distinguish helper join from target UI check. We did not assume error5 or a DPI cause from this attempt.

C: helper join, inventory restore/client observation, owned geometry and its immediate pre-click requery all succeeded; fresh explicit point was consumed. The newly instrumented existing query proved stage TARGET_UI_THREAD, status UNKNOWN, reason THREAD_DESKTOP_UNAVAILABLE, GetThreadDesktop returned NULL and saved last error was 5. No mouse message was attempted/queued. Thus this run establishes the remote target query denial, not a helper join failure or readable foreign desktop. An unrelated inventory prewrite error in an intermediate run was not reproduced and is not claimed solved. A separate normal Quit issue is open and must not block this feature's independent work.

Across A/B/C there is progress in measurement/classification but no actual NPC input/menu/trade. We are consulting the current feature approach after three blocked input implementations; we are not claiming all three had the same actual Win32 error. Do not recommend repeating unmodified runs to fill a quota.

## Current assumptions and alternatives requiring judgment

The extra remote-thread GetThreadDesktop result is currently treated as mandatory click authority. Is that the correct proof boundary, or is it coupling an otherwise proved owned HWND/UI relation to a cross-process query that can legitimately fail? We need to keep the meaning of genuine desktop/window/owner/UI identity, not merely remove a check or rename a bool. Candidate alternatives are an authoritative HWND-on-owned-HDESK proof with fresh TID/PID/owner checks, or a query/input operation dispatched through an already existing same-process/UI-thread bridge if an additional original contract is actually required. We have not implemented either as an excuse to ignore error5.

## Non-negotiable constraints

No ACL/DACL/security-token change, elevation workaround, new desktop, SwitchDesktop, foreground/focus/cursor manipulation, SendInput/global keys, uncontrolled thread/injection, guard bypass, fake current receipt or server-only success. Reuse existing original input/command bridge semantics where justified. Preserve changed-owner/selection/desktop/window refusal, signed coordinates/bounds/DPI, same-run cleanup and first exception/partial UP/finally restoration. Reading the saved error from the existing call is diagnostic only. Existing tests use explicit Win32 doubles and do not establish actual game permissions. Root alone installs/runs the next changed feature test; no standalone extra game run or deadline extension.

We want one prioritized implementable breakout for this complete SHOP input-to-client-consumption feature, the wrong assumption if any, exact proof obligations/caller-callee ownership, a decisive negative case and the next minimal real observation. Avoid a new observer/receipt framework or analysis-only loop. Clearly separate documented Windows guarantees, inference and missing source facts.
