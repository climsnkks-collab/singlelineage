# ATTACK-MAGIC LOCAL current visibility safety port v1

PRIVATE_SOURCE_ONLY / WRITER_RELEASED / default OFF / test_ready:false / RUN_COMMAND:null.

The selected LOCAL server-state cast can currently prove same-map finite range and target/issuer/current lifetime, but cannot prove projectile visibility or current doors. This leaf closes the silent range-only admission hole by requiring an explicit trusted server visibility producer before hostile cost planning. It does not require native visual completion. Original/native magic feedback, NPC HPbar and original projectile policy remain UNKNOWN.

## Actual source boundary

Exact parent is `../extended-direct-graph-v1/cast_route.py`; all parent/reference hashes and sizes are in `manifest.json`, and `changes.diff` contains only the constructor, current visibility requirement and close hunks. The selected graph uses `retaliation-npc-neighbour-goal-v28/npc_world_navigation.py` and `retaliation-npc-server-navigation-v26/npc_edge.py`. Navigation `flag_blocked` reads bit1 MOVE flags; `_flags` authenticates resource S32 chunks through AssetProvider and retains UNKNOWN on a failed load. Its `CLEAR_SERVER_MAP_SUBSET` is a current adjacent MOVE/occupancy subset, not projectile or door authority. The edge adapter does not add those missing semantics. Existing later v56 audit and REA283/284 confirm the same unresolved projectile/door binding boundary; no REA/native/runtime work was repeated.

REA283 proves raw S32 plane/Cell+4 and mask/override access, not EnergyBolt projectile mask semantics or current doors. REA284 proves saved id/range parsing, not installed same-operation row/Actor/Map or door authority. No static/reference mask or range can become a live clear result.

**First missing producer:** same-operation authoritative server projectile-passability plus dynamic door/override state, covering the complete caster-to-target segment, endpoints and corner policy, under the original operation lock and current issued NPC lifetime. It may be a LOCAL server authority; native visuals are not a prerequisite.

No concrete map0 adjacent alternative is supplied. Even adjacent cells need a supported edge/corner and current-door authority. Current MOVE mask1/occupancy is insufficient, so map0 adjacency still fails closed. This is a missing source contract, not a request to force positions or build a second map.

## Source port and route hunk

`local_visibility.py` defines `CurrentProjectileVisibility`, immutable `VisibilityQuery` and typed `VisibilityDecision`. The query carries exact operation, decoded request, BoundTarget, PacketCurrent, namespace, issuer, spawn, RESOURCE snapshot and captured caster/target geometry. A trusted cold source must implement synchronous `decide` and `current`; `current` raises on stale map, doors, override, operation, target or lifetime and returns None on success. CLEAR requires both non-null current map and door authority. These opaque objects are source-owned current identities, not arbitrary client tokens. Only a reviewed concrete producer can implement their authority; the type itself cannot establish it.

No such producer exists here. Default `UnresolvedVisibility` raises `CAST_LOCAL_PROJECTILE_DOOR_CURRENT_PRODUCER_REQUIRED`; boolean callbacks are rejected. BLOCKED and UNKNOWN reject with `CAST_LOCAL_VISIBILITY_NOT_CLEAR`. The port creates no protocol reply, synthetic success, actor proof, Store writes, MP cost or NPC HP change.

The route has an optional cold `visibility` producer input; omission chooses unresolved. At `LocalPacketNpcAdmission.current`, existing operation/PacketCurrent/lease/BoundTarget and reference range checks run first. The guard then checks the same operation and map/door decision, with held lock and immutable geometry, followed by existing current/target revalidation. Existing `admit`, `target_bound` and HostileCastContext current checks call this boundary before `plan_hostile_magic_locked` and aggregate cost/HP preparation. Default admission `enabled=False` and `Feature.actual_cast_enabled=False` remain intact. Existing self-cast and original SourceCastAdmission paths are untouched.

Cold graph selection is intentionally absent. Future composition must select this route as `cast_route` and the new source as `local_visibility` in the SAME nominal loader namespace, then pass the reviewed concrete producer to the admission constructor. Installing the new module without a producer never makes a cast executable. No graph/client/Factory/Store/shared source was modified.

## Focused verification and limits

Run `python -B work/local_original_session/attack-magic/local-visibility-v1/check_source.py` from the repository root. Seven focused checks PASS: adjacent-map0 default rejection, bool producer rejection, BLOCKED/UNKNOWN rejection, missing/stale/boolean-current/changed-geometry rejection, synthetic contract identity and close, held lock, exact parent/product pins and route ordering. The synthetic CLEAR double tests only interface mechanics and is never a live producer, map observation, LOS PASS or runtime result.

No Store/server/packet/Test execution, final graph import/Plan, learned account admission, native visual or actual clear/blocked visibility observation occurred. Parent files and existing PASS results remain unchanged. Runtime RUN remains null and test_ready false until the concrete producer and final caller/source graph are supplied.
