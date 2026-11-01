# 법사 리무브 커스 + 6단계 8종 대조·구현

2026-10-31. 비교 클라이언트 **26.09.29.2001** 고정. 리무브 커스(key36)와 6단계(key40~47)를 구현·시험했다. 이후 사용자 실행 승인으로 헤드리스 **3/5회**를 수행하고 캡처를 직접 열어 아래처럼 판정했다. 단위 시험·시전 이벤트·화면 판정을 구별하며 원본 전체 동등성이나 정상 종료 PASS를 주장하지 않는다. 사용자 저장·금지 파일은 보존했고 커밋 없음.

## 출처와 표 읽는 법

- **O36/O40~O47**: [공식 수집본](../../../tools/local_original_session/data/official/spells.json)의 `official_id` 행과 그 `source.raw_path` 원문. 6단계는 `work/official_data_refresh_20261028/raw/spell/40.json`~`47.json`(2026-10-28 수집), 리무브 커스는 카탈로그에 보존된 2026-10-26 원문이다. URL·수집일·SHA256을 각 `source_snapshot.official_source`와 `provenance`에 보존했다. 이번 작업에서 HTTP 재조회는 하지 않았다.
- **Ck**: 고정 [UI join](../../all_table_semantics/spell_token/spell-ui-joins.json), [CommonSpell 원문](../../all_table_semantics/spell_token/spell-records.json), [native dump](../../source_game_data/native-dump-v1.jsonl). `source_snapshot.client_ui/client_common_spell_raw_fields`에 필요한 행을 보존했다. 책은 공식 textbook.id/name와 native item.f41의 **이름·키 동시 일치**를 확인했다. 책203/204~208/522/605/606의 native 행은 각각1118/1119~1123/1325/1374/1375다.
- **Dk**: [표시 자료](../../../tools/local_original_session/data/m1/spell_display.json). 이름·단계로 연결한 L1J action/castgfx와 고정 SPR·파일 catalog를 사용한다. 신규8행 모두 실제 SPR·SPX 크기·해시가 존재한다. 파일 존재와 송신 시험은 화면 확인을 대신하지 않는다.
- **L**: `D:/SingleLineageRef/l1j-en-classic`, 보존 HEAD `103e6f6c9dd83545959d8e87d3f59f8de1f40ef0`. `db/l1jdb_m10.sql:35657,35661~35668`; `L1Magic.java:181~203,275~387,659~783`; `L1SkillUse.java:174~183,555~565,1755~1791,2159~2275,2714~2732,2967~2989`; `Instance/L1ItemInstance.java:1075~1117`; `config/altsettings.properties:150`. Classic 원 서버 동등성의 증명이 아닌 명시 LOCAL backend 참고다.
- **P**: [기존 wire 근거](PLAYER_MAGIC_EVIDENCE.md), [HUD 근거](BUFF_GAMETIME_EVIDENCE.md). `4EE6` 실제 handler → `4E31` 시전 동작, `4ED8` 대상 효과, `4E91` 실제 deadline의 남은 초를 재사용한다.

우선순위는 **공식 > 고정 클라이언트 > 명시 이름 대응 L1J**다. 공식에 없는 수식·확률·중첩은 LOCAL, 근거 불명은 UNKNOWN으로 둔다. 공식 원문·기존1~5단계 수집 자료·동료AI 카탈로그는 변경하지 않는다.

## 학습·소비·재사용

6단계8종의 공식 학습 조건은 **법사24 / 요정48**, 리무브 커스는 **법사20 / 요정40**이다. 장소·캐릭터 성향 임계값은 공식/고정 클라이언트에서 확인되지 않아 **UNKNOWN**이다. 주문의 라우풀·뉴트럴·카오틱 분류를 학습 장소/성향 제한으로 바꾸지 않았다. 기존과 같은 LOCAL 무추가제한 정책이다. 다른 클래스는 거절한다.

책은 기존 `0960` → 소유·수량·클래스·레벨 확인 → inventory CAS/learning intent → 영속 학습 → `4E60` 순서로 1권 소비한다. 이미 배움/조건 불충족/미구현은 소비하지 않는다. `drops_misc.json`에 있던 아래9개 책 정의를 **메타데이터·가격 참조를 보존해** `spellbooks.json`으로 옮겨 중복 ID를 제거했다. 새 아이템·UID를 발명하지 않았다.

| key / 이름 | 클래스·레벨 | 책 template / 소비 | MP / HP / 시전 재료 | 재사용 정책 | 학습·시전 상태 |
|---|---|---|---|---|---|
| 36 리무브 커스 | 법20/요40 [O36] | 203 / 1권 [O36,C36] | 10 / 0 / 없음 [O36, 공식 list] | LOCAL1초; L SQL0ms·공식 UNKNOWN | 구현함. 기존 지원·시전 경로의 해제 범위와 책 메타데이터 보완 |
| 40 크리에이트 좀비 | 법24/요48 [O40] | 204 / **소비 거절** | 원문35 / 0 / 마력의 돌166×2 [O40,C40] | 후보 LOCAL1초; 미지원이므로 소비 없음 | **미구현**. 데이터·책·표시 recipe 등록, 학습/시전은 `MAGIC_EFFECT_UNSUPPORTED` |
| 41 인챈트 마이티 | 법24/요48 [O41] | 205 / 1권 [O41,C41] | 40 / 0 / 없음 [O41,list] | LOCAL1초; L0ms·공식 UNKNOWN | 구현함 |
| 42 헤이스트 | 법24/요48 [O42] | 206 / 1권 [O42,C42] | 40 / 0 / 없음 [O42,list] | LOCAL1초; L0ms·공식 UNKNOWN | 구현함. 물약17과 같은 속도 소유자 |
| 43 캔슬레이션 | 법24/요48 [O43] | 207 / 1권 [O43,C43] | 40 / 0 / 돌166×2 [O43,C43] | LOCAL1초; L0ms·공식 UNKNOWN | 구현함. 아래 명시된 해제 범위·예외 |
| 44 이럽션 | 법24/요48 [O44] | 208 / 1권 [O44,C44] | 25 / 0 / 없음 [O44,list] | LOCAL0.4초 [L35665]; 공식 UNKNOWN | 구현함. 현재 일반 몬스터 피해 경로 |
| 45 선 버스트 | 법24/요48 [O45] | 522 / 1권 [O45,C45] | 30 / 0 / 없음 [O45,list] | LOCAL0.5초 [L35666]; 공식 UNKNOWN | 구현함. 현재 일반 몬스터 피해 경로 |
| 46 위크니스 | 법24/요48 [O46] | 605 / 1권 [O46,C46] | 25 / 0 / 돌166×1 [O46,C46] | LOCAL0.5초 [L35667]; 공식 UNKNOWN | 구현함 |
| 47 블레스 웨폰 | 법24/요48 [O47] | 606 / 1권 [O47,C47] | 20 / 0 / 없음 [O47,list] | LOCAL1초; L0ms·공식 UNKNOWN | 구현함 |

MP는 기존 **공식 기본값 차감 LOCAL 정책**이다. 실제 Classic 장비·INT 비용 감소는 UNKNOWN. HP0은 공식 list와 고정 클라이언트이며 좀비 L1J의 HP80을 복사하지 않았다. 마력의 돌은 기존 고정 template166·소유 인벤토리 양수 수량·착용 제외·동일 kit CAS를 사용한다. 재사용·대상·시야·무게·재료 확인을 통과한 시전만 자원을 소비한다. 확률 실패도 실제 시도이므로 비용을 소비한다.

## 대상·효과·표시·유지

| key / 이름 | 대상·수치·지속시간 / 근거 | 시전 action / gfx [D] | 아이콘·남은 시간 | 실제 소비·저장·이동 | 화면 확인 | 캡처 경로 |
|---|---|---|---|---|---|---|
| 36 리무브 커스 | 10칸 PC/현재 일반NPC1인, 순간 [O36]. 독·블라인드·패럴라이즈·다크니스·저주·슬로우·위크니스·디지즈·인탱글·이레이즈 해제. 기존 착용 저주 장비 훅도 실행 | 19 / 227 [L35657] | 순간 HUD 없음. 해제된 효과의 원 아이콘 삭제·독/석화/암흑 복원 wire | L은 독·마비만 명시. 나머지 디버프 해제는 **사용자 요청 LOCAL 확장**. 다른 버프·물리 무기 손상 유지. PC 저장/NPC 현재 수명 처리 | **확인**: 해제 시전·푸른 수직 효과. 초기 독/블라인드/Slow/Weakness 4개 제거, MP10 소비 | [mage-36-immediate.png](../runs/mage-stage6-20261031-01/mage-36-immediate.png) |
| 40 크리에이트 좀비 | 10칸 NPC시체, 하수인 생성3,600초 [O40] | 후보19 / 226 [L35661] | 원 CommonSpell에 양수 HUD K 없음. 미지원 | 시체 단일 소비→좀비 프로필→주인/추종/명령/타깃→3,600초 만료→저장/재접속/이동 정리 계약 **미구현**. 비용·시체 소비 안 함 | **미구현으로 제외** | 없음 |
| 41 인챈트 마이티 | 10칸 술자/현재 PC1인, STR+5·1,200초 [O41]. 기존 수신 버프의 LOCAL pledge 관계 정책 | 19 / 751 [L35662] | spell41 / K482 [C41 f3]. deadline-now·ceil | 실제 STR 계산·무게 상한·물리 profile/상태 프레임에 반영. 남은 시간 저장/오프라인 경과 차감·텔레포트 deadline 유지/HUD replay | **확인**: STR8→13, 아이콘·STR+5 설명·19분54초. 짧은 별도 gfx 모양은 미확인 | [mage-41-tooltip.png](../runs/mage-stage6-20261031-02/mage-41-tooltip.png) |
| 42 헤이스트 | 10칸 PC/현재 일반NPC1인·이동/공격 가속1,200초 [O42]. PC interval×0.745 [기존 물약17 LOCAL] | 19 / 755 [L35663] | **기존 물약 HUD** catalog223 / K481 [고정 C42와 동일 K]. 독립 spell42 아이콘을 중복 생성하지 않음 | PC `PcState.buffs['haste']`·scheduler·물약 저장/재접속·텔레포트 replay 재사용. LOCAL 남은 시간+1,200, 기존 cap1,800·속도 배율은 한 번만. Slow/Entangle 있으면 상쇄 후 가속 없음 [L1755~1783]. NPC는 EntityRef 상태와 AI cadence/HUD 아닌 actor 속도 발표, 몬스터 자기 헤이스트와 중복 방지 | **확인**: 물약 공유 가속 아이콘·설명·19분54초. 별도 시전 gfx 모양은 미확인 | [mage-42-tooltip.png](../runs/mage-stage6-20261031-02/mage-42-tooltip.png) |
| 43 캔슬레이션 | 10칸 PC/현재 일반NPC1인, 상태 변화 해제·순간 [O43]. 자기/NPC는 L1Magic181~203의 성공 분기; 다른 PC는 LOCAL 확률 | 19 / 870 [L35664] | 순간 HUD 없음. 지운 버프·가속 아이콘 삭제/속도·외형·상태 복원 | 현재 magic 버프·디버프/독/투명·소모품 마법효과·가속·변신을 각 소유자 훅으로 정리·저장. **L 예외 key11/13/86/87/89/90**와 물리 무기 손상·장비 저주·학습/재사용은 보존. 기존 몬스터용 buff-only Cancel API는 바꾸지 않음 | **부분 확인**: 자기 Mighty/가속 아이콘 제거·STR13→8·시전 자세. gfx870 모양·변신 해제 화면은 미확인 | [mage-43-immediate.png](../runs/mage-stage6-20261031-01/mage-43-immediate.png) / [mage-43-after.png](../runs/mage-stage6-20261031-01/mage-43-after.png) |
| 44 이럽션 | 10칸 1인 [O44]. 현재 일반 몬스터 대상 LOCAL `(5d3+50)` + 기존 INT/SP·MR·critical·속성1(땅) 수식 [L35665,L1Magic659~783] | 18 / 129 [L35665] | 순간 HUD 없음 | 실제 현재 몬스터 HP 감소/피격·사망·보상 소유자. HP/MP·원 이펙트 송신. 공식 정확 피해식/PvP는 UNKNOWN | **부분 확인**: 시전 자세·대상 HP50 피해/처치. 별도 땅 폭발 gfx129 모양은 미확인 | [mage-44-immediate.png](../runs/mage-stage6-20261031-01/mage-44-immediate.png) |
| 45 선 버스트 | 6칸 1인 [O45]. 현재 일반 몬스터 대상 LOCAL `(16d5+40)` + 기존 INT/SP·MR·critical·속성2(불) [L35666,L1Magic] | 18 / 1811 [L35666] | 순간 HUD 없음 | 이럽션과 같은 실제 HP 소비. 공식 정확 피해식/PvP는 UNKNOWN | **부분 확인**: 시전·대상 HP50 피해/처치·약한 수직 빛 기둥. 원 폭발 전체 동등성 미확인 | [mage-45-immediate.png](../runs/mage-stage6-20261031-03/mage-45-immediate.png) |
| 46 위크니스 | 2칸 PC/현재 일반NPC1인·근거리 대미지-4/명중-2·30초 [O46]. LOCAL L1J 일반 확률 dice12 [L35667] | 19 / 2228 [L35667] | spell46 / K852 [C46 f3], 실제 남은 초 | PC 실제 근접 profile modifier, 원거리 제외. NPC 일반/특수 물리 공격의 명중 입력-2·damage roll-4, live level/EXP/주문 피해를 바꾸지 않음. PC 남은 시간 저장/복원·텔레포트 replay/만료·리무브/캔슬로 해제. NPC EntityRef 수명 | **부분 확인**: 실제 접근 후 NPC 시전·어두운 짧은 효과/자세, 비용 소비·상태 적용. PC 수신 아이콘/설명은 화면 미확인 | [mage-46-immediate.png](../runs/mage-stage6-20261031-03/mage-46-immediate.png) |
| 47 블레스 웨폰 | 10칸 현재 PC1인·착용 무기 UID·근거리 명중+2/대미지+2·1,200초 [O47] | 19 / 2176 [L35668] | spell47 / K728 [C47 f3], 실제 남은 초 | 현재 착용 UID에서만 실제 근접 효과. Holy/Enchant Weapon과 공유 enchant timer의 교체 [L1ItemInstance1075~1117]; 기존 둘만의 동작은 유지. 저장/재접속/텔레포트 deadline·무기 UID 유지. 무기 교체 시 다른 UID에 효과 전이 안 됨 | **확인**: 무기 버프 아이콘·추가 대미지+2/근거리 명중+2 설명·19분53초. 별도 gfx 모양 미확인 | [mage-47-tooltip.png](../runs/mage-stage6-20261031-02/mage-47-tooltip.png) |

표시 OFF 실험 설정에서도 **이번9종**의 정상 시전 action/gfx를 송신한다. 1~5단계 다른 마법의 표시 설정은 그대로다. `4ED8`은 기존 대상 위치 효과 경로이며 비행·연결 폭발·픽셀 동등성은 UNKNOWN이다. 지속 HUD가 없는 순간 마법에 가짜 아이콘을 만들지 않았다.

헤이스트의 저장은 **기존 물약 정책대로 접속 해제 중 남은 시간 일시정지**, 다른 magic 버프·디버프는 **실제 오프라인 경과 차감**이다. 공식 Classic의 정확한 오프라인 정책은 UNKNOWN이다. 물약/주문 Haste를 같은 소유자로 합친 LOCAL 정책은 L1J의 서로 다른 효과 ID 구분까지 재현한 것이 아니다. 추가 중첩 구현을 Classic 사실로 주장하지 않는다.

## 크리에이트 좀비의 미완 계약

기존 `world_feature_pet.PetSystem.summon/tame`와 `world_monster_skills`의 NPC 소환 구조는 존재한다. 그러나 전자는 살아 있는 길들이기 대상·영속 펫/목걸이 소유권, 후자는 NPC 시전자 EntityRef가 소유하는 일시 전투 그룹이다. **플레이어가 소비할 시체를 원자적으로 인수해 주인에게 귀속하는 등록 서비스가 없다.** 어느 쪽도 6단계 공식3,600초 하수인의 재접속·텔레포트·명령·수명 계약을 바로 제공하지 않는다.

L1J `L1SkillUse2967~2989`는 기존 펫 비용과 CHA를 계산한 뒤 `L1SummonInstance(corpse,user,true)`를 생성한다. 그 생성자·변환 NPC 이름 대응·현재 펫 비용/CHA 제공자·시체 소비/기존 corpse cleanup의 인계·영속 저장을 먼저 연결해야 한다. 살아 있는 펫을 생성하거나 시체를 남긴 가짜 소환으로 대체하지 않았다. 다음 최소 작업은 이 **하나의 플레이어 시체→하수인 소유 서비스**를 제공하는 것이다. 현재 책204는 등록되지만 학습/시전·MP/HP/돌 소비를 거절한다.

## 단위 시험과 기대값 변경 근거

시험은 임시 사본과 순수 world/handler fixture를 사용한다. 게임·네트워크 리스너·사용자 저장을 실행하지 않는다. `TEMP/TMP=_work/tmp`; `launcher_tests`, `manual_move_commands_tests`, hunt_bot은 제외했다. 기본 guard·원본 비용·수량·CAS·수명 검사를 낮추지 않았다.

초기263개에서7실패를 보존한 로그는 `_work/tmp/stage6-tests-second.log`다. 원인/변경 근거:

| 항목 | 변경·근거 |
|---|---|
| supported catalog/표시 행 집합 | 공식6단계40~47 추가, 구현41~47과 미지원40의 실제 SPR recipe를 반영. 미지원 마법을 구현 PASS로 바꾸지 않음 |
| 책 메타데이터 개수 | 기존45행에 6단계8행+리무브 커스1행을 전용 테이블로 이동. supported22/conditional8/deferred24는 실제 분류 수. 게임 전체 아이템 ID·가격 정책 불변 |
| `JOB_DEFERRED` 집합 | 좀비를 직업 마법 상수에 섞었던 구현 오류 수정. key40은 자신의 구체적인 `implementation_limit`을 사용. 직업86이상 목록은 그대로 |
| remove_curse의 Slow 보존 기대 | O36 설명은 저주 목록을 열거하지 않는다. L1J는 독/마비만 명시. 사용자의 이번 요청에 맞춘 **명시 LOCAL 해제 확장**이므로 Slow 해제를 기대하며 기존 다른 버프 보존은 계속 확인 |
| 몬스터 Cancel `(1,10)` 아이콘 | 기존 몬스터용 API는 독/Slow를 유지한다. poison이 활성인 fixture에 고정 CommonSpell10/K5319가 남는 것이 기존 `_world_magic_icon_deadlines`와 맞다. 기대를 `(1,28),(1,10)`으로 수정했으며 **제품 동작은 변경하지 않음** |

최종 시험 명령/수치는 아래 마감 기록에 기입한다. 신규 `world_magic_stage6_tests`는 실제 MP·촉매 CAS 제안·몬스터 HP 감소·STR·무기 UID·근접/원거리 구분·가속 상태/잔여 시간·저장/복원·HUD replay·해제 예외·변신 원복/기존 timer 취소·미구현/재료 부족 거절을 확인한다. fixture 준비를 정상 로그인 패킷/책 UI 증거로 올려 말하지 않는다.

## 헤드리스 시나리오

[verify_ncg_waitonly.py](../companion-bridge/verify_ncg_waitonly.py)의 `mage_stage6`는 동료 기능을 시작 전 비활성화하고 기존 owned desktop/GLFW callback 경로를 재사용한다.

- `VERIFY_MAGE_KEYS`로 부분 선택, `VERIFY_MAGE_START_KEY`로 시작 지점을 지정한다. key40은 미구현 사유만 기록하고 native 시전을 생략한다.
- key36은5페이지, 나머지는6페이지에서 원 UI 노드 우선, 불가하면 **현재 실행 캡처에서 직접 측정한** `VERIFY_MAGE_POINTS`로 선택한다. 창 닫힘 확인 → 창 밖 실제 대상 클릭 → 즉시/후속 캡처 순서다. 위크니스는 기존 grid 투영/접근 이동으로2칸 안에 들어간다.
- 버프 영역을 가리는 창을 닫은 캡처와 hover를 남긴다. 독립 마법이 앞선 대상 사망 등으로 실패해도 다음 독립 마법으로 넘어가며 실패 결과를 지우지 않는다.
- 사본은 `_work/tmp/mage-stage6-20261031/profile` 및 `profile-clean`. 이전 시험 저장을 복사했고 UID allocator·kit append CAS로 돌6개를 추가한 뒤 장비를 복원했다. 무게는 시전 한도 아래다. 학습 완료 값은 시험 초기값이며 **native 책 학습 증거가 아니다**. 첫 사본에는 독/블라인드/Slow/Weakness가 있고 clean에는 없다.

지정 candidate SHA256 `00d646b40516a10a0f4978be156ce9dfb1f137c1f550eff34228e1762b05a67e`, `VERIFY_INPUT_ROUTE=GLFW_CALLBACK_INJECTION`, `TEMP/TMP=_work/tmp`로 실행했다. 실행별 결과는 아래 기록에 보존한다.

## UNKNOWN·부분 범위

- 크리에이트 좀비의 플레이어 시체 인수·하수인 프로필/명령·동료/펫 비용·3,600초 저장/복원/정리: 미구현.
- 공식 마법별 서버 재사용, 동적 INT/장비 MP 감소, 정확한 피해/성공 확률·가속 배율/중첩·오프라인 정책: UNKNOWN. 표의 수치식은 명시 LOCAL 참고다.
- 학습 장소/성향 임계값, 실제 혈맹/파티 관계, 캔슬레이션의 Classic 전체 예외·안전지역/다른 PC 관계 규칙: UNKNOWN. 현재 관계 정책과 일반 PC 확률은 LOCAL이다.
- 이럽션·선 버스트의 PvP 및 동료/펫 등 별도 HP 소유자에 대한 피해 경로: 미지원. 현재 일반 몬스터 경로만 구현.
- 헤이스트의 동료/펫 등 별도 actor 속도 소유자 대상: 미지원. PC/현재 일반 NPC만 구현. 인챈트 마이티/블레스 웨폰의 별도 동료 수신은 기존 등록 버프 서비스의 지원 범위에 따르며 전체 보장을 하지 않는다.
- 표의 미확인 짧은 gfx/비행/정리·다른 PC 수신 아이콘·변신 해제 및6단계 재접속/텔레포트 **화면**: UNKNOWN. 저장/복원·텔레포트 replay는 단위 시험 범위에서 통과했다. Native 책 사용/학습 화면은 이번 시전용 초기값으로 증명하지 않는다.

## 마감 검증 기록

**325개 통과 / 실패0 / 오류0 / 스킵0**, 103.212초. 실제 최종 로그: [_work/tmp/stage6-unit-verified.log](../../../_work/tmp/stage6-unit-verified.log). 기존 `unittest.defaultTestLoader.loadTestsFromNames`로 아래18개 모듈을 로드하고 `TextTestRunner`로 실행했다. 아래는 같은 스위트의 재현 명령이다.

```powershell
$env:TEMP=(Resolve-Path _work/tmp).Path
$env:TMP=$env:TEMP
$modules = @(
  'spellbook_learning','world_magic','world_magic_status_feedback',
  'world_companion_support_spell','world_companion_magic','world_undead_damage',
  'world_combat_requests','world_maps','world_item_effects',
  'monster_skills_cancel','monster_skills','monster_skills_support',
  'monster_skills_phase2','world_polymorph','world_consumable_restore',
  'game_data','world_m3_data','world_magic_stage6'
) | ForEach-Object { 'tools.local_original_session.' + $_ + '_tests' }
python -m unittest @modules
python -m py_compile work/local_original_session/companion-bridge/verify_ncg_waitonly.py
```

시나리오 구문 검사 종료코드0. 6단계 전용13개 단독 시험도 통과했다. 실제 게임/서버를 실행하는 모듈은 포함하지 않았으며, 테스트의12000/14030은 모의 socket 객체인 경우뿐이다.

이전 실행263개7실패, 중간307개0실패, 후속324개0실패의 로그를 모두 보존했다. 당시에는 화면 검증 전이었다. 이후 헤드리스 결과는 아래에 별도 기록했다. 7단계 통합 최종 소스는 **339개/110.497초/실패0·오류0·스킵0**, 로그 [_work/tmp/stage7-unit-verified.log](../../../_work/tmp/stage7-unit-verified.log)이며7단계 전용14개를 함께 포함한다.

## 수정 파일·위치

아래 줄은6단계 구현 마감 시점 스냅샷으로, 후속7단계 추가에 따라 코드 줄이 이동할 수 있다.7단계 문서의 최종 조회 위치도 함께 참조한다. 기존 대량 dirty/untracked 변경은 보존했으며 이 목록 밖의 수정·커밋을 하지 않았다.

| 파일:줄 | 변경 요지 |
|---|---|
| [player_spells.json:16](../../../tools/local_original_session/data/m3/player_spells.json#L16), [리무브10743](../../../tools/local_original_session/data/m3/player_spells.json#L10743), [6단계19555](../../../tools/local_original_session/data/m3/player_spells.json#L19555) | stage6·공식/고정클라/L1J 값별 출처8행, 리무브 해제 정책·LOCAL/UNKNOWN |
| [spellbooks.json:974](../../../tools/local_original_session/data/m1/items_ext/spellbooks.json#L974), [drops_misc.json:1](../../../tools/local_original_session/data/m1/items_ext/drops_misc.json#L1) | 기존9개 책 정의·가격/출처 보존 이동, 학습 메타데이터/미지원 거절 |
| [spell_display.json:3132](../../../tools/local_original_session/data/m1/spell_display.json#L3132) | 이름 대응6단계8종 action/gfx·실제 SPR/SPX 존재 recipe |
| [world_magic.py:22](../../../tools/local_original_session/world_magic.py#L22), [STR423](../../../tools/local_original_session/world_magic.py#L423) | strength 버프·STR 기여, 새 블레스 웨폰과 무기 enchant 교체 |
| [world_magic_status.py:13](../../../tools/local_original_session/world_magic_status.py#L13), [물리 입력91](../../../tools/local_original_session/world_magic_status.py#L91) | 리무브 Slow/Weakness, NPC haste·weakness 상태/명중·피해 입력 |
| [world_feature_magic.py:310](../../../tools/local_original_session/world_feature_magic.py#L310), [스탯794](../../../tools/local_original_session/world_feature_magic.py#L794), [시전1298](../../../tools/local_original_session/world_feature_magic.py#L1298) | 플레이어 Cancel 예외·소유자 훅, STR/근접·대상·상태·이펙트/HUD·리무브 장비 저주 연결 |
| [world_item_effects.py:984](../../../tools/local_original_session/world_item_effects.py#L984), [해제1016](../../../tools/local_original_session/world_item_effects.py#L1016) | 기존 물약 속도/타이머/저장/HUD를 Haste와 공유, Cancel 시 자기 효과 정리 |
| [world_feature_items.py:522](../../../tools/local_original_session/world_feature_items.py#L522) | 기존 변신 expiry로 원 외형 복원·타이머 취소 |
| [world_feature_monster_skills.py:30](../../../tools/local_original_session/world_feature_monster_skills.py#L30), [world_monster_skills.py:116](../../../tools/local_original_session/world_monster_skills.py#L116), [물리302](../../../tools/local_original_session/world_monster_skills.py#L302) | NPC 자기 haste 중복/해제 소유권과 특수 물리 Weakness 소비 |
| [world_magic_stage6_tests.py:17](../../../tools/local_original_session/world_magic_stage6_tests.py#L17) | 신규13개 단위 시험 |
| [spellbook_learning_tests.py:54](../../../tools/local_original_session/spellbook_learning_tests.py#L54), [world_magic_tests.py:24](../../../tools/local_original_session/world_magic_tests.py#L24), [리무브1390](../../../tools/local_original_session/world_magic_tests.py#L1390), [monster_skills_cancel_tests.py:86](../../../tools/local_original_session/monster_skills_cancel_tests.py#L86) | 위 표에 근거를 남긴 기존 기대값 수정 |
| [verify_ncg_waitonly.py:8144](../companion-bridge/verify_ncg_waitonly.py#L8144) | mage_stage6/7 시나리오·실측 좌표/현재 대상·닫힌 버프 캡처 |
| [MAGE_SPELLS_STAGE6.md](MAGE_SPELLS_STAGE6.md) | 마법별 결과·출처·실제 화면 판정·미구현 계약 |

## 실행 후 화면 판정 — 3회 완료

- 실행 폴더: [01](../runs/mage-stage6-20261031-01), [02](../runs/mage-stage6-20261031-02), [03](../runs/mage-stage6-20261031-03). 각 `verify-shots.json`, `result.json`, `mage-stage6-frames.json` 및 원 PNG를 보존했다.
- 01: key36/41/42/43/44의 실제 시전 이벤트와 비용·효과가 관측됐다. key45는 움직인/빈 대상 클릭으로 이벤트0·UNKNOWN, key46/47은 해당 종속 단계 SKIPPED. 첫 현재 페이지 캡처에서5/6페이지 좌표를 측정했다.
- 02: key41/45/47/42 성공. Sunburst가 가까운 대상을 처치해 key46 접근 대상 없음으로 UNKNOWN/SKIPPED. 03은46을 먼저 정상 접근·시전한 뒤45 피해50/처치를 확인했다. 각 성공 시전의 서버 errors는 빈 목록이다.
- **실제 화면 버그 수정**: Mighty 설명이 `MISSING_STRING_18446744073709551615`로 나왔다. `data/m1/buff_descriptions.json`에 고정 CommonSpell.f7의 **41→854,46→988,47→857**을 연결했다. 02의 Mighty/Bless tooltip에서 정상 한글 설명·남은 시간을 직접 확인했다. NPC Weakness 수신의 PC HUD 화면은 이번 실행 범위 밖이다.
- 실행 전마다 LC/LC.guard 및12000/14030 리스너0을 확인했고 중간에 끊지 않았다. 세 실행 모두 wrapper finally 완료·LC_LEFT0·캡처 설정 복원·DLL SHA256 `1d1f60a03144f0214bee56c4a875d4444d51811649135a1eaab82ec2e2899f75`를 확인했다. 수동 복원은 필요하지 않았다.
- 세 실행의 종료 분류는 모두 **FORCED_CLEANUP**, 정상 SourceQuit/로그아웃은 **UNVERIFIED**다. 이번 시전·화면 관측을 정상 종료나 전체 게임 PASS로 올려 말하지 않는다.
- 캡처 직접 검토용 축소본은 `_work/tmp/mage-stage6-20261031/`에 있다. 원 PNG 경로는 마법별 표에 연결했다. 6단계 실행2회 여유는 추가로 쓰지 않았다.

화면 판정 한계: 별도 형상을 미확인으로 남긴 짧은 gfx는 즉시/후속 정지 캡처에서 자세·주변 그림과 분리해 판정하지 못했다. 원 자원 존재·서버 효과 프레임 송신 시험을 픽셀 확인으로 대체하지 않았다.
