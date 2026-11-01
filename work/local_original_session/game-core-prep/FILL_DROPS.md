# 드롭·아이템 데이터 보강

2026-10-28 KST. data-only 작성. 게임·서버·봇·포트 실행 없음. 기존 원문은 활성 이동 시 각 drops.json의 `resolved_unresolved_history`에 보존했다. 실제 획득·줍기·사용·렌더링·저장/복원이나 원본 동등성 PASS를 뜻하지 않는다.

**유효 병합:** 선정 몬스터31→87종, 활성86→421조합, 기존 미해결192 중 **83 해결 / 109 잔여**. 기존 양쪽누락3은 복구·활성화했다. 신규 몬스터를 포함한 고정 client 구성956조합 = 활성421 + 미해결535이며 중복·누락·client밖 활성0이다.

아이템279→382종(신규103). 원192 잔여 중 ItemDef 미등록4행, 등록됐으나 확률·수량 또는 변종 대응 미확정105행. 신규까지 합친 장신구 pending은14종/27유효 미해결행이다. 기존 pending 장신구 슬롯/능력치/소비 계약을 우회하지 않았다.

기존31종의 활성은 **86+83+3=172(172/281=61.21%)**, 신규56종의 활성은 **249**다. 신규 범위까지 포함한 구성 활성률은421/956=44.04%이며 전체 클래식 드롭률이 아니다. 잔여535는 기존31종109 + 신규56종426이다.

## 출처·판정 경계

- 원구성 ID·등급은 고정 client f21과 all-drop-pairs를 사용했다. 저장 공식 상세는 이름·구성 비교 자료이고 공식 확률·수량은 없다.
- 확률·수량은 deferred_roll 원문, catalog의 검증된 같은 template roll, 선정 L1J NPC 자신의 SQL행을 재사용했다. 새 SQL 대응은 아이템 token·kind·grade/bless·raw f10·f5/f6 전체 일치만 채택했다. 다른 NPC/다른 아이템·등급의 확률을 새로 대입하지 않았다. 기존 승인 local_policy는 그대로 보존했다.
- NPC의 L1J 연결은 population_sources의 별도 backend 참고 정책이다. 같은 이름의 원본 변종 동일성을 확정하지 않는다. ID25는 ID29와 합치지 않고 고정 client25의 f21을 별도로 읽었다.
- 신규 기타/재료/마법서/막대/조명은 기존 schema의 `scroll`을 **LOCAL 비장비 보관 분류**로 사용한다. native 종류나 사용·학습·충전·제작·조명 지원을 뜻하지 않는다. heal_hp=0이며 효과 표·Python은 변경하지 않았다.
- 신규 gfx는 각 client item.bin f5/f6를 그대로 복사했다. 바닥 그래픽 실제 화면은 미검증이다. stackable은 대응 L1J 일반등급 참고값, 대응이 없으면 명시 LOCAL 가방 정책이다.

## 물리 표와 유효 병합

M3는 M1 공통 드롭을 덮고 M4/M6/M5는 기존 드롭을 우선한다. 물리 행을 합산하여 지급 가능한 양으로 주장하지 않는다.

| 표 | 활성 전→후 | unresolved 전→후 | 보존한 해결 원문 |
| --- | --- | --- | --- |
| m1 | 48→128 | 50→44 | 80 |
| m3 | 42→102 | 64→78 | 60 |
| m4 | 54→253 | 108→178 | 199 |
| m6 | 5→210 | 29→276 | 208 |
| m5 | 38→177 | 88→166 | 165 |

## 요정숲 오크156 저주3행

기존 m6의 중복 grade1 placeholder는 원문으로 보존하고 고정 client f21의 grade2를 복구했다. L1J45009의 SQL **3948/3949/3950**에는 실제 저주 아이템 **200001/220034/220135**가 있다. 각 token·kind·bless2·raw f10·f5/f6 대응이 맞으므로 item40/88/101 grade2를 각각 chance50000/1000000, count1로 활성화했다. 일반등급 roll을 전용한 것이 아니다.

## 맵별 산출 가능한 드롭 증분

현재 스폰 template 집합에 같은 유효 전역 드롭 정책을 투영했다. `전`은 현재 맵의 기존31종 subset에 baseline 정책을 적용한 수이며 과거 맵 실제 스폰/획득 관측이 아니다. 한 template이 여러 맵에 있으면 각 맵에 다시 나오므로 맵 열을 합산하지 않는다.

| 맵 | template | 기존종 기준 전 | 현재 활성 | 증분 | 현재 미해결 |
| --- | --- | --- | --- | --- | --- |
| 0 | 19 | 51 | 128 | +77 | 44 |
| 1 | 9 | 37 | 63 | +26 | 23 |
| 2 | 12 | 39 | 78 | +39 | 72 |
| 4 | 68 | 75 | 299 | +224 | 303 |
| 7 | 8 | 26 | 54 | +28 | 16 |
| 8 | 9 | 21 | 57 | +36 | 30 |
| 9 | 12 | 20 | 65 | +45 | 94 |
| 10 | 13 | 19 | 72 | +53 | 97 |
| 11 | 10 | 18 | 69 | +51 | 66 |
| 12 | 12 | 11 | 76 | +65 | 81 |
| 13 | 9 | 8 | 63 | +55 | 61 |
| 19 | 4 | 0 | 23 | +23 | 24 |
| 20 | 7 | 0 | 17 | +17 | 31 |
| 21 | 7 | 4 | 25 | +21 | 22 |
| 43 | 2 | 5 | 6 | +1 | 13 |
| 44 | 2 | 5 | 6 | +1 | 13 |
| 45 | 2 | 5 | 6 | +1 | 13 |
| 46 | 2 | 5 | 6 | +1 | 13 |
| 47 | 2 | 5 | 6 | +1 | 13 |
| 48 | 2 | 5 | 6 | +1 | 13 |
| 49 | 2 | 5 | 6 | +1 | 13 |
| 50 | 2 | 5 | 6 | +1 | 13 |
| 51 | 3 | 5 | 18 | +13 | 37 |

## 신규 아이템·출처 비율

추가103행의 source 태그 최상위 셀1236개: client 515(41.67%), local_policy 721(58.33%). 중첩 원문·메타는 제외한다.

유효 활성 item source: {'client': 421}. roll source: {'l1j': 79, 'local_policy': 342}. 신규 활성 확률은 local_policy와 L1J SQL 원문으로 표시했다. baseline 활성 원source는 보존했다. 행 출처 비율은 원본 구현율·실제 효과 소비율과 다르다.

| ID | 이름 | 보관분류 / catalog종류 | icon / ground | raw f10 |
| --- | --- | --- | --- | --- |
| 5 | 등잔 | scroll / light | 3 / 4 | 20000 |
| 19 | 소나무 막대 | scroll / wand | 117 / 28 | 55 |
| 20 | 단풍나무 막대 | scroll / wand | 116 / 28 | 55 |
| 21 | 흑단 막대 | scroll / wand | 118 / 28 | 55 |
| 36 | 양초 | scroll / light | 24 / 6 | 2000 |
| 52 | 금빛 열쇠 | scroll / etc | 59 / 19 | 3000 |
| 53 | 은회색 열쇠 | scroll / etc | 59 / 19 | 3000 |
| 121 | 셸로브 발톱 | scroll / etc | 139 / 150 | 0 |
| 127 | 랜턴 | scroll / light | 140 / 181 | 30000 |
| 131 | 랜턴용 기름 | scroll / etc | 142 / 239 | 8 |
| 157 | 아투바의 토템 | scroll / etc | 258 / 729 | 781 |
| 158 | 네루가의 토템 | scroll / etc | 259 / 730 | 781 |
| 159 | 두다-마라의 토템 | scroll / etc | 260 / 731 | 781 |
| 160 | 간디의 토템 | scroll / etc | 261 / 732 | 781 |
| 161 | 로바의 토템 | scroll / etc | 262 / 733 | 781 |
| 166 | 마력의 돌 | scroll / etc | 235 / 773 | 2000 |
| 168 | 다이아몬드 | scroll / etc | 236 / 771 | 39 |
| 169 | 고급 다이아몬드 | scroll / etc | 237 / 771 | 39 |
| 170 | 최고급 다이아몬드 | scroll / etc | 238 / 771 | 39 |
| 171 | 에메랄드 | scroll / etc | 239 / 772 | 39 |
| 172 | 고급 에메랄드 | scroll / etc | 240 / 772 | 39 |
| 173 | 최고급 에메랄드 | scroll / etc | 241 / 772 | 39 |
| 174 | 루비 | scroll / etc | 242 / 774 | 39 |
| 175 | 고급 루비 | scroll / etc | 243 / 774 | 39 |
| 176 | 최고급 루비 | scroll / etc | 244 / 774 | 39 |
| 177 | 사파이어 | scroll / etc | 245 / 775 | 39 |
| 178 | 고급 사파이어 | scroll / etc | 246 / 775 | 39 |
| 179 | 최고급 사파이어 | scroll / etc | 247 / 775 | 39 |
| 194 | 마법서 (파이어볼) | scroll / spellbook | 249 / 776 | 7000 |
| 195 | 마법서 (인챈트 덱스터리티) | scroll / spellbook | 249 / 776 | 7000 |
| 196 | 마법서 (웨폰 브레이크) | scroll / spellbook | 254 / 777 | 7000 |
| 197 | 마법서 (뱀파이어릭 터치) | scroll / spellbook | 254 / 777 | 7000 |
| 198 | 마법서 (슬로우) | scroll / spellbook | 249 / 776 | 7000 |
| 200 | 마법서 (콜 라이트닝) | scroll / spellbook | 250 / 776 | 7000 |
| 201 | 마법서 (그레이터 힐) | scroll / spellbook | 250 / 776 | 7000 |
| 202 | 마법서 (테이밍 몬스터) | scroll / spellbook | 250 / 776 | 7000 |
| 203 | 마법서 (리무브 커스) | scroll / spellbook | 250 / 776 | 7000 |
| 204 | 마법서 (크리에이트 좀비) | scroll / spellbook | 255 / 777 | 7000 |
| 205 | 마법서 (인챈트 마이티) | scroll / spellbook | 250 / 776 | 7000 |
| 206 | 마법서 (헤이스트) | scroll / spellbook | 250 / 776 | 7000 |
| 207 | 마법서 (캔슬레이션) | scroll / spellbook | 250 / 776 | 7000 |
| 208 | 마법서 (이럽션) | scroll / spellbook | 250 / 776 | 7000 |
| 209 | 마법서 (힐 올) | scroll / spellbook | 251 / 776 | 7000 |
| 211 | 마법서 (서먼 몬스터) | scroll / spellbook | 256 / 777 | 7000 |
| 212 | 마법서 (홀리 워크) | scroll / spellbook | 251 / 776 | 7000 |
| 213 | 마법서 (토네이도) | scroll / spellbook | 251 / 776 | 7000 |
| 217 | 마법서 (인비지블리티) | scroll / spellbook | 251 / 776 | 7000 |
| 218 | 마법서 (리절렉션) | scroll / spellbook | 251 / 776 | 7000 |
| 222 | 마법서 (이뮨 투 함) | scroll / spellbook | 252 / 776 | 7000 |
| 246 | 미스릴 원석 | scroll / etc | 320 / 888 | 781 |
| 249 | 버섯포자의 즙 | scroll / etc | 82 / 47 | 14063 |
| 250 | 오우거의 피 | scroll / etc | 324 / 905 | 141 |
| 252 | 미스릴 | scroll / etc | 318 / 889 | 391 |
| 332 | 동물가죽 | scroll / etc | 446 / 1164 | 78 |
| 333 | 철괴 | scroll / etc | 454 / 1167 | 781 |
| 335 | 고급피혁 | scroll / etc | 455 / 1164 | 391 |
| 336 | 뼈조각 | scroll / etc | 444 / 1166 | 156 |
| 409 | 화룡 비늘 | scroll / etc | 549 / 1567 | 7813 |
| 520 | 마법서 (어스 재일) | scroll / spellbook | 249 / 776 | 7000 |
| 522 | 마법서 (선 버스트) | scroll / spellbook | 250 / 776 | 7000 |
| 523 | 마법서 (그레이터 헤이스트) | scroll / spellbook | 251 / 776 | 7000 |
| 524 | 마법서 (어스 퀘이크) | scroll / spellbook | 251 / 776 | 7000 |
| 569 | 정령옥 | scroll / etc | 706 / 773 | 781 |
| 575 | 정령의 수정 (리턴 투 네이처) | scroll / spellbook | 677 / 2225 | 5000 |
| 576 | 정령의 수정 (블러드 투 소울) | scroll / spellbook | 677 / 2225 | 5000 |
| 580 | 정령의 수정 (윈드 워크) | scroll / spellbook | 679 / 2225 | 5000 |
| 582 | 정령의 수정 (인탱글) | scroll / spellbook | 676 / 2225 | 5000 |
| 583 | 정령의 수정 (이레이즈 매직) | scroll / spellbook | 682 / 2225 | 5000 |
| 585 | 정령의 수정 (브레스 오브 파이어) | scroll / spellbook | 680 / 2225 | 5000 |
| 586 | 정령의 수정 (아이 오브 스톰) | scroll / spellbook | 684 / 2225 | 5000 |
| 587 | 정령의 수정 (어스 바인드) | scroll / spellbook | 681 / 2225 | 5000 |
| 588 | 정령의 수정 (네이쳐스 터치) | scroll / spellbook | 683 / 2225 | 5000 |
| 589 | 정령의 수정 (블레스 오브 어스) | scroll / spellbook | 681 / 2225 | 5000 |
| 601 | 마법서 (카운터 매직) | scroll / spellbook | 249 / 776 | 7000 |
| 602 | 마법서 (메디테이션) | scroll / spellbook | 249 / 776 | 7000 |
| 604 | 마법서 (다크니스) | scroll / spellbook | 255 / 777 | 7000 |
| 605 | 마법서 (위크니스) | scroll / spellbook | 255 / 777 | 7000 |
| 606 | 마법서 (블레스 웨폰) | scroll / spellbook | 250 / 776 | 7000 |
| 607 | 마법서 (버서커스) | scroll / spellbook | 251 / 776 | 7000 |
| 608 | 마법서 (디지즈) | scroll / spellbook | 256 / 777 | 7000 |
| 610 | 마법서 (사일런스) | scroll / spellbook | 251 / 776 | 7000 |
| 633 | 낡은 거래 문서 | scroll / etc | 919 / 22 | 0 |
| 636 | 수색문서 | scroll / etc | 914 / 22 | 0 |
| 639 | 흑기사의 서약서 | scroll / etc | 927 / 22 | 0 |
| 640 | 두다 마라 오크 마법서 | scroll / etc | 923 / 776 | 0 |
| 641 | 네루가 오크 마법서 | scroll / etc | 925 / 776 | 0 |
| 642 | 간디 오크 마법서 | scroll / etc | 924 / 776 | 0 |
| 643 | 아투바 오크 마법서 | scroll / etc | 922 / 776 | 0 |
| 647 | 해골의 두개골 | scroll / etc | 921 / 150 | 0 |
| 648 | 구울의 손톱 | scroll / etc | 918 / 997 | 0 |
| 649 | 구울의 이빨 | scroll / etc | 926 / 997 | 0 |
| 677 | 생명의 비밀 | scroll / etc | 912 / 22 | 0 |
| 694 | 언데드의 열쇠 | scroll / etc | 59 / 19 | 0 |
| 707 | 비밀방 열쇠 | scroll / etc | 59 / 19 | 0 |
| 1294 | 기술서 (쇼크 스턴) | scroll / spellbook | 252 / 776 | 7000 |
| 1490 | 마법서 (디케이 포션) | scroll / spellbook | 252 / 776 | 7000 |
| 1491 | 마법서 (어드밴스 스피릿) | scroll / spellbook | 252 / 776 | 7000 |
| 1861 | 기술서 (리덕션 아머) | scroll / spellbook | 252 / 776 | 7000 |
| 1862 | 기술서 (바운스 어택) | scroll / spellbook | 252 / 776 | 7000 |
| 1863 | 기술서 (솔리드 캐리지) | scroll / spellbook | 252 / 776 | 7000 |
| 12110 | 도난당한 목걸이 | scroll / etc | 637 / 3963 | 0 |
| 12112 | 사이클롭스의 피 | scroll / etc | 20029 / 3963 | 0 |
| 12120 | 신비한 지혜의 물약 | scroll / etc | 1529 / 3963 | 0 |

## 미등록 ItemDef 계약

| ID | 이름 | 유효 드롭 미해결행 |
| --- | --- | --- |
| 64 | 순간이동 조종 반지 | 2 |
| 65 | 변신 조종 반지 | 3 |
| 306 | 완력의 목걸이 | 5 |
| 308 | 체력의 목걸이 | 1 |
| 309 | 지식의 목걸이 | 1 |
| 311 | 매력의 목걸이 | 1 |
| 314 | 오크 투사의 목걸이 | 3 |
| 502 | 낡은 신체의 벨트 | 2 |
| 503 | 낡은 정신의 벨트 | 1 |
| 504 | 낡은 영혼의 벨트 | 2 |
| 505 | 신체의 벨트 | 2 |
| 506 | 정신의 벨트 | 1 |
| 507 | 영혼의 벨트 | 2 |
| 566 | 오우거의 벨트 | 1 |

## 기존192행별 결과

키는 `몬스터ID/아이템ID/등급`이다. 잔여 이유는 과거 `미등록` 문구가 아니라 현재 ItemDef 재대조와 원문 확률/동일성 계약을 구분한다. 원문 reason/ref와 활성 roll의 정확 SQL ref는 [FILL_DROPS.json](FILL_DROPS.json)의 `original_192.rows`에 행별로 보존했다.

| 키 | 몬스터 / 아이템 | 결과 | 이유 또는 근거 |
| --- | --- | --- | --- |
| 0/74/1 | 오크 / 오크족 검 | 활성 | l1jdb:3933 원문: INSERT INTO `droplist` VALUES ('45009', 'Orc', '21', 'Orcish Short Sword', '1', '1', '50000'); source=local_policy |
| 0/101/1 | 오크 / 오크족 고리 갑옷 | 활성 | l1jdb:3936 원문: INSERT INTO `droplist` VALUES ('45009', 'Orc', '20135', 'Orcish Ring Mail', '1', '1', '50000'); source=local_policy |
| 0/332/1 | 오크 / 동물가죽 | 활성 | l1jdb:3943 원문: INSERT INTO `droplist` VALUES ('45009', 'Orc', '40405', 'Fur', '1', '1', '50000'); source=local_policy |
| 1/34/1 | 오크 궁수 / 오크족 활 | 활성 | l1jdb:3972 weapon 171 $65 bless1 (:63872); source=local_policy |
| 1/97/1 | 오크 궁수 / 오크족 사슬 갑옷 | 활성 | l1jdb:3976 armor 20136 $160 bless1 (:2980); source=local_policy |
| 1/101/1 | 오크 궁수 / 오크족 고리 갑옷 | 활성 | l1jdb:3975 armor 20135 $165 bless1; source=local_policy |
| 1/332/1 | 오크 궁수 / 동물가죽 | 활성 | l1jdb:3987 etcitem 40405 $1036; source=local_policy |
| 2/5/1 | 오크 전사 / 등잔 | 활성 | l1jdb:4369 원문: INSERT INTO `droplist` VALUES ('45082', 'Orc Fighter', '40001', 'Lamp', '1', '1', '25000'); source=local_policy |
| 2/97/1 | 오크 전사 / 오크족 사슬 갑옷 | 활성 | l1jdb:4367 원문: INSERT INTO `droplist` VALUES ('45082', 'Orc Fighter', '20136', 'Orcish Chain Mail', '1', '1', '50000'); source=local_policy |
| 2/97/2 | 오크 전사 / 오크족 사슬 갑옷 | 잔여 | ItemDef 등록. 해당 NPC·후보 item·grade의 확률/수량 행 없음. 타 NPC/등급 확률을 가져오지 않음. |
| 2/101/1 | 오크 전사 / 오크족 고리 갑옷 | 활성 | l1jdb:4366 원문: INSERT INTO `droplist` VALUES ('45082', 'Orc Fighter', '20135', 'Orcish Ring Mail', '1', '1', '25000'); source=local_policy |
| 2/115/1 | 오크 전사 / 우럭하이 방패 | 활성 | l1jdb:4368 원문: INSERT INTO `droplist` VALUES ('45082', 'Orc Fighter', '20237', 'Orcish Shield', '1', '1', '50000'); source=local_policy |
| 2/115/2 | 오크 전사 / 우럭하이 방패 | 활성 | l1jdb:4377 원문: INSERT INTO `droplist` VALUES ('45082', 'Orc Fighter', '220237', 'Orcish Shield', '1', '1', '50000'); source=local_policy |
| 2/167/1 | 오크 전사 / 사슬 갑옷 | 잔여 | ItemDef 등록. 해당 NPC·후보 item·grade의 확률/수량 행 없음. 타 NPC/등급 확률을 가져오지 않음. |
| 4/72/1 | 난쟁이 / 난쟁이족 검 | 활성 | l1jdb:4123 원문: INSERT INTO `droplist` VALUES ('45041', 'Dwarf', '26', 'Dwarvish Short Sword', '1', '1', '15000'); source=local_policy |
| 4/107/1 | 난쟁이 / 난쟁이족 망토 | 활성 | l1jdb:4125 원문: INSERT INTO `droplist` VALUES ('45041', 'Dwarf', '20052', 'Dwarvish Cloak', '1', '1', '20000'); source=local_policy |
| 4/118/1 | 난쟁이 / 난쟁이족 둥근 방패 | 활성 | l1jdb:4126 원문: INSERT INTO `droplist` VALUES ('45041', 'Dwarf', '20223', 'Dwarvish Round Shield', '1', '1', '15000'); source=local_policy |
| 4/252/1 | 난쟁이 / 미스릴 | 활성 | l1jdb:4133 원문: INSERT INTO `droplist` VALUES ('45041', 'Dwarf', '40494', 'Pure Mithril', '1', '1', '50000'); source=local_policy |
| 4/333/1 | 난쟁이 / 철괴 | 활성 | l1jdb:4132 원문: INSERT INTO `droplist` VALUES ('45041', 'Dwarf', '40408', 'Lump of Iron', '1', '3', '300000'); source=local_policy |
| 5/21/1 | 돌 골렘 / 흑단 막대 | 잔여 | ItemDef 등록. L1J item 변종 대응과 해당 NPC 확률/수량 미확정. |
| 5/166/1 | 돌 골렘 / 마력의 돌 | 잔여 | ItemDef 등록. 해당 NPC·후보 item·grade의 확률/수량 행 없음. 타 NPC/등급 확률을 가져오지 않음. |
| 5/176/1 | 돌 골렘 / 최고급 루비 | 잔여 | ItemDef 등록. L1J item 변종 대응과 해당 NPC 확률/수량 미확정. |
| 5/246/1 | 돌 골렘 / 미스릴 원석 | 활성 | l1jdb:4715 원문: INSERT INTO `droplist` VALUES ('45126', 'Stone Golem', '40496', 'Rough Mithril', '1', '3', '50000'); source=local_policy |
| 5/492/1 | 돌 골렘 / 파란 물약 | 활성 | l1jdb:4704 원문: INSERT INTO `droplist` VALUES ('45126', 'Stone Golem', '40015', 'Potion of Mana', '1', '1', '10000'); source=local_policy |
| 5/520/1 | 돌 골렘 / 마법서 (어스 재일) | 잔여 | ItemDef 등록. 해당 NPC·후보 item·grade의 확률/수량 행 없음. 타 NPC/등급 확률을 가져오지 않음. |
| 5/677/1 | 돌 골렘 / 생명의 비밀 | 활성 | l1jdb:4716 원문: INSERT INTO `droplist` VALUES ('45126', 'Stone Golem', '40564', 'Secret of Life', '1', '1', '50000'); source=local_policy |
| 6/21/1 | 돌 골렘 / 흑단 막대 | 잔여 | ItemDef 등록. L1J item 변종 대응과 해당 NPC 확률/수량 미확정. |
| 6/166/1 | 돌 골렘 / 마력의 돌 | 잔여 | ItemDef 등록. 해당 NPC·후보 item·grade의 확률/수량 행 없음. 타 NPC/등급 확률을 가져오지 않음. |
| 6/176/1 | 돌 골렘 / 최고급 루비 | 잔여 | ItemDef 등록. L1J item 변종 대응과 해당 NPC 확률/수량 미확정. |
| 6/246/1 | 돌 골렘 / 미스릴 원석 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 6/492/1 | 돌 골렘 / 파란 물약 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 6/520/1 | 돌 골렘 / 마법서 (어스 재일) | 잔여 | ItemDef 등록. 해당 NPC·후보 item·grade의 확률/수량 행 없음. 타 NPC/등급 확률을 가져오지 않음. |
| 6/545/1 | 돌 골렘 / 돌 장갑 | 잔여 | ItemDef 등록. L1J item 변종 대응과 해당 NPC 확률/수량 미확정. |
| 7/19/1 | 장로 / 소나무 막대 | 잔여 | ItemDef 등록. 해당 NPC·후보 item·grade의 확률/수량 행 없음. 타 NPC/등급 확률을 가져오지 않음. |
| 7/20/1 | 장로 / 단풍나무 막대 | 잔여 | ItemDef 등록. 해당 NPC·후보 item·grade의 확률/수량 행 없음. 타 NPC/등급 확률을 가져오지 않음. |
| 7/22/1 | 장로 / 확인 주문서 | 활성 | l1jdb:5508 원문: INSERT INTO `droplist` VALUES ('45215', 'Elder', '40126', 'Scroll of Identify', '1', '1', '50000'); source=local_policy |
| 7/24/1 | 장로 / 저주 풀기 주문서 | 활성 | l1jdb:5507 원문: INSERT INTO `droplist` VALUES ('45215', 'Elder', '40119', 'Scroll of Curse Removal', '1', '1', '50000'); source=local_policy |
| 7/166/1 | 장로 / 마력의 돌 | 잔여 | ItemDef 등록. 해당 NPC·후보 item·grade의 확률/수량 행 없음. 타 NPC/등급 확률을 가져오지 않음. |
| 7/200/1 | 장로 / 마법서 (콜 라이트닝) | 활성 | l1jdb:5509 원문: INSERT INTO `droplist` VALUES ('45215', 'Elder', '40179', 'Spellbook(CallLightning)', '1', '1', '50000'); source=local_policy |
| 7/201/1 | 장로 / 마법서 (그레이터 힐) | 활성 | l1jdb:5510 원문: INSERT INTO `droplist` VALUES ('45215', 'Elder', '40180', 'Spellbook(GreaterHeal)', '1', '1', '50000'); source=local_policy |
| 7/297/1 | 장로 / 지혜의 물약 | 활성 | l1jdb:5503 원문: INSERT INTO `droplist` VALUES ('45215', 'Elder', '40016', 'Potion of Wisdom', '1', '1', '50000'); source=local_policy |
| 7/492/1 | 장로 / 파란 물약 | 활성 | l1jdb:5502 원문: INSERT INTO `droplist` VALUES ('45215', 'Elder', '40015', 'Potion of Mana', '1', '1', '50000'); source=local_policy |
| 7/12120/1 | 장로 / 신비한 지혜의 물약 | 잔여 | ItemDef 등록. L1J item 변종 대응과 해당 NPC 확률/수량 미확정. |
| 8/96/2 | 늑대인간 / 사슬 갑옷 | 활성 | l1jdb:4017 원문: INSERT INTO `droplist` VALUES ('45024', 'Werewolf', '220125', 'Chain Mail', '1', '1', '50000'); source=local_policy |
| 8/195/1 | 늑대인간 / 마법서 (인챈트 덱스터리티) | 활성 | l1jdb:4009 원문: INSERT INTO `droplist` VALUES ('45024', 'Werewolf', '40171', 'Spellbook(EnchantDex)', '1', '1', '50000'); source=local_policy |
| 8/197/1 | 늑대인간 / 마법서 (뱀파이어릭 터치) | 활성 | l1jdb:4010 원문: INSERT INTO `droplist` VALUES ('45024', 'Werewolf', '40173', 'Spellbook(VampiricTouch)', '1', '1', '50000'); source=local_policy |
| 11/9/1 | 괴물 눈 / 괴물 눈 고기 | 잔여 | ItemDef 등록. L1J item 변종 대응과 해당 NPC 확률/수량 미확정. |
| 11/166/1 | 괴물 눈 / 마력의 돌 | 잔여 | ItemDef 등록. 해당 NPC·후보 item·grade의 확률/수량 행 없음. 타 NPC/등급 확률을 가져오지 않음. |
| 17/19/1 | 셸로브 / 소나무 막대 | 활성 | l1jdb:4806 원문: INSERT INTO `droplist` VALUES ('45136', 'Arachnevil', '40006', 'Pine Wand', '1', '1', '8000'); source=local_policy |
| 17/21/1 | 셸로브 / 흑단 막대 | 잔여 | ItemDef 등록. L1J item 변종 대응과 해당 NPC 확률/수량 미확정. |
| 17/121/1 | 셸로브 / 셸로브 발톱 | 잔여 | ItemDef 등록. L1J item 변종 대응과 해당 NPC 확률/수량 미확정. |
| 17/198/1 | 셸로브 / 마법서 (슬로우) | 활성 | l1jdb:4810 원문: INSERT INTO `droplist` VALUES ('45136', 'Arachnevil', '40174', 'Spellbook(Slow)', '1', '1', '12000'); source=local_policy |
| 17/208/1 | 셸로브 / 마법서 (이럽션) | 활성 | l1jdb:4811 원문: INSERT INTO `droplist` VALUES ('45136', 'Arachnevil', '40190', 'Spellbook(Eruption)', '1', '1', '9000'); source=local_policy |
| 17/495/1 | 셸로브 / 강화 초록 물약 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 27/197/1 | 좀비 / 마법서 (뱀파이어릭 터치) | 활성 | l1jdb:4234 원문: INSERT INTO `droplist` VALUES ('45065', 'Zombie', '40173', 'Spellbook(VampiricTouch)', '1', '1', '10000'); source=local_policy |
| 27/604/1 | 좀비 / 마법서 (다크니스) | 활성 | l1jdb:4235 원문: INSERT INTO `droplist` VALUES ('45065', 'Zombie', '40185', 'Spellbook(Darkness)', '1', '1', '10000'); source=local_policy |
| 29/67/1 | 해골 / 언월도 | 활성 | l1jdb:4538 원문: INSERT INTO `droplist` VALUES ('45107', 'Skeleton', '27', 'Scimitar', '1', '1', '20000'); source=local_policy |
| 29/67/2 | 해골 / 언월도 | 잔여 | ItemDef 등록. 해당 NPC·후보 item·grade의 확률/수량 행 없음. 타 NPC/등급 확률을 가져오지 않음. |
| 29/111/1 | 해골 / 마법 망토 | 활성 | l1jdb:4540 원문: INSERT INTO `droplist` VALUES ('45107', 'Skeleton', '20056', 'Cloak of Magic Resistance', '1', '1', '9000'); source=local_policy |
| 29/111/2 | 해골 / 마법 망토 | 활성 | l1jdb:4555 원문: INSERT INTO `droplist` VALUES ('45107', 'Skeleton', '220056', 'Cloak of Magic Resistance', '1', '1', '40000'); source=local_policy |
| 29/166/1 | 해골 / 마력의 돌 | 잔여 | ItemDef 등록. 해당 NPC·후보 item·grade의 확률/수량 행 없음. 타 NPC/등급 확률을 가져오지 않음. |
| 29/195/1 | 해골 / 마법서 (인챈트 덱스터리티) | 활성 | l1jdb:4545 원문: INSERT INTO `droplist` VALUES ('45107', 'Skeleton', '40171', 'Spellbook(EnchantDex)', '1', '1', '8000'); source=local_policy |
| 29/336/1 | 해골 / 뼈조각 | 활성 | l1jdb:4549 원문: INSERT INTO `droplist` VALUES ('45107', 'Skeleton', '40407', 'Bone Piece', '1', '1', '50000'); source=local_policy |
| 29/495/1 | 해골 / 강화 초록 물약 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 29/647/1 | 해골 / 해골의 두개골 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 29/694/1 | 해골 / 언데드의 열쇠 | 잔여 | ItemDef 등록. 해당 NPC·후보 item·grade의 확률/수량 행 없음. 타 NPC/등급 확률을 가져오지 않음. |
| 30/20/1 | 스파토이 / 단풍나무 막대 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 30/67/0 | 스파토이 / 언월도 | 활성 | l1jdb:5075 SQL: INSERT INTO `droplist` VALUES ('45161', 'Spartoi', '100027', 'Scimitar', '1', '1', '50000'); source=local_policy |
| 30/67/1 | 스파토이 / 언월도 | 활성 | l1jdb:5064 SQL: INSERT INTO `droplist` VALUES ('45161', 'Spartoi', '27', 'Scimitar', '1', '1', '30000'); source=local_policy |
| 30/93/1 | 스파토이 / 청동 판금 갑옷 | 활성 | l1jdb:5066 SQL: INSERT INTO `droplist` VALUES ('45161', 'Spartoi', '20149', 'Bronze Plate Mail', '1', '1', '5000'); source=local_policy |
| 30/166/1 | 스파토이 / 마력의 돌 | 잔여 | ItemDef 등록. 해당 NPC·후보 item·grade의 확률/수량 행 없음. 타 NPC/등급 확률을 가져오지 않음. |
| 30/495/1 | 스파토이 / 강화 초록 물약 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 91/93/1 | 아투바 오크 / 청동 판금 갑옷 | 활성 | l1jdb:4960 SQL: INSERT INTO `droplist` VALUES ('45149', 'Atuba Orc', '20149', 'Bronze Plate Mail', '1', '1', '5000'); source=local_policy |
| 91/97/1 | 아투바 오크 / 오크족 사슬 갑옷 | 활성 | l1jdb:4959 SQL: INSERT INTO `droplist` VALUES ('45149', 'Atuba Orc', '20136', 'Orcish Chain Mail', '1', '1', '12000'); source=local_policy |
| 91/115/1 | 아투바 오크 / 우럭하이 방패 | 활성 | l1jdb:4962 SQL: INSERT INTO `droplist` VALUES ('45149', 'Atuba Orc', '20237', 'Orcish Shield', '1', '1', '15000'); source=local_policy |
| 91/127/1 | 아투바 오크 / 랜턴 | 활성 | l1jdb:4964 SQL: INSERT INTO `droplist` VALUES ('45149', 'Atuba Orc', '40002', 'Lantern', '1', '1', '12000'); source=local_policy |
| 91/157/1 | 아투바 오크 / 아투바의 토템 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 91/174/1 | 아투바 오크 / 루비 | 잔여 | ItemDef 등록. L1J item 변종 대응과 해당 NPC 확률/수량 미확정. |
| 91/229/1 | 아투바 오크 / 투구 | 잔여 | ItemDef 등록. 해당 NPC·후보 item·grade의 확률/수량 행 없음. 타 NPC/등급 확률을 가져오지 않음. |
| 91/235/1 | 아투바 오크 / 다마스커스 검 | 활성 | l1jdb:4956 SQL: INSERT INTO `droplist` VALUES ('45149', 'Atuba Orc', '37', 'Damascus Sword', '1', '1', '10000'); source=local_policy |
| 91/296/1 | 아투바 오크 / 용기의 물약 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 91/314/1 | 아투바 오크 / 오크 투사의 목걸이 | 잔여 | ItemDef 미등록. 장신구 슬롯·능력치·착용 계약. |
| 91/643/1 | 아투바 오크 / 아투바 오크 마법서 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 92/6/2 | 네루가 오크 / 양손검 | 활성 | l1jdb:5190 SQL: INSERT INTO `droplist` VALUES ('45171', 'Neruga Orc', '200052', 'Two-Handed Sword', '1', '1', '5000'); source=local_policy |
| 92/97/1 | 네루가 오크 / 오크족 사슬 갑옷 | 잔여 | ItemDef 등록. 해당 NPC·후보 item·grade의 확률/수량 행 없음. 타 NPC/등급 확률을 가져오지 않음. |
| 92/115/1 | 네루가 오크 / 우럭하이 방패 | 활성 | l1jdb:5177 SQL: INSERT INTO `droplist` VALUES ('45171', 'Neruga Orc', '20237', 'Orcish Shield', '1', '1', '12000'); source=local_policy |
| 92/127/1 | 네루가 오크 / 랜턴 | 활성 | l1jdb:5179 SQL: INSERT INTO `droplist` VALUES ('45171', 'Neruga Orc', '40002', 'Lantern', '1', '1', '12000'); source=local_policy |
| 92/141/2 | 네루가 오크 / 그라디우스 | 활성 | l1jdb:5189 SQL: INSERT INTO `droplist` VALUES ('45171', 'Neruga Orc', '200032', 'Gradius', '1', '1', '500'); source=local_policy |
| 92/158/1 | 네루가 오크 / 네루가의 토템 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 92/174/1 | 네루가 오크 / 루비 | 잔여 | ItemDef 등록. L1J item 변종 대응과 해당 NPC 확률/수량 미확정. |
| 92/235/1 | 네루가 오크 / 다마스커스 검 | 활성 | l1jdb:5174 SQL: INSERT INTO `droplist` VALUES ('45171', 'Neruga Orc', '37', 'Damascus Sword', '1', '1', '5000'); source=local_policy |
| 92/314/1 | 네루가 오크 / 오크 투사의 목걸이 | 잔여 | ItemDef 미등록. 장신구 슬롯·능력치·착용 계약. |
| 92/495/1 | 네루가 오크 / 강화 초록 물약 | 잔여 | ItemDef 등록. 해당 NPC·후보 item·grade의 확률/수량 행 없음. 타 NPC/등급 확률을 가져오지 않음. |
| 92/641/1 | 네루가 오크 / 네루가 오크 마법서 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 93/115/1 | 두다-마라 오크 / 우럭하이 방패 | 활성 | l1jdb:4891 SQL: INSERT INTO `droplist` VALUES ('45143', 'Duda-Mara Orc', '20237', 'Orcish Shield', '1', '1', '12000'); source=local_policy |
| 93/127/1 | 두다-마라 오크 / 랜턴 | 활성 | l1jdb:4893 SQL: INSERT INTO `droplist` VALUES ('45143', 'Duda-Mara Orc', '40002', 'Lantern', '1', '1', '10000'); source=local_policy |
| 93/159/1 | 두다-마라 오크 / 두다-마라의 토템 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 93/166/1 | 두다-마라 오크 / 마력의 돌 | 잔여 | ItemDef 등록. 해당 NPC·후보 item·grade의 확률/수량 행 없음. 타 NPC/등급 확률을 가져오지 않음. |
| 93/175/1 | 두다-마라 오크 / 고급 루비 | 잔여 | ItemDef 등록. L1J item 변종 대응과 해당 NPC 확률/수량 미확정. |
| 93/229/1 | 두다-마라 오크 / 투구 | 잔여 | ItemDef 등록. 해당 NPC·후보 item·grade의 확률/수량 행 없음. 타 NPC/등급 확률을 가져오지 않음. |
| 93/297/1 | 두다-마라 오크 / 지혜의 물약 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 93/314/1 | 두다-마라 오크 / 오크 투사의 목걸이 | 잔여 | ItemDef 미등록. 장신구 슬롯·능력치·착용 계약. |
| 93/495/1 | 두다-마라 오크 / 강화 초록 물약 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 93/640/1 | 두다-마라 오크 / 두다 마라 오크 마법서 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 94/36/1 | 간디 오크 / 양초 | 활성 | l1jdb:4502 SQL: INSERT INTO `droplist` VALUES ('45098', 'Gandi Orc', '40005', 'Candle', '1', '1', '25000'); source=local_policy |
| 94/160/1 | 간디 오크 / 간디의 토템 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 94/166/1 | 간디 오크 / 마력의 돌 | 잔여 | ItemDef 등록. 해당 NPC·후보 item·grade의 확률/수량 행 없음. 타 NPC/등급 확률을 가져오지 않음. |
| 94/642/1 | 간디 오크 / 간디 오크 마법서 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 95/127/1 | 로바 오크 / 랜턴 | 활성 | l1jdb:4721 SQL: INSERT INTO `droplist` VALUES ('45127', 'Rova Orc', '40002', 'Lantern', '1', '1', '10000'); source=local_policy |
| 95/131/1 | 로바 오크 / 랜턴용 기름 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 95/161/1 | 로바 오크 / 로바의 토템 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 95/167/1 | 로바 오크 / 사슬 갑옷 | 잔여 | ItemDef 등록. 해당 NPC·후보 item·grade의 확률/수량 행 없음. 타 NPC/등급 확률을 가져오지 않음. |
| 95/174/1 | 로바 오크 / 루비 | 잔여 | ItemDef 등록. L1J item 변종 대응과 해당 NPC 확률/수량 미확정. |
| 95/495/1 | 로바 오크 / 강화 초록 물약 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 144/249/1 | 펑거스 / 버섯포자의 즙 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 156/19/1 | 오크 / 소나무 막대 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 156/20/1 | 오크 / 단풍나무 막대 | 잔여 | ItemDef 등록. 해당 NPC·후보 item·grade의 확률/수량 행 없음. 타 NPC/등급 확률을 가져오지 않음. |
| 156/29/1 | 오크 / 화살 | 잔여 | ItemDef 등록. 해당 NPC·후보 item·grade의 확률/수량 행 없음. 타 NPC/등급 확률을 가져오지 않음. |
| 156/40/1 | 오크 / 오크족 단검 | 활성 | l1jdb:3932 SQL: INSERT INTO `droplist` VALUES ('45009', 'Orc', '1', 'Orcish Dagger', '1', '1', '50000'); source=local_policy |
| 156/71/1 | 오크 / 오크족 창 | 잔여 | ItemDef 등록. 해당 NPC·후보 item·grade의 확률/수량 행 없음. 타 NPC/등급 확률을 가져오지 않음. |
| 156/74/1 | 오크 / 오크족 검 | 활성 | l1jdb:3933 SQL: INSERT INTO `droplist` VALUES ('45009', 'Orc', '21', 'Orcish Short Sword', '1', '1', '50000'); source=local_policy |
| 156/88/1 | 오크 / 오크족 투구 | 활성 | l1jdb:3934 SQL: INSERT INTO `droplist` VALUES ('45009', 'Orc', '20034', 'Orcish Helm', '1', '1', '50000'); source=local_policy |
| 156/101/1 | 오크 / 오크족 고리 갑옷 | 활성 | l1jdb:3936 SQL: INSERT INTO `droplist` VALUES ('45009', 'Orc', '20135', 'Orcish Ring Mail', '1', '1', '50000'); source=local_policy |
| 156/177/1 | 오크 / 사파이어 | 잔여 | ItemDef 등록. L1J item 변종 대응과 해당 NPC 확률/수량 미확정. |
| 156/246/1 | 오크 / 미스릴 원석 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 156/299/1 | 오크 / 변신 주문서 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 156/569/1 | 오크 / 정령옥 | 잔여 | ItemDef 등록. 해당 NPC·후보 item·grade의 확률/수량 행 없음. 타 NPC/등급 확률을 가져오지 않음. |
| 190/7/1 | 멧돼지 / 아데나 | 잔여 | ItemDef 등록. 해당 NPC·후보 item·grade의 확률/수량 행 없음. 타 NPC/등급 확률을 가져오지 않음. |
| 190/10/1 | 멧돼지 / 고기 | 활성 | l1jdb:4202 SQL: INSERT INTO `droplist` VALUES ('45058', 'Wild Boar', '40056', 'Meat', '1', '1', '50000'); source=local_policy |
| 190/332/1 | 멧돼지 / 동물가죽 | 잔여 | ItemDef 등록. 해당 NPC·후보 item·grade의 확률/수량 행 없음. 타 NPC/등급 확률을 가져오지 않음. |
| 223/13/1 | 오우거 / 전투 도끼 | 활성 | l1jdb:6174 SQL: INSERT INTO `droplist` VALUES ('45278', 'Ogre', '143', 'Battle Axe', '1', '1', '85000'); source=local_policy |
| 223/26/1 | 오우거 / 갑옷 마법 주문서 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 223/94/1 | 오우거 / 미늘 갑옷 | 활성 | l1jdb:6178 SQL: INSERT INTO `droplist` VALUES ('45278', 'Ogre', '20115', 'Splint Mail', '1', '1', '25000'); source=local_policy |
| 223/138/1 | 오우거 / 대형 도끼 | 활성 | l1jdb:6176 SQL: INSERT INTO `droplist` VALUES ('45278', 'Ogre', '148', 'Great Axe', '1', '1', '25000'); source=local_policy |
| 223/144/1 | 오우거 / 광전사의 도끼 | 활성 | l1jdb:6175 SQL: INSERT INTO `droplist` VALUES ('45278', 'Ogre', '145', 'Berserker Axe', '1', '1', '5000'); source=local_policy |
| 223/250/1 | 오우거 / 오우거의 피 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 223/293/1 | 오우거 / 마법의 투구: 힘 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 223/296/1 | 오우거 / 용기의 물약 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 223/566/1 | 오우거 / 오우거의 벨트 | 잔여 | ItemDef 미등록. 장신구 슬롯·능력치·착용 계약. |
| 235/171/1 | 거대 개미 / 에메랄드 | 잔여 | ItemDef 등록. L1J item 변종 대응과 해당 NPC 확률/수량 미확정. |
| 235/291/1 | 거대 개미 / 마법의 투구: 치유 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 235/296/1 | 거대 개미 / 용기의 물약 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 235/495/1 | 거대 개미 / 강화 초록 물약 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 236/93/1 | 거대 병정 개미 / 청동 판금 갑옷 | 활성 | l1jdb:5354 SQL: INSERT INTO `droplist` VALUES ('45190', 'Giant Soldier Ant', '20149', 'Bronze Plate Mail', '1', '1', '5000'); source=local_policy |
| 236/171/1 | 거대 병정 개미 / 에메랄드 | 잔여 | ItemDef 등록. L1J item 변종 대응과 해당 NPC 확률/수량 미확정. |
| 236/172/1 | 거대 병정 개미 / 고급 에메랄드 | 잔여 | ItemDef 등록. L1J item 변종 대응과 해당 NPC 확률/수량 미확정. |
| 236/173/1 | 거대 병정 개미 / 최고급 에메랄드 | 잔여 | ItemDef 등록. L1J item 변종 대응과 해당 NPC 확률/수량 미확정. |
| 236/174/1 | 거대 병정 개미 / 루비 | 잔여 | ItemDef 등록. L1J item 변종 대응과 해당 NPC 확률/수량 미확정. |
| 236/175/1 | 거대 병정 개미 / 고급 루비 | 잔여 | ItemDef 등록. L1J item 변종 대응과 해당 NPC 확률/수량 미확정. |
| 236/176/1 | 거대 병정 개미 / 최고급 루비 | 잔여 | ItemDef 등록. L1J item 변종 대응과 해당 NPC 확률/수량 미확정. |
| 236/293/1 | 거대 병정 개미 / 마법의 투구: 힘 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 236/296/1 | 거대 병정 개미 / 용기의 물약 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 236/495/1 | 거대 병정 개미 / 강화 초록 물약 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 245/35/1 | 고블린 / 넓은 검 | 활성 | l1jdb:3926 weapon 23 Broad Sword $66 bless1 (:63724); source=local_policy |
| 249/16/1 | 코볼트 / 불투명 물약 | 잔여 | ItemDef 등록. 해당 NPC·후보 item·grade의 확률/수량 행 없음. 타 NPC/등급 확률을 가져오지 않음. |
| 249/332/1 | 코볼트 / 동물가죽 | 활성 | l1jdb:3959 원문: INSERT INTO `droplist` VALUES ('45016', 'Kobold', '40405', 'Fur', '1', '1', '50000'); source=local_policy |
| 274/166/1 | 오크 마법사 / 마력의 돌 | 잔여 | ItemDef 등록. 해당 NPC·후보 item·grade의 확률/수량 행 없음. 타 NPC/등급 확률을 가져오지 않음. |
| 274/201/1 | 오크 마법사 / 마법서 (그레이터 힐) | 활성 | l1jdb:4667 SQL: INSERT INTO `droplist` VALUES ('45121', 'Orc Wizard', '40180', 'Spellbook(GreaterHeal)', '1', '1', '10000'); source=local_policy |
| 274/230/1 | 오크 마법사 / 참나무 지팡이 | 활성 | l1jdb:4663 SQL: INSERT INTO `droplist` VALUES ('45121', 'Orc Wizard', '128', 'Oak Staff', '1', '1', '50000'); source=local_policy |
| 274/231/1 | 오크 마법사 / 마법사의 지팡이 | 활성 | l1jdb:4664 SQL: INSERT INTO `droplist` VALUES ('45121', 'Orc Wizard', '129', 'Wizard`s Staff', '1', '1', '10000'); source=local_policy |
| 274/233/1 | 오크 마법사 / 힘의 지팡이 | 활성 | l1jdb:4665 SQL: INSERT INTO `droplist` VALUES ('45121', 'Orc Wizard', '131', 'Staff of Strength', '1', '1', '1000'); source=local_policy |
| 274/492/1 | 오크 마법사 / 파란 물약 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 274/522/1 | 오크 마법사 / 마법서 (선 버스트) | 활성 | l1jdb:4668 SQL: INSERT INTO `droplist` VALUES ('45121', 'Orc Wizard', '40191', 'Spellbook(SunBurst)', '1', '1', '10000'); source=local_policy |
| 276/111/1 | 해골궁수 / 마법 망토 | 활성 | l1jdb:4676 SQL: INSERT INTO `droplist` VALUES ('45122', 'Skeleton Archer', '20056', 'Cloak of Magic Resistance', '1', '1', '50000'); source=local_policy |
| 276/166/1 | 해골궁수 / 마력의 돌 | 잔여 | ItemDef 등록. 해당 NPC·후보 item·grade의 확률/수량 행 없음. 타 NPC/등급 확률을 가져오지 않음. |
| 276/195/1 | 해골궁수 / 마법서 (인챈트 덱스터리티) | 활성 | l1jdb:4679 SQL: INSERT INTO `droplist` VALUES ('45122', 'Skeleton Archer', '40171', 'Spellbook(EnchantDex)', '1', '1', '10000'); source=local_policy |
| 276/336/1 | 해골궁수 / 뼈조각 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 276/495/1 | 해골궁수 / 강화 초록 물약 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 277/19/1 | 해골도끼병 / 소나무 막대 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 277/90/1 | 해골도끼병 / 투구 | 잔여 | ItemDef 등록. 해당 NPC·후보 item·grade의 확률/수량 행 없음. 타 NPC/등급 확률을 가져오지 않음. |
| 277/111/1 | 해골도끼병 / 마법 망토 | 활성 | l1jdb:4758 SQL: INSERT INTO `droplist` VALUES ('45130', 'Skeleton Axeman', '20056', 'Cloak of Magic Resistance', '1', '1', '50000'); source=local_policy |
| 277/166/1 | 해골도끼병 / 마력의 돌 | 잔여 | ItemDef 등록. 해당 NPC·후보 item·grade의 확률/수량 행 없음. 타 NPC/등급 확률을 가져오지 않음. |
| 277/336/1 | 해골도끼병 / 뼈조각 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 277/495/1 | 해골도끼병 / 강화 초록 물약 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 278/12/1 | 해골창병 / 창 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 278/90/1 | 해골창병 / 투구 | 잔여 | ItemDef 등록. 해당 NPC·후보 item·grade의 확률/수량 행 없음. 타 NPC/등급 확률을 가져오지 않음. |
| 278/111/1 | 해골창병 / 마법 망토 | 활성 | l1jdb:4767 SQL: INSERT INTO `droplist` VALUES ('45131', 'Skeleton Soldier', '20056', 'Cloak of Magic Resistance', '1', '1', '50000'); source=local_policy |
| 278/166/1 | 해골창병 / 마력의 돌 | 잔여 | ItemDef 등록. 해당 NPC·후보 item·grade의 확률/수량 행 없음. 타 NPC/등급 확률을 가져오지 않음. |
| 278/195/1 | 해골창병 / 마법서 (인챈트 덱스터리티) | 활성 | l1jdb:4770 SQL: INSERT INTO `droplist` VALUES ('45131', 'Skeleton Soldier', '40171', 'Spellbook(EnchantDex)', '1', '1', '10000'); source=local_policy |
| 278/336/1 | 해골창병 / 뼈조각 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 278/495/1 | 해골창병 / 강화 초록 물약 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 297/33/1 | 다크 엘프 / 요정족 활 | 활성 | l1jdb:6027 SQL: INSERT INTO `droplist` VALUES ('45265', 'Dark Elf', '170', 'Elven Bow', '1', '1', '10000'); source=local_policy |
| 297/86/1 | 다크 엘프 / 엘븐 와퍼 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 297/105/1 | 다크 엘프 / 요정족 망토 | 활성 | l1jdb:6028 SQL: INSERT INTO `droplist` VALUES ('45265', 'Dark Elf', '20073', 'Elven Cloak', '1', '1', '15000'); source=local_policy |
| 297/213/1 | 다크 엘프 / 마법서 (토네이도) | 활성 | l1jdb:6038 SQL: INSERT INTO `droplist` VALUES ('45265', 'Dark Elf', '40198', 'Spellbook(Tornado)', '1', '1', '4000'); source=local_policy |
| 297/217/1 | 다크 엘프 / 마법서 (인비지블리티) | 활성 | l1jdb:6039 SQL: INSERT INTO `droplist` VALUES ('45265', 'Dark Elf', '40205', 'Spellbook(Invisibility)', '1', '1', '800'); source=local_policy |
| 297/258/1 | 다크 엘프 / 미스릴 화살 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 297/267/1 | 다크 엘프 / 요정족 흉갑 | 활성 | l1jdb:6029 SQL: INSERT INTO `droplist` VALUES ('45265', 'Dark Elf', '20139', 'Elven Breast Plate', '1', '1', '10000'); source=local_policy |
| 297/492/1 | 다크 엘프 / 파란 물약 | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 297/569/1 | 다크 엘프 / 정령옥 | 잔여 | ItemDef 등록. 해당 NPC·후보 item·grade의 확률/수량 행 없음. 타 NPC/등급 확률을 가져오지 않음. |
| 297/575/1 | 다크 엘프 / 정령의 수정 (리턴 투 네이처) | 잔여 | ItemDef 등록. 해당 NPC SQL roll은 있으나 item/grade/변종 대응 미확정. |
| 297/602/1 | 다크 엘프 / 마법서 (메디테이션) | 잔여 | ItemDef 등록. 해당 NPC·후보 item·grade의 확률/수량 행 없음. 타 NPC/등급 확률을 가져오지 않음. |

## 검증

JSON 파싱, game_data.load_items(382행), 각 game_data._drops 로더를 실행했다. 유효 활성의 ItemDef 누락0, 신규103개의 실제 native JSONL f5/f6/f10 직접 대조, 고정 client 구성과 활성/미해결 분할 일치, 양쪽중복·누락·client밖 항목0을 확인했다. 게임·서버·포트·봇 실행은 하지 않았다. source note의 인코딩 손상 문자열도 재생성 후 검사했다.

## 드롭 보류 60조합 재대조 (qDrops, 2026-10-28)

**20조합 LOCAL 승격 / 40조합 잔여.** 대상은 기존 `official_recheck_20261028`의 60키다. 맵별 보류 원문145행 중35행을 해결하고110행을 남겼다. 해결35행은 활성34행이다. m5 NPC17/item21의 중복 보류 원문2개는 모두 history에 보존하고 지급행은1개만 둔다. 위 첫 보강 집계는 역사적 기록이며 전체535미해결과 이번60키를 혼동하지 않는다.

공식 몬스터23종·아이템10종을 live API로 다시 읽고 `data/official` 캐시 및 고정 L1J SQL을 대조했다. 대상60/60 보상 ID/이름은 live·캐시 일치. 공식은 확률·수량·L1J 변종 ID를 제공하지 않는다. 원응답·SQL 추출·판정은 `work/drop_recheck_20261028/{official-monster-*.json,official-item-*.json,l1j_selected.json,decisions.json}`에 보존했다. SQL은 `D:/SingleLineageRef/l1j-en-classic/db/l1jdb_m10.sql`이다.

승격은 **원본 등가 확정이 아닌 명시 LOCAL 아이템 대응 및 roll 정책**이다. 기존 숫자 전부 일치만 요구하던 보류를 공식 상세·설명 ID·재질·기능 설명·품질별 이름·아이콘의 추가 근거로 좁혀 해소했다. client ID/등급/그래픽/무게/기능은 바꾸지 않았다.

- 흑단 막대21(3조합): 공식 별칭 ‘번개 소환 막대’/나무/weight7/번개 설명 ↔ SQL40007 wand/wood/weight7000/itemdesc21/icon118/ground28 및 C_ItemUSe.java40007 경로. client token$263 대 SQL$262, f10=55 대 SQL7000은 보존하며 같은 필드로 확정하지 않는다. 충전·사용 효과 지원은 별도다.
- 괴물 눈 고기9(1조합): 공식 동물성/weight10/괴물눈 살 설명 ↔ SQL40057 food/animalmatter/weight10000/itemdesc9/ground3176. icon124↔1205·토큰 차이는 LOCAL 버전 대응으로 명시했다.
- 오크 투사 목걸이314(3조합): 공식 HP+20/AC0/착용Lv10/보석/weight5 ↔ SQL20263 itemdesc314/HP20/AC0/min_lvl10/gemstone/weight5000 및 같은 token$1013/ground3164. icon436↔1193은 보존한다. 기존 장비 효과·저장 형식은 수정하지 않았다.
- 보석13조합: 공식 루비·에메랄드의 일반/고급/최고급 이름·품질별 고유 아이콘과 SQL Ruby/Emerald·High/Highest Quality·gem/gemstone·일반등급·바닥 그래픽을 함께 대응했다. 새 client 토큰↔SQL 조합 토큰, raw39↔SQL40 차이는 보존했다.
- 모든 신규 roll은 `source=local_policy`, 선정 NPC 자신의 SQL chance/min/max이며 다른 NPC·아이템·등급 대입은 없다. NPC6은 기존 population의 NPC45126 참고 정책을 재사용하며 원본5/6 변종 동일성을 주장하지 않는다.
- 활성 이동 전 원행은 각 표의 `resolved_unresolved_history.original_unresolved`에 보존했다. 남은 행은 `qdrops_recheck_20261028.reason`과 기존 세부 reason을 함께 읽는다.

|표|해결한 보류 원문행|추가 활성행|보류 물리행|
|---|---:|---:|---:|
|m1|4|4|16|
|m3|4|4|20|
|m4|10|10|32|
|m5|6|5|17|
|m6|11|11|25|

### 승격20조합

확률 분모1,000,000, 수량 모두1. SQL 줄번호는 고정 L1J 파일 기준이다.

|client NPC|아이템 ID·이름|L1J NPC/item|chance|SQL 줄|
|---|---|---|---:|---:|
|5|21 흑단 막대|45126/40007|50000|4703|
|5|176 최고급 루비|45126/40053|1000|4707|
|6|21 흑단 막대|45126/40007|50000|4703|
|6|176 최고급 루비|45126/40053|1000|4707|
|11|9 괴물 눈 고기|45068/40057|300000|4266|
|17|21 흑단 막대|45136/40007|20000|4807|
|91|174 루비|45149/40045|25000|4970|
|91|314 오크 투사의 목걸이|45149/20263|1500|4963|
|92|174 루비|45171/40045|10000|5183|
|92|314 오크 투사의 목걸이|45171/20263|1000|5178|
|93|175 고급 루비|45143/40049|10000|4900|
|93|314 오크 투사의 목걸이|45143/20263|800|4892|
|95|174 루비|45127/40045|10000|4726|
|235|171 에메랄드|45115/40047|50000|4610|
|236|171 에메랄드|45190/40047|75000|5361|
|236|172 고급 에메랄드|45190/40051|20000|5363|
|236|173 최고급 에메랄드|45190/40055|5000|5365|
|236|174 루비|45190/40045|50000|5360|
|236|175 고급 루비|45190/40049|12500|5362|
|236|176 최고급 루비|45190/40053|2500|5364|

### 남은40조합

등급0/1/2=축복/일반/저주. 상세 차이·타 등급 SQL 원문은 각 drops.json의 기존 reason에 보존했다.

|client NPC|아이템 ID·이름|등급|남긴 이유|
|---|---|---:|---|
|2|97 오크족 사슬 갑옷|2|선정 NPC 자신의 동일 아이템·등급 droplist 확률/수량 행 없음. 다른 NPC·등급 값 대입 안 함.|
|2|167 사슬 갑옷|1|선정 NPC 자신의 동일 아이템·등급 droplist 확률/수량 행 없음. 다른 NPC·등급 값 대입 안 함.|
|5|166 마력의 돌|1|선정 NPC 자신의 동일 아이템·등급 droplist 확률/수량 행 없음. 다른 NPC·등급 값 대입 안 함.|
|5|520 마법서 (어스 재일)|1|선정 NPC 자신의 동일 아이템·등급 droplist 확률/수량 행 없음. 다른 NPC·등급 값 대입 안 함.|
|6|166 마력의 돌|1|선정 NPC 자신의 동일 아이템·등급 droplist 확률/수량 행 없음. 다른 NPC·등급 값 대입 안 함.|
|6|520 마법서 (어스 재일)|1|선정 NPC 자신의 동일 아이템·등급 droplist 확률/수량 행 없음. 다른 NPC·등급 값 대입 안 함.|
|6|545 돌 장갑|1|돌 장갑545에 대응하는 선정 NPC45126 자신의 L1J 아이템·등급·droplist 행을 확인 못 함.|
|7|19 소나무 막대|1|선정 NPC 자신의 동일 아이템·등급 droplist 확률/수량 행 없음. 다른 NPC·등급 값 대입 안 함.|
|7|20 단풍나무 막대|1|선정 NPC 자신의 동일 아이템·등급 droplist 확률/수량 행 없음. 다른 NPC·등급 값 대입 안 함.|
|7|166 마력의 돌|1|선정 NPC 자신의 동일 아이템·등급 droplist 확률/수량 행 없음. 다른 NPC·등급 값 대입 안 함.|
|7|12120 신비한 지혜의 물약|1|공식12120은 젬 연구용 특수 재료(거래/보관/드롭 불가, weight0). L1J40016은 itemdesc297/일반 지혜 물약/weight4500: 다른 물건이므로 NPC 자신의 행이 있어도 대입 불가.|
|11|166 마력의 돌|1|선정 NPC 자신의 동일 아이템·등급 droplist 확률/수량 행 없음. 다른 NPC·등급 값 대입 안 함.|
|17|121 셸로브 발톱|1|client121 셸로브 발톱(139/150, raw f10=0)과 L1J49046 Spider Leg Meat(food/itemdesc2778, 2727/36, weight10000)는 종류·설명 ID·그래픽이 달라 대응 불가.|
|29|67 언월도|2|선정 NPC 자신의 동일 아이템·등급 droplist 확률/수량 행 없음. 다른 NPC·등급 값 대입 안 함.|
|29|166 마력의 돌|1|선정 NPC 자신의 동일 아이템·등급 droplist 확률/수량 행 없음. 다른 NPC·등급 값 대입 안 함.|
|29|694 언데드의 열쇠|1|선정 NPC 자신의 동일 아이템·등급 droplist 확률/수량 행 없음. 다른 NPC·등급 값 대입 안 함.|
|30|166 마력의 돌|1|선정 NPC 자신의 동일 아이템·등급 droplist 확률/수량 행 없음. 다른 NPC·등급 값 대입 안 함.|
|91|229 투구|1|선정 NPC 자신의 동일 아이템·등급 droplist 확률/수량 행 없음. 다른 NPC·등급 값 대입 안 함.|
|92|97 오크족 사슬 갑옷|1|선정 NPC 자신의 동일 아이템·등급 droplist 확률/수량 행 없음. 다른 NPC·등급 값 대입 안 함.|
|92|495 강화 초록 물약|1|선정 NPC 자신의 동일 아이템·등급 droplist 확률/수량 행 없음. 다른 NPC·등급 값 대입 안 함.|
|93|166 마력의 돌|1|선정 NPC 자신의 동일 아이템·등급 droplist 확률/수량 행 없음. 다른 NPC·등급 값 대입 안 함.|
|93|229 투구|1|선정 NPC 자신의 동일 아이템·등급 droplist 확률/수량 행 없음. 다른 NPC·등급 값 대입 안 함.|
|94|166 마력의 돌|1|선정 NPC 자신의 동일 아이템·등급 droplist 확률/수량 행 없음. 다른 NPC·등급 값 대입 안 함.|
|95|167 사슬 갑옷|1|선정 NPC 자신의 동일 아이템·등급 droplist 확률/수량 행 없음. 다른 NPC·등급 값 대입 안 함.|
|156|20 단풍나무 막대|1|선정 NPC 자신의 동일 아이템·등급 droplist 확률/수량 행 없음. 다른 NPC·등급 값 대입 안 함.|
|156|29 화살|1|선정 NPC 자신의 동일 아이템·등급 droplist 확률/수량 행 없음. 다른 NPC·등급 값 대입 안 함.|
|156|71 오크족 창|1|선정 NPC 자신의 동일 아이템·등급 droplist 확률/수량 행 없음. 다른 NPC·등급 값 대입 안 함.|
|156|177 사파이어|1|선정 NPC 자신의 동일 아이템·등급 droplist 확률/수량 행 없음. 다른 NPC·등급 값 대입 안 함.|
|156|569 정령옥|1|선정 NPC 자신의 동일 아이템·등급 droplist 확률/수량 행 없음. 다른 NPC·등급 값 대입 안 함.|
|190|7 아데나|1|선정 NPC 자신의 동일 아이템·등급 droplist 확률/수량 행 없음. 다른 NPC·등급 값 대입 안 함.|
|190|332 동물가죽|1|선정 NPC 자신의 동일 아이템·등급 droplist 확률/수량 행 없음. 다른 NPC·등급 값 대입 안 함.|
|249|16 불투명 물약|1|선정 NPC 자신의 동일 아이템·등급 droplist 확률/수량 행 없음. 다른 NPC·등급 값 대입 안 함.|
|274|166 마력의 돌|1|선정 NPC 자신의 동일 아이템·등급 droplist 확률/수량 행 없음. 다른 NPC·등급 값 대입 안 함.|
|276|166 마력의 돌|1|선정 NPC 자신의 동일 아이템·등급 droplist 확률/수량 행 없음. 다른 NPC·등급 값 대입 안 함.|
|277|90 투구|1|선정 NPC 자신의 동일 아이템·등급 droplist 확률/수량 행 없음. 다른 NPC·등급 값 대입 안 함.|
|277|166 마력의 돌|1|선정 NPC 자신의 동일 아이템·등급 droplist 확률/수량 행 없음. 다른 NPC·등급 값 대입 안 함.|
|278|90 투구|1|선정 NPC 자신의 동일 아이템·등급 droplist 확률/수량 행 없음. 다른 NPC·등급 값 대입 안 함.|
|278|166 마력의 돌|1|선정 NPC 자신의 동일 아이템·등급 droplist 확률/수량 행 없음. 다른 NPC·등급 값 대입 안 함.|
|297|569 정령옥|1|선정 NPC 자신의 동일 아이템·등급 droplist 확률/수량 행 없음. 다른 NPC·등급 값 대입 안 함.|
|297|602 마법서 (메디테이션)|1|선정 NPC 자신의 동일 아이템·등급 droplist 확률/수량 행 없음. 다른 NPC·등급 값 대입 안 함.|

### qDrops 검증·한계

- 포트52000: `python -X utf8 -B -m unittest`로 `tools.local_original_session.world_reward_tests`, `world_m1_reward_tests`의 WorldRewardTests/ProgressStoreTests/KitCapacityTests/BrokerRewardTests.test_kill_drop_pickup_into_kit_inventory_and_saved_progress 실행 → **32 tests OK**. 각 이름은 동일 패키지 접두어 사용. 로그 `work/drop_recheck_20261028/drop-tests.log`.
- 같은 포트52000: game_data_tests의 test_m1_tables_load_and_link/test_official_stats_keep_client_weight_precision_and_l1j_gaps, world_m3_data_tests의 test_table_references_and_sources, world_ground_items_tests → **16 tests OK**. 로그 `work/drop_recheck_20261028/data-ground-tests.log`.
- `SL_TEST_PORT_BASE=53000 SL_TEST_TIME_SCALE=10 python -X utf8 -B C:/Users/Chansol/AppData/Local/Temp/claude/D--claude/0483de89-75e7-4b94-84b8-fb31fe00f575/scratchpad/fastbot/run_fast.py hunt_bot_loopback --minutes 3` → **exit0 FINISHED, 13처치/17바닥 드롭/17줍기**, 사망0·보정0·줍기 거절0·bot failure=false·broker failure=null·cleanup=true. 가상180.03초/실제58.652초. 현재 hunt_bot_scenarios에는 hunt 옵션이 없어서 기존 loopback 사냥·드롭·줍기 경로를 사용했다.
- 시작 저장은 새 소유 fixture `work/local_original_session/runs/hunt-loopback-hbpvze_e`의 SoloKnight(기존 loopback seed). 정상 FIRST→로그인→선택→월드→실제 공격·줍기 요청. progression·kit 저장 및 종료 결과는 `work/drop_recheck_20261028/hunt-loopback.log`에 보존했다. PowerShell이 stderr FAST_CLOCK을 JSON 중간에 삽입한 원로그도 수정하지 않았다.
- 기존5개 표를 실제 `_drops`로 읽어 활성 키 중복0 확인. 기존 M1/M3/M4/M6/M5 로더 조합에 승격20/20키가 한 번씩 로드되고 등록 ItemDef 및 roll.source=local_policy임을 확인했다.
- 수정 전 넓은47시험에는 이미 소모품 프레임 관련 **2건 실패**가 있었다: game_data_tests.test_official_heal_ranges_drive_rng_and_preserve_status(frames가1개보다 많음), world_m1_reward_tests.BrokerRewardTests.test_potion_sends_older_queued_frames_first(0x4ED8을0x4E38로 기대). 원로그 `work/drop_recheck_20261028/tests-before.log` 보존. 기존 기대값·소모품 코드 수정은 하지 않았다. 드롭 관련48시험 PASS와 이 실패는 별개다.
- 원본 클라이언트 실행 없음. 봇은 일반 드롭 경로 회귀이며 승격20종 각각의 무작위 실획득·native 렌더링·효과·원본 확률을 입증하지 않는다. 원본 확인 대상: 아이콘/바닥 표시·등급별 변종·막대 충전/효과·공식 확률/수량.
- 변경: `tools/local_original_session/data/{m1,m3,m4,m5,m6}/drops.json`, 본 문서, DEFERRED_BACKLOG.md. 수집/적용 스크립트 및 원응답은 `work/drop_recheck_20261028/`. 제품 Python·몬스터 표·사용자 저장·수동 실행 핀·launcher·기존 시험 기대값 수정 및 커밋 없음.

## 전체 미해결 드롭 재대조 (2026-10-29)

현재 ItemDef567종(+M4 전용67), 고정 client item/grade, 고유 아이템 대응, 선정 NPC 자신의 L1J SQL roll을 전부 다시 대조했다. **1774원행 = 쓰기 가능1362 + m5 읽기 전용144 + population 읽기 전용268**이다. ice_cave와 map_expansion3~6의 unresolved는 지도/전이 보류이며 drop row가 아니다. 원래 활성행·과거 판단 원문은 보존했다. 위 2026-10-28 수치는 당시 snapshot이다.

**신규 물리 활성449 = m1 251 + m3 22 + m4 42 + m6 121 + catalog13**. catalog는 참고표이며 제품 로더가 소비하지 않는다. 제품 표의 물리 증분은436이다. 실제 순차 로더 `load_m1 → with_dungeon_data → load_m4 → load_dungeon_data → load_m5_data`(`SL_EXPERIMENT_MAP=0`, 명시 조합)의 유효 활성은1315→1726, **+411**이다. 제품 물리436 중25행은 기존 template 우선 병합으로 가려진다. 같은 조합의 전/후를 `_read`의 착수 원문 대체로 계산했다. m1 745→996(+251), m3 802→1075(+273), m4 977→1292(+315), m6 1283→1694(+411), m5 1315→1726(+411)이다. 실행 중 feature설정이나 실제획득 수를 의미하지 않는다. m5의 조건충족46행·population의 조건충족86행은 소유/수정 금지 범위이므로 그대로 미해결에 남겼고 활성 수에 합산하지 않았다. 나머지 standalone writable913행·readonly280행은 아래 사유로 보류했다. 현재 남은 미해결1325행의 범주는 **목적NPC roll없음793 + 고유신원미확정366 + ItemDef부재31 + f21등급없는공식placeholder1 + SQL확률범위밖2 + 수정범위보류132**다. 범위보류132는 m5 46+population86이며, 다른 결함 사유와 중복 합산하지 않았다.

기존 활성표에서 같은 client item/grade에 붙은 SQL 아이템 신원을 재사용했다(248대응, SQL ID 충돌0). 각 새 행의 `mapping.reused_identity`와 `mapping.note`에 원경로/정책을 남겼다. 보석 새토큰·raw무게 차이, 물약/주문서 무게와 identified/unidentified 토큰 차이를 원문 그대로 보존했다. **확률·수량은 재사용하지 않고 목적 NPC의 droplist 원행에서 읽었다.** 신규 대응은 token·kind·grade·raw weight의 고유 조합과 장비 subtype/이름을 대조했고 그래픽 버전 차이는 각각 명시했다. 낡은 벨트502/503/504는 Old Body/Mind/Soul 의미와 belt·grade1·고유icon/ground/raw weight가 SQL20306/20308/20307과 일치하며 단일화된 client토큰↔조합 SQL토큰 차이를 명시했다.

SQL 출처는 `D:/SingleLineageRef/l1j-en-classic/db/l1jdb_m10.sql`. 새 활성마다 `mapping.ref`에 실제 SQL item행, `roll.ref`에 실제 목적NPC droplist행, `resolved_unresolved_history`에 기존 unresolved 전체를 보존했다. 반지64→20288은 토큰$241·ring·grade1·weight3000, 반지65→20281은$261·ring·grade1·weight3000, 목걸이311→20254는$1007·amulet·grade1·weight5000으로 고유하고 client/SQL 그래픽 차이는 지우지 않았다. 바포메트24의 64/311은 각각 NPC45573 자신의 SQL10026(chance5000)·10023(chance20000), count1이다.

표의 `uN`은 착수 시 `/unresolved/N` (0부터)이며, 키는 client 몬스터/아이템/등급이다. 활성 이동 후 N은 현재 배열 인덱스가 아니며 해당 원문은 history에서 찾는다. `p`는 m6/map_expansion2_population.json, `c0`는 catalog/map0/drops.json, 나머지는 각 mN/drops.json이다. A=활성, S=조건충족하나 수정범위 보류, D=현재 ItemDef부재, F=공식 전용 placeholder grade라 fixed f21 등급근거 없음, I=같은 등급의 고유 item 신원 미확정, R=확정 item의 목적NPC 자신의 roll 없음, X=SQL chance 범위밖. I에는 SQL 같은grade 후보 ID와 현재 client 토큰을 남겼고, 토큰만 비슷한 후보를 활성화하지 않았다. R에는 정확한 SQLitem/grade를 남겼다. 공식 확률·수량·변종 서버 동일성은 UNKNOWN이다.

| 표/원행 | 몬스터/아이템/등급 | 선정NPC | 결과·현재 이유 / SQL 원행 |
| --- | --- | ---: | --- |
| m1/u0 | 249/16/1 | 45016 | I: $239 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u1 | 2/167/1 | 45082 | R: item20125 grade1 목적NPC roll 없음 |
| m1/u2 | 2/97/2 | 45082 | R: item220136 grade2 목적NPC roll 없음 |
| m1/u3 | 29/166/1 | 45107 | R: item40318 grade1 목적NPC roll 없음 |
| m1/u4 | 29/67/2 | 45107 | R: item200027 grade2 목적NPC roll 없음 |
| m1/u5 | 29/694/1 | 45107 | I: $2030 grade1 후보40581; 고유 신원/차이 대응 미확정 |
| m1/u6 | 5/520/1 | 45126 | R: item40175 grade1 목적NPC roll 없음 |
| m1/u7 | 5/166/1 | 45126 | R: item40318 grade1 목적NPC roll 없음 |
| m1/u8 | 17/121/1 | 45136 | I: $311 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u9 | 7/19/1 | 45215 | R: item40006 grade1 목적NPC roll 없음 |
| m1/u10 | 7/20/1 | 45215 | R: item40008 grade1 목적NPC roll 없음 |
| m1/u11 | 7/166/1 | 45215 | R: item40318 grade1 목적NPC roll 없음 |
| m1/u12 | 7/12120/1 | 45215 | I: $16527 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u13 | 11/166/1 | 45068 | R: item40318 grade1 목적NPC roll 없음 |
| m1/u14 | 15/168/1 | 45165 | I: $15771 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u15 | 15/171/1 | 45165 | A: item40047; SQL5130; 10000/1000000; 1..1 |
| m1/u16 | 15/174/1 | 45165 | A: item40045; SQL5128; 10000/1000000; 1..1 |
| m1/u17 | 15/177/1 | 45165 | I: $15777 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u18 | 15/296/1 | 45165 | A: item40014; SQL5124; 50000/1000000; 1..1 |
| m1/u19 | 15/492/1 | 45165 | A: item40015; SQL5125; 50000/1000000; 1..1 |
| m1/u20 | 15/633/1 | 45165 | I: $1905 grade1 후보40540; 고유 신원/차이 대응 미확정 |
| m1/u21 | 15/639/1 | 45165 | I: $1911 grade1 후보40608; 고유 신원/차이 대응 미확정 |
| m1/u22 | 16/3/1 | 45600 | A: item31; SQL10451; 300000/1000000; 1..1 |
| m1/u23 | 16/6/0 | 45600 | R: item100052 grade0 목적NPC roll 없음 |
| m1/u24 | 16/23/1 | 45600 | A: item40100; SQL10473; 300000/1000000; 1..1 |
| m1/u25 | 16/25/1 | 45600 | A: item40087; SQL10471; 300000/1000000; 1..2 |
| m1/u26 | 16/26/1 | 45600 | A: item40074; SQL10470; 700000/1000000; 1..5 |
| m1/u27 | 16/28/1 | 45600 | A: item40089; SQL10472; 300000/1000000; 1..1 |
| m1/u28 | 16/117/1 | 45600 | R: item20242 grade1 목적NPC roll 없음 |
| m1/u29 | 16/289/1 | 45600 | R: item20238 grade1 목적NPC roll 없음 |
| m1/u30 | 16/296/1 | 45600 | A: item40014; SQL10466; 300000/1000000; 2..5 |
| m1/u31 | 16/492/1 | 45600 | A: item40015; SQL10467; 300000/1000000; 2..5 |
| m1/u32 | 16/1862/1 | 45600 | R: item40166 grade1 목적NPC roll 없음 |
| m1/u33 | 16/1863/1 | 45600 | R: item41147 grade1 목적NPC roll 없음 |
| m1/u34 | 177/7/1 | 45042 | R: item40308 grade1 목적NPC roll 없음 |
| m1/u35 | 190/7/1 | 45058 | R: item40308 grade1 목적NPC roll 없음 |
| m1/u36 | 190/332/1 | 45058 | R: item40405 grade1 목적NPC roll 없음 |
| m1/u37 | 176/7/1 | 45047 | R: item40308 grade1 목적NPC roll 없음 |
| m1/u38 | 178/7/1 | 45054 | R: item40308 grade1 목적NPC roll 없음 |
| m1/u39 | 216/17/1 | 45583 | A: item40013; SQL10213; 300000/1000000; 1..5 |
| m1/u40 | 216/64/1 | 45583 | A: item20288; SQL10205; 5000/1000000; 1..1 |
| m1/u41 | 216/91/0 | 45583 | R: item120154 grade0 목적NPC roll 없음 |
| m1/u42 | 216/166/1 | 45583 | R: item40318 grade1 목적NPC roll 없음 |
| m1/u43 | 216/168/1 | 45583 | I: $15771 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u44 | 216/169/1 | 45583 | I: $15772 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u45 | 216/170/1 | 45583 | I: $15773 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u46 | 216/174/1 | 45583 | A: item40045; SQL10219; 300000/1000000; 1..1 |
| m1/u47 | 216/175/1 | 45583 | A: item40049; SQL10221; 300000/1000000; 1..1 |
| m1/u48 | 216/176/1 | 45583 | A: item40053; SQL10223; 300000/1000000; 1..1 |
| m1/u49 | 216/310/1 | 45583 | A: item20267; SQL10203; 10000/1000000; 1..1 |
| m1/u50 | 216/492/1 | 45583 | A: item40015; SQL10215; 300000/1000000; 1..5 |
| m1/u51 | 216/495/1 | 45583 | A: item40018; SQL10217; 300000/1000000; 1..1 |
| m1/u52 | 216/502/1 | 45583 | A: item20306; SQL10207; 35000/1000000; 1..1 |
| m1/u53 | 216/504/1 | 45583 | A: item20307; SQL10208; 35000/1000000; 1..1 |
| m1/u54 | 216/569/1 | 45583 | R: item40319 grade1 목적NPC roll 없음 |
| m1/u55 | 216/586/1 | 45583 | I: $1845 grade1 후보40262; 고유 신원/차이 대응 미확정 |
| m1/u56 | 216/1097/1 | 45583 | R: item123 grade1 목적NPC roll 없음 |
| m1/u57 | 246/17/1 | 45259 | A: item40013; SQL5960; 50000/1000000; 1..1 |
| m1/u58 | 246/292/1 | 45259 | A: item20013; SQL5959; 1000/1000000; 1..1 |
| m1/u59 | 246/495/1 | 45259 | A: item40018; SQL5962; 50000/1000000; 1..1 |
| m1/u60 | 247/168/1 | 45381 | I: $15771 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u61 | 247/169/1 | 45381 | I: $15772 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u62 | 247/170/1 | 45381 | I: $15773 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u63 | 247/520/1 | 45381 | R: item40175 grade1 목적NPC roll 없음 |
| m1/u64 | 247/575/1 | 45381 | A: item40237; SQL7393; 10000/1000000; 1..1 |
| m1/u65 | 247/12117/1 | 45381 | I: $16516 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u66 | 248/17/1 | 45361 | A: item40013; SQL7029; 50000/1000000; 1..1 |
| m1/u67 | 248/21/1 | 45361 | A: item40007; SQL7028; 50000/1000000; 1..1 |
| m1/u68 | 248/495/1 | 45361 | A: item40018; SQL7032; 50000/1000000; 1..1 |
| m1/u69 | 248/582/1 | 45361 | I: $1841 grade1 후보40248; 고유 신원/차이 대응 미확정 |
| m1/u70 | 248/12573/1 | 45361 | D: item12573 현재 ItemDef 없음 |
| m1/u71 | 250/17/1 | 45529 | A: item40013; SQL9277; 300000/1000000; 1..1 |
| m1/u72 | 250/28/1 | 45529 | R: item40089 grade1 목적NPC roll 없음 |
| m1/u73 | 250/166/1 | 45529 | R: item40318 grade1 목적NPC roll 없음 |
| m1/u74 | 250/168/1 | 45529 | I: $15771 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u75 | 250/169/1 | 45529 | I: $15772 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u76 | 250/170/1 | 45529 | I: $15773 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u77 | 250/171/1 | 45529 | A: item40047; SQL9285; 85000/1000000; 1..1 |
| m1/u78 | 250/172/1 | 45529 | A: item40051; SQL9289; 50000/1000000; 1..1 |
| m1/u79 | 250/173/1 | 45529 | A: item40055; SQL9293; 85000/1000000; 1..1 |
| m1/u80 | 250/174/1 | 45529 | A: item40045; SQL9283; 20000/1000000; 1..1 |
| m1/u81 | 250/175/1 | 45529 | A: item40049; SQL9287; 20000/1000000; 1..1 |
| m1/u82 | 250/176/1 | 45529 | A: item40053; SQL9291; 20000/1000000; 1..1 |
| m1/u83 | 250/177/1 | 45529 | I: $15777 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u84 | 250/178/1 | 45529 | I: $15778 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u85 | 250/179/1 | 45529 | I: $15779 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u86 | 250/492/1 | 45529 | A: item40015; SQL9279; 300000/1000000; 1..1 |
| m1/u87 | 250/495/1 | 45529 | A: item40018; SQL9281; 300000/1000000; 1..1 |
| m1/u88 | 250/583/1 | 45529 | I: $1842 grade1 후보40242; 고유 신원/차이 대응 미확정 |
| m1/u89 | 250/586/1 | 45529 | I: $1845 grade1 후보40262; 고유 신원/차이 대응 미확정 |
| m1/u90 | 250/1296/1 | 45529 | I: $3261 grade1 후보40240; 고유 신원/차이 대응 미확정 |
| m1/u91 | 250/12573/1 | 45529 | D: item12573 현재 ItemDef 없음 |
| m1/u92 | 282/20/1 | 45545 | A: item40008; SQL9580; 35000/1000000; 1..1 |
| m1/u93 | 282/25/2 | 45545 | R: item240087 grade2 목적NPC roll 없음 |
| m1/u94 | 282/26/2 | 45545 | R: item240074 grade2 목적NPC roll 없음 |
| m1/u95 | 282/111/1 | 45545 | R: item20056 grade1 목적NPC roll 없음 |
| m1/u96 | 282/166/1 | 45545 | R: item40318 grade1 목적NPC roll 없음 |
| m1/u97 | 282/205/1 | 45545 | R: item40187 grade1 목적NPC roll 없음 |
| m1/u98 | 282/492/1 | 45545 | A: item40015; SQL9581; 300000/1000000; 1..1 |
| m1/u99 | 282/506/1 | 45545 | R: item20319 grade1 목적NPC roll 없음 |
| m1/u100 | 282/569/1 | 45545 | R: item40319 grade1 목적NPC roll 없음 |
| m1/u101 | 282/576/1 | 45545 | I: $1835 grade1 후보40238; 고유 신원/차이 대응 미확정 |
| m1/u102 | 282/588/1 | 45545 | I: $1847 grade1 후보40254; 고유 신원/차이 대응 미확정 |
| m1/u103 | 282/788/1 | 45545 | R: item20225 grade1 목적NPC roll 없음 |
| m1/u104 | 282/12573/1 | 45545 | D: item12573 현재 ItemDef 없음 |
| m1/u105 | 286/177/1 | 45349 | I: $15777 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u106 | 286/178/1 | 45349 | I: $15778 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u107 | 286/179/1 | 45349 | I: $15779 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u108 | 286/575/1 | 45349 | A: item40237; SQL6880; 10000/1000000; 1..1 |
| m1/u109 | 286/605/1 | 45349 | R: item40192 grade1 목적NPC roll 없음 |
| m1/u110 | 286/608/1 | 45349 | R: item40201 grade1 목적NPC roll 없음 |
| m1/u111 | 286/1296/1 | 45349 | I: $3261 grade1 후보40240; 고유 신원/차이 대응 미확정 |
| m1/u112 | 299/23/1 | 45104 | R: item40100 grade1 목적NPC roll 없음 |
| m1/u113 | 299/115/1 | 45104 | R: item20237 grade1 목적NPC roll 없음 |
| m1/u114 | 459/166/1 | 45079 | R: item40318 grade1 목적NPC roll 없음 |
| m1/u115 | 459/168/1 | 45079 | I: $15771 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u116 | 459/171/1 | 45079 | A: item40047; SQL4340; 15000/1000000; 1..1 |
| m1/u117 | 459/174/1 | 45079 | A: item40045; SQL4338; 10000/1000000; 1..1 |
| m1/u118 | 459/177/1 | 45079 | I: $15777 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u119 | 463/21/1 | 45182 | A: item40007; SQL5271; 5000/1000000; 1..1 |
| m1/u120 | 463/210/1 | 45182 | R: item40195 grade1 목적NPC roll 없음 |
| m1/u121 | 463/545/1 | 45182 | I: $1798 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u122 | 463/547/1 | 45182 | A: item20175; SQL5270; 1200/1000000; 1..1 |
| m1/u123 | 463/588/1 | 45182 | I: $1847 grade1 후보40254; 고유 신원/차이 대응 미확정 |
| m1/u124 | 465/7/1 | 45048 | R: item40308 grade1 목적NPC roll 없음 |
| m1/u125 | 471/171/1 | 45338 | A: item40047; SQL6767; 120000/1000000; 1..1 |
| m1/u126 | 472/171/1 | 45101 | A: item40047; SQL4516; 75000/1000000; 1..1 |
| m1/u127 | 472/291/1 | 45101 | A: item20014; SQL4514; 1000/1000000; 1..1 |
| m1/u128 | 499/2/1 | 45683 | R: item41 grade1 목적NPC roll 없음 |
| m1/u129 | 499/17/1 | 45683 | R: item40013 grade1 목적NPC roll 없음 |
| m1/u130 | 499/19/1 | 45683 | R: item40006 grade1 목적NPC roll 없음 |
| m1/u131 | 499/20/1 | 45683 | R: item40008 grade1 목적NPC roll 없음 |
| m1/u132 | 499/25/1 | 45683 | R: item40087 grade1 목적NPC roll 없음 |
| m1/u133 | 499/25/2 | 45683 | R: item240087 grade2 목적NPC roll 없음 |
| m1/u134 | 499/26/1 | 45683 | R: item40074 grade1 목적NPC roll 없음 |
| m1/u135 | 499/26/2 | 45683 | R: item240074 grade2 목적NPC roll 없음 |
| m1/u136 | 499/64/1 | 45683 | A: item20288; SQL11863; 300000/1000000; 1..1 |
| m1/u137 | 499/65/1 | 45683 | A: item20281; SQL11862; 300000/1000000; 1..1 |
| m1/u138 | 499/78/0 | 45683 | A: item100057; SQL11897; 300000/1000000; 1..1 |
| m1/u139 | 499/78/1 | 45683 | R: item57 grade1 목적NPC roll 없음 |
| m1/u140 | 499/110/1 | 45683 | R: item20077 grade1 목적NPC roll 없음 |
| m1/u141 | 499/129/1 | 45683 | R: item20182 grade1 목적NPC roll 없음 |
| m1/u142 | 499/166/1 | 45683 | R: item40318 grade1 목적NPC roll 없음 |
| m1/u143 | 499/168/1 | 45683 | I: $15771 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u144 | 499/169/1 | 45683 | I: $15772 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u145 | 499/170/1 | 45683 | I: $15773 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u146 | 499/177/1 | 45683 | I: $15777 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u147 | 499/178/1 | 45683 | I: $15778 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u148 | 499/179/1 | 45683 | I: $15779 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u149 | 499/296/1 | 45683 | R: item40014 grade1 목적NPC roll 없음 |
| m1/u150 | 499/297/1 | 45683 | R: item40016 grade1 목적NPC roll 없음 |
| m1/u151 | 499/307/1 | 45683 | R: item20256 grade1 목적NPC roll 없음 |
| m1/u152 | 499/311/1 | 45683 | R: item20254 grade1 목적NPC roll 없음 |
| m1/u153 | 499/403/1 | 45683 | A: item20127; SQL11860; 6000/1000000; 1..1 |
| m1/u154 | 499/492/1 | 45683 | R: item40015 grade1 목적NPC roll 없음 |
| m1/u155 | 499/495/1 | 45683 | R: item40018 grade1 목적NPC roll 없음 |
| m1/u156 | 499/502/1 | 45683 | R: item20306 grade1 목적NPC roll 없음 |
| m1/u157 | 499/503/1 | 45683 | R: item20308 grade1 목적NPC roll 없음 |
| m1/u158 | 499/504/1 | 45683 | R: item20307 grade1 목적NPC roll 없음 |
| m1/u159 | 499/505/1 | 45683 | R: item20312 grade1 목적NPC roll 없음 |
| m1/u160 | 499/506/1 | 45683 | R: item20319 grade1 목적NPC roll 없음 |
| m1/u161 | 499/507/1 | 45683 | R: item20316 grade1 목적NPC roll 없음 |
| m1/u162 | 499/574/1 | 45683 | I: $1833 grade1 후보40236; 고유 신원/차이 대응 미확정 |
| m1/u163 | 500/17/1 | 45116 | A: item40013; SQL4624; 50000/1000000; 1..1 |
| m1/u164 | 500/175/1 | 45116 | A: item40049; SQL4627; 10000/1000000; 1..1 |
| m1/u165 | 500/229/1 | 45116 | I: $128 grade1 후보20043; 고유 신원/차이 대응 미확정 |
| m1/u166 | 500/495/1 | 45116 | A: item40018; SQL4626; 50000/1000000; 1..1 |
| m1/u167 | 503/7/1 | 45812 | R: item40308 grade1 목적NPC roll 없음 |
| m1/u168 | 503/177/1 | 45812 | I: $15777 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u169 | 503/178/1 | 45812 | I: $15778 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u170 | 503/179/1 | 45812 | I: $15779 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u171 | 503/198/1 | 45812 | R: item40174 grade1 목적NPC roll 없음 |
| m1/u172 | 503/210/1 | 45812 | R: item40195 grade1 목적NPC roll 없음 |
| m1/u173 | 503/492/1 | 45812 | A: item40015; SQL12544; 100000/1000000; 1..1 |
| m1/u174 | 503/588/1 | 45812 | I: $1847 grade1 후보40254; 고유 신원/차이 대응 미확정 |
| m1/u175 | 503/593/1 | 45812 | I: $1852 grade1 후보40255; 고유 신원/차이 대응 미확정 |
| m1/u176 | 503/1494/1 | 45812 | I: $17516 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u177 | 505/17/1 | 45192 | A: item40013; SQL5372; 50000/1000000; 1..1 |
| m1/u178 | 505/495/1 | 45192 | A: item40018; SQL5373; 50000/1000000; 1..1 |
| m1/u179 | 507/7/1 | 45819 | R: item40308 grade1 목적NPC roll 없음 |
| m1/u180 | 507/21/1 | 45819 | A: item40007; SQL12568; 50000/1000000; 1..1 |
| m1/u181 | 507/168/1 | 45819 | I: $15771 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u182 | 507/169/1 | 45819 | I: $15772 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u183 | 507/170/1 | 45819 | I: $15773 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u184 | 507/492/1 | 45819 | R: item40015 grade1 목적NPC roll 없음 |
| m1/u185 | 507/502/1 | 45819 | R: item20306 grade1 목적NPC roll 없음 |
| m1/u186 | 507/521/1 | 45819 | R: item40183 grade1 목적NPC roll 없음 |
| m1/u187 | 507/588/1 | 45819 | I: $1847 grade1 후보40254; 고유 신원/차이 대응 미확정 |
| m1/u188 | 507/3020/1 | 45819 | R: item264 grade1 목적NPC roll 없음 |
| m1/u189 | 511/12355/1 | 45159 | D: item12355 현재 ItemDef 없음 |
| m1/u190 | 513/7/1 | 45823 | R: item40308 grade1 목적NPC roll 없음 |
| m1/u191 | 513/168/1 | 45823 | I: $15771 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u192 | 513/169/1 | 45823 | I: $15772 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u193 | 513/170/1 | 45823 | I: $15773 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u194 | 513/503/1 | 45823 | R: item20308 grade1 목적NPC roll 없음 |
| m1/u195 | 513/605/1 | 45823 | R: item40192 grade1 목적NPC roll 없음 |
| m1/u196 | 513/12573/1 | 45823 | D: item12573 현재 ItemDef 없음 |
| m1/u197 | 518/17/1 | 45160 | A: item40013; SQL5059; 50000/1000000; 1..1 |
| m1/u198 | 518/20/1 | 45160 | A: item40008; SQL5058; 10000/1000000; 1..1 |
| m1/u199 | 518/177/1 | 45160 | I: $15777 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u200 | 518/178/1 | 45160 | I: $15778 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u201 | 518/179/1 | 45160 | I: $15779 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u202 | 518/495/1 | 45160 | A: item40018; SQL5060; 50000/1000000; 1..1 |
| m1/u203 | 518/504/1 | 45160 | R: item20307 grade1 목적NPC roll 없음 |
| m1/u204 | 519/17/1 | 45195 | A: item40013; SQL5381; 50000/1000000; 1..1 |
| m1/u205 | 519/495/1 | 45195 | A: item40018; SQL5383; 50000/1000000; 1..1 |
| m1/u206 | 520/650/1 | 45240 | I: $1922 grade1 후보40601; 고유 신원/차이 대응 미확정 |
| m1/u207 | 560/492/1 | 45189 | A: item40015; SQL5349; 50000/1000000; 1..1 |
| m1/u208 | 621/2/1 | 45684 | R: item41 grade1 목적NPC roll 없음 |
| m1/u209 | 621/17/1 | 45684 | R: item40013 grade1 목적NPC roll 없음 |
| m1/u210 | 621/19/1 | 45684 | R: item40006 grade1 목적NPC roll 없음 |
| m1/u211 | 621/20/1 | 45684 | R: item40008 grade1 목적NPC roll 없음 |
| m1/u212 | 621/25/1 | 45684 | R: item40087 grade1 목적NPC roll 없음 |
| m1/u213 | 621/25/2 | 45684 | R: item240087 grade2 목적NPC roll 없음 |
| m1/u214 | 621/26/1 | 45684 | R: item40074 grade1 목적NPC roll 없음 |
| m1/u215 | 621/26/2 | 45684 | R: item240074 grade2 목적NPC roll 없음 |
| m1/u216 | 621/64/1 | 45684 | A: item20288; SQL11924; 300000/1000000; 1..1 |
| m1/u217 | 621/65/1 | 45684 | A: item20281; SQL11923; 300000/1000000; 1..1 |
| m1/u218 | 621/78/0 | 45684 | A: item100057; SQL11963; 300000/1000000; 1..1 |
| m1/u219 | 621/78/1 | 45684 | R: item57 grade1 목적NPC roll 없음 |
| m1/u220 | 621/91/1 | 45684 | R: item20154 grade1 목적NPC roll 없음 |
| m1/u221 | 621/110/1 | 45684 | R: item20077 grade1 목적NPC roll 없음 |
| m1/u222 | 621/129/1 | 45684 | R: item20182 grade1 목적NPC roll 없음 |
| m1/u223 | 621/166/1 | 45684 | R: item40318 grade1 목적NPC roll 없음 |
| m1/u224 | 621/168/1 | 45684 | I: $15771 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u225 | 621/169/1 | 45684 | I: $15772 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u226 | 621/170/1 | 45684 | I: $15773 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u227 | 621/174/1 | 45684 | A: item40045; SQL11926; 300000/1000000; 1..1 |
| m1/u228 | 621/175/1 | 45684 | A: item40049; SQL11928; 300000/1000000; 1..1 |
| m1/u229 | 621/176/1 | 45684 | A: item40053; SQL11930; 300000/1000000; 1..1 |
| m1/u230 | 621/205/1 | 45684 | R: item40187 grade1 목적NPC roll 없음 |
| m1/u231 | 621/296/1 | 45684 | R: item40014 grade1 목적NPC roll 없음 |
| m1/u232 | 621/297/1 | 45684 | R: item40016 grade1 목적NPC roll 없음 |
| m1/u233 | 621/306/1 | 45684 | R: item20264 grade1 목적NPC roll 없음 |
| m1/u234 | 621/309/1 | 45684 | R: item20266 grade1 목적NPC roll 없음 |
| m1/u235 | 621/405/1 | 45684 | A: item20159; SQL11922; 6000/1000000; 1..1 |
| m1/u236 | 621/492/1 | 45684 | R: item40015 grade1 목적NPC roll 없음 |
| m1/u237 | 621/495/1 | 45684 | R: item40018 grade1 목적NPC roll 없음 |
| m1/u238 | 621/502/1 | 45684 | R: item20306 grade1 목적NPC roll 없음 |
| m1/u239 | 621/503/1 | 45684 | R: item20308 grade1 목적NPC roll 없음 |
| m1/u240 | 621/504/1 | 45684 | R: item20307 grade1 목적NPC roll 없음 |
| m1/u241 | 621/505/1 | 45684 | R: item20312 grade1 목적NPC roll 없음 |
| m1/u242 | 621/506/1 | 45684 | R: item20319 grade1 목적NPC roll 없음 |
| m1/u243 | 621/507/1 | 45684 | R: item20316 grade1 목적NPC roll 없음 |
| m1/u244 | 701/7/1 | 46129 | R: item40308 grade1 목적NPC roll 없음 |
| m1/u245 | 701/23/0 | 46129 | R: item140100 grade0 목적NPC roll 없음 |
| m1/u246 | 701/299/1 | 46129 | R: item40088 grade1 목적NPC roll 없음 |
| m1/u247 | 701/575/1 | 46129 | R: item40237 grade1 목적NPC roll 없음 |
| m1/u248 | 701/12353/1 | 46129 | D: item12353 현재 ItemDef 없음 |
| m1/u249 | 701/12573/1 | 46129 | D: item12573 현재 ItemDef 없음 |
| m1/u250 | 702/17/1 | 45267 | A: item40013; SQL6049; 50000/1000000; 1..1 |
| m1/u251 | 702/166/1 | 45267 | R: item40318 grade1 목적NPC roll 없음 |
| m1/u252 | 702/495/1 | 45267 | A: item40018; SQL6050; 50000/1000000; 1..1 |
| m1/u253 | 702/569/1 | 45267 | R: item40319 grade1 목적NPC roll 없음 |
| m1/u254 | 702/3019/1 | 45267 | R: item263 grade1 목적NPC roll 없음 |
| m1/u255 | 704/220/1 | 45294 | R: item40211 grade1 목적NPC roll 없음 |
| m1/u256 | 704/510/1 | 45294 | I: $17272 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u257 | 704/547/1 | 45294 | R: item20175 grade1 목적NPC roll 없음 |
| m1/u258 | 704/569/1 | 45294 | R: item40319 grade1 목적NPC roll 없음 |
| m1/u259 | 704/927/1 | 45294 | I: $2592 grade1 후보40524; 고유 신원/차이 대응 미확정 |
| m1/u260 | 704/1491/1 | 45294 | I: $17513 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u261 | 704/3019/1 | 45294 | R: item263 grade1 목적NPC roll 없음 |
| m1/u262 | 704/12573/1 | 45294 | D: item12573 현재 ItemDef 없음 |
| m1/u263 | 706/7/1 | 45053 | R: item40308 grade1 목적NPC roll 없음 |
| m1/u264 | 709/7/1 | 81221 | R: item40308 grade1 목적NPC roll 없음 |
| m1/u265 | 709/13/1 | 81221 | R: item143 grade1 목적NPC roll 없음 |
| m1/u266 | 709/17/1 | 81221 | R: item40013 grade1 목적NPC roll 없음 |
| m1/u267 | 709/166/1 | 81221 | R: item40318 grade1 목적NPC roll 없음 |
| m1/u268 | 709/492/1 | 81221 | R: item40015 grade1 목적NPC roll 없음 |
| m1/u269 | 709/495/1 | 81221 | R: item40018 grade1 목적NPC roll 없음 |
| m1/u270 | 709/569/1 | 81221 | R: item40319 grade1 목적NPC roll 없음 |
| m1/u271 | 710/17/1 | 45609 | A: item40013; SQL10693; 300000/1000000; 2..5 |
| m1/u272 | 710/64/1 | 45609 | A: item20288; SQL10688; 5000/1000000; 1..1 |
| m1/u273 | 710/110/1 | 45609 | R: item20077 grade1 목적NPC roll 없음 |
| m1/u274 | 710/166/1 | 45609 | R: item40318 grade1 목적NPC roll 없음 |
| m1/u275 | 710/167/1 | 45609 | R: item20125 grade1 목적NPC roll 없음 |
| m1/u276 | 710/168/1 | 45609 | I: $15771 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u277 | 710/169/1 | 45609 | I: $15772 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u278 | 710/309/1 | 45609 | A: item20266; SQL10685; 12000/1000000; 1..1 |
| m1/u279 | 710/310/1 | 45609 | A: item20267; SQL10686; 18000/1000000; 1..1 |
| m1/u280 | 710/492/1 | 45609 | A: item40015; SQL10694; 300000/1000000; 2..5 |
| m1/u281 | 710/495/1 | 45609 | A: item40018; SQL10696; 300000/1000000; 2..5 |
| m1/u282 | 710/503/1 | 45609 | A: item20308; SQL10690; 50000/1000000; 1..1 |
| m1/u283 | 710/504/1 | 45609 | A: item20307; SQL10689; 50000/1000000; 1..1 |
| m1/u284 | 710/547/1 | 45609 | A: item20175; SQL10682; 8500/1000000; 1..1 |
| m1/u285 | 710/569/1 | 45609 | R: item40319 grade1 목적NPC roll 없음 |
| m1/u286 | 710/580/1 | 45609 | I: $1839 grade1 후보40261; 고유 신원/차이 대응 미확정 |
| m1/u287 | 710/588/1 | 45609 | I: $1847 grade1 후보40254; 고유 신원/차이 대응 미확정 |
| m1/u288 | 710/593/1 | 45609 | I: $1852 grade1 후보40255; 고유 신원/차이 대응 미확정 |
| m1/u289 | 710/597/1 | 45609 | I: $1856 grade1 후보40251; 고유 신원/차이 대응 미확정 |
| m1/u290 | 710/788/1 | 45609 | R: item20225 grade1 목적NPC roll 없음 |
| m1/u291 | 710/1094/1 | 45609 | R: item121 grade1 목적NPC roll 없음 |
| m1/u292 | 710/1493/1 | 45609 | I: $17515 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u293 | 710/1494/1 | 45609 | I: $17516 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u294 | 753/14/1 | 45805 | R: item40010 grade1 목적NPC roll 없음 |
| m1/u295 | 753/15/1 | 45805 | R: item40011 grade1 목적NPC roll 없음 |
| m1/u296 | 753/17/1 | 45805 | R: item40013 grade1 목적NPC roll 없음 |
| m1/u297 | 753/21/1 | 45805 | R: item40007 grade1 목적NPC roll 없음 |
| m1/u298 | 753/22/1 | 45805 | R: item40126 grade1 목적NPC roll 없음 |
| m1/u299 | 753/24/1 | 45805 | R: item40119 grade1 목적NPC roll 없음 |
| m1/u300 | 753/25/1 | 45805 | R: item40087 grade1 목적NPC roll 없음 |
| m1/u301 | 753/26/1 | 45805 | R: item40074 grade1 목적NPC roll 없음 |
| m1/u302 | 753/28/1 | 45805 | R: item40089 grade1 목적NPC roll 없음 |
| m1/u303 | 753/86/1 | 45805 | R: item40068 grade1 목적NPC roll 없음 |
| m1/u304 | 753/126/1 | 45805 | R: item40017 grade1 목적NPC roll 없음 |
| m1/u305 | 753/130/1 | 45805 | R: item40012 grade1 목적NPC roll 없음 |
| m1/u306 | 753/296/1 | 45805 | R: item40014 grade1 목적NPC roll 없음 |
| m1/u307 | 753/297/1 | 45805 | R: item40016 grade1 목적NPC roll 없음 |
| m1/u308 | 753/492/1 | 45805 | R: item40015 grade1 목적NPC roll 없음 |
| m1/u309 | 753/495/1 | 45805 | R: item40018 grade1 목적NPC roll 없음 |
| m1/u310 | 753/656/1 | 45805 | R: item20141 grade1 목적NPC roll 없음 |
| m1/u311 | 754/14/1 | 45387 | A: item40010; SQL7462; 300000/1000000; 1..1 |
| m1/u312 | 754/17/1 | 45387 | A: item40013; SQL7465; 50000/1000000; 1..1 |
| m1/u313 | 754/21/1 | 45387 | A: item40007; SQL7461; 10000/1000000; 1..1 |
| m1/u314 | 754/25/1 | 45387 | R: item40087 grade1 목적NPC roll 없음 |
| m1/u315 | 754/26/1 | 45387 | R: item40074 grade1 목적NPC roll 없음 |
| m1/u316 | 754/492/1 | 45387 | A: item40015; SQL7467; 15000/1000000; 1..1 |
| m1/u317 | 754/495/1 | 45387 | A: item40018; SQL7470; 10000/1000000; 1..1 |
| m1/u318 | 755/14/1 | 45387 | A: item40010; SQL7462; 300000/1000000; 1..1 |
| m1/u319 | 755/17/1 | 45387 | A: item40013; SQL7465; 50000/1000000; 1..1 |
| m1/u320 | 755/21/1 | 45387 | A: item40007; SQL7461; 10000/1000000; 1..1 |
| m1/u321 | 755/25/1 | 45387 | R: item40087 grade1 목적NPC roll 없음 |
| m1/u322 | 755/26/1 | 45387 | R: item40074 grade1 목적NPC roll 없음 |
| m1/u323 | 755/492/1 | 45387 | A: item40015; SQL7467; 15000/1000000; 1..1 |
| m1/u324 | 755/495/1 | 45387 | A: item40018; SQL7470; 10000/1000000; 1..1 |
| m1/u325 | 755/657/1 | 45387 | A: item20142; SQL7459; 1500/1000000; 1..1 |
| m1/u326 | 756/14/1 | 81069 | R: item40010 grade1 목적NPC roll 없음 |
| m1/u327 | 756/15/1 | 81069 | R: item40011 grade1 목적NPC roll 없음 |
| m1/u328 | 756/17/1 | 81069 | R: item40013 grade1 목적NPC roll 없음 |
| m1/u329 | 756/21/1 | 81069 | R: item40007 grade1 목적NPC roll 없음 |
| m1/u330 | 756/22/1 | 81069 | R: item40126 grade1 목적NPC roll 없음 |
| m1/u331 | 756/24/1 | 81069 | R: item40119 grade1 목적NPC roll 없음 |
| m1/u332 | 756/25/1 | 81069 | R: item40087 grade1 목적NPC roll 없음 |
| m1/u333 | 756/26/1 | 81069 | R: item40074 grade1 목적NPC roll 없음 |
| m1/u334 | 756/28/1 | 81069 | R: item40089 grade1 목적NPC roll 없음 |
| m1/u335 | 756/86/1 | 81069 | R: item40068 grade1 목적NPC roll 없음 |
| m1/u336 | 756/126/1 | 81069 | R: item40017 grade1 목적NPC roll 없음 |
| m1/u337 | 756/130/1 | 81069 | R: item40012 grade1 목적NPC roll 없음 |
| m1/u338 | 756/296/1 | 81069 | R: item40014 grade1 목적NPC roll 없음 |
| m1/u339 | 756/297/1 | 81069 | R: item40016 grade1 목적NPC roll 없음 |
| m1/u340 | 756/492/1 | 81069 | R: item40015 grade1 목적NPC roll 없음 |
| m1/u341 | 756/495/1 | 81069 | R: item40018 grade1 목적NPC roll 없음 |
| m1/u342 | 756/674/1 | 81069 | R: item40076 grade1 목적NPC roll 없음 |
| m1/u343 | 756/927/1 | 81069 | I: $2592 grade1 후보40524; 고유 신원/차이 대응 미확정 |
| m1/u344 | 757/14/1 | 45445 | A: item40010; SQL8063; 300000/1000000; 1..1 |
| m1/u345 | 757/17/1 | 45445 | A: item40013; SQL8066; 50000/1000000; 1..1 |
| m1/u346 | 757/25/1 | 45445 | R: item40087 grade1 목적NPC roll 없음 |
| m1/u347 | 757/26/1 | 45445 | R: item40074 grade1 목적NPC roll 없음 |
| m1/u348 | 757/492/1 | 45445 | A: item40015; SQL8068; 10000/1000000; 1..1 |
| m1/u349 | 757/495/1 | 45445 | A: item40018; SQL8071; 10000/1000000; 1..1 |
| m1/u350 | 757/661/1 | 45445 | I: $1940 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u351 | 758/14/1 | 45196 | A: item40010; SQL5390; 300000/1000000; 1..1 |
| m1/u352 | 758/17/1 | 45196 | A: item40013; SQL5393; 50000/1000000; 1..1 |
| m1/u353 | 758/21/1 | 45196 | A: item40007; SQL5389; 10000/1000000; 1..1 |
| m1/u354 | 758/22/1 | 45196 | R: item40126 grade1 목적NPC roll 없음 |
| m1/u355 | 758/24/1 | 45196 | R: item40119 grade1 목적NPC roll 없음 |
| m1/u356 | 758/25/1 | 45196 | R: item40087 grade1 목적NPC roll 없음 |
| m1/u357 | 758/26/1 | 45196 | R: item40074 grade1 목적NPC roll 없음 |
| m1/u358 | 758/28/1 | 45196 | R: item40089 grade1 목적NPC roll 없음 |
| m1/u359 | 758/492/1 | 45196 | A: item40015; SQL5395; 10000/1000000; 1..1 |
| m1/u360 | 758/927/1 | 45196 | I: $2592 grade1 후보40524; 고유 신원/차이 대응 미확정 |
| m1/u361 | 759/14/1 | 45469 | A: item40010; SQL8437; 300000/1000000; 1..1 |
| m1/u362 | 759/17/1 | 45469 | A: item40013; SQL8440; 50000/1000000; 1..1 |
| m1/u363 | 759/21/1 | 45469 | A: item40007; SQL8436; 10000/1000000; 1..1 |
| m1/u364 | 759/25/1 | 45469 | R: item40087 grade1 목적NPC roll 없음 |
| m1/u365 | 759/26/1 | 45469 | R: item40074 grade1 목적NPC roll 없음 |
| m1/u366 | 759/492/1 | 45469 | A: item40015; SQL8442; 10000/1000000; 1..1 |
| m1/u367 | 759/495/1 | 45469 | A: item40018; SQL8445; 10000/1000000; 1..1 |
| m1/u368 | 759/497/1 | 45469 | R: item20280 grade1 목적NPC roll 없음 |
| m1/u369 | 759/654/1 | 45469 | A: item20143; SQL8433; 4000/1000000; 1..1 |
| m1/u370 | 759/927/1 | 45469 | I: $2592 grade1 후보40524; 고유 신원/차이 대응 미확정 |
| m1/u371 | 760/14/1 | 45505 | A: item40010; SQL8915; 300000/1000000; 1..1 |
| m1/u372 | 760/17/1 | 45505 | A: item40013; SQL8918; 50000/1000000; 1..1 |
| m1/u373 | 760/25/1 | 45505 | R: item40087 grade1 목적NPC roll 없음 |
| m1/u374 | 760/26/1 | 45505 | R: item40074 grade1 목적NPC roll 없음 |
| m1/u375 | 760/382/1 | 45505 | I: $1203 grade1 후보40899; 고유 신원/차이 대응 미확정 |
| m1/u376 | 760/492/1 | 45505 | A: item40015; SQL8920; 10000/1000000; 1..1 |
| m1/u377 | 760/495/1 | 45505 | A: item40018; SQL8923; 25000/1000000; 1..1 |
| m1/u378 | 760/654/1 | 45505 | A: item20143; SQL8913; 3500/1000000; 1..1 |
| m1/u379 | 760/659/1 | 45505 | I: $1938 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u380 | 761/14/1 | 45392 | A: item40010; SQL7554; 300000/1000000; 1..1 |
| m1/u381 | 761/17/1 | 45392 | A: item40013; SQL7557; 50000/1000000; 1..1 |
| m1/u382 | 761/21/1 | 45392 | A: item40007; SQL7553; 10000/1000000; 1..1 |
| m1/u383 | 761/25/1 | 45392 | R: item40087 grade1 목적NPC roll 없음 |
| m1/u384 | 761/26/1 | 45392 | R: item40074 grade1 목적NPC roll 없음 |
| m1/u385 | 761/492/1 | 45392 | A: item40015; SQL7559; 10000/1000000; 1..1 |
| m1/u386 | 761/495/1 | 45392 | A: item40018; SQL7562; 10000/1000000; 1..1 |
| m1/u387 | 762/14/1 | 45509 | A: item40010; SQL8975; 300000/1000000; 1..1 |
| m1/u388 | 762/17/1 | 45509 | A: item40013; SQL8978; 50000/1000000; 1..1 |
| m1/u389 | 762/21/1 | 45509 | A: item40007; SQL8974; 10000/1000000; 1..1 |
| m1/u390 | 762/25/1 | 45509 | R: item40087 grade1 목적NPC roll 없음 |
| m1/u391 | 762/26/1 | 45509 | R: item40074 grade1 목적NPC roll 없음 |
| m1/u392 | 762/492/1 | 45509 | A: item40015; SQL8980; 10000/1000000; 1..1 |
| m1/u393 | 762/495/1 | 45509 | A: item40018; SQL8983; 10000/1000000; 1..1 |
| m1/u394 | 762/654/1 | 45509 | A: item20143; SQL8971; 3500/1000000; 1..1 |
| m1/u395 | 762/927/1 | 45509 | I: $2592 grade1 후보40524; 고유 신원/차이 대응 미확정 |
| m1/u396 | 763/14/1 | 45531 | A: item40010; SQL9342; 300000/1000000; 1..1 |
| m1/u397 | 763/17/1 | 45531 | A: item40013; SQL9345; 50000/1000000; 1..1 |
| m1/u398 | 763/25/1 | 45531 | R: item40087 grade1 목적NPC roll 없음 |
| m1/u399 | 763/26/1 | 45531 | R: item40074 grade1 목적NPC roll 없음 |
| m1/u400 | 763/492/1 | 45531 | A: item40015; SQL9347; 10000/1000000; 1..1 |
| m1/u401 | 763/495/1 | 45531 | A: item40018; SQL9350; 10000/1000000; 1..1 |
| m1/u402 | 763/660/1 | 45531 | I: $1939 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u403 | 764/14/1 | 45362 | A: item40010; SQL7055; 300000/1000000; 1..1 |
| m1/u404 | 764/17/1 | 45362 | A: item40013; SQL7058; 50000/1000000; 1..1 |
| m1/u405 | 764/25/1 | 45362 | R: item40087 grade1 목적NPC roll 없음 |
| m1/u406 | 764/26/1 | 45362 | R: item40074 grade1 목적NPC roll 없음 |
| m1/u407 | 764/492/1 | 45362 | A: item40015; SQL7060; 12500/1000000; 1..1 |
| m1/u408 | 764/495/1 | 45362 | A: item40018; SQL7063; 15000/1000000; 1..1 |
| m1/u409 | 764/654/1 | 45362 | A: item20143; SQL7052; 3500/1000000; 1..1 |
| m1/u410 | 764/660/1 | 45362 | I: $1939 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u411 | 765/14/1 | 45538 | A: item40010; SQL9485; 300000/1000000; 1..1 |
| m1/u412 | 765/17/1 | 45538 | A: item40013; SQL9488; 50000/1000000; 1..1 |
| m1/u413 | 765/25/1 | 45538 | R: item40087 grade1 목적NPC roll 없음 |
| m1/u414 | 765/26/1 | 45538 | R: item40074 grade1 목적NPC roll 없음 |
| m1/u415 | 765/382/1 | 45538 | I: $1203 grade1 후보40899; 고유 신원/차이 대응 미확정 |
| m1/u416 | 765/492/1 | 45538 | A: item40015; SQL9490; 10000/1000000; 1..1 |
| m1/u417 | 765/495/1 | 45538 | A: item40018; SQL9493; 15000/1000000; 1..1 |
| m1/u418 | 765/654/1 | 45538 | A: item20143; SQL9483; 4000/1000000; 1..1 |
| m1/u419 | 765/659/1 | 45538 | I: $1938 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u420 | 766/14/1 | 45529 | R: item40010 grade1 목적NPC roll 없음 |
| m1/u421 | 766/15/1 | 45529 | R: item40011 grade1 목적NPC roll 없음 |
| m1/u422 | 766/17/1 | 45529 | A: item40013; SQL9277; 300000/1000000; 1..1 |
| m1/u423 | 766/21/1 | 45529 | R: item40007 grade1 목적NPC roll 없음 |
| m1/u424 | 766/22/1 | 45529 | R: item40126 grade1 목적NPC roll 없음 |
| m1/u425 | 766/24/1 | 45529 | R: item40119 grade1 목적NPC roll 없음 |
| m1/u426 | 766/28/1 | 45529 | R: item40089 grade1 목적NPC roll 없음 |
| m1/u427 | 766/86/1 | 45529 | R: item40068 grade1 목적NPC roll 없음 |
| m1/u428 | 766/126/1 | 45529 | R: item40017 grade1 목적NPC roll 없음 |
| m1/u429 | 766/130/1 | 45529 | R: item40012 grade1 목적NPC roll 없음 |
| m1/u430 | 766/492/1 | 45529 | A: item40015; SQL9279; 300000/1000000; 1..1 |
| m1/u431 | 766/495/1 | 45529 | A: item40018; SQL9281; 300000/1000000; 1..1 |
| m1/u432 | 766/496/1 | 45529 | R: item20303 grade1 목적NPC roll 없음 |
| m1/u433 | 766/497/1 | 45529 | R: item20280 grade1 목적NPC roll 없음 |
| m1/u434 | 766/655/1 | 45529 | R: item20140 grade1 목적NPC roll 없음 |
| m1/u435 | 766/658/1 | 45529 | R: item20284 grade1 목적NPC roll 없음 |
| m1/u436 | 766/661/1 | 45529 | I: $1940 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u437 | 766/674/1 | 45529 | R: item40076 grade1 목적NPC roll 없음 |
| m1/u438 | 766/927/1 | 45529 | I: $2592 grade1 후보40524; 고유 신원/차이 대응 미확정 |
| m1/u439 | 767/14/1 | 45452 | A: item40010; SQL8205; 300000/1000000; 1..1 |
| m1/u440 | 767/17/1 | 45452 | A: item40013; SQL8208; 50000/1000000; 1..1 |
| m1/u441 | 767/21/1 | 45452 | A: item40007; SQL8204; 20000/1000000; 1..1 |
| m1/u442 | 767/25/1 | 45452 | R: item40087 grade1 목적NPC roll 없음 |
| m1/u443 | 767/26/1 | 45452 | R: item40074 grade1 목적NPC roll 없음 |
| m1/u444 | 767/492/1 | 45452 | A: item40015; SQL8210; 50000/1000000; 1..1 |
| m1/u445 | 767/495/1 | 45452 | A: item40018; SQL8213; 10000/1000000; 1..1 |
| m1/u446 | 767/657/1 | 45452 | A: item20142; SQL8200; 2000/1000000; 1..1 |
| m1/u447 | 768/14/1 | 45390 | A: item40010; SQL7516; 300000/1000000; 1..1 |
| m1/u448 | 768/17/1 | 45390 | A: item40013; SQL7519; 50000/1000000; 1..1 |
| m1/u449 | 768/21/1 | 45390 | A: item40007; SQL7515; 10000/1000000; 1..1 |
| m1/u450 | 768/25/1 | 45390 | R: item40087 grade1 목적NPC roll 없음 |
| m1/u451 | 768/26/1 | 45390 | R: item40074 grade1 목적NPC roll 없음 |
| m1/u452 | 768/382/1 | 45390 | I: $1203 grade1 후보40899; 고유 신원/차이 대응 미확정 |
| m1/u453 | 768/492/1 | 45390 | A: item40015; SQL7521; 10000/1000000; 1..1 |
| m1/u454 | 768/495/1 | 45390 | A: item40018; SQL7524; 10000/1000000; 1..1 |
| m1/u455 | 768/657/1 | 45390 | A: item20142; SQL7513; 2500/1000000; 1..1 |
| m1/u456 | 768/12573/1 | 45390 | D: item12573 현재 ItemDef 없음 |
| m1/u457 | 769/14/1 | 45449 | A: item40010; SQL8138; 300000/1000000; 1..1 |
| m1/u458 | 769/17/1 | 45449 | A: item40013; SQL8141; 50000/1000000; 1..1 |
| m1/u459 | 769/25/1 | 45449 | R: item40087 grade1 목적NPC roll 없음 |
| m1/u460 | 769/26/1 | 45449 | R: item40074 grade1 목적NPC roll 없음 |
| m1/u461 | 769/382/1 | 45449 | I: $1203 grade1 후보40899; 고유 신원/차이 대응 미확정 |
| m1/u462 | 769/492/1 | 45449 | A: item40015; SQL8143; 12500/1000000; 1..1 |
| m1/u463 | 769/495/1 | 45449 | A: item40018; SQL8146; 15000/1000000; 1..1 |
| m1/u464 | 769/654/1 | 45449 | A: item20143; SQL8134; 3500/1000000; 1..1 |
| m1/u465 | 770/14/1 | 45389 | A: item40010; SQL7490; 300000/1000000; 1..1 |
| m1/u466 | 770/17/1 | 45389 | A: item40013; SQL7493; 50000/1000000; 1..1 |
| m1/u467 | 770/21/1 | 45389 | A: item40007; SQL7489; 10000/1000000; 1..1 |
| m1/u468 | 770/25/1 | 45389 | R: item40087 grade1 목적NPC roll 없음 |
| m1/u469 | 770/26/1 | 45389 | R: item40074 grade1 목적NPC roll 없음 |
| m1/u470 | 770/492/1 | 45389 | A: item40015; SQL7495; 10000/1000000; 1..1 |
| m1/u471 | 770/495/1 | 45389 | A: item40018; SQL7498; 10000/1000000; 1..1 |
| m1/u472 | 770/497/1 | 45389 | R: item20280 grade1 목적NPC roll 없음 |
| m1/u473 | 771/14/1 | 45355 | A: item40010; SQL6926; 300000/1000000; 1..1 |
| m1/u474 | 771/17/1 | 45355 | A: item40013; SQL6929; 50000/1000000; 1..1 |
| m1/u475 | 771/21/1 | 45355 | A: item40007; SQL6925; 10000/1000000; 1..1 |
| m1/u476 | 771/22/1 | 45355 | R: item40126 grade1 목적NPC roll 없음 |
| m1/u477 | 771/24/1 | 45355 | R: item40119 grade1 목적NPC roll 없음 |
| m1/u478 | 771/25/1 | 45355 | R: item40087 grade1 목적NPC roll 없음 |
| m1/u479 | 771/26/1 | 45355 | R: item40074 grade1 목적NPC roll 없음 |
| m1/u480 | 771/28/1 | 45355 | R: item40089 grade1 목적NPC roll 없음 |
| m1/u481 | 771/492/1 | 45355 | A: item40015; SQL6931; 10000/1000000; 1..1 |
| m1/u482 | 771/495/1 | 45355 | A: item40018; SQL6934; 10000/1000000; 1..1 |
| m1/u483 | 771/657/1 | 45355 | A: item20142; SQL6924; 1500/1000000; 1..1 |
| m1/u484 | 772/14/1 | 45371 | A: item40010; SQL7204; 300000/1000000; 1..1 |
| m1/u485 | 772/17/1 | 45371 | A: item40013; SQL7207; 50000/1000000; 1..1 |
| m1/u486 | 772/22/1 | 45371 | R: item40126 grade1 목적NPC roll 없음 |
| m1/u487 | 772/24/1 | 45371 | R: item40119 grade1 목적NPC roll 없음 |
| m1/u488 | 772/25/1 | 45371 | R: item40087 grade1 목적NPC roll 없음 |
| m1/u489 | 772/26/1 | 45371 | R: item40074 grade1 목적NPC roll 없음 |
| m1/u490 | 772/28/1 | 45371 | R: item40089 grade1 목적NPC roll 없음 |
| m1/u491 | 772/492/1 | 45371 | A: item40015; SQL7209; 10000/1000000; 1..1 |
| m1/u492 | 772/495/1 | 45371 | A: item40018; SQL7212; 10000/1000000; 1..1 |
| m1/u493 | 773/14/1 | 45358 | A: item40010; SQL6975; 300000/1000000; 1..1 |
| m1/u494 | 773/17/1 | 45358 | A: item40013; SQL6978; 50000/1000000; 1..1 |
| m1/u495 | 773/21/1 | 45358 | R: item40007 grade1 목적NPC roll 없음 |
| m1/u496 | 773/22/1 | 45358 | R: item40126 grade1 목적NPC roll 없음 |
| m1/u497 | 773/24/1 | 45358 | R: item40119 grade1 목적NPC roll 없음 |
| m1/u498 | 773/25/1 | 45358 | R: item40087 grade1 목적NPC roll 없음 |
| m1/u499 | 773/26/1 | 45358 | R: item40074 grade1 목적NPC roll 없음 |
| m1/u500 | 773/28/1 | 45358 | R: item40089 grade1 목적NPC roll 없음 |
| m1/u501 | 773/492/1 | 45358 | A: item40015; SQL6980; 10000/1000000; 1..1 |
| m1/u502 | 773/495/1 | 45358 | A: item40018; SQL6983; 10000/1000000; 1..1 |
| m1/u503 | 773/657/1 | 45358 | A: item20142; SQL6974; 1000/1000000; 1..1 |
| m1/u504 | 773/12573/1 | 45358 | D: item12573 현재 ItemDef 없음 |
| m1/u505 | 774/14/1 | 45401 | A: item40010; SQL7673; 300000/1000000; 1..1 |
| m1/u506 | 774/17/1 | 45401 | A: item40013; SQL7676; 50000/1000000; 1..1 |
| m1/u507 | 774/21/1 | 45401 | A: item40007; SQL7672; 10000/1000000; 1..1 |
| m1/u508 | 774/25/1 | 45401 | R: item40087 grade1 목적NPC roll 없음 |
| m1/u509 | 774/26/1 | 45401 | R: item40074 grade1 목적NPC roll 없음 |
| m1/u510 | 774/492/1 | 45401 | A: item40015; SQL7678; 10000/1000000; 1..1 |
| m1/u511 | 774/495/1 | 45401 | A: item40018; SQL7681; 10000/1000000; 1..1 |
| m1/u512 | 774/497/1 | 45401 | R: item20280 grade1 목적NPC roll 없음 |
| m1/u513 | 775/14/1 | 45477 | A: item40010; SQL8563; 300000/1000000; 1..1 |
| m1/u514 | 775/17/1 | 45477 | A: item40013; SQL8566; 50000/1000000; 1..1 |
| m1/u515 | 775/25/1 | 45477 | R: item40087 grade1 목적NPC roll 없음 |
| m1/u516 | 775/26/1 | 45477 | R: item40074 grade1 목적NPC roll 없음 |
| m1/u517 | 775/492/1 | 45477 | A: item40015; SQL8568; 10000/1000000; 1..1 |
| m1/u518 | 775/495/1 | 45477 | A: item40018; SQL8571; 10000/1000000; 1..1 |
| m1/u519 | 775/657/1 | 45477 | A: item20142; SQL8560; 3000/1000000; 1..1 |
| m1/u520 | 776/14/1 | 45378 | A: item40010; SQL7316; 300000/1000000; 1..1 |
| m1/u521 | 776/17/1 | 45378 | A: item40013; SQL7319; 50000/1000000; 1..1 |
| m1/u522 | 776/21/1 | 45378 | A: item40007; SQL7315; 25000/1000000; 1..1 |
| m1/u523 | 776/25/1 | 45378 | R: item40087 grade1 목적NPC roll 없음 |
| m1/u524 | 776/26/1 | 45378 | R: item40074 grade1 목적NPC roll 없음 |
| m1/u525 | 776/492/1 | 45378 | A: item40015; SQL7321; 10000/1000000; 1..1 |
| m1/u526 | 776/495/1 | 45378 | A: item40018; SQL7324; 10000/1000000; 1..1 |
| m1/u527 | 777/14/1 | 45470 | A: item40010; SQL8465; 300000/1000000; 1..1 |
| m1/u528 | 777/17/1 | 45470 | A: item40013; SQL8468; 50000/1000000; 1..1 |
| m1/u529 | 777/21/1 | 45470 | A: item40007; SQL8464; 10000/1000000; 1..1 |
| m1/u530 | 777/25/1 | 45470 | R: item40087 grade1 목적NPC roll 없음 |
| m1/u531 | 777/26/1 | 45470 | R: item40074 grade1 목적NPC roll 없음 |
| m1/u532 | 777/382/1 | 45470 | I: $1203 grade1 후보40899; 고유 신원/차이 대응 미확정 |
| m1/u533 | 777/492/1 | 45470 | A: item40015; SQL8470; 10000/1000000; 1..1 |
| m1/u534 | 777/495/1 | 45470 | A: item40018; SQL8473; 10000/1000000; 1..1 |
| m1/u535 | 777/497/1 | 45470 | R: item20280 grade1 목적NPC roll 없음 |
| m1/u536 | 827/14/1 | 45364 | A: item40010; SQL7112; 300000/1000000; 1..1 |
| m1/u537 | 827/17/1 | 45364 | A: item40013; SQL7115; 50000/1000000; 1..1 |
| m1/u538 | 827/21/1 | 45364 | A: item40007; SQL7111; 25000/1000000; 1..1 |
| m1/u539 | 827/25/1 | 45364 | R: item40087 grade1 목적NPC roll 없음 |
| m1/u540 | 827/26/1 | 45364 | R: item40074 grade1 목적NPC roll 없음 |
| m1/u541 | 827/492/1 | 45364 | A: item40015; SQL7117; 10000/1000000; 1..1 |
| m1/u542 | 827/495/1 | 45364 | A: item40018; SQL7120; 15000/1000000; 1..1 |
| m1/u543 | 884/7/1 | 45828 | R: item40308 grade1 목적NPC roll 없음 |
| m1/u544 | 884/299/1 | 45828 | R: item40088 grade1 목적NPC roll 없음 |
| m1/u545 | 884/492/1 | 45828 | A: item40015; SQL12604; 100000/1000000; 1..1 |
| m1/u546 | 885/6/0 | 45826 | R: item100052 grade0 목적NPC roll 없음 |
| m1/u547 | 885/7/1 | 45826 | R: item40308 grade1 목적NPC roll 없음 |
| m1/u548 | 885/17/1 | 45826 | R: item40013 grade1 목적NPC roll 없음 |
| m1/u549 | 885/20/1 | 45826 | R: item40008 grade1 목적NPC roll 없음 |
| m1/u550 | 885/25/0 | 45826 | R: item140087 grade0 목적NPC roll 없음 |
| m1/u551 | 885/25/1 | 45826 | R: item40087 grade1 목적NPC roll 없음 |
| m1/u552 | 885/26/0 | 45826 | R: item140074 grade0 목적NPC roll 없음 |
| m1/u553 | 885/26/1 | 45826 | R: item40074 grade1 목적NPC roll 없음 |
| m1/u554 | 885/28/1 | 45826 | R: item40089 grade1 목적NPC roll 없음 |
| m1/u555 | 885/93/1 | 45826 | R: item20149 grade1 목적NPC roll 없음 |
| m1/u556 | 885/111/1 | 45826 | R: item20056 grade1 목적NPC roll 없음 |
| m1/u557 | 885/194/1 | 45826 | R: item40170 grade1 목적NPC roll 없음 |
| m1/u558 | 885/205/1 | 45826 | R: item40187 grade1 목적NPC roll 없음 |
| m1/u559 | 885/206/1 | 45826 | R: item40188 grade1 목적NPC roll 없음 |
| m1/u560 | 885/211/1 | 45826 | R: item40196 grade1 목적NPC roll 없음 |
| m1/u561 | 885/231/1 | 45826 | R: item129 grade1 목적NPC roll 없음 |
| m1/u562 | 885/233/1 | 45826 | R: item131 grade1 목적NPC roll 없음 |
| m1/u563 | 885/296/1 | 45826 | R: item40014 grade1 목적NPC roll 없음 |
| m1/u564 | 885/297/1 | 45826 | R: item40016 grade1 목적NPC roll 없음 |
| m1/u565 | 885/492/1 | 45826 | R: item40015 grade1 목적NPC roll 없음 |
| m1/u566 | 885/495/1 | 45826 | R: item40018 grade1 목적NPC roll 없음 |
| m1/u567 | 885/583/1 | 45826 | I: $1842 grade1 후보40242; 고유 신원/차이 대응 미확정 |
| m1/u568 | 885/1294/1 | 45826 | R: item40164 grade1 목적NPC roll 없음 |
| m1/u569 | 885/1861/1 | 45826 | R: item40165 grade1 목적NPC roll 없음 |
| m1/u570 | 885/1862/1 | 45826 | R: item40166 grade1 목적NPC roll 없음 |
| m1/u571 | 885/1863/1 | 45826 | R: item41147 grade1 목적NPC roll 없음 |
| m1/u572 | 889/17/1 | 81229 | R: item40013 grade1 목적NPC roll 없음 |
| m1/u573 | 889/23/0 | 81229 | R: item140100 grade0 목적NPC roll 없음 |
| m1/u574 | 889/130/1 | 81229 | R: item40012 grade1 목적NPC roll 없음 |
| m1/u575 | 889/297/1 | 81229 | R: item40016 grade1 목적NPC roll 없음 |
| m1/u576 | 889/492/1 | 81229 | R: item40015 grade1 목적NPC roll 없음 |
| m1/u577 | 889/495/1 | 81229 | R: item40018 grade1 목적NPC roll 없음 |
| m1/u578 | 889/1861/1 | 81229 | R: item40165 grade1 목적NPC roll 없음 |
| m1/u579 | 889/1863/1 | 81229 | R: item41147 grade1 목적NPC roll 없음 |
| m1/u580 | 889/15410/1 | 81229 | I: $17765 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u581 | 891/14/1 | 45407 | A: item40010; SQL7766; 50000/1000000; 1..1 |
| m1/u582 | 891/17/1 | 45407 | A: item40013; SQL7769; 50000/1000000; 1..1 |
| m1/u583 | 891/21/1 | 45407 | A: item40007; SQL7765; 50000/1000000; 1..1 |
| m1/u584 | 891/28/1 | 45407 | R: item40089 grade1 목적NPC roll 없음 |
| m1/u585 | 891/495/1 | 45407 | A: item40018; SQL7773; 10000/1000000; 1..1 |
| m1/u586 | 891/603/1 | 45407 | R: item40184 grade1 목적NPC roll 없음 |
| m1/u587 | 891/15400/1 | 45407 | I: $17755 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u588 | 891/15410/1 | 45407 | I: $17765 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u589 | 895/67/1 | 45386 | R: item27 grade1 목적NPC roll 없음 |
| m1/u590 | 895/576/1 | 45386 | I: $1835 grade1 후보40238; 고유 신원/차이 대응 미확정 |
| m1/u591 | 895/586/1 | 45386 | I: $1845 grade1 후보40262; 고유 신원/차이 대응 미확정 |
| m1/u592 | 895/15410/1 | 45386 | I: $17765 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u593 | 897/19/1 | 81099 | R: item40006 grade1 목적NPC roll 없음 |
| m1/u594 | 897/23/1 | 81099 | R: item40100 grade1 목적NPC roll 없음 |
| m1/u595 | 897/24/1 | 81099 | R: item40119 grade1 목적NPC roll 없음 |
| m1/u596 | 897/25/0 | 81099 | R: item140087 grade0 목적NPC roll 없음 |
| m1/u597 | 897/25/1 | 81099 | R: item40087 grade1 목적NPC roll 없음 |
| m1/u598 | 897/25/2 | 81099 | R: item240087 grade2 목적NPC roll 없음 |
| m1/u599 | 897/26/0 | 81099 | R: item140074 grade0 목적NPC roll 없음 |
| m1/u600 | 897/26/1 | 81099 | R: item40074 grade1 목적NPC roll 없음 |
| m1/u601 | 897/26/2 | 81099 | R: item240074 grade2 목적NPC roll 없음 |
| m1/u602 | 897/28/1 | 81099 | R: item40089 grade1 목적NPC roll 없음 |
| m1/u603 | 897/94/1 | 81099 | R: item20115 grade1 목적NPC roll 없음 |
| m1/u604 | 897/119/1 | 81099 | R: item20229 grade1 목적NPC roll 없음 |
| m1/u605 | 897/207/1 | 81099 | R: item40189 grade1 목적NPC roll 없음 |
| m1/u606 | 897/222/1 | 81099 | R: item40213 grade1 목적NPC roll 없음 |
| m1/u607 | 897/297/1 | 81099 | R: item40016 grade1 목적NPC roll 없음 |
| m1/u608 | 897/311/1 | 81099 | R: item20254 grade1 목적NPC roll 없음 |
| m1/u609 | 897/605/1 | 81099 | R: item40192 grade1 목적NPC roll 없음 |
| m1/u610 | 897/608/1 | 81099 | R: item40201 grade1 목적NPC roll 없음 |
| m1/u611 | 897/742/1 | 81099 | R: item20227 grade1 목적NPC roll 없음 |
| m1/u612 | 897/15400/1 | 81099 | I: $17755 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u613 | 897/15410/1 | 81099 | I: $17765 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u614 | 899/23/1 | 45296 | R: item40100 grade1 목적NPC roll 없음 |
| m1/u615 | 899/28/1 | 45296 | R: item40089 grade1 목적NPC roll 없음 |
| m1/u616 | 899/297/1 | 45296 | R: item40016 grade1 목적NPC roll 없음 |
| m1/u617 | 900/78/1 | 45681 | R: item57 grade1 목적NPC roll 없음 |
| m1/u618 | 900/110/1 | 45681 | R: item20077 grade1 목적NPC roll 없음 |
| m1/u619 | 900/406/1 | 45681 | A: item20156; SQL11742; 6000/1000000; 1..1 |
| m1/u620 | 902/110/1 | 45678 | R: item20077 grade1 목적NPC roll 없음 |
| m1/u621 | 902/309/1 | 45678 | A: item20266; SQL11702; 20000/1000000; 1..1 |
| m1/u622 | 902/310/1 | 45678 | A: item20267; SQL11703; 20000/1000000; 1..1 |
| m1/u623 | 902/724/1 | 45678 | I: $2191 grade1 후보21070; 고유 신원/차이 대응 미확정 |
| m1/u624 | 971/78/1 | 45680 | A: item57; SQL11718; 16000/1000000; 1..1 |
| m1/u625 | 971/109/1 | 45680 | R: item20063 grade1 목적NPC roll 없음 |
| m1/u626 | 971/291/1 | 45680 | A: item20014; SQL11720; 300000/1000000; 1..1 |
| m1/u627 | 971/292/1 | 45680 | A: item20013; SQL11719; 300000/1000000; 1..1 |
| m1/u628 | 971/293/1 | 45680 | A: item20015; SQL11721; 300000/1000000; 1..1 |
| m1/u629 | 971/306/1 | 45680 | A: item20264; SQL11732; 20000/1000000; 1..1 |
| m1/u630 | 971/308/1 | 45680 | A: item20268; SQL11733; 20000/1000000; 1..1 |
| m1/u631 | 972/219/1 | 45102 | R: item40210 grade1 목적NPC roll 없음 |
| m1/u632 | 972/223/1 | 45102 | R: item40214 grade1 목적NPC roll 없음 |
| m1/u633 | 972/755/1 | 45102 | D: item755 현재 ItemDef 없음 |
| m1/u634 | 1025/17/1 | 45348 | A: item40013; SQL6863; 50000/1000000; 1..1 |
| m1/u635 | 1025/495/1 | 45348 | A: item40018; SQL6865; 50000/1000000; 1..1 |
| m1/u636 | 1025/15400/1 | 45348 | I: $17755 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u637 | 1025/15410/1 | 45348 | I: $17765 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u638 | 1026/492/1 | 45332 | A: item40015; SQL6712; 50000/1000000; 1..1 |
| m1/u639 | 1026/12573/1 | 45332 | D: item12573 현재 ItemDef 없음 |
| m1/u640 | 1026/15400/1 | 45332 | I: $17755 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u641 | 1026/15410/1 | 45332 | I: $17765 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u642 | 1027/219/1 | 45406 | R: item40210 grade1 목적NPC roll 없음 |
| m1/u643 | 1027/492/1 | 45406 | A: item40015; SQL7749; 50000/1000000; 1..1 |
| m1/u644 | 1027/575/1 | 45406 | A: item40237; SQL7758; 2500/1000000; 1..1 |
| m1/u645 | 1027/15410/1 | 45406 | I: $17765 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u646 | 1028/17/1 | 45399 | A: item40013; SQL7655; 300000/1000000; 1..1 |
| m1/u647 | 1028/229/1 | 45399 | I: $128 grade1 후보20043; 고유 신원/차이 대응 미확정 |
| m1/u648 | 1028/492/1 | 45399 | A: item40015; SQL7657; 65000/1000000; 1..1 |
| m1/u649 | 1028/12573/1 | 45399 | D: item12573 현재 ItemDef 없음 |
| m1/u650 | 1028/15410/1 | 45399 | I: $17765 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u651 | 1039/17/1 | 45513 | A: item40013; SQL9054; 300000/1000000; 1..3 |
| m1/u652 | 1039/28/0 | 45513 | I: $257 grade0 후보140089; 고유 신원/차이 대응 미확정 |
| m1/u653 | 1039/78/1 | 45513 | A: item57; SQL9043; 9000/1000000; 1..1 |
| m1/u654 | 1039/110/1 | 45513 | R: item20077 grade1 목적NPC roll 없음 |
| m1/u655 | 1039/167/1 | 45513 | R: item20125 grade1 목적NPC roll 없음 |
| m1/u656 | 1039/220/1 | 45513 | R: item40211 grade1 목적NPC roll 없음 |
| m1/u657 | 1039/280/1 | 45513 | A: item20187; SQL9047; 30000/1000000; 1..1 |
| m1/u658 | 1039/492/1 | 45513 | R: item40015 grade1 목적NPC roll 없음 |
| m1/u659 | 1039/495/1 | 45513 | A: item40018; SQL9057; 300000/1000000; 1..3 |
| m1/u660 | 1039/503/1 | 45513 | A: item20308; SQL9049; 100000/1000000; 1..1 |
| m1/u661 | 1039/608/1 | 45513 | R: item40201 grade1 목적NPC roll 없음 |
| m1/u662 | 1039/815/1 | 45513 | A: item20298; SQL9048; 15000/1000000; 1..1 |
| m1/u663 | 1039/1296/1 | 45513 | I: $3261 grade1 후보40240; 고유 신원/차이 대응 미확정 |
| m1/u664 | 1039/1490/1 | 45513 | I: $17512 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u665 | 1039/1491/1 | 45513 | I: $17513 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u666 | 1039/15456/1 | 45513 | I: $17921 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u667 | 1041/17/1 | 45547 | A: item40013; SQL9655; 300000/1000000; 1..3 |
| m1/u668 | 1041/28/0 | 45547 | I: $257 grade0 후보140089; 고유 신원/차이 대응 미확정 |
| m1/u669 | 1041/78/1 | 45547 | A: item57; SQL9643; 12000/1000000; 1..1 |
| m1/u670 | 1041/177/1 | 45547 | I: $15777 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u671 | 1041/178/1 | 45547 | I: $15778 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u672 | 1041/179/1 | 45547 | I: $15779 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u673 | 1041/219/1 | 45547 | R: item40210 grade1 목적NPC roll 없음 |
| m1/u674 | 1041/280/1 | 45547 | A: item20187; SQL9648; 22000/1000000; 1..1 |
| m1/u675 | 1041/309/1 | 45547 | A: item20266; SQL9649; 5000/1000000; 1..1 |
| m1/u676 | 1041/492/1 | 45547 | A: item40015; SQL9657; 300000/1000000; 1..3 |
| m1/u677 | 1041/495/1 | 45547 | A: item40018; SQL9659; 300000/1000000; 1..3 |
| m1/u678 | 1041/503/1 | 45547 | A: item20308; SQL9650; 50000/1000000; 1..1 |
| m1/u679 | 1041/576/1 | 45547 | I: $1835 grade1 후보40238; 고유 신원/차이 대응 미확정 |
| m1/u680 | 1041/592/1 | 45547 | I: $1851 grade1 후보40258; 고유 신원/차이 대응 미확정 |
| m1/u681 | 1041/595/1 | 45547 | I: $1854 grade1 후보40263; 고유 신원/차이 대응 미확정 |
| m1/u682 | 1041/15399/1 | 45547 | I: $12423 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u683 | 1041/15457/1 | 45547 | I: $17922 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u684 | 1331/17/1 | 81102 | R: item40013 grade1 목적NPC roll 없음 |
| m1/u685 | 1331/21/1 | 81102 | R: item40007 grade1 목적NPC roll 없음 |
| m1/u686 | 1331/23/0 | 81102 | R: item140100 grade0 목적NPC roll 없음 |
| m1/u687 | 1331/296/1 | 81102 | R: item40014 grade1 목적NPC roll 없음 |
| m1/u688 | 1331/297/1 | 81102 | R: item40016 grade1 목적NPC roll 없음 |
| m1/u689 | 1331/382/1 | 81102 | I: $1203 grade1 후보40899; 고유 신원/차이 대응 미확정 |
| m1/u690 | 1331/495/1 | 81102 | R: item40018 grade1 목적NPC roll 없음 |
| m1/u691 | 1331/621/1 | 81102 | R: item40092 grade1 목적NPC roll 없음 |
| m1/u692 | 1331/1862/1 | 81102 | R: item40166 grade1 목적NPC roll 없음 |
| m1/u693 | 1331/15400/1 | 81102 | I: $17755 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u694 | 1331/15410/1 | 81102 | I: $17765 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u695 | 1410/65/1 | 45393 | A: item20281; SQL7580; 500/1000000; 1..1 |
| m1/u696 | 1410/588/1 | 45393 | I: $1847 grade1 후보40254; 고유 신원/차이 대응 미확정 |
| m1/u697 | 1410/1491/1 | 45393 | F: 공식reward placeholder grade1, fixed f21등급연결 없음; native등급오류 확정 아님 |
| m1/u698 | 1410/15410/1 | 45393 | I: $17765 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u699 | 2381/7/1 | 45775 | R: item40308 grade1 목적NPC roll 없음 |
| m1/u700 | 2388/7/1 | 45778 | R: item40308 grade1 목적NPC roll 없음 |
| m1/u701 | 2389/7/1 | 45781 | R: item40308 grade1 목적NPC roll 없음 |
| m1/u702 | 2390/7/1 | 45780 | R: item40308 grade1 목적NPC roll 없음 |
| m1/u703 | 2391/7/1 | 45779 | R: item40308 grade1 목적NPC roll 없음 |
| m1/u704 | 2392/7/1 | 45773 | R: item40308 grade1 목적NPC roll 없음 |
| m1/u705 | 2394/7/1 | 45776 | R: item40308 grade1 목적NPC roll 없음 |
| m1/u706 | 2395/7/1 | 45777 | R: item40308 grade1 목적NPC roll 없음 |
| m1/u707 | 2397/7/1 | 45791 | R: item40308 grade1 목적NPC roll 없음 |
| m1/u708 | 2399/7/1 | 45792 | R: item40308 grade1 목적NPC roll 없음 |
| m1/u709 | 2400/7/1 | 45793 | R: item40308 grade1 목적NPC roll 없음 |
| m1/u710 | 2401/7/1 | 45784 | R: item40308 grade1 목적NPC roll 없음 |
| m1/u711 | 2403/7/1 | 45795 | R: item40308 grade1 목적NPC roll 없음 |
| m1/u712 | 2782/2586/1 | 46092 | D: item2586 현재 ItemDef 없음 |
| m1/u713 | 2783/2586/1 | 46093 | D: item2586 현재 ItemDef 없음 |
| m1/u714 | 2784/2586/1 | 46094 | D: item2586 현재 ItemDef 없음 |
| m1/u715 | 2785/2586/1 | 46095 | D: item2586 현재 ItemDef 없음 |
| m1/u716 | 2786/2586/1 | 46096 | D: item2586 현재 ItemDef 없음 |
| m1/u717 | 2787/2586/1 | 46106 | D: item2586 현재 ItemDef 없음 |
| m1/u718 | 10204/2586/1 | 46092 | D: item2586 현재 ItemDef 없음 |
| m1/u719 | 10205/2586/1 | 46093 | D: item2586 현재 ItemDef 없음 |
| m1/u720 | 10206/2586/1 | 46094 | D: item2586 현재 ItemDef 없음 |
| m1/u721 | 10207/2586/1 | 46095 | D: item2586 현재 ItemDef 없음 |
| m1/u722 | 10208/2586/1 | 46096 | D: item2586 현재 ItemDef 없음 |
| m1/u723 | 10209/2586/1 | 46106 | D: item2586 현재 ItemDef 없음 |
| m1/u724 | 10219/250/1 | 45278 | A: item40513; SQL6186; 2000/1000000; 1..1 |
| m1/u725 | 10219/293/1 | 45278 | A: item20015; SQL6177; 10000/1000000; 1..1 |
| m1/u726 | 10243/7/1 | 45622 | R: item40308 grade1 목적NPC roll 없음 |
| m1/u727 | 10243/17/1 | 45622 | R: item40013 grade1 목적NPC roll 없음 |
| m1/u728 | 10243/25/0 | 45622 | R: item140087 grade0 목적NPC roll 없음 |
| m1/u729 | 10243/28/1 | 45622 | R: item40089 grade1 목적NPC roll 없음 |
| m1/u730 | 10243/167/1 | 45622 | R: item20125 grade1 목적NPC roll 없음 |
| m1/u731 | 10243/492/1 | 45622 | R: item40015 grade1 목적NPC roll 없음 |
| m1/u732 | 10243/895/1 | 45622 | I: $17024 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u733 | 10243/2070/1 | 45622 | I: $4349 grade1 후보41352; 고유 신원/차이 대응 미확정 |
| m1/u734 | 10243/12876/1 | 45622 | I: $17822 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u735 | 10244/23/1 | 45206 | R: item40100 grade1 목적NPC roll 없음 |
| m1/u736 | 10244/25/1 | 45206 | R: item40087 grade1 목적NPC roll 없음 |
| m1/u737 | 10244/26/1 | 45206 | R: item40074 grade1 목적NPC roll 없음 |
| m1/u738 | 10244/508/1 | 45206 | I: $17270 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u739 | 10244/12573/1 | 45206 | D: item12573 현재 ItemDef 없음 |
| m1/u740 | 10245/6/1 | 81225 | R: item52 grade1 목적NPC roll 없음 |
| m1/u741 | 10245/7/1 | 81225 | R: item40308 grade1 목적NPC roll 없음 |
| m1/u742 | 10245/25/1 | 81225 | R: item40087 grade1 목적NPC roll 없음 |
| m1/u743 | 10245/26/1 | 81225 | R: item40074 grade1 목적NPC roll 없음 |
| m1/u744 | 10245/138/1 | 81225 | R: item148 grade1 목적NPC roll 없음 |
| m1/u745 | 10245/212/1 | 81225 | R: item40197 grade1 목적NPC roll 없음 |
| m1/u746 | 10245/525/1 | 81225 | R: item40215 grade1 목적NPC roll 없음 |
| m1/u747 | 10246/7/1 | 45620 | R: item40308 grade1 목적NPC roll 없음 |
| m1/u748 | 10246/17/1 | 45620 | A: item40013; SQL10953; 50000/1000000; 1..1 |
| m1/u749 | 10246/25/1 | 45620 | R: item40087 grade1 목적NPC roll 없음 |
| m1/u750 | 10246/26/0 | 45620 | R: item140074 grade0 목적NPC roll 없음 |
| m1/u751 | 10246/28/1 | 45620 | R: item40089 grade1 목적NPC roll 없음 |
| m1/u752 | 10246/167/1 | 45620 | R: item20125 grade1 목적NPC roll 없음 |
| m1/u753 | 10246/492/1 | 45620 | R: item40015 grade1 목적NPC roll 없음 |
| m1/u754 | 10246/898/1 | 45620 | I: $17027 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u755 | 10246/2070/1 | 45620 | I: $4349 grade1 후보41352; 고유 신원/차이 대응 미확정 |
| m1/u756 | 10246/12876/1 | 45620 | I: $17822 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u757 | 10247/7/1 | 81221 | R: item40308 grade1 목적NPC roll 없음 |
| m1/u758 | 10247/17/1 | 81221 | R: item40013 grade1 목적NPC roll 없음 |
| m1/u759 | 10247/25/1 | 81221 | R: item40087 grade1 목적NPC roll 없음 |
| m1/u760 | 10247/26/1 | 81221 | R: item40074 grade1 목적NPC roll 없음 |
| m1/u761 | 10247/492/1 | 81221 | R: item40015 grade1 목적NPC roll 없음 |
| m1/u762 | 10247/511/1 | 81221 | I: $17273 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u763 | 10248/7/1 | 46133 | R: item40308 grade1 목적NPC roll 없음 |
| m1/u764 | 10248/25/1 | 46133 | R: item40087 grade1 목적NPC roll 없음 |
| m1/u765 | 10248/26/1 | 46133 | R: item40074 grade1 목적NPC roll 없음 |
| m1/u766 | 10248/28/1 | 46133 | R: item40089 grade1 목적NPC roll 없음 |
| m1/u767 | 10248/360/1 | 46133 | R: item142 grade1 목적NPC roll 없음 |
| m1/u768 | 10248/576/1 | 46133 | I: $1835 grade1 후보40238; 고유 신원/차이 대응 미확정 |
| m1/u769 | 10248/12573/1 | 46133 | D: item12573 현재 ItemDef 없음 |
| m1/u770 | 10249/7/1 | 45621 | R: item40308 grade1 목적NPC roll 없음 |
| m1/u771 | 10249/17/1 | 45621 | A: item40013; SQL10970; 50000/1000000; 1..1 |
| m1/u772 | 10249/25/0 | 45621 | R: item140087 grade0 목적NPC roll 없음 |
| m1/u773 | 10249/25/1 | 45621 | R: item40087 grade1 목적NPC roll 없음 |
| m1/u774 | 10249/28/1 | 45621 | R: item40089 grade1 목적NPC roll 없음 |
| m1/u775 | 10249/167/1 | 45621 | R: item20125 grade1 목적NPC roll 없음 |
| m1/u776 | 10249/492/1 | 45621 | R: item40015 grade1 목적NPC roll 없음 |
| m1/u777 | 10249/896/1 | 45621 | I: $17025 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u778 | 10249/2070/1 | 45621 | I: $4349 grade1 후보41352; 고유 신원/차이 대응 미확정 |
| m1/u779 | 10249/3020/1 | 45621 | R: item264 grade1 목적NPC roll 없음 |
| m1/u780 | 10249/12876/1 | 45621 | I: $17822 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u781 | 10250/509/1 | 45554 | I: $17271 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u782 | 10250/12573/1 | 45554 | D: item12573 현재 ItemDef 없음 |
| m1/u783 | 10251/212/1 | 45549 | R: item40197 grade1 목적NPC roll 없음 |
| m1/u784 | 10251/219/1 | 45549 | R: item40210 grade1 목적NPC roll 없음 |
| m1/u785 | 10251/291/1 | 45549 | R: item20014 grade1 목적NPC roll 없음 |
| m1/u786 | 10251/3020/1 | 45549 | R: item264 grade1 목적NPC roll 없음 |
| m1/u787 | 10252/7/1 | 45619 | R: item40308 grade1 목적NPC roll 없음 |
| m1/u788 | 10252/17/1 | 45619 | R: item40013 grade1 목적NPC roll 없음 |
| m1/u789 | 10252/26/0 | 45619 | R: item140074 grade0 목적NPC roll 없음 |
| m1/u790 | 10252/26/1 | 45619 | R: item40074 grade1 목적NPC roll 없음 |
| m1/u791 | 10252/28/1 | 45619 | R: item40089 grade1 목적NPC roll 없음 |
| m1/u792 | 10252/167/1 | 45619 | R: item20125 grade1 목적NPC roll 없음 |
| m1/u793 | 10252/492/1 | 45619 | R: item40015 grade1 목적NPC roll 없음 |
| m1/u794 | 10252/897/1 | 45619 | I: $17026 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u795 | 10252/2070/1 | 45619 | I: $4349 grade1 후보41352; 고유 신원/차이 대응 미확정 |
| m1/u796 | 10252/12876/1 | 45619 | I: $17822 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u797 | 10253/7/1 | 45049 | R: item40308 grade1 목적NPC roll 없음 |
| m1/u798 | 10253/25/1 | 45049 | R: item40087 grade1 목적NPC roll 없음 |
| m1/u799 | 10253/26/1 | 45049 | R: item40074 grade1 목적NPC roll 없음 |
| m1/u800 | 10253/12573/1 | 45049 | D: item12573 현재 ItemDef 없음 |
| m1/u801 | 10254/17/1 | 45562 | A: item40013; SQL9934; 10000/1000000; 1..1 |
| m1/u802 | 10254/337/1 | 45562 | R: item64 grade1 목적NPC roll 없음 |
| m1/u803 | 10254/510/1 | 45562 | I: $17272 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u804 | 10254/1492/1 | 45562 | I: $17514 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u805 | 10254/1862/1 | 45562 | R: item40166 grade1 목적NPC roll 없음 |
| m1/u806 | 10255/6/1 | 45410 | R: item52 grade1 목적NPC roll 없음 |
| m1/u807 | 10255/7/1 | 45410 | R: item40308 grade1 목적NPC roll 없음 |
| m1/u808 | 10255/17/1 | 45410 | R: item40013 grade1 목적NPC roll 없음 |
| m1/u809 | 10255/25/1 | 45410 | R: item40087 grade1 목적NPC roll 없음 |
| m1/u810 | 10255/26/1 | 45410 | R: item40074 grade1 목적NPC roll 없음 |
| m1/u811 | 10255/492/1 | 45410 | R: item40015 grade1 목적NPC roll 없음 |
| m1/u812 | 10255/899/1 | 45410 | I: $17028 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u813 | 10255/1296/1 | 45410 | I: $3261 grade1 후보40240; 고유 신원/차이 대응 미확정 |
| m1/u814 | 10256/23/1 | 45640 | R: item40100 grade1 목적NPC roll 없음 |
| m1/u815 | 10256/56/1 | 45640 | R: item102 grade1 목적NPC roll 없음 |
| m1/u816 | 10256/162/1 | 45640 | R: item40079 grade1 목적NPC roll 없음 |
| m1/u817 | 10256/299/1 | 45640 | R: item40088 grade1 목적NPC roll 없음 |
| m1/u818 | 10256/900/1 | 45640 | I: $17029 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u819 | 10256/2070/1 | 45640 | I: $4349 grade1 후보41352; 고유 신원/차이 대응 미확정 |
| m1/u820 | 10257/17/1 | 45551 | R: item40013 grade1 목적NPC roll 없음 |
| m1/u821 | 10257/492/1 | 45551 | R: item40015 grade1 목적NPC roll 없음 |
| m1/u822 | 10258/23/1 | 45558 | R: item40100 grade1 목적NPC roll 없음 |
| m1/u823 | 10258/162/1 | 45558 | R: item40079 grade1 목적NPC roll 없음 |
| m1/u824 | 10258/299/1 | 45558 | R: item40088 grade1 목적NPC roll 없음 |
| m1/u825 | 10258/513/1 | 45558 | I: $17275 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u826 | 10258/791/1 | 45558 | I: $2354 grade1 후보51; 고유 신원/차이 대응 미확정 |
| m1/u827 | 10258/1489/1 | 45558 | R: item20060 grade1 목적NPC roll 없음 |
| m1/u828 | 10259/23/1 | 45558 | R: item40100 grade1 목적NPC roll 없음 |
| m1/u829 | 10259/162/1 | 45558 | R: item40079 grade1 목적NPC roll 없음 |
| m1/u830 | 10259/166/1 | 45558 | R: item40318 grade1 목적NPC roll 없음 |
| m1/u831 | 10259/299/1 | 45558 | R: item40088 grade1 목적NPC roll 없음 |
| m1/u832 | 10259/791/1 | 45558 | I: $2354 grade1 후보51; 고유 신원/차이 대응 미확정 |
| m1/u833 | 10259/1489/1 | 45558 | R: item20060 grade1 목적NPC roll 없음 |
| m1/u834 | 12177/26/1 | 45337 | R: item40074 grade1 목적NPC roll 없음 |
| m1/u835 | 12177/93/1 | 45337 | R: item20149 grade1 목적NPC roll 없음 |
| m1/u836 | 12177/12573/1 | 45337 | D: item12573 현재 ItemDef 없음 |
| m1/u837 | 12178/17/1 | 45295 | R: item40013 grade1 목적NPC roll 없음 |
| m1/u838 | 12178/25/1 | 45295 | R: item40087 grade1 목적NPC roll 없음 |
| m1/u839 | 12178/26/1 | 45295 | R: item40074 grade1 목적NPC roll 없음 |
| m1/u840 | 12178/91/1 | 45295 | R: item20154 grade1 목적NPC roll 없음 |
| m1/u841 | 12178/1294/1 | 45295 | R: item40164 grade1 목적NPC roll 없음 |
| m1/u842 | 12178/1861/1 | 45295 | R: item40165 grade1 목적NPC roll 없음 |
| m1/u843 | 12178/1862/1 | 45295 | R: item40166 grade1 목적NPC roll 없음 |
| m1/u844 | 12179/7/1 | 45318 | R: item40308 grade1 목적NPC roll 없음 |
| m1/u845 | 12179/25/1 | 45318 | R: item40087 grade1 목적NPC roll 없음 |
| m1/u846 | 12179/297/1 | 45318 | R: item40016 grade1 목적NPC roll 없음 |
| m1/u847 | 12179/492/1 | 45318 | R: item40015 grade1 목적NPC roll 없음 |
| m1/u848 | 12179/603/1 | 45318 | R: item40184 grade1 목적NPC roll 없음 |
| m1/u849 | 12179/606/1 | 45318 | R: item40193 grade1 목적NPC roll 없음 |
| m1/u850 | 12180/17/1 | 45610 | A: item40013; SQL10741; 300000/1000000; 1..5 |
| m1/u851 | 12180/168/1 | 45610 | I: $15771 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u852 | 12180/169/1 | 45610 | I: $15772 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u853 | 12180/170/1 | 45610 | I: $15773 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u854 | 12180/310/1 | 45610 | A: item20267; SQL10735; 10000/1000000; 1..1 |
| m1/u855 | 12180/337/0 | 45610 | A: item100064; SQL10773; 300000/1000000; 1..1 |
| m1/u856 | 12180/337/1 | 45610 | A: item64; SQL10730; 300000/1000000; 1..1 |
| m1/u857 | 12180/492/1 | 45610 | A: item40015; SQL10743; 300000/1000000; 1..3 |
| m1/u858 | 12180/495/1 | 45610 | A: item40018; SQL10745; 300000/1000000; 1..1 |
| m1/u859 | 12180/504/1 | 45610 | A: item20307; SQL10736; 60000/1000000; 1..1 |
| m1/u860 | 12180/512/1 | 45610 | I: $17274 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u861 | 12180/582/1 | 45610 | I: $1841 grade1 후보40248; 고유 신원/차이 대응 미확정 |
| m1/u862 | 12180/589/1 | 45610 | I: $1848 grade1 후보40250; 고유 신원/차이 대응 미확정 |
| m1/u863 | 12180/597/1 | 45610 | I: $1856 grade1 후보40251; 고유 신원/차이 대응 미확정 |
| m1/u864 | 12180/744/1 | 45610 | A: item20314; SQL10737; 5000/1000000; 1..1 |
| m1/u865 | 12181/58/1 | 45079 | R: item146 grade1 목적NPC roll 없음 |
| m1/u866 | 12181/168/1 | 45079 | I: $15771 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u867 | 12182/171/1 | 45554 | R: item40047 grade1 목적NPC roll 없음 |
| m1/u868 | 12182/580/1 | 45554 | I: $1839 grade1 후보40261; 고유 신원/차이 대응 미확정 |
| m1/u869 | 12183/17/1 | 45264 | R: item40013 grade1 목적NPC roll 없음 |
| m1/u870 | 12183/96/1 | 45264 | R: item20125 grade1 목적NPC roll 없음 |
| m1/u871 | 12183/297/1 | 45264 | R: item40016 grade1 목적NPC roll 없음 |
| m1/u872 | 12183/492/1 | 45264 | X: item40015; SQL6010; chance1500000>1000000, clamp안함 |
| m1/u873 | 12187/7/1 | 45797 | R: item40308 grade1 목적NPC roll 없음 |
| m1/u874 | 12187/17/1 | 45797 | A: item40013; SQL12514; 100000/1000000; 1..1 |
| m1/u875 | 12187/138/1 | 45797 | R: item148 grade1 목적NPC roll 없음 |
| m1/u876 | 12187/169/1 | 45797 | I: $15772 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m1/u877 | 12187/296/1 | 45797 | R: item40014 grade1 목적NPC roll 없음 |
| m1/u878 | 12188/7/1 | 91206 | R: item40308 grade1 목적NPC roll 없음 |
| m1/u879 | 12188/17/1 | 91206 | R: item40013 grade1 목적NPC roll 없음 |
| m1/u880 | 12188/26/1 | 91206 | R: item40074 grade1 목적NPC roll 없음 |
| m1/u881 | 12188/173/1 | 91206 | R: item40055 grade1 목적NPC roll 없음 |
| m1/u882 | 12188/297/1 | 91206 | R: item40016 grade1 목적NPC roll 없음 |
| m1/u883 | 12188/492/1 | 91206 | R: item40015 grade1 목적NPC roll 없음 |
| m1/u884 | 12188/580/1 | 91206 | I: $1839 grade1 후보40261; 고유 신원/차이 대응 미확정 |
| m1/u885 | 12188/1495/1 | 91206 | I: $17517 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m3/u0 | 11/166/1 | 45068 | R: item40318 grade1 목적NPC roll 없음 |
| m3/u1 | 29/166/1 | 45107 | R: item40318 grade1 목적NPC roll 없음 |
| m3/u2 | 29/67/2 | 45107 | R: item200027 grade2 목적NPC roll 없음 |
| m3/u3 | 29/694/1 | 45107 | I: $2030 grade1 후보40581; 고유 신원/차이 대응 미확정 |
| m3/u4 | 276/166/1 | 45122 | R: item40318 grade1 목적NPC roll 없음 |
| m3/u5 | 6/545/1 | 45126 | I: $1798 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m3/u6 | 6/520/1 | 45126 | R: item40175 grade1 목적NPC roll 없음 |
| m3/u7 | 6/166/1 | 45126 | R: item40318 grade1 목적NPC roll 없음 |
| m3/u8 | 30/166/1 | 45161 | R: item40318 grade1 목적NPC roll 없음 |
| m3/u9 | 7/20/1 | 45215 | R: item40008 grade1 목적NPC roll 없음 |
| m3/u10 | 7/19/1 | 45215 | R: item40006 grade1 목적NPC roll 없음 |
| m3/u11 | 7/166/1 | 45215 | R: item40318 grade1 목적NPC roll 없음 |
| m3/u12 | 7/12120/1 | 45215 | I: $16527 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m3/u13 | 17/121/1 | 45136 | I: $311 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m3/u14 | 277/166/1 | 45130 | R: item40318 grade1 목적NPC roll 없음 |
| m3/u15 | 277/90/1 | 45130 | R: item20043 grade1 목적NPC roll 없음 |
| m3/u16 | 278/90/1 | 45131 | R: item20043 grade1 목적NPC roll 없음 |
| m3/u17 | 278/166/1 | 45131 | R: item40318 grade1 목적NPC roll 없음 |
| m3/u18 | 2/97/2 | 45082 | R: item220136 grade2 목적NPC roll 없음 |
| m3/u19 | 2/167/1 | 45082 | R: item20125 grade1 목적NPC roll 없음 |
| m3/u20 | 24/17/1 | 45573 | A: item40013; SQL10033; 150000/1000000; 2..5 |
| m3/u21 | 24/25/0 | 45573 | A: item140087; SQL10074; 100000/1000000; 1..1 |
| m3/u22 | 24/25/1 | 45573 | A: item40087; SQL10048; 150000/1000000; 1..1 |
| m3/u23 | 24/26/0 | 45573 | A: item140074; SQL10073; 300000/1000000; 1..1 |
| m3/u24 | 24/26/1 | 45573 | A: item40074; SQL10047; 500000/1000000; 1..3 |
| m3/u25 | 24/28/1 | 45573 | A: item40089; SQL10049; 150000/1000000; 1..5 |
| m3/u26 | 24/64/1 | 45573 | A: item20288; SQL10026; 5000/1000000; 1..1 |
| m3/u27 | 24/110/1 | 45573 | R: item20077 grade1 목적NPC roll 없음 |
| m3/u28 | 24/166/1 | 45573 | R: item40318 grade1 목적NPC roll 없음 |
| m3/u29 | 24/168/1 | 45573 | I: $15771 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m3/u30 | 24/169/1 | 45573 | I: $15772 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m3/u31 | 24/170/1 | 45573 | I: $15773 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m3/u32 | 24/171/1 | 45573 | A: item40047; SQL10040; 150000/1000000; 1..2 |
| m3/u33 | 24/172/1 | 45573 | A: item40051; SQL10043; 150000/1000000; 1..2 |
| m3/u34 | 24/173/1 | 45573 | A: item40055; SQL10046; 25000/1000000; 1..1 |
| m3/u35 | 24/178/1 | 45573 | I: $15778 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m3/u36 | 24/179/1 | 45573 | I: $15779 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m3/u37 | 24/211/1 | 45573 | R: item40196 grade1 목적NPC roll 없음 |
| m3/u38 | 24/296/1 | 45573 | A: item40014; SQL10034; 150000/1000000; 2..5 |
| m3/u39 | 24/297/1 | 45573 | A: item40016; SQL10036; 150000/1000000; 2..5 |
| m3/u40 | 24/311/1 | 45573 | A: item20254; SQL10023; 20000/1000000; 1..1 |
| m3/u41 | 24/495/1 | 45573 | A: item40018; SQL10037; 150000/1000000; 2..5 |
| m3/u42 | 24/502/1 | 45573 | A: item20306; SQL10027; 50000/1000000; 1..1 |
| m3/u43 | 24/504/1 | 45573 | A: item20307; SQL10028; 50000/1000000; 1..1 |
| m3/u44 | 24/505/1 | 45573 | A: item20312; SQL10030; 25000/1000000; 1..1 |
| m3/u45 | 24/507/1 | 45573 | A: item20316; SQL10031; 25000/1000000; 1..1 |
| m3/u46 | 24/569/1 | 45573 | R: item40319 grade1 목적NPC roll 없음 |
| m3/u47 | 24/585/1 | 45573 | I: $1844 grade1 후보40257; 고유 신원/차이 대응 미확정 |
| m3/u48 | 24/601/1 | 45573 | R: item40176 grade1 목적NPC roll 없음 |
| m3/u49 | 24/605/1 | 45573 | R: item40192 grade1 목적NPC roll 없음 |
| m3/u50 | 24/1096/1 | 45573 | R: item124 grade1 목적NPC roll 없음 |
| m3/u51 | 25/12/1 | 45107 | R: item96 grade1 목적NPC roll 없음 |
| m3/u52 | 25/17/1 | 45107 | A: item40013; SQL4543; 50000/1000000; 1..1 |
| m3/u53 | 25/19/1 | 45107 | A: item40006; SQL4542; 5000/1000000; 1..1 |
| m3/u54 | 25/23/0 | 45107 | A: item140100; SQL4553; 10000/1000000; 1..1 |
| m3/u55 | 25/53/1 | 45107 | R: item40313 grade1 목적NPC roll 없음 |
| m3/u56 | 25/111/0 | 45107 | R: item120056 grade0 목적NPC roll 없음 |
| m3/u57 | 25/166/1 | 45107 | R: item40318 grade1 목적NPC roll 없음 |
| m3/u58 | 25/495/1 | 45107 | A: item40018; SQL4544; 25000/1000000; 1..1 |
| m4/u0 | 29/166/1 | 45107 | R: item40318 grade1 목적NPC roll 없음 |
| m4/u1 | 29/67/2 | 45107 | R: item200027 grade2 목적NPC roll 없음 |
| m4/u2 | 29/694/1 | 45107 | I: $2030 grade1 후보40581; 고유 신원/차이 대응 미확정 |
| m4/u3 | 276/166/1 | 45122 | R: item40318 grade1 목적NPC roll 없음 |
| m4/u4 | 249/16/1 | 45016 | I: $239 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m4/u5 | 190/332/1 | 45058 | R: item40405 grade1 목적NPC roll 없음 |
| m4/u6 | 190/7/1 | 45058 | R: item40308 grade1 목적NPC roll 없음 |
| m4/u7 | 94/166/1 | 45098 | R: item40318 grade1 목적NPC roll 없음 |
| m4/u8 | 95/167/1 | 45127 | R: item20125 grade1 목적NPC roll 없음 |
| m4/u9 | 93/229/1 | 45143 | I: $128 grade1 후보20043; 고유 신원/차이 대응 미확정 |
| m4/u10 | 93/166/1 | 45143 | R: item40318 grade1 목적NPC roll 없음 |
| m4/u11 | 91/229/1 | 45149 | I: $128 grade1 후보20043; 고유 신원/차이 대응 미확정 |
| m4/u12 | 92/495/1 | 45171 | R: item40018 grade1 목적NPC roll 없음 |
| m4/u13 | 92/97/1 | 45171 | R: item20136 grade1 목적NPC roll 없음 |
| m4/u14 | 274/166/1 | 45121 | R: item40318 grade1 목적NPC roll 없음 |
| m4/u15 | 297/569/1 | 45265 | R: item40319 grade1 목적NPC roll 없음 |
| m4/u16 | 297/602/1 | 45265 | R: item40177 grade1 목적NPC roll 없음 |
| m4/u17 | 2/97/2 | 45082 | R: item220136 grade2 목적NPC roll 없음 |
| m4/u18 | 2/167/1 | 45082 | R: item20125 grade1 목적NPC roll 없음 |
| m4/u19 | 5/166/1 | 45126 | R: item40318 grade1 목적NPC roll 없음 |
| m4/u20 | 5/520/1 | 45126 | R: item40175 grade1 목적NPC roll 없음 |
| m4/u21 | 7/19/1 | 45215 | R: item40006 grade1 목적NPC roll 없음 |
| m4/u22 | 7/20/1 | 45215 | R: item40008 grade1 목적NPC roll 없음 |
| m4/u23 | 7/166/1 | 45215 | R: item40318 grade1 목적NPC roll 없음 |
| m4/u24 | 7/12120/1 | 45215 | I: $16527 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m4/u25 | 17/121/1 | 45136 | I: $311 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m4/u26 | 28/25/1 | 45157 | R: item40087 grade1 목적NPC roll 없음 |
| m4/u27 | 28/648/1 | 45157 | I: $1920 grade1 후보40538; 고유 신원/차이 대응 미확정 |
| m4/u28 | 28/649/1 | 45157 | I: $1921 grade1 후보40539; 고유 신원/차이 대응 미확정 |
| m4/u29 | 30/166/1 | 45161 | R: item40318 grade1 목적NPC roll 없음 |
| m4/u30 | 33/23/0 | 45223 | A: item140100; SQL5615; 75000/1000000; 1..1 |
| m4/u31 | 33/25/1 | 45223 | A: item40087; SQL5606; 9000/1000000; 1..1 |
| m4/u32 | 33/26/1 | 45223 | A: item40074; SQL5605; 19000/1000000; 1..1 |
| m4/u33 | 33/575/1 | 45223 | R: item40237 grade1 목적NPC roll 없음 |
| m4/u34 | 33/707/1 | 45223 | I: $2022 grade1 후보40555; 고유 신원/차이 대응 미확정 |
| m4/u35 | 115/126/1 | 45213 | A: item40017; SQL5487; 25000/1000000; 1..1 |
| m4/u36 | 115/171/1 | 45213 | A: item40047; SQL5488; 25000/1000000; 1..1 |
| m4/u37 | 115/172/1 | 45213 | A: item40051; SQL5489; 5000/1000000; 1..1 |
| m4/u38 | 115/492/1 | 45213 | A: item40015; SQL5486; 25000/1000000; 1..1 |
| m4/u39 | 129/23/0 | 45346 | A: item140100; SQL6851; 50000/1000000; 1..1 |
| m4/u40 | 129/25/1 | 45346 | A: item40087; SQL6845; 5000/1000000; 1..1 |
| m4/u41 | 129/26/1 | 45346 | A: item40074; SQL6844; 10000/1000000; 1..1 |
| m4/u42 | 129/172/1 | 45346 | A: item40051; SQL6842; 50000/1000000; 1..1 |
| m4/u43 | 129/173/1 | 45346 | A: item40055; SQL6843; 10000/1000000; 1..1 |
| m4/u44 | 129/291/1 | 45346 | A: item20014; SQL6839; 10000/1000000; 1..1 |
| m4/u45 | 129/492/1 | 45346 | A: item40015; SQL6840; 50000/1000000; 1..1 |
| m4/u46 | 129/608/1 | 45346 | R: item40201 grade1 목적NPC roll 없음 |
| m4/u47 | 147/14/1 | 45019 | A: item40010; SQL3978; 15000/1000000; 1..1 |
| m4/u48 | 147/29/1 | 45019 | I: $61 grade1 후보40743; 고유 신원/차이 대응 미확정 |
| m4/u49 | 147/68/1 | 45019 | I: $93 grade1 후보40744; 고유 신원/차이 대응 미확정 |
| m4/u50 | 147/126/1 | 45019 | A: item40017; SQL3979; 50000/1000000; 1..1 |
| m4/u51 | 147/299/1 | 45019 | A: item40088; SQL3981; 10000/1000000; 1..1 |
| m4/u52 | 147/569/1 | 45019 | R: item40319 grade1 목적NPC roll 없음 |
| m4/u53 | 148/14/1 | 45082 | A: item40010; SQL4371; 50000/1000000; 1..1 |
| m4/u54 | 148/29/1 | 45082 | I: $61 grade1 후보40743; 고유 신원/차이 대응 미확정 |
| m4/u55 | 148/167/1 | 45082 | R: item20125 grade1 목적NPC roll 없음 |
| m4/u56 | 148/569/1 | 45082 | R: item40319 grade1 목적NPC roll 없음 |
| m4/u57 | 149/17/1 | 45149 | A: item40013; SQL4967; 35000/1000000; 1..1 |
| m4/u58 | 149/29/1 | 45149 | I: $61 grade1 후보40743; 고유 신원/차이 대응 미확정 |
| m4/u59 | 149/229/1 | 45149 | I: $128 grade1 후보20043; 고유 신원/차이 대응 미확정 |
| m4/u60 | 149/495/1 | 45149 | A: item40018; SQL4969; 20000/1000000; 1..1 |
| m4/u61 | 149/569/1 | 45149 | R: item40319 grade1 목적NPC roll 없음 |
| m4/u62 | 150/17/1 | 45171 | A: item40013; SQL5182; 25000/1000000; 1..1 |
| m4/u63 | 150/29/1 | 45171 | I: $61 grade1 후보40743; 고유 신원/차이 대응 미확정 |
| m4/u64 | 150/97/1 | 45171 | R: item20136 grade1 목적NPC roll 없음 |
| m4/u65 | 150/174/1 | 45171 | A: item40045; SQL5183; 10000/1000000; 1..1 |
| m4/u66 | 150/495/1 | 45171 | R: item40018 grade1 목적NPC roll 없음 |
| m4/u67 | 150/569/1 | 45171 | R: item40319 grade1 목적NPC roll 없음 |
| m4/u68 | 151/17/1 | 45143 | A: item40013; SQL4896; 10000/1000000; 1..1 |
| m4/u69 | 151/29/1 | 45143 | I: $61 grade1 후보40743; 고유 신원/차이 대응 미확정 |
| m4/u70 | 151/166/1 | 45143 | R: item40318 grade1 목적NPC roll 없음 |
| m4/u71 | 151/175/1 | 45143 | A: item40049; SQL4900; 10000/1000000; 1..1 |
| m4/u72 | 151/229/1 | 45143 | I: $128 grade1 후보20043; 고유 신원/차이 대응 미확정 |
| m4/u73 | 151/495/1 | 45143 | A: item40018; SQL4898; 5000/1000000; 1..1 |
| m4/u74 | 151/569/1 | 45143 | R: item40319 grade1 목적NPC roll 없음 |
| m4/u75 | 152/14/1 | 45098 | A: item40010; SQL4503; 50000/1000000; 1..1 |
| m4/u76 | 152/29/1 | 45098 | I: $61 grade1 후보40743; 고유 신원/차이 대응 미확정 |
| m4/u77 | 152/166/1 | 45098 | R: item40318 grade1 목적NPC roll 없음 |
| m4/u78 | 152/569/1 | 45098 | R: item40319 grade1 목적NPC roll 없음 |
| m4/u79 | 153/14/1 | 45127 | A: item40010; SQL4723; 50000/1000000; 1..1 |
| m4/u80 | 153/17/1 | 45127 | A: item40013; SQL4724; 15000/1000000; 1..1 |
| m4/u81 | 153/131/1 | 45127 | A: item40003; SQL4722; 5000/1000000; 1..1 |
| m4/u82 | 153/167/1 | 45127 | R: item20125 grade1 목적NPC roll 없음 |
| m4/u83 | 153/171/1 | 45127 | R: item40047 grade1 목적NPC roll 없음 |
| m4/u84 | 153/569/1 | 45127 | R: item40319 grade1 목적NPC roll 없음 |
| m4/u85 | 154/3/1 | 45024 | A: item31; SQL4001; 50000/1000000; 1..1 |
| m4/u86 | 154/8/1 | 45024 | R: item140 grade1 목적NPC roll 없음 |
| m4/u87 | 154/16/1 | 45024 | I: $239 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m4/u88 | 154/29/1 | 45024 | I: $61 grade1 후보40743; 고유 신원/차이 대응 미확정 |
| m4/u89 | 154/38/1 | 45024 | R: item138 grade1 목적NPC roll 없음 |
| m4/u90 | 154/45/1 | 45024 | R: item139 grade1 목적NPC roll 없음 |
| m4/u91 | 154/96/1 | 45024 | R: item20125 grade1 목적NPC roll 없음 |
| m4/u92 | 154/98/1 | 45024 | R: item20122 grade1 목적NPC roll 없음 |
| m4/u93 | 154/569/1 | 45024 | R: item40319 grade1 목적NPC roll 없음 |
| m4/u94 | 155/29/1 | 45043 | I: $61 grade1 후보40743; 고유 신원/차이 대응 미확정 |
| m4/u95 | 155/569/1 | 45043 | R: item40319 grade1 목적NPC roll 없음 |
| m4/u96 | 156/20/1 | 45009 | R: item40008 grade1 목적NPC roll 없음 |
| m4/u97 | 156/29/1 | 45009 | I: $61 grade1 후보40743; 고유 신원/차이 대응 미확정 |
| m4/u98 | 156/71/1 | 45009 | R: item91 grade1 목적NPC roll 없음 |
| m4/u99 | 156/177/1 | 45009 | I: $15777 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m4/u100 | 156/569/1 | 45009 | R: item40319 grade1 목적NPC roll 없음 |
| m4/u101 | 162/21/1 | 45126 | A: item40007; SQL4703; 50000/1000000; 1..1 |
| m4/u102 | 162/29/1 | 45126 | I: $61 grade1 후보40743; 고유 신원/차이 대응 미확정 |
| m4/u103 | 162/166/1 | 45126 | R: item40318 grade1 목적NPC roll 없음 |
| m4/u104 | 162/169/1 | 45126 | I: $15772 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m4/u105 | 162/246/1 | 45126 | A: item40496; SQL4715; 50000/1000000; 1..3 |
| m4/u106 | 162/492/1 | 45126 | A: item40015; SQL4704; 10000/1000000; 1..1 |
| m4/u107 | 162/569/1 | 45126 | R: item40319 grade1 목적NPC roll 없음 |
| m4/u108 | 163/14/1 | 45041 | R: item40010 grade1 목적NPC roll 없음 |
| m4/u109 | 163/16/1 | 45041 | I: $239 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m4/u110 | 163/68/1 | 45041 | I: $93 grade1 후보40744; 고유 신원/차이 대응 미확정 |
| m4/u111 | 163/166/1 | 45041 | R: item40318 grade1 목적NPC roll 없음 |
| m4/u112 | 163/246/1 | 45041 | A: item40496; SQL4134; 50000/1000000; 1..3 |
| m4/u113 | 163/333/1 | 45041 | A: item40408; SQL4132; 300000/1000000; 1..3 |
| m4/u114 | 163/569/1 | 45041 | R: item40319 grade1 목적NPC roll 없음 |
| m4/u115 | 164/23/1 | 45065 | R: item40100 grade1 목적NPC roll 없음 |
| m4/u116 | 164/28/1 | 45065 | A: item40089; SQL4233; 50000/1000000; 1..1 |
| m4/u117 | 164/29/1 | 45065 | I: $61 grade1 후보40743; 고유 신원/차이 대응 미확정 |
| m4/u118 | 164/246/1 | 45065 | A: item40496; SQL4242; 50000/1000000; 1..3 |
| m4/u119 | 164/569/1 | 45065 | R: item40319 grade1 목적NPC roll 없음 |
| m4/u120 | 164/576/1 | 45065 | I: $1835 grade1 후보40238; 고유 신원/차이 대응 미확정 |
| m4/u121 | 177/7/1 | 45042 | R: item40308 grade1 목적NPC roll 없음 |
| m4/u122 | 180/7/1 | 45046 | R: item40308 grade1 목적NPC roll 없음 |
| m4/u123 | 280/168/1 | 45173 | I: $15771 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m4/u124 | 323/495/1 | 45140 | A: item40018; SQL4850; 50000/1000000; 1..1 |
| m4/u125 | 750/90/1 | 81066 | R: item20043 grade1 목적NPC roll 없음 |
| m4/u126 | 750/168/1 | 81066 | I: $15771 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m4/u127 | 750/171/1 | 81066 | A: item40047; SQL14548; 10000/1000000; 1..1 |
| m4/u128 | 750/174/1 | 81066 | A: item40045; SQL14546; 10000/1000000; 1..1 |
| m4/u129 | 750/177/1 | 81066 | I: $15777 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m4/u130 | 750/296/1 | 81066 | A: item40014; SQL14543; 50000/1000000; 1..1 |
| m4/u131 | 750/492/1 | 81066 | A: item40015; SQL14544; 50000/1000000; 1..1 |
| m4/u132 | 750/636/1 | 81066 | I: $1908 grade1 후보40565; 고유 신원/차이 대응 미확정 |
| m5/u0 | 2/167/1 | 45082 | R: item20125 grade1 목적NPC roll 없음 |
| m5/u1 | 2/97/2 | 45082 | R: item220136 grade2 목적NPC roll 없음 |
| m5/u2 | 17/121/1 | 45136 | I: $311 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m5/u3 | 17/121/1 | 45136 | I: $311 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m5/u4 | 274/166/1 | 45121 | R: item40318 grade1 목적NPC roll 없음 |
| m5/u5 | 297/569/1 | 45265 | R: item40319 grade1 목적NPC roll 없음 |
| m5/u6 | 297/602/1 | 45265 | R: item40177 grade1 목적NPC roll 없음 |
| m5/u7 | 5/166/1 | 45126 | R: item40318 grade1 목적NPC roll 없음 |
| m5/u8 | 5/520/1 | 45126 | R: item40175 grade1 목적NPC roll 없음 |
| m5/u9 | 7/19/1 | 45215 | R: item40006 grade1 목적NPC roll 없음 |
| m5/u10 | 7/20/1 | 45215 | R: item40008 grade1 목적NPC roll 없음 |
| m5/u11 | 7/166/1 | 45215 | R: item40318 grade1 목적NPC roll 없음 |
| m5/u12 | 7/12120/1 | 45215 | I: $16527 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m5/u13 | 11/166/1 | 45068 | R: item40318 grade1 목적NPC roll 없음 |
| m5/u14 | 31/21/1 | 45184 | S: item40007; SQL5295; 30000/1000000; 1..1 |
| m5/u15 | 31/26/1 | 45184 | R: item40074 grade1 목적NPC roll 없음 |
| m5/u16 | 31/495/1 | 45184 | S: item40018; SQL5298; 40000/1000000; 1..1 |
| m5/u17 | 115/126/1 | 45213 | S: item40017; SQL5487; 25000/1000000; 1..1 |
| m5/u18 | 115/171/1 | 45213 | S: item40047; SQL5488; 25000/1000000; 1..1 |
| m5/u19 | 115/172/1 | 45213 | S: item40051; SQL5489; 5000/1000000; 1..1 |
| m5/u20 | 115/492/1 | 45213 | S: item40015; SQL5486; 25000/1000000; 1..1 |
| m5/u21 | 177/7/1 | 45042 | R: item40308 grade1 목적NPC roll 없음 |
| m5/u22 | 180/7/1 | 45046 | R: item40308 grade1 목적NPC roll 없음 |
| m5/u23 | 190/7/1 | 45058 | R: item40308 grade1 목적NPC roll 없음 |
| m5/u24 | 190/332/1 | 45058 | R: item40405 grade1 목적NPC roll 없음 |
| m5/u25 | 249/16/1 | 45016 | I: $239 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m5/u26 | 252/23/0 | 45264 | S: item140100; SQL6026; 50000/1000000; 1..1 |
| m5/u27 | 252/25/0 | 45264 | S: item140087; SQL6025; 500/1000000; 1..1 |
| m5/u28 | 252/95/0 | 45264 | R: item120101 grade0 목적NPC roll 없음 |
| m5/u29 | 252/166/1 | 45264 | R: item40318 grade1 목적NPC roll 없음 |
| m5/u30 | 252/492/1 | 45264 | X: item40015; SQL6010; chance1500000>1000000, clamp안함 |
| m5/u31 | 252/523/1 | 45264 | R: item40199 grade1 목적NPC roll 없음 |
| m5/u32 | 252/569/1 | 45264 | R: item40319 grade1 목적NPC roll 없음 |
| m5/u33 | 252/586/1 | 45264 | I: $1845 grade1 후보40262; 고유 신원/차이 대응 미확정 |
| m5/u34 | 280/168/1 | 45173 | I: $15771 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m5/u35 | 293/332/1 | 45027 | S: item40405; SQL4035; 50000/1000000; 1..1 |
| m5/u36 | 294/168/1 | 45025 | I: $15771 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m5/u37 | 294/171/1 | 45025 | S: item40047; SQL4023; 10000/1000000; 1..1 |
| m5/u38 | 294/174/1 | 45025 | S: item40045; SQL4021; 10000/1000000; 1..1 |
| m5/u39 | 294/177/1 | 45025 | I: $15777 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m5/u40 | 295/332/1 | 45033 | S: item40405; SQL4054; 50000/1000000; 1..1 |
| m5/u41 | 296/166/1 | 45064 | R: item40318 grade1 목적NPC roll 없음 |
| m5/u42 | 296/171/1 | 45064 | R: item40047 grade1 목적NPC roll 없음 |
| m5/u43 | 296/332/1 | 45064 | S: item40405; SQL4231; 50000/1000000; 1..1 |
| m5/u44 | 296/335/1 | 45064 | I: $1039 grade1 후보40406; 고유 신원/차이 대응 미확정 |
| m5/u45 | 296/492/1 | 45064 | R: item40015 grade1 목적NPC roll 없음 |
| m5/u46 | 296/520/1 | 45064 | R: item40175 grade1 목적NPC roll 없음 |
| m5/u47 | 298/296/1 | 45147 | S: item40014; SQL4933; 100000/1000000; 1..1 |
| m5/u48 | 298/335/1 | 45147 | I: $1039 grade1 후보40406; 고유 신원/차이 대응 미확정 |
| m5/u49 | 323/495/1 | 45140 | S: item40018; SQL4850; 50000/1000000; 1..1 |
| m5/u50 | 324/495/1 | 45092 | S: item40018; SQL4444; 50000/1000000; 1..1 |
| m5/u51 | 325/25/1 | 45420 | S: item40087; SQL7957; 5000/1000000; 1..1 |
| m5/u52 | 325/26/1 | 45420 | S: item40074; SQL7955; 25000/1000000; 1..1 |
| m5/u53 | 325/293/1 | 45420 | S: item20015; SQL7950; 10000/1000000; 1..1 |
| m5/u54 | 325/296/1 | 45420 | S: item40014; SQL7954; 100000/1000000; 1..1 |
| m5/u55 | 325/582/1 | 45420 | I: $1841 grade1 후보40248; 고유 신원/차이 대응 미확정 |
| m5/u56 | 325/589/1 | 45420 | I: $1848 grade1 후보40250; 고유 신원/차이 대응 미확정 |
| m5/u57 | 325/12112/1 | 45420 | I: $16509 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m5/u58 | 331/17/1 | 45144 | S: item40013; SQL4912; 65000/1000000; 1..1 |
| m5/u59 | 331/23/1 | 45144 | S: item40100; SQL4916; 300000/1000000; 1..1 |
| m5/u60 | 331/177/1 | 45144 | I: $15777 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m5/u61 | 331/229/1 | 45144 | I: $128 grade1 후보20043; 고유 신원/차이 대응 미확정 |
| m5/u62 | 331/495/1 | 45144 | S: item40018; SQL4913; 50000/1000000; 1..1 |
| m5/u63 | 333/17/0 | 45321 | I: $234 grade0 후보없음; 고유 신원/차이 대응 미확정 |
| m5/u64 | 333/23/0 | 45321 | S: item140100; SQL6585; 75000/1000000; 1..1 |
| m5/u65 | 333/95/0 | 45321 | R: item120101 grade0 목적NPC roll 없음 |
| m5/u66 | 333/166/1 | 45321 | R: item40318 grade1 목적NPC roll 없음 |
| m5/u67 | 333/169/1 | 45321 | I: $15772 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m5/u68 | 333/172/1 | 45321 | S: item40051; SQL6569; 10000/1000000; 1..1 |
| m5/u69 | 333/175/1 | 45321 | S: item40049; SQL6567; 10000/1000000; 1..1 |
| m5/u70 | 333/178/1 | 45321 | I: $15778 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m5/u71 | 333/495/1 | 45321 | S: item40018; SQL6564; 50000/1000000; 1..1 |
| m5/u72 | 333/575/1 | 45321 | S: item40237; SQL6575; 4500/1000000; 1..1 |
| m5/u73 | 333/580/1 | 45321 | I: $1839 grade1 후보40261; 고유 신원/차이 대응 미확정 |
| m5/u74 | 333/586/1 | 45321 | I: $1845 grade1 후보40262; 고유 신원/차이 대응 미확정 |
| m5/u75 | 591/24/1 | 45206 | S: item40119; SQL5460; 75000/1000000; 1..1 |
| m5/u76 | 591/25/1 | 45206 | R: item40087 grade1 목적NPC roll 없음 |
| m5/u77 | 591/26/1 | 45206 | R: item40074 grade1 목적NPC roll 없음 |
| m5/u78 | 591/162/1 | 45206 | S: item40079; SQL5458; 100000/1000000; 1..1 |
| m5/u79 | 591/299/1 | 45206 | S: item40088; SQL5459; 75000/1000000; 1..1 |
| m5/u80 | 591/409/1 | 45206 | R: item40393 grade1 목적NPC roll 없음 |
| m5/u81 | 591/492/1 | 45206 | S: item40015; SQL5457; 75000/1000000; 1..1 |
| m5/u82 | 879/7/1 | 45317 | R: item40308 grade1 목적NPC roll 없음 |
| m5/u83 | 879/14/1 | 45317 | R: item40010 grade1 목적NPC roll 없음 |
| m5/u84 | 879/15/1 | 45317 | R: item40011 grade1 목적NPC roll 없음 |
| m5/u85 | 879/17/1 | 45317 | R: item40013 grade1 목적NPC roll 없음 |
| m5/u86 | 879/38/1 | 45317 | R: item138 grade1 목적NPC roll 없음 |
| m5/u87 | 879/58/1 | 45317 | R: item146 grade1 목적NPC roll 없음 |
| m5/u88 | 879/90/1 | 45317 | R: item20043 grade1 목적NPC roll 없음 |
| m5/u89 | 879/99/1 | 45317 | R: item20147 grade1 목적NPC roll 없음 |
| m5/u90 | 879/130/1 | 45317 | R: item40012 grade1 목적NPC roll 없음 |
| m5/u91 | 879/495/1 | 45317 | R: item40018 grade1 목적NPC roll 없음 |
| m5/u92 | 879/12110/1 | 45317 | I: $16487 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m5/u93 | 880/14/1 | 45324 | S: item40010; SQL6618; 300000/1000000; 1..1 |
| m5/u94 | 880/15/1 | 45324 | S: item40011; SQL6619; 50000/1000000; 1..1 |
| m5/u95 | 880/17/1 | 45324 | S: item40013; SQL6621; 50000/1000000; 1..1 |
| m5/u96 | 880/90/1 | 45324 | R: item20043 grade1 목적NPC roll 없음 |
| m5/u97 | 880/96/1 | 45324 | R: item20125 grade1 목적NPC roll 없음 |
| m5/u98 | 880/130/1 | 45324 | S: item40012; SQL6620; 50000/1000000; 1..1 |
| m5/u99 | 880/141/1 | 45324 | R: item32 grade1 목적NPC roll 없음 |
| m5/u100 | 880/235/1 | 45324 | R: item37 grade1 목적NPC roll 없음 |
| m5/u101 | 880/495/1 | 45324 | S: item40018; SQL6622; 10000/1000000; 1..1 |
| m5/u102 | 880/12110/1 | 45324 | I: $16487 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m5/u103 | 881/13/1 | 81080 | R: item143 grade1 목적NPC roll 없음 |
| m5/u104 | 881/14/1 | 81080 | S: item40010; SQL14620; 50000/1000000; 1..1 |
| m5/u105 | 881/15/1 | 81080 | S: item40011; SQL14621; 50000/1000000; 1..1 |
| m5/u106 | 881/17/1 | 81080 | R: item40013 grade1 목적NPC roll 없음 |
| m5/u107 | 881/90/1 | 81080 | R: item20043 grade1 목적NPC roll 없음 |
| m5/u108 | 881/98/1 | 81080 | R: item20122 grade1 목적NPC roll 없음 |
| m5/u109 | 881/130/1 | 81080 | S: item40012; SQL14622; 50000/1000000; 1..1 |
| m5/u110 | 881/138/1 | 81080 | R: item148 grade1 목적NPC roll 없음 |
| m5/u111 | 881/495/1 | 81080 | R: item40018 grade1 목적NPC roll 없음 |
| m5/u112 | 881/12110/1 | 81080 | I: $16487 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m5/u113 | 882/14/1 | 45276 | S: item40010; SQL6158; 50000/1000000; 1..1 |
| m5/u114 | 882/15/1 | 45276 | S: item40011; SQL6159; 50000/1000000; 1..1 |
| m5/u115 | 882/17/1 | 45276 | S: item40013; SQL6160; 50000/1000000; 1..1 |
| m5/u116 | 882/90/1 | 45276 | R: item20043 grade1 목적NPC roll 없음 |
| m5/u117 | 882/99/1 | 45276 | R: item20147 grade1 목적NPC roll 없음 |
| m5/u118 | 882/130/1 | 45276 | R: item40012 grade1 목적NPC roll 없음 |
| m5/u119 | 882/244/1 | 45276 | I: $759 grade1 후보173; 고유 신원/차이 대응 미확정 |
| m5/u120 | 882/260/1 | 45276 | R: item20191 grade1 목적NPC roll 없음 |
| m5/u121 | 882/319/1 | 45276 | R: item20002 grade1 목적NPC roll 없음 |
| m5/u122 | 882/388/1 | 45276 | R: item169 grade1 목적NPC roll 없음 |
| m5/u123 | 882/495/1 | 45276 | R: item40018 grade1 목적NPC roll 없음 |
| m5/u124 | 882/12110/1 | 45276 | I: $16487 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m5/u125 | 883/2/1 | 45370 | R: item41 grade1 목적NPC roll 없음 |
| m5/u126 | 883/14/1 | 45370 | R: item40010 grade1 목적NPC roll 없음 |
| m5/u127 | 883/15/1 | 45370 | R: item40011 grade1 목적NPC roll 없음 |
| m5/u128 | 883/17/1 | 45370 | R: item40013 grade1 목적NPC roll 없음 |
| m5/u129 | 883/23/0 | 45370 | S: item140100; SQL7202; 300000/1000000; 1..1 |
| m5/u130 | 883/95/1 | 45370 | R: item20101 grade1 목적NPC roll 없음 |
| m5/u131 | 883/109/1 | 45370 | R: item20063 grade1 목적NPC roll 없음 |
| m5/u132 | 883/130/1 | 45370 | R: item40012 grade1 목적NPC roll 없음 |
| m5/u133 | 883/169/1 | 45370 | I: $15772 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m5/u134 | 883/170/1 | 45370 | I: $15773 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m5/u135 | 883/172/1 | 45370 | S: item40051; SQL7198; 50000/1000000; 1..1 |
| m5/u136 | 883/173/1 | 45370 | R: item40055 grade1 목적NPC roll 없음 |
| m5/u137 | 883/175/1 | 45370 | R: item40049 grade1 목적NPC roll 없음 |
| m5/u138 | 883/176/1 | 45370 | S: item40053; SQL7199; 50000/1000000; 1..1 |
| m5/u139 | 883/178/1 | 45370 | I: $15778 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m5/u140 | 883/179/1 | 45370 | I: $15779 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m5/u141 | 883/229/1 | 45370 | I: $128 grade1 후보20043; 고유 신원/차이 대응 미확정 |
| m5/u142 | 883/358/1 | 45370 | R: item29 grade1 목적NPC roll 없음 |
| m5/u143 | 883/495/1 | 45370 | R: item40018 grade1 목적NPC roll 없음 |
| m6/u0 | 156/29/1 | 45009 | I: $61 grade1 후보40743; 고유 신원/차이 대응 미확정 |
| m6/u1 | 156/71/1 | 45009 | R: item91 grade1 목적NPC roll 없음 |
| m6/u2 | 156/20/1 | 45009 | R: item40008 grade1 목적NPC roll 없음 |
| m6/u3 | 156/177/1 | 45009 | I: $15777 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m6/u4 | 156/569/1 | 45009 | R: item40319 grade1 목적NPC roll 없음 |
| m6/u5 | 2/97/2 | 45082 | R: item220136 grade2 목적NPC roll 없음 |
| m6/u6 | 2/167/1 | 45082 | R: item20125 grade1 목적NPC roll 없음 |
| m6/u7 | 6/166/1 | 45126 | R: item40318 grade1 목적NPC roll 없음 |
| m6/u8 | 6/520/1 | 45126 | R: item40175 grade1 목적NPC roll 없음 |
| m6/u9 | 6/545/1 | 45126 | I: $1798 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m6/u10 | 7/19/1 | 45215 | R: item40006 grade1 목적NPC roll 없음 |
| m6/u11 | 7/20/1 | 45215 | R: item40008 grade1 목적NPC roll 없음 |
| m6/u12 | 7/166/1 | 45215 | R: item40318 grade1 목적NPC roll 없음 |
| m6/u13 | 7/12120/1 | 45215 | I: $16527 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m6/u14 | 11/166/1 | 45068 | R: item40318 grade1 목적NPC roll 없음 |
| m6/u15 | 17/121/1 | 45136 | I: $311 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m6/u16 | 28/25/1 | 45157 | R: item40087 grade1 목적NPC roll 없음 |
| m6/u17 | 28/648/1 | 45157 | I: $1920 grade1 후보40538; 고유 신원/차이 대응 미확정 |
| m6/u18 | 28/649/1 | 45157 | I: $1921 grade1 후보40539; 고유 신원/차이 대응 미확정 |
| m6/u19 | 29/67/2 | 45107 | R: item200027 grade2 목적NPC roll 없음 |
| m6/u20 | 29/166/1 | 45107 | R: item40318 grade1 목적NPC roll 없음 |
| m6/u21 | 29/694/1 | 45107 | I: $2030 grade1 후보40581; 고유 신원/차이 대응 미확정 |
| m6/u22 | 30/166/1 | 45161 | R: item40318 grade1 목적NPC roll 없음 |
| m6/u23 | 31/21/1 | 45184 | A: item40007; SQL5295; 30000/1000000; 1..1 |
| m6/u24 | 31/26/1 | 45184 | R: item40074 grade1 목적NPC roll 없음 |
| m6/u25 | 31/495/1 | 45184 | A: item40018; SQL5298; 40000/1000000; 1..1 |
| m6/u26 | 33/23/0 | 45223 | A: item140100; SQL5615; 75000/1000000; 1..1 |
| m6/u27 | 33/25/1 | 45223 | A: item40087; SQL5606; 9000/1000000; 1..1 |
| m6/u28 | 33/26/1 | 45223 | A: item40074; SQL5605; 19000/1000000; 1..1 |
| m6/u29 | 33/575/1 | 45223 | R: item40237 grade1 목적NPC roll 없음 |
| m6/u30 | 33/707/1 | 45223 | I: $2022 grade1 후보40555; 고유 신원/차이 대응 미확정 |
| m6/u31 | 34/19/1 | 45473 | A: item40006; SQL8531; 85000/1000000; 1..1 |
| m6/u32 | 34/20/1 | 45473 | A: item40008; SQL8532; 85000/1000000; 1..1 |
| m6/u33 | 34/23/0 | 45473 | A: item140100; SQL8555; 300000/1000000; 1..1 |
| m6/u34 | 34/24/1 | 45473 | A: item40119; SQL8540; 300000/1000000; 1..1 |
| m6/u35 | 34/25/0 | 45473 | A: item140087; SQL8554; 5000/1000000; 1..1 |
| m6/u36 | 34/26/0 | 45473 | A: item140074; SQL8553; 25000/1000000; 1..1 |
| m6/u37 | 34/65/1 | 45473 | R: item20281 grade1 목적NPC roll 없음 |
| m6/u38 | 34/166/1 | 45473 | R: item40318 grade1 목적NPC roll 없음 |
| m6/u39 | 34/171/1 | 45473 | A: item40047; SQL8536; 85000/1000000; 1..1 |
| m6/u40 | 34/172/1 | 45473 | A: item40051; SQL8537; 22000/1000000; 1..1 |
| m6/u41 | 34/173/1 | 45473 | A: item40055; SQL8538; 22000/1000000; 1..1 |
| m6/u42 | 34/309/1 | 45473 | A: item20266; SQL8529; 5000/1000000; 1..1 |
| m6/u43 | 34/492/1 | 45473 | A: item40015; SQL8534; 300000/1000000; 1..1 |
| m6/u44 | 34/582/1 | 45473 | I: $1841 grade1 후보40248; 고유 신원/차이 대응 미확정 |
| m6/u45 | 34/589/1 | 45473 | I: $1848 grade1 후보40250; 고유 신원/차이 대응 미확정 |
| m6/u46 | 35/19/1 | 45488 | A: item40006; SQL8708; 85000/1000000; 1..1 |
| m6/u47 | 35/20/1 | 45488 | A: item40008; SQL8709; 85000/1000000; 1..1 |
| m6/u48 | 35/23/0 | 45488 | A: item140100; SQL8726; 300000/1000000; 1..1 |
| m6/u49 | 35/24/1 | 45488 | A: item40119; SQL8718; 300000/1000000; 1..1 |
| m6/u50 | 35/25/0 | 45488 | A: item140087; SQL8725; 5000/1000000; 1..1 |
| m6/u51 | 35/26/0 | 45488 | A: item140074; SQL8724; 20000/1000000; 1..1 |
| m6/u52 | 35/65/1 | 45488 | A: item20281; SQL8706; 500/1000000; 1..1 |
| m6/u53 | 35/109/1 | 45488 | R: item20063 grade1 목적NPC roll 없음 |
| m6/u54 | 35/128/1 | 45488 | R: item20205 grade1 목적NPC roll 없음 |
| m6/u55 | 35/166/1 | 45488 | R: item40318 grade1 목적NPC roll 없음 |
| m6/u56 | 35/174/1 | 45488 | A: item40045; SQL8713; 85000/1000000; 1..1 |
| m6/u57 | 35/175/1 | 45488 | A: item40049; SQL8714; 25000/1000000; 1..1 |
| m6/u58 | 35/176/1 | 45488 | A: item40053; SQL8715; 25000/1000000; 1..1 |
| m6/u59 | 35/194/1 | 45488 | R: item40170 grade1 목적NPC roll 없음 |
| m6/u60 | 35/306/1 | 45488 | A: item20264; SQL8705; 6500/1000000; 1..1 |
| m6/u61 | 35/492/1 | 45488 | A: item40015; SQL8711; 300000/1000000; 1..1 |
| m6/u62 | 35/585/1 | 45488 | I: $1844 grade1 후보40257; 고유 신원/차이 대응 미확정 |
| m6/u63 | 35/587/1 | 45488 | I: $1846 grade1 후보40249; 고유 신원/차이 대응 미확정 |
| m6/u64 | 35/788/1 | 45488 | R: item20225 grade1 목적NPC roll 없음 |
| m6/u65 | 36/19/1 | 45497 | A: item40006; SQL8819; 85000/1000000; 1..1 |
| m6/u66 | 36/20/1 | 45497 | A: item40008; SQL8820; 85000/1000000; 1..1 |
| m6/u67 | 36/23/0 | 45497 | A: item140100; SQL8842; 8500/1000000; 1..1 |
| m6/u68 | 36/24/1 | 45497 | A: item40119; SQL8829; 300000/1000000; 1..1 |
| m6/u69 | 36/25/0 | 45497 | A: item140087; SQL8841; 4000/1000000; 1..1 |
| m6/u70 | 36/26/0 | 45497 | A: item140074; SQL8840; 25000/1000000; 1..1 |
| m6/u71 | 36/64/1 | 45497 | A: item20288; SQL8818; 1000/1000000; 1..1 |
| m6/u72 | 36/109/1 | 45497 | R: item20063 grade1 목적NPC roll 없음 |
| m6/u73 | 36/128/1 | 45497 | R: item20205 grade1 목적NPC roll 없음 |
| m6/u74 | 36/166/1 | 45497 | R: item40318 grade1 목적NPC roll 없음 |
| m6/u75 | 36/177/1 | 45497 | I: $15777 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m6/u76 | 36/178/1 | 45497 | I: $15778 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m6/u77 | 36/179/1 | 45497 | I: $15779 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m6/u78 | 36/306/1 | 45497 | R: item20264 grade1 목적NPC roll 없음 |
| m6/u79 | 36/492/1 | 45497 | A: item40015; SQL8822; 300000/1000000; 1..1 |
| m6/u80 | 36/576/1 | 45497 | I: $1835 grade1 후보40238; 고유 신원/차이 대응 미확정 |
| m6/u81 | 36/588/1 | 45497 | I: $1847 grade1 후보40254; 고유 신원/차이 대응 미확정 |
| m6/u82 | 37/19/1 | 45464 | A: item40006; SQL8374; 85000/1000000; 1..1 |
| m6/u83 | 37/20/1 | 45464 | A: item40008; SQL8375; 85000/1000000; 1..1 |
| m6/u84 | 37/23/0 | 45464 | A: item140100; SQL8399; 300000/1000000; 1..1 |
| m6/u85 | 37/24/1 | 45464 | A: item40119; SQL8383; 300000/1000000; 1..1 |
| m6/u86 | 37/25/0 | 45464 | A: item140087; SQL8398; 7000/1000000; 1..1 |
| m6/u87 | 37/26/0 | 45464 | A: item140074; SQL8397; 20000/1000000; 1..1 |
| m6/u88 | 37/128/1 | 45464 | R: item20205 grade1 목적NPC roll 없음 |
| m6/u89 | 37/166/1 | 45464 | R: item40318 grade1 목적NPC roll 없음 |
| m6/u90 | 37/168/1 | 45464 | I: $15771 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m6/u91 | 37/169/1 | 45464 | I: $15772 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m6/u92 | 37/170/1 | 45464 | I: $15773 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m6/u93 | 37/306/1 | 45464 | R: item20264 grade1 목적NPC roll 없음 |
| m6/u94 | 37/492/1 | 45464 | A: item40015; SQL8377; 300000/1000000; 1..1 |
| m6/u95 | 37/586/1 | 45464 | I: $1845 grade1 후보40262; 고유 신원/차이 대응 미확정 |
| m6/u96 | 63/17/1 | 45601 | A: item40013; SQL10506; 300000/1000000; 1..5 |
| m6/u97 | 63/25/0 | 45601 | A: item140087; SQL10544; 300000/1000000; 1..1 |
| m6/u98 | 63/25/1 | 45601 | A: item40087; SQL10516; 300000/1000000; 1..2 |
| m6/u99 | 63/26/0 | 45601 | A: item140074; SQL10543; 300000/1000000; 1..1 |
| m6/u100 | 63/26/1 | 45601 | A: item40074; SQL10515; 300000/1000000; 1..5 |
| m6/u101 | 63/28/1 | 45601 | A: item40089; SQL10517; 300000/1000000; 1..1 |
| m6/u102 | 63/65/1 | 45601 | A: item20281; SQL10498; 6500/1000000; 1..1 |
| m6/u103 | 63/142/2 | 45601 | R: item200002 grade2 목적NPC roll 없음 |
| m6/u104 | 63/166/1 | 45601 | R: item40318 grade1 목적NPC roll 없음 |
| m6/u105 | 63/168/1 | 45601 | I: $15771 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m6/u106 | 63/169/1 | 45601 | I: $15772 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m6/u107 | 63/170/1 | 45601 | I: $15773 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m6/u108 | 63/204/1 | 45601 | R: item40186 grade1 목적NPC roll 없음 |
| m6/u109 | 63/296/1 | 45601 | A: item40014; SQL10507; 300000/1000000; 1..5 |
| m6/u110 | 63/297/1 | 45601 | A: item40016; SQL10509; 300000/1000000; 1..3 |
| m6/u111 | 63/306/1 | 45601 | A: item20264; SQL10496; 35000/1000000; 1..1 |
| m6/u112 | 63/495/1 | 45601 | A: item40018; SQL10510; 300000/1000000; 1..1 |
| m6/u113 | 63/503/1 | 45601 | A: item20308; SQL10503; 50000/1000000; 1..1 |
| m6/u114 | 63/504/1 | 45601 | A: item20307; SQL10502; 50000/1000000; 1..1 |
| m6/u115 | 63/506/1 | 45601 | A: item20319; SQL10505; 35000/1000000; 1..1 |
| m6/u116 | 63/507/1 | 45601 | A: item20316; SQL10504; 35000/1000000; 1..1 |
| m6/u117 | 63/556/1 | 45601 | R: item20166 grade1 목적NPC roll 없음 |
| m6/u118 | 63/557/1 | 45601 | A: item20100; SQL10492; 15000/1000000; 1..1 |
| m6/u119 | 63/558/1 | 45601 | R: item20198 grade1 목적NPC roll 없음 |
| m6/u120 | 63/559/1 | 45601 | A: item20010; SQL10490; 15000/1000000; 1..1 |
| m6/u121 | 63/1491/1 | 45601 | I: $17513 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m6/u122 | 63/1863/1 | 45601 | R: item41147 grade1 목적NPC roll 없음 |
| m6/u123 | 64/166/1 | 45083 | R: item40318 grade1 목적NPC roll 없음 |
| m6/u124 | 64/280/1 | 45083 | A: item20187; SQL4379; 100/1000000; 1..1 |
| m6/u125 | 115/126/1 | 45213 | A: item40017; SQL5487; 25000/1000000; 1..1 |
| m6/u126 | 115/171/1 | 45213 | A: item40047; SQL5488; 25000/1000000; 1..1 |
| m6/u127 | 115/172/1 | 45213 | A: item40051; SQL5489; 5000/1000000; 1..1 |
| m6/u128 | 115/492/1 | 45213 | A: item40015; SQL5486; 25000/1000000; 1..1 |
| m6/u129 | 147/14/1 | 45019 | A: item40010; SQL3978; 15000/1000000; 1..1 |
| m6/u130 | 147/29/1 | 45019 | I: $61 grade1 후보40743; 고유 신원/차이 대응 미확정 |
| m6/u131 | 147/68/1 | 45019 | I: $93 grade1 후보40744; 고유 신원/차이 대응 미확정 |
| m6/u132 | 147/126/1 | 45019 | A: item40017; SQL3979; 50000/1000000; 1..1 |
| m6/u133 | 147/299/1 | 45019 | A: item40088; SQL3981; 10000/1000000; 1..1 |
| m6/u134 | 147/569/1 | 45019 | R: item40319 grade1 목적NPC roll 없음 |
| m6/u135 | 148/14/1 | 45082 | A: item40010; SQL4371; 50000/1000000; 1..1 |
| m6/u136 | 148/29/1 | 45082 | I: $61 grade1 후보40743; 고유 신원/차이 대응 미확정 |
| m6/u137 | 148/167/1 | 45082 | R: item20125 grade1 목적NPC roll 없음 |
| m6/u138 | 148/569/1 | 45082 | R: item40319 grade1 목적NPC roll 없음 |
| m6/u139 | 149/17/1 | 45149 | A: item40013; SQL4967; 35000/1000000; 1..1 |
| m6/u140 | 149/29/1 | 45149 | I: $61 grade1 후보40743; 고유 신원/차이 대응 미확정 |
| m6/u141 | 149/229/1 | 45149 | I: $128 grade1 후보20043; 고유 신원/차이 대응 미확정 |
| m6/u142 | 149/495/1 | 45149 | A: item40018; SQL4969; 20000/1000000; 1..1 |
| m6/u143 | 149/569/1 | 45149 | R: item40319 grade1 목적NPC roll 없음 |
| m6/u144 | 150/17/1 | 45171 | A: item40013; SQL5182; 25000/1000000; 1..1 |
| m6/u145 | 150/29/1 | 45171 | I: $61 grade1 후보40743; 고유 신원/차이 대응 미확정 |
| m6/u146 | 150/97/1 | 45171 | R: item20136 grade1 목적NPC roll 없음 |
| m6/u147 | 150/174/1 | 45171 | A: item40045; SQL5183; 10000/1000000; 1..1 |
| m6/u148 | 150/495/1 | 45171 | R: item40018 grade1 목적NPC roll 없음 |
| m6/u149 | 150/569/1 | 45171 | R: item40319 grade1 목적NPC roll 없음 |
| m6/u150 | 151/17/1 | 45143 | A: item40013; SQL4896; 10000/1000000; 1..1 |
| m6/u151 | 151/29/1 | 45143 | I: $61 grade1 후보40743; 고유 신원/차이 대응 미확정 |
| m6/u152 | 151/166/1 | 45143 | R: item40318 grade1 목적NPC roll 없음 |
| m6/u153 | 151/175/1 | 45143 | A: item40049; SQL4900; 10000/1000000; 1..1 |
| m6/u154 | 151/229/1 | 45143 | I: $128 grade1 후보20043; 고유 신원/차이 대응 미확정 |
| m6/u155 | 151/495/1 | 45143 | A: item40018; SQL4898; 5000/1000000; 1..1 |
| m6/u156 | 151/569/1 | 45143 | R: item40319 grade1 목적NPC roll 없음 |
| m6/u157 | 152/14/1 | 45098 | A: item40010; SQL4503; 50000/1000000; 1..1 |
| m6/u158 | 152/29/1 | 45098 | I: $61 grade1 후보40743; 고유 신원/차이 대응 미확정 |
| m6/u159 | 152/166/1 | 45098 | R: item40318 grade1 목적NPC roll 없음 |
| m6/u160 | 152/569/1 | 45098 | R: item40319 grade1 목적NPC roll 없음 |
| m6/u161 | 153/14/1 | 45127 | A: item40010; SQL4723; 50000/1000000; 1..1 |
| m6/u162 | 153/17/1 | 45127 | A: item40013; SQL4724; 15000/1000000; 1..1 |
| m6/u163 | 153/131/1 | 45127 | A: item40003; SQL4722; 5000/1000000; 1..1 |
| m6/u164 | 153/167/1 | 45127 | R: item20125 grade1 목적NPC roll 없음 |
| m6/u165 | 153/171/1 | 45127 | R: item40047 grade1 목적NPC roll 없음 |
| m6/u166 | 153/569/1 | 45127 | R: item40319 grade1 목적NPC roll 없음 |
| m6/u167 | 154/3/1 | 45024 | A: item31; SQL4001; 50000/1000000; 1..1 |
| m6/u168 | 154/8/1 | 45024 | R: item140 grade1 목적NPC roll 없음 |
| m6/u169 | 154/16/1 | 45024 | I: $239 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m6/u170 | 154/29/1 | 45024 | I: $61 grade1 후보40743; 고유 신원/차이 대응 미확정 |
| m6/u171 | 154/38/1 | 45024 | R: item138 grade1 목적NPC roll 없음 |
| m6/u172 | 154/45/1 | 45024 | R: item139 grade1 목적NPC roll 없음 |
| m6/u173 | 154/96/1 | 45024 | R: item20125 grade1 목적NPC roll 없음 |
| m6/u174 | 154/98/1 | 45024 | R: item20122 grade1 목적NPC roll 없음 |
| m6/u175 | 154/569/1 | 45024 | R: item40319 grade1 목적NPC roll 없음 |
| m6/u176 | 164/23/1 | 45065 | R: item40100 grade1 목적NPC roll 없음 |
| m6/u177 | 164/28/1 | 45065 | A: item40089; SQL4233; 50000/1000000; 1..1 |
| m6/u178 | 164/29/1 | 45065 | I: $61 grade1 후보40743; 고유 신원/차이 대응 미확정 |
| m6/u179 | 164/246/1 | 45065 | A: item40496; SQL4242; 50000/1000000; 1..3 |
| m6/u180 | 164/569/1 | 45065 | R: item40319 grade1 목적NPC roll 없음 |
| m6/u181 | 164/576/1 | 45065 | I: $1835 grade1 후보40238; 고유 신원/차이 대응 미확정 |
| m6/u182 | 182/23/0 | 45241 | A: item140100; SQL5770; 50000/1000000; 1..1 |
| m6/u183 | 182/166/1 | 45241 | R: item40318 grade1 목적NPC roll 없음 |
| m6/u184 | 182/174/1 | 45241 | A: item40045; SQL5759; 50000/1000000; 1..1 |
| m6/u185 | 182/175/1 | 45241 | A: item40049; SQL5760; 10000/1000000; 1..1 |
| m6/u186 | 182/176/1 | 45241 | A: item40053; SQL5761; 10000/1000000; 1..1 |
| m6/u187 | 182/296/1 | 45241 | A: item40014; SQL5758; 50000/1000000; 1..1 |
| m6/u188 | 182/569/1 | 45241 | R: item40319 grade1 목적NPC roll 없음 |
| m6/u189 | 212/23/0 | 45298 | A: item140100; SQL6418; 75000/1000000; 1..1 |
| m6/u190 | 212/25/1 | 45298 | A: item40087; SQL6407; 9000/1000000; 1..1 |
| m6/u191 | 212/26/1 | 45298 | A: item40074; SQL6406; 20000/1000000; 1..1 |
| m6/u192 | 212/175/1 | 45298 | R: item40049 grade1 목적NPC roll 없음 |
| m6/u193 | 212/293/1 | 45298 | A: item20015; SQL6400; 10000/1000000; 1..1 |
| m6/u194 | 212/296/1 | 45298 | A: item40014; SQL6403; 50000/1000000; 1..1 |
| m6/u195 | 212/492/1 | 45298 | A: item40015; SQL6404; 50000/1000000; 1..1 |
| m6/u196 | 212/1294/1 | 45298 | R: item40164 grade1 목적NPC roll 없음 |
| m6/u197 | 276/166/1 | 45122 | R: item40318 grade1 목적NPC roll 없음 |
| m6/u198 | 277/90/1 | 45130 | R: item20043 grade1 목적NPC roll 없음 |
| m6/u199 | 277/166/1 | 45130 | R: item40318 grade1 목적NPC roll 없음 |
| m6/u200 | 278/90/1 | 45131 | R: item20043 grade1 목적NPC roll 없음 |
| m6/u201 | 278/166/1 | 45131 | R: item40318 grade1 목적NPC roll 없음 |
| m6/u202 | 454/17/1 | 45614 | A: item40013; SQL10805; 300000/1000000; 1..5 |
| m6/u203 | 454/25/0 | 45614 | A: item140087; SQL10840; 300000/1000000; 1..1 |
| m6/u204 | 454/25/1 | 45614 | A: item40087; SQL10817; 150000/1000000; 1..1 |
| m6/u205 | 454/26/0 | 45614 | A: item140074; SQL10839; 300000/1000000; 1..3 |
| m6/u206 | 454/26/1 | 45614 | A: item40074; SQL10816; 300000/1000000; 1..1 |
| m6/u207 | 454/166/1 | 45614 | R: item40318 grade1 목적NPC roll 없음 |
| m6/u208 | 454/167/1 | 45614 | R: item20125 grade1 목적NPC roll 없음 |
| m6/u209 | 454/171/1 | 45614 | A: item40047; SQL10811; 300000/1000000; 1..1 |
| m6/u210 | 454/172/1 | 45614 | A: item40051; SQL10813; 300000/1000000; 1..1 |
| m6/u211 | 454/173/1 | 45614 | A: item40055; SQL10815; 300000/1000000; 1..1 |
| m6/u212 | 454/174/1 | 45614 | A: item40045; SQL10810; 300000/1000000; 1..1 |
| m6/u213 | 454/175/1 | 45614 | A: item40049; SQL10812; 300000/1000000; 1..1 |
| m6/u214 | 454/176/1 | 45614 | A: item40053; SQL10814; 300000/1000000; 1..1 |
| m6/u215 | 454/293/1 | 45614 | A: item20015; SQL10795; 300000/1000000; 1..1 |
| m6/u216 | 454/296/1 | 45614 | A: item40014; SQL10806; 300000/1000000; 1..5 |
| m6/u217 | 454/297/1 | 45614 | A: item40016; SQL10808; 300000/1000000; 1..1 |
| m6/u218 | 454/308/1 | 45614 | A: item20268; SQL10801; 30000/1000000; 1..1 |
| m6/u219 | 454/492/1 | 45614 | A: item40015; SQL10807; 300000/1000000; 1..1 |
| m6/u220 | 454/495/1 | 45614 | A: item40018; SQL10809; 300000/1000000; 1..3 |
| m6/u221 | 454/502/1 | 45614 | A: item20306; SQL10803; 35000/1000000; 1..1 |
| m6/u222 | 454/505/1 | 45614 | A: item20312; SQL10804; 15000/1000000; 1..1 |
| m6/u223 | 454/569/1 | 45614 | R: item40319 grade1 목적NPC roll 없음 |
| m6/u224 | 454/583/1 | 45614 | I: $1842 grade1 후보40242; 고유 신원/차이 대응 미확정 |
| m6/u225 | 454/1490/1 | 45614 | I: $17512 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m6/u226 | 10129/19/1 | 45456 | A: item40006; SQL8269; 25000/1000000; 1..1 |
| m6/u227 | 10129/20/1 | 45456 | A: item40008; SQL8270; 25000/1000000; 1..1 |
| m6/u228 | 10129/23/0 | 45456 | A: item140100; SQL8291; 300000/1000000; 1..1 |
| m6/u229 | 10129/24/1 | 45456 | A: item40119; SQL8275; 300000/1000000; 1..1 |
| m6/u230 | 10129/25/0 | 45456 | A: item140087; SQL8290; 5000/1000000; 1..1 |
| m6/u231 | 10129/26/0 | 45456 | A: item140074; SQL8289; 25000/1000000; 1..1 |
| m6/u232 | 10129/128/1 | 45456 | R: item20205 grade1 목적NPC roll 없음 |
| m6/u233 | 10129/168/1 | 45456 | I: $15771 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m6/u234 | 10129/169/1 | 45456 | I: $15772 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m6/u235 | 10129/170/1 | 45456 | I: $15773 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| m6/u236 | 10129/206/1 | 45456 | R: item40188 grade1 목적NPC roll 없음 |
| m6/u237 | 10129/306/1 | 45456 | A: item20264; SQL8263; 2500/1000000; 1..1 |
| m6/u238 | 10129/492/1 | 45456 | A: item40015; SQL8272; 300000/1000000; 1..1 |
| m6/u239 | 10129/586/1 | 45456 | I: $1845 grade1 후보40262; 고유 신원/차이 대응 미확정 |
| c0/u0 | 245/120/1 | 45008 | R: item20213 grade1 목적NPC roll 없음 |
| c0/u1 | 245/90/1 | 45008 | R: item20043 grade1 목적NPC roll 없음 |
| c0/u2 | 245/38/1 | 45008 | R: item138 grade1 목적NPC roll 없음 |
| c0/u3 | 0/71/1 | 45009 | R: item91 grade1 목적NPC roll 없음 |
| c0/u4 | 249/16/1 | 45016 | I: $239 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| c0/u5 | 8/8/1 | 45024 | R: item140 grade1 목적NPC roll 없음 |
| c0/u6 | 8/38/1 | 45024 | R: item138 grade1 목적NPC roll 없음 |
| c0/u7 | 8/45/1 | 45024 | R: item139 grade1 목적NPC roll 없음 |
| c0/u8 | 177/7/1 | 45042 | R: item40308 grade1 목적NPC roll 없음 |
| c0/u9 | 180/7/1 | 45046 | R: item40308 grade1 목적NPC roll 없음 |
| c0/u10 | 11/166/1 | 45068 | R: item40318 grade1 목적NPC roll 없음 |
| c0/u11 | 11/9/1 | 45068 | A: item40057; SQL4266; 300000/1000000; 1..1 |
| c0/u12 | 459/168/1 | 45079 | I: $15771 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| c0/u13 | 459/177/1 | 45079 | I: $15777 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| c0/u14 | 459/174/1 | 45079 | A: item40045; SQL4338; 10000/1000000; 1..1 |
| c0/u15 | 459/171/1 | 45079 | A: item40047; SQL4340; 15000/1000000; 1..1 |
| c0/u16 | 459/166/1 | 45079 | R: item40318 grade1 목적NPC roll 없음 |
| c0/u17 | 2/167/1 | 45082 | R: item20125 grade1 목적NPC roll 없음 |
| c0/u18 | 2/97/2 | 45082 | R: item220136 grade2 목적NPC roll 없음 |
| c0/u19 | 324/495/1 | 45092 | A: item40018; SQL4444; 50000/1000000; 1..1 |
| c0/u20 | 29/166/1 | 45107 | R: item40318 grade1 목적NPC roll 없음 |
| c0/u21 | 29/495/1 | 45107 | A: item40018; SQL4544; 25000/1000000; 1..1 |
| c0/u22 | 29/67/2 | 45107 | R: item200027 grade2 목적NPC roll 없음 |
| c0/u23 | 29/647/1 | 45107 | A: item40605; SQL4550; 25000/1000000; 1..1 |
| c0/u24 | 29/694/1 | 45107 | I: $2030 grade1 후보40581; 고유 신원/차이 대응 미확정 |
| c0/u25 | 5/176/1 | 45126 | A: item40053; SQL4707; 1000/1000000; 1..1 |
| c0/u26 | 5/520/1 | 45126 | R: item40175 grade1 목적NPC roll 없음 |
| c0/u27 | 5/21/1 | 45126 | A: item40007; SQL4703; 50000/1000000; 1..1 |
| c0/u28 | 5/166/1 | 45126 | R: item40318 grade1 목적NPC roll 없음 |
| c0/u29 | 17/21/1 | 45136 | A: item40007; SQL4807; 20000/1000000; 1..1 |
| c0/u30 | 17/495/1 | 45136 | A: item40018; SQL4809; 30000/1000000; 1..1 |
| c0/u31 | 17/121/1 | 45136 | I: $311 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| c0/u32 | 323/495/1 | 45140 | A: item40018; SQL4850; 50000/1000000; 1..1 |
| c0/u33 | 28/25/1 | 45157 | R: item40087 grade1 목적NPC roll 없음 |
| c0/u34 | 28/649/1 | 45157 | I: $1921 grade1 후보40539; 고유 신원/차이 대응 미확정 |
| c0/u35 | 28/648/1 | 45157 | I: $1920 grade1 후보40538; 고유 신원/차이 대응 미확정 |
| c0/u36 | 280/168/1 | 45173 | I: $15771 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| c0/u37 | 31/26/1 | 45184 | R: item40074 grade1 목적NPC roll 없음 |
| c0/u38 | 31/21/1 | 45184 | A: item40007; SQL5295; 30000/1000000; 1..1 |
| c0/u39 | 31/495/1 | 45184 | A: item40018; SQL5298; 40000/1000000; 1..1 |
| c0/u40 | 7/20/1 | 45215 | R: item40008 grade1 목적NPC roll 없음 |
| c0/u41 | 7/19/1 | 45215 | R: item40006 grade1 목적NPC roll 없음 |
| c0/u42 | 7/166/1 | 45215 | R: item40318 grade1 목적NPC roll 없음 |
| c0/u43 | 7/12120/1 | 45215 | I: $16527 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| p/u0 | 279/94/2 | 45280 | R: item220115 grade2 목적NPC roll 없음 |
| p/u1 | 279/291/1 | 45280 | S: item20014; SQL6205; 10000/1000000; 1..1 |
| p/u2 | 281/492/1 | 45289 | S: item40015; SQL6314; 50000/1000000; 1..1 |
| p/u3 | 284/65/1 | 45393 | S: item20281; SQL7580; 500/1000000; 1..1 |
| p/u4 | 284/210/1 | 45393 | S: item40195; SQL7588; 10000/1000000; 1..1 |
| p/u5 | 284/214/1 | 45393 | R: item40202 grade1 목적NPC roll 없음 |
| p/u6 | 284/216/1 | 45393 | S: item40204; SQL7590; 2500/1000000; 1..1 |
| p/u7 | 284/492/1 | 45393 | S: item40015; SQL7581; 150000/1000000; 1..1 |
| p/u8 | 284/512/1 | 45393 | I: $17274 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| p/u9 | 284/575/1 | 45393 | S: item40237; SQL7592; 4000/1000000; 1..1 |
| p/u10 | 284/588/1 | 45393 | I: $1847 grade1 후보40254; 고유 신원/차이 대응 미확정 |
| p/u11 | 284/1296/1 | 45393 | I: $3261 grade1 후보40240; 고유 신원/차이 대응 미확정 |
| p/u12 | 284/1490/1 | 45393 | I: $17512 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| p/u13 | 284/12111/1 | 45393 | I: $16488 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| p/u14 | 285/64/1 | 45451 | S: item20288; SQL8176; 300/1000000; 1..1 |
| p/u15 | 285/210/1 | 45451 | S: item40195; SQL8184; 5000/1000000; 1..1 |
| p/u16 | 285/223/1 | 45451 | S: item40214; SQL8188; 5000/1000000; 1..1 |
| p/u17 | 285/492/1 | 45451 | S: item40015; SQL8177; 150000/1000000; 1..1 |
| p/u18 | 285/588/1 | 45451 | I: $1847 grade1 후보40254; 고유 신원/차이 대응 미확정 |
| p/u19 | 285/12121/1 | 45451 | I: $16528 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| p/u20 | 287/513/1 | 45373 | I: $17275 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| p/u21 | 288/11/0 | 45270 | R: item100172 grade0 목적NPC roll 없음 |
| p/u22 | 288/17/1 | 45270 | S: item40013; SQL6070; 50000/1000000; 1..1 |
| p/u23 | 288/90/0 | 45270 | R: item120043 grade0 목적NPC roll 없음 |
| p/u24 | 288/117/0 | 45270 | R: item120242 grade0 목적NPC roll 없음 |
| p/u25 | 288/166/1 | 45270 | R: item40318 grade1 목적NPC roll 없음 |
| p/u26 | 288/202/1 | 45270 | R: item40181 grade1 목적NPC roll 없음 |
| p/u27 | 288/307/1 | 45270 | R: item20256 grade1 목적NPC roll 없음 |
| p/u28 | 288/495/1 | 45270 | S: item40018; SQL6071; 50000/1000000; 1..1 |
| p/u29 | 288/509/1 | 45270 | I: $17271 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| p/u30 | 289/17/1 | 45286 | S: item40013; SQL6285; 300000/1000000; 1..1 |
| p/u31 | 289/166/1 | 45286 | R: item40318 grade1 목적NPC roll 없음 |
| p/u32 | 289/495/1 | 45286 | S: item40018; SQL6286; 50000/1000000; 1..1 |
| p/u33 | 289/510/1 | 45286 | I: $17272 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| p/u34 | 289/1863/1 | 45286 | R: item41147 grade1 목적NPC roll 없음 |
| p/u35 | 290/17/1 | 45269 | S: item40013; SQL6057; 50000/1000000; 1..1 |
| p/u36 | 290/46/0 | 45269 | S: item100098; SQL6064; 15000/1000000; 1..1 |
| p/u37 | 290/117/0 | 45269 | R: item120242 grade0 목적NPC roll 없음 |
| p/u38 | 290/166/1 | 45269 | R: item40318 grade1 목적NPC roll 없음 |
| p/u39 | 290/495/1 | 45269 | S: item40018; SQL6058; 50000/1000000; 1..1 |
| p/u40 | 327/2/1 | 45682 | R: item41 grade1 목적NPC roll 없음 |
| p/u41 | 327/17/1 | 45682 | R: item40013 grade1 목적NPC roll 없음 |
| p/u42 | 327/19/1 | 45682 | R: item40006 grade1 목적NPC roll 없음 |
| p/u43 | 327/20/1 | 45682 | R: item40008 grade1 목적NPC roll 없음 |
| p/u44 | 327/25/1 | 45682 | R: item40087 grade1 목적NPC roll 없음 |
| p/u45 | 327/25/2 | 45682 | R: item240087 grade2 목적NPC roll 없음 |
| p/u46 | 327/26/1 | 45682 | R: item40074 grade1 목적NPC roll 없음 |
| p/u47 | 327/26/2 | 45682 | R: item240074 grade2 목적NPC roll 없음 |
| p/u48 | 327/64/1 | 45682 | S: item20288; SQL11802; 300000/1000000; 1..1 |
| p/u49 | 327/65/1 | 45682 | S: item20281; SQL11801; 300000/1000000; 1..1 |
| p/u50 | 327/78/0 | 45682 | S: item100057; SQL11837; 300000/1000000; 1..1 |
| p/u51 | 327/78/1 | 45682 | R: item57 grade1 목적NPC roll 없음 |
| p/u52 | 327/91/1 | 45682 | R: item20154 grade1 목적NPC roll 없음 |
| p/u53 | 327/110/1 | 45682 | R: item20077 grade1 목적NPC roll 없음 |
| p/u54 | 327/129/1 | 45682 | R: item20182 grade1 목적NPC roll 없음 |
| p/u55 | 327/166/1 | 45682 | R: item40318 grade1 목적NPC roll 없음 |
| p/u56 | 327/168/1 | 45682 | I: $15771 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| p/u57 | 327/169/1 | 45682 | I: $15772 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| p/u58 | 327/170/1 | 45682 | I: $15773 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| p/u59 | 327/171/1 | 45682 | S: item40047; SQL11804; 300000/1000000; 1..1 |
| p/u60 | 327/172/1 | 45682 | S: item40051; SQL11806; 300000/1000000; 1..1 |
| p/u61 | 327/173/1 | 45682 | S: item40055; SQL11808; 300000/1000000; 1..1 |
| p/u62 | 327/223/1 | 45682 | S: item40214; SQL11818; 300000/1000000; 1..1 |
| p/u63 | 327/296/1 | 45682 | R: item40014 grade1 목적NPC roll 없음 |
| p/u64 | 327/297/1 | 45682 | R: item40016 grade1 목적NPC roll 없음 |
| p/u65 | 327/308/1 | 45682 | R: item20268 grade1 목적NPC roll 없음 |
| p/u66 | 327/310/1 | 45682 | R: item20267 grade1 목적NPC roll 없음 |
| p/u67 | 327/404/1 | 45682 | S: item20146; SQL11800; 6000/1000000; 1..1 |
| p/u68 | 327/408/1 | 45682 | I: $150 grade1 후보40396; 고유 신원/차이 대응 미확정 |
| p/u69 | 327/492/1 | 45682 | R: item40015 grade1 목적NPC roll 없음 |
| p/u70 | 327/495/1 | 45682 | R: item40018 grade1 목적NPC roll 없음 |
| p/u71 | 327/502/1 | 45682 | R: item20306 grade1 목적NPC roll 없음 |
| p/u72 | 327/503/1 | 45682 | R: item20308 grade1 목적NPC roll 없음 |
| p/u73 | 327/504/1 | 45682 | R: item20307 grade1 목적NPC roll 없음 |
| p/u74 | 327/505/1 | 45682 | R: item20312 grade1 목적NPC roll 없음 |
| p/u75 | 327/506/1 | 45682 | R: item20319 grade1 목적NPC roll 없음 |
| p/u76 | 327/507/1 | 45682 | R: item20316 grade1 목적NPC roll 없음 |
| p/u77 | 327/1492/1 | 45682 | I: $17514 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| p/u78 | 332/6/0 | 45649 | R: item100052 grade0 목적NPC roll 없음 |
| p/u79 | 332/17/1 | 45649 | S: item40013; SQL11291; 300000/1000000; 2..5 |
| p/u80 | 332/19/1 | 45649 | S: item40006; SQL11289; 300000/1000000; 1..1 |
| p/u81 | 332/28/0 | 45649 | I: $257 grade0 후보140089; 고유 신원/차이 대응 미확정 |
| p/u82 | 332/65/1 | 45649 | S: item20281; SQL11283; 500/1000000; 1..1 |
| p/u83 | 332/78/1 | 45649 | S: item57; SQL11269; 14000/1000000; 1..1 |
| p/u84 | 332/167/1 | 45649 | S: item20125; SQL11276; 300000/1000000; 1..1 |
| p/u85 | 332/169/1 | 45649 | I: $15772 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| p/u86 | 332/170/1 | 45649 | I: $15773 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| p/u87 | 332/176/1 | 45649 | S: item40053; SQL11299; 100000/1000000; 1..1 |
| p/u88 | 332/222/1 | 45649 | R: item40213 grade1 목적NPC roll 없음 |
| p/u89 | 332/280/1 | 45649 | S: item20187; SQL11279; 85000/1000000; 1..1 |
| p/u90 | 332/306/1 | 45649 | S: item20264; SQL11281; 20000/1000000; 1..1 |
| p/u91 | 332/309/1 | 45649 | S: item20266; SQL11282; 17500/1000000; 1..1 |
| p/u92 | 332/492/1 | 45649 | S: item40015; SQL11293; 300000/1000000; 2..5 |
| p/u93 | 332/495/1 | 45649 | S: item40018; SQL11295; 300000/1000000; 1..3 |
| p/u94 | 332/503/1 | 45649 | S: item20308; SQL11286; 300000/1000000; 1..1 |
| p/u95 | 332/504/1 | 45649 | S: item20307; SQL11285; 300000/1000000; 1..1 |
| p/u96 | 332/525/1 | 45649 | S: item40215; SQL11312; 70000/1000000; 1..1 |
| p/u97 | 332/568/1 | 45649 | R: item190 grade1 목적NPC roll 없음 |
| p/u98 | 332/592/1 | 45649 | I: $1851 grade1 후보40258; 고유 신원/차이 대응 미확정 |
| p/u99 | 332/1095/1 | 45649 | I: $2991 grade1 후보119; 고유 신원/차이 대응 미확정 |
| p/u100 | 332/1496/1 | 45649 | I: $17518 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| p/u101 | 332/2072/1 | 45649 | R: item205 grade1 목적NPC roll 없음 |
| p/u102 | 460/17/1 | 45141 | S: item40013; SQL4858; 50000/1000000; 1..1 |
| p/u103 | 460/229/1 | 45141 | I: $128 grade1 후보20043; 고유 신원/차이 대응 미확정 |
| p/u104 | 460/492/1 | 45141 | S: item40015; SQL4860; 25000/1000000; 1..1 |
| p/u105 | 460/495/1 | 45141 | S: item40018; SQL4862; 25000/1000000; 1..1 |
| p/u106 | 469/14/0 | 45162 | I: $237 grade0 후보없음; 고유 신원/차이 대응 미확정 |
| p/u107 | 469/14/1 | 45162 | S: item40010; SQL5078; 300000/1000000; 1..1 |
| p/u108 | 469/492/1 | 45162 | S: item40015; SQL5079; 50000/1000000; 1..1 |
| p/u109 | 469/495/1 | 45162 | R: item40018 grade1 목적NPC roll 없음 |
| p/u110 | 469/504/1 | 45162 | R: item20307 grade1 목적NPC roll 없음 |
| p/u111 | 469/521/1 | 45162 | R: item40183 grade1 목적NPC roll 없음 |
| p/u112 | 473/13/1 | 45322 | R: item143 grade1 목적NPC roll 없음 |
| p/u113 | 473/14/1 | 45322 | S: item40010; SQL6588; 300000/1000000; 1..1 |
| p/u114 | 473/209/1 | 45322 | R: item40194 grade1 목적NPC roll 없음 |
| p/u115 | 473/296/1 | 45322 | R: item40014 grade1 목적NPC roll 없음 |
| p/u116 | 473/495/1 | 45322 | S: item40018; SQL6593; 50000/1000000; 1..1 |
| p/u117 | 473/2069/1 | 45322 | I: $4348 grade1 후보41351; 고유 신원/차이 대응 미확정 |
| p/u118 | 534/17/1 | 45203 | S: item40013; SQL5439; 50000/1000000; 1..1 |
| p/u119 | 534/172/1 | 45203 | S: item40051; SQL5444; 10000/1000000; 1..1 |
| p/u120 | 534/175/1 | 45203 | S: item40049; SQL5442; 10000/1000000; 1..1 |
| p/u121 | 534/382/1 | 45203 | I: $1203 grade1 후보40899; 고유 신원/차이 대응 미확정 |
| p/u122 | 534/409/1 | 45203 | R: item40393 grade1 목적NPC roll 없음 |
| p/u123 | 534/495/1 | 45203 | S: item40018; SQL5440; 50000/1000000; 1..1 |
| p/u124 | 534/525/1 | 45203 | S: item40215; SQL5448; 2500/1000000; 1..1 |
| p/u125 | 534/583/1 | 45203 | I: $1842 grade1 후보40242; 고유 신원/차이 대응 미확정 |
| p/u126 | 534/586/1 | 45203 | I: $1845 grade1 후보40262; 고유 신원/차이 대응 미확정 |
| p/u127 | 534/1294/1 | 45203 | R: item40164 grade1 목적NPC roll 없음 |
| p/u128 | 579/23/1 | 45221 | R: item40100 grade1 목적NPC roll 없음 |
| p/u129 | 579/492/1 | 45221 | S: item40015; SQL5574; 50000/1000000; 1..1 |
| p/u130 | 579/512/1 | 45221 | I: $17274 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| p/u131 | 579/595/1 | 45221 | I: $1854 grade1 후보40263; 고유 신원/차이 대응 미확정 |
| p/u132 | 579/787/1 | 45221 | I: $2350 grade1 후보56; 고유 신원/차이 대응 미확정 |
| p/u133 | 579/1495/1 | 45221 | I: $17517 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| p/u134 | 579/2069/1 | 45221 | I: $4348 grade1 후보41351; 고유 신원/차이 대응 미확정 |
| p/u135 | 579/2072/1 | 45221 | R: item205 grade1 목적NPC roll 없음 |
| p/u136 | 580/14/0 | 45198 | I: $237 grade0 후보없음; 고유 신원/차이 대응 미확정 |
| p/u137 | 580/14/1 | 45198 | R: item40010 grade1 목적NPC roll 없음 |
| p/u138 | 580/15/0 | 45198 | R: item140011 grade0 목적NPC roll 없음 |
| p/u139 | 580/17/1 | 45198 | S: item40013; SQL5428; 45000/1000000; 1..1 |
| p/u140 | 580/23/1 | 45198 | R: item40100 grade1 목적NPC roll 없음 |
| p/u141 | 580/130/0 | 45198 | R: item140012 grade0 목적NPC roll 없음 |
| p/u142 | 580/234/1 | 45198 | S: item20114; SQL5425; 40000/1000000; 1..1 |
| p/u143 | 580/495/1 | 45198 | S: item40018; SQL5431; 50000/1000000; 1..1 |
| p/u144 | 580/508/1 | 45198 | I: $17270 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| p/u145 | 580/511/1 | 45198 | I: $17273 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| p/u146 | 580/547/1 | 45198 | R: item20175 grade1 목적NPC roll 없음 |
| p/u147 | 580/568/1 | 45198 | R: item190 grade1 목적NPC roll 없음 |
| p/u148 | 580/590/1 | 45198 | I: $1849 grade1 후보40244; 고유 신원/차이 대응 미확정 |
| p/u149 | 580/605/1 | 45198 | R: item40192 grade1 목적NPC roll 없음 |
| p/u150 | 580/788/1 | 45198 | R: item20225 grade1 목적NPC roll 없음 |
| p/u151 | 580/2069/1 | 45198 | I: $4348 grade1 후보41351; 고유 신원/차이 대응 미확정 |
| p/u152 | 581/14/0 | 45174 | I: $237 grade0 후보없음; 고유 신원/차이 대응 미확정 |
| p/u153 | 581/14/1 | 45174 | R: item40010 grade1 목적NPC roll 없음 |
| p/u154 | 581/15/0 | 45174 | R: item140011 grade0 목적NPC roll 없음 |
| p/u155 | 581/23/1 | 45174 | R: item40100 grade1 목적NPC roll 없음 |
| p/u156 | 581/130/0 | 45174 | R: item140012 grade0 목적NPC roll 없음 |
| p/u157 | 581/234/1 | 45174 | S: item20114; SQL5215; 40000/1000000; 1..1 |
| p/u158 | 581/492/1 | 45174 | R: item40015 grade1 목적NPC roll 없음 |
| p/u159 | 581/508/1 | 45174 | I: $17270 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| p/u160 | 581/511/1 | 45174 | I: $17273 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| p/u161 | 581/547/1 | 45174 | R: item20175 grade1 목적NPC roll 없음 |
| p/u162 | 581/590/1 | 45174 | I: $1849 grade1 후보40244; 고유 신원/차이 대응 미확정 |
| p/u163 | 581/604/1 | 45174 | R: item40185 grade1 목적NPC roll 없음 |
| p/u164 | 581/788/1 | 45174 | R: item20225 grade1 목적NPC roll 없음 |
| p/u165 | 581/2069/1 | 45174 | I: $4348 grade1 후보41351; 고유 신원/차이 대응 미확정 |
| p/u166 | 586/56/1 | 45365 | R: item102 grade1 목적NPC roll 없음 |
| p/u167 | 586/409/1 | 45365 | R: item40393 grade1 목적NPC roll 없음 |
| p/u168 | 586/545/1 | 45365 | I: $1798 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| p/u169 | 586/1296/1 | 45365 | I: $3261 grade1 후보40240; 고유 신원/차이 대응 미확정 |
| p/u170 | 587/3/1 | 45284 | S: item31; SQL6258; 50000/1000000; 1..1 |
| p/u171 | 587/17/1 | 45284 | S: item40013; SQL6265; 50000/1000000; 1..1 |
| p/u172 | 587/409/1 | 45284 | R: item40393 grade1 목적NPC roll 없음 |
| p/u173 | 587/495/1 | 45284 | S: item40018; SQL6267; 50000/1000000; 1..1 |
| p/u174 | 587/508/1 | 45284 | I: $17270 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| p/u175 | 587/790/1 | 45284 | I: $2353 grade1 후보50; 고유 신원/차이 대응 미확정 |
| p/u176 | 587/927/1 | 45284 | I: $2592 grade1 후보40524; 고유 신원/차이 대응 미확정 |
| p/u177 | 588/2/0 | 45515 | R: item100041 grade0 목적NPC roll 없음 |
| p/u178 | 588/25/0 | 45515 | R: item140087 grade0 목적NPC roll 없음 |
| p/u179 | 588/25/1 | 45515 | R: item40087 grade1 목적NPC roll 없음 |
| p/u180 | 588/91/1 | 45515 | R: item20154 grade1 목적NPC roll 없음 |
| p/u181 | 588/167/1 | 45515 | R: item20125 grade1 목적NPC roll 없음 |
| p/u182 | 588/169/1 | 45515 | I: $15772 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| p/u183 | 588/170/1 | 45515 | I: $15773 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| p/u184 | 588/172/1 | 45515 | R: item40051 grade1 목적NPC roll 없음 |
| p/u185 | 588/173/1 | 45515 | R: item40055 grade1 목적NPC roll 없음 |
| p/u186 | 588/175/1 | 45515 | S: item40049; SQL9090; 50000/1000000; 1..1 |
| p/u187 | 588/176/1 | 45515 | R: item40053 grade1 목적NPC roll 없음 |
| p/u188 | 588/178/1 | 45515 | I: $15778 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| p/u189 | 588/179/1 | 45515 | I: $15779 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| p/u190 | 588/492/1 | 45515 | S: item40015; SQL9088; 150000/1000000; 1..1 |
| p/u191 | 588/525/1 | 45515 | S: item40215; SQL9100; 7500/1000000; 1..1 |
| p/u192 | 588/583/1 | 45515 | I: $1842 grade1 후보40242; 고유 신원/차이 대응 미확정 |
| p/u193 | 588/789/1 | 45515 | R: item184 grade1 목적NPC roll 없음 |
| p/u194 | 588/790/1 | 45515 | I: $2353 grade1 후보50; 고유 신원/차이 대응 미확정 |
| p/u195 | 588/1296/1 | 45515 | I: $3261 grade1 후보40240; 고유 신원/차이 대응 미확정 |
| p/u196 | 589/17/1 | 45341 | S: item40013; SQL6788; 50000/1000000; 1..1 |
| p/u197 | 589/222/1 | 45341 | R: item40213 grade1 목적NPC roll 없음 |
| p/u198 | 589/337/1 | 45341 | R: item64 grade1 목적NPC roll 없음 |
| p/u199 | 589/409/1 | 45341 | R: item40393 grade1 목적NPC roll 없음 |
| p/u200 | 589/495/1 | 45341 | S: item40018; SQL6791; 50000/1000000; 1..1 |
| p/u201 | 589/583/1 | 45341 | I: $1842 grade1 후보40242; 고유 신원/차이 대응 미확정 |
| p/u202 | 589/927/1 | 45341 | I: $2592 grade1 후보40524; 고유 신원/차이 대응 미확정 |
| p/u203 | 589/1294/1 | 45341 | R: item40164 grade1 목적NPC roll 없음 |
| p/u204 | 589/1496/1 | 45341 | I: $17518 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| p/u205 | 590/17/1 | 45617 | S: item40013; SQL10875; 300000/1000000; 2..5 |
| p/u206 | 590/28/0 | 45617 | I: $257 grade0 후보140089; 고유 신원/차이 대응 미확정 |
| p/u207 | 590/65/1 | 45617 | S: item20281; SQL10867; 15000/1000000; 1..1 |
| p/u208 | 590/78/1 | 45617 | R: item57 grade1 목적NPC roll 없음 |
| p/u209 | 590/110/1 | 45617 | R: item20077 grade1 목적NPC roll 없음 |
| p/u210 | 590/167/1 | 45617 | R: item20125 grade1 목적NPC roll 없음 |
| p/u211 | 590/176/1 | 45617 | S: item40053; SQL10885; 200000/1000000; 1..1 |
| p/u212 | 590/220/1 | 45617 | R: item40211 grade1 목적NPC roll 없음 |
| p/u213 | 590/222/1 | 45617 | R: item40213 grade1 목적NPC roll 없음 |
| p/u214 | 590/225/1 | 45617 | S: item40219; SQL10904; 4500/1000000; 1..1 |
| p/u215 | 590/306/1 | 45617 | R: item20264 grade1 목적NPC roll 없음 |
| p/u216 | 590/307/1 | 45617 | S: item20256; SQL10866; 15000/1000000; 1..1 |
| p/u217 | 590/492/1 | 45617 | S: item40015; SQL10877; 300000/1000000; 2..5 |
| p/u218 | 590/495/1 | 45617 | S: item40018; SQL10879; 300000/1000000; 2..5 |
| p/u219 | 590/503/0 | 45617 | I: $15765 grade0 후보없음; 고유 신원/차이 대응 미확정 |
| p/u220 | 590/504/1 | 45617 | S: item20307; SQL10870; 50000/1000000; 1..1 |
| p/u221 | 590/525/1 | 45617 | S: item40215; SQL10903; 85000/1000000; 1..1 |
| p/u222 | 590/585/1 | 45617 | I: $1844 grade1 후보40257; 고유 신원/차이 대응 미확정 |
| p/u223 | 590/789/1 | 45617 | R: item184 grade1 목적NPC roll 없음 |
| p/u224 | 590/790/1 | 45617 | I: $2353 grade1 후보50; 고유 신원/차이 대응 미확정 |
| p/u225 | 590/1495/1 | 45617 | I: $17517 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| p/u226 | 591/25/1 | 45206 | R: item40087 grade1 목적NPC roll 없음 |
| p/u227 | 591/26/1 | 45206 | R: item40074 grade1 목적NPC roll 없음 |
| p/u228 | 591/409/1 | 45206 | R: item40393 grade1 목적NPC roll 없음 |
| p/u229 | 591/492/1 | 45206 | S: item40015; SQL5457; 75000/1000000; 1..1 |
| p/u230 | 592/220/1 | 45263 | S: item40211; SQL6005; 10000/1000000; 1..1 |
| p/u231 | 593/90/1 | 45291 | R: item20043 grade1 목적NPC roll 없음 |
| p/u232 | 593/409/1 | 45291 | R: item40393 grade1 목적NPC roll 없음 |
| p/u233 | 593/509/1 | 45291 | I: $17271 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| p/u234 | 593/789/1 | 45291 | R: item184 grade1 목적NPC roll 없음 |
| p/u235 | 595/17/1 | 45257 | S: item40013; SQL5940; 50000/1000000; 1..1 |
| p/u236 | 595/409/1 | 45257 | R: item40393 grade1 목적NPC roll 없음 |
| p/u237 | 595/495/1 | 45257 | S: item40018; SQL5941; 50000/1000000; 1..1 |
| p/u238 | 596/17/1 | 45359 | S: item40013; SQL6998; 50000/1000000; 1..1 |
| p/u239 | 596/21/1 | 45359 | S: item40007; SQL6997; 50000/1000000; 1..1 |
| p/u240 | 596/409/1 | 45359 | R: item40393 grade1 목적NPC roll 없음 |
| p/u241 | 596/429/1 | 45359 | I: $1608 grade1 후보40460; 고유 신원/차이 대응 미확정 |
| p/u242 | 596/495/1 | 45359 | S: item40018; SQL7001; 50000/1000000; 1..1 |
| p/u243 | 703/214/1 | 45224 | R: item40202 grade1 목적NPC roll 없음 |
| p/u244 | 703/232/1 | 45224 | R: item125 grade1 목적NPC roll 없음 |
| p/u245 | 703/492/1 | 45224 | S: item40015; SQL5617; 100000/1000000; 1..1 |
| p/u246 | 703/511/1 | 45224 | I: $17273 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| p/u247 | 703/603/1 | 45224 | R: item40184 grade1 목적NPC roll 없음 |
| p/u248 | 703/606/1 | 45224 | R: item40193 grade1 목적NPC roll 없음 |
| p/u249 | 703/1493/1 | 45224 | I: $17515 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| p/u250 | 703/3018/1 | 45224 | I: $13819 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| p/u251 | 705/17/1 | 45248 | S: item40013; SQL5851; 50000/1000000; 1..1 |
| p/u252 | 705/337/1 | 45248 | S: item64; SQL5843; 2500/1000000; 1..1 |
| p/u253 | 705/382/1 | 45248 | I: $1203 grade1 후보40899; 고유 신원/차이 대응 미확정 |
| p/u254 | 705/495/1 | 45248 | S: item40018; SQL5853; 50000/1000000; 1..1 |
| p/u255 | 705/508/1 | 45248 | I: $17270 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| p/u256 | 705/1862/1 | 45248 | R: item40166 grade1 목적NPC roll 없음 |
| p/u257 | 707/382/1 | 45372 | I: $1203 grade1 후보40899; 고유 신원/차이 대응 미확정 |
| p/u258 | 707/492/1 | 45372 | S: item40015; SQL7225; 50000/1000000; 1..1 |
| p/u259 | 707/512/1 | 45372 | I: $17274 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| p/u260 | 707/545/1 | 45372 | I: $1798 grade1 후보없음; 고유 신원/차이 대응 미확정 |
| p/u261 | 707/576/1 | 45372 | I: $1835 grade1 후보40238; 고유 신원/차이 대응 미확정 |
| p/u262 | 707/597/1 | 45372 | I: $1856 grade1 후보40251; 고유 신원/차이 대응 미확정 |
| p/u263 | 707/12354/1 | 45372 | D: item12354 현재 ItemDef 없음 |
| p/u264 | 708/44/1 | 45216 | R: item104 grade1 목적NPC roll 없음 |
| p/u265 | 708/296/1 | 45216 | R: item40014 grade1 목적NPC roll 없음 |
| p/u266 | 708/1285/1 | 45216 | I: $3250 grade1 후보107; 고유 신원/차이 대응 미확정 |
| p/u267 | 708/3019/1 | 45216 | R: item263 grade1 목적NPC roll 없음 |

헤드리스 후속 관측에 쓸 수 있는 좌표 근거는 `m3/spawns.json`의 `population_m3_2_24`: 바포메트24, map2, rect(32685,32855)..(32715,32885)이다. 이는 LOCAL 기존 rectangle이고 고정 등장점·화면 클릭 픽셀이 아니다. 실제 후속 순서는 기존 정상 로그인/캐릭터선택/월드진입 → map2에서 현재 live UID·좌표 확인 → 해당 UID 선택·공격 → 실제 처치/ground UID 확인 → 줍기 → 인벤토리 item/grade/수량·저장/복원 확인이다. 게임 클라이언트·봇은 실행하지 않았다. 검증 범위는 정적 로더·순수 reward unit 및 기존 loopback broker unit이며, broker unit은 시험용 Temp 쓰기에서 아래와 같이 실패했다. 반지의 특수 사용/원본 입력·렌더링 완료를 주장하지 않는다.


### 재대조 검증과 남은 실행 제약

- 새 `world_expansion_data_tests.ReassessedDropTests` 2개는 전체449승격의 실제 SQL item/bless·목적NPC·itemId·chance/min/max, 기존 같은 item/grade identity 재사용 원행, item/grade→SQL ID 충돌0과 바포메트64/311의 정확한 roll 및 Baltuzar34의 미보유 polymorph roll 보류를 확인했다. 기존 M3 drop 참조·disjoint 검사와 전체 활성 ItemDef 참조 검사도 통과했다. 순수 `world_m1_reward_tests.WorldRewardTests`의5개(ground·Adena·레벨·소유·pickup order)도 통과했다.
- 오케스트레이터 독립 재실행: `python -X utf8 -B -m unittest tools.local_original_session.world_expansion_data_tests.ReassessedDropTests tools.local_original_session.world_reward_tests -q` → **22 tests OK (4.838s)**. SQL·신원·보상 계산 unit이며 실제 새449종의 획득/화면 PASS가 아니다.
- 첫 실행은 `python -m unittest tools.local_original_session.world_expansion_data_tests.ReassessedDropTests tools.local_original_session.world_m3_data_tests.M3DataTests.test_table_references_and_sources tools.local_original_session.world_expansion_data_tests.ExpansionDataTests.test_every_resolved_drop_is_loadable_item tools.local_original_session.world_reward_tests tools.local_original_session.world_m1_reward_tests -v`였다. 43 tests/24.605s, **FAILED(errors=29)**. 첫실패 `realm.py:185 tmp.open('xb')`의 `PermissionError: [Errno 13] Permission denied`(시스템 Temp 하위 characters.json 임시파일), cleanup도 `[WinError 5]`였다. 원출력은 실행 session9721의 도구기록에 보존했다. 이 실패를 제품 drop 결함이나 PASS로 치환하지 않았다.
- 허용된 TMP/TEMP fallback 명령은 아래와 같다. **34 tests/12.961s, FAILED(errors=13)**. `_work/tmp/tmpqoo_o0lj` 하위 임시파일 쓰기 및 Temp 정리도 같은 PermissionError/WinError5였다. [원출력](../../../_work/tmp/drop_reassessment_unit.log)을 보존했고 ACL변경·추가경로 우회·추가 broker재시도는 하지 않았다. 저장/loopback packet 획득은 OPEN이다.

변경 대상은 `data/m1/drops.json`, `m3/drops.json`, `m4/drops.json`, `m6/drops.json`, `catalog/map0/drops.json`, drop unit이 있는 `world_expansion_data_tests.py`, 이 문서다. m2/m5·population·ItemDef·transition·launcher·companion·magic은 수정하지 않았다. 착수 원문은 `_work/tmp/drop_reassessment_before.json`에 있고 작업용 일회성 변환은 `_work/tmp/drop_reassessment.py`다. 별도 제품 검사기/guard/report 체계는 추가하지 않았다.

Temp fallback 실패 명령(추가 실행은 Claude 담당):

```powershell
$env:TMP=(Resolve-Path '_work/tmp').Path
$env:TEMP=$env:TMP
python -m unittest tools.local_original_session.world_expansion_data_tests.ReassessedDropTests tools.local_original_session.world_m3_data_tests.M3DataTests.test_table_references_and_sources tools.local_original_session.world_expansion_data_tests.ExpansionDataTests.test_every_resolved_drop_is_loadable_item tools.local_original_session.world_reward_tests tools.local_original_session.world_m1_reward_tests.WorldRewardTests tools.local_original_session.world_m1_reward_tests.KitCapacityTests.test_pickup_keeps_rolled_grade_and_separates_scroll_stacks tools.local_original_session.world_m1_reward_tests.KitCapacityTests.test_bag_holds_l1j_180_kinds_then_keeps_new_kinds_on_the_ground tools.local_original_session.world_m1_reward_tests.KitCapacityTests.test_twenty_plus_new_drop_kinds_fit_and_go_out_as_split_0964_frames tools.local_original_session.world_m1_reward_tests.BrokerRewardTests.test_kill_drop_pickup_into_kit_inventory_and_saved_progress tools.local_original_session.world_m1_reward_tests.ProgressStoreTests -v
```
