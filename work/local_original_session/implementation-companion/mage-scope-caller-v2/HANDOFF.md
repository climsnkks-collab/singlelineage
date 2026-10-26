# COMPANION-MAGE CREATE/WORLD caller v2

Corrects F1 in `integration-1/ready-mage-create-review-v1/review.json`. The v1 runner read the canonical RESOURCE binding after `ready_current()` had released the row operation. v2 rechecks original current and performs binding, participant, status, and equality read inside `context.broker._row_operation(context.writer,context.row)`; later inventory/idle code remains outside.

Parent caller: `../mage-scope-v1/run_feature.py`, sha256 `fe1c905f856df347f31c5333bc96d9568832a463512fe09ab1973f728cca3941`. All product source, cohort, scenario, input source, and Test v5 client pins are inherited unchanged. This is a caller-only revision; the earlier v1 package remains frozen.

`test_ready: true` for the same class3 male LOCAL create -> received roster -> WORLD/current/RESOURCE/initial 0964 -> close -> fresh login/selection/WORLD/current/RESOURCE/0964 flow. Test supplies a fresh complete copy of `input-source.json` and its owned result path to `RUN_COMMAND.ps1 -MageCopy ... -MageResult ...`. Runtime is UNRUN; Test owns server, packet client, copy, ports, and close. Summon, actor click, and native UI are separate unready paths.
