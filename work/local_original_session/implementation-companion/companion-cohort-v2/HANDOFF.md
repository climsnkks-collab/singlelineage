# COMPANION-MAGE coherent private cold selection v2

WRITER_RELEASED. `cold_import_ready:true`, `run_ready:false`, `test_ready:false`,
runtime **UNRUN**. One exact cold source graph now combines all completed leaves;
it is not a runnable companion Factory configuration or a packet success.
Writes are confined to this new directory. Prior/shared products, current Test
selection, APIs, queue, saved files and process ownership are preserved.

## Exact selection and glue

`manifest.json` pins eleven input manifests, the selected cohort, dependencies,
loader, assembler, scenario, verifier and result. `cohort.json` selects 183 rows;
181 are actually imported and pinned. The inherited `desktop` and `public_broker`
rows are non-imported references. `selection-delta.json` records all 13 changed
selected rows against exact companion-cohort-v1 parents.

Selected complete descendants:

- companion-canonical-v1: canonical_batch and hp_resource_document.
- companion-resource-runtime-v1: hp_resource_owner and hp_status.
- companion-skill-graph-v1: skill_buff, canonical_skill, buff_lifecycle and
  buff_skill_document, including its existing nominal canonical handoff.
- companion-ack-realm-v1: namespace root and exact ACK/realm external dependencies.
- companion-factory-v1: full canonical_feature_bootstrap.
- companion-broker-hooks-v1: full Broker including actual Host lifecycle and
  original delivery/send hooks.

The baseline already selects allied-publication-source-v2, actor-click-v1,
optional-target-v1 and mage-world-v1. Their manifest pins were checked and their
selected rows remain unchanged. No alternate implementations were introduced.

`product/broker.py`, `product/packet_peer.py`, `product/packet_server.py` are exact
byte copies of their completed parents, placed together solely to preserve
Peer.bind's original neighboring `_accept.co_filename` contract. Their source
hashes remain respectively 934fb07a, 8d71f919 and eed8e36d. Selection paths are the
only changes for these copies. No hardcoded guard or source seal was weakened.

`source_loader.py` is the complete ACK/realm loader plus the four-line SKILL
handoff from the already verified skill loader. `source_loader.diff` is the
whole glue delta. Character-state installs before nominal realm/external
movement and ACK. Selected canonical_skill installs before buff_lifecycle,
which consumes the exact module/path/hash handoff once; schema and lifecycle
share that class space. BATCH still uses inventory_aggregate's original cached
loader, then its single exact canonical alias. Existing pin/conflict checks
remain active. Dependencies are byte-identical to companion-ack-realm-v1.

## Bounded reproduction and verification

From project root:

```powershell
python -B work/local_original_session/implementation-companion/companion-cohort-v2/assemble.py
python -B work/local_original_session/implementation-companion/companion-cohort-v2/verify_cold.py
```

The assembler rewrites only this owned directory. Verification is **22 checks
PASS / 181 actual modules and pins**. It checks every selected source, external
dependency, parent manifest, Factory SourceModule identity and relocated bytes;
the actual Broker ACK/realm canonical store identities; canonical authority,
RESOURCE staged_many/support and all required joint SKILL/Factory APIs; nominal
class spaces and consumed handoff; exact Broker/Peer/Server function path.

Actual `_Sources()`, `CompanionBootstrap()` and namespace `Setup(...)` constructors
execute. Setup seals validate actual selected source triples and closes with no
registered owner, account file or optional actor records. No Factory, Host,
CharacterStore, lease, actor, server, socket, port, game, native callback, fake
grant, runtime writer or file Store is created. Factory's constructor requires
an actual existing profile and complete policy/source inputs; it was therefore
not instantiated with a synthetic account or callbacks. This verification does
not exercise attach, selection transitions, commits or send/drain.

## Real saved mage input is now available

`scenario.json` pins the main's companion-summon-input-v1 input/scenario and the
actual Test CREATE/WORLD/current/fresh result. Its seven full saved files under
`validation-profiles/packet-mage-class3-input-v1/` were hashed read-only and are
unchanged. Direct character UID1/class0 and other saved UID2/class3 with
RESOURCE:2 are recorded by that existing input. The missing-saved-mage blocker
from older leaf handoffs is superseded by this actual result. No copy is made
here. Test must prepare a new whole copy when an honest runnable summon trial
is ready; the passed copy must never be modified or overlaid. Preparation PASS
is reused and is not repeated by this cold source check.

## Exact remaining blockers and next implementation

1. No actual user-triggered summon/dismiss packet or native callback contract
   exists in this selection. The source-only actor-click entry does not provide
   the original actor selection callback, ATS create/callback/close or UI thread
   owner. Do not substitute direct Host/controller calls or invent an opcode.
2. The actual full runtime `CompanionBootstrap` and `SharedSupportConfiguration`
   still need source-captured actor/support/shared/direct-world policy callbacks
   and their genuine original owners. Importable Factory APIs alone do not bind
   such a configuration. No default or fake callback is provided here.
3. Factory `_attach_companion` still requires account `broker.realm.store.path`
   to equal Plan `self.profile`. Existing created scopes use a child profile;
   resource-only child preparation is rejected by bind_companion. Scope rebuilds
   do not carry this configuration, and Host attach requires an unstarted broker
   with empty sessions while a real scope transition retains the live broker.
   One explicit account/character/Host lifetime transition is required; the
   exact identity guards remain unchanged. Cold source coherence does not solve
   this live scope transition or claim created-character companion support.
4. Allied publication intentionally returns `pose=None` and AWAITING_POSE.
   Genuine original lookup/pose/absence evidence is still missing. Drained
   Remove, socket close or synchronous Host.closed cannot prove client absence;
   pending leases/UNKNOWN behavior must remain truthful.
5. Complete the original packet scenario/caller/RUN_COMMAND only after genuine
   input and configuration exist, reusing packet-test-client-v5 and the existing
   main-owned summon scenario. `runtime_command:null` is explicit. This source
   package does not add a second wrapper/client/large trial framework.

The prior canonical/RESOURCE/SKILL/ACK/Broker/Factory cold API blockers are now
resolved together and should not be listed as missing source in the next task.
Live owner configuration and input remain open as described. Existing leaf
bounded verification and actual mage acquisition results are reused; no whole
game trial or repeat source suite was added. Main reviews this actual selection
and handles any queue registration. Worker sent no queue/root/Test notification.
