# 무입력 종료 — 원본 정적 조사

2026-10-28. **원본의 입력 AFK 타이머는 이번 범위에서 확인하지 못했다. 확인한 타이머는 ALIVE 요청의 응답 대기이며 초기값은 float32 `20.0`이다. 현재 서버의 `4E2A → 4F57/body0B` 계약은 맞다. 임의 24시간 hook·DLL 후보는 만들지 않았다.**

## 확인한 원문

기준은 기존 `work/local_server_rea_20261016/run21_4e2a/findings.md`와 그 source evidence, run3 Quit 자료 및 고정 reader `tools/local_movement_contract/source.py`다. CONTROL SHA256 `9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`, 분석용 carrier SHA256 `c822838351d774a2022af434829a36dbd9bee030bf22182b834ca4e8659701a9`. 새 결과는 REA Evidence ID가 있는 provider 출력이 아니라 이 reader로 읽은 정적 명령·RTTI·상수다. 실제 실행본의 loaded code 일치나 실행을 관측한 자료가 아니다.

| 질문 | 확인한 근거와 결론 |
|---|---|
| keepalive 응답 계약 | run21: `LIN::CS_ALIVE_NOTI/4E2A` optional int64/int32/bytes. `LIN::SC_ALIVE_NOTI/4F57`는 body0B 유효. 같은 연결에서 응답하는 현재 최소 로컬 정책과 맞는다. |
| 응답 대기값 | `27936C`가 `[RIP+FF5954]`=`126ECD0`의 float32 `20.0`을 xmm3에 싣고 `32D2E0`에 넘긴다. `32D359 → 32D803/32D809`가 등록 row+18에 보존한다. `27D8AE → B4E140`이 같은 값을 OneTimeTask+B0에 넣는다(`B4E1CF`). |
| 만료 조건 | OneTimeTask vtable `1237AD0`, Update=`B4E270`. 이미 완료가 아니면 +B0에서 전달된 delta를 빼며 `<=0`일 때 보관 callback+80의 invoke+10을 부른다(`B4E28D..B4E2BA`). 입력 유무를 검사하는 분기는 이 직접 경로에 없다. |
| 단위 | 정확히 확인한 것은 **20.0 scheduler delta 단위**다. `ScheduleSubsystem` getter931F0/TD166B400과 update vslot+28=`B459C0`가 float delta를 받는 것까지 확인했다. wall-clock 초 단위 producer의 전체 연결은 이번 범위에서 닫지 않았으므로 문서의 확정값을 “20초”로 올리지 않는다. |
| 응답 소비 | 실제 네트워크 수신 opcode로 `27A41E/27A427 → 32D970`를 호출한다(run21). 4F57 lookup이 원 4E2A에 매핑된 task handle을 찾아 `32DAC0/32DAC3 → B453F0`로 정리한다. `27D672`에서 NetworkSubsystem+1C8이 PacketTimeoutChecker 포인터인 것도 확인했다. |
| 서버 패킷의 reset | 위 task 정리는 **기대 opcode4F57**에 결속된다. 임의 서버 패킷 전체가 이 ALIVE 대기를 reset한다는 근거는 없다. 다음 기대 task를 만들 때도 `27D770..27D77E`가 기대 reply opcode로 기존 task를 정리한다. 이것을 입력 AFK 타이머 reset으로 해석할 수 없다. |
| 만료 이후 | run21 `32E76B..32E7C7`: NetworkSubsystem 연결 정리·byte388 설정 후 `13C450(0x40)` 호출. `13C450`은 GameStateSubsystem의 `OpenDisconnectPopup` 경로다. |
| Quit과의 연결 | 원본 Quit core `13C0D0` 직접 callsite 한정 검색은 UI callback `ACBDA0`와 helper `140A60`을 찾았다. `140A60`은 vtable1186A88+10에 있는 **OpenDisconnectPopup lambda1**이다(TD16D84D0 RTTI). `13CBA4`에서 이 callable을 설치한다. 팝업 확인 callback이 `140A9C → 13C0D0`으로 이어진다. **만료가 곧 무조건 Quit 요청을 보낸다는 증거는 아니다.** |

서로 별개의 NP 타이머도 원문에 존재한다. StartVerifySessionTimer=`252960`은 float3000.0을 LoopTask에 넣고, StartValidationExpirationTimer=`252C50`은 float300.0을 OneTimeTask에 넣는다. 전자의 callback269C80은 NP 경계의 간접 호출, 후자의269AE0은 메시지2F87 표시 경로다. 이 두 값을 입력 AFK·최근 종료 원인으로 채택하거나 그 단위를 임의 확정하지 않았다.

## 최근 실행과 구별

`runs/manual-test-knight-20261027-234727-3cf8c2b9/result.json`에는 4E2A RX→4F57 TX 12쌍 뒤 4E3C RX→4EEF TX가 있다. 이는 서버의 응답 전송 근거이며 **native parser 소비·task 제거·만료 popup 부재의 증거가 아니다.** 원인 관측이 없으므로 760초 실행 길이를 AFK 제한시간으로 삼지 않는다. 최종 Quit 요청이 timeout popup·사용자 버튼·기존 실행기 경로 중 어디에서 왔는지는 UNKNOWN이다.

고정 원문에서 AFK/Inactivity/IdleTimer/AutoQuit/AutoLogout 관련 문자·RTTI 후보와 위 Quit 직접 callsite를 조사했다. 입력 AFK timer 값·현재 마지막 입력시각·입력 timer writer/resetter는 확보하지 못했다. 이는 전체 클라이언트에 AFK 기능이 없다는 증거가 아니다. 간접 호출·다른 모듈·난독화된 이름은 이 검색의 한계다. InputSubsystem 초기화/등록·한정 update 원문에도 이번 종료를 닫는 연결은 확보하지 못했다.

## 현재 결정과 남은 최소 관측

- protocol 응답 변경·서버 주기 임의변경·AFK guard 삭제·DLL 후보 제작의 근거가 없다.
- 시험 담당에게 기존 read만으로 GameState current/pending와 최종 scene/종료시각을 보존하도록 전달했다. 기존 network/task observer가 없다면 소비는 UNKNOWN으로 남긴다. 새 reader나 별도 실행은 요청하지 않았다.
- 원본 900초 1회 시험에서 조기 종료가 재현되면, 기존 수신·전송 monotonic 시각과 마지막 scene/종료 직전 경계를 대조한다. 4F57 TX 후에도 disconnect popup이 실제 열렸다는 관측이 있어야 native 소비/대기 task 경로 수정 판단을 좁힐 수 있다.

산출물: `idle_native_static.py` / `idle-native-static.json`, `idle_native_followup.py` / `idle-native-followup.json`. 원본·핀 DLL·제품·서버·ACTIVE_TASK·manual 프로필·저장·로그 변경0, 게임/포트/현재 메모리 실행0, commit0. REA CLI6.4.0은 있었으나 활성 MCP에는 REA 도구가 없고 CLI 진단상 Ghidra provider 환경 미설정이었다. 설정을 고치거나 엔진을 설치하지 않고 기존 고정 자료를 재사용했다.
