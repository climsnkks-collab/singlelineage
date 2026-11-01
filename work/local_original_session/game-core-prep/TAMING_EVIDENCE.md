# 고기 길들이기 근거와 원본 미확인 계약

2026-10-28 조사. 쓰기는 이 문서만이며 게임·서버·포트 실행과 코드·기존 데이터 변경은 하지 않았다. 기존 [PET_EVIDENCE](PET_EVIDENCE.md), `tools/local_original_session/world_pet.py`, `world_feature_pet.py`, `data/m1/pets.json`, `pet_runtime.json`을 재사용한다. 이 문서는 새 시험 PASS가 아니며 구현 worker가 추가하는 종의 실행 결과는 별도 결과를 따른다.

## 1. 근거 순서와 확인 범위

1. 고정 클라이언트 `work/source_game_data/native-dump-v1.jsonl`, 버전26.09.29.2001, SHA256 `a4a188ce02054beb0ab429dff32fe7affe00a930eb78bf7d9bd223b21eb721a9`: 이름/token·template·SPR 후보의 근거다. 같은 token의 복수 행을 모두 야생으로 채택하지 않는다.
2. `tools/local_original_session/data/official/{monsters,items,spells}.json`: 2026-10-28 수집본이다. 각 행 `source.raw_path`는 `work/official_data_refresh_20261028/raw/`의 원문, `source.url`은 공식 API다. 공식 이름·레벨·지역·설명은 확인되지만 아래 몬스터 응답에는 길들이기 허용/성공률/HP·CHA 수식이 없다.
3. `D:/SingleLineageRef/l1j-en-classic`은 별도 서버 설계 참고다. 공식 빈칸을 이 값으로 채우거나 고정 클라이언트 서버 규칙으로 부르지 않는다.

공식 웹 확인은 web open으로 monster9/177/179, item9/10, spell35를 시도했으나 도구가 `Internal Error/not accessible`을 반환했다. 이어 Python HTTPS GET으로 같은 공식 monster177/item10/spell35 URL을 직접 읽는 데 성공했고 아래 보존 수집값과 일치했다. 웹 도구 접근 실패를 공식 자료 부재로 해석하지 않는다. 새 원문 사본·수집 체계는 만들지 않았다.

## 2. 야생종 신원과 최소 추가 후보

아래 각 official 행은 `exact_id_and_name`이다. SPR은 공식 이미지 URL의 번호에서 추정하지 않고 고정 dump에서 읽은 값이다. 원본 길들이기 허용은 이 신원 대응만으로 확정되지 않는다.

| 종 | Classic template / token / SPR | dump 행 | 공식 야생 Lv / 주요 지역 | 현재 채택 경계 |
|---|---|---:|---|---|
| 늑대 | 9 / $268 / 96 | 9 | 6 / 말하는 섬·글루디오·윈다우드·켄트 등 | 기존 runtime 종 |
| 세퍼드 | 179 / $907 / 936 | 116 | 5 / 말하는 섬·글루디오·윈다우드·켄트 | 기존 runtime 종 |
| 도베르만 | 177 / $905 / 931 | 114 | 6 / 말하는 섬·글루디오·윈다우드·켄트 | 이번 최소 추가 후보 |
| 비글 | 180 / $908 / 938 | 117 | 5 / 글루디오·윈다우드·켄트 | 신원만 확인, 자동 추가 안 함 |
| 세인트버나드 | 176 / $904 / 929 | 113 | 5 / 국경 요새·오렌 | 신원만 확인 |
| 콜리 | 178 / $906 / 934 | 115 | 5 / 국경 요새·오렌 | 신원만 확인 |
| 허스키 | 706 / $1788 / 2145 | 370 | 5 / 국경 요새·오렌 | 신원만 확인 |

도베르만의 같은 token/SPR 후보183·226·10062·10155는 야생/펫/변종 역할이 미확인이다. 최소 후보177을 명시하고 다른 후보를 자동 치환하지 않는다. 전체 pure 카탈로그14종 중12종은 이름/token·SPR 후보가 있으나 Tiger/Jindo Puppy는 고정 Classic 후보가 없다. 이 분모는 실제 구현·허용종 수가 아니다.

도베르만 [공식 원출처](https://api-goats.plaync.com/linclassic/v2.0/game/monster/177?locale=ko-KR)는 이름·Lv6·지역 및 고기10/아데나7/동물가죽332 드롭을 제공한다. 드롭 고기라는 사실은 길들이기 먹이라는 증명이 아니다.

### 도베르만 backend 참고값

`D:/SingleLineageRef/l1j-en-classic/db/l1jdb_m10.sql:20662`의 npc45042: Lv5, HP20, MP5, AC25, STR16, DEX10, EXP37, 이동560ms, 공격960ms, SPR931. `:24547`의 pettypes45042: 먹이40057, HP성장3..6, MP성장1..2. 이 수치·속도를 채택하면 **L1J 참고 LOCAL 정책**이다. 공식 야생Lv6와 L1J 펫 초기Lv5/EXP750을 구분한다. runtime의 고정 damage5를 유지하면 그 값 역시 LOCAL이며 STR16에서 공식 damage5를 도출했다고 주장하지 않는다.

## 3. 음식과 원본 도움말

- dump·공식 이름 대응: 고기10/token `$23`, 괴물 눈 고기9/token `$6 $23`, 펫 목걸이361/token `$1173`/icon487/SPR1317(dump1231행). template·inventory instance UID·durable pet ID·live actor UID는 별개다.
- [공식 고기10](https://api-goats.plaync.com/linclassic/v2.0/game/item/10?locale=ko-KR)은 포만감·배고플 때 회복 제한을 설명한다. [괴물 눈 고기9](https://api-goats.plaync.com/linclassic/v2.0/game/item/9?locale=ko-KR)은 마법 재료·감각 효과를 설명한다. 두 item은 다른 정체성이며 같은 아이콘을 써도 합치지 않는다.
- [목걸이361](https://api-goats.plaync.com/linclassic/v2.0/game/item/361?locale=ko-KR)은 길들인 펫의 주인 표시와 목걸이 교환을 통한 펫 교환을 설명한다. 실제 생성/소환/보관 raw, 소유권 거래 절차를 설명한 자료는 아니다.
- 기존 `work/local_resource_provider/assets/data/dialogue.csv:473`, `helpnpc_1`은 약해진 늑대에 음식 제공, 종류별 다른 음식, 전투 경험치/성장을 설명한다(PET_EVIDENCE 재사용). 정확 HP 분수·CHA·확률·음식 소모는 없다.

## 4. L1J 길들이기와 LOCAL 선택의 차이

`C_GiveItem.java:154–187`은 giver→NPC inventory transfer, `onGetItem`, pettype의 먹이 비교 순서다. 양도 수량은 시도 횟수가 아니며 transfer 자체를 음식 파괴/실제 섭취라고 부르지 않는다. `:252–289`는 기존 pet/summon 제외, CHA+class bonus−사용 petcost≥6, transfer 뒤 슬롯<180이면 목걸이40314 발급이다. `:318–338`은 **HP < floor(maxHP/3)**, Tiger만1/16 RNG, Tiger/Raccoon/Jindo 부활 이력 제한이다. 일반 개/늑대는 이 경로에 추가 확률 판정이 없다.

현재 pure `world_pet.offer_food`는 이 참고 규칙을 제안하며 실제 item/actor/save를 수정하지 않는다. caller가 실제 소유·수량·현재 세대·거리·저장·중복 실행을 책임진다. 기존 `world_feature_pet.PetSystem.tame`는 다음을 명시 LOCAL로 구현한다.

- 고기10과 괴물 눈 고기9를 지원종 먹이로 허용한다. L1J 개/늑대 pettypes의40057 전용을 변경한 제품 선택이다.
- 유효 제공은 HP/CHA 실패에도 한 개를 소비한다. L1J inventory transfer 의미와 구분한다.
- 가시 야생·현재 세대·생존·같은 map·거리≤3, active-cap1, inventory 소유를 확인한다. 종별 주변 배치도 LOCAL이다.
- 성공하면 기존 공동 store의 pending bag/CAS에 음식1개와 새 목걸이361을 기록하고 durable 완료 뒤 야생 세대를 끝낸다. 목걸이는 보관·재소환·사망·부활 때 소비하지 않는다.

HP 경계 예: maxHP30이면10 미만, maxHP20인 도베르만이면6 미만이다. HP6은 도베르만 성공값이 아니다. 이는 LOCAL로 채택한 L1J 수식의 경계이며 공식 확정식이 아니다.

길들인 직후 HP/MP: `L1PetInstance.java:160-171`(야생→펫 생성자)은 `setCurrentHpDirect(target.getCurrentHp())`·`setCurrentMpDirect(target.getCurrentMp())`로 **야생의 남은 HP/MP를 그대로** 잇고 최대치는 템플릿 값이다. 현 제품의 `hp=slot.hp`(예 8/30)는 이와 같아 바꾸지 않았다. 회복은 `:589-616` setCurrentHp/Mp가 최대 미만일 때 `L1NpcInstance.java:849-958` 고정주기 Hpr/MprTimer를 켜는 방식이며, 개/늑대/도베르만 npc(`l1jdb_m10.sql:20654,20662,20663`)는 hprinterval5000·hpr5, mprinterval0·mpr0(MP 자연회복 없음)이다. 이를 `pet_runtime.json` species.regeneration과 `world_feature_pet.PetSystem.regenerate`(펫 tick)에 **L1J 참고 LOCAL 정책**으로 넣었다(2026-10-28).

## 5. 요청·응답과 실제 소비의 경계

기존 REA393/396/400 및 [PET_EVIDENCE](PET_EVIDENCE.md), [ENCHANT_USE_EVIDENCE](ENCHANT_USE_EVIDENCE.md)를 재사용한다.

| 흐름 | 확인 계약 | 미확인/LOCAL |
|---|---|---|
| 일반 대상 item0960 | outer f1=inventory UID, f2=nested; nested f1=1/f2=int64 대상UID/f3=0/f15=0/f16=0 | 고기 길들이기에서 원 UI가 이 producer를 고르는지는 UNKNOWN. 현재 targeted-food 수신은 LOCAL adapter |
| 목걸이0960 | 현재 adapter는 nested f1=1/f15=0/f16=0 | 목걸이 원본 raw/presence 및 소환/보관 요청 producer UNKNOWN |
| 펫 조회4F13→4F14 | 요청f1=u32 actor UID; 응답f1 UID/f2=1 PetLayout/f3 child required | 공식 서버 같은 operation의 실제 송신 기록 UNKNOWN |
| 명령4F02 | f1 명령, f2 repeated string, f3 펫UID. 목표지정1은 f2=[적 UID 10진문자열]; 공격2/방어3/휴식4/경계5/수집6/산개7/해산8 | 번호는 원본 정적 근거, 서버 AI 거리·동작은 LOCAL |
| 출현4E96 / HP4F1A / 제거4E40 | 소유이름f21·Pet enum f67=1에 추가 생성조건 필요; HP통지f1 UID/f2 percent; 제거f1 UID→HUD 해제 | f67만으로 Pet 생성 보장 안 함. HP통지 required f3 업무 의미 UNKNOWN, 현재0은 LOCAL |

이전 `runs/hunt-pet-42ag8958/summary.json`의 fresh170/170과12개 socket 개발시험은 기존 wolf/shepherd 조합의 로컬패킷·저장·성장·사망/부활·정상close 근거다. 새 도베르만/변경Source에 이전 PASS를 이전하지 않으며 원 UI·입력·렌더링 동등성으로 확대하지 않는다. 이번 조사에서 새 실행은 하지 않았다.

## 6. 테이밍 몬스터 마법35는 별도 수명

[공식 spell35](https://api-goats.plaync.com/linclassic/v2.0/game/spell/35?locale=ko-KR)와 `data/official/spells.json`/`data/m3/player_spells.json`: 요정40·법사20, MP30·마력의 돌166×2,10칸 NPC1인,3600초 하수인. `L1SkillUse.java:2942–2971`은 `L1SummonInstance(target,user,false)`로 연결한다. 영구 목걸이 펫과 합치지 않는다. 임시 신원·만료/죽음/이탈/재접속·비용 once/실패복구가 마련되지 않은 기존 `CAST_UNSUPPORTED` 경계는 이 문서에서 변경하지 않는다.

## 7. 원본 UNKNOWN과 필요한 최소 관측

고기 길들이기의 원 UI→정확 producer/0960 payload, 종별 실제 먹이·HP·CHA·확률·실패 소모, 목걸이 원 raw/선택목록·거래·소환/보관 wire, 원본 야생/펫 전환 응답 순서는 아직 UNKNOWN이다. 종 이름/SPR/공식 지역이나 LOCAL packet 성공으로 닫지 않는다.

이를 닫는 최소 입력은 고정 버전의 정상 온라인 한 번에서 **실제 약화된 대상·소유 먹이UID→원 제공 입력→C2S→성공/실패 S2C 및 수량/배우/목걸이 변화**의 동일 operation 관측이다. 현재 분석에는 그 원본 관측이 없으므로 이미 확보한 로컬 구현은 LOCAL 경계를 유지한다. 공식 도움말/도감은 정체성·설명 근거이며 원서버 수식·원요청의 대체 증거가 아니다.

## 8. 이번 구현과 검증

변경은 `world_feature_pet.py`의 국소 tame/consume 패치, `data/m1/pet_runtime.json`의 도베르만177 등록, 신규 `world_tame_tests.py`·`hunt_bot_tame.py` 및 이 문서다. 도베르만은 기존 `population_m1_0_177` 야생 스폰을 재사용하며 별도 배치를 추가하지 않았다. `world_pet.py`, `hunt_bot_pet.py`, 몬스터표, launcher와 수동 실행 핀은 이번 작업에서 수정하지 않았다.

성공 길들이기에서 마지막 고기의 비앵커 행은 목걸이 공간을 확보하며, 기존 첫 장비 앵커는 보존한다. 새 목걸이 UID는 삭제 전 전체 행과 보유 목걸이보다 크게 발급한다. 저장 intent의 before/after와 실제 inventory CAS를 일치시킨다. 실패 제공의 소비량은 pure 제안의 `transfer_count`를 따른다. 신규 개발시험7개는 이 경계와 중복 요청·야생 수명 종료·목걸이 복원을 확인한다.

전용 봇은 기존 `PetScenario`의 정상 FIRST/login/select/world·fixture·finally/close를 재사용한다. 종 선택만 늑대/세퍼드/도베르만으로 제한하며 실공격으로 약화한 현재 야생 UID에 고기를 제공한다. 소환 뒤 HOLD→주인 이동→공격 태세2의 LOCAL FOLLOW를 요청하고 실제 `4E2C` 이동 수신과 주인 거리≤2를 확인한다. 별도 원본 Follow 버튼을 복원했다고 주장하지 않는다.

실행별 Source SHA 조합과 시작 시험 저장은 각 `summary.json`의 `source_sha256_start`·`source_sha256`·`fixture`에 보존한다. 새 pre-login 시험 프로필에 기존 Lv6/먹이 등 자원을 공급한 범위이며 사용자 저장을 사용하지 않는다. 가상 시간10배, `SL_TEST_PORT_BASE=60000`의 기존 포트 매핑은 물리60000/62030이다. 원본 클라이언트는 실행하지 않았다.

검증 결과는 아래에 기록한다.

| 실행 | 결과 | 원문 |
|---|---|---|
| `python -X utf8 -B -m unittest tools.local_original_session.world_pet_tests tools.local_original_session.world_pet_integration_tests tools.local_original_session.world_tame_tests` | 51개 실행, 오류/실패0, opt-in 소켓1개 skipped. 신규 tame7개 포함 | `runs/tame-validation-20261028-141809/unit-integration.log` |
| fastbot `hunt_bot_tame --species wolf --navigation-timeout 900 --death-timeout 600` | SUCCESS12/12, 추적목록 source 변경없음, 정상 cleanup | `runs/hunt-tame-zkhweuwh/summary.json` |
| fastbot `hunt_bot_tame --species doberman --navigation-timeout 900 --death-timeout 600` | SUCCESS12/12, 추적목록 source 변경없음, 정상 cleanup. HP20→4 실공격 뒤 고기20→19, 목걸이65573 발급 | `runs/hunt-tame-w8wijdsf/summary.json` |

fastbot 명령은 `SL_PET=1`, `SL_TEST_TIME_SCALE=10`, `SL_TEST_PORT_BASE=60000`에서 `python -X utf8 -B C:\Users\Chansol\AppData\Local\Temp\claude\D--claude\0483de89-75e7-4b94-84b8-fb31fe00f575\scratchpad\fastbot\run_fast.py <모듈> <인자>` 형식으로 실행했다. 종별 두 실행은 독립된 새 저장의 로컬 패킷 PASS이며 하나의 연속 저장이나 원본 화면 PASS로 합산하지 않는다.

기존 full 소켓 회귀의 첫 실행은 `runs/hunt-pet-xhectnhw/summary.json`·`runs/tame-validation-20261028-141809/socket-integration.log`에 FAILED로 보존한다. 14개 체크 중13개 성공 뒤 저장 재접속에서 `items.243: kind/duplicate`로 실패했고 cleanup은 정상, broker 예외는 없었다. 실행 시작14:19:47 뒤 범위 밖 `game_data.py`(14:20:11)·`data/m1/items_ext/misc.json`(14:20:12)이 변경됐고 재접속14:20:13에 새 misc243이 로딩됐다. 구 프로세스의 in-memory kind 목록과 새 데이터가 섞인 것이 유력하지만 시작 시 해당 의존 소스 사본이 없어 확정하지 않는다. 기존 봇의 `source_changes_during_run=[]`는 기록한 파일 목록 안의 판정이며 이 두 파일을 포함하지 않는다. 이후 새 프로세스 `load_m1()`의559종 로딩 정상 확인을 새 입력으로 삼아 동일 pet 소스의 clean-process 회귀를 한 번 재시도한다. 범위 밖 파일은 이 작업에서 수정하지 않았다.

재시도 `runs/hunt-pet-ivlbkp_y/summary.json`은 startup에서 `world_feature_weapon_effects` 모듈 부재로 FAILED, 펫 단계0개였다. 이후 파일 복원·fresh import 성공을 확인해 마지막 재시도를 했으나 `runs/hunt-pet-oog0ci9v/summary.json`은 startup의 `data/crafting.json` 부재로 FAILED, 펫 단계0개였다. 로그는 각각 `socket-integration-retry.log`·`socket-integration-final.log`이며 같은 validation 폴더에 의존 메타데이터를 보존한다. 두 재시도에서 기록한 외부 의존의 시작/끝 SHA·mtime는 같았으나 전체 작업 폴더 고정을 증명하지 않는다. 모든 실행 cleanup은 정상이며 최종 물리60000/62030 listener는 없다.

**최종 판정: 신규 tame 개발시험7개 및 늑대·도베르만 전용 패킷 흐름은 PASS. 기존 pet 단위/개발시험은 통과했으나, 기존 full 소켓 회귀는 공용 의존성 준비 실패로 미완료다. 따라서 요청의 전체 done_when을 완료로 표시하지 않는다.** 통합 작업자가 공용 의존성을 안정화한 후 아래 기존 시험을 실행해야 한다. 그때의 Source·시작 저장에 결과를 귀속하고 이번 두 종의 PASS를 이전하지 않는다.

```powershell
$env:SL_PET='1'
$env:SL_TEST_PORT_BASE='60000'
$env:SL_TEST_TIME_SCALE='10'
$env:SL_RUN_PET_INTEGRATION='1'
python -X utf8 -B -c "from tools.local_original_session import fast_clock; fast_clock.enable_from_env(); import unittest; unittest.main(module='tools.local_original_session.world_pet_integration_tests', argv=['pet-socket-regression','PetSocketTests.test_real_pet_lifecycle_and_companion_coexistence'], verbosity=2)"
```

핀 일괄 갱신 검토 대상으로 전달할 이번 기존 제품 파일 변경은 `tools/local_original_session/world_feature_pet.py`·`tools/local_original_session/data/m1/pet_runtime.json`이다. 수동 실행 스크립트/launcher 핀 자체는 수정하지 않았다.
