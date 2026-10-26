# COMPANION-MAGE LRS1 WM_COMMAND correction v2

WRITER_RELEASED. New private v2 only; v1 and all original/common/Test/queue/
ACTIVE/DLL/NativeInput/Store/game/port state preserved. Runtime resources0.
primitive_source_ready=true; source_ready/test_ready/ui_ready/UI_ready/
runtime_ready/action_ready/save_ready=false. RUN_COMMAND=null.

Main review found a real v1 bug: the first WM_COMMAND branch unconditionally
returned0 before the later SettingsCommandOnOwner branch. The v1 fixture producer
bypassed WM_COMMAND and therefore never verified that actual button path.
V2 removes only that first dead branch. The exact old bytes can be recovered
by reinserting that single line; all other seven copied production files are
byte-identical v1. No owner/revoke/WindowProc/lifetime/IO/Host semantics changed.

One new bounded actual OS case passes. Authenticated bootstrap/retained process/
Job/one pipe -> LRS1 real owner OPEN/paint -> actual enabled Follow and Station
BUTTON handles. The established owner thread calls Follow BM_CLICK, causing the
real Button BN_CLICKED notification through corrected production WM_COMMAND,
SettingsCommandOnOwner and native TakeSettings/Run. The wire peer receives and
validates exactly one signed LSQ1 follow/sequence1/current epoch1/revision7,
actual owner HWND/thread. The source fixture macro/Produce/BurnFixture is absent.
After first click burn0->1, both controls disabled; a second BM_CLICK on the same
disabled Button leaves burn1 and produces no second LSQ1. UNKNOWN is the only
server response (no fabricated save), then actual owner UNKNOWN paint and signed
revoke/DestroyWindow/NCDESTROY/close receipt. Native and issuer original absolute
deadlines unchanged, focus/activation unchanged, retained0, cleanup COMPLETE.

This is isolated synthetic button input on a disposable non-input desktop.
It is not a human input, actual game click, selected Host/Store save, Factory,
DLL/NativeInput or gameplay success. Native helper builds WITHOUT
LOCAL_SETTINGS_FIXTURE; production compile also forbids that macro. MSVC x64
C++17 /W4 /WX compile/link PASS. No broad v1 test or parent verifier rerun.
V1 multi-action/MAC/epoch/UNKNOWN/pure-current evidence remains reusable for its
unchanged paths; the v1 button path is explicitly failed and corrected here.

Same-State/pipe/single-reader max16 requests and inherited absolute <=30s policy
are unchanged; no lifetime reset or retry is added. ITEM LIT1 remains data-only
unjoined, inventory/GEAR unavailable, COMBAT behavior and distance editor remain
missing, attack magic deferred. First product edge remains complete LRS1
Factory/Plan/launcher/native DLL + strict NativeInput/owner lifecycle/actor click
selection; root will relink and repin v2. Existing held v1 queue/source/DLL/
NativeInput are not changed by this artifact.

Read-only verification after finalization (no build/OS rerun/parent verifier,
bytecode/regeneration or output writes):

    python -B <absolute-this-directory>/verify_readonly.py

Manifest has full absolute output/input pins, including every v1 file's original
hash/size/mtime. Source inverse and all unchanged copy hashes are verified.
Root owns review/selection; writer released, resources0.
