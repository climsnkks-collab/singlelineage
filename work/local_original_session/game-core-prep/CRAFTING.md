# NPC 제작 데이터와 연결 경계

**현재 3차: 제작 NPC identity21종·19메뉴·93 NPC-제작식 연결(고유 native64식), 43연결 추가·세바스 메뉴 복구. 대표 파린·아라크네·세바스3식 실제 소켓 제작·저장·Quit 재접속 PASS.** 공식 대응 미확인 아이템10종과 90 NPC-식 연결은 OPEN이다. 카리프·조우의 돌 골렘은 원위치 배치만 추가했다. 상세는 [3차 추가](#3차-추가-2026-10-28)에 있으며 1·2차 본문과 당시 성공·실패 결과는 해당 시점의 기록으로 보존한다.

## 1차 기록

`tools/local_original_session/data/crafting.json`에 모리아·허버트·라다르·라이엔 **4명, 제작식18개, 결과/재료32종**을 작성했다. 고정 원본의 `craft.bin`·`npccraftlist.bin`에서 **native recipe ID·NPC별 목록·재료/수량·결과/수량18식**을 연결했다. 처음 참고한 L1J18식의 ID 변환 결과와 native18식이 모두 일치한다. 공식 사전은 결과 아이템과 제작 NPC의 대응을 추가 확인하는 자료다. 서버의 소비·반복 제작·스택 처리와 배치는 별도 `local_policy`로 구분한다. 퀘스트 수락/완료나 EXP 보상으로 바꾸지 않는다. 퀘스트 파일과 기존 후보 기록은 수정하지 않았다.

이 문서는 원문 확인과 데이터 연결을 기록한다. native catalog recipe reference, 원본 command→MAKE_REQ5의 주요3필드, Actor f39→동적 목록 입력, ACK6 성공·실패 분기를 정적으로 연결했다. 원본 클라이언트의 실제 표시·입력·송수신·ACK 소비는 미확인이다. 여기서 제작 데이터의 `available:true`는 로컬 계산에 필요한 ID·수량·아이템 정책이 갖춰졌다는 뜻이며, 원본 화면이나 요청 송신이 확인됐다는 뜻이 아니다. 실제 서버·포트·원본 클라이언트는 이 데이터 작업자가 실행하지 않았으며 시험 담당의 소켓 결과는 아래에 별도로 기록한다.

최종 native adapter까지 **개발시험19개를 통과**했다. 실제 소켓 시나리오2회는 각각 초기 인벤 freshness 실패와 alignment catalog startup 실패로 제작 요청에 도달하지 못했다. 원본 UI·native parser 소비·정상 재접속까지 완료됐다는 판정은 없다. 아래에 각 source/실행 결과를 분리해 보존한다.

## 원본 페이지와 NPC

UML 원문 루트는 `C:/Users/Chansol/Documents/Codex/2026-09-07/d-lineage-classic/outputs/decrypted-pack/data_0/data/uml/`이다. 기존 보존 복호본을 읽었으며 현재 LC에서 새 추출·실행한 자료는 아니다. 현재 클라이언트 비교 기준은 native dump의 `26.09.29.2001`이다. 기존 자원 교차검토 범위는 `M2_NPC_MENUS.md:30–45,77,131–154`에 보존돼 있다.

| NPC | native template/sprite | L1J identity·LOCAL 배치 | 페이지·원문 근거 |
|---|---|---|---|
| 모리아 | 346/1307, native dump204 | 70598, map4/33404,32834/h4; SQL22251·23858·49094 | `moria1.uml:8` craft_output→moria2; `moria2.uml:8–9` craft_input/request_craft; CSV280–283 |
| 허버트 | 347/1312, native dump205 | 70641, map4/33503,32777/h4; SQL22294·23884·49117 | `herbert1.uml:8` craft_output→herbert2; `herbert2.uml:8–9` craft_input/request_craft; CSV268–271 |
| 라다르 | 300/988, native dump181 | 70523, map0/32589,32957/h6; SQL22180·23812·49080 | `ladar1.uml:8` craft_output→ladar2; `ladar2.uml:8–9` craft_input/request_craft; CSV248–251 |
| 라이엔 | 302/981, native dump183 | 70525, map0/32575,32920/h4; SQL22182·23814·49089 | `lien1.uml:8` craft_output→lien2; `lien2.uml:8–9` craft_input/request_craft; CSV263–266 |

SQL은 `D:/SingleLineageRef/l1j-en-classic/db/l1jdb_m10.sql`, CSV는 `work/local_resource_provider/assets/data/dialogue.csv`, native dump는 `work/source_game_data/native-dump-v1.jsonl`이다. JSON NPC의 `npc_template_id`는 native ID, `l1j_npc_id`는 기존 Town의 정의 identity다. live Actor UID·메뉴 문맥·서버 발급 recipe reference와 혼용하지 않는다. 허버트 spawn의 설명 문자열은 `Helen`이지만 참조 NPC70641의 실제 SQL 정의·native 이름은 허버트다. 위치와 설명은 이 차이를 보존한 LOCAL 배치다.

각 `*2_s.uml`은 결과 대사와 back link를, `*2_f.uml:8`은 `dynamiclist custom="craft_fail"`을 보존한다. 원문이 있다는 사실만으로 실제 성공/실패 시의 서버 page 선택 조건을 확정하지 않는다. 기존 퀘스트 후보의 모리아 설명(`QUEST_EXPANSION.md:28,35`)은 당시 미연결 상태의 기록으로 보존한다.

## 제작식

아래 숫자는 **native 아이템 ID×수량**이다. 수량18식은 native craft.bin의 입력 f7.f1.f1/f2와 출력 f8.f1.f6.f1/f2를 읽은 값이며 L1J 참고값과 모두 일치한다. 이 정적 값 대응과 실제 서버 소비 규칙은 구별한다. 모든 결과는1개이며 입력에 포함된 아데나7을 로컬 제작 수수료로 소비한다. 추가 수수료·EXP·임의 직업 제한·확률은 만들지 않았다. 결과의 착용 직업을 제작 자격으로 해석하지 않는다.

제작식의 우선 출처(`formula_source:"client"`)는 고정 `craft.bin`·`npccraftlist.bin`이다. `D:/SingleLineageRef/l1j-en-classic/data/xml/NpcActions/ItemMaking.xml`은 수량이 일치한 교차참고이며 공식 사전은 제작자/결과 identity의 보조 확인이다. JSON `action`은 이 XML의 정확한 `Action Name`을 보존한 backend 참고 키이고 Classic 4ED4 action이 아니다. JSON root의 `local_policy`는 실제 서버 transaction/스택·배치 정책의 구분이며 제작식 수량의 출처를 L1J로 바꾸는 표시가 아니다.

`native_recipe_id`는 **결과 템플릿·배열 순번·L1J ID와 별개**다. native NPC346(모리아)의26→옷386/27→모자385,347(허버트)의18→티셔츠104/19→마법망토111/20→보호망토109,300(라다르)의1→고급피혁335/2→가죽모자317/3→가죽샌달321/4→가죽조끼327/5→가죽방패324/6→가죽투구319/7→가죽부츠323/8→중갑가죽조끼330/9→벨트334/10→벨트달린 가죽조끼328,302(라이엔)의15→해골투구320/16→뼈갑옷331/17→골각방패326이다. 각 NPC 목록은 npccraftlist의 `CraftNpcInfo.f1`과 `f3[].NpcCraftIds.f1`에서 직접 읽었다.

원본 경로는 `work/all_table_semantics/inputs/imported/bin/craft.bin`(67,369B, 기존 pin `f9a03e889bd9a72456ae7ee674219e03f05368b0d507bfd871f51e160e3f68e2`), 같은 폴더 `npccraftlist.bin`(1,138B, `0de0e113aeb5e4299ba48bc6494e0601d6000c28344fc2f62bec4eb2e0a8ecf7`)이다. `remaining/craft/README.md:3`·`report.json`은 `imported/bin/craft.bin→3772A0→SC_CRAFT_LIST_ALL_ACK_Craft` loader/schema와154 record f1=catalog key를 확인했다. `remaining/npccraftlist/README.md:3`·`fields.md:3–8`은29 NPC/185 recipe reference의 타입과 파서를 확인했다. 같은 폴더의 `remaining/craft/fields.md:36–45`와 출력 필드 표는 입력/출력 타입 근거다. 해당 scalar의 gameplay 의미가 소비자에서 미확정인 곳은 원 문서의 UNKNOWN을 그대로 유지한다. JSON에는 각 선택 record의 실제 binary offset/length와 필요한 입력 raw fields·출력 scalar를 보존했다.

| NPC/결과 | 재료 | XML action 및 줄 | 공식 제작처 원문 |
|---|---|---|---|
| 모리아/마법사 옷386 | 최고급 사파이어179×1, 마력의 돌166×25, 하얀 옷감379×2, 파란 옷감376×4 | `request magician dress`:502 | [386](https://api-goats.plaync.com/linclassic/v2.0/game/item/386?locale=ko-KR) |
| 모리아/마법사 모자385 | 고급 에메랄드172×2, 마력의 돌166×20, 하얀 옷감379×1, 붉은 옷감378×1, 파란 옷감376×1 | `request magician cap`:512 | [385](https://api-goats.plaync.com/linclassic/v2.0/game/item/385?locale=ko-KR) |
| 허버트/티셔츠104 | 붉은 옷감378×3, 파란 옷감376×2, 하얀 옷감379×10, 아데나7×30000 | `request t-shirt`:523 | [104](https://api-goats.plaync.com/linclassic/v2.0/game/item/104?locale=ko-KR) |
| 허버트/마법 망토111 | 붉은 옷감378×10, 파란 옷감376×2, 하얀 옷감379×1, 아데나7×1000 | `request cloak of magic resistance`:533 | [111](https://api-goats.plaync.com/linclassic/v2.0/game/item/111?locale=ko-KR) |
| 허버트/보호 망토109 | 붉은 옷감378×5, 파란 옷감376×5, 하얀 옷감379×10, 아데나7×20000 | `request cloak of protection`:543 | [109](https://api-goats.plaync.com/linclassic/v2.0/game/item/109?locale=ko-KR) |
| 라다르/고급피혁335 | 동물가죽332×20 | `request hard leather`:1097 | [335](https://api-goats.plaync.com/linclassic/v2.0/game/item/335?locale=ko-KR) |
| 라다르/가죽모자317 | 동물가죽332×5, 철괴333×1 | `request leather cap`:1104 | [317](https://api-goats.plaync.com/linclassic/v2.0/game/item/317?locale=ko-KR) |
| 라다르/가죽샌달321 | 동물가죽332×6, 철괴333×2 | `request leather sandal`:1112 | [321](https://api-goats.plaync.com/linclassic/v2.0/game/item/321?locale=ko-KR) |
| 라다르/가죽조끼327 | 동물가죽332×10 | `request leather vest`:1120 | [327](https://api-goats.plaync.com/linclassic/v2.0/game/item/327?locale=ko-KR) |
| 라다르/가죽방패324 | 동물가죽332×7 | `request leather shield`:1127 | [324](https://api-goats.plaync.com/linclassic/v2.0/game/item/324?locale=ko-KR) |
| 라다르/가죽부츠323 | 징박은 가죽샌달322×1, 고급피혁335×10, 철괴333×10, 아데나7×300 | `request leather boots`:1134 | [323](https://api-goats.plaync.com/linclassic/v2.0/game/item/323?locale=ko-KR) |
| 라다르/가죽투구319 | 투구90×1, 가죽모자317×1, 고급피혁335×5, 철괴333×5 | `request leather helmet`:1144 | [319](https://api-goats.plaync.com/linclassic/v2.0/game/item/319?locale=ko-KR) |
| 라다르/중갑가죽조끼330 | 징박은 가죽조끼329×1, 고급피혁335×15, 철괴333×15 | `request hard leather vest`:1154 | [330](https://api-goats.plaync.com/linclassic/v2.0/game/item/330?locale=ko-KR) |
| 라다르/벨트달린 가죽조끼328 | 가죽조끼327×1, 벨트334×1 | `request leather vest with belt`:1163 | [328](https://api-goats.plaync.com/linclassic/v2.0/game/item/328?locale=ko-KR) |
| 라다르/벨트334 | 고급피혁335×5, 철괴333×2 | `request belt`:1171 | [334](https://api-goats.plaync.com/linclassic/v2.0/game/item/334?locale=ko-KR) |
| 라이엔/해골투구320 | 가죽투구319×1, 뼈조각336×10, 아데나7×800 | `request skull helmet`:868 | [320](https://api-goats.plaync.com/linclassic/v2.0/game/item/320?locale=ko-KR) |
| 라이엔/뼈갑옷331 | 중갑가죽조끼330×1, 뼈조각336×20, 아데나7×500 | `request bone armor`:877 | [331](https://api-goats.plaync.com/linclassic/v2.0/game/item/331?locale=ko-KR) |
| 라이엔/골각방패326 | 징박은 가죽방패325×1, 뼈조각336×15, 아데나7×800 | `request bone shield`:886 | [326](https://api-goats.plaync.com/linclassic/v2.0/game/item/326?locale=ko-KR) |

공식 URL의 보존 응답은 `work/official_data_refresh_20261028/raw/item/{ID}.json:1`이며 `tools/local_original_session/data/official/items.json`에 URL·수집 시각·SHA256·native ID 대응이 있다. 각 제작식 `sources`에 해당 보존 경로와 URL을 기록했다. 이 응답의 `source.craft`/`source.npcs`는 제작처를 확인하지만 제작식·수량은 제공하지 않는다. 제작식 수량의 추가 원본 근거는 위 craft.bin이다. 2026-10-28 추가 web.open으로385/386/104/335 API를 열려 했으나 web 도구가 네 URL 모두 `not accessible`을 반환했다. 이 문서의 공식 사실은 당일 보존 응답을 직접 읽은 범위이며 새 live 웹 검증 성공으로 기록하지 않는다.

## 아이템 대응과 인벤토리 정책

`items`32행은 기존 plain kit producer를 위한 native f5 아이콘·f10 raw burden과 L1J 스택 정책이다. native f10의 실제 무게 단위까지 증명한 데이터는 아니다. `KitItemPolicy`의 기존 LOCAL 해석만 유지한다. 방어구와 벨트는 비중첩, 아데나·옷감·보석·마력의 돌·가죽·철괴·뼈조각은 해당 L1J etcitem `stackable` 컬럼을 쓴다. 각 행에 native dump 줄과 SQL 줄을 개별 기록했다.

- 결과385/386과166은 기존 `data/catalog/items_all.json`의 대응을 재사용했다. 옷감376/378/379는 native/SQL 이름 token·인벤 아이콘·ground graphic이 같지만 raw f10/SQL weight가 달라 기존 `candidate`를 유지한다. LOCAL identity bridge는 그 후보를 공식 동등성으로 승격하지 않는다.
- 고급 에메랄드172↔L1J40051은 native dump1087·SQL16505, 최고급 사파이어179↔40054는 native dump1094·SQL16508이다. 버전 간 이름 token은 바뀌었지만 한/영 보석명과 native f5/SQL invgfx·native f6/SQL grdgfx 쌍이 각각240/772,247/775로 같음을 확인했다. raw 수치/등급까지 동등하다고 하지 않고 별도 LOCAL 대응으로 기록했다.
- 투구는 L1J20043에 기존 confirmed 대응인 native90을 선택했다. native229는 같은 이름/token이어도 아이콘·ground·raw 수치가 다른 후보이므로 이 제작식의 재료로 대체하지 않았다. SQL의 blessed/cursed 변종을 native 등급으로 해독한 결론도 만들지 않았다.
- 가죽조끼327·징박은 가죽조끼329·중갑가죽조끼330과 일부 가공 재료는 원 카탈로그의 `candidate`/불일치를 각 행 `mapping`에 그대로 보존했다. 이름·용도에 맞는 L1J 제작식을 LOCAL로 연결하면서 native 아이콘과 raw 값은 native 값만 쓴다.

이번 제작 데이터는 재료의 새 상점·가격·드롭·채집·퀘스트 생산자를 추가하지 않는다. 개별 재료의 정상 획득 경로가 이미 제품에 있는지와 완전한 제작 플레이는 runtime/시험 담당의 실제 경로에서 별도로 판정한다. 제작 데이터18개를 전체 원본 제작 시스템 완료나 정상 재료 획득의 증거로 합산하지 않는다.

## 기존 요청·응답 근거

`request_craft`는 원본 등록 command다(`work/local_server_rea_20261016/run382_npc_dialog_menu/handler_registration_keys.tsv:7`, `handler_trace.md:25–33`). 일반 `haction` fallback4ED4로 보내거나 XML의 `request magician cap` 등을 원본 버튼 action으로 바꾸지 않는다. 고정 action 버튼으로 동적 목록을 대체하지 않는다.

`REQUEST_COVERAGE_MAP.json:9223–9445`에는 typed `CS_CRAFT_MAKE_REQ`의 opcode5와 정적 발신부 `5C4520→5C4E4B`, `5C4F30→5C559B`가 있다. compiled schema는 f1/f2/f3 uint32, f4 repeated `CraftInputItemSlotInfo`, f5 int32다. nested 타입은 f1/f2 uint32·f3 int64·f4–f7 uint32다.

이번 오케스트레이터 분석의 보존 instruction을 직접 읽었다. `runs/craft_protocol_20261028/asm_5caaf2.txt:6`에서 command 등록 builder `5CED50`을 호출하고, `asm_5ced50.txt`는 command 객체 vtable을 구성한다. 해당 command의 virtual+8 `5C4460`은 조건 분기 뒤 `5C4520`으로 연결한다(`asm_5c4460.txt:26`). `asm_5c4520.txt:22–24`의 UML+38→R12d와 CraftSubsystem+120→ESI가 각각 :252/:254에서 메시지 f1/f2 object slot에 기록되고, UML+40→EBX·최소1의 값이 :257에서 f3에 기록된다. 따라서 f1은 기존 NPC 대화 문맥, f2는 선택한 native recipe ID, f3은 요청 제작 수량의 정적 생산자다. 동일 함수의 catalog lookup `4D1590`과 f4 ingredient-node 생성은 추가 소비자 분석 범위이며 raw 재료 슬롯의 enchant/bless 의미·최종 ACK 성공 조건을 단순 이름으로 확정하지 않는다.

같은 문서의 정적 수신 등록은 LIST_ALL_ACK2(:99), ID_LIST_ACK4(:123), MAKE_ACK6(:147), BATCH_ACK8(:171), SUCCESS_COUNT_NOTI11(:219)다. 이름이 대응한다는 사실만으로 필수 ACK·원서버 순서·성공 enum을 만들지 않는다. LIST_ALL_REQ/ID_LIST_REQ/BATCH_REQ의 opcode는 기존 조사에서 UNKNOWN이며1/3/7로 추정하지 않는다. 로컬 craft.bin/npccraftlist가 원본 catalog를 공급하므로 새 server 목록 packet을 만들지 않는다. 아래 Actor f39→UML+3C의 정적 연결로 client-local craft_output/input이 NPC별 catalog를 고르는 입력을 공급했고, ACK6 enum은 별도 소비자 근거로 연결했다. 실제 렌더링/입력은 아직 실행하지 않았다.

## 등록형 native adapter와 Actor f39

선택 기능 `world_feature_craft.py`는 기존 `town_setup` 훅에서 이4NPC의 원래 root stem을 서비스 메뉴로 등록한다. 기존 `world.runtime_extensions.wrap('craft', town, 'appearance', wrapper)`를 통해 이 NPC들에만 `TownAppearance.wire_f39=native NPC template`을 기여한다. 기존 sprite가 없을 때만 검증된 native sprite를 사용하고, `runtime_stopped`에서 wrapper handle을 닫는다. 다른 선택 기능의 private 상태나 함수를 직접 호출하지 않는다.

f39의 원문 연결과 이번 연결을 구별한다. 기존 `run106_shop_dialog_contract/normal_npc_spawn_action/finalize.py:51`·`source-evidence.json`은 SC_NOTIFY_ACTOR f39→rawF4→C13F0의 InteractiveNPC+3C 복사를 확인했으나 그 당시에는 template 의미까지 부여하지 않았다. 이번 `runs/craft_protocol_20261028/impl_asm_5cceb0.txt:142,156,164,211–214`는 SC_HYPERTEXT_NOTI context를 UML+38에 쓰고 Actor를 resolve/dynamic_cast한 뒤 InteractiveNPC+3C를 UML+3C에 복사하는5CD1AE→5CD1B6를 확인한다. `impl_asm_a463c0.txt:65`의 A464A3은 그 UML+3C 값을 NPC craft-list 조회에 사용한다. 고정 npccraftlist의 nativeNPC346/347/300/302에 이 값을 대응시켰다. 이4NPC 바깥의 모든 Actor f39를 일괄 template로 재해석하지 않는다. 4E44의 f4에 임의 recipe 목록을 넣지도 않는다.

opcode5 처리기는 기존 원본 protobuf decoder/라우터를 통과한 요청의 current NPC 문맥·native recipe ID·제작 횟수와 raw slot/item/count/enchant/bless 입력을 native catalog와 대조한다. 현재 전달 완료된 NPC 메뉴·Actor generation·range/생존·동일 인벤/장비·무게·수량 조건을 재사용한다. `world_craft.py` 계산 결과를 기존 core의 inventory CAS·UID 할당으로 저장한 뒤 quantity/remove/add와 ACK6을 응답한다. 정식 native 입력 경로에 static 대체 버튼이나 별도 recipe 번호를 만들지 않는다.

성공 ACK6은 소비자에서 확인한 명시적f1=0이다. transaction 이전의 거절은 f1을 생략한 ACK6을 보내며, 이 빈 body의 native parser 수용은 아래 미확인 경계다. 저장을 시도한 뒤의 오류는 성공/거절 ACK로 숨기지 않고 기존 failure/partial 보존 경로로 전파한다. 단순 함수 계산·source 등록과 실제 원본 소비는 다음 실행 결과 범위에 따라 따로 판정한다.

## 데이터 확인

작성 과정에서 XML 실제 출력18개와 official source.npcs의 각 제작자 이름을 대조했고, 모든 결과/재료 ID가 고정 native dump에 존재하며32개 아이템의 명시 icon/raw_weight/stackable 정책으로 연결되는지 확인했다. 추가로 npccraftlist→craft catalog의18 recipe에 대해 결과ID/수량과 재료ID/수량 쌍이 JSON/L1J값과 모두 같은지 확인했다. 모리아 재료 보석2종은 SQL/native 두 그래픽을 직접 비교했고 native recipe의 원래ID로도 재확인했다. 이는 파일·원문 연결 확인이며 게임 시험이나 정식 PASS가 아니다. 엔진 개발시험과 실제 메뉴/저장 검증 결과는 담당 결과가 도착한 뒤 해당 source·범위로 기록한다.

## ACK6 소비자 추가 확인

`reverse-engineer-anything` 지침과 기존 PE/Capstone carrier를 재사용한 오프라인 정적 분석이다. carrier는 `work/rea_lineage_resume_20261013/main-gameplay/audit/metadata-v2/DERIVED_RESTORED_ANALYSIS_ONLY.exe`이며 기존 source SHA256 `c822838351d774a2022af434829a36dbd9bee030bf22182b834ca4e8659701a9`에 귀속한다. 원본 실행·포트 시험을 하지 않았고 main의5C4520 REA pseudocode timeout은 재시도하지 않았다. 원문 `rea_pseudocode_error.txt`는 `timed out awaiting tools/call after 300s`이며 native 분석 세션은 정상 close했다. REA pseudocode 성공을 주장하지 않고 Capstone/보존 catalog 근거만 사용한다. timeout을 제품 실패로 분류하지 않는다. 전체 결론은 `runs/craft_protocol_20261028/data_ack6_findings.json`과 해당 `data_asm_*.txt`에 보존했다. 제작 데이터 JSON은 시험 선정 이후 고정했다.

연결은 opcode6의 기존 publisher3144C0→314561에서 global17F4E40→2770B0이다. Craft 초기화4D09B0은4D09E3에서 callback4D1A10을 얻고4D09ED에서 같은 global17F4E40을4D2390 구독에 전달한다. callback4D1A68의 typed local copy vtable11E6410은 `SC_CRAFT_MAKE_ACK`의 정확한 vtable이다. 따라서 아래 분기는 이름으로만 추정한 ACK 대응이 아니다. source wrapper에는 generated object 앞8바이트가 있어 raw enum+40은 wrapper+48에서 읽는다.

- **pending 정리:** callback4D1B46은 CraftSubsystem+1D1을 항상0으로 만든다. 이후 f1 presence bit2가 있어야 enum 분기로 들어간다. f1이 없거나0/1 이외 값이면 이 callback의 페이지 publication은 없다.
- **f1=0:** 4D1BD7의 명시적0 분기는 성공 페이지로 이어진다. 원본 UML+48 stem을 복사하고 `_s` 또는 `_s_prob`를 붙인다. 이는 protobuf 기본값0을 성공으로 가정한 결론이 아니다. helper4D1830은 선택 recipe의 output-list f3를100000과 비교해 다르면 true다(4D188B/4D1892). 이번18식의 해당 원문값은 모두100000이므로 정상 current recipe lookup에서 `_s`가 선택된다. 최종 publication은4D1D00→5CC3A0이다.
- **f1=1:** 4D1BDC의 명시적1 분기는 **f6 presence가 있을 때만** `_f_prob`를 붙인다(4D1CCE–4D1CE8). f6가 없으면 페이지를 발행하지 않는다. 이 소비자는 일반 재료 부족을 `1→moria2_f`로 연결하지 않는다. native 부족재료 경로와 plain `_f` 선택은 별도이며 여기서 임의 대응을 만들지 않았다.
- **부가 필드:** f2 출력 repeated는 typed local copy/정리에서 확인했으나 이 callback 자체의 새 인벤 지급은 확인하지 못했다. f3는 presence와 local state+1BC==2 조건에서 일부 수량 상태를 갱신한다. f6는3개 정수를 subsystem+1C4/+1C8/+1CC에 복사하고+1C0을 켜며 `_f_prob` 분기에도 쓰인다. 필드의 세부 업무 의미를 이름으로 채우지 않았다.

따라서 빈 ACK6이 원본 parser를 통과해 이 callback까지 전달된다면 pending은 해제되고 페이지는 바뀌지 않는다는 조건부 결론은 가능하다. **빈 body의 native generic parser acceptance는 이 분석으로 증명하지 않았다.** 공식 서버 응답 순서·전체 enum 의미·실제 원본 화면 소비도 정적 분기와 별도다.

## 실행 결과와 현재 검증 경계

| 실행 | 결과 | 실제 도달 범위 |
|---|---|---|
| native 최종 개발시험 | 19 tests PASS/0.252초 | synthetic decoder/계산/저장·복원/API 계약; 원본 클라이언트 소비 제외 |
| 첫 bot47000 | FAIL/7 requests | 초기 AddInventory freshness 거절; 모리아/제작 전; cleanup 완료 |
| 최종 bot48000 | FAIL/0 requests·0 epochs | alignment catalog startup 실패; fixture_notes[]·재료 준비 전; cleanup 완료 |

native opcode5/ACK6 adapter 추가 **이전 backend 범위**에서 기존 unittest command `python -X utf8 -B -m unittest tools.local_original_session.world_craft_tests`를 실행했다. 최종 보존 출력은 같은 suite를 `unittest.TextTestRunner(stream=file, verbosity=2)`로 실행한 `runs/craft-tests-20261028-142345/unittest-final.txt`이며 **14 tests OK,0.353초**다. 정확한 재료 소비·생성/수량 프레임·반복 횟수·부족/착용/변형재료/무게 거절·UID 충돌·저장 후 응답·CAS 실패 시 미지급·기존 core 저장/재개·다른 캐릭터 보존·선택 기능 제외를 확인했다. 개발 fixture와 함수 호출 시험이며 native 요청 adapter 이후 전체판의 PASS나 원본 UI PASS로 확대하지 않는다.

첫 소켓 시나리오의 명령은 다음과 같다.

```powershell
$env:SL_TEST_TIME_SCALE='10'
$env:SL_TEST_PORT_BASE='47000'
python -X utf8 -B C:/Users/Chansol/AppData/Local/Temp/claude/D--claude/0483de89-75e7-4b94-84b8-fb31fe00f575/scratchpad/fastbot/run_fast.py hunt_bot_craft --navigation-timeout 180
```

`runs/craft-bot-xocqfzio/result.json`은 **FAIL**이며7 requests·9.393초다. FIRST의 로그인/선택/월드 진입 요청 후 초기 `API:AddInventory` 송신에서 `CURRENT_OWNER_REQUIRED`로 거절됐다. 원문 `failure_code`는 `INVENTORY_SEND_OUTCOME_UNKNOWN`이고 owner failure는 `POLICY_FRESHNESS`다. 관측 age540,627,300ns가 기존 fresh250,000,000ns를 넘었으며 identity/peer/alive 검사는 참이었다. 이동·모리아 클릭·제작 요청에는 도달하지 않았다. 시작 저장은 새 M5 레벨5 test_knight/기란 saved-map LOCAL fixture였고 제작 재료는 공급하지 않았다. 따라서 제작 성공·부족재료 응답·Quit 재접속 복원 결과가 아니다. finally 뒤 `cleanup_complete:true`, active task0·registry session0을 확인했고 실패 원문과 선정 소스 해시·시험 저장은 그대로 보존했다.

native adapter 시험 착수 전 동시 다른 작업에서 변경된 `tools/local_character_creation/realm.py`의 실제 SHA256은 `91cfbade7845273e8fa971c063acc9ac8e19e23ed848115a3074c6637863307a`였고 기존 acknowledgement 기대값은 `b594d067f844a5140fd8cab77e4a53f6eb2056fd4abdcd85ea3d421fdf14a80e`여서 import가 `EXACT_CHARACTER_CREATION_REALM_REQUIRED`에 막혔다. 이 진단 결과를 보존한다. 이후 다른 동시 작업의 기존 source pin 제거를 확인하고 오케스트레이터 지시로 아래 최종 시험을 진행했다. 제작 작업자는 realm/ack pin을 수정하지 않았다.

최종 개발시험 명령은 `python -X utf8 -B -m unittest tools.local_original_session.world_craft_tests -v`이며 `runs/craft-tests-native-20261028-143330/unittest-output.txt`에 **19 tests OK,0.252초**를 보존했다. 기존14개 외에 native request 필드/수량·중복 slot 거절·uint32 high-bit UID 보존/잘못된 sign-extended wire 거절·성공 후 메뉴 유지/이전 인벤 선택 무효화·명시적 성공enum0/거절enum 미위조를 확인했다. 선정 source는 같은 폴더의 `source-sha256.json`에 있다. 주요 조합은 `world_craft.py:581cce61edfc62b78c816cd766eff6f233b2557dc851b1e0f50e4d1fc17af98b`, `world_feature_craft.py:d3f15a8c5fa55db2ccc562f537ec90c8cd337c41aa0faa62a458824aa1cc8612`, `data/crafting.json:06e078e653c21eec5acef6b3a2d45ad0dff2532867ad72e372d8ca5f1cdcf8d3`이다. 직접 함수·synthetic 개발시험 범위이며 native 클라이언트가 이 패킷을 소비한 결과는 아니다.

포트48000 소켓 재실행은 위 bot 명령에서 `SL_TEST_PORT_BASE='48000'`으로 바꿔 실행했다. `runs/craft-bot-wnki11t2/result.json`은 **FAIL,3.120초,requests0/epochs0/fixture_notes[]/cleanup_complete:true**다. 서버 startup의 `world_alignment.py:145 load_alignment_catalog`에서 `ValueError: alignment catalog must cover current M1 monsters`로 중단됐다. 시험 담당의 읽기 전용 확인은 현재 M1에 추가된158 templates가 alignment catalog에 없는 입력 불일치다. FIRST·로그인·모리아 메뉴·native5·재료 준비 모두 미도달이다. 결과의 `starting_save`에 적힌 “recipe27 materials supplied before login”은 예정 fixture 설명이며 실제 공급/저장 생성의 증거가 아니다. 이 실행의 실제 공급은 없었다. 테스트별 선정 해시는 해당 result의 `selected_source_sha256`에 보존했다. 이 실패는 native 제작 동작의 실패/성공으로 확대하지 않고 startup 입력 불일치로 남긴다. 추가 재실행이나 외부 파일 수정은 하지 않았다.

현재 native wire의 producer·ACK consumer 정적 근거, 실제 코드 연결, 개발시험, 소켓 실행 범위를 구분한다. **아직 남은 실동작 확인**은 startup alignment catalog 입력을 정리한 선정판에서 정상 메뉴→client-local 선택→opcode5→원자 소비/생성→ACK6/인벤 소비→반복/저장/정상 재접속, 원본 craft_output/input 표시와 입력, 빈 거절 ACK의 native parser acceptance다. inventory freshness 실패·당시 realm pin 불일치·alignment startup 실패를 제작 자체의 기능 성공/실패로 바꾸지 않는다.

## 2차 추가 (2026-10-28)

고정 `craft.bin`154식과 `npccraftlist.bin`29NPC·185 reference를 기존 `tools/all_table_semantics/remaining.py:parse`로 읽었다. 실제154식에 대응하는 reference183개와 `uint64(-1)` sentinel2개를 구분했다. 원본 파일은 수정하지 않았다. 입력 f7.f1과 결과 f8.f1.f6의 ID·수량, 원본 재료 slot/raw fields, 선택 record offset/length를 기존 형식으로 `crafting.json`에 추가했다. 원본 스칼라의 미확정 성공률·조건을 공식 규칙으로 해석하지 않으며 기존 plain 재료·확정 결과 LOCAL 계산 정책을 유지한다.

등록 판단은 기존 `_default_item_policies`의 `load_items`·실 상점 정책·기존 stack fallback, 기존 quest 정책, 1차 craft의32개 정책 중 `grant_fields`가 있는566종의 합집합이다. 2차는 `items`32행을 그대로 두었으며 미등록 아이템을 허용하기 위한 새 정책·아이템 정의·상점·드롭을 만들지 않았다. 배치는 기존 M2+M4+M5 `TownData`의 선택된 native identity·count>0·활성 village scope를 기준으로 했다. 새 NPC spawn이나 scope 활성화는 하지 않았다. 추출 스크립트와 NPC별 채택/제외 전량은 `runs/craft-phase2-20261028/extract_phase2.py`·`extraction.json`에 있다.

| NPC (native / 서버 L1J identity) | 1차 연결 | 2차 추가 | 현재 연결 | native recipe ID | 현재 메뉴 |
|---|---:|---:|---:|---|---|
| 모리아346 / 70598 | 2 | 0 | 2 | 26,27 | moria1 |
| 허버트347 / 70641 | 3 | 0 | 3 | 18–20 | herbert1 |
| 라다르300 / 70523 | 10 | 0 | 10 | 1–10 | ladar1 |
| 라이엔302 / 70525 | 3 | 0 | 3 | 15–17 | lien1 |
| 빈센트348 / 70034 | 0 | 10 | 10 | 1–10 | vincent1 |
| 헥터337 / 70642 | 0 | 5 | 5 | 21–25 | hector1 |
| 세바스338 / Dio(디오)70027 | 0 | 17 | 17 | 135–148,165–167 | OPEN: dio1 자원 없음 |
| 합계 | 18 | 32 | **50** | **고유40식** | **메뉴 가능33연결** |

빈센트의10식은 라다르와 같은 native1–10을 공유한다. JSON의 NPC별 고유 `id`와 `_world_craft_native[(l1j_npc_id,native_recipe_id)]` 조회를 사용해 한 NPC의 연결이 다른 NPC의 연결을 덮어쓰지 않게 했다. 기존 current menu·대상·입력·소유·저장 검사는 그대로 사용한다. 코어 계산 모듈 `world_craft.py`는 변경하지 않았다.

헥터5식의 결과는 강철 장갑365·강철 장화366·강철 판금 갑옷367·강철 부츠368·강철 방패369다. 표기 이름은 고정 native ID가 기준이며 각 재료/수량 원문은 JSON의 `native_catalog.inputs`와 `materials`에 있다. 세바스17식 결과는 마나의 반지12405, 지식의 반지12860, 민첩의 반지15385, 완력의 반지15384, 완력/민첩/체력/지식/지혜/매력의 목걸이306–311, 불/물/땅/바람 정령의 벨트3934–3937, 멸마의 반지497·목걸이15090·벨트15091이다.

native338의 원래 이름은 **세공사^세바스**(`native-dump-v1.jsonl:202`)다. 서버의 기존 L1J70027 이름은 `Dio`, 기존 `data/m5/town_npcs.json`의 단일 native candidate·selected_classic_npc_id338을 재사용했다. 버전 간 이름을 같다고 바꾸지 않았다. 이 배치의 L1J 기본 dialogue는 `dio1`이지만 보존 UML에는 해당 파일이 없고 기존 `data/m5/npc_menus.json` binding도 `initial_stem:null / UNAVAILABLE_NO_CURRENT_RESOURCE`다. 따라서 제작 NPC 데이터의 `menu_stem:null`을 유지하고 `town_setup`이 메뉴 발급을 건너뛴다.17식은 데이터·LOCAL 계산만 연결됐으며 정상 메뉴→원본 입력을 통한 제작은 **OPEN**이다. 가짜 page·다른 NPC page·정적 대체 버튼은 만들지 않았다.

### 미등록·미배치 제외 목록

다음133 NPC-식 연결은 현재 서버 배치 조건을 충족하지 않아 추가하지 않았다. 이 중 카리프6식·헤이즐3식은 아이템 등록 조건도 충족하지 않는다. 별도로 디오 목록의 `18446744073709551615`2개는 catalog에 없는 sentinel이며 제작식 수에 넣지 않았다. 제외 원문과 개별 missing ID는 `runs/craft-phase2-20261028/extraction.json:excluded`에 보존한다.

| native NPC | 제외 native recipe ID | 이유 / 미등록 item ID |
|---|---|---|
| 호런166 | 74–87,96–104 | 기존 서버 배치 없음 |
| 줄리303 | 1–10 | 기존 서버 배치 없음 |
| 파린301 | 11–14 | adjacent 배치 원문만 있음, `include_adjacent=False` |
| 핀304 | 11–14 | 기존 서버 배치 없음 |
| 죠엘305 | 15–17 | 기존 서버 배치 없음 |
| 루디엘559 | 28 | 기존 서버 배치 없음 |
| 나르엔159 | 29 | 기존 서버 배치 없음 |
| 아라크네136 | 30–32 | 기존 서버 배치 없음 |
| 페어리137 | 33,34 | 기존 서버 배치 없음 |
| 페어리 퀸146 | 33–35 | 기존 서버 배치 없음 |
| 판138 | 36,37,68 | 기존 서버 배치 없음 |
| 네루파143 | 38–67 | 기존 서버 배치 없음 |
| 에브롤509 | 105,106,113 | 기존 서버 배치 없음 |
| 이벨빈605 | 69–73 | 기존 서버 배치 없음 |
| 로빈우드1330 | 129 | 기존 서버 배치 없음 |
| 카리프1367 | 126–128,132–134 | 미배치, 결과12333–12335·12371–12373 미등록 |
| 류미엘1368 | 107–112 | 기존 서버 배치 없음 |
| 헤이즐 이스터10182 | 114–116 | 미배치, 결과12193–12195 및 재료12192 미등록 |
| 샤미드10214 | 130 | 기존 서버 배치 없음 |
| 파울로10132 | 89–95 | 기존 서버 배치 없음 |
| 조우의 돌 골렘10232 | 151–163 | 기존 서버 배치 없음 |
| 엘리샤10298 | 164 | 기존 서버 배치 없음 |

카리프의 recipe126/127/128은 각각 결과12333/12334/12335,132/133/134는12371/12372/12373가 미등록이다. 헤이즐114/115는 결과12193/12194,116은 재료12192와 결과12195가 미등록이다. 누락 아이템을 새 정의로 채우지 않았다.

### 2차 검증과 실제 소켓 범위

`python -X utf8 -B -m unittest tools.local_original_session.world_craft_tests`에 해당하는 suite는 **25 tests OK,2.269초**다(`runs/craft-phase2-20261028/unit-tests-final.log`). 기존19개를 유지하고6개를 추가했다. 전체50연결의 원본 ID/수량·NPC별 reference 대조, 신규32연결의2회 반복 정확 소비·기존 정책 출력, 공유 recipe의 current NPC 선택, Dio null root 미발급, 저장된 시작 kit의 CAS append·아데나 단일 스택 보존을 확인했다. 직접 함수 개발시험을 실제 원본 실행으로 확대하지 않는다. 초기 신규 시험 fixture 오류1건은 `unit-tests.attempt1-fail.log`로 보존했다.

실제 소켓 명령:

```powershell
$env:SL_TEST_TIME_SCALE='10'
$env:SL_TEST_PORT_BASE='48000'
python -X utf8 -B C:/Users/Chansol/AppData/Local/Temp/claude/D--claude/0483de89-75e7-4b94-84b8-fb31fe00f575/scratchpad/fastbot/run_fast.py hunt_bot_craft --recipes vincent_native_1,hector_native_21,hector_native_24
```

| 2차 실행 | 결과 | 실제 범위 |
|---|---|---|
| 47000 / craft-bot-kxx1wsge | FAIL,요청0,cleanup 완료 | M5가 이미 저장한 starter에 `grant`를 재호출한 fixture 충돌 `INVENTORY_STORE_ITEM_CONFLICT`; 로그인 전 |
| 48000 / craft-bot-s54ovunc | FAIL,요청97,cleanup 완료 | 빈센트 실제 메뉴·request5 도달, 중복 아데나 fixture로 `UNIQUE_ADENA_STACK_REQUIRED` 거절·빈 ACK6; 제작 미소비 |
| 48000 재사용 / craft-bot-1m88gs1q | **PASS,26체크·122요청,2epochs,cleanup 완료** | 정상 로그인→선택→월드, 빈센트1·헥터21/24 실제 소켓 제작, 명시 ACK6 f1=0, 정확 소비/결과/수신 인벤/저장 일치, 정상 Quit·재접속 복원 |

실패 저장·원문은 위 각각의 `runs/craft-bot-*/result.json`·`requests.jsonl`에 남겼다. 중복 공급은 `hunt_bot_craft`의 로그인 전 fixture에서 기존 스택을 증가시키고 core `InventoryTransactions.commit_inventory(...,append=True)`로 저장하도록 수정했다. 제품의 아데나 단일 스택·소유·CAS guard는 수정하지 않았다. 셋째 실행의 세 결과는 고급피혁335, 강철 장갑365, 강철 부츠368이다. 원본 재료 획득 시험은 아니며 새 기란 saved-map 레벨5 test_knight에 정확한 재료만 로그인 전에 공급한 LOCAL 시험 저장에서 진행했다.

성공 결과의 `selected_source_sha256`에 당시 소스 조합을 보존했다. 핵심은 `world_craft.py:581cce61edfc62b78c816cd766eff6f233b2557dc851b1e0f50e4d1fc17af98b`(변경 없음), `world_feature_craft.py:ed7de6aea2d48a2e5ff296a871118c0a67aa613ace3e99fee2f747e02ba1e467`, `data/crafting.json:c568b3c60b73abf3145bc754eb326ce753c94d389b870ec1bbd5fddf73608a12`다. 실행 wall15.590초·가속시간43.739초이며 `FAST_CLOCK`의 child exit는0이다. PowerShell의 stderr 처리 문구가 남아 있어도 판정은 보존 `result.json`과 child 결과에 따른다.

**미확인:** 원본 클라이언트는 실행하지 않았다. craft_output/input 표시·버튼·native 송신/ACK 소비·빈 거절 ACK parser 수용, 디오17식의 원래 대화 자원과 입력 연결, 정상 재료 획득 경로는 미확인이다. 실제 소켓 PASS는 위3식과 선정 소스·시작 저장·수신/소비/저장/재접속 범위이며50연결 전체 원본 동등성으로 확대하지 않는다.

변경 제품 파일은 `data/crafting.json`, `world_feature_craft.py`, `hunt_bot_craft.py`, `world_craft_tests.py`이며 이 문서와 위 runs 산출물을 함께 보존한다. 현재 `work/local_original_session/manual-play/start-manual-play.ps1`의 `$pins`에는 이4파일이 없어 이번 변경으로 갱신할 기존 핀 항목은 없다. 실행 스크립트·launcher·사용자/수동시험 프로필은 수정하지 않았다.

## 3차 추가 (2026-10-28)

**데이터 연결은 93 NPC-제작식 연결·고유 native64식, 제작 NPC identity21종이다.** 2차50연결에43연결을 추가했다. 메뉴를 연결한19NPC가93연결을 담당하며 카리프·조우의 돌 골렘2NPC는 원문 위치 배치만 추가하고 제작 메뉴는 발급하지 않는다. 미등록 아이템10종은 공식 대응을 확보하지 못해 추가하지 않았다. 아래는 데이터·개발 계산 확인이며 실제 소켓과 원본 화면의 판정은 별도 실행 결과에 귀속한다. 1·2차 당시의 실패·소스·결과는 그대로 보존한다.

### 추가한 NPC와 제작식

위 제작식 우선순위와 같은 고정 `craft.bin`·`npccraftlist.bin`을 기존 `remaining.py:parse`로 읽었다. 신규43연결은 입력 `f7.f1` 전량과 결과 `f8.f1.f6`의 native ID·수량을 그대로 쓴다. 모든 새 연결의 입력 `f4=0/f5=1`, 별도 `f7.f2` 없음도 확인했다. 각 record offset/length·slot·raw fields는 JSON `native_catalog`에 있다. 기존 `items`32정책과 일반·상점·quest의 등록 정책만 재사용했다. misc·무기·방어구 정의, 상점·가격·드롭·재료 생산자는 추가하지 않았다.

다음 숫자는 `native recipe ID→결과 native item ID`이며 결과 수량은 모두1이다. 입력 수량 전량은 해당 JSON `materials`와 원문 `native_catalog.inputs`에 있으며 공식 사전에 없는 수량을 공식 규칙으로 주장하지 않는다. 원문 정적 대응과 LOCAL 소비·성공 정책은 구분한다.

| NPC native / 서버 identity | 추가 연결 | native recipe→결과 | 원래 위치 map/x/y·배치행 수 | 원래 spawn SQL 줄 | 연결 메뉴 |
|---|---:|---|---|---|---|
| 아라크네136 / 70846 | 3 | 30→251,31→259,32→257 | 4/33139/32262 외9곳·10행 | 49097–49106 | arachneE1→arachneE2 |
| 페어리137 / 70851 | 2 | 33→261,34→252 | 4/33158/32276 외13곳·14행 | 49120–49133 | fairyE1→fairyE2 |
| 판138 / 70850 | 3 | 36→264,37→265,68→268 | 4/33009/32403 외9곳·10행 | 49107–49116 | panE1→panE2 |
| 페어리 퀸146 / 70852 | 3 | 33→261,34→252,35→256 | 4/33157/32276·1행 | 49095 | fairyqE1→fairyqE2 |
| 나르엔159 / 70837 | 1 | 29→262 | 4/33070/32337·1행 | 49085 | narhen1→narhen2 |
| 파린301 / 70537 | 4 | 11→318,12→322,13→329,14→325 | 0/32413/32983·1행 | 49088 | farlin1→farlin2 |
| 줄리303 / 70805 | 10 | 1→335,2→317,3→321,4→327,5→324,6→319,7→323,8→330,9→334,10→328 | 4/33112/33357·1행 | 49090 | ladar1→ladar2 |
| 핀304 / 70807 | 4 | 11→318,12→322,13→329,14→325 | 4/33071/33383·1행 | 49091 | farlin1→farlin2 |
| 죠엘305 / 70804 | 3 | 15→320,16→331,17→326 | 4/33089/33355·1행 | 49092 | lien1→lien2 |
| 에브롤509 / 70872 | 3 | 105→145,113→551,106→417 | 62/32739/32815·1행 | 49086 | eveurol1→eveurol5 |
| 루디엘559 / 70841 | 1 | 28→86 | 4/33035/32325·1행 | 49084 | luudiel1→luudiel2 |
| 류미엘1368 / 70676 | 6 | 107→505,108→506,109→507,110→936,111→937,112→938 | 4/34122/33148·1행 | 49083 | ryumiel1→ryumiel2 |
| 카리프1367 / 70762 | 0 | 126–128,132–134 보류 | 4/33701/32512·1행 | 49135 | 원문 karif1/5→2 보존, 발급 null |
| 조우의 돌 골렘10232 / 71252 | 0 | 151–163 보류 | 4/33712/32494·1행 | 50232 | 원문 joewoogolem1→2→3 보존, 발급 null |
| 합계 | **43** | **기존 포함93연결·고유64식** | **45 source행: 신규44행+파린1행 재분류** | | |

SQL 원문은 위 `D:/SingleLineageRef/l1j-en-classic/db/l1jdb_m10.sql`이다. NPC 정의·npcaction·모든 반복 spawn과 native 이름·sprite 근거는 각 JSON NPC `sources`, `town_npcs`의 원문행, `runs/craft-phase3-20261028/npc_sources.json`에 보존했다. native dump 줄은 아라크네84·페어리85·판86·퀸90·나르엔102·파린182·줄리184·핀185·죠엘186·에브롤285·루디엘320·카리프551·류미엘552·조우 골렘850이다.

배치는 **LOCAL 원문 위치 정책의 명시 확장**이다. M5의 옛 five-town bounds 밖 제작 NPC를 마을 안 좌표로 옮기지 않았다. `data/m5/town_npcs.json:scope`에 map4의 원위치와 기존 지원 map62의 에브롤까지 포함함을 명시했다. `npcs`/`scope:village`는 기존 활성 배치 bucket을 재사용하는 LOCAL 선택이며 모든 중심이 옛 마을 bounds 안이라는 뜻이 아니다. 45 source 중심은 기존 S32 `can_stand=True`였다. count·heading·random 범위·movement_distance 원문을 보존하고 이 서버의 기존 고정 중심 NPC 정책을 재사용한다. 실제 이동·생성·충돌·화면 동등성을 정적 S32로 대신하지 않는다.

파린은 M2 `adjacent_npcs`의 기존 spawn87200 한 행을 동일 좌표·count·identity 그대로 `npcs`로 이동했다. 해당 행의 `crafting_placement_policy.previous_scope`와 문서 `scope.crafting_extension`에 예외를 남기고 집계도 갱신했다. 중복 spawn을 만들거나 전역 `include_adjacent`를 켜지 않았다. 에브롤 map62는 기존 `world_maps.load_dungeon_policy()`와 `world_terrain.LAZY_MAP_IDS`의 지원을 확인했으며 새 맵·전환은 구현하지 않았다.

native 이름 token은 각 선택 L1J NPC와 일치한다. 줄리·죠엘의 L1J gfx1509·696과 native sprite706·794 차이는 보존하고 실제 appearance는 native f2를 쓴다. 버전 간 외형이 같다고 주장하지 않는다. 줄리/핀/죠엘의 SQL npcaction은 각각 ladar1/farlin1/lien1을 지정한다. 이 retained page들은 `<var src="name"/>`와 일반 제작 문구·동적 목록을 쓰므로 그 원래 generic 메뉴 alias를 LOCAL로 채택했다. 다른 NPC의 고정 결과 버튼을 복제하지 않았다. 다른 신규 NPC도 정확한 대소문자를 가진 원문 `craft_output`→`craft_input/request_craft` chain을 재사용한다.

### 세바스 메뉴 정정

2차의 native338 / 서버 Dio70027 연결은 L1J alias `dio1` 검색 실패로 OPEN이었다. 고정 native 이름은 **세공사^세바스**이며 retained `sebas1.uml:11`에 `craft_output→sebas2`, `sebas2.uml:11–12`에 `craft_input/request_craft`, `sebas2_s`·`sebas2_f`가 존재한다. `dialogue.csv:3292–3301`도 세공 대사·성공·실패 문구를 보존한다. 3차는 동일 NPC의 `menu_stem/detail_stem`만 sebas1/sebas2로 연결하고 기존17식과 서버 identity/key(`dio_native_*`)는 유지했다. 2차의 dio1 부재 사실을 지우거나 새 원본 화면 성공으로 바꾸지 않는다.

### 미등록 아이템과 보류 제작식

고정 native catalog에 있는 다음10종은 당일 보존 official613종 목록에 없었다. 추가로 같은 공식 `/game/item/{ID}?locale=ko-KR` endpoint에 직접 HTTP 조회한 결과 **10개 모두 HTTP200,2바이트 `{}`**였다. 같은 요청 방식의 대조386은 HTTP200,746바이트로 `id/name/categoryName` 등을 반환했다. 이는 이 endpoint에서 해당 ID의 공식 상세를 얻지 못했다는 관측이며 모든 공식 자료에서 영구 부재한다는 결론이 아니다. ID 응답 원문·URL·시각·상태는 `runs/craft-phase3-20261028/official-probes/`의 개별 JSON·`responses.json`·`386-control.json`에 있다. 이10종은 native 전용 새 정의나 장비 스탯 추측으로 채우지 않았다.

| native item | 이름 | 영향을 받는 native recipe | 남은 입력 |
|---|---|---|---|
| 12333/12334/12335 | 카리프의 붉은/고급 붉은/최고급 붉은 주머니 | 126/127/128 결과 | 공식 대응 상세·등록 정책 |
| 12371/12372/12373 | 카리프의 푸른/고급 푸른/최고급 푸른 주머니 | 132/133/134 결과 | 공식 대응 상세·등록 정책 |
| 12192 | 황금빛 이스터에그 | 116 재료 | 공식 대응 상세·등록 정책 |
| 12193/12194 | 황금알을 낳는 모자/밀짚모자 | 114/115 결과 | 공식 대응·실제 장비 스탯/계약 |
| 12195 | 세공된 달걀 보석함 | 116 결과 | 공식 대응 상세·등록 정책 |

조우 골렘151–163은 등록 아이템이 있어도 **단순 재료식으로 추가하지 않았다.** 원문 `CraftInputList.f2`(`craft/fields.md:47` 이하)에 recipe마다 추가 slot4가3행씩 있으며 `f4=9`, `f5=1/0/2`, 표시문자열 `+9 $...`를 가진다. 예를 들어151은 추가 native278×1을 이3변형으로 명시한다. 151/156→278,152/157→235,153/158→2,154/159→274,155/160→358,161→269,162→81,163→233이다. 기존 adapter/계산은 plain 입력 `f7.f1`만 처리하며 강화·변형 입력의 선택/실소비 계약이 없다. 이 목록을 무시하면 주요 무기 재료를 생략하게 되므로13식은 `recipes`에서 제외하고 `native_catalog.deferred_recipes`에 offset·f7.f1·f7.f2 raw·출력을 보존했다. 초안의 plain 계산 성공은 완전한 제작식 근거가 아니며 해당13식의 소켓 실행은 하지 않았다. 기존2차50연결에는 f7.f2가 없어 이 발견의 영향이 없다.

| 남은 native NPC | 보류 native recipe | 직접 부족한 입력 |
|---|---|---|
| 호런166 | 74–87,96–104 (23식) | 원문 spawn map16은 현재 지원맵 아님 |
| 네루파143 | 38–67 (30식) | 원문 spawn map17은 현재 지원맵 아님 |
| 이벨빈605 | 69–73 (5식) | 원문 spawn map66은 현재 지원맵 아님 |
| 로빈우드1330 | 129 | 같은 token의 SQL90004/Cronos에 spawn 없음; 원위치 필요 |
| 카리프1367 | 126–128,132–134 (6식) | 위6개 결과 아이템 등록 근거 |
| 헤이즐10182 | 114–116 (3식) | 위4개 재료/결과 아이템 근거와 source NPC 위치 |
| 파울로10132 | 89–95 (7식) | 고정 native 이름에 대응하는 source NPC 위치 |
| 샤미드10214 | 130 | source NPC 위치 |
| 조우의 돌 골렘10232 | 151–163 (13식) | f7.f2 강화/변형 입력 실제 선택·소비 계약 |
| 엘리샤10298 | 164 | source NPC 위치 |
| 합계 | **90 NPC-식 연결 OPEN** | 별도 uint64(-1) sentinel2개는 식에서 제외 |

각 제외 사유·missing ID는 `runs/craft-phase3-20261028/extraction.json:excluded`에 있다. 정상 재료 획득 경로, 원본 화면의 제작 목록·입력·native 송수신/ACK 소비·빈 거절 parser 수용은 계속 미확인이다. 기존 LOCAL 확정 결과 정책의 추가 연결을 원본 확률·자격·강화 입력까지 복원한 것으로 확대하지 않는다.

### 3차 개발 확인과 실제 소켓 검증

포트 없는 한정 개발 명령은 다음과 같다.

```powershell
python -X utf8 -B work/local_original_session/runs/craft-phase3-20261028/phase3_development_tests.py
```

선정판 **4 tests OK,1.790초**(`development-tests-selected.log`)다. 새43연결 전부2회분의 정확한 plain 입력 소비/결과·입력 불변, 기존 TownData로45배치행과 파린 중복없음·map62 로딩, 기본 기란 시작 유지/선택 recipe의 원위치 인접 S32 셀 시작 fixture, 세바스 메뉴 및 미등록10종/추가 입력13식의 비활성화를 확인했다. 직접 함수·정적 로더 범위이며 원본 실행이나 소켓 PASS가 아니다. 최초 시험 harness가 import한 기존 Phase2 TestCase까지 자동발견해 옛50/7과 Dio null 기대2개가 실패했고, 신규4개만 선택하도록 harness를 고쳤다. 제품의 기존 `*_tests.py`는 변경하지 않았으며 그 옛 기대값 정리는 통합 담당 범위다.

`hunt_bot_craft.py`에 `--start-near-recipe <선택 recipe key>`만 추가했다. 해당 NPC의 보존 map/x/y와 인접 S32 서 있을 수 있는 한 셀을 새 시험 저장의 **로그인 전 LOCAL 시작 위치**로 쓴다. 인자가 없으면 기존 기란(4,33438,32796)을 유지한다. 재료는 기존 로그인 전 fixture·스택·CAS를 그대로 사용하고 guard·메뉴수신·native request/ACK·Quit/복원은 바꾸지 않았다. 이 fixture는 해당 NPC까지 정상 여행하거나 재료를 획득한 근거가 아니다.

검증 worker는 위 신규4개 선정판 로그를 재사용했고 중복 실행하지 않았다. 기존 개발시험은 다음 명령으로 실행했다. 원문은 `runs/craft-phase3-20261028/existing-tests.log`에 보존했다.

```powershell
$env:SL_TEST_PORT_BASE='47000'
$env:SL_TEST_TIME_SCALE='10'
python -X utf8 -B -m unittest tools.local_original_session.world_craft_tests tools.local_original_session.misc_items_tests tools.local_original_session.game_data_tests tools.local_original_session.equipment_stats_tests
```

합계46개 중42개 통과,4개 실패(9.303초)이며 기대값은 수정하지 않았다.

| suite | 결과 | 실패 범위 |
|---|---|---|
| world_craft_tests | 23/25 통과 | 2차 고정 `(50,7,50)` 대비 현재 `(93,21,93)`, Dio null 메뉴 기대 대비 실제 sebas 메뉴 복구의 오래된 기대2개 |
| misc_items_tests | 5/5 통과 | 없음 |
| equipment_stats_tests | 8/8 통과 | 없음 |
| game_data_tests | 6/8 통과 | 제작 변경 범위 밖의 monster/spawn ID 집합 동일 가정, monster HP source `local_policy` 대비 `l1j` 기대2개 |

실제 소켓은 지정10배 wrapper로 다음3개를 **순차 실행**했다. 원본 클라이언트는 실행하지 않았다. 각 명령 stdout/stderr는 같은 phase3 runs의 `farlin-47000.log`, `arachne-48000.log`, `sebas-48000.log`에 보존했다.

```powershell
$env:SL_TEST_TIME_SCALE='10'
$env:SL_TEST_PORT_BASE='47000'
python -X utf8 -B C:/Users/Chansol/AppData/Local/Temp/claude/D--claude/0483de89-75e7-4b94-84b8-fb31fe00f575/scratchpad/fastbot/run_fast.py hunt_bot_craft --recipes farlin_native_11 --start-near-recipe farlin_native_11
$env:SL_TEST_PORT_BASE='48000'
python -X utf8 -B C:/Users/Chansol/AppData/Local/Temp/claude/D--claude/0483de89-75e7-4b94-84b8-fb31fe00f575/scratchpad/fastbot/run_fast.py hunt_bot_craft --recipes arachne_native_30 --start-near-recipe arachne_native_30
python -X utf8 -B C:/Users/Chansol/AppData/Local/Temp/claude/D--claude/0483de89-75e7-4b94-84b8-fb31fe00f575/scratchpad/fastbot/run_fast.py hunt_bot_craft --recipes dio_native_135
```

| 실행 recipe | 로그인 전 LOCAL 시작 map/x/y | 수신·저장 결과 | 실제 result.json (`runs/` 기준) | 판정 |
|---|---|---|---|---|
| farlin_native_11 | 0/32413/32982, 파린 원위치 인접 셀 | 318×1 | `craft-bot-hthousrs/result.json` | PASS,12체크·21요청·2epochs·cleanup 완료 |
| arachne_native_30 | 4/33139/32261, 아라크네 원위치 인접 셀 | 251×1 | `craft-bot-0i6q5iks/result.json` | PASS,12체크·21요청·2epochs·cleanup 완료 |
| dio_native_135 (세바스) | 4/33438/32796, 기존 기란 시작 | 12405×1 | `craft-bot-hndkq5nl/result.json` | PASS,12체크·46요청·2epochs·cleanup 완료 |

세 실행 모두 정상 로그인→캐릭터 선택→월드 진입→서버 발급 현재 NPC UID·실제 메뉴→native request5→명시 ACK6 f1=0→정확 재료 소비·수신 인벤/저장 일치→정상 Quit·재접속 복원을 확인했다. `gaps`·`server_failures`는 모두 빈 목록이다. 3개 `result.json:selected_source_sha256`의 선정 조합이 같으며 각 시작 저장·fixture·요청 원문도 해당 실행에 보존했다. 주요 선정 해시는 `crafting.json:1dede992bff25f028e10d9cd2ed0e9b104d6163bf6a9cb8ba370390821d4cf2c`, `hunt_bot_craft.py:237602e6cf62c0b68c20800f9e05b6e636ad5458b8a371f699167fe9e502c38a`, `m2/town_npcs.json:5942091db12078451a6b96c5b1caff190fd3a27e124f2d3f3dfedc0c73b66fbd`, `m5/town_npcs.json:99d4ec21b412df16dd6574f4431be10d98c3ea37bdd1f5306bef00ee532e3f64`다. FAST_CLOCK child exit는 모두0이며 PowerShell stderr 표시 문구와 제품 판정을 구분한다.

**미확인:** 원본 craft_output/input 화면·버튼·native 송신/ACK 소비와 빈 거절 ACK parser 수용, 정상 재료 획득·해당 NPC까지의 정상 여행은 시험하지 않았다. 위 PASS는 선정 조합·LOCAL 시작 저장의 대표3식 소켓/소비/저장/복원 범위이며93연결 전체나 원본 화면 동등성의 판정이 아니다.

이번 제품 변경 파일은 `tools/local_original_session/data/crafting.json`, `data/m2/town_npcs.json`, `data/m5/town_npcs.json`, `hunt_bot_craft.py`이며 이 문서와 위 phase3 runs만 추가했다. `start-manual-play.ps1`의 기존 `$pins`에는 이4파일이 없어 갱신 대상 핀은 없다. launcher·실행 스크립트·수동시험 프로필·ACTIVE_TASK·기존시험·코어/adapter는 수정하지 않았다.
