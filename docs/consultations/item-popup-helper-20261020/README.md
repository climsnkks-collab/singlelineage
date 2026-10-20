# Popup 어댑터 정적 상담 요청

이 자료는 우리가 작성한 어댑터의 검증·진단 설계를 검토하기 위한 최소 익명화 패킷입니다. 원본 클라이언트 코드·디컴파일·어셈블리·바이너리·실행 자료는 포함하지 않습니다. 원본 소프트웨어를 직접 재현 가능한 공개 standalone도 아닙니다.

## 상담할 문제와 현재 상태

- 내부 실행 R269: 원 선택·Drop 진입이 정상 반환한 뒤 Popup 요청이 `REFUSED / 42005(Helper) / invoked=false`로 거부됐습니다.
- 내부 실행 R270: 선택·Drop 진입은 정상 반환했고 Popup은 동일한 범주로 거부됐습니다. 선택적 cancel 역할이 null일 때 원 계약상 허용되는 경로를 보존한 수정만으로는 거부가 해결되지 않았습니다. 어느 개별 검사가 false였는지는 두 실행 모두 모릅니다.
- 두 실행의 Popup 거부는 setter 이전 acquire/첫 current 경계입니다. 수량 setter/readback·원 whole Submit·backend/Ground/Get 성공은 확인하지 못했습니다. 이미 확인한 정상 종료·보존 결과를 Popup 성공으로 확대하지 않습니다.
- 최신 진단 후보 D는 기존 검사의 bool을 한 번씩 캐시해 첫 false 번호만 기록합니다. **이 패킷 작성 시 D의 다음 실행 결과는 아직 없습니다.** 기존 실행의 세부 false를 소급해 추정하지 않습니다.
- 별도 보호 경로는 R270에서 정상 반환·해제 후 상태 일치가 관측됐습니다. 그것은 Helper guard 성공의 증거가 아닙니다. 보호 기능을 해제·우회하는 제안은 이번 질문의 범위가 아닙니다.

## 주어진 계약과 어댑터 정책을 구분해주세요

주어진 계약의 요약: 정당한 실제 UI 실행 경계와 현재 등록 owner 아래에서 PC를 보유합니다. 보유된 PC는 객체 생존 근거이며, 현재 등록 상태·가변 helper/callback까지 고정하지 않습니다. 설치된 helper의 submit callable과 선택적 cancel callable, 실제 callback·widget/getter는 현재 요청과 일치해야 합니다. 원 setter/getter/whole Submit의 정상 반환과 정상 owner 정리를 보존합니다. whole Submit은 정상적으로 popup을 유지하거나 닫고 callback을 퇴거시킬 수 있습니다. 이후 옛 raw helper를 다시 쓰지 않습니다. 이 요약은 외부에 공개하지 않은 근거를 전제로 한 입력이며 웹 답변으로 새 ABI·레이아웃을 확정할 수 없습니다.

어댑터 정책: 실제 guard는 읽기 가능 범위, 정확 callable 역할/entry/포획 owner, 현재 identity를 순서대로 검사합니다. 숫자 상태 전체의 불변이나 전체 callback 바이트의 동일성이 원 native 필수조건이라고 간주하지 않습니다. 아래 발췌는 이 검사의 control flow를 opaque 역할로만 나타냅니다.

## 파일과 익명화 범위

`adapter-control-flow.cpp`는 **exact 제품 source/diff가 아닙니다.** 원래 프로젝트가 작성한 guard/trace/실패전파를 상담용 추상 C++ 표기로 옮겼습니다. 대상 주소·객체 오프셋·타입 주소·ABI·메모리 구현·구체 identity는 제거했고, 모든 read/span/type/owner 비교는 구현 없는 opaque predicate로 치환했습니다. predicate 순서와 단락평가·선택적 cancel·current identity·reason/status 전파를 논의할 수 있으나, 컴파일·게임 실행·원인 재현 근거로 쓸 수 없습니다. 생략한 capture/text/소유검사는 아래 단일 opaque 단계가 표현하며 그 내부 순서를 이 파일이 증명하지 않습니다.

최신 제품 진단 변경은 (1) 기존 Helper bool의 once-cache·23단계 번호, (2) 새 요청/acquire/current/Snapshot 진입 시 초기화, (3) 기존 출력 경로의 Code 또는 Helper REFUSED/!invoked일 때 캐시 정수 추가, (4) 두 include 선택의 새 자식 연결입니다. 기존 memory read 수·순서·권위 reason·수명·setter/Submit 경로는 그대로입니다. 발췌는 제품 delta 전체를 공개하는 파일이 아닙니다.

기존 검증 요약만 재사용합니다: 111 assert·각 false 23개·읽기/순서 delta 0, stale/reset·출력 IO 실패 무간섭, 엄격 경고 빌드 성공. 이는 해당 진단 변경의 근거이며 런타임 Helper 원인·제품 동작 성공 증거는 아닙니다. 이번 상담 패킷 때문에 추가 빌드·실행·관측을 만들지 않았습니다.

진단 해석: `phase=0` 새 시도 또는 미도달, `1` initial Snapshot, `2` current; `state=0` 미도달, `1` Helper 이전, `2` 검사 중, `3` Helper 블록 통과, `4` 정확 false. `falsecode=0`은 false 미관측이며 성공·권위가 아닙니다. 1..7 설치 helper/callback/callable 저장, 8..19 callable 역할/entry/owner, 20..23 current identity입니다. 새 attempt와 early current 실패는 stale cache를 지우고, 출력 요청과 다른 sequence의 캐시는 0으로 출력합니다. 순번은 실행 식별 값이 아닌 진단 필드 이름만 공개합니다.

## 구체 질문

1. 주어진 계약과 발췌만으로 필수검증·어댑터의 추가 정책·근거 부족을 어떻게 분류하겠습니까? 정확 타입/entry/owner/현재 identity 확인을 빼자는 결론은 필요한 추가 근거와 함께 조건부로 제시해주세요. 새 객체 필드·ABI·허용 상태 목록을 추측하지 마세요.
2. PC 강한 보유와 helper/callback의 가변성을 구분할 때 acquire→첫 current→setter→current→readback→current→whole Submit→정리 중 어떤 경계가 반드시 유지되어야 합니까? 동일 주소가 세대/수명 증명이 되지 않는 한계를 포함해주세요. 확인되지 않은 lease를 만들어 답하지 마세요.
3. 아직 D 실행 결과가 없을 때, 향후 status+phase+state+falsecode로 나눌 **최소 의사결정 표**를 제시해주세요. 1..7, 8..19, 20..23과 미도달/0을 구분하고, 관측 전 원인 확정·같은 실패의 추측 반복을 피해주세요. 새 collector·raw dump·주기 query는 요청하지 마세요.
4. setter 전 `REFUSED42005/!invoked`와 setter 뒤 current/readback 실패의 `UNKNOWN42008/!invoked`를 어떻게 구분해 설명해야 합니까? 이 진단 출력은 Code/Helper REFUSED 범위라 후자의 세부 false를 출력하지 않는 한계가 있습니다. 출력 부재를 setter 미시도로 해석하지 마세요.
5. 원 callback/whole Submit 정상 반환 뒤에도 실제 요청 송신과 backend/Ground/Get는 별도 조건입니다. 기존 소비자는 실제 Drop 상태+Ground 소유+DRAINED+pending 없음 후 원 Get을 호출하고, 실제 반환 상태+Player 소유+DRAINED+초기 frame 복원+revision 2 증가를 확인합니다. 이 분리와 정상 퇴거·no-retry를 유지하면서 결과를 어떤 수준으로만 주장해야 합니까?

원하는 답변: 확인 사실/조건부 가설/추가 근거가 필요한 항목을 분리한 짧은 검토와 최소 다음 분기. 이 패킷으로 원인·ABI를 알 수 없으면 명시해주세요. 실행 가드 강제 통과·가짜 helper·강제 current·보호 우회·재시도 코드는 요구하지 않습니다.

## 공개 허용 범위

공개 allowlist는 `README.md`, `adapter-control-flow.cpp`, `PUBLIC_MANIFEST.json`의 정확 세 파일뿐입니다. `LOCAL_ONLY_PROVENANCE.json`과 그 파일이 가리키는 로컬 자료는 업로드 금지입니다. 상대경로로도 allowlist 밖 파일을 자동 첨부하지 마세요. 원본 바이너리/동적 라이브러리·자원·저장·실행 로그 원본·REA 원문·주소/레이아웃·계정·실행 식별자·원 raw memory·로컬 절대경로는 제외했습니다. 파일 hash와 익명 후보 hash는 무결성 식별에만 사용합니다. 이 패킷은 게시/상담을 실행하지 않으며 지정 supervisor가 별도 소유합니다.
