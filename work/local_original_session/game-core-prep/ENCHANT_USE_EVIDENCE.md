# 대상 지정 아이템 사용·강화 결과의 원본 연결

2026-10-26. **인벤토리 대상 클릭을 같은 CS0960의 nested f2:int64로 보내는 원 경로를 새로 확인했다. 별도 강화 결과 메시지는 SC_ENCHANT_RESULT / 0967이다.** 다만 실제 확인 주문서22·강화 주문서25/26의 instance raw 값과 이 경로의 귀속, 성공/실패 enum·문구·`+N` 변경의 동일 작업 인과는 미확정이다. 정적 원문 확인이며 화면·입력·실송수신 PASS가 아니다.

산출물은 [run393 선정 원문](../../local_server_rea_20261016/run393_item_target_use/selected-source.txt), [색인·필드표](../../local_server_rea_20261016/run393_item_target_use/source-index.json), 같은 폴더의 `body-*.json/bin`·RTTI·xref 기록이다. 제품 코드·게임·서버·포트·live attach·입력·REA 공용 session은 변경·실행하지 않았다.

## 1. 대상과 근거 경계

[기존 신원 경계](../../local_server_rea_20261016/TARGET_IDENTITY.md)를 승계한다. CONTROL SHA256은 `9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`, 파생 carrier는 `c822838351d774a2022af434829a36dbd9bee030bf22182b834ca4e8659701a9`다. 새 code는 기존 REA104 `wire_schema/exec-buffer.bin`, RTTI·data·PData는 보존 carrier에서 읽었다. 기존 run262의 같은 frozen CODE/원문 대응 근거를 재사용했고 전파일 hash·원본 전체 검증은 반복하지 않았다. 현재 디스크 LC.guard·실행 메모리와의 동등성을 주장하지 않는다.

이 문서 주소는 **RVA**다. preferred VA는 `0x140000000 + RVA`다. 예를 들어 sender `52A820`은 preferred VA `0x14052A820`, callback `4FD080`은 `0x1404FD080`이다. 원 실행시 ASLR·protection·현재 owner·scene·lease는 미관측이다.

재사용: run37 기본 sender/schema, run39 PC Use·switch 원문, run41/73 UPDATE, run63 원 클릭 처리, run262 이름/설명 소비, run292/293/297/301의 이전 frontier와 원문, 기존 Inventory discovery의 REMOVE. `world_enchant.py:1`은 명시 LOCAL L1J 확률/계산 정책이며 원본 wire 근거로 쓰지 않았다. HANDOFF의 BOOK/장비 정책·예전 실행 PASS도 강화의 실행 근거로 전용하지 않았다.

## 2. 새로 연결한 대상 선택과 요청

### 두 message의 f5를 구별한다

**ItemInfo.f5**는 optional int32/bit8, DTO+90 → Entity+50이다(`4F77BF..4F77CE`, run41). **원 Use는 이 Entity+50을 `4FD347`에서 읽어 interaction 선택·switch에 실제 사용한다.** 아이콘이라는 기존 업무 표기가 있더라도 이 직접 소비를 없애지는 않는다. 여기서는 raw 값으로만 부른다. **CommonItemInfo catalog.f5**의 UI reference와 다른 message/도메인이다. catalog22의 f5=475 또는 f4=7을 actual ItemInfo.f5=7로 복사할 근거는 없다.

### 조건부 정상 경로

| 단계 | 원문 연결 | 판정 |
|---|---|---|
| 원 interaction 등록 | `4FBDF0`: Inventory+468 map의 raw key **7** 및 **132(84h)**에 vptr11C6AC0 `TargetInteraction` pair 설치 | 새 정적 확정. 선정 원문 A, L7 |
| 처음 사용 | run39의 `4FD260`은 실제 UID lookup → Entity+50 key → map pair를 current context+4B0/+4B8로 보유하고, +4A8=사용UID, +4C0=1을 설치한다 | 기존 원문 재사용. 선정 B, L39 |
| raw7 첫 branch | key7→selector3→`4FDA51`; `16F520(...,8,20h)`, `3DEF0(...,85h)` 후 정상 pair 정리로 간다 | 이 branch에 알려진 0960 sender 호출은 없다. helper의 전체 부작용·85h의 문자열/용도·모든 패킷 부재는 UNKNOWN |
| 대상 item 클릭 | 원 PC first-hit/model UID→`4FD080(I,clickedUID)`. +4C0이 참이고 current interaction이 nonnull이면 **vslot8(RDX=I+4A8 사용UID, R8=clickedUID)** | 원 run63 재사용. 선정 C, L127. 클릭한 UID와 사용UID를 바꾸지 않는다 |
| 실제 callback | TargetInteraction.v8=`529410`: clickedUID64를 보존하고 R9d=0으로 `4FF370(I,사용UID,clickedUID,0)` | 새 정적 확정. 선정 D, L165 |
| 정상 handler | `4FF370`은 I+508 byte guard가 참일 때 사용UID로 실제 row를 재조회한다. row.template+10→`52B260`→handler.vslot10 | guard 업무명/현재값은 UNKNOWN. default 선택 조건상 실제 template22/25/26은 ItemUseHandler11C7B00, slot10=`52A820`이다. 선정 E/F, L182/L240 |
| 요청 생성·전송 접점 | `52A820`이 아래 field를 새 owning child에 만들고 `52ABEF EDX=0960`→`52ABF8 CALL27D620` | 새 정적 확정. **별도 대상 선택 opcode가 아니라 같은0960의 다른 handler 메서드**다. 선정 G, L277 |

위 연결은 **actual raw7/132의 current interaction이 TargetInteraction이고, I+508 guard=true인 조건**이다. **I+508을 실제 사용 시점에 활성화하는 writer는 이번 선정 원문에 없고 UNKNOWN**이다. 따라서 일반 인벤토리 전체 흐름이 완결됐다는 판정이 아니다. raw132는 같은 callback 등록이 있으나 이번에 첫 Use의 switch branch 의미를 별도로 해석하지 않았다. **실제 주문서22/25/26의 ItemInfo.f5 presence/value는 미공급**이므로 주문서 세 종류의 실제 흐름이 이 경로라고 최종 확정하지 않는다. template 번호 비교 통과와 actual raw 귀속은 서로 다른 사실이다.

### 원 대상 요청의 wire

| 위치 | 타입·presence | 이 경로의 값/생산자 |
|---|---|---|
| opcode | `0x0960`, CS_USE_ITEM_REQ | 두 번째 메서드 `52A820`, 기본 메서드52A410과 같은 message |
| outer f1 | **required uint64 / wire0** | RDX=사용 item UID64. `52A882` request+20 qword |
| outer f2 | **required message / wire2** | 실제 새 UseItemReqParam. `52A88A→52A310` |
| outer f2.f1 | optional **int32 / wire0**, bit15 | **present 1**, `52A892` child+70 |
| outer f2.f2 | optional **int64 / wire0**, bit2 | **present clickedUID64**, `52ABB7/52ABBB` child+38. int64 varint이며 ZigZag/sint64가 아니다. u32로 자르는 명령 없음 |
| outer f2.f3 | optional **int32 / wire0**, bit3 | **present 0**. `52942B`의 R9d=0→`4FF401`→`52A84D`→`52A8A3` child+40. 다른 caller의 packed 값과 혼동하지 않는다 |
| outer f2.f15 | optional **int32 / wire0**, bit12 | **present 0**, `52A8A6..52A8B3` |
| outer f2.f16 | optional **int32 / wire0**, bit13 | **present 0**, `52A8B7..52A8C4` |
| 나머지 child | optional | 이 새 child 생성 경로에서는 absent, f18 repeated 목록은 empty. f17 enum·f18 대상 목록을 추가하지 않는다 |

이것은 **UI 사용→대상 클릭→callback→request 구성의 순서**다. sender 내부 store는 f1/f3/15/16을 먼저 쓰고 f2를 나중에 쓰지만, 이를 서버의 업무 처리 순서로 해석하지 않는다. protobuf 필드 순서 자체를 별도 행동 단계로 만들지 않는다. outer required mask3·child optional schema는 run37 재사용이다.

정상 수명: 첫 Use가 current interaction pair를 보유한다. `4FD080`은 original callback 뒤 남은 context를 `504480`으로 정리하고 +4C0을 내린다. `4FF370`도 기존 context가 남았으면 먼저 정리하고, 사용 row/control pair를 handler 호출 동안 보유한 뒤 정상 release한다. handler는 숫자 targetUID를 child에 copy하므로 Slot/model 포인터를 요청에 비동기로 빌려 두지 않는다. `52AC50..52AC60`은 child의6C1E00 및0x78 free를 수행한다. +508은 원 guard대로 검사한 뒤 호출 후0으로 내려간다. 전체 EH·재진입·현재 target 소유/유효성·서버 수락은 정적으로 보장하지 않는다.

## 3. 별도 강화 결과0967과 generic 갱신

### 새로 확인한 SC_ENCHANT_RESULT

`2943D5` callable11AAA98 → `2943DC EDX=0967` → `2943F4 292F80`의 등록을 확인했다. 실제 callable.slot10=`30B500` → wrapper constructor`320BB0` → vptr11A3B98/TD170D9D0 `ProtocolMessageParser<SC_ENCHANT_RESULT>` → wrapper+8 vptr11F3000/TD16821E8 `SC_ENCHANT_RESULT` → `2D3130`의 DEFFF0 parse → **event17F9940 publish**까지 원문으로 연결했다. 선정 H–L, L343–419.

parser getter`7A6E10`은 descriptor`1601E80`에 연결된다. regular metadata10개와 serializer`7A6E20`을 확인했고, `7A7260`의 IsInitialized mask는 **1Fh**, 즉 f1..f5가 required다.

| 0967 필드 | 타입 / wire | presence bit / storage | 확인 수준 |
|---|---|---|---|
| f1 | uint32 / 0 | required bit0 / +18 | UID라는 업무명은 아직 UNKNOWN |
| f2 | int32 / 0 | required bit1 / +1C | 업무명 UNKNOWN |
| f3 | closed enum int32 / 0 | required bit2 / +20 | **success/failure 값 mapping UNKNOWN** |
| f4 | int32 / 0 | required bit3 / +24 | 강화 전/후 레벨인지 UNKNOWN |
| f5 | int32 / 0 | required bit4 / +28 | 업무명 UNKNOWN |
| f6 | int32 / 0 | optional bit5 / +2C | 업무명 UNKNOWN |
| f7 | bool / 0 | optional bit6 / +30 | 소멸/성공 bool이라는 명명 금지 |
| f8/f9/f10 | int32 / 0 | optional bits7/8/9 / +34/+38/+3C | 메시지 ID·수치 의미 UNKNOWN |

**결과 callback·실제 소비는 아직 연결하지 못했다.** event17F9940의 exact PData-bound RIP-relative LEA 참조는 init8AA0/publisher30B500/static destructor10944D0만 나왔다. 이는 computed/indirect/alias/dynamic 등록을 포함한 전체 부재 증명이 아니다. 이 publisher의 generic dispatch를 Inventory·메시지창·사운드·이펙트 소비라고 바꾸지 않는다. 같은0960 작업과의 causal 응답 순서·성공/실패 문구는 UNKNOWN이다.

### 결과 반영에 사용할 수 있는 기존 generic 계약

| 응답 | 확인된 클라이언트 소비 | 강화/확인 전용으로 아직 미확정인 부분 |
|---|---|---|
| **0965 UPDATE** outer f1 repeated ItemInfo | event17F97C0→4F7670. ItemInfo.f1 **required uint32**로 기존 Entity+8 UID lookup. missing row는 skip | 실제 같은 강화/확인 결과로 어떤 필드가 오는지·0967과 순서 |
| 0965 ItemInfo.f4 | optional uint64/bit6 → Entity+28 **새 절대 수량**, 50A6B0. 0을 쓰는 것과 삭제는 다름 | 주문서1개 소비의 원서버 trigger/원자성·저장 |
| 0965 ItemInfo.f18 | optional string/bit0 → Entity+58, f4 setter **뒤**4AC00 복사 | 완성된 이름형 문자열을 바꾸는 generic 접점. `+N`을 어느 scalar에서 자동 합성하는지·원 강화 이름 문법·최종 화면은 UNKNOWN |
| 0965 ItemInfo.f7 | optional int32/bit9 → Entity+20 → 기존 모델 수치 | **강화 level이라는 업무 근거 없음**. +1을 넣으면 `+1` 이름이 된다고 주장하지 않음 |
| **0978 REMOVE** SC_REMOVE_INVENTORY_NOTI | f1 **required uint64/wire0**; 등록2945A9..CD→callable11AA8B8.slot10=30A250→event17FA300→Inventory4F6920. UID 일치 행 whole erase→504DC0 compaction→3E0060 lastPair 정리→vector end−10h | 소진 주문서·실패 target 소멸의 **같은 작업 인과**는 미확정. 다른 owning pair가 있으면 logical 제거 즉시 physical free는 아님 |
| **096E USE_FAILED** | run62의 required f1/f2 signed32 두 필드와 event17F9DC0 publish | 성공/실패 enum·UI 메시지·선택 상태 해제·0960 인과 UNKNOWN |

UPDATE는 found-row가 있으면 Inventory+E0→기성 adapter/Grid/model refresh를 알릴 수 있다(run41/61/73). 값/presence 실제 변경·commit·원 사용 성공·실제 render는 각각 별개다. 일반 request/response builder·현재 제품의 로컬 projection은 이 원문 연결의 근거가 아니다.

`+N` 관련 원문은 run262의 **f18 문자열 pattern `\((\d+)\)` 처리**와 f19 ItemDescription/DescToken `enchantDamage`, `enchantAc` tag 소비까지만 재사용한다. 이것은 instance 강화레벨 reader·확률/파괴·자동 `+N` 이름 합성의 증명이 아니다. 확인 주문서의 identified before/after field와 설명 표시 인과는 run301에서 남은 그대로 UNKNOWN이다.

## 4. 제외한 잘못된 후보와 남은 한계

- **run293/297 f18 목록은 강화 대상 UID 근거로 쓰지 않는다.** 새 exact RTTI에서45B9D0 dynamic-cast target TD168C6A0은 `BookmarkSubsystem`,45B740 target TD1689488은 `BookmarkLayout`이다. writer4596E0은40B 행의 첫 dword를 목록으로 복사하며912FCB caller는 `BookmarkCrystalLayout::Initialize` lambda다. 이로써 이전 generic 후보의 실제 subsystem은 닫았고, f18을 아이템UID로 명명하지 않는다. 관련 원문 M–O, L420–479.
- run381의 `InvenTargetWaitingState` seed도 원문을 따라 확인했다. vslot8=`494070`은 **0195**를 보내는 별도 경로다.0960의 대상선택 근거로 전용하지 않았다(선정 P, L480).
- 정확0960 immediate EDX→sender 후보에서 기본52A410 외52A820/52AC90을 분리했고, A23510은 `MailLayout::InitWriteMode`로 제외했다.52AC90은 f6/f17을 쓰는 별도 메서드이며 이 대상 click recipe와 섞지 않는다. 한정 pattern scan은 모든 computed/indirect opcode의 전수 증명이 아니다.
- 정적 확정은 **조건부 raw interaction→대상 클릭 UID→0960 wire**, **0967 typed/schema/publish**, **기존0965/0978 generic 소비**다. 실제 주문서22/25/26 raw/presence·동일 요청/응답·성공/실패/소멸·이름·메시지·저장/재접속·현재 화면은 UNKNOWN이다.
- 원서버 확률·축복/일반/저주 판정·안전강화 수치·소멸 정책·계산식을 클라이언트 이름이나 enum으로 추정하지 않았다. `world_enchant.py` LOCAL 정책은 별도로 유지한다.

## 5. 실행하지 않은 사용자 화면 실험안

현재 산출물에는 실험 실행이 없다. 다음 승인된 한 번의 게임 시험에서 기존 packet log/정상 시작 저장·소유 desktop 경로를 그대로 쓸 수 있다.

1. 실제 수신 Inventory에서 **사용 주문서22 또는25/26의 UID/template/f5 presence/value**, 대상 item UID·현재 이름·수량을 먼저 기록한다. f5를 catalog값이나 LOCAL0으로 채우지 않는다.
2. 주문서 사용 버튼까지만 수행해 현재 선택/프롬프트와 실제 C2S 발생 여부를 기록한다. raw7 조건부 경로라면 다음 대상 click 전후를 분리한다. 85h 문구를 임의 번역해 기대값으로 만들지 않는다.
3. 원 Inventory에서 대상 한 개를 클릭한다. 실제0960의 outer 사용UID, nested f2 대상UID/int64, f3 present0, f1=1/f15=f16 present0·그 외 presence를 대조한다. 이 단계에서 처음 주문서별 귀속을 판정한다.
4. 같은 작업의 실제 응답을 순서대로 보존한다.0967 모든 present field,0965 대상/주문서 변경,0978 UID, 실제 메시지·이름·선택 해제 화면을 각각 대조한다.0967 enum값을 성공·실패 화면 없이 이름 붙이지 않는다. 파괴/실패는 정상 결과가 관측된 경우에만 기록하고 성공 강제·반복 소비로 만들지 않는다.
5. 정책상 실제 mutation/소비가 있었다면 같은 시험 저장의 정상 종료·재접속에서 레벨/이름·주문서 수량·target 존재를 확인한다. 다른 실행/저장의 성공을 합치지 않는다.

최소 부족 입력은 **주문서별 actual ItemInfo.f5와 동일 작업 한 건의 C2S/S2C·화면 전후**다. 이 입력 없이 강화 전용 완료·메시지 mapping·+N 갱신·공식 확률을 확정하지 않는다.

## 6. 정적 확인과 파일 보존

새 body·RTTI·descriptor·opcode·xref 원문은 모두 run393 한 폴더에 보존했다. 선정 원문을 기존 run39/63/41/37과 직접 대조했으며 신규 검사기·guard·빌드·테스트·게임 실행은 없다. leaf가 PData에 없는 조회 실패는 정확 entry의 bounded window로만 보완했다. `window-294280.json`은 중간 명령에서 시작한 탐색 산출물로 **positive 근거에서 제외**했다. 기존 run·원본·저장·dirty 파일·branch·queue는 수정하지 않았다.
