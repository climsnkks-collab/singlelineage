# COMPANION-MAGE basic combat caller v3

**WRITER_RELEASED** / component_source_ready:true / source_ready:false / test_ready:false / gameplay RUN unavailable / packet/runtime UNRUN / effective **PASSIVE**. Attack magic DEFERRED.

실제 COMBAT callee source/issued admission/result API가 아직 없다. 본 결과는 동료 쪽 event caller와 Host 후보 변경이며 실제 기본 공격 완료나 실행 가능한 전체 선정판이 아니다. 첫 blocker는 `COMPANION_BASIC_ATTACKER_BINDING_UNAVAILABLE`다.

`companion_combat_caller.py`는 v2 assist_locked/defend_locked typed API에 실제 객체를 그대로 전달하도록 구현했다. ASSIST는 원 owner AttackSession의 새 accepted_count+1/current AttackIntent와 원 feedback DRAINED를 확인한다. DEFEND는 원 npc_player_hit.Result의 source/current operation validator와 실제 before>after>0 owner HP만 받는다. 실제 controller/actor UID·identity generation·companion lease·direct owner 및 기존 SharedSupport.current의 현재 LOCAL pose/resource 경계를 사용한다. COMBAT가 별도 allied target/physical gear·resource·stats/range/cadence/RNG/send/한 NPC HP/death commit을 소유해야 하며 caller는 이를 만들어 내거나 selected-player Position으로 대체하지 않는다.

실제 event 객체를 callee await 전에 같은 selected state에 기억하여 실패/UNKNOWN의 동일 event 재시도를 막는다. 새 target queue/idle poll/타이머/HP polling/handler 직접 호출/가짜 packet 또는 receipt는 없다. Opaque callee 반환은 CALLEE_RETURNED_UNCLASSIFIED이며 성공으로 판정하지 않는다. 미래 실제 issued result validator가 필요하다.

`companion_host.py`는 v1 Host 후손이다. 기존 view/command/spawn/motion/support/kill/retirement 메서드는 AST 동일이며, init의 owner=None caller·selected state의 두 event reference·두 async callback만 추가했다. v1 preferences/CAS와 UI effective PASSIVE 및 비활성 ASSIST/DEFEND/distance는 그대로다. 이 Host는 source-selected graph에 설치되지 않았다. client/command/runtime setter가 callee를 공급할 수 없다.

`broker.event-edges.diff`는 pins의 정확한 역사적 Broker 부모에 대한 **미선정 후보**다. 실제 Broker를 수정하지 않았다. ASSIST는 real4E30 전 count capture → original handler → original send/drain/peer completion 뒤 같은 row callback이다. DEFEND는 실제 positive COMMITTED result를 원 hit UNKNOWN catch 바깥·같은 row에서 전달하여 뒤 companion 실패가 이미 commit된 원 피해를 UNKNOWN으로 바꾸지 않게 한다. zero/miss와 lethal 결과의 원 return은 그대로다. 현재 selected Broker/peer/cap/Host 후손에 실제로 연결하고 일관되게 고정하는 작업은 COMBAT/root 소유이며 완료로 주장하지 않는다.

`SOURCE_API.md`의 exact19 input fullSHA와 v2 signature/등록·LOCAL pose·canonical resource/실제 같은 캐릭터 DerivedStats 계약을 COMBAT에 전달할 수 있다. 동료 physical reach/cadence와 allied killcredit source는 아직 미선정이다. 기존 stats source는 실제 class3 level1+known gear만 지원하며 absent/unknown을 거절한다. historical input pin은 현재 cohort 선정 증명이 아니다.

`trial-scenario.json`는 기존 packet-test-client-v5 normal_session/ready_current → 실제F101 summon/4E96 → 원 settings transport → PASSIVE/real4E30 ASSIST/positive owner-hit DEFEND → concrete callee result/원 저장·strictclose 순서를 고정했다. callee/fullSHA/result API, 실제 Broker/cohort/loader, source-backed settings transport, physical range/cadence/killcredit 및 DEFEND hostile scenario 입력이 부족하여 전체 정상 packet caller를 실행할 수 없다. 존재하지 않는 설정·피격 opcode를 만들거나 Host/handler를 Test에서 직접 호출하지 않았다.

조건부 명령만 실행 가능: `powershell -NoProfile -File "C:\Users\Chansol\Documents\ChatGPT\싱글리니지\work\local_original_session\implementation-companion\local-companion-combat-caller-v3\RUN_COMMAND.ps1" -Preflight`.
이 명령은19 pins를 읽고 첫 blocker와 null callee pins를 출력한 뒤 **expected exit2**로 끝나는 preflight다. gameplay RUN이나 Test PASS가 아니다. 실제 preflight도 packets0/runtimeUNRUN/exit2를 확인했다. 새 gameplay caller/RUN은 COMBAT source와 위 실제 입력이 준비된 후 같은 시나리오를 완결해야 한다.

검증: `python -B "C:\Users\Chansol\Documents\ChatGPT\싱글리니지\work\local_original_session\implementation-companion\local-companion-combat-caller-v3\verify.py"` **36 checks PASS**. 19 exact source pins, Host exact diff/기존 AST 보존, caller/Host/preflight compile, Broker candidate exact-context 재구성/compile/변경 두 메서드와 event 순서, owner=None의 실제 async 메서드가 host/event 읽기 전에 BLOCKED로 끝나는 경계만 확인했다. PowerShell Parser errors0. 실제 양의 event/callee dispatch·packet·game·UI·저장·피격/공격/HP는 UNRUN이며 성공으로 확대하지 않는다. 검증 sentinel은 무권위 pre-read 거절 검사용이며 actor/HP/receipt를 모사하지 않는다.

모든 쓰기는 새 v3 경로 내부뿐이다. original/common/COMBAT/Test client/API/JSON queue/ACTIVE/기존 v1·v2와 원 actual 결과·UIDburn·복사본은 변경하지 않았다. game/server/포트/Store 복사·열기/focus/branch/worktree/commit 작업0. writer/runtime 자원0/released. Main이 실제 delta 검토 후 수용/큐 등록한다.
