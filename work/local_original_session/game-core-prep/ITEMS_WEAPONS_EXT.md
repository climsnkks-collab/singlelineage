# 클래식 무기 확장 데이터

2026-10-28 사용자 지정 데이터 작업. `items_ext/weapons.json`에 **73종**, 같은 ID의 `item_gfx_ext/weapons.json`에 **73종**을 추가했다. 기존 `items.json`의 무기 14종과 합쳐 **87종**이다. 최초 확장 시 기존 ID/행은 수정하지 않았으며, 후속 조사에서 확장 659·660·661의 미확인 4셀을 아래 L1J 로컬 정책으로 갱신했다. `starter.json`은 최초 작업에서 `test_knight.companion_supplies`에 마나의 지팡이342를 `item/count/icon = 342/1/293` 형식으로 1개 추가한 국소 변경뿐이다. 기존 키트 `entries`·지급 순서·사용자 저장은 변경하지 않았다.

신규 ID: 2,13,31,32,33,34,35,42,44,46,47,48,54,56,57,58,61,67,69,70,72,73,74,75,77,78,81,123,138,141,142,144,231,232,233,235,244,268,269,270,271,272,274,276,277,278,337,342,358,359,360,388,568,659,660,661,671,672,673,711,787,789,790,791,1094,1095,1096,1097,1285,2072,3018,3019,3020.

## 출처와 입력 단위

기준은 `tools/local_original_session/data/catalog/items_all.json` 1266행과 고정 클라이언트 `work/source_game_data/native-dump-v1.jsonl`, 그다음 `data/official/items.json`과 그 표가 참조하는 `work/official_data/raw/item/{id}.json`이다. 모든 신규 행은 client ID·한국명과 공식 ID·한국명이 대응한다. 공식 상세 URL은 `https://api-goats.plaync.com/linclassic/v2.0/game/item/{id}?locale=ko-KR`이며 기존 수집 원문을 재사용했다. 최초 온라인 조회는 공식 표에 없던771이었다(아래 미확인). 후속으로 659·660·661·3018을 다시 HTTP200 조회했고 기존 원문과 SHA256이 모두 같았다. 새 원문은 같은 폴더 `weapon-official-{id}-20261028.json`에 보존했으며 기존 공식 캐시는 덮어쓰지 않았다.

클라이언트에서 ID·이름토큰·이름·f5 아이콘·f6 바닥 그래픽·f13 직업·f10 무게를 가져온다. 직업은 현재 `items.json`과 동일한 해석(0군주/1기사/2요정/3마법사, f13 부재 시 네 직업)을 유지하며 공식 classNames와 대조했다. 원시 enum을 새로 복원했다고 주장하지 않는다. `weight.value`는 **f10 raw 원값**이다. 1000으로 나누어 입력하지 않는다. note의 표시 무게는 `floor(f10/1000)`이며, `ITEM_WEIGHT.md`의 이전 L1J 무게 입력 설명보다 현재 `items.json`의 client f10 정책을 따른다.

피해는 공식 `sdam.origin/ldam.origin`, 명시된 명중·추가 대미지는 공식 `options[].origin`, 안전강화는 공식 `enchantDescription`의 기존 derived 수치를 쓴다. client `meleeDmg/rangeDmg` 배열은 강화별 추가 배열이며 공식 기본 피해/장비 추가 대미지와 같은 의미라고 가정하지 않고 note에 원값을 보존했다. 공식 옵션이 없는 명중·추가 대미지는 대응 L1J 일반(bless=1) `weapon` 행을 **source=local_policy인 L1J 참조 backend 정책**으로 채웠다. `l1jdb`는 `D:/SingleLineageRef/l1j-en-classic/db/l1jdb_m10.sql`의 정확한 줄을 가리킨다. 이 선택은 native 등급·축복 변형 확정이 아니다. 후속 조사에서 4셀의 로컬 참고 근거를 연결했고 3018의 2셀은 아래처럼 명시적 UNKNOWN 중립값이다.

신규 73행 × 16셀 = **1168개 최상위 출처 셀** 중 client 511(43.75%), official 254(21.75%), local_policy 403(34.50%)이다. `source=l1j` 셀은 0이며 L1J 참고값을 local_policy로 명시했다. local_policy에는 슬롯·비중첩·무기 AC/회복 기본 처리 같은 서버 구조값도 들어간다. weapon.note 내부의 별도 출처는 이 분모에 중복 가산하지 않았다.

| 주요 필드 | 분모 | client | official | local_policy |
|---|---:|---:|---:|---:|
| weapon (small/large 한 셀) | 73 | 0 | 73 | 0 |
| hit | 73 | 0 | 21 | 52 (L1J 51, 미확인 1) |
| dmg_bonus | 73 | 0 | 14 | 59 (L1J 58, 미확인 1) |
| classes | 73 | 73 | 0 | 0 |
| weight | 73 | 73 | 0 | 0 |
| safe_enchant | 73 | 0 | 73 | 0 |
| weapon_type | 73 | 0 | 73 | 0 |
| 위 7필드 합계 | 511 | 146 (28.57%) | 254 (49.71%) | 111 (21.72%) |

타입은 공식 분류를 기존 서버 키로 옮겼다. 신규 sword24/blunt7/spear17/bow11/dagger1/staff10/twohand3, 합73이다. '도끼'라는 이름만으로 axe를 추측하지 않고 공식 둔기는 blunt로 둔다. SQL `tohandblunt`는 공식 둔기→blunt, `singlebow`는 공식 활→bow이며 미지원 제외 항목으로 다시 세지 않는다. 신규 데이터에 현재 서버 키 밖의 무기 타입은 없다.

## 양손·마법과 스키마 미완

각 행의 `weapon.note`에 JSON 문자열로 `two_handed`, 출처/ref, 공식 전체 옵션/설명/재질/손상 여부/착용레벨/oneHanded 원값, 공식 피해 원값, 클라이언트 능력치·강화별 배열과 L1J 원행을 보존했다. 이 위치는 `_Fields`가 읽으므로 `ItemDef.sources['weapon'].note`에서도 확인할 수 있다. 양손 출처는 공식54/로컬 L1J18/UNKNOWN1(천사의 지팡이3018)이다. 공식 `양손` 옵션이나 `한손검/단검` 분류·명시 '한손' 설명을 우선하고, 없는 경우 L1J 타입 및 `templates/L1Weapon.java:97-105`를 로컬 참고로 사용했다. `oneHanded`는 공식 수집 문서에서도 의미 미확정이므로 단독 판정에 쓰지 않았다.

마나의 지팡이342: client `native-dump:1223`, 토큰$1063, icon293/ground30068, 피해3/3·명중-3·추가피해0(L1J 로컬 참고)·직업[3]·무게raw15000(표시15)·안전6. 공식 `마나 흡수`와 '대상을 때릴 때마다 MP를 조금씩 뺏어오는' 설명을 보존했다. 양손 여부 false는 L1J staff 타입/함수에 따른 로컬 참고이며 공식 `oneHanded=false`만으로 확정한 값이 아니다.

현재 `ItemDef`/소비자에 별도 연결이 필요한 계약은 다음과 같다. 이번 데이터 작업은 동작을 추가하지 않았다.

- 양손 여부와 방패 동시 착용 제한. `weapon_type`/자세만으로는 양손 창·둔기·한손활을 표현하지 못한다.
- STR/INT/SP, 최대HP/MP회복 같은 장비 능력치, 강화 단계별 client 배열, 재질/언데드 추가효과·관통·손상 여부·착용레벨.
- 마나 흡수342, 헤이스트144, 무형화살568, 발동 마법789/1094/1096/2072/3018/3019/3020의 발동률·대상·피해·비용·수명. 공식 이름·설명만 보존되며 수치·실제 소비 계약은 미확인이다.
- 안전강화 수치와 별개인 `enchantable` 정책. 659/660/661/671/672는 인챈트 불가이며 safe_enchant는 null이다. 기존 강화 소비자가 이 note를 읽어 금지한다고 주장하지 않는다.

## 제외와 미확인

catalog `kind=weapon`은 105행이다. 기존14 + 신규73 + 아래16 범위제외 + 아래2 근거부족 = 105다. 캐시/이벤트/시험 변형을 원래 일반 장비로 합치거나 원본 ID를 생성하지 않았다.

| 제외 구분 | ID/이름 | 근거/경계 |
|---|---|---|
| 무명 시험 후보 6 | 10016,10017,10018,10020,10021,10022 | client name/token 부재, 공식/SQL 대응 없음. 시험용이라는 native 의미까지 확정하지 않으며 일반 장비 근거 부족으로 제외 |
| 개인화/특수 변형 4 | 12035·12584 `%i의 은장검`, 12036·12585 `%i의 사냥꾼 활` | 일반 고유명 대신 `%i` 템플릿, 공식 일반 장비 대응 없음. 일반358/388에 합치지 않음 |
| 이벤트 변형 6 | 12421 청명한 싸울아비 장검,12422 청명한 달의 장궁,12423 시원한 마나의 지팡이,12424 청명한 뇌신검,12602 청명한 천사의 지팡이,12603 청명한 사이하의 활 | client 특수 이름과 f54 변형 그래픽, 공식 일반 장비 대응 없음. 이벤트/특수 범위로 제외 |
| 피해/종류 미확인 1 | 771 고대의 하프 | client f45=1/f46=2는 있으나 하프를 원본 bow로 확정하지 않음. L1J 토큰 대응 없음. 2026-10-28 공식 상세 API는 HTTP200 `{}`; 원문 `weapon-official-771.json`. 피해·명중·안전강화 근거 부재 |
| 종류 미확인 1 | 2586 날이 빠진 무기 | 공식 피해1/1은 있지만 categoryName이 없고 native f46=0은 검/단검 공통이다. SQL 대응은 etcitem41206으로 weapon 종류 충돌. 임의 sword 확정 없이 제외 |

공식 전체 무기분류는 한손검27/창19/활15/둔기12/지팡이11/단검7/양손검4 = **95종**이다. 이 중 고정 클라이언트 무기87종, 화살3종(29화살/68은화살/258미스릴화살, catalog kind=ammo), 고정 버전 ID 부재5종(1283미스릴 단검,1497샴쉬르,1783수정 단검,12651커트라스,15476강철 단검)으로 나뉜다. 화살은 무기 확장에 중복 추가하지 않으며 다른 ammo 데이터 범위다. 공식만 있는 5종은 `client_mapping.status=id_absent_in_fixed_client_dump`이므로 아이콘/바닥 번호를 추측하거나 다른 ID로 연결하지 않았다.

고정 catalog의 실제 weapon/L1J 후보에는 이도류(edoryu), 크로우(claw), 키링크, 체인소드 같은 추가 무기종의 client ID 후보가 없다. L1J 전체 무기 목록을 고정 클라이언트에 역으로 수입하지 않았다. 유일한 하프771은 위 근거부족 항목이며 '미지원 타입 수'로 중복 가산하지 않는다. 명시 캐시 판정 근거를 가진 추가 weapon 행은 발견하지 못했으며 모든 특수 변형을 캐시라고 단정하지 않는다.

최초 추가 시 미확인 숫자는 **659·660 dmg_bonus, 661·3018 hit/dmg_bonus = 6셀**이었다. 후속 조사는 catalog의 exact-token 후보가 놓친 SQL 복합 토큰 `$1958 $1938/$1939/$1940`과 공식 `name2`의 '봉인된 잊혀진' 명칭을 연결했다. 다음 4셀은 원본 확정 대신 출처·충돌을 남긴 **local_policy**다.

| client ID | 로컬 참고값 | SQL 원문 | 대응·충돌 |
| --- | --- | --- | --- |
| 659 | dmg_bonus 3 | `l1jdb:63718 weapon17 Sealed Forgotten Great Sword` | itemdesc659·토큰접미사$1938·종류·icon90·f10=80000 대응. SQL 피해3/6과 공식2/3은 다르므로 공식 피해 유지 |
| 660 | dmg_bonus 0 | `l1jdb:63719 weapon18 Sealed Forgotten Sword` | itemdesc660·토큰접미사$1939·종류·icon103·f10=40000·피해3/2 대응 |
| 661 | hit 0, dmg_bonus 0 | `l1jdb:63868 weapon167 Sealed Forgotten Bowgun` | itemdesc661·토큰접미사$1940·종류·f10=50000·피해1/1 대응. SQL icon278과 client20은 다르므로 client 아이콘 유지 |

세 행 모두 SQL f6·착용레벨/강화정책은 고정 client/공식과 다르다. 이 로컬 참고 연결은 원본 밸런스나 변형 동일성의 증명이 아니다. 공식 옵션 부재에서 0을 도출한 것이 아니며, 표에 적은 SQL 열을 읽었다.

남은 미확인 숫자는 **3018 hit/dmg_bonus 2셀**이며 임시 중립값0과 UNKNOWN note를 유지한다. 양손도 null/UNKNOWN이다. L1J261 `Arch Mage`s Staff`(`l1jdb:63957`)는 icon2915·ground6737·f10=20000·itemdesc3018·피해12/12가 같지만 이름·토큰(client$13819/SQL$5489)·발동(공식 턴 언데드/SQL 디지즈)이 다르다. hit5·damage0·한손을 이식하지 않았고 `weapon.note.unadopted_l1j_reference`에 이유를 남겼다. 공식 `oneHanded=false` 단독으로 한손을 확정하지 않았다. 일반 데이터 추가는 완료했으나 위 미확인·스키마 동작까지 완성된 것은 아니다.

## 특수효과 후속 조사

공식은 342 마나 흡수, 144 헤이스트효과, 568 화살 미장착 시 무형 화살, 789 파이어 애로우, 1094 콘 오브 콜드, 1096 이럽션, 2072 문라이트 이럽션, 3018 턴 언데드, 3019 콜드 체이서, 3020 일렉트릭 쇼크의 **효과 존재/이름**을 제공한다. 고정 client의 강화별 `meleeDmg/rangeDmg` 배열을 발동률/발동피해로 해석하지 않았다. 공식 상세에 그 계산·확률은 없다.

L1J 참고 계산은 구현 담당에 별도로 전달했다. 342↔L1J126은 토큰$1063·명칭·icon293·f10=15000 대응이며 `L1Attack.java:1208-1221`은 명중 후 1..(강화+3) 균등 흡수, `Config.java:572` 공격당9 제한이다. NPC는 `L1NpcInstance.java:2094-2104`에서 요청/현재MP/누적잔여 중 작은 값, `Config.java:570` 생애 누적40 제한이다. `L1MonsterInstance.java:247-253`의 실제 hit 성공 후 계산, `L1Attack.java:1442-1453`의 반환량만 양측 MP에 적용하는 연결을 따른다. 음수 강화의 `nextInt(0)` 원결함까지 복제하지 않는다. 고정 client에 L1J127의 토큰$2003 대응은 없으므로 별도 마나 지팡이를 추가하지 않았다. 이 수치는 공식 Classic 확정이 아닌 **local_policy**다.

발동 피해 참고는 `L1WeaponSkill.java:402-410`의 공통 식으로 N=max(INT,18)+max(SP,13), `N×(배율×1.5+버서커상태0.2)+uniform(0..N-1)×배율×1.5`다. Bapho124↔1096은 :420-425의 14%·배율1.8·Earth 단일, Thunder264↔3020은 :428-433의 4%·배율2·Wind 단일, Frozen263↔3019는 :333-339의 5%·배율1.4·Water·대상 중심 반경3이다. 면역/MR/속성 감소는 :475-518을 별도로 적용하므로 단순 고정 피해와 다르다. 1094/2072는 `USE_INT_PROCS` 설정에 따라 테이블/INT 계산 경로가 갈리고, 3019 공식 콜드 체이서와 L1J 즉시 광역 피해도 효과 계약이 다르므로 값만 가져와 원본 동작으로 확정할 수 없다. 789 대응184는 참고 `weapon_skill`에도 계산이 없고 3018은 위 identity 충돌이 있어 미확인으로 남겼다. 이 문서의 자료 조사는 특수효과 동작 PASS가 아니다.

## 등록형 효과 구현과 실제 봇 결과

### 무기 효과 2차 연결(2026-10-28, 현재 코드)

144 장착 헤이스트는 코어 `WorldCombat.haste_modifiers`에 등록한다. 현재 `world_magic.py`·`world_feature_magic.py`에는 haste 생산자가 없고 `world_magic_status.ai_status`의 slow/berserk가 기존 speed wrapper에서 별도 곱해진다. 따라서 이전의 마법 기능 존재만으로144 전체를 끄던 gate를 제거했다. 물약 haste와 무기144는 같은 category에서 `min(기존 haste, 물약17 rate0.745)` 한 번, brave는 별도 곱이며 마법 slow/berserk의 현재 배율은 보존한다. 무기 해제·저장 장비 재선택·종료는 장비 조회/등록 해제로 처리하고 물약 상태를 삭제하지 않는다. 명시적 로컬 합성 정책이며 원본의 haste/slow 상호 취소는 **UNKNOWN**이다.

568은 실제 소유 화살29를 먼저 제안하고 기존 비용 owner가 공격당1개를 소비한다(빗나가도1개). 화살이 없을 때만 가상 화살 die1..15·비용없음으로 fallback한다. range=-1은 L1J SQL190/205, die15는 L1Attack.java:806-807을 로컬 정책으로 채택했다. 순수 `world_ammo.prepare_attack`의 일반 bow11 정책을 임시 ItemDef 복사에서 재사용하며 실제 무기·저장 template/UID를 변경하지 않는다. 비용 소비·저장·wire는 기존 `world_feature_combat._world_prepare_pc_attack`에 남고 가상 아이템/UID를 만들지 않는다. `world_ammo.py`는 수정하지 않았다.

2072는 실제 화살 비용·일반 Arrow66을 연결하고 실제 양수 물리 명중의10% 발동에서 별도 ArrowType6288을 보낸다. SQL205 fixed8/random0의 **발동 추가피해0**은 그대로다. 568 무형 화살은 ArrowType2349이며 실제 화살은66이다. L1Attack.java:1285-1294 및 L1WeaponSkill.java:264-275의 ArrowType/SkillSound 구분을 따르되, 고정 Classic의 `SC4E31 f7`에2349/6288을 대응시킨 것은 **LOCAL 표현**이다. 네이티브 투사체·좌표·추적/렌더링 동등성은 **UNKNOWN**, 표적4ED8로 대체하지 않는다. 789 확률/피해와3018 턴언데드 발동률/성공식·hit/dmg_bonus/양손은 **UNKNOWN/비활성**을 유지한다.

최소 등록 계약(등록자가 없으면 기존 동작):

- `WorldCombat.haste_modifiers`: `modifier(haste_factor, uid, now) -> haste_factor` 순서대로 호출. 기본 물약 haste factor1 또는 실제 활성값을 받아 brave 등 다른 buff와 나중에 곱한다. 무기 feature가 자기 contributor를 등록/종료 해제한다.
- `bow_ammunition`: `fold(prepared, pc_uid, weapon, stacks, target, now) -> AttackPreparation`. 비용 확정 직전의 읽기 전용 제안 변환이다. 기본값은 `world_ammo.prepare_attack` 결과이며 등록자 없으면 동일. 비용 owner는 `cost is None`이면 소비 없이 허용 결과를 반환하고, 실물 cost는 기존 소비/거절 경로를 한 번만 사용한다.
- `WorldCombat.projectile_modifiers`: `modifier(projectile, uid, target_uid, prepared, now) -> projectile`. 기본66, `world_visibility.pc_attack`의 발사1곳에서 `projectile_for`를 호출한다. `attack_frame(..., projectile=66)`의 기본 송신은 불변이다. 2072 발동 투사체는 발동 gate 뒤 같은 ArrowType encoder를 별도 사용한다.

기존 `world_weapon_effects_tests`는 코어 selection/stats/hook NS fixture만 보완했고 게임 기대값은 변경하지 않았다. `world_combat_requests_tests`에도 새 fold의 기본반환 fixture1줄만 주입했으며 기대값은 불변이다. 새 직접 영향 시험은568 실물우선/빗나감비용/고갈fallback/가상die/거리·cadence·commit거절,2072 일반66+발동6288/10%경계/피해0,144 물약·brave·마법slow/berserk 별도합성을 검증한다.

검증: 첫48시험은 cleanup 중복호출/NS fold fixture 오류와 외부 BOM 오류 등6 ERROR(`runs/weapon-second-unit-20261028.txt`)로 보존했다. 수명 cleanup과 fixture를 수정한 두 번째4모듈은 **52시험 중51 OK/외부1 ERROR**(`runs/weapon-second-unit2-20261028.txt`,19.654s). 남은 오류는 선언 AST reader가 범위 밖 `world_feature_bonus_stat.py`의 UTF-8 BOM(U+FEFF)을 읽지 못한 것으로 무기 실행 오류가 아니다. 해당 파일·reader를 수정하거나 우회하지 않았다.

동일4모듈 재확인도 **52시험 중51 OK/동일 외부 BOM1 ERROR**(`runs/weapon-second-unit3-20261028.txt`,24.310s)다. 코어 실제 물약속도 만료와 마법 slow의 이동/공격 deadline 기존2시험은 **2 OK**(`runs/weapon-second-speed-20261028.txt`,0.900s)다.

봇 첫 시도는 **시작 전 차단/fixture 없음**: `ModuleNotFoundError: tools.local_original_session.world_feature_monster_skills`. `runs/hunt-weapon-effects-jyzticsp/summary.json`(epochs없음·cleanup_complete=true), 콘솔 `runs/weapon-second-bot-20261028.txt`에 보존했다. 모듈 도착 후 두 번째(base50000/offset2)는 `data/m1/monster_skills.json` 미도착 `FileNotFoundError`로 **시작 전 차단/fixture 없음**이었다. `runs/hunt-weapon-effects-dinedtat/summary.json`(epochs없음·cleanup_complete=true), 콘솔 `runs/weapon-second-bot2-20261028.txt`에 보존했다. 외부 기능 등록과 모듈/데이터 도착 사이 통합 조합이며 무기8종 PASS로 확대하지 않는다. 원본 클라이언트는 실행하지 않았다.

현재 변경/핀 검토 대상 제품 파일은 `world_combat.py`, `world_visibility.py`(발사 presentation 소비1곳), `world_feature_combat.py`(비용 fold/cost없음 처리), `world_feature_weapon_effects.py`, `hunt_bot_weapon_effects.py`다. 시험 fixture2개·신규 직접 영향 시험과 본 문서는 제품 핀 대상과 구분한다. launcher/start-manual-play/validation profiles/ACTIVE_TASK/원본/사용자 저장은 수정하지 않았다.

직접 무기2모듈은 위52시험 로그에서 **31개 모두 OK**(weapon_effects16+weapon_proc_effects15)다. 봇 기본은 독립 저장8종342/144/568/2072/1094/1096/3019/3020이며,568/2072는 실제 화살 소비 뒤 정상 Quit→새 FIRST의 화살수·장착무기 복원도 확인하도록 작성했다. 외부 데이터 도착을 약60초 기다린 마지막 확인에서도 `data/m1/monster_skills.json`은 없었으므로 불필요한 세 번째 실행은 하지 않고 **시작 전 차단**으로 마감했다. 해당 새 봇 행동의 실행 PASS는 아직 없다. 마지막 수정 봇은 syntax compile OK다.

현재 단위시험 명령과 기본8종 봇 재실행 명령:

```powershell
python -X utf8 -B -m unittest tools.local_original_session.world_weapon_effects_tests tools.local_original_session.world_weapon_proc_effects_tests tools.local_original_session.world_combat_requests_tests tools.local_original_session.world_ammo_tests -v
python -X utf8 -B -m unittest tools.local_original_session.world_ai_tests.AiTests.test_speed_potions_shorten_attack_interval_until_expiry tools.local_original_session.world_magic_tests.StatusAiConsumerTests.test_slow_is_consumed_by_actual_move_and_attack_deadlines -v
$env:SL_TEST_TIME_SCALE='10'
$env:SL_TEST_PORT_BASE='50000'
python -X utf8 -B C:\Users\Chansol\AppData\Local\Temp\claude\D--claude\0483de89-75e7-4b94-84b8-fb31fe00f575\scratchpad\fastbot\run_fast.py hunt_bot_weapon_effects --navigation-timeout 600 --port-offset 4
```

### 이전 후속 구현(2026-10-28, 2차 연결 이전 코드)

아래의 기존 342 단독 결과와 데이터 조사 시점 이후 `world_feature_weapon_effects.py`를 확장했다. JSON `special_effects.runtime_status`는 **이전 데이터 조사 시점 기록**이며 현재 실행 상태로 자동 갱신되는 필드가 아니다. 이번 구현은 JSON 수치·아이템 행을 수정하지 않았다. 공식 10종의 보존 상세 `work/official_data/raw/item/{id}.json`의 옵션 원문과 아래 L1J 원파일/SQL 내용을 직접 확인했다. 모든 확률·피해·속도 계산은 별도 **local_policy**이며 Classic 확정값이 아니다.

| 무기 | 현재 연결과 한계 |
|---|---|
|144 광전사의 도끼|코어 장착 조회→속도 소비. 기존 haste 물약과 같은 category로 1회만 적용하고 brave는 별도 곱, 해제 때 물약 원상태 유지. 물약17의 기존 rate0.745 재사용. 마법 기능이 켜졌는데 아래 haste contributor가 없으면 중복 가속을 막고 **UNKNOWN/비활성**. 저장장비 재조회로 복원하며 독립 영구 buff를 저장하지 않음.|
|342 마나의 지팡이|실물리 양수 명중→공용 EntityRef NPC MP 소유자 차감→PC MP clamp·4E38. 기존1..(강화+3)/공격당9/생애40 재사용. 코어 `_world_stats_for`에서 실제 착용 무기/강화 조회. 다른 선택 기능 private 참조 제거.|
|568 사이하의 활|**미연결**. L1Attack.java:806-807의 가상 화살 die1..15, :1292-1294의 projectile2349는 확인했으나 기존 `world_feature_combat._world_prepare_pc_attack`→`world_ammo.prepare_attack`이 지원하지 않는 bow를 비용 확정 전에 거절한다. 비용 owner 안의 `bow_ammunition` fold(기본 제안, pc_uid, weapon, stacks, target, now)가 필요. 실제 화살 우선/소비와 fallback을 같은 owner가 확정해야 하며 우회·가상 UID 생성 안 함. projectile의 고정 client 표현 대응은 UNKNOWN.|
|789 화염의 활|**UNKNOWN/비활성**. 공식 파이어 애로우 존재 외에 L1J184의 확률·피해 생산자가 없음. 일반 bow range/화살 접점도 위와 같음.|
|1094 얼음 여왕의 지팡이|L1J SQL121의 USE_INT_PROCS=false 경로를 명시 채택:25%,95+uniform(1,55),Water·단일, gfx1810→4ED8. INT ProcMap의 random0 경로를 피해식으로 잘못 채택하지 않음.|
|1096 바포메트의 지팡이|L1WeaponSkill.java:420-425,14%,INT/SP 식·배율1.8,Earth·단일. 원문 gfx129는 좌표 EffectLocation이므로 target UID의4ED8로 변환한 **로컬 표현**이며 원본 좌표 연출 동등성 UNKNOWN.|
|2072 달의 장궁|확률10%·SQL205 fixed8/random0의 실제 gate를 보존하여 **발동 판정은 있어도 피해0**. gfx6288은 원문 ArrowType이라4ED8 target으로 잘못 보내지 않음(투사체 UNKNOWN). 일반 bow range/화살 owner가 미지원하여 정상 소켓 발동도 미연결.|
|3018 제로스의 지팡이|**UNKNOWN/비활성**. 공식 턴 언데드의 무기 발동률·성공식 없음. L1J261 Disease를 이식하지 않음. 명중·추가피해·양손 UNKNOWN도 유지.|
|3019 혹한의 창|L1J263 즉시 반경3 NPC 광역을 **별도 로컬 정책**으로 채택:5%,INT/SP 식·배율1.4,Water,gfx1804. 실제 EntityRef 스냅샷·세대 확인 뒤 일반 HP/죽음/보상 소비자로 전달. Classic 콜드 체이서의 지연/추적/연속타·정확한 대상 규칙은 UNKNOWN.|
|3020 뇌신검|L1WeaponSkill.java:428-433,4%,INT/SP 식·배율2,Wind·단일,gfx10→4ED8.|

INT 식은 N=max(INT,18)+max(SP,13), N×(배율×1.5+버서커0.2)+uniform(0,N-1)×배율×1.5다. 코어 실제 INT와 공식 장비 SP를 읽고, 미제공 active spell SP/berserk/originalMagicHit는 다음 훅에서 받아야 한다. 기본 originalMagicHit0/비버서커/SP하한13은 명시적 로컬 baseline이다. MR 감소는 L1WeaponSkill.java:475-518을 적용하며 기본 NPC 속성저항0/면역false는 기존 일반 NPC baseline이다. 마법의 live counter_magic/freeze/속성저항·MR 변경과 병용한 완결성은 아직 입증되지 않았다.

**부족한 공개 contributor(모두 동기 fold, 등록자 없으면 기본값):** `weapon_proc_attacker(value, uid, now)`는 `{template,enchant,intelligence,spellpower,berserk,original_magic_hit}`를, `weapon_proc_defense(value, attacker_uid, target_ref, element, now)`는 `{mr,resistance,immune,original_magic_hit}`를 변환한다. 생산 위치는 `world_feature_magic.py`의 기존 마법 상태 소유자이며 현재 미등록이다. `weapon_haste_factor(value, uid, now)`는 이미 최종 `speed_factor`에 곱해진 haste/slow category의 전체 interval factor를 반환해야 한다(물약 contribution 포함). 소비는 이 무기 기능의 runtime speed wrapper이며 마법 private 상태를 읽지 않는다. 중복 category를 제거할 수 없는 현재 구성에서는144 효과가 UNKNOWN으로 남는다.

추가 마법 피해는 한 번 계산한 값을 고정한 뒤 대상별 방어만 적용한다. 광역의 secondary kill/reward로 레벨이 변해도 메인 roll을 재계산하지 않는다. 보고 `damage`는 **방어 감소 후·현재 HP clamp 전(overkill 포함)** 합계이며 실제 HP 손실 총합이 아니다. 마법 발동을 재귀시킨 추가타나 별도 보상 경로는 만들지 않았고, 일반 `_apply_monster_swing`의 HP·AI·죽음·보상·정리 경로를 재사용한다.

새 `world_weapon_proc_effects_tests` **11 tests OK(9.855s)**: 각 수치효과 hit/miss·확률 경계, SQL96/150·INT/SP clamp·버서커·2072zero의 정확식, 물리+proc HP 소비, MR/속성/면역 contributor, 반경3/4·secondary lethal cleanup/reward·고정 메인 roll, 마나 고갈/clamp·상태, haste/brave·해제·마법 미제공 gate·선택기능 제외/종료 복원을 검증했다. 원문 `runs/weapon-procs-unit-20261028.txt`. 기존32시험 묶음은 **10 ERROR**(`world_weapon_effects_tests`의 이전 NS fixture가 `_world_pcs`/`has_hooks` 코어 계약을 주입하지 않음)이며 `runs/weapon-procs-regression-20261028.txt`에 보존했다. 기존 시험 기대값을 수정하거나 제품에 private fallback을 추가하지 않았다.

후속 봇은342/1094/1096/3019/3020을 서로 독립적인 prelogin 저장으로 정상 FIRST/login/선택/world→실제CS4E30→수신4ED8 또는4E38→정상 종료 순서로 시험하도록 확장했다. 342에는 기존 Quit→새 FIRST/login 복원도 유지했다. 포트base49000의 기존+2030은51030이므로 build_epoch 안에서만 reserve/listener를 동일49000/49001로 지정한다. 첫 실행은 기존 타 PID30532의49000 listener와 충돌해 **FAILED/fixture생성 전/cleanup 정상**이었다. 원문 `runs/weapon-procs-bot-20261028.txt`, `runs/hunt-weapon-effects-whq4vtaw/summary.json`. 타 프로세스/예약은 변경하지 않았다.

같은base에서 `--port-offset 2`로49002/49003을 사용한 `runs/hunt-weapon-effects-rnhlmj0r/summary.json`은342 단독흡수·Quit저장·새FIRST복원 **SUCCESS**,1094 자연사 **UNCONFIRMED**였다.1094만의 낮은레벨 사냥·실물약 사용을 추가한 `runs/hunt-weapon-effects-6b5vpt9a/summary.json`도261회공격·실물약20개소진 후 `LOW_HP_NO_RECEIVED_POTION14`로 **FAILED**였다. 두 실행의 모든epoch broker failure_code는null·cleanup정상이며 실패/소진 저장을 보존했다.

원인은 물약량이 아닌 시작 생성 스탯과 무기 기본피해의 조합이다. 기존 mage fixture는STR8(STR_DMG[8]=-2),1094의 공식 small2는die1..2이므로 일반 코어물리피해가 항상0이하이고 `pc_hits_npc`가Swing(False,0)을 반환한다. 양수 물리명중을 요구하는 발동이 안 나는 정상경로다.1094 전용 새 prelogin 생성에서만 STR8→13/INT18→13(합계75불변)을 선언하고, 실제 공격profile 및 수신용4E31 raw hit 필드를 읽기관측에 추가했다. 사후HP/스탯대입·강제명중·RNG변경은 없다.

수정봇의 최종 기본5종 최소 후속 명령은 다음과 같다. 해당 runner가 모듈 prefix를 직접 붙이므로 인수에 `tools.local_original_session.`을 중복하지 않는다.

```powershell
$env:SL_TEST_TIME_SCALE='10'
$env:SL_TEST_PORT_BASE='49000'
python -X utf8 -B C:\Users\Chansol\AppData\Local\Temp\claude\D--claude\0483de89-75e7-4b94-84b8-fb31fe00f575\scratchpad\fastbot\run_fast.py hunt_bot_weapon_effects --navigation-timeout 600 --port-offset 2
```

첫 최종 시도 `runs/hunt-weapon-effects-ornnm4v7/summary.json`은 범위 밖 `tools/local_character_creation/realm.py`가 병행 변경되어 기존 `tools/local_native_login_local_ack_hook/ack_enter_world.py:20-21`의 `EXACT_CHARACTER_CREATION_REALM_REQUIRED`에서 **FAILED/fixture 없음/cleanup 정상**이었다. 이 파일의 `REALM_SHA`와 `tools/local_native_login_self_actor_hook`의 기존 profile source pin은 통합 담당 소유이며 무기 worker가 갱신하거나 우회하지 않았다. 원문 `runs/weapon-procs-bot-final-20261028.txt`. 이후 독립 단위 재실행도 기존 pin에 막혔다(`runs/weapon-procs-final-unit-20261028.txt`: realm import 실패, `runs/weapon-procs-independent-unit-20261028.txt`: CP57_PROFILE_SOURCE_CHANGED). 새 검사/핀 체계를 만들지 않고 원래 시험 fixture를 유지한다. 위 11시험 OK는 외부 realm 변경 전 해당 제품 Source에서 얻은 결과이며 현재 통합 조합의 재시험 PASS로 확대하지 않는다. 현재 **5종 전체 소켓 PASS는 아니다**.

이번 worker의 변경/핀 검토 대상은 `world_feature_weapon_effects.py`, `hunt_bot_weapon_effects.py`, 새 `world_weapon_proc_effects_tests.py`, 본 문서의 구현/결과 절이다. 제품 함수 소비 파일은 앞 두 개이며 시험 파일과 문서는 별도이다. 외부 `tools/local_character_creation/realm.py` 변경과 그 ack/profile pin 갱신은 이 목록에 포함되지 않는다. 최종 제품 Source는 원래 고정한 무기 효과 구현이며, 새 STR13/INT13은 **수정된 봇의 1094 전용 prelogin fixture**에만 해당한다.

### 이전 342 단독 구현·검증 기록(후속 구현 이전)

`world_feature_weapon_effects.py`를 선택 기능으로 등록했다. 기존 `RuntimeExtensions`의 `pc_attack`·`_apply_monster_swing` 합성으로 실제 물리 명중에만 342 마나 흡수를 적용한다. 전투 계산 파일은 수정하지 않았다. NPC MP는 신규 공용 `world_npc_resources.py`가 EntityRef 세대별로 소유하고 사망·tick·종료에서 정리한다. PC MP는 기존 상태 프레임·진행도 저장 경로를 사용한다. 위 L1J 계산은 전부 `local_policy`이며 원본 Classic 수치 확정은 아니다. 추가 마법 피해는 확률·효과 계약의 미확인/충돌 때문에 이번 적용에서 제외했다.

단위시험: `python -X utf8 -B -m unittest tools.local_original_session.world_weapon_effects_tests tools.local_original_session.world_combat_requests_tests -v` → **24 tests OK**. 명중/빗나감·쿨다운·원거리/다른 무기/마법 비적용·MP clamp·고갈·NPC 세대/사망/종료·등록 제외를 포함한다.

실제 봇 명령(PowerShell):

```powershell
$env:SL_TEST_TIME_SCALE='10'
$env:SL_TEST_PORT_BASE='46000'
python -X utf8 -B C:\Users\Chansol\AppData\Local\Temp\claude\D--claude\0483de89-75e7-4b94-84b8-fb31fe00f575\scratchpad\fastbot\run_fast.py hunt_bot_weapon_effects
```

결과: `work/local_original_session/runs/hunt-weapon-effects-bx_b2n1a/summary.json` **SUCCESS**, run_fast exit0. 독립 prelogin 시험 저장 SoloMana Lv30·HP319·MP0·실 소유 342 장착에서 정상 FIRST/login/선택/world 후 실제 CS4E30으로 PC MP **0→1**, 제품 오크 MP **4→3**, SC4E31 ordinal114·SC4E38 ordinal115를 확인했다. 동기 공격 경계의 MP 차이로 자연 회복을 구별했다. 정상 Quit 저장 MP1, 새 FIRST/login/world 첫 상태 MP1·장착 UID 복원, 두 epoch cleanup 정상이다. 콘솔은 `runs/weapon-effects-20261028-console.txt`에 보존했다. 원본 클라이언트 실행·장착 입력·렌더링은 검증하지 않았다.

**미완 접점:** 기존 마나 드레인 마법은 `world_magic.py`의 별도 NPC MP를 아직 사용한다. 해당 파일은 다른 작업자 소유·수정 금지이므로 변경하지 않았다. 마법 담당자가 `world_npc_resources.install(view).mana_of(ref, initial_mp)` / `.drain_mana(ref, initial_mp, requested)`로 연결하기 전에는 두 효과의 공유 고갈/중복 흡수 방지가 완성되지 않는다. 위 봇 PASS는 342 단독 공격·응답·저장/복원 범위이며 병용 PASS가 아니다. 3018 명중·추가피해·양손과 발동 마법 수치는 여전히 미확인이다.

## qWeapon 데이터 한정 재조사 (2026-10-28)

기존에 채워진 659 dmg_bonus3·660 dmg_bonus0·661 hit0/dmg_bonus0의 **4셀을 재사용**했다. 이번에 확정 수치를 새로 채운 셀은 없다. 고정 client item표 → 보존 공식표/상세 → 공식 live API → L1J weapon/weapon_skill 순서로 다시 확인했다. 659·660·661·3018·342·144·568·789·1094·1096·2072·3019·3020의 공식 상세는 HTTP200이고, JSON 내용은 기존 `work/official_data/raw/item/{id}.json`과 13종 모두 같았다. 웹 도구의 API 열기는 Internal Error여서 HTTP 조회로 확인했으며 보존 원문을 덮어쓰거나 중복 수집 파일을 만들지 않았다.

3018의 client 원문 `native-dump:1526`은 INT1·mpMod4와 강화별 meleeDmg 배열뿐이다. 공식은 INT1·MP회복4·턴 언데드만 제공한다. 따라서 hit/dmg_bonus의 기존 중립값0은 확인된 0이 아니며 **UNKNOWN 2셀·양손null을 유지**한다. 공식 oneHanded=false의 의미가 확인되지 않았고 L1J261은 이름·토큰·발동 효과가 충돌하므로 hit5·damage0·한손·디지즈 확률을 가져오지 않았다. 최소 추가 입력은 고정 버전의 명중/기본 추가피해/손 사용 소비자 또는 이를 명시한 공식 설명이다.

`items_ext/weapons.json`의 기존 weapon.note 안에 **10종**(144/342/568/789/1094/1096/2072/3018/3019/3020)의 `special_effects`를 구조화했다. 공식 옵션명·출처·존재, 미확인 Classic 확률/피해/비용/수명, L1J 로컬 참고 계산, `runtime_status`, 필요한 생산자·소비자·저장/수명 계약을 함께 보존한다. 3018에는 `unresolved_stats_review`도 추가했다. 기존 원문·배열·미채택 참조·최상위 수치/아이콘/직업/양손 판단은 그대로다. 이 note는 runtime이 읽어 효과를 추가하는 데이터가 아니다. 기존 342 하드코딩 구현만 존재하며 이번 작업에서는 코드를 바꾸지 않았다.

추가로 L1J 실행식의 제한을 확인했다. `L1WeaponSkill.java:271-275`는 **randomDamage>0일 때만** 피해를 계산한다. 같은 파일 :95-128의 USE_INT_PROCS ProcMap 행은 randomDamage=0이므로 1094/2072의 의도된 INT 계산식과 별개로 실제 이 경로의 피해는0이다. USE_INT_PROCS=false일 때 SQL121(:64038)은 95+uniform(1,55), SQL205(:64041)는 fixed8이 있어도 random0 때문에 피해0이다. 기존 문서의 공통식·테이블값을 실제 발동 피해로 확정하지 않는다. 위 계산·확률은 전부 L1J 참고이며 Classic 확정값이나 활성화한 backend 정책이 아니다.

**코드가 필요한 잔여:** 144 장착/해제 헤이스트의 중첩·복원, 568 화살 우선/무형 화살 fallback·피해·투사체·소비, 789/1094/1096/2072/3018/3019/3020의 실제 물리 명중→발동 판정→대상 세대·피해/상태→응답·저장/정리 연결이다. 3019는 공식 콜드 체이서와 L1J 즉시 반경3 광역의 계약도 다르다. 342 단독 흡수는 기존 구현을 재사용했으며 `world_magic.py`와 공용 NPC MP 연결은 이번 수정 범위가 아니다. 미확인 발동률·피해·턴 언데드 성공식을 추측해 활성화하지 않았다.

`build_weapons_ext.py`는 JSON만 수정하라는 요청에 따라 변경하지 않았다. **기존 generator를 재실행하면 이번 10개 note와 3018 재조사 메타데이터가 유실**되므로 재생성 시 해당 JSON 변경분을 보존해야 한다.

## 검증

후속 4셀 조사 갱신: `python -X utf8 -B work/local_original_session/game-core-prep/build_weapons_ext.py --items-only`로 gfx/기존표를 쓰지 않고 확장 무기표만 재생성했다. 신규 수/출처 총계는 동일하며 generator gaps는 3018의 2셀이다. `python -X utf8 -B -m unittest tools.local_original_session.game_data_tests` **8 tests OK (0.402s)**. 659 dmg_bonus3, 660 dmg_bonus0, 661 hit0/dmg_bonus0은 SQL 값과 연결했고 3018 두 수치의 UNKNOWN0·양손null을 확인했다. 아래 70개 시험은 최초 확장 당시 결과로 보존하며 이번 조사에서 재실행했다고 주장하지 않는다.

`python -X utf8 -B -m unittest tools.local_original_session.game_data_tests tools.local_original_session.item_use_tests tools.local_original_session.world_item_effects_tests tools.local_original_session.world_ground_items_tests tools.local_original_session.world_enchant_inventory_tests tools.local_original_session.world_companion_equipment_tests`

결과 **70 tests OK (3.314s)**: game_data8/item_use24/world_item_effects11/world_ground_items13/world_enchant_inventory8/world_companion_equipment6. 기존 시험/기대값은 수정하지 않았다. `game_data.load_m1()` 성공, 342의 피해3/3·명중-3·직업3·무게15000·안전6·아이콘293 확인. 검증 당시 총279행은 base61 + 본 무기73 + 병행 consumables29 + 병행 armor116으로, 다른 작업자의 추가 수를 이 작업의 성과로 세지 않는다.

통합 세션의 별도 worker가 `world_weight.py`의 기존 `items.json` 단독 원문 읽기를 확장 로더와 호환시키는 최소 수정을 담당했다. 통합 세션이 최종 입력에서 `python -X utf8 -B -m tools.local_original_session.world_weight_tests` **14 tests OK (0.030s)**를 확인했다. 해당 서버 파일은 이 데이터 worker의 변경이 아니다. 통합 세션이 gfx 확장 누락0과 companion_supplies342×1도 독립 확인했다. start-manual-play.ps1에는 이번 데이터/game_data/world_weight 핀이 없음을 통합 세션이 확인해 핀을 추가하거나 변경하지 않았다.

위 최초 확장 검증은 파일 로드·순수 단위시험 범위였다. 당시 원본 클라이언트 실행·캡처·포트시험·실제 착용·양손 제한·마법 발동·화면 동등성·사용자 저장 갱신은 하지 않았다. 커밋 없음. 생성 입력/로직은 같은 폴더 `build_weapons_ext.py`이며 별도 검사기·guard·실행 프로필을 추가하지 않았다.

### qWeapon 데이터 재조사 후 별도 검증

`python -X utf8 -B -m unittest tools.local_original_session.game_data_tests tools.local_original_session.equipment_stats_tests tools.local_original_session.world_weapon_effects_tests tools.local_original_session.world_combat_requests_tests -v` → **40 tests OK (14.789s)**. 기존 시험·기대값은 수정하지 않았다. 원문은 `runs/weapon-data-20261028-unit-console.txt`다. 한글 옵션명은 기존 official_options에서 그대로 복사했고 신규 note 문자열을 확인했다.

다음 두 명령은 순차 실행했으며 실제 게임을 실행하지 않았다. 각 명령 앞에 `$env:SL_TEST_TIME_SCALE='10'`과 지정 포트 환경변수를 적용했다.

```powershell
$env:SL_TEST_TIME_SCALE='10'
$env:SL_TEST_PORT_BASE='56000'
python -X utf8 -B C:\Users\Chansol\AppData\Local\Temp\claude\D--claude\0483de89-75e7-4b94-84b8-fb31fe00f575\scratchpad\fastbot\run_fast.py hunt_bot_weapon_effects
$env:SL_TEST_PORT_BASE='57000'
python -X utf8 -B C:\Users\Chansol\AppData\Local\Temp\claude\D--claude\0483de89-75e7-4b94-84b8-fb31fe00f575\scratchpad\fastbot\run_fast.py hunt_bot_play_matrix --scenario equip_all
```

- 무기 효과 봇 **SUCCESS**, runner exit0. `runs/hunt-weapon-effects-ldse24rh/summary.json`: 새 시험 저장의 정상 FIRST/login/선택/world와 실제 소유342 장착 후 CS4E30에서 PC MP0→3, 제품 NPC MP5→2, SC4E31 ordinal113·SC4E38 ordinal114를 확인했다. 정상 Quit 저장MP3→새 FIRST/login/world 복원MP3, 두 epoch cleanup 정상이다. 콘솔 `runs/weapon-data-20261028-mana-console.txt`.
- equip_all **PASS**, runner exit0. `runs/hunt-play-matrix-j3_bx7lr/summary.json` 및 `equip_all/result.json`: 244요청·408관측·6 epoch, failure/gaps/server_failures 없음, cleanup_complete=true. 56종 장신구와 기존 시험 키트 장비의 착용/해제·저장/재접속 범위다. 기존 LOCAL614의 고정 native 대응 UNKNOWN도 결과에 그대로 남아 있다. 콘솔 `runs/weapon-data-20261028-equip-console.txt`.

두 봇은 이번 JSON 조합에서 기존 효과와 장비 경로가 유지됨을 검증했다. 신규 note의 발동 마법을 실행한 결과가 아니며 87종 모든 무기 착용·3018 수치/양손·다른 발동 마법·원본 화면/입력 동등성 PASS로 확대하지 않는다. 코드·launcher·핀·validation profile·사용자 저장·원본은 변경하지 않았고 커밋도 하지 않았다.
