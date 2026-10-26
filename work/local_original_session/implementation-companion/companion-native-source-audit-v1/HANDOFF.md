# COMPANION-MAGE native source audit v1

WRITER_RELEASED / SOURCE_AUDIT_COMPLETE / test_ready:false / runtime:UNRUN.

기존 native 제품 source의 current Actor lookup→Interaction owning Pair→B6D20→정상 반환→정리 패턴을 찾았다: `integration-1/item-normal-current-serial348-v1/native/entry_native.hpp`. 이는 GroundItem action9/B7DB0 전용 소비자이며 Player 콜백 설치자·generation binding이 아니다. `equipment-window/normal-window-input-v1`은 current player/map·원 UI thread·공유 busy/sequence와 exact whole-entry delegation만 재사용 가능하다. 원 CharacterInfo toggle을 ATS로 바꾸지 않는다.

첫 미공급은 REA272와 동일한 server publication record UID/generation→원 게시 소비 시점의 current native Player/Interaction object/control·owner 문맥 binding/receipt다. 뒤이어 original selector5/I88 보존 하의 per-instance 클릭 도달, 실제 이벤트 전달, 이미 진입한 invoke retirement/drain과 실제 ATS `interface` 구현이 필요하다. 기존 WH_GETMESSAGE host lock은 actor callable의 수명 lock이 아니다.

`CONTRACT.md`에 정확한 source 접점/한계와 다음 구현 한 단위를 정리했다. 공개 packet client/API나 새 wrapper, 가짜 native 함수·receipt·게임 packet은 추가하지 않았다. 제품 구현을 가장한 native adapter candidate는 없다. source-only contract 산출물이며 기능 완료 source 큐 등록·Test 발주 대상이 아니다. main이 필요한 다음 source 담당 결정을 할 때 이 파일을 재사용한다.

확인: 실제 source와 저장된 REA main 검토만 읽고 파일 pins를 확인했다. 새 REA·빌드·runtime·포트·프로세스·입력0; 제품/공용·기존 private 변경0. `parents.json`/`manifest.json`을 함께 인계하며 WORK_RULES의 성공 재사용·최소검증과 공용 client/API Test 단일 writer를 승계한다. 별도 다른 worker의 actor-config runtime rebind 작업과 파일 소유 충돌이 없다.
