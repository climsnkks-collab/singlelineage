# COMPANION-MAGE UID2 item target audit v1

WRITER_RELEASED / SOURCE_AUDIT_COMPLETE / adapter:null / source_ready:false / test_ready:false / runtime:UNRUN.

actual account-v5 PASS96e8ec02의 UID2→UID1→UID2 정상 WORLD/fresh를 재사용했다. 단일 account custody의 두 member/RESOURCE와 UID2 실제 AthameUID1073741824Q1은 확인됐다. 이 실행은 root-selected+동료 lease의 동시 item open/use가 아니다.

기존 v5 provider.bind_companion→issued current Binding→BatchStore.restore(binding), InventoryStore.restore(uid)는 읽기 source로 재사용 가능하다. 첫 missing port는 최종 v5 Host469의 `interface.open_items(...character_lease,actor,owner)` 실제 구현/ITEM admission이다. selected ITEM Effect `_context`·GEAR consumer는 actual selected UID/frame/profile을 요구하고 companion target 인수가 없다. 이를 root current 치환·재선택·새 packet으로 우회하지 않았다.

추가로 actual PASS의 장비 파일은 UID1 legacy row만 있고 전체7파일에 full gear sidecar/UID2 GearState가 없다. missing을 빈 장비로 채우거나 initializer/adoption을 실행하지 않았다. `CONTRACT.md`에 ITEM 소유 target port의 최소 요구를, `actual-evidence.json`에 bounded 실제 결과·입력을 보존했다.

AST/부모 핀·actual 결과 exact hash·원 inventory/equipment pre/post hash 최소확인 PASS. 실행/REA·packet/port·Store·ITEM/common/기존 private·큐/Test 변경0. main이 정확 source 결손·후속 owner를 검토하며 이번 artifact는 실행 SKU가 아니다.
