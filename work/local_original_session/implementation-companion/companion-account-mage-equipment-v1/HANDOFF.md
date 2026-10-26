# COMPANION-MAGE class3 legacy equipment account cutover

WRITER_RELEASED / source_ready:true / test_ready:true / run_ready:true / runtime UNRUN. accepted account-v5 product 소스를 수정하지 않고 새 정상 입력으로 시험할 수 있다. 기성 account184 exact source graph를 그대로 선정하며 새 private caller/metadata만 작성했다. 실제 cutover/Store/fresh 결과는 Test가 판정한다.

## 정당 입력과 권위

actual `packet-mage-created-equipment-actual-v1/mage-created-equipment-result.json` SHA f675c2c5b78aedc578b81f2d81d3ecaa9af27a60fbf4c79fa08a993c36385476의 정상 class3 CREATE/WORLD→strictclose/fresh 결과만 사용한다. status=CREATED_SCOPED_WORLD_AND_RECONNECTED_ITEM_STORE_MATCH/first_errorNone/CREATE·RECONNECT cleantrue다. **원 top business_pass:false는 그대로 보존했다.** 이를 true로 고치거나 모든 게임기능 PASS로 확장하지 않는다. 원 결과의 copy_files_after8 SHA와 실제 whole input을 대조했다.

입력은 `validation-profiles/packet-mage-created-equipment-input-v1` 전체8파일이다. UID2 LCMageEquip23A/class3/gender0/원attrs[8,7,12,12,8,12]다. rootinventory d9f9a7e3, childinventory d3f74dae, childequipment50dc690b(159B: actual item1073741824/template1/weapon0/rev1)다. old class0 CREATE32·Mage31/actual55에 sidecar를 붙이는 입력은 사용하지 않는다. 전체8 SHA는 input-source.json에 있다.

기성 accepted InventoryStore.cutover_account는 원 SELECT issuer/oldGraph 퇴역/sourcecurrent→원 root/child profile·Batchv3/canonicalv4 검증→account_canonical.join→rootinventory 한 CAS를 수행한다. 새 입력은 동일 schema/원 same-roster child projection/pendingNone/noPREPARED·실rootcursor 조건에 맞는다. join은 각 member 전체 canonical.equipment_guard를 보존하고 원 inventory bytes/history를 origins로 보존한다. 이 경로는 legacy sidecar를 열어 장비를 생성/수정하지 않는다. 전체8파일 집합은 caller 입력pin만 달라지며 codec/Store의 장비 source 변경은 필요 없다.

## 실행 순서와 판정

Test가 input-source.json의8파일을 새전체사본으로 준비한 뒤 다음 명령을 실행한다.

```powershell
& "C:\Users\Chansol\Documents\ChatGPT\싱글리니지\work\local_original_session\implementation-companion\companion-account-mage-equipment-v1\RUN_COMMAND.ps1" -AccountCopy "<NEW_WHOLE8_COPY_ABSOLUTE>" -AccountResult "<RESULT_ABSOLUTE>"
```

기성 client-v5/API/정상caller를 재사용한다. MAGE→ROOT→MAGE_FRESH의 세 owner에서 매번 정상 KEY/VERSION/address/login/roster 수신→실제 수신 이름의 packetless 선택→원4E28→WORLD prefix/0964/원RESOURCE/current를 확인한다. 실UID/class3/gender0/sprite734·원Store/frame·rootcursor/live members/RESOURCE·immutable origins를 판정한다. 앞owner strictcleanclose 뒤에만 다음owner/fresh로 진행한다. 실제 server.prepare/decoder/router/Scope/Store만 실행하며 caller의 handler직접/가짜UID/current/상태 강제0이다.

추가한 관측은 입력 root·child legacy 파일이 각각 원 canonical.equipment_guard와 동일함, 각 WORLD 뒤 두 파일 bytes와live member equipment_guard가 그대로임뿐이다. 최종 preservation이 rootinventory 이외7파일 SHA를 확인한다. 새로운 GearState나 EquipmentStore.restore/live 장착 성공을 주장하지 않으며 메타에도 legacy_equipment_runtime_restore=UNRUN_RESOURCE_ONLY_NOT_FULL_GEAR를 기록한다. RESOURCE-only Plan에는 장비소비 owner/fullGear/ADOPT/Use/장비통지가 없다.

기성 엄격 close 블록은 byte동일하다. 첫 오류·원문stack·부분저장/현재cursor/pending/receipt를 보존하고 server snapshot failure_code, connection failed/error/completedERROR면 cleanfalse·다음fresh0이다. 결과 status ACCOUNT_CLASS3_LEGACY_EQUIPMENT_CANONICAL_WORLD_FRESH_MATCH일 때만 exit0이다. 정상 Quit은 기존 unsupported/send0이며 소유 server/socket 정리를 Quit 성공으로 부르지 않는다. Test만12000/14030·새copy/FIRST/result/close를 소유한다.

## 변경과 확인

cohort.json/source_loader.py/dependencies.json은 accepted account 부모와 byte동일이다. 제품source/공용/ITEM/Test/원저장/기성private/큐 수정0, 새서버/포트/사본0. 새 caller의 변경은 입력8file·실새이름/획득근거, 양legacy 보존관측, 최종판정명/7파일 오류label뿐이다. 정상Protocol/current/Store/수명·strictclose 몸체를 재사용했다. caller.diff에 정확 변경을 남겼다.

verify_ready.py 한 번으로 actual결과핀/whole8 SHA·실class3와 원양sidecar=guard, join필요schema/정당projection, 원source선정byte동일/정확부모, caller syntax/기성strictclose byte동일 및 새관측접점만 PASS했다. product import/Factory/Store/TCP는 실행하지 않았고 기존actual55 migration과새CREATE의정상취득관측을 재실행하지 않았다. 실행준비와Runtime성공은 구별한다. fullGear/동료Host/actor소환/지원AI/Native UI는 이 SKU 범위가 아니다.
