# COMBAT A–J 구현 상태와 웹 GPT 재검토 질문

2026-10-25 KST / 계획·검토 자료만. 제품·계획 정본·실행·큐 수정 없음. 기존 상세 source/math/STRDEX/cold/refresh 검토 재사용. LOS 구현의 정확한 source 감사는 별도 worker 담당이며 이 표는 그 판정을 선취하지 않는다.

## 분류 기준

- **R — 실제 패킷 PASS(제한 범위):** 실제 정상 입력·응답·current/저장 중 명시된 경계만 통과. 한 기능/사본의 성공을 전체에 복사하지 않는다.
- **I — 코드 통합, runtime 미확인:** 실제 caller/callee/선정 또는 소비 경로가 존재하나 해당 실제 동작 PASS는 없음.
- **P — 부분 leaf/권위·입력 미공급:** 계산/안전 거부/접점은 있으나 필수 issuer/current/선정/입력이 닫히지 않음.
- **N — 확인 범위에서 실제 기능 미구현:** 실제 producer/consumer가 현재 지원 구현에 없음. 저장소 전체에 코드가 전혀 없다는 주장이 아님.
- **O — 타 담당·보류:** COMBAT이 대신 구현하지 않을 원 소유 또는 현재 명시 보류. 다른 상태와 병기한다.

SourceReady·검사 PASS·fixture PASS는 R이 아니다. 각 세부 기능의 지원 무기/주문/대상/정책 목록이 완료 범위를 결정한다. LOCAL L1J 참고 구현은 NC 공식 동등성 주장이 아니다.

## A–J 상태 매트릭스

| 계획/세부 기능 | 상태 | 누가 이미 구현했나 / 실제 완료 범위 | 남은 실제 작업·입력 / 담당 | 수용 기준·핵심 근거 |
|---|---|---|---|---|
| **A 기본 Stats·성장 입력** | I + 일부R | COMBAT: 생성/영구/유효 6Stats·직업·레벨·AC/ER/MR/SP·감소·current/P 입력. 실제148 첫EXP·159 level2 복원·163 level3 성장 연결은 R | COMBAT: 새 수치/선정 delta만. 모든 직업/장비/레벨 runtime 완료로 확대 금지 | INITIAL 보존, P/Derived/SELF/ROSTER/fresh 일치. [C], [PL] |
| **A 장비·저항·무게의 실제 소비** | I/P + O | GEAR가 실제 UID/슬롯/Definition/장착·저장을 공급. COMBAT FullGear/base-reference·10종 속성/상태저항 소비·중복방지 source 완료 | GEAR/BUFF: current 실제 장비 projection/cold 전달. COMBAT: 지원 Definition 효과만 소비; 미지원 instance/set/특수 효과 자동 채택 금지 | 장착/해제/다음행동/fresh와 revision 일치·효과 한 번 합산. [GR], [B] |
| **B 근접 물리 판정·HP** | R(일부) + I | COMBAT 수치/불변 Decision·원 NPC HPAuthority. 실제148 hit/miss·HP6→0/처치,198 NPC6→5 통과 | COMBAT/NPC: 새 실패/입력만 이어감; 범위·재질·언데드·면역·지원 무기별 전체 통과는 별도 | 같은 accepted intent RNG1회→HP1회→실응답→다음행동. [C], [N] |
| **B 원거리·탄약·공격 timing** | I/P | COMBAT에 근거리/원거리·무기/탄약 수치·명중/회피 분기 존재. 이를 native 탄약 소비/전체 속도 완료로 세지 않음 | GEAR/ITEM/NPC와 실제 탄약 UID/Q·범위·무기속도/행동 재사용 Source·소비/취소 caller 연결. 현 보급된 runtime 근거 부족 | 성공/빗나감/거절별 정책에 맞는 탄약·효과 소비; IO2s/sample250ms를 공격속도로 사용하지 않음. [P], [C] |
| **B/G/H 벽·문·LOS/투사체·feedback** | P/O(별도 감사) | 명시 시험 LOS 생략 예외는 존재하나 일반 벽막힘/시야/투사체 성공은 아님. 원 packet/target 검사와 구분 | 별도 LOS worker가 source/소유·실제 벽/동적문/범위/각 방향 동작 판정. ATTACK/NPC/원 map owner의 실제 callee로 연결 | 정상 정책의 막힌/열린 벽·문·코너, 대상변경·교체와 거절 시점/cost/RNG/탄약 의미. 아래 질문 참조. [P], [AT] |
| **C 반격·추적·공격 주기** | R(일부) + I/P/O | NPC 구현: 원 Controller/Session/이동·반복/생애·cadence guards. COMBAT 역방향 판정·Resource 소비. 실제198 PC10→5/hp-1-45 COMMITTED+DRAINED·PCMove 저장 R | NPC의 mover identity 전달 수정·현재좌표용 single/repeat/respawn 후보 준비. 실제 NPCMove/연속반격/fresh 미완. CONSUM 정상 회복 입력 OPEN | 현재pose에서 추적→반격; 사망/제거/목표이탈/종료 후 추가타 없음. 최신199 R45HP5/current계보 유지. [N] |
| **D 사망·Remove·EXP·성장** | R(명시 범위) + I/P | NPC 과거172 단일 Death/Remove/lookup부재; COMBAT148 자연 kill/EXP5,163 35distinctkill EXP125→300/level3/native성장DRAINED/fresh R | 현재 NPC family의 kill→명시Remove→새 UID/generation→다음공격은 NPC 후속 실결과 필요 | 동일 realKillReceipt/보상once; oldUNKNOWN/UNATTEMPTED 재작성·재award 없음. [P], [C], [N] |
| **D loot/drop·소유/용량·신규 NPC** | P/O | ITEM의 개별 Drop/Get 성공과 처치 기반 loot 생성은 구분. 이번 확인에서 kill→drop→원소유·획득 완결 근거 미확인 | NPC/ITEM 원담당이 실제 kill/drop-table/issued item UID·소유/인벤토리·용량 계약과 caller 공급. COMBAT 새 아이템 시스템0 | 같은 처치1회 생성/귀속, 중복·낡은 UID·재접속 재지급 없음. 미확인을 코드부재로 단정하지 않음. [P-D], [N] |
| **E lethal0·사망 admission** | I/P | COMBAT 기존 HP0 다음공격/추가피격 guard 확인(추가제품 불필요). Resource d45는 HP>1 실제 adjudicated lethal 허용 predicate 수정. Life/Status/PRE source는 NPC 담당에 존재 | exact6f72/Lifecad9/Status5527 packet family·진짜 retained PRE 입력 미공급. 현재 NPCb4에 d45 overlay 금지 | 강제HP1 없이 reallethal→native0→death/pending에서 RNG/commit 차단. [L], [C] |
| **E 정식 복귀·사망 패널티** | P/O + 미확정정책 | 원 Life cycle/typed recovery source 존재. 실해당 lethal→dead→정식복귀 full경로 R 아님 | NPC/Life: 실제PRE/DEAD/RESTORED current source와 정상복귀 caller. 패널티/부활 방식 미확정 부분은 명시 선택 필요 | 원cycle/TTL/once·fresh 보존, 회복/새생명 전 사망행동 거절. [L], [P-E] |
| **F STR/DEX25/41·다음 물리 소비** | I(이미 연결) | COMBAT de1e/97dc/e687 producer·seal·exactacceptedclock·coldbinding 완료. BUFF Scope4a25/runtimee9a8이 실제tuple 전달. 기존 Broker→adapter→skills refresh→physical capture, lifecycle 제거/만료/복원 갱신 존재 | 같은 refresh/캐시/API를 다시 만들지 않음. BUFF200 정확 Mage projection 후손 ready9v5/601v2 실결과 필요 | 실제cast 전후·refresh/만료/fresh 수치와 다음행동 일치. 아직 실제수치/시전 PASS 아님. [S], [B] |
| **F 기타 버프·회복·재생/명상** | I/P/O | BUFF/CONSUM에 원 cast/Use/cost/canonical/lifecycle 및 효과별 소비 source 존재. COMBAT 채택 수치 소비. 정상회복15/130의 다른 시험 PASS와 현재 MOB 회복은 별개 | 각 담당이 선정효과별 입력/실UID/Q/정상cost/최대치clamp/전투중 취소·지속회복을 닫음. 현재 MOB HP5/20 실제 회복품·family·Use 입력 미공급 | 중첩·상충·refresh·remove·expiry·restore, HP/MP max/clamp·tick/취소. Test10s는 정상duration과 분리. [B], [N], [P-F] |
| **G 직접 공격마법·자기힐** | I/P/O | COMBAT INT/SP/MR/속성/감소/crit/heal 수치와 자기힐 owner contact. ATTACK 개별 learned/cost/ingress/native상태·HP source 다수 | ATTACK가 PC→NPC caster/target/current/거리/시야/원응답·Book 입력/caller 완결. 공용 targetclass/hidden owner의 partial은 양성admission 아님 | received4EE6→실admission→한 cost/CAS→같은대상결과→feedback/Death/Remove/다음행동. [AT], [M] |
| **G 다중/선분·중심 타깃** | P/N/O | Lightning16 선분/순수분기 source; Fireball24 received입력 계약 요청 존재. 실제 세계 대상집합/다중 결과 완결 아님 | ATTACK/원input·NPC owner: actualcast target/center 의미·class/hidden·line/area cohort·대상별 생애/피해/반사/죽음. COMBAT 임의UID/좌표/AOE매핑0 | 한 비용과 실제 발급 대상별 once 결과, 제거/교체 대상 제외. [AT], [M] |
| **H NPC→PC 마법·저항/면역** | P + N(실incoming producer) | COMBAT 장비/효과 저항·피해/상태수식·readonly IncomingTargetFacts 존재 | 현재 확인된 선정범위에는 실제NPC spell/caster/operation/MP/cooldown/StatusResult issuer가 없음. NPC/별도 원담당이 실제 producer 공급; PC→NPC route 차용0 | 진짜incoming 한 건의 actualactor/target/동일RNG와 효과/HP/cost/source 수명. [IN], [GR], [AT] |
| **H CounterMagic30·반사** | P | 순수branch/exclusion·consume/reflection intent 존재. active30를 지운 permissive target 없음 | 실제incomingadmission·성공StatusResult 뒤 SKILL같은plan expectedrevision/remove30·반사HP owner 연결 필요. 독립30제거/가짜성공bool0 | damageRNG 전 또는 실제상태성공 후 원정책대로1회소비; 반사/원피해 중복 없음. [IN], [M] |
| **I 독·DoT·tick** | P + N(현재 native tick owner) | ATTACK Poison10 cost/marker/reference tick leaf 존재. native 실제tick0 | 공용 Monster-kind/globalpoisonslot·activegeneration/setup/tick cursor·독립tick-once HP/죽음·archive owner 필요. 원cast permit을tick에 전용0 | refresh/충돌/remove/expiry/death/respawn/fresh에서 중복·타세대 피해 없음. [AT], [DOT] |
| **I Slow/Freeze/ManaDrain·proc/추가타** | I/P/N/O(항목별) | ATTACK Slow28 common34 graph, Ice49 motion fence, Mana38 cost/reaction contacts. COMBAT generic tableproc/배율·마법 순수수식 | actualadmission/class/hidden/nativeMP/hate·AI/drop 반응 등 각owner 필요. bespoke무기switch/일반광역 대상원장·추가타재귀는 현지원구현 없음(자동지원0) | 상태성공→실제MOVE/반격/MP consumer→정상해제; proc미발동/중간사망/별도타격 once. [AT], [M] |
| **J packet/save/fresh·연속 플레이** | R(일부) + I/P/O | COMBAT159/163 성장·fresh/strictclose,186 단일HP복원 R. 실제198반격까지 R이나 뒤cleanup/fresh 미완 | NPC199 이전anchor에서 멈춤; 최신whole10 next536871549/rev25/R45HP5/asset49/현재좌표를 원담당후손이 승계. BUFF는 별도178계보. 정상회복·여러MOB·만료·다음전투 및 각partial 유지 필요 | COMMITTED/DRAINED/UNKNOWN 구별, 재시도 재차감·재추첨0; strictclose와 같은변경 fresh 확인. 화면/HUD/NativeQuit는 별도 미확인. [N], [B], [P-J] |
| **공통 보류/타담당** | O | 동료 기존 source는 보존·현재 회수 전용. GEAR/ITEM/BUFF/ATTACK/NPC/공용 source 소유 유지 | 동료자동공격/EXP분배·Warehouse/BOOK일반기능·PvP/전콘텐츠를 이 COMBAT후속으로 자동재개하지 않음 | 원소유/명시범위 준수. Root 통합, Test만runtime. [P], [C] |

## 우선순위와 완료 오인 방지

1. 이미 구현된 STRDEX producer/정확clock/cold/refresh는 재구현하지 않는다. 최신 BUFF200 후손의 실제결과만 관련 delta로 소비한다.
2. NPC198의 hit/counter/nativeHP DRAINED 성공을 재사용하고199 최신계보/좌표·회복 입력을 사용한다. 추적/재생성/공격주기 전체 PASS로 확대하지 않는다.
3. d45 lethal leaf는 실제packet family와typedPRE에서 막혀 있다. HP값을1/0으로 쓰거나 b4에 overlay하여 시험준비를 가장하지 않는다.
4. LOS·targetcurrent·incomingcaster·poison tick·ManaDrain 반응은 서로 다른권위다. 하나의 boolean/default값이나 물리Controller로 모두 대체하지 않는다.
5. 준비된각기능은독립진행하고, 미지원효과전체통짜나전수재검을선행gate로만들지않는다. source-only/실패/부분실행/실PASS를각결과그대로보존한다.

## 웹 GPT 재검토 질문

1. 이 표에서 실제로 구현된 타담당 source를 미구현으로 중복계획하거나, 반대로 pure/fixture/source-ready를 완결기능으로 잘못 분류한 곳이 있는가? 반드시 실제 Source/owner/RUN 근거로 지적해 달라.
2. A–J의 최소 싱글PvE 완료에 빠진 의존은 무엇인가? 특히 무기속도/재사용·원거리탄약·kill loot·정상회복·PCdead→정식복귀·실incomingcaster·tick 독립권위를 검토해 달라.
3. 별도 LOS 감사 결과와 대조해 벽·닫힌문·동적문·대각코너·다른맵/층·숨은대상의 각 PC/NPC 물리·원거리·마법 정책이 구별되는가? 범위검사/길찾기를 시야검사로 오인한 부분은 없는가?
4. LOS 거절은 실제cost/탄약/RNG/HP/시각효과 전 어느경계에서일어나야 하는가? 수락뒤/미시도write전 차단변화와 이미write시도된결과의 부분보존을 어떤기준으로 나눌 것인가? 별도 시험LOS bypass는 정상차단PASS에서 반드시 제외해야 한다.
5. 실제acceptedoperation/immutable결과가 모든피해·상태·반사·소모·죽음·보상·응답에 once로이어지는가? 전송실패/partial뒤재추첨·재차감/rollback 위험과 stale current/세대혼용은 어디에남는가?
6. 최소검증을유지하면서 각기능의 완료조건을 어떤 정상1경로/필수거절·수명·fresh관측으로 닫을 것인가? 이미통과한math/observer/source/cold전체를다시돌리는안은제외해 달라.

웹 GPT에는 이 표뿐 아니라 정확 branch/commit·대상파일을 주고 **연결된 GitHub 앱으로 실제 source를 읽었는지** 확인해야 한다. 로그인된 본인계정/실Pro 모델 조건과 상담 뒤탭정리 원칙을 따른다. 이번 unit은 질문 준비만이며 웹상담·브라우저·REA·시험을 실행하지 않았다.

## 근거 경로

경로는 저장소 root 기준. 최신 HANDOFF가 과거 날짜별 ready/stop/status보다 우선이며 이 표는 queue snapshot이나 Test진행조회가 아니다.

- [P], [P-D/E/F/J]: `work/local_original_session/implementation-5/combat-adjudication/COMBAT_COMPLETION_PLAN.md` 각 A–J.
- [C]: `work/local_original_session/implementation-5/combat-adjudication/HANDOFF.md` — 제한된148/159/163/186 및현재source경계.
- [N]: `work/local_original_session/implementation-2/npc-motion-goal/HANDOFF.md` — 실제198/199,현재후손/회복입력OPEN.
- [B]: `work/local_original_session/implementation-3/skill-buff/HANDOFF.md` — 실제200실패와수정ready9v5/601v2,실cast/expiry/fresh미확인.
- [S]: `work/local_original_session/implementation-5/combat-adjudication/strdex-current-cast-continuation-v1/HANDOFF.md`; `buff-cast-stats-producer-v1/API.md`; `buff-cast-stats-cold-binding-v1/API.md` — 완료된원소비경로/이전carrier공백해소.
- [GR]: `work/local_original_session/implementation-5/combat-adjudication/full-gear-magic-resists-v1/HANDOFF.md` — 지원장비/typed저항/이중가산방지와미지원범위.
- [L]: `work/local_original_session/implementation-5/combat-adjudication/pc-adjudicated-lethal-resource-v1/API.md`; `pc-adjudicated-lethal-packet-v1/API.md`; `pc-zero-hp-admission-v1/API.md`.
- [M]: `work/local_original_session/implementation-5/combat-adjudication/magic/API_SOURCE.md`; `magic/hostile-owner/API_SOURCE.md` — 순수수식과실권한접점구별,proc/AOE/특수무기제한.
- [IN]: `work/local_original_session/implementation-5/combat-adjudication/magic/incoming-admission-v1/API.md` — active30/readfacts와실incomingissuer미공급.
- [AT]: `work/local_original_session/attack-magic/HANDOFF.md` — 최신Fireball24입력·TurnUndead17disabledreceived·targetcurrent/Slow/Ice/Mana/Poison각owner.
- [DOT]: `work/local_original_session/attack-magic/poison10-reference-tick-owner-v1/integration-gap.json`.
- LOS source별정확행/수용범위는별도worker감사산출물로결속(이번worker재감사0). 시험LOS예외는현재AGENTS의ATTACK Test101한정승인과분리해읽는다.

WRITER_RELEASED. 이 파일만 작성했다. 계획정본·제품·코호트·테스트·runtime·import/Store/profile·queue·외부채팅 변경/실행0.


## LOS 감사 결합
실제 차폐 감사는 같은 폴더 los-audit.md와 source-file-list.json에 있다. 물리 admission의 실제 벽/문 차폐는 검토한 선정 경로에서 미연결, 마법은 계약/미확정 거부와 Test전용우회만 있어 real LOS 생산이 미완이다. NPC→PC의 캐릭터 피해도 요구 범위다. 미지원 PvP를 지원된 것으로 바꾸지 않는다. 웹 GPT 검토는 아직 수행되지 않았다.
