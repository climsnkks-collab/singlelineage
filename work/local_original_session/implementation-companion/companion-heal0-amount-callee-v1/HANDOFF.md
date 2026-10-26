# COMPANION-MAGE Heal0 amount callee audit v1

WRITER_RELEASED / SOURCE_AUDIT_COMPLETE / callee:null / test_ready:false / runtime:UNRUN.

첫 결손은 실제 same-current companion caster의 `magic_context(binding,active)->{'lawful': actual_value}` producer다. selected DerivedStats/strict CharacterStore에는 lawful source가 없고 MagicActor default0·SQL spell lawful0·fixture lambda는 현재 caster 값이 아니다. 이 값은 resolve_heal이 치료량에 실제 소비하므로 생략하지 않았다.

기존 COMBAT는 setup.rng 한 객체를 physical providers에 공유한다. concrete packet-combat 입력의 SystemRandom owner 경로도 있다. 다만 그 같은 owner/instance를 companion의 retained cold configuration/source capture에 결속하는 source는 미공급이다. 별도 RNG나 wrapper·가짜 callable을 만들지 않았다.

amount formula는 기존 selected combat_magic의 HealingSpell/resolve_heal, coefficient는 이전 named Book164→Heal0→LesserHeal1의 dice4/value2 근거를 재사용한다. 실제 lawful/RNG가 공급되면 기존 SharedSupportConfiguration.healing[0]/magic_context/rng에 연결해 원 SharedSupport.plan의 단1 resolver 호출을 그대로 쓸 수 있다. 원 Rule0/current/learned/Store·target/positive key 경계를 변경하지 않는다.

`CONTRACT.md`, `source-contract.json`, 정확 부모 `parents.json`과 `manifest.json`으로 인계한다. AST/핀/소비 접점 최소확인만 PASS. callee·실행 caller/RUN_COMMAND·runtime/REA/포트·패킷·Store·공용·큐/Test 변경0. main이 source 결손과 다음 producer 담당을 검토한다.
