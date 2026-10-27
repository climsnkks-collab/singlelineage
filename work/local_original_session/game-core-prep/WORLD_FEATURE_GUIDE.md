# 월드 기능 추가: 새 모듈 + 등록 한 줄

`tools/local_original_session/world_feature_이름.py`를 만들고 `world_handlers.FEATURE_MODULES`에 `'world_feature_이름',` 한 줄을 추가한다. broker 수정은 필요 없다. 아래 동료 이름은 구조 예시이며 동결 기능의 재개 지시가 아니다.

```python
# world_feature_companion.py — 기능 구현 전의 등록 예시
async def _companion_on_enter(ctx, writer, row, game, operation_lock):
    position = ctx.realm.service(writer).snapshot()
    # 기존 소유권/월드 계약 안에서 기능을 구현한다.

METHODS = (_companion_on_enter,)
HOOKS = {'after_enter': ('_companion_on_enter',)}
```

함수명은 전체 기능에서 고유하게 쓴다. `METHODS`는 기존 broker 호출자와의 호환 API도 설치한다. 같은 이름을 뒤 등록하면 덮어쓰므로 기존 이름을 재사용하지 않는다. 등록/임포트는 시작 시 한 번이다.

`world_bridge.Context`의 API는 `ctx.world`, `ctx.realm`, `ctx.inventory_store`, 읽기/쓰기 가능한 `ctx.inventory_frame`, `ctx.selected_session(writer)`, `ctx.owner_current(writer, row, position)`, `await ctx.send(...)`다. 기존 동적 override·저장 세대·writer/잠금 객체를 그대로 연결한다. 상태/소유권은 실제 broker·world·writer를 기준으로 한다.

요청은 `FRAMES={확인된_opcode: ('함수명',)}`으로 등록한다. 서명은 `async def 함수(ctx, writer, row, game, frame, operation_lock) -> bool`이다. 등록 순서대로 호출하며 True면 소비 완료, False면 다음 처리기와 기존 경로를 계속한다. 소비·저장한 요청을 False로 넘기지 않는다. 기존 송신 목록에 없는 검증된 opcode만 `OUTGOING_OPCODES=(opcode,)`로 추가한다. opcode·필드값을 추측하지 않는다.

`HOOKS`의 함수도 `METHODS`에 넣는다. 첫 인수 `ctx` 뒤의 서명은 다음과 같다.

| hook | 나머지 인수 / 방식 |
| --- | --- |
| `initialize`, `runtime_started` | 없음 / 동기 |
| `runtime_stopped` | 없음 / 동기·async |
| `after_enter`, `after_move` | `writer, row, game, operation_lock` / 동기·async |
| `after_request` | `writer, row, game, opcode, operation_lock` / 동기·async |
| `after_kill` | `event` / 동기, world 잠금 안 |
| `after_death` | `uid` / 동기, world 잠금 안 |
| `after_leave` | `writer` / 기존 이탈·귀환 정리 뒤, 동기·async |

row 잠금과 world runtime 잠금은 다르다. 새 frame 처리에서 월드 변경은 기존 `runtime.dispatch_now`로 직렬화한다. `after_move`는 수락된 월드 이동의 runtime 잠금 안에서도 호출되므로 재진입하지 않는다. `after_enter`는 진입 프레임 전송 뒤다.

응답은 `await ctx._world_send(writer, row, frames, operation_lock)`로 기존 chunk/send를 재사용한다. 직접 `ctx.send`가 필요하면 같은 tuple을 `frames`와 `world_operation`에 주고 `game=True`, 동일한 잠긴 `operation_lock`을 전달한다. 직접 socket write로 우회하지 않는다. 기존 owner 확인·CAS·한 번 소비·저장 후 응답 순서, 정확한 drain 뒤 `mark_delivered`, FIRST/close와 자원 정리를 유지한다.

새 소스/정책 파일 판독·해시·등록은 startup에만 둔다. 요청 처리 중 판독 대기·새 guard·pin은 추가하지 않는다. 수정한 기존 pin 대상의 해시만 갱신하고 PS1의 UTF-8 BOM을 유지한다.

시험은 `$env:SL_TEST_PORT_BASE='22000'`으로 물리 22000/24030을 쓴다. 미설정은 12000/14030, 두 번째 포트는 base+2030이다. 논리 endpoint·Peer·claims와 제품 게임 포트는 그대로다. 두 설정의 독립 프로세스를 동시에 실행할 수 있으며 시험 실행 소유는 지정 worker가 조율한다.
