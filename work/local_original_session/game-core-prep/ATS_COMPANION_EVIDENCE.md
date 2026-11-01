# ATS 창을 동료 법사 설정에 사용하는 설계 근거

2026-10-27 · **정적 조사만. 제품 구현·원본 실행·접속·패킷 송수신·화면 캡처·커밋 없음.** 이번 직접 요청의 조사 범위만 수행했으며 제품 중지·다른 기능 동결을 해제하지 않았다.

## 결론과 판정 기준

**A(법사로 직접 접속해 설정한 뒤 그 법사를 동료로 사용)를 우선 권장한다.** 현재 캐릭터에 귀속된 원본 ATS 설정을 같은 법사의 영구 character ID에 연결하면 된다. **B(기사 접속 중 법사 설정 편집)는 추가 클라이언트 연결이 필요한 조건부 설계**다. 설정 전송 경로가 있다는 사실만으로 기사 세션의 원본 창이 다른 캐릭터의 가방·학습 마법·설정을 표시하는 것은 아니다.

중요한 의미 차이: 원본 도움말은 **회복 칸을 아이템창의 회복 아이템용**으로 설명한다. 힐 마법을 그 칸에 넣어 주인의 HP 기준으로 시전할 수 있다는 근거는 없다. 원본 ATS는 현재 캐릭터의 자동 사냥이고, 동료가 주인을 치료하는 정책은 별도 LOCAL 동료 정책으로 명시해야 한다. 원본 UI를 사용하더라도 의미를 바꾼 부분은 원본 동작이라고 부르지 않는다.

- **확인[정적]**: 보존 원문·CSB 구조·타입/명령·직접 참조·현재 서버 코드에서 확인했다. 실행 성공을 뜻하지 않는다.
- **추정/설계**: 확인된 입력을 어떤 동료 정책에 연결할지 제안한 것이다.
- **미확인(UNKNOWN)**: 값의 의미·간접 호출·실제 화면·송수신·저장 성공을 확인하지 못했다. 부재나 실패로 단정하지 않는다.

## 기준 원본과 근거 위치

주소는 모두 **RVA**, VA는 `0x140000000 + RVA`다. 원본 CONTROL 신원은 기존 [TARGET_IDENTITY](../../local_server_rea_20261016/TARGET_IDENTITY.md)의 SHA256 `9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`를 승계한다. 읽기 전용 `View`는 기존 복원 record 6개와 `.pdata` 경계를 읽고 Capstone으로 선택 함수만 해석했다. 기존 runner를 실행하거나 원본을 수정하지 않았다. 파생 분석 carrier의 SHA256은 `c822838351d774a2022af434829a36dbd9bee030bf22182b834ca4e8659701a9`; 원본 LC 자체와 동일한 실행파일이라고 주장하지 않는다.

자원은 기존 평문 `C:/Users/Chansol/Documents/Codex/2026-09-07/d-lineage-classic/outputs/decrypted-pack/`를 읽었다. 기존 `work/asset_data_analysis/current/catalog.tsv`에서 ATS CSB·`ats_basic.jsonc`·`behavior_list.jsonc`가 고정 `26.09.29.2001` 묶음과 `identical`인 범위를 재사용했다. `string.csv`는 `changed`이므로 옛 CSV 문구의 현재 동일성을 주장하지 않는다. 일반/Purple 중 실제 선택된 레이아웃은 실행 확인하지 않았다.

이번 조사 근거의 출처는 **로컬 원본 자원·복원 코드·현 서버 코드100%, 신규 외부 웹/공식 API/L1J 조회0%**다. 이는 출처 구분이며 확인된 기능 비율이나 원본 동등성 수치가 아니다. 기존 서버 코드의 L1J/LOCAL 수치는 현 정책으로 인용하고, 새 동료 설계 제안은 별도로 표시했다.

| 근거 | 내용과 경계 |
|---|---|
| [resource_findings.md](ats-evidence/resource_findings.md), [resource_summary.json](ats-evidence/resource_summary.json) | 12 CSB·1289 노드, 도움말 전문·offset·자원 출처. 실행 화면 아님 |
| [resource_trees.json](ats-evidence/resource_trees.json), [resource_nodes.tsv](ats-evidence/resource_nodes.tsv) | 전체 선택 자원 트리 및 펼친 원문 |
| [resource_behavior_ats.json](ats-evidence/resource_behavior_ats.json), [resource_ats_basic.json](ats-evidence/resource_ats_basic.json) | 행동 ID·아이콘, packaged ATS 행동 트리 |
| [ui_layout_vptr_refs.json](ats-evidence/ui_layout_vptr_refs.json), [ui_layout_constructor.json](ats-evidence/ui_layout_constructor.json), [ui_layout_initialize.json](ats-evidence/ui_layout_initialize.json) | ATS 실제 클래스·생성자·버튼 lookup·초기화 |
| [ui2_findings.md](ats-evidence/ui2_findings.md), [ui2_slot_population.json](ats-evidence/ui2_slot_population.json) | 전투8회 native loop, ATS 등록값 바인딩, drop/직업 제한의 미확인 범위 |
| 기존 [REA216](../../local_server_rea_20261016/run216_companion_actor_ats_existing_contract/MAIN_REVIEW.md), [REA278](../../local_server_rea_20261016/run278_ats_ui_native_adapter/source/native/contract.md) | subsystem 및 과거 미확인 경계. 이번 원본 UI identity 확인으로 보완하며 과거 실행 성공을 만들지 않음 |

## 창 구성과 등록할 수 있는 것

`ATSLayoutScene.csb/Scene/ATSLayout`(CSB offset132) → `ATS/ATSLayout.csb`를 확인했다. 후자는 242180B, SHA256 `eca0f7add466f7ece1de9c90d5204aa4ac1ae3a0c5b216448924d866318a7cb7`. `ATSLayout` RTTI type descriptor `0x1670ed0`, vptr `0x120f308`, 생성자 `0x8e3e60`, Initialize `0x8e5f40`; PC 구현의 type descriptor `0x1755e00`, vptr `0x1210e88`, 생성자 `0x8fcfe0`, Initialize `0x8fbfe0`를 연결했다. 생성자에서 `Root.Tab.Bt_Buff/Combat/Option/Help` 및 하단 `Bt_Reset/Save/Quit/Play`, `Tx_Time`을 실제 lookup한다. 이름만 남아 있던 옛 ATS subsystem 자료보다 구체적인 창 근거다.

| 부분 | 확인[자원/도움말] | 미확인/동료 설계 시 주의 |
|---|---|---|
| HP·MP 회복 | 각각 Item01/02, 총4칸. **아이템창** 회복 아이템 드래그, 1번 소진 뒤2번 사용. 도움말 offset53492 | 힐 마법 허용·주인 HP를 기준으로 하는 기능은 확인되지 않음 |
| 기능 아이템 | 6칸. 아이템창의 1단/2단 가속·요리·해독제·호흡물약·변신주문서. 효과 종료/필요 상황에 사용. offset52548 | 정확한 허용 template ID 및 직업별 제한은 별도 |
| 변신 | 등록한 변신주문서와 변신 버튼→목록 외형 선택, 사용 때 적용. offset51580 | 동료 변신 표시·선택 외형 저장 연결 별도 |
| 버프 | **아이템창 또는 마법창**, 효과 종료 후 사용. 모든 아이템/마법을 넣을 수 있는 것은 아님. offset50644 | 6×3 배경과 빈 ListView는 확인. authored Item18개가 있는 구조는 아님; 동적 정원·허용 목록은 native 근거와 구분 |
| 전투 순차 | 마법창→8칸. 전투 때1~8번 순서대로 사용, 마지막 뒤 **해당 몬스터 사망까지 재사용하지 않음**. offset45384 | 무한 순환으로 해석하면 원본 설명과 다름 |
| 전투 조건 | 8행. HP 이상/이하·MP 이상/이하(퍼센트), 시간(사용 후 입력 초), 누적(횟수 후 중단). offset44356 | 각 조건의 대상·조합·단위 변환은 native/화면 확인 필요 |
| Save·Reset | Save는 아이템·마법·설정을 저장, Reset은 등록정보 제거. offset58820 | Reset 후 서버 저장 시점은 callback 추적과 구분 |

사용자가 설명한 HP/MP `80% 이하`는 현재 화면값이며 고정 기본값으로 채택하지 않았다. CSB TextField raw slot5의 `100`도 schema·native 초기 대입을 확인하기 전에는 실행 기본값이 아니다. 자원의 `남은시간: 3일 00시간`은 견본 문자열이다.

추가 native 확인: `0x8ed160`에서 순차 `01.Slot01.Item_{}`를 `0x8ed389 cmp esi,8`, 조건 `02.Slot_{:02}`를 `0x8ede70 cmp ebx,8`로 각각8회 구성/갱신한다. 반면 버프18개 hard limit은 찾지 못했다. ATS 관련 선택 함수의 immediate18 비교가 없다는 결과는 계산된 정원이나 다른 함수의 제한 부재를 증명하지 않는다.

PC/base vtable24개 중 destructor·Initialize 외22개는 같다. `0x8e6970 → 0xc06300`은 visible 탭에 따른 입력 전달까지 확인했으며 item/spell 허용검사로 확정하지 않았다. `0x644b0`는 RTTI로 **ATSSubsystem getter**임을 확인했다. Buff 갱신 `0x8ec100`이 그+450 등록 vector를 읽는 사실을 current-player 가방/학습 목록 제한으로 해석하지 않는다. **회복 슬롯의 실제 힐 마법 거절 및 기사 세션의 법사 편집 제한 predicate는 UNKNOWN**이다. 제한을 확인하려면 마법/아이템 창 drag payload 생산자→실제 drop 소비자를 이어야 한다.

옵션 탭의 실제 자원 항목은 다음과 같다.

- 탐색 범위·사냥 구역 제한(걸음), 아이템 우선, 매너 사냥, 선공 우선. 도움말의 탐색 범위는1~18걸음.
- 획득 무게 제한: 해제/49% 이하/82% 이하. 아데나만 획득: 해제/사용.
- 귀환: 비전투 시간(초), HP 해제/30% 이하/50% 이하, MP 해제/5% 이하/10% 이하, 무게 해제/50% 이상/83% 이상. MP 노드 이름 `Bt_30/Bt_50`과 실제 표시5/10이 다르므로 이름으로 수치를 해석하지 않는다.

도움말 탭은 일반/버프/전투/옵션 설명이다. 별도 `Report` 분기는 CSB에서 visible=false이며 가동시간·처치·경험치·획득/소모 아이템을 포함한다. 실제 보고 탭 노출 조건은 미확인이다.

행동 데이터는 ATS On/Off **행동 ID16**, icon20009/offIcon20010, ATS 설정 **ID17**, icon20009를 가진다. 도움말은 Alt-W 또는 행동창 ATS 설정 더블클릭, 실행/종료는 Play·Alt-G·행동창 ATS On/Off 더블클릭으로 설명한다. `ATSMsgHudLayout`에는 Ico_Play/Ico_Rotate와00:00 Text가 있다. **사용자 화면 우측의 아이콘3개 각각이 어떤 instance/행동인지까지는 확인하지 않았다.**

## 패킷·저장 계약

메시지 이름·typed parser·수신 등록·ATS callback·protobuf schema·실제 송신 인수를 연결한 범위다. **표의 body field 번호는 protobuf 번호**이며 객체 offset·외부 frame header와 다르다. 모든 정수는 wire0(varint), 문자열/bytes는 wire2다. 기존 로컬 서버 frame codec의 opcode와 body 경계를 그대로 사용해야 한다.

### 실행·종료·시간

| 방향/opcode | 원본 메시지 | body field와 정적 확인 범위 |
|---|---|---|
| C→S `0x4F36` | `CS_START_ATS_REQ` | 빈 protobuf. Play 생성자 lambda5의 invoke `0x8f6390`→ATS getter `0x644b0`→`0x42ac10`; 현재 상태 검사 뒤 시작 분기에서 `0x27d620` 송신 |
| S→C `0x4F37` | `SC_START_ATS_ACK` | **필수 f1 enum**, 객체+18/typecard1C91. enum 전체 명칭은 미확인. ATS callback `0x42f110`은 **f1=0**일 때 `0x42ada0(true)`로 가동 상태 변경; 다른 값을 성공으로 취급하지 않음 |
| C→S `0x4F38` | `CS_FINISH_ATS_REQ` | **선택 f1 enum**. 버튼 toggle 종료 경로 `0x42aaf0`은 f1=**4**를 넣음. 이 값의 공식 enum 명칭은 미확인 |
| S→C `0x4F39` | `SC_FINISH_ATS_ACK` | **필수 f1 bool**. callback `0x42f430`은 true일 때 가동 상태false 처리 |
| S→C `0x4F3A` | `SC_FORCE_FINISH_ATS_NOTI` | **필수 f1 closed_enum**. callback `0x42f530` 및 후속 `0x42fce9`에서 상태false 처리. 종료 사유 enum 이름/표시 대응은 미확인 |
| C→S `0x4F45` | `CS_ATS_TIME_CHECK_REQ` | 빈 protobuf. 시간 조회 경로와 송신 인수 확인 |
| S→C `0x4F46` | `SC_ATS_TIME_CHECK_ACK` | **필수 f1 uint32, f2 uint32**. callback `0x42ff90`은 두 값을 ATS+2B0/+2C8의 보호저장 값으로 기록하고+F0 delegate 알림 |
| S→C `0x4F47` | `SC_UPDATE_ATS_TIME_NOTI` | **필수 f1 closed_enum, f2 uint32, f3 uint32, f4 uint32**. callback `0x4300d0`은 f2/f3를 같은 두 시간 슬롯에 반영. f1/f4는 schema에 존재하나 이 callback에서 시간 상태값으로 소비하지 않음 |

`0x293570`의 실제 opcode 등록→함수객체→typed parser→ATS 구독 callback을 따라 대응시켰다. `0x42ac10`은 clock/debounce와 `0x42aa90` 상태 확인을 거쳐 시작/종료를 선택하므로 버튼 클릭마다 무조건 시작 패킷을 보낸다고 설명하면 안 된다. 켜짐/꺼짐 표시·실제 서버 행동 시작은 실행 확인하지 않았다.

시간 소비 `0x42d450`은 두 저장값을 해독한 합을 반환한다. `0x42d310`은 첫 값에서 경과량을 차감하고 음수 잔여를 두 번째 값에 반영하며0으로 clamp한다. **클라이언트가 이 값을 초 단위 잔여량으로 소비한다는 정적 추론**은 `0x42a9ea..0x42aa14`의 경과 clock÷1,000,000,000→차감 및 `0x42aa58`의 차감량×1,000,000,000 기준시각 갱신으로 뒷받침된다. [native_ats_tick_time.json](ats-evidence/native_ats_tick_time.json), [native_clock.json](ats-evidence/native_clock.json) 참조. **두 값의 공식 이름·무료/유료 여부·충전 규칙은 미확인**이다. UI의3일/00:00 견본에서 임의 사용시간 정책을 만들지 않는다. 동료 AI에 ATS 사용시간을 적용할지 역시 새 LOCAL 제품 정책이며 이번에는 결정/구현하지 않았다.

근거: [native_findings.md](ats-evidence/native_findings.md), [native_dispatch_registration.json](ats-evidence/native_dispatch_registration.json), [native_response_schemas.json](ats-evidence/native_response_schemas.json), [native_presence_checks.json](ats-evidence/native_presence_checks.json), [native_play_subsystem.json](ats-evidence/native_play_subsystem.json), [native_stop_and_state.json](ats-evidence/native_stop_and_state.json), [native_time_request.json](ats-evidence/native_time_request.json). 각 파일의 원행 주소·필수 presence 검사 및 schema를 함께 읽는다.

### 설정 Save·초기 로드·Reset

**서버 설정 저장 경로는 존재한다. 로컬 파일에만 저장한다고 결론낼 수 없다.** 다음의 확인 단계를 구분한다.

1. Save 버튼 lookup `0x8e5134`→함수객체 wrapper `0x8f76c0`→vptr `0x120e930`의+10→**실제 invoke `0x8f6450..0x8f769c`**다. 바로 뒤 함수 `0x8f7710`을 Save body로 오인하지 않는다. invoke는 UI 값을 ATS model로 옮긴 뒤 `0x8f7552`의 enum2를 ATS+1A8 delegate에 `0x8f7569 → 0x436900`으로 알린다.
2. ATS PostInitialize `0x429d50`은 Config getter `0x11b7f0`의 loaded delegate(+18)에 `0x4302f0`, pre-save delegate(+D8)에 `0x42ebe0`를 등록한다. `0x42ebe0`은 ATS+370/+390의 목록 및+590..+5BC의 옵션을 **ATSConfig_ATSOptionSection/ATSConfig_ATSOption** 객체에 쓴다. 이 객체를 CharacterConfig의 동일 이름과 비슷한 section으로 곧바로 간주하지 않는다. 별도의 `CharacterConfig_ATSOptionSection`과 CharacterConfig root **field7(+48)** 직렬화도 확인했으며 두 표현 사이의 변환은 구분해서 추적해야 한다.
3. Config 저장 `0x104ea0..0x10530e`는 전역 `0x163afa0`(**CharacterConfig**)와 `0x163af78`(**ATSConfig**)를 각각 `0xdf01f0`으로 직렬화하고 `0x1061c0`으로 변환해 문자열2개를 만든다. cached+258/+278과 비교해 변경 시 `CS_SAVE_SETTINGS_REQ` vptr `0x11ef858`을 구성하고 `0x10519c`의 opcode **`0x4ED6`**을 `0x1051aa → 0x27d620`으로 전송한다. **f1=CharacterConfig 변환 결과, f2=별도 ATSConfig 변환 결과**이며 AccountConfig로 확인한 것은 없다.
4. **S→C `0x4ED7 SC_CLIENT_SETTINGS_NOTI`**는 등록 `0x2957a9`→vtable `0x11a78b8`의+10=`0x2fea50`→`0x319ec0`→typed parser `0x2b0fb0`로 연결된다. 실제 Config handler는 `0x1067a0..0x108567`다. ATS `OnCharacterConfigLoaded` 문자열·loaded callback도 있다. 설정을 S→C로 공급하는 경로가 존재하며, 타캐릭터 설정 지정 기능이나 서버 내구성의 증명은 아니다.

| 방향/opcode | 설정 메시지의 확인된 외부 body |
|---|---|
| C→S `0x4ED6 CS_SAVE_SETTINGS_REQ` | **f1·f2, wire2 길이 구분 데이터**, 객체+18/+20의 C++ string 저장소. serializer `0x765570`이 두 필드를 `0xf7060`으로 기록. 필수검사 `0x765790`은 **f1 presence**를 요구하며 f2 presence는 요구하지 않음 |
| S→C `0x4ED7 SC_CLIENT_SETTINGS_NOTI` | **f1·f2, wire2 길이 구분 데이터**, 같은+18/+20 저장소. serializer `0x765890`과 typed parser로 확인. 필수검사 `0x765ac0`은 항상true로 두 field presence를 요구하지 않음 |

`0xf7060`은 `(field_number << 3) | 2` tag를 생성한다. C++ string 저장소라는 사실만으로 내부를 UTF-8 JSON이나 평문이라고 가정하지 않는다. **parser가 field 생략을 허용해도 정상 초기 설정을 빈 값으로 만들어도 된다는 뜻은 아니다.** 확인되지 않은 character ID field를 추가해서는 안 된다.

확인한 내부 구조는 **ATSConfig root f1→ATSOptionSection**, section **f1=string 저장소(의미미확인), f2=ATSOption**, ATSOption **f1/f2/f3=nested message**다. serializer는 각각 `0x101d80`, `0x101940`, `0x101540`. child의 정확한 타입/옵션별 필드 이름까지는 미확인이다. 병존 CharacterConfig root f7에도 별도 `CharacterConfig_ATSOptionSection`이 있고 BuffData/BattleData/OptionData/ConditionalSpell RTTI가 있으나, 별도 ATSConfig 타입과 혼합하지 않는다. 두 표현의 복사 bridge는 미확인이며 **현재 pre-save→ATSConfig→4ED6 f2 저장 경로에 그 복사가 필수인 것은 아니다.**

수신 `0x1067a0`에는 역변환 `0x1063e0` 후 `0xdf0040`으로 CharacterConfig/ATSConfig 전역에 파싱하는 경로가 있다. SC f1/f2 각각의 세부 분기→두 parser 대응과 변환/역변환 알고리즘은 완전히 닫지 못했다. 실제 초기 응답 구현 전 필요한 최소 추가 분석은 `0x1061c0/0x1063e0`의 변환과 ATSOption3개 child serializer·필드 의미다. [storage_ats_root_serializer.json](ats-evidence/storage_ats_root_serializer.json), [storage_ats_nested_serializers.json](ats-evidence/storage_ats_nested_serializers.json), [storage_required_presence.json](ats-evidence/storage_required_presence.json), [storage_globals.json](ats-evidence/storage_globals.json) 참조.

**열린 연결:** Save의 enum2 delegate부터 Config dirty/즉시·지연 저장 함수까지의 최종 bridge는 아직 닫지 못했다. 따라서 “Save 클릭 즉시4ED6 발생”은 미확인이다. Reset 도움말과 실제 wrapper는 찾았지만 초기화 범위·Reset 단독으로 저장 전송하는 시점은 미확인이다. 내부 blob의 전체 schema·ATS 항목명의 직렬화 대응, 설정 저장 ACK, 정확한 로컬 파일 경로·IO는 미확인이다. 서버 저장 경로의 존재가 로컬 cache/파일의 부재를 뜻하지 않는다.

`0x42ebe0`은 `.pdata`가22B로 잘라 표시하는 함수다. 추가 bounded decode `0x42ebe0..0x42f103`(1315B/336명령, 마지막ret)을 보존했다. 자동 함수 경계만으로 pre-save가 없다고 판단하지 않는다. 근거: [storage_findings.md](ats-evidence/storage_findings.md), [storage_save_invoke.json](ats-evidence/storage_save_invoke.json), [storage_save_transport.json](ats-evidence/storage_save_transport.json), [storage_ats_post.json](ats-evidence/storage_ats_post.json), [storage_pre_save_raw.json](ats-evidence/storage_pre_save_raw.json).

## 현재 동료 AI에 연결할 때의 차이

현재 코드의 근거는 [ai_policy.json](../../../tools/local_original_session/data/companion/ai_policy.json), [companion_ai.py](../../../tools/local_original_session/companion_ai.py), [world_feature_companion.py](../../../tools/local_original_session/world_feature_companion.py), [world_companion.py](../../../tools/local_original_session/world_companion.py), 물약 소비는 [world_feature_trade.py](../../../tools/local_original_session/world_feature_trade.py)다. 코드의 존재·연결만 확인했으며 이번에 실행 시험하지 않았다.

| 현재 확인한 동작 | ATS 연결 시 필요한 작업 |
|---|---|
| `CompanionRecord`(:54~)에 법사 character_id·owner_character_id·learned_spells·이동/전투 모드·support_enabled·절대량 mp_reserve가 있음. 저장은 기존 캐릭터 저장 옆 `companion.json`(:486~) | HP/MP 비율·회복 슬롯 순서·버프 목록·공격 순서/조건·옵션은 캐릭터별 설정 schema가 새로 필요. actor UID/generation을 영구키로 쓰지 않음 |
| JSON은 SOURCE_ONLY/runtime_enabled=false라 적혀 있지만 `_companion_initialize`(:338/358/384)는 `SL_COMPANION=1`에서 정책을 읽고 `CompanionMagic`에 전달. 해당 JSON 플래그 검사는 없음 | 표기와 실제 연결을 구분. 단순히 “현재 미연결”로 설명하면 틀림. 이번에는 수정하지 않음 |
| `CompanionMagic.eligible`(:104~)은 `record.learned_spells`를 검사. 직접 법사의 마법서 학습은 `world_feature_magic.py:1006~`의 `_world_magic.state(uid).learned`를 변경 | 읽은 참조 범위에 두 학습 목록의 연결 writer가 없음. ATS Save 자체가 학습권한이 될 수 없으며 같은 법사의 학습 권위를 연결해야 함 |
| 현재 Heal은 **주인**, Shield는 **법사 자신**, Energy Bolt는 현재 적. 법사 자신의 MP 차감·저장(:227~/257~) | 원본 self ATS의 회복·버프 대상을 그대로 주인 지원으로 옮기면 의미가 달라짐. 자기 물약·주인 힐·자기/주인 버프를 별도로 명시 |
| `CompanionAI.step:234~`에서 물약을 시도한 뒤 마법 정책을 실행. `world_feature_trade.py:219~`는 실제 법사 가방 수량을 CAS로 차감 | 현재 빨간 물약14는 동료 HP 임계값, 파란 물약492는 MP 조건에서600초 회복 효과. 즉시 MP 회복으로 바꾸지 않음. 2칸 우선순위와 선택품목 소비는 아직 없음 |
| 전역 LOCAL 정책은 주인·동료 비상 HP0.35, 해제0.55, MP 회복0.4, 힐2회분 reserve. 기존 `support_enabled`는 물약 시도를 끄지 않음 | 사용자가 저장한80% 등을 적용하려면 기존 전역 기본값 위에 캐릭터별 설정을 읽어야 함. ATS MP%와 절대 mp_reserve는 다른 단위 |

## A/B 설계 판단과 이후 구현 단계

이 절은 제안이며 이번에 구현하지 않았다.

| 설계 | 가능성 | 필요한 계약 | 막히는 지점 |
|---|---|---|---|
| A. 법사 직접 접속→ATS 편집·Save→그 법사가 동료일 때 적용 | **우선 권장, 원본 저장 경로를 재사용하는 조건부 가능** | 인증된 현재 법사 ID에 설정 저장·조회, 같은 ID의 동료 AI가 정규화 설정을 읽음. Save와 Play를 분리 | 원본 회복칸은 물약 중심. 주인 힐 대상 정책은 별도. 직접 학습과 동료 학습 권위 연결·각 설정 실제 소비·저장/복원 미구현 |
| B. 기사 접속 상태→법사 설정을 ATS 창에 내려 편집 | **서버만으로 무수정 지원 가능하다고 확정할 수 없음** | 편집 대상 영구 character ID 선택·소유관계, 대상의 설정/학습/가방 view, Save를 대상 ID로 매핑, 종료 때 기사 view 복원 | 원본은 현재 캐릭터 설정/Subsystem을 사용. 기사 spell/item 목록으로 법사 설정을 편집할 수 있는지, 다른 target ID wire field·독립 view model은 미확인. 설정 S→C가 있어도 타캐릭터 편집 API 증명은 아님 |

A의 패킷 계획은 로그인/캐릭터 선택 뒤 `4ED7(f1,f2)`로 그 법사의 저장 설정을 공급하고 `4ED6(f1,f2)` 요청을 같은 인증 캐릭터에 저장하는 것이다. **내부 blob 형식과 ATS 변환을 먼저 확인해야 실제 응답을 만들 수 있다.** 직접 법사의 ATS Play를 지원한다면 `4F36→4F37`, 종료 `4F38→4F39`, 시간 `4F45→4F46` 및 `4F47/4F3A` 소비도 별도 완결해야 한다. 이 메시지들을 동료 실행용 명령으로 자동 전용하지 않는다.

B의 외부 설정 메시지에서도 확인한 것은 두 blob뿐이며 **목표 법사 ID field는 확인되지 않았다**. 별도 편집 context 없이 기사에게 법사 `4ED7`을 보내는 것은 기사 Config/cache와 저장 대상을 섞을 수 있다. 법사 선택·view·Save 라우팅·닫기 복원이 준비되기 전에는 서버에서 blob만 교체하는 방식을 권장하지 않는다. 기사 자신의 마법창에서 법사 마법을 가져올 수 없다는 원본 predicate를 찾은 것은 아니므로, 이를 확정된 불가능 사유로 쓰지도 않는다.

1. 원본 ATS의 Save·초기 설정·시작/종료·시간 메시지를 각각 기존 decoder/router에 대응시킨다. 원본 필드와 LOCAL 동료 저장 schema를 구분하고, 알 수 없는 설정 항목도 원문 보존 여부를 정한다. 이번 조사 helper를 요청 경로의 새 검사기로 넣지 않는다.
2. A부터 캐릭터 ID별 설정을 저장·복원한다. **설정 Save가 자동 사냥 시작을 의미하지 않도록** 하고, 직접 법사 조작 중의 ATS와 소환된 동료 AI 중 누가 행동을 수행하는지 분리한다. 같은 법사 동시 직접 접속/소환 수명은 기존 선택·dismiss 경로를 따른다.
3. 동료 정책으로 정규화한다. 자기 HP/MP 물약2칸, 자기 유지 버프, 현재 적 공격 순서·조건부터 매핑하고 주인 회복 마법/대상은 명시 LOCAL 설정으로 설계한다. UI에 원래 없는 의미를 조용히 덧씌우지 않는다.
4. 학습·가방·MP 권위를 같은 법사 ID로 연결한다. 설정에 등록된 주문이 학습/레벨/MP/재료 조건을 만들어내지는 않는다. 실제 수량·MP 소비와 현재 버프·cooldown·대상 유효성은 기존 실행 경로에서 처리한다.
5. 새 기능 모듈에서 캐릭터별 설정을 읽는 선택적 연결을 사용한다. 다른 기능의 ctx 메서드 직접 호출·공통 코어 새 필수 호출·같은 이름 METHODS 덮어쓰기를 추가하지 않는다. 모듈을 FEATURE_MODULES에서 빼면 기존 서버와 동료 기본 동작이 유지되도록 한다.
6. B는 A 저장/실행 연결 뒤 검토한다. 원본 창이 기사 자신의 가방·마법만 받으면 별도 client adapter/view 연결이 필요하다. 그 경우 현재 기사 설정과 동료 설정이 섞이지 않게 편집 대상·해제 수명을 설계한다. 원본 wire에 확인되지 않은 character ID 필드를 임의로 붙이지 않는다.
7. 구현을 별도로 승인한 뒤 원본 입력→Save→재접속 복원→소환→설정대로 선택·실소비·대상 효과·종료를 확인한다. 이번은 STATIC_ONLY이며 화면·플레이·원본 동등성 PASS가 아니다.

## 사용자가 원본 화면에서 확인할 것

이번 조사에서는 게임을 실행하지 않았다. 아래는 이후 사용자가 확인할 최소 항목이다.

- 법사 마법창의 힐을 HP 회복칸에 드래그했을 때 등록되는지/거절되는지. 버프칸에 힐을 넣을 수 있어도 그 대상·조건을 회복칸 동작과 혼동하지 않기.
- 전투탭8칸의 순서·각 조건 선택값, 마지막 주문 이후 같은 몬스터에게 반복하는지. HP/MP 조건이 누구의 수치인지.
- Save 후 창 재열기·캐릭터 재접속에서 슬롯·HP/MP%·옵션이 유지되는지. Reset 직후 닫기와 Reset→Save의 차이.
- Play/Alt-G/우측3아이콘 각각의 기능, 시작·중단·시간0 때의 버튼/아이콘/메시지 변화. 사용시간 종류별 표기와 차감 단위.
- 기사로 접속했을 때 법사 전용 마법을 어떤 출처창에서 가져올 수 있는지. 원본 UI에 다른 캐릭터 선택 기능이 있는지. 없으면 B의 별도 view 연결이 필요함.

## 검증·미확인

조사 자료 **JSON116개 파싱, 조사 helper5개의 AST, 문서 로컬 링크37개**를 확인했다. 오류0·누락 링크0이며 제품 시험은 실행하지 않았다. 검증 명령은 다음과 같다.

```powershell
python -c "from pathlib import Path; import json,ast,re; d=Path('work/local_original_session/game-core-prep'); t=(d/'ATS_COMPANION_EVIDENCE.md').read_text(encoding='utf-8'); js=list((d/'ats-evidence').glob('*.json')); py=list((d/'ats-evidence').glob('*.py')); [json.loads(f.read_text(encoding='utf-8-sig')) for f in js]; [ast.parse(f.read_text(encoding='utf-8-sig')) for f in py]; missing=[s for s in re.findall(r'\]\(([^)]+)\)',t) if not s.startswith(('https:','http:')) and not (d/s).exists()]; print(len(js),len(py),missing); assert not missing"
```

결과: `116 5 []`. 원본 실행·접속·드래그·패킷 송수신·실제 설정 파일 IO·화면 검증은0이다. REA는 파생 carrier open/close를 수행했으나 Ghidra 문자열 조회가 구조화된 결과를 주지 않아 새 REA Evidence로 채택하지 않았다. 본문 원함수 근거는 보존 복원 record의 선택 명령과 Capstone 정적 분석이다.

남은 핵심은 **설정 blob 변환/옵션별 field 의미, Save→실제 저장 시점, 정확한 로컬 파일 경로, drop 허용검사·회복 힐 허용, 버프18 정원, 우측3아이콘 각각의 identity, B의 타캐릭터 view/저장 대상, 실제 화면·저장·소비**다. 다음 조사에는 이 입력만 좁혀 재사용하며, 미확인 때문에 임의 필드·성공 응답·준비 상태를 만들지 않는다.

변경은 본 문서와 `ats-evidence/`의 조사 원문·helper에 한정했다. 제품 파일·핀·저장·manual 프로필·ACTIVE_TASK는 수정하지 않았다. 커밋은 없다.
