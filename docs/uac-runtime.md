# 지속 관리자 도우미 — 새 루트 구현과 검증

2026-10-04. 새 구현은 `tools/admin_runtime/`에 있다. 이전 원본·보관본을 수정하거나 이전 도구를 실행하지 않았다. 원본 루트의 RAM broker·cold route·Gate producer와 수백 source pin을 통째로 복사하지 않고, 기존 metadata IO의 Windows share-delete/ReplaceFile 원리와 full rule scope audit 중 필요한 함수만 가져왔다.

한 번 승인한 관리자 프로세스가 계속 살아 있으면 이 도우미의 고정 작업은 같은 권한을 상속하는 자식 PowerShell에서 이어진다. core는 UAC·자동 elevation/재시작을 요청하지 않는다. 별도 고정 launcher만 최초 필요한 `RunAs` 1회를 요청한다.

## 최신 종료와 통합 — 2026-10-04 17:05 KST

1회 실제 UAC의 Host는 약17:02에 수명 만료로 원래 True/True baseline을 복구하고 durable ledger/status CLOSED를 기록한 뒤 정상 종료했다. launcher exit0/HOST_EXITED, active CIM의 Host/supervisor/old guardians/LC 부재, 종료 후 양쪽 firewall store의 두 Enabled=1을 확인했다. 현재 살아 있는 관리자 Host는 없다. True/True는 과거 local gate 복구이며 정상 온라인 접속 성공이 아니다.

해제된 source pin/lease·정확한 closed ledger·old/new hash를 확인한 뒤 reviewed restart 수정5파일을 일반권한으로 `tools/admin_runtime/`에 통합했다. 현재 source11개의 digest는 `6baa277e306c9bf9f63e325242268a4bc2abed82841f1d052882a2b12db35d4a`다. 기존 ad0888… source9개+launcher는 새 provenance 폴더에 보존했다. [통합 결과](../work/admin-runtime-restart-applied.json), [최종 종료 증빙](../work/admin-runtime-closure-proof.json).

launcher는 고정된 최초 PREPARED receipt의 전체 SHA·producer native/source·legacy binding을 검증하면 ResumeHost를 선택한다. 새 ResumeHost는 old Prepare를 반복하지 않고 기존 LegacyExclusion·현재 consumer inventory·retired native identity를 확인한 뒤 동일 Runtime을 활성화한다. gone=87 또는 정확한 positive exit만 허용한다. 실제 exited object의 image query31은 검증된 과거 identity proof와 birth/Wait0가 함께 있을 때만 허용한다. live/reused/다른 query 오류는 거부하며 PID를 종료하지 않는다. closed ledger는 현재 audited 상태를 새 baseline으로 기록하고 unfinished ledger는 explicit Recover로 기존 기록을 복구한다.

새 session이 과거 command를 다시 처리해 완료 receipt를 REFUSED로 덮던 문제도 수정했다. 모든 기존 UUID receipt는 immutable이며 historical nonce queue는 실행·새 응답 생성·새 session command bound에서 제외한다. 기존 producer ad0888… evidence와 새6baa… session을 구분한다. 통합 후 주 세션 core23/launcher6/restart14/operator7, **50개 통과**다. 실제 관리자 재시작은 시험하지 않았고 추가 UAC를 요청하지 않았다. 다음 실제 관리자 시작이 필요할 때에는 OS 승인 한 번이 다시 필요할 수 있으며 자동 취소/실패 재시도는 하지 않는다.

원래 상태 폴더의 고정 receipt를 삭제·이동·변조하지 않는다. 다음 관리자 실행은 같은 `launch.ps1`을 쓰며 이미 완료된 인계를 Retry로 반복하지 않는다. root의 이전 live proof script/native review script는 통합 전 source와 살아 있던 retained object를 가정한 이력용이므로 현재 검사에 그대로 재사용하지 않는다.

## 실제 연속 실행 관찰 이력 — 2026-10-04 16:24 KST

사용자 정정은 **UAC 금지가 아니라 가급적 띄우지 말고 작업하라**는 뜻이다. 실제 최초 UAC 1회로 supervisor9756/native birth `134355709182042655`, Host12924/native birth `134355709186388796`를 시작했다. 이후 같은 Host에서 RetryLegacyHandoff→InspectRules→PauseRules→RestoreBaseline을 실제 완료했으며 추가 UAC·Host 재시작은 없었다. 기존 Watch32684/Monitor46308은 source/native/argv/full scope 검증과 legacy 복구 뒤 정리됐으며 retained handle exit와 최종 active CIM inventory를 확인했다.

PauseRules 후 외부 PersistentStore는 두 Enabled=2였다. RestoreBaseline 후 외부 PersistentStore·ActiveStore는 모두 Enabled=1이고 Host는 `BASELINE_RESTORED`, closed=false, error/status_error=null이다. 현재 True/True는 **legacy local gate 복구 후 새 Runtime이 기록한 baseline**이며 정상 온라인 접속 확인이 아니다. 실행 중 state는 `tools/admin_runtime/state-handoff-live`다. 도우미를 계속 유지했고 최초 시작 기준 3600초, 약 17:01:59 KST에 복구·종료 예정이므로 다음 작업은 생존·native birth·phase를 재확인한다. live pin된 core source9개와 launch.ps1은 수정하지 않는다.

첫 인계의 기존 client 35초 timeout 뒤에도 실제 준비가 완료됐고 동일 UUID receipt로 확인했다. timeout을 새 UAC나 repost 이유로 삼지 않았다. 새 operator client는 최대 120초 대기·기존 receipt 조회를 제공한다. root가 fixture launcher6개와 client7개를 독립 재실행해 통과했으며 기존 core23개 기록을 유지한다. 원문 nonce·private argv를 제외한 [실제 증빙](../work/admin-runtime-live-proof.json)을 저장했다. 이후 아래 “미실행/guardian 생존” 설명은 초기 준비 당시 이력으로 읽으며 현재 상태를 대신하지 않는다. 게임 독립 기동·온라인 정상 접속은 미검증이다.

## 제공하는 동작

`Status`, `InspectRules`, `PauseRules`, `RestoreBaseline`, `Close` 및 HandoffHost의 고정 `RetryLegacyHandoff`를 제공한다. `ExerciseFailure`는 mock backend에서만 동작한다. 임의 명령·주소·게임 PID 입력, 게임 실행/종료, RAM 읽기, 방화벽 규칙 추가/삭제는 없다.

실제 대상은 `D:\Lineage Classic\LC.exe`에 대한 아래 두 internal Name뿐이다.

- `CodexSoloLC-c7b05daa-e47b-4800-a00d-561bdc562056-12000`
- `CodexSoloLC-c7b05daa-e47b-4800-a00d-561bdc562056-14000`

PersistentStore와 ActiveStore의 원본 CIM 조건, 일곱 filter, 소유 marker를 모두 감사한다. 기존 고정 ownership SHA-256과 일치해야 하며, 각 실제 native rule object를 마지막 경계에서 다시 검사한 뒤 `Enabled`만 쓴다. 이름·Program만 맞는 외래/변경/중복 규칙은 거부한다. `Enabled=1`은 True, `2`는 False다. disabled 상태에 unconditional `PrimaryStatus==1`을 요구하지 않고, profile/enforcement hint를 실제 통신 차단 증명으로 취급하지 않는다.

`PauseRules`는 승인된 공식 분석에 필요한 두 작업 규칙의 Enabled만 False로 만든다. `RestoreBaseline`은 **Runtime 활성화 전에 기록한 각 규칙의 실제 Enabled**로 복귀한다. 직접 Host 시작 시 혼합 False/True라면 그 값으로 복귀하고, 이번 HandoffHost는 legacy prelude가 True/True를 복구한 뒤 Runtime을 활성화했으므로 True/True로 복귀한다. 이것을 온라인 정상 접속 완료로 부르지 않는다. 온라인 정상 접속과 실제 게임 진입은 별도 실증이 필요하다.

## 수명·상태·복구

- 같은 state root의 동시 Host는 OS advisory lease로 거부한다. JSON에 남은 PID만 보고 살아 있는 Host라고 판단하지 않는다.
- production Host는 기존 Gate의 원본 journal·gate-manager.lock·operation.lock existing 파일을 read-only/share-none native handle로 독점할 수 있어야 준비 상태에 들어간다. 생성/쓰기/삭제 없이 열린 handle을 종료까지 보유한다. 기존 guardian의 source pin/operation lock이 살아 있으면 거부하고 새 Gate 소유자와도 충돌을 막는다. 일시적으로 비어 있는 operation.lock만으로 기존 owner 종료를 추정하지 않는다. 이번 실제 인계에서 guardian exit 후 독점 잠금을 획득했다.
- Host가 source 파일 아홉 개와 metadata directory ancestors를 native handle로 유지하여 실행 중 source 변경과 reparse/경로 교체를 막는다. command/response는 session nonce, source digest, command UUID, Host PID와 native birth로 묶는다. state 경로는 현재 사용자 전용 신뢰 경로에서 사용해야 한다.
- JSON은 thread별 path lock과 고유 임시 이름으로 직렬화한다. Windows reader는 share-delete를 허용하고 실제 열린 handle의 reparse 속성과 파일 크기를 확인한다. 기존 파일은 ReplaceFileW로 교체한다. transient sharing/access 오류는 200ms만 재시도한다.
- baseline ledger를 첫 변경보다 먼저 영속화한다. 미완료 ledger가 있으면 새 disabled 값을 baseline으로 덮어쓰지 않고 startup을 거부한다. 명시적 `--recover`는 기존 검증된 두 baseline 값을 재사용한다.
- 부분 변경 실패는 변경 직전 상태로 역순 복귀를 시도한다. 결과가 확인되지 않으면 `RECOVERY_REQUIRED`로 같은 Host를 유지하고 후속 tick/명령에서 원래 baseline 복구를 이어간다.
- parent owner의 retained native handle, 최대 3600초 수명, Ctrl+C/예외는 복구와 종료 요청으로 처리한다. 복구·ledger close가 확인되기 전에는 source pin과 Host 권한을 놓지 않는다. permission/provider 오류를 새로운 UAC로 해결하려고 재시도하지 않는다.
- status publish 실패는 Host를 끝내지 않고 response의 `status_error`로 노출한다. transport가 명령을 받았어도 실행 오류가 있으면 `status=FAILED`, client exit 2다. source/nonce/identity mismatch나 응답 timeout도 자동 새 Host를 만들지 않는다.

## 실행 방법

기존 Python으로 비관리자 모의 Host를 실행한다. `-I -B`를 사용해도 이 프로젝트의 아홉 파일만 직접 로드한다.

```powershell
python -I -B tools/admin_runtime/entry.py Host --backend mock --state tools/admin_runtime/state-mock
```

같은 state를 사용하는 별도 일반권한 터미널에서 고정 명령을 보낸다.

```powershell
python -I -B tools/admin_runtime/entry.py Command --state tools/admin_runtime/state-mock --action PauseRules
python -I -B tools/admin_runtime/entry.py Command --state tools/admin_runtime/state-mock --action RestoreBaseline
python -I -B tools/admin_runtime/entry.py Command --state tools/admin_runtime/state-mock --action Close
```

실제 방화벽의 읽기 전용 감사:

```powershell
python -I -B tools/admin_runtime/entry.py Inspect
```

직접 `Host --backend windows --state tools/admin_runtime/state-windows`는 이미 관리자 권한인 콘솔/도우미를 요구하며 비관리자이면 UAC 없이 거부한다. 별도 고정 launcher의 HandoffHost 경로가 최초 권한 요청과 인계를 처리한다. 초기 준비 당시 두 legacy guardian이 살아 있어 readiness가 충족되지 않았으나 위 실제 인계에서 종료와 exclusion을 확인했다. preflight는 기존 파일의 exclusive read handle을 얻지 못하면 변경 전에 거부한다. state 공유 폴더나 다른 사용자가 쓸 수 있는 경로를 사용하지 않는다.

## 초기 모의 검증 이력

`python -I -B tools/admin_runtime/tests.py`의 18개 검증이 통과했다. 모의 live Host의 PID/native birth가 Status→Pause→복구→고정 오류→복구→Close 동안 같았고, actual firewall writes/UAC는 없었다. 두 reader와 네 writer의 실제 Windows 300회 JSON 교체, enum 2, foreign scope 거부, nonadmin write 거부, partial rollback, status publish 실패, owner loss/TTL recovery, unfinished-ledger restart 거부와 recorded-baseline recovery를 확인했다. legacy exclusion은 테스트 전용 임시 파일의 live read pin 거부와 원문 보존으로 검증했으며 실제 원본 lock에는 접근하지 않았다.

실제 nonadmin `Inspect`는 첫 시도에서 provider의 `CimException`/`MI RESULT 1`을 반환했다. 다음 read-only 조사에서는 native Windows PowerShell과 새 CLI 모두 성공했고, full fingerprints 및 양쪽 store가 12000=2, 14000=1임을 확인했다. 첫 실패를 지속 권한 문제로 결론 내리지 않았다. runtime은 이런 오류의 stage와 bounded ErrorRecord ID만 기록하고 provider 전체 메시지/명령 문자열을 출력하지 않는다.

초기 모의 검증 당시 실제 관리자 mutation·인계·UAC 연속 실행은 미검증이었다. 이후 실제 결과는 최상단 기록을 따른다. mock pass나 실제 방화벽 동작을 단독 게임 실행·온라인 정상 접속 성공으로 취급하지 않는다.

## 기존 guardian 정리부터 같은 Host에서 잇는 준비 경로

추가 구현은 `legacy_handoff.py`, `legacy_handoff.ps1`, `legacy_binding.json`이다. 원본 코드 실행·변경 없이 이미 관리자 권한인 **동일 Python Host** 안에서 legacy 복구와 소유자 정리를 처리한 다음 Runtime으로 전환한다. `HandoffPlan`은 기본 읽기 전용이고 `HandoffHost`는 준비 중인 Host를 유지한다. 초기 구현 시에는 모의 검증만 했고 이후 위 최신 시험에서 실제 Prepare·방화벽 변경·guardian 종료를 수행했다. 기존 IPC는 사용하지 않았다.

기존 controller의 Watch/Monitor는 operation.lock을 lifetime 동안 소유하지 않는다. 정상 tick은 controller.ps1의 finally Dispose로, recovery tick은 engine.ps1의 Recover-SGECycle finally ReleaseLock으로 매 cycle 놓는다. 새 prelude는 **기존 파일을 read/share-none으로 열어 최대 10초 내 lock을 실제로 독점하는 경우에만** 작업한다. 실패하면 `LEGACY_HANDOFF_PENDING`을 유지하며 lock 경쟁을 우회해 쓰지 않는다.

binding에는 현재 두 ready 파일의 SHA, 정확한 guardian PID/native birth/image/session, request의 원래 owner 및 memory session identity, 원본 bundle·여섯 component·plan/journal SHA를 고정했다. nonce는 원문 대신 SHA로 비교하며 출력하지 않는다. arbitrary PID·스크립트·명령 인수를 받지 않는다.

실제 Prepare의 순서는 다음과 같다.

1. 원본 소스와 ready/request/ledger binding, native guardian identity 및 Windows parser로 분해한 정확한 source/role/nonce argv를 검사한다. LC가 없고 원래 owner PID가 없으며 옛 RAM Host가 없는 완전한 inventory를 요구한다. ledger는 official=null이고 recovery/restoring/restored 상태여야 한다. 조회 오류·누락은 부재로 처리하지 않는다.
2. 원본 소스·ready/request는 read pin만 잡고 기존 operation.lock을 독점한다. 원본 파일 내용을 쓰거나 새 lock을 만들지 않는다.
3. 고정 두 rule의 전체 scope를 다시 확인하면서 legacy gate baseline인 Enabled=True로만 복구한다. 이것은 온라인 정상 접속 성공을 뜻하지 않는다.
4. 두 store의 전체 복구를 확인한 뒤 자연 종료를 2초 관찰한다. 여전히 살아 있으면 no-LC/no-old-owner/no-RAM·소스·정확한 native handle·full restore를 매 경계에서 다시 확인한 **두 작업 소유 guardian만** 고정 cleanup한다. 다른 PID·게임 프로세스에는 종료 API를 적용할 수 없다.
5. 두 retained handle의 실제 signaled exit와 final full audit 후 기존 LegacyExclusion을 획득한다. 이 시점까지 새 `PauseRules`는 거부한다. 그 후 같은 Python PID/native birth에서 기존 Runtime으로 전환한다.

prelude 실패나 결과 timeout은 같은 관리자 Host를 `LEGACY_HANDOFF_PENDING`으로 남긴다. `Status`, `RetryLegacyHandoff`, `Close`만 허용하고, 이미 변경됐을 가능성이 있으면 Close/owner loss/TTL도 준비·복구 확인 전에는 token을 놓지 않는다. query-only retained guardian handle은 retry 동안 유지하여 첫 cleanup 후 부분 실패가 생겨도 정확한 exit를 다시 확인할 수 있다. 재시작이나 새로운 UAC를 자동으로 요청하지 않는다.

읽기 전용 준비 확인:

```powershell
python -I -B tools/admin_runtime/entry.py HandoffPlan
```

이미 승인된 관리자 콘솔에서는 `HandoffHost --backend windows --state tools/admin_runtime/state-handoff`로 같은 준비 경로를 사용할 수 있다. 일반권한 모의 확인은 backend mock이다. 이번 실제 실행은 아래 고정 launcher/state-handoff-live에서 수행했다. 완료된 legacy 인계를 오래된 고정 guardian binding으로 새로 반복하지 않는다.

추가 후 **23개 검증이 통과**했다. live mock HandoffHost가 pending→고정 준비→Pause→Restore→Close 동안 동일 PID/native birth임을 확인했고 실패 후 token 유지·retry·proof/exclusion 실패 시 rule action 거부도 검증했다. 초기 일반권한 HandoffPlan은 `guardian_argv_unreadable`로 BLOCKED였다. 이후 위 관리자 실행에서 정확한 argv/source/native 검증과 실제 Prepare·cleanup·단일 UAC 연속 실행을 완료했다.

## 1회 요청 뒤 같은 Host를 유지하는 launcher

사용자의 최신 정정은 **UAC 금지가 아니라 가급적 띄우지 말고 작업하라**는 뜻이다. `launch.ps1`은 필요한 최초 관리자 실행만 명시적 `RunAs` 한 번으로 요청한다. 취소·권한·시작 오류를 자동 재시도하지 않으며 취소의 native error 1223을 `UAC_CANCELLED`로 구분한다. 기존 Host나 동시 launcher가 있으면 요청 전에 거부한다.

일반권한 launcher가 source 아홉 개와 자신의 script를 읽기 pin하고 독점 `launcher.lock`을 보유한다. 최초 UAC로 시작된 고정 PowerShell supervisor는 동일한 bundled Python으로 `entry.py HandoffHost --backend windows`만 시작하며 Python이 종료될 때까지 살아 있다. Python의 `Owner` retained handle은 이 supervisor를 가리킨다. 일반권한 launcher도 supervisor 종료까지 유지하여 tool exec가 yield하더라도 owner 수명이 끊어지지 않는다. source 파일이나 launcher는 실제 Host가 살아 있는 동안 수정하지 않는다.

고정 경로만 사용하며 backend·PID·임의 명령·외부 script 인수를 받지 않는다. 상태 폴더는 `tools/admin_runtime/state-handoff-live`다. `launcher-status.json`의 `BOUND_HOST_READY`는 session/status의 source digest, nonce hash, retained child PID/native birth와 실제 supervisor parent를 확인했다는 뜻이다. `host_phase=LEGACY_HANDOFF_PENDING`은 아직 guardian 정리를 수행하지 않은 준비 상태다. 변경은 이후 고정 `RetryLegacyHandoff` 명령에서 시작한다. 실패해도 같은 Host의 권한과 source pin을 유지하며 다른 UAC·Host를 만들지 않는다. 메타데이터 실패도 owner를 종료하거나 자식 프로세스를 강제 종료하지 않는다.

필요한 최초 실행은 일반권한에서 다음 고정 script로 시작한다. 최초 UAC는 사용자가 Windows에서 승인해야 한다.

```powershell
& 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe' -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File 'C:\Users\Chansol\Documents\ChatGPT\싱글리니지\tools\admin_runtime\launch.ps1'
```

launcher가 유지된 상태에서 아래 `operator_client.py`로 승인 범위의 고정 action을 보낸다. `Close`는 기존 Host의 복구 확인 후 종료를 요청한다. 미완료 baseline ledger가 남은 경우 일반 실행은 UAC 전에 거부하며, 이전 baseline을 다시 사용하는 명시적 `-Recover`만 별도 지원한다. 이미 인계된 이번 실행 이후의 재기동은 과거 guardian binding 재사용 문제가 있으므로 자동 성공을 가정하지 않는다.

`launcher_tests.py`의 **6개 Windows fixture 검증이 통과**했다. 일반권한 PowerShell supervisor와 mock HandoffHost로 parent/native identity 유지, 초기 metadata publish 세 번 실패 후 같은 Host 회복, 준비→Pause→오류→Restore→Close의 동일 PID/birth, 정확한 source digest, stale PID/birth/source/nonce 거부, 한글·공백·따옴표·끝 backslash 인수, 동시 lease의 UAC 이전 거부 및 모의 취소 1223의 1회 시도를 확인했다. fixture 자체는 UAC·실제 legacy Prepare·방화벽 쓰기·게임 실행을 하지 않았고, 실제 관리자 launcher 연속 동작은 위 별도 증빙을 따른다.

### 긴 작업의 1회 요청과 기존 receipt 조회

`operator_client.py`는 일반권한에서 살아 있는 동일 Host에 고정 action을 한 번만 보낸다. 기본 상태 폴더는 고정 `state-handoff-live`이며 CLI에서 임의 경로·PID·명령을 받지 않는다. `Request --action Status --wait 120`은 요청 UUID를 먼저 출력하고 최대 120초 기다린다. 실제 인계는 기존 `entry.Command`의 35초보다 길 수 있으므로 timeout을 작업 실패나 새 UAC 필요로 판단하지 않는다.

응답이 늦으면 출력한 UUID로 `Receipt --id <UUID> --wait 120`을 실행한다. 이 조회는 기존 요청 파일과 응답만 읽으며 요청을 다시 보내지 않는다. 원문 nonce는 출력하지 않는다. 현재 source/session과 기존 요청의 nonce·UUID·action binding 및 응답의 source digest·nonce hash·Host PID/native birth를 모두 확인한다. transport의 ACCEPTED만으로 완료를 표시하지 않고, 해당 action의 runtime phase와 오류·closed 값을 함께 확인해 `COMPLETE`를 반환한다. `FAILED`, `REFUSED`, `INCOMPLETE`, receipt timeout은 exit 2다. 자동 repost·Host 재시작·UAC는 없다.

`operator_client_tests.py`의 **7개 임시 파일 검증이 통과**했다. 120초 모의 timeout 후 동일 UUID receipt를 가져와도 명령 파일은 하나였고, 잘못된 source/native/nonce/request binding·잘못된 완료 phase·runtime 오류를 거부했다. UUID의 대기 전 flush, 실패 exit 2, 원문 nonce·private 필드의 출력 제외도 확인했다. 이 테스트는 실제 Host 명령·권한 변경·방화벽 작업을 수행하지 않는다.
