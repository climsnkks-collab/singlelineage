# COMPANION-MAGE Heal0 amount source boundary

SOURCE_AUDIT_COMPLETE / CALLEE_NOT_SUPPLIED / test_ready:false / runtime:UNRUN.

**첫 미공급은 같은 current companion caster의 실제 lawful 값을 생산하는 `magic_context(caster_binding, active)` source다.** selected `SharedSupport.plan`은 정확한 `{'lawful': int}`를 요구하지만 호출 가능한 실제 producer는 이번 선정 source에서 찾지 못했다. `MagicActor`의 기본값0·fixture lambda·SQL의 spell lawful0을 실제 caster lawful로 대입하지 않았다. 따라서 이번 디렉터리에는 fake callable이나 치료량 callee가 없다.

## 실제 source를 따라 확인한 경계

1. `companion-derived-stats-v2/companion_derived_stats.py:95`는 실제 broker/ResourceOwner/SharedSupport의 identity, current active companion lease/operation lock, 같은 Gear/Inventory/SKILL를 읽어 original `DerivedStats`를 반환한다. 이 반환에는 INT/SP/magic bonus/level이 있으며 lawful 필드나 RNG 소유자는 없다. 실제 companion stats producer를 direct player stats로 대체할 이유가 없다.
2. selected `combat_magic.py:40,62`의 `MagicActor.from_derived`는 original derived magic fields를 복사하고 explicit context를 추가한다. `lawful=0` dataclass 기본값은 현재 caster의 저장값·관측 근거가 아니다. 같은 source의 `resolve_heal:310`은 `actor.lawful > 0`일 때 치료량을 실제로 변경하므로 이 값이 생략 가능한 표시 metadata가 아니다.
3. selected `character_state.py:174–203`의 strict row는 uid/name/class/gender/attributes와 revision/progression/preferences다. progression도 experience/level만 허용한다. 읽은 selected CharacterStore·ResourceOwner/HP status·DerivedStats source에는 lawful producer가 없다. 가짜 row 키나 새 저장 파일을 추가하지 않았다. 이 결론은 이번 선정 source 범위이며 저장소 전체 또는 원 protocol 전체에 값이 없다는 주장이 아니다.
4. `optional-target-v1/candidate/companion_shared.py:492–506`은 이미 같은 installed Rule0/caster operation/current 검사 뒤 actual `configuration.healing`, `derived_stats(caster,active)`, `magic_context(caster,active)`와 하나의 `configuration.rng`를 existing resolver에 전달한다. 별도 amount 함수/두 번째 resolver 호출/새 공식은 필요하지 않다. 실제 context producer와 retained RNG를 기존 configuration에 공급하는 source가 필요하다.

## RNG owner는 일부 기존 경로가 있다

선정 COMBAT `combat_roster_setup.py`는 주입된 하나의 rng를 `self.rng`로 보유하고, 같은 객체를 기존 PcNpcProvider와 NpcPcAdjudicator로 넘긴다. selected `combat_adapters.py:35`도 그 exact injected object를 보유해 accepted physical action당 한 번 판정한다. 기존 `packet-combat-trial-v1/inputs.py:104`에는 `random.SystemRandom()` 한 개를 만들어 setup에 넣는 구체적인 준비 경로가 있다.

하지만 이것은 **동일한 live companion configuration이 그 owner의 rng를 보유한다는 source**가 아니다. companion source capture는 `canonical_feature_bootstrap.py:458–511`의 기존 one-cold capture/명목 source identity를 지켜야 하고, `SharedSupportConfiguration`의 retained rng·magic_context identity도 보존해야 한다. physical provider의 임의 private rng를 읽거나 별도 SystemRandom/seeded Random을 만드는 callee로 해결하지 않는다. 원 COMBAT rng source/instance를 같은 cold 구성에서 명시 연결하는 한 owner 계약이 필요하다. 테스트 Rolls/fixture RNG와 source 파일만 같은 임의 새 객체를 제품 권위로 옮기지 않는다.

## HealingSpell 설정에 재사용할 정확한 source

이전 `companion-heal0-target-authority-v1/source-facts.json`의 named join·SQL 원행을 재사용한다: Book164/client key0→LesserHeal SQL skill1, damage_dice4/damage_value2. 이 숫자는 기존 `LOCAL_REFERENCE_L1J` resolver에 공급할 reference coefficient이며 완성된 HealingSpell0 설치가 아니다. SQL19 Heal·Light1로 대체하거나 key0을 숫자 offset으로 만들지 않는다. `HealingSpell`의 leverage 기본값10은 existing reference API 기본값이며 원 NC 계수를 새로 확인한 결과가 아니다.

실제 lawful/RNG source가 공급되면 기존 SharedSupportConfiguration의 `healing[0]`에 같은 selected `combat_magic.HealingSpell`를 exact coefficient/source 정책으로 하나 구성하고, 기존 SharedSupport.plan의 resolver 호출을 그대로 소비하면 된다. Rule0/cost/learned/current, caster binding·Store/CAS, target clamp·원 response는 기존 owners가 유지한다. 이 문장은 현재 존재하는 callee/API나 이미 설치된 configuration을 뜻하지 않는다.

range10/current target·정상 learned0/header·공동 custody는 앞선 target-authority 계약 그대로 별도다. amount 조사에 source가 없는 lawful을 이유로 전체 feature나 다른 준비 작업을 멈추는 gate를 추가하지 않는다. 필요한 다음 입력은 실제 character-state/resource owner가 공급하는 same-caster lawful source와 같은 cold configuration의 단일 RNG owner 연결이다.

최소 확인은 부모 핀/JSON, 위 selected source의 AST·field/consumer 접점만이다. 기존 stats·magic 테스트/SQL 추출은 재실행하지 않는다. 제품 import/생성자·runtime/REA/native·포트·패킷·handler·Store/공용·기존 private 변경·큐/Test 작업 0이다.
