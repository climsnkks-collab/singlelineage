# COMPANION-MAGE account equipment input 판정

WRITER_RELEASED / source-only / test_ready:false / run_ready:false / runtime UNRUN.

CREATE32 전체8파일은 **UID2의 실제 legacy EquipmentState**의 정당 취득 근거다. 실제 CREATE→WORLD→close→fresh PASS와 child equipment.json 159B SHA256 `50dc690bf39f39a365fb1a4543222a1eabf2b9e66be36774a21390a46879dedc`를 확인했다. state는 character_uid2/item_uid1073741824/template1/weapon_uid0/revision1이며 실제 child canonical.equipment_guard와 같다. 그러나 이는 full 12-slot GearState가 아니다. 전체8파일에는 equipment-slots.json이 없다.

**동료법사 입력으로 바로 소비할 수 없다.** CREATE32 UID2는 이름 LCEqAuth23A, class0이다. accepted actual55는 LCMage1023A/class3의 다른 전체7파일을 정상 WORLD 순서로 account-v5에 합친 PASS다. 같은 UID2라고 동일 캐릭터 계보가 아니다. CREATE32 sidecar를 actual55 계정에 접붙이거나 roster/class/name/canonical을 고치는 방식은 허용된 입력이 아니다. mage actor-config의 실제 callback도 record.class !=3이면 legacy 경로로 분기한다.

accepted account-v5 **caller 그대로** CREATE32를 넣으면 서버 생성 전 run_account_scope.py55–56의 INPUT_UNSUPPLIED_COMPLETE_UNCHANGED_TEST_COPY_REQUIRED로 거부한다. 정확7파일 목록에 child equipment.json이 추가되며 root/child characters.json 및 root/child inventory.json 네 SHA가 다르다. 그 뒤에도 선택 scenario는 LCMage1023A라 이름이 다르다. input pin만 교체해서 mage 선택 성공으로 주장할 수 없다.

account_canonical.join은 class별 장비 생성기가 아니다. 두 Batchv3/canonicalv4/각 single-member revisions/pendingNone/noPREPARED와 real root cursor를 받아 root 한 CAS로 합치는 codec다. CREATE32 두 문서는 검사한 구조 조건을 만족하고 root/child cursor는 실제1073741826이다. 따라서 일반 두 캐릭터 canonical migration 후보로 검토할 수 있으나 정확8파일/선택이름을 받는 소유 caller 후손과 정상 cutover/strictclose/fresh가 필요하다. 해당 조합 decode/Runtime은 실행하지 않았다. codec/schema 호환 가능성은 기존 SKU의 동일 입력 허용 또는 class3 권위를 뜻하지 않는다.

## 첫 직접 의존

동료법사 목적의 첫 입력 의존은 **실제 class3 캐릭터에 정상 CREATE 경로로 발급된 같은-profile legacy equipment와 그 전체계정 취득 근거**다. 기존 created-equipment-authority initializer와 정상 CREATE/WORLD/fresh caller를 담당 owner가 합성한 후손에서 공급해야 한다. 현재 mage31/actual55에는 UID2 legacy sidecar가 없고 CREATE32에는 class3가 없다. v5의 추가 CREATE는 accepted source에서 쓰기 전 UNSUPPORTED이므로 migrated actual55에 추가 CREATE로 우회하지 않는다. 정상 class3+equipment whole input을 먼저 마련한 뒤 기존 account-v5 cutover 계약으로 전달해야 한다. 이 worker는 새 CREATE/사본/장비 보정을 수행하지 않았다.

그 입력이 준비돼도 runtime full GearState는 별도 정상 기존 GEAR 경계다. GEAR의 명시 ADOPT_LOCAL_WEAPON_ADD_ELEVEN_SLOTS는 실제 same-profile EquipmentStore.restore/current와 no-armor preimage, old writer release를 요구하고 새11칸0을 LOCAL 초기값으로 생성한다. sidecar 한 행을 GearState로 변환했다고 주장하거나 frozen DTO를 발급/current 권위로 쓰지 않는다. 현재 account migration caller는 RESOURCE-only Plan이며 fullGear 설치/ADOPT/current가 실행됐다는 근거가 없다.

ITEM companion-item-target-view-v1은 원 Host/provider/BatchStore/current로 inventory만 읽는다. kind=equipment는 COMPANION_ITEM_TARGET_EQUIPMENT_STATE_UNSUPPLIED로 명시 거부한다. 같은 actual active/lease/actor/owner, 최종 typed interface.open_items 직접 호출, 원 issuer와 same account-v5 그래프의 수명 결속이 후속 공급 조건이다. 파일 존재만으로 그 guard를 풀 수 없다. 현재 부모 Host/Core exact pins를 다른 account 후손에 자동 전파하지 않는다.

## 확인과 보존

inspect_inputs.py를 한 번 실행해 전체8파일 SHA, 실제 CREATE32 result/preservation/cleanclose, actual55 result, 두 문서의 필요한 구조 및 sidecar=guard만 확인했다. 제품 import, 게임/서버/포트, Factory/Store 쓰기, 저장사본, 기존 폴더/공용/ITEM/GEAR/Test/queue 수정은 없다. 기존 통과는 재실행하지 않았다. inspection.json에 정확17 source pin과8 saved-file pin, 실제 결과/보존/FIRST/source-copy pin 및 mismatch를 기록했다. 이 폴더의 manifest.json은 산출물 pin만 묶는다.

읽기 전용 재확인 명령: `python -B work/local_original_session/implementation-companion/companion-account-equipment-input-v1/inspect_inputs.py` (inspection.json만 자기 폴더에 갱신). 게임 RUN_COMMAND는 제공하지 않으며 test_ready는 false다.
