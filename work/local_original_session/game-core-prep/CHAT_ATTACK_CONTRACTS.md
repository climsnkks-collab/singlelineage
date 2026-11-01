# 채팅·연속 공격·원거리 공격·방향 계약

2026-10-28 · **정적 조사 / SOURCE_ONLY**. 게임·서버 실행, live attach, 캡처, 패킷 송수신, 제품 코드 수정, 커밋 없음. 요청 지도와 기존 REA 원문을 먼저 재사용했다. 이 문서의 확인은 정적 원문·연결 확인이며 실제 입력·화면·공식 서버 동작 PASS가 아니다.

## 1. 기준과 판정

- 기준 버전 `26.09.29.2001`, inherited CONTROL SHA256 `9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`.
- 분석 carrier: `work/rea_lineage_resume_20261013/main-gameplay/audit/metadata-v2/DERIVED_RESTORED_ANALYSIS_ONLY.exe`, inherited SHA256 `c822838351d774a2022af434829a36dbd9bee030bf22182b834ca4e8659701a9`. 주소는 전부 RVA, preferred base `0x140000000`.
- 신원 근거: [TARGET_IDENTITY](../../local_server_rea_20261016/TARGET_IDENTITY.md), [요청 지도 JSON](REQUEST_COVERAGE_MAP.json)의 `identity`, `rows[message=…]`. carrier는 실행용 원본이 아니며 현재 disk `LC.guard.exe`와의 동등성은 미확인이다. 새 전수 해시 검사는 하지 않았다.
- **확인**: schema/직접 sender/수신 등록/consumer의 실제 정적 명령. **추정**: 이름·조건·자료를 해석한 업무 의미/로컬 구현안. **미확인**: 현재 UI 발신·공식 응답 의무·시간·실표시 등 근거가 닫히지 않은 부분. 필드명 `fN`은 번호이며 원래 `.proto` 필드명은 복원하지 않았다.
- 출처: 원본 파생 분석·기존 REA·현 로컬 서버 코드 100%, 신규 공식 API/웹/L1J 조회 0%. 기존 L1J 비교는 배경 참고에 한정하며 opcode·값·공식 규칙의 근거로 전용하지 않는다. 이 비율은 계약 완성률이 아니다.

| 질문 | 이번 판정 | 구현에 주는 결론 |
|---|---|---|
| 일반·외치기 게임 소켓 송신 | 확인된 Mobile UI는 PURPLE 경로, 게임 C→S opcode/본문 미확인 | 가상의 `CS_CHAT_REQ`나 `4F2D`로 연결하지 않는다 |
| 귓속말 | `4F2D` 대상 선검사, `4F2E` 수신 등록 확인; 본문 전달 완료 계약 미확인 | 선검사와 본문 전달을 구분한다 |
| 채팅·시스템 표시 | `4E52`와 `4EEA`의 채팅 목록 소비 확인 | `4E52` 필수 f5 정상값 공백; `4EEA/12066`은 자원 조건부 후보 |
| 연속 공격 | f1=대상 UID low32/취소0; ACK false는 유지 대상 해제 | 상태 계약 확인. 매 요청 ACK 의무·정확한 UI/주기는 미확인 |
| 원거리 공격 | 현재 bow base40은 `4EE1`, 그 외 통과 분기는 `4E30` | 활 sender 분기 확인. 실제 발신·전용 응답 의무는 미확인 |
| 방향 | `4E2F→4E2E` 타입·필드·actor 소비 확인 | 현재 구현을 재사용한다. 원서버의 매 요청 echo 의무는 미확인 |

## 2. 채팅과 GM 최소 계약

### 2.1 C→S: 일반·외치기·귓속말

주 근거: [CHAT_EVIDENCE](CHAT_EVIDENCE.md), [run392 송신 검토](../../local_server_rea_20261016/run392_chat_system_message/c2s_review_summary.md), 같은 폴더의 `c2s_review_prefix.json`, `purple-imports.json`, `selected.txt`.

| 입력/역할 | 확인한 경로 | wire 판정 |
|---|---|---|
| 일반 채팅 channel0 | `HudChatLayoutMobileImpl` 기본 `[this+160]=0`; `9AFF20→472380→481510`; channel0 literal `NORMAL`; `482280`의 Purple `SendMessage` | **게임 소켓 opcode/본문 미확인**. SDK 내부 transport도 조사 범위 밖 |
| `!` 외치기 | `473A90` prefix table의 `!→2`, UI에서 prefix 1바이트 제거; channel1 이외는 `472E40→481510` | 확인 Mobile 경로는 PURPLE. 게임 소켓용 외치기 opcode를 별도로 확인하지 못함 |
| `"대상 본문` 귓속말 | prefix `"→1`; `472380`이 대상/본문을 공백으로 분리하고 본문을 대상별 보류 자료에 저장; `472DDC→27D620` | **`4F2D CS_CAN_WHISPER_TO_REQ`**. f1=대상 이름의 length-delimited 바이트열(tag `0A`, native +18). 본문 필드가 아님. 지도 required는 null이므로 필수 선언은 여기서 확정하지 않음 |
| 귓속말 선검사 응답 | 지도 `CS_CAN_WHISPER_TO_REQ.expected_s2c.name_candidates[].opcode_bindings`: `295F00/295F18→292F80`, factory `11A6238`, publisher `2F9F90`, typed RTTI `17011D0` | **`4F2E SC_CAN_WHISPER_TO_ACK` 등록 확인**. 성공 enum·필수 필드·후속 본문 송신은 별도 미확인 |
| 반대 방향 선검사 | 지도 `CS_CAN_WHISPER_FROM_ACK`의 상대 등록 `295F24`, publisher `2F9E20` | `4F2F SC_CAN_WHISPER_FROM_REQ`; 클라이언트 `4F30 CS_CAN_WHISPER_FROM_ACK`는 f1 length-delimited, f2 bool. 채팅 본문 요청으로 사용하지 않음 |

기존 CHAT_EVIDENCE의 `4F2E opcode 미확정` 범위는 더 최근 요청 지도의 직접 등록 결속으로 좁혀졌다. 이름 대응만으로 응답 의무·성공값·본문 전달을 확인한 것은 아니다. 확인 Mobile UI 외에 PC UI/다른 socket sender가 전혀 없다는 부재 증명도 아니다.

UI getter `C56A20`와 `C015B0→C1CC60→C1DDE0→3D1DD0`의 UTF-8 decoder는 **UI 기대 형식 UTF-8이라는 정적 추론**을 지원한다. 실제 IME 바이트·활성 UI·SDK wire·한국어 수신 인코딩은 미확인이다. protobuf length-delimited라는 사실만으로 UTF-8 또는 CP949를 확정하지 않는다.

### 2.2 S→C: 채팅 표시 `4E52 SC_CHAT_ACK`

등록 `294C28 EDX=4E52`, factory `11A9778` → publisher `306030→31DE00→2C4E80` → event `17FC580` → subscriber `469CE0` → `ChatMessage/ChatData→HudChatAdapter(9AAEB0)`. 근거: run392 [schema-15f73e0.json](../../local_server_rea_20261016/run392_chat_system_message/schema-15f73e0.json), [선택 원문](../../local_server_rea_20261016/run392_chat_system_message/selected.txt), CHAT_EVIDENCE의 `4E52` 절.

| 필드 | wire/type·필수성 | 확인한 소비 |
|---|---|---|
| f2 | 0 / enum, **필수** | 채팅 type. 0 일반/1 귓속말/2 SHOUT의 표시 분기 |
| f3 | 2 / 문자열 바이트열, **필수** | 본문 |
| f5 | 0 / enum, **필수** | required mask `A1`에 포함. 정상 서버 값·업무 의미 **미확인** |
| f8 | 2 / 문자열 바이트열, optional | f17이 비어 있을 때 sender fallback |
| f16 | 0 / uint32, optional | actor 식별 값으로 sign-extend하여 보관 |
| f17 | 2 / 문자열 바이트열, optional | sender 우선값 |
| f23 | 0 / bool, optional | true이면 본문·fallback 이름의 `339AB0` 치환을 생략 |

전체 21개 descriptor는 위 schema 파일을 따른다(번호 1/6 없음). 최소 표시 필드는 f2/f3만이 아니며 **f5를 임의 0으로 채운 완성 패킷은 공급하지 않는다**. 색상 선택 `473B30`은 type을 literal backslash+`f`+문자 제어열로 변환한다. 내부 type24 fallback을 `4E52`의 공식 시스템 발급값으로 확정하지 않는다. SC 이름의 ACK가 특정 게임 C→S 본문 요청의 존재를 증명하지도 않는다.

### 2.3 S→C: 시스템 알림 `4EEA SC_MESSAGE_CODE_NOTI`

`29593C EDX=4EEA`, factory `11A8998` → publisher `2FDA80→3195F0` → event `1800B40` → `46A700→469950→469A50→46B920`. 근거: run392 [schema-15fb950.json](../../local_server_rea_20261016/run392_chat_system_message/schema-15fb950.json), CHAT_EVIDENCE의 `4EEA`·추가 선정 절.

| 필드 | wire/type·필수성 | 의미/경계 |
|---|---|---|
| f1 | 0 / int32, **필수** | `338FF0` 현지화 문자열 ID |
| f2 | 2 / repeated 문자열 바이트열 | 각 인자를 `339AB0` 치환 후 format에 전달 |
| f3 | 0 / enum, optional | 별도 HudMessageLayout 표시 분기. 채팅색 type이 아님 |
| f4 | 2 / 문자열 바이트열, optional | 이 채팅 목록 consumer의 자유 본문으로 사용되지 않음 |
| f5 | 0 / int32, optional | 이 최소 후보에서 생략; 전체 업무 의미 미확인 |

**GM 응답의 최소 source 후보:** f1=`12066`, f2=본문 하나. 기존 [string.csv](../../all_table_semantics/inputs/data/string.csv):12012의 ID12066은 `TYPE=SYSTEM_GM`, KR/TW=`{}`. `_essentialSystemSet` reader `48DB26..48DD29`와 분류 `48E235..48E2F9`는 해당 자원이 로드됐을 때 내부 type7로 연결한다. formatter의 인자1 branch `B4A43D..B4A446→18E300→EED5F0`를 근거로 `{}`가 본문을 출력한다는 것은 **정적 추론**이다. 기성 current catalog와 추출 자원 metadata는 일치하지만 실제 로드·한국어·하단 화면은 미확인이다.

ASCII `OK`의 **protobuf body만**인 후보: `08 A2 5E 12 02 4F 4B`. 송신하지 않았다. f2는 format 전 `$숫자` 치환을 거치므로 임의 문자열 byte-exact passthrough·제어문자 무해화 계약은 아니다. 기존 framing `<u16 total_length><u16 opcode><body><2-byte tail>`은 기존 transport에 맡기며 이 예를 완성 암호화 frame으로 사용하지 않는다.

다른 알림을 혼동하지 않는다. `00C8 SC_NOTIFICATION_MESSAGE_NOTI`는 필수 f1/f2/f3/f4, f1/f4 sint32(ZigZag), f2 본문, f3 3바이트 색상, f4 시간(ms→/1000)이며 `Root.MiddleMessageArea` 소비다. 하단 채팅 대체가 아니다. `00CE SC_MESSAGE_NOTI`는 등록/schema까지만 확인했고 직접 표시 subscriber는 미확인이다. 상세는 CHAT_EVIDENCE를 따른다.

### 2.4 `world_gm.py`에 필요한 연결

현재 [world_gm.py](../../../tools/local_original_session/world_gm.py)의 `prepare_chat/handle_chat`는 해석·제안·명시적 service commit만 수행하며 socket/송신을 소유하지 않는다. `handle_chat(ctx,text,now,services=...)`를 기존 `WorldRuntime.dispatch_now`/월드 operation lock 안에서 호출한다.

1. **입력 계약부터 분리한다.** 실제 본문을 생산하는 opcode/decoder 또는 별도로 선정한 로컬 input/bridge가 필요하다. `4F2D` 대상 문자열을 `.item` 본문으로 디코딩하지 않는다. normal0 PURPLE 경로를 이 문서만으로 로컬 socket에 연결할 수 없다.
2. 시작 때 decoder·system encoder·기존 owner adapter를 준비한다. 요청 중 파일/소스 탐색·핀·해시·중복 검사 체계를 추가하지 않는다.
3. `GMServices.snapshot/commit`을 명시 공급한다. `.item`은 기존 item owner가 UID·stack·중량·소유·저장/CAS와 완료 frame을 소유한다. 서비스 미연결이면 변경 명령은 `GM_BINDING_REQUIRED`; 단순 proposed 결과를 적용 성공으로 표시하지 않는다.
4. handled 결과의 `frames`를 기존 `ctx.send_frame`으로 각 1회, 그 뒤 `message`를 시스템 encoder로 1회 보낸다. service의 commit frames에 시스템 텍스트를 중복 포함하지 않는다. unhandled 일반 채팅은 일반 경로로 넘긴다. partial/unknown 예외는 기존 마감 경로로 전달한다.
5. 응답 후보는 위 `4EEA/12066`이며 아직 표시 검증 전이다. 미래 선택 feature는 [WORLD_FEATURE_GUIDE](WORLD_FEATURE_GUIDE.md)를 따르고 등록을 빼도 코어·다른 기능이 동작해야 한다. 다른 feature의 ctx 메서드 직접 호출·필수 코어 의존·중복 METHODS override를 만들지 않는다.

## 3. 연속 공격 `4E42` / `4F32`

지도 `rows[message=CS_ATTACK_CONTINUE_REQ]`의 sender 결속과 기존 restored section reader [run380/f2_research.py](../../local_server_rea_20261016/run380_map_transition_receive/f2_research.py)의 `View.read/function`을 재사용해 생산자·consumer를 추가 정적 판독했다. 새 REA native 세션·Evidence ID는 만들지 않았다.

### 3.1 요청 필드와 대상 유지·해제

**`4E42 CS_ATTACK_CONTINUE_REQ`는 f1 하나, required uint32/wire0/tag08**다. 원 message vptr `11E3218`, parser `761920`, schema `15EF0D8`, Init `761A80` mask1; 지도 schema의 raw offset18/typecard891을 실제 required 검사와 함께 판독했다. `3CB30` sender는 `3CCA8`에서 이 vptr를 설치하고 presence1을 설정한다. `3CCB3..3CCBA`는 입력 target의 `-1`을 0으로 바꾸고 low32를 f1에 저장, `3CCF4→27D620`에 opcode4E42를 전달한다. 다른 sender `54710→548D0`은 명시 f1=0을 만든다.

`AIControllerComponent::AttackCommand`의 RTTI TD `166B360`, vtable `11806E0`에 연결된 다음 경로가 대상 유지의 근거다. 같은 이름의 `ActorControllerComponent::AttackCommand`(일반 `4E30/4EE1` 경로)와 구분한다.

| 원 경로 | 확인한 상태와 동작 | 해석/한계 |
|---|---|---|
| vslot18=`74800` | 현재 target Actor 존재, command+24==0, AI+4C<=0 조건에서 targetUID를 `3CB30`에 전달. subsystem의 key3 target에 저장하고 AI+4C에 float0.3 설정 | 대상 유지/연속 공격 명령의 송신 경로 확인. 0.3은 native 상태값이며 서버의 공식 공격간격이나 실측 발신주기가 아님 |
| vslot20=`749E0` | 기존 key3 target이 -1이 아니면 `3CB30(-1)` 호출 후 key3=-1 | wire f1=0은 이 경로의 취소/해제 표현. 피해0이나 대상UID0의 정상 공격으로 해석하지 않음 |
| helper `54710` | key3의 유지 대상 검사 뒤 own bow predicate111B20=true이면 false 반환. false이고 own Actor 존재·99FD0=false일 때 f1=0 송신(`54878..548D0`) | 조건부 취소 helper라는 해석. `4C440` 공격 알림 handler의 내부flag+8 조건(`4C531..4C542`) 및 자세 변경 handler `4FC20→4FD57`에서 호출. 모든 상위 UI/수명 조건은 미복원 |

따라서 **uint64 공격 대상 UID를 담는 `4E30.f1`과 이 uint32 필드를 동일 선언으로 취급하지 않는다**. low32가 실제 서버의 어떤 UID 공간을 뜻하는지·높은 비트 UID의 모호성 처리까지 원서버 계약을 확정하지 않았다. 임의 새 UID/대상으로 재구성하지 않는다.

정확히 어느 클릭/자동공격 토글이 이 AI command를 생성하는지, 누르고 있기/더블클릭/대상 변경 때의 전체 순서와 반복주기는 **미확인**이다. 확인한 것은 명령 내부에서 대상 유지·해제 요청을 생산하는 조건부 경로다.

### 3.2 응답 `4F32 SC_ATTACK_CONTINUE_ACK`

**opcode·타입·필드와 consumer 확인**이며 더 이상 이름만의 ACK 후보에 머물지는 않는다. 다만 요청마다 응답해야 한다는 인과·의무는 미확인이다.

- 지도 수신 등록: `295F6C EDX=4F32`, factory `11A6418`, publisher `2F9B40` → event `1802C40`. `5FC4C R8=4D9D0`/`5FC56`이 이 event의 구독을 연결한다.
- native message vptr `11E4120`, TD `16832F8`, parser `776940`, schema `15F3228`, serializer `776950`. **f1 required bool**, native offset18, wire0/tag08. Init `776A70`은 presence bit0을 검사한다. ctor `776920`의 기본 false는 서버의 정상 응답값을 뜻하지 않는다.
- subscriber `4D9D0`의 `4DA82..4DAC4`: **f1=false이면** ActorSubsystem+918 map의 key3 target을 -1로 지우고 조건에 따라 subsystem+1A0에 `679F0(-1)`도 반영한다. true이면 이 해제 분기를 건너뛰어 대상을 유지한다.

본문 형태만 쓰면 `08 00`=false/해제 분기, `08 01`=true/해제 생략이다. 송신하지 않았고 정상 서버 성공값으로 선정하지 않았다. required bool을 생략한 빈 ACK와 명시 false는 같은 유효 계약이 아니다. true를 보내도 공격 시작·명중·피해·반복 타격을 자동으로 수행한다는 근거는 없다.

### 3.3 일반 공격과 서버 구현 경계

`4E30/4EE1`은 targetUID와 좌표를 보내는 타격 sender이고, 확인한 `4E42`는 target 유지/해제 상태 요청이다. AI command 외에도 기존 run24의 **ActorController AttackCommand+4D 분기 `A3FF0→A402D→3CB30→4E42`**가 추가 연결됐다. 일반 분기는 `A38E0→A3970→bow4EE1/그 밖의4E30`이다. `4F32` consumer는 target 상태를 지우거나 유지하며 `4E31` AttackAction 통지를 대체하지 않는다. 두 요청 사이의 전체 런타임 순서와 서버가 자동 타격을 계산하는 책임 분담은 아직 미확인이다.

후속 구현은 현재 session/actor에 결속한 유지 대상·해제 수신을 일반 피해 처리와 분리하고, 기존 공격 owner의 속도·대상 수명·거리·LOS·탄약·kill-once를 유지해야 한다. **`4E42` 수신마다 기존 공격을 1회 실행하거나 새 반복 timer를 켜는 구현은 이번 근거만으로 확정할 수 없다.** 원서버 응답 조건을 더 확인하기 전 임의 `4F32 true`를 성공 ACK로 추가하지 않는다.

## 4. 원거리 공격 `4EE1`과 일반 `4E30`

기존 [run24 일반 공격](../../local_server_rea_20261016/run24_normal_attack/findings.md)의 `A17B0→A38E0→A3970`, 지도 exact stack-slot sender 증명을 재사용했다. 기존 문서에서 UNKNOWN이었던 predicate `111B20`은 이번에 같은 reader로 좁혔다.

### 4.1 활이 어느 요청을 보내는가

**확인한 현재 bow 동작군(base40)은 `4EE1` 분기다.** `111B20`은 CharacterData+6D8 ownUID→`627B0` 자기 Actor 조회→`3ED20` ActionComponent 조회 뒤 **`111BCB cmp [Action+40],0x28`**를 검사한다. [WEAPON_STANCE_EVIDENCE](WEAPON_STANCE_EVIDENCE.md)의 원 SPR/정규화 연결은 base40=bow를 독립 확인한다. 그러므로 이름 FAR만으로 활이라고 추측한 것이 아니다.

`A3970`의 `A39FA call111B20 / A39FF test / A3A01 je A3AB6`에서 true는 `CS_FAR_ATTACK_NOTI` vptr `11E3420`을 설치하여 **`A3A78 EDX=4EE1→27D620`**으로 간다. false는 별도 `111740/99FD0` 등 기존 조건을 통과한 뒤 `CS_ATTACK_NOTI` vptr `11E3280`을 설치하고 **`A3C34 EDX=4E30→27D620`**으로 간다.

따라서 **현재 서버가 `4E30`에 활 계산을 지원하는 사실과 원 bow producer가 `4EE1`을 선택하는 사실은 별개**다. 모든 외형·변신·특수 활·다른 sender의 전수 판정이나 실제 한 발의 발신 관측은 아니다. 상위 own AI/상태 객체+40>0이면 아예 송신하지 않는 기존 gate도 유지된다.

### 4.2 C→S 필드

| 필드 | `4EE1 CS_FAR_ATTACK_NOTI` | 일반 `4E30 CS_ATTACK_NOTI`와의 관계 |
|---|---|---|
| f1 | **required uint64**, wire0/tag08, raw18. target vslot8 UID; 입력 -1 sentinel은 0으로 치환 | 선언·정상 target producer 의미가 같음 |
| f2 | optional int32, wire0/tag10, raw20. target Coordinate+8 qword의 low32=X | 동일한 native 좌표 producer. 방향/타일 단위라고 바꿔 부르지 않음 |
| f3 | optional int32, wire0/tag18, raw24. 같은 qword high32=Y | 동일. ZigZag가 아닌 signed int32 varint |

`4EE1`의 parser `766950`, schema `15EA970`, producer `A3A21..A3A40`은 presence7로 세 필드를 모두 넣으며 **Init `766B50` mask1은 f1만 required**임을 확인한다. 일반 `4E30`의 Init `75E060`도 mask1이다. 좌표는 `A38E0→414A0(target)`에서 나온 현재 Coordinate이며 임의 raw 타일 좌표 대입을 정당화하지 않는다.

### 4.3 S→C 응답과 기존 투사체 표시

`4EE1`에 대응하는 전용 SC opcode/매 요청 필수 응답/응답 순서는 **미확인**이다. 같은 필드 구조라는 이유만으로 `4E30→4E31`의 요청 인과를 자동 이전하지 않는다.

별도로 **`4E31 SC_ATTACK_NOTI`가 원거리 AttackAction과 투사체를 표시할 수 있다는 consumer 계약**은 확인됐다. 근거: run24, [RANGED_ATTACK_EVIDENCE](RANGED_ATTACK_EVIDENCE.md), [run384](../../local_server_rea_20261016/run384_ranged_attack_display/findings.md), [run386](../../local_server_rea_20261016/run386_arrow_projectile_gfx/findings.md) 및 [f6/f14 계약](../../local_server_rea_20261016/run386_arrow_projectile_gfx/field_contract/findings.md).

- f1..5 required = kind(int32), attackerUID(uint64), targetUID(uint64), raw effect(int32), 방향(int32). kind1→AttackAction이며 raw effect를 공식 damage 수식으로 확정하지 않는다.
- own attacker에서 f13 bool=false는 action·projectile postlude를 생략하는 분기가 있다. true는 그 gate를 통과시키는 값이지 전체 admission/표시 성공 보장이 아니다.
- optional **f6/f7 둘의 presence**가 projectile 경로를 연다. f6 int32는 UID 입력, f7 int32는 graphic key. 현 자원 **66**은 `#66 arrow`→effect subtype3→native `Arrow` factory로 연결된다. subtype3은 f6를 native 감소 카운터 기반 local UID로 교체한다.
- f14 enum domain1/2, 생략 default1. 일반 Arrow subtype3은 이 값을 읽는 분기를 건너뛴다. f6=0/f14=1은 기존 LOCAL 표시 후보이며 공식 화살 wire 발급값은 미확인이다.
- f9..12의 A/B raw 좌표와 실제 시작/목표 소비는 전체 미완이다. `(tile-32256)*64`는 역상 후보일 뿐 정확 subcell/current 증명이 아니다. `C373 SC_PROJECTILE_DRAW_NOTI`는 등록/schema 후보가 있으나 subscriber/업무 소비 미결속으로 필수 추가하지 않는다.

후속 서버에서는 `4EE1`을 현재 공격 owner에 전달하는 ingress adapter와 S→C 표시를 구분해야 한다. 공통 필드 decoder를 재사용할 여지는 있지만 활 비용·속도·LOS·소유·현재 target을 우회하거나 두 opcode를 중복 피해로 계산해서는 안 된다. 정확한 응답 의무가 닫히기 전 `4E31` 송신을 **원서버와 동일한 4EE1 응답 계약**으로 표시하지 않는다. 활의 실제 발사→비행→도착→피격→정리와 다음 공격은 미관측이다.

## 5. 방향 `4E2F`와 원본 S→C `4E2E`

근거: [ITEM_INFO_EVIDENCE](ITEM_INFO_EVIDENCE.md) 1–2장, 지도 `CS_CHANGE_DIRECTION_NOTI`, 현 `world_feature_iteminfo.py`의 `decode_direction/direction_notice/_iteminfo_direction`.

| 방향 | 확인 계약 |
|---|---|
| C→S `4E2F CS_CHANGE_DIRECTION_NOTI` | schema `15EE458`, f1 **required int32** 방향, wire0/tag08. sender `92850`이 actor 이전 +88과 비교하고 먼저 새 방향을 저장한 뒤 변경됐을 때 `929D5→27D620` 송신 |
| S→C `4E2E SC_CHANGE_DIRECTION_NOTI` | `294A0C/294A24→292F80`, factory `11AB518`→publisher `3075C0→31EA10`, vptr `11E41F0`; schema `15EE4B0`, f1 **required int32 UID**, f2 **required int32 방향**, wire0/tag08/10. Init `75DC00` mask3 |
| 실제 소비 | subscriber `4C150..4C38E`, f1을 sign-extend하여 `4C239→627B0` actor lookup, f2를 `4C2A5`에서 방향 동작 객체로 전달. unknown UID만 보내서는 actor가 생기지 않음 |

**현재 서버 코드 확인:** 이미 현재 선택·생존 PC의 entity heading과 service heading을 갱신하고, 그 UID를 `visibility.known`으로 알고 있는 다른 observer에 기존 outbox/announce로 `4E2E`를 알린다. 자기 echo 생략과 방향0..7 허용은 **현 LOCAL 정책**이다. 클라이언트의 선반영은 확인했지만 공식 서버가 자기 echo를 항상 생략하는지는 미확인이다. SC f1은 uint64가 아니므로 높은 bit의 UID는 signed int32의 sign-extension varint 의미를 보존해야 한다.

이 문서에서 방향 코드를 다시 추가하거나 observer spawn 기능을 확대하지 않았다. 현재 WorldView가 다른 PC를 spawn하지 않는 제한과 실제 다른 actor의 화면 회전·동작 수명은 별도 미확인이다.

## 6. 서버 구현 단계와 남은 확인

이번 산출물은 문서뿐이다. 아래는 후속 구현 순서이며 실행·수정 완료 주장이 아니다.

1. 방향은 기존 구현을 재사용한다. known actor 대상으로 `4E2E` 소비를 확인할 때 원본 callback·실화면을 함께 구분한다.
2. GM은 입력 생산 계약 공백과 응답 표시 공백을 각각 닫는다. 기존 parser/owner 서비스에 연결하되 `.item` 지급·저장 성공을 텍스트 출력만으로 판정하지 않는다.
3. 원거리 ingress는 base40→4EE1의 확인을 반영해 기존 공격 owner에 연결하는 후속 작업으로 좁힐 수 있다. 연속 공격은 대상 유지·해제 상태와 타격 계산을 분리한다. 현재 일반 공격·탄약·속도·LOS·저장 소유 경계를 유지하며, 새 opcode를 기존 공격으로 무조건 치환하거나 ACK를 임의 성공값으로 보내지 않는다.
4. 이번에는 실행하지 않았다. 후속 실제 확인이 허용된 범위에서 정상 로그인→선택→월드, 일반/외치기/귓속말 본문 경로, 연속 공격 시작·유지·해제, 활1발, known remote actor 회전, 시스템 알림1건의 순서와 필드·화면을 같은 Source로 관측한다. 그 전에는 공식 응답 의무·cadence·활 발신·표시 성공을 UNKNOWN으로 유지한다.

### 이번 검증과 재현 위치

- `git status --short --branch`, recent branch 목록: 현재 `main`; 다수 기존 dirty/untracked가 있어 보존했다. 이 작업의 writer는 이 문서 하나다. ACTIVE/요청 지도/제품 코드/핀은 수정하지 않았다.
- `python -B -`의 inline 정적 reader: `importlib.util.spec_from_file_location(...,'work/local_server_rea_20261016/run380_map_transition_receive/f2_research.py')`로 import, `View()` 후 `function(RVA)['instructions']`/`read(RVA,size)`만 호출했다. 모듈의 main/save는 실행하지 않았다. 결과: `111B20` bow40 비교, `A3970` 4EE1 producer, `3CB30` -1→0/uint32 저장, `776A70` required bool 검사, `4D9D0` false→target 해제 원문 확인. 함수 경계로 decode한 결과를 채택했으며 임의 중간 바이트에서 시작한 부분 decode는 근거로 사용하지 않았다.
- 분석 worker의 추가 원문 판독은 `python -B`로 `tools/local_movement_contract/source.py`를 import하고 `peer,v=m.view()` 후 `v.read`, `v.md.disasm`, `v.owner`, `peer.primary_tables(v,TD)`, `peer.lea_xrefs(v,{event_RVA})`만 사용했다. main/재생성은 호출하지 않았다. 그 결과인 schema/Init·AI command slots·A3FF0 연결·54710 caller는 위의 정확 RVA에 보존했다.
- `REQUEST_COVERAGE_MAP.json`을 `json.loads(...encoding='utf-8-sig')`로 읽어 해당 6개 요청의 schema·`opcode_static_proofs`·상대 수신 등록과 대조했다. 결과: `4F2E/4F2F` 기존 미확정 범위를 등록 결속까지 정정, `4E42/4EE1/4E2F` sender 일치.
- 문서 참조 파일 존재·미완 placeholder·정적 판독 값의 교차 점검을 수행했다. 게임·서버·제품 테스트와 네트워크 송수신은 요청 범위대로 0회다. 새 검사기·guard·핀은 만들지 않았다.

**남은 최소 입력:** PURPLE 없는 실제 채팅 본문 producer/decoder, `4E52.f5`의 정상값(해당 응답을 채택할 경우), `4EEA/12066`의 실제 loaded 자원·한국어·하단 표시, 자동공격 UI→AI command 연결과 `4E42/4F32`의 실제 순서/응답 의무, `4EE1` 발신 및 S→C 응답 한 발, known remote actor 방향 소비·수명. 정적 타입/원문 확인과 이 동작 공백은 합산하지 않는다.
