# ATS 같은 창의 나 / 동료 전환 설계

2026-10-28 · **STATIC_ONLY / 구현 설계**. 게임·서버·포트·원 함수 실행·화면 캡처·패킷 송신·DLL 빌드는 하지 않았다. 제품 코드·핀 DLL·원본 자원·사용자 저장·manual 프로필·ACTIVE_TASK·공식 큐를 수정하지 않았고 커밋도 하지 않았다. 이번 직접 요청의 분석·문서 범위만 수행한다.

## 1. 적용할 UI와 설계 경계

사용자 결정은 **하나의 ATSLayout에서 편집 대상만 전환**하는 것이다. 기존 버프/전투/옵션 탭은 유지하고, 도움말 탭의 자리를 `나 / 동료` 전환 버튼으로 재사용한다. 새 탭이나 자체 Win32/GDI 창을 만들지 않는다. 버튼에는 현재 대상이 항상 보이게 하고, 클릭하면 반대 대상을 요청한다. 이는 원본 기능으로 주장하지 않는 LOCAL UI 확장이다.

1차 대상은 **직접 접속한 법사 자신의 영구 character ID**다. 같은 ID 아래 `self_ats`(직접 플레이할 때)와 `companion_ats`(동료일 때)를 별도로 저장한다. `동료`는 현재 소환된 actor UID나 다른 법사를 뜻하지 않는다. 따라서 마법창·가방의 기존 drag producer를 그대로 이용할 수 있다. 기사로 로그인해 다른 법사를 편집하는 기능은 2차이며 이번에는 막힘과 후킹 후보만 남긴다.

권고 연결은 **도움말 callback의 index3만 가로채기 → DLL의 대상 상태 → 로컬 제어 IPC → 서버의 해당 ATS blob → 기존 4ED7 수신/ATS 로드 → 열린 창 population 재실행**이다. Save는 클릭 때 확정한 대상의 설정으로 저장한다. 현재 서버는 이 저장 분리나 IPC를 구현하지 않았다.

| 판정 | 이 문서에서의 의미 |
|---|---|
| 확인[정적] | 보존 복원 record, CSB, 디스어셈블리, 현재 소스에 실제 연결이 있음. 실행 성공 아님 |
| 설계 / LOCAL | 우리 DLL·서버가 추가할 동작. 원본 opcode/필드 의미와 구분 |
| UNKNOWN | ABI·분기·화면·실제 저장 등 아직 닫지 못한 부분. 불가능이나 성공으로 해석하지 않음 |

기준 원본은 **LC 26.09.29.2001**, CONTROL SHA256 `9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`다. [기존 ATS 조사](ATS_COMPANION_EVIDENCE.md)와 [TARGET_IDENTITY](../../local_server_rea_20261016/TARGET_IDENTITY.md)의 신원을 승계한다. 주소는 전부 **RVA**이며 preferred VA는 `0x140000000 + RVA`, 실제 설치 주소는 **선택된 module base + RVA**다. 분석 carrier `work/rea_lineage_resume_20261013/main-gameplay/audit/metadata-v2/DERIVED_RESTORED_ANALYSIS_ONLY.exe`와 기존 복원 section record는 실행용 제품이 아니다. 새 전파일 해시나 요청 중 핀 검사를 추가하지 않았다.

출처 비율은 **로컬 원본 자원·복원 코드·현재 프로젝트 소스 100%, 신규 웹·공식 API·L1J 0%**다. 기능 완성률이나 원본 동등성 수치가 아니다. 대상 전환·저장키·IPC는 별도 LOCAL 설계이며 기존의 출처 있는 backend 정책을 원본 UI 규칙으로 섞지 않는다.

## 2. 설정 blob와 슬롯 계약

상세 원명령·한계는 [blob 분석](ats-toggle-analysis/BLOB_FINDINGS.md)에 둔다. 외부 메시지의 핵심 경계는 다음과 같다.

| 방향 / 메시지 | f1 | f2 | 확인 근거 |
|---|---|---|---|
| C→S `4ED6 CS_SAVE_SETTINGS_REQ` | CharacterConfig 직렬화·변환 결과, wire2 | ATSConfig 직렬화·변환 결과, wire2 | `104EA0`, `10519C/1051AA`, serializer `765570` |
| S→C `4ED7 SC_CLIENT_SETTINGS_NOTI` | 같은 CharacterConfig 계열 | 같은 ATSConfig 계열 | handler `1067A0`, parser `2B0FB0`, serializer `765890` |

4ED6 필수검사 `765790`은 **f1 presence**를 요구한다. 4ED7 검사 `765AC0`은 항상 true지만, handler는 **`107310→FEF80`(CharacterConfig Clear), `10731C→101D30`(ATSConfig Clear)를 두 presence 검사보다 먼저 실행**한다. 앞의 `107309/107315`는 각 global을 RCX로 읽는 lea다. 따라서 **f2-only 4ED7로 전환하지 않는다.** 항상 현재 법사의 SELF CharacterConfig f1과 선택 대상 ATSConfig f2를 함께 공급해야 한다. f1/f2는 대상 식별자·JSON·새 명령을 넣는 빈 공간이 아니다. CharacterConfig의 f7에 병존하는 구형 ATSOptionSection과 별도 ATSConfig를 구분한다. 현재 pre-save는 후자를 생산한다. 같은 이름의 child를 자동 복사한다고 가정하지 않는다.

### 2.1. C→S와 S→C의 포장이 다르다

`1061C0`의 변환과 `1063E0`의 역변환은 다음 구조다. IAT `10B7C30/10B7C28`은 복원 import의 **`zlib1.dll!compress/uncompress`**에 대응한다. 이 경로에서 별도 암호화나 base64는 확인되지 않았다.

```text
W = little-endian u32(직렬화 protobuf 길이 N)
    + u8(flag)
    + (flag == 1 ? little-endian u32(zlib 길이 C) + zlib stream[C]
                 : 직렬화 protobuf[N])

4ED6 f1/f2 = W                     # raw bytes, C++ string 저장소
4ED7 f1/f2 = ASCII hex(W)          # 길이 2배, 서버 응답용
```

수신 handler의 **`10733A/1077DD→108570`**은 짝수 길이의 `0-9A-Fa-f`를 2글자→1byte로 바꾼 뒤 `1063E0`에 넘긴다. `4ED6` 요청 body 전체를 그대로 `4ED7`에 echo하면 안 된다. 서버는 각 f1/f2의 raw wrapper를 따로 hex로 바꿔 기존 frame codec으로 4ED7을 구성한다. outer protobuf 태그·길이·frame header는 hex 대상이 아니다.

native 압축 output buffer capacity는 **`0xED4`**이고 압축 실패 시 raw fallback을 쓴다. flag는 1일 때만 압축 분기이며 그 외 값은 raw 분기다. 실제 생성은 0/1을 사용한다. Python 초안의 엄격한 길이·해제 크기 상한은 오프라인 분석용이며 native 규칙이나 새 요청 guard가 아니다. 압축 library 버전별 byte 차이가 있으므로 원본 blob은 그대로 보관하고, 값 편집 때만 새 wrapper를 만든다.

### 2.2. protobuf tree와 회복/버프/전투 슬롯

아래 `+offset`은 **해당 message 객체 또는 명시한 ATS/native slot 객체** 기준이며 wire offset이 아니다. wire0은 varint, wire2는 길이 구분 bytes/message, wire5는 LE fixed32다. singular presence와 repeated 순서를 원문대로 보존한다.

```text
ATSConfig                           serializer 101D80
└ f1 ATSOptionSection (+18)          serializer 101940
   ├ f1 opaque string (+18)          의미 UNKNOWN; target ID로 전용 금지
   └ f2 ATSOption (+20)              serializer 101540
      ├ f1 BuffData (+18)            serializer FFB30
      ├ f2 BattleData (+20)          serializer 100560
      └ f3 OptionData (+28)          serializer 100A60
```

모두 wire2 nested다. Buff/Battle/Option의 Clear는 `FFA70/100500/1009E0`, vptr는 `1184278/11840D8/1184960`이다. pre-save **`42EBE0..42F103`**가 이 별도 ATSConfig tree를 실제 채운다.

| BuffData field | wire / 형식 | message offset | ATS saved source / 의미 |
|---|---|---|---|
| f1 | 2, repeated SlotShortcut | +18/count+20 | +370 vector / HP 회복 슬롯 |
| f2 | 5, float32 | +88 | +388 / HP 기준% |
| f3 | 2, repeated SlotShortcut | +30/count+38 | +390 vector / MP 회복 슬롯 |
| f4 | 5, float32 | +8C | +3A8 / MP 기준% |
| f5 | 2, repeated SlotShortcut | +48/count+50 | +3B0..+410, 0x10 step의 고정6 슬롯; 화면 그룹 순서 UNKNOWN |
| f6 | 2, opaque string | +78 | +410 string / 의미 UNKNOWN |
| f7 | 2, repeated SlotShortcut | +60/count+68 | +438 vector / 버프 목록 |
| f8 / f9 | 0, int32 | +80/+84 | +430/+434 / 의미 UNKNOWN |

HP/MP%는 정수 비트값이 아니라 **float32**다. native UI `8EC100`의 HPTextField/MPTextField는 saved+388/+3A8→working+468/+488을 float로 표시한다. protobuf 생성자·Clear의 내부80.0과 presence0을 사용자의 현재 기본 설정으로 확정하지 않는다. 자원은 회복2+2칸을 설명하지만 반복 field의 native 허용 정원과 화면 정원은 별개다.

**공통 SlotShortcut는 `CharacterConfig_SlotShortcut` 타입 재사용**이며 serializer `F9BE0`, vptr `1184550`, factory `103950`, repeated append `103810`으로 연결된다.

| SlotShortcut field | wire / 형식 | message offset | 저장 시 실제 native slot source |
|---|---|---|---|
| f1 | 0, int32 | +20 | slot+8, kind 구분값 |
| f2 | 0, bool | +24 | 현재 ATS pre-save가 생산하지 않음 |
| f3 | 0, int32 | +28 | 현재 ATS pre-save가 생산하지 않음 |
| f4 | 0, int32 | +2C | slot+20 또는 slot+0 low32; 목록/kind 분기에 따름 |
| f5 | 0, int32 | +38 | slot+B8 |
| f6 | 0, 64bit 일반 varint | +30 | slot+28 qword; proto int64/uint64 명칭 UNKNOWN |
| f7 | 2, opaque string | +18 | slot+30 string |

int32는 `movsxd` 후 일반64bit varint로 쓰므로 **zigzag가 아니다**. 음수는10byte가 될 수 있다. source별 정확 분기는 다음과 같다.

- HP/MP/고정6개 슬롯: f1/f4/f5/f6/f7을 slot+8/+20/+B8/+28/+30에서 기록한다.
- 버프 목록: kind==2면 같은 복합값을 쓰고, 다른 kind는 f4에 slot+0 low32를 쓴다.
- 전투 순차/조건 child: f1=slot+8, f4=slot+0을 쓴다.

추가 producer 추적으로 **kind1=마법 데이터 row**, **kind2=inventory item snapshot**을 구분했다. 근거는 [UI 분석](ats-toggle-analysis/UI_FINDINGS.md)의 slot producer와 선택 명령이다.

| 종류 | producer와 실제 값 생성 | ATS에 직렬화되는 값 / 한계 |
|---|---|---|
| kind1 마법 | **`B079B0`**가 `AE360`의 SpellSubsystem(RTTI166B978) `+3E0` learned/state map을 data row+0 int key로 조회. `B07BBE..B07BD6` 등에서 slot+0=sign-extended row+0, slot+8=1, slot+C=row+48, slot+30=`5A6AB0(row)` 라벨 | 순차/조건·버프의 non-kind2는 **f1=1, f4=내부 마법 row ID**. 캐릭터 UID가 아니다. 서버의 실제 cast opcode ID와 숫자 domain 일치는 아직 UNKNOWN |
| kind2 아이템 | **`B03780`**가 ItemEntity에서 slot+0←entity+8(UID), +20←+10(template ID), +28←+18(opaque64), +B8←+54(opaque int32), +30←`50A220(entity)` 문자열, +8=2를 작성 | HP/MP/고정슬롯 및 kind2 버프는 **f1=2, f4=template ID, f5=ItemInfo f22, f6=ItemInfo f3, f7=문자열**. f3/f22의 공식 의미는 UNKNOWN이라 원문 보존 |

아이템 필드 이름은 [기존 ItemInfo 분석](../../local_server_rea_20261016/run30_inventory_first_wire/findings.md)과 `509390` ItemEntity constructor의 DTO→entity 복사를 재사용했다. DTO+70/+74/+78/+CC의 ItemInfo f1/f2/f3/f22가 위 entity 필드로 이동한다. `509390`을 snapshot writer라고 오인하지 않는다.

`8F2A00`의 kind2는 **InventorySubsystem getter `77340`→`4FFCE0`**에 +20/+B8/+28/+30의 복합 query를 전달한다. `4FFCE0`는 item+18을 query+8과 비교하므로 slot+28은 inventory lookup identity에 참여한다. **kind2의 현재 UID는 slot+0에 있지만 이 저장 분기에서는 f4로 쓰지 않고 template ID를 쓴다.** 아이템을 `f4=템플릿ID` 한 값만 넣어 합성하거나 f6를 임의 UID로 채우는 것은 이 계약을 충족하지 않는다. **원 UI가 만든 슬롯을 서버에서 분해·저장·다시 인코딩**하는 수준은 확보했다. 아이템 복합키 의미·재접속 유효성·AI 소비는 추가 연결이 필요하다.

| BattleData / ConditionalSpell | wire / 형식 | message offset | ATS source |
|---|---|---|---|
| Battle f1 | 2, repeated SlotShortcut | +10/count+18 | +530 vector, step0x10 / 순차 목록 |
| Battle f2 | 2, repeated ConditionalSpell | +28/count+30 | +548 vector, step0x18 / 조건 목록 |
| Conditional f1 | 0, int32 | +20 | entry+0 / 아래 1..6 조건 종류 |
| Conditional f2 | 0, int32 | +24 | entry+4 / 아래 %·초·회 정수 기준값 |
| Conditional f3 | 2, SlotShortcut | +18 | entry+8; child f1/f4는 slot kind/slot+0 |

ConditionalSpell serializer는 `1001A0`, vptr `1184140`다. UI 순차/조건 각8회 loop는 `8ED160`에서 확인했다. UI8칸과 protobuf repeated의 허용 정원을 같은 사실로 합치지 않는다.

W36 정적 조사 기준: LC `26.09.29.2001`, CONTROL SHA256 `9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`. 아래 주소는 모두 RVA다. 조사 전문: `C:/Users/Chansol/AppData/Local/Temp/claude/D--claude/d2e6d25b-5490-4381-89b5-3fba6fdf4077/scratchpad/w36_result.md`.

| f1 | 조건 / f2 단위 | 실행 판정 | UI 문구 RVA | 판정 RVA |
|---:|---|---|---|---|
| 1 | 자신의 HP 이상 / 정수 % | HP% ≥ f2 | `8E6FED` | `449D8D..449D91` |
| 2 | 자신의 HP 이하 / 정수 % | HP% ≤ f2 | `8E7006` | `449DA2..449DA6` |
| 3 | 자신의 MP 이상 / 정수 % | MP% ≥ f2 | `8E701F` | `449DB7..449DBB` |
| 4 | 자신의 MP 이하 / 정수 % | MP% ≤ f2 | `8E7038` | `449DCC..449DD0` |
| 5 | 같은 마법 재사용 간격 / 정수 초 | 경과 정수초 ≥ f2 | `8E7051` | `449E24..449E43` |
| 6 | 같은 마법 누적 사용 상한 / 정수 회 | 기존 사용 횟수 < f2 | `8E706A` | `449FBE..449FD0` |

`448BF0→449BB0` 실행 경로에서 자신의 CharacterDataSubsystem HP/MP를 읽는다(`449BE8..449C11`, getter `3EB60`). `float32(current×100/max)`를 정수 반올림 없이 비교한다(`449C15..449D25`). 동료 서버에서는 사용자 결정에 따라 **동료 자신**의 자원을 쓴다.

같은 spellRowID의 조건은 순서대로 **AND** 평가하며 하나라도 실패하면 시전하지 않는다(`449D58..449D62`, `449FD6..449FE1`). 시간 기록이 없으면 첫 평가 시각을 기록하고 그 시간 조건을 통과한다. 뒤 조건이 실패해도 첫 시각은 유지한다(`449E4B..449F1F`). 시각·횟수 key는 spellRowID이며 native `5B63A0` true 반환 뒤 횟수를 늘리고 시각을 갱신한다(`449324..449344`, `449408`). 서버는 실제 자원/효과 시전 수락 시 갱신하고 실패 시 갱신하지 않는다. 순서 칸에 같은 마법이 있어도 해당 조건을 우회하지 않는다.

`f1=0`·음수·7 이상은 false다(`449D68..449D6F→449FDE`); UI는 빈 문구(`8E7083..8E709A`)이며 `0=해제`로 해석하지 않는다. UI callback은 index+1을 저장(`8F55DA..8F55DF`), 단위는 5→초·6→회·나머지%(`8EDD4F..8EDD85`)다. UI f2 입력은 1..99 clamp(`8E762F..8E767C`, `8E7735..8E7769`)지만 wire/로드 값을 같은 범위로 제한하는 근거는 아니다. Save는 entry+0/+4→객체+20/+24(`42EF9C..42EFAC`), 로드는 `430BBE..430BEC→438580`이며 별도 배율 변환은 없다.

초기 생성 시 두 상태는 비어 있다(`77244..7728E`). 원본 START/STOP·맵 이동 초기화는 UNKNOWN이고 확인한 target 변경 분기는 초기화하지 않는다(`448CDA..448E6A`). 동료의 **대상 변경·재소환·재접속 시 순서와 시간·횟수를 처음부터** 시작하는 것은 사용자 지정 LOCAL 정책이다. 원본 UI→Save→재접속→시전 동작은 이 정적 조사나 서버 개발 시험으로 입증하지 않았다.

### 2.3. OptionData 필드 의미

pre-save `42EFEE..42F0F1`과 serializer `100A60`, UI setter **`8EEF00`**를 교차했다. 아래 source는 saved ATS 기준이고 working은 대체로 +0x30이다. 전부 wire0이며 bool은0/1, int32는 일반 varint다.

| f | 형식 / message offset | ATS source | 확인한 UI 의미 / 값 |
|---|---|---|---|
| 1 | int32 / +24 | +590 | 탐색 범위 |
| 2 | int32 / +28 | +594 | 사냥구역 걸음 |
| 3 | bool / +2C | +599 | 아이템 우선 |
| 4 | bool / +2D | +59A | 매너 사냥 |
| 5 | bool / +2E | +59B | UNKNOWN |
| 6 | bool / +2F | +59C | 선공 우선 |
| 7 | int32 / +30 | +5A0 | 획득 무게: native 비교100/50/83, 표시 해제/49/82 |
| 8 | bool / +1C | +5A4 | LootAttempt: 자원 표시 아데나만 획득 |
| 9 | int32 / +34 | +5B8 | UNKNOWN |
| 10 | int32 / +38 | +5BC | UNKNOWN |
| 11 | int32 / +18 | +5AC | 귀환 HP: 0/30/50 |
| 12 | int32 / +3C | +5B4 | 귀환 무게: UI 비교100/50/83 |
| 13 | bool / +1D | +598 | 사냥구역 제한 checkbox |
| 14 | bool / +1E | +5A5 | 비전투 귀환 checkbox |
| 15 | int32 / +40 | +5A8 | 비전투 귀환 초 |
| 16 | int32 / +20 | +5B0 | 귀환 MP: 0/5/10 |

생성자 `F9210`의 내부 값·presence0과 UI가 선택하는 값을 구분한다. 특히 f12 내부값101을 UI 비교100에 맞춰 조용히 수정하지 않는다. 알려진 옵션만 필드 단위로 편집하고 unknown·반복·명시0·opaque string을 보존한다.

### 2.4. 서버 초안의 사용 범위

[ats_blob_draft.py](ats-toggle-analysis/ats_blob_draft.py)는 제품 import 없는 독립 오프라인 초안이다. `wrap_blob/unwrap_blob`은 wrapper, `settings_noti_field/read_settings_noti_field`는 수신 hex 방향, `SCHEMAS/inspect_message`는 위 tree를 처리한다. `Field.raw`와 `encode_fields`는 unknown·반복·필드순서·비정규 varint·presence를 유지한다. float도 raw4byte로 유지한다. 원하는 nested field만 다시 인코딩해 부모 length를 재계산하면 된다.

```python
# outer f1/f2는 기존 protobuf/frame codec으로 별도 추출·구성한다.
self_proto = unwrap_blob(c2s_field1_raw)
ats_proto = unwrap_blob(c2s_field2_raw)
tree = inspect_message(ats_proto)
assert encode_fields(parse_fields(ats_proto)) == ats_proto

# 새/수정된 ATS protobuf를 서버→클라이언트로 보낼 때:
s2c_field1 = settings_noti_field(self_proto)
s2c_field2 = settings_noti_field(selected_ats_proto)
# 4ED7(field1=s2c_field1, field2=s2c_field2); field값만 ASCII hex다.
```

이 초안은 정상 native sample의 수신 성공, 모든 malformed 입력의 native 동작, `.proto` 원선언 전체를 증명하지 않는다. protobuf groups는 미지원이며 원문을 버리는 대신 파싱 실패로 남긴다. 슬롯 전체 의미·실제 권한·원본 저장정책의 복원도 아니다.

## 3. 탭 callback과 열린 창 재로딩

기준 클래스는 ATSLayout ctor `8E3E60`, Initialize `8E5F40`, vptr `120F308`; PC 구현 ctor/factory `8FCFE0`, Initialize `8FBFE0`, vptr `1210E88`다. `Root.Tab.Bt_Buff/Combat/Option/Help`라는 기존 lookup 키를 유지한다. 문구·역할이 바뀌어도 `Bt_Help` 노드 이름까지 바꾸지 않는다.

`8FCFE0`는 size0x290을 할당하고 base ctor/PC Initialize를 호출하는 **shared-result factory 형태**다. `void ctor(self*)`로 잘못 호출하지 않는다. owning manager에서 정상 instance를 얻는 경로를 재사용하고 raw factory 호출을 ATS show로 대체하지 않는다. 이전 command 경로 `8E6550`의 command0=show, command1=hide, **command2=표시 조회**이며 다른 창의 command2 toggle을 복사하지 않는다.

constructor의 **`8E4CBF` 네 버튼 루프**는 callback capture에 `+8=ATSLayout*`, `+10=index`를 저장한다. 함수객체 vtable `120E818`의 `+10` invoke **`8F7940` → `8E78A0(layout,index)`**로 들어간다. 도움말 index는 **3**이다. 따라서 공통 탭 함수를 무조건 바꾸거나 다섯 번째 탭을 추가할 필요가 없다. 우리 instance의 index3만 새 대상 전환으로 소비하고, index0..2는 원 callback에 전달하는 것이 좁은 후킹 지점이다.

실제 버튼 event는 ctor **`8E4E59→9667B0`**, destination **Button+4F0**로 전달된다. `9667B0`는 add-listener가 아니라 native function wrapper의 +38 swap과 inline move/destroy를 처리한다. 임의 MSVC `std::function`을 호환형으로 넣지 않는다. **1차 후보는 `8F7940` entry detour + 해당 ATS instance filter**다. callback container 교체는 native wrapper 소유 ABI를 확인한 뒤의 대안으로 남긴다. 공용 vtable 메모리를 모든 창 대상으로 덮지 않는다.

```cpp
// 설계 의사 코드. patch/trampoline 생성·ABI 확정·설치는 이번에 하지 않았다.
struct TabCapture { void** vptr; void* layout; uint32_t index; uint32_t pad; };
void HookTabInvoke(TabCapture* f) { // 원 leaf: RCX=capture, EDX=index
    if (!OwnsThisAtsInstance(f->layout) || f->index != 3)
        return OriginalTabInvoke(f);   // 8F7940 원3명령 trampoline
    QueueToggle(f->layout, LastContentTab0to2(f->layout));
    // Help의 원8E78A0(layout,3)은 호출하지 않는다.
}
```

entry의 stolen-byte 길이·상대분기 relocation, 실제 반환형/thunk, instance attach/destruction 및 재진입 퇴역은 구현 전 확인한다. 설계상 native 구조체 필드가 확인됐다는 뜻이지 복사해 빌드할 수 있는 완성 hook 코드라는 뜻은 아니다. hook의 진행 중 호출과 UI 작업을 정리한 뒤 원 entry를 복원하고 trampoline을 해제한다.

표시 문자열은 Button title이 아니라 **`Root.Tab.Bt_Help.Tx_Help` Text child**다(일반 CSB offset235312, Purple259888). 기존 `BF9ED0(Text*,string*)`는 Text setter 후보이나 이 child subtype/ABI 호출은 UNKNOWN이다. 인스턴스 Text adapter로 `나 / 동료` 현재 선택을 표현하고, 전환 중에는 완료 전 대상 이름을 확정하지 않는다.

로드된 global 설정은 **`4302F0` OnCharacterConfigLoaded**에서 ATS model로 읽힌다. 이 함수의 선택 전체 명령에서는 열린 ATSLayout을 직접 refresh하는 call이나 간접 call을 찾지 못했다. UI Initialize의 ATS `+28` delegate는 `8EF560`(Play 표시), `+E8`은 `8EF5B0`(시간), 별도 subsystem `+D8`은 `8EF340`(drop callback 재설치)로 연결된다. 이를 설정 전체 재바인딩 알림으로 취급하지 않는다. **4ED7 도착만으로 열린 슬롯·조건 UI가 다시 읽힌다고 보장할 수 없다.**

확보한 전체 show/reload 후보는 **vtable+70 = `8E6A80(layout,bool)`의 true 분기**다.

1. `42BAA0`: saved buff `ATS+370`→working `+450` deep replacement.
2. `42BD30`: saved battle `+530`→working `+560` deep replacement.
3. saved 옵션 `+590` 계열→working `+5C0` 계열 복사.
4. **`8EC100`(버프/회복 population), `8ED160`(전투 population), `8EEF00(layout,true)`(옵션 population)**.
5. `8E78A0(layout, layout+284의 현재 탭)`와 Play 표시 갱신.

vector 대입 helper `42D4A0/4286A0`은 기존 원소를 `4391F0`으로 release하고 end를 begin으로 되돌린 뒤 새 원소를 deep-copy한다. 반복 갱신을 기존 목록 뒤 append하는 구현으로 바꾸지 않는다. show true 전체 호출은 창 열기·입력·상태 부작용도 포함할 수 있어 **정확한 위치는 확인, 열린 창에서의 직접 호출 안전성은 UNKNOWN**이다. 구현은 full owning show 경로를 검증하거나 위 population 순서를 UI thread adapter에서 재사용한다. 포인터 보유·native 컨테이너 복사를 `memcpy`로 대체하지 않는다.

전환 시 마지막 내용 탭(index0..2)을 별도로 기억하고 reload 뒤 그 탭을 선택한다. index3을 원 `8E78A0`에 넘기면 도움말 페이지로 가므로, 전환 버튼 클릭을 소비한 뒤 기존 Help 선택 상태로 바꾸지 않는다. 버튼은 탭 selected 표시와 별개로 현재 `나 / 동료`를 표현한다.

### 3.1. 후킹/호출 목록

| RVA / 대상 | 사용할 역할 | 확인과 남은 경계 |
|---|---|---|
| `8FBFE0` PC Initialize 종료 부근 | owning instance attach 관측 후보 | 초기화 중 callback 금지. 전체 Initialize 재호출은 delegate 중복 위험 |
| **`8F7940`** / capture index3 | 대상 전환 click detour 1순위 | 3명령·인자 source 확인. patch 크기/relocation·instance filter 수명은 구현 전 확인 |
| `9667B0`, Button+4F0 | callback instance swap/restore 대안 | wrapper 소유 ABI 미완. std::function 임의 대입 금지 |
| `1067A0`, **`4302F0` 완료 경계** | full4ED7 parse/ATS saved 반영 이후 UI 작업 예약 | global 초기화·hex parse 확인. 여러 응답·닫기 시 적용 수명은 구현할 부분 |
| **`8E6A80` true** | saved→working와 열린 창 reload | exact body 확인. parent show 부작용을 포함한 직호출 안전성 UNKNOWN |
| `42BAA0`, `42BD30`; `8EC100/8ED160/8EEF00` | reload를 분리하는 대안 | native copy/release/옵션 순서 보존. fullshow와 두 경로를 중복 실행하지 않기 |
| `8E78A0`, self+284 | 내용 탭 복원 | index0..2; index3은 소비한 전환 버튼이라 넘기지 않음 |
| **`8F6450`** / Save invoke | 클릭 scope·snapshot 결속 | UI→model 경로 확인. enum2→Config scheduling 마지막 연결 UNKNOWN |
| `42EBE0`, `104EA0`, **`1051AA`** | actual serializer snapshot·원4ED6 SELF 보존·cache 연결 | 각 기능 주소 확인. ABI/cache 갱신 지점·autosave 포함 구현은 미완 |
| `B03780`, `B079B0`; `8FCD40/8F2A00` | 2차 target drag view adapter seed | 값 생산/조회 일부 확인. target view/소유·학습·소비 수명은 2차 |

모든 entry를 일괄 detour하는 목록이 아니다. 먼저 tab invoke와 필요한 load/save 경계만 선택하고 native owning 경로를 재사용한다. instance destroy/로그아웃의 정확 퇴역 hook RVA는 아직 UNKNOWN이다. 전역 detour라도 실제 동작 변경은 bridge가 보유한 현재 ATS instance에 한정한다.

## 4. Save 귀속과 DLL → 서버 제어 경로

현재 [settings.py](../../../tools/local_original_session/settings.py)의 `SettingsStore`는 **계정 UUID별 마지막 opaque 4ED6 요청**을 보존한다(`LOCAL_ACCOUNT_OPAQUE_LAST_REQUEST`). [broker.py](../../../tools/local_original_session/broker.py)의 `save_settings`는 bound account와 기존 owner를 확인하고 저장한 뒤 빈 응답을 반환한다. 캐릭터별 ATS 저장·동료 모드·저장 ACK·자동 4ED7 echo는 현재 기능이 아니다.

따라서 `server.current_mode`만 바꾸고 이후 모든 4ED6을 그쪽에 저장하면 안 된다. 원 Config는 Save 클릭과 다른 시점에도 저장할 수 있고, f1은 가방창 등 일반 캐릭터 UI와 공유된다. **클릭 시점의 대상 + 실제 직렬화된 f2 snapshot**을 한 저장 작업으로 결속해야 한다. target 전환 응답, 파일 기록 완료, native model 반영, 화면 갱신 완료를 구별한다.

### 4.1. 전송안 선택

| 방법 | 판단과 필요한 변경 |
|---|---|
| 기존 f1/f2, section의 미해석 string, ATS 시작/종료 enum에 구분값 삽입 | 채택하지 않는다. 이미 소비되는 설정·실행 의미를 파괴한다 |
| 기존 4ED6에 새 LOCAL f3(scope 등)를 추가 | 새 opcode 없이 가능하지만 원본 field로 주장할 수 없다. 현재 `settings.parse`는 unknown field를 거절하므로 native serializer와 서버 parser를 함께 바꿔야 한다. scope는 클릭 때 capture해야 하며 송신 때의 전역 mode를 붙이는 것으로는 지연 저장 race를 해결하지 못한다 |
| DLL→Python 별도 LOCAL 제어 IPC | **권고.** 조회/전환과 companion Save를 원 게임 메시지와 구분한다. 원4ED6는 SELF 설정 귀속을 유지한다. 기존 파일+UI 메시지 dispatch/수집 경계를 확장하며 새 listener/게임 opcode를 만들 필요가 없다 |

IPC의 최소 동작은 `select(scope)`, `save(scope, actual_f2_bytes)`, `apply_completed`, `saved/failed`다. request ID/창 수명은 기존 owned command sequence에 연결하고, 서버는 인증된 선택 캐릭터에서 영구 ID를 얻는다. DLL이 보낸 actor UID를 캐릭터 권위로 쓰지 않는다. native byte payload는 길이 구분한 binary sidecar로 전달하고 로그·JSON에 base64로 출력하지 않는다. 기존 result 파일만으로 unsolicited 클릭 이벤트를 지원한다고 주장하지 않는다. native UI thread는 이벤트를 enqueue하고 Python의 기존 event loop가 파일/저장을 처리한다. UI thread 안에서 asyncio handler·blocking IO를 실행하지 않는다.

### 4.2. 전환과 Save 순서

**대상별 in-memory draft**를 두되 영구 Save와 구별한다. 전환 자체는 Save가 아니다. 다른 쪽에서 미저장 변경을 하고 돌아와도 해당 draft를 재표시하며, 처음 열린 scope만 서버 저장을 읽는다. 서버를 거쳐 반영하는 경우 해당 draft를 저장하지 않는 load 입력으로 보내 서버가 4ED7을 생산하게 한다. IPC의 draft와 durable 저장 작업을 혼동하지 않는다.

```text
SELF_READY ── index3 ──> SNAPSHOT_SELF_DRAFT
  └ current SELF f1 보존, 요청 scope f2 조회/선택
      └ server 4ED7(hex(SELF f1), hex(selected f2))
          └ native parse → 4302F0 → UI thread reload → COMPANION_READY

COMPANION_READY ── Save ──> capture(COMPANION, 이 문서의 f2 snapshot)
  └ LOCAL IPC → companion store durable → 동일 요청 saved

COMPANION_READY ── index3/닫기 ──> SNAPSHOT_COMPANION_DRAFT
  └ full 4ED7(SELF f1, SELF draft/saved f2) → native/UI 복원 → SELF_READY/닫기
```

full4ED7의 f1은 **서버의 오래된 계정 sidecar가 아니라 전환 직전 최신 SELF CharacterConfig snapshot**이다. 동료 모드에서도 f1의 다른 UI 설정은 자기 소유로 유지한다. CharacterConfig f7의 별도 ATS 표현은 SELF 원문을 보존하고 비ATS field의 실제 변경은 유지한다. 이 혼합에 필요한 serialize/delegate ABI는 아래 미확인 항목이다. f1/f2 root를 무조건 같은 동료 문서로 갈아끼우지 않는다.

Save 실제 원 invoke는 **`8F6450..8F769C`**다. wrapper `8F76C0`의 vtable `120E930`+10으로 호출되고, UI 값을 model에 복사한 뒤 **`8F7552` enum2 → `8F7569→436900`(ATS+1A8 delegate)**를 알린다. Config **`104EA0..10530E`**는 pre-save 뒤 global `163AFA0/163AF78`을 `DF01F0`→`1061C0`으로 직렬화·변환하고 cache `+258/+278`을 비교한다. **`1051AA→27D620`**이 4ED6 송신 callsite다. 즉 Save wrapper만 교체하면 이후의 지연 저장·autosave까지 해결되는 구조가 아니다.

권고 구현은 세 경계를 함께 연결한다.

- **UI Save wrapper:** 창 instance·scope·문서 snapshot을 캡처하고 원 UI→model 복사를 재사용한다. companion은 actual serializer 결과의 f2를 IPC로 보낸다. Save하지 않았는데 snapshot을 durable로 처리하지 않는다.
- **Config serializer/pre-save:** `42EBE0`이 model에서 ATSConfig를 채우는 시점과 actual 직렬화 결과를 결속한다. 변환을 추측해 합성하지 않는다. unchanged Save는 실제 snapshot과 저장 상태가 같은지로 구별하며 packet 부재/timeout을 성공으로 보지 않는다.
- **원 4ED6 boundary/cache:** companion 편집 중에도 원 socket에는 **SELF CharacterConfig + SELF ATSConfig**만 저장한다. f1의 legacy ATS f7까지 포함해 SELF를 유지한다. cache `+258/+278`도 실제 SELF 전송값과 맞춰 companion 값이 다음 autosave에 새 변경으로 유출되지 않게 한다. companion 저장 bytes와 자기 메시지를 둘 다 전체 opaque last-request에 쓰지 않는다.

`Save enum2→Config dirty/저장 스케줄`의 마지막 구독자, 동기 snapshot/flush의 정확 ABI, cache update의 전후 위치는 아직 닫지 못했다. **위 세 지점은 구현할 연결이며 검증된 hook 코드가 아니다.** 이를 구현 전에 좁은 정적 caller 조회로 확정하고 실제 한 번의 Save에서 확인한다. f3 대안을 쓰더라도 이 model/cache 문제는 남는다.

기존 Save가 진행 중이면 해당 snapshot의 결과를 받은 뒤 전환한다. 실패 때는 그 scope/draft와 원오류를 유지하고 라벨을 새 대상 완료로 바꾸지 않는다. 4ED7 socket 전송→native parse→UI reload가 끝나기 전에 새 Save를 허용하지 않는다. 기존 dispatch에서 전환 하나를 순서대로 완료하며 타이머 지연으로 완료를 대신하지 않는다. 닫힘/로그아웃 후 도착한 작업은 새 창에 적용하지 않는다.

### 4.3. 원 ATS 실행과 편집 모델

현재 population은 같은 ATSSubsystem saved/working model을 사용한다. 동료 편집 blob을 로드하면서 실행 중 자기 ATS가 이를 읽지 않는다는 증거는 없다. **1차 설계는 자기 ATS가 정상 OFF인 상태에서 동료 설정을 편집**하는 범위로 둔다. OFF 판별은 기존 ATS state/delegate를 재사용하며 새 준비 상태를 위조하지 않는다. 원 실행을 몰래 중단시키지 않는다.

companion scope의 Play는 원 `4F36/4F38`에 연결하지 않는다. Save는 설정 저장만 한다. Alt-G/행동창 On/Off 등 다른 진입도 같은 scope adapter에서 다루어야 하므로 Play 버튼만 숨기는 것으로 끝내지 않는다. SELF 복원 뒤에는 원 자기 실행 의미로 돌아간다. 실행 중 편집까지 확장하려면 별도 shadow edit model과 원 runtime model을 분리하고 UI model receiver를 교체하는 후속 구현이 필요하다. 동료 AI 실제 설정 소비·시전·시간 정책은 이번 UI 설계의 완료 주장에 포함하지 않는다.

### 4.4. 서버 모듈과 기존 코드 경계

향후 구현 파일은 예를 들어 `ats_config_codec.py`(원문 변환), `ats_config_store.py`(캐릭터·scope별 저장), `world_feature_ats_config.py`(선택적인 world 진입/종료 연결)로 나눈다. 이들은 **이번에 생성한 제품 파일이 아닌 설계상 이름**이다. store는 SELF CharacterConfig, SELF ATSConfig, COMPANION ATSConfig와 원문 unknown을 분리한다. 기존 account opaque sidecar를 새 형식으로 덮거나 소급 변환하지 않고, 기존 데이터의 캐릭터 귀속이 불명확하면 임의로 모든 캐릭터에 복제하지 않는다. companion 최초값도 의미 미확인 field를0으로 합성하지 않고 원 UI의 실제 설정 snapshot을 출발점으로 삼는다.

world 기능 모듈을 쓰면 `FEATURE_MODULES`에 한 줄 등록하고 자신만의 이름을 사용한다. 다른 모듈 ctx 메서드 직접 호출이나 기존 METHODS 덮어쓰기는 하지 않는다. **4ED6는 현재 broker의 별도 route이므로 world 모듈 한 줄만으로 interception이 되지 않는다.** 기존 route는 SELF 저장으로 유지하고 companion IPC는 선택적 bridge/control service가 맡는다. 기존 host에서 인증된 선택 캐릭터와 frame 송신을 제공받는 경계가 필요하며 그 연결이 현재 있는 것처럼 주장하지 않는다. 공통 코어에 새 필수 호출을 넣지 않고 adapter가 없으면 기존 서버·다른 기능·원 settings 동작이 유지되게 한다. 이번 금지 파일은 수정하지 않았다.

## 5. 리소스 공급과 DLL 빌드 설계

기존 [PET_WINDOW_EDIT_EVIDENCE 1장](PET_WINDOW_EDIT_EVIDENCE.md)의 root-mount/raw 결론을 그대로 재사용한다. provider assets 폴더를 수정하는 것만으로 실행 클론에 공급되지는 않는다. 기존 provider/materialize 도구는 원문과 다른 source/destination을 거절하므로 편집본을 그 검증 경로의 원본으로 가장하지 않는다.

- 원본 pack·추출 원문을 보존하고 **별도 편집용 실행 사본의 raw CSB**를 실제 요청 root 아래 공급한다. `ATSLayoutScene.csb`의 논리 참조는 `ATS/ATSLayout.csb`, 추출 경로는 `data_u/ATS/ATSLayout.csb`다. 실제 raw 상대 경로는 root resolver가 받은 요청에서 정하며 두 경로가 항상 같다고 가정하지 않는다. module root→raw open→실패 시 pack fallback이라는 기존 계보를 사용한다.
- native resolver 후보는 **`B74A20`**이다. `/memory/`, `/pack/` 우선 prefix와 선택된 일반/Purple 레이아웃을 확인해야 한다. 현재 raw 우선 소비·런타임 무결성·cache/hot reload는 UNKNOWN이다.
- 1차는 원 CSB의 `Bt_Help`를 유지한 **instance-local Text/callback adapter**로도 시작할 수 있다. 수정 CSB가 필요하면 기존 버튼의 위치·폭·문구만 구조를 보존해 바꾼다. FlatBuffer의 가변 길이 문자열을 hex로 덮지 않는다.
- 전역 string.csv의 기존 도움말 ID를 교체하면 다른 창과 locale까지 바뀔 수 있다. `나 / 동료` 현재 상태는 해당 instance의 Text로 갱신하는 편이 적합하다. 파일을 고쳐 놓았다는 사실은 열린 창 갱신의 증거가 아니다.

빌드는 [ui-open-bridge/build.cmd](../ui-open-bridge/build.cmd)의 기존 **MSVC x64 DLL + asm/object + 로컬 include 고정** 방식을 재사용한다. 향후 후보에는 별도 `ats_toggle_bridge.hpp`를 두고 own-login-bridge 계열의 기존 UI thread dispatch/종료 경계에 선택적으로 연결한다. 이번에는 header·C++·build.cmd·DLL·핀을 고치거나 빌드하지 않았다. 후보 DLL은 별도 출력으로 만들고 기존 `own-login-bridge-dg49.dll`과 manual 핀 대상은 보존한다.

기존 [ui_open_bridge.hpp](../../../tools/local_original_session/native/ui_open_bridge.hpp)는 `LC-Owned-UIOpen-v1` 등록 메시지와 `WH_GETMESSAGE`에서 Python→DLL 명령을 UI thread로 전달한다. 현재 명령은 마법/스탯/펫/미지원 hotbar이며 ATS나 DLL→서버 대상 전환 명령은 없다. 현재 result 파일은 반환 상태 보고이지 ATS control API가 아니다. 이 기반을 확장해야 하며 callback 반환을 창 표시·저장 성공으로 기록하지 않는다.

## 6. 2차: 기사 접속 중 동료 편집

1차는 같은 법사로 접속하므로 기존 학습 마법·가방의 drag payload를 이용한다. 2차는 서버가 ATS f2를 보내는 것과 별개로 **동료의 learned-spell/inventory view → drag producer → slot drop consumer**를 연결해야 한다. 기사에게 없는 마법 아이콘이 어디에서 만들어지는지부터 해결한다. 기사 전역의 직업·학습·가방을 법사 것으로 바꾸거나 UID/소유권을 위조하지 않는다.

기존 근거로는 ATS getter **`644B0`는 current-player getter가 아니라 ATSSubsystem getter**다. `8EC100`이 읽는 `ATS+450`은 등록 vector이며 다른 캐릭터 마법 drop 허용의 증거가 아니다. `8E6970 → C06300`은 visible 탭의 입력 전달이다. `8EF3A0`의 UIDropSlotComponent 등록, callback `8F2A00`의 payload kind2/`4FFCE0`, PC callback **`8FCD40` → SlotNode `+808/+810` → `B03960`**, `8FCB00 → 95C4C0`을 다음 조사 seed로 재사용한다. 기존 .pdata 일부가 분기 끝까지 덮지 않으므로 선택 dump를 완전한 함수로 취급하지 않는다.

별도 동료 view에 원 SlotShortcut 형식의 payload를 생산하고 동일 drop handler를 호출하는 adapter가 후보다. 아이템의 instance UID/템플릿/실소유·수량, 주문 ID/실학습을 대상 캐릭터와 연결하는 시점은 2차에 확정한다. 회복칸 힐 마법 허용, 직업 제한 predicate, 버프18 hard limit은 현재 UNKNOWN이며 도움말 문구나 visual grid만으로 거절/정원을 확정하지 않는다.

## 7. 구현 순서와 검증 범위

이 절은 **후속 구현 시의 순서**이며 이번에 실행한 결과가 아니다. 탭 분리로 바꿀 때도 `EditTarget`, character별 두 ATS blob, Save snapshot, 4ED7 apply를 UI 배치와 분리해 재사용한다. index3 adapter만 별도 두 버튼/탭 adapter로 교체하면 된다. 저장키에 화면 탭 인덱스를 넣지 않는다.

| 순서 | DLL / 서버 / 리소스 작업 | 그 단계에서 확인할 것 |
|---|---|---|
| 1 | 오프라인 blob decoder/encoder와 필드 보존; 저장키 `(account, permanent_character_id, self/companion)` 설계 | unknown/반복/presence 보존, 두 대상 저장 분리. 빈 설정을 임의 기본값으로 채우지 않기 |
| 2 | 별도 후보 DLL에서 owning ATS instance 획득, index3 callback adapter와 현재 대상 라벨 | 기존 세 내용 탭·원 입력·닫기·재열기 유지. callback 중복/해제·instance 재생성 확인 |
| 3 | LOCAL control IPC, 서버 조회→4ED7→UI apply 완료 전달 | 응답 전에 대상 라벨 확정하지 않기. 대상 캐릭터·scope·실제 model/화면이 일치 |
| 4 | Save click의 scope/snapshot 결속과 자기 4ED6 보존 | 동료 저장이 자기 f1/f2를 덮지 않음. autosave·Quit·저장 실패·전환 연타 포함 |
| 5 | 필요할 때만 편집용 raw CSB 공급 | 실제 file open 경로·일반/Purple·layout 재생성 뒤 문구/클릭 영역 확인 |
| 6 | 정상 접속→법사 선택→월드 진입 후 자기/동료 전환·각 Save→닫기/재접속 | 실제 원 입력·4ED6/IPC·저장·4ED7·열린 창 reload·복원. 이후 동료 실행 소비는 별도 단계 |

화면 검증은 사용자의 포커스·전역 입력을 건드리지 않는 기존 **owned non-input desktop/Job의 헤드리스 원본 스크린샷**을 사용할 수 있다. 실제 게임·포트 실행은 시험 worker 하나가 순차 소유한다. 이번에는 스크린샷도 생성하지 않았다. 정상 로그인·캐릭터 선택·월드 진입과 앞 응답을 확인한 순서로만 정식 패킷 판정을 한다. 원 callback 직접 호출·합성 blob 단위시험은 개발 확인이며 원본 화면/입력 PASS가 아니다.

위험에 맞춘 최소 실행 항목은 다음과 같다.

1. 자기 A/동료 B를 서로 다른 슬롯·조건으로 저장하고 각 전환/재열기/재접속에서 분리되는지 확인한다. 편집 중 dirty 상태와 Save하지 않은 변경은 대상별 draft로 유지하거나 사용자에게 명확히 표시한다. 전환을 암묵 Save로 만들지 않는다.
2. 법사 마법·아이템의 실제 drop→Save→blob field→재로딩된 슬롯을 잇는다. 슬롯 ID를 넣었다는 사실을 실학습·실소비·동료 AI 효과의 증거로 확대하지 않는다.
3. 저장과 전환 연속 클릭, 서버 응답 지연/실패, 원본 autosave/Quit를 한정 확인한다. 실패 시 현재 대상/미저장 draft를 남기며 다른 대상 저장을 성공으로 표시하지 않는다.
4. 창 닫힘·재생성·로그아웃·DLL 종료에서 callback, native string/protobuf 객체, retain/release, IPC 작업을 원 소유 경계에서 정리한다. raw instance 포인터를 다음 세션에 재사용하지 않는다.
5. 원 ATS 실행 모델과 편집 모델의 공유, Play/Alt-G/행동16(On/Off)·17(설정) 진입, 동료 보기 종료 시 자기 설정 복원을 확인한다. 편집 Save가 자동사냥 시작/종료나 동료 소환이 되지 않게 한다.

## 8. 이번 검증과 미확인

메인 세션은 worker 요약만으로 완료를 판정하지 않고 새 분석 문서·초안·선정 원명령을 읽었다. 특히 `storage_config_functions.json`의 실제 callsite와 `ui_tab_callback.json`의3명령을 대조했다. Clear 앞 lea 주소를 callsite로 쓴 초안은 **107310/10731C**로 정정했다. REA provider session이나 게임 process를 열지 않았고 기존 reader의 `View`와 Capstone 파일 분석만 재사용했다. 새 REA Evidence ID나 runtime 관측은 없다.

```powershell
python -B -m unittest discover -s work/local_original_session/game-core-prep/ats-toggle-analysis -p test_ats_blob_draft.py -v
```

결과: **8 tests / OK**, exit0. 합성 입력으로 zlib/raw header, 고정 압축 buffer 초과 fallback, 빈값, 수신 hex 대소문자/오류, 길이·stream 오류, unknown/반복/presence 보존, nested slot/float를 확인했다. 실제 native 입력 sample이나 원본 수신 성공으로 확대하지 않는다.

일회성 `python -X utf8 -B -` 읽기 검사로 새 분석 JSON **29개 parse**, Python **3개 AST**, 문서4개의 UTF-8·로컬 링크 **66개 전부 존재**를 확인했다. `git diff --check -- work/local_original_session/game-core-prep/ATS_COMPANION_TOGGLE_DESIGN.md work/local_original_session/game-core-prep/ats-toggle-analysis`도 exit0이다. 이 검사는 새 실행 경로 검사기로 설치하지 않았다. work 산출물이 Git ignore 대상인 점 때문에 diff-check를 내용 검증의 대용으로 쓰지 않았다. 기존 대량 dirty/untracked 제품 파일은 이번 변경에 포함하지 않았고 커밋/브랜치 변경도 없다.

| 질문 | 이번 답 / 남은 최소 확인 |
|---|---|
| 서버가 blob을 읽고 만들 수 있는가 | header/zlib·방향별 hex·tree/wire·원 슬롯 생산자를 확보. 원문 슬롯 roundtrip 초안 있음. Conditional f1=1..6·f2 단위·AND·시각/횟수는 위 정적 근거로 확인. Option f5/f9/f10, Buff f6/f8/f9, 문자열 일부 의미 UNKNOWN |
| 기존 도움말 자리에 전환을 넣는가 | index3 invoke `8F7940` 후보와 label child 확보. patch/trampoline·attach/destruction·실제 Text ABI는 미구현 |
| 열린 창은 다시 읽는가 | 자동 재조회 보장 없음. `8E6A80(true)` saved→working→population 경로 확보. 열린 창 직접호출 부작용·실제 화면은 UNKNOWN |
| Save가 대상별로 안전하게 가는가 | companion IPC + 원4ED6 SELF 고정 설계. dirty scheduling·serializer ABI·f1 legacy ATS/cache 처리의 실제 연결은 미완 |
| 기사 세션의 drop은 어떻게 하는가 | target view 양쪽 adapter와 producer/drop hook seed 기록. 원본 class/learned 허용검사 전체·slot 소유/실소비·서버 spell ID 숫자대응 UNKNOWN |
| 수정 CSB를 읽게 할 수 있는가 | 기존 root-mount/raw 공급 경로 재사용 가능. 정확한 runtime open 경로·일반/Purple 선택·cache·무결성은 실행 확인 필요 |

따라서 이번 완료는 **요청한 정적 설계와 오프라인 초안**이다. 제품 연결·원본 화면·입력·Save 패킷 발생·내구 저장·재접속 복원·동료 실제 소비는 모두 **UNRUN**이다.

## 9. 재사용 근거와 변경 파일

| 근거 | 이 문서에서 재사용한 것 |
|---|---|
| [기존 storage 조사](ats-evidence/storage_findings.md), [Config handler 원문](ats-evidence/storage_config_functions.json), [Save transport](ats-evidence/storage_save_transport.json) | outer 메시지·global·cache·Clear·Save 송신·구형 f7 병존 |
| [BLOB_FINDINGS](ats-toggle-analysis/BLOB_FINDINGS.md), `blob_stage1..5.json`, [imports](ats-toggle-analysis/blob_imports.json) | 변환·압축 import·hex parser·필드/wire·pre-save source |
| [UI_FINDINGS](ats-toggle-analysis/UI_FINDINGS.md), [tab callback](ats-toggle-analysis/ui_tab_callback.json), [reload](ats-toggle-analysis/ui_reload_functions.json), [item writer](ats-toggle-analysis/ui_item_slot_writer.json), [spell identity](ats-toggle-analysis/ui_slot_magic_identity.json) | lookup/capture·전환·목록 수명·옵션 의미·마법/아이템 생산자 |
| [BRIDGE_FINDINGS](ats-toggle-analysis/BRIDGE_FINDINGS.md) | 기존 DLL 빌드·IPC 능력·서버 store·제안 흐름과 한계 |
| [PET_WINDOW_EDIT_EVIDENCE](PET_WINDOW_EDIT_EVIDENCE.md), [기존 ATS 조사](ATS_COMPANION_EVIDENCE.md) | root-mount/raw·locale/공유·기존 UI·프로토콜 계약 |

변경은 **이 설계 문서**와 새 **`ats-toggle-analysis/` 35개 파일**(분석 메모3, JSON29, Python3)에 한정한다. Python3개는 [blob 초안](ats-toggle-analysis/ats_blob_draft.py), [합성 단위시험](ats-toggle-analysis/test_ats_blob_draft.py), 선택 파일 분석 helper `ui_static.py`다. 기존 `ats-evidence/`·제품 소스·핀 DLL은 수정하지 않았다. raw JSON은 선택 정적 원문과 상속 source metadata이며 실행 로그가 아니다.
