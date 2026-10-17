# 전투 공식 조사

조사일: 2026-10-05. 대상은 한국 NC 리니지 클래식, 프로젝트 클라이언트 `26.09.29.2001`이다.

**현재 서버의 명중·최종 피해·MR/속성저항 전체 산식은 이번 조사에서 확정하지 못했다.** 대신 현재 인증 데이터의 실제 전투 속성, 공식 가이드의 규칙·효과 설명, 클라이언트 표시 계산, 버전을 고정한 공개 서버 참고식을 각각 확보했다. 표시값이나 구버전 수식을 현재 서버 계산식으로 합치지 않았다.

## 추가 확인: spell.bin에 피해 수식·계수가 있는가

사용자의 후속 질문에 따라 수식 문자열뿐 아니라 **433개 레코드/3,672개 실제 wire field**를 다시 읽었다. 독립 parser·기존 decoder·Root의 raw parser로 대조했다.

- 에너지 볼트3, 아이스 대거5, 윈드 커터6, 파이어 애로우14, 파이어볼24, 콜 라이트닝33, 콘 오브 콜드37, 이럽션44, 선 버스트45는 **ID를 제외한 body가 정확히 같다.** f2/3/4/5/6/10은0, f13은10이며 wire2/고정숫자 payload가 없다. f13을 피해10으로 이름 붙일 근거는 없다. 이 body에서 주문별 서로 다른 기본 피해·dice·INT/SP 계수를 읽어내지 못했다.
- 전체 spell.bin의 실제 wire1/5 fixed field는0개다. 레코드 내부 길이 payload는 f8의 명시 효과 tuple224개뿐이다. 이들과 내부 문자열672개, 합계896 payload를 packed/nested/UTF8로 교차검토했다. 문자 bytes를 숫자열로 해석할 수 있다는 사실만으로 숨은 피해 배열이라고 판정하지 않았다. 미분류 nonprintable/nonmessage packed 후보는0개다.
- 실제 효과값은 있다. 실드의 acBonus2, 위크니스의 meleeHit−2/meleeDmg−4, 이레이즈의 mrRatioBonus−500, 라이트7200·실드1200의 지속 설명 대응 등을 확인했다. **버프/디버프 효과 상수와 주문 자체의 피해 계산식은 구분한다.**
- 코드에서 `spell.bin → LIN::CommonSpellInfo 파싱 → ID별 저장 → GetSpell 조회`를 확인했다. path RVA11b0468, loader373450, ID 삽입386b60, GetSpell370350이며 CommonSpellInfo TD173ca28/COL12f3d70/vtable11de368을 직접 대조했다. 별도의 `CharacterStatT_ConstantT_SpellDmgT`와 마법 확률·modifier 타입도 존재한다. 확인한 SpellDmgT 함수는 생성·복사·직렬화이며 피해 산술로 확정하지 않았다.
- CommonSpellInfo serializer에서는 f13이 반복 varint다. 실제 table에 있는 f10=0의 이름/소비 의미는 연결하지 못했다. 객체 +0x68을 f10으로 추정하면 안 되며 해당 serializer helper의 tag는 f14다.

따라서 **현재 확인한 spell.bin에서 마법별 피해 공식·계수를 확인하지 못했다**고 답할 수 있다. 여러 순간 공격 body의 동일성은 직접 확인했지만, ID로 다른 코드/룰/서버 자료를 선택하는 가능성까지 부정하지 않는다. 게임 전체에 마법 피해 공식이 없다는 결론은 아니다.

[숫자·packed 정밀 보고서](../work/combat_formula_research/spell_detail/findings.md), [실제 loader·RTTI 근거](../work/combat_formula_research/spell_consumer/findings.md), [Root 독립1,150개 확인 PASS](../work/combat_formula_research/spell-root-review.json)

## 현재 클래식에서 확인한 규칙과 남은 산식

| 항목 | 확인된 근거 | 아직 미확정인 부분 |
|---|---|---|
| 물리 명중 | 공식 가이드: STR은 근거리, DEX는 원거리 명중에 영향. 데이터에 `meleeHit`/`rangeHit` 존재 | 능력치·레벨 보너스표, AC와의 확률식, 최소/최대 확률, 대상 유형별 차이 |
| 물리 피해 | 공식 가이드의 몬스터 크기별 피해 구분. 제작 표시 자료의 `sdam`/`ldam`, 추가 피해·강화 속성 | 무기 난수 분포, STR/DEX 계수, 손상·강화·속성·버프·리덕션 적용 순서 |
| AC | 방어구 강화 +1마다 AC−1. AC가 낮을수록 물리 피격 가능성 감소 | AC 1당 회피율, 클래스별 피해감소, 현재 산식의 반올림·하한 |
| MR | MR 증가 시 마법 피해 및 일부 확률마법 성공 가능성 감소. 이레이즈 매직의 MR 감소 설명과 수치 확보 | 피해계수, 마법 성공률, 시전자/대상 종류별 분기·적용 순서 |
| 속성저항 | 지·화·수·풍 저항 이름·값과 공식 UI 설명 존재 | 저항값→피해계수, 속성 우선순위·상쇄·상한 |
| 치명타·리덕션 | `critical` 이름/사전, `dmgReduction` 실제 속성 존재 | 실제 치명 확률·배율, 감산·곱셈 순서, 물리/마법 구분 |

현재 규칙 설명은 [NC 스탯 가이드](https://lineageclassic.plaync.com/ko-kr/guidebook/view?title=%EC%8A%A4%ED%83%AF), [무기 가이드](https://lineageclassic.plaync.com/ko-kr/guidebook/view?title=%EB%AC%B4%EA%B8%B0), [방어구 가이드](https://lineageclassic.plaync.com/ko-kr/guidebook/view?title=%EB%B0%A9%EC%96%B4%EA%B5%AC)에 근거한다. 공개 JSON 원문과 문서 ID·업데이트 날짜·SHA256은 [출처 목록](../work/combat_formula_research/sources/sources.json)에 남겼다. 해당 가이드는 서버 실행 코드나 전체 확률식을 공개한 자료가 아니다.

## 현재 데이터에서 찾은 구체적인 효과

현재 인증 바이너리 19개를 전수 읽었다. 아이템 1,266/NPC 951/마법·효과 433/설명 token 1,419개다. 명시 이름·값 tuple **483개**, 아이템 표시 token **5,968쌍**, 제작 표시 token **1,712쌍**을 보존·대조했다.

| 자료 | 실제 값·문구 | 서버 룰 해석 경계 |
|---|---|---|
| 실드, spell ID2 | `acBonus="2"` ↔ 설명 `AC-2` | 효과 설명상 AC를 2 낮춤. 저장 부호를 그대로 `AC += 2`로 적용하면 맞지 않음 |
| 이레이즈 매직, ID152 | `mrRatioBonus="-500"` ↔ MR이 1회에 한해 약 1/2로 감소 | 상대 변화가 천분율이라는 가설과 일치. 실제 분모·반올림·유효기간·소모 판정 구현은 미확정 |
| 스트라이커 게일, ID173 | `evasionRateRatioBonus="-667"` ↔ 대상 ER이 1/3로 감소 | 위 가설과 일치하지만 0.333과 정확한 1/3의 차이·반올림은 미확정 |
| 레이피어, item274/recipe58 | 제작 출력 표시 `sdam=11`, `ldam=6` | 소형/대형 피해 입력 후보. 이를 바로 uniform dice 1..11/1..6으로 확정하지 않음 |
| 요정족 단검, item39/recipe56 | `sdam=4`, `ldam=3` | 동일한 경계 |
| 화살, item29/recipe39 | `sdam=6`, `ldam=5` | 활/화살 결합 피해 순서는 별도 근거 필요 |
| 라이트, ID1 | raw field6 값 7200 ↔ 설명 지속 7,200초 | 이 표본의 대응은 확인. field6 전체의 시간 단위·의미를 확정한 것은 아님 |

이레이즈 매직과 스트라이커 게일은 현재 UI 자료에서 MP30·정령옥2개·사거리6도 읽혔다. 이 값들은 사용 조건 입력이며 명중/피해 산식은 아니다. [원문·필드 경로](../work/combat_formula_research/data/special-ratio-effects.json)

현재 명시 속성에는 `meleeDmg`, `rangeDmg`, `meleeHit`, `rangeHit`, `acBonus`, `dmgReduction`, `spBonus`, 능력치·HP/MP 보너스와 4속성저항이 있다. 원문 배열의 축과 비율 단위는 별도로 남겼다. 특히 item field14의 값 배열을 강화 단계별 값이라고 단정하지 않았다.

`diceNum`, `diceType`, `diceBonus`, `damageMulti`, `levelMod`, `critical` 등의 설명 사전 이름은 있으나 이번 named/display 경로에서 실제 사용값이 확인되지 않은 이름도 있다. 사전 이름을 근거로 임의의 주사위·치명타 공식을 생성하지 않는다.

공식 가이드의 오크족 단검 표시는 `2+0/3+0`이다. 현재 item40은 찾았지만 이 기본값에 직접 대응하는 필드를 확인하지 못했다. 따라서 언팩 아이템 자료가 서버의 모든 기초 전투값을 포함한다고 전제할 수 없다.

NPC의 이름 없는 숫자 필드에도 HP/AC/MR/레벨이라는 이름을 임의로 붙이지 않았다. binary 문자열 **23,232개**와 관련 한글 문구를 탐색했지만, 검사한 수식 패턴에 맞는 실행 산식 후보는 0개였다. 이는 이번 탐색 범위의 결과이며 직렬화된 계산 자료나 다른 표현의 부재를 입증하지 않는다.

## 클라이언트에서 확인한 계산

현재 CONTROL SHA256 `9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`와 복원 record7개를 검증했다. 공개 전투 명칭 **106개**, 정확한 instruction 경계와 RIP operand를 확인한 참조 **51개/함수26개**, 근거창 **11개**를 조사했다.

`0x403820~0x404c85`는 문자열을 구성하는 스탯 설명 경로다. 다음 수치 변환을 실제 코드에서 확인했다.

| 코드 | 확인한 연산 | 경계 |
|---|---|---|
| `0x403ccc~0x403cf5` | 입력 int32의 부호를 반전해 문자열 생성: +2→−2 | 입력 offset `+0x6c`가 AC인지 아직 미확정 |
| `0x40444c~0x40447a`, `0x404480~0x4044ae` | 분모>0이면 `분자/분모×100`, 아니면 0 | 설명용 비율. 게임 명중률이라는 근거 없음 |
| `0x404802~0x40486a`, `0x404922~0x40498a` | int32 배열의 각 값에 float32 `0.1`을 곱한 뒤 formatter 전달 | 표시 단위 변환. 서버 확률 분모1000으로 연결되지 않음 |

MR/4속성저항 이름을 소비하는 `0x3d02a0`은 이름 등록 경로였다. 산술 함수로 보였던 공격 핸들러의 multiply/shift도 kind의 modulo 계산이어서 피해 공식 근거에서 제외했다.

`SC_ATTACK_NOTI`, `SC_ATTACK_MANY_NOTI`, `SC_ATTACK_CONTINUE_ACK`, `SC_HIT_POINT_NOTI`, `SC_INSTANCE_HP_NOTI`, `SC_MAGIC_EVASION_NOTI`, `SC_SPECIAL_RESISTANCE_NOTI`, `SC_DAMAGE_OF_TIME_NOTI` 등의 수신 parser와 공격 객체 복사·소비 경로를 확인했다. 정확한 wire opcode/피해 필드까지 연결한 것은 아니다. 제한된 코드 조사로 클라이언트 전체에 전투 계산이 없다고 주장하지 않는다. [코드 조사 및 RVA 근거](../work/combat_formula_research/code/findings.md)

## 별도 참고 계산식

아래는 **현재 NC Classic에 검증되지 않은 L1J-EN 참고 구현**이다. [저장소 README](https://github.com/l1j-en/classic/blob/103e6f6c9dd83545959d8e87d3f59f8de1f40ef0/README.md)의 대상은 2009년 최종 미국 클라이언트이며, 조사 commit은 `103e6f6c9dd83545959d8e87d3f59f8de1f40ef0`이다. 현재 서버 룰에 적용하지 않았다.

| 참고식 | 조건 |
|---|---|
| 명중%= `min(95,max(5,5×(H+대상AC)))` | 정상 PC→NPC, 스킬 조정·특수 예외 없음. H 정의와 실제 d20 분기는 상세 출처에 있음 |
| 근접 기초 피해= `U(1,W)+무기추가피해+유효강화+STR보정+기타보정` | 보통 무기의 기초 단계. 후속 버프·감소·특수 무기 분기 포함한 최종식 아님 |

근거는 고정 commit의 [L1Attack.java](https://github.com/l1j-en/classic/blob/103e6f6c9dd83545959d8e87d3f59f8de1f40ef0/src/l1j/server/server/model/L1Attack.java)다. PC→PC에는 다른 방어주사위가 사용된다.

PC가 시전한 마법의 참고 MR 계수는 `MR≤100: 1−0.01×trunc((MR−b)/2)`, `MR>100: 0.6−0.01×trunc((MR−b)/10)`이다. `b`는 originalMagicHit, `trunc`는 0 방향 정수화다. NPC 시전 마법은 다른 확률적 반감 분기다. [L1Magic.java](https://github.com/l1j-en/classic/blob/103e6f6c9dd83545959d8e87d3f59f8de1f40ef0/src/l1j/server/server/model/L1Magic.java)

STR/DEX 보너스표, AC·WIS·INT 계산과 속성·확률마법·치명타의 참고 분기는 [버전별 출처 보고서](../work/combat_formula_research/sources/findings.md)에 있다. 이 참고식을 현재 NC 서버의 확정값으로 가져오지 않는다.

## 서버 룰 적용 전에 확인할 것

1. item/NPC/spell field를 실제 소비 코드/descriptor와 연결해 이름·타입·부호·단위를 확정한다.
2. 물리 공격 방향(PC→NPC, NPC→PC, PC→PC), 근거리/원거리·대상 크기를 분리해 명중과 피해 순서를 검증한다.
3. MR/속성저항·버프·리덕션의 계산 순서와 정수화 지점을 확인한다. 표시 배율을 판정 배율로 사용하지 않는다.
4. 원본 현재 공식과 참고 구현의 일치 확인에는 조건을 통제한 전투 결과 측정 또는 추가 실행 코드 근거가 필요하다. 이번 작업에서는 게임을 실행하거나 서버 룰을 변경하지 않았다.

## 검증과 산출물

데이터 worker의 62개 확인과 코드 근거를 검토한 뒤 Root가 **소스·데이터 독립459개 확인 PASS**를 기록했다. 실제 파일 SHA, token 대응, 효과 문구, public literal/RIP operand, 근거 instruction의 원본 hash와 상수를 다시 대조했다. 별도 참고 명중식은 Root가 **8,181개 H/AC 조합에서 d20 전20면**과 일치함을 확인했다. 이는 참고 코드 해석의 산술 검증이고 NC 서버 실측이 아니다.

- [Root 독립 확인](../work/combat_formula_research/root-review.json)
- [현재 데이터 조사](../work/combat_formula_research/data/findings.md), [명시 속성 TSV](../work/combat_formula_research/data/named-attributes.tsv), [제작 무기 피해 표시](../work/combat_formula_research/data/crafted-weapon-displays.json)
- [현재 코드 조사](../work/combat_formula_research/code/findings.md), [instruction 근거창](../work/combat_formula_research/code/bounded-public-combat-instructions.json)
- [공식/참고 출처](../work/combat_formula_research/sources/sources.json), [참고 구현 산술 확인](../work/combat_formula_research/sources/arithmetic-checks.json)

새 코드는 `tools/combat_formula_research/`, 분석 산출물은 `work/combat_formula_research/`에 있다. 원본·보관·팩·SDK·키 파일 수정, 게임 실행·메모리·UAC 작업은 없었다. 네트워크 사용은 공개 웹 원문/공개 코드 조회뿐이다.
