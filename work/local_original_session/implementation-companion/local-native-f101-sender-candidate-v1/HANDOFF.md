# COMPANION-MAGE LOCAL F101 native sender: first missing source

**SOURCE_FINDING_COMPLETE / NATIVE_SENDER_NOT_SUPPLIED / test_ready:false / packet_test_gate:false / runtime:UNRUN / WRITER_RELEASED.**

REA290의 확정 계약과 기존 native login source·foreground hook를 대조했다. 현재 읽은 source로는 **같은 authenticated WORLD 연결에 empty F101을 안전하게 보내는 실행 후보를 만들 수 없다.** 새 sender·Message·binding stub·DLL·Install caller를 만들지 않았다. 새 private 폴더의 이 인계와 핀/확인 JSON만 작성했다. 공용 파일·큐·기존 부모는 변경하지 않았다.

## 확인된 원 경로

- `tools/local_native_login_key_invoke_boundary/producer.cpp:25–38,74–103`: `Send=void(*)(void*,uint16_t,Message*)`로 `base+27D620`을 호출한다. `base+799D00/799FD0`, vtable `base+11F09D0`, sizeof38 Message는 원 **0263 login 전용**이다. 이를 F101로 retag하거나 hasbits를 비워 empty carrier로 쓰지 않는다.
- REA290 `contract.md`와 `sender/contract.md`: 27D620은 RCX=NetworkSubsystem, EDX=opcode, R8=typed Message다. `[NetworkSubsystem+198]` manager를 통해 26DA90의 exact key0 node로 전달한다. 숫자0은 WORLD enum으로 확정되지 않았다.
- 26DA90은 원 `M.v10(M,0)`으로 새 N을 얻고 `N.v30(N,M)`을 호출한 뒤 N을 담은 payload/control Pair를 node+C0 큐에 소유 이전한다. 구체 타입의 deep-copy·직렬화·파괴 의미는 미확정이다. 기존 producer.cpp의 “deep clone” 주석을 REA290보다 강한 근거로 사용하지 않는다.
- REA290 `world_pair/contract.md`: `base+3EC40`은 RCX=owner/RDX=신선한16B output/RAX=동일out이다. owner+D0의 +180/+188 배열에서 첫 castable NetworkSubsystem을 반환하며 control+8을 retain한다. authenticated WORLD/선택 캐릭터/현재 연결·epoch/thread·retirement 권위를 검사하지 않는다.
- 기존 `caller.cpp`의 Selected/Connected/Dispatching/SenderReturned/Cancelled와 `abi_bridge_v2.cpp`의 sender forwarding은 login-selected 작업의 수명이다. 이를 WORLD 소환 owner·epoch로 대입하지 않는다. sender RET는 enqueue·socket write·응답·소환 성공이 아니다.

## 첫 미공급 두 묶음

1. **F101 empty Message 또는 실제 원 raw encoder.** typed 경로라면 구체 factory/type/descriptor, v10 factory·v30 copy, 정확히 0 bytes가 되는 serializer와 destroy/arena 계약이 필요하다. 현재 27D620은 raw `(bytes,size)` ABI가 아니다. 대안은 원 queue pop의 N→bytes→header/sequence/cipher→같은 socket queue를 사용하는 실제 raw entry의 ABI·buffer ownership·copy/retain 수명이다. REA290의 26EE70은 queue segment allocator이며 rawsend가 아니다. control v0 target26EDC0은 body/decode 미공급으로 파괴 완료 근거도 아니다.
2. **같은 현재 WORLD의 원 producer/caller.** 실제 UI/owner callback에서 Root·NetworkSubsystem Pair·manager가 현재 authenticated selected WORLD connection과 같은 것임을 연결하는 기존 설치/교체·dispatch·retirement source가 필요하다. Pair retain만으로 낡은 연결을 배제할 수 없다. 원 epoch 형식은 미확정이며 임의 native field/새 handshake/LOCAL lease generation을 발명하지 않는다. 원 owner 직렬화에서 호출·교체/close를 막고 정상 반환까지 유지하는 실제 경계가 필요하다.

위 두 입력이 오면 원 queue consumer의 송신/부분 실패와 원 서버 응답 관측까지 같은 request에 연결한다. 부분 enqueue/예외 뒤 자동 재시도하지 않는다. 원 framing/sequence는 같은 연결의 원 경로에서 발급되어야 하며 새 TCP 연결이나 수동 frame 추측으로 대체하지 않는다.

## 기존 Ctrl+Shift+M 접점의 정확한 소비

`local-foreground-hotkey-hook-v1/local_foreground_hotkey.hpp`의 `SenderBinding`이 유일한 공급 접점이다. 후속 후보는 같은 header의 `resolve_game_window`와 `try_send(context,game,ui_tid,expected_world_epoch)`를 실제 원 owner source에 연결해야 한다. `expected_world_epoch`는 현재 hook의 C++ 공급자 인터페이스이며 **원 client에 그 필드/ABI가 있다는 근거가 아니다.** 실제 원 current 권위에 결속할 공급자가 없으면 Install하지 않는다.

기존 hook의 same-process/same-HWND/UI-thread·foreground·첫 M keydown·Ctrl+Shift·Alt/Win 거부·PM_REMOVE 경계, CallNextHookEx, revoke/module pin 및 Close의 DrainPending/UnhookFailed 수명은 그대로 재사용한다. production resolver/context는 Close=Closed까지 살아 있어야 한다. 새 전역 입력 hook·polling·포커스 변경·background guard 변경을 추가하지 않는다. 이번 단위는 hook 설치·실키·송신을 수행하지 않았다.

## 최소 확인과 인계

`parents.json`은 읽은 핵심 source의 실제 SHA256/bytes다. `verification.json`은 REA290 source-refs의 output/child 8핀과 foreground hook manifest의 header 핀을 실제 파일에 대조한 결과다. 이번 단위 product delta0이므로 새 C++ 빌드가 필요한 변경이 없다. 기존 hook의 MSVC compile/fixture PASS는 그 원 source에 한해 재사용하며 native ABI/키 동작 PASS로 확대하지 않는다. 새 build0/runtime0/REA0/network0/게임0/Store0다.

`RUN_COMMAND:null`이다. 이미 준비된 `local-summon-packet-trial-v1`의 같은 정상 WORLD stream/empty F101 caller는 독립적으로 계속한다. 이 native 결손을 packet Test 선행조건이나 전체 구현 중지로 만들지 않는다. root의 후속 REA 요청은 위 **두 묶음의 기존 source 접점**만 공급받으면 된다.
