# 법사 2단계 8종 대조·구현

2026-10-31. 고정 클라이언트 **26.09.29.2001**. [1단계](MAGE_SPELLS_STAGE1.md)의 원본 UI·owned non-input desktop·Job·원 스크린샷·서버 요청 경로를 재사용한다. 공식 수치, 고정 클라이언트 계약, L1J backend 참고와 실제 화면 확인을 구별한다. UNKNOWN은 완료/PASS가 아니다.

## 출처

- **O8~O15**: [큐어 포이즌](https://api-goats.plaync.com/linclassic/v2.0/game/spell/8?locale=ko-KR), [칠 터치](https://api-goats.plaync.com/linclassic/v2.0/game/spell/9?locale=ko-KR), [커스:포이즌](https://api-goats.plaync.com/linclassic/v2.0/game/spell/10?locale=ko-KR), [인챈트 웨폰](https://api-goats.plaync.com/linclassic/v2.0/game/spell/11?locale=ko-KR), [디텍션](https://api-goats.plaync.com/linclassic/v2.0/game/spell/12?locale=ko-KR), [디크리즈 웨이트](https://api-goats.plaync.com/linclassic/v2.0/game/spell/13?locale=ko-KR), [파이어 애로우](https://api-goats.plaync.com/linclassic/v2.0/game/spell/14?locale=ko-KR), [스탈락](https://api-goats.plaync.com/linclassic/v2.0/game/spell/15?locale=ko-KR). 사용 원문은 [공식 수집본](../../../tools/local_original_session/data/official/spells.json)의 `spells[official_id=k].official`, `official_list`, `source`다. 2026-10-28 수집 원본 경로·해시를 그대로 보존한다. 이번 web.open 8/10/13 재조회는 접근 실패였으며 새 HTTP 수집 성공을 주장하지 않는다.
- **Ck**: [플레이어 카탈로그](../../../tools/local_original_session/data/m3/player_spells.json)의 `classic_key.value=k`, `source_snapshot.client_ui`, `client_common_spell_raw_fields`. [고정 native dump](../../source_game_data/native-dump-v1.jsonl), [UI join](../../all_table_semantics/spell_token/spell-ui-joins.json), [spell records](../../all_table_semantics/spell_token/spell-records.json)를 연결한다. 마법창 icon과 HUD K는 별개다.
- **Dk**: [표시 자료](../../../tools/local_original_session/data/m1/spell_display.json) `spells[key=k]`. 이름을 대조한 L1J action/castgfx와 고정 SPR·catalog 파일 존재의 참고 recipe다. 존재 확인은 렌더 성공이 아니다.
- **L**: `D:/SingleLineageRef/l1j-en-classic`, 보관 HEAD `103e6f6c9dd83545959d8e87d3f59f8de1f40ef0`. `db/l1jdb_m10.sql:35629-35636`의 CurePoison/ChillTouch/Poison/EnchantWeapon/Detection/DecreaseWeight/FireArrow/Stalac 8행. `L1SkillUse.java:1783-1784,1944-1945,3034-3043,2049-2050,1894-1900,3061-3063`, `L1DamagePoison.java:69-121,148-159`, `L1ItemInstance.java:1075-1097`, `L1PcInstance.java:1686-1696`, `L1Magic.java:659-783`. 각 카탈로그 `effect_source_refs`에 이름 연결·사용 범위가 남아 있다.
- **P**: [기존 마법 wire](PLAYER_MAGIC_EVIDENCE.md), [CommonSpell·HUD](BUFF_GAMETIME_EVIDENCE.md). 4EE6 원 요청 → 실제 handler → 4E31 동작·4ED8 효과. 4E91은 실제 deadline 잔여 초를 ceil한다. 독 4F05·투명 4F04는 기존 `world_magic_status_feedback_tests.py` 및 [고정 소비 계약](../runs/status-feedback-contract-20261030)의 근거다.

우선순위는 **공식 > 고정 클라이언트 데이터 > L1J 이름 일치 참고**다. L1J 수식·LOCAL 대상 subset·거리 metric을 공식 Classic 사실로 승격하지 않는다.

## 학습·소비·재사용

8종 공통 학습 레벨은 **법사8 / 군주20 / 요정16** [각 O `/learnings`]. 기사는 허용하지 않는다. 학습 장소·캐릭터 성향 임계값은 **UNKNOWN**이다. Lawful/Chaotic/Neutral은 주문 분류 [각 O `/alginName`, C 설명]이며 학습 제한으로 추측하지 않았다.

| key / 이름 | 학습 조건 | 책 template·소비 | MP / HP / 시전 재료 | 재사용 |
|---|---|---|---|---|
| 8 큐어 포이즌 | 공통 클래스·레벨 [O8], 장소·성향 임계 UNKNOWN | 184, 1권 [O8 `/textbook`, 기존 CAS] | 8 / 0 / 없음 [O8 detail·list] | 공식 UNKNOWN, LOCAL 공유1초, L SQL35629=0ms |
| 9 칠 터치 | 공통 [O9], 장소·성향 임계 UNKNOWN | 185, 1권 [O9, CAS] | 9 / 0 / 없음 [O9 detail·list] | 공식 UNKNOWN, LOCAL1초, L35630=0ms |
| 10 커스:포이즌 | 공통 [O10], 장소·성향 임계 UNKNOWN | 186, 1권 [O10, CAS] | 10 / 0 / 없음 [O10 detail·list itemCount0]. L 마력의 돌1개는 채택 안 함 | 공식 UNKNOWN, LOCAL1초, L35631=0ms. C10 delay500은 서버 reuse 증거 아님 |
| 11 인챈트 웨폰 | 공통 [O11], 장소·성향 임계 UNKNOWN | 187, 1권 [O11, CAS] | 20 / 0 / 없음 [O11 detail·list] | 공식 UNKNOWN, LOCAL1초, L35632=0ms |
| 12 디텍션 | 공통 [O12], 장소·성향 임계 UNKNOWN | 188, 1권 [O12, CAS] | 8 / 0 / 없음 [O12 detail·list] | 공식 UNKNOWN, LOCAL1초, L35633=0ms |
| 13 디크리즈 웨이트 | 공통 [O13], 장소·성향 임계 UNKNOWN | 599, 1권 [O13, CAS] | 10 / 0 / 없음 [O13 detail·list]. L HP50은 채택 안 함 | 공식 UNKNOWN, LOCAL1초, L35634=0ms |
| 14 파이어 애로우 | 공통 [O14], 장소·성향 임계 UNKNOWN | 517, 1권 [O14, CAS] | 3 / 0 / 없음 [O14 detail·list] | 공식 UNKNOWN, LOCAL1초, L35635=0ms |
| 15 스탈락 | 공통 [O15], 장소·성향 임계 UNKNOWN | 518, 1권 [O15, CAS] | 3 / 0 / 없음 [O15 detail·list] | 공식 UNKNOWN, LOCAL1초, L35636=0ms |

책은 학습 때만 1권 소비한다. 이미 배움·클래스·레벨 거절은 소비하지 않는다. 학습 제안 → 기존 인벤토리 CAS/intent → 영속 학습 → 4E60, 중간 실패 forward recovery를 유지했다. MP는 공식 기본값 차감이며 INT·장비에 따른 실제 Classic 최종 비용 감소는 UNKNOWN이다. 0ms L1J 참고를 Classic 무재사용으로 해석하지 않았다.

## 대상·효과·표시·유지

공통 변경: **8~15도 표시 실험 OFF와 무관하게 4E31/4ED8 송신**. 피해가 실제 적용되는 9/14/15는 f4=1, counter/실패는0. 원본 애니메이션 속도·DLL은 바꾸지 않았다.

| key / 이름 | 대상·효과 수치·지속 | 시전 4E31 / 효과 4ED8 | 버프·디버프 아이콘·시간 | 저장·이동 / 이미 맞던 것 | UNKNOWN·미완 | 화면 확인 |
|---|---|---|---|---|---|---|
| 8 큐어 포이즌 | 10칸 PC/NPC1인, 독 치료, 순간 [O8,C8]. 현재 PC·일반 몬스터의 damage poison과 ticker 제거 [L] | action19 / gfx871 [D8] | 독 4F05를 현재 Stone 상태와 함께 false로 송신. **수정:** 본인 독 K5319 HUD도 해독·외부 해독·만료 시 제거 [P] | 기존 PC 저장 poison 삭제·NPC EntityRef 상태 제거, 이후 tick 피해 없음 | 모든 독 종류·별도 펫/동료 소유자 해독·Classic 픽셀 동등성 UNKNOWN | 확인 진행 중 |
| 9 칠 터치 | 2칸 PC/NPC1인·HP 흡수·순간 [O9,C9]. LOCAL 기초2d10+10·물 attr4 및 INT/SP/MR 식 [L35630,L1Magic]. 회복=실제 제거 HP×1.0, maxHP clamp [L1SkillUse] | action18 / gfx252 [D9], **피격 f4 연결** | 순간, 지속 HUD 없음 [C9,P] | 기존 실제 NPC 피해·처치·보상·1회 MP 차감·흡수 회복. 자원은 기존 vitals 저장 | 공식 피해/흡수식, PvP·펫/동료 대상, 비행·전체 프레임 동등성 UNKNOWN | 확인 진행 중 |
| 10 커스:포이즌 | 3칸 PC/NPC1인, HP 독30초 [O10,C10]. LOCAL3초당5HP [L1DamagePoison], 감염확률1.0은 기존 LOCAL subset | action19 / gfx745 [D10], 지속 독4F05 [P] | 현재 대상 poison 표시. **추가:** 본인 PC 독 authority→spell10/K5319와 실제 잔여 시간. 적 몬스터 타이머를 술자 HUD에 붙이지 않음 [P] | 기존 현재 몬스터 EntityRef·독 tick·처치/정리. PC 독은 저장/재접속 offline 경과 차감·과거 tick 재생 없음; 텔레포트 deadline 유지 | 플레이어의 PC 대상 시전, 공식 성공 확률·면역·tick수치, 적 몬스터 native 잔여시간 UI, NPC 독 cold save는 UNKNOWN/미지원 | 확인 진행 중 |
| 11 인챈트 웨폰 | 술자의 소지 무기, 추가 타격+2·1800초 [O11,C11]. LOCAL 현재 착용 무기UID 바인딩 [L1ItemInstance] | action19 / gfx747 [D11] | spell11/K5265·실제 deadline 잔여 [C11,P] | 기존 실제 melee/ranged damage consumer+2. 무기 교체 중지·같은 UID 재착용 잔여 재개. 저장/재접속/텔레포트 유지 | native 소지 무기 선택 전체 계약, 공식 다른 무기 버프 중첩, 전체 시각 동등성 UNKNOWN | 확인 진행 중 |
| 12 디텍션 | 18칸 숨어있는 대상·순간 [O12,C12]. **수정:** 기존 화면 모양/최대17칸 필터 대신18칸 적용. 거리 metric은 LOCAL Chebyshev | action19 / gfx749 [D12] | 순간 HUD 없음. 기존 투명4F04 false를 현재 actor 관찰자에게 송신 [P] | 기존 현재 PC/NPC 투명 deadline 제거·PC 저장, 재접속 시 해제 유지. NPC EntityRef 수명 유지 | 공식 거리 metric·벽 경계, 묻힘/변장/함정 등 다른 숨김 종류, 실제 투명→노출 화면 UNKNOWN | 확인 진행 중 |
| 13 디크리즈 웨이트 | 술자·무게 감소1800초 [O13,C13]. 수치 공식 UNKNOWN. LOCAL 한도+180 [L1PcInstance1686-1696], 개별 아이템 무게는 유지 | action19 / gfx2170 [D13] | spell13/K757·실제 deadline 잔여 [C13,P] | 기존 코어 실제 carried/capacity/gauge·일반 마법 무게 제한이 소비. 만료 재계산·저장/재접속/텔레포트 유지 | Classic 정확 감소량·regen/교환/획득 등 모든 별도 무게 소비자의 일치 UNKNOWN | 확인 진행 중 |
| 14 파이어 애로우 | 10칸 PC/NPC1인, 작은 불 피해·순간 [O14,C14]. LOCAL2d10+10·불 attr2, INT/SP/MR 식 [L35635,L1Magic] | action18 / gfx1583 [D14], **피격 f4 연결** | 순간 HUD 없음 [C14,P] | 기존 현재 NPC 실제 HP·처치/보상·1회MP 차감·자원 저장 | 공식 피해식·PvP·펫/동료 대상, 투사체 비행/연결 폭발 recipe·속도 동등성 UNKNOWN | 확인 진행 중 |
| 15 스탈락 | 10칸 PC/NPC1인, 바위 송곳 피해·순간 [O15,C15]. LOCAL2d10+10·땅 attr1, INT/SP/MR 식 [L35636,L1Magic] | action18 / gfx1801 [D15], **피격 f4 연결** | 순간 HUD 없음 [C15,P] | 기존 현재 NPC 실제 HP·처치/보상·1회MP 차감·자원 저장 | 공식 피해식·PvP·펫/동료 대상, 전체 피격·효과 프레임 동등성 UNKNOWN | 확인 진행 중 |

현재 일반 몬스터/PC subset을 공식 대상 전체 완료로 확대하지 않는다. 버프 재접속은 실제 offline 경과를 빼고, 텔레포트는 기존 deadline을 유지한다. 순간 효과는 버프를 새로 만들어 복원하지 않는다. 동료가 없는 실제 WorldView에서도 8종 admit/effect/display를 단위 시험했으며, 동료 AI/ATS 경로는 기존 코드를 유지했다.

## FullWorld 1회와 실행 경계

0번 전용 실행은 [mage-stage2-fullworld-20261031](../runs/mage-stage2-fullworld-20261031). `SL_EXPERIMENT_MAP=2`, `SL_EXPERIMENT_M5=1`. **COMPANION_TEST_KNIGHT_REQUIRED로 실패**, 프로세스 수명14.593초. 초기화 성공·오류 없음으로 표시하지 않는다. 법사 사본에 동료 초기화가 적용됐다. 0번 전용 실행은 반복하지 않았다.

허용된 마법 실행03의 같은 FullWorld 구성에서 부가 관측한 초기화 시작은 **2026-10-31 00:55:01 +0900**, `world_bridge.initialize` **4.562초**다. 던전 교체 맵 실제 등록 slot 합계 **8,121**, map13 **145**; handler/hook/magic 오류 `[]`다. 별도 [던전 population 자료](../../../tools/local_original_session/data/m6/dungeon_population.json) 자체는 **8,086**, map13 **145**다. 8,121에는 별도 보스 등의 추가 등록이 포함되므로 8,086 자료와 같은 모집단으로 쓰지 않는다. 소켓 listen 전체 준비 시간과 initialize 시간도 구별한다.

## 단위 시험

```powershell
python -X utf8 -B -m unittest tools.local_original_session.spellbook_learning_tests tools.local_original_session.world_magic_tests tools.local_original_session.world_magic_status_feedback_tests tools.local_original_session.world_companion_support_spell_tests tools.local_original_session.world_companion_magic_tests tools.local_original_session.world_undead_damage_tests tools.local_original_session.world_combat_requests_tests
```

**177/177, 72.081초, OK**. 원로그 `_work/tmp/mage-stage2-20261031/unit-tests.log`. `launcher_tests`, `manual_move_commands_tests`, hunt_bot은 실행하지 않았다. 기존 no-companion 표시 시험을8~15로 확장하고, 실제 피격 f4·디텍션18/19칸 경계·독 HUD 추가/외부해독 제거를 기존 시험에 포함했다. 실제 화면 판정은 이 결과로 대체하지 않는다.

## 헤드리스 원문·캡처

허용량은 0번1회 + 마법 최대4회이며 실패도 횟수에 포함한다. 실행 직전 LC 계열 프로세스와12000/14030 리스너0을 확인했다. DLL은 1단계의 검증된 기존 wrapper 임시 설치/원복만 사용했고 수정·빌드하지 않았다. 사용 candidate는 `own-login-bridge-companion-glfw-input.dll`, SHA256 `00d646b40516a10a0f4978be156ce9dfb1f137c1f550eff34228e1762b05a67e`다. 사용자 저장·manual-user-play·기존 실패/부분 저장은 수정하지 않았다.

| 실행 | 시작 사본·구성 | 실제 판정·캡처·정리 |
|---|---|---|
| [01](../runs/mage-stage2-20261031-01) | `_work/tmp/mage-stage2-20261031/profile`, 학습8~15·독/투명 초기 fixture, FullWorld | import 뒤 feature 제외가 캐시 목록에 반영되지 않아 COMPANION_TEST_KNIGHT_REQUIRED. 시전0, 캡처0. FORCED_CLEANUP, 정상 Quit/로그아웃 미검증 |
| [02](../runs/mage-stage2-20261031-02) | 같은 입력의 새 사본, companion 제외를 import 앞으로 이동, FullWorld | Land 도달 뒤 UI_OPEN_DELIVERED_CURRENT_GENERATION_REQUIRED. 마법0·캡처0. 시험 법사 사망/성장 저장30→29·EXP손실 보존. FORCED_CLEANUP |
| [03](../runs/mage-stage2-20261031-03) | `profile-cure` 새 사본, 초기 투명 제거·독 fixture 유지, FullWorld | 같은 인벤토리 수명 경계에서 중단. 마법0·캡처0. 실제 사망/레벨손실 보존. 위 FullWorld 초기화·등록 수만 OBSERVED. FORCED_CLEANUP |
| [04](../runs/mage-stage2-20261031-04) | `profile-final`, 1단계 기본 map0/M5 OFF. 학습8~15·독 초기 fixture | 진행 중 |

02/03은 초기 투명 유무를 분리했지만 같은 준비 실패가 재발했다. 투명을 원인으로 확정하지 않는다. 사망과 성장 손실은 해당 시험 사본의 실제 결과이며 되감지 않았다. 마지막04는 기본 맵으로 분리했다. 사전 learned·독 fixture는 native 책 학습·커스 감염 PASS가 아니다. 1단계 가벼운 인벤토리의 실제 UID·소모품 수량·무기65549·장비 anchor를 이어받았으며 무게 guard를 완화하지 않았다.

각 run의 `result.json`, `verify-shots.json`, `mage-stage2-frames.json`, `boundary-path.txt`와 해당 validation-profile의 `execution.log`, `_work/tmp/mage-stage2-20261031/headlessN-wrapper.log`를 보존한다. 원 Capture 폴더는 wrapper가 원복하고 생성 파일은 해당 run의 `native-capture-produced`에 보존한다.
