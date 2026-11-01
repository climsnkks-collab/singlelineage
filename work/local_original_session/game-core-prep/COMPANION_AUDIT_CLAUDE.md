# 동료 법사 예전 산출물 감사 (Claude 독립 판단)

작성 2026-10-27. 읽기 전용 감사이며 코드·큐·데이터는 바꾸지 않았다. 게임·서버는 실행하지 않았다.
표기: **[근거]**는 파일:줄 또는 경로, **[추론]**은 근거에서 끌어낸 판단이다.

## 0. 결론 요약

1. 사용자의 의심이 맞다. 예전 동료 작업은 "같이 사냥하는 동료"를 만든 것이 아니다. 저장·계정·패킷 송신 순서·정리 절차를 검증하는 장치를 쌓은 것이다.
   - 실제 실행 25회는 전부 **패킷 봇 실행**이었고(`native_game: false`) 원본 클라이언트로 동료가 화면에 나온 기록은 없다.
   - 실행 25회 가운데 16회는 게임 규칙이 아니라 스스로 만든 검사(250ms 표본 만료, 정확 drain 요구, 포트 객체 누락 등)에 걸려 실패했다.
2. 동료가 움직이거나, 공격하거나, 마법을 쓰거나, 힐한 런타임 기록은 **0건**이다. 이동·지원 선택 코드는 있지만 한 번도 실행되지 않았다.
3. 그래도 건질 것은 있다. 작은 순수 로직 몇 개, 정책 결정 몇 개, 그리고 **원본 클라이언트 내장 펫/소환수 제어창 분석**(4F13/4F14/4F02)이다. 마지막 것이 가장 값지다.
4. 나머지 대부분(구 Broker 후손, 서버 사본 수십 벌, DLL 10개, 큐 169건)은 새 월드 구조에서 쓸 수 없다.
   - 이유는 구 요청-응답 Broker·Core6041·Root 계보와 해시 고정에 묶여 있기 때문이다.
   - 새 구조에는 월드 틱, 엔티티 레지스트리, NPC AI가 생겼다.

## 1. 산출물 범위

### 1-1. 큐 (docs/INTEGRATION_QUEUE.json, revision 5106 기준 집계)

- 전체 345건 중 동료 관련은 **169건**이다.
  - feature별: `COMPANION-MAGE` 156, `GEAR-COMPANION-OWN-EQUIPMENT` 6, `ITEM-EQUIPMENT/*COMPANION*` 7.
- 상태 분포: **blocked 162 / superseded 7 / queued 0**. `test_ready=true`는 9건이고 전부 blocked 또는 superseded다.
- 생성 시각은 2026-10-23 10:38 ~ 10-24 11:17이다. 약 하루 사이에 169건이 등록됐다.
- blocked 사유:
  - 160건은 같은 문구다: "Latest human Companionmain01a16769 COLLECTION_ONLY until basicfeatures complete…". 기술 문제가 아니라 **사람이 동결한 것**이다.
  - 기술 사유는 2건이다. 둘 다 동료 이동 시험(one-step, sequential-carry-v2)이고, ROOT_FRESH owner_position 증거 덮어쓰기와 기존 guard 경로 문제 때문이다.
- superseded 7건: F101 restart drain 진단 v7·v9, LRS1 native 패널 3건(WM_COMMAND 분기가 설정 명령을 가림), native shop 후보 1건, sequential trial v1.
- 항목 요약을 키워드로 세어 본 분포다(중복 허용).

  | 주제 | 건수 |
  |---|---|
  | UI·클릭·핫키·패널 | 122 |
  | 저장·계정·복원 | 50 |
  | 소환·F101·4F13/14 | 48 |
  | 장비·인벤토리 | 39 |
  | 제거·퇴역·사망 | 38 |
  | 이동 | 36 |
  | MP·RESOURCE | 23 |
  | EXP·credit | 23 |
  | 공격 | 14 |
  | 버프 | 5 |
  | 힐 | 4 |

  **[추론]** 사냥 동료의 핵심인 공격·버프·힐은 전체의 10% 안팎이다. UI·저장·수명 절차가 압도적으로 많다.

### 1-2. 폴더·코드 덩어리

| 덩어리 | 위치 | 규모 | 무엇인가 |
|---|---|---|---|
| 동료 본작업 | `work/local_original_session/implementation-companion/` | 하위 폴더 243개, 파일 3,909개, 147MB, .py 1,065개(약 61만 줄) | 소환·모드·이동·지원·복원·UI의 "private 후손"들이다. `.py` 파일 이름은 169종뿐이고 나머지는 해시 고정용 사본이다. 사본 수는 `source_loader.py` 71, `companion_host.py` 43, `companion_actor_config.py` 39, `broker.py` 38벌이다. |
| 인계 문서 | `implementation-companion/HANDOFF.md` (182줄) | — | 마지막 상태: COMP-01/02A/03A/04B/05 단위표(약 113~120행), 실제265·266 결과(3~27행). |
| 실행 결과 | `integration-1/packet-comp*`(4), `integration-1/packet-companion-*`(21) | 25회 | 패킷 봇 실행 결과 JSON·FIRST·stderr. |
| 통합 검토 | `integration-1/companion-*` 등 | 동료 관련 폴더 67개 | 선정·검토·웹 Pro 검토(v1~v5) 기록. |
| 공용 Source | `shared-api/companion-native-dual-progression-credit-v1/` | — | 주인·동료 EXP 50:50 반단위 잔여를 한 번에 저장하는 native 트랜잭션. Core6041/Root78f 후손이고 runtime UNRUN(HANDOFF 첫 단락). |
| 공용 Source | `shared-api/companion-source-operation-broker-v1/` | — | 주인이 맞은 직후 같은 operation 안에서 동료 DEFEND 콜백을 부르는 Broker 후손. feature_ready=false(API.md 3~5행). |
| 공용 Source | `shared-api/comp01-actual265-pending-removal-current-sample-v1/` | — | 265 제거 실패(표본 297ms > 250ms)를 고치는 Broker 2줄 삽입. 검토 NOT_STARTED, UNRUN. |
| COMBAT 쪽 | `implementation-5/combat-adjudication/allied-basic-attack/` | 2.2MB, 29폴더 | admission v1~v3, physical-inputs v1~v7, attack-speed, split-exp v1/v2. split-exp만 순수 산술. |
| 장비·인벤 | `equipment-window/companion-own-gear/`, `spellbook/companion-own-inventory/` | — | 동료 장비 출생 패킷, 동료 인벤토리 UI 데이터. Source-only. |
| 원본 역분석 | `work/local_server_rea_20261016/run216…run310`, `run396_pet_control` | 18개 run | 펫/소환수 클릭·제어창·HUD, allied player 클릭·수명. run396은 2026-10-27 작성. |
| native DLL | `implementation-companion/local-ui-*`, `local-native-hotkey-package-v1` | DLL 10개 | `own-login-bridge-companion-{hotkey,distance,composite,lop1,lrs1*,ui,lui2}-v1.dll`. 전부 링크만 했고 **한 번도 로드하지 않았다**. |
| `tools/` 제품 코드 | `tools/local_original_session/` | **0** | 제품 트리에 동료 모듈이 없다. `companion`·`allied`가 들어간 .py 10개는 무관한 연구 도구다. **[추론]** 동료는 끝까지 제품에 합류하지 못했다. |

## 2. 실제로 동작이 확인된 것 / 모양뿐인 것 / 막힌 것

### 2-1. 실행 근거가 있는 것 (전부 패킷 봇, 원본 클라이언트 아님)

**[근거]** 25개 결과 JSON 모두 `"native_game": false`다.
- 예: `integration-1/packet-companion-zero-watermark-v10-actual-v1/zero-watermark-result.json:1950`, `:1957` `native_unverified: true`
- 예: `integration-1/packet-comp05-saved-members-only-actual-v2/test-summary.json:36`
- work 전체를 검색해도 `"native_game": true`인 동료 결과는 없다.

| 결과 | 판정 | 실제로 보인 것 |
|---|---|---|
| `packet-companion-account-actor-reader-v4`, `class3-reader-v3`, `preserved-skill-reader-v3`, `full-plan-host-v2`, `full-root-credit-v3`, `resource-host-fix-v2` | business_pass=true (6건) | 계정 안의 class3(법사) 저장 캐릭터를 동료 멤버로 읽기, 장비·스킬·RESOURCE 저장, 재접속 후 같은 값 확인. **저장 계층만 확인.** |
| `packet-comp05-saved-members-only-actual-v2` (실제266) | `LOCAL_COMP05_SAVED_MEMBERS_FRESH_STRICT_CLOSE_PASS` | 저장된 동료 2명·설정·성장값이 재접속 후 일치. actor는 비어 있다(EMPTY_NO_AUTO_SUMMON, HANDOFF.md:8-10). |
| `packet-companion-zero-watermark-v10` | strict close PASS, business_pass=false | 서버가 동료 actor UID 805306368(0x30000000)을 발급하고 4E96을 송신, 제거 요청 시 4E40·4E3B 응답 송신. 상태는 `AWAITING_POSE`, `native_hotkey_observed:false`, `ai_support_observed:false`. |
| `packet-comp01-actor-port-binding-v3` (실제265) | 소환 관측 후 제거 실패 | 소환 4E96 DRAINED, 서버 위치 map0 (32577,32945). 이후 Restart 제거 단계에서 표본 297ms가 250ms를 넘어 `PACKET_CURRENT_SAMPLE_REQUIRED`로 실패(HANDOFF.md:18-27). |

**[추론]** "동작 확인"이라고 할 수 있는 범위는 세 가지뿐이다.
- 서버가 동료 actor를 패킷으로 송신했다.
- 서버가 제거 패킷을 송신했다.
- 저장·재접속이 일치했다.

원본 화면 표시, 클릭, 이동, 전투, 지원은 한 번도 관측되지 않았다.

### 2-2. 실패 16건의 성격

| 첫 오류 코드 | 결과 폴더 |
|---|---|
| `PACKET_CURRENT_SAMPLE_REQUIRED` | removal-restart-v2, removal-sample-v3, comp01-v3 |
| `RESTART_EXACT_DRAIN_REQUIRED` | restart-drain-v8, typed-removal-v6 |
| `SERVER_OPCODE_UNBOUND` | removal-fresh-v4 |
| `LOCAL_SUMMON_REAL_ONE_PLAYER_DRAIN_REQUIRED` | first-summon, inner-error-v2 |
| `ALLIED_CURRENT_GENERATION_REQUIRED` | sameframe-v2 |
| `BATCH_CURRENT_CONNECTION_ROW` | scope-capture-v2, mage-equipment |
| `NPC_UID_ORIGINAL_REALM_BIND_ONCE_REQUIRED` | resource-host-world |
| `PACKET_WORLD_REQUEST_COMPLETION_REQUIRED` | root-world-v2 |
| `COMPANION_FRESH_CALLBACK_DEPENDENCY_NOT_CAPTURED` | account-actor-scope |
| `AttributeError … AlliedPlayerPort` (packet 0) | comp01-v2, comp05-v1 |
| SERVER_CLOSE 오류 | postdrain-v3 |

**[추론]** 16건 모두 게임 규칙 오류가 아니다. 자기 검증 장치(표본 유효시간, 정확 drain, 해시 고정 모듈 선택, 연결 행 일치)의 실패다. 고치는 데 쓴 시간이 다시 같은 종류의 장치를 만드는 데 들어갔다(v1→v10 계열).

### 2-3. 코드·계약 모양뿐인 것 (runtime UNRUN)

- **따라다니기·대기**
  - 근거: `local-allied-repeated-motion-trial-v1/companion.py:596-667`. FOLLOW/STATION 두 모드가 있고 한 틱에 한 칸 움직인다. 이동 방향은 축 부호만 쓰며 경로탐색·우회는 없다(641-644행 주석). 타이머와 백그라운드 작업도 만들지 않는다(1-10행 docstring).
  - 이 코드를 쓰는 시험(one-step, sequential)은 큐에서 blocked 또는 superseded이고 실행 기록이 없다.
- **지원(힐·버프·물약) 선택**
  - 근거: `companion-heal0-consumer-v3/companion_support.py:322-370` `choose()`. 규칙 목록을 우선순위대로 훑는다. 확인하는 조건은 HP 임계%, 최소 MP%, 쿨다운, 사거리, 버프 만료 전 갱신, 물약 예비 수량이다. 순수 함수이고 실행된 적은 없다.
  - 힐 실행부는 "HealZero admission + 고정 해시 producer"(30-60행)에 막혀 있다.
- **전투 모드**
  - 근거: `local-ui-mode-combat-host-merge-v1/companion_combat.py:1-13, 73-81`. PASSIVE/ASSIST/DEFEND와 교전 거리(1~8) 설정 저장만 있다. ASSIST/DEFEND는 `COMPANION_BASIC_ATTACK_PRODUCER_UNAVAILABLE`로 꺼져 있다.
  - 근거: `local-companion-basic-auto-attack-v1/HANDOFF.md:3` "Automatic repetition is NOT implemented. Attack magic deferred."
- **EXP 50:50**
  - 근거: `allied-basic-attack/split-exp-v1/allied_split_exp.py:28-44`. 정수와 반단위 잔여를 보존하는 순수 산술이다. native 저장 트랜잭션도 Source만 있다.
- **native UI**
  - DLL 10개는 빌드와 export 대조만 했다. `local-native-hotkey-package-v1/HANDOFF.md:3,25` "runtime:UNRUN … No DLL was loaded", `local-ui-native-linked-v1/HANDOFF.md:9` "never loaded".

### 2-4. 막힌 것과 이유

1. **사람의 동결**: 큐 160건. 칼사냥 완료 전까지 동료 신기능 금지(`docs/ACTIVE_TASK.md:97,101`).
2. **원본 클라이언트 클릭·핫키 경로가 막힘**
   - `local-native-click-321-install-v1/HANDOFF.md:3`: 법사 클릭으로 정당한 OPEN을 낼 방법이 없다. observer 미설치, 4F13 미송신, 설치는 `BLOCKED_SOURCE_INPUT`.
   - `local-native-allied-observer-installer-v2/HANDOFF.md:3`: CALL을 보존하는 패치 트랜잭션과 퇴역 경계가 없다.
   - 핫키는 실제 포그라운드와 물리 Ctrl+Shift+M 입력이 필요한데, 이를 허용하는 시험 슬롯이 없다(hotkey HANDOFF "Runtime first blockers").
   - **[추론]** "allied player(PC 외형)"로 띄운 actor에 원본 클릭을 붙이려면 클라이언트 함수를 후킹해야 했다. 수명이 안전한 후킹 설계를 끝내 못 찾았다.
3. **구 Broker 수명 계약**: Restart 제거 표본 TTL 250ms, 정확 drain, watermark. 새 월드에서는 의미가 없다.
4. **공격·힐 producer 부재**
   - 동료 시전자 HP/MP를 다루는 공용 SKILL/HP owner가 정해지지 않았다(COMP-03B 미확정, `docs/ACTIVE_TASK.md:103`).
   - 자기 공속·cadence·반복 target 입력이 공급되지 않았다(`docs/ACTIVE_TASK.md:120`).

## 3. 같이 사냥하는 동료에 필요한 요소별 상태

| 요소 | 예전 작업 | 상태 | 빠진 것 |
|---|---|---|---|
| 출현 | 서버 UID 발급 + 4E96 송신(패킷 봇에서 관측) | 부분 | 원본 화면 표시 확인, 외형 sprite 숫자(run266: class3/gender→숫자 producer 미공급), 주인 옆 배치 규칙 |
| 따라다니기 | FOLLOW/STATION, 한 칸씩, 축 부호 | 코드만 | 경로탐색, 막힘 우회, 맵 이동·순간이동 동행, 너무 멀면 재배치, 실행 |
| 대상 선택 | 주인 공격(ASSIST)·주인 피격(DEFEND) 이벤트 훅 계약 | 계약만 | 자기 피격 반응, 주변 선공몹 처리, 대상 유지·전환, 자동 반복 |
| 공격 마법 | 없음(deferred) | 없음 | 마법 목록, 사거리, 데미지, 시전 모션·이펙트 패킷 |
| 버프 | `choose()` 규칙에 buff 종류, 만료 전 갱신 | 선택 로직만 | 버프 효과 적용(월드에는 `world_combat.apply_buff`가 있다), 시전 표시 |
| 힐 | Heal0 규칙·사거리 계약(REA275: Chebyshev ≤ 행 값) | 선택 로직만 | 회복량 공식, 시전 표시, 실제 HP 반영 |
| MP | 비용·최소 MP% 검사 | 일부 | 자연 회복, 휴식 시 회복, 고갈 시 행동 |
| 위치 잡기 | 교전 거리 설정값(1~8)만 | 설정만 | 법사다운 거리 유지, 근접몹에서 물러나기 |
| 사망/부활 | 사망이면 retire, lethal은 미완 | 거의 없음 | 몹이 동료를 공격하는 경로 자체, 사망 표시, 재소환 대기, 패널티 정책 |
| 장비 | 동료 장비 출생 패킷, 인벤 UI 데이터(Source-only) | 모양만 | 장비가 능력치에 반영되는 경로, 교체 UI |
| 명령 UI | native DLL 패널·핫키(미로딩), 원본 펫창 역분석 | 막힘 + 근거 확보 | 실제 입력 경로. 아래 4절의 4F13/4F14/4F02 활용 |
| 저장 | 계정 멤버, preferences.companion, RESOURCE, 성장 | **가장 많이 다룸, 패킷 PASS 7건** | 새 월드 저장 형식으로 옮기기 |
| EXP 분배 | 50:50 반단위 산술 + native 트랜잭션 Source | 산술만 쓸 만함 | 새 월드 보상 경로에 연결 |
| 몹 어그로 | 없음 | 없음 | 현재 `npc_ai._pc_ok`는 `Kind.PC`만 표적으로 삼는다(`tools/local_original_session/npc_ai.py:207-212`) |

## 4. 재사용 가치 표

| 대상 | 판정 | 이유 |
|---|---|---|
| 원본 펫/소환수 제어창 분석 (REA270~281, `run396_pet_control/l1j/findings.md:54-73`) | **그대로** | C2S 4F13(펫 UID로 창 열기), S2C 4F14(f2 1=Pet/2=Summon 레이아웃, child f1~f6 필수), C2S 4F02(f1 모드: 공격2/방어3/휴식4/경계5/산개7/해산8은 확인 중). DLL 없이 원본 UI로 명령할 수 있는 유일한 근거다. |
| L1J 펫 행동 비교 (`run396_pet_control/l1j/findings.md` 전체) | 그대로 | 모드 의미, HP 미터(S_HPMeter), 출현·제거 순서의 설계 참고로 쓴다. |
| `allied_split_exp.split_integer_pool` | 그대로 | 10여 줄 순수 산술이다. 인간 확정 정책(50:50, 홀수 0.5 누적, `docs/COMBAT_COMPANION_PLAN.md:283`)과 맞는다. |
| `companion_support.choose()` 규칙 선택 | 고쳐 쓰기 | 우선순위 규칙, 임계%, MP 예약, 쿨다운 구조는 좋다. HealZero admission·해시 고정·generation 토큰을 걷어내고 새 월드 상태를 바로 읽게 한다. |
| `companion_spell_rules.plan_skill`의 비용·쿨다운 검사 | 고쳐 쓰기 | MP/HP 비용·쿨다운 그룹 처리만 남긴다. 마법 표는 새로 만든다(M3 마법 시스템과 공유). |
| `CombatSettings`(PASSIVE/ASSIST/DEFEND, 교전 거리)·`MovementSettings`(FOLLOW/STATION, follow_distance) | 고쳐 쓰기 | 설정 모델로는 쓸 만하다. 원본 펫창 모드 값(2/3/4/5/7)에 맞춰 이름을 다시 붙인다. |
| "동료 = 같은 계정의 class3 저장 캐릭터 + `preferences['companion']`" 결정 | 고쳐 쓰기 | 설계 결정은 재사용한다(저장 PASS 근거 있음). 저장 코드(account-v5, canonical batch)는 구 Root/Core에 묶여 있어 버린다. |
| 동료 UID 대역 0x30000000~(`allied_player_publication.py` 상수)·4E96 송신 바이트 예 | 고쳐 쓰기 | 아이디어와 wire 예시만 쓴다. 새 월드에서는 `UidAllocator`가 UID를 관리한다. |
| `companion.py` CompanionController (lease, serial, UNKNOWN, retire) | 버리기 | 한 칸 이동 외 실체가 없다. 구 Broker 포트 프로토콜과 수명 토큰 검사 위주다. |
| Broker 후손 전부(F101, restart drain, watermark, sample TTL, same-operation DEFEND) | 버리기 | 새 월드는 틱과 즉시 처리 구조다. 구 요청-응답 Broker의 수명 계약 문제를 고친 것들이다. |
| native dual progression credit 트랜잭션 | 버리기 | Core6041/Root78f 전용이다. "반단위 잔여를 수혜자별로 저장" 정책만 남긴다. |
| native DLL 10개와 click/observer/hotkey/LRS1·LUI2·LOP1 패널 | 버리기 | 한 번도 로드하지 않았다. 후킹 수명 문제가 미해결이다. 원본 펫창 패킷 경로가 있다. |
| COMBAT allied-basic-attack admission/physical v1~v7 | 버리기 | 구 계보 입력 계약이다. "동료는 자기 공속으로 반복" 정책만 남긴다. |
| 서버 사본(broker.py 38벌 등)·verify/finalize/manifest 스크립트 | 버리기 | 해시 고정용 사본이다. 제품 가치가 없다. |
| 큐 169건 | 버리기(정리) | 전부 구 계보 기준이다. **[추론]** 동료 재개 시 일괄 superseded 처리하고 새 단위로 다시 등록하는 편이 낫다. 이번 감사에서는 큐를 바꾸지 않았다. |

## 5. 새 월드 구조에 동료를 얹는 권장 설계 초안

### 5-1. 원칙

- 동료는 **월드 안의 또 하나의 엔티티**다. 패킷 수명 검증이 아니라 틱마다 판단하는 AI로 만든다.
- 몬스터용 `NpcAi`와 같은 방식으로 만든다. 즉 `runtime.scheduler`에 한 번짜리 예약을 걸고, 콜백 안에서 다음 예약을 다시 건다.
- 판정 기준은 원본 클라이언트 30분 플레이다(`docs/ACTIVE_TASK.md:140`). 패킷 PASS는 회귀용이다.
- 마법이 필요하므로 시기는 7장 M3(마법서·MP 마법) 이후 M4가 자연스럽다(`docs/ACTIVE_TASK.md:138`). 단계 1~3(표시·동행)은 M1 이후 언제든 가능하다. **[추론]**

### 5-2. 구성

| 부분 | 설계 | 새 구조의 접점 |
|---|---|---|
| 엔티티 | `Kind`에 `COMPANION`을 추가하거나, PC 계열로 등록하고 owner_uid를 둔다. 주인 로그인 시 주인 옆 빈칸에 출현, 로그아웃 시 제거. 죽으면 generation이 오르는 기존 규칙을 그대로 쓴다. | `world_entities.py:22-26` Kind, `EntityRegistry.add/kill/remove` |
| 표시 | 4E96 actor 프레임에 법사 외형 sprite와 이름을 넣는다. 이동과 공격은 몬스터와 같은 프레임 경로로 관측자에게 보낸다. | `world_visibility.town_spawn_frame`(sprite+이름 경로), `WorldView.npc_step`, `world_combat.attack_frame` |
| 상태 | HP/MP/레벨/능력치/버프/쿨다운. PC 상태 구조와 자연 회복을 재사용한다. | `world_combat.PcState`, `regen_tick`, `apply_buff/expire_buff` |
| AI | 새 모듈 `companion_ai.py`. 상태는 FOLLOW(주인과 거리 ≤ N이면 대기), ENGAGE(대상 공격), SUPPORT(힐/버프), STAY(제자리), RETURN(너무 멀면 주인 쪽), DEAD. 판단 순서: ①주인 위험 시 힐 ②버프 만료 임박 ③대상 있으면 공격(사거리 안, MP 예약 유지) ④따라가기. 경로는 `NpcAi._path_step`, `_can_move`, `local_line_clear`를 재사용하고 맵이 바뀌거나 15칸 넘게 벌어지면 순간이동한다(로컬 정책). | `npc_ai.py` BFS·LOS, `world_runtime.add_tick_hook` |
| 대상 선택 | 주인이 공격한 몹 → 주인을 공격 중인 몹 → 동료를 공격한 몹 순서. 모드에 따라 거른다(공격: 위 세 가지 / 방어: 뒤 두 가지 / 휴식: 없음). | `WorldView.pc_attack`, `npc_attack`에서 이벤트를 받는다 |
| 몹 쪽 | `npc_ai._pc_ok`와 `_perceive`를 "PC 또는 동료"로 일반화한다. 동료가 때리면 `on_hit(uid, attacker_uid)`로 어그로가 넘어가게 한다. | `npc_ai.py:167-174, 207-224` |
| 마법 | 첫 판은 에너지볼트·힐·버프 1종이다. 수치는 클라이언트 데이터 → 공식 정보 → L1J 순으로 정하고 출처를 적는다. 마법 표는 M3의 PC 마법과 같은 표를 쓴다. | 신규 마법 표, `choose()` 개조본 |
| 보상 | 동료가 처치하면 주인 보상 경로를 타고 50:50으로 나눈다(반단위 잔여 저장). | `WorldView._reward`, `split_integer_pool` |
| 저장 | `WorldPersist` 키 `('companion', owner_uid)`에 템플릿(class3 캐릭터 uid), 레벨/EXP/반잔여, HP/MP, 모드, 지원 규칙을 저장한다. | `world_persist.py` enqueue/flush |
| 명령 UI | 1순위는 원본 펫창(4F13 클릭 → 4F14 응답 → 4F02 모드 명령)이다. 2순위는 동료 클릭 → 기존 마을 NPC 대화창(4E43 → 4E44 하이퍼텍스트 → 4ED4) 메뉴로 명령하는 것이다. 채팅 명령은 클라이언트 송신이 Purple 커뮤니티 API 경로라 게임 소켓 opcode가 미확인이다(`game-core-prep/CHAT_EVIDENCE.md` 결론 절). 그래서 후순위다. | `world_handlers.py` CLICK/HACTION 경로, REA run277/279/396 |
| 사망 | HP가 0이면 사망 프레임을 보내고 제거한다. N초 뒤 주인 옆에 재소환하고 HP/MP 일부로 시작한다(로컬 정책, 패널티 없음). | scheduler 예약 |

### 5-3. 먼저 풀어야 할 미확인 (첫 단계에서 확인)

- **[추론]** 원본 펫창(4F13)은 Minion 계열 actor(Pet 타입 7 / SummonedMonster 17, run266)에서 열린다. 법사 외형 actor를 그 타입으로 보낼 수 있는지 모른다. 어느 4E96 필드가 actor 타입을 정하는지도 모른다.
  - 이 확인 결과로 "동료 = 펫/소환수 타입 actor"(원본 창 사용)와 "동료 = PC 외형 actor"(대화창 메뉴 사용) 중 하나를 고른다.
- 마법 시전 모션과 이펙트 패킷: 원본에서 실제로 표시된 근거가 없다(공격마법 계보 미완). 이펙트가 확인되기 전에는 데미지와 상태창 갱신만 하고 이펙트 없이 시작할 수 있다.

### 5-4. 단계별 작업 단위 (7개)

1. **원본 표시 프로브 (게임 1회 실행, 짧게)**
   - 할 일: 주인 옆에 법사 외형 actor를 4E96으로 띄운다. 한 칸 이동, 공격 모션 프레임, 제거를 각각 보낸다. 펫/소환수 타입 후보 필드로도 띄워서 클릭 시 4F13이 들어오는지, 4F14 응답에 창이 열리는지 본다.
   - 완료: 스크린샷과 수신 로그로 표시, 클릭, 창 열림 여부를 판정한다. 명령 UI 방식을 결정한다.
2. **동료 엔티티·상태·저장·출현/퇴장**
   - 할 일: Kind 확장, 동료 상태(PcState 재사용), WorldPersist 키, 로그인 출현·로그아웃 제거, 자연 회복.
   - 완료: 단위 시험과 재접속 후 같은 HP/MP/레벨.
3. **따라다니기 AI**
   - 할 일: `companion_ai.py`의 FOLLOW/STAY/RETURN. NpcAi 경로·LOS 재사용, 맵 이동 동행, 멀어지면 재배치.
   - 완료: 시험과 패킷 봇 동행 이동. 원본에서 주인을 따라 10분 걷기.
4. **전투 기본**
   - 할 일: 대상 선택 3순위와 모드별 거르기. 몹이 동료를 표적·반격하도록 `npc_ai`를 일반화. 에너지볼트 1종(사거리·MP·쿨·데미지 출처 명시). 처치 EXP 50:50.
   - 완료: 패킷 봇이 동료와 함께 사냥 루프를 돈다. 원본에서 동료가 몹을 공격하는 장면을 확인한다.
5. **지원**
   - 할 일: `choose()` 개조본으로 힐·버프·(선택) 물약. 주인 HP 임계와 MP 예약을 적용하고 효과를 반영한다.
   - 완료: 주인 HP가 임계 아래로 떨어지면 다음 판단 주기 안에 힐하는지 시험한다. 원본 상태창에서 HP가 회복되는지 확인한다.
6. **사망·재소환·휴식**
   - 할 일: 동료 사망 표시와 제거, 재소환 대기, 휴식 모드 MP 회복.
   - 완료: 일부러 죽게 하는 시험과 원본 확인.
7. **명령 UI 연결과 30분 플레이**
   - 할 일: 1단계 결과에 따라 원본 펫창(4F13/4F14/4F02) 또는 대화창 메뉴로 공격/방어/휴식/경계/해산을 연결한다. hunt_bot에 동료 동행 시나리오를 추가한다.
   - 완료: 원본 클라이언트로 동료와 30분 사냥할 때 깨지는 곳이 없다.

## 6. 이번 감사에서 확인하지 못한 것

- 동료 HANDOFF에 적힌 Test157(패킷 F101 → 제거 → Restart → fresh PASS)의 원결과 폴더는 열어 보지 않았다(계획 문서 `docs/COMBAT_COMPANION_PLAN.md:58`의 언급만 확인).
- 25회 결과 중 `FIRST.json`과 stderr 원문은 표본만 봤다. 판정은 각 결과 JSON의 `status`·`first_error`·`business_pass`·`native_game` 필드 기준이다.
- `companion_derived_stats.py`(148줄), 동료 장비·인벤 Source의 세부 내용은 읽지 않았다. 재사용 판정은 "구 계보 Source-only" 근거로 했다.
- 법사 PC 외형 sprite 번호: 자기 캐릭터 표시 경로에 있을 가능성이 높다 **[추론]**. 확인하지 않았다.
