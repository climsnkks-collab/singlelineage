# 동료를 원본 파티 창에 표시하는 계약

2026-10-28. **조사·문서만 작성. 게임·서버·포트·화면 캡처·live attach·패킷 송신 없음. 제품 코드·원본·저장·프로필·ACTIVE_TASK·큐·핀 수정 및 git commit 없음.** 일반 제품 중지/동결을 해제하지 않는다.

**원본 파티 창에 자율 actor인 SoloMage의 HP/MP를 표시할 정적 경로가 있다. 초대 수락 UI를 거치지 않은 목록 수신에서도 창을 여는 경로가 확인됐다. 실제 화면과 정상 원 서버 payload는 미확인이다.** 목록의 종류, 멤버 식별 키, 초기 상태 갱신을 맞춰야 하며 단순히 이름/UID 두 개를 보내는 계약은 아니다.

사용자 결정은 [COMPANION_DESIGN_DECISION.md](COMPANION_DESIGN_DECISION.md)의 **머리 위 HP바 + 원본 파티 창, 장래 여러 직업/여러 동료**를 따른다. 이번 결과는 파티 창에 관한 것이다. 머리 위 HP바의 미완 계약은 [COMPANION_DISPLAY_EVIDENCE.md](COMPANION_DISPLAY_EVIDENCE.md), [MOB_HPBAR_EVIDENCE.md](MOB_HPBAR_EVIDENCE.md)에 그대로 남는다. 파티 창 성공을 머리 위 HP바 성공으로 합산하지 않는다.

## 1. 근거와 판정 경계

`R/`=`work/local_server_rea_20261016/`, `T/`=`tools/local_original_session/`, `J/`=`D:/SingleLineageRef/l1j-en-classic/src/l1j/server/server/`. 주소·offset은 **16진수 CONTROL RVA**다. 현재 프로세스 VA나 packed LC.guard.exe 파일 offset이 아니다.

- 원본 기준: `26.09.29.2001`, 상속 CONTROL SHA256 **`9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`**. 기존 복원 `recovery.json`/`selector_0_record_N.bin`과 `.pdata`/Capstone reader를 파일 전용으로 재사용했다. 현재 disk/live 바이너리와의 동일성을 새로 주장하지 않는다.
- REA 스킬 적용. MCP `binary_session({})`는 `open=false`, 위 해시로 `get_evidence_bundle(detail=summary)`는 retained record **0**. target을 새로 열거나 닫지 않았고 새 Evidence ID도 없다. 아래 새 정적 판독은 원문 위치·getter/schema/함수 RVA와 재현 명령으로 남긴다.
- **확인**은 저장 원문·이번 정적 판독/소비 연결, **추정**은 연결에서 도출한 설계 판단, **LOCAL**은 후속 서버 정책 제안, **미확인**은 정상값·전체 연결·실행 근거가 없는 범위다. 정적 확인은 화면 PASS가 아니다.

| 근거군 | 자료와 범위 |
|---|---|
| O1 원본 패킷 | [run406 protocol-types.json](../../local_server_rea_20261016/run406_companion_equipment/appearance/protocol-types.json:570)의 파티 RTTI 후보 → 복원 vtable/getter/schema → 등록 함수 `293570` 및 송신 함수 `553120/553228`. 문자열만으로 opcode를 정하지 않았다. |
| O2 원본 수신·UI | 이번 파일 전용 판독 `550870/552530/5548A0/555800`, `9CA7E0/9CD750/9CDC20`, `9C7D40/9CCE60/9C97B0/9C9A40`. 기존 [reader](../../local_server_rea_20261016/run381_mob_hpbar_receive/click_frontier.py:1)·[View](../../local_server_rea_20261016/run380_map_transition_receive/f2_research.py:23)를 호출하고 save/main은 실행하지 않았다. |
| O3 원본 행 선택 | [click_frontier_selected.txt](../../local_server_rea_20261016/run381_mob_hpbar_receive/click_frontier_selected.txt:1)의 callback→`9CBC20`→`97F4A0`, [click_altcallables_selected.txt](../../local_server_rea_20261016/run381_mob_hpbar_receive/click_altcallables_selected.txt:432)의 초대 대상 UID→이름 경로. |
| O4 원본 actor·HP | [COMPANION_DISPLAY_EVIDENCE.md](COMPANION_DISPLAY_EVIDENCE.md:1)의 다른 Player 생성/HP HUD, [MOB_HPBAR_EVIDENCE.md](MOB_HPBAR_EVIDENCE.md:1)의 `4F1A/4EC8` 경계. |
| C1 현 서버 원장 | [world_companion.py](../../../tools/local_original_session/world_companion.py:1): 저장 character ID와 runtime actor UID 분리, `CompanionRecord`가 자원 권위. |
| C2 현 서버 소비 | [world_feature_companion.py](../../../tools/local_original_session/world_feature_companion.py:353)의 SoloMage 생성·복원·펫 상태 송신, [world_hpbar_experiment.py](../../../tools/local_original_session/world_hpbar_experiment.py:1)의 미확인 탐색 builder. |
| L1 L1J 참고 | checkout `103e6f6c9dd83545959d8e87d3f59f8de1f40ef0`, origin `https://github.com/l1j-en/classic.git`. `README.md:5–6`은 **2009 최종 US 클라이언트** 대상으로 명시. §7의 정책 참고에만 쓴다. |

출처 비율은 위 **7개 근거군 수 기준 원본 4/7(57%), 현 서버 2/7(29%), L1J 1/7(14%)**다. 코드 줄 수나 구현/동등성 완료율이 아니다. 후속 LOCAL 제안은 확인 근거에 포함하지 않는다.

## 2. 원본 파티 패킷

아래 opcode는 현재 복원 원본의 숫자 등록/송신 immediate다. L1J의 1바이트 opcode와 별개이며 `4E/4F` 접두사가 아니어도 같은 원본 registry에 등록돼 있다.

| 방향 | opcode | 원본 타입 / 확인 범위 |
|---|---|---|
| S→C | `08A0` | `SC_PARTY_MEMBER_LIST`: 파티 그룹/멤버 목록. `294291` factory `11AADF8` → `294298 MOV EDX,8A0` → `2942B0 call292F80`; typed publisher `30C1F0`, parser ctor `3212C0`, vtable `11A3C40`. |
| S→C | `08A1` | `SC_PARTY_MEMBER_LIST_CHANGE_NOTI`: 목록 변경. 등록 `2942BC`. add/remove의 enum별 의미·정상 payload는 아래 미확정 경계를 따른다. |
| S→C | `08A2` | `SC_PARTY_MEMBER_STATUS`: 멤버 상태. 등록 `2942E0`; f3 **HP%**, f4 **MP%**. |
| S→C | `08A3` | `SC_PARTY_SYNC_PERIODIC_INFO`: f1 반복 `SC_PARTY_MEMBER_STATUS`. 등록 `294304`; 각 상태는 `08A2`와 같은 갱신 소비자에 도달한다. |
| C→S | `08A4` | `CS_PARTY_CONTROL_REQ`: 초대 등 파티 제어 요청. `553120 MOV EDX,8A4` → `55312D call27D620`, vtable `11E26B8`. 요청 종류별 enum 의미를 임의 배정하지 않는다. |
| S→C | `08A5` | `SC_PARTY_CONTROL_NOTI`: 파티 제어 통지. 등록 `294328`; 초대 질문/수락 전이의 전체 UI 계약은 미확인. |
| C→S | `08A6` | `CS_PARTY_LEAVE_REQ`: 탈퇴 요청. `553228 MOV EDX,8A6` → `553232 call27D620`, vtable `11E2650`. |
| S→C | `0899` | `SC_PARTY_MEMBER_MARK_CHANGE_NOTI`: 등록 `29422C`; 마크 변경. HP/MP 필드와 혼동하지 않는다. |
| S→C | `089A` | `SC_PARTY_OPERATION_RESULT_NOTI`: 등록 `29425C`; 처리 결과 enum의 정상 의미는 미확인. |
| S→C | `089B` | `SC_PARTY_SPELL_AVATAR_NOTI`: 등록 `294274`; 파티 스펠 관련 부수 표시. HP/MP 표시의 필수 선행 패킷으로 입증되지 않았다. |

등록은 각 factory→같은 문맥의 `MOV EDX`→`292F80`을 대조했다. 같은 함수의 `295D60=4F1A`, `294530=0973`도 동일 등록 형태다. 번호 인접성으로 opcode를 추정하지 않았다. 원본 parser의 실제 수신·암호화·프레이밍 성공을 실행한 결과는 아니다.

### 목록과 멤버 스키마

`R`=required, `O`=optional, `*`=repeated. 타입은 generated mini-table과 IsInitialized를 함께 대조했다. `string`은 wire2 UTF-8 protobuf string이며 기존 actor 출현의 bytes 필드와 구별한다.

| 메시지 | 필드 번호·타입·필수성 | 확인한 소비 / 남은 의미 |
|---|---|---|
| `SC_PARTY_MEMBER_LIST` | **f1 string R**, f2 `PartyMember`*, **f3 int32 R**, f4 enum O | getter `748460`, schema `15FAE48`, IsInit `7487A0`: required mask5 및 각 child 검사. f1/f3가 복합 이름 key 구성에 쓰이며 f4가 그룹 종류 key다. f4=3이면 아래 자동 표시 이벤트를 건너뛴다. f1/f3의 공식 업무 명칭·enum 전체 의미는 미확인. |
| `PartyMember` | **f1 string R**, f2 uint32 O, f3 uint32 O, **f4 int32 R**, f5 int32 O, **f6 int32 R=HP%**, **f7 int32 R=MP%**, f8 int32 O, f9 int32 O, f10 int64 O, f11 uint64 O, f12 uint32 O, f13 message*, f14 int32 O | getter `747B80`, schema `15FAF08`, IsInit `748330` mask69. f3는 표시 DTO의 **actor UID(+28)**로 연결되며 부재 시 -1이다. `553C33..553C3C`는 f6/f7를 DTO+64/+68에 저장한다. f1 이름과 추가 키를 쓰는 경로가 있어 UID만으로 멤버를 식별하지 않는다. f4 등 정상값·전체 의미, f13 child schema `15FA108`의 전체 계약은 미복원이다. |
| `SC_PARTY_MEMBER_STATUS` | **f1 string R**, f2 uint32 O, **f3 int32 O=HP%**, **f4 int32 O=MP%**, f5..f8 int32 O, f9 message*, f10 int32 O, f11 int32 O | getter `749200`, schema `15FAAA8`, IsInit `749820` mask1 및 child 검사. f1와 **f10(+54)**를 포함한 복합 이름 key로 그룹/멤버 lookup `554D20/54F790`. f10의 공식 의미와 목록 각 키와의 완전 대응은 미확인. f2를 UID라고 추측하지 않는다. |
| `SC_PARTY_SYNC_PERIODIC_INFO` | f1 `SC_PARTY_MEMBER_STATUS`* | getter `749910`, schema `15FAC70`, nested aux `15FACC0→15FAAA8`. 빈 repeated는 갱신 대상이 없을 뿐 상태 생성이나 초기 파티 가입을 대신하지 않는다. |

**signedness 주의:** mini-table `0x891=uint32`, `0x1091=int32`, `0x10D1=int64`, `0x8D1=uint64`([기존 타입 해석](../../local_server_rea_20261016/run106_shop_dialog_contract/wire_schema/finalize.py:4)). 따라서 HP/MP는 int32 비율이며 uint32 current/max 쌍이 아니다. `PartyMember.f10`을 UID로 잘못 지정하지 않는다.

### 목록 변경·초대 제어·탈퇴의 스키마

| 메시지 | 필드 | 정적 근거 / 남은 계약 |
|---|---|---|
| `08A1 SC_PARTY_MEMBER_LIST_CHANGE_NOTI` | f1/f2/f3 string O, f4 `PartyMember` O, f5/f6 int32 O, **f7 enum R** | getter `748B60`, schema `15FACD0`, IsInit `7490B0` mask40 및 child 검사. f7의 추가/제거/리더 변경 enum 값 대응은 미확인. |
| `08A4 CS_PARTY_CONTROL_REQ` | **f1 enum R**, f2 uint32 O, f3 string O, f4/f5 int32 O | getter `74A140`, schema `15FA8B0`, IsInit `74A480` bit4. 송신 caller에 f1=3/4/5/6/7/8/9/10/11 값이 있지만 각각을 초대/수락/거절이라고 번역할 근거는 부족하다. |
| `08A5 SC_PARTY_CONTROL_NOTI` | f1 bool O | getter `748880`, schema `15FADF0`, IsInit `7489B0` 항상 true. 이 bool을 파티 가입 성공/초대 수락이라고 단정하지 않는다. |
| `08A6 CS_PARTY_LEAVE_REQ` | f1 enum O | getter `74A510`, schema `15FA850`, IsInit `74A680` 항상 true. `5531B0` caller에서 f1=1 present 또는 absent/default1 경로를 확인했으나 종류별 업무 의미는 미확인. |
| `PartyInviteData` | **f1 string R** | getter `754580`, schema `15FCBD0`, IsInit `754710` bit0. 어느 outer packet/field가 실제 초대 대화상자에 공급하는지는 미확인. `08A5`의 nested 필드라고 임의 결속하지 않는다. |

따라서 **초대/가입/탈퇴 관련 메시지의 존재·opcode·위 필드 형식**은 확인됐고, **정상 초대→수락/거절→가입, 탈퇴→제거/해산의 enum별 전체 프로토콜**은 미완이다. 서버가 목록으로 동료를 게시하는 별도 LOCAL 경로와 구별한다.

## 3. HP/MP·창 표시의 실제 정적 소비

### HP/MP

`08A2 → typed subscriber551D30 → wrapper copy5507A0 → 552530`에서 **f3(+3C)→555800(type0)**, **f4(+40)→555800(type1)**로 들어간다. `08A3 →551B10`은 반복 상태마다 같은 `552530`을 호출한다.

`555800`은 현재 파티 그룹과 복합 이름 key의 기존 멤버를 찾아 **type0→멤버 DTO+64, type1→DTO+68**에 쓴다. 그 멤버의 DTO+28 UID와 수치/type을 `PartySubsystem+260` delegate 내부 `+268` fanout에 전달한다. 수신만으로 존재하지 않는 멤버를 만드는 경로가 아니다.

UI 구독 `9CDC20..9CDCA3`은 UID에 해당하는 행을 찾고 type0을 **HP `9C97B0→9C98C0/9C9950`**, type1을 **MP `9C9A40/9C9AC0`**로 보낸다. 원본 `9C7D40`은 행의 `HpBar`를 +68, `MpBar`를 +78에 보유하며 둘 다 cocos2d `LoadingBar` 타입이다. setter는 **0..100**으로 clamp해 LoadingBar+704 및 원 `C1E7E0/C1E820` 갱신을 사용한다. 이는 **비율 막대** 근거이며 실제 current/max 숫자가 함께 출력된다는 근거가 아니다.

초기 행 채우기 `9CCE60..9CD36D`에는 DTO+64 HP 소비가 있지만, 확인한 전체 구간에 **DTO+68 MP read/MP setter가 없다**. 따라서 목록만 보낸 뒤 MP 초기값도 보일 것이라고 가정하지 않고 **목록 뒤 초기 HP/MP 상태를 모두 갱신**해야 한다.

### 초대 없이 창 열기

`08A0` 수신 `550870`의 멤버 loop `550A30→5548A0`는 그룹/멤버를 저장한다. 목록 **f4(enum)→그룹 DTO+48**이며, `554BCB CMP [group+48],3 /554BCF JE554C24`는 종류3의 표시 통지를 건너뛴다. 그 밖에는 `554BD1→647D0`의 PartySubsystem, 멤버 DTO+28 UID를 얻어 **`554BE3 subsystem+28 →554BEB call679F0`**으로 목록 delegate를 발행한다.

UI ctor `9CA7E0`은 PartySubsystem **+20**에 `9CD750`을 구독한다. 위 +28은 그 delegate의 내부 fanout으로 연결된다. **`9CD763..9CD775`는 숨겨져 있으면 visibility slot68→slot70(true)**를 호출하고 멤버 UID로 현재 파티 자료를 찾아 행을 채운다. PC vtable `121F5A0`의 실제 slot68=`A10B90`, slot70=`A10BB0`은 Node visibility getter/setter다.

**결론: 올바른 그룹/멤버 key와 nonempty 목록, f4!=3, 원 UI/Subsystem 초기화·구독이 갖춰진 경우, 목록→저장→이벤트→창 열기 경로에 초대 수락을 확인하는 gate가 없다.** 서버가 자율 동료를 목록에 넣는 방식은 정적으로 가능하다. 전체 로그인 수명·다른 창·화면 배치·차단/재정렬의 모든 gate를 배제하거나 실제 표시 성공을 증명한 것은 아니다. 종류3의 공식 명칭도 미확인이다.

## 4. 필요한 패킷 순서 — 후속 구현안, 미실행

1. **정상 로그인→캐릭터 선택→WORLD와 원 파티 UI 초기화**를 유지한다. 저장 SoloMage의 `CompanionRecord`와 현재 actor의 UID/세대를 확보한다. 다른 Player 생성은 기존 완전한 `4E96(f16=true, nonself UID)` 계약을 사용한다.
2. **`08A0` 완전 목록**을 보낸다. 그룹 f1/f3와 종류 f4, 주인과 동료 각 `PartyMember`의 required f1/f4/f6(HP%)/f7(MP%) 및 정상 optional key·현재 actor UID f3를 구성한다. 정상값 미확정 항목은 먼저 정적으로 닫는다. 첫 행이 self, 다른 멤버는 나머지7행으로 가는 원 경로에 맞춰 주인을 포함한 한 그룹으로 구성하는 LOCAL 설계를 제안한다. 실제 순서/표시는 화면으로 확인한다.
3. 목록 생성/행 반영 뒤 **`08A2`를 멤버별로**, 또는 **`08A3.f1` 반복 상태**로 초기 HP/MP를 보낸다. 같은 복합 key를 사용하고 f3=HP%, f4=MP%를 명시한다. 두 메시지를 모두 보내야 한다는 근거는 없으므로 한 경로를 선택한다. 상태를 목록보다 먼저 보내 lookup 실패한 것을 정상 초기화로 세지 않는다.
4. 실제 피해/치유/MP 소비/회복/최대값 변경 후 **같은 원장에서 새 비율을 투영**해 상태 갱신한다. `100*current/max` 정수 나눗셈은 후속 **LOCAL 인코딩 정책 제안**이며 원본 서버 rounding 공식은 미확인이다. maxMP=0인 다른 직업은 0%로 표현할지·MP바를 숨길지 별도로 확인한다. 파티 표시 때문에 자원을 변경하지 않는다.
5. 멤버 추가/제거·맵 전환·로그아웃·재접속·actor 교체는 목록과 상태 key/UID 수명도 함께 정리한다. `08A1`의 add/remove 의미와 해산/탈퇴 통지 순서를 닫은 뒤 사용한다. full `08A0` 재전송이 제거까지 처리하는 **snapshot**이라는 보장은 아직 없다. `4E40`만으로 파티 행도 없어질 것으로 가정하지 않는다.

초대·수락 화면을 생략하는 LOCAL 동료 파티는 위 목록/상태 경로를 쓰는 안이다. 정상 플레이어 간 초대 기능까지 구현하려면 `08A4/08A5` 및 제어/결과 enum·초대 수명·거절·탈퇴를 별도로 완성해야 한다. 파티 표시를 위해 사용자 저장 캐릭터를 두 번째 로그인 세션으로 접속시키거나 PC 상태 원장을 복제할 필요는 없다.

## 5. 클릭·채팅·수명·여러 동료의 영향

| 항목 | 확인 / 설계에 반영할 것 |
|---|---|
| 파티 행 선택 | PC callback `9D7700/9D7620` → owner+B8 선택 index → `9CBC20` → 행 UID 또는 -1 → HUD manager `97F4A0`. 현재 강조/이름 visibility를 바꾸는 정적 경로다. **행 클릭=공격/자동 따라가기/동료 명령**으로 입증되지 않았다. 실제 타깃·시전 선택·우클릭·더블클릭 효과는 미확인이다. |
| 초대·추방·리더 변경 메뉴 | 원본에 UID target callback과 파티 제어 요청이 존재한다. 메뉴에서 현재 동료/주인을 대상으로 요청이 나올 수 있으므로 표시만 붙이고 서버 요청을 방치하면 안 된다. 허용할 요청만 기존 세션/현재 멤버에 적용하고 잘못된 요청만 거절한다. 초대 수락이 자율 동료 가입의 필수라는 뜻은 아니다. |
| 채팅 | 파티 채팅 입력이 활성화되더라도 자율 actor는 실제 socket 세션이 없다. 주인에게 정상 채팅 표시/회신 범위만 LOCAL로 정하고 동료의 자발적 발화를 가정하지 않는다. **현재 LC의 파티 chat opcode/type 값은 이번 자료로 확정하지 않았다.** L1J type11을 전용하지 않는다. |
| 경험치·보상 | 파티 표시와 서버 보상 계산은 분리한다. 사용자 확정 **주인/동료 50:50·0.5 잔여**를 유지한다. L1J 파티 분배를 추가 적용해 이중 지급/레벨 가중 분배로 바꾸지 않는다. 여러 동료의 보상 분배 정책은 이번 표시 조사로 결정하지 않는다. |
| 다른 Player·펫 UI | 동료는 원본의 remote Player actor를 유지한다. 파티 등록이 f16을 Pet으로 바꾸거나 `4F14` 펫 상태를 파티 상태로 만드는 계약은 아니다. 펫 창·행 선택·머리 위 HP바가 서로 덮이는지는 후속 화면 확인 대상이다. |
| 화면 밖·다른 맵·사망 | 파티 DTO의 멤버와 화면 actor registry의 수명은 다르다. 화면 밖에서도 상태 막대가 유지되는지, UID 없는 행의 동작, HP0와 시체/부활·거리/오프라인 표시는 미확인이다. 죽었다고 저장 캐릭터를 삭제하거나 파티 탈퇴를 강제하지 않는다. |
| 여러 명 | PC initializer `9D3AF0`은 `ListView.PartySlot_{}`를 **1부터8까지** 만들고 `9D43EF CMP8`; 선택 함수도 `9CBDC3 CMP8`이다. `9CCE60`은 자기 UID를 첫 행에, nonself를 **+D0..+130의 빈7행**에 배치한다. 이 PC 레이아웃에서 주인+동료7명의 표시 슬롯은 확인했다. 넘친 목록 처리·mobile 차이/확장·정확한 서버 정원은 미확인이다. |
| 안정된 식별 | 저장 `character_id`→현재 `actor.ref.uid`와 이름/추가 key의 대응을 사용한다. 주인 이탈·맵 변경·재접속으로 UID가 바뀌면 옛 파티 행의 선택과 status가 새 actor에 섞이지 않게 기존 수명에서 정리한다. 단순 이름만으로 여러 저장 캐릭터/다른 그룹을 합치지 않는다. |

현 서버는 `WorldCompanions.records/active`가 사전이라 여러 항목을 담지만 **현재 구현 전체가 직업 중립/다중 동료 완성인 것은 아니다**. `world_companion.py:130–140`은 class3만 허용하고, `world_feature_companion.py:389–442`는 법사 생성/프로필/외형을 선택하며, `:512–516`은 첫 `members[0]`만 복원한다. 이는 후속 구현 범위이며 이번에는 수정하지 않았다.

## 6. 현 서버에 붙일 구현 단계

1. **남은 wire 의미부터 닫기:** 목록 f1/f3·그룹 종류 enum, 필수 `PartyMember.f4`, 이름+추가 key 대응, `08A1` 제거/해산과 `08A4/08A5/08A6` 제어 enum·caller 의미. f6/f7는 HP/MP%로 확인됐고 제어 shape도 위에 정리했다. 정상값이 없으면 고정값을 원본 값으로 주장하지 않는다.
2. **독립적인 선택 기능으로 목록/상태 encoder·projection:** 기존 `CompanionRecord`의 hp/mp/max값, 저장 이름과 현재 actor reference를 읽는다. 파티 HP/MP용 새 원장·별도 타이머·로그인 세션을 만들지 않는다. 기존 world 순서에서 목록→초기 상태→실제 변화→정리를 연결한다.
3. **양쪽 표시를 같은 자원 생산자에 연결:** 파티 `%` 통지는 이번 계약을 쓰고, 머리 위 HP바는 기존 미확정 계약을 별도로 닫는다. `4F1A` debug 숫자·`4EC8` 익명 세 필드·기존 HPbar 탐색 builder를 정상 파티 갱신으로 쓰지 않는다. 현재 `_companion_status_frame`의 `4F14`도 펫 UI용이다.
4. **제어 요청과 수명 마감:** 원본 행/메뉴가 만드는 실제 요청을 확인해 허용/거절하고, 주인 이탈·actor 교체·사망/부활·재접속의 목록·상태·선택 잔존을 정리한다. 현재 공통 코어에 새 필수 호출을 만들지 않고 선택 모듈을 빼도 다른 기능이 동작하게 한다. 타 기능의 ctx 메서드를 직접 호출하지 않는다.
5. **원본에서 한 순서씩 검증:** 다음 절의 실제 화면 확인으로 목록·막대·입력·정리의 판정을 나눈다. 그때도 실행 소유자는 하나이며 이미 정상 상태인 Source/저장과 원 실행·정리 계약을 재사용한다. 이번 조사가 실제 실행을 수행하거나 새로 승인한 것은 아니다.

## 7. L1J 참고 — 현재 클래식과 분리

이 checkout의 `S_Party`는 **HTML 이름 목록**, `S_HPMeter`는 **객체 HP 비율**이다. 현 원본 `08A0/08A2/08A3`와 동일 패킷이 아니다. `C/H/D`는 각각 u8/LE16/LE32, `S`는 UTF-8+NUL(`J/serverpackets/ServerBasePacket.java:37–50,73–82`).

| L1J 용도 | 이 checkout의 wire / 출처 |
|---|---|
| 목록 요청/응답 | C→S `4D`, 추가 필드 없음(`clientpackets/C_Party.java:33–45`). S→C **`25,D pcObjId,S "party",H 1,H 2,S leaderName,S members`**(`serverpackets/S_Party.java:31–44`). members는 공백으로 연결한 이름이며 마지막도 공백(`model/L1Party.java:93–98`). |
| HP | S→C **`68,D 대상ObjId,C HP%`**, MP·이름·maxHP 필드 없음(`serverpackets/S_HPMeter.java:28–44`). |
| MP | S→C **`5C,H currentMP,H maxMP`**, **대상ID 없는 자기 MP**(`serverpackets/S_MPUpdate.java:24–39`). 다른 파티원 MP 통지의 근거가 아니다. |
| 초대/질문 | C→S `82,C type(0/1),D targetId`(`C_CreateParty.java:40–70`). S→C `69,H 953,S inviterName`(`S_Message_YN.java:26–43`). |
| 수락/거절 | C→S `3F,H 953,C answer(0/1)`(`C_Attr.java:74–82,413–438`). |
| 탈퇴/추방 | C→S `0B` 추가 필드 없음(`C_LeaveParty.java:30–35`), C→S `48,S memberName`(`C_BanParty.java:31–47`). |
| 파티 채팅 | C→S `12,C 11,S text`(`C_Chat.java:50–55,128–134`); S→C `03,C 11,S "(이름) 내용"`(`S_ChatPacket.java:76–79`). |

- `L1Party.java:38–65,101–128`: 가입 때 HP meter를 서로 교환, HP 변경 시 전체 멤버 갱신, 제거 때 `0xff`. **목록 HTML은 가입 시 자동 송신하지 않고 목록 요청에 응답**한다.
- `L1PcInstance.java:2786–2813`: HP setter는 파티 갱신, MP setter는 자기 MP 통지만 보낸다. `S_PacketBox.java` subcode/전체 검색에서도 파티 MP 갱신을 찾지 못했다. 이 checkout에 한정한 음성 결과다.
- `L1Party.java:34`는 `List<L1PcInstance>`, 초대도 `C_CreateParty.java:44`에서 PC만 허용한다. 자율 NPC 성격의 동료를 그대로 넣을 수 있는 범용 서버 구현이 아니다.
- 초대 같은 맵·거리≤5, `MaxPT=8`, 리더 탈퇴 시 해산·2인 파티 이탈 시 양쪽 제거, 로그아웃 탈퇴는 **L1J backend 정책 참고**다(`C_CreateParty.java:51–54`, `config/altsettings.properties:41`, `L1Party.java:130–170`, `network/Client.java:178–183`). 현재 사용자 결정이나 원본 LC 규칙으로 확정하지 않는다.
- 일반 사망은 HP0 갱신이며 조사한 death/leave 경로에서 자동 파티 탈퇴는 확인되지 않았다. 사망 시 표시·부활·정리는 원본과 LOCAL 정책을 각각 확인한다. type2/질문951의 **채팅 전용 파티**는 일반 파티와 별개다.

## 8. 사용자가 원본 화면에서 확인할 것 — 모두 미실행

| 순서 | 확인할 실제 화면/입력 | 판정 경계 |
|---|---|---|
| 1 | 정상 WORLD에서 법사 출현 후 초대 질문 없이 파티 창이 열리는지, 주인/SoloMage 이름·행 순서·중복 여부 | `08A0` 수신/서버 목록만으로 화면 성공을 대신하지 않는다. |
| 2 | 초기 HP/MP 막대가 모두 보이는지; 실제 피해·치유와 법사 실제 시전/회복 후 각 막대가 알맞게 변하는지 | HP와 MP를 따로 판정. debug 숫자나 펫 창 갱신을 파티 창 성공으로 세지 않는다. 자기 PC HP/MP가 동료 값으로 바뀌면 실패다. |
| 3 | 파티 행 선택/해제와 월드의 법사 클릭, 원 펫 창, 실제 공격/마법 대상 선택 | 강조만 바뀌는지, 이동/공격/명령 요청이 발생하는지 각각 기록. 현재 사용자 입력을 자동화하지 않는다. |
| 4 | 파티 채팅·초대/추방/탈퇴/리더 메뉴 | 실제 outbound 요청과 서버 처리 결과를 대조. 동료의 가짜 수락/채팅 세션을 만들지 않는다. |
| 5 | 화면 밖→복귀·맵 이동·동료 HP0/시체/부활·주인 로그아웃/재접속 | 같은 저장 캐릭터의 새 actor UID·행 갱신/옛 선택 제거, 무료 부활·자원 refill·유령 행 없음. |
| 6 | 두 번째 동료를 추가해 서로 다른 HP/MP 변경, 선택·정리, 8행 경계 | 한 행/법사 이름 하드코딩·상태 뒤섞임·목록 넘침을 구별. 장래 다른 직업 maxMP0 동작도 확인. |

## 9. 남은 미확인과 최소 다음 입력

- **정상 완전 payload:** 그룹/멤버의 미명명 필수값과 복합 key의 정확한 생산자 대응. 다음 정적 입력은 `550870/553B40/5548A0`의 모든 필수값 소비와 `08A1/08A4/08A5/08A6` enum·caller다. 정상 온라인 파티 기록을 이미 보유했다면 그 동일 버전의 payload 한 건으로 대조한다. 이번에는 온라인 접속도 하지 않았다.
- **초대/탈퇴 전체 계약:** opcode·기본 스키마는 확인했지만 요청 종류별 필드 의미·수락/거절·탈퇴/해산·멤버 제거의 완전 순서는 미완이다. 표시만 가능한 것과 완성된 파티 기능을 구별한다.
- **실화면·입력·수명:** 자동 열림/HP·MP 소비는 정적 연결, 실제 원본 화면은 UNKNOWN. 후속에는 정상 WORLD의 완전 목록 1회와 실제 자원 변화 1회, 정리 결과가 최소 관측이다. 다른 Source/저장의 PASS를 합산하지 않는다.
- **머리 위 HP/MP:** 파티 창 `%` 계약이 다른 Player 머리 위 bar visibility를 켜는지 확인하지 않았다. 기존 `4F1A`/`4EC8` 미확정을 유지한다.

## 10. 이번 검증

- `git status --short --branch`, 최근 branch 목록과 ACTIVE_TASK/WORK_RULES를 읽었다. 현재 `main`의 기존 대량 dirty/untracked 변경은 다른 작업으로 보존했다. 이번 쓰기는 이 문서 하나다.
- `rg`/`Get-Content`로 위 원본 자료·현 서버·지정 L1J를 대조했다. 잘못된 PowerShell wildcard 경로의 `rg` 실패는 literal 디렉터리 조회로 보완했다. 데이터 부재나 제품 실패로 해석하지 않았다.
- `python -B -X utf8 -`에서 `click_frontier.V.read/fn`을 호출해 **LIST/STATUS mini-table, `294291..294340` 등록, `555800` DTO/이벤트, `9CD750` visibility, HP/MP setter**를 독립 재확인했다. 파일 출력·원 게임 함수 호출은 없다. `9CDC20`은 `.pdata` entry가 없는 leaf, split된 setter는 함수 추출만으로 꼬리가 잘릴 수 있으므로 exact 범위 판독 결과를 사용했다.
- 재현은 아래처럼 **import만 하고 기존 추출기의 main/save를 호출하지 않는** 파일 전용 Python으로 한다. 바이너리 bytes/base64는 출력하지 않는다.

```powershell
@'
import sys, struct
from pathlib import Path
sys.path.insert(0, str(Path('work/local_server_rea_20261016/run381_mob_hpbar_receive').resolve()))
from click_frontier import V, fn
print('CONTROL', V.meta['source_sha256'])
for at in (0x15fae48, 0x15faaa8):
    h = V.read(at, 40)
    mx, skip, off = (struct.unpack_from('<I', h, p)[0] for p in (4, 12, 16))
    n = struct.unpack_from('<H', h, 20)[0]
    fields = [j+1 for j in range(mx) if not (skip >> j) & 1]
    print(hex(at), list(zip(fields, struct.iter_unpack('<IIHH', V.read(at+off, n*12)))))
for r in fn(0x293570)['instructions']:
    if 0x294291 <= int(r['rva'], 16) <= 0x294340:
        print(r['rva'], r['instruction'])
'@ | python -B -X utf8 -
```

결과는 위 CONTROL 해시, LIST4필드/STATUS11필드와 08A0/08A1/08A2/08A3/08A5 등록 확인이다. 추가 파일 전용 판독에서 Member/제어4종 mini-table, non3 이벤트 발행, HP/MP DTO 저장과8행 분기도 대조했다. 문서 자체의 `python -B -X utf8 -` 점검 결과 **로컬 링크14개 누락0, 필수 주제13개 누락0, trailing whitespace/NUL0, UTF-8 정상**이다. 이 경로는 기존 git ignore 대상이며 stage/commit하지 않았다. 실행 시험이나 화면 PASS를 발급하지 않는다.

## 11. MP 누락 후속 — 서버 갱신 및 머리 위 표시 경계 (2026-10-30)

**서버는 이미 기사와 동료 모두 08A0 멤버 f7 및 08A3 상태 f4에 MP%를 보냈다. 파티 창에서 동료 MP가 안 보인 원인을 패킷 필드 누락으로 확정할 수 없다.** 이번 수정은 실제 MP 또는 maxMP가 바뀌어도 정수 비율이 같으면 상태 송신을 생략하던 캐시를 고친다. 예를 들어 0→3/max314도 f4=0을 명시해서 다시 보낸다. current/max는 자원 원장에서 읽으며, 이 패킷에 미확인 current/max 필드를 추가하지 않았다. 파티/머리 위 원본 소비 입력은 같은 **비율**이다.

| 비교 | 기사(자기 PC) | 동료(nonself Player) |
|---|---|---|
| 서버 자원 권위 | `combat.pcs[uid].mp/max_mp` | `CompanionRecord.mp/max_mp` |
| 파티 초기/변경 | 동일한 `CompanionParty.member/status`: 08A0.f2 child.f7 / 08A3.f1 child.f4 | 동일. 이름/현재 actor UID만 다르며 MP 표시용 차별 필드는 없다. |
| 자기 상태 | 4E38.f12/f13 current/max → 자기 CharacterData | 동료 값으로 4E38을 보내지 않는다. 주인 MP를 덮어쓰게 된다. |
| 머리 위 MP | 생성 995C60의 self bool=true → 993910 | self bool=false → 993910. 파티 가입 9838D0은 9937E0(HP)만 호출한다. |

새 **파일 전용 정적 판독** 원문은 [companion-mp-display-disassembly.txt](companion-mp-display-disassembly.txt)다. §1의 동일 CONTROL 복원 자료와 기존 run381 reader를 재사용했다. REA MCP session은 open=false였으며 새 target/현재 프로세스를 열지 않았다. 새 REA Evidence ID는 없고, 아래는 로컬 Capstone 판독이다. 현재 실행 바이너리와의 동일성·실행 성공을 뜻하지 않는다.

- `5525DA..552613`: 상태 f4 present bit3를 검사하고 +40 값을 `555800(type1)`에 전달한다. f4=0도 present면 처리한다. `5558AE`는 DTO+68에 저장하고, `555940..555980`은 actor UID/type/value로 구독자에게 전달한다.
- `9CDC82..9CDC9D`: 파티 행+10에 MP float를 쓰고 행+8 bool의 역을 visibility 인자로 하여 `9C9A40` 또는 `9C9AC0`으로 보낸다. `9C9A40`은 행+78의 MpBar visibility와 LoadingBar+704를 갱신한다. 이 경로에는 self UID 전용 조건이 없다. 행+8이 왜 해당 실행에서 설정됐는지와 실제 게이지 값은 현재 미관측이다.
- **머리 위 MP 값도 연결됨:** `996E10`은 이벤트 UID와 HUD actor UID 일치를 확인하고, `996EC3..996ECF`의 type1은 `996F50`으로 간다. `996F50`은 PlayerActorHud+1A8의 MP LoadingBar+704를 0..100으로 갱신한다. HP type0은 +1A0/996F00을 쓴다.
- **머리 위 MP 표시가 별도로 막힘:** `996275..99627C`는 생성 self bool을 `993910`에 넘긴다. `99391F`는 HUD+201 bool에 저장하고, `993A16..993A34`는 이 bool 및 표시 설정을 통과해야 +180 MP 컨테이너를 visible=true로 한다. 값 setter `996F50`에는 이 visibility 호출이 없다. 확인한 파티 가입 `983970..983A80`은 HP를 켜고 HP%만 채우며 MP를 켜지 않는다. `993910`의 bounded direct CALL/JMP 탐색은 생성 caller 한 곳만 찾았고 간접 호출/alias 전체 부재까지 증명하지 않는다.

따라서 **머리 위 MP는 서버의 확인된 f4 송신만으로 표시 완료를 주장할 수 없으며 DLL 쪽에서 nonself 동료 HUD의 MP visibility를 연결할 근거가 있다.** 해당 작업은 기존 HP 가입/제거/재생성 수명과 표시 설정을 따라 원 setter를 연결해야 한다. 임의 Actor wire 필드, 미확인 4EC8/4F1A, 실험 HPbar 설정으로 해결하지 않았다. 이번에는 DLL을 수정하지 않았다. 파티 MP 미표시는 MP=0%(빈 파란 게이지)였는지, 행 visibility나 적용 시점 문제였는지 아직 UNKNOWN이며 캡처/메모리 관측으로 구별해야 한다.

서버 변경: [world_feature_companion.py](../../../tools/local_original_session/world_feature_companion.py)의 `CompanionParty`는 마지막 송신 투영에 원장의 `(mp,max_mp)`를 보관하여 기사/동료의 매 변화마다 기존 08A3.f4를 보낸다. 자원 권위를 복제하거나 저장 형식을 바꾸지 않는다. 초기 목록 뒤 상태, 멤버 제거·UID 교체, 기존 저장/송신 경계는 유지한다.

시험: [world_companion_mp_display_tests.py](../../../tools/local_original_session/world_companion_mp_display_tests.py) 4개를 추가했다. 초기 기사/동료 필드 대조, current/max 변화·동일 비율·명시적 0·무변화 시 무송신, 실제 shield 시전/자연 회복, 착용 무기 흡수의 패킷을 검사한다. 첫 실행은 시험 시작값100에서 회복이 9%→10% 경계를 넘어 동일 비율 검증이 실패했다. 시작값을104로 고친 뒤 아래 **35개 모두 통과**했다. 첫 실패는 제품 패킷 실패가 아닌 fixture 기대값 오류다.

```powershell
$env:TMP=(Join-Path (Get-Location) '_work/tmp'); $env:TEMP=$env:TMP
python -B -X utf8 -m unittest tools.local_original_session.world_companion_mp_display_tests tools.local_original_session.world_companion_rules_tests.PartyProjectionTests tools.local_original_session.world_companion_regen_tests tools.local_original_session.world_companion_mana_tests -v
```

직접 실행 결과: `Ran 35 tests in 21.088s / OK`, [원로그](../runs/companion-mp-display-20261030/offline-tests.txt). 포트/게임/봇 실행0, 사용자 저장 수정0. 흡수 fixture의 저장 시험은 `_work/tmp` 아래 임시 characters.json만 사용한다. **개발 패킷 시험이며 화면/정식 플레이 PASS가 아니다.**

Claude 헤드리스 확인 지점(이번에는 실행하지 않음):

1. 정상 WORLD·동료 생성·08A0→08A3 뒤 MP가 양수인 시점에 전체 화면 캡처. 기사와 Mage의 파티 행 및 머리 위를 한 장에 담고, 해당 원장의 current/max·f4 비율을 함께 기록한다. MP=0이면 파란 채움이 안 보이는 것은 정상적인 빈 비율일 수 있으므로 양수 시점도 필요하다.
2. 실제 시전 직전/직후, 흡수 명중 직후, 자연 MP 회복 직후에 각각 송신/drain 이후 원 프레임이 진행된 지점에서 캡처. 같은 멤버 이름/key의 08A3.f4를 대조하고, 주인 MP가 동료 값으로 바뀌지 않는지도 확인한다. 0→3/max314는 패킷 갱신을 기대하지만 여전히0%이므로 픽셀 변화의 판정점으로 쓰지 않는다.
3. f4>0인데 파티에서 안 보이면 해당 행 UID·+10 MP float·+8 숨김 bool·+78 MpBar(+704 percent/Node visibility), 접힌 레이아웃이면 +80/+88과 +25를 읽는다. 머리 위는 동일 UID의 PlayerActorHud+1A8(+704)와 +180 컨테이너 visibility·+201 bool을 따로 읽는다. 값 양수/컨테이너 hidden이면 값 수신과 가시성 실패를 구별할 수 있다. 모두 **현재 프로세스의 확인된 RVA/객체 연결**로 읽으며 과거 VA를 재사용하지 않는다.
