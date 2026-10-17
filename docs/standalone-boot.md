# PURPLE 독립 기동 — 현재 빌드 준비 결과

2026-10-04. 현재 원본 `26.09.29.2001` / SHA-256 `9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`에서 설정을 복원하고 클론 기동 관찰을 이어가고 있다. **최신 실제 실행·권한·프로세스 상태와 다음 작업은 [ACTIVE_TASK.md](ACTIVE_TASK.md)를 따른다.** 아래 시각이 붙은 “미실행”·후보 준비 기록은 당시 상태이며, 이후 실제 CONTROL/런처 후보 비교와 CONTROL의 같은 클론 High 재실행을 관찰했다. 실제 독립 기동·local 게임 화면 진입은 아직 미확인이다.

## 최신 결과 — 이전 조사 중단점과 구분

### 후속 준비 — 2026-10-04 16:30 KST

변경하지 않은 현재 클라이언트 복사본 `work/standalone_boot/current-unmodified-clone/`을 일반 권한으로 준비했다. root 파일17개와 pack/Emblem만 포함한 **134개/3,685,908,451B**이며 LC.exe hash는 현재 원본 `9ffc…b7af`와 같다. worker가 전후 source size/mtime 변동0과 계획 밖 파일0을 확인했고, 주 세션도 파일 수·총크기·LC hash·user/cache/log 폴더 부재를 독립 조회했다. [복사 기록](../work/standalone_boot/clone-stage-report.md)과 staged=true인 clone-plan.json을 남겼다. 계정·캐시·로그·업데이트 상태는 복사하지 않았다. 실제 게임 실행·네트워크 격리는 아직 없다. 원본 경로의 방화벽 규칙은 이 clone에 적용되지 않는다.

추가 정적 조사 `startup_followup.py`는 현재 source의 정확한 anchor10개와 wrapper `68ac→6ed8/ab500` 입력2를 확인했다. getter가 돌려줄 데이터의 **현재 원본 설정으로 만든 준비 fixture**를 입력한 조건에서, volatile register는 unknown으로 두고 CPU flag64개를 열거해 모두 `6ffe→ada94` decoder 입력 경계에 도달했다. packed3473/decoded8790 길이와 local output 계약이 일치했다. 주 세션이64개를 재실행하고 기존 query 성공384개/실패12개 calibration도 재실행해 통과했다. 이 결과는 실제 getter 반환 관찰이나 startup reachability 증명이 아니다.

남은 경계는 `c84e8`의 restore-flags/pop 앞 ECX reaching definition, `cb6e7`이 읽는 stack+230의 기원, decoded JSON에서 LauncherChecker.switch를 읽는 실제 startup consumer다. [후속 근거](../work/standalone_boot/startup-followup.json)는 이를 미증명으로 표시하고 필요한 최소 관찰을 selector·동일 호출의 pointer continuity 여부·길이/digest·공개 switch bool로 한정했다. 실제 observation 도구는 구현·실행하지 않았고 argv/token/게임 key·원시 주소를 수집하지 않았다. SDK·UI·자원 준비와 로컬 접속을 이 조건부 모델로 완료 처리하지 않는다.

이후 아래 “clone은 계획만/미복사” 문장은 앞선 준비 시점의 기록이며 현재 staging 상태는 이 항목을 따른다. 후보 `.candidate.bin`은 그대로 검토용이며 clone에 채택하지 않았다.

### 호출 인수 역추적 — 2026-10-04 17:01 KST

[역추적 근거](../work/standalone_boot/backward-startup-report.md)에서 `cb6b8`의 incoming ECX home slot과 `cb6e0`의 stack+230이 같은 저장소임을 exact prologue/stack delta로 확인했다. complete entry→call256개가 입력을 그대로 wrapper에 전달했다. `c8491→c84e8`도 **c69d4 post-prologue frame base와 home 보존 조건**에서256개가 일치했지만 전체 c69d4 body 도달은 미증명이다. 상위 `30f60`은 local loop index를 전달하고 count helper의 source-only64개는7을 반환했다. 실제 선택을 결정하는 descriptor byte 생성과 parent-loop entry/control이 남았다.

[C69 상위 조사](../work/standalone_boot/upstream-c69-report.md)에서는 `b7f6→b82b`, `34241→342a9`의 local index 전달896개와 comparator EAX=3을 명시한 조건448개를 확인했다. 주 세션이 두 새 script의 전체 case를 독립 재실행해 통과했다. index0..6과 descriptor=3은 transfer 검사 입력이며 실제 startup 값으로 읽거나 만들어 넣은 것이 아니다. 실제 selector2 선택·전체 startup 도달·JSON→LauncherChecker 소비·SDK/UI/resource 준비는 미확인이다. 다음 관찰은 정확한 caller의 index·descriptor·branch와 같은 호출의 pointer-free continuity로 좁혔으며 원시 key/token/argv·stack dump를 요구하지 않는다.

current getter의 ECX=2 입력이 설정 RVA `0x13baf44`/3,489B를 고르는 것은 **명시적인 Windows self-image query 성공 조건의 source 모델**로 확인했다. selector0의 이미 확보한 7 record source와 먼저 대조하고, 3개 입력 × 2개 초기 register 모델 × 64개 volatile CPU flag 조합 **384개**가 같은 getter source/size에 도달했다. 실패·잘못된 반환 길이 **12개**는 query helper의 NULL 반환으로 분리했다. 실제 LC의 API 성공은 관찰하지 않았다. startup caller가 의미상 selector2를 공급하고 JSON 설정 consumer에 연결하는 전체 chain은 여전히 미증명이다.

현재 원본과 한 설정만 다른 검토 파일은 `work/standalone_boot/current-launcher-switch-false.candidate.bin`이다. 39,144,728B, hash `7e66b52b18caf852c741d43abdef0398faf2894c9b989172a8123b16141f1d33`. **PE 내용을 가진 검토용 bin이며 실행·채택 대상이 아니다.** `candidate-preflight.json`의 8개 검증은 source/getter binding, 한 값 변경 preflight, header/layout/길이·certificate bytes 보존, payload 변경 범위, 저장 후 hash를 확인한다. 원본 Authenticode content digest는 인증서 안의 저장 digest와 일치하고 이 후보는 일치하지 않는다. 인증서 chain/Windows trust는 검사하지 않았다. SDK·UI·자원·최초 로컬 접속 성공도 미확인이다.

후보 생성 시에는 일반 파일 쓰기만 했고 실행 helper를 만들지 않았다. 당시 clone은 계획만 있었으며 이후 후속 준비에서 실제 복사했다. 아래 초반 조사에서 "caller 미증명"/"PE 미저장"이라고 적힌 부분은 당시 결과다. Startup 소비 연결·실제 기동은 여전히 미완료다.

## 이번에 현재 파일에서 확인한 근거

| 항목 | 현재 확인값 |
|---|---|
| LC 파일 | 39,144,728 bytes, 위 hash 유지 |
| embedded manifest | RT_MANIFEST ID1/lang1033, RVA `0x3e93540`, 381B, `asInvoker`, `uiAccess=false` |
| raw PE entry | RVA `0xd390c`, file offset `0xd2d0c`; 128B hash는 `work/standalone_boot/preflight.json` |
| raw imports | `USER32.DLL`; 복구 selector0 game image imports와 구분 |
| 정적 selector0 records | 기존 current-build 7개를 size/hash로 다시 대조함 |
| 현재 런처 설정 데이터 후보 | RVA `0x13baf44`, raw offset `0x13ba344`, 전체 block 3,489B |
| 현재 복원 JSON | 8,790B, hash `0ba7f4ff2c19fad5542f3724598dd380790df5e5d512922a60e3f89ade0655a6` |
| `LauncherChecker` | switch=true, action=suicide, NC/Valve issuer 허용 목록, 동일한 한국어 런처 요구 문구 |

`asInvoker`는 첫 LC 프로세스가 요청하는 권한 수준이다. 이후 SDK/자식이 관리자 작업을 요청하지 않는다는 보장은 아니다. 과거 직접 실행·switch-false 실행 기록은 구버전 `26.08.28.2002` 결과이며 현재 EXE의 결과로 옮기지 않았다.

현재 `ncplatformsdk-cpp.dll`, `PurpleCommunitySdk.dll`, `YetiLoaderDLL.dll`의 공개 export 이름을 읽었다. named exports는 각각 319/532/20개이며 `offline` 이름은 없었다. NC SDK에는 `initialize`, `loadConfiguration`, `setConfigurationServerUrl`, `showTrafficBalancer`가 있다. **export 이름만으로 내부 cache/offline 경로의 존재나 부재를 판정하지 않는다.** 초기 SDK→configuration→traffic callback가 NP 준비를 만드는 기존 현재 코드 근거는 유지되며, PURPLE 없이 그 계약이 정상 완료되는 방법은 미확정이다.

## 비실행 설정 조각과 정확한 한계

새 `recover_config.py`는 이전 evaluator를 실행하지 않는다. 고정 현재 LC에서 selector0용 48개 immediate byte writer를 독립적으로 확인하고, 기존 현재 7 record의 frame 길이를 대조했다. 다음 좁은 함수 구간에서 selector1/2용 48개의 별도 byte writer를 정확한 stack displacement로 확인했다. 두 transient 정적 XOR buffer는 출력·파일에 남기지 않고 finally에서 지운다. 게임 resource master, 인증값, process memory는 다루지 않는다.

현재 selector0 뒤에서 frame들을 읽고 다음 설정 block을 복원했다. 이것은 **연속 block 배치에 기반한 후보**다. JSON framing·길이·종료 marker·현재 `LauncherChecker` 내용은 확인했지만, current selector2 getter의 선택 분기가 정확히 이 pointer/size를 소비하는 **코드 호출 연결은 아직 증명하지 않았다.** 따라서 RVA를 운영 패치 주소로 승인하거나 실행 가능한 EXE를 저장하지 않았다.

비실행 조각 `work/standalone_boot/current-switch-false-config-fragment.bin`은 다음 검증을 통과했다.

- JSON 객체 기준 변경은 `LauncherChecker.switch` true→false 한 값뿐이며 복원 JSON 길이는 그대로다.
- 독립 LZSS encoder의 동적 계획으로 bit 비용을 줄여 3,433B 재압축했고, 원래 3,473B payload에 들어간다.
- 재압축과 원래 남는 payload를 보존한 padding의 두 decode 결과가 수정 JSON과 byte 단위로 같다.
- 12B header, 4B trailer, 전체 EXE 길이를 유지한다. 메모리 내 whole-EXE 비교에서 변경 3,027B는 raw `[0x13ba3d7,0x13bb0b9)` 안에 있다.
- 조각 hash는 `2ffa74df4458a4b1ad784cc4d557c280f836a5a8d0083c650c59b691e5316b55`다. 실행 불가능한 3,489B 데이터이며 current full-EXE candidate는 저장하지 않았다.

이 내용 변경은 기존 publisher signature가 그대로 유효한 변경이 아니다. Windows trust나 보호 loader의 수용 여부는 시험하지 않았다. 런처 안내를 넘는다고 SDK·UI·자원·최초 localhost가 준비된다고 볼 수도 없다.

## 다음 최소 실험

### 일반 Windows 계약 확인과 조건부 getter calibration

GS 접근의 다음 사용은 game/auth/TLS 준비 flag가 아니라 Windows module lookup이었다. 설치된 SDK `10.0.26100.0`의 `winnt.h`/`winternl.h` hash와 AMD64 field prefix를 대조해 `GS:+30 → NT_TIB.Self`, `TEB:+60 → PEB`, `PEB:+18 → Ldr`, `LDR:+20 → InMemoryOrderModuleList`를 확인했다. 현재 code anchor는 `4d9e2`, `4da67`, `507b0`, `507be`다. 현재 source가 구성한 whitelisted lookup 이름은 `ntdll.dll`이며 LC module base로 바꾸지 않았다. [NtCurrentTeb](https://learn.microsoft.com/en-us/windows/win32/api/winnt/nf-winnt-ntcurrentteb), [PEB_LDR_DATA](https://learn.microsoft.com/en-us/windows/win32/api/winternl/ns-winternl-peb_ldr_data)

`own_os_abi.py`는 **자기 Python process/current thread**만 읽었다. 임의 PID/address 입력, 다른 process, LC/PURPLE, command line/env/user data, raw 주소·byte 출력을 포함하지 않는다. Current thread 반환 size/IDs와 TEB Self를 먼저 맞추고, bounded loader traversal에서 정확히 whitelisted NTDLL을 `GetModuleHandleW`/`GetModuleFileNameW`와 대조했다. Public SDK가 예약한 name offset `entry+58/+60`은 현재 Windows build26200의 자기 process에서만 비교했다. Source의 head-minus10→entry+0 traversal도 같은 NTDLL을 찾았다. [NtQueryInformationThread](https://learn.microsoft.com/en-us/windows/win32/api/winternl/nf-winternl-ntqueryinformationthread)

자기 NTDLL의 공개 `NtQueryVirtualMemory` export 주소에 current-process pseudo-handle로 query하고, NTSTATUS0/return48, AllocationBase==자기 NTDLL handle/MEM_IMAGE, `VirtualQuery`와의 일치를 확인했다. **13개 check 통과**이며 LC 주소를 읽거나 LC query 성공을 관찰한 결과가 아니다. Source는 `0x66517`에서 같은 export RVA의 `NtQueryVirtualMemory`/`ZwQueryVirtualMemory` alias로 연결됐다. 인수는 current process -1, 자기 source code RVA `0xd41f3`, class0, local output buffer, size48, local ReturnLength였다. [NtQueryVirtualMemory](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/nf-ntifs-ntqueryvirtualmemory), [MEMORY_BASIC_INFORMATION](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/ns-ntifs-_memory_basic_information)

Conditional fixtures는 **mapped own-image query가 성공하고 48B를 돌려준 경우**만 AllocationBase를 정규화했다. 다른 MBI fields는 unknown, volatile registers는 unknown으로 두고 CPU flags 64개를 모두 열거했다. Source는 `6b2a2`에서 ReturnLength, `2f099`에서 MBI+8 AllocationBase를 읽고 `2f0a2`에서 반환하여 caller `ab5f9`로 돌아왔다. SDK/auth/UI/resource flag를 만든 과정은 없다.

| getter 입력 | 조건부 source 결과 | success cases |
|---|---|---:|
| 0 | RVA `d494a`, 11,652,850B; 기존 현재 7 record source와 대조 | 128 |
| 1 | RVA `bf183c`, 8,165,128B; 현재 frame walk와 대조 | 128 |
| 2 | RVA `13baf44`, 3,489B; 현재 런처 설정 block과 대조 | 128 |

### current startup 소비 연결의 남은 경계

현재 raw wrapper prologue 후보 `68ac`/`21e03`와 21개 direct call opcode를 별도로 확인했다. `68ac`에 ECX=2와 local output fixture를 준 source path는 `6ed8 → ab500`에 도달하여 getter ECX=2를 유지한다. 하지만 `68ac`를 부르는 startup raw 후보 `c84e8`, `cb6e7`이 **실제 도달하는 selector2 assignment**를 제공한다는 증명은 아직 없다. `cb6e0`는 `[rsp+230]`에서 ECX를 가져오며 literal2가 아니다. Getter 뒤의 outer XOR/JSON parser→LauncherChecker 연결도 startup caller와 함께 미완료다. `config-consumer-candidates.json`에 이를 분리했다. `68ac` 입력0/1 fixture의 local read `1f894` 중단을 실제 client blocker로 해석하지 않는다.

Raw PE exception table의 function 경계는 복구 game-code 주소에 대응한다. 이를 보호 loader의 raw bytes 함수 경계로 그대로 적용해 linear disassembly하거나, 후보 opcode가 있는 것만으로 실제 호출을 주장하지 않는다. 다음 조사 대상은 위 두 current startup caller와 selector2 JSON consumer 연결이며, SDK·맵 서버 확장이나 실제 `.bin` 실행이 아니다.

### current caller 연결의 추가 오프라인 시도

새 `trace_dispatch.py`는 이전 evaluator를 실행하지 않고 current raw PE의 scalar 명령만 제한적으로 해석한다. current entry `0xab500`의 첫 명령 `mov dword ptr [rsp+8], ecx`와 hash를 확인했다. raw 코드 범위에서 직접 call 후보는 `0x6ed8 → 0xab500`, `0xae5ac → 0xab500` 두 개다. 이 call opcode가 맞는 것과, 보호된 caller가 ECX에 **selector2 의미의 2**를 넣어 실제 도달한다는 ABI/경로 증명은 구분했다. 현재 후자는 미완료다.

ECX=0/1/2 × 두 초기 nonargument register 모델의 6개 bounded case를 진행했다. 첫 중단점 `0x52f3d`의 `movzx edx, byte ptr [rsp+0x20]`는 초기화되지 않은 **로컬 dummy byte**였다. source의 `0x52f2f → 0x52f57 → 0x941ec` 전체 leaf를 정확한 명령과 hash로 대조한 결과, DL은 home slot에 한 번 저장되고 읽히지 않으며 기존 child가 정확히 21B를 zero-fill하고 receiver를 반환한다. 유사한 `0x20167 → 0x2018f → 0x4c0d3`도 source 검증 후 20B zero-fill로 해석했다. 이 dead dummy 값을 0으로 만들어 통과시키지 않았다. 첫 함수 반환의 volatile EDX는 unknown으로 유지하고 이동·저장만 taint를 보존한다. 실제 consumed arithmetic나 bit 단위 복원이 필요하면 거부한다. 반환 register, caller home 저장과 source의 마지막 stack ADD로 생기는 flags도 반영했다. 두 summary는 game/auth/resource 상태를 다루지 않는다.

최종 6개 case는 **6,626 명령 뒤 `0x4d9e2: mov rax, qword ptr gs:[0x30]`**에서 모두 `unmodeled_GS_TEB_access`로 중단했다. 최근 직접 path는 `0x50790 → 0x4d9f6 → 0x4d986 → 0x4d9e2`다. 이는 raw source가 없어서가 아니라 **현재 offline 모델에 GS segment/thread state와 그 후속 helper 계약이 없기 때문**이다. 실제 thread 상태를 읽거나 기존 evaluator의 module-base 반환 shortcut을 그대로 적용하지 않았다. 이 단계에서는 allocator placeholder에도 도달하지 않았다.

이 결과는 current selector0 getter 출력과 이미 확보한 7 record source pointer/size를 **해석기에서 재현해 calibration한 결과가 아니다**. 알려진 selector0 framing 대조는 앞서 `recover_config.py`에서 별도로 통과했지만 이 caller 해석기는 copy boundary `0xabf91`에 이르지 못했다. 따라서 selector2 pointer/size 반환이나 config consumer까지의 chain은 아직 증명하지 않았다. `dispatcher-provenance.json`은 exact source pin, leaf hash/checks, current call 후보, 6개 중단점과 마지막 20개 redacted 명령을 남긴다. 보호가 영구적으로 static 분석을 막는다거나 별도의 인증/VM 관문이 확인됐다는 결론은 내리지 않는다.

다음 bounded 조사는 위 GS-dependent helper의 **현재 self-module/base 및 caller 인수 계약을 source로 분리 증명**하고, 그때만 실제 알려진 selector0 pointer/size를 재현하는 것이다. 임의 Windows 구조나 API 반환값을 만들어 현재 fragment를 실행 EXE로 승격하지 않는다. 실제 SDK·자원 관문, 관리자 runtime/UAC 및 clone 격리의 미검증은 이 모델 부족과 별개다.

첫 준비는 **current selector2 source getter/분기→위 RVA/3,489B→config consumer** 연결을 file-only로 확인하는 것이다. 그 연결이 확인될 때 현재 EXE 한 파일의 독립 복사본에서 이 조각의 roundtrip·byte 범위·서명 영향까지 다시 대조할 수 있다. 구버전 EXE나 raw offset을 현재 빌드에 적용하지 않는다.

그 뒤 runtime의 작은 control 실험은 현재 **수정하지 않은** LC를 독립 clone에 `LC.exe` 이름으로 놓고 clone을 working directory로 하여, 일반 권한·인수 없음·PURPLE 없음으로 한 번 시작해 첫 gate/exit만 관찰하는 것이다. 수정 후보와의 비교는 별도 실험이다. 시작 전 clone path에 대한 실제 네트워크 격리와 쓰기 범위를 확보해야 한다. 원본 경로용 firewall 규칙은 clone을 보호하지 않는다. 현존 elevated guardian의 생존이나 asInvoker만으로 이 준비를 충족하지 않는다. 추가 UAC 창은 재시도하지 않는다.

`prepare_clone.py`는 기본 dry-plan이며 실행 기능이 없다. `--stage`만 일반 파일 복사를 수행한다. 이번에는 **134개/3,685,908,451B의 계획만** 저장하고 3.69GB clone을 만들지 않았다. `user`, account/cache/log state와 업데이트 staging은 포함하지 않는다. 실제 파일명·DLL·asset 복사는 정적 경로 보존용이며 최소 UI dependency가 확인됐다는 뜻은 아니다.

독립 실행의 남은 관문은 각각 분리한다.

| 관문 | 현재 상태 |
|---|---|
| current LauncherChecker를 읽는 정확한 caller | 데이터 후보 복원, caller 연결 미증명 |
| SDK initialization/configuration/traffic completion | 정상 현재 경로 근거 있음, 독립 완료 계약 없음 |
| 최초 socket localhost-only | 지원 argv/list filter로 해결되지 않음; 복구 후 최초 connect 전 설치점 미확정 |
| 현재 resource 공급 | `/memory`, `/pack`, `/user` 경로 있음; 일반 `data/*` override 및 최소 UI dependency 미증명 |
| 정상 inner master provenance | 확인된 nonzero install은 version field13; 재사용 값 없음. outer resource.key와 구별 |
| 첫 화면 및 character select | UI·BI timer·NP 조건 존재; 실제 current 독립 진행 미검증 |

SDK/auth/resource 준비 flag, key 또는 응답값을 만들어 관문을 완료 처리하지 않는다. 전투·맵 서버 확장은 이 독립 기동 판단 뒤에 진행한다.

## 재현과 검증

```powershell
$pythonRuntime = 'C:\Users\Chansol\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $pythonRuntime -I -B work/standalone_boot/file_preflight.py --verify
& $pythonRuntime -I -B work/standalone_boot/recover_config.py
& $pythonRuntime -I -B work/standalone_boot/prepare_clone.py
& $pythonRuntime -I -B work/standalone_boot/trace_dispatch.py
& $pythonRuntime -I -B work/standalone_boot/own_os_abi.py
& $pythonRuntime -I -B work/standalone_boot/trace_dispatch.py --os-contract
& $pythonRuntime -I -B work/standalone_boot/trace_dispatch.py --ntdll-model
& $pythonRuntime -I -B work/standalone_boot/trace_dispatch.py --query-fixtures
& $pythonRuntime -I -B work/standalone_boot/inspect_consumers.py
& $pythonRuntime -I -B work/standalone_boot/recover_config.py
& $pythonRuntime -I -B work/standalone_boot/prepare_candidate.py
& $pythonRuntime -I -B work/standalone_boot/startup_followup.py
& $pythonRuntime -I -B work/standalone_boot/backward_startup.py
& $pythonRuntime -I -B work/standalone_boot/upstream_c69.py
```

모두 이번 새 루트에서 만든 file-only script다. 최종 실행은 전부 통과했다. 첫 번째는 현재 원본·SDK metadata·7 records와 저장 preflight를 비교하고, 두 번째는 현재 framing/JSON/한 값 변경/재압축 roundtrip/변경 범위·원본 보존을 확인한다. 세 번째는 dry-plan만 만들었다. 게임/PURPLE/관리자 실행, UAC, 네트워크, firewall/process 변경, 보관 재hash는 하지 않았다.

`recover_config.py`의 instruction decoder는 이전 원본의 `work/static_client/deps/capstone` 제3자 library를 읽기 전용으로 가져온다. 이전 조사 script는 실행하지 않는다. 모든 재현 명령은 `-I -B`를 쓰며 decoder import 앞에서도 `sys.dont_write_bytecode=True`를 고정하여 이전 dependency 위치에 새 `__pycache__`를 쓰지 않는다. 로컬 helper를 가져오는 두 script는 `-I`에서도 동작하도록 자기 파일의 절대 디렉터리를 먼저 등록한다. 이번 검증의 Python source 3개도 AST 구문 검사를 통과했다.

추가 caller 조사 script도 같은 절대 local import·`dont_write_bytecode`·제3자 decoder 규칙을 따른다. 최종 명령은 구조화된 **6개 inconclusive/blocked case**를 정상 저장했으며, 이것을 getter 성공으로 표시하지 않는다. `trace_dispatch.py` 추가 후 source 4개 AST 구문 검사와 current LC pin 대조를 수행했다.

이후 확장한 최종 준비에는 자기 Python OS ABI13개, 조건부 getter384개/실패12개, startup wrapper3case의 명시적 partial 결과, candidate8개 검증을 포함한다. Source8개 AST와 원본 pin/candidate byte 범위 검사를 마쳤다. Native OS 확인은 승인된 자기 Python 전용 예외이며 game/native game 함수·다른 process 접근은 하지 않았다. Microsoft primary 문서 조회 외에 게임/플랫폼 인증 network 요청은 없었다. 이 항목이 초반 file-only/GS 중단 기록을 현재 성공으로 잘못 확장하지 않도록 결과의 scope를 유지한다.

검사 중 온라인 설치 파일이 잠시 없어졌다가 돌아오고 `UpdatedList.dat` 크기가 달라지는 변동을 관찰했다. 재시도 때 버전 XML·SDK가 돌아왔으며 현재 LC pin과 저장 SDK metadata 최종 비교는 통과했다. 다음 runtime 준비 때 다시 안정적인 source/DLL pin을 확인해야 한다.
