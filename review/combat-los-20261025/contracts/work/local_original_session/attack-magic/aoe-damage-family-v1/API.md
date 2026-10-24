# 공격 범위 피해: 고정 참고 descriptor와 현재 NPC 후보만

현재 client의 직접 피해 중 고정 L1J `103e6f6c`에서 `area>0`인 **9개**를 불변 `AreaDamage` tuple로 제공한다. FrozenCloud21은 별도 이름 bridge를 명시 소비한다. 일반 catalog의 미확정 행을 덮어쓰지 않았다. `reference-facts.json`에는 UI와 SQL 원값을 분리 보존한다.

|현재 logical|참고 L1J|참고 중심|range/area|참고 MP/HP|dice/count/base/attr|
|---|---|---|---|---|---|
|21|22 FrostCloud|대상 actor|6/3|20/0|4/8/0/4|
|24|25 Fireball|대상 actor|6/3|20/0|9/5/0/2|
|29|30 EarthJail|대상 actor|6/2|24/0|8/5/0/1|
|52|53 Tornado|시전자|0/4|40/0|10/5/20/8|
|58|59 Blizzard|시전자|0/10|60/10|10/3/3/4|
|61|62 Earthquake|시전자|0/3|40/0|10/6/40/1|
|64|65 LightningStorm|대상 actor|10/3|48/0|10/5/25/8|
|69|70 FireStorm|시전자|0/3|48/0|15/8/30/2|
|73|74 MeteorStrike|대상 actor|10/3|60/0|15/8/50/2|

모두 참고 SQL `target_to=3(PC|NPC)`, `through=0`, type64, 소모재0, duration0이다. 이 구현의 방향은 PC→NPC뿐이다. 비용·reuseDelay·원소·피해 숫자는 참고 자료이며 실제 InstantRule 또는 native 서버 비용/공식이 아니다. 예를 들어 Fireball UI MP16·주변2칸과 SQL MP20·area3, Tornado UI MP45·3칸과 SQL MP40·area4, Blizzard SQL HP10을 혼합하지 않는다. FrozenCloud UI target=location도 NPC actor 중심과 같다고 추정하지 않는다.

`area_descriptors.describe(logical_id)`와 `damage_parameters(logical_id)`는 데이터만 반환한다. Lightning16은 SQL area0이지만 `L1SkillUse.java:887–909`의 선형 별도 분기이므로 이 family에 넣지 않는다. FogOfSleeping65는 area3이지만 상태 type4라 제외했다. IceLance49도 area0이다. 피해 산술 자체는 기존 `combat_magic.py e6ed0e76`의 PC_NPC 함수를 재사용할 수 있으나 이 모듈은 RNG 실행·피해 배분·HP 변경을 하지 않는다.

원 `L1SkillUse.java:292–295`는 target=none에서 대상 ID/위치를 시전자로 바꾼다. `:870–879`는 대상과 map 일치 및 `getTileLineDistance<=ranged`를 검사한다. `:928–970`은 attack 중심 대상을 추가하고 `getVisibleObjects(_target,area)`를 순회하며 `isTarget`을 적용한다. `:739–745`는 through=false에서 실제 glanceCheck를 요구한다. SQL area 숫자만으로 정사각형·원·맨해튼 거리나 완전한 수신자 집합을 정하지 않았다. `isTarget`에는 숨김·죽음·소유 동료 등의 별도 조건이 있다.

## 현재 후보 API의 좁은 안전 범위

`await current_candidates.enumerate_current_candidates(context)`는 **이미 발급·승인된 같은 `HostileCastContext`**를 받는다. 최종 선정 graph의 정확 canonical `combat_hostile_cast.HostileCastContext`, `attack.AttackTargets/BoundTarget`, `npc.NpcSpawn` 타입을 요구하며 duck-typed 외부 입력을 런타임에서 받아들이지 않는다. 이 파일은 다른 graph에 자동 설치되지 않는다.

같은 실제 realm의 `_npc_spawns` 최대64행만 읽고 현재 발급 NPC UID를 기존 `AttackTargets.authorize`에 넘긴다. 이것은 송신하지 않는 원 source authority API 재사용이며 물리 Attack packet/acceptance를 만들지 않는다. 좌표는 request에서 주입하지 않고 원 authority의 issued frame·실 current motion/map에서 얻는다. 기존 primary BoundTarget을 그대로 보존한다. 같은 writer·시전자 Position identity·operation row·lock/current를 context와 기존 revalidate가 검사하며 매 await 뒤 모든 이전 후보를 다시 확인한다. 중복 UID, 바뀐 발급 roster, 소유권/현재값 변화는 전체 후보 읽기를 거부한다. map이 다른 발급 NPC는 후보에서 제외한다. 읽기 실패 시 비용/HP/Store 변경이나 재시도가 없다.

반환 `CurrentNpcCandidates.bounds`는 **멀리 있는 NPC도 포함하는 같은 map의 현재 후보**다. 범위 적중·수신자·cast 선택 권한이 아니다. `require_damage_selection()`은 현재성을 다시 검사한 뒤 항상 `AOE_SAME_CAST_AREA_GEOMETRY_ELIGIBILITY_LOS_SOURCE_UNRESOLVED`로 거부한다. 시전자 중심4종은 기존 NPC primary context로 source cast를 발명할 수 없으며 별도 실제 self/around 시전 admission이 필요하다. FrozenCloud location→actor 선택도 실제 현재 ingress 계약이 필요하다.

첫 미완 계약은 같은 시전의 area geometry/visible-object enumeration·NPC eligibility·projectile/door LOS다. 그 다음에 실제 family admission/Instant 비용·선정 graph, 실제 피해별 현재 HP와 다중 HP/비용 단일 transaction·부분 보존/죽음 once·정상 응답 배송이 필요하다. 후보를 순서대로 단일 NPC HP API에 commit해 동시 다중 HP 성공으로 표시하지 않는다. 기존 치사 worker·LOCAL 상태 응답·direct graph 파일을 수정하지 않았다.

확인: `python -B work/local_original_session/attack-magic/aoe-damage-family-v1/check_family.py`.
12 focused 검사는 9 descriptor·source pins와 **controlled unit authority**의 동일 cast/현재 map·stale/await·roster 변경/중복/64한계·무조건 selection 거부만 확인한다. 실제 retained reader/native owner·current actor 발급/계정·학습·server·packet·Store·Test 실행0이다.

`RUN_COMMAND:null`, `test_ready:false`, `runtime_ready:false`. 모든 새 파일은 이 폴더에만 있고 공용/client/큐/HANDOFF writer는 사용하지 않았다. source 작성·검사 마감 뒤 worker writer/실자원 해제.
