# 플레이어 법사 8단계 — 요청한 6종

2026-10-31. 고정 클라이언트 **26.09.29.2001** 기준. 학습·시전·현재 HP/MP/재료 소비·지속효과·저장/복원·텔레포트 replay를 기존 7단계 경로에 연결했다. 원문 확인, 단위 시험, 원본 클라이언트 화면 판정을 구별한다. 미확인을 전체 완료로 확대하지 않는다.

## 출처와 공통 정책

- **O키**: `tools/local_original_session/data/official/spells.json`의 해당 `official_id`, `work/official_data_refresh_20261028/raw/spell/<키>.json` 실제 보관 원문. 상세뿐 아니라 `official_list.consumables`의 HP0·재료0도 사용했다. URL·수집 시각·SHA256은 새 행의 `source_snapshot.official_source`와 `provenance`에 보존했다. 이번 작업은 새 HTTP 수집을 주장하지 않는다.
- **C키**: 고정 `work/source_game_data/native-dump-v1.jsonl` spell2273~2278행, 기존 `spell-ui-joins.json`, `spell-records.json`. 책은 공식 textbook ID/이름과 native item.f41 마법 키가 모두 일치한다. `source_snapshot`에 native 책 행과 CommonSpell 필드를 보존했다.
- **L**: `D:/SingleLineageRef/l1j-en-classic`, 기존 고정 HEAD `103e6f6c9dd83545959d8e87d3f59f8de1f40ef0`. 명시 이름·단계가 일치하는 `db/l1jdb_m10.sql:35677,35679~35682,35684`. 힐/피해식은 기존 `L1Magic.java:659~783`; 투명 시전 허용 목록은 `L1SkillUse.java:155~161`, 공격 제한은 `C_Attack.java:63~64`; NPC 부활 HP는 `L1SkillUse.java:1837~1841`이다. 이 자료의 서버 수치·계산식은 **LOCAL 참고 정책**이다.
- 표시 recipe는 위 L의 이름 대응 action/gfx와 고정 SPR/file alias·실제 SPX catalog 존재 자료를 사용한다. `4E31` 시전 동작, `4ED8` 대상 효과, `4F01` 기존 투명, `4E91` HUD/실제 남은 초를 재사용한다. 파일 존재·송신은 픽셀 성공과 다르다.

우선순위는 **공식 > 고정 클라이언트 > 이름·단계 일치 L1J**이다. 6종 모두 **법사32레벨** [각 O.learnings]. 학습 장소·캐릭터 성향 임계값은 **UNKNOWN**, 현재 **LOCAL 장소/성향 제한 없음**이다. 기존 `0960` 실제 책 소유·양수 수량 → 학습 제안 → inventory CAS/learning intent → 영속 magic save → `4E60` 목록을 사용한다. 배우기1회당 책1권, 이미 배웠거나 조건 불충족이면 소비0이다.

MP는 공식 기본값을 실제 차감하는 기존 **LOCAL 정책**이다. 실제 Classic INT/장비 MP 절감식은 UNKNOWN. 재사용의 공식 서버 값은 모두 UNKNOWN이며 아래 값은 L1J SQL 또는 기존1초 기본값을 사용한 LOCAL이다. client UI.delay는 입력 지연 자료로 별도 보존하며 서버 재사용의 증명으로 바꾸지 않는다.

| 키 / 이름 | 책 template [O,C] | MP / HP / 돌166 | LOCAL 재사용 | 학습·효과 범위 |
|---|---|---|---|---|
| 56 풀 힐 | 214 | 30 / 0 / 0 [O56,list,C56] | 0.5초 [L35677] | 구현함. 현재 PC/일반 NPC HP 회복, 언데드 반전/면역 |
| 58 블리자드 | 216 | 60 / 0 / 0 [O58,list,C58] | 1.5초 [L35679] | 구현함. 현재 가시 일반 몬스터 범위 피해 |
| 59 인비지블리티 | 217 | 45 / 25 / 1 [O59,C59] | 1초 [L0→기존 기본값] | **부분**. 투명·제한·저장/이동·디텍션. 정기 MP 소모 UNKNOWN |
| 60 리절렉션 | 218 | 50 / 0 / 0 [O60,list,C60] | 1초 [L0→기존 기본값] | **부분**. 일반 NPC/등록된 소유 동료·펫 부활. PC 수락 절차 없음 |
| 61 어스 퀘이크 | 524 | 40 / 0 / 0 [O61,list,C61] | 0.5초 [L35682] | 구현함. 술자 중심3칸 현재 일반 몬스터 피해 |
| 63 사일런스 | 610 | 30 / 0 / 2 [O63,C63] | 1초 [L0→기존 기본값] | **부분**. PC/NPC 마법 차단16초. 채팅 처리기 없음 |

## 효과·표시·화면 확인

| 마법 | 대상·수치·지속 / 출처 | action / gfx [L,고정 자원] | HUD [C] | 화면 확인 | 캡처 경로 |
|---|---|---|---|---|---|
| 풀 힐 | 10칸PC/NPC1인 [O56]. LOCAL `(12+min(10,magicBonus(INT)))d12`·lawful 배율·maxHP clamp [L35677,L1Magic]. 일반 NPC 실제 HP 회복, undead1 회복을 피해로 반전, undead3 면역 [기존 Heal,L1SkillUse] | 19 / 832 | 순간 효과, 가짜 지속 아이콘 없음 | 구현함. native 회복136·MP30, 금빛 효과 확인 | [1회 즉시](../runs/mage-stage8-20261031-01/mage-56-immediate.png) |
| 블리자드 | 술자 중심10칸 모든 적 [O58,C58 around]. 현재 가시 일반 NPC만 LOCAL `3d10+3`, 물4·기존 INT/SP/MR [L35679,L1Magic] | 18 / 757 | 순간 효과 | 구현함. native 피해43·MP60. 흰 냉기 입자 확인, 전체 눈보라 프레임은 미확인 | [1회 즉시](../runs/mage-stage8-20261031-01/mage-58-immediate.png) |
| 인비지블리티 | 술자, MP 유지 동안 [O59]. 공식 MP45/HP25/돌1. 기존 투명·디텍션을 쓰고 공격 제한, L1J 명시 이름 연결 시전 허용 목록을 LOCAL로 적용. MP0이면 해제. **주기/추가 MP량 근거가 없어 발명하지 않음** | 19 / 2510 + 기존4F01 | C59 양수 HUD K 없음. 무한/가짜 남은 시간 표시 없음 | 부분. MP45·HP25·돌1 및 투명 전후 확인. 실제 1회 저장 사본으로 4회 정상 재접속 후 투명 유지 확인. 유지비 미구현 | [시전 전](../runs/mage-stage8-20261031-01/mage-59-before.png), [시전 후](../runs/mage-stage8-20261031-01/mage-59-after.png), [재접속](../runs/mage-stage89-20261031-04/mage-world-entry.png) |
| 리절렉션 | 10칸PC/NPC 시체 [O60]. 일반 NPC는 보존된 현재 corpse/EntityRef·활성 spawn·출처 있는 cant_resurrect 허용값 확인. LOCAL maxHP/4 [L]. 동료/펫은 등록 훅으로 기존 실제 save/AI/부활 재사용 | 19 / 3944 + 기존 remove/spawn | 순간 효과 | 부분. 단위 통과. native 시전 화면 미확인: 1·6회 현재 시체 없음, 3회 좌표 근거 메타데이터 누락으로 입력 거절. 메타데이터 수정 후에도 시체를 얻지 못함. PC 수락 절차 미구현 | [3회 시체 관측](../runs/mage-stage8-20261031-03/mage-60-target-before.png) |
| 어스 퀘이크 | 술자 중심3칸 모든 적 [O61,C61 around]. 현재 일반 NPC LOCAL `6d10+40`, 땅1·기존 INT/SP/MR [L35682] | 18 / 1812 | 순간 효과 | 구현함. 균열·암석 효과, MP40, 3회 실제 피해150·처치 확인 | [3회 즉시](../runs/mage-stage8-20261031-03/mage-61-immediate.png) |
| 사일런스 | 10칸PC/NPC1인·16초 [O63]. 기존 silence 상태, LOCAL 일반 확률dice10 [L35684]. PC는 동료·몬스터 기능 없이도 시전 거절, NPC 두 마법 선택기 모두 MP 소비 전 차단. 물리 행동 유지 | 19 / 2177 | K824 / tooltip986, deadline-now ceil [native2278] | 부분. 3회 NPC 회색 바람·실제16초/MP30/돌2 확인. 6회 수신 렌더 fixture로 HUD·남은13초 확인. 채팅 처리기 없음 | [NPC 효과](../runs/mage-stage8-20261031-03/mage-63-immediate.png), [수신 HUD](../runs/mage-stage89-20261031-06/mage-received-1-tooltip.png) |

범위 피해는 실제 현재 map/LOS/EntityRef/HP·처치·보상 소유자를 유지한다. PvP·모든 적대/혈맹/안전지역 규칙은 UNKNOWN이며 현재 일반 몬스터 범위 밖을 구현했다고 주장하지 않는다. 마력의 돌은 착용 제외·양수 수량·단일 기존 kit CAS로 차감한다. 확률 실패/Counter Magic도 실제 시도 비용을 소비하고 거절은 소비하지 않는다.

NPC 부활은 같은 UID의 새 generation을 만들고 이전 corpse/respawn 시간을 취소해 기존 AI를 재시작한다. 실제 시체 remove/spawn으로 다시 표시한다. **LOCAL 동일 spawn의 두 번째 loot/EXP 없음**을 유지하고 원래 드롭/보상은 보존한다. 다음 정상 refill은 새 spawn 수명이다. PC 부활은 native Y/N·수락 응답 계약이 없어 **비용 차감 전에 거절**한다. 동료 코드를 플레이어 시전의 필수 의존성으로 만들지 않았다.

사일런스 등 유한 상태는 기존 magic effects 저장·실제 오프라인 경과 차감·텔레포트 deadline/HUD replay·만료/캔슬을 재사용한다. 인비지블리티는 기존 effects의 permanent 표시로 저장해 재접속/이동 뒤 투명을 재송신한다. MP0·디텍션·캔슬·사망으로 정리한다. 원 서버의 지속 MP 유지/오프라인 소모 동등성은 **미완**이다.

## 시험

신규 8/9단계 전용35개 통과: `_work/tmp/mage-stage89-unit-final-v2.log`(전체512개에 신규35개 포함). 클래스/레벨·실제 책 handler·중복 무소비·실제 HP/재료·범위 중심·투명/디텍션·NPC 부활·원 보상 보존·두 NPC 침묵 선택기·저장/이동/HUD/만료를 확인했다. 단위 fixture는 정상 로그인/원본 화면 PASS가 아니다.

최종 전체 **512개: 통과511, 실패0, 오류0, skip1**. 신규35개 포함. unittest 실행233.142초(러너 전체233.855초). 명령:

```powershell
$env:TEMP=(Resolve-Path _work/tmp).Path
$env:TMP=$env:TEMP
python _work/tmp/run_stage89_unit.py _work/tmp/mage-stage89-unit-final-v2.log
# 모듈 목록: _work/tmp/mage-stage89-test-modules.txt
# w133 28모듈 + world_magic_stage7/8/9 + spellbook_learning (stage6 중복 제거)
python -m py_compile work/local_original_session/companion-bridge/verify_ncg_waitonly.py
```

`launcher_tests`, `manual_move_commands_tests` 제외. `CompanionSocketTests` 1개는 `hunt_bot_companion.run`을 실행하므로 사용자 hunt_bot 금지에 따라 기존 skip을 유지한다. 다른 실제 broker loopback은 시험 사본에서 순차 실행한다. 1~7단계 별도 헤드리스/임의 전수 재검증은 하지 않는다.

## 헤드리스 실행 기록

구현·단위 시험 완료 후 최대6회, 같은 원인2회 실패면 해당 화면은 미확인으로 남긴다. 기존 owned non-input desktop/Job·GLFW callback injection만 사용한다. 매 실행 직전 LC/LC.guard·12000/14030 리스너가 없을 때만 시작하고, 점유 시2분 간격 최대20분 대기한다. 실행 중간 중단 없이 원 finally를 기다린다. 매 실행 후 게임 DLL 기준 해시 확인/필요 시 지정 원본으로 복원한다.

시험 사본 `_work/tmp/mage-stage89-20261031/profile-stage8`: 기존7단계 시험 사본을 읽어 복사했다. UID1만 시험 LV60/HP100(최대1000)/MP1500·시험 능력치로 준비했다. 기존 실제 UID allocator·kit append CAS로6종 책을 추가하고6개 돌을 재사용했다. 모든 대상 마법의 학습은 **로그인 전 fixture 초기값**이며 native 책 학습 증거로 부르지 않는다. NPC HP·확률·위치/소환을 강제하지 않았다. 시작 위치는7단계의 S32 검증된 golem spawn 중심을 재사용한다.

총6회/한도6회. 모든 실행 직전 LC/LC.guard와12000/14030 리스너0, 실행 후에도0이었다. 모두 wrapper 원 finally로 끝났으며 `FORCED_CLEANUP`, `normal_exit_verified=false`, logout `UNVERIFIED`다. 캡처 성공을 정상 종료 PASS로 확대하지 않는다. 게임 폴더 DLL은 매회 `1d1f60a03144f0214bee56c4a875d4444d51811649135a1eaab82ec2e2899f75`로 확인됐다. Capture 복원11. 사용자 저장은 읽어서 시험 사본으로 복사했으며 원본을 수정하지 않았다.

| 회차 / 실행 폴더 | 실제 판정 |
|---|---|
| 1 [mage-stage8-20261031-01](../runs/mage-stage8-20261031-01/result.json) | 56·61·58·59 native 시전. 63은 기존8칸 탐색으로 대상 부재, 60은 현재 시체 없음. 풀 힐136·블리자드43, 투명 전후 확인 |
| 2 [mage-stage9-20261031-02](../runs/mage-stage9-20261031-02/result.json) | 67·65·64·69·68 native 시전. 70 self PC는 클라이언트에서 거절되어 요청·비용 없음. 접근 대기 timer None 오류가 있었으나 독립 시전 결과는 별도 보존 |
| 3 [mage-stage8-20261031-03](../runs/mage-stage8-20261031-03/result.json) | 공식10칸 탐색·timer 수정. 63 실제16초, 61 피해150·처치. 60은 기존 corpse 좌표 함수를 썼으나 `coordinate_basis` 누락으로 입력 guard가 거절. guard를 유지하고 메타데이터만 수정 |
| 4 [mage-stage89-20261031-04](../runs/mage-stage89-20261031-04/result.json) | 1회 실제 저장 사본의 투명으로 정상 로그인·월드 진입 확인. 추가63/65/70은 로그인 전 수신 상태 렌더 fixture이며 적대 시전 PASS가 아니다. 지연 상태 아이콘3개는 보였으나 대기 timer 오류로 활성 툴팁 미확인. 포그는 같은 timer 원인2회 이후 재시도하지 않음 |
| 5 [mage-stage9-20261031-05](../runs/mage-stage9-20261031-05/result.json) | `COMPANION_TEST_KNIGHT_REQUIRED`: mage UID1이 기존 동료 시험 fixture의 knight 조건을 만족하지 못해 primary resume/로그인 전 실패. 조건을 우회하지 않음. 동료 동반 매스 텔레포트 native 미확인 |
| 6 [mage-stage89-20261031-06](../runs/mage-stage89-20261031-06/result.json) | 수신63/70 렌더 fixture 활성 툴팁13/15초 확인, 자연 만료 후61·69 native 시전. 포그 재시도 없음. 60은 현재 시체 없음. 접근 요청의 정확한 목적지 도착은 UNKNOWN. 최종6회에서 종료 |

재현 경로는 기존 `run_verify_fresh_capture.ps1 -RunName X -Steps mage_stage8` 또는 `mage_stage9 -SourceProfile <시험 사본> -Timeout N -CandidateBridge work/local_original_session/companion-bridge/own-login-bridge-companion-glfw-input.dll -CandidateSha256 00d646b40516a10a0f4978be156ce9dfb1f137c1f550eff34228e1762b05a67e`다. 환경 `VERIFY_INPUT_ROUTE=GLFW_CALLBACK_INJECTION`, `TEMP/TMP=_work/tmp`. 이번 입력·측정 자료와 wrapper 로그는 `_work/tmp/mage-stage89-20261031/`에 보존했다. 원본 UI 노드와 직접 확인한 캡처 좌표 및 기존 world/corpse 변환만 사용했다.

12권의 실제 학습 handler·CAS·저장·4E60 응답은 단위 시험으로 확인했다. 헤드리스는 미리 학습한 시험 사본을 사용했으므로 **각 책을 native UI에서 클릭해 학습하는 화면은 미확인**이다. 상태별 재접속·텔레포트 replay는 단위 확인이며, 화면 재접속은 인비지블리티만 직접 확인했다.

## UNKNOWN / 미완

- 인비지블리티 추가 MP량·주기·오프라인 유지비: UNKNOWN/미구현. 일정 시간을 발명하거나 무소모 완성으로 주장하지 않는다.
- PC 리절렉션 수락 절차/원 부활 응답: 미구현. 현재 일반 NPC와 등록된 소유 동료·펫만 지원한다.
- 사일런스 채팅 차단: 채팅 요청 처리기 부재로 UNKNOWN. 두 NPC 선택기와 PC 시전 차단만 구현했다.
- 공식 서버 재사용·동적 MP 절감·정확한 힐/피해/확률식·중첩/오프라인·PvP·관계/안전지역 정책: UNKNOWN. 문서의 LOCAL 수치는 원 서버 사실이 아니다.
- 순간 효과 모양·모든 아이콘/입력/원 프레임 동등성은 각 화면 판정 범위만 인정한다.

## 변경 파일·줄

아래 표에 최종 변경 파일과 진입 줄을 기록한다. 기존 카탈로그96행의 값은 변경하지 않고 요청12행만 추가했다. 사용자 저장·동료 classes/hotbar probe 수정과 커밋은 하지 않았다. 게임 DLL은 실행 wrapper의 후보 배치·원본 복원을 거쳤으며 코드 수정은 없다.


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

