# Idle disconnect test

Scope: fresh test copies only; no original LC/resource, user save, prior result,
or immutable bridge candidate changes. One worker owns all game/port tests.

Preparation observations:

- Initial LC.guard PID 26660 was present while 12000/14030/26000/28030 had no
  observed listeners. It was neither stopped nor attached. Later read-only
  process inventory found no LC.guard; native launch remains sequential after
  the loopback finishes and native investigation is ready.
- `main` is the existing branch; existing dirty/untracked work is preserved.
- Initial native wrapper help without its required background/attack flags
  returned `ValueError: FOCUS_STEALING_LAUNCH_DISABLED` before launch. Repeating
  help with those flags printed argparse usage. Neither attempt launched LC.

Loopback:

- Command: `SL_TEST_PORT_BASE=26000 python -X utf8 -B work/local_original_session/game-core-prep/idle_disconnect_loopback.py --idle-seconds 900`
- Run: `work/local_original_session/runs/idle-disconnect-loopback-xam0kb4n/`.
- Started UTC: 2026-10-27T15:16:41Z. Fresh run is also the test profile.
- Broker Source: `d21c30274189b7c7acea0399e0e0030729ed301247a338aa2d0170e68e3374db`.
- Existing HuntBot login/FIRST bootstrap/continuous Peer reader/Alive/Quit and
  hunt_bot_loopback fixture are reused. No move/attack/potion/inventory action
  is requested during idle. Alive uses the observed native cadence candidate
  of 60 seconds. This is user gameplay idle, not transport silence.
- Source combination and invocation are in the run directory. Fixture-owned
  owner/equipment stand-ins remain the existing socket-test boundaries; this
  test cannot establish native input/rendering equivalence.
- Completed: observed idle 900.016 seconds, overall 900.172 seconds. Bot
  FINISHED; no failure/cleanup failure. Alive requests/replies 16/16 including
  the final response after the deadline, no gameplay actions. Entry/final
  map0 position32595,32906 HP20/20 stayed unchanged. Quit request/ACK1/1,
  subsequent normal server EOF, broker failure null and cleanup_complete true.
- The launcher script exited 1 because its disk-source comparison found 12
  concurrent file edits, not because the idle or Quit failed. Original
  `result.json` is preserved unchanged. This supports the already loaded
  runtime's 900-second socket behavior; it does not certify an unchanged
  on-disk Source combination for all 900 seconds. No hot reload is performed
  by this test; exact import timing for each changed module was not captured.
- Concurrent changes: game_data.py, hunt_bot_play_matrix.py,
  item_equipment_effect.py, world_feature_companion.py, world_feature_magic.py,
  world_feature_stats.py, world_handlers.py, world_item_effects.py,
  world_item_effects_tests.py, world_magic_tests.py, world_visibility.py,
  world_weight.py. Last-write times observed span15:21:22–15:31:12 UTC, after
  run start. Broker.py is absent from the change list. Existing external edits
  were not reverted or repinned. Before native launch the coordinator is
  notified because that launch needs a newly selected current Source.

Native preparation:

- `run_idle_disconnect_native.ps1` is adapted from the explicitly requested
  scratchpad `run_auto_knight_m1.ps1`; immutable baseline and candidate pins
  remain checked. It uses the existing source-Quit candidate SHA256
  `d5865458c910415c4007f169cea64c5f99e31e78ad6c19a7d0dd7f635d53da8d`, unlike
  the latest manual baseline bridge `1d1f60a0...` or old attack `2c0bcd6e...`.
  Only the verified slot is temporarily installed, with baseline restore in
  the original finally path after owned cleanup. Source candidate is unchanged.
- `idle_disconnect_native.py` uses the existing Scenario Login/Slot/SelectOK,
  stable current Land/world/move observations, Alive receive/send evidence,
  900 actual seconds, and existing source Quit. It removes haste injection,
  inventory/attack/movement actions. The original scenario file is unchanged;
  only the loaded test copy has bounded idle/tool time limits extended.
- Final native outcome requires real hold and normal exit; no attack/inventory
  success fields are fabricated. TX4F57 evidence alone is not native consume
  proof. Current scene/position and native connection duration are distinct
  observations; exact packet task consumption remains UNKNOWN unless observed.
- One native attempt launched as `idle-disconnect-native-20261028-003500`
  without user focus/global input. Initial LC.guard and all four relevant
  listeners were absent; baseline/candidate pins matched. Startup Source
  manifest is `runs/idle-disconnect-native-20261028-003500.source-start.json`.
- Login/Slot/SelectOK returned, Land/none/root_ready and uid1 grid32576,32946
  were observed with a stable world sample. Initial native kit delivery was
  AddInventory CLIENT_CONFIRMED rows35; no scenario gameplay action followed.
  The existing movement observer consistently returned
  `UNKNOWN: RETAINED_SAMPLE_BYTE_BUDGET`, so strict `idle_hold_complete` never
  became true. No observer budget/ready/source guard was changed.
- The wrapper returned shell exit0 with `RUN_EXIT=-1`. Native final result,
  source-end metadata and normal Quit/owned Job close evidence are absent.
  Last published status is still RUNNING with elapsed323.812, Land/none,
  broker failure null, last received4E2A and movement requests/commits0. That
  elapsed value is the stale sample's time, **not observed process exit time**.
  Native900-second hold, native timeout cause and normal cleanup are UNKNOWN.
- Read-only process checks found no exact `idle_disconnect_native.py` Python
  process and no previously recorded owned Python48708/LC25140/LC5356. Their
  recorded birth/PID evidence and boundary directory remain in the raw run.
  Current Python47456 and LC15028 were separately identified as a later foreign
  manual-test-knight run created15:40:05/15:40:24 UTC. They were not stopped,
  attached, or otherwise changed. No native retry was performed.
- Slot hash was observed back at baseline1d1f60a0... after wrapper return.
  Reaching the wrapper's final output follows its existing finally restoration
  path, but this is not evidence of native normal exit or owned Job cleanup.
  Failure/interruption cause is UNKNOWN; later foreign process presence alone
  does not establish what ended the first run.
- Raw partial: `runs/idle-disconnect-native-20261028-003500/`; early observation
  copies `idle-start-status.json`/`idle-start-scenario.json`; bounded close-out
  metadata `interrupted-observation.json`. Original status, scenario, command
  result, boundary records, test profile and empty execution.log are preserved.
  The latter metadata lists six disk changes observed after interruption;
  it does not substitute for the missing in-process source-end result.
