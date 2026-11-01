# PC 경험치·HP/MP 성장 데이터

2026-10-28. `data/m1/pc_exp.json`의 기존 Lv30 제한을 Lv99로 확장한다. **누적표·최대레벨·HP/MP 수치는 L1J를 참고한 `local_policy`이며 확보한 클래식 원본과의 동등성을 입증하지 않는다.** 기존 Lv1~30 값과 직업별 성장 계산은 보존한다.

## 출처 우선순위와 확인 범위

1. 클라이언트: 기존 [MAPPING_SCOPE](MAPPING_SCOPE.md)의 경험치 표 행과 [M1_REWARD_PACKETS](M1_REWARD_PACKETS.md)의 run383 분석을 재사용했다. 원 클라이언트는 서버의 EXP 백분율 double을 표시한다. 누적 성장표·서버 HP/MP 증가 공식은 확인되지 않았으므로 클라이언트 원본 값으로 채우지 않았다.
2. 공식: 2026-10-28 익명 GET으로 [공식 가이드 목차 API](https://lineageclassic.plaync.com/api/v2/lineageclassic/categories?gwLocale=ko_KR)의 12대분류·52소분류를 확인했다. 경험치표 항목은 없었다. 같은 API의 `guide/{제목}?gwLocale=ko_KR`에서 [초보자 가이드](https://lineageclassic.plaync.com/api/v2/lineageclassic/guide/초보자%20가이드?gwLocale=ko_KR), [스탯](https://lineageclassic.plaync.com/api/v2/lineageclassic/guide/스탯?gwLocale=ko_KR), 군주·기사·요정·마법사 본문 6개를 확인했으나 누적 EXP 표, 최대 레벨, 레벨별 HP/MP 증가량·상한 숫자표를 확보하지 못했다. 스탯은 CON이 HP, WIS가 MP에 영향을 준다는 설명을 제공한다. 이 제한된 확인을 공식 자료 전체에 숫자가 없다는 결론으로 확대하지 않는다. 검색의 이용자 게시글·역산표와 NC AI 생성 안내는 수치 근거로 채택하지 않았다.
3. L1J: `D:/SingleLineageRef/l1j-en-classic`의 아래 원문을 `local_policy` 근거로 사용한다. 공식 클래식의 확정 최대레벨이 아니라 이 로컬 서버가 지원하는 최고레벨을 99로 정한다.

## 공식 확인·미확인과 남은 로컬 정책

2026-10-28 공식 원문 확인 범위를 보완했다. 아래 가이드·공지는 각각의 공개/적용 시점에 대한 근거이며 **확보 원본 버전과의 동등성은 UNKNOWN**이다. 두 JSON의 `official_findings`는 런타임에서 소비하지 않는 출처 메타데이터다. 이번 보완에서 누적 EXP, 지원 상한, HP/MP 성장값, 사망 계산값과 기존 `source=local_policy`를 바꾸지 않았다. 사망 손실의 수치 중 공식으로 출처를 확정한 것은 **Lv1~10 무손실(손실률 0)**뿐이며, 이는 이미 존재하던 런타임 hardcode와 일치한다.

| 항목 | 공식 확인 사실·시점 | 미확인·남은 `local_policy` |
| --- | --- | --- |
| CON/WIS 역할 | [공식 스탯 가이드](https://lineageclassic.plaync.com/api/v2/lineageclassic/guide/스탯?gwLocale=ko_KR): CON은 최대 HP·회복, WIS는 최대 MP·회복 및 MR에 영향 | 직업별 수치·증가량·cap·숫자 성장표는 미확인. 현재 L1J 수식 유지 |
| HP 재계산 | [오렌 Q&A](https://lounge.plaync.com/feed/71927): 초기 CON 투자와 무관하게 현재 CON으로 HP 재계산, 장비 CON도 반영 | 숫자 산식 미공개. 현재 L1J cap/레벨업 roll/original CON 보너스 방식은 공식 설명과 불일치 가능성이 있으며 재계산 구현으로 간주하지 않음 |
| EXP 완화 예정 | [2026-03-04 하이네 Q&A](https://lounge.plaync.com/feed/60745?country=KR&locale=ko-KR): 52레벨까지 요구 EXP 완화 준비 | 예정 안내다. 적용 완료·숫자표·최대레벨 52의 근거가 아님 |
| EXP 완화 적용 | [3/18 공식 업데이트](https://lounge.plaync.com/feed/62286): 40레벨 이후 레벨업 요구 EXP 완화 적용 안내 | 레벨별 숫자표 미공개. 현재 누적값은 L1J 참고 `local_policy` 유지 |
| 최고레벨 | 공식 최대레벨 직접 근거 **UNKNOWN** | 로컬 지원 상한 99 유지. 초기 52/최종 70 언론 언급이나 완화 대상 52를 공식 최대레벨로 채택하지 않음 |
| 저레벨 사망 손실 | [공식 복구 시스템 가이드](https://lineageclassic.plaync.com/api/v2/lineageclassic/guide/복구%20시스템?gwLocale=ko_KR), id6689, 갱신 2026-09-16 02:32:37+09:00, 문단25244: 10레벨 이하 경험치 손실 없음 | Lv1~10 무손실 hardcode와 일치하므로 해당 메타데이터만 `official`. Lv11 이상 손실률·분모·반올림·divisor는 공식 확인 안 됨 |
| 지역별 손실 | 같은 복구 가이드 문단25245 표: Safety·No Death Penalty Normal은 NPC/PVP 모두 없음, Normal은 모두 있음, Combat·Siege는 NPC만 있음. [PVP 시스템 가이드](https://lineageclassic.plaync.com/api/v2/lineageclassic/guide/PVP%20시스템?gwLocale=ko_KR)의 Safety/Normal/Combat/Siege 설명도 확인 | 지역별 적용 여부의 공식 근거이며 숫자 손실률 근거가 아님. 현재 지역 판정 구현·실제 소비를 입증하지 않음 |
| 복구 기록 | 공식 복구 가이드: 최대 3건, 24시간, 한도 초과 시 가장 오래된 기록 삭제 | 출처 메타데이터만 추가. 복구 기록 런타임을 새로 구현하지 않음 |
| 복구율 변경 | [7/22 공식 업데이트](https://lounge.plaync.com/feed/76029?country=KR&locale=ko-KR), 적용 2026-07-22: 사망 경험치 복구율 99.9%→97.5% | 해당 적용일 기록이며 현재 최신 복구율로 단언하지 않음. **복구율은 손실률 5%의 근거가 아님**. 복구 런타임 신규 구현 없음 |
| 커뮤니티 역산 | [인벤 2026-02-15 게시글](https://www.inven.co.kr/board/lineageclassic/6482/5774): 실측 역산과 추정 수식 | 공식 자료가 아니고 3/18 완화 이전 시점이므로 미채택 |
| 현재 수치 정책 | 공식 누적표·HP/MP 숫자표가 확보되지 않음 | 누적값·지원 99·직업별 성장·cap·Lv11 이상 사망 손실과 divisor·최고레벨 다음 경계 부재 시 EXP 보존은 기존 `local_policy` 유지 |

## 누적 EXP와 최고레벨

`src/l1j/server/server/datatables/ExpTable.java:30`은 `MAX_LEVEL=99`, `:39-40`은 `_expTable[level-1]`, `:95-116`은 누적값 배열이다. 기존 첫 30값을 보존하고 `[0..98]`까지 채택했다. 배열의 마지막 `[99]`(1,859,065,562)는 Lv100 경계이며 새 레벨로 넣지 않았다. 로더는 행 수를 최대레벨로 사용한다.

| 레벨 | 누적 EXP |
| --- | ---: |
| 30 | 810,016 |
| 31 | 923,537 |
| 50 | 55,810,962 |
| 60 | 416,461,882 |
| 65 | 596,787,342 |
| 98 | 1,786,935,378 |
| 99 | 1,823,000,470 |

Lv49 이후 인접 누적값 차이는 36,065,092다. 최고레벨을 넘는 EXP는 기존 동작대로 보존하지만 레벨과 성장 roll은 99에서 멈춘다. 기존 처치 EXP x1 계산은 변경하지 않았다. L1J의 고레벨 **획득량** penalty를 이식한 것은 아니다.

## 직업별 HP/MP

`utils/CalcStat.java:101-156,168-250`과 `config/charsettings.properties:6-13`을 재사용한다. 같은 직업별 수식을 매 레벨업마다 적용하므로 99행의 고정 HP/MP를 만들 필요가 없다. `level_growth.json.supported_levels`는 이 적용 범위를 밝히는 출처 메타데이터다. 실제 소비는 기존 `world_reward.on_kill`의 레벨업 횟수 loop다.

| 직업 | HP 기본 증가량 | HP cap | MP 배율 | MP cap |
| --- | ---: | ---: | ---: | ---: |
| 군주 0 | 11 + 0..1 + max(CON-15, 0) | 1,400 | 1 | 800 |
| 기사 1 | 17 + 0..1 + max(CON-15, 0) | 2,000 | 2/3 | 600 |
| 요정 2 | 10 + 0..1 + max(CON-15, 0) | 1,400 | 3/2 | 900 |
| 마법사 3 | 7 + 0..1 + max(CON-15, 0) | 1,000 | 2 | 1,200 |

MP는 기존 WIS 주사위·정수 내림을 사용한다. HP/MP 모두 cap 적용 후 original CON/WIS 보너스를 더하므로 최종 max가 cap보다 소폭 높을 수 있다. 기존 `PcProfile`의 base/original 미분리 한계와 `world_reward.py`의 원문 출처를 유지한다. 신규 직업·스탯 분리·레벨다운 자원 감소를 구현한 것은 아니다.

## 사망 경험치의 국소 수정

실제 산식은 `world_progress.py`가 아니라 `world_reward.py:death_exp_penalty`다. 이전 Lv99 확장 작업에서 이 함수 한 곳의 산식만 수정했다. 이번 공식 자료 조사에서는 코드를 변경하지 않았다. 호출부는 기존 `world_core_life._world_pc_died`를 그대로 사용한다.

- Lv30은 실제 Lv31 경계가 생겨 손실을 정상 계산한다.
- Lv50 이상 인자 생략 시 `config/charsettings.properties:21-71`의 divisor를 적용한다: 50~64=1, 65~69=2, 70~74=4, 75~78=8, 79~99=`2**(level-75)`. 명시 `penalty_divisor`가 있으면 우선한다. 이는 사망 계산의 정책이며 x1 처치 보상과 별개다. 원문은 `L1PcInstance.java:1227-1261`, `ExpTable.java:83-89`다.
- 공급된 마지막 레벨의 다음 경계가 없으면 `need_exp=None`, `exp_lost=0`으로 EXP를 보존한다. **이 경계 보존은 별도 로컬 정책**이며 공식/L1J의 사망 무손실 근거가 아니다. 명시 `next_level_exp`는 기존 계약대로 계산 가능하다.

## 검증과 시험 fixture

이번 공식 출처 메타데이터 추가 후 비소켓 개발 시험:

```powershell
python -X utf8 -B -m unittest tools.local_original_session.game_data_tests tools.local_original_session.world_reward_tests
# 28개 중 27개 통과, 1 ERROR: test_official_heal_ranges_drive_rng_and_preserve_status
# game_data_tests.py:191, frame, = result.frames → ValueError: too many values to unpack (expected 1)
python -X utf8 -B -m unittest tools.local_original_session.game_data_tests.GameDataTests.test_m1_tables_load_and_link tools.local_original_session.world_reward_tests
# 21개 OK: 로더·누적표·4직업 성장·Lv99 경계·사망 손실/면제
```

물약 회복 시험의 응답 프레임 개수 오류는 이번 출처 메타데이터 범위 밖이며 미수정이다. 전체 시험 통과로 표시하지 않는다. 아래 결과는 이전 Lv99 확장 작업 기록으로 보존한다. 원본 클라이언트·소켓·봇·사용자 저장은 이번에 실행하거나 변경하지 않았다.

비소켓 개발 시험에서 로더·누적값, 4직업 Lv30/50/98 이후 성장·최고레벨 overflow, Lv30 사망 손실, 고레벨 기본 divisor와 명시값 일치, Lv99 경계 보존, 진행 저장/재읽기를 확인한다. 기존 injected broker 사망 시험은 Lv11/30/50/65/99에서 HP0 상태 → 사망 패킷 순서, progress 오류 없음과 저장 호출을 확인한다. 이 함수/주입 시험을 게임·소켓·원화면 정식 PASS로 확대하지 않는다.

실행 명령과 결과: 순서대로 50개·6개·2개, 모두 OK. 별도 시험 로그 파일은 만들지 않았으며 실행 원문은 작업 세션 도구 출력에 보존한다.

```powershell
python -m unittest tools.local_original_session.game_data_tests tools.local_original_session.world_reward_tests tools.local_original_session.world_m1_reward_tests.ProgressStoreTests tools.local_original_session.world_decoupling_state_tests tools.local_original_session.world_integration_tests.InjectedBrokerTests.test_death_updates_exp_full_hp0_before_death_and_saves_progress
python -X utf8 -B -m unittest tools.local_original_session.world_m1_reward_tests.WorldRewardTests tools.local_original_session.world_m1_reward_tests.PotionDeadTests
python -X utf8 -B -m unittest tools.local_original_session.world_expansion_data_tests.ExpansionDataTests.test_monster_identity_and_client_sprite_exists tools.local_original_session.world_expansion_data_tests.ExpansionDataTests.test_every_resolved_drop_is_loadable_item
```


보스 시험의 Lv60 시작 EXP는 **416,461,882**다. HP는 레벨에 고정된 값이 아니므로 기존 승인된 시험 초기화 계약으로 지정해야 한다. 예를 들어 기사 CON12, Lv1 maxHP30에서 59회 정상 성장한 Lv60 maxHP 범위는 **1,033~1,092**(original HP 보너스 0)다. 재현 가능한 구체값은 같은 초기값·RNG로 기존 reward API를 적용한 결과를 사용한다. fixture의 HP를 바꾸는 행위는 이 작업에서 수행하지 않았다.

`work/local_original_session/manual-play/start-manual-play.ps1`의 기존 pin 목록에 이번 변경 파일은 없으며 pin은 변경하지 않았다. 원본·사용자 저장·manual profile·기존 성공/실패 로그도 변경하지 않았다.
