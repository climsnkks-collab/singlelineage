# COMPANION-MAGE native hotkey package v1

PRIVATE_LINKED_CANDIDATE / implementation_complete:false / test_ready:false / runtime:UNRUN / WRITER_RELEASED.

Parent host manifest: `059463a3f25842448abfbe04089713574c0329c590aa27a715e7060a0a47d67e`. Only this new private directory is owned/written. Original/shared/Test/queue/ACTIVE files were not edited. Existing main dirty checkout was retained; no branch, worktree or commit was made. No game process, port, hook install, DLL load, focus change, message post, keyboard/mouse input or native sender was used.

## Linked artifact and source selection

`own-login-bridge-companion-hotkey-v1.dll`, 615936 bytes, SHA256 `236d0208a03fd09369fb704165960170f3c4c6316cab88e5983f288823e9d3ae`.

This compiles the parent host's diagnostic/auto_ok/abi_bridge/host-entry/host-lifetime copies, with only the six include-alias targets in diagnostic changed from the parent host directory to this package. Its auto_ok/abi_bridge and lifetime code are byte-identical to the parent. The genuine original callback/forwarding and sender lifetime behavior are inherited unchanged. All 120 input pins, including both exact ASM sources and static libraries, original composite build/launcher/manifest, and all repository compiler dependencies, are in `input-pins.json`. Two private ASM objects are assembled and linked with the private diagnostic object; libraries are copied byte-for-byte from the original composite.

The candidate deliberately has its own output filename and private `.def` LIBRARY identity `own-login-bridge-companion-hotkey-v1`. The `.def` export names and ordinals 1–27 are unchanged. The first link with original LIBRARY name plus private output name correctly failed LNK4070/LNK1218 under linker /WX; changing only this textual LIBRARY line to the private candidate name resolved that identity mismatch. No binary patch or warning suppression was used. A future loader selection must stage the pinned bytes into the existing `own-login-bridge-dg49.dll` loader slot in a Test-owned NEW runtime copy and replace the product's corresponding hash and bridge_artifact together. Original images/import names, exported ABI and existing source pin policy were not modified. No candidate import library is supplied to modify any client image.

## Verification/reproduction

From workspace root:

```
python work/local_original_session/implementation-companion/local-native-hotkey-package-v1/prepare.py
cmd /c work\local_original_session\implementation-companion\local-native-hotkey-package-v1\build.cmd
python work/local_original_session/implementation-companion/local-native-hotkey-package-v1/verify.py
```

These are build/static commands only, not runtime commands. The package was built with MSVC x64 C++17 `/W4 /WX /fp:strict /EHsc /O2 /MD /LD` and linker `/WX`. Full DLL link PASS; actual PE AMD64/PE32+ DLL flags PASS; actual dumpbin 27 export/ordinal pairs match original `.def`; compiler `/sourceDependencies` all 357 includes match exact parent with the four package-local include paths substituted; diagnostic inverse-source and exact ASM/library checks PASS. `verification.json`, `build.log`, `source-dependencies.json`, `exports.txt`, `headers-dependents.txt` and map preserve bounded evidence. No DLL was loaded to verify it. Build is not runtime acceptance, F101 contact, render or sender drain success.

## Runtime first blockers and remaining owner contract

The inspected original `launcher.py` SHA is recorded in `input-pins.json`. Its selected composite descriptors (`sibling-background-item-drop-pickup-spawn` and `sibling-background-repeated-player-life-spawn`) require background/private non-input desktop execution and existing SourceQuit semantics. Their DLL pins still select the original `18164426...` artifact. The private hotkey's inherited `ObserveExpected`/Install requires the game's genuine foreground current selection and dispatch requires physical Ctrl+Shift+M. There is no approved input-owned Test slot that meets those conditions while preserving the no-focus/no-injection boundary. Consequently, deriving a runnable hotkey launcher by dropping background guards, manufacturing messages or inventing an input slot is unsupported. No launcher copy/wrapper or fake runtime command was added; `runtime-scenario.md` records the exact unresolved inputs and close constraints. Packet tests remain independent and must not wait on this native source.

Additionally, native Finish on a nonowner thread revokes but cannot guarantee another natural owner UI callback. Without that callback, hook/binding remain revoked/pinned until process teardown. It is not Closed and cannot justify DLL unload/reuse. The package preserves this behavior. Deterministic owner-thread close before teardown, if required by a future runtime scenario, still needs an actual existing owner caller or a separately reviewed implementation; no fabricated close acknowledgement is provided.

Original current WORLD/native queued clone lifetime, physical key recognition/once behavior, real sender F101 wire, server session/current acceptance, actor rendering, reselection and reconnect remain UNRUN/UNKNOWN. Main must review actual package pins/delta before any queue/source selection. Writer released.
