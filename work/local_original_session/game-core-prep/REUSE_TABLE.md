# 게임 뼈대 준비: 기존 코드 재사용표

2026-10-26 현재 작업 트리와 기존 HANDOFF를 읽은 정적 판단이다. 게임·서버·시험은 실행하지 않았다. **패킷·소유권·저장 계약은 보존하고, 단일 시험 NPC 중심의 실행 구조는 월드·엔티티 구조로 바꾼다.** 여기서 교체는 해당 실행 구조의 교체이며 기존 codec·원본 분석·성공/실패 기록의 폐기가 아니다. 별도 후보의 scoped PASS를 현재 공통 서버나 M1 전체 성공으로 옮기지 않는다.

아래 파일명은 기본적으로 `tools/local_original_session/` 기준이다. `C/`는 `work/local_original_session/implementation-5/combat-adjudication/`, `S/`는 `work/local_original_session/implementation-3/skill-buff/`다. 줄 번호는 현재 읽은 파일 기준이다.

| 기능 영역 | 기존 코드 위치(파일:주요 함수) | 판정 | 이유 한 줄 |
| --- | --- | --- | --- |
| 접속·로그인·캐릭터 선택·월드 진입 | `broker.py:414` LocalRealm.grant, `:452` receive_login, `:473` select, `:386` _frames_for | 수정 후 재사용 | 실제 요청·목록 reference·선택 순서는 살리고, 고정 UID/이름·map0 월드 프로필(`:387`, `:430`)을 선택 캐릭터 데이터로 바꾼다. |
| 패킷 송수신(broker) | `broker.py:1301` PersistentBroker.start, `:1381` _accept, `:3874` _serve, `:3347` _send | 재사용(제품 구조로 동작) | 지속 연결·분할 수신·라우팅·write/drain·종료 수명은 이미 있으며, 새 월드 알림도 기존 잠금·송신 정책 안에 연결한다. |
| 이동 | `movement.py:267` MovementService.handle_CS4E2B, `:173` PositionStore.commit | 수정 후 재사용 | 서버 권한 좌표·통행 판정·보정·위치 CAS는 살리고, 게임 이동속도와 월드 충돌·다중 엔티티 연결을 더한다. |
| 대상 선택 | `attack.py:167` AttackTargets._current, `:322` authorize, `:332` revalidate | 수정 후 재사용 | 현재 선택·거리·동일 객체 재확인은 살리고, 고정 NPC 대신 월드 UID·세대·생존·가시 범위 조회로 연결한다. |
| 공격·피해 계산 | `attack_session.py:211` handle; `C/pve-accuracy-rng-v1/candidate/tools/local_original_session/combat_physical.py:156` resolve_pc_npc, `:207` resolve_npc_pc | 수정 후 재사용 | 공격 패킷·별도 명중/피해 후보는 살리고 고정 피해 입력(`npc_hp.py:68`)을 실제 스탯·데이터 표·공속에 연결한다. |
| NPC 표시·생성 | `npc.py:61` NpcSpawn, `:91` prepare; `broker.py:480` select의 NPC 배치 | 교체(시험 모양) | SPR56/template0·MAX_SPAWNS=1(`npc.py:4`, `:22`)의 명시 배치를 근처 스폰 그룹·UID 발급·활성/해제·재보충으로 바꾼다. |
| NPC 이동 | `npc_motion.py:83` NpcMotion.plan; `broker.py:2418` step_npc | 교체(시험 모양) | 외부 goal·direction·now_ns를 받아 한 걸음만 처리하므로 AI·추적·귀환을 새로 만들고 이동 wire·통행·drain 후 commit은 살린다. |
| NPC 반격 | `broker.py:2235` attack_player_once, `:2215` attack_player_repeated; `npc_player_hit.py:246` prepare_locked | 교체(시험 모양) | 명시 호출·damage1(`npc_player_hit.py:363`)을 AI의 선공·추적·사거리·실공속 공격으로 바꾸고 HP 알림은 살린다. |
| NPC 사망·경험치·레벨업 | `npc_death.py:120` prepare_death; `C/progression-owner-v1/progression_owner.py:339` award_kill_locked; `C/experience-progression-v2/experience_progression.py:105` solo_progression | 수정 후 재사용 | kill once·성장 저장/전송을 다수 NPC 사망·사체 정리·재스폰과 연결하고 고정 보상 입력을 표로 바꾼다. |
| 드롭·줍기·인벤토리 | `item_ground.py:226` _prepare; `item_transfer_session.py:348` handle; `inventory.py:881` _collection_items | 수정 후 재사용 | 패킷·custody CAS는 살리되 whole B 한 왕복·동일 타일·NPC 공존 금지·1~2개 제한을 일반 전리품 구조로 바꾼다(`item_ground.py:189`, `:220`, `:235`; `inventory.py:884`). |
| 장비 | `equipment_store.py:72` _state, `:157` compare_and_swap | 수정 후 재사용 | UID·revision·인벤토리 결속은 살리고 template1/weapon 제약(`:79`)을 아이템 표·슬롯·능력치 구조로 넓힌다. |
| 저장·재접속 | `movement.py:143` restore, `:173` commit; `inventory_store.py:401` _custody_atomic_write, `:483` commit_custody; `broker.py:774` close | 수정 후 재사용 | 원자 저장·preimage/CAS·실패 latch는 보존하되 캐릭터 자원·성장·위치·장비·전리품 수명을 연결한다. |
| 시간 처리(타이머·만료) | `launcher.py:4998` run_session 감시 루프; `S/item-timed-lifecycle-service-v1/lifecycle.py:332` lifecycle_locked | 수정 후 재사용 | 감시 poll은 게임 타이머가 아니며, 별도 실제 시계·만료 저장 후보를 새 스케줄러에 연결해야 한다. |

공격·성장 후보는 공통 `tools/` 통합 완료가 아니다. actual163 선택 조합은 `C/progression-level3-growth-packet-v2/source-inputs.json:3`에 연결되며, `C/HANDOFF.md:137`은 35회 distinct kill→EXP300/레벨3→성장 패킷 drain→새 접속 저장 일치의 제한된 성공을 기록한다. NPC 인계의 retained37+new1도 준비 Source/UNRUN이다(`work/local_original_session/implementation-2/npc-motion-goal/HANDOFF.md:71`). 둘 다 30분 플레이 성공이 아니다.

드롭의 새 접속 복원 후보도 동일 타일의 기존 DROPPED Q1에 한정된다(`work/local_original_session/implementation-1/item-equipment-product/drop-pickup/live/dropped-generation-recovery-ui-338-v1/API.md:23`). 장비 최신 인계 역시 actual250의 paid POST 읽기 복원 범위이며 거래 직후 능력치 publication은 미완이다(`work/local_original_session/equipment-window/API.md:1`). 두 결과를 일반 전리품·장비 완료로 합치지 않는다.

월드 틱을 붙일 자리와 걸림돌

**설계 제안:** `PersistentBroker.start()`가 얻는 기존 asyncio 루프(`broker.py:1303`)에 월드 소유 task 하나를 붙인다. 100~200ms 틱에서 엔티티·근처 스폰·NPC AI·회복·만료를 진행하고, 플레이어 요청은 기존 `_serve → game.received`에서 즉시 처리한다(`broker.py:3921`, `:3965`). 무수신 timeout은 소유권·부분 패킷 확인만 하므로(`:3897–3910`) 이를 틱으로 삼으면 연결별 중복 실행과 입력 빈도 의존을 피하기 어렵다. `launcher.py:1035`의 NativeOwner.tick도 Job 생존 확인이다.

월드 상태는 writer별 표시 상태와 분리해야 한다. 현재 NPC·이동 객체는 선택 때 만들어지고(`broker.py:488–494`) 연결 종료 때 제거된다(`:799–806`). 월드 엔티티가 수명을 소유하고 세션은 관측·조작 권한을 갖도록 바꿔야 근처 스폰 해제·재진입·재접속을 처리할 수 있다. 단독 게임에서 어떤 NPC 상태까지 재접속에 보존할지는 아직 정책 선택이다.

월드 알림은 현재 row의 `operation_lock`과 `_send`를 통과시킨다(`broker.py:1393`, `:2178`). AI에서 기존 잠금 획득 API를 호출하면서 같은 잠금을 다시 잡지 않도록 호출 경계를 정한다. `_TransportPolicy`의 opcode·크기·단계·rate·drain 규약(`broker.py:177–224`)과 단일 NPC wire 검증(`:3562–3566`)을 새 엔티티에 맞춰 확장한다. 패킷 rate 제한은 캐릭터 공속·이속 판정을 대신하지 않는다. 종료는 새 행동 발행 중단→진행 중 저장/송신 마감→월드 task 회수→기존 세션 정리로 연결한다(`:4025–4088`).

HP·MP 자연 회복은 새 게임 로직이 필요하다. `hp_status.py:1–5`는 명시 HP 표시이며 타이머·저장이 없다. 회복 주기·양·행동 상태·RESOURCE 저장을 연결해야 한다. 사망 복귀도 `player_life.py:27–33`의 HP1→동일 좌표 최대 HP 시험 정책을 교체하고, 검증된 사망/복귀 패킷 순서·newlife token을 살려 마을 좌표 저장과 반복 사망에 연결한다.

만료 후보를 곧바로 동작 완료로 보지 않는다. `work/local_original_session/consumables/timed267-world-first-recovery-contact-v1/API.md:3–13`은 실제267/268의 WORLD 복원 실패와 후속 만료·fresh 미실행을 남긴다. 몬스터·스폰·드롭·경험치·아이템·속도 표를 공급하는 층은 새로 필요하며, 값은 클라이언트 자료→공식 정보→출처 있는 L1J 로컬 정책 순으로 채운다. 미확인 공식·속도는 추측으로 확정하지 않는다.

꼭 보존할 계약

- KEY/VERSION/COUNTS의 보존 자원·signed pack 인증·슬롯 소비/폐기, 전용 loopback 포트와 소유 프로세스 결속(`README.md:49`, `broker.py:1305–1313`).
- C2S header10·cipher mode별 길이/패딩(`tools/local_entry_server/codecs.py:88–114`), S2C 길이·opcode·본문·끝 2바이트, 4E28 선택→4E29→4E95 map→4E38 SelfInfo→4E96 Actor 순서와 필드 번호(`broker.py:386–397`, `:473–496`).
- 이동/공격/HP·사망·제거/인벤토리의 기존 opcode·DTO·필드 존재 여부·raw 값. 예를 들어 드롭/줍기 4E3F/4E3E와 0978(`item_transfer_protocol.py:39`), 사망 뒤 원 4EEC 요청·4EED·4F16의 순서와 새 수명 결속(`player_life.py:27–33`).
- 서버 발급 UID·UIDburn·current/selection·소유권·generation·kill/보상 once, preimage/revision CAS와 실패 partial 보존. write 시도·drain·실제 native 소비·저장 완료를 구별하며 결과 불명 시 재지급하거나 되감지 않는다(`inventory_store.py:401–488`, `C/progression-owner-v1/progression_owner.py:339`).
- 실제 server clock과 정상 300/1800초·시험 10초의 구분, 기존 finally/FIRSTclose·정리·성공/실패 원문. 만료·새 접속 미확인을 PASS로 바꾸지 않는다(`docs/WORK_RULES.md:43`, `broker.py:4057–4088`).
