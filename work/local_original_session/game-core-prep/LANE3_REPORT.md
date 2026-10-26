# LANE3 월드 모듈 연결

2026-10-26~27. 사용자 이번 task의 직접 구현·시험 승인으로 진행. 기존 main과 dirty 작업을 보존했고 commit/ACTIVE_TASK 수정은 하지 않았다. 서버 코드 작성·고정 포트 시험은 이 작업 하나가 순차 소유했다.

## 연결과 근거

- `world_handlers`에 0960 확장을 등록했다. 비대상 아이템은 기존 아이템/장비 경로로 돌아간다. 변신299는 `SL_EXPERIMENT_POLY=<form key>` opt-in에서만 raw0 사용을 받는다. 원본 선택 파라미터를 해석했다고 주장하지 않는다. run390의 SC_POLYMORPH_NOTI4E5C required f1=현재UID, f2=선정SPR, f3=현재 무기 자세만 송신하며 f4..7은 보내지 않는다. 기존 Actor4E96 재생성을 변신 전용 알림으로 대체하지 않았다.
- 변신 비용은 기존 kit replace CAS·0965/0978이며 이후 같은 월드 monotonic scheduler로 만료·원 SPR 복원을 예약한다. 재변신은 이전 타이머를 취소하고 접속 종료 시 타이머/상태를 정리한다. 접속을 넘는 지속시간 저장은 제공하지 않는다. f3=0의 맨손 자세 완전 복원은 run390의 UNKNOWN이므로 전체 변신 동작은 실험 뒤다. 허용되지 않은 현재 무기는 기존 정상 장비 경로로 먼저 해제해야 하며, 변신 중 허용되지 않는 새 무기 착용은 거절한다.
- `world_town_services`의 시작 로더를 연결했다. native stem `inn`, `lucas1`, `lucas2`와 실제 action literal만4E44/4ED4로 사용한다. 전달 완료 메뉴·현재 NPC 세대·맵·거리 검사를 기존 등록부에서 재사용한다. `room`은 명시 LOCAL100A를 기존 인벤토리에서 차감한 뒤 full4E38로 HP/MP 완전 회복한다. 100A는 원본/L1J 여관 요금이라는 주장이 아니다. 창고는 연결하지 않았다.
- Selena/Lucas의 Classic NPC template·정식 sprite 대응은 현재 REA 자료에서 미확정이다. 임의 외형 packet을 만들지 않아 기본 화면에서 서비스 NPC가 보인다고 주장할 수 없다. Zeno/Keith의 미확보 메뉴 stem도 송신하지 않는다. map4/68의 준비되지 않은 데이터는 비용 차감 전에 거절한다.
- 최종 기본 월드는 미확정 서비스 NPC를 자동 등록하지 않는다. 보이지 않는 충돌체를 기본 플레이에 추가하지 않도록 기존 `SL_WORLD_TOWN_CANDIDATES` 명시 후보 또는 `-MapExp`에서만 backend 실험 등록을 허용한다. 메뉴 source는 시작 시 준비해 둔다. 실험 등록 자체도 sprite/화면 표시를 확정하지 않는다.
- 같은 맵 서비스도 기존 lane2 `4E40 → 4EE0 → 새로 보이는4E96` 경로를 재사용한다. 현재 Lucas `island-dungeon` 목적지 map0(32478,32853)는 M3_DUNGEON_DATA:51의 native enter-map 후보이며 소비자·요금이 미확정이다. 따라서 `experimental_teleporters`에 분리했고 `-MapExp 1/2/3`에서만 로드한다. 요금0·방향5는 명시 LOCAL 실험이다. `-MapExp 2`에서만 다른 맵 전환을 허용하되 실제 데이터가 없는 map4/68은 여전히 준비 안 됨이다. 이 거절은 잔액 부족 판정보다 먼저 처리한다.
- `world_alignment`는 시작 시 한 번 카탈로그를 읽고 기존 combat kill-once callback에서 M1 몬스터 성향을 계산한다. run395가4E38.f18·전체 상태 갱신 경로를 확정했으므로 기존 full status에 현재 성향을 넣는다. `progression.json` 기존 version1 행을 읽으면서 optional lawful(옛 행 기본0)을 보존·저장한다. 사망 시 per-mille 확률·최대 시도 수만 broker report에 기록하고 RNG 추첨·아이템 이동·실제 드롭은 하지 않는다. 계산식은 출처가 있는 LOCAL/L1J 정책이다.
- test_knight: Classic299 변신5,162 귀환10,23 순간이동10, 기존 활11 유지·화살29를200개로 보충했다. 사용자 manual-user-play는 수정하지 않는다.
- `start-manual-play.ps1 -TestKnight -PolyExp`는 기본 선정 form `orc`를 opt-in하고 `-PolyForm <key>`로 명시 변경한다. 이 실행 명령은 사용자 수동 확인용이며 이번 자동 시험에서 보이는 실행은 하지 않았다. 기존 broker 핀을 갱신했고 스크립트 UTF-8 BOM을 유지했다. 새 guard/pin/검증기는 추가하지 않았다. manual-test-knight의 inventory/equipment 두 파일만 삭제했으며 progression은 원래 없었다. characters/positions/account-settings와 manual-user-play는 변경하지 않았다.

## 검증

최초 world_handlers_tests는 등록 opcode 집합의 기존 기대값 한 건이 실패했으며 새0960 등록에 맞게 수정했다. game_data_tests의 옛 키트 수량/끝 항목 기대값 두 건도 요청한 키트에 맞게 수정했다. 이후 대상 시험은 통과했다. 원 실패 출력은 세션에 보존되어 있다. 시나리오 fixture의 귀환 주문서는 새 키트에 이미 있으면 중복 발급하지 않도록 바꿨다.

- 사전 전체 시나리오: `runs/hunt-scenarios-vyi_n7e_`, death/reconnect/town/items 모두 SUCCESS, 모든 broker cleanup_complete=true. 이 뒤의 작은 연결 수정까지 포함하는 최종 실행은 별도로 아래에 남긴다.
- 개발 소켓 시험 첫 실행: `runs/lane3-services-etg88_d0/result.json`. 소비/만료/여관은 관측했지만 시험용 장비 객체의 `_last` 누락으로 보고 단계가 실패하여 cleanup_complete=false를 그대로 보존했다. 이 결과를 정리 PASS로 바꾸지 않았다. 해당 시험 프로세스는 종료됐고 고정 포트는 해제됐다.
- 재실행: `runs/lane3-services-1lhx3kuj/result.json`. 정상 소켓 로그인 뒤 실제 UID 주문서5→4, required f1/2/3의4E5C SPR3906, 실제 monotonic scheduler의 시험용10초 만료→원 SPR61, 허용되지 않는 활 거절, 여관1000→900A/fullHP20·MP10, 유료 메뉴 재사용 거절, Lucas 현재 메뉴→같은 map0(32478,32853) 이동을 관측했다. 상태 SUCCESS·cleanup_complete=true·broker failure 없음. 두 서비스 NPC UID는 화면 수신이 아닌 현재 owner에서 읽었고, 장비 owner를 대역으로 연결했으므로 **개발 fixture 결과이며 정식 Native/화면 PASS가 아니다**. 정상 변신1800초를10초로 바꾼 것은 이 시험 프로세스의 catalog 사본뿐이며 제품 데이터는1800초다.

## 마감 결과

전체 순차 실행 원문은 [`runs/lane3-validation-20261026-235602/summary.json`](../runs/lane3-validation-20261026-235602/summary.json)과 같은 폴더의 개별 `.log`/`scenarios.json`/`loopback.json`에 보존했다. 최종 NPC 기본 등록 정책 수정 뒤의 영향 범위 재시험은 [`final-recheck.json`](../runs/lane3-validation-20261026-235602/final-recheck.json)이다. 앞 실행과 최종 재시험의 source SHA256은 각 JSON에 따로 있으며, 서로 다른 Source의 결과를 합쳐 전체 원본 동등성 PASS로 주장하지 않는다.

- `hunt_bot_scenarios --scenario all`: exit0, death/reconnect/town/items 4개 모두 SUCCESS, 전 epoch cleanup_complete=true. 재접속 사냥3분13처치·EXP75/레벨1·장비/인벤토리 보존, 성향32 저장을 확인했다. 귀환162는10→9개 소비·저장 후 같은 맵 마을 이동이 일치했다. 프로필은 `scenarios.json`의 output_directory에 보존했다.
- `hunt_bot_loopback --minutes 5`: exit0, 실제 사냥300.031초,24처치·35줍기·레벨2·EXP150·성향61 저장, 사망0, 요청 실패0, broker failure 없음, cleanup_complete=true. 프로필 `runs/hunt-loopback-pfdpht9n`을 보존했다. 이 두 장시간 소켓 실행은 마지막 미확정 NPC 기본 등록 제외 수정 전 Source에 속한다. 기본 등록 제외 수정 자체는 아래 월드/이동 재시험 범위로 확인했다.
- 요청 회귀22묶음/413시험을 전부 순차 실행했다. 최초 `world_integration_tests`의 수동 주입 fixture에 새 성향 상태가 없어1 ERROR, 미확정 NPC 기본 등록으로 기존 기대 목록과 달라1 FAIL이었다. 원 실패 `.log`는 보존했다. fixture에는 성향 상태를 초기화했고, 제품 기본 등록은 위와 같이 실험 opt-in으로 고쳤다. 최종 source의 world_integration12·world_spawn8·edge33·world_handlers12·world_town14를 순차 재실행해 모두 exit0을 확인했다. 나머지17묶음은 앞 실행의 통과 결과를 해당 범위로 유지한다. 추가 game_data5·world_handler_adapter7도 exit0이다. 회귀 결과는 Native 화면 PASS가 아니다.
- 헤드리스는 지정 `run_auto_knight_m1.ps1`로 **1회** 실행했다. 이름 `lane3-headless-20261027-001419`; 결과 [`runs/lane3-headless-20261027-001419/result.json`](../runs/lane3-headless-20261027-001419/result.json). helper stdout은 `RUN_EXIT=2`이며 PowerShell wrapper exit0을 게임 성공으로 취급하지 않았다. Login/Slot/SelectOK 호출 RETURNED, 키트 FIRST_GRANT 행 CLIENT_CONFIRMED, 초기 장비 동기화 DRAINED까지 관측했다. 이후 `ATTACK_WAIT`에서 `MANUAL_ATTACK_ACTION_SNAPSHOT_UNKNOWN`/strict consumer refusal이 발생했고 최종 `MANUAL_MOVE_TERMINAL_UNKNOWN`·SESSION_FAILURE다. 실제 이동0, 정상 종료 확인false, Native 공격 시작/화면/HP는 UNKNOWN이다.
- 헤드리스 종료는 **FORCED_CLEANUP**이다. owned_job_empty=true, broker cleanup_complete=true, 원 bridge 슬롯은 helper finally에서 baseline 복원했다. 강제 정리를 정상 Quit나 성공으로 바꾸지 않았다. 최소 미완 입력은 같은 native 공격 feedback 이후의 유효 action snapshot이며 기존 manual attack reader/consumer 경로가 생산해야 한다. guard 제거·준비 강제·가짜 성공으로 통과시키지 않았다. 기본 등록 정책 수정 뒤 추가 헤드리스를 반복하지 않았다.
- 보이는 실행·화면 캡처·전역 입력은 사용하지 않았다. 헤드리스 원 결과도 background=true/private_non_input_desktop=true/cursor_focus_global_input=false다. ACTIVE_TASK·사용자 manual-user-play·원본 LC/자원은 수정하지 않았다. 기존 dirty 변경은 이번 결과에 임의 포함/commit하지 않았다.

## 사용자가 화면에서 확인할 것

`-TestKnight -PolyExp`의 실제 변신 선택 UI가 이 실험 raw0 경로를 호출하는지, 변신 전후 정지/이동/공격·허용 무기 자세·원 외형 복원과 입력 복구를 확인해야 한다. 정상1800초 타이머의 Native 화면 만료, 특히 f3=0 맨손 자세 완전 복원은 미확인이다. 서비스 NPC는 정확 외형 대응이 공급되기 전 기본 화면 확인을 보류한다. 대응 뒤 inn/루카스 메뉴·결제·HP/MP·같은 맵 이동 후 카메라/입력·주변 actor 수명을 확인하며 map4/68은 자원/지형 준비가 먼저다. 제품30분 플레이 완료나 전체 원본 동등성 완료는 주장하지 않는다.
