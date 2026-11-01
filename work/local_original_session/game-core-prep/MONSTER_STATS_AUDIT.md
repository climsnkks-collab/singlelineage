# 몬스터 능력치 87종 대조

2026-10-28 KST. `data/m1,m3,m4,m5,m6/monsters.json`의 **고유87종·물리166행**을 고정 client → 저장 공식표 → 현재 공식 API → 선정 L1J 원행 순서로 대조했다. 공식 API87/87 HTTP200, 저장표 대비 id/name/level/big 변경0이다. HP/MP/AC/EXP/선공은 모두 선정 L1J와 일치했고, 수치 수정은 **7종의 damage.max 11행**이다. 이 수정은 기존 명시식과 실제 소비 레벨의 불일치를 닫으며 공식 공격 수치를 확정하지 않는다.

## 출처와 확인 범위

- 고정 client: `work/source_game_data/native-dump-v1.jsonl`, version **26.09.29.2001**. ID·이름토큰·SPR f2를 확인했다. 이번87종의 f20=0/1은 저장 공식표와 현재 API의 big=false/true와87/87 일치한다. 이 관측을 다른 NPC 전체의 미확인 enum 의미로 확대하지 않는다. HP/MP/AC/MR/공격/EXP/레벨을 이 dump의 미확정 필드에서 추측하지 않았다.
- 저장 공식표: `tools/local_original_session/data/official/monsters.json`, 해당 `source.raw_path`인 `work/official_data/raw/monster/{id}.json`. 원 수집표·raw는 변경하지 않았다. 현재 API87건은 **2026-10-28 12:45:27~12:47:02 KST**, 익명 직렬 GET, 시작 간격1.10초로 확인했다. 아래 ID는 실제 조회 URL이다. 현재 API는 빌드26.09.29.2001 지정 응답이 아니므로 현재/저장 level·big 일치를 고정 빌드 서버 능력치의 증명으로 소급하지 않는다.
- L1J: `D:/SingleLineageRef/l1j-en-classic/db/l1jdb_m10.sql`, npc schema1544~1610행. 아래 L1J 열은 **기존 선정 NPC ID와 실제 INSERT 행**이다. 다른 이름/SPR/레벨 변종으로 자동 교체하지 않았다. 모든 HP/MP/AC/EXP/선공은 이 원행과 같지만 클래식 원본에서는 여전히 UNKNOWN인 backend 참고 정책이다. MR도 해당 원행의 참고값이다.
- 속도: `work/local_resource_provider/assets/data/list.spr` 및 기존 파싱본 `work/asset_link_audit_20261007/sprite/current-parsed.jsonl`. 각 기존 참조 command의 C합을 직접 대조했다. **명목 round(C합/24×1000)ms**와 일치한다. 실제 서버 행동 간격으로 채택한 것은 LOCAL 정책이며 실제 원본 서버 속도는 UNKNOWN이다. 그렘린294 공격은 양의 client 공격주기 근거가 없어 **L1J45025 atkspeed=0을 기존 scheduler 하한100ms로 제한한 local_policy**다. 원래 note에 이 한계가 명시돼 있어 무수정이다. `m1/action_speed.json`은 중복 참고표이고 실제 NPC 이동/공격 소비값은 MonsterDef의 monsters.json 두 간격이다. action_speed 숫자/출처는 수정하지 않았다.

| 항목 | 실제 확인 | 정책·미확인 |
|---|---|---|
| 레벨 | 저장 공식표=현재 API,87/87 | 고정 빌드 서버 레벨의 독립 관측 아님. L1J와 다른7종의 공식 레벨 유지 |
| HP/MP/AC/EXP/선공 | 기존 선정 SQL과166물리행 모두 일치 | 공식 API는 이 필드를 제공하지 않음. 클래식 실제값 UNKNOWN. 조건부 선공·family·상태·특수행동까지 확인한 결과 아님 |
| 공격 | STR=선정SQL, min=STR//2+1, max=min+**소비 MonsterDef.level**−1 | `l1j_npc_melee`의 LOCAL 기본 물리식. PC방어·마법·보스 패턴·L1J의 추가 보정 전체를 대표하지 않음 |
| MR | L1J 원문87종 참고값; 기존 상태마법 사전11행은 모두 SQL과 일치 | MonsterDef 필드 없음. 아래 S11종만 상태마법 참고 연결; U76종은 해당 사전 미등록. 일반 공격마법 호출은 NPC MR을 전달하지 않아 기존 기본MR0 정책. MR 전체 연결 완료 아님 |
| 크기 | client f20=저장/현재 big,87/87 (대형13종·소형74종) | 이번 size 메타를166행에 추가했지만 `_monsters`/MonsterDef는 읽지 않는다. `pc_hits_npc`가 근접 weapon.small 및 원거리 target_size='small'을 사용하는 기존 정책 유지. 대형 피해 연결 미완 |
| 이동/공격속도 | SPR 참조명목331셀, 그렘린 공격하한 정책1셀 | 실제 서버 간격·버프·다른 공격 animation 선택 및 그렘린 공격 가능 여부는 미확인 |

MR 소비 원문은 `world_feature_magic._world_magic_cast` → `player_spells.json#/local_policy/npc_status_reference/<template_id>` → `world_magic_status.probability`다. `player_spells.json`은11행 전부 MR 일치하여 무수정이다. 공격마법은 `world_combat.magic_damage(..., mr=0)`의 기존 기본인수 경계를 구분한다. 크기 미연결은 `game_data.MonsterDef`, `game_data._monsters`, `world_combat.pc_hits_npc`에서 확인했으며 코드/schema를 변경하지 않았다.

## 87행 대조표

아래 **HP·MP·AC·EXP·선공은 `현재값=선정SQL값`**이다. 원본/공식에서 제공하지 않는 값까지 ‘공식 일치’로 세지 않는다. Lv는 저장/현재 공식 두 값이 같아 하나로 적고, L1J 레벨이 다르면 `(L값)`을 덧붙였다. SPR/행은 고정 dump f2와 원문 행, 크기 S/L은 client f20=공식 big이다. MR의 `S`는 기존 상태마법 참고사전 연결, `U`는 참고사전 미등록을 뜻한다(일반 공격마법 MR 연결을 뜻하지 않음). 공격의 `←`는 이번 수정 전 max다. 속도 `C`는 client 명목 LOCAL 채택, `P100(J0)`은 SQL0에 로컬 하한100ms를 적용한 그렘린 정책이다. 선공0/1은 단순 SQL agro 플래그다. 모든 행은 client 대응·공식 level/big·SQL 참고 대조를 마쳤고, 고정 빌드 서버의 나머지 능력치는 UNKNOWN이다.

| ID / 현재 API | 이름 / 표 | SPR / dump행 | Lv공식 | HP | MP | AC | MR참고/연결 | 기본공격 LOCAL | EXP | 크기 | 선공 | 이동/공격ms | 선정L1J ID:SQL행 |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|---|---:|---|---|
| [0](https://api-goats.plaync.com/linclassic/v2.0/game/monster/0?locale=ko-KR) | 오크 / m1,m3,m4,m5,m6 | 56/1 | 2 | 6 | 4 | 10 | 0/S | 4~5 | 5 | S/0/false | 0 | C833/C1375 | 45009:20631 |
| [1](https://api-goats.plaync.com/linclassic/v2.0/game/monster/1?locale=ko-KR) | 오크 궁수 / m1,m4,m5,m6 | 57/2 | 3 | 12 | 4 | 10 | 2/S | 7~9 | 10 | S/0/false | 0 | C833/C1958 | 45019:20640 |
| [2](https://api-goats.plaync.com/linclassic/v2.0/game/monster/2?locale=ko-KR) | 오크 전사 / m1,m3,m4,m5,m6 | 94/3 | 8 | 50 | 8 | 5 | 5/S | 8~15 | 65 | S/0/false | 0 | C667/C958 | 45082:20702 |
| [4](https://api-goats.plaync.com/linclassic/v2.0/game/monster/4?locale=ko-KR) | 난쟁이 / m1,m4,m5 | 54/4 | 5 | 30 | 5 | 10 | 2/S | 6~10 | 26 | S/0/false | 0 | C625/C1542 | 45041:20661 |
| [5](https://api-goats.plaync.com/linclassic/v2.0/game/monster/5?locale=ko-KR) | 돌 골렘 / m1,m4,m5 | 49/5 | 13 | 150 | 50 | -1 | 5/S | 30~42 | 170 | L/1/true | 0 | C1333/C2750 | 45126:20744 |
| [6](https://api-goats.plaync.com/linclassic/v2.0/game/monster/6?locale=ko-KR) | 돌 골렘 / m3,m6 | 49/6 | 13 | 150 | 50 | -1 | 5/U | 30~42 | 170 | L/1/true | 0 | C1333/C2750 | 45126:20744 |
| [7](https://api-goats.plaync.com/linclassic/v2.0/game/monster/7?locale=ko-KR) | 장로 / m1,m3,m4,m5,m6 | 32/7 | 21 | 250 | 60 | -5 | 30/U | 6~26 | 442 | S/0/false | 0 | C833/C1875 | 45215:20816 |
| [8](https://api-goats.plaync.com/linclassic/v2.0/game/monster/8?locale=ko-KR) | 늑대인간 / m1,m3,m4,m5 | 33/8 | 9 | 50 | 20 | 4 | 10/S | 8~16 | 82 | S/0/false | 0 | C667/C1000 | 45024:20645 |
| [9](https://api-goats.plaync.com/linclassic/v2.0/game/monster/9?locale=ko-KR) | 늑대 / m1,m4,m5 | 96/9 | 6 (L5) | 30 | 5 | 18 | 1/U | 7~12 ←max11 | 37 | S/0/false | 0 | C500/C1042 | 45043:20663 |
| [11](https://api-goats.plaync.com/linclassic/v2.0/game/monster/11?locale=ko-KR) | 괴물 눈 / m1,m3,m5,m6 | 29/11 | 7 | 40 | 30 | 5 | 20/U | 6~12 | 50 | S/0/false | 0 | C1000/C1792 | 45068:20688 |
| [15](https://api-goats.plaync.com/linclassic/v2.0/game/monster/15?locale=ko-KR) | 흑기사 / m1 | 110/14 | 16 | 100 | 10 | -10 | 10/U | 9~24 | 257 | S/0/false | 0 | C500/C1167 | 45165:20781 |
| [16](https://api-goats.plaync.com/linclassic/v2.0/game/monster/16?locale=ko-KR) | 커츠 / m1 | 111/15 | 51 (L55) | 2000 | 250 | -67 | 65/U | 38~88 ←max92 | 3026 | S/0/false | 0 | C667/C1125 | 45600:21165 |
| [17](https://api-goats.plaync.com/linclassic/v2.0/game/monster/17?locale=ko-KR) | 셸로브 / m1,m3,m4,m5,m6 | 95/16 | 14 | 100 | 15 | 0 | 12/S | 8~21 | 197 | L/1/true | 1 | C500/C917 | 45136:20753 |
| [24](https://api-goats.plaync.com/linclassic/v2.0/game/monster/24?locale=ko-KR) | 바포메트 / m3 | 53/19 | 50 (L51) | 3000 | 350 | -65 | 80/U | 35~84 ←max85 | 2602 | S/0/false | 1 | C500/C792 | 45573:21138 |
| [25](https://api-goats.plaync.com/linclassic/v2.0/game/monster/25?locale=ko-KR) | 해골 / m3 | 30/20 | 10 | 80 | 30 | 3 | 10/U | 9~18 | 101 | S/0/false | 1 | C667/C958 | 45107:20725 |
| [27](https://api-goats.plaync.com/linclassic/v2.0/game/monster/27?locale=ko-KR) | 좀비 / m1,m3,m4,m5,m6 | 52/22 | 6 | 45 | 12 | 8 | 5/S | 8~13 | 37 | S/0/false | 1 | C2083/C1083 | 45065:20685 |
| [28](https://api-goats.plaync.com/linclassic/v2.0/game/monster/28?locale=ko-KR) | 구울 / m4,m6 | 144/23 | 16 | 110 | 30 | -4 | 13/U | 9~24 | 257 | S/0/false | 1 | C1333/C750 | 45157:20773 |
| [29](https://api-goats.plaync.com/linclassic/v2.0/game/monster/29?locale=ko-KR) | 해골 / m1,m3,m4,m6 | 30/24 | 10 | 80 | 30 | 3 | 10/S | 9~18 | 101 | S/0/false | 1 | C667/C958 | 45107:20725 |
| [30](https://api-goats.plaync.com/linclassic/v2.0/game/monster/30?locale=ko-KR) | 스파토이 / m3,m4,m6 | 145/25 | 16 | 120 | 30 | -3 | 18/U | 9~24 | 257 | S/0/false | 1 | C833/C958 | 45161:20777 |
| [31](https://api-goats.plaync.com/linclassic/v2.0/game/monster/31?locale=ko-KR) | 웅골리언트 / m5,m6 | 146/26 | 18 | 200 | 30 | -5 | 10/U | 10~27 | 325 | L/1/true | 1 | C500/C875 | 45184:20796 |
| [33](https://api-goats.plaync.com/linclassic/v2.0/game/monster/33?locale=ko-KR) | 버그베어 / m4,m6 | 152/27 | 22 | 250 | 30 | -6 | 10/U | 10~31 | 485 | L/1/true | 1 | C667/C875 | 45223:20823 |
| [34](https://api-goats.plaync.com/linclassic/v2.0/game/monster/34?locale=ko-KR) | 발터자르 / m6 | 185/28 | 43 | 800 | 250 | -32 | 80/U | 7~49 | 1850 | S/0/false | 1 | C667/C1542 | 45473:21044 |
| [35](https://api-goats.plaync.com/linclassic/v2.0/game/monster/35?locale=ko-KR) | 카스파 / m6 | 173/29 | 44 | 450 | 250 | -32 | 80/U | 7~50 | 1937 | S/0/false | 1 | C667/C1542 | 45488:21059 |
| [36](https://api-goats.plaync.com/linclassic/v2.0/game/monster/36?locale=ko-KR) | 메르키오르 / m6 | 187/30 | 45 | 450 | 250 | -32 | 80/U | 7~51 | 2026 | S/0/false | 1 | C667/C1542 | 45497:21068 |
| [37](https://api-goats.plaync.com/linclassic/v2.0/game/monster/37?locale=ko-KR) | 세마 / m6 | 183/31 | 42 | 800 | 250 | -32 | 80/U | 7~48 | 1765 | S/0/false | 1 | C667/C917 | 45464:21035 |
| [63](https://api-goats.plaync.com/linclassic/v2.0/game/monster/63?locale=ko-KR) | 데스나이트 / m6 | 240/40 | 52 (L55) | 4000 | 250 | -67 | 65/U | 38~89 ←max92 | 3026 | S/0/false | 1 | C667/C625 | 45601:21166 |
| [64](https://api-goats.plaync.com/linclassic/v2.0/game/monster/64?locale=ko-KR) | 크로울링 크로 / m6 | 246/41 | 8 | 30 | 15 | 0 | 5/U | 7~14 | 65 | S/0/false | 1 | C667/C1292 | 45083:20703 |
| [91](https://api-goats.plaync.com/linclassic/v2.0/game/monster/91?locale=ko-KR) | 아투바 오크 / m4 | 786/58 | 15 | 120 | 15 | -5 | 10/U | 8~22 | 226 | S/0/false | 1 | C667/C1083 | 45149:20765 |
| [92](https://api-goats.plaync.com/linclassic/v2.0/game/monster/92?locale=ko-KR) | 네루가 오크 / m4 | 788/59 | 17 | 150 | 15 | -8 | 7/U | 9~25 | 290 | S/0/false | 1 | C667/C1208 | 45171:20787 |
| [93](https://api-goats.plaync.com/linclassic/v2.0/game/monster/93?locale=ko-KR) | 두다-마라 오크 / m4 | 788/60 | 15 | 100 | 50 | -5 | 20/U | 7~21 | 226 | S/0/false | 1 | C667/C1208 | 45143:20760 |
| [94](https://api-goats.plaync.com/linclassic/v2.0/game/monster/94?locale=ko-KR) | 간디 오크 / m4 | 784/61 | 10 | 80 | 25 | 0 | 15/U | 6~15 | 101 | S/0/false | 1 | C667/C1083 | 45098:20717 |
| [95](https://api-goats.plaync.com/linclassic/v2.0/game/monster/95?locale=ko-KR) | 로바 오크 / m4 | 786/62 | 13 | 80 | 20 | -2 | 5/U | 7~19 | 170 | S/0/false | 1 | C667/C1083 | 45127:20745 |
| [115](https://api-goats.plaync.com/linclassic/v2.0/game/monster/115?locale=ko-KR) | 가스트 / m4,m5,m6 | 255/75 | 21 | 200 | 30 | -10 | 10/U | 9~29 | 442 | S/0/false | 1 | C1042/C667 | 45213:20814 |
| [116](https://api-goats.plaync.com/linclassic/v2.0/game/monster/116?locale=ko-KR) | 오크 스카우트 / m4 | 790/76 | 14 | 90 | 15 | -3 | 5/U | 8~21 | 197 | S/0/false | 1 | C667/C1583 | 45138:20755 |
| [129](https://api-goats.plaync.com/linclassic/v2.0/game/monster/129?locale=ko-KR) | 가스트 로드 / m4 | 257/81 | 33 | 300 | 50 | -13 | 20/U | 10~42 | 1090 | S/0/false | 1 | C1125/C667 | 45346:20936 |
| [144](https://api-goats.plaync.com/linclassic/v2.0/game/monster/144?locale=ko-KR) | 펑거스 / m4,m5,m6 | 852/88 | 4 | 40 | 10 | 5 | 1/U | 4~7 | 17 | S/0/false | 1 | C1083/C1542 | 45030:20651 |
| [145](https://api-goats.plaync.com/linclassic/v2.0/game/monster/145?locale=ko-KR) | 브롭 / m6 | 31/89 | 5 | 20 | 10 | 7 | 0/U | 8~12 | 26 | S/0/false | 0 | C875/C667 | 45032:20652 |
| [147](https://api-goats.plaync.com/linclassic/v2.0/game/monster/147?locale=ko-KR) | 오크 궁수 / m4,m6 | 57/91 | 3 | 12 | 4 | 10 | 2/U | 7~9 | 10 | S/0/false | 0 | C833/C1958 | 45019:20640 |
| [148](https://api-goats.plaync.com/linclassic/v2.0/game/monster/148?locale=ko-KR) | 오크 전사 / m4,m6 | 94/92 | 8 | 50 | 8 | 5 | 5/U | 8~15 | 65 | S/0/false | 0 | C667/C958 | 45082:20702 |
| [149](https://api-goats.plaync.com/linclassic/v2.0/game/monster/149?locale=ko-KR) | 아투바 오크 / m4,m6 | 786/93 | 15 | 120 | 15 | -5 | 10/U | 8~22 | 226 | S/0/false | 1 | C667/C1083 | 45149:20765 |
| [150](https://api-goats.plaync.com/linclassic/v2.0/game/monster/150?locale=ko-KR) | 네루가 오크 / m4,m6 | 788/94 | 17 | 150 | 15 | -8 | 7/U | 9~25 | 290 | S/0/false | 1 | C667/C1208 | 45171:20787 |
| [151](https://api-goats.plaync.com/linclassic/v2.0/game/monster/151?locale=ko-KR) | 두다-마라 오크 / m4,m6 | 788/95 | 15 | 100 | 50 | -5 | 20/U | 7~21 | 226 | S/0/false | 1 | C667/C1208 | 45143:20760 |
| [152](https://api-goats.plaync.com/linclassic/v2.0/game/monster/152?locale=ko-KR) | 간디 오크 / m4,m6 | 784/96 | 10 | 80 | 25 | 0 | 15/U | 6~15 | 101 | S/0/false | 1 | C667/C1083 | 45098:20717 |
| [153](https://api-goats.plaync.com/linclassic/v2.0/game/monster/153?locale=ko-KR) | 로바 오크 / m4,m6 | 786/97 | 13 | 80 | 20 | -2 | 5/U | 7~19 | 170 | S/0/false | 1 | C667/C1083 | 45127:20745 |
| [154](https://api-goats.plaync.com/linclassic/v2.0/game/monster/154?locale=ko-KR) | 늑대인간 / m4,m6 | 33/98 | 9 | 50 | 20 | 4 | 10/U | 8~16 | 82 | S/0/false | 0 | C667/C1000 | 45024:20645 |
| [155](https://api-goats.plaync.com/linclassic/v2.0/game/monster/155?locale=ko-KR) | 늑대 / m4 | 96/99 | 4 (L5) | 30 | 5 | 18 | 1/U | 7~10 ←max11 | 37 | S/0/false | 0 | C500/C1042 | 45043:20663 |
| [156](https://api-goats.plaync.com/linclassic/v2.0/game/monster/156?locale=ko-KR) | 오크 / m4,m6 | 56/100 | 2 | 6 | 4 | 10 | 0/U | 4~5 | 5 | S/0/false | 0 | C833/C1375 | 45009:20631 |
| [162](https://api-goats.plaync.com/linclassic/v2.0/game/monster/162?locale=ko-KR) | 돌 골렘 / m4 | 49/105 | 13 | 150 | 50 | -1 | 5/U | 30~42 | 170 | L/1/true | 0 | C1333/C2750 | 45126:20744 |
| [163](https://api-goats.plaync.com/linclassic/v2.0/game/monster/163?locale=ko-KR) | 난쟁이 / m4 | 54/106 | 5 | 30 | 5 | 10 | 2/U | 6~10 | 26 | S/0/false | 0 | C625/C1542 | 45041:20661 |
| [164](https://api-goats.plaync.com/linclassic/v2.0/game/monster/164?locale=ko-KR) | 좀비 / m4,m6 | 52/107 | 6 | 45 | 12 | 8 | 5/U | 8~13 | 37 | S/0/false | 1 | C2083/C1083 | 45065:20685 |
| [177](https://api-goats.plaync.com/linclassic/v2.0/game/monster/177?locale=ko-KR) | 도베르만 / m1,m4,m5 | 931/114 | 6 (L5) | 20 | 5 | 25 | 1/U | 9~14 ←max13 | 37 | S/0/false | 0 | C583/C1000 | 45042:20662 |
| [179](https://api-goats.plaync.com/linclassic/v2.0/game/monster/179?locale=ko-KR) | 세퍼드 / m1,m4,m5 | 936/116 | 5 | 30 | 5 | 9 | 1/U | 8~12 | 26 | S/0/false | 0 | C583/C1000 | 45034:20654 |
| [180](https://api-goats.plaync.com/linclassic/v2.0/game/monster/180?locale=ko-KR) | 비글 / m4,m5 | 938/117 | 5 | 20 | 30 | 25 | 15/U | 6~10 | 26 | S/0/false | 0 | C750/C1000 | 45046:20666 |
| [182](https://api-goats.plaync.com/linclassic/v2.0/game/monster/182?locale=ko-KR) | 켈베로스 / m6 | 951/118 | 24 | 120 | 60 | -20 | 25/U | 9~32 | 577 | S/0/false | 1 | C667/C1083 | 45241:20839 |
| [190](https://api-goats.plaync.com/linclassic/v2.0/game/monster/190?locale=ko-KR) | 멧돼지 / m1,m4,m5 | 979/125 | 6 | 20 | 5 | 7 | 1/U | 6~11 | 37 | S/0/false | 0 | C667/C833 | 45058:20678 |
| [212](https://api-goats.plaync.com/linclassic/v2.0/game/monster/212?locale=ko-KR) | 킹 버그베어 / m6 | 894/139 | 30 | 400 | 30 | -13 | 20/U | 11~40 | 901 | L/1/true | 1 | C667/C750 | 45298:20892 |
| [223](https://api-goats.plaync.com/linclassic/v2.0/game/monster/223?locale=ko-KR) | 오우거 / m4,m5 | 1020/144 | 28 | 500 | 20 | -18 | 20/U | 11~38 | 785 | L/1/true | 1 | C1000/C1250 | 45278:20872 |
| [235](https://api-goats.plaync.com/linclassic/v2.0/game/monster/235?locale=ko-KR) | 거대 개미 / m5,m6 | 1037/150 | 12 | 90 | 20 | -4 | 60/U | 8~19 | 145 | S/0/false | 1 | C667/C917 | 45115:20733 |
| [236](https://api-goats.plaync.com/linclassic/v2.0/game/monster/236?locale=ko-KR) | 거대 병정 개미 / m6 | 1039/151 | 20 | 150 | 100 | -7 | 60/U | 16~35 | 401 | L/1/true | 1 | C667/C792 | 45190:20802 |
| [245](https://api-goats.plaync.com/linclassic/v2.0/game/monster/245?locale=ko-KR) | 고블린 / m1,m4,m5 | 1022/152 | 2 | 3 | 10 | 10 | 2/S | 6~7 | 5 | S/0/false | 0 | C792/C958 | 45008:20630 |
| [249](https://api-goats.plaync.com/linclassic/v2.0/game/monster/249?locale=ko-KR) | 코볼트 / m1,m4,m5 | 1059/156 | 3 | 7 | 15 | 10 | 2/S | 7~9 | 10 | S/0/false | 0 | C1333/C1125 | 45016:20637 |
| [252](https://api-goats.plaync.com/linclassic/v2.0/game/monster/252?locale=ko-KR) | 하피 / m5 | 1024/158 | 26 | 230 | 150 | -18 | 25/U | 9~34 | 677 | S/0/false | 1 | C875/C1292 | 45264:20859 |
| [274](https://api-goats.plaync.com/linclassic/v2.0/game/monster/274?locale=ko-KR) | 오크 마법사 / m4,m5 | 1211/159 | 12 | 80 | 50 | 0 | 30/U | 4~15 | 145 | S/0/false | 1 | C1000/C1292 | 45121:20739 |
| [276](https://api-goats.plaync.com/linclassic/v2.0/game/monster/276?locale=ko-KR) | 해골궁수 / m3,m4,m6 | 1096/160 | 12 | 80 | 25 | 0 | 10/U | 9~20 | 145 | S/0/false | 1 | C833/C1167 | 45122:20740 |
| [277](https://api-goats.plaync.com/linclassic/v2.0/game/monster/277?locale=ko-KR) | 해골도끼병 / m3,m6 | 1104/161 | 13 | 90 | 20 | 0 | 10/U | 10~22 | 170 | S/0/false | 1 | C500/C875 | 45130:20748 |
| [278](https://api-goats.plaync.com/linclassic/v2.0/game/monster/278?locale=ko-KR) | 해골창병 / m3,m6 | 1106/162 | 13 | 90 | 15 | 8 | 10/U | 9~21 | 170 | S/0/false | 1 | C667/C917 | 45131:20749 |
| [280](https://api-goats.plaync.com/linclassic/v2.0/game/monster/280?locale=ko-KR) | 라이칸스로프 / m4,m5 | 1108/164 | 17 | 120 | 60 | -4 | 7/U | 9~25 | 290 | S/0/false | 1 | C667/C833 | 45173:20789 |
| [293](https://api-goats.plaync.com/linclassic/v2.0/game/monster/293?locale=ko-KR) | 아이들론 / m5 | 1150/174 | 4 | 20 | 5 | 10 | 1/U | 6~9 | 17 | S/0/false | 0 | C333/C1000 | 45027:20648 |
| [294](https://api-goats.plaync.com/linclassic/v2.0/game/monster/294?locale=ko-KR) | 그렘린 / m5 | 1154/175 | 4 | 50 | 20 | 10 | 1/U | 6~9 | 17 | S/0/false | 0 | C333/P100(J0) | 45025:20646 |
| [295](https://api-goats.plaync.com/linclassic/v2.0/game/monster/295?locale=ko-KR) | 임프 / m5 | 1152/176 | 5 | 20 | 40 | 6 | 1/U | 5~9 | 26 | S/0/false | 1 | C500/C1583 | 45033:20653 |
| [296](https://api-goats.plaync.com/linclassic/v2.0/game/monster/296?locale=ko-KR) | 임프 장로 / m5 | 1158/177 | 6 | 100 | 50 | 10 | 30/U | 5~10 | 37 | S/0/false | 0 | C1000/C958 | 45064:20684 |
| [297](https://api-goats.plaync.com/linclassic/v2.0/game/monster/297?locale=ko-KR) | 다크 엘프 / m4,m5 | 1125/178 | 27 | 350 | 110 | -24 | 30/U | 9~35 | 730 | S/0/false | 1 | C667/C2000 | 45265:20860 |
| [298](https://api-goats.plaync.com/linclassic/v2.0/game/monster/298?locale=ko-KR) | 아울베어 / m5 | 1162/179 | 15 | 250 | 10 | -6 | 10/U | 10~24 | 226 | L/1/true | 1 | C1000/C1125 | 45147:20763 |
| [323](https://api-goats.plaync.com/linclassic/v2.0/game/monster/323?locale=ko-KR) | 홉고블린 / m4,m5 | 1206/190 | 14 | 90 | 30 | 1 | 1/U | 7~20 | 197 | S/0/false | 0 | C667/C1083 | 45140:20757 |
| [324](https://api-goats.plaync.com/linclassic/v2.0/game/monster/324?locale=ko-KR) | 난쟁이족 전사 / m5 | 1184/191 | 9 | 70 | 5 | 5 | 1/U | 8~16 | 82 | S/0/false | 0 | C667/C1208 | 45092:20711 |
| [325](https://api-goats.plaync.com/linclassic/v2.0/game/monster/325?locale=ko-KR) | 사이클롭스 / m5 | 1202/192 | 40 | 800 | 50 | -23 | 30/U | 11~50 | 1601 | L/1/true | 1 | C1000/C1208 | 45420:21009 |
| [331](https://api-goats.plaync.com/linclassic/v2.0/game/monster/331?locale=ko-KR) | 리자드맨 / m5 | 1173/196 | 15 | 90 | 10 | -2 | 5/U | 8~22 | 226 | S/0/false | 1 | C667/C958 | 45144:20761 |
| [333](https://api-goats.plaync.com/linclassic/v2.0/game/monster/333?locale=ko-KR) | 그리폰 / m5 | 1204/198 | 31 | 380 | 150 | -20 | 10/U | 9~39 | 962 | L/1/true | 1 | C667/C1333 | 45321:20913 |
| [454](https://api-goats.plaync.com/linclassic/v2.0/game/monster/454?locale=ko-KR) | 거대 여왕 개미 / m6 | 1390/261 | 57 | 8000 | 100 | -65 | 60/U | 16~72 | 3250 | L/1/true | 1 | C1333/C833 | 45614:21179 |
| [591](https://api-goats.plaync.com/linclassic/v2.0/game/monster/591?locale=ko-KR) | 파이어 에그 / m5 | 1820/339 | 39 (L25) | 120 | 10 | -14 | 35/U | 9~47 ←max33 | 626 | S/0/false | 1 | C1500/C917 | 45206:20812 |
| [750](https://api-goats.plaync.com/linclassic/v2.0/game/monster/750?locale=ko-KR) | 흑기사 수색대 / m4 | 110/398 | 16 | 100 | 10 | -10 | 10/U | 9~24 | 257 | S/0/false | 0 | C500/C1167 | 81066:23117 |
| [879](https://api-goats.plaync.com/linclassic/v2.0/game/monster/879?locale=ko-KR) | 산적 / m5 | 2443/463 | 28 | 500 | 10 | -16 | 25/U | 10~37 | 785 | S/0/false | 1 | C500/C1042 | 45317:20911 |
| [880](https://api-goats.plaync.com/linclassic/v2.0/game/monster/880?locale=ko-KR) | 산적 / m5 | 2489/464 | 32 | 330 | 15 | -22 | 40/U | 9~40 | 1025 | S/0/false | 1 | C1000/C1125 | 45324:20916 |
| [881](https://api-goats.plaync.com/linclassic/v2.0/game/monster/881?locale=ko-KR) | 산적 / m5 | 2516/465 | 31 | 350 | 20 | -15 | 30/U | 10~40 | 962 | S/0/false | 1 | C1000/C1417 | 81080:23130 |
| [882](https://api-goats.plaync.com/linclassic/v2.0/game/monster/882?locale=ko-KR) | 산적 / m5 | 2533/466 | 30 | 300 | 15 | -16 | 25/U | 9~38 | 901 | S/0/false | 1 | C1000/C1833 | 45276:20870 |
| [883](https://api-goats.plaync.com/linclassic/v2.0/game/monster/883?locale=ko-KR) | 산적 두목 / m5 | 2417/467 | 35 | 500 | 50 | -25 | 50/U | 11~45 | 1226 | S/0/false | 1 | C1000/C1208 | 45370:20960 |
| [10129](https://api-goats.plaync.com/linclassic/v2.0/game/monster/10129?locale=ko-KR) | 네크로맨서 / m6 | 183/751 | 42 | 800 | 250 | -32 | 80/U | 7~48 | 1765 | S/0/false | 1 | C667/C917 | 45456:21027 |

## 수정과 미완 계약

공식 레벨과 L1J 레벨이 다른7종은 늑대9(6/5), 늑대155(4/5), 도베르만177(6/5), 커츠16(51/55), 바포메트24(50/51), 파이어 에그591(39/25), 데스나이트63(52/55)다. 기존 max는 L1J 레벨로 계산돼 `world_combat.npc_hits_pc`의 명시된 `nextInt(level)+STR/2+1` 및 이미 채택된 MonsterDef.level과 맞지 않았다. 현재 공식 레벨은 보존하고 **max만** LOCAL 식에 맞췄다. 해당 damage source를 `local_policy`로 구분하고 기존 max/L1J 레벨·원문 출처를 note에 남겼다. 다른 공식/SQL 값으로의 추정 보정은 하지 않았다.

| 파일 | template_id: max 전→후 |
|---|---|
| data/m1/monsters.json | 9:11→12,16:92→88,177:13→14 |
| data/m3/monsters.json | 24:85→84 |
| data/m4/monsters.json | 9:11→12,155:11→10,177:13→14 |
| data/m5/monsters.json | 9:11→12,177:13→14,591:33→47 |
| data/m6/monsters.json | 63:92→89 |

이 다섯 표에 size 메타166개·level의 현재 API 재확인 출처·공통 감사경계를 추가했다. 크기 소비 연결과 나머지76종 MR 상태사전/전체 NPC MR 소비 연결은 코드 변경이 필요한 별도 미완 계약이다. 크기 확인을 위해 L1J size로 덮지 않았다. 동일 이름 해골25/29와 오크0/156, 공식 레벨이 다른 늑대9/155 등 기존 개별 ID는 유지한다. L1J 대응 변종 자체가 이미 LOCAL 선택인 항목은 raw 일치를 원본 변종 확정으로 올리지 않는다. HP/MP/AC/EXP/선공, 기존 SPR 속도 숫자, 성장·드롭·성향·스폰·마법 JSON·코드·manual 프로필은 변경하지 않았다.

## 검증과 제한

기존 `game_data.load_m1` → `world_interest_spawn.with_dungeon_data`(프로세스 내부 `SL_EXPERIMENT_MAP=2`) → 기존 `world_feature_dungeons.load_dungeon_data` → 기존 `world_feature_m5.load_m5_data`를 **`python -X utf8 -B`에서 비소켓 호출**했다. 19→57(M3+M4)→71(M6)→87(M5)종·323스폰을 로드했다. 수정7종의 최종 MonsterDef.damage.max는12/88/14/84/10/47/89(9/16/177/24/155/591/63 순)이며 수정값이 실제 파서에 소비됨을 확인했다. 동일 template의166물리행 간 대상 수치/크기 충돌0이다. size는 파싱된 MonsterDef에 존재하지 않음도 확인했다.

이 결과는 원문·출처·데이터 소비까지의 확인이며 실제 공격/피격·대형 피해·NPC MR 효과·원본 입력/화면·속도·보스 처치의 실행 PASS가 아니다. 원본 클라이언트·서버·소켓 시험을 실행하지 않았고 저장·current·원본 자원을 변경하지 않았다. 기존 API raw/공식 snapshot을 덮어쓰지 않았으며 현재 API의 확인값은 위87행과 각 URL/수집시각 범위에 남겼다. 신규 검사기·guard·hash 보고서를 만들거나 커밋하지 않았다.

## 후속 크기·MR 소비 연결 (2026-10-28)

위87종 감사 당시의 미연결 설명은 다음 구현으로 갱신한다. `game_data.MonsterDef`에 `size`·`mr`를 추가하고 기존 `_monsters`가 출처를 포함해 읽는다. 기존5표166행의 size 값·MR 원값은 유지했다. MR이 없던 행에는 이미 선정된 `l1j_npcid`의 SQL `npc.mr`를 `l1j_mr` 셀에 보충했다. 별도 로더가 소비하는 `m6/map_expansion2_population.json`33행에도 두 셀만 보충했다. 이33행의 고정 dump f20=0/1은 저장 공식표 `official.big`과 모두 일치한다. 전체199물리행·119종(대형22종)이 로드되며 중복 template의 size/MR 충돌은 없다. 기존 다른 능력치·행·선정 NPC ID를 바꾸지 않았다. 수정 전 전체 객체 보관본과의 독립 diff는 없으며 셀 국소 삽입으로 수정했다.

크기는 고정 client와 저장 공식표의 근거다. 공식 API에 수치 MR이 없어 MR과 계산은 **L1J 참고 LOCAL backend 정책**이다. 근거 원문은 `D:/SingleLineageRef/l1j-en-classic/db/l1jdb_m10.sql` npc schema1544~1610행 및 각 셀의 INSERT 행, `src/l1j/server/server/model/L1Attack.java:750-762,798-806`, `L1Magic.java:326-343,738-762`다. 물리 공격은 대상 크기로 무기/화살의 small·large 주사위를 선택하며 플레이어·동료 기본공격이 공통 함수를 쓴다. 플레이어 단일·광역 공격 피해와 일반 MR 확률형 마법은 현재 몬스터 표의 MR을 소비한다. 과거 `player_spells.json` 상태사전 MR로 실제 표를 덮지 않는다. Erase Magic의 반감·1회 소비는 유지한다. 일반 공격마법에 MR 기반의 임의 빗나감을 추가하지 않았고, L1J의 레벨 차 확률 분기는 MR을 사용하지 않는 원래 분기를 유지했다.

**동료 공격마법 MR은 미완**이다. `world_feature_companion.py:282`는 여전히 대상 MR 없이 호출한다. 이 파일은 이번 직접 사용자 금지 범위라 수정하지 않았으며 예외 승인 응답을 받지 못했다. 필요한 최소 변경은 해당 호출에 `mr=found[0].monster.mr`를 더하는 한 곳이다. 동료 기본공격의 크기 연결 성공을 이 미완 마법 경로의 성공으로 확대하지 않는다.

변경 파일은 `tools/local_original_session/{game_data.py,world_combat.py,world_feature_magic.py,world_npc_defense_tests.py}`, `data/{m1,m3,m4,m5,m6}/monsters.json`, `data/m6/map_expansion2_population.json`, 이 문서다. 기존 시험·동료·변신·퀘스트·성장표·장비관측·ACTIVE_TASK·런처·프로필·수동 스크립트는 수정하지 않았다. 핀/manifest가 이 변경을 추적한다면 재산정 대상은 앞의 런타임3파일과 데이터6파일이다. 현재 `manual-play/start-manual-play.ps1`의 직접 `$pins` 목록에는 이9파일이 없으며 핀 값은 수정하지 않았다.

시험 원문은 `work/local_original_session/runs/npc-defense-20261028/`에 있다. 아래 봇은 모두 지정 runner `C:/Users/Chansol/AppData/Local/Temp/claude/D--claude/0483de89-75e7-4b94-84b8-fb31fe00f575/scratchpad/fastbot/run_fast.py`를 `python -X utf8 -B`로 실행했다. 실제 게임은 실행하지 않았다.

| 실제 명령·설정 | 결과·보존 위치 |
|---|---|
| `python -X utf8 -B -m unittest tools.local_original_session.world_npc_defense_tests -v` | 6개 OK (`unit-attempt2.log`). MR 낮음/높음의 실제 피해·확률형 명중, 단일/광역·Erase, 대소 무기/화살·동료 기본공격. 첫 시험은 새 fixture의 STR/결과 이름 기대2건을 고쳤으며 `unit-attempt1.log` 보존. 개발 직접 호출이며 정식 게임 PASS 아님. |
| `python -X utf8 -B -m unittest tools.local_original_session.{game_data_tests,world_combat_requests_tests,world_magic_tests,world_companion_magic_tests,world_ammo_tests,world_expansion_data_tests,world_dungeon_maps_tests}` (중괄호7개를 각각 모듈 인수로 전개) | 128개 중124 OK/4 FAIL (`regression.log`). MR 사전만80으로 바꾼 기존 fixture는 실제 MonsterDef MR2의 Erase 결과1을 받아40 기대와 불일치. 나머지3건은 던전 population33종·추가맵·drop 출처 local_policy의 범위 밖 기대 불일치이며 변경 전 재현 미실시. 기존 시험 무수정. |
| `SL_TEST_TIME_SCALE=10 SL_TEST_PORT_BASE=58000 .../run_fast.py hunt_bot_magic --scenario jobs` | exit1 FAILED, `ValueError: items.243: kind/duplicate`,151체크 성공 뒤 후속 프로필 준비 실패. `magic-jobs.log`, 원사본 `runs/hunt-magic-94w2nvgi/summary.json`. cleanup=true·broker 예외0. `game_data._items_dir`가 합치는 `data/m1/items_ext/misc.json`·`drops_misc.json`에 id243이 중복되며 해당 파일은 무수정. 봇의 source_changes0은 선언된 코드 목록뿐이고 item JSON은 추적하지 않아 전체 실행 데이터 고정 증명 아님. 재실행하지 않았다. |
| `SL_TEST_TIME_SCALE=10 SL_TEST_PORT_BASE=59000 .../run_fast.py hunt_bot_scenarios --scenario hunt` | argparse 실제 exit2: `hunt` 미지원 (`hunt-requested.log`). finally의 FAST_CLOCK exit1은 runner 초기값으로 argparse exit2와 구별한다. CLI 수정 없음. |
| 같은59000 설정, `.../run_fast.py hunt_bot_scenarios --scenario combat` | exit0 SUCCESS·9체크·정상cleanup, `combat.log`, `runs/hunt-scenarios-f79cq3pq/combat/`. 정상 로그인/선택/월드, 원거리 공격2·이동14와 화살1회 소비/저장·공유 cooldown 검증. kill0이므로 사냥 완주나 MR별 실제 소켓 피해 비교 PASS 아님. |

원본 Classic MR·서버 계산의 동등성, 원본 클라이언트 화면/입력·대형 피해 표시, 동료 공격마법 MR 소비와 jobs 전체 완료는 확인하지 못했다. 기존 저장·실패·partial·current·원본 자원은 보존했고 커밋은 하지 않았다.
