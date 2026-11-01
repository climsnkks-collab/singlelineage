# 던전·선내 맵 확장

## 기사 지도3·237 준비와 접근 보류 (2026-10-29)

`data/m6/knight_maps.json`에 고정 자원 메타데이터와 출처 있는 LOCAL 전이4개·귀환2개를 기록했다. `world_maps.load_dungeon_policy()`는 **각 맵의 canonical S32가 있을 때만** 해당 지도·전이·귀환을 시작 시 합성한다. `world_terrain.LAZY_MAP_IDS`에는3/237만 추가했다. 현재 canonical 두 폴더가 없으므로 실제 admission은 둘 다 비활성이며 관련 전이/귀환도 로드하지 않는다. `_work`를 제품 자원 fallback으로 사용하지 않는다.

인증 provider로 원본 pack을 변경하지 않고12청크/843,912B를 `_work/knight-maps/assets/map/{3,237}`에 추출했다([원문/산출물 메타데이터](../../../_work/knight-maps/extraction.json)). 사용자 허용 출력 위치에서만 생성했으며 `work/local_resource_provider/assets/map/{3,237}`는 쓰기 범위 확장 응답 없이 수정하지 않았다.

| 경로 | 출처 | 확인 범위 / 상태 |
|---|---|---|
| map0(32510,32863) → map3(32675,32814,h0) | SQL14932 | 현 S32 양 끝 통행 가능, 말섬 귀환 지점에서 입구까지 정적 연결 |
| map3(32675,32815) → map0(32509,32865,h4) | SQL15179 | 입구→군터(32669,32788)→출구 정적 연결 |
| map13(32813,32810) → map237(32736,32807,h5) | SQL16220 | 양 끝 통행 가능. **map13 기존 입구에서 출발점까지 접근 불가** |
| map237(32736,32807) → map13(32813,32810,h2) | SQL15516 | 착지→짐(32746,32807)→출구 정적 연결 |
| map3 귀환 → map0(32574,32941,h5) | SQL18319 | 기존162 소비 제안1개 유지, 사망은 기존 대기 relocation에만 기록 |
| map237 귀환 → map4(32628,32807,h5) | SQL18552 | 위와 같은 기존 귀환 훅 사용 |

전이는 L1J 원좌표를 현 S32로 대조한 **LOCAL 정책**이며 native trigger는 UNKNOWN이다. 원문 좌표/보상을 임의 보정하지 않았다. `C_ItemUSe.java:1287–1295`의 키40555는 기사/map13/(32806,32798)–(32814,32807)에서 map13(32815,32810)으로 옮기며 그 분기에 키 차감은 없다. 키는 고정707/$2022(native dump1433)↔L1J40555/$2022(SQL17009)로 대응한다. 하지만 기존 map13 입구(32727,32725)에서 도달하는6,826칸에는 키 사용 구역이 한 칸도 없다. 키 목표에서 문까지는 연결된다. **정상 접근에 필요한 원본 이동 계약이 부족하므로 키 사용 위치/지형을 발명하지 않는다.**

새 지도 단위시험7개는 명시한 `_work` 추출 경로를 시험에서만 사용해 admission 유무/전이 훅/현재 지형/군터·짐 연결/귀환 비용 보존/정상 접근 미완을 확인했다([로그](../../../_work/knight-maps/unit-tests-final.log)). 클라이언트·소켓은 실행하지 않았다. 자원 추출/정적·단위 성공을 제품 입장·원본 화면·기사 전체 완료로 확대하지 않는다.

## 말하는 두루마리 244·777·779 연결 (2026-10-29)

현 클라이언트 S32를 기준으로 244·777·779를 기존 MapExp2 던전 정책과 lazy terrain에 등록했다. `data/m6/talkscroll_maps.json`은 맵 메타데이터만 기존 `load_dungeon_policy`에서 합성하며, 배치는 기존 `map_expansion6.json`의 `m6_talkscroll_` 그룹을 기존 던전 로더가 읽는다. 원본 두루마리 행·좌표·소비 정책과 클라이언트 자원은 변경하지 않았다.

|맵 / 원문 명칭|원본 group8 ordinal / 진입점|현 S32 청크 / 경계|LOCAL 귀환162·사망 대기 목적지|
|---|---|---|---|
|244 / 오염된 축복의 땅|102 / (32987,32811)|35 / x32640~33023,y32768~33151|4(32750,32435), SQL18559|
|777 / 버림받은 자들의 땅|133 / (32554,32952)|64 / x32512~33023,y32832~33343|4(34043,32184), SQL18639|
|779 / 버림받은 자들의 땅:심연|134 / (32554,32952)|16 / x32512~32767,y32832~33087|4(32608,33178), SQL18641|

번호·region 근거는 `work/local_resource_provider/assets/data/region.jsonc:341/408/412`의 `_map`, 원문 진입점은 `data/m2/talkscroll.json`의 위 세 행이다. 기존 `_work/talkscroll/maps-not-served.json`의 통행 관측을 재사용하고 실 S32로 다시 확인했다. 귀환은 `D:/SingleLineageRef/l1j-en-classic/db/l1jdb_m10.sql` 해당 GetBack 첫 외부 map4 좌표를 고정하는 기존 **LOCAL backend 정책**이다. 세 외부 목적지의 현 S32 통행 가능을 확인했으며 원본 랜덤·마을·클래스 규칙이나 Native 귀환과 동일하다는 뜻은 아니다.

|맵|배치 template → 기존 runtime NPC / 정확 SQL spawnlist 줄|
|---|---|
|244 / 12그룹|2381→45775/46751, 2388→45778/46755, 2389→45781/46758, 2390→45780/46757, 2391→45779/46756, 2392→45773/46749, 2394→45776/46752, 2395→45777/46753, 2397→45791/46767, 2399→45792/46768, 2400→45793/46769, 2401→45784/46760|
|777 / 5그룹|2782→46092/47362, 2783→46093/47363, 2784→46094/47364, 2785→46095/47365, 2786→46096/47366|
|779 / 0그룹|보류: 현 runtime의 공식10204~10208 매핑은 NPC46092~46096, 같은 L1J 맵 SQL47651~47653은 NPC46077/46080/46081로 다름|

각 배치는 `data/official/monsters.json` 및 `work/official_data_refresh_20261028/raw/monster/{template}.json`의 정확 지역명·현 client ID와 기존 runtime NPC를 교차 확인했다. 같은 맵·같은 선정 NPC의 원 SQL 사각형 **안**에서 원본 두루마리 진입점과 같은 현 S32 연결성분의 통행 가능한3×3을 골랐다. 원 SQL 행은 각 그룹 `l1j_spawn_reference.raw/ref`에 보존했다. 그룹당1마리·60~120초는 기존 단독 플레이 LOCAL 부분집합이고 원본 밀도·정확 생성좌표/주기의 재현이 아니다. 연결성분은244 63,920셀,777 163,740셀이다. 기존 몬스터 수치·드롭·스킬·공용 population은 변경하지 않았다. 나머지 종은 NPC 불일치·runtime 미등록·같은맵 spawnlist 부재를 보간하지 않았다.

특히 L1J `mapids` SQL19544의779는 x32832~32959,y32704~32831이고 현779의 영역과 다르다. 내부좌표·입구·스폰을 복사하지 않았다.779의 귀환은 위의 외부 map4 점을 명시적으로 선택한 LOCAL 정책에 한정한다. 계단·NPC는 세 맵 모두 추가하지 않았다.

검증은 신규5개와 기존 dungeon/maps/terrain/talkscroll 회귀를 합쳐 **48tests /24.216s OK**다. 로그는 `_work/talkscroll_maps/unit-population-regression.log`, 배치 원문은 `placement.log`, 생성 작업은 `place_maps.py`에 있다. 최초 신규4개 시험 중 귀환3건은 시험 PC 바인딩 누락으로 실패했고 `unit-first.log`를 보존했다. 실제 `bind_pc` fixture를 추가한 뒤 몹 배치 전 회귀47개도 통과했으며, 최종48개는17그룹 추가 뒤의 별도 결과다.

```powershell
$env:TMP = Join-Path $PWD '_work/tmp'
$env:TEMP = $env:TMP
$env:SL_TEST_TIME_SCALE = '10'
python -X utf8 -B -m unittest tools.local_original_session.world_dungeon_talkscroll_maps_tests tools.local_original_session.world_dungeon_maps_tests tools.local_original_session.world_talkscroll_tests tools.local_original_session.world_dungeon_terrain_tests tools.local_original_session.world_terrain_tests tools.local_original_session.world_maps_tests -v
```

새 시험은 실제 `_talkscroll_request` 디스패처·원본0960 인코딩·등록된 `realm_serves_map`·실S32를 사용해 세 목적지가 이동 제안 소비부에 도달하는지 확인한다. 단위 fixture의 relocation 함수는 메모리 위치와 응답표지만 기록한다. 실제 소켓·저장·Native 클라이언트를 실행한 결과가 아니다. 두루마리 스택 유지, 실제 일반 귀환162 효과와 던전 목적지 훅의 `consume_count=1`, 사망시 대기 귀환만 직접 확인했으며 실제 인벤토리1소비·CAS 저장·화면/입력 PASS로 확대하지 않는다.17그룹의 startup 합성·정적 통행·진입 연결성은 확인했지만 실제 생성/수신·전투·드롭·줍기는 미시험이다.

별도 단일 시험 담당이 기존 소켓 봇을 실행할 때의 한정 재현 명령은 다음과 같다. **이번 작업에서는 실행하지 않았다.** 이 봇은 원본 클라이언트 없는 서버 직접 패킷 경로이며 별도 Native 헤드리스 화면 검증을 대체하지 않는다. 출력은 기존 `_work/talkscroll/hunt-talkscroll-*`에 남고 실제 귀환162 소비 시험은 이 명령의 판정 범위가 아니다.

```powershell
$env:SL_TEST_TIME_SCALE = '10'
$env:SL_TEST_PORT_BASE = '50000'
python -X utf8 -B tools/local_original_session/run_fast.py hunt_bot_talkscroll --ordinals 102 133 134
```

변경파일은 `world_maps.py`, `world_terrain.py`, `data/m6/talkscroll_maps.json`, `data/m6/map_expansion6.json`의17그룹, `data/m6/returns.json`의3행, `world_dungeon_talkscroll_maps_tests.py`, 이 절이다. 기존 `build_map_expansion6.py`를 재실행하면 별도 추가그룹도 사라지므로 기존 상층 생성과 마찬가지로 추가분을 보존·재적용해야 한다. 이번 `place_maps.py`는 중복 배치를 막기 위해 이미 그룹이 있으면 중단한다. 게임·포트·사용자 저장·launcher·다른 기능은 실행/수정하지 않았다.

## 원본 지형 자원과 번호

현재 고정 클라이언트의 `work/local_resource_provider/assets/data/region.jsonc`가 지도 번호와 한글 명칭의 기준이다. 선내5/6은 줄11–14, 요정숲19/20/21은 줄29–34, 글루디오7–13은 줄228–241, 개미굴43–51은 줄243–260에 있다. `_id`는 region 번호이며 실제 맵은 `_map`이다. 글루디오와 요정숲은 1층부터 번호순이고, 개미굴43–50의 클라이언트 명칭은 **1층-1 … 1층-8**, 51은 **2층**이다.

L1J 참고 `D:/SingleLineageRef/l1j-en-classic/db/l1jdb_m10.sql`의 `mapids` 줄19196–19204,19210–19212,19233–19241도 이 ID 집합을 제공한다. L1J의 개미굴 층명은 클라이언트와 다르고 `area`와 `mapids`도 서로 다르므로 이름·원본 층수의 근거로 채택하지 않는다. L1J 경계도 현 클라이언트의 유효 영역으로 대체하지 않는다.

현 인증 catalog의 `dungeon/entermap/portal/stair/spawn` 이름 후보13개를 좁게 확인했다. 데이터 후보는 `imported/bin/entermaps.bin`, `data/uml/pcdungeon{,1,2,3,4}.uml`이고 나머지는 UI/이미지다. 기존 `work/all_table_semantics/travel_review/entermap-data-candidates.json`의 135항목에는 새21개 맵 목적지 후보가 0개이며 `README.md`는 실제 typed consumer를 UNKNOWN으로 남긴다. `monster/npclist/spawn` 이름의 데이터 후보는 `imported/bin/summonmonster.bin`과 `map/20001/npclists.csv`뿐이고, 대상21개 map 폴더에는 S32/SEG 이외 자원이 없었다. 이 제한된 이름·기존 디코딩 자료 확인에서 새 맵의 native 계단 trigger·서버 스폰 테이블은 확인하지 못했다. 다른 이름/서버 데이터에 없다는 뜻은 아니다.

기존 `tools/local_resource_provider/provider.py:AssetProvider.save`로 인증된 현 catalog의 해당 `map/<id>/*.s32`를 모두 추출했다. 새 자원은 **21개 맵, 232청크, 21,240,458 bytes**다. 원본 pack·원본 LC·기존 map0/1/2/4는 수정하지 않았다. 새 파일은 `work/local_resource_provider/assets/map/{5,6,7,8,9,10,11,12,13,19,20,21,43,44,45,46,47,48,49,50,51}/` 아래에 있다.

기존 provider의 catalog 서명/AEAD·해시/길이 대조·동일 기존 파일 거절 계약을 그대로 사용했다. 입력은 `work/config_startup_trial/control.snapshot.bin`(기존 provider CONTROL `9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`)와 `work/standalone_boot/current-unmodified-clone/pack`이다. 새 자원 추출 보조 파일은 `extract_dungeon_maps.py`이며 원보관 분석 프로그램을 실행하지 않는다. 다음 명령은 기존 파일이 동일하면 재사용하고 다른 내용이면 기존 provider가 거절한다.

```powershell
& 'C:/Users/Chansol/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 -B work/local_original_session/game-core-prep/extract_dungeon_maps.py
```

## S32 통행·경계

`tools/local_original_session/world_terrain.py`의 기존 `parse_s32_flags`, `(sx,sy)-0x7e00` 청크 좌표 변환, 정적 mask1 이동 판정을 그대로 사용한다. `LAZY_MAP_IDS`에 새 맵을 추가했고 parser나 판정식은 바꾸지 않았다. 실험의 시작 시 선로드는 맵 연결 소유 코드가 담당하며 요청 경로에 새 pin/해시/guard는 없다.

아래 경계는 **추출 청크들의 inclusive bounding box**다. 중간 빈 청크가 있을 수 있고 유효 바닥 전체나 공식 맵 경계가 아니다. 공통 경계 A는 `(32640,32640)–(32895,32895)`다. `can_stand`는 기존 LOCAL 정책(한 방향 이상 정적 이동 가능)이며 동적 문·점유·원본 전체 navigation을 포함하지 않는다.

| 맵 | 청크 | 청크 bbox | 실제 통행 셀 예시 |
|---|---:|---|---|
| 5 글루딘행 배 | 2 | (32640,32768)–(32767,32831) | 32723,32794 |
| 6 말하는 섬행 배 | 2 | (32704,32768)–(32831,32831) | 32750,32792 |
| 7 글루디오1층 | 12 | A | 32730,32721 |
| 8 글루디오2층 | 12 | A | 32762,32721 |
| 9 글루디오3층 | 12 | A | 32740,32722 |
| 10 글루디오4층 | 7 | (32640,32640)–(32831,32895) | 32734,32721 |
| 11 글루디오5층 | 12 | A | 32727,32721 |
| 12 글루디오6층 | 12 | A | 32722,32721 |
| 13 글루디오7층 | 12 | A | 32721,32721 |
| 19 요정숲1층 | 12 | A | 32727,32722 |
| 20 요정숲2층 | 12 | A | 32754,32723 |
| 21 요정숲3층 | 12 | A | 32724,32723 |
| 43 개미굴1층-1 | 12 | A | 32738,32726 |
| 44 개미굴1층-2 | 12 | A | 32756,32725 |
| 45 개미굴1층-3 | 12 | A | 32762,32725 |
| 46 개미굴1층-4 | 12 | A | 32739,32724 |
| 47 개미굴1층-5 | 12 | A | 32750,32725 |
| 48 개미굴1층-6 | 12 | A | 32728,32728 |
| 49 개미굴1층-7 | 11 | A | 32745,32725 |
| 50 개미굴1층-8 | 12 | A | 32746,32726 |
| 51 개미굴2층 | 18 | (32576,32704)–(32895,32959) | 32676,32730 |

21개 맵 모두 통행 셀과 정적 불통행 셀을 확인했다. 던전19개 모두 실제 동쪽 청크 경계를 넘는 통행 셀을 확인했다. 선내5/6은 두 청크가 있지만 통행 가능한 동서 청크 경계는 발견되지 않았다. bbox 바깥의 셀·이동은 UNKNOWN(None)을 유지한다.

## 지형 검증 결과

```powershell
& 'C:/Users/Chansol/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 -B -m unittest tools.local_original_session.world_dungeon_terrain_tests tools.local_original_session.world_terrain_tests
```

**12 tests OK, exit0**. 새 시험5개는 새 지형의 청크 수·bbox, 모든 맵 통행/불통행 셀, 던전 청크 경계 이동, 바깥 UNKNOWN, lazy 최초 로드·재사용·map0 보존을 확인한다. 기존 지형 시험7개도 통과했다. 기존 미지원 맵 시험의 5는 이제 지원되므로 미지원77로 바꾸었다.

이 결과는 인증 자원 추출과 기존 정적 지형 소비의 확인이다. 원본 클라이언트 실행·화면캡처·포트 시험은 수행하지 않았다. 화면·입력·계단 native trigger·선내 탑승·자동 항해·정상 로그인부터 실제 플레이의 성공은 이 지형 시험으로 입증하지 않는다.

## 실험 활성화와 서버 연결

`-MapExp 2`(`SL_EXPERIMENT_MAP=2`)에서만 새 던전 기능을 활성화한다. `world_feature_dungeons.py`를 `world_handlers.FEATURE_MODULES`에 한 줄 등록했다. 기존 맵 기능은 이동·맵 프레임·저장·시야 갱신을 계속 소유하며, 새 기능은 시작 때 지형과 `data/m6/` 정책을 읽고 추가 스폰 그룹·귀환 목적지를 설치한다. 요청 중 파일 읽기·해시·pin·새 guard는 추가하지 않았다.

기존 `TRANSITIONS` 네 행은 유지하고 추가 정책을 선택 인수로 전달한다. 새 기능 등록을 빼면 추가 맵 지원과 데이터를 설치하지 않으며 기존0/1/2/4의 기본 계약이 남는다. 기존 몬스터·드롭 정의가 중복될 때 기존 정의를 우선하며, 월드·전투·드롭 소비자는 같은 확장 데이터 객체를 쓴다. 기본 MapExp0/1/3은 추가 맵을 서비스하지 않는다.

추가 정책은 21개 맵, 전이95개, 귀환21개, 던전19개 맵의 스폰37그룹(목표74마리)이다. 선내5/6의 자원·서비스·하선 후보를 지원하지만, 기존4EF8 배표 소비 후 항구 직행 실험은 유지한다. 탑승→선내→시간표→자동 도착을 구현한 것으로 주장하지 않는다. 귀환과 사망 후 pending 복귀는 맵별 L1J GetBack 첫점을 고정한 LOCAL 정책이며, 원본의 클래스·무작위·도시 선택 규칙은 미확인이다.

`start-manual-play.ps1`의 기존 pin 목록에 이번 변경 파일은 없으므로 pin이나 스크립트를 바꾸지 않았다. 사용자 프로필·금지된 코어 파일·ACTIVE_TASK·기존 자원·저장·로그는 수정하지 않았고 git commit도 하지 않았다.

## 사냥·전이 데이터와 출처 비율

새 `data/m6/{maps,transitions,returns,monsters,spawns,drops}.json`에 원문 위치와 보정 전 값을 함께 보존했다. 기존 몬스터9종(template0/7/11/27/29/30/144/277/278)을 재사용하고, 클라이언트 identity·SPR와 공식 레벨을 대조한 156 오크(레벨2), 235 거대개미(레벨12), 236 거대병정개미(레벨20)를 추가했다. HP·MP·AC·경험치·전투 수치와 드롭 확률·수량은 출처를 명시한 L1J backend 정책이며 공식 서버값으로 확정하지 않는다.

스폰37행 중30행은 같은 맵·같은 L1J NPC의 원배치를 참고했고, 나머지7행은 공식 출현지역을 우선한 뒤 참고 범위를 골랐다. 배치 영역은 현 S32에서 통행 가능한7×7로 좁히고 각 그룹 목표를2마리로 정했다. 새 드롭은 거대개미3행·거대병정개미2행이며, 기존 지원 아이템과 공식 드롭 구성에 동시에 대응되는 것만 지급한다. 오크156을 포함한 미대응29행은 `unresolved`에 남기며 지급하지 않는다.

출처 비율은 **`{value,source,ref}` 형태의 데이터 필드463개**를 분모로 집계했다. 하나의 출처만으로 전체 기능을 확정한 비율이나 공식 재현율이 아니다.

| 출처 | 필드 | 비율 |
|---|---:|---:|
| 클라이언트 | 160 | 34.6% |
| 공식 | 43 | 9.3% |
| L1J | 109 | 23.5% |
| 로컬 정책 | 151 | 32.6% |

지형232청크와 맵 번호·명칭21행은100% 현재 클라이언트 자원이다. 혼합 출처인 전이95행과 귀환21행은 위463필드 분모에 넣지 않았다. 이116행은 모두 **L1J + 현재 S32를 적용한 LOCAL 정책**, native trigger는 UNKNOWN이다. 추가 전이 중 source 보정은 맵48의 `(32778,32802)→(32777,32802)` 한 건이고 destination 보정은 없다. 범위 밖 맵14/32/237 연계6행과 배표를 우회하는 걸음 탑승7행은 제외했다. 선내 하선은 후보만 포함하며 탑승 경로를 새로 만들지 않았다.

## 회귀와 패킷 봇의 판정 범위

`SL_TEST_PORT_BASE=18000`(물리18000/20030)에서 관련 회귀11모듈 **83 tests / 56.401s OK, exit0**. 로그는 `work/local_original_session/runs/dungeons-20261027-2011-regression.log`이다. 기존 지형·맵·M4·확장 데이터·효과/맵 계약·핸들러·스폰·통합과 새 지형/봇 경로 시험을 포함했다.

이후 `m6/monsters.json`의 비소비 `expansion_official_regions` 3행에 남아 있던 복사 메타데이터만 공식 캐시의 각 몬스터 지역 목록으로 정정했다. identity·전투·스폰·드롭 실소비 값은 바뀌지 않았다. 위83개는 정정 전 실행이고, 추가 맵 단위시험과 던전 봇은 정정 후 소스를 사용한다.

앞서 기본12000/14030에서 `world_maps_tests world_m4_tests world_handlers_tests -q`를 실행한 예비28개도 OK였으나 요청한 포트 조건의 결과로 합산하지 않았다. 해당 시험의 `runs/m4-gludin-{4i5ew7ka,p7f_7hlk,0n7g36js,zdf6m45p,j_2txwvj,iprwt9wi}` fixture와 원결과를 보존했고 정상 cleanup 후 실행 소유를 넘겼다.

신규 `hunt_bot_dungeons.py`는 기존 Matrix의 FIRST→로그인→선택→월드 진입·인벤 peer·정상 송신/저장·finally/close를 재사용한다. 각 family는 바깥 입구 인근의 별도 새 레벨6 기사 시험 저장에서 시작한다. 이는 캐릭터 생성점부터 대륙 이동 전체를 증명하지 않는다. 실제 수신한 현재 몬스터만 공격하며 입구·걷기·공격·다음 구역 계단·귀환162 소모/위치 저장을 순서대로 확인한다. 개미굴의 다음 구역은 번호 연속이 아니라 실제 선정 전이43→47이다.

재현 명령(회귀에 포함된 기존11모듈과 추가 맵 단위시험):

```powershell
$env:SL_TEST_PORT_BASE='18000'
python -X utf8 -B -m unittest tools.local_original_session.world_terrain_tests tools.local_original_session.world_maps_tests tools.local_original_session.world_m4_tests tools.local_original_session.world_expansion_data_tests tools.local_original_session.world_effect_map_contract_tests tools.local_original_session.world_handler_adapter_tests tools.local_original_session.world_handlers_tests tools.local_original_session.world_spawn_tests tools.local_original_session.world_integration_tests tools.local_original_session.world_dungeon_terrain_tests tools.local_original_session.hunt_bot_dungeons_tests tools.local_original_session.world_dungeon_maps_tests
python -X utf8 -B -m tools.local_original_session.hunt_bot_dungeons --family all
```

봇 최초 CLI 구성에는 상속 `scenario` 기본값이 빠져 포트 실행 전에 종료했다. `scenario='dungeon_items'`를 지정하고 생성자 단위시험을 추가해4개 OK로 확인했다. 원로그 `runs/dungeons-20261027-2016-bot.log`를 보존한다. 메타데이터 정정 후 추가 맵 단위시험8개는 `runs/dungeons-20261027-2016-maps-unit.log`에서 **8 tests / 0.682s OK**다.

다음 실행은 공용 마법 초기화에서 `_world_magic_consumers` 전역이 없는 `NameError`로 네 family 모두 요청0개에서 실패했다. `runs/dungeons-20261027-2018-bot.log`와 `runs/hunt-dungeons-4ueb5th3/summary.json`을 보존했고 네 건 모두 cleanup_complete=true였다. 금지된 마법 파일을 수정하거나 기능 등록을 제거하지 않았다. 이후 fresh import에서는 해당 함수가 존재함을 확인했으므로 새 프로세스의 현재 소스로 다시 실행했다. 실패 당시와 현재의 로드 내용이 달랐던 정확한 시점은 미확인이다.

### 정상 경로 결과

수정한 봇을 `--family talking_island`, `--family gludio`, `--family elven_forest`, `--family ant_cave`로 각각 새 프로세스에서 순차 실행했다. 모두 물리18000/20030을 사용했고, 시험 저장에서 정상 FIRST→로그인→선택→입구→던전 걷기→실제 수신 몬스터 처치→다음 층/구역→귀환162 소모→위치 저장→정상 정리를 확인했다. **각 행은 해당 소스·시험 저장에만 귀속된 scoped packet PASS**이며 원본 UI·입력·전체 던전 플레이 PASS로 합산하지 않는다. 각 결과의 기존 `source_sha256`에 시작 시 맵 코드·m6 JSON도 기록했다. 공용 마법 소스는 병행 작업 중 달라졌으므로 실행별 기록을 구분한다.

| family | 실제 맵 경로 | 초 / 요청 | 실제 이동 / swing / kill | 결과 |
|---|---|---:|---:|---|
| talking_island | 0→1→2→0 | 331.909 / 515 | 434 / 7 / 1 | [PASS](../runs/hunt-dungeons-vjgmbm0g/talking_island/result.json) |
| gludio | 4→7→8→4 | 119.932 / 212 | 159 / 1 / 1 | [PASS](../runs/hunt-dungeons-3l9zt1_k/gludio/result.json) |
| elven_forest | 4→19→20→4 | 100.583 / 250 | 133 / 2 / 1 | [PASS](../runs/hunt-dungeons-qhy0t2bc/elven_forest/result.json) |
| ant_cave | 4→43→47→4 | 117.509 / 266 | 98 / 42 / 1 | [PASS](../runs/hunt-dungeons-2urxqbm5/ant_cave/result.json) |

네 결과 모두 `failure=null`, `cleanup_complete=true`, 관측 handler/item 오류 없음이다. 귀환 저장은 각각 맵0 `(32578,32946)`, 맵4 `(32624,32813)`, 맵4 `(32745,32445)`, 맵4 `(32612,33188)`을 확인했다. 개미굴은 레벨6 시험 기사로 실제 물약14를53개 소모하고 HP94로 생존했다. 쉬운 임의 몬스터 추가·전투 수치/HP/RNG 변경·공속 단축은 하지 않았다. 말하는 섬은 긴 실제 미로 경로를 걸어 완료했고, 이번 요정숲 경로는 same-map maze warp를 사용하지 않아 봇 planner를 추가 수정하지 않았다.

정상 실행 로그는 `runs/dungeons-20261027-{200639-talking-island,201309-gludio,201600-elven-forest,201807-ant-cave}.log`에 있다. 원본 클라이언트는 실행하지 않았다. 추가19개 던전 맵의 전층 전투·왕복·스폰 균형·모든 계단 실제 UI 입력·맵 전환 렌더링·동적 문/점유·정확한 드롭 확률과 원본 항해 계약은 여전히 미확인이다.

### 최종 직접 영향 회귀와 소스 경계

네 경로 뒤에 현재 공용 소스의 영향 범위인 봇4개 단위시험·`world_integration_tests`·`world_spawn_tests`를 물리18000/20030에서 다시 확인했다. **29 tests / 35.570s OK, exit0**이며 로그는 `runs/dungeons-20261027-202021-final-regression.log`이다. 실행 종료 후18000/20030 listener가 없음을 시험 담당과 root가 확인했다.

```powershell
$env:SL_TEST_PORT_BASE='18000'
python -X utf8 -B -m unittest tools.local_original_session.hunt_bot_dungeons_tests tools.local_original_session.world_integration_tests tools.local_original_session.world_spawn_tests
```

각 봇의 공용 마법 소스 기록 해시는 TI `cef30067…`, GD/EFD `2fb0daab…`, Ant `8ec9abb9…`로 달랐다. TI→GD 사이에는 공용 `world_feature_pet`, `world_feature_m5`, `hunt_bot` 기록도 달랐다. 이 작업에서는 해당 파일들을 수정하지 않았다. 따라서83개 회귀·8개 맵 단위시험·29개 마감 회귀·네 봇 경로는 각각 기록된 Source/fixture 범위의 결과이며, 다른 소스의 PASS를 합산한 전체 성공이나 최종 단일 조합 네 경로 재시험으로 표시하지 않는다. 원해시와 상세 파일은 각 `result.json`의 `source_sha256`을 기준으로 한다.

## 변경 파일

- 국소 변경: `tools/local_original_session/{world_terrain.py,world_terrain_tests.py,world_maps.py,world_feature_maps.py,world_handlers.py}`. handlers는 등록 한 줄만 추가했다.
- 신규 기능·봇·시험: `tools/local_original_session/{world_feature_dungeons.py,hunt_bot_dungeons.py,hunt_bot_dungeons_tests.py,world_dungeon_maps_tests.py,world_dungeon_terrain_tests.py}`.
- 신규 데이터: `tools/local_original_session/data/m6/{maps,transitions,returns,monsters,spawns,drops}.json`.
- 자원: 위21개 `work/local_resource_provider/assets/map/<id>/`의 S32232개.
- 추출 보조·문서: `work/local_original_session/game-core-prep/{extract_dungeon_maps.py,DUNGEON_MAPS.md}`.

## 맵 확장 2차 (2026-10-28)

**현재 구현: 19맵의 지형·입구·귀환과 맵별 사례가 준비돼 있다.** 초기에는 신규5맵·map4의3지역만 사냥을 확인했으나 후속 `map_expansion2_population.json`과 대표종 사례가 용계31/32/33/35/36/37·상아탑78~82 및 화룡의 둥지를 보완했다. 상아탑75~77은 비사냥 통로다. 아래 초기 표·부족 입력·실행 결과는 당시 Source 기록으로 보존하며, 현재 완료/보류는 「2차 현재 구현·보류와 Claude 실행」을 따른다. 원본 보스·전체 종/밀도·화면/입력 완료를 뜻하지 않는다. 기존25+19=44/169와 DATA_COVERAGE_MAP의25/169는 당시 정적 서빙 snapshot이며 사냥 완료 수가 아니다.

원본 기준은 같은 `region.jsonc`의 `_map`과 이름 주석이다. 사막25~28·용계30/31/32/33/35/36/37·상아탑75~82를 기존 AssetProvider.save로 추출했다. **166청크,16,013,034 bytes**이며 원본 pack/LC/기존 자원은 수정하지 않았다. 새 파일은 `work/local_resource_provider/assets/map/<id>/*.s32`, 추출 명령은 다음과 같다.

```powershell
& 'C:/Users/Chansol/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 -B work/local_original_session/game-core-prep/extract_map_expansion2.py
```

기존 mask1 파서·청크 좌표 변환·통행 규칙을 그대로 사용한다. 아래 bbox는 추출 청크의 inclusive 외곽이며 유효 바닥 전체의 경계가 아니다. A=`(32640,32640)–(32895,32895)`, B=`(32576,32704)–(32831,32959)`, C=`(32704,32768)–(32831,32895)`.

| map | 원본 명칭 | 청크 / bbox | 실제 통행 셀 | 초기 구현 당시 전투 상태(현재는 아래 표) |
|---|---|---|---|---|
|25|사막 던전1층|12 / A|32734,32721|봇 확인|
|26|사막 던전2층|12 / A|32752,32720|봇 확인|
|27|사막 던전3층|12 / A|32756,32722|봇 확인|
|28|사막 던전4층|12 / A|32732,32722|봇 확인|
|30|용의 계곡 던전1층|12 / A|32693,32831|봇 확인|
|31|용의 계곡 던전2층|12 / A|32756,32720|몬스터 정의 부족|
|32|용의 계곡 던전3층|12 / B|32692,32784|몬스터 정의 부족|
|33|용의 계곡 던전4층|12 / B|32665,32784|몬스터 정의 부족|
|35|용의 계곡 던전5층|12 / B|32658,32784|몬스터 정의 부족|
|36|용의 계곡 던전6층|12 / B|32682,32785|몬스터 정의 부족|
|37|용의 계곡 던전7층|12 / B|32677,32784|안타라스 보스 정의/전투 미완|
|75|오렌 상아탑1층|6 / (32704,32768)–(32831,32959)|32746,32787|비사냥 통로|
|76|오렌 상아탑2층|4 / C|32750,32787|비사냥 통로|
|77|오렌 상아탑3층|4 / C|32747,32787|비사냥 통로|
|78|상아탑4층|4 / (32832,32704)–(32959,32831)|32857,32735|몬스터 정의 부족|
|79|상아탑5층|4 / C|32730,32794|몬스터 정의 부족|
|80|상아탑6층|4 / C|32739,32789|몬스터 정의 부족|
|81|상아탑7층|4 / C|32725,32788|몬스터 정의 부족|
|82|상아탑8층|4 / (32640,32768)–(32767,32895)|32659,32790|몬스터 정의 부족|

`world_dungeon_terrain_tests.py`의 기존 지형 사례에19맵의 청크 수·bbox·통행/불통행 셀·실제 동쪽 청크 경계 이동을 보탰다. bbox 밖 UNKNOWN을 유지한다. 기존 기본 지형 시험과 합쳐 **12 tests OK**이며 로그는 `runs/map-expansion2-terrain.log`다.

```powershell
$env:SL_TEST_PORT_BASE='50000'
python -X utf8 -B -m unittest tools.local_original_session.world_terrain_tests tools.local_original_session.world_dungeon_terrain_tests -q
```

데이터는 공유 스폰/몬스터/드롭 표를 수정하지 않고 `data/m6/map_expansion2.json`에 담았다. `build_map_expansion2.py`는 원본 region·현 S32·기존 공식 캐시·L1J SQL을 읽어 이 파일을 만든다. 기존 던전 기능의 시작 로더만 이 파일의 maps/transitions/returns/groups를 합성한다. MapExp0/1/3에서 설치하지 않으며 새 기능 간 호출·요청 경로 검사·pin·해시를 만들지 않았다. 기존 start-manual-play pin 목록에는 수정 코드/데이터가 없어 스크립트도 바꾸지 않았다.

추가 전이는125행, 귀환19행이다. 원문 위치·보정 전 좌표를 각 행에 남겼다. L1J 계단을 현 S32 통행 셀에 적용한 **LOCAL backend 정책**이며 native trigger는 UNKNOWN이다. 범위 밖 기존맵과 연결되는2행은 `skipped_transitions`로 보존했다. 귀환은 L1J GetBack 첫점의 기존 고정정책이며 원본 랜덤/클래스 선택은 미확인이다. 상아탑5층 등의 내부 이동도 원문 map ID를 유지한다.

새 스폰은8그룹/목표8마리다. 각 그룹은 해당 도착점과 연결된 현 S32의 통행 가능한3×3에1마리를 두는 LOCAL 단독 플레이 배치다. 원본 서버 좌표·밀도·스폰 빈도 재현으로 주장하지 않는다. 공식 지역 출현이 있는 기존 template만 골랐으며 HP/공격/경험치/드롭 수치를 바꾸지 않았다. 오크요새region110은 오크숲 안의 성곽 영역이므로 공식 오크숲 출현 종을 쓰는 명시적 LOCAL 정책이다. 윈다우드region149를 사막 전체로 표현하지 않는다.

| 그룹 대상 | template / 이름 | 기존 드롭 파일의 활성 행수 |
|---|---|---|
|map25|0 오크|m3/drops.json:7행 (기존m1을 덮는 M3)|
|map26|145 브롭|m6/drops.json:0행, 기존 빈 정책 유지|
|map27|29 해골|m3/drops.json:12행|
|map28|33 버그베어|m4/drops.json:7행|
|map30|30 스파토이|m3/drops.json:9행|
|map4 region110 오크요새|1 오크 궁수|m1/drops.json:7행|
|map4 region149 윈다우드|1 오크 궁수|m1/drops.json:7행|
|map4 region155 용의 계곡|4 난쟁이|m1/drops.json:8행|

위 행수는 이번 검토 시점의 기존 표이며 몬스터·드롭 담당자의 이후 변경은 별도다. 이 확장은 기존 정의의 우선순위를 유지하며 동일 객체를 월드/전투/보상 소비자에 전달한다. 기존 드롭 결과는 처치당 RNG이고 이번 봇은 전투→귀환을 판정하며 모든 드롭 입수의 PASS로 확대하지 않는다.

부족 입력은 `map_expansion2.json`의 `unresolved`와 `maps[].missing_templates`에 있다. 최소 정의는 용계2~4층279 트롤(또는281 무리안),5~6층284 서큐버스(또는287 에틴),7층327 안타라스, 상아탑4~5층460 미믹(또는464/735 페이퍼맨·473 리빙아머·707 아이언골렘),6~8층469 실루엣(또는579 데스·580/581 유령), 화룡의 둥지534 사라만다(또는586 라바골렘·591 파이어에그 등)다. 몬스터 표는 다른 작업자의 금지 범위이므로 새 정의/대체 몬스터를 임의로 만들지 않았다. 특히 안타라스를 약화하거나 준비 상태를 강제해 시험하지 않았다.

### 2차 봇과 판정 범위

`hunt_bot_map_expansion2.py`는 기존 Matrix/DungeonScenario의 FIRST→로그인→선택→월드 진입·실수신 인벤토리·장비·실패/부분저장·finally/Quit/close를 재사용한다. 신규5맵은 외부 또는 이전층의 실제 계단 바로 옆에서 시작하는 **새 Lv18 기사 시험 저장**이다. 장비89/104/128/129를 정상 요청으로 착용하고 실제 수신한 해당 지역 template을 공격해 사망을 관측한 뒤 귀환162 소모와 위치 저장을 확인한다. 생성점부터 대륙/던전 전체를 걸어온 결과는 아니다. 기존map4 필드는 region 경계를 실제 걸음으로 넘으며 새 map 전이를 만들지 않는다. 통로75~77은 진입→걷기→귀환만 판정한다.

공용 봇의 최종 로그인 관측이map0/1/2만 허용해 이전층27/75/76 시작3건이 최초 실패했다. 서버의4E29→4E95→4E38→self4E96 수신은 정상이고 모두 정상 정리했다. 새봇 subtype에서 그 특정 마지막 기대만 actual saved map/position·selected·HP/maxHP를 확인하도록 확장하고 정상 ALIVE를 보냈다. 공용 봇/서버 guard를 변경하거나 상태를 강제하지 않았다. 원실패는 `runs/map-expansion2-bot-all.log`, `runs/hunt-map-expansion2-dfw7kxv2/summary.json`에, 해당3건 재시험은 `runs/map-expansion2-bot-retry.log`, `runs/hunt-map-expansion2-52xpn8zx/summary.json`에 보존했다. CLI 첫 시도의 잘못된 긴 모듈명 오류도 `map-expansion2-map25-first.log`에 보존했다.

```powershell
$env:SL_TEST_TIME_SCALE='10'
$env:SL_TEST_PORT_BASE='50000'
python -X utf8 -B C:/Users/Chansol/AppData/Local/Temp/claude/D--claude/0483de89-75e7-4b94-84b8-fb31fe00f575/scratchpad/fastbot/run_fast.py hunt_bot_map_expansion2 --case all
```

실포트는50000/52030이며 원본 클라이언트는 실행하지 않았다. 원본으로 확인할 항목은 실제 화면·입력/계단 트리거·원본 몬스터 배치/밀도·지형의 동적 문/점유·공식 사냥/드롭 수치·상아탑 서비스와 보스 계약이다. 19맵의 정적 지형/서빙과11개 봇케이스를 원본 전체 플레이 완료로 확대하지 않는다.

마감 실행은 **11/11 scoped packet PASS**, 전부 `cleanup_complete=true`, 이후50000/52030 listener 없음이다. [원summary](../runs/hunt-map-expansion2-teflnpmb/summary.json), `runs/map-expansion2-bot-final.log`를 보존한다. 각 결과의 기존 `source_sha256`에는 이번 코드/확장JSON과 재사용 몬스터/드롭 입력을 시작 시 기록했고, 저장 fixture·요청/응답·서버 오류·Quit/close도 각 case에 남겼다. FAST_CLOCK 설정은scale10(가상231.783초/실제78.156초)이며 실제 관측 속도가 정확히10배였다는 뜻은 아니다.

| case / 실제 진입 | 이동 / swing / kill | 결과 범위 |
|---|---|---|
|25 / 4→25|13 / 1 / 1|입구→걷기→전투→귀환162/저장 PASS|
|26 / 4→26|47 / 3 / 1|같음|
|27 / 4→27|26 / 13 / 1|같음|
|28 / 27→28|23 / 40 / 1|같음, 이전층 입구 옆 시험저장|
|30 / 4→30|7 / 19 / 1|같음|
|75 / 4→75|2 / 0 / 0|비사냥 진입→걷기→귀환/저장 PASS|
|76 / 75→76|2 / 0 / 0|같음|
|77 / 76→77|2 / 0 / 0|같음|
|region110 / map4 오크요새 경계|10 / 2 / 1|경계 진입→걷기→전투→귀환/저장 PASS|
|region149 / map4 윈다우드 경계|13 / 2 / 1|같음, 사막 전체 확인 아님|
|region155 / map4 용의 계곡 경계|7 / 6 / 1|같음|

맵 데이터 단위시험을 포함한 첫20개에서는19개가 통과했고, 기존 드롭 출처 기대1개만 `local_policy != l1j`로 실패했다(`runs/map-expansion2-unit-initial.log`). 이는 동시 작업된 기존 드롭 표의 출처 표기이며 이번에 그 값/기대를 수정하지 않았다. 영향 없는 지형12개는 위 마감 명령에서 모두 통과했다.

비사냥/미완층을 제외한 예상 스폰 맵 집합과 기존 소유자 보존을 명시한 `world_dungeon_maps_tests.DungeonMapsTests.test_startup_adds_groups_without_replacing_live_owners` 마감1개도 OK(`runs/map-expansion2-startup-final.log`).

2차 변경 파일: `world_terrain.py`, `world_maps.py`, `world_feature_dungeons.py`, `world_terrain_tests.py`, `world_dungeon_terrain_tests.py`, `world_dungeon_maps_tests.py`, 신규 `hunt_bot_map_expansion2.py`, 신규 `data/m6/map_expansion2.json`, 신규 `extract_map_expansion2.py`·`build_map_expansion2.py`, 이 문서와 `DATA_COVERAGE_MAP.md`, 위19폴더의 신규 S32166개. 금지 프로필·ACTIVE_TASK·다른 기능/공유 몬스터/드롭/스폰 표·원본/저장·기존 로그는 수정하지 않았으며 커밋도 하지 않았다.

## 2차 현재 구현·보류와 Claude 실행 (2026-10-29)

기존 시작 로더가 19맵·125전이·19귀환과23case(던전19 + map4 지역4), 후속33종·63그룹을 이미 연결하므로 재구현하지 않았다. 아래 **준비**는 코드·자료 연결이며 이번 Source의 새 패킷 PASS가 아니다. 초기11/11과 후속12/12는 각기 기존 Source의 문서 기록으로 보존한다. 이 환경에서 후속 `hunt-map-expansion2-gzv7p3bf/summary.json`은 `PermissionError [Errno 13]`으로 읽지 못했으므로 원결과를 재검증했다고 주장하지 않는다.

귀환 A=map4(33089,33397), B=map4(33428,32815), C=map4(34053,32284), D=기존 필드 귀환map4(32624,32813)이다. 기존 L1J GetBack 첫점 + 현 S32 LOCAL 정책을 재사용한다. 입구 열은 사례 시작 전 맵이고, 정확한 좌표·원행/줄은 기존 JSON에 있다. 모든 계단 native trigger는 UNKNOWN이다.

|map / 명칭|입구|대표종 / 선택 그룹수|귀환|현재 연결·사례 / 보류|
|---|---:|---|---|---|
|25 사막1층|4|0 /1|A|준비·새 실행 대기|
|26 사막2층|4|145 /1|A|준비·새 실행 대기, 무드롭 줍기 N/A|
|27 사막3층|4|29 /1|A|준비·새 실행 대기|
|28 사막4층|27|33 /1|A|준비·새 실행 대기|
|30 용계1층|4|30 +279/288/289/290 /5|B|대표1 + 추가94목표; 아래 용계1층 보완의 scoped packet PASS|
|31 용계2층|30|288 /5|B|준비·새 실행 대기|
|32 용계3층|31|288 /6|B|준비·새 실행 대기|
|33 용계4층|32|288 /7|B|준비·새 실행 대기|
|35 용계5층|33|281 /4|B|준비·새 실행 대기|
|36 용계6층|35|287 /3|B|준비·새 실행 대기, 기존+9/열매200 fixture|
|37 용계7층|36|327 /1|B|준비·새 실행 대기, Lv99/+20/열매480 fixture; 보스 주기·기믹 보류|
|75 상아탑1층|4|없음 /0|C|비사냥 이동·귀환 준비·새 실행 대기|
|76 상아탑2층|75|없음 /0|C|비사냥 이동·귀환 준비·새 실행 대기|
|77 상아탑3층|76|없음 /0|C|비사냥 이동·귀환 준비·새 실행 대기|
|78 상아탑4층|77|464 /5|C|준비·새 실행 대기|
|79 상아탑5층|78|464 /5|C|준비·새 실행 대기|
|80 상아탑6층|79|469 /4|C|대표종 준비·새 실행 대기; 580 배치 원문 부족|
|81 상아탑7층|80|469 /4|C|대표종 준비·새 실행 대기; 580 배치 원문 부족|
|82 상아탑8층|81|469 /5|C|대표종 준비·새 실행 대기; 580/581 배치 원문·데몬 주기/기믹 보류|
|region157 화룡의 둥지(map4)|map4 경계|592 /14|D|대표종 준비·새 실행 대기; 588 배치 원문·피닉스 주기/기믹 보류|

63그룹 중 **55그룹은 같은맵 `spawnlist`, 3그룹은 같은맵 `spawnlist_boss`** 원문이 있다. 이번에 확인한 보스 원문은 `D:/SingleLineageRef/l1j-en-classic/db/l1jdb_m10.sql:47899`(map37/NPC45682/327 안타라스),`:47884`(map82/NPC45649/332 데몬),`:47875`(map4/NPC45617/590 피닉스)다. 세 그룹의 기존 `reference_spawn_rows`에 table·줄·원필드를 보완했다. LOCAL 통행3×3/1슬롯/60~120초 배치·수치는 유지했고 boss cycle/percentage/spawn_type은 원문만 보존하며 소비하지 않는다.

나머지5그룹(80/580,81/580,82/580,82/581,region157/588)은 공식 `regionNames`와 S32 연결 패치만 근거로 보존하며 정확한 L1J 배치 완료로 표시하지 않는다. 최소 부족 입력은 **같은 버전/맵/종의 배치 원문 또는 실제 서버 관측**이다. map30의 당시 `missing_templates`4종은 아래 보완에서 연결했으며 `previously_unselected_templates`에 과거 항목을 보존했다. 새 결과는 대표종30 처치와 추가4종 출현/슬롯 관측으로 구분한다. 전체33종 처치·268행 미해결 드롭·공식 확률/밀도·보스 기믹·모든 계단 왕복·원본 화면/입력은 보류다.

봇은 무드롭 대표종도 줍기를 무조건 기다리던 종료 조건을 수정했다. map26/145처럼 활성 드롭 행이 없으면 실제 수신 UID 처치를 필수로 요구하고 `NO_ACTIVE_DROP_POLICY`로 기록한 뒤 귀환한다. 드롭/줍기 PASS로 표시하지 않는다. 활성 드롭 행이 있으면 기존 ground UID→GET→인벤/저장 확인을 유지한다. 비사냥75~77 요약의 전투/줍기는 `NOT_APPLICABLE_TRANSIT`다. 제품 전투·드롭 정책은 수정하지 않았다.

Claude 실행 명령(이 worker는 봇·게임·포트 실행 안 함):

```powershell
python -X utf8 -B -m unittest tools.local_original_session.world_dungeon_maps_tests
$env:SL_EXPERIMENT_MAP='2'
$env:SL_TEST_TIME_SCALE='10'
# 기존 포트 소유 계약 확인 후 Claude만 하나씩 실행한다.
python -X utf8 -B tools/local_original_session/run_fast.py hunt_bot_map_expansion2 --case map31,map32,map33,map35,map36,map37,map78,map79,map80,map81,map82,region157
# 19맵 + 기존 map4 지역4를 모두 재현하려면 위 대신 아래를 사용한다.
python -X utf8 -B tools/local_original_session/run_fast.py hunt_bot_map_expansion2 --case all
# 단일 맵은 --case map31 등 표의 ID를 사용한다.
```

`all`은 별도 시작 저장23개이며 한 캐릭터의 전층 연속 순회가 아니다. map36/37의 유한 사전 장비/공급은 기존 fixture 그대로이며 획득·강화 성공이나 일반 Lv60 보스 사냥을 증명하지 않는다. 실행의 정확한 Source/시작 저장·FIRST/요청/응답·첫 실패/부분저장·Quit/close는 기존 봇 결과에 귀속한다. 위 단위시험 마감 결과는 **9 tests /7.441s OK, exit0**다. 기존8개와 가짜 bot의 attack 호출→kill 상태 반영→줍기 N/A 분기를 확인하는 소켓 없는 단위시험1개를 포함한다. 새 봇/게임/포트 실행 결과는 없다.

변경 파일은 `hunt_bot_map_expansion2.py`, `world_dungeon_maps_tests.py`, `data/m6/map_expansion2_population.json` 참조 메타데이터와 이 문서다. `world_feature_dungeons.py`·계단/귀환/배치 실소비 값은 기존 구현을 재사용했다. 원본·저장·성공/실패 로그·금지 기능·launcher·수동 스크립트·프로필은 수정하지 않았고 커밋하지 않았다.

## 용계1층 미선정4종 보완 (2026-10-29)

**map30에4그룹·94목표를 추가했다.** 기존 스파토이30의1그룹·1목표는 그대로여서 현재 map30은5그룹·95목표다. 다른 층의 새 종은 추가하지 않았다. 위63그룹 설명은 당시 population63그룹의 기록이며 현재 `map_expansion2_population.json`은67그룹이다. 전층·전체 종 완료 수치가 아니다.

입구는 기존 map4(33348,32347)→map30(32727,32726)이다. 네 SQL 원범위는 모두 `(32704,32704)–(32831,32831)`이다. 현재 S32의 원범위 통행셀5102개 중 이 입구에서 외부 계단을 밟지 않고 걸어 닿는 셀은1443개, 닿지 않는 셀은3659개다. 따라서 원범위 전체를 그대로 배치하지 않고 아래 **서로 겹치지 않는 LOCAL 부분 사각형**을 택했다. 사각형에는 벽이 있으나 기존 spawner의 `can_stand` 필터를 그대로 쓰며, 모든 통행셀의 입구 연결성과 충분한 수를 기존 단위시험에서 확인했다. 아래 좌표는 원본 배치 좌표·공식 밀도 재현을 주장하지 않는다.

|map / 종|SQL 줄 / NPC / 원목표|LOCAL 사각형 (양끝 포함)|통행·입구연결 셀|실행 슬롯 / 수신 live actor|
|---|---|---|---:|---|
|30 해골저격병288|46138 /45270 /24|(32744,32720)–(32767,32731)|170|24/24 ·1 UID|
|30 해골근위병290|46139 /45269 /24|(32744,32732)–(32767,32743)|168|24/24 ·2 UID|
|30 트롤279|46143 /45280 /20|(32744,32744)–(32759,32760)|178|20/20 ·1 UID|
|30 해골돌격병289|46140 /45286 /26|(32720,32745)–(32743,32760)|214|26/26 ·20 UID|

출처는 `D:/SingleLineageRef/l1j-en-classic/db/l1jdb_m10.sql`의 위4행이다. 기존 고정판 신원·종 정의·능력치·드롭은 재사용했고 각 그룹의 `reference_spawn_rows`에 같은맵 원행을 보존했다. 현 S32와 같은맵 배치 근거가 있는4종만 연결했다. 문서의 다른 명시 미선정 항목인 상아탑580/581·화둥588은 같은맵 배치 원문 부족으로 그대로 보류하며 보스 주기/기믹도 보류한다.

실행 명령(프로젝트 루트 PowerShell, 각각 Python exit0):

```powershell
$env:PYTHONIOENCODING='utf-8'
python -X utf8 -B -m unittest tools.local_original_session.world_dungeon_maps_tests
$env:SL_EXPERIMENT_MAP='2'
$env:SL_TEST_TIME_SCALE='10'
$env:SL_TEST_PORT_BASE='40400' # 실행 전40400/42430 모든 상태·listener 확인, 재시험은 TIME_WAIT도 피한다.
$env:TMP=(Resolve-Path _work/tmp).Path
$env:TEMP=$env:TMP
python -X utf8 -B tools/local_original_session/run_fast.py hunt_bot_map_expansion2 --case map30 --output-root _work/dungeon_population
```

[단위시험 원로그](../../../_work/dungeon_population/unit-final.log)는 **13 tests /21.269s OK**다. 기존 지형시험에 map30의 벽 포함 사각형을 명시하고, 추가 시험은 같은맵 원행·NPC·원목표94·원범위 내 사각형·서로/기존 대표그룹 비중첩·모든 통행셀 입구 연결성을 확인한다. 다른 검사기나 제품 guard는 추가/삭제하지 않았다.

[최종 summary](../../../_work/dungeon_population/hunt-map-expansion2-1a2317b3e590/summary.json)·[case 원결과](../../../_work/dungeon_population/hunt-map-expansion2-1a2317b3e590/map30/result.json)·[원로그](../../../_work/dungeon_population/bot-attempt4.log)는 **1/1 scoped packet PASS**,127요청·정상 이동57·처치1·줍기1·총스윙25다. 스파토이30의 실제 kill UID·드롭57아데나·GET·인벤/저장, 네 추가종의 정상 interest 활성 슬롯24/24/20/26과 수신 live actor,162귀환 map4(33428,32815)·위치 저장을 각각 확인했다. **추가4종 처치·드롭은 미시험**이며94개를 모두 클라이언트가 수신했다는 결과도 아니다. 서버실패0·failure=null·cleanup_complete=true, 이후40400/42430 listener 없음(TIME_WAIT만 잔존)이다. FAST_CLOCK scale10은 설정이며 실제 가상44.294초/실제16.098초·관측2.75배였다.

시작 저장은 기존 fresh pre-login Lv60 기사 fixture이며 사용자 저장을 수정하지 않았다. 봇은 map30에서 기존 유한 소유 물약17/296을 실제 USE로 각1개 소비하도록 했고14를6개·162를1개 소비했다. 새 보급/아이템·능력치·전투 guard·RNG 변경은 없다. 추가종은 처치 성공을 강제하지 않고 걸어 접근해 실제 수신과 기존 슬롯 상태만 읽었다. 상대 `--output-root`는 절대경로로 정규화해 기존 store 경로 guard를 지켰다. 실행 시 `source_sha256`·fixture_notes·요청/응답·저장·Quit/close는 각 case에 보존됐다. PowerShell의 정상 stderr `NativeCommandError` 표기는 FAST_CLOCK 출력 포맷이며 Python 종료값은0이다.

실패도 보존했다. [attempt1](../../../_work/dungeon_population/hunt-map-expansion2-59a7328d001a/summary.json)은46000 잔여 TIME_WAIT로 startup `WinError10048`·0요청이었다. [attempt2](../../../_work/dungeon_population/hunt-map-expansion2-c6fb204bc18a/summary.json)는 상대 출력경로가 기존 `EXPLICIT_ABSOLUTE_STORE_PATH_REQUIRED`에서 거절돼0요청이었다. [attempt3](../../../_work/dungeon_population/hunt-map-expansion2-b9fef4eab7c8/summary.json)은 최초 좁은 통행패치284셀에94목표를 몰아둔 배치에서 실제 사망(hp0/dead=true)·`use_14_quantity` 실패·71요청이었다. 세 실행 모두 cleanup_complete=true이며 원결과/부분저장을 지우거나 소급 PASS 처리하지 않았다. 최종730통행셀의 분산 배치와 실제 소유17/296 사용 후 새 실행에서 위 PASS를 얻었다.

**후속 헤드리스 원본 확인 절차(이번에는 실행하지 않음):** 시험 담당 하나가 기존 owned non-input desktop/Job 실행 경로와 별도 시험 저장을 소유한다. 시작 전 LC/포트 소유와 해당 실행의 Source를 확인하고 MAP2로 정상 로그인→선택→월드 진입 후 기존 입구로 이동한다. 메모리의 현재/대기 map·scene과 서버 Map→Status→SelfActor를 먼저 확인한 다음, 위 네 배치에 차례로 접근해 기존 `OriginalScreenshot`/`tools/local_original_session/original_screenshot.py`의 원본 PNG를 파일로 수집한다. 화면의 종별 외형·애니메이션·입력/공격·벽/문 충돌·계단 전환을 패킷 결과와 별도로 판정한다.162귀환·저장 후 원 Quit와 FIRST/close·owned 자원 정리를 확인하고 정상종료/강제정리/UNKNOWN을 구분한다. 사용자 포커스·커서·전역입력을 쓰지 않으며 PNG가 없거나 준비 판독이 실패하면 UNKNOWN이다. 이번 작업은 원본 클라이언트·화면 캡처를 실행하지 않았다.

변경 파일은 `data/m6/map_expansion2_population.json`, `data/m6/map_expansion2.json`, `hunt_bot_map_expansion2.py`, `world_dungeon_maps_tests.py`, 이 문서5개다. 필드 population·서버 runtime·원본 LC/자원·다른 층 정책·기존 사용자 저장·옛 결과는 수정하지 않았고 커밋하지 않았다.

## 기존 네 계열 전21층 순회 (2026-10-28)

**단일 새 프로세스에서 네 계열·21층 scoped packet PASS**다. 대상은 말섬1/2·글루디오7–13·요정숲19–21·개미굴43–51이다. 신규 자원21맵의 선내5/6은 사냥 던전이 아니므로 제외하고 기존 말섬1/2를 합쳐21층을 순회했다. 위 2차 확장의 사막·용계·상아탑은 이번 판정에 합산하지 않는다.

봇은 기존 방향성 계단 그래프를 따라 모든 분기를 방문하고 마지막 맵으로 돌아온다. S32 경로에 기존 같은맵 미로 전이를 연결하고 실제 Map→Status→SelfActor·도착 위치를 checks/stair_history에 기록한다. 부모의 require_reached 조회가 경로 캐시를 소모하던 문제를 수정했다. **전이·계단·귀환 자료와 제품 서버는 수정하지 않았다.** 기존 client S32 + L1J LOCAL 정책의 출처·보정 전 좌표·native_trigger_status=UNKNOWN을 재사용했으며 새 외부 출처나 임의 계단은 추가하지 않았다.

계열별 입구 바깥의 새 test_knight 저장에 FIRST 전 **Lv60/EXP416461882/maxHP1168/maxMP72**를 기존 Matrix 순수 성장 계산으로 준비했다. 성장·획득 전체 PASS는 아니다. 월드 진입 후 수신한 기존 방어구89/104/128/129를 정상0960으로 착용하고 각 층 첫 방문에서 기존17/296을 소비했다. 빨간14는 기존100개만 사용했다(글루디오99=명시USE_14 87+자동0x0960 12, 최종저장 UID65545 잔량1; 개미61·말섬/요정0 소비). 제품 몬스터·전투·HP·RNG·경험치표·속도·다른 기능·사용자 저장은 수정하지 않았다.

```powershell
python -X utf8 -B -m unittest tools.local_original_session.hunt_bot_dungeons_tests -q
$env:SL_TEST_TIME_SCALE='10'
$env:SL_TEST_PORT_BASE='44000'
$env:SL_EXPERIMENT_MAP='2'
python -X utf8 -B 'C:/Users/Chansol/AppData/Local/Temp/claude/D--claude/0483de89-75e7-4b94-84b8-fb31fe00f575/scratchpad/fastbot/run_fast.py' hunt_bot_dungeons --family all --navigation-timeout 900 --hunt-timeout 600
```

유닛6 tests OK. 최종 [원로그](../runs/dungeons-all-floors-fast10-attempt2.log)·[summary.json](../runs/hunt-dungeons-tb71ez7x/summary.json)에 정확한 시작 Source 해시·시험 저장·요청을 보존했다. FAST_CLOCK scale10/idle, 가상1713.821초·실제251.525초·관측 가속6.81배·**module exit0**이다. PowerShell `*>`가 정상 stderr의 FAST_CLOCK 줄을 NativeCommandError로 포맷해 바깥 shell은 exit1을 표시했지만 Python의 기록된 종료값은0이다.

| 계열 | 실제 맵 경로 | 가상초 / 요청 | 정상 이동 / 스윙 / 처치 | 결과 |
|---|---|---:|---:|---|
| talking_island | 0→1→2→0 | 246.623 / 570 | 534 / 8 / 2 | [PASS](../runs/hunt-dungeons-tb71ez7x/talking_island/result.json) |
| gludio | 4→7→8→9→10→11→12→13→4 | 546.838 / 1394 | 1158 / 55 / 7 | [PASS](../runs/hunt-dungeons-tb71ez7x/gludio/result.json) |
| elven_forest | 4→19→20→21→4 | 132.603 / 334 | 285 / 13 / 3 | [PASS](../runs/hunt-dungeons-tb71ez7x/elven_forest/result.json) |
| ant_cave | 4→43→47→51→48→50→45→50→48→51→49→46→49→44→49→51→4 | 787.239 / 1951 | 1567 / 146 / 9 | [PASS](../runs/hunt-dungeons-tb71ez7x/ant_cave/result.json) |

총3544회 정상 이동·21처치·4249요청이다. 각 계열 failure=null, failures/gaps/server_failures 없음, handler/item/attack/hook 오류0·사망0·cleanup_complete=true다. 글루디오 같은맵 계단은 map8에서1회·map11에서4회, 총5회 실제 소비했다. **귀환162는 각 층마다가 아니라 계열 최종 맵2/13/21/51에서 한 번씩, 총4개**를 소비했다. 아래 가족귀환 PASS는 그 최종 귀환·저장의 공통 결과이며 다음계단은 재방문을 포함한 최종 출구 관측이다.

| 계열 | 맵 | 진입 | 걷기 | 전투(처치/스윙) | 다음계단(최종 관측) | 가족귀환 |
|---|---:|---|---|---:|---|---|
| talking_island | 1 | PASS | PASS | 1/2 PASS | 2 | PASS |
| talking_island | 2 | PASS | PASS | 1/6 PASS | 최종162귀환 | PASS |
| gludio | 7 | PASS | PASS | 1/2 PASS | 8 | PASS |
| gludio | 8 | PASS | PASS | 1/7 PASS | 9 | PASS |
| gludio | 9 | PASS | PASS | 1/6 PASS | 10 | PASS |
| gludio | 10 | PASS | PASS | 1/17 PASS | 11 | PASS |
| gludio | 11 | PASS | PASS | 1/15 PASS | 12 | PASS |
| gludio | 12 | PASS | PASS | 1/5 PASS | 13 | PASS |
| gludio | 13 | PASS | PASS | 1/3 PASS | 최종162귀환 | PASS |
| elven_forest | 19 | PASS | PASS | 1/1 PASS | 20 | PASS |
| elven_forest | 20 | PASS | PASS | 1/5 PASS | 21 | PASS |
| elven_forest | 21 | PASS | PASS | 1/7 PASS | 최종162귀환 | PASS |
| ant_cave | 43 | PASS | PASS | 1/12 PASS | 47 | PASS |
| ant_cave | 44 | PASS | PASS | 1/10 PASS | 49 | PASS |
| ant_cave | 45 | PASS | PASS | 1/25 PASS | 50 | PASS |
| ant_cave | 46 | PASS | PASS | 1/11 PASS | 49 | PASS |
| ant_cave | 47 | PASS | PASS | 1/13 PASS | 51 | PASS |
| ant_cave | 48 | PASS | PASS | 1/18 PASS | 51 | PASS |
| ant_cave | 49 | PASS | PASS | 1/20 PASS | 51 | PASS |
| ant_cave | 50 | PASS | PASS | 1/11 PASS | 48 | PASS |
| ant_cave | 51 | PASS | PASS | 1/26 PASS | 최종162귀환 | PASS |

귀환/저장 좌표는 말섬 map0(32578,32946), 글루디오 map4(32624,32813), 요정숲 map4(32745,32445), 개미굴 map4(32612,33188)이다.

첫 실행 [4FAIL/정상close 결과](../runs/hunt-dungeons-bs8e_9ag/summary.json)·[원로그](../runs/dungeons-all-floors-fast10-attempt1.log)·부분 저장·소진은 보존했다. 당시 로드된 broker의 로그인026B 검증 누락과 글루디오9→10·개미50→45의 빨간100개 소진을 기록했다. broker는 이 worker가 수정하지 않았으며 새 프로세스의 기존026B 검증에서 오류0을 확인했다. 서로 다른 Source의 부분 PASS를 합산하지 않았다.

원본 클라이언트는 실행하지 않았다. native 계단 trigger·화면/입력·맵 전환 렌더링·공식 스폰/전투 균형·모든 계단 왕복은 원본 확인이 필요하다. 이번 변경은 hunt_bot_dungeons.py·hunt_bot_dungeons_tests.py·이 문서와 위 실행 출력뿐이다. 세 파일은 현재 수동 실행 스크립트의 pin 대상이 아니므로 start-manual-play.ps1·BOM·핀은 수정하지 않았고 커밋도 하지 않았다.

## 맵 확장 3차 (2026-10-28)

**신규 사냥 던전6맵과 비사냥 연결 통로1맵을 설치했다.** 기존map4에는 사냥지역6곳의 대표종 스폰과 마을6곳의 경계 이동 사례를 추가했다. 마을·통로를 사냥맵으로 세지 않는다. MAP2 런타임의 정적 지형/서빙 정의는 기존44+7=**51/169 unique client map IDs**이며 이 수치는 사냥·원본 플레이 완료율이 아니다. 모든 신규 데이터는 `data/m6/map_expansion3.json`에 분리했고 기존 몬스터·아이템·드롭·NPC 외형·M5 마을 표와 전투 수치는 수정하지 않았다.

### 2차 미완 항목의 현재 근거

위 2차 절의 “몬스터 정의 부족”은 그 당시 상태다. 다른 담당이 추가한 `map_expansion2_population.json`과 기존 봇의 최신 [12/12 summary](../runs/hunt-map-expansion2-gzv7p3bf/summary.json)를 확인해 재사용했다. 대상은 용계31/32/33/35/36/37, 상아탑78~82, 화룡의 둥지region157이다. 모두 대표종 실제 패킷 처치·드롭/줍기·귀환 저장과 정상정리까지 확인된 **각 결과의 Source/시험 저장에 귀속한 scoped PASS**이며 3차 최종 Source의 재실행 결과로 합산하지 않는다. 이 worker는 population과 2차 봇을 수정하거나 같은 시험을 반복하지 않았다.

그 시작 저장은 일반적으로 Lv60 기사지만 map36은+9 장비/열매279 200개, map37은 **Lv99/+20 일반 무기·방어구/열매279 480개**와 유한한 기존 속도 물약·용기 물약을 갖춘 별도 사전 시험 공급이다. 획득·강화 난도·일반 Lv60 안타라스 사냥·보스 기믹·전체 종/밀도는 미확인이다. 대표종 scoped packet kill의 미완이 해소됐다는 뜻이며 원본 보스 완결을 뜻하지 않는다.

### 3차 자원과 연결 정책

이름·map ID는 고정 클라이언트 `region.jsonc`의 주석/`_map`을 우선한다. 기존 `AssetProvider.save`로 신규9개 map의 S32 **94청크/9,911,412 bytes**를 물리 추출했으며 이3차에는 **7개 설치맵72청크/7,422,903 bytes**를 사용했다. 나머지72/73의22청크/2,488,509 bytes는 당시 미연결 자료로 보존했으며 아래 후속 연결에서 그대로 재사용했다. 원본 pack·LC·기존 자원은 수정하지 않았다.

| map | 고정 클라이언트 명칭 | 청크 / bbox | 대표 기존 template |
|---|---|---|---|
|23|윈다우드 성 던전1층|12 / (32640,32640)–(32895,32895)|27 좀비|
|24|윈다우드 성 던전2층|12 / 같은 bbox|64 크로울링 크로|
|29|윈다우드 내성|1 / (32704,32768)–(32767,32831)|비사냥 연결 통로|
|53|기란 던전1층|12 / (32640,32640)–(32895,32895)|28 구울|
|54|기란 던전2층|12 / 같은 bbox|28 구울|
|55|기란 던전3층|11 / (32640,32640)–(32831,32959)|115 가스트|
|56|기란 던전4층|12 / (32640,32640)–(32895,32895)|115 가스트|

bbox는 청크 외곽이며 유효 바닥 전체 경계가 아니다. 기존 S32 mask1 parser와 통행 규칙은 유지했다. `world_terrain` lazy ID에 설치7맵만 추가하고 `world_maps`의 시작 로더에 maps/transitions/returns 합성을, `world_feature_dungeons` 시작 로더에 스폰 합성 한 줄을 더했다. 같은 기존 MapExp2 던전 기능을 사용하며 새 기능 간 호출·요청 guard·pin·해시·검사기를 추가하지 않았다.

전이20행은 기존 L1J `dungeon` 원행을 현 S32에 대조한 **LOCAL backend 정책**이다. 원좌표와 원행/줄을 모두 남겼고 이번20행은 원좌표 보정0건이다. 설정 그래프에는4↔29↔23↔24와4↔53↔54↔55↔56,54 같은맵 계단이 있다. 귀환7행은 L1J `getback` 첫점 고정 정책이며 기란 귀환의 막힌 원점map4(33429,32814)은 현 S32의 가까운(33428,32815)로 보정했다. native trigger·랜덤/클래스 귀환 규칙과 모든 역방향 계단 실제 소비는 미확인이다.

스폰12그룹/목표12마리는 각 도착점과 연결된 통행 가능한3×3에1마리를 두는 기존 LOCAL 단독 플레이 정책이다. 공식 캐시 `data/official/monsters.json`의 정확한 지역명에 대응하는 기존 몬스터만 선택했다.8그룹은 같은 map+기존 L1J NPC 종의 `spawnlist` 원행/줄도 `l1j_spawn_reference`에 남겼으며, 특히map4는 그 원행이 해당 세부 region 안에 있다는 주장이 아니다. 기란4그룹은 같은map/종 L1J 스폰 원행이 없어 공식 지역 대응만 근거로 삼았다. 원본 좌표·밀도·주기와 전투/드롭 수치의 공식 확인으로 올리지 않는다.

| 기존map4 사냥 region | 이름 | 대표 template |
|---|---|---:|
|139|은기사 지역|0 오크|
|143|오크 숲|1 오크 궁수|
|151|요정 숲|0 오크|
|99|엘모어 격전지|27 좀비|
|97|오렌 설벽|708 좀비 엘모어 병사|
|96|국경 요새|708 좀비 엘모어 병사|

마을 경계 이동만 추가한 곳은136 은기사 마을,147 우드벡 마을의 첫 경계,142 화전민 마을,150 요정 숲 마을,156 웰던 마을,171 아덴 마을의 첫 경계다. 각region의 전체 영역/서비스를 모두 확인한 것이 아니며 새 map ID·NPC·상점·서비스를 만들지 않았다.

### 보류와 검증 경계

3차 당시 얼음수정72/73은 현 S32와 L1J 계단 원점/도착점이 맞지 않았다.73(32781,32735/32736),72(32872,32834/32835)의 내부계단4행 모두 가까운6셀 안에 유효 통행 셀이 없어 `NO_NEARBY_STATIC_CELL`로 보존했다. `skipped_transitions`에 원행·원문줄·실패를, `unconnected_terrain`에 추출자료를 남기고 당시 제품서빙/스폰에서 제외했다. 본토 입구/NPC 텔레포트 계약도 당시 OPEN이었고 먼 위치의 임의 계단을 만들지 않았다. 이후 현 client 명명 링크에 의한72/73 본토·내부계단 연결과 대표4case 패킷 PASS는 아래「얼음수정72/73 연결 수정」을 따른다.74와 듀펠게넌18·에바59~63·잊섬70·아덴지하수로301·몽환303은 정확한 공식 지역에 대응하는 기존 몬스터 정의가 없어 이3차 사냥 확장에서 제외했다.

기존 순수 지형·계단 회귀는 **13 tests OK**(`runs/map-expansion3-unit.stderr.log`, Python exit0)다. 새 시험 파일/검사기는 만들지 않았다. 첫 봇은 신규 별도 `craft` 기능의 `data/crafting.json` 누락으로 broker 초기화에서19건 모두 requests0/정상정리로 실패했다. [첫 결과](../runs/hunt-map-expansion3-my5s9q13/summary.json), `map-expansion3-attempt1{,.stderr}.log`를 보존했으며 해당 파일/기능을 이 worker가 고치지 않았다. 후속은 `SL_DISABLE_FEATURES=craft`로 범위 밖 기능만 제외했다.

```powershell
& 'C:/Users/Chansol/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 -B work/local_original_session/game-core-prep/extract_map_expansion3.py
python -X utf8 -B work/local_original_session/game-core-prep/build_map_expansion3.py
python -X utf8 -B -m unittest tools.local_original_session.world_terrain_tests tools.local_original_session.world_maps_tests -q
$env:SL_TEST_TIME_SCALE='10'
$env:SL_TEST_PORT_BASE='44000'
$env:SL_DISABLE_FEATURES='craft'
python -X utf8 -B 'C:/Users/Chansol/AppData/Local/Temp/claude/D--claude/0483de89-75e7-4b94-84b8-fb31fe00f575/scratchpad/fastbot/run_fast.py' hunt_bot_map_expansion3 --case all
```

첫 base43000은 실제43000/45030, 후속 base44000은 실제44000/46030이다. `test_ports`의 기존+2030 매핑은 수정하지 않았다. 새 봇은 기존 Matrix/Dungeon/MapExp2의 FIRST→정상 로그인→선택→월드·서버 발행 인벤토리·실제 이동/공격 요청·정상 Quit/EOF/close·부분 보존을 재사용한다. 시작 저장은 입구 바깥 또는 이전층의 입구 이웃에 만든 별도 새 Lv60 기사(EXP416461882/maxHP1168/maxMP72)다. 기존 일반 시작 장비·빨간14 100개 등 유한한 kit와 정상 장착89/104/128/129를 사용하며 과한 보스용 별도 강화 공급은 없다. 원래 생성점부터 온 여행이나 한 프로필로 모든 층을 연속 순회한 결과가 아니다.

이번 source 변경은 `world_terrain.py`·`world_maps.py`·`world_feature_dungeons.py`, 신규 `data/m6/map_expansion3.json`·`hunt_bot_map_expansion3.py`, `extract_map_expansion3.py`·`build_map_expansion3.py`, 두 맵 문서와 S32 자원/실행 출력이다. 기존 `manual-play/start-manual-play.ps1`의24개 pin과 변경파일의 교집합은0개여서 스크립트·BOM·pin을 바꾸지 않았다. 금지 프로필·ACTIVE_TASK·다른 기능/공유표·사용자 저장·기존 로그를 수정하지 않았고 커밋도 하지 않았다. 원본 클라이언트는 실행하지 않았으며 화면·입력·렌더링·공식 스폰/균형·동적 문/점유·성 접근권한과 보스 기믹은 원본 확인이 필요하다.

### 3차 봇 최종 결과

**19/19 scoped packet PASS**. [최종 summary](../runs/hunt-map-expansion3-tnjx1bcf/summary.json)와 각case의 `result.json`·FIRST/저장/요청/응답·부분 보존 기록, `runs/map-expansion3-final{,.stderr}.log`를 남겼다. 총810요청·156스윙·12처치다. 19건 모두 정상 로그인/선택/월드 진입→각 입구/경계 진입→걷기→해당 사냥12건의 실제 수신 대상 처치→귀환162 소비/위치 저장→정상 Quit/close 순서다. 비사냥7건에는 처치를 만들지 않았다. 드롭 RNG·줍기는 이 3차의 필수 판정이 아니며 전체 드롭 완료로 확대하지 않는다.

| case / 실제 진입 | 대표 template | 처치 / 스윙 | 귀환 저장 / 정상정리 | 결과 범위 |
|---|---:|---:|---|---|
|map23 / 29→23|27|1 /12|PASS /true|신규 사냥맵 PASS|
|map24 /23→24|64|1 /6|PASS /true|신규 사냥맵 PASS|
|map53 /4→53|28|1 /14|PASS /true|신규 사냥맵 PASS|
|map54 /53→54|28|1 /17|PASS /true|신규 사냥맵 PASS|
|map55 /54→55|115|1 /29|PASS /true|신규 사냥맵 PASS|
|map56 /55→56|115|1 /28|PASS /true|신규 사냥맵 PASS|
|region139 /은기사 지역 경계|0|1 /1|PASS /true|기존map4 사냥지역 PASS|
|region143 /오크숲 경계|1|1 /2|PASS /true|기존map4 사냥지역 PASS|
|region151 /요정숲 경계|0|1 /1|PASS /true|기존map4 사냥지역 PASS|
|region99 /엘모어 격전지 경계|27|1 /6|PASS /true|기존map4 사냥지역 PASS|
|region97 /오렌 설벽 경계|708|1 /20|PASS /true|기존map4 사냥지역 PASS|
|region96 /국경 요새 경계|708|1 /20|PASS /true|기존map4 사냥지역 PASS|
|map29 /4→29|없음|0 /0|PASS /true|비사냥 내성 통로 이동 PASS|
|region136 /은기사 마을 경계|없음|0 /0|PASS /true|비사냥 마을 이동 PASS|
|region147 /우드벡 마을 경계|없음|0 /0|PASS /true|비사냥 마을 이동 PASS|
|region142 /화전민 마을 경계|없음|0 /0|PASS /true|비사냥 마을 이동 PASS|
|region150 /요정숲 마을 경계|없음|0 /0|PASS /true|비사냥 마을 이동 PASS|
|region156 /웰던 마을 경계|없음|0 /0|PASS /true|비사냥 마을 이동 PASS|
|region171 /아덴 마을 경계|없음|0 /0|PASS /true|비사냥 마을 이동 PASS|

전부 `failure=null`, `failures=[]`, `server_failures=[]`, `cleanup_complete=true`다. 실제 포트44000/46030과 최초43000/45030에 종료 후 listener가 없음을 확인했다. 이번 런타임3코드·새봇·새JSON의 기록 해시는 각각19case에서 같은1종이며 정확한 값과 재사용 입력은 각 결과의 `source_sha256`에 있다. FIRST 이후 제품 소스 변경은 없고 문서만 마감했다. FAST_CLOCK은scale10/idle, 가상346.18초·실제182.878초·module exit0이며 실제 전체 관측이10배 가속됐다는 뜻이 아니다. 정상 stderr의 FAST_CLOCK 줄에 붙은 PowerShell `NativeCommandError` 포맷과 Python 종료값0을 구별했다.

귀환 저장은23/24/29가map4(32612,33188),53~56이map4(33428,32815),map4 지역/마을이 기존 글루딘map4(32624,32813)이다. 서로 다른 시작 fixture의 단계 PASS를 하나의 캐릭터 연속 여행이나 모든 연결 왕복의 PASS로 합산하지 않는다.

## 맵 확장 4차 (2026-10-28)

**오만의 탑 사냥4맵(102~105)과 비사냥 입구/연결1맵(101)을 설치했다. 이4차 실행 당시 얼음수정72/73 좌표 불일치는 미해결이었으며, 봇 진입·처치 완료 기준도 충족하지 않았다. 현 client 좌표에 의한 후속 연결은 아래「얼음수정72/73 연결 수정」을 따른다.** 2차 미완 사냥맵은 위3차 절에 기록된 population 담당의12/12 scoped PASS를 재사용한다. 용계·화둥·말섬·요정숲을 중복 확장하지 않았다.

### 얼음수정 선행 조사

L1J `db/l1jdb_m10.sql:15925~15926,16328~16329`, `db/archive/m9/l1jdb_m9.sql`, `db/archive/m7/update_064.sql:1045~1048`의72↔73 내부계단 원좌표는 동일하다. 현 S32에서72 원점(32872,32834)의 최근접 통행 셀은(32815,32805), Chebyshev57칸이고73 원점(32781,32735)은(32781,32789),54칸이다. 3차의6칸 이내 보정 실패를 임의 장거리 전이로 바꾸지 않았다. 레이아웃/버전 차이는 가능한 설명이며 원인 확정은 아니다.

기존 client `entermap-data-candidates.json`135행 중 map72/73/74 목적지 후보는0개였다. 4차에74 자원12청크/1,191,317 bytes도 인증 provider로 추출했으나73↔74의 L1J 계단 역시 현 S32 통행과 맞지 않았다. 당시72~74는 서빙·스폰에서 제외했고 원행13건의 보류와 자원은 `map_expansion4.json`에 그대로 보존한다. 당시 부족 입력은 **현 버전 계단 trigger/arrival와 본토 입구 또는 NPC 텔레포트 계약**이었다. 이 제한된 후보 자료의 원문 부재를 다른 자원에도 없다는 뜻으로 확대하지 않았으며, 이후 S32 명명 링크에서 확보한 좌표와 대표4case 결과는 아래 후속절에 기록했다. Native trigger 실행은 여전히 UNKNOWN이다.

### 설치한 자원·전이·출현

시작 시점(2026-10-28 14:30 KST) 등록260종의 ID·이름·레벨·L1J ID를 `registered_monster_snapshot`에 고정했고 그 뒤 추가된 종은 선정하지 않는다. 공식 캐시의2026-10-28 원문/정확한 `regionNames`와 고정 client `region.jsonc` 이름·ID를 우선했다. 신규 몬스터·드롭·NPC 외형·M5 마을·전투 표는 수정하지 않았다. 미등록 종이 선정 지역에 있으면 `unregistered_occurrence_evidence`에만 기록하며 이번 선정 지역에는0종이다.

| map | 고정 client 명칭 | 청크 / bytes | 기존 대표종 | 판정 범위 |
|---|---|---:|---|---|
|101|오만의 탑1층|9 /1,713,853|없음|입구/층간 연결만, 사냥 완료 아님|
|102|오만의 탑2층|9 /1,759,382|1025 변종 웅골리언트|사냥 준비, 패킷 검증 미완|
|103|오만의 탑3층|9 /1,583,835|891 키메라|같음|
|104|오만의 탑4층|9 /1,233,770|891 키메라|같음|
|105|오만의 탑5층|9 /1,389,136|891 키메라|같음|

설치5맵45청크/7,679,976 bytes, 미연결74를 포함한 새 물리 추출은57청크/8,871,293 bytes다.101~103 청크 bbox는(32704,32704)–(32895,32895),104~105는(32576,32768)–(32767,32959)이며 바닥 전체 경계가 아니다. MAP2 정적 서비스 정의는51+5=56/169 unique client map IDs이고 플레이 완료율이 아니다.

전이26행은 L1J `dungeon`+현재 S32의 LOCAL backend 정책이다.4↔101↔102↔103↔104↔105와 기존 원문 같은맵 계단을 연결하고, 범위 밖301/106 연결은 제외했다.103 같은맵 원점(32744,32731)은(32744,32734),101 같은맵 원점(32799,32797)은(32798,32797)로6칸 이내 보정했다. 나머지 원점·모든 도착점은 보정0건이다. 원좌표·원행/줄·`native_trigger_status=UNKNOWN`을 유지한다. 귀환5행은 기존 L1J GetBack 첫점 고정 LOCAL 정책이다.

스폰4그룹은 각 도착점에 연결된 통행3×3/목표1마리/기존 LOCAL 리스폰 정책이다. 공식은 종의 해당 층 출현만 입증하며 좌표·밀도·수치는 입증하지 않는다.4그룹 모두 같은 map/L1J NPC의 `spawnlist` 원행/줄을 별도로 보존했다.101은 정확 공식지역 대응종과 L1J 같은맵 spawnlist 행이 모두 없어 비사냥 연결로 분리했다. 에바59~61은 client 층명과 공식지역명의 동일성 근거가 부족하고63의 입구/수중 계약도 별도여서 이번에 임의 연결하지 않았다.

### 검증과 첫 실패

```powershell
& 'C:/Users/Chansol/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 -B work/local_original_session/game-core-prep/extract_map_expansion4.py
python -X utf8 -B work/local_original_session/game-core-prep/build_map_expansion4.py
python -X utf8 -B -m unittest tools.local_original_session.world_terrain_tests tools.local_original_session.world_maps_tests -q
$env:SL_TEST_TIME_SCALE='10'
$env:SL_TEST_PORT_BASE='43000' # 후속 실행44000
python -X utf8 -B 'C:/Users/Chansol/AppData/Local/Temp/claude/D--claude/0483de89-75e7-4b94-84b8-fb31fe00f575/scratchpad/fastbot/run_fast.py' hunt_bot_map_expansion4 --case all
```

기존 지형·맵 회귀 **13 tests OK /0.532s**. 새 봇은 기존3차/2차/Dungeon/Matrix의 별도 새Lv60 기사·FIRST→로그인→선택→입구→실제 수신 몬스터 처치→귀환162/저장→Quit/close 흐름을 재사용한다. 그러나 아래 두 실행은 공통 초기화에서 중단했으므로 진입·처치 PASS가 아니다.

| 실행 | 결과 | 첫 실패 | 원결과 |
|---|---|---|---|
|base43000|5FAIL, 전건requests0/cleanup true|`MAP_HOOK_FROZEN_DEPENDENCY_REQUIRED` (`local_native_login_map_notify_hook/hook.py` ACK import)|[summary](../runs/hunt-map-expansion4-o538tzzj/summary.json), `runs/map-expansion4-attempt1{,.stderr}.log`|
|base44000|5FAIL, 전건requests0/cleanup true|`FIXED_SELF_INFO_PROFILE_SOURCE_CHANGED` (`local_self_actor_profile/profile.py:109`)|[summary](../runs/hunt-map-expansion4-jfu4l001/summary.json), `runs/map-expansion4-attempt2{,.stderr}.log`|

후자는 다른 작업의hook 의존 변경을 실제 확인한 뒤 실행한 새 프로세스다. 이worker는hook·ACK·프로필·핀을 수정하지 않았으며 두 시도의 원실패·부분 출력·시작Source를 보존했다. 지정base에 대한 기존`test_ports`의 실제 포트는43000/45030,44000/46030이며 매핑을 바꾸지 않았다. 공통 프로필 계약 정합화 후 같은 새봇의5case 재실행이 필요하다.

변경 파일은`world_terrain.py`·`world_maps.py`·`world_feature_dungeons.py`의 시작 연결, 신규`data/m6/map_expansion4.json`·`hunt_bot_map_expansion4.py`·`extract_map_expansion4.py`·`build_map_expansion4.py`, 이 문서·`DATA_COVERAGE_MAP.md`, 신규S32/실행 출력이다. 기존`start-manual-play.ps1`24pin과 교집합은0건이며 스크립트·launcher·금지 프로필·ACTIVE_TASK·공유표·기존 시험 기대값을 수정하지 않았고 커밋도 하지 않았다.

이4차 worker는 원본 클라이언트를 실행하지 않았다. 화면·입력·렌더링·native 계단trigger·동적 문/점유·공식 출현밀도/전투 균형·전체 계단 왕복은 미확인이다. 당시 얼음 좌표 해결과 신규 사냥맵의 실제 패킷 진입/처치는 미완이었다. 얼음72/73 후속 좌표 연결과 대표4case의 패킷 진입 결과는 아래 절로 구별하며, 사냥 처치·전체 계단 완료로 확대하지 않는다.

## 얼음수정72/73 연결 수정 (2026-10-28)

**현 클라이언트의 S32 명명 링크 레코드로72/73 원점·도착점 불일치를 해소하고 본토 입구를 연결했다. 대표4case에서 정상 로그인→선택→월드 진입→실제 계단 이동→귀환/저장→정상 close가4/4 scoped packet PASS다. 원본 클라이언트의 trigger/화면은 UNKNOWN이다.** 위3·4차의 `NO_NEARBY_STATIC_CELL`과 원실행 결과, 각 JSON의 `skipped_transitions`/`unconnected_terrain`는 당시 실패 근거로 그대로 보존했다. 현재 런타임은 별도 [ice_cave.json](../../../tools/local_original_session/data/m6/ice_cave.json)의 현 client 좌표를 합성한다. 과거 L1J 좌표에서54~57칸 떨어진 임의 통행점을 고른 것이 아니다.

### 클라이언트 원문과 좌표 해석

기존 `tools/source_scene_assets/scene_assets.cpp:41`의 S32 순서(바닥→decoration→mask→object groups→5byte events→tile list→명명 레코드)를 재사용했다. 각 명명 레코드는 길이1byte·이름·8byte payload다. payload를 `<BBHhh`로 읽은 좌표 해석은 다음과 같다.

- 원점 `x=(chunk_sx-0x7e00)*64+origin_halfx//2`, `y=(chunk_sy-0x7e00)*64+origin_y`.
- 목적지 `map=u16`, `x=32768+signed_destination_halfx//2`, `y=32768+signed_destination_y`.
- 레코드에는 heading이 없다. 설치 heading5는 별도 LOCAL 선택이며 원본 방향으로 주장하지 않는다.

대조 사례는 map1 `7fff8001.s32` byte219784의 `to2`, raw `422d020032ff1500`이다. 해석값1(32737,32877)→2(32665,32789)가 기존 `world_maps.TRANSITIONS`와 일치한다. map2 `7ffe8000.s32` byte170399의 `to1`, raw `32140100c2ff6d00`은2(32665,32788)→1(32737,32877)이다. 출발·목적map/y는 기존 연결과 같으나 기존 L1J LOCAL 도착x32738과 client x32737은1칸 다르다. 이 차이를 숨기거나 완전 일치라고 하지 않았고 범위 밖1/2 연결은 수정하지 않았다. 이는 정적 레코드 해석의 교차 근거이며 native reader 실행을 관측한 결과는 아니다.

아래 offset은0부터 시작하는8byte payload 위치다. 각 행에 대응하는 인접 `_2`도 같은 파일에 있으며,16개 모두 JSON에 이름·offset·raw hex·정확한 좌표를 보존했다.

| 이름 / 원본 S32 | payload offset / raw hex | 원점 → 도착점 |
|---|---|---|
|out of ice lake_1 /4/80127ff9|83453 / `62114900aaff4d00`|4(33969,32337)→73(32725,32845)|
|ice dungeon 1f_in /4/80167ff6|109230 / `04364800d6ff1300`|4(34178,32182)→72(32747,32787)|
|ice dungeon 1f in_L /4/80167ff7|163232 / `4c3848005c002300`|4(34214,32248)→72(32814,32803)|
|ice dungeon exit /72/7fff8000|178313 / `56120400040bb7fd`|72(32747,32786)→4(34178,32183)|
|ice dungeon down /72/7fff8001|163931 / `2c1d4900e6ff6600`|72(32726,32861)→73(32755,32870)|
|ice exit_L /72/80008000|171383 / `5e2304004a0bf8fd`|72(32815,32803)→4(34213,32248)|
|ice dungeon up /73/7fff8001|200007 / `68264800aeff5d00`|73(32756,32870)→72(32727,32861)|
|out of ice lake_1 /73/7fff8001|200058 / `2a0d0400620951fe`|73(32725,32845)→4(33969,32337)|

각 원점과 목적지는 현 mask1 `can_stand=True`이고, 모든 원점에 적어도 하나의 실제 `can_step` 진입 방향이 있다. 좌표 보정0건이다. map72의12청크와 map73의10청크는3차 추출본을 재사용했다. `world_terrain.LAZY_MAP_IDS`에72/73, `world_maps.load_dungeon_policy`의 시작 합성에 새 JSON만 추가했고 요청시 파일 읽기·새 guard·pin·검사기를 만들지 않았다. 정적 서비스 정의는 기존56+2=58/169 unique client map IDs이며 원본 플레이 완료율이 아니다.

귀환72/73→4(34053,32284)는 L1J `getback` 원문 `l1jdb_m10.sql:18387~18388`의 첫점 고정 LOCAL 정책을 재사용했다. 현 S32에서 통행 가능하며 보정하지 않았다. 원본 랜덤/클래스 귀환 규칙은 미확인이다.

73↔74도 현재 명명 레코드가 발견됐다.73/80008000 byte188582 `ice dungeon 3f`는73(32797,32808)→74(32733,32853),74/7fff8001 byte162005 `ice dungeon 2f up`은74(32733,32852)→73(32798,32808)이다. 인접행을 포함한4개 원문은 JSON의 `unresolved`에 보존했다. 이번 지정72/73 연결 범위에는74 서빙·스폰·시험을 포함하지 않았다.

### 정적 검증과 대표4case 실제 패킷 결과

기존 `world_terrain_tests`·`world_maps_tests`는 **13 tests OK /0.580s**다. 별도 포트없는 확인에서16전이의 실제 로더 resolve·원점/도착 통행·진입방향·기존 `entrance_start`와2개 anchor BFS가 통과했다. map72 본토 도착에서 연결성분3557셀, map73 내부계단 도착에서3252셀이고 각 `local_spawn_anchors`의3×3 전9셀은 같은 성분에서 통행 가능하다. 이 rect는 스폰 담당이 원행 없는 종에 쓸 수 있는 LOCAL 후보이며 공식 좌표/밀도 근거는 아니다.

`ice_cave.json`의 `maps.hunting=false`·`representative_template=null`은 이 연결 데이터 자체가 사냥/전투를 판정하지 않았다는 표기이며 런타임이 이 필드를 소비하지 않는다. 별도 population 담당의 종/스폰 추가 및 그 결과와 구별한다. 이 worker는 `spawns*.json`·몬스터/드롭·기존 시험·프로필·launcher·수동 실행 스크립트·ACTIVE_TASK·원본 자원·사용자 저장을 수정하지 않았다. 서버·포트·봇·원본 클라이언트를 실행하지 않았고 커밋하지 않았다.

시험 담당은 `hunt_bot_ice_cave`의 데이터 선택 wrapper에서 기존 `hunt_bot_map_expansion4`의 FIRST→정상 로그인/선택/월드 진입→실제 걷기 계단→162 귀환/저장→Quit/close를 재사용했다. [대표4case summary](../runs/hunt-map-expansion4-93yo8fd6/summary.json)와 [실행 로그](../runs/population-ice-43000-20261028.log)에 **4PASS·총72요청(각18)**을 보존했다.

| case | 실제 계단 이동 | 요청 / 결과 | 귀환 저장 / 정상 close |
|---|---|---|---|
|ice_link01|4(33969,32337)→73(32725,32845)|18 / PASS|4(34053,32284) / PASS|
|ice_link03|4(34178,32182)→72(32747,32787)|18 / PASS|4(34053,32284) / PASS|
|ice_link09|72(32726,32861)→73(32755,32870)|18 / PASS|4(34053,32284) / PASS|
|ice_link13|73(32756,32870)→72(32727,32861)|18 / PASS|4(34053,32284) / PASS|

4건 모두 입구 이웃의 별도 새Lv60 기사 시작 저장에서 정상 로그인·선택·월드 진입 후 실제 이동 요청으로 계단을 건넜고 내부 걷기·162 수량10→9·귀환 위치 저장을 확인했다. `failure=null`, `failures=[]`, `server_failures=[]`, `cleanup_complete=true`이며 각 최종 epoch는 `CLOSED`·`active_tasks=0`·`registry_sessions=0`·Quit 응답 drain 완료다. 실제 포트는43000/45030, FAST_CLOCK scale10/idle·exit0이며 stderr의 PowerShell `NativeCommandError` 포맷과 Python 종료값을 구별했다. 이 결과의 Source 해시·요청·응답·시작/최종 저장은 각 case 결과에 귀속한다.

`ice_link01..16`의16전이 중 이4건만 실제 패킷으로 판정했다. 나머지12건, 사냥 처치, 하나의 캐릭터로 생성지부터 연속 여행, 모든 계단 왕복은 이 PASS에 포함하지 않는다. wrapper는 기존 parser의 `--case`와 쉼표 구분 case 선택을 그대로 사용한다. 실제 실행 로그의 선택 인수는 `ice_link03,ice_link09,ice_link13,ice_link01`이며 데이터 순서상01/03/09/13으로 실행됐다. 같은4건의 재현 명령은 다음과 같다.

```powershell
python -X utf8 -B -m unittest tools.local_original_session.world_terrain_tests tools.local_original_session.world_maps_tests -q
# 포트/실행 소유권을 가진 시험 worker만 실행. base43000의 실제 포트는43000/45030.
$env:SL_TEST_TIME_SCALE='10'
$env:SL_TEST_PORT_BASE='43000' # 재실행44000을 지정하면 실제44000/46030
python -X utf8 -B 'C:/Users/Chansol/AppData/Local/Temp/claude/D--claude/0483de89-75e7-4b94-84b8-fb31fe00f575/scratchpad/fastbot/run_fast.py' hunt_bot_ice_cave --case ice_link01,ice_link03,ice_link09,ice_link13
```

실제 패킷 계단 진입·귀환 저장은 위4case 범위에서 확인했다. 원본 클라이언트 실행, 화면·입력·렌더링·dynamic door/점유·native 명명 링크 소비와 방향은 UNKNOWN이다. 이4case 결과는 자기 Source/시작 저장에 귀속하며 기존3·4차 PASS와 합산하지 않는다.

## 맵 확장 5차 (2026-10-28)

**신규6맵의 지형·입구·귀환과 미출현33종의 출현을 연결했다.** 59/60/61/62는 비사냥 연결,63 에바왕국17종·303 몽환의 섬16종은 사냥 배치다. 신규158종 중 기존 출현40종을 제외한 실제 미출현118종을 기준으로 우선순위를 정했다. `registry_population_sources.json`의 보류120행에는 부분지역만 미완인1388/2214도 포함되므로120을 미출현 분모로 쓰지 않았다. 기존 몬스터277종·드롭·전투·경험치 표를 수정하지 않았다.

| 미출현 많은 지역 | 미출현종 | 5차 처리 / 부족 입력 |
|---|---:|---|
|잊혀진 섬 map70|26|5차는 항해 계약 부족으로 보류. 2026-10-29 원본 map83 자원·70/83 지형과 근거 있는23종 스폰을 로더에 연결했다. 항해·사냥의 실제 완료 판정은 별도(아래 잊섬 연결절)|
|에바왕국 map63|17|현 client의4→59→60→61→63 링크와 귀환을 연결하고17그룹 설치|
|오염된 축복의 땅 map244|17|S32 추출·내부 링크 보존. L1J71039 `teleport orcfcd`/10000A 원문은 있으나 현 catalog에 `orcfbuwoo1`/`orcfcd` 메뉴·액션 부재, 외부 서비스 미설치|
|몽환의 섬 map303|16|현 `phantasmisland.uml` 액션과 L1J50045 배치/1000A 정책을 기존 유료서비스 owner에 연결,16그룹 설치|

잊섬/오염의 유료·승선 계약을 무료 걷기 전이로 바꾸지 않았다. 지하수로500/501/502/505/506의 공식 명칭은 client59~62의 에바층명과 다르며, S32 링크만으로 지역 동의어를 확정하지 않았다. 이5종은 보류다. 얼음74·오만 추가층 등은 이번 우선4지역의 범위를 넓히는 구실로 추가하지 않았다.

### 잊혀진 섬 map70 스폰 연결 (2026-10-29, 항해·사냥 실동작 별도 판정)

`data/m6/forgotten_island_spawns.json`에 공식 정확 지역명·기존 선정 L1J NPC·map70 spawnlist 원행이 모두 대응하는23종을 준비했다. 공식 지역은 `work/official_data_refresh_20261028/raw/monster/<id>.json`, SQL은 `D:/SingleLineageRef/l1j-en-classic/db/l1jdb_m10.sql`이다. 각 그룹에 원행·줄번호·원문 사각형을 보존했다.754/755 라미아는 같은 NPC45387을 재사용하는 기존 두 template이므로 별도 종으로 위조한 원본 NPC 대응이 아니다. 나머지 선정은757~765,767~777,827이며 기존 몬스터·드롭·전투 정의를 변경하지 않았다.753 리자드맨(NPC45805),756 도펠갱어(81069),766 드레이크(45529)는 같은 선정NPC/map70 spawnlist 행이 없어 보류했다. 비슷한 이름의 다른 NPC를 대신 쓰지 않았다.

map70의 기존49청크를 그대로 읽었다. 각 LOCAL3×3 전9셀은 자기 NPC 원문 생성 사각형 안에서 정적 통행 가능하며 ShipInfo key4의 도착 중심70(32937,33042)에서 접근 가능하다. 기존5차 조사에서 확보한 내부 `tm1~tm4`4행도 원점·도착점·byte offset·raw hex를 그대로 보존했다. 이 링크들을 포함한 연결성분은79,270셀이다. 각 template당 목표1/60~120초 재출현은 기존 LOCAL 단독플레이 정책이며 원본 밀도·생성 좌표·주기를 재현했다는 뜻은 아니다. 반경7의 실제 무작위 도착 선택은 별도 항해 소유자가 맡는다.

항해 원조사 `c4_result.md`는 key4/배표12017/4→83(32735,32797)→70(32937,33042,7)을 정적으로 연결한다. 이후 사용자 승인으로 인증된 `AssetProvider.save`에서 map83 원본 S32 두 파일을 추출하고 `world_terrain.LAZY_MAP_IDS`에70/83만 추가했다(`_work/ship-terrain/extraction.json`). 선내83(32735,32797), 도착중심70(32937,33042), 귀환4(33426,33502)는 정적 `can_stand=True`다. 반경7 사각형은219/225칸만 통행 가능하므로 실제 도착 선택은 지형 필터가 필요하다(`_work/ship-terrain/terrain.json`).

`world_feature_dungeons` 시작 로더가 이 JSON의23그룹과 내부 `tm1~tm4` 네 링크를 기존 B2 population 합성 경로로 읽고 map70/83 서비스를 등록한다. `world_interest_spawn.py`는 수정하지 않았다. 이는 정적 로더·지형 연결이며 실제 항해 진입·NPC 처치·드롭 검증과 구별한다. 무료 외부 걷기 입구·임의 선내 지형은 추가하지 않았다.

`python -X utf8 -B -m unittest tools.local_original_session.world_forgotten_island_tests tools.local_original_session.world_dungeon_maps_tests -v`는 로더 연결 뒤 **16tests OK**다(`_work/ship-review/integration/dungeon-unit-retry.log`). 최초 통합시험은 기존 시험 fixture가 map70 지형을 로드하지 않아 1실패했고 fixture에70/83을 추가해 같은16개를 다시 통과시켰다. 정확 공식 지역/선정NPC/SQL 원행/사각형, 원본S32 raw bytes, 도착 중심에서23그룹 접근성과 실제 로더 등록을 검사했다. 재생성 스크립트와 원조사는 `_work/ship-island/build_island.py`, `survey.py`, `survey.json`에 있다. 이는 독립 데이터 시험이며 서버·포트·클라이언트·실제 패킷·처치·드롭·저장·화면/입력 확인은 실행하지 않았다.

후속 표12017 등록 뒤 개발 시험 저장에 표1장을 명시 공급한 [항해·사냥 봇](../../../_work/ship-bot/RESULT_TICKET_20261029.md)은 실제4EF8→예정83→70/표1장 소비·저장→내부 `tm1` 이동→몬스터1처치→162 귀환·map4 저장을 **11개 확인 항목/153요청 PASS**로 기록했다. 실제 이동66·공격16이고 Quit/FIRST close·listener0을 확인했다. 원본 이스발 template가 없어 자연 매표는 미시험이며, 같은 실행의 별도 보스 주기 시험사본 저장에서 `WinError 5` 한 건이 남았다. 따라서 이 범위를 오류 없는 전체 게임/저장 PASS나 Native 화면·입력 성공으로 확대하지 않는다.

### 자원·전이·귀환·배치 근거

| map / 고정 client 명칭 | 청크 / bytes | 추가종 / 그룹 / 목표 | 대표 |
|---|---:|---:|---|
|59 에바왕국 던전1층|12 /1,410,506|0 /0 /0|비사냥 통로|
|60 에바왕국 던전2층|12 /1,439,783|0 /0 /0|비사냥 통로|
|61 에바왕국 던전3층|12 /1,361,829|0 /0 /0|비사냥 통로|
|62 에바의 성지|6 /735,276|0 /0 /0|비사냥 연결|
|63 에바왕국|25 /4,249,392|17 /17 /17|535 말미잘|
|303 몽환의 섬|35 /3,601,508|16 /16 /16|10257 펑거스|

설치6맵102청크/12,798,294 bytes, 보류70/244까지 조사 추출8맵186청크/20,618,307 bytes다. 기존 인증 `AssetProvider.save`의 동일 원문 저장 계약을 재사용했다. 메뉴 조사에서25개 UML 원문을 보존했으며 런타임에 새로 연결한 메뉴는 `phantasmisland.uml` 하나다. 서버의 정적 서비스/지형 범위는64/169 unique client map IDs이며 원본 플레이 완료율이 아니다.

에바10전이는 앞 얼음 절과 같은 S32 명명 레코드 `<BBHhh` 좌표 해석이다.4↔59↔60↔61↔63 및59↔62, 보정0건이다. 모든 원점·도착점은 현 mask1 통행 가능하다. 대표 순방향은4(33627,33502)→59(32709,32789),59(32663,32867)→60(32745,32857),60(32706,32809)→61(32728,32807),61(32695,32824)→63(32806,32868),59(32747,32851)→62(32744,32838)다. 정확 이름/파일/byte offset/raw hex는 [map_expansion5.json](../../../tools/local_original_session/data/m6/map_expansion5.json)의 각 전이와 [원조사](../runs/map-expansion5-survey.json)에 있다. heading5는 LOCAL 선택이며 Native trigger 실행은 UNKNOWN이다.

몽환은 본토4(33978,32923)의 L1J50045/배치50064(`l1jdb_m10.sql:21764,48762`)를 사용한다. 현 client `data/uml/phantasmisland.uml:8`의 `phantasm-island` 액션→L1J `data/xml/NpcActions/Teleporter.xml:1047~1048`의303(32635,32817)/1000A를 연결했다. 실제 NPC identity는 미확인이며 기존 teleporter role sprite940를 LOCAL 외형으로 명시했다. NPC 클릭·현재 메뉴·소유 Adena·레벨·목적지 검사·차감/재배치/저장은 기존 town-service owner가 수행한다. 이 유료 NPC는 S32 걷기 전이가 아니다.

새 선택 기능 `world_feature_map_expansion5`는 `dungeons`가 시작 시 발행하는 `dungeon_town_setup` fold에만 등록했다. 다른 선택기능을 직접 호출하지 않으며 dungeons 또는 이 새 기능을 빼면 해당 메뉴·유료 route도 없다. 초기화에서만 데이터/서비스를 합성한다. 요청시 파일·해시·핀 읽기나 새 guard는 없다.

귀환59/60/61→4(33614,33243),62/63→4(33604,33237)는 L1J GetBack 원행18374~18378의 첫점 고정 LOCAL 정책이다.303은 GetBack 전용행이 없어 `model/Getback.java:150~155`의 기본값4(33089,33397)을 보존했다. 전부 현 S32 통행 가능·보정0이다. 원본 랜덤·클래스·수중/몽환 특수귀환 동등성을 주장하지 않는다.

공식 정확 regionNames에 대응하는33종에 각1개 LOCAL3×3/목표1/60~120초를 설치했다.3×3 전9셀은 진입 도착과 같은 정적 연결성분이며 중심 간격은5칸 이상이다. 자기종·같은맵 L1J 원행이 있는13그룹은 원행/줄을 별도로 보존했지만 선택 좌표·수·주기는 LOCAL이다. 공식 출현지역은 좌표·밀도·수치 근거가 아니다. 실제 동적 점유·전체 이동·33종 전투/드롭/줍기나 수중 호흡환경 소비는 미확인이다.

### 5차 재현 명령과 판정 경계

```powershell
& 'C:/Users/Chansol/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 -B work/local_original_session/game-core-prep/extract_map_expansion5.py
python -X utf8 -B work/local_original_session/game-core-prep/build_map_expansion5.py
python -X utf8 -B -m unittest tools.local_original_session.world_terrain_tests tools.local_original_session.world_maps_tests -q
$env:SL_TEST_TIME_SCALE='10'
$env:SL_TEST_PORT_BASE='44000' # 실제44000/46030, 실행 owner만 직렬 실행
python -X utf8 -B 'C:/Users/Chansol/AppData/Local/Temp/claude/D--claude/0483de89-75e7-4b94-84b8-fb31fe00f575/scratchpad/fastbot/run_fast.py' hunt_bot_map_expansion5 --case all --strong-fixture
```

기존 지형/맵 회귀13tests OK/1.097s. 포트 없는 실제 등록훅의 축소 조합 확인은 [feature-subsets.log](../runs/map-expansion5-feature-subsets.log)의 enabled1메뉴/1route, dungeons제외0/0, map5제외0/0으로 모두 통과했다. 전체 기능부분집합 전수시험을 새로 만들지 않았다.

이 worker는 원본 클라이언트를 실행하지 않았다. 화면·입력·렌더링·Native 계단 소비/방향·수중 피해/호흡환경·전체 맵 연속여행·모든 종 전투/드롭은 UNKNOWN이다. 금지 프로필·수동 실행 스크립트·launcher·ACTIVE_TASK·원본 자원·사용자 저장·기존 로그를 수정하지 않았으며 커밋하지 않았다. 이번 제품 변경과 수동 실행 스크립트24개 pin 대상의 교집합은0건이다.

### 5차 실제 패킷 결과와 보존한 실패

**최종 별도 조합6/6 scoped packet PASS,154요청·대표2처치/10스윙**이다. [최종 summary](../runs/hunt-map-expansion4-retnstbi/summary.json), 각case `result.json`의 정확한 Source 해시·FIRST/요청/응답/시작·최종 저장·원정리를 보존했다. 공용4차 driver를 재사용해 결과 디렉터리 접두사는 `hunt-map-expansion4-`지만 실제 모듈/데이터는5차다. [최종 로그](../runs/map-expansion5-strong-final.log)에 정확한 argv와 FAST_CLOCK/exit0이 있다.

| 최종case / 시작 조건 | 실제 진입 | 처치 / 스윙 | 요청 | 귀환 저장 / 정상 close |
|---|---|---:|---:|---|
|map59 / Lv60 일반장비|4→59|비사냥|18|4(33614,33243) / PASS|
|map60 / Lv60 일반장비|59→60|비사냥|18|같음 / PASS|
|map61 / Lv60 일반장비|60→61|비사냥|18|같음 / PASS|
|map62 / Lv60 일반장비|59→62|비사냥|18|4(33604,33237) / PASS|
|map63 / Lv60 일반장비|61→63|535 1처치 /4|45|4(33604,33237) / PASS|
|map303 / Lv60 strong 별도장비|실수신50045→현재 메뉴→1000A 차감→303|10257 1처치 /6|37|4(33089,33397) / PASS|

6case 모두 정상 FIRST→로그인→캐릭터 선택→각 입구 근처에 미리 저장된 위치의 월드 진입→실제 이동/유료메뉴→걷기→사냥case의 수신UID 공격/처치→162(10→9) 귀환/위치저장→Quit/close 순서다. 각각 별도 새 시험저장이며 생성지부터 연속여행이나10전이 전부/역방향의 PASS로 합산하지 않는다. `failure=null`, `failures=[]`, `server_failures=[]`, `cleanup_complete=true`다. 실행 뒤43000/45030/44000/46030 listener 잔여0을 확인했다. FAST_CLOCK은scale10/idle, 실41.697초·가상59.889초이며 관측 전체가10배 가속된다는 뜻이 아니다. stderr의 PowerShell `NativeCommandError` 포맷과 Python exit0을 구별했다.

`--strong-fixture`는 **303에만** 기존 population 시험과 같은 +9장검·+6방어구7부위·물약14 200개·가속17/용기296 각10의 별도 시작장비를 준다. 실제0960 장착과 소비 뒤AC-53/weapon enchant9를 확인했다. 나머지5case는 원래 일반장비다. 이 시작장비는 자연획득/강화성공이나 일반장비 몽환 생존의 증거가 아니다. 제품 몬스터·드롭·공속·전투/RNG·배치 밀도는 세 실행 사이에 바꾸지 않았다.

| 이전 실행 | 실제 결과 / 첫 실패 | 보존 원결과 |
|---|---|---|
|1차43000 일반|5PASS/1FAIL.303은 봇 전용 `saved_counts` AttributeError로 유료 전송 전 중단·정상정리|[summary](../runs/hunt-map-expansion4-x48tw0sw/summary.json), [log](../runs/map-expansion5-attempt1.log)|
|2차44000 일반|5PASS/1FAIL.303의 원메뉴·1000→0A 차감·진입저장은 PASS. 이후5스윙/0처치·실제HP0 사망, 후속 물약 요청의 `AssertionError: use_14_quantity`로 FAIL·정상정리|[summary](../runs/hunt-map-expansion4-riee2lvv/summary.json), [log](../runs/map-expansion5-attempt2.log)|

일반조건5/1을 최종 strong303 결과로 덮거나 서로 다른 Source/저장 실행의 PASS를 합산하지 않는다. 새봇 안의 누락 메서드와 명시 시작fixture만 보완했으며 제품은2차·최종 사이에 변경하지 않았다. 첫 실행 이후 dungeons를 제외하면 몽환 메뉴도 설치되지 않도록 시작 fold를 연결했고, 그 뒤 최종6case를 모두 새로 실행했다. 최종 FIRST 이후에는 문서와 보류상태 기록만 마감했다.

변경제품: `world_terrain.py`, `world_maps.py`, `world_feature_dungeons.py`, 등록1행의 `world_handlers.py`, 신규 `world_feature_map_expansion5.py`, `data/m6/map_expansion5.json`, `hunt_bot_map_expansion5.py`. 자료/기록: 신규 `extract_map_expansion5.py`·`build_map_expansion5.py`, `registry_population_sources.json`의 최신 정확ID 집합, 이 문서와 `FILL_MONSTERS_POPULATION.md`, 추출자원/새 runs 출력이다. 원문 pending120행은 역사 근거로 유지하고5차 종료 당시 미출현85종은 별도 명시집합으로 보존했다. 현재80종은 다음6차절을 따른다. pin 대상 변경파일 목록은 빈 배열이다.

## 맵 확장 6차 (2026-10-28)

**7맵의 정적 지형·전이·귀환과5종/5그룹의 지도 구현은 완료했다. 65/74의 대표처치는 실제 사망으로 미완이다.** 최초7case는5PASS/2FAIL이며 전체 완료/PASS로 표시하지 않는다. 추가 전투2case도0처치이고, 마지막 별도 귀환전용2case만2PASS다. 몬스터277종·드롭·스킬·전투·공속·경험치·기존 스폰은 바꾸지 않았다.

미출현 우선순위는5차의 정확85-ID 집합을 사용했다. 원래118-ID와 과거 pending120행(부분지역만 미완인1388/2214 포함)을 보존하고 보류 분모로 혼용하지 않았다. 신규499/710/723/972/1039를 제외한 현재80-ID는 `registry_population_sources.json#/map_expansion6/current_unspawned_template_ids`다. 신규등록158종 중 출현 배치는73→78종이다. 배치된5종의 처치 완료를 뜻하지 않는다.

| 우선지역 / 미출현종 | 6차 결과와 최소 부족입력 / 원문 |
|---|---|
|잊혀진 섬70 /26|6차 당시 외부 링크·항해 계약 부족으로 보류. 2026-10-29 사용자 지정 LOCAL 항해와 원본 map83 지형·map70/83 서비스·23종 스폰을 연결했다. 명시 표 fixture의 항해→1처치→귀환 패킷 봇은 scoped PASS; 3종 근거·이스발 원본 template/자연 매표는 보류, 같은 실행 보스주기 저장 WinError5는 별도 실패(위 잊섬 연결절)|
|오염된 축복의 땅244 /17|외부 S32 링크0. `Teleporter.xml:1107~1108`의71039/10000A 원문은 있으나 현 인증catalog에 `orcfbuwoo1`/`orcfcd` 메뉴 부재|
|버림받은 자들의 땅777 /5|외부 S32 링크0. `Teleporter.xml:1095~1096`의80048/메뉴3/Lv45~51 경로와 SQL `24313,49716`은 있으나 현 `entgate.uml` 부재|
|오만20층120 /5,15·17·18·19층 /각4,11~14층 /각3|111~120 내부 계단은 있으나 현 S32110→111 연결 없음. client15410/15430/15457 이동 주문서·부적의 item-use/획득·실소비 계약 부재(`native-dump:2165,2185,2202`). 무료계단으로 대체하지 않음|
|버림받은 땅:심연779 /5|외부 S32 링크0. L1J 내부 경로는 미서비스778에서 출발하며777로 치환할 근거 없음. 공식/고정client 명칭의 콜론 뒤 공백도 다름|
|얼음74 /3|73→74 현 명명 링크로 연결·3종 배치|
|오만10층110 /1|105→106→107→108→109→110 현 명명 링크로 연결·1종 배치|
|파푸리온65 /1|63→65 현 명명 링크로 연결·1종 배치|

아덴 대륙10종·풍룡4종·황혼2종은 이미 서비스된 map4의 좌표근거 문제이며 새 맵 순위와 구분했다. 지하수로500/501/502/505/506의 이름 대응 부족도 유지했다. 위 부족입력을 해결하려 새 승선·아이템·가짜 메뉴를 구현하지 않았다.

### 지형·명명 링크·배치

|map / 고정 client 명칭|청크 / bytes|추가종 / 그룹 / 목표|대표|
|---|---:|---:|---|
|65 파푸리온 둥지|4 /367,937|1 /1 /1|499 파푸리온|
|74 얼음 수정 동굴3층|12 /1,191,317|3 /3 /3|972 얼음 여왕의 시녀(710/723 얼음 여왕도 배치)|
|106 오만6층|6 /517,521|0 /0 /0|비사냥 경유|
|107 오만7층|9 /1,119,845|0 /0 /0|비사냥 경유|
|108 오만8층|9 /1,200,360|0 /0 /0|비사냥 경유|
|109 오만9층|9 /1,215,400|0 /0 /0|비사냥 경유|
|110 오만10층|9 /1,331,707|1 /1 /1|1039 제니스 퀸|

설치7맵58청크/6,944,087 bytes다. 조사 추출은 미설치111~120/777/779까지19맵221청크/26,894,369 bytes이며 기존 `AssetProvider.save`를 재사용했다. 미설치 자원은 서버 서비스/진입 가능으로 세지 않는다. 정적 서비스 범위는64+7=71/169 unique client map IDs이며 원본 플레이 완료율이 아니다.

28전이는 앞 얼음/5차의 S32 명명 레코드 `<BBHhh` 해석을 재사용했다. 원문 이름·파일·payload offset·raw hex와 정확 좌표는 [map_expansion6.json](../../../tools/local_original_session/data/m6/map_expansion6.json)의 `transitions`, [조사 원문](../runs/map-expansion6-survey.json)에 있다. 모든 원점·도착점은 정적 통행 가능하고 좌표 보정0이다. heading5는 LOCAL 선택이고 Native trigger/방향 소비는 미확인이다.

대표 순방향은63(32738,32674)→65(32760,32869),73(32797,32808)→74(32733,32853),105(32672,32865)→106(32742,32865),106(32784,32866)→107(32671,32859),107(32667,32934)→108(32670,32932),108(32731,32806)→109(32732,32810),109(32622,32812)→110(32754,32739)다. 별도 포트없는 BFS에서106~109의 진입 도착 성분에서 다음 층 입구의 실제 진입 방향을 확인했다. 연결성분은 각각1412/18234/16428/14092셀이다. 이는 한 캐릭터의 전층 연속여행 실행을 대체하지 않는다.

귀환65→4(33604,33237),74→4(34053,32284),106~110→4(33966,33253)는 `l1jdb_m10.sql:18380,18389,18421~18425` GetBack 첫점 고정 LOCAL 정책이다. 현 S32 통행 가능·보정0이며 원본 랜덤·클래스·수중 규칙은 미확인이다.

공식 정확 regionNames에 해당하는5종을 진입 도착과 같은 정적 연결성분의3×3에 각1개/LOCAL60~120초로 추가했다. 각3×3 전9셀 통행 가능·중심 간격5 이상이다. 공식 지역목록은 좌표·밀도·보스주기의 근거가 아니다. `world_maps`·`world_terrain`·`world_feature_dungeons`의 기존 시작 합성만 추가했고 다른 선택기능 호출·새 METHODS·요청시 파일 읽기·guard·pin은 만들지 않았다. 새 선택 모듈이나 `world_handlers.py` 변경도 없다.

### 실제 패킷 결과와 미완

제품은 첫 FIRST부터 모든 close까지 고정했다. 새봇의 fixture·대응·보고 수정은 서로 다른 실행 Source로 구분하고 기존 결과를 덮지 않았다. 전case 정상 FIRST→로그인→선택→입구 이웃의 별도 저장 위치로 월드 진입→실제 계단→내부 걷기를 통과했다. 실제 수신 UID만 공격했다.

|실행 / 시작fixture|map / 결과|요청 / 처치·스윙|귀환162·저장 / close|
|---|---|---:|---|
|[최초7case](../runs/hunt-map-expansion4-cmzjo000/summary.json),65 Lv99/+20장비/열매480|65 **FAIL 실제사망**|29 /0·3|미실행 /정상|
|같은 실행,74 Lv60/+9장검/+6방어구/물약200|74 **FAIL 실제사망**|22 /0·0|미실행 /정상|
|같은 실행,일반 Lv60|106/107/108/109 각각PASS|각18 /비사냥|4(33966,33253),10→9·저장 /정상|
|같은 실행,Lv60/+9장검/+6방어구/물약200|110 **PASS**,1039 실제처치|258 /1·70|같음 /정상|
|[추가 전투2case](../runs/hunt-map-expansion4-gq74mhb1/summary.json),별도 Lv99/+20장비/열매480·수속성/MR 장비|65 **FAIL 실제사망**|179 /0·51,열매55소비|미실행 /정상|
|같은 추가fixture|74 **FAIL 실제사망**,마지막 물약의 `use_279_quantity` 검사 실패|144 /0·10,열매99소비|미실행 /정상|
|[마지막 귀환전용](../runs/hunt-map-expansion4-0n9o2q_w/summary.json),위 별도fixture·전투 명시 생략|65/74 각각 **travel-only PASS**|각26 /0·0|65→4(33604,33237),74→4(34053,32284),각10→9·저장 /정상|

최초는5PASS/2FAIL·431요청, 추가전투0PASS/2FAIL·323요청, 귀환전용2PASS·52요청이다. 서로 다른 봇/저장 실행의 PASS를 합쳐7/7 성공으로 만들지 않는다.65/74 대표처치와5종 전체 전투는 미완이다.

추가fixture는 기존 카탈로그403 수룡 비늘 갑옷·111 마법 망토·15090 멸마 목걸이·3935 물 정령 벨트·499 수령 반지2개를 실제0960으로 착용하고,95% HP부터 실제 유한 열매279를 소비했다. 실제프로필 Lv99/AC-128/+20무기,스킬 trace의 MR77·elemental_defense0.5를 관측했다. 자연획득·강화성공·일반장비 생존이나 원본 난이도의 증거가 아니다. 최초/추가전투의 상속 check에 `level60 fixture` 설명상수가 남았으나 같은 result의 fixture_notes/실프로필은65 Lv99,추가65/74 Lv99다. 원문은 그대로 두고 새봇의 보고만 실프로필 레벨로 고쳐 마지막 귀환전용에서 확인했다.

65 추가전투 마지막 기존 스킬 이벤트는 `499:mob:3` 마법이 HP1864→0,`damage_before_mr=2610`,MR77/roll100/elemental_defense0.5였다.74는972/723/710 세종 동시수신·근접접근을 확인했고,723/710 두여왕의 실제 광역마법 누적에 열매99개를 소비한 뒤 마지막710 마법의 HP685→0을 관측했다.65/74 모두 길찾기 timeout이나 공용초기화 실패가 아니었다. 이 관측으로 전체 게임밸런스 결함이나 원본 규칙을 확정하지 않는다. 제품 밀도·몬스터·스킬·피해를 바꾸거나 더 높은 장비 실험을 이어가지 않았다.

각 실행의 정확 Source 해시·시작/최종 저장·요청/응답·실패·partial은 각 `result.json`에 귀속한다. 모든 case `server_failures=[]`,cleanup_complete=true,최종 CLOSED/active_tasks0/registry_sessions0이다. 사용 포트43000/45030·44000/46030의 listener 잔여0을 확인했다. FAST_CLOCK scale10/idle이며 최초 실40.548초/가상95.001초,재전투 실26.859초/가상82.100초,귀환 실13.384초다. PowerShell의 stderr `NativeCommandError` 표기와 봇 실제 exit(1/1/0)을 구분했다. 공용초기화 실패는 없어 해당 마지막 재시도 조건은 발생하지 않았다.

### 재현 명령·변경 파일

```powershell
& 'C:/Users/Chansol/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 -B work/local_original_session/game-core-prep/extract_map_expansion6.py
python -X utf8 -B work/local_original_session/game-core-prep/build_map_expansion6.py
python -X utf8 -B -m unittest tools.local_original_session.world_terrain_tests tools.local_original_session.world_maps_tests -q
$env:SL_TEST_TIME_SCALE='10'
$env:SL_TEST_PORT_BASE='43000'
python -X utf8 -B 'C:/Users/Chansol/AppData/Local/Temp/claude/D--claude/0483de89-75e7-4b94-84b8-fb31fe00f575/scratchpad/fastbot/run_fast.py' hunt_bot_map_expansion6 --case all --strong-fixture
$env:SL_TEST_PORT_BASE='44000'
python -X utf8 -B 'C:/Users/Chansol/AppData/Local/Temp/claude/D--claude/0483de89-75e7-4b94-84b8-fb31fe00f575/scratchpad/fastbot/run_fast.py' hunt_bot_map_expansion6 --case map65,map74 --strong-fixture --boss-retry-fixture
python -X utf8 -B 'C:/Users/Chansol/AppData/Local/Temp/claude/D--claude/0483de89-75e7-4b94-84b8-fb31fe00f575/scratchpad/fastbot/run_fast.py' hunt_bot_map_expansion6 --case map65,map74 --strong-fixture --boss-retry-fixture --travel-only
```

위 명령은 현재 새봇의 재현 명령이다. 최초 원실행은 이후 보고/재시도 옵션을 추가하기 전 Source이며 원hash는 해당result에 있다. 로그는 `runs/map-expansion6-attempt1.log`, `map-expansion6-boss-retry.log`, `map-expansion6-travel-only.log`에 보존했다. 기존 지형/맵 회귀13tests OK/0.597s다. 새 검사기나 기존 시험 기대값 수정은 없다.

변경파일은 `world_maps.py`, `world_terrain.py`, `world_feature_dungeons.py`, 신규 `hunt_bot_map_expansion6.py`·`data/m6/map_expansion6.json`, `registry_population_sources.json`의6차 메타데이터, 신규 `build_map_expansion6.py`·`extract_map_expansion6.py`, 이 문서와 `FILL_MONSTERS_POPULATION.md`, 추출자원/새 runs 출력이다. 기존 수동 실행 스크립트24개 pin 대상과의 변경 교집합은 빈 배열이다. 원본 클라이언트·사용자화면/입력·프로필·launcher·ACTIVE_TASK·사용자 저장을 실행/수정하지 않았고 커밋하지 않았다. 화면·Native 계단 소비·dynamic door/점유·수중환경·연속여행·전체 전투/드롭/줍기는 UNKNOWN이다.

## 오만 11~20층 데이터·아이템 연결 (2026-10-29)

**111~120의 기존 지형·내부계단40행·귀환10행과 정확히 대응하는13스폰 그룹을 연결했다.** 외부110→111 링크는 현 S32에 없으며 무료계단을 추가하지 않았다. 기존 `map_expansion6.json` 시작 합성과 기존 던전 로더를 그대로 사용한다. `world_terrain.LAZY_MAP_IDS`에111~120만 추가했다. 확보돼 있던83청크/12,410,293bytes를 재사용했으며 원본 자원은 수정하지 않았다. 아래는 데이터·정적 연결 판정이고 실제 클라이언트·패킷·전투 PASS가 아니다.

|map / 층|내부 전이 출발행|선정 template / 그룹수|근거·현재 상태|
|---|---:|---|---|
|111 /11층|2|없음 /0|현 S32→112. 공식3종은 있으나 같은맵·선정NPC spawnlist 대응 없음; 비사냥 연결|
|112 /12층|6|1028 사악한 미믹 /1|동일NPC45399, SQL46386;111↔112↔113|
|113 /13층|6|1028 /1|SQL46390;112↔113↔114|
|114 /14층|4|1028 /1|SQL46394;113↔114↔115|
|115 /15층|4|1027 사악한 비홀더·1028 /2|NPC45406/45399, SQL46399/46398;114↔115↔116|
|116 /16층|4|없음 /0|공식 대응종·L1J spawnlist0행; 비사냥 연결115↔116↔117|
|117 /17층|4|895 댄싱 소드·1027 /2|NPC45386/45406, SQL46403/46404;116↔117↔118|
|118 /18층|4|895·1027 /2|SQL46409/46410;117↔118↔119|
|119 /19층|4|895·1027 /2|SQL46415/46416;118↔119↔120|
|120 /20층|2|895·1027 /2|SQL46421/46422;→119.1041 시어는 같은NPC spawnlist 행이 없어 보류|

표의 SQL은 `D:/SingleLineageRef/l1j-en-classic/db/l1jdb_m10.sql` 줄이다. 원문 행·NPC·사각형은 `map_expansion6.json` 각 그룹의 `l1j_spawn_reference`에 보존했다. 공식 `raw/monster/{895,1027,1028}.json`의 정확 층명과 기존 선정 NPC가 같은 맵 spawnlist에 있는 경우만 설치했다. 원문 사각형 안에서 현재 S32의 진입 도착과 같은 연결성분에 통행 가능한3×3을 골랐고 그룹당1마리/60~120초는 기존 LOCAL 단독 플레이 정책이다. SQL 전체 밀도·원본 생성 좌표/주기를 재현했다는 뜻은 아니다.889 다이어울프의 선정NPC81229와 SQL45409,1410 서큐버스45393과 SQL45394는 서로 달라 대입하지 않았다.111의1028도 공식 출현만으로 다른층 spawnlist를 빌리지 않았다.116과 미확정종에 임의 몹을 채우지 않았다.

40개 계단은 기존 S32 named-link `<BBHhh` 해석을 재사용했고 출발·도착 좌표 보정0, 정적 통행 가능이다. 모든 층의 진입 연결성분에서 각 내부 계단의 실제 진입 방향과13개 스폰 사각형에 도달할 수 있음을 단위시험으로 확인했다. heading5는 LOCAL이며 Native trigger·화면/입력·동적 점유는 UNKNOWN이다. 귀환111~120→4(33966,33253)은 SQL18426~18435의 GetBack 첫점 고정 LOCAL 정책이고 원본 랜덤/클래스 규칙은 미확인이다.

### 오만 아이템별 용도·규칙·출처

|template / 용도|현재 적용 규칙|원문과 LOCAL 정책 경계|
|---|---|---|
|15410 /11층 이동 주문서|허용된 출발맵에서1개 소비 후111(32669,32814). 출발 정책 UNKNOWN이면 무소비 거절|identity `native-dump-v1.jsonl:2165`, 공식 `raw/item/15410.json`.1소비·escapable은 L1J `C_ItemUSe.java:1245~1254` LOCAL 참고.101~120 escapable은 SQL19289~19308; 나머지는 기존 location_allowed 사용|
|15430 /11층 이동 부적|재사용·0소비. map101 x32816~32821/y32778~32783 양끝 포함에서111(32669,32814). ANYWHERE 옵션 비활성|identity native2185·공식 `raw/item/15430.json`. 재사용·출발범위는 L1J1553~1554/4779~4789/4806~4812 LOCAL 참고. 근거 없는 레벨 제한 없음|
|15457 /봉인된11층 이동 부적|해제 조건·산출물이 미확정이어서 무소비 보류|identity native2202·공식 `raw/item/15457.json`;f4=91/f51=3007.3007을 산출 template로 해석하지 않음|

위 공식 raw 파일은 `work/official_data_refresh_20261028/raw/item/` 기준이다. L1J 파일은 `D:/SingleLineageRef/l1j-en-classic/src/l1j/server/server/clientpackets/C_ItemUSe.java`다.15410/15430 목적지111(32669,32814)는15396 기억책 group11 ordinal1(`teleport-ui-joins.json:11937`, `TALK_SCROLL_EVIDENCE.md:156`)을 **명시 LOCAL 매핑**한 값이다. 이 두 아이템과 해당 좌표를 직접 잇는 원본 계약이 확인됐다는 뜻은 아니다. 기본 요청0960·UID·child `{1:1,15:0,16:0}`는 기존 조사 `c4_result.md`와 run37/run40을 재사용한다. 아이템 담당 변경은 `data/m1/item_effects.json`, `world_item_effects.py`, `world_feature_items.py`, `world_item_effects_tests.py`다.

드롭은 변경하지 않았다.15410의10개 NPC 대응과1041→15457은 현재 `data/m1/drops.json`에서 확률·수량=null/unresolved다. 고유 같은등급 L1J 아이템 대응·자기NPC 확률/수량이 확인되지 않은 행을 활성화하지 않았다. 드롭표에 보상 이름이 있다는 사실은 실제 지급이나 자연획득의 증거가 아니다.

데이터 단위시험 `python -X utf8 -B -m unittest tools.local_original_session.world_dungeon_maps_tests -v`는 **12tests /21.271s OK**, 로그 `../_work/tower_upper/unit.log`다. 기존11개와 상층 내부 연결·정확 NPC/맵/SQL 사각형·lazy 지형·무료110→111 부재 시험1개를 포함한다. 포트·게임을 실행하지 않았다. 아이템 원시험은 신규7개 통과, 전체47개 중 기존 임시저장 fixture의 WinError5로3실패7오류였으며 전체통과로 표시하지 않는다. 별도 권한모드 실험 결과는 승인검증 PASS로 합산하지 않는다.

상층 데이터 변경파일은 `data/m6/map_expansion6.json`, `world_terrain.py`의 LAZY_MAP_IDS, `world_dungeon_maps_tests.py`, 이 절이다. 생성 작업은 `../_work/tower_upper/build_upper.py`에 보존했다. 기존 `build_map_expansion6.py`만 다시 실행하면 상층 추가분이 없어지므로 재생성할 때는 기존 생성 뒤 이 상층 생성기를 이어 실행한다. 다른 맵·몬스터/드롭 수치·공용 스폰/가시성·환경·field·m5·마법/동료·launcher·프로필·사용자 저장은 이 데이터 작업에서 수정하지 않았다. 최종 패킷/헤드리스 시험은 별도 단일 시험 담당 결과를 따른다.

헤드리스42사례의 시작 해시와 최종 메타데이터는 구별한다. 실행 시작 뒤 `map_expansion6.json#/newly_placed_ids`가 `[499,710,723,972,1039]`→`[499,710,723,895,972,1027,1028,1039]`, `#/priority[map_id=120]/pending_species`가5→3으로 정정됐다. 실행 소비값인 maps/groups/transitions/returns/cases는 불변이다. 이 메타데이터 정정으로42사례를 반복하지 않으며 결과는 실제 시작 시 기록된 Source 해시에 귀속하고 최종 파일 해시의 새 실행으로 주장하지 않는다.

### 상층 직접 패킷 실행 결과

단일 시험 담당이 물리46000/48030에서 정상 FIRST→로그인→캐릭터 선택→월드 진입 후 실제 디코더/라우터를 통과하는 순차 요청을 보냈다. Lv60 시험 저장에 아이템을 명시 공급했고 각 계단은 해당 계단 근처의 별도 시작 저장에서 실제 이동으로 밟았다.40개 방향별 계단을 한 캐릭터로11층부터20층까지 연속 여행한 결과로 해석하지 않는다. Native 클라이언트·화면·입력은 실행하지 않았다.

|실행|결과 /요청|직접 확인 범위|정리·오류|
|---|---|---|---|
|[원42사례 summary](../../../_work/tower_upper/run-c0df8889a773/summary.json)|41PASS·1FAIL /754|15410 이동·1소비와40개 내부계단 통과.15430 첫사용 뒤 수량1 유지했으나 재접속 시험 봇의 `RuntimeError: PERSIST_CLOSED`로 실패|전부 cleanup_complete=true·server_failures0|
|[수정봇15430 단독 summary](../../../_work/tower_upper/run-5a6a47a65eb2/summary.json)|1PASS /34|동일UID65572를 두 정상 로그인 epoch에서 재사용. 두 번111도착·각 saved_count1 유지·귀환 저장|cleanup_complete=true·server_failures0|

두 실행은 별개 Source·시작 저장에 귀속하며 합산42/42라고 표시하지 않는다. 원42사례의 `hunt_bot_tower_upper.py` 시작해시는 `2b0731f0…`, `map_expansion6.json`은 `6970804b…`이고 단독재시도는 각각 `ba5f672d…`, `e0a152c9…`다. 전체 값은 각 결과의 `source_sha256`에 있다. 부적 두사용 사이에는 원 시험 저장의 위치만 map101 허용 사각형으로 준비하는 명시 fixture가 들어갔고 같은 부적UID/수량은 유지했다. 정상 게임에서 해당 출발점으로 실제 귀환한 결과가 아니다.

`PERSIST_CLOSED`의 원인은 정상 Quit으로 닫힌 broker positions wrapper를 시험 봇이 재사용한 것이었다. 수정봇은 Quit 뒤 동일 파일에 새 `movement.PositionStore` 인스턴스를 열어 기존 CAS로 다음 epoch의 위치 fixture를 갱신했다. 제품의 저장/소유권 guard를 제거하지 않았다. 원실패는 보존했고 실패한15430만 단독 재시도했다. 오케스트레이터가112~115/117~120의 runtime/수신 actor 관측 존재,111/116의 actor 부재를 확인했다. 이는13그룹 전체의 처치·드롭 확인을 뜻하지 않는다. 마감 때46000/48030 listener 잔여0도 확인했다.

실행·재현 명령(프로젝트 루트 PowerShell):

```powershell
$env:TMP = Join-Path $PWD '_work/tmp'
$env:TEMP = $env:TMP
$env:SL_TEST_PORT_BASE = '46000'
$env:SL_TEST_TIME_SCALE = '10'
python -X utf8 -B tools/local_original_session/run_fast.py hunt_bot_tower_upper --output-root _work/tower_upper
python -X utf8 -B tools/local_original_session/run_fast.py hunt_bot_tower_upper --output-root _work/tower_upper --case amulet15430_reuse
```

임시저장 권한 오류 때 허용된 전체 아이템 단위시험의 재시도 원명령은 아래와 같다. 이 절은 앞서 보존한 원47개 결과와 별도 권한모드 실험을 전체통과로 바꾸지 않는다. TMP/TEMP 재지정 후에도 같은 오류가 남으면 추가 우회 없이 해당 오류·명령을 보류로 남긴다.

```powershell
$env:TMP = Join-Path $PWD '_work/tmp'
$env:TEMP = $env:TMP
python -X utf8 -B -m unittest tools.local_original_session.world_item_effects_tests
```

원본 직접목적지·자연획득/봉인해제·미배치종·111/116사냥·13그룹 실제 전투/드롭/줍기·전체탑 연속여행·Native계단 트리거/렌더링/동적 점유는 여전히 보류 또는 UNKNOWN이다.

## MapExp2 map36 지연·map37 사망 조사 (2026-10-29)

원실행 `hunt-map-expansion2-avsr35zl`의 읽을 수 있는 사본은 `../_work/b1b_runs/`다. map35는 59.174초/171요청/무리안1처치49스윙/물약14 36회, map36은 1651.895초/3505요청/에틴11처치292스윙/회복0회, map37은 18.891초/52요청/안타라스0처치4스윙/회복0회였다. map36 requests.jsonl 줄36~86은 첫 에틴 공격9.44~23.85초이고 다음 에틴 공격은 줄387의175.45초다. 자연 드롭이 나올 때까지 같은1슬롯의 시체50초+재출현60~120초를 반복 대기한 것이 map36 지연 원인이다. L1J npc45373은 레벨35/HP500/AC-22/STR20이고 기존 피해11~45와 맞는다(SQL20963; L1Attack.java943~947). 활성 드롭은 보장되지 않는다. L1J droplist7257의 보장 아데나는 현 native 대응 활성표에 없어 이 조사에서 추가하지 않았다.

map37 NPC327은 안타라스1마리이며 HP22200/AC-99/STR80은 L1J SQL21238과 같다. L1J레벨90 대신 현 공식93을 소비하는 기존 정책의 물리피해41~133, 현 클라이언트 action속도500ms는 유지한다. L1J npc atkspeed2240ms와 현 클라이언트 action속도는 다른 기준이며 동일값으로 주장하지 않는다. 명중식은 L1Attack.java659~680의 level/d20와 음수AC의 무작위 방어에 대응한다. L1J mobskill20240의 이럽션은 leverage200(×20),20242의 skill10054는 leverage50(×5), skills35942는250+12d10/INT18이어서 속성저항0·MR실패 기준 단발 상한2890이다(L1Magic.java418,659~688,755~758). 시작HP1926/+20방어구도 이 단발사를 막지 못한다. 기존 봇은 HP60% 미만에서만 회복하며 위험 귀환이 없었다. map37 requests.jsonl 줄9~14는 장신구4회·속도2회뿐이고 회복279요청은0회다. 정확한 사망 스킬과 직전HP 시계열은 원로그에 없어 미확인이다.

세 맵의 vitals.json/positions.json은 종료시 저장 스냅샷이다. map35/36은4(33428,32815),HP712/1145이고 map37도 같은 마을/HP1926으로 정리됐다. map37 result.json의 마지막 관측은 map37/HP0/실제사망이므로 정리 후 vitals의 HP1926을 생존으로 해석하지 않는다. 서버 피해·명중·밀도·어그로를 바꿀 근거는 확인하지 못했고 제품 데이터/계산은 변경하지 않았다. L1J는 LOCAL backend 참고이며 공식Classic 원본수치 동등성의 증거가 아니다.

봇 수정은 map36 첫 실제 처치 뒤 자연 수신 loot가 있으면 기존 GET/저장검증을 하고, 없으면 `NO_DROP_OBSERVED`로 종료해 재출현 농사를 하지 않는다. 받은 loot의 줍기가 거부되면 실패를 유지한다. map37은 수신한 살아있는 안타라스 actor와 현재HP/단발 위험 근거를 기록하고 실제 귀환162/위치저장/생존만 시험한다. 전투·드롭 결과는 `NOT_ATTEMPTED_DANGER_RETURN`이며 보스 처치 성공으로 표시하지 않는다. map36/37의 일반 회복 기준은80%로 올렸고 소유 유한279의 정상 요청·소비를 유지한다. 새 `--output-root`는 기본runs를 유지하며 필요시 `_work`를 지정한다. Windows Python3.13 mkdtemp mode0700의 읽기 거부를 피하려고 출력 폴더만 UUID+Path.mkdir로 부모ACL을 상속한다. 기존 출력은 재사용/덮어쓰기하지 않는다.

검증: `python -X utf8 -B -m unittest tools.local_original_session.world_dungeon_maps_tests` 최초 **11tests OK**. map36의 무드롭 첫 처치 종료/map37의 수신 보스 위험 판정과 처치 미주장 검사를 포함한다. 마감 시 같은 시험 재실행은 **11tests 중2FAIL**이었다. 병행 작업의 map0 배치가 72그룹/2315에서91/2732로 바뀌면서 기존 시험 줄86의 고정 수량과 줄159의 전셀 통행 기대가 실패했다. map0 데이터나 그 기대값을 이 작업에서 바꾸지 않았다. 두 신규 봇 시험은 통과했다.

봇 첫 시도는 `_work/hunt-map-expansion2-2ysr8r7w/map36` 생성 전 WinError5였고, 출력 생성 수정 뒤 `_work/hunt-map-expansion2-5c3c56f984f3`는 읽기 가능하지만 두case 모두 requests0/WinError10048로 시작 실패했다. 12000/14030은 PID11632 python이 LISTEN 중이고 14030에 PID8532 LC.guard.exe가 ESTABLISHED임을 netstat/Get-Process로 확인했다. 다른 활성 클라이언트 세션과 시험을 겹치지 않으므로 종료/새 포트 우회/추가 봇 실행은 하지 않았다. **수정 봇의 map36 시간 개선·map37 생존 귀환은 실행 미확인**이다. 기존 클라이언트/서버가 정상 종료된 뒤 같은 명령에 `--output-root work/local_original_session/_work`를 붙여 두 맵을 재시험해야 한다.



## 던전 L1J 밀도 적용 (2026-10-30)

**사용자의 후속 승인으로799그룹·8086목표를 제품 `data/m6/dungeon_population.json`과 기존 던전 로더에 적용했다.** 기존 중단 판정의10~15ms는150ms tick 대비 허용됐으며, 현재 제외 기준은 **tick 최대50ms 초과 시 그 맵만 제외**다. 측정한5맵은 모두50ms 이하이므로 제외맵은 없다. 나머지맵까지 부하를 측정했다고 주장하지 않는다. 고정 L1J `D:/SingleLineageRef/l1j-en-classic/db/l1jdb_m10.sql`의 spawnlist를 활성 던전 정책86맵(기존 M3 map1/2 및 island policy70/83 포함)에 대조했다. map0/4 필드는 제외했다. 원문1051행·11444목표 중 런타임의 정확한 `MonsterDef.l1j_npcid`가 있는799행·8086목표를 후보로 만들었고, 정의 없는252행·85종·3358목표는 unresolved로 보존했다. 다른 NPC로 대체하지 않았다. 후보는 기존 LOCAL 부분집합839목표를 대체하는 값으로, 기존 부분집합에 더해 중복 합산한 값이 아니다. SQL행이 없거나 같은 NPC가 미정의인 맵은 후보0으로 표시했다.

적용 원문·맵별 집계·신원 선택·unresolved 전체(이름/NPC ID/맵/count/SQL원문): [`data/m6/dungeon_population.json`](../../../tools/local_original_session/data/m6/dungeon_population.json). 이전 미적용 후보는 `_work/tmp/dungeon_population/dungeon_population.json`에 그대로 보존했다. 같은 NPC에 여러 template이 있으면 기존 같은맵 배치를 우선하고, 없으면 현재 런타임 정의 순서의 대표를 사용했다. 이는 정확한 원본 template 선택의 증명이 아니다. 능력치·드롭 정의는 바꾸지 않았다.

B2의 기존 `_work/tmp/build_field_population_20261029.py` SQL 파서와 rectangle 변환을 재사용했다. area 상한은 SQL상한−1, random support는 loc±(random−1), 원좌표와 fallback은 원문 그대로다. 막힌/UNKNOWN칸은 보정하거나 강제 배치하지 않으며 기존8회추첨·5초retry·점유/통행 조건을 그대로 소비한다. B2처럼 일반 random support는 uniform이고 젖소만 triangular인 기존 제한, spawn_home/near_spawn/mobgroup 등 미복원 경계도 그대로다. 원본 Classic 서버 동등성이나 화면·입력 PASS로 해석하지 않는다.

### 맵별 이전 → 적용됨 목표

모든 값은 interest 활성 여부와 별개인 목표 슬롯 수다. 실제 생존 개체 수를 뜻하지 않는다. unresolved 열은 정확한 L1J NPC ID이며 이름과 원문은 위 JSON에 있다.

|맵|이전|적용됨|unresolved 목표 / NPC ID|
|---|---:|---:|---|
|1|17|166|6 / 45100, 70981, 70983|
|2|25|205|0 / 없음|
|3|0|0|0 / 없음|
|5|0|0|0 / 없음|
|6|0|0|0 / 없음|
|7|10|166|0 / 없음|
|8|11|148|0 / 없음|
|9|14|150|0 / 없음|
|10|15|132|0 / 없음|
|11|13|188|0 / 없음|
|12|15|148|0 / 없음|
|13|10|145|30 / 45738|
|19|5|50|70 / 45103, 45128, 45137|
|20|8|40|70 / 45103, 45137, 45151, 45153|
|21|9|10|72 / 45135, 45179, 45183, 45186, 45336, 45504|
|23|1|245|0 / 없음|
|24|2|205|0 / 없음|
|25|1|199|0 / 없음|
|26|1|165|0 / 없음|
|27|1|145|0 / 없음|
|28|1|145|0 / 없음|
|29|0|0|0 / 없음|
|30|95|139|0 / 없음|
|31|5|115|0 / 없음|
|32|6|127|0 / 없음|
|33|7|137|0 / 없음|
|35|4|73|0 / 없음|
|36|3|79|0 / 없음|
|37|1|15|0 / 없음|
|43|4|0|0 / 없음|
|44|4|75|0 / 없음|
|45|4|75|0 / 없음|
|46|4|75|0 / 없음|
|47|4|75|0 / 없음|
|48|4|75|0 / 없음|
|49|4|75|0 / 없음|
|50|4|75|0 / 없음|
|51|5|75|0 / 없음|
|53|2|0|72 / 91405, 91406|
|54|2|0|130 / 91421, 91422, 91423, 91424, 91425, 91428|
|55|2|0|71 / 91411, 91421, 91422, 91423|
|56|1|0|116 / 91426, 91427, 91428, 91429|
|59|0|96|54 / 45307, 81076|
|60|0|64|60 / 45307, 81076, 81077|
|61|0|70|110 / 45307, 81076, 81077|
|62|0|0|0 / 없음|
|63|17|660|200 / 45077, 45154, 45279, 45285|
|65|1|0|0 / 없음|
|70|23|476|49 / 45377, 45457, 45578|
|72|72|80|55 / 45029, 45133, 45207, 46136, 46143|
|73|72|80|51 / 45029, 45207, 46135, 46138, 46144, 46145, 46146, 46147, 46148|
|74|3|70|31 / 45207, 46137, 46139, 46140, 46149, 46150, 46151, 46152|
|75|0|10|0 / 없음|
|76|0|10|0 / 없음|
|77|0|10|0 / 없음|
|78|5|80|0 / 없음|
|79|5|90|0 / 없음|
|80|4|90|0 / 없음|
|81|4|90|0 / 없음|
|82|5|120|1 / 46041|
|83|0|0|0 / 없음|
|101|0|0|0 / 없음|
|102|57|110|50 / 45380|
|103|115|143|30 / 45380|
|104|82|116|40 / 45380|
|105|3|126|49 / 45380, 81173|
|106|0|0|0 / 없음|
|107|0|104|62 / 45380, 81173|
|108|0|110|69 / 45380, 81173|
|109|0|101|73 / 45380, 81173|
|110|1|104|79 / 45380, 81173|
|111|0|0|63 / 45394, 45409|
|112|1|8|68 / 45394, 45409|
|113|1|7|70 / 45394, 45409|
|114|1|16|118 / 45394, 45409|
|115|2|50|107 / 45409|
|116|0|0|0 / 없음|
|117|2|49|83 / 45409|
|118|2|55|90 / 45409|
|119|2|62|100 / 45409|
|120|2|23|60 / 45409|
|237|0|0|0 / 없음|
|244|12|400|400 / 45770, 45771, 45774, 45783, 45785, 45786, 45787, 45788, 45789, 45790|
|303|16|333|436 / 45552, 45553, 45555, 45556, 45557, 45559, 45560, 45561|
|777|5|136|3 / 46097, 46098, 46099|
|779|0|0|60 / 46077, 46080, 46081|
|합계|839|8086|3358 / 중복 제외85종|

### B2와 같은 순수 WorldView 부하 측정·현재50ms 기준

B2 `_work/map4_population_perf/measure.py`의 `world_for`·통계 함수를 그대로 사용했다. 현재 WorldView/실제 Scheduler·InterestSpawner·NpcAi·S32 지형·패킷 인코딩·전투를 소비하되 소켓/서버/봇/게임/사용자 저장은 실행하지 않았다. 아래 앞4맵의 이전 측정은 후보를 dataclasses.replace로 메모리 안에서 구성한 결과다. map13 추가측정도 같은 방법으로 적용 직전 수행했으며, 제품 로더가 동일799그룹·8086목표·SQL 좌표/count/주기를 읽는 것은 단위시험으로 확인했다. map63은 전체 후보 중 최대660슬롯이고, RON 확장 사각형의 최대 중첩660에 속한 실제 S32 통행 가능 좌표(32598,32693)를 시작점으로 잡았다. 지도별 동일한 seed20261029·±8칸 경로,400tick×150ms=가상60초,4tick당 위치갱신1회,매tick drain/visibility refresh,동일 지형·PC fixture로 이전/후보를 비교했다. 활성화 시간은 tick 통계에서 제외했다.

B2 보존값 `dense-final-production-timing.json`:2400tick,평균0.616689ms·p95 3.1918ms·최대6.2098ms. 던전 표본과 필드 경로가 다르므로 동일 workload의 성능 배율로 주장하지 않는다. map63 후보는 B2보다 평균10.71배,p95 2.44배,최대1.65배이고 자체 이전 표본 최대0.3892ms에 비해서도 크게 늘었다. 측정 스크립트의 자동중단은 최대가 B2의2배를 넘는 조건이었으며, map70의15.1833ms에서 종료됐다. 이는 이전 중단 이력이다. 후속 사용자 승인은 해당 부하를 허용하고 임계값을50ms로 지정했다. 수량 축소나 스폰/AI guard 변경 없이 후보 그대로 연결했다.

|맵|이전 tick 평균/p95/최대 ms|후보 tick 평균/p95/최대 ms|후보 peak active/alive|사망 tick|
|---|---|---|---:|---:|
|63|0.167379/0.2699/0.3892|6.602666/7.7789/10.2193|660/660|0|
|244|0.149675/0.1737/0.2991|4.049709/5.5916/6.1000|200/200|0|
|303|0.241315/0.3319/0.5032|0.514738/0.7023/2.3330|270/270|0|
|70|0.209114/0.2702/0.3731|2.011022/6.6008/15.1833|47/47|192|
|13 추가측정|0.308939/0.4274/0.7118|3.792450/5.5448/9.6229|145/145|107|

map63은400tick에서 PC 사망0·peak 활성660슬롯/생존660을 관측했다. map70은192tick에서 사망 상태였으므로60초 연속 생존 사냥 부하로 해석하지 않는다. 모든 표본의 runtime error는0이다. map13은400tick·가상60초에서145슬롯/생존145 peak와사망107tick을 관측했다. 최대9.6229ms로50ms 이하이며, 사망을 제거하거나 체력/몬스터 수치를 조정하지 않았다. 나머지81맵 부하는 미측정이다.

측정 원문: [`performance.json`](../../../_work/tmp/dungeon_population/performance.json), 생성 스크립트: [`build_dungeon_population.py`](../../../_work/tmp/build_dungeon_population.py), 측정 스크립트: [`measure_dungeon_population.py`](../../../_work/tmp/measure_dungeon_population.py). 이전 실행 명령은 프로젝트 루트에서 `python -X utf8 -B _work/tmp/build_dungeon_population.py`, `python -X utf8 -B _work/tmp/measure_dungeon_population.py`이며 각각exit0이었다. map13 추가측정 명령은 `python -X utf8 -B _work/tmp/measure_dungeon_population_50ms.py`(exit0), 결과는 [`perf-map13.json`](../../../_work/tmp/dungeon_population_applied/perf-map13.json)이다. 이전 후보 생성기는 이제 로더가 적용 데이터를 소비하므로 현재 파일을 다시 실행해 이전839집계를 재생성하지 않는다. 원후보와 이전결과를 재사용한다. 이들은 오프라인 후보 생성/순수 부하 측정이며 단위시험이나 정식 플레이 PASS가 아니다.

### 제품 로더·단위시험 결과

`world_feature_dungeons.load_dungeon_data()`가 현재 admission에 등록된맵의 기존 LOCAL 스폰을 제거하고 소스799행을 설치한다. map0/4 필드는 보존한다. 시작 initialize는 그대로 유지할 그룹 객체를 재사용하고 대체 대상의 비어 있는 그룹만 제거한 뒤 ID 기준으로 신규 그룹/슬롯을 추가한다. 기존 spawner/이벤트/RNG/runtime tick hook·combat/ground 공유 데이터 연결은 보존한다. 몬스터 정의·드롭은 바꾸지 않았다. `world_dungeon_maps_tests.py`는 시작 교체·799/8086·정확 NPC/맵/count/사각형/respawn·unresolved 비적용과 기존 포맷 계약을 확인한다. `world_dungeon_talkscroll_maps_tests.py`는 옛1마리 LOCAL 그룹 대신 같은 NPC의 SQL 수량이 설치되는 것으로 기대값을 수정했다.

관련 오프라인 단위시험은 **58개 중57개 통과·1개 오류(그 안3개 subtest 오류)**다. 던전/지형/스폰/확장/주입형 integration 시험은 통과했다. 유일한 오류는 `world_maps_tests.RelocationPublicationTests.test_same_and_cross_map_replay_speed_item_and_spell_icons_without_state_change`: 병행 마법 변경에서 사용하는 `_world_magic_light_frames`를 기존 SimpleNamespace fixture가 바인딩하지 않아 AttributeError가 난다. 던전 연결 경로와 관계없는 마법 파일·해당 fixture는 수정하지 않았다. 전체통과로 표시하지 않는다. 별도 변경로더 필드 회귀 `field_population_tests`는 **12개 통과/2.785초**다.

프로젝트 루트 PowerShell 명령:

```powershell
$env:TMP = Join-Path $PWD '_work/tmp'
$env:TEMP = $env:TMP
python -X utf8 -B -m unittest tools.local_original_session.world_dungeon_maps_tests tools.local_original_session.world_dungeon_talkscroll_maps_tests tools.local_original_session.world_dungeon_terrain_tests tools.local_original_session.world_maps_tests tools.local_original_session.world_terrain_tests tools.local_original_session.world_spawn_tests.SpawnerTests tools.local_original_session.world_spawn_tests.VisibilityTests tools.local_original_session.world_expansion_data_tests tools.local_original_session.world_integration_tests.InjectedBrokerTests -q
# 58 tests /32.581s; errors=3 (one method's 3 subtests), Python exit1
python -X utf8 -B -m unittest tools.local_original_session.field_population_tests -q
# 12 tests /2.785s OK, Python exit0
```

원로그: [`unit-offline.log`](../../../_work/tmp/dungeon_population_applied/unit-offline.log), [`unit-loader-fields.log`](../../../_work/tmp/dungeon_population_applied/unit-loader-fields.log). PowerShell이 Python stderr를 NativeCommandError로 포장하는 표기와 실제 unittest 결과/exit는 구분한다.

최초에는 `world_spawn_tests`·`world_integration_tests`를 모듈 전체로 지정하여 포트/봇 helper를 사용하는 loopback 사례까지 잘못 포함했다. 보존 로그 [`unit-initial.log`](../../../_work/tmp/dungeon_population_applied/unit-initial.log)는68tests/2fail/17error다. 포트 사례의14개 error 항목(일부 subtest 포함)은 모두 `reserve()`의 bind 단계 `WinError10048`이며 서버 시작·패킷 요청까지 도달하지 못했다. 이 호출 시도 자체는 있었으며 포트 없는 시험으로 주장하지 않는다. 이후 포트 사례10개 method는 제외했고 재시도·대체 포트·타 프로세스 종료는 하지 않았다. 최초 LOCAL 기대값 실패2건은 위 계약 변경으로 해결했고 마법 fixture3오류는 남았다. 게임·헤드리스 클라이언트는 실행하지 않았다.

실제 변경파일은 `data/m6/dungeon_population.json`, `world_feature_dungeons.py`, `world_dungeon_maps_tests.py`, `world_dungeon_talkscroll_maps_tests.py`, 이 문서와 `_work/tmp`의 추가측정 스크립트/결과다. 원본 자원·사용자 저장·DLL·몬스터 수치·드롭·법사/물약/NPC 담당파일·커밋은 건드리지 않았다. 새 guard/중복 검사 체계는 추가하지 않았다.

남은 일: 미정의85종·3358목표는 계속 미적용이며 다른 종으로 대체하지 않았다. 같은맵 spawnlist가 없거나 미정의종뿐인43·53~56·65 등은 표처럼0목표다. 개별 좌표가 막히거나 unknown이면 기존스포너가 빈슬롯으로 두고재시도한다. 전맵 부하·Native 화면/입력·전체 실제 처치/재출현은 미확인이고, 현재 실행 중 세션을 재기동하지 않았다. 적용 데이터는 다음 정상 FullWorld 시작 시 로드된다. 마법 fixture 오류와 포트 loopback 미실행은 별도 잔여다.
