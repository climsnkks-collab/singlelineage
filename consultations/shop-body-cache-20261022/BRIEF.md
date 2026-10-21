# SHOP interaction blocked before original input: BODY cache direction review

## Goal and scope
Restore one complete local SHOP interaction through the retained original client and local server: normal NPC input -> original request 0x4E43 -> canonical menu/list -> BUY/row/quantity/confirm -> server/store/adoption -> independent client inventory -> cleanup. Review only the failed NPC-input approach and its direct dependencies. Do not evaluate the entire project or substitute a single getter diagnosis for this feature-level decision.

Original client binaries/resources and user saves are preserved. The adapter runs only in an existing owned non-input desktop and owned UI thread. Common integration and actual game execution have separate owners. This repository snapshot contains authored adapter code only, not original binaries/disassembly, credentials, full logs or saves. Do not infer original ABI/semantics from our fixtures or the adapter alone.

## Three failed attempts and confirmed boundaries
| Attempt | Confirmed boundary | Missing result |
|---|---|---|
| 339 | Original owned-window MOVE/DOWN/UP returned; no native fault | No 0x4E43/menu within existing deadline |
| 343 | Same normal messages returned; one post-MOVE key0 snapshot was u64 max | No 0x4E43/menu; max alone did not identify cause or prove no target |
| 354 | Matched full production Native build and one source-derived BODY request; native UNKNOWN 62007 / point_failure BODY_CACHE / attempted=returned=0 | No effective point, no WM attempted, no 0x4E43/menu; BUY and later stages not reached |

339/343 used a measured name-label point, whose pickability was not proven. 354 kept that measurement as a geometry/admission echo only and attempted to derive the actual NPC point from source-qualified BODY geometry. Do not propose another arbitrary label/pixel, fixed rectangle, retries, added delay or a longer deadline. The first two runs did not prove the source-derived BODY approach works. 354 did not observe which internal CachedBody predicate failed.

## Current implementation and assumptions
The first NPC step requires point_source BODY and expected_npc_uid 10001; selected player UID is 1. Remaining SHOP UI steps use EXPLICIT coordinates. Driver._click -> strict Python request -> strict Native parser -> Execute under existing Held UI/state/scene/ActorSubsystem and current owned UI thread -> DeriveBodyPoint -> original three window messages. Original request XY echo remains distinct from effective_point. Native output -> strict Python result -> full Driver report carries point_state, point_failure, pre_move_body_query, hover and BODY metadata. Canonical menu response remains the hit authority.

Before the first WM, DeriveBodyPoint performs a conditional current GI owning-Pair/global CameraSubsystem join; exact existing key4 Camera profile; owned GameStateLand W+8 SceneRef and either direct Scene/Camera or Scene/one typed GameLayer/Camera managed-child membership. Camera offset for the supported actual Camera profile is +3C/+40, not the separate base-view +18 example. It copies only POD before leaving the no-original-call interval; no raw pointers escape. It then uses the current Actor/action/resource subset to compute a BODY query rectangle, maps one derived interior midpoint back through current normal HostView mouse mapping, quantizes once to signed16 and forward-checks original comparisons. There is no point fallback.

CachedBody may return UNKNOWN for current ownership, Actor registry/UID/type, component/backlink, current action getter profile/token, SPR/action/frame, existing C+58 resource cache, child/tile, shape/correction/math, or final current/token readback. BODY_CACHE labels that whole operation; it is NOT an observation of a C+58 cache miss. Actual internal values were not exported in 354.

Released source work supplied: Actor lookup order and passive UID/component/pose; conditional direct current-action token, exact SPR/action/frame and existing resource-cache-hit BODY math; natural G/key4 Camera producer/retirement and same-UI current owner/child borrow. Existing successful source/wire/registration/build checks are reused. No proof yet connects merchant UID10001 creation/model/action/frame/resource-cache production/update to the first passive BODY read. The source helper 95E10 was identified as a Pair MOVE constructor, not an external cache producer. Original 41E10/981E0 producer/consumer behavior is now being investigated by the separate original-analysis owner. No original code/disassembly is in this snapshot.

## Concrete files
- shop_wndproc_input.hpp: existing lifetime/current checks, pre-point cancellation, derivation, effective 3WM and output.
- shop_wndproc_point_binding.hpp: current roles and DeriveBodyPoint. BODY_CACHE is set after CachedBody returns unsupported/unknown.
- shop_wndproc_body_cache.hpp: the entire conditional CachedBody chain.
- shop_wndproc_body_math.hpp and body_point.hpp: source F32/wrap math and one-candidate inverse/forward check.
- shop_normal_input_driver.py, shop_wndproc_input.py, shop_wndproc_protocol.hpp: caller and strict matched request/result protocol.
- shop_wndproc_sequence.hpp and shop_wndproc_body_binding.hpp: original message flow/cleanup and passive read binding.
- SOURCE_SNAPSHOT.json: exact authored source file hashes. Missing includes are intentional; this snapshot is not a standalone build or original source proof.

## Constraints and requested judgement
Keep original current/source/lifetime checks, original input priority/selection, once semantics, fault/cancel/UP and shared Quit authority. No forced Actor target, child/direct virtual/getter call, raw 0x4E43 sender, cache mutation/insertion, guard relaxation, synthetic default rect, new standalone observer/collector/hook, global input/focus, or actual game execution by the reviewer. A proposal must join an existing legitimate full producer/caller boundary with the real consumer and cleanup; source-only preparation is not an actual success.

1. Is continuing passive BODY-cache-derived point production as a prerequisite for normal SHOP input the right feature-level approach? Which assumption or architecture is likely causing repeated lack of an actual interaction?
2. Prioritize the smallest legitimate breakthrough: correcting a demonstrable adapter bug, joining the natural Actor/model/action/cache producer before passive consumption, using a justified existing complete normal-input caller, or narrowly classifying the first unsupported predicate inside the existing command result. Distinguish facts from hypotheses and state what evidence would choose among them.
3. Review the actual adapter files for concrete contradictions, ordering mistakes or a circular producer/consumer dependency. Do not label all unsupported predicates as defects merely because they are restrictive.
4. Specify one minimal next implementation and verification bundle that can advance normal input -> 0x4E43/menu -> purchase/adoption/client while preserving the boundaries. Do not demand whole-engine reconstruction, all-child leases or broad new instrumentation.

Use the GitHub connected app/plugin to read this repository at the exact branch/commit and target files provided in the chat. Do not try to open a private repository URL with general web browsing. Make the actual tool/source reads visible; if access is unavailable, report that limitation instead of claiming a source review. Answer in Korean.
