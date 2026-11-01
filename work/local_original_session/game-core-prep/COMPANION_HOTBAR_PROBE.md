# 동료 마법 단축창 가능 여부 시험 준비 (W134)

> ?? ?? ?? ??? ? UX? ????? ??? [COMPANION_HOTBAR_COMMAND](COMPANION_HOTBAR_COMMAND.md)? ???. ?? ??? ?? ???? ????.


2026-10-31. **기본 시험3회 + 아래 f6 후속 실제 게임2회 완료 / 가능 여부 시험 / 본 구현 아님.** 기사는 미학습, 소유 법사는 기존 38개 학습 상태이며 클릭 대상은 힐 key0이다. 실제 PNG를 직접 열어 아래와 같이 판정했다.

| 질문 | 판정 | 실제 근거·캡처 |
|---|---|---|
| Q1 기사에게 법사 마법 4E60 upsert → 기사 마법창 표시 | **예** | 기사 레벨30·자기 학습 없음·법사 key0 학습. 힐 포함 첫 페이지 8개 아이콘 표시. 클릭 후 `힐`, MP/HP[4/0] 설명 확인. [첫 표시 PNG](../runs/w134-hotbar-enough-20261031-01/w134-spell-window-before.png), [MP41 힐 선택 PNG](../runs/w134-hotbar-enough-20261031-02/w134-message-after-spell-click.png), [MP0 힐 선택 PNG](../runs/w134-hotbar-zero-20261031-03/w134-message-after-spell-click.png). 38개 전부의 화면을 확인한 것은 아님. |
| Q2 단축창 드래그·4ED6 저장 요청 | **UNKNOWN** | 검증된 단축창 드래그 방법이 없어 미실행. 슬롯·저장 가능 여부 미판정. |
| Q3 마법창 클릭 → 4EE6, MP 충분 | **예** | MP41에서 실제 원본 마법 더블클릭·자신 대상 클릭 뒤 `4EE6 key=0, target=1, mp=41, cast=false` 수신 1건. [수신 JSON](../runs/w134-hotbar-enough-20261031-02/w134-result.json), [대상 클릭 후 PNG](../runs/w134-hotbar-enough-20261031-02/w134-message-after-target.png). |
| Q3 마법창 클릭 → 4EE6, MP0 | **아니오** | 같은 클릭 경로에서 서버 MP0·화면 MP0/41 유지, 4EE6 수신0. 캡처에 **마법 사용: 불가(MP 부족)**. [결과 JSON](../runs/w134-hotbar-zero-20261031-03/w134-result.json), [거절 문구 PNG](../runs/w134-hotbar-zero-20261031-03/w134-message-after-target.png). |
| Q3 단축창 클릭 → 4EE6, MP 충분 / MP0 | **UNKNOWN / UNKNOWN** | Q2 미실행으로 단축창 클릭도 미실행. 마법창 결과로 대신 판정하지 않음. |
| Q4 기사 직업 때문에 차단하는 메시지 | **아니오 — 이번 힐 경로** | MP41은 수신 성공·직업 제한 문구 없음. MP0은 MP 부족 문구만 관측. [MP41 클릭 후](../runs/w134-hotbar-enough-20261031-02/w134-message-after-target.png), [MP0 클릭 후](../runs/w134-hotbar-zero-20261031-03/w134-message-after-target.png). 다른 법사 전용 마법의 직업 차단은 **UNKNOWN**. |

**기본(f6 미지정) 시험 해석:** 미학습 마법을 표시하고 기사 자신의 MP가 충분할 때 입력 요청을 받는 경로는 가능하다. MP0에서는 원본 클라이언트가 자기 MP로 막으므로, 이 방식 그대로는 기사 MP와 무관한 동료 시전 명령을 보장하지 못한다. 단축창 등록과 다른 마법은 미확인이다. 시험 key를 실제 플레이어/동료 시전으로 연결하지 않았다.

## 실행 결과·보존

| 실행 | 조건·결과 | 종료·원복 |
|---|---|---|
| [01: MP 충분](../runs/w134-hotbar-enough-20261031-01/verify-shots.json) | 시작 MP41. upsert38개, 마법창·PNG 성공. 기존 `spell_rows`가0개라 `w134-visible-key0` UNKNOWN, 이후 클릭은 SKIPPED. PNG 직접 검토로 힐 아이콘 확인. | wrapper exit0, FORCED_CLEANUP, LC_LEFT0, Capture 복원, DLL 원복 확인. |
| [02: MP 충분](../runs/w134-hotbar-enough-20261031-02/verify-shots.json) | 첫 PNG에서 측정한 같은 창 크기 좌표로 진행. 마법 선택5 native events, 대상 클릭3 events 완료. MP41에서 key0/target1 수신1건. PNG5개. | wrapper exit0, FORCED_CLEANUP, LC_LEFT0, Capture 복원, DLL 원복 확인. |
| [03: MP0](../runs/w134-hotbar-zero-20261031-03/verify-shots.json) | 시작·마법 클릭 전·대상 클릭 전·끝 모두 MP0. 선택5/대상3 native events 완료. 수신0·MP 부족 메시지. PNG5개. | wrapper exit0, FORCED_CLEANUP, LC_LEFT0, Capture 복원, DLL 원복 확인. |

총3회로 한도를 소진했다. 첫 실행의 노드 탐색 실패는 두 번째에서 해결됐으며 같은 원인2회 실패는 없었다. 실행을 외부에서 중간에 끊지 않았다. 기존 harness의 정리 경로가 세 실행 모두 `exit_outcome=FORCED_CLEANUP`, `normal_exit_verified=false`, `game_logout_protocol=UNVERIFIED`를 기록했으므로 정상 Quit/로그아웃 PASS로 표시하지 않는다. 각 원본 `result.json`·`verify-shots.json`·`execution.log`·입력 JSON·PNG는 보존했다. 수동 화면 판정은 이 문서에 기재했으며 자동 결과의 `UNKNOWN_PENDING_*` 원문은 덮어쓰지 않았다.

매 실행 직전 LC/LC.guard0·12000/14030 listener0을 확인했다. 매 실행 직후 게임 폴더 DLL SHA256은 모두 `1d1f60a03144f0214bee56c4a875d4444d51811649135a1eaab82ec2e2899f75`로 확인했다. 지정 runner가 후보 DLL을 일시 배치하고 baseline으로 복구했으며 DLL 소스/내용 수정은 없다. 마지막에도 게임·리스너 없음. 원본 Capture 파일3개가 각 실행 후 복원됐다.

시작 사본은 `_work/tmp/w134-headless-20261031/profile-enough`와 `profile-zero`. 기존 정상 기사·법사 사본 `validation-profiles/glfw124-head-mp-20261030-d`의 top-level 파일을 복사하고 **기사 vitals.mp만 각각41/0으로 설정**했다. 최대MP41·학습·직업·인벤토리·장비·UID·동료 기록은 바꾸지 않았다. source를 읽기 전용으로 두고 runner가 각 `validation-profiles/<RunName>`으로 다시 복사했다. MP0은 실제 입력·캡처 시점에도0이었으며 강제 유지/재생 차단은 넣지 않았다. 사용자 저장을 수정하지 않았다.

실행02의 `w134-result.json:7`이 수신 이벤트, `:12`가 key0, `:13`이 target1, `:14`가 MP41이다. 실행03의 `w134-result.json:4`가 끝 MP0, `:5`가 빈 수신 목록이며 `w134-input-before-spell.json:3`과 `w134-input-before-self.json:3`도 MP0이다. 실제 broker 결과 위치는 각 `result.json`의 `broker.world.companion_hotbar_probe`다.

선정 소스 식별: probe 모듈 SHA256 `819a0c0c35af42dd20d88cff5d187e6b5df8f61dd8849b1e878cf04e04f91eaf`; 실행01 harness `81fcacee86f0daa5aa64d25003af142236fd8d8d1cec45ee8b380f8729893aa2`; 실행02/03 harness `b8809c107267d79c7eed355105b82f169da74db383f2b79b412040d0954a21db`. MP41/0 시작 `vitals.json` 해시는 각각 `767fa83b1c1ca8bb547976c25ab76f106c08acbf17434234efdaf68598571563`, `924ddc9f47ccac891629d25032375309a5e74b8de442280a35412bd137b7ca5a`. 전체 원본 동등성·정상 종료의 정식 PASS가 아닌 위 UI/수신 범위의 관측이다.

## 만든 파일·등록

- `tools/local_original_session/world_feature_companion_hotbar_probe.py:17`: 환경변수가 정확히 `1`일 때만 활성화. 기본 꺼짐.
- 같은 파일 `:33`: 기사(class1) 진입 후 소유 법사(class3)의 학습 권한을 `character_learned_spells` 훅으로 읽어 기사 미학습 key만 4E60 f1/key, f2/true로 송신. 학습 저장·MP·동료 상태를 변경하지 않음. 기본에는 SpellInfo.f6을 보내지 않아 원래 클라이언트 비용 검사를 관측함. 후속 opt-in f6=1 시험은 아래에 별도 기록.
- 같은 파일 `:58`: 시험에서 주입한 key의 4EE6을 시전 처리 앞에서 소비. key·signed 대상·서버 MP·시각(epoch/monotonic)·`cast:false` 기록. 일반 key는 기존 경로로 통과. 4ED6은 수신 메타데이터만 남기고 기존 ATS/설정 저장 경로로 통과.
- 같은 파일 `:101`: 연결 종료 시 시험 세션 제거. `:105` report 훅이 `world.companion_hotbar_probe.events`에 결과 기여. 실제 기존 report 진입점은 `world_bridge.py:691`, 훅 호출은 `:717`.
- `tools/local_original_session/world_handlers.py:879`: 선택 기능 등록 1줄. 목록에서 빼도 나머지 코어·기능 등록 정상(단위 시험).
- `tools/local_original_session/world_companion_hotbar_probe_tests.py:36`: 새 오프라인 시험 8개. 기본 꺼짐·소유/직업/미학습 key·upsert wire·MP 충분/0·signed target·일반 마법 통과·설정 관측·수명·실 bridge receive dispatcher 순서·등록 제거 확인.
- `_work/tmp/w134_scenario_patch.py:15`: 동기화된 시나리오 초안. 실제 적용은 `verify_ncg_waitonly.py:8608`의 `W134_STEPS`, `:8629`의 선택 시나리오 설치 함수, `:8765`의 호출이다. 기존 본문과 다른 선택 시나리오는 보존했으며 적용 전 본문과 W134 블록 제거 후 본문이 일치함을 확인했다. `:8673`은 캡처 측정 fallback, `:8685`는 입력 직전 MP/좌표 기록이다.

ATS 기능 파일, 기존 magic/monster 모듈·자료, 동료 코어, 사용자 저장은 수정하지 않았다. 기존 `verify_ncg_waitonly.py`에는 허용된 새 선택 시나리오만 추가했다. DLL은 지정 runner의 일시 교체·원복만 수행했으며 내용 수정·새 빌드·커밋 없음. 시작 브랜치는 기존 `main`; 다른 작업의 많은 dirty/untracked 파일은 보존했다.

## 실행에 사용한 설정 (3회 한도 소진, 추가 실행하지 않음)

기존 로컬 시험 서버/owned desktop runner의 환경에 다음을 넣고 새 프로세스로 시작한다.

```powershell
$env:SL_COMPANION = '1'
$env:SL_EXPERIMENT_COMPANION_HOTBAR = '1'
$env:W134_MP_CASE = 'enough'  # 별도 MP0 시험은 'zero'
```


실제 명령은 다음 공통 형식이었다. `SourceProfile`은 각각 `../../../_work/tmp/w134-headless-20261031/profile-enough`, `.../profile-zero`, RunName은 위01/02/03이다. `TEMP`·`TMP`는 프로젝트 `_work/tmp`, `VERIFY_INPUT_ROUTE=GLFW_CALLBACK_INJECTION`을 사용했다.

```powershell
& work/local_original_session/companion-bridge/run_verify_fresh_capture.ps1 -RunName <위 RunName> -Steps companion_hotbar_probe -SourceProfile <해당 시험 사본> -Timeout 150 -CandidateBridge work/local_original_session/companion-bridge/own-login-bridge-companion-glfw-input.dll -CandidateSha256 00d646b40516a10a0f4978be156ce9dfb1f137c1f550eff34228e1762b05a67e
```

일반 시작에는 환경변수를 제거하거나 `0`으로 둔다. 등록 자체를 제외하는 기존 `SL_DISABLE_FEATURES=world_feature_companion_hotbar_probe`도 사용 가능하다. 런타임 중 환경변수 변경은 반영하지 않는다.

정상 경로로 만든 새 시험 저장 사본에서 기사 자신은 key0 미학습, 소유 법사는 key0 학습 상태가 필요하다. 이 입력이 없으면 `NO_UNLEARNED_MAGE_SPELLS` 또는 시나리오 fixture UNKNOWN으로 멈춘다. 임의 학습·초기화는 이 모듈이 하지 않는다. 초안은 key0/힐을 대상으로 MP>=4와 MP=0 두 시작 조건을 각각 확인하며 MP를 바꾸지 않는다. 기사도 레벨에 따라 힐을 배울 수 있으므로 key0 결과를 모든 법사 전용 마법의 직업 제한으로 일반화하지 않는다.

기존 bridge 입력 도우미를 재사용한다. 두 MP 조건은 시험 담당자가 별도 시작 저장 사본과 새 클라이언트로 순차 실행한다. 클라이언트 SpellInfo에만 주입한 정보는 서버 학습 저장과 별개다. 모드를 껐다는 사실만으로 이미 실행 중인 클라이언트의 UI가 복원되지는 않으므로 각 시험 뒤 기존 Quit/finally/FIRST close 경로로 종료하고 새 프로세스를 사용한다. 기존 4ED6 저장은 시험 사본에만 남겨야 한다.

## 적용한 시나리오·단계

사용자 실행 승인에 따라 초안을 공용 harness에 독립된 W134 블록으로 적용했다. 선택 이름은 `--steps companion_hotbar_probe`. `--steps`가 다르면 설치 함수가 즉시 반환한다. 기존 시나리오의 본문을 바꾸지 않았다. 실행01에서 원본 마법 아이콘 노드 탐색이 실패해, 좌표 규칙3번의 예외(노드가 없을 때 같은 창 크기의 캡처 측정)를 사용했다. 직접 검토한01 PNG의 힐 중심 `(2264,150)`을 재사용하고 기존 mage 시나리오와 같은 `scene_bounds=(899,380,1279,960)` 확인을 유지했다. 드래그는 추가하지 않았다.

1. 정상 로그인·캐릭터 선택·월드 진입 후 opt-in, 기사, key0 주입 세션, 시작 MP 조건 확인.
2. 기존 `UIOpenCommands.open_magic_window`로 마법창 열기 → 대기 → PNG 캡처.
3. 기존 `MemoryUi.spell_rows`에서 kind1/key0 노드 관측·기록. 노드와 PNG로 Q1 판정.
4. **드래그 생략.** `HEADLESS_COORDINATE_RULES.md:19`의 UI 노드 방법은 확인했으나 단축창 드래그 성공 방법이 지정되어 있지 않다. harness의 `paced_drag_events` 함수 존재만으로 검증된 단축창 드래그라고 주장하지 않는다. Q2·단축창 Q3는 UNKNOWN.
5. 클릭 전 PNG → 해당 마법 노드 중심에서 기존 private `left_double_click` → 직후 메시지 PNG.
6. 기존 UI callback으로 마법창 닫기 → 대상 클릭 전 PNG → 기존 `world_grid_to_capture`로 기사 자신 선택 → 대기 → 메시지 PNG.
7. broker의 시험 수신 이벤트·당시 MP를 `w134-result.json`에 기록. 화면 검토 전 Q1/Q4 자동 결과는 UNKNOWN으로 보존하고 이 문서의 실제 PNG 검토 표로 판정.
8. 별도 MP0 시작 사본·새 클라이언트에서 같은 단계 반복. MP0가 입력 전에 회복되면 MP0 결과로 인정하지 않는다.

좌표는 현재 노드의 `scene_bounds` → 기존 `node_point/node_to_capture`, 대상은 기존 `world_grid_to_capture`만 쓴다. 입력 어댑터의 `capture_to_client`에서 crop(+480,0)을 한 번만 적용한다. 근거는 `HEADLESS_COORDINATE_RULES.md:5`, `:10`, `:24`, harness `verify_ncg_waitonly.py:1331`(spell_rows), `:4237`(world grid), `:8255`(기존 마법 노드 입력). 새 투영·고정 아이콘 좌표·전역 입력 없음.

## 단위 시험 결과

```text
python -m unittest tools.local_original_session.world_companion_hotbar_probe_tests tools.local_original_session.world_decoupling_tests
27 tests: 27 OK (새 시험 8 + 등록 관련 19)

python -m unittest tools.local_original_session.world_companion_ats_heal_tests tools.local_original_session.world_companion_ats_spell_tests tools.local_original_session.world_companion_ats_window_tests
25 tests: 23 OK, 2 FAIL

python -m py_compile _work/tmp/w134_scenario_patch.py tools/local_original_session/world_feature_companion_hotbar_probe.py tools/local_original_session/world_companion_hotbar_probe_tests.py
OK (3 files)
```

ATS 실패는 `world_companion_ats_spell_tests.py:35`의 기대 80/실제96, `:66`의 key54 미매핑 기대/실제 버서커스 icon1570이다. 새 기능을 `FEATURE_MODULES`에서 제외하고 동일 25개를 다시 실행해도 같은 2개 실패가 재현됐다. 해당 파일·자료는 이번 범위에서 수정하지 않았다. 처음 사용한 unittest discover는 namespace 디렉터리의 importability 오류로 수집 실패했으며 위 명시 모듈 명령으로 실행했다. 이 결과는 실제 게임 PASS가 아니다.

## 실제 헤드리스 판정 기준

- Q1 YES: 기사 미학습/법사 학습·4E60 송신을 확인한 같은 실행에서 해당 key 노드와 실제 아이콘 PNG 확인. 정상 마법창/올바른 페이지가 확인돼도 없으면 그 조건에서 NO. 페이지·노드·캡처가 불명확하면 UNKNOWN.
- Q2: 현재 초안은 UNKNOWN. 후속 승인된 드래그 방법 확보 시 슬롯 kind1·해당 key와 후속 4ED6을 함께 확인. `settings-received`만으로 슬롯 내용·저장 완료를 입증하지 않는다.
- Q3: MP 조건별 실제 클릭 이후의 `cast-received(key,target,mp,at)`면 YES(수신만, 시전 성공 아님). 올바른 원본 입력·대상·충분한 관측 시간·해당 MP를 확인하고 요청이 없으면 그 조건에서 NO. 입력/대상/MP가 미확인이면 UNKNOWN. 초안은 무수신을 자동 NO로 바꾸지 않는다.
- Q4: 캡처에서 직업 제한을 명시한 문구가 보이면 YES. 실제 경로를 끝까지 관측하고 해당 문구가 없으면 그 경로에서 NO. MP 부족 문구는 직업 차단과 구분한다. 요청 부재만 있거나 문구를 읽을 수 없으면 UNKNOWN.
- MP 충분/0, 마법창/단축창, key0/다른 법사 마법의 결론을 합치지 않는다. 송신 반환·단위 시험·노드 메모리만으로 원본 화면/입력 전체 성공을 주장하지 않는다.


## f6=1 후속 시험 (2026-10-31, 사용자 추가 승인)

**결론: 기본 MP10인 홀리 웨폰(key7)이 기사 MP2와 MP1에서 4EE6을 보냈다. 툴팁은 MP10을 그대로 표시했다. 정확한 MP0의 요청 전송은 UNKNOWN이다.** MP0 구간에서 자연 회복으로 대상 클릭 전에1이 되었으므로, 자동 결과의 `case=zero, Q3_spell=YES`를 MP0 성공으로 해석하지 않는다.

| 항목 | 판정 | 실제 근거·캡처 |
|---|---|---|
| f6=1, 기사 MP2 < 마법 기본 MP10에서 4EE6 | **예** | `key=7,target=1,mp=2,cast=false` 1건. [low 결과 JSON](../runs/w134-f6-both-20261031-02b/w134-result-low.json), [입력 직전 MP2](../runs/w134-f6-both-20261031-02b/w134-input-before-self-low.json), [선택·툴팁 PNG](../runs/w134-f6-both-20261031-02b/w134-message-after-spell-click.png), [대상 클릭 후 PNG](../runs/w134-f6-both-20261031-02b/w134-message-after-target.png). |
| f6=1, 정확한 MP0에서 4EE6 | **UNKNOWN** | 마법 선택 직전은 MP0이나 대상 클릭 직전·수신 때는 MP1이었다. [선택 직전 MP0](../runs/w134-f6-both-20261031-02b/w134-input-before-spell-zero.json), [대상 직전 MP1](../runs/w134-f6-both-20261031-02b/w134-input-before-self-zero.json), [해당 구간 결과](../runs/w134-f6-both-20261031-02b/w134-result-zero.json). |
| f6=1, 기사 MP1에서 4EE6 (부수 관측) | **예** | 위 MP0 시도 중 MP1로 자연 회복된 뒤 `key=7,target=1,mp=1,cast=false` 수신1건. MP1은 기본 MP10보다 작다. |
| f6=1이 툴팁 MP 소모 표시를1로 바꾸는가 | **아니오 — key7** | 두 구간 모두 툴팁 `홀리 웨폰`, `MP/HP[10/0]` 표시. [MP2 툴팁 PNG](../runs/w134-f6-both-20261031-02b/w134-message-after-spell-click.png), [선택 때 MP0 툴팁 PNG](../runs/w134-f6-both-20261031-02b/zero-w134-message-after-spell-click.png). |
| 화면 메시지 | **MP2: 거절 문구 없음 / 정확한 MP0 대상 클릭: UNKNOWN** | low 대상 후에는 직업·MP 부족 문구 없음. zero 선택 캡처는 MP0/41, 대상 후 캡처는 MP1/41이며 거절 문구 없음. [선택 때 MP0 PNG](../runs/w134-f6-both-20261031-02b/zero-w134-message-after-spell-click.png), [대상 때 MP1 PNG](../runs/w134-f6-both-20261031-02b/zero-w134-message-after-target.png). |

원 PNG에서 툴팁·MP HUD·채팅 영역을 잘라 만든 `_work/tmp/w134-f6-20261031/low-review.png`, `zero-review.png`(각1100×900)를 직접 열어 위 표시를 확인했다. 원본 PNG는 각 실행 폴더에 그대로 보존했다. f6=1이 **기본 비용보다 작은 양의 MP에서 요청 전송을 허용한 것**은 확인했지만, 무MP 명령이나 동료 MP 비용 처리·시전 연결은 구현/검증하지 않았다. 단축창은 계속 UNKNOWN이다.

### 변경·활성화

- `world_feature_companion_hotbar_probe.py:19`: `SL_EXPERIMENT_COMPANION_HOTBAR=1`과 `SL_EXPERIMENT_COMPANION_HOTBAR_F6=1`이 모두 있어야 f6 override 활성화. 기본은 None.
- 같은 파일 `:54`: 시험 upsert의 각 SpellInfo에만 protobuf f6=1 추가. 옵션이 꺼져 있으면 기존 바이트(f1/key, f2/true) 그대로. `:60`의 upsert 이벤트에 실제 `spellinfo_f6:1` 기록. 실제 플레이어·동료 마법 비용 처리·학습 저장은 변경하지 않았다.
- `world_companion_hotbar_probe_tests.py:63`: 두 opt-in의 조합, 전송 wire f6=1/미지정, 학습 불변 확인. 기존8개+새1개, 등록 관련19개와 합계 **28/28 통과**. 명령: `python -m unittest tools.local_original_session.world_companion_hotbar_probe_tests tools.local_original_session.world_decoupling_tests`. probe·harness 문법 검사 통과.
- `verify_ncg_waitonly.py:8634`: 선택 시나리오의 `W134_SPELL_KEY` 옵션. `:8635`의 `W134_BOTH_MP=1`이면 동일 시험 세션에서 low와 zero 구간을 분리하고 PNG/입력/결과 이름을 다르게 보존. `:8743`의 시험 전용 `w134_zero`는 현재 기사 MP만0으로 설정하고 기존 world runtime·정상 status_frame/송신 경로를 사용한다. MP를 고정하거나 자연 회복을 막지 않았기 때문에 이번에는 대상 클릭 전에1로 회복됐다. 기존 기본 key0 시나리오는 이 옵션들이 없으면 원래 단계대로다.

실제 완료 실행 환경은 `SL_EXPERIMENT_COMPANION_HOTBAR=1`, `SL_EXPERIMENT_COMPANION_HOTBAR_F6=1`, `W134_SPELL_KEY=7`, `W134_MP_CASE=low`, `W134_BOTH_MP=1`, `VERIFY_INPUT_ROUTE=GLFW_CALLBACK_INJECTION`, TEMP/TMP=`_work/tmp`. 시작 사본 `_work/tmp/w134-f6-20261031/profile-low`는 이전 시작 사본의 기사 vitals.mp만2로 설정했다. 최대MP41·학습·UID·인벤토리·동료 저장은 보존했다. 별도 profile-zero도 준비했으나 게임 실행에는 쓰지 않았다.

### 실제 실행·실패·한도

| 실행·시도 | 결과 |
|---|---|
| [실제 게임1: w134-f6-low-20261031-01](../runs/w134-f6-low-20261031-01/verify-shots.json) | 최초 대상은 익스트라 힐 key18/기본 MP11. MP2·법사38개 upsert·f6=1 송신은 확인. 페이지3 버튼 `UI_NODE_NOT_UNIQUE:Root.NomalSpellPanel.Page_3.Bt_3:Bt_3`로 클릭 전 REFUSED, 나머지 SKIPPED. [첫 페이지 PNG](../runs/w134-f6-low-20261031-01/w134-before-page3.png) 보존. 익스트라 힐 송신/툴팁 결론은 UNKNOWN. |
| 게임을 시작하지 않은 사전조건 거절 | 다른 `w133-companion-paralyze-20261031-a` 게임·리스너가 있어 먼저 대기했다. 해당 게임 종료 직후에도 DLL이 후보 해시인 상태라 `w134-f6-both-20261031-02` wrapper가 **BRIDGE_PIN_CHANGED**로 Python/게임 기동 전에 거절했다. 기준 DLL로 복구했고 부분 시험 사본은 보존했다. 이 시도에서 새 LC를 시작하거나 기존 LC를 종료하지 않았다. |
| [실제 게임2: w134-f6-both-20261031-02b](../runs/w134-f6-both-20261031-02b/verify-shots.json) | 기존 캡처에서 확인한 첫 페이지 홀리 웨폰 key7/기본 MP10으로 변경. 검증된 같은 창 크기의 `(2684,290)` 좌표 사용. MP2→시험용 MP0 설정→자연 회복 MP1. 실제 4EE6은 MP2/MP1 각1건. 두 구간 tooltip·HUD·메시지 PNG 합계10개. |

실제 게임 실행은 **2회**다. 중간에 끊지 않았고 추가 게임은 실행하지 않았다. 두 실행 모두 wrapper exit0·LC_LEFT0, DLL baseline `1d1f60a03144f0214bee56c4a875d4444d51811649135a1eaab82ec2e2899f75` 확인. 각 실행 직전 LC·12000/14030 listener 없음 확인. 마지막에도 없음. 기존 종료 결과는 둘 다 `FORCED_CLEANUP`, `normal_exit_verified=false`, `game_logout_protocol=UNVERIFIED`다. 정상 종료 PASS로 표시하지 않는다. 후보 DLL은 이전과 같은 `00d646b40516a10a0f4978be156ce9dfb1f137c1f550eff34228e1762b05a67e`; 지정 runner의 일시 배치/원복만 수행했다.

원본 자동 결과·실패·부분 사본은 수정하지 않았다. `case=zero`는 **시도 이름**이며 수신 시 MP0을 뜻하지 않는다. probe 해시는 `79a970308da8108b54cf3ea0795ef3e168339066253d927f275437353a945413`. 실제 게임1 준비 harness 해시는 `af8e3441e32cbf8d65d2adc2d0be4b59af707bcd2d710753cd966b041916c7b4`, 게임2 준비 때는 `cfcfde4ec04d3c97f9e3f0cce17c03f8c78e040e3586d14c1ed1bb6423e388cd`였다. 대기 중 타 작업의 공용 harness 변경이 있었고 실행 직후 현재 해시는 `436a251980bc3e87c71c49370046d050e3efdca6b034e202ee2c55bf0c45415d`로 확인됐다. 따라서 마지막 전체 파일 해시를 실행 전 고정 해시라고 소급하지 않는다. 금지된 magic/companion/monster 파일·사용자 저장·DLL 내용·커밋은 수정하지 않았다.

남은 최소 관측은 f6=1 상태에서 **실제 대상 클릭 시에도 MP0**인 요청/메시지다. 이번 한도에서는 UNKNOWN으로 마감한다.
