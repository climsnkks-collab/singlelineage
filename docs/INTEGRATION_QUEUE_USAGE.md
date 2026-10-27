# 단일 통합 큐

완료된 기능 source와 완료된 Test 결과만 `INTEGRATION_QUEUE.json`에 등록한다.
기능 메인은 `integration`, Test는 `test_result`를 enqueue한다. 구현 완료 source의
별도 알림은 보내지 않는다. Test는 완료 결과를 직접 관련 구현 담당에게 한 번
알리고 통합root에는 완료 알림을 보내지 않는다. 구현 담당이 상세 결과를 읽고
수정·후속 구현을 계속하며 완료 변경만 큐에 등록한다. root는 공용판/다음 시험
선정에 필요한 결과 요약만 확인하고 매 결과를 중계하지 않는다. 상세 이력은
기존 artifact/HANDOFF에 보존하며 별도 feedback/ACK 큐는 만들지 않는다.

통합 root가 claim과 담당 배정을 관리한다. 배정받은 worker는 자기 private
변경분을 마감하고, root가 수용·기존 기록·필요 인계를 마친 뒤 complete한다.
claim/complete/hold/release/supersede/restore는 root만 수행한다. 독립 항목은 여러 개를 동시에
in_progress로 처리하며 완료 시 해당 항목만 물리적으로 삭제한다.
root는 쓰기 범위가 겹치지 않게 기능별 worker를 배정한다. 각 worker가 독립 시험의
구현 담당이 완성한 source·실행 시나리오의 실제 병합/충돌을 조정하면 root는 변경분 확인 후 해당 고정 선정판을
즉시 Test에 발주한다. 전기능 공통판·다른 시험 준비를 기다리지 않으며 한 시험의
실패는 그 시험만 수정하고 다음 준비 시험을 계속한다. 공용 client/API는 Test
단일 writer의 완료본을 재사용한다. helper는 의존/제품파일 검증이나 자동 배정을 하지 않는다. 큐는 별도 완료 이력이나
실행 권한을 만들지 않는다. Test 실행 자체는 claim하지 않으므로 root의 다음
통합과 병행할 수 있다. 작업 중 새 enqueue는 가능하다.

## 구현 완료 등록 기준

2026-10-23 사용자 지시. **기능 구현 담당이 실행 시나리오와 caller/실행 명령까지 함께 준비**한다. 통합에서 기능별 시험 업무를 다시 조립하게 하지 않는다. 기존에 통과한 시나리오를 처음부터 다시 만들거나 공용 클라이언트를 복제하지 않는다.

`test_ready:true`인 기능 항목은 기존 HANDOFF/API/manifest와 `evidence`에 다음 내용을 함께 제공한다.

1. **실행 코드와 명령:** 기존 `work/local_original_session/integration-1/packet-test-client-v5/API.md`의 완료 API와 기존 caller/flow를 재사용한 실행 가능한 기능 호출부 경로, 정확 `RUN_COMMAND`(또는 기존 API의 실행 명령). Test는 소유한 사본/결과 경로만 넣고 실행할 수 있어야 한다. 시나리오 설명문·순수 함수검사·코드 조각만으로 준비 완료라고 하지 않는다.
2. **정상 플레이 순서:** 로그인/roster/캐릭터 선택/WORLD부터 필요한 대상 선택→메뉴→항목/수량→확정, 실제 요청·응답/상태를 순서대로 연결한다. 패킷 없는 선택도 기록하고 다음 요청 값 반영을 확인한다. 앞 응답/current 확인 전에 최종 행동을 보내지 않는다. 미확정 클릭/프로토콜은 근거와 미확정 단계로 표시한다.
3. **실제 입력·선정판:** 정확 부모/변경 source·필수 의존/핀, 재사용할 실제 획득/저장 결과와 전체 사본의 원경로/보존 방식, 서버 발급 UID·현재 frame을 읽는 위치를 명시한다. Broker/Peer/Server의 기존 이웃 파일/HERE 계약도 같은 선정판에서 맞춘다. 실제 사본·프로세스/포트 준비와 실행은 Test가 소유한다. 구현 담당은 이를 대신 실행하거나 원본/통과 사본을 수정하지 않는다.
4. **최소 판정·정리:** 실제 수신→올바른 응답→서버 상태/Store→변경상 필요한 복원을 확인한다. 마지막 성공/첫 실패·미확인/오류 원문·부분 저장을 구분하며, 원 client/server/Plan 종료와 소유 자원 정리를 연결한다. 가짜 ACK/성공/current·상태 강제·검사 삭제로 통과시키지 않고 패킷 통과를 NativeUI/입력/충돌 해결로 확대하지 않는다. 이미 통과한 무관 경로는 반복하지 않는다.

공용 client/ready_current/API 대응은 **Test 한 writer의 완료본**을 사용한다. 새 wrapper·별도 송수신 도구·대형 시험체계를 추가하지 않는다. 필요한 공통 API 결함만 기존 예외 절차로 Test에 넘기고, 기능 caller의 부족은 해당 구현 세션이 보완한다. 준비된 작은 기능부터 독립 투입하며 다른 기능 준비를 기다리지 않는다.

정적 facts/의존 source만 완료된 항목은 `test_ready:false`와 실제 소비자/남은 입력을 적는다. 미준비 입력을 위조하거나 통합에 기능 시나리오 작성을 넘기지 않는다. 이미 착수해 완성한 통합 caller는 그대로 인계·재사용한다. 결과를 받은 구현 main은 통과 재사용/실패 수정과 다음 실행 시나리오를 계속 준비한다. 등록·중간진행·ACK 메시지는 보내지 않는다.

동료법사 `01a16769-c8cd-7603-be3d-ff5050d8f20a`, 공격마법 `01a1676e-8cf3-70e3-b21e-edd263f2210c`도 동일하다. 현재 worker와 후속 세션에 이 기준을 인계한다.

## PowerShell 사용

저장소 루트에서 실행한다. **JSON 직접 편집은 금지한다.**

```powershell
python tools/integration_queue.py init
@'
{
  "id": "FEATURE-source-v1",
  "kind": "integration",
  "feature": "FEATURE",
  "owner_thread": "실제-담당-thread-id",
  "summary": "완료한 변경과 남은 실제 제한",
  "source": "work/owned/source-manifest.json",
  "parent": "정확한 부모 source 참조 또는 commit",
  "evidence": ["work/owned/HANDOFF.md", "work/owned/run_feature.py", "work/owned/RUN_COMMAND.txt"],
  "test_ready": true
}
'@ | python tools/integration_queue.py enqueue
python tools/integration_queue.py list
python tools/integration_queue.py show FEATURE-source-v1
python tools/integration_queue.py claim
python tools/integration_queue.py complete FEATURE-source-v1
```

`enqueue`는 stdin JSON 객체 한 개만 받는다. `source`는 integration에서 완료
source 참조, test_result에서 완료 결과 artifact 참조다. `parent`에는 그 결과가
사용한 정확한 source 부모/선정판 참조를 적는다. 파일 존재 확인·hash 계산·제품
검증은 하지 않는다. 경로는 참조이며 별도 요청 파일을 만들 필요가 없다.
`evidence` 생략 시 `[]`, `test_ready` 생략 시 `false`, `created` 생략 시 UTC
ISO timestamp가 붙는다. 같은 ID·내용의 재등록은 revision/상태를 바꾸지 않고
기존 항목을 반환한다. 같은 ID의 다른 내용은 거부한다. 완료 후 재등록 방지는
별도 이력이 없으므로 기존 HANDOFF와 고유 ID 운영으로 관리한다.

```powershell
python tools/integration_queue.py claim FEATURE-source-v1
python tools/integration_queue.py claim OTHER-source-v1 --worker source-worker-2
python tools/integration_queue.py hold FEATURE-source-v1 --reason "필수 결정 대기"
python tools/integration_queue.py release FEATURE-source-v1
python tools/integration_queue.py list --limit 10
python tools/integration_queue.py supersede FEATURE-source-v1 --by FEATURE-source-v2 --reason "수정본으로 교체"
python tools/integration_queue.py restore FEATURE-source-v1
Get-Content -Raw -Encoding utf8 new-item.json | python tools/integration_queue.py enqueue --supersedes FEATURE-source-v1
python tools/integration_queue.py list --status superseded
```

`supersede`는 queued/blocked 항목을 삭제하지 않고 superseded로 보존한다.
`--by`에는 대체 ID·경로·설명을, `--reason`에는 사유를 비어 있지 않게 적는다.
기존 `reason`은 유지하며 `superseded_by`, `superseded_reason`, UTC ISO 시각
`superseded_at`, 이전 상태 `superseded_from`을 기록한다. in_progress 항목은
먼저 release해야 한다. `restore`는 superseded 항목만 이전 queued/blocked로
되돌리고 `superseded_*` 필드를 제거한다. 원래 blocked 사유도 그대로 복원된다.
superseded 항목의 claim/complete/hold/release는 restore를 먼저 하라는 오류로 거부한다.

`enqueue --supersedes <old_id>`는 stdin의 새 항목 등록과 구항목 supersede를
한 잠금·한 원자 저장으로 처리하고 revision을 한 번만 올린다. 대체 참조는 새 ID,
자동 사유는 `Replaced by <새 ID>`다. 구항목이 없거나 in_progress이면 파일·revision과
새 항목 모두 변경하지 않는다. 기존과 같은 ID·내용을 다시 보내면서 같은 구항목을
지정한 경우, 이미 그 새 ID로 superseded된 구항목이면 변경 없이 기존 항목을 반환한다.
그 외 기존 ID로 다른 항목을 교체하려는 요청은 거부한다. `--supersedes`가 없는
기존 동일 등록의 변경 없는 반환은 유지한다. 위 `new-item.json`은 예시 입력이며
별도 요청 파일 생성은 필수가 아니다. 기존 stdin JSON을 그대로 사용할 수 있다.

기본 claim은 배열에서 첫 queued 항목을 고른다. root는 준비 상태를 판단해
명시 ID를 선택할 수 있다. 각 claim은 `claimed_by`에 기본 `root` 또는
`--worker` 값을 기록한다. 여러 프로세스가 동시에 claim해도 같은 항목을
중복 선택하지 않는다. 이미 in_progress인 ID의 재claim은 거부한다.
hold는 해당 ID만 blocked로 바꾸고 claimed_by를 제거한다. blocked와 superseded는 자동 claim에서
건너뛴다. release는 active의 의도적 인계 또는 blocked의 재개에 사용하며
queued로 되돌리고 claimed_by를 제거한다. complete는 지정한 ID가
in_progress일 때 그 항목만 삭제한다. 담당자 표시는 운영 메타데이터이며
추가 인증 계층이 아니다. 다른 항목의 상태/담당자는 바꾸지 않는다.
`test_ready`는 참고 메타데이터이며 자동 시험 발주나 우선순위가 아니다.

## 저장 형식과 잠금

```json
{"schema_version": 2, "revision": 0, "items": []}
```

각 항목은 위 입력 필드와 `created`, `status`를 가진다. 상태는 `queued`,
`in_progress`, `blocked`, `superseded`이며 in_progress에는 `claimed_by`가 붙는다.
hold 시 `reason`이 추가되고 release 시 제거된다.
실제 변경마다 revision이 1 증가한다. list는 기본 최대 20건의 160자 이내
요약(담당자 포함), active_ids와 전체 건수 `total`을 출력하며 `--limit`은 1–100이다.
기본 items는 superseded를 제외한다. `--status queued|in_progress|blocked|superseded`는
지정 상태만 고르며 필터 후 limit을 적용한다. `counts`는 항상 네 상태별 전체 건수이며
`total`도 숨겨진 superseded를 포함한 보존 항목 전체 건수다. show는 숨겨진 항목도 전체 출력한다.

기존 schema 1의 `active_id` 큐도 읽는다. 기존 active의 상태/입력 필드는
그대로 두고 담당자만 root로 해석한다. 읽기/init/동일 내용 enqueue는 실제
파일을 변경하지 않는다. 다음 성공적인 변경이 같은 OS 잠금 안에서 schema 2로
원자 저장한다. top-level active_id는 제거되고 각 항목의 status/claimed_by가
현재 담당을 나타낸다. 기존 enqueue 입력/CLI와 transition 호출은 유지한다.
Python API는 `transition(command, item_id=None, reason=None, worker="root", by=None)`이며
worker는 claim, by는 supersede에만 사용한다. `supersede(item_id, by, reason)`,
`restore(item_id)`, `enqueue(payload, supersedes=None)`도 제공한다. 기존 위치 인자는 유지한다.
구버전 helper를 별도로 복사해 실행하지 않는다.

모든 큐 읽기/변경은 영구 sibling `INTEGRATION_QUEUE.json.lock`의 짧은 OS
잠금으로 직렬화한다. 이 파일은 데이터 큐가 아니며 삭제/교체하지 않는다.
프로세스 종료 시 OS가 잠금을 해제한다. Windows는 msvcrt byte lock,
POSIX는 flock을 사용하며 대기는 최대 30초다. 잠금은 read/modify/write 동안만
유지한다. 같은 폴더 임시 파일에 flush/fsync한 뒤 os.replace한다.
도중 종료로 남은 `.tmp`는 요청이나 복구 큐가 아니며 자동 소비하지 않는다.
init은 기존 큐를 보존하며 잘못된 JSON도 덮어쓰지 않는다.

격리 확인: `python -m unittest discover -s tools -p test_integration_queue.py -v`.
`--queue <path>`는 격리 시험용 경로이며 운영 큐를 분리하는 데 쓰지 않는다.
