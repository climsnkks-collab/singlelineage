# 동료에게 아이템·장비 주기 — 원본 정적 근거

2026-10-27. 대상은 고정 LC 26.09.29.2001의 다른 Player형 법사와 `4E96.f21`에 주인 이름을 넣는 경로다. CONTROL SHA256 `9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`는 기존 복원 metadata의 식별을 승계했다. 아래 주소는 RVA이며 현재 프로세스 주소가 아니다. 원문 확인·정적 연결·실제 화면 동작을 구별한다.

이번 쓰기는 `work/local_server_rea_20261016/run406_companion_equipment/`와 이 문서뿐이다. 기존 `main`의 제품·분석 dirty 변경과 worktree는 보존했다. 게임·서버·포트·패킷 송신·원 함수 실행·서버 제품 수정·git commit은 하지 않았다. `reverse-engineer-anything` 스킬과 기존 run의 파일 기반 reader/Capstone을 재사용했다. REA 세션은 `binary_session({})`에서 `open=false`였고 신규 target open·native dossier 발행은 하지 않았다. 따라서 신규 REA Evidence ID나 실행 PASS는 없다.

`R/`는 `work/local_server_rea_20261016/`, `O/`는 `work/local_original_session/`, `J/`는 `D:/SingleLineageRef/l1j-en-classic/src/l1j/server/server/`다. 신규 세부 원문은 `R/run406_companion_equipment/{trade,pet,appearance}/`에 보존한다.

## 출발점과 기존 구현의 범위

- 기존 `tools/local_original_session/item_transfer_*`의 이름만으로 원본 교환창을 구현했다고 보지 않는다. DROP/GET, GIVE, Exchange는 각각의 실제 opcode·caller로 나눠 확인한다.
- `O/implementation-companion/local-ui-own-inventory-wire-v1/HANDOFF.md:26`의 LIT1은 authored LOCAL 표시용 고정928B 데이터다. 같은 문서 `:35`에서 equipment는 명시적으로 UNAVAILABLE이며 use/equip/transfer/save 요청이 없다고 한다. 격리된 GDI paint 성공은 원본 펫·장비창의 근거가 아니다.
- `O/implementation-companion/local-ui-own-items-model-v1/HANDOFF.md:13`도 `GEAR_CURRENT_OWNER_UNSUPPLIED`, `item_action=UNAVAILABLE`다. `local-ui-lrs1-item-core-coherent-v5/HANDOFF.md:87`의 읽기 연결은 원본 장비 착용·서버 이전 완료가 아니다. 폐기한 자체 Win32/GDI 패널을 제품으로 복원하는 안을 제안하지 않는다.
- `O/game-core-prep/PET_EVIDENCE.md`와 `R/run400_pet_command_target/player/findings.md:9`의 최신 조건부 Player 경로를 우선한다. f16=true인 실제 nonself Player도 f21 nonempty, Player38!=2, f21과 현재 주인 이름의 정확한 length/bytes 일치 및 정상 Interaction/current 조건이면 `B8710→4F13` 후보 경로가 있다. 일반 empty-f21 Player 결론을 모든 Player에 확대하지 않는다. 공식 서버의 생산·허용과 실제 클릭 성공은 UNKNOWN이다.

## 교환창과 단순 전달

**동료에게 주는 가장 직접적인 원본 후보는 인벤 아이템을 배우로 드래그하는 `4EF5 GIVE`다.** 양방향 교환창과 별개이며, 기존 로컬 item_transfer의 DROP4E3F/GET4E3E 구현과도 다르다. `A0ADB0→현재 target UID의627B0 lookup→586E0 InteractionComponent→B7690`이 true이면 `3D0F0→4EF5`, false이면 `3CF00→4E3F DROP` 분기로 간다. 수량1과 수량입력 callback을 각각 확인했다. [교환·전달 세부 결과](../../local_server_rea_20261016/run406_companion_equipment/trade/findings.md):48 이후, 직접 발췌 `trade/selected-source.txt:142–363`.

`B7690`은 Interaction+80에 대한 bitmap0x101440(6,10,12,20)을 허용한다. 기존 같은 actor 생성의 **nonempty f21→B6CBD Interaction+80=20**과 정확히 결속되므로, 실제 Player 클래스를 유지하는 f21 동료도 **드래그 GIVE 허용 predicate의 조건부 양성**이다. 주인 이름 일치는 원펫클릭4F13의 별도 guard이고, 이 GIVE predicate에서 같은 문자열 검사를 재확인한 것은 아니다. 현재 배우·선택·아이템·양쪽Action+46·맵/거리/상태 등 나머지 송신 조건은 그대로 필요하다. `R/run400_pet_command_target/player/reused-disassembly.txt:46–55`, 신규 `trade/selected-source.txt:333–363,4–95`.

| 단계·메시지 | opcode·필드 | 실제 caller/consumer·범위 |
|---|---|---|
| 단방향 주기 CS_GIVE_REQ | **4EF5**, required **f1 u32 대상ActorUID, f2 u32 itemUID, f3 u64 수량** | `3D661/3D676/3D665` 저장,`3D6A4→27D620`. descriptor15EDEF0/mask7. 직접 발췌 `trade/selected-source.txt:96–140`, `schema-11e3488.json:5`. |
| 교환 요청 CS_ASK_EXCHANGE_REQ | **4EFB**, f1 u32 대상ActorUID | ExchangeCommandHandler496BB0→496FCA 송신. 정상 sender는 f1 present로 쓰지만 initializer는 항상true여서 required라 부르지 않는다. `selected-source.txt:365–422,886–911`. 원 메뉴/키 등록은 UNKNOWN. |
| 초기 질문 SC_ASK_NOTI | **4ED3**, required f1 enum/f2 u32/f3 i32, optional f4 string, oneof f10 message/f11 string | generic 질문의 등록·schema는 확인. **교환 전용 selector와 최초 수락/거절 callback·C2S 회신은 미연결**. `schema-11ef928.json:5`, `selected-source.txt:876`. |
| 교환 시작 SC_EXCHANGE_START_NOTI | **4EF9**, required f1 string | 4E4640이 상대 표시문자열 복사·active=1·확정상태=0 및 UI open 경로를 호출. `selected-source.txt:669–748,848`. |
| 아이템 올리기 CS_ADD_EXCHANGE_ITEM_REQ | **4EFA**, required f1 u32 아이템키/f2 u64 수량 | 원 ExchangeLayout 수량callback975BB0→4E5AE0; 수량1 직접경로도 있음. `selected-source.txt:423–566,912–962`, `schema-11f25d8.json:5`. |
| 목록 SC_EXCHANGE_ITEM_LIST_NOTI | **0972**, required f1 enum/f2 repeated ItemInfo(child1603A28) | ExchangeSubsystem LIST 수신·공통35필드 ItemInfo schema 확인. enum의 업무명·항목 모든 의미를 임의 지정하지 않는다. `selected-source.txt:640,866,1003`, `schema-1603a28.json:5`. |
| 최종 확정 CS_ACCEPT_EXCHANGE_REQ | **4EFC**, 필드없음 | 원 ExchangeLayout callback976830 송신. **최초 상대방 거래 수락 회신과 다르다.** `selected-source.txt:567–606`, `schema-11f2508.json:5`. |
| 결과 SC_EXCHANGE_RESULT_NOTI | **4EFD**, required f1 u32 | 4E5670의 f1==2는 성공 UI 분기, 이후active=0/close. 아이템 이관·저장 성공의 증명은 아니다. `selected-source.txt:749–865,977`, `schema-11f31a0.json:5`. |
| 취소 CS_CANCEL_EXCHANGE_REQ | **4EFE**, 필드없음 | 4E59C0 송신. `selected-source.txt:607–639`, `schema-11f2570.json:5`. |

원문은 `3D62C→580590`의 추가 조회·거절 분기도 보존한다. caller·entry stack을 대조하면 이 인벤/슬롯 조회에는 **item이 아닌 target 값이 전달**된다(`trade/selected-source.txt:96–140,1049` 이후). 이 원문을 일반적인 ‘장착 아이템 금지’ 규칙으로 보정하지 않으며 업무 의미는 UNKNOWN이다. 송신 조건 통과와 서버의 동료 소유권 이관·수량 차감·저장·착용은 별개이며 **GIVE 후 자동 착용 소비자는 UNKNOWN**이다. 교환창도 최초 질문 수락이 닫히지 않았으므로 완성된 원본 사용자 흐름으로 표시하지 않는다.

## 펫 상태·인벤토리·장비 경로

**조건부 Player 클릭→원 펫 통계창은 정적 연결이 있다. 그 통계창의 인벤·장비 탭은 확인하지 못했다.** `4F13 {required u32 f1=actor UID low32}` 요청과 `4F14 {required u32 f1, enum f2, child f3}` 응답은 상태/명령 창이다. f2=1은 PetLayout,2는 SummonLayout이며 성공값이 아니다. 선정 수신 body는 UID를 공통 ActorSubsystem에서 찾으므로 Player 클래스라는 이유로 거절하지 않는다. 동일 요청에 대한 공식 응답·실제 화면은 UNKNOWN이다. [Player 조건 원문](../../local_server_rea_20261016/run400_pet_command_target/player/findings.md):9–19.

| 경로 | 확인 사실·경계 | 직접 근거 |
|---|---|---|
| 통계 표시 | child f3/f2=HP 현재/최대, f5/f4=MP 현재/최대, f6=Level, f8=허기, f9=성향, f10=double Exp, f1=명령 상태. child f1..6 필수/f7..10 선택. PC 장비의 AC/STR/DEX/INT·무기슬롯 창으로 확장하지 않는다. | `R/run396_pet_control/commands/pet-update.txt:130,291,359,426,492,558,630`, `child-serialize.txt:197` |
| 탭/버튼 | 전체 PetStatusLayout init `A81400..A82974`의 widget/callback은 제어·이름/닫기와 위 상태 표시다. 선정 init/child 소비에 인벤·장비 탭 연결 없음. 공통 CSB script·다른 입력까지 기능 전체 부재를 입증한 것은 아니다. | `R/run396_pet_control/commands/pet-init.txt:1`, `R/run406_companion_equipment/pet/pet-init-annotations.json:10,40,305` |
| 별도 펫 보관 | `PetStorageLayout::Init A84BF0`의 Bt_Ok→callable122BC58→`A87670`은 선택 row 목록을 `4F09 CS_PET_WAREHOUSE_REQ`로 보낸다. 통계창의 아이템 인벤 탭과 연결하지 않는다. 선택 row의 업무 의미·모든 필드·mode 공식값은 미확정. | `R/run406_companion_equipment/pet/storage-init.txt:313`, `warehouse.txt:139–207`, `selected-types.json:1–14` |

L1J 참고는 checkout `103e6f6c9dd83545959d8e87d3f59f8de1f40ef0`의 별도 구형 계약이다. [펫 세부 결과](../../local_server_rea_20261016/run406_companion_equipment/pet/findings.md)의 L1J 절과 `pet/l1j-excerpts.txt`에 원파일의 원행 번호를 보존했다.

- `J/clientpackets/C_PetMenu.java:37–50`은 L1PetInstance의 아이템 목록 조회이며, `S_PetInventory.java:36–54`는 SHOWRETRIEVELIST(24),petId,itemCount,mode0B,아이템별 UID/gfx/bless/count/identified/viewName,마지막 petAC다. C13을 착용 flag로 해석하지 않는다.
- `J/clientpackets/C_UsePetItem.java:40–71`은 별도 USEPETITEM(111),`C data/D petId/C listNo`로 **펫 인벤 ordinal**을 선택한다. 펫 전용 type2=0/type11과 정해진 무기40749..40752/40756..40758·갑옷40761..40766만 허용한다. 같은 장비는 해제, 다른 장비는 교체하고 PetItemTable 수치를 가감한다(`L1PetInstance.java:655–759`). `S_PetEquipment.java:9–15`의 PACKETBOX/sub25 응답도 별개다.
- `J/clientpackets/C_GiveItem.java:116–144,240–250`은 NPC 대상·impl whitelist/수량·수용 조건 뒤 inventory.tradeItem→onGetItem이다. 다른 Player형 법사는 이 source의 대상이 아니다. 전달만으로 자동 무기 착용되는 경로도 아니다. 고정 클래식의 대응 opcode·payload와 다른 Player의 장비 관리는 **UNKNOWN**이다. 구형 코드의 누락된 권한검사를 로컬 정책으로 채택하지 않는다.

## 다른 Player의 무기 표시와 장비·능력치 창

**전용 live 무기 통지는 `4ED5 SC_WIELD_NOTI`다. required u32 f1=ActorUID, required u32 f2=무기 동작군**이며 itemUID가 아니다. `29578C`의 opcode 등록→factory2FEBC0/parser319F80→event1800240→handler4FC20→같은 UID의 Actor/ActionComponent→`4FD28 [Action+40]=f2`를 연결했다. self·Player·f21 비교나 f2!=0 조건 없이 직접 쓰므로, 정상 등록 nonself Player도 이 공통 경로의 후보이며 **0도 저장**한다. [세부 결과](../../local_server_rea_20261016/run406_companion_equipment/appearance/findings.md):15–29, 직접 발췌 `appearance/wield-dispatch.txt:1–43`, `appearance/live.txt:29–98`.

후속은 현재 Action이 **ShopAction인 경우** 기본 action 재queue를 건너뛰고, 나머지는 `977F0(mode1)`로 이어진다. Action+40 쓰기는 이 분기보다 먼저다. 최종 SPR entry/resource 소비는 기존 run385의 `8F9A0→348C80→98F60`과 연결된다. 정적 쓰기·queue와 현재 실행의 구독/자원/실제 픽셀은 구별한다.

| 경로 | 의미·제한 |
|---|---|
| 출현4E96.f4 | `Info+10→970B0→B40EE0→Action+40` 초기화. staff50..53은 base50으로 정규화된다. 같은UID의4E96은 기존 배우 제거/새 생성이라 live 장비 교체와 다르다. |
| **live4ED5.f2** | 정규화 없이 Action+40에 직접 저장한다. 초기 출현처럼51→50을 기대하면 안 된다. `f2=50`의 staff군과 `f2=0`의 해제 후보를 구분하며, 공식 item→군값/송신순서는 미확정이다. |
| 변신4E5C | sprite와 자세를 갱신하지만 f3 정규화결과0이면 Action+40 store를 건너뛰므로 해제0의 대체가 아니다. |
| 자기 장비097A/096B | 현재 Equipment/Inventory subsystem의 key→itemUID·슬롯 표시다. remote Actor의 무기군·동료 소유 장비·능력치 저장을 뜻하지 않는다. |

위 초기화/동작군은 `O/game-core-prep/WEAPON_STANCE_EVIDENCE.md:19` 이후와 `R/run385_weapon_stance_table/source-excerpts.txt:4–59,115–180,294–367`을 재사용했다. 변신은 `O/game-core-prep/POLYMORPH_EVIDENCE.md:35–55`, 자기 장비는 `R/run74_item_equipment_client_contract/worker/findings.md:9–39`와 구분한다. **4ED5에는 아이템 소유·착용·수치·저장 필드가 없다.** 외형 갱신만으로 장비 장착 성공으로 판정하지 않는다.

원 **CharacterInfoLayout의 확인 경로는 현재 PC 모델**이다. `91B660→3EB60`이 전역 CharacterDataSubsystem+6D8을 읽고, `91B6D8→AE6C0`이 전역 EquipmentInfoSubsystem+3D8 map을 얻는다. 슬롯의 `91E430→77340`도 전역 Inventory에서 itemUID를 푼다. **다른 actorUID를 넘겨 이 창을 여는 API는 미확인**이다. `4E38.f1`만 동료UID로 치환하거나 현재PC subsystem을 갈아끼우는 방법은 별도 동료창 근거가 아니다. 직접 원문 `R/run395_selfinfo_stats_fields/selected-disassembly.txt:3588–3633`, `R/run406_companion_equipment/appearance/own.txt:1–34,58–63,84–118`; 자기 능력치 수신은 `O/game-core-prep/SELFINFO_FIELDS_EVIDENCE.md:17–22,54–85`.

따라서 현재 확인된 **동료에게 보여줄 수치 창 후보는 조건부4F14의 HP/MP/Level/허기/성향/Exp/상태**이며, 동료의 일반PC 장비 슬롯·AC/주능력치 창은 별도 미확정이다. 클라이언트 전체에 관찰창이 없다는 전역 부재 주장은 하지 않는다.

## 미확정과 사용자 화면 실험안

**미확정:** Exchange 최초 수락 회신/원 입력 등록, 클래식 펫 인벤·장비의 별도 입력/패킷, 다른Player 인벤/장비 접근권한, GIVE 실제 응답과 두 소유 인벤의 이동·저장, 동료 착용 소비자와 능력치 반영, 공식 장비→무기군 생산값/송신순서, 실제 창·픽셀·입력·저장/재접속. 서버 정책을 원본 화면 표시 근거로 대신하지 않는다.

아래는 **사용자 화면 실험안이며 이번에는 모두 UNRUN**이다. 정상 로그인→캐릭터 선택→WORLD와 정상 생성된 현재 동료ActorUID·주인 소유 아이템을 사용한다. 게임·서버 기동이나 실험 송신기를 이번에 만들지 않았다.

1. 정상 f16=true/f21=현재 주인 이름/f65!=2의 법사에서 인벤의 **장착하지 않은 Q1 아이템 하나를 그 배우로 드래그**한다. 실제 요청이4EF5인지4E3F인지, target/item/Q와 주인 인벤 감소·동료 소유 인벤 증가·저장을 순서대로 기록한다. GIVE 송신만 성공으로 판정하지 않는다.
2. 같은 동료를 원 클릭해 동일UID4F13→정상4F14와 실제 창을 대조한다. 창의 스크롤·탭 유무와 HP/MP/Level/상태를 확인한다. 실제 인벤/장비 버튼이 있다면 원 입력 한 번과 새 요청·응답을 보존한다. 일반 펫과 대조하면 Player형 제한과 기능 유무를 구별할 수 있다. 4F09나 L1J bytes를 임의 전용하지 않는다.
3. **실제 착용을 일으키는 별도 동작이 확보된 뒤에** 장비 이전/착용→능력치와동료 소유저장→동일ActorUID의4ED5→무기 동작을 각각 확인한다. 정지·이동·공격 및 정상 해제0을 나눠 보고, 자기 장비창·능력치가 덮이지 않는지도 본다. 외형만 개발 주입했다면 정식 장착 성공과 구별한다.
4. 양방향 교환은 원본 입력 등록을 먼저 확인한 뒤 요청→질문→정상 수락회신→START→아이템ADD/목록→최종ACCEPT→RESULT 및 실제 인벤·저장을 관측한다. 마지막으로 정상 종료·재접속 후 동료 장비/수치 복원을 확인한다. 앞 응답/상태를 건너뛰거나 selector·callback·성공값을 강제하지 않는다.

이번 확인은 기존 근거 재사용과 새 파일 전용 원문/정적 연결의 검토다. 새 검사기·guard·제품 테스트·전수해시 검사는 만들거나 실행하지 않았다. 정식 PASS·화면동등성 PASS·장비 이전/착용 완료는 선언하지 않는다.
