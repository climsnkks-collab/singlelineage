# LOCAL 소환 ACTIVE / FOLLOW 입력 확인

WRITER_RELEASED / SOURCE_FINDING_COMPLETE / source_ready:false / test_ready:false / runtime UNRUN.

선정 `local-summon-packet-trial-v1`의 정확한 source를 읽었다. 제품 변경은 없다. 첫 F101 → 원4E96 진단은 기존 `AWAITING_POSE` 허용 범위로 독립 진행할 수 있다. 이 문서는 그 진단의 선행 gate가 아니다. 별도 실행 caller/RUN_COMMAND를 발명하지 않았다.

첫 미공급 입력은 **SAME_GENERATION_REMOTE_PLAYER_CURRENT_POSE_PRODUCER**다. `AlliedPlayerPort.spawn`은 실제 Root PlayerRegistration·companion lease·독립 actor UID/generation·원4E96 DRAINED 뒤 `pose=None`을 반환한다. `snapshot`은 무조건 None, `step`은 `ALLIED_CURRENT_EDGE_AND_POSE_UNAVAILABLE`로 거부한다. `server_snapshot`의 RESOURCE/placement는 server-only current 권위이고 원 Player의 안정된 pose 증거가 아니다.

선정 Controller의 `_publish`와 `active`는 살아 있는 actor의 실제 spawn drain + `pose_matches` + `moving=False`를 요구한다. `pose_matches`는 안정된 Pose와 actor UID/map/grid 동등성을 검사한다. `tick`은 같은 generation을 검사하고 ACTIVE가 아니면 FOLLOW/step 전에 멈춘다. 따라서 송신 성공, peer가 수신한4E96, owner grid, 일정 시간 경과, server record 또는 가짜 ACK만으로 ACTIVE를 반환하는 후손은 만들지 않았다. lease/current/Store/UNKNOWN 검사는 그대로다.

기존 재사용 가능 근거는 REA216의 원 remote Player 생성(48510→C24A0)과 공통 SC4E2C UID/packedgrid/direction→MovingAction 소비다. 이 근거는 수신 즉시 actionStart가 아님을 명시하고 f2 pre/postcommit도 미확정으로 남긴다. 원 field 근거를 새로 분석하지 않았다. 기존 MoveState는 실제 `MyPlayer` 한 개와 `world_row.my_player_uid`만 관측한다. 해당 코드를 UID 치환해 remote pose로 삼을 근거가 없다. 현재 actor factory는 DTO/clock만 전달하고 remote pose/current edge producer를 받지 않는다. 기존 native audit도 server registration UID/generation→원 current Player object/control/lifetime 연결을 첫 미공급으로 기록했다.

## 다음 담당에게 필요한 최소 입력

1. **원 remote Player current producer:** 정확한 source path/hash와 callable. 실제 등록 record의 actor UID/generation·companion lease·direct owner selection/connection/world lifetime를 원 publication 소비 후 Player lookup/object-control에 연결하고, 같은 map/grid·현재 action/moving·stable 여부를 양성으로 읽는 생성/소비 경로. 반환 전 same generation/current 수명 재확인, unavailable이면 None. UID만 같은 낡은 actor/owner pose/이전 snapshot은 거부한다. 기존 저장 REA를 먼저 재사용하며 구현 채팅은 REA를 실행하지 않는다.
2. **FOLLOW 첫 이동 producer:** 위 current actor의 정확한 현 위치에서 한 타일 방향·목표와 actual current map/edge/occupancy를 확인하는 원 producer, 실제 SC4E2C 발행/ordered reserve-write-drain, source-backed pre/postcommit 의미, 이후 같은 generation의 완료 pose. 기존 selected-owner `MovementService`/CS4E2B는 direct writer의 자기 위치 서비스이므로 그 UID를 동료로 바꾸지 않는다. NPC NpcSpawn adapter도 Player로 치환하지 않는다.
3. **support는 별도 기존 공급 필요:** 이 trial의 cold_inputs는 RESOURCE actor-only로 `shared=None/support_factory=None/interface=None/rewards=None`이고 actor_publication_only=True다. ACTIVE를 확보해도 support 성공이 생기지 않는다. Host는 ACTIVE 뒤에만 scheduler를 부르며, 실제 SharedSupportConfiguration·같은 companion의 SKILL/current Rule/target/range/cost/derived_stats는 기존 담당의 완료본을 받아야 한다. `companion-support-config-v1` 및 `companion-support-catalog-v1`의 미공급을 그대로 재사용한다.

동일 producer가 공급되면 **현재 Allied 포트 한 후손**에서 snapshot/step만 연결하고 원 lease/current/Store/retirement/UNKNOWN을 유지한다. source를 확인한 뒤 Test 소유의 기존 packet-client-v5/API/caller에 정상 login/received roster/선택/WORLD/current → 한F101 → 실제4E96/발급 UID·generation → 실제 pose/current → 필요한 한 FOLLOW 이동 → 최소 저장/strict close를 연결한다. 실제 pose를 공급하지 않는 packet peer만으로 Native pose/AI 성공을 주장할 수 없다. 원 소환 진단 caller는 이미 별도 준비되어 있다.

검증: `python -B work/local_original_session/implementation-companion/local-summon-pose-activation-v1/inspect_source.py`. 정확 부모 pins와 필요한 AST/문자열 계약만 확인하며 제품 import·Host/Controller/Store 구성·handler 직접호출·native read·REA·server/port/socket·시험사본 생성은 없다. `parents.json`과 `verification.json`이 실제 결과다. 현재 main과 recent branch를 확인했으며 unrelated dirty 파일은 보존했다. 이 새 private 경로 외 writer0, 공용/ITEM/Test/client/API/queue 수정0.
