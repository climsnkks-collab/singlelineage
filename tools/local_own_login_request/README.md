`codec.LocalLoginRequest(socket_address_u32, 'standalone.local', guest_uuid, selected_tag=None)`는 Source-known0263 필드1 uint32/필드2·3 required string/필드4 optional string을 기존 protobuf encoder로 만든다. `socket_address_u32`는 실제27EE30 결과를 caller가 제공해야 하며 selected server ID나 기본값으로 대체하지 않는다. issuer/UUID/selected_tag는 독립 local contract이며 NC token/certificate가 아니다.

```python
# Root가 codec.py/route.py와 explicit local input을 Source closure에 승인·핀해야 한다.
# socket_address_u32는 실제27EE30 결과를 제공하는 caller가 아직 필요하다.
explicit_local_request = route.codec.LocalLoginRequest(
    actual_socket_address_u32, 'standalone.local', owned_guest_uuid, selected_tag)
owned_serve = hook.bind_serve_both(prepared, ctx, approved_config)
extension = route.attach(owned_serve, explicit_local_request)
await owned_serve(parent, resource, ctx, trace, stop, pins, owner_guard, pool)
```

원래 OwnedGameAdapter.grant가 session을 생성한 직후 extension.bind(session)을 호출한다. 기존 current-owner/Source 검사와 registry를 재사용하고 COUNTS 후 실제0263 요청만 한 번 소비하여 extension.receipts[own UUID]에 저장한다. 한 runtime에서 같은 own UUID는 새 writer/재접속에서도 재소비하지 않는다. receipt는 EOF 후 유지되며 writer 객체 ID를 쓰지 않는다. 기대한 own 값과 다르거나 replay/closed/wrong order면 거절한다. response는 없다.

**codec body 생성은 게임의 native request 송신이 아니다.** 실제 retained selectedNetwork에서 KEY/VERSION 준비 뒤 generated 객체·DDE430/DDDCA0 setters→27D620 호출을 잇는 producer는 아직 없다. Native SDK callback/flag를 흉내 내지 않는다.

실제27EE30 결과를 codec과 서버 expectation에 전달하는 연결도 아직 없다. 필드1과 own UUID 등은 caller가 명시적으로 제공해야 하며, 이번 순수 검사 값은 synthetic이다.

0263 이후0264 ACK의 필수값·consumer 계약은 미확정이고, character-list 요청 opcode도 미확정이다. 따라서 이 route가 캐릭터 목록을 열거나 로그인/캐릭터·맵 진입을 완료하지 않는다. frozen connection/hook은 수정하지 않았다.

이 새 Source closure는 fixed v6 actual runtime에 아직 포함되지 않았다. 위 예시는 Root의 후속 연결 위치이며 실제 설치·native 송신·게임 시험은 수행하지 않았다.
