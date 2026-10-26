# COMPANION-MAGE linked native receipt reconciliation v2

WRITER_RELEASED / source_ready:true (private linked candidate only) / test_ready:false / UI_ready:false / runtime:UNRUN.

This is a provenance correction for `local-ui-native-linked-v1`, not a new DLL build. The v1 DLL remains 694272 bytes, SHA256 `2755fe262556b76fc0753d85b53a81a068370e43071bac637e5cb45eeaf891b0`. It has not been loaded or selected by Operating.NativeInput.

## Why a new manifest is required

During main review I ran v1 `verify.py` expecting a read-only check. It writes `compiler-link-input-pins.json` and `build-receipt.json`. Their actual bytes then changed after v1 manifest SHA256 `e11982710731d2960de02992490ff98b865477e2753cf5a5c00200e38d327729` had been queued. Exactly those two of v1's 49 pinned artifacts differ; the DLL and other 47 artifacts retain their original pinned bytes. The v1 manifest must not be used as a complete source pin or Test input. Root was directly told to hold its queued item.

The present receipt and its input ledger agree: `build-receipt.json` SHA256 `5bf12c8630a9d0a221d2f717493bd50ac03f3089a536fec396a02071638f2e98`, 3989 bytes, points to current `compiler-link-input-pins.json` SHA256 `e2bee4e259ee21f82ed3d3d141460d2cbe124ab90ff4d593099239444f31e62f`, 97693 bytes. The receipt still pins the unchanged DLL SHA above. This v2 manifest pins all 49 current v1 artifacts by absolute path and size/hash, plus this report and a strictly read-only verifier. It does not edit v1, rebuild, rename, load or copy the DLL.

## Scope and use

The v1 source/link review, selected SHOP export/import comparison and build evidence remain applicable to the unchanged DLL and 47 unchanged artifacts; the two changed metadata files are now pinned to their current, internally consistent bytes. The v1 `verify.py` is mutating and **must not be rerun** on a selected/queued artifact. Run only this v2 `verify_readonly.py` for reconciliation checks. It hashes every referenced file, confirms the old v1 manifest differs on exactly the two named paths, and checks receipt → input ledger → DLL references. It writes no files.

The official queue item `COMPANION-MAGE-local-ui-linked-native-shop-candidate-v1-20261024` is superseded by the v2 item. Root owns holding/removing that old queue item and final common selection. This v2 descriptor still does not satisfy selected Operating.NativeInput, selected Host model or panel, nonfocus execution, Test readiness or native game runtime. No original/common/Test/ACTIVE files, Git branch/commit, game, DLL load, ports, focus or input changed. Writer and execution resources released.
