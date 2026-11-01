# FullWorld 마을 NPC 배치 전수 점검

## 카운터 고정 NPC 원좌표 복원 (2026-10-30 후속 수정)

Mayer가 벽 밖에 보인다는 사용자 플레이 관측에 따라, 아래 기존 점검의 LOCAL 보정 13개를 폐기하고 `D:/SingleLineageRef/l1j-en-classic/db/l1jdb_m10.sql`의 `spawnlist_npc` 원좌표를 복원했다. 고정 NPC는 카운터 뒤 통행 불가 칸에도 설 수 있으므로 `TownNpcs._placement`의 고정 좌표 분기에서 `can_stand` 조건을 제거했다. 랜덤 범위 후보의 지형·점유 검사와 몬스터 스폰은 그대로다. 아래 옛 본문의 195개/blocked fixed 2개/LOCAL 보정 13개 및 결과 JSON은 **수정 전 기록**이며 현재 재집계 결과가 아니다.

| NPC | 이전 → 복원 좌표 (맵; SQL 행) |
|---|---|
| Verita | 33385,32730 → 33383,32730 (4; 48989) |
| Mayer | 33457,32820 → 33455,32820 (4; 48991) |
| Werner | 33400,32669 → 33398,32669 (4; 49023) |
| Vergil | 33438,32751 → 33436,32751 (4; 49030) |
| Molly | 33431,32783 → 33431,32785 (4; 49075) |
| Bius | 34065,32287 → 34065,32289 (4; 48997) |
| Mandra | 34070,32295 → 34068,32295 (4; 49025) |
| Enke | 34062,32254 → 34062,32252 (4; 49076) |
| Britt | 33639,33286 → 33641,33286 (4; 48994) |
| Shivan | 33624,33281 → 33624,33283 (4; 49024) |
| Elly | 33599,33271 → 33599,33273 (4; 49072) |
| Karim | 32619,32800 → 32618,32800 (4; 48950) |
| Jem | 32587,32926 → 32587,32927 (0; 49190) |
| Miriam 50619/50419 | 未등록 → 33626,33225 (4; 48941) |
| Elsha 50622/50422 | 未등록 → 33618,33266 (4; 48944) |

M5 town/shop 양쪽의 `spawns`와 shop 단일 `spawn`, M4 Karim, M2 quest runtime Jem을 함께 수정했다. 현재 `local_placement_source`는 SQL 원좌표를 가리키고, 폐기 보정 근거는 `retired_local_placement_source`로 보존했다. `terrain_can_stand=False`도 사실대로 유지했다. Miriam·Elsha는 기존 M5 메뉴/외형/등록 선택 경로를 그대로 사용한다.

대화/상점 거리는 `world_handlers.py:488` 기본값 15를 `handle_click`(211행) 및 후속 요청의 `_interaction`(189행)이 `world_town.py:332`의 `route_click`에 전달한다. 같은 맵·현재 UID/수명을 확인하고 Chebyshev 거리 `max(abs(dx),abs(dy)) <= 15`만 적용하며 보행 경로/벽/카운터 통과 여부는 검사하지 않는다. 기존 범위 변경 없이 원좌표 주변 통행 가능 칸에서 메뉴가 열린다. 이는 기존 LOCAL 범위이며 Classic 공식 거리 수치의 입증은 아니다.

단위 시험: `python -X utf8 -B _work/tmp/run_fixed_npc_unit_tests.py` — **84 tests, failures 0, errors 0, skipped 0**. M5DataTests/M5BotActionTests, M5 returns/supply/Gludin, town/town_services, npc_placement 및 Jem 등록 시험을 실행했다. 15개 시작 등록·SQL 원좌표·주변 칸 route_click, 14개 map4 NPC의 실제 CLICK 핸들러 메뉴 응답, 복원 상인 6개의 주변 칸 대화→구매/판매→저장 복원을 확인했다. 소켓을 여는 M5PacketTests, launcher_tests, manual_move_commands_tests는 제외했다. 로그: `_work/tmp/fixed-npc-unit-tests-verified.log`.

게임·헤드리스·서버·포트 실행, 사용자 저장 수정, DLL 수정 및 커밋은 하지 않았다. 실행 중 게임에 반영하지 않았으며, 다음 기동의 원본 화면/직접 클릭은 미확인이다.

## 기존 전수 점검 기록 (후속 수정 전)

기준: 2026-10-30, `SL_EXPERIMENT_MAP=2`, `SL_EXPERIMENT_M5=1`, 기본 Shop/Warehouse 켜짐, 별도 town candidate/feature-disable 없음. `start-manual-play.ps1:118-119`의 FullWorld 설정이다. **최종 420 placement 중 195개 등록, 같은칸 0쌍, 8방향 거리 2 이내 10쌍(3그룹)**이다. 수정전은 195개/같은칸 0쌍/근접 11쌍(4그룹)이다. 동일 NPC ID라도 spawn key/ordinal이 다른 개체를 포함했다.

이 문서는 실제 `setup_town` 및 등록형 fold 함수를 원본 S32 지형으로 오프라인 실행한 정적 시작상태 점검이다. 게임·봇·서버·포트·사용자 저장은 실행/수정하지 않았다. 원본 화면·입력·가림·경로 또는 플레이 PASS를 뜻하지 않는다. 전체 판정값/해시는 [기존 runs의 결과 JSON](../runs/npc-placement-audit-20261030.json)에 있다.

## 계산 범위와 소비 경로

`d=max(|xA-xB|, |yA-yB|)`인 Chebyshev 거리다. d0=같은칸, d1~2=8방향 격자 두 걸음 이내이며 벽/보행경로/원근 화면거리가 아니다. 실제 actor는 `(placement key, ordinal)`로 센다. 같은 key가 town/shop JSON에 반복된 것은 metadata로 합치며, 같은 ID의 다른 spawn은 합치지 않는다.

`world_feature_town.setup_town`은 M2→M4 loader를 합친 후 confirmed/service/shop/menu 후보를 선택하고 최초 등록한다. `town_setup` 순서는 `_world_dungeons_town_setup → _m5_town_setup → _world_quest_town_setup → _world_craft_town_setup`이다. dungeons의 `dungeon_town_setup`은 MapExp5 Eldin을 더하며, M5는 기존 UID를 adopt하고, quest는8 placement를 추가/치환하며, craft는 후보와 appearance를 연결한다. 실제 이 함수들을 호출했다. binding 연결/항목 정책 전달만 IO 없는 얇은 context로 받았으며 등록·appearance는 제품 함수를 사용했다.

M3/M6 monster `spawns.json` 등은 InterestSpawner의 동적 전투개체이며 마을 TownNpcs 고정배치 전수의 모수에 포함하지 않는다. M6의 마을 추가자는 `map_expansion5.json.teleporters` Eldin 1개다. 펫·소환·동료·필드 몬스터의 동적 접근까지 이 표가 보장하지 않는다.

## 모수와 활성/비활성 구분

| 원행 파일 | 배치 원행 수 |
|---|---|
| tools/local_original_session/data/m2/shop_npcs.json | 22 |
| tools/local_original_session/data/m2/town_npcs.json | 48 |
| tools/local_original_session/data/m4/shop_npcs.json | 45 |
| tools/local_original_session/data/m4/town_npcs.json | 67 |
| tools/local_original_session/data/m5/shop_npcs.json | 31 |
| tools/local_original_session/data/m5/town_npcs.json | 291 |

원행504개는 고유 key411개이며93개는 같은 key의 shop/town metadata 중복이다. loader merge 후 quest8개와 Eldin1개를 더한 최종 key는420개다. M3에는 TownNpcs 배치표가 없다.

| 맵 | catalog key | 수정전 actor | 최종 actor | 최종 근접쌍 |
|---|---|---|---|---|
| 0 | 53 | 17 | 17 | 0 |
| 3 | 1 | 1 | 1 | 0 |
| 4 | 364 | 175 | 175 | 10 |
| 62 | 1 | 1 | 1 | 0 |
| 237 | 1 | 1 | 1 | 0 |

| 최종 상태 | key 수 |
|---|---|
| active | 195 |
| candidate_off | 195 |
| count0 | 17 |
| center_blocked_or_unknown | 2 |
| scope_off | 11 |

기본맵0/1/2/4와 `load_island_policy().maps`의 총88개 지원맵도 포함했다. catalog 배치가 없는83개 맵(1, 2, 5, 6, 7, 8, 9, 10, 11, 12, 13, 19, 20, 21, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 35, 36, 37, 43, 44, 45, 46, 47, 48, 49, 50, 51, 53, 54, 55, 56, 59, 60, 61, 63, 65, 70, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 244, 303, 777, 779)은 마을 actor0/근접0이다. 이는 동적 몬스터가 없다는 뜻이 아니다.

`active`는 backend 등록이다. 최종195개 중194개는 sprite가 선택된 표시 대상이며 Lucas50015/50020은 sprite 미선택 backend 개체다. native 렌더링 관측은 아니다. candidate_off195, count0 17, scope_off11, blocked fixed2는 미등록이다. 미등록과 중복 metadata를 active 충돌로 세지 않았다.

| 지역/등록 출처 | 최종 actor 수 |
|---|---|
| fire_farmer | 2 |
| giran | 68 |
| heine | 23 |
| kent | 7 |
| oren | 8 |
| silver_knight | 3 |
| windawood | 7 |
| 글루딘·항구(map4) | 6 |
| 말하는 섬(map0; 인접 제작 포함) | 17 |
| 추가 제작/퀘스트/서비스(map237) | 1 |
| 추가 제작/퀘스트/서비스(map3) | 1 |
| 추가 제작/퀘스트/서비스(map4) | 51 |
| 추가 제작/퀘스트/서비스(map62) | 1 |

지역명은 JSON town_id 또는 기존 M4 범위/명시 확장 출처다. 추가 제작/퀘스트는 기존 5개 마을 region에 억지로 편입하지 않았다.

## 휜·쥬디스·모나: 원행과 변경 전후

사용자의 “퀸”은 이름·함께 언급된 NPC 맥락상 “휜”으로 해석한 **추론**이다. native catalog는 휜83/sprite705, 쥬디스84/sprite706, 모나322/sprite234를 확인한다(`native-dump-v1.jsonl:52,53,189`). 그 원문은 위치를 제공하지 않는다. 세 NPC의 **Classic 공식 고정 좌표는 UNKNOWN**이다.

| NPC/key | SQL 중심·범위 | 수정전 오프라인 등록 | 최종 오프라인 등록 | 좌표 근거 |
|---|---|---|---|---|
| Fiin `70101/87554` | 0/32575,32946; random25,25 | 32600,32964 | 32582,32963 | SQL:49243 |
| Judice `70102/87555` | 0/32575,32946; random25,25 | 32598,32967 | 32577,32950 | SQL:49244 |
| Mona `70529/87556` | 0/32575,32946; random25,25 | 32598,32964 | 32573,32939 | SQL:49245 |
| Lengo `70100/87553` | 0/32575,32946; random25,25 | 32568,32937 | 32565,32951 | SQL:49242 |

SQL 원행의 동일 중심은 고정 중복 배치가 아니다. `L1Spawn.java:435-438`은 각 축에 `floor(random*r)-floor(random*r)`를 적용한다. range25의 실제 델타 범위는 -24..24인 삼각분포다. 수정전은 균등 randint(-25,25)를 사용했고 map0 무조건 통과로 렝고가 막힌 칸에 남았다. 최종은 이 L1J random 계산을 소비하고 실제 후보칸에 기존 S32 can_stand를 적용한다. deterministic seed·64회 예산·같은칸 NPC 검사·실패시 미등록은 LOCAL 실행정책이다. 원 SQL/JSON 좌표는 바뀌지 않았다.

수정전 렝고32568,32937은 can_stand=False였고 최종32565,32951은 True다. 휜/쥬디스/모나/렝고 최종 위치는 모두 True이며 서로 d>=3이다. exact Classic 위치를 추정해 임의로 고정 이동한 결과가 아니다.

## 최종 실제 근접쌍 전수 (10쌍)

| 맵 | NPC A(key) | 좌표 A | NPC B(key) | 좌표 B | d | 좌표 근거 |
|---|---|---|---|---|---|---|
| 4 | Brad `70751/87522` | 34071,32312 | Sabin `70758/87523` | 34071,32310 | 2 | SQL:49211 / SQL:49212 |
| 4 | Fairy `70851/87232` | 33158,32276 | Fairy `70851/87234` | 33156,32277 | 2 | SQL:49120 / SQL:49122 |
| 4 | Fairy `70851/87232` | 33158,32276 | Fairy `70851/87235` | 33156,32274 | 2 | SQL:49120 / SQL:49123 |
| 4 | Fairy `70851/87232` | 33158,32276 | Fairy Queen `70852/87207` | 33157,32276 | 1 | SQL:49120 / SQL:49095 |
| 4 | Fairy `70851/87233` | 33155,32276 | Fairy `70851/87234` | 33156,32277 | 1 | SQL:49121 / SQL:49122 |
| 4 | Fairy `70851/87233` | 33155,32276 | Fairy `70851/87235` | 33156,32274 | 2 | SQL:49121 / SQL:49123 |
| 4 | Fairy `70851/87233` | 33155,32276 | Fairy Queen `70852/87207` | 33157,32276 | 2 | SQL:49121 / SQL:49095 |
| 4 | Fairy `70851/87234` | 33156,32277 | Fairy Queen `70852/87207` | 33157,32276 | 1 | SQL:49122 / SQL:49095 |
| 4 | Fairy `70851/87235` | 33156,32274 | Fairy Queen `70852/87207` | 33157,32276 | 2 | SQL:49123 / SQL:49095 |
| 4 | Pin `70807/87203` | 33071,33383 | Aanon `70802/87506` | 33069,33383 | 2 | SQL:49091 / SQL:49195 |

최종 근접 그룹은 오렌 Brad/Sabin 2개체1쌍, 요정숲 Fairy 4개체+Fairy Queen 1개체8쌍, 화전민 제작 Pin/Aanon 2개체1쌍이다. Fairy끼리의4쌍도 포함했다. 서로 다른 ID만 세면6쌍이다. 전부 원 SQL 고정 중심 그대로이므로 근접이라는 이유만으로 변경하지 않는다. 여기서 의도적 근접은 “보존된 source가 그렇게 배치한다”는 뜻이며 공식 Classic 서버 의도 입증은 아니다.

수정전만 있었던 근접쌍은 휜87554(32600,32964)↔모나87556(32598,32964), d2다. 수정전 쥬디스32598,32967과 모나/휜은 d3여서 이 기준에 포함되지 않는다.

## 좌표 provenance 전수와 미확정/변경하지 않은 목록

로컬 SQL `D:/SingleLineageRef/l1j-en-classic/db/l1jdb_m10.sql`의 actual `spawnlist_npc` key·맵·중심을420개 모두 직접 대조했다. **SQL 배치 key/좌표 출처 부재0개; SQL 중심 일치407개; 기존 LOCAL 지형보정13개**다. 모든420개에 spawn.source_ref 또는 상위 row.spawn_ref가 있다. L1J 출처가 있다는 사실은 Classic 고정좌표 확인과 별개다. 전체420개의 SQL 행번호·원좌표·현재 중심·실제 actor·상태는 결과 JSON after.rows에 보존했다.

| 구분 | NPC/범위 | 부족한 근거·현재 처리 |
|---|---|---|
| 정확한 Classic fixed 위치 미확정 | 휜·쥬디스·모나·렝고 | 원본 위치 UNKNOWN; L1J 중심+random 소비. 임의 fixed 이동 안 함. |
| 대체 standable 위치 미선정 | Dorin60001/60009, map0 32575,32946 | SQL:48955 fixed, can_stand=False. 기존 초기 등록/UID 보존; 임의 이동·삭제 안 함. 창고 접근의 실제 화면/경로 UNKNOWN. |
| 대체 standable 위치 미선정 | Ladar70523/87192, map0 32589,32957 | SQL:49080 fixed, can_stand=False. 기존 초기 등록/UID 보존; 임의 이동·삭제 안 함. |
| 기존 blocked fixed 미등록 | Miriam50619/50419, map4 33626,33225; Elsha50622/50422, map4 33618,33266 | SQL:48941/48944 근거 있음. can_stand=False; 대체칸 미선정이므로 기존 미등록 유지. |
| source 근접이므로 변경 불필요 | Brad/Sabin, Fairy/Queen, Pin/Aanon | 위10쌍은 SQL 원행 중심 그대로. 떨어뜨릴 근거 없음. |
| 좌표 출처 완전 부재 | 없음(0/420) | 인물 identity UNKNOWN과 좌표출처 부재를 혼동하지 않음. |
| 기존 LOCAL 보정 | 아래13개 | S32 지형보정/원좌표 metadata 있음; Classic 고정배치 입증 아님. 이번 작업에서 좌표 변경 안 함. |

| NPC/key | SQL 원좌표 | 기존 LOCAL 중심 | 근거 |
|---|---|---|---|
| Verita `70033/60804` | 4/33383,32730 | 4/33385,32730 | SQL:48989 + local_placement_source/reference_locx,y |
| Mayer `70030/60806` | 4/33455,32820 | 4/33457,32820 | SQL:48991 + local_placement_source/reference_locx,y |
| Werner `70039/60902` | 4/33398,32669 | 4/33400,32669 | SQL:49023 + local_placement_source/reference_locx,y |
| Vergil `70032/60909` | 4/33436,32751 | 4/33438,32751 | SQL:49030 + local_placement_source/reference_locx,y |
| Molly `70031/61127` | 4/33431,32785 | 4/33431,32783 | SQL:49075 + local_placement_source/reference_locx,y |
| Bius `70063/60812` | 4/34065,32289 | 4/34065,32287 | SQL:48997 + local_placement_source/reference_locx,y |
| Mandra `70061/60904` | 4/34068,32295 | 4/34070,32295 | SQL:49025 + local_placement_source/reference_locx,y |
| Enke `70065/61128` | 4/34062,32252 | 4/34062,32254 | SQL:49076 + local_placement_source/reference_locx,y |
| Britt `70082/60809` | 4/33641,33286 | 4/33639,33286 | SQL:48994 + local_placement_source/reference_locx,y |
| Shivan `70083/60903` | 4/33624,33283 | 4/33624,33281 | SQL:49024 + local_placement_source/reference_locx,y |
| Elly `70084/61124` | 4/33599,33273 | 4/33599,33271 | SQL:49072 + local_placement_source/reference_locx,y |
| Karim `60007/60004` | 4/32618,32800 | 4/32619,32800 | SQL:48950 + local_placement_source/reference_locx,y |
| Jem `70531/87501` | 0/32587,32927 | 0/32587,32926 | SQL:49190 + reference_original_spawn/spawn.source_ref |

S32 mask1은 원본 자원이고 can_stand는 “8방향 중 하나라도 나갈 수 있음”으로 정한 LOCAL 파생정책이다. actor/문/동적 점유와 전체 원본 충돌 판정은 별도다. 정적 보정 중심13개 모두 현재 can_stand=True다.

## catalog 중심 근접쌍 전수 (61쌍; active 혼동 금지)

아래는 등록/미등록과 무관한 데이터 중심을 비교한 결과다. 랜덤 중심은 실제 actor 좌표가 아니며 dormant/count0도 포함한다. status A/B는 최종 등록 상태다. 같은 key의 metadata 사본은 이미 합쳤다.

| 맵 | A(key) | 중심 A | 상태 A | B(key) | 중심 B | 상태 B | d |
|---|---|---|---|---|---|---|---|
| 4 | Alchemist `70520/87361` | 32615,33174 | candidate_off | Village Manager `70774/87861` | 32617,33175 | candidate_off | 2 |
| 4 | Secratary to the Mayor `70556/87850` | 33050,32745 | candidate_off | Village Manager `70546/87860` | 33049,32745 | candidate_off | 1 |
| 4 | Message Board `80006/130866` | 32615,33190 | candidate_off | Unknown `81200/1310378` | 32613,33189 | candidate_off | 2 |
| 4 | Message Board `80006/130865` | 33421,32806 | candidate_off | Pumpkin Trader `81124/130862` | 33421,32804 | candidate_off | 2 |
| 4 | Unknown `81200/1310368` | 34053,32264 | candidate_off | Sharna `81246/1310416` | 34052,32262 | candidate_off | 2 |
| 4 | Secretary to the Mayor `70788/87851` | 32618,33175 | candidate_off | Village Manager `70774/87861` | 32617,33175 | candidate_off | 1 |
| 4 | Bag Girl `90013/1900006` | 33454,32823 | candidate_off | Jeif `71180/1900015` | 33454,32824 | candidate_off | 1 |
| 4 | Moria `70598/87206` | 33404,32834 | active | Sarsha `70607/87348` | 33403,32833 | candidate_off | 1 |
| 4 | Secratary to the Mayor `70631/87845` | 33450,32793 | candidate_off | Village Manager `70594/87855` | 33451,32794 | candidate_off | 1 |
| 4 | Torch Fire `81160/130876` | 33429,32822 | candidate_off | Wizard Merlin `81287/1900014` | 33429,32824 | candidate_off | 2 |
| 4 | Auction Board `81161/130877` | 33421,32823 | candidate_off | Auctioneer `70577/130878` | 33423,32823 | active | 2 |
| 4 | Market Teleporter `50050/50042` | 34062,32273 | count0 | Message Board `81130/130870` | 34063,32275 | candidate_off | 2 |
| 4 | Brad `70751/87522` | 34071,32312 | active | Sabin `70758/87523` | 34071,32310 | active | 2 |
| 4 | Secretary to the Mayor `70761/87847` | 34063,32268 | candidate_off | Village Manager `70748/87857` | 34062,32268 | candidate_off | 1 |
| 4 | Old `70085/60954` | 33618,33238 | active | siksudea c `71103/90164` | 33619,33237 | candidate_off | 1 |
| 4 | Secretary to the Mayor `70876/87846` | 33613,33229 | candidate_off | Village Manager `70860/87856` | 33611,33229 | candidate_off | 2 |
| 4 | Unknown `71214/90251` | 33573,33351 | candidate_off | Unknown `71214/90252` | 33571,33349 | candidate_off | 2 |
| 4 | Fairy `70851/87232` | 33158,32276 | active | Fairy `70851/87234` | 33156,32277 | active | 2 |
| 4 | Fairy `70851/87232` | 33158,32276 | active | Fairy `70851/87235` | 33156,32274 | active | 2 |
| 4 | Fairy `70851/87232` | 33158,32276 | active | Fairy Queen `70852/87207` | 33157,32276 | active | 1 |
| 4 | Fairy `70851/87233` | 33155,32276 | active | Fairy `70851/87234` | 33156,32277 | active | 1 |
| 4 | Fairy `70851/87233` | 33155,32276 | active | Fairy `70851/87235` | 33156,32274 | active | 2 |
| 4 | Fairy `70851/87233` | 33155,32276 | active | Fairy Queen `70852/87207` | 33157,32276 | active | 2 |
| 4 | Fairy `70851/87234` | 33156,32277 | active | Fairy Queen `70852/87207` | 33157,32276 | active | 1 |
| 4 | Fairy `70851/87235` | 33156,32274 | active | Fairy Queen `70852/87207` | 33157,32276 | active | 2 |
| 4 | Pin `70807/87203` | 33071,33383 | active | Aanon `70802/87506` | 33069,33383 | active | 2 |
| 4 | Secratary to the Mayor `70572/87849` | 32609,32817 | candidate_off | Village Manager `70567/87859` | 32609,32818 | candidate_off | 1 |
| 4 | Guard `60501/89034` | 32588,32758 | count0 | Blue Sharks `71184/130896` | 32586,32757 | candidate_off | 2 |
| 4 | Guard `60501/89034` | 32588,32758 | count0 | Kent Castle Guard `71183/130897` | 32587,32756 | candidate_off | 2 |
| 4 | Guard `60501/89036` | 32618,32708 | count0 | Blue Sharks `71184/130899` | 32619,32706 | candidate_off | 2 |
| 4 | Guard `60501/89036` | 32618,32708 | count0 | Kent Castle Guard `71183/130901` | 32620,32707 | candidate_off | 2 |
| 4 | Guard `60501/89040` | 32629,32830 | count0 | Blue Sharks `71184/130892` | 32630,32832 | candidate_off | 2 |
| 4 | Guard `60502/89035` | 32588,32764 | count0 | Blue Sharks `71184/130895` | 32586,32765 | candidate_off | 2 |
| 4 | Guard `60502/89035` | 32588,32764 | count0 | Kent Castle Guard `71183/130898` | 32587,32766 | candidate_off | 2 |
| 4 | Guard `60502/89037` | 32613,32709 | count0 | Kent Castle Guard `71183/130902` | 32611,32707 | candidate_off | 2 |
| 4 | Guard `60502/89041` | 32625,32830 | count0 | Blue Sharks `71184/130891` | 32624,32832 | candidate_off | 2 |
| 4 | Auctioneer `80103/89618` | 32613,32775 | candidate_off | Auction Board `81161/89619` | 32611,32775 | candidate_off | 2 |
| 4 | Auction Board `81161/89619` | 32611,32775 | candidate_off | Lolo `71251/90419` | 32610,32775 | candidate_off | 1 |
| 4 | Lolo `71251/90419` | 32610,32775 | candidate_off | Tilo `90012/1900002` | 32608,32775 | candidate_off | 2 |
| 4 | Blue Sharks `71184/130891` | 32624,32832 | candidate_off | Kent Castle Guard `71183/130894` | 32622,32831 | candidate_off | 2 |
| 4 | Blue Sharks `71184/130892` | 32630,32832 | candidate_off | Kent Castle Guard `71183/130893` | 32632,32831 | candidate_off | 2 |
| 4 | Blue Sharks `71184/130895` | 32586,32765 | candidate_off | Kent Castle Guard `71183/130898` | 32587,32766 | candidate_off | 1 |
| 4 | Blue Sharks `71184/130896` | 32586,32757 | candidate_off | Kent Castle Guard `71183/130897` | 32587,32756 | candidate_off | 1 |
| 4 | Blue Sharks `71184/130899` | 32619,32706 | candidate_off | Kent Castle Guard `71183/130901` | 32620,32707 | candidate_off | 1 |
| 4 | Blue Sharks `71184/130900` | 32612,32706 | candidate_off | Kent Castle Guard `71183/130902` | 32611,32707 | candidate_off | 1 |
| 0 | Zeno `50016/50059` | 32600,32914 | count0 | Zeno `50016/90067` | 32600,32914 | candidate_off | 0 |
| 0 | Zeno `50016/50059` | 32600,32914 | count0 | Serian `50112/87557` | 32600,32916 | candidate_off | 2 |
| 0 | Zeno `50016/90067` | 32600,32914 | candidate_off | Serian `50112/87557` | 32600,32916 | candidate_off | 2 |
| 0 | Dorin `60001/60009` | 32575,32946 | active | Lengo `70100/87553` | 32575,32946 | active | 0 |
| 0 | Dorin `60001/60009` | 32575,32946 | active | Fiin `70101/87554` | 32575,32946 | active | 0 |
| 0 | Dorin `60001/60009` | 32575,32946 | active | Judice `70102/87555` | 32575,32946 | active | 0 |
| 0 | Dorin `60001/60009` | 32575,32946 | active | Mona `70529/87556` | 32575,32946 | active | 0 |
| 0 | Lengo `70100/87553` | 32575,32946 | active | Fiin `70101/87554` | 32575,32946 | active | 0 |
| 0 | Lengo `70100/87553` | 32575,32946 | active | Judice `70102/87555` | 32575,32946 | active | 0 |
| 0 | Lengo `70100/87553` | 32575,32946 | active | Mona `70529/87556` | 32575,32946 | active | 0 |
| 0 | Fiin `70101/87554` | 32575,32946 | active | Judice `70102/87555` | 32575,32946 | active | 0 |
| 0 | Fiin `70101/87554` | 32575,32946 | active | Mona `70529/87556` | 32575,32946 | active | 0 |
| 0 | Judice `70102/87555` | 32575,32946 | active | Mona `70529/87556` | 32575,32946 | active | 0 |
| 0 | Secratary to the Mayor `70534/87848` | 32588,32952 | candidate_off | Village Manager `70528/87858` | 32588,32953 | candidate_off | 1 |
| 0 | Oasis Stuff `80001/130408` | 32647,32950 | scope_off | Pandora `70014/60801` | 32645,32951 | active | 2 |
| 0 | Coliseum Manager `50018/50086` | 32551,33006 | scope_off | Seal Merchant `80128/89623` | 32552,33004 | scope_off | 2 |

## 재산출·보존 한계

최초 오프라인 스냅샷은 지형0/4만 명시 로드해192개를 셌다. supported lazy-map3·62·237 각각1개는 누락이므로 전체 활성 수로 사용하지 않는다. 실제 default_terrain과 동일 LAZY_MAP_IDS를 사용한 최종은195개다. 변경전0/4 스냅샷은 보존했고, 변경전 register/_placement/setup_town 알고리즘만 임시 메모리에 복원하여 전체맵 baseline195개를 보정했다. 파일 rollback은 하지 않았다. 이 세 추가맵에는 근접쌍이 없어11→10 결론에 영향 없다. 최종은 수정 후 실제 소비 함수를 새 프로세스에서 재산출했다.

임시 계산은 `_work/tmp/npc_audit.py`와 provenance 추출을 사용했고 제품 validator/guard는 만들지 않았다. source hash는 결과 JSON의 original/before/after에 있다. 최종 원본 함수 흐름의 상태·좌표를 조사했지만 서버 패킷·게임 화면·입력·실제 플레이 및 full original 동등성은 이 감사에서 UNKNOWN이다.
