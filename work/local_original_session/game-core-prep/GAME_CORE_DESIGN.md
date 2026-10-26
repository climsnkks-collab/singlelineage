# 게임 뼈대 설계와 M1 실행 단위

2026-10-26 · 설계 초안 · 이번 작성에서 제품 코드·게임·서버·시험은 실행하지 않았다.

## 1쪽 — L1J에서 참고할 구조

원본 클라이언트와 Python broker를 유지하고 자율 사냥터를 만든다. 참고 저장소는 `D:/SingleLineageRef/l1j-en-classic`, 소스 기준은 `src/l1j/server/server/`다. README의 대상은 **2009년 최종 US 클라이언트**로 현재 클래식과 ID·패킷·공식·속도가 같다는 근거가 아니다. 기본값과 실제 설정도 구별한다.

1. **게임 시계와 AI 실행은 별개다.** `model/gametime/L1GameTimeClock.java:TimeUpdater/notifyChanged`는 500ms마다 시각을 갱신한다. `L1GameTime.valueOf/fromSystemCurrentTime`은 실시간 6배 게임시계다. `GeneralThreadPool`의 예약 풀·PC별 풀은 별도여서 500ms가 모든 행동 주기는 아니다.

2. **NPC AI는 행동 뒤 다시 깨어난다.** `model/Instance/L1NpcInstance.java:startAI/NpcAITimerImpl/NpcAIThreadImpl`은 예약 재등록 또는 sleep으로 반복한다. `AIProcess`의 기본 300ms 경로와 이동·공격별 지연을 사용한다. `noTarget`에서 인식 PC가 없으면 AI가 끝나지만 그 자체로 스폰 객체를 삭제하지 않는다.

3. **인식·대상·공격 판정이 분리된다.** `L1MonsterInstance.searchTarget`은 선공·제외 조건에 맞는 첫 visible PC를 찾고 `L1NpcInstance.setHate/checkTarget`은 최대 hate로 대상을 고른다. `onTarget`은 스킬/공격 또는 추적을 수행한다. `L1Character.isAttackPosition`은 거리와 `glanceCheck`를 쓴다.

4. **추적·도주·귀환 조건은 다르다.** `moveDirection/_serchCource`는 제한 범위 큐 탐색과 먼 거리 직선 통행을 사용한다. `setDirectionMove`는 home의 `movement_distance` 초과 시 순간이동 경로가 있다. 도주 조건은 `atkspeed==0 && passispeed>0`이며 일반 저HP 도주가 아니다. 아래 보행 귀환은 로컬 정책이다.

5. **스폰은 표·그룹·예약으로 구성된다.** `datatables/SpawnTable.fillSpawnTable`→`L1Spawn.init/doSpawn/calcRespawnDelay`가 마릿수·영역·randomxy·지연을 사용한다. 사각형 추첨과 두 난수 차의 randomxy는 분포가 다르다. `Death.run`→시체 삭제→`deleteMe/onDecay` 뒤 재스폰을 예약하며 그룹은 마지막 구성원 제거와 재생을 잇는다.

6. **보이기와 AI 활성은 같은 사건이 아니다.** `L1PcInstance.updateObject/removeOutOfRangeObjects`와 `L1MonsterInstance.onPerceive`가 표시·제거·AI 시작을 연결한다. `PC_RECOGNIZE_RANGE==-1`이면 `Point.isInScreen`, 그 외에는 tileLine 거리를 사용한다. PC 자동 갱신은 300ms 예약이며 이를 고정 반경 하나로 요약하지 않는다.

7. **속도는 행동 데이터로 판정한다.** `datatables/SprTable.calcActionSpeed`는 `int(framecount*40*24/framerate)`ms다. `AcceleratorChecker.checkInterval/getRightInterval`은 PC gfx·무기·상태별 기준보다 `실경과×strictness`가 짧으면 누적하고 한도에서 차단한다. 참고 설정 strictness는 1.10이다. NPC는 별도로 `NpcTable`의 `passispeed/atkspeed`를 `attackTarget/calcSleepTime`에서 소비한다.

8. **회복·효과 만료는 별도 시간 작업이다.** `L1PcInstance.startHpRegeneration/startMpRegeneration`과 `HpRegeneration/MpRegeneration`은 1초 예약에서 공격/이동/정지 점수와 레벨·CON/WIS·장비·상태를 소비한다. NPC 회복은 표의 양·간격을 사용한다. `skill/L1SkillTimerTimerImpl.begin/run`→`removeSkillEffect`→`L1SkillStop.stopSkill`은 만료·해제를 잇고 duration 0은 무기한이다.

9. **피해·성장·드롭을 순서대로 소비한다.** `L1Attack.calcHit/calcDamage/action/commit`은 능력치·무기·AC·RNG로 결정한 피해를 애니메이션 종료 대기 없이 `receiveDamage`에 적용한다. `Death.run`→`utils/CalcExp.calcExp`→`addExp`→`L1PcExpMonitor`→`L1PcInstance.onChangeExp/levelUp`이 성장 경로다. 최초 `onNpcAI`의 `DropTable.setDrop`이 몬스터 인벤토리에 미리 생성하고 사망 시 `dropShare`가 분배한다. 자동 루팅·아데나 직행·바닥 분배가 있으며 `C_PickUpItem`은 거리·수량·소유·용량 확인 후 이전한다.

<div style="page-break-after: always;"></div>

## 2쪽 — Python 모듈과 단일 상태 소유

### 기존 구현을 잇는 경계

`broker.py:LocalRealm.grant`와 `PersistentBroker._serve`의 디코딩→`game.received`→`_send`를 재사용한다. `row.operation_lock`·current·write/drain·once·저장/CAS·partial은 유지한다. 함수·성공 범위는 [재사용표](REUSE_TABLE.md)를 따른다.

`npc.py:NpcSpawn/prepare`는 map0·SPR56/template0·MAX_SPAWNS=1 배치, `npc_motion.NpcMotion.plan`은 목표에 가까워지는 한 칸만 지원한다. wire·통행·drain 뒤 commit을 살려 다수 엔티티 AI를 연결하고 제약 삭제로 일반화하지 않는다. 고정 피해·명시 반격 시험의 성공은 자율 사냥 완료가 아니다.

### 모듈별 책임

`world_runtime`은 월드 실행 수명·틱 시작/종료, `world_entities`는 PC/NPC/바닥 아이템의 UID·generation·위치·생명을 소유한다. `world_scheduler`는 활성 행동·회복·효과 만료·시체·재스폰 deadline을 관리한다. NPC별 thread를 만들지 않는다.

`world_interest_spawn`은 PC 위치·스폰 표로 활성·휴면·보충을 결정한다. `npc_ai`는 대상·통행·속도로 상태를 진행한다. `combat_service`는 실제 스탯·무기로 사거리/LOS·공속·명중/피해 결정과 HP를 연결한다.

`recovery_life`는 회복·사망·마을 복귀를 RESOURCE/Life에 전달한다. `reward_service`는 진짜 KillReceipt로 EXP·성장·드롭을 기존 once 저장에 연결한다. `game_data`는 출처 있는 읽기 전용 정의를 공급한다. 기존 모듈 접점을 우선 쓴다.

레지스트리는 위치·수명을 연결하고 HP는 기존 HP/RESOURCE, 성장·아이템은 기존 participant/custody를 권위로 둔다. AI 복사본을 두 번째 원장으로 만들지 않는다. UID/generation 목표의 위치·생존·선택 수명은 행동 직전 확인하며 폐기 세대의 예약은 실행하지 않는다.

### 100~200ms 자율 틱과 즉시 요청

기존 asyncio 루프에 월드 task 하나를 두고 100~200ms마다 현재 monotonic 시각의 due 자율 행동만 진행한다. 무수신 poll이나 launcher 생존 감시를 월드 틱으로 대신하지 않는다. 더 느린 행동은 자기 deadline까지 쉬며, 틱이 늦었다고 누락 공격을 몰아서 실행하지 않는다. 다음 허용 시각은 실제 행동과 데이터의 간격에서 정한다.

PC 요청은 기존 수신 경로에서 즉시 dispatch하며 다음 틱까지 쌓아두지 않는다. 단타인지 공격 시작/중지인지 기존 실제 입력 계약을 따르고, 실제 반복 계약이 있을 때만 틱이 후속 행동을 처리한다. 허용 시각보다 이른 요청은 상태를 바꾸거나 예약하지 않고 거절하며 이동에는 기존 broker의 보정을 요청한다. 허용오차는 속도 표의 로컬 정책으로 둔다.

입력과 틱은 같은 월드 상태 소유자·gameplay operation 경계로 직렬화한다. asyncio에서도 await 사이 경합은 가능하며, 연결별 row lock 두 개가 같은 캐릭터 월드를 따로 쓰지 않도록 활성 gameplay owner 하나를 결속한다. 요청 안에서는 locked callee를 쓰고 틱은 그 operation으로 진입한다. 잠금을 잡은 채 다시 lock을 잡는 외부 `step_npc` 같은 API를 호출하지 않는다.

계산·저장·송신·반영은 원 소비자 순서를 따른다. “즉시”는 틱 대기를 추가하지 않는다는 뜻이다. 종료는 새 행동 중단→원 저장/송신 마감·partial 보존→월드 task 회수→기존 close로 잇고 옛 수명을 재접속 권위로 복원하지 않는다.

<div style="page-break-after: always;"></div>

## 3쪽 — 스폰·AI·시간·broker·데이터

### 근처 그룹과 휴면 slot

그룹은 map·스폰 영역·target_count와 slot을 가진다. PC와 **스폰 영역**의 거리가 Ron 안이면 활성화하고 Roff 밖에서 휴면을 검토하며 `Ron<Roff`다. Roff는 인식 범위보다 크게 두어 화면 퇴장과 그룹 해제를 구별한다. 추적·전투 중인 몹은 시야 밖이라고 즉시 휴면시키지 않고 leash→귀환·대상 해제 뒤 그룹을 쉰다. 수치는 자료에 맞춰 정하는 로컬 정책이다.

slot은 빈칸, 살아 있는 몹, 죽은 몹의 재등장 대기를 구별한다. 살아 있는 휴면 slot은 HP·위치·home·generation을 보존하고 M1에서는 휴면 중 회복/전투 계산을 하지 않는다. 재진입 때 새 fullHP로 바꾸지 않는다. 죽은 slot은 사망 시각과 시체 제거 예정 시각 `corpse_at`을 보존하고, 로컬 정책으로 `respawn_at=corpse_at+respawn_delay`를 둔다.

inactive 그룹은 틱과 타이머 heap에서 제외한다. 재진입 때 죽은 slot의 deadline이 지난 결원만 target_count까지 보충하고 경과 동안 가상 kill·drop·EXP를 만들지 않는다. 살아 있는 slot은 휴면 스냅샷으로 활성화한다. 생성은 범위 안 무작위 후보→NPC 통행·점유 확인→정해진 횟수 실패 시 결원 유지/재시도다. 무한 탐색이나 막힌 좌표 강제 출현은 하지 않는다.

출현은 정당 UID·현재 generation·기존 소비 경로로 잇고 죽은 UID를 재사용하지 않는다. 휴면은 kill·보상·사망 리스폰을 만들지 않는다. 가시성은 PC 이동 즉시, NPC 이동·spawn·death·remove 뒤 known 집합 차이로 enter/exit를 낸다. enter 뒤 move/HP 순서를 보존한다.

### AI와 타이머

AI는 IDLE/대기→WANDER/배회, 선공 조건 충족→CHASE/추적, 사거리·LOS·공속 충족→ATTACK/공격으로 전이한다. 비선공 몹은 실제 피격/hate 후 전투하며 대상 사망·소멸, leash·경로 포기면 RETURN/귀환→home 대기로 간다. FLEE/도주는 해당 몬스터 데이터와 조건이 있을 때만 사용하고 조건 해제·대상 상실 후 RETURN으로 전이한다.

경로는 NPC 통행과 현재 점유를 사용하는 제한 범위 BFS를 M1 기본으로 택하고, 먼 목표는 작은 중간 목표로 나눈다. 막히면 다음 허용 시각에 제한 재시도하고 한계 뒤 추적을 포기해 귀환한다. A*로 바꿀 수 있으나 무제한 전맵 탐색은 피한다. 귀환도 막히면 정해진 재시도/정지 정책을 따르며 임의 순간이동으로 성공 처리하지 않는다.

이동·공격은 각각 다음 허용 시각을 갖고 명중/피해 RNG는 한 번만 소비한다. 표시 raw effect와 피해를 구별한다. NPC HP0→Death→시체 제거→slot 대기를 잇는다. PC 사망은 공격·추적·회복 예약과 이전 생명 입력을 정리한 뒤 기존 token/ACK/복귀 경로로 마을 좌표·자원을 저장한다.

시간은 tick 횟수 대신 monotonic deadline을 쓴다. 기존 저장 UTC deadline은 시작 때 monotonic 기준으로 변환하고 runtime 숫자를 영구 시각으로 저장하지 않는다. 재스폰은 휴면 경과를 인정하되 NPC 휴면 회복·PC 오프라인 회복은 지급하지 않는 M1 정책이다. 자연 회복은 현재 HP/MP·최대값·행동 상태·수식으로 RESOURCE를 변경한다. 버프는 기존 저장 만료 시각에 효과를 해제하고 파생 능력치를 재계산하며 무기한 효과는 구별한다. M1에서 버프 종류를 확대하지 않는다.

### broker와 표의 계약

게임 모듈은 선택된 세션/current 조회와 의미 입력 `on_move/on_attack/on_pickup/on_recovery`, 선택 해제/종료 통지를 요구한다. 출력은 출현·이동·공격 결과·자원 변경·사망·제거·인벤토리 변경과 거절/이동 보정이다. 실제 current/generation/receipt는 기존 권위를 유지한다. broker는 원 파서·DTO·consumer·송신을 맡으며 여기서는 형식·opcode·새 sender를 설계하지 않는다.

계산은 `combat-adjudication/adapters/API.md`와 실제 Stats/Gear/SKILL snapshot을 쓴다. 성장은 `progression-kill-delivery-v1/API.md`의 Death drain→KillPort→ProgressionOwner, 드롭은 실제 kill→native 자산/custody→바닥/줍기를 잇는다. held-item DROP은 전리품 생성 권위가 아니다. 사망 시 바닥 드롭은 M1 로컬 선택이다.

표는 몬스터 ID/template/sprite 대응·HP/MP·공격/인식/leash, 스폰 영역/마릿수/지연, 드롭 chance/min/max, EXP 누적 threshold, 아이템·회복 공식, 행동 framecount/framerate·속도를 분리한다. 값마다 **클라이언트 내부 자료→공개 공식 정보→L1J 빈칸 보충/로컬 정책** 순의 출처를 붙인다. 이름·순번만으로 ID를 합치지 않으며 M1 한 사냥터의 필요한 행부터 채운다.

<div style="page-break-after: always;"></div>

## 4쪽 — M1을 잇는 8개 worker 단위

Claude가 각 단위의 부모·기존 API·소유 파일을 지정한다. 공용 파일은 한 writer, 게임·포트·사본·공용 호출부·FIRST/close 실행자는 동시에 하나다.

1. **M1 데이터·정의.** 고정 클라이언트 자료·공식 정보·참고 L1J와 기존 ID 대응을 받아 `game_data`와 한 사냥터 표를 소유한다. 지원 몬스터·장비·스폰·EXP·드롭·속도·회복의 실제 필요 행과 출처를 산출한다.

2. **월드 소유·엔티티·시간.** 기존 broker operation·선택/종료 수명과 1번 타입을 받아 `world_runtime/entities/scheduler`를 소유한다. 단일 상태·100~200ms due 틱·즉시 요청 접점·UID/generation·예약 취소를 산출하고 공용 변경은 8번에 전달한다.

3. **근처 스폰·휴면.** 스폰 표·현재 엔티티/시간·기존 출현/제거를 받아 `world_interest_spawn`을 소유한다. Ron/Roff·slot·살아 있는 HP·dead deadline·무작위 통행/점유 배치와 재진입 보충을 연결해 복제·무료 회복 없는 사냥터를 산출한다.

4. **NPC AI·이동.** 행동/속도·현재 세대·기존 NPC 통행을 받아 `npc_ai`와 해당 이동 경로를 소유한다. 배회·선공·추적·공격 의도·조건부 도주·귀환과 기존 drain commit, 휴면/사망 시 취소를 산출한다.

5. **양방향 칼 전투.** 실제 PC/NPC 스탯·무기·속도·현재 대상과 기존 AttackSession/HP/RESOURCE를 받아 combat 접점을 소유한다. 즉시 공격·명중/피해·실제 반복 계약·반격·양쪽 HP·대상 사망 시 중단을 한 번의 Decision으로 연결한다.

6. **회복·사망 복귀·타이머.** 회복 정책·현재 RESOURCE·피해/죽음·기존 Life API를 받아 `recovery_life`와 해당 후손을 소유한다. HP/MP 회복·원 생명 종료·마을 복귀·새 생명과 deadline을 실제 좌표/자원 저장·예약 정리에 연결한다.

7. **EXP·드롭·줍기·영속화.** genuine kill/Death·보상 표·기존 PROGRESSION/RESOURCE/custody/Store를 받아 `reward_service`와 해당 owner 접점을 소유한다. kill once→EXP/성장·바닥 보상→줍기→캐릭터/자산 저장을 기존 CAS/receipt로 연결한다.

8. **broker 연결·수명·재접속.** 1~7번의 정확 부모/변경분·정상 시작 저장과 기존 broker/client 접점을 받아 공용 broker의 유일 writer가 된다. 의미 입력/출력·가시성 순서·선택 종료/새 선택·성장/장비/전리품 복원을 연결해 재접속 후 다른 NPC와 다음 사냥까지 산출한다.

M1은 **정상 저장→로그인/월드→이동/NPC 선택→칼 공격/반격/HP→처치/EXP/드롭→줍기/회복→사망/마을 복귀→저장/재접속→다음 사냥**을 잇는다. 기존 저장·current·UIDburn·partial을 보존하고 재화 지급·동결 기능 확대는 제외한다. 목표는 원본 클라이언트로 이 순환을 30분 직접 플레이하는 것이다.

기준: [ACTIVE_TASK](../../../docs/ACTIVE_TASK.md), [WORK_RULES](../../../docs/WORK_RULES.md), [재사용표](REUSE_TABLE.md). 설계 작성은 제품 재개가 아니다.
