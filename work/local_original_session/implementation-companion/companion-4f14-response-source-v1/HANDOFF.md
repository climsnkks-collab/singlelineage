# COMPANION-MAGE 4F14 response source 판정

WRITER_RELEASED / source-only / test_ready:false / run_ready:false / runtime UNRUN. **현재 근거로 충실한 응답 builder를 만들 수 없다.** 첫 필수 결손은 child.f6(uint32)의 실제 업무 의미·같은 actor producer·정당 값이다. 선정 표시 body에서 직접 읽지 않는다는 근거로 전체 미사용·0 허용을 주장할 수 없다. DTO/serializer/send를 구현하지 않았다. 이 source blocker는 실행한 서버 오류가 아니다.

## 원 형식과 소비

REA274 최종 main/원schema·required CFG, REA277 nested required/enum, REA279 최종 child/init/commands/resource 계약을 결합했다. sourcepins.json에 원문22파일과 selected coherent graph를 고정했다. 중간274 child 미확정은277 완료본으로 대체했다.

| 영역 | 필드 | 형식/필수 | 확인된 소비 |
|---|---|---|---|
| SC_SUMMON_STAT_ACK 4F14 | f1 | uint32/wire0/required | B215D0→layout+B8/Minion+198→Actor lookup UID |
| parent | f2 | closed-enum int32/wire0/required | 1=PetStatusLayout, 2=SummonedMonsterStatusLayout; 성공코드 아님 |
| parent | f3 | message/wire2/required | child15D7A68 복제·property1 |
| child | f1 | closed-enum int32/wire0/required | 현재상태 표시 enum; canonical1..10 parser 허용, 표시1..8 매핑 |
| child | f2..f6 | uint32/wire0/required | f3/f2→HP label1642, f5/f4→MP label1643, f6 직접 scalar 소비 미선정 |
| child | f7..f10 | optional | uint64 family/int32/int32/string family; 원 type-card/offset은 contract.json |

parent required mask7, child mask22F는 presence index9/0/1/2/3/5로 필수 f1..6이다. `{label}: {f3}/{f2}`, `{label}: {f5}/{f4}`와 HP/MP resource 원문까지 확인됐다. 분자/분모의 current/max 업무명은 선정근거에서 미확정이다. child.f1=1..8 표시는 목표지정/공격/방어/휴식/경계/수집/산개/해산이며 이것이 Host의 FOLLOW/STATION/lifecycle 문자열 매핑을 제공하지 않는다.

4F13 f1은 클릭 actor UID 요청이다. 4F14 f1은 client Actor lookup 역할이 확인됐지만 같은 요청UID echo/원server 동일operation 인과는 미확정이다. 등록 Allied Player를 Summon/Pet layout으로 취급하는 정책도 현재 LOCAL 제품 선택으로 별도 명시해야 한다. 4F14 f2를 status success로 부르지 않는다.

4F02는 별도 CS_PET_COMMAND_REQ: f1 명령 enum required, f2 repeated string(선정 producer 빈목록), f3 storedMinion UID(uint32, schema optional이나 해당 producer present). 공격2/방어3/휴식4/산개7/경계5만 실제 producer 양성이다. target 추가선택/해산확정 이후 C2S는 미공급이며 mode6/가짜payload를 만들지 않는다.

## 선택 server 값과 남은 mapping

Allied d149의 실제 PlayerRegistration에는 발급 actorUID/generation, Host/owner/CharacterLease, selection/row/current selected Binding, placement/frame 및 발급시 RESOURCE digest가 있다. 이는 통계child의 상태/f6 값을 보유하지 않는다. root.current(record)는 원sameHost/선택/lease/current를 확인한다. already-registered만으로 delivery 성공은 아니므로 실제phase DRAINED와 controller active actor UID/generation/current 결속도 필요하다.

현재 숫자는 원 RootPlayers._resource(host,owner,lease)에서 owning row operation과 기존 Store/character/realm locks 안에 root account inventory Batchv3/canonicalv5의 RESOURCE:<lease.uid>를 검증해 읽는다. 원child history/record.resource_digest의 발급시 cache·generation만으로 현재HP/MP를 대체하지 않는다. server_snapshot은 actual actor/alive/spawn_drained를 주지만 네 숫자를 모두 내보내지는 않는다. lease.uid는 저장캐릭터, record.uid는 별도발급 actor이며 교환하지 않는다.

RESOURCE는10/11/12/13의 signed32이며 HP는0<=10<=11,11>0 검사가 있다. MP의 gameplay min/max는 이 schema로 확정되지 않는다. uint32 child로 음수를 감싸거나 clamp/0으로 바꾸면 안 된다. 원수치가 있다는 사실과 f2..f5의 정확 업무 대응은 구별해야 한다.

후속 최소 공급은 버전고정 same-operation record 또는 별도 명시·검토된 LOCAL 정책으로 parent와child1..6 모두의 같은actor 업무값을 결정하는 것이다. 특히 f6 producer/값, child상태 enum, HP/MP 순서, registeredAllied와layoutkind를 닫아야 한다. 이후 순수 serializer는 원current/한번의RESOURCE read로 받은 typed 값만 직렬화하며 발급/등록/current/send/drain을 만들지 않아야 한다. Native UI current installation/ownerthread/렌더·입력 성공은 여전히 별도다.

## 최소 확인

verify_contract.py 한 번: 정확22source SHA/bytes, parent3필수, child1..6/mask22F, requiredf6 uint32와 blocked분류 PASS. 제품 import/새REA/서버/사본/저장/공용/Broker/shared/client/Test/기성private/큐 변경0이다. 새 폴더의 contract.json/sourcepins.json/verification.json만 근거로 삼는다. 실행caller/RUN_COMMAND를 시험ready로 공급하지 않는다.
