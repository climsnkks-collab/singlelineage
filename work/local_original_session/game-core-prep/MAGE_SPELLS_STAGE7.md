# 법사 7단계 8종 대조·구현

2026-10-31. 고정 비교 클라이언트 **26.09.29.2001**. 공식 > 고정 클라이언트 > 이름·단계 일치 L1J 순서를 따른다. 아래 LOCAL은 원본 서버 동등성을 뜻하지 않으며, 단위 시험·원문 확인·원본 화면 확인을 구별한다. `data/companion/classes.json`, 동료 AI/ATS 데이터, 지상 아이템 프레임/이름 표시 파일은 수정하지 않았다. 커밋 없음.

## 출처

- **O48~O55**: [공식 수집본](../../../tools/local_original_session/data/official/spells.json)의 `official_id48~55`, 각 `source.raw_path` 원문. 2026-10-28 수집 `work/official_data_refresh_20261028/raw/spell/48.json`~`55.json`. `player_spells.json`의 `source_snapshot.official_source`와 provenance에 URL·시각·SHA256을 보존했다. 이번에 새 HTTP 성공을 주장하지 않는다.
- **Ck**: [고정 UI join](../../all_table_semantics/spell_token/spell-ui-joins.json), [CommonSpell 행](../../all_table_semantics/spell_token/spell-records.json), [native dump](../../source_game_data/native-dump-v1.jsonl). native 책 행1124~1128,1326,1376~1377의 item.f41과 공식 textbook.id/name를 동시에 확인했다. 마법창 아이콘 번호와 HUD K, tooltip 참조번호는 별개다.
- **Dk**: [표시 자료](../../../tools/local_original_session/data/m1/spell_display.json). 명시 영어 이름/단계 SQL 대응 → action/castgfx → 고정 SPR/file alias 및 실제 SPX catalog 크기·해시 존재를 확인한 recipe. 파일 존재는 픽셀 성공이 아니다.
- **L**: `D:/SingleLineageRef/l1j-en-classic`, 보존 HEAD `103e6f6c9dd83545959d8e87d3f59f8de1f40ef0`; `db/l1jdb_m10.sql:35669~35676`. `L1Magic.java:275~387,659~783`, `L1SkillUse.java:163~183,555~565,2066~2088`, `AcceleratorChecker.java:49,170~179`, `HpRegeneration.java:150`, `skill/executor/L1Berserkers.java`, `L1Disease.java`. 공식과 다르면 아래 표처럼 공식 우선이다.
- **P**: [기존 마법 wire](PLAYER_MAGIC_EVIDENCE.md), [HUD/남은 시간](BUFF_GAMETIME_EVIDENCE.md). 정상 `4EE6` decoder/handler, `4E31` 시전, `4ED8` 효과, `4E91` 아이콘·ceil 남은 초, 기존 `4E5B` 이동/공격 축을 사용한다.

## 학습·소비·재사용

8종 모두 **법사28레벨** [각 O의 learnings]이며 다른 클래스는 거절한다. 책을 한 번 배울 때1권, 시전은 책을 재소비하지 않는다. 기존 `0960` 소유/수량 확인 → 학습 제안 → kit CAS/learning intent → 영속 magic save → `4E60` 목록을 사용한다. 조건 불충족·이미 배움·미구현은 책을 소비하지 않는다.

**그레이터 헤이스트의 장소·성향 학습 제한은 추가하지 않았다.** O53은 법사28만 제시하고 C53은 시전 target=self/MP60만 제시한다. L1J의 사원/추가 클래스 조건을 Classic 조건으로 승격하지 않았다. 장소/성향 조건은 **UNKNOWN**, 현재 동작은 **LOCAL 장소 제한 없음**이다. 라우풀 신전이든 다른 장소든 같은 클래스·레벨·소유 책 검사를 따른다. 마법의 성향 분류는 캐릭터 성향 임계값과 다르다.

| key / 이름 | 책 template | MP / HP / 시전 촉매 | 재사용 | 학습·구현 상태 |
|---|---|---|---|---|
| 48 힐 올 | 209 [O48,C48] | 35 / 0 / 없음 [O48,공식 list,C48] | LOCAL0.5초 [L35669], 공식 UNKNOWN | **부분**. 학습·시전·등록된 실제 파티 PC 회복. 현재 native PC 파티 구성원 생산자 없음 |
| 49 아이스 랜스 | 210 [O49,C49] | 30 / 0 / 없음 [O49,list,C49] | LOCAL1초 [L35670], 공식 UNKNOWN | **부분**. 일반 NPC 피해·확률 빙결/행동 차단. PvP 피해·빙결 피해 면역/원 케이지 동등성 미완 |
| 50 서먼 몬스터 | 211 [O50,C50] | 원문50 / 0 / 돌166×3 [O50,C50] | 후보 LOCAL1초 [L35671], 미지원 소비 없음 | **미구현**. 책/자료/recipe 등록, 학습·시전은 `MAGIC_EFFECT_UNSUPPORTED` |
| 51 홀리 워크 | 212 [O51,C51] | 15 / 0 / 없음 [O51,list,C51] | LOCAL1초 [L0ms fallback], 공식 UNKNOWN | 구현함 — 이동 축 가속, 공격 축 유지 |
| 52 토네이도 | 213 [O52,C52] | 45 / 0 / 없음 [O52,list,C52] | LOCAL1초 [L35673], 공식 UNKNOWN | **부분**. 술자 중심3칸 현재 일반 몬스터 범위 피해. PvP/실제 적대·파티 규칙 없음 |
| 53 그레이터 헤이스트 | 523 [O53,C53] | 60 / 0 / 없음 [O53,list,C53] | LOCAL1초 [L0ms fallback], 공식 UNKNOWN | 구현함 — 2,400초, 기존 가속 상태/HUD/저장 공유 |
| 54 버서커스 | 607 [O54,C54] | 30 / 0 / 없음 [O54,list,C54] | LOCAL1초 [L0ms fallback], 공식 UNKNOWN | 구현함 — 공식 근접+5·AC+10·HP 자연 회복 차단 |
| 55 디지즈 | 608 [O55,C55] | 30 / 0 / 돌166×2 [O55,C55] | LOCAL1초 [L0ms fallback], 공식 UNKNOWN | 구현함 — 공식 근접 명중-4·AC+8, 현재 PC/NPC 소비 경로 |

MP는 공식 **기본값 차감 LOCAL 정책**이며 실제 Classic INT/장비 최종 MP 감소는 UNKNOWN이다. 공식 list의 HP0을 우선해 L1J 힐 올HP30·서먼HP30을 복사하지 않았다. 마력의 돌은 기존 고정 template166·양수 수량·착용 제외·kit CAS를 사용한다.

책8종은 기존 정의·가격/원출처를 보존해 `spellbooks.json`으로 이동했다. 아이스 랜스210은 `misc.json`, 나머지7개는 `drops_misc.json`에 있던 행이다. 전체 로드 ID 중복을 없앴고 원 아이템 가격·UID를 새로 만들지 않았다. `stage_support`는7단계8행/지원7/서먼1미지원으로 갱신했다.

## 대상·효과·표시·유지

| key / 이름 | 대상·효과·지속시간 | action / gfx [D,L] | HUD K / tooltip [C] | 실제 소비·저장/이동 | 화면 확인 | 캡처 경로 |
|---|---|---|---|---|---|---|
| 48 힐 올 | 술자 제외10칸 모든 파티원 [O48]. LOCAL `(10+min(10,magicBonus(INT)))d8`·lawful·회복량 clamp [L35669,L1Magic715~735] | 19 / 759 | 순간 HUD 없음 | 등록 `party_members`의 실제 현재 PC만 회복·개별 HP writer·Water Life 소비. 술자/근처 타인/동료를 임의 파티원으로 만들지 않음. 제공자 없으면 LOCAL 파티원0, 시전 비용·표시만 정상 소비 | **부분 확인**: 회색 회전 고리·시전/MP35 소비. 현재 파티0명, 회복0이므로 파티 회복 화면 미확인 | [mage-48-immediate.png](../runs/mage-stage7-20261031-03/mage-48-immediate.png) |
| 49 아이스 랜스 | 10칸1인 [O49]. 현재 일반 NPC 물 피해 LOCAL`6d5+50`와 INT/SP/MR, 7단계이므로 기존 L1J critical 제외. 독립 LOCAL 확률dice9·빙결8초 [C49 f6; L은16초] | 18 / 756 | C49 양수 K 없음, 가짜 HUD 없음 | HP 소비 후 살아 있는 동일 EntityRef에 frozen 적용. AI/행동 차단·기존 Stone/block 표시,8초 만료/캔슬 정리. Erase의 이번 시도 MR을 피해/빙결 양쪽에 적용. 원 얼음 케이지/피해 면역 동등성 UNKNOWN | **부분 확인**: 시전·대상 피해109/MP30 소비. `freeze_applied=False`로 빙결 화면 미확인; 04는 대상 없음 | [mage-49-immediate.png](../runs/mage-stage7-20261031-03/mage-49-immediate.png) / [mage-49-after.png](../runs/mage-stage7-20261031-03/mage-49-after.png) |
| 50 서먼 몬스터 | CHA/레벨로 복수 몬스터·3,600초 [O50]. 공식 target 미제공, C50 self | 후보19 / 2510 | 양수 K 없음 | 크리에이트 좀비와 같은 플레이어 하수인 소유/명령·펫 비용·영속/3,600초 종료 계약 미완. 소환 NPC·소비·성공을 위조하지 않음 | **미구현으로 제외** | 없음 |
| 51 홀리 워크 | 술자 이동 속도 향상64초 [O51]. LOCAL 이동 interval×0.745 [L AcceleratorChecker49,172~173], 공격 축 불변 | 19 / 3936 | 1561 / 817, 실제 남은 초 | 기존 magic effects 저장·실제 오프라인 경과 차감·텔레포트 deadline/HUD replay. 기존 가속과 이동 축만 합성.6단계 Haste 동작은 유지 | **확인**: 이동 가속 아이콘·한글 설명·58초. 짧은 별도 gfx 모양은 미확인 | [mage-51-tooltip.png](../runs/mage-stage7-20261031-03/mage-51-tooltip.png) |
| 52 토네이도 | 술자 중심3칸 모든 적 [O52,C52 around]. LOCAL 현재 가시 일반 NPC만 `5d10+20` 바람 피해 [L35673], map/LOS/실 EntityRef 유지 | 18 / 758 | 순간 HUD 없음 | 대상 UID 없는 원 around 요청으로 술자 중심 선정. 현재 몬스터 HP·피격·처치·보상 재사용. Counter/Erase는 실제 대상별 소비 | **확인**: 술자 위치 큰 회색 회오리·대상 피해37/처치·MP45 소비. 범위 순간 HUD 없음 | [mage-52-immediate.png](../runs/mage-stage7-20261031-03/mage-52-immediate.png) |
| 53 그레이터 헤이스트 | 술자 이동/공격 가속2,400초 [O53]. rate0.745는 기존 물약 LOCAL | 19 / 3104 | 물약 catalog223 / K481 / tooltip849 공유 | 같은 `PcState.buffs['haste']`·scheduler·물약 저장/HUD. 공식2,400을 보존하는 cap2,400;6단계 기본 cap1,800은 그대로. 재접속 복원 시2,400을1,800으로 자르지 않음. 저장 중 일시정지는 기존 물약 LOCAL 정책 | **확인**: 공유 가속 아이콘·39분54초, 재접속 후38분43초 보존. Native 책 학습은 미확인 | [mage-53-tooltip.png](../runs/mage-stage7-20261031-03/mage-53-tooltip.png) / [mage-restored-buff-0-tooltip.png](../runs/mage-stage7-20261031-04/mage-restored-buff-0-tooltip.png) |
| 54 버서커스 | 10칸 술자/파티/혈맹1인·근접 대미지+5·AC+10·HP 자연 회복 불가·1,200초 [O54] | 19 / 3943 | 1556 / 965, 실제 남은 초 | 실제 근접 profile·AC와 자연 HP/음식 회복 차단, MP/물약·힐 회복은 유지. L1J의 추가 명중+2는 공식 미제공이라 추가하지 않음. 기존 PC 수신 버프/저장/이동/만료/캔슬 재사용; 관계 규칙은 기존 LOCAL | **확인**: 시전·AC7→17·아이콘, 재접속 후 근접+5/AC+10/HP 자연 회복 불가 설명·16분6초. 짧은 gfx 모양 미확인 | [mage-54-buff-closed.png](../runs/mage-stage7-20261031-03/mage-54-buff-closed.png) / [mage-restored-buff-1-tooltip.png](../runs/mage-stage7-20261031-04/mage-restored-buff-1-tooltip.png) |
| 55 디지즈 | 2칸PC/NPC1인·근접 명중-4·AC+8·30초 [O55]. LOCAL 일반 확률dice10 [L35676] | 19 / 2230 | 760 / 695, 실제 남은 초 | PC 실제 AC/근접 명중·상태 프레임. NPC 물리 명중 입력-4와 플레이어의 해당 NPC 방어 AC+8 소비. L1J 대미지-6/AC12를 복사하지 않음. PC 저장/복원/이동·리무브/캔슬·만료, NPC EntityRef 수명 | **부분 확인**: 시전 자세·MP30/돌2 소비. 실제 확률 실패로 디버프/수신 아이콘 화면 미확인; 04는 대상 없음 | [mage-55-immediate.png](../runs/mage-stage7-20261031-03/mage-55-immediate.png) |

`4ED8`은 기존 대상 위치 효과 recipe이며 투사체 비행/원 픽셀 동등성을 단정하지 않는다. 이번7단계도 표시 OFF 실험과 관계없이 정상 시전 action/gfx를 송신한다. 순간 마법에 가짜 지속 아이콘을 만들지 않았다. CommonSpell.f7의 tooltip 참조를 `buff_descriptions.json`에 추가했다.

## 미완·UNKNOWN

- 힐 올의 **native PC 파티 구성/가입/탈퇴 → `party_members` 생산자**가 없다. 등록 접점의 실제 HP 회복은 단위 시험으로 확인했지만 현재 단독 게임에서 파티 회복까지 완료했다고 주장하지 않는다.
- 서먼 몬스터는 기존 NPC 소환·영속 펫을 플레이어 레벨/CHA별 하수인으로 즉시 대체할 수 없다. 소환 프로필 이름 대응·주인/명령·펫 비용·3,600초 저장·종료·재접속/텔레포트 소유 서비스가 필요하다. 책/MP/돌은 소비하지 않는다.
- 아이스 랜스8초는 고정 client f6을 채택한 LOCAL 서버 지속시간이다. 공식 순간 표기는 피해의 지속이며 정확한 원 서버 freeze 확률/시간은 UNKNOWN. 원 얼음 케이지, 전체 피해 면역, PvP 및 별도 펫/동료 HP 소유자 피해는 미구현이다.
- 공식 재사용·동적 MP 감소·정확한 피해/힐/확률식·원 속도/중첩/오프라인 정책·혈맹/파티 관계/안전지역 정책은 UNKNOWN. 표의 참고값은 명시 LOCAL이다.
- 별도 동료 버서커스 수신의 전체 HP 자연 회복 차단까지 이번 범위에서 구현한 것은 아니다. 플레이어 PC/일반 NPC 소비와 기존 AI/ATS 보존이 검증 범위다.

## 단위 시험

최종 전체 **339개/110.497초/실패0·오류0·스킵0**. 로그 [_work/tmp/stage7-unit-verified.log](../../../_work/tmp/stage7-unit-verified.log). 새7단계 전용14개를 포함하며 아이스 랜스 Erase MR을 피해/빙결 양쪽에 보존하는 시험도 통과했다. 이전338개 통과 로그도 보존했다. 단위 시험은 native 화면을 대신하지 않는다.

재현 명령(launcher/manual_move_commands 시험 제외):

```powershell
$env:TEMP=(Resolve-Path _work/tmp).Path
$env:TMP=$env:TEMP
$modules = @(
 'spellbook_learning','world_magic','world_magic_status_feedback',
 'world_companion_support_spell','world_companion_magic','world_undead_damage',
 'world_combat_requests','world_maps','world_item_effects',
 'monster_skills_cancel','monster_skills','monster_skills_support',
 'monster_skills_phase2','world_polymorph','world_consumable_restore',
 'game_data','world_m3_data','world_magic_stage6','world_magic_stage7'
) | ForEach-Object { 'tools.local_original_session.' + $_ + '_tests' }
python -m unittest @modules
python -m py_compile work/local_original_session/companion-bridge/verify_ncg_waitonly.py
```

기대값 변경은 새 공식7단계 행/표시 recipe/책 행 수를 반영한 것이다. misc의 기존 미지원 아이스 랜스 책210을 지원 책으로 이동했으므로 전체 book 분류는 supported29/conditional8/deferred24다. 이전1~5단계 수치/행동의 기대값을 바꿔 새 기능을 통과시키지 않았다.

## 헤드리스 기록 — 4/4회 완료

시나리오 `mage_stage7`, GLFW candidate SHA256 `00d646b40516a10a0f4978be156ce9dfb1f137c1f550eff34228e1762b05a67e`. 매 실행 전 LC/LC.guard·12000/14030 리스너0을 확인했다. 중간 중단 없이 wrapper finally를 기다렸다. 네 실행 모두 LC_LEFT0·캡처 설정 복원·DLL 기준 해시 `1d1f60a03144f0214bee56c4a875d4444d51811649135a1eaab82ec2e2899f75`를 확인했다. 수동 복원은 필요 없었다. 네 실행 모두 **FORCED_CLEANUP / 정상 로그아웃 UNVERIFIED**이며 화면 성공과 구별한다.

- 시작 사본: `_work/tmp/mage-stage7-20261031/profile`. 기존6단계 가벼운 시험 사본에서 기존 stone-golem spawn `m1_field_62050` source rect 중심·S32 can_stand를 확인해 `(map0,32570,32848)`을 정했다. NPC HP/소환/이동/확률은 강제하지 않았다. 실제 캐릭터 선택·월드 진입 후 현재 대상과 기존 검증된 grid 투영으로 클릭한다.
- 책523 한 권은 기존 UidAllocator·kit append CAS·장비 restore로 추가했고 첫 두 실행은 **53 미학습**으로 시작했다. 나머지 학습은 로그인 전 시험 초기값이며 native 책 학습 증거가 아니다.
- [01](../runs/mage-stage7-20261031-01): 실제 가방 열기 reply는 RETURNED/opened=true였지만 harness gate가 REPLIED를 실패로 분류해 책 단계 SKIPPED. 닫기 노드 `Root.Bt_Close`도 유일하지 않아 가방이 마법창을 가렸다. 미측정 마법 좌표 입력을 거절했고 시전0. reply 해석을 실제 관측대로 수정했다.
- [02](../runs/mage-stage7-20261031-02): 책 resolver의 잘못된 `broker.inventory_frame` 참조로 AttributeError. 기존 `_inventory_current_frame`으로 수정했지만 가방이 마법창을 가리는 문제가 두 번 반복되어 이 native 학습 경로는 **UNKNOWN**으로 남겼다. 원 캡처·실패 로그를 보존했고 같은 경로를 세 번째 실행하지 않았다. 제품 학습 handler의 책523 소비·영속 학습은 단위 시험 통과지만 UI 학습 성공으로 주장하지 않는다.
- [03](../runs/mage-stage7-20261031-03): `_work/tmp/mage-stage7-20261031/profile-casts`에서 **53 학습 완료 시험 초기값**을 명시하고 시전만 분리 검증했다. 실제7페이지 캡처에서 좌표를 측정한 뒤 `48,51,53,54,55,49,52` 순서로 모두 실제 시전 이벤트를 관측했다. 48 파티0/회복0, 51 이동 가속64초, 53 가속2,400초, 54 AC7→17, 55 확률 실패, 49 피해109/빙결False, 52 피해37/처치였다. errors는 모두 빈 목록이다. 마법별 PNG를 직접 열어 위 표처럼 판정했다.
- [04](../runs/mage-stage7-20261031-04): 03의 **실제 실행 후 저장**을 SourceProfile로 재사용했다. 시작HP174/MP81·AC17, 가속/버서커스가 복원됐다. 아이콘0/1을 실제 hover해 가속38분43초(1,800초 초과 보존) 및 버서커스16분6초·정상 한글 설명을 직접 확인했다. 55/49 재시도는 `NO_CURRENT_VISIBLE_IN_RANGE_MONSTER`로 대상 입력 전 UNKNOWN/SKIPPED. 확률/피격 성공을 강제하지 않았고 한도에 도달해 추가 실행하지 않았다.

03의 `mage-54-tooltip.png`는 첫 아이콘인 가속을 hover한 사진이다. 버서커스 설명 증거는 **04의 `mage-restored-buff-1-tooltip.png`**이며 서로 혼동하지 않는다. 49 빙결·55 디버프 수신 성공·실제 파티 HP 회복·원 짧은 gfx 모양·텔레포트 화면은 **미확인**이다. 저장/복원·텔레포트 replay·성공/실패 효과 소비는 단위 시험 범위에서 통과했다.

실행 명령의 재현 형태(각 실행 직전 프로세스/리스너0 확인):

```powershell
$env:VERIFY_INPUT_ROUTE='GLFW_CALLBACK_INJECTION'
$env:TEMP=(Resolve-Path _work/tmp).Path; $env:TMP=$env:TEMP
# VERIFY_MAGE_POINTS는 현재 실행 캡처에서 측정해 준비한 JSON이다.
work/local_original_session/companion-bridge/run_verify_fresh_capture.ps1 `
 -RunName mage-stage7-20261031-03 -Steps mage_stage7 `
 -SourceProfile _work/tmp/mage-stage7-20261031/profile-casts -Timeout 480 `
 -CandidateBridge work/local_original_session/companion-bridge/own-login-bridge-companion-glfw-input.dll `
 -CandidateSha256 00d646b40516a10a0f4978be156ce9dfb1f137c1f550eff34228e1762b05a67e
```

## 수정 파일·위치

아래 위치는 최종 소스에서 조회한 줄이며 기존 다른 작업의 dirty 파일을 이 작업의 변경으로 포함하지 않는다.

| 파일:줄 | 변경 요지 |
|---|---|
| [data/m3/player_spells.json:22278](../../../tools/local_original_session/data/m3/player_spells.json#L22278) | 7단계8행·값별 출처·공식 우선 수치·LOCAL/UNKNOWN·stage_support |
| [data/m1/items_ext/spellbooks.json:1206](../../../tools/local_original_session/data/m1/items_ext/spellbooks.json#L1206) | 기존 책8종 ID/가격 보존·학습 조건·미지원 서먼 소비 거절 |
| [data/m1/items_ext/drops_misc.json:1](../../../tools/local_original_session/data/m1/items_ext/drops_misc.json#L1) | 지원 마법서 기존 정의를 전용 테이블로 이동 |
| [data/m1/items_ext/misc.json:1](../../../tools/local_original_session/data/m1/items_ext/misc.json#L1) | 아이스 랜스 책210을 전용 테이블로 이동 |
| [data/m1/spell_display.json:3594](../../../tools/local_original_session/data/m1/spell_display.json#L3594) | 고정 자원 존재를 확인한 이름 대응 action/gfx recipe |
| [data/m1/buff_descriptions.json:81](../../../tools/local_original_session/data/m1/buff_descriptions.json#L81) | CommonSpell.f7 tooltip 참조51/53/54/55.6단계41/46/47도 화면 버그 수정 |
| [world_magic.py:407](../../../tools/local_original_session/world_magic.py#L407) | 버서커스 근접+5·AC+10, 디지즈 AC+8 |
| [world_magic_status.py:1](../../../tools/local_original_session/world_magic_status.py#L1) | frozen/holy_walk/disease 저장·상태/이동 축·NPC 물리 입력 |
| [world_feature_magic.py:415](../../../tools/local_original_session/world_feature_magic.py#L415) | 자연 HP 회복 차단·디지즈 실제 근접/방어 소비·등록형 파티 회복 |
| [world_feature_magic.py:1411](../../../tools/local_original_session/world_feature_magic.py#L1411) | 빙결 MR/확률·상태 적용, 술자 중심 범위 요청·토네이도·힐 올·홀리 워크·이펙트 |
| [world_item_effects.py:418](../../../tools/local_original_session/world_item_effects.py#L418) | 2,400초 가속 복원 보존·HP 음식 회복 차단 |
| [world_monster_skills.py:306](../../../tools/local_original_session/world_monster_skills.py#L306) | NPC 특수 물리 공격 디지즈 명중 입력 소비 |
| [world_magic_stage7_tests.py:15](../../../tools/local_original_session/world_magic_stage7_tests.py#L15) | 새14개 시험: 실제 책 handler·비용·HP·상태·빙결·범위·저장·HUD·기존 효과 보존 |
| [spellbook_learning_tests.py:246](../../../tools/local_original_session/spellbook_learning_tests.py#L246) | 새 지원 책 행 수·분류 기대값 |
| [world_magic_tests.py:1](../../../tools/local_original_session/world_magic_tests.py#L1) | 7단계 지원/미지원 key·표시 행 집합 기대값 |
| [verify_ncg_waitonly.py:8144](../companion-bridge/verify_ncg_waitonly.py#L8144) | 단계6/7 순차 시전·현재 캡처 실측 좌표·독립 실패 후 계속·버프 hover·책 UI 준비 |

UNKNOWN 요약: 공식 재사용/최종 MP/수식/확률·중첩·오프라인/관계 규칙, 실제 파티 생산자, 서먼 하수인 소유 서비스, 빙결 케이지/피해 면역·PvP/별도 HP 소유자, native 책523 학습 및 표에 표시한 화면 미확인 항목. 런타임 구현 뒤에는 데이터/문서·harness만 수정했으며 전체339개 통과 소스와 게임 실행 소스가 일치한다.

화면 판정 한계: 별도 형상을 미확인으로 남긴 짧은 gfx는 즉시/후속 정지 캡처에서 자세·주변 그림과 분리해 판정하지 못했다. 원 자원 존재·서버 효과 프레임 송신 시험을 픽셀 확인으로 대체하지 않았다.
