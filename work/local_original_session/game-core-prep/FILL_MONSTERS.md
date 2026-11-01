# 몬스터·스폰·드롭 채우기

현재 등록은 [공식366 무스폰 보충](#공식366-기준-무스폰-등록-보충-2026-10-28)의277종이다. 앞부분87종/323그룹은 당시의 기록이다.

2026-10-28 KST. 고정 클라이언트 **26.09.29.2001**과 저장 공식 사전 **2026-10-27 snapshot**을 기준으로 데이터만 보강했다. Python 코드·기존 문서·저장·프로필을 수정하지 않았고 게임·서버·봇·포트 실행과 git 커밋은 하지 않았다. 다른 작업자의 리팩터링 변경은 보존했다.

**고유 몬스터31→87종(+56), 스폰131→323그룹(+192), 아이템279→382종(+103), 유효 활성 드롭86→421조합(+335).** 원래 미해결192조합 중83을 활성화하고109는 부족한 근거를 기록했다. 기존 양쪽누락3조합도 원문을 찾아 복구·활성화했다. 선정87종의 client 드롭956조합은 **활성421 + 미해결535**, 교집합·양쪽누락·client밖 활성 모두0이다.

몬스터87/366=23.77%는 공식 사전 전체 대비 등록 비율이다. 이번 대상 지역의 공식 regionNames에 해당하는 고정 client 몬스터는 전부 등록·배치해 해당 snapshot 대조 누락0이다. 클래식 전체 등장조건·시즌·보스 주기·원본 동등성 완료율로 확대하지 않는다. 신규56종까지 포함한 드롭 활성률은421/956=44.04%이며, 기존31종만 고정하면86/281→172/281(30.60%→61.21%)이다.

87종은 모든 해당 표를 병합한 최대 정의 수다. 정적 로더 기준 M1 단독19종, M3까지26종, M4까지57종, M6까지71종, M5까지87종이다. 실제 활성화에는 기존 MapExp2·M5 설정과 거리·지형·수명 조건이 적용된다. 이번 작업에서 실행 설정을 켜거나 현재 서비스의 활성 몬스터 수를 관측하지 않았다.

## 맵별 추가 결과

`전→후`는 이번 작업 시작 시 표와 최종 표의 비교다. 몬스터는 해당 맵 스폰의 고유 template 수, 스폰은 그룹 행 수다. 목표개체는 target_count 합계로 실제 동시 활성 NPC 수가 아니다. 드롭은 각 시점의 유효 전역 드롭 표를 **각 시점에 그 맵에 있던 template 집합**에 투영한 `(monster,item,grade)` 수다. 같은 몬스터가 여러 맵에 있어 맵별 드롭 열은 합산하지 않는다. map4는 m4+m5를 합쳐 센다.

| 맵 / 지역 | 몬스터 전→후(추가종) | 스폰 전→후 | 목표개체 전→후 | 활성 드롭 전→후(추가조합) |
| --- | ---: | ---: | ---: | ---: |
| 0 말하는 섬 | 11→19(+8) | 37→45 | 108→116 | 48→128(+80) |
| 1 말섬 던전1층 | 4→9(+5) | 4→9 | 12→17 | 11→63(+52) |
| 2 말섬 던전2층 | 10→12(+2) | 10→12 | 23→25 | 39→78(+39) |
| 4 본토 | 21→68(+47) | 43→147 | 81→185 | 60→299(+239) |
| 7 글루디오 던전1층 | 2→8(+6) | 2→8 | 4→10 | 9→54(+45) |
| 8 글루디오 던전2층 | 2→9(+7) | 2→9 | 4→11 | 5→57(+52) |
| 9 글루디오 던전3층 | 2→12(+10) | 2→12 | 4→14 | 8→65(+57) |
| 10 글루디오 던전4층 | 2→13(+11) | 2→13 | 4→15 | 7→72(+65) |
| 11 글루디오 던전5층 | 3→10(+7) | 3→10 | 6→13 | 12→69(+57) |
| 12 글루디오 던전6층 | 3→12(+9) | 3→12 | 6→15 | 7→76(+69) |
| 13 글루디오 던전7층 | 1→9(+8) | 1→9 | 2→10 | 4→63(+59) |
| 19 요정숲 던전1층 | 1→4(+3) | 1→4 | 2→5 | 0→23(+23) |
| 20 요정숲 던전2층 | 1→7(+6) | 1→7 | 2→8 | 0→17(+17) |
| 21 요정숲 던전3층 | 2→7(+5) | 2→7 | 4→9 | 4→25(+21) |
| 43 개미굴1층 | 2→2(+0) | 2→2 | 4→4 | 5→6(+1) |
| 44 개미굴1층 | 2→2(+0) | 2→2 | 4→4 | 5→6(+1) |
| 45 개미굴1층 | 2→2(+0) | 2→2 | 4→4 | 5→6(+1) |
| 46 개미굴1층 | 2→2(+0) | 2→2 | 4→4 | 5→6(+1) |
| 47 개미굴1층 | 2→2(+0) | 2→2 | 4→4 | 5→6(+1) |
| 48 개미굴1층 | 2→2(+0) | 2→2 | 4→4 | 5→6(+1) |
| 49 개미굴1층 | 2→2(+0) | 2→2 | 4→4 | 5→6(+1) |
| 50 개미굴1층 | 2→2(+0) | 2→2 | 4→4 | 5→6(+1) |
| 51 개미굴2층 | 2→3(+1) | 2→3 | 4→5 | 5→18(+13) |

m6의 배 내부 map5/6은 사냥지역 공식분모가 없어 추가하지 않았다. m5의 기존 오렌·하이네 배치는 보존했고 이번 확장 대상에 더하지 않았다. map4의 글루디오·켄트·윈다우드·기란 및 기존 요정숲·오크숲별 증분과 추가 ID는 [지역별 상세](FILL_MONSTERS_POPULATION.md), 각 `data/m*/population_sources.json`에 있다. 윈다우드19종·요정숲21종처럼 공식 지역분모를 초과하는 수는 보존한 기존 LOCAL 배치를 포함한다.

기존 몬스터·스폰 행은 보존했다. 신규192그룹은 같은 map/field/town의 기존 사각형에 각1마리를 추가하는 LOCAL 정책이다. 그중95그룹은 해당 지역에 대응 L1J spawn 원행이 있고97그룹은 공식 지역 확인과 기존 지역 사각형으로 배치했다. 새 좌표·밀도·주기·지형·도달성은 공식 확인이나 실제 실행 검증이 아니다. 서로 다른 client ID는 유지했으며 해골25는29와 드롭을 합치지 않았다. 25의 능력치는 별도 L1J 변종 미확정인 공유 backend 참고값이다.

## 드롭·아이템과 잔여

기존31종의 잔여109조합을 재대조했다. 58개 고유 아이템 ID 모두 고정 클라이언트 카탈로그(`data/catalog/items_all.json`)와 저장 공식 사전(`data/official/items.json`)에 존재해 신규 `items_ext/drops_misc.json`/`item_gfx_ext` 행은 추가하지 않았다. L1J 선정 NPC 자신의 droplist와 대응 후보를 확인해 **48조합을 `local_policy`로 활성화**했고, 61조합은 보류했다. 모든 활성 행은 L1J 출처를 기록하며 클래식 원본의 확률·수량이나 변종 동일성을 확정하지 않는다.

| 판정 | 조합 수 | 처리 / 사유 |
| --- | ---: | --- |
| 활성 | 48 | 선정 NPC 자신의 L1J droplist의 확률·수량을 `local_policy`로 기록. 대응 후보 차이·고정 클라이언트 변종 미확정은 각 원행 이력에 남김. |
| 보류 | 36 | 해당 NPC의 후보 아이템·등급에 대응하는 droplist 확률·수량 행 없음. 다른 NPC·등급 값을 대신 쓰지 않음. |
| 보류 | 21 | 해당 NPC SQL은 있으나 아이템/등급 변종 후보를 유일하게 대응할 근거 부족. |
| 보류 | 4 | 오크 투사의 목걸이314 3조합, 오우거의 벨트566 1조합. 공식·클라이언트 사전과 현재 ItemDef는 있으나 해당 NPC의 드롭 아이템 변종·확률/수량 대응 근거가 부족해 보류. |
| 합계 보류 | 61 | 기존109 중 활성48 제외. |

| 범위 | 활성 | 미해결 | client 구성 |
| --- | ---: | ---: | ---: |
| 기존31종, 작업 전 | 86 | 192 | 281(양쪽누락3 포함) |
| 기존31종, 재처리 후 | 220 | 61 | 281 |
| 신규56종 | 249 | 426 | 675 |
| 최종87종 | 469 | 487 | 956 |

신규56종 포함 총 미해결487은 기존31종 보류61 + 신규56종426이다. 지원되지 않는 장신구를 일반 기타품으로 위장 등록하지 않았다. 남은 미해결은 원 드롭 표의 unresolved 사유와 `resolved_unresolved_history`에 처리 전 원행을 보존했다. 활성은 데이터 표 로딩 범위이며 실제 획득·줍기·사용·렌더링·저장/복원이나 원본 동등성 PASS가 아니다.

기존 양쪽누락3은 요정숲 오크156의 item40/88/101 grade2다. 실제 L1J45009의 SQL3948~3950에 대응 저주 아이템200001/220034/220135가 있다. 각 token·kind·bless2·raw f10·f5/f6 대응이 맞으므로 각각 chance50000/1000000, count1로 활성화했다. 일반등급 roll을 전용한 것이 아니다.

## 출처 비율

우선순위는 고정 client ID/토큰/sprite/아이템 구성·gfx → 저장 공식 level/regionNames → 별도 L1J backend 참고 정책이다. 공식 수집본은 확률·수량·HP 등의 빈칸을 제공하지 않으므로 그 값을 공식 확인으로 올리지 않았다.

몬스터18필드·스폰6필드의 **로더 소비 source 셀4926개**를 센 비율이다. 중복 표의 물리 행을 포함하고 메타데이터는 제외하므로 고유 몬스터의 출처 비율이나 원본 구현율과 다르다.

| source | 셀 | 비율 |
| --- | ---: | ---: |
| client | 1604 | 32.56% |
| official | 166 | 3.37% |
| l1j | 1187 | 24.10% |
| local_policy | 1969 | 39.97% |

기존 활성행의 source는 유지했고 신규 L1J 기반 정책은 local_policy로 구분했다. 신규103개 아이템의 최상위 source 셀1236개는 client515(41.67%)·local_policy721(58.33%)이다. 활성421조합의 구성 item 출처는 전부 client다. roll source는 기존 l1j79(18.76%)·local_policy342(81.24%)이며, 후자는 기존7과 신규335를 포함한다. 공식 확률/수량으로 분류한 행은0이다.

기준 원문: `work/source_game_data/native-dump-v1.jsonl`, `work/npc_field_semantics/hypotheses/all-drop-pairs.json`, `data/catalog`, `data/official/{monsters,items}.json` 및 각 `source.raw_path`, `D:/SingleLineageRef/l1j-en-classic/db/l1jdb_m10.sql`. 공식 API 현재 응답을 재수집한 결과는 아니다.

## 검증·변경 범위

JSON88파일을 파싱하고 `python -X utf8 -B`에서 `game_data.load_m1()` → 기존 M3 로더 → `game_data.load_m4()` → 기존 M6/M5 로더를 순서대로 호출했다. 최종 **87monsters/323groups/382items/421active/535unique unresolved**를 확인했다. unresolved 실제 append 원행은664이며 동일 조합이 여러 표에 보존돼 고유535와 다르다. 활성/미해결 교집합0, 활성 ItemDef 누락0, 스폰 MonsterDef 누락0, group ID 중복0, roll 범위·수량·등급·rect·respawn 범위 이상0, 신규103종 gfx 로딩을 확인했다. 이는 데이터 로딩·참조 검증이며 실제 게임 PASS가 아니다.

변경 데이터는 `data/{m1,m3,m4,m5,m6}/{monsters,spawns,drops}.json`, 신규 `population_sources.json`, `data/m1/items_ext/drops_misc.json`, `data/m1/item_gfx_ext/drops_misc.json`이다. 결과 문서는 본문과 위 연결한 신규 상세 문서·JSON이다. 기존 DATA_COVERAGE_MAP은 작업 전 기준으로 보존했다. 화면·입력·실제 드롭/줍기·사용·저장/복원, 혼합 배치 지형, 보스·특수공격·마법·펫·테이밍 동작은 이번 실행 금지 범위에서 검증하지 않았다.

## 실제 서버 봇 감사 결과 (2026-10-28)

기존 Matrix/loopback의 FIRST → 정상 로그인 → 수신 캐릭터 reference로 선택 → 월드/가방 수신 → 실제 이동·공격·줍기 요청 → Quit/finally/close를 재사용했다. 원본 클라이언트는 실행하지 않았다. 이 감사 worker의 변경은 새 tools/local_original_session/hunt_bot_spawn_audit.py와 본문 두 파일이며, 몬스터·스폰·드롭 데이터와 NPC 생성·AI·전투 코드는 무수정이다.

SL_EXPERIMENT_MAP=2·SL_EXPERIMENT_M5=1의 실제 world에서 87종/323그룹을 로드했다. 전체117개 공유 사각형, RAM경계4그룹, 부족한111그룹/31사각형, 미처치 일반16그룹의 개별 실행, 바포메트1그룹을 순차 시험했다. 전체166 epoch의 cleanup_complete=true이며 최종 포트56000/58030 listener 없음이다. 기본 fixture는 새 저장의 사전 위치·Lv30/HP581·test_knight 장비/물약100이다. 재시험은 같은 레벨/HP에 +9장검, +6방어구7부위(AC-49), 빨간물약200·초록/용기 각10의 별도 시작 fixture다. 불필요한 초기 가방 행은 첫 지급 전에 제외해 무게 guard를 유지했고 초록/용기는 수신UID의 정상 사용 요청으로 소비했다(speed80/80 수신). 사용자 저장·원본·NPC HP·RNG·전투식·간격 guard는 강제로 바꾸지 않았다. 지정된 fast_clock의 10배 idle 모드를 사용했다.

**아래는 여러 개발 attempt의 관측 범위이며 단일 Source의 정식 PASS가 아니다.** 1차 실행 도중 다른 담당자가 Matrix 원파일을 바꿔 최초 import 캐시와 나중 디스크 원문의 줄 텍스트/일부 fixture 입력이 다를 수 있다. 또 다른 담당자가 드롭 활성421→469·미해결535→487을 갱신했다. 각 fresh epoch가 표를 다시 읽으므로 모든 epoch의 정확한 활성 드롭 크기는 미기록이다. 본 감사 worker는 이 표들을 수정하지 않았으며 실행별 해시·시험 저장·원실패·부분 결과를 따로 보존했다. 실제 수신된 드롭은 그 실행의 관측 사실로 남긴다. 4E96은 표시 패킷 수신이며 native sprite 실제 렌더링·원본 입력/화면·30분 직접 플레이는 미확인이다.

고유87종·323그룹 모두 server-issued UID에 연결된 4E96 수신을 확인했다. 접근314/323그룹, AI상태와 위치 변화가 함께 관측된 배회145/323그룹이다. 몬스터×맵218조합 중 실제 자기 공격에 연결된 처치204, ground source NPC UID까지 연결된 드롭 관측154조합이다. 고유 몬스터 처치 관측은82/87종이다. 배회0은 즉시추격·공격 또는 관측 부족과 구별했고 정지 오류로 판정하지 않았다. 드롭0을 오류로 추정하거나 성공할 때까지 반복하지 않았다.

|맵|그룹 총/수신/접근/배회|몬스터×맵 총/처치/드롭관측|
|---|---:|---:|
|0|45/45/45/39|19/18/16|
|1|9/9/8/9|9/8/7|
|2|12/12/7/6|12/6/6|
|4|147/147/147/78|68/68/47|
|7|8/8/8/3|8/8/8|
|8|9/9/9/0|9/9/9|
|9|12/12/12/1|12/12/8|
|10|13/13/13/0|13/13/9|
|11|10/10/10/0|10/9/9|
|12|12/12/12/2|12/11/9|
|13|9/9/6/0|9/6/6|
|19|4/4/4/3|4/4/1|
|20|7/7/7/3|7/7/0|
|21|7/7/7/1|7/7/4|
|43|2/2/2/0|2/2/2|
|44|2/2/2/0|2/2/2|
|45|2/2/2/0|2/2/1|
|46|2/2/2/0|2/2/2|
|47|2/2/2/0|2/2/2|
|48|2/2/2/0|2/2/1|
|49|2/2/2/0|2/2/2|
|50|2/2/2/0|2/2/2|
|51|3/3/3/0|3/2/1|

같은 맵/template의 전투는 대표 그룹 검증이며 다른 지역의 생성·접근은 그룹별로 남겼다. map4 글루디오·켄트·윈다우드·기란 및 기존 오렌·하이네는 population_area/region/town_id·사각형·원group으로 구별했다. map5/6 배 내부는 사냥 스폰 행이 없어23맵 분모에 없다. [323그룹 표](../runs/spawn-audit-70tvhoc7/review-groups.md), [218 몬스터×맵 표](../runs/spawn-audit-70tvhoc7/review-monster-map.md), [집계·남은 항목 JSON](../runs/spawn-audit-70tvhoc7/review-summary.json)에 각 attempt의 실제UID·원결과를 연결했다.

수정한 오류는 감사용 RAM fixture다. 기존 Matrix는 segment를 x 기준, transform grid를 x+1 기준으로 써 x=32895 경계에서 EDGE_CLIENT_POSITION_INVALID가 났다. 감사봇만 수신 x,y를 그대로 mirror하게 고쳤고 같은4그룹 생성·접근·처치4/4·드롭5를 확인했다. native guard와 스폰 위치는 그대로다. 또한 사망 예외에도 finally에서 실제 대상별 공격·HP 전후·마지막 좌표를 기록하게 했다. 바포메트 단독 시험에서 자기대상 공격116회·HP3000→2860 뒤 PC 사망이 기록돼 예외 경로를 확인했다. 초기 두 소스의 사망 시 누락된 HP는 소급 추정하지 않고 미기록으로 남겼다.

아래 두 문단은 위 A~E 감사 당시의 잔여·실패 기록이다. 보스6조합의 후속 결과는 [보스 고레벨 추가 관측](#보스-고레벨-추가-관측-2026-10-28), Lv30 사망 진행도 수정과 비소켓 검증은 [성장 데이터](PC_GROWTH_DATA.md#사망-경험치의-국소-수정)에서 구분한다.

남은 처치 미확인은14조합이다. 보스6조합/고유4종은 커츠(map0), 바포메트(map2), 데스나이트(map11/12/13), 거대 여왕 개미(map51)이며 사망·앞선 배경 전투의 미시도·HP미기록을 그대로 남겼다. 보스 처치·드롭은 미확인이고 같은 제한을 반복하지 않았다. 지원 성장표 상한Lv30과 보스 AC-65~-67·HP2000~8000의 시작조건 한계가 있다.

일반8조합은 map1 오크0, map2 돌 골렘6·괴물 눈11·해골25/29·해골궁수276, map13 웅골리언트31·해골궁수276이다. 각각 독립 시작 fixture로1회 더 시도했다. map2 다섯 행은 기존 bounded A*가 정적경로를 찾았지만 실제 대상 접근을 끝내지 못했다(수신 이동거절0, 일부 accepted step0). 동적NPC/시체 점유·움직이는 대상·봇경로 선택의 정확한 기여는 미확인이며 지형단절로 판정하지 않았다. map1 오크는 수신 시야에서 사라져 마지막 좌표 미확인이고 map13 두 행은 접근 중 PC 사망이다. 데이터 오류를 입증할 근거가 없어 배치·밀도·확률은 무수정이다. 범위 밖 잔여로 Lv30 사망의 world.progress_errors에 death EXP loss needs the next cumulative level threshold가 있다(성장표 마지막 레벨의 다음 EXP 임계값 부재). 해당 진행도/사망 코드는 수정하지 않았다.

검증 명령: 환경 SL_TEST_TIME_SCALE=10, SL_TEST_PORT_BASE=56000에서 python -X utf8 -B C:/Users/Chansol/AppData/Local/Temp/claude/D--claude/0483de89-75e7-4b94-84b8-fb31fe00f575/scratchpad/fastbot/run_fast.py hunt_bot_spawn_audit. 국소 실행에는 --strong-fixture --groups <실제group목록>, 개별 실행에는 --one-group-per-epoch를 추가했다. 목록은 runs/spawn-audit-retry-groups-20261028.json·spawn-audit-isolated-groups-20261028.json에 있다.

원결과: [전체 A](../runs/spawn-audit-70tvhoc7/summary.json)·[경계수정 B](../runs/spawn-audit-5f7o4cro/summary.json)·[강한장비 C](../runs/spawn-audit-ayypm3bm/summary.json)·[독립일반 D](../runs/spawn-audit-dhpkx8ub/summary.json)·[바포메트 E](../runs/spawn-audit-f4xwtc_z/summary.json). 콘솔 원로그는 기존 runs/spawn-audit-{full,retry,isolated,baphomet}-20261028.log와 각 clock 로그다. Windows PowerShell stderr 리디렉션은 FAST_CLOCK를 NativeCommandError 형식으로 기록해 셸exit1이지만 bot 원문의 exit0·cleanup과 구별했다. 모든 원실패/저장을 보존했고 커밋은 하지 않았다.

## 보스 고레벨 추가 관측 (2026-10-28)

성장표 확장·몬스터 공격 상한 수정 뒤 기존 감사봇에 `--fixture-level`을 열어, 보류했던 보스6조합을 각각 새 Lv99 저장에서 정상 FIRST/login/select/world → 실제 공격·드롭·줍기 → Quit/close로 시험했다. Lv99 EXP1823000470·성장 HP1926은 현재 L1J 기반 LOCAL 정책이며 공식 최대 레벨 확인이 아니다. 원본 클라이언트는 실행하지 않았다. **아래는 서로 다른 시작 fixture/attempt의 개별 관측이며 단일 Source의 전체 PASS로 합산하지 않는다.** 각 summary의 기존 source_sha256과 epoch별 시작 저장·fixture_notes·requests.jsonl·result.json을 기준으로 읽는다.

| 보스 / 맵 | 시작 장비·회복품 | 자기 스윙 | NPC HP | 실제 드롭/줍기 행 | 원결과 |
| --- | --- | ---: | --- | ---: | --- |
| 커츠 / 0 | 기존 strong(+9장검·+6방어구·빨간물약200) | 131 | 2000→0 | 4/1 | [uq66o7wi epoch1](../runs/spawn-audit-uq66o7wi/epoch-001/result.json) |
| 바포메트 / 2 | catalog·맑은물약150 | 134 | 3000→0 | 2/2 | [4dc1n0du epoch1](../runs/spawn-audit-4dc1n0du/epoch-001/result.json) |
| 데스나이트 / 11 | catalog·맑은물약150 | 222 | 4000→0 | 4/2 | [4dc1n0du epoch2](../runs/spawn-audit-4dc1n0du/epoch-002/result.json) |
| 데스나이트 / 12 | catalog·맑은물약150 | 239 | 4000→0 | 4/4 | [4dc1n0du epoch3](../runs/spawn-audit-4dc1n0du/epoch-003/result.json) |
| 데스나이트 / 13 | catalog·엔트열매250 | 160 | 4000→0 | 3/3 | [qusou3j9 epoch1](../runs/spawn-audit-qusou3j9/epoch-001/result.json) |
| 거대 여왕 개미 / 51 | catalog·맑은물약150 | 306 | 8000→0 | 4/3 | [4dc1n0du epoch5](../runs/spawn-audit-4dc1n0du/epoch-005/result.json) |

catalog fixture는 실제 카탈로그 고대의 검672·고대의 판금 갑옷667을 강화 미지원 상태인 +0으로 지급하고, 나머지 기존6부위 +6과 초록/용기 각10을 유지했다. 모두 첫 로그인 전 기존 grant/장비 초기화 API로 준비했으며, 회복품·속도품은 수신된 소유 UID의 정상 사용 요청으로 소비했다. 최종 combat profile은 Lv99/고대검+0/AC-65였다. 맑은물약130과 엔트열매279는 기존 회복 정책을 그대로 사용한다. map13 성공 epoch의 엔트열매 실제 소비는157개다. 물약·열매 수량과 무게를 포함한 일반 인벤토리/공격 guard는 유지했다. 시야 밖 생성은 고정 사각형 안 정적 경유지를 정상 걸어서 탐색하도록 감사봇만 수정했으며 live 좌표·스폰·HP·RNG·전투·드롭 규칙을 바꾸지 않았다.

실패도 보존했다. [6pbcwqtm](../runs/spawn-audit-6pbcwqtm/summary.json)은6epoch 모두 선택0x4E28에서 당시 `world_stats.equipment_set_modifiers`의 `ItemDef.item_id` AttributeError로 월드 진입 전 실패했다. 담당 범위 밖 수정 뒤 fresh로 재실행했다. [uq66o7wi](../runs/spawn-audit-uq66o7wi/summary.json)는 커츠만 처치했으며, 바포메트는 생성됐지만 시야 수신이 없어 미시도, 나머지4조합은 빨간물약200소진·PC사망이다. [4dc1n0du](../runs/spawn-audit-4dc1n0du/summary.json)의 map13은 맑은물약150소진·NPC HP11에서 PC사망한 원실패를 유지했다. 정상 epoch 종료만으로 미시도·미처치를 성공 처리하지 않았다.

DK의 작은 순HP감소는 NPC 흡혈 마법의 실제 소비와 함께 관측했다. catalog의 map11/12/13에서 VampiricTouch20회가 각각1871/1914/2228 HP를 복구했고, map13 열매 재시도는2103을 복구했다. 기존 NPC 마법·MP·회복 코드의 읽기 관측이며 단순 재생 오류나 원본 동등성으로 판정하지 않는다. 새 groups.json에는 최종profile·자기4E31 hit/miss·해당 NPC의 기존 마법 event만 좁게 기록했다.

총18epoch의 cleanup_complete=true이고 월드 진입한12epoch의 world.progress_errors는 모두 빈 목록이다. 포트38000/40030 listener 없음으로 마감했다. 실행은 지정 scratchpad `run_fast.py hunt_bot_spawn_audit`, `SL_TEST_TIME_SCALE=10`, `SL_TEST_PORT_BASE=38000`에서 순차 수행했다. catalog는 `--boss-fixture --fixture-level 99 --one-group-per-epoch`, 최종 map13은 `--fixture-heal-template 279 --fixture-heal-count 250 --groups population_m6_13_63`을 추가했다. 콘솔 원문은 `runs/spawn-audit-boss-{lv99,lv99-retry,catalog,ent}-20261028.log`와 대응 clock 로그다. 데이터 전체·일반8조합 잔여·native 화면/입력·30분 직접 플레이의 미확인 범위는 이 관측으로 해제하지 않는다.

실제 실행 명령(프로젝트 루트, 세 명령은 순차 실행):

```powershell
$env:SL_TEST_TIME_SCALE='10'
$env:SL_TEST_PORT_BASE='38000'
$bossRunner='C:/Users/Chansol/AppData/Local/Temp/claude/D--claude/0483de89-75e7-4b94-84b8-fb31fe00f575/scratchpad/fastbot/run_fast.py'
python -X utf8 -B $bossRunner hunt_bot_spawn_audit --strong-fixture --fixture-level 99 --one-group-per-epoch --groups population_m1_0_16 population_m3_2_24 population_m6_11_63 population_m6_12_63 population_m6_13_63 population_m6_51_454
python -X utf8 -B $bossRunner hunt_bot_spawn_audit --boss-fixture --fixture-level 99 --one-group-per-epoch --groups population_m3_2_24 population_m6_11_63 population_m6_12_63 population_m6_13_63 population_m6_51_454
python -X utf8 -B $bossRunner hunt_bot_spawn_audit --boss-fixture --fixture-level 99 --fixture-heal-template 279 --fixture-heal-count 250 --one-group-per-epoch --groups population_m6_13_63
```

## 공식366 기준 무스폰 등록 보충 (2026-10-28)

**기존119종→277종(+158)**. 앞의87종은 과거 감사 범위이며, 착수119에는 별도 `map_expansion2_population.json`의 추가32종(물리33행)이 포함된다. 신규158종은 `data/m1/{monsters,drops}.json`에 append했고 기존 몬스터·드롭·unresolved 원행의 값·순서를 쓰기 전후 객체로 확인했다. 생산 스폰·좌표·밀도·아이템·전투·성장식·런처·프로필·ACTIVE_TASK·기존 시험을 수정하지 않았다. m1 등록표에 넣었다는 사실은 말하는 섬 출현 근거가 아니다.

원래 공식366 ID집합에서 **277/366=75.68%**, 고정client 대응343 안에서277/343=80.76%다. 미등록은 **동종 L1J 수치 근거 미확정66 + 고정client 미대응23**이다. 현재 저장 refresh는378종/미대응35종이며 추가12종 전부 미대응이다. 원래366과 현재378을 분리하며 현재378 기준 등록은73.28%다. 전체 게임 완료율은 아니다.

수치는 원래366 ID에 대해 저장 refresh 원문을 우선했다. 공식은 level·big·regionNames·reward 구성을 제공하고 HP/MP/AC/수치MR/EXP/속성/확률·수량은 제공하지 않는다. 신규level·size는 official이며 size는 고정dump f20과158/158 일치한다. 나머지 빈 수치는 선정L1J의 **local_policy**, ID·이름·SPR·명목SPR주기는 client다. 후속 약점 연결에서 `l1j_weak_attr`를 MonsterDef가 소비하도록 연결했다. m1/m3/m4/m5/m6와 catalog/map0의 기존 선정 npcID에 해당하는 SQL weakAttr 속성 셀만 보충했고, 다른 수치·스폰·식별 대응은 바꾸지 않았다. 일반 마법과 무기 발동마법의 정확 일치 ×1.2 및 검증 범위는 [ELEMENT_RESIST의 PC 공격 약점 연결](ELEMENT_RESIST.md#pc-공격의-몬스터-약점-연결-2026-10-28)을 따른다. 공식 약점이나 원본 속성·특수행동의 완료가 아니다.

대응은 token+SPR127, 동일token/SPR차이16, 이름·개별SPR·SQL/지역 검토15종이다. 후보 중 공식레벨 근접→낮은SQL ID의 LOCAL 선정이며 원변종 동일성은 UNKNOWN이다. 도펠겡어560은 SPR31의 브롭/슬라임을 제외한 이름·Lv19 대응45189, 오염된11종은 개별SPR/영문Polluted/무기형태와 SQL map244 참고를 함께 남겼다. SQL map244를 현재공식맵으로 치환하지 않았다. 미노타우르스769·에이션트자이언트12180·독침킬러비12182도 이름·SPR 대응과 SQL레벨 차이를 명시했다. 전체선정·불일치는 `m1/monsters.json#/registry_fill_20261028/mappings`다. 타락한 신규SPR·결속 던전 어둠/화염·순찰병 등 보류66종은 같은SPR의 base종 수치를 넣지 않았고, 첫부족입력은 같은 메타의 `summary.pending_monsters`다. 다음 입력은 같은종/변종 L1J ID를 입증할 이름·SPR·지역 근거 또는 독립 수치 원문이다.

공식reward→고정f21 item/grade→선정NPC 자신의 L1J droplist로 **활성610조합/100종**, **보류849**를 추가했다. 활성item source=official/roll source=local_policy이며 타NPC/등급 확률을 빌리지 않았다. 보류는 자기NPC 확률·아이템 동등성 미확정817, f21등급 부재16, ItemDef부재15, 공식목록 밖1이다. 전체 client구성2875=활성1315+미해결1560이며 활성/미해결 교집합·양쪽누락·client밖활성0이다. 공식전용/f21등급미확정16을 더한 전체미해결고유1576, append원행1677과 구분한다. 실제 획득·줍기·소비·저장 PASS는 아니다.

기존 [MapExp2 생산도구](build_map_expansion2_population.py)의 SQL/SPR/아이템 대응을 [build_monster_registry.py](build_monster_registry.py)에서 재사용했고 스폰·지형 쓰기는 실행하지 않았다. 기본 dry-run, `--apply`는 미등록만 m1 두표에 추가한다. [158종 공식 출현지역 근거](FILL_MONSTERS_POPULATION.md#공식366-추가등록의-출현지역-근거)는 regionNames·고정region 정확명 대응만 기록하며 새좌표·스폰을 만들지 않는다.

### 비소켓 로더와 후속 시험 범위

기존로더를 비소켓 호출해 신규158 전원의 HP/MP/AC/level/size/EXP/SPR/MR 실제소비·양의HP와 활성ItemDef누락0을 확인했다. 신규158의 생산spawn참조0이며 기존그룹/슬롯 증가0이다. 말미잘535/536·오염딥플라워2381의 이동0은 SQL 정지정책을 보존했다.

| 로더 | 고유 몬스터 | 기존 그룹 | target slots | 활성 드롭 |
|---|---:|---:|---:|---:|
| m1 | 177 | 45 | 116 | 745 |
| m3 | 184 | 66 | 158 | 802 |
| m4 | 215 | 138 | 250 | 977 |
| m6 | 262 | 335 | 484 | 1283 |
| m5 | 277 | 410 | 577 | 1315 |

첫 비소켓 관측은277종/406그룹/573슬롯이었다. 위 표는 문서 마감 읽기의277종/410그룹/577슬롯이며, 관측 사이 다른 작업표의4그룹 증가를 포함한다. 이 worker의 생산 스폰 변경은0이고 신규158종 참조도0이다. 두 관측을 같은 Source의 게임 PASS로 합산하지 않는다.

후속 전용worker의 대표299/459/500/504/246 봇은 [5epoch 원summary](../runs/monster-fill-3xra783p/summary.json) 모두 서버 시작 전 `EXACT_CHARACTER_CREATION_REALM_REQUIRED`로 중단됐다. 요청0/수신0/처치0, cleanup_complete=true다. `ack_enter_world.py`의 realm SHA pin과 현재파일 불일치이며 범위밖 pin/realm을 수정·우회하지 않았다. [봇로그](../runs/monster-fill-five-20261028.log)·[변경후시험로그](../runs/monster-fill-postdata-20261028.log)를 보존했다.

[game_data 시험](../runs/monster-fill-loader-postdata-20261028.log)은6/8통과,2FAIL(모든등록=스폰집합의 과거기대와 무스폰요청 충돌; HP source l1j기대 vs local_policy)이다. [defense 시험](../runs/monster-fill-defense-postdata-20261028.log)은1PASS/1FAIL(119고정기대 vs277)/4ERROR(동일pin)다. [직접전투식](../runs/monster-fill-formula-postdata-20261028.log)은5종각100스윙에서 명중91~96·양의피해794~954지만 실제처치PASS가 아니다. 기존시험은 무수정이며 실제로그인→월드→수신→처치/드롭/줍기는 OPEN이다. 이 데이터worker는 포트·봇·원본클라이언트를 실행하거나 커밋하지 않았다.
