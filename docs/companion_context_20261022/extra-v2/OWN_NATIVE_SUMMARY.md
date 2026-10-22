# OWN NATIVE SUMMARY — 동료 계약 제공 범위

REA216의 MAIN 검토에 있는 외부 전달용 OWN SUMMARY만 바탕으로 우리 자체 문장으로 정리했다. REA 원문·주소·분해 결과·바이너리를 포함하지 않는다. 분석 원문과 이 요약은 제품 구현 또는 실게임 성공을 의미하지 않는다.

기존 Player 분류와 공통 MOVE·Remove 소비 접점은 동료 연결에 재사용할 수 있다. 현재 자체 encoder와 Monster 전용 adapter를 그대로 복제해 완전한 법사 입력이 된다고 판단할 근거는 없다. 완전한 mage DTO와 numeric gender·appearance 변환은 OPEN이다. 정상 Player의 실제 등록·제거 성공과 동료 current 수명도 아직 공급되지 않았다.

actor UID, character UID, current generation은 서로 다른 계약으로 구분해야 한다. 현재 동료의 정당한 UID 배정·충돌 방지와 실제 등록·generation 결속은 OPEN이다. UID3은 NPC395의 명시 LOCAL 시험 후보일 뿐 동료를 위해 예약한 값이 아니다.

기존 Inventory shortcut·close는 현재 선택 캐릭터에 연결된 계약이다. 원 ATS 창 생성·callback 등록과 호출·close·shortcut 및 창 수명은 OPEN이다. 다른 아군 캐릭터의 Inventory/Equipment를 여는 ITEM target 진입점과 독립 view·transaction adapter 역시 미공급이다. 설정과 동료 행동은 자동사냥에서 분리해야 한다.

추가 요청한 다른 caster용 SupportResponseSource/native send 접점과 potion effect owner도 이번 묶음에 공급되지 않았다. 기존 selected-character API의 UID만 바꾸거나 Monster adapter·직접 송신·임의 효과 owner로 이 빈 계약을 대체했다고 주장하지 않는다. 같은 Pro가 구현·수정을 이어가며, 필요한 실제 계약과 최초 정상 입력 조건을 명시해야 한다.
