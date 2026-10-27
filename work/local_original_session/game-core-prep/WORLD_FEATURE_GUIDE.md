# 월드 코어와 선택 기능 등록

## 필수 코어

`world_handlers.CORE_MODULES`는 서버가 플레이어의 월드 수명을 유지하는 기본 서비스다.
`world_core_session`(진입·이동 dispatch·기본 근접 공격·송신·퇴장), `world_core_kit`(인벤토리 CAS·장비 자세), `world_core_reward`(진행도 저장·획득), `world_core_life`(죽음·리스폰), `world_core_maps`(이동·재배치), `world_core_stats`(스탯·무게·상태 프레임)를 항상 등록한다.

옛 `world_feature_session/kit/reward/life/maps/stats.py`는 기존 import를 위한 호환 파일이다. 선택 기능 목록에 다시 추가하지 않는다. 기존 `world_core_inventory`와 `world_core_lifecycle`은 broker의 인벤토리/종료 수명을 계속 소유한다.

## 선택 기능

새 `tools/local_original_session/world_feature_이름.py`를 만들고 `world_handlers.FEATURE_MODULES`에 한 줄을 추가한다. 목록에서 제거하면 해당 기능의 초기화·요청·훅이 함께 사라진다. 다른 선택 기능의 메서드 또는 private 상태를 직접 참조하지 않는다.

```python
async def _example_after_enter(ctx, writer, row, game, operation_lock):
    position = ctx.realm.service(writer).snapshot()
    # 기본 코어 API 또는 등록된 훅을 이용한다.

METHODS = (_example_after_enter,)
HOOKS = {'after_enter': ('_example_after_enter',)}
```

`METHODS`와 `REALM_METHODS` 이름 중복은 시작 시 오류다. 등록 순서로 덮어쓰지 않는다. 함수 감싸기가 필요한 경우만 `WRAPS = {'기존_메서드': wrapper}`를 사용한다. wrapper 서명은 `(ctx, base, *args, **kwargs)`이고 `base`는 이미 같은 ctx에 연결된 이전 구현이다. 비동기 메서드는 비동기 wrapper로 감싼다. 가능하면 아래의 명시적 훅을 사용한다.

현재 kit 물약의 코어 진입점은 기본적으로 기존 no-effect receipt를 반환한다. items의 명시적 WRAPS가 있을 때 기존 물약 소비 구현을 호출하므로, items를 제외한 경우 수량 차감 뒤 없는 기능 메서드를 호출하지 않는다.

`FRAMES={opcode: ('함수명',)}`의 함수 서명은 `(ctx, writer, row, game, frame, operation_lock) -> bool`이다. `True`는 처리 완료, `False`는 다음 처리기로 넘긴다. 소비·저장한 요청은 `False`로 넘기지 않는다. 프레임 순서는 `FRAME_PRIORITY`가 낮은 쪽부터이며 기본 20이다. 기존 pet 입력은 0, 코어 session dispatch는 10이다. 같은 우선순위는 등록 순서를 유지한다. core/feature 분류가 기존 pet → session → 일반 기능 순서를 바꾸지 않는다.

## 훅 호출 방식

다음 메서드는 `world_bridge.Context`에서 제공한다. 이름 조회와 등록 검사는 시작 시 완료하며 요청에서 소스 탐색·해시·핀·의존 검사를 하지 않는다.

| 호출 | 계약 / 등록자가 없을 때 |
|---|---|
| `run_hooks(name, *args)` / `run_sync_hooks` | 모든 이벤트 구독자 호출, 반환값 사용 안 함 / 아무 동작 없음 |
| `chain_hooks(name, *args)` / `chain_sync_hooks` | 첫 참값에서 중단 / `False` |
| `fold_hooks(name, value, *args)` / `fold_sync_hooks` | 함수에 현재 누적 `value`를 첫 인자로 전달하고 반환값을 다음 함수에 전달 / 원래 `value` |
| `collect_hooks(name, *args)` / `collect_sync_hooks` | 반환값들을 순서대로 tuple에 수집 / 빈 tuple |
| `has_hooks(name)` | 등록자가 있는지 확인 |

비동기 함수는 async 호출 방식에서만 사용한다. `HOOK_PRIORITY={'service_action': 0}`처럼 특정 훅의 순서를 명시할 수 있다. 기본값은 20이며 같은 우선순위는 등록 순서다. 퀘스트의 메뉴 소비는 일반 마을 서비스보다 먼저 실행한다.

### 수명과 요청 계약

표의 인자는 첫 `ctx` 뒤 인자다.

| 훅 | 인자 / 방식 |
|---|---|
| `initialize`, `runtime_started` | 없음 / 동기 이벤트 |
| `runtime_stopped` | 없음 / 동기·async 이벤트 |
| `before_enter`, `after_enter`, `after_move` | `writer, row, game, operation_lock` / 동기·async 이벤트 |
| `after_request` | `writer, row, game, opcode, operation_lock` / 동기·async 이벤트 |
| `after_kill`, `after_death`, `npc_hit`, `stats_changed` | 각각 `event`, `uid`, `uid`, `uid` / 월드 잠금 안의 동기 이벤트 |
| `before_leave` | `writer, uid` / 기존 선택 binding이 남아 있는 상태의 동기·async 이벤트 |
| `after_leave` | `writer` / 코어 이탈 뒤의 동기·async 이벤트; restart와 disconnect 모두 동일 경로 |
| `pre_dispatch` | `writer, row, game, frame, operation_lock` / 소비 체인 |
| `item_use` | `host_context, payload, now` / 소비 체인 |
| `service_action` | `host_context, interaction, menu, fields, now` / 동기 소비 체인 |
| `warehouse_trade`, `warehouse_close` | `host_context, payload, now` / 동기 소비 체인 |
| `begin_click` | `host_context` / 동기 이벤트 |
| `inventory_changed` | `writer, row` / 동기 이벤트; 각 기능의 UI 선택 무효화 |
| `cure_poison` | `uid` / 동기 이벤트; 각 효과 소유자가 자기 상태만 정리 |
| `inventory_changed` | `writer, row` / 동기 이벤트; 기능 소유의 현재 목록을 무효화 |
| `cure_poison` | `uid` / 동기 이벤트; 각 기능이 자기 독 상태만 제거 |
| `report` | `world_result_dict` / 동기 이벤트; 자기 기능의 보고 필드만 기여 |

`before_leave`는 코어가 진행도를 저장한 뒤, 선택 binding을 제거하기 전에 호출한다. 각 기능은 자기 타이머·상태를 여기 또는 자기 `after_leave`에서 정리한다. 코어가 특정 기능의 상태를 지우지 않는다.

### 값 변환과 기여 계약

| 훅 | 인자 / 방식 |
|---|---|
| `kit_frame` | `frame, character_class` / 동기 fold |
| `stats_modifiers` | `(calculated, worn, info), position, level=...` / 동기 fold; 기본 장비 계산 뒤 |
| `item_weight` | `current_weight, template_id` / 동기 fold; 코어 카탈로그에 없는 행의 무게 기여 |
| `weight_capacity` | `capacity, calculated, position` / 동기 fold; 최종 스탯 뒤 무게 계산 전 |
| `selected_exp` | `exp, position` / 동기 fold; 선택한 캐릭터를 bind하기 전 |
| `item_destination_policy` | `result, position` / 동기 fold; 효과 엔진을 교체하지 않고 목적지 제안만 변환 |
| `map_transition` | `destination_or_none, map_id, x, y` / 동기 fold |
| `menu_sources` | `town` / 동기 collect; 각 반환값은 메뉴 sources의 tuple |
| `item_policies` | 없음 / 동기 collect; 각 반환값은 KitItemPolicy tuple |
| `town_setup` | `TownSetup` / 동기 fold; town/services/sources/shop experiment 구성 기여 |
| `give_provider` | 없음 / 동기 collect; None 또는 대상 해석·이전·오류 보고 API |
| `joint_progress_sources` | `uid` / 동기 collect; None 또는 `(saved_owner_row, mtime_ns)` |
| `joint_progress_adopt` | `uid, saved_owner_row` / 동기 이벤트; 각 소유자가 자기 저장소 projection 반영 |
| `item_policies` | 없음 / 동기 collect; 각 반환값은 추가 item policy tuple |
| `town_setup` | `TownSetup(town, services, sources, shop_experiment)` / 초기화 중 동기 fold |
| `give_provider` | 없음 / 동기 collect; 사용 가능한 소유 인벤토리 adapter 또는 `None` |
| `joint_progress_sources` | `uid` / 동기 collect; 기능 저장의 `(owner_row, mtime_ns)` 또는 `None` |
| `joint_progress_adopt` | `uid, saved` / 동기 이벤트; 공동 저장에서 복구한 진행도를 해당 기능 저장에 반영 |
| `relocate_keeps_self` | `uid` / 동기 참값 체인 |
| `before_relocate` | `uid, transit_dict` / 동기 이벤트; 자기 기능 이름의 키에 이동 상태를 기록 |
| `after_relocate` | `uid, transit_dict` / 동기 collect; 각 반환값은 추가 프레임 tuple |
| `prepare_attack` | `pc_uid, target, now` / 전용 합성; 모든 제공자가 허용해야 하며 화살·비용 결과를 보존 |

`prepare_attack` 등록자가 없으면 WorldView에 callback을 설치하지 않아 기본 근접 판정을 유지한다. 화살 비용을 확정하는 제공자는 하나이며 `prepare_attack` 우선순위 100으로 마지막에 둔다. 추가 정책 제공자는 기본 우선순위 20 등 더 낮은 값으로 먼저 허용 여부를 판단하고 비용을 소비하지 않는다. 따라서 앞 정책의 거절 뒤에 화살을 소비하지 않으며, 비용 확정 뒤의 거절 제공자를 등록하지 않는다. 기본 공격 opcode 처리는 코어 session이 유지한다.

### Realm 변환

`REALM_HOOKS={'actor_fields': (fn,), 'status_fields': (fn,), 'serves_map': (fn,)}`는 직접 callable을 등록한다. 서명은 각각 `(realm, actor, position)`, `(realm, fields, position, initial)`, `(realm, served, map_id)`이며 새 값을 반환한다. 필요한 기능 Context는 `realm._world_context`다.

actor 변환은 기본 sprite/stance 뒤와 기존 ACTOR_F4 실험 앞에 있다. status 변환은 기존 선택 진행도·현재 HP/MP·기본 속성 뒤, 최종 코어 스탯 투영 앞에 있다. 이 순서를 바꾸면 동료 상태와 장비 스탯이 서로 덮어쓰므로 유지한다.

### 명시적 runtime 서비스

`WorldView`는 선택 기능을 자동 생성하지 않는다. companion 또는 활성 pet이 `install_companion_runtime()`으로 공유 follower 서비스를 설치하고, town은 `attach_view()`로 연결한다. `world.events.add(owner, event, callback, isolate=False, priority=20)`는 시작 때 callback 순서를 정한다. 같은 우선순위는 등록 순서를 유지한다. town 가시성은 followers 앞, follower spawn/close는 town 앞이다.

magic/pet의 기존 인스턴스 감싸기는 `world.runtime_extensions.wrap(owner, target, name, wrapper)`를 사용하고 반환한 handle로 자기 감싸기만 해제한다. wrapper는 이전 구현을 받아 새 callable을 만드는 함수다. 코어에서 특정 기능 메서드를 직접 찾아 호출하지 않는다. 전체 runtime 이벤트 목록과 각 서명은 브랜치 루트 `REFACTOR_NOTES.md`에 있다.

Pet처럼 실제 적용을 지연해야 하면 초기화에서 `reserve(owner, target, name)`로 한 번 등록하고, 준비된 자리의 `install(wrapper)`를 기존 적용 시점에 한 번 호출한다. 이전 구현은 적용할 때 캡처한다. 따라서 pet의 기존 저장/복구 순서를 유지하면서 첫 진입 요청에 새 중복 검사를 넣지 않는다.

## 공유 상태 소유자

- `ctx.world.progress`: 진행도와 lawful의 단일 API. `snapshot`, `lawful_of`, `set_lawful`, `mark`, `adopt`, `pending`, `pending_items`, `ack`를 사용한다. 선택 기능이 별도 lawful 사전이나 `progress_dirty`를 기록하지 않는다. 기존 progression JSON 형식은 바꾸지 않는다.
- `ctx.inventory_transactions`: 인벤토리·장비·창고의 기존 공동 저장을 제공한다. `commit_inventory`, `restore_warehouse`, `commit_warehouse`를 사용한다. 창고 UI를 제외해도 일반 인벤토리 저장에 같은 소유자가 남는다.
- `ctx.world.replace_data(data)`: world/combat/ground 카탈로그를 함께 갱신하고 카탈로그 구독자에게 알린다.
- `ctx.item_policies`, `ctx.add_item_policies(policies, replace_existing=False)`, `ctx.configure_town(town, sources, refresh_policies=True)`: HostBindings 소유자의 시작 시 API. 기능이 `_world_handler_bindings` 전체를 직접 교체하지 않는다. 코어는 비어 있는 bindings로 시작하며, 마을 구성 때 기존 메뉴 codec과 정책을 준비한다. 마을 없이 대화 프레임을 쓰는 기능은 초기화에서 `ctx.prepare_dialogue()`를 호출한다. 요청 시점에 codec을 준비하지 않는다.
- `ctx._world_set_relocation(uid, destination)`: 코어 life가 소유하는 다음 리스폰 목적지 제안.
- `ctx.world_options`: immutable 초기 설정. `world_policy`, `world_handler_sources`, `world_starter_kit`, `restart_policy`, `store_path`를 제공한다.

## 저장 경계와 예외

기존 즉시 저장 경계는 각 모듈의 `SAVE_BOUNDARIES={'메서드명': True 또는 predicate}`로 선언한다. predicate 서명은 `(broker, positional_args) -> bool`이다. 강화처럼 다른 요청에도 조회되는 처리기는 기존 소비 대상 판별을 그대로 옮긴다. 일반 물약 조회가 불필요한 디스크 flush를 일으켜서는 안 된다.

훅 예외는 기본적으로 전파한다. 초기화, 거래 소비, 저장, 이동 확정의 실패를 무시하면 부분 변경을 성공으로 보고할 수 있다. 비핵심 알림·보고·정리만 모듈의 `NONCRITICAL_HOOKS`로 지정한다. 해당 훅의 `Exception`은 feature/hook/method/error 이름을 최대 16개 기록하고 다음 구독자를 실행한다. 취소와 시스템 종료는 삼키지 않는다.

응답은 기존 `_world_send`, 동일한 row/world 잠금, 저장 후 응답, 정확한 drain 뒤 `mark_delivered` 순서를 유지한다. 새로운 요청 guard·pin·해시·파일 판독을 추가하지 않는다. World runtime 잠금 안의 after_move에서 runtime에 다시 진입하지 않는다.

## 시험

기존 `*_tests.py`와 `hunt_bot*.py`의 게임 기대값은 유지한다. 코어 승격에 따른 import·서비스 연결만 수정한다. 선택 기능을 하나씩 제외한 구성과 모두 제외한 구성, 중복 메서드 거부, 훅 기본값·순서·예외 격리, 진행도 lawful 보존, 창고 UI 없는 인벤토리 저장을 확인한다.

실제 게임/포트 시험은 한 번에 하나만 실행한다. 기존 `$env:SL_TEST_PORT_BASE='22000'`은 물리 22000/24030, 미설정은 12000/14030이며 논리 endpoint는 바꾸지 않는다. 원본 codec·관측 자료·Windows 클라이언트가 없는 환경에서 실행하지 못한 시험은 실행하지 못했다고 보고한다.
