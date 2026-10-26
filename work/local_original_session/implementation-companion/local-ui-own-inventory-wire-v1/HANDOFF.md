# COMPANION-MAGE own inventory wire v1

WRITER_RELEASED. Source/test/UI/runtime/action/save ready all false;
RUN_COMMAND null. Primitive codec/native data paint only. No common/original/
Test/queue/ACTIVE/Store/port/game/other worker files changed. Existing main dirty
checkout preserved. No branch/worktree/commit, selected DLL or focus/input work.

`inventory_wire.py` adds a bounded LIT1 data-only encoder for actual ITEM fa9b
CompanionInventoryRows. It requires that exact SourceModule and nominal actual
owner/context/rows, original issued rows identity, current selected state/row/
operation, active/lease/actor generation/ui_epoch, same canonical member/frame/
asset revision, and exact current selection object. It calls the existing
owner's current recapture, without a UID lookup or a new lease/Binding/Store.
Use the original model component's direct open_items/select_item first; this
codec does not wrap those direct-call-frame methods. No await or IO is added.

`encode_inventory(owner, context=..., rows=..., selection=..., binding=..., key=...)`
returns data only. Before any eventual serialized send, selected caller must
call `require_current(owner, context=..., data=..., binding=..., key=...)`.
The retained dataclass is not a capability: that call rechecks the actual rows
and exact retained context, reconstructs the canonical display bytes, and
compares them to the supplied wire. A fabricated ticket or serialized UID
cannot replace original owner-issued rows or alter their displayed contents.
Binding/key are presentation correlation/authentication data, not item authority.

Wire is fixed928B: LIT1/version1/inventory1/DATA_ONLY1/gearUNAVAILABLE2;
size928 and sequence1; opaque16B display token, original OPEN sequence/native
display epoch/display sequence, row count<=32, selected ordinal or FFFFFFFF,
asset/member revision and SHA256 of actual inventory frame. 32 fixed24B slots
contain ordinal/template_bits/u64 quantity/reserved; unused slots are zero.
HMAC-SHA256 covers the first896B with domain
`LOCAL-COMPANION-OWN-INVENTORY-V1` plus terminating NUL. No character/account/
actor/item UID is serialized. Exceeding32 rows refuses rather than truncating.
Names/catalog labels are unsupplied: native text honestly labels template IDs.
Equipment always explicitly UNAVAILABLE; absence is not forged empty gear.
No item use/equip/transfer/save request, native action token or success is issued.

`ui_inventory_data.hpp` validates the exact fixed schema, HMAC, display binding,
reserved bytes/unused rows, ordinal and selected range; every failed parse clears
the entire output. It formats bounded text only. `ui_inventory_publication.hpp`
adds a standalone one-attempt native data paint adapter. It copies an owning
fixed projection under a short lock, performs formatting/GDI outside all locks,
rechecks current/epoch, and clears the owner stack/text after use. Publication
expires at min(original remaining session deadline, now+250ms), never refreshes,
reissues, or resets a deadline. Revoke clears data immediately without waiting
for owner drawing. A resumed paint erases its stale pixels before accepting a
current diagnostic. Already displayed pixels require the owner to paint again;
there is no off-thread GDI or claim that parked owner pixels disappear instantly.
Paint observations are local diagnostics, never LOR1/render/protocol receipts.

Actual focused checks: production header compile and isolated harness MSVC x64
C++17 /W4 /WX PASS. Two disposable non-input desktop processes, 50 checks PASS.
Python synthetic codec fixture -> native CNG HMAC/parser -> real CreateWindowEx
NOACTIVATE/WM_PAINT/BeginPaint/TextOutW/EndPaint draws two inventory rows and the
explicit equipment UNAVAILABLE line. The second process pauses after actual
first inventory-row TextOutW, withdraws from worker before owner resume, then
observes genuine stale FillRect/EndPaint, no current draw, erased stack and
real window/worker/event/desktop cleanup. Partial/bad-MAC/stale display epoch and
four correctly authenticated malformed schema cases refuse. Synthetic fixture
quantity 2^32+1 proves u64 survives projection. These fixtures are NOT actual
ITEM/Host/Store/lease/Factory/game proof. No actual rows runtime success claimed.

Exact first missing callable: no selected Factory/Host full-interface bootstrap
currently binds this codec's actual ITEM owner/model data methods, authentic
NativeOpen mapping and a serialized inventory phase. The peer composite owns
LOP1 -> LMB2/LMR2 -> LMC1/LMA1 -> LMZ2 on one authenticated State. A future
inventory continuation must run ONLY after exclusive completion of that phase,
on that SAME authenticated State/key/pipe and its original remaining deadline;
no second reader, new ACK/key/capability/deadline or concurrent LUI2/LOP1 consumer.
This directory deliberately supplies no State/pipe IO phase or parallel reader.
The selected adapter must also attach this paint adapter to the genuine v4
owner WM_PAINT/revoke/destruction lifecycle without minting an OPEN/render
receipt from parser/publication success. Actual GEAR current owner/action/
canonical request/once/save owners remain separate missing contracts. Attack
magic policy remains deferred. User-visible product inventory path is unselected.

Explicit own-output build/check commands (not game RUN):

    cmd /c work\local_original_session\implementation-companion\local-ui-own-inventory-wire-v1\build.cmd
    python -B work/local_original_session/implementation-companion/local-ui-own-inventory-wire-v1/run_isolated_once.py

After finalization use ONLY the read-only verifier, never rebuild/regenerate:

    python -B work/local_original_session/implementation-companion/local-ui-own-inventory-wire-v1/verify_readonly.py

Input pins, compiler project dependencies, new-source diff and exact output pins
are recorded locally. Original parents stay immutable. All owned resources0.
