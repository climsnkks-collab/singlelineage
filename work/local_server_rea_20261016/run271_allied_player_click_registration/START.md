# REA271 — 원 Player 클릭과 개별 allied actor 콜백 등록

- 목표: 원 Player Interaction 생성·콜백 선택과 특정 발급 UID/generation의 actor 한 개에만 설정 진입을 등록/해제할 원 접점·수명을 조사한다.
- 재사용: REA267/270의 일반 선택·Pet/Summoned 요청·generic installer는 반복 분석하지 않고 Player 생성/초기화와 개별 callable 수명만 잇는다.
- 소유: Player 경로 worker는 source/player/ 및 최종 source3파일, 등록/수명 worker는 source/lifetime/만, main은 MAIN/기존 ledger/HANDOFF만 쓴다.
- 경계: 별도 정적 REA source만·제품/공용/Test/실행/포트/저장0·Pet 변환/전역 훅/geometryCamera/ATS창생성0·새 provider/target open0이다.
- 마감: 같은 Player·원 등록/퇴역과 서버 발급 UID/generation 결속을 구별해 확인/조건부/첫 미공급을 적고 관련 질문자에게 계약 답1회만 전달한다.
