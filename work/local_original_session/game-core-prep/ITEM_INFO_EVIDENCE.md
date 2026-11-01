# 아이템 이름·설명과 4E2F 계약

2026-10-28. 고정 CONTROL SHA256 `9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`의 기존 복원 섹션과 저장 분석을 재사용했다. 게임 실행·메모리 관측·스크린샷·원본 및 사용자 저장 변경은 하지 않았다. 포트 시험은 아래 6장의 별도 로컬 시험사본에서 수행했다. **정적 원문 확인·Python 연결 확인·실제 화면 확인을 구분한다.**

## 1. 4E2F 정체 정정: 아이템 설명 요청이 아닌 방향 알림

`CS_CHANGE_DIRECTION_NOTI`다. 이름 문자열 검색만으로 정한 것이 아니라 실제 sender의 numeric opcode, 같은 message vptr/RTTI, serializer/parser/schema를 결속했다.

| 원문 위치 (RVA) | 직접 확인 |
| --- | --- |
| `92850..92CB3` | actor component의 이전 `+88`을 R14D로 읽고 `928F0`에서 ESI 방향을 먼저 저장한다. `92975`에서 이전 값과 비교하고 바뀐 경우에만 송신한다. |
| `92988..9299A` | stack DTO vptr=`11E32E8`, presence=1, `DTO+18=ESI`. |
| `929CC..929D5` | EDX=`0x4E2F`, R8=그 DTO, `27D620` 송신 호출. |
| vptr `11E32E8` | COL `130A4D8` → TD `1742AD0` → `.?AVCS_CHANGE_DIRECTION_NOTI@LIN@@`. |
| parser `75DC90` | schema `15EE458` → `DEDF80`. |
| schema `15EE458` | max/count1, skip `FFFFFFFE`, f1 offset18/presence128/type-card1091=`int32`. |
| Init `75DDC0` | presence bit0 필수. serializer `75DCA0..75DD4B`는 present f1 scalar 하나를 출력한다. |

따라서 item UID로 파싱하거나 `0964/0965`를 그 요청의 ACK로 보내면 다른 프로토콜을 섞는 것이다. 구현은 정상 현재 선택/소유자·생존 PC와 LOCAL 기존 방향 범위0..7을 확인하고 world entity heading 및 기존 `service._actor_heading`만 갱신한다. 위치·공격·아이템·저장 변경은 없다. malformed/현재 소유자 불일치는 해당 요청만 거절하며 다음 정상 요청은 계속된다.

자기 방향은 sender가 원 actor 상태에 선반영한다. **LOCAL 응답 정책은 자기 echo 생략**이다. 이는 공식 서버의 모든 회전 응답/ACK 정책을 관측한 결론이 아니다.

## 2. 실제 SC 방향 알림: 4E2E

`294A0C EDX=4E2E`/`294A24→292F80`의 등록 table `11AB518`의 `+10=3075C0`은 `307634→31EA10`을 호출한다. ctor `31EA41`은 nested message vptr `11E41F0`을 설치한다. TD `1680FA8`은 `SC_CHANGE_DIRECTION_NOTI`다. 이 타입은 기존 `run406_companion_equipment/appearance/protocol-types.json`에도 있다.

- parser `75DA70` → schema `15EE4B0`; f1 int32 offset18/presence128, f2 int32 offset1C/presence129. Init `75DC00` mask3으로 둘 다 필수.
- serializer `75DA80..75DB2A`는 f1/f2를 각각 출력한다. signed UID의 sign-extension을 유지한다.
- subscriber `4C150..4C38E`는 f1을 UID로 sign-extend하여 `4C239→627B0` actor lookup에 넣고, f2를 `4C2A5`에서 다음 방향 동작 객체에 넘긴다.
- 구현은 기존 `visibility.known`에 그 같은 actor UID가 게시된 다른 observer만 기존 world outbox/announce로 알린다. 현재 WorldView는 다른 PC를 spawn 목록에 추가하지 않으므로 단순히 거리가 가깝다는 이유만으로 unknown UID 알림을 만들지 않는다. 다른 PC 출현 자체를 새 기능으로 구현한 것은 아니다.

## 3. 바닥 4E96 이름

`item_ground.PARAMETERS`의 기존 opaque local14 profile에는 required f9가 빈 bytes다. 원 profile·그 핀·기존 whole-B custody는 보존하고, `world_visibility.ground_frame`이 world drop의 f9 한 항목만 client catalog 이름으로 교체한다. required 나머지 필드/UID/좌표/수량/Item 분기/그래픽은 기존 producer를 유지한다.

원 schema `work/online_world_packet_source/world-notify-contract.json`의 `4E96.f9`는 bytes/type-card815/raw offset20이다. `4B690`의 보유 proto 복사 뒤 `4B80B..4B83E`가 이 문자열을 `CD0B0` 인수로 넘기고, `CD464..CD4EC`는 Info+20/+40 문자열을 구성한다. 기존 spawn Item 분기 `48760→C15E0→40ED0`를 그대로 쓴다. f9를 catalog template이나 desc token 정수로 바꾸지 않는다.

이름 출처는 `tools/local_original_session/data/catalog/items_all.json`의 `name_ko`와 원 `name_token`, 그 `client_original.source_ref`가 가리키는 `work/source_game_data/native-dump-v1.jsonl`, `work/source_game_data/raw/desc.csv`다. 예: template1 `$14`→아탐,2 `$16`→일본도,3 `$5`→장검,4 `$1`→도끼. 이번 producer는 **이미 원 desc.csv에서 해석된 UTF-8 한국어**를 보낸다. 클라이언트가 모든 f9/f18 `$` 토큰을 똑같이 해석한다고 새로 단정하지 않는다. 이름 없는 행에 임의 `아이템#ID`를 만들지 않는다.

## 4. 인벤0964 이름과 정상0977 설명 갱신

기성 근거: `run30_inventory_first_wire/findings.md`, `run41_inventory_update/worker/findings.md`, `run262_gear_instance_consumers/source/contract.md`, `run301_identify22_iteminfo_consumer/contract.md`.

- 초기0964 ctor `509390`의 `50958A..5095A8`은 ItemInfo f18(+58)을 Entity+58 문자열로 복사한다. `5095B0→50C3F0`는 이 문자열의 `\((\d+)\)` 처리다. 이름·개수 문자열 처리와 설명 전체 초기화를 혼동하지 않는다.
- `world_feature_kit._inventory_kit_frame`은 startup에 공급된 이름으로 **빈 f18만** 채운다. 기존 주문서 등급표시/강화명은 보존한다. 이 optional feature 등록이 빠져도 원 builder는 동작한다.
- 기존 저장의 canonical0964는 수정하지 않는다. initial0964가 drain되어 `inventory_frame`이 설치된 뒤, 새 feature의 enter/after_request hook이 **정상0977 f1현재UID/f2이름/f4현재수량**을 전송한다. canonical f18이 있으면 그 강화명·등급명 등을 그대로 쓰며, 없으면 원client 이름을 쓴다. 첫 enter 때 아직 수동 AddInventory 전이면 이후 정상 요청에서 처리한다. 완료 기록은 send/drain 뒤에만 남긴다. 재진입 때 표시 기록을 비운다.
- 0965 callback `4F7782..4F77A7`은 present f18을 Entity+58에 복사한다. absent f18인 수량0965는 이 복사를 건너뛴다. Python 시험은 부분 갱신에서 이름 유지의 **프로토콜 존재성 의미**만 확인했으며 native 렌더링 성공으로 표시하지 않는다.
- **f18 이름만으로 상세 설명 복원을 완료했다고 판단하지 않는다.** f19 repeated ItemDescription의 원 ctor `509695→50D090`은 별도 계약이다. `50D090`은 child f1 DescTokenID→tag를 key로 Entity+A8에 f2 value를 저장하고 Entity+128에도 description을 복사한다. `509CAC→50D1A0→50A4E0` 후속 소비가 있다. 0965 직접 callback에는 이 f19 처리/50C3F0 호출이 없어 최종 구현은0965 이름복사에서 멈추지 않고 아래0977로 연결했다.

### 0977 원문·필드·실제 소비

읽기 전담 worker의 [정적 원문·최종 근거](../runs/iteminfo-source-20261028/findings.md)와 그 폴더의 `change-desc-*.json`을 수용했다. `294585` callable table `11AA918` / `29458C EDX=0977` → `2945A4→292F80` 등록, table+10=`30A3C0` → `320230` → message vptr `11F27E0`(`SC_CHANGE_ITEM_DESC_NOTI`) → event `17FA240`. Inventory 등록 `4FB7F0 R8=4F64D0`은 같은 event에 연결된다.

schema `1604CF8`, parser `7B4100`, Init `7B4620`, serializer `7B4110`의 계약:

| field | type / 필요성 | 구현 공급 |
| --- | --- | --- |
| 1 | required uint64, DTO+50, presence bit1 | 현재canonical item UID |
| 2 | optional string, DTO+48, presence bit0 | 기존f18 또는 원client name. **absent여도consumer가empty로복사하므로항상제공** |
| 3 | repeated ItemDescription, DTO+18 | 아래 기존 로컬 서버 정책값을 검증된 native tag/value로 공급 |
| 4 | required uint64, DTO+58, presence bit2 | 현재canonical 수량 |
| 5 | repeated ItemDescription, DTO+30 | 공급된special description계보없음,현재omit |

Init는 mask6과 f3/f5 모든 child의 `6CF3C0`를 확인한다. child ItemDescription은 required f1 int32 DescTokenID와 required f2 string value다. callback `4F64D0`는 f1로 현재 row를 찾은 뒤 `50BA80(entity, proto)`, `50A6B0(entity, f4)`를 호출한다. `50BA80`은 f2를 Entity+58에 복사하고 `50C3F0`를 호출하며, f3를 `50D090`으로 처리하고 f5는 `50D820`을 거쳐 마지막 `50D1A0`로 전달한다. 이 normal wire 경로를 새 feature가 재사용하며 native 함수를 직접 호출하지 않는다.

**한계:** f3 empty는 `50D090`을 호출하지 않고 catalog f29를 자동 합성하지도 않는다. `50D820`의 f5 empty 경로는 기존 special 선택/일부 description key를 정리하고 Entity+148=-1로 되돌린다. 따라서 모든 기존 특수 설명 보존을 보장한다고 주장하지 않는다. 현재 로컬 canonical ItemInfo는 f19/f5 설명 계보를 저장하지 않는다. native 상세 설명 화면은 별도 확인 대상이다.

`DescTokenID → DescToken.f2 tag → item_extra_desc._tag → _desc → desc.csv`가 설명 지역화 경로다. DescToken1321은 enchantDamage이며 desc.csv1321과 같은 의미가 아니다. CommonItemInfo의 raw price/weight 후보·L1J 후보 능력치를 설명 value로 합성하지 않는다. 원 dump의 display_tokens에는 value의 길이/해시만 있고 plaintext가 없으며, 물약 등 일부 행은 display_tokens가 없다.

0977는 수량이 같아도 이름을 교체하는 반면 `50A6E1..50A6E5`는 기존 수량과 같으면 수량 setter를 건너뛴다. 따라서 이름을 base만 공급해 stack 수량 suffix가 사라지지 않도록 wire f2에는 Q>1일 때 `이름 (Q)`를 준다. `50A780`의 RIP literal `11C6E58`은 정확히 `" ("`, `50A7C0`의 `11AE9C4`는 `")"`이고 `50A8AA`가 합친 suffix를 Entity+58에 붙인다. canonical 저장/base f18은 바꾸지 않는다. 최초0964 이후 정상0977 투영의 native 표시 결과는 미시험이다.

### 기존 로컬 서버 수치의 원본 설명 형식 투영

사용자는 긴급 표시 수정 범위를 승인했고, root는 기존 M1Data에서 실제 서버가 사용하는 값을 원 native formatter로 보여 주되 새 밸런스/공식 값 추정을 만들지 않는 대안을 명시했다. `backend_descriptions`는 이미 로드된 `world.data.items`를 startup에 보관하고 그 `ItemDef`와 기존 `world_enchant_inventory.enchant_level`만 읽는다. 아이템 원본 함수 직접 실행·요청 중 파일 판독·새 pin/guard가 없다. initialize 뒤 optional feature가 catalog를 추가하는 경우 runtime_started에서 최종 definition 목록을 보관한다.

| DescToken ID / tag | 공급값 | 값의 범위/출처 |
| --- | --- | --- |
| 33 sdam, 34 ldam, 1321 enchantDamage | `dmg_small`, `dmg_large`, 기존 LOCAL 강화레벨 | 기존 무기 backend의 base small/large와 별도 강화값. 강화값을 base에 미리 합산하지 않음 |
| 8 ac, 1417 enchantAc | `ac`, `-강화레벨` | 기존 `world_stats`의 armor AC 기여 = base AC - 강화레벨. native에 AC 반전/합산을 맡긴다고 추정하지 않음 |
| 1356 meleeHit / 1358 rangeHit | 기존 nonzero `hit` | bow는 기존 ranged 분류, 나머지는 melee. Decimal string만 공급 |
| 1366 meleeDmg / 1368 rangeDmg | 기존 nonzero `dmg_bonus` | 기존 backend의 추가 피해. 별도 '+' 문자를 붙이지 않음 |
| 48 weight | 기존 `weight // 1000` | 기존 M1/world_weight raw 단위의 1개 아이템 표시값. 합계/수량별 burden 정책을 변경하지 않음 |

원 데이터 태그는 `native-dump-v1.jsonl`의 token 행, 레이블/format은 `work/all_table_semantics/inputs/data/item_extra_desc.jsonc`와 desc.csv를 재사용한다. 예: sdam/ldam/enchantDamage의 `_desc=1119` 타격치, ac/enchantAc는1082 AC, weight1142 무게다. 이 ID는 description-token ID와 다른 desc.csv 지역화 ID다.

원문 `5195D0`는 `{sdam,ldam,enchantDamage}` 3종과 `{ac,enchantAc}` 2종을 묶는다. `520E20..520F36`은 그룹 태그가 모두 존재해야 채택하므로 강화0도 present로 보낸다. `524130`는 sdam/ldam 문자열과 `DF660`으로 읽은 signed enchantDamage를 따로 표시한다. `523BE0`도 ac 문자열과 signed enchantAc를 따로 표시한다. **두 callback은 base와 강화를 합산하지 않으며 AC 부호를 반전하지 않는다.** literal `11C7628='{}{} {}{}{}/{}{}{} \n'`, `11C7600='{}{} {}{}{} \n'`. `+0`이 표시될 수도 있으며, 이를 숨기려 group 필수 태그를 생략하지 않는다. 원문은 같은 source 폴더의 `damage-ac-merge.json`, `desc-format-literals.json`, `special-group-admission{,-continuation,-tail}.json`에 있다.

외부/임의 이름에서 LOCAL 강화레벨을 읽을 수 없으면0으로 추정하지 않고 해당 damage/AC 그룹을 생략한다. 정의/이름을 찾지 못한 template에도 설명을 만들지 않는다. 물약의 heal_hp/범위는 기존 서버에 있지만 **hpMod140은 HP regeneration 태그이므로 물약 회복량에 전용하지 않았다.** 물약 사용 효과·재질·직업·안전 강화·축복/저주·special f5 등 미확인 producer는 표시 누락 범위로 남긴다. 이 누락이 모든 아이템 상세 설명 완성을 뜻하지 않지만, 검증된 이름과 현재 무기/방어구/무게 설명의 실제 wire 연결은 구현했다.

## 5. 출처 비율과 실제 검증 범위

client catalog1266행 중 한국어 이름이 있는1241행(98.03%)을 그대로 읽고, 이름 없는25행은 비운다. **이 비율은 이름 데이터 범위일 뿐 원본 클라이언트 복원율·원본 코드 비율·아이템 설명 완성률이 아니다.** 새 Python 기능은 원본 코드를 소스화한 것이 아니라 확인한 wire/소비 계약을 연결한 로컬 서버 구현이다. 보존 profile의 미확인 값과 sprite/item mapping의 기존 LOCAL 경계도 유지한다.

기본 `load_m1()`의279 template(무기87/방어구132/물약26/화폐1/탄약3/주문서30), 각1개·LOCAL 강화0을 기준으로 생성하는 **845개 숫자 description cell**의 원 `ItemDef.sources`를 집계하면 client279(33.02%, 무게), official345(40.83%, 기존 무기/AC/명중 등), local_policy221(26.15%, 기존 강화상태/일부 기존 정책값), L1J0이다. L1J가 기존 backend에 없다는 뜻이 아니라 이 기준에서 nonzero 전송 대상으로 선택된 cell의 비율이다. 추가 feature의 startup catalog/실제 사용자 강화값은 이 집계 밖이다. **wire/schema·표시 태그·한국어 레이블은 client 원문을 재사용하며, 수치는 기존 서버 정책의 출처를 따른다. 원서버의 상세 설명 값과 같다는 주장이 아니다.**

개발 단위 검증: `world_iteminfo_tests` 초기18개와 `world_ground_items_tests`, `world_visibility_regression_tests`, `world_handlers_tests` 33개의 결합51개가 통과했다. 후속 회귀의 optional transport-row 보완 뒤 `world_iteminfo_tests`는20개다. 시험은279개 기본 template의 실제 descriptor child/프레임 크기, 별도 강화값·AC 부호·custom 이름과 wire 수량 suffix/원 canonical 보존, 물약 태그 오용 없음, 잘못된/과거 소유자 회전 거절 뒤 정상 요청, 늦은 inventory drain 후 표시/재진입 및 outbox observer 범위를 포함한다. 구현 worker는 게임·포트·native 입력·화면·tooltip·재접속·실저장을 시험하지 않았으며 별도 시험 worker의 포트 결과는6장에 둔다. 최초 source 선택의 full 함수 해시는 기존 복원 reader로 확인했으며 raw pointer나 현재 실행 증거로 사용하지 않았다.

| 선택 함수 | full 범위 | SHA256 |
| --- | --- | --- |
| direction sender | 92850..92CB3 | 7d79496c5e402076a6d59bb516bc38d6ac3831cd022ca2d4e59b5ecd69d3e80d |
| CS serializer | 75DCA0..75DD4B | f06bf0e14c762ea83665a3c0dbfbe7a28aa5dcbadf6585ef79fba947d7adabbf |
| SC serializer | 75DA80..75DB2A | eaff93c749fa09807dde21291f9d3b4863e7b5ac31819f291e2c4c2a72b5f6ad |
| SC subscriber | 4C150..4C38E | 14a2d0cfd39bb6313bd47656ea4f819c3e42365b8a3fa6d5f6c65de25c4bae18 |
| 0965 callback | 4F7670..4F78DF | 960008f10166c46a286a9d09c73e2a907b49bdbc03f639a7b3445ba39f34b3a5 |

분석 방법: `run395_selfinfo_stats_fields/extract.py`의 기존 restored-record/PData/Capstone reader를 import해서 선택 함수·schema·RTTI·명시 opcode 인접 원행만 읽었다. 설명 소비의 새 원문은 읽기 전담 worker가 현재 경로에 맞춘 file-only helper로 보존했다. REA skill의 관측/추론/미확인 구분을 적용했다. 신규 live REA Evidence ID나 현재 게임 관측은 없다.

## 6. 브로커 생존과 실제 소켓 검증

원 실패 `runs/manual-test-knight-20261028-004005-62e10023/result.json`은 보존했다. `broker.py`는 월드 모드의 `GAME_OPCODE_UNBOUND`를 기존 수신 rate 예산에 계상한 뒤, bootstrap 수신2/송신3 완료 상태에서 기존 요청 거절 기록으로 넘겨 해당 프레임만 폐기한다. 소유권·크기·drain·bootstrap 순서 검사는 유지하며 비월드 거절 동작도 유지한다. `broker_request_refusal_tests`는 단계 부적합 요청, 정상 다음 요청, 비월드 실패와 기존 검사 경계를 확인한다.

`SL_TEST_PORT_BASE=26000`의 실제 소켓 시험 `world_iteminfo_loopback_tests`(아래 통합 회귀 명령에 포함)는 기존 Scenario의 새 test_knight/EquipmentStore 시험사본에서 FIRST → 로그인 → 선택을 재사용했다. 서버가 보낸 인벤 UID와 결속된 아이템35개의 0977 이름·현재수량·description child를 수신한 뒤 같은 peer에서 unknown7FFF → Alive → 4E2F(direction6) → Alive를 수행했다. 서버 현재 PC heading6, failure_code=null, 의도한 `GAME_OPCODE_UNBOUND@0x7fff` 기록만 남았으며 정상 Quit/cleanup_complete=true였다. 함수 직접 호출이나 최종 상태 강제는 사용하지 않았다.

실제 시험사본과 결과: `work/local_original_session/runs/iteminfo-loopback-ecwy1ymt/result.json`. 이는 로컬 decoder/router·응답·동일 연결 생존의 확인이며 원본 화면·tooltip 렌더링 성공은 아니다. 수동 실행기의 기존 broker 핀만 갱신했고 UTF-8 BOM을 유지했다. 원본 확인 항목은 바닥 이름, 인벤 hover/click 설명과 수량 suffix, 회전 뒤 계속 플레이, 재진입 표시다. 물약 회복량·기타 특수설명·f29 선택축·실제 화면은 위 한계대로 미확인이다.

### 회귀에서 확인한 실패와 범위

- 첫 확장 회귀는251 tests / errors11이었다. `broker_tests.WorldProfileTests`의 실제 transport row 없는 직접 호출에서 새 표시 훅이 `policy_row`를 요구한1건은 optional 표시만 생략하도록 보완했다. 실제 통신 row는 기존 owner 검사를 그대로 통과해야 한다. 기존 실패와 회귀를 보존했다.
- 다른 원인은 기존 MapExp2의 `world_feature_dungeons.DungeonItemEffects`에 `detach`가 없는데 `world_item_effects._world_consumable_stopped`가 이를 호출하는 종료 오류다. 이1건 뒤9건은 같은 시험 프로세스의 포트 충돌이었다. 이 작업의 허용 제품 파일 밖이므로 수정하지 않았고, MapExp2 두 시험은 최종 제한 회귀에서 제외했다. MapExp1/3 및 포트 연쇄로 실행되지 못한 RegisteredMovement3개는 별도 재시험했다. 전체 확장 회귀가 통과했다고 주장하지 않는다.
- 첫 `--scenario all`은 death/town 성공, reconnect/items는 `ATTACK_STALLED`였다. `hunt_bot.apply`가 빈 f9 이름으로 ground를 구분해, 이름이 채워진 ground(f39=0)를 실제 monster0(오크)로 분류하는 결함을 확인했다. 봇만 기존 LOCAL `ground.f7=양수 수량 / monster.f7=0` 계약으로 구분하도록 수정했다. 서버 공격·상태·guard는 바꾸지 않았다. 이름 있는 ground/실제 오크0/옛 빈 이름/자기·PC 분기의4개 순수 회귀를 추가했다. 같은 첫 실행의 target UID timeline은 보존되지 않아 직접 인과 관측과 정적 결함 확인을 구분한다.

원실패 로그는 `runs/broker-iteminfo-20261028-010816-unittest.log`, `runs/broker-iteminfo-20261028-010816-scenarios.log`, 시험사본은 `runs/hunt-scenarios-dzj0sz3e`에 보존했다.

### 최종 제한 회귀

`SL_TEST_PORT_BASE=26000`에서 다음 명령이 **43 tests / 26.117초 / OK**였다. 기존 성공 중 영향 없는 검증은 재사용했다.

```powershell
$env:SL_TEST_PORT_BASE='26000'
python -X utf8 -B -m unittest tools.local_original_session.world_iteminfo_tests tools.local_original_session.hunt_bot_iteminfo_tests tools.local_original_session.broker_request_refusal_tests tools.local_original_session.broker_tests.WorldProfileTests tools.local_original_session.world_iteminfo_loopback_tests tools.local_original_session.world_integration_tests.RegisteredMovementLoopbackTests tools.local_original_session.world_integration_tests.MapExperimentLoopbackTests.test_same_map_baseline tools.local_original_session.world_integration_tests.MapExperimentLoopbackTests.test_same_map_omit_only_map_frame -q
```

최종 로그: `runs/broker-iteminfo-20261028-010816-final-unittest.log`. 최종 실제 소켓 결과는 `runs/iteminfo-loopback-n7gmhvdz/result.json`이며35개 설명 수신·heading6·의도한 unknown 거절 기록·failure_code=null·정상 Quit/cleanup_complete=true를 다시 확인했다.

### 최종 전체 시나리오

같은 최종 소스를 FIRST/close까지 고정하고 다음 명령을 기본 reconnect 사냥3분 그대로 실행했다.

```powershell
$env:SL_TEST_PORT_BASE='26000'
python -X utf8 -B -m tools.local_original_session.hunt_bot_scenarios --scenario all
```

**SUCCESS / exit0**. death4·reconnect6·town2·items4, 총16항목이 모두 성공했다.5개 broker epoch 모두 failure_code=null, handler_errors=[], cleanup_complete=true였다. reconnect 사냥은13처치·13줍기였으며 이름 있는 ground를 다시 공격하는 stall은 재발하지 않았다. 시험 종료 후26000/28030 listener0을 확인했다. 이는 이 로컬 시험사본의 패킷·저장/재접속·정리 결과이며 원본 화면 확인을 대체하지 않는다.

최종 로그: `work/local_original_session/runs/broker-iteminfo-20261028-010816-final-scenarios.log`(PowerShell UTF-16 BOM). 시험 저장 사본: `work/local_original_session/runs/hunt-scenarios-4wxcxzxn`. 위 최초 실패·별도 MapExp2 종료 오류는 이 성공으로 덮지 않는다. 금지된 사용자 profiles/ACTIVE_TASK·원본 클라이언트는 수정/실행하지 않았으며 커밋하지 않았다.

변경 파일: `tools/local_original_session/{broker.py,world_visibility.py,world_feature_kit.py,world_handlers.py,world_feature_iteminfo.py,hunt_bot.py,broker_request_refusal_tests.py,world_iteminfo_tests.py,hunt_bot_iteminfo_tests.py,world_iteminfo_loopback_tests.py}`, `work/local_original_session/manual-play/start-manual-play.ps1`의 기존 broker 핀, 이 문서. 정적 분석 원문은 `work/local_original_session/runs/iteminfo-source-20261028/`에 보존했다.
