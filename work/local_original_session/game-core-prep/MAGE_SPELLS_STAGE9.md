# 플레이어 법사 9단계 — 요청한 6종

2026-10-31. 고정 클라이언트 **26.09.29.2001**. 공식 원문과 고정 자원을 우선하며 기존7단계 시전·소비·표시·저장 구조를 확장했다. 단위 시험과 원본 화면 확인은 별개다.

## 출처·학습·소비

**O키**는 `tools/local_original_session/data/official/spells.json`과 `work/official_data_refresh_20261028/raw/spell/<키>.json` 보관 원문이다. 각 행 `source_snapshot.official_source`에 URL·수집 시각·SHA256을 보존했다. HP0·재료0은 공식 list를 우선한다. **C키**는 `native-dump-v1.jsonl` spell2279~2284행 및 고정 UI join/CommonSpell 행이다. 책은 공식 textbook ID·이름과 native item.f41을 동시에 확인했다. **L**은 고정 `D:/SingleLineageRef/l1j-en-classic` HEAD `103e6f6c9dd83545959d8e87d3f59f8de1f40ef0`, `db/l1jdb_m10.sql:35685,35686,35688~35691`의 명시 이름/단계 대응 행이다. 공식 > 고정 클라이언트 > L1J 순서를 적용한다. 이번 작업의 새 HTTP 성공을 주장하지 않는다.

6종 모두 **법사36레벨** [각 O.learnings]. 학습 장소·성향 임계값은 UNKNOWN, 현재 **LOCAL 추가 장소/성향 제한 없음**이다. 기존 실제 책 `0960` handler·소유/양수 수량·학습 intent·kit CAS·magic save·`4E60`을 그대로 쓴다. 1권을1회 소비하며 중복·조건 불충족은 무소비다. MP는 공식 기본값 실제 차감 LOCAL이며 동적 MP 절감 UNKNOWN. 재사용의 공식 서버 값은 UNKNOWN이며 아래는 명시 LOCAL 값이다.

| 키 / 이름 | 책 template [O,C] | MP / HP / 돌166 | LOCAL 재사용 [L] | 구현 범위 |
|---|---|---|---|---|
| 64 라이트닝 스톰 | 219 | 48 / 0 / 0 [O64,list,C64] | 0.5초 | 구현함. 실제 대상 중심3칸 현재 일반 몬스터 피해 |
| 65 포그 오브 슬리핑 | 220 | 40 / 0 / 1 [O65,C65] | 1.5초 | 구현함. 공식 단일 PC/NPC 수면1~8초 |
| 67 이뮨 투 함 | 222 | 30 / 0 / 2 [O67,C67] | 1.5초 | **부분**. 현재 PC 실제 피해30% 감소32초. native 혈맹 구성원 생산자 없음 |
| 68 매스 텔레포트 | 223 | 60 / 0 / 0 [O68,list,C68] | 1초(SQL0→기존 기본값) | **부분**. 술자·기존 동료/펫 이동 훅, 등록 그룹 수신자 접점. native PC 파티/혈맹 생산자·주문 북마크 wire 없음 |
| 69 파이어 스톰 | 525 | 48 / 0 / 0 [O69,list,C69] | 0.4초 | 구현함. 술자 중심3칸 현재 일반 몬스터 피해 |
| 70 디케이 포션 | 1490 | 20 / 0 / 2 [O70,C70] | 0.5초 | 구현함. PC 물약 사용 차단4~16초, 소비 전 차단 |

기존 책 정의·가격·UID 체계를 보존해 `spellbooks.json`으로 옮겼다. generic `stage_support`는1~9단계 중 등록67/지원64/기존 미지원3이며 직업 원문을 포함한 전체 카탈로그108행과 구분한다. 새 8/9단계 각6행 이외의 마법은 추가하지 않았다. 동료 AI의 지원 마법/ATS 동작을 확대하거나 `classes.json`을 바꾸지 않았다.

## 효과·표시·화면 확인

| 마법 | 대상·수치·지속 / 출처 | action / gfx [L,고정 자원] | HUD K / tooltip [C] | 화면 확인 | 캡처 경로 |
|---|---|---|---|---|---|
| 라이트닝 스톰 | 10칸 내 대상과 그 주위3칸 모든 적 [O64]. 현재 가시 일반 몬스터 LOCAL `5d10+25`·바람8·기존 INT/SP/MR [L35685,L1Magic659~783]. 술자 중심으로 바꾸지 않음 | 18 / 3924 | 순간 효과 | 구현함. native 푸른 번개·피해12·처치·MP48 확인 | [2회 즉시](../runs/mage-stage9-20261031-02/mage-64-immediate.png) |
| 포그 오브 슬리핑 | 6칸PC/NPC **1인**·수면1~8초 [O65]. L1J 영역3/32초를 복사하지 않음. LOCAL 확률dice8 [L35686], 공식 범위 내 정수 균등 시간 선택(원 분포 UNKNOWN). 이동·공격·시전 차단, 실제 양수 피해로 해제 | 19 / 760 + 기존 block0 표시(LOCAL) | 1560 / 296 [native2280], 실제 남은 초 | 구현함. native NPC 구름·성공·MP40/돌1 확인. 4회 지연 상태 아이콘 확인. 활성8초 툴팁은 timer 오류로 미확인, 같은 원인2회 이후 재시도 없음 | [NPC 효과](../runs/mage-stage9-20261031-02/mage-65-immediate.png), [지연 아이콘](../runs/mage-stage89-20261031-04/mage-world-entry.png) |
| 이뮨 투 함 | 10칸 술자/혈맹원1인·**피해30% 감소32초** [O67,C67]. L1J50%를 거부. 현재 PC 물리/특수 물리/마법/독 HP 차감 전에70/100 정수 연산. 회복량 유지. 다른 PC는 등록 clan_members 필요 | 19 / 228 | 1562 / 966 [native2281] | 부분. native 녹색 광채·HUD·남은26초 확인. 실제30% 감소는 단위 확인. 혈맹 구성원 생산자/독립 동료 HP 수신 경로 미완 | [효과](../runs/mage-stage9-20261031-02/mage-67-immediate.png), [HUD](../runs/mage-stage9-20261031-02/mage-67-tooltip.png) |
| 매스 텔레포트 | 술자 포함 주위2칸 혈맹원 [O68]. 기존 Teleport의 실제 request/operation lock·목적지·저장/재배치·동료/펫 훅 재사용. LOCAL 파티 확장. random radius200은 기존 텔레포트 LOCAL 정책, Classic 실제 범위 UNKNOWN | 19 / 2236, 도착 후 원 재배치 표시 | 순간 효과 | 부분. native 술자 이동·지형 변경·MP60 확인. 시전 동작은 보이나 고유 gfx 모양 미확인. 5회 knight 전용 fixture 조건으로 동료 동반 화면 미확인. PC 그룹/북마크 wire 미구현 | [이동 전](../runs/mage-stage9-20261031-02/mage-68-before.png), [이동 후](../runs/mage-stage9-20261031-02/mage-68-after.png) |
| 파이어 스톰 | 술자 중심3칸 모든 적 [O69,C69 around]. 현재 일반 NPC LOCAL `8d15+30`·불2·기존 INT/SP/MR [L35690] | 18 / 1819 | 순간 효과 | 구현함. native 주황 불꽃·MP48 확인. 2·6회 범위 내 피해0이므로 실제 피해 화면은 미확인; 단위 피해 통과 | [2회 효과](../runs/mage-stage9-20261031-02/mage-69-immediate.png), [6회 효과](../runs/mage-stage89-20261031-06/mage-69-immediate.png) |
| 디케이 포션 | 3칸PC1인·4~16초 [O70]. LOCAL 확률dice10 [L35691], 공식 범위 내 정수 균등 시간 선택(원 분포 UNKNOWN). 힐/가속/블루/지혜/호흡/해독 물약을 실제 수량 CAS 전에 거절. 음식·주문서·마법 힐 유지 | 19 / 2232 | 754 / 12607 [native2284] | 구현함. PC 물약 차단/무소비 단위 통과. 6회 수신 렌더 fixture의 HUD·물약 사용 불가·남은15초 확인. native 시전은 self PC를 클라이언트가 거절하여 미확인 | [수신 HUD](../runs/mage-stage89-20261031-06/mage-received-0-tooltip.png) |

순간 효과에 가짜 버프 아이콘을 만들지 않는다. `4E31`/`4ED8`은 기존 정상 시전 표시를 설정 OFF에서도 새12종에 송신한다. 수면은 기존 검증된 block 표시를 LOCAL로 사용하며 원 수면 자세 동등성은 UNKNOWN이다. 실제 양수 피해가 없으면 단지 공격 요청만으로 수면을 깨우지 않는다. 상태는 기존 PC effects 또는 현재 NPC EntityRef에 속하며 generation/사망/이탈 정리 경로를 지킨다.

포그·이뮨·디케이는 기존 magic effects 저장, 실제 오프라인 경과 차감, 텔레포트 뒤 deadline/HUD replay, 만료/캔슬/사망 정리를 사용한다. 각 실제 남은 초로 HUD를 갱신하며 재접속/이동 때문에 새 지속시간을 주지 않는다. 물약 거절은 기존 소비 진입점과 checkpoint 이후 CAS 직전 둘 다 적용해 await 중 디케이가 들어와도 수량을 먼저 쓰지 않는다.

매스 텔레포트는 실제 현재 그룹 수신자를 `party_members`/`clan_members`로 받는다. **근처 PC를 임의 그룹으로 만들지 않는다.** 수신자의 기존 잠금·저장·송신 소유자가 없는 등록 그룹은 비용 전에 거절한다. native PC 파티/혈맹 구성원 생성과 주문의 선택 북마크 wire는 없으므로 전체 그룹 이동 완료로 주장하지 않는다. 기존 동료/펫의 이동 훅은 술자 원 재배치에서 재사용된다. 클라이언트 미사용 좌표를 검증 없는 목적지로 바꾸지 않는다.

## 시험

8/9단계 전용 **35개 통과**, `_work/tmp/mage-stage89-unit-final-v2.log`(전체512개에 신규35개 포함). 범위 중심·실제 HP/MP/돌·단일 수면/피해 해제·Counter/실패·30% 감소의 사망 전 HP 소비·두 물리 경로/마법/독·물약 무소비 거절·저장/이동/HUD/만료·실제 책 handler를 포함한다. 추가 관련 ATS 목록/물약 실패 보존 시험10개 통과: `_work/tmp/mage-stage89-focused-final.log`.

최종 전체 **512개: 통과511, 실패0, 오류0, skip1**, 신규35개 포함. unittest 실행233.142초(러너 전체233.855초). 재현:

```powershell
$env:TEMP=(Resolve-Path _work/tmp).Path
$env:TMP=$env:TEMP
python _work/tmp/run_stage89_unit.py _work/tmp/mage-stage89-unit-final-v2.log
```

목록 `_work/tmp/mage-stage89-test-modules.txt`: 요청 w133 28모듈 + stage7/8/9 + 학습, stage6 중복 제거. launcher/manual_move_commands 제외. `hunt_bot_companion.run`을 실행하는 기존 socket 통합1개는 사용자 hunt_bot 금지로 skip을 유지한다. 단위 시험은 원본 화면·정상 게임 종료 PASS를 뜻하지 않는다.

## 헤드리스 실행 기록

단위 검증 완료 후 기존 `mage_stage9` 시나리오·owned desktop·GLFW callback injection. 시험 사본 `_work/tmp/mage-stage89-20261031/profile-stage9`는 사용자 저장과 독립적으로 LV60/HP100(최대1000)/MP1500·능력치·학습 완료 초기값을 준비했다. 책6개는 기존 UID allocator·kit append CAS로 추가했다. 원 NPC 수치·확률·소환을 강제하지 않았다. native 책 학습 증거와 구별한다. 좌표는 기존 UI node와 현재 캡처 측정/기존 격자 함수만 사용한다.

실행은 총6회로 마쳤다. 실행 폴더별 결과·후보 해시·전후 LC/리스너·DLL 복원은 [8단계 전체 실행 기록](MAGE_SPELLS_STAGE8.md)에 적었다. 모두 `FORCED_CLEANUP`, 정상 종료/logout은 미확인이다.

9단계 중심 실행은 [2회](../runs/mage-stage9-20261031-02/result.json)이며 67·65·64·69·68 native 시전, 70 self-target 클라이언트 거절을 기록했다. [4회](../runs/mage-stage89-20261031-04/result.json)는 실제 저장 투명 재접속과63/65/70 수신 상태 렌더 fixture를 분리했다. 활성 대기 timer 오류로 포그 툴팁은 미확인이며 같은 원인2회 후 재시도하지 않았다. [5회](../runs/mage-stage9-20261031-05/result.json)는 `COMPANION_TEST_KNIGHT_REQUIRED`로 primary resume/로그인 전 실패했으며 동료 조건을 우회하지 않았다. [6회](../runs/mage-stage89-20261031-06/result.json)는63/70 수신 HUD13/15초를 확인한 뒤 자연 만료 후61·69를 실제 시전했다.

수신 렌더 fixture는 실제 적대 PC 시전·확률·물약 클릭의 화면 PASS가 아니다. 12권 학습은 실제 handler/CAS/4E60 단위 확인이며, 헤드리스의 사전 학습 값으로 native 학습 화면을 주장하지 않는다. 상태별 재접속·텔레포트 replay는 단위 확인이며, 화면 재접속은 인비지블리티만 직접 확인했다.

## UNKNOWN / 부분 범위

- 이뮨의 native 혈맹 구성원 생산자·다른 독립 동료 HP 소유자의 수신 경로는 미완. 현재 PC HP 소유자와 등록 혈맹원만 지원한다. 환경 익사·PvP 등 별도 피해 경로는 이번 근거로 전체 성공을 주장하지 않는다.
- 매스 텔레포트의 실제 PC 파티/혈맹 구성·그룹 수신자 소유 서비스·주문 북마크 선택 wire는 미완. 술자 랜덤 이동과 기존 동료/펫 이동 훅만 현재 실제 경로다.
- 포그/디케이의 공식 시간 범위는 확인했지만 원 분포/성공 확률은 UNKNOWN. LOCAL 균등 시간/이름 대응 L1J dice를 사용한다.
- 공식 서버 재사용, 동적 MP 감소, 정확한 피해/확률식, 관계/안전지역/PvP, 원 수면 자세·모든 순간 효과 픽셀 동등성은 UNKNOWN. 현재 일반 NPC 피해를 그 밖의 대상으로 확대하지 않는다.

## 변경 파일·줄

아래 표는 8/9단계 공통 최종 변경 파일과 진입 줄이다. 기존 카탈로그96행 값은 유지하고 요청12행만 추가했다. 사용자 저장·동료 classes/hotbar probe 수정과 커밋은 하지 않았다. 게임 DLL은 실행 wrapper의 후보 배치·원본 복원을 거쳤으며 코드 수정은 없다.


| 파일:줄 | 변경 요지 |
|---|---|
| [tools/local_original_session/world_feature_magic.py:23](../../../tools/local_original_session/world_feature_magic.py#L23) | 시전·범위·부활·상태·HUD·저장 연결 |
| [tools/local_original_session/world_magic_stage89.py:1](../../../tools/local_original_session/world_magic_stage89.py#L1) | 기존 NPC/동료/펫 부활 및 그룹 수신자 연결 |
| [tools/local_original_session/world_magic.py:250](../../../tools/local_original_session/world_magic.py#L250) | 독립 PC 침묵·투명·피해30% 감소 |
| [tools/local_original_session/world_magic_status.py:13](../../../tools/local_original_session/world_magic_status.py#L13) | 수면·이뮨·디케이·투명 상태 수명 |
| [tools/local_original_session/world_entities.py:167](../../../tools/local_original_session/world_entities.py#L167) | 현재 NPC 시체의 새 generation 부활 |
| [tools/local_original_session/world_interest_spawn.py:84](../../../tools/local_original_session/world_interest_spawn.py#L84) | 부활 시 corpse/respawn 취소·원 spawn 수명 |
| [tools/local_original_session/world_visibility.py:694](../../../tools/local_original_session/world_visibility.py#L694) | LOCAL 동일 spawn 두 번째 보상 방지 |
| [tools/local_original_session/world_feature_companion.py:66](../../../tools/local_original_session/world_feature_companion.py#L66) | 기존 동료 부활 등록 훅 |
| [tools/local_original_session/world_feature_pet.py:1132](../../../tools/local_original_session/world_feature_pet.py#L1132) | 기존 펫 부활 등록 훅 |
| [tools/local_original_session/world_monster_skills.py:167](../../../tools/local_original_session/world_monster_skills.py#L167) | NPC 침묵과 특수 물리 피해 이뮨 적용 |
| [tools/local_original_session/world_feature_items.py:312](../../../tools/local_original_session/world_feature_items.py#L312) | 물약 소비 전 상태 확인 |
| [tools/local_original_session/world_item_effects.py:1332](../../../tools/local_original_session/world_item_effects.py#L1332) | 확장 물약 CAS 전 디케이 적용 |
| [tools/local_original_session/item_equipment_effect.py:474](../../../tools/local_original_session/item_equipment_effect.py#L474) | kit 물약·checkpoint 후 CAS 전 디케이 적용 |
| [tools/local_original_session/data/m3/player_spells.json:24993](../../../tools/local_original_session/data/m3/player_spells.json#L24993) | 12행·stage_support·값별 출처·LOCAL/UNKNOWN |
| [tools/local_original_session/data/m1/items_ext/spellbooks.json:1420](../../../tools/local_original_session/data/m1/items_ext/spellbooks.json#L1420) | 기존 12권 정의 보존·학습 연결 |
| [tools/local_original_session/data/m1/items_ext/drops_misc.json:6906](../../../tools/local_original_session/data/m1/items_ext/drops_misc.json#L6906) | 옮긴 마법서의 중복 정의 제거 |
| [tools/local_original_session/data/m1/items_ext/misc.json:489](../../../tools/local_original_session/data/m1/items_ext/misc.json#L489) | 옮긴 마법서의 중복 정의 제거 |
| [tools/local_original_session/data/m1/spell_display.json:4095](../../../tools/local_original_session/data/m1/spell_display.json#L4095) | 12종 source-backed action/gfx |
| [tools/local_original_session/data/m1/buff_descriptions.json:99](../../../tools/local_original_session/data/m1/buff_descriptions.json#L99) | 63/65/67/70 원 HUD 설명 |
| [tools/local_original_session/world_magic_stage8_tests.py:1](../../../tools/local_original_session/world_magic_stage8_tests.py#L1) | 신규16개 |
| [tools/local_original_session/world_magic_stage9_tests.py:1](../../../tools/local_original_session/world_magic_stage9_tests.py#L1) | 신규19개 |
| [tools/local_original_session/spellbook_learning_tests.py:61](../../../tools/local_original_session/spellbook_learning_tests.py#L61) | 학습 분류 집계41/8/18 |
| [tools/local_original_session/world_magic_tests.py:29](../../../tools/local_original_session/world_magic_tests.py#L29) | 지원 목록12종 반영 |
| [tools/local_original_session/world_companion_ats_spell_tests.py:35](../../../tools/local_original_session/world_companion_ats_spell_tests.py#L35) | 카탈로그 집계96→108, ATS 동작 불변 |
| [verify_ncg_waitonly.py:8150](../companion-bridge/verify_ncg_waitonly.py#L8150) | 기존 mage 시나리오에8/9단계·원 좌표 함수·수신 상태 렌더·캡처 추가. 좌표 guard 유지 |

