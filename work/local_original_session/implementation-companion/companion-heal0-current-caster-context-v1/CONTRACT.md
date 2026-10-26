# COMPANION-MAGE actual UID2 caster context

SOURCE_AUDIT_COMPLETE / ADAPTER_NOT_SUPPLIED / test_ready:false / runtime:UNRUN.

**실제 선택된 mage31 저장 입력까지 확인했지만 UID2 caster lawful과 companion에 결속된 단일 RNG를 공급하지 않는다.** 첫 미공급은 같은 current companion binding/lease를 검사하고 실제 lawful 값을 반환하는 `magic_context(binding,active)` source다. 이번 파일에서 값0·default·SQL/fixture·새 RNG를 대입하지 않았다.

## 새로 확인한 실제 저장 입력

기존 `companion-summon-input-v1/input-source.json`이 지정한 Test-passed 전체사본의 다음 세 파일을 read-only로 읽고 정확 hash/bytes를 확인했다. 원 전체사본·기존 파일은 수정하지 않았다.

| 실제 파일 | 확인된 UID2 저장 내용 | lawful/current 한계 |
|---|---|---|
| root `characters.json` (`44082b5a…`,235B) | UID2/class3/gender0, attributes `[8,7,12,12,8,12]`; uid/name/class/gender/attributes만 있음 | lawful 필드·같은 live companion lease 없음 |
| `character-state/2/characters.json` (`d511209e…`,151B) | 같은 UID2/class3/attributes, 같은 legacy CharacterStore shape | root의 UID1이나 다른 NPC 상태를 caster context로 대입할 근거 없음 |
| `character-state/2/inventory.json` (`80b404ea…`,2064B) | 유일 participant RESOURCE:2, rev0, HP20/max20·MP10/max10, pending null | 값 키는 정확10/11/12/13뿐. full_status_sha는 hash이며 lawful 값/field 의미를 복원하지 못함 |

실제 전체 pin·관측한 key 집합은 `saved-evidence.json`에 있다. 저장 입력과 현재 서버 actor/lease는 구별한다. 이 읽기는 정상 WORLD를 새로 실행하거나 live `provider.current`를 호출한 결과가 아니다.

## 현재 제품 source의 소비·생산 경계

- selected CharacterStore `_read`의 strict legacy row는 uid/name/class/gender/attributes이며 새 row도 revision/progression/preferences만 더한다. progression은 experience/level이다. 저장되지 않은 lawful을 legacy upgrade가 생성하지 않는다.
- selected ResourceDocument는 RESOURCE_FIELDS `(10,11,12,13)`와 정확 네 values key를 사용한다. 같은 current actor Resource snapshot·source proof는 HP/MP 권위이며 lawful producer가 아니다.
- `mage-world-v1/mage_world.py:69–100`의 다른 required scalars는 명시 LOCAL opaque policy다. 16/17/18/20 등의 literal0을 lawful로 명명하거나 실제 caster 상태로 승격하지 않는다. 원 world codec도 compiled scalar type/requiredness만 공급하며 product label 의미를 부여하지 않는다.
- `companion-derived-stats-v2`는 same-current companion lease/operation/store·Gear/SKILL를 확인해 원 DerivedStats를 반환한다. 이 객체에는 lawful이 없다. 기존 stats 경계는 재사용하고 record/default를 추가하지 않는다.
- 기존 `SharedSupport.plan:498–506`은 같은 caster derived stats와 explicit `magic_context`의 정확 `{'lawful': int}`를 요구하고 기존 `MagicActor.from_derived`/`resolve_heal`을 한 번 호출한다. MagicActor 기본 lawful0은 source producer가 아니며 lawful이 양수면 실제 치료량이 달라진다.

## 단일 RNG의 실제 경계

이전 amount audit의 exact COMBAT source를 재사용한다. selected CombatSetup은 주입한 `self.rng`를 보유해 같은 객체를 원 providers에 전달한다. 구체 packet-combat 입력은 SystemRandom 한 개를 setup에 넣는다. 하지만 실제 saved UID2의 세 파일에는 RNG instance가 없고, 파일 존재·COMBAT module 선정을 companion의 retained live RNG 보유로 볼 수 없다. source-only 작업에서 runtime 객체를 새로 만들거나 existing private provider RNG를 빼내는 adapter는 만들지 않았다.

필요한 다음 구현은 기존 character-state/resource 권위가 같은 current UID2 binding·lease와 실제 lawful의 provenance/current 경계를 공급하고, 실제 cold configuration 작성자가 하나의 원 RNG owner/instance를 companion `configuration.rng`에 명시 연결하는 것이다. 기존 SourceModule capture·one-cold identity·Rule0/current/learned/Store를 유지해야 한다. source 없이 새 법성 schema/sidecar·lawful0 policy·seeded RNG를 이 작은 adapter에 숨기지 않는다.

이 조건이 공급된 뒤에만 기존 HealingSpell0/reference dice4-value2·단1 resolver 호출을 그대로 소비하는 private 연결이 가능하다. 앞선 range10/current target·정당 learned0/header·공동 custody 결손은 이번 조사에서 해결했다고 주장하지 않는다.

## 확인 범위

원 세 저장파일 pre/post hash/bytes·UID2/class3/실 RESOURCE shape를 확인했고 selected source AST·exact parent 핀을 점검했다. 앞선 stats/magic/SQL/packet 성공검사는 재실행하지 않았다. 제품 import/생성자/runtime/REA/native·포트/패킷/handler·Store/공용/기존 private/큐/Test 변경 0이다. 호출 가능한 adapter·실행 caller/RUN_COMMAND는 없다.
