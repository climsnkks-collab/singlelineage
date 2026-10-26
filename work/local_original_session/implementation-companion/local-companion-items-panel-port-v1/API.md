# 동료 설정 패널의 ITEM 읽기 포트 후보

현재 클릭 Host `5c561041…`와 계정 Core `86c0d7d1…`에 명시적으로 묶은 기존 ITEM `CompanionItemTargetView` 후손이다. 실제 패널 interface 구현은 제공하지 않는다. 제품 변경은 원 읽기 포트의 HOST_SHA256 한 literal뿐이다. 다른 Host/Core 후손으로 자동 적용하지 않는다.

기존 API를 그대로 사용한다:

```python
CompanionItemTargetView(host, provider, store, *,
    source, host_source, core_source, interface_source)
```

네 인수는 원 canonical_feature_bootstrap.SourceModule이며, 실제 붙은 Host/provider/BatchStore와 최종 interface 모듈이 필요하다. 원 생성자는 Broker 시작 전·등록된 원 companion issuer·한 계정 그래프를 요구한다. ATTACHING 중 설치나 실행 중 재부착을 허용하도록 guard를 바꾸지 않았다. 후속 scope에서 새 Host/provider/interface를 발급할 때는 이 cold 설치 계약의 별도 source 후손이 필요하다. old port.host나 provider를 치환하거나 constructor를 건너뛰지 않는다.

미래 실제 interface의 `async def open_items(self, *, panel, kind, character_lease, actor, owner)` 본문이 아래 동기 읽기를 **직접**, await 없이 호출해야 한다. Host.command가 원 row operation을 이미 소유한다. 이 예시는 계약 설명이며 생성된 interface나 실행 caller가 아니다.

```python
snapshot = self.item_target_view.read_companion_item_target_locked(
    panel=panel, kind=kind, character_lease=character_lease,
    actor=actor, owner=owner)
```

same panel/state/epoch와 실제 active.lease/actor/owner를 확인한 뒤 원 `provider.bind_companion(writer, active)` → `BatchStore.restore(binding)` → `provider.current(binding)`를 사용한다. 원 active/actor/direct generation/current frame과 row가 읽기 전후 동일해야 한다. 계정 root canonical member의 동료 UID만 반환하며, child inventory history는 읽지 않는다. binding은 반환/보관하지 않는다.

반환값은 frozen/slots `CompanionInventorySnapshot`: 동료/direct/account UID, actor UID와 generation 관측값, immutable inventory frame bytes, asset/member revision, member/account SHA다. snapshot은 해당 시점의 읽기 결과이며 현재 행동 권한이 아니다. `native_opened=False`, `action_admitted=False`, `equipment_state='UNKNOWN'`는 유지한다. 행 선택·Use/Equip/이동·저장은 이 포트의 API에 없다.

`kind='equipment'`는 원 `COMPANION_ITEM_TARGET_EQUIPMENT_STATE_UNSUPPLIED`로 거절한다. 실제 UID2 GearState와 해당 same-account GearStore/current/action 계약이 필요하다. 현재 account Core에는 reference GearStore가 canonical restore에 호출하는 `gear_current_locked`도 없다. 이 사실은 GEAR 구현 전체가 없다는 주장이 아니라, 정확히 이 두 source를 바로 결합할 수 없다는 뜻이다. GearStore의 same-profile adoption/참가자/current 검사와 ITEM effect의 selected profile/generation/CAS 검사는 그대로 둔다.

첫 실행 의존은 실제 final interface SourceModule 및 그 `open_items` 본문·패널 수명 소비자다. 기존 native LUI2 display는 이름/레벨/상태/support 표시만 인코딩하며 ITEM frame/장비/변경 request를 운반하지 않는다. 4F13 클릭 route나 LUI2 model 검증을 ITEM open/action 성공으로 간주하지 않는다. 새 opcode, selected UID/frame 교체, handler 직접 호출, Store 쓰기 우회는 없다.

실제 game RUN_COMMAND/packet caller는 null이고 test_ready/run_ready/ui_ready/action_ready 모두 false다. 소스 재확인은 `python -B work/local_original_session/implementation-companion/local-companion-items-panel-port-v1/verify_source.py`다.
