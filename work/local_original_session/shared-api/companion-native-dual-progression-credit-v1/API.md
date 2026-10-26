# Native 동료 EXP 두 수혜자 경계 v1

구현 Source는 `canonical_batch.py`, `item_uid_namespace_root.py`, `companion_native_dual_progression.py` 세 파일이다. 실제 게임/Store profile/packet 실행은 **UNRUN**이다. 기존 Allied kill reader는 현재 읽기만 제공하고 정당한 allied 보상 자격·두 수혜자 성장 stage를 제공하지 않는다. 따라서 이 패키지는 **native Source 경계 완성 / 전체 source_ready=false / test_ready=false / run_ready=false**이다. 아래 foreign Source와 실제 caller가 공급되기 전 임의 fixture나 숫자로 실행하지 않는다.

## 선택과 소유

- Core 부모6041eb5d와 Root 부모78f0d95d의 private 후손이다. `account_canonical.py`03340f72와 policy7af8은 그대로 쓴다. canonical inventory/members/origins/cursor에 EXP 필드를 추가하지 않는다.
- 실제 `tools.local_original_session.canonical_batch`, `tools.local_original_session.item_uid_namespace_root`, `tools.local_original_session.companion_native_dual_progression` nominal 이름으로 같은 classspace에 선택한다. source bytes/module/class/function/code/default anchors와 실제 등록 owner/current를 함께 검사한다. source 해시만으로 kill/EXP 권한을 만들지 않는다.
- Root `Setup(..., dual_progression_source=(module, absolute_Path, sha256))`는 새 선택 슬롯이다. `None`일 때 기존 경로는 유지된다. `dual_progression_current(owner, binding, companion, store)`는 기존 Root current를 두 번 사용하며 실제 owner Binding, issuer가 발급한 companion Binding, 같은 account/operation scope/task/lease를 요구한다.
- native Source는 native transaction/잔여 schema만 소유한다. COMBAT progression/document/math, HP RESOURCE, 동료 scheduler/kill/caller, Broker/Factory/Store bootstrap, Test client와 ready_current는 원소유 파일을 변경하지 않았다. 정확 후속은 `consumer-contract.json`에 있다.

## 저장 표현과 초기화

기존 v3 batch envelope의 `participants['EXP-HALF:<character_uid>']`에 저장한다.

```json
{"revision":0,"digest":"<sha256(document)>","document":{"schema":1,"policy":"NATIVE_ALLIED_EXP_EQUAL_HALF_CARRY_V1","uid":1,"revision":0,"half":0}}
```

`half`는 **해당 recipient UID에 귀속된 반단위 잔여**이며 정수0/1만 허용한다. PC carry와 companion carry는 독립적이다. owner1/new-companion0 같은 이력도 보존한다. 두 row의 revision은 각 document revision과 같고 digest는 실제 document digest이다. 없음·부분없음·기존 임의 JSON 필드는 `NATIVE_DUAL_HALF_CARRY_UNKNOWN`이며 0으로 만들지 않는다. 새 companion의 아직 없는 carry도 자동0으로 간주하지 않는다.

초기 0을 만드는 유일한 API는 `initialize_half_carry_locked(binding, companion_binding, *, creation_receipts)`이다. `creation_receipts`는 pair 순서의2-tuple이다. **carry absent인 수혜자만** 같은 실제 Root 원발급 `_CreatedCharacterRecord`·원 `CREATE` event·현재 원저장/등록 record 일치, 실제 PROGRESSION revision0/exp0/level1, reward marker없음, 기존 비ABORTED progression/carry transaction없음을 증명해야 한다. **이미 carry가 있는 수혜자는 receipt=None**으로 표시하고 실제 saved row의 uid/revision/digest/document를 그대로 read-only anchor로 보존한다. owner carry1 + 새 companion absent이면 `(None, genuine_companion_create_receipt)`로 새 companion0만 만들며 owner의 EXP/carry/revision은 재생성하지 않는다. 양쪽 absent이면 두 genuine CREATE receipt가 필요하고, 양쪽 present이면 restore를 사용한다. 누락된 과거 이력·import·legacy/adoption은 지원하지 않는다. 이는 새 CREATE provenance에 따른 명시적 초기값이며 restore의 기본값이 아니다. 해당 provenance가 없으면 초기화 UNKNOWN이다.

초기화도 한 native reservation과 기존 Core final replace로 두 row를 같이 저장한다. 초기화는 EXP나 성장 RESOURCE를 변경하지 않는다. `recover_created_character`의 SELECT origin은 CREATE로 바꾸지 않는다. 이미 carry가 있는 pair에는 초기화를 호출하지 않는다.

## Cold 구성 순서

1. 위 세 Source와 기존 codec/policy/COMBAT document·split·실제 feature Source를 원 loader가 선택한다. 임의 monkeypatch/별도 classspace를 만들지 않는다.
2. `native.carry_capability()`와 `native.NativeDualCatalog()`를 만든다. catalog의 `entries()`가 돌려주는 세 새 participant tuple을 기존 `ParticipantCatalogOwner`에 추가한다. 기존 solo PROGRESSION/RESOURCE/PC/SHOP/SKILL catalog owner는 유지한다.
3. 원 bootstrap이 실제 provider/BatchStore를 만들고 Root를 attach한다. PROGRESSION capability는 원 document validator와 transition을 사용하고, 실제 foreign `AlliedProgressionOwner.authorize_progression`이 원 solo 경로와 새 native pair stage를 각각 인증해야 한다. RESOURCE capability는 원 HP Source authority를 유지한다.
4. `NativeDualProgression(provider, store, *, split_source, document_source)`를 만든다. 두 source 인자는 `(module, absolute_Path, sha256)`이며 각각 원 split11c63c37, document7c8f8a83을 요구한다. constructor는 실제 attached Root/Core/Store를 검사하고 단일 native owner로 등록한다.
5. `bind_carry_capability(native_owner)`와 `bind_native_catalog(native_owner, catalog)`를 한 번 호출한다.
6. 실제 소스가 존재할 때만 `register_sources(...)`를 한 번 호출한다. provider가 아직 selected binding을 갖지 않은 cold 단계여야 한다. 현재 부족한 future Source의 경로·해시를 발명하지 않는다.

`register_sources`의 키워드는 `kill_reader, kill_source, reward_owner, reward_source, projection_owner, projection_source, resource_owner, resource_source`이다. 각 source는 동일한 source triple이다. 모든 instance는 선택 nominal class의 정확한 type, 모든 method는 해당 원동기 class method여야 한다. reward/projection/resource owner의 store/provider는 이 native Store/provider와 같아야 한다.

새 native catalog tuple은 `('EXP-HALF',)`, `('EXP-HALF','PROGRESSION')`, `('EXP-HALF','PROGRESSION','RESOURCE')`이다. digest는 `core.digest(dict(policy=native.POLICY, progression_policy=original_document.POLICY, participants=names))`다. 실제 stage/current를 검사한 원 NativeDualCatalog만 이 값을 공급한다.

## 실제 정상 호출

모든 locked API는 원 operation scope를 보유한 같은 owner/companion current Binding으로 호출한다. 다른 잠금/가짜 Binding/fixture kill을 만들지 않는다.

```python
# 원 정상 inbound/login/select/WORLD/동료 current/실 allied kill 이후
carry = native_owner.restore_half_carry_locked(owner_binding, companion_binding)
cap_or_history = native_owner.prepare_credit_locked(
    actual_allied_result, binding=owner_binding,
    companion_binding=companion_binding, carry=carry)
if type(cap_or_history) is native.DualCreditCapability:
    result = native_owner.commit_locked(cap_or_history)
else:
    result = cap_or_history  # historical outcome: read/recover only
outcome = native_owner.result_locked(result)
```

`restore_half_carry_locked`의 native-issued proof에는 실제 saved rows/revisions/digests/raw preimage와 두 원 Binding identity가 묶인다. 숫자 DTO·다른 owner proof·수정된 proof·stale raw는 거절한다. `prepare_credit_locked`는 숫자 pool/EXP/HP/잔여를 인자로 받지 않는다.

`prepare_credit_locked`는 원 reader를 호출하고 원 result/receipt/operation/accepted ordinal/actor/owner/companion/target을 묶은 server-side request bytes와 `DUAL-EXP:<original_operation_id>`를 만든다. 이것은 C2S packet을 발명한 것이 아니다. 기존 같은 receipt가 있으면 **projection/growth RNG 전에** historical result를 반환한다. 같은 operation의 원 solo `PROGRESSION:<operation_id>` transaction이나 marker가 있으면 복구/기award 거절로 끝낸다. 외부 qualifier는 같은 original receipt/operation identity의 공유 winner/자격을 증명해야 하며 alias가 다른 operation을 같은 kill로 인정할 근거를 만들지 않는다.

두 독립 residue는 원 split 함수를 각각 자신의 residue를 두 입력에 동일하게 넣어 재사용한다. native `DualHalfSplit(pool, owner_before_half, companion_before_half, owner_grant, companion_grant, owner_after_half, companion_after_half)`에 필요한 출력만 결합하고 전체 반단위 보존식을 검사한다. 기존 equal-history 함수를 고치거나 legacy alternating parity를 사용하지 않는다. 이 DTO는 숫자이며 보상권한이 아니다.

foreign projection은 원 progression math/level/growth 계산과 두 수혜자의 실제 current/resource proof를 공급한다. native는 각각 원 PROGRESSION validator/transition·정확한 `before.exp + grant`·예상 revision/digest를 검사한다. level이 오르면 해당 수혜자의 실제 growth proof와 RESOURCE document가 필수다. level이 오르지 않으면 RESOURCE 변경/growth proof와 base max 변경을 거절한다. 둘 중 한쪽이라도 MAX_EXP/Java int/level 지원 범위를 넘거나 clipped grant가 되면 **pair 전체를 PREPARED 전에 거절**하고 잔여를 그대로 둔다. 한쪽 포화분 소실/다른쪽만 credit은 지원하지 않는다.

## 한 native transaction

`BatchStore.prepare_dual_progression(binding, capability)`는 native 원발급 live capability만 소비한다. 두 PROGRESSION·두 EXP-HALF·필요한0/1/2 RESOURCE의 CAS와 actual current를 검사하여 같은 plan을 만든다. PREPARED replace는 원 participant/asset 값을 변경하지 않고 한 transaction/pending만 보존한다. 그뒤 기존 `Reservation` 하나가 발급된다.

기존 `BatchStore.commit`은 같은 reservation/plan/source/current/두 asset revision/모든 participant preimage/원 kill/qualification/growth stage를 다시 검사한다. 기존 `_replace` 한 번에 두 recipient의 변경·두 asset revision+1·reward markers·COMMITTED receipt·pending 해제를 저장한다. canonical inventory 값은 그대로다. PROGRESSION marker에는 native dual once 외에 원 `PROGRESSION:<operation_id>` alias를 **같은 commit**으로 추가한다. 핀된 원 solo owner의 정확한 marker guard는 이후 같은 operation을 거절한다. 실제 선택된 foreign solo consumer도 그 원 guard를 보존해야 하며 다른 family/runtime에서 증명된 것으로 확대하지 않는다.

일반 `BatchStore.prepare`로 EXP-HALF를 따로 변경할 수 없다. 원 generic participant/CAS/PC/None/quantity/credit/transfer 경로를 두 독립 credit으로 호출하여 원자성을 주장하지 않는다.

## 결과·전달·부분보존·복원·퇴역

- `DualCreditResult`는 private-issued identity다. `result_locked(result)`는 현재 durable receipt와 역사 여부/request bytes를 읽는다. packet write나 restore authority가 아니다.
- `require_committed_projection_locked(result, *, projection, binding)`는 원 newly committed result, 같은 foreign stage, 두 current Binding, 같은 COMMITTED receipt와 모든 현재 participant digest를 검사해 원 result를 반환한다. foreign 실제 delivery owner가 이 native parent를 검증해야 한다. 기존 `DeliveryCapability`/`open_delivery`·WRITE_ATTEMPTED·DRAINED·UNKNOWN·원 wire/수신 경로를 그대로 사용한다. native가 wire/성장응답/송신을 만들지 않는다.
- historical/recovered result는 위 committed projection parent가 될 수 없다. duplicate를 이유로 재prepare/reward/재송신하지 않는다. 저장된 UNATTEMPTED를 임의 DRAINED로 바꾸지 않는다.
- final replace/write/readback 오류는 기존 Core의 failed/ambiguous 상태를 보존한다. durable PREPARED 또는 COMMITTED와 이미 변경된 양쪽 값은 rollback/refund/reset하지 않는다. caller는 첫 오류·원문·partial·현재 저장·UIDburn을 보존하고 원 finally/close를 수행한다.
- `recover_locked(binding, companion_binding, *, txid, request)`는 원 exact pair receipt를 읽는 historical native result만 발급한다. 새 current를 만든 뒤 PREPARED라면 기존 `abort_recovered_prepared`만 명시적으로 사용할 수 있다. EXP 재award는 하지 않는다. COMMITTED 뒤 fresh `restore_half_carry_locked`는 실제 현재 두 row에서 새 proof를 발급한다. row 없으면 UNKNOWN이다.
- `retire(cap)`는 아직 ISSUED인 native cap만 해제한다. PREPARED는 원 native abort 또는 close/recovery가 필요하다. Core abort는 원값을 유지하고 native cap을 퇴역시킨다. `retire_result(result)`와 `close()`는 native memory만 해제한다. close는 PREPARED/COMMITTED/UNKNOWN을 수정하지 않는다.
- foreign projection/HP stage의 RNG/부분산출물/두 live growth resource stage는 foreign 원소유가 original finally에서 해제한다. projection 도중 첫 예외, native cap 발급 전 검증실패, native retire/abort, commit후 delivery실패 모두 포함한다. native는 외부 stage를 추정 재생성/rollback하지 않는다. 동료 실제 caller의 finally/RUN/판정/정리까지 공급되기 전 실행 ready가 아니다.

## 확인과 미완 경계

```powershell
python work/local_original_session/shared-api/companion-native-dual-progression-credit-v1/check_native_source.py
```

이 RUN은 Source 순수 검사 전용이다. parent AST 보존, 실제 재사용 split과 독립 잔여, schema/absence/stale proof/solo once, 실제 Core 메서드의 **in-memory reducer**에서 한 reservation·두 growth/carry CAS·원자 변경·abort/ambiguous 보존을 검사한다. in-memory authority port는 명시적 test double이며 원 kill/current/native authority/runtime PASS가 아니다. native profile/game/ports/packets/fixture kills0이다.

gameplay RUN_COMMAND는 null이다. 필요한 실제 same-classspace AlliedKillReader 후손, 정당 allied reward qualifier/shared once identity, 두 recipient PROGRESSION/HP source stage와 projection/delivery·restore caller, loader/cohort/current/input/RUN/판정/정리가 아직 없다. 다른 ready 작업을 이 미준비로 막지 않는다. old166 hold·원본/기성PASS/current/partial/UIDburn·Test 독점실행·공식 단일큐·직접ACK0·종료전 잠금snapshot 규칙을 승계한다.
