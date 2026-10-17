# 소유 로컬 브로커의 지속 연결 정책 — 순수 fixture 준비

`policy.py`는 연결 수명·자원 예산·정리 순서만 결정한다. socket bind, 게임, 슬롯,
SourceReview, OneTrial, UAC, 온라인 작업과 실제 packet 송신은 없다. 기존 동결 runtime은
수정하지 않았다. 이 모듈은 production adapter 또는 실제 지속 플레이 증명이 아니다.

선택된 Root owner 객체·보유 process handle·Job 객체는 전체 수명 동안 literal identity로
묶인다. 각 읽기/dispatcher 진입/write/drain 완료와 100ms 유휴 checkpoint에서 정확한
loopback 전체 tuple과 PID/birth/image/Job/live handle을 확인한 최신 owner 표본을 요구한다.
표본은 accept 이후이며 현재 시각보다 미래가 아니고 250ms 이내여야 한다. 오래된 receipt,
PID, client supplied ID 또는 포트만으로 owner를 대신하지 않는다. `OwnerSample`의 bool은
합성 adapter 계약이며 native admission capability가 아니다. production은 실제 retained
native 검증을 실시하며 JSON/CLI로 이 값을 받아 gate를 열면 안 된다.

초기 KEY12는 기존 retained source/lease scope 아래 accept 즉시 쓰는 순서를 유지한다.
owner poll을 기다린 뒤 첫 KEY를 쓰면 timing이 바뀐다. Root가 같은 writer에서 실제
KEY12 write/drain을 확인한 뒤 `admit(..., key_already_drained=True)`로 정책을 연결한다.
나머지 bootstrap과 game write 전에 현재 owner를 확인한다. 정책의 opcode/size 검사는
기존 DTO/전체 wire/hash/shape/ACK→Map→Self→Actor 순서 검사를 대신하지 않는다.

첫 bootstrap은 VERSION→COUNTS 두 요청과 KEY→VERSION→COUNTS 세 write/drain을
보존한다. 첫 stream의 완전 EOF·decoder empty·positive writer close·Registry remove·
task join 뒤 같은 endpoint의 두 번째 stream만 허용한다. 대기 writer queue는 만들지
않고 겹친 accept는 즉시 거절/정리한다. 현재 source-supported 흐름은 endpoint당 두
stream뿐이다. 세 번째 connection, tuple 재사용, game stream reconnect/resume은
`APPLICATION_RECONNECT_UNBOUND`로 거절하며 새 launcher/자동 재실행으로 숨기지 않는다.
초기 EOF는 listener를 닫거나 realm 선택 상태를 삭제하지 않는다.

두 번째 stream에서 bootstrap이 완료되면 전체 시간·수신 byte·frame 횟수·빈 연결 idle
한도가 없다. 현재 owner가 살아 있고 source가 유효한 유휴 상태는 계속 유지한다. 총량을
늘리는 대신 아래 동시에 보유할 자원과 시간 구간별 처리량을 제한한다.

| 범위 | 순수 정책의 제한 |
|---|---|
| Endpoint/stream | 127.0.0.1:12000/14030; endpoint별2 lifetime row, live1; writer literal identity |
| C2S codec | `present_disabled`만; wire10..65535B, read4096B, decoder≤69631B, read당 decoded≤410 |
| 처리율 | 방향별 byte bucket burst131070B/refill65536B/s, frame bucket burst128/refill64/s |
| Write | frame6..65535B; 동시 write/drain1; transport queued+next≤131070B; drain 뒤≤65535B |
| 유휴 | 100ms scheduler checkpoint; positive owner/process/session exit까지 지속, heartbeat 송신 없음 |
| 진행 | bootstrap15s; 한 incomplete frame10s 절대 deadline, byte trickle로 연장하지 않음; drain2s/close2s |
| 메모리/진단 | payload 소유0; connection row≤4; 고정 metadata ring256행; aggregate u64 saturation |

위 처리율·partial deadline은 **제안된 제품 자원 정책**이다. 정상 클라이언트의 최고 처리율,
느린 완전 frame 도착 시간 또는 live 지속 호환성을 입증한 값이 아니다. 작은 default로
단순 timeout을 연장한 것만으로 제품이 완성됐다고 표시하지 않는다. 한 frame이 완성되고
다음 incomplete frame이 남으면 decoder의 실제 completed count로 새 deadline을 시작한다.
모든 완성 frame은 source decoder/dispatcher에서 schema/order/replay를 별도로 검사한다.
8,000회 fixture는 opcode 인식·예산 확인용이며 READ_NEWS 반복이 정상 게임 traffic이라는
뜻이 아니다. 원래 handler는 해당 재전송을 거절해야 한다.

Unknown opcode는 C2S/S2C 모두 거절한다. 확인된 추가 C2S는 own login0263, READ_NEWS0267,
create4E24, select4E28이다. S2C 목록에는 원래 ACK/NUM4E21/INFO4E22와 검증된 world
frame만 있다. heartbeat/ping, 이동, 전투 opcode·reply를 추측하거나 unknown frame을
성공으로 삼키지 않는다. 실제 사용자 입력 기능은 이 route 집합으로 완성되지 않는다.

Owner가 unknown이면 Root는 `stop('owner_unknown')`, source 변경이면 source_refused,
IO/partial/drain/unknown opcode 실패이면 `fail(writer)` 또는 broker_failed를 즉시 호출한다.
메서드의 Refused 예외를 무시하고 다시 진행하면 계약 위반이다. Positive process exit는
같은 retained handle의 실제 wait signaled 결과를 Root가 검증한 뒤에만 사용한다. 명시
session 종료/cancel도 새 accept와 read/dispatch/write를 막지만 process exit 성공으로
승격하지 않는다. Root cleanup은 취소에 보호된 같은 event loop에서 task를 join하며,
writer2s close 실패는 cleanup UNKNOWN으로 남기고 재연결/새 실행/slot restore를 막는다.
이 모듈은 process 종료, owned Job empty 또는 CONTROL restore를 직접 확인하지 않는다.

정리 순서는 accept 정지→read/dispatch 취소→literal Registry writer와 owner-map 제거→
decoder/reply wipe→writer close/positive wait→connection task join→listener/reservation
close다. `release()`는 같은 socket 객체·모든 writer의 positive cleanup을 요구한 뒤
참조를 해제한다. 실제 Root는 preflight에서 **두 port 모두 SO_EXCLUSIVEADDRUSE로
예약**하고 같은 socket을 `start_server(sock=...)`에 넘긴다. 둘째 예약 실패 시 첫 예약도
닫고, 조회 후 재bind하거나 foreign listener를 종료하지 않는다. 정책의 socket 객체는
합성 identity 모델이라 실제 bind, closed socket, exclusive flag를 입증하지 않는다.

Ring log에는 고정 event/port/opcode/size만 남고 body/참조/소유 identity는 없다. production
파일 log는 old `Trace.emit`에 매 packet을 계속 보내면 안 된다. bounded aggregate와
현재 ring만 별도 고정크기 종료 보고로 CREATE_NEW 저장하거나, source-reviewed disk quota
writer를 연결해야 한다. 파일 log가 가득 찼다고 소유 보호 검사를 중단하면 안 된다.

## 읽은 정확 source와 통합 차단점

`source-basis.json`은 읽은18파일의 SHA와51 text anchor를 고정한다. 완전 executable
closure/SourceReview가 아니다. CP74/75는 port compiler로14000을14030으로 바꾸고,
ACK overlay로 base game idle15s를45s로 바꾼다. 따라서 현재45s도120s 전체 deadline,
65536B/16frame, 다른 observer/listener 한도와 함께 단회 시험의 일부다.

| 기존 경계 | 별도 successor에서 필요한 실제 통합 |
|---|---|
| `local_game_session/connection.py` | 120s/65536B/16frame/132sent 총량 제거 대신 순수 정책+actual current owner+per-frame validator 연결; persistent one loop |
| `local_ready_entry_prepared/broker.py` | listener `sleep(300)`/300s wait를 exact owner exit 또는 명시 stop으로 교체; 동일 예약 socket 연결; cancellation-safe close/join |
| `local_ready_entry_trial/peer.py` | current250ms owner 검증 유지; accepted16/ID≤16/receipt64 cap을 bounded current state·ring aggregate로 교체 |
| deps native peer `Registry.snapshot()` | 조회640 cap과 누적 timeline을 bounded latest/ring으로 교체. 기존5Hz poll의640회는 약128s이며 actual 종료 시점 예측은 아님 |
| broker `Trace` |512event/1MiB와 누적 owner_admissions를 bounded ring/counters로 바꾸고 lifetime 받은 bytes≤65536 metadata 제약도 분리 |
| game `Registry`/owner maps | exact writer resolve/register/close 유지; release 때 owner map도 제거; selected는 explicit 로컬 character 수 안에서 보존하며 durable save는 별도 |
| session/heartbeat | 현재 artifact에 game network heartbeat ID/schema/간격/응답/caller 연결 없음. resource `itemHeartbeatInterval` 문자열·ETW owner heartbeat는 그 규약이 아님 |
| game reconnect | bootstrap2-stream 외 selected world socket의 reconnect/resume/replay/reset 규약 없음; 자동 재시도 없음 |

CP75 metadata는 Actor 뒤 새 C2S frame을 기록하지 않고 `io_failed_or_timeout`으로 닫힌다.
이는 관찰 창의 한 표본이며 정상 온라인 클라이언트가 heartbeat를 보내지 않는다는 증거가
아니다. 기존 정상 접속/소스 계약을 읽은 범위에서 game heartbeat contract는 찾지 못했다.
이를 UNKNOWN으로 유지한다. 새로운 온라인 접속이나 게임 실행은 하지 않았다.

Root 통합은 frozen source를 바꾸지 않는 fresh successor와 실제 owner/Registry/writer/
native poll/예약 socket closure를 필요로 한다. 이 policy를 기존 handler에 monkeypatch
하거나 timeout 상수만 제거해서 실행하지 않는다. source/제품/slot/recovery gate와
정확 DTO guards를 결합한 뒤 live 지속·취소·positive 종료·저장/재기동을 검증해야 한다.

```powershell
python -B tools/local_persistent_broker_policy/tests.py
python -B tools/local_persistent_broker_policy/verify_basis.py
```
