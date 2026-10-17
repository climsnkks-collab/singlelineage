# 변경하지 않은 clone의 첫 안내 관찰

고정 대상은 `work/standalone_boot/current-unmodified-clone/LC.exe`다. SHA-256 `9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`, build 26.09.29.2001, clone working directory, 인수 없음이다. 원본·보관·clone 내용을 바꾸지 않는다. 기본 `observer.py`는 파일 경로와 계획만 출력한다. 실제 `--run`은 root가 소스와 설치 영수증을 검토한 뒤 호출한다. 새 사용자 승인 질문을 생성하는 도구가 아니다.

같은 한 EXE 슬롯의 비교는 `--variant control`(기본) 또는 `--variant candidate`만 허용한다. CONTROL의 hash는 위 `9ffc...`, CANDIDATE의 hash는 `7e66b52b18caf852c741d43abdef0398faf2894c9b989172a8123b16141f1d33`로 소스에 고정했다. path·workingdir·인수·Job 조건은 같다. root review/실제 설치 영수증/current admin status/fresh native audit의 program_variant와 실제 hash가 모두 선택된 role과 일치해야 한다. 임의 hash/path/PID 입력은 없다. candidate 보고서에는 publisher_signature_content_mismatch=true와 operational_adoption=false를 반드시 남긴다. observer는 EXE·자원을 교체하지 않는다. root만 no-LC·관리자 Cleanup 완료·gate source pin 해제 후 단일 슬롯을 교체하고 CONTROL을 복구한다.

실행 전에는 LC가 전혀 없는 snapshot, ordinary controller token/integrity, root의 plan/installed receipt SHA 기록, 실제 관리자 producer의 native PID/birth/image/생존 및 bound 실제 Arm 영수증, 현재 admin14 source digest 및 `CloneInspect`의 양Store full audit가 모두 일치해야 한다. current status의 clone_isolation phase는 ARMED여야 한다. 현재 이 파일들은 실제 기동을 위해 생성·검증하지 않았다.

CreateProcessW는 고정 EXE를 **suspended**로 만들고 creation process/thread handle을 즉시 보유한다. thread를 실행하기 전에 active process limit 1, KILL_ON_JOB_CLOSE, breakaway 없음인 자기 Job을 연결하고 limit·membership을 읽어 확인한다. clone이 존재하는 suspended 상태에서 full firewall audit와 producer를 한 번 더 검사한 뒤 primary thread를 Resume한다. Job 연결·token·scope 확인 실패는 thread 실행 전에 자기 creation handle로 종료한다. protected debugger, auth/parent spoof, injection, memory 읽기, RunAs는 없다.

25초 동안 자기 process의 실제 exit code와 자기 HWND의 public caption/launcher notice만 관찰한다. Edit/ComboBox는 읽지 않는다. unknown caption/static text는 hash·길이만 저장한다. SDK child 생성 제한 이벤트가 오면 중단한다. 25초 안에 자연 종료하지 않으면 마지막 native exit 검사 뒤 exact retained creation handle로만 강제 cleanup한다. UI 메시지·닫기 입력은 보내지 않는다. 자연 exit와 forced cleanup을 구분한다. PID 숫자를 다시 열어 다른 프로세스를 종료하지 않는다.

root controller console은 `launch.ps1`의 일반권한 Start-Process/WindowStyle Hidden으로 시작할 수 있다. 첫 launcher 안내를 관찰할 때 자기 game window는 보일 수 있다. 창 클릭·키 입력·UAC 승인·스크린샷은 제공하지 않는다. root의 UI 도구 초기화가 os3으로 실패한 환경에서 전역 screen API를 우회하지 않고 자기 창의 bounded public text만 사용한다.

**실험 범위:** active-process-limit 1은 SDK child를 실행 전 거부하므로 정상 온라인 초기화와 다른 제한이다. 고정 clone 프로그램의 직접 통신 규칙이 확인돼도 이미 실행 중인 PURPLE·broker의 간접 영향과 앱 전체 네트워크 격리를 증명하지 않는다. standalone play나 공식 로그인 성공으로 표시하지 않는다. PURPLE은 실행하지 않으며 pre-snapshot에서 확인된 현재 native identity만 기록한다.

root 검토 기록 예시의 키:

```json
{
  "schema": "lc-clone-observer-root-review-v1",
  "reviewed": true,
  "program": "고정 clone LC.exe 절대 경로",
  "program_sha256": "9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af",
  "program_variant": "CONTROL",
  "plan_sha256": "실제 plan의 SHA",
  "installed_sha256": "실제 설치 영수증의 SHA",
  "admin_source_sha256": "실행 중인 admin14의 SHA",
  "producer": {"pid": "현재 native admin PID", "birth": "현재 native FILETIME"}
}
```

검토 기록은 `tools/clone_observer/root-review.json`, plan/설치 영수증은 `work/clone-isolation-plan.json`과 `work/clone-isolation-installed.json`이다. 설치 영수증은 actual_admin_operation=true, verified=true, producer/program/program_sha256/source_sha256을 현재 host와 일치시켜야 한다. 파일이 없거나 native audit 계약이 불일치하면 시작하지 않는다.

검증 명령: `python -I -B tools/clone_observer/tests.py`. 16개 검증이 통과했다. 모의 자연 종료/안내, timeout/forced cleanup, job 연결 실패, suspended 후 gate 변경, foreign LC 존재, elevated controller, SDK child 제한, unknown/credential text 제외, cleanup 실패를 검증했다. control/candidate의 동일 path와 고정 hash, 잘못된 receipt role/current hash 거부도 확인했다. 실제 Windows 64bit ABI와 자기 controller native identity/token query만 수행했으며 LC·PURPLE·실제 UI·UAC를 시작하지 않았다.

근거: [Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects), [AssignProcessToJobObject](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-assignprocesstojobobject), [Process creation flags](https://learn.microsoft.com/en-us/windows/win32/procthread/process-creation-flags).

실제 CloneInspect wrapper는 lc-fixed-clone-native-inspect-v1/source_sha256/program_variant/actualprogram_sha256/audit이다. observer는 audit의 lc-fixed-clone-audit-v1을 reviewed clone_isolation.validate_audit 순수 함수로 검사하고, 현재 live ARMED의 모든 NAMES와 두 store Enabled=True·profiles_enabled=True를 요구한다. read-only audit에 ARMED 상태를 만들어 넣지 않는다. native subprocess timeout은 60초다. 실제 read-only 출력 fixture를 저장했고 absent/foreign/profile-false 거부와 expected fullscope present 통과를 검증했다.

ordinary observer에서 foreign elevated Host의 token DACL이 읽기를 거부할 수 있다. mandatory native birth/image/생존은 유지하며 privilege는 bound 실제 Arm mutation 영수증과 fresh full policy로 증명한다. token은 실제 읽은 경우에만 elevation_token_verified=true로 보고하고, 실패하면 값을 지어내거나 추가 관리자 권한을 요청하지 않는다.

## 동결된 codec 오류의 CONTROL 진단

`--mode codec-diagnostic --variant control`은 기존 normal gate를 바꾸지 않는 별도 제한 경로다. frozen f06 source, Host 38688/native birth 134355790844375964, failed Arm UUID 6982de69aa544cefacb01ebff03e2fc3의 원본 FAILED/UnicodeDecodeError 응답과 현재 epoch를 요구한다. physical cached audit SHA와 새 fixed read-only Inspect의 양Store/profile/fullscope가 모두 True여야 한다. ordinary 검사 프로세스의 Console.OutputEncoding만 UTF8로 정하며 live 관리자 source·상태·규칙은 쓰지 않는다.

root는 `tools/clone_observer/root-codec-diagnostic-review.json`에 schema=`lc-clone-codec-diagnostic-review-v1`, reviewed=true, no_admin_repair_during_observation=true, program(고정 path), program_sha256(9ffc...), program_variant=CONTROL, admin_source_sha256(f06...), producer={pid:38688,birth:"134355790844375964"}, failed_arm_request_id(위 UUID), failed_arm_result_sha256, physical_audit_sha256를 남긴다. 이는 현재 승인 범위에서 source/실물 gate의 root 검토 기록이다.

관찰 중 encoding repair/upgrade/별도 cleanup을 동시에 수행하지 않는다. normal manager의 ARMED/성공을 만들지 않고 `RULE_VERIFIED_HOST_CODEC_FAULT`, manager_operation_succeeded=false, manager_ARMED=false로 보고한다. source의 noClone guard와 native Assert-CloneAbsent가 suspended/실행 중인 자기 clone의 rule 제거를 막는다. known UnicodeDecodeError/ArmFailed 외에는 거부하며, 자기 child 생성 이후에만 ValueError/CloneStillLive 전환을 허용한다. candidate는 이 모드에서 거부한다. 진단 종료 후 codec repair와 gate cleanup은 여전히 별도 작업이다.

추가한 known-fault/CloneStillLive/fullscope-false/profile-false/unknown-fault/candidate 거부 fixture를 포함해 **18개 검증이 통과**했다. 이 구현 작업에서 실제 game/UAC/repair/cleanup은 수행하지 않았다.

## 자기 창 stage와 CPU/module 진단 확장

`observer.py --seconds 20..120`을 허용하며 default25는 유지한다. 이 시간은 관측 상한일 뿐 실제 게임 진입 기준이 아니다. Root가 검토한 정상 CONTROL 한 번에 `--seconds 120`을 사용하면 같은 blind caption 반복 대신 아래 새 값을 얻는다. 이 확장 작업에서 실제 game/Arm/admin/slot은 실행하지 않았다.

- 매 public property 조회 경계에서 retained native creation handle의 birth/image/생존 및 HWND의 현재 PID를 다시 확인한다. 창이 사라지거나 foreign PID면 caption/class/geometry/text를 읽지 않는다. raw HWND/other PID는 결과에 내보내지 않는다.
- 자기 top window의 known public class/visibility/geometry와 owner/GA_PARENT의 same-owned-process/외부/없음 관계, 최대64개 자기 child의 class count를 기록한다. public Windows/common-control/공개 browser class만 plaintext, unknown class는 hash·길이로 남긴다. Edit/ComboBox와 foreign HWND의 text는 읽지 않는다.
- Launcher notice는 source에서 확인된 exact ko-KR 문장만 plaintext로 허용한다. 그 밖의 static text와 unknown caption은 hash·길이뿐이다.
- 공개 Windows caption `Default IME`의 digest는 기존 c104...와 맞지만, **실제 조회한 class=IME와 visibility가 함께 있어야** Windows default-IME infrastructure로 분류한다. 이전 caption hash만으로 과거 창을 확정하거나 game UI 증거로 삼지 않는다. [Windows는 thread마다 default IME window를 만든다](https://learn.microsoft.com/en-us/windows/win32/api/imm/nf-imm-immgetdefaultimewnd).
- 5초마다 최대25회 자기 GetProcessTimes kernel/user CPU 시간, ownPID thread count, [Toolhelp module](https://learn.microsoft.com/en-us/windows/win32/api/_toolhelp/) basename/size/고정 file version만 수집한다. module base/address/bytes/full path/argv는 출력하지 않는다. CPU 상승·SDK image 존재는 실제 측정값이고 SDK initialization/game entry 증명이 아니다. 모듈 조회 오류는 숫자만 기록하며 승격·VM read를 재시도하지 않는다.

Win32 RECT/MODULE64 ABI와 actual 자기 Python process의 CPU/thread/module metadata query가 통과했고, foreign HWND·native birth mismatch 거부, IME 조건, unknown class/privacy, 120초 상한 fixture를 포함해 **23개 검증 통과**다. `owned-window-stage-plan.md`에 Root의 실제 실행 command와 소스 hashes를 남긴다.

## startup-analysis의 SDK descendants

실제 Job1 관찰에서 약70초에 ACTIVE_PROCESS_LIMIT가 발생한 뒤의 정상 bootstrap을 관찰하려면 Root가 `--profile startup-analysis --mode normal --variant control --seconds 120 --run`을 검토한다. default `single`은 기존 Job1과 같다. 새 profile은 CONTROL만 허용하고 anonymous owned Job의 KILL_ON_JOB_CLOSE/noBreakaway/activeLimit16을 설정·readback한다. main LC의 fresh ANY/nonloopback rule은 계속 요구한다. SDK descendants의 통신은 이미 승인된 정상 공식 분석 범위이며 이 profile의 앱 전체 격리·offline play 증거는 false다.

root-review.json에는 기존 record 외에 profile=startup-analysis, analysis_only=true, SDK_descendant_online_analysis_allowed=true, job_active_process_limit=16, cleanup_scope=owned_job_members가 필요하다. 이는 실제 분석 scope에 관한 Root의 코드 검토 기록이다. candidate/codec-diagnostic는 이 profile에서 거부한다.

owned Job NEW_PROCESS6 알림에서 query/sync handle을 retain하고 birth/image/token/job membership을 검증한다. basename·file version·birth만 공개하고 argv/env/token/private UI·image full path는 수집하지 않는다. foreign/reused/unknown membership·unexpected elevation·16-tree bound 초과는 중단한다. 빠르게 끝나 identity를 잡지 못한 child는 명확히 미확인으로 기록하며 성공한 capture로 만들지 않는다. kernel active limit은 동시16개, retained tree/event census도16개 이내다.

main이 먼저 자연 종료했는데 owned descendants가 살아 있으면 같은 120초 상한 안에서 소유 Job을 관찰한다. 이미 검증한 각 member의 자기 window metadata만 읽는다. 종료 때 PID를 재오픈해 kill하지 않고 **retained exact owned Job handle**의 TerminateJobObject/positive empty를 사용한다. main natural exit와 descendants forced cleanup을 구분한다. Job 연결 전 실패는 suspended 자기 creation handle만 cleanup한다. input/screenshot·overlay hook 변경은 없다.

RTSSHooks64.dll이 관찰됐다는 사실은 overlay 이름의 image 존재뿐이다. reported image size와 version=null을 원인이나 초기화 완료로 판정하지 않으며 RTSS hook을 제거·변경하지 않는다. SDK image 존재도 initialization proof로 표시하지 않는다.

native ACCOUNTING48 ABI, Job16/noBreakaway readback, foreign member 거부/tree cap, retained Job-only cleanup, main natural exit 보존 및 explicit scope review fixture를 포함해 **27개 검증 통과**다. 실제 SDK/game child는 이 구현 검증에서 시작하지 않았다.

## 승인된 정상 CONTROL 온라인 분석

`--profile online-startup-analysis --mode normal --variant control --seconds 120 --run`은 기존 격리 profile과 별개다. 정상 공식 온라인 분석에 관한 기존 사용자 승인 범위에서 Root가 현재 코드·실물 상태를 검토해 실행한다. 추가 사용자 승인 질문이나 UAC를 만들지 않는다. default `single`, 기존 gated `startup-analysis`, codec diagnostic은 유지한다. candidate와 codec mode는 이 새 profile에서 거부한다.

Root는 `tools/clone_observer/root-online-analysis-review.json`에 다음 필드를 남긴다. 이는 승인된 분석의 코드와 현재 상태 검토 기록이며, 관리자 ARMED나 성공 receipt를 대신 만들지 않는다.

- schema=`lc-clone-online-analysis-review-v1`, reviewed=true, profile=`online-startup-analysis`
- normal_online_analysis_authorized=true, network_isolation_required=false, analysis_only=true, SDK_descendant_online_analysis_allowed=true, no_concurrent_manager_launch=true
- allow_verified_stock_high_relaunch=true: 아래 고정 CONTROL의 정상 High 재실행에 대한 코드 검토 scope다. 기존 사용자 승인 안의 정상 앱 동작 관찰이며 observer 자체 RunAs/token 재사용은 없다.
- program=고정 clone LC.exe, program_sha256=`9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`, program_variant=`CONTROL`, build=`[26,9,29,2001]`, stock_signature_verified=true. 이 digest는 서명 검증한 stock bytes에 고정되고, 서명 불일치 candidate를 허용하지 않는다.
- admin_source_sha256=`3cebc7134275c20142da90482cbd9bad118599949835c42fe9c3d1f5444e32d8`, observer_source_sha256={core.py,windows.py,observer.py,tests.py의 현재 SHA256}
- job_active_process_limit=16, cleanup_scope=`owned_job_members`
- former_host={pid:12460,birth:`134355830290220367`}, former_owner={pid:40940,birth:`134355829987543068`}
- closed_state_sha256={status.json,baseline.json,clone-baseline.json,clone-status.json,launcher-status.json의 현재 raw-byte SHA256}. 모두 고정 state-handoff-live 경로다.

코드는 이전 host/owner의 native birth/image/종료를 일반권한 query/synchronize handle로 검사한다. PID가 재사용됐으면 birth 차이로 이전 객체 부재만 확인하며 새 프로세스를 조작하지 않는다. 접근 실패는 부재로 간주하지 않는다. CLOSED runtime와 RESTORED clone/종료 launcher, 정확한 legacy baseline·clone baseline·scope digest를 검증하고, 현재 source14의 새 read-only CloneInspect에서 CONTROL bytes와 clone 규칙의 Persistent/Active 양Store **부재**를 요구한다. disabled 규칙도 부재와 같다고 처리하지 않는다. audit 전후 코드·검토·상태 bytes와 이전 owner 종료를 재확인한다. 관측 시작 전 complete no-LC snapshot은 공통 controller에서 요구한다.

보고는 `AUTHORIZED_CONTROL_ONLINE_ANALYSIS`, manager_present=false, manager_ARMED=false, analysis_only=true, network_isolation_required=false, network_isolation_verified=false, standalone_play_verified=false다. 관리자 token query나 새 관리자 process는 요구하지 않는다. 기존 PURPLE/broker 변수가 남으며 앱 전체 격리·로그인 독립·local gameplay를 완료로 표시하지 않는다. CONTROL의 정상 SDK/인터넷 초기화만 기존 승인 범위에서 관찰하며, auth flags·parent spoof·로그인 입력은 없다.

동일 Job16/noBreakaway/KILL_ON_JOB_CLOSE와 retained exact Job cleanup을 사용한다. 자기 creation/소유 child handles 밖의 종료, 방화벽 쓰기, 관리자 source 변경, UI 입력, memory read, 전체 argv나 credential 수집은 없다. **30개 검증 통과**: 온라인 profile CONTROL 제한, 잘못된 승인·hash·현재 코드·closed ledger·live owner·rule enabled/disabled/present·native audit variant/source 거부, native absence 오류 거부를 포함한다. 검증 과정에서 실제 game/network/UAC/rule 작업은 수행하지 않았다.

실제 첫 온라인 관찰의 child identity 거부를 구분하기 위해 `owned_member_refusal`에 job membership·native birth·image basename(최대128자)·실제 조회한 elevated/integrity RID·token_verified 및 실패 조건을 기록한다. 조건은 birth_before_owned_main/elevated_token/integrity_above_medium으로 나눴으며 기존 거부 기준을 완화하지 않았다. membership 미확인 foreign process의 image/token을 추가 수집하지 않는다. token 조회 실패는 unknown으로 남긴다. 거부된 실제 Job member의 query/synchronize handle은 관측용 member로 채택하지 않고 종료 검증만 위해 보관한다.

Job accounting 0이 native process 종료 신호보다 먼저 관측되는 race를 처리한다. retained exact Job을 종료한 뒤 main과 모든 보관된 member handle의 WaitForSingleObject를 **합산 최대5초** deadline에서 기다리고, main의 새 exit code를 조회해야 positive_exit=true다. PID 재오픈/종료는 없다. native signal mock race와 public refusal metadata/기존 조건 유지 검증을 포함해 **32개 검증 통과**다. 실제 game·SDK·관리자 작업은 이 수정 검증에서 실행하지 않았다.

실제 후속 관찰에서 high Job member의 basename LC.exe/elevated=true/RID12288이 확인됐다. basename만으로 채택하지 않는다. online-startup-analysis에서만 native full image가 정확한 고정 clone path인지 확인하고, main 이후 birth·동일 Job·실제 High token(RID12288)·이미 보유한 source SHARE_READ pin의 CONTROL SHA/build와 Root의 stock 서명 검토/allow_verified_stock_high_relaunch를 모두 요구한다. 같은 CONTROL의 정상 앱 자체 재실행에만 `high_as_actual_normal_app_relaunch=true`를 보고하며 권한을 medium으로 바꾸어 보고하지 않는다. single·기존 gated startup-analysis는 계속 high를 거부한다. SYSTEM/unknown token, 다른 path/app, original-path LC, candidate, 서명 검토 누락은 거부한다.

거부 정보에는 exact_fixed_path와 known_original_program bool만 추가해 경로를 공개하지 않는다. accepted member summary에는 actual elevated/RID/path match/version/relaunch flag를 남긴다. observer의 controller와 최초 main은 여전히 medium 이하이고 observer는 RunAs·privileged generic command·token 재사용·auth/parent spoof를 구현하지 않는다. class/geometry/caption API 접근 거부는 bounded public_metadata_errors의 operation/WinError로 남기며 더 높은 권한을 요청하지 않는다. native identity나 Job membership 증명이 없으면 중단한다. profile별 high path/token/hash/서명 guard와 public metadata access-denial mock을 포함해 **34개 검증 통과**다. 실제 게임·UAC·관리자 source14 변경은 이 구현 작업에서 수행하지 않았다.

## 각 소유 LC의 종료와 초기화 측정

Job16에서는 main이 먼저 종료해도 살아 있는 exact-fixed LC들의 metadata를 계속 수집한다. 각 LC를 처음 capture한 직후 즉시 측정하고, 이후 5초 간격으로 member당 최대25회, 전체16 members/400 samples를 파일에만 보관한다. source SHA·Job·native birth/image binding과 기존 privacy 경계를 유지하며 CPU/thread/module basename·size/version만 남긴다. CPU의 optional access error는 WinError metadata이고 unknown을 성공값으로 만들지 않는다. mandatory identity/membership 오류는 중단한다. main만 측정하던 기존 제약은 해소했지만 module 존재가 SDK initialization을 증명하지는 않는다.

cleanup의 `final_owned_members`에는 모든 retained member의 실제 GetExitCodeProcess code, native creation/exit FILETIME·실제 lifetime seconds, first-capture monotonic clock과 capture 후 elapsed를 기록한다. `natural_exit_no_force_requested`와 `forced_cleanup_requested`를 나누며, 이미 종료된 main과 아직 살아 있어 Job termination을 요청한 descendant를 구분한다. force를 요청한 사실만으로 종료 원인을 단정하지 않는다. query 실패는 metadata error/unknown으로 남긴다. 종료 신호와 code를 확인한 뒤에만 retained handles를 닫는다. raw argv/private path/메모리/토큰 bytes는 수집하지 않는다.

자기 native process ABI/query, 모든 member exit code·native lifetime 구분, 처음 capture 즉시/5초/25회 cap, optional CPU access denial, main exit 뒤 high-member samples 지속을 포함해 **37개 검증 통과**다. 이 source 작업에서는 실제 SDK/game/UAC/관리자/rule action을 실행하지 않았다. 원문 last-run과 preserved high-relaunch의 finished_utc는 `2026-10-04T12:15:39.636929+00:00`으로 이미 UTC이며, PowerShell 파싱 표시의 +09 변환과 구분한다. 수명 판정에는 native FILETIME와 monotonic 측정값을 사용한다.

## 고정 A/B 설정 후보의 온라인 분석

새 `--profile online-config-analysis --variant admin-off|admin-launcher-off --mode normal --seconds 120 --run`은 별도 실험이다. 기존 CONTROL 온라인/High 예외와 다른 profile의 조건은 유지한다. A=`ADMIN_OFF`는 SystemManager.run-as-admin만 false, B=`ADMIN_LAUNCHER_OFF`는 여기에 LauncherChecker.switch도 false다. path는 같은 고정 clone LC.exe이며 Root의 fixed slot 도구가 준비한다. 이 observer는 slot을 쓰지 않는다.

- A candidate path: `work/standalone_boot/current-systemmanager-admin-false.candidate.bin`, SHA256=`f13cb8967ff800268af5b9190c75789cc0991ccb3a42fdf085e314d92e04e4f1`
- B candidate path: `work/standalone_boot/current-systemmanager-admin-and-launcher-false.candidate.bin`, SHA256=`94fa03e91eac3798c7f940cd9b30e6fe9862f577f226eb3a2fdf81314064e35c`
- 양쪽 size=39144728, build=26.9.29.2001. 서명 content digest가 변했으므로 stock_signature_verified=false, publisher_signature_content_mismatch=true, operational_adoption=false로 보고한다. 정상 서명 stock으로 표시하지 않는다.

Root record는 `tools/clone_observer/root-online-config-analysis-review.json`, schema=`lc-clone-online-config-analysis-review-v1`이다. 기존 온라인 Root record의 reviewed/authorized-online/analysis-only/SDK-descendants/no-concurrent-manager/job16/cleanup-scope/former-host-owner/current-admin3ce/current-observer4SHA/CLOSED5SHA/build/path 필드에 아래를 설정한다.

- profile=`online-config-analysis`, program_variant=`ADMIN_OFF` 또는 `ADMIN_LAUNCHER_OFF`, program_sha256=해당 literal digest, candidate_path=해당 고정 candidate의 absolute path
- candidate_code_reviewed=true, roundtrip_preflight_verified=true, stock_signature_verified=false, publisher_signature_content_mismatch=true, operational_adoption=false, allow_verified_stock_high_relaunch=false
- candidate_preflight_sha256=`work/standalone_boot/startup-policy-trials-preflight.json`의 Root가 검토한 현재 raw SHA256. compact schema=`lc-startup-policy-trials-preflight-v1`의 stock source9ffc/anchor0ba7/original policy/A-B semantic1·2 fields/10개 exact checks/서명 불일치·미실행을 검증한다. full report는 실행하거나 dump하지 않는다.

Gate는 candidate input과 현재 고정 slot의 실제 bytes를 해당 literal SHA와 비교하며, 공통 controller가 source pin·build·ordinary token·complete no-LC를 검증한다. CLOSED ledger와 이전 관리자 native 부재 및 실제 clone 규칙의 양Store 부재를 재확인한다. Admin14 ImagePin은 원래 CONTROL/CANDIDATE family만 받으므로 A/B CloneInspect 성공을 만들지 않는다. 현재 source3ce에 묶인 fixed clone_firewall.ps1의 literal read-only Inspect를 일반권한 UTF8 child에서 사용하고 pure fullscope validator로 검사한다. 관리자 code/규칙/nonce는 쓰지 않는다.

모든 main/controller/child는 medium 이하이며 후보 High 재실행은 경로가 같아도 거부한다. noargs/Job16/noBreakaway/retained exact owned cleanup/privacy 규칙을 유지한다. 서명 변형 실행은 기존 승인된 정상 분석의 source-reviewed config 비교에 한정되며 실제 JSON 소비·SDK 초기화·게임 진입·단독 local 완료를 증명하지 않는다. unknown privilege/identity/membership 분기는 중단한다.

모듈 snapshot이 error5 등으로 실패하거나 truncation/중간 종료가 있으면 module_observation_complete=false다. `SDK_images_present=[]`와 SDK_initialized_proven=false를 SDK가 없다는 증거로 해석하지 않는다. optional CPU/thread/module 접근 오류만 public error metadata로 남기며 높은 권한을 요구하지 않는다. actual 자기 process complete-module query, denied snapshot incomplete, actual compact preflight semantic/roundtrip/signature 거부, A/B profile/bytes guard·High 거부·실제 read-only audit-shape 검증을 포함해 **41개 검증 통과**다. 이 구현 검증에서 실제 game/UAC/slot/admin/rule action은 수행하지 않았다.

## 공개 안내 확인을 위한 B 유지

사용자의 공개 안내 확인을 위한 `--public-review`는 `--mode normal --profile online-config-analysis --variant admin-launcher-off`에만 허용한다. 실행 command는 `observer.py --mode normal --profile online-config-analysis --variant admin-launcher-off --public-review --run`이며 **--seconds를 넣지 않는다**. 이 flag가 actual observation을 정확히900초로 고정한다. 다른 profile/variant/mode와 seconds override(900을 직접 지정하는 경우 포함)는 거부한다. flag가 없으면 기존 default25/20..120초 범위 그대로다.

Root CONFIG_REVIEW에는 기존 조건 모두와 public_UI_review_requested=true, max_observation_seconds=900을 기록한다. metadata는 각 member25회·16 members/400 samples, windows32개 상한을 유지한다. 추가 UI input/screenshot/foreground 전환·자동 승인은 없다. 실제 source/file pins·ordinary controller/main/child·native identity·owned Job·정확한 handle cleanup을 유지하고 Ctrl+C와 예외의 finally에서도 자기 Job만 정리한다. 원래 main이나 descendants가 먼저 자연 종료하면 실제 종료에 맞춰 종료하며, 900초를 채우기 위해 앱을 다시 시작하지 않는다.

Root가 official GLFW3.4 win32_window.c의 등록 literal을 검증한 공개 class `GLFW30`만 whitelist에 추가했다. 실제6-char SHA ccbfc78b6de79b018134e144ddc26e8be4005efef5aa0869ebe5345dd03189de와 일치하지만 game entry라는 label은 추가하지 않는다. custom-drawn 문구와 계정 정보는 추정하거나 수집하지 않는다.

fixed900/잘못된 flag 조합·seconds override·Root review900 필드·fake-clock 실제900초와400/32상한·Ctrl+C exact cleanup·GLFW literal SHA 검증을 포함해 **44개 검증 통과**다. 이 구현 작업에서는 실제 game/slot/UAC/admin/network/rule 동작을 수행하지 않았다.

## 별도 C: 공개 multi-client 설정 비교

C는 `--mode normal --profile online-config-analysis --variant sdk-multiclient --seconds 120 --run`으로 준비한다. variant role=`SDK_MULTICLIENT`, candidate=`work/standalone_boot/current-sdk-multiclient.candidate.bin`, SHA256=`85497a9d4c5abfaff33d14766874e74eca93bda96f1745f5dc17f4ca74d150e7`, size39144728/build26.9.29.2001이다. C는 B에서 SystemManager.enable-multi-client-mode false→true만 추가하며, CONTROL에서 정확히3개 semantic fields다. auth/ready/callback/token 값은 만들지 않는다. 실제 소비와 인과관계는 확인되지 않았다.

Root C record는 `tools/clone_observer/root-C-review.json`, schema=`lc-clone-online-C-review-v1`이다. 기존 unsigned-medium online-config record의 필드를 유지하면서 program_variant=SDK_MULTICLIENT/program_sha256=C literal/candidate_path=C absolute path/candidate_code_reviewed=true/roundtrip_preflight_verified=true/stock_signature_verified=false/publisher_signature_content_mismatch=true/operational_adoption=false/allow_verified_stock_high_relaunch=false를 설정한다. 추가로 public_UI_review_requested=false/max_observation_seconds=120을 요구한다. admin_source_sha256=current3ce/observer_source_sha256=current4/CLOSED5SHA/former host-owner 및 기존 normal-analysis scope는 그대로다.

candidate_preflight_sha256은 고정 `work/standalone_boot/sdk-multiclient-preflight.json` SHA256=`c7aeb460deaa01dee507ef0b960f48845c9baa97491c06efbc84314ea80b8393`다. schema=`lc-sdk-multiclient-trial-preflight-v1`/3494B의 CONTROL9ffc/JSON0ba7/source snapshot/current build/B frozen SHA와 policy/3 exact semantic fields/12 deepcompare·roundtrip·certificate/content digest checks/noAuthFake를 검증한다. A/B compact preflight와 review 파일은 변경하지 않는다.

API `OnlineCAnalysisGate(native,'sdk-multiclient')`는 공통 CLOSED/source/native absence/실제 fixed read-only physical Inspect/정확한 candidate+slot bytes 검증을 재사용한다. C artifact·schema·pure proof는 별도로 고정하며 Admin14의 C ImagePin 지원/ARMED를 꾸미지 않는다. 모든 프로세스 medium 이하/Job16/noBreakaway/source pins/retained handle cleanup/privacy와 false isolation/standalone 표시는 유지한다. C는 public-review 및900초를 거부하며 기존 default25/20..120만 허용한다. 기존 B의900초 특례와 CONTROL High 조건은 유지한다. STOP handshake는 이 단계에서 추가하지 않았다.

C preflight 실제 형태·잘못된 B 관계/3fields/12checks/서명 허위·별도 C review·고정 profile/hash·900/public-review 거부를 포함해 **47개 검증 통과**다. worker 검증에서 실제 game/slot/admin/UAC/UI/network/rules/RAM/argv 작업은 수행하지 않았다.

## 고정 ROUTE_B local socket 후보의 일반권한 관찰

`--mode normal --profile online-config-analysis --variant route-b --seconds 120`은 기본 **Plan**이다. Root가 검토한 뒤 `--run`을 붙인다. 별도 ROUTE_B만 허용하며 고정 path는 기존 clone LC.exe다. candidate=`work/local-route-static-trial.candidate.bin`, SHA256=`720d4f8bdc754f2f5ef2dd69cc9936f5edc7d9afc0473d7a885111cf64fc05e5`, size39144728/build26.9.29.2001이다. 기존 B의 두 설정을 그대로 유지하고 decoded game code39B host 입력 및4B port 입력 범위에서 `127.0.0.1:12000`만 바꾼다. multi-client=false, SDK/auth/ready patch=false다. 후보 publisher content digest는 불일치한다. runtimeLoader 수용·첫 socket·resource provider·게임 진입은 미확인이다.

Root review 파일은 `tools/clone_observer/root-route-B-review.json`, schema=`lc-clone-online-route-B-review-v1`이다. 기존 unsigned-medium online-config review 계약에 다음 **고정 필드**를 사용한다. 리뷰 파일을 observer가 생성하거나 승인 성공으로 꾸미지 않는다.

- `reviewed=true`, `profile="online-config-analysis"`, `normal_online_analysis_authorized=true`, `analysis_only=true`, `network_isolation_required=false`, `SDK_descendant_online_analysis_allowed=true`, `no_concurrent_manager_launch=true`
- `program=고정 clone LC.exe`, `program_variant="ROUTE_B"`, `program_sha256=720d...05e5`, `candidate_path=위 고정 후보의 absolute path`, `build=[26,9,29,2001]`
- `candidate_code_reviewed=true`, `route_candidate_reviewed=true`, `roundtrip_preflight_verified=true`, `stock_signature_verified=false`, `publisher_signature_content_mismatch=true`, `allow_verified_stock_high_relaunch=false`, `operational_adoption=false`
- `route={"ipv4":"127.0.0.1","port":12000}`, `SDK_auth_ready_patch=false`, `whole_app_isolation_proven=false`, `public_UI_review_requested=false`, `max_observation_seconds=120`
- `candidate_preflight_sha256="7b7326c21d708b5d335944e0b419eff968c72b431099905d4629226893de1718"`, `candidate_producer_sha256="22f8c15bdd908544b093a8abe356a79333b083ea993a4da92e4e5efed8395f01"`
- `admin_source_sha256=current3ce`, `observer_source_sha256=current core.py/windows.py/observer.py/tests.py 각각의 rawSHA dict`, `closed_state_sha256=5개 실제 CLOSED 상태 rawSHA dict`, `former_host={"pid":12460,"birth":"134355830290220367"}`, `former_owner={"pid":40940,"birth":"134355829987543068"}`
- `job_active_process_limit=16`, `cleanup_scope="owned_job_members"`, `slot_trial_family="ROUTE_B_LOCAL_SOCKET"`, `slot_file_id=이번 새slot 증거의 native ID`, `slot_transaction_sha256=아래 transactions.json rawSHA`, `slot_provenance_sha256=아래 control.provenance.json rawSHA`

fixed preflight는 `work/local-route-static-trial.json`, fixed producer는 `work/local-route-static-trial.py`다. rawSHA와 pure proof로 sourceCONTROL9ffc/B94fa/candidate720d/7 whole-record SHA·10 exact checks·host39B/port4B·loopback12000·B payload byteexact·JSON2semantic·SDK-auth-ready patchfalse를 검증한다. 다른 master/provider나 성공값을 invent하지 않는다. producer를 실행하지 않는다.

새 slot namespace는 `work/route_startup_trial/{transactions.json,control.provenance.json,control.snapshot.bin}`만이다. transactions schema=`lc-fixed-config-trial-transactions-v1`, provenance schema=`lc-fixed-config-trial-control-snapshot-v1`, family=`ROUTE_B_LOCAL_SOCKET`이다. 기존 C와 같은 base header에 `preflight_sha256`/`producer_sha256` fixed2가 추가된다. `candidate_sha256={"PrepareRouteB":720d...05e5}`와 current3ce/CLOSED5/own provenanceSHA/native slotfileID/length39144728을 요구한다. INTENT→COMPLETE의 sorted compact JSON+newline hashchain을 검증하고 마지막 action이 **PrepareRouteB COMPLETE/current720d**여야 한다. incomplete intent·foreign family·AB/C history·다른 hash·이미 Restore된 receipt는 거부한다.

candidate와 현재 slot bytes가 literal720d, 자기 새 snapshot이CONTROL9ffc인지 확인한다. native READ handle로 현재 slot/snapshot의 canonical path·no reparse·single hardlink·file ID를 검증하고 새 증거와 비교한다. source3ce/CLOSED5 strict schema, 이전 관리자/owner native absence, 새 고정 read-only Inspect의 실제 clone rule 양Store absence도 공통 gate에서 다시 검사한다. Admin14 ImagePin/ARMED 성공을 대신 만들지 않는다. prelaunch와 suspended child에서 동일 gate를 다시 적용한다.

ROUTE_B는 `public-review`/900초/codec diagnostic/다른 profile을 거부하고 default25/20..120만 허용한다. Job16/noBreakaway/KILL_ON_JOB_CLOSE·ordinary controller/main/all owned descendants·retained exact handle cleanup·공개 창 metadata 정책은 그대로다. Root가 쓰는 현재 observer4 SHA가 바뀌므로 기존 리뷰 기록은 새 파일 검토 전에는 stale다. **52개 검증 통과**: 기존47 + ROUTE_B의 static semantics/외래·incomplete 새slot chain/closed·native·rule gate/Plan·900거부/owned timeout·High 및 foreign hash 거부5개다. 구현 검증 중 실제 slot/game/network/UAC/admin/rule 동작은 없었다.
# ROOT_MOUNT_ROUTE_B 별도 관찰

고정 명령은 bundled Python `-X utf8 -I -B tools/clone_observer/observer.py --profile root-mount-analysis --variant root-mount-route-b --mode normal`이다. 기본은 PLAN이고 실제 Root 실행에만 `--run`을 붙인다. 이 profile은120초/Job16/KILL_ON_JOB_CLOSE/noBreakaway/all-medium이며 다른 variant·codec mode·900초·public-review를 거부한다. 기존 A/B/C/ROUTE profile의 역사적 CLOSED 조건은 유지한다. 시험 보고는 별도 `work/root_mount_resume/observer-proof/last-run.json`과 `observer-report.md`에 저장한다.

Root review는 `tools/clone_observer/root-mount-review.json`, schema `lc-clone-root-mount-review-v1`이다. 고정 profile/ROOT_MOUNT_ROUTE_B hash374691.../build26.09.29.2001/clone경로, analysis_only=true/normal_online_analysis_authorized=true/network_isolation_required=false/whole_app_isolation_proven=false, candidate_code_reviewed=true/roundtrip_preflight_verified=true/stock_signature_verified=false/publisher_signature_content_mismatch=true/operational_adoption=false/SDK_auth_ready_patch=false/allow_verified_stock_high_relaunch=false, job_active_process_limit=16/cleanup_scope=owned_job_members/public_UI_review_requested=false/max_observation_seconds=120/no_concurrent_manager_launch=true를 요구한다. 현재 observer4 SHA, admin3ce SHA, candidate_path, preflight52dc.../producer75e8... SHA, slot_source_sha256={slot.py,tests.py}, slot_manifest_sha256/slot_profile_sha256, 오늘 closed_state_sha2566, slot_trial_family=ROOT_MOUNT_ROUTE_B_LOCAL_SOCKET, slot_file_id, slot_transaction_sha256/slot_provenance_sha256도 Root가 실제 값으로 바인딩한다. 자세한 required fields는 새 gate의 fixed dict와 slot module 검증에 있다.

고정 mount slot의 pure validator로 오늘 core26976/source3ce CLOSED, 정상 supervisor23632 CLOSED, 이전 launcher d09 이력을 구분한다. 고정 이전 owner5개의 native birth/image 부재와 완전한 LC inventory, 마지막 COMPLETE PrepareRootMount hashchain, 동일 native slot/snapshot file ID, 현재 후보·slot·CONTROLsnapshot 전체SHA, 배치된 고정67개 asset의 크기/SHA를 확인한다. source/metadata/snapshot/candidate/assets는 read-share pin을 Job cleanup까지 유지한다. fresh literal clone firewall Inspect는 두 store의 owned clone rule 부재를 검사한다. 원본 규칙이나 관리자 scope를 변경하지 않는다.

`require_PURPLE_absent`는 Root review의 필수 bool이다. true이면 prelaunch와 suspended-child 재검사 시 PURPLE 부재를 요구하고, false이면 기존 PURPLE을 변수로 기록하는 초기 warm 분석을 허용한다. 사용자 PURPLE을 종료하지 않는다. 현 패치는 SDK 인증·공식 초기화 코드를 제거하지 않으므로 PURPLE이 살아 있는 관찰은 그 영향으로부터 독립되었다는 증거가 될 수 없다. PURPLE 부재는 cold 비교의 필요한 통제 조건이며, 부재만으로 단독 기동이 입증되지는 않는다. cold_PURPLE_independence_verified/standalone_play_verified는 이번 observer에서 항상 false로 남는다.

기본 metadata-only observer는 메모리를 읽지 않는다. 기존 원본 D/CONTROL reader5는 변경하지 않았다. 별도 `tools/root_mount_public_state/`의 clone374691·cloneSDK·retained main creation handle 계약을 구현했으며, Root review의 `public_state_diagnostic` 고정 구조가 enabled=true이고 소스4/contract rawSHA·120초5초25회·read-only/private-data 제외를 승인했을 때만 main metadata sample에 typed public_states를 추가한다. Root phase/FM availability/UI completion/concrete NP presence와 source-known NP/SDK 준비 bool을 읽으며 raw master32/key/buffer는 읽지 않는다. 값이 unknown이면 false로 바꾸지 않는다. 상세 필드는 별도 tool README에 있다.

