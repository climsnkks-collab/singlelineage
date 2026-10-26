# 버프 HUD·잔여시간 / 낮밤 게임시간 원본 근거

2026-10-26, 이번 사용자 명시 REA 분석 범위. 제품 재개·서버 수정·게임/포트 시험·live attach는 하지 않았다. 결과는 **정적 연결 확인**이며 화면·입력·실제 동작 PASS가 아니다.

## 결론

- `4E5B SC_SPEED_BONUS_NOTI`는 actor 속도 성분을 갱신한다. 선택한 원 수신 경로에는 HUD 아이콘·잔여시간 필드/소비가 없다. 버프 아이콘은 별도 `4E91 SC_BUFF_ICON_NOTI`다.
- `4E91`의 outer `f1=1/2`는 add/upsert, `3`은 같은 K 제거다. required outer `f2`는 `BuffIconInfo` 메시지다. 이 child의 `f1` catalog, `f2` duration 표시 방식, `f3` 잔여시간, `f4/f5` instance/image K를 구별해야 한다.
- 원 HUD 아이콘은 선택한 **K의 signed 십진수 + `.png`**다. `f1 catalog`나 별도 spell metadata icon을 자동으로 이미지 K에 대입하는 계약이 아니다. 헤이스트/용기의 정당 원 발급 K·현재 atlas frame 대응은 이번 입력에서 확정하지 못했다.
- 남은 시간은 원 `Row+74`에서 실제 tooltip 문자열 생산자로 이어진다. `BuffIconInfo.f2=1`은 남은 시간을 일/시/분/초로 만드는 formatter를 선택한다. 상시 숫자 label·실제 픽셀·tooltip 재갱신 주기는 미관측이다.
- 낮밤 시각은 **`4E49 SC_WORLD_STATUS_NOTI`의 optional `f1:int64 varint`**다. 원 `WorldEnvironmentSubsystem`은 값을 `_gmtime64_s`에 그대로 전달하고 UTC 시·분으로 광도 계수를 계산한다. 따라서 이 consumer의 입력 단위는 **Unix epoch seconds 호환값**이며, 클라이언트 소비식에 L1J의 6배·3초 정렬은 없다.

## 기준 Source와 재사용

새 file-only 추출은 [run391/static_extract.py](../../local_server_rea_20261016/run391_buff_icon_gametime/static_extract.py)의 reader·PData·Capstone을 [followup_v2.py](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2.py)에서 재사용했다. 원 script/산출물은 보존하고 `followup_v2/`에 추가했다.

기준 carrier는 `work/rea_lineage_resume_20261013/main-gameplay/audit/metadata-v2/DERIVED_RESTORED_ANALYSIS_ONLY.exe`, image base `140000000`, inherited SHA256 `c822838351d774a2022af434829a36dbd9bee030bf22182b834ca4e8659701a9`, 26,021,376 bytes다. 원 LC·자원·저장에는 쓰지 않았고 전체 해시를 다시 계산하지 않았다. 실제 loaded image와의 동등성은 주장하지 않는다.

REA104의 `accepted-cache.json` 중 `4627E0/45FD40/4623B0`는 원 CONTROL `9ffc…` 분석 캐시의 재사용이다. 새 c822 함수와 정체를 합치지 않고 `cached-*.json`에 출처/원 pointer를 남겼다. REA104의 wire metadata·REA115/119·REA158/189/199/201·REA206/324의 한계와 source 정정을 그대로 재사용한다.

## 4E91 → Buff model → HUD

원 dispatch는 REA104 [wire packet](../../local_server_rea_20261016/run104_skill_buff_contract/wire_schema/packet.json)의 `responses[5]`에 고정되어 있다: outer schema `15ED770`, typed `SC_BUFF_ICON_NOTI`, event `17FDFC0`, captured `466C30 → 463960 → 4627E0`. required fields는 `f1`과 `f2`이며 outer f1은 closed enum이다. `1/2/3`의 wire 수용과 native 분기는 REA104의 [enum 근거](../../local_server_rea_20261016/run104_skill_buff_contract/wire_schema/buff_enum_validator/packet.json)를 재사용한다. 이 값들이 전체 유효 enum 범위라는 뜻은 아니다.

| BuffIconInfo child | 원 raw offset | 형식 | 확인된 소비 |
|---|---:|---|---|
| f1 | 30 | uint32 varint | Row04 catalog, static spell lookup의 별도 입력 |
| f2 | 34 | closed enum varint | duration formatter 선택. 부재 default는 0 |
| f3 | 38 | uint32 varint | bits를 signed32로 해석 → Row08 → F32 Row74 |
| f4 / f5 | 3C / 40 | uint32 varint | signed 조건으로 K 선택 → Row00·map identity·HUD frame key |

child의 required field는 없다. 전체 15개 필드의 원 schema와 wire type은 REA104 [packet.json](../../local_server_rea_20261016/run104_skill_buff_contract/wire_schema/packet.json)의 `nested_schemas[1]`을 따른다. f3를 float/fixed32 wire나 ms deadline으로 바꾸지 않는다. f10/f14/f15 및 다른 필드의 전체 역할은 이번 범위에서 새로 확정하지 않았다.

K 선택은 `i32(f4)>0 || i32(f5)<=0`이면 `f4 bits`, 그 외에는 `f5 bits`다. 같은 K의 add/upsert는 기존 row를 지운 뒤 새 row를 넣는다. `ready B+280=0`일 때 owned packet이 pending queue에 보관되고 정상 ready callback `462750`이 재생한다. 임의 ready 강제를 전제하지 않는다.

원 Row add event `B+20` → `149030/9A23E0/9A3390`의 `HudBuffLayout` 가입 → `9A46D0/9A0870` → `917AC0 BuffSlot`이다. Row00/08/0C가 Slot18/1C/20으로 전달된다. `Icon` child에 signedDecimal(Slot18)+`.png`가 전달되고, base Sprite `BFED40 → BDA150`은 현재 cache exact frame/한 단계 alias를 찾으며 첫 miss에 `0.png`를 다시 조회한다. 근거: [REA158](../../local_server_rea_20261016/run158_buff_effect_consumer/static-recovery/findings.md), [REA189](../../local_server_rea_20261016/run189_buff_hud_slot_producer_lifetime/MAIN_REVIEW.md), [REA199](../../local_server_rea_20261016/run199_buff_icon_resource_lookup_fallback/MAIN_REVIEW.md), [REA201](../../local_server_rea_20261016/run201_buff_wire_identity_frame_key/MAIN_REVIEW.md).

예를 들어 K65538이면 원 입력은 `65538.png`이며 catalog2/icon385로 자동 정규화되지 않는다. `4E91` 수용·row 생성·fallback 그림은 의도 버프 아이콘의 성공과 구별한다. 헤이스트/용기의 packet 발급·K·선택 frame·pixels를 이번에 관측하지 않았다. 기존 `LOCAL_ITEM_ORIGIN:HASTE`, item17/495와 spell51/53 합성 정책은 로컬 저장/속도 모델이며 원 icon K의 증거가 아니다. [기성 합성 계약](../implementation-3/skill-buff/item-origin-speed-composition-v1/API.md)도 수치/정책·실 delivery 미공급 경계를 명시한다.

## 잔여시간의 실제 문자열 소비

`f3 → signed Row08 → F32 Row74`와 normal update `4623B0`의 `remaining -= XMM1`은 REA104/115를 재사용했다. REA119의 원 frame caller `B539E0 → ED500 → F6F50 → v28 → 4623B0`는 scheduler timescale을 포함한 **simulation seconds**다. 실제 timescale·walltime 1:1은 미관측이며, 별도 `4E41` absolute deadline/held-context epoch 경로를 ordinary f3와 합치지 않는다. [REA119 findings](../../local_server_rea_20261016/run119_buff_delta_normal_caller/worker/findings.md).

새 선택 원문과 캐시를 연결하면 다음과 같다.

1. `462B66..462B77`: child f2가 있을 때 raw34 값을 local `rbp+90`에 복사한다. `462FB3..462FE0`은 그 값을 분기해 formatter를 선택한다. [cached-4627e0.txt](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/cached-4627e0.txt).
2. f2=1 → vtable `11BB500`, invoke slot10=`45EC80`. 입력 i64가 음수이면 별도 localized branch, 0 이상이면 86400/3600/60으로 분해해 숫자와 localized 단위를 조합한다. 최대 두 단위까지 조합하고 남은 초도 읽는 원 분기다. f2=0/2 → `11BB4C8/45F470`, 입력 duration을 사용하지 않는 localized 문구. switch default → `11BB490/45EC00`, 빈 문자열. 이 native default 분기는 임의 enum 값의 wire 수용 증명이 아니다. [rtti-171d5a0.json](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/rtti-171d5a0.json), [function-45ec80.txt](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/function-45ec80.txt), [function-45f470.txt](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/function-45f470.txt), [function-45ec00.txt](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/function-45ec00.txt).
3. `45FE01..45FE4A`: 선택 formatter를 Row+D0 storage/Row+108 callable에 원 clone/move 방식으로 보관한다. [cached-45fd40.txt](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/cached-45fd40.txt).
4. REA189의 `918540` 원 Widget callback은 같은 Slot18 K로 현재 RowPair를 찾고 TooltipContent 생산 callback `1213290`을 `B27DA0`에 넘겨 원 manager `B28EC0`에 게시한다. `1213290` RTTI가 `BuffSlot::Init`의 `TooltipContent` lambda이고 slot10=`918840`인 것을 새로 확인했다. [vtable-1213290.json](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/vtable-1213290.json), [REA189 source-918540.json](../../local_server_rea_20261016/run189_buff_hud_slot_producer_lifetime/ctor_change/source-918540.json).
5. `918840 → 70120 → sameK 460B50 → 460310`: 매 생산 호출에서 현재 Row를 다시 찾는다. `460349`는 현재 Row74 F32를 i64 trunc하고 `460353..460371`은 Row108.v10에 그 값을 전달한다. 만들어진 description+duration 문자열은 `9188B9..9188BF`의 `4E29E0` TooltipContent 생성으로 소비된다. [function-918840.txt](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/function-918840.txt), [function-460310.txt](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/function-460310.txt).

따라서 **아이콘 + 남은 시간 tooltip에 필요한 별도 패킷/필드는 4E91의 K/f3/f2와 원 HUD 소비**다. f3만 넣고 f2를 생략하면 이 선택 경로는 default0 formatter를 쓰므로 숫자 잔여시간 문구를 기대할 근거가 없다. 표시 형식의 정확 한국어·상시 숫자 overlay·tooltip timer 재호출 주기·현재 frame/Widget·입력/픽셀은 이번 정적 분석에서 미관측이다. 원 row/manager/Widget 수명·정상 제거·close는 REA189의 기존 경계를 유지한다.

`4E5B`의 registry `293570/294C70 → 305D50 → 31DC80 → event17FC700 → 4E850`은 Actor UID로 SpeedComponent를 골라 signed q→F32(q)/100을 기존 key에 교체한다. move key0/attack key1은 interval=base/(1+b)를 소비한다. 이 callback에 icon K·duration·TooltipContent 갱신은 없다. 전체 client의 임의 side effect 부재를 주장하는 것이 아니라 **이 선택된 수신 소비는 별개**라는 결론이다. [REA206 contract](../../local_server_rea_20261016/run206_multi_buff_speed_meditation_contract/worker/contract.md), [REA324 contract](../../local_server_rea_20261016/run324_windwalk_speed_field_semantics/contract.md).

## 4E49 게임시간 wire / dispatch

`294BB5`가 factory table `11A9598`을 고르고 `294BBC`가 `edx=4E49`를 원 registrar `292F80`에 준다. table+10의 실제 publisher는 `306480`이다. [xrefs-11a9598.json](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/xrefs-11a9598.json), [game-time-selected-v2.json](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/game-time-selected-v2.json).

`306480 → 31E070`이 RTTI `SC_WORLD_STATUS_NOTI` vptr `11E3AA0`의 wrapper를 만들고 `2C5A00 → DEFFF0`으로 원 message parse를 수행한다. `306521..306528`은 event `17FC340`으로 publish한다. [function-306480.txt](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/function-306480.txt), [function-31e070.txt](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/function-31e070.txt), [기존 rtti-1681508.json](../../local_server_rea_20261016/run391_buff_icon_gametime/rtti-1681508.json).

| SC_WORLD_STATUS_NOTI | 원 raw / wrapper | 형식 | 확인된 의미 |
|---|---|---|---|
| f1 optional | 18 / 20 | signed int64, protobuf varint, tag08 | WorldEnvironment 시각. gmtime64_s 입력 seconds |
| f2 optional | 20 / 28 | signed int32, protobuf varint, tag10 | 의미 UNKNOWN. 선택한 WorldEnvironment callback은 복사만 하고 적용하지 않음 |

원 schema=`15FCCB0`, typecard f1=`10D1`/f2=`1091`, presence bit0/1, IsInitialized=`753FB0`는 무조건 true이므로 required 필드가 없다. [schema-11e3aa0.json](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/schema-11e3aa0.json), [leaf-753fb0.txt](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/leaf-753fb0.txt). typecard의 int64/int32 해석은 REA104 [fast_wire_proof.py](../../local_server_rea_20261016/run104_skill_buff_contract/wire_schema/fast_wire_proof.py)의 같은 family를 재사용했다. 선정 fastslot tag08/10도 JSON에 보존했다. 4E49라는 숫자나 이름만으로 필드 의미를 부여하지 않았다.

## 시각 → 낮밤 consumer

`546A70` 생성자의 vptr `11C84C0` RTTI는 `WorldEnvironmentSubsystem`이다. `546B60..546B71`은 callback `547620`을 event17FC340에 구독한다. callback은 wrapper f1 presence를 검사한 뒤 **64비트 전체를 WorldEnvironment+28에 저장**하고 `547AD0`을 부른다. f1 부재면 이 store/update를 건너뛴다. [vtable-11c84c0.json](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/vtable-11c84c0.json), [function-546a70.txt](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/function-546a70.txt), [function-547620.txt](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/function-547620.txt).

`547AD6..547AFF`: +28 값의 주소를 IAT `10B78D8`에 그대로 준다. restored IAT cell은 hint/name RVA `15BA8DC`, 문자열 `_gmtime64_s`다. 따라서 표준 CRT binding 조건에서 Unix epoch seconds의 UTC `tm`을 얻는다. live IAT/CRT 구현이나 invalid/범위초과 입력 동작은 관측하지 않았다. [imports-selected.json](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/imports-selected.json).

`547B47..547BD5`는 `m = UTC.hour*60 + UTC.minute`와 아래 level을 만들고 `a = night_base + ((level-1)/14)*(1-night_base)`를 `WorldEnvironment+30`에 저장한다. `night_base`는 같은 객체+34이며 ctor 초기값은 float≈0.258(3E841893)이다. float 상수1·14의 원 RVA는126EAB4/126ECBC다.

| 분 m | level |
|---|---|
| m≤360(06:00), m≥1240(20:40) | 1 |
| 360<m<400(06:40) | min(15, trunc((m-360)*15/40)+1) |
| 400≤m≤1200(20:00) | 15 |
| 1200<m<1240 | min(15, trunc((1240-m)*15/40)+1) |

별도 현재 객체+890==1 조건은 계수를0으로 만든다. 그 필드의 의미와 화면 최종 셰이더/픽셀은 이번 선정 범위에서 확정하지 않았다. [function-547ad0.txt](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/function-547ad0.txt), [leaf-547be4.txt](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/leaf-547be4.txt). 후자는 PData 분리 tail의 normal release/RET이고 전체 EH·동시 close 보장은 아니다.

같은 event의 `CharacterDataSubsystem` callback `1153E0`은 f1 low32를+780 protected integer로 보관하고 기존 event를 통지한다. 이 사실을 낮밤 consumer의64비트 절단으로 오해하지 않는다. [vtable-1185340.json](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/vtable-1185340.json), [function-1153e0.txt](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/function-1153e0.txt).

같은 객체의 다른 원 event callback `547540`에도 presence bit4000인 qword가+28→547AD0으로 이어진다. 이 callback의 상위 message 정체/전체 snapshot 필드는 이번에 확정하지 않았다.4E49가 같은 저장/광도 계산을 갱신하는 경로는 확인됐지만 공식 server 발급 주기·클라이언트 독립 ticking은 미관측이다. [function-547540.txt](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/function-547540.txt).

L1J `D:/SingleLineageRef/l1j-en-classic/src/l1j/server/server/serverpackets/S_GameTime.java:33`은 1-byte opcode + writeD(time)인 다른 프로토콜이다. 이 참고 서버의 6배 clock·3초 정렬·낮밤 정책을 클래식4E49의 wire·소비 규칙으로 전용하지 않는다. 실제 클래식 발급 정책은 별도 미확정이다.

## 사용자 직접 화면 실험안 — 이번에는 실행하지 않음

1. 정상 로그인/캐릭터 선택/월드 진입의 같은 Source·시험 저장에서 현재 속도·아이콘·tooltip을 먼저 기록한다. 정당한 헤이스트/용기 적용에 대해 4E5B와4E91 수신, 4E91의 catalog/f2/f3/f4/f5, 선택K·현재 frame/alias·HUD Slot/현재Row를 함께 확인한다. 다른 버프 metadata로 K를 대체하지 않는다.
2. 해당 아이콘의 원 입력으로 tooltip을 열어 초/분 경계와 원 f2=1 formatter 결과·만료 제거를 확인한다. 상시 숫자 overlay가 실제 존재하는지도 구분해 기록한다. 익명 callback 직접 호출이나 ready 강제로 화면 성공을 만들지 않는다.
3. 시험 서버의 같은 정상 월드에서4E49 f1을 각각 UTC05:59/06:20/06:40/20:20/20:40을 나타내는 seconds로 변화시키고 원 WorldEnvironment+28/+30과 화면 변화를 함께 비교한다. 공식 원 서버의 주기/epoch 정책을 확정하려면 정상 온라인 수신을 별도로 관측한다. 임의 시험값을 공식 정책으로 채택하지 않는다.

남은 미확정: 헤이스트/용기별 원 catalog→K→frame mapping·정당 발급 wire, 현재 atlas/current HUD 동작, 상시 숫자 label·tooltip 재갱신 주기,4E49 f2 의미·공식 초기/갱신 주기·최종 렌더러. 서버 제품 코드는 변경하지 않았다.
