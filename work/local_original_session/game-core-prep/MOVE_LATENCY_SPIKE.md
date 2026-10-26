# 이동 지연 튐 정적 분석

2026-10-27. 요청한 문서만 작성했다. `main`의 기존 미커밋·미추적 코드를 읽었으며 서버 코드·설정·저장·큐 변경, commit, 게임·서버·포트·벤치마크·제품 모듈 실행은 하지 않았다. 동시 writer가 있으므로 아래 줄번호는 열람 시점의 위치이며 **함수명·분기를 함께 기준으로 삼는다.**

**가장 먼저 다룰 후보는 매 성공 이동의 `PositionStore.commit → _write → flush/fsync/replace`다.** 이벤트 루프에서 직접 실행되므로 저장 지연이 이동과 월드 틱을 함께 멈출 수 있다. 반복 저장 읽기와 시야 Remove의 고정 자료 재읽기도 연결돼 있다. 다만 기존 결과에는 개별 작업의 시작·끝 시각이 없어 **547ms를 특정 fsync·GC 등에 귀속하는 것은 UNKNOWN**이다. 현재 관측용 `status.json`에는 이미 fsync가 없어 과거 감사 내용을 그대로 원인으로 사용할 수 없다.

## 1. 기존 측정이 실제로 뜻하는 것

| 기존 결과 | 이동 측정 | 같은 실행의 루프 지연 | 판정 범위 |
|---|---|---|---|
| [hunt600 원로그](../runs/task-20261026-hunt600-resume.log), 87–92·192–196줄 | `0x4E2B_to_ALIVE_barrier` 800건, 중앙값 **16.0ms**, 최대 **547.0ms** | 최대 **532.5ms**, >50ms 18회, >200ms 7회 | 600.109초 socket 봇. 저장 사본 `hunt-loopback-7gq9_aar`, broker failure null. |
| [후속 loopback5](../runs/rea-connect-20261026-225926-loopback5.log) | 377건, 중앙값 **17.884ms**, 최대 **229.345ms** | 최대 **219.2ms**, >50ms 5회, >200ms 2회 | 300.199초, 별도 사본 `hunt-loopback-rcmwsbsw`. 이전 실행과 소스 동일성·개선 인과를 주장하지 않는다. |
| [latency-after-np4](../runs/latency-claude-20261026/latency-after-np4.json) | 24건, 중앙값 **15.38ms**, 최대 **17.37ms** | 이 JSON에 루프 지연 없음 | 짧은 별도 fixture. 장시간의 드문 튐이 없다는 증거가 아니다. |

[hunt_bot.py](../../../tools/local_original_session/hunt_bot.py)의 `Peer.request:193`은 이동과 `CS4E2A`를 순서대로 보내고 `SC4F57` 수신 시각까지 잰다. 성공 이동 자체는 self `SC4E2C`를 보내지 않는다. 따라서 547ms는 이동 함수 단독 시간이 아니라 **수신 대기·이동 처리/저장·시야 응답 송신·뒤따르는 Alive owner 확인/송신·봇 수신 처리까지의 장벽 시간**이다. Alive 송신 후 `_world_after_request`도 실행되므로 같은 루프의 수신 task가 재개되기 전 그 비용이 겹칠 수 있다.

[hunt_bot_loopback.py](../../../tools/local_original_session/hunt_bot_loopback.py)의 `run.watch:131`은 같은 asyncio 루프에서 `sleep(.01)`의 초과시간을 집계한다. 두 최대값이 약 0.5초로 비슷한 것은 루프 정체 후보와 부합하지만 동일 사건의 시간 상관 증거는 아니다. 루프 지연에는 OS 스케줄링도 포함될 수 있다.

현재 확인한 loopback fixture의 `build:42`는 `owner_guard → True`, `source_guard → None`, `FixtureConversation`을 사용하고 native edge 없이 정적 terrain fallback을 쓴다. `run:144–150`도 launcher/SessionMonitor를 만들지 않는다. **이 구성의 봇 튐을 실제 LC 메모리 판독·GetExtendedTcpTable·관측 status 발행으로 설명할 수 없다.** 과거 hunt600의 정확한 소스 스냅샷/전체 호출 추적은 확인하지 않았으므로 현재 파일만으로 당시 모든 분기를 소급 확정하지 않는다. 봇·broker·월드는 같은 프로세스/루프이므로 클라이언트 측 Python 처리와 GC도 별도 분리되지 않는다.

## 2. 현재 코드의 실제 이동 순서

```text
PersistentBroker._serve                         broker.py:5115–5161
  row operation_lock → chunk/frame _checkpoint → _world_dispatch
  WorldRuntime.dispatch_now                     world_runtime.py:80 (world lock)
    world_handlers.dispatch → handle_move       world_handlers.py:292/323
      HostContext.move → _world_move_for_handler broker.py:4518
        game.received → LocalRealm.grant.move   broker.py:616
          MovementService.handle_CS4E2B         movement.py:293 (movement lock)
            _owner → _movement_owner            broker.py:2424
              exact_selection → _checkpoint → exact_selection
            parse/start/heading → edge callback
              UNKNOWN이면 _world_edge_fallback  broker.py:4193
                terrain.can_step + 현재 NPC 점유 확인
            _owner (두 번째)
            PositionStore.commit → _write       movement.py:353 → 173/157
              read/preimage CAS → JSON → temp → flush → fsync → replace
            memory position 갱신                movement.py:357
        WorldView.update_pc_and_drain           broker.py:4541
          update_pc → update_interest → ai.sync → _refresh/_refresh_items
    원 world send 경로                         broker.py:4636/4222
  다음 CS4E2A → owner 확인 → SC4F57
```

**일반 이동은 저장 성공 뒤 메모리·시야를 갱신한다.** 시야 계산 뒤 위치를 저장하는 순서가 아니다. 현재 `_world_dispatch`가 처리한 이동은 `_serve`의 `continue`로 끝나므로 이동에 `_world_after_request`까지 중복 합산하지 않는다. 반면 Alive는 기존 game route와 `_world_after_request:4871`를 지나며 위치가 같아도 `update_pc_and_drain`을 다시 호출한다.

## 3. 원인 후보와 코드 근거

### A. 매 걸음 동기 내구성 저장 — 최우선, 직접 연결 확인

[movement.py](../../../tools/local_original_session/movement.py) `handle_CS4E2B:351–357`, `PositionStore.commit:173–194`, `_write:157–171`.

- 승인된 이동마다 최대 3개 캐릭터의 좌표 JSON 전체를 다시 만들고, 고유 temp 생성 → write → flush → **`os.fsync` 1회** → `os.replace` → temp 정리를 동기로 수행한다. JSON 상한은 4,096B다. 파일이 작아도 fsync·파일 생성/교체의 대기시간에는 코드상 ms 상한이 없다.
- 이 동안 movement/row/world lock과 `threading` 저장 lock을 보유한다. `async def` 안의 직접 호출이므로 OS I/O가 지연되면 같은 이벤트 루프도 정지한다. `wait_for`·drain timeout이 동기 호출을 중간에 선점하지 않는다.
- 성공 이동만 저장하며 stale/blocked/unknown 거절은 여기까지 오지 않는다. 순간 튐과 거절 여부를 연결할 개별 이벤트 기록은 없다.
- [기존 profile-fix2](../runs/latency-claude-20261026/profile-fix2.txt) 46·54·83줄에는 commit **56회/누적0.374초**, `_write` **56회/0.328초**, 전체 fsync **58회/0.217초**가 있다. fsync 평균 약3.74ms는 이 별도 실행의 합계로, hunt600의 단일 최대532ms를 입증하지 않는다. 저장 비용 자체가 실제로 발생했다는 기존 근거로만 쓴다.

### B. owner 검사에 중첩된 파일 읽기·JSON 재생성 — 직접 연결, 증폭 요인

`MovementService._owner`를 정상 이동 전후 2회 부른다. 각 [broker.py](../../../tools/local_original_session/broker.py) `_movement_owner:2424–2445`는 await 전후 `exact_selection` 2회, 매번 `CharacterStore.select`와 `positions.restore`를 실행한다.

- 성공 이동 하나에 **characters 4회 + positions 4회**, commit preimage의 positions 1회를 더해 **최소 9회 저장 읽기/파싱**다. 뒤의 Alive owner는 characters 2회 + positions 2회를 추가한다. 즉 이동+Alive 기본 경로만 최소 **13회**이며 기능별 추가 검사는 별도다.
- [CharacterStore](../../../tools/local_character_creation/realm.py) `_read:132`는 최대64KB JSON을 다시 읽고 전체 행을 검증하며, `select:209`는 INFO DTO도 재구성한다. `PositionStore._read:115`는 매번 JSON과 스키마를 다시 읽는다. `_path_check:102`는 파일부터 모든 상위 디렉터리의 `lexists/lstat`를 순회하고 `_write`에서도 2회 추가한다.
- 기존 profile-fix2 26·31·33줄: positions `_read` 643회/누적0.583초, `restore` 586회/0.554초, `_path_check` 756회/0.520초. 서로 중첩된 누적시간이므로 합산하지 않는다. 전체 `nt.stat/lstat`도 프로파일에 있으나 다른 기능까지 포함한다.
- 고정 소스 JSON과 달리 이 자료는 변경 가능한 권위/preimage다. 시작 때 한 번 읽는 캐시로 대체하거나 owner/CAS 확인을 삭제하는 것은 최소 수정안으로 채택하지 않는다. 보통 비용을 늘린다는 근거는 충분하나 500ms CPU 작업이라는 근거는 없다.

### C. 시야 경계마다 Remove의 고정 evidence 재읽기 — 조건부 직접 연결

[world_visibility.py](../../../tools/local_original_session/world_visibility.py) `_refresh:276–281`, `_refresh_items:284–296`, `remove_frame:116` → [npc_death.py](../../../tools/local_original_session/npc_death.py) `frame:47` → `source_ready:30`.

- 화면 밖으로 나가는 **NPC/마을 NPC/아이템 UID마다** run75의 3파일 **40,896B**를 재읽고 SHA256을 계산하며 `source-evidence.json`도 다시 파싱한다. 생성 시 `WorldView.create:200`에서 확인한 같은 고정 자료인데 frame 경로에서 캐시하지 않는다. 한 이동에서 여러 UID가 leave하면 그 수만큼 반복된다.
- NPC 이동에 따른 leave(`npc_step`), corpse/respawn tick의 `_refresh`, 아이템 소멸도 같은 producer를 사용한다. 따라서 이동 밖의 월드 tick도 같은 루프를 점유할 수 있다.
- `_world_send`의 `world_operation` 분기는 기존 legacy Death/Remove service 검증 경로를 타지 않는다(`broker.py:3741/3756`). 여기서 `npc_death.validate_frame`까지 매 world wire마다 더한다고 계산하면 오탐이다.
- 진입 spawn은 `NpcSpawn.encode`를 사용한다. **14MB SPR/native 자료 전체를 이동마다 재파싱한다는 경로는 아니다.** 현재 월드 create의 시작 비용과 구분한다.

### D. 지형·관심 그룹·AI/월드 tick — 메모리 계산, 장면 변화에 따라 추가

[world_terrain.py](../../../tools/local_original_session/world_terrain.py) `default_terrain:209`는 map0를 시작 때 로드하고 `flag/can_step`은 메모리 배열을 읽는다. map0 청크 경계를 넘을 때 파일을 다시 로드하지 않는다. map1/2만 `_map_chunks:119`의 최초 질의에서 해당 맵 S32를 동기 로드하므로 M1 map0의 반복 튐 설명과 구분한다.

`update_pc:342`는 매 이동과 Alive에 `InterestSpawner.update_interest`, `NpcAi.sync`, NPC/아이템 시야 차이를 계산한다. 그룹 활성화 시 `_refill/_place`는 슬롯별 최대8회 랜덤 배치·지형/점유 확인을 한다([world_interest_spawn.py](../../../tools/local_original_session/world_interest_spawn.py):127/167/194). [EntityRegistry.near](../../../tools/local_original_session/world_entities.py):174는 공간 버킷과 결과 정렬을 사용한다. 여기에 파일 쓰기는 없으며 현재 M1 규모에서 수백ms CPU를 쓴 실행 근거도 없다.

`WorldRuntime.tick_once:69`는 scheduler/AI/시야 hook을 요청과 같은 world lock에서 실행한다. 앞선 tick 또는 다른 연결의 저장/Remove가 이동을 늦출 수 있다. **tick 간격150ms와 idle poll100ms는 패킷마다 반드시 더하는 대기시간이 아니다.** `dispatch_now`는 lock을 얻는 즉시 실행한다.

### E. 관측·추가 저장·GC — 적용 실행을 구분

- **현재 launcher 관측:** [observe.py](../../../tools/local_original_session/observe.py) `SessionMonitor.tick:613`의 window/scene 판독, `broker_status/bridge_status`, `publish:691`의 JSON 비교·변경 시 재인코딩·temp/replace는 여전히 동기다. 하지만 `_write`에 해당하는 `publish:704–710`은 **fsync를 이미 제거**했다. 코드의 과거 “~600ms 측정” 주석은 이번 측정이 아니다. steady Land의 window 3초/memory 2초 간격도 이미 적용돼 있다. [HOT_PATH_AUDIT](HOT_PATH_AUDIT.md) 4장의 과거 fsync1 설명보다 현재 코드가 우선이다.
- **native 게임만:** [edge.py](../../../tools/local_original_session/edge.py) `EdgeAdapter.__call__:598`은 live typed read/code SHA/재판독을 동기로 수행한다(40,960B 예산은 시간 예산이 아님). launcher `guard_exact_sync:1048`의 TCP table/owner 조회도 있다. 이들은 실제 게임에서 추가 지연 후보지만 앞의 loopback 봇에는 없다.
- **다른 행동의 저장:** progression은 `_world_save_progress`에서 dirty일 때만 `ProgressStore.commit → fsync/replace`를 한다(`broker.py:4235/4920/4944`, [world_progress.py](../../../tools/local_original_session/world_progress.py):99). pickup/물약의 inventory CAS도 동기다. 모든 이동에 무조건 EXP·inventory 저장을 더하지 않는다. hunt600 pickup 최대359ms는 같은 실행의 별도 행동 지연일 뿐 공통 원인 확정은 아니다.
- **GC/봇 처리:** `tools/local_original_session/*.py`에서 명시 `gc.collect`, `gc.disable`, `gc.set_threshold` 호출은 발견하지 못했다. JSON·시야의 임시 dict/list 생성과 bot `Peer.pump/apply/wait`도 같은 루프에서 실행되므로 자동 GC·수신 디코딩은 후보로 남는다. `Peer.frames`는 maxlen=2048이며 무한 프레임 누적이라고 볼 근거가 없다. GC 시작/끝 기록이 없어 기여도 UNKNOWN; GC 비활성화를 수정안으로 삼지 않는다.

## 4. 최소 수정안과 보존해야 하는 계약

1. **고정 Remove evidence를 기존 시작 준비로 한정한다.** `WorldView.create`에 이미 `npc_death.source_ready()`가 있으므로 월드가 쓰는 encoder만 런타임 UID/opcode 검증과 인코딩을 수행하게 분리한다. `npc.NpcSpawn.encode`의 기존 방식이 직접 재사용 후보다. legacy `frame/validate_frame/Notifications`의 권위 계약을 일괄 삭제하지 않고 월드 caller만 분리한다. 새 해시/guard·요청 중 파일 검사·판독 대기는 추가하지 않는다. 경계 이동의 반복 I/O를 없애지만 fsync 튐까지 해결한다고 주장하지 않는다.
2. **저장 정책을 유지한다면 위치 CAS 전체를 직렬 I/O 실행부로 분리한다.** read/preimage 비교부터 temp/write/fsync/replace/정리까지 한 작업으로 옮기고 성공을 기다린 뒤 메모리·시야를 승격한다. `fsync` 한 줄만 분리하거나 fire-and-forget하지 않는다. 기존 저장 lock과 row/movement/world 직렬화, close의 진행 중 저장 회수, 취소·replace 후 예외의 UNKNOWN/fatal을 유지해야 한다. **이 방식은 루프 전체의 정지를 줄이지만 해당 걸음은 같은 디스크 완료를 기다리므로 이동 최대 지연 자체가 사라지지는 않는다.** 또한 world lock을 기다리는 다른 월드 행동은 여전히 기다릴 수 있다. `restore:151`도 같은 `_store_lock`을 잡으므로 worker 저장 중 다른 coroutine이 loop에서 동기 restore를 호출하면 lock 대기로 루프를 다시 막는다. 이 경합 read도 같은 실행부로 보내는 등 기존 caller와 함께 처리해야 하며 commit 하나의 단순 offload로 해결됐다고 판정하지 않는다.
3. **해당 걸음도 저장 완료를 기다리지 않게 하려면 위치 저장 정책 결정이 필요하다.** 메모리 권위+dirty 최신 좌표를 주기적으로 합치는 방식은 기존 persist-before-memory/CAS·충돌 감지·크래시 복원 범위를 바꾼다. 이 감사가 허용하거나 즉시 적용할 수정으로 제시하지 않는다. [world_persist.py](../../../tools/local_original_session/world_persist.py)도 자동 해결책이 아니다. 현재 broker/WorldView에 연결되지 않았고, docstring대로 flush는 world thread의 **동기 I/O**이며 CAS 실행이 아닌 absolute snapshot writer를 요구한다. 그대로 붙이면 튐을 tick으로 옮길 수 있다.
4. **반복 읽기와 관측은 위 수정 이후의 좁은 후보다.** 변경 가능한 selected/current/preimage를 무조건 캐시하지 않는다. 관측은 이미 fsync 제거·steady cadence 완화가 돼 있으므로 중복 적용하지 않는다. 필요한 경우 기존 report의 `monitor_tick_max_ms/features_poll_max_ms`로 실제 launcher 관측 비용부터 분리한다. native typed reader를 임의로 다른 thread에 옮기거나 현재 owner 증명을 과거 sample로 대체하지 않는다.

연결 함수의 현행/제안 시그니처와 제한을 docstring 형태로만 남긴다. **아래는 구현 코드가 아니다.**

```python
async def handle_CS4E2B(self, payload, *, transition=None):
    """현행 MovementService 진입점. owner 2회·저장 성공 뒤 memory 승격을 유지한다."""

def commit(self, expected, updated, *, transition=False):
    """현행 PositionStore 동기 CAS. preimage부터 replace/정리까지 하나의 작업이다."""

async def commit_async(self, expected, updated, *, transition=False):
    """제안만: 위 commit 전체를 직렬 I/O 작업으로 실행하고 최종 결과를 회수한다.
    취소가 worker의 write를 취소했다고 간주하지 않는다. FIRST/close 전에 완료/오류를
    회수하며, 실패는 현행 fatal/UNKNOWN으로 남긴다. 저장 중 await가 새로 생기므로
    기존 writer/selection/position 수명과 잠금 순서를 유지할 caller 검토가 필요하다.
    commit 뒤 old-position 기준 _owner를 그대로 재호출하면 이미 바뀐 디스크와
    비교해 실패하므로 단순 to_thread 한 줄 치환으로 완결됐다고 보지 않는다.
    """

def encode_frame(opcode, uid):
    """제안만: WorldView.create가 기존 source_ready를 완료한 월드 전용 encoder.
    현행 frame의 opcode/UID 검증·wire 형식은 보존하고 고정 파일 재읽기만 분리한다.
    """
```

## 5. 남은 최소 입력·검증 범위

- **이미 있는 결과 재사용:** 위 hunt600/loopback5, latency JSON·profile, [HOT_PATH_AUDIT](HOT_PATH_AUDIT.md), [관측 atomic 결과](../integration-1/observation-atomic-fix/RESULT.md)를 대조했다. output-only도 과거에는 fsync를 사용했다는 결과와 현재 `observe.publish`의 제거를 구분했다. [기존 cold cache API](../shared-api/book-cold-explicit-dependencies/API.md)의 “선택된 고정 자료 첫 로딩 후 재사용” 원칙만 참조하며 과거 Source/PASS를 현재 이동 실행에 이전하지 않는다.
- **아직 없는 입력:** 최대 이동/loop stall 각각의 발생 시각과 당시 `PositionStore.commit/_write`, world tick/시야 Remove의 소요시간. 누적 max끼리는 동일 사건 여부·fsync/replace/GC 비중을 알 수 없다. 별도 새 검사기·guard·벤치마크·검증 체계는 만들지 않았다.
- **다음 실행 소유자에게 필요한 최소 관측:** 기존 latency/profile 실행과 기존 loop_lag report를 사용해 승인된 수정 한 단위의 전후만 비교한다. 원인 확정이 꼭 필요하면 해당 실행에서 기존 저장/시야 단계의 경과시간과 현재 이동 사건을 한 번 대응시키는 것으로 충분하다. 서버 owner가 수행하며 이 문서는 서버·포트 실행을 발주하지 않는다. 저장 실패/취소/close 결과는 기존 시험과 보존 계약으로 확인하고 원오류를 지우지 않는다.
- **이번 확인:** `git status --short --branch`/최근 branch, `rg -n/--files`, UTF-8/UTF-16 원문 읽기와 표준 라이브러리 JSON 요약으로 caller·분기·기존 수치를 정적 확인했다. Python은 지정 runtime의 `-X utf8 -B -`로 읽기만 했다. 코드 변경이 없는 문서 작업이므로 pure-module 시험도 실행하지 않았다. 실제 532.5ms의 담당 함수·디스크 상태·GC·화면/입력 동작, 수정 후 개선량은 미확인이다.
