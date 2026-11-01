# 클래식 상점 품목 갱신 결과

2026-10-28. 대상은 M2 말하는 섬, M4 글루딘, M5 본토 마을의 기존 상점 자료다. 요청의 데이터 전용 경계를 지켰으며 제품 코드와 상점 JSON은 수정하지 않았다. 현재 로더 계약상 신규 계산 가능 품목을 추가할 수 없어 NPC별 추가 판매·매입은 모두 0종이다.

## 상점별 수

| 지역·상점 | 기존 계산 가능 판매/매입 | 이번 추가 판매/매입 |
| --- | ---: | ---: |
| M2 배표상인 70011 | 1 / 1 | 0 / 0 |
| M2 판도라 70014 | 42 / 42 | 0 / 0 |
| M2 콜 70013 | 0 / 0 | 0 / 0 |
| M2 상인 후보 81123 | 0 / 0 | 0 / 0 |
| M4 Luth 70021 | 23 / 23 | 0 / 0 |
| M4 Catty 70024 | 12 / 12 | 0 / 0 |
| M4 Rollko 70020, Lakuki 80090, Jaint, Sharon, Myzin, Pumpkin Trader, Harbor Master | 각 0 / 0 | 각 0 / 0 |
| M5 24개 상점 | 합계 176 / 235 | 0 / 0 |

M2 입력 표는 84행이며 43행이 계산 가능, 미선정은 41행이다. M4 입력 표는 131행(판매가 있는 131, 매입가가 있는 65), Classic ID 선정 54행 중 35행이 계산 가능하다. M5는 원행 3,276개, Classic ID 선정 324개, 현 로더 규칙으로 계산 가능한 236행이다. 수치는 상점 파일의 참조 행 수가 아니라 현 로더에서 실제 계산 가능한 기존 행 수다.

M2 판도라의 기존 재고는 확장 품목 정의와 19종이 겹친다(무기 4, 방어구 3, 소모품 9, 잡화 3). ID 67 언월도는 M4에도 정의돼 있어 새 정의와의 교집합은 18종이다. 이들은 새 상점 행이 아니므로 추가 수에는 넣지 않았다.

## 데이터 전용으로 막힌 계약

- `world_shop.load_shops()`는 상점 JSON의 선택 Classic ID와 코드 안의 고정 `_ITEM_RULES`를 결합한다. 무게·겹침 규칙이 없는 L1J ID는 JSON에서 Classic ID를 골라도 계산 불가 상태로 남는다. 미선정 M2 41행과 M4 미선정 행 가운데 현재 `_ITEM_RULES`가 지원하는 ID는 없다. M4의 현재 선정 54행 중 19행도 고정 규칙 누락 때문에 계산되지 않는다. 이 M4 신규 정의는 `2, 13, 32, 37, 43, 55, 56, 59, 60, 68, 82, 83, 90, 91, 93, 94, 95, 125`다.
- M2/M4 `shop_buyback_reference.json`은 로더가 읽지 않는 참고표다. `selling_price < 0`인 매입 전용 행을 `shop_sales.json`에 복사해도 `open_shop()`의 판매가 필터에서 빠지고, 판매가를 임의로 0 이상으로 바꾸면 원행에 없는 NPC 판매를 만들므로 채택하지 않았다. M5에서도 매입 전용 60행은 이 필터로 SELL 목록에 도달하지 않는다.
- 공식 품목 snapshot `tools/local_original_session/data/official/items.json`의 610종 모두 `not_provided.shop_price.value`가 null이며 공식 상세에 상점가 필드가 없다. 따라서 새 가격을 공식 가격이라고 만들 근거가 없다. 기존 지역 행의 L1J 원가격을 `local_policy`의 x1·세금 0 정책으로 참조해야 하지만, 이는 공식 경제값 확인을 뜻하지 않는다.

실제 새 행을 거래 가능하게 하려면 신규 item ID의 무게·겹침 메타데이터를 로더가 소비하고, 매입 전용 행을 SELL 목록에 공급하는 계약이 필요하다. 이는 코드 변경이므로 현재 데이터 전용 요청에 포함하지 않았다. 품목 정의와 상점 판매·매입 노출은 별도 상태이며 이 결과를 전체 클래식 상점 완성으로 해석하지 않는다.

## 검증

- `python -X utf8 -B -m unittest tools.local_original_session.world_shop_tests` — PASS, 24 tests.
- `python -X utf8 -B -m unittest tools.local_original_session.world_shop_menu_tests` — PASS, 12 tests.
- `SL_TEST_TIME_SCALE=10`, `SL_TEST_PORT_BASE=20000`, `python -X utf8 -B -m unittest tools.local_original_session.world_m5_tests` — PASS, 9 tests; 내부 M5 packet scenario 결과 `work/local_original_session/runs/m5-bot-3c8oa9n1`.

원본 클라이언트 상점 화면과 실제 구매·매입은 이번 데이터 전용 시험 범위에서 확인하지 않았다.

---

## 후속 구현 연계 결과 (2026-10-28)

위 본문은 앞선 데이터 전용 시도의 원문이다. 이번 후속에서 `world_shop`이 `game_data`의 M1 `items.json`·`items_ext`와 지역 `items.json`의 raw 무게·겹침을 실제로 읽고, 매입 전용 원행을 SELL 목록에 공급하도록 연결했다. 아래 수치는 그 코드와 이번 JSON 조합의 로더·거래 계산 결과다. M2/M4 JSON의 과거 `loaded_by_product:false`·SOURCE_DATA_ONLY 표시는 수집 당시 기록이며 현재 로더 소비 여부를 대신하지 않는다.

### 상점별 계산 가능 판매·매입 수

판매는 `open_shop().offers`, 매입은 노출 후보의 각 Classic ID를 정상 수량1·미착용·강화0 인벤토리로 `calculate_sale()`에 넣어 성공한 품목 수다. 동일 ID 중복 매입 모호성은 0건이다. 이전 값은 변경 전 로더 목록 및 기존 고정 규칙을 재사용해 같은 노출·중복 조건으로 산출했다. 실제 인벤토리를 만들거나 게임·서버·포트를 실행한 결과가 아니다.

| 지역·NPC·상점 | 이전 판매/매입 | 현재 판매/매입 | 추가 판매/매입 |
| --- | ---: | ---: | ---: |
| M2 70011 Harbor Master | 1 / 1 | 1 / 1 | +0 / +0 |
| M2 70013 Cole | 0 / 0 | 0 / 0 | +0 / +0 |
| M2 70014 Pandora | 42 / 42 | 42 / 171 | +0 / +129 |
| M2 81123 Pumpkin Trader | 0 / 0 | 0 / 0 | +0 / +0 |
| **M2 합계** | **43 / 43** | **43 / 172** | **+0 / +129** |
| M4 70020 Rollko | 0 / 0 | 3 / 3 | +3 / +3 |
| M4 70021 Luth | 23 / 23 | 23 / 171 | +0 / +148 |
| M4 70022 Harbor Master | 0 / 0 | 1 / 1 | +1 / +1 |
| M4 70024 Catty | 12 / 12 | 20 / 19 | +8 / +7 |
| M4 80090 Lakuki | 0 / 0 | 7 / 0 | +7 / +0 |
| M4 80092 Jaint | 0 / 0 | 0 / 0 | +0 / +0 |
| M4 80096 Sharon | 0 / 0 | 0 / 0 | +0 / +0 |
| M4 80100 Myzin | 0 / 0 | 0 / 0 | +0 / +0 |
| M4 81123 Pumpkin Trader | 0 / 0 | 0 / 0 | +0 / +0 |
| **M4 합계** | **35 / 35** | **54 / 194** | **+19 / +159** |
| M5 70015 Arieh | 0 / 0 | 0 / 0 | +0 / +0 |
| M5 70016 Andyn | 13 / 13 | 26 / 25 | +13 / +12 |
| M5 70018 Ysorya | 23 / 23 | 24 / 171 | +1 / +148 |
| M5 70026 Derek | 1 / 1 | 3 / 2 | +2 / +1 |
| M5 70027 Dio | 0 / 0 | 0 / 0 | +0 / +0 |
| M5 70028 Randal | 6 / 6 | 6 / 6 | +0 / +0 |
| M5 70029 Margaret | 0 / 0 | 7 / 7 | +7 / +7 |
| M5 70030 Mayer | 23 / 23 | 24 / 171 | +1 / +148 |
| M5 70032 Vergil | 8 / 8 | 16 / 16 | +8 / +8 |
| M5 70033 Verita | 12 / 12 | 12 / 12 | +0 / +0 |
| M5 70036 Stella | 0 / 0 | 0 / 0 | +0 / +0 |
| M5 70038 Evert | 0 / 0 | 0 / 0 | +0 / +0 |
| M5 70039 Werner | 7 / 7 | 30 / 29 | +23 / +22 |
| M5 70043 Philip | 0 / 0 | 0 / 0 | +0 / +0 |
| M5 70061 Mandra | 7 / 7 | 31 / 30 | +24 / +23 |
| M5 70063 Bius | 23 / 23 | 24 / 171 | +1 / +148 |
| M5 70068 Franko | 1 / 0 | 6 / 0 | +5 / +0 |
| M5 70069 Momo | 0 / 0 | 0 / 0 | +0 / +0 |
| M5 70072 Elmina | 21 / 21 | 21 / 21 | +0 / +0 |
| M5 70082 Britt | 22 / 22 | 23 / 23 | +1 / +1 |
| M5 70083 Shivan | 9 / 9 | 12 / 11 | +3 / +2 |
| M5 70085 Old | 0 / 0 | 0 / 0 | +0 / +0 |
| M5 81123 Pumpkin Trader | 0 / 0 | 0 / 0 | +0 / +0 |
| M5 81124 Pumpkin Trader | 0 / 0 | 0 / 0 | +0 / +0 |
| **M5 합계** | **176 / 175** | **265 / 695** | **+89 / +520** |

전체는 판매254→362(+108), 매입253→1,061(+808)이다. 앞선 본문의 M5 매입235는 원행의 매입가 필드 합산이며, 당시 실제 SELL에 노출되는 매입 품목은175종이었다. 지역별 합계는 상점·품목 쌍이며 여러 상점의 같은 품목을 합친 고유 품목 수가 아니다.

M2 판매 추가0은 기존43개 선정 판매행이 이미 계산 가능했고, 미선정41개에서 확장 정의와 일치하는 새 판매 근거를 얻지 못했기 때문이다. 폭죽 등 token·종류·원본 그래픽 대응이 없는 품목은 그대로 미선정이다. M4는 기존 선정 행19개가 새 메타데이터 소비로 열렸으며, M5는 새 선정 판매55행과 기존 선정 미계산34행이 열렸다.

### 추가 자료와 출처

- 기존 per-NPC L1J 행의 가격·판매/매입 방향·pack·원문 reference는 보존했다. 새 NPC, 임의 판매가, 임의 매입가를 만들지 않았다. M2/M4 `shop_buyback_reference.json`은 각각129/148개 기존 매입행의 Classic 대응을 보강했고 M5 `shop_sales.json`은385행(판매55행)의 대응을 보강했다. 전체662행은 고유 품목662종을 뜻하지 않는다.
- 기존 상점의 reviewed Classic 대응을 우선 재사용했다. 그 밖에는 고정 client `catalog/items_all.json`의 name-token·kind·raw f10·f5·f6 대응이 confirmed이고 현재 `items` 정의가 있으며, 같은 L1J ID에 Classic 후보가 하나인 일반 bless1 행만 선택했다. client 원문과 공식 사전의 이름/정의가 우선이고 L1J는 backend 자료다. native 축복·변형 의미는 UNKNOWN이다.
- `data/official/items.json`의 수집610종에는 상점가격 값이 없으므로 가격을 공식값으로 주장하지 않는다. 각 대상 JSON의 `local_policy`는 원 L1J DB 판매/매입 가격 x1, 세금0을 명시한다. stock은 새로 만들지 않았다.
- 무기 대표: M4 Catty70024 빌귀사름 Classic32 180/90, M5 Andyn70016 그라디우스 Classic141 2,750/1,375. 방어구 대표: M5 Ysorya70018 부츠 Classic128 2,000/1,000, M2 Pandora70014 가죽모자 Classic317 매입2. 소모품 대표: M2 Pandora70014 달걀 Classic43 매입3, 양초 Classic36 매입1. 표기는 NPC판매/매입이며 매입전용은 NPC판매를 만들지 않았다.

### 미확인·후속 경계

장신구는 현재 표에 추가되지 않았다. 기존56개 장신구 정의 가운데 catalog로 대응되는 L1J49개(축복 변형 포함)를 전체 대상 NPC 원행과 대조했으나 교집합0이다. 전체 L1J `shop`을 확장 조사하면 normal 대응29행이 NPC81019/81020/81021에 존재하며 전부 판매1/매입1이다. 이들은 `spawnlist_npc`89524~89526(`l1jdb:49681~49683`)이고 `config/altsettings.properties:62~67`의 GMshop 범위89508~89535에 포함된다. 일반 마을 가격으로 채택하지 않았으며, 기존 상점으로 옮길 경우에는 GM가격 재사용과 NPC 재고 재배치를 별도 LOCAL 정책으로 명시해야 한다. `armor` 테이블에는 price/cost 열이 없고 별도 XML 일반상점 가격도 발견하지 못했다. 기본 항마의 반지496↔L1J20303, 신체/정신/영혼 벨트505/506/507↔20312/20319/20316은 대응 confirmed지만 일반 상점 가격이 없다. 오크 투사의 목걸이314↔20263은 token·ground 일치, icon 불일치의 candidate다. GM가격 적용 또는 장신구 보류에 관한 사용자 선택을 기다리며 현재 소스 동결을 유지했다.

원본 클라이언트 화면·입력·전체 클래식 경제 동등성은 미확인이다. 최종 단위시험·패킷 실행은 지정 시험 worker 결과를 아래에 기록한다. M4는 기존 merchant menu source가 없어 로더·계산 가능수를 해당 마을 실제 메뉴 완료로 확대하지 않는다.

### 후속 검증 실행

- `python -X utf8 -B -m unittest tools.local_original_session.world_shop_tests` — 26 PASS. `world_shop_menu_tests` — 13 PASS.
- 봇 공통 명령은 `SL_TEST_TIME_SCALE=10 SL_TEST_PORT_BASE=<base> python -X utf8 -B C:/Users/Chansol/AppData/Local/Temp/claude/D--claude/0483de89-75e7-4b94-84b8-fb31fe00f575/scratchpad/fastbot/run_fast.py hunt_bot_shop_update`이다. 실행 원문은 `work/local_original_session/runs/shop-update-validation-20261028-124900/commands.txt`와 로그에 보존했다.
- base49000 첫 봇은 M4 Catty 메뉴 source 부재로 SKIP, 요청9·정리완료(`shop-update-bot-ilwt83z1`). 신규 봇 기본 대상을 기존 메뉴가 연결된 Kent로 변경했다.
- base50000 봇 PASS, 11 checks·78 requests·정리완료(`shop-update-bot-hmwy6bh2/result.json`). fresh test_knight의 pre-login 시험 공급은 매입전용 Classic40 1개뿐이며 구매할 Classic13은 공급하지 않았다. 정상 로그인·선택·월드→Andyn70016 발급 BUY 목록에서 전투도끼13 구매770(신규UID65573)→발급 SELL 목록에서 매입385→Ysorya70018에서 Classic40의 BUY 미노출·SELL 매입16→정상 Quit/FIRST close→재접속 후 동일 저장 frame 복원을 확인했다. 실제 수신 인벤토리와 저장 Adena는1000→230→615→631로 일치했다. 원본 Native UI/입력 시험은 아니다.
- `world_m5_tests` base48000 첫 실행은 병행 작업의 `m4/town_services.json` 부재로 초기화 실패(요청0, 정리완료, `m5-bot-dcc6qc_r`). 파일 존재 후 base51000 재시험은 data8개 PASS·packet1개 FAIL(`m5-bot-1kuu1jf5`). 상점 BUY/SELL·창고는 통과했고 Kent field 단계에서 `NAVIGATION_STALLED`로 실패했다. 서버 오류목록은 비어 있으며, 종료 당시 population 사냥감 선택·점유/회피 영향은 UNKNOWN이다. 실패 원문은 보존했다. 이후 다른 writer가 수정한 현재 `hunt_bot_m5.py`에는 Kent population 후보 제외가 있어 그 새 소스로 한 번 더 시험한다. 이 파일은 이번 상점 작업에서 수정하지 않았다.
- base52000의 새 M5 소스 재시험도 data8개 PASS·packet1개 FAIL(`m5-bot-wfwi0_zr/result.json`, 요청469·정리완료). Kent 상점·창고 통과 뒤 level5 `m5_kent_4` 사냥터 이동에서 `NAVIGATION_STALLED`였다. handler 오류는0이며 실제 몬스터 공격 응답을 받았다. 시험 시작·종료 사이 다른 writer가 `hunt_bot_m5.py`를 다시 변경했으므로 고정 소스 M5 전체 PASS는 성립하지 않는다. 범위 밖 파일을 수정하거나 더 반복하지 않았다. M5 봇 writer의 실행 소스 고정과 이동 실패 해결이 남았다. 별도 새 품목 거래 PASS와 이 실패를 합산하지 않는다.
