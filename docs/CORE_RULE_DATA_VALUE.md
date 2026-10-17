# 핵심 서버값: 확보한 숫자와 아직 비어 있는 부분

2026-10-09. 정적 표 51개를 분석했지만 전체 서버 룰을 재현할 정도의 데이터는 아직 확보하지 못했다. 앞선 요약은 구조·필드 수·사용처를 강조했고, 실제로 있는 유용한 숫자를 충분히 드러내지 못했다. 중요한 수치는 일부 있으며 완전한 몬스터 DB와 전투·성장 공식은 별도 미확정이다.

## 실제 있는 숫자

| 자료 | 현재 확인한 숫자 | 근거 수준 |
|---|---|---|
| 화살, recipe39/item29 | sdam6 / ldam5 | 제작 결과의 소형·대형 피해 **표시값** |
| 미스릴 화살, recipe40/item258 | 10 / 9 | 같은 경로 |
| 요정족 검, recipe57/item73 | 8 / 8 | 같은 경로 |
| 레이피어, recipe58/item274 | 11 / 6 | 같은 경로 |
| 메일 브레이커, recipe65 | 4 / 5, meleeHit10 | 피해·명중 태그의 실제 숫자 |
| 실드, spell2 | acBonus2, 지속1200초 | 효과 선언·설명 대응. 저장값+2를 곧바로 AC+=2로 쓰지 않음 |
| 메디테이션, spell31 | MP10 / HP40, 지속600초 | 현재 마법 설정·설명 대응 |
| 인비지블리티, spell59 | MP45 / HP25, 촉매1개 | 현재 마법 설정·설명 대응 |
| 바디 투 마인드 / 블러드 투 소울 | HP8→MP2 / HP50→MP15 | HP 비용 설정과 MP 회복 설명 문구 |
| 공식 몬스터 목록 | 현재 ID·이름 정확 대응333개에 레벨 값 | [공식 목록 대조](MONSTER_LEVEL_COMPARISON.md); 언팩 f23을 레벨로 대체하지 않음 |

제작 결과의 `craft.f8.f1.f6.f13 → ItemDescription.f1 → DescToken33/34 → sdam/ldam`에는 **34개 결과의 피해값 쌍**이 있다. 현재 item.bin의 f29에는 sdam/ldam이 각각0개이므로 제작 상세표가 일부 무기값을 보완한다. f29에는 enchantDamage2052개·enchantAc3708개가 있지만 인덱스의 실제 강화 적용과 서버 산술은 아직 별도 미확정이다.

이 값들은 재현 목표·데이터 seed의 근거가 될 수 있다. sdam6이 고정 피해6이나 uniform1..6 난수를 뜻한다는 증거는 없으며, 최종 피해/명중 판정·자원 차감·제작 성공/재료 소모 구현은 확인한 표시 숫자와 구분한다. 전체34쌍의 원문 경로·이름·ID·값은 [피해값 원문](../work/core_rule_research/value_audit/weapon-pairs.json)에 있다.

인비지 촉매 이름은 `spelldesc118`의 “마력의 돌 1개” 문구에 근거한다. spell_list의 촉매type0은nameid166을 참조하지만 현재desc.csv166의 실제 값은placeholder `desc166`이다. 이를 실제 아이템 이름 조인으로 확정하지 않는다.

## 파일 밖에서 확인한 값의 전달 경로

원본 `SC_STATUS` opcode4E38 → handler113540 → 로컬ActorStatusInfo → HUD를 추가로 닫았다.

| 프로토 필드 | 확인된 역할 | 경계 |
|---|---|---|
| f2 | 로컬 캐릭터 레벨 표시 | 실제 수신한 레벨 숫자 미관측 |
| f12/f13 | 현재/최대 MP 표시 | 기본 MP·레벨업 증가 산식과 다름 |
| f26 double | EXP 퍼센트 표시(`{:.4f}%`, 게이지상한100) | 선택 필드. 누락 초기값을 실제 수신0으로 취급하지 않음 |

이것은 서버에서 받은 상태를 표시하는 경로다. “레벨업마다 필요한 경험치” 배열이나 서버가 그 퍼센트를 계산하는 수식은 회수하지 못했다. [수신 경로 상세](../work/core_rule_research/progression/README.md)에 원본 필드·저장·소비·해시를 남겼다.

## 아직 확보하지 못한 핵심

- 몬스터 전체의 HP/MP/AC/MR/EXP·공격력 기본값, spawn과 드롭 확률/수량의 실제 생성 룰
- 클래스별 HP/MP 성장, 레벨별 요구 경험치, 능력치별 피해·명중·MR 보너스
- 물리/마법 피해 난수, AC 명중식, INT/SP/MR·속성저항·치명타·리덕션 적용 순서
- 아이템 가격·장착/class 조건 일부와 제작 성공·차감·보상 지급의 서버 실행 규칙

`CharacterStatT → StartStatT/LevelBonusByClassT/ConstantT → Hit/Ac/Dmg/HP/MP/SpellDmg/SpellProb`와 `ExperienceDesign`, `NPC_ClassT`, `BossSpawn` 등의 생성 타입은 코드에 존재한다. 그러나 이번 좁은 추적에서는 값을 채우는 파일·서버 패킷·비생성 전투 소비에 연결하지 못했다. `config::Config f2/+38 → SpellHealModifierT`도 생성·초기화·복사만 확인됐고 회복 계산이 아니다.

타입·기본값을 실제 운영 수치로 확대하지 않았다. 공유 코드에 포함된 미사용 protobuf 타입일 가능성은 후보이며, 클라이언트 전체에 공식이 없다는 단정은 하지 않는다. [핵심 타입 추적](../work/core_rule_research/stat_routes/README.md)의 실제 비기본 운영값·공식 추가 회수는0이다.

## 검증

[Root 독립 검토](../work/core_rule_research/root-review.json) **15,163검사 PASS**. 별도 raw wire parser로34쌍·아이템5968표시 항목·MP/HP 비용·지속/효과 예제를 대조하고, 현재CONTROL의 선택된 원본 구간15,095개와 입력핀을 다시 읽었다. 이는 의미가 확정된 수나 운영값 수가 아니다. 게임·메모리·GUI·프로세스·네트워크·UAC·원본/제품 변경0이다.

[유용한 숫자 감사](../work/core_rule_research/value_audit/README.md) · [10개 구체 예제](../work/core_rule_research/value_audit/numeric-examples.json) · [전체 정적 표 분석](ALL_TABLE_SEMANTICS.md)
