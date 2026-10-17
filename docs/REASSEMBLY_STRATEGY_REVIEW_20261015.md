# 원본 재조립 방식 검토 — 2026-10-15

이 검토 후 사용자가 요청한 구현·검토의 운영 기준은 [작업 규칙](WORK_RULES.md)에 명문화했으며 AGENTS.md에서 필수 적용한다.

## 결론과 적용 범위

함수별 복원과 ASM/COFF 보존은 유효한 기술 자산이다. 다만 현재는 여러 정적 작업집합을 검토하는 일이 단일 실행 통합보다 앞서 있다.
앞으로는 원본 code/data를 가능한 한 큰 일관된 단위로 보존하고, ABI·EH·초기화·수명 경계를 유지한 재링크와 실제 소비 연결을 중심에 둔다.
함수별 작업은 그 실행 경로의 미해결 의존성을 닫는 수단으로 배치한다. 전체 원본 동일성 목표를 축소하는 제안이 아니다.
저장 소스와 검토자료를 읽은 정적 검토이며 새 제품 빌드·원본 실행·REA 분석은 하지 않았다. 폐기 준비에서는 기존 앱 이름의 프로세스 목록만 읽었고 해당 프로세스는 관측되지 않았다. 일반 PE/x64 실행 계약은 Microsoft 공식 문서와 대조했다.
보고서 작성 당시 실행 검증을 새로 수행하지 않았으므로 아래 실제 결과는 각 저장 증거가 기록한 범위다.

## 사용자 결정: 기존 단독앱 폐기

사용자는 **REA 스킬 사용 전에 자체 제작했던 Win32/GDI 단독앱**을 폐기 대상으로 명확히 했고, 해당 범위임을 확인한 뒤 진행에 동의했다.
REA 이후 원본에서 복원한 코드·ASM·렌더러·메인 루프·분석 자료는 폐기 대상이 아니다.
현재 앱 전용 소스·실행본·빌드 파일 211개(31,264,581바이트)를 실제 삭제했다. 프로젝트 tools의 명시된 기존 앱 모듈과 2026-10-12 배포본 single-lineage-corrected-icons-1301bb579ebb/staging/tools에 한정했다.
Root가 삭제 결과의 211개 이벤트와 실제 대상 부재211개를 별도로 대조했다. 보존 핀54개가 삭제 전후 일치했고, 사용자 저장·실행 기록·원본 REA 메인 루프·과거 V15 후보·보관 디렉터리의 존재를 확인했다.
근거: [정확한 삭제 목록](../work/reassembly_strategy_review_20261015/decommission/DELETE_INVENTORY.json), [삭제 결과](../work/reassembly_strategy_review_20261015/decommission/DELETE_RESULT.json), [Root 후속 확인](../work/reassembly_strategy_review_20261015/DECOMMISSION_VERIFIED.json).
과거 검증 사본과 원본 사실/호스트 정책이 섞인 자료는 기록으로 보존하며 제품 재사용을 금지한다. 이는 모든 과거 복사본의 물리 삭제를 뜻하지 않는다. 보존된 출처 데이터·catalog·EXP 표를 기존 앱 구현의 재사용 허가로 해석하지 않는다.
원본 클라이언트, 복원 ASM/COFF, 분석근거, 원본 자원과 저장자료는 이 폐기 범위가 아니다.
기존 단독앱의 보수, GDI overlay, 임의 UI/속도/타이밍, 가짜 provider/stub를 새 제품의 기반으로 재사용하지 않는다.
기존 앱에 원본 함수를 붙여 동작시키는 접합 계획과 그 앱 전용 frame/입력/HUD/장면 adapter는 제품 계획에서 효력을 잃는다.
과거 GDI 표시·headless·저장 시험의 PASS는 과거 앱에 대한 기록이며 새 원본 재조립 제품의 통과 근거로 승계하지 않는다.
다만 저장된 OriginalDirector·renderer·이벤트·자원 코드 전체를 GDI 앱과 동일시하여 폐기하면 안 된다. 원본 출처와 소비 경계를 따로 판별한다.
V15 mixed candidate의 single_main.cpp는 static HUD 자원을 직접 읽고 WM_PAINT와 10ms SetTimer/GetMessage 루프를 소유한다.
이 host의 HUD/입력/paint/timer 접합을 앞으로의 제품 소비자로 삼는 계획은 폐기 결정에 따라 obsolete다. 독립된 원본 복원 함수의 근거는 남는다.
근거: [V15 과거 host 소스](D:/CodexArtifacts/single-lineage-rea-resume-20261013/integration/bootstrap/gameplay-moving-latecopy-v15-source/candidate/product/staging/tools/source_single_app_20261010/single_main.cpp), 80·209·224행. 이 링크는 역사 후보 경로이며 삭제 제외의 지시가 아니다.

## 발견 1: 현재 숫자는 서로 다른 작업집합이다

| 이름 | 저장자료가 입증하는 것 | 통합 한계 |
|---|---|---|
| Root actual62 | decoder 계열 정적 COFF 62개, PUBLIC110 및 참조필드931의 정적 분류 | runtime 미채택, public ZSTD_decompress 부재 |
| Main3 | 게임 코드·EH 객체 3개 조립 및 원문·참조 검토 | Root decoder에 자동 추가되지 않음, runtime 미채택 |
| Main5 | 후속 callee/EH 객체 5개 조립, Main3 원문 참조 join24 검토 | 별도 정적 집합, 전역 cohort 채택0, link/runtime false |
| Front378 | 소스784개에 기반한 CPP353+C25 객체 컴파일 | compile-only, unlinked static frontier684 |
| frozen normal DLL | frontend343+sidecar3+decoder35, 객체381개·라이브러리18개 링크 시도 | 미해결180, raw1120, DLL 생성 false |

이 값들을 더하여 제품에 연결한 함수 수 또는 완료율로 표시하면 안 된다.
Main5 미공급71은 참조 수이며 고유34와 구분된다. Main3·Root62·Front378의 미공급 집합과도 중복될 수 있다.
Front378의 684는 해당 정적 집합의 외부참조 경계이며 원본 기능684개라는 의미가 아니다.
근거: [Root62 참조·한계](../work/rea_lineage_resume_20261013/integration/root/DECODER_CURRENT62_UNADOPTED_STATIC_FRONTIER.json), 315·13864·14077–14095행.
근거: [Main3 정적 채택](../work/rea_lineage_resume_20261013/integration/root/MAIN_B4_ACTUAL3_FINAL_ROOT_STATIC_ADMISSION_EXPLICIT_SOURCE799_SERIAL_RETURN.json), 1215–1235·1266–1270행.
근거: [Main5 최종 범위](../work/rea_lineage_resume_20261013/integration/root/MAIN_GENV7_ACTUAL5_SCOPE_FINAL_ROOT_STATIC_ACCEPTED_CLEANUP_EXPLICIT_RETURN_CLOSED.json), 106–127·147–161행.
근거: [Front378 최종 범위](../work/rea_lineage_resume_20261013/integration/root/FRONT91_LOGICAL378_FINAL_ROOT_COMPILE_ONLY_ADMISSION_EXPLICIT_MAIN_B4_SERIAL_RETURN.json), 160–174·191–216행.
근거: [V83 저장 통합현황](../work/rea_lineage_resume_20261013/integration/root/HANDOFF_CHECKPOINT_V83_MAIN5_STATIC_CLOSED_FRONT198_CODE15_CALLER.json), 60–79·2382–2389행.

## 발견 2: unresolved133은 전체 원본의 분모가 아니다

ledger의 baseline은 과거 frontend286 실제 링크진단이다. 그때 심벌133개는 project132+Zstd1로 분류됐다.
이는 원본 함수133개, 제품 요구사항133개, 남은 작업 전체133개라는 의미가 아니다.
이후 다른 작업집합의 미해결180과 단순 증감률을 계산해도 전체 진척이 되지 않는다.
ledger 각 행이 actual consumer와 producer·ABI·수명·실제 DLL 연결을 완료 조건으로 둔 점은 유지할 가치가 있다.
첫 전역 문자열 항목도 BSS dynamic initializer이며 current original CRT invocation은 false다. 이름 해결만으로 초기화 동일성을 선언할 수 없다.
근거: [원133 ledger](../work/rea_lineage_resume_20261013/integration/root/UNRESOLVED133_ORIGINAL_PORT_LEDGER_V59_MAIN5_STATIC_CLOSED_FRONT198_CODE15_CALLER.json), 5–18·87–100행.

## 발견 3: ASM 방식은 원코드 보존에 적합하지만 독립 실행을 자동으로 보장하지 않는다

실제 fa0a80 소스는 원 instruction을 DB로 보존하고 call/branch를 symbolic reference로 바꾸며 오프셋 assertion을 둔다.
동일 파일의 xdata/pdata는 원 unwind와 코드 구간 연결을 재배치 가능한 형태로 유지한다.
이 방식은 원 최적화 코드의 명령·분기·부동소수점 세부동작을 보존하는 데 유리하다.
선택한 범위의 원문 역복원 일치는 그 범위·재배치 표현의 증거이며 실행환경 전체의 동등성 증거가 아니다.
fa0f34 EH 자료도 FH4 replay/inverse 일치와 별개로 identity/runtime OPEN을 명시하고 외부 handler·funclet를 요구한다.
PE 재배치, image-relative 참조, TLS/CRT 초기화, import, cookie, EH 등록, heap 경계를 함께 보존해야 한다.
일반 실행 계약 근거: [Microsoft PE/COFF 형식](https://learn.microsoft.com/en-us/windows/win32/debug/pe-format), [Microsoft x64 예외 처리](https://learn.microsoft.com/en-us/cpp/build/exception-handling-x64). 이 문서가 대상 게임의 모든 의존성을 확인해 주는 것은 아니다.
근거: [fa0a80 ASM](../work/rea_lineage_resume_20261013/main-gameplay/engine15-b4-callees-five-tu-code-label-correction-source-v1/original-source/fa0a80.asm), 1–10·14–31·83–91행.
근거: [fa0f34 EH ASM](../work/rea_lineage_resume_20261013/main-gameplay/engine15-b4-callees-five-tu-code-label-correction-source-v1/original-source/fa0f34_eh.asm), 1–9·19–36행.

## 발견 4: 핵심 병목은 dependency closure와 실제 소비 연결이다

Root62는 미공급 고유39개 중 intrinsic1, internal15를 기록한다. 일부는 import·data이며 함수39개라는 뜻이 아니다.
새 DATA8은 기존 코드 consumer0이고 callback2의 actual supplier0이다. 객체가 존재하는 사실과 제품이 사용하는 사실은 다르다.
Main3는 비intrinsic 공급자128개/참조필드249개와 loader/storage/cookie/lifetime을 열린 조건으로 둔다.
가상함수/vtable·RTTI·전역 producer·간접콜·heap·예외 handler·수명 계약을 닫지 않으면 조각별 성공이 링크 가능성으로 이어지지 않는다.
C++ adapter와 literal ASM을 혼합하는 경계에서는 this/layout, 인자·반환·숨은 인자, 정렬, 소유권, 예외·CRT 규약을 명시해야 한다.
같은 이름이나 대략 비슷한 클래스 API만으로 원 객체를 새 C++ 객체처럼 사용하면 안 된다.
근거: [Root62 미공급·데이터·runtime](../work/rea_lineage_resume_20261013/integration/root/DECODER_CURRENT62_UNADOPTED_STATIC_FRONTIER.json), 13864–13885·14077–14095행.
근거: [Main3 열린 조건](../work/rea_lineage_resume_20261013/integration/root/MAIN_B4_ACTUAL3_FINAL_ROOT_STATIC_ADMISSION_EXPLICIT_SOURCE799_SERIAL_RETURN.json), 1266–1270행.

## 발견 5: 원본 메인루프 복원 자산은 이미 있다

현재 작업을 모두 leaf 함수나 가짜 정적 화면이라고 평가하면 부정확하다.
저장된 OriginalDirector::mainLoop에는 종료·재시작, clock/update, 이벤트, 장면 교체·retain/release, render와 swapBuffers, pool clear 흐름이 있다.
실제 코드에는 callback 이후 포인터 재읽기와 suppression 때 endFrame을 건너뛰는 분기도 표현돼 있다.
이는 중심 실행 경로를 복원하려 한 실질적인 자산이다. 기존 GDI 앱 폐기가 이 자산의 자동 폐기를 뜻하지 않는다.
그러나 같은 파일은 전역/RTTI producer의 미해결을 명시하며, 저장 소스만으로 해당 loop가 독립 제품에서 실제 실행됐다고 판단할 수 없다.
권고는 loop를 새로 흉내 내는 것이 아니라 이 자산의 원본 근거·의존성·실제 caller를 연결해 사용하는 것이다.
AppDelegate 생성자와 initializeApplication의 전체 normal/failure body가 필요하다는 선언도 남아 있다. loop 본체의 존재와 초기화 완결은 별개다.
근거: [OriginalDirector 저장 소스](D:/CodexArtifacts/single-lineage-rea-resume-20261013/frontend/platform/coherent-future-p68-core74-main-b7-ed500-v8-source-only-corrected4/source/frontend/renderer/original_director_main_loop.cpp), 7–11·12–41·43–85행.
근거: [OriginalAppDelegate 선언](D:/CodexArtifacts/single-lineage-rea-resume-20261013/frontend/platform/coherent-future-p68-core74-main-b7-ed500-v8-source-only-corrected4/source/frontend/platform/original_application.hpp), 36–40행.

## 발견 6: 독립검토를 공통 자동화와 통합 결과에 연결해야 한다

source/object binding·COFF profile·수명 반례를 찾는 독립검토는 필요하다. 원본/프로세스 보호를 없애자는 제안이 아니다.
다만 매 조각마다 별도 gate/writer/bootstrap/reader/receiver를 만드는 방식은 검토 인프라의 변경량도 늘린다.
최신 기록에는 reviewer의 빈 stream 판정 1바이트 수정, publication 상수 lead/LEAD 오독 등 검토기 자체 수정이 별도 계층으로 남아 있다.
이런 기록은 보존하되, 그 처리량을 제품 동등성 진척으로 집계하지 않는다.
성숙한 공통 실행기·COFF 검증기·manifest에 불변 조건을 모으고 실제 달라진 source/ABI/동작과 새 반례를 중심으로 비례 검증한다.
총 시간·비용 원자료를 분석하지 않았으므로 낭비 비율을 수치로 단정하지 않는다.
근거: [빈 stream 수정 검토](../work/rea_lineage_resume_20261013/integration/root/MAIN_GENV7_ZERO_STREAM_HARNESS_FIX_ROOT_DIRECT_SOURCE_REVIEW.json), 32–42행.
근거: [상수 오독 보존](../work/rea_lineage_resume_20261013/integration/root/FRONT_V71_ROOT_HEADER_CONSTANT_CASE_FAILURE2_PRESERVED.json), 9–16행.

## 권고하는 실행 전략

1. 단일 선택 manifest가 제품 source/object/data/import/provider와 버전·원본 출처를 소유하게 한다. 여러 cohort의 자동 혼합을 금지한다.
2. 원본 code/data와 그 의존성을 가능한 한 큰 일관된 단위로 유지한다. 매 함수 분리는 검증 가능한 경계가 있을 때 선택한다.
3. 초기화 → 원본 loop → 실제 입력 → frame/render/present → 해제의 연결된 경로를 첫 통합 단위로 삼는다.
4. 해당 경로의 직접·간접 code/data·vtable·EH·CRT·allocator 의존성을 실제 consumer까지 닫고 단일 산출물로 재링크한다.
5. 원본과 같은 입력·상태에서 이벤트 순서, 프레임/버튼 움직임, 전환, 자원 생성·해제와 예외 경로를 대조한다.
6. 통합 기반이 확인되면 그 위에서 기능·장면·자원 경로를 확장한다. 이 순서는 전체 목표를 축소하는 MVP 완료 기준이 아니다.

원본 온라인 실행은 관찰·대조 기준이다. 제품 시작이나 게임 초기화가 PURPLE 로그인·공식 서버 실행에 의존하는 상태를 완료로 인정하지 않는다.
원코드 실행 유지 방식은 원래 기계어·데이터를 보존하고 로더·서비스 경계를 독립 환경에 공급하는 접근이다.
고급언어 semantic 재구현은 의미·상태·자료구조·오류·타이밍·수명이 충분히 확인되고 대조 가능한 영역에 한정한다.
두 방식 모두 완전한 동작을 목표로 하며, C++ 소스 생산량이나 기계어 바이트 일치를 서로의 동등성 증거로 대체하지 않는다.
새 host가 필요하면 원본 loop·윈도·입력·present의 경계를 연결하는 얇은 기동부로 설계하며 기존 앱을 보수해 이어 쓰지 않는다.

## 진행지표와 방식 변경 기준

- 보존 지표: 원문 범위, hash, instruction, relocation, unwind, 원본 출처와 실패 반례의 검증 상태.
- 통합 지표: 단일 선택 집합에서 실제로 해결된 provider, 남은 참조의 종류, 실제 링크 산출물, host consumer와 연결된 경로.
- 동작 지표: 독립 기동, 실제 loop/입력/present/해제 관찰, 원본 대조로 확인한 상태·전환·수명과 아직 열린 차이.
- 전체 기능·원본 분모가 정해지기 전에는 객체 수나 원133표로 전체 완료율을 산출하지 않는다.
- 연속 작업 단위가 source/gate/receipt 수만 늘리고 선택 경로의 의존성이나 실행 연결을 줄이지 못하면 분할·우선순위를 바꾼다.
- 동일 종류의 검토기 오류가 반복되면 제품 원문을 더 쪼개기 전에 공통 검증기를 고치고 그 수정 범위만 재검증한다.
- ABI·EH·producer가 불명확한 경계를 임의 stub로 통과시키지 않는다. 경계를 넓혀 원문을 보존하거나 필요한 증거를 확보한다.
- 통합 시험 실패는 원래 실패를 보존하고 원인을 code/data/초기화/ABI/수명/환경으로 분류한다. PASS를 얻기 위한 기능 생략은 금지한다.

자료 보존과 전체 제품 동등성은 별도 성과다. 현재 자산을 활용하되 다음 진척은 실제 원본 실행 경로가 닫히는지로 판단한다.
