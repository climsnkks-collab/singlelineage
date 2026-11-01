# 보스 등장 주기 — LOCAL L1J 참고 정책

이 기능은 고정 원본 클라이언트의 서버 규칙을 복원했다고 주장하지 않는다. 현재 선택된 MonsterDef의 클라이언트 신원·전투/보상 정책을 유지하고, L1J의 보스 위치·수·파티·등장 창을 별도 선택 기능으로 소비한다. 기존 일반 몹 JSON·밀도·필드 인구 수는 수정하지 않는다.

**기본 등록은 아직 없다. `world_handlers.py` 한 줄 변경은 명시 허용 범위 답변 대기이며 이 worker는 수정하지 않았다. 아래 기능 끄기/기동 설명은 등록 후에 적용된다. 현재 신규 시험은 모듈의 실제 등록 훅을 명시적으로 구성해 실행했다.**

## 출처와 포함 범위

- 원문: `D:/SingleLineageRef/l1j-en-classic/data/xml/Cycle/BossCycle.xml`, `db/l1jdb_m10.sql`의 `spawnlist_boss`와 `mobgroup`.
- 시간 해석: `src/l1j/server/server/model/L1BossCycle.java:init/calcSpawnTime/nextSpawnTime`. 생존 파티 중복 억제 참고: `L1BossSpawn.java:executeSpawnTask`.
- 파티 위치: `L1MobGroupSpawn.java:spawn`의 leader + nextInt(5)-2. 막힘/점유 때 강제로 겹쳐 놓는 L1J fallback은 사용하지 않고 기존 spawner 재시도를 유지하는 LOCAL 차이.
- 구현 데이터: `tools/local_original_session/data/m6/boss_cycles.json`. 모든 SQL 보스 행에 포함/제외를 기록하며 SQL 행 번호·원래 NPC 번호·현재 template·대응 근거를 보존한다.
- 현재 클라이언트 지원 맵 정책 범위 82개에서 SQL 69행: **47행 / 71개 파티 슬롯 / 17개 주기** 포함, 22행 제외. 지원 밖 67행은 별도로 데이터에 기록했다.
- 지원 목록은 맵0/1/2/4와 기존 DungeonPolicy 맵, 항해 기능이 여는70이다. 실행 때는 `realm.serves_map()`으로 한 번 더 제한하므로 관련 기능을 끄면 그 맵의 보스를 가져오지 않는다. 관련 카탈로그 기능을 빼서 MonsterDef가 없는 행도 활성화하지 않는다.

| SQL spawn id | 보스 / 현재 template (첫 항목은 대장) | 맵 | 주기 / 창(초, 끝 제외) | 슬롯 수 | SQL 줄 |
|---|---|---:|---|---:|---:|
| 4 | Crocodile: 471×1 | 4 | Crocodile: 7200 / 3600~7200 | 1 | 47835 |
| 5 | Bandit Leader: 883×1 | 4 | BanditLeader: 28800 / 600~28800 | 1 | 47836 |
| 6 | Bandit Leader: 883×1 | 4 | BanditLeader: 28800 / 600~28800 | 1 | 47837 |
| 7 | Bandit Leader: 883×1 | 4 | BanditLeader: 28800 / 600~28800 | 1 | 47838 |
| 8 | Bandit Leader: 883×1 | 4 | BanditLeader: 28800 / 600~28800 | 1 | 47839 |
| 9 | Bandit Leader: 883×1 | 4 | BanditLeader: 28800 / 600~28800 | 1 | 47840 |
| 10 | Necromancer: 10129×1, 28×4, 11×2 | 12 | Caspa: 3600 / 1800~3600 | 7 | 47841 |
| 17 | Caspa: 35×1, 36×1, 34×1, 37×1 | 9 | Caspa: 3600 / 1800~3600 | 4 | 47847 |
| 21 | Zenith Queen: 1039×1 | 110 | ZenithQueen: 28800 / 14400~28800 | 1 | 47851 |
| 22 | Ifrit: 588×1 | 4 | Ifrit: 7200 / 3600~7200 | 1 | 47852 |
| 23 | Ifrit: 588×1 | 4 | Ifrit: 7200 / 3600~7200 | 1 | 47853 |
| 24 | Ifrit: 588×1 | 4 | Ifrit: 7200 / 3600~7200 | 1 | 47854 |
| 25 | Ifrit: 588×1 | 4 | Ifrit: 7200 / 3600~7200 | 1 | 47855 |
| 26 | Drake: 250×1, 250×1 | 4 | 2Drake: 10800 / 5400~10800 | 2 | 47856 |
| 27 | Drake: 250×1 | 4 | 1Drake: 7200 / 3600~7200 | 1 | 47857 |
| 28 | Drake: 250×1 | 4 | 1Drake: 7200 / 3600~7200 | 1 | 47858 |
| 29 | Drake: 250×1, 250×1 | 4 | 2Drake: 10800 / 5400~10800 | 2 | 47859 |
| 31 | Dark Elder: 282×1, 30×2 | 4 | DarkElder: 7200 / 600~7200 | 3 | 47861 |
| 32 | Dark Elder: 282×1, 30×2 | 4 | DarkElder: 7200 / 600~7200 | 3 | 47862 |
| 34 | Seer: 1041×1 | 120 | Seer: 18000 / 9000~18000 | 1 | 47864 |
| 35 | Baphomet: 24×1 | 2 | Baphomet: 18000 / 9000~18000 | 1 | 47865 |
| 36 | Beleth: 216×1 | 24 | Beleth: 18000 / 9000~18000 | 1 | 47866 |
| 38 | Kurtz: 16×1, 15×8 | 0 | Night: 14400 / 7200~14400 | 9 | 47868 |
| 39 | Death Knight: 63×1 | 11 | DK: 25200 / 12600~25200 | 1 | 47869 |
| 44 | Ancient Giant: 12180×1 | 4 | Aden: 14400 / 5400~14400 | 1 | 47873 |
| 45 | Ant Queen: 454×1 | 51 | DK: 25200 / 12600~25200 | 1 | 47874 |
| 46 | Phoenix: 590×1 | 4 | DK: 25200 / 12600~25200 | 1 | 47875 |
| 49 | Unicorn: 10256×1 | 303 | Unicorn: 7200 / 1200~7200 | 1 | 47878 |
| 50 | Great Spirit of Earth: 10252×1 | 303 | Caspa: 3600 / 1800~3600 | 1 | 47879 |
| 51 | Great Spirit of Water: 10246×1 | 303 | Caspa: 3600 / 1800~3600 | 1 | 47880 |
| 52 | Great Spirit of Wind: 10249×1 | 303 | Caspa: 3600 / 1800~3600 | 1 | 47881 |
| 53 | Great Spirit of Fire: 10243×1 | 303 | Caspa: 3600 / 1800~3600 | 1 | 47882 |
| 55 | Demon: 332×1 | 82 | Oren: 18000 / 9000~18000 | 1 | 47884 |
| 68 | Ken Rauhel: 971×1, 902×1 | 4 | Aden: 14400 / 5400~14400 | 2 | 47897 |
| 69 | Lindvior: 900×1 | 4 | Dragon: 86400 / 3600~86400 | 1 | 47898 |
| 70 | Antharas: 327×1 | 37 | Dragon: 86400 / 3600~86400 | 1 | 47899 |
| 71 | Fafurion: 499×1 | 65 | Dragon: 86400 / 3600~86400 | 1 | 47900 |
| 200 | Great Spirit of Earth: 10252×1 | 303 | Caspa: 3600 / 1800~3600 | 1 | 47954 |
| 201 | Great Spirit of Earth: 10252×1 | 303 | Caspa: 3600 / 1800~3600 | 1 | 47955 |
| 202 | Great Spirit of Water: 10246×1 | 303 | Caspa: 3600 / 1800~3600 | 1 | 47956 |
| 203 | Great Spirit of Water: 10246×1 | 303 | Caspa: 3600 / 1800~3600 | 1 | 47957 |
| 204 | Great Spirit of Fire: 10243×1 | 303 | Caspa: 3600 / 1800~3600 | 1 | 47958 |
| 205 | Great Spirit of Fire: 10243×1 | 303 | Caspa: 3600 / 1800~3600 | 1 | 47959 |
| 211 | Unicorn: 10256×1 | 303 | Unicorn: 7200 / 1200~7200 | 1 | 47965 |
| 212 | Unicorn: 10256×1 | 303 | Unicorn: 7200 / 1200~7200 | 1 | 47966 |
| 213 | Great Spirit of Wind: 10249×1 | 303 | Caspa: 3600 / 1800~3600 | 1 | 47967 |
| 214 | Great Spirit of Wind: 10249×1 | 303 | Caspa: 3600 / 1800~3600 | 1 | 47968 |

Caspa는 SQL19749의 카스파35·메르키오르36·발터자르34·세마37을 한 주기로 소유한다. Drake 26/29행은 SQL19752의 두 마리 파티다. Dark Elder의 스파토이2, Kurtz의 흑기사8, 네크로맨서의 구울4·눈괴물2도 파티 슬롯으로 생성하지만 일반 필드의 동일 종 그룹은 억제하지 않는다.

Ifrit SQL45516은 현재 template588의 토큰$1567·SPR1773과 일치한다. 현재 전투 정책은 기존 선택 backend45515 그대로이며 이 매핑 차이를 JSON에 명시했다. 대정령45642~45645도 기존10252/10246/10249/10243의 동일 토큰·SPR 대응을 사용하며 기존 전투값을 바꾸지 않는다.

## 지원 맵에서 제외한 행

아래 제외는 신규 보스/좌표/신원을 추측하지 않기 위한 범위다. 공식 원본 동등성 완료나 전체 BossCycle 지원으로 확대하지 않는다. 기존 일반 배치가 있던 미확정 변종은 그대로 유지한다.

| SQL spawn id | 원문 이름 / 맵 | 제외 사유 | SQL 줄 |
|---|---|---|---:|
| 1 | Sea Dancer / 63 | 고정 클라이언트 신원 대응 미확정 (SQL token $1429, SPR 4017) | 47833 |
| 12 | Evil Spirit of Heine / 59 | 고정 클라이언트 신원 대응 미확정 (SQL token $4359, SPR 3364) | 47843 |
| 13 | Evil Spirit of Heine / 60 | 고정 클라이언트 신원 대응 미확정 (SQL token $4359, SPR 3364) | 47844 |
| 14 | Evil Spirit of Heine / 61 | 고정 클라이언트 신원 대응 미확정 (SQL token $4359, SPR 3364) | 47845 |
| 33 | Doppelganger / 4 | 고정 클라이언트 신원 대응 미확정 (SQL token $1554, SPR 2389) | 47863 |
| 37 | Greater Minotaur / 70 | 고정 클라이언트 신원 대응 미확정 (SQL token $2106, SPR 2402) | 47867 |
| 43 | Ice Queen / 74 | 원문 percentage=0: 임의 활성화하지 않음 | 47872 |
| 76 | Jindo Puppy / 70 | 고정 클라이언트 신원 대응 미확정 (SQL token $4072, SPR 5065) | 47905 |
| 78 | Jindo Puppy / 0 | 고정 클라이언트 신원 대응 미확정 (SQL token $4072, SPR 5065) | 47907 |
| 80 | Jindo Puppy / 4 | 고정 클라이언트 신원 대응 미확정 (SQL token $4072, SPR 5065) | 47909 |
| 89 | Elindaire / 60 | 고정 클라이언트 신원 대응 미확정 (SQL token $2049, SPR 187) | 47918 |
| 90 | Elindaire / 61 | 고정 클라이언트 신원 대응 미확정 (SQL token $2049, SPR 187) | 47919 |
| 105 | General Hamel Full of Resentment / 4 | 고정 클라이언트 신원 대응 미확정 (SQL token $5112, SPR 5979) | 47934 |
| 109 | Cursed Medusa / 60 | 고정 클라이언트 신원 대응 미확정 (SQL token $228 $2113, SPR 2535) | 47935 |
| 110 | Cursed Great Spirit of Water / 61 | 고정 클라이언트 신원 대응 미확정 (SQL token $228 $2482, SPR 4404) | 47936 |
| 111 | Spirit of Water / 63 | 고정 클라이언트 신원 대응 미확정 (SQL token $4347, SPR 5447) | 47937 |
| 112 | Spirit of Water / 63 | 고정 클라이언트 신원 대응 미확정 (SQL token $2005, SPR 2268) | 47938 |
| 113 | Kapu / 63 | 고정 클라이언트 신원 대응 미확정 (SQL token $4360, SPR 5818) | 47939 |
| 114 | Giant Worm / 63 | 고정 클라이언트 신원 대응 미확정 (SQL token $4361, SPR 5786) | 47940 |
| 126 | Ice Queen / 74 | 고정 클라이언트 신원 대응 미확정 (SQL token $1771, SPR 6581) | 47952 |
| 127 | Ice Demon / 73 | 고정 클라이언트 신원 대응 미확정 (SQL token $5525, SPR 6566) | 47953 |
| 210 | Baell Zaer / 1 | 고정 클라이언트 신원 대응 미확정 (SQL token $6077, SPR 6992) | 47964 |

Sea Dancer는 SQL45228의 SPR4017과 고정 시댄서503의 SPR1603이 다르다. Doppelganger45546의 SPR2389는 고정$1554 후보의 SPR31/2340과 다르다. Ice Queen46141의 SPR6581도 고정2118과 다르다. 해당 외형을 다른 변종으로 임의 치환하지 않았다. Greater Minotaur$2106·Jindo$4072 등은 고정 `work/source_game_data/native-dump-v1.jsonl`에 같은 토큰의 NPC 행이 없다. 정확한 대응과 출현 근거가 생기면 이 제외만 재검토한다.

## 수명·저장·끄기

- 주기는 최초 실행일 로컬 자정의 절대 timestamp를 anchor로 잡고 이후 재시작에도 그 값을 유지한다. XML End 생략은 Period이다. `[Start, End)`에서 초 단위로 한 번 뽑은 deadline을 보존한다. 첫 기동에서 이미 지난 deadline은 한 파티만 due가 된다.
- 각 SQL 행은 독립된 wave다. 대장·파티원이 살아 있거나 아직 배치에 실패한 슬롯이 있으면 다음 wave를 만들지 않는다. 죽은 파티원은 시체 종료 후 빈 상태로 기다린다. 모든 파티원이 죽으면 현재 주기와 이전 등장 주기보다 뒤인 다음 주기 창을 선택한다. 오래 살아남거나 서버가 오래 꺼져 있어도 지나간 wave를 몰아서 만들지 않는다.
- 보스 그룹만 항상 active로 두어 근처 PC가 없어도 서버 tick이 시간·시체·재시도를 소비한다. 일반 그룹의 RON/ROFF·재등장 지연·target_count는 그대로다.
- 동일 map+보스 template의 기존 일반 배치 placeholder만 실행 중 대체한다. Caspa의 고유 파티원도 대체하지만 스파토이/흑기사/구울/눈괴물 등의 일반 필드 그룹은 유지한다. 소스 JSON은 바꾸지 않는다.
- 저장은 `<characters 파일 이름>.boss_cycles.json`이라는 같은 디렉터리의 별도 파일이다. 예: `characters.json.boss_cycles.json`. 플레이어 저장·current·UIDburn은 읽거나 쓰지 않는다. 서로 다른 characters 경로는 서로 다른 보스 상태를 쓴다.
- spawned/HP변경/사망/정상 world close 때 상태를 원자적 임시 파일→`os.replace`로 저장한다. 재시작은 살아 있던 슬롯의 HP·좌표·home을 복원하되 entity UID는 새로 발급한다. 실패한 배치는 pending으로 남고, 막힘/UNKNOWN/점유 좌표로 강제 배치하지 않는다. 저장 파일이 손상되면 원문을 덮어쓰지 않고 시작을 실패시킨다.
- 정상 종료가 아닌 프로세스 종료에서는 이동만 한 마지막 좌표가 마지막 HP/등장 저장보다 최신일 수 있다. 정상 close는 최신 위치/home을 저장한다. 시체 entity는 재시작에 복구하지 않으며 저장된 다음 deadline은 유지한다. 마지막 사망의 corpse 종료보다 이르게 다음 wave를 만들지 않는다.
- 선택 기능 등록 이름은 `world_feature_boss_cycles`. `SL_DISABLE_FEATURES=world_feature_boss_cycles` 또는 FEATURE_MODULES에서 제거하면 해당 이벤트/저장 소유자가 아예 설치되지 않고 기존 일반 spawner와 배치를 사용한다. 기능을 껐다 켜도 기존 boss state 파일은 보존한다.
- 기존 report의 `world.boss_cycles.schedule`은 행별 key/cycle/state/alive/pending/dead/due_epoch를 보여준다. 생존/미완 파티는 due_epoch=null이며 과거 등장 시각을 다음 등장으로 표시하지 않는다.

## 시험과 헤드리스 확인

게임 클라이언트 실행/입력/화면 PASS는 하지 않았다. 아래는 서버 함수·유닛 검증이며 정식 로그인→월드→실제 패킷 처치 PASS와 구분한다.

`SL_TEST_TIME_SCALE=10`을 쓰고 `fast_clock.enable_from_env()`를 broker/bot import보다 먼저 호출한다. 출력은 `_work/boss_cycle/`에 보존한다. 순차 단일 시험만 허용하며 동시에 다른 게임/포트 시험을 실행하지 않는다.

```powershell
$env:SL_TEST_TIME_SCALE='10'
$env:SL_TEST_PORT_BASE='32000'
$env:TMP=(Resolve-Path _work/tmp).Path
$env:TEMP=$env:TMP
python -X utf8 -B -c "from tools.local_original_session.fast_clock import enable_from_env; enable_from_env(); import unittest; unittest.main(module='tools.local_original_session.world_boss_cycles_tests', verbosity=2)"
```

신규 boss suite는 `_work/boss_cycle/unit_artifacts/<uuid>/`에 독립 시험 상태를 보존한다. 기존 fixture의 tempfile 권한을 바꾸거나 우회하지 않는다. 일반 기동은 기존 headless 서버/봇 설정(맵2 실험과 해당 맵 기능)을 유지한 뒤 기존 report만 확인한다. 시간·death deadline의 개발 fixture 시험을 원본 렌더링/마우스/전체 플레이 동등성으로 확대하지 않는다.

검증 결과와 명령 원문은 아래 최종 결과 기록을 따른다.

## 이번 검증 결과

- `_work/boss_cycle/unit.log`: 최초 신규 suite 11건, 실패1 + 오류15. Caspa 기대 template를 잘못 쓴 한 assertion은 원문 `mobgroup`과 기존 MonsterDef를 다시 대조해 `{34,35,36,37}`로 수정했다. 나머지는 Python3.13의 mode0700 `TemporaryDirectory`를 `_work/tmp` 아래에 만든 뒤에도 읽기/쓰기/정리가 WinError5/Errno13으로 막힌 환경 오류다. 기본 TEMP와 별도 두 번 실행한 로그는 없으며 이 최초 명령부터 TMP/TEMP를 `_work/tmp`로 지정했다.
- `_work/boss_cycle/unit_retry.log`: 신규 시험 fixture만 사용자 요청 출력 경로 `_work/boss_cycle/unit_artifacts/<uuid>/`에 결과를 남기도록 바꾼 뒤 **11건 성공**. 기존 시험의 tempfile 구현이나 ACL은 수정하지 않았다. 원래 실패 로그와 산출물은 보존했다.
- `_work/boss_cycle/integration_unit.log`: 신규 등록 훅 startup→catalog 전파→report→world close→runtime_stopped를 직접 구성한 **1건 성공**. broker/클라이언트 없이 실제 모듈의 공개 훅을 소비했다. 별도 테스트 파일/프로토콜을 만들지 않았다.
- 마지막 파티 위치 보완(살아 있는 대장의 현재 좌표 사용) 뒤 `_work/boss_cycle/final_focused.log`에서 Dark Elder 파티와 등록 수명 **2건 성공**. 신규 고유 시험은 총12개(11+1)이며 이2건은 그중 재확인이다. 실행 명령은 `_work/boss_cycle/test_commands.ps1`에 보존했다.
- `_work/boss_cycle/regression.log`: 요구된 spawn/dungeon maps/dungeon terrain/field population/M5/returns/supply/Gludin 회귀 **71건 실행, 65건 성공, 6건 막힘(오류 항목12개: 각 setup와 cleanup에서 중복 오류)**. 막힌 것은 FireFarmerSupplyTests·SilverKnightSupplyTests의 각3개 저장 시험으로, `_work/tmp/tmp.../characters.json.<uuid>.tmp` 접근과 폴더 정리가 위 tempfile 권한 오류로 실패했다. assertion 실패는 없다. 이 여섯 건은 성공으로 계산하지 않으며 환경 우회/추가 재시도하지 않았다.
- 같은 회귀 실행 안의 BrokerWorldTests와 M5PacketTests는 기존 loopback 경로로 완료했다. `SL_TEST_PORT_BASE=32000`, `SL_TEST_TIME_SCALE=10`이며 시험을 순차 실행했다. 원본 게임 클라이언트는 실행하지 않았다. 보스 전투 자체의 정상 로그인→패킷 처치/전리품/화면 PASS는 미실행이다.

회귀 명령(위 TEMP/TMP·시간·포트 설정 뒤 실행, 결과 전체를 `regression.log`에 저장):

```powershell
python -X utf8 -B -c "from tools.local_original_session.fast_clock import enable_from_env; enable_from_env(); import unittest; names=['world_spawn_tests','world_dungeon_maps_tests','world_dungeon_terrain_tests','field_population_tests','world_m5_tests','world_m5_returns_tests','world_m5_supply_tests','world_m5_gludin_regression_tests']; suite=unittest.defaultTestLoader.loadTestsFromNames(['tools.local_original_session.'+n for n in names]); result=unittest.TextTestRunner(verbosity=2).run(suite); raise SystemExit(not result.wasSuccessful())"
```

아직 미검증인 것은 등록 후 실 headless 서버에서 정상 입력으로 보스까지 이동→공격/마법 처치→원드롭/경험치→실 저장→재접속하는 전체 흐름과 각47행의 실제 S32 배치 성공이다. 이번 소스 검증은 좌표를 수정/발명하지 않았으며 막힌 좌표는 기존 spawner가 pending 재시도로 남긴다. 클라이언트 신원 미확정22행(원문 비활성1행 포함)은 위 표의 근거가 확보되기 전 생성하지 않는다.
