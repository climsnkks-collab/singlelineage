# M2 말하는 섬 마을 상점 데이터

2026-10-26. 요청한 **데이터 준비만 완료**했다. L1J·서버·게임을 실행하지 않았고 제품 로더·저장·큐는 변경하지 않았다. 클래식 기준은 `MAPPING_SCOPE.md`의 26.09.29.2001이다. 아래 L1J 위치·가격·상품 구성은 출처가 있는 로컬 정책 **후보**이며 클래식 원본 상점의 확정값이 아니다.

## 산출물과 범위

모두 `tools/local_original_session/data/m2/`에 둔다. 기존 `m1/`과 분리된 준비 자료이며 `game_data.py`가 아직 읽지 않는다. JSON 공통 `reference_paths`의 약어와 각 행의 `source_ref`로 원문을 찾는다. 새 추출기·검사기 파일은 만들지 않았다.

| 파일 | 내용 |
|---|---|
| `shop_npcs.json` | 클래식 마을 경계 안 L1Merchant 21명. 스폰·NPC 원문, 상품 수, 클래식 NPC/SPR 후보. 상품 있는 4명과 shop 행 없는 17명을 구분한다. count0인 Liri도 비활성 원행으로 남겼다. |
| `shop_sales.json` | NPC→플레이어 판매 가능 84행. L1J item 정의, 양방향 가격, 묶음 수량, 클래식 아이템·아이콘 후보와 불일치. 선택 후보 43행, 미선택 41행. |
| `shop_buyback_reference.json` | 판매 불가 나머지 909행. 매입 전용 904행과 양 가격 -1인 비활성 5행. 원행 숫자와 위치만 보존하며 전량 클래식 아이템 변환은 하지 않았다. |

경계는 `work/local_resource_provider/assets/data/region.jsonc:3`의 map0, x32543..32671/y32905..32987이다. 정수 중심 좌표가 경계에 포함되는 `spawnlist_npc` 행에서 `npc.impl=L1Merchant` 또는 shop 행이 있는 NPC를 선정했다. 랜덤 반경은 원값으로 보존했으며 반경 안 모든 셀의 통행·클래식 배치까지 확인한 것은 아니다.

## 상품 있는 NPC

L1J 원문은 `D:/SingleLineageRef/l1j-en-classic/db/l1jdb_m10.sql`이다. 열 정의는 npc:1544, shop:1756, spawnlist_npc:1917, weapon:2091, armor:63, etcitem:716이다.

| L1J NPC / 분류 | 위치 / NPC행 / 스폰행 | 전체 / 판매 / 매입 |
|---|---|---|
| 70014 Pandora / 잡화·무기·방어구·물약 | 32645,32951 / 22069 / 48986 | 964 / 55 / 955 |
| 70013 Cole / 불꽃놀이 | 32635,32951 / 22068 / 49045 | 26 / 26 / 26 |
| 70011 Harbor Master / 항구 배표 | 32633,32968 / 22066 / 49055 | 1 / 1 / 1 |
| 81123 Pumpkin Trader / 계절 이벤트 | 32575,32950 / 23171 / 50257 | 2 / 2 / 2 |

M2 핵심 후보는 Pandora다. 이 L1J 표의 경계 안에서는 무기·방어구 별도 판매 NPC를 찾지 못했고 Pandora가 함께 판매한다. Cole·항구·호박 상인은 누락 방지를 위해 포함하되 M2 핵심으로 선택하지 않았다. shop 행이 없는 서비스/제작 NPC에게 상품을 새로 지어 넣지 않았다.

**판매 NPC 4명의 클래식 NPC template는 UNKNOWN이다.** 해당 L1J 이름토큰과 같은 native npc 행이 없었다. SPR98=`pandora`(파싱 JSONL:94), SPR725=`citizen girl`(:398), SPR148=`kent castle guard`(:140)는 기존 클래식 SPR 레코드의 존재만 확인했다. 이것으로 NPC template나 실제 정상 외형·클릭/메뉴 동작을 확정하지 않는다. 호박 상인의 gfx2499는 같은 파싱 표에서 찾지 못했다. 상품 없는 NPC 중 토큰·f2가 맞는 후보 7명은 각 원행과 함께 남겼다. L1J81200의 `?????????` nameid는 원 SQL의 문자열 그대로다.

## 가격·수량 해석

- `selling_price>=0`은 NPC 판매, `purchasing_price>=0`은 NPC 매입이다. 각각 -1이면 해당 방향을 제공하지 않는다. 가격0도 원행의 유효값으로 보존했다. L1J `src/l1j/server/server/datatables/ShopTable.java:80-91`이 두 목록을 별도로 만든다.
- `pack_count=0`은 같은 파일:83에서 1로 바뀐다. JSON은 raw값과 `effective_pack_count`를 함께 보존한다. 판매 가격은 묶음 하나 가격이며 주문 수량×묶음 수량이 실제 지급 개수다(`model/shop/L1ShopBuyOrderList.java:55-100`). 화살40743은 DB가격1/10개 묶음이므로 기본 개당 가격은 유리수1/10이다. 임의로 정수 단가로 반올림하지 않았다.
- 가격은 **DB 원가**, 세금·배율 적용 전이다. 판매는 `Config.RATE_SHOP_SELLING_PRICE`와 `L1TaxCalculator`를 거치며 매입 단가는 `int(price*RATE_SHOP_PURCHASING_PRICE/pack_count)`다(`model/shop/L1Shop.java:107-109`). 실행 시 세금·배율을 읽거나 클래식 정책으로 채택하지 않았다.
- L1J `order_id`는 같은 NPC 안에서도 반복된다. 원행 식별은 `(npc_id,item_id,order_id)`이고 이를 클래식 wire row key나 live UID로 사용하면 안 된다. 화폐 L1J40308↔클래식7/$4 대응은 기존 MAPPING_SCOPE 근거만 참조하며 재화·UID·funding을 생성하지 않았다.

## 클래식 아이템 대응과 한계

`MAPPING_SCOPE.md` 3장 방식으로 판매 84행만 `native-dump-v1.jsonl`과 대조했다. **확인된 것은 각 dump 행의 ID·한국어 이름·토큰·f5 아이콘 등 필드값이다. 교차버전의 동일성·등급·원본 경제·실제 소비는 모두 후보/미확정이다.** `selected_classic_item_id`도 준비 단계에서 선택한 후보 ID이며 제품 사용 승인을 의미하지 않는다.

기본 선택은 이름토큰·종류·아이콘이 맞는 유일한 이름 있는 행 36개다. 토큰이 같은 중복 후보도 배열에 남겼다. 별도로 장검3·빨간 물약14·강화 초록 물약495는 이름과 두 그래픽의 일치 및 기존 M1 대응을 근거로 토큰 변경 후보로 선택했다. 창12·활11·가죽 재킷103·사탕362는 이름·토큰·종류가 맞지만 아이콘이 바뀐 후보 4개로 따로 표시했다. **사용할 아이콘은 선택한 클래식 행의 f5이며 L1J invgfx를 그대로 보내지 않는다.** 예를 들어 가죽 재킷은 클래식103/icon62와 L1J20322/invgfx1196으로 다르다.

| 예시 | L1J → 클래식 후보 / 아이콘 | DB 판매·매입 |
|---|---|---|
| 단검 | weapon4/$70 → item41/$70 /35 | 8 /4 |
| 가죽 갑옷 | armor20089/$116 → item102/$116 /51 | 100 /50 |
| 가죽 재킷 | armor20322/$167 → item103/$167 /62 | 1 /0 |
| 빨간 물약 | etcitem40010/$26 → item14/$237 /80 | 37 /19 |
| 주홍 물약 | etcitem40011/$235 → item15/$235 /78 | 150 /75 |
| 맑은 물약 | etcitem40012/$238 → item130/$238 /81 | 300 /150 |

빨간 물약은 기존 `tools/local_original_session/data/m1/items.json` item14의 그래픽80/45·L1J40010 대응을 재사용했다. 상품의 일반/축복/저주 의미는 native dump에서 해독하지 않았으므로 L1J bless1을 클래식 등급으로 자동 승격하지 않는다. 화살29/30은 같은 토큰·아이콘·ground graphic이므로 선택하지 않았다. L1J Wand of Blink와 클래식 흑단 막대21은 같은 그래픽이어도 이름/효과가 달라 거절했다. 마법 방어 사슬 갑옷20110도 icon1201만 같은 클래식 사슬 갑옷167로 대체하지 않았다. 불꽃놀이·고대 물약·지도·투척검·이벤트 상품 등 미선택 41행은 삭제하지 않고 원문/후보/부족 근거를 남겼다.

## 기존 SHOP 계약의 재사용 위치

상점 패킷·거래·저장을 새로 구현하지 않았다. 다음 기성 문서와 자료를 소비자가 재사용한다.

| 자료 | 재사용할 내용과 경계 |
|---|---|
| `implementation-4/shop-quest/merchant-source-input-v1/API.md` | 정상 publication·Catalog·Offer·row key·unknown678·provenance를 받는 `prepare(...)` 계약. 기존 SPR1552 auction board 선택은 명시 LOCAL 정책이며 Pandora template의 근거가 아니다. f39를 template로 가정하지 않는다. |
| `shared-api/mob199-root-potion-shop-source/API.md` | Potion14 일반상품 Source·정확 Setup/Catalog/Resource/current/credit 연결. 가격37의 정당 funding은 별도 미공급이므로 데이터만으로 준비완료가 되지 않는다. |
| `shared-api/gear-created-child-canonical-shop/API.md` | 새 캐릭터 canonical GEAR/SHOP birth admission 미공급 경계. 기존 root 상품·UID 복사를 새 지급으로 대체하지 않는다. |
| `integration-1/packet-shop-actual-v4/shop-result.json`, SHOP `HANDOFF.md:874` | 정상 로그인/WORLD→NPC→4E43/4E44→4ED4/4E48 row101→무패킷 수량선택→4ED1→commit/drain/Store/fresh의 기존 제한 PASS. LOCAL Athame의 결과이며 M2 아데나 경제나 UI PASS로 확대하지 않는다. |
| `integration-1/shop-human-manual-serial396-v8/API.md`, `parent-policy.json` | v8의 exact decoder trailer length 후손과 보존된 LOCAL buy3/sell1/max10 계약. 정상 메뉴·BUY·원 UI 완료는 여전히 미확인이고 해당 가격을 이번 L1J 가격에 덮어쓰지 않는다. |
| `run106_shop_dialog_contract/wire_schema/shop_list_opcode/findings.md` | BUY list4E48·SELL list4EE7·Event4EEF 등록/소비와 기성 wire schema. L1J 2009 opcode를 이식하지 않는다. |
| `run128_shop_buy_row_display/main-review.json` | BUY row f2 CommonItem 조회, 독립 f3 아이콘, f4 표시가격, row key/수량4ED1 소비. 실제 현재 catalog/render/거래는 별도다. |
| `run241_book_shop_row_and_icon/MAIN_REVIEW.md` | BUY f6/7/8 required presence와 클래식 f5/UI reference의 구별. 이번 JSON이 이 세 필드의 정당 값을 공급하지 않는다. |
| `run249_shop_buylist_first_consumer/MAIN_REVIEW.md` | outer f2=0의 조건부 CommonItem null+D0 반례. 임의 header/placeholder0으로 정상 입력을 만들지 않는다. |

표의 implementation/shared-api/integration 기준은 `work/local_original_session/`, run* 기준은 `work/local_server_rea_20261016/`이다. 다음 소비자는 ① 핵심 NPC의 클래식 identity/template 또는 명시 LOCAL 외형 정책 ② 정당 current/uid/catalog/offer와 BUY 필드 ③ 정상 플레이로 확보한 재화·상품·저장 권위 ④ 실제 메뉴/거래/소비/저장/정리 연결을 완결해야 한다. 준비 JSON을 실행 PASS로 표시하지 않는다.

## 확인

기존 Python 실행파일 `C:/Users/Chansol/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe -X utf8 -B -`에 일회성 stdin 코드를 전달했다. SQL을 읽기만 하여 선정 원행을 만들었고 같은 명령 형식의 데이터 확인에서 JSON 파싱, 원행 숫자·줄 위치 대조, 경계·상품 수, 후보 ID/아이콘 원문 대조, 선택 후보의 배열 포함, 84+909=993 분할·키 중복·pack 정규화·깨진 물음표 문자열을 확인했다. 영구 검증 도구는 추가하지 않았다. 실행·패킷·UI·가격 적용 시험은 UNRUN이다.
