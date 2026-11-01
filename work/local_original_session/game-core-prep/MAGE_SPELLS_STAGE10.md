# 플레이어 법사 10단계 — 미티어 스트라이크·어드밴스 스피릿

2026-10-31. 고정 클라이언트 **26.09.29.2001**. 기존 8·9단계의 학습·소비·범위 피해·시전 표시·마법 저장·HUD 경로를 확장했다. 단위 시험, 패킷 관측, 원본 화면 판정을 구별한다. 이번 요청의 두 종만 추가했으며 이전 단계의 미완 계약을 전체 완료로 바꾸지 않는다.

## 출처와 값

- **O73/O78**: `tools/local_original_session/data/official/spells.json`의 `official_id=73/78`, 실제 보관 원문 `work/official_data_refresh_20261028/raw/spell/73.json`, `78.json`. 각 행 `source_snapshot.official_source`에 URL·수집 시각·SHA256·list 원문 출처를 보존했다. 새 HTTP 수집을 주장하지 않는다.
- **C73/C78**: `work/source_game_data/native-dump-v1.jsonl:2285/2286`, 기존 `spell-ui-joins.json`, `spell-records.json`. 책은 공식 textbook 이름/ID와 native item의 f41을 대조했다. 책225는 native1137, 책1491은 native1510이다.
- **L**: `D:/SingleLineageRef/l1j-en-classic`, 기존 고정 HEAD `103e6f6c9dd83545959d8e87d3f59f8de1f40ef0`. 명시 이름·10단계가 일치하는 `db/l1jdb_m10.sql:35694` MeteorStrike, `:35699` AdvanceSpirit. 수치·재사용·표시 recipe는 **LOCAL 참고 정책**이며 공식 > 고정 클라이언트 > L1J 순서다.

| 키 / 이름 | 책 [O,C] | 학습 [O] | MP / HP / 재료 [O,list,C] | 대상·지속 [O] | LOCAL 재사용 [L] |
|---|---|---|---|---|---|
| 73 미티어 스트라이크 | 225 | 법사40 | 60 / 0 / 없음 | 10칸 대상과 주변3칸 적, 순간 | 1.5초 |
| 78 어드밴스 스피릿 | 1491 | 법사40 | 20 / 0 / 없음 | 술자, 1,200초 | 1초(SQL0 → 기존 기본값) |

학습 장소와 성향 임계값은 **UNKNOWN**이며 **LOCAL 추가 장소/성향 제한 없음**이다. 실제 `0960` 책 handler가 소유·수량·직업·레벨·중복을 판정하고 기존 kit CAS/learning intent/magic save/`4E60`을 사용한다. 성공1회에 책1권, 중복·조건 불충족은 무소비다. MP는 공식 기본량을 실제 소비하는 기존 LOCAL 정책이며 동적 MP 절감식은 UNKNOWN이다.

| 마법 | 효과 수치와 정책 / 출처 | 시전 action / gfx [L,고정 자원] | HUD [C] | 화면 확인 | 캡처 경로 |
|---|---|---|---|---|---|
| 미티어 스트라이크 | 기존 라이트닝 스톰과 같은 대상 중심 범위 경로. 공식 반경3칸, 현재 가시 일반 NPC만. LOCAL `8d15+50`, 불2, 기존 INT/SP/속성/MR 계산 [L35694, 기존 L1Magic 참고식]. 실제 HP·처치·보상 소유자·EntityRef 유지 | 18 / 762 | 순간 효과: 가짜 버프 아이콘 없음 | **부분: 화면 미확인**. 학습·범위 피해·실제 소비·표시 패킷 단위 통과. 1회 캡처 밖 입력 거절, 2·3회 대상 클릭은 전달됐으나 native 시전 요청/소비/효과 없음. 두 캡처에서 능력치 창이 대상 지점을 가림. 3회 한도 종료 | [1회 대상 전](../runs/mage-stage10-20261031-01/mage-73-target-before.png), [3회 대상 전](../runs/mage-stage10-20261031-03/mage-73-target-before.png), [3회 후](../runs/mage-stage10-20261031-03/mage-73-after.png) |
| 어드밴스 스피릿 | 공식 최대 HP/MP 각각20% 증가. LOCAL 성장 기본 최대치 각각 `//5`를 더함 [L1SkillUse.java:2854~2860]. 장비 최대치에는 곱하지 않음, 현재 HP/MP를 채우지 않음. 재시전은 시간 갱신만, 보너스 중첩 없음 | 19 / 3935 | K1607 / tooltip12610 [native2286 f3/f7], 실제 남은 초 | **확인**. 보라 광채·HUD 화살표·최대1200/1800·남은19분54초. 실제 MP20 소비 | [효과](../runs/mage-stage10-20261031-01/mage-78-immediate.png), [상한·툴팁](../runs/mage-stage10-20261031-01/mage-78-tooltip.png) |

## 연결과 수명

미티어는 기존 `area_damage` 소비·현재 가시 대상·거리·LOS·Counter Magic·실제 피해·사망 경로를 재사용한다. 술자 중심으로 바꾸지 않는다. `4E31`/`4ED8`은 실험 표시 OFF에서도 두 마법에 송신한다. 고정 자원의 sprite/파일 alias·SPX 존재는 `spell_display.json`에 보존했으며 파일 존재를 화면 성공으로 바꾸지 않는다.

어드밴스는 기존 `MagicState.buffs`에 저장한다. 코어의 기존 기본/유효 최대치 분리와 상한 정리를 사용하고 등록형 `resource_bonuses` 훅으로 기본 최대치의20%만 기여한다. 기존 기본 최대치 갱신 로직은 `resource_bases()`로 이동해 성장·보상에서 두 최대치가 바뀐 같은 갱신에 새 보너스를 계산한다. 장비 보너스·다른 버프를 두 번 넣지 않는다.

초기 SelfInfo의 기본 상한으로 현재 HP/MP가 먼저 잘리는 것을 막기 위해, 기존 realm `status_fields` 훅에서 저장된 어드밴스가 있을 때 같은 magic owner를 먼저 복원한다. 실제 vitals owner의 현재값을 유효 상한으로 투영하며 별도 저장 형식·자원 원장을 만들지 않는다. 기존 after_enter가 남은 시간/HUD를 송신하고, 텔레포트 replay는 deadline을 바꾸지 않는다. 오프라인 경과를 차감하고 만료/사망 때 상한을 낮추고 현재값을 clamp한다.

어드밴스의 플레이어 Cancellation 예외는 이름 대응 L1J `UNCANCELABLE:174~176`의 **LOCAL** 정책이다. 새 행의 `cancel_exempt`만 기존 예외에 합치며 이전 마법의 예외 목록을 바꾸지 않았다. 기존 별도 monster buff-only cancel 계약을 전체 원본 규칙으로 주장하지 않는다.

데이터 형식은 기존과 같다. `player_spells.json`에는 `classic_key/magic_stage/mp_cost/hp_cost/materials/target/range_tiles/duration_seconds/formula/source_snapshot/player_policy`, `stage_support.stages.10`을 추가했다. 총 카탈로그110행, 단계 집계69행/지원66/기존 미지원3이다. 두 책의 기존 metadata·가격·UID 체계는 유지해 `spellbooks.json`으로 옮겼다. 동료 AI·ATS의 허용 마법 정책과 classes/DLL/단축창 모듈은 수정하지 않았다.

## 시험과 실행

최종 단위 시험 **33모듈·522개: 통과521, 실패0, 오류0, skip1**, 러너240.245초. 로그 `_work/tmp/mage-stage10-unit-final-v3.log`. 신규17개가 포함된다. 코어 최대치 변경에 직접 관련된 `equipment_stats_tests`8개와 신규17개를 묶은 추가25개도 통과했다: `_work/tmp/mage-stage10-core-final.log`.

첫 실행은 동시 포트 점유로 기존 loopback2개와 책 집계 기대값1개가 실패했다(`mage-stage10-unit-first.log`). 집계와 테스트 Context의 기본 fold API를 반영하고 기존 격리 포트 설정으로 재실행했다. 중간 로그의 실행 중 소스 변경/fixture 오류를 최종 성공으로 합산하지 않는다. 위 최종 실행은 구현을 고정한 새 프로세스의 결과다.

```powershell
$env:TEMP=(Resolve-Path _work/tmp).Path
$env:TMP=$env:TEMP
$env:SL_TEST_PORT_BASE='22000'
python _work/tmp/run_stage10_unit.py _work/tmp/mage-stage10-unit-final-v3.log
```

러너는 `_work/tmp/run_stage89_unit.py`와 같은 기존32모듈 목록에 신규 `world_magic_stage10_tests`만 추가한다. launcher/manual_move_commands는 제외한다. hunt_bot을 실행하는 기존1개 skip을 유지한다. 22000/24030은 기존 격리 단위 시험 설정이며 헤드리스의12000/14030과 구분한다.

헤드리스는 구현·단위 시험 이후 `mage_stage10`, 기존 owned non-input desktop/Job와 GLFW callback injection만 사용한다. 시작 전 LC/LC.guard·12000/14030이 비어 있어야 하며 점유 시2분 간격 최대20분 대기한다. 좌표는 기존 UI node·현재 캡처 측정·원 격자 함수만 사용한다. 최대3회, 동일 원인2회 실패 시 해당 화면은 미확인으로 남긴다.

시험 시작 사본 `_work/tmp/mage-stage10-20261031/profile-stage10`은 기존7단계 시험 사본을 복사해 UID1을 LV60/기본HP1000/MP1500·현재HP1000/MP1500·시험 능력치로 준비했다. 사용자 저장의 레벨/가방에 의존하지 않는다. 두 실제 책은 기존 UID allocator·kit append CAS로 추가했다. 사전 학습 초기값을 native 책 클릭 학습 증거로 부르지 않는다. NPC 수치·위치·확률은 강제하지 않는다.

```powershell
work/local_original_session/companion-bridge/run_verify_fresh_capture.ps1 `
  -RunName mage-stage10-20261031-01 -Steps mage_stage10 `
  -SourceProfile ../../../_work/tmp/mage-stage10-20261031/profile-stage10 -Timeout 200 `
  -CandidateBridge work/local_original_session/companion-bridge/own-login-bridge-companion-glfw-input.dll `
  -CandidateSha256 00d646b40516a10a0f4978be156ce9dfb1f137c1f550eff34228e1762b05a67e
```

환경 `VERIFY_INPUT_ROUTE=GLFW_CALLBACK_INJECTION`, TEMP/TMP=`_work/tmp`. 헤드리스에서는 `SL_TEST_PORT_BASE`와 `SL_PLAYER_MAGIC_BUFF_SECONDS`를 해제해 실제12000/14030과 공식1,200초를 쓴다. 매 실행 후 게임 폴더 DLL 기준 해시 `1d1f60a03144f0214bee56c4a875d4444d51811649135a1eaab82ec2e2899f75`를 확인하고 필요 시 지정 원본으로 복원한다.

### 헤드리스 최종 결과 — 3회/한도3회

| 실행 폴더 | 실제 판정 / 캡처 |
|---|---|
| [mage-stage10-20261031-01](../runs/mage-stage10-20261031-01/result.json) | LC/리스너0에서 시작. 현재 page10 캡처로73=(2264,150),78=(2404,150)을 직접 측정하고 기존 동일 창 bounds/capture_to_client 경로 사용. 어드밴스 native 시전 MP1500→1480, 상한1000/1500→1200/1800, 보라 광채·HUD·19분54초 확인. 미티어 대상은(32577,32857), 술자(32570,32848)로 기존 격자식 결과가 오른쪽 PNG 경계 밖: `INPUT_CAPTURE_POINT_OUTSIDE_PNG`, 요청/비용 없음 |
| [mage-stage10-20261031-02](../runs/mage-stage10-20261031-02/result.json) | 처음 LC0/리스너2여서2분 대기 후 LC/리스너0에서 시작. 실제1회 저장의 magic/vitals를 그대로 복사, 시험 시작 위치만 기존 지형이 허용한(32576,32856)으로 변경. 정상 로그인·월드 진입에서 HP1063/상한1200, MP1483/상한1800 유지. [재접속 툴팁15분28초](../runs/mage-stage10-20261031-02/mage-restored-buff-0-tooltip.png)로 재부여/20분 리셋 없음. 미티어 대상(-3,-3)의 입력은 POSTED지만 능력치 창 경계에 가려졌고 시전 요청/MP60 소비/이펙트 없음 |
| [mage-stage10-20261031-03](../runs/mage-stage10-20261031-03/result.json) | LC/리스너0에서 시작. 실제2회 저장을 보존해 복사하고 시작 위치만 기존 지형이 허용한(32571,32851)로 변경. 가까운 오른쪽 현재 NPC를 우선했으나 해당 후보가 없어 기존 가까운 대상으로 돌아감. 대상(32568,32845), 입력 capture(630,660)은 능력치 창 뒤. POSTED 이후 시전 요청/소비/효과 없음. 같은 native 대상 입력 막힘2회, 전체3회에서 종료 |

모두 wrapper의 원 finally를 기다려 **FORCED_CLEANUP**, `normal_exit_verified=false`, logout `UNVERIFIED`로 끝났다. 제품 수명은 각각97.078/42.157/40.297초다. 매 실행 후 LC/12000·14030 리스너0, 게임 DLL은 모두 위 기준 해시, 원 Capture11개 복원을 확인했다. 다른 프로세스는 종료하지 않았다. 실제 결과·후보 입력·정상/강제 종료를 합쳐 PASS로 확대하지 않는다.

어드밴스는 실제1회 시전 저장을2회 정상 로그인에서 복구했다. 저장 현재HP1063이 기본1000보다 높아도 손실 없이 유지됐으며 실제 오프라인 경과가 반영됐다. 두 재접속 시험의 초기 위치 변경은 **시험 fixture**이며 native 텔레포트 증거가 아니다. 텔레포트 뒤 deadline/HUD/상한 유지는 단위 확인이고 native 텔레포트 화면은 이번3회에서 미확인이다.

헤드리스의 사전 학습 값을 native 책 클릭 학습으로 주장하지 않는다. 두 책의 학습 가능/1회 소비/CAS/저장/4E60/중복 무소비는 실제 handler 단위 검증이다. 미티어의 표시 recipe/패킷 존재를 native 운석 화면 성공으로 표시하지 않는다. 다음 화면 관측에 필요한 입력은 능력치 창을 닫는 검증된 원 UI node 경로 또는 그 창에 가리지 않는 현재 NPC 대상이며, 새 좌표식·guard 우회·추가 실행으로 대체하지 않았다.

임시 실행/측정/검토 자료: `_work/tmp/mage-stage10-20261031/`. 원 PNG를 줄인 `run01-review.jpg`, `run02-review.jpg`, `run03-review.jpg`, 어드밴스 툴팁/상한/효과 crop을 이곳에 보존했다. 공식 결과는 위 `runs/`의 원 PNG/`verify-shots.json`/`result.json`이다.

## UNKNOWN

- 공식 피해식·서버 재사용·동적 MP 절감식. 피해·재사용은 위의 출처 있는 LOCAL 정책이다.
- 어드밴스의 실제 Classic 정수 반올림·장비 최대치 포함 방식·Cancellation 예외. 현재 L1J 기본 최대치/5·UNCANCELABLE을 LOCAL로 채택했다.
- 학습 장소·성향 임계값. 현재 LOCAL 제한 없음.
- 미티어 PvP·전체 적대/혈맹/안전지역 정책. 현재 일반 NPC 범위만 구현했다.
- 미티어 native 대상 클릭→시전 요청과 실제 운석 이펙트·피해 화면은 미확인. 세 번의 실행에서 비용을 강제 소비하거나 성공으로 만들지 않았다.
- 어드밴스 native 텔레포트 뒤 유지/만료 화면, 두 책의 native 클릭 학습 화면은 미확인. 해당 저장·이동·만료·학습 동작은 단위 검증 범위다.
- 화면 확인은 아래 실제 실행 결과의 범위만 인정하며 전체 픽셀/입력/프레임 동등성을 주장하지 않는다.

## 변경 파일·줄

| 파일:줄 | 변경 요지 |
|---|---|
| [world_magic.py:21](../../../tools/local_original_session/world_magic.py#L21) | 기존 timed buff 종류에 advance_spirit 추가 |
| [world_feature_magic.py:41](../../../tools/local_original_session/world_feature_magic.py#L41) | HUD1607, 새 Cancellation 예외, 최대치 기여 훅, 실험 OFF 시에도 두 시전 표시, 초기 realm projection 등록 |
| [world_core_stats.py:45](../../../tools/local_original_session/world_core_stats.py#L45) | 기존 기본 최대치 갱신 로직 재사용 및 유효 상한 투영 전 등록형 resource_bonuses 소비 |
| [world_magic_stage10.py:9](../../../tools/local_original_session/world_magic_stage10.py#L9) | 공식20%의 LOCAL 기본치/5, 저장 상태를 초기 상한 정리 전에 복원 |
| [player_spells.json:153](../../../tools/local_original_session/data/m3/player_spells.json#L153) | stage_support10. 신규73행29967, 78행30291, 값별 출처·LOCAL·UNKNOWN |
| [spellbooks.json:15293](../../../tools/local_original_session/data/m1/items_ext/spellbooks.json#L15293) | 책225/1491(15562줄) metadata 보존·학습 연결 |
| [drops_misc.json:1](../../../tools/local_original_session/data/m1/items_ext/drops_misc.json#L1), [misc.json:1](../../../tools/local_original_session/data/m1/items_ext/misc.json#L1) | 옮긴 두 책의 기존 중복 정의 제거 |
| [spell_display.json:4778](../../../tools/local_original_session/data/m1/spell_display.json#L4778) | 이름 대응73/78 action/gfx 및 고정 sprite/SPX 근거 |
| [buff_descriptions.json:121](../../../tools/local_original_session/data/m1/buff_descriptions.json#L121) | native78의 tooltip12610 |
| [world_magic_stage10_tests.py:15](../../../tools/local_original_session/world_magic_stage10_tests.py#L15) | 신규17개: 학습·소비·피해·거절·표시·상한·저장·초기 SelfInfo·이동·만료·사망 |
| [world_magic_tests.py:32](../../../tools/local_original_session/world_magic_tests.py#L32), [spellbook_learning_tests.py:61](../../../tools/local_original_session/spellbook_learning_tests.py#L61), [world_companion_ats_spell_tests.py:35](../../../tools/local_original_session/world_companion_ats_spell_tests.py#L35) | 새 데이터의 지원 키/학습 집계/카탈로그110행 기대값만 반영 |
| [world_companion_resource_tests.py:253](../../../tools/local_original_session/world_companion_resource_tests.py#L253) | 가짜 Context에 기존 fold API의 기본 동작 추가, 게임 기대값 유지 |
| [verify_ncg_waitonly.py:8145](../companion-bridge/verify_ncg_waitonly.py#L8145) | 기존 mage 시나리오에10단계·상한 관측·78 툴팁 추가. 기존 UI/격자 변환·입력 guard 유지 |

사용자 저장·manual-user-play·classes·ATS/단축창 모듈·DLL 소스는 수정하지 않았고 커밋하지 않았다. DLL은 실행 wrapper의 후보 배치/지정 원본 복원만 사용한다. 임시 러너·준비 스크립트·실행 로그·측정은 `_work/tmp/`에 보존한다.
