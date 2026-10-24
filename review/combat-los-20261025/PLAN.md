# COMBAT 전체 완료 계획

작성 기준: 2026-10-25 KST. COMBAT main과 모든 후속은 combat 전담이다. 이 문서는 단위 Source 큐나 HANDOFF를 대체하지 않고, 전체 목표·빠진 기능·순서·완료 기준을 묶는다. 이번 작성은 계획 정리이며 제품 변경이나 시험 발주가 아니다. 구현 현황은 작성 당시 각 원담당 HANDOFF와 실제 결과의 제한된 성공 범위를 따른다. 실행 입력은 항상 그때의 최신 같은 계보 POST를 사용한다.

## 1. 최종 목표와 범위

완료 목표는 일반 PC와 NPC가 같은 월드에서 정상적으로 싸우고, 능력치·장비·버프·마법이 결과에 반영되며, 피격·사망·보상·다음 전투·저장 복원이 연결되는 싱글 PvE다.

정상 세션/월드 → 현재 능력치·무기·효과 확보 → 실제 대상 선택 → 거리·시야·생존·재사용 검사 → 같은 행동의 명중/피해/상태 판정 → 비용·HP·MP·효과 변경 → 실제 패킷 응답 → 반격/추적 또는 사망 → 제거·보상·재생성 → 다음 행동 → 정상 종료·재접속.

PC가 죽는 분기도 포함한다. 실제 치명 피해 → HP0 저장 → 원 사망 사이클 → 정상 공격/추가 피해 차단 → 정식 새 생명/재선택 경로 → 다음 전투로 복귀한다. 부활 방식·사망 패널티 등 근거가 확정되지 않은 규칙은 열린 결정을 남기고 임의의 동작을 넣지 않는다.

- 현재 직접 완료 범위: COMBAT 수치 판정, 현재 스탯 소비, HP/MP·사망·보상·성장의 전투 접점, 전투 상태의 저장/다음 행동 연결.
- 연동 완료 범위: NPC 대상/이동/AI/공격 주기/재생성, GEAR 효과 공급, BUFF 생명주기, ATTACK 시전/admission/상태·응답, 아이템 드롭/회복 입력. 각 원담당이 구현하고 COMBAT은 계약과 실제 소비를 닫는다.
- 동료는 현재 회수 전용이다. 동료 AI/공격/분배를 이 계획의 새 작업으로 재개하지 않는다. Warehouse·BOOK·상점 UI·프로젝트 정리는 이 세션의 구현 범위가 아니다.
- PvP와 미선정 콘텐츠 전종 지원은 현재 싱글 PvE 완료와 구분한다. 선정한 무기·주문·NPC·효과 목록을 명시하고, 그 목록에 남은 미지원/미확인은 완료로 세지 않는다.
- L1J 참고 구현은 명시된 LOCAL 참고 정책이다. 현재 NC 공식 서버 수치/동작과 동일하다고 선언하지 않는다.

## 최우선 추가 요구 — 벽·문·코너 뒤 적중 차단

최신 사용자 직접 요구: **벽 뒤 NPC 또는 캐릭터는 물리 공격·공격마법·유해 상태마법에 적중하지 않아야 한다.** NPC가 PC를 공격하는 방향도 포함한다. 미지원 PvP의 admission을 새로 허용하는 지시가 아니며, 현재 지원하는 모든 대상 경로에는 같은 비차폐 원칙을 적용한다.

이 항목은 일반 물리·마법의 핵심 완료 조건이다. 범위/길찾기 검사와 구분하고 다음 Source 상태로 판정한다.

| 경로 | 현재 확인된 코드 | 아직 완료되지 않은 것 |
|---|---|---|
| PC→NPC 근접/원거리 | 실제 대상/current/거리·HP/판정 연결 | 검토한 admission에 실제 벽·문·공격 edge/segment 차폐 입력·판정 미연결 |
| NPC→PC 근접/원거리 | 실제 위치·거리·이동/반격 operation | 거리1/길찾기가 벽·대각코너·문 뒤 공격 차단을 보증하지 않음. 해당 공격 LOS 미연결 |
| PC→NPC 공격/상태마법 | VisibilityGuard 계약·미확정 거부·시험 전용 우회 | 실제 지형 projectile 차폐·동적 문 owner와 real CLEAR 생산 미연결. 거부 코드만으로 LOS 기능 완료 아님 |
| 선분/광역/주기 효과 | 일부 geometry·현재 후보·수치 코드 | 선분 열거와 대상 목록은 장애물 검사가 아님. 효과별 origin/각 피해 대상 LOS와 실제 admission 필요 |
| 캐릭터 대상/받는 마법 | 일부 수치/read-only target facts | 지원되는 NPC→PC에도 차폐 필요. 미지원 PC→PC/incoming admission·실 caster는 별도 미구현/미연결로 유지 |

구현 순서: (1) 원 map의 공격/투사체 차폐 의미와 실제 door 상태 owner 확인 → (2) 같은 attacker/target/map/세대/operation에 결속한 현재 CLEAR/BLOCKED/UNKNOWN 생산 → (3) 원 물리 admission과 ATTACK VisibilityGuard 소비 → (4) 기존 잠금·async 경계에서 필요한 current/door 변경 재확인 → (5) 실제 차단/개방 시나리오.

이동 불가 비트·actor 점유를 곧바로 projectile 차폐로 재사용하지 않는다. Unknown 또는 stale geometry/문 상태를 CLEAR/빈 문 목록으로 채우지 않는다. 기본 정상 Source에서 LOCAL_TEST_VISIBILITY_BYPASS는 일반 기능 통과로 인정하지 않는다. 한 주 대상의 CLEAR를 광역의 모든 대상에 복사하지 않는다. 실제 적중에 필요한 재확인은 원 prepare/commit 수명에 두고, 이미 commit/시도된 결과를 문 변경 뒤 임의 rollback하거나 재추첨하지 않는다.

수용 시나리오: 동일 거리의 열린 경로/벽 차단 비교, 양방향 NPC/PC 근접·원거리, 대각 코너, 닫힌/열린 문과 요청 간 변경, 다른 맵/층·stale/unknown, 선분/광역의 대상별 차폐, 정상 선택에서 시험 우회 배제. BLOCKED/UNKNOWN 대상에는 피해·유해 효과·적중 성공 결과가 없어야 한다. 비용·탄약·시도/실패 표현의 시점은 원 정책을 명시해 확인한다. 새 codec/가짜 상태·권한이나 중복 검증 프레임워크를 만들지 않는다.

자세한 세션별 상태는 `combat-los-plan-review-v1/status-matrix.md`, 실제 LOS Source/행 근거는 같은 폴더의 `los-audit.md` 및 `source-file-list.json`을 따른다. 이는 로컬 코드 감사이며 웹 GPT 검토 완료를 뜻하지 않는다.

## 2. 완료 수준을 구분하는 기준

| 수준 | 의미 | 이 수준만으로 주장할 수 없는 것 |
|---|---|---|
| 계산/Source 구현 | 실제 파일·caller/callee와 제한된 정적/순수 계산 근거가 있음 | 실제 입력·전송·저장·화면 성공 |
| 실행 준비 | 정확한 Source 선정, 실제 입력, 실행 caller/RUN, 판정·부분 보존·정리가 완결 | 실제 실행 PASS |
| 실제 패킷 PASS | 정상 세션의 실제 UID/current로 요청·응답·상태/원 저장 결과를 확인 | 원본 화면·HUD·애니메이션 성공, 모든 콘텐츠 성공 |
| 해당 기능 완료 | 지원 범위의 정상/필수 거절·수명·저장 경로와 실제 소비가 닫힘 | 다른 계열·주문·무기·세대·전체 게임 동등성 |

처음부터 기존 수식과 전체 성공 시나리오를 다시 확인하지 않는다. 같은 변경에 필요한 검토는 한 번이며, 새 실패·실제 변경·누락 근거에 직접 영향받는 경로만 확인한다. 지원표 정리는 이미 준비된 시험의 선행 gate가 아니다.

## 3. 전체 기능별 작업과 완료 기준

### A. 전투 입력·기본 능력치·장비

필요한 동작:
1. 생성 능력치, 영구 변화, 현재 버프 능력치를 구분한다. 직업/레벨·STR/DEX/CON/INT/WIS/CHA와 파생 명중·피해·AC/ER/MR/SP·감소를 같은 current에서 계산한다.
2. 실제 장착 UID·슬롯·무기·방어구·강화·재료·탄약·무게·저항을 선정된 Definition으로 소비한다. 무기/효과를 두 번 더하지 않는다.
3. 장착/해제·성장·버프 변경이 완료된 뒤 다음 공격이 갱신된 값으로 판정되게 한다. 이전 선택/세대의 캐시는 사용하지 않는다.

현재: 수치와 여러 FullGear/current 연결은 구현됐다. 실제 성장·저장 복원 성공도 있다. 모든 직업/장비/특수 효과를 실제로 통과했다는 뜻은 아니다. BUFF200은 실제 선택 장비 projection 전달에서 멈췄고 원 BUFF 담당이 수정 중이다.

완료 기준: 지원 대상마다 실제 변화 후 다음 전투 입력과 current 수치가 일치하고, 해제/만료/재접속에서도 중복 가산·오래된 revision이 없다. 장비 생성/장착 자체는 GEAR 담당이 공급한다.

### B. PC → NPC 일반 물리 공격

필요한 동작:
1. 정상 공격 요청을 실제 대상 UID·현재 세대·생존·맵·거리/허용된 시야에 결속한다.
2. 근접/원거리, 무기·탄약, 대상 크기/재질/언데드/방어·감소·면역을 지원표대로 계산한다.
3. accepted 행동에서 RNG/명중/피해 판정을 한 번 만들고 같은 결과를 HP·소비·응답에 사용한다.
4. 빗나감·0피해·무효 대상의 HP 변화/탄약·효과 소비는 원 정책대로 구분한다. 거절된 요청으로 피해나 RNG 재추첨을 만들지 않는다.
5. 대상 교체·사망·제거·종료 중 취소와 이후 입력을 원 수명에 맞춘다.

현재: 계산/HP Authority 연결과 실제 처치가 있다. actual148은 hit/miss와 NPC HP6→0, actual198은 NPC HP6→5가 확인됐다. 이것만으로 원거리·특수 무기·전 공격 주기를 완료로 세지 않는다.

완료 기준: 지원하는 공격 종류의 정상 입력 → 같은 판정 → 단일 HP 반영 → 실제 응답 → 다음 공격이 닫힌다. 범위/생존/current 거절은 관련 RNG·commit 전에 수행된다.

### C. NPC 반격·추적·공격 주기

필요한 동작:
1. 같은 실제 NPC operation/공격자/대상에서 반격을 판정하고 PC RESOURCE에 한 번 반영한다.
2. PC가 이동하면 NPC가 실제 허용 edge로 추적하고, 새 pose/current에서 다시 반격한다.
3. 실제 선정된 공격속도·모션/clock 근거로 공격 주기를 적용한다. 네트워크 sample250ms/IO2s를 공격속도 수치로 사용하지 않는다.
4. 목표 이탈·대상 사망·NPC 사망/제거·세대 교체·세션 종료 시 반복 공격과 goal을 정리한다. 여러 NPC는 서로의 목표·operation을 혼용하지 않는다.
5. 속도 변화와 이동 제한 효과가 적용되면 실제 소비자에 반영하고 해제 후 정상 동작을 복구한다.

현재: actual198에서 PC HP10→5, hp-1-45 COMMITTED/DRAINED와 PCMove 저장이 실제 통과했다. 이후 owned-mover/current 세대 경계부터 미확인이다. NPC 원담당은 실제 mover 전달 한 곳을 수정하고 현재 좌표용 후속 후보를 준비했다. actual199는 이전 anchor와 현재 PC 좌표의 차이로 전투 전에 멈췄다. 최신 HP5에서 추적을 계속할 정상 회복 입력은 CONSUM 담당의 OPEN 계약이다.

완료 기준: 실제 NPCMove drain/current pose 뒤 추적·반격이 이어지고, 취소/정리 후 공격이 더 발생하지 않는다. 현재 HP·좌표·UID 계보를 옛 사본으로 되돌려 성공시키지 않는다. 전체 공격 cadence는 별도 근거를 갖추고 이 단계에서 닫는다.

### D. NPC 사망·제거·보상·재생성

필요한 동작:
1. NPC HP0에서 같은 current NPC의 Death를 한 번 소비하고 Remove/lookup 퇴역을 연결한다.
2. 같은 실제 kill receipt로 EXP·성장과 드롭/소유권 전달을 수행한다. 중복 처치·재접속·낡은 UID로 보상을 재발급하지 않는다.
3. 실제 새 UID/generation으로 재생성하고 다음 공격은 새 actor만 받게 한다. 이전 goal·lease·타격은 폐기한다.
4. 새 레벨의 Stats·최대 HP/MP·알림·저장값을 연결한다. INITIAL/원 생성 값과 과거 receipt를 보존한다.

현재: 과거 actual172의 명시 단일 NPC Death/Remove/lookup 부재와 actual148의 자연 처치·첫 EXP가 있다. actual163은 자연 35 distinct kill로 EXP125→300/level3, 성장 패킷과 durable DRAINED, fresh 일치를 실제 통과했다. 이를 전 몬스터 드롭/EXP표·현재 다중 NPC 재생성 완료로 확대하지 않는다.

완료 기준: 현재 지원하는 NPC가 처치 → 제거 → 보상 once → 실제 새 UID 재생성 → 다음 정상 공격으로 이어진다. 드롭의 생성/인벤토리/용량은 원 아이템 담당과 연결하고 COMBAT이 별도 아이템 시스템을 만들지 않는다.

### E. PC 치명 피해·사망·정식 복귀

필요한 동작:
1. 실제 landed lethal 판정과 같은 source-issued PRE/Context/cycle로 HP0을 원 native 저장 경계에 반영한다.
2. 정상 공격·추가 피격·다른 생존 전제 행동을 사망/pending cycle에서 차단한다. 다음 RNG·HP commit을 만들지 않는다.
3. 사망 상태/응답을 원 절차로 전환하고, 지원하는 정식 새 생명/재선택 경로를 통해 복귀한다. 비용/패널티는 선정 정책을 명시한다.
4. 전송 실패·부분 commit·종료를 구분해 저장 상태를 보존한다. 물리 정리만 성공한 것을 정상 사망/종료로 세지 않는다.

현재: HP0 입장 거절은 이미 구현됐다. 실제 lethal HP>1에서 Status와 Resource가 다르게 허용하던 조건은 d45 Resource 후손 한 predicate로 수정했다. exact6f72 계열에 한정하며 실제 lethal0 실행 PASS는 없다. 원 typed PRE helper/Observer API는 존재하지만 실제 RetainedSceneReader/sample·OBSERVED query 입력과 호환 lethal 실행 family가 미공급이다. 기존6f72 조립은 NONLETHAL이며 Resource만 교체해 lethal 실행 권한으로 바꿀 수 없다. NPC192의 다른 Resourceb4를 d45 파일로 덮지 않는다.

완료 기준: HP1 선행 강제 없이 실제 HP>1 lethal → HP0 저장 → 사망 사이클 → 다음 입력 거절 → 정식 복귀가 확인된다. 원 native CAS/once/current/receipt를 유지하고 이전 UNKNOWN을 성공으로 바꾸지 않는다.

### F. 버프·회복·재생·현재 전투 수치

필요한 동작:
1. STR/DEX뿐 아니라 지원하는 명중·피해·AC/MR/저항·감소·속도 효과를 실제 canonical SKILL/current에서 소비한다.
2. 시전/중첩·상충/갱신/제거/만료/복원 시 적용·원복을 일관되게 한다.
3. 자원 변화·최대 HP/MP 변화·회복 clamp·재생/명상과 전투 취소를 해당 원 정책으로 연결한다.
4. 실제 효과 유무가 필요한 추가 피해 분기는 같은 행동의 완전한 현재 효과 입력을 사용한다. 미확인 효과를 False나0으로 채우지 않는다.

현재: STRDEX25/41의 plan producer·봉인·commit 검증·cold binding, BUFF carrier 전달, cast drain DONE 뒤 Stats 갱신과 다음 physical capture 연결은 Source 완료다. lifecycle의 제거/만료/복원 갱신도 있다. BUFF200 이후 정상 시전/수치/만료 실결과는 아직 필요하다. 다른 버프와 재생/명상은 각 실제 소비 범위로 나눠 완료해야 한다.

완료 기준: 시전 전후 수치와 다음 전투 결과가 선정 정책대로 바뀌고, 갱신 시 중복 가산이 없으며 해제/만료/fresh에서 원복·복원된다. Test10초 duration과 정상 Source duration을 구분한다. BUFF/CONSUM의 시전/사용·아이템 준비 자체는 원담당 범위다.

### G. PC → NPC 공격마법

필요한 동작:
1. 학습·실제 spell Definition·대상 class/hidden/current·거리/시야·HP/MP/재료/재사용을 실제 시전 admission에 결속한다.
2. 같은 시전의 비용과 피해/상태 결과를 once로 처리한다. 원 owner의 원자적 저장 경계와 부분 commit 의미를 유지한다.
3. INT/SP·MR/속성/저항·마법 감소·critical·회복을 실제 actor/target 입력으로 계산한다.
4. 타격/실패/면역/사망·Remove·보상으로 연결하고 실제 feedback을 확인한다.
5. 주문별 direct damage와 확률/저주/Slow/Freeze/ManaDrain 등의 실제 상태 소비를 구분한다.

현재: 순수 마법 계산과 일부 admitted 자기힐 접점은 있다. ATTACK의 개별 주문 비용·ingress·상태 leaf는 여러 개 존재하지만 전체 정상 시전 완료가 아니다. 실제 대상/학습·MP·상태·응답을 ATTACK/NPC 원담당이 공급해야 한다. 시험 서버 LOS 예외를 일반 시야 성공으로 확대하지 않는다.

완료 기준: 지원표의 각 주문 종류에서 정상 received cast → 실제 admission → 비용 → 같은 대상 결과 → 응답/상태 소비 → 후속 행동/저장이 닫힌다. 한 주문의 성공을 다른 주문·미선정 target 유형에 복사하지 않는다.

### H. NPC → PC 마법·저항·카운터매직·반사

필요한 동작:
1. 실제 NPC caster·주문/분기·자원/재사용·현재 target·같은 operation과 RNG/StatusResult를 공급한다.
2. 실제 PC의 장비/버프 저항·MR·면역으로 피해/상태를 판정한다.
3. 카운터매직은 주문 분기와 원 정책에 따라 damage RNG 전 또는 실제 상태 성공 후 처리하고, 원 같은 계획/once 경계에서 효과30 소비를 연결한다.
4. 반사·counter mirror·무효/예외 주문을 지원표에 분리하고, 원 cast와 반사 피해를 중복 실행하지 않는다.

현재: COMBAT의 read-only current target facts·순수 계산/결정은 있다. 실제 NPC incoming caster/operation issuer는 미공급이다. PC→NPC 시전 경로나 비활성 Poison reader를 그 권한으로 사용할 수 없다.

완료 기준: 실제 NPC cast 한 건에서 피해/상태/차단/반사와 효과 소비가 정확히 한 번 발생하고, 비용·HP·SKILL/상태의 원 수명·부분 저장이 일치한다. caster/주문/성공 여부를 raw 값으로 꾸며서 통과시키지 않는다.

### I. 주기 피해·상태 이상·특수 공격

필요한 동작:
1. 독/지속 피해는 실제 상태 slot·세대·시각·tick cursor의 독립 권한으로 처리한다. 닫힌 cast permit을 tick에 재사용하지 않는다.
2. tick once·갱신·상충·제거/만료·사망·재접속에서 중복 피해나 다른 세대 피해가 없게 한다.
3. 지원하는 무기 proc·확률 배율·소모 효과·별도 추가타·광역/지속장판을 서로 다른 기능으로 다룬다. 같은-hit 배율을 추가 공격으로 세지 않는다.
4. 광역은 실제 발급된 대상 집합과 대상별 결과/수명을 연결하고 원 비용·반사·죽음 순서를 지킨다.

현재: 일부 proc/배율과 마법 계산은 순수 Source에 있고 producer/실제 소비가 열린 항목이 있다. 일반 물리 critical/모든 무기 효과 완료가 아니다. Poison10 tick/일반 status owner, 실제 광역 대상 생산·상태 소비까지 모두 완료되지 않았다.

완료 기준: 지원표에 채택된 각 효과의 정상/미발동/상충/만료·사망 중단이 실제 원 상태 owner에 의해 처리되고 중복 타격·tick·보상이 없다. 지원 근거 없는 특수 ID/타격/효과는 열린 항목으로 남긴다.

### J. 응답·저장·재접속·연속 플레이

필요한 동작:
1. 공격/피격/HP/MP/사망/제거/효과 응답을 실제 판정 및 원 receipt와 맞춘다.
2. COMMITTED와 DRAINED/UNKNOWN/UNATTEMPTED를 구분한다. 전송 실패 후 재차감·재추첨·임의 rollback을 하지 않는다.
3. 정상 종료와 fresh에서 HP/MP·EXP/레벨·장비/효과·원 UID 계보·receipt가 해당 변경 범위대로 복원된다.
4. 한 전투 이후 실제 회복·다음 NPC·재생성·버프 만료·다음 전투로 계속 플레이한다.
5. 원본 client 소비/HUD/애니메이션은 별도 관측 범위를 기록한다. 패킷 PASS로 화면 성공을 주장하지 않는다.

현재: actual159/163 성장 저장/fresh와 actual186 단일 fresh HP10/strict close PASS를 재사용한다. 186의 성공은 현재 피격/추적·Native Quit·PC death fresh까지 통과했다는 뜻이 아니다. 실제 전투 current는 이후198/199 계보이므로 옛 HP10/UID 사본으로 돌아가지 않는다.

완료 기준: 아래 최종 연속 시나리오가 선정 범위에서 닫히고, 필수 항목의 FAILED/UNKNOWN·미연결 소비가 남지 않는다. 화면/원본 동등성 미확인은 별도 명시한다.

## 4. 실제 진행 순서와 병렬 의존

| 묶음 | 다음 실제 작업 | 병렬로 진행 가능한 일 | 마감 조건 |
|---|---|---|---|
| 0. 공통 LOS | 실제 map 공격 차폐·문 상태 producer와 각 공격 admission을 연결한다. | 이미 준비된 비관련 기능은 별도 진행 | 벽/닫힌 문/코너 뒤 NPC·PC 적중 금지와 열린 경로 정상 동작. 시험 bypass 제외 |
| 1. 현재 물리 PvE | NPC의 owned-mover/current 후손·현재 좌표 후보와 CONSUM 정상 HP 회복 입력을 결합해 추적/새 pose 반격을 닫는다 | COMBAT의 실제 수치/Resource 결함, PC lethal 입력 구성 | 실제 이동/추적/새 반격과 정리. 기존HIT·HP10→5·PCMove는 재사용 |
| 2. PC 사망 | d45에 맞는 원 Life/Status/NPC/observer family·실PRE를 마련해 정상 lethal caller를 완결한다 | 버프의 정상 cast/current 수치 확인 | 실제 HP>1 lethal0·죽음·후속입력차단·정식복귀 |
| 3. 버프와 스탯 | BUFF200 장비 projection 전달 후 정상 cast→다음 수치/공격 소비→만료/복원을 닫는다 | NPC 사망/제거/재생성과 이미 준비된 공격마법 | 실제 current 효과 변화/원복·다음행동·저장 일치 |
| 4. 죽음/보상/재생성 | 현재 NPC kill→Death/Remove→새 UID→다음 공격, 드롭 연결을 닫는다 | 개별 주문의 정상 admission/비용/HP/응답 | kill/보상/재생성이 once로 계속되는 루프. 기존EXP35kill 재실행 gate0 |
| 5. 공격마법 | 실제 입력이 준비된 주문부터 개별 effect/cost/feedback 완결 | target/status/caster 공용 owner가 다음 주문에 필요한 producer 공급 | 지원 주문별 정상/실패·면역·후속 상태/저장 |
| 6. incoming/주기/특수 | 실제 NPC caster·상태 slot/tick·proc/광역 대상이 있는 항목부터 연결 | 다른 ready 기능은 계속 | 지원 효과별 실생산·소비·종료·once가 닫힘 |
| 7. 최종 연속 플레이 | 닫힌 기능을 하나의 실제 사냥/사망/복구/저장 흐름으로 묶는다 | 신규 기능을 이 마감에 끼워 넣지 않음 | 지원표·완료 근거·잔여가 일치하고 전체 필수 흐름에 미확인 없음 |

이 순서는 COMBAT 구현 묶음의 우선순위다. 실제 공용 Source 선택과 시험 순서는 통합 Root가 맡는다. 다른 lane이 미준비여도 준비된 기능의 시험은 즉시 보낼 수 있고, 모든 주문·전체 공통판을 기다리지 않는다. 외부 실제 입력이 미공급인 항목은 그 정확한 입력/owner만 OPEN으로 두고 새 가짜 API나 반복 검증으로 대체하지 않는다.

## 5. 담당과 산출물

| 담당 | 맡는 일 | 이 계획에서 요구하는 산출물 |
|---|---|---|
| COMBAT main/worker | 수치 판정·현재 스탯 소비·전투 Resource/죽음·보상/성장 접점 | 실제 제품 delta·정확 부모/선정·Source 근거·정상 패킷 시나리오/caller/RUN·판정/부분 보존/정리 |
| NPC 원담당 | 대상 UID/세대·좌표·이동·goal/반격·주기·Remove/Respawn | actual current 대상·operation·mover/caster/kill source와 caller |
| GEAR / BUFF / CONSUM / ATTACK / 아이템 원담당 | 실제 장비·효과·회복·시전·상태·드롭 생성/소비 | 원 상태/Source·완결 업무 caller·필요 현재 입력 |
| 공용 API 원담당 | 자기 파일의 실제 공용 계약 누락 | 정확 부모의 private Source 후손/API. 다른 owner의 전체 파일 overlay 금지 |
| 통합 Root | 완료 변경의 검토 결과·최종 Source 일치 확인, 결합·큐 선정·Test 발주 | 독립 상세 검토1회 재사용·고정 시험 선정판 |
| Test | 정상 직접 패킷 실행·시험 사본·자원·첫 오류·부분 저장·정리 | 원 결과/FIRST/현재POST·한정 PASS/첫 실패·관련 main 최종1회+동일큐 |

기성 client/codec/통과 flow를 사용한다. Runtime을 만드는 작업과 실행 권한은 구분한다. COMBAT main이 원담당 제품을 가져오거나 Test 실행을 대신하지 않는다. 통상 직접 채팅/ACK·Test 진행폴링은 없다. 완료 Source/API만 기존 단일 큐에 등록한다.

## 6. 검증과 전체 종료 조건

개별 기능에서 확인할 것은 다음이다.
- 정상 로그인/선택/WORLD와 앞 응답·실제 UID/current 이후 원 decoder/router/handler로 행동한다.
- 실제 요청/응답, 같은 판정, 상태 변화, 필요한 native 저장, 다음 소비를 구분해 확인한다.
- first miss/첫 실패/미확정/이미 commit된 partial을 원문으로 보존한다. 원하는 hit가 나올 때까지 재시도하지 않는다.
- 최소 거절 범위는 해당 변경의 실제 위험만: stale UID/세대, 사망/만료된 상태, 비용 부족/중복 소비, 취소/정리 이후 행동 등이다. 모든 변경마다 전부 돌리는 전수 체크리스트가 아니다.
- 영속 상태가 바뀐 경로에만 필요한 fresh 복원을 포함하고, 종료는 그 시험 끝에 합친다. 기존35kill/수식/왕복/유지/종료 성공을 관성적으로 반복하지 않는다.

최종 확인 흐름:
1. 실제 장비/지원 버프를 반영한 정상 공격과 NPC 반격.
2. 이동 → NPC 추적/새 pose → 후속 전투.
3. NPC 처치 → Death/Remove → EXP·드롭의 실제 전달 → 새 UID 재생성 → 다음 행동.
4. 정상 회복과 버프의 갱신/만료 뒤 전투 수치 변화.
5. 지원 공격마법·상태·카운터매직/주기 효과의 실제 소비.
6. PC 실제 사망 → 입력 차단 → 정식 복귀.
7. 마지막 strict close/fresh에서 해당 저장 상태·효과·성장·UID/receipt 계보 확인.

‘물리 PvE 핵심 완료’와 ‘지원 전투 전체 완료’를 별도 마일스톤으로 둔다. 전자는 일반 공격·반격/추적·양쪽 사망·보상/재생성·저장이 닫혔을 때이고, 후자는 지원표의 버프/마법/상태/특수 효과까지 포함한 위 전 흐름이 닫혔을 때다. 실제 UI/HUD/원본 공식 동등성은 그 관측 근거가 갖춰진 범위만 별도 표시한다. 계산 함수 존재·Source 수용·일부 한정 PASS만으로 전체 완료를 선언하지 않는다.

## 7. 열린 사항과 관리 방식

- 공격속도/재사용·특수 효과·무기/탄약·주문/대상별 지원 목록과 원문 정책/LOCAL/미확정 구분을 이 계획과 실제 구현에 맞춘다. 미지원 값을 일반 공격/기본값으로 대체하지 않는다.
- 사망 패널티/정식 복귀·전 몬스터 보상표·미확정 공식 규칙은 실제 근거/명시 제품 결정이 필요하다. 이 계획이 그 수치를 임의 결정하지 않는다.
- 현재 실제 막힘은 각 원담당의 최신 HANDOFF로 갱신한다. 계획 작성 자체를 제품 완료나 새 시험 Source로 등록하지 않는다.
- 새 버전·인계·소스 수용을 이유로 완료 검토/성공을 다시 시작하지 않는다. 계획의 남은 항목과 현재 가장 앞 실패만 갱신한다.

## 8. 핵심 근거

- [프로젝트 상위 계획](docs/IMPLEMENTATION_COMPLETION_PLAN.md): 전투 전체 항목은 있으나 이 상세 완료 범위를 묶은 계획은 아니었다.
- [COMBAT 인계](work/local_original_session/implementation-5/combat-adjudication/HANDOFF.md)
- [NPC 현황](work/local_original_session/implementation-2/npc-motion-goal/HANDOFF.md): actual198/199·현재 mover/회복 입력.
- [BUFF 현황](work/local_original_session/implementation-3/skill-buff/HANDOFF.md): actual200 및 원 carrier.
- [ATTACK 현황](work/local_original_session/attack-magic/HANDOFF.md)
- [자연 level3 결과](work/local_original_session/integration-1/packet-progression-level3-growth-actual-v2/level3-result.json)
- [단일 fresh/종료186 결과](work/local_original_session/integration-1/packet-combat-post176-onefresh-close-actual-v2/test-summary.json)
- [STRDEX 소비 경계](work/local_original_session/implementation-5/combat-adjudication/strdex-current-cast-continuation-v1/HANDOFF.md)
- [PC lethal 수정](work/local_original_session/implementation-5/combat-adjudication/pc-adjudicated-lethal-resource-v1/API.md)
- [lethal 실입력/family](work/local_original_session/implementation-5/combat-adjudication/pc-adjudicated-lethal-packet-v1/API.md)
- [incoming 마법](work/local_original_session/implementation-5/combat-adjudication/magic/incoming-admission-v1/API.md)
- [추가 물리 효과](work/local_original_session/implementation-5/combat-adjudication/additional-physical-effects-v1/API.md)
