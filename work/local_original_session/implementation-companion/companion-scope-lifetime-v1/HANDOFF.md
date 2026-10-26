# COMPANION-MAGE account / selected scope lifetime review v1

WRITER_RELEASED. Source-only result; `run_ready:false`, `test_ready:false`, runtime UNRUN.
No product descendant is published: the selected source does not supply a safe live
account-to-child Host transfer. No source guard was weakened. Only this new path was written.

## Root direct UID1 with saved other mage UID2

The account is the whole saved `characters.json`, not `character-state/2/characters.json`.
The real saved input contains direct UID1/class0 and other UID2/class3. A full root
Plan can satisfy the existing exact account path equality with its own Setup and
RESOURCE/SKILL owners, and cold attach exactly one Host **if** the genuine complete
configuration is supplied. This is a conditional source conclusion, not a constructor
or attachment result. `bind_companion` still requires actual captured callbacks and
joint SKILL; `CompanionBootstrap.attach` still requires an unstarted empty broker.

The ordinary root selection does not switch Plans: `CreatedCharacterScopes.selecting`
returns at `uid == realm.profile_uid` (line 616), before a transition token or close.
The realm's normal `selection` callback then calls `Host.selection_started` (broker
lines 691-699), acquiring the direct lease from the account store. The saved other
mage remains another account character; summoning that character is not a direct
selection of the child profile and requires no child Plan for this root-only case.
No migration is needed merely to retain the cold Host through UID1 login/selection.

Normal root Restart/reselection likewise has an existing source path: Broker
`_prepare_restart` awaits `before_retire_locked`; controller dismissal must report
EMPTY, then original drained restart cleanup calls `selection_retired`, releases the
direct lease and removes selected state. Selecting UID1 again takes the unchanged
same-profile branch. UNKNOWN/failed dismissal cannot be converted into retirement.
Joined connection cleanup remains separate from synchronous `Host.closed()`.

## An actual account-to-child transition cannot retain this single Plan/Host

The source intentionally retires the old Plan and builds a new Plan/provider/Store
inside the current lexical connection operation. It is not a selected-field update:

1. `selecting` issues its real `_ScopeTransition`, calls old `plan.close`, clears
   runtime and calls `_construct_graph` (character_scope lines 617-669).
2. First new source-level blocker after a legitimate prior selection retirement:
   `plan.close -> _close_companion -> Host.closed -> SharedSupport.close ->
   provider.unregister_companion_authority`. The live transition still owns
   `provider._scope`; unregister requires `_scope is None` and raises
   `BATCH_COMPANION_SAME_RETIRED_SCOPE_AUTHORITY_REQUIRED` (canonical_batch 169-178).
   Even without that scope check, the second guard permits only cold or joined
   cleanup, not a running broker transition. This failure is inferred from source,
   not observed. If selected state were not retired, Host's earlier
   `COMPANION_UNRETIRED_CHARACTER_LEASE` guard would stop first.
3. Bypassing close would leave SharedSupport sealed to the retired root owner,
   provider, Store, document and schema; its `validate_sources` rejects replacement.
   Original Plan retirement also closes Setup and clears companion source captures.
4. `_construct_graph` creates a new child Plan; full root Plan identity cannot be
   retained. Child Plan profile is different from `broker.realm.store.path` and
   fails existing exact attachment equality. The default child graph is RESOURCE
   only, which `bind_companion` rejects. Fresh root reconstruction does not carry
   companion configuration either.
5. Host and shared authority registration/install are independently cold-only.
   `Host.closed` sets `_closed` but does not clear the Broker/realm/configuration
   Host references. A new attach on the live Broker is not a supported rebind.
6. CompanionBindings additionally requires direct and companion lease `_profile`
   to equal the actual provider source-store profile (companion_binding 87-94).
   Weakening Factory path equality alone would not establish a same-owner contract.

Therefore no safe source-backed transition edit is available without a new explicit
account lifetime owner and a genuine scoped shared-owner retirement/reinstallation
contract. This task does not invent that contract, silently disable scopes, retain
stale shared references, force-clear leases or relax account/profile equality.

## Precise remaining inputs

For the narrower root UID1 trial, scope migration is not its first blocker. The
first missing runnable input is still the complete source-captured cold actor,
shared-support and direct-world configuration plus genuine summon action/callback;
there is no packet RUN_COMMAND. Native/packet input cannot be replaced by Host.command.
Actor publication also still needs genuine pose/absence evidence for retirement.

Read-only saved evidence adds a distinct later constraint: root inventory contains
only `RESOURCE:1`; the passed mage `RESOURCE:2` exists only in the child inventory.
Shared support uses one original BatchStore and requires an existing linked RESOURCE
document. The child's actual RESOURCE does not by itself supply a root BatchStore
participant. A future support path must source and persist this linkage through an
explicit legitimate owner contract; copying/moving that row is not authorized here.
This fact is not claimed to prevent an actor-only summon before a support action.

## Verification and preservation

`verification.json` records bounded AST/source branch checks and read-only input
hash checks. `manifest.json` pins the exact reviewed cohort, Factory, Host, scope,
shared support, canonical and lease sources. Existing coherent cold verification
and actual mage preparation PASS are reused; no cold suite or game trial repeated.
Seven Test-owned saved input files matched their existing pinned hashes before and
after this review. No Factory/Host/controller/handler constructor or runtime call,
socket, port, game, Test copy mutation, queue registration or direct notification
was performed. Existing main branch and unrelated dirty files were preserved.

No product diff exists because no product bytes changed. Main can independently
review these exact source locations and select the root-only configuration work;
the actual cross-profile transition remains explicitly unsupported.
