# 월드 기능 간 결합 감사 (2026-10-27, 읽기 전용)

사용자 결정(10-27): 결합 해소는 **리팩터링 때 한 번에** 한다. 그 전까지 새 기능은 다른 기능 모듈을 직접 호출하지 않고, 코어에는 "있으면 쓰고 없으면 기본 동작" 연결로만 붙인다.
줄 번호는 감사 시점(사냥터 확장·마법 16종·말하는 두루마리·꺼짐 안전망 적용 직후) 기준이다. 경로는 `tools/local_original_session/`.

## 구조 전제 (확실)
- 이름이 겹치면 뒤 모듈이 조용히 덮어씀: `world_handlers.py:879-880` `methods[function.__name__] = function`. 가이드(WORLD_FEATURE_GUIDE.md:15) 금지 위반이 이미 2건(#12, #13).
- FEATURE_MODULES에서 빼도 setup은 돎: `world_bridge.initialize`(346-377)가 items·town·alignment·combat·kit·reward의 `setup_*`를 직접 import·호출 → 상태는 있고 메서드는 없는 반쯤 빠진 상태.
- 세션 루프 안전망은 `ValueError`만 살림(broker.py:2157-2161). 기능 누락의 AttributeError/KeyError는 `_fail`로 브로커 전체 실패.

## A. 빼면 서버 시작 실패
1. bridge 초기화의 필수 바인딩 `world_bridge.py:363-372`: `_world_wake`(session), `_world_edge_fallback`(maps), `_world_fields_for`(stats), `_world_commit_respawn`·`_world_unserved_return`(life). → 넷은 코어로 올리거나 getattr+기본 동작.
2. setup이 다른 모듈 METHODS 필수 참조: `world_feature_reward.py:122` `_world_progress_for`, `world_feature_kit.py:128` `_world_stance_for`.
3. bridge가 기능 파일 직접 import: `world_bridge.py:346-377, 519-551, 591-613` (items, town, alignment, combat, kit, reward, stats, maps, life). → setup은 initialize 훅, realm 위임은 레지스트리(REALM_HOOKS).

## B. 런타임에 다른 기능 전체 마비
4. items 빼면 모든 0x0960 실패: `world_handlers.py:774-778` `_world_enchant_use`·`_world_polymorph_use` 직접 호출(session `_world_dispatch`가 먼저 받음). → item_use 훅 체인.
5. town 빼면 상점·NPC 메뉴 실패: `world_handlers.py:771` `_world_service_action`, 781 `_world_warehouse_trade`; `handle_trade`(266-268)가 모든 TRADE에서 warehouse를 먼저 부름.
6. town→quest 무조건 의존: `world_feature_town.py:15` `_world_quest_action`; `setup_town`이 `setup_quests` 호출(249)·quest 아이템 정책 병합(284-289). → service_action 체인, menu_sources 훅.
7. 이동이 maps에 묶임: `world_handlers.py:828-834` `_world_move_for_handler`·`_world_transition_for_handler`.
8. combat 빼면 PC 공격 전부 거부: `world_bridge.py:360` prepare_pc_attack 람다 항상 설치 → 훅 0개면 None 반환 → `world_visibility.py:784-787` 거부. `run_sync_hooks`는 마지막 결과만(`world_handlers.py:900-904`) → 둘째 등록자가 화살 소비 결과 덮어씀. → 훅 0개면 None 설치, 결과 합치기.
9. after_kill 배선이 alignment 안: `world_feature_alignment.py:36`. → bridge initialize로.
10. 퇴장 처리가 items·alignment 상태 직접 삭제: `world_feature_session.py:131-137` (`_world_ailments`, `_world_poly_timers`, `_world_polymorphs`, `_world_lawful`). setup을 훅으로 옮기거나 기능을 빼면 퇴장마다 `WORLD_PERSIST_FAILED`(bridge 441-444). (추정: 잠재적 시한폭탄) → 각 기능 after_leave 훅, Restart(session 69-74)도 같은 훅.
11. 종료 보고가 기능 필드 하드코딩: `world_bridge.py:574-583`. → report 훅.

## C. 기능→기능 직접 의존
12. magic이 stats `_world_stats_for`를 같은 이름으로 덮어씀: `world_feature_magic.py:168-197`, METHODS 619; 소지 무게 계산이 magic 안에만 → magic 빼면 무게 페널티 소멸(추정). 사용처 town 창고(`town.py:138-141`), magic 430. → stats_modifiers 훅, carried 계산은 코어로.
13. talkscroll이 `_inventory_kit_frame`·`_world_dispatch`를 같은 이름으로 덮어씀: `world_feature_talkscroll.py:185`, base 직접 import(47, 68). → kit_frame_extensions·pre_dispatch 훅, 레지스트리 이름 중복은 에러.
14. magic이 combat에 단일 슬롯 주입: `world_feature_magic.py:103` `combat.magic_profile`; 코어 기본값 있음(`world_combat.py:376`) 그러나 슬롯 하나·`ranged=` 계약(523). → `combat.profile_modifiers: list`.
15. magic의 필수 호출: `_world_replace_kit`(110, 120, kit), `_world_relocate_locked`(512, maps), `_world_recalculate_uid`(141, 333, 381, 519, stats); `_world_ailments`(490)만 getattr.
16. maps 순간이동이 companion 직접 import: `world_feature_maps.py:183-185`. → before/after_relocate 훅.
17. maps가 items 효과 엔진 교체: `world_feature_maps.py:40` `GludinItemEffects(...)`, setup 순서 의존. → item_destination_policy 훅.
18. trade 숨은 등록: `world_feature_companion.py:834-837` `METHODS += _trade.METHODS`; companion 빼면 GIVE(0x4f0d) 소멸; trade가 companion private 사용(trade.py:271 `_companion_owned_actor`, 101 `_companion_rows`).
19. companion이 진행도 공유 상태 직접 기록: `world_feature_companion.py:478-489` (`world.exp`, level, `_world_lawful`, `progress_dirty`); `realm_status`도 companion record로 2·10-13 필드 덮음(getattr 있음).
20. 강화·kit CAS가 창고 저장소에 묶임: `world_feature_items.py:70, 75` warehouse store, 78 창고 UI 상태 삭제; `world_feature_kit.py:72-87`; 저장소 생성은 `world_bridge.py:329-332`; 강화 결과 리스트를 town `setup_warehouse`가 초기화.
21. kit이 items 상태를 기본값 없이 읽음: `world_feature_kit.py:27` `_world_enchant_exp`.
22. session이 stats·reward 필수 호출: `world_feature_session.py:81-89`; `world_handlers.py:594` `_world_pc_profile`, 693 `_world_handler_bindings`(town).

## D. 공유 전역 상태
23. lawful 진짜 값이 두 군데: `Progress.lawful` 기본 500(world_progress.py:43); 코어 `world_visibility.py:732`·life `world_feature_life.py:36`은 lawful 없이 Progress 생성; 저장 시 getattr 보정(reward.py:21, bridge.py:181) → alignment 없으면 저장마다 500으로 덮임. 쓰기: alignment 17, session 81, companion 483 / 읽기: life 15, magic 445, quest 121·214, stats 39, bridge 181. → alignment가 `lawful_of(uid)` 소유, Progress 생성 한 곳.
24. `world.progress_dirty` 다중 기록(순서 의존 추정): 코어 732, alignment 19, life 36, companion 487, quest pop.
25. talkscroll이 공유 카탈로그 통째 교체: `world_feature_talkscroll.py:40-42` (`world.data`, `combat.data`, `_world_handler_bindings`); 옛 data를 잡은 GroundItems(world_visibility.py:216 → ground_items.py:108/179)·TownNpcs는 갱신 안 됨.
26. 프레임·훅 순서 결합, 예외 격리 없음: 0x0960은 session(+talkscroll)→items→companion→magic 첫 True(bridge.py:428-430); `run_hooks`(world_handlers.py:893-897) 한 훅 예외가 뒤 훅 건너뜀.
27. 코어 저장 경계가 기능 이름 하드코딩: `world_bridge.py:134-155` (`_world_enchant_use`, 템플릿 25/26, `_world_quest_action`, `_world_warehouse_trade`, `_companion_give_frame`). → 기능별 SAVE_BOUNDARIES 선언.
28. 코어 WorldView가 동료·마을 직접 생성: `world_visibility.py:56-58, 187, 196-209`; 동료 EXP 분배가 코어 `_reward`(697-749); 플레이어 마법이 `world_combat.companion_magic_damage/heal` 사용. None 가드로 안전하나 코어에서 분리 불가.

## 기능 하나를 뺄 때
| 뺀 기능 | 결과 |
|---|---|
| session, kit, stats, reward, life, maps | 서버 시작 실패 (#1, #2) |
| items | 모든 0x0960 세션 실패 (#4) |
| town | 상점·창고·NPC 메뉴 실패 (#5) |
| quest | 마을 서비스 메뉴 전부 실패 (#6) |
| combat | PC 공격 전부 거부 (#8) |
| companion | GIVE 함께 소멸 (#18) |
| magic | 무게 페널티 소멸 추정 (#12) |
| alignment, talkscroll | 안전 |

## 리팩터링 때 바꿀 지점
1. 코어/기능 분리: session·kit·stats·reward·life·maps를 `world_core_*`로 올리고 FEATURE_MODULES에서 제외, 또는 `REQUIRES=()` 선언 + 시작 시 의존 그래프 검사.
2. 레지스트리 엄격화: METHODS 이름 중복은 에러, 감싸기는 `WRAPS={'name': fn(base, ...)}` (대상: magic `_world_stats_for`, talkscroll `_inventory_kit_frame`/`_world_dispatch`).
3. bridge.initialize 정리: `setup_*` 직접 호출(346-377) → 순서 있는 initialize 훅; 필수 바인딩(360-372) → getattr+기본 동작; after_kill 배선 → bridge.
4. 새 훅: 합치기형 `prepare_attack`(모두 allow)·`combat_profile_modifiers`·`stats_modifiers` / 체인형 `item_use`·`service_action`·`pre_dispatch` / 이벤트형 `before/after_relocate`·`report`·`save_boundaries`.
5. 퇴장 정리를 기능별 after_leave 훅으로, Restart 경로도 같은 훅.
6. 공유 상태 소유자 지정: `_world_lawful`·Progress 생성, 창고 저장소, `world.data` 교체 — 한 기능이 소유하고 API로만.
7. 비핵심 훅 예외 격리(기록 후 계속), `run_sync_hooks`는 마지막 값 대신 합치기.
