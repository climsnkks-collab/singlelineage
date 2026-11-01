# M3 말하는 섬 던전 데이터

2026-10-26. 사용자 지정 범위의 **데이터 준비**다. 비교 기준은 기존 클래식 26.09.29.2001 자료와 보관된 L1J classic SQL이다. 게임·서버·L1J를 실행하지 않았고, `game_data.py` 및 현재 M1 표는 수정하지 않았다. 새 표는 `tools/local_original_session/data/m3/{monsters,spawns,drops}.json`이며 M1의 `value/source/ref/note` 셀과 세 테이블 구조를 따른다. 출처의 `l1j`는 원본 클래식 수치가 아니라 빈칸을 채우는 로컬 backend 참고 정책이다.

## 맵 존재와 경계

| 실제 맵 | 클래식 지역·청크 근거 | 확인된 경계 / 남은 경계 |
| --- | --- | --- |
| map0 말하는 섬 | `work/local_resource_provider/assets/data/region.jsonc:5` region21 | x32256–32767 / y32768–33279. L1J mapids와 일치한다. |
| map1 말하는 섬 던전 1층 | 같은 파일 `:7` region22, `_isDungeon:true`; `work/asset_link_audit_20261007/map/map_namespaces.tsv:3` | 클래식 `_bounds` 없음. 기존 분석의 구버전 현물 12개 .s32가 현재 catalog 12개와 일치한다. **클래식 전체 경계·유효 셀은 UNKNOWN.** L1J 참고 경계는 x32640–32767 / y32768–32895 (`l1jdb_m10.sql:19192`). |
| map2 말하는 섬 던전 2층 | 같은 파일 `:9` region23, `_isDungeon:true`; 같은 TSV `:4` | 클래식 `_bounds` 없음. 기존 분석의 구버전 현물 16개 .s32가 현재 catalog 16개와 일치한다. **클래식 전체 경계·유효 셀은 UNKNOWN.** L1J 참고 경계는 x32640–32831 / y32768–32895 (`l1jdb_m10.sql:19193`). |

SQL은 `D:/SingleLineageRef/l1j-en-classic/db/l1jdb_m10.sql`이다. mapids 열 정의는 `:1461–1467`의 mapid/startX/endX/startY/endY다. 청크 수·이전 분석의 일치 기록은 자원 존재 근거이며 실제 입장·이동·렌더 성공이나 .s32 이름에서 복원한 좌표 경계가 아니다. 지도 UI의 `_id`는 실제 map ID와 다르다. `work/asset_link_audit_20261007/map/report.md:20–31,78–93` 및 `MAPPING_SCOPE.md` 1장을 재사용했다.

스폰 사각형은 L1J 해당 층의 기존 spawnlist에서 고른 참고 영역이다. 이 영역을 클래식 통행 가능 영역으로 확정하지 않는다. 이후 실제 연결에서는 기존 클래식 지형·점유 소비 경로로 출현 셀을 확인해야 한다. L1J `maps/*.txt`의 비트를 클래식 통행 비트로 전용하지 않는다(`MAPPING_SCOPE.md` 1장; `tools/local_tile_passability/README.md:9–15`).

## NPC·외형·드롭 대응

`MAPPING_SCOPE.md` 3장대로 이름 토큰으로 후보를 묶고, 보관된 공식 이름·레벨·출현 지역으로 변종을 구별한 다음 클래식 f2 및 SPR 이름으로 외형을 고른다. 다음 여섯 종은 던전 전체 생물 목록이 아니라 성장용으로 선정한 부분집합이다. 아래 `all-rows`는 `work/monster_level_comparison/analysis/all-rows.csv`이며 2026-10-09 공식 저장본과의 대응 자료다.

| 종 | 클래식 template / 토큰 / f2 | 공식 레벨·던전 출현 | L1J NPC / SQL 행 |
| --- | --- | --- | --- |
| 좀비 | 27 / $57 / 52 | Lv6, 1·2층 (`all-rows:39`) | 45065 / `:20685` |
| 괴물 눈 | 11 / $6 / 29 | Lv7, 1·2층 (`all-rows:48`) | 45068 / `:20688` |
| 해골 | 29 / $7 / 30 | Lv10, 1·2층 (`all-rows:60`) | 45107 / `:20725` |
| 해골궁수 | 276 / $986 / 1096 | Lv12, 1·2층 (`all-rows:72`) | 45122 / `:20740` |
| 돌 골렘 | 6 / $56 / 49 | Lv13, 1·2층 (`all-rows:75`) | 45126 / `:20744` |
| 스파토이 | 30 / $318 / 145 | Lv16, 2층 (`all-rows:99`) | 45161 / `:20777` |

이름이 같은 해골 template25와29, 돌 골렘5/6/162 등은 하나로 합치지 않는다. 같은 토큰·이름만으로 해당 변종의 L1J 능력치가 클래식과 같다고 확정하지 않는다. 서버 HP·MP·AC·보상 EXP·공격식은 해당 L1J 행의 참고값이고 공식 레벨과 SQL 레벨이 다르면 양쪽 값을 남긴다. 속도는 선택한 클래식 SPR 명목 재생시간을 우선하며, 최종 서버 간격으로 쓰는 것은 로컬 정책이다.

드롭 구성은 해당 클래식 NPC의 f21 목록(`work/npc_field_semantics/hypotheses/all-drop-pairs.json`)을 유지한다. 두 번째 값은 확률이 아니라 등급(0축복/1일반/2저주)이다. 아이템은 클래식 ID·이름 토큰·종류·등급과 f5(인벤토리 아이콘)/f6(바닥 그래픽)·무게를 대조한다. L1J 아이템 번호를 클래식 template로 직접 넣지 않는다. 대응 NPC 자신의 L1J droplist에 실제 행이 있는 조합만 확률·수량을 `roll`에 넣고, 없는 조합이나 대응이 불명확한 조합은 `unresolved`에 남긴다. 미채택 L1J 원행은 선택 메타데이터 `l1j_unapplied`에 보존하며, 이 목록에는 클래식 구성 밖 항목과 미확정 대응 후보가 함께 있다. 상세 양쪽 ID·SPR/아이콘·원문 위치 및 차이는 각 JSON 행에 기록한다.

클래식 원문 74행을 중복 제거한 아이템·등급 52쌍 중 `drops` 35건, `unresolved` 17건이다. 괴물 눈에는 클래식 목록에 없는 아데나를 추가하지 않았다. 해골29의 저주 언월도는 L1J 일반/축복 언월도 확률로 대체하지 않았다. 활11의 클래식 인벤토리 아이콘20과 L1J278의 차이, 초록 물약17의 무게·이름 토큰 차이는 기존 M1 대응과 함께 보존했다. 강화 초록 물약·막대·퀘스트 변종 등은 확정 근거가 부족해 확률을 비워 두었다.

## 단일 플레이어 스폰 정책

| 층 | 선정 종의 L1J 마릿수 → 로컬 마릿수 | 총합 |
| --- | --- | --- |
| 1층 | 좀비35→4, 괴물 눈15→2, 해골70→5 | 120→11, 3그룹 |
| 2층 | 좀비10→2, 괴물 눈10→2, 해골20→4, 해골궁수20→3, 돌 골렘10→2, 스파토이20→2 | 90→15, 6그룹 |

L1J 전체 던전 생물이 아니라 위 여섯 종에서 선정한 그룹의 비교다. 1층은 Lv6–10의 세 종, 2층은 Lv6–16의 여섯 종으로 시작한다. 혼자 플레이할 때 집중 선공·과밀을 줄이는 초기 정책이며 실제 사냥 밀도·소요 시간은 아직 확인하지 않았다. 사각형은 각 층 L1J spawn의 전체 후보 범위를 그대로 두었다. 출처는 SQL `:45974,45976,45977` 및 `:45981,45983–45985,45988,45990`이다.

이 L1J 원행의 min/max_respawn_delay는 모두0/0이다. 이를 클래식 즉시 리젠으로 해석하지 않고 M1과 같은 60–120초를 **local_policy**로 선택했다. 원본 리젠값을 확인한 결과가 아니며 실제 지형·점유 및 자연 리젠은 미실행이다.

## 던전 입구·층간 이동의 근거

**원본 정적 입구 목적지는 map0(32477,32853)이다.** `work/all_table_semantics/travel_review/teleport-ui-joins.json:189–204`의 group1/ordinal11, desc16271은 “말하는 섬 던전 입구”, destination0/x32477/y32853을 보존한다(JSON pointer `/11`). 기존 TeleportBookTargetInfo UI 복사 경로의 자료이며 실제 계단 트리거·패킷 동작을 관측한 것은 아니다. 아래 L1J 진입 트리거보다 y가2 크고, L1J 귀환 도착점과는 같다. 서로 같은 종류의 위치로 합치지 않는다.

`run287`가 참조한 `work/all_table_semantics/travel_review/entermap-data-candidates.json:15–26`에도 `lucas2`/`island-dungeon` → map0(32478,32853)이 있다(pointer `/1`). 이 자료의 실제 typed consumer는 UNKNOWN이며 입구 부근 목적지 후보일 뿐 계단 진입 계약이 아니다.

기존 `run273_map_transition_contract`와 `run287_temple4_77_return_map0_contract`는 **말하는 섬 계단의 정확한 트리거·원요청 기록을 제공하지 않는다.** 다음은 L1J `dungeon` 테이블의 참고 후보이며 클래식의 실제 입장·층간 이동 관측이 아니다. 열 정의는 SQL `:671–681`의 src_x/src_y/src_mapid → new_x/new_y/new_mapid 및 new_heading이다.

| 방향 | L1J 출발 map(x,y) → 도착 map(x,y) | SQL 원문 |
| --- | --- | --- |
| 섬 → 1층 | 0(32477,32851) → 1(32669,32802), heading4 | `:14930` |
| 1층 → 섬 | 1(32669,32802) → 0(32477,32853), heading4 | `:15088` |
| 1층 → 2층 | 1(32737,32877) → 2(32665,32789), heading4 | `:15535` |
| 2층 → 1층 | 2(32665,32788) → 1(32738,32877), heading2 | `:15074` |

같은 층 안 계단·지하통로 map14 연결도 SQL에 있으나 이번 표 범위에 추가하지 않았다. 출발·도착 칸은 서로 다른 값이며 역방향을 임의로 좌표 반전해 만들지 않는다.

- `work/local_server_rea_20261016/run273_map_transition_contract/MAIN_REVIEW.md`와 `source/contract.md`: 일반 dialog4E43 → 조건부 HACTION4ED4, MapNotify4E95 수신/actor 정리/Map 값 반영의 기존 계약이다. 특정 NPC·목적지 row와 action/cookie 및 `4F3650`의 node+58 callback·current Player 완료·정상 다음 요청은 미공급이다. 계단이 이 NPC 경로라는 근거도 없다. 4ED4 f4/f5를 목적지 좌표로 해석하거나 03EB를 map ACK로 쓰지 않는다.
- `work/local_server_rea_20261016/run287_temple4_77_return_map0_contract/MAIN_REVIEW.md`와 `source/contract.md`: Temple4/77 → map0 귀환의 선정 입력에서 정확한 출구·producer/caller가 미공급이었다. region의 literal map77은 오렌 상아탑 3층이라는 namespace 반례도 보존한다. 이 결과를 말하는 섬 던전 귀환 성공·전체 자료의 경로 부재로 확대하지 않는다.
- 기존 수용 기록은 `work/local_original_session/implementation-2/npc-motion-goal/HANDOFF.md:796,818`이다. 이번 작업은 이 source 계약을 재사용했으며 새 역분석·패킷·map setter·저장 guard 수정은 하지 않았다.

클래식 입구·층간 이동을 확정할 최소 후속 입력은 해당 계단의 현재 좌표와 정상 이동 요청/응답, 같은 operation의 도착 map·위치·current Player 재수립 및 다음 정상 요청 기록이다. 이 데이터 준비에 그 관측을 선행조건으로 추가하지 않는다.

## 소비 범위

기존 `game_data.py`의 `_monsters`, `_spawns`, `_drops`가 읽는 세 표 형태를 재사용한다. `load_m1()`은 별도로 M1 items/pc_exp/action_speed/town/starter/level_growth 파일을 읽으므로 새 폴더 전체를 로드하는 M3 공개 API는 이번 범위에 없다. M3 활성화·전환·NPC 생성·드롭 지급·저장/복원·화면/입력·통행 검증은 미실행이다.

## 실행한 확인

- 프로젝트 루트에서 `C:\Users\Chansol\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -X utf8 -B -m tools.local_original_session.game_data_tests`: 기존 M1 순수 데이터 시험 5개 통과(exit0). M3 실행 검증으로 확대하지 않는다.
- 같은 Python의 `-X utf8 -B -` stdin에서 기존 `game_data._read/_monsters/_spawns/_drops`에 M3 세 JSON을 직접 전달했다. 6종/9그룹/35개 드롭/17개 미확정을 읽었고 스폰의 NPC 참조·map1/2·그룹 ID 중복 없음까지 확인했다(exit0). 새 시험·검증기 파일은 만들지 않았다.
- 원문 확인·구조 로드는 완료했으며 제품 연결과 게임 동작은 미확인이다. 임시폴더 사용·권한 오류는 없었다.

## 2026-10-27 데이터 점검·보정 결과

이번 직접 요청의 범위는 M3 데이터와 새 정적 시험이다. 앞 절의 2026-10-26 미검증 기록은 당시 결과로 보존하며, 통행·공식 대조의 최신 결과는 이 절을 따른다. `world_terrain.py`, `world_maps.py`, `game_data.py`와 M1 데이터는 수정하지 않았다. 게임·서버·포트·broker 시험 및 git commit은 실행하지 않았다.

### 실제 S32 통행과 스폰 영역

`WorldTerrain.load(map_ids=(0,1,2))`로 현재 보유한 S32를 읽었다. map1은 12청크, 로드된 청크의 포괄 경계는 `(32576,32704)–(32831,32959)`이고, map2는 16청크, `(32576,32704)–(32895,32959)`다. 이 값은 청크의 bounding box이며 클래식 전체 유효 영역·모든 칸의 통행성을 뜻하지 않는다. `can_stand` 역시 원본의 독립된 stand 비트가 아니라, 로드된 칸에서 정적 mask1 기준 한 방향 이상 이동 가능한지를 사용하는 기존 LOCAL 판정이다. 동적 점유·문·오버라이드는 포함하지 않는다.

기존 사각형은 청크 포괄 경계 안이었지만 통행 비율이 낮고 `None` 칸이 있었다. 비율의 분모는 `False`와 `None`도 포함한 사각형 전체 칸 수다. 같은 몬스터의 L1J `spawnlist.locx/locy` 원 중심 주변 ±15칸을 선택해 다음과 같이 보정했다.

| 층 / 적용 그룹 | 이전 사각형 | 이전 True / False / None · 비율 | 보정 사각형 | 이후 True / False / None · 비율 |
| --- | --- | --- | --- | --- |
| map1 / 3그룹 | `(32640,32768)–(32767,32895)` | 6062 / 10318 / 4 · 36.9995% | `(32685,32785)–(32715,32815)` | 546 / 415 / 0 · 56.8158% |
| map2 / 6그룹 | `(32640,32768)–(32831,32895)` | 10681 / 13891 / 4 · 43.4611% | `(32685,32855)–(32715,32885)` | 552 / 409 / 0 · 57.4402% |

| 그룹 | 목표 수 유지 | L1J 원 중심 | SQL 행 |
| --- | ---: | --- | ---: |
| `m3_tic1_zombie` | 4 | `(32700,32800)` | 45974 |
| `m3_tic1_floating_eye` | 2 | `(32700,32800)` | 45977 |
| `m3_tic1_skeleton` | 5 | `(32700,32800)` | 45976 |
| `m3_tic2_zombie` | 2 | `(32700,32870)` | 45981 |
| `m3_tic2_floating_eye` | 2 | `(32700,32870)` | 45983 |
| `m3_tic2_skeleton` | 4 | `(32700,32870)` | 45984 |
| `m3_tic2_skeleton_archer` | 3 | `(32700,32870)` | 45985 |
| `m3_tic2_stone_golem` | 2 | `(32700,32870)` | 45988 |
| `m3_tic2_spartoi` | 2 | `(32700,32870)` | 45990 |

원 SQL은 `D:/SingleLineageRef/l1j-en-classic/db/l1jdb_m10.sql`이다. 원 사각형·중심·출처와 전후 수치를 `spawns.json`의 `l1j_reference_rect`, `l1j_reference_origin`, `terrain_check`에 보존했다. LOCAL 채택 기준은 통행 비율 50% 이상, `None=0`, 통행 칸 수가 동일 영역의 총 목표 수 이상이다. 보정 후 통행 칸 546/552는 각 층 목표 11/15를 수용한다. 기존 `InterestSpawner._place`는 전체 rect에서 최대 8번 무작위 선택하고 `can_stand is True`·비점유인 칸만 채택하므로, 보정 사각형 안의 벽을 통행 칸으로 취급하지 않는다. 8번 모두 거절되면 빈 슬롯을 유지하고 5초 뒤 재시도한다.

### 계단 통행과 도착점 완충 거리

| 기존 `world_maps.TRANSITIONS` 출발 → 도착 | 출발 can_stand | 도착 can_stand |
| --- | --- | --- |
| `0(32477,32851) → 1(32669,32802)` | **False** | True |
| `1(32669,32802) → 0(32477,32853)` | True | True |
| `1(32737,32877) → 2(32665,32789)` | True | True |
| `2(32665,32788) → 1(32738,32877)` | True | True |

**OPEN: 섬 쪽 진입 출발점 `map0(32477,32851)`은 정적 통행 검사에 실패한다.** 이번 쓰기 범위에 계단 표·지형 코드가 없으므로 좌표를 임의 변경하지 않았다. 실제 원본 계단 트리거는 여전히 UNKNOWN이다. 표 담당자가 고정 클라이언트의 해당 위치·정상 전환 입력/응답과 정적 판정을 대조해야 하며, 근처의 통행 칸을 곧바로 원본 트리거로 대신하지 않는다.

도착 직후 배치에 대한 LOCAL 기준은 전체 스폰 사각형과 도착점 사이 Chebyshev 거리 `max(8, monster.perception_range+1)` 이상이다. 현재 여섯 종의 인지거리 13칸에 따라 실제 요구 거리는 14칸이다. 보정 후 모든 map1 그룹의 최솟값은 16칸, 모든 map2 그룹은 66칸으로 충족한다. 이 거리는 통행 칸만 골라 측정한 값이 아니라 전체 사각형의 가장 가까운 칸 기준이다. 정책값과 근거는 `spawns.json.terrain_policy`에 보존했다. 초기·리젠 배치의 분리만 입증하며, 몬스터 이동 후 안전·실제 길 연결·원본 선공 규칙·30분 플레이를 보장하지 않는다. map0에는 이번 M3 스폰 그룹이 없다.

### 공식 몬스터 사전 대조

지정 경로 `work/official_data/raw/monster/`가 없어 `https://api-goats.plaync.com/linclassic/v2.0/game/monster/{id}`를 쿠키·인증 없는 익명 GET으로 수집했다. 2026-10-27 KST 02:03:40–46에 여섯 응답 모두 HTTP 200이었다. 요청 시작 간 최소 1.14초, 앞 응답 완료 후 최소 1.10초 간격을 뒀다. 공식 ID와 client template 대응은 기존 `all-rows.csv`의 `strict_id_name_match`를 재사용하고 이름·출현 지역을 대조했다.

| 종 / 공식 ID = client template | 기존 → 공식 레벨 | 공식 항목 수 / 활성·미확정 | 공식 드롭과 기존 전체 구성의 차이 |
| --- | --- | --- | --- |
| 좀비 / 27 | 6 → 6 | 5 / 5·0 | 없음 |
| 괴물 눈 / 11 | 7 → 7 | 2 / 1·1 | 없음 |
| 해골 / 29 | 10 → 10 | 15 / 10·5 | 없음 |
| 해골궁수 / 276 | 12 → 12 | 9 / 7·2 | 없음 |
| 돌 골렘 / 6 | 13 → 13 | 11 / 5·6 | 없음 |
| 스파토이 / 30 | 16 → 16 | 10 / 7·3 | 없음 |

공식 rewards의 몬스터별 아이템·등급 52쌍은 기존 활성 `drops` 35건과 `unresolved` 17건의 합집합과 일치했다. 공식에만 있는 항목 0, 기존에만 있는 항목 0이다. 공식 API에는 별도 등급 필드·확률·수량이 없으므로, 표시명의 축복/저주 접두사와 기존 client f21 등급을 함께 대조했다. 공식 목록 일치는 미확정 17건의 확률 근거가 아니므로 승격하지 않았다. 레벨·활성 드롭·확률·수량의 수치 변경은 없으며, 공식 대조·차이 메타데이터와 레벨의 최신 출처만 M3에 반영했다. 최신 공식 사전 조회가 고정 26.09.29.2001 클라이언트의 전체 동등성을 증명하지는 않는다.

응답 원문은 `tools/local_original_session/data/m3/official_monster_{27,11,29,276,6,30}.json`에 보존했다. `monsters.json`과 `drops.json`의 `official_comparison`에 개별 URL·수집 시각·해시·매핑·종별 차이와 미반영 사유를 기록했다. 기존 클라이언트·L1J 출처와 원래 레벨 출처도 보존했다.

### 새 데이터 시험과 판정 범위

실행 명령: `C:\Users\Chansol\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -X utf8 -B -m tools.local_original_session.world_m3_data_tests -v`

`world_m3_data_tests.py`는 기존 세 테이블 loader와 opt-in 소비 `with_dungeon_data`, 참조·등급·확률 구조, 실제 S32의 스폰 경계·통행 비율·기록 수치, 계단 도착 거리, 계단 출발/도착 통행을 검사한다. 결과는 **7개 중 6개 성공·1개 실패(exit1)**다. 유일한 실패는 `test_every_stair_source_is_standable`의 `source=(0,32477,32851)`, 원오류 `False is not True : blocked/unknown existing stair source (0, 32477, 32851)`이다. 실패를 skip·expectedFailure·가짜 성공으로 바꾸지 않았다. worker 최초 실행과 공식 메타데이터 마감 후 최종 조합 실행이 같은 실패를 보였으며, 최종 실행 시간은 0.685초다.

별도 읽기 전용 확인에서도 공식 원문 6개 SHA256, 이름·레벨, 52쌍의 합집합 일치와 응답 후 최소 간격 1.100473초를 확인했다(exit0). 첫 확인 명령은 PowerShell stdin의 한글 접두사 인코딩 때문에 등급 비교 assertion에 실패했으며, ASCII Unicode escape로 전달한 같은 비교에서 일치했다. 이는 표의 차이로 처리하지 않았다. 원실패는 실행 출력에 보존했다. 공용 코드 3개의 작업 전후 SHA256은 모두 동일했다.

이 결과는 데이터 로드·정적 통행·초기 배치 조건의 개발 시험이며 정식 로그인→월드 진입→실제 던전 플레이 PASS가 아니다. 미해결 계단 출발점 때문에 전체 데이터 시험을 PASS로 표시하지 않는다.
