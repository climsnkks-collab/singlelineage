# LOCAL 동료 직접 소환: 원 클라이언트 hotkey 경로 확인

상태: **SOURCE_FINDING_COMPLETE / NATIVE_SEND_ABI_NOT_SUPPLIED / test_ready:false / runtime:UNRUN**.

사용자가 임시 LOCAL 직접 hotkey 소환을 승인한 범위에서 기존 source만 읽었다. 현재 선정 source에는 같은 WORLD 세션에서 임의 LOCAL 소환 payload를 원 클라이언트로 송신하는 완결 경로가 없다. 실행 가능한 hotkey/DLL/packet caller를 만들지 않았다. 이는 소환 기능의 제품 구현 완료나 새 권한 요구가 아니다. 서버의 새 LOCAL route 작업과 독립적인 native 입력·message ABI 결손이다.

## 1. 기존 WH_GETMESSAGE가 실제 제공하는 범위

- `tools/local_original_session/native/command_bridge.hpp:220`의 GetMessage는 `code>=0`, `PM_REMOVE`, 선정 HWND, 등록된 `LC-Owned-Internal-Command-v1` 메시지만 소비한다. 실제 WM_KEYDOWN/WM_SYSKEYDOWN은 해석하지 않는다. 기존 명령은 1=login OK, 2=character select OK, 3=quit, 4=원 own-player 이동이다. command 범위를 늘리는 것만으로 새 native 송신이 생기지 않는다.
- 같은 파일의 Install은 `BackgroundGuardCurrentDesktop()`와 18개 보호 export, 정확한 GLFW30 HWND/소유 thread/원 window anchor를 확인하고 그 **한 thread**에 WH_GETMESSAGE를 설치한다. 전역 hook가 아니다.
- `background_guard.hpp:33–58`은 `OWN_INTERNAL_COMMAND_MODE=1`과 `LC-Owned-Internal-<32hex>` desktop을 요구한다. `launcher.py:915`가 실제 private desktop 이름을 전달한다. `desktop.py:25`의 PrivateDesktop은 입력 desktop이 아닌 새 desktop을 만들고, `verify_non_input`이 이를 확인하며 SwitchDesktop을 호출하지 않는다.
- 따라서 이 bridge를 그대로 포함한 hidden/background 게임에는 foreground에서 사용자가 누른 물리 키가 도달하지 않는다. guard를 없애거나 desktop을 전환하면 기존 격리 계약을 변경하게 된다. 이번 source 작업에서 그런 변경은 하지 않았다.

향후 사용자 조작용 foreground 게임에 넣는 경우에는 **현재 게임이 foreground이고 현재 UI thread에서 꺼낸 해당 HWND의 키 메시지일 때만** 동작하는 별도 선택 경계가 필요하다. 현재 command bridge의 background 전제와 동일하다고 주장할 수 없다. 전역 RegisterHotKey/WH_KEYBOARD_LL/GetAsyncKeyState polling이나 다른 앱의 키를 가로채는 방법은 이 구현에 필요하지 않다. 키 메시지만으로 OS가 생성한 물리 입력인지 완전히 증명할 수 있다는 주장도 하지 않는다.

## 2. 원 outbound 접점과 사용할 수 없는 지름길

`tools/local_native_login_key_invoke_boundary/producer.cpp`에는 다음 실제 ABI가 있다.

| 원 접점 | 확인된 source 계약 | 이 기능의 미확인 |
|---|---|---|
| base+3EC40 | `Pair*(*)(void* publishedRoot, Pair* out)`; 원 Root+D8 게시 gate를 사용하며 getter가 발급한 Pair를 원 해제 순서로 유지 | 현재 WORLD/current owner와 동일 세션/동일 network epoch인지, reselection/close에 대한 lifetime 경계 |
| base+27D620 | `void(*)(void* network, uint16_t opcode, Message*)`의 **3개 인수**; 원 `26DA90` 네 인수 ABI와 다름 | 새로운 LOCAL payload용 원 protobuf 객체의 생성·clone·직렬화와 송신 결과 관측 |
| base+799D00 / DDE430 / 799FD0 | 기존 0263 login Message의 factory/string setter/destroy; struct size38, hasbits/cache/issuer/uuid/address와 vtable11F09D0 | 숫자 saved character UID를 담는 별도 LOCAL request의 factory/field/hasbit/serializer ABI |

기존 `SendOwnLoginPublished`는 진짜 Root에서 getter를 호출하고, `SendOwnLoginHeld`는 Pair retain→원 0263 객체 생성→deep-clone sender 호출→temporary destroy→Pair release 순서를 공급한다. **0263 객체에 다른 opcode만 넣으면 올바른 LOCAL 소환 payload가 되는 것은 아니다.** 임의 가짜 vtable/Message를 만들어 원 sender에 넘길 근거가 없다. 같은 함수의 주석은 sender가 role0 없으면 조용히 반환할 수 있으므로 반환만으로 enqueue/socket delivery/server 성공이 증명되지 않음을 명시한다.

기존 `abi_bridge_v2.cpp:135`의 OwnLoginSenderBridge는 원 호출을 먼저 그대로 전달하고, 선정 caller+2746FF+4F3D 조건에서 login source를 소비한다. `caller.cpp`의 Selected/Connected/Dispatching/SenderReturned/Cancelled는 그 **login 작업** 수명이다. 이를 WORLD 소환의 session epoch나 current authority로 쓰지 않는다.

`integration-1/item-normal-current-serial348-v1/native/entry_native.hpp`의 B6D20/B7DB0는 원 GroundItem Interaction GET 경로다. 기존 consumer를 동료 소환으로 호출하거나 UID2를 GroundItem/기발행 ally UID로 바꾸지 않는다. 기존 4F13은 기발행 actor의 settings click 경로이고 첫 summon producer가 아니라는 기존 계약을 재사용한다.

root가 전달한 **잠정 서버 계약**은 `LOCAL C2S opcode=0xF101`, payload 길이0, 기존 `<HIHH>` 10-byte frame와 실제 연결 sequence다. 서버가 같은 계정의 유일한 다른 class3 mage를 선택하며 client는 UID/mode를 보내지 않는다. opcode 충돌 검사·descriptor는 아직 담당 진행 중이므로 확정/가동 계약으로 봉인하지 않는다. 이 계약이 확정되면 native 질문은 숫자 UID message가 아닌 **원 empty-payload Message 또는 원 raw-frame encoder**로 좁혀진다. client가 직접 frame sequence를 추측하거나 일반 TCP sender로 새 연결을 열지 않는다.

## 3. 별도 REA 담당에게 넘길 정확한 질문

새 LOCAL wire descriptor가 확정되면, 기존 저장 분석을 먼저 재사용하여 아래만 확인한다. 구현 채팅에서 새 REA/decompile/runtime 분석을 실행하지 않았다.

1. **같은 WORLD 세션의 send receiver:** 원 WORLD 입력 처리 owner/UI thread에서 현재 Root의 3EC40 getter가 발급하는 object/control Pair가 실제 현재 connected network임을 어떤 원 필드/원 getter/owner lock로 확인하는가? close/reselection 전에 Pair만 retain해 둔 낡은 연결을 배제할 최소 native current 경계는 무엇인가? 기존 login-selected caller state는 대용으로 쓰지 않는다.
2. **새 LOCAL wire의 원 Message 객체:** 잠정 F101/zero payload라면 **정확히 empty protobuf를 직렬화하는 원 메시지 type**의 factory/vtable/hasbits/cache/clone/serializer/destroy를 확인하고 이 type을 원 sender에서 LOCAL opcode와 함께 쓰는 것이 지원되는지 확인한다. 임의 struct/vtable로 대체하지 않는다. 그 type이 없으면 **이미 직렬화된 bytes를 원 framing/cipher/현재 socket queue로 전달하는 실제 원 함수**의 ABI·크기·버퍼 ownership·copy/retain 수명과 thread 요구를 확인한다. `<HIHH>` sequence는 그 동일 connection의 원 경로가 발급해야 한다. 독립 TCP client/new port는 같은 original client session을 대신하지 않는다.
3. **전송의 관측 경계:** 27D620의 정상 return과 실제 enqueue/drain/server 응답을 구분할 기존 관측은 무엇인가? 부분 enqueue나 예외 뒤 자동 재시도하지 않으며, 같은 WORLD request의 첫 실패와 원문을 보존할 수 있는가?

message type과 current network가 확인되면 원 thread-local callback 안에서 원 builder→원 sender를 한 번 호출하는 private descendant를 만들 수 있다. 새 사용자에게 보이는 단축키 선택과 충돌 확인은 그 descendant에서 구체화한다. 그 전에는 이름만 있는 callback/동작하지 않는 sender stub를 제품 source로 등록하지 않는다.

## 4. 완결 후보가 공급될 때의 최소 실행 흐름

1. Test가 통과한 saved ROOT+other class3 mage의 정당 전체사본을 새로 만든다. 기존 `companion-summon-input-v1/input-source.json`과 더 최신 정상 복원 결과의 실제 선택을 root가 확정한다. 사용자 원본과 다른 시험 사본을 수정하지 않는다.
2. 공용 packet client-v5/API 및 기존 caller를 재사용해 정상 KEY/VERSION/login/roster→ROOT direct 선택→WORLD/current/실RESOURCE를 먼저 확인한다. target saved character UID는 roster/account에서 받은 값이며 고정 ally UID가 아니다.
3. packet 경로 시험은 확정된 LOCAL request만 보내 원 decoder/router/handler와 소환 callee를 거친다. 앞 응답/상태 확인 후 다음 단계만 보낸다. Host/controller 직접 호출, fake interface, 준비상태 강제는 하지 않는다. 이 부분이 native physical key 성공을 증명하지 않는다.
4. native 사용자 조작 시험은 사용자가 실제 foreground 게임 안에서 누른 선택 키→같은 WORLD owner network의 원 builder/encoder/send→LOCAL request→실 발급 allied UID/current→4E96 publication 응답/상태라는 별도 증거가 필요하다. 이 native 요구 때문에 packet 기능 시험을 대기시키지 않는다. 이번 source finding에는 실행 명령이 없다.
5. 최소 Store/원 actor UID cursor·부분 저장·첫 실패 원문/owner close를 기존 도구로 보존한다. native actor pose/렌더/AI/ATS·정상Quit는 별도 실제 관측 없이 성공으로 확대하지 않는다.

## 5. 이번 변경과 확인

새 private 폴더의 이 계약·parents/manifest만 작성했다. 원 native source, 공용 client/ready_current/API, launcher/desktop, runtime/포트/저장은 변경하지 않았다. source parents의 실제 SHA256/size는 parents.json에 저장했다. **빌드0, 게임0, hook 설치0, Windows 입력0, network0, REA0**이다. 문서/핀을 한 번 재읽어 확인했다. 제품 delta0이므로 구문/ABI build PASS를 주장하지 않는다. `test_ready:false`, `RUN_COMMAND:null`이다.
