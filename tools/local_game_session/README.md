# 실제 요청 기반 자체 세션 hook

`connection.py`의 `OwnedGameAdapter`는 listener/게임을 실행하지 않는다. 실제 prepared broker의 `serve_both`에서 adapter를 한번 만들고, `run_connection`의 기존 `base.bootstrap_connection(...)` 호출 한 곳을 아래 callable로 교체한다. 원래 `run_conversation(pool, connection_id, operation)`와 EOF/취소/pool cleanup을 그대로 사용한다. frozen 파일은 수정하지 않고 Root가 운영 wrapper에 이 호출을 연결한다.

```python
game = OwnedGameAdapter(config, source_guard=ctx.verify_sources)
serve_connection = game.bootstrap_connection(base)
# tools/local_ready_entry_prepared/broker.py:40의 operation 생성에 사용
operation = serve_connection(reader, writer, port, trace, decoder_factory,
    conversation_factory, ctx.verify_sources, parent.adapter.wipe,
    scope, first, owner_guard, policy)
```

기존 KEY→VERSION→COUNTS 처리 후 세 번째 이상 실제 decoded request는 원래 current owner가 literal True인 경우만 Source guard 뒤 자동 local-register→game dispatch로 들어간다. vendor 인증/SDK 성공을 주장하지 않는다. 등록은 실제 writer 객체에 묶인다. 기존 owner_admission metadata, write/drain·wire wipe·EOF·current-owner refusal을 유지한다.

4E28은 실제 protobuf request의 reference/i32/i32를 검사해 이미 전달된 owned roster에 있는 캐릭터만 자체 realm `Registry.selected`에 저장한다. 이 두 i32를 좌표로 이름 붙이지 않는다. ACK3·026B·월드는 보내지 않는다. unknown/malformed/unregistered/foreign/replayed request는 거절한다. `opened()`는 무응답이며 roster push가 없다.

두 LIST request opcode는 아직 Source null이라 wire dispatcher에 등록되지 않는다. Source가 확정되면 기존 typed `GameSession.list_request(source_kind=..., payload=...)`가 완전 explicit NUM→INFO encoder를 실제 요청에서 반환한다. 현재 이 hook을 임의 opcode에 붙이면 안 된다. list-request binding·nonempty21개 INFO 입력·ACK/world 필수 값과 실제 순서가 현재 제품 blocker다. 테스트3개는 synthetic stream/model뿐이며 게임 진입 증거가 아니다.

실제 LC 게임 시험과 운영 broker 통합은 수행하지 않았다. 캐릭터 목록 표시·선택의 실제 게임 반영·월드/맵 접속은 미완료다.
