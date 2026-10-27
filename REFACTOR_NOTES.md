# 월드 기능 결합 해소 — 2026-10-27

## 기준과 결과 범위

- 저장소: `climsnkks-collab/singlelineage`
- 기준: `review/refactor-base-20261027`, `24ec7ec89922ebbeb2148426c5c452ebdf258a5a`
- 결과: `refactor/decoupling-20261027`. 기준 커밋에서 분기했으며 `main`에는 기록하지 않았다.
- 구현 범위: `tools/local_original_session/`, 이 문서, `WORLD_FEATURE_GUIDE.md`. `native/`, 클라이언트 관측 코드, 옛 broker 구현은 변경하지 않았다. `broker_tests.py`의 Realm fixture는 새 등록 경로에 맞게 연결했다.

필수 코어 6개와 선택 기능 12개를 나누고, 선택 기능의 연결을 등록 선언과 소유자 API로 옮겼다. 기본 이동·공격·획득은 코어에 남는다. 선택 기능을 모두 제외하면 대화 자료나 동료 런타임을 코어가 자동으로 준비하지 않는다. 구성 변경은 **프로세스 시작 전** `FEATURE_MODULES` 편집을 대상으로 한다. 실행 중 기능 해제 기능은 만들지 않았다.

게임 수치·패킷 생성 함수·JSON 스키마는 기존 구현을 사용한다. 새로운 요청 검증 `need()`·핀·해시·의존 검사나 요청 시 codec 준비를 추가하지 않았다. 등록 이름·감싸기 대상 검사는 시작 때 수행한다. 기존 요청 검증과 저장 경계의 의미는 유지했다.

**검증 수준:** 기존 순수 시험 179개 + 새 계약 시험 39개 = **218개 통과**. 실제 선언의 선택 기능 4,096개 조합이 레지스트리를 구성하는 것도 확인했다. 이 조합 검사는 callback body/import/initializer를 실행하지 않는다. 이 환경에서는 실제 서버 시작, 전체 회귀, 소켓, 봇, 원본 클라이언트 패킷 동등성을 검증하지 못했다. 아래의 제한과 감사 #16을 함께 읽어야 한다.

## 1. 최종 구조와 소유권

### 필수 코어

`world_handlers.CORE_MODULES`에 다음 여섯 모듈을 등록한다.

| 모듈 | 책임 |
|---|---|
| `world_core_session` | 선택·진입·요청 dispatch·기본 공격 `0x4e30`·송신·퇴장. Restart와 disconnect의 동일한 기능 정리 경로 |
| `world_core_kit` | 기존 starter kit, 인벤토리 CAS, 장비 자세, 선택적 kit 변환, 물약 기능 진입점의 기본 동작 |
| `world_core_reward` | progression 저장소, 진행도 저장, 바닥 아이템 획득 `0x4e3e` |
| `world_core_life` | 사망·리스폰·재선택·미지원 맵 귀환·다음 리스폰 목적지 |
| `world_core_maps` | 기존 이동과 맵 변경, 재배치, 기존 Gludin 지도 정책과 ship 진입 |
| `world_core_stats` | 기본 속성·장비 스탯, 소지 무게·최대 무게, 전투 프로필과 SelfInfo 투영 |

기존 `world_core_inventory`, `world_core_lifecycle`의 broker 수명 책임은 유지한다. `world_bridge`는 broker/Realm과 등록 메서드를 연결하며, `world_handlers`는 기존 요청·HostContext 경로를 제공한다. `WorldView`, `WorldCombat`, scheduler/entity/ground/persist는 기본 월드 실행 서비스다.

옛 `world_feature_session/kit/reward/life/maps/stats.py`는 같은 함수 객체를 내보내는 호환 import 파일이다. 선택 기능 목록에는 넣지 않는다. 코어를 다시 이 목록에 넣으면 중복 메서드 오류가 나며 조용히 덮어쓰지 않는다.

### 선택 기능

| `FEATURE_MODULES` 항목 | 소유하는 동작 / 항목을 제외했을 때의 경계 |
|---|---|
| `world_feature_pet` | 펫·훈련사·펫 UI. 활성화 시 공유 follower 서비스를 직접 설치하므로 companion 기능 없이도 연결 가능 |
| `world_feature_combat` | 탄약 준비·비용·화살·HP bar 실험. 제외해도 코어 기본 공격은 남음 |
| `world_feature_town` | NPC 메뉴·상점·여관·창고 UI·마을 서비스. 제외하면 마을 메뉴 없음; 일반 인벤토리 소유자는 남음 |
| `world_feature_items` | 강화·변신·물약·아이템 효과. 제외하면 다른 `0x0960` 소비자가 계속 기회를 받음. 기존 kit 물약은 수량 차감 전에 기존 `ITEM_USE_KIT_NO_EFFECT` 결과로 종료 |
| `world_feature_dungeons` | 확장 던전 데이터·지도 허용·계단·귀환/사망 목적지 |
| `world_feature_alignment` | kill lawful 변화와 사망 드롭 위험 계산·보고. lawful 값 자체의 저장/조회는 코어 소유 |
| `world_feature_companion` | 동료 캐릭터·성장·AI 설정·인벤토리 제공자. GIVE 등록은 이 기능에서 숨겨서 합치지 않음 |
| `world_feature_trade` | 독립 GIVE 요청 `0x4ef5` 경로. 등록된 제공자가 없으면 처리하지 않고 반환 |
| `world_feature_quest` | 퀘스트 상태·메뉴·아이템 정책·완료 거래. 마을의 메서드를 호출하지 않고 기여 훅으로 연결 |
| `world_feature_magic` | 플레이어 마법·상태·아이콘·마법 스탯. 제외해도 기본 장비/소지 무게 계산은 코어에 남음 |
| `world_feature_talkscroll` | 두루마리 카탈로그·kit 공급·대화/이동 소비. 마을 없이 필요한 codec은 자기 초기화에서 준비 |
| `world_feature_m5` | M5 데이터·마을 구성 기여·목적지 정책. 마을 기능의 private 필드를 수정하지 않음 |

기존 환경 변수에 따른 실험 활성화 조건은 유지한다. 기능 항목 제거와 환경 변수 비활성화는 서로 다른 구성이다. 예를 들어 companion 항목이 있으면 공유 follower 서비스를 설치하지만, `SL_COMPANION`이 꺼져 있으면 동료 캐릭터·저장소를 활성화하지 않는다.

### 공유 상태 API

| 상태 | 소유자와 API | 보존한 계약 |
|---|---|---|
| EXP·level·최대 HP/MP·lawful·미저장 진행도 | `world.progress: ProgressOwner`의 `snapshot`, `lawful_of`, `set_lawful`, `mark`, `adopt`, `pending`, `pending_items`, `ack`, `clear` | live lawful은 bound `PcState.status_fields[18]`. 별도 `_world_lawful` 사전 없음. 이전 snapshot의 ack가 새 변경을 지우지 않음. `adopt`는 현재 HP/MP를 회복시키거나 패킷을 보내지 않음 |
| 진행도 JSON | 기존 `ProgressStore`, `ctx.progress_store` | version/row 필드 그대로. 옛 행의 lawful 누락은 0, 새 캐릭터 기본은 500. `peek`는 이미 읽은 상태만 조회 |
| 인벤토리·장비·창고 공동 저장 | `ctx.inventory_transactions: InventoryTransactions` | `commit_inventory`, `restore_warehouse`, `commit_warehouse`가 기존 `WarehouseStore` 저널/직렬화 또는 기존 `replace_kit`을 호출. 창고 UI가 저장소를 소유하지 않음 |
| 월드 카탈로그 | `world.replace_data(data)` | world/combat/ground가 같은 새 카탈로그를 받고 `catalog_changed` 발행. 원래 참조를 유지하던 ground도 갱신 |
| HostBindings·아이템 정책·메뉴 | `ctx.add_item_policies`, `configure_town`, `prepare_dialogue`, 읽기용 `item_policies` | 시작 시만 준비. 기존 정책 우선권과 M5의 기존 정책 유지 경로 보존. `TownNpcs.data`는 별도 `TownData`이므로 M1Data로 덮지 않음 |
| follower actor/AI/보상 | 명시적인 `install_companion_runtime(world)` | companion 또는 활성 pet이 설치. 코어는 생성/직접 호출하지 않고 events를 호출. 기존 호환 메서드는 설치 시 중복 검사 후 연결 |
| follower 활성 roster | `WorldCompanions` | `active`는 읽기 전용 view. pet 보상 중 일시 제외는 `without_reward_member()` 소유자 scope가 원래 pop/복원 순서를 유지 |
| 동료 인벤토리 | `CompanionInventory` | 캐릭터·정책·저장·대상 해석·오류 보고를 명시적으로 전달. GIVE는 제공자 API를 사용 |
| 다음 리스폰 위치 | 코어 `_world_set_relocation(uid, destination)` | 지도·던전·M5가 목적지를 제안하며 각 기능이 공유 사전을 직접 기록하지 않음 |

`progress_dirty`는 옛 조회/시험을 위한 읽기 전용 view만 남았다. 선택 기능이 이를 기록하지 않는다. Quest의 공동 저장 뒤에는 `adopt(dirty=False)`와 `clear`를 사용한다. Companion/Pet 공동 JSON의 필드·receipt 형식은 유지하며, 전체 공유 records를 잠시 갈아끼우는 대신 저장할 records/receipts projection을 `CompanionStore.commit`에 전달한다.

## 2. 등록과 훅 계약

### 레지스트리 기본 규칙

`world_registry.build_registry(CORE_MODULES + FEATURE_MODULES)`가 immutable 테이블을 만든다. `METHODS`, `REALM_METHODS` 중복, 없는 훅/프레임 메서드, 없는 WRAPS/저장 경계 대상은 시작 오류다. `METHODS`는 override 수단이 아니다.

`WRAPS={'메서드명': wrapper}`의 서명은 `(ctx, base, *args, **kwargs)`다. `base`는 이전 구현에 같은 ctx가 연결된 callable이다. 현재 kit 물약 진입점은 이 명시적 감싸기를 사용한다. items가 없을 때 코어는 기존 no-effect receipt를 반환하고, 있으면 기존 `ItemEquipmentEffect._consume_potion`을 그대로 호출한다. 차감 뒤 기능 존재 여부를 검사하지 않는다.

`RuntimeExtensions.wrap(owner, target, name, wrapper)`는 기존 인스턴스 메서드를 명시적으로 합성한다. wrapper 인자는 이전 구현을 받아 새 callable을 만드는 함수다. 반환한 handle의 `close()`는 자기 wrapper만 제거하고 나머지를 다시 합성한다. magic/pet의 기존 동작 감싸기를 이 API로 옮겼다. 별도 기능이 지정한 메서드를 단순 복원하여 지우는 종료 순서 문제를 피한다.

Pet은 생성 시 `reserve(owner, target, name)`로 열 개의 adapter 자리를 등록·검사한다. 기존 첫 tick/진입의 `PetSystem.install`에서는 준비된 자리의 `install(wrapper)`만 호출한다. 그때의 실제 이전 구현을 잡으므로 뒤에 초기화되는 companion의 callback도 보존한다. 예약/적용은 각각 한 번이라는 계약이며 기존 pet 설치 수명이 이를 보장한다. 기존 저장소 읽기·복구·실제 적용 시점은 옮기지 않았고, 첫 요청에 새 중복 검사를 추가하지 않았다.

| Context 호출 | 반환/빈 등록 기본값 |
|---|---|
| `run_hooks`, `run_sync_hooks` | 이벤트 전체 호출, 반환 무시 / no-op |
| `chain_hooks`, `chain_sync_hooks` | 첫 참값에서 소비 종료 / `False` |
| `fold_hooks`, `fold_sync_hooks` | callback 첫 인자가 누적값 / 원래 값 |
| `collect_hooks`, `collect_sync_hooks` | callback 결과 tuple / `()` |
| `has_hooks` | 등록 유무 |

동기 호출에는 동기 callback만 등록한다. 비동기 호출은 awaitable을 기다린다. 아래 인자는 첫 `ctx` 다음이다.

### Context 훅 전체 목록

| 훅 | 인자 | 방식 / 책임 |
|---|---|---|
| `initialize` | 없음 | 동기 이벤트; core 준비 후 선택 기능 초기화 |
| `runtime_started` | 없음 | 동기 이벤트 |
| `runtime_stopped` | 없음 | async 이벤트; 자기 저장·타이머/감싸기 정리 |
| `before_enter` | writer, row, game, operation_lock | async 이벤트; bind 이전 |
| `after_enter` | writer, row, game, operation_lock | async 이벤트; 진입 송신 후 |
| `after_move` | writer, row, game, operation_lock | async 이벤트; 기존 잠금 안에서 호출하며 runtime dispatch에 재진입하지 않음 |
| `after_request` | writer, row, game, opcode, operation_lock | async 이벤트 |
| `after_kill` | KillEvent | 동기 이벤트 |
| `after_death` | uid | 동기 이벤트; 기존 life·지도·기능 순서 |
| `npc_hit` | npc_uid | 동기 이벤트; 선택 HP bar 알림 |
| `stats_changed` | uid | 동기 이벤트; 코어 재계산 |
| `before_leave` | writer, uid | async 이벤트; 진행도 저장 뒤, 선택 binding 제거 전 |
| `after_leave` | writer | async 이벤트; 코어 이탈 뒤. Restart/disconnect 양쪽 호출 |
| `pre_dispatch` | writer, row, game, frame, operation_lock | async 소비 체인; 두루마리 등 선행 처리 |
| `item_use` | host_context, payload, now | async 소비 체인; 강화/변신 이후 남은 요청은 다음 frame 소비자에게 전달 |
| `service_action` | host_context, interaction, menu, fields, now | 동기 소비 체인; 기존 메뉴 소유자의 pages 확인 뒤 quest→town |
| `warehouse_trade` | host_context, payload, now | 동기 소비 체인 |
| `warehouse_close` | host_context, payload, now | 동기 소비 체인 |
| `begin_click` | host_context | 동기 이벤트; 각 UI가 자기 선택 수명 정리 |
| `inventory_changed` | writer, row | 동기 이벤트; 창고 등 자기 UI 무효화 |
| `cure_poison` | uid | 동기 이벤트; 각 효과 소유자가 자기 poison만 제거 |
| `report` | world_result_dict | 동기 이벤트; 자기 보고 필드 기여 |
| `kit_frame` | frame, character_class | 동기 fold; 기존 kit 뒤 metadata/두루마리 공급 |
| `stats_modifiers` | (calculated, worn, info), position, level=… | 동기 fold; 기본 계산 뒤 마법 속성/AC |
| `item_weight` | current_weight, template_id | 동기 fold; 기본 카탈로그에 없는 행의 무게 |
| `weight_capacity` | capacity, calculated, position | 동기 fold; 최종 속성으로 무게 상태 계산 전 |
| `selected_exp` | exp, position | 동기 fold; 캐릭터 bind 전에 선택 동료 진행도 반영 |
| `item_destination_policy` | effect_result, position | 동기 fold; engine을 교체하지 않고 목적지/requirements 변환 |
| `map_transition` | destination_or_none, map_id, x, y | 동기 fold; 기본 계단 이후 추가 지도 정책 |
| `menu_sources` | town | 동기 collect; 각 결과는 source tuple |
| `item_policies` | 없음 | 동기 collect; 각 결과는 KitItemPolicy tuple |
| `town_setup` | TownSetup | 동기 fold; town/services/sources/shop experiment 기여 |
| `give_provider` | 없음 | 동기 collect; None 또는 대상 해석·이전·오류 보고 API. 현재 첫 non-None 사용 |
| `joint_progress_sources` | uid | 동기 collect; None 또는 (saved_owner_row, mtime_ns) |
| `joint_progress_adopt` | uid, saved_owner_row | 동기 이벤트; 각 저장소 소유자가 자기 owner projection 반영 |
| `relocate_keeps_self` | uid | 동기 참값 체인; 기존 같은 맵 교정 경로 선택 |
| `before_relocate` | uid, transit_dict | 동기 이벤트; 자기 기능 이름 키에 이동 상태 보관 |
| `after_relocate` | uid, transit_dict | 동기 collect; 각 결과는 추가 frame tuple |
| `prepare_attack` | pc_uid, target, now | 전용 동기 합성; 각 제공자가 허용해야 하며 arrow/cost를 보존 |

`prepare_attack`이 없으면 `WorldView.prepare_pc_attack=None`으로 기본 근접 경로를 사용한다. 정책 제공자는 비용을 소비하지 않고 앞에서 판단한다. 현재 탄약 비용 제공자는 하나이며 priority 100으로 마지막에 실행한다. 새 제공자를 추가할 때 비용 확정 뒤 거절하는 제공자를 두지 않는다. 이것은 등록 계약이며 요청에 새 검증을 넣지 않는다.

### Realm / WorldView / Combat 확장

`REALM_HOOKS`는 직접 callable을 받으며 다음 fold 계약을 사용한다. 월드 Context가 없는 일반 Realm에서는 기본값을 유지한다.

| Realm 훅 | 서명 | 위치 |
|---|---|---|
| `actor_fields` | realm, actor, position → actor | 기본 sprite/stance 뒤, 기존 ACTOR_F4 실험 앞 |
| `status_fields` | realm, fields, position, initial → fields | 저장 진행도/HP/MP/기본 속성 뒤, 최종 코어 stats 투영 앞 |
| `serves_map` | realm, served, map_id → bool | 기본 지도 허용에 선택 정책 합성 |

`world.events`는 명시적으로 설치된 runtime 서비스의 이벤트 버스다. `add(owner, event, callback, isolate=False, priority=20)`로 등록한다. 우선순위 정렬은 등록 때만 하며 같은 우선순위는 순서를 유지한다. town 가시성은 followers 앞, follower spawn/close는 town 앞으로 기존 순서를 명시했다.

| Runtime 이벤트 | 인자와 반환 |
|---|---|
| `catalog_changed` | data, 이벤트 |
| `ai_target` | uid, 참값 체인; NPC AI의 비PC 대상 조회, 기본 False |
| `tick` | now, 이벤트 |
| `close` | 없음, 이벤트 |
| `visible_entities` | pc_uid, map_id, x, y, known → entity iterable, collect |
| `spawn_frame` | entity → frame 또는 None, 첫 non-None; 없으면 기본 monster frame |
| `before_map_change`, `before_pc_leave`, `pc_death` | uid, 이벤트 |
| `npc_target_attack` | entity, monster, target_uid, now → bool, 소비 체인 |
| `pc_hit`, `pc_attack_started` | pc_ref, npc_ref, now, 이벤트 |
| `npc_died` | npc_uid, now, 이벤트 |
| `reward_plan` | pc_uid, corpse, monster, now → plan 또는 None; plan은 allocated/calculate()/commit() 제공 |
| `reward_committed` | pc_uid, receipt_or_none, 이벤트 |
| `combat.events.can_be_attacked` | uid → bool, 참값 체인; 기본 False |

보상 순서는 기존대로 owner 보상/loot RNG → follower 성장 RNG → owner 상태/프레임 → follower 상태/receipt → 공동 저장 → ground drop이다. `combat.profile_modifiers`는 `(uid, profile, now, **kwargs) -> profile`을 순차 합성하며 `ranged=`를 유지한다. 플레이어와 follower가 공유하는 순수 수식 이름은 `magic_damage`, `magic_heal`, `apply_heal`이다. 옛 수식 이름은 import 호환 alias로 남는다.

### 순서, 예외, 저장 경계

- Frame 기본 priority 20, pet 0, core session 10. 전체 구성의 item-use 순서는 pet → core dispatch(두루마리와 item_use 포함) → items → companion → magic이다. 첫 True가 소비한다.
- Hook 기본 priority 20, quest의 `service_action`은 0, 탄약 `prepare_attack`은 100이다.
- `NONCRITICAL_HOOKS`: combat의 `npc_hit/report`, alignment의 `report`, items의 `before_leave/report`, town의 `report`, pet의 UI 정리 `after_leave`. 해당 `Exception`을 feature/hook/method/error 종류로 최대 16개 남기고 다음 제공자를 실행한다.
- Runtime의 follower 이벤트 `tick`, `pc_hit`, `npc_died`, `pc_attack_started`는 `isolate=True`. 이벤트 버스는 오류를 로깅하고 최근 16개를 유지한다. `ai_target`, `npc_target_attack`, reward plan과 저장·소비·이동 확정은 기본 전파한다. `BaseException`과 취소를 무조건 삼키지 않는다. 기존 `_save_companion`의 오류 기록/정리 계속 정책은 원래 위치에서 유지했다.
- `SAVE_BOUNDARIES`는 core dispatch/leave, life의 사망/리스폰, maps의 relocation, items 강화, town 창고 거래, quest 완료, trade GIVE가 각각 선언한다. 강화 대상 판별은 기존 predicate 그대로다. 일반 물약 조회를 새 즉시 flush 경계로 만들지 않았다.
- 강화의 창고 preimage 읽기는 `commit_attempted=True` **전**, 실제 공동 commit은 **후**다. 퇴장 critical hook 실패는 원래 `WORLD_LEAVE_FAILED`와 progress error 기록 의미를 유지한다.

## 3. 단계별 커밋

| 단계 | 커밋 | 옮긴 내용 |
|---|---|---|
| 1 | `feddd3e` | 기존 여섯 구현을 core 파일로 이동하고 옛 import facade 유지. 이 단계의 본문은 기준 구현 그대로 |
| 2 | `6fb61b1` | 중복 거부 레지스트리, WRAPS, 이벤트/체인/fold/collect, RuntimeExtensions 추가. 아직 기존 소비자 경로를 전환하지 않음 |
| 3 | `97b0b10` | ProgressOwner·InventoryTransactions·CompanionInventory·공유 follower runtime 추출. 기존 JSON 구현 유지 |
| 4 | `f85ca4b` | bridge/handlers/core/선택 기능/WorldView/combat/NPC AI를 함께 새 연결로 전환. 중복 METHODS 제거, 소유자 API, 재배치/보상 이벤트, 안전한 물약 진입점 |
| 5 | `8ca2f1c` | 기존 시험 17개 파일과 봇 3개 파일의 구조 연결 수정, 새 계약 시험 2개 파일 추가 |
| 6 | `dd5fff5` | 기존 play-matrix 소스 기록이 옮겨진 `world_core_*` 본문도 기록하도록 경로 필터 수정 |
| 7 | `ac3d254` | pet adapter 등록 검사를 생성 시점으로 분리하고 기존 지연 적용 유지. Lane4 fresh-reload 호출을 저장소 소유자 API로 수정 |
| 8 | 이 문서 및 가이드 커밋 | 최종 구조·계약·감사 대응·검증 제한과 로컬 실행 순서 기록 |

4단계는 서로 의존하는 26개 파일의 일괄 연결 전환이다. 이를 최종 파일 단위로 더 쪼개면 중복 메서드가 남거나 새 WorldView에서 follower 초기화가 빠지는 중간 상태가 생기므로 함께 커밋했다. 앞 세 단계는 원래 경로를 유지한 채 이동/추출한다.

## 4. 감사 28항목 대응

번호는 기준 `work/local_original_session/game-core-prep/COUPLING_AUDIT.md`를 따른다. **해결은 해당 소스 결합을 제거했다는 뜻이며 실제 클라이언트 검증 통과를 뜻하지 않는다.** 27개 해결, 1개 부분, 보류 0개다.

| # | 판정 | 처리와 근거 |
|---|---|---|
| 1 | 해결 | wake/maps/stats/life 필수 binding의 구현을 `CORE_MODULES`로 승격 |
| 2 | 해결 | progress와 stance setup은 core initialize에서 등록된 core 메서드만 사용 |
| 3 | 해결 | bridge가 선택 feature 파일을 import/setup하지 않음. 선택 초기화는 HOOKS, Realm 기여는 REALM_HOOKS |
| 4 | 해결 | HostContext item_use 소비 체인. 추가로 legacy kit 물약의 차감 후 누락 메서드 호출도 core 기본값 + items WRAPS로 제거 |
| 5 | 해결 | service_action/warehouse_trade/warehouse_close/begin_click 훅. town=None이면 해당 메뉴 경로는 소비하지 않음 |
| 6 | 해결 | town→quest 직접 호출 제거. quest가 menu_sources/item_policies/service_action을 기여하고 우선순위로 기존 처리 순서 유지 |
| 7 | 해결 | 이동·transition 구현은 필수 core maps |
| 8 | 해결 | 기본 attack은 core session. 준비 훅 없으면 callback 미설치. 복수 결과에서 arrow/cost 보존, 비용 소유자는 마지막 |
| 9 | 해결 | after_kill 배선은 bridge가 설치. alignment는 자기 훅만 등록 |
| 10 | 해결 | 코어의 items/alignment private 상태 삭제 제거. before_leave/after_leave로 소유자 정리, Restart도 동일 경로 |
| 11 | 해결 | feature 보고는 report 훅. 전체 구성의 기존 보고 key 유지, combat attack_errors 추가 |
| 12 | 해결 | magic의 동명 stats override 제거. AC/DEX·capacity·미등록 아이템 weight를 훅으로 기여, 기본 무게는 core stats |
| 13 | 해결 | talkscroll의 kit/dispatch 동명 override 제거. kit_frame fold와 pre_dispatch chain |
| 14 | 해결 | magic_profile 단일 슬롯을 profile_modifiers로 교체. 실제 기준에 있던 추가 인스턴스 감싸기도 RuntimeExtensions로 명시 |
| 15 | 해결 | kit/maps/stats 호출 대상은 필수 core API. 타 기능 ailments 직접 접근은 cure_poison 이벤트로 변경 |
| 16 | 부분 | maps의 companion 직접 import 제거, companion/pet이 자기 relocation 상태를 보관·복원. 아래 펫 레코드 소유권 문제 때문에 실제 이동 호환성은 로컬 확인 필요 |
| 17 | 해결 | maps뿐 아니라 dungeons/M5의 효과 엔진 교체도 제거. item_destination_policy fold로 목적지만 기여 |
| 18 | 해결 | trade 독립 FEATURE_MODULES 등록. give_provider API와 추출한 CompanionInventory 사용. 실제 기준 opcode는 감사의 0x4f0d가 아니라 **0x4ef5** |
| 19 | 해결 | companion의 EXP/level/lawful/dirty 직접 갱신을 ProgressOwner.adopt로 이동. Realm status는 등록된 feature hook |
| 20 | 해결 | 창고 UI와 무관한 InventoryTransactions. 강화 결과 목록은 items가 초기화. preimage/commit 오류 경계도 보존 |
| 21 | 해결 | core kit이 enchant 실험 필드를 읽지 않음. items kit_frame 훅이 해당 metadata만 변경 |
| 22 | 해결 | session이 의존하는 stats/reward는 core. HostBindings도 core가 빈 상태로 소유하고 town이 선택적으로 구성 |
| 23 | 해결 | lawful 조회/기록/Progress snapshot을 ProgressOwner로 통합. live status, 저장된 row, fresh/default 정책을 별도 사전 없이 반영 |
| 24 | 해결 | dirty 사전 직접 쓰기 제거. mark/adopt/pending/identity ack/clear API로 변경 |
| 25 | 해결 | replace_data가 world/combat/ground를 함께 갱신. TownNpcs는 다른 TownData 소유자이므로 별도 configure_town/등록 인계 API로 처리 |
| 26 | 해결 | FRAME_PRIORITY/HOOK_PRIORITY와 명시적인 runtime event 순서. 비핵심 Exception 격리, critical 저장/소비 실패는 유지 |
| 27 | 해결 | 기능 이름·강화 template 하드코딩을 bridge에서 각 소유 모듈의 SAVE_BOUNDARIES로 이동 |
| 28 | 해결 | follower 생성/AI/보상 plan을 명시적으로 설치하는 runtime으로 추출. town은 attach_view 이벤트. 공유 magic 수식은 일반 이름 제공. 실제 기준 WorldView는 town=None만 두었으며 TownNpcs 생성은 이미 town setup에 있었음 |

### 감사 #16: 펫 재배치의 남은 위험

**소스에서 확인한 사실:** 기준 maps는 companion의 재배치 함수를 사용했고, 그 함수는 공유 active follower들을 선택했다. pet 제거 callback은 pet 레코드를 shared companion records에서 제거한다. 기존 companion 도착 함수는 그 records를 다시 인덱싱한다.

**추정:** 활성 pet이 이 경로를 타면 이미 제거된 레코드 접근으로 KeyError가 발생할 수 있다. 실제 기준 서버/클라이언트에서 재현하지 못했으므로 확인된 런타임 장애라고 표현하지 않는다.

새 pet 훅은 `PetSystem.records`라는 자기 소유 레코드와 기존 summon 경로로 복원하고 네 개의 cooldown 상태를 옮긴다. companion 훅은 자기 캐릭터만 처리한다. 기존에 성공하지 못했을 가능성이 있는 pet 경로까지 패킷 동등성을 주장할 수 없다. **살아 있는/죽은 pet, companion 동시 사용, 같은 맵 교정, 다른 맵 이동, 반복 귀환**을 원본 로컬 환경에서 확인해야 한다.

## 5. 검증 결과와 기존 시험 변경 범위

### 실행하여 통과

다음 12개 기존 suite의 합계 **179개**가 통과했다.

| suite | 수 |
|---|---:|
| `world_tests` | 6 |
| `world_persist_tests` | 14 |
| `world_stats_tests` | 13 |
| `world_weight_tests` | 14 |
| `world_ammo_tests` | 13 |
| `world_alignment_tests` | 15 |
| `world_companion_tests` | 15 |
| `world_pet_tests` | 27 |
| `world_polymorph_tests` | 12 |
| `world_enchant_tests` | 12 |
| `world_shop_tests` | 24 |
| `world_town_tests` | 14 |

새 `world_decoupling_tests` 19개, `world_decoupling_state_tests` 20개도 통과했다. 최종 통합 명령은 아래와 같으며 **Ran 218 tests / OK**였다. 같은 시험의 반복 실행은 합산하지 않았다.

```bash
python -m unittest tools.local_original_session.world_tests tools.local_original_session.world_persist_tests tools.local_original_session.world_stats_tests tools.local_original_session.world_weight_tests tools.local_original_session.world_ammo_tests tools.local_original_session.world_alignment_tests tools.local_original_session.world_companion_tests tools.local_original_session.world_pet_tests tools.local_original_session.world_polymorph_tests tools.local_original_session.world_enchant_tests tools.local_original_session.world_shop_tests tools.local_original_session.world_town_tests tools.local_original_session.world_decoupling_tests tools.local_original_session.world_decoupling_state_tests -q
```

새 시험은 중복 거부, WRAPS와 제거 순서, 시작 시 adapter 예약과 지연 적용, 빈 훅 기본값, sync/async 예외 정책, 화살 비용 보존, 4,096개 실제 선언 조합, 실제 물약 진입점 body의 빈/활성 wrapper 경로, lawful 보존, HP/MP 비회복, 옛 progression JSON, readonly pending/roster, 이전 snapshot ack, 기존 transaction 위임과 CompanionStore projection 직렬화를 확인한다. 실제 물약 시험도 전체 broker/codec을 실행한 것은 아니다.

변경한 Python 파일 61개를 원래 인코딩의 bytes로 문법 컴파일했다. 생산 코드에서 `world_feature_*`를 직접 import하는 경로가 없음을 AST로 확인했다. 이는 동적 초기화와 플레이 동등성의 증명은 아니다.

### 기존 시험·봇 수정의 한계까지 명시

기존 시험 17개 파일과 봇 `hunt_bot_magic.py`, `hunt_bot_m5.py`, `hunt_bot_talkscroll.py`의 import/호출/소유자 fixture 연결을 수정했다. 네 번째 봇 `hunt_bot_play_matrix.py`는 기존 소스 기록 필터에 이동된 core 경로를 포함했다. 새 요청 검증이나 해시 비교를 추가한 것은 아니다. 기대하는 수치·패킷 상수·비교 조건은 바꾸지 않았다. Assertion call AST 비교는 talkscroll의 두 equality를 제외하고 동일하다. 그 두 곳은 삭제된 feature kit override 대신 실제 core kit + 등록 훅을 호출하는 operand 경로만 바꿨다.

Quest fixture에는 원래 저장 Progress와 `_world_lawful`의 **500**, live status field18의 **0**이 동시에 있었다. 실제 새 소유자를 설치하면서 기존 authoritative 값 500을 `adopt(dirty=False)`로 초기화했다. assertion 값/조건은 그대로지만 동적으로 캡처하는 초기 status는 이제 500으로 일치한다. 서로 모순된 두 ledger를 유지하는 test-only 가짜 owner는 만들지 않았다. 이 integration fixture는 아래 누락 의존성으로 끝까지 실행하지 못했다.

### 실행을 시도했으나 완료하지 못한 suite

| suite | 관측된 중단 원인 |
|---|---|
| `world_reward_tests`, `world_ground_items_tests`, `world_item_effects_tests`, `world_handler_adapter_tests`, `world_magic_tests`, `world_quest_store_tests`, `world_warehouse_tests` | import/setup에서 `work/local_movement_contract/contract.json` 없음 |
| `world_handlers_tests`, `world_status_frames_tests` | `tools.local_world_protocol` 없음 |
| `world_writebehind_tests` | `tools/local_character_wire_v2/wire.py` 없음 |
| `world_quest_tests` | 순수 17개 통과, 나머지 14개 setup/import 오류. 위 movement contract 또는 character wire 부재 |

Quest의 부분 통과 17개는 완주한 218개 합계와 분리했다. 이 오류들을 PASS나 skip으로 바꾸지 않았다. 실제 `feature_registry()` import도 character wire 부재로 막혔다.

기준 Git tree에 character wire, local_world_protocol, movement contract, 기존 dialogue-contract 자료, `work/source_game_data/native-dump-v1.jsonl`이 없다. 별도로 **저장소에 있는** `data/catalog/items_all.json`은 약 12.35MB이며 연결 앱의 blob 전달이 종료되어 이 환경으로 가져오지 못했다. 이 파일을 대체하거나 원격에서 수정하지 않았다. 누락 codec/관측 자료를 추측해서 만들거나 production import를 stub으로 통과시키지 않았다.

전체 `*_tests.py` 회귀, 실제 서버의 기능별 제외 초기화, 모든 hunt bot, 실제 포트/클라이언트 동작은 **실행하지 못했다**. 기준 커밋 메시지의 과거 회귀/플레이 성공 수치를 이번 결과로 재사용하지 않았다.

## 6. 로컬에서 우선 실행할 검증

원본 codec/관측 자료가 갖춰진 기존 로컬 작업 환경에서 실행한다. 실제 포트를 여는 시험과 봇은 한 번에 하나씩 실행한다.

1. 위 통합 시험 명령과 전체 회귀: `python -X utf8 -B -m unittest discover -s tools/local_original_session -p "*_tests.py"`. `world_integration_tests.RegisteredMovementLoopbackTests` 등은 기본 discovery에서도 실제 포트를 연다. Companion/Pet의 opt-in 소켓 클래스는 별도로 활성화해야 한다.
2. 실제 서버 구성: 기본 전체 구성, `FEATURE_MODULES=()`, 12개 항목을 하나씩 뺀 구성을 **각각 새 프로세스**로 시작한다. 로그인/선택/이동/기본 공격/획득/저장/Restart/재선택/종료를 확인한다. 특히 items 제외 물약 무차감, combat 제외 근접 공격, town 제외 talkscroll와 pet, companion 제외 pet, trade 제외 companion, magic 제외 무게를 확인한다.
3. 저장과 실패 경계: `world_writebehind_tests`, `world_quest_store_tests`, `world_quest_tests`, `world_warehouse_tests`, `world_enchant_inventory_tests`, `world_handler_adapter_tests`, `world_m1_reward_tests`, `world_review_fix_tests`. lawful이 500이 아닌 저장/재접속, 옛 lawful 누락 JSON, 강화·창고 preimage 오류, 저장 도중 실패, 재선택과 종료를 우선 확인한다.
4. relocation과 follower: `world_companion_integration_tests`, `world_companion_movement_tests`, `world_companion_equipment_tests`, `world_companion_magic_tests`, `world_companion_revive_tests`, `world_pet_integration_tests`, `world_dungeon_maps_tests`, `world_effect_map_contract_tests`, `world_visibility_regression_tests`. 감사 #16의 조합과 타이머/중복 actor/저장 receipt를 확인한다.
5. 메뉴·마법·세계 데이터: `world_handlers_tests`, `world_town_services_tests`, `world_talkscroll_tests`, `world_magic_tests`, `world_m4_tests`, `world_m5_tests`, `broker_tests`의 첫 SelfInfo/동료 선택 fixture.

`world_lane4_connection_tests.py`는 unittest suite가 아닌 실행 스크립트다. Discovery만으로는 실행되지 않으므로 강화·창고의 실제 연결 시험을 따로 실행한다. `--output`에는 아직 존재하지 않는 새 fixture 디렉터리를 지정한다.

```bash
python -X utf8 -B -m tools.local_original_session.world_lane4_connection_tests --output <새_fixture_디렉터리> --case all
```

### 필수 봇 목록

| 봇 | 우선 확인할 동작 |
|---|---|
| `hunt_bot_play_matrix.py --scenario all` | 기존 15 시나리오의 전체 회귀와 종료/재접속 |
| `hunt_bot_scenarios.py --scenario all` | death, reconnect, town, items |
| `hunt_bot_loopback.py --minutes 3` | 기본 사냥·획득·물약·정상 종료 |
| `hunt_bot_magic.py --scenario all` | 원래 두 profile의 마법·스탯·무게·MP·packet·저장 |
| `hunt_bot_talkscroll.py` | 공급 kit, native 메뉴, 같은/다른 맵 이동, 재선택 |
| `hunt_bot_m5.py` | M5 구성, 상점·창고, 귀환과 목적지 정책 |
| `hunt_bot_dungeons.py --family all` | 던전별 진입·사냥·귀환·사망 목적지 |
| `hunt_bot_companion.py --scenario all` | 공동 EXP/RNG/receipt, GIVE, 장비, 마법, 재배치 |
| `hunt_bot_pet.py` 및 `--with-companion` | pet 단독/동시 사용, 성장·재접속·저장·재배치 |

위 파일은 `python -X utf8 -B -m tools.local_original_session.<모듈명>`으로 실행할 수 있다. pet 봇의 기존 요구값은 `SL_TEST_PORT_BASE=16000`이며 16000/18030을 쓴다. 소켓 integration은 각각 `SL_RUN_COMPANION_INTEGRATION=1`, `SL_RUN_PET_INTEGRATION=1`을 사용한다. 다른 봇은 기존 테스트 포트 설정을 따른다. 실제 원본 클라이언트에서는 actor 생성/제거, SelfInfo optional 필드, 아이콘, 마을 메뉴, 순간이동의 프레임 순서를 별도로 비교해야 한다.

새 훅의 우선순위, optional runtime wrapper 제거, 공동 저장 오류 경계, pet 재배치가 주요 잔여 위험이다. 순수 시험 통과나 선언 조합 통과를 이 동작들의 실제 게임 PASS로 확대 해석하지 않는다.
