# Mage potion v1 — first target ITEM port missing

WRITER_RELEASED / SOURCE_ONLY. `test_ready:false`, runtime UNRUN.
No product mutation adapter, runnable placeholder, queue, Store, Test copy,
socket, game or REA analysis was created. Only this private directory was written.

## Exact existing caller and first blocker

v5 SharedSupport.execute first calls current(active). Its potion branch consumes
configuration.item_executor(active,intent,view,binding_for(active,'self')) and
returns existing SupportPrewriteRefusal(COMPANION_SHARED_ITEM_EFFECT_OWNER_OPEN)
when that executor is absent. SupportRule permits potion only for self; choose
requires actual owned instance, quantity/reserve, cooldown and HP/MP threshold.
CanonicalSupportReader reads the actual companion character inventory and
RESOURCE/SKILL through issued bindings; missing inventory is not a grant.

binding_for(self) is provider.bind_companion(owner.connection,active). The
companion binding proves character lease/actorUID/generation separately but
retains the selected owner's transport inventory generation. It is not the
selected character's ITEM generation or an accepted received ItemUse intent.

The selected current Potion Use source enters
HealingBatch.consume_received_locked(writer,row,intent). Before any debit it
requires issue_received_locked's real broker ItemUseSession._current _Intent,
accepted ordinal, raw0960 payload, held row operation scope, active selected
inventory generation/frame and selection_binding identity. It then explicitly
uses provider.bind_selected(writer). Its _context uses ItemUseSession._project
of the same selected generation and the same received item identifier. There
is no target-companion admission method in this selected HealingBatch.

**First blocker: an ITEM-owned consumed-item operation for a separately owned
companion inventory, admitted by the real companion lease/actor lifetime.**
The SharedSupport potion hook does not supply that operation. Passing its
SupportIntent to HealingBatch, changing binding.uid, installing a fake _Intent,
or using another character's _inventory_frame would violate existing authority.
No existing guard was removed or relaxed to produce an apparent connection.

## Existing transaction/delivery to reuse once that port exists

HealingBatch.prepared_locked obtains the current ITEM context and RESOURCE
snapshot, computes source-policy HealDecision, debits exactly the same owned
inventory, builds ResourceOwner.healing_operation and jointly prepares the
existing BatchStore reservation. commit_locked commits once, checks real
COMMITTED receipt and same inventory readback. HealingDelivery retains the
same binding, reservation, receipt and ITEM operation; the original Broker
sender writes inventory then full HP status. Actual drain/queued0 and the
original ItemUseSession.adopt_healing_drained finish the same operation. A
companion port must preserve these semantics with its own legitimate target
adoption; it cannot adopt another target through selected current memory.

No duplicate Store, resource effect handler, potion formula or packet is needed.
The default existing refusal remains the correct behavior until ITEM supplies
the target operation. Copying this refusal into a new executable adapter adds
no product behavior, so no such placeholder is provided.

## Single next source contact

Ask the ITEM source owner to extend the exact selected
HealingBatch.consume_received_locked / issue_received_locked admission boundary
with a separately issued companion-character consumed-item operation. This is
a requested new additive port, not a claimed existing method. It must bind the
actual companion lease, inventory owner/current frame and real owned potion
instance, RESOURCE target, receipt/CAS and target adoption to the same original
connection operation. Original normal0960 selected behavior remains unchanged.
The caller is the already existing SharedSupport.item_executor hook. Once that
owner port is supplied, this implementation can attach that hook and prepare
the full independent packet scenario.

Separate input state: the latest direct Potion Use API still has no normal
Potion BUY/fresh PASS acquisition or actual owned Potion14 UID. That genuine
acquisition is also required later; it does not resolve the target port above.
Mage CREATE/WORLD/current RESOURCE by itself supplies no potion ownership.

## Evidence and minimal inspection

source-evidence.json pins the received v5 sources, current Potion Use cohort
and its actual Healing/Delivery/ItemUse/runtime selections. Four selected file
hashes were checked against that cohort. blocker.json records 25 exact source
function spans. AST inspection confirms the real selected bind_selected call,
the current-intent requirements and absence of a companion admission method
in this selected class. This is bounded source inspection, not a global claim
that no alternative source exists. No runtime success or native UI is claimed.

No runnable/RUN_COMMAND is appropriate while a real input authority is missing.
Source-only registration must retain test_ready:false. The unrelated mage-scope,
queued allied actor/world and common/Test sources remain frozen.
