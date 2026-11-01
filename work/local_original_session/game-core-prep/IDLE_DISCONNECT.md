# 무입력 접속 끊김 조사

2026-10-28. 대상은 확보된 원본 클라이언트와 현재 Python 로컬 서버다. 기존 저장·핀 DLL·실패 결과를 보존하고, 이번 실행은 별도 시험 사본을 사용한다. 이 문서는 원문 확인·연결 확인·실제 동작 확인을 구별한다.

## 현재 판정

- **(a) 생존 응답 누락: 최근 기록으로 지지되지 않음.** `4E2A → 4F57` 요청/응답 12쌍이 기록됐다. 기존 REA run21은 빈 protobuf 응답이 클라이언트 기대응답 task를 제거하는 경로를 확인했다. 서버의 추가 시간확인 응답이 필요하다는 근거는 아직 없다.
- **(b) 원본 무입력 종료 타이머: 한정 정적 조사에서 미확인.** 확인한 타이머는 Alive 응답 대기이며 float32 `20.0` scheduler delta 단위다. 입력 유무를 검사하는 분기는 이 직접 경로에 없다. 단위 producer 연결은 미완이므로 정확히 20초라고 확정하지 않는다. 입력 AFK 타이머 자체가 없다고 단정하지도 않는다.
- **(c) 현재 서버 무활동 제한: 없음.** 활성 stream의 전체 수명·무입력 deadline이 없다. bootstrap/partial-frame/drain 제한은 유지한다. 옛 `local_game_session/connection.py`의 별도 제한을 현재 broker 경로의 제한으로 혼동하지 않는다.

최근 원로그는 `../runs/manual-test-knight-20261027-234727-3cf8c2b9/{status,result}.json`이다. 마지막 수신은 생존 요청이 아니라 `Quit 4E3C`(10B), 다음 송신은 `4EEF`(8B)다. Quit request verified/response drained/empty queue가 확인된 뒤 `ConnectionResetError`가 기록됐으며 **FORCED_CLEANUP**이다. 이것만으로 Quit의 원인이 무입력이었다거나 정상 종료했다고 단정할 수 없다.

원로그의 패킷 ring에는 시각이 없다. 마지막 수신 시각·연결 reset 시각·두 사건 간격·무입력 시작 시각은 **UNKNOWN**이다. 주프로세스 PID16524의 native creation 2026-10-27 23:47:40.490771 KST부터 강제정리 exit 2026-10-28 00:00:20.985586 KST까지는 **760.494815초(약 12분 40초)**다. 이 프로세스 수명을 AFK 제한 시간으로 사용하지 않는다.

## 원본의 확인된 타이머와 원인 후보

고정 원문 `27936C → 32D2E0`은 상수 RVA `126ECD0`의 `20.0`을 응답 대기 등록 row+18에 보존한다. 송신 뒤 `27D8AE → B4E140`이 OneTimeTask+B0에 같은 값을 넣는다. Update `B4E270`은 받은 delta를 차감하고 `<=0`이면 callback을 부른다. `4F57` 실제 수신은 `27A41E/27A427 → 32D970 → 32DAC0/32DAC3 → B453F0`으로 기대 task를 정리한다.

만료 callback `32E76B..32E7C7 → 13C450(0x40)`은 disconnect 팝업을 연다. 팝업 승인 lambda `140A60 → 13C0D0`은 Quit를 호출한다. 다른 직접 Quit caller는 UI callback `ACBDA0`다. 따라서 최근 Quit는 사용자 종료 버튼 또는 disconnect 팝업 승인 경로와 양립한다. **최근 실행에서 팝업이나 응답 소비 실패를 관측한 것은 아니다.** 이 후보를 실제 원인으로 확정하지 않는다.

서버 대안도 이 경계에서 판단한다. 기대 opcode `4F57`의 수신은 Alive 대기를 제거하지만, 임의 서버 패킷이나 선제 `4F57`이 입력 AFK 타이머를 reset한다는 근거는 없다. 이미 요청에 응답하고 있으므로 주기 송신을 추가하지 않았다. AFK 값/조건과 원인 연결이 없어 기존 DLL을 보존하고 새 타이머 hook 후보도 만들지 않았다.

## 적용한 변경과 출처

- `tools/local_original_session/broker.py`: 기존 `last_received_frame.received_monotonic_ns`와 최초 `failure_monotonic_ns`를 추가했다. 다음 실패 시 동일 monotonic clock에서 마지막 수신부터 실패까지의 간격을 계산한다. 프로토콜·timeout·종료 판정을 바꾸는 수정은 아니다.
- `tools/local_original_session/broker_idle_tests.py`: 후속 정리 실패가 최초 실패 코드/시각을 덮지 않는지 확인한다.
- `work/local_original_session/manual-play/start-manual-play.ps1`: 변경한 broker의 기존 핀만 갱신했다. UTF-8 BOM `EF-BB-BF`를 유지했다.
- `idle_disconnect_loopback.py`: 기존 HuntBot 로그인·월드 진입·지속 수신·Alive·Quit 경로를 재사용한 900초 실제 시간 시험이다. 무입력 구간에는 플레이 요청을 보내지 않고 생존 요청만 보낸다.
- `idle_disconnect_native.py`, `run_idle_disconnect_native.ps1`: 사용자 지정 scratchpad 스크립트와 기존 Scenario를 재사용한 순수 idle 시험 복사본이다. 이동·공격·버프·인벤토리 시나리오를 제외하고 idle/tool 시간 범위만 시험 복사본에서 연장했다. 기존 source-Quit 후보 `d5865458…`를 사용하므로 최근 수동 실행의 baseline `1d1f60a0…`와 구별한다. 불변 DLL 후보 자체를 덮어쓰지 않으며, 검증된 시험 slot만 임시설치하고 finally에서 baseline으로 복원한다.

출처 비율: 통신 처리 경로는 기존 서버/원본 계약을 100% 재사용했고 새 opcode/응답은 0건이다. 새 시각 진단·시험 제어는 100% 로컬 구현이며 원본 기능 복원이라고 주장하지 않는다. 원본 패킷/타이머 수정 0건, 신규 DLL 후보 0개다. 아직 특정하지 못한 AFK 조건을 로컬 정책으로 대신 확정하지 않았다.

서버 변경 후 SHA256: `d21c30274189b7c7acea0399e0e0030729ed301247a338aa2d0170e68e3374db`. 수정 전 dirty source/diff는 `idle-server-before.broker.py`, `idle-server-before.broker.diff`에 보존했다. 다른 작업자의 파일과 기존 사용자 profile은 수정하지 않았고 git commit도 하지 않았다.

## 검증

포트 없는 개발 단위검증 12개 OK: 신규 최초 실패 시각 보존 1개, 기존 Alive schema/route/policy 8개, 기존 장시간 idle·partial/drain deadline 3개. 실제 원본 입력·화면·AFK 유지 검증과 구별한다.

해당 개발 검증의 재실행 명령:

```powershell
python -X utf8 -B -m unittest tools.local_original_session.broker_idle_tests tools.local_original_session.broker_tests.AliveSchemaTests tools.local_original_session.broker_tests.AliveRouteTests tools.local_original_session.broker_tests.AlivePolicyTests
Push-Location tools/local_persistent_broker_policy
try {
    python -X utf8 -B -m unittest tests.PolicyTests.test_idle_hours_with_fresh_owner_and_no_total_quota tests.PolicyTests.test_partial_timeout_absolute_no_byte_trickle_extension tests.PolicyTests.test_drain_timeout_and_changed_owner_after_write
} finally {
    Pop-Location
}
```

### 루프백 15분

명령(프로젝트 루트, PowerShell):

```powershell
$env:SL_TEST_PORT_BASE = '26000'
python -X utf8 -B work/local_original_session/game-core-prep/idle_disconnect_loopback.py --idle-seconds 900
```

[실행 결과](../runs/idle-disconnect-loopback-xam0kb4n/result.json), [시작 소스 manifest](../runs/idle-disconnect-loopback-xam0kb4n/source-sha256.json), [실행 인수](../runs/idle-disconnect-loopback-xam0kb4n/invocation.json).

- 실제 무입력 **900.016초**, gameplay 요청 0, Alive 응답 **16/16**. 마지막 추가 Alive 응답을 받은 시점에도 selected/HP20/20/좌표32595,32906이며 reader error는 null이었다.
- 이후 Quit ACK 수신, 실제 EOF·positive close·joined·registry 제거 모두 확인. 종료 후 Peer의 `SERVER_EOF`는 이 Quit 뒤 관측이다. broker failure null, cleanup true, active tasks/registry sessions 0.
- **스크립트 exit 1 / Source 고정 판정 실패.** 시험 중 타 작업자의 파일 12개가 바뀌었다. 우리 broker는 변경되지 않았다. loaded runtime의 900초 행동 유지와 디스크 소스 조합 불일치를 구분하며, 이를 엄격한 고정 Source 정식 PASS라고 표시하지 않는다. 변경 목록은 result 원문에 보존했다. 타 변경을 롤백·재핀하거나 이번 수정에 포함하지 않았다.
- 기존 fixture의 owner/equipment 대용 객체는 socket 시험 경계다. 이 결과는 원본 UI·입력·렌더링·DLL이나 AFK 타이머를 입증하지 않는다.

### 원본 헤드리스

`idle-disconnect-native-20261028-003500`을 순차 1회 실행했다. 시작 전 LC.guard와 12000/14030/26000/28030 listener가 없고 slot/baseline/candidate의 기존 핀이 맞는지 확인했다. 실행 시작/종료 Source와 외부 변경을 구분하며 기존 source guard를 제거하지 않았다.

초기 관측은 로그인/Slot/SelectOK RETURNED, Land/none, world stable double-read/UID1/좌표32576,32946이다. 다만 move_state 읽기가 기존 `RETAINED_SAMPLE_BYTE_BUDGET`에 걸려 UNKNOWN이며, 기존 strict idle의 시작 조건이 충족되지 않았다. 실제 무조작 연결 시간과 `idle_hold_complete`를 구별한다. 관측 예산·ready 조건을 바꿔 성공을 만들지 않았다.

**원본 15분 미확인 / 부분 기록.** 래퍼는 예상보다 일찍 shell exit0 / `RUN_EXIT=-1`로 반환했다. 이번 run의 status는 elapsed323.812초에서 stale이며 `result.json`이 없다. 323.812는 마지막 관측의 경과시간이지 실제 종료 시각이 아니다. 최초 원인·정상 Quit·FIRST/close·owned Job 최종화는 최종 원문이 없어 UNKNOWN이다. 래퍼 반환을 성공으로 표시하지 않는다.

마지막 status는 Land/none·broker failure null·마지막 수신4E2A·이동 요청/commit0이다. 이후 읽기 전용 확인에서 이번 exact-script Python과 기록된 owned PID48708/25140/5356은 모두 없었다. 원시 부분 결과는 [interrupted-observation.json](../runs/idle-disconnect-native-20261028-003500/interrupted-observation.json)에 있다. 프로세스 부재를 정상 Job/FIRSTclose 증거로 대체하지 않는다.

이어 발견한 Python47456/LC.guard15028은 이번 시험이 아니라 2026-10-28 00:40:05/00:40:24 KST에 시작한 `sibling-manual-play-spawn` / `manual-test-knight-20261028-004005-62e10023`이었다. 이 별도 수동 플레이에는 attach·입력·종료·저장 변경을 하지 않았다. 시험 재실행도 하지 않았다. slot은 baseline으로 돌아온 것을 확인했으며, 불변 DLL 후보 자체는 변경하지 않았다. 시험 중단 원인을 AFK 또는 타 작업자의 강제종료라고 추측해 확정하지 않는다.

원본 재실행 명령은 이번 시도의 재현용 기록이며, 이번 작업에서는 두 번째 실행하지 않았다:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File work/local_original_session/game-core-prep/run_idle_disconnect_native.ps1 idle-disconnect-native-20261028-003500
```

같은 이름의 실행·profile은 이미 존재하므로 이 명령을 그대로 재실행하면 기존 fresh-run 검사에서 거절된다. 원문과 부분저장을 덮어쓰지 않는다.

## 근거와 미확인

- 서버 조사: [idle-server-findings.md](idle-server-findings.md).
- 원본 정적 조사 및 검색 한계: [idle-native-findings.md](idle-native-findings.md). 기존 fixed CONTROL/분석용 carrier를 읽은 근거이며 현재 loaded code의 실행 관측과 구별한다.
- 시험 원문: [idle-test-findings.md](idle-test-findings.md).
- 원본 계약: [run21 findings](../../local_server_rea_20261016/run21_4e2a/findings.md).
- 원본 입력/종료 타이머, 서버 수신으로 입력 타이머를 reset할 수 있는지, 최근 Quit를 촉발한 실제 원인은 아직 미확인이다.
- 현재 실제 원인 수정은 완료하지 않았다. 관측 보강과 장시간 시험을 원인 수정 완료로 표시하지 않는다.
