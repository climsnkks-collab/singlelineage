# 현재 작업 상태
이 문서는 중지 범위, 저장 계보, 옛 담당 기록과 새 구조로 재개할 지점을 안내한다. 상시 규칙은 [WORK_RULES](WORK_RULES.md), 제품 계획은 [전투·동료 계획](COMBAT_COMPANION_PLAN.md)을 따른다.
파일 상한은 30,000바이트다. 마감 기록은 [월별 로그](history/ACTIVE_TASK_LOG_202610.md)로 옮기고 현재 상태와 필요한 링크만 남긴다.
정리 전 원문은 [ACTIVE_TASK 원본 보관](history/ACTIVE_TASK_ARCHIVE_20261026.md)에 보존했다. 아래 ‘원본 L’은 이 보관본의 줄 번호다.

## 1. 전체 상태

**2026-10-26 직접 요청한 REA 연결·지정 시험을 마감했다.** main이 기존 서버의 단독 writer, 일회성 worker는 새 world_shop_menu 모듈/시험만 작성했다. 시험 worker 하나가 포트12000/14030·헤드리스를 순차 소유했고 종료했다. 다른 제품·분석·큐는 STOPPED / WRITER_RELEASED이며 다음 일반 “작업 재개” 때 7장 계획을 시작한다. Source/결과 도착은 재개 권한이 아니다.

연결: run384/386 Arrow66/f6 present0(LOCAL 후보)/f14=1; run382/388 UML stem→buy/sell→목록→기존 거래/인벤 CAS; run389 기본 같은 맵 old-only4E40→self4EE0→new-only4E96·위치 저장·시야/관심 재계산. `-ArrowExp 'f6[,f14]'`로 후보를 바꾼다. `-ShopExp 1`에서만 목록 outer2=7·BUY6/7/8=0/0/0와 메뉴3상인 sprite 후보(Pandora98 등)를 켠다. `-ShopExp 'outer2,f6,f7,f8'`로 바꿀 수 있다. catalog template/f39·공식 필드값은 UNKNOWN, 기본 상점 목록은 거절한다. `-Hpbar` 기본0, 기존 `-MapExp` 대안은 명시 실험이다. 메뉴는 시작 때만 읽고 요청 중 해시/핀 확인·판독 대기는 추가하지 않았다.

원로그 접두사: `work/local_original_session/runs/rea-connect-20261026-225926`.

- `-scenarios.log`: all 4종16항목 SUCCESS·정리 완료. 귀환162 소진→4EE0 도착 및 positions.json 32578,32946 저장 확인.
- `-loopback5.log`: 사냥300.073초·24처치·25줍기·Lv2·사망/서버실패0·정리 완료. 봇에 PC 활 시나리오는 없다. integration의 실제 공격 frame에서 kind1/f6=0/f7=66/f13=true/f14=1 확인, 비행·화면 UNKNOWN.
- `-unittest.log`: 지정19+직접 영향2종=381 tests 최신 결과 OK. 최초 HP 기대값 FAIL1/이동 context stub ERROR1는 시험만 수정 후 12+7개 OK, 원실패 보존. ShopExp 표시 연결 뒤 town14/spawn8/integration12 재확인, 나머지 성공 재사용. 최신 모듈 로그는 -rerun/-shopspawn 접미사다.
- `-shop-probe-received.log`: FIRST/로그인/선택→수신 Pandora4E96(sprite98/UID268435463)→4E43/4E44 pandora→4ED4 buy/4E48 context1 row33→4ED1 mode5 수량1/-2,-2→0965×2·저장 아데나1000→963/물약100→101; sell/4EE7 context2 UID65545 단가19→mode6→0965×2·저장982/100. 정상Quit·handler_errors[]·정리 완료. 앞선 준비 실패2건도 보존, 실제 UI 미확인.
- [헤드리스 1회](../work/local_original_session/runs/rea-connect-20261026-225926-headless/result.json): RUN_EXIT=0이나 **FORCED_CLEANUP**, 정상종료 미확인/logout UNVERIFIED. 공격 intent COMMITTED·feedback DRAINED·34이동/idle hold 완료, render/HP/combat_effect UNKNOWN. broker failure null/cleanup true/tasks0/registry0/owned_job_empty true. LC.guard·포트0·bridge baseline 복원, 재실행 없음.

start-manual-play broker 핀 갱신·UTF-8 BOM 유지. 사용자 manual-user-play·기존 저장/로그 보존, 커밋 없음. 연결 전 상태와 큐 기록은 [월별 기록](history/ACTIVE_TASK_LOG_202610.md)으로 옮겼다. 큐와 2~6장 계보/보류는 변경하지 않았다.

## 2. 옛 담당 세션·참고 ID

아래 ID·실설정·소유 경로·상태는 중지 당시 기록을 찾는 참고이며 재개할 장기 세션이나 현재 writer 권한이 아니다. Claude가 필요한 Source와 미완 계약만 일회성 worker에 배정한다. `shared-api/`·기능 폴더의 기준은 `work/local_original_session/`이다. 실제 설정이 원문에서 특정되지 않은 것은 추측하지 않았다.

| 기능 ID | 옛 이름과 ID | 당시 실모델·effort | 당시 소유 경로 | HANDOFF/API | 당시 상태 |
| --- | --- | --- | --- | --- | --- |
| ORCHESTRATION | 오케스트레이터 `01a1704d-bcf2-7410-82e6-54c526a54a68` | gpt-6.1-sol / xhigh | 계획·우선순위·배분·조율 | [분리 인계](../work/local_original_session/integration-1/ORCHESTRATION_SPLIT_HANDOFF.md) | STOPPED, 통합 writer 해제 |
| INTEGRATION | 통합 Root `01a1717a-afe6-7a83-8b10-16fc3e930266` | gpt-6.1-sol / xhigh | 공용판·선정·공식 큐·Test 발주·정규 ACTIVE writer | [분리 인계](../work/local_original_session/integration-1/ORCHESTRATION_SPLIT_HANDOFF.md) | STOPPED / WRITER_RELEASED |
| TEST | 전담 Test `01a16d46-f794-7841-986e-1705a2b95c0b` | local gpt-6.1-sol / xhigh | 시험 사본·프로필·게임·서버·포트·DLL·공용 client/ready_current/API 호출부·FIRST/close | [Test 인계](../work/local_original_session/integration-1/test-session-handoff-20261021.md) | 269 마감, STOPPED / WRITER_RELEASED |
| COM-01 / COMP-02B/04A | COMBAT `01a16b89-d02c-7c73-80f2-e7140380aee3` | gpt-6.1-sol / high | `implementation-5/combat-adjudication/`, 명시 allied-basic-attack 후손 | [HANDOFF](../work/local_original_session/implementation-5/combat-adjudication/HANDOFF.md) | STOPPED, COMBAT ONLY |
| NPC-01 / LIFE-01 | NPC `01a16b90-ac2b-7283-b196-6c534903433a` | gpt-6.1-sol / high | `implementation-2/npc-motion-goal/` | [HANDOFF](../work/local_original_session/implementation-2/npc-motion-goal/HANDOFF.md) | STOPPED / WRITER_RELEASED |
| GEAR-01 | 장비 `01a17278-3dfc-76d0-9ace-b8133d1d1326` | local gpt-6.1-sol / high | `equipment-window/` consumer·cohort·caller | [API](../work/local_original_session/equipment-window/API.md) | STOPPED, 후속 수신처 |
| SKILL-BUFF | BUFF `01a16b66-02ab-7903-b402-4661a34d480b` | gpt-6.1-sol / high | `implementation-3/skill-buff/` | [HANDOFF](../work/local_original_session/implementation-3/skill-buff/HANDOFF.md) | STOPPED, BUFF ONLY |
| CONSUMABLES / HEAL-01 | 소모품 `01a16ce3-1a1e-7cc1-a6a8-1bafce00fe3a` | local gpt-6.1-sol / high | `consumables/` 입력·consumer·case·entry·RUN | [HANDOFF](../work/local_original_session/consumables/HANDOFF.md) | STOPPED |
| CAST-01/02 | 공격마법 `01a1705f-6cd5-7f01-82e7-d17713b37f73` | local gpt-6.1-sol / xhigh | `attack-magic/` cast·Poison application·outer·caller | [HANDOFF](../work/local_original_session/attack-magic/HANDOFF.md) | STOPPED, 실입력 미공급 |
| REA-01 | 별도 REA `01a16b9a-4988-7e01-98e0-0bcbb0283fb8` | gpt-6.1-sol / xhigh | `work/local_server_rea_20261016/` 명시 산출물 | [연락 계약](../work/local_server_rea_20261016/run379_adapter_output_binding_source/API_CONTACT.md) | STOPPED, Source-only |
| LOS-01 / MAP-Broker | MAP `01a16def-80c8-71b3-920e-014a8538662e` | local gpt-6.1-sol / high (마지막 명시 설정, 원본 L1676) | `shared-api/current-projectile-visibility/`·명시 Broker 제품 후손 | [API](../work/local_original_session/shared-api/current-projectile-visibility/API.md) | STOPPED |
| NATIVE-BORN | Native4 `01a1712c-307b-72b1-b3c0-4c333b2f2a43` | gpt-6.1-sol / high | `shared-api/native-npc-born-item-custody-v1/` 명시 최소 후손 | [HANDOFF](../work/local_original_session/shared-api/native-npc-born-item-custody-v1/HANDOFF.md) | STOPPED, funding 예외 미승인 |
| NATIVE-GEAR / USE | NativeUse `01a16e85-fd32-7d71-a698-a54fb8a4f956` | gpt-6.1-sol / high | 명시 Use·Retirer·Gear Store/Joint·BUFF263 후손 | [API](../work/local_original_session/shared-api/gear-native-backend-completion/API.md), [392d 인계](../work/local_original_session/shared-api/buff263-native-use-resource-continuity-support-v1/resource392d-pair-v2/HANDOFF.md) | STOPPED, pair 큐 대기 |
| TIMED-FACTORY | Factory `01a16e62-d950-7e30-a97a-b2bf3baeda41` | gpt-6.1-sol / high | 명시 timed17/495 Factory·17 builder·Scope 후손 | [API](../work/local_original_session/shared-api/timed-equipment-scoped-profile/API.md) | STOPPED |
| COMP-04B NATIVE | 동료 EXP Native `01a172cd-7ead-77a2-bac8-cbe657572c77` | local gpt-6.1-sol / xhigh | `shared-api/companion-native-dual-progression-credit-v1/` Core·Root·필요 schema 후손 | [HANDOFF](../work/local_original_session/shared-api/companion-native-dual-progression-credit-v1/HANDOFF.md) | STOPPED, Source 공급 완료 |
| CORE / PROCEEDS | Core `01a1718c-6afe-7cc1-9311-937ad178a4a4` | local gpt-6.1-sol / high | `shared-api/current215-same-root-proceeds-admission-v1/` | [API](../work/local_original_session/shared-api/current215-same-root-proceeds-admission-v1/API.md) | STOPPED, 기성 Source 재사용 |
| QUALIFIED-SOLD | qualified producer `01a17210-fc98-7c40-b2b2-73c4532fd263` | local gpt-6.1-sol / high | `shared-api/current215-legacy-qualified-sold-source-v1/` | [API](../work/local_original_session/shared-api/current215-legacy-qualified-sold-source-v1/API.md) | STOPPED, Source 공급 완료 |
| SHOP-QUEST / WAREHOUSE | SHOP `01a16bf3-6cbd-79a0-8251-9fcaefdaf358` (구 01a162d0은 CRITICAL로 해제) | local gpt-6.1-sol / high | `implementation-4/shop-quest/`, 창고 전부 직접 소유 | [HANDOFF](../work/local_original_session/implementation-4/shop-quest/HANDOFF.md) | STOPPED, 창고 관련 미착수 큐 26건 hold/반환 |
| SHOP-BOOK10-CATALYST166 | SHOP API `01a16ec5-acd0-77c0-92e1-75ccdd0e0b27` | gpt-6.1-sol / high | `shared-api/shop-book10-catalyst166-flat11/` 및 명시 후손 | [API](../work/local_original_session/shared-api/shop-book10-catalyst166-flat11/API.md) | STOPPED, Warehouse와 별도 |
| ACCOUNT-TRANSFER | Transfer `01a17042-a2e8-73e2-841e-7826e29b38d1` | local gpt-6.1-sol / high | `shared-api/account-v5-packet-transfer/`·명시 custody/current/fresh caller | [HANDOFF](../work/local_original_session/shared-api/account-v5-packet-transfer/HANDOFF.md) | STOPPED |
| NPC-MANA-REACTION | Mana `01a1701e-b377-73b2-9096-209b1af7e008` | gpt-6.1-sol / high | `shared-api/npc-mana-reaction/` | [HANDOFF](../work/local_original_session/shared-api/npc-mana-reaction/HANDOFF.md) | STOPPED |
| NPC-PERSISTENT-DAMAGE | PD/tick `01a1701e-b7d3-7c93-bb03-94488c083309` | gpt-6.1-sol / high | `shared-api/npc-persistent-damage/` | [HANDOFF](../work/local_original_session/shared-api/npc-persistent-damage/HANDOFF.md) | STOPPED |
| COMP-01/02A/03A/04B/05 | 동료 `01a16769-c8cd-7603-be3d-ff5050d8f20a` | 확인 필요(원본 L2020–L2021) | `implementation-companion/` 소환·모드·scheduler·명령·caller·복원 | [HANDOFF](../work/local_original_session/implementation-companion/HANDOFF.md) | STOPPED, old166 hold |
| BOOK | BOOK `01a17052-b911-75b3-a55b-6f888cfaf394` | gpt-6.1-sol / high | `implementation-1/item-equipment-product/` BOOK 전용 | [HANDOFF](../work/local_original_session/implementation-1/item-equipment-product/HANDOFF.md) | STOPPED, BOOK ONLY |

구 GEAR `01a16901-8691-7ae3-910c-6d8e88d78d68`는 CRITICAL 40.02MB로 모든 writer를 해제했다. 당시 후속 수신처는 위 01a17278이다. 구 queueowner·SENT·원Source는 보존한다. 옛 오케스트레이터→통합 Root의 ACTIVE writer 이전은 과거 기록이며 새 구조에서는 Claude가 문서와 worker 쓰기 범위를 조율한다.

근거: 원본 L1–L38, L49–L63, L109, L162–L169, L191–L199, L409–L425, L627–L638, L785–L805, L883, L997, L1277, L1455, L1533, L1864, L2020–L2021. 위 인계와 전투·동료 계획의 소유 지도는 과거 경계와 Source를 찾는 데 사용한다.

## 3. 진행 중·대기 단위

실행 중인 새 단위는 없다. 아래는 공식 큐 revision 5106에서 **status != blocked인 5건 전부**이며 모두 queued / test_ready:false다. 현재 동결한다. 표의 담당·다음 행동은 당시 미완 계약의 참고다. 재개 후에도 일괄 처리하지 않고 칼사냥에 바로 필요한 준비 항목만 Claude가 선정한다.

| 큐 ID | 담당 | 현재 단계 | 다음 행동 |
| --- | --- | --- | --- |
| `SKILL-BUFF-actual263-completed-diagnostic-output-coherent-intake-v2-20261025` | BUFF 01a16b66 | 진단 DATA 13개 소비 Source-only. Native392d pair 미소비 | [소비 API](../work/local_original_session/implementation-3/skill-buff/buff263-completed-diagnostic-output-intake-v2/API.md)와 실제 선정 Source·미결합을 통합 확인한다. 진단을 원인 수정·재시전 PASS로 취급하지 않는다. |
| `BUFF263-exact392d-native-pair-v2-6fdacbca` | NativeUse 01a16e85 | exact392d/Status6c7e Use·directRetirer pair Source-only, UNRUN | [pair API](../work/local_original_session/shared-api/buff263-native-use-resource-continuity-support-v1/resource392d-pair-v2/API.md)와 원 ab2510c1/dbfbc126 계약으로 수용 여부를 판정한다. BUFF가 최신 POST의 caller/RUN을 완결한다. |
| `CONSUMABLES-timed267268-strict-original-world-resource-prefix-source-contact-v1` | CONSUM 01a16ce3 | 공통 Source 계약, actual operand UNKNOWN, 새 v18/RUN 없음 | [필요 계약](../work/local_original_session/consumables/timed267-world-first-recovery-contact-v1/required-source-contract.json)의 정당 canonical resource prefix·realBroker 순서를 원소유자가 지원한 뒤 같은 Q0 POST 후속을 준비한다. |
| `REA-COMBAT-P0-379-same-output-adapter-binding-source` | REA 01a16b9a | SOURCE_ONLY. whole extent 미확정, callback tag store 없음. 누적2726/PData276 | [연락 계약](../work/local_server_rea_20261016/run379_adapter_output_binding_source/API_CONTACT.md)의 파생 근거만 통합 확인한다. actual Value/installedrow·door current 미공급은 유지한다. |
| `SKILL-BUFF-actual263-remaining-three-fullgear-normal-run-v2-20261025-actual-v269-test-result` | Test 01a16d46 / BUFF 01a16b66 | 269 마감·FAILED. 212 제한 PASS 뒤523 BUYLIST 거절. 수용 전 | [Test 인계](../work/local_original_session/integration-1/test-session-handoff-20261021.md)와 [결과](../work/local_original_session/integration-1/packet-buff263-remaining-three-full-credit-actual-v2/test-summary.json)의 원오류·POST143/131·partial·UIDburn을 수용한다. 같은 실패를 성공으로 취급하지 않는다. 재현·환경 분리·성능 목적 재시험은 원결과를 보존한다. |

그 외 중지 직전 미완은 MAP actual265 authentic pending sample, NPC retained37 소비 caller/RUN, HEAL01 funding Source다. 미완 계약의 근거는 기존 [동료](../work/local_original_session/implementation-companion/HANDOFF.md)·[NPC](../work/local_original_session/implementation-2/npc-motion-goal/HANDOFF.md) 인계 및 [HEAL01 계획](COMBAT_COMPANION_PLAN.md)이다. 칼사냥에 필요한 접점만 일회성 worker로 배정하고 동결 기능은 재개하지 않는다.

근거: 원본 L3–L13, L29–L36. 큐 5건의 ID·상태·후속 도착 결과는 공식 큐 revision 5106 원payload를 따른다.

## 4. 저장 계보 현재값

계보별 최신 POST와 성공 범위를 구분한다. 원오류·partial·current·UIDburn·COMMITTED/UNATTEMPTED·FAILED를 보존하며 다른 계보 PASS를 합산하지 않는다. 아래 재시도 금지·영구 skip은 당시 소비·저장·UID를 되감거나 재소비하지 않는 경계다. 같은 Source의 재현·환경 분리·성능 목적 재시험 자체를 금지하지 않으며 정상 시작 저장과 모든 결과를 보존한다.

| 계보 | 최신 완료 actual·POST와 현재값 | 보존 상태·소비/저장 경계 |
| --- | --- | --- |
| same-MOB / Native4 | **actual264**, DATA는 actual260 POST와 byte동일. NPC586..622→next536871623/rev27. ITEM1825..1861→next1073741862. asset86/history83=old46+37issue. HELD37 COMMITTED_UNATTEMPTED·pendingNone. PLAYER65537/65538 각tpl1Q3, HP5/max20 MP10/10 RESOURCE45. held14/PLAYERtpl7 없음, cash UNKNOWN. | 254 burn549..585·원FAILED/partial/SENT 보존. 260 초기 GEN0 출생37/current UIDQ/실저장·strictclose와264 whole10 readonly fresh/strict만 scoped PASS. durable HELD는 live/adopt/award 권위가 아니다. oldlife 재bind·재ISSUE·UID 재사용·legacy downgrade·되감기 금지. |
| 9BUFF, 원본 최신 수용분 | **actual263 POST12**, asset130/SKILL119. RESOURCE4→5 HP416/max456 MP326/max352, cash94, learn[1,2,13,25,31], buffs{}, nextUID1833. consumed602UID1831Q0·held205UID1832Q1. 새 거래 14건은 COMMITTED_DRAINED다. 구성은 startup 9건과 602 BUY126/BOOK127/CAST128, 205 BUY129, expiry-tail130이다. | root+child3 inventory 두 파일만 변경, other10·미선택·Source 보존. raw allfixed=false/copyorigin=false 그대로. 602 BUY/LEARN/STORE/CAST/EFFECT·205 BUY만 PASS. 602 NUMERIC_EFFECT UNSUPPLIED/evidenceNone. 205Use ord13 `ITEM_USE_RESOURCE_CONTIGUOUS_REVISION_REQUIRED`/reply0·LEARNFAILED/noBOOK205. 재BUY·임의재Use·기존CAST·INIT/refund/reset 금지. |
| 9BUFF, 이후 도착 결과 | **actual269가 가장 큰 실행번호**. 같은 사본 POST130→143/SKILL119→131, learn[1,2,13,25,31,51], HP416/max456 MP326→311/max352, buffs{}. BUY212 native140 DRAINED UID1073741833Q1→BOOK141 DRAINED learned51/Q0→CAST142 DRAINED, BUFF51tick143 COMMITTEDDRAINED. 새 거래 13건은 모두 COMMITTEDDRAINED다. 구성은 startup 9건과 BUY140, BOOK141, CAST142, tick143이다. UIDnext 확인 필요(큐269 요약에 없음). | **RECEIVED_UNREVIEWED**, 통합 수용 전. 212 BUY/LEARN/STORE/CAST/EFFECT 제한 PASS, NUMERIC/expiry/fresh UNSUPPLIED. 523 BUYLIST ord11 DRAINED2 [4E48,4E91] 후 `BOOK_PACKET_ACTUAL_BUY_LIST_RESPONSE_REQUIRED`; servererrorNone. 523 실BUY/UID/payment/Use/CAST·607 행동 없음. strictcleanfalse·cleanup[]·aftersnapshotclosedcleanuptrue/failureNone/socketclosed/physical0은 전체 PASS가 아니다. held205·paidUIDburn·원FAILED·raw false 두 값 보존. 새사본·초기화·재시도 금지. |
| 9BUFF 유료 carry | 195 BOOK116 학습 PASS/CAST UNKNOWN. BUY96 DRAINED와 raw BUYFAILED 분리. 599 CAST95/EFFECT/NUMERIC_EFFECT PASS. paid181 BUY45/BOOK46/CAST56 DRAINED·oldCAST26 UNATTEMPTED. actual240 expiry/restore UNKNOWN. | 180181195599601602205 진전·실패는 최신269에서 불변으로 보고됐다. CAST/BUY/Use/비용/회복 재생·과거 POST 초기화 금지. |
| 별도601 | **actual246 POST11**, asset99/SKILL92. HP456/456 MP332/352, learn30/gem없음/cash98. child3만 변경했고 startup 9건은 DRAINED다. canonical RESOURCE와 oldtx는 불변이다. | 원241 CAST90 COMMITTED_WRITE_ATTEMPTED/UNKNOWN·재료166Q1→0·MP352→332·buff30 저장·Refused/WRITE_CHECKPOINT 보존. BUY88/BOOK89 PASS를 CAST/EFFECT/CATALYST PASS로 확대하지 않는다. 재CAST·환불·reset 금지. UIDnext 확인 필요(원본 L129). |
| CONSUM495 | **actual267**, 저장은 actual257 그대로 **56/49full55=old47+8DRAINED**, Q0. savedGEAR48 COMMITTED_UNATTEMPTED. | 257Use1/nativeITEM17 DRAINED·Q1→0·timer durable 및 첫 strict PASS 영구 skip. 267 첫 복원 WORLDord4 `PACKET_WORLD_ORIGINAL_BROKER_FIRST_REQUIRED`/5응답·strict FAILED/active_restore·expiry·fresh UNRUN. whole8/current/timer/cash/RESOURCE/UIDburn 불변. Use·BUY·init/adoptprepare/recommit/reprojection/clockforce/refund/reset 금지. UIDnext 확인 필요(원본 L43). |
| CONSUM17 | **actual268**, 저장은 actual258 그대로 **49/42full48=old40+8DRAINED**, Q0. savedGEAR41 COMMITTED_UNATTEMPTED. | 258Use1/nativeITEM17 DRAINED·Q1→0·timer durable 및 첫 strict PASS 영구 skip. 268 첫 복원 WORLDord4 같은 originalBrokerFirst 오류/4응답·strict FAILED/active_restore·expiry·fresh UNRUN. whole8/current/UIDburn 보존. 양Use 재실행·수동 GEAR delivery 승격 금지. UIDnext 확인 필요(원본 L43). |
| GEAR source-issued 거절 | **actual244**, asset23/Gear5/RESOURCE3, whole6delta[], oldtx/newtx0/pendingNone. | semantic 거절·sameUse once-release/JointIDLE·current/StatsWeight 불변과 strictfirst+readonlyfreshUse0만 scoped PASS다. old239FAILED를 보존한다. nativeCOMMITTED·성공backendtoken·화면 PASS가 아니다. UIDnext 확인 필요(원본 L134). |
| GEAR paid BUY744 | **actual250**, actual248 불변 paid POST의 readonly 관측. asset28/SHOP19/Gear8/RESOURCE6, UID1073741833Q1, wallet9. AC10 MR15 water0 STR13 CON10, cap1800/carried254/gauge34. oldtx/newtx0/pendingNone. | 250 WORLD/동일 StatsWeight/nativeStorehistory/strict/whole6 불변 scoped PASS. 원243·248 FAILED·liveposttrade publication 미수정·원UIDburn 및 oldcatalog27 COMMITTED_UNATTEMPTED 보존. paidBUY·catalog 재commit·수동 setup/refresh/sample·reset 금지. UIDnext 확인 필요(원본 L117). |
| 동료 소환·저장 | 소환 **actual265** actor805306368/member2/direct1/currentpose, next805306369 burn. removal WRITE_ATTEMPTED/UNKNOWN·actor/direct/companionlease retained. 독립 saved-only **actual266** whole7/원55 불변, saved RESOURCE revision42/0·preferences·progression/current/fresh 관측. | 265 Restart sample297ms>250ms `PACKET_CURRENT_SAMPLE_REQUIRED`/reply0·strictfalse/hostclosedfalse. 266 scoped PASS는 active actor·효과·halfcarry·native·fullrestore PASS가 아니다. 261/262 prepare 실패/packet0·259 미착수 held/copy·runtime·actorissue0·원SENT 보존. leaseclear·timestamp 재작성·reissue·retry265 금지. |
| BOOK 원계보 | 원203 whole11 / **actual210 POST12** / 211 실패 보존. actual224는 준비 실패 INPUT_UNSUPPLIED·owner0/runtimeUNRUN으로 POST21012 불변이다. UIDnext 확인 필요(원본 L543·L743). | Source-only 후손을 저장 진전으로 간주하지 않는다. 전110 완료·일반 동료Heal·창고 권위를 만들지 않는다. 원본·partial/current·UIDburn·BOOK 전용 유지. |

실제 파일·FIRST·source-copy·preservation·raw 결과와 원오류는 [Test 인계](../work/local_original_session/integration-1/test-session-handoff-20261021.md) 및 각 기능 HANDOFF가 정본이다. 269 문서 반영은 제품 수용·시험 재개나263 원결과 수정이 아니다.

근거: 원본 L3–L5, L21–L27, L35, L43, L54–L55, L96–L102, L112–L120, L129, L134, L141, L157, L168, L543, L743. 이후269 값은 공식 큐 revision 5106·Test 인계·BUFF HANDOFF의 RECEIVED_UNREVIEWED 기록을 따르며 원본 최신 수용분과 분리했다.

## 5. 기능 동결·유효 보류

칼사냥 완료까지 **동료, 창고, 공격마법, 버프 확대, 상점 확장 등 새 기능을 동결**한다. 기존 결과·Source·큐·실패 원문·부분 저장·UID 소진은 보존한다. 칼사냥은 정상 시작 저장→로그인·월드 진입→이동→현재 NPC 선택→칼공격→피해·NPC HP 감소→NPC 반격·PC HP 변화→NPC 사망→경험치·실제 보상→저장→재접속→다음 사냥으로 한정한다.

| 항목 | 유지할 경계 |
| --- | --- |
| old166 | 과거 동료 미착수166개 hold와 옛 Source·SENT·시험 기록을 보존한다. 동료 새 기능을 시작하지 않는다. |
| Warehouse | 창고는 동결한다. 옛 원담당 SHOP `01a16bf3`·SHOP API `01a16ec5`는 참고 ID다. 관련 미착수 큐 26건 hold/반환, Stage1v2·계정 V5 acquisition 미기동 보류 기록을 보존한다. (원본 L15, L1750, L2020) |
| BOOK | BOOK `01a17052`·BUFF ONLY·COMBAT ONLY는 옛 작업 경계다. 일반 동료Heal이나 새 버프 기능을 배정하지 않는다. COMP-03B 공용 SKILL/HP manifest owner·부모·파일 미확정은 남긴다. |
| Pro | 별도 Pro 브라우저 자동화 보류는 일반 재개로 해제하지 않는다. |
| 공용 파일·실행 | Claude가 공용판과 worker 쓰기 범위를 조율한다. 공용 client/ready_current/API 호출부·게임·사본·포트·FIRST/close는 일회성 시험 worker 하나가 맡으며 한 파일 한 writer와 게임·포트 하나를 지킨다. |
| 기성 Source | Native 동료 EXP·retained37 지원·Factory·qualified-sold·Core/proceeds 공급 완료 Source를 다시 미공급 gate로 만들지 않는다. 칼사냥에 필요한 실제 caller·입력·RUN·runtime 미완만 잇는다. |

근거: 원본 L15, L30–L38, L47–L63, L109, L1277, L1748, L2016–L2020. 옛 담당의 영구 소유·Root/Test 분리 절차는 새 구조에 적용하지 않는다.

## 6. 막힘·확정 필요

| 구분 | 필요한 결정·입력 | 현재 판정과 소유 |
| --- | --- | --- |
| 사용자 지시 대기 | 작업 재개 | 지금은 중지 유지. 다음 “작업 재개”에 새 구조·7장 칼사냥 계획을 별도 재승인 없이 시작한다. 새 Source·결과 도착은 재개 지시가 아니다. |
| 사용자 결정 | HEAL01 시험 PLAYER funding 예외 | **재화 지급 예외는 인간 미승인**. Native01a1712c의 실행 없는 private 지원 Source 준비만 배정됐고 현재 중지다. 사본생성·UID/native·Store·게임/Test 발주 허가가 아니다. |
| 외부 입력 | HEAL01 potion14 또는 price37 자금 | 정당 UID/template/Q/provenance/currentcatalog·획득근거·새 caller/RUN 미공급. cash UNKNOWN은0이 아니며 NPC_LIFE Adena744는 PLAYER 자금/award가 아니다. |
| 외부 입력 | 운영 LOS | actual provider/buffer→Value/installedrow·door event/current·open 의미·geometry/projectile 결속 미공급. SourceReadyfalse/testfalse/UNRUN·운영 P0 PASS 없음. 허가 대기가 아닌 의미/입력 미확정이다. |
| 구현·계약 | BUFF263 continuity·진단 | 실제 callee/guard operand UNKNOWN. Native392d pair·진단 소비는 큐 대기 Source-only. RESOURCE4→5를 원인으로 단정하지 않는다. 269의523 BUYLIST 실패는 별도 실결과다. |
| 구현·계약 | CONSUM267/268 복원 | 정당 canonical resource prefix·realBroker 순서 지원 필요. 개별 actual operand UNKNOWN. index 검사 삭제·임의prefix 허용·caller reorder로 통과시키지 않는다. |
| 구현·입력 | NPC·동료 | NPC retained37 caller/cohort/RUN·HP5 생존 또는 정당회복·P0/current/realclock·새1 자연kill/strictclose 미완. 동료265 authentic pending sample·실공속/cadence/repeat target·COMP-03B writer·EXP consumer/growth/caller/coldclassspace 미완. 기성 Native 재발주 없음. |
| 외부 입력 | GEAR SELL·ATTACK | SHOP actual65538 f2/provenance null UNSUPPLIED. livepublication 하위예외/operand 미관측. ATTACK positive host·Book/current38·정당 학습/재료·초기 status·geometry/proc 미공급. |
| 기록 확인 | 실설정·현재 값 | 동료 실설정은 원본 L2020–L2021에서 확인 필요다. UIDnext 미기재 지점은 별도601 L129, CONSUM17/495 L43, GEAR paid BUY744 L117, GEAR source-issued 거절 L134, BOOK L543·L743이다. BOOK은224 준비 실패로210POST12 불변 기록까지 확인했으며 더 새 완료 POST는 확인 필요다. 269 UIDnext는 원본에 없고 큐 `SKILL-BUFF-actual263-remaining-three-fullgear-normal-run-v2-20261025-actual-v269-test-result` 요약에도 없다. 세부 값은 Test 인계·원결과에서 확인하며 추정하지 않는다. |

근거: 원본 L8–L13, L29–L36, L44–L62, L120, L153, L627, L743, L785–L805, L1277, L2020–L2021. 269·267/268 후속 계약은 공식 큐 revision 5106에 보존돼 있다.

## 7. 재개 시 첫 행동: 게임 중심 계획

2026-10-26 사용자 결정(A안): 파이썬 서버를 유지하고 게임 로직을 직접 만든다. L1J는 엔진으로 쓰지 않고 데이터·설계 참고로 쓴다. 데이터 우선순위는 클라이언트 내부 데이터 → 공개 공식 정보 → L1J(빈칸 채움, 출처 밝힌 로컬 정책)다. 다음 **“작업 재개”**에 Claude 한 세션이 아래 순서로 시작한다. 옛 Root/Test/기능 채팅은 이어 쓰지 않는다.

현재: 이동·칼 공격·NPC HP 감소·반격·처치·경험치·레벨업·장비 저장이 각각 다른 계보에서 통과했지만 대부분 시험 모양이다. 서버는 요청-응답 처리기이고 월드 틱·NPC AI·자연 회복이 없다(`npc.py` "HP, AI 없음", `npc_motion.py` "타이머·자율 AI 없음", `MAX_SPAWNS = 1`).

| 단계 | 할 일 |
| --- | --- |
| 0. 준비 (게임 실행 없음) | L1J 소스·데이터 확보(포크는 사용자 확인 후 받음), 클래식과의 몬스터·아이템·스프라이트 번호 대응 범위 확인. 기존 코드 중 제품 구조로 재사용할 것과 시험 모양이라 바꿀 것을 한 표로 정리. |
| 1. 게임 뼈대 | 월드 틱 루프(100~200ms)와 타이머, 엔티티 관리, 플레이어 근처 스폰 그룹만 활성화(활성·해제 반경, 재진입 시 마릿수 보충), 데이터 표 로딩(몬스터·스폰·드롭·경험치·아이템·공식), NPC AI 상태(대기·배회·선공·추적·공격·귀환), 공격·이동 속도 제한. 플레이어 행동은 틱을 기다리지 않고 즉시 처리. |
| 2. M1 사냥터 30분 | 초보 사냥터 한 곳: 근처 스폰, 배회·선공하는 몹, 실제 공속 칼 전투, HP·MP 자연 회복, 드롭과 줍기, 경험치·레벨업, 사망 후 마을 복귀, 저장·재접속. |
| 3. M2 마을 순환 | 전리품 판매, 물약·장비 구매, 물약 사용, 장비 교체. |
| 4. M3 성장 / M4 확장 | 마법서 학습과 MP 마법, 실제 지속시간 버프 / 사냥터·몬스터를 표에 줄 추가로 확장, 동료 등 동결 기능 재개. |

완료 판정: 마일스톤마다 원본 클라이언트로 30분 직접 플레이해 깨지는 곳이 없는지 본다. 사이사이 회귀는 패킷 봇이 사냥 루프를 자동으로 돌린다. 이 계획이 끝날 때까지 동결 기능(5장)은 재개하지 않는다. 워커 단위·지시문·검증·지표는 [WORK_RULES](WORK_RULES.md)를 따른다.
