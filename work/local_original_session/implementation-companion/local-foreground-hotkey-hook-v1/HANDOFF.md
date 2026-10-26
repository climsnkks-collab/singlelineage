# LOCAL foreground Ctrl+Shift+M private candidate

상태: **SOURCE_CANDIDATE_COMPILED / NATIVE_SENDER_NOT_SUPPLIED / test_ready:false / runtime:UNRUN**.

신규 `local_foreground_hotkey.hpp`는 사용자 조작용 foreground 게임에서 임시 LOCAL 소환 키를 처리하기 위한 독립 후보다. 기존 `command_bridge.hpp`의 WH_GETMESSAGE/PM_REMOVE/정확 HWND·UI thread 범위와 `land_hook.hpp`의 revoke·callback 수명·unhook 실패 보존 원칙을 재사용했다. 기존 private desktop/background bridge·launcher·Client·Test·Store에는 연결하거나 수정하지 않았다. 원본 게임은 기동하지 않았다. 이 폴더만 작성했다.

## 입력 경계

- Ctrl+Shift+M을 채택했다. 이는 임시 LOCAL 선택이며 원 게임 공식 단축키·충돌 없음이 확인됐다는 뜻은 아니다. Alt/Windows modifier 동시 입력은 거부한다.
- hook는 현재 프로세스의 **실제 game HWND 소유 UI thread 안에서만** 설치할 수 있다. source-backed `resolve_game_window`가 같은 HWND를 반환해야 한다. 실제 메시지도 그 HWND의 PM_REMOVE 키 메시지이고 현재 UI thread가 일치해야 한다.
- 콜백은 GetForegroundWindow()==game을 확인하고, 해당 message queue의 GetKeyState로 modifier를 읽는다. 키를 처리하는 시점의 조회이며 타이머/polling은 없다. M 최초 keydown만 처리하고 bit30으로 autorepeat를 억제한다. 다른 앱에서 시작된 press·modifier 뒤늦은 추가·foreground 복귀 중 repeat도 호출하지 않는다. HWND 밖에서 keyup이 발생해도 다음 새 press를 막는 latch는 두지 않는다.
- MSG를 수정하거나 키를 삼키지 않는다. 모든 경로가 CallNextHookEx로 이어진다. RegisterHotKey/전역 hook/WH_KEYBOARD_LL/합성 입력/포커스 변경은 없다. 이 입력 필터는 OS 메시지가 물리 입력이라는 증명은 제공하지 않는다.

## 송신 공급 전 설치 금지

`Install(game, binding)`의 binding은 원 game HWND resolver, `try_send` 함수, nonzero expected_world_epoch를 모두 요구한다. 하나라도 없으면 module pin/hook 설치 전에 MissingSourceBinding을 반환한다. **이번 결과에는 생산용 binding/try_send 구현도, Install 호출부도 없다.** 검사용 fake sender·stub 반환도 없다.

`try_send(context,game,ui_tid,expected_world_epoch)`는 C++ host 인터페이스다. 이것을 원 sender ABI로 추측하지 않는다. 후속 공급자는 호출 안에서 현재 WORLD의 실제 owner/epoch와 수명 경계를 획득·대조한 채 원 builder/encoder→같은 network queue로 **F101/empty payload를 단 한 번** 보내야 한다. 해당 callback의 context와 함수는 Close가 Closed를 반환할 때까지 살아 있어야 한다. resolver는 원 HWND anchor 조회만 하며 설치·종료나 송신으로 재진입하지 않는 공급자 계약이다.

아직 빠진 원 ABI는 기존 `local-hotkey-client-path-v1/CONTRACT.md` §2–3과 같다.

1. 현재 WORLD의 Root getter `base+3EC40` Pair가 같은 연결/current epoch임을 확인하고 reselection/close 동안 보존하는 실제 owner/lifetime 접점. 예전 login-selected caller의 상태는 대용이 아니다.
2. `base+27D620`의 알려진 **3인수** 원 Message sender에 사용할 empty Message의 factory/vtable/clone/serializer/destroy, 또는 원 framing/cipher/connection sequence를 유지하는 실제 raw encoder ABI. 0263 login Message를 opcode만 바꾸거나 임의 struct/vtable을 만들지 않는다.
3. 실제 enqueue/drain/server 응답의 원 관측 접점. OriginalSendAttempted는 호출 시도 분류일 뿐 패킷/서버/소환 성공이 아니다. 실패/부분 송신을 자동 재시도하지 않는다.

새 TCP 연결·추측 frame sequence·준비 상태 강제·fake ACK가 없다. 별도 서버 F101 직접 패킷 시험은 기존 `local-summon-packet-trial-v1`의 caller를 그대로 사용하며 이 native ABI 때문에 대기시키지 않는다. 이번 후보를 packet 시험 통과나 단축키 동작 완료로 등록하지 않는다.

## 수명과 정리

생산 호스트는 source-backed UI thread 진입점에서 Install을 호출하고 같은 thread에서 Close한다. hook callback 코드가 있는 모듈은 GetModuleHandleEx(PIN)으로 process lifetime에 고정한다. hook 설치 실패 뒤에도 pin은 process 종료까지 유지된다. runtime 중 DLL unload는 지원하지 않는다.

Close는 먼저 revoked로 전환하고 UnhookWindowsHookEx의 실제 BOOL을 확인한다. 실패 시 handle·context를 보존하고 UnhookFailed를 반환하며 같은 UI thread의 명시 Close로만 다시 정리한다. 콜백 도중 동기 종료가 재진입하면 shared lifetime lock을 재획득하지 않고 DrainPending을 반환한다. sender가 돌아온 뒤 기존 UI thread 소유자가 Close를 다시 호출해 Closed를 확인한 다음 context를 해제한다. Close가 성공하기 전 재설치는 거부한다. 기존 background 게임에 이 후보를 주입하거나 desktop을 전환하는 호출은 없다.

## 수행한 최소 확인과 실행 명령

프로젝트 root에서 다음 한 명령은 **컴파일 및 비기동 fixture만** 실행한다.

```bat
cmd /c work\local_original_session\implementation-companion\local-foreground-hotkey-hook-v1\build_check.cmd
```

기존 VS2022 vcvars64/MSVC C++17 도구로 `/W4 /WX /EHsc /O2 /MD` 빌드 exit0. fixture exit0이며 `verification.txt`에 결과를 보존했다. fixture는 빈 binding의 설치 거부·첫 press/repeat/keyup·부적격 press/다른 키 분기만 확인한다. resolver/원 sender 호출·실제 hook 설치·foreground/실키 관측·unhook 실행은 수행하지 않았다. compile_check.exe는 제품 DLL/게임 caller가 아니다. 상용·실게임 ABI 성공을 주장하지 않는다.

게임용 RUN_COMMAND는 **null**이다. native sender/current epoch ABI와 기존 소유자의 정확 source 선정·정상 WORLD 준비/실키→원 packet→응답/상태·최소 Store/첫 실패/정리 caller가 함께 공급되어야 native test_ready가 될 수 있다. 기존 Test의 packet caller를 복제하거나 공용 API를 수정하지 않았다. 이 단위는 새 REA/프로세스/포트/저장/사용자 입력 없이 마감했다.
