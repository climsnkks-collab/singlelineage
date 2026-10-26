# COMPANION-MAGE actor + click cold graph v1

WRITER_RELEASED_SOURCE_SELECTION_CONFLICT. source_ready:false / test_ready:false /
run_ready:false. Runtime UNRUN. No product source was edited.

Exact reviewed actor-only-cold-graph-v1 selection supplies Factory, locked Host,
actor-config-v2. Exact click-router-v2 selection supplies its Broker/Peer/Server
siblings and companion_actor_click. Relative to the 184-row actor graph, 181 rows
are unchanged; Broker has changed bytes, Peer/Server only move selected sibling
paths with their bytes identical, and companion_actor_click is added (185 rows).
selection-delta.json records every parent and selected pin. Dependencies bytes are
identical to both parents. Loader adds only the reviewed actor-click import to the
actor parent's existing config import; exact reverse delta is recorded.

12 source/cold checks pass: 185 exact selected pins, 183 imports, actual SourceModule
nominal identities, original Broker/Peer/Server sibling co_filename contract, locked
Host and Factory nominal modules, real click Feature nominal import and original
grant route source, original packet source capture, actual saved settings header
and original read-only LocalRealm construction without sessions/namespace ownership.

First actual conflict: companion-actor-config-v2/companion_actor_config.py lines
116-118 passes the selected Broker module into SourceSeal but hardcodes:
companion-cohort-v2/product/broker.py
SHA934fb07af30efd5853fdd147f5dfda64fb5f16b730914e3757e89ec50963c46a.
The actual clicked Broker is companion-click-router-v2/product/broker.py
SHAa22a5e63f3ccaf25e21cbea2368946fb240f315835d99ee1517250be19ec0cea.
SourceSeal refuses UID_ROOT_SOURCE_BYTES_OR_MODULE_CHANGED. Exact traceback and
pins are retained in verification.json. No speculative actor-config/source-seal
patch or guard deletion was made; this graph is not a coherent accepted callback
graph and must not be marked source/test ready.

The actual seven saved-input files were pinned before/after and retain identical
bytes. Entire saved-input directory listing is identical. No Plan bind, Host or
Feature install, callback actor factory execution, game/server/socket/ports/save
writes, native publication, summon or UI result occurred. No shared/prior path,
queue or Test file was modified.

Bounded command:
python -B work/local_original_session/implementation-companion/companion-actor-click-graph-v1/verify_cold.py

This command reports the exact expected blocked selection and preserves the raw
error. Main owns the next reviewed source selection decision and queue registration.
