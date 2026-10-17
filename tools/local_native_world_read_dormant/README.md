# CP59 source-anchor dormancy correction

The CP58 reader and trial remain frozen. This successor changes only instruction-anchor handling and adds diagnostic stages. The retained-handle API is unchanged:

`inspect_attached(native, sampler, expected_uid=None, expected_grid_words=None)`

`empty_result(reason)` returns a skipped UNKNOWN observation.

Only a source instruction read at an exact bounded image RVA may be skipped after Native.read reports `region_not_readable` with every condition below:

- committed state `0x1000` and MEM_IMAGE type `0x1000000`;
- image allocation matches the expected LC image and the requested length fits;
- guard is false and exact protection is PAGE_NOACCESS (`1`);
- native metadata requested byte count equals the exact instruction length.

Missing, noncanonical, or different metadata fails closed. Readable instructions still require exact SHA256. The original static contracts and producer hashes remain mandatory. No file bytes substitute for unreadable live memory.

The exception applies only to the 102 instruction anchors. Every object, vtable, strong owner, MyPlayer UID, Transform segment/grid pair, Map/context, tile search, scene, route, and final reread remains mandatory under the existing rules. No memory protections or process state are changed.

The result schema is `lc-owned-world-dormant-read-v1`. `diagnostic.stage` identifies the phase that failed or COMPLETE. Counts distinguish checked anchors, successful readable hashes, and skipped dormant anchors. `source_anchors_all_live_hash_verified` is false if any anchor was dormant. `source_anchor_index` identifies a failed source anchor without addresses. `failure_region_conditions` retains only bounded native state/type/protection/size and boolean conditions, with no addresses.

Dormant anchors never prove execution. Object/tile presence never proves rendered pixels, decoded resources, movement, play, or standalone completion. Existing UNKNOWN and false proof fields are preserved.

File-only fixtures: `python -B tools/local_native_world_read_dormant/tests.py`. Runtime review may load `tests.py` and call `run_checks()`.
