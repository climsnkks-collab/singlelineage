# M4 글루딘 데이터 준비

2026-10-27. **SOURCE_DATA_ONLY / 정적 지형 확인 / 게임·이동·상점·전투 UNRUN.** 고정 클래식 26.09.29.2001의 본토 첫 확장 준비다. 글루딘 마을과 동쪽의 작은 언데드 사냥 구역만 선정했으며, 본토 전체나 글루디오 던전 복원을 뜻하지 않는다.

쓰기 범위는 `tools/local_original_session/data/m4/`, 새 `work/local_resource_provider/assets/map/4/`, 이 문서다. 기존 코드·M1/M2/M3·공식 데이터·원본·저장·큐를 수정하지 않는다. broker·게임·서버·포트 시험과 git commit은 하지 않는다. 시작 브랜치는 기존 `main`이며, 기존 다수 dirty/untracked 변경은 이번 산출물에 포함하지 않는다.

## 출처와 데이터 경계

- 클라이언트: `work/source_game_data/native-dump-v1.jsonl`, `work/local_resource_provider/assets/data/region.jsonc`, 기존 맵 namespace/MapView·SPR 분석. ID·이름·외형과 지역 경계의 근거다.
- 공식 저장본: `tools/local_original_session/data/official/monsters.json` 및 `items.json`. 몬스터 출현 지역과 드롭 구성은 이 자료를 우선한다. 공식 자료가 제공하지 않은 확률·수량·NPC 배치·가격을 공식값으로 채우지 않는다.
- L1J: 읽기 전용 `D:/SingleLineageRef/l1j-en-classic`, 기존 확인 HEAD `103e6f6c9dd83545959d8e87d3f59f8de1f40ef0`, `db/l1jdb_m10.sql`의 `npc`, `spawnlist`, `spawnlist_npc`, `shop`, `droplist`. 좌표·능력치·경제·확률의 출처 있는 backend 참고이며 클래식 공식 정책의 증명이 아니다.
- 기존 [M3 데이터](M3_DUNGEON_DATA.md), [마을 메뉴](M2_NPC_MENUS.md), [맵 전환](MAP_TRANSITION_EVIDENCE.md), [배 이동](BOAT_EVIDENCE.md)의 대응과 미확정을 재사용한다.

M1의 `{value, source, ref, note?}` 필드와 `monsters`·`groups`·`drops` 구조를 재사용한다. NPC·상점은 기존 M2의 원행·후보·미확정 보존 형식을 따른다. Classic template, 공식 ID, L1J ID, region ID, MapView ID, 실제 Actor UID는 서로 다른 namespace다.

## 맵과 범위

[maps.json](../../../tools/local_original_session/data/m4/maps.json)에 원문 경계와 실제 추출 경계를 구분했다.

| 구분 | ID / map | inclusive 경계 | 근거 |
|---|---|---|---|
| 글루딘 마을 | region145 / map4 | x32581–32655, y32704–32834 | region.jsonc:159–160 |
| 글루디오 | region146 / map4 | x32512–32960, y32537–33023 | region.jsonc:161–162 |
| 아덴 대륙 | region175 / map4 | x32512–34303, y32192–33535 | region.jsonc:225–226 |
| 추출된 S32 청크 bbox | map4 / 650청크 | x32448–34367, y32128–33599 | `WorldTerrain.bounds(4)` |

청크 bbox는 빈 곳을 포함할 수 있고, 지역 경계도 모든 칸의 통행 가능성을 뜻하지 않는다. MapView25의 `_regionId=[145]`, `_baseLoc=(32608,32736)`은 UI 자료이며 이동 도착칸으로 전용하지 않는다. 배 선내 map5/6은 region32/33이고 본토 map4와 별개다.

## 첫 사냥 구역

글루딘 동쪽의 좀비27·해골29·해골궁수276을 선정한다. 공식 저장본 세 종 모두 `official.regionNames`에 `글루디오`가 있으며, 드롭 원문은 각각 5·15·9행이다. 해골의 같은 item ID에 붙은 일반/저주 이름도 별도 원문으로 보존한다. 공식 지역명은 넓은 출현 지역 근거이며 특정 L1J 좌표에서의 클래식 출현 관측은 아니다.

스폰은 같은 L1J 몬스터의 근처 실제 원행을 기준으로 한 로컬 축소 정책이다. 원본 마릿수와 선정·축소 근거는 [spawns.json](../../../tools/local_original_session/data/m4/spawns.json), 공식 구성과 실행 후보/미확정은 [drops.json](../../../tools/local_original_session/data/m4/drops.json)에 둔다. 미지원 아이템이나 효과를 작동 가능한 보상으로 승격하지 않는다.

| 몬스터 / Classic / L1J | 선정 inclusive rect | 근처 L1J 마릿수 → LOCAL 목표 | can_stand True / False / None |
|---|---|---|---|
| 좀비 / 27 / 45065 | x32749–32769, y32701–32721 | 30 → 4 | 440 / 1 / 0 |
| 해골 / 29 / 45107 | x32777–32797, y32755–32775 | 18 → 3 | 439 / 2 / 0 |
| 해골궁수 / 276 / 45122 | x32760–32780, y32737–32757 | 13 → 2 | 416 / 25 / 0 |

각 rect는 21×21칸이며 합계 1,323개 칸을 중복 영역별로 센 값이다. 서로 겹치는 칸을 제거한 고유 타일 수는 아니다. 목표는 총 9마리이고, 세 영역 모두 글루디오 경계 안·글루딘 마을 경계 밖이다. 영역별 중심과 선정 L1J 원점은 통행 가능하다. 막힌 28개 칸을 통행 성공으로 표시하지 않는다.

공식 세 종의 원문 전체 행을 [official_monsters.json](../../../tools/local_original_session/data/m4/official_monsters.json)에 그대로 보존했다. 기존 순수 parser에 넣을 수 있는 드롭 후보는 12행, 미확정은 17행이다(좀비 2/3, 해골 6/9, 궁수 4/5). 17행 중 10행은 책·부활·MR 망토·재료 등 소비 미지원 때문에 보류했고 기존 item/roll 참고 근거도 남겼다. 나머지 7행은 해당 NPC의 L1J droplist 부재·대응 미확정 등 기존 결손이다. 다른 NPC의 확률로 채우지 않는다. 12행도 실제 전투·보상 PASS는 아니다.

[items.json](../../../tools/local_original_session/data/m4/items.json)은 M1과 겹치지 않는 Classic67 언월도 1종의 추가 정의다. 기존 M1 아이템과 병합해서 참조해야 하며 원본 등급·특수효과의 전체 동등성을 뜻하지 않는다. 공식 드롭의 확률·수량 null은 그대로 유지하고 실행 후보의 별도 L1J roll만 출처를 붙였다.

## S32 추출과 통행 검사

기존 `tools/local_resource_provider/provider.py:AssetProvider.save`를 사용해 서명된 현재 catalog의 `map/4/*.s32` 전체 650개, **74,725,623 bytes**를 새 `work/local_resource_provider/assets/map/4/`에 추출했다. 기존 map0/1/2 폴더에는 쓰지 않았다. CONTROL은 `work/config_startup_trial/control.snapshot.bin`, SHA256 `9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`; pack은 `work/standalone_boot/current-unmodified-clone/pack`이다.

추출 시 provider의 catalog 서명·AEAD·개별 크기/해시·readback 검사를 통과했다. 사용 archive는 `data_0.lcx`다. 출처 식별, 청크별 크기/해시, 최종 통행 집계는 [terrain_validation.json](../../../tools/local_original_session/data/m4/terrain_validation.json)에 있다. 추출 성공은 런타임 자원 소비·맵 전환·화면 성공의 근거가 아니다.

`world_terrain.py`를 수정하지 않고 `WorldTerrain.load(map_ids=(4,))`로 읽는다. `can_stand`는 static mask1에서 한 방향 이상 이동할 수 있는 loaded cell을 고르는 기존 LOCAL 정책이다. 문·동적 점유·전체 원본 navigation은 판정 범위 밖이다. 직사각형 안의 막힌 칸도 보존하고 실제 출현 시 `can_stand(...) is True` 검사로 제외해야 한다.

최종 목적지 대조 때는 기존 map0도 읽기만 하여 `WorldTerrain.load(map_ids=(0,4))`를 사용했다. 배의 L1J 탑승 SQL row15018 출발칸 map0 `(32632,32983)`도 False다. 해당 원행을 보존했고 주변 칸으로 자동 보정하지 않았다. 선내 map5/6의 14개 점 조회는 전부 미로딩(None)으로 남겼다. NPC는 중심만 검사했으므로 `randomx/randomy` 전체 영역이나 실제 점유를 보장하지 않는다.

## 마을 NPC·상점과 이동

NPC 배치는 클래식 region145 안의 L1J `spawnlist_npc`를 기준으로 하며 count0·반복 배치·randomx/y를 원행대로 보존한다. 항구 배표 상인70022의 중심 `(32560,32723,map4)`는 마을 서쪽 경계 밖이므로 인접 NPC로 분리한다. NPC identity 대응과 실제 메뉴·프레임·거래 성공을 구별한다.

| 파일 | 보존 범위 |
|---|---|
| [town_npcs.json](../../../tools/local_original_session/data/m4/town_npcs.json) | 마을 47종/66배치 + 항구 1종/1배치, 합계 48종/67배치. count0 원행 10개 포함 |
| [shop_npcs.json](../../../tools/local_original_session/data/m4/shop_npcs.json) | 상품·매입 원행이 있는 상인/서비스 38후보. 모든 후보가 실제 판매 상인은 아님 |
| [shop_sales.json](../../../tools/local_original_session/data/m4/shop_sales.json) | 판매 131원행. 기존 loader에서 계산 대상으로 선정되는 후보 35행, 나머지 미선정/미확정 보존 |
| [shop_buyback_reference.json](../../../tools/local_original_session/data/m4/shop_buyback_reference.json) | 매입/비판매 참고 933원행. 판매 표와 합쳐 SQL 1,064원행 보존 |

NPC의 유일한 Classic catalog 대응 선정은 L1J80093→Classic81, L1J80098→Classic79 두 종이다. 나머지는 후보 또는 미확정으로 보존한다. 같은 번호의 sprite만으로 NPC를 확정하지 않는다. 마을 NPC60007 / spawn60004 `(32618,32800,map4)`는 static `can_stand=False`라 원좌표를 유지하고 배치 제외·후속 원본 확인 대상으로 표시했다. 임의 이웃칸 이동은 하지 않았다.

NPC 고유 `(l1j_npc_id, spawn_id)` 67배치는 True66/False1/None0이다. terrain 결과의 NPC 문서항목 112회는 town67 + shop45이며 shop의45배치가 town에 중복된다. shop NPC 38종 중 Blue Sharks71184만8배치를 가져 45개 원행이 된다. 문서항목 검사 수를 고유 배치 수로 합산하지 않는다.

공식 대조는 기존 공식 item 사전과 공식 도메인의 룻·케티·글루딘 마을 상점·루카스 검색으로 제한했다. NPC 추정 API 두 경로는 HTTP404, 마을 guidebook은 접근 실패였고 사용 가능한 NPC별 사전/공식 판매표는 확보하지 못했다. 따라서 NPC 배치·판매 구성·가격은 공식 확인값이 아니다. 배표124/125의 공식 이름·선착장 설명과 대응 상품의 공식 item identity만 대조했고, 정확한 검색어·실패 URL·응답 한계는 각 표의 `official_comparison`에 남겼다. 이 제한된 검색을 공식 자료의 전역 부재 주장으로 쓰지 않는다.

[travel.json](../../../tools/local_original_session/data/m4/travel.json)은 배와 루카스 목적지를 출처별로 구분한다. 특히 [배 이동 원문](BOAT_EVIDENCE.md)의 Classic ShipInfo `f9 RandomPoint`, `f11/f12 Point`, L1J GetBack 기준점과 요청 좌표 허용 범위를 서로 덮어쓰지 않는다. Classic item124(`$314`, 글루디오 영지행)·125(`$315`, 말하는 섬행)와 L1J40299·40298도 별도 번호다. 배표·운항·소비·정상 왕복 동작은 이번에 실행하지 않는다.

| 이동 | 도착 좌표 근거 | static can_stand / 한계 |
|---|---|---|
| 말하는 섬→글루딘 배 | Classic ShipInfo row1 f8/f9: map4 `(32569,32726)`, radius raw5 | True. RandomPoint 선택·실제 플레이어 최종 도착은 UNKNOWN |
| 글루딘→말하는 섬 배 | Classic ShipInfo row2 f8/f9: map0 `(32632,32963)`, radius raw5 | True. 실제 플레이어 최종 도착은 UNKNOWN |
| 같은 정방향 L1J 참고 | GetBack map4 기준 `(32565,32726)` | True. 요청 x/y의 각 ±20 허용 기준이며 단일 도착칸 아님 |
| 같은 역방향 L1J 참고 | GetBack map0 기준 `(32632,32973)` | **False**. 좌표를 고치거나 도착 가능으로 승격하지 않음 |
| 말하는 섬 루카스→글루딘 | L1J Teleporter.xml:126–127, map4 `(32608,32734)`, heading5 | True. 1,500A는 L1J 정책 후보, Classic 목적지/요금 실제 관측 아님 |

원본 메뉴 literal은 `lucas1`→`teleportURL`→`lucas2`의 **`island-gludin`**이다. L1J XML의 `teleport island-gludin`과 구분하며 wire action에 접두사를 붙이지 않는다. 역방향 루카스 목적지를 추측해 만들지 않는다. 배의 map5/6 선내점은 미추출·미로딩으로 UNKNOWN이며 본토 도착점으로 대체하지 않는다. `f12`의 출발항 쪽 Point는 의미 미확정 자료로 별도 보존했다.

`town_services.json`은 만들지 않았다. 기존 서비스 로더는 `inns[0]` 및 창고 정책을 요구하지만 글루딘 여관 요금·서비스 계약은 미확정이다. 로더를 만족시키기 위해 임의 요금을 넣지 않고 루카스 자료를 travel 표에 보존했다.

## 필요한 로드 지원 — 이번에는 보고만

- `world_terrain.py:DEFAULT_MAP_IDS=(0,)`, `LAZY_MAP_IDS=(1,2)`이므로 추출만으로 기본 terrain에 map4가 등록되지 않는다. 후속 코드 작업에서 map4의 명시/지연 로드를 선택해야 한다.
- `game_data.load_m1()`은 기본 M1 경로와 전체 M1 필수 표를 읽는다. M4는 확장 표이므로 `load_m1(m4)`로 대체하지 말고 기존 M1에 M4 몬스터·스폰·보상·추가 아이템을 합치는 연결이 필요하다.
- NPC·상점은 M2 형식으로 준비해도 기본 경로를 자동 변경하지 않는다. 마을 범위·인접 NPC·count0·미확정 후보·상품 대응을 유지한 명시적 로드/선정이 필요하다.
- 기존 상점 계산기에 후보가 읽힌다는 사실은 그 아이템의 인벤토리 정의·native 메뉴·획득·사용 지원을 뜻하지 않는다. 미지원 상품/배표125는 그대로 보류하며 데이터 준비를 실제 거래 성공으로 확대하지 않는다.
- 이동 데이터는 실행 trigger나 wire 값이 아니다. map4 허용 범위, 도착 지형, 실제 원본 map 전환 계약과 루카스/배 소비·저장/정리를 후속 허용 작업에서 연결해야 한다. map5/6 선내 지형은 이번 map4 추출에 포함하지 않는다.

현재 `world_feature_maps.py:149–150`의 `realm_serves_map`도 기본 map0과 명시 실험의 map1/2만 허용한다. 따라서 지형 파일 추가만으로 map4 이동을 허용하지 않으며 이 조건은 이번에 변경하지 않는다.

## 확인 범위

이번 확인은 새 JSON 읽기·기존 순수 데이터 parser의 형식 호환·내부 참조·S32 정적 통행에 한정한다. 데이터·추출을 실제 플레이 PASS, 30분 사냥, NPC 화면·입력·상점 거래·왕복·저장 성공으로 표시하지 않는다.

메인은 기존 `game_data._monsters/_spawns/_drops/_items`, `world_town.load_town(m4)`, `world_shop.load_shops(m4)`를 읽기 전용으로 호출해 3종·3그룹/9마리·드롭12/미확정17·추가아이템1종·마을67배치·상점131행의 형식 호환을 확인했다. 실행 드롭의 아이템 참조는 M1+M4 합집합에 존재하고, M4 추가 아이템은 M1과 ID가 겹치지 않는다. 공식 선택 3행/드롭29행은 기존 공식 원문과 구조적으로 동일했다. 별도 검사기·시험 파일·중복 실행 로그는 만들지 않았다.

산출물은 M4 JSON 12개와 새 map4 S32 650개, 이 문서다. 메인은 최종 terrain 입력 문서 해시의 일치와 주요 목적지·불통행 칸을 기존 지형 reader로 독립 확인했고, 문서의 로컬 링크도 확인했다. 추출·정적 검사용 작업 프로세스는 종료했다. 다른 세션의 실행·저장·포트·프로세스에는 개입하지 않았다.
