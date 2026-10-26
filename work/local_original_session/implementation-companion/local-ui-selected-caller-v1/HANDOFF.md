# COMPANION-MAGE — selected caller source descendant

2026-10-24. **WRITER_RELEASED**. 소유 범위는 이 private 폴더뿐이다. 공용/원본/Test/queue/ACTIVE/Git에는 쓰지 않았다. 프로세스·Job·DLL 실행·서버·포트·게임·화면·입력·Store 사본 소유는 0이다.

## 실제 완료

- 부모 `companion-account-click-host-v1/cohort.json`의 185행을 이어받아 **launcher 한 행만** 이 폴더의 실제 `launcher.py` 후손으로 선정했다. 184행은 원본과 같은 path/bytes/SHA다. `source_loader.py`와 `dependencies.json`은 부모와 바이트 동일하며, loader의 기존 HERE 기준 선정이 새 cohort를 읽는다.
- launcher 전체 source는 정확 부모 `integration-1/adena-book-integration-v1/launcher.py` SHA256 `1cc72cdccbb703e8b85485a3ba677ef14fbe1b7ee18920869921337b8750ec11` 후손이다. `main`이 자체 전역의 `run_session`을 호출하며, 별도 미선정 session 함수가 아니다.
- 원 NativeOwner·ProductFeatureFactory·ProductFeatures class AST와 nominal type 공간을 보존한다. 원 Broker/Factory inventory owner guard·monitor·source-quit·Store cleanup·프로필 검사·시작 순서가 보존됐다는 근거는 새 추가만 역변환한 **전체 launcher AST의 원본 일치**다. monkeypatch/subclass/guard 완화/가짜 DLL은 없다.
- 기존 `local-ui-launcher-owner-compat-v1/session_composition.py`의 검토된 `_tick`/`_close`를 명칭만 바꿔 사용했다. `LocalUiTransport`는 manifest `3f7a72b248259f19e34e16fb70d2b9b3dc4a8cd995a8334d17c79974323e3077`의 `local_ui_channel.py`를 바이트 그대로 이 폴더에 보존·핀한다.
- 실제 caller source 경로: 원 `owner.prepare()` → suspended 원 owner에 LocalUiTransport 생성/issue → 원 monitor/Broker/start/Feature/source-quit 준비 → channel current 확인 → 원 `owner.resume()` → `primary_resumed=True` → activate → 원 두 tick(일반/close-grace)에서 원 owner.tick 뒤 poll → 원 Broker/Store close 뒤 exact channel/owner cleanup. channel close 실패에도 원 owner.close는 finally에서 수행하고 native 종료 뒤 exact artifact 제거를 재시도한다. 기존 control-flow helper 결과를 재사용하며 게임 성공으로 확대하지 않는다.

## 실행 차단과 미완

**기능 전체 source_ready=false / test_ready=false / runtime_ready=false / runtime UNRUN.** selected caller source 연결만 완료다. 실제 selected UI model, Host binding, OPEN/CLOSE, panel rendering, 선택 캐릭터 scope 전환, UI 작업 성공은 미구현/미확인이다. transport 자체는 기존 인증된 REQUEST_MODEL/UNBOUND 응답만 유지하며 Host actions=0이다.

선정 `operating_input.py`는 기존 native394 DLL SHA256 `1e18afd8643d5a60e941782726c681b1c0a1e2944f700933dd28d4256de742d6`, native manifest `b419f1d20438448af90f9693d0844edf0887f0103bd3687633a851909baa1e33`, receipt `767b535fa0526e5ce329409933f0dd861c132b11ab076b54ae3866b082268638`를 그대로 요구한다. 이 DLL이 새 transport native 후손이라고 표시하지 않았다.

새 launcher `main`은 새 run-directory/owner/DLL/listener 생성 전에, 직접 `run_session`은 첫 실행 문장에서 `LOCAL_UI_PAIRED_NATIVE_DLL_RECEIPT_INPUT_REQUIRED`로 차단한다. 플래그·환경변수·가짜 receipt로 해제하는 API는 없다. 다음 실제 paired native DLL + build receipt + 정확 NativeInput/선정 후손이 마련되면 별도 source descendant에서 해당 gate를 올바른 검사로 대체해야 한다. 이번 caller의 실행 명령은 **null**이다.

## 확인 근거

`python -B work/local_original_session/implementation-companion/local-ui-selected-caller-v1/verify_source.py`

실제 결과: **PASS, 224 checks**, 185 pinned cohort rows / 184 unchanged, 183 genuine cold modules. 전체 launcher inverse AST exact parent, 원 세 class AST exact, main→run_session 전역 연결, 두 tick 및 prepare/issue/resume/activate 순서, 원 helper AST 재사용, 원 native394 3파일 실제 hash, paired-native gate 자원생성 전 거절을 확인했다. cold import/class 로딩만 실행했으며 NativeOwner/transport 인스턴스·게임·DLL/포트는 만들지 않았다. 원본 runtime 효과·속도·UI 성공을 이 결과로 추정하지 않는다.

정확 부모/입력은 `parent-pins.json`, 출력과 검증 파일은 `manifest.json`, 실제 변경분은 `launcher.diff`, 원 native394 읽기 핀은 `verification.json`에 있다. Root가 실제 delta와 선정 변경만 검토하고 큐에 공급한다. 이 worker는 큐나 공용 소스를 선정하지 않는다.
