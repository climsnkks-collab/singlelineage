# 펫·소환수 제어와 표시 — 고정 클라이언트 근거

2026-10-27. 원본 기반 클라이언트 26.09.29.2001의 보존 복원 섹션을 정적으로 읽었다. 기준 CONTROL SHA256은 기존 recovery metadata의 `9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`를 승계한다. 주소는 RVA이며 현재 프로세스 주소가 아니다. 게임·서버·포트·패킷 송신·원 함수 실행·commit은 하지 않았다. 쓰기는 `run396_pet_control/`와 이 문서뿐이다.

`R/`는 `work/local_server_rea_20261016/`, `J/`는 `D:/SingleLineageRef/l1j-en-classic/src/l1j/server/server/`다. 원문 확인·정적 연결·실제 화면 동작을 구분하며, 기존 COMPANION의 authored LOCAL host·시험 성공을 원본 펫 서버 규칙으로 쓰지 않는다.

## 기존 근거에서 확정된 계약

| 방향·역할 | 고정 클라이언트의 확인 사실 | 범위·근거 |
|---|---|---|
| C2S `4F13 CS_SUMMON_STAT_REQ` | 펫/소환수의 실제 Interaction callback `B8710`이 actor slot8 반환의 low32 UID를 **required uint32 f1**에 넣어 `27D620`으로 보낸다. 동작·좌표 필드는 없다. | `R/run270_pet_callback_installer_join/source/contract.md:3–9`. 같은 actor 생성→Interaction 등록→selector20→callable 설치까지 연결. 문자열/current guard가 있어 모든 클릭이 송신되는 것은 아니다. |
| S2C `4F14 SC_SUMMON_STAT_ACK` | `2FB970→318440→event1801C80→Minion54BDF0`. **f1 uint32, f2 closed-enum int32, f3 nested message 모두 required**다. | `R/run274_summon_stat_reply_contract/source/contract.md:3–9`. 실제 등록 근거이며 번호 인접성 추정이 아니다. 공식 서버의 동일 요청·응답 기록은 미확인. |
| 창 선택 | ACK의 **f2=1은 PetLayout/PetStatusLayout, f2=2는 SummonLayout/SummonedMonsterStatusLayout** 분기다. f1은 property0, 복제 child는 property1로 넘긴다. | `R/run277_summon_stat_server_menu/source/menu/contract.md:3–9`. f2를 성공값으로 부르지 않는다. |
| C2S `4F02 CS_PET_COMMAND_REQ` | **f1 closed-enum 명령(required), f2 repeated string, f3 uint32(optional)**. 기존 Summon 버튼 producer `54C460`은 f2 빈 목록과 Minion+198 lowDWORD를 f3에 항상 넣는다. | `R/run279_summon_layout_child_commands/source/commands/contract.md:16–24`. 명령 번호와 ACK child.f1 상태 번호는 별도 도메인이다. |
| S2C `4F1A SC_HIT_RATIO_NOTI` | f1 required uint32 대상키, f2 required int32 HP percent. f1을 zero-extend하여 Pet/Summon HUD map에서 조회하고 **clamp(float(signed f2),0,100)**을 LoadingBar_HP+704에 저장한다. C1E820이 percent/100을 실제 sprite 폭에 소비한다. | `R/run381_mob_hpbar_receive/ratio_findings.md:3,11–17`, `render_findings.md:16–17`. 255는 숨김값이 아니라100으로 clamp된다. 일반 Monster HUD와 구분. |

4F1A의 **f3도 required지만 업무 의미·정상값은 미확정**이다. f2 HP%의 확인만으로 공식 4F1A 전체 payload를 완성했다고 할 수 없다. f4/f5는 별도 Monster debug current/max 텍스트 경로다. `4EC8`은 이 펫 HP% 경로와 다른 통지이며 익명 i32/bool/i32의 업무 의미를 재명명하지 않는다.

## 이번 추가 분석

펫 전용 `PetStatusLayout`의 실제 버튼도 공통 `54C460` producer에 연결된다. 대상은 현재 Minion에 저장된 UID의 low32이며, 공격할 적 UID라고 해석하지 않는다.

| 펫 버튼 | 4F02.f1 | 직접 invoke RVA |
|---|---:|---|
| AttackStance / 공격 태세 | 2 | A843A0 |
| DefendStance / 방어 태세 | 3 | A842C0 |
| Rest / 휴식 | 4 | A841E0 |
| Alert / 경계 | 5 | A84020 |
| Gather / 수집 | 6 | A83F40 |
| Spread / 산개 | 7 | A84100 |
| Dismiss / 해산 확인 callback | 8 | A83D30이 넘긴 A848E0; 소환수는 B22590 |

새 직접 원문 `R/run396_pet_control/commands/pet-commands.txt:31,63,95,127,159,191` 및 `dismiss.txt:8–10`을 확인했다. Dismiss 버튼→확인용 callable→mode8 producer를 구분한다. 모달 accept/reject event 분기·확인 UI의 실제 실행·서버 처리·정상 제거 응답은 미확인이다. 선정 init에는 Follow/Wait widget이 없으며, 별도 **따라오기/대기 요청은 미확정**이다. 확인된 Rest는 휴식4로 기록하고 방어·휴식을 따라오기 값으로 치환하지 않는다. 공격 태세와 **Targeting / 공격 목표 지정**도 별도 경로이며 목표 선택 이후 C2S는 미확정이다.

펫 전용 버튼·확인해산·창 child 갱신의 전체 근거: [명령 분석](../../local_server_rea_20261016/run396_pet_control/commands/findings.md).

### 4F14 → 펫 창의 실제 갱신

`f2=1→PetLayout→54D660.vA0→A82980`에서 property0(상위 f1)은 `A82C30`을 통해 layout+B8/Minion+198에 저장되고 actor UID lookup·이름 표시로 소비된다. property1(child)은 `A82DD0`으로 간다. 이는 f1의 실제 UID 소비 근거이며, 공식 서버가 앞 4F13의 UID를 echo한다는 실행 인과 증명은 아니다.

| nested child | PetStatusLayout의 직접 표시 |
|---|---|
| f1 i32 / raw44 | 상태: 1 목표 지정, 2 공격, 3 방어, 4 휴식, 5 경계, 6 수집, 7 산개, 8 해산 resource 분기 |
| f3 / f2 | HP 라벨 뒤 `f3/f2` 순서 |
| f5 / f4 | MP 라벨 뒤 `f5/f4` 순서 |
| f6 uint32 / raw30 | Level |
| f8 i32 / raw34 | Hunger: 0–20 / 21–40 / 41–60 / 61–80 / >80 단계; 음수는 공백 |
| f9 i32 / raw40 | Alignment |
| f10 double / raw38 | Exp: `{}: {:.4f}%` |

직접 원문은 `R/run396_pet_control/commands/pet-update.txt:130,291,359,426,492,558,630`이다. 특히 **기존 run277의 child.f10 문자열계열 표기는 오기**다. 원 serializer `6C59E2..6C59EA`의 double load→tag **0x51(field10,wire1)**→8바이트 write를 확인했다(`commands/child-serialize.txt:197–199`). 기존 run281에서 미확정이었던 **f6은 Pet 경로에서 Level로 소비**된다. Summon 표시 body에서 f6 직접 소비를 못 찾았던 과거 결과와 구분한다.

상위 required mask7과 child required mask22F는 기성 schema를 재사용한다. **child는 f1..f6이 required, f7..f10이 optional**이다(f1의 presence bit9, f2..f5의 bit0..3, f6의 bit5; bit 번호와 필드 번호는 다름). HP/MP의 네 필드는 uint32다. optional 값도 이번 Pet consumer의 읽기 경로는 확인했지만 공식 정상값·수치 생산식·Exp 배율은 미확정이다. f1 상태 표시와 4F02 명령 번호는 각각의 직접 소비 근거로 연결했으며 숫자만 같다고 동일 enum 타입으로 합치지 않는다. 명령 뒤 공식 서버가 언제 4F14를 재송신하는지와 별도 명령 ACK도 미확인이다.

### 4E96 출현·소유 표시와 4E40 제거

`4E96.f2`의 u32 배우 키와 별개로, **f21(required bytes)**가 SpawnInfo+68 문자열로 복사되고 그 길이 Info+78이 nonzero인 분기에서 **f67(optional enum)=1은 Pet, 2는 SummonedMonster** 생성으로 이어진다. 이때 비Player(f16=false), f39>=0, 실제 SPR subtype5/10 등의 선행 분기도 만족해야 한다. f67만으로 타입을 강제하는 계약이 아니며 f68의 nested message와 혼동하지 않는다. 직접 근거: `R/run396_pet_control/spawn_hp/selected-disassembly.txt:2763–2804`, `selected-metadata.json:5–25`; 자세한 field→Info 복사는 [출현·HP 분석](../../local_server_rea_20261016/run396_pet_control/spawn_hp/findings.md:11).

`f21→SpawnInfo+68→DescriptionComponent+88`의 문자열을 현재 MyPlayer의 Description+40 이름과 길이·bytes로 비교한다. 일치하면 Pet/Summon HUD+190=true, `Node_HP` visibility=true가 된다. 이것이 이번에 닫은 **소유 이름에 따른 HP바 표시** 계약이다. owner UID나 서버 권한 검사로 바꾸지 않는다. 별도 ‘주인 이름’ 텍스트가 화면에 인쇄되는지는 이 경로로 확정하지 않는다. f21의 정상 인코딩/생산자와 이름 변경 후 재평가도 미확정이다. 원문: `spawn_hp/selected-disassembly.txt:764–790,4976`; Pet `992392..9923FE`, Summon `99AA42..99AAAE`.

기존 run270의 `targetTransform+88` 명칭은 **DescriptionComponent+88**로 정정한다. 실제 42EC0 cast RTTI가 DescriptionComponent임을 확인했다(`spawn_hp/selected-metadata.json:37`). 이 정정은 기존 파일을 수정하지 않고 새 문서에 남긴다.

Pet/Summon ctor는 HP 게이지를0으로 초기화한다. 이후 같은 UID의 4F1A.f2가 percent를 바꾸며, numeric setter 자체는 owner 이름을 재검사하지 않는다. 숨겨진 Node_HP 아래 값도 갱신될 수 있다. f21 일치와 HP 수치 갱신은 별도 조건이다.

`4E40.f1(required uint64)→event17FBF80→4E700→ActorSubsystem61650`은 배우 Pair 제거와 선택 정리 뒤 removed-Actor event를 게시한다. `B33774`에서 등록한 ActorHudManager callback **97E290**은 같은 배우 UID64로 HUD를 찾아 root UI slot220 detach 후 map erase/strong·weak release로 간다. 원문: `spawn_hp/selected-disassembly.txt:2111,2204,2569,2626`; 기존 `R/run75_npc_hp_death_contract/findings.md:27`. 따라서 **배우 제거→그 UID HUD detach/erase의 정적 연결**은 확인했다.

이것이 모든 strong reference 즉시 소멸·열린 통계창 종료·Minion+198 초기화까지 입증하는 것은 아니다. 그 후속 정리와 실제 픽셀·소환/해제 공식 송신 순서, 4F02 해산 뒤4E40이 온다는 같은 operation 인과는 미확정이다. 출현과 제거 S2C를 최초 소환/해제 C2S로 대신하지 않는다. 전체 근거는 [출현·HP 분석](../../local_server_rea_20261016/run396_pet_control/spawn_hp/findings.md).

L1J의 별도 구버전 계약: [L1J 대조](../../local_server_rea_20261016/run396_pet_control/l1j/findings.md). L1J 값은 클래식 wire에 그대로 적용하지 않는다.

L1J의 `C_PetMenu`는 petId만 읽어 **S_PetInventory**를 보내며 제어 명령이 아니다(`J/clientpackets/C_PetMenu.java:37–50`). 제어는 NPCTalk→S_PetMenuPacket의 `anicom`/`moncom` 창→NPCAction의 `objectId + action 문자열`이다. `aggressive/defensive/stay/extend/alert/dismiss`의 내부값1/2/3/4/5/6은 클래식 mode2/3/4/7/5/8과 다르다. `extend`는 산개이며 별도 follow 문자열은 없다(`J/model/Instance/L1PetInstance.java:568–585,108–118`).

## 실제 화면에서 확인할 최소 순서

정상 로그인·월드 진입 후 정당하게 꺼낸 펫 한 마리의 실제 UID를 기준으로, 출현→이름/소유 표기와 HP바→펫 클릭→창→명령 하나→창 재조회→해산 확인 순서로 관측한다. 펫과 소환수는 별도로 기록하고, 앞 응답·현재 상태 뒤에 다음 행동을 한다. 해산 취소와 확정을 분리하며 추정 mode나 임의 payload를 송신하지 않는다.

HP는 같은 펫 UID의 4F1A.f2 변화와 실제 막대 폭을 대조하고, 가능하면 다른 주인 펫의 f21/HP바 표시와 비교한다. 창에서는 같은 UID의 4F13/4F14 및 명령 전후 child 값·HP/MP 표시·상태 문구를 대조한다. 휴식4 후 이동과 방어3 후 이동을 따로 관측해 ‘대기/따라오기’의 실제 행동을 구분하며, 별도 따라오기 입력이 있다면 그 원 입력·요청을 보존한다. 제거 뒤 배우·HUD·창이 함께 사라지는지, 뒤늦은 이전 UID 통지가 잘못된 배우를 갱신하지 않는지도 관측한다. 이번 작업은 이 화면 실험을 실행하지 않았으며 정적 연결을 실행 PASS로 표시하지 않는다.
