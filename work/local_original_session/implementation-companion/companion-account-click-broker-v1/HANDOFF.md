# COMPANION-MAGE account-v5 click Broker hooks v1

WRITER_RELEASED / private source_ready:true / run_ready:false / test_ready:false / runtime:UNRUN.

실제 account-v5 cohort의 Broker `934fb07af30efd5853fdd147f5dfda64fb5f16b730914e3757e89ec50963c46a` 위에 검토된 click-router-v2의 **두 additive hook만** 옮겼다. 원 account Broker가 그 reference의 정확 부모와 같아 최종 Python text는 reference a22a와 동일하다. source byte의 LF는 account 부모 형식을 유지했다. product/packet_peer.py8d71·packet_server.pyeed8는 실제 account 부모의 byte 사본이며 같은 새 디렉터리에 둔다.

## 변경과 보존

- `_TransportPolicy.received_frame`: 설치된 동일 nominal Feature일 때만 4F13을 받는다. 원 checkpoint/writer·boot/stage·pending drain·rate limit·received counter 경계를 유지하고 Feature.header_locked에 실제 row/current 검사를 위임한다. 미설치 None이면 기존 경로다.
- `LocalRealm.grant`: writer별 route closure가 실제 같은 `_companion_click_feature` identity를 재확인하고 기존 locked dispatch를 호출한다. 기존 terminal guard 전에 등록하며 원 settings/quit/current 실패 경로를 그대로 거친다.

그 외 전체 module AST는 원 account Broker와 같다. `_serve/_row_operation/_send/_accept/close`와 scope/CAS/connection·정상 completion은 변경하지 않았다. Peer.bind의 `_accept.co_filename == Peer.with_name('broker.py')` 조건을 원 코드 그대로 유지했다. 새 경로로 compile한 실제 `_accept` code object의 filename이 같은 product sibling Broker를 가리키는 것까지 확인했다. source compile은 실제 bind나 runtime PASS가 아니다.

## 첫 미공급 typed interface

Broker hook이 요구하는 nominal source는 `tools.local_original_session.companion_actor_click.Feature`다. 다음 account-compatible **실제 Feature 후손**이 필요하며 여기서는 Host/Feature/Allied를 수정하지 않았다.

1. 같은 실제 account Broker/realm/policy/attached Host에 연결된 단 하나의 instance를 cold before-start에 설치하고, policy/realm `_companion_click_feature`가 동일해야 한다.
2. 원 `header_locked(writer,policy_row,opcode,size)`와 `async dispatch_locked(writer,payload)` 계약을 유지한다. 원 f1 uint32 UID parser·명시 LOCAL strict field/size admission을 재사용하며 packet에서 generation/lease를 만들지 않는다.
3. actual final account Host/Allied source seal, root.current(record), 같은 writer/row/selection/real lease·UID/generation·publication DRAINED/no removal을 확인한 뒤 원 Host `_open_from_actor_click_locked`에 같은 record identity를 넘긴다. actual interface/panel lifetime가 없으면 거부한다. 이미 가진 원 row operation을 재획득하거나 fake helper로 대체하지 않는다.

기존 reference Feature는 **Host ed8666/pub4d1544**를 고정한다. actual account Host는219bfd이고 새 account-v5 Allied 후손은d1490b이므로 그대로 설치하면 source provenance가 맞지 않는다. 최종 Host가 다른 account descendant면 그 정확 source를 검토한 Feature가 필요하다. literal만 바꿔서 실제 compatible installation/owner lifetime가 완성됐다고 하지 않는다. 이 package는 Feature를 만들어 설치하거나 optional 슬롯을 강제로 채우지 않는다.

## protocol 의미

REA270의 원 Pet/Summoned 조건부 요청은4F13/f1 uint32 UID다. REA274는4F14/SC_SUMMON_STAT_ACK의 실제 static 형식·소비를 확인했고, REA277은 child 필수f1..6/선택f7..10과 Summon/Pet 분기를 보완했다. 그러나 같은 요청 actor와 실제 응답 업무값·menu callback·정상 다음 요청의 결속은 여전히 미공급이다. 새4F14/child/성공코드를 만들지 않았다. 원 Player가 이 요청을 native click으로 송신한다는 증거·UI 성공도 없다.

이 transport는 기존 명시 LOCAL settings adaptation에 한정한다. future Feature의 return()은 actual Host helper가 반환한 뒤의 LOCAL no-wire 동작이며 원 Pet 응답이나 Native 메뉴가 무응답이라는 주장이 아니다. 실제 실행은 정상 login/roster/root WORLD→genuine summon/실UID-current·drained registration 뒤 기존 공용 packet-client-v5로 source-backed f1을 보내야 한다. 이 package에는 정상 summon/Native interface/완성 caller·사본/RUN_COMMAND가 없으므로 발주 준비는 false다.

## 최소 확인

```powershell
python -B work/local_original_session/implementation-companion/companion-account-click-broker-v1/verify_source.py
```

8조건 PASS: 정확 source pins/구문, reference text 재사용, 두 메서드만 변경, 각 두 statement를 제거하면 전체 원 Broker AST 동일, actual compile filename/sibling 조건, Peer/Server 원 byte·같은 디렉터리, typed header 경계, 동일 Feature closure와 terminal wrapper 순서. reference의 이미 통과한 strict parser/current/route fixture는 재실행하지 않았다. import/생성자/bind/server/port/packet/Store/Native/REA 실행0이다.

정확 부모/새source/두hunk는 parents.json·manifest.json·broker.diff다. coherent final account+actor-only+Feature selection은 main의 별도 통합 대상이며 기존 loader/client/API/common/ITEM/Host/Factory/Allied/이전 private/Test copy·queue를 변경하지 않았다.
