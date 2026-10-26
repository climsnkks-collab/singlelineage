# COMPANION-MAGE actor click locked Host v2

WRITER_RELEASED. Source-only Host split; test_ready:false / runtime UNRUN.

Exact parent is actor-click-v1/tools/local_original_session/companion_host.py SHA256 591c4b189a7d5b9b86943baf637a72cac5bb423fe4d84bfb6deb1ab24cce9846. The immutable descendant is tools/local_original_session/companion_host.py in this directory. product.diff is the full single-hunk delta. No Broker, parser, packet sender, opcode, route, common client/API, existing source, profile, queue or execution owner changed.

The public asynchronous open_from_actor_click still resolves the same unique writer row and acquires its existing broker._row_operation once. It delegates to the new synchronous private _open_from_actor_click_locked(writer, row, *, actor_uid, actor_generation). A future actual router already inside the original operation can use that helper without reacquiring the canonical scope or legacy asyncio lock. It must resolve actor generation from genuine server registration, never from packet bytes or a caller-created object.

The helper requires _row(writer) is the supplied row: existing _row requires its original operation_lock locked, live/unfailed/unjoined row, live broker and unique writer. It repeats the same UID type/range boundary and preserves exact experience_participant/current owner writer, actor UID, generation identity, actual separate character lease and non-direct UID checks. It calls the original _open_panel_locked unchanged; the original panel/command callback/epoch body remains byte-identical. No alternate panel state or settings authority is created. This private locked method follows the existing Host locked-caller convention: the caller owns the original broker scope; it is not a capability for unrelated tasks merely observing a locked row. No new route exposes it.

Verification: existing v5 Host fixtures 5 PASS, actor-click-v1 fixtures 2 PASS, one bounded locked-entry fixture PASS (8 total). The new fixture checks native entry acquires exactly once; the helper inside the same scope does not reacquire/yield/release; identical panel/callback/epoch reuse; wrong UID, generation, row and unlocked entry refuse; dismissed actor refuses. Existing old-panel callback test preserves stale epoch refusal. AST inspection confirms only public open_from_actor_click changed, one private helper added, and every other Host method including _open_panel_locked unchanged. Compile PASS. The fixture initially failed before running tests because Python namespace package paths do not support insert; the local runner now sets a list of lookup paths. No product behavior workaround was needed.

Reproduce from project root:

    python -B work/local_original_session/implementation-companion/actor-click-locked-v2/verify_host.py

The runner explicitly installs this private Host module, reuses existing extracted v5 actor/controller/CharacterStore fixtures, and creates disposable temporary fixture state only. These passes are source boundary evidence, not genuine summon, registered actor publication, packet click, native ATS/settings panel or game success. Existing saved Test inputs are untouched. Genuine summon, native interface/response and account-child Host lifetime remain open, so there is no runtime command or Test-ready claim.
