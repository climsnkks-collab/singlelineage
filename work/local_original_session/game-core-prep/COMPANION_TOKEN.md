# 동료 소환 아이템

동료 소환에는 원본 **신성한 유니콘의 뿔** 자원을 사용한다. 동료 소환·불러오기 효과와 영구 사용은 이 서버의 LOCAL 정책이다. 원본 아이템의 공식 효과를 재현했다고 주장하지 않는다.

## 선정 근거

| 항목 | 값·출처 |
|---|---|
| 클라이언트 ID | **2070**, 이름 토큰 `$4349` |
| 원본 이름 | **신성한 유니콘의 뿔** |
| 인벤토리 아이콘 | **2181**, CommonItemInfo **f5** |
| 정리용 분류 | `etc` — 카탈로그의 local_policy 분류 |
| raw_kind | `f4=0`, `f45/f17/f48` 부재(null). 부재를 0으로 해석하지 않는다. |
| 카탈로그 | `tools/local_original_session/data/catalog/items_all.json` 787행 |
| 원문 | `work/source_game_data/native-dump-v1.jsonl` **1521행** (카탈로그 `reference_paths.native-dump`) |

뿔이라는 이름은 부르는 도구를 연상시킬 수 있어 단검보다 용도를 구별하기 쉽다. 원본 이름 자체가 ‘뿔피리’인 것은 아니며, 아이콘을 실제 화면에서 확인하지 않았다. 같은 목적의 가장 직접적인 이름인 펫 호루라기343은 이미 m2/m4/m5 상점 판매표와 `world_shop`의 판매 규칙에 연결되어 제외했다. 선택 당시 2070은 m1~m6·companion 런타임 JSON 및 제품 Python 코드에서 사용 참조가 없었다. `data/official/monsters.json`의 수집 참고 드롭에는 존재하므로 공식 게임에서 미사용인 아이템이라고 주장하지 않는다.

ID·이름·아이콘·raw_kind 네 항목은 **원본 클라이언트 자료 4/4**다. 새 효과·비소모·저장 이전은 **LOCAL 정책**이며 공식/L1J 소환 규칙을 추가하지 않는다. L1J41352의 material/normal 대응은 후보에 불과하고 원본 악기·소환 의미의 근거로 채택하지 않았다.

사용 요청은 기존 [raw0 분석](../../local_server_rea_20261016/run150_local_book_use_policy/worker/findings.md)의 정상 분기를 재사용한다. wire ItemInfo에 `f5=0`을 명시 공급하면 원 Entity+50의 raw0 분기로 연결되고, CS0960 child는 `{1:1,15:0,16:0}`, f17 부재다. 2070에 이 사용 종류를 공급하는 것은 LOCAL 연결이며, 카탈로그 f4=0만으로 실제 더블클릭 송신을 확인한 것은 아니다.

## 사용·저장 계약

- 동료가 없으면 소환하고, 살아 있는 동료가 있으면 같은 동료를 주인 옆의 유효 타일로 불러온다. 아이템 사용으로 해산하지 않는다.
- 죽은 동료는 소환 아이템으로 이동·부활시키지 않는다. 부활 주문서 사용 안내만 보낸다.
- 사용 수량은 줄지 않는다. 기존 부활 주문서의 대상 지정·소비 경로는 유지한다.
- 옛 토큰은 **template1이며 f18이 정확히 ‘동료 소환/해산’인 행**만 이전한다. 다른 단검이나 이름만 같은 타 템플릿은 보존한다. 새 아이템이 이미 있으면 추가 지급하지 않는다.
- 기존 inventory 저장의 같은 UID 템플릿 변경 금지를 따라 옛 토큰 제거와 새 UID 추가를 기존 저장 API로 처리한다. 사용자 저장을 일괄 직접 수정하지 않고 정상 접속의 키트 처리에서 이전한다.

불러오기는 같은 UID·수명과 HP/MP·성장·저장 명령·행동 대기시간을 유지한다. 이미 보던 클라이언트에도 위치가 갱신되도록 기존 제거/출현 프레임을 보낸다. 장착된 옛 토큰은 기존 저장 트랜잭션을 재사용해 인벤토리와 장비 참조를 함께 이전한다.

사망 안내는 [CHAT_EVIDENCE](CHAT_EVIDENCE.md)의 `4EEA f1=12066`, 반복 f2 본문1개 후보를 재사용한다. 원문 문자열 `SYSTEM_GM/{}` 및 formatter 연결에 근거한 SOURCE_ONLY 표시 후보다. 한국어 수신·자원 로드·실제 화면 표시를 확인한 것으로 확대하지 않는다.

## 검증 범위

원본 클라이언트를 실행하거나 화면을 캡처하지 않았다. 소켓·단위 시험 결과는 서버 요청 처리와 저장 계약 범위이며, 실제 표시·더블클릭·아이콘의 직관성을 입증하지 않는다.

원본으로 확인할 것: 가방에서 뿔 이름/아이콘, 더블클릭의 CS0960 송신, 재사용 때 동료가 주인 옆에 나타나는 모습, 사망 시 안내 표시와 시체 위치 유지. 서버 ItemInfo의 사용 종류 f5와 카탈로그 CommonItemInfo의 아이콘 f5는 서로 다른 메시지 필드다.

현행 `work/local_original_session/manual-play/start-manual-play.ps1`의 핀 대상에는 이번 변경 파일이 없어 핀·BOM을 수정하지 않는다.

소켓 검증 중 발견한 초기화 순서 오류는 저장 이전 준비를 `runtime_started`로 옮겨 수정했다. 안내 프레임은 수신됐으나 봇 디코더에 없던 `4EEA`도 로컬 목록에 추가했다. 이후 반복 사망 단계의 이동 정체를 확인해 테스트봇은 현재 접근 가능한 NPC를 고르고 한 걸음마다 수신 위치를 다시 선택하게 했다. 당시 정확한 동적 장애물은 기록이 없어 미확정이다. 기존 15초 정체·전체 시간 제한·실제 패킷·사망 판정은 유지했다. 이전 실패 원문과 저장 사본은 아래 기존 runs 경로에 보존한다.

- 시작 순서 실패: `runs/hunt-companion-o0bxeylw/summary.json`
- 안내 디코더 실패: `runs/hunt-companion-wsev3tlb/summary.json`
- 반복 사망 중 이동 정체: `runs/hunt-companion-scmbc_n7/summary.json`

경로 기준은 `work/local_original_session/`이다.

최종 검증(2026-10-28): 위 단위 묶음 **97 tests OK, skipped=1**(중복 소켓 opt-in 제외), 원문 `runs/companion-native-token-units-20261028-000038.stderr.log`. 옛 저장 이전·중복 방지·장착 참조 정리 시험을 포함한다. 이후 변경은 소켓 봇의 디코딩·목표 선택뿐이어서 같은 제품/단위 성공을 재사용했다.

`SL_TEST_PORT_BASE=24000`의 `hunt_bot_companion --scenario all`은 **SUCCESS, 47/47 checks SUCCESS**다. [최종 summary](../runs/hunt-companion-u84hpld_/summary.json), 원문 `runs/companion-native-token-all-20261028-000815.stdout.log`에 보존했다. 동일 UID 불러오기/비소모, 최초·반복 사망 때 각각 안내12066 수신1건과 시체 보존, 부활 주문서·저장·재접속을 확인했다. `cleanup_complete=true`, 5개 epoch 모두 `failure_code=null`, `close_code=SESSION_STOPPED`, 정리 완료, 물리 24000/26030 listener 0이다. 범위는 정상 FIRST/login/선택 뒤 실제 소켓 디코더·라우터를 거친 로컬 서버 동작이며 원본 입력·화면의 성공이 아니다.

실행 명령(프로젝트 루트, 지정 Python):

```powershell
$taskPython = 'C:/Users/Chansol/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$env:SL_TEST_PORT_BASE = '24000'
& $taskPython -X utf8 -B -m unittest tools.local_original_session.world_companion_tests tools.local_original_session.world_companion_movement_tests tools.local_original_session.world_companion_equipment_tests tools.local_original_session.world_companion_magic_tests tools.local_original_session.world_companion_revive_tests tools.local_original_session.world_companion_integration_tests tools.local_original_session.companion_ai_tests
& $taskPython -X utf8 -B -m tools.local_original_session.hunt_bot_companion --scenario all
```
