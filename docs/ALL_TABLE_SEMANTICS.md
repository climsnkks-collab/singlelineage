# 전체 테이블 필드·소비 코드 분석

2026-10-09 현재 클라이언트 26.09.29.2001의 **바이너리 19종, 명명 텍스트 표 31개, SPR 1개 — 총 51개 자료**를 같은 기준으로 분석했다. 저장 구조·중첩 타입·실제 소비·ID 사전·데이터 대조를 구분했다. 기존 NPC 분석을 재사용하고 다른 표를 새로 추적했다. 모든 게임 속성명과 서버 공식을 확정했다는 뜻은 아니다.

[전체 51자료 색인](../work/all_table_semantics/index.json) · [입력과 버전 근거](../work/all_table_semantics/inventory.json) · [독립 검증](../work/all_table_semantics/root-review.json)

현재 catalog 후보 52개와 별도 SPR을 확인했다. credit.txt/credit_en.txt 두 문서는 게임 테이블에서 제외했다. 포함 51개는 모두 실제 평문 SHA·크기가 현재 catalog와 일치한다. 새 복호화·계정/키 접근·게임 실행·RAM·UAC·제품/서버 룰 변경은 없다.

## 주요 결과

- **아이템:** 최상위 55필드와 중첩 18필드. 표시 이름, 아이템 참조, 수량×f15와 f26의 128 보정, 설명 토큰→태그→값 복사를 확인했다. 무게라는 이름·가격·장착/class·raw 재질 필드 전달은 아직 후보/미확정이다. 효과 설명 259개(일반244+방어구 세트15), 강화 설명 5,760개, 표시 ID·값 5,968쌍을 검증했다.
- **마법:** 최상위 실제 schema 13필드와 자식 6필드. f9는 현재 생성 schema에 없다. f3 버프 아이콘, f7 툴팁, f5 버프 통지와의 boolean 결합, f13 UI trait 포함 검사, f14 최근 사용·버프 그룹 비교를 확인했다. f8 효과 224개는 반복 문자열이며 실제 피해 계산 소비는 미확정이다.
- **제작·퀘스트:** 실제 파일→로더→RTTI를 연결했다. 제작 입력/출력 아이템 참조와 QuestT prerequisite/objective/reward/optional-reward/teleport/exchange 자식 타입을 찾았다. 재료 차감·보상 지급·조건 enum·서버 판정은 개별 unknown을 보존했다.
- **확률표:** 강화 501행·보물 1,098행에서 double=int64÷10,000,000 대응을 전량 확인했다. [Root 문자열 대조](../work/all_table_semantics/root-probability-labels.json)에서 강화 f4=0성공/1파괴/2유지, 보물 f10=0축복/1보통/2저주, f13=2독립/1일반이 각각 같은 행의 표시 문구와 일치했다. 원래 enum 이름과 실제 서버 추첨 방식은 미확정이다. 출석 보상과 보물·제작 아이템 참조도 현재 item ID 사전에 대응한다.
- **소환·이동:** 추가 [소비 추적](../work/all_table_semantics/travel_review/README.md)에서 소환 f2의 “레벨 {} 이상” 표시, f3→NPC 조회→이름과 이동책의 맵·좌표·설명값 UI 전달을 확인했다. [독립 조인](../work/all_table_semantics/root-travel-joins.json)은 소환 NPC14개와 이동책704항목(제목135/좌표목적지569), 설명704/보조설명73을 재검사했다. 플레이어 레벨 허용 판정·실제 서버 이동은 별도 미확정이다.
- **명명 설정표:** 전체 603개 경로의 타입·출현·표본·의미 근거를 기록했다. 211경로는 선택된 파일 reader 안의 키 읽기를 확인했다. 키 읽기 확인만으로 그 값의 게임 효과·단위까지 확정하지 않는다.
- **ID 공간:** DescToken ID와 desc.csv ID는 다르다. 옵션은 DescToken.f2 태그→item_extra_desc._tag→_desc→desc.csv로 연결한다. string.csv/spelldesc/dialogue의 키도 구분했다.
- **SPR:** 2,976정의/10,664액션/77,097 strict 토큰. C/FPS·기본24·양수 **N** 지정 ms·속도 보정은 기존 원본 코드를 다시 검증했다. 원문 예외를 수정하지 않았고 서버 공격 간격이나 피해식으로 확대하지 않았다.

## 바이너리 19종

필드 경로 수는 부모와 자식을 포함한 표별 분석 경로다. 공유 타입은 여러 표에 다시 나타날 수 있다. 공통 GameDataFile/GameData envelope 8필드는 payload와 별도로 기록한다. 이 수치를 고유 속성 수나 의미가 모두 확정된 수로 해석하지 않는다.

| 파일 | 레코드 | 실제 값 타입 | 필드 경로 | 근거 |
|---|---:|---|---:|---|
| battlepass.bin | 1 | BattlePassT | 61 | [전체 필드](../work/all_table_semantics/remaining/battlepass/report.json) |
| copymaplist.bin | 26 | ChannelMapListT | 2 | [전체 필드](../work/all_table_semantics/remaining/copymaplist/report.json) |
| craft.bin | 154 | SC_CRAFT_LIST_ALL_ACK_Craft | 272 | [전체 필드](../work/all_table_semantics/remaining/craft/report.json) |
| desctoken.bin | 1419 | ParserTokenTable | 2 | [전체 필드](../work/all_table_semantics/spell_token/report.json) |
| entermaps.bin | 29 | EnterMapTAG | 208 | [전체 필드](../work/all_table_semantics/remaining/entermaps/report.json) |
| indun.bin | 1 | IndunInfoForClient | 6 | [전체 필드](../work/all_table_semantics/remaining/indun/report.json) |
| ingame_prob_attendance.bin | 1 | BmProbAttendanceInfoListT | 12 | [전체 필드](../work/all_table_semantics/remaining/ingame_prob_attendance/report.json) |
| ingame_prob_attendance2.bin | 1 | BmProbAttendanceInfoListT | 12 | [전체 필드](../work/all_table_semantics/remaining/ingame_prob_attendance2/report.json) |
| ingame_prob_enchant.bin | 1 | BmProbEnchantTableListT | 13 | [전체 필드](../work/all_table_semantics/remaining/ingame_prob_enchant/report.json) |
| ingame_prob_treasure.bin | 1 | BmProbTreasureInfoListT | 23 | [전체 필드](../work/all_table_semantics/remaining/ingame_prob_treasure/report.json) |
| item.bin | 1266 | CommonItemInfo | 73 | [전체 필드](../work/all_table_semantics/item/report.json) |
| npc.bin | 951 | CommonNPCInfo | 32 | [전체 필드](../work/npc_field_semantics/layout/report.json) |
| npccraftlist.bin | 1 | NpcCraftList | 6 | [전체 필드](../work/all_table_semantics/remaining/npccraftlist/report.json) |
| quest.bin | 75 | QuestT | 146 | [전체 필드](../work/all_table_semantics/remaining/quest/report.json) |
| shipinfo.bin | 4 | ShipInfo_ShipInfoListT_ShipT | 31 | [전체 필드](../work/all_table_semantics/remaining/shipinfo/report.json) |
| skin.bin | 1 | SkinInfoForClient | 10 | [전체 필드](../work/all_table_semantics/remaining/skin/report.json) |
| spell.bin | 433 | CommonSpellInfo | 19 | [전체 필드](../work/all_table_semantics/spell_token/report.json) |
| summonmonster.bin | 14 | SummonSlotT | 4 | [전체 필드](../work/all_table_semantics/remaining/summonmonster/report.json) |
| teleportbooks.bin | 11 | TeleportBookGroupT | 9 | [전체 필드](../work/all_table_semantics/remaining/teleportbooks/report.json) |

## 명명 텍스트 표와 SPR 32개

JSONC 수량은 문서 루트의 배열 길이 또는 문서 1개다. 실제 중첩 행 수는 각 field의 presence와 parent_population을 본다. XML 수량은 요소 수이며 변신 종류 수와 같지 않다.

| 파일 | 행/문서/요소/정의 | 필드 경로 |
|---|---:|---:|
| data/activate_content_shortcut.jsonc | 1 | 1 |
| data/ats_basic.jsonc | 1 | 53 |
| data/behavior_list.jsonc | 1 | 15 |
| data/campaign_settings.jsonc | 1 | 8 |
| data/class_info/char_attr_type.jsonc | 16 | 10 |
| data/class_info/class_explain.jsonc | 4 | 4 |
| data/class_info/class_status.jsonc | 4 | 17 |
| data/damaged_effect.jsonc | 1 | 16 |
| data/desc.csv | 17949 | 6 |
| data/dialogue.csv | 3617 | 7 |
| data/item_cooldown.jsonc | 1 | 6 |
| data/item_extra_desc.jsonc | 71 | 13 |
| data/item_usage_display.jsonc | 1 | 5 |
| data/map_background.jsonc | 3 | 7 |
| data/map_view_data.jsonc | 1 | 56 |
| data/npc_hud_rules.jsonc | 1 | 7 |
| data/out_game_settings.jsonc | 1 | 17 |
| data/polymorph_list.xml | 132 | 13 |
| data/purple_on_push.jsonc | 1 | 3 |
| data/region.jsonc | 226 | 18 |
| data/server_settings.jsonc | 1 | 8 |
| data/ship_data.jsonc | 1 | 28 |
| data/sound_env_config.jsonc | 1 | 33 |
| data/sound_item_config.jsonc | 1 | 17 |
| data/sound_mixing_rules.jsonc | 1 | 38 |
| data/sound_music_config.jsonc | 1 | 22 |
| data/spell_list.jsonc | 1 | 101 |
| data/spelldesc.csv | 230 | 6 |
| data/string.csv | 12748 | 7 |
| data/string_type.jsonc | 1 | 17 |
| map/20001/npclists.csv | 0 | 16 |
| data/list.spr | 2976 | 28 |

[32개 파일 소비 관계](../work/all_table_semantics/text/file-consumers.json) · [603개 전체 경로](../work/all_table_semantics/text/fields.json) · [선택한 코드 근거](../work/all_table_semantics/text/selected-source-proofs.json)

`npclists.csv`는 **15개 명명 열+끝 빈 열=16열, 데이터 0행**이다. 배치 좌표를 확보한 스폰표로 쓰지 않는다. `activate_content_shortcut.jsonc`는 현재 null이다.

## 검증과 남은 해석

Root가 독립 wire parser로 19bin/4,390레코드/최상위 48,568필드를 읽고, item의 모든 중첩 경로와 마법/나머지15표 field path별 출현·타입을 대조했다. JSONC/CSV/XML 575경로는 별도 재귀·열 parser로, SPR 28경로는 기존 코드 근거·원문 헤더·문법 예외와 함께 검토했다. 최종 검증은 **249,827검사 PASS**이며 선택된 원본 함수·명령·metadata·RTTI와 입력 핀을 다시 읽었다. 발견용의 다른 literal/함수는 확정 소비 범위와 분리했다.

각 필드에는 object offset/자료형/출현/실제 기본값 또는 UNKNOWN/명명 수준/코드 근거/한계를 남겼다. 미기록과 명시적 0을 구분한다. 동일 오프셋의 스택 저장·string 내부 capacity 접근을 proto 필드 증거로 쓰지 않는다. GetItem/GetSpell/GetNpc 등의 RAX는 shared_ptr 결과 저장소 주소이며 실제 객체 첫 qword와 구분했다.

아직 미확정인 것은 HP/MP/AC/MR/EXP/레벨의 전체 기본값·피해/명중/마법 계산식, raw 아이템 가격·장착·class 의미 일부, 확률표의 서버 적용, 퀘스트 조건·보상 처리, 미기록 필드와 inlined/virtual 소비 일부다. Entermaps는 정확한 loader/타입을 확인했지만 비생성 실제 field consumer는 추가 추적에서도 닫지 못한 부분을 보존한다.

[아이템 상세](../work/all_table_semantics/item/README.md) · [마법/토큰 상세](../work/all_table_semantics/spell_token/README.md) · [나머지15표 상세](../work/all_table_semantics/remaining/README.md) · [명명표 상세](../work/all_table_semantics/text/README.md) · [NPC 기존 상세](NPC_FIELD_SEMANTICS.md)
