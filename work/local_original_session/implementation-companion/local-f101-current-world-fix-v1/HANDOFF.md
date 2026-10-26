# LOCAL F101 current/world collision — bounded diagnosis

WRITER_RELEASED. No product patch; test_ready:false. Only this directory is owned/changed. No runtime, listener, Test copy, common client/API, shared source, queue or failed-profile repair.

Exact Test103 source is selected trial `local-summon-packet-trial-v1/cohort.json`. `diagnosis.json` records checked source pins and bounded original result receipt. Test103's last success is WORLD_SERVER_CURRENT. The actual ordinal5 F101 completed ERROR/reply0 with ALLIED_CURRENT_DIRECT_WORLD_REQUIRED. Before close the real policy held pending 4E96/89bytes and sent12; its cursor was already burned (805306369/rev1). Failed copy, cursor, UNKNOWN controller and retained lease remain protected.

## Location and causal boundary

RootPlayers.prepare calls operation and _resource before _reserve. It then creates a registration and calls current(record). AlliedPlayerPort.spawn adds by_lease only after prepare returns, then invokes original Broker._send. The pending4E96 observation establishes policy.begin_write was reached. Thus initial current checks, durable cursor reservation, DTO creation and registration preflight have passed; the first failure lies after begin_write and before actual writer.write. Broker calls Allied.send_phase(WRITE_ATTEMPTED) there. That calls validate→for_frame→current→operation, whose current_owner read can return None.

The selected Host.current_owner calls hp_status.current and catches any ValueError, returning None. Selected status.current validates its projection through the selected ResourceOwner. Ordinary active projection calls _binding→provider.bind/current. Selected BrokerProvider.current refuses pending_opcode/pending_size/drain_started with BATCH_PENDING_TRANSPORT_REFUSED. This establishes a source contract collision consistent with Test103. The inner exception and each boolean in ALLIED_CURRENT_DIRECT_WORLD_REQUIRED were not logged, so BATCH_PENDING_TRANSPORT_REFUSED remains inferred, not an observed raw Test103 error.

## Why moving the existing check is insufficient

The selected Broker order is Allied RESERVED current → await _checkpoint → normal prewrite checks → policy.begin_write → Allied WRITE_ATTEMPTED current → writer.write → await drain → pending Allied validate loop (which can await sleep/_sample) → policy completion → Allied DRAINED current. Exact lines are in diagnosis.json.

The original RESERVED check is before an await. Reusing its owner/RESOURCE snapshot at WRITE_ATTEMPTED would therefore skip current validation across that await. The pending loop has further awaits. A held row lock/lease is not an existing capability to bypass BatchStore's provider.current or to assert unchanged canonical RESOURCE. delivery_current checks structural generation, not the required Store participant. No existing Allied pending ResourceOwner read capability was identified. Changing current to cached owner, substituting raw status, temporarily clearing pending, issuing a new lease or accepting a generation without current Store would weaken the existing boundary.

A safe implementation needs an exact post-checkpoint/pre-begin current capture and a typed original-send borrow admitting only the same Allied frame, writer/row/operation task, selected generation, direct/companion leases, Store and RESOURCE revision while pending. The pending queue loop must validate that same capability across awaits and retire it at the original drain/cleanup boundary. Shared core/resource changes belong to their writers. This worker did not speculate on that contract or alter shared source.

## First missing observation

Before any replacement packet trial, preserve the original exception at the existing Host.current_owner `except ValueError` contact, alongside the already-held policy's pending opcode/size/sent/drain_started fields. Keep its existing None return. Do not call status.current twice or add a new request. This will distinguish the inferred BATCH_PENDING_TRANSPORT_REFUSED from another source/current refusal without changing success handling. It must be selected and pinned with its caller/config by the feature main before root review; this report is not an executable test SKU.

Recheck this bounded diagnosis without imports/runtime:

```powershell
python -B work/local_original_session/implementation-companion/local-f101-current-world-fix-v1/verify_diagnosis.py
```

Do not rerun Test103's failed copy or old SKU. Any later root-dispatched Test uses a new independently prepared original55 whole7 copy and preserves first failure, raw exception, partial files/cursor and strict close. This worker supplies no RUN_COMMAND because no new selected runtime source/caller is ready. Existing original trial scenario/caller remain evidence only.
