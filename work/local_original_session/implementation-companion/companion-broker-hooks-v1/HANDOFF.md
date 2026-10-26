# COMPANION-MAGE Broker Host hooks v1

WRITER_RELEASED. Broker module `source_ready:true`; whole companion graph
`run_ready:false`, `test_ready:false`. Runtime and cold import **UNRUN**.

## Exact parent and delivered delta

The only product is this directory's full `broker.py`, descended from
`../allied-publication-source-v2/broker.py` SHA256
`463b787a6415129c5ee09f3148c6e1018abf2dc3d7fc603af15086b01268ea1c`.
The reviewed v5 `selected36a-broker.patch` is pinned at
`d2ad1e5390fcfde69b323b82af57f801ac817c5bfe560ae82fcec282e1c22fbe`.
`manifest.json` pins the resulting product, exact diff, resolution and verification.
No shared, prior/frozen, Factory, ack/realm, canonical, skill, Test client/API,
queue or saving path was edited. No runtime object, socket, port, game, fake
summon callback, direct Host trial or Test request was created.

All sixteen v5 patch hunks are accounted for in `resolution.json`. The seven
previous unresolved hunks 2/4/8/9/12/14/15 are translated onto their actual current
operation boundaries. There is no unresolved textual Broker conflict.

- Host starts selection and prepares its source profile before the existing
  callback. The **entire current** callback remains inside try/abort, including
  character scope selection, UID-root foreign check, profile identity, movement
  owner and cache validation. Host selected binding follows existing SHOP/current.
- Real accepted NPC death invokes the original Host award hook after the existing
  SHOP hook. Its actual accepted ordinal/result conditions remain required.
- Quit/Restart await Host retirement before their original transitions. Actual
  Restart selection drain retires the direct lease. Both idle poll and complete
  decoded batch boundaries tick Host under the original row operation, after
  request dispatch/send/drain, with no buffered partial frame.
- Cleanup awaits Host closing before PacketPeer world retirement/session close
  and original realm cleanup. Positive writer close then calls Host's original
  retirement reconciliation. Failures remain failures; no socket-close inference
  of actor lookup absence is added.
- Policy and `_send` admit only the exact `CompanionCostDelivery` with its real
  registered shared owner/broker, exact response opcode batch, binding, concrete
  policy/current/source validation and unchanged original drain callbacks.
  Companion policy imports occur only when a real owner has registered support;
  ordinary skill deliveries do not import companion modules as a new default gate.

Healing's existing status `0x4e38` policy overlaps the companion status wire. Its
full branch is retained for all non-companion operations, alongside original
Book/Buff/normal CostDelivery/SHOP/typed allied `0x4e96` and `0x4e40` paths.
There is no new raw send or bypass of source/current/receipt/ownership checks.

## Why old hunks 8/9 are not copied literally

The selected current Broker no longer contains the legacy cast post-drain helper
which those two old hunks extended. It already calls concrete delivery methods
`validate_batch`, `reserve`, `before_write_checkpoint`, `attempt`, `drain_returned`,
`validate_pending_drain`, and `drained` inside `_send`, along with original policy
and transport queue checks. The v5 CompanionCostDelivery implements those methods
and checks real receipt/source/current there. The source rebase extends exact
type/owner admission into this existing path, rather than resurrecting the stale
helper or its dead `cast_reply` variable. Book and Healing sample refresh and Buff
post-drain branches remain byte-for-byte in normalized source. This is static
integration evidence, not an executed delivery claim.

## Bounded verification

From project root:

```powershell
python -B work/local_original_session/implementation-companion/companion-broker-hooks-v1/prepare.py
```

The preparation command checks exact parent/patch hashes before writing only
this owned directory. `verification.json` records AST parse, unchanged function
signatures, preservation of all parent string/guard literals, all sixteen hunks
accounted for, and inverse recovery of the exact **newline-normalized** parent
from the bounded edits. Parent bytes are never rewritten; output uses LF.
The full `broker.py.diff` was inspected, including the current Healing and
PacketPeer cleanup branches. No product module was imported or executed.

## Remaining whole-graph requirements

This Broker must not replace a live/frozen selection by itself. Actual integration
still requires the separately owned coherent canonical Batch/resource/schema/
lifecycle, real Factory Host attach/bind, and matching canonical character-state/
realm/ack namespace. The Host's actor/support/direct-world configuration must be
real; this source does not construct or supply it. The current Factory/ack/skill
work stays with their owners. Source-bound summon/dismiss input and an actual
saved other class3 mage with its actual RESOURCE/account are not supplied here.

PacketPeer's exact `_accept.co_filename` neighboring Broker contract is preserved.
A final cohort must co-locate its exact selected Peer/Server and this Broker and
update the existing selection/pins once. This directory deliberately contains no
duplicate Peer/Server or wrapper. Do not select this path as an already executable
Broker/Peer pair.

Reuse `../mage-scope-caller-v2/run_feature.py` and its unchanged input-source with
the existing Test v5 API for the separately prepared normal mage acquisition.
That preparation caller is not a companion summon trial and must not run against
this incomplete graph. No executable companion packet RUN_COMMAND can honestly
be supplied until genuine summon/dismiss input and the required saved other mage
exist. Keep `test_ready:false`; the missing work does not block independent ready
trials. Allied pose remains `None`, native lookup absence and actual UI behavior
remain unverified. Main reviews the actual delta and handles any common source
selection/queue registration; worker sends no root/Test message or ACK.
