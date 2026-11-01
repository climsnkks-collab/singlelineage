# 변신 주문서: 원본 선택 창과 선택 요청

2026-10-28. **원본의 주문서 사용은 클라이언트에서 선택 창을 열고, 형태를 고른 뒤 `CS_USE_ITEM_REQ(0x0960)`를 한 번 보낸다. 선택값은 SPR 번호나 XML desc가 아니라 `polymorph_list.xml`의 `monster/@name` 문자열이다.** 일반299를 위해 새 서버 목록/창 열기 패킷을 만들 필요는 없다. 아래는 정적 연결 확인이며 원본 실행·화면 확인이 아니다.

## 기준과 근거

- 고정 버전 `26.09.29.2001`; CONTROL SHA256 `9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`, CODE record SHA256 `a49e798ded9ed540abb2c6848fdd678cb1a2a12fc3ec243f301f69348bfb4b24`는 [기존 변신 근거](POLYMORPH_EVIDENCE.md)의 계보다.
- 이번 정적 원문은 [polymorph_select_evidence](polymorph_select_evidence/), 짧은 명령 발췌는 [source-excerpts.txt](polymorph_select_evidence/source-excerpts.txt)다. 각 JSON은 실제 명령 bytes, RVA, 함수 범위와 상속 source record 경로/신원을 보존한다. [inspect_static.py](polymorph_select_evidence/inspect_static.py)는 기존 `run380_map_transition_receive/f2_research.py:View`를 읽기 전용으로 재사용한다. 원본·현재후보·게임프로세스 동일성의 새 증명으로 확대하지 않는다.
- 기존 [run393의569260 원문](../../local_server_rea_20261016/run393_item_target_use/body-569260.json)도 보존돼 있으며 이번 확인의 동일 producer다. 당시 아이템 대상 선택 분석의 남은 원문이며 이번에는 XML 로더·native 슬롯 callback·scroll UID 분기를 추가로 연결했다. 기존 원문은 변경하지 않았다.
- 주소는 **복원 CONTROL RVA**다. 분석용 carrier의 VA는 `0x140000000 + RVA`다. carrier는 `work/rea_lineage_resume_20261013/main-gameplay/audit/metadata-v2/DERIVED_RESTORED_ANALYSIS_ONLY.exe`, SHA256 `c822838351d774a2022af434829a36dbd9bee030bf22182b834ca4e8659701a9`이며 실행파일의 원 bootstrap/protection 동등성을 뜻하지 않는다.
- REA 스킬에 따라 기존 근거/reader를 우선 재사용했다. REA MCP는 기존 active target이 없어 위 carrier를 열었다. 엔진의 최초 문자열 질의 결과와 종료 상태는 아래 REA 절에 기록한다. 로컬 원문 분석에는 새 MCP Evidence ID가 없으며 파일·주소를 인용한다.

## 1. 주문서 사용 → 원본 창

1. Inventory의 원래 사용 함수 `4FD260`은 선택 UID로 ItemEntity를 조회한다. `4FD347`이 `ItemEntity+50`의 raw use code를 읽고, `4FD5CE..4FD5F7`의 두 단계 switch가 분기한다. [switch_data.json](polymorph_select_evidence/switch_data.json)의 원본 table `4FE264/4FE2B8`을 해석하면 **raw16(0x10), raw130(0x82)**가 모두 `4FDB2E`다. [item_execute.json](polymorph_select_evidence/item_execute.json).
2. `4FDB39`는 `R8=선택 item UID`, `4FDB40`은 `EDX=ItemEntity+10(nameId)`, `4FDB46`은 `PolymorphSubsystem::ExecutePolymorphScroll(5689D0)` 호출이다. 이름은 함수의 오류 경로에 실제 `lineage::PolymorphSubsystem::ExecutePolymorphScroll` literal 참조(`5691C3→11C8C08`)가 있다. raw0는 원래 다른 요청 생성 분기이며 원본 변신 창을 여는 값이 아니다.
3. `568A50..568A71`은 nameId를 `PolymorphDataTable`의 `AB7A20` 조회에 넘기고 반환 group의 첫 dword(UI)를 읽는다. nameId·현재 클래스·성별 조건의 key 조회 원문은 [group_lookup_full.json](polymorph_select_evidence/group_lookup_full.json)에 있다. XML 그룹의 `UI=0`은 `3EFF10`, **`UI=1/2`는 `3F0230`**으로 간다. 후자의 native layout key는 `Transform_Event_Layout`이다([show_key.json](polymorph_select_evidence/show_key.json)). raw16과130은 동일 이 분기로 들어가지만 실제 공식299 인스턴스에서 둘 중 어떤 raw가 내려오는지는 이번 실행 없이 구분하지 않았다. 서버 기본값은 확인된 분기16을 사용하면 된다.
4. 일반 XML 첫 group은 `UI="2"`, `nameId="20,299,10015,12046,12054,12176,12304"`, `class="0,1,2,3"`, `gender="0,1"`다. [보존 XML](../../all_table_semantics/inputs/data/polymorph_list.xml). `568BA9..568BB7`은 UI·scroll UID·nameId를 layout state에 넣어 전달한다. `PolymorphSimpleLayout::On...`의 `ABD484..ABD4C4`는 scroll UID를 layout+C0, nameId를+B8, UI를+C8에 보관하고 `ABD4E1`에서 원래 show virtual70을 호출한다. [execute.json](polymorph_select_evidence/execute.json), [show_state_full.json](polymorph_select_evidence/show_state_full.json).

따라서 서버가 인벤토리 `ItemInfo.f5`를 raw16으로 보내면, 원래 사용 동작에서 서버 소비 요청을 먼저 기다리지 않고 원본 변신 창으로 간다. ItemInfo.f5→ItemEntity+50 copy는 [run40 기존 계약](../../local_server_rea_20261016/run40_item_raw0_branch/findings.md)을 재사용한다. **창 표시 성공은 정적 연결까지이며 실제 렌더·입력은 미확인이다.**

## 2. 목록 이름 → 버튼 callback → 요청

XML 로더 `AB60E0`는 `polymorphlist/polymorphGroup/polymorph/monster`를 순회한다. `AB6CA0..AB6CCE`는 `desc`를 정수로 읽어 row+20에 저장하고, `AB6D00..AB6D5B`는 별도 `name` attribute를 문자열로 읽어 row 시작의 std::string에 저장한다. 두 값을 같은 SPR로 취급하지 않는다. row는40바이트이며 `AB6D73..AB6D8C`가 이름과 desc를 함께 벡터에 복사한다. [xml_loader.json](polymorph_select_evidence/xml_loader.json), [문자열 교차참조](polymorph_select_evidence/xml_loader.json.strings.json).

RTTI로 `PolymorphSimpleLayout` vtable `122EA98`과 `MakeItemSlotList` lambda_1의 std::function vtable `122EDB8`을 연결했다([ui_types.json](polymorph_select_evidence/ui_types.json), [ui_tables.json](polymorph_select_evidence/ui_tables.json)). 슬롯 생성 `ABF910`은 해당 row 이름을 callback+10에 복사하고, desc는+30에 별도로 복사한다(`ABFD36..ABFDA2`). 일반 선택 전략0의 callback은 **`AC1530`**이며 즐겨찾기 편집 상태가 아닐 때:

```text
AC1591  RCX = [layout+C0]          # 선택했던 주문서 UID
AC1598  call 569260              # RDX=&callback 이름 string
AC159D..AC15AB                    # 기존 layout 닫기
```

해당 `569260`은 첫 인자 UID가 0이 아니면 `5693DE`로 간다. `UseItemReqParam`을 실제 vptr `11DE028`으로 만들고, 현재 자기 actor UID(`current player+6D8`)와 선택 이름을 채운 뒤 `5694E3→4FE630`으로 넘긴다. [slot_builder.json](polymorph_select_evidence/slot_builder.json), [callback_full.json](polymorph_select_evidence/callback_full.json), [request_producer.json](polymorph_select_evidence/request_producer.json).

## 3. 확정된 wire

outer schema·sender는 [run37 원본 계약](../../local_server_rea_20261016/run37_item_command_sender/findings.md)과 [descriptor](../../local_server_rea_20261016/run37_item_command_sender/source-evidence.json)를 재사용했다. `4FE630→4FE820→52A410→27D620` 기본 사용 경로다. raw16의 UI를 여는 동작과 아래 최종 선택 송신을 두 개의 소비 요청으로 만들지 않는다.

| 위치 | 필드 | 타입/값 | 원문 |
|---|---|---|---|
| `CS_USE_ITEM_REQ(0960)` | f1 | required uint64, 소유한 주문서 item UID | 선택 창+C0→569260 RCX→4FE630 RDX, run37 outer+20 |
| 같은 요청 | f2 | required `UseItemReqParam`, wire2 | 5694D9 R8=&params, run37 child copy |
| params | f1 | int32 varint **1** | params+70, `56949B`; presence bit15 |
| params | f2 | int64 varint, **현재 자기 actor UID** | params+38, `56945A/5694A2`; presence bit2 |
| params | f7 | string/wire2, **XML `monster/@name` 원문** | params+28, `5694C0..5694CA`; presence bit0 |
| params | f15/f16 | absent일 때 일반 sender가 각각 present **0**으로 보완 | run37 `52A410` 기존 계약 |

`5694A6`의 hasbits는 **`0x8005`**(bits15/2/0)다. f14의 내부 기본 bool1이 초기화되지만 presence bit16은 설정하지 않으므로 이번 경로의 추가 wire 필드로 만들지 않는다. desc·SPR·로컬 runtime key를 f7에 넣지 않는다.

f2는 signed int64의 일반 protobuf varint이며 sint64/zigzag가 아니다. f7은 기존 descriptor상 string이고 생성자는 선택된 std::string을 `DDDCA0`으로 복사한다. 이 경로에서 별도 한글/UTF-8 변환 호출은 확인하지 않았다. 보존 XML의 실제 monster 이름은 전부 ASCII여서 현재 선택 이름을 ASCII/UTF-8 bytes로 보내는 값은 같다. 비ASCII 선택 이름의 인코딩/정규화 계약은 UNKNOWN이다.

예: 서버가 발급한 현재 주문서 UID와 자기 actor UID를 쓰는 논리 요청은 다음과 같다. 이 표기는 실제 UID를 위조하는 시험 fixture가 아니다.

```text
0960 { f1: owned_scroll_uid,
       f2: { f1:1, f2:current_self_uid,
             f7:"orc morph", f15:0, f16:0 } }
```

일반299는 위 **이름 선택이 끝난 요청 한 번**으로 소비·변신한다. 클라이언트 로컬 창 열기를 흉내 내기 위한 별도 서버 packet·빈 raw0 선요청·서버가 발급하는 가짜 menu reference는 필요 없다.

서버 패킷 불필요 판정은 정상 로컬 item 사용 case16/130→이미 로드된 XML→native show까지의 정적 연결에 한정한다. 그때의 클라이언트 자원 로드·현재 장면·잠금/오류 분기를 실행으로 통과했다는 뜻은 아니다. 서버 인벤토리의 정확한 f5·nameId·UID 공급과 정상 월드 상태를 전제로 한다.

### 별도 4F2C 경로와 구분

`569260`의 첫 인자 UID=0 분기는 `CS_POLYMORPH_OTHER_ACK(4F2C)`를 보낸다(`569333..56933D`). `SC_POLYMORPH_OTHER_REQ` 수신 `5695D0`가 상태를 보관한 뒤 UID0으로 `5689D0`을 호출하는 별도 경로다. **이 분기는 일반 소유 주문서299 선택 요청이 아니다.** 서버가 일반299 창을 띄우려고 4F2C 또는 그 대응 서버 요청을 발명하지 않는다.

## 4. 서버 적용 경계

- `data/m1/polymorph.json`의 **forms77**은 기존 LOCAL runtime 키/외형·무기 정책이다. Classic XML catalog85개 이름은 별도다. f7 native name→검토된 runtime form 매핑을 사용하며 미확정 이름을 desc나 SPR 추정으로 승격하지 않는다. 일반 주문서 그룹과 기본 레벨 조건은 클라이언트 XML 출처다. 이벤트 낮은 레벨·다른 특수 그룹은 일반299에 적용하지 않는다.
- 외형 알림은 이미 확정한 `SC_POLYMORPH_NOTI(4E5C) {f1:현재UID,f2:선정SPR,f3:현재자세}`를 재사용한다. 이 분석은 원래 서버의 변신 지속시간/무기제한 계산식을 복원하지 않았다. 기존 L1J 기반 값은 `local_policy`다. 공식299 API의1200초와 기존 LOCAL1800초를 혼동하지 않는다.
- **4E5C f3=0은 ActionComponent+40을 덮지 않는다.** 만료 때 원래 sprite를 보내는 것과 맨손 자세0의 완전한 native 복원은 구분한다. 원래 Actor/Pair 유지·화면·이동·공격·입력·자원 수명에 대한 실행 관측은 이번 범위 밖이며 [POLYMORPH_EVIDENCE](POLYMORPH_EVIDENCE.md)의 제한을 유지한다.
- 잘못된 선택 요청은 그 요청만 거절한다. 일반 주문서 사용/선택의 새로운 pin·hash·guard 체계를 추가할 근거는 없다. 기존 item ownership·CAS·소비·타이머 수명 경계를 재사용한다.

## REA 엔진 및 검증 상태

원본 클라이언트 실행, live attach, UI 입력은0이다. 정적 reader의 원문·switch·callback·params producer를 연결했다. REA MCP carrier open은 성공했으나 최초 `search_strings(pattern="polymorph")`는 **300초 tool timeout**으로 실패했다. 같은 실패 질의를 재시도하지 않고 기존 reader로 필요한 정적 원문을 확보했다. `close_binary({})`는 `result:null`로 성공했다. [rea_status.json](polymorph_select_evidence/rea_status.json). 새 engine Evidence ID나 engine decompile 성공은 없다. **정적 분석 결과를 봇 PASS나 native 화면 PASS로 표시하지 않는다.**

## 5. 서버 구현과 검증

변경 파일은 `tools/local_original_session/world_feature_items.py`, `world_polymorph.py`, 기존 `hunt_bot_play_matrix.py`의 변신 요청 부분이다. 전용 봇 `hunt_bot_polymorph.py`와 임시 저장 단위 시험 `world_polymorph_inventory_tests.py`를 추가했다. 데이터 원문은 변경하지 않았다.

- `SL_EXPERIMENT_POLY` 없이 일반299의 native 선택을 기본 경로로 받는다. 신규 kit·획득·상점에는 raw16을 공급하고, 기존 저장은 초기 인벤토리 전달 뒤 기존0965.f5 갱신으로 표시만 보완한다. 저장/current 원문을 마이그레이션하지 않는다.
- 기존 forms77 계산은 유지하며, 확보된 XML 이름63개를 기존 runtime form에 연결한다. 미지 이름·레벨 부족은 소비 없이 해당 요청만 거절한다. XML 이름과 SPR 매핑·지속시간·무기 정책의 출처 구분은 위 제한을 유지한다.
- 주문서 소비는 기존 즉시 저장 경계를 사용한다. 부적합 무기의 해제는 기존 인벤토리/장비 공동 CAS와 알림 소유자를 재사용한다. 기존 월드 scheduler로 정상1800초 만료·원 SPR 복원을 예약하고 퇴장 때 타이머/상태를 정리한다. 접속을 넘는 변신 지속시간 저장은 제공하지 않는다.
- 수정 파일은 `start-manual-play.ps1`의 기존24개 pin 대상에 없으므로 pin/스크립트는 변경하지 않았다. 금지된 사용자 프로필·ACTIVE_TASK·동료/퀘스트/마법/전투/경험치/몬스터 파일과 원본 클라이언트는 수정하지 않았고 commit도 하지 않았다. 같은 파일에 도착한 다른 작업자의 물약4ED8/강화 표시 변경은 보존했다.

단위/구조 검증 명령은 다음과 같다. 공용 변경까지 들어온 현재 통합 조합에서 **39 tests OK (7.356s)**다. 원문 요약은 [POLYMORPH_SELECT_SERVER_CHECKS.txt](POLYMORPH_SELECT_SERVER_CHECKS.txt)에 있다.

```powershell
python -X utf8 -B -m unittest tools.local_original_session.world_polymorph_tests tools.local_original_session.world_polymorph_inventory_tests tools.local_original_session.world_decoupling_tests
```

### 첫 소켓 실행 — 관측 성공, 실행 중 source 변경

지정 `SL_TEST_TIME_SCALE=10`, `SL_TEST_PORT_BASE=60000`에서 [실행 명령과 로그](../runs/polymorph-select-validation-20261028-132425/command.txt)를 보존했다. [summary.json](../runs/hunt-polymorph-8rrhiizr/summary.json)은8체크 SUCCESS, 오류 없음, 실제 디스크 주문서5→4, SPR61→3906→61, 실제 scheduler1800.561가상초 만료, 정상 Quit·cleanup_complete=true다. 포트60000/62030 listener0을 확인했다.

다만 실행 중 다른 작업으로 `world_feature_items.py`, `item_equipment_effect.py`가 바뀌었다. 시작/종료의 정확한21파일 SHA는 위 summary의 `source_sha256_start`/`source_sha256`에 있고, `source_changes_during_run`도 보존했다. 이 결과는 시작 시 로드한 조합의 성공 관측으로 한정하며 현재 디스크 최종 선정판 PASS로 쓰지 않는다. 기존 시험 저장과 실패/소진 이력을 수정하거나 되감지 않았다.

동시 추가된 물약4ED8 동적 opcode 선언은 기존 AST 기반 구조 시험에서 `NameError: name 'tuple' is not defined`를 냈다. 실제 runtime 등록은 정상이었으며, 같은 `(0x4ED8,)` 정적 선언으로 정리한 뒤 위39시험을 재통과했다. 다른 작업의 물약 효과/강화 표시 동작을 제거하지 않았다.

### 61000 재시험 — 봇 비교 실패 보존

[summary.json](../runs/hunt-polymorph-hooi106w/summary.json), [원로그](../runs/polymorph-select-validation-20261028-133011/bot.log). FIRST/login/world·기본 경로·299 raw16 수신 뒤 `AssertionError: refused_POLYMORPH_UNKNOWN_NATIVE_FORM`으로 실패했다. 서버는 실제로 그 요청을 기대 코드로 거절했으며 failure/close=null, cleanup_complete=true, source 변화0, 포트61000/63030 listener0이다. 변신/만료 단계에 도달하지 않았으므로 이 실행은 FAIL이다.

봇의 거절 판정이 저장 원문과 수신 표시 전체를 직접 같다고 요구해, 동시 추가된 강화25/26의 송신 f5=7 투영과 호환되지 않았다. 저장 원문·실제 디스크·수신 표시를 각자의 요청 직전 snapshot과 비교하도록 호출부를 보완하고, 각 불변성 및 저장/표시 차이를 분해 기록한다. 서버의 요청/레벨/소비 판정은 변경하지 않는다.

### 62000 재시험 — 동작 성공, 공용 source 변경 보존

[summary.json](../runs/hunt-polymorph-hh3u6445/summary.json), [원로그](../runs/polymorph-select-validation-20261028-133233/bot.log). 8체크 SUCCESS, 실제 디스크299가5→4, SPR61→3906→61, 실제 scheduler1800.604가상초 만료, cleanup_complete=true, 포트62000/64030 listener0이다. 두 거절 요청은 저장/cache·disk·수신 표시가 각각 직전 상태를 유지했고 성공 알림/세션 오류가 없었다. 실제 표시 차이21개 중 강화25/26 여섯 행의 저장f5=0/수신f5=7 및 stack 이름 suffix가 분해 기록돼 있다.

변신 코드·봇은 불변이지만 실행 중 공용 `world_core_kit.py`, `world_core_session.py`, `broker.py`가 외부 작업으로 변경됐다. 정확한 시작/종료21파일 SHA와 변경 목록은 summary에 있다. 이 결과 또한 시작 조합의 동작 관측이며 현재 디스크 전체 선정판 PASS로 확대하지 않는다. 원본/사본/소진은 보존한다.

### 최종 소켓 재시험 — 고정 source SUCCESS

[summary.json](../runs/hunt-polymorph-osedaa4h/summary.json), [실행 명령](../runs/polymorph-select-validation-20261028-133749/command.txt), [원로그](../runs/polymorph-select-validation-20261028-133749/bot.log). **8체크 전부 SUCCESS, error=null, 실행 중21파일 source 변경0, 정상 Quit·cleanup_complete=true, failure/close=null**이다. 정확한 시작/종료 SHA와 초기 시험 저장 신원은 summary에 있다. 지정60000부터 순차 +1000으로 재실행한 마지막 기반은63000(보조65030)이다.

```powershell
$env:SL_TEST_TIME_SCALE='10'
$env:SL_TEST_PORT_BASE='63000'
Remove-Item Env:SL_EXPERIMENT_POLY -ErrorAction SilentlyContinue
python -X utf8 -B C:/Users/Chansol/AppData/Local/Temp/claude/D--claude/0483de89-75e7-4b94-84b8-fb31fe00f575/scratchpad/fastbot/run_fast.py hunt_bot_polymorph --scenario polymorph --timeout 30
```

시험 시작은 새 retained `SoloKnight` Lv1/test_knight 저장 사본이며 기존 starter/equipment 소유자가 발급한 실제 주문서UID65556·수량5를 사용했다. 사용자 저장·기존 실행 사본을 변경하지 않았다. 정상 FIRST/login→roster/선택→월드 진입→299 raw16 수신→클라이언트 로컬 창/선택의 정적 단계 기록→미지 이름/레벨 부족 요청 국소거절→`orc morph`의 실제0960 선택 요청→디스크 수량5→4→4E5C SPR61→3906→실제 scheduler **1800.671가상초** 만료 후61 복원→정상 Quit 순서다. 상태/cache·실제 디스크·클라이언트 수량이4로 일치하며 두 거절 요청은 각각 저장/디스크/수신 상태를 보존했다. 정상 제품1800초를 단축하거나 타이머를 직접 호출하지 않았다.

시험 담당은 실제204.550초/scale10과 포트63000/65030 listener0을 확인했다. 이전 실행의 성공 관측·실패·소진·사본은 모두 남겼다.

이는 위 고정 조합과 시작 저장에서 원본 계약의 실제 decoder/router/handler·저장·알림·만료를 연결한 **서버/직접 패킷 범위 PASS**다. 원본 창·입력·렌더·전체 플레이의 PASS가 아니다. 기존 saved-equipment combat_inputs adapter를 사용했으므로 부적합 무기 해제의 실제 native 알림/장비 메모리 동기화는 이 봇에서 시험하지 않았고, 공동 저장·앵커 이동·해제 비용은 별도 임시 저장 단위 시험 범위다. 원본 화면/입력, 맨손 자세0의 완전한 복원, 특수/미대응 XML 형태, 접속을 넘는 변신 지속시간 저장은 미확인/미제공이다. 지속시간1800초와 무기 정책은 기존 L1J 기반 `local_policy`이며 공식 원본 계산식으로 확정하지 않는다.


## 근거 부족22항목 재대조 (2026-10-28)

신규 런타임 승격0개, SPR 이름 대응3개(치파오 남30148/여30161·한복 여30191)를 추가했다. catalog85/활성63/런타임77은 유지하며 SPR 정적 대응78개다. 기존 “특수 주문서7종”은 특수 형태7개이고 전용 아이템은9개다. 클라이언트 실제 item identity는 확보했지만 공식 API9개는 HTTP200 빈 객체이며 전용 지속시간·등급 정책이 없다. 일반299에 이벤트 이름/낮은 레벨을 추가하지 않았다.

22항목별 부족 계약,9개 아이템 name token/원문 줄, L1J Sharna 유사성의 한계, 공식299 `1200초`와 `20~30분` 및 기존 LOCAL1800/2100초 유지 판단은 [POLYMORPH_UPDATE](../../../tools/local_original_session/data/m1/POLYMORPH_UPDATE.md)와 `polymorph.json.recheck_20261028`에 있다. XML class/gender·아이템별 목록은 이후 특수 지원 시 함께 소비해야 한다. 원본 목록 창만 보는 것으로 전용 만료·장비 허용 정책까지 확인할 수는 없다.
