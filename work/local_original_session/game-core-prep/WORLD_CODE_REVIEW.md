# 월드 코드 버그 리뷰

2026-10-26 현재 `main`의 미커밋 작업 트리 기준. 지정한 10개 모듈을 읽고 실제 호출부와 기존 계약을 대조했다. 동시 수정 중인 파일의 아래 줄 번호는 검토 종료 시 다시 확인했다. 제품 코드 수정·커밋·게임·서버·포트 실행은 하지 않았다.

**결함 4건: P1 1건, P2 2건, P3 1건. 별도로 퇴장 수명 위험 1건은 실행 영향이 추론이다.** 아래 재현은 메모리 상태와 fake clock을 사용하는 순수 모듈 직접 호출이다. 실제 원본 화면·정상 패킷·영속 저장 왕복의 정식 PASS는 아니다. 코드 사실과 그로부터 예상되는 실제 실행 영향은 구별해 적었다.

## 1. [P1] PC 칼 공격이 차폐 판정 없이 피해를 적용한다

- **위치·근거:** `tools/local_original_session/world_visibility.py:486–490`은 생존·맵·근접 거리만 검사하고 바로 `WorldCombat.try_pc_swing()`을 호출한다. 이 함수도 `world_combat.py:414–421`에서 시간·수치만 처리한다. 반대 방향은 `npc_ai.py:199–221,231–235`에서 LOS를 확인한다. PC 공격 경로에는 동등한 차폐 판정이 없다.
- **재현 조건·관측:** PC `(100,100)`, NPC `(101,100)`, NPC HP 10000, `PcProfile(20,1,0,13,13,weapon=ATHAME)`, RNG `Random(7)`로 구성한다. 제공 지형의 `can_step()`을 `False` 및 `None`으로 각각 두면 기존 AI의 `_line_clear()`는 두 경우 모두 `False`다. 그런데 `pc_attack()`은 두 경우 모두 NPC HP를 **10000→9995**로 줄이고 공격 프레임 1개, 다음 공격 시각 **100.917**을 만든다.
- **영향:** PC의 실제 공격 요청이 차폐 여부를 전혀 소비하지 않는다. 차단·미확인 경로에서도 피해·처치·보상으로 이어질 수 있다. 이 재현은 로컬 지형 입력의 거절과 PC 판정의 불일치를 입증하며, 원본의 특정 벽·문 좌표에서 발생한 화면 관측은 아니다.
- **기존 계약:** [GAME_CORE_DESIGN.md](GAME_CORE_DESIGN.md) 2쪽의 combat 책임과 [COMBAT_COMPLETION_PLAN.md](../implementation-5/combat-adjudication/COMBAT_COMPLETION_PLAN.md) `:23,35–39`는 양방향 차폐와 BLOCKED/UNKNOWN 피해 금지를 요구한다. 같은 계획 `:37`에 따라 이동 불가 비트를 곧바로 원본 투사체 차폐 의미로 확정해서는 안 된다.
- **최소 수정안:** `try_pc_swing()` 전 현재 공격자·대상·맵의 기존 차폐 판정 결과를 소비하고 BLOCKED/UNKNOWN이면 피해 경로에 진입하지 않는다. 기존 [current-projectile-visibility/API.md](../shared-api/current-projectile-visibility/API.md)의 입력·미확인 계약을 재사용한다. NPC용 로컬 static-edge 판정만 연결한 경우에도 동적 문·원본 LOS까지 완료했다고 표시하지 않는다.

## 2. [P2] 줍기 저장 중 만료되면 인벤토리만 변경되고 소비·응답이 실패한다

- **위치·근거:** `world_visibility.py:285`가 현재 시각으로 줍기를 검사하고 `:288`에서 `commit()`한 뒤, `:289`에서 다시 시각을 읽는 `ground.pickup()`을 호출한다. `world_ground_items.py:228,238,248–249`는 두 번째 시각이 만료 이후면 예외를 낸다. 실제 소비자의 `broker.py:4350–4357,4391–4394`는 callback 안에서 `replace_kit()` 저장과 현재 인벤토리 교체를 완료한다. `broker.py:4415–4419`는 이후 ValueError를 줍기 거절로 처리해 인벤토리 응답을 보내지 않는다.
- **재현 조건·관측:** 수량 10인 바닥 아이템을 `expires_at−0.01`에 줍는다. 첫 검증 후 callback에서 저장 수량을 10 증가시키고 시계를 `expires_at+0.01`로 진행한다. 결과는 **`GROUND_ITEM_EXPIRED`, callback 완료 수량 10, 바닥 잔여 수량 10**이다. callback 반환 응답도 호출자에게 도달하지 않는다.
- **영향:** 실제 저장이 만료 경계를 넘길 만큼 걸리면 영속 인벤토리는 증가했지만 클라이언트에는 해당 변경이 전달되지 않고 바닥은 다음 만료 정리까지 남는다. 실제 디스크 저장의 시간 경계 재현은 하지 않았으며, 위 영속 저장 경로 연결은 정적 확인이다. 만료 이후 같은 아이템을 다시 주울 수 있다는 주장은 하지 않는다.
- **최소 수정안:** 같은 직렬화 요청에서 승인 시각 `now`를 한 번 확보하고 `check_pickup(..., now=now)`와 저장 후 `pickup(..., now=now)`에 동일하게 넘긴다. 기존 동기 world lock·현재 참조·수량·소유권 검사는 유지한다.

## 3. [P2] 지연된 회복 틱이 다음 회복 간격을 1초보다 짧게 만든다

- **위치·근거:** `world_visibility.py:362–370`, 특히 `max(due + tick, now)`는 예정 시각이 크게 지난 경우 다음 예약을 **현재 시각 자체**로 만든다. `world_scheduler.py:90–104`는 callback에서 추가한 due 작업을 다음 호출까지 미루므로, 다음 월드 틱에 곧바로 다시 실행된다.
- **재현 조건·관측:** 회복 주기 1초, 최초 due=1.0에서 시각을 10.0으로 늦춰 `run_due()`를 실행한다. 다음 deadline은 **10.0**이다. 다음 월드 틱 10.15에서도 회복 함수가 호출되어 호출 시각은 **`[10.0, 10.15]`**, 이후 deadline은 11.0이 된다.
- **영향:** 지연 직후 150ms 만에 회복 점수가 한 번 더 누적되어 자연 HP/MP 회복이 빨라진다. 틱 횟수로 누락 회복을 따라잡지 않는다는 현재 설계와 다르다. 순수 재현은 실제 `regen_tick` 대신 호출 기록 callback을 사용해 예약 간격을 확인했다.
- **최소 수정안:** 처리한 실제 시각을 기준으로 다음 예약을 `now + tick`으로 계산한다. 오래된 `due`에서 즉시 재실행할 예약을 만들지 않는다.

## 4. [추론] 선택 종료한 PC의 공간 점유와 generation이 남는다

- **위치·근거:** `world_visibility.py:334–349`의 `leave_pc()`는 선택·시야·전투 상태만 제거하며 registry PC를 비활성화하지 않는다. `npc_ai.py:329–337`은 registry의 살아 있는 PC를 이동 점유자로 보고, `world_interest_spawn.py:168–170`은 죽은 객체까지 포함한 점유를 검사한다. `world_entities.py:119–126`에서 기존 PC ref도 계속 resolve된다. `broker.py:4429–4439`의 실제 퇴장 호출부에는 별도 registry 정리가 없다.
- **재현 조건·관측:** PC를 `(100,100)`에 등록하고 ref를 보관한 뒤 `leave_pc(1)`을 실행한다. 결과는 **selected=False, alive=True, old_ref_current=True**다. `(99,100)`의 NPC가 오른쪽으로 이동하려 하면 `can_step=True`여도 **can_move=False**, 스폰 점유는 **True**다.
- **영향·미확정:** 위 API 상태는 직접 확인했지만 **현재 단일 gameplay owner에서의 실제 이동·스폰 장애는 미확인**이다. 유일한 PC가 나가면 그룹은 휴면하고, 같은 profile UID로 재입장하면 `update_pc()`가 스폰 전에 위치를 옮기므로 이 경로에서는 유령 점유가 플레이를 막는다고 확정할 수 없다. 퇴장 뒤 다른 UID가 월드를 활성화하거나 옛 ref를 소비하는 경로가 있으면 장애·stale 참조 승인이 발생한다는 것은 **추론**이다. 실행 영향이 확인된 위·아래 결함 4건과 구별한다.
- **최소 수정안:** 퇴장 때 PC의 활성 생명·generation과 공간 점유를 함께 종료하고, 재선택 때 보존된 profile UID를 새 generation으로 활성화한다. 점유 검사에서 비활성 PC도 제외해야 한다. 단순 `remove()` 후 기존 `add(uid=...)`만 호출하면 `world_entities.py:108–109`의 UID 재사용 금지에 걸리므로 재입장 경계까지 함께 연결한다. UIDburn 자체는 유지한다.

## 5. [P3] 제거된 시체의 드롭 once 표식이 영구 누적된다

- **위치·근거:** `world_ground_items.py:112,157–158,217`은 성공한 시체 ref를 `_spawned`에 보관하지만 제거 경로가 없다. `:258–274`의 완전 줍기·만료·`close()`도 이 집합을 정리하지 않는다. 이미 제거된 시체는 `:154–156`에서 먼저 거절되므로 그 ref의 once 표식을 계속 보관할 필요가 없다.
- **재현 조건·관측:** 같은 관리자에서 새 NPC 생성→사망→드롭 1개→완전 줍기→시체 제거를 10회 반복하고 601초의 scheduler 처리와 `close()`까지 실행했다. **활성 엔티티 1(PC), 바닥 아이템 0, 예약 0**인데 `_spawned`에는 **resolve 불가능한 시체 ref 10개**가 남았다.
- **영향:** 같은 월드 프로세스의 사냥 횟수에 비례해 불필요한 참조가 선형 누적된다. 즉시 큰 메모리 장애를 확인한 것은 아니다. UID 재사용 방지를 위해 보존하는 registry의 `_used`와는 별개다.
- **최소 수정안:** 시체가 registry에서 제거된 뒤 해당 once 표식을 해제하거나 다음 드롭 처리 때 이미 resolve 불가능한 표식을 정리하고, `close()`에서도 집합을 비운다. 아직 현재 시체로 등록된 ref의 중복 지급 금지는 유지한다.

## 검토·실행 범위

`world_entities.py`, `world_scheduler.py`, `world_runtime.py`, `world_interest_spawn.py`, `world_visibility.py`, `world_terrain.py`, `npc_ai.py`, `world_combat.py`, `world_reward.py`, `world_ground_items.py`를 검토했다. 나머지 파일에 독립적으로 입증한 추가 결함은 없었다. 이는 무결함 판정이 아니다. 다중 PC가 필요한 화면 갱신 후보는 현재 단일 gameplay owner 경로의 도달 가능성이 미확정이어서 지적에서 제외했다.

기존 `GAME_CORE_DESIGN`, combat LOS 계획·adapters API, current-projectile-visibility API, respawn-drain/status-close API와 기존 시험 사례를 참고했다. 새 역분석·guard·핀·해시 검사·검증 도구는 만들지 않았다.

프로젝트 루트에서 아래 형식으로 기존 순수 모듈 시험을 실행했다.

```powershell
& 'C:\Users\Chansol\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -B -m tools.local_original_session.<시험>
```

| 시험 | 결과 |
|---|---|
| `world_tests` | 6개 OK, exit 0 |
| `npc_ai_range_tests` | 16개 OK, exit 0 |
| `world_reward_tests` | 9개 OK, exit 0 |
| `world_ground_items_tests` | 13개 OK, exit 0 |
| `world_terrain_tests` | 5개 OK, exit 0 |

위 **총 49개 통과**와 별도로 동일 Python `-X utf8 -B -`의 stdin 순수 재현 두 번에서 결함 4건과 퇴장 후 잔존 상태의 출력·예외·메모리 결과를 직접 확인했다(각 exit 0). 새 시험 파일은 만들지 않았다. 메인 확인 출력은 다음과 같다.

```text
PC_LOS False line_clear False hp 9995 frames 1 cooldown 100.917
PC_LOS None line_clear False hp 9995 frames 1 cooldown 100.917
PICKUP GROUND_ITEM_EXPIRED committed_count 10 ground_count 10
REGEN [10.0, 10.15] first_next 10.0 next 11.0
LEAVE selected False alive True old_ref_current True can_move False spawn_occupied True
TOMBSTONES entities 1 items 0 callbacks 0 dead_refs 10 all_removed True
```

게임・broker・loopback 포함 시험은 실행하지 않았다. 실제 디스크 저장·정상 패킷·원본 벽/문·화면·30분 사냥은 미확인이다. 최종 산출물은 이 문서 하나이며 기존 dirty/untracked 파일은 보존했다.
