# AFK/idle 서버 조사

2026-10-28. **원인 미확정. 서버 idle timeout/누락 Alive 응답이라는 증거는 없으며, 이번 변경은 다음 실행의 시간 관측 보강이다.** 게임·포트 실행은 하지 않았다.

- 관측: `runs/manual-test-knight-20261027-234727-3cf8c2b9/result.json`의 기존 ring은 `4E2A → 4F57` 12쌍을 포함한다. 마지막 수신은 `4E3C` Quit(10B), 다음 송신은 `4EEF`(8B)다. quit metadata도 request verified/response drain/empty queue 모두 true다. 이후 `ConnectionResetError`, 원 `FORCED_CLEANUP`을 그대로 보존한다. 정상 EOF나 정상 종료로 판정하지 않았다.
- 시각: 기존 ring/last_received_frame에는 시각이 없다. **마지막 수신 시각, socket reset 시각, 두 사건 사이 간격은 UNKNOWN.** PID16524의 native creation은 2026-10-27 23:47:40.490771 KST, 강제정리 exit는 2026-10-28 00:00:20.985586 KST, lifetime 760.494815초다. 이것은 수신/끊김 시각이 아니다. Alive 12회와 전체 수명으로 실제 주기·AFK deadline을 확정하지 않는다.
- 연결 확인: `tools/local_original_session/broker.py`의 selected Alive route는 `4E2A`를 typed parse하고 같은 writer로 `4F57/body0B`를 응답한다. [run21 계약](../../local_server_rea_20261016/run21_4e2a/findings.md)은 이 응답의 실제 parser·기대응답 task 제거까지 연결한다. request f1/f2/f3는 optional int64/int32/bytes이며 값의 업무 의미는 UNKNOWN이다. 원본 입력/AFK timer reset 계약은 이 근거에 없다.
- 코드 확인: 현재 경로는 `local_game_session/session.py`를 사용한다. `PersistentPolicy.checkpoint`는 bootstrap 15초, partial frame 10초, drain 2초를 구분하며 활성 stream에 total/idle deadline은 없다. broker `_serve`도 pending read를 취소하지 않고 100ms poll한다. old `connection.py`의 별도15초 deadline은 이 경로 원인으로 보지 않는다.

변경은 `broker.py` 5줄이다. 기존 `last_received_frame.received_monotonic_ns`는 decoded frame을 처리하기 직전 시각, `failure_monotonic_ns`는 최초 `_fail` 시각이다. 같은 monotonic clock으로 다음 실행의 두 사건 간격을 계산할 수 있다. 패킷 내용·로그 ring 형식·프로토콜·owner guard·timeout·종료 판정은 바꾸지 않았다. `4F57`의 추가 선제 송신이나 추측한 시간확인 응답을 만들지 않았다.

수정 전 파일과 기존 dirty diff는 같은 폴더의 `idle-server-before.broker.py`/`idle-server-before.broker.diff`에 보존했다. Source SHA256은 `d21c30274189b7c7acea0399e0e0030729ed301247a338aa2d0170e68e3374db`다. 다른 dirty 파일·사용자 profile/저장·기존 결과에는 쓰지 않았고 commit은 하지 않았다.

no-port 개발 단위검증 12개 OK: `broker_idle_tests` 1개, 기존 `AliveSchemaTests`/`AliveRouteTests`/`AlivePolicyTests` 8개, 기존 policy의 장시간 idle/fresh owner·partial deadline·drain deadline 3개. 최초 policy 실행 명령은 루트 `tests.py` 경로 오류였고 올바른 모듈 디렉터리에서 재실행했다. 이 결과는 실제 원본 AFK 유지/입력/화면/정상종료 PASS가 아니다. 전담 시험 worker가 Source를 고정하고 15분 유지와 이후 이동·입력, Quit/close의 실결과를 확인한다.
