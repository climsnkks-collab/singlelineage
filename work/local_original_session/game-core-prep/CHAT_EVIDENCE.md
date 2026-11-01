# 채팅·시스템 메시지 원본 수신/송신 근거

2026-10-26 지정 REA. **STATIC PARTIAL / 제품 수정·게임·포트·live attach 없음.** 원문 연결 확인이며 화면·입력·동작 PASS가 아니다.

아래 **observed/static**은 보존 원문·metadata에서 읽은 값/분기, **inferred**는 그 결속에서 도출한 역할, **UNKNOWN**은 미관측이다. runtime observed 항목은 없다. `4E52.f2=24` 자유 시스템 후보와 화면하단 역할은 inferred/미검증이며 정상 서버 발급값으로 확정하지 않는다.

## 결론과 GM 접점

- 확인된 **`HudChatLayoutMobileImpl`**의 일반 **channel 0 → 원 `PurpleCommunityChatAPI::SendMessage`** 경로를 UI 생산자부터 결속했다. 현재 활성 Mobile/PC는 미관측이다. 이 경로의 게임 소켓용 `CS_CHAT_REQ` opcode·protobuf body는 확인되지 않았다. `4F2D`는 **`CS_CAN_WHISPER_TO_REQ`**, 즉 귓속말 가능 여부 선검사다. 일반 채팅으로 사용하면 안 된다.
- 게임 수신 **`4E52 = SC_CHAT_ACK`**는 `f2` 채팅 종류, `f3` 본문을 원 `ChatMessage → ChatData → HudChatAdapter`에 전달한다. **`4EEA = SC_MESSAGE_CODE_NOTI`**는 `f1` 문자열 번호와 `f2` 반복 인자를 현지화한 뒤 같은 채팅 목록에 전달한다.
- `4E52.f2 → 내부 type → 색상 제어문자`는 연결됐다. `4EEA`의 내부 type은 원 메시지 분류 자료에서 정하며 `f3`를 그대로 채팅 색상으로 쓰지 않는다. 자유문자용 **정상 서버 시스템 type·`4E52.f5` 정상값·한국어 wire 인코딩·현재 화면**은 미확정이다.
- 별도 **`00C8 SC_NOTIFICATION_MESSAGE_NOTI`**는 자유 본문·3바이트 색상·시간을 읽지만 원 **`Root.MiddleMessageArea`**에 넣는다. 하단 채팅 메시지로 대체하지 않는다. `00CE SC_MESSAGE_NOTI`는 schema/등록까지만 확인됐고 직접 표시 subscriber는 미확정이다.

따라서 미래 `world_gm.py`의 `decode_chat(payload)->str`을 원 normal0 게임 소켓 수신에 바로 연결할 opcode는 이번 근거에 없다. PURPLE 없이 입력을 받는 로컬 input/bridge 계약은 별도 미완이다. 응답에는 아래 추가 선정의 **`4EEA f1=12066 + f2=본문1개` source 지원 후보**가 있다. 12066 row의 기성 plaintext metadata는 **고정 current catalog의 크기/해시 pin과 일치**하지만 **restored CONTROL 실행 시 같은 자원이 실제 로드되는 결속은 미확정**이다. `encode_system_message(text)->bytes`의 **한국어 wire/하단 실표시까지 검증한 완성 계약은 아니다.** 제품 코드는 변경하지 않았다.

## 기준 Source와 재사용 경계

원 추출기는 [run392/extract.py](../../local_server_rea_20261016/run392_chat_system_message/extract.py)이며 기존 [run380/f2_research.py](../../local_server_rea_20261016/run380_map_transition_receive/f2_research.py)의 **View·restored section·PData·Capstone**을 import 재사용했다. import 전에 bytecode 쓰기를 껐다. 기존 run·원 LC·자원·저장에는 쓰지 않았다. 기존 HANDOFF/ANALYSIS_RESULTS·shared-api·game-core-prep에서 채팅 전용 wire 계약은 찾지 못했고, 공통 protobuf typecard·required-mask 판독은 REA104의 `wire_schema/schema_stage.py`, `fast_wire_proof.py` 방식을 재사용했다.

기준은 `C:/Users/Chansol/Documents/Codex/2026-09-07/d-lineage-classic/work/current_client_key_mapping/selector_0_record_*.bin` 6개 복원 section이다. **inherited CONTROL SHA256 `9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`**, preferred base `140000000`. 주소는 모두 그 **RVA**다. [identity.json](../../local_server_rea_20261016/run392_chat_system_message/identity.json)에 원 record 경로/해시 계보가 있다. 새 전체 해시는 계산하지 않았다.

**현재 disk `LC.guard.exe` 동등성은 미확인**이다. 기존 [run380/f2_identity.json](../../local_server_rea_20261016/run380_map_transition_receive/f2_identity.json)은 disk 39,147,520B의 선정 4개 window가 restored CONTROL과 다름을 보존한다(`/anchors/*/equal_to_restored:false`). 이를 새 채팅 함수별 disk 비교로 확대하지 않았고 이전 mismatch를 성공으로 바꾸지 않았다. 이번 결과는 restored 분석 자료의 계약이다.

선정 원문은 [selected.txt](../../local_server_rea_20261016/run392_chat_system_message/selected.txt), 원 JSON pointer가 포함된 [selected-evidence.json](../../local_server_rea_20261016/run392_chat_system_message/selected-evidence.json)이다. 재선정 명령은 `python work/local_server_rea_20261016/run392_chat_system_message/select_evidence.py`다. 이것은 저장된 추출 결과를 고르는 작업이며 제품 시험·검사기가 아니다.

## 원 일반 채팅 송신

확인된 **`HudChatLayoutMobileImpl`**의 UI 기본 channel 0은 생성자/초기화가 `[this+160]=0`으로 저장한다. 송신 `9AFF20`은 첫 글자를 `473A90`에 보내고 반환 0이면 이 UI channel을 사용한다. `9B0225 → 472380(channel,text)`이고 `4727CA`의 channel==1 예외를 제외하면 `472E2F..472E40 → 481510`이다. `485ED0`의 channel0 literal은 **`NORMAL`**이다. UI 기본값과 literal 이름을 함께 결속한 결과이며 임의 channel 숫자를 일반 채팅으로 명명한 것이 아니다. **현재 Mobile/PC 중 어느 UI가 활성화됐는지는 미관측**이다. 보조 [요약](../../local_server_rea_20261016/run392_chat_system_message/c2s_review_summary.md), [c2s_review_selected.json](../../local_server_rea_20261016/run392_chat_system_message/c2s_review_selected.json), [c2s_review_types.json](../../local_server_rea_20261016/run392_chat_system_message/c2s_review_types.json), [fn-485ed0.txt](../../local_server_rea_20261016/run392_chat_system_message/fn-485ed0.txt).

`481549 → IAT10B6C80`는 `PurpleCommunityChatAPI::Instance`, `481552 → IAT10B6C68`은 `IsConnected`, `482280 → IAT10B6C78`은 **`SendMessage(RequestGameRoomKeyInfo, GameMessageInfo, …)`**다. 실제 hint/name 문자열을 [purple-imports.json](../../local_server_rea_20261016/run392_chat_system_message/purple-imports.json)에 보존했다. DLL 내부 네트워크 protocol/opcode·현재 SDK 연결·PURPLE 인증 성공은 관측하지 않았다.

channel1은 공백으로 대상/본문을 나누고 대상별 보류 자료를 만든 뒤 `472DCE..472DDC`에서 `4F2D`를 `27D620`에 넘긴다. vptr `11E1C28`의 원 RTTI는 **`CS_CAN_WHISPER_TO_REQ`**다([type-11e1c28.json](../../local_server_rea_20261016/run392_chat_system_message/type-11e1c28.json)). 이 선검사·후속 ACK와 일반 송신을 합치지 않는다.

문자열은 UI `std::string`의 **8비트 바이트열과 길이**를 복사해 전달한다. 이번에 CP949↔UTF-8 변환이나 SDK transport의 정확 encoding 계약을 닫지 못했다. **UTF-8/CP949를 확정값으로 쓰지 않는다.** 게임 소켓 opcode 부재도 전체 프로그램의 부재가 아니라 위 정상 UI 경로의 결과다.

추가 선정에서 UI 입력 객체의 `+340` interface vslot10은 **`C56A20`**으로 결속됐다. getter는 `interface+4F0`, 즉 native 객체+830의 std::string을 반환한다. `C015B0 → C1CC60 → C1DDE0 → 3D1DD0` 길이 검사/decoder는 UTF-8의 leading-byte mask·continuation `C0/80`·shift6/12/18을 실제로 소비한다. 따라서 **UI의 기대 문자열 형식 UTF-8은 inferred/static**이다. 이름만으로 판정하지 않았다. 현재 IME writer·입력 바이트 표본·활성 vptr와 SDK 내부 wire encoding은 여전히 UNKNOWN이다. [c2s_review_encoding_selected.json](../../local_server_rea_20261016/run392_chat_system_message/c2s_review_encoding_selected.json), 보조 요약의 최종 encoding 단락.

## `4E52` 일반 채팅 수신

원 등록 `293570`의 **`294C21` factory `11A9778`, `294C28 EDX=4E52`, `294C40 → 292F80`**이다. factory+10의 실제 publisher `306030 → 31DE00 → 2C4E80`는 `SC_CHAT_ACK` vptr `11E77F8`의 protobuf message를 parse하고 event `17FC580`에 게시한다. `46D4B8`의 callback **`469CE0`**가 이 event를 구독한다. 관련 `fn-*`, `refs-*`, `rtti-16812a0.json` 및 selected group `receive_opcode_registry/chat_publish_and_parse/chat_subscriptions`를 재사용한다. 숫자는 원 registrar key이며 독립 TCP frame/header 전체를 이번에 새로 복원한 것은 아니다.

schema **`15F73E0`**, 원 descriptor 21개(번호 1/6 없음). [schema-15f73e0.json](../../local_server_rea_20261016/run392_chat_system_message/schema-15f73e0.json)의 `/fields`와 `/compiled_tags`가 전체 형식이다. 선택한 표시 계약은 다음과 같다.

| field | raw offset / wire | 확인된 소비 |
|---|---|---|
| **f2 필수** | 40 / enum varint(tag10) | `ChatMessage.type` → `ChatData+0` → HUD 색상 선택 |
| **f3 필수** | 18 / length-delimited(tag1A) | 본문 → `ChatMessage+8` → `ChatData+8` |
| **f5 필수** | 48 / enum varint(tag28) | required이나 이 선택 callback의 type/색상으로 사용하지 않음. 정상 서버 값·의미 UNKNOWN |
| f8 | 20 / length-delimited(tag42) | f17이 빈 경우 sender 이름 fallback |
| f16 | 68 / uint32 varint | `ChatMessage+68` actor 식별 값으로 sign-extend 저장 |
| f17 | 28 / length-delimited | sender 이름 우선값 |
| f23 | 66 / bool varint | true면 본문·fallback 이름의 `339AB0` 원 문자열 치환을 건너뛰고 그대로 복사 |

**required 판정**은 enum이라는 사실이 아니라 **`7359E0..7359EA`의 presence mask `A1`**와 schema presence bit 연결이다. bits0/5/7은 각각 f3/f2/f5다. optional의 0/빈 문자열 기본값과 서버가 발급하는 정상값을 구분한다. f5의 validator metadata는 aux `116B2C8`에 있으나 이번에 전체 유효값·의미를 확정하지 않았다. 완성 payload 예제를 만들지 않았다.

`469CE0`의 stack frame은 `RBP=RSP+100`, 복사 raw message 시작은 `RSP+60`이다. `469D40`은 **f16**, `469D47`은 **f2**, `469D55`는 **f23**이다. offset을 f7/f14로 오독하지 않는다. `469D5B..469DCC` 본문, `469E92..46A024` sender/fallback, `46A270..46A2DD`가 최종 type/body/sender/actor와 `472F20` 큐 입력을 잇는다.

normal update `46F320`의 `46FFF8..470027 → 467480`은 같은 `ChatMessage`의 type/body/sender를 `ChatData`로 복사한다. `HudChatAdapter` vptr `121C800`의 UpdateItemWidget **`9AAEB0`**는 현재 row를 가져와 `9AB192..9AB1A3`에서 **그 type을 `473B30` 색상 선택기에 전달**한다. 목록의 저장/필터/원 frame 갱신을 거치는 source 연결이며 현재 HUD 위젯·실제 화면 위치·픽셀 성공을 관측한 것은 아니다.

## `4EEA` 코드형 시스템 메시지와 색상

원 등록은 **`295935` factory `11A8998`, `29593C EDX=4EEA`**다. `2FDA80 → 3195F0`의 typed `SC_MESSAGE_CODE_NOTI` publisher는 event **`1800B40`**를 게시하고 `46D4E4..46D4F5`는 **`46A700`**을 구독한다. `46A700 → 469950`의 원 message 복사 후 **`469A50 → 46B920`**이다.

schema **`15FB950`**: f1:int32 varint(raw38), f2:repeated length-delimited(raw18), f3:enum varint(raw40), f4:length-delimited(raw30), f5:int32 varint(raw3C). **필수는 f1만**이다(`74D610..74D61B`, presence bit1). [schema-15fb950.json](../../local_server_rea_20261016/run392_chat_system_message/schema-15fb950.json).

채팅 목록 경로는 **f1 번호를 `338FF0` 현지화 조회**, f2 각 인자를 `339AB0` 치환, `B4A3F0` format에 넣는다. **f4를 자유 본문으로 채택하지 않는다.** 내부 채팅 type은 `48E0E0`의 메시지 분류 조회 결과다. 분류가 없을 때 **`48E8BA EBX=24 → 48E917 EAX=EBX`**, 그 값이 `46BA43`의 `ChatMessage.type`으로 들어간다. 24는 이 코드형 경로의 실제 fallback이며 모든 시스템 메시지의 정상 type 또는 원 서버 `4E52.f2=24` 발급 증명은 아니다.

별도 `HudMessageLayout`도 같은 4EEA event를 받는다(`9C436A`, callback `9C5240 → 9C6250`). 이쪽은 f3 presence가 없거나 f3=2면 건너뛰고, f3=3과 다른 값의 동작을 나눈다. **이 f3 표시 분기와 채팅 목록의 internal type/색상은 별개**다. 원 f3 enum 유효값·전체 의미와 screen pixel은 미확정이다.

`473B30`은 enum에 따라 **literal backslash + `f` + 한 문자**를 생산한다. 실제 form-feed byte0C가 아니다. [chat-color-controls.json](../../local_server_rea_20261016/run392_chat_system_message/chat-color-controls.json)과 원 switch/table `473B5F..473D15`, `473D44`를 보존했다.

| wire/producer → 내부 type | 원 색상 제어문자 |
|---|---|
| `4E52.f2=0` 일반 / 2(SHOUT) | `\f>` |
| `4E52.f2=1` 귓속말 | 선택 469CE0 경로의 추가 bool=false이므로 backslash·f·파이프 문자. 공통 선택기의 bool=true 경로는 `\f<` |
| type3 | `\f\` |
| type4 | `\f;` |
| type11 | `\fe` |
| type12 | `\fR` |
| type13 | `\f_` |
| type14 | `\fM` |
| **4EEA 분류 fallback24** 및 type5–10/16/18/19/23 | `\fH` |

이 표는 **원 제어문자 구분의 확인**이다. 추가 bool은 `ChatMessage+70 → ChatData+A0`이며 469CE0의 `46A269`가 false로 초기화한다. **f23과 다른 값**이다. `H=노랑`, `>=흰색` 같은 RGB/색 이름을 추측하지 않는다. 채팅 색상 제어문자→최종 palette/RGB와 현재 theme는 이번에 확정하지 않았다. `4E52.f5`나 `4EEA.f3`를 이 type 표에 그대로 대입하지 않는다.

## 다른 메시지 opcode의 경계

`00CE`는 `293709/293710`의 원 factory 등록과 **`SC_MESSAGE_NOTI`** RTTI/schema **`15FBA50`**가 확인됐다. f1:enum 필수(raw44, `74D120` bit4), f2:int32(raw38), f3:length-delimited(raw30), f4:repeated length-delimited(raw18), f5:int32(raw3C), f6:uint32(raw40)다. event `17F5500`의 direct concrete subscriber는 선정 RIP 참조에서 찾지 못했다. 간접 subscriber까지 전역 부재라고 주장하지 않는다. **CE+f3만으로 하단 자유 메시지가 뜬다고 확정하지 않는다.**

`00C8`은 `293655/29365C` 등록 → `313F00 → 3255A0` → event **`17F5140`** → **`9C4F40`**다. 원 RTTI는 **`SC_NOTIFICATION_MESSAGE_NOTI`**, schema **`15F9318`**다. required mask `721B40`의 `0F`로 **f1/f2/f3/f4 필수**, f2 raw28=본문, f3 raw30=3바이트 색상, f4 raw3C=`sint32` varint(ZigZag) 시간이다. f1(raw38)도 sint32이며 선택한 callback의 동작 의미는 미확정이다. `DECC8C..DECC9D`의 shift1/xor 원 fast decoder를 보존했다.

`9C4F40`은 wrapper+30의 본문을 치환한 뒤, wrapper+44의 시간을 float로 바꿔 **1000으로 나누며**(상수 RVA126EDD8 F32=1000), wrapper+38 색상 문자열의 첫3바이트를 소비한다. **이 큐는 Layout+B8, `Root.MiddleMessageArea`**다. `9C41E6(index1)`/`9C4273(index0)`과 `9C46D0 index*88`의 결속에서 index1=Middle, index0=Top이며, `9C4950 → 9649E0/BB95D0`과 Text virtual438이 문자열·색상을 소비한다. [hud-message-widget-keys.json](../../local_server_rea_20261016/run392_chat_system_message/hud-message-widget-keys.json), [selected-data.json](../../local_server_rea_20261016/run392_chat_system_message/selected-data.json), `selected.txt`의 notification groups. 실제 RGB 채널 순서·현재 pixels까지 증명한 것은 아니다. **C8을 하단 GM 응답으로 채택하지 않는다.**

length-delimited 필드는 native std::string으로 보관되지만 protobuf string/bytes의 의미나 전체 문자열 encoding을 형식만으로 확정하지 않는다. 특히 C8 색상3바이트를 한국어 UTF-8 본문 근거로 사용하지 않는다.

## L1J 의미 대응과 남은 최소 관측

| L1J 참고 코드 | 이번 클래식 대응 |
|---|---|
| `C_Chat.java:54/55` readC(type)/readS(text), type0 `.` → GMCommands(73–76) | **역할 참고만.** 클래식 UI normal0은 위 Purple 경로이며 같은 C2S body/opcode/문자 인코딩을 이식할 근거가 없음 |
| `S_SystemMessage.java:37` 자유문자 SYSMSG+09+writeS, nameid overload52/write54는 NPCSHOUT+2+writeD(0)+writeS | 하단 자유문자 역할은 필요하지만 같은 클래식 wire 미확정. 4E52 type24/raw본문은 탐색 후보이며 완성 대체로 확정하지 않음. C8 Middle은 별도 표시 |
| `S_ServerMessage.java:64` buildPacket, opcode67/writeH(ID)68/인자수/각writeS | 클래식 **4EEA f1 ID + repeated f2 인자**와 의미 대응. opcode 크기·필드 배치·현지화 ID 일치·인코딩은 전용하지 않음 |

원 참고 경로는 `D:/SingleLineageRef/l1j-en-classic/src/l1j/server/server/` 아래 `clientpackets/C_Chat.java`, `serverpackets/S_SystemMessage.java`, `serverpackets/S_ServerMessage.java`다. 출처 있는 backend 참고 정책이며 원본 클래식 규칙이 아니다.

**첫 미확정:** (1) PURPLE 없이 원 일반 입력을 로컬 서버에 전달하는 계약, (2) 아래 4EEA ID12066 대안의 실제 resource 조회/한국어 수신·하단 표시. 4E52 대안을 택하면 f5 정상값·system type도 별도로 필요하다. 이를 추측 opcode·정상 enum·가짜 성공으로 채우지 않았다.

다음 화면 실험은 **이번에는 실행하지 않았다**. 같은 고정 Source·정상 로그인/월드·시험 저장에서 사용자가 일반 채팅 ASCII/한국어 각1건을 입력하고 UI channel0/문자 바이트·Purple 호출·게임 socket 수신을 함께 기록한다. 정상 서버의 자유 시스템 메시지1건과 코드형1건을 수신해 4E52의 f2/f3/f5/f16/f17/f23, 4EEA의 f1/f2/f3, 실제 채팅 목록/다른 알림 위치를 결속한다. 공식 발급을 얻지 못한 로컬 화면 탐색은 **4E52.f2=24, f23=true를 확인된 분기에서 고른 탐색값**으로만 기록하며, **f5는 정상 수신에서 확보한 값을 재사용한 뒤** 수행한다. 임의 f5=0·ready 강제·callback 직접 호출로 완성 표시를 만들지 않는다. 원 제어문자별 실제 색·하단 표시·종료/수명은 이 직접 화면 관측으로 남겨야 한다.

## 추가 선정 — 기존 GM 문자열의 1인자 표시 후보

마감 시 기존 자원에서 바로 찾은 별도 대안이다. [기존 string.csv](../../all_table_semantics/inputs/data/string.csv):**12012**의 **ID12066 / TYPE=`SYSTEM_GM` / KR=`{}` / TW=`{}`**가 있다. [string_type.jsonc](../../all_table_semantics/inputs/data/string_type.jsonc)의 `/_essentialSystemSet`에 `SYSTEM_GM`이 들어 있다. 같은 `{}`인 ID11686은 `UI_summon`이므로 채택하지 않았다.

기성 `StringTypeDataTable` reader의 `48DB26..48DB3D`는 `_essentialSystemSet`을 읽어 stack30 set을 만들고 `48DCE5..48DD29`는 그 set을 같은 table+118에 옮긴다. 앞서 확인한 `48E235..48E2F9`는 이 set의 문자열 TYPE을 찾아 **내부 type7**을 반환한다. 따라서 **해당 자원이 정상 로드된 조건**에서 4EEA ID12066은 원 essential-system 분류·type7·`\fH` 채팅 목록으로 이어지는 source 후보다. 기성 reader의 정확 JSON pointer를 [passthrough-candidate.json](../../local_server_rea_20261016/run392_chat_system_message/passthrough-candidate.json)에 모았다.

`B4A3F0`은 인자 벡터의 길이를32로 나눠 개수를 고르고, 1개인 branch **`B4A43D..B4A446 → 18E300`**은 format pointer/length와 한 string argument view(typeD)를 **`EED5F0`**에 전달한다. 따라서 `{}`+인자1개가 그 인자를 출력한다는 것은 이 원 formatter 계약에 따른 **정적 추론**이며 이번에 formatter/게임을 실행한 결과는 아니다. 원 4EEA 필수는 f1뿐이므로 **f1=12066, 반복 f2에 본문1개**가 가장 작은 source 지원 대안이다. ASCII `OK`의 **protobuf body 탐색 예**는 `08 A2 5E 12 02 4F 4B`다. opcode/frame/encryption은 포함하지 않았고 송신하지 않았다.

자원 계보도 구분한다. 기존 `all_table_semantics/index.json#/records/28`은 string.csv 637,926B, inherited SHA256 `aab0a19b92d349724672695ebd9ea8aba00df3559bbbaa3f76ace198172f50af`, `current_authenticated_cache`, **`catalog_comparison:"changed"`**다. 한정 lookup한 [current/catalog.tsv](../../asset_data_analysis/current/catalog.tsv):139는 **current=637926B/aab0…50af, old=623447B/1f40…74cb**다. 따라서 `changed`는 **이전판 대비 변경**이며 current와 이 input의 불일치를 뜻하지 않는다. 기성 actual metadata는 current pin과 일치한다. `/records/29` string_type.jsonc는 `identical`이다. 새 파일 해시·현재 loaded 자원 대조는 하지 않았다. **restored CONTROL 실행 시 같은 자원 로드/실제 ID12066 조회·표시는 미확정**이며 catalog 일치만으로 runtime 성공을 주장하지 않는다.

원 인자는 format 전에 **339AB0의 `$` 숫자 토큰 치환**을 거친다. 임의 문자열의 byte-exact passthrough·색 제어문자 무해화까지 확보한 helper는 아니다. 한국어는 위 UI UTF-8 기대 근거와 별도로 실제 수신/표시를 확인해야 한다. **4E52의 미확정 f5를 피할 수 있는 코드형 대안**이며 C2S PURPLE 의존을 해결하지 않는다. 다음 최소 로컬 화면 실험은 정상 월드의 같은 Source/시험 저장에서 이 ASCII `OK` 후보1건을 실제 decoder/router로 전달해 원 resource ID12066 조회·essential type7·원 목록 추가·표시를 함께 관측하는 것이다. 그 전에는 SOURCE_ONLY로 유지한다.
