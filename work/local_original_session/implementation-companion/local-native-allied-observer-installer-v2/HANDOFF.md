# COMPANION-MAGE — exact CALL installer feasibility v2

**First missing: a source-qualified, CALL-preserving patch transaction and retirement boundary in the selected composite host for RVA4B8E7.** The selected host's existing Detours operation cannot redirect this CALL to the v1 wrapper with its required stack contract. No installer stub, E8 write, thunk, linkable admitted_source or runtime receipt was created.

SOURCE_ONLY / BLOCKED_SOURCE_INPUT / observer UNINSTALLED / implementation_complete:false / test_ready:false / packet_test_gate:false / runtime UNRUN / WRITER_RELEASED.

## Exact source result

The retained packet source records `4B8E7 CALL60B50`, followed by4B8EC release of caller's O.control. Derived five bytes are **E8 64 52 01 00**, relative displacement +0x15264 from4B8EC. Their SHA256 **679abdebd665b4e0d656e111b266f47bc7a97547e3d71135d0b69f4ce998d272** exactly matches the retained instruction hash. This establishes static expected bytes, not bytes or identity at a running image. No image, process, game or memory read occurred.

REA311 source3 FINAL_IMMUTABLE and v1 compile result are reused. RCX=S/RDX=O/R8=P, normal RAX=O, caller O at RSP+40 and receiver Pair at RSP+50 remain the candidate's exact ABI. A replacement **CALL** would push4B8EC and preserve the v1 wrapper return-slot arithmetic; changing that instruction to JMP would not.

## Selected mechanisms actually inspected

| Selected source | What it supplies | Exact limit here |
|---|---|---|
|`native/mark_on_install.hpp` `Production`, `InstallWith`, `GuardedInstallWith`|Actual manual_move owned UI-context, process/birth check, two bounded thread snapshots, per-thread handles, module pin, supplied Ops call and UNKNOWN on uncertain install/cleanup|It delegates installation to fixed interposer/FrameInstallOps. It is not an arbitrary code-write transaction or a CALL-site patch API. No callsite4B8E7 operation is supplied.|
|`native/frame_interposer.hpp` `FrameInstallOps::install`|Detours begin/enlist/attach/abort/commit with exact target/trampoline prefix checks|Fixes B54E60's five-byte leaf home-slot MOV. `frame_source.inc` covers B54E60/B54EF5/B540C2/E42F0 only. No4B8E7/60B50 source admission, CALL patch or native drain.|
|Vendored Detours4.0.1 `src/detours.cpp`|Real enlisted-thread SuspendThread, transaction handling, jump-bounded trampoline allocation and IP relocation for its own pending DetourOperations|x64 commit invokes `detour_gen_jmp_immediate`, which emits **E9** at the target. DetourAttach(4B8E7,wrapper) removes the CALL push; wrapper receives4B690's caller stack, not4B8EC/return-slot. Ordinary Attach is not a transparent CALL rewrite. Its IP adjustment/rollback metadata describes registered DetourOperations, not an ad hoc external E8 write.|
|`native/item_mark_on_interposer.hpp`|Fixed validated-image entry API and original normal-return ASM ABI; caller is explicitly required to supply an approved source/owner and quiescent boundary|Not generic CALL patch owner. Product detach is absent; mock detach is behind ITEMMARK_MOCK.|
|`native/screenshot_completion_wrapper.hpp` `ChangeCell`|Eight-byte data pointer CAS, verified readonly image cell, protection restoration and narrow callback lifecycle|Not a five-byte executable code patch; cannot reuse it as instruction-cache/PC-safe CALL publication.|
|Companion `local_foreground_hotkey.hpp` `Install`/`Close` and native `host_lifetime.hpp`|WH_GETMESSAGE callback code pin, SRW shared callback lifetime, revoke/unhook/DrainPending and same UI owner|The v1 native At4B8E7 wrapper never acquires this lock/entry contract. A hotkey callback drain does not drain ActorNotify threads or an in-flight original60B50 and wrapper.|

The selected composite native tree and selected companion native package contain no4B8E7/60B50 installation/admission reference. This is a bounded selected-source result, not a repository-wide absence claim. Sources/locators are preserved in evidence.json and manifest.json.

## Requested installation conditions

| Condition | Status / implication |
|---|---|
|Exact live image+E8/source hash verification|Static E8 and hash proven above. Actual image allocation/protection/hash and retained source-domain admission remain UNSUPPLIED; selected FrameSource targets another path. Matching five bytes alone would not admit the whole original60B50/registry source domain.|
|rel32 wrapper reachability|UNKNOWN without a linked wrapper address and admitted image base. Direct E8 is legal only for signed32(wrapper-(callsite+5)); no address/range fabricated.|
|Near thunk without undefined unwind|No selected CALL-preserving near-thunk source/lifetime is supplied. Detours near allocation is internal to its E9/trampoline operation, not an owned reusable E8 thunk API. No thunk allocated or modeled as installed.|
|Patch-thread ownership/suspension|Existing owner/enumeration guards are reusable ingredients. There is no selected operation binding those actual thread handles/suspension/PC handling to this five-byte E8 replacement. No claim that two snapshots exclude all future threads.|
|Immutable admitted_source lifetime|v1 `admitted_source` remains undefined. Existing process-lifetime code pin does not publish or protect this binding. No blind base-only definition added to make link succeed.|
|Failed install rollback|Detours rollback applies to its own E9 operations. No selected E8 transaction restores byte/protection/cache/state and handles partial/unknown outcomes. A pure model would not supply that native operation.|
|Retire after in-flight native drain|v1 contains TLS samples/reentry detection, not cross-thread entry/drain/retirement ownership. Existing WH_GETMESSAGE lifetime lock does not cover it. Native drain remains UNSUPPLIED; a zero counter read without quiescent publication would not prove drain.|

## Next exact input

The required source input is the **selected composite host's CALL-preserving install/retire operation**, bound to its actual host source admission and owned quiescent patch/thread boundary. It must leave the CALL semantics intact, route to a linked reachable wrapper or source-owned correctly unwound near thunk, publish immutable admitted_source before entry, keep code/binding alive across original exceptions/reentry, transactionally handle failed/partial install, and restore original E8 before draining admitted native entries. Until then, importing Detours or defining the base is insufficient. This is a missing native source contract, not a request for renewed user authorization, a new REA scan or native execution.

If that operation is later implemented, bounded pure rel32 and rollback tests can check its real arithmetic/state machine, followed by object/link/unwind checks. No such tests were invented for a nonexistent installer. v1 compile PASS is reused, not rerun or broadened. Current-unit validation is static expected-E8/hash equality and inspection of selected mechanisms only; runtime/link/install/retire are NOT RUN.

No positive publication, current selected world, LOCAL generation, click/settings, pose, absence or retirement receipt follows from this assessment. Independent packet work remains unaffected. Only this new private directory was written; shared/original/queue/ACTIVE/Test/game/port/REA writes and execution were zero.
