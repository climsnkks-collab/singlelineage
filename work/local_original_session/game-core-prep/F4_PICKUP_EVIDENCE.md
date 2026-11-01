# F4 주변 아이템 줍기 — 원본 근거와 동료 구현안

조사일: 2026-10-28 KST. **조사·문서만 작성했다. 게임·서버 실행, 화면 캡처, 입력 주입, 제품 코드·저장·프로필·핀·ACTIVE_TASK 변경, git commit은 하지 않았다.** 정적 원문 확인을 실제 F4 입력·패킷 수신·화면·저장 복원 PASS로 확대하지 않는다. 다른 작업자가 있는 현재 working tree를 읽었으므로 코드의 함수명과 경로를 기준으로 삼고 줄 번호는 조사 시점의 탐색 위치로 사용한다.

**사용자 확정:** 주인이 F4로 주변 아이템을 주우면 동료 법사도 주변 바닥 아이템을 **동료 자신의 가방**으로 줍는다. 자동 분배·주인 가방으로 전송·상시 오토루팅까지 승인된 결정으로 해석하지 않는다. 범위·우선순위·HOLD 처리 등 아래 `local_policy 제안`은 아직 원본 사실이나 추가 사용자 결정이 아니다.

경로 약칭: `T/` = `tools/local_original_session/`, `R/` = `work/local_server_rea_20261016/`. 주소는 별도 표시가 없으면 원본 CONTROL의 RVA다.

## 1. 현재 결론과 확인 수준

| 질문 | 판정 | 근거와 한계 |
| --- | --- | --- |
| F4가 주변 아이템 줍기인가? | **원문·기본 키 연결 확인** | 기본 F4 scan→GLFW293→내부 key0x32→ActorInputComponent→`A3120`을 연결했다. `string.csv` ID6147의 주변1셀 설명과 Loot 행동 콜백도 같은 함수로 합류한다. 현재 사용자 재바인딩은 미확인이다. |
| “모두 줍기” 옵션과 같은가? | **원문상 구분** | ID6172/6173은 별도 On/Off이며 수량성 아이템의 모두/낱개 줍기 설명이다. F4가 주변 전체를 한 번에 일괄 처리한다는 증거로 쓰지 않는다. |
| 기존 서버가 받는 요청은? | **코드·기존 REA 확인** | `CS_GET_ITEM_REQ 0x4E3E`, outer singular f1 안에 x/y/UID/수량. 요청에 F4 플래그는 없다. |
| F4에서 4E3E를 반복하는가, 전용 요청인가? | **정적 연결 확인** | 한 번의 `A3120` 호출은 첫 대상 하나만 고르고 기존 GET 경로로 넘긴다. 즉시 분기는 `4E3E` 한 건이며 조건에 따라 수량 팝업을 거친다. 이 경로에서 전용 주변줍기 요청이나 여러 대상 반복은 없다. 키 유지의 반복 주기는 미확인이다. |
| 반경·개수·순서·이동은? | **선택 코드 확인 / 화면 미확인** | 정상 좌표에서 각축 차이≤1, 자기칸+인접8칸. actor vector 순서상 첫 state9 대상 하나이며 거리순 정렬이 아니다. 원거리까지 걷는 경로는 확인되지 않았고 방향 갱신은 있다. 서버의 허용 거리3은 별도 로컬 정책이다. |
| 현재 동료가 바닥 아이템을 주울 수 있는가? | **미구현** | 동료 bag/중량/저장과 이동 AI는 있으나 ground pickup은 살아 있는 PC만 받는다. 동료 actor는 NPC다. |

## 2. 단축키·원본 리소스

### 2.1 고정 추출본

[기존 자원 색인](../../all_table_semantics/inventory.json)의 버전은 `26.09.29.2001`이다. 리소스 이름의 `assets/data/...`에 대응하는 이번 로컬 자료는 [inputs/data](../../all_table_semantics/inputs/data/) 아래에 있다. 새 자원 추출·업데이트는 하지 않았다.

| 파일 | 직접 읽은 내용 | 기존 색인의 신원·주의 |
| --- | --- | --- |
| [activate_content_shortcut.jsonc](../../all_table_semantics/inputs/data/activate_content_shortcut.jsonc) | 4바이트 `null` | SHA256 `74234e98afe7498fb5daf1f36ac2d78acc339464f950703b8c019892f982b90b`. 따라서 이 파일에서 기본 키표·사용자 재바인딩을 얻었다고 할 수 없다. |
| [string.csv](../../all_table_semantics/inputs/data/string.csv) | 아래 F4/모두줍기 문구 | 637,926바이트, SHA256 `aab0a19b92d349724672695ebd9ea8aba00df3559bbbaa3f76ace198172f50af`. 색인의 `catalog_comparison`은 **changed**다. 보존된 추출본의 문구이며 다른/최신 catalog와 완전 동일하다고 주장하지 않는다. |

`string.csv`에서 확인한 위치:

- **6148행, ID6147, UI_ACTION:** `토글(F4)` / `종류: 액션` / `대상: 술자와 1셀 내의 아이템` / `주변의 아이템을 주움`.
- **6173행, ID6172:** `모두 줍기 On/Off`.
- **6174행, ID6173:** `모두 줍기` / `종류: 토글` / `대상: 술자` / `수량 성 아이템을 모두/낱개 줍기 가능`.
- **2469–2470행, ID2468/2469:** `모두줍기 켬` / `모두줍기 끔`.

추가로 [behavior_list.jsonc](../../all_table_semantics/inputs/data/behavior_list.jsonc):25–31의 `_id=0`, `_name=Loot`, `_exTooltipId=6147`을 실제 콜백과 연결했다. `_delay=600`의 단위는 파일 주석상 ms지만, **행동창 Loot의 지연 설정을 별도 F4 키 경로의600ms 반복 간격으로 단정하지 않는다.** `_name=LootAll`은 id13의 별도 설정 동작이다. 아래 키 코드 연결은 고정 원본의 기본값이며 현재 사용자 설정·실제 keydown/repeat 관측은 아니다.

### 2.2 클라이언트 함수·REA 조사

기존 [run98 GET 계약](../../local_server_rea_20261016/run98_item_drop_pickup_contract/findings.md)과 [source-evidence](../../local_server_rea_20261016/run98_item_drop_pickup_contract/worker/source-evidence.json)를 재사용했다. GET sender는 `0x3CD90`, GET schema는 `0x15EF230`, child schema는 `0x15EF290`이다. 기준 CONTROL SHA256은 `9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`다. 저장된 복원 섹션은 그 CONTROL의 파생 분석 자료이며 무수정 실행파일이나 현재 실행 메모리와 혼동하지 않는다.

이번 REA MCP `binary_session`은 `open:false`, retained `analyze_function` record0이었다. 공유 세션을 변경하거나 새 게임을 실행하지 않고 기존 [run395 정적 reader](../../local_server_rea_20261016/run395_selfinfo_stats_fields/extract.py)의 복원 섹션·PData·Capstone 읽기를 재사용했다. **신규 REA Evidence ID는 없으며**, 아래 파일이 이번 정적 분석의 재사용 가능한 원문이다. 신규 분석 스크립트는 남기지 않았다.

원문: [selected-evidence.txt](f4-pickup-evidence/selected-evidence.txt) 909행. 나머지 txt/json은 [f4-pickup-evidence](f4-pickup-evidence/)에 보존했다. JSON의 함수 RVA·범위·선택 함수 SHA는 분석 바이트의 식별용이며 실행 PASS가 아니다.

| 연결 | 정적 근거·원문 위치 |
| --- | --- |
| 기본 F4→내부 key | native 초기화 `EF8F60`의 상수 store `EF9049`를 투영하면 scan`0x3E`의 배열 slot`0x17A7F04`=`0x125`(293). GLView 생성자`B88280`은 매핑 표`0x165F848`의 external`0x125`→internal`0x32`를 등록한다. [f4_scancode_projection.json](f4-pickup-evidence/f4_scancode_projection.json), [keymap_table.json](f4-pickup-evidence/keymap_table.json):372, selected:1–13. |
| 내부 key→action | `156B35`가 callable vptr`1188A90`을 구성하고 `156B91..156B99`가 key`0x32`로 등록한다. invoke slot`+0x10=15D310`→`93570`의 ActorInputComponent `+0x38` interface virtual`+8`로 전달한다. 실제 interface vptr`1181188`은 생성자`A7793`에서 설치되고 slot`+8=A7EF0`. selected:15–138,193–248; [tables.json](f4-pickup-evidence/tables.json), [actor_input_vtable.json](f4-pickup-evidence/actor_input_vtable.json). |
| key 분기→주변 선택 | `A8926`에서 key`0x32` 비교, `A8935→582D0`로 자기 Player를 얻고 `A8940→A3120`. selected:219–226. |
| 행동창 Loot→같은 선택 | `BehaviorSubsystem::InitBehaviorFunc`의 Loot callable vptr`11BAB58`, invoke`+0x10=454CC0`→자기 Player→`A3120`. 리소스 Loot/tooltip6147과 합류한다. selected:250–370; [behavior_callbacks_metadata.json](f4-pickup-evidence/behavior_callbacks_metadata.json). |
| 첫 대상→기존 GET | `A3447→B6D20`→설치 callable`B9990`→`B7DB0`→`B83B8→3CD90`→`4E3E`. callable 설치는`B8D3C`에서 `B7DB0`을 계산해`B93D0`으로 저장한다. selected:137–192,371–480,802–827; [loot_entry.txt](f4-pickup-evidence/loot_entry.txt)의`B7DB0` 본문; 기존 run98 계약. |

**반경·순서·개수:** `A321D/A3224`가 ActorSubsystem의 vector`+0x8A8..+0x8B0`을 얻고16바이트씩 순방향 탐색한다. `A3269..A328F`는 두 좌표 차이의 절댓값을 각각1과 비교한다. 정상 좌표에서 Chebyshev≤1, 즉 자기칸과 인접8칸이다. actor의 component state`+0x80==9`인 첫 후보에서 `B6D20`을 호출하고 정리·RET로 나가며 다음 아이템으로 반복하지 않는다. 미채택 후보만 다음 vector 원소로 진행한다. **한 번에 첫 ground 객체 하나**이며 stack의 Q개와 서로 다른 아이템 객체 개수를 혼동하지 않는다. 거리·가치·UID 정렬은 이 함수에 없고 vector 자체의 구성/삽입 순서가 선택 순서를 좌우한다. 전체 actor vector의 삽입 순서까지 규명한 것은 아니다. 근거 selected:481–801, 특히 `A3276/A328C`, `A33DD`, `A343C..A3447`, `A34FB..A357D`.

**Q와 모두줍기:** `B7DB0`의 즉시 송신 분기는 Item`+0x38`의 현재 수량을 사용한다. 설정/조건에 따라 수량 팝업을 열고 그 팝업의 확정 경로도 같은 GET sender를 쓴다. 수량이 항상1이거나 F4 한 번에 주변 모든 객체를 전부 보낸다고 해석하면 안 된다. 모두줍기는 이 stack 수량/팝업 설정과 관계된 별도 기능이다. 원문은 `loot_entry.txt`의`B7F39..B8111`, `B8391..B83B8`와 기존 [run98 worker/findings.md](../../local_server_rea_20261016/run98_item_drop_pickup_contract/worker/findings.md):20,29–33. 설정·키 조합별 팝업/즉시 전송의 실제 조합은 실행 미확인이다.

**이동:** 선택기는1칸 밖 대상은 건너뛴다. `B7DB0→A2B10`은 좌표 차이로 방향값을 계산하고 현재 방향과 다르면 갱신 호출을 수행한다. [loot_position_update.txt](f4-pickup-evidence/loot_position_update.txt) 및 selected:828–909. **원거리 바닥까지 자동으로 걷기·경로탐색은 이 선택 경로에서 확인되지 않았다.** 하위 이벤트 전체 효과·화면상 회전/프레임은 미관측이므로 “전혀 움직이지 않는다”까지 단정하지 않는다.

위 선택/GET 경로에는 전용 주변줍기 batch를 생성하는 분기가 없다. 프로그램 전체의 다른 기능·opcode 부재를 증명한 것은 아니다. `get_sender_calls.json`에 보존한 직접 caller 두 곳 역시 inlined/간접 호출 전역 부재를 의미하지 않는다.

## 3. 패킷과 현재 서버 소비

### 3.1 확인된 개별 GET

| 계층 | 필드 | 타입·의미 |
| --- | --- | --- |
| C→S opcode | `0x4E3E` | `CS_GET_ITEM_REQ` |
| outer | f1 | required **singular message**; 여러 아이템의 repeated batch가 아니다. |
| f1.child | f1 | required int32 x, wire0 |
| f1.child | f2 | required int32 y, wire0 |
| f1.child | f3 | required uint64 ground UID, wire0 |
| f1.child | f4 | required uint64 요청 수량, wire0 |

근거: run98 위 자료, [T/item_transfer_protocol.py](../../../tools/local_original_session/item_transfer_protocol.py):39,79–100,138–174,198–230. 현재 parser의 canonical 순서·중복/미지 필드 거절은 **현재 서버의 strict subset**이다. wire에서 표현 가능한 Q0·음수 좌표와 실제 줍기 허용은 구별한다. 기존 프레이밍·암호화 경로를 재사용하며 F4 전용 opcode·추가 필드를 임의 발명하지 않는다.

**한 4E3E에 아이템 하나를 담으며, F4 선택 코드도 한 호출당 첫 대상 하나만 넘긴다.** 수동 클릭·수량 팝업·다른 행동도 같은 sender에 도달할 수 있으므로 단일 GET의 출처를 서버가 구별할 수 없다.

### 3.2 현재 처리 순서

1. [T/world_feature_reward.py](../../../tools/local_original_session/world_feature_reward.py):76–116의 `_world_pickup`이 요청을 파싱한다. x/y는 전달하지 않고 **UID·수량만** `runtime.dispatch_now(world.pc_pickup, ...)`에 넘긴다. 현재 entity 위치가 거리 판정의 기준이다.
2. [T/world_visibility.py](../../../tools/local_original_session/world_visibility.py):357–381 `pc_pickup`은 ground ITEM·현재 PC·월드 진입·사망 상태를 확인한다. `0 < 요청Q <= 바닥Q`이면 요청Q, 그 밖에는 **바닥 전체Q**로 정규화한다. ground API를 직접 호출했을 때의 잘못된 수량 거절과 같지 않다.
3. 같은 runtime 임계영역과 승인시각에서 ground 사전 확인 → bag 삽입/CAS → ground 소모 순서다. bag commit 예외이면 ground는 남는다. **개별 요청의 직렬화·메모리상 중복 방지**이며 전체 디스크 crash transaction을 입증한 것은 아니다.
4. [T/world_ground_items.py](../../../tools/local_original_session/world_ground_items.py):65–68,223–277 `check_pickup/pickup`은 현재 세대의 살아 있는 **Kind.PC**, 같은 맵, Chebyshev 거리≤3, 권한·수량·만료를 적용한다. pickup 자체의 LOS 검사는 없다. owner 독점10초·수명600초는 파일 상단에 명시된 **local_policy**다. L1J 유래 거리3·독점/수명 적용을 원본 클래식 F4의 반경1·규칙으로 승격하지 않는다.
5. 부분 소모는 동일 UID/ref/만료시각을 유지한다. 최종 소모는 timer 취소·entity 제거·`on_remove`를 거쳐 알려진 PC들에 `4E40`을 큐잉한다. bag 신규 row는 `0964` append, 기존 stack은 `0965` 절대 수량이다. pickup PC에는 해당 drain+bag 응답을 보낸다. 부분 소모의 ground 수량 갱신은 이 경로에서 별도로 구성하지 않는다.

### 3.3 동료 구현에서 그대로 복사하면 안 되는 부분

- `_world_pickup_commit`(:29–73)은 주인 bag의 **template만 같으면** stack을 합치며 신규 row는 `starter_fields`를 바탕으로 만든다. ground의 grade를 이 코드가 새 row에 전달하지 않는다. 무게 검사도 이 함수에는 없다. 동료 줍기의 인스턴스 정보·무게 보존 근거로 전용하지 않는다.
- 현재 주인 경로의 신규 UID는 해당 bag의 max+1, bag 제한은180칸, stack Q 상한은 int31이다. 이 값을 동료/전체 character UID 정책으로 무조건 복사하지 않는다.
- `replace_kit`의 성공을 항상 즉시 disk durable로 쓰면 안 된다. [T/inventory_store.py](../../../tools/local_original_session/inventory_store.py):255–286은 world persist 활성 시 기존 UID의 양수 Q만 변하는 stack 변경을 enqueue할 수 있다. 신규 UID/삭제/metadata 변경은 동기 쓰기 쪽이다. [T/world_bridge.py](../../../tools/local_original_session/world_bridge.py):128–155의 immediate 저장 경계에 `_world_pickup`은 없다.
- ground는 현재 **메모리 수명만** 소유하며 저장/복원이 없다(`world_ground_items.py` 상단 계약, `close`). 따라서 bag+ground 전체 crash 원자성·재접속의 ground 복원을 완료했다고 주장하지 않는다.

## 4. 서버가 “F4를 눌렀다”를 알아내는 방법

| 방안 | 판정·권장 |
| --- | --- |
| 확인한 F4 원본 경로 | 일반 GET`4E3E`를 재사용한다. 전용 F4 opcode를 추가해야 할 근거가 없다. |
| 개별 4E3E만 관찰 | 현재 schema에 입력 출처가 없으므로 서버만으로 exact F4를 판별할 수 없다. |
| 짧은 연속 pickup 묶음 | **권장하지 않음.** F4 한 호출은 첫 대상 하나이므로 “F4가 여러 요청을 보낸다”는 전제부터 맞지 않는다. 반복 F4·클릭 등의 burst 후보에 불과하다. |
| 클라이언트 semantic action의 로컬 bridge 이벤트 | **정확한 기능의 권장안.** 실제로 검증된 주변줍기 action에 선택적 로컬 intent를 연결한다. 물리 VK_F4에만 hook하면 재바인딩·UI action 경로를 놓칠 수 있다. 기존 원본 게임 패킷을 변조하거나 미확인 opcode를 만들지 않는다. |

휴리스틱을 비교 실험한다면 예를 들어 **같은 연결·현재 owner/map, 이동 없이 150ms 이내의 서로 다른 ground UID 2개 이상, 각 대상이 주변1셀**인 4E3E를 하나의 `pickup_burst_candidate`로 묶을 수는 있다. **150ms·2개는 출처 없는 실험값이며 도입 권장값이 아니다.** 정적 결과상 이것은 F4 한 번을 검출하는 기준이 될 수 없다. 실제 trace가 없으므로 적정 window도 미확인이고 수신 간격에는 지연·TCP 합류/분할·키 반복·action cooldown도 섞인다.

이 방식은 수동 클릭 연속·다른 자동줍기·key repeat를 오인한다. F4 한 번의 단일 요청은2개 기준에서 빠지고, 아이템1개는 클릭과 구별되지 않는다. 빈 바닥이나 클라이언트 상태 조건으로 후보가 없으면 이 경로는 GET 없이 끝날 수 있다. **“F4면 동료도 줍는다”를 보장하려면 exact action 신호가 필요하다.** 주인의 pickup 성공 여부와 입력 의도도 다르다. 주인 가방이 가득 차 실패해도 F4 의도는 있을 수 있다.

등록 접점 주의:

- [T/world_handlers.py](../../../tools/local_original_session/world_handlers.py):838–855에서 reward가 companion보다 앞이다. [T/world_bridge.py](../../../tools/local_original_session/world_bridge.py):422–435는 첫 True에서 frame dispatch를 끝낸다. **맨 뒤 새 모듈의 `FRAMES[4E3E]`로는 reward가 소비한 요청을 관찰할 수 없다.**
- `after_request`는 opcode만 받아 target/Q/성공/F4 출처를 모른다. 정확한 trigger의 대체물이 아니다.
- 개발용 burst 관찰이 필요할 때만 reward 앞의 읽기 전용 handler가 False를 반환하고 원 pickup을 계속하게 할 수 있다. 그 관찰자에서 저장·ground 소모를 해놓고 False로 넘기면 안 된다. 실제 구현의 권장 접점은 선택적 intent/task service다.

## 5. 동료 가방·이동·수명에서 재사용할 것

| 영역 | 현재 사실·근거 |
| --- | --- |
| 신원 | [T/world_companion.py](../../../tools/local_original_session/world_companion.py):54–71,144–169,212–233. character ID/owner character ID와 runtime actor/owner EntityRef를 분리한다. 동료 actor는 **Kind.NPC**다. |
| bag·장비 권위 | 같은 파일:118–120의 `equipment` dict는 효과 metadata다. 실제 bag·8개 장착 slot은 일반 character inventory/equipment store가 소유한다. |
| bag 서비스 | [T/world_feature_trade.py](../../../tools/local_original_session/world_feature_trade.py):18–28,49–117 `CompanionInventory`. 같은 `inventory_store`·`EquipmentStore`, character ID별 frames/states·restore·stats/weight refresh를 사용한다. 별도 JSON bag을 만들 필요가 없다. |
| 중량·stack 재사용 후보 | 같은 파일:154–213 `give`. 실제 보유·수량·장착·정의·무게를 확인하고 UID/Q를 제외한 **모든 instance metadata가 같은 stack**만 합친다. 신규 UID는 주인·대상·로드된 동료 bag의 사용 UID를 고려한다. 단, 이것은 **주인 bag→동료 bag의 GIVE**라 바닥 줍기 함수가 아니다. |
| 저장 복구 경계 | GIVE의 intent는 두 bag의 중단된 이전을 forward recovery한다. 이를 ground pickup의 복구 권위로 재사용했다고 주장하지 않는다. `companion.json`에는 runtime UID/target/timer가 저장되지 않으며 bag 저장은 별도다. |
| AI | [T/companion_ai.py](../../../tools/local_original_session/companion_ai.py):208–275 `step`은 생존·owner 유효성→hostile/PASSIVE→leash→HOLD→물약→magic→공격/전투 이동→추종/귀환 순서다. `_move`(:288–314)는 실제 next_move_at, 지형·점유, bounded path, move_consumer를 재사용한다. 새 timer loop나 순간이동은 필요 없다. |
| 기능 활성 범위 | [T/world_feature_companion.py](../../../tools/local_original_session/world_feature_companion.py):353–379,434–445는 현재 `SL_COMPANION=1` opt-in/KIT에서 bag과 AI를 설치하며 `manual-user-play` 경로를 거절한다. 이번 문서는 그 설정/제한을 바꾸지 않았고 현재 실행 활성 여부도 관측하지 않았다. |

## 6. 구현 단계 — 전부 제안, 이번에는 구현하지 않음

1. **주변줍기 intent 연결.** 확인한 F4 키 경로와 행동창 Loot가 합류하는`A3120`을 우선 연결 후보로 삼되, 상태 gate로 조기 반환하는 입력도 사용자 의도로 볼지와 함수 호출/키 반복의 중복을 구별해야 한다. 검증된 주변줍기 semantic action의 로컬 bridge intent를 선택적 기능으로 전달한다. owner의 현재 session/ref에 귀속하며 물리 키 문자열이나 GET 성공 카운터만으로 대체하지 않는다. 주인 요청을 처리한 뒤 다음 scheduler turn에 동료 작업을 깨워 주인의 정상 pickup을 선점하지 않게 한다. intent가 패킷보다 먼저 도착하거나 주인 GET가 아예 없는 경우의 순서는 후속 관측으로 정한다.
2. **유한한 후보와 작업 상태.** F4 시점의 동료 actor ref·owner ref·map과 ground 후보 refs만 보유한다. 후보를 계속 늘리는 상시 오토루팅은 하지 않는다. 최초 제안은 **동료 중심1셀·신호당 성공1객체**다. 후보를 골라 실제 아이템 타일 또는 정상 줍기 위치까지 기존 `_move` 경로로 이동해 집은 뒤 종료한다. 실패/이미 소모된 후보는 건너뛰되 이번 snapshot 밖의 새 drop은 추가하지 않는다. 더 넓은 탐색·한 신호로 모든 후보 순회·아이템 우선순위는 별도 local_policy 제안이며 사용자 확정이나 원본 F4 동작으로 취급하지 않는다. 같은 F4 재입력은 현재 작업을 갱신하고 중복 credit을 만들지 않는다. 수집 작업은 저장하지 않는다.
3. **기존 AI에 선택적으로 연결.** 기존 생존/owner 유효성·귀환·HOLD·응급회복·전투를 우선하고 일반 추종 전에 수집을 처리하는 것을 초기안으로 제안한다. HOLD는 이동하지 않고 허용 거리 안에서만 집는다. 현재 magic consumer는 응급회복뿐 아니라 공격·shield·RECOVER도 소비하므로 그 뒤에 둘 경우 전투가 길면 수집이 계속 대기할 수 있다. 기존 scheduler 위의 유한 종료시각을 두고 대기가 끝나면 정상 추종으로 복귀한다. 전투 중단·HOLD override는 아직 사용자 확정 사항이 아니다.
4. **actor 거리와 owner 권한을 분리.** 현재 `GroundItems.check_pickup`에 NPC ref를 넣으면 `GROUND_CURRENT_ALIVE_PC_REQUIRED`로 거절된다. 주인의 PC ref를 대신 넣고 동료 가방에 넣으면 위치 판정을 왜곡한다. 중립 pickup 서비스가 **실제 동료 actor 위치**와 **그 owner PC의 독점 권한**을 함께 사용하게 한다. 기존 PC 검사를 삭제/완화하거나 가짜 PC를 만들지 않는다. 타인의 독점기간인 아이템은 이번 후보에서 제외하며 권한 해제를 기다리며 탈취하지 않는다.
5. **동료 bag admission·저장 후 ground 소모.** 기존 bag 서비스에서 definition·grade 등 instance metadata, stack 일치, UID, 수량,180칸, 중량을 처리한다. `world_weight.can_add_weight`와 `CompanionInventory.calculated/refresh`를 재사용한다. 다른 feature의 ctx 메서드를 직접 호출하지 않도록 공통 서비스/주입된 callable로 좁게 연결한다. 같은 runtime 임계영역에서 현재 target/Q를 확인하고 bag CAS→ground 소모 순서를 유지한다. 성공을 durable pickup으로 정의한다면 해당 변경의 기존 저장 경계에서 실제 disk 완료를 확보해야 한다. 신규 journal/검사 체계를 선행조건으로 만들지 않는다.
6. **화면 통지·복원.** ground 제거는 기존 `on_remove→4E40`을 사용한다. 동료에게 들어간 아이템을 주인에게 `0964/0965`로 보내 주인 bag을 늘리지 않는다. 실제 동료 character bag을 저장·refresh하고, 나중에 그 법사를 직접 선택했을 때 기존 inventory loader로 복원되는지 확인한다. 부분 줍기를 지원한다면 바닥 잔량 통지와 중복 수량을 별도로 완결한다. 동료 pickup 애니메이션은 미확인 계약이며 임의 opcode/정적 연출을 발명하지 않는다.
7. **모듈 경계.** 새 기능은 고유 METHODS·startup 등록·선택적 task/consumer로 만든다. 새 모듈을 FEATURE_MODULES에서 빼거나 동료를 비활성화하면 기본값 None으로 기존 서버/다른 기능이 동작해야 한다. 코어에 특정 feature ctx의 필수 호출, 기존 METHOD 덮어쓰기, 요청 중 새 guard/핀/해시·소스 판독을 넣지 않는다. [WORLD_FEATURE_GUIDE](WORLD_FEATURE_GUIDE.md)의 `dispatch_now`·기존 send/drain·저장 owner 계약을 따른다.

충돌·정리 기준:

- 주인이 먼저 집었거나 만료된 ref는 해당 후보만 끝낸다. actor·owner·item의 현재 세대와 남은 Q를 같은 world 임계영역에서 확인해 두 번 credit하지 않는다. 여러 동료에 확장해도 같은 target ref를 중복 배정하지 않고 마지막 소모 확인은 생략하지 않는다.
- map 변경·owner/동료 사망·dismiss/recall·세션 이탈·캐릭터 전환·명령 변경에는 작업을 폐기하고 기존 scheduler handle 정리를 따른다. 기존 정리 접점은 `world_companion.py`의 `_stop/die/dismiss/clear`, `companion_ai.py`의 sync/command_changed다.
- 길 없음/이동 불변은 유한 시도 뒤 그 후보를 포기한다. 무게·bag full이면 이번 작업을 종료하는 것을 초기안으로 제안한다. 무한 이동/재시도나 매 tick 전 ground 전수검색을 하지 않는다.
- metadata/grade 대응을 모르면 starter 값으로 꾸미지 않고 해당 대상 실패로 남긴다. 저장이 성공했는지 불명확한 예외 뒤에는 같은 credit을 자동 반복하지 않는다. 원오류·부분 저장을 보존한다.

## 7. 후속 원본 확인·검증 범위

이번에는 다음 실행을 **하지 않았다**. 후속 실행이 별도 허용될 때 기존 정상 로그인→캐릭터 선택→월드 진입과 직접 실제 입력/요청의 순서에서 관측한다.

| 필요한 관측 | 닫을 질문 |
| --- | --- |
| 현재 사용자 재바인딩 reader·실행 상태와 확인된 기본 경로 비교 | 고정 원본의 기본F4 경로가 현재 설정에서도 선택되는지 |
| 아이템0/1/여러 개, 같은 칸/인접1/거리2, 모두줍기 On/Off에서 action별 C2S와 실제 상태 전이 | 정적 첫 대상1개·4E3E·vector순서와 실제 동작의 일치, Q·키 repeat·이동·cooldown |
| 같은 배치의 수동 클릭과 비교 | GET만으로 입력 출처를 구별할 수 있는지, 휴리스틱 오탐·누락 |
| 주인/동료 동일 ground, 동료 무게/가방 full, 타인 독점, 소환 해제·map 이동 | 중복 소모 없음·거절 시 ground 유지·작업 정리 |
| 동료 bag 저장 후 직접 법사 선택/재접속 | 동료 자신의 UID/Q/grade·중량/장비 보존, 주인 bag 불변 |

출처 비율은 **근거로 인용한 자료 기준100% 로컬 원본 자원·보존 REA·기존 코드**다. 외부 공식 API/웹/L1J를 이번에 새로 조사한 비율은0%다. 현재 서버에 이미 포함된 L1J 유래 규칙은 해당 코드에 명시된 local_policy로만 인용했다. 구현 단계와150ms 휴리스틱은 새 설계 제안이며 원본에서 확인된 비율로 합산하지 않는다.

검증 명령과 결과:

- `rg -n`으로 `string.csv`의 F4/모두줍기, 서버 pickup/parser/AI, 새 정적 원문의 RVA·호출을 대조했다. 위 본문에 확인/미확인을 분리했다.
- `Get-Content -Encoding UTF8`로 자원·원문·현재 코드를 읽었다. 기존 정적 reader는 실행파일을 띄우는 runner로 실행하지 않고 저장 섹션을 읽는 부분만 재사용했다.
- `python -` 인라인 문서 확인: 로컬 링크31개·누락0, 원문 txt/json36개(총1,086,461바이트), JSON 구문 정상, 분석 `.py/.ps1` 산출물 없음. 새 검사 파일/체계는 만들지 않았다.

이 검증은 문서·정적 원문 범위다. 게임·서버·포트·모듈 시험·입력·화면·저장 복원 결과는 **UNRUN/미확인**이다.
