# 펫·소환수 제어와 표시 — 고정 클라이언트 근거

2026-10-27의 초기 정적 분석 단계에서는 원본 기반 클라이언트 26.09.29.2001의 보존 복원 섹션을 읽었다. 기준 CONTROL SHA256은 기존 recovery metadata의 `9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`를 승계한다. 주소는 RVA이며 현재 프로세스 주소가 아니다. 이 정적 분석 단계에서는 게임·서버·포트·패킷 송신·원 함수 실행·commit을 하지 않았다. 기존 제어·표시는 `run396_pet_control/`, 이 단계의 목표 지정·Player 클릭 조건은 `run400_pet_command_target/`에 남겼으며 쓰기는 run400과 이 문서뿐이었다. 이후 서버 연결·패킷 시험은 아래 해당 절에 별도로 기록한다.

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

새 직접 원문 `R/run396_pet_control/commands/pet-commands.txt:31,63,95,127,159,191` 및 `dismiss.txt:8–10`을 확인했다. Dismiss 버튼→확인용 callable→mode8 producer를 구분한다. 모달 accept/reject event 분기·확인 UI의 실제 실행·서버 처리·정상 제거 응답은 미확인이다. 선정 init에는 Follow/Wait widget이 없으며, 별도 **따라오기/대기 요청은 미확정**이다. 확인된 Rest는 휴식4로 기록하고 방어·휴식을 따라오기 값으로 치환하지 않는다. 공격 태세와 **Targeting / 공격 목표 지정**은 별도 경로다. 목표 선택 이후 C2S의 이전 미확정은 아래 run400의 실제 producer로 좁혀 닫았다.

펫 전용 버튼·확인해산·창 child 갱신의 전체 근거: [명령 분석](../../local_server_rea_20261016/run396_pet_control/commands/findings.md).

### 목표 지정 → 실제 공격대상 UID → 4F02 (run400)

**Targeting 뒤 대상을 찍는 원 요청은 `4F02 CS_PET_COMMAND_REQ`의 명령1이다.** AttackStance는 명령2·빈 f2를 즉시 보내며 이 선택 모드를 설정하지 않는다. 따라서 화면의 ‘공격’이라는 표현만으로 두 동작을 합치지 않는다.

| wire field | 목표 지정 producer의 실제 값 |
|---|---|
| f1 closed-enum i32, required | **1**. UI command4·공격 태세2와 다른 값이다. |
| f2 repeated string | **공격할 actor UID를 10진 문자열로 넣은 원소 1개**. uint32 필드가 아니다. |
| f3 uint32, optional | **조종할 펫/소환수의 Minion+198 lowDWORD**, 실제 present. 공격대상 UID가 아니다. |

Pet `A84480` / Summon `B22390`→`54C380→1689D0(command4)`의 뒤를 연결했다. `167D00` 생성자의 `168109`는 RTTI **PetAttackInteraction**의 vptr11890C0를 설치하고 `168193/16819D`는 key4에 같은 receiver를 등록한다. `168EE0`의 slot0=`163F40`은 선택 대기를 설정한다. 다음 원 입력 `A8EC0→168B30`이 slot8=`163F90`을 호출한다. 원문: `R/run400_pet_command_target/target/selected.txt:1–81,160–202`, `input.txt:17–24,106–111`.

`163F90`은 ActorsSubsystem+918의 **key0** 값으로 `627B0`에서 실제 actor Pair를 찾고, 그 actor.slot8 반환 **RAX64**를 `A6400`으로 문자열화한다. `1640C7`은 f1=1, `1640D2..1640F5`는 f2 원소 추가·복사, `1640FE/164104`는 f3, `164130/16413D`는 opcode4F02→27D620이다. 원문: `target/selected.txt:82–159`. key0는 기존 run172의 정상 Mouse→A9180→AD350 선택 producer를 재사용했다(`target/reused-hover.txt:3–7,212–255`). 실제 클릭 순간의 선택 상태를 관측한 결과는 아니다.

`A6400`은 signed64 값의 10진 문자열을 만든다(음수이면 `-` 포함). 이 호출에서 low32 절단·zero-extension은 없다. 정상 4E96.f2 u32→Actor UID 프로필이면 양수 10진 문자열이다(`target/uid.txt:140–208`). key0 node 존재·actor lookup·원 입력 admission/current 상태가 필요하며 actor lookup null이면 요청을 만들지 않는다. 송신 뒤 protobuf/string·Pair 정리와 로컬 선택 상태 복귀는 서버 ACK나 행동 성공을 뜻하지 않는다. 취소 입력의 전체 분기도 미확정이다. 자세한 원문·정리 범위: [목표 지정 분석](../../local_server_rea_20261016/run400_pet_command_target/target/findings.md).

### 실제 Player형 actor에서 펫 창을 여는 조건 (run400)

**일반 Player의 기본 클릭은 여전히 펫 요청 경로가 아니지만, 실제 Player도 조건부로 원 경로를 쓸 수 있다.** 같은 생성 Info의 f21이 nonempty이면 `B6CB6..B6CC7`이 Player.slot10/selector5보다 먼저 selector20을 고른다. `B8C9A..B8CB8`은 Player38==2일 때만 usershop으로 선점하므로 Player38!=2이면 case20을 계속한다. 근거: `R/run400_pet_command_target/player/reused-disassembly.txt:46–55,173–190`, `selected-disassembly.txt:17–39`. REA280의 Info78==0 일반 Player 결론을 모든 Player로 확대하지 않는다.

조건은 **4E96.f16=true인 nonself Player, Player38!=2(f65 복사값), nonempty f21이 현재 MyPlayer 이름과 정확한 length/bytes로 일치**하는 것이다. 원 f21은 SpawnInfo+68에, 공통 Description 초기화는 이를 Description+88에 복사하므로 Info78/Description98은 각각 같은 문자열의 길이다. case20이 B8710을 설치한 뒤 B8710의 current·Description 존재/이름 일치 guard를 통과하면 실제 actor UID low32의4F13을 만든다. 근거: `player/reused-disassembly.txt:74–172`, `player/selected-disassembly.txt:67–78`, `R/run270_pet_callback_installer_join/source/installer/selected-evidence.json`의 B879B..B8879. 정상 선택/Interaction·current world/actor 수명도 필요하다.

이 조건부 경로는 **실제 Player 클래스를 유지**한다. f16=false 뒤쪽의 Pet/Summoned 생성·SPR subtype5/10 조건과 별개이며, 임의 Player 외형 SPR을 Pet으로 바꾸는 방법을 요구하지 않는다. 원 wire 필드로 소유 이름을 생산하는 LOCAL 정책은 메모리 patch·selector/I88 강제·callback 직접 호출과 구분한다. 공식 서버가 실제 Player에 그런 f21을 보내는지, 소유권/권한을 허용하는지는 UNKNOWN이다.

정상4F14의 선정 consumer `54BDF0→54D660→A82C30`에는 actor를 Pet으로 제한하는 cast가 없다. f2=1이면 PetLayout을 선택하고 f1을 Minion+198에 저장해 공통 actor lookup/Description 이름을 소비한다. 따라서 존재하는 Player UID라는 이유만으로 이 경로가 거절되지는 않는다. 요청 pending 대조 부재는 이 body 범위의 관측이며, 공식 서버가 그 요청에 실제4F14를 보내거나 전체 UI가 열린다는 실행 증거는 아니다. 근거: `player/selected-disassembly.txt:277–342,502–564,589–664`, `R/run396_pet_control/commands/pet-commands.txt:429–520`. 상세: [Player 조건 분석](../../local_server_rea_20261016/run400_pet_command_target/player/findings.md).

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

목표 지정은 창의 Targeting→실제 적 한 마리 클릭→4F02.f1=1/f2=[그 적 UID의 10진 문자열]/f3=그 펫 UID→실제 펫 행동 순서로 관측한다. AttackStance만 누른 mode2/빈f2 및 선택 취소를 별도로 기록한다. Player는 정상 생산된 f16=true/f21=현재 주인 이름/f65!=2와 실제 Player 타입을 확인한 한 배우에서 원 클릭→같은UID4F13→정상4F14→창→동일 목표 지정 흐름을 비교하고, empty-f21 일반 Player를 대조한다. 메모리·selector 강제나 직접 callback/최종 요청 송신으로 원 입력을 대신하지 않는다. 이번 실험은 모두 UNRUN이다.

HP는 같은 펫 UID의 4F1A.f2 변화와 실제 막대 폭을 대조하고, 가능하면 다른 주인 펫의 f21/HP바 표시와 비교한다. 창에서는 같은 UID의 4F13/4F14 및 명령 전후 child 값·HP/MP 표시·상태 문구를 대조한다. 휴식4 후 이동과 방어3 후 이동을 따로 관측해 ‘대기/따라오기’의 실제 행동을 구분하며, 별도 따라오기 입력이 있다면 그 원 입력·요청을 보존한다. 제거 뒤 배우·HUD·창이 함께 사라지는지, 뒤늦은 이전 UID 통지가 잘못된 배우를 갱신하지 않는지도 관측한다. 이번 작업은 이 화면 실험을 실행하지 않았으며 정적 연결을 실행 PASS로 표시하지 않는다.

## 펫 구현용 근거 보강 — 기존 자료 재사용

2026-10-27 후속 펫 범위의 정적 조사다. 위 run396/run400 기록과 원문은 보존한다. 이 절은 기존 소스·복호화 UML·카탈로그·공식 수집자료·L1J Java를 읽었으며 새 바이너리 분석, 게임·서버·포트 실행이나 원본/저장 변경은 하지 않았다. 아래 `T/`는 `tools/local_original_session/`, `U/`는 `C:/Users/Chansol/Documents/Codex/2026-09-07/d-lineage-classic/outputs/decrypted-pack/data_0/data/uml/`다. `확정`은 원문·정적 연결, `LOCAL`은 별도 서버 정책이며 화면 성공을 뜻하지 않는다.

| 접점 | 확인 근거와 구현 경계 |
|---|---|
| 고기·약해진 동물·성장 | 현재 보존 `work/local_resource_provider/assets/data/dialogue.csv:473`의 `helpnpc_1`은 약해진 늑대 등에 음식 제공, 종류별 다른 음식, 전투 경험치·레벨 성장을 명시한다. 정확 HP 기준·확률·성장량은 없다. `T/data/m1/pets.json`의 HP<floor(maxHP/3), 잔여 CHA≥6, 슬롯<180, 종별 먹이·성장은 L1J를 채택한 **local_policy**다. 고기10과 괴물 눈 고기9를 혼용하지 않는다. |
| 실제 펫 보관소 메뉴 | **`dick1`**이 확보된 원 stem이다. `U/dick1.uml:6–8`은 action=`depositpet`, action=`retrievepet`, link=`helpnpc`다. `dick2/3.uml:9`의 뒤로가기는 link=`dick1`. `work/asset_data_analysis/current/catalog.tsv:357–359`의 기존 `identical` 판정으로 보존 UML과 현 catalog의 대응을 재사용했다. `dialogue.csv:466–471`은 맡기기/찾기/길들이기와 찾기당50아데나를 설명한다. **`petshop` stem을 찾았다는 결과가 아니다.** |
| 메뉴 요청 | 기존 [NPC 메뉴 근거](M2_NPC_MENUS.md)의 4E43 클릭→4E44.f2 stem→UML, HACTION→4ED4를 재사용한다. `R/run382_npc_dialog_menu/handler_registration_keys.tsv`의 initializer29키에는 `depositpet`/`retrievepet`가 없어 generic fallback 후보다. 실제 버튼 요청·공식 발급 문맥은 미확인이다. L1J의 `depositnpc`/`withdrawnpc`로 원 literal을 바꾸지 않는다. |
| 관리 NPC·위치 | L1J SQL:22200/23830은 Rick70544, token `$615`, gfx1515→`dick1`; :48978은 map4(33039,32746)다. 이 위치는 요청한 말하는 섬/글루딘 근거가 아니다. 고정 native dump에서 `$615` 대응을 확보하지 못했다. 두 마을 관리 NPC의 배치·외형 선택은 **LOCAL**이며 공식 원배치로 주장하지 않는다. `petmatcher`는 별도 경기장 NPC다. |
| 0960 대상 사용 | [기존 대상 사용 근거](ENCHANT_USE_EVIDENCE.md:31)는 outer f1=사용 inventory UID, nested f1=1/f2=int64 대상 UID/f3=0/f15=0/f16=0의 일반 경로를 확인한다. **고기10의 길들이기·목걸이361에 그 producer가 실제 선택되는지는 미확인**이다. 이를 받는 서버 어댑터는 LOCAL이며 template ID를 live UID로 대체하지 않는다. 기존 동료 raw0 토글도 펫 원 입력 근거가 아니다. |
| 목걸이361 | native dump:1231의 item361/`$1173`/icon487/SPR1317과 `T/data/official/items.json`의 official_id361이 이름을 대응한다. [공식 수집 원출처](https://api-goats.plaync.com/linclassic/v2.0/game/item/361?locale=ko-KR)는 주인 표시·목걸이 교환을 통한 펫 교환을 설명한다. 361은 template이며 collar instance UID·durable pet ID·live actor UID는 별개다. raw0 사용이나 공식 소환/보관 wire를 이 설명으로 확정하지 않는다. |
| 보관과 영구 해산 | L1J `J/clientpackets/C_NPCAction.java:486–501`의 depositnpc는 save→collect→active 제거·deleteMe이며 목걸이를 지우지 않는다. withdrawnpc는 S_PetList, `C_SelectList.java:44–88`는 실제 collar instance를 골라 useDogCollar로 연결한다. `C_ItemUSe.java:900–905,4940–4948`의 목걸이 사용도 같은 연결이다. `L1PetInstance.java:329–352`의 liberate는 야생 대체 배우 생성·목걸이/펫 원장 삭제로 **보관과 다른 영구 해산**이다. 일반 보관·사망·부활·재접속으로 item361을 소비하지 않는다. |
| 사망·부활 | [공식 부활 주문서28](https://api-goats.plaync.com/linclassic/v2.0/game/item/28?locale=ko-KR)은 펫 부활 가능만 확인한다(보존 `T/data/official/items.json`, official_id28). L1J `C_ItemUSe.java:966–1030`의 일반40089는 NPC/펫 HP max/4, 축복140089는 full, 재생 시작·resurrect flag다. 이는 별도 LOCAL 수치 근거다. [동료 표시 근거](COMPANION_DISPLAY_EVIDENCE.md:80)의 4F16 동일UID 복원은 다른 Player에서 확인했으므로 **Pet형 소비 전체·일어서기 프레임까지 입증하지 않는다**. 같은UID4F16과 제거후4E96 재출현을 구분한다. |

공식 수집자료는 2026-10-26 수집한 원문을 재사용했다. item10의 공식 설명은 포만감뿐이며 길들이기 수치가 없고, item9는 별도 음식이다. item343의 호루라기 설명은 주위로 모음이며 창의 수집6/산개7 요청과 합치지 않는다. 원 도움말의 굶주림·보관 중 안전 설명은 정성 근거이며 시간·소모량 전체를 구현 완료로 바꾸지 않는다.

확보 `T/data/official/monsters.json`에서 Wolf9는 레벨6, Doberman177은6, Shepherd179는5이며 말하는 섬·글루디오 지역을 포함한다([늑대 원출처](https://api-goats.plaync.com/linclassic/v2.0/game/monster/9?locale=ko-KR), [세퍼드 원출처](https://api-goats.plaync.com/linclassic/v2.0/game/monster/179?locale=ko-KR)). 정확 좌표·길들이기 가능·HP·공속을 주는 자료는 아니다. 특히 L1J Wolf45043의 레벨5와 공식 야생 Wolf9의6을 섞지 않으며, 길들인 뒤의 초기 EXP750/레벨5는 별도 L1J LOCAL 정책이다.

### 기존 카탈로그의 출처 집계

`T/data/m1/pets.json`의 **종 정의14개**를 분모로 하면 고정 Classic 이름/token·SPR 후보가 있는 종은12/14, 미확인 Tiger/Jindo Puppy는2/14다. 12종에 보존된 후보 행은38개이며 같은 종의 야생/펫/변종 역할을 확정한 수가 아니다. **아이템 정의4개**(고기·괴물 눈 고기·당근·목걸이)는 Classic 후보가4/4이고 확보 공식 items의 ID·이름도4/4 대응한다. L1J ID와의 의미 대응, 실제 사용 wire·소비·길들이기 확정은 이 분자에 포함하지 않는다.

종별 수치 정책은14/14가 L1J 유래 `local_policy`다. 공통 `rules`의 길들이기·명령·경험치·목걸이 **정책 묶음4개**도4/4가 L1J 참고와 명시 LOCAL 선택을 담고 있으며, 별도 경험치표1개 역시 L1J 유래다. 이 집계는 카탈로그 출처 커버리지이며 구현 완료율·원본 동등성 백분율이 아니다. 원 창 명령/표시·출현·HP·제거의 확정 계약은 위 본문의 개별 근거로 관리한다.

### 이번 서버 연결의 명시 정책

`T/world_feature_pet.py`와 `T/data/m1/pet_runtime.json`은 **`SL_PET=1` opt-in, 기본0**의 별도 펫 연결이다. 개는 세퍼드179/SPR936, 늑대는9/SPR96 두 종을 채택한다. 기존 동료 엔티티·전투·AI·보상 계약과 CompanionStore 저장 스키마/atomic 처리를 재사용하되, 펫 저장은 프로필의 `pets/companion.json`이며 기존 플레이어 동료 저장과 분리한다. 펫의 영속 신원과 목걸이 instance를 보존하고 live actor·선택창 문맥은 별도 수명으로 다룬다. 이 기록은 구현 정책의 출처 설명이며 시험 PASS 선언이 아니다.

고기10을 요청한 두 종의 먹이로 허용하는 것은 **L1J의 괴물 눈 고기9 전용 조건을 바꾼 명시 LOCAL 선택**이다. 입장이 유효한 제공은 HP/CHA 조건 실패에도 한 개를 실제 먹는 정책이며, L1J의 주는 이→대상 inventory transfer 의미와 다르다. 목걸이361은 보관·소환·사망·부활에 소모하지 않는다. targeted0960과 목걸이 raw0는 서버 어댑터이며 원 클라이언트 입력 귀속은 여전히 미확인이다.

명령2는 주인 공격 보조/추종,3은 방어/추종,4는 휴식/정지,5는 경계/정지와 반경8 탐색,6은 반경8 수집,7은 반경4 산개/방어를 선택한다. **번호는 원 창 근거, 각 AI 결정·거리·획득 정책은 LOCAL**이다. 기존 사용자 승인 경험치50:50 및 half 원장을 재사용하며 종별 레벨당 HP/MP 성장·경험치표는 L1J 정책을 사용한다. 죽은 펫은 로그인만으로 부활시키지 않고, 부활 주문서의 대상 사용 후 같은UID·새 generation으로 HP=max(1,maxHP//4), MP 유지하는 LOCAL 복원을 선택한다. 실제 Pet형 원 화면 부활은 미확인이다. 영구 해산8은 이 정책의 일반 보관으로 재해석하지 않는다.

현재 runtime 데이터의 **활성 종2개**는 고정 내부 ID·SPR 근거2/2와 확보 공식 이름·지역 근거2/2가 있고, HP/MP·속도·성장 수치는2/2가 L1J 참고 LOCAL이다. **관리 NPC 배치2개**는2/2가 LOCAL이며 확인된 Classic NPC 신원은0/2다. 원 `dick1` 자원·`depositpet`/`retrievepet` 두 action은 재사용하되, 특정 두 NPC의 메뉴 발급·고유 목걸이 직접 찾기 어댑터·수수료 적용은 서버 정책이다. `local_policy`의 **이름 있는 정책 묶음7개**(food/consumption/positions/commands/trainer/taming/revival)는7/7이 LOCAL 경계를 명시한다. 서로 다른 분모를 더해 원본 비율로 환산하지 않는다.

### 초기 패킷 시험의 경계(원결과 보존)

`runs/hunt-pet-qvh98sf3/summary.json`은 정상 FIRST/로그인/선택/월드 진입 뒤 실제 늑대 공격 HP30→6, 고기10 한 개 소비, 서버 발급 목걸이361, 펫 창, 목걸이 보관/새 배우 소환, 첫 홀수 처치의 공동 EXP/half1까지 관측했다. 같은 실행의 정상 Quit/close는 기존 `world_feature_magic.py` 어댑터 정리에서 `AttributeError: 'Context' object has no attribute '_world_move_for_handler'`로 실패했다. `cleanup_complete:false`와 원실패를 보존하며 전체 PASS로 표시하지 않는다. 시험 중 선정 소스 변경은 없었다.

당시 필요한 변경은 `world_feature_magic.py`의 `_world_magic_consumers.install()`에서 Context facade가 아닌 실제 `ctx.broker`를 어댑터 소유자로 기록·복원하는 국소 수정이었다. 당시 요청에서는 이 파일이 수정 금지 범위여서 변경하지 않았다. 그 실행에서 후속 명령별 행동·성장 사냥·상점·사망/부활·재접속은 미확인이며, 이후 결과로 원실패를 소급 성공 처리하지 않는다.

### 2026-10-27 펫 마감 후속

이번 시작 baseline의 `world_feature_magic.py:288–291`에는 이미 Context→broker 어댑터 소유자 정규화가 있었다. 기존 변경을 보존했으며 이번 worker가 다시 작성하지 않았다. 이번 소유 파일의 시작 사본은 `runs/pet-finish-20261027/baseline/`에 있다.

첫 후속 `runs/hunt-pet-d8k6f7kd/summary.json`은 정상 Quit/close와 두 epoch의 `cleanup_complete:true`, 첫 홀수 처치의 EXP/half 저장까지 확인했으나 첫 재접속 record 동등성에서 실패했다. 저장 JSON의 `learned_spells:[]`를 PetSystem만 list로 복원한 것이 원인이다. 새 record의 tuple 및 기존 `world_feature_companion.py:393`/`world_companion.py:423` 복원 계약을 따라 펫 로더에서도 tuple로 정규화했다. 저장 형식·값·보상·목걸이를 바꾸지 않는다. 원실패와 저장은 그대로 보존한다. `world_pet_integration_tests.py`에 저장/복원 collection type 회귀를 추가했다.

다음 `runs/hunt-pet-pduecyvc/summary.json`은 늑대 HP를 낮추던 실제 장검 치사타(HP30→0) 뒤 봇이 중단한 실패이며 정상 정리됐다. 봇은 같은 제한시간 안에 다음 실제 수신 야생을 고르게 보완했다. 죽은 동물로 음식 요청을 보내지 않고 RNG·피해·HP를 바꾸지 않는다. `runs/hunt-pet-klbvq06y/summary.json`은 tuple 수정 뒤 첫 half 저장/재접속·두 홀수 처치·성장 사냥 두 처치(EXP755→781)까지 통과했으나 소진 스폰 중심에서 no-op step을 반복해 `NAVIGATION_STALLED`로 끝났고 정상 정리됐다. 봇의 성장 탐색만 살아있는 슬롯/미활성/소진 그룹 순으로 선택하고, 도착한 중심에서는 실제 재생성을 기다리도록 보완했다. 제품의 스폰 수·재생성60~120초·시계·EXP·성장식은 유지한다.

`runs/hunt-pet-oow_1asm/summary.json`은 성장 사냥13처치·펫EXP755→962·HP4 유지 뒤 실제900초 관측기한으로 `UNCONFIRMED: NATURAL_PET_LEVEL6_GROWTH_DEADLINE`이며 정상 정리됐다. 이를 레벨업 성공으로 표시하지 않는다. 후속 봇은 기존 hunt 안전상한 주인레벨+3을 재사용하여 고EXP 먹잇감(기존 늑대인간8 등)도 사냥하며 가까운 스폰의 실제 수량/EXP와 수신 대상을 기준으로 경로를 선택한다. 한 이동 목적지는 도착 전까지 유지하고, 실제 NPC→주인 공격 수신 뒤 펫 한 번 참여→즉시 주인 공격/휴식으로 정상 공격 간격 안에 대상을 되찾는다. 관측기한만3600초로 늘리고 제품 시계·스폰·레벨/EXP·피해를 바꾸지 않는다.

`runs/hunt-pet-igr8dbov/summary.json`은 성장14처치·펫EXP1190/HP8까지 진행한 뒤 실제 공격 요청에서 `SERVER_EOF`, broker `KeyError`로 실패했다. broker 두 epoch의 자원 정리는 true이나 실패 epoch의 Quit ACK가 없어 **전체 `cleanup_complete:false`**다. 원실패의 정확 KeyError 인수/traceback은 당시 broker 보고가 코드명만 남겨 **UNKNOWN**이다. 이후 성공이 있더라도 이 KeyError를 수정했다고 해석하지 않는다. 후속 봇은 기존 magic bot의 bounded exception observer를 재사용하여 실제 원예외·최대6000자 traceback을 최대8개 기록한다. 원 `_failure_code`의 반환과 예외 처리 동작은 그대로다.

개발 진단 `runs/pet-growth-diagnostic-7sepaljx/diagnostic.json`은 원실패1190EXP 저장을 새 사본으로 복사하고 정상 로그인했으나 실제 펫 사망으로 종료돼 KeyError를 재현하지 못했다. 다음 독립 사본 `runs/pet-growth-diagnostic-2s0linmc/diagnostic.json`은 실제 사냥으로 펫EXP1305/레벨6/maxHP39·HP39·MP6까지 성장하고 정상 재접속/저장을 확인했으나 역시 KeyError는 재현하지 못했다. 두 진단은 fresh 전체 시나리오 PASS로 합산하지 않는다. observer에 기록된 정상 종료 과정의 `SESSION_STOPPED`와 제품 요청 실패는 구분한다.

후속 fresh `runs/hunt-pet-uhveflte/summary.json`은 펫EXP1209/HP9까지 진행한 뒤 같은 공격 요청 EOF로 실패했고, 이번에는 observer가 **KeyError(23)**의 실제 traceback을 남겼다. 기존 `WorldView._reward→_show_items→world_visibility.ground_frame:173`의 `item_gfx()[item.item_id][1]`에서 실제 순간이동 주문서23 드롭의 바닥 그래픽 행이 없었다. `cleanup_complete:false`와 원저장을 보존한다. 이 실행의 원인은 고정된 자료 누락이며 펫 보상·소유권을 우회하거나 드롭을 숨겨 해결하지 않는다. 앞 igr8dbov에는 traceback이 없어 동일 원인인지는 추정이다.

읽기 확인한 기존 `T/data/m1/item_gfx.json` 형식의 누락은 이번 성장 먹잇감4/27/2/8 드롭 중23·28·299이다. 고정 `work/source_game_data/native-dump-v1.jsonl`의 973행 item23은 f5=473/f6=22, 977행 item28은471/22, 1194행 item299는472/22다. 범용 표 수정은 이번 최초 허용 파일 밖이라 승인 전에는 읽기만 했다. 값3쌍은 클라이언트 원문이며 실제 원 화면 렌더링의 증거는 아니다.

### 이전 마감의 검증과 당시 남은 작업

아래 명령은 `SL_TEST_PORT_BASE=16000`, `SL_PET=1`에서 순차 실행했다. 실제 클라이언트·화면 캡처·전역 입력은 실행하지 않았다.

| 명령/근거 | 실제 결과와 범위 |
|---|---|
| `python -m tools.local_original_session.world_pet_tests` | 27 tests OK. 기존 pure 규칙 개발 시험. 로그 `runs/pet-finish-20261027/pet-rules.log`. |
| `python -m tools.local_original_session.world_pet_integration_tests` (`SL_RUN_PET_INTEGRATION=0`) | 최종 10 tests OK, **socket 1개 skipped**, 개발9개 통과. tuple 복원 회귀 포함. 로그 `runs/pet-finish-20261027/pet-development-final.log`. 실제 전체 socket 통합 성공을 뜻하지 않는다. |
| `python -m tools.local_original_session.world_magic_tests` | 55 tests OK. magic 코드가 추가 변경되지 않아 동일 결과 재사용. 로그 `runs/pet-finish-20261027/magic-development.log`. |
| `python -m tools.local_original_session.hunt_bot_magic --scenario all` | `runs/hunt-magic-rvwo1og6/summary.json`: **SUCCESS**, 355 checks/51 casts/8 epochs, 각 epoch 정상 Quit/close·cleanup true, 전체 cleanup true, 실행 중 source 변경 없음. 기존27과 새11 마법은 독립 시험 프로필이며 한 캐릭터 연속성·원 화면 동등성으로 확대하지 않는다. 로그 `runs/pet-finish-20261027/magic-all.log`. |
| `python -m tools.local_original_session.hunt_bot_pet --with-companion` | **당시 전체 SUCCESS 미달**. 앞 절 원실패/UNCONFIRMED 모두 보존. 당시 최신 fresh uhveflte의 정확 첫 실패는 실제 주문서23 드롭 그래픽 누락 KeyError(23)이었고, gfx표 보강 전 재실행을 보류했다. 이후 최종 결과는 아래 절에 기록한다. |

`runs/pet-finish-20261027/item-gfx-three-rows.patch`는 당시 위 클라이언트 원문3행의 **미적용 승인용 패치안**이었다. 그 마감에서는 `git apply --check`만 확인하고 제품 `item_gfx.json`을 바꾸지 않았다. 이후 이번 요청 시작 전3행이 반영됐고 fresh 전체 펫/socket 통합은 아래 최종 절에서 마감했다. 원본 클라이언트 화면·입력·공식 AI/성장·부활 수명 동등성은 계속 미확인이다.

그 마감의 실제 제품 변경은 펫 JSON 로더의 tuple 정규화1곳이며, 기존 companion 복원 계약을 재사용했다. 봇의 자연 치사타 재선택·사냥 탐색/수신 공격 동기화·기한·기존 exception observer 재사용은 LOCAL 시험 행동이다. 기존 활성 종2개 내부 ID/SPR 근거2/2·공식 이름/지역2/2, 수치2/2 LOCAL 및 관리 NPC2/2 LOCAL 집계는 유지하며 이를 구현/원본 동등성 비율로 합산하지 않는다. `world_feature_magic.py`의 기존 종료 수정과 `player_spells.json`의 CAST_UNSUPPORTED는 당시 worker가 변경하지 않았다. 마지막 magic 실행 후16000/18030 listener는0개로 확인했다.

### 2026-10-27 최종 로컬 패킷 마감

이번 요청 시작 때 주문서23/28/299의 `item_gfx.json` 3행은 이미 반영돼 있었다. 이번 추가 수정은 `hunt_bot_pet.py`, `world_feature_pet.py`, `world_pet_integration_tests.py`와 이 문서에 한정한다. 원본 클라이언트·화면 캡처는 실행하지 않았고 사용자 저장·launcher 핀은 수정하지 않았다. `manual-play/start-manual-play.ps1`의 핀 목록에 이번 수정 파일은 없어 핀 갱신은 필요하지 않았다.

원 실패 `hunt-pet-v1gf7b99`는 이동172회 모두 승인/4EE0 정정0회였다. 기존 짧은 BFS와 후속 10,000노드 A*의 탐색 한계를 펫 봇 내부의 확장 A*·경로 재사용으로 해결했다. 다음 실제 걸음마다 현재 점유·terrain·거절 edge를 유지하며 goal/map 변경·막힌 다음 걸음은 재계획하고 epoch가 바뀌면 캐시를 버린다. 실패 저장의 새 사본 `pet-failed-route-e1z4r7d2`에서 (32633,32848)→(32454,32901)을 실제179걸음/정정0회로 통과하고 정상 종료했다. 이 경로 진단을 전체 성공과 합산하지 않았다.

서버의 경계5는 HOLD를 유지하며 실제 공격 가능한 적→거리→UID 순으로 선택하고, 공격할 수 없는 원거리 적에 묶이면 가까운 공격 가능 후보를 다시 선택한다. 이는 기존 반경8의 **LOCAL AI 정책** 보완이다. 봇은 주인 이동으로 실제 펫 근접 위치를 만들고, 홀수 EXP/성장 사냥은 실제 주인 선공·NPC 주인피격 수신 뒤 펫1회 참여→주인 재공격/휴식을 재사용한다. 경계 첫 공격 확인 뒤에도 휴식시켜 주인이 마무리한다. HP·RNG·피해·공격 간격·스폰·보상·서버 guard는 바꾸지 않았다. 성장의100% HP와 명령 이동/부활은 해당 실제 응답 수신까지 기다린다.

| 최종 검증 | 결과와 원문 |
|---|---|
| `SL_TEST_PORT_BASE=16000`, `SL_PET=1`, `SL_RUN_PET_INTEGRATION=1`에서 `python -X utf8 -B -m tools.local_original_session.world_pet_integration_tests` | **12 tests OK, skip0**, 868.214초. 로그 `runs/pet-finish-20261027/pet-final-complete-socket-20261027.log`. 짧은 BFS 밖 우회/거절된 캐시 걸음 재계획과 원거리 적보다 근접 적을 실제 공격하는 개발 회귀를 포함한다. |
| 같은 socket test가 호출한 fresh `hunt_bot_pet.run(--with-companion)` | `runs/hunt-pet-42ag8958/summary.json`: **SUCCESS,170/170 checks**,4 epochs 정상 Quit/close·cleanup true, operation failure_code null, 펫errors 빈 목록, 실행 중 source 변경 없음. CLI `main()`의 JSON stdout을 별도 실행한 결과는 아니다. |

위 한 fresh 실행에서 자연18처치로 EXP787→1297/Lv5→6/maxHP30→36·100% HP 응답과 성장 재접속, 명령2/3/4/5/6/7의 실제 행동, 수집 아데나13(1000→1013), 실제 사망·시체/AI 정리, 주문서28 수량10→9·같은UID/새 generation·HP9 부활, 관리NPC 보관/찾기와50아데나(1013→963), 최종 재접속 복원을 확인했다. 마지막16000/18030 listener는0개였다.

새 실패 `hunt-pet-eiy6ftt7`(성장 후 HP 응답 즉시 검사), `hunt-pet-0p7jc6rr`(먼 경로 탐색), `hunt-pet-dqebc07p`(낮은 초기HP에서 선탱킹), `hunt-pet-lcx2u4ci`(경계 뒤 공격보조 재개 중 사망)와 모든 scoped 진단·저장·원로그는 그대로 보존한다. 정상 성장 저장 사본의 꼬리 진단 `pet-grown-tail-ngjjl82h`/`pet-grown-tail-x8nbcwpr`도 별도 결과이며 위 fresh170개에 합산하지 않았다.

새 외부 자료는 사용하지 않았으며 기존 코드·검증된 패킷 계약·명시 LOCAL 정책을 재사용했다. 기존 활성종2/2의 ID/SPR·공식 이름/지역 대응과 수치2/2 LOCAL, 관리NPC2/2 LOCAL의 출처 집계는 유지한다. 이번 성공은 로컬 패킷/저장 수명 범위이며 원본 UI·실제 입력·렌더링·공식 AI/성장/부활 동등성은 아래 미확인 항목대로 남는다.

### 테이밍 몬스터35의 연결 판정

기존 고기 길들이기와 마법35를 같은 영구 펫으로 연결하지 않았다. 보존 `T/data/m3/player_spells.json`의 `taming_monster`는 고정 클라이언트·공식 원문으로 법사20/요정40 학습, MP30/HP0/마력의 돌166 두 개, 거리10, **3600초 하수인**이다. L1J 참고 `D:/SingleLineageRef/l1j-en-classic/src/l1j/server/server/model/skill/L1SkillUse.java:2942–2971`도 `L1SummonInstance(_targetNpc, _user, false)`로 연결하며 영구 목걸이 펫을 만들지 않는다. 같은 트리 `model/Instance/L1SummonInstance.java:36,108–123,193–215`는 1시간 timer와 tamed 수명을 별도로 처리한다. 이 L1J 수치·알고리즘은 공식 구현 증거가 아닌 별도 backend 참고다.

현 PetSystem.tame는 먹이 소비→영구 pet ID/목걸이361 발급→CompanionStore 영속 저장→야생 세대 종료를 한 흐름으로 소유한다. 마법으로 재사용하려면 **목걸이 없는 임시 하수인 신원·주인/대상 세대 전환, 3600초 만료와 죽음/이탈/재접속 시 잔여시간·원야생 해제 정책, catalyst166×2/MP30 한 번 소비와 임시 소유 전환의 실패 복구**가 먼저 필요하다. 마법 기능이 펫 feature의 ctx 메서드를 직접 부르거나 PetSystem의 먹이/목걸이 원장을 빌려 위 수명 차이를 숨기지 않는다. 대상별 길들이기 허용·CHA·성공률의 Classic 값도 미확인이며 L1J만으로 확정하지 않는다. 따라서 `CAST_UNSUPPORTED`를 유지한다. 기존 입장 거절은 책·MP·HP·촉매를 소비하지 않으며, 이는 기존 world_magic_tests의 unsupported 학습/시전 시험 범위다.

### 원본 확인이 더 필요한 항목

- 고기 제공의 실제 UI/producer, 종류별 정확 먹이, 길들이기 확률·CHA·HP 조건과 실패시 음식 처리. 일반 targeted0960 수신 성공만으로 원 입력을 입증하지 않는다.
- 목걸이 사용의 실제 raw/presence와 소환/보관 요청, 여러 목걸이의 선택 목록·비용·한마리 대응, 말하는 섬/글루딘 관리 NPC의 native 신원·배치와 메뉴 발급 조건.
- 공격2/방어3/휴식4/경계5/수집6/산개7 이후 공식 AI 대상선정·이동·획득·분산 거리, 실제 Pet actor의 프레임·공속과 수집 성공.
- Pet형 사망 시체·4F16 복원/일어서기·부활 아이템 실제 소비, 영구 해산의 확인/정리, 배고픔·성장·저장/복원의 공식 수치와 수명. 현재 서버의 LOCAL 저장 정책과 원 규칙은 별도다.
