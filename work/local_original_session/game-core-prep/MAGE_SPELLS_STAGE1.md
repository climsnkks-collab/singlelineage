# 법사 1단계 8종 대조·구현

2026-10-30. 비교 클라이언트는 **26.09.29.2001**로 고정한다. 2단계 이상은 이번 수정 대상이 아니다. 공식 수치, 고정 클라이언트 입력·표시 계약, 이름을 연결한 L1J backend 참고를 구별한다. 이 문서의 UNKNOWN은 완료/PASS가 아니다. 단위 시험과 실제 화면 판정은 서로 대체하지 않는다.

## 출처와 표 읽는 법

- **O0~O7**: [공식 힐](https://api-goats.plaync.com/linclassic/v2.0/game/spell/0?locale=ko-KR), [라이트](https://api-goats.plaync.com/linclassic/v2.0/game/spell/1?locale=ko-KR), [실드](https://api-goats.plaync.com/linclassic/v2.0/game/spell/2?locale=ko-KR), [에너지 볼트](https://api-goats.plaync.com/linclassic/v2.0/game/spell/3?locale=ko-KR), [텔레포트](https://api-goats.plaync.com/linclassic/v2.0/game/spell/4?locale=ko-KR), [아이스 대거](https://api-goats.plaync.com/linclassic/v2.0/game/spell/5?locale=ko-KR), [윈드 커터](https://api-goats.plaync.com/linclassic/v2.0/game/spell/6?locale=ko-KR), [홀리 웨폰](https://api-goats.plaync.com/linclassic/v2.0/game/spell/7?locale=ko-KR). 실제 사용 원문은 [공식 수집본](../../../tools/local_original_session/data/official/spells.json)의 `spells[official_id=N].official` 및 각 `source`의 raw 경로·수집일·해시다. 2026-10-26 수집본을 사용했다. 이번 web.open의 0/1/7 재조회는 접근 실패였으며 새 HTTP 성공을 주장하지 않는다.
- **Ck**: [플레이어 카탈로그](../../../tools/local_original_session/data/m3/player_spells.json)의 `spells[classic_key.value=k].source_snapshot.client_ui`와 `client_common_spell_raw_fields`. 원본 [UI join](../../all_table_semantics/spell_token/spell-ui-joins.json), [spell records](../../all_table_semantics/spell_token/spell-records.json), [native dump](../../source_game_data/native-dump-v1.jsonl). CommonSpell HUD 키는 마법창 아이콘 번호와 별개다.
- **Dk**: [표시 자료](../../../tools/local_original_session/data/m1/spell_display.json)의 `spells[key=k]`. L1J `skills`의 action/castgfx를 이름·key+1로 연결하고 고정 SPR·catalog 존재를 대조한 **참고 recipe**다. 파일 존재는 화면 성공 증거가 아니다. `EBolt`↔에너지 볼트, `WindShuriken`↔윈드 커터는 보관된 이름 대응이며 임의의 동일 번호만으로 다른 행을 채택하지 않았다.
- **L**: `D:/SingleLineageRef/l1j-en-classic`, 보관 HEAD `103e6f6c9dd83545959d8e87d3f59f8de1f40ef0`. `db/l1jdb_m10.sql:35621-35628`의 8행, `L1Magic.java:659-783`의 피해·힐, `L1ItemInstance.java:1089-1093`의 Holy Weapon, `L1Attack.java:1144-1148`의 언데드 추가, `L1Character.java:1112-1142`의 lightSize. 공식과 다르면 공식 우선: 실드 MP2/1200초, 라이트7200초, 텔레포트 MP5, 아이스/윈드 MP3을 유지했다.
- **P**: [기존 마법 wire 근거](PLAYER_MAGIC_EVIDENCE.md), [HUD 근거](BUFF_GAMETIME_EVIDENCE.md), [REA163 광원 검토](../../local_server_rea_20261016/run163_light_illumination/main-review.json). `4EE6` 시전 → 실제 handler → `4E31` 시전 동작, `4ED8` 대상 효과. `4E91`은 서버 권위의 남은 초를 ceil하여 송신한다.

우선순위는 **공식 > 고정 클라이언트 데이터 > L1J 이름 대응 참고**다. L1J 수식·밝기·대상 분류를 공식 Classic 수치로 승격하지 않는다.

## 학습·소비·재사용

아래 학습 레벨은 각 O의 `learnings`: **법사4 / 군주10 / 기사50 / 요정8**이다. 8종 모두 동일하며 다른 클래스는 허용하지 않는다. `alginName`/클라이언트 설명의 Lawful·Neutral은 **마법 분류**이고 캐릭터 성향의 학습 임계값이라는 근거가 아니다.

| key / 이름 | 클래스·레벨 | 장소 / 성향 학습 조건 | 책 template·소비 | MP / HP / 시전 재료 | 재사용 |
|---|---|---|---|---|---|
| 0 힐 | 위 공통 [O0] | UNKNOWN / UNKNOWN. 주문 분류 Lawful [O0,C0] | 164, 1권 [O0 `/textbook`, 기존 book CAS] | 4 [O0] / 0 [C0] / 없음 [L SQL35621] | 공식 UNKNOWN. 기존 LOCAL 공유1초, L1J 후보10ms [카탈로그0 `/cooldown_ms`] |
| 1 라이트 | 위 공통 [O1] | UNKNOWN / UNKNOWN. Neutral [O1,C1] | 180, 1권 [O1, CAS] | 4 [O1] / 0 [C1] / 없음 [L35622] | 공식 UNKNOWN. LOCAL1초, L 후보10ms [카탈로그1] |
| 2 실드 | 위 공통 [O2] | UNKNOWN / UNKNOWN. Neutral [O2,C2] | 181, 1권 [O2, CAS] | 2 [O2] / 0 [C2] / 없음 [L35623] | 공식 UNKNOWN. LOCAL1초, L 후보10ms [카탈로그2] |
| 3 에너지 볼트 | 위 공통 [O3] | UNKNOWN / UNKNOWN. Neutral [O3,C3] | 182, 1권 [O3, CAS] | 3 [O3] / 0 [C3] / 없음 [L35624] | 공식 UNKNOWN. LOCAL1초, L 후보10ms [카탈로그3] |
| 4 텔레포트 | 위 공통 [O4] | UNKNOWN / UNKNOWN. Neutral [O4,C4] | 183, 1권 [O4, CAS] | 5 [O4] / 0 [C4] / 없음 [L35625] | 공식 UNKNOWN. LOCAL1초, L 후보10ms [카탈로그4] |
| 5 아이스 대거 | 위 공통 [O5] | UNKNOWN / UNKNOWN. Neutral [O5,C5] | 515, 1권 [O5, CAS] | 3 [O5] / 0 [C5] / 없음 [L35626] | 공식 UNKNOWN. LOCAL1초, L 후보10ms [카탈로그5] |
| 6 윈드 커터 | 위 공통 [O6] | UNKNOWN / UNKNOWN. Neutral [O6,C6] | 516, 1권 [O6, CAS] | 3 [O6] / 0 [C6] / 없음 [L35627] | 공식 UNKNOWN. LOCAL1초, L 후보10ms [카탈로그6] |
| 7 홀리 웨폰 | 위 공통 [O7] | UNKNOWN / UNKNOWN. Neutral [O7,C7] | 598, 1권 [O7, CAS] | 10 [O7] / 0 [C7] / 없음 [L35628] | 공식 UNKNOWN. LOCAL1초, L 후보0ms [카탈로그7; 공식0초라는 뜻 아님] |

책은 학습에만 소비하고 시전 때 재소비하지 않는다. 이미 배움·클래스·레벨 거절은 책을 소비하지 않는다. 학습 제안 → 인벤토리 CAS/learning intent → 영속 학습 → `4E60` 목록을 재사용하며 중간 실패의 forward recovery를 유지한다. 장소/성향을 추측해서 새 제한을 만들지 않았다. L1J `C_ItemUSe.java:3413-3499`는 성당/카오틱 사원과 darkelf를 포함하므로 그 좌표·추가 클래스를 Classic 사실로 복사하지 않았다.

MP는 현재 공식 **기본값** 차감 정책이다. 실제 Classic 장비/초기 INT 등의 비용 감소는 UNKNOWN. L1J `L1SkillUse.java:1028-1087`에서는 1단계 INT tier 감소가 없지만 힐 전용 장비 반감·originalMagicConsumeReduction이 별도로 있으므로 기본 MP와 동적 최종 소모를 혼동하지 않는다.

## 대상·효과·표시·유지

모든 수치 뒤 O/C/L/D/P는 위 출처를 가리킨다. 지속효과 재접속은 저장 시 남은 시간에서 실제 오프라인 경과를 빼며 텔레포트는 기존 deadline을 유지한다.

| key / 이름 | 대상·효과 수치·지속 | 시전 4E31 / 효과 4ED8 | 4E91 아이콘·남은 시간 | 실제 효과·저장/이동 | UNKNOWN·미완 | 화면 확인 |
|---|---|---|---|---|---|---|
| 0 힐 | 10칸 PC/NPC1인, HP 조금 회복·언데드 피해, 순간 [O0,C0]. LOCAL `(2+min(10,magicBonus(INT)))d4`, lawful>0 배율 `1+lawful/32768`, Java trunc [L1Magic715-735] | action19 / gfx744 [D0]. 자기 UID도 수신. 언데드 피해 성공에 f4=1 [P] | 순간 마법, 지속 HUD 없음 [C0,P] | 기존 PC HP clamp·MP 차감. **추가:** 현재 spawn의 일반 NPC HP clamp, undead1 피해·undead3 면역 [L1SkillUse3022-3035]. 처치·EXP는 기존 소유 경로 | 공식 정확 회복/피해식, 동료/펫 등 별도 NPC HP 소유자의 플레이어 힐 접점·화면 동등성 UNKNOWN | 05: **시전자 자세·푸른 입자 효과 확인**. immediate에는 안 보였으나 후속 after에서 보임. 서버 HP+14/MP-4. 순간 HUD 해당 없음. [after](../runs/mage-stage1-20261031-05/mage-0-after.png) |
| 1 라이트 | 술자, 주위를 밝힘,7200초 [O1,C1]. LOCAL strength14 [L1Character1119] | action19 / gfx2510 [D1] | C1 CommonSpell에 검증된 양수 HUD K 없음. 임의 아이콘을 만들지 않음 [P] | **추가:** 정상4F01 f1=u64 UID,f2=i32=14 → 원 LightComponent/렌더 소비 [REA163]. 만료·사망·캔슬=0으로 원 기본값 복원. 재접속/텔레포트/새 관찰자에 재송신, 남은 deadline 유지 | 공식 밝기/반경/색·실제 픽셀, Light의 원 HUD 존재·타이머 UNKNOWN. 0은 완전소등이 아니라 native 기본값 fallback [REA163] | 06: **마법창 닫힘**. 시전자 자세는 확인, 라이트 단독 HUD 아이콘은 안 보임. 동일 map0/격자·지면 영역의 시전 전후 비교에서 **뚜렷한 밝기 변화는 확인 못함**. [우상단](../runs/mage-stage1-20261031-06/mage-1-buff-closed-region.png), [같은 영역 전후](../runs/mage-stage1-20261031-06/mage-1-light-same-region.png) |
| 2 실드 | 술자,AC-2,1200초 [O2,C2] | action19 / gfx221 [D2] | spell2 / K485, 실제 deadline-now [C2,P] | 기존 스탯 AC·저장/복원·만료·텔레포트 HUD replay 유지. **수정:** 표시 OFF 설정에도 1단계 action/gfx 송신 | Classic 원 서버 송신 순서·픽셀 동등성 UNKNOWN | 06: **창이 닫힌 우상단 실드 아이콘 확인**, AC7→5. 07 재접속 뒤 원 hover 툴팁 **실드: AC-2 / 남은시간13분22초** 확인. 시전 자세 O, 별도 gfx 전체 형태는 미판정. [아이콘](../runs/mage-stage1-20261031-06/mage-2-buff-closed-region.png), [복원·시간](../runs/mage-stage1-20261031-07/mage-restored-shield-tooltip-region.png) |
| 3 에너지 볼트 | 10칸 PC/NPC1인, 작은 피해·순간 [O3,C3]. LOCAL 기초 `1d10+8`,속성16 [L35624], INT/SP·MR·법사 critical 수식 [L1Magic659-783] | action18 / gfx167 [D3]. **수정:** 실제 피해 시 f4=1; counter 흡수 시0 [P] | 순간, 지속 HUD 없음 [C3,P] | 기존 현재 몬스터 HP/피격·사망·보상 경로, 1회 MP 차감 유지 | 공식 피해식, PvP·동료/펫 대상, 투사체 비행·연결 폭발 recipe·픽셀 동등성 UNKNOWN. 현재4ED8은 대상 위치 효과 | 05: **시전자 자세·대상 쪽 청색 광탄 확인**. 비행 궤적/속도·피격 모션 미확인(대상 일부 화면 밖). 서버 피해23/MP-3. [immediate](../runs/mage-stage1-20261031-05/mage-3-immediate.png) |
| 4 텔레포트 | 술자,임의 위치 또는 조종 반지 기억 장소,순간 [O4,C4] | action19 / gfx169, 자기 Actor 재생성 **뒤** 송신 [D4,P] | 순간, 지속 HUD 없음 [C4,P] | 기존 LOCAL 같은 map passable 후보·반경200 [카탈로그4/L1Location128-219], 이동·저장·interest 갱신. **추가:** 라이트4F01 재송신. 실드/홀리 HUD는 기존 remaining replay | 반지+마법의 native 기억 선택 계약과 전체 map 허용/목적지 분포 UNKNOWN. 도착 이펙트 외 출발 이펙트·화면 동등성 UNKNOWN | 05: **지형 전환·도착 백색 원형 효과 확인**. 몸은 효과에 가려 자세 미판정. 라이트/실드 서버 deadline 유지, HUD 미확인. MP-5. [immediate](../runs/mage-stage1-20261031-05/mage-4-immediate.png) |
| 5 아이스 대거 | 10칸 PC/NPC1인,작은 물 피해·순간 [O5,C5]. LOCAL 기초 `1d10+10`,속성4 [L35626], 나머지 L 피해식 | action18 / gfx1797 [D5]. 실제 피해 f4=1, counter시0 [P] | 순간, 지속 HUD 없음 [C5,P] | 기존 현재 몬스터 피해·사망·보상·MP 유지. **수정:** OFF 설정에서도 시전/효과·피격 표시 송신 | 공식 피해식, PvP·별도 NPC 소유자, 비행·연결 효과·픽셀 동등성 UNKNOWN | 06: **창 닫은 뒤 대상 클릭·시전 성공**. 시전자 자세·난쟁이 옆 청색 얼음 광탄 확인. 피해24/MP311→308. 독립 피격 중간 모션·비행 속도 미확인. [immediate](../runs/mage-stage1-20261031-06/mage-5-immediate.png) |
| 6 윈드 커터 | 10칸 PC/NPC1인,작은 바람 피해·순간 [O6,C6]. LOCAL 기초 `1d10+10`,속성8 [L35627], 나머지 L 피해식 | action18 / gfx1799 [D6]. 실제 피해 f4=1, counter시0 [P] | 순간, 지속 HUD 없음 [C6,P] | 기존 현재 몬스터 피해·사망·보상·MP 유지. **수정:** OFF 설정에서도 시전/효과·피격 표시 송신 | 공식 피해식, PvP·별도 NPC 소유자, 비행·연결 효과·픽셀 동등성 UNKNOWN | 06: **창 닫은 뒤 시전 성공**. 시전자 자세·대상 쪽 흰 곡선 빛 일부와 쓰러짐/드롭 라벨 확인. 피해6(남은 HP6 처치)/MP311→308. 라벨이 효과 일부를 가려 전체 gfx·피격 중간 프레임은 미판정. [immediate](../runs/mage-stage1-20261031-06/mage-6-immediate.png) |
| 7 홀리 웨폰 | 10칸 PC1인,근거리 명중+1·추가 피해+1·언데드 추가,1200초 [O7,C7] | action19 / gfx2165 [D7] | spell7 / K777, 실제 deadline-now [C7,P] | 기존 대상 PC/등록 buff recipient·선택 무기 UID 바인딩, 바꾸면 중지·같은 UID 재착용 시 잔여 재개. **추가:** melee undead1/3에 별도+1 [L1ItemInstance1091,L1Attack1144-1148], 기존 일반+1과 한 번씩 합산. 저장/재접속/텔레포트 유지 | 공식 언데드 추가량·분류 조건, 동료 자신의 별도 공격 프로필의 동일 추가량, 시각 동등성 UNKNOWN | 06 후보0은 시전 미관측. 07 기존 좌표 함수의 **후보2(+0,+12)로 자기 대상 시전 성공**, MP311→301·무기UID65549 바인딩. 팔 든 자세·옅은 흰 세로빛 일부 확인. **닫힌 우상단 홀리 웨폰+실드 아이콘 확인**. 전체 gfx 형태/속도·홀리 자체 시간 툴팁은 미판정. [immediate](../runs/mage-stage1-20261031-07/mage-7-immediate.png), [아이콘](../runs/mage-stage1-20261031-07/mage-7-buff-closed-region.png) |



공식 대상 문자열의 모든 PC/NPC를 현재 몬스터·PC subset 통과만으로 완료라고 하지 않는다. 사거리의 Chebyshev·현재 map·가시성·static LOS는 기존 LOCAL backend 정책이며 공식 벽/문 경계 동등성은 UNKNOWN이다.

## 이번 변경과 검증

- `world_feature_magic.py`: 1단계8종 action/gfx를 표시 실험 OFF와 무관하게 송신. 피해가 실제 적용되는 경우만 피격 f4=1. 기존 counter/실패에서 피격을 만들지 않음. 라이트4F01 수명/복원/관찰자 replay, 일반 몬스터 힐·언데드 분기, 선택 무기 holy modifier.
- `world_combat.py`: `Weapon.holy_damage`를 실제 melee 대미지 소비에 연결. 다른 무기·화살·동료 기존 기본 프로필의 default는0. 원래 은무기 추가 피해와 별도 합산.
- `data/m3/player_spells.json`: key0/1/7에 구현 범위·출처를 직접 기록. 공식 값과 다른 단계의 지원 표시는 승격하지 않음.
- `world_magic_tests.py`: 기존 fixture를 재사용. 동료 runtime이 없는 실제 WorldView의 플레이어 시전, 광원 deadline/복원/만료, NPC 힐/언데드 분기, holy 실제 피해/무기/거리 종류/만료를 확인.
- `verify_ncg_waitonly.py`: `mage_stage1` 시나리오만 추가. 원 마법창 → 원 private input → 기존 handler → 마법별 캡처. 기존 좌표 함수만 사용. 시험 전 복사한 프로필의 UID1은 법사30/MP314·기존 소유 무기65549·학습0~7이며 **native 책 학습 PASS가 아니다**. 최초3회 마감 때 입력 helper install 누락과 첫 실패 이후 중단을 교정했고04/05에서 실행 확인했다. 06/07에는 원 마법창을 선택 뒤 닫고 숨김을 읽은 뒤 대상/캡처로 진행하도록 고쳤다. 선택 key 목록·기존 대상 후보 선택·기존 HUD hover 방법만 인자로 분리했다.

단위 시험: 수정 전 지정5모듈 **155/155**. 변경 후 지정5모듈 + 변경된 combat 관련 `world_undead_damage_tests`·`world_combat_requests_tests` **177/177**, 최종66.216초. 마지막 서버 수정은 비활성 광원의 replay가 기존 NPC/PC 기본 조명을 덮지 않게 하고, 새 NPC 힐·피격 분기를 1단계로 한정했다. `launcher_tests`·`manual_move_commands_tests`와 hunt_bot은 실행하지 않았다.

```powershell
python -X utf8 -B -m unittest tools.local_original_session.spellbook_learning_tests tools.local_original_session.world_magic_tests tools.local_original_session.world_magic_status_feedback_tests tools.local_original_session.world_companion_support_spell_tests tools.local_original_session.world_companion_magic_tests tools.local_original_session.world_undead_damage_tests tools.local_original_session.world_combat_requests_tests
```

원로그: `_work/tmp/mage-stage1/baseline-tests.log`, `unit-tests.log`(시험 fixture 오류2 및 존재하지 않는 모듈 지정1,166개 중 errors3), `fixture-fixes.log`·`fixture-fixes2.log`, `unit-final.log`(중간177 성공/68.656초), `unit-final-scoped.log`(최종177 성공/66.216초), `final-admission-check.log`(동일 admission 조건을 기존 거절 검사에 합친 뒤 해당 NPC 힐1/1,0.761초). 과거 실패를 삭제하거나 최종 결과로 덮지 않았다.

요청별 허용 범위로 최초3회(01~03), 후속2회(04~05), 창 가림 교정 후2회(06~07)를 사용했다. 이번06~07의2회 한도에 도달한 뒤 더 실행하지 않았다. 각 실행 전 LC 계열 프로세스와12000/14030 리스너가 없음을 확인했다. DLL은 기존 wrapper의 임시 설치/원복 경로만 사용했으며 바이너리 수정·빌드·커밋은 하지 않았다. 사용자 원 저장·manual-user-play는 수정하지 않았다.

| 실행 폴더 | 판정 | 캡처·정리 |
|---|---|---|
| `runs/mage-stage1-20261030-01` | 로그인 전 시험 장비의 빈 slots로 `EQUIPMENT_SLOT_SCHEMA`. 시전 UNRUN | 캡처 없음. owned Job 강제 정리, LC_LEFT0·포트 정리·DLL slot/Capture 원복. 원 실패 result.json 보존 |
| `runs/mage-stage1-20261030-02` | 동료 모듈 미설치 법사 로그인·월드 진입. UI open 결과 RETURNED 파일은 있었으나 시나리오가 pending의 busy 검사에서 수거하지 못함. TEST_DURATION, steps incomplete | 캡처 없음. 정리 FORCED_CLEANUP, 정상 Quit/로그아웃 미검증. LC_LEFT0·slot/Capture 원복 |
| `runs/mage-stage1-20261030-03` | 마법창8종 아이콘 확인. key0 첫 입력은 당시 좌표 파일 미준비로 거절. 첫 대상 입력 `INPUT_GLFW_COMPLETION_TIMEOUT`; 이후 `INPUT_GLFW_REQUEST_PENDING` 거절. **시전 이벤트0/8, MP314 유지, 화면 마법 PASS0/8** | 원 PNG22개. `mage-spell-window.png`, `mage-0-after.png`~`mage-7-after.png` 직접 contact sheet/확대 확인: 시전 이펙트·버프·이동 확인 안 됨. done=true/프로세스 exit0은 시나리오 종료일 뿐 마법 PASS 아님. FORCED_CLEANUP·정상 Quit/로그아웃 미검증. LC_LEFT0·slot/Capture 원복 |

실행은 모두 `companion-bridge/run_verify_fresh_capture.ps1 -Steps mage_stage1`, `SourceProfile=../../../_work/tmp/mage-stage1/profile`, 고정 candidate `own-login-bridge-companion-glfw-input.dll` SHA256 `00d646b40516a10a0f4978be156ce9dfb1f137c1f550eff34228e1762b05a67e`를 사용했다. 각 원 실행 폴더의 `result.json`, `verify-shots.json`, boundary-path.txt 및 시험 사본 execution.log를 보존했다. wrapper 로그는 `_work/tmp/mage-stage1/headless1-wrapper.log`~`headless3-wrapper.log`다.

세 번째 실행의 owned boundary에는 `glfw-input.request.json`만 있고 `companion-request-*.json`(install)과 GLFW 결과 파일이 없었다. 기존 `world_feature_companion_bridge._bridge_attempt`는 map/model 등의 생산자가 있을 때 처음 install을 보내며, DLL `companion_bridge_nopatch.hpp:990-991,1507-1508`는 install에서 GLFW Start, 기존 timer에서 Tick을 수행한다. **동료를 끈 시나리오가 입력 helper install까지 생략한 것이 정적 원인으로 판단된다.** 현재 시나리오는 기존 DirectoryHost의 install만 명시해 AI·동료 map을 만들지 않고 입력 helper를 준비하도록 고쳤다. 좌표는 위 현재 캡처에서 직접 잰 8점을 동일 window bounds에서만 재사용하고 기존 first-failure 중단을 사용한다. 최초 마감 당시 이 교정은 import/구문·0~7 순서만 확인했고 UNRUN이었다. 후속04/05의 install 성공 및 입력 완료는 아래 결과로 구분한다.

그 교정은 서버 마법 학습·소비·피해를 직접 호출하거나 준비/성공을 강제하지 않는다. 최종 서버 code의 단위 결과와 세 번째 실행 code의 native 결과를 합쳐 정식 PASS로 만들지 않는다. 남은 최소 관측은 **교정된 입력 helper 초기화가 끝난 동일 시나리오에서 원 시전 요청 및8종 효과를 실제 캡처로 확인하는 것**이다.

현재 정식 결론: **잔여5/6/7 각 시전과 화면 표시를 관측했고 실드·홀리 웨폰 HUD를 확인했다. 라이트의 가시적 밝기 변화와 전체 원본 동등성은 미판정**. 05/06/07의 서로 다른 실행·시험 사본을 한 번의8종 완주 PASS로 합산하지 않는다. 학습은 기존 단위 근거이며 이번 native 책 학습을 주장하지 않는다.


## 추가 헤드리스 04~05 (2026-10-31)

두 실행 모두 직전 LC 계열 프로세스 및12000/14030 리스너0을 확인했다. 같은 고정 DLL·기존 owned non-input desktop/Job·fresh capture wrapper를 재사용했다. **입력 시간 초과는 재발하지 않았다.** 사용자 저장과 이전 실패 사본은 변경하지 않았다.

| 실행 폴더 | 입력/시전 결과 | 화면·정리 |
|---|---|---|
| [04](../runs/mage-stage1-20261031-04) | install INSTALLED/native_error0. 힐 선택5개·대상 클릭3개 native event COMPLETED. 시전0/8. **무게82% 초과로 마법 사용 불가** 문구. 첫 미확인에서 나머지 SKIPPED | PNG4개. [mage-0-after.png](../runs/mage-stage1-20261031-04/mage-0-after.png) 직접 확인. FORCED_CLEANUP, 정상 Quit/로그아웃 미검증. LC_LEFT0·slot/Capture 원복 |
| [05](../runs/mage-stage1-20261031-05) | install 성공. **key0~4 시전5/8**, key5 입력 완료/시전 미관측, key6/7 SKIPPED. 입력 timeout0 | PNG21개. key0~4 immediate와 후속 after, key5 after를 직접 열고 필요한 원본 해상도 부분도 확대 확인. 위 표 「화면 확인」 칸 참조. FORCED_CLEANUP, 정상 Quit/로그아웃 미검증. LC_LEFT0·slot/Capture 원복 |

05 시작 저장은 `_work/tmp/mage-stage1-followup-20261031/profile-light`의 **새 로그인 전 시험 사본**이다. 기존36개 인벤토리 UID·소유 무기65549·학습0~7·장비 anchor를 유지하고 세 소모품의 시작 수량만65546(template17)50→1,65547(template296)62→1,536871312(template14)90→1로 줄였다. 기존 장비 `_kit_state` 검증을 재사용했고 실제 화면 무게61%였다. 사용자 저장·04의 실패 기록은 보존했다. 런타임 무게 검사·MP·학습·대상 guard는 완화하지 않았다. 이 fixture는 native 책 학습의 증거가 아니다.

| key | 05 실제 handler 이벤트·소비 |
|---|---|
| 0 | cast, HP회복14, MP314→310 |
| 1 | cast, MP310→306, 광원4F01 `{1:1,2:14}` 큐 기록 |
| 2 | cast, MP309→307(앞선 자연회복 별도),4E91 큐 기록 |
| 3 | cast, 대상268435487 흑기사 피해23, MP307→304 |
| 4 | cast, MP307→302, map0 `(32632,32835)→(32529,32813)` 이동. 버프1 deadline60321.328·버프2 deadline54328.703 유지.4E91/4F01 replay 큐 기록 |
| 5 | mage-5-native-spell·mage-5-native-target 모두 POSTED/원 helper COMPLETED. 시전 이벤트0, MP302 유지, 서버 마법 오류[] |
| 6/7 | first-failure 중단으로 SKIPPED. 시전·소모·화면 확인을 만들지 않음 |

05 마감 당시 중단 위치는 그때 `verify_ncg_waitonly.py:8195`의 기존 world_grid_to_capture 대상 좌표 → **mage-5-native-target**이었다(현재 같은 투영 호출은8233행). `validation-profiles/mage-stage1-20261031-05/execution.log:60`은 아이스 대거 선택,`:63`은 대상 입력 COMPLETED,`:66`은 시전 미관측이다. NPC 격자 `(32534,32821)`의 PNG 클릭점은 **(2610,930)**(client(3090,930))이었다. 로그의 열린 SpellLayout capture rect는 **(2022.75,0)~(2877.75,1305)**라 클릭점이 창 내부다. **월드 대상 대신 마법창이 입력을 받은 것으로 추정한다.** 입력 timeout 재발이나 서버 MP/대상 거절로 확정하지 않는다. 다음 최소 관측은 같은 검증된 좌표 방법으로 마법창에 가리지 않는 원 대상 입력 경로에서 key5~7을 시전하는 것이다. 추가2회 한도 때문에 재실행하지 않았다.

실드·라이트 buff HUD는 열린 마법창과 함께 찍힌 캡처에서 확인되지 않았다. 4E91/4F01 큐 기록만으로 화면 성공으로 판정하지 않는다. 힐의 푸른 입자는 immediate에는 없고 **후속 after**에서 보여 그 파일을 근거로 삼았다. 한 장의 시전자 자세는 전체 애니메이션 속도/프레임 동등성의 증명이 아니다.

이번 제품 서버·데이터 변경은0이다. 변경한 시나리오는 `verify_ncg_waitonly.py:8133,8213`의 시전 이벤트 최초 관측 시 원 screenshot을 앞당기는 부분뿐이다. 좌표식·효과/애니메이션 속도·DLL은 변경하지 않았다. 문법 검사와 지정5모듈 **159/159**,51.374초를 확인했다. 원로그 `_work/tmp/mage-stage1-followup-20261031/unit-tests.log`. Claude가 전달한 world_maps_tests fixture 바인딩·던전58개 OK는 별도 선행 결과로 보존했고 여기서 재실행했다고 주장하지 않는다.

```powershell
python -X utf8 -B -m unittest tools.local_original_session.spellbook_learning_tests tools.local_original_session.world_magic_tests tools.local_original_session.world_magic_status_feedback_tests tools.local_original_session.world_companion_support_spell_tests tools.local_original_session.world_companion_magic_tests
```

wrapper 원로그는 `_work/tmp/mage-stage1-followup-20261031/headless4-wrapper.log`, `headless5-wrapper.log`다. 각 실행 폴더의 verify-shots.json·result.json·mage-stage1-frames.json·boundary-path.txt와 원본 PNG를 보존했다. 작은 검토 이미지/확대본은 같은 `_work/tmp/mage-stage1-followup-20261031`에만 만들었다.


## 마법창 가림 교정·잔여3종 확인 (06~07)

2026-10-31 직접 후속 지시의 최대2회 안에서 실행했다. 매번 LC 계열 및12000/14030 리스너0을 확인했다. 제품 서버·데이터·DLL·사용자 저장 수정0, 커밋0이다.

`verify_ncg_waitonly.py:8110`은 VERIFY_MAGE_KEYS를 받아 이미 확인한 시전을 생략한다. `:8128`은 마법 선택 바로 뒤 mage_close를 넣고,`:8296`은 기존 open_magic_window 원 토글 뒤 새 MemoryUi 읽기로 숨김을 확인한다. 원 이벤트 최초 관측 캡처도 창이 닫힌 뒤로 미뤘다. UI/월드 좌표는 기존 node_to_capture·world_grid_to_capture만 사용했다. `:8206`의 실드 hover는 기존 play.buff_hover 선택 방법 재사용이며,`:8233`은 원 함수가 이미 가진 후보0/1/2만 선택한다. 새 투영식·보정·게임 속도·효과 지속시간·guard 완화는 없다.

| 실행 | 시작 저장·시나리오 | 실제 결과·마감 |
|---|---|---|
| [06](../runs/mage-stage1-20261031-06) | 앞서 검증한 가벼운 로그인 전 시험 사본 `_work/tmp/mage-stage1-followup-20261031/profile-light`. keys=`1,2,5,6,7`, 기존 좌표 후보0. 라이트·실드는 가림 없는 HUD/밝기 비교를 위해 필요한 표시만 재시전 | 라이트·실드·아이스·윈드 시전. 아이스 피해24, 윈드 남은HP6 처치. 홀리는 입력 완료됐지만 시전 이벤트0·서버 오류[]. 원 캡처22개+요청 영역 파생 PNG4개. FORCED_CLEANUP, 정상 Quit/로그아웃 미검증. LC_LEFT0·slot/Capture 원복 |
| [07](../runs/mage-stage1-20261031-07) | **06 결과 저장을 새 사본으로 복사**해 UID/MP/버프 잔여·수명·EXP를 이어받음. keys=`7`, 기존 후보2. 원 HudBuffLayout Panel_Slot hover로 복원 실드 시간 확인 | 홀리 MP311→301, target1, 실제 selected weapon65549. 닫힌 HUD에 홀리·실드 아이콘. 원 캡처7개+요청 영역 파생 PNG2개. FORCED_CLEANUP, 정상 Quit/로그아웃 미검증. LC_LEFT0·slot/Capture 원복 |

06의 홀리 입력 실패를 같은 조건으로 반복하지 않았다. 06 PNG 자기 대상점(1440,795)과 달리07은 **기존 world_grid_to_capture 후보2**의(1440,807), client(1920,807)을 사용했다. 이 변경 뒤 원 native input→기존 디코더/handler→MP/무기 버프→HUD가 관측됐다. 좌표 민감성이 원인 후보지만06에 시전 요청이 없었던 내부 원인까지 확정하지 않는다. 06 `execution.log:65,68`은 입력 완료/시전 미관측,07 `execution.log:17,21`은 입력 완료/시전 성공이다. 두 실행 모두 같은 입력 시간 초과는 재발하지 않았다.

06 라이트 전후는 모두 map0 `(32632,32835)`에서 창이 닫힌 상태다. 원본 `mage-1-light-before.png`, `mage-1-light-after.png`의 **같은 (1050,850)~(1350,1100) 영역**을 좌우로 놓은 `mage-1-light-same-region.png`를 직접 확인했다. 뚜렷한 주변 밝기 변화는 확인되지 않았다. 일부 알파/이동 객체 차이도 있어 작은 RGB 평균 차이를 광원 성공으로 해석하지 않는다. 광원 강도·현재 조도 모드의 미확정은 유지하고 숫자를 올리거나 렌더러를 대체하지 않았다. 라이트 단독 HUD 영역에는 아이콘이 보이지 않았고 검증된 양수 CommonSpell HUD K도 기존 자료에 없다.

06 실드 뒤 창 가림 없이 방패 아이콘과 AC5를 확인했다(전 AC7, Claude의05 관측과도 일치). 07 cold restore 후 **실드: AC-2 / 남은시간13분22초** 원 hover 툴팁을 직접 읽었다. 07 마감 저장은 실드 remaining779.733초, 홀리 remaining1186.234초·weapon_uid65549를 보존한다. native 툴팁을 보지 않은 홀리 자체 잔여시간까지 화면 PASS로 확대하지 않는다.

확대 검토에서06 아이스의 난쟁이 옆 청색 광탄, 윈드의 대상측 흰 굽은 빛 일부·쓰러짐/35아데나 드롭 라벨을 확인했다. 드롭 라벨은 줍기/인벤토리 획득 PASS가 아니다. 07 홀리의 시전자 팔 든 자세·옅은 흰 세로빛 일부와 HUD 십자 아이콘을 확인했다. 별도 효과 전체 형태·프레임·원본 속도 동등성은 미판정이다. 각 원본 경로와 판정은 위 「화면 확인」 칸에 반영했다.

요청한 버프 영역 파일:06 `mage-1-buff-closed-region.png`, `mage-2-buff-closed-region.png`, `mage-7-after-hud-region.png`;07 `mage-7-buff-closed-region.png`, `mage-restored-shield-tooltip-region.png`. 영역 PNG는 해당 원 캡처의 (2100,0)~(2880,500), tooltip은 y650까지 자른 **파생본**이며 원본을 덮지 않았다. 원본 해상도 확대·작은 검토 JPEG는 `_work/tmp/mage-stage1-window-20261031`에만 두었다.

현재 지정5모듈 명령은 앞 절과 같으며 **159/159**,61.501초. 원로그 `_work/tmp/mage-stage1-window-20261031/unit-tests.log`. 시나리오 구문도 확인했다. wrapper 원로그는 같은 tmp의 headless6-wrapper.log·headless7-wrapper.log이고, 각 run의 result.json·verify-shots.json·mage-stage1-frames.json·boundary-path.txt·원 PNG를 보존했다. 0/3/4는05 근거를 재사용했고 재시전하지 않았다.
