# COMPANION-MAGE private SKILL schema/nominal graph v1

WRITER_RELEASED. Bounded SKILL source graph completed; whole companion product
remains incomplete. `run_ready:false`, `test_ready:false`, runtime **UNRUN**.
All writes are inside this new directory. No queue registration or root/Test
message, Factory/Broker/ack/RESOURCE owner edits, game, socket, port, account,
save or runtime actor operations were performed.

## Exact products

`manifest.json` records complete exact parent/patch/output triples. Four full
private descendants and their adjacent exact-parent diffs are supplied:

| Product | Current parent SHA prefix | Output SHA prefix |
| --- | --- | --- |
| skill_buff.py | 063120c7 | 1f328294 |
| canonical_skill.py | c1ef77e4 | 022cc8d9 |
| buff_lifecycle.py | 0ca0a8ca | 18d35cd5 |
| buff_skill_document.py | 0c26110b | 82e15d73 |

The three former skill_buff conflicts (hunks 2,3,5) are resolved. The row shape
accepts optional received_buff_sources; learned IDs still use the exact current
learnable catalog, including learned non-cast IDs. Cooldowns still filter learned
IDs to cast rules. A non-learned buff needs a validated source caster in the same
account rows, distinct from the recipient, who learned that exact cast rule.
The current `rule=self.rules[spell_id]` remains, and only removal can accept a
received buff without learning it. Expiry/removal/self-cast clear provenance.
Existing resource, cooldown, time, self-target and atomic commit guards remain.

The other three full accepted v5 patches apply byte-exactly after LF text
normalization. They add the joint-stage canonical authority and pure support
event/exclusive policy joins, preserve normal Buff/catalyst/catalog behavior,
and clear received provenance during lifecycle removal. Saved provenance alone
does not grant casting or refresh authority; ordinary canonical stages cannot
manufacture or extend received provenance.

## Single nominal class space

`source_loader.py` is the cohort-v1 exact loader plus one cold selection handoff
before executing buff_lifecycle. It first installs/verifies selected
`tools.local_original_session.canonical_skill`, then supplies its module/path/SHA
as `_COHORT_CANONICAL_SELECTION`. The accepted lifecycle source consumes and
removes that handoff, checks the exact 022cc8d9 pin and sys.modules/package/path
identity, and subclasses that canonical Service. The selected extended schema
also subclasses that same canonical SkillDocument. No module reference is
reassigned after execution and no private canonical duplicate is loaded.

`cohort.json` changes only these four selected source rows. Dependencies and all
other selected rows remain identical to cohort-v1. This loader intentionally does
not select companion-canonical-v1's completed BATCH/RESOURCE pair or any other
worker's concurrent changes. Main must combine those exact selected descendants
with this graph in its one final selection; this is not a combined executable
Factory SKU. The existing nominal loader handoff must be carried forward.

## Bounded verification

From project root:

```powershell
python -B work/local_original_session/implementation-companion/companion-skill-graph-v1/verify_source.py
```

`verification.json`: 27 bounded checks PASS, 181 pinned cold imports, 72 existing
methods byte unchanged. Checks cover parent/patch/output bytes, exact v5 patches,
the exact changed-method scope, current learning extensions, canonical nominal
identity/base classes, consumed handoff, no old private canonical duplicate and
support schema availability. No Factory/Host/Store/lease/actor is instantiated.
This is source and import verification, not gameplay or packet success.

Reproduction: `python -B .../companion-skill-graph-v1/rebase.py`, then the verifier.
The rebase only rewrites this owned directory. Parents and patches are pinned.

## Remaining integration and packet boundary

The former lifecycle/schema nominal mismatch is resolved in this private
selection. Still required: combine the completed canonical/RESOURCE source pair
and exact accepted RESOURCE owner/status patches; integrate actual Factory cold
bind/attach/current/cleanup and Broker Host hooks; select the independently owned
ack/realm canonical store descendant and matching namespace proof. These are
separate owned joins and were not edited here.

The source-bound summon/dismiss input and verified saved other class3 mage plus
its actual full-account RESOURCE input remain unprovided. Consequently no honest
companion packet RUN_COMMAND can be supplied from this bounded graph. Preserve
the existing reviewed mage-scope-caller-v2 preparation caller and current Test v5
API; complete their actual source/input selection before execution. Do not use
direct Host/controller/handler calls or invented packets. Native pose, client
lookup absence, UI, actual support commit/delivery/restore and gameplay remain
unverified. Main owns final review and any integration queue entry.
