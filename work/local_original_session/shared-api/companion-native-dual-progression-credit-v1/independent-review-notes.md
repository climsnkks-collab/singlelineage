# Independent native boundary review notes

This review covers one detailed pass over the initial frozen Core0727bb1a / Root0df9c702 / native6b562cc6 Source, then only the two reported native deltas and affected counterexamples. No historical reader/math/PASS/full suite or game/native/packet execution was rerun by the reviewer. Product files and all foreign sources remain read-only to this reviewer.

## Concrete findings and closure

1. Initial per-recipient persisted carry required equal residues. The first patch removes this restore restriction and composes each beneficiary's grant from the unchanged pinned split function using that beneficiary's own saved residue. The combined half-unit conservation assertion accounts for both distinct inputs. Thus owner1/new-companion0 is retained without overwriting either residue or editing foreign math.
2. Initial native-only DUAL-EXP markers did not exclude the original solo route. The patch checks the original PROGRESSION:<operation_id> transaction and both original marker namespaces before projection and again at final current validation. Both PROGRESSION changes add that exact original solo marker alias in the common commit. The reviewer independently evaluated the actual native marker expression, JSON-roundtripped the saved aliases, and executed the exact two original ProgressionOwner award guards. Both recipient UIDs refused PROGRESSION_KILL_ALREADY_COMMITTED; unmarked controls passed. This proves the persisted alias matches those original guards. It does not prove a future selected solo successor preserves the guard or a foreign reward producer identifies the same kill across different routes.
3. The first residue patch still could not initialize a genuine newly CREATEd replacement beside an owner with an existing carry row. The final delta seeds only the absent recipient with its genuine Root-issued CREATE receipt and untouched new PROGRESSION provenance. The existing recipient supplies None only when its actual saved carry row exists and passes UID/revision/digest/schema validation. That row enters the same native plan/receipt as a byte-equivalent readonly anchor, including its unchanged revision. At COMMIT only the exact before==after anchor is authorized. Both lease/current, raw preimage and participant CAS checks remain. No existing carry or progression is reset and an absent older history never defaults to zero.

## Source boundary conclusions

The source owns a concrete EXP-HALF participant schema, native-issued current restore/capability/result identities, same-pair source/current/CAS routing, one PREPARED reservation and the existing single final durable COMMITTED replacement. The common credit plan contains both PROGRESSION rows, both half rows, applicable genuine RESOURCE postimages, both asset revisions, once aliases and one receipt. Aborts preserve original participant values; ambiguous final replacement preserves the original failed/partial outcome. Saved historical results cannot acquire resend or fresh projection authority. Native retirement clears its own stages; original caller and foreign growth owners must close their own stages/resources.

CREATE initialization is separate from restoration: absent rows require genuine original CREATE provenance and virgin progression values. SELECT/import/legacy parity is not migrated. Existing valid rows are restored as saved, including differing residues. Missing rows remain UNKNOWN.

The published cap policy refuses the whole pair before PREPARED if either recipient cannot receive exactly its integer grant under the original document domain. It does not clip, credit only one side, reset a half or assert successful award. The original committed kill and any consumed growth prefix remain caller-owned partial evidence.

Nominal source tuples select concrete module/class/method/code/default anchors, while actual producer methods must issue and revalidate the same registered receipt/result/current stages. Numeric DTOs and source metadata alone cannot mint the native capability. The implementation is more than an always-refusal stub: its typed transaction/recovery/current/result reducers exist, but their genuine foreign producer inputs are not supplied.

## Mandatory unready seams

- A coherent selected AlliedKillReader/session/actor/ledger/NPC cohort with actual registered result/KillReceipt and same-operation current semantics. Existing reader-v2 is not silently accepted as a v3/current successor.
- A source-owned AlliedRewardOwner for lawful pool/provenance, eligibility, shared same-kill operation identity and exclusive original solo route. The native original-marker guards only close the identical accepted operation ID.
- A same-new-Core AlliedProgressionOwner using original document/math/thresholds/initial values, both recipient stages and stable two-beneficiary growth RNG order. The old PCe4b3 classspace is not interchangeable with this account Core.
- A genuine dual-recipient HP RESOURCE growth/current/status/projection/delivery owner. The original single-PC _Award/progression_operation cannot authorize a second UID. Native proof/result DTOs do not add that authority.
- Original companion caller/loader/cohort, genuine current inputs, normal packet sequence, real gameplay RUN_COMMAND, first-failure/partial preservation and finally cleanup. Only Test owns native profiles/game/ports/packet execution.

These remain source-only contracts, not implemented foreign producers, native runtime PASS or gameplay readiness. Other ready work must proceed independently.

## Verification evidence and limits

The product owner's focused-check-result.json reports20 pure checks. The reviewer inspected the actual check source and reused the result without rerunning it. It tests source preservation/compile/schema/restore and actual selected transaction methods in an explicitly in-memory model. Its current/authority ports and CREATE records are declared test doubles; its positive reducer checks cannot certify genuine source registration, Root current, actual kill eligibility, live dual growth, delivery or disk runtime. The reviewer added only the bounded actual-alias/original-guard JSON restore counterexample described above. Native profiles, games, fixture kills, ports and packet sends were zero.
