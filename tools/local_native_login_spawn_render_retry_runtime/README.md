# CP74 — 같은 소유 창의 제한된 렌더 재관찰

동결 CP73에서 만든 fresh 한 번 런타임이다. RUN_ID `cp74-render-20261009-01`은 23자이고 원본 native 컨텍스트의 소문자·숫자·하이픈/최대32자 계약을 따른다. work·slot·리뷰·observer·forward 출력은 CP74 후속 전용이다. CP73 실제 시험의 새 좌표 `(32571,32950)`와 타일 dir2 PASSABLE은 보존된 이전 실행 근거다. CP73 첫 WGC 프레임은 검은 화면과 흰 직사각형이었고, 이번 새 실행의 월드·렌더·Navigation·이동은 아직 미검증이다.

CP73 Actor/profile/타일 검사 소스와 Actor ledger는 byte 그대로 보존한다. 새 namespace profile 경로2개를 spawn-profile-pins에 추가하고 hook의 해당 pinset SHA literal만 연결한다. 기존 profile 선언 guard는 그대로 유지한다. UID1/map0/이름/통계/ACK→Map→Self→Actor/저장 `characters.json` 불변, 후보·CP49 owned producer, exact PID/birth/Job/이미지 admission, 슬롯·cleanup·RestoreControl, short context ID 계약과 안정 표본 조건은 같다. 독립 창 선택 이후 기존 `capture` 호출 한 곳만 동결 `local_native_login_spawn_render_runtime/observation.py`의 `sequence(native, render, ...)`로 연결한다. 기존 adapter의 `run`은 CP73 namespace를 로드하므로 새 런타임에서는 호출하지 않는다.

동일 보유 native 핸들과 정확한 HWND에 첫 캡처, 2초 뒤 두 번째, 다시 2초 뒤 세 번째 WGC 세션을 제한적으로 수행한다. 각 세션 timeout6초, window metadata 전후 일치, visible/minimized 조건을 유지한다. UNKNOWN·예외·owner/window 변화가 있으면 남은 관찰을 중단한다. 전경 전환·desktop pixels·새 PID open·게임 내부 호출·이동 입력·새 이동 패킷·메모리 쓰기는 없다. `render-capture.json`의 기존 `capture_attempts`는 단일 sequence 호출 수1을 보존하며, 실제 세션 수/시간/경로는 `render-sequence.json`의 attempts에 기록한다. 모든 픽셀 결과는 `world_visibility_verified=false`다. Root의 별도 이미지 검토 전 보이는 월드 성공으로 올리지 않는다.

정적 검사는 전체 CP73 byte/AST 선언 delta, 동결 CP73/CP74 어댑터 파일, additive evidence pins, actual source_api/verify_files 및 hook/slot closure, CP73 SelfInfo/Actor frame byte 동일성, 기존 source fixtures, 45 자기 프로세스 API 검사, CP70 타일17, 동결 어댑터12, 새 post_stability 연결10 fixture를 확인한다. 복사한 `probe_tests.py`는 기존 단일 WGC 가드 검사를 위해 동결 CP73 helper를 명시적으로 사용하고, 새3회 연결은 `integration_tests.py`가 검증한다. `initial-source-freeze.json`은 마지막 직접 packet 동일성 검사·문서 정정 전 중간 검증 보존본이며 최종 동결은 `source-freeze.json`이다. 게임·WGC·슬롯·SourceReview·OneTrial·UAC·온라인 동작은 worker 검사에서0이다. 검증은 다음 명령이다.

```powershell
& 'C:\Users\Chansol\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B tools/local_native_login_spawn_render_retry_runtime/static_check.py
```

Root가 최종 `source-freeze.json`과 실제 소스·동결 근거를 검토한 다음, 동일 승인 범위에서 아래 명령을 순서대로 한 번만 실행한다. Worker는 실행하지 않는다.

```powershell
& 'C:\Users\Chansol\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B tools/local_native_login_spawn_render_retry_runtime/root-control.py SourceReview
& 'C:\Users\Chansol\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B tools/local_native_login_spawn_render_retry_runtime/root-control.py OneTrial
```

full Navigation/실제 이동/지속 플레이/PURPLE·공식 초기화 없는 독립 기동은 UNKNOWN·미검증이다. 타일 PASSABLE만으로 이동 승인을 만들지 않는다.
