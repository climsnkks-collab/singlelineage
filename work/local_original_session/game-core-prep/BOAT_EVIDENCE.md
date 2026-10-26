# 배 이동: 말하는 섬 ↔ 글루딘

2026-10-27 사용자 지정 REA. **정적 근거 정리이며 게임·입력·패킷·저장 동작 PASS가 아니다.** 기존 [M2_NPC_MENUS](M2_NPC_MENUS.md):35,73,124의 배표 상인과 [MAP_TRANSITION_EVIDENCE](MAP_TRANSITION_EVIDENCE.md):164–232 및 run389에서 출발했다. L1J 소스는 별도 backend 참고로 구분한다. 산출물은 [run397_boat_travel](../../local_server_rea_20261016/run397_boat_travel/)에 있다.

## 출처와 동일성

클래식 분석 기준은 기존 26.09.29.2001/복원 CONTROL 선언 `9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`다. 기존 run380/389의 복원 reader·REA 산출물을 재사용해 필요한 구간만 정적 디스어셈블했다. 원본 전체를 새로 복원하거나 CONTROL 동일성을 다시 입증한 것은 아니다. 아래 native 주소는 이 **복원 CONTROL RVA**이며 현재 디스크 LC·프로세스 VA/상태를 뜻하지 않는다. run380의 디스크 짧은 window 불일치 기록을 보존한다. REA `binary_session({})`은 open=false였으며 새 native session/게임을 열지 않았다.

L1J는 읽기 전용 `D:/SingleLineageRef/l1j-en-classic`, HEAD `103e6f6c9dd83545959d8e87d3f59f8de1f40ef0`다. SQL/Java 원문·원줄은 [l1j_source_excerpts.md](../../local_server_rea_20261016/run397_boat_travel/l1j_source_excerpts.md)에 보존했고, 정책 차이는 [l1j_findings.md](../../local_server_rea_20261016/run397_boat_travel/l1j_findings.md)에 정리했다. 이 fork의 시간·가격·ID·옛 wire를 클래식 공식값으로 선언하지 않는다.

## 배표 상인과 구매 입력

기존 원본 메뉴 후보는 exact `ShipEvM3`이며 `buy`, `sell`, link `ShipEvM4`를 가진다. `ShipEvM4_1`의 ‘이곳, 말하는 섬 선착장’ 텍스트로 말하는 섬 후보를 좁혔다. L1J70011의 `shipEvI3/shipEvI1`과 exact 문자열이 다르며 NPC70011/70022 번호 자체도 L1J namespace다. `ShipEvM4` link를 탑승 서버 action으로 바꾸지 않는다([M2_NPC_MENUS](M2_NPC_MENUS.md):35,73,124).

역방향은 원본 `ShipEvM1`의 말하는 섬행 안내·`buy/sell`, link `ShipEvM2`와 M2의 글루디오 선착장 문구로 대응한다. 두 방향의 대사는 ‘표 없으면 탑승 불가’와300아데나를 명시한다. 이는 **자원에 적힌 설명**이며 정상 서버의 검사/매매가격 관측이 아니다. M2/M4의 한국어·대만어 시간표는 한 시간 차이가 나므로 단일 공식 시각으로 합치지 않는다([client_resources.md](../../local_server_rea_20261016/run397_boat_travel/client_resources.md)의 원dialogue.csv:717–740, UML M1–M4).

기존 일반 대화·상점 경로는 `C2S4E43(선택 NPC UID) → S2C4E44(대화 context/stem) → C2S4ED4(action buy/sell, 실제 context·cookie) → S2C4E48/4EE7(목록) → C2S4ED1(mode5/6, context·rowkey·수량)`이다. 메뉴 `buy/sell`은 일반 초기 command map에서 HACTION fallback으로 가지만, 배표 상인의 정상 context·실제 품목·가격·거래/표 발급을 관측한 것은 아니다. BUY required outer2/row6·7·8의 공식 producer값은 여전히 UNKNOWN이다. Pandora 로컬 성공을 배표 상인 성공으로 확대하지 않는다([M2_NPC_MENUS](M2_NPC_MENUS.md):102–113,170–202).

## 클래식 추가 정적 연결: 표·선착장 포털·배 전용 패킷

클래식 CommonItem 원자료의 배표는 **item124=글루디오 영지행 배표(`$314`), item125=말하는 섬행 배표(`$315`)**다. L1J40299/40298와는 토큰·표 이름으로 대응하며 숫자ID는 서로 다르다. 기존 ShipInfo의 row1은 `f2=0,f3=5,f4=124`, row2는 `f2=4,f3=6,f4=125`다. 따라서 이 두 행의 항구/선내 후보는 별도의 클래식 원자료로도 확인된다. 이것이 일반 saved map/raw f1/alias의 동일성이나 모든 맵번호 대응을 입증하지는 않는다. 원본 `ship_data.jsonc:13–14,26–27`의 wharf world5/6은 선내 표시 자료이며 그 좌표를 본토/말하는 섬 도착칸으로 바꾸지 않는다.

| 클래식 ShipInfo 원자료 | row1 / 글루디오행 | row2 / 말하는 섬행 |
|---|---|---|
| f6 Box의4값 | 32625,32976,32636,32985 | 32535,32721,32550,32735 |
| f7 Point / f8 | 32735,32797 / 4 | 32735,32797 / 0 |
| f9 RandomPoint의3값 | 32569,32726,5 | 32632,32963,5 |
| f11 / f12 Point | 0 / 32631,32966 | 4 / 32572,32724 |
| f13 ScheduleTime raw | `1111111`; (1,30),(4,30)…(22,30); f3=60,f4=5 | `1111111`; (0,0),(3,0)…(21,0); f3=60,f4=5 |

이는 기존 parse의 **원자료 값**이다. Box 경계 포함 여부·Point/RandomPoint의 실제 소비·날짜/게임시간 기준·체류/여행 분 단위 의미·정상 서버 운항과의 일치는 native consumer 또는 해당 실행으로 판정해야 한다. 특히 L1J의 선내 도착칸과 일부 좌표가 다르므로 L1J 값으로 덮어쓰지 않는다.

| 접점 | 복원 CONTROL에서 확인한 연결 | 아직 미확정 |
|---|---|---|
| 선착장 입력 | `534E60`의 map portal 목록에서 ShipPortal RTTI로 cast(`534F1C/534F2B`)→`52F1F0` 영역 판정(`534F8E`)→성공 시 portal+70 읽기(`534FD7`) | 정상 플레이의 실제 호출 시점·부두 좌표·거리/표/시간에 대한 공식 서버 거절 조건 |
| 탑승 요청 | `535020`은 위 값을 DTO+18에 저장, `535023 edx=4EF8`, `535030→27D620` 송신. RTTI **CS_ENTER_SHIP_REQ**. f1은 **required int32**. `75D2C0` writer→1023F0은 tag08/sign-extension을 사용하며75D3E0이 presence bit1을 검사 | 표 더블클릭 요청과 동일시하지 않음. 실제 서버 수신·소비·도착 응답은 미관측 |
| 출항 알림 | `295BE1`의 factory vtable11A8578→`295BF8 edx=4F0E`→`295C00→292F80` 등록. parser318740의 RTTI **SC_SHIP_START_NOTI**와 global1801980→2770B0 dispatch. f1은 required signed i32(+18), presence bit1 | 이 알림이 실제 ShipSubsystem의 어떤 구독자를 통해 운항/도착으로 이어지는지 미연결. f1의 정상값·업무 의미도 UNKNOWN |
| 잘못 합치면 안 되는 이벤트 | ShipSubsystem5778D0에서 설치하는57AF20은 **On_SC_PUT_DELAYED_ANIMATION_NOTI**(global1801EC0) | START(global1801980)와 다른 이벤트다. delayed animation callback을 배 출항·도착 consumer로 채택하지 않음 |

요청 원문은 [client_ship_protocol.json](../../local_server_rea_20261016/run397_boat_travel/client_ship_protocol.json)의 함수534E60/75D2C0, 표·ShipInfo는 [client_asset_rows.json](../../local_server_rea_20261016/run397_boat_travel/client_asset_rows.json)에 보존했다. 수신 등록·타입 원문은 같은 run의 `client_ship_registry.json`, `client_ship_start_registration.json`, `client_ship_start_types.json`에 있다. 이 JSON의 RVA/항목은 로컬 정적 근거 식별자이며 REA MCP runtime Evidence ID가 아니다.

입력의 상위 연결은 `531795 CharacterData getter→+258 위치 delegate→5317B4 callback534E60→5317CD 등록`이다. ShipPortal ctor546990은 다섯 번째 인수를+70에 저장하고, 호출535ACE/535AD1은 rectangle node+1C를 전달한다. **node+1C를 만드는 앞 생산자와 ShipInfo key의 동일성은 미확정**이다. 따라서4EF8.f1을 임의1/2(ShipInfo key),124/125(표),5/6(선내map)으로 만들지 않는다. 직접 확인한 producer에는 표 lookup/수량 감소가 없지만 다른 callee/서버의 표 검사가 없다는 전역 부재 주장은 아니다.

## 클래식 선내 대기: 닫힌 시간 계산과 남은 도착 인과

`578359`는 ShipInfo+44(f2)와 현재 resolved Map+718을 비교해 항구 쪽 ship을 갱신한다. `578DB0`은 selected ship(this+40)이 있고 ShipInfo+48(f3)이 현재 resolved map과 같아야 시간창을 검사한다(`578EC4..578ED2`). 이 두 소비가 각각 위 원자료의 항구0/4와 선내5/6을 뒷받침한다.

`578EFA..578F3E`는 날짜·시간쌍으로 만든 분값에 ScheduleTime+38(f3=60)을 더한 시작값과 +3C(f4=5) 길이를100ns 계열 상수로 계산해 `start <= now < end`를 검사한다. 즉 두 row의 **시간쌍+60분부터5분 창**을 계산하며, 대사의 한 시간 대기 구간과 같은 구간으로 읽지 않는다. `5781A0 UpdateVoyageWharf`는578DB0이 참일 때 `duration*60-60`을 task 인수로 만든다(`578BDF..578C33`, row1/2는240). `Ship ArrivalTask` literal과 adapter57C040→57A690→local Actor 생성57ADAC→60FF0도 연결된다.

이는 **client의 local 배/부두 처리**다. server clock 동기화·game/real-time 변환·공식 운항/도착시각·자기 Player map 이동·표 소비는 닫히지 않았다. arrival task를 성공적인 하선 패킷 또는 플레이어 전환으로 확대하지 않는다. 상세·원문·제한은 [findings_client.md](../../local_server_rea_20261016/run397_boat_travel/findings_client.md):24–40과 `client_ship_methods.json`, `client_ship_arrival_callback.json`, `client_ship_arrival_invoke.json`에 있다.

## L1J 참고: 탑승·선내 대기·하선

| 접점 | 이 L1J 소스에서 확인한 것 | 클래식에 대한 경계 |
|---|---|---|
| 표 | 말하는 섬 NPC70011이40299(`$314`), 글루딘 NPC70022가40298(`$315`)를 판매. SQL 판매300/매입150 | 클래식 item/template·가격·상인 identity를 이 번호로 고정하지 않음 |
| 말하는 섬 탑승 | map0 `(32630/32631/32632,32983)` 다음 칸→40299 보유·시간 검사→map5 `(32733,32797)`, h4 | 클래식 보행 trigger·요청/거절 조건의 실제 관측 필요 |
| 본토 탑승 | map4 `(32540/32542/32543/32544,32728)`→40298 보유·시간 검사→map6 `(32735,32795)`, h4 | L1J map4는 본토 전체. 클래식 raw/resolved namespace를 별도 확인 |
| 표 사용/소비 | 입장 Dungeon.dg는 보유 검사만 하며 소비 없음. 도착 C_Ship에서 현재map5/6에 따라40299/40298 한 장 consume | 이 경로는 더블클릭 사용이 아님. 클래식 사용 가능 여부·소비 시점은 별도 입증 필요 |
| 대기 | 선내map5/6에 머무르며 C_Ship 요청을 받는 구조. C_Ship 본문에는 운항시간·도착시각 검사 없음 | 서버 타이머가 자동 도착시킨다는 증거로 읽지 않음 |
| 도착 | 현재map5→GetBack 목적map4, 기준 `(32565,32726)`; 현재map6→map0, 기준 `(32632,32973)`. 요청x/y는 GetBack 기준 X/Y 각각±20 검사를 통과한 실제 client 값 사용 | GetBack 기준점을 유일한 실제 도착칸으로 고정하지 않음 |
| 출발항으로 내리기 | map5 `(32733/32734,32796)`→map0 `(32631,32982)`; map6 `(32734/32735/32736,32794)`→map4 `(32544,32727)`. 같은 시간/표 보유 조건 적용 | 도착 처리와 다른 출발항 하선 경로. 언제든 내릴 수 있다고 단정하지 않음 |

정확한 원문은 [L1J 결과](../../local_server_rea_20261016/run397_boat_travel/l1j_findings.md):7–37이다. 입장 시간은 `gameSeconds%86400`: map5 방향 `[15+30k,25+30k)×360초(k=0..7)`, map6 방향 `[0,360초)` 및 `[30k,30k+10)×360초(k=1..7)`다. **첫 map6 구간 상한은 원문360초**이며3600으로 정규화하지 않았다. 현실 경과×6 및 연도 이동 설정이 있으므로 이 시간을 클래식 시간표로 옮기지 않는다. 도착 consumeItem의 반환 미검사도 원문 그대로 남겼다.

## 도착 후 클래식 맵 전환 계약

기존 run380에서 `4E95 → typed Map receiver5325C0 → Actor 정리63200 → raw f1/alias3DA970/resolved map 갱신 → changed-map 처리4F3650 → MapChanged`를 확인했다. **MapChanged의 ShipSubsystem callback57A020**은 기존 배 local Actor를61650으로 퇴역시키고, 자료+48과 새map이 맞으면60FF0으로 local Actor를 만들며 Actor+10=1로 표시한다. 이 local 배 생성은 자기 Player/모든 주변 서버 Actor 생성의 대체가 아니다([run380 flow_findings](../../local_server_rea_20261016/run380_map_transition_receive/flow_findings.md):14).

| 필드/프레임 | 확인된 소비 | 배 이동에서 남은 입력 |
|---|---|---|
| 4E95 f1 | required i32, raw Map+71C→alias→resolved Map+718 | 정상 탑승/도착의 실제 raw map. L1J5/6/4/0을 그대로 wire로 쓰지 않음 |
| f2 | required i32→CharacterData+568, 무분기32비트 저장 | 업무 의미·정상값 UNKNOWN. 배 flag/층/0상수로 확정하지 않음 |
| f3/f4 | required bool. f3 수중 후처리 활성, f4 환경 렌더 scalar 선택 | 실제 각 항구/선내의 값·presence 필요. false라도 required presence 필요 |
| f5..f10 | optional scalar/nested/사각형/환경 소비 일부만 확인 | 탑승·도착별 presence/값 미확정. 임의0·빈목록으로 확정하지 않음 |
| 4E38→자기4E96 | SelfInfo UID가 Actor UID와 맞아야 MyPlayer factory. fresh 자기 게시→Camera UID/mode 결속 | 전환마다4E38 재전송이 필수인지는 미확정 |
| 목적지 주변4E96 | 해당 full Actor를 새 게시 | 배 local Actor/camera 변화로 주변 서버 Actor를 대체하지 않음 |

다른 resolved map 전환의 **소비조건을 만족하는 실험 후보**는 `4E95(실제값) → [필요한4E38] → 자기4E96(목적grid) → 목적지 주변4E96`다. 공식 전체 순서·추가 effect/remove·타일 준비·후속 요청·입력 복원은 UNKNOWN이다. 4E95를 빼고4EE0 좌표 보정만 보내면 목적map/tile context가 갱신되는 근거가 없다. run389의4EE0→Transform/Camera 양성 연결은 **같은 map·기존 MyPlayer** 전제여서 map5→4 또는map6→0의 대체 근거가 아니다([MAP_TRANSITION_EVIDENCE](MAP_TRANSITION_EVIDENCE.md):183–232,256–273).

## 사용자 화면 실험안 — 이번에는 미실행

후속 실행이 허용된 한 단위에서 기존 관측 경로·owned non-input desktop/Job을 재사용한다. 정상 원본 조작은 사용자가 맡고 포커스/전역 입력을 자동 조작하지 않는다. 게임·포트는 시험 worker 한 명이 한 번에 하나만 소유한다.

1. **말하는 섬 정상 편도:** 정상 구매로 표를 확보하고 상인 대사→목록→표 이름/수량을 기록한다. 정상 탑승 시 부두의 직전칸·진입칸·거절/허용·시계와 **실제4EF8.f1**을 함께 남긴다. 표 더블클릭은 정상 UI에서 실제로 허용할 때만 관측하고 보행 탑승과 분리한다.
2. **선내→글루딘:** 선내 지형·자기1명·대기/배 출항·입력 상태를 보고 **4F0E 유무/실제f1·전후 통지**와 도착 직전부터 첫 정상 한 칸 걷기까지의 짧은 기존 기록을 확보한다. 실제 도착 요청·4E95 전 필드/순서·4E38/자기·주변4E96·effect/remove·표 수량 전후·raw/resolved map/current/Camera를 같은 실행에 묶는다. 화면만으로 f2나 표 소비 시점을 판정하지 않는다.
3. **역방향 1회:** 글루딘에서 정상 새 표 구매→선내→말하는 섬을 같은 방법으로 기록한다. 양방향 표/맵/시간/도착 좌표가 같은지 추측하지 않는다. 출발항으로 도로 내리는 행동은 필요할 때 별도 최소 관측으로 구분한다.
4. 관측된 한 편도의 **정확한 값·순서**를 얻은 뒤에만 로컬 시험 저장 사본에서 정상 로그인→선택→월드 진입→해당 편도1회를 비교한다. 도착 지형·단일자기·주변·다음 이동/선택과 실제 표 소비·저장/fresh를 구분해 판정한다. 송신 drain/receiver RET를 화면 완료로 쓰지 않고 가상 ACK/강제 준비/표UID 위조를 넣지 않는다.

기존 관측이 제공하지 않는 필드는 UNKNOWN으로 남긴다. 새 수집기·검증기·guard를 만들지 않는다. 이번 변경은 새run397 및 이 문서뿐이며 원본·다른run·제품서버·저장·큐·기존dirty를 보존했다. 게임/서버/포트/실패 재실행·git commit은 없다.

정적 확인: worker의 기존 reader 재사용 추출은 exit0, `client_selected.json`으로 선정 구간이 저장됐다. 메인은 생성 파일의4EF8 producer·4F0E 등록·Portal+70 생산·항구/선내map 비교·시간창 연산과 원자료124/125·ShipInfo1/2를 직접 재독하고 통합했다. 새 검사기나 런타임 시험을 추가하지 않았다. 재현 명령·도구 실패의 한계는 [client 결과](../../local_server_rea_20261016/run397_boat_travel/findings_client.md):63–73에 있다. **SOURCE_ONLY / 전체 배 왕복·화면·입력·저장 UNRUN**이다.
