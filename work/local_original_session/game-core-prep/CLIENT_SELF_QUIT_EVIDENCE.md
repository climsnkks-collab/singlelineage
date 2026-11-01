# 사용자 Quit 없이 발생한 4E3C 조사

2026-10-28. 정적 원문·정적 연결·과거 실행 관측·추정을 구별한다. 게임 실행·새 캡처·제품 코드·핀 DLL·사용자 저장·manual profile·ACTIVE_TASK 수정·commit은 이번 조사에 없다.

## Native 조사 결론

**확보한 코드에서 `4E3C`를 송신하는 분기는 Quit core `13C0D0`의 `13C21C → 13C228`이다. 이 분기는 현재 NetworkSubsystem의 `+388`이 0일 때만 실행된다.** 직접 caller는 `140A60`과 `ACBDA0` 두 개다. 전자는 disconnect popup 확인 callable, 후자는 QuitLayout의 `Root.Button_Quit` callable이다. 이는 호출 경로의 확인이며, 이번 사건에서 사용자가 종료 버튼을 눌렀다는 증거가 아니다. 사용자는 Quit를 누르지 않았다고 설명했다. 프로그램에 의한 callable 호출·의도하지 않은 UI dispatch·아직 해석하지 못한 간접 호출은 남아 있다.

**기존 “Alive timeout popup 확인이 최종 4E3C의 후보”는 조건을 보완해야 한다.** 확인한 popup 생산자 네 개는 모두 먼저 `NetworkSubsystem+388=1`을 쓴다. 같은 객체와 값이 유지되면 popup 확인→Quit core는 `4E3C` 송신을 건너뛰고 로컬 state6으로 간다. 그 사이 새 NetworkSubsystem/`+388` reset 등 별도 변화가 없다는 조건에서 이 timeout 경로는 사건의 `4E3C`를 설명하지 못한다. 서버가 `4F57`을 전송했다는 사실과 원본이 이를 소비했는지는 여전히 다른 근거다.

입력 AFK의 조건·마지막 입력시각 필드·600/720/750초 한계·그 한계에서 `4E3C`를 생산하는 연결은 **미확인**이다. 이를 “AFK 기능 없음”으로 바꾸지 않는다. 약760.49초는 과거 주프로세스 creation부터 강제정리 exit까지의 수명이며 Quit 발생까지의 무입력 시간이 아니다.

## 기준과 분석 경계

주소는 모두 고정 원본의 **RVA**, preferred VA는 `0x140000000 + RVA`다. CONTROL SHA256 `9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`, 분석 carrier SHA256 `c822838351d774a2022af434829a36dbd9bee030bf22182b834ca4e8659701a9`는 [기존 신원](../../local_server_rea_20261016/TARGET_IDENTITY.md)을 따른다. 원본은 LC 26.09.29.2001 기준이다. 파생 carrier는 `work/rea_lineage_resume_20261013/main-gameplay/audit/metadata-v2/DERIVED_RESTORED_ANALYSIS_ONLY.exe`이며 실행 제품이나 현재 loaded code와 동일하다고 주장하지 않는다.

REA skill37을 적용했다. REA6.4.0/Ghidra12.1.4가 위 carrier를 정확한 SHA로 open했다. 최초 `procedure_callers(0x14013C0D0)`는 **300초 tool-call timeout**으로 결과를 얻지 못했다. 새 Ghidra 분석·REA Evidence ID가 생겼다고 주장하지 않는다. `close_binary({})`를 완료하고 `binary_session({}).open=false`를 확인했다.

실제 추가 원문은 기존 `tools/local_movement_contract/source.py`의 pinned reader→복원 section record를 읽고 Capstone으로 확인했다. packed 디스크 원본의 stub만 분석한 것은 아니다. 다만 복원 정적 자료이며 원본 전체·현재 실행 메모리의 동등성은 범위 밖이다. `.pdata`는 hot/cold 조각을 따로 가리킬 수 있으므로 짧은 pdata 조각을 전체 함수로 해석하지 않았다. Input update는 `16A0F0..16A1AC` 연속 명령도 읽었다. 새 조사 보조와 raw 검색 결과는 임시 파일 `C:/Users/Chansol/AppData/Local/Temp/singlelineage-quit-native-20261028.py` 및 같은 이름 `.json`에 있다. 아래 필요한 원문은 문서에도 보존한다.

재사용 근거는 [idle-native-static.json](idle-native-static.json), [idle-native-followup.json](idle-native-followup.json), [run21 Alive](../../local_server_rea_20261016/run21_4e2a/findings.md), [run32 normal close](../../local_server_rea_20261016/run32_normal_close_confirmation/findings.md), [ATS 근거](ATS_COMPANION_EVIDENCE.md)다. 기존 문서의 popup 원인 후보는 위 `+388` 조건과 함께 읽는다.

## 생산 경로와 공통 consumer

| 경로 | 확인한 producer → consumer | 4E3C와의 관계 / 판정 |
|---|---|---|
| QuitLayout 승인 callable | `Root.Button_Quit`에 설치한 vptr`122F708`/invoke`ACBDA0`; `ACBE75 → 13C0D0` | `+388=0`이며 앞쪽 CharacterData predicate가false이면 `4E3C`. 호출자의 실제 입력/프로그램 기원은 정적 코드로 판별 못 함 |
| 일반 WM_CLOSE, Land | `EF5480 → B89EE0 → B3FA80 → 568D0(QuitLayout,command0)` → 위 버튼 callback | WM_CLOSE 자체가 즉시 `4E3C`를 보내는 경로가 아니다. 승인 callable의 실행이 필요함. 실제 입력 delivery는 UNKNOWN |
| disconnect popup 확인 callable | `13C450`이 vptr`1186A88`/invoke`140A60` 설치 → `140A9C → 13C0D0` | generic callable은 Quit core에 연결됨. 아래 네 native popup 생산자는 먼저 `+388=1`이므로 같은 상태에서는 송신하지 않음 |
| 서버 kick | `SC_KICK_NOTI/4E23` 수신→`274960`; `274A4C [+388]=1` → `274DDB → 13C450` | popup 승인 뒤 기본 경로는 로컬 state6. kick 자체가 `4E3C`를 보낸다고 표시하지 않음 |
| socket error | `285010`; `2853A0 [+388]=1` → `2853D8 → 13C450` | 같은 객체/값 유지 시 `4E3C` 없음 |
| 연결 대기 timeout | `285B00`; `285B87 [+388]=1` → `285FA0 → 13C450` | 같은 조건에서 `4E3C` 없음. 활성 Land의 입력 AFK 한계로 해석하지 않음 |
| 기대 응답 timeout | `32E76B..32E7C7`; `32E7BB [+388]=1` → `13C450(0x40)` | 같은 조건에서 `4E3C` 없음. popup 표시와 승인은 별개 |
| 서버 시간제한 / socket-disconnect 통지 | `SC_PLAY_TIME_LIMIT_NOTI/4E74`, `SC_DISCONNECT_SOCKET_NOTI/04B5` parser→event까지 확인 | event의 실제 subscriber/후속 종료 consumer 미확보. `13C0D0` 연결이나 자동 송신 여부 UNKNOWN |

공통 consumer의 결정적인 원문은 다음과 같다. `[rsi+388]`은 여기서 **NetworkSubsystem의 byte**다. 아래 Alive task의 GameStateSubsystem `+388` 포인터와 객체가 다르다.

```text
13C129 call 111EF0              ; CharacterDataSubsystem 상태 predicate
13C168 test sil,sil
13C16B je 13C18A
13C177 mov edx,82
13C17F call 3DEF0
13C185 jmp 13C3FA              ; 이 가지는 아래 송신에 도달하지 않음
13C1A3 call 3EC40              ; NetworkSubsystem strong pair
13C1B3 mov rsi,[rbp-49]
13C1B7 cmp byte ptr [rsi+388],0
13C1BE jne 13C244
13C21C mov edx,4E3C
13C221 lea r8,[rbp-69]         ; CS_QUIT_REQ
13C225 mov rcx,rsi
13C228 call 27D620
13C242 jmp 13C251
13C244 mov edx,6
13C249 mov rcx,r14              ; GameStateSubsystem
13C24C call 13B880             ; 로컬 상태 전환

32E79D mov rbx,[rbp+10]
32E7A1 xor edx,edx
32E7A3 mov rcx,[rbx+198]
32E7AA call 26DDF0
32E7AF lea rcx,[rbx+E0]
32E7B6 call 67DF0
32E7BB mov byte ptr [rbx+388],1
32E7C2 mov ecx,40
32E7C7 call 13C450
```

앞쪽 `111EF0`의 receiver는 getter`3EB60`이 얻은 **CharacterDataSubsystem**이다. 이 predicate는 GameState가Land(enum5)가 아니면false를 반환한다. Land에서는 현재 actor/관련 component를 조회하고, 특정 component 상태값8 또는 조회한 영역 flag의bit2 조건이면 CharacterData+8E0을0으로 하고+8D0 task를 정리한 뒤 현재+8E0을 반환한다(`111FC7..1120CB`). byte+8E0의 정확한 업무 명칭은 이번에 확정하지 않았다. true이면 Quit core는 메시지`0x82` 경로로 빠져 송신하지 않는다. 이를 modal 창 존재 검사로 단정하지 않는다.

복원 executable section에서 direct `E8`와 RIP-relative `LEA` 후보를 pdata 명령 경계로 검증한 결과 Quit core 직접 callsite는 위 두 개였다. 64bit 절대 주소 패턴 검색에서 `13C0D0`/`13C450` 자체의 pointer 출현은 없었고 callback pointer는 `1186A98→140A60`, `122F718→ACBDA0`였다. `u32 4E3C`의 pdata 내부 immediate 소비는 `13C21C` 송신 인수와 `26C1D6` 구성 table 행 두 곳이었다. 후자는 네트워크 구성 생산자이지 별도 확인된 Quit 송신이 아니다. 이는 해당 section/형식의 검색 결과이며 다른 모듈·계산된 opcode·tailcall·간접 호출 전체의 부재 증명은 아니다.

## 입력·주기·시간제한의 분리

| 항목 | 확인한 주소·값·reset/소비 | 해석과 미확인 |
|---|---|---|
| Alive 반복 | GameState Initialize `13AE62 [task+8]=42700000`(**float60.0**), `13AE71 [GameState+388]=task`; 월드 ready `13D28D → 1410B0`; callback`141300` | `141153`에서 task+8을 읽어 `B4E8C0`; `B4E978/B4E980`에서 LoopTask+B0/+B4에 같은 값 보존. 입력 AFK 비교가 아님 |
| Alive 응답 대기 | `27936C`가 pool`126ECD0`의 **float20.0** → 등록 row+18 → 송신 뒤 OneTimeTask+B0. `B4E270` update가 delta 차감 | 받은 `4F57` opcode가 `27A41E/27A427 → 32D970 → 32DAC0/32DAC3 → B453F0` task 정리. 임의 서버 패킷/선제 응답의 AFK reset 근거는 없음 |
| scheduler 단위 | 위60.0/20.0은 전달된 float delta를 차감하는 scheduler 단위 | wall-clock producer→ScheduleSubsystem 전체 연결은 이번에 닫지 않음. 따라서 새 확정값을 “60초/20초”로 올리지 않음 |
| GameState Update | vptr`1182E30` slot+28=`6CFE0` 본문 `ret 0` | 이 slot에 600/720/750 timeout은 없음. 다른 delegate/task 전체가 없다는 뜻은 아님 |
| Input update | vptr`1182D40` slot+28=`16A0F0`; `16A130` listener+158 검사, +15C delta 차감, 음수가 되면 callable invoke+10, +160을 +15C에 reload | per-listener 반복 countdown. 키 해제 `16AD1E`는+15C에 **float0.5**를 쓰고 `16AD28`에서+158을0으로 만듦. AFK logout counter로 확정할 근거 없음 |
| 키보드 | Bootstrap`169A2E/169A50`가 `16A730`/`16ABA0`를 바인딩; keydown`16AAE3/16AAE7`은 keycode를+208에, keyup`16AD4A`는0을 저장; listener vslot+8/+10 dispatch | `+208`은 이 경로에서 keycode이며 마지막 입력 timestamp로 해석하지 않음. 확인한 직접 경로에 Quit core 호출 없음. listener 간접 소비 전체는 미해석 |
| 마우스 | Bootstrap`169B78..169C10`가 `16B440/16B580/16B650/16B7A0` 바인딩; listener vslot+38/+48/+40/+50 dispatch | 확인한 직접 경로에서 마지막 입력시각 저장→장시간 비교→Quit 연결 미확인. 간접 listener 전체를 다 따라간 결과는 아님 |
| NP timer | StartVerifySessionTimer`252960`: **float3000.0**, callback`269C80`; StartValidationExpirationTimer`252C50`: **float300.0**, callback`269AE0` | 앞 callback은 NP 간접 경계, 뒤는 메시지`2F87` 표시. 이 값의 wall-clock 단위 및 사건의 `4E3C` 연결 미확인 |
| network ResettableTimer | `27FC40/27FD29`, pool`126EDA8` **float300.0**. LoginEnter`1547A0`, CharacterSelectEnter`149AC0`, selfDie`994F0/9976F`에서 시작. 만료 callback`285B00`은 C→S`4E32` 송신·정리·`+388=1` 후 팝업 | 로그인/선택/죽음 메뉴 조건의 타이머다. 일반 Land 입력 AFK로 확정하지 않음. wall-clock 단위는 미확인 |
| ATS | 종료요청`42AAF0 → CS_FINISH_ATS_REQ/4F38(f1=4)`; 강제 ATS 종료`SC_FORCE_FINISH_ATS_NOTI/4F3A → 42F530/42FCE9`가 ATS 상태false | 게임 Quit`4E3C`와 별개. 남은 ATS 시간은`42D450/42D310/42A9EA..42AA58`의 clock ns÷1e9 경로. ATS 만료→게임 Quit 연결 미확인 |
| 피로도 | RTTI`174D680`의 `LIN::FatigueInfo` 존재 | 타입 존재만으로 강제logout 정책·수치·caller를 만들 수 없음. 실제 consumer→Quit 연결 미확인 |
| 비활성/최소화 | 문자열`123B220/123B240`의 foreground/background event가 `B997CE/B99860`에서 소비됨 | 이벤트 존재와 자동 종료는 별개. 비활성/최소화 상태·경과시간·Quit 사이 연결 미확인 |

### 600·720·750 비교

u32 초/밀리초 후보와 float32/64 literal을 복원 section에서 찾고 executable section의 pdata 명령에서 실제 immediate 소비를 확인했다. raw 숫자가 객체 offset·스택 크기·할당 크기·schema·문자 bytes일 수 있어 숫자 출현을 timer로 채택하지 않았다.

| 후보 | 실제 소비와 결론 |
|---|---|
| 600초 후보 | float600.0 pool`126EDC8`의 직접 RIP 소비 `3FC18C`, `D94151`. 전자는 두 float를 UI 크기 인수로 만들어`D92560`, 후자는2축 값에 곱해 scroll 좌표+4F58/+4F5C를 갱신함. 이 소비는 경과시간 한계 비교가 아님. u32 immediate600도 pointer/스택/크기/필드 대입이며 이 검색에서 logout threshold 비교를 확인하지 못함 |
| 720초 후보 | float720.0 raw 패턴은`117446E/1833A1F`였으나 직접 RIP 소비를 확인하지 못함. u32 immediate720의 확인된 소비에는 스택/할당/구조 크기 등이 있음. 경과시간→Quit 연결 없음 |
| 750초 후보 | 유효 u32 immediate`B6EAE3: mov dword[rbp+68],2EE`는 `B6DEAD..B6DEF9`의 source-location/log 레코드→`578E0`에 소비된다. 같은 필드에 인접 로그 source line721도 들어간다. timer가 아니다. float750.0 raw 패턴의 직접 RIP 소비 미확인 |
| 600000/720000/750000ms 후보 | raw u32는 앞 두 값이 각각`18183D0/18199CC`, 마지막은 출현0. 이 검색에서 executable의 유효 즉시값 소비·RIP timer 비교를 확인하지 못함. table-index 방식이나 실행 중 계산된 값의 부재 증명은 아님 |

## 원인 판단과 수정 후보의 경계

현 정적 자료에서 최종 `4E3C`를 가장 직접 설명하는 가지는 `ACBDA0 → 13C0D0`의 **NetworkSubsystem+388=0 송신 가지**다. 이 설명력은 producer/consumer 수준이며, 사건에서 `ACBDA0`가 실제 호출됐다는 관측은 없다. 사용자의 종료 클릭이 없었다는 설명과 양립하는 실제 trigger는 계속 UNKNOWN이다. timeout popup은 `+388`이 유지되는 한 같은 패킷의 원인으로 채택할 수 없다.

서버는 기대 `4F57/body0B`를 같은 연결에서 응답하는 기존 계약을 유지할 근거가 있다. 선제 heartbeat·임의 packet flood·ATS 응답을 추가해 입력 AFK를 reset한다는 근거는 없다. 서버 시간제한 통지의 consumer가 미확인인 상태에서 새로운 서버 정책을 추측해 넣지 않는다.

현재 사건을 해결한다고 확정할 DLL patch는 없다. 정적으로 식별한 조정 지점과 적용 범위는 다음과 같다. 이번에는 어느 것도 적용하지 않았다.

| 목적 | 서버 대응 또는 DLL 후킹 후보 | 적용 한계 |
|---|---|---|
| Alive 응답 만료 방지 | 같은 연결의 `4E2A`마다 `4F57/body0B` 응답. 대기값 연장이 필요하다면 `27936C..279380 → 32D2E0`의 **4E2A 등록행**에 전달하는20.0 인자가 지점 | 이미12회 응답했다. 연장해도 이번 `4E3C` 원인을 해결한다는 근거 없음. 공유 pool`126ECD0` 전체 변경은 이 행만 바꾸는 것과 다름 |
| 로그인/선택/죽음 메뉴 대기 연장 | `27FD29`의 ResettableTimer 생성 인자300.0 및 기존 task reset`27FAF0` | 해당 상태의 대기값 조정 후보다. Land AFK 해제나 사건 원인 수정으로 표시할 수 없음 |
| 서버 Kick 방지 | `4E23`을 보내는 서버 정책 자체를 점검 | f2를0/누락으로 바꿔도 강제 정리를 취소하지 않음. 해당 사건 ring에는 이 패킷 없음 |
| 원치 않은 Quit callback 구별 | `ACBE75 → 13C0D0`와 `140A9C → 13C0D0`, 공통 분기`13C1B7`가 서로 구별되는 지점 | 호출 기원을 먼저 알아야 선택적으로 차단할 수 있음. 공통 Quit 함수/송신을 무조건 생략하면 정상 종료 계약까지 바뀜 |
| ATS/피로도/키보드 AFK 제한 해제 | 이번 자료로 확정할 조정 지점 없음 | ATS 잔여시간 통지와 게임 Quit 연결을 임의로 만들지 않음. 키 입력 자동 발생을 해결책으로 채택할 근거도 없음 |

원본으로 추가 확인할 최소 정보는 **Quit 당시 `ACBDA0`/`140A60` 진입 기원, `13C1B7`의 실제 NetworkSubsystem+388 값과 현재 QuitLayout/팝업 상태**다. 기존 기록으로 이 경계를 복원할 수 없으므로 실제 trigger는 미확인으로 남긴다. 이는 이후 관측 위치 설명이며 이번 조사에서 게임 실행·hook 설치·새 collector를 수행한 결과가 아니다.

## 서버 통지와 연결 타이머의 상세 조건

`SC_KICK_NOTI/4E23`은 등록`29492D..294934`의 callable vptr`11AB458` → invoke`307E60` → parser`31EE90` → `307F01` event`17FB5C0` 발행 → `278FC0`에서 등록한 callback`274960`으로 연결된다. 생성 parser`753A10`/schema`15FCD78`의 **f1은 required signed int32, f2는 optional signed int32**다. handler는 f2가 존재하고 양수이면 팝업 표시문구 번호로 사용하고, 아니면 기본`0x40`을 쓴다(`274A6D..274A8B`). 연결 정리와 `+388=1`은 이 값에 관계없이 수행된다. f1/f2의 공식 업무 의미 전체는 미확인이다.

`OnSocketError` callable은 TD`16E7C60`/vptr`1199610` → `285010`이다. `285333`에서 기존 Network+388을 읽고0일 때만1로 바꿔 팝업을 연다. `StartConnectionTimeoutTask` callable은 TD`16E7A20`/vptr`11995A0` → `285B00`이다. `285B46`에서 C→S`4E32`를 송신하고 정리한 뒤 `285B87`에서+388을1로 만든다. 이 둘을 별도 S→C 강제 logout 패킷으로 해석하지 않는다.

연결 타이머 `27FC40`은 Network+378에 활성 task가 있으면 `27FECD → 27FAF0`으로 reset하고, 없으면 `27FD29`에서 float300.0으로 만든다. 생성자`B4EC9A/B4ECA2`는 기간+B0/잔여+B4를 설정하고, Update`B4ED6C`는 delta를 빼며 `B4EE79..B4EE9D`에서 잔여<=0이면 callback을 호출한다. reset은 Scheduler의 현재 handle을 찾아 ResettableTimer로 cast한 다음 `27FBBB`의+B0를 `27FBC3`의+B4로 복구한다.

확인한 Start 직접 callsite는 세 곳이다. `149EA6`은 CharacterSelectState Enter(`149AC0`), `154842`는 LoginState Enter(`1547A0`), `9976F`는 내장 literal`117E7F8="lineage::ActorSubsystem::Die"`가 있는`994F0`의 죽음 처리다. 마지막은`995DC`의 두 식별값 비교가 같고`42AA90` predicate가 false일 때 UI`568D0` 이후 타이머를 시작한다. true이면`9965B → 13BB80` restart 쪽이다. 이 식별값과 predicate의 의미를 추가 확정하지 않는다. CharacterSelect Exit`149FCD`와 Login Exit`154B0D`는 취소`27FEF0`을 호출한다. 직접 reset callers에는 CharacterCreateLayout lambda`931A10/931C90/931EE0/9320A0/932220`, CharacterSelectLayout InitWidgets lambda`938F90/9398F0`, CharacterSelectPopup lambda`93C5D0` 등이 있다. 일반 Land 키보드/마우스 또는 모든 서버 패킷이 이 값을 reset한다고 단정하지 않는다.

시간제한 통지 두 종류는 다음 범위까지 확인했다.

| 통지 | 파서·event 생산 | 실제 종료 소비의 확인 범위 |
|---|---|---|
| `4E74 / SC_PLAY_TIME_LIMIT_NOTI` | 등록`294EF1..294F0D` → callable`11A8CF8`/invoke`304370` → parser`31CEB0` → `304411/304418` event`17FD480` 발행. schema`15F40F8` f1/f2 signed int32 | event 본체와 내부0xC0 범위의 직접 RIP 참조는 초기화`9970`, 발행`304370`, 정리`1095D80`뿐. 실제 subscriber 미확보 |
| `04B5 / SC_DISCONNECT_SOCKET_NOTI` | 등록`293A8D..293AAD` → callable`11AC358`/invoke`3113E0` → parser`323EA0` → `311481/311488` event`17F67C0` 발행. schema`15F6E38` f1 bool | 같은 범위의 직접 RIP 참조는 초기화`7E40`, 발행`3113E0`, 정리`1093030`뿐. 실제 subscriber 미확보 |

검색은 고정 reader의 LEA 참조와 첫 code section의 REX+LEA/MOV RIP 상대 참조, 복원 section의 절대 VA qword 참조를 포함했다. 두 event의 절대 pointer 출현은0이었다. 정리 함수의 event 내부+98/+88/+8 해제는 게임 연결 해제 callback의 증거가 아니다. 계산된 alias·동적 포인터·간접 등록·다른 모듈 subscriber는 UNKNOWN이다. 별도`4F52 / SC_ENTRANCE_KICK_NOTI`의 CharacterSelectState 계열 소비도 일반 Land Kick과 합치지 않았다.

## 사건·브리지 통합

### 사건 원문의 관측 범위

[status.json](../runs/manual-test-knight-20261027-234727-3cf8c2b9/status.json)과 [result.json](../runs/manual-test-knight-20261027-234727-3cf8c2b9/result.json)은 `sibling-manual-play-spawn`/`control_mode=manual`이다. `user_shutdown_requested=false`, `UI_close_requested=false`, `normal_exit_verified=false`, `game_logout_protocol=UNVERIFIED`, 결과는 **BROKER_FAILURE / FORCED_CLEANUP**이다. 사용자 설명은 **마우스 클릭만 했고 키보드·종료 입력은 없었다**이며 그대로 전제한다.

broker ring은65개/event65/dropped0이다. index38..61은`4E2A RX → 4F57 TX`12쌍, index62는`4E3C RX`10B, index63은`4EEF TX`8B, index64는stopped다. Quit request verified/response drained/queue empty는true다. 마지막12Alive 구간에 별도 서버 Kick/시간제한/ATS 강제종료 통지는 없다. 이는 서버 전송·수신 순서의 관측이며 client parser 소비·버튼 실행·정상 종료 관측은 아니다. **마지막 수신/RST 시각은 ring에 없으므로 두 사건 간격도 UNKNOWN**이다.

primary PID16524/birth`134375860604907717`의 creation은 KST2026-10-27 23:47:40.4907717, 강제정리 exit는2026-10-28 00:00:20.9855863, native lifetime은**760.494815초**다. product lifetime760.641초와도 구별한다. bootstrap child PID86344는1.090687초 수명의 별도 과정이다. **760.49초는 AFK 시작→Quit 간격이 아니며 750초 타이머의 일치 증거가 아니다.**

새로 재사용한 과거 [close-caller-1.json](../../local_native_login_key_invoke_boundary/runs/ls-702b397a674e46f5a4b8d2f6/close-caller-1.json)은 같은 PID/birth/candidate SHA와 selected socket 일치를 가진다. 생산자 FILETIME`134375868208743608`=KST00:00:20.8743608, primary 강제정리 exit보다**0.1112255초 전**의 original Close 진입이다. 게임 stack return RVAs는`[CF4AF,B5CF4E,B4FB47,FA09C4]`다.

생산자`native-verified-socket-duplicate/abi_bridge_v2.cpp:379..433`은 CaptureStackBackTrace의 게임-image 내 return 주소를 RVA로 기록하고 GetSystemTimeAsFileTime을 저장한다. OwnLoginCloseBridge는 **원본 Close가 호출했을 때** 기록한 뒤 원함수에 전달한다. 따라서 파일 수정시각 추정이 아닌 close **진입** 관측이다. 원함수 반환·close 성공·최초 Quit trigger의 증거는 아니다. 정적으로`CF4AC`는 registry subsystem의 vcall+20, 복귀가CF4AF이고, 상위`B5CF4B` vcall+58/`B4FB42 call B5CCE0`와 연결된다. cleanup 순회에 양립하는 스택이며 Quit 생산자 stack이 아니다. `close-caller-0`은23:47:59.9138788의 bootstrap close이고 이 사건과 합치지 않는다.

### own-login-bridge와 런처

[launcher.py](../../../tools/local_original_session/launcher.py)의 제품 정의90..97/130..132행은 사건 제품이`sibling-verified-socket-duplicate`를 상속함을 보여 준다. 해당 DLL 핀은 **`1d1f60a03144f0214bee56c4a875d4444d51811649135a1eaab82ec2e2899f75`**다. `work/local_original_session/manual-play/start-manual-play.ps1:33`도 같은 핀이며117행은 해당 제품을 실행한다. 현재 baseline DLL/설치 slot은 이 SHA이고86,016B다. baseline [source-report.json](../native-verified-socket-duplicate/source-report.json)의 ABI·binding·def·candidate header·build·diagnostic·probe7파일 SHA도 현재 파일과 일치했다. **해당 과거 run의 loaded-DLL byte manifest·shared include 전체의 당시 동일성까지 확보한 것은 아니다.**

| 조사 대상 | Quit를 일으킬 수 있는 조건 / 결과 |
|---|---|
| 사건 baseline `native-verified-socket-duplicate` | 재귀 project include14파일+guard_template.asm에서 Quit/13C0D0/4E3C/WM_CLOSE/ExitProcess/TerminateProcess/DestroyWindow/PostMessage/PostQuitMessage/CreateThread/Sleep/SetTimer/WaitFor 검색0건. Connect/Init의 timeout 인자는 원함수 전달값. 직접 자동 Quit 경로 미발견 |
| baseline의 `auto_ok.hpp` | 등록 메시지에 따라 Login/Slot/SelectOK/Create를 once 호출하는 로그인 보조. 자동 종료 스레드/장시간 종료 타이머가 아님 |
| `tools/local_original_session/native/command_bridge.hpp:166` | **별도 internal-command DLL**에서 command3이면 `quit_detail::Execute()`. request파일·owner·sequence·UI thread·posted메시지가 필요함. `quit_command.hpp:93`는 scene에 따라944B80/ACBDA0/ACB2A0 호출. 자체 시간 조건 없음 |
| 별도 `implementation-1/manual-source-quit-codegate-bounds/source_quit.hpp` | `LC-Owned-Manual-SourceQuit-v1` 메시지와`source-quit-request.json`으로 FirstLandQuit/Quit6Approval 각once. 이 계보 DLL`d5865458…`는 사건 baseline과 다름 |
| `work/local_original_session/`의 Quit 헤더52파일/내용15종 | timer/thread/WM_CLOSE/ExitProcess/TerminateProcess 자동 패턴 미발견. 일부 WaitForSingleObject(duplicate,0)는 worker 생존 진단 |
| 런처 `request_close():1253` | owned visible HWND에 WM_CLOSE. 명시 close.request/사용자 interrupt/test-duration/관측조건 등 종료 사유에서 사용. 기본 제품 lifetime 제한은 없음. grace10초는 종료 후 정리 상한이며760초 실행 제한이 아님 |
| 이번 `BROKER_FAILURE` | 런처4925..4973의 WM_CLOSE 요청 사유 목록에 없음. 결과에도UI_close_requested=false, SourceQuit/명령 종료 결과 없음. `command.result.json`은AddInventory 결과뿐 |

`status.memory_write_or_game_control=false`는 [observe.py](../../../tools/local_original_session/observe.py)의 read-only snapshot 생성부682..688/767행에서 **상수로 붙이는 observer 필드**다. 런처·DLL 전체의 모든 제어 능력을 부정하는 필드는 아니다. baseline에서 Quit 경로가 없다는 판단은 위 소스/제품 계보 조사를 근거로 한다.

### 유력한 설명과 남은 원인

1. **생산 경로 수준에서 가장 유력:** 연결이 살아 있고 Network+388=0인 상태의 `ACBDA0 → 13C0D0 → 4E3C`. 정상 UI callable이 뜻하지 않게 dispatch됐거나 프로그램이 이를 호출했는지는 현재 기록으로 구별할 수 없다. 사용자가 종료를 눌렀다고 결론내리지 않는다.
2. **설명력이 낮아진 기존 후보:** Alive timeout/Kick/socket error/연결 대기 만료의 팝업 확인. 모두388=1을 세우므로 별도 reset/객체 교체가 없는 같은 상태에서는 관측한4E3C가 나오지 않는다. 실제 reset/교체를 관측한 기록도 없다.
3. **사건 계보에서 근거 없음:** baseline bridge 자동 Quit,760초 런처 제한, 마지막12Alive 구간의 서버 강제종료 패킷. 키보드만 세는 AFK 타이머와 ATS/피로도→Quit도 연결 미확인이다.

최초 trigger와 전체 간접 호출·다른 모듈 경로는 **UNKNOWN**이다. 조사 완료를 원인 재현·수정 완료나 전체 호출 경로의 완전성 증명으로 표시하지 않는다.

## 변경·출처·검증

- 변경 파일은 이 문서 하나다. 저장소 코드·원본·DLL·실행 로그·프로필·ACTIVE_TASK·핀·git commit 변경0, 게임/포트/캡처 실행0이다. 분석 보조는 위 임시 경로에만 두었다.
- 근거 출처는 원본 복원 정적 자료·기존 실행 기록·우리 브리지/런처 소스다. 외부 공식 웹/L1J 정책 인용0. 원본 경로·상수 주장은100% 원본 정적 근거, 브리지/런처 제어 설명은100% 로컬 소스/기존 로그에 귀속한다. 실제 원인 추정은 별도 표기했으며 새 원본 동작을 창작하지 않았다.
- 검증 명령: `python -X utf8 -B -`의 메모리 내 판독으로 고정 reader의 함수 시작부터 디코드한`13C1B3..13C24C`/`32E79D..32E7C7`와600/750 실제 소비를 독립 대조했다. branch/송신/+388 store 원문 일치. 같은 방식으로 result ring65개/Alive12쌍/Quit1개/원 FILETIME을 직접 확인했다.
- 문서 UTF-8 읽기·로컬 링크12개 존재·미완 placeholder 제거를 검사했다. 최초 문서 검사에서는 정규식 오류로 중단됐고 검사식을 고쳐 같은 문서를 재검증했다. 문서 작업이므로 제품 시험은 추가하지 않았다. REA caller 조회의300초 timeout과 session close는 위 도구 결과 그대로 남겼다.
