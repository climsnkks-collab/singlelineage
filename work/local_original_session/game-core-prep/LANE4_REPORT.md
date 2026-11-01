# LANE4 강화·능력치·성향·창고 연결

2026-10-27. 이번 직접 사용자 요청 범위만 구현했다. main 브랜치의 기존 dirty 서버를 이어 사용했으며 commit·ACTIVE_TASK 수정·사용자 프로필 수정·화면 캡처·보이는 실행은 하지 않았다. 메인이 기존 서버 유일 writer이고, gpt-6.1-sol/high 일회성 worker는 신규 어댑터 모듈 2종과 시험만 작성했다. 게임/고정 포트12000·14030 실행은 시험 worker 하나가 순차 소유한다.

## 연결과 근거 경계

- **강화**: run393 `ENCHANT_USE_EVIDENCE.md`의 0960 outer1=사용UID / child1=1,2=int64 대상UID,3=0,15=0,16=0을 받는다. 실제 소유·양수 수량·장비 종류·명시 등급을 확인한 뒤 startup에 읽은 `world_enchant.py`/`enchant.json`의 LOCAL L1J 확률을 계산한다. 주문서 소비와 장비 이름 변경/제거를 한 트랜잭션으로 저장한 다음 0965(절대 수량/f18 이름),0978(UID 제거),full4E38을 보낸다. 착용 장비 증발은 equipment sidecar의 weapon/slot/anchor도 같은 intent로 갱신하고 기존097A 해제 경로·자세 갱신을 사용한다.
- 강화 등급은 native grade 필드로 추정하지 않는다. 이번 LOCAL 인스턴스 계약은 이미 저장되는 ItemInfo.f18의 정확한 `[일반/축복/저주] 주문서명`과 `+N/-N 장비명`이다. f7은 기존 아이콘 값 그대로다. 원본과 동일한 이름 문법·등급 wire라는 주장이 아니다.
- `-EnchantExp 1`에서만 주문서 interaction f5=7 후보와0967 결과 후보를 켠다. 기본 후보 f1=대상UID,f2=주문서template,f3=success0/unchanged1/destroyed2/rejected3,f4=이전레벨,f5=결과레벨(소멸은 이전값)이다. 의미/enum/화면 소비는 UNKNOWN이며 `-EnchantExp '1,f3=2,f4=6'`처럼 required f1..5를 숫자로 바꿀 수 있다. 기본 모드에서는0967을 만들지 않는다. native 주문서의 actual raw7 귀속/guard와 실제 대상 클릭은 미확인이다.
- **능력치·AC**: run395 `SELFINFO_FIELDS_EVIDENCE.md`에 따라 `world_stats`를 전투 profile과 표시의 계산 접점으로 연결했다. f4..9=STR/DEX/INT/WIS/CON/CHA, f14=-표시AC이며 required18개와 기존 optional/EXP/현재HP·MP를 보존한다. 장비 sync/착탈·강화·레벨업/하락·변신 적용/만료에서 전체4E38을 다시 만든다. 변신의 미확정 능력치 보너스는 만들지 않는다. 4F0F/4F10 보너스 배분은 범위 밖이다.
- **성향**: 클라이언트 stage는 음수 chaotic,0..500 포함 neutral,501 이상 lawful로 맞췄다. 신규 Progress 기본값은 LOCAL 중립500이다. 기존 명시 저장값과 구형 lawful 누락 행의0은 그대로 보존한다. signed[-32768,32767] 영역의 L1J kill/사망위험 계산은 유지하며 근거 없는 +500 변환을 하지 않는다. 전역 이름색 전체 동등성은 주장하지 않는다.
- **창고**: run394 `WAREHOUSE_EVIDENCE.md`의 모델을 사용한다. 현재 NPC/도달거리/메뉴/전송 완료된 목록·context·행key·인벤 snapshot을 묶어 `storage→deposit→4ED2` 또는 `retrieve→0971(full ItemInfo/별도 entrykey)`를 발급한다. 4ED1 mode는 kind1/3에서1·2,kind2에서3·4이며 수량과 좌표0/0을 받는다. 즉시097B는 별도 창 정리이며 성공ACK로 만들지 않는다. 기존 shop decoder는 mode5/6만 받으므로 동일 근거 schema의 창고 mode1..4 decoder를 신규 모듈에 둔다.
- `world_town_services`의 LOCAL 정책은 개인150슬롯/플레이어180슬롯/레벨5 이상/무료 맡기기/서로 다른 찾기UID당30A다. 정확한 raw variant가 같을 때만 겹치며 착용품은 맡길 수 없다. fee는 인벤 아데나7에서 소비한다. `warehouse.json`은 inventory kit와 같은 `{version:1,inventories:[{uid,frame:hex}]}` 형식이며 빈 창고는 해당 row가 없다.
- `-WarehouseExp 1`에서만 Dorin60001/placement60009의 storage 연결·sprite143 후보 및 미확정 숫자를 켠다. 후보는 kind1,COUNT f1=0/f3=150,LIST f2=0/f4=0/f5=30/f6=150이며 `-WarehouseExp 'kind,count1,count3,list2,list4,list5,list6'`로 바꾼다. LIST f5가 공식 수수료라는 뜻은 아니며 backend30A 정책은 별개다. NPC 신원·정상 숫자·실제 원 UI는 UNKNOWN이다.
- **저장**: `world_warehouse.WarehouseStore`가 warehouse를 startup에 캐시하며 요청에서 창고 파일/핀/해시를 다시 읽지 않는다. 기존 InventoryStore CAS와 장비 소유 검사를 유지하고, 최소 `warehouse-transfer.json` intent를 fsync한 뒤 inventory/equipment/warehouse를 저장한다. 중단 후에는 EquipmentStore 생성 전에 정확한 old/new 상태를 forward 복구한다. 불명확한 저장 실패는 세션 실패로 보존하고 성공/환불/재소비로 바꾸지 않는다. 새 guard/pin/검증 도구는 추가하지 않았다.

## 키트·프로필·실행 설정

- test_knight 키트에 template25 무기/26 갑옷 주문서를 각각 일반·축복·저주5장씩 추가했다. ID/아이콘468·467/이름·raw무게625는 기존 native-dump:975/976을 재사용한다. 등급은 키트에 명시하고 서버가 이름 규약으로 저장한다.
- 시작 시 `manual-test-knight`에는 characters.json/positions.json/account-settings.bin만 있었다. 지정한 inventory.json/equipment.json/progression.json/warehouse.json은 이미 없으므로 삭제할 파일이 없고 다음 첫 지급에서 새 키트를 받는다. manual-user-play는 읽기/쓰기 시험 대상으로 쓰지 않았다.
- `start-manual-play.ps1`에 두 실험 인수/환경 전달을 추가하고 기존 broker 핀을 갱신했다. UTF-8 BOM을 유지했다. 사용자 수동 확인은 `-TestKnight -EnchantExp 1 -WarehouseExp 1`로 가능하며 창고는 Lv5 이상이어야 한다.

## 검증 기록

구문 검사13파일 성공. 지정 시나리오·5분 봇·회귀·신규 연결시험·헤드리스1회를 단일 시험 worker에서 순차 마감했고 실행 소유권을 반환했다. 신규 순수 어댑터 enchant8개/warehouse11개도 최종457개 회귀 범위에 포함된다. 최초 실패·시험 사본·부분 결과는 모두 보존했다. 패킷/순수 계산/저장 성공을 화면·입력·원본 동등성으로 확대하지 않는다.

- 원로그 접두사: `work/local_original_session/runs/lane4-20261027-20261027-004154`.
- `-scenarios.log`: death4/reconnect6/town2/items4, 총4종16항목 SUCCESS. 원 JSON을 메인에서 직접 읽어 확인했다. fresh fixture는 `hunt-scenarios-ydp5yhu5`, 각 실행 정리 완료.
- `-loopback5.log`: 첫 실행은44초 부근 SERVER_EOF/broker_failure=KeyError, cleanup_complete=true. fixture `hunt-loopback-g4219ik_`의 저장·전리품101·lawful507·원실패를 보존한다. 시험 봇 profile의 `data.items[template]`가 장착되지 않은 미정의 전리품101까지 필수 조회하여 재계산에서 실패한 것이 원인이다. 이 실행을5분 성공으로 표시하지 않는다. 회귀 단위 종료 뒤 해당 조회만 수리하고 새 시험 저장으로5분 재실행했다.
- `-regression.log`: 지정24종+새 어댑터2종,457 tests/475.057초. 첫 결과 failures3/errors1을 보존한다. integration의 주입 fixture는 새 계산에 필요한 realm.store.select가 없었고, handlers registry의 기대값은 신규097B를 빠뜨렸다. 두 시험을 실제 새 계약에 맞춰 보완했다. town의 broker 미import 검사와 polymorph의 capstone 미import 검사는26모듈을 같은 프로세스에 로드한 실행 간섭이므로 검사 삭제/완화 없이 해당 모듈을 독립 프로세스로 다시 실행한다. 나머지 성공은 재사용하며 최종 결과는 아래 후속 로그로 대체한다.
- `-loopback5-fixed.log`: 미장착 미정의 전리품 조회를 `.get`으로 수리하고 fresh `hunt-loopback-4xngmhe4`에서 재실행했다. 실제 hunt300.015초/25처치/28줍기/Lv2/사망0, bot failure=false/broker_failure=null/cleanup_complete=true. 저장은 EXP150/Lv2/maxHP40/maxMP10/lawful563. 메인이 최종 JSON과 저장 결과를 직접 읽었다. 원실패 사본은 재사용하거나 되감지 않았다.
- `-rerun-world_integration.log`12개/`-rerun-world_handlers.log`12개/`-rerun-world_town.log`14개/`-rerun-world_polymorph.log`12개는 각각 독립 Python 프로세스에서 OK. 메인이 각 원로그의 count/OK를 직접 확인했다. 최초26종457개 범위 중 재실행 대상50개를 대체하고 나머지407개 성공을 재사용한다. 제품 broker 소스는 이 과정에서 변경되지 않았다.
- `-connection.log`: fresh 개발 fixture의 실제 FIRST/로그인/선택/디코더/라우터로 강화14개 check 성공. 일반 무기/갑옷+1 저장·수신 이름/주문서0965·0978/전투weapon.enchant·AC/full4E38/중립500 및 미착용 단검의 명시-7+저주 시작 상태에서 두0978·실제 저장 제거·착용 상태 불변을 확인했다. -7은 개발용 시작 데이터이며 정상 강화로 도달한 상태라는 주장이 아니다. 착용 장비 증발의 native097A/화면은 미실행이다. 창고 첫 연결시험은 HACTION fixture가 normal f4/f5를 생략하여 `SHOP_DIALOG_NORMAL_HACTION_COORDINATE_PRESENCE_REQUIRED`로 거절됐고 timeout으로 보존했다. fixture를 원 계약의 present0/0으로 보완하고 창고만 새 저장으로 재시험한다.
- `-connection-banks-fixed.log`: fresh 창고 개발 fixture에서9 checks SUCCESS/cleanup=true. 수신sprite143 NPC→storage/deposit→4ED2 발급context→2개 보관→097B→retrieve→0971의full ItemInfo/별도key→2개 찾기·30A(1000→970)→빈목록 재개봉→새 InventoryStore/WarehouseStore의 저장 복원까지 메인이 원 JSON으로 확인했다. fixture 준비는 Lv5와 시작 위치를 명시하며, 이미 키트에 있던 등급별 주문서에 강화 시험용 중복 스택을 더 만들지 않는다. 최초 실패와 성공14개 강화 시험은 보존/재사용했다. 총 연결 범위는 개발 fixture의23 checks이며 native 입력/화면이나 정상 플레이로 만든 Lv5 시작 저장의 정식 PASS가 아니다.
- `-headless.log`/`-headless/result.json`: 지정 스크립트를 새 이름으로1회 실행했다. LC.guard 미실행 상태에서 시작했고 `background=true/private_non_input_desktop=true`였다. RUN_EXIT=0이지만 실제 게임은 **FORCED_CLEANUP**, normal_exit_verified=false/native_exit_observed_without_force=false/game_logout_protocol=UNVERIFIED이며 정상 종료 PASS가 아니다. broker failure=null/cleanup_complete=true/active_tasks0/registry_sessions0, owned_job_empty=true를 메인이 원 JSON으로 확인했다. bridge 기준 SHA256 `1d1f60a03144f0214bee56c4a875d4444d51811649135a1eaab82ec2e2899f75` 복원과 잔여 LC.guard0/포트12000·14030 listener0도 메인이 직접 확인했다. 재실행·스크린샷·보이는 실행은 없다.

## 선정 소스와 변경 파일

시험 대상 제품 broker SHA256은 `280135f497ed2e51c7c36f4f33cfc1016b55f3a744b049299767d2e7ef5bcb29`이며5분 봇 실패 후에는 제품 broker를 바꾸지 않았다. 후속 수리는 봇의 미정의 전리품 조회1줄과 시험 fixture/기대값/격리에 한정했다. 연결시험 JSON에도 당시 관련 source 식별값이 있으며, 이를 요청 시 재검사하거나 새 pin으로 사용하지 않는다.

기존 서버 변경: `broker.py`, `game_data.py`, `world_handlers.py`, `world_visibility.py`, `world_combat.py`, `world_town.py`, `world_town_services.py`, `world_alignment.py`, `world_progress.py`. 신규 어댑터: `world_enchant_inventory.py`, `world_warehouse.py`. 데이터: `data/m1/items.json`, `data/m1/starter.json`. 실행: `start-manual-play.ps1`, `hunt_bot_scenarios.py`/`hunt_bot_loopback.py`의 profile level 인수 및 loopback 미정의 전리품 조회. 시험: 기존 `world_alignment_tests.py`, `world_handlers_tests.py`, `world_integration_tests.py`와 신규 어댑터2종/연결시험1종. 기존의 다른 dirty 파일·큐·실패·원소스는 이번 변경에 포함하거나 정리하지 않았다.

## 남은 화면 확인과 제한

실제 주문서 첫 사용→장비 대상 클릭과0960 발생,0967 문구/연출,0965의+N 이름,착용품 증발 뒤 슬롯/전투/재접속을 화면에서 확인해야 한다. stat 창의 AC 부호·능력치·성향500 중립과 장비 착탈/레벨업/변신 갱신도 미확인이다. 창고지기 표시·메뉴·COUNT 보유품/보관행 선택·수량·확정 직후 닫힘·30A·재개봉을 확인해야 한다. 기존 kit codec은 빈 플레이어 인벤을 표현하지 않아 모든 행을 없애는 마지막 맡기기/두 행뿐인 주문서+장비 동시증발은 저장 전에 거절한다. 이 제한을 전체 완료로 표시하지 않는다.
