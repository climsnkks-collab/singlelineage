# 원본 클라이언트·로컬 서버와 전면 소스 재조립 비교

작성일: 2026-10-16 KST. 기존 분석·소스 해석·보존된 실제 실행 기록만 비교했다. 이번 조사는 게임·서버·native·REA 분석을 새로 실행하지 않았다.

후속 사용자 결정: **원본 기반 클라이언트+로컬 서버를 주력으로 확정**했다. 반복 기동·월드 진입·실제 이동 순서의 [현행 계획](IMPLEMENTATION_COMPLETION_PLAN.md)을 적용한다. 이번 후속 요청은 계획 개정이며 구현·실행 재개는 아니다.

## 판단

**현재 증거에서는 원본 기반 클라이언트+로컬 서버를 주력 후보로 삼는 편이 더 빠르고, 원본 화면·입력·프레임 동작을 보존할 확실성이 높다.** 기존 패치·hook·bridge를 포함한 클라이언트가 로컬 응답을 받아 마을·캐릭터·HUD를 실제 표시한 CP69 근거가 있다. 반면 전면 소스 재조립은 초기화·링크·수명 연결부터 열려 있다. 이는 전체 제품 완료나 기간 보장이 아니다.

여기서 원본 기반 클라이언트는 무수정 원본에 서버만 붙인 상태를 뜻하지 않는다. CP69 실행 후보 SHA는 `656a64e7…`로 원본 CONTROL `9ffc24fe…`와 다르다. 추천 경로도 기존 성공 후보의 패치·bridge와 기동·수명·서버 통합을 승계·검증해야 하며, 경로 이름 `current-unmodified-clone`은 실행 당시 바이트 무수정의 증거가 아니다.

REA는 필요한 통신·초기화·객체 수명 경계를 복원하는 도구로 계속 유효하다. 전면 소스 재조립 산출물은 보존된 대안이다. 아래 비교는 조사 당시 판단 근거이며, 이후 사용자가 위 권고 노선을 채택해 AGENTS·구현 계획에 반영했다. 노선 확정과 실제 구현·실행 재개는 구분한다.

통신은 전부 미지인 상태가 아니다. 로그인·캐릭터 생성/선택·월드 진입에 실제 작동한 흐름이 있다. 다만 메시지 이름/형식 확인, consumer 연결 확인, 원본에서의 동작 확인은 각각 다른 증거이며 전체 프로토콜 분모가 없으므로 완료율을 산출하지 않는다.

## 복원 범위와 남은 일

| 경로 | 확보된 근거 | 남은 일·분류 |
|---|---|---|
| 1. transport | disabled framing의 실제 원본 흐름. 기존 frame/protobuf 처리 재사용 가능 | enabled C2S 8B chained XOR seed·S2C RC4 계열 초기 permutation 미검증. 작동하는 disabled 경로에 자동으로 필수 blocker가 되는 것은 아님 |
| 2. 기동·로그인 | 패치·bridge가 포함된 새 원본 기반 프로세스, KEY→VERSION `4E34`→COUNTS `4F3D`, guest `0263/0264`, NUM `4E21`/INFO `4E22`, readnews `0267` 흐름 | 독립 반복 기동·지속 세션·오류 복구 검증. 공식 프로그램 없는 clean environment 검증은 미완료 |
| 3. 생성 | `4E24/4E25`, 필수1..9/선택10..12와 로컬 stats. 실제 create→ACK→NUM→INFO 및 store_created 기록 | 다른 허용 입력·실패/중복·재기동의 제품 경로 확인. 공식 서버 원래 수치와 동일해야 한다는 요구는 없음 |
| 4. 선택 | `4E28/4E29`, 동일 writer의 owned route·선택·store 연결과 실제 Land 진입 | 전체 실패·재선택·다중 캐릭터·수명 경로를 제품 요구에 맞춰 검증 |
| 5. 월드·상태 | Self `4E38` 26필드/필수18, Map `4E95` 10/필수4, Actor `4E96` 65/필수26의 번호·폭·presence. UID→MyPlayer·Map/tile 소비. ACK→Map→Self→Actor로 CP69 실제 마을·HUD | 다른 맵/직업·자원 key·필수 미명명 필드 소비 확장. optional nested44/51·enum48/67, Self19/26은 현재 primitive 경로에서 생략 가능하며 전부 선행 복원할 이유는 없음 |
| 6. 이동 | CS `4E2B`: 시작 packed-grid u32·방향 i32, UID 없음. SC `4E2C`: Actor UID·좌표·방향. 방향0..7 delta·원본 command/Navigation/MovingAction 경로 | 실제 정상 입력→송신→서버 commit 미검증. CP76 owner/retained handle 결합·sender ABI·5초 witness·actual decoder/dispatcher는 통합/시험 도구 blocker. SC 좌표 별도 event·거절/보정·연속 이동은 의미 조사 필요 |
| 7. 전투·HP·죽음 | SC_ATTACK 선택 selector/공격자/대상/raw 필드→Action 소비. `4E38` HP10/11→상태 복사. `4EC8` 3필드 형식. Death/Damaged frame·queue·corpse 소비 분석 | 공격 요청/전체 dispatch·NPC HP setter·lethal wire→죽음/제거/복구 연결 미완결. action 분석·합성 fixture는 원본 wire gameplay 실증이 아님 |
| 8. 아이템·장비 | Inventory callback→ItemEntity ID/template/수량형 필드, 장비 map·Inventory 연계 set. 정상 온라인 item6종·장비 map 표본 | 획득/사용/착용/해제 요청·응답의 전체 DTO·슬롯 의미·실제 roundtrip 연결 조사. RAM 값 관찰만으로 규약 완료 아님 |
| 9. 스킬·버프 | Spell key tree·상태 필드, BuffInstance kind/timer/deadline 소비. 정상 온라인 Buff 표본 | 시전/학습·level/cooldown·갱신 wire·기간 단위 조사 및 서버 구현. 공개 L1J 정책은 현행 공식 서버 수식의 복원 증거가 아님 |
| 10. NPC | Actor f3 SPR key와 Monster 한정 f39 NPC template 소비, 원본 NPC/Actor 관찰 | appearance 도출 정책·다른 subtype·상태 전이. `4EC8` 필드를 근거 없이 NPC UID/HP로 명명할 수 없음 |
| 11. 삭제 | `4E27` anchor 자료 존재 | 원본 client→server→목록/저장 반영의 삭제 end-to-end 근거 없음. 선택 범위 구현·실증 필요 |
| 12. 저장 | 로컬 캐릭터 생성·선택 store와 보존 자료 존재 | 권한 있는 이동·HP/MP·아이템·장비·스킬·시계/진행 상태의 일관된 저장·cold restart 복구는 양 경로 공통 과제 |

필수 미명명 필드에 명시한 로컬 값이 특정 실행에서 받아들여졌다는 근거는 있다. 이를 모든 맵·상태에 안전한 0으로 일반화할 수는 없다. 공식 숫자와 같을 필요는 없지만, type/presence·UID 일치·자원 key·순서·실제 소비 조건은 지켜야 한다.

특히 자기 `SC4E2C`를 무조건 ACK로 반사하면 안 된다. 확인된 경로에서는 기존 Transform을 기준으로 또 한 칸을 실행하고 `CS4E2B`를 재송신할 수 있다. 현재 1회 로컬 권한 모델은 자기 echo를 보내지 않지만, 이것만으로 연속 이동·거절·보정 규약이 닫힌 것은 아니다.

## 두 경로의 잔여 비용

| 항목 | 원본 클라이언트+로컬 서버 | 전면 소스 재조립 |
|---|---|---|
| 이미 도달한 지점 | 기존 패치·bridge가 포함된 새 원본 기반 프로세스에서 로컬 월드·마을·캐릭터·HUD 표시 | Front CPP353+C25의 compile-only 집합, selected source784. runtime-ready=false |
| frontend 잔여 | 초기화 분리·정상 입력·세션 수명·필요한 wire 응답과 실제 consumer 연결 | AppDelegate ctor CDA20/init D0040 전체 경로·전역/ABI/allocator/EH·간접 호출·자원/객체 수명·렌더/해제 연결 |
| 현재 실패의 뜻 | CP76은 통신 schema 미상만의 문제가 아니라 실행/관찰 adapter 미연결이 큼 | frozen343+3+35 마지막 링크는 unresolved180/DLL0. 별 Root62/Main3/Main5를 합산해 실행 가능한 제품으로 표시할 수 없음 |
| 동작 충실도 | 보존된 원본 renderer·입력·action/frame 구현을 직접 사용하므로 유리. 실제 선택 경로 검증은 필요 | 원문 조각 보존·컴파일을 넘어 모든 관련 동작·수명을 대조해야 함 |
| 공통 비용 | backend 게임 규칙·NPC AI/전투/아이템/스킬·권한 상태·저장·복구 | 같은 backend 기능이 필요하며 frontend 복원 비용이 추가됨 |

REA 이전 자체 Win32/GDI 앱 211개 파일 폐기는 원본 클라이언트 clone·통신 prototype의 폐기를 뜻하지 않는다. 폐기 앱의 사냥 PASS와 공개 서버 정책 테스트를 원본 wire 실증으로 합산하거나, 그 앱을 새 제품 기반으로 되살리지 않는다.

## 처음 재개할 때의 권고

1. 기존 성공 단일 후보의 패치·bridge·서버 통합을 승계해 새 프로세스의 독립 반복 기동, 캐릭터/월드 진입, 지속 lifetime와 종료·복구를 먼저 확인한다. 과거 official-closed metadata를 읽는 도구 admission과 게임 코드의 실제 의존을 구분한다.
2. 정상 사용자 입력→원래 송신 경로를 우선 연결하고 실제 `CS4E2B`, server commit, client prediction/완료, 표시를 따로 기록한다. bespoke 외부 sender 복원 자체가 필수 제품 요구인지는 재평가한다. 거절·보정·연속 이동을 닫은 뒤 지속 플레이로 넓힌다.
3. NPC→전투/HP/죽음→아이템/장비→스킬의 선택 경로별 필요한 메시지와 소비자를 확장하고 저장·cold restart를 함께 확인한다. 전체 wire 목록 완성을 선행 조건으로 삼지 않는다.

이 순서는 재개 시의 권고이며 현재 실행 지시가 아니다. 새 승인 절차·하네스·독립 검토 계층을 만드는 제안도 아니다.

## 판단이 바뀌는 조건

- 원본이 현재 살아 있는 SDK/공식 프로세스에 실제 의존한다는 연결이 확인되고, 그 제거 비용이 보존된 재조립의 남은 비용보다 커지는 경우.
- 필요한 client↔server 규약의 필수 분기가 반복해서 막히거나, 정상 입력·상태 수명을 안전하게 유지할 수 없다는 구체적 증거가 생기는 경우.
- 재조립 쪽에서 원본 초기화→첫 프레임→입력→해제의 실제 독립 실행이 먼저 연결되고, 이후 확장 비용이 더 작다는 실측 근거가 생기는 경우.

현재는 공식 선행 실행이 매번 필수라는 확정 근거가 없다. CP69는 기존 패치·bridge가 포함된 일반 권한의 새 프로세스이며, 실행 도구는 PURPLE 부재를 검사했다. gate의 과거 공식 종료 metadata·SDK hash/materialized67 검사는 도구 admission이며 게임에 그 상태를 주입했다는 연결은 없다. 다만 모든 공식 runtime·잔류 cache가 없는 clean environment에서의 검증도 아직 없으므로 완전 무의존을 확정하지 않는다.

후속 빈 WGC 역시 원본 렌더 실패로 확정하지 않는다. CP69/71의 보이는 월드는 보존하고, CP73~75 빈 프레임 및 WGC 자기 시험 실패는 캡처/표시 환경 문제와 제품 문제를 분리할 근거로 사용한다.

## 결정적 근거 위치

1. [CP69 화면 판정](C:/Users/Chansol/Documents/ChatGPT/싱글리니지/work/local_native_login_image_alt_diag_runtime/root-visual-review.json:3): 마을·캐릭터·HUD; movement/sustained/independent boot 주장은 false. 같은 폴더 `root-trial-result.json`·`runtime-summary.json`은 후보656a64e7…와 새 PID16584·일반 권한·60초 관찰 종료의 근거다.
2. [새 프로세스 생성](C:/Users/Chansol/Documents/ChatGPT/싱글리니지/tools/clone_observer/windows.py:219), [PURPLE 부재 검사](C:/Users/Chansol/Documents/ChatGPT/싱글리니지/tools/local_ready_entry_trial/run.py:20), [도구 admission](C:/Users/Chansol/Documents/ChatGPT/싱글리니지/tools/local_ready_entry_gate/gate.py:34).
3. [transport 계약](C:/Users/Chansol/Documents/ChatGPT/싱글리니지/tools/local_entry_server/contract.json:43): disabled와 enabled의 근거 범위를 구분한다.
4. [실제 writer route·생성/선택/store 연결](C:/Users/Chansol/Documents/ChatGPT/싱글리니지/tools/local_native_login_local_ack_hook/ack_enter_world.py:115), [생성 필수/선택 필드](C:/Users/Chansol/Documents/ChatGPT/싱글리니지/tools/local_character_creation/realm.py:79), [실제 생성 패킷 metadata](C:/Users/Chansol/Documents/ChatGPT/싱글리니지/work/local_native_login_create_submit_runtime/broker/packet-metadata.jsonl:42).
5. [월드 opcode·필수성·소비](C:/Users/Chansol/Documents/ChatGPT/싱글리니지/work/online_world_packet_source/README.md:9), [미확정 optional의 범위](C:/Users/Chansol/Documents/ChatGPT/싱글리니지/tools/local_world_protocol/README.md:19).
6. [이동 자기 echo·prediction](C:/Users/Chansol/Documents/ChatGPT/싱글리니지/work/local_move_action_followup/contract.json:416), [CP76 통합 blocker](C:/Users/Chansol/Documents/ChatGPT/싱글리니지/tools/local_native_login_one_move_runtime/README.md:5).
7. [공격·NPC 선택 소비](C:/Users/Chansol/Documents/ChatGPT/싱글리니지/tools/source_npc_binding/README.md:15), [HP opcode·선택 decoder 한계](C:/Users/Chansol/Documents/ChatGPT/싱글리니지/tools/source_hp_network/README.md:5).
8. [죽음 presentation와 로컬 정책 경계](C:/Users/Chansol/Documents/ChatGPT/싱글리니지/tools/source_death_hit_phase_20261010/README.md:58).
9. [Inventory/Spell 실제 소비 source](C:/Users/Chansol/Documents/ChatGPT/싱글리니지/work/online_inventory_skill_source/review.md:17), [장비/Buff 소비 source](C:/Users/Chansol/Documents/ChatGPT/싱글리니지/work/online_equipment_buff_source/review.md:13).
10. [정상 온라인 item 표본](C:/Users/Chansol/Documents/ChatGPT/싱글리니지/work/online_public_session-v4/root-memory-proof.json:233), [장비/Buff 표본·미확정](C:/Users/Chansol/Documents/ChatGPT/싱글리니지/work/online_public_session-v5/root-memory-proof.json:343).
11. [서버 정책과 현행 공식 수식의 구별](C:/Users/Chansol/Documents/ChatGPT/싱글리니지/tools/source_single_skills_20261010/v2/CONTRACT.md:3): 공개 정책·합성 검증을 원본 통신 실증으로 확대하지 않는다.
12. [Front378 실제 범위](C:/Users/Chansol/Documents/ChatGPT/싱글리니지/work/rea_lineage_resume_20261013/integration/root/FRONT91_LOGICAL378_FINAL_ROOT_COMPILE_ONLY_ADMISSION_EXPLICIT_MAIN_B4_SERIAL_RETURN.json:160), [마지막 DLL 링크 기록](C:/Users/Chansol/Documents/ChatGPT/싱글리니지/work/rea_lineage_resume_20261013/integration/root/HANDOFF_CHECKPOINT_V83_MAIN5_STATIC_CLOSED_FRONT198_CODE15_CALLER.json:60), [현재 초기화 선언](D:/CodexArtifacts/single-lineage-rea-resume-20261013/frontend/platform/coherent-source-v10-core98-r59-p73-p70-overlay-source-only-v1/source/frontend/platform/original_application.hpp:36): compile-only, unresolved180/DLL0, 원본 AppDelegate 정상·실패 본문과 통합은 별도 미완결이다. [재조립 검토](REASSEMBLY_STRATEGY_REVIEW_20261015.md)의 원본·REA 보존 경계와 최신 중지·재개 지시는 유지한다.
