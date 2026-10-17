# 캐릭터 진입 통합 진단과 작업 기준

## 2026-10-07 실제 시험 후 갱신

CP06 실제 시험에서는 **자체 선택 Begin·입력·genuine Network pair가 PASS, enqueue·task 등록이 true, 실제 own Connect의 원래 반환값이 true**였다. 따라서 앞선 선택 준비 차단은 넘어섰다. [선택 기록](../work/local_native_login_create_exec_boundary/runs/cp06-primary-20261007-01/selected-boundary.json), [Connect 기록](../work/local_native_login_create_exec_boundary/runs/cp06-primary-20261007-01/own-connect-result.json). factory 검증은 선택 단계에서 수행하지 않았으며, DTO 검증 파일은 없어 도달 여부 UNKNOWN이다. 이를 factory 검증 성공이나 실패로 바꾸어 해석하지 않는다.

같은 시험의 초기 conn2는 VERSION·COUNTS 합계168B/2frame을 유지했고, 후속 conn4는 KEY1frame 뒤 C2S0/EOF였다. 자체0263 소비도0이다. 다음 첫 미해소 구간은 **후속 KEY의 클라이언트 처리→queued task 실행→VERSION 송신 또는 그 전에 일어난 종료**다. Connect 성공만으로 KEY 처리까지 완료됐다고 주장하지 않는다. 현재 관측은 DTO serializer·로그인 ACK가 이 앞단 정지의 원인이라는 근거를 제공하지 않는다. [실제 보고](../work/local_native_login_create_exec_runtime/trial-report.json), [기존 KEY 구간 Source](../work/local_ready_entry_import_fix/second-key-independent.md).

CP06은 60초 관측 후 소유 프로세스 정리와 [정상 CONTROL 복구](../work/local_native_login_create_exec_runtime/root-post-restore.json)를 완료했다(CONTROL9ffc·같은 FileID·restoration_required=false·LC/PURPLE0). **캐릭터·맵 진입은 여전히 미완료**다. 아래는 CP05와 CP04에서 이 수정까지 이른 근거다.

CP05에서는 **선택 bridge 진입과 원래 함수 복귀는 확인됐지만, 자체 선택 세션을 시작하기 전에 메시지 factory의 실행 가능성 검사에서 탈락했다.** 선택 context/base/qualified는 PASS였고, factory 코드 복사·비교, setter 검증, Begin·task 등록은 수행되지 않았다. 후속 연결은 KEY 뒤 C2S0·109ms EOF였으며 자체0263 수신도 없다. 실행 검사의 세부 탈락 조건은 기록되지 않아 메모리 권한 문제의 원인은 아직 UNKNOWN이다. [선택 실제 기록](../work/local_native_login_selected_boundary/runs/cp05-primary-20261007-02/selected-boundary.json), [통신·정리 대조](../work/local_native_login_selected_actual_review/communication.md), [검사 조건 대조](../work/local_native_login_selected_actual_review/eligibility.md).

확인된 설계 문제는 **나중에 메시지를 만들 때만 쓰는 factory·setter 검증을 선택·소켓 준비의 선행조건으로 둔 결합**이다. 두 함수는 선택·Init·Task·Connect에서 호출되지 않고 `SendOwnLoginHeld`에서 처음 사용된다. CP06은 이 검증을 삭제하지 않고 실제 DTO 생성 직전, 송신 시도 상태 소비 전에 수행하도록 분리했다. 선택 단계는 실제 필요한 getter·객체·소유권 조건을 유지한다. DTO 검증에 실패하면 생성·setter·송신을 하지 않고 기존 자체 경로 취소 정책을 지킨다. 같은 기존 Query의 상태만 그 지점에서 기록해 세부 원인을 구분한다. callback 중 close 취소도 생성 직전에 재확인한다. [독립 Source 검토](../work/consolidated_diagnosis_20261007/cp06-readiness-review.md)와 관련 compiled fixture·[collector 연결 검사](../work/local_native_login_create_exec_runtime/tests.json)를 완료했으며, 실제 결과는 위 CP06 항목에 기록했다.

아래 CP04는 앞선 시험 이력이다. CP05도 소유 프로세스 정리와 정상 CONTROL 복구를 완료했으며, 캐릭터 선택·맵 진입은 아직 확인되지 않았다.

CP04 후보에서 **초기 VERSION158B·COUNTS10B 통신이 실제로 재현됐고, 이전 unmatched guard 없이 60초 관측을 마쳤다.** 이후 소유 프로세스 정리와 정상 CONTROL 복구가 기록됐다. 이것은 새 후보의 실제 진전이며, 과거 TCP0의 원인을 한 조건으로 소급 확정하는 결과는 아니다. 이번에는 typed Scene 관측을 하지 않아 Lobby·캐릭터 화면 회복까지 주장하지 않는다.

후속 연결은 서버 KEY12B 전송 뒤 C2S0으로125ms 만에 EOF였다. 자체0263 receipt도 없다. 현재 가장 앞의 미해소 경계는 **그 선택 연결의 KEY 소비/준비→첫 VERSION**이며, ACK·캐릭터 응답이나0263 serializer부터 바꿀 근거는 없다. producer는 원래 VERSION consumer의 COUNTS 송신 뒤에 자체0263를 붙이므로 그 앞 구간을 구분해야 한다.

CP04의 진단5개는 전역 once를 먼저 차지한 Close 역할의 기록이다. 이를 Selected/Connect/Sender 결과로 일반화하지 않는다. own 준비 함수에는 실패를 영구 고정하는 latch가 없고, factory/setter의 두10B anchor도 현재 후보의 정적 Source와 일치했다. 다음 후속은 기능을 유지하면서 selected 판정 한 건과 실제 own-selected Connect 반환 한 건을 독립적으로 기록한다. 원래 동작·소유권 guard·복구는 그대로 두고 이 질문에 불필요한 커널 trace는 NOT_REQUESTED로 명시하여 반복 UAC를 피한다.

근거: [실제 CP04 감사](../work/consolidated_diagnosis_20261007/cp04-evidence.md), [producer Source 감사](../work/consolidated_diagnosis_20261007/cp04-forward-audit.md), [두 anchor 대조](../work/local_native_login_forward_actual_review/eligibility-source.json). 아래는2026-10-06 통합 진단 이력이며 당시 TCP0 상태와 현재의 초기 통신 회복을 구분한다.

## 2026-10-06 통합 진단

2026-10-06. 사용자 요청에 따라 기존 시험·코드·제품 연결을 다시 감사했다. 이 문서는 가장 최근 실제 증거와 미완성 제품 기능을 구분한다. 현재 캐릭터 선택·맵 진입은 미완료다. 다른 기록의 Source/mock/복구 성공을 게임 진입 성공으로 읽지 않는다.

## 현재 결론

한 개의 확인된 게임 내부 버그가 남은 상황이 아니다. **최근 시험은 추가 프로세스를 관리 가능한 소유 프로세스로 확인하지 못해 도구가 중단했고, 자체 DLL에는 원래 초기 동작을 막을 수 있는 추가 선행조건이 있으며, 로그인 이후 응답과 캐릭터·맵 연결도 아직 완성되지 않았다.** 이 세 문제를 분리해 해결해야 한다.

| 문제 | 확정된 사실 | 아직 확정할 수 없는 것 |
|---|---|---|
| 최근 시험 중단 | 추가 LC가 snapshot에 나타났으나 뒤의 Job 조회에서 확인되지 않아 원래 guard가 시험을 중단했다. 최신 후보는 TCP 접속0/0263 소비0이다. | 추가 LC의 실제 신원·수명·생성 코드·Job 상태, guard가 없었다면 게임이 진행했을지 |
| 초기 원래 호출 전달 | 최초 native 후보부터 현재 CP03까지 공통 bridge의 RequireBound가 원래 ctor/task/connect/sender/close 앞에서 파일·crypto·고정 base·own DTO anchor 검증을 요구하고 실패하면 새 예외를 던진다. | 실제 시험에서 해당 bridge에 도달했는지, 어느 검증이 실패했는지, 이것이 접속0의 원인인지 |
| 실제 로그인 응답 | active 서버 hook은 유효 own0263를 소비해도 빈 응답을 반환한다. ACK/roster 확장은 별도 Source이며 운용 계약이 UNBOUND다. | 정상 결과값 및 정확한 목록 전달 순서의 운용 바인딩 |
| 실제 캐릭터·맵 | 운영 roster가 비어 있고, 선택 이후 응답·SelfInfo/Map/Actor 연결이 완성되지 않았다. | 실제 CharacterSelect/Land 전환과 자체 캐릭터·맵의 정상 소비 |

## 오래 걸린 원인

1. 실행 도구·설치·복구·관찰 장치의 수정과 제품 기능 연결을 같은 진전처럼 다뤘다. 현재의 많은 Source·fixture는 실제 게임 경로의 성공을 보장하지 않는다.
2. 현재 실행된다는 증거가 없는 생성 CALL에 관찰기를 붙이는 작업이 반복됐다. DLL 열거와 현재 매핑의 marker0까지 확인했지만 실제 생성 코드는 찾지 못했다.
3. 초기 일반 동작의 원래 함수 전달에 자체 기능 검증을 결합했다. 이 결합은 원본보다 강한 실패 조건을 추가하며 정상 동작 보존이라는 설계 의도와 충돌한다.
4. 시작 문제 뒤에 남은 무응답 서버·빈 roster·맵 연결을 사용자가 체감할 완료 기준과 분리해 충분히 설명하지 못했다.

## 비교 실험의 중요한 제한

- 과거 H는 초기 VERSION/COUNTS를 재현했고 한 시험에서 typed Lobby 상태를 관측했다. 후속 선택 연결의 KEY 이후 첫 C2S는 해결되지 않았다.
- 과거 첫 accept는 observer clock 약11.5~12.8초, 최신 guard 중단은 약11.8~13.0초다. native 전체 수명18~22초를 동일 원점의 유효 관찰 시간으로 비교할 수 없다. 접속0은 실제 관측값이지만 native 코드 회귀라는 인과는 미확정이다.
- raw H는 나중에 Win225로 읽기가 거절됐다. 보존 정책상 재읽기·격리 복구·AV 제외·같은 payload의 새 이름 재생성은 하지 않는다. 현재 H 재실행 A/B를 가능한 다음 단계로 제안하지 않는다.
- H의14000은 Windows 제외 포트 범위로 bind가 실패한 이력이 있다. 현재12000/14030 서버 준비와 이를 혼동하지 않는다. 시스템 예약 변경으로 대조군을 만들지 않는다.

## 수정과 실제 검증의 순서

1. **원래 동작 전달과 자체 기능 준비를 분리한다.** 실제 원래 target의 검증된 binding 없이 RequireBound만 지우지 않는다. preferred0x140000000을 actual base로 대체하지 않는다. 원래 target 검증과 own DTO/UUID/phase 준비를 나누고, own 미준비 때문에 원래 호출을 생략·재시도·새 예외로 대체하지 않는다. vft가 최초 진입일 가능성을 direct CALL의 순서 가정으로 덮지 않는다.
2. **다음 실제 시험의 질문을 먼저 고정한다.** 현재 허용된 후보에서 최초 producer bridge의 도달·binding 결과와 추가 프로세스의 실제 생성 경계를 분리해서 판정한다. 어느 결과든 다음 수정 대상을 줄여야 한다. 경로를 모르는 상태의 새 CALL hook 추가와 같은 0값 재시험을 반복하지 않는다. OS 이벤트의 PID/이미지/시각은 프로세스 분류이고 코드 귀속은 실제 스택·당시 매핑이 확인된 범위만 인정한다.
3. **한 실제 자체 로그인 요청을 서버까지 연결한다.** 동일 selected 연결에서 원래 VERSION/COUNTS와 native0263가 전송되고 같은 등록 writer가 자체 UUID를 소비하는지 확인한다. DLL load나 sender 반환으로 이를 대신하지 않는다.
4. **기존 응답 확장과 자체 캐릭터를 active runtime에 연결한다.** Source로 확인된 ACK 타입·필드와 검증된 결과/순서를 사용한다. 서버 push 방식이 근거로 확인되면 존재 여부가 미확정인 client 목록 요청을 불필요한 선행조건으로 만들지 않는다. empty roster 진입과 실제 선택 가능한 한 캐릭터의 진입을 구분한다.
5. **선택 이후 맵까지 연결한다.** 선택 ACK와 필요한 SelfInfo/Map/Actor 응답, 실제 전송 validator와 클라이언트 소비를 연결한다. PURPLE·온라인 원본의 선행 실행 없이 같은 자체 캐릭터·맵으로 들어간 실제 결과가 최종 완료다.

## 진행 중인 독립 확인

- [관측 시간·중단 원인 감사](../work/consolidated_diagnosis_20261006/evidence-audit.md)
- [native 변경과 원래 함수 전달 감사](../work/consolidated_diagnosis_20261006/native-diff-audit.md)
- [로그인·캐릭터·맵 제품 공백 감사](../work/consolidated_diagnosis_20261006/product-gap-audit.md)
- [original-forward 분리 구현 brief](../work/local_native_login_original_forward_plan/forward-plan.md)
- [기존 원래 코드에서 확인한 두 vft 계약](../work/consolidated_diagnosis_20261006/vft-existing-source.md)
- [웹 GPT에 전달한 검토 요청](../work/consolidated_diagnosis_20261006/web-gpt-request.md)
- [웹 GPT 검토 채팅](https://chatgpt.com/c/6ac4fd0c-1870-83ee-b51b-eb3e36dce573)
- [수집한 웹 GPT 답변](../work/consolidated_diagnosis_20261006/web-gpt/response.txt)

웹 검토는 기존 전용 자동화 Chrome 스크립트로 Pro에 한 번 제출했고, 생성 종료·응답1개(약11,613자)를 확인하여 전체 답변을 수집·대조했다. raw H 재실행 없이 확인된 forwarding 계약 위반을 수정할 정당성, guard 중도 검열, 서버 제품 공백의 구분을 채택했다. 특히 original binding이 보장되지 않은 hook을 활성화한 뒤 새 gate 안에서 실패하는 구조를 반복하지 않는다. 전체 파일 해시·원래 target 식별과 own DTO 자격을 같은 optional 검사로 취급하지 않는다.

추가 기존 Source 대조로 task의 `this+0→1198DC8+10→26F7E0`, Socket close의 `this+0→1198D90+20→241990` 및 해당 dispatch의 no-adjustor 계약을 찾았다. 앞선 vft note의 UNKNOWN은 읽은 범위의 한계였으며 이 근거로 보완한다. actual runtime base와 새 binder의 실행 검증이 끝났다는 뜻은 아니다.

구현 담당 채팅에 위 forward 분리 한 계열의 구현·compiled 검증·새 후보 한 번의 실제 시험과 원상복구를 진행하도록 전달했다. 웹 교차검토 대기를 해제했으며, 아직 새 후보의 실제 성공은 보고되지 않았다. 이번 startup 시험은 기존 소비 검증용 서버 정책을 유지해 응답 정책 변경을 동시에 섞지 않는다. 별도 서버 연결 준비에서는 ACK WireLimits의 본문16/필드기본65524 충돌을 찾아 후속에서 필드한도16으로 수정했고, encoded0263→같은 writer→0264/NUM/INFO→선택 등9개 stream 검증이 통과했다. 그 검증은 명시적 synthetic 의미값을 쓴 것이므로 실제 ACK 의미·CharacterSelect 성공 증거가 아니다.
