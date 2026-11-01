# 4속성 저항 근거와 구현 경계

2026-10-28 조사·국소 구현. 원문 확인, 개발시험, 자연 전투 연결의 범위를 구분한다.

## 결론

공식 자료는 불·물·바람·땅 저항의 존재와 장비/버프의 수치까지 확인한다. **피해 환산식·총저항 상하한·MR과의 연산 순서를 공식 규칙으로 확정할 자료는 찾지 못했다.** 아래 L1J 계산을 채택하거나 현 Python 피해식에 맞게 변형하면 `local_policy`다. 공식 수치의 출처와 backend 계산 정책의 출처를 따로 남긴다.

참고 소스 루트는 `D:/SingleLineageRef/l1j-en-classic/src/l1j/server/server/`다. 아래 Java 위치는 이 루트 기준이다. L1J의 수치·ID·버전은 고정 원본 클라이언트의 내부 규칙을 입증하지 않는다.

## L1J 실제 계산과 생산자

| 계약 | 확인 위치 | 실제 동작 |
|---|---|---|
| 속성 코드 | `model/Element.java:8–12` | None=0, Earth=1, Fire=2, Water=4, Wind=8. 4속성 이외 값은 아래 함수에서 R=0이다. |
| 저항 누적/상하한 | `model/L1Character.java:763–808` | 각 `_true{Wind,Water,Fire,Earth}`에 가감 후 getter용 값을 **-128..127**로 제한한다. L1PcInstance가 상속한다. 계산 함수 안의 clamp 유무와 구별해야 한다. |
| 장비→누적 | `model/L1EquipmentSlot.java:103–106`, `181–184` | 착용 때 아이템 기본 저항+인스턴스 저항을 가산하고 해제 때 같은 양을 차감한다. 네 속성 독립이다. |
| 저항 선택/환산 | `model/L1Magic.java:763–783` | PC_PC 또는 NPC_PC 때만 주문 속성과 같은 PC 저항을 읽는다. NPC 대상은 이 함수의 R=0이다. `A=sign(R)*int(0.32*abs(R))/32.0`. int는 소수부를 버린다. 함수 자체에는 추가 clamp가 없다. |
| 일반 마법 피해 | `model/L1Magic.java:659–688` | 주사위 합+기본값(+PC 무기 마법피해)을 `max(1-A+I*3/32,0)`에 곱한다. `I=max(attacker.INT+itemSP-12,1)`이며 상수12는 `:117`이다. Java `int *= double`이므로 이 단계 결과는 정수로 절삭된다. |
| NPC 약점 | `model/L1Magic.java:690–697`, `:122` | PC_NPC 때 주문 속성이 NPC weakAttr와 정확히 일치하면 추가 ×1.2다. 이것은 PC 장비 속성저항과 별도 정책이다. |
| MR 적용 시점 | `model/L1Magic.java:389–396` | 일반 피해 계산 다음 `calcMrDefense`를 거친다. JOY_OF_PAIN은 MR 예외다. |
| PC 시전자 MR | `model/L1Magic.java:738–754` | MR≤100이면 `F=trunc0((MR-originalMagicHit)/2)`, 배율 `1-0.01*F`; MR>100이면 `F=trunc0((MR-originalMagicHit)/10)`, 배율 `0.6-0.01*F`. Java 정수 나눗셈이 `Math.floor` 이전에 실행된다. 여기에는 배율 상하한 clamp가 없다. |
| NPC 시전자 MR | `model/L1Magic.java:755–758` | 1..100 난수≤대상 MR이면 정수 피해를 절반으로 나눈다. MR50은 매번75% 피해가 아니라 50% 확률의 절반 피해다. MR≥100은 매번 절반이다. |
| MR 생산/일시효과 | `model/L1Character.java:941–958` | addMr 결과는 최저0·명시 상한 없음. getMr는 ERASE_MAGIC 중 /4를 반환한다. 속성저항 getter와 독립이다. |
| PC 기본 MR | `model/Instance/L1PcInstance.java:2546–2549` | 직업 기본MR+WIS MR+level/2를 기본MR로 반영한다. 속성저항을 MR에 합치지 않는다. |
| Fire Wall 별도식 | `model/L1Magic.java:404–413` | `max(int((1-A_fire)*firewall.damageValue),0)` 및 무적 검사를 사용한다. 이 함수 자체는 MR을 부르지 않는다. 일반 마법 계수와 동일하게 취급하지 않는다. |
| 물리 무기 속성강화 | `model/L1Attack.java:1153–1177` | 설정 활성+강화1 이상일 때 별도 추가피해 `(2*강화단계-1)*(1-R/100)`을 절삭한다. PC_PC의 해당 저항 또는 PC_NPC 약점 -50을 쓴다. 일반 마법의 0.32/32 계단식과 다르다. |

환산 A는 R=10→0.09375, 20→0.1875, 50→0.5, 100→1.0, 127→1.25, -50→-0.5, -128→-1.25다. **R100이 모든 일반 마법을 완전 무효화한다는 뜻은 아니다.** 일반식에는 INT/SP 항이 더해지며, 전체 피해에 단순 `(1-A)`를 곱하는 구현은 L1J 일반식 자체가 아니다. 기존 Python의 완성 피해에 그 배율을 추가할 경우 변형 계산이라는 `local_policy` 표시가 필요하다. 음수 저항은 피해를 증가시킨다.

PC 대상 일반 피해 경로는 `calcPcMagicDamage`이며 `:498–500`에서 음수 피해를0으로 만든다. FINAL_BURN/JOY_OF_PAIN의 대체 피해는 `:502–512`에 있어 일반 주사위·속성식과 구별한다. 모든 마법에 한 식을 강제로 적용할 근거로 사용하지 않는다.

## 몬스터 공격의 속성 경로

- `model/L1Attack.java:943–1037`의 NPC→PC 일반 물리는 레벨/STR/공격력·방어·피해감소·버프 등을 사용하며 네 속성저항 getter나 MR을 읽지 않는다. 몬스터 이름·지역·외형·자기 약점을 이유로 일반 물리 전량에 속성을 부여할 근거는 없다.
- `model/L1MobSkillUse.java:232–250`은 mobskill의 skillId를 읽어 L1SkillUse로 보낸다. `model/skill/L1SkillUse.java:1633–1634`가 시전자/대상으로 L1Magic을 만들고 `:1679`가 calcMagicDamage(skillId)를 호출한다. `templates/L1Skill.java:299`에서 DB attr를 읽고 `:172–173` getter를 통해 `L1Magic:684`에 전달한다. **공격에 실제 지정된 주문의 attr가 속성 피해 생산자다.**
- 몬스터 template의 weakAttr는 맞을 때의 약점이며 몬스터 일반공격의 속성 태그가 아니다. NPC 공격주문과 NPC 일반 물리는 따로 소비해야 한다.
- `db/l1jdb_m10.sql:19833`의 Beagle→Stalac, `:19937` Fang of Earth→Stalac 같은 실제 mobskill 행이 존재하지만, 이것을 고정 원본의 동일 몬스터·동일 주문 보유 증명으로 확장하지 않는다.

L1J SQL의 주문 번호와 공식/native 번호가 다르다. 예를 들어 L1J EBolt4/Teleport5/WindShuriken7/Stalac16이며 공식 Teleport4/Wind Cutter6/Stalac15다. **숫자를 그대로 이식하지 말고 기존 고정 이름 대응을 재사용한다.** 참고 SQL은 `D:/SingleLineageRef/l1j-en-classic/db/l1jdb_m10.sql`이다.

| L1J 주문 | L1J ID | attr | SQL 줄 |
|---|---:|---:|---:|
| EBolt | 4 | 16(네 속성저항 미사용) | 35624 |
| IceDagger | 6 | 4(물) | 35626 |
| WindShuriken | 7 | 8(바람) | 35627 |
| FireArrow | 15 | 2(불) | 35635 |
| Stalac | 16 | 1(땅) | 35636 |
| Lightning | 17 | 8(바람) | 35637 |
| FrostCloud | 22 | 4(물) | 35642 |
| Fireball | 25 | 2(불) | 35645 |
| EarthJail | 30 | 1(땅) | 35650 |
| CallLightning | 34 | 8(바람) | 35654 |
| ConeOfCold | 38 | 4(물) | 35658 |
| Eruption | 45 | 1(땅) | 35665 |
| SunBurst | 46 | 2(불) | 35666 |
| IceLance | 50 | 4(물) | 35670 |
| Firewall | 58 | 2(불) | 35678 |
| LightningStorm | 65 | 8(바람) | 35685 |
| MeteorStrike | 74 | 2(불) | 35694 |
| Destroy | 77 | 16(네 속성저항 미사용) | 35697 |

이 표도 L1J 참고 정책이다. 공식 주문명/설명의 바람·얼음·바위 표현은 대응 검토에 쓸 수 있지만 모든 공격의 수치 attr를 공식으로 확인한 표가 아니다.

## 공식 근거와 재사용 자료

기존 `tools/local_original_session/data/official/items.json`(610행), `spells.json`(110행), 각 행 source가 가리키는 `work/official_data/raw/{item,spell}/{id}.json`을 재사용했다. 표의 줄은 official 테이블의 해당 행 시작이다.

| 공식 장비 | ID / local 줄 | 확인된 속성저항 |
|---|---|---|
| 수룡/지룡/화룡/풍룡 비늘 갑옷 | 403/83589, 404/83896, 405/84203, 406/84510 | 각각 물/땅/불/바람 +20 |
| 화령/수령/지령/풍령의 반지 | 498/88221, 499/88509, 500/88797, 501/89085 | 각각 불/물/땅/바람 +10 |
| 불/물/땅/바람 정령의 벨트 | 3934/155903, 3935/156217, 3936/156531, 3937/156845 | 각각 해당 속성 +10 |

속성저항 옵션을 가진 공식 item은 총18행이다. 위12행 외 맘보코트1286(물+10/불-10), 장갑1288–1291(각 속성+4), 기타12557(땅+5)가 있다. 1286/1288–1291은 기존 고정 native 대응이 null이며, 일반 장비로 새로 생성하지 않는다. 음수 옵션 원문이 실제 존재한다는 점은 확인되나 현재 원본 장비 수용 범위를 확장하지 않는다.

기존 `data/m1/items_ext/accessories.json`의 반지4/벨트4행에는 typed `resist_fire/water/earth/wind` +10이 이미 있다(줄1970/2133/2296/2459/6657/6833/7008/7185). `items_ext/armor.json`의 비늘갑옷4행은 +20 옵션이 note에만 보존돼 있다(줄4675/4755/4835/4915). 기존 [ITEMS_ARMOR_EXT](ITEMS_ARMOR_EXT.md)의 미지원 설명을 이번 실제 소비 구현 범위에 맞춰 구별해야 한다.

공식 주문137 레지스트 엘리멘트는 전속성+10, 1200초이고 공식 테이블 줄14388부터다. 주문146 프로텍션 프롬 엘리멘트는 선택한 자기 속성+50, 1200초이고 줄14922부터다. `L1SkillUse.java:2762–2765`, `:2784–2790`에도 같은 가산 구조가 있지만 버프 확대 자체는 이번 조사 결과만으로 구현 완료가 아니다.

2026-10-28 웹 확인:

- [공식 화령의 반지 API](https://api-goats.plaync.com/linclassic/v2.0/game/item/498?locale=ko-KR), [공식 화룡 비늘 갑옷 API](https://api-goats.plaync.com/linclassic/v2.0/game/item/405?locale=ko-KR): 직접 GET 200, 저장된 원문의 +10/+20 옵션과 일치했다.
- [공식 레지스트 엘리멘트 API](https://api-goats.plaync.com/linclassic/v2.0/game/spell/137?locale=ko-KR), [공식 프로텍션 프롬 엘리멘트 API](https://api-goats.plaync.com/linclassic/v2.0/game/spell/146?locale=ko-KR): 직접 GET 200, +10/+50·지속시간 설명과 일치했다. 네 API에는 피해식·합산 상하한·MR 결합 공식이 없다.
- [공식 윈드 커터 API](https://api-goats.plaync.com/linclassic/v2.0/game/spell/6?locale=ko-KR), [공식 스탈락 API](https://api-goats.plaync.com/linclassic/v2.0/game/spell/15?locale=ko-KR): 직접 GET 200. 바람/바위의 공격 설명은 있으나 numeric attr와 피해식은 제공하지 않는다.
- [공식 메뉴/UI 가이드](https://lineageclassic.plaync.com/zh-tw/guidebook/view?title=%E9%81%B8%E5%96%AE%E5%8F%8AUI%E4%BB%8B%E7%B4%B9)는 캐릭터 창에 땅/불/물/바람 저항과 MR 표시가 따로 있음을 설명한다. [공식 방어구 가이드](https://lineageclassic.plaync.com/zh-tw/guidebook/view?title=%E9%98%B2%E5%85%B7)는 MR 증가가 마법 피해/일부 확률마법에 영향을 준다는 정성 설명까지만 제공한다. 수식 근거는 아니다.
- 한국어 동일 가이드 URL은 검색/열기에서 SPA shell만 반환했고 API를 web 도구로 열 때도 접근 오류가 났다. API 직접 HTTP는 정상200이었다. 도구 접근 오류를 공식 자료 부재나 제품 실패로 표시하지 않는다. 게시판 이용자 글은 공식 계산 근거에서 제외했다.

## 첫 조사 단계의 구현·시험 범위 (후속 마감 전 기록)

첫 조사 시점의 구현 범위는 `NpcMagicAttack`와 `WorldCombat.npc_magic_swing(monster, uid, attack)`의 HP 소비, PC/동료 profile의 저항 제공 경로였다. 당시 자연 공격 정의는 물리뿐이고 주문 선택 생산자는 없었다. **이후 완료한 NPC 생산자 연결은 아래 ‘자연 NPC 생산자 마감’의 소스·범위·실행 결과를 따른다.** 앞의 조사와 개발시험을 자연 공격 연결의 근거로 소급하지 않는다.

현재 조사로 확정한 것은 원문·파일 연결이다. 구현 담당은 실제 채택한 합산·상하한·피해식·반올림과 MR 선후관계를 `local_policy`로 명시하고, 네 속성 이외/물리/정의 없는 공격이 그대로인지 확인한다. 저항의 생산자는 실제 착용 장비/활성 버프이며, 저장에는 기존 인벤토리·장비·버프 소유 수명을 유지하고 파생 저항을 별도 저장해 중복 가산하지 않는다.

원본 클라이언트의 속성 표시 패킷·네이티브 소비·피해 체감, 실제 몬스터 주문과 매핑, 장착/해제/재접속의 최종 연결은 이번 문서 조사에서 시험하지 않았다. 단위 계산·개발 fixture의 성공을 원본 화면·정상 패킷·저장 복원 전체 PASS로 확대하지 않는다. 게임·서버·포트·클라이언트·사용자 저장은 실행/변경하지 않았다.

## 채택 구현과 검증 결과

- 변경: `tools/local_original_session/world_stats.py`, `world_core_stats.py`, `world_combat.py`; 신규 개발시험 `element_resist_tests.py`. `world_magic.py`, 동료 모듈, 원본, 저장 형식은 변경하지 않았다. 현 manual-play 시작 스크립트의 핀 목록에 이 변경 파일은 없다.
- `StatModifiers` → `CalculatedStats`에서 장비의 typed `resist_earth/fire/water/wind`를 다른 기여와 합산한 뒤 -128..127로 제한한다. PC 코어와 동료 공통 profile 투영은 각각 자기 선택 장비의 MR·저항을 사용한다. 파생 저항을 별도 저장하지 않는다. note에만 있는 비늘갑옷 저항의 typed 데이터 확장은 이번 허용 범위 밖이다.
- 일반 주사위 마법의 local_policy: `D0=damage_value+Σd(damage_dice)`, `R=해당 공격속성의 실효 저항`, `A=sign(R)*int(.32*abs(R))/32`, `D1=int(D0*max(1-A+max(INT+itemSP-12,1)*3/32,0))`. 속성은 formula.parameters.element_attr_raw의 1/2/4/8만 선택한다. 0/16/그 외 값의 A는 0이다.
- NPC 시전자는 D1에 대해 별도 1..100 난수≤MR이면 정수 절반, 아니면 그대로다. 기존 PC 시전자 경로는 저항 뒤 기존 치명타·MR 배율을 유지한다. 최종 음수 피해는 0이다. 일반 물리 피해는 저항·MR의 영향을 받지 않는다. Firewall/특수 고정피해/무기 속성강화는 이 일반식의 적용 완료 범위가 아니다.
- `NpcMagicAttack(parameters, intelligence, item_sp=0)`와 `WorldCombat.npc_magic_swing(monster, uid, attack)`는 명시된 공격을 계산해 기존 PC HP·상태·사망 소비자에 반영한다. 물리용 npc_swing을 감싸는 선택 magic 기능을 활성화한 경우에도 이 명시 진입점이 동작함을 개발시험했다. NPC 선택·MP·재사용·이펙트·시전 생산자를 새로 만들지는 않았다. 동료는 자기 저항 profile과 공통 계산까지 검증했으며 동료 실제 마법피격 HP 소비는 미연결이다.

최종 명령(포트 없는 개발시험):

```powershell
python -X utf8 -B -m unittest tools.local_original_session.element_resist_tests tools.local_original_session.world_stats_tests tools.local_original_session.world_magic_tests.WorldConsumerTests tools.local_original_session.world_companion_equipment_tests tools.local_original_session.world_companion_magic_tests tools.local_original_session.world_combat_requests_tests tools.local_original_session.world_tests tools.local_original_session.world_decoupling_tests tools.local_original_session.accessory_runtime_tests
```

결과: **110 tests / 22.243s / OK**, 신규 속성저항 11개 포함. 실제 player_spells.json의 earth15/fire14/water5/wind6 formula parameters를 그대로 사용한 저항 유무 비교, 장비 합산·해제·상하한, PC/동료 자기 장비, 음수·무속성·타속성, MR 경계, 물리 불변, 실제 PC HP/status/death 및 선택 magic wrapper 활성 구성을 포함한다. 예시 D0=100/INT12/MR0의 불 저항 0/50/100은 피해 109/59/9다. 함수 직접 호출의 개발시험이며 정상 로그인·패킷·자연 공격의 정식 PASS가 아니다.

원문: `work/local_original_session/runs/element_resist_final_20261028_123954_493.log`. 초회 신규시험 itemSP4 기대값96 오류는 수식상87로 수정했고 실패 원문 `element_resist_new_20261028_123845_249.log`를 보존했다. 변경 전 baseline의 전체 world_magic_tests는 기존 catalog 확장과 맞지 않는 RulesTests 두 메서드에서 42개 실패를 보였다(신규 key86..174 및 unsupported/class 오류 기대 차이). `element_resist_baseline_20261028.log`를 보존하고 해당 기대값·제품 코드는 수정하지 않았다. 최종 명령은 이 두 메서드를 제외한 실제 WorldConsumerTests를 포함한다. 전체 world_magic_tests 회귀 통과라고 주장하지 않는다.

첫 단계에서 요청받은 `SL_TEST_PORT_BASE=66000`은 TCP 최대65535 및 기존 시험기 허용 최대63505를 넘어 당시 소켓·10배 봇 회귀를 실행하지 않았다. 포트 제한을 변경하거나 임의 포트로 대체하지 않았고, 그 시점에는 범위 확대·유효 포트 답변 대기였다. **후속 지시로 NPC→PC 및36000을 승인받아 아래에 실행 결과를 남겼으며 현재 대기 상태가 아니다.** 동료 마법피격은 이번 후속 범위 밖이다. 원본 화면·입력·저항 표시·피해 체감은 원본으로 별도 확인해야 한다.

## 자연 NPC 생산자 마감 (2026-10-28 후속 승인)

후속 사용자 지시로 **NPC 생산자·PC 실제 피격 및 포트36000**을 진행했다. 위66000 대기는 이 범위에 더 이상 적용하지 않는다. 동료 마법피격·원본 클라이언트 실행은 이번 범위 밖이다.

변경 파일은 `tools/local_original_session/game_data.py`, `data/m1/npc_magic_attacks.json`(신규), `world_feature_magic.py`, `world_combat.py`, `world_magic_tests.py`, `element_resist_tests.py`, `hunt_bot_element_resist.py`(신규)와 이 문서다. 저장 형식·원본·동료 모듈·manual-user-play·manual-test-knight·ACTIVE_TASK·시작 스크립트는 수정하지 않았다. 기존 시작 스크립트의 이 파일들에 대한 직접 핀은 없어 핀 갱신도 없다.

- 식별은 기존 fixed client와 official monster 대응을 사용한다. 공식 monster 원문은 이름/level/region/rewards 등만 제공하며 numeric 주문/속성 공격 필드는 없다. 해당 client dump 행의 named_attributes/display_tokens에도 typed 주문 목록은 없다. 미해석 client 필드를 ‘공격 데이터가 전혀 없다’는 증명으로 확장하지 않는다.
- 빈칸은 `D:/SingleLineageRef/l1j-en-classic/db/l1jdb_m10.sql`의 실제 mobskill→skills와 npc.INT로 채웠다. 11개 생산자는 비글(Stalac/땅), 오크마법사(Fireball/불), 장로(CallLightning/바람), 다크엘프(Tornado/바람), 네크로맨서·세마(Lightning/바람), 발터자르·바포메트(Eruption/땅), 카스파(Fireball/불), 커츠(Earthquake/땅), 데스나이트(VampiricTouch/물)다. 각 행에 실제 SQL 3곳의 줄 번호를 남겼다. 기존 spell formula의 `l1j_skills:<줄>` 대응이 있는 경우만 classic_key를 재사용하며 ID를 산술 변환하지 않았다. 값 전체는 **local_policy**이고 고정 원본의 동일 몬스터 주문 보유 증명은 아니다.
- `game_data.load_npc_spells()`는 선택 magic 초기화 때 한 번 읽는 immutable 생산자표다. magic의 기존 npc_attack/npc_swing 인스턴스 wrapper에서 현재 EntityRef·기존 AI 공격 기회로 주문 확률을 선택한다. MP 부족·재사용·정의 없음·확률 탈락은 기존 물리 경로다. weakAttr는 읽지 않는다. 주문 MP/reuse는 기존 magic.npc_statuses의 EntityRef 수명 안에 있고 소멸·세대 교체·종료 때 기존 정리가 제거한다. NPC MP 재생은 이번 범위에 넣지 않았다.
- 선택된 주문만 `npc_magic_swing`으로 보내 실제 PC 장비 저항·MR과 기존 HP/status/death 소비자를 사용한다. 기존 물리 weapon_break wrapper와 혼합하지 않는다. mobskill Leverage가0이면10을 쓰고 `D2=int(D1*Leverage/10)` 다음 NPC MR 난수 절반을 적용한다(`L1Magic.java:418`, `:389–396`). VampiricTouch는 실제로 제거한 PC HP만큼 NPC slot HP를 maxHP까지 회복한다. Counter Magic 흡수 때도 시도 MP/reuse는 소비한다.
- 기존 코어의 공격거리·LOS·추격·공격 기회 간격을 유지하며 별도 최소 시전 재사용은 source atk_magic_speed/reuseDelay다. 현 AoE 주문은 선택된 PC 한 명을 소비한다. **전체 원본 주문거리·AoE·고유 주문 애니메이션·NPC MP 재생을 복원 완료로 표시하지 않는다.** 전투 통지는 기존 NPC 피격 프레임을 재사용하며 원본 주문 이펙트/네이티브 소비는 미확인이다. 특수/비피해 mobskill은 전량 속성 태그를 붙이지 않고 기본 물리를 유지한다.

기존 `world_magic_tests`의 42개 실패는 catalog 확장 뒤 오래된 기대였다. 첫 메서드는 전체 catalog가5단계39행뿐이라는 기대를 기존5단계 포함+명시 지원집합 유지로 갱신했다. unsupported 시험41개는 elf/royal 주문도 mage3으로 `admit_cast`하여 먼저 `CLASS_NOT_ALLOWED`를 받던 문제였다. 해당 주문의 선언된 직업으로 호출해 `EFFECT_UNSUPPORTED`와 무소비를 확인한다. 제품 허용/거부 순서를 바꾸지 않았다. 최초 실패 원문과 이번 수정 전 실패 로그 `element_resist_producer_unit_20261028_124703.log`는 보존했다.

포트 없는 최종 관련 회귀:

```powershell
python -X utf8 -B -m unittest tools.local_original_session.world_magic_tests tools.local_original_session.element_resist_tests tools.local_original_session.game_data_tests tools.local_original_session.world_stats_tests tools.local_original_session.world_combat_requests_tests tools.local_original_session.world_tests
```

**105 tests / 18.597s / OK**. 원문 `work/local_original_session/runs/element_resist_finish_scoped_20261028_125247.log`. 이후 magic 제거 기본물리 시험을 한 개 추가하여 `python -X utf8 -B -m unittest tools.local_original_session.element_resist_tests`는 **14 tests / 3.434s / OK**, 원문 `element_resist_optional_removal_20261028_125333.log`다. `test_ordinary_npc_melee_is_unchanged_by_resistance_and_mr`는 물리 불변, `test_removing_optional_magic_restores_sourced_npc_basic_physical_swing`는 source 주문이 있는 장로도 magic 제거 뒤 기존 class npc_swing·물리 피해로 돌아감을 확인했다. 네 속성 source 선택·실제 HP·MP·reuse·drain·Leverage 및 기존 player magic 전체 회귀가 포함된다. 함수/개발 fixture 시험이다.

넓힌 기존 회귀의 별도 제한도 보존한다. `element_resist_producer_unit_20261028_124915.log`는97개 중 범위 밖 `world_decoupling_tests`의 `world_feature_companion_bridge.py:235 companion_signals` AST 선언 추출 NameError1개다. `element_resist_finish_regression_20261028_125134.log`는111개 중 범위 밖 `accessory_runtime_tests.py:195`의 unsupported maxHP 기대와 현재 max_hp_bonus30 불일치1개다. 이 두 파일을 수정하지 않았고 전체 회귀 통과로 표시하지 않는다.

자연 피격 소켓 명령:

```powershell
$env:SL_TEST_TIME_SCALE='10'; $env:SL_TEST_PORT_BASE='36000'
python -X utf8 -B C:/Users/Chansol/AppData/Local/Temp/claude/D--claude/0483de89-75e7-4b94-84b8-fb31fe00f575/scratchpad/fastbot/run_fast.py hunt_bot_element_resist
```

**PASS, 21 checks, 2 epochs, cleanup_complete=true**. 원결과 `work/local_original_session/runs/element-natural-l9aiyomr/result.json`, 요청 `requests.jsonl`, 로그 `element_resist_natural_20261028_125102.log`. 실행은 기존 Matrix의 fresh Lv30·장로 지역 시작 저장 및 바람반지501/벨트3937 지급 fixture, source-layout RAM peer를 사용했다. 사용자 저장/원본 프로세스는 사용하지 않았다. 결과의 source_sha256에 실제 소스 조합과 생산자표를 남겼다. FIRST→정상 로그인→캐릭터 선택→월드→인벤토리 전달 후, 받은 NPC UID로 실제 공격 패킷을 보내 장로의 자연 반격을 유발했다. 이후 실제0960 장착/저장/SC097A→재접속 저항20 유지→0960 해제/저항0→다시 자연 피격 순서다. 직접 핸들러 호출·HP/준비 강제·NPC/난수 조작은 없다.

장로 CallLightning에서 저항0은 HP553→506(47), 저항20은543→509(34)였다. 후자의 실제 dice합58/INT16/Leverage5/MR25/MR난수60을 같은 값으로 계산하면 저항20 피해34·무저항 피해39다. 실제 HP소비와 수신 SC_STATUS가34에 일치했다. 재접속 뒤 저항 장비를 해제한 실제 피격은551→508(43), 같은 dice/MR 무저항 계산43에 일치했다. 서로 다른 난수 표본의 평균만으로 저항 효과를 주장하지 않는다. 자연 패킷 검증은 **장로/바람 한 사례**이며 나머지 세 속성은 source 선택을 포함한 개발시험 범위다. 10배 설정의 관측 wall14.348초/virtual57.546초(실효4.01배)다.

원본 확인 잔여는 고정 클라이언트의 속성 표시·입력·주문별 애니메이션/거리/AoE·최종 피해 체감과 실제 몬스터 주문 매핑이다. 이번 결과는 local_policy 자연 NPC→PC 저항·HP 연결의 소켓/저장 관측이며 원본 화면 동등성이나30분 수동 플레이 완료가 아니다.

## PC 공격의 몬스터 약점 연결 (2026-10-28)

현재 공식 378행 `data/official/monsters.json`의 `monsters[*].official`은 id/name/image/favorite/level/big/damageable/regionNames/rewards/formName을 제공하며 약점 필드는 없다. 따라서 이번 연결은 **선정 L1J npcID의 weakAttr와 배율을 채택한 local_policy**다. 공식 약점을 확인하거나 L1J 수치를 공식 빈칸에 써 넣었다고 주장하지 않는다. 각 몬스터의 기존 L1J 식별 대응을 유지했고 SQL `db/l1jdb_m10.sql`의 정확한 행은 각 `l1j_weak_attr.ref`에 남겼다.

- `game_data.MonsterDef.weak_attr`는 명시적 `weak_attr` 셀이 있으면 우선하고, 없으면 기존 `l1j_weak_attr` 셀, 둘 다 없으면 0을 사용한다. 출처도 기존 Sources에 보존한다. 현재 공식 약점 셀은 없으며 모든 신규 fallback은 local_policy다. m1/m3/m4/m5/m6 및 catalog/map0의 기존 몬스터 행에서 속성 셀만 추가하거나 과거 미소비 note를 갱신했다. JSON 전체 재직렬화·다른 수치/드롭/스폰 수정은 하지 않았다. 요청 때 원시표를 다시 읽지 않는다.
- `world_combat.elemental_weakness_multiplier()`는 1/2/4/8 단일 속성이 약점과 정확히 일치할 때만 1.2다. 0/16/미정의/복합값은 두 값이 같아도 1이다. 근거는 `L1Magic.java:690–697` 및 상수 `:122`다. 기존 일반 주문 계산·정수 절삭·치명타·MR 순서를 유지하고 `world_feature_magic`의 단일/범위 피해자별 호출에 약점 입력을 전달했다. 위크 엘리멘탈도 같은 MonsterDef 약점을 읽는다. NPC의 물리·주문 공격속성 생산자는 바꾸지 않았다.
- 실제 무기 속성 생산자는 `world_feature_weapon_effects.PROCS`의 얼음/땅/바람 발동마법이다. 기존 장비 조회→발동 확률/난수→현재 피해자→HP/처치 소비 경로에서, 피해자마다 `amount × weakness_multiplier`를 기존 `reduce_proc_damage()`에 보낸다. 기존 MR·속성저항 곱 및 마지막 한 번의 int 절삭은 그대로다. **이는 일반 주문의 ×1.2를 무기 마법에도 공유하도록 채택한 변형 local_policy**다. `L1WeaponSkill.java:475–518` 자체에는 weakAttr 읽기가 없고 target의 네 저항만 읽는다. `L1Attack.java:1170–1177`의 -50은 별도 속성강화 추가피해용이며 이번 proc에 적용하지 않았다. 속성강화 생성/저장 기능을 새로 만들지 않았다. 기본 물리 피해는 증가하지 않는다.
- 무기 기능은 코어 계산 helper만 사용하며 magic의 메서드/private 상태를 호출하지 않는다. magic을 제외한 weapon_effects 단독 개발 fixture에서도 약점 증가를 확인했다. 선택 기능을 빼면 그 기능의 기존 생산자/소비 수명이 함께 사라진다. 파생 약점을 사용자 저장에 추가하지 않는다.

개발시험: `python -X utf8 -B -m unittest tools.local_original_session.monster_weakness_tests tools.local_original_session.element_resist_tests` → **19 tests / 8.811s / OK**. 원문 `runs/monster-weakness-focused-20261028.log`; 신규 5개 초회도 `monster-weakness-unit-20261028.log`에 보존했다. 실제 loaded item 정의를 사용하되 시험 fixture의 선택 template/약점/HP/난수를 교체해 단일/범위 주문의 HP·MP 소비와 무기 proc의 물리+마법 합산 HP 소비, 타속성/물리 불변을 확인했다. 정상 패킷 실장착이나 원본 화면 PASS가 아니다.

같이 실행한 회귀 94개는 **3FAIL/2ERROR**이며 `runs/monster-weakness-regression-20261028.log`를 보존했다. 기존 시험은 수정하지 않았다.

| 기존 시험 | 실제 결과와 분류 |
|---|---|
| `WeaponProcTests.test_single_target_hp_consumes_exact_physical_plus_reduced_proc` | actual122/expected103. 기존 기대식이 신규 약점 ×1.2를 포함하지 않는 직접 영향이다. 신규시험에서 약점/무약점 각각의 HP 소비를 확인했다. |
| `WeaponProcTests.test_cold_chaser_radius_boundary_secondary_death_reward_and_fixed_main_roll` | actual81/expected68. 동일하게 약점 추가 전 proc 고정 기대다. |
| `WorldConsumerTests.test_job_second_erase_real_npc_damage_and_probability_consume_once` | actual MR1/expected40. 시험이 catalog reference MR을80으로 바꾸지만 실제 경로는 기존 MonsterDef MR2를 사용한다. 이번 변경은 MR 경로를 수정하지 않았다. |
| `WorldConsumerTests.test_mana_drain_spell_npc_cast_and_weapon_use_same_actual_balance` | weapon event 없음으로 IndexError. 시험의 구 equipment `combat_inputs` fixture와 현재 core stats 기반 무기 입력 계약이 다르다. 이번 변경 전 조합으로 재시험한 결과는 아니므로 baseline PASS/FAIL로 소급하지 않는다. |
| `RegistryContractTests.test_actual_declarations_resolve_all_optional_subsets_without_callback_imports` | `world_feature_craft` 선언 AST 실행 중 `world_craft` NameError. 이번 변경 파일 밖의 선언 추출 계약 실패다. |

지정 봇은 `SL_TEST_PORT_BASE=49000`, `SL_TEST_TIME_SCALE=10`, 외부 기존 `C:/Users/Chansol/AppData/Local/Temp/claude/D--claude/0483de89-75e7-4b94-84b8-fb31fe00f575/scratchpad/fastbot/run_fast.py`로 순차 실행했다. `hunt_bot_magic --scenario jobs`는 **SUCCESS, 208 checks, 16 magic epochs, broker exception0, cleanup_complete=true, source_changes_during_run=[]**다. 원결과 `runs/hunt-magic-gr_q28jf/summary.json`, 로그 `runs/monster-weakness-magic-jobs-20261028.log`. 정상 FIRST/login/selection/world와 실제 소켓 decoder/router의 기존 jobs 회귀 범위이며 새 약점 무기별 실장착 관측으로 확대하지 않는다.

`hunt_bot_element_resist` 초회는 서버/행동 전 `AttributeError: 'Namespace' object has no attribute 'boss_fixture'`, cleanup_complete=true로 중단됐다. `runs/element-natural-1_gznsj7/result.json` 및 `runs/monster-weakness-element-bot-20261028.log`에 보존했다. 공용 fixture 계약은 이번 범위 밖이라 해당 봇을 수정하지 않았다. 마지막 재시도 `runs/element-natural-gf41vp0h/result.json`은 로그인/선택/월드와 장로 수신·접근을 통과했으나, 저항0의 자연 주문 관측에서 `AssertionError: natural_spell_observed_resist_0`로 **FAIL**이다. 90.783 virtual seconds/1447 requests/1 epoch, samples0, server_failures=[], cleanup_complete=true다. 로그는 `runs/monster-weakness-element-bot-final-20261028.log`; 원본 공격과 무기 약점의 성공 증거로 합산하지 않는다. 재실행 없는 최소 진단에서 **이벤트 관측 목록 불일치**를 확인했다. 봇 `hunt_bot_element_resist.py:77`은 기존 `_world_magic_events`의 `outcome='npc_magic'`만 찾지만, 등록된 monster_skills는 `world_monster_skills.py:145–193`에서 장로 주문 기회를 소유하고 fallback 물리도 직접 처리하여 기존 magic 선택자를 우회한다. 신규 결과는 `:343–346`에서 별도 `_world_monster_skills_events`에 기록한다. 실행 결과의 magic/monster_skills 등록 모듈 해시는 현재 파일과 일치한다. 다만 보존된 result/requests에는 신규 이벤트·장로 잔여MP·현재 AI target·LOS가 없어 **실제 시전 횟수/MP/LOS는 미기록**이다. 정의상 MP60·CallLightning 비용18·확률35%·거리4지만 어느 조건이 실제로 통과/탈락했는지 소급 확정하지 않는다. 접근·공격 응답과 이후 HP538/물약26회는 전투 진행 범위의 근거이며, samples0를 주문 미시전의 증거로 쓰지 않는다. 첫 부족 관측은 신규 생산자의 해당 장로 시전 이벤트와 그때의 MP/거리/LOS다. 추가 재시도나 범위 밖 봇 수정은 하지 않았다.

같은 지정 조건의 재실행 명령:

```powershell
$env:SL_TEST_PORT_BASE='49000'; $env:SL_TEST_TIME_SCALE='10'
python -X utf8 -B C:/Users/Chansol/AppData/Local/Temp/claude/D--claude/0483de89-75e7-4b94-84b8-fb31fe00f575/scratchpad/fastbot/run_fast.py hunt_bot_element_resist
python -X utf8 -B C:/Users/Chansol/AppData/Local/Temp/claude/D--claude/0483de89-75e7-4b94-84b8-fb31fe00f575/scratchpad/fastbot/run_fast.py hunt_bot_magic --scenario jobs
```

변경 제품 소스: `game_data.py`, `world_combat.py`, `world_feature_magic.py`, `world_feature_weapon_effects.py`; 데이터 `data/{m1,m3,m4,m5,m6,catalog/map0}/monsters.json`; 신규 개발시험 `monster_weakness_tests.py`와 이 문서/FILL_MONSTERS.md. 이 목록은 통합 담당의 핀 검토 대상 목록이며 핀/시작 스크립트/validation-profiles는 변경하지 않았다. 원본 클라이언트·공식 약점 수치·최종 속성 피해 체감은 미확인이다.

## 장로 관측 복구와 생산자 공존 검증 (2026-10-28)

직전 `element-natural-gf41vp0h`의 관측 실패는 보존했다. 현재 장로 주문은 선택 `monster_skills`가 생산하는데 봇이 기존 magic의 `npc_magic` 이벤트만 기다리던 문제가 확인됐다. 이번 수정은 `hunt_bot_element_resist.py`와 신규 `element_resist_observation_tests.py`, 이 문서뿐이다. 전투·마법·몬스터 런타임과 데이터는 변경하지 않았다. 추가 외부 조사 없이 위 공식/L1J 출처와 기존 `MONSTER_SKILLS.md`·생산자 정의를 재사용했다.

현재 `MonsterSkills._fight_wrapper`는 주문 성공 시 그 AI 공격 기회를 끝내며, 실패한 기회의 `_attack_wrapper`도 해당 마법종의 물리 fallback까지 소유한다. 따라서 기존 magic의 `npc_swing` selector가 같은 기회에 다시 roll/MP 소비하지 않는다. 두 표에 같은 장로 정의가 있지만 **현재 공존 구성에서 이중 생산은 재현되지 않았으며 런타임 패치는 필요하지 않았다.** 등록 훅을 사용한 개발 회귀에서 양쪽 wrapper 설치 순서 모두 주문1회·MP18 단일소비·legacy selector 호출0, 신규 확률 탈락 후 물리1회·MP불변을 확인했다. magic 제외 시 새 주문, monster_skills 제외 또는 종료 시 기존 주문과 HP 소비도 유지된다. 이는 장로 대표 경로의 근거이며 모든 종/행동의 전수 검증은 아니다.

봇은 기존 FIRST/login/selection/world/인벤토리와 장비0960·Quit/close를 유지한다. 수신한 자기 공격4E31을 확인한 뒤 수동 몬스터의 반격을 관측하며, 두 생산자 이벤트에서 주문을 찾는다. 실제 시전 시각 이후·이번 관측 ordinal 이후에 받은 해당 NPC→자기4E31, 이어진 자기HP4E38, 정의된 효과4ED8을 한 공격 수신 구간으로 묶는다. 다른 NPC 공격이 끼면 그 구간을 종료한다. 전체 과거 frames에 같은 HP가 있다는 이유로 통과시키지 않는다. monster 이벤트에 없는 `rolled_damage`는 합성하지 않고 실제 HP 감소량을 독립 계산한 `min(hp_before, expected_damage)`와 비교한다.

명령과 원문:

```powershell
python -X utf8 -B -m unittest tools.local_original_session.element_resist_observation_tests tools.local_original_session.element_resist_tests tools.local_original_session.monster_skills_tests
$env:SL_TEST_PORT_BASE='49000'
$env:SL_TEST_TIME_SCALE='10'
python -X utf8 -B C:/Users/Chansol/AppData/Local/Temp/claude/D--claude/0483de89-75e7-4b94-84b8-fb31fe00f575/scratchpad/fastbot/run_fast.py hunt_bot_element_resist
```

단위시험 **33/33 OK, 18.650초**(신규6개 포함), 원문 [element-observation-unit-20261028.log](../runs/element-observation-unit-20261028.log). 봇 최종 소스의 신규6개도 **6/6 OK, 3.440초**, [element-observation-final-unit-20261028.log](../runs/element-observation-final-unit-20261028.log). 신규시험 초회에는 fixture의 정상 visibility 갱신이 빠져 주문/MP 확인 뒤 watcher 공격 프레임3건이 실패했고, fixture에서 `_refresh(1)`로 기존 visibility를 구성한 뒤 위 결과를 얻었다. 제품 런타임이나 기존 시험 기대값은 수정하지 않았다.

봇 **DEVELOPMENT saved-fixture socket PASS**, exit0·23 checks·400 requests·2epochs·server_failures=[]·각 cleanup_complete=true/active_tasks0. 결과 [result.json](../runs/element-natural-75vvy_6k/result.json), 실행 원문 [element-observation-bot-20261028.log](../runs/element-observation-bot-20261028.log). 새 Lv30 저장 fixture와 보유 반지501/벨트3937 공급을 사용했으며 자연 획득·성장은 판정하지 않는다. `FAST_CLOCK`의 설정 `scale=10.0`, 실제 측정은 **real14.751초/virtual30.333초, speedup=2.06**다. 요청/타이머의10배 설정 실행이며 전체 wall-clock10배 가속을 달성했다고 주장하지 않는다.

| 단계 | 실제 피해/MP | 이번 시전에 귀속한 수신 ordinal |
| --- | --- | --- |
| 바람저항0 | HP581→559, 피해22, MP60→42; 주사위65/MR25·roll4 | marker149 뒤 NPC4E31=155, HP4E38=156, gfx10 4ED8=157 |
| 반지·벨트 장착 저항20 | HP546→508, 피해38, MP42→24; 주사위65/MR25·roll50, 속성계수0.1875 | marker163 뒤 512/513/514. 같은 주사위·MR의 무저항 피해44보다 감소 |
| 재접속 저항20 복원 뒤 장비 해제0 | HP528→480, 피해48, 새 runtime MP60→42; 주사위70/MR25·roll54 | 새 연결 marker87 뒤 91/92/93 |

세 샘플 모두 `monster_skills` 생산자다. 세 피해량 자체를 서로 비교한 판정이 아니라 각 시전의 같은 주사위·MR roll을 유지한 독립 계산과 실제 HP 소비를 비교했다. 시작 저장·각 epoch·기록된 해시 조합은 위 result의 fixture_notes/epochs/source_sha256에 있다. 이 Matrix 결과에는 `source_changes_during_run` 필드가 없으므로 실행 중 모든 소스 불변을 확인했다고 표시하지 않는다. 수신 bookkeeping은 기존 `hunt_bot_monster_skills.SkillBot.apply`를 재사용했으나 해당 모듈은 Matrix 기본 fingerprint/봇 명시 목록 밖이어서 이 실행에 해시가 기록되지 않았다. 기존 import 시점 fingerprint 및 봇 종료 시 명시 소스 해시의 기록 범위만 사용하며 새 guard/핀/검사체계는 추가하지 않았다.

이번 변경의 핀 검토 대상은 `hunt_bot_element_resist.py`, `element_resist_observation_tests.py`다. `launcher.py`, 시작 스크립트, validation profiles, ACTIVE_TASK와 제품 런타임·데이터는 수정하지 않았으며 커밋하지 않았다. 원본 클라이언트는 실행하지 않았다. 원본 장로 주문 보유/시전 동작·입력·화면·속성 표시와 공식 계산식은 여전히 미확인이다.
