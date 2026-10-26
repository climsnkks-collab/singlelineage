# COMPANION-MAGE LOCAL post-ACK transport v1

WRITER_RELEASED / source_ready:true **process-authenticated UNBOUND transport only** / test_ready:false / UI_ready:false / game_runtime:UNRUN.

Private descendant of issuer-v2 manifest da7ba96dcd82df2395c628edf59346057f9246ef456da3ca31ed30e9c3b6136d and native-bootstrap-reader-v1 manifest 9b148c40e36a06e1887c63343f9e9487465c65271ca4d438fc9a43c5fb049768. Exact absolute parent pins and compiler-selected inherited source pins accompany this directory. Existing dirty main and all original/common/Test/queue/ACTIVE files are preserved. No game/DLL load, game port, input/focus, branch/worktree/commit or Host invocation occurred. Main owns review/queue/selection; this worker did not register a queue item or send product messages.

## Supplied scope and exact first remaining blocker

The existing single authenticated pipe now carries a bounded bidirectional LOCAL REQUEST_MODEL command and an explicit UNBOUND model. UNBOUND is backed by the real issuer's existing selected_binding=UNIMPLEMENTED; it does not fabricate Host.view, a character selection, panel state or action authority. The only supported action mask is zero. No public API takes UID, Python object id, Host callback or gameplay command. There is no OPEN/RENDER/CLOSE message or native control creation.

The next missing producer remains actual selected Host registration under the canonical Broker row operation, plus a coherent Host/panel pending/open/destroy/drain lifecycle. This transport intentionally cannot bind that authority. Do not map its model or ACK to a non-None synchronous interface.open result or a completed interface.close. A later selected protocol must supply an exact paired descendant and must retain real writer/row/selection/direct/companion lease/actor generation/epoch server-side. Native UI and Host actions remain UNKNOWN/UNIMPLEMENTED.

## Wire: lineage-local-ui-payload-v1

Authentication/bootstrap/hello/ACK remain byte-identical v1. Payload starts only after the exact ACK is consumed by native; issuer sends no unsolicited model in the ACK tick. All integers below are unsigned little-endian.

Every frame has exactly 16 header bytes: magic ASCII LUI1 (offset0,4 bytes), version1 (offset4,u8), kind (offset5,u8), flags0 (offset6,u16), sequence (offset8,u32), payload_length (offset12,u32). No extensions, optional fields, textual values or UID exist.

- Native→issuer kind1 REQUEST_MODEL: payload_length4, payload u32 opcode1. Total20 bytes.
- Issuer→native kind2 MODEL: payload_length8, payload u32 binding_status1=UNBOUND and u32 supported_Host_actions0. Total24 bytes. Model echoes the exact request sequence; it does not ACK any Host operation.

Sequence starts1, strictly increments, max16 total requests/models per process attempt. Stop-and-wait: one outstanding request, one fixed-size native atomic snapshot and no queued list. Duplicate/replayed/out-of-order/unknown kind/version/flags/opcode/length and an observed >20-byte request are refused and close/revoke this pipe. The issuer reads at most21 bytes to detect observed excess; byte-pipe coalescing is not a proof of the sender's issuance time, so stop-and-wait is a semantic peer contract rather than a packet-boundary guarantee. Full ambiguous commands are never retried. No reconnect, reissue or selected-revision reset exists.

## Lifetime and actual composition

LocalUiChannel base method AST is unchanged: exact retained owner/handle/PID/birth/Job/key guard and one-use capability admission remain original v2, including true post-resume deadline activation. New LocalUiTransport subclass serves the same pipe from the inherited launcher tick. Every authenticated poll rechecks retained owner and connected actual client PID. Each tick performs at most one nonblocking byte-pipe ReadFile or WriteFile, with bounded20-byte accumulation and retained24-byte output suffix on zero/partial NOWAIT writes. The unchanged original admission deadline is not extended.

Issuer imposes one absolute30-second transport deadline starting at ACK write, independent of activity. Native imposes its own absolute30-second deadline starting when it observes complete ACK; neither refreshes per request. Both use monotonic clocks. Normal owner/reselection/close cancellation remains a permanent stop; max16 does not rearm or automatically close a native panel. If issuer ticks stop, native still expires; if native stalls, issuer expires while ticking. This bounds explicit waits, not undocumented synchronous kernel wall time.

Native bootstrap Run now accepts one optional source-level post-ACK worker continuation. Before it returns/deletes State it invokes that continuation only after the unchanged full ACK/server-current/cancellation checks. Production WindowsOps calls that continuation on the original one-attempt pinned worker. State retains the same pipe/process handles, event, heap OVERLAPPED/buffer and cancel event through the payload session. All actual pipe I/O reuses original Io/CancelIoEx/2000ms drain. If completion is unknown, the unchanged retained State path keeps every request-owned object alive until process exit; no cleanup/UI-close success is inferred. UNKNOWN retention is source-verified, not an induced OS failure PASS.

Original Lifecycle Start/Revoke/Join/Stop, module pin, cancel-event process lifetime and zero-budget UI join behavior are unchanged. Production ABI/F101/hook/Host files are byte-identical; diagnostic.cpp only remaps existing include aliases to this private sibling. Compiler sourceDependencies confirms this descendant's transport/reader/lifecycle/Host/ABI are actually selected.

Native starts one REQUEST_MODEL after ACK. RequestModel() offers bounded lock-free atomics for a later owner-thread caller; its true result only admits a refresh to the fixed mailbox. It never reports delivery or UI success. It returns false before authentication, while one request is outstanding, after16, or after worker exit. Snapshot packs sequence/status atomically and only publishes after complete exact24-byte response validation. The worker stays alive awaiting mailbox/cancellation/deadline, then invalidates authenticated, drains pending IO and retires State or retains UNKNOWN. No UI thread waits, native UI calls, callbacks or extra work queues were added. Unchanged owner invalidation remains permanent; reconnect/reselection cannot rearm Start.

## Actual verification and reproducible commands

From project root:

1. `cmd /c work\local_original_session\implementation-companion\local-ui-post-auth-transport-v1\build.cmd` — PASS, production translation unit compile-only MSVC x64 /std:c++17 /W4 /WX.
2. `cmd /c work\local_original_session\implementation-companion\local-ui-post-auth-transport-v1\build_helper.cmd` — PASS, isolated executable /W4 /WX. No production DLL linked/loaded.
3. `python -B work/local_original_session/implementation-companion/local-ui-post-auth-transport-v1/check_transport.py` —13 actual isolated disposable retained process/Job/named-pipe cases PASS: two-model roundtrip; real fragmented7-byte model writes/full native reassembly;16 requests; cancellation during actual pending model read; native150ms deadline during pending model read; issuer30s deadline; retained owner revocation; malformed header; sequence; unsupported opcode; excess request; replay; malformed model. All native retained=0, authenticated=0 and post-exit RequestModel=false; all owned artifacts/handles/processes/Jobs cleaned. Test-only clock injection advances issuer deadline without waiting30s, and native150ms case calls the same bounded Session with a shorter test budget. Default source budgets remain30s. Wrong PID/capability/birth and original lifecycle checks reuse pinned prior PASS; no unchanged full game sequence rerun.
4. `python -B work/local_original_session/implementation-companion/local-ui-post-auth-transport-v1/verify.py` — exact parent/inherited pins, method inverse/AST, unchanged ABI/F101/Host/lifetime, compiler private includes and13 recorded OS results.

isolated-verification.json stores bounded real results. manifest.json pins deliverables and diff.patch records exact source changes. Runtime game RUN_COMMAND:null. Test-ready and UI-ready remain false; no selected Host/panel exists, OPEN/CLOSE/native callback drain are UNKNOWN. All helper processes/Jobs and worker resources are released; unknown-drain path was not forced and is never called PASS.
