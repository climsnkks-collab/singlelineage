# COMPANION-MAGE retained UID2 item target

SOURCE_AUDIT_COMPLETE / ADAPTER_NOT_SUPPLIED / test_ready:false / runtime:UNRUN.

**account v5는 UID2 inventory를 같은 계정 Store에서 읽을 수 있는 custody를 공급한다. root를 selected 상태로 유지한 UID2 inventory/equipment open·Use를 실행하는 ITEM port는 이번 선정 source에서 공급되지 않는다.** 첫 호출부는 Host의 `interface.open_items(panel,kind,character_lease,actor,owner)`이며 구현체는 없다. 저장 member 조회를 UI 열기나 ITEM Use 권위로 바꾸는 adapter는 만들지 않았다.

## 이미 통과한 account 경계

실제 Test `packet-account-multi-canonical-actual-v1/account-world-result.json` SHA256 `96e8ec0266c916a3a129030ac92273309b9957a196a893048773aa26726cb4cc`를 재사용했다. 정상 direct 선택 UID2→UID1→UID2 fresh 세 owner 모두 C2S6/clean close다. 같은 root account v5에는 live members1/2와 RESOURCE:1/2·원 cursor1073741825가 있다. UID2는 실제 Athame itemUID1073741824/Q1을 복원했다.

이 결과는 UID2를 **player로 선택한** 순서이며 root selected+retained companion lease의 동시 item 요청 시험이 아니다. 같은 저장 custody가 생겼다는 이유로 새 actor/Host/UI/Use/FullGear authority를 승인하지 않는다. 기존 PASS의 inventory81697B/hash57842ab0와 equipment159B/hash3b580a47를 read-only로 확인했고 바꾸지 않았다. 필요한 제한·요약은 `actual-evidence.json`에 있다.

## 정확히 재사용 가능한 source

| source | 제공하는 것 | 제공하지 않는 것 |
|---|---|---|
| v5 `account_canonical.member/rows` | 같은 canonical v5의 live member만 UID로 해석한다. archive를 현재 custody로 사용하지 않는다 | operation/current lease·open/Use 권위 |
| v5 `inventory_store.py:713` | 원 locks 아래 `restore(character_uid)`로 그 UID의 기존 immutable inventory bytes를 반환한다. 생성·송신 없음 | 임의 UID 인수 자체가 UI/거래 권위가 아님 |
| v5 `canonical_batch.py:206,1258` | 기존 provider.bind_companion이 실제 selected binding과 발급 active lease/actor proof로 companion Binding을 만든다. BatchStore.restore(binding)는 원 current 검사를 거쳐 해당 member/frame/revision을 읽는다 | issued companion binding이 실제 설치됐다는 runtime 증명이나 ITEM Use/장비 UI 자동 admission |
| 기존 `companion_binding.py:78–166` | 같은 selected owner·현재 active companion lease·원 profile·registry/actor generation·lexical scope를 검증한다 | caller가 직접 만든 Binding·UID만으로 대체 불가 |
| v5 `companion_host.py:461–472` | panel epoch/원 row operation 안에서 actual active lease/actor/owner를 interface.open_items에 넘기고 반환 후 같은 active를 재확인한다 | 실제 open_items implementation·ITEM-specific CAS/consumer/UI port |

원 v5 Host가 정확 부모인 최종 경계다. 과거 actor-click-locked-v2 Host의 같은 action을 재확인하되 그 old Host 전체를 v5 위에 덮어쓰지 않는다. registered companion authority가 있으면 기존 binding/restore를 재사용할 수 있다. source graph에 메서드가 있다는 이유로 실제 active actor·등록 proof·current scope를 발급하지 않는다.

## 기존 ITEM/GEAR Use가 다른 UID를 받지 않는 이유

선정 `item_equipment_effect.py:358–399`의 `_context(writer,...)`는 원 ItemUseSession projection·active selected InventoryGeneration을 얻고 실제 selected position.name/UID·roster selection·realm.profile_uid를 같은 UID로 요구한다. 반환 `character_uid`도 그 selected UID다. target character/companion Binding 인수는 없다.

선정 `gear_consumer.py:40,53,90`은 그 동일 `_context`와 실제 accepted current item intent/frame/selection binding을 소비한다. GearLife도 selected inventory frame·game.selection/원 actor identity에 묶인다. root selected UID1의 context에 UID2 item을 넣거나 current frame·profile_uid·selected selection을 바꾸면 기존 권위를 치환하는 것이다. root를 재선택하거나 UID2 Use packet에 없는 target field를 추가해서 동료 open을 구현하지 않는다.

일반 Batch current companion binding이 존재해도 이 selected ITEM receiver/Effect/GEAR admission이 동료 캐릭터 대상으로 변하는 것은 아니다. 따라서 기존 current 검사 삭제·직접 Store CAS·handler 호출·가짜 packet/response는 해법으로 쓰지 않는다.

## UID2 장비 입력의 별도 결손

실제 account PASS의 유일 `equipment.json`에는 **UID1 legacy Athame row만** 있다. 전체7파일에 `equipment-slots.json`도 없으며 UID2 full GearState를 만든 실행이 아니다. selected GearStore는 그 sidecar를 읽고, inherited ArmorStore.restore는 missing을 None/unknown으로 남긴다. 빈12slot/legacy adoption/initializer를 여기서 새로 실행하지 않는다. 사용자에게 UID2의 기존 장비가 비어 있다고 확정하거나 UI success를 만들지 않는다.

## 다음 필요한 한 port

ITEM 소유 구현이 기존 Host `open_items`와 actual same-account companion binding/lease를 소비하는 **명시 UID2 item-view/action admission port**를 공급해야 한다. root selected binding/current frame은 유지하고 원 companion issuer/current와 UID2 member/frame/revision·정당 GearState를 원 operation scope에서 재확인해야 한다. 표시·수량/아이템 선택·확정의 실제 UI 또는 정상 요청 소비 경로와 원 ITEM/GEAR CAS·response·퇴역 수명을 연결해야 한다. snapshot 반환은 `open`/`Use` 성공으로 표시하지 않는다.

현재 exact source는 두 권위의 읽기 접점과 Host call site까지 공급한다. 위 port/UID2 GearState/native UI가 없으므로 실행 가능한 adapter·caller/RUN_COMMAND는 없다. source-only false이며 다른 기능의 준비 시험을 막지 않는다. source/actual PASS 재사용·AST/핀/저장 pre/post hash 확인만 수행했다. REA/runtime/native·포트·packet·handler·Store·공용/ITEM-owned·기존 private·큐/Test 변경0이다.
