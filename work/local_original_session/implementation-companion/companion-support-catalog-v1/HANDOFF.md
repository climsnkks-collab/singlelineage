# COMPANION-MAGE current support catalog source contract v1

WRITER_RELEASED. `source_ready:false`, `run_ready:false`, `test_ready:false`.
Product callback was not fabricated; runtime UNRUN.

First missing source: `CURRENT_SUPPORT_RANGE_TARGET_PRODUCER_ABSENT`.
Even if a separately owned opt-in effect/target policy arrives, the exact
companion-cohort-v2 selection has no per-spell support range predicate over the
current companion and owner. `CanonicalSupportReader` expressly delegates this
to a source/native range producer and provides no default. Same map, distance
between coordinates, or an admitted ally target alone does not establish range.

Actual source-backed inputs already exist: the reader holds the aggregate lock
and reads real learned/cooldown/buff rows, RESOURCE values and inventory; the
shared owner checks the actual current bindings, server actor UID/generation,
map and placement. The selected allied publication v2 returns a retained server
snapshot, but its client snapshot returns None, initial ActorSnapshot has
pose=None and movement refuses unavailable edge/pose. These distinctions are
preserved. There is no claim that missing client pose invalidates server-only
publication or XP authority; it prevents substituting a fictitious pose and
cannot supply the missing support range policy.

The installed SKILL schema retains exact Rule objects and the shared planner
checks `rule is policy.cost_rule`, actual learned state and costs/cooldowns.
The cold Rule constructor is available, but neither it nor the learnable/self
metadata supplies companion support range. No Rule is reconstructed or ID
selected here. No ItemCapability is supplied. Existing target-policy and
same-companion derived-stats blockers remain separately owned.

`source-contract.json` specifies the precise next producer contract and source
line evidence. `manifest.json` pins 12 exact selected Python sources plus the
cohort and prior source contract (14 files). Absence finding is bounded to these
selected sources. Minimal reproducible inspection from project root:

```powershell
python -B work/local_original_session/implementation-companion/companion-support-catalog-v1/verify_source.py
```

This parses source and verifies pins only. It does not import product code,
instantiate actor/owner/configuration, execute callbacks, or access game,
server, socket, ports, saves, direct handlers, packet APIs or queues. There is
no gameplay caller/RUN_COMMAND until real range and configuration inputs exist;
future caller must reuse Test's packet-test-client-v5/API and normal session
acquisition. Prior/shared files were only read. Current main and recent branches
were inspected; unrelated dirty files were preserved. No branch/worktree was
created because this task owns only the assigned new private artifact path.
No root/Test notification or enqueue was sent; return is to feature main.
