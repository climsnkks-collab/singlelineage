# M4 사냥 구역 데이터 확장

2026-10-27. 기존 `main` 작업 트리에서 M1/M3/M4 표를 확장한다. 원본 클라이언트 실행·화면 캡처·사용자 저장 변경·커밋은 하지 않는다. 이 문서의 봇 결과는 로컬 서버 패킷과 개발 시작 저장 범위이며 원본 화면·입력 동등성 판정이 아니다.

## 출처와 적용

클라이언트 `native-dump-v1.jsonl`·NPC/SPR 대응 자료로 Classic template와 외형을 연결하고, `data/official/monsters.json`으로 이름·레벨·지역·드롭 구성을 우선 확인한다. 누락된 능력치·스폰·확률·수량은 `D:/SingleLineageRef/l1j-en-classic/db/l1jdb_m10.sql`을 참고한다. 밀도 축소·통행 가능한 사각형 선정 등은 `local_policy`로 구분한다. L1J 값을 클래식 공식값으로 취급하지 않는다.

번호 대응 기준은 [MAP0_MONSTER_CATALOG](MAP0_MONSTER_CATALOG.md)와 [MAPPING_SCOPE](MAPPING_SCOPE.md)를 따른다. Classic template·sprite·L1J npcid·공식 ID·실행 UID를 서로 바꾸어 쓰지 않는다. 실행 가능한 드롭은 로더에 존재하는 아이템으로 제한하며 미지원·미확정 드롭은 보류 원문을 보존한다.

기존 M1은 그대로 로드하고, 던전은 기존 `with_dungeon_data` 경로, map4는 기존 `-MapExp 2` (`SL_EXPERIMENT_MAP=2`) 경로를 사용한다. 관심 반경에 따른 활성화와 `world_terrain.can_stand(...) is True` 배치 검사를 재사용한다. 청크 bbox와 `can_stand`는 정적 지형 범위이며 문·동적 점유·원본 전체 navigation의 증명이 아니다.

## 구역별 표와 검증 결과

|표|추가 종 정의 / 고유 종 증분|추가 스폰 그룹 / 정원|최종 종 정의 / 그룹 / 정원|
|---|---:|---:|---:|
|M1 map0|7 / 5|33 / 92|11 / 37 / 108|
|M3 map1·2|5 / 3|5 / 9|11 / 14 / 35|
|M4 map4|16 / 10|22 / 36|19 / 25 / 45|

고유 종 증분은 기존 세 표 전체의10종을 제외하고 M1→M3→M4 순서로 중복 template을 제거한 수다. 합계 **새 고유 template 18종, 60그룹, 정원137마리 추가**, 최종28종·76그룹·188마리다. 같은 NPC의 다른 지역 배치를 새로운 고유 몬스터로 세지 않는다.

- map0: 북쪽·북서·서·남서·남동 필드. 코볼트249, 난쟁이4, 오크 전사2, 좀비27, 해골29, 돌 골렘5, 셸로브17을 추가했다. 기존4그룹의 정원·리젠은 유지하고 막힌 칸을 포함했던 사각형은 내부 통행 구역으로 좁혔다. 이전 rect는 표에 보존했다. 모든37그룹의11,149개 선택 칸은 정적 통행 가능하고 마을 기준점에서 도달 가능하다.
- 던전1층: 장로7. 던전2층: 늑대인간8, 셸로브17, 해골도끼병277, 해골창병278. 신규5그룹은 원 L1J 배치를 근거로 축소하며 계단 도착점과 이격한다.
- 글루디오 외곽: 기존 언데드3종의 배치를 추가 분산한다. 요정숲은8그룹, 화전민 밖 오크숲은8그룹을 추가한다. 요정숲의 고블린245·오크 궁수1·코볼트249·난쟁이4·늑대인간8 배치는 L1J 기반 `local_policy`다. 현재 공식 저장본이 해당 지역 출현을 지지하지 않으므로 `official_region_supported=false`, 클래식 실제 출현 UNKNOWN을 명시한다.

M3/M4의 신규27그룹은 각7×7=49칸 전부 `can_stand=True`인 사각형이다. 기존 M3/M4 사각형의 부분 차단은 원정책대로 남기고 런타임 배치 검사에서 제외한다. 같은 template이 여러 표에 있을 때 실제 소비되는 몬스터 필드가 동일한지도 확인했다. 기존 M3 우선·M4 base 우선 병합을 바꾸지 않았다.

세 핵심 표(`monsters/spawns/drops.json`)에서 실제 파서가 소비하는 출처 셀은 client505(34.1%), official41(2.8%), L1J636(42.9%), local_policy300(20.2%)다. 분모1,482셀은 세 표의 전체 활성 정의를 기준으로 하며 중복 template의 표별 정의도 센다. 미소비 메타·보존행·unresolved·action_speed·alignment는 제외한다. 출처 비율은 검증률이나 공식 동등성 비율이 아니다.

세부 대응·SQL줄·정책은 [M1 출처](../../../tools/local_original_session/data/m1/EXPANSION_SOURCES.md), [M3 출처](../../../tools/local_original_session/data/m3/EXPANSION_SOURCES.md), [M4 출처](../../../tools/local_original_session/data/m4/EXPANSION_SOURCES.md)에 둔다. 새 속도 정의와 M1 성향 표를 연결했으며 로더/관심 스폰 제품 코드는 수정하지 않았다.

## 검증

- 최종 정적 관련45 tests OK: game_data7, expansion_data3, M3 7, M4Data5, effect/map contract5, alignment15, spawner3. M3 item67 보류 뒤 직접 영향15개를 다시 실행해 OK였다. M3의 옛 고정 rect 기대값5건은 새 로컬 사각형 선정 근거에 맞춰 고쳤으며 첫 실패 로그도 보존했다.
- 모듈별 전체 회귀와 새 구역 봇은 `SL_TEST_PORT_BASE=20000`에서 일회성 시험 worker 하나가 순차 실행한다. 원로그: `work/local_original_session/runs/expansion-regression-20261027/`.
- 현재 기존 `inventory_store.py`의 부모 소스 핀과 작업 중인 `inventory.py`가 불일치하여 `INVENTORY_STORE_PARENT_SOURCE_CHANGED`가 발생한다. 기존 `inventory_observe.py` 소비자도 부모 소스 불일치를 보고했다. 이 파일들은 이번 지정 수정 범위 밖이며 검사 완화·monkeypatch로 우회하지 않았다. 다만 봇의 fresh kit 경로는 이 오류 없이 FIRST/login/select를 통과했다.
- 첫 봇 `m1_field_62007`은 FIRST/login/select·인벤토리 수신 뒤 `NAVIGATION_STALLED`로 종료했다. 고레벨 사냥 구역을 피하는 기존 봇 정책과 새 배치가 겹치는 경로를 조사하고 다른 안전한 신규 구역으로 재확인한다. 원결과: `runs/expansion-bot-x3as1be4/result.json`, handler_errors 없음·정리 완료.
- 재확인 봇 **SUCCESS**: 신규 서쪽 필드 `m1_field_62008`에서 FIRST/login/select → 고블린4마리 수신 → 이동2회·공격1회·처치1회 → 아데나10 드롭·줍기1회·저장+10을 확인했다. NPC UID268435464/generation2 → ground UID268435476/owner1의 실제 원장 연결을 대조했다. handler/reward/pickup errors 없음, cleanup_complete=true. [원결과](../runs/expansion-bot-1n76brsg/result.json). 기존 고블린 종의 새 사냥 구역 성공이며 신규18종의 송신 성공을 뜻하지 않는다.
- 실제 송신 차단: `npc.py:26`의 `WORLD_MONSTERS`는 기존4쌍, `DUNGEON_MONSTERS`는 기존6쌍만 허용한다. `NpcSpawn.__post_init__`는 map4도 거절한다. `world_ai_tests.test_leash_returns_home`에서 신규 template 송신 시 `NPC_EXPLICIT_SPR56_TEMPLATE0_ONLY`가 확인됐다. 이 파일은 요청된 수정 가능 범위 밖이다. 표의 신규 종을 실제 출현 완료로 주장하거나 시험을 축소해 숨기지 않는다. 신규 종·map4 송신 연결과 전체 회귀 성공은 미완료다.
- 전체 회귀 최종: 당시 존재한 **80모듈 전부 시도**, 최신71모듈 OK / 8모듈 실패 / 1모듈 수집 시간 초과. 완료 unittest1,522개 및 별도 lane4 custom2사례·23검사를 실행했다. 중복 재실행을 새로운 시험 수로 더하지 않았다. [최종 집계](../runs/expansion-regression-20261027/summary.json).
- 남은 실패: 기존 부모 소스 핀 관련6모듈(`broker`, `inventory_observe`, `inventory_store`, `inventory`, `item_use_session`, `launcher`), 신규 몬스터 송신 제한의 `world_ai_tests`1오류, 기존 `_world_replace_kit` fixture 누락의 `world_companion_revive_tests`3오류. `manual_move_commands_tests`는600초에 시험프로세스 강제 종료·수집 미완으로 남겼다. 정상 종료로 표시하지 않았다.
- 직접 영향 시험 수정 뒤 재확인: `npc_ai_range`16개, `world_spawn`10개, `world_terrain`7개 OK. 기존4종 비선공 정책, 실제 여러 종의 wire 수신, 별도 확인된 차단칸 판정은 유지했다. `world_lane4_connection_tests`는 unittest0개였으므로 기존 CLI로 별도 실행해2사례·23검사 SUCCESS를 확인했다. [원로그](../runs/expansion-regression-20261027/lane4-custom.log).
- 최종 직접 영향9모듈80 tests OK. 시험 worker 마감 뒤20000/22030 LISTEN 없음도 확인했다. 지정 범위 밖 파일의 수정 승인 응답은 없어 부모핀·NPC 송신 목록·revive 제품/fixture를 변경하지 않았다. 따라서 **데이터 및 신규 구역1곳 봇 검증 완료 / 확장 전체와 전체 회귀 완료 기준 미충족**이다.

## 변경 파일

- `data/m1/monsters.json`, `spawns.json`, `drops.json`, `action_speed.json`, `alignment.json`, `EXPANSION_SOURCES.md`.
- `data/m3/monsters.json`, `spawns.json`, `drops.json`, `EXPANSION_SOURCES.md`.
- `data/m4/monsters.json`, `spawns.json`, `drops.json`, `EXPANSION_SOURCES.md`.
- 관련 시험: `game_data_tests.py`, `world_m3_data_tests.py`, `world_m4_tests.py`, `world_effect_map_contract_tests.py`, `npc_ai_range_tests.py`, `world_spawn_tests.py`, `world_terrain_tests.py`, 새 `world_expansion_data_tests.py`, 새 `hunt_bot_expansion.py`.
- 이 문서. 시험 출력은 기존 `runs/` 아래 보존한다. 다른 작업자의 기존 dirty/untracked 파일은 이번 변경 목록에 포함하지 않는다.

## 미확인

원본 외형·화면·입력·전체 navigation, 종별 독·마법·무리 AI, 신규 구역 간 실제 보행 연결, 원본 정확한 밀도·능력치·드롭확률, 30분 원본 플레이는 미확인이다. 이번 요청에 따라 원본 실행·화면 캡처는 하지 않았다. 요정숲5그룹의 클래식 출현도 미확인이다.
