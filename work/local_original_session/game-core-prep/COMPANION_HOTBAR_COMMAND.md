# 동료 단축창 수동 시전 명령 (W136)

2026-10-31. [기존 가용성 시험](COMPANION_HOTBAR_PROBE.md)을 이어 구현했다. **동료 마법창 → 원본 F8 등록·저장 → 법사 힐/공격 시전 및 기사 마법창 숨김을 동일 헤드리스 실행에서 확인했다.** 원본 전체 동등성·정상 종료의 종합 PASS는 아니다.

## 동작

- 사용자는 동료 설정의 DLL 전용 마법창 `SLCompSpell`에서 기사의 원본 단축창으로 마법을 끌어 놓는다. 원본 슬롯 `kind=1, spell row=key`를 원본 드롭 콜백으로 등록하고 원본 Config serializer가 `4ED6`을 보낸다. 최종 검증 입력은 **F8 키 → 대상 클릭**이다.
- 서버 선택 기능은 기존 등록 이름 `world_feature_companion_hotbar_probe`를 유지하되 실험 환경변수를 제거했다. 기본 켜짐이며, 동료 기능이 꺼졌거나 가용 법사가 없으면 새 목록/초기 IPC를 공급하지 않는다.
- 소유·소환·생존한 법사의 실제 학습 key 중 기사 미학습 key만 `4E60 f2=true, f6=1`로 공급한다. 학습 저장에 추가하지 않는다. 해제·사망·접속 상태 및 학습 변경은 tick/학습 hook에서 목록 추가·삭제(`f2=false`)로 반영한다. 기사가 직접 배운 key는 자신의 마법으로 통과시키며 f6도 원래 비용으로 복구한다.
- 저장된 소환 목록은 초기 `4ED7` 또는 `USER_START_DONE` 직전에 먼저 송신한다. 월드 진입 후 실제 소환과 다시 동기화한다. ATS 편집 종료/재진입 복원도 지시용 key를 지우지 않도록 공개 표시 hook을 사용한다.
- `4EE6`의 지시용 key는 기사 시전기로 넘기지 않는다. `CompanionMagic.cast(..., manual=True)`로 현재 법사가 시전한다. 수동 명령은 ATS 선택·자동 지원/전투 모드와 분리하며 실제 학습·레벨·생존·MP·재사용·거리·시야·마비/침묵·무게·대상 검사는 기존 경로를 유지한다. 효과·이펙트·아이콘·저장도 기존 소비자를 쓴다.
- 요청 대상은 기사·동료 자신의 실제 entity UID를 유지한다. 대상 없는 자기 마법은 법사 자신으로 해석한다. 현재 소비자가 지원하는 엔티티 대상 17종만 공급한다. **지면 좌표 소비자가 없는 마법과 다른 미지원 마법은 노출하지 않는다.** 수신한 좌표는 관측에 남기며 엔티티 대상으로 바꾸어 지면 마법을 지원한다고 주장하지 않는다.
- 17종: 힐/익스트라 힐/그레이터 힐, 실드/블레스드 아머/인챈트 덱스터리티/홀리 웨폰/인챈트 웨폰/디크리즈 웨이트, 에너지 볼트/아이스 대거/파이어 애로우/라이트닝/파이어볼/콘 오브 콜드, 큐어 포이즌/리무브 커스.
- 거절은 기존 SYSTEM_GM `4EEA code12066`로 `[LOCAL] <이름>: <짧은 이유>`를 보낸다. 정확한 동료 지시용 기존 클라 문자열은 확보하지 않아 LOCAL 문구를 선택했다. MP·거리·시야·마비·침묵·재사용 거절을 단위 시험했다.

## DLL 방식과 근거

- 기존 `SpellDragTick`의 드래그 종료점에 원본 HUD 드롭 대상 소비를 연결했다. UI thread·Pair move/release·원본 슬롯 분류 검사를 기존 ATS 드래그와 같은 방식으로 쓴다.
- CONTROL 정적 근거: 원본 `HudSlotLayoutPCImpl` target function64 vptr `1220550`, callback `9E2810` → `9DB6A0` 슬롯 복사/선택 갱신 → 원본 `11B7F0 → 104EA0 → 4ED6` 저장. 실제 드롭 JSON·원본 native 슬롯·수신 저장은 별도로 확인했다.
- 기사 마법창은 원본 **SpellAdapter 인스턴스의 vtable count/bind**만 필터링한다. 원본 vector/SpellSubsystem·학습을 제거하지 않는다. 실제 슬롯 개수/행 매핑에서 서버 지시용 key를 제외하고 남은 widget은 숨긴다. 원본 adapter의 갱신 구독을 유지하며 소유 layout Pair를 보유하고 종료 때 vtable/타이머를 정리한다.
- 서버는 기존 `companion_bridge_publish`/DirectoryHost에 `hotbar-keys`와 key 목록 JSON basename을 공급한다. 새 전송/큐/로그 체계는 만들지 않았다. 직렬화 때문에 `companion_bridge_host.py`의 명령 허용/파일 필드 처리 **2곳도 최소 수정**했다.
- 인라인 후킹·원본 함수 코드 패치는 추가하지 않았다. B-2는 시간 제한 안에 위 방식으로 구현·화면 확인했다.
- 이번 정적 조회는 기존 `ats-evidence/native_inspect.py`의 고정 CONTROL section/.pdata 자료를 재사용했다. 조사 스크립트/출력은 `_work/tmp/w136_native.py`, `w136-native-*.json/.txt`에 있다. 정적 분석 자체를 실행 근거로 삼지 않는다.

## 실제 헤드리스 결과

선정 DLL: `own-login-bridge-companion-glfw-input-hotbar-r2.dll`, SHA256 `7fe82b8131ad1e4fa724f53cd8e35ad86183419202ade41b325262a2e756714c`.

최종 실행: [w136-hotbar-20261031-05](../runs/w136-hotbar-20261031-05/verify-shots.json). 77단계가 OBSERVED46 / WAITED16 / POSTED14 / REPLIED1, UNKNOWN·REFUSED·SKIPPED0이다. 자동 결과의 `formal_pass:false` 원문은 유지했다.

| 확인 | 실제 결과·근거 |
|---|---|
| 동료 창에서 원본 F8 드래그·저장 | `SLCompSpell`의 힐(key0) → 원본 slot index3. DLL `HOTBAR_NATIVE_DROP_RETURNED`, native `kind1/key0`, 실제 `4ED6`/SELF config f1→f2 section→kind1/f4=0 확인. [드롭 후 PNG](../runs/w136-hotbar-20261031-05/after-w136-heal-drag.png), `verify-shots.json`의 `w136-confirm-native-save`. |
| 기사에게 힐 지시 | 원본 F8 키 → 기사 대상 클릭 → 실제 `4EE6 key0,target1`. 법사 actor268435479의 action19, 기사 대상 gfx744 송신. 실제 힐 **15**, 법사 MP **222→218**, 기사 MP **41→41**. [직전 PNG](../runs/w136-hotbar-20261031-05/w136-self-target-before.png), [시전 직후 PNG](../runs/w136-hotbar-20261031-05/w136-heal-immediate.png), [결과 JSON](../runs/w136-hotbar-20261031-05/w136-heal-result.json). |
| 힐 화면 | 직전/직후 원 PNG를 직접 열어 시전 위치의 새 흰색·금색 원형 이펙트를 확인했다. 기사 HP는 단계 시작50→최종86이며, 이 중 힐15와 별도 자연 회복을 구분한다. 기사 HUD MP41 유지. 법사 몸동작은 수목에 일부 가리므로 전신 동작을 명확히 본 것으로 확대하지 않는다. |
| 기사 원본 마법창 숨김 | 열린 원본 SpellLayout에서 borrowed17, visible borrowed0 / visible rows0. F8의 힐 아이콘은 유지. [원본 마법창 PNG](../runs/w136-hotbar-20261031-05/w136-knight-magic-hidden.png). |
| 공격 마법 | 동료 창 key3(에너지 볼트)를 F8에 다시 드래그·4ED6 저장 → F8 → 몬스터 대상 클릭. 실제 `4EE6 key3,target268435480`, 법사 action18, 대상 gfx167. 법사 MP **294→291**, 기사 MP **41→41**, 몬스터 HP **3→0**. [시전 직후 PNG](../runs/w136-hotbar-20261031-05/w136-attack-immediate.png), [결과 JSON](../runs/w136-hotbar-20261031-05/w136-attack-result.json). |
| 공격 대상 범위 | 기존 status 시나리오의 시험 NPC 구성 방식을 재사용한 **소모성 고블린(template245) 1개**다. 현재 맵의 비점유·통행 가능·실제 시야 타일에 놓고 정상 소비자의 학습/MP/시야/거리/타격/사망/보상을 통과했다. 자연 스폰·자동 AI 사냥 PASS는 아니다. |
| 이펙트/마법 실제 소비 | [w136-packets.json](../runs/w136-hotbar-20261031-05/w136-packets.json)에 action19/18과 gfx744/167, JSON에 실제 MP 차감·힐/피해가 있다. 원 PNG를 함께 확인했으며 패킷만으로 화면 성공을 주장하지 않는다. |

법사 MP 정확한 수치는 서버 cast 원장으로 판정했다. 기존에 열어 둔 펫 창의 숫자 텍스트는 이전 조회값184를 유지했다. 라이브 머리/파티 MP 막대와 이 숫자 표시를 혼동하지 않는다. 펫 숫자 텍스트 갱신은 이번 범위에서 고치지 않았다.

### 앞선 실행과 보존

| 실행 | 결과 |
|---|---|
| `w136-hotbar-20261031-01` | F5~F8에 실제 빈 저장 슬롯이 없어서 드래그 전 중단. F8은 없는 아이템 링크라 겉으로 비어 보였다. 이후 관측자 close의 현재 consumer 재조회 오류가 발생해 최종 result.json이 없으며 execution/verify-shots/PNG는 보존했다. |
| `w136-hotbar-20261031-02` | 소모성 시작 사본의 F8만 비웠으나, HUD 빈 슬롯을 찾는 시험용 트리 탐색 조건 때문에 입력 전 UNKNOWN. 제품 드롭 실패 아님. |
| `w136-hotbar-20261031-03` | 실제 UI 슬롯 발견. 좌표 근거 metadata를 기존 ATS 형식과 다르게 반환해 `INPUT_APPROVED_COORDINATE_BASIS_REQUIRED`, 드래그 입력 전 거절. |
| `w136-hotbar-20261031-04` | 원본 F8 등록·4ED6 저장 확인. MP3에서 단일 마우스 클릭·대상 클릭은 요청0. HP 상승은 자연 회복이며 시전 성공 아님. 결과 요약의 bytes 직렬화 오류도 보존했다. |
| `w136-hotbar-20261031-05` | MP41, F8 키 경로로 힐/공격·기사 마법창 숨김 확인. 추가 후보 대상 클릭은 이전 시전을 확인해 보내지 않았다. |

실제 게임 **5회**, 추가 실행 없음. 실행을 중간에 끊지 않았다. 매 실행 전 LC·12000/14030 listener 없음 확인. 매 실행 후 LC_LEFT0·게임 폴더 DLL baseline SHA256 `1d1f60a03144f0214bee56c4a875d4444d51811649135a1eaab82ec2e2899f75` 확인. Capture는11개 원파일로 복원됐다. 각 wrapper 로그 `_work/tmp/w136-headless-01.log`~`05.log` 보존. 01/04의 후처리 오류도 숨기지 않았다. 종료는 기존 harness의 **FORCED_CLEANUP**, `normal_exit_verified=false`, `game_logout_protocol=UNVERIFIED`다.

시험 시작 사본은 `_work/tmp/w136-profile`, `w136-profile-empty`, `w136-profile-high`. 기존 시험 사본에서 기사 HP1·MP2 또는41, 법사 PASSIVE/자동 support off를 준비하고, empty/high에서는 원본 f1 shortcut schema로 F8 링크만 비웠다. 마법 학습·사용자 저장은 바꾸지 않았다. runner는 각각 새 validation-profiles 사본으로 다시 복사했다.

재현 명령(5회 한도 사용 완료, 기록용):

```powershell
$env:VERIFY_INPUT_ROUTE='GLFW_CALLBACK_INJECTION'
$env:W136_ATTACK='1'
$env:TEMP=(Resolve-Path _work/tmp).Path
$env:TMP=$env:TEMP
& work/local_original_session/companion-bridge/run_verify_fresh_capture.ps1 -RunName w136-hotbar-20261031-05 -Steps companion_hotbar_command -SourceProfile '../../../_work/tmp/w136-profile-high' -Timeout 240 -CandidateBridge work/local_original_session/companion-bridge/own-login-bridge-companion-glfw-input-hotbar-r2.dll -CandidateSha256 7fe82b8131ad1e4fa724f53cd8e35ad86183419202ade41b325262a2e756714c
```

좌표는 현재 UI node `scene_bounds → node_to_capture`, 대상은 기존 `world_grid_to_capture`만 사용했다. HUD 슬롯도 native SlotNode/Panel_Slot로 찾았다. 드래그는 기존 ATS의11점·event40ms, crop(+480,0)은 기존 `capture_to_client`에서 한 번만 적용했다. F8은 같은 소유 GLFW key helper에 key297/scan0x42를 주며 전역 키보드를 쓰지 않는다.

## 단위·회귀 시험

```powershell
$hotbarModules=Get-Content _work/tmp/w133_test_modules.txt
python -X utf8 -m unittest @hotbarModules tools.local_original_session.world_companion_hotbar_command_tests

python -X utf8 -m unittest tools.local_original_session.world_companion_mp_loopback_tests tools.local_original_session.world_companion_resource_loopback_tests tools.local_original_session.world_companion_hotbar_command_tests tools.local_original_session.world_companion_hotbar_probe_tests

python -X utf8 -m unittest tools.local_original_session.world_companion_hotbar_command_tests tools.local_original_session.world_companion_hotbar_probe_tests
```

- 지정28모듈+새 시험 최종 묶음: **465개, 실패0, 오류2, skip1**. 462개 통과. 두 오류는 기존 MP/resource 루프백의 setup `WinError10048`(bind)이다. `_work/tmp/w136-regression-final.log`, `w136-regression-final-summary.json`.
- 오류2를 별도 순차 재실행하고 새·등록 시험을 함께 실행: **19/19 OK**, `_work/tmp/w136-final-isolated.log`. 두 루프백의 실제 MP/저장/표시 소비도 통과했다. 전체 묶음의 포트 오류를 없던 결과로 덮지 않는다.
- 마지막 추가 USER_START_DONE 순서 검사 포함 새15+등록2: **17/17 OK**, `_work/tmp/w136-command-final.log`. 목록 추가/삭제/사망/기사가 새로 학습/동료 없음/초기 IPC 무동작, F6, 힐·공격·기사 MP/쿨타임 불변, 거절 MP·거리·시야·마비·침묵·재사용, ATS 미등록 수동 지시, 원래 자동 ATS 조건 보존, malformed 소비, 선택 기능 제거, 두 복원 marker 앞 송신을 검증했다.
- `launcher_tests`, `manual_move_commands_tests`는 실행하지 않았다. 변경 Python 문법 검사 통과.
- 첫 회귀의 중복 실행으로 생긴 포트 오류와 중간 ATS 목록 개수 기대값 변화(`110 !=108`)도 원로그에 보존했다. 후속 최종 묶음에서는 ATS assertion 실패0이며 다른 worker의 magic/data 파일을 고치지 않았다.

## 새 DLL·빌드·수동 실행 핀

기존 vcvars64/cl 방식, `/std:c++17 /utf-8 /W4 /WX /EHsc /O2 /MD /LD`, `COMPANION_NO_CODE_PATCH`로 빌드했다. GLFW용은 기존 diagnostic/input define을 유지하고 수동용은 GLFW define을 제외했다. 소스 컴파일·링크 성공. 기존 def의 LIBRARY 이름 때문에 새 출력명과의 LNK4070 경고가 있으나 /OUT 새 이름을 사용했다. 기존 후보 DLL은 덮어쓰지 않았다.

| 용도 | 새 파일 | SHA256 | 빌드 로그 |
|---|---|---|---|
| 수동 | `companion-bridge/own-login-bridge-companion-nopatch-hotbar.dll` | `744487615fa0638b105d52e999982610a5ec33ae4c034051a99b7253e6d5be72` | `_work/tmp/w136-nopatch-build.log` |
| 헤드리스 선정판 | `companion-bridge/own-login-bridge-companion-glfw-input-hotbar-r2.dll` | `7fe82b8131ad1e4fa724f53cd8e35ad86183419202ade41b325262a2e756714c` | `_work/tmp/w136-glfw-build-r2.log` |

첫 성공 빌드 `own-login-bridge-companion-glfw-input-hotbar.dll`과 실패/수정 로그도 보존했다. 최종 헤드리스는 r2만 사용했다. 빌드 command는 `_work/tmp/w136-build-glfw-r2.cmd`, `w136-build-nopatch.cmd`다. IPC/PNG의 candidate_sha256(8b9e...)은 LC.guard 프로그램 식별자이며 위 DLL 파일 해시와 별개다.

헤드리스 확인 뒤 `manual-play/start-manual-play.ps1`의 핀2줄만 변경했다:

- 이전 `$bridgeCandidate`: `own-login-bridge-companion-nopatch.dll`, hash `84ca3a2c2946e9d483b67b0f2f175f80d3afa3b065aaf86ab47d5c6715415559`.
- 이후 `$bridgeCandidate`: `own-login-bridge-companion-nopatch-hotbar.dll`, hash `744487615fa0638b105d52e999982610a5ec33ae4c034051a99b7253e6d5be72`.
- 전 스크립트는 `_work/tmp/w136-start-manual-play-before.ps1`에 보존. 수동 게임을 실행하지 않았다.

## 고친 파일·줄

- `tools/local_original_session/world_feature_companion_hotbar_probe.py:32`: 가용 법사/실제 학습/지원 key·초기 복원 순서·실시간 목록·기존 IPC 목록 공급. `:160`: 공개 동료 cast 소비·LOCAL 거절. `:200`: 4EE6 분기·기사 key 통과.
- **`tools/local_original_session/world_feature_companion.py:291,540` 수정함**: eligible/cast에 keyword-only manual 옵션, ATS·자동 모드 조건만 분리. 학습/레벨·리소스/수명/시야/거리·효과 경로는 유지. 다른 worker 영역을 통째로 교체하지 않았다.
- `tools/local_original_session/world_feature_companion_ats.py:319,402,818`: 복원 표시 key 공개 hook 합성. 학습 권한과 분리.
- `tools/local_original_session/companion_bridge_host.py:25,63`: 기존 host 직렬화의 hotbar-keys 허용 및 view_file 처리. 명시된 기능 파일 외에 필요한 최소2곳이다.
- `tools/local_original_session/world_companion_hotbar_command_tests.py:9`: 새15개 소비자/리소스/목록/순서 시험. `world_companion_hotbar_probe_tests.py:1`: 폐기된 receive-only 실험 기대를 정식 선택 기능 등록 회귀2개로 갱신.
- `work/local_original_session/companion-bridge/companion_hotbar.hpp:26,43,80,96`: 표시 필터·key 공급·원본 HUD 드롭/저장.
- `companion5_ats_window.hpp:1508`, `companion_bridge_nopatch.hpp:318,1108,1166,1179`: 기존 드래그·파일 파싱·disable 정리·요청 처리 접점.
- `verify_ncg_waitonly.py:213,9051`: 선택적 F8 입력 및 단축창 드래그·저장·힐·숨김·공격 시나리오. 다른 시나리오의 본문은 바꾸지 않았다.
- `work/local_original_session/manual-play/start-manual-play.ps1:123,125`: 핀2줄.
- 이 문서와 `COMPANION_HOTBAR_PROBE.md:3` 후속 링크. world_handlers 등록 이름은 그대로여서 등록 줄 변경 불필요.

## 확인하지 못한 것

- 새 단축창 UX의 정확한 기사 MP0 및 낮은 양의 MP에서 F8 전송. 기존 가용성 MP1/2 결과는 마법창 입력이며 이 UX에 합산하지 않는다.
- MP3+단일 마우스 클릭 실행의 무수신 원인. MP41+F8 변경과 분리해 미확인으로 남긴다. 단일 클릭 시전 성공을 주장하지 않는다.
- 실제 재접속 후 저장 슬롯 재사용(목록 선송신·4ED6 저장은 검증). 다른 마법/다른 페이지/복수 법사 전체 UI 동등성.
- 수목에 가린 법사의 전신 시전 프레임, 펫 창 숫자 MP의 실시간 갱신, 정상 Quit/로그아웃.

금지된 magic/monster 파일·player_spells/spellbooks·classes.json·사용자 저장·기존 후보 DLL은 이번 작업에서 수정하지 않았다. DLL 게임 슬롯의 승인된 일시 배치/복원만 했으며 커밋·새 브랜치·하위 에이전트 없음. main의 다른 dirty/untracked 작업은 그대로 뒀다.
