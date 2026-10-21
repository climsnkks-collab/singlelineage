# ITEM Drop→Get 연결 방향 상담 (2026-10-21)

이 자료는 사용자가 보유한 원본 기반 클라이언트와 자신이 만든 로컬 서버를 연결하는 ITEM 기능의 **자체 Python 조율 코드** 검토용이다. 원본 바이너리/ASM/메모리 주소·오프셋/저장 데이터/실행 로그/인증정보는 공개하지 않는다. 아래 실행 결과는 익명화한 필요한 요약이며 자체 코드의 성공과 원본 소비 성공을 구별한다. 보호기능 우회나 수명 검증 생략은 대상이 아니다.

## 목표와 확인된 경계

사용자의 원 Drop(수량1) 호출→실제 Drop 요청 수신→서버 durable Ground 소유/응답2개→client 인벤토리 A만 남음→현재 typed Ground 원 Get→서버 Player 복원→client A+B 복원→Ground lookup 퇴역까지 같은 원본 호출/현재 owner/정상 수명으로 이어야 한다. 현재 원 Drop 호출의 정상RET·실제 Drop RX·서버 GROUND rev2 및 Remove+Spawn TX는 확인했다. Get/client 반영/Ground 퇴역은 미확인이다. 원본 client의 whole ctor·Action·resource·cleanup은 보존하며 임의 객체/필드/추가 인자/가짜 완료를 넣지 않는다.

## 같은 기능에서 막힌 경과

- R286: 실제 Drop RX/서버GROUND rev2/응답2개 뒤 UI DROP_BACKEND에서 원래10초 제한 만료. client/Get 미확인.
- 진단 보강 후 R288: 원 clock/마지막 context의 의미가 보였으나 DROP_ENTRY_WAIT 누적17.859초 만료. 마지막 READY context는 역사이고 최종 권위가 아니다.
- 별도 동기 monitor.tick을 정확 typed 활성 ITEM 범위에서 유예한 R291: DROP_BACKEND에서 누적10.391초 만료. primary는 약41.406초 뒤 자연 exit1; 종료 직전 같은 부모 새 child 생성. 정상 Quit 성공 아님.
- Runner의 매poll 동기 진단파일 fsync도 같은 typed 범위에서 유예한 R296: 여전히 DROP_BACKEND에서 누적10.594초 만료. primary 약41.542초 자연 exit1, 새 child 강제 정리, 정상 Quit false. native owner failure 기록은 null이다.

이 변경들이 같은 왕복 기능의 미확인을 해결하지 못했다. 진단과 첫 Entry 진행의 변화는 있었으나 실제 완결 기능은 진전이 없다. 같은 후보를 상담 기준 채우려고 재실행하지 않았다.

## 현재 접근·핵심 가정

자체 UI adapter의 `_original()`은 같은 consumer clock을 **한 번** 읽고 phase_started로부터 0<=age<10초를 검사한다. 이 10초는 현재 adapter의 기존 제한이며 게임 프로토콜 제한으로 주장하지 않는다. root 지시로 임의 연장/재설정하지 않는다. single-Q Drop 정상RET 뒤 DROP_BACKEND의 시작시각은 **Drop Entry의 원 시작시각을 그대로 보존**한다. DROP_CLIENT도 이를 이어받는다. 따라서 10.594초는 Entry부터 누적 age이지 두 poll 사이의 gap이나 한 handler의 실행시간이 아니다.

UI poll 맨앞 clock검사→fresh context 취득(row operation lock/current generation/current session)→phase branch 순서다. DROP_ENTRY_WAIT에서 정상RET 확인후 phase만 BACKEND로 바꾸고 poll을 반환한다. 그 poll의 context는 RET 수집 전의 READY였으므로 fresh DRAINED로 재사용하지 않는다. 다음 poll은 fresh context 전에 원 clock에서 만료될 수 있다.

Outer loop는 owned primary/job tick→broker health/current checks→await feature.poll→(활성ITEM이면 일반 monitor.tick 유예)→기존 control/stop/sleep다. feature.poll은 활성ITEM에 UI로 바로 진입한다. Runner의 중간 output-only JSON/fsync는 같은 범위에서 유예하고 terminal/error/cancel/final 저장은 유지한다. 필수 owner/current/source/row/typed query·Native의 정상 호출·원기한은 유지한다. 일반 diagnostic IO만을 원인으로 특정할 근거는 이제 없다. exact 동기/await 구간별 비용은 기존 증거로 분리되지 않았다.

같은 connection의 서버 source는 frame 단위 await game.received→await send가 끝난 다음 frame 수신을 처리한다. Drop handler는 durable commit→원 Remove+Spawn 2wire send/drain→Ground membership DRAINED/sessionDROPPED/pendingNone→정상RET한다. R296 ring에는 Drop응답2개 뒤 **다른 client RX 2개와 ACK TX**, 같은 원 SourceQuit call/RET도 있다. 따라서 동일 connection/source라는 조건 아래 Drop handler의 **역사적 정상RET**와 양립한다. 이것은 UI 실패 당시 current context/actual client Drop 소비 성공 증거는 아니다. 'Spawn 직후 즉시 모든 client 처리 중단'이나 'packet이 exit1을 일으켰다'고 확정할 수도 없다.

실패 시 마지막 cached context는 READY/PLAYERrev1/pendingfalse/send_index0(DROP_ENTRY_WAIT)이며 마지막 clock은 DROP_BACKEND/POLL_ENTRY/context_originNone이다. fresh row context 접근 전에 실패한 사실만 말한다. cached READY를 현재 상태로 해석하지 않는다.

## 재사용한 원 소비 근거와 미확인

별도 원본 분석은 Remove가 UID행 전체삭제(수량필드없음), Spawn 필수필드/좌표 전개와 현 local profile의 구조에 충돌이 없음을 확인했다. fresh 별도 Action의 sentinel/첫 appearance 갱신/빈 record일 때 f4를 소비하지 않는 경로도 정적으로 닫혔다. 이 결과는 실제 TX field/현재 Action/loaded record/게시/픽셀 성공을 증명하지 않는다. 원본 응답을 추측 수정하거나 Action flag를 강제할 근거는 없다. 실제 primary exit1/child producer는 별도 담당이 기존 로그/원 수명 경계를 조사 중이며 이를 새 primary로 채택하지 않는다.

## 요청

이 기능의 현재 접근을 계속하는 것이 맞는지 평가해 달라. 특히 (1) 같은 Entry 제한을 보존한 phase 기반 polling과 현재 owner/current contract 사이의 잘못된 가정이나 구조, (2) deadline 관측과 exit1을 구분하는 우선순위, (3) 기존 자료만으로 다음에 고칠 **가장 작은 실제 연결**의 순위를 제시해 달라.

후보 방향으로 정상 Entry RET 뒤 동일 operation에서 fresh row context를 재취득해 이미 DRAINED이면 원 client observer/Get continuation까지 이어주는 방식이 현재 강한 수명/current/clock을 지키면서 의미가 있는가? 이것이 유효한 돌파인지, 아직 필요한 caller/dependency가 무엇인지 판단해 달라. 단순 시간 연장, cached 상태 승인, 가짜 ACK/receipt, 새 child primary 채택, guard/보호 완화, 외부 sender, 새 대형 collector/분석기·반복 기동은 제외한다.

다음 최소 구현·검증에서 성공/반증/UNKNOWN을 구별할 조건을 명확히 제안해 달라. 함수 하나/메모리 읽기만의 진단으로 축소하거나 프로젝트 전체 노선/다른 기능/장기계획으로 확대하지 말아 달라. 아래 발췌는 own control-flow 설명용이며 원본 실행 성공이나 완전한 재현 코드가 아니다.
