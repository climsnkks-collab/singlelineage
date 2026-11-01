# 동료 가방·장비 창 — 정적 REA와 구현 설계

2026-10-28. **동료 가방은 원 InventoryLayout, 동료 장비는 원 CharacterInfoLayout을 각각 별도 동료 모델에 연결한다. 두 창은 분리하며 주인의 두 창과 동시에 열 수 있어야 한다.** 동료는 펫 전용 아이템 저장이 아니라 실제 법사 저장 캐릭터다. StorageLayout/창고 목록을 재사용하지 않는다. [기존 펫 창 설계](PET_WINDOW_CUSTOM_DESIGN.md)의 8장 A안·창고 우선순위와 11장 4A 우선 설명은 이번 사용자 결정으로 대체한다. 기존 문서·근거 자체는 보존한다.

**현재 확보한 원 open API는 모두 현재 PC용이다. actorUID 인수를 추가하면 동료 창이 되는 함수는 확인하지 못했다.** 권고안은 별도 원 레이아웃 인스턴스와 view별 아이템·장비·능력치 projection을 만들고, 생성/구독/조회/입력 경계에서 그 view의 모델을 선택하는 DLL 확장이다. 원 전역 subsystem을 동료 데이터로 교체하거나 동료 `0964/097A`를 일반 PC 수신 경로에 흘리는 방식은 채택하지 않는다. 별도 factory의 안전한 두 번째 생성·원 event 해제·전체 callback 수명은 아직 구현 전 계약이다.

이번 변경은 **이 문서 한 개**다. 게임·서버·포트·주입·원 함수 호출·화면 캡처·코드 수정·커밋은 하지 않았다. 이후의 헤드리스 원본 스크린샷은 검증 계획이며 이번 실행 결과가 아니다.

## 1. 근거의 범위와 읽는 법

대상은 고정 **LC 26.09.29.2001**이다. CONTROL SHA256 `9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`는 기존 metadata의 식별을 승계한다. 정적 carrier는 `work/rea_lineage_resume_20261013/main-gameplay/audit/metadata-v2/DERIVED_RESTORED_ANALYSIS_ONLY.exe`, 기존 SHA256 `c822838351d774a2022af434829a36dbd9bee030bf22182b834ca4e8659701a9`, 분석 base `0x140000000`이다. 아래 주소는 모두 **RVA**다. 기존 restored reader/`run104_skill_buff_contract/wire_schema/exec-buffer.bin`과 carrier의 선정 구간을 재사용하며, 실제 loaded LC의 현재 주소·패치 안전성·실행 동등성으로 확대하지 않는다.

`정적 확인`은 보존 명령·schema·자원/기존 분석의 연결, `LOCAL 설계`는 앞으로 추가할 동료 scope·전송·거래 정책, `미확인`은 아직 연결/관측하지 않은 부분이다. REA 스킬을 적용했고 MCP `binary_session({})`은 `open=false`였다. 공유 분석 target을 새로 열거나 원본을 실행하지 않고 기존 파일 근거와 필요한 구간의 파일 기반 Capstone 해독을 사용했다. 신규 REA Evidence ID나 실행 PASS는 발행하지 않았다.

| ID | 기존 근거와 정확한 용도 |
|---|---|
| E1 | [run55 PC receiver](../../local_server_rea_20261016/run55_current_pc_receiver/findings.md), [run63 open contract](../../local_server_rea_20261016/run63_useitem_ui_dispatcher/open-worker/findings.md): Inventory selector/factory·public/impl cache·show/hide/toggle |
| E2 | [run61 population](../../local_server_rea_20261016/run61_useitem_model_population/worker/findings.md): InventoryAdapter·row→metadata→Slot·원 구독/refresh |
| E3 | [run74 equipment](../../local_server_rea_20261016/run74_item_equipment_client_contract/worker/findings.md): `096B/097A` schema·Equipment map·D4 표시 |
| E4 | [run238 검토](../../local_server_rea_20261016/run238_equipment_window_and_item_contracts/MAIN_REVIEW.md), [Use/장비 계약](../../local_server_rea_20261016/run238_equipment_window_and_item_contracts/equip_source/contract.md), [run243 open](../../local_server_rea_20261016/run243_equipment_normal_input/source/contract.md): CharacterInfo factory·12개 슬롯·`0960`과 정상 입력 |
| E5 | [장비 근거](COMPANION_EQUIPMENT_EVIDENCE.md), [run406 trade](../../local_server_rea_20261016/run406_companion_equipment/trade/findings.md), [appearance 원문](../../local_server_rea_20261016/run406_companion_equipment/appearance/own.txt): GIVE·remote 무기·현재 PC getter |
| E6 | [UI_OPEN_EVIDENCE](UI_OPEN_EVIDENCE.md), [PET_WINDOW_CUSTOM_DESIGN 9장](PET_WINDOW_CUSTOM_DESIGN.md): 기존 인벤 재사용안·ABI/현재 모델 한계 |
| E7 | [브리지 HOOKS](../companion-bridge/HOOKS.md), [SIGNALS](../companion-bridge/SIGNALS.md): 7행·`bag-open-take/equipment-open`·현재 IPC 한계 |
| L1 | [world_feature_trade.py](../../../tools/local_original_session/world_feature_trade.py), [world_companion_inventory.py](../../../tools/local_original_session/world_companion_inventory.py): 현재 LOCAL GIVE·동료 저장/착용 서비스. 원본 계약의 증거와 구분 |

**출처 비율:** 원본 함수·wire 동작의 근거는 고정 클라이언트/그 보존 정적 분석 **100%**, 신규 공식 API **0%**, L1J **0%**다. 서버 현황·브리지 신호와 이 문서의 동료 격리/전송 설계는 별도 **LOCAL**이며 위 원본 출처 비율이나 구현 완성률에 합산하지 않는다. E3의 초기 ‘무기 key 미확인’은 E4의 후속 명명된 슬롯표로 보완하지만, 슬롯 이름을 모든 아이템의 장착 자격으로 확대하지 않는다.

## 2. 인벤토리 창·아이템 모델

| 접점 | 정적 확인 | 동료 확장에서의 의미 |
|---|---|---|
| `15EDF0`, `15ECF0→159A20` | 현재 manager `560F0`의 owning Pair를 보유, EDX=2·R8=유효 empty any64로 가방 toggle. `159A20(manager,command,&any)`는 actor/member 인수가 없다 | 주인 shortcut 보존. 동료 open으로 그대로 호출하지 않음 |
| `159A20` cache | key `Inventory`; manager public map `+348`, impl map `+388`은 서로 다름. miss `15B6F0→B38B00→B3B750`; ordinary first-name `InventoryLayout`, resource `InventoryScene.csb` | 같은 key를 다시 요청하면 같은 창 재사용. 별도 동료 instance/소유 등록 경계 필요 |
| PC factory `A0D640` | RCX=factory capture, RDX=out Pair16, R8=Node* cell. 원 InventoryLayoutPCImpl TD`1771848`, primary vptr`12228D8`, COL`1349C80` | 원 자원/원 노드/원 PC 구현을 재사용할 후보. raw object 복사나 factory 직접 실행 성공 근거 아님 |
| 표시 `A11810`, `A096C0`, `A117D0` | command0=show,1=hide,2=toggle. actual v98/v70/v88. `P+30`의 Q own-visible과 원 후처리/구독 수명 보존 | 새 동료 창은 자기 instance에 show. 주인 창 toggle로 대체하지 않음 |
| adapter 생성 `A086C0→A060B0`, vptr`1221E28` | A060B0는 **RCX=out Adapter* cell, RDX=borrowed string32**인 allocating factory. `A+90`에 문자열 복사, 내부 population·구독 후 out에 A 게시 | 단순 ctor(this) ABI로 호출하지 않음. 생성 중 SELF 구독/최초 population부터 분리해야 함 |
| `A00850(A)` | `77340(outPair)`로 현재 InventorySubsystem I를 찾고 `I+3D8/+3E0` stride16 owning ItemEntity Pair 목록 순회 | 동료용 population은 해당 member rows만 읽도록 view별 source 선택 |
| `B03780(outPair,row)` | 원 SlotMetadata 생성. `model+0=row+8` UID64, `+C0`는 row index. adapter `+B0/+B8/+C0`는 stride16 model Pair vector | UID·index·멤버 scope를 혼동하지 않음. 원 아이콘/문자열/수량/instance metadata 보존 |
| `C03C20→C04A90` | adapter 소유를 Grid `+E70`에 move; 기존 adapter 정리. `P+B8`은 Grid | 두 창의 Grid/adapter/vector가 달라야 함 |
| `C05A40→9FFD80→B042D0` | same Grid의 표시 pool Slot에 model owning Pair 설치, Slot `+808/+810` 보유 | 별도 instance에서도 원 SlotNode와 정상 설치·refresh를 사용 |
| `A01B10`, `A01D20` | model `+B0` UI 선택 state, `+D4` 장착 표시. model `+8=2`와 `+B0=2`는 별개 | 동료 rows를 만들어 놓는 것만으로 원 사용/선택 경로가 준비되지는 않음 |

E1 `run63`의 public cache→actual receiver 절, E2:16–69가 핵심 원문이다. `A060B0` 생성 직후 `A00850`와 이벤트 등록이 있으므로 **나중에 화면 rows만 덮는 방식은 다음 SELF 알림에 원복/혼합된다.** Inventory `I+D8` 등록은 helper가 +8을 더한 실제 signal `I+E0`이며, capture `{A,A01AE0}`→`A01AE0→A00850→Grid refresh`다. Equipment 구독도 `A06800→A022C0`를 통해 owner `+1A0`에 연결한다. 생성·구독·해제 전체를 동료 view의 model source에 귀속시켜야 한다(E2:49–69, E3:31–39).

adapter v0 소멸자는 **`9FFAF0(RCX=A,EDX=deletingFlags)`**다. 모델/vector/문자열 정리와 `45190(A+88)→4E2B00(A)` 후 flag1이면 allocation을 해제하는 경계까지 확인했다. 두 helper가 subscriber를 어떻게 끊는지는 미확인이다. raw capture를 둔 채 별도 adapter를 먼저 파괴하는 구현은 수명 계약이 닫히지 않는다. 신규 `40960..40A18` 문자열 copy, `9FFAF0..9FFBC7` 선정 원문은 12장에 식별한다.

## 3. 장비 창·EquipmentInfoSubsystem

원 CharacterInfoLayout은 장비 슬롯과 능력치가 함께 있는 **현재 PC 창**이다. 현재 PC 전체 모델을 동료 것으로 바꿔 표시하는 관찰 API가 아니다.

| 접점 | 정적 확인 | 필요한 후킹/바인딩 |
|---|---|---|
| `15EBF0→159C70` | 원 CharacterInfo shortcut. `159C70`은 command2를 고정 전달하므로 EDX0 전달로 force-open되지 않음 | 별도 동료 owning Pair 획득 후 확인된 actual v98/command0 경계 사용 후보 |
| PC factory `92AEF0` | vptr`1214248` invoke, object vptr`1214090`/TD`175B0C0`. **RCX=callable, RDX=outPair, R8=Node* cell** | Inventory factory와 ABI 혼합 금지. resource/descriptor·Node/Pair 원 소유 보존 |
| manager `B3A290→B3A8F5` | Node 이름으로 factory 선택 후 impl`+388`/public`+348`에 게시. CharacterInfo first-name key 재사용 | 원 SELF key 덮어쓰기 없이 동료 key/별도 owning instance 관리 필요 |
| `91B660→3EB60` | CharacterDataSubsystem `+6D8` 현재 PC 모델 | 능력치/레벨/이름 등도 동료 모델이어야 함. 주인 4E38 전역 교체 금지 |
| `91B6D8→AE6C0` | EquipmentInfoSubsystem `+3D8` map의 key→itemUID | 동료 장비 projection map과 같은 view의 가입 callback 연결 |
| `91E330→91E3A0→91E430` | UI owner `+C0` key→UI index와 Slot vector를 소비. `77340→4FF8E0`으로 itemUID를 **현재 Inventory**에서 lookup | 장비 map만 분리하면 부족. 아이템 lookup도 같은 동료 inventory로 연결 |
| `4EF780` | Equipment `+3D8`의 value 또는 별도 set `+3E8`의 UID membership을 읽음 | map만 clear해 모든 model+D4가 초기화된다고 가정하지 않음 |

E4 `MAIN_REVIEW.md`:5–14, E5 `COMPANION_EQUIPMENT_EVIDENCE.md`:67 및 `appearance/own.txt`, E3:25–39. `3EB60/AE6C0/77340`은 전역 getter이므로 **함수 전체를 무조건 동료 반환으로 detour하는 안은 금지**한다. SELF UI·hotbar·tooltip·원 UseItem의 조회도 바뀐다. 동료 instance/adapter의 확인된 호출 경계에만 view context를 전달하고 원래 반환 Pair의 retain/release ABI를 지킨다. return-address 몇 개만으로 전체 scope가 완성됐다고 보지 않는다.

**Equipment native 모델을 하나 더 생성하는 경로도 정적 확인했다.** startup `E1097..E10F5`는0x440 제어블록/객체를 할당하고 object=block+10에 **`4EE860`** ctor를 호출한 뒤 **`F6A70(GI,&pair,true)`**로 GI `+180/+188/+190` stride16 subsystem vector에 게시한다. `AE6C0`는 그 vector의 타입 첫 일치를 돌려주므로 같은 타입을 뒤에 넣는 것만으로 동료 모델을 선택할 수 없다.

ctor `4EE860..4EF077`는 vptr`11C6450`/TD`166B940`, map`+3D8`와 set`+3E8`을 초기화할 뿐 아니라 **`4EECF7..4EED08`에서096B event`17F9B80`→`4EFB00`, `4EED0D..4EED1E`에서097A event`17FA480`→`4EFCD0`를 raw this/member로 전역 구독**한다. 이를 그대로 한 번 더 호출하는 것은 독립 projection allocator가 아니다. 생성/가입을 분리하거나 동료 owner용 publisher에 연결하는 경계를 먼저 닫아야 한다(12장 신규 선정).

CharacterInfo는 초기 getter 두 곳만 바꾸어 끝나지 않는다. 기존 [run177 구독 근거](../../local_server_rea_20261016/run177_status_characterinfo_subscription/)의 `91BBCB`, 갱신 `91E330`, `91E7E0` 내부 `91E813/91E9EB`, 슬롯 `91E430`, 아래 요청 callback까지 같은 instance의 모델 source가 이어져야 한다. 전체 후행 소비자의 범위를 모두 닫았다는 뜻은 아니다.

E4의 원 key→실 UI index는 `1→0 투구,11→1 목걸이,3→2 셔츠,2→3 갑옷,4→4 망토,13→5 반지,7→6 장갑,12→7 벨트,8→8 방패,9→9 무기,14→10 반지,6→11 부츠`다. 라벨 switch index(key−1)와 실 UI index는 다르다. 원 12개 정의와 현재 vector 길이, 로컬 서버가 지원하는 슬롯 수, 아이템별 직업·양손·저주·반지 규칙은 각각 별도 계약이다.

## 4. 다른 캐릭터 모델로 여는 세 방법

| 방법 | 가능 범위·첫 문제 | 판정 |
|---|---|---|
| **별도 원 창 + view별 projection** | 원 레이아웃/Slot/아이콘/수량/애니메이션 재사용. 별도 adapter rows·equipment map·CharacterData·선택/drag/tooltip가 같은 member에 귀속. factory 생성 순간의 전역 구독을 분리해야 함 | **권고 LOCAL 설계.** native subsystem 전체 복제까지 선행할 필요는 없지만 원 모델 생성/소유 ABI·이벤트 분리는 확인 필요 |
| 별도 Inventory/Equipment/CharacterData native subsystem 인스턴스 | 원 typed handler의 this를 별도 owner로 주면 의미상 분리 가능. 그러나 생성자/초기화/구독·GI 등록·해제·참조 graph 전체가 확보되지 않음 | 전체 byte memcpy/가짜 vtable/원 GI vector에 동료를 추가하는 구현은 제안하지 않음. 독립 초기화·수명이 닫힐 때만 재사용 후보 |
| 표시 중 전역 데이터 바꿔치기 | 이미 열린 SELF 창·hotbar·tooltip·ATS/AI 소비·지연 응답·가입 callback까지 같은 singleton을 읽음. 닫을 때 복원해도 중간 원 Use/저장·알림을 되돌릴 수 없음 | **불채택.** 동시 열기 요구를 충족하지 못함 |
| 서버가 동료 `0964/0965/0978/096B/097A`를 일반 socket으로 송신 | 이 packet에는 소유 캐릭터/창 ID가 없음. 현재 등록된 SELF Inventory/Equipment 수신자가 소비 | **그대로는 불가.** 창을 foreground로 올리거나 최근 open 대상을 바꾸어 구분할 수 없음 |
| 동료 scope를 가진 별도 게시 → 분리 모델에만 원 payload 해석 | host가 대상 member와 소유 view를 지정한 모델 게시로 전달. 원 opcode/body를 payload의 내부 표현으로 재사용할 수는 있음 | **권고 운반 경계.** 실제 SELF socket packet과 구분한 LOCAL 게시이며 원 wire에 owner 필드를 몰래 추가하는 방식이 아님 |

원 raw packet에는 없는 정보가 필요하므로 `097A.f2`에 actorUID를 넣거나 `0964.ItemInfo.f1`을 임의 proxy UID로 바꾸지 않는다. slot key·itemUID·actorUID·영구 character ID를 그대로 구별한다. 같은 숫자 UID가 두 저장에 나타나더라도 view별 lookup 결과를 사용한다.

## 5. 서버 통지와 view별 적용

| 통지 | 확인된 schema/consumer | 동료 창에 적용할 때 |
|---|---|---|
| S2C `0964 SC_ADD_INVENTORY_NOTI` | repeated f1 ItemInfo. ItemInfo f1 UIDu32, f2 templatei32, f4 Q u64, f5 raw discriminatori32. **outer f2=false로 확인된 분기**는 현재 Inventory 행 append | 동료 full rows를 SELF receiver에 넣지 않음. 다른 f2 분기를 동료 모델 선택 API로 가정하지 않음 |
| S2C `0965 SC_UPDATE_INVENTORY_NOTI` | 기존 UID의 ItemInfo field 갱신; 현재 rows의 알림/refresh | delta는 존재하는 같은 member row에 적용. 없는 UID 생성·Use 성공 ACK로 취급하지 않음 |
| S2C `0978 SC_REMOVE_INVENTORY_NOTI` | f1 UID 행 제거 | Q0 통지와 삭제를 구분. anchor/저장 처리는 기존 서버 계약 유지 |
| S2C `096B SC_EQUIP_LIST_NOTI` | outer f1 repeated ItemEquipInfo; child required f1 UIDu32/f2 keyi32, optional f3 bool/f4 ItemInfo. `4EFB00`은 `+3D8`에 **clear 없이 unique insert** | 빈096B를 clear/full replacement로 쓰지 않음. 새 분리 model의 최초 population 또는 명시 LOCAL snapshot replace를 구분 |
| S2C `097A SC_EQUIP_CHANGE_NOTI` | required f1 UIDu64/f2 keyi32/f3 bool, mask7. `4EFCD0` true→`4F1410` unique insert, false→key/−1 알림 후 key erase. `4F2A50→A01D20`이 같은 UID model+D4 갱신 | 점유 key에 true만 보내면 old map/new badge 불일치 가능. 기존 model과 backend 전이를 일치시킨 해제→장착 projection 필요. 이 순서를 공식 서버 규칙이라고 주장하지 않음 |
| S2C `4E38` | 현재 PC의 상태/능력치 모델 경로 | 동료 능력치 snapshot을 별도 CharacterData projection으로 전달. f1만 동료UID로 바꾼 socket 송신은 분리 모델 API 아님 |
| S2C `4ED5 SC_WIELD_NOTI` | required f1 ActorUIDu32/f2 무기 **동작군**u32. `4FC20→4FD28 Action+40` | 동일 동료 actor의 공개 외형 갱신에 정상 actor 경로 사용 가능. item 소유/장비 저장/장비창 갱신의 대체가 아님. live0도 store |

E2/E3/E4/E5의 typed parser·consumer를 재사용한다. `096B` f4의 ItemInfo가 존재한다는 것만으로 companion Inventory rows가 자동 생성된다고 보지 않는다. 장비 map value를 풀 때는 같은 동료 inventory가 이미 준비되어야 한다. 처음 열기는 동료 rows→equipment map/능력치→원 refresh 순서, 변경은 서버 commit 이후 해당 view에만 projection을 게시하는 LOCAL 순서로 설계한다. 공식 모든 응답 순서·ACK는 미확인이다.

Inventory 수신 hook 후보의 정확한 정적 경계는 다음과 같다. 모두 동료 식별자를 자체 해석하는 경로가 아니다.

| 통지 | 등록/consumer RVA | 실제 현재 모델 소비 |
|---|---|---|
|0964|`4FB7DA..4FB7EB`, event`17F9700`→`4F5B00`|위 f2=false 분기 `77340→509390→3DF600` append. [run30](../../local_server_rea_20261016/run30_inventory_first_wire/findings.md):13–23|
|0965|`4FB848..4FB859`, event`17F97C0`→`4F7670`|같은 UID의 기존 row, present f4를 row+28의 **절대 Q**로 저장. [run41](../../local_server_rea_20261016/run41_inventory_update/worker/findings.md):31–55|
|0978|`4FB806..4FB81C`, event`17FA300`→`4F6920`|`4F69CD→77340` 현재 rows lookup, `4F6ED5..4F6EFB` compaction/end−16. [run98](../../local_server_rea_20261016/run98_item_drop_pickup_contract/saved_consumers/findings.md):19–25|

이 subscriber에 동료 모델을 넣으려면 등록 owner·내부 전역 getter·발행 event까지 scope를 분리해야 한다. `this` 하나만 바꾼 재호출로 충분하다고 주장하지 않는다.

## 6. 드래그: 주인→동료, 동료→주인

**주인 가방→월드의 동료 배우:** 원 `A0ADB0→627B0(ActorsSubsystem,outPair,fullUID)→586E0(InteractionComponent)→B7690`의 predicate 양성 뒤 `3D0F0(target,item,Q)→27D620`이 **C2S `4EF5 CS_GIVE_REQ`**를 보낸다. required `f1:u32 대상ActorUID, f2:u32 주인 itemUID, f3:u64 Q`, mask7이다. `3D661/3D676/3D665`가 필드를 저장하고 `3D6A4`가 송신한다. f21 nonempty 배우의 Interaction+80=20은 B7690 bitmap0x101440의 허용 bit20과 정적으로 연결된다. 나머지 current/local actor·Action+46·거리/맵·수량 조건도 필요하다(E5 trade:44–56).

`B7690=false`의 원 분기는 `3CF00→4E3F DROP`이다. **동료 창으로의 드래그를 월드 DROP으로 fallthrough시키면 안 된다.** 동료 창의 Slot/배경 drop target은 원 월드 actor target과 다른 입력이므로, DLL은 source view와 destination view를 모두 해석한 뒤 LOCAL give 의도로 넘긴다. 원 월드 actor drop은 기존4EF5를 그대로 재사용할 수 있다. 창 drop에서 원 sender를 직접 호출할 때도 원 target/current/row/Q 조건을 우회하거나 임의 protobuf bytes를 원 sender ABI로 전달하지 않는다.

**동료 가방→주인 가방:** 원4EF5에는 sourceCharacter 필드가 없다. 로그인된 주인의 요청에서 동료 itemUID만 넣어 보내는 것은 동료가 송신한 것과 같지 않다. 동료 source Slot의 정상 drag callback에서 원 GIVE/DROP을 소비하고, `(source=member, destination=인증 주인, itemUID, Q)` LOCAL 꺼내기 요청으로 연결한다. 주인→동료 창 drop도 같은 현재 거래 소유자의 반대 방향 작업이다. 임의 UID 변환·주인 bag 임시 삽입·가짜 actor 송신으로 해결하지 않는다.

수량1과 원 quantity popup callback을 구분한다. popup 생성 순간 source/destination view·실제 itemUID를 보유하고, 확인/취소/창 닫힘 때 같은 원 callback 소유를 종료한다. 늦은 확인을 새 동료/재사용된 Slot의 거래로 적용하지 않는다. 전체 popup ABI·창 간 drop registration은 아직 미확인이다. wire Q u64와 원 UI가 선택할 수 있는 수량 범위를 동일하다고 가정하지 않는다.

**신규 정적 hook/수량 접점:**

| 접점 | 확인 ABI/명령 | 동료 확장 |
|---|---|---|
| `A0D440→A0ADB0` drag thunk | RCX=callable, RDX=move할 Pair16*, R8=position8B 주소. incoming Pair를0으로 move 후 member에 RCX=보정P, RDX=local Pair, **R8=position8B 값** 전달 | thunk의 pointer ABI와 member의 값 ABI 구별. source P/adapter에서 동료 view 판별 |
| `A00470(A,outVector24B)` | adapter v40의 선택 index→A+B0 model Pair retain/copy | source UID는 그 view의 선택 모델에서 얻음 |
| GIVE callable vptr`12229F0`, invoke`A0D270` | RCX=capture32B(+8 targetUID,+10 itemUID,+18 Q64), RDX=string32. 검증·parse 후 `3D0F0`, AL1 반환 | capture에 source member/view가 없다. 역take는 popup 생성 전 source context와 별도 callback 필요 |
| `A0D2D4/A0D2D6` | 유효 전체문자열·err0·positive signed32 입력에 **signed min(input,capturedQ low32)** 선택, `A0D2E1` sign-extend→sender | DROP callback `A0D160`과 같은 parser/상한이라고 쓰지 않음. low32 이외 큰 Q의 정상 UI 범위는 미확인 |

원 DROP `3CF00(RCX=itemUID,RDX=coordinate*,R8=Q)`의4E3F schema는 outer f1 repeated child, child required f1/f2 좌표i32·f3 inventoryUIDu64·f4 Qu64다([run98 drop](../../local_server_rea_20261016/run98_item_drop_pickup_contract/worker/findings.md):9–25). **4EF5 itemUID는u32,4E3F itemUID는u64**인 차이도 보존한다. drag/quantity 신규 선정은 12장에 보존하며 popup 원생성·취소·창 간 target 전체 수명을 닫은 결과는 아니다.

## 7. 착용·해제 클릭과 요청 귀속

인벤토리 원 사용은 `A0BF80→95C4C0` 등록→`953890→A0C0B0`이며 **RDX는 `&Node*` cell**이다. 원 Slot metadata Pair를 보유하고 model+B0==2 등 원 조건 뒤 `77340→4FD260(Inventory*,UID64)`로 들어간다. 실제 Entity+50 raw에 따라 params가 생성되고, 기본 handler `52A410`은 **C2S `0960 CS_USE_ITEM_REQ` required f1 itemUIDu64/f2 UseItemReqParam**을 구성한다. f15/f16은 원래 absent일 때만 present0을 보충한다. raw0의 `4FE1FC→4FE520→4FE630`에서 nested f1=1/f17 absent를 확인한 것을 모든 장비 raw에 확대하지 않는다(E4 equip_source:7–13).

**CharacterInfo 장비 슬롯의 직접 요청 경로는 새로 구분했다.** 기존 [run162 init 원문](../../local_server_rea_20261016/run162_shield_effective_ac/worker/body-91b1c0.json)의 ordinal180–196, `91B4FC..91B549`는 callable vptr`12137B0`와`1213740`을`95DDD0`에 등록한다. 첫 callable actual+10=**`921AF0`**가 `95C4C0`에 first `12137E8/921D60`, second **`1213778/921C20`**를 설치한다. 둘째 listener 분기의 `921C20`은 SlotNode cast→Slot`+808/+810` owning metadata→model UID≠−1→**`77340→4FE520(Inventory*,UID64)`**으로 직접 들어간다. 핵심은 `921C8C call77340`, `921C98 call4FE520`이다. first 쪽921D60과 다른1213740/921A60은 layout vC8/vC0 tail이며 착용 요청으로 명명하지 않는다.

`921C20`도 **RDX=`&Node*` cell**이다(`921C2F mov rcx,[rdx]`). incoming RCX capture는 이 선정 본문에서 읽지 않으므로, 전역 hook에서 RCX를 CharacterInfo instance라고 cast하면 안 된다. 동료/SELF 판별은 별도 보유한 창→Slot/Node 귀속에서 수행하고, 동료 슬롯에만 LOCAL 장비 의도를 생산하는 callback으로 분기한다. 원 cast/metadata/control 정상 소유를 임의 포인터로 대체하지 않는다.

이 직접 경로에는 **Inventory `4FD260/raw switch`와 model+B0==2 조건을 덧붙이지 않는다.** `4FE520` 자체의 params 생성은 nested f1:i32=1 present/f17 absent다([run40](../../local_server_rea_20261016/run40_item_raw0_branch/findings.md):7–19). 이후 원 `4FE630` pending/gate와 `4FE820`의 현재 row/handler 조건을 통과하고 기본 sender가 선택돼야 `52A716 EDX=0960→52A71F call27D620`으로 이어진다([run37](../../local_server_rea_20261016/run37_item_command_sender/findings.md):11–33). callback 반환은 송신·해제 성공의 증거가 아니다. 요청에 actorUID·slotkey·명시 equip bool이 추가되는 근거도 없다.

동료 view에서는 원 현재-PC Use를 먼저 보내고 서버가 나중에 대상을 바꾸게 하지 않는다. **현재 view 소유와 itemUID가 아직 결속된 Slot callback 경계에서 원 요청을 소비**하여 동료 장비 의도로 바꾼다. 전역 `52A410/27D620`에서 ‘마지막 연 창’으로 owner를 추정하는 hook은 주인 일반 use/소모품/시전과 충돌한다. SELF callback은 원본 그대로 둔다.

LOCAL 서버 요청은 동일 동료의 현재 장착 상태를 바탕으로 명시 `equip/unequip` 의도를 처리하는 방향을 권고한다. 기존 `CompanionInventory.equip(member,itemUID,automatic=False)`는 **같은 item이면 해제, 다른 item이면 교체하는 toggle**이므로 반복/지연 클릭을 명시 set 상태와 같다고 보지 않는다. 현재 구현을 호출하는 adapter가 원하는 전이와 실제 현재 장비를 일치시켜야 한다. UI D4만 먼저 바꾸거나 `097A`를 가짜 성공으로 만드는 방식은 사용하지 않는다.

## 8. DLL·서버 구현 단계

| 단계 | DLL 소유 작업 | 서버 소유 작업·완료 경계 |
|---|---|---|
| 1. instance/모델 | Inventory와 CharacterInfo 원 factory·owning Pair·Node를 별도 생성/보유할 경계 확인. 원 SELF cache를 교체하지 않고 동료 instance 두 개 관리. 초기 population/구독부터 member source 분리 | 기존 실제 법사 inventory/equipment/attributes 읽기 서비스를 view용 snapshot으로 제공. 별도 bag 저장 포맷 생성 없음 |
| 2. 조회·표시 | view별 Inventory rows/Equipment map/CharacterData를 연결, 정상 Grid/Slot refresh·원 visible/close 사용. PC event가 동료 adapter를 덮지 않음 | open 시 같은 실제 저장 캐릭터의 모델 게시. 주인4E38/0964와 혼합 송신하지 않음 |
| 3. 원 입력 분기 | Pet `A84020`의 `bag-open-take`, `A83F40`의 `equipment-open` 의도 소비. 가방/장비 각각 자기 instance show. 가방 use·장비 slot·drag/drop·popup을 source view에 결속 | 선택적 UI adapter가 open/take/give/equip/unequip을 기존 거래/장비 서비스로 연결. 없는 adapter는 미지원으로 끝내고 일반 서버 유지 |
| 4. 양방향 저장 | commit 전 표시 성공으로 확정하지 않음. 수신 projection으로 실제 아이콘/수량/슬롯 갱신 | 기존 give와 앞으로 복구 intent 재사용; **역방향 take는 신규**. 양쪽 bag/CAS·장비 anchor·중량·UID·자동착용·AI 소비와 같은 저장 사용 |
| 5. 수명·동시성 | 창별 위치/visible/선택/drag/tooltip/popup·callback owner 분리. 일반 펫/SELF 복귀·hide/dtor/unmap 후 원 정리. detour runtime unload는 기존 후보처럼 별도 미지원 | 해산/재소환·주인 전환·재접속 때 기존 actor/member/current 수명에 맞춰 게시. 늦은 projection을 다른 view에 쓰지 않음 |

브리지 현재 범위(E7): Pet 7행의 두 open 신호는 있으나 실제 view/model consumer가 없다. `4F02` body는 `f1=7, repeated f2=["LOCAL_COMPANION_UI_V1",operation,args...], f3=동료 actor low32`인 **LOCAL 확장**이고 원 protobuf sender ABI는 미확정이다. 현재는 UI queue→owned file IPC·독립 codec 초안까지며 host reader/서버 router/UI model publisher가 미연결이다. `.bin`은 opcode/암호화 frame이 아닌 body다.

현재 inbound `own-companion-request-v1`은 literal 순서 고정·**1024B 상한**이며 whitelist에 bag snapshot 적용 명령이 없다. 전체 가방을 그 필드에 억지로 넣거나 기존 `ats-apply`를 가방 apply로 재사용하지 않는다. **기존 owned host/bridge serial과 run directory를 공유하는 별도 typed model payload 확장**이 필요하다. 내용은 대상 member/현재 view 귀속, 실제 rows·장비·능력치 및 기존 상태 전이에 필요한 모델 식별을 담되 정확한 binary/파일 참조 형식은 후속 구현 계약으로 남긴다. 새 포트·polling 서비스·두 번째 큐/원장·요청마다 해시/핀 검사를 추가하지 않는다. 생성/해제는 기존 UI thread에서 수행한다.

서버 현재 상태(L1): `world_feature_trade.py:54`의4EF5 handler는 선택적 `give_provider`를 찾는다. 실제 서비스는 import shim 뒤 **`world_companion_inventory.py`**에 분리되어 있다. `give:156`은 소스 메타데이터 보존/동일 stack 합침·수용 중량을 확인하고, `companion-transfer.json` durable intent→`_finish:51`의 **debit-before-credit 두 CAS**→동료 `equip(automatic=True)`·refresh로 진행한다. 두 캐릭터가 한 번에 원자 commit되는 구현이라고 쓰지 않는다. 역take는 없고 `equip:121`은 Python 서비스이지 동료 창 클릭 receiver가 아니다. `refresh:99`의4ED5는 동료 무기군 공개 통지다. 기존 원 warehouse atomic-file helper 사용은 거래 저장 재사용이며 **창고 UI 재사용이 아니다.**

역take 최초 정책은 장착품 거절→동료 장비창에서 정당 해제→다시 꺼내기를 권고한다(LOCAL). commit 중 실패는 기존 intent/부분 상태를 보존하고 앞으로 복구하며 refund/되감기/재소비로 숨기지 않는다. 실제 법사로 직접 선택했을 때도 같은 가방/장비여야 한다. AI의 물약/아이템 소비와 수량이 바뀌면 열린 view도 실제 새 결과를 받는다.

새 기능은 독립 `world_feature_*` 및 선택적 provider/hook으로 연결하고 `FEATURE_MODULES`에서 빼도 일반 서버가 동작하게 한다. 다른 기능 모듈의 ctx 메서드 직접 호출·기존 METHODS 이름 덮어쓰기·공통 코어 새 필수 호출을 만들지 않는다. 이번 문서는 공유 파일이나 FEATURE_MODULES를 수정하지 않았다.

## 9. 동시에 열 때의 충돌·수명

| 위험 | 구체 처리/아직 확인할 것 |
|---|---|
| 동일 manager key가 SELF instance를 반환 | 별도 두 동료 owning instance 필요. 원 key 전체를 rename하거나 SELF public entry를 교체하지 않음. 별도 resource/descriptor 등록의 정확한 지원 범위는 OPEN |
| 동료 adapter가 SELF Inventory/Equipment event를 구독 | 생성 시점의 source 선택과 원 unsubscribe/퇴역을 함께 연결. rows 교체만으로 완료 처리하지 않음 |
| 전역 getter hook이 hotbar·Use/tooltip에 전파 | 확인된 동료 instance callback에만 scope. raw global/tls를 영구 동료로 바꾸지 않음. 재진입·callback lifetime 별도 확인 |
| 장비 map과 가방 UID/selection이 다른 member | 두 창은 같은 member 모델을 공유하되 Slot/선택/drag 상태는 창별 소유. 장비→아이템 lookup도 그 member로 귀속 |
| singleton input manager의 capture/drag가 서로 덮임 | 원 focus/z-order/capture routing 유지. 네 창의 hit·drag source/destination·popup owner 확인 필요. 사용자 전역 입력이나 cursor 조작으로 해결하지 않음 |
| 097A unique insert·096B empty 처리 | 명시 local projection 전이로 map와D4를 일치. SELF 수신자에 동료 reset/clear 보내지 않음 |
| 닫힌 창·해산 뒤 callback/응답 사용 | 원 Node/Pair/row/control 소유를 반환까지 유지하고 기존 view 퇴역에 따라 정리. hide와 소멸·모델 수명은 다름. raw P/Slot을 영구 캐시하지 않음 |
| 주인/동료 이름·능력치·도움말이 혼합 | 제목만 동료로 바꾼 성공을 인정하지 않음. 같은 member의 CharacterData·장비·아이템과 description 소비 확인 |

## 10. 검증 계획과 판정

**이번 정적 문서 판정:** 원 PC 창/모델·wire·입력 경계의 확인과 동료 격리 구현안이다. 별도 동료 창 생성·입력·송수신·저장·렌더링 PASS가 아니다. 실행 없는 작업이므로 빌드/서버 테스트를 추가하지 않는다.

후속 구현의 필요한 확인은 기존 시험 흐름을 재사용해 다음 범위로 한 번 연결한다. 게임·포트는 기존 owned non-input desktop/Job을 쓰는 시험 worker 하나가 순차 소유한다. HEADLESS 화면과 패킷·저장 판정은 서로 분리한다.

1. 정상 로그인→캐릭터 선택→월드→실제 법사 동료 소환→펫7행의 가방/장비 각각 열기. 주인 가방/장비도 열어 **네 원 창**의 서로 다른 내용·위치·닫기·재열기를 확인한다.
2. 주인→동료 월드 actor 드래그와 창 간 drag를 구분해 Q1/Q다수/취소를 확인한다. 실제4EF5 또는 명시 LOCAL 요청→양쪽 실제 bag 수량/UID/저장→해당 view 반영을 연결한다. DROP4E3F로 떨어지지 않는지 본다.
3. 동료→주인 역take, 장착품 거절, 정당 해제 뒤 take를 확인한다. 과거 popup·해산 뒤 확인·재소환 뒤 응답은 기존 수명과 실제 결과대로 거절/정리한다.
4. 동료 가방 착용과 장비 슬롯 해제를 각각 원 입력으로 확인한다. 실제 요청 소비→동료 장비 CAS/능력치/중량→같은 actor4ED5→아이콘/배지/무기 태세를 확인한다. SELF0960/장비 변경이 섞이지 않아야 한다.
5. 정상 저장·재접속·동료를 직접 법사로 선택해 같은 inventory/equipment 복원을 확인한다. AI 소비 중 열린 창, 닫기/재열기·일반 펫 대조·원 Quit/FIRSTclose/부분 보존까지 판정한다.

향후 **헤드리스 원본 스크린샷**은 가방/장비 분리·네 창 동시표시·실아이콘/수량/이름·slot/tooltip·해제 표시·z-order·modal/hit 영역을 확인하는 데 사용한다. 패킷 통과가 화면 성공을 증명하지 않으며, PNG만으로 drag caller·서버 commit·저장/복원 성공을 주장하지 않는다. 강제 cleanup이면 정상 종료와 구분한다.

## 11. 미확인과 다음 최소 정적 입력

| 미완 계약 | 필요한 최소 입력/담당 |
|---|---|
| 동일 원 자원으로 두 번째 Inventory/CharacterInfo instance를 안전하게 보유/게시 | DLL: `A0D640/92AEF0` 정상 호출부·`B3A290`의 descriptor/owner를 좁혀 별도 key/instance와 원 close retirement 확정 |
| adapter 최초 population·subscriber/dtor 격리 | DLL: `A060B0/A00850/9FFAF0`과 `45190(A+88)/4E2B00`, CharacterInfo 초기 subscription/소멸을 같은 instance에 결속. Equipment ctor `4EE860` 전역 가입도 분리 |
| 동료 native ItemEntity/SlotMetadata/CharacterData 생산 ABI | DLL: 기존 B03780 및 능력치 row/Pair 생성·정상 해제 재사용. opaque 메타데이터를 임의0으로 채우지 않음 |
| 창 간 drag source/destination·수량 popup의 정확 ABI | DLL: `A0ADB0` 등록 thunk와 callback capture·원 quantity 경계. 원 월드 GIVE와 별도로 확인 |
| 모델 게시/역take/명시 장비 요청 receiver | 서버+DLL: E7의 현재 작은 control·미연결 host consumer를 확장. 기존 service/저장 소유자에 선택적 연결 |
| 실제 네 창 동시 입력·수명/정리·공식 제한 | 후속 원본 실행: 최소 위 순서의 실제 caller/응답/표시/저장 확인. 이번에는 UNRUN |

원 actor/member 인수만으로 이 두 원 창을 여는 완성 API, 전체 native subsystem 복제 초기화, 모든 장비 raw/프로토타입·공식 서버 교체 순서, 모든 tooltip/drop/popup 소비자의 view 분리는 미확인으로 남긴다. 확인된 함수/packet 목록을 동료 기능 완성으로 확대하지 않는다.

## 12. 신규 정적 선정과 문서 검증

추가 산출물/분석 스크립트는 만들지 않았다. 기존 `run406_companion_equipment/trade/extract.py`의 reader/Capstone 원리를 메모리에서 재사용하고 **그 스크립트의 파일 쓰기 CLI 분기는 실행하지 않았다.** worker의 새 해독과 main의 선정 바이트·핵심 명령 확인을 구분했다. 아래 `[start,end)` 10구간 **5,427B**는 frozen exec-buffer의 `[RVA−1000h]`와 carrier PE section raw bytes가 모두 같았다. CONTROL 전체/현재 loaded image 확인이 아니다.

| 선정 RVA | B | SHA256 |
|---|---:|---|
|40960..40A18|184|86ef7abbb2e9d28ad999e00bbe4b84e810046616bc3fb403497282c910932b92|
|A0D440..A0D484|68|ed7c89e71138c4aa7dca13e29294a39e700bcbd57cb6ea46c2a3abd32dcfe0ec|
|A00470..A00846|982|e7eda45bd257a9deee032ab4f926926463d66872866313c5df077af706afacc4|
|9FFAF0..9FFBC7|215|4deccf31df0fb35cb13a3670862478f9a5f8153994eb3cc76a59c94d99d49822|
|A0D270..A0D2FB|139|66c0baadcf210ec8dab7672bb6e9f6b65ebf16289ce4ded3668ca176266729b5|
|4EE860..4EF077|2071|671746415510beb78d3d81ac2fed6fc209ae33ad09f6e31211e955f5609efccc|
|E1097..E10F5|94|e77504360f4d2aa51c6f0a08286711d361555d180c7255aff48cd5c96dfd0f9f|
|F6A70..F6F4F|1247|00c23e2b13be6594e94af3a23e1d521310a8c5636d4c7ba9f725706772569fe8|
|921AF0..921BAD|189|bb5108c84c1aa0dd51ebcb147b77275696a4ab974be5165359d84361487f5108|
|921C20..921D0E|238|ea42423d5197f3a7b44f35d579eb10c5fb39b7e019a0f78885df75c4b99c2e22|

metadata 확인은 adapter vptr`1221E28`, GIVE callable`12229F0` 및 drag callable`12229B8`, CharacterInfo callable `12137B0+10=921AF0`, `1213778+10=921C20`, `1213740+10=921A60`, `12137E8+10=921D60`이다. carrier pointer는 base를 빼 RVA로 읽는다. 새 이름·vtable patch를 원본에 쓰지 않았다.

대표 두 callback의 원문을 다시 읽는 명령(출력은 명령 텍스트뿐, 파일 생성/게임 실행 없음):

```powershell
@'
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, 'C:/Users/Chansol/Documents/Codex/2026-09-07/d-lineage-classic/work/static_client/deps')
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
c = Path('work/local_server_rea_20261016/run104_skill_buff_contract/wire_schema/exec-buffer.bin').read_bytes()
m = Cs(CS_ARCH_X86, CS_MODE_64)
for a, e in [(0x921c20,0x921d0e),(0xa0d270,0xa0d2fb)]:
    for i in m.disasm(c[a-0x1000:e-0x1000], a):
        print(hex(i.address), i.mnemonic, i.op_str)
'@ | python -X utf8 -B -
```

main 확인 결과: 위 두 구간의 `921C2F/921C8C/921C98` Node cell/getter/직접 요청, `A0D2D4/A0D2D6/A0D2E1` signed min/sign-extension 및10구간 carrier equality·선정 hash **일치**, exit0. 빌드/원본 실행·캡처·실제 장비/거래/동시창은 **UNRUN**이다.

문서만 확인한 명령은 `python -X utf8 -B -` here-string으로 UTF-8 decode·상대 Markdown 링크 resolve·행 끝 공백을 읽은 것이다. 결과 **UTF-8 OK, 로컬 링크25개 누락0, 행 끝 공백0**이다. `git diff --check -- work/local_original_session/game-core-prep/COMPANION_BAG_WINDOW_DESIGN.md`는 exit0이나 이 문서는 기존 work ignore 대상이므로 실제 본문 공백 확인은 위 읽기 결과에 근거한다. `git check-ignore -- <동일경로>`도 해당 경로를 반환했다. 원 ignore/추적 정책은 변경하지 않았다.
