# 보너스 스탯·엘릭서

2026-10-28. `main`의 기존 dirty/untracked 작업 위에 국소 연결했다. 원본 클라이언트 실행·핀 수정·커밋은 하지 않았다. **로컬 소켓8체크 성공은 alignment 기능을 제외한 구성에 한정한다. 전체 구성은 기존 alignment 표의 현재 몬스터 coverage 불일치로 초기화에 실패했다.** 원본 화면·버튼·입력·렌더링 동등성은 미확인이다.

## 연결한 동작

- 선택 기능 `world_feature_bonus_stat.py`를 `world_handlers.FEATURE_MODULES`에 등록했다. `0x4F10 CS_RAISE_ATTR_REQ`의 f1을 읽고 Lv51부터 레벨당1포인트를 영구 기본 능력치에 분배한다. 이미 쓴 포인트·현재 레벨·영구 기본값35 한도를 확인한다. 장비/버프 합산값은 한도 판정에 쓰지 않는다. 중복/잘못된 분배는 저장을 바꾸지 않고 현재 잔여 포인트와 SelfInfo를 돌려준다.
- `0x4F0F SC_BONUS_ATTR_NOTI` f1은 잔여 포인트다. 월드 진입과 포인트 수 변경에 알리고, 분배 직후에는 저장→코어 재계산→전체 `0x4E38 SelfInfo`와 잔여 포인트 순서로 기존 송신 소유자를 쓴다. 이름만 비슷한 `SC_CHANGE_ATTR_NOTI`를 임의 ACK로 만들지 않았다. `CS_STAT_RENEWAL_*`의 미결속 opcode는 그대로 미확인이다. 초기화/재분배/회상의 촛불은 이번 범위가 아니다.
- 고정 자원·공식 사전에 있는895STR/896DEX/897CON/898INT/899WIS/900CHA 엘릭서를 기존 `0960/item_use` 훅으로 연결했다. 받은 소유 UID·실제 수량을 쓰며 Lv50 이상, 영구 기본35 미만, 엘릭서 누적5개 미만에서1개를 소비하고 해당 능력치+1을 저장한다. 포인트 분배 원장과 엘릭서 원장은 별도다. 아이템 식별·무게·아이콘·이름은 기존 공식/클라이언트 자료를 쓰고 새 판매처·드롭은 만들지 않았다.
- 코어 `_world_stats_for`에 `base_attributes` fold만 추가했다. 영구 능력치가 장비 계산 전에 들어가므로 STR/DEX의 적중·피해, DEX AC, WIS MR, 무게/회복 계산과 이후 레벨업의 CON/WIS 입력에 반영된다. 이미 얻은 HP/MP를 소급 재계산하거나 즉시 채우지 않는다. 기존 성장 계산 자체는 유지했다.
- 선택 기능끼리 메서드/상태를 직접 호출하지 않는다. 코어 인벤토리 거래·진행 저장·계산·등록 훅만 쓴다. `METHODS` 이름 중복 없이 기동했다. 기능을 제외하면 해당 요청·base fold·item 훅·outgoing 등록이 사라지고 저장의 선택 필드는 보존된다. 등록 제외 단위시험을 통과했다. 실제 원본 게임을 이용한 제외 구성은 시험하지 않았다.

## 원문 근거와 정책 경계

| 내용 | 출처와 확인 범위 |
|---|---|
| 요청 번호와 enum | `REQUEST_COVERAGE_MAP.json`의 CS_RAISE_ATTR_REQ 정적 stack-slot 결속: sender0x92C120, send0x92C1AF, opcode4F10, f1 int32. 보존 `work/local_server_rea_20261016/run395_selfinfo_stats_fields/selected-source.json`의 `levelup_enum_mapping`, `levelup_direct_calls`, `bonus_schemas`. LevelUpStatLayout callback enum은0STR/1INT/2WIS/3DEX/4CON/5CHA다. |
| 잔여 포인트 응답 | 같은 run395의 SC_BONUS_ATTR_NOTI schema f1 int32와 consumer0x117060: CharacterData+8E4에 복사하고 양수이면 LevelUpStatLayout 경로로 보낸다. REQUEST_COVERAGE_MAP의 숫자 수신 registrar4F0F도 일치한다. 원서버의 전체 인과·순서는 미확인이다. |
| 고정/보존 분석 구분 | run395 CONTROL inherited SHA256 `9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`; 요청 지도 metadata carrier inherited SHA256 `c822838351d774a2022af434829a36dbd9bee030bf22182b834ca4e8659701a9`. 서로 다른 분석 carrier를 같은 파일이라고 주장하지 않는다. 보존 주소·타입의 대응을 재사용했다. |
| 엘릭서 식별 | `work/source_game_data/native-dump-v1.jsonl` item895..900(1477..1482행)과 `tools/local_original_session/data/official/items.json`의 exact_id_and_name mapping. [공식 item895](https://api-goats.plaync.com/linclassic/v2.0/game/item/895?locale=ko-KR), 보존 `work/official_data_refresh_20261028/raw/item/895.json` 등. 공식 weight20/equipLevel50과 클라이언트 이름·아이콘을 확인했다. 공식 상세에 영구+1·총5·35 한도 문구는 없다. |
| 공식 스탯 설명 | [공식 스탯 가이드](https://lineageclassic.plaync.com/ko-kr/guidebook/view?title=스탯). 보존 `data/companion/mage_spells.json`의 `official_stat_guide_corrected.json_snapshot.paragraphList`에는 스탯별 효과와 초기화 포인트 설명이 있다. 최고 달성 레벨 기준이라는 설명은 초기화 문맥이며 이번 일반 분배에 추측 확장하지 않았다. |
| LOCAL 규칙 | `D:/SingleLineageRef/l1j-en-classic/src/l1j/server/server/clientpackets/C_Attr.java:439..509`의 Lv-50 소진수·각 기본값35 한도와 `C_ItemUSe.java:2641..2658`의 엘릭서+1/총5/35. 원 L1J item40033..40038 번호를 클라이언트에 보내지 않고 고정 클라이언트895..900 이름 대응만 사용했다. Lv51당1포인트·영구+1/총5/35·stackable은 `local_policy`이며 공식 Classic 수치 확정이 아니다. Lv50 사용은 공식 equipLevel50에 따른 로컬 소비 조건 해석이다. |

이번 조사에서 reverse-engineer-anything skill을 적용했다. 새 원본 실행/REA 세션을 만들지 않고 보존 정적 자료를 우선했다. 필요한 sender/callback 부분의 로컬 파일 해석은 `bonus-stat-evidence/`에 남겼다. 이후 run395에 같은 enum/schema/consumer가 완전히 보존된 것을 확인해 추가 RE는 중단했다. 공식 웹 검색과 API open은 수행했지만 API를 web 도구가 열지 못했고 검색 결과에 정밀 한도 근거가 없어 기존 공식 API 수집 원문을 재사용했다. 라이브 공식 업데이트를 고정 클라이언트와 같다고 주장하지 않는다.

## 저장 형식과 오류 경계

`Progress` dataclass의 기존5필드와 version1은 그대로다. 모든 기존 positional `Progress(...)`, `ProgressOwner.snapshot/mark/adopt`, lawful 갱신, 일반 레벨업, QuestStore 공동저장은 같은 API를 쓴다. ProgressStore가 각 행의 선택 `bonus_stats`를 별도로 읽어 보존한다. 구형 행에 선택키가 없으면 두 배열은0이며, 일반 저장만으로 새 키를 만들지 않는다.

```json
{"uid":1,"exp":91876054,"level":51,"max_hp":1000,"max_mp":100,"lawful":500}
```

분배 STR1회와 CON 엘릭서1회 후 해당 행에 다음 선택키만 추가된다. 배열 순서는 두 경우 모두 원본 StatAttr인 STR/INT/WIS/DEX/CON/CHA다.

```json
"bonus_stats":{"allocated":[1,0,0,0,0,0],"elixirs":[0,0,0,0,1,0]}
```

일반 포인트는 기존 temp/fsync/replace로 성장 snapshot과 선택필드를 한 progression.json에 즉시 저장한 뒤 응답한다. IO 실패 시 이전 disk/memory를 유지한다. 이후 기존 Progress 저장도 선택키를 포함하므로 snapshot 재생성으로 소실되지 않는다.

엘릭서는 기존 `WarehouseStore` forward intent를 재사용한다. `InventoryTransactions.commit_inventory`와 코어 `_world_replace_kit`가 선택 `progress_store/progress_before/progress_after`를 전달한다. 장비 anchor 제거가 있으면 기존 equipment 동시 저장 경계도 유지한다. 새로운 거래/저널 체계를 만들지 않았다.

- 구형 intent: `version,uid,inventory_before,inventory_after,warehouse_before,warehouse_after`와 선택 `equipment_before/equipment_after`가 그대로 허용된다.
- 새 intent: 위 형식에 선택 `progress_before/progress_after` 한 쌍만 더한다. 값은 전체 원 progression 문서의 bytes를 기존 방식의 hex 문자열로 담으며 없는 이전 파일은 null이다. 새 `progress_after`는 선택필드·다른 캐릭터 행을 포함한 완전한 문서다. Progress dataclass를 늘려 기존 QuestStore exact-key decoder를 깨지 않는다.
- 모든 기존 참여자 상태 확인 뒤 인벤토리 CAS→장비(필요 시)→성장 문서→창고→intent 정리를 수행한다. 불확실 IO는 성공/환불/재시도로 바꾸지 않는다. 재기동의 기존 recovery가 정확한 before/after만 받아 앞으로 마감하며 다시1개를 소비하지 않는다. 요청 중 재시작/새 파일 guard는 추가하지 않았다.
- 새 ProgressStore로 인벤토리 저장 후 성장 저장 전 중단 복구, 성장 저장 후 intent unlink 전 중단 복구, 기존 QuestStore intent의 새 ProgressStore 복구를 시험했다. 일반 레벨업/lawful/adopt/stage/commit 후에도 선택키가 남는다.

## 실행과 실제 결과

단위 최종 **74개 OK, 실패0·오류0, exit0,3.213초**. 신규12개와 기존 warehouse/progress-owner/stats/quest-store 회귀를 포함한다. 정확 명령과 stdout/stderr는 [단위 로그](../runs/bonus-stats-unit-20261028.log)에 있다.

```powershell
python -X utf8 -B -m unittest tools.local_original_session.world_bonus_stat_tests tools.local_original_session.world_warehouse_tests tools.local_original_session.world_decoupling_state_tests tools.local_original_session.world_stats_tests tools.local_original_session.world_quest_store_tests -q
```

소켓은 지정 wrapper로 각각 한 번씩, 순차 실행했다. 테스트 mapper만 기존 논리12000/14030을 실제 base/base+1로 연결해 두 endpoint 모두 작업 한도57999 이내를 지켰다. 정상 입력 순서를 기다린 실제 decoder/router/handler 경로이며 원본 클라이언트는 실행하지 않았다.

```powershell
$env:SL_TEST_TIME_SCALE='10'
$env:SL_TEST_PORT_BASE='56000'
python -X utf8 -B C:/Users/Chansol/AppData/Local/Temp/claude/D--claude/0483de89-75e7-4b94-84b8-fb31fe00f575/scratchpad/fastbot/run_fast.py hunt_bot_bonus_stat
# 전체 구성: alignment catalog must cover current M1 monsters, cleanup true

$env:SL_TEST_PORT_BASE='57000'
$env:SL_DISABLE_FEATURES='world_feature_alignment'
python -X utf8 -B C:/Users/Chansol/AppData/Local/Temp/claude/D--claude/0483de89-75e7-4b94-84b8-fb31fe00f575/scratchpad/fastbot/run_fast.py hunt_bot_bonus_stat
# 제외 구성: SUCCESS,8checks,두 epoch failure null/handler errors0/cleanup true
```

- 전체 구성 첫 실패: [summary](../runs/hunt-bonus-stats-f1xhn0x0/summary.json), [첫 실패](../runs/hunt-bonus-stats-f1xhn0x0/first-failure.txt), [명령 출력](../runs/bonus-stats-socket-first-failure-20261028.log). 실제56000/56001 소유 소켓은 초기화 실패 뒤 정리됐다. 다른 worker의 몬스터/alignment 원자료는 수정하지 않았다.
- 성공: [summary](../runs/hunt-bonus-stats-wydz0iay/summary.json), [명령 출력](../runs/bonus-stats-socket-alignment-excluded-20261028.log), [시작 fixture 설명](../runs/hunt-bonus-stats-wydz0iay/starting-fixture.json), `starting-profile/`의 characters/progression/inventory/equipment4파일. Source SHA 조합은 성공 summary의 `source_sha256`에 있다. 성공 당시 through close까지 Source를 고정했다. 이후 제품 동작 변경은 없으며 progression docstring을 설명했고, 전역 WORLD_SEND_OPCODES의 중복4F0F 한 줄을 제거했다(기존 registry.outgoing_opcodes 합성으로 켜진 구성 허용 집합은 동일).
- 시작은 새 LOCAL 시험 저장의 Lv51/EXP91876054/HP1000·MP100, 무분배와 엘릭서895..900각2개다. 이는 기존 API로 FIRST 전에 만든 명시 개발 fixture이며 Lv1→51 실제 사냥·성장 성공을 주장하지 않는다. 표준 hs fixture의 시작점32595/32906을 쓰고 본 시나리오에서 이동0·처치0이다. positions.json은 기존 지연 저장 때문에 시작4파일 사본에 없고 첫 진입/종료에서 마감된다.
- 실제 정상 FIRST→로그인→캐릭터 선택→월드→잔여1→STR분배→중복 무소비→서버가 보낸 UID의 CON엘릭서8971개 소비→Quit/close→새 broker로 같은 저장 재접속→STR/CON·잔여0·엘릭서 수량유지를 확인했다. 원본 UI의 popup 재활성/버튼 동작·애니메이션·수명/렌더링은 시험하지 않았다.

초기 별도 broker-import 단위 명령은 `MAP_HOOK_FROZEN_DEPENDENCY_REQUIRED`를 냈다. 참조 `tools/local_native_login_map_notify_hook/hook.py:14,32,40`의 ACK_SHA expected `2da189d4669c9b3c827b1ed579390a9312da6cef12e03f1349c23076e5d52ac4`, 실제 `tools/local_native_login_local_ack_hook/ack_enter_world.py` SHA256 `7a439df1a76d010c07556a6f2b90fb60aeb8778c420aaee092a8b3d877120303`이었다. 핀은 수정/우회하지 않았다. 이 관측과 지정 봇의 실제 첫 실패(alignment)는 다른 명령·시점의 결과로 구별한다. 현재 다른 통합 작업의 핀 상태를 이번 결과로 일괄 확정하지 않는다.

## 변경 파일·핀 검토 대상

제품 코드 변경은 `tools/local_original_session/` 아래 새 `world_feature_bonus_stat.py`와 기존 `world_handlers.py`, `world_core_stats.py`, `world_core_kit.py`, `world_progress.py`, `world_state_services.py`, `world_warehouse.py`다. 이7파일이 통합 시 핀/Source 검토 대상이며 이 worker는 핀을 바꾸지 않았다. world_bridge.py는 중복 변경을 되돌려 최종 worker 변경이 없다.

시험은 새 `world_bonus_stat_tests.py`, `hunt_bot_bonus_stat.py`; 설명은 이 파일과 `bonus-stat-evidence/`; 요청 지도는 `REQUEST_COVERAGE_MAP.json`의 CS_RAISE_ATTR_REQ 및 관련 status counter만 수정했다. 기존 *_tests.py 기대값, ACTIVE_TASK, 사용자 프로필, launcher, 관측/장비 효과 원본, 변신·마법·퀘스트·동료·전투·몬스터/성장 표, 원본 자원·기존 저장·로그는 건드리지 않았다. 요청 지도 Markdown 요약은 이번 writer 범위가 아니므로 기존 통계 요약이 남아 있을 수 있다.

