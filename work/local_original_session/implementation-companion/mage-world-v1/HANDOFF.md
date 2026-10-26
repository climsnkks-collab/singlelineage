# Mage WORLD v1 — full LOCAL DTO source; runtime selection incomplete

WRITER_RELEASED. `test_ready:false`, `summon_test_ready:false`, runtime UNRUN. 쓰기는 mage-world-v1만 소유하며 queued allied-actor-v1·공용·다른 기능·저장·port·game·REA·queue는 변경하지 않았다.

## 구현한 제품 후손

`mage_world.MageWorldSource`는 실제 CharacterStore INFO에서 class3/gender/name·UID·속성·level을 읽는 full SelfInfo/Player DTO producer다. class0 DTO를 복사하지 않고 기존 INFO→SelfInfo 필드 대응에 따라 full required SelfInfo18필드와 Actor26필드를 명시 구성한다. Actor의 generic opaque scalar/string/bool은 기존 source ledger의 명시 LOCAL literal 정책을 그대로 선언한다. 알려지지 않은 f20 의미·원서버 수치·Native 안전을 새로 확정하지 않는다. appearance는 동결된 allied-actor-v1의 SPR734/1186 명시 LOCAL 정책을 소비한다.

INFO7/8은 realm의 LOCAL 초기 HPMP이며 저장된 현재 RESOURCE가 아니다. seed 결과는 반드시 `INFO_SEED_REQUIRES_ORIGINAL_RESOURCE_RESTORE`로 표시한다. direct WORLD의 현재값은 기존 status.prepare_source_profile → 원 WORLD/RESOURCE restore가 담당한다. current_self_fields가 실제 owner에서 공급되면 HP/MP/max·buff된 속성·무게 등 전체 current SelfInfo를 보존하며 INFO 값으로 덮지 않는다. from_selected_status는 기존 status.fields_for(writer)→current(writer) 경로를 읽고 canonical record/INFO와 같은 UID를 요구한다. 다른 direct player의 status를 동료 RESOURCE로 복사할 수 없다.

별도 live actor 입력 경로는 caller 발급 live_actor_uid와 현재 full RESOURCE 및 실제 map0/packed-position/direction을 모두 요구한다. 없으면 거부하며 직접 플레이의 fallback 위치를 동료 현재 위치로 대체하지 않는다. 이 숫자 입력 검사 자체는 actor 등록 권위가 아니다. source에 actor 생성·등록·UID발급·current generation·송신·소멸 구현은 없다.

`selected_actor.py`는 growth-create 정확 부모의 public selected_actor 함수만 확장한 후손이다. class3은 명시 mage_source로 위 producer를 호출한다. class0의 원 `_project` AST 전체는 그대로이며 기존 initial/royal 경로도 유지한다. 기존 class0 current RESOURCE 대응을 바꾸지 않는다. 부모 diff는 selected_actor.py.diff다.

## 실제 caller 연결

v5 CompanionHost.prepare_direct_world는 require_current(state.direct)로 받은 record를 `configuration.direct_world_for(record)`에 넘긴다. 새 `direct_world_callback(source=..., store=실제_선정_CharacterStore, world_profile=실제realm.world_profile, clock=기존UTC함수, legacy_source=원래_비법사_callback)`가 이 콜백 자리에 맞는다. class3만 기존 store.select(record.name)를 호출해 실제 UID/INFO를 받아 canonical record와 대조한다. 반환은 v5 host가 원래 기대하는 dict2개이며 host의 기존 `status.prepare_source_profile`/rollback·WORLD·RESOURCE restore 연결을 재사용한다. 비법사는 legacy_source로 그대로 넘긴다.

현재 class0 CreatedCharacterScopes의 actor_source 호출부는 `mage_source`를 공급하지 않는다. 정확 cold source capture/loader를 함께 소유한 통합판이 아직 없으므로 해당 call site를 임의 mutable callback으로 우회하거나 공용 scope를 수정하지 않았다. 이 후손 module·동결 appearance module·기존 world/info codec을 동일 coherent selection에 cold capture해야 한다. 현재 최신 scope의 class0 전용 장비/성장/리소스 전제까지 이 소스만으로 지원한다고 주장하지 않는다.

## 최소 확인과 남은 실행 입력

verify_pure.py 11 PASS: 두 gender의 full INFO seed/실 codec 왕복, 전 current RESOURCE 보존+별도 외부UID/위치, v5 host 반환형, 다른 캐릭터 current/INFO mismatch/법사source 누락/외부actor 위치누락 거부, class0 `_project` AST 불변. 이 값은 명시 pure fixture이며 실제 CREATE/login/world 시험이 아니다. verification.json 참조.

직접 패킷 실행 caller/RUN_COMMAND는 아직 제공할 수 없다. 정상 CREATE→INFO→동일 class3 WORLD를 실행할 coherent source selection에 새 mage source capture·콜백 설정과 실제 class3 RESOURCE owner의 첫 생성/복원 연결이 미공급이다. 먼저 이 선택판과 정상 획득된 class3 전체 계정 사본이 필요하다. 실행준비가 되면 기존 packet-test-client-v5로 CREATE/INFO/WORLD/current→close/fresh만 검증하고 원 CREATE/Store를 우회하지 않는다. 명령처럼 보이는 비실행 placeholder나 실패만 하는 run_feature.py는 추가하지 않았다.

동료 소환 시험에는 별도로 실제 allied Player registration producer(발급UID/current generation/character lease/direct owner/world lifetime alias)가 여전히 필요하다. 그 입력이 없는 현재 summon_test_ready는 false다. 외형 producer·full DTO pure 통과를 실제 actor/NativeUI·정상Quit 완료로 올리지 않는다.

정확 부모·동결 의존·제품 hash는 manifest.json. 완료 source만 root가 실제 delta 검토 후 선택하며 이 작업자는 큐를 변경하지 않았다.
