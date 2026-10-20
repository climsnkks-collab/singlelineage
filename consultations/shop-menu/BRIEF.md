# 상담 범위: 원본 클라이언트의 상점 메뉴를 로컬 서버에 연결하기

이 자료는 현재 막힌 한 기능의 설계 상담용이다. 아래 source는 우리가 작성한 Python adapter의 일부이며 원본 바이너리·분석 원문이 아니다. 실제 메뉴 구현 완료나 상담 성공을 주장하지 않는다.

## 이미 연결된 경계

원본 클라이언트의 UI·입력·프로토콜을 유지하고 로컬 서버가 상태·저장을 담당하는 구성이 목표다. 실제 제품 메서드를 사용하는 격리된 source fixture에서 다음 서버 흐름은 연결됐다.

- 같은 Factory / Provider / Store / delivery owner 아래 아이템 사용의 backend 완료 → 장비 상태 → NPC HP 변화.
- 그 다음 정상 BUY 요청의 실제 decoder Frame → 정책의 수신 ordinal → private ADMITTED operation → 한 번의 atomic commit → 원 transport write/drain → 새 current inventory adoption.
- 과거 adoption/intent와 새 거래 권위의 분리, selected generation·task/thread·lock 검사, 실패·종료 정리.

가격·listing·Native/clock/process 관측은 명시된 fixture 입력이다. 이는 원본 서버 경제 규칙, 실제 게임 UI, 실제 normal NPC 메뉴 입력의 성공이 아니다. 이 하위 경계를 더 반복하는 것이 현재 메뉴 gap을 해결하지는 않는다.

## 반복해서 남는 gap

현재 실제 caller가 없는 구간은 다음이다.

normal NPC/Actor 입력 → C2S 4E43 → 서버 응답 4E44 또는 4E45 → 메뉴 UI → C2S HACTION 4ED4 → typed 목록 → 기존 거래.

메뉴·목록을 인코딩하고 guarded sender로 실제 write/drain한 뒤 detached listing을 발급하는 Python 경로는 있다. 그러나 실제 normal input과 current Actor/메뉴 source를 공급하는 owner bridge가 없다. 현재 양성은 synthetic source owner를 사용한 source fixture까지이며 제품 기본값은 off다. 기존 저장된 프로토콜·수명 근거를 재사용해도 실제 메뉴 이벤트의 정상 caller와 owner를 아직 연결하지 못했다.

현재의 `SourceTargetResolver`는 다음 여섯 callback을 요구한다.
`sent_input`, `current_sent`, `read_current_actor`, `current_read`, `observed_origin`, `current_origin`.
역할은 detached 정상 송신 receipt, 매 검사 때만 유효한 current Actor read lease, 서버 spawn과 같은 Actor라는 인과를 각각 확인하는 것이다. 공급자의 이름이나 True 반환 자체가 이 근거를 만들지는 않는다.

HAction owner도 여섯 역할을 요구한다: 실제 DRAINED 응답으로부터 메뉴 origin 분리, 현재 메뉴 검증, 명시 action/reply 해석, action·reply source 현재성 검사, 실제 목록 DRAINED 뒤 listing origin 분리. 실제 owner 공급자가 없으며 새 receipt 이름을 만들어 gap을 숨기지 않으려 한다.

## 현재 구조와 검토할 가정

1. 4E43 dispatch와 resolver는 canonical Binding을 먼저 요구한다. 현재 canonical-on 장비의 COMMITTED/DRAINED 경로는 backend 완료가 intent를 정상 종료해 `_current=None`이며, NPC 및 다음 BUY까지 통과했다. 따라서 이번 주된 막힘은 그 intent가 아니라 실제 메뉴 source owner 부재다. 다른 accepted intent/Eq-off 수명에서는 일반 bind 거부가 남을 수 있으나, 거래의 source-validated prebind release를 모든 메뉴 요청에 넓히는 방식으로 해결하려 하지 않는다.
2. 4E43은 transport 검사는 있으나 decoded Frame/ordinal을 private ADMITTED issuer로 연결하는 prefix가 없다. 4ED4에는 수신 issuer가 있으나 bind 전 accessor와 독립적인 메뉴-entry issuer는 부족하다. 공개 metadata나 노출 dict의 값은 새 권위가 아니다.
3. HACTION f1은 앞선 메뉴 응답의 echo다. 이를 4E43 target, NPC UID, merchant 또는 transaction ID와 같다고 가정하지 않는다. menu echo와 list context echo도 분리한다. 같은 payload가 나중의 정상 요청에서 재사용될 수 있다.
4. **이 가정이 과한지 상담하고 싶다:** 서버가 원 packet과 자신이 발급한 NPC registry를 검증하는 것만으로 충분한데, 정상 입력 처리의 선행조건으로 클라이언트의 과거 송신 receipt와 current Actor 읽기까지 요구해 스스로 막혔는가? 서버 상태 권위와 클라이언트 UI 수명 관측을 잘못 결합했을 가능성을 열어 둔다.

## 선택지와 trade-off

A. 기존 여섯 callback을 만족하는 실제 owner bridge를 끝까지 연결한다. 현재 계약과 frontend 인과를 잘 보존하지만, 필요한 최소 source가 아닌 전체 UI/Native 수명 복원을 선행조건으로 만들 위험이 있다.

B. normal packet을 수신한 server-owned selected session/NPC registry의 좁은 interaction route를 먼저 만든다. packet 필드와 서버 발급 identity의 관계가 근거로 뒷받침될 때만 채택하고, 빠진 거리·역할·가격 정책은 명시 local policy로 구분한다. 더 단순할 수 있으나 raw target 숫자를 곧바로 권위로 승격하거나 정상 UI source를 검증했다고 오인하면 안 된다.

C. Binding 없는 최소 ADMITTED request + 독립 detached menu issuer를 도입하고 기존 resolver는 bind 이후에만 사용한다. 순환을 분리할 수 있지만 owner 입력이 여전히 없다면 추상화만 하나 더 늘어난다.

현재는 A를 요구하면서 C의 필요한 prefix를 식별한 단계다. B 또는 다른 접근이 제품 목표에 더 직접적이면 기존 구조를 고집할 이유가 없다. 다만 원 frontend를 자체 메뉴·새 입력 경로로 대체하는 해법은 목표와 다르다.

## 제약과 원하는 다음 결과

원본 입력·UI·wire를 보존한다. 가짜 True callback, 과거 Binding/Actor/UI borrow의 왕복 보유, UID 절단 추론, 임의 command/가격/재고, 일반 intent auto-clear, 새 wallet/store, 가짜 ACK는 허용하지 않는다. 기존 atomic backend와 sender를 전면 재작성하거나 프로젝트 전체 계획으로 확대하지 않는다.

원하는 것은 현재 접근의 잘못된 전제를 지적하고, 막힘을 깨는 우선 전략 하나와 필요한 최소 source fact·구체 caller/callee·한 번의 판별 검증을 제시하는 것이다. 실제 source 사실이 부족하면 어떤 사실 하나가 결정을 가르는지 명확히 해 달라.

상대 source 위치: `readonly-menu-use-prefix-v1/SOURCE_GAP.md`, `dialogue-contract/dialogue_target.py`, `haction-list-ingress-v1/haction_list_ingress.py`, 해당 child의 dialogue sender/API, `backend-completion-next-trade-v1/API.md`. 전체 프로젝트 그래프나 원본 분석 자료는 첨부하지 않았다.
