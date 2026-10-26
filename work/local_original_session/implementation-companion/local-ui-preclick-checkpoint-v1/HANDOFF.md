# COMPANION-MAGE genuine first-4F13 checkpoint candidate

WRITER_RELEASED. source_ready=false / test_ready=false / ui_ready=false /
runtime_ready=false / RUN_COMMAND=null / resources0. Only this NEW private
directory is owned. No original/common/Host/Test/queue/ACTIVE/Store/port changes.

The selected-model-v2 Broker still performs its original `_checkpoint` for every
decoded frame. Its actual `_sample` calls retained NativeOwner.guard, creates
OwnerSample with the original timestamp, and `_policy_sample(received_frame)`
validates that same sample and the real click feature/header before dispatch.
The only product delta is eight lines immediately after that original validation:
for 4F13, decoder-empty, an installed LOP1 channel with no OPEN intent receives
`row_checkpoint(..., checkpoint_sample=sample)` before game.received routes to
Feature.dispatch_locked -> Host._open_from_actor_click_locked -> OpenPort.issue.
It stays inside the actual existing `_row_operation`, no await or lock reentry.

Corrected LOP1-v2 row_checkpoint performs actual `_capture_locked` and, while
`_open_intent is None`, stores that binding and returns before delivery logic.
Therefore this new hook adds no owner/TCP query, no pipe write or synthetic
capture. It forwards the actual freshly policy-consumed frame sample, not a
cached sample or new timestamp. Existing idle and post-frame checkpoints remain
byte-identical. Non-4F13, absent channel, LUI2 without `_open_intent`, pending/
UNKNOWN intent and partial-decoder paths are unchanged. Authentication not ready
still fails at submit; stale samples still fail original received_frame validation.
Original header/current ownership, payload UID parsing and handler order remain.

The exact selected-model manifest -> LOP1-v1 -> corrected LOP1-v2 lineage is
checked and pinned. `parent-pins.json` includes exact Broker, LOP1-v2 source and
manifest, Host click/OpenPort/Feature source and original policy. Only Broker is
copied, with an inverse-exact diff. Parent sources and verification are immutable;
no parent build/verify/regeneration is invoked.

Readonly verification compiles in memory, hashes the exact parents/artifacts and
executes the actual changed pre-dispatch source segment in eight isolated
recording-sink cases. It verifies same-sample identity/order, one existing owner
checkpoint, excluded paths and original policy/channel refusal barriers. The sink
does not capture any binding, invoke a handler, issue OPEN, invent a receipt or
run a game. This is scheduling evidence only, not real owner/UI/runtime proof.

Known boundaries: Host `_refresh_panel` can replace ui_epoch if shown_lease differs
from the current lease; if that happens after this capture, exact intent binding
must reject as before. No extra refresh/forced state/capture is introduced to
hide it. Runtime success needs the actual prior lease/epoch alignment and selected
Factory/Plan/launcher/native lifecycle/LOP1 pair/Host integration. Native panel
OPEN, render, commands, native close, successor and settings/save remain unproven.
No retry of UNKNOWN and no readiness or selected-cohort claim is made here.

After handoff only `python -B verify_readonly.py` may be run; it reads, hashes,
compiles in memory and emits bounded JSON without writing files or importing the
product. Parent/main owns actual diff review, selection and queue publication.
