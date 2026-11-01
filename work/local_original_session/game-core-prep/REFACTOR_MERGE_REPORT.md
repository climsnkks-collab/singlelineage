# 리팩터링 병합 검증 결과

## 기준과 범위

- 작업 폴더: `main` / HEAD `f599fd7af903e0724999fff110601c8a724d52f0`의 미커밋 로컬 작업물. 커밋·푸시·브랜치 이동 없음.
- 로컬 보존 기준: `refs/backup/pre-refactor-merge-20261028` / `8de65c63476c9296a86a00249c6aa48eec923c32`.
- 리팩터링: `origin/refactor/decoupling-20261027` / `f37ca9850b360f3665243e0adf54a60eed39f4ab`, 공통 기준 `24ec7ec89922ebbeb2148426c5c452ebdf258a5a`.
- 원본 클라이언트 실행 없음. `docs/ACTIVE_TASK.md`와 사용자 `manual-user-play`·`manual-test-knight` 프로필은 수정 대상에서 제외했다.
- 이 보고서의 서버·직접 패킷 시험 결과는 원본 클라이언트 화면·입력 동등성이나 30분 플레이 완료를 뜻하지 않는다.

## 충돌 해결 및 결함 수정

- `world_feature_kit.py`, `world_feature_stats.py`는 리팩터링의 코어 호환 import로 정리했다. 빈 ItemInfo field18을 클라이언트 이름으로 채우는 로컬 변경은 `world_core_kit.py`로 옮겼다.
- `world_feature_magic.py`의 중복 스탯 projection 설치를 제거하고 `stats_modifiers`·`weight_capacity` 훅을 사용한다. 동료 토큰2070의 등록 정책 무게78을 공개 `item_policies`로 읽으며, 기존 무게·마법 스탯 회귀를 새 구조에 연결했다.
- 마법 기능을 제외해도 미정의 아이템의 정책 무게가 유지되도록 `world_core_stats.py`의 기본 무게 조회에 같은 정책을 반영했다.
- 동료 기능의 private bindings 교체와 마을 창고 저장소 참조를 기존 정책 등록 API 및 공동 인벤토리 저장 소유자로 연결했다.
- 소모품의 마법 private 상태 참조를 `consumable_magic_provider` 훅으로 옮겼다. 소모품은 `items`가 소유하는 helper로 등록해 `items` 제외 시 엔진 초기화·요청 처리도 함께 빠지게 했다. 기존 선언 시험의 reader만 이 합성 선언을 읽도록 맞췄다.
- pet 실행 harness의 고정16000 거절을 제거하고 기존 `test_ports` 매핑을 사용한다. 회귀·opt-in 통합은26000, pet 봇은16000으로 실행한다.
- 생성 후 인벤토리 저장소를 연결하는 기존 `hunt_bot_scenarios.build_epoch` fixture는 같은 저장소를 공동 인벤토리 소유자에도 연결했다.
- 선택 시점에는 인벤토리 current가 아직 없을 수 있어 식별 표시를 계산하지 않는다. `world_core_inventory.py`의 실제 kit 전송·drain·current 설정 뒤 `inventory_delivered` 훅으로 표시를 발행한다. 비월드 경로와 기존 strict kit 파서는 유지했다.
- 아이템 확장 데이터 로더, item_gfx_ext 병합·fallback, iteminfo 등록, 월드 미지원 opcode 폐기, 장비 효과 실패 비종료, talkscroll 공급 수량은 기존 로컬 의미를 보존했다.
- 첫 broker 회귀에서 디스크 몬스터19종과 lawful11종의 불일치로 초기화가 실패했다. 몬스터 파일에는 별도 population 확장 기록이 있으며 이번 worker들은 수정하지 않았다. 추가8종의 lawful/randomlawful을 기존 L1J SQL에서 확인해 `data/m1/alignment.json`만 보완했다. 기존11행 값·순서는 유지했고 기존 coverage 검사를 통과했다. 이는 별도 LOCAL backend 정책이며 공식 Classic 규칙으로 확정하지 않는다. 실패 원로그는 보존하고 해당 broker 모듈은 다시 실행한다.
- 같은 확장의 SPR 속도8행을 기존 `list.spr` 원문에서 보완했다. 기존 속도11행은 불변이다. 데이터 시험은 기존11종의 출처·Adena 기대를 유지하면서 신규15/16의 명시적 LOCAL 출처와 확장 동물의 별도 드롭 선언을 구별한다. 몬스터·드롭 값을 만들어 시험을 통과시키지 않았다.
- pet은 설치하지 않은 inventory wrapper 예약을 종료 때 해제하지 않아 같은 월드에서 복원 시 중복 등록 오류가 났다. 준비된 wrapper가 자기 예약 또는 자기 설치 handle을 해제하게 하고, pet 종료의 finally에서 미설치 상태도 함께 정리한다. 중복 등록 거부와 다른 소유자의 wrapper는 유지한다.
- M5 봇은 이름이 있는 시작 물약 UID와 방금 구매한 판매 가능 물약 UID를 혼동했다. 실제 수신 SELL 목록과 현재 보유 UID를 교차해 판매하고 수신 가격으로 기존 현금·저장 검증을 유지한다. 판매 정책·guard는 바꾸지 않았다.
- 옮겨진 Progress·인벤토리 거래·Realm/서비스 훅·relocation·카탈로그 교체·로그 소유자를 기존 시험 fixture에 연결했다. 보상 패킷의 실제 아이템 이름은 빈 문자열로 분류하지 않고 수신 UID와 실제 item 종류를 교차 확인한다. 기존 보상·용량180·1024바이트 분할·저장 실패·무효 메뉴 거절 기대는 유지한다.
- population 확장 그룹은 선언된 원그룹을 참조해 지형 출처를 확인하고 UNKNOWN0·배치 가능 칸 수를 검증한다. 기존 완전 통행 가능 그룹의 조건은 유지한다. 현재 공식 안전 한계가 +4인 아이템103은 원문과 기존 아이템 표에 맞게 옛 L1J0 시험 기대만 갱신했다.

- 이어서 확인한 시작 무기 판매 실패는 ItemInfo 이름 채움과 판매용 기본 prototype의 f18 불일치였다. `world_feature_iteminfo`가 시작 때 기존 정책 API로 같은 고정 클라이언트 이름을 등록하고, `KitItemPolicy.plain_names`로 과거 빈 이름 저장의 동등성도 보존한다. 착용 상태·다른 필드 변형·커스텀/강화 이름 거절은 유지한다. 관련 iteminfo21·handlers12·shop_menu12, 총45시험이 통과했다.
- 장거리 매트릭스 길찾기는 A* 탐색 한도를 2만→20만으로 늘리고 완료 경로를 재사용한다. 다음 칸의 live 점유·blocked edge와 실제 서버 이동 검사는 유지한다. 최종 전체 재시험은 기존 navigation/hunt 예산 인수를900초로 지정한다.
- 시작 무기 판매 단독 첫 재시험은361요청·137.401초·PASS였으나, 후속 호환 수정을 실행 중 디스크에 먼저 쓴 이력이 있다. 해당 실행은 시작 때 로드한 이전 조합의 한정 결과로 보존하며 최종 조합의 전체 재시험으로 대체 판정한다. 원로그: `raw/shop_sell_anchor_retry.log`, 시험 사본: `runs/hunt-play-matrix-82iexecb`.

- 중단 후 첫 전체 재시험의 `dungeon_items`는430회 정상 이동으로map2 계단·물약17·무기 교체까지 통과했지만 `NO_REACHABLE_SAFE_CURRENT_MAP_HUNT_GROUP`로 실패했다. 신규Lv50 바포메트의 전체spawn 사각형＋선공 반경을Lv18 봇이 위험 처리하면서map2 일반spawn 중심도 전부 제외하는 봇 정책이 원인이다. 서버 오류0·정상cleanup. 원기록: `runs/hunt-play-matrix-576ynk2v/dungeon_items/result.json`.

- 첫 전체 재시험은 `hunt-play-matrix-576ynk2v`에서12PASS/3FAIL로 마감했다. `quit_saved_map`도map1 신규 강적과 일반 스폰의 공유 사각형으로 안전 목표가 사라진 같은 봇 문제였다. `companion_full`은 실제0x4EEA 공지가 왔지만 Matrix 수신 decode 목록에서 빠져 공지0건으로 오판정했다. 공지 decode를 기존 CompanionScenario와 맞췄다.
- map1/2 봇 안전판정은 수신한 살아있는 강적의 실제 위치·공격/선공 반경과 여유2칸을 회피하고, 기존 사냥 레벨 제한을 유지한다. 같은 제품 스폰 사각형 안의 실제 통행 가능한 접근칸을 고르며, 새 적 수신으로 막히면 기존hunt 제한시간 안에서 실제Alive/tick으로 재계획한다. 현재 위험 여유 반경 안에서는 실제 적과의 거리가 늘어나는 정상 후퇴를 우선한다. 제품 몬스터·스폰·HP·레벨·공속·이동·소비 판정은 바꾸지 않았다.
- 추가 던전 단독 재시험 `hunt-play-matrix-imx3vr6l`은490이동 뒤 안전 목표 즉시실패가 남아429.819초에 실패했다. 이후 정상map2 POST의 보존 사본으로 국소 시험했다. 첫 사본은 실제 물약 소진으로 중단했고, 물약59개가 남은 더 이른POST를 복사한 `special-dungeon_recovery_retry`는65.2초에 정상로그인/재선택→실제1처치/1줍기→귀환162 소진→map0도착·정상cleanup을 통과했다. 기존POST·실패·소진은 변경하지 않았다. 국소PASS를 전체15개 판정에 합산하지 않는다.
- `hunt_bot_dungeons.DungeonScenario.travel_heading`의 선택 인수를 부모 호출 계약과 맞췄다. 직접 영향 기존 matrix1·iteminfo_loopback1·dungeons4시험이 통과했고, 후속 수정 뒤 matrix1도 다시 통과했다.

- 두 번째 전체 매트릭스 `hunt-play-matrix-duno49jm`은14PASS/1FAIL로 마감했다. 던전·저장맵 재접속은 통과했으나, 동료 봇이 스폰 중심 반경2에 이미 도착한 상태를15초 이동정체로 오판정했다. 목표 반경 도착과 미도달 정체를 구분하도록 공통 `HuntBot.step`을 수정했고, 동료 목표 선택도 같은 반경·안전 조건을 사용한다.
- 신규 몬스터의 공유 스폰 사각형은map0 일반 시나리오의 낮은 레벨 목표도 가렸다. 공통 봇의 안전판정·후퇴·실제 수신한 낮은 레벨 목표 우선을 실제 적 위치 기준으로 맞췄다. loopback은 다른 기존 시나리오와 달리terrain이 빠져 있었으므로 같은 실제 서버terrain을 연결했다. 최초3분 결과0처치·0공격·146교정은 실패로 보존했다. 수정 후 일반 시나리오4/4 SUCCESS,3분 loopback180.054초·15처치·18줍기·사망0·교정0·서버failure null·정상cleanup을 확인했다.
- 마법 봇은 poison 만료시각과 실제tick의 소유자dict 제거 사이를 즉시 비교해 실패했다. 기존 제한시간 안에서 실제 제거까지 기다리고, HS/loopback의 owned peer EOF를 처리한 뒤 broker를 닫는 기존 Matrix 정리 순서를 재사용했다. 최종 마법all은352.784초·독립2프로필·363체크·실패0·broker exception0·정상cleanup이다.
- 공통 봇 의존성이 바뀌기 전 동료·두루마리·M5·던전4계열·소모품의 성공은 이전 조합의 결과로 보존하며, 최종 조합의 결과로 합산하지 않는다. 최종 조합에서 필수 플로를 각각 다시 실행했다(아래 검증 결과).
- pet 봇(`hunt_bot_pet.py`)은 리팩터링 기준 커밋 이후 바뀐 동료 봇·토큰 의미를 따라가지 못한 기존 결함 3개가 있었다. 서버는 바꾸지 않았다.
  - 현재 동료 토큰(신성한 유니콘의 뿔)은 소환/호출 전용이라 토글 해산이 아니다. `suspend_mage`가 토큰 대신 기존 펫 창 명령8(조회 후 해산)로 마법사를 내린다. 실패 원로그: `hunt-pet-y0kb6wrl`(OBSERVATION_TIMEOUT:mage_management_toggle_off).
  - `hunt_bot_companion.check_corpse`에 추가된 마법사 토큰 사망 호출 확인(`toggle`)을 pet이 빌려 쓰며 `AttributeError`가 났다. `check_corpse`를 `check_corpse_stopped`(사망 동작·시체 유지·행동 정지)와 `check_dead_call`로 나누고, pet은 앞부분만 쓴다. 동료 봇의 검사 내용·순서는 같다.
  - 50/50 경험치 단계에서 `guarded_participation`이 HOLD로 끝난 뒤 재접속하고 다음 사냥감으로 걸어가 펫이 화면 밖에 남아 PET_CURRENT_STATUS 응답 시간 초과가 났다. 재접속 뒤 기존 FOLLOW 명령2를 한 번 더 보낸다.

## 검증 결과

원로그와 모듈별 결과: `work/local_original_session/runs/refactor-verification-20261028-013520/`. 최종 매트릭스는 `final-matrix/`, pet·소모품·동료는 `final-petcons/`에 있다. 실패 attempt의 원로그는 `*.attemptN-fail.log`로 남겼다.

| 범위 | 결과 |
|---|---|
| 충돌 마커 | 관련 소스 0개 |
| 전체 회귀 | 96개 unittest 모듈 실패0·오류0, Lane4 all exit0 |
| companion/pet opt-in 소켓 통합 | companion17 OK·skip0; pet12 OK·skip0(10배 가상시간, 첫 시도는 펫 자연 전투 사망 UNCONFIRMED로 실패, 재시도 통과) |
| play_matrix 15개 | 15/15 PASS, 시나리오별 별도 프로세스·포트 30000부터1000 간격·4개 동시, navigation/hunt 900초 |
| pet 봇 | 단독 SUCCESS 174 status·`--with-companion` SUCCESS 172 status, 10배 가상시간(실제118초/82초), 포트16000 |
| 소모품 봇 | consumables SUCCESS 30체크, 포트45000 |
| 동료 봇 all | SUCCESS 47체크, 포트46000(check_corpse 분할 뒤 실행) |
| 마법·두루마리·M5·던전4계열·loopback·일반4 | 이전 단계에서 최종 공통 봇으로 통과(위 본문) |
| 강화 표 확장 영향 | 가죽 재킷103 안전값4 기대는 이미 반영돼 있음. 관련 10개 모듈(game_data, world_enchant, world_enchant_inventory, world_iteminfo, world_shop, world_shop_menu, world_stats, world_writebehind, world_companion_equipment, world_effect_map_contract) OK |
| 봇 수정 후 회귀 | world_pet_integration(12 OK), world_companion_integration·movement·revive, hunt_bot_play_matrix_tests OK; check_corpse 외부 사용처 없음 |
| 기능 제외 구성 | 15개 구성 전부 SUCCESS(아래) |
| 수동 실행 스크립트 핀 | 24개 전부 실제 SHA256과 일치, 추가 변경 없음, UTF-8 BOM 유지 |

play_matrix 최종 결과(요청 수·초): equip_all 76·13.8, potions_after_pickup 225·58.5, shop_sell_anchor 207·73.5, warehouse_roundtrip 25·4.6, scrolls 77·23.4, enchant_poly 87·29.7, dungeon_items 739·415.9, gludin_items 538·247.4, dungeon_death_restart 226·101.4, field_death_restart 208·93.5, quit_saved_map 495·171.0, companion_full 1582·245.7, mage_login 173·58.6, early_item_use 12·3.0, spam 1449·138.9. 모두 gaps0·failures0. 이 매트릭스는 10배 도구 도입 전 실제 시간으로 끝난 실행이다.

기능 제외 구성(직접 패킷 basic 시나리오: 로그인·무게·이동·근접·처치·줍기·재시작·저장 일치·물약·종료): 전체 구성(basic·talkscroll·pet·companion 추가), 빈 목록, 그리고 alignment·combat·companion·dungeons·iteminfo·items·m5·magic·pet·quest·talkscroll·town·trade를 하나씩 뺀 13개, 총15개가 모두 SUCCESS·cleanup 정상이다. 첫 실행에서 빈 목록과 combat 제외는 실행기의 기대가 틀려 실패했다(combat 기능은 prepare 훅만 맡고 코어 근접은 남는데 "근접 없음"을 기대함). 실행기 기대를 `combat_excluded_core_melee_prepare_none`으로 고친 재실행에서 둘 다 통과했다. 서버 코드는 바꾸지 않았다. 기능을 빼면 해당 opcode는 `GAME_REQUEST_OPCODE_UNBOUND`로 폐기된다(예: 빈 목록·items 제외의 0x0960).

## 남은 문제

- 원본 클라이언트 검증은 사용자 요청에 따라 하지 않았다. 위 결과는 서버·직접 패킷 수준이며 화면·입력 동등성을 뜻하지 않는다.
- pet 통합 첫 시도는 펫이 자연 전투에서 죽어(COMPANION_DIED_DURING_GROWTH_SHARED_NATURAL_KILL) UNCONFIRMED였다. 재시도는 통과했다. 낮은 HP의 Lv5 펫이 성장 사냥 중 죽을 수 있는 확률적 결과라 반복 실행 시 다시 날 수 있다.
- 커밋·푸시는 하지 않았다.
