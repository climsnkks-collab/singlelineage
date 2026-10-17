# 원본 기반 CP69 지속 세션

현재 설치된 별도 진단 profile은 `sibling-internal-lifecycle-integrity-spawn` / dg49 `03f77493…65647a`다. actual33의 ready에서 commit 직후 기준과 비교한 guard17 중12·lifecycle8 전부의 16B 차이가 관측돼 현재 native 실행은 중지했다. 완전한 unhook·변경 주체는 미확인이다. 이 profile은 동일 primary 신원의 고정 ready/선택 late health를 읽고, 파일 부재·쓰기 중에는 명령 없이 WAIT, 확정 형식·신원·signature count 실패에는 `NATIVE_GUARD_INTEGRITY_FAILURE`로 추가 명령·Quit 없이 기존 owned cleanup을 실행한다. 명령 게시 직전에도 다시 확인한다. 표적7 PASS/main1회 및 closed actual33 기록 재생에서 count 거절을 확인했다. 이 두 시점의 검사는 수명 전체 보호 보장이 아니다. 아래 실행 예시는 해당 초기화 경계가 해결된 뒤에 사용하며, 과거7cd DLL과 성공 근거는 보존한다.

최근 실제 이동·저장·복원을 확인한 내부 profile은 `sibling-internal-quit-source-retry-spawn`이며 같은 자원 폴더의 `LC.guard.exe`(8b9e2628…)와 dg49 bridge `7cd55da1…bd8485`를 사용한다. `internal-bridge-20`에서 내부 Login→Select→Land→원래 Quit→설정 저장/4E3C/4EEF082D→Quit6/후기 승인→primary exit0·무강제 Job 정리를 실제 확인했다. 이후23은 같은 종료 흐름에서 새 분류기의 `normal_exit_verified=true`도 확인했다. 29에서 원래 MoveGoal→CS4E2B1회→once commit→client current/predicted32572,32950→정상 종료를,30에서 새 기동의 같은 위치 복원·정상 종료를 실제 확인했다. 새 프로파일은 CP74의 명시 로컬 spawn32571,32950을 재사용하고 기존 저장 위치가 있으면 우선한다. 공식 spawn이나 전체 Navigation 동등성을 주장하지 않는다. Quit 없이 약30초 뒤 exit1과 같은 exe Job member가 생기는 별도 현상도 미해결이며 짧은 정상 종료 성공으로 해결했다고 보지 않는다.

4ED6는 계정에 묶인 opaque binary 요청을 선택한 store 옆 `account-settings.bin`에 원자 저장한다. 캐릭터/좌표 저장 형식을 바꾸지 않으며 임의 ACK·설정 echo를 보내지 않는다. 처음 종료 응답이 drain된 뒤 같은 selected writer의 같은 빈 Quit가 다시 오면 현재 권한·UID·저장 상태를 재검사하고 추가 ACK/저장 없이 처리하는 로컬 정책을 쓴다. 공식 서버의 중복 처리 규칙을 복원했다는 뜻은 아니다.

현재 기본 제어는 `--control-mode internal`이다. 이 모드는 OwnedMouse/InputRequests를 생성하거나 polling하지 않고 cursor·focus API를 사용하지 않는다. 명시 명령은 run directory의 `command.request.json`에 `{"schema":"local-original-command-request-v1","sequence":1,"command":"LoginOK","uid":0,"x":0,"y":0}` 형식으로 쓴다. command는 LoginOK/Select/Quit/MoveGoal이며 앞의 세 명령은 uid/x/y 모두 0, MoveGoal은 같은 실행에서 관측한 선택 UID와 grid goal을 명시한다. native가 현재 UID·장면·객체·원래 호출 경계를 다시 확인하며, 미확인 계약은 UNSUPPORTED/REFUSED로 남긴다. 순번은 1..2147483647에서 엄격 증가하고 durable claim 뒤 한 번만 전송하며 pending 중에는 덮어쓰지 않는다. `command.result.json`의 RETURNED는 native UI thread에서 조건을 검사한 원래 callback의 복귀만 뜻하고 화면·월드·이동·로그아웃 완료는 UNKNOWN이다.

내부 모드는 새 비입력 desktop을 전용 helper thread에서 생성하고 그 thread의 원래 desktop 복원을 검사한다. retained HDESK를 STARTUPINFO.lpDesktop에 지정하고 첫 표시를 SW_HIDE로 설정하며 사용자 desktop을 전환하지 않는다. suspended primary의 User32 초기화 전 desktop 조회 실패는 UNKNOWN으로 기록하고 알려진 이름 불일치는 거절한다. 정확한 lpDesktop·fresh HDESK·pre-entry 보호를 기동 경계로 사용하고 native 첫 창 생성 wrapper가 loader 밖에서 실제 desktop을 엄격히 검사한다. HWND 조회는 HDESK의 EnumDesktopWindows로 한정하며 명령 PostMessage는 같은 private desktop에 조인한 전용 helper thread에서 현재 owner/HWND/UI thread를 재확인한 뒤 한 번만 보낸다. helper의 원래 thread desktop을 복원·join할 때까지 HDESK를 유지하고 기존 retained process/Job 정리 뒤 handle을 닫는다. private desktop만으로 전역 display-mode 변경까지 막았다고 간주하지 않으며, source가 검증된 background display/cursor/focus guard와 그 고정 DLL profile이 준비되기 전에는 `INTERNAL_DISPLAY_GUARD_UNVERIFIED`로 native 생성 전에 거절한다. 이 제한은 원본 게임 규약이 아니라 사용자 PC 비개입 실행을 위한 현재 검증 경계다. `--control-mode manual`은 과거 직접 UI 실행 경로를 명시적으로 선택하되 runner 입력 helper는 사용하지 않는다. 아래 마우스 시험 설명은 이전 기록이며 내부 모드에서 적용하지 않는다.

고정 CP69 후보·기존 DLL/자원·원래 UI 입력을 사용한다. 원본 `LC.exe`, 과거 성공 후보와 사용자 저장을 덮어쓰지 않는다. 기존 CP69 `LC.local.exe`(656a64e7…)는 보존하며 현재 내부 실행은 위 `LC.guard.exe`와 명시 profile을 쓴다.

기존 zstandard native dependency가 CPython 3.12용이므로 아래 고정 Python 3.12.14 runtime을 사용한다. 기본 Python 3.13으로는 genuine resource import가 실패한다. 파일 사전검사(프로세스/서버 실행 없음):

```powershell
& "C:/Users/Chansol/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe" -X utf8 -B tools/local_original_session/launcher.py --preflight --product sibling-internal-lifecycle-integrity-spawn --image work/standalone_boot/current-unmodified-clone/LC.guard.exe
```

실제 실행은 메인 소유다. 아래 UUID는 CP69에 설정된 본인 로컬 UUID이며 테스트용 값을 만들지 않는다. `--store`에는 명시적으로 선택한 저장을 지정하고 `--run-directory`는 존재하지 않는 새 경로를 지정한다.

```powershell
& "C:/Users/Chansol/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe" -X utf8 -B tools/local_original_session/launcher.py --run --control-mode internal --product sibling-internal-lifecycle-integrity-spawn --image work/standalone_boot/current-unmodified-clone/LC.guard.exe --expected-uuid <LOCAL_UUID> --store work/local_original_session/test-profile/characters.json --run-directory work/local_original_session/runs/run-01
```

기본 `--product baseline`은 기존 cp49 bridge SHA와 이미지 폴더 CWD를 유지한다. 별도 진단 빌드는 명시적으로 `--product guard-diagnostic`를 선택한다. 이 프로파일은 `runtime-guard-diagnostic/LC.local.exe`와 source에 고정한 진단 cp49 DLL SHA만 허용하며 원래 clone 폴더를 자원 CWD로 사용한다. CLI로 DLL 해시나 자원 CWD를 임의 지정할 수 없다. 진단 DLL은 기존 검사·호출 순서를 유지하면서 실패 지점 enum을 기록하는 용도이며 guard 우회·동작 수정·정상 동작 성공을 뜻하지 않는다. 실행 폴더 배치는 메인이 준비하며 원래 clone과 동결 DLL을 덮어쓰지 않는다.

같은 자원 폴더에서 진단할 때는 `--product sibling-guard-diagnostic --image work/standalone_boot/current-unmodified-clone/LC.guard.exe`를 명시한다. 이 known profile은 기존 CP69의 등폭 import 이름 두 군데만 `cp49`→`dg49`로 바꾼 고정 후보 SHA `8b9e2628…650b684`와 `own-login-bridge-dg49.dll` SHA `2af9a217…701d0d9`를 사용한다. 실행 폴더·CWD·자원은 원래 clone과 같으며 기존 `LC.exe`·`LC.local.exe`·cp49 DLL을 변경하지 않는다. 새 PID/birth context에는 이 프로파일의 실제 image SHA가 기록된다.

Connect 역할 재검증 제품은 `--product sibling-connect-fix`를 명시한다. 같은 `LC.guard.exe`·후보 SHA·CWD와 dg49 DLL 이름을 사용하되 이 프로파일의 DLL SHA는 `39b56477…7903013`으로 별도 고정한다. `sibling-guard-diagnostic`의 기존 DLL pin은 유지한다. runtime DLL 교체와 실제 실행은 메인 소유다. `status.bridge`는 현재 context 신원이 일치할 때만 `current_original_verified`, `prior_all_roles_verified`, `connect_role_revalidated`의 정확한 bool 값을 추가 기록한다. 이 값은 진단 관찰이며 guard admission을 대신하지 않는다.

메모리 query 진단은 `--product sibling-memory-query`로 선택한다. 실행 이미지·자원 CWD·dg49 DLL 이름은 Connect 프로파일과 같으며 DLL SHA만 `bdb1d851…b90c167`로 별도 고정한다. 기존 guard 판정은 유지한 진단 빌드이고 이전 프로파일·고정 원본은 보존한다. runtime DLL 교체와 실제 실행은 메인 소유다.

`--product sibling-source-retry`는 DLL `96683321…7da5be9`로 고정한다. 이전 완전 게시와 동일 target·정확한 NOACCESS image span 조건에서 한 번 안전 읽기를 시도하고 원래 전체 검증을 다시 요구한다. `retry-input-05`에서 Selected source retry와 원래 Selected 반환까지 실제 확인했다. `--product sibling-verified-duplicate`는 DLL `46cc8a82…cf9d67`로 고정하며 full-verified Connect의 중복 연결 경로를 추가한다. `verified-init-06`에서는 이 새 경로가 미발동이므로 Login 성공 프로파일로 표시하지 않는다. 두 프로파일의 이미지·CWD·기존 보존물 경계는 위 sibling 프로파일과 같다.

`--product sibling-duplicate-diagnostics`는 DLL `82adeaa1…aa3f0b`로 고정한 진단 전용 후보다. 바로 위 duplicate 판정·원래 호출 순서를 유지하며 fresh context에 입력 port·최초 거절 조건·Task 진입/borrow scope의 제한된 scalar 기록만 추가한다. 별도 게임 메모리 읽기나 query를 추가하지 않는다.

최종 socket 수정 후보 `--product sibling-verified-socket-duplicate`는 DLL `1d1f60a0…2899f75`를 사용한다. 기존 legacy의 동일 connected owned socket·실제 local peer·phase 경계에 fresh Connect 검증과 이전 완전 게시 증명을 추가한다. 새 Task 주소 동일성 조건·추가 getter·borrowed Task TLS는 사용하지 않는다. 기존 source retry와 legacy 경로·ASM·exports를 유지한다. 실제 성공 범위는 해당 run의 메모리·통신 결과로 판단한다.

launcher는 같은 retained reader로 `EdgeAdapter`를 준비하고 broker의 `edge_passability`에 연결한다. 선택된 월드 UID/map, 서버 권한 시작점의 mask1 통행 조건, 양쪽 완전 spatial query가 비어 있거나 정확한 현재 MyPlayer pointer만 포함하는 조건과 안정된 재읽기가 모두 확인된 edge만 허용하며 UNKNOWN은 기존 위치 보정으로 처리한다. 최종 `edge_check`에는 마지막 판정 요약을 남긴다. 현재 client grid는 서버 authority로 사용하지 않는다. 이 로컬 서버 subset의 실제 한 걸음 성공은29/30 근거에 한정하며, 원본 Navigation 전체 동등성은 미확인이다.

```powershell
& "C:/Users/Chansol/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe" -X utf8 -B tools/local_original_session/launcher.py --preflight --product guard-diagnostic --image work/local_original_session/runtime-guard-diagnostic/LC.local.exe
```

launcher는 선택 프로파일의 실행 이미지·두 sibling DLL의 실제 해시를 검사하고 읽기 핸들을 유지한다. 기존 원본 native wrapper의 suspended CreateProcess → retained handle → Job → resume 경로를 재사용한다. CWD는 위 known profile에 고정한다. 생성된 PID/birth와 candidate hash는 bridge가 실제 요구하는 `work/local_native_login_key_invoke_boundary/runs/ls-.../context.json`에 canonical compact JSON으로 쓰고 `OWN_KEY_INVOKE_BOUNDARY_DIR`를 자식에게 상속한다. 이 context는 해당 새 프로세스만 식별하며 과거 PID나 실행 허가를 재사용하지 않는다.

브로커는 `127.0.0.1:12000`과 `127.0.0.1:14030`을 배타적으로 예약한다. KEY/VERSION/COUNTS에는 기존 `PreservedConversation`과 실제 보존 resource key·signed pack 인증을 사용한다. VERSION은 4개 transient slot만 만들고 각 connection에서 1회 소비·wipe한다. 자원 생성이나 종료 때도 secret 값을 로그·해시·보고서에 출력하지 않는다. 과거 공식 로그인/SDK 프로세스를 새로 실행하거나 attach하지 않는다.

내부 모드는 위의 명시 command 파일로 원래 callback을 호출한다. 기본 제품 수명에는 60/120초 종료가 없다. 사용자가 게임을 종료하거나 run directory에 `close.request` 파일을 만들면 종료한다. Ctrl+C도 저장·정리 경로로 처리한다. `--test-duration N`은 메인의 제한된 실행 검증에만 쓰며 결과를 `TEST_DURATION`으로 구분한다.

메인이 실제 화면으로 확인한 client 좌표는 같은 run directory의 `input.request.json`에 명시해 원래 창 입력 경로로 한 번 전달할 수 있다. 예: `{"schema":"local-original-input-request-v1","action":"left_click","x":410,"y":380,"expected_scene":"Login","sequence":1}`. 이 좌표는 형식 예시이며 실제 버튼 위치를 뜻하지 않는다. `expected_scene`은 Intro/Lobby/Login/CharacterSelect/Land 중 하나이며 순번은 1부터 엄격 증가한다. 같은 retained primary와 GLFW/client rectangle을 확인한 WM_MOUSEMOVE→WM_LBUTTONDOWN→WM_LBUTTONUP만 사용한다. RUNNING과 설정된 CLOSING 대기에서 monitor 갱신 뒤 요청을 확인하므로 원래 종료 확인창에도 명시적 요청을 전달할 수 있다. native 종료·broker 실패·정리 중에는 입력하지 않는다. 명시 input은 같은 retained/scene/window/DPI 확인 뒤 현재 foreground를 읽고, 필요할 때 소유 HWND에 SetForegroundWindow를 한 번 요청한다. 이는 best effort 관찰이며 거절돼도 같은 owned HWND의 기존 메시지 경로를 사용할 수 있다. OS foreground 정책을 우회하거나 자동 재활성화하지 않는다. 결과의 foreground_before/focus_attempted/focus_succeeded는 이 관찰만 뜻한다. `action=mouse_move`는 같은 strict6field/단조 sequence 경계에서 WM200 한 번만 보내며 DOWN/UP은 없다. 명시 input은 target DPI context의 ClientToScreen으로 위치를 구하고 자기 thread context 복원을 확인한 뒤 SetPhysicalCursorPos를1회만 요청한다. 실제 physical cursor 위치와 owner/window/scene/변환 target을 재확인하고 같은 소유 HWND 메시지를 보낸다. OS실패·clip·사용자cursor이동은 중단하며 global mouse button·커서 자동복원·재이동은 없다. DOWN 뒤 release는 기존과 같이 같은 owned window에만 보낸다. `input.result.json`의 POSTED는 메시지 게시 결과이며 UI 동작은 UNKNOWN이다. poll 예외는 class 이름만 최종 결과에 기록하고 해당 세션 입력을 중지하며 자동 재시도하지 않는다. 종료 확인 UI 후 OS 종료가 관측돼도 게임 로그아웃 wire 검증으로 승격하지 않는다.

전용 runner는 시작 전에 reader source·contract를 한 번 준비하고 현재 owner의 retained process handle을 읽기 전용 `0x101010`으로 DuplicateHandle한다. PID를 다시 attach하지 않고 같은 birth/image/Job을 전후 확인하면서 기존 scene sampler를 재사용한다. 기본 0.75초 간격, 합산 sample당 16384바이트(기존 leaf별8192)·최소 0.5초 간격을 유지하며 세션 누적 counter는 포화 처리한다. 최초 KEY write/drain·owner admission 전에는 typed memory와 window 관측을 미룬다. 연결 없이 5초가 지나면 초기 오류를 놓치지 않도록 known public window metadata만 먼저 확인한다.

`status.json` 한 파일에 현재·최초·마지막 관찰 scene, 알려진 caption/error·창 class/geometry, broker 상태·마지막 opcode/길이를 32KB 이내로 원자 갱신한다. 상태가 같으면 파일을 다시 쓰지 않는다. unknown UI text·그 해시·Edit/ComboBox 값·화면 캡처·raw pointer·패킷 본문은 저장하지 않는다. 현재 PID/birth/image SHA가 같은 fresh `connect-probe-0.json`/`1.json` 두 개만 각 8KB 이내로 읽고 고정 진단 필드를 `bridge`에 붙인다. 이 metadata는 native guard admission 근거가 아니다.

장면·연결·bridge·종료 상태처럼 메모리와 로그로 판단 가능한 항목에는 화면 캡처를 사용하지 않는다. 실제 표시 확인이 필요한 경우에만 별도로 캡처한다. 캡처 정상 동작은 기존 실제 게임·종료창에서 확인했으며 `retry-input-05`의 흰 화면은 사용자 모니터 꺼짐 상황으로 확인됐다.

명시적 실행 검증에서 `--until-scene Land`를 추가하면 `OBSERVED/current=Land/pending=none/root_ready=true`인 완전한 read 한 번에 `OBSERVATION_CONDITION`으로 종료한다. 기본은 조건 종료가 없다. 이 조건이나 monitor 성공은 실제 화면 표시·정상 로그아웃·게임 완료 증거가 아니다. 실제 화면 확인이 필요할 때만 메인이 Computer Use를 별도로 사용한다. 반복 `observe.py` attach 대신 실행 중 `status.json`을 읽으면 된다.

사용자 종료·Ctrl+C·명시적 검증 종료는 내부 모드의 원래 Quit 명령(과거 manual 모드만 소유 HWND의 WM_CLOSE) → broker·resource slot을 유지하며 기본 최대 10초 native 종료 대기 → broker close(기존 CharacterStore의 동기 atomic commit 및 연결·task 정리) → 남은 소유 Job만 정리 → resource/slot wipe 순서다. 대기 중 native 종료나 broker failure가 확인되면 바로 정리로 진행한다. 이미 종료된 native와 세션·broker 실패에는 이 대기를 추가하지 않으며 반복 취소도 같은 broker cleanup task의 완료를 기다린다. `--close-grace-seconds 30`으로 종료 확인 입력을 기다릴 시간을 명시적으로 늘릴 수 있으며 허용 범위는 `0 < 값 <= 120`초, 기본값은 10초다. 이 값은 종료 요청 뒤의 제한된 대기이며 제품 세션 timeout이나 게임 규약이 아니다. `close_wait_end`는 대기 종료 원인만 기록하며 게임 로그아웃 성공을 뜻하지 않는다. retained process handle의 PID/birth/image/token과 Job membership을 확인하며, TCP 요청은 fresh OS table의 정확한 loopback tuple과 연결한다. CP69의 flags=0 image-query 실패 때는 동일 process handle의 flags=1 NT 경로를 현재 pinned 실행파일 handle의 NT 경로와 실제 비교한다. 실패·불일치·PID/birth 변경·종료는 거절하며 cached old image를 증거로 사용하지 않는다.

최종 결과는 새 run directory의 `result.json`과 `boundary-path.txt`에 남는다. `PREFLIGHT_FILES_VERIFIED`는 실행파일/DLL 확인만 의미한다. 실제 기동·반복 종료·월드·저장·이동 증거는 메인의 native 실행에서 별도로 확인한다. `CharacterStore` 형식은 재사용하며 위치는 별도 `positions.json`에 저장한다. 실제29의 original command 이동·once commit과30의 새 기동 복원 근거는 `work/local_original_session/INTERNAL_COMMAND_VALIDATION_20261016.json`에 기록한다.

`USER_CLOSE`는 사용자가 종료를 요청했다는 뜻이다. `positive_exit`와 `owned_job_empty`는 OS 정리 증거이며 게임의 정상 로그아웃을 증명하지 않는다. `exit_outcome`은 `FORCED_CLEANUP`, `NATIVE_EXIT_NO_FORCE`, `NOT_LAUNCHED`, `CLEANUP_UNKNOWN`으로 구분한다. 같은 connection의 원래 Quit·응답 drain·EOF·positive close/join/등록 제거와 primary exit0·Job 전체 무강제 정리가 모두 확인된 실행만 `normal_exit_verified=true`, `game_logout_protocol=SOURCE_QUIT_DRAIN_EOF_EXIT0`로 표시한다. 이 값은 해당 종료 흐름의 증명이며 전체 게임 동등성 판정은 아니다. WM_CLOSE 요청이나 callback RETURNED만으로는 true가 되지 않는다.

표적 fixture 검사(게임/native/브로커 실행 없음):

```powershell
& "C:/Users/Chansol/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe" -X utf8 -B -m unittest tools.local_original_session.launcher_tests
```

