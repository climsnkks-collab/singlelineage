# 기능 간 결합 재감사·리팩터링 — 2026-11-01

## 기준과 증거의 범위

- 저장소: `climsnkks-collab/singlelineage`.
- 기준 브랜치: `review/refactor-base-20261101`.
- 고정 기준 커밋: `6003c1c402245722219d66b623488807ad189089`.
- 결과 브랜치: `refactor/decoupling-20261101`. 이 브랜치만 새로 생성·갱신한다.
- GitHub 연결 앱으로 기준 commit/tree와 `COUPLING_AUDIT.md`, `WORLD_FEATURE_GUIDE.md`, `REFACTOR_MERGE_REPORT.md`, `world_handlers.py`, `world_bridge.py`를 실제 읽었다. 후속 소스도 같은 SHA에서 받았다.
- 아래 감사 표의 줄 번호는 **기준 커밋**의 번호이며, 경로는 별도 표시가 없으면 `tools/local_original_session/` 기준이다. 구현 위치는 공개 함수·훅 이름으로 함께 식별한다.
- 과거 병합 보고서의 PASS는 과거 조합의 실행 결과다. 이번 결과로 재사용하지 않는다. 소스 확인, 제한된 계약 점검, 기존 unittest 실행, 실제 서버/클라이언트 실행을 구분한다.
- 이 첫 커밋은 재감사와 이행 계획이다. 구현·최종 시험·원격 커밋 목록은 후속 커밋에서 이 문서에 갱신한다.

## 결론과 설계

기존 필수 `CORE_MODULES` 6개와 선택 `FEATURE_MODULES` 28개의 구분, METHODS 중복 거부, collect/chain/fold/event 훅 구조는 유지된다. 새로운 프레임워크나 요청 guard를 만들 이유는 없다.

1차 감사 #17의 **다른 기능 효과 엔진 교체 패턴**은 M5에서 재발했다. 또 ATS/hotbar, monster skills, knight skills, consumables에서 공개 provider로 다른 기능의 엔진을 얻은 뒤 내부 상태를 직접 읽거나 변경하는 연결이 생겼다. 공개 provider 취득만으로 상태 소유가 분리되지는 않는다. 필요한 조회·변경을 기존 소유자 메서드로 이동하고, 기능이 없을 때 기존 훅의 빈 결과/False/no-op을 사용한다.

`world_magic_stage89.py`·`world_magic_stage10.py`는 하나의 magic 기능 안에서 구현을 나눈 파일이다. 이 파일 간 호출은 독립 선택 기능 사이의 호출로 세지 않는다. 필수 core kit/maps/stats 호출도 선택 기능 의존과 구별한다.

## 1차 28항목 대조

`해소 유지`는 해당 결합이 현재 소스에서 재발하지 않았다는 뜻이다. 모든 기능 제외 구성의 실제 서버 시작 성공을 뜻하지 않는다.

| 번호 | 1차 문제 | 기준 소스 근거 | 재감사 및 처리 방향 |
|---:|---|---|---|
| 1 | bridge 필수 메서드가 선택 기능에 있음 | `world_handlers.py:856-863`; `world_bridge.py:440-449` | 해소 유지. session/maps/stats/life는 필수 core. |
| 2 | reward/kit setup의 선택 메서드 필수 참조 | `world_handlers.py:856-863`; `world_core_reward.py:198-212`; `world_core_kit.py:292-296` | 해소 유지. 필요한 기본 메서드는 core에 있음. |
| 3 | bridge가 기능 setup·Realm 구현 직접 import | `world_bridge.py:396-450,650-680` | 해소 유지. 선택 초기화는 initialize 훅, Realm 기본 구현은 core. |
| 4 | items 제외 시 모든 item-use 실패 | `world_handlers.py:798-800`; `world_feature_items.py:569-592` | 해소 유지. item_use 소비 체인과 items 소유 helper 선언. |
| 5 | town의 서비스·창고 직접 호출 | `world_handlers.py:794-806` | 해소 유지. 선택 service/warehouse 훅. |
| 6 | town이 quest 메서드·setup 필수 호출 | `world_feature_town.py:277-278,316-325`; `world_feature_quest.py:480-495` | 해소 유지. 메뉴·정책·서비스 훅. |
| 7 | 이동 dispatch가 선택 maps에 종속 | `world_handlers.py:846-852,861`; `world_core_maps.py:126-164` | 해소 유지. 필수 core maps. |
| 8 | combat 제외 시 근접 거부, prepare 결과 덮기 | `world_bridge.py:435-436`; `world_registry.py:221-240` | 해소 유지. 훅 없으면 callback 없음, 기존 합성 계약 유지. |
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

| ID | 구체 결합과 기준 파일:줄 | 처리 계획 |
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
- hotbar 목록 → adopted MP 복원 프레임 → bridge publication. shortcut 복원 marker 앞에 목록을 넣던 순서를 유지한다.
- M5 요청자 UID 전달과 core/dungeon/M5/ship의 기존 hook priority·동순위 등록 순서를 유지한다.
- 장비 commit → notification → projection 및 기존 native-inventory readiness 판정을 보존한다.

## 검증 및 최종 결과

후속 최종 보고 커밋에서 동일 기준/수정본 시험 명령, 결과 숫자, 미실행·누락 의존성, 단계 커밋 SHA를 기록한다. 원본 클라이언트 또는 Windows 실행을 했다는 주장은 하지 않는다.
