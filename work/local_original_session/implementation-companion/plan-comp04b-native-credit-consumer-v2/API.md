# COMP-04B 실제 Native EXP 소비 leaf v2

Native transaction/schema는 **공급됨**. Core `0e5ddc77`, Root `0df9c702`, Native
`a8cb9bec`, manifest `b96a54c7`를 Root 수용 Source 그대로 소비한다. v1의
“native 미공급/심벌 미정”은 이 새 범위에서 해제하며 v1 파일은 수정하지 않는다.
`product_delta_ready:true`, coherent `source_ready:false`, `test_ready:false`,
`RUN_COMMAND:null`, runtime `UNRUN`.

## 실제 leaf API

선정 nominal `tools.local_original_session.companion_native_dual_progression`의
실제 `NativeDualProgression` 인스턴스, 원 operation scope를 계속 보유한 두 원
Binding, 원 `AlliedAttackResult`가 입력이다. leaf는 SourceModule/loader/native
instance/Binding/operation/receipt/cap/proof를 만들지 않는다. 실제 nominal class의
메서드를 직접 호출하며 instance callback으로 바꾸지 않는다.

```python
with credit_operation_locked(native_owner, real_allied_result,
        binding=owner_binding, companion_binding=companion_binding) as observed:
    # observed.result: 같은 Native가 발급한 result를 이 scope 안에서만 빌린다.
    # observed.outcome: Native result_locked가 읽은 원 receipt/historical/request.
    # 이 leaf에는 delivery 호출이 없다.
    pass
```

호출은 정확히 `restore_half_carry_locked` →
`prepare_credit_locked(original_result, same bindings, native carry)` →
**원 반환값이 `DualCreditCapability`일 때만** `commit_locked` 1회 →
`result_locked`다. Native가 반환한 historical `DualCreditResult`는 커밋 없이
읽는다. 원 native source가 실제 kill/qualification/current/once/projection/한
reservation/CAS를 인증한다. leaf는 숫자 EXP/pool/carry 또는 eligibility bool을
받지 않는다. 이미 저장된 recipient별 독립 잔여를 그대로 복원한다. missing carry는
원 `NATIVE_DUAL_HALF_CARRY_UNKNOWN`; 기본0/legacy parity로 바꾸지 않는다.

`recover_operation_locked(native_owner, binding=..., companion_binding=...,
txid=original_txid, request=original_request)`는 `recover_locked`→`result_locked`
만 호출하는 별도 역사 관측 context다. PREPARED/UNATTEMPTED를 이유로 credit,
prepare, commit, projection/growth RNG 또는 전송을 호출하지 않는다.

`restore_saved_half_carry_locked(native_owner, binding=..., companion_binding=...)`
는 새 current의 실제 saved rows를 Native에 읽혀 원 `RestoredHalfCarry`를 그대로
돌려준다. proof 수명·폐기는 Native의 원 lifetime close/성공 credit에 속한다.
원 CREATE 영수증 없는 absent row를 이 helper가 초기화하지 않는다.

## 결과 수명·부분 보존

두 context의 finally는 빌린 result를 `retire_result`로 memory에서만 해제한다.
result는 context 밖에서 delivery/reward/restore authority가 아니다. native의
`result_locked` 자체도 `delivery_authority:false`, `restore_authority:false`다.
역사 결과의 재전송은 금지하며 UNATTEMPTED를 DRAINED로 바꾸지 않는다.

`commit_locked` 진입 전 사용하지 않은 definite ISSUED cap만 `retire`할 수 있다.
진입 뒤 예외는 ISSUED/PREPARED/COMMITTED/ambiguous 여부를 추측하지 않는다.
leaf는 그 cap을 retire/abort/재commit하지 않고 원 native owner finally/strictclose/
fresh recovery에 보존한다. Native.close는 attached lifetime 소유자가 수행하며
leaf가 공유 owner 전체를 닫지 않는다. close 자체도 durable 상태를 바꾸지 않는다.

첫 예외는 원 객체/traceback 그대로 re-raise한다. result retirement도 실패하면
원 예외에 cleanup note만 붙이며 최초 오류를 대체하지 않는다. 원 durable partial,
raw current/FIRST/UIDburn/원본은 소유자가 보존한다. refund/reset/rollback/retry0.
foreign projection/양 growth stage는 COMBAT 원소유자의 **outer original finally**가
원 RNG/projection 초기 실패·native cap 전 실패·commit/delivery 실패·성공 모두에서
정리한다. 실제 ABI가 공급되지 않은 cleanup 함수를 leaf가 발명하지 않는다.

## 공급된 원계약과 실제 잔여

아래 경로 기준은 `work/local_original_session/`이며 절대경로·전체 해시는
`parents.json`과 `required-inputs.json`에 보존한다.

| 소유 | 원접점/단계 | 현재 범위 |
| --- | --- | --- |
| Native01a172cd | `shared-api/companion-native-dual-progression-credit-v1/` 실제3Source/등록/restore/prepare/commit/result/recover | 실제 공급·Root 수용 완료. 구현 재발주·미공급 gate 없음. |
| COMBAT01a16b89 | `consumer-contract.json` COMBAT-KILL-IDENTITY: `AlliedKillReader.current_kill_locked(actual_result)` | 기존 COMP04A 후속에서 원 실kill/result/receipt/op/current를 인증. 이 leaf는 DTO나 kill을 재구성하지 않는다. |
| COMBAT01a16b89 | COMBAT-LAWFUL-ALLIED-REWARD: `AlliedRewardOwner.qualify_kill_locked/require_current_locked` | 원 lawful pool·공유 once/winner·같은 receipt/op 보존. 기존 배정 진행, 중복 구현0. |
| COMBAT01a16b89 | COMBAT-DUAL-PROGRESSION: `AlliedProgressionOwner.project_locked/require_projection_locked/authorize_progression` | 두 PROGRESSION/current/growth stage. 실제 최종 Source/cohort 수신 뒤 nominal 등록에 사용; 미래SHA/field 발명0. |
| COMBAT의 명시 최소 HP 후손 | HP-DUAL-GROWTH: `ResourceOwner.require_dual_progression_locked`; 원 `progression-level-delivery-v1/.../hp_resource_owner.py` 1de79 | 별도 원담당 최소 후속, 일반 HP 재배정0. 두 recipient RESOURCE/delivery/cleanup은 원소유. |
| Companion01a16769 | 이 caller: original held operation/actual AlliedResult/두 원Binding/restore/fresh 관측 | Native leaf 구현 완료. 실제 Host kill hook/packet caller/cohort 연결은 아직 선정되지 않아 실행 준비 아님. |
| 원 Broker/Factory/Store loader | BOOTSTRAP-CALLER-TEST: 같은 Source family·Root dual_progression_source·catalog carry/cap bind·원 foreign instances register | 구체 파일/원담당은 Root final 소비 선정에서 명명해야 한다. 이 Source 수신은 외부 파일 쓰기 배정이 아니다. old6041 family 통째 교체0. |
| 원 registered delivery owner | Native `require_committed_projection_locked(result, projection=original_stage, binding=original_binding)` 후 기존 DeliveryCapability/open_delivery/write/drain/UNKNOWN | 실제 delivery method/file/final Source 미선정. leaf는 callback·wire·가짜 DRAINED를 만들지 않는다. 새 commit result가 있어도 이것을 공급하기 전 full 실행 ready 아님. |
| Test01a16d46 | 실제 saved pair/carry 또는 genuine CREATE provenance, 정상 packet/current/real kill/RUN/strictclose/fresh | Test 독점 실행. 이번 worker는 Store/game/socket/profile/packet0. |

`consumer-contract.json`과 Root `root-consumption-scope.json`의 4개 foreign 접점을
그대로 재사용한다. COMP04A/HP 구현이 진행 중인 상태를 Native ABI 미공급으로
되돌리지 않는다. 현재 첫 미선정은 **실제 coupled cold cohort/등록 owner와 원
operation caller/registered delivery 연결**이며, 다른 ready 기능을 막지 않는다.

## 실행·검증

게임 `RUN_COMMAND`와 packet caller는 null. `scenario.json`은 정상 플레이 조건부
순서이며 누락된 operation/packet을 가정한 실행 스크립트가 아니다. 추후 실입력이
공급되면 기존 Test packet-client-v5/공식 단일큐를 사용한다.

```powershell
python -B work/local_original_session/implementation-companion/plan-comp04b-native-credit-consumer-v2/verify_leaf.py
```

이 명령은 핀과 실제 새 호출 순서/branch/권한 전달/finally의 AST 최소 검사다.
Native import/constructor/positive authority fixture/기성 pure20/split/reducer/
그래프/Store/game/socket/사본/packet 재실행0. 기성 producer/root review를 재사용한다.
