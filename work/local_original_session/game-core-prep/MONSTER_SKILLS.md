# 몬스터 특수행동 데이터와 실행 범위

## 데이터·출처 (2026-10-28)

고정 클라이언트 **26.09.29.2001**, 현재 등록 **277종**, 저장된 2026-10-28 공식 사전과 선정 L1J NPC 원문을 대조했다. 데이터는 [monster_skills.json](../../../tools/local_original_session/data/monster_skills.json)에 독립 등록했다. 기존 몬스터·드롭·스폰 표와 원본 클라이언트·자원·저장은 수정하지 않았다. 이 절의 활성 수는 **실행 소비가 가능한 LOCAL 데이터 후보 수**이며 실제 플레이 성공 수나 원본 동등성 완료율이 아니다.

| 조사 결과 | 종 / 행동 수 | 의미 |
| --- | ---: | --- |
| 등록 coverage | 277종 | 모든 template의 client 식별·공식 원문·선정 L1J NPC·mobskill·skills 확인 위치 포함 |
| LOCAL 활성 후보 | 174종 / 251행 | physical131, magic78, summon11, poison22, paralysis독4, silence4, slow1 |
| 활성만 있는 종 | 159종 | 현재 조사에서 선정 SQL의 지원 가능 행동 후보가 있음 |
| 활성·미확인 혼재 | 15종 | 지원 후보와 보류 행을 별도로 보존 |
| 보류만 있는 종 | 10종 | 특수행동 원문은 있으나 연결할 계약 부족 |
| 선정 L1J에 특수기록 없음 | 93종 | `local_policy_no_special_record`; 원본 무스킬 확정과 다름 |
| 보류 | 25종 / 31행 | 15종 혼재 + 10종 보류만 |
| 공식 특수행동 확인 / 원본 무스킬 확정 | 0 / 0종 | 277종 모두 원본 상세 행동은 `UNKNOWN` |

`physical`에는 선정 NPC의 일반 원거리 공격도 포함한다. 따라서 174종을 특별한 주문·상태이상을 가진 종 수로 해석하지 않는다. `magic`에는 `drain=true`인 칠 터치·뱀파이어릭 터치가 포함된다. 피해 공식 원문, 확률, 재사용, MP, 사거리, 속성, 효과 번호, 행동 번호, 소환 원문과 대응은 모두 `source=local_policy`다.

### 식별과 출처의 경계

- 고정 client의 `template_id`, 이름 토큰, 이름, SPR을 식별 기준으로 유지했다. `monsters[]`의 `registry_refs`, `mapping_policy`, `client_ref`, `client_scalar_fields`가 기존 대응과 원문 위치를 보존한다. native 번호필드를 주문·상태이상으로 추측해 해석하지 않았다.
- 공식은 [보존 사전](../../../tools/local_original_session/data/official/monsters.json)의 각 `source.raw_path`와 `source.url`을 따랐다. 277종 원문 필드 합집합은 `id/name/image/favorite/level/big/damageable/regionNames/rewards/formName`이다. **공격·마법·상태이상 설명 필드는 없다.** 예: [장로 API](https://api-goats.plaync.com/linclassic/v2.0/game/monster/7?locale=ko-KR), [구울 API](https://api-goats.plaync.com/linclassic/v2.0/game/monster/28?locale=ko-KR), [웅골리언트 API](https://api-goats.plaync.com/linclassic/v2.0/game/monster/31?locale=ko-KR).
- 공식 `lineageclassic.plaync.com`/`lineage.plaync.com` 범위로 구울 마비, 가스트 침묵, 셀로브, 바실리스크 마비, 데스나이트 헬파이어 및 공식 가이드의 독·마비를 웹 검색했다. 이번 검색에서는 공식 운영자가 쓴 종별 특수행동 설명 근거를 확보하지 못했다. 공식 도메인의 이용자 게시판, 리마스터·리니지M 자료, 제3자 설명을 클래식 공식 근거로 채택하지 않았다. 검색 실패는 해당 행동이 없다는 증거가 아니다.
- backend 참고는 `D:/SingleLineageRef/l1j-en-classic/db/l1jdb_m10.sql`의 **해당 선정 NPC 자신**의 `npc`, `mobskill`, `skills` 행이다. 모든 행은 line ref와 원문 열을 JSON에 보존했다. 기존 L1J 후보 선정은 별도 LOCAL 정책이며 exact original variant를 확정하지 않는다. 다른 종의 기술을 외형·이름만 보고 복사하지 않았다.
- 기존 [npc_magic_attacks.json](../../../tools/local_original_session/data/m1/npc_magic_attacks.json)은 일부 보통 원소마법 경로다. 신규 표가 그 기존 PASS나 생명주기를 자동 승계하지 않으며 중복 선택 방지는 runtime 소비자의 책임이다.

### 소비 스키마

최상위 `attacks[]`는 `enabled=true` 후보, `omitted[]`는 `enabled=false` 보류, `monsters[]`는 277종 조사 coverage다. 행 ID는 `7:mob:0`, `28:contact:4`, `31:contact:1` 등으로 고유하다. 런타임은 `template_id`로 소비하고 `npc_id`는 참고 backend 식별자다.

| 필드 | 계약 |
| --- | --- |
| `kind` | physical / magic / poison / paralysis / silence / slow / summon. drain은 magic의 `drain=true` |
| `chance_percent` | 후보별 원문 TriRnd. 선행 actNo 후보가 선택되면 뒤 후보는 같은 기회에 선택하지 않음 |
| `min_distance/max_distance` | TriRange 음수는 최대, 양수는 최소. physical Range와 양의 skill ranged는 추가 최대 제약 |
| `mp_cost/reuse_seconds/cast_interval_seconds` | 선정 SQL 원문. 원문 속도0을 임의 정상속도로 덮지 않음; runtime의 기존 기본주기 fallback은 별도 LOCAL 정책 |
| `parameters` | damage_value, damage_dice, damage_dice_count, skill_level, element_attr_raw |
| `element/effect_id/action_id` | SQL의 속성/표현 식별자. native 표시 동등성은 별도 검증 필요 |
| `area/area_width/area_height/skill_target` | 원문 영역·대상 메타데이터. 단일 PC 소비를 전체 AoE 완료로 확대하지 않음 |
| `on_hit` | 접촉독은 실제 물리 명중 후만 roll. 시전 후보로 취급하지 않음 |
| `duration_seconds/tick_seconds/tick_damage/delay_seconds` | 상태 지속/틱/피해/잠복. silence duration null은 해제까지 |
| `poison_color_effect_id` | L1J setPoisonEffect의 색 상태. native 시전 효과 ID가 아님 |
| `count_min/count_max` | 소환 **정규화한 포함 경계**. L1J nextInt(SummonMax)+SummonMin 보존 |
| `limit/trigger_count_limit` | TriCount에 따른 해당 기술 총 시전 횟수. 0은 원문 횟수 제한 없음 |
| `summon_limit/summon_radius` | 참고 서버 설정100 및 원문 randomLocation 반경8. 생존·누적 카운트 차이는 아래 참조 |

### 상태이상과 소환에서 확인한 원문

접촉독은 `L1Attack.java:1186~1205`가 생산한다. `poison_atk=1`은12%·3초마다5피해이며 `L1DamagePoison.java:76~82`에 PC 지속30초가 있다. `poison_atk=2`는12% 침묵독이며 `L1SilencePoison.java:54~58`의0 타이머는 치료 전까지다. `poison_atk=4`는12%·20초 잠복 후45초 마비이며 `L1ParalysisPoison.java:45~88`가 실제 지연과 해제를 연결한다. 숫자는 별도 L1J LOCAL 정책이다. 접촉독의 `setPoisonEffect(1)`은 색 상태이므로 `effect_id=0`, `poison_color_effect_id=1`로 분리했다. 이1을 native 4ED8 시전 gfx로 보내지 않으며 원본의 독 색·마비 상태표시는 미확인이다.

**`paralysis_atk`만 있는 괴물 눈·비홀더·바실리스크·코카트리스·하피 등의 접촉 마비는 활성화하지 않았다.** 원문 `L1Attack.java:1203`의 분기 본문이 비어 있어 확률·지속을 생성할 근거가 없다. 바실리스크·코카트리스의 별도 mobskill 공격은 피해 주문으로 원문 확인된 범위만 유지한다. `Poison Cloud`라는 이름만으로 독 지속효과를 추가하지 않았고, `Root Debuff`의 실제 제어 handler 미확정도 보류했다.

소환은 `L1MobSkillUse.java:165~185,518~552`가 원문이다. `SummonMax`는 upper bound가 아닌 난수 폭이다. 바포메트는2..7해골, 베레스는2..5켈베로스가 된다. 원문 `MaxServantSummons=100`(`config/server.properties:149`)과 `getServantSummonCount()>MAX_SERVANT_SUMMONS`는 **누적 생성 수** 기준이며 `TriCount`는 별도 기술 시전횟수다. 부모종료 정리·재생성·보상·저장 정책은 실제 런타임 구현 범위를 아래에 명시한다. 원본과 동일한 cap/주기라고 주장하지 않는다.

| 생산자 | template → 소환 template | 정규화 수 / 시전 한도 | 대응 |
| --- | --- | --- | --- |
| 바포메트24 | 29 해골 | 2..7 / 3회 | L1J45107을 공유하는 client25·29 중 기존 명시 l1j 대응29를 LOCAL 선정. 두 client의 동등성 주장이 아님 |
| 베레스216 | 182 켈베로스 | 2..5 / 3회 | L1J45241 대응 |
| 데스나이트63 | 30 스파토이 | 1..3 / 원문0 | L1J45161 대응 |
| 데몬332 | 581·288·586·707·589·287·325 | 각1..2 / 원문0 | 각각 선정 NPC와 현재 등록 template 대응 |
| 스피리드2403 | 2402 소환물 | 1..3 / 원문0 | L1J45794 대응 |

폭탄 꽃592는 `10034 Bomb Flower E`의 fire 피해 projectile 원문만 확보했다. 자폭·죽을 때 폭발·소환물로의 상태 전파·독 광역 확산은 별도 계약이 없어 만들지 않았다. `explode_status`는277종 모두 명시 자폭/사망폭발 계약 미확인으로 기록했다.

### 보류와 데이터 확인

2차 확인 후 보류31행은 마비 flag 미구현13, 유한 최대 사거리 부재6, 별도 buff/heal/cancel 소비 필요4, companion/self/random 대상 소비 필요3, NPC HP 비용2, root 제어 미확인1, physical range0 1, Poison Cloud ground/대상 계약1이다. 보류 행은 raw SQL과 사유를 보존하며 활성 표에 섞지 않았다.

JSON 파싱,277종 고유 coverage, 활성251/보류31행 ID 중복0, 활성 사거리 null/역전0, 소환 대상 등록 누락0, 활성·보류의 ID 교집합0을 확인했다. 277종 원문 필드 집합도 확인했다. 이는 **데이터 원문·연결 확인**이며 실제 서버 수신·HP/상태 소비·치유·소환 정리·원본 화면 검증 결과는 아래 별도 실행 절에서만 판정한다.

### 2차 원문 확인과 승격 (해독·데이터 담당)

메르키오르 `36:mob:0` 한 행만 LOCAL 활성으로 옮겼다. 선정 NPC45497의 `mobskill`은 `l1jdb_m10.sql:19985`, NPC는 `:21068`, EBolt4는 `:35624`다. `attr=16`과 피해8+1d10·MP3·TriRange−6·재사용10ms·시전800ms를 그대로 보존한다. `L1Magic.java:763~783`는 저항을0으로 시작해 Earth1/Fire2/Water4/Wind8만 선택하므로16은 어느 원소저항도 선택하지 않는다. 기존 `world_combat.elemental_defense`가 이미 같은 분기를 소비한다. 속성16의 이름은 `unknown`으로 남기고0이나 다른 원소로 치환하지 않았다. 새 시험에서 실제 HP 감소·MP3·쿨다운 거절과 저항0 분기 소비를 확인했다.

먼저 보존 공식 `data/official/monsters.json`과 `work/official_data_refresh_20261028/raw/monster/36.json`을 확인했으며 후자의9개 필드에도 행동 설명은 없다. [메르키오르 공식 API](https://api-goats.plaync.com/linclassic/v2.0/game/monster/36?locale=ko-KR)는 이번 web 도구 조회가 접근 오류였다. 공식 사이트에서 `메르키오르 에너지 볼트`, `해독제 침묵 마비 독`, `큐어 포이즌`, `비취 물약`을 추가 검색했지만 해당 상세 행동을 뒷받침하는 운영자 문서는 확보하지 못했다. 검색된 [필드 가이드](https://lineageclassic.plaync.com/ko-kr/guidebook/view?title=%ED%95%84%EB%93%9C+%EC%82%AC%EB%83%A5%ED%84%B0)는 출현/소개이며 이용자 게시판의 치료 주장은 근거로 쓰지 않았다. 승격은 공식 클래식 확인이 아닌 선정 L1J 소비 정책이다.

해독의 별도 backend 근거는 `C_ItemUse.java:471~484`의 비취물약→`pc.curePoison()`, `L1SkillUse.java:1783~1784`의 CURE_POISON→`cha.curePoison()`, `L1Character.java:524~528`의 소유 독 객체 `cure()` 위임이다. `L1ParalysisPoison.java:119~130`은 예약 취소·독 제거, `L1SilencePoison.java:56~61`은 침묵독 효과·독 제거를 소유한다. 이 공통 소유자 호출 관계를 기존 등록 훅으로 연결했다.

에틴 Haste `287:mob:0`·`760:mob:0`, 케레니스 FullHeal `902:mob:0`은 self/companion/random buff/heal 소비가 아직 없어 보류한다. Blizzard의 `884:mob:0`·`902:mob:1`도 NPC HP비용10 소비가 없어 보류한다. 나머지 사거리·빈 마비 분기·root·ground/area 등의 부족 계약을 추정으로 채우지 않았다.

해독·데이터 담당 변경은 `world_item_effects.py`, `data/monster_skills.json`, 신규 `monster_skills_cure_tests.py`, 이 문서다. 신규 consumer5개와 기존 item_effects/monster_skills 회귀를 함께 실행한 개발 시험은 **44개 통과(17.269초)**다. 잠복/발현 마비독·침묵독·피해독의 물약 치료, 저장/복원 후 재발 없음, 일반 마비/슬로우 보존, 마법의 같은 등록 훅과 실제 MP8 소비, detach callback 해제, EBolt 실제 피해·자원·재사용을 확인했다. 두 PC 시야를 공급하는 개발 fixture를 포함하며 소켓·게임·사용자 저장은 사용하지 않았다. 기존 시험 기대값은 수정하지 않았다. 전체 조합과 봇 결과는 통합 담당자가 별도로 기록한다.

## 런타임 연결

`world_feature_monster_skills.py`를 `world_handlers.FEATURE_MODULES`의 magic 다음에 등록했다. 실행 소유자는 `world_monster_skills.MonsterSkills`다. `runtime_started`에서 기존 `consumable_magic_provider`의 공개 엔진·save API와 `world_npc_resources`의 공유 MP를 얻는다. `world_magic_status.KINDS`에는 침묵독 저장·만료를 위한 `silence`만 추가했다. 기존 마법 모듈·전투 파일·몬스터 표는 수정하지 않았다.

기존 `runtime_extensions`로 AI `_fight`, `npc_attack`, `npc_swing`, 소환물 `_refill`, 공개 마법 `admit_cast`를 등록하고 종료 때 자신의 wrapper만 제거한다. EntityRef별 재사용·시전횟수·MP·부모 수명을 유지한다. 원거리·주문은 시야와 사거리를 통과한 현재 PC 또는 등록된 동료 대상으로 발동한다. 관리하는 마법종은 물리 fallback까지 한 공격 기회로 소유하여 기존 NPC 마법 selector가 같은 기회에 다시 roll/MP 소비하지 않게 한다. 동료 대상은 기존 `npc_magic_target` 공개 어댑터를 확장해 선택기를 재호출하지 않는 물리 피해·상태·저장 소비를 제공한다.

피해 주문은 기존 `npc_magic_swing`과 원소저항 계산을 재사용한다. 흡혈은 실제 제거한 HP와 시전자 최대 HP로 제한한다. 슬로우는 L1J NPC 확률 dice·leverage·MR·90% 상한을 적용하고 기존 counter/erase를 소비한다. 접촉독은 실제 물리 명중·양의 피해 뒤만 판정하며 잠복 마비독 재감염으로 발동 시간이 계속 밀리지 않게 한다. 독은 기존 독 tick/save, 마비·슬로우는 기존 상태 저장·이동·공격 소비 경로를 사용한다. 침묵은 공개 `admit_cast`에서 해당 요청만 거절한다. 근거가 있는 주문 gfx만 기존 `effect_frame`으로 4ED8에 보낸다.

소환물은 기존 spawner·AI·HP·사망 슬롯을 사용하며, 재생성하지 않는다. 부모가 죽거나 수명/활성 범위를 잃으면 자식 그룹·entity·예약을 정리한다. 소환물은 임시 월드 상태로 사용자 저장에 추가하지 않는다. L1J `L1MobSkillUse.java:527~529`의 `set_storeDroped(true)`와 `L1MonsterInstance.java:224~227`에 따라 소환물 시체의 일반 지상 드롭 생성만 등록 wrapper로 억제하고, 기존 경험치 경로는 유지한다. 일반 몬스터의 드롭과 유효 시체 검사에는 기존 처리를 사용한다. 클래식의 동일 정책과 화면 동등성은 미확인이다.

### 남은 접점

- 동료 대상 물리·마법·접촉독 선택기 접점은 2차에서 연결했다. `world_combat.py`와 코어는 수정하지 않았다. 동료 기능의 `CompanionMonsterTarget`이 기존 `npc_magic_target` 훅을 통해 피해·독·마비독·침묵독·슬로우 소비를 제공한다. 몬스터 기능은 동료의 private 상태나 메서드를 직접 호출하지 않는다. 동료 기능이 없으면 해당 대상 제공자가 없으며 PC 처리는 유지한다.
- 동료 기능의 `CompanionAilments`가 기존 `CompanionRecord.equipment`의 LOCAL 메타데이터에 상태와 잔여 시간을 저장한다. 오프라인 경과로 만료시키며 독 피해를 몰아 재생하지 않는다. `actor_action_status` runtime fold로 AI 이동·공격·시전을 제한하고, 제공자가 없으면 기본 행동을 유지한다. 몬스터 기능을 빼도 동료가 자기 상태의 틱·만료·치료를 소유한다. 해독약은 기존 ATS `function_items`에 설정된 경우 기존 가방 CAS와 소비 주기를 사용한다. 이 자동 사용 정책은 LOCAL이며 공식 자동사냥 규칙 확인으로 확대하지 않는다.
- 해독물약의 치료 접점은 2차 변경에서 연결했다. `world_item_effects.WorldItemEffects.attach`가 기존 `cure_poison(uid)` 등록 훅의 callback을 받고, 물약 소유자가 일반 피해독을 지운 뒤 같은 훅을 호출한다. 각 상태 소유자가 마비독·침묵독만 지우며 일반 마비·슬로우를 유지한다. 상태독만 제거돼도 `applied/poison_cured=true`, 기존 수량 제안1과 gfx192를 유지한다. detach에서 callback을 제거한다. 마법의 기존 훅 경로는 수정하지 않았다. 이 연결은 아래 개발 단위 소비 범위이며 원본 표시·클릭 검증은 아니다.

## 검증

`python -X utf8 -B -m unittest tools.local_original_session.monster_skills_tests`: 최초 **12개 통과**. 활성250행별 실행/쿨다운·MP·거리, 잠복 마비·치료·침묵, 슬로우 MR/카운터, 속성저항·실제 흡혈, 원거리 AI 단일 소비, 소환물 사망/부모종료/재생성 금지, EntityRef 변경·종료/재시작·magic 미등록 fallback을 확인했다. 이후 소환 드롭 보완을 추가한 최종 결과는 아래에 남긴다. 직접 함수 호출을 포함한 개발 단위시험이며 정식 플레이 PASS가 아니다.

실제 전체 `feature_registry()` import/build는226메서드로 성공했다. `SL_DISABLE_FEATURES=world_feature_monster_skills`에서222메서드이고 해당 초기화가 빠지는 것을 확인했다. 기존 `world_decoupling_tests`는19개 중18개 통과,1개는 다른 작업 파일 `world_feature_bonus_stat.py`의 BOM을 `ast.parse`가 거절하는 `U+FEFF` 오류다. 해당 파일이나 기존 시험 기대값은 수정하지 않았다.

추가 영향 회귀 `python -m unittest tools.local_original_session.npc_ai_range_tests tools.local_original_session.world_magic_tests tools.local_original_session.world_npc_resources_tests`는92개 집계 중89개 통과·1실패·2오류였다. 실제 존재하는91개 중 `WorldConsumerTests.test_job_second_erase_real_npc_damage_and_probability_consume_once`는 MR40 기대/실제1, `test_mana_drain_spell_npc_cast_and_weapon_use_same_actual_balance`는 `weapon_events[-1]` IndexError다. 두 fixture는 신규 monster 기능을 설치하지 않은 상태에서 실패해 기존 기대값을 수정하지 않았다. 나머지 import 오류1건은 존재하지 않는 `world_npc_resources_tests`를 검증 명령에 잘못 넣은 실행 오류다. 이를 제품시험 실패나 성공으로 합산하지 않는다.

### 봇: 대표3종 실제 수신

아래 명령을 지정 wrapper로 실행했다. wrapper가 적용한 실제 가속 배율은 로그의 `speedup=2.0`이다. 요청 환경값은10이지만 실제10배였다고 주장하지 않는다. `SL_TEST_PORT_BASE=58000` 단독 실행이며 원본 클라이언트는 실행하지 않았다.

```powershell
$env:SL_TEST_PORT_BASE='58000'
$env:SL_TEST_TIME_SCALE='10'
python -X utf8 -B C:\Users\Chansol\AppData\Local\Temp\claude\D--claude\0483de89-75e7-4b94-84b8-fb31fe00f575\scratchpad\fastbot\run_fast.py hunt_bot_monster_skills
```

결과는 [summary.json](../runs/monster-skills-natural-mkeoyau4/summary.json), 상세는 같은 디렉터리 `epoch-001~003/result.json`, 원문은 [실행 로그](../runs/monster-skills-launch-20261028-144141.log)다. **3종 모두 DEVELOPMENT socket PASS, exit0, 모든 epoch cleanup=true**다. 정상 FIRST·로그인·캐릭터 선택·월드·인벤토리 응답 뒤 수신한 NPC에 접근하고 실제 공격 요청으로 반격을 유도했다. CP57/realm 시작 오류는 발생하지 않아 재시도하지 않았다.

| 종 | 수신·실제 소비 확인 |
| --- | --- |
| 장로7 | 자연 CallLightning, 공유 MP60→42, 피해43/HP496→453, 실제4ED8 gfx10과4E38 HP453 수신 |
| 구울28 | 실제 명중 뒤 마비독,20초 잠복 뒤 실제4E30 요청을 보내도 자신의4E31 공격이 없고 대상 HP102불변 |
| 웅골리언트31 | 실제 명중 뒤 독 감염, 같은 감염의 next_tick이3초 전진, 실제4E38 HP410 수신. 관측 구간의 일반 물리피해와 독 피해량을 독립 분리한 판정은 아님 |

이 결과는 새 시험 저장·레벨 fixture와 실제 loopback 패킷/AI 소비 범위다. 원본 클라이언트 화면·입력·애니메이션·전체 클래식 동등성 PASS가 아니다. 증거 파일의 source_sha256은 해당 실행 조합 기록이며 요청 경로의 신규 핀·guard가 아니다.

봇 종료 뒤 소환물 일반 드롭 억제 wrapper와 해당 단위시험만 추가했다. 위 봇3종은 소환 행동을 쓰지 않으므로 해당 수신 결과를 재사용했다. 따라서 위 실행 해시는 소환 드롭 보완 전 소스이며 최종 파일 전체의 신규 봇 PASS로 바꾸지 않는다.

최종 동일 단위시험 명령을 통합 측에서 다시 실행해 **13/13 통과(10.982초)**를 확인했다. 추가한 실제 코어 kill/reward 시험에서 소환물 경험치 증가·지상 아이템0, 정확한 시체의 반복 드롭 억제, 옛 living ref 거절, 일반 몬스터 경험치 증가·지상 아이템1과 종료 후 wrapper 복원을 확인했다. 최종 런타임 해시는 `72005fc7f962dc5eaebfd2e532157002ecf22cadd004f659a6f5ca1dd9c40109`다.

## 변경 파일과 통합 인계

- 신규: `tools/local_original_session/data/monster_skills.json`, `world_monster_skills.py`, `world_feature_monster_skills.py`, `monster_skills_tests.py`, `hunt_bot_monster_skills.py` (후4개는 같은 tools 디렉터리).
- 국소 변경: `tools/local_original_session/world_handlers.py` 등록1행, `world_magic_status.py` silence1항목.
- 문서: 이 `MONSTER_SKILLS.md`. 기존 몬스터 표와 `world_combat.py`는 수정하지 않았다. git 커밋 없음.
- 핀 갱신 검토 대상 변경 소스: 위 신규·변경7파일. `start-manual-play.ps1`, `launcher.py`, 검증 프로필은 수정하지 않았으며 통합 담당자가 최종 선정판의 기존 핀만 갱신한다.
- 부모: 작업 시작 Git HEAD `f599fd7af903e0724999fff110601c8a724d52f0` + 이미 존재하던 동시작업 dirty 상태. 이 기능의 변경만 통합하며 다른 수정/미추적 파일을 포함하지 않는다.

남은 원본 확인: 공식 종별 특수행동 설명, 정확한 변종·주문·확률·주기·범위/AoE, 원거리 발사체와 주문 시전 동작, 독색/마비표시, 소환 보상·부모종료 정책, 명시 자폭 계약. 데이터에서 보류한31행과 원본 화면·입력 동등성을 완료로 확대하지 않는다. 동료 대상 신규 selector의 이번 연결·검증 결과는 통합 절에서 별도 판정한다.

## 2차 통합 검증·변경 범위

이번 변경 소스는 `world_monster_skills.py`, `world_feature_companion.py`, `companion_ai.py`, `world_item_effects.py`, `data/monster_skills.json`이다. 신규 시험은 `monster_skills_phase2_tests.py`, `monster_skills_cure_tests.py`, 신규 봇은 `hunt_bot_monster_companion.py`다(모두 `tools/local_original_session/` 아래). 기존 `*_tests.py`의 기대값은 수정하지 않았다. 핀 갱신 대상은 위 변경 소스 목록이며 `launcher.py`, `start-manual-play.ps1`, 지정 검증 프로필과 `docs/ACTIVE_TASK.md`, `world_combat.py`는 이 작업에서 수정하지 않았다. 커밋하지 않았다.

```powershell
python -X utf8 -B -m unittest tools.local_original_session.monster_skills_tests tools.local_original_session.monster_skills_phase2_tests tools.local_original_session.monster_skills_cure_tests tools.local_original_session.world_companion_rules_tests tools.local_original_session.world_item_effects_tests tools.local_original_session.world_companion_magic_tests tools.local_original_session.companion_ai_tests
```

최종 위 명령 **119/119 통과(39.788초)**. 원문은 [최종 단위 로그](../runs/monster-companion-final-unit-20261028-150605.log)다. 신규 동료 시험11개에는 단일 물리/마법 소비·접촉독 명중 조건·독틱·지연 마비의 실제 AI 차단·침묵의 시전 차단/기본공격 유지·저장복원·독성 상태만 치료·사망/부활 상태 정리·구 EntityRef 거절·기능 제외·ATS 해독 소비 경계가 포함된다. ATS 가방 CAS의 실제 패킷 소비는 아래 봇에서 별도 판정한다. 전체 기능 레지스트리와 동료 기능 제외/몬스터 기능 제외 레지스트리 빌드도 각각 성공했다. 개발 단위시험이며 원본 화면·입력 PASS가 아니다.

기존 최소 AI fixture에 event bus가 없는 경우가 추가 회귀에서 드러나 초기 선택 callback에 no-op 기본값을 두었다. 기존 `companion_ai_tests`와 `world_companion_movement_tests`, 신규11개는 합계42개 통과했다. 존재하지 않는 `companion_magic_tests`를 처음 명령에 넣어 생긴 import 오류는 실제 모듈명 `world_companion_magic_tests`로 정정했다. 원로그는 보존하며 제품 결함이나 성공으로 합산하지 않는다.

### 2차 봇: 동료 피독·해독

```powershell
$env:SL_TEST_PORT_BASE='58000'
$env:SL_TEST_TIME_SCALE='10'
python -X utf8 -B C:\Users\Chansol\AppData\Local\Temp\claude\D--claude\0483de89-75e7-4b94-84b8-fb31fe00f575\scratchpad\fastbot\run_fast.py hunt_bot_monster_companion
```

최종 **SUCCESS、exit0、cleanup=true**. [결과 summary.json](../runs/monster-companion-natural-dt4xpnf8/summary.json), [실행 원문](../runs/monster-companion-launch-20261028-151005.log). 요청 scale10의 idle 가상시계를 사용했으며 실제 전체 속도 향상은1.96배(실제7.104초/가상13.912초)다. CPU·입출력을 포함한 실행 전체가10배였다고 주장하지 않는다.

새 시험 저장의 기사/동료 레벨30·사냥터 시작위치·물약 공급 fixture를 명시했다. 정상 FIRST→로그인→캐릭터 선택→월드→소유 동료 소환 뒤 실제 ATS 설정 저장과 pet 공격 요청으로 웅골리언트31의 반격을 유도했다. 실제 명중·접촉독 이벤트 뒤 독틱 HP237→232(5피해)와4F14 HP232를 수신했다. 주인의 비취물약126을 GIVE 요청으로 전달해 주인 수량1→0, 동료가 받은1개를 ATS 자동사용하여 저장 가방 잔량0, `poison_cured=true`, `poison=None`을 자연 만료 전에 확인했다. 요청/기능 오류 목록은 비어 있고 정상 Quit/close를 완료했다. 이는 loopback 패킷·서버 실제 소비의 DEVELOPMENT 증거다. 원본 클라이언트는 실행하지 않았고 native 화면·입력·독색/마비 표시 동등성은 미확인이다.

실패한 준비 실행도 보존했다. `monster-companion-natural-fku2q9g_`는 새 fixture의 PositionStore 맵 전환 인자 누락, `monster-companion-natural-bba08gzq`는 봇의 주인 ATS 초기 저장 순서 누락(`SELF_CHARACTER_CONFIG_UNKNOWN`), `monster-companion-natural-7hkacjmf`는 봇이 M1 전용 수신 카탈로그를 써 확장 몬스터를 인식하지 못해 실패했다. 모두 cleanup=true였고 신규 봇 파일만 수정한 뒤 재실행했다. 공용 초기화 오류는 최종 실행에서 발생하지 않았다. 앞선 실패를 성공으로 바꾸지 않는다.
