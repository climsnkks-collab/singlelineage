# 정상 원본 Intro 읽기 관찰

`source.py`는 CONTROL9ffc 원본의 복원 CODE·공개 RTTI로 좁은 계약을 생성한다.
`reader.py`의 기본 동작은 PLAN이다. Root가 실제 네 파일과 계약을 검토한 뒤
`work/online_intro_capture_20261006/root-review.json`에 PLAN의 정확한 검토 값을
저장해야 `reader.py --watch`가 실행된다. 작업자는 승인 파일을 만들지 않는다.

공식 LC 실행 전에 시작한다. 자기 PID/birth·Source/계약/검토 hash를 묶은
`work/online_intro_capture_20261006/ready.json`이 READY가 되면 공식 실행이 가능하다.
대기300초 동안 원본 EXE를 lifetime pin하지 않는다. 동일 원본 경로의 프로세스가
여러 개면 최대4개 PID/birth만 기록하고 하나가 될 때까지 기다린다. 하나가 된 뒤
원본 파일을 read-share로 pin하고 CONTROL을 다시 확인하며 0x101010 읽기 권한만
요청한다. 권한 실패·버전 변경은 자동 재시도나 승격 없이 거절한다.
최초 모듈 snapshot의 초기화 오류 ERROR_BAD_LENGTH(24)만 동일 보유 핸들에서
최대1초/10회 제한으로 재조회한다. 권한 오류5는 재시도하지 않으며 횟수·지연·최종
이유를 남긴다. [Microsoft Toolhelp 설명](https://learn.microsoft.com/en-us/windows/win32/api/tlhelp32/nf-tlhelp32-createtoolhelp32snapshot).

관찰은 별도90초/0.25초 간격/최대361표본/표본8KiB·전체4MiB다. 장면을 먼저 읽고,
Root stage/ready, FM availability(+128), UI318, 원본 NP498, Intro18, 공개 CI/BI
cache presence, BI FA/F9, 원래 두 timer ID/저장 active byte와 읽을 수 있는 원래
registry task의 remaining float/파생 finished를 기록한다. 캐시 존재는 실제 위젯
활성으로 표시하지 않는다. 삭제·읽기 실패·소유권 변화·예산 부족은 unknown이다.
timer ID0/registry 부재도 콜백 실행·준비 경쟁 증거가 아니다.

샘플에는 파일 hash/모듈 inventory가 없고, 작고 고정된 원본 CODE와 vtable bytes,
Root/GI/장면/선택 owner를 재대조한다. 관찰 duration·overrun·누락 slot을 기록한다.
폴링이므로 순간 callback 순서나 정확한 전환 시각은 확인하지 못한다. 게임 쓰기,
콜백 호출, helper DLL, packet/auth/key/계정/캐릭터 DTO·원시 포인터 출력은 없다.
결과는 새 work 아래 session 디렉터리의 report.json만 저장한다. 도구는 게임을
실행하거나 종료하지 않으며 기존 문서·Source·온라인 운영 상태를 바꾸지 않는다.
