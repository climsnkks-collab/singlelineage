# COMPANION-MAGE account actor Scope callback capture F1 fix v2

WRITER_RELEASED. `source_ready:true`, `run_ready:true`, `test_ready:true` describes the complete private source/caller/input/command/cleanup preparation. Runtime UNRUN; genuine CONSTRUCTING/fresh Host/ATTACHING/MAGE WORLD success is not claimed.

## Actual F1 and exact diagnosis

Parent manifest `f7d80c8eaed1d2c5ae1d21aa40bc6d069c6b047c275dc9988740a15aff7754ef`; caller `2ddbad33acd5bc8df8a289bb09cb13a68637005a4f09f2fcd0e5f7dc89589153`.

Test result `integration-1/packet-companion-account-actor-scope-actual-v1/account-scope-world-result.json`, SHA256 `7c53065af580310ca668c6633e2a609243cf2a31092defe57b2fb9664062d754`, records ROOT WORLD/clean PASS then MAGE4E28 first failure `COMPANION_FRESH_CALLBACK_DEPENDENCY_NOT_CAPTURED`, cleanfalse. That result and its Test-preserved partial copy remain untouched; no failure is relabeled or replayed unchanged.

Genuine old cold inputs reproduced the capture discrepancy without a token/Host/runtime fixture. Exactly two callback triples were absent from the22-member `_companion_sources` tuple, despite being present in overall Plan.sources:

| Module | Exact source | SHA256 |
|---|---|---|
| `tools.local_original_session.hp_resource_owner` | `spellbook/account-multi-character-canonical-v1/hp_resource_owner.py` | `91dbb29930cc3aeea7e900c1b2a221e69956b1c0825470bb6aa1aea23e110900` |
| `tools.local_original_session.broker` | `implementation-companion/companion-cohort-v2/product/broker.py` | `934fb07af30efd5853fdd147f5dfda64fb5f16b730914e3757e89ec50963c46a` |

Canonical core is already captured in the old tuple and is not a missing dependency. The diagnosis uses actual module/path/hash matches, not assumed module lists.

## Narrow fix and original guards

Only `cold_inputs.py` source collection changes:

```python
# before
seen={pin.module for pin in sources}|{pin.module for pin in plan.sources}
# after
seen={pin.module for pin in sources}
```

Each actual callback source_triples member is now added once to companion sources even when already included in overall Plan.sources. Genuine new cold Plan capture is24 unique nominal modules, within original8..32 limit; all17 dependency triples have exactly one matching actual SourceModule in `_companion_sources` and pass its original check. Global Plan source checks also pass with those modules represented in companion capture. No Host guard is weakened, and no token or current authority is synthesized.

185 selected product rows/cohort, loader and dependencies are byte-identical to parent. ITEM Scope13df, Factoryc79, Host15d, Alliedd149, actor-configf06, Broker934/Core86 and Peer/Server remain exact. No client/API/Scope/Factory/Host/Broker/common product edit is made. `cold_inputs.parent.diff` is the one-line product-input delta; `caller.parent.diff` records only private trial scope/protection/failure observations.

## Lawful input and changed path only

Test must make a NEW independent whole seven-file copy of original actual55 PASS source `validation-profiles/packet-account-multi-canonical-input-v1`. All seven source hashes still match the actual55 accepted post-PASS record; root inventory remains81697B/SHA57842ab0. No SKILL is supplied/seeded. This is lawful immutable passed source, not the failed actor-scope-v1 copy or an overlay/reset of it. Input-source.json pins the exact seven files and explicitly refuses failed copy `validation-profiles/packet-companion-account-actor-scope-input-v1`.

Reuse actual v1 ROOT PASS. The new normal sequence is **MAGE → ROOT_FRESH**, each with original KEY/VERSION/login/address/actual INFO/name/LOCAL selection/WORLD/current/RESOURCE/0964. MAGE's first changed4E28 consumes the corrected fresh capture under the real Scope token. Only strict clean MAGE permits same-copy ROOT_FRESH; no unchanged ROOT WORLD prelude or failed-copy retry is performed.

Original actor-only Host identities, account members/RESOURCE/cursor/origins/Store observations and caller preservation_after metadata remain. Caller retains first exception/message, actual server row error/completion, and both original before+after snapshots; failure_code, failed/error rows, completed ERROR or completed.error reject clean and next owner. Normal client/server/Host/Plan close is retained. Cleanup faults do not replace first error. Native Quit/summon/support/UI remain outside this test.

Test continues to own FIRST/full raw partial-file preservation and failed copy/result evidence. No redundant raw inventory mirror or per-owner original-source reread is added. Loader/SourceModule own selected-source verification; the caller does not repeatedly walk manifest artifacts. Output must be an explicitly new absolute path outside profiles and old actual result directory and uses exclusive creation. Copy regular-file/reparse/link/independence checks prevent source aliasing. Worker does not copy or execute anything.

## Exact command (Test only)

```powershell
powershell -NoProfile -File "C:\Users\Chansol\Documents\ChatGPT\싱글리니지\work\local_original_session\implementation-companion\companion-account-actor-scope-capture-v2\RUN_COMMAND.ps1" -AccountCopy "<Test NEW whole actual55 seven-file copy absolute directory>" -AccountResult "<Test NEW absolute result outside profiles/old actual directory>"
```

The command retains existing client-v5 and policy/feature inputs and invokes exact run_account_scope.py. New trial-scenario.json describes judgments; unchanged scenario.json supplies the original caller's three required saved selection fields. No server/port/Test writes occurred in implementation.

## Minimal verification

`python -B .../companion-account-actor-scope-capture-v2/verify_cold.py` passes15 focused checks: exact parent/actual F1; one-line source delta; same185/183 graph; actual old/new cold Plan capture and original global checks; all17 exact-one dependencies/24 unique source names; original unchanged Host guard; changed MAGE/clean ROOT_FRESH caller/both-snapshot failure shapes; original cold cleanup and actual55 seven-file/listing preservation. Host/Broker/token/actor callback/runtime construction0. Runtime F1 resolution remains UNRUN until Test executes this exact fixed SKU.

Final cold_inputs bytes preserve the parent's LF line endings: final4258B is the exact one-line byte replacement. Verification reports stable selected module keys instead of the aggregate loader's variable UUID import name; actual module/path/hash identity remains checked. No clock/account identifier/transient core UUID is serialized, so fresh namespace allocation does not change report bytes.
