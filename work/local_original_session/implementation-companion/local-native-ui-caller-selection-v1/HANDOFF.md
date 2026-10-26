# COMPANION-MAGE native UI caller selection v1

WRITER_RELEASED / audit_complete:true / source_ready:false / test_ready:false / runtime:UNRUN / RUN_COMMAND:null.

The exact selected native graph cannot yet run the sidecar. No speculative caller, launcher guard bypass, module monkeypatch, game process, DLL load, port, pipe connection, focus/input, Store mutation, or runtime copy was created. Only this new private directory was written. Existing main dirty checkout and unrelated changes were preserved; no common/Test/queue/ACTIVE, branch/worktree or commit changes.

## Actual selected graph

`companion-account-click-host-v1/cohort.json` SHA e4be6a47f94956dcce35aad320c972eb760bfa9dcef9fd0364fd501dc25dc2ea selects 185 files. All 185 actual path/size/SHA pins match and are preserved in selected-pins.json. The source loader supplies that cold import graph only; cohort explicitly says COLD_IMPORT_ONLY_ACCOUNT_CLICK_COMPONENT/run_ready:false. It contains no game/native selection or completed runtime installation.

The shortest relevant selection chain is:

1. Original cohort source_loader -> selected operating_input SHA241f5a30 -> operating Prepared.feature_factory (lines344-354), constructing selected launcher's original ProductFeatureFactory for canonical-shop-input-v1.
2. Selected launcher SHA1cc72cdc defines SHOP_INPUT_PROFILE and cold install_shop_input_profile (583-607). Native input is not chosen by the launcher's older composite product descriptors: the selected operating NativeInput.check (221-250) requires native394 absolute DLL path, SHA **1e18afd8643d5a60e941782726c681b1c0a1e2944f700933dd28d4256de742d6**, build-receipt SHA767b535f and manifest SHAb419f1d2. Those three actual files match. install_shop_input_profile is called only after selected assembly (550).
3. Prepared.launch (356-379) validates exact GameInput/ProfileInput/argv and calls original launcher.main(**kwargs). Selected main (5475 onwards) constructs its original NativeOwner, SessionMonitor, sockets and Broker factory. Selected Broker SHA3c7b80ac is cohort-pinned; original ProductFeatureFactory.inventory_owner_guard (3675 onwards) returns that exact owner's original synchronous guard. Bootstrap c876200c and feature_config bb4a4f70 remain selected.
4. Accepted sidecar composition manifest **eb498c49d7236b39aeb9c938c2d77bc9f6211db3a530248b15574e01b3461397** supplies only run_session. Its existing run_session is not selected by Prepared.launch or launcher.main. The required future entry must preserve main's real owner/factory/monitor/source-quit/Store setup, then call that exact composition with the same original owner; installing an alternate type, replacing parent.run_session, or copying an incomplete main is not supplied by this audit.

## First exact dependency boundary

**Selected operating NativeInput refuses the companion DLL before native preparation.** The linked hotkey DLL is SHA **236d0208a03fd09369fb704165960170f3c4c6316cab88e5983f288823e9d3ae**/615936B, at its own private path. It cannot satisfy NativeInput's exact native394 path/hash or the required receipt/manifest association. Merely replacing launcher PRODUCTS or its bridge_artifact does not update operating NativeInput and is not a coherent selected graph. The older launcher's inherited composite SHA18164426 is also not this selected SHOP native pin; do not use that ancestor descriptor to diagnose this path.

The reader manifest **9b148c40e36a06e1887c63343f9e9487465c65271ca4d438fc9a43c5fb049768** is a separate bootstrap-handshake-only source. Its build.cmd uses /c and supplies diagnostic.obj, no DLL in that directory. The hotkey DLL's actual compiler dependency report contains no bootstrap-reader-v1 files. Thus the existing linked hotkey DLL cannot be claimed to contain the reader handshake. A pinned new linked native artifact, exact source/build receipt association and reviewed operating selection descendant are required before a runnable caller can be concrete.

Separate remaining boundaries are preserved:

- Selected operating argv requires --background/--source-quit-test; selected launcher retains background guards and private non-input desktop semantics. The hotkey host's actual host_lifetime.hpp:70-72 requires source-backed foreground ObserveExpected for binding, and its inherited command dispatch requires physical hotkey input. No nonfocus execution ownership meeting that native input contract was supplied. Bootstrap handshake code alone does not supply a selected command/model transport or change those requirements. No foreground ownership was invented.
- Original cohort companion Feature requires genuine configured Host/interface/AlliedPlayerPort before Broker start (companion_actor_click.py:46-54), and its retained Host lifetime cannot transparently become an account Scope successor. Existing blockers.json preserves this unresolved source contract. No fake interface/token or slot clear is added.
- GameInput requires a full isolated runtime copy plus real executable provenance and exact bridge preflight. No selected runtime copy/profile, retained execution slot or caller argv was supplied here. Existing Test/other-owner copies are not appropriated.

## Minimum next concrete scope

Supply one exact compiled native descendant that contains the reader and required nonfocus selected UI entry/command/close contracts, with source dependencies/exports/receipt; pair it with an operating NativeInput selection descendant and a source-owned original-owner sidecar entry. Supply actual profile/GameInput and explicit execution ownership. Keep source-only native bootstrap, native UI outcome, native close/drain and companion feature completion distinct. Until those inputs exist, no game RUN_COMMAND is truthful. Packet tests continue independently.

## Bounded verification

`python -B work/local_original_session/implementation-companion/local-native-ui-caller-selection-v1/audit_selection.py`

PASS: 185 selected files match their cohort bytes/hashes; accepted parent/reader manifests match requested exact hashes; selected launcher/operating/composition syntax parsed without importing product modules; exact original-owner requirement and original Prepared.launch target inspected; selected native394 DLL/receipt/manifest pins match; hotkey DLL pin matches and differs from selected native pin; actual hotkey compiler dependencies exclude reader; reader build is compile-only and no reader DLL exists. Existing build/isolated/native checks are reused without rerunning. This is static audit evidence, never native constructor/OS/UI success. verification.json contains actual result; input-pins.json has exact absolute input paths, bytes and full hashes. No execution resources acquired; writer released.
