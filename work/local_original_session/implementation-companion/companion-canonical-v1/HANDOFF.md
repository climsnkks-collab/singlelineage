# COMPANION-MAGE canonical/RESOURCE private source pair v1

WRITER_RELEASED. All **8 canonical_batch and 1 hp_resource_document unresolved
v5 hunks are resolved** on the cohort's exact current parents. Both complete
patches are included, not just the formerly failing hunks. This is a coherent
private source pair for the later runtime graph; it is **not an executable
companion SKU**. `run_ready:false`, `test_ready:false`, runtime **UNRUN**.

## Exact source lineage and deliverables

- `canonical_batch.py`: current selected pending-custody parent
  `f6de9e07a6e5fc401164c3539e82b83d92341bdcaeb45820411cab40d70249b6`
  plus all 26 accepted `core2fd-canonical-batch.patch` hunks translated at the
  eight changed anchors. Output
  `efae3268b5a7980696f909d85568e131e71bfa82a3d4439fc8b64dada2a2c484`.
- `hp_resource_document.py`: selected healing-use-v1 parent
  `e0a0eeba887b0b17dbe1200201112cf55866681e6c8c442347728d7f38808fe9`
  plus all six accepted `core-hp-resource-document.patch` hunks, retaining
  `CONSUMABLE_HEAL`. Output
  `7d6babcc1fc848abfb185c5f89b6ac3a3865c4f79d657858bb45fa1c0f6f1dd2`.
- Adjacent `*.diff` files are complete exact-parent deltas. `resolution.json`
  explains each of the nine former conflicts. `manifest.json` has full paths,
  hashes, sizes and patch lineage. No unresolved patch hunk remains in this pair.

All writes are confined to `companion-canonical-v1/`. Shared files, frozen
parents, original cohort/loader, Factory, skill schema, Broker and queues were
not changed. Existing unrelated dirty workspace files were left as found.

## Preserved joins

Canonical's constructor still validates and binds the actual `packet_port`.
The original `_selected_current`, custody handling, packet selection methods,
credit namespace checks, equipment/armor debit checks and transfer owner methods
are byte unchanged. The prepare signature retains `credit_issuance`,
`credit_context`, `credit_offer_id` and `transfer`; the existing transfer digest
wrap, `armor_sha`, `Reservation.transfer` and close-time `_transfer_owner=None`
remain. A transfer also refuses `linked_resources` and `skill_bindings`, since
the existing transfer contract prohibits participant mutation.

Companion bindings are opt-in and authority registration remains cold/single
source. Joint changes use exact distinct Binding identity, same writer/lock/
scope/generation and live current checks, per-participant CAS, phase authority,
weak operation proofs and existing delivery/retirement paths. During linked
RESOURCE commit, reservation revalidation uses the original primary binding;
it does not reassign ownership to the resource participant.

RESOURCE keeps the original single writer, seed snapshot identity, revision,
source and phase guards, plus `CAST_COST`, `HP_EFFECT`, `PLAYER_LIFE` and
`CONSUMABLE_HEAL`. It adds v5 exact multi-stage selection and the companion
reasons; support-target values must remain unchanged. No default/fake stage or
authority is created.

## Bounded source verification

From project root:

```powershell
python -B work/local_original_session/implementation-companion/companion-canonical-v1/verify_source.py
```

`verification.json`: five static checks **PASS**. Both sources parse, exact
parents/patches/output hashes match, existing BATCH/CREDIT/RESOURCE error guards
are retained, 109 canonical and 3 RESOURCE unaffected methods are byte unchanged,
and the actual credit/equipment/armor sub-block is byte identical. The transfer
sub-block is identical after removing only the added linked-mutation refusal.
No product imports, synthetic runtime test, game, socket, port or saves were used.
Reproduction of the source translation is `python -B .../rebase.py`; this only
rewrites this private pair/diffs/manifest, then run the source check above.

## Runtime boundary and next exact joins

The pair can be reviewed/selected as completed source without running Factory,
skill or Broker. It **cannot enable or verify companions by itself**. It needs
the accepted v5 `companion_binding` in the same nominal canonical Binding space,
the coherent RESOURCE owner/status companion snapshot authority, SKILL joint
schema/lifecycle authority and Factory/Broker Host register/bind/lifecycle/send/
retire joins. Those files were intentionally not modified in this bounded task.
The cohort's nominal lifecycle/schema and realm/ack mismatches remain open.

The real summon/dismiss input and verified saved other class3 mage with its
RESOURCE/full-account input remain unprovided. There is consequently no honest
packet RUN_COMMAND for this pair and no runnable scenario. Reuse the existing
mage-scope-caller-v2 preparation and Test v5 API only once the complete exact
runtime graph and source-bound inputs are ready; do not substitute direct Host
or handler calls. Packet, native pose, original client lookup absence and UI
success are all unverified. Main owns review/integration; no root/Test message
or queue registration was sent by this worker.
