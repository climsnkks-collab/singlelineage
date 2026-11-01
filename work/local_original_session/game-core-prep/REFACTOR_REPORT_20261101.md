# 기능 간 결합 재감사·리팩터링 — 2026-11-01

## 기준과 증거의 범위

- 저장소: `climsnkks-collab/singlelineage`.
- 기준 브랜치: `review/refactor-base-20261101`.
- 고정 기준 커밋: `6003c1c402245722219d66b623488807ad189089`.
- 결과 브랜치: `refactor/decoupling-20261101`. 이 브랜치만 새로 생성·갱신한다.
- GitHub 연결 앱으로 기준 commit/tree와 `COUPLING_AUDIT.md`, `WORLD_FEATURE_GUIDE.md`, `REFACTOR_MERGE_REPORT.md`, `world_handlers.py`, `world_bridge.py`를 실제 읽었다. 후속 소스도 같은 SHA에서 받았다.
- 아래 감사 표의 줄 번호는 **기준 커밋**의 번호이며, 경로는 별도 표시가 없으면 `tools/local_original_session/` 기준이다. 구현 위치는 공개 함수·훅 이름으로 함께 식별한다.
- 과거 병합 보고서의 PASS는 과거 조합의 실행 결과다. 이번 결과로 재사용하지 않는다. 소스 확인, 제한된 계약 점검, 기존 unittest 실행, 실제 서버/클라이언트 실행을 구분한다.
- 감사·계획을 먼저 커밋하고, 공개 API → core 소유 경계 → companion 연결 → 효과 소비자 순서로 구현했다. 아래 최종 검증과 커밋 목록은 이번 작업의 실제 결과다.

## 결론과 설계

기존 필수 `CORE_MODULES` 6개와 선택 `FEATURE_MODULES` 28개의 구분, METHODS 중복 거부, collect/chain/fold/event 훅 구조는 유지된다. 새로운 프레임워크나 요청 guard를 만들 이유는 없다.

1차 감사 #17의 **다른 기능 효과 엔진 교체 패턴**은 M5에서 재발했다. 또 ATS/hotbar, monster skills, knight skills, consumables에서 공개 provider로 다른 기능의 엔진을 얻은 뒤 내부 상태를 직접 읽거나 변경하는 연결이 확인됐다. 공개 provider 취득만으로 상태 소유가 분리되지는 않는다. 필요한 조회·변경을 기존 소유자 메서드로 이동하고, 기능이 없을 때 기존 훅의 빈 결과/False/no-op을 사용한다.

`world_magic_stage89.py`·`world_magic_stage10.py`는 하나의 magic 기능 안에서 구현을 나눈 파일이다. 이 파일 간 호출은 독립 선택 기능 사이의 호출로 세지 않는다. 필수 core kit/maps/stats 호출도 선택 기능 의존과 구별한다.

## 1차 28항목 대조

`해소 유지`는 해당 결합이 현재 소스에서 재발하지 않았다는 뜻이다. 모든 기능 제외 구성의 실제 서버 시작 성공을 뜻하지 않는다.

| 번호 | 1차 문제 | 기준 소스 근거 | 재감사 및 처리 결과 |
|---:|---|---|---|
| 1 | bridge 필수 메서드가 선택 기능에 있음 | `world_handlers.py:856-863`; `world_bridge.py:440-449` | 해소 유지. session/maps/stats/life는 필수 core. |
| 2 | reward/kit setup의 선택 메서드 필수 참조 | `world_handlers.py:856-863`; `world_core_reward.py:198-212`; `world_core_kit.py:292-296` | 해소 유지. 필요한 기본 메서드는 core에 있음. |
| 3 | bridge가 기능 setup·Realm 구현 직접 import | `world_bridge.py:396-450,650-680` | 해소 유지. 선택 초기화는 initialize 훅, Realm 기본 구현은 core. |
| 4 | items 제외 시 모든 item-use 실패 | `world_handlers.py:798-800`; `world_feature_items.py:569-592` | 해소 유지. item_use 소비 체인과 items 소유 helper 선언. |
| 5 | town의 서비스·창고 직접 호출 | `world_handlers.py:794-806` | 해소 유지. 선택 service/warehouse 훅. |
| 6 | town이 quest 메서드·setup 필수 호출 | `world_feature_town.py:277-278,316-325`; `world_feature_quest.py:480-495` | 해소 유지. 메뉴·정책·서비스 훅. |
| 7 | 이동 dispatch가 선택 maps에 종속 | `world_handlers.py:846-852,861`; `world_core_maps.py:126-164` | 해소 유지. 필수 core maps. |
| 8 | combat 제외 시 근접 거부, prepare 결과 덮기 | `world_bridge.py:435-436`; `world_registry.py:209-227` | 해소 유지. 훅 없으면 callback 없음, 기존 합성 계약 유지. |
| 9 | after_kill 배선이 alignment 내부 | `world_bridge.py:437` | 해소 유지. bridge의 core 배선. |
| 10 | 퇴장이 다른 기능 private 상태 삭제 | `world_core_session.py:142-155`; `world_feature_items.py:509-515` | 해소 유지. before/after_leave와 기능별 cleanup. |
| 11 | core 보고가 선택 기능 필드 하드코딩 | `world_bridge.py:717`; `world_feature_alignment.py:38-49` | 해소 유지. report 훅. |
| 12 | magic이 stats 이름 덮어씀 | `world_core_stats.py:77-120`; `world_feature_magic.py:844-865,2054-2066` | 해소 유지. 단일 stats 소유자와 modifier fold. |
| 13 | talkscroll의 kit/dispatch 이름 덮어쓰기 | `world_feature_talkscroll.py:203-207`; `world_registry.py:56-60` | 해소 유지. 명시적 훅 및 중복 등록 거부. |
| 14 | magic의 단일 combat profile 슬롯 | `world_feature_magic.py:391-392,1306-1308`; `world_combat.py:480,493` | 해소 유지. modifier 목록과 자기 항목 해제. |
| 15 | magic의 kit/maps/stats 필수 호출 | `world_feature_magic.py:180,259,1892`; `world_handlers.py:856-863` | 해소 유지. 상대는 필수 core API. |
| 16 | maps가 companion 직접 import | `world_core_maps.py:192,206-207` | 해소 유지. 재배치 전후 훅. |
| 17 | maps가 items 효과 엔진 교체 | `world_feature_m5.py:95-124,143-145`; `world_feature_items.py:317-319` | **M5에서 같은 패턴 재발.** 기존 목적지 fold에 요청 UID를 전달하여 엔진 교체 제거. |
| 18 | companion 속 숨은 trade 등록·private 호출 | `world_handlers.py:880`; `world_feature_trade.py:16-19,53-57` | 해소 유지. trade 독립 등록과 give_provider. |
| 19 | companion이 진행도 공유 상태 직접 기록 | `world_feature_companion.py:1039,1584,1631-1638` | 해소 유지. progress.adopt와 Realm hook. |
| 20 | 강화/kit CAS가 town 저장소에 묶임 | `world_bridge.py:389-392`; `world_state_services.py:10-38`; `world_feature_items.py:78-84`; `world_core_kit.py:72-94` | 해소 유지. core InventoryTransactions. |
| 21 | kit이 items enchant 상태 필수 읽기 | `world_core_kit.py:25-30`; `world_feature_items.py:460-469` | 해소 유지. kit fold. |
| 22 | session이 선택 stats/reward/bindings 필수 호출 | `world_core_session.py:84-97`; `world_handlers.py:856-863`; `world_bridge.py:434` | 기본 서비스 core 승격 유지. HostBindings 노출은 신규 표에서 처리. |
| 23 | lawful 값의 이중 소유 | `world_feature_alignment.py:13-16`; `world_core_stats.py:161`; `world_core_life.py:23-33` | 해소 유지. progress API. |
| 24 | progress_dirty 여러 기능 직접 쓰기 | `world_core_reward.py:15-21`; `world_feature_quest.py:338-339`; `world_visibility.py:782-785` | 해소 유지. progress owner API. |
| 25 | talkscroll의 공유 catalog 교체·stale owner | `world_feature_talkscroll.py:49-50`; `world_visibility.py:282-287` | 원 catalog 문제는 해소 유지. HostBindings private 접근은 별도 잔여로 처리. |
| 26 | 암묵적 순서·일괄 예외 전파 | `world_registry.py:64-75,85-100,127-155` | 명시 priority/criticality 유지. 핵심 소비·저장 실패를 새로 삼키지 않음. |
| 27 | core 저장 경계의 기능 이름 하드코딩 | `world_bridge.py:211-216`; `world_feature_items.py:578-580`; `world_feature_quest.py:495` | 해소 유지. SAVE_BOUNDARIES 선언. |
| 28 | WorldView가 town/companion 필수 생성·보상 소유 | `world_visibility.py:217-248,758-785`; `world_companion_runtime.py:48-94`; `world_combat.py:685-686` | 해소 유지. 선택 runtime 설치, reward events, 공용 마법 API. |

## 이번에 추가로 등록한 결합 항목

이 표의 '신규'는 1차 28항목과 별도로 이번에 식별했다는 뜻이다. 1차 결과 커밋과 해당 행의 도입 커밋을 추적하지 않은 경우 정확한 도입일은 주장하지 않는다.

| ID | 구체 결합과 기준 파일:줄 | 처리 결과 |
|---|---|---|
| N01 | hotbar → companion `_companion_enabled/rows` 및 수동 cast 정책: `world_feature_companion_hotbar_probe.py:29-50,94-103,131,160-202` | companion owner의 `CompanionCommands`를 선택 provider로 제공. 입력·패킷·로그는 hotbar에 남김. |
| N02 | hotbar → magic `_world_magic.spells[key].mp`: 같은 파일 `:78-80` | `MagicService.spell_mp` 공개 조회. |
| N03 | hotbar → ATS `_ats_edit`: 같은 파일 `:121-123` | `companion_hotbar_suspended` chain 훅. |
| N04 | hotbar → bridge `_bridge_host` 및 bridge 파일 생성: 같은 파일 `:52-62,81-83` | `companion_hotbar_publish`를 bridge 소유로. 준비된 host만 사용하는 기존 시점 유지. |
| N05 | ATS → magic catalog/state, companion catalog: `world_feature_companion_ats.py:98-105,313-316` | 기존 magic_service와 companion catalog provider. live state만 읽는 의미 유지. |
| N06 | ATS → bridge attach 설정: `world_feature_companion_ats.py:418-419` | `companion_bridge_directory` provider. |
| N07 | companion이 follower `on_remove` 수동 wrapping: `world_feature_companion.py:887-894`; pet 예약 `world_feature_pet.py:104-109,160` | 기존 runtime_extensions.wrap에 등록. 기존 callback 실행 순서 유지. |
| N08 | shared AI private 정책 호출: `world_feature_companion.py:421,563,1467`; `world_feature_pet.py:430,435-439,450,462,587,597`; `world_companion_inventory.py:141` | 기존 CompanionAI에 좁은 공개 forwarding API. |
| N09 | monster가 magic `admit_cast` 직접 wrapping: `world_monster_skills.py:65-66,103-108` | 기존 WorldEvents의 player_magic_admit 이벤트로 사전 판정 이동. |
| N10 | monster가 magic NPC 상태·poison 직접 읽기/쓰기: `world_monster_skills.py:119-123,213-214,479-482,528-531` | PlayerMagic query/mutation 및 CompanionMonsterTarget.apply_poison 소유 API. |
| N11 | knight가 magic buff/binding dict 직접 접근: `world_feature_knight_skills.py:76-95` | MagicService has_buff/buff_weapon/remove_weapon_buff. |
| N12 | consumable이 magic effect/poison 직접 변경: `world_item_effects.py:849-851,862-872` | PlayerMagic replace_status/cure_poison. 기존 callback·저장 순서 유지. |
| N13 | iteminfo/town/pet의 core HostBindings private slot: `world_feature_iteminfo.py:106-123`; `world_feature_town.py:321-323`; `world_feature_pet.py:765` | 기존 Context에 host_bindings/configure_sale_item 공개 소유 API. |
| N14 | 장비 projection/notification/defer private 접근: `world_feature_items.py:88-93,214-215`; `world_feature_town.py:206-207`; `world_feature_quest.py:336-337`; `world_core_kit.py:95-96`; `world_feature_companion.py:1229,1278-1279` | ItemEquipmentEffect의 project_state/prepare_deferred/notify_kit_changes. 기존 조건·수명 유지. |

## 이행 순서와 불변 조건

1. 이 감사·계획을 문서 커밋으로 기록한다.
2. 기존 PlayerMagic/MagicService에 필요한 공개 API를 먼저 추가한다. 실제 동작과 상태 생성 여부를 옮기며, 기존 오류 우선순위를 유지할 callback 접점을 둔다.
3. core 소유 API와 M5 목적지 훅을 이행한다. 기존 요청 UID·클래스별 귀환 RNG를 그대로 전달한다. 기존 공개 proxy는 호환용으로 남기되 runtime에 설치하지 않는다.
4. companion/ATS/hotbar/bridge를 선택 provider로 이행한다. shared AI 및 장비 private fixture도 새 공개 API로 옮긴다.
5. monster/knight/consumables 소비자를 공개 API와 기존 이벤트로 옮긴다.
6. 기준/수정본의 동일 unittest 명령 결과와 제한된 계약 검증, 미실행 목록을 이 문서에 기록하고 기능 가이드를 갱신한다.

새 guard·중복 검사·의존성·클라이언트 패킷·저장 schema·게임 수치·`data/` JSON 변경은 포함하지 않는다. 단계별 커밋은 새 API 제공자를 소비자보다 먼저 둔다. 시험 기대값은 바꾸지 않고 private 구현에 결합된 fixture와 조회/호출만 공개 API로 옮긴다.

### 특히 보존해야 하는 순서

- silence 상태의 unknown spell도 기존 `MAGIC_CASTER_SILENCED`가 먼저 나와야 한다(`monster_skills_tests.py:139-140`). 단순 wrapper 삭제는 하지 않는다.
- knight buff 삭제 → clock → icon sync → save. icon 실패 뒤 save를 새로 실행하지 않는다.
- poison 삭제 → 다른 owner cure callback → 변경 결과 확인 → 기존 save. 없는 live state를 조회 때문에 새로 생성하지 않는다.
- hotbar 목록·adopted MP 프레임의 생성 순서를 유지하고 bridge publication 후 반환한다. 호출자는 목록 → adopted MP의 기존 순서로 송신하며 shortcut 복원 marker 앞에 목록을 둔다.
- M5 요청자 UID 전달과 core/dungeon/M5/ship의 기존 hook priority·동순위 등록 순서를 유지한다.
- 장비 commit → notification → projection 및 기존 native-inventory readiness 판정을 보존한다.


## 구현 결과와 공개 계약

구현 커밋 `7fcf35b04ac4d1f0eedfa633389f8ad2c81ef87c` 기준으로 위 재발 #17과 N01–N14를 처리했다. 변경은 `tools/local_original_session/`의 Python **40파일, 추가 413줄·삭제 223줄**과 이 보고서·기능 가이드다. 40파일에는 기존 시험 14개와 그 시험이 사용하는 두 hunt-bot fixture helper가 포함된다.

`world_registry.py`, `FEATURE_MODULES`의 구성·순서, packet codec, `SAVE_BOUNDARIES`, 저장 schema, 게임 수치와 `data/` JSON은 바꾸지 않았다. GitHub의 기준/결과 tree 비교에서 데이터 변경 **0건**, 파일 mode 변경 **0건**, 허용 범위 밖 변경 **0건**을 확인했다. 새 패키지 의존성이나 요청 guard/중복 검사도 추가하지 않았다. 기존 판정은 소유 API 안으로 이동했다.

### 훅·이벤트

인자는 기존 Context가 암묵적으로 전달하는 첫 `ctx` 다음부터 표시한다. 모두 기존 registry 또는 WorldEvents를 재사용한다.

| 계약 | 제공자 → 소비자 | 인자·방식·기능 부재 시 동작 |
|---|---|---|
| `companion_commands` | companion → hotbar | 없음 / collect. 활성 companion owner 서비스 또는 None. 등록자가 없으면 hotbar 후보·요청 처리가 비활성화됨. |
| `companion_spell_catalog` | companion → ATS | 없음 / collect. 기존 companion catalog 또는 None. ATS의 기존 정의 파일 fallback 순서 유지. |
| `companion_hotbar_suspended` | ATS → hotbar | `writer` / chain. 기존 열린 편집 창 여부. ATS가 없으면 False. |
| `companion_bridge_directory` | bridge → ATS | 없음 / collect. 기존 명시 attach directory 또는 기존 환경 설정. 없으면 기존 ATS directory refusal 경로. |
| `companion_hotbar_publish` | bridge → hotbar | `uid, keys` / chain. 기존 JSON 기록과 publish 훅 호출. 반환값은 준비된 host 존재 여부이며 전달 성공 확인은 아님. bridge/host가 없으면 False. |
| `player_magic_admit` | PlayerMagic → monster skills | `uid, now` / 기존 WorldEvents의 critical emit. 기존 silence 사전 판정을 옮김. 구독자가 없으면 no-op. |
| `item_destination_policy` (확장) | core maps/dungeons/ship/M5 | `result, position, *, uid=None` / 기존 fold. item-use만 자신의 요청 UID를 전달. UID를 전달하지 않는 기존 호출은 `position.uid`/호환 result의 기존 값을 사용. |

목적지 훅의 실제 순서는 **core maps → dungeons → ship → M5**로 이전과 같다. 58개 선언 구성에서 기존 frame route의 처리기 순서, outgoing opcode 목록, 기존 hook별 처리기 순서를 기준본과 대조했고 모두 같았다. 추가 훅은 기존 구독자 사이에 끼워 넣지 않았다.

### 단일 소유자 공개 API

아래 구현 줄 번호는 위 구현 커밋의 번호다.

| 소유자·위치 | 공개 API | 보존하는 의미 |
|---|---|---|
| `MagicService`, `world_magic.py:170-195` | `catalog`, `live_learned(uid)`, `spell_mp(key)`, `has_buff(uid,key)`, `buff_weapon(uid,key)`, `remove_weapon_buff(uid,key,clock)` | 현재 live 학습 상태만 조회; 없는 state의 복원을 새로 실행하지 않음. counter 제거의 clock/HUD/save 순서 보존. |
| `PlayerMagic`, `world_magic.py:214-217,275-276` | `before_cast` callback | 플레이어 magic owner가 기존 world event에 연결. unknown/dead 검사보다 먼저 실행되는 기존 monster silence 순서 보존. companion의 별도 engine은 기본 no-op. |
| `PlayerMagic`, `world_magic.py:400-440` | `npc_status`, `poison_of`, `set_poison`, `clear_monster_poison_effects`, `replace_status`, `cure_poison` | NPC generation 일치 조회, 기존 poison payload, 기존 state 생성 여부, cure callback·저장 시점 보존. |
| `CompanionCommands`, `world_feature_companion.py:803-872` | `ready`, `character_class`, `members`, `cast` | 소유 캐릭터/마법 후보·비용·대상·쿨다운 판정은 companion이 소유. hotbar는 원래 wire·로그·입력 처리를 유지. |
| `CompanionMonsterTarget`, `world_feature_companion.py:2296-2297` | `apply_poison(poison,now)` | 기존 poison 대입을 해당 owner로 이동. 저장 호출은 원래 소비자 위치에 유지. |
| `CompanionAI`, `companion_ai.py:275-289` | `hostile_target`, `select_target`, `move_toward`, `attack_position` | 기존 AI helper로 바로 위임. 경로·거리·RNG·예약 판정을 변경하지 않음. |
| `Context`, `world_bridge.py:97-99,139-145` | `host_bindings`, `configure_sale_item` | 기존 frozen bindings 조회 및 기존 기본 sale projection의 identity 조건에 따른 설정. |
| `ItemEquipmentEffect`, `item_equipment_effect.py:86-98` | `project_state`, `prepare_deferred`, `notify_kit_changes` | 기존 선택 상태 조건·native inventory 준비 판정·INITIAL_SYNC receipt와 송신 순서를 소유자 내부로 이동. |

Companion의 `on_remove`는 `world_feature_companion.py:970-978`에서 기존 `runtime_extensions.wrap`에 등록한다. 기존 `reset_sequence → previous → unmapped` 순서와 pet의 지연 wrapper 설치 시점을 유지한다.

### 의도적으로 유지한 내부 구현

- `MainlandItemEffects/MainlandReturnResult`는 기존 공개 호출과 기존 시험의 호환성을 위해 남았다. 서버 초기화에는 더 이상 설치하지 않는다(`world_feature_m5.py:93-124,127-144`).
- `_atomic_json`을 사용하는 기존 공용 serializer 이름은 바꾸지 않았다. `world_state_services.py:1-5,12-14`가 warehouse journal/serializer를 필수 core transaction으로 조립하며 `world_warehouse.py:185-203`은 선택 feature 상태를 읽지 않는다. town을 빼도 이 구현은 남는다. 이것을 선택 town 기능 의존이라고 주장하지 않는다.
- 같은 magic owner의 stage89/10 helper, 기존 core/codec/data helper, 필수 NPC AI의 내부 스케줄 helper를 전부 이름 변경하지 않았다. 이번 목표는 선택 기능 사이의 결합 해소다.
- 등록 28개 feature 사이의 직접 import는 정적 검사에서 0건이다. production helper의 다른 `world_feature_*` 직접 import도 0건이다. 공유 오류 목록 `_world_handler_errors`는 bridge의 core 소유 상태이므로 다른 feature private 상태로 세지 않았다.

## 검증 환경과 입력

- 환경: Linux, Python **3.12.14**. 원본 게임 클라이언트나 Windows 실행은 하지 않았다.
- Git 전송은 이 실행 환경의 `browser-proxy:8889` 연결 실패로 사용할 수 없어, 소스 취득과 원격 commit/tree/ref 갱신에 지정된 GitHub 연결 앱을 사용했다. 기준 SHA의 파일을 별도 `baseline`에 보존하고 수정본과 같은 환경·명령으로 비교했다.
- GitHub 기준 tree는 truncated=False, 931개 blob이다. 저장소의 Python 526개와 `tools/local_original_session/data/`의 JSON 123개, 합계 **649개 파일**의 취득 바이트가 기준 Git blob SHA와 일치함을 확인했다. 이 검사 코드는 제품에 추가하지 않았다.
- 다음 **저장소에 있는 대용량 JSON 2개**는 연결 앱의 큰 blob 응답에서 `Transport closed`, contents/line-range 읽기에서는 빈 content가 반환돼 두 실행 사본에 취득하지 못했다. `data/catalog/items_all.json`(12,351,577 bytes), `data/m6/field_population.json`(16,970,494 bytes). 이 둘은 '저장소에 없는 파일'과 구별한다. 원격 결과 tree는 원래 blob을 그대로 보존한다. 특히 field population 시험의 이 입력 부족은 환경상 미검증이다.

## 기존 unittest: 기준/수정본 동일 명령 비교

각 `tools/local_original_session/*_tests.py`를 별도 프로세스에서 **순차 실행**했다. 실제 명령 형식은 다음과 같으며 아래 모듈 표의 이름을 하나씩 넣었다.

```bash
python -m unittest tools.local_original_session.<module_name>
```

각 모듈에 120초 상한을 둔 실행기는 stdout/stderr와 결과를 기록했다. timeout은 두 쪽 모두 0이다. 게임·소켓 실행을 병렬로 돌리지 않았다. 기존 opt-in 환경 변수 `SL_RUN_COMPANION_INTEGRATION`, `SL_RUN_PET_INTEGRATION`는 켜지 않았다.

| 집계 | 기준 6003c1c4 | 수정본 | 비교 |
|---|---:|---:|---|
| 실행 요청한 모듈 | 182 | 182 | 동일 |
| 모듈 전체 성공(exit 0) | 20 | 20 | 같은 20개, 합계 261 tests |
| 수집/초기 import 단계 중단 | 128 | 128 | 같은 모듈·마지막 예외 |
| unittest의 Ran 집계 | 930 | 930 | 동일 |
| failure 이벤트 | 81 | 81 | 같은 실패 식별자·마지막 예외 |
| error 이벤트 | 533 | 533 | 같은 오류 식별자·마지막 예외 |
| skip | 9 | 9 | 동일 |
| timeout | 0 | 0 | 동일 |

**이번 실행에서 새 실패/오류는 확인되지 않았다. 전체 시험 통과는 아니다.** failure/error에는 subTest가 있어 `Ran - failures - errors - skips`로 성공 testcase 수를 계산하지 않았다. 일부 모듈은 성공 케이스와 오류 케이스가 섞여 있다. `_FailedTest` placeholder도 unittest의 집계에 포함될 수 있다.

단순 총계만 비교하지 않았다. 각 모듈의 exit code·Ran·fail/error/skip 및 실패 식별자·마지막 예외 메시지를 비교했다. 사본 루트, 임시 실행 폴더명, 객체 주소만 정규화한 결과 차이는 0건이었다. 따라서 아래 실패를 이 리팩터링의 신규 실패로 표시하지 않으며, 기준의 실제 게임 환경에서 원래도 실패한다고 확대 해석하지 않는다.

### 실행하지 못했거나 일부만 도달한 영역

| 분류 | 실제 근거·미확인 범위 |
|---|---|
| 기준 tree에 없는 pinned dependency | `work/local_movement_contract/contract.json`, `tools/local_character_wire_v2/wire.py`, `tools/local_world_protocol`, `tools/local_tile_passability_budget`, 기타 REA evidence가 없다. 특히 앞 두 파일은 다수 서버/마법/몬스터/장비 시험이 수집 전에 요구한다. pin·guard를 해제하거나 가짜 대체 파일을 만들지 않았다. |
| 원본 resource·terrain | `work/local_resource_provider/assets/map/0`의 S32 및 여러 원본 pack/관측 자료가 없어 실제 지도·출현·이동 검증 일부가 불가하다. |
| Windows/native | `commands_tests`의 실제 Windows file-sharing 시험은 기존 skip 조건이며, desktop/input/launcher 관련 시험은 누락 Win32 helper/DLL·관측 자료 때문에 기존 실패/오류가 재현됐다. `D:/SingleLineageRef/l1j-en-classic/db/l1jdb_m10.sql`도 없다. |
| 소켓/클라이언트 시나리오 | `world_companion_integration_tests`, `world_pet_integration_tests`의 opt-in 통합은 꺼져 있다. `world_integration_tests`, `world_companion_mp_loopback_tests`, `world_status_feedback_loopback_tests`, `world_iteminfo_loopback_tests`, `accessory_packet_tests`, `hunt_bot_play_matrix_tests` 등은 필요한 pinned 입력/실행 폴더·원본 자료의 부재로 실 플로를 검증하지 못했다. 아래 표의 실패/수집 중단을 통합 PASS로 세지 않는다. |
| 기존 선언 검사 결함 | `world_decoupling_tests`는 19 tests 중 UTF-8 BOM을 `utf-8`로 파싱하는 오류 1건을 양쪽에서 재현했다. 본래 테스트 파일의 기대값/reader를 수정하지 않았다. |
| 기능 제외 상태의 실제 startup | 28개 기능을 하나씩 뺀 실제 broker startup/게임 기본 루프는 위 입력 누락 때문에 확인하지 못했다. 아래 58구성 결과는 선언 검사다. |
| 실제 클라이언트 불변성 | packet 내용·순서, 저장 결과의 실게임 종단 비교 및 Windows bridge/DLL 검증은 미실행이다. 이번의 소스/계약 점검을 원본 클라이언트 PASS로 표현하지 않는다. |

### 별도 제한된 확인

| 확인 | 실제 명령/방법 | 결과와 한계 |
|---|---|---|
| 변경 Python compile | 변경 40파일에 `compile(source_bytes, path, 'exec')` | 40/40 성공. import·실행 검증 아님. |
| private fixture만 이행 | 수정한 14개 기존 시험의 assert 호출 AST 비교 | **1,269개 → 1,269개**. 1,267개 식은 동일. 나머지 2개는 private selection 조회 → 공개 projection fixture의 저장 결과 조회, `ai._move` → `ai.move_toward` 호출이며 기대값은 동일. |
| 귀환 의미 동등성 | `python -m unittest core_destination_contract_tests` (저장소 밖 임시 계약 점검) | 2 tests, 62 subcase 성공. 실제 기준/현재 M5 함수 body로 목적지·consume count·frames·requirements·RNG 최종 상태와 기존 UID fallback을 비교. 서버 import 아님. |
| magic owner API·순서 | `python -m unittest magic_api_contract_tests` (저장소 밖 임시 계약 점검) | 13 tests 성공. live-learning 비복원, NPC generation, poison payload, cure callback 실패, counter HUD/save, silence→unknown 우선순위·구독 제거 확인. 실제 class/function body를 추출한 점검으로 전체 게임 실행 아님. |
| 위 두 계약 점검 재실행 | `python -m unittest core_destination_contract_tests magic_api_contract_tests` | 15 tests, failures=0, errors=0. |
| 기능 선언 조합 | 실제 선언의 전체·없음·각 하나 제외·각 하나만 | 기준/현재 각각 **58/58** 등록. 기존 34 frame route·34 outgoing opcode와 기존 hook 순서 동일, 중복 이름 없음. callback body 미실행. |
| 차이·범위 | `git diff --check`, GitHub 기준/결과 tree 비교 | whitespace 오류 0; Python 40파일+문서만 변경; data/mode 변화 0. |

선언 점검은 기존 `actual_module_declarations` reader를 재사용하되 **임시 분석 코드에서만** Python이 허용하는 BOM을 읽고 imported function reference를 callback 미실행 placeholder로 표현했다. 이 보충 없이는 기존 reader가 BOM, 이어서 `_stage10_realm_status` imported alias를 처리하지 못한다. 제품 또는 기존 테스트를 수정해 이 결과를 만들지 않았다. 따라서 이것은 구성·이름·순서의 정적 증거이며, 시작 또는 frame 소비의 실행 증거가 아니다.

### 모듈별 기존 unittest 결과

모든 행의 기준/수정본 결과가 동일하다. `B`는 Ran 집계 전 수집 중단, `P`는 exit 0, `F`는 수집 이후 실패/오류다. 모듈별 정확한 명령은 위 command의 `<module_name>`을 첫 열로 치환한 것이다.

| 모듈 | 상태 | Ran | failures | errors | skips |
|---|---|---:|---:|---:|---:|
| `accessory_data_tests` | P | 7 | 0 | 0 | 0 |
| `accessory_packet_tests` | F | 1 | 0 | 1 | 0 |
| `accessory_runtime_tests` | B | 0 | 0 | 0 | 0 |
| `ats_config_codec_tests` | P | 16 | 0 | 0 | 0 |
| `attack_action_observe_tests` | B | 0 | 0 | 0 | 0 |
| `attack_feedback_tests` | B | 0 | 0 | 0 | 0 |
| `attack_session_tests` | B | 0 | 0 | 0 | 0 |
| `attack_tests` | B | 0 | 0 | 0 | 0 |
| `broker_idle_tests` | B | 0 | 0 | 0 | 0 |
| `broker_request_refusal_tests` | B | 0 | 0 | 0 | 0 |
| `broker_tests` | B | 0 | 0 | 0 | 0 |
| `commands_tests` | F | 21 | 0 | 2 | 6 |
| `companion_ai_tests` | F | 31 | 0 | 5 | 0 |
| `companion_ats_window_connection_tests` | B | 0 | 0 | 0 | 0 |
| `desktop_tests` | F | 16 | 0 | 19 | 0 |
| `edge_tests` | F | 33 | 0 | 79 | 0 |
| `element_resist_observation_tests` | B | 0 | 0 | 0 | 0 |
| `element_resist_tests` | B | 0 | 0 | 0 | 0 |
| `entry_watch_tests` | B | 0 | 0 | 0 | 0 |
| `equipment_stats_tests` | B | 0 | 0 | 0 | 0 |
| `feature_config_tests` | B | 0 | 0 | 0 | 0 |
| `field_population_tests` | B | 0 | 0 | 0 | 0 |
| `game_data_tests` | F | 8 | 0 | 1 | 0 |
| `hunt_bot_dungeons_tests` | P | 6 | 0 | 0 | 0 |
| `hunt_bot_iteminfo_tests` | P | 4 | 0 | 0 | 0 |
| `hunt_bot_play_matrix_tests` | F | 1 | 0 | 1 | 0 |
| `input_tests` | F | 63 | 44 | 1 | 0 |
| `inventory_observe_tests` | B | 0 | 0 | 0 | 0 |
| `inventory_store_tests` | B | 0 | 0 | 0 | 0 |
| `inventory_tests` | B | 0 | 0 | 0 | 0 |
| `inventory_update_tests` | F | 11 | 22 | 7 | 0 |
| `item_equipment_failure_tests` | B | 0 | 0 | 0 | 0 |
| `item_use_session_tests` | B | 0 | 0 | 0 | 0 |
| `item_use_tests` | F | 24 | 3 | 77 | 0 |
| `knight_material_drop_tests` | B | 0 | 0 | 0 | 0 |
| `launcher_tests` | F | 196 | 1 | 150 | 0 |
| `manual_move_commands_tests` | B | 0 | 0 | 0 | 0 |
| `manual_source_quit_tests` | B | 0 | 0 | 0 | 0 |
| `misc_items_tests` | B | 0 | 0 | 0 | 0 |
| `monster_skills_cancel_tests` | B | 0 | 0 | 0 | 0 |
| `monster_skills_cure_tests` | B | 0 | 0 | 0 | 0 |
| `monster_skills_phase2_tests` | B | 0 | 0 | 0 | 0 |
| `monster_skills_support_tests` | B | 0 | 0 | 0 | 0 |
| `monster_skills_tests` | B | 0 | 0 | 0 | 0 |
| `monster_weakness_tests` | B | 0 | 0 | 0 | 0 |
| `move_pickup_coverage_tests` | B | 0 | 0 | 0 | 0 |
| `movement_tests` | B | 0 | 0 | 0 | 0 |
| `npc_ai_range_tests` | F | 16 | 11 | 10 | 0 |
| `npc_edge_tests` | B | 0 | 0 | 0 | 0 |
| `npc_motion_tests` | B | 0 | 0 | 0 | 0 |
| `npc_observe_tests` | B | 0 | 0 | 0 | 0 |
| `npc_placement_tests` | B | 0 | 0 | 0 | 0 |
| `npc_session_tests` | B | 0 | 0 | 0 | 0 |
| `npc_tests` | B | 0 | 0 | 0 | 0 |
| `observe_tests` | F | 38 | 0 | 44 | 0 |
| `play_feedback_fix_tests` | B | 0 | 0 | 0 | 0 |
| `restart_tests` | F | 6 | 0 | 3 | 0 |
| `settings_tests` | B | 0 | 0 | 0 | 0 |
| `shop_price_fill_tests` | F | 3 | 0 | 1 | 0 |
| `spellbook_learning_tests` | B | 0 | 0 | 0 | 0 |
| `stack_merge_tests` | B | 0 | 0 | 0 | 0 |
| `stance_tests` | B | 0 | 0 | 0 | 0 |
| `ui_open_commands_tests` | B | 0 | 0 | 0 | 0 |
| `world_ai_tests` | B | 0 | 0 | 0 | 0 |
| `world_alignment_tests` | P | 15 | 0 | 0 | 0 |
| `world_ammo_tests` | P | 13 | 0 | 0 | 0 |
| `world_aux_requests_tests` | B | 0 | 0 | 0 | 0 |
| `world_balsim_shop_tests` | B | 0 | 0 | 0 | 0 |
| `world_bonus_stat_tests` | B | 0 | 0 | 0 | 0 |
| `world_bookmark_tests` | B | 0 | 0 | 0 | 0 |
| `world_boss_cycles_tests` | B | 0 | 0 | 0 | 0 |
| `world_combat_requests_tests` | B | 0 | 0 | 0 | 0 |
| `world_companion_ats_heal_tests` | B | 0 | 0 | 0 | 0 |
| `world_companion_ats_spell_tests` | B | 0 | 0 | 0 | 0 |
| `world_companion_ats_window_tests` | B | 0 | 0 | 0 | 0 |
| `world_companion_click_attack_tests` | B | 0 | 0 | 0 | 0 |
| `world_companion_equipment_tests` | B | 0 | 0 | 0 | 0 |
| `world_companion_hotbar_command_tests` | B | 0 | 0 | 0 | 0 |
| `world_companion_hotbar_probe_tests` | F | 2 | 0 | 2 | 0 |
| `world_companion_integration_tests` | F | 19 | 0 | 17 | 1 |
| `world_companion_magic_tests` | B | 0 | 0 | 0 | 0 |
| `world_companion_mana_tests` | B | 0 | 0 | 0 | 0 |
| `world_companion_movement_tests` | B | 0 | 0 | 0 | 0 |
| `world_companion_mp_display_tests` | B | 0 | 0 | 0 | 0 |
| `world_companion_mp_loopback_tests` | B | 0 | 0 | 0 | 0 |
| `world_companion_regen_tests` | B | 0 | 0 | 0 | 0 |
| `world_companion_resource_loopback_tests` | B | 0 | 0 | 0 | 0 |
| `world_companion_resource_tests` | B | 0 | 0 | 0 | 0 |
| `world_companion_revive_tests` | B | 0 | 0 | 0 | 0 |
| `world_companion_rules_tests` | F | 57 | 0 | 44 | 0 |
| `world_companion_spell_matrix_tests` | B | 0 | 0 | 0 | 0 |
| `world_companion_support_spell_tests` | B | 0 | 0 | 0 | 0 |
| `world_companion_tests` | P | 15 | 0 | 0 | 0 |
| `world_consumable_loopback_tests` | B | 0 | 0 | 0 | 0 |
| `world_consumable_restore_tests` | B | 0 | 0 | 0 | 0 |
| `world_craft_tests` | B | 0 | 0 | 0 | 0 |
| `world_decoupling_state_tests` | P | 20 | 0 | 0 | 0 |
| `world_decoupling_tests` | F | 19 | 0 | 1 | 0 |
| `world_delevel_tests` | B | 0 | 0 | 0 | 0 |
| `world_dungeon_maps_tests` | B | 0 | 0 | 0 | 0 |
| `world_dungeon_talkscroll_maps_tests` | B | 0 | 0 | 0 | 0 |
| `world_dungeon_terrain_tests` | F | 0 | 0 | 1 | 0 |
| `world_effect_map_contract_tests` | B | 0 | 0 | 0 | 0 |
| `world_enchant_coverage_tests` | B | 0 | 0 | 0 | 0 |
| `world_enchant_inventory_tests` | B | 0 | 0 | 0 | 0 |
| `world_enchant_tests` | P | 12 | 0 | 0 | 0 |
| `world_environment_tests` | B | 0 | 0 | 0 | 0 |
| `world_expansion_data_tests` | F | 2 | 0 | 1 | 1 |
| `world_forgotten_island_tests` | F | 0 | 0 | 1 | 0 |
| `world_gm_tests` | F | 1 | 0 | 1 | 0 |
| `world_ground_items_tests` | B | 0 | 0 | 0 | 0 |
| `world_handler_adapter_tests` | B | 0 | 0 | 0 | 0 |
| `world_handlers_tests` | F | 1 | 0 | 1 | 0 |
| `world_hpbar_experiment_tests` | P | 8 | 0 | 0 | 0 |
| `world_inn_tests` | B | 0 | 0 | 0 | 0 |
| `world_integration_tests` | B | 0 | 0 | 0 | 0 |
| `world_item_effects_tests` | B | 0 | 0 | 0 | 0 |
| `world_item_feedback_loopback_tests` | B | 0 | 0 | 0 | 0 |
| `world_item_refusal_notice_tests` | B | 0 | 0 | 0 | 0 |
| `world_iteminfo_loopback_tests` | F | 1 | 0 | 1 | 0 |
| `world_iteminfo_tests` | B | 0 | 0 | 0 | 0 |
| `world_knight_maps_tests` | B | 0 | 0 | 0 | 0 |
| `world_knight_quest_tests` | B | 0 | 0 | 0 | 0 |
| `world_knight_skills_tests` | B | 0 | 0 | 0 | 0 |
| `world_lane4_connection_tests` | B | 0 | 0 | 0 | 0 |
| `world_m1_reward_tests` | B | 0 | 0 | 0 | 0 |
| `world_m3_data_tests` | F | 0 | 0 | 1 | 0 |
| `world_m4_tests` | B | 0 | 0 | 0 | 0 |
| `world_m5_gludin_regression_tests` | B | 0 | 0 | 0 | 0 |
| `world_m5_returns_tests` | B | 0 | 0 | 0 | 0 |
| `world_m5_supply_tests` | B | 0 | 0 | 0 | 0 |
| `world_m5_tests` | F | 2 | 0 | 3 | 0 |
| `world_magic_stage10_tests` | B | 0 | 0 | 0 | 0 |
| `world_magic_stage6_tests` | B | 0 | 0 | 0 | 0 |
| `world_magic_stage7_tests` | B | 0 | 0 | 0 | 0 |
| `world_magic_stage8_tests` | B | 0 | 0 | 0 | 0 |
| `world_magic_stage9_tests` | B | 0 | 0 | 0 | 0 |
| `world_magic_status_feedback_tests` | B | 0 | 0 | 0 | 0 |
| `world_magic_tests` | B | 0 | 0 | 0 | 0 |
| `world_maps_tests` | B | 0 | 0 | 0 | 0 |
| `world_monster_status_feedback_tests` | B | 0 | 0 | 0 | 0 |
| `world_npc_defense_tests` | B | 0 | 0 | 0 | 0 |
| `world_pc_response_tests` | B | 0 | 0 | 0 | 0 |
| `world_persist_tests` | P | 14 | 0 | 0 | 0 |
| `world_pet_integration_tests` | F | 19 | 0 | 13 | 1 |
| `world_pet_tests` | P | 27 | 0 | 0 | 0 |
| `world_pledge_tests` | B | 0 | 0 | 0 | 0 |
| `world_polymorph_inventory_tests` | B | 0 | 0 | 0 | 0 |
| `world_polymorph_recheck_tests` | P | 4 | 0 | 0 | 0 |
| `world_polymorph_tests` | P | 17 | 0 | 0 | 0 |
| `world_quest_expansion_tests` | F | 13 | 0 | 13 | 0 |
| `world_quest_store_tests` | B | 0 | 0 | 0 | 0 |
| `world_quest_tests` | F | 36 | 0 | 19 | 0 |
| `world_refactor_review_tests` | B | 0 | 0 | 0 | 0 |
| `world_review_fix_tests` | B | 0 | 0 | 0 | 0 |
| `world_reward_tests` | B | 0 | 0 | 0 | 0 |
| `world_scale_tests` | P | 9 | 0 | 0 | 0 |
| `world_ship_terrain_tests` | F | 0 | 0 | 1 | 0 |
| `world_ship_tests` | B | 0 | 0 | 0 | 0 |
| `world_ship_ticket_tests` | B | 0 | 0 | 0 | 0 |
| `world_shop_menu_tests` | F | 1 | 0 | 1 | 0 |
| `world_shop_tests` | P | 26 | 0 | 0 | 0 |
| `world_shop_warehouse_tests` | B | 0 | 0 | 0 | 0 |
| `world_spawn_tests` | B | 0 | 0 | 0 | 0 |
| `world_stats_tests` | P | 14 | 0 | 0 | 0 |
| `world_status_feedback_loopback_tests` | B | 0 | 0 | 0 | 0 |
| `world_status_frames_tests` | F | 1 | 0 | 1 | 0 |
| `world_talkscroll_tests` | B | 0 | 0 | 0 | 0 |
| `world_tame_tests` | B | 0 | 0 | 0 | 0 |
| `world_terrain_tests` | B | 0 | 0 | 0 | 0 |
| `world_tests` | P | 6 | 0 | 0 | 0 |
| `world_town_services_tests` | F | 27 | 0 | 10 | 0 |
| `world_town_tests` | P | 14 | 0 | 0 | 0 |
| `world_undead_damage_tests` | B | 0 | 0 | 0 | 0 |
| `world_video_magic_damage_tests` | B | 0 | 0 | 0 | 0 |
| `world_visibility_regression_tests` | B | 0 | 0 | 0 | 0 |
| `world_warehouse_tests` | B | 0 | 0 | 0 | 0 |
| `world_weapon_effects_tests` | B | 0 | 0 | 0 | 0 |
| `world_weapon_proc_effects_tests` | B | 0 | 0 | 0 | 0 |
| `world_weight_projection_tests` | B | 0 | 0 | 0 | 0 |
| `world_weight_tests` | P | 14 | 0 | 0 | 0 |
| `world_writebehind_tests` | B | 0 | 0 | 0 | 0 |

## 커밋 목록

아래 커밋은 GitHub 연결 앱의 tree/commit/ref API로 요청한 새 브랜치에 순서대로 기록했다. 각 ref 갱신은 직전 head를 expected_sha로 지정했고 force는 사용하지 않았다. 최초 부모는 정확히 `6003c1c402245722219d66b623488807ad189089`다.

| 단계 | 커밋 SHA | 내용 |
|---:|---|---|
| 1 | `989c2669d752d114e7f41948e0c4c3de616f6c31` | docs: audit feature coupling and stage decoupling work for 2026-11-01 |
| 2 | `5f04217b64563d2b1f5beed9906c6c34d4496ce8` | refactor: expose magic-owned status and spell APIs |
| 3 | `6cb6dbf0b298c947de3319346fa7bbb41bad85e9` | refactor: route destinations and shared state through core owners |
| 4 | `6f15927b0d84eacb3624e73b484278c78ade9078` | refactor: connect companion commands and UI through optional hooks |
| 5 | `7fcf35b04ac4d1f0eedfa633389f8ad2c81ef87c` | refactor: keep monster knight and item mutations with magic owners |
| 6 | 이 문서와 WORLD_FEATURE_GUIDE의 최종 갱신 커밋 | `docs: record decoupling verification and public hook contracts` |

구현 마지막 커밋은 `7fcf35b04ac4d1f0eedfa633389f8ad2c81ef87c`다. 최종 문서 커밋의 SHA는 자기 파일 내용에 자기 SHA를 넣을 수 없으므로 브랜치 HEAD 및 `git log -1 -- work/local_original_session/game-core-prep/REFACTOR_REPORT_20261101.md`로 확인한다. 채팅 완료 보고에도 최종 HEAD를 명시한다.

## 최종 판정

요청 범위의 결합 재감사, 기존 구조를 재사용한 설계, 단계별 구현·원격 커밋을 완료했다. 재발 #17 및 추가 N01–N14는 구현으로 처리했다. 실행 가능한 기존 unittest의 관측 결과는 기준과 같고, 새 실패는 관측되지 않았다. 누락 pinned 입력·원본 resource·Windows 환경 때문에 실제 서버 시작/기능 제외 기본 루프/원본 클라이언트 패킷 동등성은 **미검증**이며 전체 PASS로 판정하지 않는다.
