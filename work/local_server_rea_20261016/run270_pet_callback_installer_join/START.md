# REA270 — 원 callback installer와 Pet/Summoned 생성 연결

- 목표: 사용자 ‘계속해’에 따라 B8C60의 보존 prefix 뒤 실제 원 설치 분기와 Pet/Summoned 생성/초기화의 Interaction 등록 연결을 확인한다.
- 재사용: 266/267/269의 UID·일반선택·HUD 결과, Actor→Player 특수 분기 판정은 재사용하며 후속 전체 Pet 부재로 확대하지 않는다.
- 소유: installer worker는 source/installer/와 최종 source3파일, actor worker는 source/actor/만, reply worker는 source/reply/reply-reuse.json의 기존 응답 연결 회수만, main은 MAIN/기존 ledger/HANDOFF만 쓴다.
- 경계: frozen104/c822의 exact 정적 source만·새 provider/target open/runtime/제품공용Test/포트저장0·화면좌표Camera/UI전체복원0이다.
- 마감: 같은 actor→concrete 등록/invoke→실 요청 tuple 또는 무패킷 callback의 확인/첫 미공급을 판정하며 기능main의 실행caller/시나리오 작성·Test 발주를 대행하지 않는다.
