# REA274 — Pet/Summon 통계 요청 후 응답·메뉴 계약

- 요청자: companion main `01a16769-c8cd-7603-be3d-ff5050d8f20a`. REA270의 `CS_SUMMON_STAT_REQ 4F13`, required f1 uint32 actorUID를 재사용한다.
- 범위: 명시적으로 연결되는 S2C 응답·메뉴 소비·정상 다음 요청만 확인한다. REA270/271/272와 기존 6-cache 상관 미확인 결과를 재사용하고 같은 부재 검색을 반복하지 않는다.
- 담당: 기존 `gear_existing_named_contacts` Sol6.1/high가 `source/`만 단독 작성한다. main은 원문·실제 변경분을 검토하고 MAIN_REVIEW/기존 인계에 결과를 남긴다.
- 경계: 4F14·4EF3 인접성으로 응답을 추정하지 않는다. 기존 frozen 원문 우선, 새 선택 CODE16KiB/PData2KiB/DATA1KiB/exact query4 이내(같은 54A950 등록의 직접 subscriber54BDF0/54BB40을 닫는 추가2 승인). 필요 직접 callee만 선정한다.
- 실행·포트·원본변경·게임·전역 hook·화면 좌표·ATS 구현·공용 source/Test 사본·Root/Test 알림·큐·시험 발주 0. 완료 계약은 관련 companion main에 직접 1회 전달한다.

최소 wire 보완: 기존 source3 마감 후 actual opcode→typed publisher/factory join과 virtual20=770080 required-init leaf만 pet worker가 source/wire/에 독립 선정한다. 추가 CODE4KiB/PData512B/DATA512B/exactquery3(직접 publisher VA→factory table exact DATA lookup1 추가 승인), total CODE16KiB는 유지하고 PData2KiB/DATA1536B 안에서 결합한다. 기존6-cache 부재 검색·전체 registry/메뉴/geometry 확장0. 원 서버 요청/응답 인과와 UI 성공을 정적 join으로 판정하지 않는다.
