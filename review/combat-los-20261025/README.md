# COMBAT / LOS repository review snapshot

This branch publishes the real local source and review documents that were absent from main f599fd7 because they were ignored/untracked. It does not merge or change the shared product checkout and is not an executable product family.

Read REVIEW_BRIEF.md, IMPLEMENTATION_STATUS.md, LOS_AUDIT.md and PLAN.md first. Then use SOURCE_INDEX.json to find the actual sources/ files for each conclusion. Most sources are byte-identical copies with original relative paths and hashes. BROKER_CURRENT_EXCERPTS.py is a focused original-line excerpt, not a full/runnable module. Different source families (NPC physical, PC lethal, Buff cast) must not be combined as a proven runtime.

Runtime summaries contain only limited reported results. Raw results/saves/full history are not published. Missing dependencies are not proof of missing implementation. Classify source implementation, integration, preparation and actual runtime PASS separately.

User scope: complete ordinary single-player PvE combat, especially NO hits through walls/closed doors/corners against NPC OR character victims. Range/pathfinding is not LOS. Unresolved refusal or a Test-only CLEAR bypass is not real production LOS support. Unsupported PvP/caster admission must remain unsupported.

No original game/client binaries/assets, save files, credentials, full runtime logs, raw REA data or unrelated feature history are included.

The user has now supplied a manual Web GPT review of commit `4f5b0875f59cd67a484824d097c3a0a5652a83a3`. See REVIEW_RESPONSE.md for accepted corrections and the bounded follow-up request. The original SOURCE_INDEX.json entries and S00–S22 numbering remain unchanged. ADDENDUM_SOURCE_INDEX.json separately identifies supplemental sources; these are separate named families, not a runnable merged product. PLAN.md and IMPLEMENTATION_STATUS.md incorporate the corrections. Historical results are not a claim about the latest executing family.
