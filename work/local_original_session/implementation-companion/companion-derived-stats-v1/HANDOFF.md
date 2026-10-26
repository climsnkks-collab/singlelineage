# COMPANION-MAGE derived stats source boundary

WRITER_RELEASED · source/run/test_ready false · runtime UNRUN.

정확한 `companion-cohort-v2` 선정판을 검토했다. 기존 `SelectedStatsSource`는 직접 선택된 캐릭터만 읽는다. 동료 binding은 실제 별도 캐릭터 UID를 가지면서 직접 선택의 writer/generation/lock을 빌리므로 새 source의 `selection_locked`는 `COMBAT_SELECTED_CHARACTER_INFO_MISMATCH`, 기존 직접 cache의 `capture_locked`는 `...:UID_CHANGED`로 거부한다. 이는 실제 실행 결과가 아니라 소스에서 확인한 거부 조건이다.

`CharacterStore.require_current(active.lease)`의 실제 동료 attributes/class/progression과 canonical SKILL 행은 읽을 수 있다. GearStore가 상속한 공개 `restore(uid, frame)`도 실제 저장 GearState 또는 None을 반환하고, `current_members`는 아이템/Definition을 반환한다. 이 저장 읽기 API 부재를 주장하지 않는다. 첫 미충족 입력은 이 저장 사실을 동료의 실제 current/lifetime과 연결하는 장비·stats producer다. 현재 `GearConsumer.current_fact(writer)`는 직접 선택 캐릭터에 묶인다. owner 장비를 복사하거나 기본 빈 장비로 채우지 않았다. 실제 장비 owner의 동료 fact와 COMBAT의 같은 캐릭터 projection/refresh 계약이 필요하다. 세부 API와 경계는 `source-contract.json`에 있다.

제품 코드는 만들지 않았다. 부여받은 새 폴더에만 기록했으며 공용/이전 source, client/API, 큐, 실행/포트/저장은 변경하지 않았다. `manifest.json`은 정확 14개 선정 source와 cohort 해시를 보존한다. `verification.json`은 AST·핀 및 거부 경계 확인뿐이며 기능/패킷 PASS가 아니다.

검증 명령: `python -B work/local_original_session/implementation-companion/companion-derived-stats-v1/verify_source.py`.

첫 입력이 미준비이므로 packet caller/RUN_COMMAND는 없음, test_ready false. 향후 해당 owner의 정확 source가 공급되면 그 변경 경로만 확인하고 기존 Test client/API를 재사용한다. 별도 wrapper나 전수검사를 추가하지 않는다.
