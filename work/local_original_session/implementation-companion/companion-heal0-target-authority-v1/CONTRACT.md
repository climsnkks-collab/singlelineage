# COMPANION-MAGE Heal0 target/range/amount source audit

SOURCE_AUDIT_COMPLETE / CALLEE_NOT_SUPPLIED / test_ready:false / runtime:UNRUN.

**첫 미공급은 같은 current caster/selected-owner target을 받는 Heal0 `catalog(...)->in_range` producer의 range10 판정 계약이다.** 기존 source에는 정확한 두 binding/UID·수명 확인과 치료 resolver가 있다. 그러나 거리 metric·경계/단위·LOS/target opt-in을 공급하는 실제 catalog source는 이번 선정에 없다. 따라서 현재 파일에서는 호출 가능한 callee나 임시 범위 True를 만들지 않는다.

## 이미 있는 실제 접점

| 항목 | source와 확인한 내용 | 한계 |
|---|---|---|
| Heal0 cost/key | root의 `heal0-instant-source-integration-v1/root-review.json`, SKILL `heal_zero_rule.py`, companion consumer v3 | Rule0/MP4/HP0/순간의 source 접점은 수용됐다. 과거 catalog-v2의 "Rule0 없음"은 이 수용으로 대체됐다. 실제 learned0·mixed header·현재 row를 공급했다는 뜻은 아니다. |
| current selected owner target | `optional-target-v1/candidate/companion_shared.py:152,310,324,443` | `binding_for(active,'owner')`는 원 provider.bind_selected와 같은 owner character UID를 요구한다. `plan`은 발급 caster/target UID·generation을 재확인한다. 추가 target resolver를 만들 필요가 없다. 다만 실제 installed SharedSupport/공동 custody는 별도 실제 입력이다. |
| range 소비 | v3 `companion_support.py:457,513`, 기존 `companion_shared.py:478` | catalog가 반환한 `(spell_id, actor_uid)` in_range를 소비한다. 이 consumer 자체가 metric/LOS/현재 range producer는 아니다. |
| same caster stats | `companion-derived-stats-v2/companion_derived_stats.py`와 기존 SharedSupport heal branch | 같은 companion binding의 실제 저장 Gear/Inventory/SKILL/RESOURCE를 읽는 source가 있다. actual Gear/learned/custody를 생성하지 않고 lawful·RNG·HealingSpell을 공급하지 않는다. |
| heal amount 계산 | exact `combat-pve-serial386-v2/cohort/combat_magic.py:293,310` | 기존 `HealingSpell`+`resolve_heal`이 있다. SharedSupport가 실제 DerivedStats→MagicActor→resolver를 한 번 소비하며 HP owner가 죽은 대상 거부/maxHP clamp·원 공동 CAS를 맡는다. 새 치료 공식은 필요 없다. |
| 실제 owner HP 응답 | `optional-target-v1/candidate/companion_response.py:122` | `SelectedStatusSupportSource`가 같은 plan의 selected owner scalar heal 2개 Resource Operation·원4E38을 결속한다. companion-self/다른 추가 effect는 명시 거부한다. caster UID를 selected target으로 치환하지 않는다. |
| 기존 timed Buff response | exact `buff-multi-self-v1/source_response.py:152` | SourceResponseAdapter의 allowlist는 원 positive self-buff key만이며 원 event/action/time을 소비한다. Heal0 허용을 이유로 0을 이 allowlist에 넣거나 timed Buff로 변환하지 않는다. scalar heal에는 위 별도 기존 status 소비 경로가 있다. |

## 치료량 source의 구체적인 진전

실제 asset `spell_list.jsonc`와 CommonSpell join은 key0/힐/range10/MP4/순간만 알려 준다. CommonSpell0의 선정 raw fields는 모두 0이며 이를 피해계수로 읽지 않는다.

기존 `spellbook/book-full-catalog-v1/source-map.json`의 **template164 / key0 / 마법서(힐) / Spellbook(LesserHeal) / SQL skill1 LesserHeal** 명시 이름 조인을 찾았다. 숫자 offset을 추론하지 않았다. 기존 pinned `l1jdb_m10.sql`의 35621행과 33열 순서를 대조하면 `damage_dice=4`, `damage_value=2`, `damage_dice_count=0`이다. 실제 raw line/hash·전체 SQL hash·조인은 `source-facts.json`에 보존했다. SQL19 `Heal`은 별도 행이며 대신 쓰지 않는다.

이것은 기존 명시 `LOCAL_REFERENCE_L1J` 치료 resolver에 공급할 **reference coefficient 근거**다. 원 NC 공식 치료량·같은 current caster의 HealingSpell configuration 설치나 실행 성공이 아니다. 원 resolver는 `damage_value + min(10, actor.magic_bonus)`번 `randint(1,damage_dice)`를 합산하고 실제 actor lawful과 leverage로 계산한다. `damage_dice_count`를 그 반복 횟수로 대입하지 않는다. 현재 source에는 Heal0용 실제 configuration.healing/같은 caster RNG·lawful producer가 설치되지 않았다. SQL 행의 `lawful=0`은 actor lawful 값이 아니며 caster lawful0으로 대체하지 않는다. API의 기존 leverage 기본값10을 원 NC 계수로 주장하지 않는다.

SQL의 `ranged=-1`도 client UI range10의 metric·LOS가 아니다. 이 값을 UI 거리나 무제한 지원으로 쓰지 않는다.

## 다음 하나의 source 계약

기존 SharedSupportConfiguration.catalog에 전달할 구체 source가 필요하다. 원 호출 서명 `catalog(active, actor_binding, owner_binding, frame, now)`을 그대로 쓰며, 현재 installed Heal0 admission/같은 cost Rule와 정당 learned0을 소비하고 같은 active/caster/selected-owner binding·현재 server map/grid를 판정해야 한다. 거리 metric·단위·경계/LOS·허용 대상 정책을 정확한 source 또는 명시 승인 LOCAL 정책으로 공급해야 한다. raw UI range10만으로 Chebyshev/Manhattan/Euclidean·고정 True를 선택하지 않는다. 서버 좌표 정책이 공급되면 native pose를 별도 선행조건으로 늘리지 않는다.

해당 source 뒤에도 실제 HealingSpell0 설정·같은 caster lawful/RNG, 원 same aggregate 공동 custody/RESOURCE+SKILL CAS·정상 learned0/header가 필요하다. 기존 ITEM/SKILL 소유 producer를 복제하거나 다른 캐릭터의 stats·RESOURCE를 대입하지 않는다. 기존 selected-owner binding/status response를 새 target/packet wrapper로 재구현하지 않는다.

새 callee 작성은 모든 입력이 source로 결속됐을 때만 허용된 이번 배정 조건을 따랐다. range producer가 없으므로 계약/핀만 마감했다. runtime/packet/handler/port/native/REA·Store 쓰기·학습 grant·공용API·기존 source 변경은 0이다. 소유 파일은 이 새 private 디렉터리뿐이다.
