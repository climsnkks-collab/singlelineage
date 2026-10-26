# COMPANION-MAGE same-account joint RESOURCE review v1

WRITER_RELEASED. `test_ready:false`, `run_ready:false`, runtime **UNRUN**.
No product descendant is supplied. The selected original owner cannot legitimately
make the two existing RESOURCE rows participate in one BatchStore. Only this new
directory was written. Existing source, seven passed Test files, queue, callers,
runtime, saves and process ownership remain untouched.

## Result and first blockers

The issue is more restrictive than a missing RESOURCE row. The passed root
inventory is outer Batch v3 with **inner canonical v4 for UID1 only**. Its
participants are exactly RESOURCE:1, revision42; asset revision46. The child is
outer Batch v3 with inner canonical v4 for UID2 only and exactly RESOURCE:2,
revision0; asset revision2. Both pending fields are null. These are genuine
separate durable documents and their existing transaction histories remain intact.
Full hashes and bounded facts are in `verification.json`.

On a hypothetically genuine active root companion, SharedSupport.plan first
requests the caster participant through owner._participant / BatchStore.participant.
Root has no RESOURCE:2, so that path rejects `BATCH_PARTICIPANT_NOT_INSTALLED`.
This is a source-derived later support blocker, not an executed summon failure;
missing actor/input/configuration can stop earlier.

1. **A row-only insertion is structurally invalid.** canonical_batch.py
   BatchStore._validate_canonical (line1020) maps inner v4 to its single
   snapshot.character_uid. _validate (line1045) permits character participants
   only for those canonical inventory UIDs. RESOURCE:2 under root would reject
   `BATCH_PARTICIPANT_CHARACTER_SCOPE`; the account roster containing UID2 does
   not add UID2 to this custody document. Moving only RESOURCE:1 into the child
   fails symmetrically. It also leaves the old owner capable of independent writes.
2. **No existing installation API covers this state.** BatchStore.migrate
   (line1197) accepts only outer legacy v1/v2 and keys seeds by binding.uid.
   Both saved files are already v3. ResourceDocument.seed (line85) explicitly
   forbids companion seeding and demands the real direct selected/drained
   pre-world status. Repeating CREATE/WORLD, selecting the child, refreshing an
   actor snapshot, or calling _replace directly supplies no adoption authority.
3. **No cross-file joint commit exists.** BatchStore owns the exact source
   inventory path/profile and one _OWNERS entry; _current compares its raw bytes
   and parsed preimage. _replace (line1119) validates and CAS-checks one file,
   performs one atomic replace and exact readback. prepare (line1514) requires
   existing linked resources in that same document and _joint_current
   (line1489) requires one writer/operation lock/scope/generation. Two sequential
   file commits, even while holding the shared Python lock, do not become one
   crash-atomic transaction. A split failure cannot be reported as success.
4. **Identity/lifetime guards independently exclude using the child Store as a
   substitute.** companion_binding.py._source_current (line76) requires both
   real account leases' _profile to equal the provider's source-store profile.
   Root leases cannot honestly bind the child Store. Existing character_scope
   selecting (line594) retires/rebuilds the Plan for a real child transition;
   the earlier scope-lifetime HANDOFF identifies its separate Host retirement
   and reinstallation barriers. Rewriting profile strings or retaining a stale
   provider would be fake binding, not an ownership transition.

The accepted v5 joint cost/support machinery is already present and is reused:
the selected SharedSupport stages caster RESOURCE + SKILL and optional linked
owner RESOURCE, with exact before revisions/digests and one Store commit. The
existing staged_many implementation and linked-commit API are not missing. Their
same-file prerequisites are not established by these saved inputs.

## Concrete next owner/input contract

An inventory/canonical-owner product change is required before this feature can
consume joint RESOURCE. The accountable owner is the existing canonical inventory
and created-character-scope owner, coordinated by the integration main; this
worker does not claim those shared files. The next bounded assignment must
deliver one coherent, source-backed **account custody and participant ownership
transition**, with all of these explicit inputs/outputs:

- Inputs: exact root account roster plus root/child inventory byte preimages,
  their existing canonical v4 custody, participant revisions/digests, receipt and
  marker history, real closed/quiescent writer ownership and actual account UID
  namespace. Test alone creates a new whole account copy when runnable. No grant,
  row overlay or edits to this passed copy are legitimate preparation.
- Destination: one authoritative account Batch document must represent both real
  characters' existing custody and RESOURCE (and the required account SKILL),
  preserving frame fields, equipment guards, UID cursor provenance, existing
  revision/digest/history meaning and recovery visibility. Current single-UID
  v4 cannot represent that output. The owner must supply the precise compatible
  schema/decoder and producer contract, not downgrade v4 to a lossy legacy frame
  or hide a second authoritative RESOURCE ledger behind a projection.
- Ownership cutover: supply an actual durable linearization/recovery rule that
  retires old writers/read routes before the account Store becomes authoritative.
  Any old child artifact retained as history must be provably non-writable and
  non-authoritative; it must never be accepted as a second live RESOURCE source.
  A Python lock or two os.replace calls is insufficient. Recovery must select
  exactly the old or new owner after an interrupted cutover and preserve partial
  outcomes without rollback/retry pretending success. No new independent ledger
  or migration wrapper is proposed by this review.
- Runtime: direct selection and companion lease must resolve the same genuine
  account source-store identity; child selection must use that actual owner with
  a separately explicit character scope. Preserve real scope/generation/current,
  CAS and Host retirement/reinstallation contracts. Both selected direct and
  companion paths must observe later costs/heals from this one owner after fresh
  reopen. Changing Factory path equality alone cannot establish this contract.
- Handoff: exact parents, private delta, authority provenance and one executable
  normal packet flow/caller/RUN_COMMAND from the existing packet-test-client-v5,
  with first error/partial-store/close handling. Until the owner supplies this
  product contract, a support packet trial cannot be honestly prepared here.

The narrow root UID1 actor-only summon does not require this resource cutover
merely to publish an actor; its separate genuine input/configuration/pose/absence
blockers remain with their existing owners. This result must not stop independent
ready work or claim that any actual companion summon/support packet was sent.

## Minimal source verification

From repository root:

```powershell
python -B work/local_original_session/implementation-companion/companion-joint-resource-v1/inspect_source.py
```

This script parses only the seven relevant selected source modules, checks ten
specific API/guard facts, compares their exact selected hashes, and reads bounded
saved metadata. All seven passed files match the existing summon-input manifest
before and after. It constructs no product object, imports no runtime, sends no
packet and opens no Store. Existing cold-source and actual mage preparation PASS
are reused. Source conclusions are labeled as such; there is no fabricated runtime
failure. `manifest.json` pins reviewed parents and artifacts. No product diff,
runtime caller, queue registration or direct root/Test notification was created.
