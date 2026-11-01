# Broker 월드 모듈화

상태: 요청한 구조 변경·전후 회귀·포트 격리·헤드리스 1회 마감. 시험 실행 소유는 02:20:14 해제했다. 헤드리스는 FORCED_CLEANUP이며 정상 종료/화면 동등성 PASS가 아니다. 최신 직접 요청 범위만 수행했고 일반 제품 재개·동료 구현은 포함하지 않는다.

## 구조와 범위

- 기존 `main` 작업 폴더에서 작업했다. 시작부터 있던 다수의 dirty/untracked 파일은 보존했고 commit·브랜치 생성·ACTIVE_TASK 수정은 하지 않았다.
- broker의 월드 구현 41개 메서드를 기능 파일로 옮겼다. broker는 5,720행/360,318바이트 → 4,270행/271,104바이트다. `PersistentBroker` 안에 `_world_*` 구현 메서드는 없다.
- `world_bridge.py`: Context, 기존 native 소비자/시험용 동적 메서드 호환 연결, 월드 초기화 연결·runtime 시작/정지·이벤트·송신 계약·수신 한 곳·정리·보고.
- `world_feature_session.py`: 준비/바인딩, 요청 후처리, flush/send, 기존 handler 연결, 월드 이탈.
- `world_feature_kit.py`: 시작 키트, 키트 CAS 소비·배송 연결, 장착 준비 연결, 자세·자기 actor 갱신.
- `world_feature_combat.py`: 공격·탄약 준비, HP바/화살 실험.
- `world_feature_reward.py`: 진행 저장·복원, 보상 연계, 드롭 줍기·인벤 반영.
- `world_feature_life.py`: 사망·경험치 패널티, 리스타트 연결·마을 귀환 저장.
- `world_feature_town.py`: 마을 NPC/상점 메뉴 준비, 여관·텔레포터·창고 거래.
- `world_feature_items.py`: 물약·헤이스트/버프·주문서, 강화·변신·만료.
- `world_feature_maps.py`: 이동 후 월드 반영, terrain/edge fallback, 맵 전환·순간이동.
- `world_feature_stats.py`: 장비/레벨 능력치·전투 프로필, SelfInfo/Actor 보정.
- `world_feature_alignment.py`: 처치 성향 계산과 상태/진행 연결.
- `world_handlers.py`의 `FEATURE_MODULES`, opcode→처리기 목록과 12개 hook slot으로 등록한다. 새 파일+등록 한 줄 확장은 [WORLD_FEATURE_GUIDE](WORLD_FEATURE_GUIDE.md)에 적었다. 기존 pure `HANDLERS`/HostContext/HostStore 계약은 재사용한다.
- Context는 기존 broker의 송신, 선택 세션, 인벤 저장/프레임·세대·동적 override를 연결한다. 실제 패킷 생성기·CAS·저장 형식·소비/정리 순서는 기존 구현을 사용한다. 새 guard·pin·요청 중 해시/판독 대기는 추가하지 않았다.

broker에 남은 월드 관련 코드는 모드/정책 스위치와 `world_bridge.receive` 수신 전달 한 곳, 수송 이벤트 대기·송신/정리/세션 콜백 연결이다. 원래 로그인에서도 쓰는 `_world_frames` 캐시·원본 world DTO 프레이밍/검증·비월드 HP status의 `world_status` 경로는 공용 native 코드이므로 유지했다. 키트 전용 처리 본문은 기능 파일로 옮기고 호출만 남겼다.

## 포트

시험 helper의 `SL_TEST_PORT_BASE` 기본값은 12000이고 두 번째 물리 포트는 base+2030이다. 22000이면 22000/24030, 26000이면 26000/28030이다. 정책·Peer·claims의 논리 키는 12000/14030을 유지하고, 시험이 명시한 `listener_ports`로 reserve/connect/start/accept의 물리 포트만 바꾼다. 제품은 환경변수를 읽지 않으며 실제 게임 접속 기본 포트는 그대로다.

포트 변경 파일은 `test_ports.py`, `broker_tests.py`, `world_spawn_tests.py`, `world_ai_tests.py`, `hunt_bot_loopback.py`, `hunt_bot_scenarios.py`, `world_lane4_connection_tests.py`다. 마지막 CLI의 직접 HuntBot 인수에도 물리 포트 매핑 2줄을 적용했다. `hunt_bot.py`와 launcher의 게임 접속 포트는 수정하지 않았다. helper 기본값·다른 base 매핑과 구문 확인을 마쳤다.

동시 실행에서 PID86472는 22000/24030, PID87636은 26000/28030을 사용했다. 02:12:11.211~02:12:46.363 사이 35.152초 동안 네 listener의 동시 존재를 34회 관측했고, 두 프로세스는 각각 spawn+integration 20tests OK였다(36.636/36.679초). 정리 후 listener0. 로그는 `-after-ports-{base}-stdout/stderr.log`, `-after-ports-overlap.json`이다. PowerShell Start-Process가 child ExitCode를 null로 남겨 **OS 종료코드는 UNKNOWN**이며 OK 출력과 실제 동시 listener/정리 관측을 충돌 검증의 근거로 쓴다. 로그 수집 명령의 exit1을 제품 실패나 child 종료코드로 해석하지 않았다.

## 전후 회귀

원문 접두사: `work/local_original_session/runs/modularize-20261027-011835-before-`, `modularize-20261027-011835-after-`.

| 범위 | 변경 전 | 변경 후 |
| --- | --- | --- |
| 지정 unit 25종 | 637 tests, launcher FAIL1/ERROR2, 나머지 24종 exit0 | 637 tests, 모듈별 counts/결과 동일. launcher의 같은 FAIL1/ERROR2 외 신규 실패0 |
| hunt_bot_scenarios --scenario all | exit0, 4종 16항목 SUCCESS, 정리 모두 true | exit0, 같은 4종 16항목 SUCCESS, 정리 모두 true |
| hunt_bot_loopback --minutes 5 | 300.028초, 22처치·27줍기·Lv2·사망0, 서버 오류 없음·정리 true | 300.034초, 같은 22처치·27줍기·Lv2·사망0, 서버 오류 없음·정리 true |
| 두 포트 설정 동시 시험 | 해당 없음 | 각20tests OK, 4개 listener 동시 35.152초, 정리 후0. OS ExitCode UNKNOWN |
| 헤드리스 | 새 실행 없음: 사용자 지정 1회는 변경 후에 실행 | 유일1회 RUN_EXIT=0, FORCED_CLEANUP. native cleanup exit_code=1, 정상종료 false/logout UNVERIFIED. broker 오류 없음·정리 완료 |

기준 unit 실행 순서: world_ai, world_spawn, world_m1_reward, world_integration, edge, broker_tests, launcher_tests, stance, feature_config, restart, movement, inventory_store, inventory_observe, world_handlers, world_town, world_shop, world_item_effects, world_maps, world_terrain, world_ammo, world_polymorph, world_town_services, world_alignment, world_enchant, world_stats. 각 모듈 원문은 접두사 뒤 `<module>_tests.log`다(broker/launcher는 각 `broker_tests.log`/`launcher_tests.log`).

기존 launcher 실패는 범위 밖으로 보존했다. 변경 후 테스트명과 오류 시그니처가 모두 같음을 대조했다.

1. `LifecycleTests.test_explicit_source_quit_host_binds_after_features_and_closes_after_two_phase_poll`: source_quit 보고가 None인 상태에서 subscript TypeError.
2. `ProductFeatureNpcTests.test_config_factory_real_session_edge_policy_write_drain_commit`: 닫힌 feature poll의 `npc` KeyError.
3. `InventoryProductTests.test_client_wait_does_not_rebind_changed_selection_after_delivery`: 기대 `MANUAL_MOVE_TERMINAL_UNKNOWN`, 실제 `FEATURE_INVENTORY_CLIENT_SELECTION_CHANGED` 오류 문자열 불일치.

추가 호환 확인은 지정 637개와 별도로 기록한다.

- `world_handler_adapter_tests`: 7개 중 ERROR4. 기존 SimpleNamespace broker에 `_world_warehouse_trade` stub이 없어 발생했다. HostContext 16개 메서드의 전후 본문이 동일함을 확인했고, 변경 전 `world_handlers.py.before` 원문을 별도 모듈로 읽은 국소 비교에서도 같은 4개 ERROR를 재현했다. 이 비교는 `__file__`만 원래 위치로 복원하고 다른 의존성은 현재 것을 사용한 범위다. 초기 로더/상대경로 준비 실패와 최종 `-before-world_handler_adapter_tests-snapshot-origin.log`, 변경 후 원문을 모두 보존했다. 제품 코드는 고치지 않았다.
- `world_lane4_connection_tests`는 unittest 발견 대상이 아닌 `--output <새 폴더> --case all` CLI다. 최초 잘못된 unittest 호출의 0tests/NO TESTS RAN도 보존했다. 올바른 기본 CLI는 강화14+창고9=23 checks SUCCESS/exit0였다. 포트 누락 2줄 보완 뒤 base22000 CLI도 같은 23 checks SUCCESS/exit0, 실제 22000/24030 listener 관측·정리 후0이었다. 새 결과는 각각 `modularize-20261027-011835-lane4/`, `modularize-20261027-011835-lane4-port22000/`에 귀속한다.

이 시험들은 loopback/development 범위이며 native 화면·입력·전체 원본 동등성 PASS로 확대하지 않는다. 처치/줍기 수와 지연은 RNG·스케줄링에 따라 달라지므로 정확한 같은 숫자를 동등성 조건으로 쓰지 않는다.

## 보존과 핀

- 변경 전 broker SHA256 `280135f497ed2e51c7c36f4f33cfc1016b55f3a744b049299767d2e7ef5bcb29`.
- 적용 broker SHA256 `c655c5532cc9343912ec4594f7323fad2fab320dc79dc2aa3aba0696b3a4ab45`.
- 같은 run 접두사의 `broker.py.before`, `world_handlers.py.before`, `start-manual-play.ps1.before`에 이번 작업 직전 원문을 보존했다.
- canonical `work/local_original_session/manual-play/start-manual-play.ps1`의 기존 broker 핀 값만 갱신했고 UTF-8 BOM `EF BB BF`를 유지했다. 수정 전후 pin 대상은 24개로 같으며, broker 해시 교체 외의 내용이 동일함을 확인했다. 새 모듈 핀은 추가하지 않았다. 조사 범위에서 현행 PS1을 pin하는 live 상위 파일은 없었으며 과거 실행의 hashes.json은 보존했다.
- `npc_ai.py`, `world_companion.py`, `companion_ai.py`, 사용자 `manual-user-play`, 원본 클라이언트/자원·저장·기존 로그·공식 큐는 수정하지 않았다. 화면 캡처·보이는 실행을 하지 않는다.

## 헤드리스 실제 결과

실행 전 LC.guard가 없어 지정 `run_auto_knight_m1.ps1 modularize-20261027-011835-headless`를 기존 owned background/non-input desktop 경로로 정확히 한 번 실행했다. 스크립트 `RUN_EXIT=0`이지만 `exit_outcome=FORCED_CLEANUP`, `normal_exit_verified=false`, `game_logout_protocol=UNVERIFIED`, 강제 정리된 native exit_code=1이다. root의 정상 종료를 주장하지 않는다.

공격 intent COMMITTED/feedback DRAINED, 이동 34요청·34commit·0correction과 idle hold 완료를 기록했다. render·HP·combat_effect는 UNKNOWN이다. broker는 CLOSED/failure_code=null/cleanup_complete=true/active_tasks=0/registry_sessions=0이고 owned_job_empty=true다. 최종 LC.guard0과 12000/14030/22000/24030/26000/28030 listener0을 다시 직접 확인했다. 슬롯 bridge SHA256은 기준 `1d1f60a03144f0214bee56c4a875d4444d51811649135a1eaab82ec2e2899f75`로 복구됐고 시험 env는 unset이다. headless run 폴더의 PNG0도 확인했다.

원결과는 `work/local_original_session/runs/modularize-20261027-011835-headless/result.json`, `modularize-20261027-011835-headless-launch.log`, 새 validation profile의 `execution.log`에 보존했다. 정상/강제 종료·미확인을 그대로 남기고 재실행하지 않았다. 최종 broker hash와 기존 PS1 pin 일치·BOM 유지도 재확인했다.
