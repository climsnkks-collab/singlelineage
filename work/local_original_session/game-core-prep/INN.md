# 여관: 근거와 구현 경계

2026-10-28 조사. 조사 worker는 코드·게임·포트·클라이언트를 실행하지 않았다. 원문 확인은 실제 소비·화면·입력 PASS가 아니다. 검증 절은 메인 담당이 갱신한다.

## 결론

클라이언트 dialogue/UML/아이템 카탈로그 → 기존 공식 데이터·공식 API·사이트 검색 → L1J 순서로 확인했다. 원문에서 방/홀/반납/입장 메뉴, 숫자입력 패널, 대여 4시간과 기간 내 열쇠당 10아데나 반환이 확인된다. 가격 숫자·숫자확인 패킷·입장 조건·방별 좌표·정확한 회복 계산은 미확인이다. 기존 M2의 100아데나 즉시 full HP/MP는 과거의 명시적 local_policy이며 원본 규칙으로 승계하지 않는다.

## 원문: 메뉴와 후속 페이지

원문은 `work/local_resource_provider/assets/data/dialogue.csv:223-247`. UML은 `C:/Users/Chansol/Documents/Codex/2026-09-07/d-lineage-classic/outputs/decrypted-pack/data_0/data/uml/inn*.uml` 보존 해독본이다. 기존 `tools/local_original_session/data/m2/npc_menus.json`이 inn 현재 catalog와 보존 해독본의 동일 비교를 기록한다. 아래 구조는 원문을 직접 읽어 확인했다.

| stem | 원문/구조 | 확인 범위 |
|---|---|---|
| inn | room=방을 대여한다, hall=홀을 대여한다, return=대여한 방이나 홀을 반환한다, enter=방 또는 홀로 들어간다 | UML action literal 확인; 실제 클릭 송신 미시험 |
| inn1 | 악인에게 줄 방 없음 | 문구 확인; 실제 lawful 경계 미확인 |
| inn2 | 방은 한 사람당 var1 아데나, 열쇠 몇 개? | NpcTalk_InputNum, custom=input_num_inn; 가격은 서버 공급 변수 |
| inn3 | 돈 부족 | 문구 확인 |
| inn4 | 동행자에게 열쇠 분배 후 계단; 대여 4시간, 기간 내 반환 열쇠 개수당 10아데나 | 기간·환불 명시; 실제 거래/입장 미시험 |
| inn5/inn6 | 이미 방 대여/빈방 없음 | 문구 확인 |
| inn7 | 홀은 한 사람당 var1 아데나, 열쇠 몇 개? | inn2와 같은 숫자입력 패널 |
| inn8/inn9 | 이미 홀 대여/빈 홀 없음 | 문구 확인 |
| inn10 | var1 아데나 반환, 반환되지 않은 열쇠는 이후 사용 불가 | 임대 단위 무효화 명시; 실행 미시험 |

inn2/inn7에는 후속 action literal이 없다. 임의 문자열을 원본 숫자확인 action으로 확정하지 않는다. inn4의 계단 문구와 inn의 enter 메뉴는 모두 존재하지만 각 실제 native 소비 계약은 미확인이다. 방과 홀의 인원 상한·가격 차이·재고 수는 원문으로 확정할 수 없다.

`dialogue.csv:1152` auction2_3은 아지트에서 여관처럼 평소보다 HP/MP 회복 속도가 빠르다고 설명한다. 정확한 수치·주기는 제공하지 않는다.

## 원문: 열쇠 ID와 이름

근거는 `tools/local_original_session/data/catalog/items_all.json`의 client_original 및 기존 `work/source_game_data/native-dump-v1.jsonl` 참조다. 이름은 `work/local_resource_provider/assets/data/desc.csv`와 조인된다. 모두 client inventory icon59, ground raw f6=19다. 아래는 클라이언트 ID이며 L1J ID가 아니다. 이름/아이콘 확인은 스택성·거래·사용 효과 확인이 아니다.

| 마을 | 방 ID / 정확 한글명 | 홀 ID / 정확 한글명 | 이름 토큰 |
|---|---|---|---|
| 말하는 섬 | 10100 여관 열쇠(말하는 섬 마을) | 10101 여관 홀 열쇠(말하는 섬 마을) | $15502/$15503 |
| 은기사 | 10102 여관 열쇠(은기사 마을) | 10103 여관 홀 열쇠(은기사 마을) | $15504/$15505 |
| 글루딘 | 10104 여관 열쇠(글루딘 마을) | 10105 여관 홀 열쇠(글루딘 마을) | $15506/$15507 |
| 우드벡 | 10106 여관 열쇠(우드벡 마을) | 10107 여관 홀 열쇠(우드벡 마을) | $15508/$15509 |
| 기란 | 10108 여관 열쇠(기란 마을) | 10109 여관 홀 열쇠(기란 마을) | $15510/$15511 |
| 하이네 | 10110 여관 열쇠(하이네 마을) | 10111 여관 홀 열쇠(하이네 마을) | $15512/$15513 |
| 아덴 | 10112 여관 열쇠(아덴 마을) | 10113 여관 홀 열쇠(아덴 마을) | $15514/$15515 |
| 오렌 | 10114 여관 열쇠(오렌 마을) | 10115 여관 홀 열쇠(오렌 마을) | $15655/$15656 |

일반 이름 여관방 열쇠와 켄트 전용 키는 이번 client 카탈로그 열쇠 목록에서 확인되지 않았다. windawood는 서버 지역 ID이며 벨리사 좌표는 L1J 우드벡 여관 후보다. 우드벡 키와의 연결은 local_policy로 구분한다.

## NPC 대응

기존 `tools/local_original_session/data/{m2,m4,m5}/town_npcs.json` 재사용. 아래 ID·배치는 L1J 참고이며 native template ID가 아니다. inn/Inn1 stem은 공통이다.

| 서버 지역 | L1J ID / 이름 | map,x,y | 원본 이름/식별 경계 |
|---|---|---|---|
| 말하는 섬 | 70012 Selena | 0,32596,32929 | native 이름토큰 매칭 없음 |
| 글루딘 | 70019 Lolia | 4,32627,32758 | native 이름토큰 매칭 없음 |
| windawood | 70070 Velisa | 4,32618,33166 | desc $912 여관대여^벨리사, 명시 이름 sprite989; template 미확인 |
| 기란 | 70031 Molly | 4,33431,32785 | desc $1250 여관대여^몰리; template 미확인 |
| 오렌 | 70065 Enke | 4,34062,32252 | desc $1828 여관대여^엔케; template 미확인 |
| 하이네 | 70084 Elly | 4,33599,33273 | desc $1539 여관대여^앨리; template 미확인 |

켄트는 기존 m5 npcs에 inn 기본메뉴 행이 없다. m5 기란·오렌·하이네 원배치의 terrain_can_stand=False도 보존하므로 제품 배치는 기존 마을 소비 경로의 조정 여부와 구분한다.

## 방 지도: 클라이언트와 L1J가 다름

클라이언트 `work/local_resource_provider/assets/data/region.jsonc:308-327`이 아래 번호를 명시한다.

| 지역 | 방 map | 홀 map |
|---|---|---|
| 말하는 섬 | 30000 | 30200 |
| 은기사 | 30250 | 30450 |
| 글루딘 | 30500 | 30700 |
| 윈다우드 | 30750 | 30950 |
| 기란 | 31000 | 31200 |

현재 materialized `work/local_resource_provider/assets/map`에는 0,1,2,4~13,19~21,43~51만 있고 여관 번호가 없다. `world_terrain.py` DEFAULT_MAP_IDS/LAZY_MAP_IDS와 `world_maps.py` 전환도 여관을 지원하지 않는다. region 등록은 자원·통행·전환·원본 화면 지원 증거가 아니다. 오렌·하이네 region 지도 연결은 이번 범위에서 미확인이다.

L1J `db/l1jdb_m10.sql:14959`의 말섬 방16384/홀16896 등은 원본 번호와 다르므로 원본 지도라 주장하지 않는다. 입장 미지원 거절은 OPEN 경계다. NPC 근처를 방으로 간주하는 근거는 없다.

## 공식 확인

기존 `tools/local_original_session/data/official/items.json`에서 위 열쇠 레코드를 찾지 못했다. 2026-10-28 [공식 item API](https://api-goats.plaync.com/linclassic/v2.0/game/item/10100?locale=ko-KR)의 10100,10104,10114를 HTTP로 읽었고 모두 빈 JSON `{}`였다. 빈 응답은 존재하지 않음의 증명이 아니다. web 도구는 API 접근에 실패하여 일반 HTTP 읽기로 확인했다.

공식 도메인 한정 검색 `site:lineageclassic.plaync.com 여관 아데나`, `여관 열쇠`에서 가격·회복 근거를 얻지 못했다. 검색에서 나온 비공식 자료는 규칙으로 채택하지 않았다.

## L1J 참고와 local_policy

참고 루트 `D:/SingleLineageRef/l1j-en-classic/`:

- `src/l1j/server/server/clientpackets/C_NPCAction.java:342-347`: room/hall/return/enter 본문이 비어 있다. 임대료·환불·수량의 근거가 아니다.
- `src/l1j/server/server/templates/L1Inn.java`: 방/열쇠/숙박자/기한 저장 템플릿이며 완전 동작 증거가 아니다.
- `src/l1j/server/server/model/map/Maps.java:16-32`: 여관 내부 map 집합만 isInInn으로 판정한다. NPC 거리 조건이 없다.
- `model/HpRegeneration.java:128-129`, `model/MpRegeneration.java:88-89`: 자연회복 계산에 hotel 설정 가산. `config/rates.properties:12-13,33-34`의 HP5/MP3는 초당 즉시 지급 규칙이 아니다.

현재 구현 결정은 방/홀 100A, 열쇠1개, NPC3칸 이내에서 기존 자연회복 threshold 충족 시 HP5/MP3 가산이며 각각 명시적 local_policy다. 회복 주기는 기존 자연회복 소비 경로를 따른다. 4시간/기간 내 반납10A만 클라이언트 원문 근거가 있다. proximity 회복을 방 입장·원본 여관 복원 완료로 표시하지 않는다. 원본 방 기능에는 숫자확정 native 소비, 실제 키 발급/반납 무효화, 내부 map 자원/좌표/전환, 내부 회복, 저장/재접속/만료 수명이 남는다.

## string.csv 조사

`work/local_resource_provider/assets/data/string.csv`도 여관·열쇠·대여·반납·빈방 문구로 검색했다. 여관 관련 확인 행은 UI_ServerTransfer 안내다. 12039행/ID12093은 여관에서 서버 이전 신청 불가, 12040행/ID12094는 서버 이전 후 여관 열쇠·편지지 자동 삭제를 명시한다. 혈맹 이전 안내 12424행/ID12482와 12428행/ID12486에도 같은 종류의 제한·삭제 문구가 있다. 이는 서버 이전 UI 설명이며 여관 요금·대여시간·반납량·회복 수치의 근거가 아니다. 이번 검색에서 임대/입장 실패용 별도 숫자 메시지 ID는 찾지 못했다. 실제 임대 페이지 문구는 dialogue.csv의 inn_* 키, 열쇠 표시명은 desc.csv의 $15502 등 토큰에 있다. CSV 행 번호와 첫 열의 string ID를 구분하며 미발견을 메시지 부재의 증명으로 확대하지 않는다.
## 구현

선택 기능 `world_feature_town.py`에서 여관 메뉴를 소비하고, `world_inn.py`가 임대·열쇠·저장·회복을 소유한다. `world_town_services.py`는 글루딘에도 원본 inn 메뉴를 연결한다. `data/m2/m4/m5/town_services.json`의 여관 6개(말섬·글루딘·우드벡/윈다우드·기란·오렌·하이네)에 정확한 클라이언트 열쇠 이름을 등록했다. 켄트는 원본 대응 여관 배치가 없어 만들지 않았다. M5 재생성 시에도 여관 정책과 한글 이름을 유지한다.

현재 LOCAL 동작은 방/홀 메뉴 선택 즉시 100A를 내고 해당 열쇠 1개를 받는 것이다. 한 캐릭터에 임대 하나이며, 수량 입력 패널·동행자 배분·객실 재고는 구현하지 않았다. 열쇠의 ID·이름·icon59는 원본 근거이며 나머지 ItemInfo 필드는 기존 starter prototype을 재사용한 LOCAL 표현이다. 유효한 열쇠를 소유하고 해당 NPC의 3칸 안에 있으면 기존 자연회복 HP/MP threshold에서 HP5/MP3를 가산한다. 기존 회복 주기를 바꾸거나 즉시 완전 회복하지 않는다.

아데나 차감과 열쇠 추가/제거는 기존 인벤토리 CAS를 사용한다. 같은 시험/사용자 프로필의 `inn.json`에 캐릭터·NPC 배치·실제 발급 key UID·종류·절대 만료시각을 저장하고, `inn-pending.json`은 저장 중 실패한 정확한 이전/다음 인벤토리를 앞으로 복구한다. 기존 장비 anchor가 제거되면 코어의 인벤토리/장비 공동 저장 경로를 사용한다. 접속 중 만료 타이머와 재접속 만료 처리가 열쇠를 제거하며, 로그아웃/서버 종료 때 소유 타이머·wrapper를 정리한다. 기간 내 해당 여관에서 반납하면 열쇠를 제거하고 10A를 돌려준다.

지원하지 않는 `enter`는 해당 요청만 `INN_INTERIOR_MAP_UNSUPPORTED_RENTAL_REST_ONLY`로 거절한다. 방 입장·퇴장 전환은 구현하지 않았으며 임의 외부 맵으로 이동시키지 않는다.

## 검증

단위시험: `python -m unittest tools.local_original_session.world_inn_tests tools.local_original_session.world_town_services_tests -q` — 44개 OK. 임대/반납·돈 부족·정확한 열쇠명·유효기간·거리·소유권에 따른 회복, 저장 중단 전/후 복구와 중복과금 방지, 온라인/재접속 만료 정리를 포함한다. 만료 시험은 시계를 주입한 개발 시험이며 실제 4시간 경과 패킷 PASS가 아니다.

봇은 다음 명령을 방/홀 각각 순차 실행했다. 원본 클라이언트는 실행하지 않았다.

```powershell
$env:SL_TEST_TIME_SCALE='10'
$env:SL_TEST_PORT_BASE='40000'
python -X utf8 -B C:\Users\Chansol\AppData\Local\Temp\claude\D--claude\0483de89-75e7-4b94-84b8-fb31fe00f575\scratchpad\fastbot\run_fast.py hunt_bot_inn --timeout 20 --recovery-timeout 180 --rental-kind hall
python -X utf8 -B C:\Users\Chansol\AppData\Local\Temp\claude\D--claude\0483de89-75e7-4b94-84b8-fb31fe00f575\scratchpad\fastbot\run_fast.py hunt_bot_inn --timeout 20 --recovery-timeout 180 --rental-kind room
```

고정 최종 조합 결과: [홀 summary](../runs/hunt-inn-l3mtpv8z/summary.json), [방 summary](../runs/hunt-inn-h2557cmq/summary.json) 각각 **15/15 SUCCESS**, cleanup=true, handler/hook 오류 없음. 두 실행의 선정 source 해시 조합은 같고 실행 중 변경은 없다. 정확한 source 해시·시작 저장·실제 패킷 순서는 각 summary와 같은 폴더의 로그에 보존한다. 종료 후 40000/42030 LISTEN은 0이었다.

각각 새 시험 사본의 기존 test_knight1000A를 사용했다. 기존 PositionStore로 여관 옆 시작 위치, ProgressStore로 HP1/max200·MP1/max200을 FIRST 전에 준비했으며 열쇠·임대·돈을 주입하지 않았다. 정상 FIRST→로그인→선택→월드→현재 NPC→inn 메뉴→room/hall 요청으로 서버 발급 UID65572와 정확한 template10100/10101·이름을 수신했다. 비용1000→900A, HP1→13(기본7+여관5), MP1→5(기본1+여관3)를 wire/state로 확인했다. 정상 Quit 후 서버를 닫고 같은 저장을 seed=False로 새 FIRST 접속해 실제 키 UID·기한·돈·위치와 최초 status13/5가 복원됐다. 그 뒤 실제 return 요청으로 키 제거·임대 해제·900→910A를 저장했다.

이 PASS 범위는 준비한 여관 옆 시작 저장에서 말섬의 방/홀 대여→회복→재접속→반납이다. 최초 이동, 다른 마을의 실제 패킷 이용, 실제 4시간 경과, 원본 화면·클릭·숫자패널·방 입퇴장은 미검증이다. 다른 마을 키/정의는 위 단위시험 범위다. 최초 방 시험 `../runs/hunt-inn-f2m1wz4_/summary.json`도 15/15 SUCCESS·정상 cleanup으로 보존했으며, 최종 주석 수정과 시작 시점 통보가 엇갈려 위 최종 조합으로 다시 확인했다.

별도 회귀 묶음에서 `world_m4_tests`의 loopback 시험을 단위시험으로 오분류해 12000/14030에서 실행한 뒤 해당 Python PID15976만 중단(exit1)했다. 이 중단 실행은 PASS에 포함하지 않는다. 원본 클라이언트·사용자 프로필을 실행/수정하지 않았다. 저장 사본 `../runs/m4-gludin-{n_n0sbb4,x2d27me2,1copsqak,rpeqqds2,sdltnwo3,qj9y0usn}`과 세션 원출력을 보존한다. 후속 시험 전 관련 포트 LISTEN이 없음을 확인했다.

