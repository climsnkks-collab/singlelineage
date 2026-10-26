# 기존 실패 시험 분류

2026-10-26 읽기 전용 조사. 먼저 정리할 대상은 **공유 fixture와 private API 호출 계약**이다. 현재 확보한 실패 원문에서 제품 버그로 확정할 항목은 없으며, 별도로 **시험 파일 중간의 `unittest.main()` 때문에 직접 실행 시 시험이 누락되는 결함**을 확인했다. 시험·제품 코드, 저장, 큐, 핀은 변경하지 않았다.

## 판정 범위와 원기록

- 사용자 제공 이전 수치인 broker 16 / launcher 39 / inventory 10 / item_use_session 4 / manual_move_commands 165의 **정확한 실행 원문·Source 조합은 이번 조사에서 확보하지 못했다**. 각 수치 전부를 아래 원인에 배분하거나 현재 실패 수로 주장하지 않는다.
- 현재 소스는 다른 작업자의 미커밋 수정이 진행 중이다. 아래 줄 번호와 정적 판단은 읽은 시점 기준이며, 오래된 로그의 성공·실패를 현재 조합으로 옮기지 않는다.
- [환경 오류 포함 baseline](../runs/latency-20261026-143428/baseline-failures.json): broker 47 tests/errors59, inventory_observe 25/errors50 등. setup와 cleanup이 각각 ERROR이면 한 시험에서 복수 오류가 생기며, subTest 오류 수도 시험 method 수와 다르다.
- [별도 broker 원로그](../runs/latency-claude-20261026/baseline/broker_tests.log): 47 tests/failures1/errors81. 위 baseline 및 사용자 제공 16과 다른 기록이다.
- [기존 환경 요약](../runs/weapon-stance-baseline-20261026-summary.txt): capstone import, TEMP WinError5, 후속 포트 10048 및 직접 실행 수집 범위를 구별한다. 이번에는 게임·서버·포트·suite를 실행하지 않았다.

이하 파일명은 별도 표시가 없으면 `tools/local_original_session/` 기준이다. **로그 확인**은 보존된 실제 오류, **정적 확인**은 코드상 차이, **UNKNOWN**은 원로그와 연결하지 못한 경우다.

## 1. 시험이 옛 계약을 기대함

| 대표 시험 | 근거와 원인 | 정리 방안 |
| --- | --- | --- |
| `broker_tests.AlivePolicyTests.test_only_typed_alive_extends_policy_with_stage_owner_and_drain_checks`, `AttackIntentPolicyTests.test_only_explicit_attack_c2s_extends_frozen_policy_with_existing_checks` | **로그 확인.** `broker_tests.py:1346,1318`은 `_TransportPolicy.__new__`로 생성자를 생략한다. `received_frame`은 `broker.py:196`에서 `item_transfer`를 읽지만 fixture에는 없다. 정상 생성자는 `broker.py:115–116`에서 이 필드를 검증·설정한다. broker 원로그의 첫 두 AttributeError와 일치한다. | **시험 fixture 수정.** 정상 생성자 또는 현재 생성자 계약에 맞는 명시 초기화를 사용한다. 제품에 누락 필드 fallback을 넣거나 opcode 검사를 완화하지 않는다. |
| `broker_tests.AttackIntentRouteTests.test_original_c2s_frame_product_factory_real_route_records_one_intent_no_reply` 등 4개 route 시험 | **로그 확인.** setup은 `attack_tests.py:61 → npc_motion_tests.py:113`의 `object.__new__(PersistentBroker)`를 사용한다. `npc_motion_tests.py:123`의 원 `_send`에서 `_npc_respawn` 누락으로 실패한다. 정상 생성자는 `broker.py:1399`에서 초기화한다. 공격 의미를 검사하기 전의 실패다. | **공유 ConnectedMotion fixture 수정.** 개별 공격 assertion을 삭제하지 않는다. 비활성 서비스 필드를 계속 누락하는 수제 객체 대신 기존 정상 구성 방식을 재사용한다. |
| `broker_tests.OwnerFailureMetadataTests.test_first_bootstrap_actual_eof_completes_during_owner_poll_uses_existing_eof` 및 같은 계열 | **로그·정적 확인.** `broker_tests.py:469,485,529,550,621,658,719,788,812,831` 부근 호출은 `decoder_empty`만 넘긴다. 현재 `broker.py:1895`의 `_poll_checkpoint(..., *, decoder, decoder_empty, ...)`에는 실제 decoder가 필수다. 원로그에 `missing ... 'decoder'`가 반복된다. | **호출 fixture 수정.** 실제 decoder와 해당 상태를 함께 제공한다. 필수 인수를 optional로 바꾸거나 empty 여부 검사를 없애서 통과시키지 않는다. |
| `broker_tests.OwnerFailureMetadataTests.test_late_bootstrap_complete_eof_await_mutation_and_sync_cancel_precede_eof_sideeffect` | 원로그에 callback 횟수 `[0] != [2]`도 있다. 위 필수 인수 누락으로 본문 진입 전에 종료하는 경로가 선행한다. 별도 EOF 제품 결함이라는 증거는 부족하다. | **선행 호출 계약부터 수정.** callback 기대 횟수를 먼저 0으로 바꾸지 않는다. |
| `launcher_tests.ExitOutcomeTests.test_archived_quit_and_broker_row_publish_the_same_source_connection_id` | **정적 확인, 옛 39와 대응 UNKNOWN.** `launcher_tests.py:1129–1140`은 `LocalRealm.__new__` 후 일부 필드만 만든 뒤 `close`한다. 현재 `broker.py:878`의 close는 미설정 `_item_transfer_broker` 등을 읽는다. 정상 realm은 `broker.py:343,356` 등에서 수명 필드를 초기화한다. | **시험 fixture 수정.** 정상 close 계약을 갖춘 realm을 사용한다. 실제 Quit/EOF/connection ID 검증은 유지한다. |
| `launcher_tests.AttackFeedbackFactoryTests.test_feedback_observer_optin_requires_explicit_config_same_real_session_feedback` | **정적 확인, 옛 39와 대응 UNKNOWN.** `launcher_tests.py:3643`은 위 불완전 ConnectedMotion 계열의 `broker_tests.AttackFeedbackRouteTests.asyncSetUp`을 재사용한다. | **공유 setup부터 수정.** factory의 opt-in 의미를 폐기할 근거는 없다. |
| inventory 관련 typed-byte 고정 기대 | **정적 불일치 후보.** `broker_tests.py:1869` 및 `launcher_tests.py:2899,3123` 등에는 2343 기대가 남아 있다. `inventory_tests.py:1504`는 1857을 기대하고, 별도 기존 inventory_observe 로그에도 empty=1857이 기록돼 있다. 서로 다른 fixture의 수치일 수 있어 옛 inventory 10의 원인으로 확정하지 않는다. | **동일 fixture·동일 읽기 계약인지 확인한 뒤 해당 기대만 수정.** 2343을 모두 1857로 치환하지 않는다. 원 읽기·수량·실제 scalar 검증은 유지한다. |

재사용한 [bootstrap EOF 수정 기록](../integration-1/bootstrap-eof-poll-fix/RESULT.md)은 literal row/read/lock, empty decoder, 원 EOF 경로 보존을 요구한다. [respawn drain API](../shared-api/respawn-drain-current/API.md)는 실제 service/operation/write/drain 수명을 설명한다. 이 계약을 불완전 fixture에 맞춰 낮추는 것은 정리 방안이 아니다.

## 2. 실제 버그

**확정한 것은 시험 실행 진입점의 수집 결함이다. 제품 동작 버그는 이번 자료만으로 확정하지 못했다.**

| 위치 | 정적 결과 | 정리 방안 |
| --- | --- | --- |
| `broker_tests.py:1369–1370` | `unittest.main()` 다음에도 시험 클래스가 있다. AST로 확인한 이 파일의 직접 정의 test method 113개 중 66개가 진입점 뒤에 있다. 기존 `python -m tools.local_original_session.broker_tests` 로그의 47개 수집과 부합한다. | **시험 코드 버그 수정:** 기존 main 블록을 파일 끝으로 이동한다. 시험을 import하는 unittest 실행과 파일 직접 실행의 수집 차이를 제거한다. |
| `launcher_tests.py:3635–3636` | 직접 정의 test method 199개 중 49개가 main 뒤에 있다. 직접 실행은 이 클래스 정의까지 도달하지 못한다. | **같은 수정.** 199는 AST 정의 수이며 import·상속까지 포함한 실제 실행 수라고 주장하지 않는다. |

## 3. 환경 의존

| 대표 시험·기록 | 구체 원인 | 정리 방안 |
| --- | --- | --- |
| broker / inventory_observe / world_ai / world_spawn setup | 보존 baseline에는 `cannot import name 'Cs' from 'capstone'`, TEMP WinError5가 있다. 이번 지정 Python의 독립 import도 `ModuleNotFoundError: No module named 'capstone'`로 종료했다. **기존 오류와 이번 오류 문구는 서로 다르지만 모두 의존성 단계다.** | 시험 유지. 현재 런타임 의존성 문제를 제품 assertion 실패와 구별한다. 이번에는 설치·우회·재시험하지 않았다. |
| `feature_config_tests.FeatureTests.test_file_is_bounded_and_rejects_duplicate_or_nonfinite_json` | `feature_config_tests.py:162–173`의 `TemporaryDirectory/config.json` 생성·쓰기 PermissionError. 별도 기존 latency-claude 로그에는 16 tests OK가 있다. | 시험 유지. 실행 환경의 TEMP/TMP·쓰기 권한 문제로 분류한다. config 파서 수정 근거가 아니다. |
| `movement_tests.MovementTests.test_blocked_edge_corrects_without_saving` 등 | `movement_tests.py:30–33`의 공통 임시 저장 setup 실패가 9 errors로 전파된다. 별도 기존 로그에는 9 tests OK가 있다. | 시험 유지. 좌표 commit·저장 회귀로 확대하지 않는다. |
| `restart_tests`의 `test_frozen_sources_fail_closed_in_both_builder_and_validator` | 임시 ROOT·큰 파일 경계를 준비하다 WinError5. 이 기록의 원오류는 SOURCE_CHANGED가 아니다. 별도 기존 로그에는 6 tests OK가 있다. | 시험·고의 핀 변조 반례 유지. 임시 경로 오류를 핀 실패로 바꾸지 않는다. |
| `BrokerTests.test_complete_login_create_select_world_and_shutdown` 및 `world_spawn_tests.BrokerWorldTests` | `broker_tests.py:53,69,92`의 실제 12000/14030 reserve와 임시 저장을 사용한다. 기존 요약의 후속 10048은 이미 사용 중인 포트 오류다. 이 suite들은 전부 순수 함수 시험이 아니다. | 이번 실행 금지 유지. 타 프로세스 종료·대체 포트·포트 정책 변경으로 통과시키지 않는다. |

다른 Source·환경의 기존 OK는 환경 분류의 참고일 뿐 현재 전체 PASS가 아니다. 접근 거부된 `runs/*temp*/tmp*`는 읽지 못했으며 수정·삭제하지 않았다.

## 4. 핀·해시 불일치

**이번에 확보한 실패 원문으로 확정한 현재의 실제 mismatch는 없다.** 다음 시험은 확인 대상의 대표 예이며, 실패가 입증된 목록과 구별한다.

| 대표 시험 | 분류 기준·현재 판정 | 정리 방안 |
| --- | --- | --- |
| `launcher_tests.ProductProfileTests.test_background_attack_candidate_has_exact_pin_and_preserves_foreground_source_block`, `test_attack_product_exact_postpredicate_pin_and_two_explicit_capability_gates` (`:3312,3342` 부근) | 실제 DLL artifact와 profile pin, 고정 product 기대를 비교한다. 과거 launcher 39의 traceback이 없어 **실제 파일 mismatch / 오래된 profile 기대 / 파일 부재** 중 무엇인지 UNKNOWN이다. | 원래 선정 Source와 기대/실제 오류가 일치하는 경우에만 해당 profile/시험을 함께 수정한다. 최신 해시 일괄 덮어쓰기·비교 삭제는 하지 않는다. |
| `inventory_tests.WireTests.test_fixed_wire_and_catalog_pins_are_required` (`:83`) | test 자체가 복사한 SOURCE_PINS에 0 해시를 넣고 `assertRaisesRegex(..., 'SOURCE_CHANGED')`를 기대한다. **이 거절은 의도된 성공 조건**이며 실제 mismatch 실패로 집계하면 안 된다. | 음성 시험 유지. assertion 실패 원문이 있어야 실제 회귀로 분류한다. |
| inventory Store/Observer parent-source 결속 | worker가 읽은 현재 `inventory_store.py:27`, `inventory_observe.py:17`의 parent와 Inventory 조합에는 mismatch 근거가 없었다. 옛 10/4 실패를 현재 이 결속 탓으로 돌릴 수 없다. | 기존 선정 조합을 보존한다. 새 핀·해시 검사나 전수 대조는 만들지 않는다. |

## 5. 주요 suite별 결론과 manual 165의 전파 범위

| suite | 이번 결론 | 남은 불확실성 |
| --- | --- | --- |
| broker_tests | 보존 로그의 필수 decoder 누락, `__new__` fixture 필드 누락 및 환경 오류를 구별했다. 수집 진입점 결함도 있다. | 옛 16의 개별 대응·현재 전체 실패 수 UNKNOWN. |
| launcher_tests | close용 realm/feedback 공유 setup의 정적 결함과 수집 진입점 결함을 확인했다. 바이너리·OS 의존 시험도 포함한다. | 옛 39의 원로그가 없어 항목별 수량 UNKNOWN. |
| inventory_tests | 환경 선행 실패와 byte 수치 기대 후보를 구별했다. 핀 거절·읽기·저장·CAS 반례는 삭제 근거가 없다. | 옛 10의 개별 원인 UNKNOWN. |
| item_use_session_tests | `SessionTests.asyncSetUp = InventoryRestoreOnlyBrokerTests.asyncSetUp` (`:20`). inventory 배송 fixture의 실패가 전파될 수 있다. full uint64 불일치 거절(`:114`)과 await 뒤 source/current 검사 기대(`:240` 부근)는 현재 `item_use_session.py:367–388`과 부합한다. | 옛 4의 원인 UNKNOWN. 이 4개를 모두 옛 계약으로 폐기할 근거 없음. |
| manual_move_commands_tests | AST에서 직접 정의 method **165개** 확인. 아래의 공유 setup 영향부터 정리할 대상이다. | 165 전체가 실제로 같은 오류였는지는 원로그 부재로 UNKNOWN. |

manual은 165개의 독립 제품 결함으로 볼 수 없다. 다음은 **실행 결과가 아닌 정적 의존 관계**다.

| 클래스·method 수 | 공유 준비 경로 | 영향 |
| --- | --- | --- |
| ManualMoveTests 74 (`:25`) | `:29 → npc_motion_tests.ConnectedMotionTests.asyncSetUp` | 위 `_npc_respawn` 누락 fixture에 직접 의존. 대표 `test_two_explicit_goals_use_real_edge_service_store_and_sequence`도 본문 전에 막힐 수 있다. |
| ManualAttackTests 55 (`:1229`) | `:1233 → NpcObservationTests → attack_tests.TargetTests → ConnectedMotionTests` | 같은 준비 경로의 선행 오류가 공격/idle/feedback 검증까지 전파된다. |
| ManualUseItemTests 21 (`:2628`) | `:2632 → item_use_session_tests.SessionTests → InventoryRestoreOnlyBrokerTests` | 실제 Add/Store/drain fixture를 재사용하므로 환경·inventory 선행 오류와 개별 사용 assertion을 구별해야 한다. |
| ManualSourceRestartTests 7 (`:3017`) | `:3023 → broker_tests.RestartRouteTests.asyncSetUp` | Restart/retained reader 준비 계약의 영향. |
| ManualSourceReselectTests 8 (`:3224`) | `:3230 → ManualSourceRestartTests.asyncSetUp`, 이후 정상 broker 재구성 | 뒤에서 정상 broker를 만들어도 앞선 공용 setup 실패를 회복하지는 못한다. |

item-use의 [기존 intent-session 결과](../implementation-2/item-use-request/intent-session/RESULT.md)는 처음의 helper 이름 충돌과 assertion 두 개를 이미 교정했고, uint64·owner/source/Store 오류 전파·실배송 경계를 보존한 고유 10개와 native-match delta 4개의 당시 PASS를 기록한다. 이 계약을 재사용하되 다른 Source인 현재 18개 정의 시험의 PASS로 확대하지 않는다.

인접 suite 중 `game_data_tests.GameDataTests.test_stance_table_is_editable_and_immutable_after_loading`는 [기존 실제 FAIL](../runs/latency-claude-20261026/baseline/game_data_tests.log)이 있다. JSON에서 편집 가능한 자세표(`game_data.py:458–469`)를 전체 고정 수치(`game_data_tests.py:88–90`)와 비교한다. 현재 staff=120은 시험·데이터가 일치하므로 현재 원인은 미재현이다. 불변성·키·형식 검증은 유지하고 편집 가능한 튜닝값의 고정 assertion을 분리할 수정 후보이며, 데이터 로더 버그나 시험 삭제로 단정하지 않는다.

## 정리 순서와 실행 결과

1. **시험 수정:** broker/launcher의 기존 main 블록을 끝으로 옮겨 수집 범위를 일관되게 한다.
2. **시험 fixture 수정:** 필수 decoder와 생성자·close 수명 계약을 공용 준비 경로에서 먼저 맞춘다. 개별 수백 assertion을 고치기 전에 선행 오류를 구별한다.
3. **시험 기대 수정 후보:** 동일 fixture임이 확인된 typed-byte 값·편집 가능한 데이터 수치만 정리한다. 저장·UID·once·CAS·current·수명 검증은 유지한다.
4. **환경:** capstone·TEMP·포트 실패를 환경 원인으로 남긴다. 이번에는 suite 재실행·설치·게임·서버·포트 접근을 하지 않는다.
5. **제품 버그 수정:** 현재 확정할 근거 없음. **삭제 권고 시험도 없음.** 과거 실패 개수만으로 시험 삭제·핀 완화·guard 삭제를 하지 않는다.

이번에 실행한 것은 `git status --short --branch`, `git for-each-ref`, `rg`/`Get-Content` 읽기와 아래의 독립 import·AST 읽기뿐이다. 브랜치 main과 기존 다수 dirty/untracked를 확인했고 브랜치·commit·타 파일은 변경하지 않았다.

```powershell
& 'C:\Users\Chansol\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -B -c 'from capstone import Cs'
```

결과: **exit 1, `ModuleNotFoundError: No module named 'capstone'`**. 기존 로그의 TEMP 권한 오류는 재시도하지 않았다. 같은 Python `-X utf8 -B -`에서 stdlib `ast.parse`로 위 5개 시험 파일을 읽은 명령은 exit 0이며 파일 수정·시험 import·실행은 없었다. 실제 게임 동작, 패킷·저장·복원, 전체 suite 현재 결과와 과거 수치의 개별 대응은 확인하지 못했다.
