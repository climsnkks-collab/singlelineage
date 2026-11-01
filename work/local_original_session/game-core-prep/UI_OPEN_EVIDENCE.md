# 원본 UI 열기·단축 슬롯의 정적 근거

2026-10-27. `reverse-engineer-anything`의 관찰/추정/UNKNOWN 구분을 적용했다. **요청한 5경로 모두 원 진입·주요 소비 주소를 확보했다(5/5). 무인 bridge의 실제 호출·창 표시·입력·정상 닫기 확인은 0/5이며 모두 UNKNOWN이다.** 마법/스탯은 원 no-argument shortcut 전체 함수 2/5, 두루마리/펫/단축 슬롯은 현재 소유 객체·UID/슬롯에 결속해야 하는 경로 3/5다. 이 분모는 정적 계약의 구분이며 기능 완료율이 아니다.

게임·서버·포트·live attach·원 함수 실행·입력 전송·캡처·commit을 하지 않았다. 쓰기는 이 문서 하나다. 기존 dirty 파일과 원본은 보존했다. 공유 REA MCP가 제공되지 않아 기존 원문 및 이미 설치된 Python pefile/Capstone으로 보존 carrier만 읽었다. 새 연결·설치·분석 DB를 만들지 않았다.

## 고정 신원과 주소

- 원본 신원: `D:/Lineage Classic/LC.exe`, 39,144,728B, SHA256 `9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`. 보존 CONTROL `work/config_startup_trial/control.snapshot.bin`과 같은 기존 신원이다. 버전/자원 기준은 **26.09.29.2001**이다.
- 이번 신규 정적 읽기: `work/rea_lineage_resume_20261013/main-gameplay/audit/metadata-v2/DERIVED_RESTORED_ANALYSIS_ONLY.exe`, 26,021,376B, 기존 SHA256 `c822838351d774a2022af434829a36dbd9bee030bf22182b834ca4e8659701a9`. 신원은 같은 폴더 `MANIFEST.json#/shipped_original` 및 [TARGET_IDENTITY](../../local_server_rea_20261016/TARGET_IDENTITY.md)를 승계하며 전파일 해시 재검사는 하지 않았다.
- 모든 아래 주소는 **RVA**, VA=`140000000+RVA`다. carrier는 분석용 파생 PE이며 실행용 LC 자체가 아니다. 현재 packed LC.guard/loaded memory와의 전체 동일성은 확인하지 않았다. 신규 명령은 carrier `.rea1`의 RVA1000/file400 mapping, RTTI/테이블은 PE section mapping, 함수 경계는 `.rea4` PData로 확인했다. partial span은 전체 함수 분석이라고 표시하지 않는다.

## 5경로의 계약

| 경로 | 원 주소·ABI/this·실제 path | 현재 판정·최소 다음 관측 |
|---|---|---|
| 배운 마법 목록 창 | **`15EAF0()`** 원 `ShortcutRegistry::InitUIShortcut lambda4`의 `void()` whole invoke. incoming RCX/RDX/R8을 소비하지 않고 `560F0(outPair)`로 manager를 보유, empty any64를 만들고 **`159F90(manager,2,&any64)`** 호출/정상 정리. `159F90`은 `SpellLayout` public cache 조회 또는 B38B00 get/create, typed Pair 보유→actual v98에 command 전달. PC `SpellLayoutPCImpl` vptr12341C8.v98는 **A11810**. 원 cmd2는 toggle다. | 정적 전체 shortcut 양성. 이미 보이는 창은 닫힐 수 있으므로 `open`이라는 명칭만으로 열린 상태라 판정하지 않는다. current ready/UI thread 아래 실제 호출→same layout own-visible/화면→원 close 관측 필요. 배운 목록은 기존 4E60→5B19B0의 client map 소비가 별도이며 창 열기만으로 학습 표시를 보증하지 않는다. |
| 말하는 두루마리 목적지 | 원 Inventory 사용 **A0C0B0→4FD260(Inventory*,fullUID)**. raw133 case **4FE125**는 actualUID를 Inventory+578에 저장하고 **5027B0(Inventory*)** 호출. **5027B0의 RCX는 UID가 아니다.** manager/typed TeleportBookLayout Pair→vA0 **B23B10**의 command0→**B23D30(layout,UID,true)**, UID는 layout+C8에 저장. 처음 사용은 로컬 목록이며 0960 대기 없음. 선택 callback B26810→4FE630→0960, 이후503B00 command1 close. | 기존 [TALK_SCROLL_EVIDENCE](TALK_SCROLL_EVIDENCE.md:35) 재사용. wire **ItemInfo.f5=133**→Entity+50 interaction discriminator와 catalog **CommonItemInfo.f4=133**을 구분한다. item template12273과 inventory instanceUID도 구분. group은 catalog.f53=10,95행이다. 현재 ownedUID→raw133 사용→실창/선택→0960 ordinal→원 close가 최소 관측이며 UNKNOWN. |
| 스탯 창 | **`15EBF0()`** 원 InitUIShortcut lambda3의 whole `void()` invoke. `560F0` manager Pair→empty any64→**159C70(manager,unusedEDX,&any)**→CharacterInfoLayout typed Pair→v98 **EDX=2 고정**→PC vptr1214090.v98 **A11810**. 따라서159C70에EDX0을 줘도 force-open이 아니다. | [run243/source/contract.md](../../local_server_rea_20261016/run243_equipment_normal_input/source/contract.md) 재사용. magic과 같은 toggle/실창 UNKNOWN. 공통A11810 cmd0 show/1 hide/2 toggle, visible predicate A117D0은 P+30 Q의 actual v150을 읽는다. 이를 다른 타입/소유의 P에 적용하지 않는다. full4E38 수신·표시값과 보너스4F0F/4F10은 별도 [SELFINFO_FIELDS_EVIDENCE](SELFINFO_FIELDS_EVIDENCE.md). |
| 펫 통계 창/4F13 | **B8710(Actor*)**, RCX는 실제 Actor 포인터다. 원 B6D20은 Interaction+8 Actor를 holder→B9990이 RCX로 꺼내 B8710 invoke. 원 current111740 Pair/target42EC0 Transform의 문자열 guard 보존, actor.v8 반환 low32를4F13.f1에 넣어27D620 송신. fresh actor lookup은 **`627B0(ActorsSubsystem*,Pair16*out,uint64 fullUID) -> out`**. 응답4F14 `2FB970→318440→event1801C80→54BDF0`, f2=1 PetLayout/2 SummonLayout을 선택. | [run270](../../local_server_rea_20261016/run270_pet_callback_installer_join/source/contract.md), [PET_EVIDENCE](PET_EVIDENCE.md:9) 재사용. Lookup627B0의 정확 ABI/return을 새 확인했다. callee가 actor control+8을 retain하며 wholeB8710 RET까지 actor Pair를 보유하고 정상 release해야 한다. directB8710은 개발용 원 callee 호출이며 원 click 관측이 아니다. 정당 current petUID→lookup→request→sameUID4F14→실창/원 close가 UNKNOWN. |
| 단축 슬롯 마법 시전 | **`9DC8D0(Pair16*out) -> out`**로 current `HudSlotDataSubsystem` owning Pair. **`59B630(HudSlotDataSubsystem*,int32 slot)`**가 currentpage subsystem+40와 signed slot%8로 **page*8+slot%8** tree+20 key를 찾고 실제 row를 보유. row.kind+8=1이면 actual key DWORD0→AE360 Spell Pair→5B66F0에 따라 ownActor5B63A0 또는 whole5B5A70. kind2는원아이템, 다른kind는원분기이며 임의마법으로 바꾸지 않는다. | 새 정적 UI caller9DEBA0/9E22A0는 SlotNode+808/810 metadata Pair의+C0 index를 넘긴다. **원 page당8칸, 인덱스0..7**. 요청0..9를10칸으로 취급하면8→0/9→1 alias다. mapkey miss는59BC58 원 error helper/INT3 경로라 단순 no-op이 아니다. currentpage/실row.kind/key·원callback/실4EE6·MP/효과/취소는 UNKNOWN. 원 row 없는 상태에서 추측 슬롯을 호출하지 않는다. |

## 신규 정적 원문 핵심

마법 shortcut의 RTTI 연결: `TD16DAF70` NUL string은 `std::_Func_impl_no_alloc<ShortcutRegistry::InitUIShortcut lambda4,void>` 문맥이다. COL1286FC8→vptr1188940의 slot10=15EAF0. `1581E8 LEA1188940`로 callable을 만들고 `15823E EDX=2008E`,158246→1578B0 등록이다. **2008E를 Win32 VK나 물리 단축키라고 해석하지 않는다.** 원문은 다음과 같다.

```text
15EAFA lea rcx,[rsp+20]       15EAFF call560F0
15EB05 mov rcx,[rax]         15EB0C/12 zero ymm->[rsp+30/+50]
15EB18 lea r8,[rsp+30]       15EB1D mov edx,2
15EB25 call159F90            15EB2B..9E any/manager cleanup;RET
159FC3 save R8               159FC7 save EDX
15A11C LEA TD1670EA0(SpellLayout);15A123 LEA TD166A190(LayoutBase)
15A220 mov rax,[rsi]         15A223 restoreR8
15A227 restoreEDX            15A22A mov rcx,rsi
15A22D call[rax+98]          15A234..293 Pair cleanup;RET
```

SpellLayoutPCImpl exact RTTI: TD178CEE8→COL13604B0→vptr12341C8, v98=A11810/v70=B0BB70/v88=A117D0. 여기서 v98를 알고 있다는 사실은 현재 subtype/instance·수명/표시 관측을 대신하지 않는다.

Hotbar getter `9DC8D0..9DC9D7`는 RCX(out)를R14에 보존하고 global1668790→ready+D8→GI+D0→subsystemvector+180/188를 순회한다. dynamic_cast는 ISubsystem TD1669A58→HudSlotDataSubsystem TD16D48D8이며 hit의 control+8을 retain한다. `9DC9A5 [out]=object;9DC9A8 [out+8]=control;9DC9AC RAX=out`이다. missing/미준비는 empty Pair다. `59B65C R12D=EDX;59B65F R15=RCX`로 입력을 보존하며 incomingR8 계약은 없다. `59B662..678`의 page*8+slot%8→tree 조회, `59B6E8..705` kind1/key/AE360/5B66F0, `59B7A8`5B63A0,`59B88E`5B5A70이 핵심이다. normal return59BC57에는 bool 성공 계약이 없다.

Pet lookup `627B0..62979`는 `627BF RBP=R8(fullUID);627C2 RSI=RDX(out);627C5 R15=RCX(ActorsSubsystem)`로 고정한다. subsystem+8A8/8B0,+8C0/8C8,+8D8/8E0의 owning Actor Pair vectors에서 actor.v8 **fullRAX**와 UID를 비교하고 hit의control+8 retain→out으로 이전한다. miss는empty Pair,`62967 RAX=RSI(out)`→RET. 기존 native ABI 출처: `implementation-3/skill-buff/spell-whole-entry-v1/native/drop_reference.hpp:6–13,88–99`. 그 코드의 다른 호출권한/시험 PASS까지 승계하는 것은 아니다.

## PostMessage WM_KEYDOWN 가능성

**정적 경로는 존재하며 실제 headless 전달 성공은 UNKNOWN이다.** 기존 원 WndProc등록 EF4650/EF4663→EF5480, GLFW property→Window와 run194의 원 callback등록을 재사용했다.

```text
EF5AB6 message<=112; EF5AC8 index=message-100
EF5ADE jump table EF64FC:100/101/104/105->EF5BAF,102->EF5AEB
EF5BAF lParam>>16 -> scan low9bits; zero는원 mapping fallback
EF5BBD EF5010 현재 modifier 조회
EF5D07 action/EF5D0A scan/EF5D11 key/EF5D14 Window
EF5D17 callEF0220
EF0220 원 key-state/repeat 처리;EF027D currentWindow+340 callback
EF029F tail->callback
```

기존 [run194 host packet](../../local_server_rea_20261016/run194_quantity_normal_text_input_producer/host_source/packet.json)은 B88835..43→EF1550가 Window+340에B8A2B0를 설치함을 확인했다. B8A2B0는 mappedkey/action/modifier로 B9C770 keyboard Event를 dispatch한다. [run196 normal key contract](../../local_server_rea_20261016/run196_partial_quantity_original_commit_trigger/normal_commit_source/packet.json)는 원 KeyboardListener→pressed16A730→현재Input+1E8의157D70→enabled key node의 current callable.v10까지 연결한다.

따라서 PostMessage는 원 message path를 이용할 **조건부 후보**다. 큐 접수/같은 HWND WndProc 도달/현재 Window callback/원 Input guard/실제 shortcut binding/창 표시를 구분한다. lParam scan과 release/repeat가 원 코드에 소비되며, modifier는 EF5010의 외부 상태조회이므로 posted wParam만으로 Ctrl chord를 재현한다는 근거가 없다. 15EAF0/15EBF0 wholeentry 호출의 정적 계약과 posted-key 성공을 서로 대체하지 않는다. 이 문서는 key posting·새 hook·사용자 focus 변경을 실행하지 않았다.

## 신규 조각 식별과 경계

신규 선택 carrier 조각만 hash했다. `[start,end)` 표기이며 이 문서의 RVA 명령으로 재검토할 수 있다. 원본/보존 전체 hash·이미 통과한 검사를 반복하지 않았다.

| RVA 조각 | B | SHA256 |
|---|---:|---|
|15EAF0..15EB9F|175|d627013e600b528b13aec54b4758e678cb77833ce3832d2fdd402c6cf7adf2e7|
|159F90..15A294|772|17b3c9079b7e9f80c9b23ece05a18f5775f0bb2dac682b71b563f54322840474|
|9DC8D0..9DC9D7|263|aab6a24312854ec64570ebbcc28b26a587be9b0339f9676a1543fdbd0f6a1ba1|
|59B630..59BC66|1590|0a7ce0f22909931df279e16f7e1f87cd31c00bbce7e1cecccd4256b879e0885a|
|EF5AB6..EF5AEB|53|5364c7e9160f8af4e18cc8f046e4c3a1fed8ba3a517ecf6763e800833c04fb48|
|EF5BAF..EF5D21|370|a25eee3c2b1aba9a51beec9f441b5ebd2258cf29d0e3d6c0de047321f8922638|
|EF0220..EF02A3|131|44498937166a897d35f07a9280f9aff90c061351aac01f831672e1a4fe2c77c9|

새 carrier E8 direct-call 검색은5B5A70/5B63A0→59B630 및59B630→원 HudSlot caller를 좁히는 데만 사용했다. callsite의명령/PData owner·실전달 인수를 확인했으며 E8 byte-hit만으로 caller를 확정하지 않았다. 예외/재진입/모든 keybinding·전체 UI수명은 닫지 않았다. 이번 결과는 bridge worker에게 magic/stats wholeentry,pet627B0/B8710,hotbar9DC8D0/59B630 ABI로 전달했다. 구현·컴파일·실호출 결과는 해당 worker/주실행 기록에서 별도로 판정한다.

## 최종 연결 범위와 hotbar 첫 막힘

Bridge worker는 `tools/local_original_session/native/ui_open_bridge.hpp`와 `work/local_original_session/ui-open-bridge/` 후보에 magic15EAF0/stats15EBF0 toggle 및627B0 fullUID lookup→retained Actor Pair→B8710을 연결했다. 마법·스탯 반환은`action=toggle`,펫은`action=pet_request`,모두`window_state/effect=UNKNOWN`이다. 두루마리는 기존원아이템사용raw133 경로를 재사용한다. **Hotbar는 최종 `UNSUPPORTED`,reason8,actionnone으로 제한**했다. 새 SlotNode resolver를 추측해 만들지 않았다.

Hotbar 마지막 한정 확인: `9DEBA0`는 RCX=실HudSlotLayout*,RDX=실입력*,R8=event를 받아P+30Q→9082B0→B53130(input+20 point)→95E010 current Slot hit를 얻고,Slot+870 child의v150 표시검사 뒤 metadata+C0를 사용한다. **숫자slot API가 아니다.** `9E22A0`는 RDX=`&Node*` cell을 한 번 역참조해 actual SlotNode cast→Slot+808/810 owning metadata Pair→metadata+C0→59B630을 호출한다. 이 함수 역시 숫자slot을 받지 않는다. 현재 numeric0..7→동일현재SlotNode의 owning resolver/등록callback borrow가 미공급인 것이 첫 막힘이다. 최소 추가 입력은 그 현재SlotNode를 원등록/소유아래 획득하는 기존 API 한 접점이며, 전체 UI/기하 복원이나 원함수수정은 필요조건으로 주장하지 않는다.

주실행자가 확인한 최종 DLL은 `ui-open-bridge/own-login-bridge-dg49.dll`,399872B,SHA256 `511840fedca21818b0bcfd64e4111c6f213b6a25d9604b84488d2a814f7dc775`,MSVC /W4 /WX build exit0이다. 기존 dispatcher/UseItemAlreadyOpen/OriginalScreenshot을 보존했다는 구현 worker 결과와 주실행자의 빌드 확인을 별도 재사용한다. 이는 정적 ABI/컴파일 결과이며 게임주입·실호출·화면·정상종료를 검증하지 않는다. 새 원문 파일은 이 문서뿐이며 소유밖 코드를 수정하지 않았다.

## 실행 준비와 오프라인 확인

- 명령: `tools/local_original_session/ui_open_commands.py`. 원 serial sequence를 공유하며 마법/스탯 toggle, 실제 target_uid의 펫 요청, 현재 가방 template12273·raw133의 기존 UseItem 요청을 제공한다. `hotbar_cast`는 UNSUPPORTED8이며 실제 시전을 주장하지 않는다. 함수/경로 근거의 출처는 5/5 클라이언트, 공식 API/L1J는 0/5다. IPC·시나리오 구성은 로컬 도구 구현이다.
- 시나리오: `work/local_original_session/run_ui_shots_scenario.py`. 기존 정상 Login→Slot→SelectOK·AddInventory COMMITTED 뒤 magic→PNG→두루마리→PNG→stats→PNG 순서이며 기존 SourceQuit/FIRST/finally를 사용한다. 새 runtime 사본에 후보 DLL을 두고 기존 핀 대상 DLL을 덮어쓰지 않는다. 원 캡처 관측과 실제 창/픽셀 판단은 별도다.
- 실행 준비 파일: `C:/Users/Chansol/AppData/Local/Temp/claude/D--claude/0483de89-75e7-4b94-84b8-fb31fe00f575/scratchpad/run_auto_ui_shots.ps1`. 이후 사용자 결정으로 `powershell -NoProfile -File '<위 경로>' -RunName ui-shots-20261027a`를 실행한다. 이번에는 PowerShell Parser로 구문만 검사했고 오류 0, 본문은 실행하지 않았다.
- 단위시험: `python -X utf8 -B -m unittest tools.local_original_session.ui_open_commands_tests -v` → **8 tests OK**. 실제 C++ 결과 형식·주소표·현재 raw133 UID와 UseItem 전송·파일 게시 중 상태·시나리오 순서/첫실패·후보 staging 보존·UNSUPPORTED 보존을 게임 없이 확인했다.
- 실행 후 출력 예정: `work/local_original_session/runs/<RunName>/{magic,talking_scroll,stats}.png`, `ui-shots-scenario.json`, 기존 `result.json`의 `ui_shots` 및 수명/종료 결과. 지금은 생성하지 않았다. 실제 창 열림·학습 목록·목적지 표시·스탯 값·펫 ACK/창·정상종료는 전부 UNRUN/UNKNOWN이다.
