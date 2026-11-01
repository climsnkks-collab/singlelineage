# 고정 원본 UI 단축키 조사

2026-10-30. 동료창 키 충돌 방지를 위한 **정적 조사**다. 게임·서버·포트·온라인·입력·프로세스 attach·REA/MCP 호출은 하지 않았다. 쓰기는 이 문서 하나다. `reverse-engineer-anything`의 원문 관찰/추론/UNKNOWN 구분을 적용하되, 사용자 지시에 따라 기존 파일과 Python(pefile/Capstone)만 읽었다.

**결론:** 가방은 Tab/Ctrl+I, 캐릭터는 Ctrl+A, 마법은 Ctrl+S, 옵션은 Ctrl+V의 기본 등록을 주소로 연결했다. ATS는 Alt+W 설정/Alt+G 실행·토글 문구와 해당 키 등록을 찾았다. **펫·소환 창 전용 키는 확인하지 못했다.** F1~F3은 3개 페이지용 등록, F5~F12는 8개 슬롯용 등록이고 F4는 주변 줍기다. F1~F12 전체를 12개 슬롯으로 취급하면 안 된다. 현재 사용자 재바인딩·실제 입력/표시 성공은 전부 미확인이다.

## 기준 자료와 주소

- 고정 버전 `26.09.29.2001`, 원 `LC.exe` CONTROL SHA256 `9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`. 기존 [UI_OPEN_EVIDENCE.md:9](UI_OPEN_EVIDENCE.md:9), [TARGET_IDENTITY](../../local_server_rea_20261016/TARGET_IDENTITY.md)를 재사용했다.
- 신규 읽기는 `work/rea_lineage_resume_20261013/main-gameplay/audit/metadata-v2/DERIVED_RESTORED_ANALYSIS_ONLY.exe`(기존 SHA256 `c822838351d774a2022af434829a36dbd9bee030bf22182b834ca4e8659701a9`)의 PE mapping과 Capstone 정적 해석이다. **아래 주소는 RVA**, VA=`0x140000000+RVA`. 분석 파생 PE이며 현재 실행 메모리/무수정 LC와 같다고 확대하지 않는다.
- 문자열 `S`=`work/all_table_semantics/inputs/data/string.csv`. 물리 행과 ID를 병기한다. 기존 색인 버전은 고정 버전이나 이 파일의 catalog 비교는 **changed**다([F4_PICKUP_EVIDENCE.md:23](F4_PICKUP_EVIDENCE.md:23)). 문자열만 있는 항목은 실제 바인딩 확정이 아니다.
- 사용자가 지정한 catalog의 실제 경로는 `work/asset_data_analysis/current/catalog.tsv`(`work/asset_data_analysis/catalog.tsv`는 없음). current catalog는 비교용 색인이므로 현재 제품 채택판/고정판 자원 전체 동일성의 증거로 쓰지 않는다.

## 키 → 기능과 확인 수준

`정적 연결`은 기본 키 코드→등록→원 callback/대상까지 확인한 범위이며 실행 PASS가 아니다. `문구`는 자원이 그렇게 설명한다는 뜻이다.

| 키 | 기능 | 근거 파일:행 또는 RVA | 판정·경계 |
|---|---|---|---|
| Tab | 가방 toggle | S:617 ID616 `인벤토리 Tab`; key map `165F7A8` external258→internal8; `158070 EDX=8`, `158078→1578B0`, vptr`1188630`+10→`15EDF0→159A20` | 정적 연결. 원 InventoryLayout toggle 계약은 [UI_OPEN_EVIDENCE.md:17](UI_OPEN_EVIDENCE.md:17), [run63/open-worker/findings.md](../../local_server_rea_20261016/run63_useitem_ui_dispatcher/open-worker/findings.md) 재사용 |
| Ctrl+I | 가방 toggle(대체) | key map`165F6D8` I→84; `15810A EDX=20084`, `158112→1578B0`; vptr`1188668`+10=`15ECF0→159A20` | 정적 연결. S의 메뉴 문구에는 Tab만 있으므로 문구 미기재가 미사용을 뜻하지 않는 실제 사례 |
| Ctrl+A | 캐릭터/스탯 창 toggle | S:615 ID614; key map`165F698` A→7C; `1581A4 EDX=2007C`, `1581AC→1578B0`, vptr`11888D0`+10=`15EBF0→159C70` | 정적 연결. 원 CharacterInfoLayout/command2는 [UI_OPEN_EVIDENCE.md:19](UI_OPEN_EVIDENCE.md:19) |
| Ctrl+S | 마법 창 toggle | S:616 ID615; key map`165F728` S→8E; `15823E EDX=2008E`, `158246→1578B0`; vptr`1188940`+10=`15EAF0→159F90` | 정적 연결. SpellLayout/command2. **2008E 자체를 Win32 VK로 해석하지 않음** |
| Ctrl+V | 옵션/설정 창 | S:619 ID618; key map`165F740` V→91; `158623 EDX=20091`, `15862B→1578B0`; vptr`11887F0`+10=`15E310`; `15E340→15A870`; `15A9FB` RTTI=`OptionLayout` | 정적 연결. 실제 표시·닫기 미확인 |
| Alt+W | ATS 설정 열기/닫기 | S:11908 ID11962, S:11934 ID11988; key map`165F748` W→92; `158F00 EDX=40092`, `158F08→1578B0`; vptr`1188A58`+10=`15D660`; `15D68D EDX=2`, `15D695→15AE90`; `15AFCA` RTTI=`ATSLayout` | 정적 연결＋기능 문구. 원 ATS를 동료 설정으로 전용해도 이 원 키 경로를 무시하면 안 됨 |
| Alt+G | 원 ATS 실행/토글 | S:11819 ID11873, S:11937 ID11991; key map`165F6C8` G→82; `158E66 EDX=40082`, `158E6E→1578B0`; vptr`1188B70`+10=`15D760→644B0→42AC10` | 키 등록 및 문구 확인. `42AC10` 이후 전체 실행 계약은 이번에 미분석. 설정창 열기와 다른 기능 |
| Ctrl+C | 커뮤니티 | S:618 ID617; `158757 EDX=2007E`, `15875F→1578B0`, callback`15E1B0` | 해당 키 등록＋기능 문구. 하위 소비 의미는 이번에 미분석 |
| Ctrl+D | 행동창 | S:3119 ID3118; `1586BD EDX=2007F`, `1586C5→1578B0`, callback`15E210` | 해당 키 등록＋기능 문구. 아래 Alt+D 문구 충돌을 보존 |
| Alt+D | 행동창이라고 적힌 ATS 안내 | S:11937 ID11991 `행동창(Alt-D)` | **문구 충돌/미확인.** 같은 추출본 S:3119의 Ctrl+D와 다름. 현재 등록·소비를 연결하지 못했으며 Alt+D를 빈 키로 추천하지 않음 |
| Ctrl+M | 지도 | S:1736 ID1735; `158D23 EDX=20088`, `158D2B→1578B0`, callback`15DB70` | 해당 키 등록＋기능 문구. 현재 창/동작 미확인 |
| Ctrl+Q | 종료 | S:620 ID619; `15888B EDX=2008C`, `158893→1578B0`, callback`15E050` | 해당 키 등록＋기능 문구. 실행하지 않음 |
| F1/F2/F3 | 단축창 페이지 번호0/1/2를 전달하는 UI 명령1 | key map`165F830/838/840`: external290/291/292→2F/30/31. `1582E5 EBX=0`, `15832B capture=EBX`, `158348 EDX=EBX+2F`, `15837C→1578B0`, `158381..386` 3회. vptr`1188860`+10=`15E790`; `15E7E2 EDX=1`, `15E7EA→11AA80`; `11ABCC` RTTI=`HudSlotLayout`, `11AC9C`=`SlotCommand` | 정적 등록·3개 index·UI 명령 연결. **페이지 선택이라는 해석은 3개 index/명령/기존 currentpage 계약에 따른 추론**, 실제 페이지 전환 미관측 |
| F4 | 주변1셀 아이템 줍기 | S:6148 ID6147; scan3E→GLFW293→internal32→`156B91..99` 등록→`15D310`→ActorInputComponent→`A8926` key32→`A8940→A3120` | 기존 정적 연결 재사용. [F4_PICKUP_EVIDENCE.md:50](F4_PICKUP_EVIDENCE.md:50), [selected-evidence.txt](f4-pickup-evidence/selected-evidence.txt). 전체 아이템 일괄 줍기나 4E3E 출처 플래그로 확대 금지 |
| F5~F12 | 현재 단축창의 8개 슬롯 index0..7에 대한 UI 명령2/4 | key map`165F850..888`: external294..301→33..3A. `15838C EBX=0`, `158421 EDX=EBX+33`, `158455→1578B0`; `1584F1..4F6` 8회. callback`15E650` 명령2, `15E510` 명령4→`11AA80(HudSlotLayout/SlotCommand)` | 정적 등록·8개 index·UI 명령 연결. `15E510/650` 두 callback의 keydown/up·hold 역할 전체 의미는 미확인. 숫자 slot0..7 실제 마법/아이템 발동 PASS 아님 |
| Ctrl+1~Ctrl+8 | 위와 같은 8개 슬롯 index0..7의 대체 UI 명령2 | `158496 capture=EBX`, `1584B5 EDX=EBX+2004D`, `1584EC→1578B0`; callback`15E650→11AA80` 명령2. key map`165F640..678` 1..8→4D..54 | 정적 연결. F5~F12와 등록 구조가 다르므로 누름/유지/해제 동등성은 미확인 |
| Alt+F2 | 창모드 크기 | S:6336 ID6335 | 문구 확인. 실제 callback/원 등록 미연결. **일반 F2 페이지와 modifier를 구분** |
| Alt+Enter | 창모드 전환 | S:6340 ID6339 | 문구 확인. 실제 원 등록 미연결 |
| Alt | 드롭 아이템 표시 관련 옵션 | S:6361 ID6360 `드롭 아이템(ALT)` | 문구 확인. 누르기/유지/토글 의미 미확인 |
| 펫창·소환창 전용 키 | **미확인** | S 전역의 Ctrl/Alt/Shift/실제 F키 표기, pet/summon 자원명 및 기존 PET/UI 문서 검색에서 전용 chord 미검출. 원 창 경로는 아래 | 부재의 완전 입증 아님. 임의로 Ctrl+P/Alt+P 등을 펫창으로 지정하지 않음 |

## 키 코드 해석과 충돌 주의

이번 신규 정적 읽기로 기존 `2008E` 불명확성을 다음 범위만 좁혔다. 키 map은 기존 [keymap_table.json](f4-pickup-evidence/keymap_table.json)의 external→internal 쌍과 carrier 바이트를 재사용했다. GLFW의 external 문자는 ASCII A..Z, 숫자1..8, Tab258, F1..F12=290..301의 mapping이다. 원 `EF5010` modifier 수집은 `EF501F` key10(Shift) 조회→bit1, `EF502D..5048` key11(Ctrl)→bit2, `EF503D..505E` key12(Alt)→bit4를 만든다. `B8A349..B8A38C`는 modifier를16비트 왼쪽으로 옮겨 internal key와 OR한다. 즉 Ctrl+S의 내부 합성값은 `2<<16 | 8E`이다. Win32 VK=2008E라는 주장이 아니다.

원 소비 `157D70`은 WORLD5 gate 후 키를 조회한다([run196 findings](../../local_server_rea_20261016/run196_partial_quantity_original_commit_trigger/normal_commit_source/findings.md)). `157DFD..157E14`에는 **F5~F12/internal33..3A에 modifier가 있어도 Alt bit4가 없으면 modifier를 떼는 특례**가 있다. 따라서 **Ctrl+Shift+F5~F12를 새 빈 키로 쓰면 원 슬롯에 충돌할 수 있다.** `157E3B..157EC4`는 이후 전체 DWORD key의 hash/equality 조회이며, 이 함수에서 일반 문자 chord를 부분 modifier로 fallback하는 분기는 확인하지 못했다. 다른 listener·전역/OS·사용자 설정까지 안전하다는 뜻은 아니다. F1~F3·Alt+F2·Alt+G/W도 예약 대상으로 취급한다.

단축창의 page당8칸과 실제 사용의 추가 한계는 [UI_OPEN_EVIDENCE.md:21](UI_OPEN_EVIDENCE.md:21)의 `59B630(page*8+slot%8)` 계약을 재사용한다. 이번 정적 UI 명령을 실제 슬롯 선택/발동 관측으로 대체하지 않는다.

## 펫·소환 창과 옵션 CSB 조사

원 펫·소환 창은 현재 확보 근거상 **대상 Actor의 상호작용→4F13 요청→4F14 응답** 경로다. `B6D20`의 Interaction+8 Actor→`B9990→B8710(Actor*)`가4F13을 송신하고, `2FB970→318440→54BDF0`가4F14.f2=1 PetLayout/2 SummonLayout을 선택한다. [UI_OPEN_EVIDENCE.md:20](UI_OPEN_EVIDENCE.md:20), [PET_EVIDENCE.md](PET_EVIDENCE.md), [run270/source/contract.md](../../local_server_rea_20261016/run270_pet_callback_installer_join/source/contract.md). 이 경로는 물리 키를 증명하지 않는다. **원 펫 키가 확인되면 우선 재사용한다는 방향은 유지하되 지금 확인된 원 키는 없다.**

catalog에서 `option/optionlayout.csb`:4456, `pet/petlayout.csb`:4478, `summon/summonlayout.csb`:126869 및 purple 대응4559/4571/4596행을 확인했다. 옵션 CSB는 catalog에서 changed, 펫·소환은 identical 비교로 표시된다. 파일명에 keysetting/keyconfig/shortcut를 포함한 별도 CSB 이름은 이 catalog 검색에서 미검출이다. **색인 이름만으로 옵션 CSB 내 키 설정이 없다고 단정하지 않는다.** 이번 허용 범위에서 해당 CSB payload의 키 설정 노드/현재 적용값을 얻지 못했으므로 옵션 CSB의 실제 설정·재바인딩은 미확인이다. `activate_content_shortcut.jsonc`는4바이트 `null`([catalog:108](../../asset_data_analysis/current/catalog.tsv:108), [원문](../../all_table_semantics/inputs/data/activate_content_shortcut.jsonc:1))이므로 키 표로 사용할 수 없다.

## 충돌 미검출 후보3개

**완전히 비어 있음이 입증된 키는0개다.** 아래는 검색 범위 내 **예약 미검출/충돌 미확인 후보**이며 채택·구현하지 않았다. S의 chord 문구 전역 검색, 기본 UI 등록 함수`157FB0..158FC0`, 위 키 map/소비를 대조했다. 모든 InitAction/BuilderShortcut·다른 listener·현재 사용자 설정·PURPLE/OS 전역 단축키를 전수 해석한 결과가 아니다.

| 후보 | 이유 | 남은 확인 |
|---|---|---|
| Ctrl+Shift+J (`30085`) | S에 해당 chord 미검출, 기본 UI 등록 목록에 해당 합성 key 미검출. F5~F12 modifier 제거 특례 대상이 아닌 일반 문자. 확인된 UI/ATS 키와 문자도 겹치지 않음 | 다른 등록 함수/현재 key map/다른 listener와 글로벌 환경 충돌 미확인 |
| Ctrl+Shift+K (`30086`) | 위와 같으며 조사한 기본 UI 등록에 Ctrl+K·Alt+K 기능도 검출하지 못함 | 같은 한계. 문자열 부재로 원 기능 부재를 주장하지 않음 |
| Ctrl+Shift+L (`30087`) | 위와 같으며 조사한 기본 UI 등록에 Ctrl+L·Alt+L 기능도 검출하지 못함 | 같은 한계. 채팅/텍스트 편집 focus의 소비·키 유실 미확인 |

현재 Ctrl+Shift+M은 과거 동료 private 후보 흔적이 있으므로 새 후보로 세지 않았다([COMPANION_AUDIT_CLAUDE.md:127](COMPANION_AUDIT_CLAUDE.md:127)). 동료 키 최종 선택 전에 필요한 최소 추가 근거는 **현재 적용된 전체 binding 조회 또는 해당 후보의 모든 input listener 등록 정적 확인**이다. 이번 금지 범위인 실제 입력 시험을 수행하지 않았으며 사용자에게 실행/화면 확인을 요구하지 않는다.

## 조사 범위와 미확인

읽은 범위는 WORK_RULES/ACTIVE_TASK, game-core-prep의 기존 hotkey/단축키 문서, S의 명시 chord 전체, all_table_semantics의 관련 입력과 자원 색인, asset catalog의 관련 CSB 이름, 기존 F4 정적 원문/key map, 파생 carrier의`157D70..157FA5`, `157FB0..158FC0`, 선택 callback/manager·modifier 구간이다. reader는 인라인 `python -`에서 `sys.dont_write_bytecode=True`로 파일만 읽고 이 문서 이외 산출물을 만들지 않았다. 초기 폭넓은 `rg --files -uu work`는 접근 거절된 임시 폴더가 많아 범위를 좁혔으며 그 경로를 검색 완료로 세지 않는다.

미확인: 펫/소환 전용 키의 존재·부재, 모든 일반키/Alt/Ctrl 조합의 기능, InitAction/BuilderShortcut 전체 등록, 옵션 CSB payload·사용자 재바인딩, ATS 동작 전체 downstream, F1~F3 실제 페이지 전환·F5~F12 실제 발동/hold/repeat, 현재 입력 focus·모달/텍스트편집 우선순위, 화면 표시/저장/수명/정리. 이 문서의 신규 주소 확인은 보존 파생 carrier의 정적 관찰이며 정식 게임 PASS가 아니다.
