# M3 플레이어 마법 학습·시전 근거

2026-10-27. **시전 C2S는 `4EE6`, 학습/가용 목록 S2C는 `4E60`, 마법서 사용은 일반 item-use `0960`이다.** 기존 REA 원문을 재사용해 정적 wire·소비 계약을 확인했다. 1단계 정적 분석에서는 게임·서버·포트를 실행하지 않았다. 이후 구현의 시험 전용 로컬 패킷 결과는 마지막 절에 별도로 기록한다. 원본 클라이언트 기동·화면 캡처·원본/사용자 저장 변경·commit은 하지 않았다. 정적 계약과 패킷 시험을 원본 화면·입력·30분 플레이 PASS로 확대하지 않는다.

현재 [player_spells.json](../../../tools/local_original_session/data/m3/player_spells.json)은 마법 1~5단계 **39행, LOCAL 지원 후보38종·미지원1종(테이밍 몬스터)**이다. 4차는 기존 미지원12종 중11종에 상태·확률·유틸리티 정책을 연결하며 실제 검증 결과와 지원 제한은 별도로 판정한다. 고정 클라이언트의 3단계 빈 슬롯 key23은 만들지 않았다. 아래 1·2차16행과 3차27종의 설명·거절·시험 결과는 당시 Source의 보존 기록이다. 기존 [companion/mage_spells.json](../../../tools/local_original_session/data/companion/mage_spells.json)·계산식과 공식 수집본을 재사용하고, 명시한 주문명·단계로 L1J 행을 연결했다. 전역 `L1J id-1` 변환을 규칙으로 만들지 않았다.

## 3차 당시 카탈로그와 지원 범위 — 보존 기록

현재 자료 우선순위는 **고정 클라이언트26.09.29.2001 → 보존 공식 사전 → 이름을 연결한 L1J 참고**다. [공식 주문 수집본](../../../tools/local_original_session/data/official/spells.json)의 각 `official/source/official_list`와 고정 [UI](../../all_table_semantics/spell_token/spell-ui-joins.json)를 비교했다. 신규23권 전부 공식 textbook id/name과 [item 수집본](../../../tools/local_original_session/data/official/items.json)의 exact id/name이 일치하며, 고정 [native dump](../../source_game_data/native-dump-v1.jsonl)의 item.f41은 정확한 spell key다. f10 raw무게는 모두 **7000**, 공식 표시무게는7이다. 책의 key는 inventory UID·L1J id가 아니다.

2026-10-27에 신규23개 [공식 API 예시16](https://api-goats.plaync.com/linclassic/v2.0/game/spell/16?locale=ko-KR)의 실제 detail URL 전부를 웹 도구로 다시 열었지만 모두 접근 불가였다. 최신 재수집 성공으로 표시하지 않는다. 각 행의 `source_snapshot.official_source`에 기존 URL·수집시각·raw_path·raw_sha256를 그대로 보존했다. 공식은26.10.27 KST 수집본이고 고정 클라이언트는26.09.29.2001이므로 버전이 다르다. 아래 MP/HP·촉매·레벨·기간·대상 반경·AC/DEX는 공식 원문과 고정 UI가 일치한 수치다. L1J 차이값은 JSON에 비교용으로만 남겼다.

표의 지원은 **구현 후보 허용목록**이며 실제 실행 PASS가 아니다. 법사레벨은 학습 최저레벨, 비용은 **MP/HP/마력의 돌166 수량**이다. 0은 공식 목록의 명시0과 고정 UI를 확인한 값이다. 마나 드레인의 MP0도 상세 키 생략을 임의로0 처리한 값이 아니라 공식 목록MP0·고정 UI MP/HP(0/50)를 확인했다. 비용 있는 미지원 주문은 효과를 흉내 내면서 HP·촉매를 생략하지 않는다.

| 단계·key·주문 | 책 | 법사레벨 | MP/HP/돌 | 공식 효과·기간 | 현재 소비와 수치 출처 |
|---|---:|---:|---|---|---|
| 3·16 라이트닝 | 189 | 12 | 13/0/0 | 대상6칸·주변3칸 모든 적 | `area_damage`, 반경3 공식. LOCAL NPC 범위공격, L1J V0/D10/N4·바람8. |
| 3·17 턴 언데드 | 190 | 12 | 15/0/0 | 언데드 해방·확률적 버서크 | **CAST_UNSUPPORTED**: 언데드 판별·성공/버서크·처치 판정 미연결. |
| 3·18 익스트라 힐 | 191 | 12 | 11/0/0 | 대상10칸 HP회복·언데드 피해 | `heal`, 살아 있는 PC 회복만. L1J 기본dice4/D8·기존 LOCAL 회복식, NPC회복·언데드 피해 미구현. |
| 3·19 커스:블라인드 | 192 | 12 | 20/0/0 | 대상2칸 암흑10초 | **CAST_UNSUPPORTED**: 시야/AI 실제 소비·저주확률 미연결. |
| 3·20 블레스드 아머 | 193 | 12 | 20/0/0 | 술자 갑옷 AC-3·1800초 | `armor`, 공식-3. LOCAL 현재 armor슬롯의 실제 UID 결속·해제 시 AC소비 중단·같은 UID 재착용 잔여복원. |
| 3·21 프로즌 클라우드 | 519 | 12 | 9/0/0 | 대상6칸·주변2칸 모든 적 | `area_damage`, 반경2 공식. LOCAL NPC 범위공격, L1J V0/D4/N8·물4. 위치만 지정하는 시전은 미구현. |
| 3·22 위크 엘리멘탈 | 600 | 12 | 8/0/0 | 대상10칸 취약 속성 파악 | **CAST_UNSUPPORTED**: 대상별 속성 원천·식별 응답 미연결. |
| 4·24 파이어볼 | 194 | 16 | 16/0/0 | 대상6칸·주변2칸 모든 적 | `area_damage`, 반경2 공식. LOCAL NPC 범위공격, L1J V0/D9/N5·불2. |
| 4·25 인챈트 덱스터리티 | 195 | 16 | 35/0/0 | 술자/혈맹원10칸 DEX+5·1200초 | `dexterity`, 공식+5. LOCAL 술자만 PC attribute·물리 전투 profile·status 소비. 혈맹 대상 미구현. |
| 4·26 웨폰 브레이크 | 196 | 16 | 25/0/1 | 대상2칸 무기 손상 | **CAST_UNSUPPORTED**: 대상 무기 소유·손상 및 촉매 원자소비 미연결. |
| 4·27 뱀파이어릭 터치 | 197 | 16 | 13/0/0 | 대상2칸 HP흡수 | `drain`, L1J V15/D10/N3·물4. LOCAL 실제 감소한 NPC HP×1.0만 술자 missingHP 이내 회복. |
| 4·28 슬로우 | 198 | 16 | 20/0/1 | 대상10칸 이동·공격속도 감소30초 | **CAST_UNSUPPORTED**: 이동/공격속도 소비·촉매 원자소비 미연결. |
| 4·29 어스재일 | 520 | 16 | 11/0/0 | 대상6칸·주변2칸 모든 적 | `area_damage`, 반경2 공식. LOCAL NPC 범위공격, L1J V0/D8/N5·땅1. |
| 4·30 카운터 매직 | 601 | 16 | 20/0/1 | 술자 피해마법1회 무효·16초·일부 제외 | **CAST_UNSUPPORTED**: incoming 마법의 실제 차단/예외·일회소모·촉매 원자소비 미연결. |
| 4·31 메디테이션 | 602 | 16 | 10/40/0 | 술자 명상600초 | **CAST_UNSUPPORTED**: HP40/MP10 원자소비·실제 MP재생/행동취소 미연결. L1J HP30/MP5/640초를 채택하지 않음. |
| 5·32 커스:패럴라이즈 | 199 | 20 | 35/0/2 | 대상2칸 석화4초 | **CAST_UNSUPPORTED**: 입력/AI 실제 정지·확률·촉매2개 원자소비 미연결. |
| 5·33 콜 라이트닝 | 200 | 20 | 25/0/0 | 대상6칸 번개 피해 | `damage`, L1J V40/D8/N5·바람8, 기존 LOCAL NPC 피해식. |
| 5·34 그레이터 힐 | 201 | 20 | 20/0/0 | 대상10칸 HP회복·언데드 피해 | `heal`, 살아 있는 PC 회복만. L1J 기본dice10/D8·기존 LOCAL 회복식, NPC회복·언데드 피해 미구현. |
| 5·35 테이밍 몬스터 | 202 | 20 | 30/0/2 | NPC10칸 하수인 전환3600초 | **CAST_UNSUPPORTED**: actor 소유권 전환·동료 수명·촉매2개 원자소비 미연결. 공식HP0/돌2를 보존하며 L1J HP20/돌1로 바꾸지 않음. |
| 5·36 리무브 커스 | 203 | 20 | 10/0/0 | 대상10칸 저주 해제 | **CAST_UNSUPPORTED**: 저주/저주아이템 owner·실제 해제 미연결. cure_poison으로 대체하지 않음. |
| 5·37 콘 오브 콜드 | 521 | 20 | 21/0/0 | 대상6칸 냉기 피해 | `damage`, L1J V40/D6/N5·물4, 기존 LOCAL NPC 피해식. |
| 5·38 마나 드레인 | 603 | 20 | 0/50/0 | 대상2칸 MP흡수 | **CAST_UNSUPPORTED**: 대상 NPC 현재MP 권위·흡수·술자HP50 원자소비 미연결. L1J MP1로 바꾸지 않음. |
| 5·39 다크니스 | 604 | 20 | 25/0/1 | 대상2칸 암흑20초 | **CAST_UNSUPPORTED**: 시야/AI 실제 소비·촉매 원자소비 미연결. |

범위공격4종은 공식 대상 문구를 따라 **선택 대상 중심 radius**를 쓴다. 라이트닝도 공식 주변3칸을 선형 beam으로 바꾸지 않았다. 현재 같은 맵의 보이는 살아 있는 적 NPC만 LOCAL Chebyshev 거리·기존 LOS 조건으로 선정하고, MP를 한 번 소비한 뒤 각 NPC의 기존 피해·처치·보상을 소비한다. PC/PvP·아군·지점만 지정하는 시전은 지원하지 않는다. heal의 PC 범위, DEX의 자신 한정, 갑옷 UID의 LOCAL 결속도 원본 전체 대상·화면·입력 동등성으로 확대하지 않는다. 전체27 허용목록 중3차 추가11종의 실제 패킷·수명·저장·해제 관측은 별도 시험 결과로 판정한다.

신규 계산치는 같은 [L1J SQL](https://github.com/l1j-en/classic/blob/103e6f6c9dd83545959d8e87d3f59f8de1f40ef0/db/l1jdb_m10.sql#L35637) 35637~35660행에서 이름·단계를 연결했다. V/D/N은 `damage_value/damage_dice/damage_dice_count`이며 회복은 별도 `l1j_healing` 정책이다. 공식 계산식은 공개되지 않았고 MR·장비SP·원본마법보너스 등 기존 LOCAL 제한을 유지한다. 기본MP 직접소비·1초 재사용도 LOCAL 선택이며 client UI delay·L1J reuseDelay를 공식 서버 쿨다운으로 확정하지 않았다. JSON `stage_support`와 각 `player_policy.unsupported_reason`이 현재 지원/거절 범위다.

## 4차11종 자료와 LOCAL 정책 — 구현·시험 결과와 구분

4차 대상은 key17/19/22/26/28/30/31/32/36/38/39다. **이11종의 identity·책 exact join·기본비용·지속시간·대상 문구는 고정 client와 보존 official 양쪽에서11/11 확인되며, 공식 서버의 확률·피해·회복 계산식은0/11 확보**다. 두 출처의11/11은 서로 중복되는 대조 범위이므로 더해22종이나 공식 수식100%로 표시하지 않는다. 원본 버전은26.09.29.2001로 고정한다. 공식 보존본은2026-10-27 KST 수집된 별도 시점 자료이며 이번4차에서 새 HTTP 수집 성공을 주장하지 않는다. 3차 web 재열기 실패도 보존한다.

원자료는 각 행 `source_snapshot.client_ui`·`book_native_item_line`·`book_native_spell_key_f41`, `source_snapshot.official_source`의 URL/raw_path/collected_at_utc/raw_sha256 및 `official_detail`이다. 예를 들어 [턴 공식 API](https://api-goats.plaync.com/linclassic/v2.0/game/spell/17?locale=ko-KR)·[카운터 공식 API](https://api-goats.plaync.com/linclassic/v2.0/game/spell/30?locale=ko-KR)·[메디테이션 공식 API](https://api-goats.plaync.com/linclassic/v2.0/game/spell/31?locale=ko-KR)는 해당 URL의 **보존 raw 응답**을 뜻하며 현재 재조회 결과가 아니다. 책의 고정 client f10 raw7000·공식 표시7·기존 LOCAL weight 환산을 그대로 쓴다.

| key·kind | 고정 client/공식 기본비용 MP/HP/돌·기간 | 계산·효과 연결 정책과 미확인 |
|---|---|---|
|17 `turn_undead`|15/0/0·순간|L1J undead1/3·IsTU 허용 NPC에 확률식. 성공은 현재HP를 정상 처치/보상 경로에 전달. 실패 버서크의 속도2배·기간30초는 **LOCAL**이며 공식 수치 미확보.|
|19 `blind`|20/0/0·10초|L1J 확률 참고, LOCAL 시야/목표획득·공격 소비. Native 암흑 화면/입력은 UNKNOWN. SQL16초로 바꾸지 않음.|
|22 `weak_elemental`|8/0/0·순간|대상의 약점 비트 확인만 한다. 저항 감소 마법으로 바꾸지 않는다. 현재 NPC 약점은 exact L1J join의 LOCAL 참고이며 원본 식별 연출은 UNKNOWN.|
|26 `weapon_break`|25/0/1·순간|L1J NPC weapon-broken flag와 최종 물리피해/2 참고. PC는 현재 무기UID에 같은 최종피해/2를 결속하는 **LOCAL 대체정책**이며 L1J PC의 랜덤 장비손상 수치가 아니다. 순간은 손상 발생시점이며 permanent 상태·repair producer API를 사용한다. Native 장비손상/수리UI는 UNKNOWN.|
|28 `slow`|20/0/1·30초|L1J 확률 참고, 이동/공격 interval2배는 **LOCAL**. 종료 때 복원·중복 비누적 정책. SQL64초 대신 공식30초.|
|30 `counter_magic`|20/0/1·16초|공식은 피해마법1회 무효·일부 제외. **MP 흡수와 피해 반사가 아니다.** 현재 대응 hostile 상태까지 허용하는 명시 LOCAL L1J 예외목록 subset이며 공식 예외와 같다고 주장하지 않음.|
|31 `meditation`|10/40/0·600초|L1J 자연회복 tick의+5 참고, 추가5MP/10초는 **LOCAL**. 최대MP·이동/공격/시전/텔레포트 취소·오프라인 MP 비지급. SQL5MP/30HP/640초를 채택하지 않음.|
|32 `paralyze`|35/0/2·4초|L1J 확률 참고·NPC 즉시 onset0. NPC 이동/공격 정지. L1J PC8초 대기/NPC16초 석화를 고정 client4초에 덮지 않음. Native PC 입력 차단은 별도 미확인.|
|36 `remove_curse`|10/0/0·순간|L1J 독/마비 치료 참고. blind/darkness/generic curse도 제거하는 것은 **LOCAL 확장**. 다른 버프·소유권 보존. 저주 아이템 등급/장비 해제까지 완료 주장하지 않음.|
|38 `mana_drain`|0/50/0·순간|L1J randint5..14+INT//2, 흡수량은 실제 target currentMP 상한·술자 회복은 maxMP 상한. NPC 초기MP는 기존 MonsterDef.mp의 L1J 참고값; 고갈 뒤 재흡수·초과회복으로 MP 생성 금지.|
|39 `darkness`|25/0/1·20초|L1J 확률 참고·LOCAL 시야/목표획득·공격 소비. 고정 client20초·돌1을 보존하며 Native 암흑 화면은 UNKNOWN.|

확률7종(17/19/26/28/32/38/39)의 dice는 각각7/11/10/12/8/12/11로 [동일 L1J SQL](https://github.com/l1j-en/classic/blob/103e6f6c9dd83545959d8e87d3f59f8de1f40ef0/db/l1jdb_m10.sql#L35638)의 명시 이름·단계 join이다. [L1Magic](https://github.com/l1j-en/classic/blob/103e6f6c9dd83545959d8e87d3f59f8de1f40ef0/src/l1j/server/server/model/L1Magic.java#L328) 일반식과 [L1Character](https://github.com/l1j-en/classic/blob/103e6f6c9dd83545959d8e87d3f59f8de1f40ef0/src/l1j/server/server/model/L1Character.java#L1070)의 INT magicBonus·level//4를 참고한다. diceCount=max(1, magicBonus+level//4+(법사1/다른직업-1)), dice 합에서 대상MR을 뺀 값을 d100과 비교한다. Leverage10·originalMagicHit0·미보유 PC MR0은 **LOCAL 대체값**이며 원본 Classic 확률식 복원이 아니다. 확정성공이나 임의 원본 성공률로 표시하지 않는다.

NPC 원천은 기존 [M1 monsters](../../../tools/local_original_session/data/m1/monsters.json)의 명시 `l1j_npcid`를 같은 SQL의 npc 열1544~1610·행20630/20631/20637/20640/20645/20661/20685/20702/20725/20744/20753과 연결했다. JSON `local_policy.npc_status_reference`에 기존11개 template의 MR/undead/weakAttr/IsTU/IsErase와 줄 출처를 저장했다. 이중 좀비27→45065·해골29→45107만 현재 참고의 undead1/IsTU=true이며, 오크 궁수 undead5를 언데드1로 취급하지 않는다. 약점 bit earth1/fire2/water4/wind8은 [Element.java](https://github.com/l1j-en/classic/blob/103e6f6c9dd83545959d8e87d3f59f8de1f40ef0/src/l1j/server/server/model/Element.java#L8)다. 알 수 없는 template을 추측한 일반값으로 공식 확인처럼 채우지 않는다.

세부 효과의 L1J 원문은 [L1SkillUse](https://github.com/l1j-en/classic/blob/103e6f6c9dd83545959d8e87d3f59f8de1f40ef0/src/l1j/server/server/model/skill/L1SkillUse.java)163~169(카운터 예외),1785~1789(독/마비 치료),2038~2059(암흑·마비),2276~2297(턴·MP흡수·무기손상),2992~3007(약점 확인),3183~3204(대상 허용·일회 카운터 소비), [L1Attack](https://github.com/l1j-en/classic/blob/103e6f6c9dd83545959d8e87d3f59f8de1f40ef0/src/l1j/server/server/model/L1Attack.java#L962)962~964/1058~1060(NPC 손상 최종피해 절반), [MpRegeneration](https://github.com/l1j-en/classic/blob/103e6f6c9dd83545959d8e87d3f59f8de1f40ef0/src/l1j/server/server/model/MpRegeneration.java#L69)69~71(메디+5)다. 현재 L1J 참조 commit은103e6f6c9dd83545959d8e87d3f59f8de1f40ef0이며 새 계산 출처의 path/hash는 JSON provenance에 보존했다. Native gfx·아이콘·입력·화면 동등성은 이 자료로 확인되지 않는다.

자료 확인은 기존39행 파싱과11종 고정/공식 원문·현재 kind·비용·기간·L1J source-ref 검토 범위다. 실제 효과 소비·저장/복원·성공/실패·정상 종료는 구현 및 전용 시험 결과가 추가되기 전에는 PASS가 아니다. 정상 데이터 기간은 바꾸지 않았고 원본 클라이언트·캡처·사용자 저장·manual 프로필을 실행/변경하지 않았다.

## 확정 wire와 남은 의미

| 방향/메시지 | 원문 확인·정적 소비 | 미확정/LOCAL 경계 |
|---|---|---|
| C2S `4EE6 CS_USE_SPELL_REQ` | required f1:uint32 spell key, optional f2:UseSpellParam. 정상 `SpellInteraction→5B33A0→5B7520→27D620` | 실제 학습·현재 대상·범위·비용은 별도 서버 권위 검사다. |
| `UseSpellParam` | 모든 child optional. f1:int32는 원 대상 vslot8의 EAX. f3/f4:uint32는 원 입력 또는 대상 위치의 Coordinate DWORD. 음수 int32는 sign-extended varint이며 zigzag가 아니다. | f1을 UID64 임의 절단으로 만들지 않는다. f3/f4는 wire raw 좌표이지 tile 값으로 확정한 것이 아니다. 다른 optional 필드 역할은 여기서 정하지 않는다. |
| S2C `4E60 SC_AVAILABLE_SPELL_NOTI` | outer f1:repeated SpellInfo, required outer 없음. child required f1:int32 key/f2:bool, optional f3:i32/f4:i32/f5:bool/f6:i32. `305620→event17FCAC0→5B19B0` | 별도 outer 성공 bool은 없다. 원 서버 초기 전체 snapshot인지 delta인지 미확정이다. |
| SpellInfo 소비 | f2=true upsert, false erase. f4 nonzero→tree3F0, zero→3E0. f6>0이면 MP threshold, 아니면 static config+84. | f3/f4/f5의 완전한 업무 의미·공식 레벨 값은 UNKNOWN. 일반 마법 f4=0·전체 재연결 목록 정책은 LOCAL producer 선택이다. |
| C2S `0960 CS_USE_ITEM_REQ` | required f1:uint64 full Inventory UID, required f2:UseItemReqParam. 정상 Inventory callback→4FD260→4FE630→4FE820→default52A410→27D620 | book template는 UID/스킬키가 아니다. 서버는 실제 소유 Q와 중복학습·직업·레벨·실소비·저장을 별도로 확인한다. |
| S2C `4F25 SC_USE_SPELL_ACK` | required f1:uint32/f2:closed enum int32. typed `2FA6C0→event1802640→5B2A00` | **SC_LEARN_SPELL_ACK가 아니다.** 성공 숫자·f1 의미·필수 응답/순서는 UNKNOWN. 임의 success0 ACK를 만들 근거가 없다. |
| `4E38 SC_STATUS` | required f12/f13:int32=current/max MP | 기존 complete status의 다른 필드/권위를 유지한다. MP 변경만으로 시전 표시가 증명되지 않는다. |

정본: [REA104 wire findings](../../local_server_rea_20261016/run104_skill_buff_contract/wire_schema/findings.md), [compiled schema packet](../../local_server_rea_20261016/run104_skill_buff_contract/wire_schema/packet.json), [4EE6 독립 계약](../../local_server_rea_20261016/run104_skill_buff_contract/wire_schema/cast_4ee6/packet.json), [정상 입력 소비](../../local_server_rea_20261016/run104_skill_buff_contract/spell_input/findings.md). 이것은 보존 고정 CONTROL의 정적 자료이며 현재 loaded image를 관측한 결과가 아니다. 신규 binary 전수 조사나 REA runtime 세션을 만들지 않았다.

## 마법서 → 학습 경로

REA148은 원 UI에서 현재 Inventory UID를 찾아 ItemEntity+50 discriminator로 분기한 뒤 default `0960`으로 가는 경로와, template180/181(라이트/실드)의 default handler 선택을 확인했다. 원 공식 book discriminator는 아직 UNKNOWN이다([book-use packet](../../local_server_rea_20261016/run148_book_learning_contract/book_use/packet.json)).

후속 REA150의 **기존 명시 LOCAL_BOOK_USE_RAW0_V1**은 materialized `ItemInfo.f5=0`을 **present**로 공급하는 선택이다. 원 raw0 case가 child f1=1을 만들고 default sender가 부재 f15/f16을 각각0 present로 보충한다. 최종 **f1=1,f15=0,f16=0; f17 absent**다. 이는 원 정상분기의 LOCAL 선택이며 공식 책 분류를 발견한 결과가 아니다. 이 로컬 정책을 다른 책 template로 확장할 때도 실제 UID·Q·현재 소유·pending·정상 정리를 유지한다([REA150 packet](../../local_server_rea_20261016/run150_local_book_use_policy/worker/packet.json)).

로컬 연결은 **현재 책 UID의 0960 → 직업/레벨/중복학습 검사 → 같은 소유 책 Q1 소모와 learned key 저장 → 0965 inventory 변경 + 4E60 available row → 후속 4EE6**이다. 응답 순서는 LOCAL 계약으로 명시하며 원 공식 필수 순서라고 주장하지 않는다. 조회/조건 실패는 책·MP를 소비하지 않고, 저장 시도 이후 불확실한 결과를 환불/재학습 성공으로 덮지 않는다. 별도 forged learned grant·학습 ACK는 필요하지 않다.

공식 상세의 `textbook.id`와 보존 client item의 exact id/name을 각각 대조했다. JSON의 `player_policy.book_classic_key`는 **item template ID**이며 Inventory UID가 아니다.

## 1~2단계 수치와 범위 — 1차 구현 당시 기록

이 절의 7종 지원·9종 거절은 **1차 구현 당시 상태**를 보존한 기록이다. 아래 2차 명세에서 16종 지원 후보로 확장했으며, 과거 실패·성공을 수정하지 않는다.

| key | 주문 | 책 template | 공식/고정 UI MP | 지속초 | generic 구현 후보 |
|---|---|---:|---:|---:|---|
| 0 | 힐 | 164 | 4 | 순간 | heal; L1J 계산식 LOCAL |
| 1 | 라이트 | 180 | 4 | 7200 | 미구현, 광원 소비 필요 |
| 2 | 실드 | 181 | 2 | 1200 | shield, 공식 AC-2 |
| 3 | 에너지 볼트 | 182 | 3 | 순간 | damage; L1J V8/D10/N1 |
| 4 | 텔레포트 | 183 | 5 | 순간 | 미구현, 이동 계약 필요 |
| 5 | 아이스 대거 | 515 | 3 | 순간 | damage; L1J V10/D10/N1 |
| 6 | 윈드 커터 | 516 | 3 | 순간 | damage; L1J V10/D10/N1 |
| 7 | 홀리 웨폰 | 598 | 10 | 1200 | 미구현, 무기별 효과 필요 |
| 8 | 큐어 포이즌 | 184 | 8 | 순간 | 미구현, 독 상태 필요 |
| 9 | 칠 터치 | 185 | 9 | 순간 | 미구현, 피해→흡혈 결속 필요 |
| 10 | 커스:포이즌 | 186 | 10 | 30 | 미구현, 독·재료 매핑 필요 |
| 11 | 인챈트 웨폰 | 187 | 20 | 1800 | 미구현, 무기별 추가피해+2 |
| 12 | 디텍션 | 188 | 8 | 순간 | 미구현, 숨은 대상 상태 필요 |
| 13 | 디크리즈 웨이트 | 599 | 10 | 1800 | 미구현, 무게 계산 소비 필요 |
| 14 | 파이어 애로우 | 517 | 3 | 순간 | damage; L1J V10/D10/N2 |
| 15 | 스탈락 | 518 | 3 | 순간 | damage; L1J V10/D10/N2 |

**1단계는 군주10·기사50·요정8·법사4, 2단계는 군주20·요정16·법사8이며 기사는 공식 학습 명단에서 제외된다.** 데이터의 class0/1/2/3는 현재 제품의 군주/기사/요정/법사 convention이다. 레벨 충족은 자동 학습 지급이 아니다. 공식 `classNames/learnings`를 우선하며 L1J의 darkelf 허용·제단 위치 조건은 Classic으로 옮기지 않는다.

숫자의 원문은 보존 [official/spells.json](../../../tools/local_original_session/data/official/spells.json)과 [official/items.json](../../../tools/local_original_session/data/official/items.json)의 각 entry `source`에 URL·수집시간·raw path/hash로 남아 있다. 공식 API 예: [힐0](https://api-goats.plaync.com/linclassic/v2.0/game/spell/0?locale=ko-KR), [실드2](https://api-goats.plaync.com/linclassic/v2.0/game/spell/2?locale=ko-KR), [에너지 볼트3](https://api-goats.plaync.com/linclassic/v2.0/game/spell/3?locale=ko-KR). 이번 web 도구 재열기는 접근 실패하여 최신 응답으로 덮지 않았고, 2026-10-26 UTC/27 KST 보존 응답을 재사용했다. 이 live 공식을 고정 client26.09.29.2001의 역사 API라고 부르지 않는다. 선정 16행의 UI MP/HP는 보존 client 설명과 각각 대조했다.

L1J는 [l1j-en/classic](https://github.com/l1j-en/classic) 로컬 참조 checkout `103e6f6c9dd83545959d8e87d3f59f8de1f40ef0`다. `db/l1jdb_m10.sql:35621–35636`의 명시 이름 join으로 수치 후보를 가져왔고, `C_ItemUSe.java:3413–3499`의 일반 책 학습도 1단계 기사50·법사4와 2단계 법사8을 뒷받침한다. L1J item45000대/skill1..16을 Classic book/key와 혼동하지 않는다.

L1J 값보다 고정 UI/공식 값을 우선했다: Shield는 MP2/1200초(L1J8/1800), Light7200초(L1J3600), IceDagger/WindCutterMP3(L1J4), FireArrow/StalacMP3(L1J6), DecreaseWeightHP0(L1J50)다. 공식이 계산식을 공개하지 않은 공격/힐은 companion 데이터의 `formula_policies`를 LOCAL backend 참고로 재사용했다. 서로 독립인 dice·Java 단계별 truncation·INT/SP·MR·법사 critical·힐 lawful/INT 보너스·HP clamp를 단일 임의 고정 피해/힐로 대체하지 않는다. 칠 터치를 단순 damage로 처리하면 흡혈 기능이 누락되므로 지원 후보에서 제외했다.

1차 당시 JSON `player_policy.supported`는 generic consumer에 맞는 **후보 allowlist**(heal0/shield2/damage3·5·6·14·15)였으며 실행 PASS 표시가 아니었다. 나머지 주문은 학습 정적 자료만 준비하고 `CAST_UNSUPPORTED`였다. LOCAL actual base-MP debit·1초 재사용은 명시 backend 선택이며 원 서버 동적 비용/공속 수치가 아니다. 현재 16행은 아래 2차 후보로 갱신했다.

1차에서 재사용한 공격 계산에는 더 좁은 범위가 있다. `world_feature_magic._world_magic_cast`는 기존 `world_combat.companion_magic_damage`를 호출하며 현재 INT와 SQL dice parameter를 전달한다. **extraSP·무기 마법피해·original magic 보너스는0, leverage는10, 대상 몬스터 MR·weakAttr는0인 LOCAL baseline**이며 2차도 이 한계를 유지한다. 몬스터별 MR·약점과 장비/SP/캐릭터 original bonus를 모두 소비하는 완전한 L1J 계산식이나 공식 서버 계산을 구현했다는 뜻이 아니다. 데이터에 보존한 전체 참고식과 helper가 실제로 받는 입력 범위를 구분한다.

1차 학습 UX에도 제한이 있었다. **당시 16개 중 시전 지원7개·미지원9개였고, 미지원9개의 학습을 `MAGIC_EFFECT_UNSUPPORTED`로 거절해 책을 보존했다. 기존 저장에서 이미 배운 미지원 key는 삭제하지 않고 보존하되, 시전도 같은 오류로 거절하며 MP를 소비하지 않았다.** 당시 `CAST_UNSUPPORTED` 목록은 라이트·텔레포트·홀리 웨폰·큐어 포이즌·칠 터치·커스:포이즌·인챈트 웨폰·디텍션·디크리즈 웨이트다. `world_magic.learn`의 미지원 거절이 책 mutation/저장보다 앞에 있음을 확인한 기록도 보존한다. 2차는 이 9행의 효과 소비를 추가하며, 이 문서의 기록만으로 원 클라이언트 안내 UX·입력이 증명되지는 않는다.

## 2차 명시 승인: 16종 효과와 실제 소비 명세

사용자가 승인한 2차 범위는 기존 7종에 아래 9종의 LOCAL 효과를 연결하는 것이다. 데이터 `player_policy.supported=true`는 16행의 구현 후보 허용이며 원본 화면·공식 수식 동등성·실행 PASS를 뜻하지 않는다. MP·지속시간·대상 설명은 보존 공식/고정 UI를 유지하고, 공식에 없는 수치는 출처 있는 L1J 또는 명시 LOCAL 선택으로 구분한다.

| key/주문 | 현재 kind·선택 수치 | 실제 소비와 범위 |
|---|---|---|
| 0 힐 | `heal`, MP4, 순간 | 기존 LOCAL 힐식·실 HP 상한 처리 재사용. |
| 1 라이트 | `light`, MP4, 7200초 | 지속 `is_lit` 상태·저장/잔여/만료. L1J 밝기14는 참고만이며 Classic 광원 wire·실제 화면 빛은 UNKNOWN. |
| 2 실드 | `shield`, MP2, 1200초 | 기존 AC-2·저장/잔여/만료 재사용. |
| 3 에너지 볼트 | `damage`, MP3, 순간 | 기존 LOCAL 공격식 V8/D10/N1. |
| 4 텔레포트 | `teleport`, MP5, 순간 | 같은 맵 반경200의 무작위 통행 가능 칸을 기존 이동·위치 저장·관심 재계산 경로로 처리. 반경200은 L1J 참고 LOCAL, 조종반지/기억 장소는 제외. |
| 5 아이스 대거 | `damage`, MP3, 순간 | 기존 LOCAL 공격식 V10/D10/N1. |
| 6 윈드 커터 | `damage`, MP3, 순간 | 기존 LOCAL 공격식 V10/D10/N1. |
| 7 홀리 웨폰 | `weapon_hit`, MP10, 1200초 | 공식 명중+1/피해+1. 자신의 현재 실제 무기 UID에 결속하며 교체 중 보너스를 쓰지 않고 같은 UID 재장착 시 잔여기간 적용. 공식 언데드 추가의 수치·조건은 미확정/미소비. |
| 8 큐어 포이즌 | `cure_poison`, MP8, 순간 | 자신/살아 있는 PC 또는 보이는 살아 있는 NPC의 이번 피해독·틱 상태 해제. 다른 독 종류는 미구현. |
| 9 칠 터치 | `drain`, MP9, 순간 | 2칸 내 보이는 살아 있는 적대 NPC에 기존 LOCAL V10/D10/N2 피해, **실제 감소 HP×1.0**만 시전자 missing HP 이내 회복. 과잉피해 흡혈 배제는 LOCAL 선택. |
| 10 커스:포이즌 | `poison`, MP10, 30초 | 3칸 내 보이는 살아 있는 적대 NPC에 3초마다5HP, 재시전 갱신/치료/만료/사망 정리. 수용 조건 뒤 감염확률1.0은 LOCAL이며 공식/L1J 확률식을 구현한 것이 아니다. |
| 11 인챈트 웨폰 | `weapon_damage`, MP20, 1800초 | 공식 피해+2. 홀리와 같은 자신의 실제 무기 UID 결속 LOCAL 정책. |
| 12 디텍션 | `detect`, MP8, 순간 | 자신 시전, 같은 맵 현재 screen 좌표 안 엔티티의 투명상태 해제. 현재 world visibility 필터·관심 재계산/재등장·원 native 투명 wire는 미연결/UNKNOWN. 공식18칸의 전체 숨은 객체/잠복 종류 복원도 미확인. |
| 13 디크리즈 웨이트 | `weight`, MP10, 1800초 | LOCAL 무게한도+180을 무게 계산·normal_skill admission에 소비하고 잔여/만료 복원. 자연회복·trade/loot의 별도 capacity 소비는 이번 연결에 포함하지 않는다. 아이템 자체 무게는 바꾸지 않는다. |
| 14 파이어 애로우 | `damage`, MP3, 순간 | 기존 LOCAL 공격식 V10/D10/N2. |
| 15 스탈락 | `damage`, MP3, 순간 | 기존 LOCAL 공격식 V10/D10/N2. |

홀리/인챈트의 실제 공격 명중·피해, 독의 틱 HP/처치·보상, 큐어의 다음 틱 중단, 칠 터치의 피해/흡혈은 소비 지점에서 확인해야 한다. 디텍션 재등장·무게한도의 자연회복 적용은 현재 미연결이며 상태/수치 저장 성공으로 대신하지 않는다. 버프 숫자나 저장 키만 존재한다고 전체 효과를 완료로 판정하지 않는다. 타 PC 대상 지원은 위 LOCAL 범위를 넘겨 주장하지 않는다.

커스 감염확률의 L1J 참고식은 `L1Magic.java:326–343`의 probability dice·magicBonus/magicLevel·직업·originalMagicHit·leverage·대상MR와 `171–221`의 상태/zone/추첨 검사를 요구한다. 현재 MonsterDef에는 MR/resist/독 면역 입력이 없고 캐스터 originalMagicHit·원래 장비/SP 소비도 연결되지 않았다. 해당 값을 추측해 L1J 수식을 완성했다고 주장하지 않고 현재 대상 수용 guard 뒤 확정감염을 명시 LOCAL로 채택했다. 공식 확률은 공개되지 않았고 이 미채택 수식·입력 부재는 남은 범위다.

**커스:포이즌 촉매는0개다.** 보존 `official/spells.json` id10의 `official_list.consumables`는 `mp:10,hp:0,itemCount:0`을 명시한다. 상세 응답의 item 생략만으로0을 추정한 것이 아니다. 고정 client 설명도 MP/HP10/0이며 촉매 행이 없다. 따라서 JSON `materials.value=[]`, `OFFICIAL_LIST_ZERO_CATALYST`를 선택했다. L1J SQL의 Magic Gem40318×1은 미채택 비교로 보존하며 Classic 마력의 돌166과도 혼동하지 않는다. 이 때문에 마력의 돌을 임의 소비하거나 촉매 guard를 우회할 필요가 없다.

L1J 세부 참고는 동일 checkout의 [SkillUse](https://github.com/l1j-en/classic/blob/103e6f6c9dd83545959d8e87d3f59f8de1f40ef0/src/l1j/server/server/model/skill/L1SkillUse.java#L1783)의 큐어1783–1784·흡혈1944–1945/3034–3043·독2049–2050, [독 수명](https://github.com/l1j-en/classic/blob/103e6f6c9dd83545959d8e87d3f59f8de1f40ef0/src/l1j/server/server/model/poison/L1DamagePoison.java#L69), [무게한도](https://github.com/l1j-en/classic/blob/103e6f6c9dd83545959d8e87d3f59f8de1f40ef0/src/l1j/server/server/model/Instance/L1PcInstance.java#L1686), [무기 버프](https://github.com/l1j-en/classic/blob/103e6f6c9dd83545959d8e87d3f59f8de1f40ef0/src/l1j/server/server/model/Instance/L1ItemInstance.java#L1075), [통행칸 선택](https://github.com/l1j-en/classic/blob/103e6f6c9dd83545959d8e87d3f59f8de1f40ef0/src/l1j/server/server/model/L1Location.java#L128)이다. L1J의 NPC 독7200초는 채택하지 않고 공식30초를 쓴다. 홀리의 공식 기본 피해+1을 L1J의 holy/undead 조건식으로 대체하지 않는다. 이번 web 공식 API 재열기는 접근 실패했고 위 고정 GitHub 원문은 열렸다. 기존 공식 응답을 최신 재수집 응답으로 덮지 않았다.

버프 저장에는 실제 만료시각과 필요한 무기 UID를 사용한다. NPC 독은 월드 actor 수명에 귀속하며 플레이어 저장에 runtime actor UID를 영구 소유처럼 넣지 않는다. 정상 만료·치료·죽음·actor 제거·재접속에서 상태/타이머·소비·정리를 확인해야 하며, 시험 단축시간은 정상 데이터의 지속시간을 바꾸지 않는다. 2차 시험 결과는 아래 별도 절에 기록한다.

16권 책은 M1 item catalog에 없으므로 `player_policy.book_raw_weight`에 **고정 client item f10=7000**을 value/source/ref로 보존했다. 각 책의 공식 표시 무게7·exact id/name join과 대조했고, raw1000당 부담무게1인 기존 LOCAL weight consumer에 이 raw값을 전달한다. M1에 실제 값이 있으면 그 값을 우선하며 정확히 이번16권에만 이 fallback을 쓴다. 미지 항목을0으로 추정하거나 unknown kit weight 검사를 건너뛰지 않는다.

## 표시·지속효과 경계

[SPELL_DISPLAY_EVIDENCE](SPELL_DISPLAY_EVIDENCE.md)의 `4E31 kind18/19→SpellAction`, `4ED8 대상UID/gfx`, `4ED9 좌표gfx`를 재사용한다. 시전자 자신의 SPR action18/19 row가 필요하고, EnergyBolt key3을 gfx로 쓰지 않는다. Heal744/Shield221·EnergyBolt projectile167은 자원 근거가 있는 LOCAL 표시 후보이며 주문별 공식 발행·순서·실화면은 UNKNOWN이다. f6/f7 projectile UID/gfx와 raw A/B가 미공급이면 비행 성공으로 표시하지 않는다.

[BUFF_GAMETIME_EVIDENCE](BUFF_GAMETIME_EVIDENCE.md)의 `4E91`은 outer f1=1/2 upsert·3 remove, required f2 BuffIconInfo다. child f1은 CommonSpell catalog, f3는 uint32 bits→signed 잔여초 consumer, f4/f5에서 고른 K는 HUD identity/image key다. **K를 UI icon이나 spell key와 보편적으로 같게 만들지 않는다.** Shield catalog2의 원 CommonSpell f3=485는 PNG 자료이며 월드gfx221과 별개다. 임의 발급 K/485 실험은 스위치 뒤 LOCAL 표시 후보로 남긴다.

정상 Shield는1200초다. 10초 만료는 기존 명시 허용된 시험 전용 source/설정에서만 쓰고 normal 데이터는 바꾸지 않는다. 실제 지속시간·재접속 잔여/만료는 서버 실제 clock·기존 저장·복원에 결속하며 packet send나 HUD 반짝임으로 증명하지 않는다. `4E5E` clock 단위는 UNKNOWN이므로 임의1초 cooldown을 그 wire f1로 송신하지 않는다.

## 이번 확인과 다음 입력

16개 고정 UI MP/HP, 공식 learn/class/textbook, exact client item template, JSON parse/unique keys/books와 공격 formula parameter를 확인했다. 원본·게임·저장 실행 없이 끝냈고 신규 binary decode/guard/검사 도구/중복 registry는 만들지 않았다. 구현 담당에게 정확 schema·책 LOCAL 경로·직업 제한·데이터 shape를 전달했다.

원본 클라이언트의 available 소비·마법창/단축키·연속 시전·표시/아이콘은 미확인이다. 원 공식 표시 정책을 확정하려면 고정 버전 정상 cast의 실제 C2S key/target과 S2C fields/presence/stream 순서가 최소 추가 입력이다.

## 1차 구현 후 시험 전용 패킷 결과 — 보존 기록

`SL_TEST_PORT_BASE=22000`에서 `python -X utf8 -B -m tools.local_original_session.world_magic_tests` 19개가 통과했다. 저장 단위시험의 재고 참가자는 명시 fake CAS이며, 아래 실제 소켓 시험과 구분한다.

`python -X utf8 -B -m tools.local_original_session.hunt_bot_magic --scenario magic`의 [최종 원결과](../runs/hunt-magic-gabv0wk1/summary.json)는 **21 checks SUCCESS**, 3 epochs 정상 정리, 실행 중 기록한 소비 소스17개의 변경 없음이다. 새 시험 프로필 SoloMage 법사5의 FIRST→로그인→선택→월드 이후 실제 decoder/router/handler로만 행동했다. 책·HP1·레벨·재고는 로그인 전 전용 fixture이며 사용자 저장을 사용하지 않았다. 공용 kit 및 등록표 후속 변경 전의 [앞선 성공](../runs/hunt-magic-373ksy55/summary.json)과 [kit 변경 후 성공](../runs/hunt-magic-zvhmx1n0/summary.json)도 별도로 보존한다.

- 힐/실드/에너지 볼트 책 각 1→0, 4E60 목록과 learned 저장. 첫 힐 책이 저장 장비의 기준 항목인 경우 기존 `_world_replace_kit` 소비 owner를 통해 남은 항목으로 함께 이전했다.
- 에너지 볼트 MP52→49·몹 HP6→0·처치, 힐 MP49→45·실제/수신 HP1→13, 실드 MP45→43·AC10→8.
- 정상 Quit 후 재기동에서 learned[0,2,3]·MP43·버프 잔여 약8.688초 복원. 실제 틱 약8.752초 뒤 AC10/버프 만료, 다음 재접속에도 learned 유지·버프 없음.

시험 실드만 `SL_PLAYER_MAGIC_BUFF_SECONDS=10`을 사용했고 정상 데이터1200초는 유지했다. 4E31/4ED8 후보는 `SL_SPELL_EXP=1`, 4E91 후보는 별도 `SL_PLAYER_MAGIC_BUFF_UI=1`이다. 최종 봇은 4ED8 후보 수신까지 확인했으며 4E91 원본 HUD·시간 표시와 투사체/화면은 확인하지 않았다.

앞선 공용 source pin 불일치와 힐의 stale HP 재송신 실패는 [모듈별 실행 원문](../runs/m3-player-magic-20261027-180106/results.json)에 보존한다. 수정 뒤 최종 조합의 성공을 이전 실패의 소급 성공으로 취급하지 않는다. 전체 회귀의 범위 밖 실패도 위 원문과 별도로 판정한다.

전체 `*_tests.py`는 독립 CLI 모듈을 구분해 81개 모두 실행했다. 최종 모듈별 결과는 **80 PASS / 1 FAIL**, latest unittest1680개, 시간 초과 미완0이며 Lane4 독립 CLI23 checks도 SUCCESS다. 실패 모듈은 failfast로 첫 실패에서 멈췄고 성공 모듈은 전 시험을 실행했다. 남은 기존 실패는 `world_ai_tests.AiTests.test_leash_returns_home`의 `npc.py:89 NPC_EXPLICIT_SPR56_TEMPLATE0_ONLY`이며 이 요청의 수정 범위 밖이다. 전체 회귀 통과 조건은 미충족이다. 시험 listener22000/24030은 마감 시0이고 사용자 저장/원본/화면은 변경·실행하지 않았다.

## 2차 구현 후 시험 결과

현재 16종 데이터의 JSON 파싱·key0..15/책 template 중복 없음·9종 kind/LOCAL 매개변수·커스:포이즌 공식 `itemCount:0`·16권 raw무게7000 선택을 확인했다. 이 확인은 정적 데이터 검사다. 2차 최종 [마법 단위시험](../runs/player-magic-stage2-unit-final-20261027-191515.log)은 **30/30 OK**, [직접 관련 회귀](../runs/player-magic-stage2-regression-20261027-191324.log)는 world6/effect-map5/weight14/stats13/M3-data7의 **45/45 OK**, [활/탄약 회귀](../runs/player-magic-stage2-ammo-20261027-192201.log)는 **13/13 OK**다. 아래 통합15개까지 중복 없이 합한 성공 범위는 **103 unittest**다. 최초191220 결과도 보존하며 최종 Source의 시험으로 대체 주장하지 않는다. 앞 절의 1차21 checks·전체 회귀 결과를 2차 성공으로 재사용하지 않는다. 원본 클라이언트·캡처·게임 화면은 이 자료 작업에서 실행하지 않았다.

[191433 통합+마법 실행](../runs/player-magic-stage2-final-modules-20261027-191433.log)은 통합15개와 마법30개를 합친45개 실행 중 **마법 fixture 오류2개**(`WorldView.light_sources` 부재)가 발생했다. 이 로그를45개 성공으로 표시하지 않는다. fixture 보완 뒤 위191515 마법30개가 통과했으며 원실패 로그는 보존했다.

`SL_TEST_PORT_BASE=22000`에서 [2차 실제 소켓 원결과](../runs/hunt-magic-hdcjysyd/summary.json)는 **107/107 SUCCESS**, 3 epochs 모두 `SESSION_STOPPED`·cleanup true·failure null, magic handler 오류[]·실행 중 기록한 소비소스22개 변경[]다([CLI 원로그](../runs/player-magic-stage2-all-20261027-191914.log)). Source 조합과 각 시작/종료 해시는 원결과의 `source_sha256_start`/`source_sha256`, fixture는 같은 파일의 `fixture`가 정본이다. 새 전용 SoloMage 법사30·HP1/MP332·16권 책·투명120초를 로그인 전에 선언했고, FIRST→로그인→선택→월드 이후 요청은 실제 decoder/router/handler를 통과했다. 사용자 저장은 사용하지 않았다.

- 16권의 현재 UID/Q를 받아 각각 책1→0·available 목록·learned0..15 저장 후 실제 시전 key0..15·각 MP 차감을 확인했다.
- 칠 터치 NPC HP6→0/시전자HP40→46, 커스 독의 실제 틱HP6→1 뒤 처치/정리, 큐어 뒤 틱 중단을 확인했다. 디텍션은 선언한 투명상태 해제와 무상태 시 MP만 소모한 범위다.
- 실제 같은 RNG 상태를 복제한 계산 기준과 실제 공격을 함께 남겼다. 홀리 적용 공격은 피해1→2, 홀리+인챈트 적용 공격은2→5이며 실제 NPC HP 감소/처치도 있었다. 홀리 명중+1은 유효 weapon 입력과 단위시험이 근거이며 이 소켓 실행만으로 확률분포가 검증되지는 않는다.
- 무게한도1800→1980, 라이트 활성·서버 광원 수명 상태, 실드AC-2와 다섯 버프 `[1,2,7,11,13]`의 정상 Quit 저장→첫 재접속 잔여 복원→실제 틱 만료→두 번째 재접속 부재를 확인했다. 시험 버프만10초이며 정상7200/1200/1800초 데이터는 유지했다.
- 텔레포트는 같은 맵0의 `(32595,32906)→(32413,33049)` 통행 가능 도착·수신·저장 일치를 확인했다.

시험 담당의 최종 listener22000/24030은0이다. PC 독의 치명타·오프라인 복원/기한 및 비치명 독 만료·명중 보정은 단위시험 범위이며 소켓 관측으로 확대하지 않는다. native 입력·렌더링·원본 광원/아이콘·디텍션 실제 재등장은 UNKNOWN이고 trade/loot는 기존 별도 capacity 소비를 유지한다. 이번103개 회귀는 1차 전체81개 모듈의 기존 실패를 재시험하거나 지운 결과가 아니다.

## 3차 구현 후 지정 검증 결과

`SL_TEST_PORT_BASE=22000`에서 `python -X utf8 -B -m tools.local_original_session.world_magic_tests`는 **38/38 OK**다([원로그](../runs/magic-tier3-20261027-194804-unittest.log)). 신규11종 학습·직업/레벨/MP 거절, 상위 회복·흡혈·단일 피해, 네 범위공격의 복수 NPC 피해와 범위/맵/동료 제외, 갑옷 UID 결속·DEX 계산·기존 저장 호환·잔여 복원/만료, 미지원12종의 학습/저장된 key 시전 거절을 확인했다. 함수 직접 호출·fake CAS를 쓰는 단위시험은 아래 소켓 관측과 구분한다.

`python -X utf8 -B -m tools.local_original_session.hunt_bot_magic --scenario all`의 [최종 원결과](../runs/hunt-magic-5ve2hzvn/summary.json)는 **189/189 SUCCESS**다([CLI 원로그](../runs/magic-tier3-20261027-195251-socket.log)). 지원27종의 학습과 총32회 실제 시전을 관측했고, 다섯 epoch 모두 정상 FIRST/로그인/선택/월드 진입 후 `SESSION_STOPPED`·cleanup true·failure null로 마감했다. 기록한 소비 Source의 실행 중 변경은 없으며 정확한 조합은 원결과 `source_sha256_start`/`source_sha256`에 있다. 예상한 미지원 책12개·unknown 주문 거절 외의 마법 오류는 없었다. 오류 보관은 기존 최대8개 제한이므로 12개 거절의 각각 관측은 `checks`가 근거다.

- 새 전용 SoloMage 법사30·HP1/max318·MP332, 기존 starter와 추가23권의 시험용 책, 실제 착용 갑옷103을 로그인 전에 선언했다. 사용자 저장·`starter.json`·manual 프로필은 변경하지 않았다. 책은 현재 수신 UID의 일반0960으로 학습하고 소모/저장/available 목록을 확인했다. 미지원 책12권은 수량1과 저장을 보존했다.
- 기존 힐 뒤 전투 전에 익스트라 힐 HP16→52/MP328→317, 그레이터 힐 HP52→114/MP317→297을 확인했다. 두 시전 전 incoming swing은0이며 HP를 낮추기 위한 공격·NPC·RNG 준비나 입장 후 HP 강제 변경은 없었다.
- 추가 직접공격·흡혈·네 범위공격 모두 실제 NPC HP 감소/처치와 MP 한 번 차감을 확인했다. 이번 소켓 실행의 각 범위공격 실제 대상은1마리였으며 **복수 대상과 제외 조건은 단위시험 범위**다. 이 결과를 원본 광역 연출·PvP/아군 처리 검증으로 확대하지 않는다.
- 블레스드 아머는 실제 갑옷 UID536871273에 결속해 AC6→3, DEX는 전투 profile과 수신 status에서7→12였다. 정상 Quit 저장→첫 재로그인 잔여 복원→실제 clock 만료와 UID 결속 정리→다음 재로그인 부재·learned27 유지까지 확인했다. 시험 지속시간만10초이며 정상1800/1200초는 그대로다. 필요한 MP는 정상 자연회복으로 준비했다.

최초 [실패 원결과](../runs/hunt-magic-o923_o8q/summary.json)와 [로그](../runs/magic-tier3-20261027-194853-socket.log)는 보존한다. 171항목 중170개 뒤 어스재일 대상이 재사용 대기 중 사거리 밖으로 이동해 `MAGIC_TARGET_OUT_OF_RANGE`/응답 대기 TIMEOUT이 발생했다. 세 epoch의 정리와 Source 변경 없음은 확인했으나 전체 성공이 아니다. 재사용/MP 준비 후 현재 대상을 선정하고 사거리 여유를 두도록 시험만 수정했다. 새 회복 시험도 전투 전 HP1 시작 계보로 옮겼으며, 최초 코드의 피해 준비 helper는 실제 추가 공격을 보내지 않았어도 제거했다. 제품 로직·카탈로그는 바꾸지 않아 앞선38개 단위시험 성공을 재사용했다.

원본 클라이언트 실행·화면 캡처는 하지 않았다. 새 마법창/단축키 입력·공식 효과/아이콘·광역 연출, 공식 피해/확률·동적 비용·쿨다운, NPC/언데드 회복·혈맹원 DEX 대상 등 명시한 LOCAL 범위 밖 동작은 원본으로 별도 확인해야 한다.

## 4차 구현·지정 검증

`world_magic_status.py`의 순수 상태를 기존 마법 기능에 연결했다. `npc_ai.NpcAi._act` 한 곳에서 선택적 `view.magic_status` 조회를 사용하며, 조회 훅이 없으면 기존 행동 경로를 쓴다. 마비는 이동·공격을 막고 슬로우는 두 행동의 실제 다음 실행시각을 늦춘다. PC의 이동·공격, NPC의 공격과 동료 피해에는 마법 기능이 있을 때만 인스턴스 연결을 설치하며 종료 때 원래 연결을 복원한다. 공용 코어에 필수 마법 호출이나 새 METHODS 이름 덮어쓰기를 추가하지 않았다.

기존 `magic.json` version1의 선택적 `statuses.effects`를 확장했다. 이전 저장을 읽으며 플레이어 효과는 오프라인 경과시간을 차감한다. 명상은 이전 프로세스의 monotonic `next_tick`을 저장하지 않고 복귀 후 새 회복 간격으로 시작한다. NPC 상태·잔여 MP는 EntityRef 수명에 속하고 재출현 개체로 넘기지 않는다. 무기 손상은 실제 장비 UID에 결속한 LOCAL 영구 상태이며 사망·재접속 뒤에도 보존한다. 순수 수리 API와 실제 수리 아이템/UI 경로는 구별한다.

HP·MP·촉매를 모두 확인한 뒤 기존 재고 owner/CAS로 촉매를 차감한다. 원래의 수량0 행은 보존하고 마지막 촉매 행을 소진하면 기존 책 소비와 같이 실제 UID의 수량0 anchor를 남긴다. 마력의 돌166의 raw 무게는 고정 [native dump](../../source_game_data/native-dump-v1.jsonl)1081행 item166.f10=2000, body SHA256 `b6fba5a867b549996dc64f7208733f7b53cd0c51cd52a5e27c1c4db6fd5c3e70`이며 보존 공식 표시 무게2와 대조했다. M1 정의가 없을 때만 이 명시 자료를 사용하고 미지 아이템을 무게0으로 처리하지 않는다.

모든 명령은 `SL_TEST_PORT_BASE=22000`으로 실행했다. `python -X utf8 -B -m tools.local_original_session.world_magic_tests` 최종 **55/55 OK**([로그](../runs/magic-fourth-tests-20261027-201004/world_magic_tests-catalyst-weight-fix.log)), `python -X utf8 -B -m tools.local_original_session.world_ai_tests` **19/19 OK**([로그](../runs/magic-fourth-tests-20261027-201004/world_ai_tests-close-fix.log)), `python -X utf8 -B -m tools.local_original_session.npc_ai_range_tests` **16/16 OK**([로그](../runs/magic-fourth-tests-20261027-201004/npc_ai_range_tests.log))다. 직접 함수 호출·가상 CAS·개발 상태 입력을 사용하는 단위시험은 실제 소켓 판정과 구분한다. 마지막 무게 조회 수정은 마법55개로 검증했고 변경이 없는 AI 경로의 성공은 재사용했다.

첫 단위시험의 마나 드레인 대상 거리 fixture 오류와 첫 AI 시험의 Context 종료 복원 오류는 [원로그 폴더](../runs/magic-fourth-tests-20261027-201004)에 보존했다. 첫 [소켓 실패](../runs/hunt-magic-ymhr1lzh/summary.json)는 입장 시 촉매166 무게 조회 KeyError로 종료했고 전체 cleanup_complete=false다. 내부 broker cleanup과 전체 시나리오 성공은 구분한다. 무게 수정 뒤 [두 번째 실패](../runs/hunt-magic-3pma84br/summary.json)는195개 중194개 성공 뒤 언데드 대상 장거리 이동의 `NAVIGATION_STALLED`로 멈췄다. cleanup_complete=true·소비 Source 변경[]이며 새11종 시전 성공으로 확대하지 않는다. 두 실패의 부분 저장·원문을 보존한다.

세 번째 [소켓 실패](../runs/hunt-magic-maqb4su5/summary.json)는 시험용 언데드가 기존 공격마법의 대상으로 선정되어 실제 처치·바닥 보상2개 생성 뒤 `KeyError`로 끝났다. 전체 cleanup_complete=false이며 성공으로 표시하지 않는다. 동일 언데드의 [짧은 정상 broker 진단](../runs/magic-kill-diagnostic-8axh2n9y/summary.json)은 로그인·학습·힐/공격·처치와 정상 정리까지 통과했으나 전체 시나리오 성공은 아니다. 정적으로 template27의 확률 드롭23/28이 `world_visibility.item_gfx()`에 없고 `ground_frame`이 해당 표를 직접 조회함을 확인했다. 원실패의 예외 인수·위치는 미확인이므로 이 누락과의 인과는 추정이며, 수정 범위 밖의 표시 결함을 보상 삭제·RNG 변경·예외 무시로 우회하지 않는다. 최종 시험은 기존27종 구간의 정상 Quit 뒤 새 상태 전용 접속 구간에서만 언데드 배치를 선언한다.

상태 전용 접속 구간을 분리한 [다음 실행](../runs/hunt-magic-499m7at5/summary.json)은197개 중196개 성공 뒤 `PLAYER_DIED:natural_mp_recovery_turn_undead`로 UNCONFIRMED다. 실제 턴 확률 실패·MP16→1 소비·버서크 뒤 NPC 앞 MP 대기 중 사망이며, 정상 상태 강제나 오류 은폐 없이 보존했다. 전체 cleanup_complete=true·소비 Source 변경[]이며 서버 예외는 없었다. 이후 봇의 정상 안전지대 자원 준비·후퇴·소유 물약 사용을 보완한다.

안전지대에서 최대MP까지 회복을 기다렸던 [대기 제한 결과](../runs/hunt-magic-pwbi_9x5/summary.json)는 `safe_status_resources_turn_undead`360초 제한으로 UNCONFIRMED다. cleanup_complete=true·소비 Source 변경[]이며 실패·소진 저장을 보존한다. WIS18의 현재 LOCAL 자연회복은3MP/16초라 잔량16에서 최대332까지360초 안에 회복할 수 없다. 최대MP 충전 선행을 제거하고, 기존27종 구간과 신규11종 구간에 별도의 명시 시험 프로필을 사용한다. 새 프로필도 같은 정상 성장 함수로 레벨30·최대 자원을 산출하고 FIRST→로그인→38종 책 학습→정상 회복/물약→실제 시전→저장/재접속을 거친다. 두 저장의 결과를 한 캐릭터의 연속 플레이로 합치지 않는다.

별도 [신규11종 소켓 진단](../runs/magic-status-development-gontjm7v/summary.json)에서 정상 턴 처치→보상→`_show_items`→`world_visibility.ground_frame:173`의 `item_gfx()[23]`에서 `KeyError(23)`가 발생하는 원예외를 확보했다. 따라서 바닥 표시 표의 누락은 정적 추정을 넘어 실제 실행으로 확인했다. 제품 밖 코드를 고치거나 드롭·RNG를 바꾸지 않고, 다음 시험의 로그인 전 배치에 기존 해골29/L1J45107과 그 전체 드롭 규칙을 선택했다. 해골29의 원래 드롭117/90/90/17/7에는 기존 표시 자료가 있다.

독립 프로필 분리 뒤 [기존 스탈락 대상 이동 실패](../runs/hunt-magic-5uuxv1q5/summary.json)는 `MAGIC_TARGET_OUT_OF_RANGE` 무소모 거절·응답 대기로 마감했고 cleanup_complete=true·소비 Source 변경[]다. 봇의 공통 대상 선정 순서를 실제 MP/HP·재사용 준비→현재 대상·사거리 여유 확인→요청으로 수정했다. [신규 구간의 기록 키 오류](../runs/magic-status-development-cc80i33t/summary.json)도 보존하고, 판정용 status와 효과 증거용 effect_state의 이름만 분리했다.

같은 제품 코드의 [신규11종 단독 소켓 검증](../runs/magic-status-development-ef0zkvfz/summary.json)은 **152/152 SUCCESS**,3개 접속 구간 정상 정리·cleanup_complete=true다. 정상 FIRST/로그인/38종 책 학습 뒤11종 실제 시전, 턴 실제 처치·EXP+101, 마나 드레인MP274→278·HP277→227, 마비 실제2.002초 동안 NPC 이동·공격0, 슬로우 상태 소비·리무브 커스 해제·HP/MP/촉매 소모, 명상 실제 회복·저장/재접속/만료와 카운터 만료를 확인했다. 이 단독 helper 실행은 아래 전체 `--scenario all`을 대체하지 않는다. 확률7종의 L1J/LOCAL 수식은 원본 서버 확률 검증이 아니며, 슬로우의 실제 이동·공격 deadline은 앞선 개발 AI 시험이 별도 근거다.

`SL_TEST_PORT_BASE=22000`에서 최종 `python -X utf8 -B -m tools.local_original_session.hunt_bot_magic --scenario all`은 **353/353 SUCCESS**다([최종 원결과](../runs/hunt-magic-fov74hht/summary.json)). 같은 고정 Source에서 총50회 시전으로 지원38개 key 전부를 확인했고,8개 접속 구간 모두 cleanup_complete=true·failure_code=null로 정상 마감했다. `source_sha256_start`와 `source_sha256`가 같고 실행 중 소비 Source 변경[]이다. 시험 담당의 마감 listener22000/24030은0이다.

이 전체 명령은 명시한 **독립 프로필2개**를 순차 실행했다. 기존27종은 첫 프로필의5개 접속 구간, 신규11종은 `status-profile`의3개 접속 구간이며 두 프로필 모두 정상 성장 함수로 만든 법사30이다. 각 프로필에서 정상 FIRST→로그인→선택→월드와 책 학습·시전·Quit/재접속을 통과했다. 시작 재고·HP/MP·38권 책·시험 촉매50개·해골29의 로그인 전 정상 스폰 선언은 원결과 `profile_fixtures`, 시전/접속 귀속은 각 `profile_path`가 정본이다. 서로 다른 저장의 성공을 한 캐릭터의 연속 플레이로 주장하지 않는다.

최종 전체 명령에서도 턴 실제 처치·EXP810016→810117, 마나MP274→278·HP263→213, 마비2.004초 동안 실제 NPC 이동·공격0, 슬로우 상태 소비·실제 리무브 커스 요청·촉매 수신/저장 차감, 명상 회복·정상 Quit 저장→재로그인 복원→실제 만료와 카운터 복원/만료를 확인했다. 카운터의 피격 마법1회 무효와 무반사는 단위시험 근거이며 이 소켓 실행의 카운터 확인은 시전·상태·저장·만료 범위다. 슬로우의 이동·공격 실행시각과 마비 후 행동 재개도 앞선 개발 AI 시험이 별도 근거다. 시험의 지속시간만 기존 설정10초를 사용했고 정상4/10/16/20/30/600초 데이터는 유지한다.

원본 클라이언트·캡처·사용자 저장·manual 프로필은 실행/변경하지 않았고 커밋하지 않았다. 이번 변경 파일은 `world_feature_magic.py`, `world_magic.py`, 새 `world_magic_status.py`, `npc_ai.py`, `world_magic_tests.py`, `hunt_bot_magic.py`, `data/m3/player_spells.json`과 이 문서다. `start-manual-play.ps1`의 기존 핀 대상은 변경하지 않아 핀 갱신은 없었다. Native 약점 표시/암흑 화면·아이콘·입력, 원본 확률식, 실제 수리 아이템 경로와 재고 grade2 저주 해제는 미확인/미구현 범위다. **아이템23/28 바닥 표시 누락은 이번 허용 파일 밖의 실제 잔여 결함**이며 최종 성공으로 지우지 않는다.
