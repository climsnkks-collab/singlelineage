# COMPANION-MAGE account-v5 allied publication v1

WRITER_RELEASED / private source_ready:true / run_ready:false / test_ready:false / runtime:UNRUN.

동일 immutable 부모 Allied publication `4d15444513594461e40de8c2c552d299c55bd43357d1c410479b2fbe7220b242` 위 두 read 메서드와 prepare의 호출부만 바꿨다. 정확 account Batch `86c0d7d13a9649840cc875c8368b96d9ef698c02dd1241fcd1998063be14c0e9`를 요구한다. core/Store/Host/root와 전체 cohort는 부모 account-v5 source를 참조하며 이 폴더에서는 수정·새 선정하지 않았다.

## 실제 변경

`RootPlayers._resource`는 원 `operation(host,owner,lease)`의 실제 selected owner/lease/current/row/lexical scope를 보존한다. 같은 root.provider/root.store와 실제 broker의 ResourceOwner/Batch/InventoryStore·account profile/path/lock을 일치시킨다. 원 BatchStore._current(binding)를 원 Store/character/realm lock 아래 소비해 실제 account v5 live members와 `participants['RESOURCE:<lease.uid>']`만 읽는다. original ResourceDocument validator·digest/uid/revision·pending guard를 유지하고 필요한 HP/MP 필드만 복사한다.

child history의 inventory/CharacterStore를 다시 열거나 origins를 current로 쓰지 않는다. 새 Binding·Store·RESOURCE participant·상태 파일을 생성하지 않는다. pre-publication이므로 아직 존재하지 않는 active CompanionBinding도 발급하지 않는다. 실제 root selected binding과 이미 발급된 같은 계정의 retained companion CharacterLease가 읽기의 권위다. 원 `_current`가 `_OWNERS`·profile/path·실제 preimage/data/current를 계속 확인한다.

초기 prepare에서만 `check_collisions=True`를 주며 원 `_reserve` 전 같은 검증된 account 문서를 collision scan에 전달한다. `canonical.members`의 실제 live v4 member domain·stack UID·original/credit prototype frames와 실제 account roster/next_uid·NPC UID를 확인한다. Batch가 이미 검증한 member shape를 다시 전체 decode하지 않고 충돌 판정만 한다. child/origins를 중복 live inventory로 검사하지 않는다. 다음 snapshot RESOURCE read에는 이 issuance scan을 반복하지 않는다.

원 별도 allied namespace `0x30000000..0x3000ffff` cursor 잠금·monotonic CAS/실패 burn/고갈 거부는 byte/AST 그대로다. `operation`, 등록/current, 실제4E96/4E40 DTO와 send/drain·server_snapshot/close·retire_owner/absenceFalse/poseNone도 그대로다. account itemcursor와 allied cursor를 같은 allocator라고 부르지 않는다.

## 확인

```powershell
python -B work/local_original_session/implementation-companion/companion-allied-account-v5-v1/verify_source.py
```

12개 focused source/cold/pure 조건 PASS. 부모 대비 `_resource`/`_collision_check`/prepare만 AST가 바뀌고 prepare는 새 keyword/통합 scan 호출을 되돌리면 원 AST와 같다. 원 allocator·registration/transport/수명은 불변이다. 기존 account graph의 cold import만 수행한 뒤 실제 Test PASS account JSON의 두 live member를 원 codec으로 읽고 새 **정확 pure member scan**을 실행했다. domain overlap·reserved stack UID를 넣은 명시 scalar fixture는 각각 원 충돌 코드로 거부됐다. frame/credit/NPC predicate는 그대로다.

live Root/Host/owner/lease/Batch/Store/Plan 생성·current RESOURCE 호출·UID 예약/파일쓰기·packet/send/서버/포트는 0이다. 첫 source 검사에서 docstring의 origins 단어를 executable archive access로 읽은 assertion만 AST subscript 검사로 고쳤다. 제품 동작 우회는 없었다. 기존 cursor/minion/source 검사·actual account-v5 정상2→1→2 PASS는 재실행하지 않았다. 원 result96e8ec02/accountinventory57842ab0 hash는 전후 같다.

## 통합·실행 경계

이 source는 **한 publication callee 후손**이며 coherent account+actor-only graph/runnable이 아니다. 실제 같은 account-v5 nominal core/source 공간에서 allied row를 이 파일로 선정하고 Setup.allied_player_source와 해당 actor-config의 exact source seal을 후속 통합 담당이 결속해야 한다. 원 Broker/Peer/Server tuple은 그대로 유지한다. 미준비 actor-only Factory/scope-token·fresh callback/Host 수명·실제 summon caller/normal input·native pose/absence/UI를 이번 파일로 해결했다고 주장하지 않는다.

향후 정상 순서는 원 계정 login/roster→root UID1 WORLD/current→원 Host가 실제 다른 UID2 lease를 발급→이 source의 같은 root RESOURCE/충돌 scan→원 monotonic 예약·Player DTO 등록→원 send/drain이다. 최종 행동을 먼저 보내거나 handler를 직접 호출하는 시험은 없다. test_ready는 false이고 packet caller/RUN_COMMAND는 여기서 만들지 않았다. main이 실제 delta/핀·다른 worker의 source ownership을 검토해 완료 source만 큐에 등록한다. 공용/ITEM/이전 private/원저장/Test copy·queue/port/REA 수정·실행0이다.
