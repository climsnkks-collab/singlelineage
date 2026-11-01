# M2 마을 NPC 대사·상점 메뉴 대응

## M5 막힌 상인·여관 최소 배치 복구 (2026-10-29)

기란 상인 4명과 같은 map4 등록 거절 원인이 있는 오렌·하이네 상인/여관 5명을 가까운 통행 칸으로 옮겼다. `WorldTerrain.can_stand`가 원 중심에서 False여서 `TownNpcs.register`가 건너뛰던 배치다. `town_npcs.json` 9개와 중복되는 `shop_npcs.json` 6개의 `(l1j_npc_id, spawn.id)`·좌표를 맞췄으며, NPC ID·count·map·heading·메뉴·상품은 유지했다. shop의 보존용 `spawns[]`와 소비용 `spawn`도 일치시켰다. 각 spawn의 `reference_locx/reference_locy`와 `local_placement_source.source_spawn`에 원 좌표·원 행·기존 blocked 판정을 보존한다. 아래 이동은 **LOCAL 배치 정책**이며 공식 Classic NPC 위치를 확정한 것이 아니다.

| 마을 | NPC / L1J ID / spawn ID | 원 중심 (x,y) | 선택 중심 (x,y) | 정적 return→선택 칸 이동 수 |
|---|---|---|---|---:|
| 기란 | Verita / 70033 / 60804 | 33383,32730 | 33385,32730 | 75 |
| 기란 | Mayer / 70030 / 60806 | 33455,32820 | 33457,32820 | 25 |
| 기란 | Werner / 70039 / 60902 | 33398,32669 | 33400,32669 | 127 |
| 기란 | Vergil / 70032 / 60909 | 33436,32751 | 33438,32751 | 45 |
| 기란 | Molly / 70031 / 61127 | 33431,32785 | 33431,32783 | 20 |
| 오렌 | Mandra / 70061 / 60904 | 34068,32295 | 34070,32295 | 17 |
| 오렌 | Enke / 70065 / 61128 | 34062,32252 | 34062,32254 | 24 |
| 하이네 | Shivan / 70083 / 60903 | 33624,33283 | 33624,33281 | 45 |
| 하이네 | Elly / 70084 / 61124 | 33599,33273 | 33599,33271 | 14 |

선택 근거는 보존 클라이언트 map4 S32와 기존 `world_terrain.py`다. 9개 모두 원 중심·주변 8칸이 False이고 선택 칸은 True다. 선택 이동은 유클리드 거리 제곱 4로 가장 가깝고 기존 양수 count NPC 중심과 겹치지 않는다. 같은 최소거리 후보는 큰 x, 이후 작은 y 순서로 골랐다. 각 마을의 기존 `towns.json.return_point`에서 마을 bounds의 외곽 8칸까지 기존 `can_step` 규칙으로 정적 경로를 확인했다. 표의 이동 수는 해당 제한 범위에서 찾은 정적 경로이며 실제 플레이어 이동·문·동적 점유·native 입력/화면 PASS가 아니다. 원 SQL `source_ref`와 읽은 S32 경로는 각 spawn의 `local_placement_source`에 있다. 기존 `terrain_validation.json`은 원 좌표의 과거 관측으로 보존한다.

켄트·우드벡은 현재 서비스/상인에 같은 blocked 중심이 없고, 글루딘은 기존 Karim의 east1 LOCAL 복구가 이미 반영돼 있다. 기란 Alchemist70520·Coliseum Manager50037·Jason70040·Secil70042·Polly70035는 현 메뉴가 미확보라 보류한다. 하이네 집사 Miriam50619·Elsha50622는 대화 자원만 있고 지원 서비스 action이 없어 이 상인·서비스 복구에 포함하지 않는다. 분수·횃불·장식 객체와 count0은 옮기지 않았다. 말하는 섬(map0)에도 blocked 원 후보가 있으나 기존 초기 town 등록은 map0에 이 map4 passability 거절을 적용하지 않으므로 동일 원인으로 단정하지 않았다. 말하는 섬 배치는 변경하지 않았다. 게임·서버·포트 실행 없이 정적 자료만 확인했으며 native 화면/입력은 UNRUN이다.

## 실험 스위치 기본 활성화 판정 (2026-10-29)

상점과 개인 창고에 아래 LOCAL 기본 정책을 채택한다. 일반 변신과 강화의 LOCAL 처리 경로도 이미 기본 연결돼 있다. 공식 서버 공급값이나 화면 동등성을 확정한 것은 아니다. 아래의 기본 켬은 `world/items` 기능이 등록된 구성을 뜻하며 `-World` 없는 실행이나 `SL_DISABLE_FEATURES`로 제외한 기능까지 켠다는 뜻은 아니다.

| 기능 / 스위치 | 판정 | 근거와 부족 입력 |
|---|---|---|
| 상점 목록 `-ShopExp` / `SL_EXPERIMENT_SHOP` | LOCAL 기본 켬 | outer.f2=7 → catalog item7.f5=5 → `Common_5.png`. BUY f6/f7/f8은 required presence 검사 `6C3B74`를 충족하는 present 0/0/0. 공식 공급값과 필드 업무 의미는 미확정이다. |
| 개인 창고 `-WarehouseExp` / `SL_EXPERIMENT_WAREHOUSE` | LOCAL 기본 켬 | COUNT/LIST tuple `(1,C,150,C,7,30,150)`, C는 현재 점유 행 수. kind1은 LOCAL 개인창고 선택이며 공식 개인/혈맹 대응은 미확정이다. [WAREHOUSE_EVIDENCE](WAREHOUSE_EVIDENCE.md) 참조. |
| 강화 소비·저장·generic Inventory 갱신 | 이미 기본 켬, 유지 | `world_feature_items._world_enchant_use`는 실험 유무와 독립적으로 기존 CAS·저장 뒤 `0965/0978` 투영을 수행한다. 송신 표시 훅은 25/26의 use code7을 기본 공급한다. [ENCHANT_USE_EVIDENCE](ENCHANT_USE_EVIDENCE.md) run393의 `529410→4FF370→52A820`은 조건부 대상 클릭 요청, `4F7670/4F6920`은 generic 소비 근거다. 실제 주문서 raw 귀속·`I+508` 활성화와 native 화면은 미확정이며 기본 구현을 원본 동등성으로 판정하지 않는다. 확률은 L1J `Enchant.java/rates.properties` 기반 LOCAL 정책이며 [FILL_ENCHANT](FILL_ENCHANT.md)의 안전값 출처와 구별한다. |
| 강화 결과 `-EnchantExp` / `SL_EXPERIMENT_ENCHANT` | 보류, opt-in 유지 | `world_enchant_inventory.result_frame`만 미확인 `SC0967`을 추가한다(kit 초기 투영의 raw7 조건에도 사용). run393 RVA `30B500→event17F9940`, descriptor `1601E80`, IsInitialized `7A7260`은 schema/publish 근거다. 실제 결과 소비 callback, required f1..5의 업무 의미·성공/실패 enum과 같은 강화 작업의 응답 순서가 없다. 결과 UI/문구·소멸·강화 전후 값의 실제 소비를 연결해야 한다. L1J 확률로 이 패킷 의미를 채우지 않는다. |
| 일반299 변신 `-PolyExp`, `-PolyForm` / `SL_EXPERIMENT_POLY` | 이미 기본 켬, 스위치 제거 가능 | [POLYMORPH_SELECT_UI](POLYMORPH_SELECT_UI.md): raw16→`5689D0` 원 창, callback `AC1530→569260→4FE630`, params.f7은 XML 이름이다. 서버는 환경변수를 읽지 않고 `native_names`로 검토된 63개 이름을 처리한다. [POLYMORPH_EVIDENCE](POLYMORPH_EVIDENCE.md)의 `4E5C` 소비와 기존 scheduler·소비/장비 공동 저장을 재사용한다. 지속시간·무기 제한은 L1J 기반 LOCAL 정책이며 native 화면·자세0 완전 복원·접속 간 시간 저장은 미확인/미제공이다. |
| 변신 미대응22개·특수 주문서 | 보류 | [POLYMORPH_UPDATE](../../../tools/local_original_session/data/m1/POLYMORPH_UPDATE.md)의 항목별 SPR·무기 mask·특수 아이템별 목록/등급/지속시간 부족을 유지한다. XML 이름·L1J 유사 이름만으로 일반299 목록에 추가하지 않는다. |

`start-manual-play.ps1`의 `-ShopExp 0`, `-WarehouseExp 0` (또는 `off`)은 각 기능을 끈다. 생략하면 환경변수를 지우고 서버의 LOCAL 기본값을 사용한다. 두 옵션은 월드를 자동으로 켜지 않으므로 월드 구성이 필요하다. 임의 숫자 조합은 이 실행 경로에서 받지 않는다. `-EnchantExp`와 `-PolyExp`, `-PolyForm`은 기존 경로를 유지한다.

### 헤드리스 화면 확인 절차 — UNRUN

말하는 섬 map0의 **Pandora (L1J NPC ID 70014, 중심 32645,32951)** 에서 현재 발급 NPC UID를 선택 → 대화 `pandora` → `buy` → 아데나 아이콘·단가 확인 → 행 선택·수량 1 → 확정하고 Inventory·아데나 변화와 저장/재접속 복원을 확인한다. `sell`도 같은 NPC의 별도 경로다. 배치 ID와 현재 발급 UID는 구별한다.

같은 map0의 **Dorin (L1J NPC ID 60001, 중심 32575,32946)** 에서 현재 UID 선택 → LOCAL `storage` → `deposit` → Inventory 행·수량 선택 → 확정한다. 다시 Dorin → `retrieve` → 창고 행 선택·수량 설정 → 확정한다. 비어 있지 않은 시험 저장에서 count/limit와 한 행 30A, 두 행 60A 및 실제 아데나 잔액을 확인하고 입출고 결과와 저장/재접속 복원을 확인한다. `4ED4` action → `4ED1` 확정 → `097B` close이며 close만으로 거래 성공을 판정하지 않는다. 실제 NPC 화면·입력·좌표 도달과 거래 결과는 **UNRUN**이다. Dorin의 sprite 및 storage 연결은 LOCAL 후보이며 공식 대응은 미확정이다.

`D:/SingleLineageRef/l1j-en-classic/db`의 shop 표는 NPC 상품·가격 업무 데이터 참고이며 위 native 필드 소비의 근거가 아니다. 기존 실패와 제한된 성공 기록은 아래 그대로 보존한다.

`world_shop_warehouse_tests.py`를 포함한 단위시험 81개 중 70개는 통과했고, 11개 시험에서 임시 디렉터리 접근 `PermissionError` 21건(정리 오류 포함)이 발생했다. assertion 실패는 0건이지만 전체 검증은 미완이며 화면 확인은 UNRUN이다. 기존 `inventory_tests`·`inventory_store_tests`는 미실행이다. 상세: `_work/shop-warehouse-unittest-primary-runtime.log`.

현재 데이터에서 Pandora의 Classic item14는 L1J 40010, order28, 판매 37A·매입 19A·pack1이다. Cole70013은 현재 매핑에서 판매 0건·미해결 26건으로 BUY 목록이 비어 있으므로 위 화면 확인은 Pandora를 기준으로 한다.

### 기본 경로 회귀 시험

추가한 두 시험은 환경변수가 없는 실제 startup helper와 표시/변경 함수를 호출한다. 변신은 상점/획득 정책·시작 kit·줍기의 raw16 및 native 이름 연결을 확인한다. 강화는 기본 raw7 표시·주문서 수량 차감·강화 이름 변경과 미확인0967 미발행을 함께 확인한다. 임시 저장·포트·게임을 사용하지 않으며 native 화면/입력 PASS가 아니다.

```powershell
python -X utf8 -B -m unittest tools.local_original_session.world_polymorph_inventory_tests.PolymorphInventoryTests.test_default_startup_supplies_native_scroll_without_poly_experiment tools.local_original_session.world_enchant_inventory_tests.EnchantInventoryTests.test_default_startup_keeps_target_use_and_mutation_without_unknown_result
```

결과: **2 tests OK (0.141s)**. 변경 시험 파일은 `world_polymorph_inventory_tests.py`, `world_enchant_inventory_tests.py`다.

관련 모듈 전체 명령은 다음과 같다. **103 tests 실행, errors=17, 전체 통과 아님**. 임시폴더 `C:/Users/Chansol/AppData/Local/Temp/tmp...` 생성 후 파일 쓰기/cleanup의 `PermissionError`가 상점·창고 저장·변신 장비 공동 저장 시험을 막았다. 요청에 따라 임시폴더 위치/권한을 우회하거나 해당 저장 시험을 재시도하지 않았다. 추가한 두 시험은 위 독립 명령으로 통과를 확인했다.

```powershell
python -X utf8 -B -m unittest tools.local_original_session.world_shop_tests tools.local_original_session.world_shop_menu_tests tools.local_original_session.world_warehouse_tests tools.local_original_session.world_enchant_tests tools.local_original_session.world_enchant_inventory_tests tools.local_original_session.world_enchant_coverage_tests tools.local_original_session.world_polymorph_tests tools.local_original_session.world_polymorph_inventory_tests tools.local_original_session.world_polymorph_recheck_tests
```

아래는 기존 자료와 당시 관측 원문이다.

2026-10-26. 결과 데이터는 `tools/local_original_session/data/m2/npc_menus.json`이다. 기존 마을·상점 자료와 보존된 Classic UML/현지화 자료를 대응한다. 이번 쓰기 범위는 이 문서와 해당 JSON뿐이며 제품 코드·큐·저장·원본은 수정하지 않았다. 게임·서버·L1J·broker는 실행하지 않았다.

## 연결에 필요한 값

**Classic 대사창은 숫자 대사 ID 대신 UML stem을 4E44.f2로 받는다.** `data/uml/` + stem + `.uml`이 원 파일명이다. 예를 들어 `pixel`을 보내면 `data/uml/pixel.uml`을 찾는다. `pixel.uml`을 보내면 `.uml.uml`이 되므로 확장자를 포함하지 않는다. 근거는 `work/local_server_rea_20261016/run122_dialogue_resource_link/main-filename-review.json:16`이다. 옛 `RESOURCE_LOOKUP.md`의 fullkey 후보 설명은 이 후속 확정으로 교정한다.

| 단계 | 원 값과 기존 구현 | 이번 자료의 사용 범위 |
|---|---|---|
| NPC 선택 C2S4E43 | required f1 signed int32. 원 Actor slot8 UID low32 비트다. `run106_shop_dialog_contract/dialog-request-main-review.json:29` | 현재 선택된 NPC UID를 기존 resolver로 연결한다. L1J NPC ID·Classic catalog template를 클릭값으로 보내지 않는다. |
| 대사 S2C4E44 | required f1 i32/f2 string, optional f3 string, repeated f4 i64/f5 string. `dialogue-contract/INTEGRATION.md:13`, `hypertext-field4/INTEGRATION.md:14` | f2에는 아래 대응한 정확 stem을 쓴다. f3를 HTML 본문으로 해석하거나 미확정 f4에 UID를 넣지 않는다. |
| 메뉴 C2S4ED4 | required f1 i32/f2 action string, optional f3 cookie/string/f4·f5 i32. `run106_shop_dialog_contract/haction-menu-main-review.json:35` | f1은 발급한 4E44/45 메뉴 context의 echo다. action·cookie는 실제 메뉴 자원/입력에서 온다. 원 normal writer는 좌표를 모두 present로 보내며 좌표 flag가 없으면 0/0이다. |
| 구매 목록 S2C4E48 / 판매 목록 S2C4EE7 | outer required f1/f2 i32, repeated f3 rows. `dialogue-contract/shop-list-wire/INTEGRATION.md:15` | 상점 메뉴 `buy`/`sell` 이후 기존 목록 생산자를 쓴다. NPC 대응표가 outer2·row6/7/8 등의 미확정 값을 생산하지 않는다. |
| 확정 C2S4ED1 | f1 context u32, f2 BUY5/SELL6, repeated f3 `{rowkey:u32,quantity:u64}`, 명시 f4/f5 i32. `dialogue-contract/trade-request-wire/INTEGRATION.md:14` | context·rowkey는 받은 목록의 값이며 NPC ID나 메뉴 ID가 아니다. normal 수량은 1..INT32_MAX. 원 null/both-zero 좌표 경로는 -2/-2로 HACTION의 0/0과 다르다. |

위 표에서 `run*`의 기준은 `work/local_server_rea_20261016/`, 구현 상대경로의 기준은 `work/local_original_session/implementation-4/shop-quest/`이다. 기존 strict codec은 재사용 위치이며 이번 조사에서 import·실행하지 않았다. 4E44.f4는 후속 확장으로 canonical unpacked signed64/tag0x20, 일반 two's-complement varint가 확인됐다. 옛 codec의 `f4 UNSUPPORTED` 설명만 읽어 제외하면 안 된다. packed/slow fallback과 개별 값의 업무 의미는 미확정이다.

**메뉴 항목의 식별자는 UML의 action literal이다.** 숫자로 보이는 action도 문자열로 보존한다. 공통 wire에 별도의 숫자 메뉴 항목 ID는 없으므로 자원에 명시되지 않은 numeric ID는 null로 남긴다. XML 문서 순서, 목록 row key, catalog_npc, live UID를 대신 넣지 않는다. 4ED4.f1은 초기 클릭 UID와 자동 동치가 아니며, 기존 normal Hypertext encoder가 둘을 같게 제한하는 로컬 정책과 원 schema를 구분한다(`haction-list-ingress-v1/API_DESIGN.md:62`).

원 버튼 처리에서는 local action lookup이 먼저이며 fallback `haction`만 등록된 UMLEvent_HACTION→4ED4로 이어진다. 따라서 XML에 `buy`가 있다는 사실이 모든 상태에서 4ED4를 보낸다는 뜻은 아니다. cookie/link·close·panel 속성을 보존하며 임의로 빈 argument를 만들지 않는다. 근거: `run122_dialogue_resource_link/main-button-review.json:38`.

## 자료 판정과 NPC별 대응

**마을 NPC31종·42배치(활성39/count0 비활성3)를 정리했다.** 기존 town27종과 상품 보유 상인4종의 합집합이며 무상품 서비스17종을 중복 추가하지 않았다. 외곽 adjacent10배치는 이번 마을 표에 포함하지 않는다. Classic catalog 식별 대응 확정은 기존7종을 유지한다. 메뉴 후보54개 중25개는 보존 UML과 현재 catalog의 기존 `identical` 판정을 확보했고, 나머지29개는 현재 catalog와 보존 UML에서 찾지 못했다. 이는 확보 자료 범위의 부재 판정이다.

Classic catalog의 이름·template 대응, 원 UML/텍스트 존재, 특정 NPC가 실제 발급한 메뉴, 실제 창 표시·입력은 각각 별개 판정이다. 위치는 기존 자료의 L1J 배치 후보이며 count0·반복 배치를 그대로 보존한다. L1J 기본 `normal_action/caotic_action/teleport_url/teleport_urla`와 Java/XML 조건부 override를 구분한다. 빈 문자열과 npcaction 행 부재도 합치지 않는다.

아래 `—`는 template 미확정 또는 원 자원 미확보다. ‘키 확보’도 NPC가 그 메뉴를 발급한다는 실행 확인은 아니다. 모든 위치는 map0 중심 좌표이며 경비6배치씩과 Zeno의 count0/1 중복 좌표는 JSON에 원행별로 보존했다. 상품 유무는 L1J shop 행에 귀속하며 Classic 경제·재고의 확정값이 아니다.

| NPC / L1J ID | Classic template / 중심 좌표 | 확보한 native stem·메뉴 | 후보·결손 |
|---|---|---|---|
| Pandora70014 | — / 32645,32951 | `pandora`: `buy`, `sell`, `asktax`, `asknpctax`; `pandora2` 거절 | 상품 있음. L1J caotic `pandora5`는 없음; `pandora2`로 자동 대체하지 않음. |
| Cole70013 | — / 32635,32951 | `cold1`: `buy`, `sell`, `asktax`, `asknpctax`; `cold2` 거절 | 상품 있음. NPC 식별/조건별 발급은 후보. |
| 항구 배표 상인70011 | — / 32633,32968 | `ShipEvM3`: `buy`, `sell`, link `ShipEvM4` | 상품 있음. L1J `shipEvI3/shipEvI1`은 없음. native 말하는 섬 선착장 텍스트로 좁힌 별도 후보. |
| 호박 상인81123 | — / 32575,32950 | — | 상품 있음. `pump1` 자원 없음. |
| Lucas50015 | — / 32583,32922 | `lucas1`: `teleportURL`, `asknpctax`; `lucas2`: `island-gludin`, `island-dungeon` | 현재 텍스트가 텔레포터 루카스 명시. L1J `teleisland1/2`는 없으며 별도 native 후보로 기록. |
| Zeno50016 | — / 32600,32914 | — | `zeno/zeno2` 없음. 같은 위치 count0·count1 두 원행. |
| Keith50017 | — / 32577,32957 | — | `telefire1/2/3` 없음. |
| Dorin60001 | — / 32575,32946 | `dorinl` 거절; 공통 `storage`: `deposit`, `retrieve`, `deposit-pledge`, `retrieve-pledge`, `history` | `dorin/pdorin` 없음. `storage`는 공통 창고 자원 후보이며 Dorin 전용 연결은 미확정. |
| Selena70012 | — / 32596,32929 | `inn`: `room`, `hall`, `return`, `enter`; `inn1` 거절 | SQL caotic 원문 `Inn1`은 그대로 보존하고 native f2 후보는 정확한 `inn1`로 분리. |
| 라다르70523 | 300 / 32589,32957 | `ladar1` 동적 craft_output→`ladar2` craft_input/`request_craft`; `ladarC1` 거절 | 상품 shop 행 없음. 실제 제작 행·선택 키는 미공급. |
| Raidar70526 | — / 32593,32931 | — | `raiders1/raiders3` 없음. |
| Lavienue70524 | — / 32558,32965 | — | `lavienue9/lavienue2` 없음. |
| 라이엔70525 | 302 / 32575,32920 | `lien1` 동적 craft_output→`lien2` craft_input/`request_craft`; `lienC1` 거절 | 실제 제작 행·선택 키는 미공급. |
| Alchemist70520 | — / 32573,32936 | — | `alchemy1/alchemy4` 없음. |
| Jem70531 | — / 32587,32927 | `jem2` 텍스트 | 고정 action 없음. |
| Liri50111 | — / 32583,32935 | — | count0 비활성; `orenc14` 없음. |
| Kuper70099 | — / 32600,32920 | — | `kuper2` 없음. |
| 렝고70100 | 82 / 32575,32946 | `lengo1` 텍스트 | 고정 action 없음. |
| 휜70101 | 83 / 32575,32946 | `fiin1` 텍스트 | 고정 action 없음. |
| 쥬디스70102 | 84 / 32575,32946 | `judice1` 텍스트 | 고정 action 없음. |
| 모나70529 | 322 / 32575,32946 | `mona1` 텍스트 | 고정 action 없음. |
| Serian50112 | — / 32600,32916 | — | `orenb1/orenb0` 없음. |
| 혈맹 집행인 엘도린70538 | 984 / 32579,32922 | `bpledge2`: `create`; `bpledge1` 텍스트 | 초기/조건별 분기는 L1J 후보. |
| 시장 비서70534 | — / 32588,32952 | — | `secretary1/secretary4` 없음. |
| 마을 관리자70528 | — / 32588,32953 | — | `othertown/othertownh` 없음. |
| 경비60501 | — / 마을6배치 | — | template10/58/68 후보 유지; `patguard` 없음. |
| 경비60502 | — / 마을6배치 | — | template10/58/68 후보 유지; `patguard` 없음. |
| Unknown81200 | — / 32590,32934 | — | `nobelt` 없음. |
| Harbor Master81000 | — / 32652,32953 | — | count0 특수 객체; npcaction 행 없음. 배표 상인70011과 구분. |
| Oasis Stuff80001 | — / 32647,32950 | — | npcaction 행 없음. |
| 게시판80006 | — / 32578,32941 | — | npcaction 행 없음. 대사 없는 객체를 상점으로 만들지 않음. |

JSON은 `npcs[]`에 template·위치·원 npcaction 네 열·추가 native 후보·shop 여부를, `resources[stem]`에 실제 f2 후보·UML 경로·메뉴 action·link·panel·동적 목록·현지화 키와 원문 줄을 둔다. `classic_template_id`는 catalog 대응이고 wire f39의 정당 값이라는 뜻은 아니다. `resources`의 lookup key는 L1J 원문을 유지할 수 있으므로 실제 전송 후보는 `f2_candidate`를 읽는다. 특히 `resources.Inn1.f2_candidate`는 `inn1`이다. `current_catalog_asset_path`는 catalog의 정규화 표기이며 원 constructed/decoded casepath와 구분한다.

직접 확보한 주요 근거는 다음과 같다. `catalog`는 `work/asset_data_analysis/current/catalog.tsv`, `dialogue`는 `work/local_resource_provider/assets/data/dialogue.csv`, 아래 UML 줄은 JSON `decoded_uml_root` 기준이다. 기존 catalog의 동일성 판정을 읽었으며 이번에 해시 계산·추출기를 실행하지 않았다.

| 확인 대상 | 정확한 값·근거 |
|---|---|
| Pandora 구매·판매 | `pandora.uml:10` Npc_Bt_Buy, :11 `buy`, :12 `sell`, :17 `asktax`, :18 `asknpctax`; catalog:1067. 텍스트 키 `pandora_2/3/4/10`은 dialogue:341/342/343/3335. |
| Cole 구매·판매 | `cold1.uml:10` panel, :11 `buy`, :12 `sell`; catalog:322, 텍스트 `cold1_2/3/4/10`은 dialogue:352/353/354/3337. |
| 말하는 섬 배표 메뉴 후보 | `ShipEvM3.uml:9` panel, :10 `buy`, :11 `sell`, :15 link ShipEvM4; catalog:1216. `ShipEvM4_1`은 dialogue:731에서 ‘이곳, 말하는 섬 선착장’ 명시. |
| 루카스 native 후보 | `lucas1.uml:8` teleportURL, :14 asknpctax; `lucas2.uml:8/9` 두 목적지 action, ui_close=true. catalog:845/846, `lucas1_1/2`는 dialogue:741/742에서 화자 루카스 명시. |
| 공통 구매 panel | `NpcTalk/Npc_Bt_Buy.csb`; catalog 정규화 key `npctalk/npc_bt_buy.csb`:4452, 기존 identical. 원 panel 경로 구성 근거는 run122 main-button-review다. |

`$N`은 `basename_N` 현지화 키로 연결한 content 대응이며 숫자 메뉴 ID가 아니다(`work/asset_data_analysis/tables/relationships.json:89`). `link`는 원 문서 연결로 보존하며 서버 action으로 자동 승격하지 않는다. 라다르/라이엔의 `craft_output`·`craft_input`과 `var craft`는 실제 동적 입력 생산자를 필요로 한다. 공통 창고/여관/혈맹 키의 회수는 서비스 구현 재개나 동결 해제가 아니다.

## 기존 SHOP 결과를 재사용할 때

| 자료 | 확보된 사실 | 이 대응표로 확대하지 않는 범위 |
|---|---|---|
| `menu-content-source-v1/RESOURCE_LOOKUP.md:9`, `menu-resource-stem-v1/INSTALL_API.md:5` | 실존 `pixel.uml`, panel `Npc_Bt_Buy`, action `buy`·`sell`, 현지화 `pixel_1`; 최신 f2는 `pixel` | 원 Pixie·특정 마을 NPC의 identity→메뉴 대응은 `PIXEL_NPC_SOURCE.md:3`에서 OPEN이다. |
| `merchant-source-input-v1/API.md:28` | SPR1552 auction board를 LOCAL merchant-board로 선택, pixel/buy·가격3 등 명시 로컬 정책 | Pandora·Cole 등 공식 상인 대응이나 원 서버 가격이 아니다. |
| `integration-1/shop-operating-input-343/root-input-policy.json:30` | LOCAL UID10001, map0 `(32578,32945)`, 이름 Local merchant board | 이 UID/좌표/catalog_npc1/rowkey101/context0을 마을 NPC 메뉴 ID로 복사하지 않는다. |
| `implementation-2/npc-motion-goal/packet-static-npc-navigation-v1/API.md:23` | NPC-STATIC-SHOP은 발행된 단일 LOCAL SHOP의 위치 점유 정책. 위치는 NormalSpawn.fields[1] | NPC별 대사·상점 목록, 실제 원본 NPC identity, UI 성공의 근거가 아니다. |
| `integration-1/shop-human-manual-serial396-v8/API.md:3` 및 SHOP `HANDOFF.md:1070` | v7 실제4E43 뒤 길이 검사 실패; v8은 trailer_length를 포함하는 수정과 실제 inventory/current 경계 실패·강제 정리 | v8의 메뉴·BUY 성공은 미확인이다. 코드 span 수정과 실제 메뉴 성공을 합치지 않는다. |
| SHOP `HANDOFF.md:1069` | 별도 v9 사람 NPC 클릭→RX4E43/TX4E44→RX4ED4/TX4E48 31B 관측 | 목록 소비·실4ED1/BUY/CAS·현재 마을 NPC별 대응·정상 종료는 입증하지 않는다. native0xC0000005와 broker/cleanup 오류가 남았다. |

위 표의 `integration-1/`·`implementation-2/`는 `work/local_original_session/` 기준이고 SHOP HANDOFF는 `work/local_original_session/implementation-4/shop-quest/HANDOFF.md`다. v9의 부분 성공은 v8의 실패 기록을 덮어쓰지 않는다. 원본 정상 메뉴 연결 순서는 **NPC 현재 UID → 4E43 → 4E44 stem/현재 메뉴 → 실제 action 4ED4 → 4E48 또는 4EE7 → 목록 context/row·수량 → 4ED1 → 기존 거래·저장**이다.

## 검증과 남은 범위

지정 Python `C:/Users/Chansol/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe -X utf8 -B -`에 일회성 stdin 코드를 전달해 UTF-8 JSON 재읽기·참조·31 unique NPC·42배치·count0 보존·마을 경계를 확인했다. 통합 검토에서는 Pandora/Lucas/여관/제작의 보존 UML 원문과 현재 현지화·catalog 줄을 읽고, 정확 native `inn1`과 SQL `Inn1`의 분리를 수정했다. 이번 데이터 전용 변경에 대응하는 기존 시험 모듈은 없어 무관한 broker/game suite를 실행하지 않았다. 임시폴더 권한 오류는 발생하지 않았다.

새 검사기·guard·pin·해시 검사·요청 처리 중 파일 읽기/대기는 추가하지 않았다. 제품이 이 파일을 로딩하도록 연결하는 작업, 실제 NPC 생성·창 표시·버튼 입력·상점 거래와 30분 플레이는 이번 범위 밖이며 **UNRUN**이다. 회수된 구매/판매 literal은3 NPC의 메뉴 후보에 연결되며, 나머지 상품 상인인 호박 상인은 원 자원 키가 미확보다. 메뉴 파일명 부재, template 식별 부재, 실제 UI/목록 소비 미확인을 각각 JSON에 남겼다.

## REA 결과: NPC 대화창·상점 열기 메뉴 값 (run382)

2026-10-26 사용자 지정 정적 조사 결과다. **숫자 메뉴 ID를 채우는 작업은 필요하지 않다. 4E44는 서버가 지정한 UML stem을 받고, fallback 메뉴 요청 4ED4는 action 문자열을 보낸다.** `npc_menus.json`은 수정하지 않았다. 아래는 원 자원 값과 로컬 연결 제안이며, 공식 서버의 NPC별 메뉴 발급 조건이나 실제 화면 성공을 확정한 표가 아니다. 이번 쓰기는 이 결과 절과 `work/local_server_rea_20261016/run382_npc_dialog_menu/`뿐이다. 현재 `main`의 기존 dirty 파일은 보존했다. 게임·서버·포트·provider·원본 실행과 git commit은 하지 않았다.

### 수신·버튼·목록을 연결한 정적 사실

| 접점 | 확인한 동작 | 근거 |
|---|---|---|
| 4E44 대사 선택 | `306A40 → 17FC040 → 5CCEB0`. required f2를 받아 `data/uml/` + f2 + `.uml`을 구성한다. NPC ID에 따라 클라이언트가 별도 stem을 고르는 switch는 이 경로에서 확인되지 않았다. `pandora`, `cold1`, `ShipEvM3`처럼 확장자 없는 정확 stem이 입력이다. | `run122_dialogue_resource_link/main-filename-review.json:19`; `run382_npc_dialog_menu/handler_trace.md`의 4E44 절 |
| 문맥·부가 데이터 | f1 int32가 UML+38에 들어가고 Actor lookup에는 sign-extend된다. f3는 별도 UML+70/payload+30이며 f2 파일명과 다르다. f4 signed64 배열은 UML+A8, f5 문자열 배열은 `339AB0` 경유 UML+90에 들어간다. f3를 HTML이나 NPC 메뉴 번호, f4 원소를 action ID로 확정할 근거는 없다. | `run106_shop_dialog_contract/worker/body-5cceb0.json:973`, `:1714`; `run120_dialogue_string_args/worker/packet.json:16`; `run382_npc_dialog_menu/handler_trace.md` |
| 대사 표시 진입 | `5CC3A0 → 12AA50(owner,4,entryData)` 성공과 후속 `5CE490` 자원/UIData 조회가 필요하다. operation4는 ContentEntry 동작 번호다. GameState4·Scene4라는 뜻은 아니다. | `run106_shop_dialog_contract/worker/body-5cc3a0.json:218`; `run106_shop_dialog_contract/trade_source/packet.json:180` |
| 버튼 dispatch | `A51BF0`는 action의 exact 문자열을 UML+168 map에서 먼저 찾고, 미발견일 때 `haction`으로 보낸다. 정상 initializer `5CA3E0`의 29개 키에는 exact `buy`/`sell`이 없다. `buy_user_shop`/`sell_user_shop`는 별개 키다. 따라서 이 초기 map에서는 두 메뉴가 fallback으로 연결된다. 실행 중 map 추가·교체 여부는 미관측이다. | `run122_dialogue_resource_link/worker/body-a51bf0.json:1267`; `run382_npc_dialog_menu/handler_registration_keys.tsv:2` |
| 실제 4ED4 값 | 등록된 UMLEvent_HACTION의 `5C3E90 → 5C3CE0 → 27D620(4ED4)`. f1은 현재 UML+38, f2는 event+20 문자열 그대로다. 숫자 모양 문자열도 int/enum으로 바꾸지 않는다. f3는 resolved cookie가 nonempty일 때만 포함한다. 정상 f4/f5 좌표는 둘 다 present이고 좌표 flag가 없으면 0/0이다. | `run106_shop_dialog_contract/worker/body-5c3ce0.json:97`, `:234`, `:332`, `:572`; `run106_shop_dialog_contract/haction-menu-main-review.json:35` |
| 구매 목록 열기 | 4E48은 `3065F0 / 17FC280 → 58F8E0`. `12AA50(owner,3,entryData)` 성공 뒤 Shop active/context/rows를 채우고 원 NPCShopLayout의 구매 command를 dispatch한다. | `run106_shop_dialog_contract/trade_source/body-58f8e0.json:418`; `run382_npc_dialog_menu/handler_trace.md`의 목록 절 |
| 판매 목록 열기 | 4EE7은 `2FDED0 / 1800900 → 58E980`. 같은 ContentEntry operation3 성공 뒤 판매 context/rows와 원 UI를 처리한다. 이 operation3도 GameState3·Scene3 검사가 아니다. | `run106_shop_dialog_contract/trade_source/body-58e980.json:439`; `run106_shop_dialog_contract/trade_source/packet.json:180` |

**목록을 여는 클라이언트 조건은 정당한 목록 응답의 수신과 원 ContentEntry/UI 소비 경로다.** 선택된 두 수신 handler가 앞선 `buy`/`sell` 문자열, UML+38 또는 처음 클릭 UID를 비교해 창을 허용하는 것은 확인되지 않았다. 그러므로 `buy`라는 문자열만 보내면 언제나 4E48이 돌아온다는 공식 서버 규칙은 클라이언트 정적 분석으로 확정할 수 없다. 로컬 연결 제안은 현재 NPC·세션·발급 메뉴와 실제 action을 기존 권위 계약으로 연결한 뒤 `buy → 4E48`, `sell → 4EE7`을 명시적으로 선택하는 것이다. 메뉴 f1·목록 context·상품 rowkey는 서로 다른 역할이며 자동 동일값으로 만들지 않는다. 목록 필수 필드와 실제 행/자원 공급·화면 소비까지 갖춰야 한다. 메뉴 stem만으로 이를 대신하지 않는다.

### NPC별 제안 값 표

아래 `4ED4.f2`는 **정상 초기 map에서 fallback인 action**만 적었다. 모든 행의 별도 숫자 메뉴 ID는 계속 `null`이다. f1은 발급한 메뉴의 int32 context echo이며 상수 NPC template·L1J ID를 넣는 칸이 아니다. f3 cookie는 실제 event 값을 보존한다. 아래 UML에는 cookie 속성이 없지만 parent-data가 event 값을 바꿀 수 있으므로, 이를 모든 실행에서 빈 문자열이라는 뜻으로 확대하지 않는다.

| NPC / L1J ID | 4E44.f2 제안 | 4ED4.f2 제안 / local command 예외 | 목록·대응 판정과 원문 |
|---|---|---|---|
| Pandora70014 | `pandora` | `buy`, `sell`, `asktax`, `asknpctax` | 구매/판매 연결 제안 4E48/4EE7. `pandora.uml:10–18`; 거절 `pandora2`와 L1J 미확보 `pandora5`의 조건을 합치지 않음. |
| Cole70013 | `cold1` | `buy`, `sell`, `asktax`, `asknpctax` | 구매/판매 연결 제안 4E48/4EE7. `cold1.uml:10–17`; `cold2`는 별도 거절 자원. |
| 항구 배표 상인70011 | `ShipEvM3` | `buy`, `sell` | 구매/판매 연결 제안 4E48/4EE7. `ShipEvM3.uml:9–15`; `ShipEvM4`는 link 목적지로 별도 보존. NPC identity/조건별 발급은 후보. |
| 호박 상인81123 | **미확정** (`pump1` 미확보) | **미확정** | 상품 행이 있다는 이유로 다른 NPC의 `buy`/`sell` 또는 stem을 복사하지 않음. |
| Lucas50015 | `lucas1` → 후속 후보 `lucas2` | `teleportURL`, `asknpctax`; 후속 `island-gludin`, `island-dungeon` | `lucas1.uml:8,14`, `lucas2.uml:8–9`. 초기 map에서는 fallback이나 공식 후속 조건·teleport 결과는 미확정. 목적지 두 action은 ui_close=true. |
| Zeno50016 | 미확정 (`zeno/zeno2` 미확보) | 미확정 | 현재 자원 근거 없음. |
| Keith50017 | 미확정 (`telefire1/2/3` 미확보) | 미확정 | 현재 자원 근거 없음. |
| Dorin60001 | `dorinl`은 거절; `storage`는 **공통 후보** | 공통 후보 `deposit`, `retrieve`, `deposit-pledge`, `retrieve-pledge`, `history` | `storage.uml:9–15`; Dorin 전용 대응/발급 조건 미확정. 상점 목록으로 치환하지 않음. |
| Selena70012 | `inn`; 거절 후보 `inn1` | `room`, `hall`, `return`, `enter` | `inn.uml:9–12`. `room/hall`은 UML+44 설정 후 같은 HACTION sender로 감. SQL `Inn1`과 정확 stem `inn1` 구분. |
| 라다르70523 | `ladar1` → link `ladar2` | **`request_craft`는 등록된 local command** | `ladar1.uml:8`, `ladar2.uml:8–9`. 동적 craft_output/input·craft 선택값 생산 미확정. 이 literal을 4ED4로 직접 보내는 제안은 하지 않음. |
| Raidar70526 | 미확정 (`raiders1/raiders3` 미확보) | 미확정 | 현재 자원 근거 없음. |
| Lavienue70524 | 미확정 (`lavienue9/lavienue2` 미확보) | 미확정 | 현재 자원 근거 없음. |
| 라이엔70525 | `lien1` → link `lien2` | **`request_craft`는 등록된 local command** | `lien1.uml:8`, `lien2.uml:8–9`. 동적 입력·후속 wire는 이 조사에서 확정하지 않음. |
| Alchemist70520 | 미확정 (`alchemy1/alchemy4` 미확보) | 미확정 | 현재 자원 근거 없음. |
| Jem70531 | `jem2` | 고정 action 없음 | 텍스트 자원만 확인. |
| Liri50111 | 미확정 (`orenc14` 미확보) | 미확정 | count0 비활성 배치 보존. |
| Kuper70099 | 미확정 (`kuper2` 미확보) | 미확정 | 현재 자원 근거 없음. |
| 렝고70100 | `lengo1` | 고정 action 없음 | 텍스트 자원만 확인. |
| 휜70101 | `fiin1` | 고정 action 없음 | 텍스트 자원만 확인. |
| 쥬디스70102 | `judice1` | 고정 action 없음 | 텍스트 자원만 확인. |
| 모나70529 | `mona1` | 고정 action 없음 | 텍스트 자원만 확인. |
| Serian50112 | 미확정 (`orenb1/orenb0` 미확보) | 미확정 | 현재 자원 근거 없음. |
| 혈맹 집행인 엘도린70538 | `bpledge2`; 텍스트 `bpledge1` | **`create`는 등록된 local command** | `bpledge2.uml:9`. 등록 map의 exact key이므로 곧바로 HACTION/4ED4라고 할 수 없음. |
| 시장 비서70534 | 미확정 (`secretary1/secretary4` 미확보) | 미확정 | 현재 자원 근거 없음. |
| 마을 관리자70528 | 미확정 (`othertown/othertownh` 미확보) | 미확정 | 현재 자원 근거 없음. |
| 경비60501 | 미확정 (`patguard` 미확보) | 미확정 | NPC별 template/배치 후보와 메뉴 값은 별개. |
| 경비60502 | 미확정 (`patguard` 미확보) | 미확정 | NPC별 template/배치 후보와 메뉴 값은 별개. |
| Unknown81200 | 미확정 (`nobelt` 미확보) | 미확정 | 현재 자원 근거 없음. |
| Harbor Master81000 | 미확정 (npcaction 행 없음) | 미확정 | count0 특수 객체. 배표 상인70011과 구분. |
| Oasis Stuff80001 | 미확정 (npcaction 행 없음) | 미확정 | 대사/상품 역할을 새로 부여하지 않음. |
| 게시판80006 | 미확정 (npcaction 행 없음) | 미확정 | 게시판을 상점으로 대체하지 않음. |

UML 원문 줄은 JSON `reference_paths.decoded_uml_root` 기준이다. 이번에 해당 보존 UML25개를 직접 읽었으며 고정 action26회/고유18개 중 숫자 literal은 없었다. 초기 map와 고유18개의 교집합은 `create`, `request_craft` 두 개뿐이다. 따라서 원 markup의 action 속성 전부를 4ED4 송신값으로 일괄 취급하면 두 local command를 잘못 연결한다. 등록 근거는 `handler_registration_keys.tsv:5`의 create와 `:7`의 request_craft이며 전체29개도 같은 파일에 보존했다.

`$N → basename_N`은 대사 텍스트의 content 대응이다. 예를 들어 `pandora.uml:6`의 `$2`는 `dialogue.csv:341`의 `pandora_2`, `$4`는 `:343`의 `pandora_4`와 대응한다. 이것은 메뉴 번호가 아니다. 구매 버튼은 `pandora.uml:11`의 literal `buy`다. 기존 `relationships.json:89`도 이 관계를 content ID match로 한정한다. **native locale/치환 consumer의 전체 연결은 이번 정적 근거에서 미확정**이며, 텍스트 대응과 실제 표시를 구분한다.

### 상점 조건의 출처와 미확정

로컬 L1J 참고 소스 `D:/SingleLineageRef/l1j-en-classic/src/l1j/server/server/clientpackets/C_NPCAction.java:168`에는 거리 제한, `:213`에는 XML action 우선 처리, `:227` 이후에는 buy/sell 및 상점 disable/전용 NPC 분기가 있다. 다만 `buy → S_ShopSellList`(:240), `sell → S_ShopBuyList`(:283)처럼 **클래스 이름의 관점이 다르다**. 실제 전자는 `serverpackets/S_ShopSellList.java:86,96`에서 SHOWSHOPBUYLIST·상인의 getSellingItems를 사용한다. L1J 클래스명이나 자체 opcode를 Classic 4E48/4EE7·숫자 메뉴 ID로 복사하지 않는다. 이 소스의 거리·거절·제작 분기는 L1J backend 참고일 뿐 Classic 공식 서버 규칙으로 채택하지 않았다.

기존 사람 입력 v9의 RX4E43→TX4E44→RX4ED4→TX4E48 31B는 재사용하되, 그 LOCAL merchant/pixel 경로를 위 마을 NPC31종의 성공으로 확대하지 않는다(`implementation-4/shop-quest/HANDOFF.md:1069`). 당시 native0xC0000005와 broker/cleanup 오류·목록 소비 미확인은 보존한다. 정확한 f1/f2·실행 시점의 action map·cookie·행/자원·NPC별 서버 분기와 현재 화면은 이번 실행 금지 범위에서 확인할 수 없었다.

### 사용자 화면 실험안 (미실행)

후속 게임 실행이 허용되는 별도 단위에서 기존 owned non-input desktop/Job·정상 입력 경로로 Pandora, Cole, 배표 상인을 한 명씩 확인한다. 각 NPC의 정상 선택→4E43 UID→4E44 f1/f2와 **실제 대사창**을 함께 기록하고, 구매·판매를 순서대로 한 번씩 선택해 실제 4ED4 f1/f2/f3와 뒤따른 4E48/4EE7 및 **구매/판매 목록 화면**을 대응한다. 두 번째 NPC로 전환할 때 메뉴 context가 바뀌는지도 함께 확인한다. 거절/빈 목록/메뉴 미표시는 결과 그대로 남긴다. 창이 보이기 전의 수신 성공이나 과거 pixel 시험은 화면 성공의 대체 근거가 아니다. 이 실험은 이번에 실행하지 않았다.

상세 함수/RVA·재사용 source identity·정확 원문 위치는 [run382 handler_trace](../../local_server_rea_20261016/run382_npc_dialog_menu/handler_trace.md), 등록키는 [handler_registration_keys.tsv](../../local_server_rea_20261016/run382_npc_dialog_menu/handler_registration_keys.tsv)에 있다. 새 guard·검증 도구·큐 항목은 만들지 않았다.

## REA 결과: 구매·판매 목록과 확정 요청 필드 (run388)

2026-10-26 사용자 지정 정적 분석. **SELL4EE7 row.f2는 선택 개수당 매입 단가로 소비된다.** 기존 v38/API의 native 의미 UNKNOWN을 이 한정 소비에 대해 보완했다. `5914B7`이 derived row+10 선택수량을 읽고, `5914BF`가 copied SellRow+1C(f2)와32bit 곱, `5914C4`가32bit 합을 수행한다(`run128_shop_buy_row_display/worker/body-591380.json:523`, :535, :541). 공식 서버의 가격·세금·재고 정책이나 화면 성공을 확정한 결과는 아니다.

| 접점 | 확정된 필드와 소비 | 남은 경계 |
|---|---|---|
| BUY4E48 outer | required f1:i32/f2:i32, repeated f3. f1은4ED1 context의 low32 echo이며 f2는 CommonItem 조회 key→catalog+D0 UI reference다. | outer2의 정상값·화폐 등 업무 의미는 미확정. BUY5905A7과 SELL58F5C6 모두 lookup 뒤 null guard 없이+D0를 읽으므로0을 기본값으로 넣지 않는다. |
| BUY row | required f1:i32 rowkey, f2:i32 CommonItem/template key, f3:i32 icon decimal+`.png`, f4:u32 선택단위당 표시가격, f5:string 표시문자열, f6:i32/f7:u64/f8:i64. optional f9 repeated ItemDescription, f10:i32/f11:bool style. | f6/7/8은 required·복사만 확정이며 stock·한도·pack·flags 역할과 정상값 producer UNKNOWN. f7을 선택수량으로 쓰지 않는다. |
| SELL4EE7 row | required f1:i32/f2:u32. f1은 sign-extend Inventory UID lookup 및4ED1 rowkey echo, f2는 단가다. template·이름·수량·style은 기존 Inventory Item에서 가져온다. | list에 독립 icon/token/quantity 필드가 없다. lookup 실패의 원 fallback을 모든 list 앞 Inventory 강제 순서로 바꾸지 않는다. |
| 확정4ED1 C2S | required f1:u32 list-context echo/f2 enum BUY5·SELL6, repeated f3 `{required f1:u32 rowkey,f2:u64 quantity}`, 정상 writer는 명시 f4/f5:i32 좌표. 선택수량은 양수i32이며 null/both-zero 좌표=-2/-2. | 원 send→즉시5910E0 close이며 ACK 대기가 없다. 동일4ED1 S2C 성공응답 근거는 없으며 만들지 않았다. |
| 거래 후 LOCAL 통지 | 기존 backend commit 뒤 projection이 기존UID 수량은0965, 새UID는 완전한0964 ItemInfo, 소진 제거는0978로 투영한다.0965는 outer f1 repeated ItemInfo `{f1:UID u32,f4:newQuantity u64}`다. | 공식 서버 순서·응답 ACK와 별개다. 현재 유효 UID·정당 funds·실거래·저장·화면은 미관측. |

SELL 단가의 추가 경로는 `run106_shop_dialog_contract/trade_source/body-58e980.json:2598`의58F09B→descriptor+18, :2892의58F16E→593C80→derived row+18이다. 같은 함수:2549의 Item+10 template, :2563의 Item+8 UID, :2584의 Item+28 lowDWORD quantity, :2626의50A220 이름 문자열과 연결된다. 위 BUY 표시·수량 소비는 REA128/244를 재사용했다. **UI 선택수량은 별도 row+10이며, 해독된 pack_count 필드는 없다.** f6/7/8에 pack 의미가 전혀 없다는 전역 부재 증명은 아니다. `world_shop.py`의 L1J 선택묶음×effective pack 정책과 원 wire 의미는 구분한다.

### Pandora 빨간 물약10개 frame 예시와 한계

`M2_SHOP_DATA.md:50`의 Classic **후보** item14/token`$237`/icon80, L1J 판매37·매입19/effective pack1을 명시 LOCAL 정책 예시로 썼다. 원 Pandora의 Classic template·공식 가격·현재 live UID는 미확정이다. 실제 예시 바이트·BODY/전체 plaintext frame의 구별은 [frame_examples.json](../../local_server_rea_20261016/run388_shop_list_contract/frame_examples.json)에 있다. 모든 N/context/row/Inventory UID·시작 보유량·sequence 숫자는 **임의 교육용 값**이며 실제 발급값이나 실행 관측이 아니다.

1. C2S4E43 `{1:N}` → S2C4E44 `{1:D,2:"pandora"}` → C2S4ED4 `{1:D,2:"buy",4:0,5:0}`.
2. S2C4E48 `{1:C,2:H,3:[{1:R,2:14,3:80,4:37,5:"$237",6:A,7:B,8:E}]}`. **H/A/B/E는 정당 producer 입력을 받아야 하는 파라미터**다. 해당 완성 frame hex는 null로 보존했으며 미확정 필드를0으로 채우지 않았다.
3. 예시 C=43/R=101에서 정상 수량10 선택 후 C2S4ED1 `{1:43,2:5,3:[{1:101,2:10}],4:-2,5:-2}`. BODY32B는 아래와 같다. plaintext frame42B는 C2S header `2a 00 01 00 00 00 d1 4e 20 00` 뒤 이 BODY다.

```text
08 2b 10 05 1a 04 08 65 10 0a 20 fe ff ff ff ff ff ff ff ff 01 28 fe ff ff ff ff ff ff ff ff 01
```

이 LOCAL 정책이 정상 commit됐다고 **가정한 경우에만** 370아데나 debit·물약10 credit이다. 예시 JSON의 wallet1000→630/기존물약3→13은 SC0965 두 개로 표현했으며 실제 성공응답이 아니다. 새 UID라면 source-issued 완전한0964가 필요하다. 기존 transport의 C2S sequence/body-length/alignment와 S2C length/opcode/body/0000 framing을 재사용했고 실제 암호화 송신은 하지 않았다. 실제 context/row/UID·가격·상품과 미확정 header/row678을 예시 숫자로 대신해 실행할 권한이나 근거는 없다.

### 판정과 최소 화면 실험안

판매10개도 기존 [frame_examples.json](../../local_server_rea_20261016/run388_shop_list_contract/frame_examples.json)의 `sell_frames`에 보완했다. 예시4EE7 `{1:44,2:H_sell,3:[{1:287454037,2:19}]}`는 header producer 미공급으로 완성 hex가 null이다. 뒤4ED1은 context44/mode6/Inventory UID`0x11223355`/수량10/-2,-2이며 BODY36B·plaintext frame46B를 기존 codec roundtrip으로 확인했다. 정상 LOCAL commit을 **가정한** 매입190·wallet630→820·물약13→3의0965 예시일 뿐 실제 응답·공식 가격·거래 성공이 아니다. 원문244/249를 재대조했으나 BUY f6/7/8과 outer2의 정상 producer를 닫는 새 근거는 없어 UNKNOWN을 유지했다. 새 도구·보고서·REA session은 만들지 않았다.

정적 확정은 schema·단가 연산·목록/요청 echo·원 close·기존 LOCAL projection까지만이다. Pandora의 실제 목록 표시·수량 버튼/합계·4ED1·아데나/아이템 변화·저장/복원은 **UNRUN**이다. 최소 추가 입력은 정상 Pandora buy에 대응한 S2C4E48 한 건의 outer1/2·row1..8 및 NPC/입력/session/build/direction/ordinal이다. SELL도 정상 Inventory에 연결된4EE7 한 건이 필요하다.

향후 실행이 승인된 시험 worker 한 명이 owned non-input desktop/Job·시험 저장에서 정상선택→4E43→4E44 pandora 실제창→buy→4E48 이름/아이콘/가격→원 UI 수량10/합계370→4ED1→원 즉시close→실제 Inventory/아데나 변화→정상Quit·저장/fresh를 한 번 대응한다. 부족 재화·빈 목록·AV·미표시는 그대로 기록한다. 판매는 정상 sell→4EE7→수량/단가 합계→mode6에서 별도로 확인한다. 이번 정적 분석을 그 실행 PASS로 확대하지 않는다.

상세 계약·정확 Source 원문 줄·교육용 예시는 [run388 CONTRACT](../../local_server_rea_20261016/run388_shop_list_contract/CONTRACT.md), [source_excerpts](../../local_server_rea_20261016/run388_shop_list_contract/source_excerpts.md), [frame_examples](../../local_server_rea_20261016/run388_shop_list_contract/frame_examples.json)에 있다. 기존 pure codec을 `python -X utf8 -B`로 사용한 offline 계산이며 게임·서버·프로세스/메모리·포트·REA session·제품 수정·git commit은 하지 않았다. 새 guard·검증 도구·큐 항목도 추가하지 않았다.

## REA 결과: 서비스·퀘스트 NPC의 정확 stem과 action (run403)

2026-10-27 사용자 지정 정적 조사. 기존 run106/122/382, 위 대응표와 `data/m2/npc_menus.json`·`town_services.json`·`quests.json`에서 출발했다. **아래 확정은 보존 UML literal과 현재 대사 내용의 대응이다. NPC별 공식 서버의 메뉴 발급·조건 분기·실제 화면은 미확정이다.** 결과는 이 절과 `work/local_server_rea_20261016/run403_service_npc_dialogs/`에만 썼고 세 JSON·서버 제품 코드는 수정하지 않았다. 게임·서버·포트·원본 실행·git commit·새 guard/검증 도구 추가는 하지 않았다.

아래 `U`는 `C:/Users/Chansol/Documents/Codex/2026-09-07/d-lineage-classic/outputs/decrypted-pack/data_0/data/uml/`, `D`는 `work/local_resource_provider/assets/data/dialogue.csv`, `C`는 `work/asset_data_analysis/current/catalog.tsv`다. `U/<stem>.uml`의 정확 대소문자를 보존하고 **4E44.f2에는 확장자를 뺀 stem**을 쓴다. catalog의 소문자 정규화 key나 L1J 원문 철자를 native stem으로 덮어쓰지 않는다. 아래 action 열은 XML literal이며 link·panel·변수는 별도다.

| NPC / 대응 수준 | 확인한 stem과 action literal | 문서·입력과 남은 경계 | 원문 근거 |
|---|---|---|---|
| 여관 주인 / Selena70012 연결 후보 | `inn`: `room`, `hall`, `return`, `enter` | `inn1..10`도 회수. `inn2`/`inn7`은 `NpcTalk_InputNum`·`custom=input_num_inn` 입력 panel이며 고정 action은 없다. Selena 이름은 문서에 고정돼 있지 않고 `var name`을 쓴다. | `U/inn.uml:9..12`; `U/inn2.uml:6,23`; `U/inn7.uml:6,23`; `D:223..228` |
| 텔레포터 루카스 / 대사가 화자 명시 | `lucas1`: `teleportURL`, `asknpctax`; `lucas2`: `island-gludin`, `island-dungeon` | 목적지 두 버튼은 `ui_close=true`, 가격 자리는 각각 `var 0`/`var 1`. L1J의 `teleport island-gludin`과 native literal은 다르다. `teleisland1/2`는 미확보. | `U/lucas1.uml:8,14`; `U/lucas2.uml:8,9`; `D:741..750` |
| 텔레포터 키스50017 / 화전민촌 주민 자원 후보 | `keith2`: `teleportURL`; `keith3`: `firefieldtown` | 새로 회수한 `keith1`은 link=`keith4`; `keith4`는 설명. 화전민촌 역할은 대사로 확인되지만 개인명 Keith·실제50017 귀속은 미확정. `telefire1/2/3` 부재를 이 자원으로 자동 대체하지 않는다. | `U/keith1.uml:12`; `U/keith2.uml:10`; `U/keith3.uml:8`; `D:751..767`; `C:797..800` |
| 텔레포터 Zeno50016 / 미확정 | 확보 stem/action 없음 | `zeno`/`zeno2`·native `singing-island`는 조사한 UML·대사·catalog에서 미회수. L1J `teleport singing-island`는 별도 참고 후보다. | [서비스 검색 경계](../../local_server_rea_20261016/run403_service_npc_dialogs/service_resources.md) |
| 창고지기 / Dorin60001 연결 후보 | 공통 `storage`: `deposit`, `retrieve`, `deposit-pledge`, `retrieve-pledge`, `history` | `storage_history`는 `dynamiclist custom=storage_history`와 link=`storage`; 고정 action 없음. `dorinl`은 초보자 거절 대사만 있고 악인 거절로 확정할 수 없다. `dorin`/`pdorin`은 미확보, 공통 storage의 Dorin 전용 발급도 미확정. | `U/storage.uml:9,10,13..15`; `U/storage_history.uml:4,7`; `U/dorinl.uml:8`; `D:916` |
| 말하는 섬 배표 상인 / 선착장 내용 대응 | `ShipEvM3`: `buy`, `sell` | link=`ShipEvM4` 시간표, 역방향 link=`ShipEvM3`. L1J70011의 `shipEvI3/I1`은 미확보이며 native NPC 신원·발급은 미확정. | `U/ShipEvM3.uml:10,11,15`; `U/ShipEvM4.uml:18`; `D:729,731` |
| 다른 항구 배표 상인 / 구분용 내용 대응 | 글루디오 `ShipEvM1`: `buy`, `sell`; 하이네 `forgottenship1`: `buy`, `sell` | 시간표 link는 각각 `ShipEvM2`/`forgottenship2`. `ShipEvM1`은 말하는 섬행, M3는 글루디오행이므로 뒤집지 않는다. L1J70022 `shipEvM1/M2`와 native `ShipEvM1/M2`의 첫 글자 case도 다르다. | `U/ShipEvM1.uml:10,11,15`; `U/forgottenship1.uml:10,11,15`; `D:717,719,2367,2369` |
| 젬 / 대사가 이름·연구 내용 명시, template 미확정 | `jem1`/`jem9`: `queststart`; `jem3`/`jem4`: `questcomplete`; 결과 `jem8`/`jem10`은 고정 action 없음 | 앞 교환은 구울 재료·미완성 마법서, 뒤 교환은 저주받은 마법서·해골 두개골·마력서. 별도 `jemw1`: `queststart`, `jemw4`/`jemw7`: `questcomplete`도 회수했으며 기존 두 의뢰와 합치지 않는다. | `U/jem1.uml:12`; `U/jem9.uml:10`; `U/jem3.uml:15`; `U/jem4.uml:13`; `U/jemw1.uml:14`; `U/jemw4.uml:9`; `U/jemw7.uml:9`; `D:474..513` |
| 군터 / catalog template26 이름 대응 | `gunterp1`: `queststart`; `gunterp10`: `questcomplete`; `gunterp11` 결과는 고정 action 없음 | p1 버튼의 대사는 ‘책략가 제로에 대해서’이므로 **생명의 비밀 직접 수락 stem으로 채우지 않는다**. 추가 exact `gunterkE1`: `queststart`, `gunterkE2`: `questcomplete`; 대문자 E 보존. 직업·진행 상태별 공식 발급은 미확정. | `U/gunterp1.uml:9`; `U/gunterp10.uml:12`; `U/gunterkE1.uml:9`; `U/gunterkE2.uml:8`; `D:570..581`; `work/source_game_data/native-dump-v1.jsonl:21` |

여관의 `inn1/3/5/6/8/9`는 같은 XML 골격이어도 stem별 현지화 뜻이 악인 거절·돈 부족·이미 대여·만실 등으로 다르다. 같은 markup이라는 이유로 통합하지 않는다. `inn2/7`의 인원 입력 consumer·뒤따른 요청, `inn10`의 환불액 `var 1`, 루카스의 목적지 가격과 창고 이력 행의 실제 생산자는 미확정이다. 여관의 방 대여 action을 `town_services.json`의 명시 LOCAL 100아데나/즉시 full회복 정책과 동일한 원본 서비스로 주장하지 않는다. 창고 `deposit→4ED2`/`retrieve→0971`의 기존 모델 대응도 공식 NPC의 실제 응답 관측과는 구분한다([WAREHOUSE_EVIDENCE](WAREHOUSE_EVIDENCE.md)).

### questcomplete의 전용 sender: 로컬 명령도 4ED4를 보낸다

`queststart`는 기존 initializer29키에 없어 원 generic HACTION fallback 후보다. `questcomplete`는 exact local command(`run382/handler_registration_keys.tsv:11`)여서 같은 fallback이라고 처리하면 안 되지만, **별도 handler 역시 opcode4ED4를 보낸다.** 기존 run106 `source_tool.py`와 보존 c822 실행영상을 재사용해 factory `5CF0D0`→event vptr `11CB788`→virtual+8 `5C5950`을 연결했다. `5C598B`는 UML+38 문맥, `5C59E6..5C59EE`는 event+20의 원 action 문자열을 복사하고 `5C5B0A`/`5C5B17`은 4ED4/27D620 전송을 지정한다. 원 local dispatch의 `A51ECC→A52A0E` action 복사는 `quest_native.json:1140` 이후의 기존 run122 원문 위치에 연결돼 있다. 새 근거는 [quest_native.json](../../local_server_rea_20261016/run403_service_npc_dialogs/quest_native.json)에 RVA·보존 입력 경로·기존 해시·선정 명령으로 남겼다. 이 보존 소스와 현재 실행 중인 원본의 동일성을 새로 입증한 것은 아니다.

이 handler는 nonempty event cookie를 그대로 보내지 않고 `DF660` 반환 AL로 만든 **길이1 문자열**을 f3에 복사한다(`5C5A16..5C5A28`, `5C5A93..5C5A9E`). DF660의 업무 의미는 미확정이다. 조사한 퀘스트 UML55개에는 cookie 속성이 없지만, 부모 데이터의 resolved cookie·실제 event 상태가 비어 있다는 실행 증거는 아니다. 가짜 quest ID·빈 cookie를 만들거나 generic sender의 raw-cookie 처리를 덮어쓰지 않는다. f4/f5는 기존과 같이 event 좌표 또는 명시0/0이다. 실제 UI 입력·전송·서버 처리·보상은 UNRUN이다.

### 자료 범위·미확정·사용자 화면 실험안

서비스 UML20개와 배표 family6개는 현재 catalog의 해당 key 전부와 대응하며 기존 비교값이 모두 `identical`이다. 퀘스트는 보존 UML55개(젬18·군터37)가 기존 `identical`이고, current catalog family56개 중 **`gunterp12.uml`만 `added`**다(`C:590`,195B). 이 key는 존재하지만 보존 decoded 원문은 찾지 못해 action/content를 확정하지 않았다. 현재 CSV의 일부 관련 대사나 다른 p문서의 복사본으로 p12 내용을 대신하지 않는다. `data/dialogue.csv` 자체는 기존 catalog에서 `changed`(`C:119`)이므로 보존 UML과 현재 대사 키의 대응을 구/현 CSV 전체 동일성으로 확대하지 않는다. 전체 원본 재해시·새 추출·게임 실행은 하지 않았다. UML의 `$N`·CSV 내부 inline `<a link=...>`·문서 링크와 숫자 메뉴 ID를 구별해 별도 보존했다.

상세 stem별 원문 줄·action/link/panel/변수·현지화·catalog 메타데이터·한정 부재 검색은 [service_resources.md](../../local_server_rea_20261016/run403_service_npc_dialogs/service_resources.md), [ship_resources.md](../../local_server_rea_20261016/run403_service_npc_dialogs/ship_resources.md), [quest_resources.md](../../local_server_rea_20261016/run403_service_npc_dialogs/quest_resources.md)와 각 동명 JSON에 있다. NPC별 live UID/실제 stem 발급, 클래스·레벨·성향·진행 상태 조건, 공식 요금·지도·회복·재료 수량·보상·저장 계약은 이번 자원 회수로 닫히지 않았다. Zeno의 미회수, Dorin/Selena/Keith/배표 상인의 identity 후보, 군터의 선행 의뢰와 생명의 비밀 수락 미확정을 유지한다.

**화면 실험안만 남기며 이번에 실행하지 않았다.** 후속 실행이 허용된 시험 worker 한 명이 기존 owned non-input desktop/Job·정상 저장에서 NPC 한 명씩 정상선택→4E43 UID→4E44 f1/f2→실제 창을 대응한다. 여관은 방/홀/반환/입장과 인원 panel, 루카스·키스는 목적지 목록/가격과 실제 action, 창고는 맡김/찾기/혈맹/이력 창, 배표는 현재 선착장/시간표와 buy/sell을 확인한다. 젬·군터는 정당한 직업/진행 상태·재료를 보존하고 수락과 완료 입력을 따로 대응하며 실제4ED4 f1/f2/f3·뒤따른 화면/서버응답·인벤·저장과 정상Quit/FIRSTclose를 기록한다. `gunterp1`을 생명의 비밀 직접 수락으로 강제하지 않고 거절·미표시·미전송·강제 정리는 실제 결과대로 남긴다.
