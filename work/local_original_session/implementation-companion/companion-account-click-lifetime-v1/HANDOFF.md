# COMPANION-MAGE account click lifetime v1

WRITER_RELEASED / source_ready:true (bounded product component) / run_ready:false / test_ready:false / runtime:UNRUN.

## 실제 경계와 최소 변경

원 account Scopebf419474의 `checked_companion_transition`을 재사용한다. 이 원 함수는 진짜 token/실제 4E28 RECEIVED ordinal·writer/row·lexical task/thread·이전 generation 퇴역·account authority·정확 RETIRING/ATTACHING을 검증한다. 별도 token/registry/dispatcher/ancestry/caller-stack framework는 만들지 않았다. 기존 common/ITEM/Test/Scope/Factory/Allied/actor-config/이전 private source는 수정하지 않았다.

제품은 private 후손 세 파일이다.

1. **Host:** 부모 click Host5c561041 위에 additive hook 두 곳만 둔다. 원 `closed`가 Shared/interface를 정리하고 `_closed=True`로 만든 뒤, 같은 current Feature를 퇴역시킨다. 기존 scope Host slot 해제는 그 다음 원 코드대로 수행한다. 원 `attach`는 실제 native interface bind가 끝난 뒤 genuine scoped transition이며 기존 Feature가 있을 때만 새 Feature를 만든다. 콜백 fresh producer/Shared/default/클릭 helper·panel/current/command 코드는 원 AST와 같다. Feature가 없는 기본 경로에는 설치를 추가하지 않는다.
2. **Feature:** 부모2471d0d7에 optional original scope token과 `retire` 한 메서드, 일회성 `_retirement` 한 필드만 더한다. caller stack inspect나 ancestry 필드는 없다. cold 설치는 기존 not-started/no-sessions/empty 두 slots/interface/typed port/source guard를 그대로 적용한다. scope successor는 원 ATTACHING token·정확 token.new_companion/new current Host·같은 broker/policy/source·두 slots가 가리키는 동일한 retired predecessor와 그 원 token을 요구한다. 원 Plan이 캡처한 Feature SourceModule도 확인한다. 모든 검사가 끝나면 **새 객체 self를 old→new로 두 slots에 직접 게시**한다. None으로 비우거나 old Feature.host/attached/latch를 재설정하지 않는다. 전체 parser/header/dispatch/current/UID·generation·row/lease/root.current/DRAINED/removal·패널 guard는 원 AST와 같다.
3. **Broker:** 부모3c7b80ac의 기존 grant-owned 4F13 route body만 바꾼다. 매 요청에 같은 source의 nominal attached current Feature를 조회하고, 그 broker.realm 및 `registry.resolve(writer) is game`를 검증한 뒤 원 dispatch를 호출한다. 기존 connection route/원 terminal wrapper가 수명을 소유한다. **같은 still-live game의 원 route closure는 successor를 조회해 계속 사용한다.** 이는 same-game route continuity이며 retired Feature를 재사용하거나 다른 connection에 새 route를 부여하는 동작이 아니다. 원 game과 다른/퇴역 game, attached=False인 Feature, 미공급 successor, terminal cleanup 뒤 요청은 기존 terminal/registry/current guard로 거부한다. old Host Feature를 캡처한 callback은 사용하지 않는다. 전 transport/Scope/row operation/received header/close와 nonactor 기본 경로는 불변이다. Peer/Server는 원 byte 그대로 같은 새 product 폴더에 둬 Broker `_accept` sibling filename 경계를 유지한다.

실제 diff는 companion_host.py.diff / companion_actor_click.py.diff / broker.py.diff, 정확 부모는 parents.json이다. Feature의 새 Host/Broker seal과 unchanged Alliedd149 seal은 실제 cold module SourceSeal로 확인했다.

## close와 recovery 원문 확인

- **정상 close(None):** 원 Factory._close_companion가 exact config/Host/broker를 확인하고 Host.closed에 token을 전달한다. close된 nonselected current Host의 Feature만 퇴역한다. old slots는 그대로 retired object를 보유하며 cold 재설치에 쓰지 않는다.
- **첫/후속 계정 close:** 원 Scope.selecting은 genuine RETIRING token으로 old Plan.close를 호출한다. retire는 actual current Host/config가 token.old_companion 또는 token.new_companion인지 확인한다. 이번 Feature는 token을 한 번 기록하고 attached=False가 된다.
- **새 ATTACHING:** original Scope._construct_graph는 CONSTRUCTING fresh config 생성 → token.new_companion 지정 → 원 bind_companion → 새 runtime/source graph → ATTACHING Plan.create_broker를 진행한다. 새 Host attach가 위의 정확 retired-token/slot/source를 소비한다.
- **게시 전 실패:** 새 Feature가 모든 검사를 마치기 전 slots를 바꾸지 않는다. 기존 Host.attach except가 원 Host slots/interface/Shared만 정리하고 원 오류를 보존한다. old Feature는 같은 token으로 retired 상태다.
- **게시 뒤 실패/복구:** 원 Factory의 실패 cleanup은 phase를 RETIRING으로 만들고 current companion.close를 호출한다. 또는 원 `_recover_previous_graph`가 current BOUND Plan을 같은 token으로 닫는다. 이때 token.new_companion은 아직 실패한 current Host config다. 그 Feature를 같은 token으로 퇴역시킨 다음, 원 recovery `_construct_graph`가 새 config를 지정하고 다시 ATTACHING한다. 이 순서 때문에 ancestry 필드 없이 actual retired-token/slot identity로 충분하다. 원 close 자체가 실패하면 성공으로 바꾸거나 우회하지 않는다.

원 Scope/Factory는 그대로 참조했고 source-contract.json에 각 경로와 남은 범위를 기록했다. 이 설명은 source contract이며 실제 recovery/close 성공을 관측했다는 뜻이 아니다.

## 최소 검증

```powershell
python -B work/local_original_session/implementation-companion/companion-account-click-lifetime-v1/verify_source.py
```

46개 focused assertion PASS. 정확 부모 pin, Host의 두 hook을 제거한 전체 원 AST, Broker의 한 route body를 되돌린 전체 원 AST, 원 terminal guard, Feature parser/header/dispatch/current 불변, genuine token·정확 current Host/config·retired slot/captured source·cold admission, old 객체 변경/slot None reset/await/relock 부재, 원 close/recovery token 전달 원문, exact diffs/compile, 실제185행/183 module cold import 및 source seals, Peer/Server 동일byte·실제 compile filename을 확인했다. 처음 검증기의 ast.unparse 괄호/로컬 할당 집계가 과도한 assertion 두 개만 고쳤으며 제품 우회는 하지 않았다. main 중간 검토에 따라 제품의 caller inspect/ancestry는 제거하고 원 checked token/Host/slot 경계로 단순화했다.

Host/Feature/Scope/Plan/Root/owner/actor/lease/Store/runtime fixture 생성·설치, 서버/포트/실제 packet/send/저장·REA·실제 interface/summon은 실행하지 않았다. 기존 strict f1 parser/decoder 실행 결과는 부모의 exact AST이므로 재사용했다. report에는 가변 clock/시각을 쓰지 않으며 연속 확인은 같은 byte/hash를 남긴다.

## 남은 실행 조건

실제 source-backed interface와 normal summon/caller가 없어서 runtime_command:null / test_ready:false다. 이 후손도 없는 interface나 panel, Native Player callback, 4F14/응답 child를 만들지 않는다. LOCAL 4F13 f1 uint32와 no-wire `()` 의미는 그대로다. 화면/Native 클릭/소환/ATS/지원마법/CAST/정상 Quit 성공을 주장하지 않는다.

Main의 coherent 후손은 기존 actor-config f8b2의 Host15d/Broker934/Allied4d와 원 Factory capture를 새 정확 Host/Broker/Alliedd149/Feature·검토된 actor-only Factoryc79로 명시적으로 결속해야 한다. token.companion_sources에 이 exact Feature source가 없으면 successor가 거부한다. 이 폴더 cohort는 source/cold 증거만이며 actor-config나 Factory를 새 선정하지 않았다.

현재 별도 검토된 actor-only Factoryc79의 mode는 interface/support/rewards가 None인 actor publication 전용이며, 이 mode 자체를 클릭/UI 공급으로 부르지 않는다. 진짜 interface를 포함하는 별도 정상 configuration 계약 없이 이 Feature가 설치됐다고 주장할 수 없다.

수용된 ITEM target view4d2844는 Host219/Core86을 고정한다. 새 Host를 그 포트에 묵시적으로 대체하거나 최종 typed interface SourceModule이 설치됐다고 하지 않는다. ITEM의 native_opened/action_admitted:false와 equipment 미공급 경계는 그대로다. 다음 실제 정상 시나리오는 login/roster→root WORLD/current→genuine summon/실 UID·generation·DRAINED 등록→명시 LOCAL 4F13→원 같은 panel→Store/strict close/fresh이며, 앞의 미공급 interface/summon/caller를 우회해 최종 요청부터 보내지 않는다.
