# 동료 selected-owner BUFF bridge v1 — source 구현 완료 / 패킷 미준비

2026-10-23 root의 후속 직접 배정으로 **원 target BUFF preparation을 caster 단일 receipt에 결속하는 실제 제품 후손 두 개를 완성**했다. WRITER_RELEASED / `test_ready:false`. 아래 「최초 read-only 확인 이력」의 구현 전 문구는 현재 상태가 아니다.

| 제품 후손 | 정확 v5 부모 → 새 SHA 앞부분 | 실제 변경 |
|---|---|---|
| `candidate/companion_response.py` | `4c706a6b…` → `54bff5c66c68…` | 기존 default source에 selected-owner BUFF 분기·retained participant bridge 추가. |
| `candidate/companion_shared.py` | `6dc38143…` → `96c3d080257e…` | 원 `_send` 뒤 final receipt를 먼저 확인하고 BUFF 때 원 `refresh_selected_stats(owner,target.writer,'skills')` 호출. |

전체 pin·부모·범위는 **`manifest.json`**, 변경분은 **`v5-to-selected-owner-buff.patch`**다. root는 actor/UI/SKU 작업과 합칠 때 이 필요한 hunk만 사용하고 source pin을 명시한다. 공용 파일·selector/issuer/bootstrap·큐·ACTIVE·REA·포트·게임·저장 변경은 없다.

## 구현한 실제 경로

1. 원 scheduler→SharedSupport→actual393 issuer의 **전체 ordered remove/add/refresh** views를 사용한다. 진짜 selected owner만 허용하며 nonselected 동료 자신, 별도 actor 응답이 필요한 Light, 미소비 semantic effect·원 다섯 reply 한계 초과는 commit 전에 거절한다.
2. 설치된 `broker._buff_lifecycle.adapter`의 원 `SourceResponseAdapter`·`OptionalCodec`를 재사용한다. 실제 target binding으로 원 `prepare_exact`→`base.prepare_locked/frame_locked`를 호출하고 원 `PreparedBuff`·실제 target Resource Operation을 보관한다. Notification/UID/시간/instance/native 응답을 새로 만들지 않는다.
3. status frame0 뒤 semantic index1…N→wire index1…N을 유지한다. 기존 SharedSupport 한 commit과 **caster 단일 BatchStore receipt**만 사용한다. `OptionalScopedService.bind_committed`를 target으로 호출하거나 target generic recover·두 번째 receipt/writer를 만들지 않는다.
4. 원 CompanionCostDelivery의 source callback에서 target projection/_HPLineage·준비 객체·source graph·frame/phase를 검증한다. pending은 원 constrained delivery capability와 adapter.current의 메모리 검증만 사용하며 generic current/recover/participant로 재진입하지 않는다.
5. 원 broker reserve/write/drain에서 BUFF별 policy row·pending opcode/size·sent counter·drain timestamp를 유지하고 실제 drain callback·queue0/sent+1 뒤에만 part를 DRAINED로 바꾼다. 마지막 BUFF 전 status 단독 drain은 전체 성공이 아니다. 실패는 원 UNKNOWN/UNATTEMPTED를 유지한다.
6. 동일 parent의 DONE/TERMINAL 정리가 part의 preparation/view/target/source/policy 참조를 해제한다. 원 parent finally가 schema seal·delivery capability·owner를 해제한다. 전체 receipt DRAINED 후에만 원 selected skills refresh를 호출한다.

## 최소 변경 검사

**`validation-result.json`: PASS_SOURCE_BOUNDARIES / 4검사.** 원 add·refresh/실제 target binding/한 caster receipt·비용·pending drain·마감 및 selected skills refresh 호출, issued remove→add semantic/wire 순서, status 이후 BUFF drain 실패의 UNKNOWN/한 번 비용/정리, 위조 index·self target·설치 source 부재의 precommit 무변경 거절을 확인했다. 기존 v2/v5 setup만 재사용했고 예전 suite는 실행하지 않았다. 이 bounded 단위에서 검사를 더 늘리지 않고 마감한다.

검사에는 actual v5 BatchStore/schema/ResourceOwner/SharedSupport/parent와 원 SourceResponseAdapter/OptionalCodec/PreparedBuff 코드가 들어간다. persistence·roster/process·full-status encoder·broker transport는 명시 대역이고 `(2,31)` exclusive group은 검사 전용이다. 실제 socket writer.drain/패킷/native/Factory/wholeload/프로필/사용자 저장 실행은0이며 기능 성공으로 확대하지 않는다. 초기 spell7→Shield2 fixture 누락과 AST loader의 future flag 불일치는 fixture만 고쳤고 제품 guard는 낮추지 않았다.

Source 경계 재현: `python work/local_original_session/implementation-companion/optional-target-v1/test_selected_buff_bridge.py`. **이 명령은 기능 패킷 RUN_COMMAND가 아니다.**

## 현재 시험 준비와 다음 입력

**`test_ready:false`.** 최신 AGENTS와 `docs/INTEGRATION_QUEUE_USAGE.md` 기준을 승계한다. 정확 source SKU/root 검토·정당 actor/current generation·실제 학습/소유/지원 허용 입력과 전체 저장 사본·기존 공용 packet-client-v5/API를 재사용한 기능 caller/RUN_COMMAND가 아직 함께 준비되지 않았다. 실제 UID/준비 상태/실행 명령을 위조하지 않는다. 후속 기능 담당은 이 source/4검사를 재사용하고 실제 입력·caller를 이어 준비한다. 완료 source만 공식 단일 JSON 큐 등록 대상이며 이 worker의 큐 등록은0이다. 다른 ready 시험의 gate로 삼지 않는다.

동료 자신 target native restore/tick/remove와 Light 별도 actor response는 계속 OPEN/명시 거절이다. 사용자 요구 **동료 actor를 테이밍 펫/서먼 몬스터처럼 클릭해 설정 UI 진입**은 별도 actor/UI 담당 계약이며 이번 파일과 겹치지 않는다.

## 최초 read-only 확인 이력 — 아래는 bridge 구현 전 판정

2026-10-23. root의 현재 직접 배정으로 동료 HELD를 해제한 독립 source 계약 확인이다. 과거 v5 artifact의 HELD 기록은 수정하지 않았다. 쓰기는 이 폴더에만 했으며 제품 후손 수정·공용 pin/큐/ACTIVE·REA·포트·게임·패킷·저장 변경은 없다. WRITER_RELEASED. `test_ready: false`.

## 완료한 단위

v5가 404로 받지 못했던 `optional_enum.py`의 **로컬 실제 바이트를 읽고 SHA256 `9d3cc09e3d147161d713de7c8320611700045a5ff6969ed4f80298b7f3681a72` 일치**를 확인했다. 로컬 확인은 과거 GitHub 연결 앱의 404를 성공으로 바꾸지 않는다.

그 파일의 실제 고정 의존 retirement `ebdef8c7…` → delivery `3b27b793…` → owned wire `0e9d1d32…`를 이어 읽었다. 공개 문맥의 정확 ref `0b3fe817fa7aff36c0356f6e05e33a6958cecc7b:docs/companion_context_20261022/skill382/source_response.py`도 로컬 Git object에서 원바이트로 추출했다. SHA `d2a9fbdfa1991e64230bb522ba5aea53a5c99cd0482509fee39fbfd69d6913fc`가 기존 local `buff-multi-self-v1/source_response.py`와 같다. 이름만 비슷한 `buff-factory-join-v1/cohort/buff_source_response.py` SHA `004033ed…`는 다른 source이므로 이 정확 caller의 대체 부모로 쓰지 않았다.

`source-input/`에 원 relative path로 보존한 10파일은 열람 입력이다. 실행 cohort나 자동선정 source가 아니다. 모든 정확 부모·SHA·bytes·출처는 `source-contract.json`에 있다. 제품 변경분은 0이다.

## 원 source에서 확인한 연결과 실패 경계

| 단계 | 실제 계약 | 결론 |
|---|---|---|
| v5 `SkillDocument.support_event_plans` / `source_event` | 발급한 전체 ordered `SupportEventPlan` 자체와 같은 target binding·request·Rule·plan을 요구한다. | selected-owner target은 **진짜 target binding**으로 source event를 소비할 수 있다. caster binding 치환은 거절된다. |
| `SourceResponseAdapter.prepare_exact` → `base.prepare_locked` | 원 Notification(action/Info)는 spell·instance·time만 담는다. `PreparedBuff`는 actual selection/provider/operation_binding을 보관한다. | 진짜 selected owner에게 준비하는 접점은 source 수준에서 재사용 가능하다. 실행 preflight를 통과했다고 주장하지 않는다. |
| `buff_wire._current_owned` | `op.uid == selection.uid`, 같은 writer/lock/generation과 실제 acquired scope를 요구한다. | nonselected 동료 자신 target은 이 경계에서 불가하다. UID·selection을 바꾸거나 Notification target field를 추가하지 않는다. |
| `OptionalScopedService` | 실제 `retirement.ParentLifetime`만 등록하며 BUFF consumer 하나를 해당 parent lifetime에 연결한다. | v5 `CompanionCostDelivery`는 이 base가 아니며 current/attach bridge도 없다. 단순 service 구성은 불가하다. |
| delivery `Service.bind_committed` | `preflight.binding`으로 `store.recover(binding, txid, request)`하고 원 participant Operation을 parent에 attach한다. | selected target preflight라도 receipt의 primary는 **동료 caster UID**다. target UID와 다르면 canonical `BATCH_RECOVERY_RECEIPT_MISMATCH` 계약을 만족하지 못한다. |
| actual2fd `BatchStore.recover` + v5 후손 patch | 원 recover의 `tx['uid'] == binding.uid`를 유지한다. v5 `recover_participant`는 quiescent·이미 DRAINED된 selected RESOURCE 복구만 허용한다. | pre-send COMMITTED/UNATTEMPTED target attachment에 `recover_participant`를 재사용할 수 없다. |
| 원 `CostDelivery.current_active/attach_active` | 모든 BUFF participant binding이 primary `self.binding`과 같아야 한다. pending은 원 delivery capability를 쓴다. | 기존 self-cast parent에 target UID만 바꾸는 방식도 불가하다. |

위 실패 코드는 소스의 필수 검사에서 도출한 계약이다. 실제 서버를 실행해 관측한 오류로 기록하지 않는다. **현재 원 service를 그대로 조립해 완결할 수 있는 target adapter는 없다.** 또한 이 결론은 진짜 selected target용 source를 구현하는 것 자체가 불가능하다는 뜻이 아니다.

## 다음 필요한 제품 접점 한 건

`CompanionCostDelivery`와 같은 source owner가 **primary caster receipt와 selected target의 원 PreparedBuff/Resource Operation을 별도로 유지하는 실제 retained participant bridge**를 구현해야 한다. 최초 범위는 진짜 selected owner buff로 좁힐 수 있다.

1. canonical prepare 전에 같은 plan에서 발급한 전체 ordered views로 원 `SourceResponseAdapter.prepare_exact(target_binding, view, request)`를 수행한다. 실제 selected UID·writer·generation·lock을 보존하고 원 status reply도 같은 묶음에 둔다.
2. 기존 caster의 한 BatchStore commit·원 receipt를 유지한다. target로 `recover`하거나 두 번째 receipt/writer를 만들지 않는다. target preparation, 원 target Operation, semantic index와 실제 wire frame index를 한 번 연결한다.
3. `CompanionCostDelivery`의 원 capability/current와 broker send callbacks가 그 정확 participant를 검증하도록 연결한다. pending callback에서 generic provider.current/store.recover를 호출하지 않는다. 원 receipt의 WRITE_ATTEMPTED/UNKNOWN/DRAINED 규칙과 queued0/실제 drain 반환을 유지한다.
4. 동일 parent retire에서 source preparation/view·실제 target operation과 schema seal을 해제한다. postcommit 실패를 안전한 prewrite refusal/성공으로 바꾸지 않는다.

이는 source·수명 구현이 필요한 접점이며, 인터페이스 이름이나 bool callback만 추가해 충족할 수 있는 계약은 아니다. owner native actor/appearance 전체 답변을 이 selected-owner 접점의 선행 gate로 묶을 필요는 없다. 동료 자신 target의 native response 및 restore/tick/remove는 계속 별도 OPEN이다.

## 최소 확인과 범위

- 정확 optional/retirement/delivery/wire/actual2fd canonical 부모 SHA 5개 일치. exact public source caller를 로컬 Git object에서 원바이트로 공급했다.
- 입력 Python 8파일 AST parse만 수행했다. import/Factory/wholeload·fixture 성공·game/native/packet·write/drain·실제 오류 재현은 수행하지 않았다.
- v5 author8/peer review와 기존 기능 PASS를 재사용했으며 전수검사·새 검증기·observer를 추가하지 않았다.
- main branch/기존 unrelated dirty 파일을 보존했고 branch/worktree를 새로 만들지 않았다. 큐 등록·시험 발주는 root 범위다.

사용자 후속 요구 **동료 actor를 테이밍 펫/서먼 몬스터처럼 클릭해서 동료 설정 UI에 진입**은 독립 UI 계약으로 인계한다. 이 source 작업은 UI 코드를 소유하지 않으며 UI/native 클릭 성공으로 확대하지 않는다.
