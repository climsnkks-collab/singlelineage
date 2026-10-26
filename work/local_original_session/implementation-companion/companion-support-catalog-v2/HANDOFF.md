# COMPANION-MAGE support catalog v2: Heal metadata reassessment

WRITER_RELEASED. `source_ready:false`, `run_ready:false`, `test_ready:false`.
No product callback, parser/admission helper or gameplay caller was created.

The real assets now prove Heal UI ID **0**, range **10**, target text
`self, other` / one PC or NPC within ten cells, MP4/HP0 and instantaneous effect.
`spelldesc` name/detail IDs are 1/2, not spell IDs. The pinned joins and CommonSpell
record both use spell_id0. The actual local spell_list bytes match the exact
selected metadata input hash. Thus UI-to-retained-table ID0 is established.

The first missing contract is the mapping/admission into an **installed Rule
and accepted companion support key**. Selected seventeen Rule rows omit Heal0;
Light is ID1. Selected metadata construction accepts self only, and selected
Rule requires duration_ms>0. Accepted companion SupportRule, SpellCapability,
learned view and in_range entries require positive spell IDs. Passing zero
fails those contracts; changing Heal0 to Heal1 would wrongly select Light.
The selected cast codec preserves the signed key bits without an offset, and
the selected route also requires a positive identical key. No new alias or
wire mapping is inferred. No installed owner/Rule instance was constructed.

Even after that source contract is completed, the metadata range10 does not
choose a coordinate metric, LOS rule, PC target/lifetime admission or approved
LOCAL policy. Current server actor/owner positions may support a server-only
predicate when those contracts are supplied; this reassessment does not make
client pose a prerequisite for that server-only policy. No guessed metric or
fake pose was added. Separate opt-in targeting/effect policy remains owned by
its assigned writer.

`source-contract.json` records proved facts, first missing producer and next
inputs. `manifest.json` pins thirteen files, including both requested actual
assets, current selected metadata/Rule/support/cast sources and retained joins.
Minimal source check from repository root:

```powershell
python -B work/local_original_session/implementation-companion/companion-support-catalog-v2/verify_source.py
```

Verification reads hashes/AST/JSON/CSV only, including accepted literal Rule
rows. It imports no product, creates no owner/configuration/callback, and touches
no game/server/socket/port/save/direct handler/Test copy/queue. v1 and every
prior/shared path remain untouched. No root/Test message or enqueue was sent;
return goes only to the feature main. Existing v1 range finding is narrowed by
this new asset evidence, not rewritten in place.
