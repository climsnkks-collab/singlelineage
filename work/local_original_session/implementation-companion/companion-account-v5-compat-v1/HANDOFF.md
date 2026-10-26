# COMPANION-MAGE account-v5 compatibility finding

WRITER_RELEASED / SOURCE_ONLY. The compatibility report is ready; implementation,
direct consumer, run_ready and test_ready are false. Runtime UNRUN. No product
descendant is proposed because the present sources lack a complete compatible
publication/actor-only/scope lifecycle contract. No ITEM/common/prior source,
Test profile/copy, Store, process/ports, queue or REA change/execution occurred.

## Reused actual result

The exact actual result is packet-account-multi-canonical-actual-v1/
account-world-result.json SHA96e8ec0266c916a3a129030ac92273309b9957a196a893048773aa26726cb4cc.
Its MAGE UID2 -> ROOT UID1 -> MAGE_FRESH UID2 owners all reached normal WORLD/current,
same account Store and original clean close/RETIRED Plan. C2S6 per owner. The actual
root inventory is Batch v3/canonical v5, live members1/2, RESOURCE:1/RESOURCE:2,
pending null and root cursor1073741825. SKILL is absent, not an empty learned
document. Host publication, companion CAST, summon/support and normal protocol
Quit are not covered by that result. Actual-account-summary.json pins all seven
post-PASS files and stores only bounded metadata/digests, never archived raw hex.

## Exact graph comparison

companion-actor-runtime-rebind-v2 has185 rows; the actual account-v5 cohort has184.
There are183 shared names:165 exact identical rows,167 byte-identical rows,16
changed byte selections plus2 path-only sibling changes. The complete exact
path/SHA/size pairs are comparison.json. Account-only is account_canonical;
companion-only are companion_actor_config and companion_actor_click. Their union
would be186 names; this report does not select that union as an executable graph.

Changed byte selections are:

| Area | Exact module keys |
|---|---|
| Runtime/owner | broker, canonical_batch, canonical_feature_bootstrap, character_scope, companion_host, companion_shared, hp_resource_owner, item_uid_namespace_root |
| Custody | inventory_store, popup_partial_stack_v2, packet_transfer_owner, item_ground, item_transfer_session |
| Literal consumers | ground_client_retirement, item_transfer_runner, potion_credit_source |

packet_peer and packet_server have identical byte hashes but different sibling
directories. Keep the source Broker/Peer/Server HERE/co_filename tuple coherent;
equivalent peer/server bytes alone do not permit mixing source directories.

## First concrete blocker and subsequent contacts

1. Unchanged companion185 cannot consume the actual root canonical v5. Its
   companion-canonical-v1/canonical_batch.py BatchStore._validate_canonical handles
   only4/2/legacy1. At line1031, the exact BATCH_CANONICAL_LEGACY_SHAPE predicate is
   false for the actual v5 document. verify_compat.py evaluates that original pure
   predicate over the actual saved JSON without constructing a Batch/provider or
   fake owner. This is a source/data incompatibility, not an observed new runtime
   failure. Merely changing the input path cannot make the185 graph account-aware.

2. AlliedPlayerPort is byte-identical in both cohorts. RootPlayers._resource at
   line137 reads character-state/<lease UID>/inventory.json directly for the mage's
   RESOURCE. After cutover this is preserved history, while the account root Batch
   is the sole live participant authority. The account InventoryStore._path_check
   explicitly refuses child authority with INVENTORY_CHILD_HISTORY_RETIRED_TO_ACCOUNT_AUTHORITY.
   The child may still contain equal old values; equality does not make it live.
   Allied _collision_check also dispatches only canonical4/2/legacy1 and its line211
   ALLIED_ORIGINAL_INVENTORY_SCHEMA_REQUIRED predicate rejects the actual root5.
   These checks precede original allied UID reservation/publication. Reading the
   old child/immutable origins as current, skipping the collision scan or adding a
   second Batch/RESOURCE owner would violate the account contract.

3. Switching to account184 solves custody parsing but not actor installation.
   Account canonical_feature_bootstrap.bind_companion has no actor_publication_only
   option and at line441 requires not self.resource_only plus a full
   SharedSupportConfiguration (COMPANION_ONE_COLD_SHARED_BOOTSTRAP_REQUIRED).
   The actual account has no SKILL. Replacing missing SKILL with a made-up empty
   document or weakening this guard is not a compatible actor-only installation.
   The reviewed companion RESOURCE actor-only Factory33ff is a different source
   and lacks the account scoped attach/close token forwarding.

4. Current actor-config92b seals Brokera22/Hosted86/Factory33ff explicitly; the
   account sources are Broker934/Host219/Factoryc876. A direct mixed selection
   fails source provenance. Literal repinning alone is also insufficient:
   account CompanionBootstrap.fresh_for_scope reuses self.actor_factory and
   self.direct_world_for, while actor-config92b binds once to one actual Broker/
   Plan and admits only original unstarted CREATING construction. Reusing that
   already bound closure for an account ATTACHING transition conflicts with
   COMPANION_CONFIG_RUNTIME_BIND_ONCE_REQUIRED and the original current/close
   contract. Resetting the latch or changing captured realm/owner after close
   would reactivate authority rather than issue a fresh source-owned lifetime.

## Supported pieces and required next contract

The two saved characters and their source CharacterStore/lease module are shared.
The existing root-relative direct/companion lease identity conditions can express
UID1 direct plus UID2 companion in one account once a genuine Host owns them;
this report does not manufacture or acquire those leases. The typed allied
0x30000000..0x3000ffff allocator/record/send-drain authority remains separate from
the actual item account cursor and NPC domain. It must stay under the one genuine
root Setup/_ACTIVE/provider/Store, never a second owner or sidecar RESOURCE ledger.

The account codec already exposes live members; the account Batch contains both
real RESOURCE participants and preserves original joint/linked-resource machinery.
canonical_skill, skill_buff, companion_binding, companion_spell_rules and
companion_support selections are exact shared bytes. SharedAuthority's original
refresh_resource/resource_snapshot methods are AST-identical in the account
descendant. This supports reusing the existing CAST engine, not claiming it works
with absent learned/SKILL input or that publication already reads the same Store.

A compatible next implementation needs one coherent account-v5 graph; a genuine
pre-publication same-root Batch/lease/current resource accessor and live-member
collision scan; the reviewed RESOURCE actor-only admission combined with account
scope token forwarding; and source-owned fresh actor callback/Host lifetimes on
the actual transition. Original old Host/leases/bindings must retire before any
new owner, original lexical current/CAST scopes and strict close stay intact, and
missing SKILL remains absent. These changes span consumer and lifecycle contracts,
so this bounded comparison stops before speculative product changes.

## Accepted ITEM target port constraint

The exact main-accepted read-only port is spellbook/companion-item-target-view-v1/
manifest.json SHAea7e5085e0222f9098b4b61651a06ebc3598bfde217e01ffa6aeea2d2952ebb8;
source companion_item_target_view.py
SHA4d2844c63b8904ca2a15837d966e106fc7aa808a20b3727065c0346b2729da18.
Its literal Host219bfd8793e52a7ed263381c201f2ae0105c302c6add8c9ce95d0a09cba76dd5
and Core86c0d7d13a9649840cc875c8368b96d9ef698c02dd1241fcd1998063be14c0e9
are the exact account-v5 sources. Companion Hosted866 is not a valid substitution.
Any future changed Host needs an explicit coherent port descendant/review; this
report does not repin the accepted port or claim an interface is installed.

The port requires four genuine current SourceModules, including the final typed
interface module. Installation occurs only after actual Host attachment and an
original registered companion issuer, before Broker start. The final interface's
own synchronous open_items body must directly call the locked read under original
Host row/active lease/actor/owner/panel/epoch checks. It calls original
provider.bind_companion -> BatchStore.restore -> provider.current and returns an
immutable member snapshot. native_opened=False/action_admitted=False remain exact.
Equipment is refused as COMPANION_ITEM_TARGET_EQUIPMENT_STATE_UNSUPPLIED; UID2 has
no supplied GearState. The final typed interface/actual retained invocation are
still unsupplied/UNRUN. This port consumes an already published/current companion;
it does not solve the pre-publication RESOURCE/collision or Host-lifetime blockers.

## Bounded verification

    python -B work/local_original_session/implementation-companion/companion-account-v5-compat-v1/verify_compat.py

18 source/pure DTO checks PASS, including the accepted ITEM port constraints.
Every selected/parent/artifact pin and all actual
post-PASS seven-file hashes were checked; the entire Test input directory listing
is unchanged. No selected product module import, constructor, registered owner,
Realm/Plan/Host/Broker/server/socket/ports, actual lease/current/CAST, Store/UID write,
new profile, packet or REA execution was performed. No runtime success beyond the
reused actual WORLD result is claimed. Product changes0; no runnable/Test SKU.
