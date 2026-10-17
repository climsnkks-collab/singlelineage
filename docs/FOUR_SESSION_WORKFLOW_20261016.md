# 4세션 작업 분담 — 2026-10-16

2026-10-16 최종 사용자 의미 정정: **게임을 실행하지 말라는 뜻이 아니다. 실제 게임을 포커스 없이 백그라운드에서 실행해 테스트하라는 지시다.** 통합의 전면 게임 차단 해석은 잘못이며 아래 전체 게임 실행 금지 문구를 현재 중지 조건으로 쓰지 않는다. 전경 기동과 사용자 포커스·커서·전역 입력 간섭은 계속 금지한다. 검증된 기존 PrivateDesktop/hidden_desktop_launch를 재사용해 성공 manual 구성의 표시만 격리하고 internal DLL/guard 모드와 분리하는 최소 연결을 준비한다. SW_SHOWNOACTIVATE 실패 경로·전경 baseline을 다시 실행하거나 가림/포커스 회피 도구를 만들지 않는다. background의 실제 owned non-input desktop/primary-thread/Job·source·정리 증거를 확인하고 통합만 게임/포트/DLL을 실행·복구한다. 창 없는 일반 검사와 실제 백그라운드 게임 검증을 계획대로 계속하며 사용자에게 같은 의미나 표시 허가를 다시 묻지 않는다.

2026-10-16 최신 상태: actual60은 제품 ingress 원래 CS4E2B 왕복2/request2/commit2/correction0·fresh client/idle·별도 save 원점복귀·월드경과60초/Alive를 확인했다. 정상Quit는 false/ownedforce이므로 종료 완료로 세지 않는다. 같은 기동이 사용자 포커스를 가져와 최신 “포커스 주지마”에 따라 실제 게임 추가 기동을 차단했다. 표시 예외를 포커스 전환 허가로 쓰지 않고 source/build/headless 구현·검사는 계속한다. 구현1은 원래 AttackTarget ABI와 공유 command 수명, 구현2는 NPC typed 관측/공격 backend, 통합은 실제 route·launcher 소비와 필수 원본 계약만 연결한다.

최신 정정: 사용자는 계획 완료까지 계속 작업하라고 명시했다. 과거 '이번 단위 종료 후 자동 착수 금지'는 통합의 잘못된 해석으로 철회한다. 중간 결과를 통합하고 다음 필요한 제품 연결을 계속 배정한다. 현재 소유는 구현 1의 새 manual_move_commands.py/tests, 구현 2의 새 npc_session.py/tests 및 자기 npc_edge 접점, 통합 worker의 launcher/feature_config 및 해당 tests다. 기존 완료 후보·원본·저장 보존과 일반 검사 무창/무포커스 원칙은 유지한다.

사용자가 구현2·통합1·REA1 체계와 작업 재개를 승인했다. 최신 지시는 통합의 현재 NPC 이동 단위만 마무리하고 구현 1·2에 후속 작업을 나누는 것이다. 모든 메인은 `gpt-6.1-sol` / `xhigh`, 모든 워커는 `gpt-6.1-sol` / `high`를 명시한다. 기존 일시 중지는 해제됐다.

| 채팅 | ID | 소유·첫 작업 |
|---|---|---|
| 싱글리니지 구현 1 | 01a1402d-7c38-70b0-8f03-981c79dafed0 | 고정 `native-manual-move/`는 읽기 기준으로 보존하고 `work/local_original_session/implementation-1/manual-move-continuous/`에 연속 MoveGoal 명령·hook 수명 source/build. runner 차단·공유 슬롯은 변경 금지. 기존 API 보호·30초 필터 작업은 재개하지 않는다. |
| 싱글리니지 구현 2 | 01a142a7-f954-7d50-b117-ebdb4e5a9643 | 새 `tools/local_original_session/npc_edge.py`/`npc_edge_tests.py`의 NPC 전용 exact-edge adapter, 필요한 자기 소유 movement/edge 접점과 `implementation-2/`. npc.py/npc_motion.py/broker.py는 수정 금지. |
| 싱글리니지 통합 1 | 01a142a7-febb-7781-b0b6-a7837fb596f9 | 공유 launcher/commands/broker/desktop/관측 연결, 설치·게임·포트·실제 실행, ACTIVE_TASK·현재계획·REA 큐·결과 통합 |
| 싱글리니지 REA 1 | 01a1402c-454a-7ec2-98c5-a287adb203b5 | 큐 순서대로 필요한 원본 계약 분석·결과. 제품·게임·설치·ACTIVE 변경 금지 |

## REA 작업 노트와 순서

현재 분배 결과: 구현 1의 `implementation-1/manual-move-continuous/`는 source/build 준비 완료(W4WX·제품 접점 mock88, 수명 지적1개 해결), 구현 2의 npc_edge.py/tests는 실제 writer/PersistentBroker·retained owner/claim 결속을 보완해 callback 준비 완료(초기10/영향5/최종3 결과 범위별 재사용)다. 통합은 양 구현 메인의 검토 결과를 재사용하고 핵심 코드/결과/소비 계약/해시를 확인했다. 공유 소비 설정·게임 실행·설치는 하지 않았다. 두 구현 모두 이번 단위를 종료하고 다음 단위를 자동 착수하지 않는다.

- 구현1은 `work/local_server_rea_20261016/requests/implementation-1.md`, 구현2는 `requests/implementation-2.md`만 작성한다. ID·막히는 계약·기존근거·필요한 답·결과경로를 짧게 남긴다.
- 통합만 `work/local_server_rea_20261016/REA_QUEUE.md`의 처리 순서를 갱신한다. 현재 수명 문제에 필요한 질문을 먼저 두고 요청이 독립적이면 구현은 계속한다.
- REA는 큐를 읽어 한 건씩 처리하며 상태·답은 자체 결과파일과 `ANALYSIS_RESULTS.md`에 남긴다. 큐를 직접 고치지 않아 동시 쓰기를 피한다.
- 새 요청·결과·통합 가능 상태가 생기면 해당 노트 경로를 통합에 전달한다. 사용자는 이 4세션의 작업 분배·REA 요청/결과·통합에 필요한 메시지를 승인했다. REA 재승인은 묻지 않는다.

## 실행과 검토

실제 게임 실행·설치·native Job/포트/사용자 저장은 통합1만 소유한다. 구현은 source·build·pure 필수 영향검사까지 준비한다. 일반 검사는 창·포커스 없이 백그라운드에서 진행하며 게임 표시는 실제 화면/입력 확인이 꼭 필요한 때만 통합에서 수행한다. 현재 후속 단위는 게임/native 설치·실행·포트·캡처·마우스·커서·포커스·desktop 전환·SendInput 없이 진행한다. actual55의 새 이동 runner는 BACKGROUND_LAUNCH_UNVERIFIED 차단을 유지하며 같은 기동 경로를 재사용하지 않는다.

공유 checkout의 기존 commitless master/untracked·원본·동결 후보·사용자 저장·보관은 보존한다. 소유 밖 변경은 통합에 요청하고 같은 파일을 동시에 쓰지 않는다. 필요 검사와 구현 메인의 실제 delta 검토1회를 재사용하고, 통합은 핵심 변경·증거·실제 소비 연결만 확인한다. 승인·다중검토 사슬이나 별도 영구 도구 프레임워크를 만들지 않는다.

당면 작업은 원래 MoveGoal 연속 명령 수명과 NPC exact-edge 공급을 독립 구현한 뒤 통합하는 것이다. 정상 Quit/기존30초 원인은 미해결로 보존하되 다음 구현의 선행 gate로 두지 않는다. 수동34의 사용자 플레이/40.09초/이동commit23/정상exit0은 한정 근거이며 다른 구성의 수명·현재 NPC 동작 완료로 합산하지 않는다.
