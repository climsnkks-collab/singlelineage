# Adjudicated lethal RESOURCE zero — exact6f72 private 후손

leaf source_ready:true / test_ready:false / run_ready:false / runtime:UNRUN / WRITER_RELEASED. 실제 lethal0/CAS/drain/recovery PASS가 아니다. 변경 제품은 이 폴더 hp_resource_owner.py 하나이며 부모는 Resource6f7298fc711b2778a570b55f5e5bb1585f98f27e6b43418c3af60bfde1e4738c/78550B다. 원본·foreign Life/Status/Broker·NPC192 Resourceb4는 수정하지 않았다.

## 실제 불일치와 수정

원 Broker의 실제 adjudicated damage>=beforeHP 분기는 같은 원 _Prepared operation으로 Life.lethal_adjudicated_locked를 호출한다. Life cad9:405-426은 실제 NPC policy/동일 Context·operation·Snapshot과 typed PRE 입력을 확인하고 PREPARED _Cycle을 먼저 등록한다. 이어 _zero_death_locked:428-435가 원 NPC ATTACK DRAINED를 확인한 뒤 **바로** status.prepare_player_life(kind=ZERO)를 호출한다. HP를1로 먼저 낮추는 commit은 없다.

HP Status5527:271-297은 beforeHP==1 또는 기존 life.adjudicated_lethal_locked(writer,cycle) proof를 허용하고0을 계산해 원 Resource.commit_hp_locked로 전달한다. 그러나 Resource6f72._verified_hp_producer의 PREPARED 분기는 무조건 beforeHP==1이라 진짜 HP>1 lethal decision도 RESOURCE_HP_LIFE_ZERO_PRECONDITION으로 거절한다. 이는 실행 추측이 아니라 같은 원 호출/값 전달의 source 불일치다. 실제 게임에서 이 경우를 재현했다는 주장은 하지 않는다.

후손은 이 predicate만 `before.current_hp == 1 or service.adjudicated_lethal_locked(writer, producer)`로 바꾼다. HP Status가 이미 사용하는 **원 Life validator**를 Resource의 computed-value authority 경계에서도 사용한다. HP1은 기존 첫 항에서 short circuit하므로 새 validator 호출 없이 원 동작이 유지된다. beforeHP>0만으로 허용하거나 raw boolean/caster/DTO/새권한을 만들지 않는다.

원 Life.adjudicated_lethal_locked:365-367 → _adjudicated_attack_locked:354-363은 실제 Life.hit/NPC service/operation_for의 동일 operation, 그 operation.context.snapshot의 동일 before와 HP>0, ATTACK_DRAINED/transportDRAINED, hp_operation 부재, 기존 immutable adjudication의 landed 및 damage>=beforeHP, 원 service.validate_locked의 실제 current/lifetime을 확인한다. Resource의 기존 nominal Life.Service/Context/_Cycle·같은 registered cycle/context·heldrow·selected Binding·Snapshot identity·quiescence·policy/드레인 검사는 모두 유지된다.

새 Store.restore/participant/lookup/read API를 넣지 않았다. HP>1에서 기존 Life validator가 자신의 원 current 검증을 실행한다는 호출 비용은 있으며, 별도 capture/cache/Store getter 층을 만들지 않았다. validator는 원 저장 adjudication을 읽고 RNG를 다시 돌리지 않는다. commit_hp_locked의 computed0, native prepare/commit/receipt/txid/once/CAS와 restore 경로는 byte 그대로다.

## 실제 API·선정 범위

기존 `ResourceOwner.commit_hp_locked(writer,row,before,*,current_hp,maximum_hp,life_context)` ABI는 그대로다. SourceModule이 선택할 hp_resource_owner descendant만 바뀐다. 의존은 **원 Life cad9의 adjudicated_lethal_locked(writer,cycle)** 및 Status5527의 실제 ZERO 경로다. foreign 새 API 요청이나 shim은 필요하지 않다. required fullpins와 실제 caller contacts는 evidence/selection-fragment/manifest에 있다.

최종 공급자는 exact6f72 family에 이 단일 hunk를 선정한다. NPC192의 Resourceb4는 정확 소스가 이 단위에 공급되지 않았고 이 후손으로 덮을 수 없다. 그 family에 같은 predicate가 남았다면 실제 소유자가 해당 원부모·Life method 계약을 확인한 뒤 이 hunk만 fold한 새 fullpin을 제공해야 한다. 아직 그 variant의 결함/호환성/선정을 주장하지 않는다.

## 최소 확인과 실행 입력

원 source compile(no import), exact 부모 pin, 변경 inverse bytes→부모 완전 동일, 원CRLF 유지, HP1 short circuit와 실제 helper 호출 위치 AST만 확인했다. 기존 숫자/closure/admission/수명 검사 결과는 재사용했다. canonical positive fixture/가짜 Store/Context/RNG 성공 시험은 없다.

최신 supplied saved MOB basis actual186은 HP10/R44다. lawful normal NPC lethal operation과 원 typed PRE/native observer/current death 입력·전체 선정 caller가 아직 공급되지 않아 새 runnable scenario/caller/RUN은 만들지 않았다. HP0/1 강제·state 생성·알려진 DRAIN 실패 prefix 재실행은 하지 않는다. source leaf 수용 뒤 기존 NPC/Life 담당의 정상 packet flow와 호환 Source 선정을 사용해야 하며 별도 guard완화·TTL/clock변경·handler직접호출은 없다. import/NativePlan/Store/profile read·copy/runtime/server/process/ports/queue/directchat 0.
