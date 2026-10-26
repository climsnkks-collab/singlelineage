# COMPANION-MAGE — moved-owner retirement v1

SOURCE_COMPLETE / WRITER_RELEASED. source_ready=true, test_ready=false,
run_ready=false, runtime=UNRUN, selected=false.

Exact parent: `../local-allied-server-pose-step-v2/` six products recorded in
parents.json. Parent Allied SHA256
`0bbef07e60c23e631bc8251b2b694151c4fbd08fb0078dde05c1afa3bdc6a600`.
New Allied SHA256
`a6725428c13a2d5afaf5b6f4781224a9c0676e52cc5d530ecd5338506261678a`,
50018 bytes. The six product hashes and exact parent diffs are local to this
folder. `build_private.py` reproduces products and direct motion pins.

The exact parent Controller `_retire_locked` actually supplies retained
`self._owner`, so its original Port identity check passed; the failing parent
boundary is Root.operation comparing retained grid to actual Host grid.
The Port now accepts the original retained DTO or a fresh same-owner DTO,
without interpreting DTO object identity as owner authority. Both routes bind
one actual Host.current_owner snapshot in the separate `record.removal_owner`
field before sending removal. Original publication owner/binding remain intact.

Root.removal_operation_owner checks exact typed registration, real Host owner,
connection/direct lease/lifetime, owner and actor UIDs, alive state, and the
original map. Grid may move before removal begins. Once captured, removal's
map/grid and identities must remain equal to fresh Host state. The unchanged
Root.operation still checks Root/Host/realm, current direct and companion leases,
canonical task/provider/current binding, actual selection and row operation lock.
Original removal_current retains same selection/row/generation/writer/UID/lock
and original _resource authority/path checks; only its owner operand changes.

The same captured snapshot enters preBEGIN Resource proof and is added to sealed
identity anchors. Pending validation uses that exact proof snapshot in original
operation. All pending/Core guard expressions are AST-identical after normalizing
only the owner operand. No direct Store access replaces those Core checks, and
no generic pending Store.current exemption is added.

Tombstone caller authority uses the same retained/fresh identity contract and
revalidates the sealed live operation before mutation. Original typed Actor /
RemovalResult / actual 4E40 / DRAINED / send-return / policy / reader-retired
conditions remain. Receipt.owner remains the caller DTO, preserving Controller's
receipt check. Publication owner is never overwritten. Ambiguous send keeps
leases/record and cannot become absence or successful strict close.

Host and Controller are byte-identical to v2. Default server_snapshot, publication
current, later_current/resource, original resource method and operation are
unchanged. Default follow_distance remains 1. No pose-policy/default movement
changes; no map change rebasing. Original REGISTERED never-emitted removal keeps
its exact owner identity/current guard.

Focused check:

`python work/local_original_session/implementation-companion/local-allied-moved-owner-retirement-v1/verify_focused.py`

51 source/isolated-model checks PASS (verification.json): exact hashes/syntax,
unchanged methods, pending/Core guard AST, direct pins, retained-grid refusal by
original operation, fresh same-owner operation/resource, changed identity/map/
lifetime/selection/generation refusal, post-seal movement refusal, original owner
preservation, fresh-caller Port entry and failed-send UNKNOWN evidence. These use
isolated DTO/Host/Resource/transport doubles; they are not runtime packet or Store
success evidence.

No common/original/Test/queue/ACTIVE files modified. No game/process/port/save
copy/packet execution. Existing v2 final Broker/cohort source pins and normal
packet caller/RUN still require owner integration; this private source alone is
not test-ready. Separate queued removal v5 was not used as parent or overlaid.
