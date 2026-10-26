# Companion same-operation Broker source v1

공용 Broker Source component만 완결했다. `source_component_ready=true`,
`feature_ready=false`, `test_ready=false`, `run_ready=false`, runtime `UNRUN`.
동료의 실제 DEFEND 실행·scheduler·공속·Heal0·첫 소환 PASS를 발급하지 않는다.

## 정확한 부모 선택

직접 제품 부모는 기존 event-hook-v2 Broker
`b0fea98ae51e1a8378a9cfa3ed5590219ce5c6ed16c44a5df3561caf0ade919c`
/419649B다. 이 Source는 기존 선택 기준 Broker
`6e703872e79a8b15e9ef9c92442521d93b6ff5c30091c0dd11068bc6f6976a2f`
/412030B의 후손이며 ASSIST post-drain hook을 이미 가진다.
6e703은 원 motion cohort의 실제 선택 기준, b0fe는 그 후속 private event-hook
제품으로 역할이 다르다. 새 Broker는 b0fe를 그대로 계승하여 `_serve`와 기성
ASSIST를 재구현하지 않는다. 기존 event-hook-v2의 STOPPED 기록과 파일도 수정하지
않았고, 최신 인간이 허용한 새 독립 Source만 공급한다. old166hold/SENT/옛시험의
재개나 blanket family overlay가 아니다.

Peer는 원 같은 family d21628ea/28093B, Server는84348db8/21443B를 바이트 동일하게
복사했다. Peer.bind가 실제 `_accept.__code__.co_filename`을 sibling broker.py와
비교하므로 새 Broker와 같은 폴더의 Peer를 선택한다. 실제 Port58f39802는 원
경로를 유지한다. source selection/fullpins는 이 정확한 부모와 필수 후손만 제시한다.
동료 Host·COMBAT·Native Store·공용 client는 수정하지 않았다.

## DEFEND: 원 body의 실제 return 뒤, 같은 원 operation

기존 호출 서명은 변하지 않는다.

`PersistentBroker._attack_player_current(self, writer, *, service,
expected_context, raw_effect, direction, repeated, retaliation_lease=None,
continuous_lease=None)`

새 bounded inner callee는 실제로 구현했다.

`PersistentBroker._attack_player_current_locked(self, writer, row, *, service,
expected_context, raw_effect, direction, repeated, retaliation_lease=None,
continuous_lease=None)`

원 outer가 원 single claims row를 고르고 **한 번** `_row_operation`을 열어 inner를
await한다. inner는 원 `_attack_player_current`의 held-row body와 원 UNKNOWN catch를
그대로 옮긴 것이다. 새 진입 검사는 같은 writer/held lock 및 원 canonical task를
요구한다. inner에서 lock이나 provider scope를 새로 얻지 않는다.

원 Service.prepare/build/첫 ATTACK send/drain·판정/RNG·STATUS/native HP·Result 생성,
lethal 분기, lease validation, error의 fail_active_hp/terminal/row failed/
NPC_PLAYER_HIT_OUTCOME_UNKNOWN 처리는 원 body와 같다. 원 body가 실제 Result를
return한 뒤에만 outer가 아래 검사를 수행한다. 이 callback은 inner의 try/catch
바깥이므로 동료 callback 오류/취소를 이미 commit된 주인 HP의 UNKNOWN으로
재분류하지 않는다. 오류를 삼키거나 가짜 feature 성공으로 바꾸지도 않는다.

callback은 Host가 있고 actual nominal `npc_player_hit.Result`이며
`before.current_hp > after.current_hp > 0`인 경우만 대상이다. 실제 selected
CompanionHost/Service, Broker/Realm 동일성, 같은 expected_context, 원 operation의
result identity와 `COMMITTED`, ATTACK/HP 두 `DRAINED`를 요구한다.
`result.require_current_locked(writer)`는 원 Service.validate_result_locked로 실제
current Result를 재확인한다. 정상 이후 다음 **기존 Host symbol**에 전달한다.

`await CompanionHost.after_owner_positive_hit_locked(writer, result)`

주인 miss/zero HP 변화·lethal/Life result는 이 positive-nonlethal DEFEND callback에
들어가지 않는다. 반환값은 여전히 원 Result 자체다. 새 callback registry·marker·
속도·timer·반복·권위 bool은 만들지 않았다. 기성 caller의 last_combat_hit once,
실 mode/current actor/lease·COMBAT admission은 동료/COMBAT 원 소유가 보존한다.

## 원 Host가 소비해야 할 실제 계약

읽기 전용 event-hook-v2 Host83967b8e의
`after_owner_positive_hit_locked(self, writer, hostile_hit)`는 현재 `_row(writer)` 뒤
**`COMPANION_DEFEND_POST_RETURN_SAME_OPERATION_SOURCE_UNSUPPLIED`를 명시적으로
raise한다.** 새 Broker가 원 post-return/same-operation seam을 공급했다는 이유로
그 foreign Host를 고치거나 거절을 성공으로 해석하지 않았다.

원 동료 owner가 자신의 새 Host 후손에서 이 **동일한 두 인자**를 소비해야 한다.
호출 시점은 inner의 원 native COMMITTED/STATUS DRAINED return 후이면서 outer의
원 canonical row scope가 아직 살아 있는 지점이다. 다시 `_row_operation`을
획득하면 원 `BATCH_OPERATION_SCOPE_ALREADY_ACTIVE` 거절이므로 금지한다.
기존 CompanionCombatCaller.after_owner_positive_hit_locked는 actual nominal
Result/current·같은 owner UID/map·positive nonlethal·모드 DEFEND·현재 actor/lease·
last_combat_hit once와 COMBAT.defend_locked를 이미 구분한다. 이 task는 그 caller를
재작성하거나 unavailable cold COMBAT owner를 설치하지 않는다.

Host callback이 실패하면 원 operation/result/HP 저장과 원 first failure/partial을
그대로 보존해야 한다. Host는 자기 동료 실패를 따로 판정하며 주인 HP rollback,
RNG replay, status 재전송, 원 Result의 terminal/UNKNOWN 재분류를 하면 안 된다.
원 `_row_operation` finally의 scope-chunk 정리와 canonical task release는 callback
예외/취소에도 그대로 실행된다. Host의 기존 partial cleanup gate와 actor/lease
퇴역 소유권도 유지한다.

## 최초 소환: 별도 완료 contact 소비

`summon-contact/contact.json`과 그 API는 별도 Source-contact worker의 완료본이다.
원 selected6e703에 이미 **LOCAL F101 empty 요청→정상 decoder/route→Hostd149→
Controller18c→Allied37a8 실제4E96 publication** 경로가 있음을 확인했다.
이 새 Broker는 그 실제 경로를 바이트/AST 그대로 보존하며 복제하지 않는다.
이것은 임시 LOCAL 계약이고, 원 native UI/hotkey inbound publisher가 공급됐다는
뜻이 아니다. 설정4F13·직접 Host/Controller 호출·과거 dismiss/remove 결과를
첫 소환 수신 증거로 승격하지 않는다.

원 COMP01 owner가 완료 contact를 소비하여 실제 cold 선택/LOCAL enable, 정당한
현재 account와 다른 saved mage, 정상 login/선택/WORLD 뒤 F101, issuer4E96/
actor/resource/pose/current 실수신·판정·strict close/fresh와 실행 가능한 caller/
RUN을 마감해야 한다. 이번 Source에는 실제 게임 RUN이 없다.

## 최소 검사와 보존

`SOURCE_CHECK_COMMAND.txt`는 Source-only 검사 명령이다. 바뀐 원 outer/inner와
바이트 동일한 원 `_row_operation` AST를 inert memory ABI adapters로 실행한다.
실 Result/_Prepared/Service class space·원 Host 거절 메서드를 사용한다. 양성
callback·오류·취소·scope reentry 거절·stale current/foreign Host·miss/lethal·원
send 실패와 실제 finally 경계를15개 검사했다. 원 `_serve`, ASSIST, once/repeated
caller, summon body·원 UNKNOWN try가 동일하고 전체 b0fe byte inverse가 일치한다.
Native current/Store/프로필/process/socket/packet/RNG/동료 행동 실행은 하지 않았다.
기성64검사나 old movement/native suites를 다시 돌리지 않았다.

Source component 공급과 feature readiness를 분리한다. Host 후속·COMBAT own-speed/
cadence·scheduler/cold owner·coherent current/cohort/scenario/caller/RUN/정리가
완료되기 전 feature/test/runfalse다. old166hold/기성Source/SENT·원결과/partial/
current/UIDburn·Warehouse/BOOK/Pro의 별도 소유/보류를 유지한다. 공식 큐 등록은
독립 review 뒤 main이 담당한다. 이 worker는 외부 메시지/큐/타폴더 쓰기0이다.
