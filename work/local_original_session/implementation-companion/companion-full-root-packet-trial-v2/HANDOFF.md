# COMPANION-MAGE full-root packet trial v2 — F1 close predicate

WRITER_RELEASED / source_ready:true / run_ready:true / test_ready:true / runtime:UNRUN.

준비 범위는 기존 full-root UID1 정상 WORLD→empty SKILL 원 CAS 설치→정상 close→같은 사본 fresh WORLD 확인뿐이다. 원 184 graph/Plan/SKILL/actor/Host/common client-v5/API와 정상 패킷·저장 경로는 바꾸지 않았다. actor/소환/support/Native UI 성공이나 준비를 주장하지 않는다.

부모 caller `companion-full-root-packet-trial-v1/run_feature.py` SHA256 `183851106797c31b36391528de4d375bc357c46274f18ecd7cf6d27dd2ced522`의 finally에만 strict fault 판정 한 loop를 추가했다. SHOP v61의 accepted post-close predicate를 재사용하며 원 before/after snapshot 모두에서 다음을 검사한다: `failure_code is not None`, connection `failed is True`/`error`, completion `status == ERROR`/`error`. 마지막 항목은 ERROR status가 없이 error만 남는 경우도 거부한다.

첫 해당 원 row.error 또는 completed.error는 원문 `original_error`와 기존 type/code/message/stack을 보존한다. 최초 `first_error`가 이미 있으면 덮어쓰지 않고 late fault를 cleanup_errors에 남긴다. 두 원 snapshot은 수정하지 않는다. 서버 close가 raise하지 않아도 fault가 있으면 `clean_owner_close:false`가 되며 기존 FIRST 실패 gate가 FRESH/PASS 진입을 막는다. 원 raw partial Store capture·최종 보존은 판정 앞에서 그대로 수행하며 rollback/reset/재송신은 없다.

`caller.diff`는 유일한 제품 실행부 delta다. `input-source.json`은 v1과 byte 동일한 실제 mage31 전체7파일/획득 PASS 근거이며, scenario는 v2 입력 경로와 close 판정 설명만 갱신했다. RUN_COMMAND는 같은 sibling caller 명령이고 v2 표기만 추가했다. 부모와 accepted predicate·root F1 리뷰의 정확 핀은 `parents.json`, 원 runtime pins·184행 선정·정책·사본 근거는 `manifest.json`으로 그대로 승계한다.

Test만 원7파일의 **새 독립 전체사본**과 새 결과 경로를 준비하고 아래 명령을 실행한다. 원본/기존 실패사본 변경·부분 overlay·복원·기능 구현자의 서버/포트 실행은 없다.

```powershell
powershell -NoProfile -File "C:\Users\Chansol\Documents\ChatGPT\싱글리니지\work\local_original_session\implementation-companion\companion-full-root-packet-trial-v2\RUN_COMMAND.ps1" -Copy "<Test NEW whole-copy absolute directory>" -Result "<Test NEW absolute result.json outside profiles>"
```

최소 확인 PASS: v2 AST에서 새 finally loop 한 개를 제거하면 v1 전체 AST와 동일하다. 같은 실제 finally fragment의 scalar snapshot 8경우(정상/late failure_code/failed/error/completed ERROR/completed error만/before fault·after clean/기존 firsterror 보존), 원 snapshot 불변, 원 error text·stack 보존을 확인했다. 문법과 `--help`만 실행했으며 원 cold Plan·9 source checks는 재사용했다. runtime/product import/server/socket/시험사본 생성/포트/REA/게임/공용 수정/큐 등록·메시지 0이다. `verification.json`은 source 수준 결과이며 실제 late fault나 게임 통과 관측이 아니다. main이 실제 diff를 검토해 같은 큐에 등록한다.
