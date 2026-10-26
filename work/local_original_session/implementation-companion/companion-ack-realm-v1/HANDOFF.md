# COMPANION-MAGE ACK / canonical realm join v1

WRITER_RELEASED. Private join source complete; full companion runtime remains
incomplete. `cold_import_ready:true`, `test_ready:false`, runtime **UNRUN**.
No shared/frozen sources, Test API/client, queue, account, save, port or process
were changed. No CharacterStore instance, character lease, Factory, root owner,
actor, Host or transport was created. Existing unrelated worktree changes were
left in place on `main`; this private descendant does not require a Git branch.

## Exact source selection

`cohort.json` descends directly from companion-cohort-v1: the only changed selected
row is `item_uid_namespace_root`, pointing to the private two-constant descendant.
All other 182 selected paths/hashes, including actual allied v2 Broker/Peer/Server,
remain unchanged. The v5 character-state source remains byte identical at its
original selected path/hash `536cb683...`.

`dependencies.json` replaces original ACK and realm validation rows with the exact
private paths/hashes. Its load order chooses private nominal realm **before
movement**, whose original source imports realm constants; private nominal ACK is
installed before Broker imports it. `source_loader.py` installs the selected
nominal character-state once before external imports. Existing validation and
conflict rejection remain active. This is a real source selection, with no
post-import mutation of Broker.ack, realm.CharacterStore, locks or canonical APIs.

`realm.py` is frozen accepted v5 realm766310cb with only project-root discovery
adapted to its private location. Actual `WIRE`, original wire hash, protobuf,
schema, class, decoder, roster, select and create bodies are unchanged. It imports
the same `tools.local_character_creation.character_state` selected by companion
modules and inherits its real CanonicalCharacterStore, lease methods and LOCK.

`ack_enter_world.py` is original ack2da189d4 with only project-root, exact realm
path/hash and single nominal realm selection changed. Its complete `wrap` body
and every other function/class are unchanged. KEY/login/roster/WORLD handling,
original frame checks, CONNECTION path/hash and default STORE_PATH remain intact.
Existing nominal realm at a different file is refused; this loader never replaces
a live module. The normal caller still supplies the actual account path through
the existing Broker/LocalRealm path; no separate companion store is introduced.

Both namespace character seals now pin this exact private realm (`ea46f90b...`)
because default and allied opt-in use the same source in this selected descendant.
All namespace functions/classes, registries, source validation, current/CAS,
reserved ranges and class3 appearance approval are byte-equivalent at the AST
level to the exact cohort parent. The two constant changes do not manufacture
authority, a selected character or a lease.

## Minimal verification

```powershell
python -B work/local_original_session/implementation-companion/companion-ack-realm-v1/verify_cold.py
```

`verification.json`: **12 checks PASS**, 181 actual cold module imports and pins.
Actual imported Broker.ack is private ACK; its realm is the one nominal private
realm; its CharacterStore inherits the selected v5 canonical store and uses the
same CharacterLease and LOCK. Real `acquire`, `require_current`, `release` methods
are inherited unchanged. Both source seals and ACK pin match. Original fixed
wire produces/validates the same enter ACK. Full realm/ACK/namespace function and
class ASTs equal their respective direct parents. No leases or root authority
were issued. This verifies source resolution and availability, **not successful
direct/companion lease issuance against saved records**.

The unchanged original Map hook also loads a historical ACK under its frozen
private alias, which loads old noncanonical realm under
`_owned_local_character_creation`. This is an inherited read-only MAP protocol
dependency, not the selected Broker store and not a second canonical class space.
The bounded check confirms only state+selected realm expose this canonical store.
Broker's unchanged Map usage is `map_frame` and `validate_map_frame`; no legacy
store is constructed by cold import. Its original frozen hook/compiler pins are
preserved. Do not claim that every historical hook was migrated to canonical state.

## Remaining trial boundary

This resolves the cohort HANDOFF's actual ACK/store/namespace source blocker.
Canonical Batch/RESOURCE/schema/lifecycle and Factory/Broker Host joins remain
other owned work. Genuine summon/dismiss input and a normally obtained saved
other class3 mage with actual full account/RESOURCE are still unprovided here.
The accepted v5 schema remains exactly v5; compatibility with newer separate
character-growth initial-row extensions has not been tested or claimed.

Reuse mage-scope-caller-v2 and current Test packet API for the existing normal
preparation sequence after main selects a coherent executable graph. No new
wrapper/client, fake summon packet, direct Host call, or packet trial command is
published here. `test_ready:false` is mandatory. Main reviews and merges only
these private deltas; this worker enqueues nothing and sends no root/Test message.

`assemble.py` rebuilds the exact private sources, cohort and dependency selection;
adjacent `.diff` files contain each full change. `selection-delta.json` and
`manifest.json` pin the exact parents and delivered artifacts.
