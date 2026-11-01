# M5 본토 마을

2026-10-27. 대상은 기존 본토 map4의 켄트·윈다우드·기란 및 추가 가능한 클래식 마을이다. 말하는 섬 M1/M2와 글루딘 M4를 보존하고 M5 확장 데이터를 시작 시 합친다. 이 작업은 사용자가 직접 지정한 M5 범위이며 과거 동결된 다른 기능·큐를 재개하지 않는다. 원본 클라이언트 실행·화면 캡처·사용자 저장 변경·git commit은 하지 않는다.

## 출처와 판정 범위

- 클라이언트 내부 자료의 이름·외형·지역 경계와 기존 추출 메뉴를 우선한다. Classic template, sprite, L1J NPC/item ID, 실제 Actor UID는 서로 다른 번호다.
- `tools/local_original_session/data/official/`의 공식 저장본을 재사용한다. 공식 몬스터·아이템 identity 및 지역·드롭 구성과, 공식 자료에 없는 가격·확률·수량·배치 정책을 구별한다.
- `D:/SingleLineageRef/l1j-en-classic`의 SQL·Teleport XML 등은 출처 있는 `local_policy` backend 참고다. 이 자료의 좌표·가격·리젠·귀환 규칙을 클래식 공식 관측으로 표시하지 않는다.
- 기존 [M4 자료](M4_GLUDIN_DATA.md), [M2 메뉴](M2_NPC_MENUS.md), [맵 전환 근거](MAP_TRANSITION_EVIDENCE.md), [기능 가이드](WORLD_FEATURE_GUIDE.md)의 형식과 판정 경계를 따른다.

`WorldTerrain.can_stand(4,x,y)`는 추출한 S32 static mask1에 대한 기존 통행 정책이다. 결과 True는 동적 점유·문·원본 전체 navigation 또는 화면 접근 성공의 증명이 아니다. 막힌 원행·미대응 identity·미지원 상품은 출처와 함께 보존해야 한다.

출처 비율은 NPC identity·공식 몬스터/아이템 identity·메뉴 resource·수치 정책을 각각 센다. 서로 다른 분모를 합친 단일 “원본 비율”은 사용하지 않는다. NPC 외형이 대응해도 위치·방향·상품·가격·서비스가 공식값이 되는 것은 아니다. 기존 추출 메뉴는 현재 catalog와 내용이 동일한지 구분하며, 변경된 메뉴의 과거 action 목록을 현재 원본 확인값으로 표시하지 않는다.

## 마을별 표

표 경로의 기준은 `tools/local_original_session/data/m5/`다. `town_npcs.json`은 외형 후보·이름·방향·좌표·원행·count0을, `shop_npcs.json`/`shop_sales.json`은 NPC별 판매·매입 품목과 원가격을 보존한다. `town_services.json`은 창고·여관·텔레포터 목록/요금과 미지원 항목을, `towns.json`은 지역과 귀환/사망 복귀 지점을 보존한다. 몬스터·주변 필드·드롭은 기존 표와 같은 `monsters.json`/`spawns.json`/`drops.json` 형식이다.

| 마을 | 클라이언트 region | NPC 원배치 / 고유 NPC | 창고 L1J ID | 여관 L1J ID | 귀환·사망 복귀 map4 좌표 | 필드 그룹 |
|---|---|---:|---|---|---|---:|
| 켄트 | 152 | 19 / 19 | 60003 | 마을 경계 안 출처 배치 없음 | 33050,32782 | 4 |
| 윈다우드 영지 우드벡 | 147,148 | 26 / 20 | 60023 | 70070 | 32640,33203 | 4 |
| 기란 | 160,161 | 109 / 95 | 60008,60009 | 70031 | 33438,32796 | 4 |
| 오렌 | 168 | 26 / 25 | 60021 | 70065 | 34062,32278 | 2 |
| 하이네 | 164,165,166 | 62 / 44 | 60030 | 70084 | 33612,33257 | 4 |

고유 NPC는 여러 마을에 반복될 수 있어 마을별 수를 합치지 않는다. 윈다우드의 서비스 마을은 클라이언트 우드벡 지역을 사용하며, 성 region111이나 넓은 사막 필드를 마을로 합치지 않는다. 고정 귀환점은 L1J silver 목적지를 선택한 LOCAL 정책이며 Classic GetBack 관측이 아니다.

| 출발 텔레포터 / 현재 메뉴 | 지원 목적지와 기본 A 요금 |
|---|---|
| 켄트 50020 / stanley2 | 글루딘50, 기란50, 은기사50, 아덴180, lawful200, chaos200 |
| 우드벡 50054 / trey2 | 글루딘50, 은기사50, 아덴180 |
| 기란 50036 / wilma2 | 켄트52, 하이네52, 화전민52, 오렌126, 아덴126 |
| 오렌 50051 / kirius2 | 화전민50, 기란120, 아덴240 |
| 하이네 50066 / riol2 | 기란50, 은기사50, 화전민120, 아덴50 |

글루딘50024의 `steve2`에 있는 `gludin-kent`는 55A다. 요금은 XML의 사용 가능한 분기 중 최소 원가격을 선택한 LOCAL x1/세금0 정책이다. 원본의 성향·세금·조건과 같다는 뜻이 아니다. 현재 목적지 메뉴를 NPC 클릭에 직접 연결하는 것도 LOCAL 대응이다. 다른 지역으로 가는 항목이 그 지역의 NPC·서비스 구현 완료를 뜻하지 않는다.

현재 메뉴29개(텔레포터6·storage·inn·상점21)는 기존 AssetProvider로 현재 catalog의 자원을 읽어 `uml/`에 보존했다. `npc_menus.json`에 asset 경로·판독 metadata와 실제 action을 남긴다. 과거 목적지 메뉴와 달리 아덴 항목이 있어 이전 변수 번호를 재사용하지 않는다. 켄트 상인70018에는 현재 `ysorya1`을 연결한다.

## 데이터의 출처별 수량과 지형

184종 NPC / 242배치의 현재 데이터는 catalog template19종, 선택 외형132종이다. 선택 외형은 직접 client 대응27종과 LOCAL/추론 선택105종으로 나뉘며, 미선택은52종이다. 1차의 template18종·외형21종과 후속 선택94종 기록은 각 당시 범위로 보존한다. 이번 90종 재검토에서는 LOCAL L1J 참고 외형38종을 추가했으며 신규 client template identity 확정은0종이다. 이를 원본 NPC 외형132종 확정으로 표시하지 않는다. 상점 3,276원행 중 기존 검토 item 대응을 재사용한 행은 324/3,276(약9.9%)이며, 이는 모두 런타임 거래가 가능하다는 비율이 아니다. 가격·배치·방향은 L1J 참고와 LOCAL 정책이다. 현재 메뉴 본문29/29는 클라이언트 자원이며 NPC와 그 메뉴를 연결하는 판단은 별도다.

NPC 원중심은 S32 통행 True212/False30/UNKNOWN0, count0은4행이다. 원좌표를 고쳐 숨기지 않고 통행 불가 중심·count0을 런타임 배치에서 제외한다. 실제 randomx/y 배치도 기존 TownNpcs 통행 판정을 사용한다. 반환점5개 모두 True다. 필드는18그룹/각2마리, 7×7칸씩882개 검사에서 모두 True이며 마을 경계 밖에 둔다. 원스폰 중심 주변20칸 안에서 정적 통행 가능한 작은 영역을 선정한 LOCAL 축소 정책이다.

상점 NPC 표는24종이며, 글루딘을 포함한 텔레포터6개의 지원 map4 action은25개다. 창고6종의 기존 정책은 최소레벨5·개인150칸·무료 입고·출고 UID당30A를 재사용한다. 몬스터11종과 실행 드롭38행/미확정 원행88개는 기존 M1/M3/M4의 출처 있는 정의를 재사용한다. 공식 identity·지역/드롭 구성과 L1J 수치·확률·수량의 경계를 그대로 유지하며 다른 Source의 과거 PASS를 가져오지 않는다. 신규 공식 API 조회를 수행한 결과로 표시하지 않는다.

| parser가 소비하는 출처 표기 셀 | client | official | L1J | LOCAL | 합계 |
|---|---:|---:|---:|---:|---:|
| 몬스터 | 66 | 11 | 110 | 11 | 198 |
| 스폰 | 36 | 0 | 18 | 54 | 108 |
| 드롭 | 38 | 0 | 31 | 7 | 76 |
| 해당 셀 합계/비율 | 140 / 36.65% | 11 / 2.88% | 159 / 41.62% | 72 / 18.85% | 382 |

이 셀 집계에는 NPC·상점·서비스·UML 본문을 넣지 않았다. 필드별 출처 비율이며 제품의 원본 동등성 비율이 아니다. `uml/pandora.uml`은 준비 초기에 보존한 미참조 자원으로 runtime metadata29개에 포함하지 않는다.

## NPC 이름·외형·HTML 정적 보완

2026-10-28 데이터 전용 검토다. 기존 `native-dump-v1.jsonl`의 NPC951행, `current-parsed.jsonl`의 SPR 헤더, `desc.csv`·`dialogue.csv`·`string.csv`, 현재 catalog와 기존 보존 UML을 재사용했다. 원본·서버·포트는 실행하지 않았으며 원 NPC184종·배치242행·count0·좌표·방향·원 npcaction·상품·가격을 보존했다. 변경 파일은 `town_npcs.json`, `shop_npcs.json`, `npc_menus.json`과 본 문서다. `build_data.py` 등 코드는 바꾸지 않았다.

NPC의 `$N` 이름은 **desc.csv**에서 읽는다. 예를 들어 `$459`는 `desc.csv:460`의 `잡화상^이소리야`이며, 같은 번호의 `string.csv:460`은 갑옷 인챈트 안내다. `string.csv`를 NPC 이름 표로 사용하지 않았다.184종 중 placeholder가 아닌 desc 이름은130종이며 이름만 확인된 항목을 template·외형 확정 수에 합치지 않았다. `dialogue.csv`의 `NPC_NAME` 열은 보존본 전체가 비어 있어 화자 join 근거가 되지 않는다. 이름·번호만 같거나 공유 외형·공통 여관/아지트 대사만 있는 항목은 미확정으로 남겼다.

| L1J NPC / 표시명 | 선택한 Classic template / SPR | 직접 근거와 한계 |
|---|---|---|
| 70545 Richard / 리차드 | 947 / 147 | `native-dump:510`의 유일 `$2160`·리차드, `desc.csv:2161`. L1J 외형148 대신 현재 native f2=147을 사용하며 원행은 보존. `richard3`는 catalog:1134와 dialogue:2406/2407의 자원 후보 |
| 70776 Mack / 맥 | 948 / 147 | `native-dump:511`의 유일 `$2161`·맥, `desc.csv:2162`. L1J 외형148 대신 현재 native f2=147. `meg4`는 catalog:908와 dialogue:2420/2421의 자원 후보 |
| 70870 Arina / 아리나 | 550 / 703 | `native-dump:311`의 유일 `$1524`·아리나, `desc.csv:1525`. L1J 외형1508 대신 현재 native f2=703. 원 stem `arina1x`는 catalog에 없고 `arina1`은 catalog:208, dialogue:1393/1394의 별도 후보이며 런타임 연결하지 않음 |
| 60525 Court Guard / 근위병 | 86 / 148 | `$475` 원 후보86/571을 모두 보존. 그중 원 gfx148과 일치하는 행은 `native-dump:54`의86 하나. template571의 f2는1659. 실제 배치·방향은 L1J 정책 |
| 70857 Heine Guard / 하이네 경비병 | 539 / 1659 | 원 이름 `$1513 $240`을 `desc.csv:1514/241`로 합성하면 KR `하이네 경비병`, TW `海音警衛`. NPC951행 중 이 이름과 f2=1659가 함께 맞는 행은 `native-dump:304`의539 하나. 같은 sprite의 근위병571은 이름이 달라 제외. 원 빈 token 후보목록은 review에 보존. `heguard6` 자원 미확보 |
| 70018 Ysorya / 잡화상 이소리야 | 미확정 / 695 | SPR:1972 헤더 `ysorya`, desc:460, `ysorya1_2`의 자기소개가 일치. 해당 이름의 native NPC template은 없어 null 유지 |
| 70016 Andyn / 무기 방어구 상인 안딘 | 미확정 / 457 | SPR:1575 헤더 `andyn`, desc:459와 `andyn1` 상점 대사. 해당 native template은 없어 null 유지 |
| 70070 Velisa / 여관대여 벨리사 | 미확정 / 989 | SPR:3090 헤더 `velisa`, desc:913의 이름이 일치. `inn`은 공통 자원이며 전용 화자 증명이 아님. 해당 native template은 없어 null 유지 |

표의 SPR 줄은 `work/local_resource_provider/assets/data/list.spr`, desc/dialogue 줄은 같은 폴더의 CSV, catalog 줄은 `work/asset_data_analysis/current/catalog.tsv` 기준이다. `native-dump`는 `work/source_game_data/native-dump-v1.jsonl`의 실제 줄이다. 리차드·맥·아리나의 이름과 현재 native 외형을 우선한 결과는 옛 L1J gfx와의 차이를 숨기지 않는다. template는 Actor UID나 wire f39가 아니며 원본 화면 성공을 뜻하지 않는다.

각 NPC의 `client_name_evidence`·`l1j_gfx_client_resource`·`client_identity_review`에 근거와 미확정 이유를 남겼다. 상점24종의 중복 외형 metadata도 같은 값으로 맞췄다. `npc_menus.json`의 별도 `catalog_identity_review_resources`46개·`npc_identity_links`184행은 원 npcaction stem, 존재/부재, 현재 catalog 줄, 동일한 보존 UML의 literal action 및 현지화 키를 보존한다. 기존 runtime `resources`29개와 action 목록은 변경하지 않았다. `<var src="name"/>`은 Actor에서 공급하는 표시명으로, 해당 HTML 자체에 화자 identity가 적혀 있다는 뜻이 아니다. 정적 HTML 후보와 실제 서버 메뉴 발급·런타임 binding은 구별한다.

`appearance_for`는 선택 template가 후보목록에 있어야 그 후보의 한글 이름을 소비한다. 아래 1차 시험 당시 template18종은 그 조건을 만족하지만 외형만 보완한3종은 계속 L1J 영문 label을 사용했다. 현재 template 선택은19종이며 이번 LOCAL38종 역시 template를 빌려 이름을 바꾸지 않는다. 나머지 desc 이름도 metadata 보완이며 실제 이름 소비 완료가 아니다. `confirmed_npc_ids`는 후보가 정확히1개여야 하므로 원 후보2개를 보존한 근위병60525를 자동 포함하지 않는다. 이 자동 선정 함수가 포함하는 M5 고유 NPC는17종이며, template18종·외형21종과 분모/조건을 구분한다.

**검증 완료: JSON 재읽기와 기존 원행·배치·가격·메뉴 action 보존 확인, 이번 데이터 조합의 `world_m5_tests` 전체9개 OK(exit0).** 일회성 시험 worker가 지정 `SL_TEST_PORT_BASE=20000`, `SL_TEST_TIME_SCALE=10`, `SL_TEST_TIME_MODE=idle`로 기존 fast_clock을 import 전에 활성화해 실행했다. 실제37.944초/가상166.889초이며 내부 봇은 한 번만 실행했다. 로그는 `work/local_original_session/runs/m5-unittest-fast10-20261028-123305.log`, 결과는 `work/local_original_session/runs/m5-bot-enq0vgpw/result.json`이다. 봇은 PASS·27checks·478requests·failure null·gaps/failures 없음, 두 epoch 모두 CLOSED·cleanup_complete=true·tasks0/registry_sessions0이며 종료 뒤20000/22030 listener0을 확인했다. 최초 Python 인수 SyntaxError는 시험 시작 전 실패로 `m5-unittest-fast10-20261028-123252.log`에 보존했다. 이번 결과는 개발 fixture의 데이터/direct-hook8개와 직접 패킷1개 범위이며 원본 화면·입력 확인은 아니다. 아래 과거 PASS와 합산하지 않는다.

```powershell
$env:SL_TEST_PORT_BASE='20000'
$env:SL_TEST_TIME_SCALE='10'
$env:SL_TEST_TIME_MODE='idle'
$m5Code = "from tools.local_original_session import fast_clock; fast_clock.enable_from_env(); import unittest,json; suite=unittest.defaultTestLoader.loadTestsFromName('tools.local_original_session.world_m5_tests'); result=unittest.TextTestRunner(verbosity=2).run(suite); print('FAST_CLOCK ' + json.dumps(fast_clock.report()), flush=True); raise SystemExit(not result.wasSuccessful())"
python -X utf8 -B -c $m5Code
```

새 검사기·guard·보고서·실행 코드는 만들지 않았다. `build_data.py`에는 옛13종 선정 규칙이 남아 있으므로 재생성 시 이 정적 검토가 사라질 수 있다. 재생성 작업에서는 현재 보완 metadata와 선택값을 보존·재적용해야 한다.

## 미선택90종 외형 조사와 LOCAL L1J 참고 선택 (2026-10-28)

이 항목은 위 1차 정적 검토·기존 봇 결과 이후의 데이터 변경이다. 실제 시작 데이터는 선택94종(직접 client27·LOCAL67), template19종, 미선택90종이었다. 90종 전원을 desc 이름·native 이름 후보951행·SPR 헤더2976개 순서로 검토하고 공식 자료를 확인한 뒤 L1J 원 NPC행을 대조했다. 같은 이름/토큰의 native 후보가 있던4종도 SPR와 identity가 맞지 않아 template를 새로 선택하지 않았다.

**현재 결과: 38종 LOCAL 외형 추가 → 선택132/184종(직접 client27·LOCAL105), 미선택52종, template19종 유지.** `selected_classic_sprite_id`를 실제 로더가 소비하는 선택으로 반영하고 상점 중복 metadata도 동기화했다. 일반 역할/소품 헤더와 정확한 L1J NPC→gfx 원행은 LOCAL 참고 외형의 근거이며, NPC 이름·Classic template·화면 외형 확정 근거는 아니다. shaman·gypsy·nobleman·maid처럼 서비스명과 헤더 역할이 다른 경우에도 전용 타인명 없는 일반 자원의 L1J 사용 계약만 채택했다. 다른 전용 이름이나 약칭만 있는 자원은 선택하지 않았다.

`appearance_for`와 M5 런타임 fallback의 분모도 다르다. 기존 `_m5_town_setup`의 텔레포터940·창고143·상점/여관 후보 fallback은 런타임 LOCAL 정책이며 아래 미선택52종을 데이터 선택 완료로 바꾸지 않는다. 신규38종은 template null을 유지하고 wire f39·이름·후보목록·기존 identity 근거·원행·좌표·방향·count0·상품·가격·메뉴를 보존한다.

공식 원문은 `tools/local_original_session/data/m5/appearance_sources/official_villages.json`·`official_pets.json`에 보존했다. 공식 페이지가 선언한 서비스와 실제 `view.js`의 `/api/v2/{service}/guide/{title}` 호출식을 확인한 뒤 조회했으며 NPC endpoint를 추정하지 않았다. 조회일은2026-10-28이고 두 문서 updateTime은 각각2026-10-20T23:00:41+09:00·23:08:25+09:00다. [마을 소개](https://lineageclassic.plaync.com/ko-kr/guidebook/view?title=%EB%A7%88%EC%9D%84%20%EC%86%8C%EA%B0%9C)는 마을 시설을 설명하지만 대상 이름→SPR 번호를 주지 않는다. [펫](https://lineageclassic.plaync.com/ko-kr/guidebook/view?title=%ED%8E%AB)의 보관소 문단은 켄트 딕 이름을 확인하지만 보존한 `official_pet_storage.png`(988×742)는 말하는 섬 존슨을 보여준다. 이 이미지를 딕이나 본토 펫 관리인의 SPR 증거로 전용하지 않았다. 마을 지도 이미지는 개별 외형 결합 근거가 없어 수집하지 않았다. 공식 문서/게시 이미지 확인과 현재 로컬 원본 렌더 관측은 다르다.

아래 `L1J` 줄은 `D:/SingleLineageRef/l1j-en-classic/db/l1jdb_m10.sql`, `SPR` 줄·헤더는 `work/local_resource_provider/assets/data/list.spr` 원문이다. 모든38종의 L1J ID·이름·nameid·impl·gfxid와 현재 보존 원행이 일치하고 해당 SPR 정의가 실제 존재함을 확인했다.

### 추가한 LOCAL38종

| L1J NPC / 원이름 | 원행 | 선택 SPR / 원문 줄 / 헤더 이름 |
|---|---|---|
| 50117 Syria | l1jdb:21810 | 940 / SPR:2915 / `Teleporter` |
| 70546 Village Manager | l1jdb:22202 | 971 / SPR:2986 / `steward` |
| 60508 Guard | l1jdb:21996 | 148 / SPR:854 / `kent castle guard` |
| 80006 Message Board | l1jdb:22915 | 1546 / SPR:4907 / `board b` |
| 50119 Oshillia | l1jdb:21812 | 940 / SPR:2915 / `Teleporter` |
| 70774 Village Manager | l1jdb:22423 | 971 / SPR:2986 / `steward` |
| 60510 Guard | l1jdb:21998 | 148 / SPR:854 / `kent castle guard` |
| 90013 Bag Girl | l1jdb:23293 | 725 / SPR:2129 / `citizen girl` |
| 50034 Market Teleporter | l1jdb:21753 | 2141 / SPR:7010 / `shaman` |
| 50529 Even | l1jdb:21849 | 1256 / SPR:4246 / `maid` |
| 70033 Verita | l1jdb:22088 | 1307 / SPR:4438 / `npc alchemist` |
| 70030 Mayer | l1jdb:22085 | 1276 / SPR:4325 / `leather craft` |
| 70039 Werner | l1jdb:22094 | 1208 / SPR:4083 / `blacksmith` |
| 70032 Vergil | l1jdb:22087 | 1314 / SPR:4457 / `npc gappaci` |
| 70607 Sarsha | l1jdb:22260 | 1307 / SPR:4438 / `npc alchemist` |
| 70605 Blaise | l1jdb:22258 | 1288 / SPR:4375 / `npc bald man` |
| 70594 Village Manager | l1jdb:22247 | 971 / SPR:2986 / `steward` |
| 60524 Court Guard | l1jdb:22012 | 335 / SPR:1451 / `guard archer` |
| 81160 Torch Fire | l1jdb:23185 | 1171 / SPR:3944 / `sacred fire` |
| 81161 Auction Board | l1jdb:23186 | 1544 / SPR:4901 / `board a` |
| 70577 Auctioneer | l1jdb:22230 | 1256 / SPR:4246 / `maid` |
| 81287 Wizard Merlin | l1jdb:23279 | 2400 / SPR:8201 / `gypsy one` |
| 71180 Jeif | l1jdb:22822 | 721 / SPR:2111 / `citizen boy a` |
| 50050 Market Teleporter | l1jdb:21769 | 2141 / SPR:7010 / `shaman` |
| 70749 Milo | l1jdb:22399 | 2255 / SPR:7417 / `dog merchant` |
| 70063 Bius | l1jdb:22118 | 1271 / SPR:4305 / `craftsman` |
| 70061 Mandra | l1jdb:22116 | 1254 / SPR:4237 / `hunter` |
| 70740 Soldier of Dicarding | l1jdb:22390 | 148 / SPR:854 / `kent castle guard` |
| 50125 Gilbert | l1jdb:21818 | 940 / SPR:2915 / `Teleporter` |
| 70748 Village Manager | l1jdb:22398 | 971 / SPR:2986 / `steward` |
| 60523 Guard | l1jdb:22011 | 148 / SPR:854 / `kent castle guard` |
| 80192 Jewel Craftsman David | l1jdb:23064 | 2293 / SPR:7559 / `nobleman` |
| 70085 Old | l1jdb:22140 | 721 / SPR:2111 / `citizen boy a` |
| 50123 Galleon | l1jdb:21816 | 940 / SPR:2915 / `Teleporter` |
| 70860 Village Manager | l1jdb:22505 | 971 / SPR:2986 / `steward` |
| 71198 Head of Mercenary Squad Tion | l1jdb:22840 | 1659 / SPR:5370 / `sinwarrior` |
| 71199 Jeron | l1jdb:22841 | 1254 / SPR:4237 / `hunter` |
| 90014 Benole | l1jdb:23294 | 1271 / SPR:4305 / `craftsman` |

Auction Board81161의1544는 SPR:4901 `board a`에 더해 SPR:4913의 `#1552 1=1544 auction board a`가 같은 파일/자원을 명시한다. 그 alias도 Actor identity나 화면 성공을 입증하지 않는다.

### 미선택52종 전원과 이유

분류 합은 고정 client SPR 부재12 + 전용 다른 이름/약칭 연결 없음37 + 원이름 Unknown3 =52다. `desc`가 있어도 native template·SPR 결합이 없으면 이름만 확인한 것으로 남긴다. 각 행의 상세 이름 근거와 해소에 필요한 입력은 `town_npcs.json.npcs[].appearance_followup_review`에 있다. 공통으로 검토한 공식 두 문서에는 아래 이름을 해당 번호에 결합하는 근거가 없었다.

| L1J NPC / 원이름 | L1J gfx / 고정 SPR 헤더 | 보류 이유 |
|---|---|---|
| 50020 Stanley | 6377 / 정의 없음 | 고정 list.spr에 해당 번호 없음; 대체 자원 근거 필요 |
| 50022 Harrison | 981 / `brunner` (SPR:3027) | 전용 다른 이름/약칭을 대상 이름과 잇는 근거 없음 |
| 60003 Thram | 143 / `dorin` (SPR:799) | 전용 다른 이름/약칭을 대상 이름과 잇는 근거 없음 |
| 70544 Rick | 1515 / `terry` (SPR:4739) | 전용 다른 이름/약칭을 대상 이름과 잇는 근거 없음 |
| 70015 Arieh | 1530 / `tovia` (SPR:4824) | 전용 다른 이름/약칭을 대상 이름과 잇는 근거 없음 |
| 70520 Alchemist | 2090 / `varyeth` (SPR:6899) | 전용 다른 이름/약칭을 대상 이름과 잇는 근거 없음 |
| 70556 Secratary to the Mayor | 460 / `ishmael` (SPR:1582) | 전용 다른 이름/약칭을 대상 이름과 잇는 근거 없음 |
| 81123 Pumpkin Trader | 2499 / 정의 없음 | 고정 list.spr에 해당 번호 없음; 대체 자원 근거 필요 |
| 81200 Unknown | 1768 / `dwarf master` (SPR:5775) | 원 이름·토큰 불명; 객체/배치 identity 근거 필요 |
| 50054 Trey | 6377 / 정의 없음 | 고정 list.spr에 해당 번호 없음; 대체 자원 근거 필요 |
| 50053 Cobb | 793 / `Rohan` (SPR:2391) | 전용 다른 이름/약칭을 대상 이름과 잇는 근거 없음 |
| 60023 Tarkin | 143 / `dorin` (SPR:799) | 전용 다른 이름/약칭을 대상 이름과 잇는 근거 없음 |
| 70069 Momo | 991 / `miranda` (SPR:3106) | 전용 다른 이름/약칭을 대상 이름과 잇는 근거 없음 |
| 70783 Aria | 796 / `Lyra` (SPR:2407) | 전용 다른 이름/약칭을 대상 이름과 잇는 근거 없음 |
| 70788 Secretary to the Mayor | 460 / `ishmael` (SPR:1582) | 전용 다른 이름/약칭을 대상 이름과 잇는 근거 없음 |
| 50036 Wilma | 6377 / 정의 없음 | 고정 list.spr에 해당 번호 없음; 대체 자원 근거 필요 |
| 50037 Coliseum Manager | 992 / `anotte` (SPR:3114) | 전용 다른 이름/약칭을 대상 이름과 잇는 근거 없음 |
| 50038 Assistant Manager of the Coliseum | 800 / `Woodford` (SPR:2437) | 전용 다른 이름/약칭을 대상 이름과 잇는 근거 없음 |
| 60008 Nodim | 143 / `dorin` (SPR:799) | 전용 다른 이름/약칭을 대상 이름과 잇는 근거 없음 |
| 60009 Sauram | 143 / `dorin` (SPR:799) | 전용 다른 이름/약칭을 대상 이름과 잇는 근거 없음 |
| 70632 Kevin | 792 / `Ofo` (SPR:2383) | 전용 다른 이름/약칭을 대상 이름과 잇는 근거 없음 |
| 70617 Almon | 704 / `lengo` (SPR:2044) | 전용 다른 이름/약칭을 대상 이름과 잇는 근거 없음 |
| 70036 Stella | 200 / `cw maid catty` (SPR:1076) | 전용 다른 이름/약칭을 대상 이름과 잇는 근거 없음 |
| 70040 Jason | 1243 / 정의 없음 | 고정 list.spr에 해당 번호 없음; 대체 자원 근거 필요 |
| 70042 Secil | 1505 / `eliza` (SPR:4691) | 전용 다른 이름/약칭을 대상 이름과 잇는 근거 없음 |
| 70035 Polly | 990 / `mellin` (SPR:3098) | 전용 다른 이름/약칭을 대상 이름과 잇는 근거 없음 |
| 70041 Maeno | 1515 / `terry` (SPR:4739) | 전용 다른 이름/약칭을 대상 이름과 잇는 근거 없음 |
| 70031 Molly | 1507 / `jessy` (SPR:4707) | 전용 다른 이름/약칭을 대상 이름과 잇는 근거 없음 |
| 70631 Secratary to the Mayor | 460 / `ishmael` (SPR:1582) | 전용 다른 이름/약칭을 대상 이름과 잇는 근거 없음 |
| 80128 Seal Merchant | 800 / `Woodford` (SPR:2437) | 전용 다른 이름/약칭을 대상 이름과 잇는 근거 없음 |
| 81124 Pumpkin Trader | 2499 / 정의 없음 | 고정 list.spr에 해당 번호 없음; 대체 자원 근거 필요 |
| 71181 Emai | 5913 / `MY` (SPR:13962) | 전용 다른 이름/약칭을 대상 이름과 잇는 근거 없음 |
| 50051 Kirius | 6377 / 정의 없음 | 고정 list.spr에 해당 번호 없음; 대체 자원 근거 필요 |
| 60021 Hirim | 143 / `dorin` (SPR:799) | 전용 다른 이름/약칭을 대상 이름과 잇는 근거 없음 |
| 70068 Franko | 457 / `andyn` (SPR:1575) | 전용 다른 이름/약칭을 대상 이름과 잇는 근거 없음 |
| 70065 Enke | 991 / `miranda` (SPR:3106) | 전용 다른 이름/약칭을 대상 이름과 잇는 근거 없음 |
| 70744 Roje | 2829 / 정의 없음 | 고정 list.spr에 해당 번호 없음; 대체 자원 근거 필요 |
| 70761 Secretary to the Mayor | 460 / `ishmael` (SPR:1582) | 전용 다른 이름/약칭을 대상 이름과 잇는 근거 없음 |
| 81130 Message Board | 2207 / 정의 없음 | 고정 list.spr에 해당 번호 없음; 대체 자원 근거 필요 |
| 81246 Sharna | 2090 / `varyeth` (SPR:6899) | 전용 다른 이름/약칭을 대상 이름과 잇는 근거 없음 |
| 81150 Ranking Board | 2205 / 정의 없음 | 고정 list.spr에 해당 번호 없음; 대체 자원 근거 필요 |
| 50066 Riol | 6377 / 정의 없음 | 고정 list.spr에 해당 번호 없음; 대체 자원 근거 필요 |
| 60030 Hakim | 143 / `dorin` (SPR:799) | 전용 다른 이름/약칭을 대상 이름과 잇는 근거 없음 |
| 70873 Ellan | 704 / `lengo` (SPR:2044) | 전용 다른 이름/약칭을 대상 이름과 잇는 근거 없음 |
| 70082 Britt | 695 / `ysorya` (SPR:1972) | 전용 다른 이름/약칭을 대상 이름과 잇는 근거 없음 |
| 70083 Shivan | 695 / `ysorya` (SPR:1972) | 전용 다른 이름/약칭을 대상 이름과 잇는 근거 없음 |
| 70084 Elly | 989 / `velisa` (SPR:3090) | 전용 다른 이름/약칭을 대상 이름과 잇는 근거 없음 |
| 70876 Secretary to the Mayor | 460 / `ishmael` (SPR:1582) | 전용 다른 이름/약칭을 대상 이름과 잇는 근거 없음 |
| 71212 Unknown | 1705 / `H windmil_bg` (SPR:5549) | 원 이름·토큰 불명; 객체/배치 identity 근거 필요 |
| 71214 Unknown | 1710 / `H windmil_sm B` (SPR:5564) | 원 이름·토큰 불명; 객체/배치 identity 근거 필요 |
| 71197 Endel | 1513 / 정의 없음 | 고정 list.spr에 해당 번호 없음; 대체 자원 근거 필요 |
| 90015 Sarah | 706 / `judice` (SPR:2060) | 전용 다른 이름/약칭을 대상 이름과 잇는 근거 없음 |

**이번 변경의 정적 검증:** JSON 재읽기, 원 NPC184종·배치242행과 원행·좌표·방향·count0·후보/identity 근거·상품/가격·메뉴 보존 및 상점 중복 metadata 일치 확인. 기존 `world_town.load_town`·`appearance_for`가 신규38종의 선택 gfx를 소비하고 template null을 유지함을 확인했다. 아래 두 시험 동안 town/shop 데이터는 고정했다. 데이터 metadata의 `UNRUN`은 작성 당시의 조사 worker 스냅샷이며 후속 실행 결과는 이 문단에 별도로 기록한다. 기존 봇 PASS를 이번 조합으로 이전하지 않았다.

**직접 패킷 봇 결과: 기본6마을 SKIP과 본토5마을 scoped PASS를 분리한다.** 원본 클라이언트를 실행하지 않은 새 개발 시험 저장과 실제 로컬 broker decoder/router/handler 경로다. 시작은 기존 Lv5 Gludin saved-position/warehouse_roundtrip fixture이며 초기 본토 공개 진입 성공을 주장하지 않는다. 두 결과·stdout은 `work/local_original_session/runs/` 아래에 보존했다.

| 범위 / 결과 | 원결과 / stdout | 조건·실제 결과 |
|---|---|---|
| 기본6마을 **SKIP**, exit1 | `m5-bot-jbudflft/result.json` / `m5-npc-appearance-20261028-141850.log` | base50000·time scale10·navigation/hunt timeout900. 49checks=48PASS+1SKIP, 478requests, 실제41.181초(결과 가상179.019초). 켄트10단계 모두PASS, 글루딘 유료 이동·매입·매각PASS 뒤 `M5 current NPC60007 unavailable`로 중단. 글루딘 창고 이후와 나머지4마을은UNRUN. failure null·failures/server_failures 없음은 SKIP을 전체PASS로 바꾸지 않음 |
| 본토5마을 **scoped PASS**, exit0 | `m5-bot-h36ltsch/result.json` / `m5-npc-appearance-five-towns-20261028-142017.log` | base51000·time scale10·`--towns kent,windawood,giran,oren,heine --navigation-timeout 900 --hunt-timeout 900`. 201checks 전부PASS, 1,626requests, 실제161.398초(결과 가상621.720초), failure null·gaps/failures/server_failures 없음. 정상 글루딘 경유는 유지하고 글루딘 자체visit만 시험목록에서 제외 |

두 번째 실행에서는 켄트·우드벡·기란·오렌·하이네 각각 유료 이동/저장, BUY·SELL/저장, 창고 입출고/저장, 필드 전투·drop·pickup, 귀환/저장, 자연사→Restart→재선택/저장, `visit_complete`가 모두PASS다. 정상Quit 후 새 로그인·선택·월드 재접속과 위치·가방·창고 복원 및 handler 오류 없음도PASS다. 글루딘은 유료 경유만PASS이고 해당 실행의 매매·창고 등visit은UNRUN이다. 첫 실행의 NPC60007은 기존 M4 글루딘의 외형null 대상이므로 실패 범위를 보존하며 이번 M5 외형 데이터에서 임의로 채우지 않았다.

첫 실행1epoch·두 번째2epoch 모두 CLOSED·cleanup_complete=true·active_tasks0·registry_sessions0이다. 두 번째의 두 epoch 모두 Quit 응답 drain을 확인했다. 종료 후 listener0은 시험 worker가 각각50000/52030·51000/53030에서 확인했다. 기존 결과의 startup `source_sha256` 맵에는 `hunt_bot_m5`와 data 파일이 포함되지 않는다는 원문 한계를 유지하며 이를 이번 JSON 데이터의 해시 증명으로 확대하지 않는다.

이 PASS는 고정된132종 외형 선택 데이터 조합에서 위5마을 직접 패킷 서비스·전투·저장/복원 흐름을 확인한 범위다. 신규38종을 각각 방문·렌더한 결과, 원본 화면·입력·자원 로딩, 공식 NPC identity/외형 동등성 또는30분 원본 플레이 완료는 미검증이다. 기본6마을 전체PASS로 합산하지 않는다.

`build_data.py`에는 이전 선정 규칙이 남아 있어 재생성으로 이 선택/근거를 덮을 위험이 있다. 재생성 시 현재 JSON의 기존·추가 선택과 근거를 보존·재적용해야 하며 이번에는 generator를 수정하지 않았다.

## NPC 클릭의 원본 대화·메뉴 연결 (2026-10-28)

위 정적 검토46후보와 현재 `dialogue.csv`/catalog·보존 UML을 런타임 선택에 연결했다. 기존 `resources`는 실제31개였으며 이를 보존하고, catalog 내용이 동일한 안내·NPC별 창고·텔레포터 첫 페이지 및 client-local 링크 하위문서를 추가해68개가 됐다. 변경된 `colos1`의 옛 본문은 사용하지 않는다. 원 NPC184종/242배치·count0·원좌표·방향·identity 검토값·상품·가격은 변경하지 않았다.

해당 대화 연결 시험 당시 `npc_menus.json.runtime_bindings`185행은 본토184종과 기존 글루딘 Steve1종이다. 자원 있는 초기 대화는110종(본토109+Steve1)이며, 외형 조건을 적용한 본토 준비 binding은104고유 NPC/104배치다. 기존 지형·수명·등록 조건을 통과해 실제 발급 가능한 본토 대상은93고유 NPC/93actor다. 이 수는 공식 NPC identity나 원본 화면 성공 수가 아니다.

| 역할 | 본토 준비 NPC/배치 | 실제 등록 NPC/actor |
|---|---:|---:|
| 텔레포터 | 5/5 | 5/5 |
| 개인 창고 | 6/6 | 6/6 |
| 상점 | 20/20 | 14/14 |
| 일반 안내 | 68/68 | 66/66 |
| 여관 | 4/4 | 1/1 |
| 퀘스트 안내 | 1/1 | 1/1 |

자료는 있지만 외형을 고르지 않은 Rick70544·Aria70783·Even50529·Auctioneer70577·Soldier of Dicarding70740은 발급 대상을 추가하지 않았다. 여관은 Woods70070만 원중심 통행 가능하다. Giran70031·Oren70065·Heine70084의 S32=False 원좌표를 보존하고 배우를 임의로 옮기지 않았다. 기존 M2/M4 상점 연결은 이전 stem/suffix 선택 방식의 fallback으로 보존하며 현재 해당하는 글루딘 Luth70021도 유지한다. Steve/Luth는 위 본토 집계에 넣지 않았다.

기존 `MenuSource`/`ServiceMenuSource`와 등록형 `town_setup`·`service_action` 훅을 재사용한다. 텔레포터는 `steve1/stanley1/trey1/wilma1/kirius1/riol1`을 먼저 발급하고 실제 `teleportURL` 요청 뒤 각 목적지2를 발급한다. 개인 창고는 공통 `storage` 대신 `thram/tarkin/nodim/sauram/hirim/hakim` 원문을 발급하고 기존 입출고·CAS 소유자에게 연결한다. 상점 거래와 여관의 현재 LOCAL 대여 정책은 기존 소유자를 유지한다.

`<a link>`는 클라이언트 내부 문서 전환으로 보존하며 가짜4ED4 링크 패킷을 만들지 않는다. 하위문서의 실제 action literal은 같은 현재 메뉴 context에서 검사한다. 미구현 queststart·길드·아지트·세금·펫·창고 혈맹/이력 action은 `M5_DIALOGUE_ACTION_NOT_READY`로 거절해 유료 텔레포트로 오인하지 않는다. `dialogue.csv.NPC_NAME`은 전행 비어 있으므로 화자 identity join 근거가 아니며, NPC→페이지 선택은 명시적인 LOCAL 대응이다. 본토 퀘스트는 안내를 연결한 범위이며 수락·보상 구현을 완료했다고 표시하지 않는다.

최종 소스 검증은 `SL_TEST_TIME_SCALE=10`, `SL_TEST_TIME_MODE=idle`, `SL_TEST_PORT_BASE=24000`으로 순차 실행했다. 서버 포트 시험 소유자는 이번 worker 하나였으며 원본 클라이언트를 실행하지 않았다.

| 실행·로그 (`work/local_original_session/runs/` 기준) | 결과와 판정 범위 |
|---|---|
| `m5-dialogue-bot-cognoc7o/result.json`, `m5-dialogue-bot-final-20261028-134926.log` | **PASS**,34checks/732requests. 실제 FIRST→로그인→선택→월드 진입 후 상점randal1·개인창고nodim과 입출고·텔레포터 첫1→2와 정상 요금/저장·일반 안내herbert1/vincent1·퀘스트 안내brad1과 queststart 무부작용 거절·Woods여관inn을 확인. CLOSED·cleanup=true·tasks0/registry0 |
| `m5-dialogue-mandatory-final-20261028-135013.log`, `m5-bot-lafgzpir/result.json` | **world_m5_tests 9/9 OK**. 기존 기대가 모두 Kent scoped이므로 `--towns kent`를 명시했다. 내부 봇70checks/508requests PASS, 실제 켄트 거래·창고·전투·줍기·귀환·사망/재선택·전체 경로 정상 텔레포트·저장 재접속. 두 epoch 모두 CLOSED·cleanup=true·tasks0/registry0. 다른 마을의 전투/거래 완료로 확대하지 않음 |
| `m5-dialogue-town-tests-20261028-134906.log` | `world_town_tests`14/14, `world_town_services_tests`27/27 OK. 위 M5와 합계50개 |

전용 봇 명령은 `python -X utf8 -B C:/Users/Chansol/AppData/Local/Temp/claude/D--claude/0483de89-75e7-4b94-84b8-fb31fe00f575/scratchpad/fastbot/run_fast.py hunt_bot_m5_dialogue --navigation-timeout 240`이다. 필수 시험은 fast_clock을 import 전에 활성화한 뒤 `python -X utf8 -B -c "from tools.local_original_session import fast_clock; fast_clock.enable_from_env(); import unittest; r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName('tools.local_original_session.world_m5_tests')); raise SystemExit(not r.wasSuccessful())"`로 실행했다. town 두 모듈도 같은 방식으로 각각 독립 프로세스에서 실행했다.

실패와 부분 성공은 보존했다. `m5-dialogue-bot-po_ybbxf`는 봇의 데이터 경로 상수 참조 오류로 FAIL 후 정상 정리했다. `m5-dialogue-bot-c45crgsj`는 막힌 원중심의 Giran여관이 없어서 SKIP했고, 이후 원좌표를 보존한 채 정상 텔레포트로 Woods여관을 확인했다. 기본 전마을 회귀 `m5-bot-x9t53__r`는 Luth 연결 누락으로 SKIP→unittest FAIL였으며 fallback을 복구했다. 별도 `--towns gludin` 실행 `m5-bot-g3bla1tr`는 Luth 구매/판매까지 통과한 뒤 기존 미지원 창고60007에서 SKIP(11checks/45requests·정상cleanup)했다. 따라서 기본 전마을 봇 전체 PASS는 주장하지 않는다. 이번 기능 밖인60007을 새로 확장해 실패를 덮지 않았다.

우리 실행 종료 뒤24000/26030을 소유한 PID25508은 main이 별도 `world_integration_tests` 작업임을 확인했다. 이 프로세스를 종료하지 않았다. 변경 파일은 `npc_menus.json`, `world_feature_m5.py`, `world_town_services.py`, `world_feature_town.py`, `hunt_bot_m5.py`의 텔레포터 구간, 새 `hunt_bot_m5_dialogue.py`, `world_m5_tests.py`의 Kent 범위 인수와 본 절이다. 수동 실행 핀 대상은 없으며 ACTIVE·사용자 프로필·원본·저장·타 기능을 변경하거나 commit하지 않았다.

남은 범위는 미확보/변경된 HTML과 외형, 막힌 원배치, 미구현 quest/service action, 여관 내부맵·입장, 원본 클라이언트의 실제 렌더·입력·client-local 안내 링크 전환이다. 직접 패킷의 페이지 발급·저장 성공을 원본 화면·입력 동등성이나30분 플레이 완료로 확대하지 않는다.

## 로딩과 활성화

새 `world_feature_m5.py`의 startup hook이 `SL_EXPERIMENT_M5=1`과 `SL_EXPERIMENT_MAP=2`일 때만 데이터를 합친다. `world_handlers.FEATURE_MODULES`에 한 줄로 등록하며 기존 필수 호출·기능 메서드 덮어쓰기를 추가하지 않는다. 마을과 서비스·메뉴 bindings를 시작 시 합치고 기존 item 정책·공급된 메뉴·할당기·판매 callback·wire·거리 정책과 스폰 슬롯/RNG를 보존한다. 요청 중 파일 판독·새 hash/pin 검사는 없다.

상점·창고의 패킷 실험은 기존과 같이 `SL_EXPERIMENT_SHOP=1`, `SL_EXPERIMENT_WAREHOUSE=1`도 필요하다. 새 봇이 이 환경을 해당 실행 안에서 설정·복원한다. 실험의 기존 미확정 wire 피연산자를 원본 정상 서버값으로 승격하지 않는다.

기존 item effect 객체에 위임하는 wrapper가 귀환 주문서의 map4 목적지만 가장 가까운 마을로 고르고, `after_death`는 같은 정책으로 기존 사망 복귀 예약을 갱신한다. 글루딘도 거리 후보에 포함한다. 거리는 Chebyshev이며 동률은 표 순서로 고르는 LOCAL 규칙이다. map4 밖은 기존 동작을 유지한다.

텔레포터의 L1J sprite6377은 현재 sprite 표에 없어, 명시적인 LOCAL 역할 외형940을 사용한다. 창고의 역할 외형143 역시 NPC identity 확정이 아니다. 외형을 고르지 못한 서비스는 보이지 않는 장애물로 등록하지 않는다. 모듈 등록을 빼면 기존 M1/M4 서버가 작동하는 구조다. 기존 `world_town.py`·`world_maps.py` 로더를 재사용하므로 M5를 위해 두 파일을 수정할 필요는 없었다. `start-manual-play.ps1`의 기존 핀 대상도 이번 수정 범위에 없다.

## 미완 서비스

여관4종의100A는 기존 M2와 같은 명시적인 LOCAL 계산 참고값이다. Native `room`의 수량·열쇠·입장·반환/회복 계약이 미확정이므로 실제 방 대여·회복은 NOT_READY다. 켄트는 선정한 마을 region 안에 여관 출처 배치 자체가 없어 `inn_unavailable`로 남긴다. 임의 NPC를 만들거나 다른 마을의 여관을 켄트 원본 여관으로 표시하지 않는다.

## 실행 기록과 실패 보존

시험은 별도 새 개발 저장과 기존 Matrix의 native-layout LOCAL 인벤 adapter로 FIRST→로그인→캐릭터 선택→월드 진입 후 실제 요청을 보낸다. 시작은 글루딘 map4 고정점·기존 test_knight 키트·창고 요건을 위한 개발 level5 fixture다. M5가 아이템 UID·보상·RNG·살아 있는 HP를 강제하지 않는다. 이동·상점/창고·장비·전투·줍기·귀환은 받은 현재 참조와 정상 패킷을 사용한다.

아래 결과는 `work/local_original_session/runs/`에 그대로 보존한다. 서로 다른 실행의 성공을 합산하지 않는다.

| 실행 | 실제 결과 |
|---|---|
| `m5-bot-8ehk3qph` | FAIL. 켄트 이동·구매는 처리됐지만 봇이 BUY f3 아이콘을 가격으로 읽어 검증 실패. 시험만 f4 가격으로 수정. 정상 정리 |
| `m5-bot-p8pmauqt` | FAIL. 상점·창고 후 기본 첫그룹의 레벨9 늑대인간을 상대로 실제8타·물약3개 사용 뒤 사망. 시험 캐릭터 레벨5에 맞춰 기존 봇의 레벨+3 이하 대상 선정 정책을 적용. 정상 정리 |
| `m5-bot-uzlsi7zw` | FAIL. 드워프 처치·드롭13A 줍기·귀환/저장·Quit까지 통과했지만 마법 모듈의 Context 메서드 복원 오류로 close 실패, 재접속 UNRUN, cleanup_complete=false. 실행 중 캐시된 마법 소스와 동시 작업에서 갱신된 현재 소스가 달랐으며, M5 작업은 해당 금지 파일을 수정하지 않음 |
| `m5-bot-0jzbzgns` | **PASS / 개발 fixture 직접 패킷 범위**. 한 실행의28항목 전부 PASS,487요청,217이동,드워프4타/1처치·13A 드롭1줍기,물약1회,귀환162 수량10→9,켄트33050,32782 귀환과 새 FIRST 재접속 시 위치·인벤·창고 복원. 두 epoch 모두 정상 Quit와 cleanup_complete=true, tasks0/registry0·오류목록 없음 |

별도로 데이터 작업자가 전체 M4 시험 모듈을 잘못 선택해 기본12000/14030에서 소켓 시험을 실행했다. 해당 프로세스는 종료되고 포트가 정리됐으며 지정 봇20000/22030과 포트 충돌은 관측되지 않았다. 최종 출력이 확보되지 않았으므로 이 실행은 PASS 근거에서 제외한다. 기존 combined unittest의 import graph 검사 실패도 보존하고 순수 모듈 독립 실행 결과와 구별한다.

최종 시험 로그 경로는 `work/local_original_session/runs/m5-tests-20261027-195544/`다. 최종 소스의 M5 데이터8개+패킷1개(모듈9/9,170.201초), 회귀187개가 통과해 합계196개다. 최종 통합 명령은 `$env:SL_TEST_PORT_BASE='20000'; python -X utf8 -m unittest tools.local_original_session.world_m5_tests`이며 로그는 `m5-current-source-final.log`, 실행 결과는 `m5-bot-0jzbzgns/result.json`이다. 결과의 `source_sha256`에 실행된 M5 모듈을 포함한 로드 소스가 기록돼 있다. 지정 물리 포트20000/22030은 마지막 종료 뒤 listener 없음으로 확인했다. 회귀는 import graph 조건을 보존하기 위해 아래 모듈을 각각 독립 Python 프로세스로 순차 실행했다. 마법 모듈의 현재 수정본에서는 M4의 실제 open/close도10/10 통과했다.

```powershell
$env:SL_TEST_PORT_BASE='20000'
python -X utf8 -m unittest tools.local_original_session.world_m5_tests.M5DataTests
python -X utf8 -m unittest tools.local_original_session.world_m5_tests.M5PacketTests

$m5RegressionModules = @(
  'world_m4_tests', 'world_town_tests', 'world_maps_tests',
  'world_town_services_tests', 'world_shop_tests', 'world_shop_menu_tests',
  'world_warehouse_tests', 'world_item_effects_tests', 'world_handlers_tests',
  'world_handler_adapter_tests', 'world_magic_tests'
)
foreach ($m5TestModule in $m5RegressionModules) {
  python -X utf8 -m unittest "tools.local_original_session.$m5TestModule"
}
```

회귀별 수는 M4 10·town14·maps6·services27·shop24·shop_menu12·warehouse11·item_effects11·handlers12·handler_adapter7·magic53이다. 단독 봇 실행은 `python -X utf8 -m tools.local_original_session.hunt_bot_m5 --navigation-timeout 240 --hunt-timeout 180`이며, 시험 모듈의 실행과 같은 시나리오다. 패킷 시험과 단독 봇을 중복 실행해 성공 수를 늘리지 않는다.

실행 코드는 `data/m5/`·새 `world_feature_m5.py`·새 `hunt_bot_m5.py`·새 `world_m5_tests.py`와 `world_handlers.py`의 M5 등록1줄이다. 본 문서 외 ACTIVE·금지 파일·기존 사용자 저장은 M5 작업에서 수정하지 않았고 git commit은 없다. 기존 다수 dirty/untracked 및 동시 작업 M6/마법 변경을 이번 변경으로 주장하지 않는다.

이 절의 과거 최종 봇 실제 방문은 글루딘·켄트였다. 당시 다른 네 마을은 표·지형·경로·로더 검증이며 실제 방문·거래·귀환의 직접 패킷 완료를 뜻하지 않았다. 현재132종 데이터 조합의 본토5마을 후속 scoped PASS는 위 「미선택90종 외형 조사」 항목에 별도 기록했다. 다섯 마을의 사망 선택은 직접 hook 단위 시험으로 확인했고, 정상 사망→Restart→재선택 전체 경로는 M5에서 별도 완료하지 않았다. 여관과 원본 외형/입력·화면·정확한 공식 정책은 여전히 미확인/미완이다.

## 기본 6마을 NPC60007·사냥 정체 원인 수정 (2026-10-28)

기존 qNpcLook 기본6마을 SKIP과 본토5마을 scoped PASS 원결과는 위 기록 그대로 보존한다. 이번 수정은 글루딘 NPC60007에 한정하며 본토184종 외형 선택 수는 변경하지 않는다.

- **60007 unavailable:** `data/m4/town_npcs.json`의 Karim 외형 선택이 null인 데 더해, `data/m5/npc_menus.json.runtime_bindings`에 60007이 없었다. `_m5_town_setup`은 binding이 없으면 창고 역할 외형 fallback에 도달하기 전에 제외하므로 외형만 채워도 등록되지 않았다. 기존 `storage` 자원·deposit/retrieve action과 창고 처리 소유자를 쓰는 60007 binding 하나를 추가했다. 서버·봇 코드는 수정하지 않았다.
- **외형과 배치 경계:** 60007만 기존 M5 창고 역할 정책과 같은 LOCAL SPR143을 명시했다. 출처는 L1J `l1jdb:21958`의 gfx143과 고정 클라이언트 `work/local_resource_provider/assets/data/list.spr:799`의 `#143 dorin`이다. Karim을 Dorin identity로 확정하지 않으며 native template는 null이다. 수정 전부터 있던 LOCAL 동쪽1칸 `(32619,32800)` 배치를 재사용했고, 막힌 L1J 원좌표 `(32618,32800)`·reference·지형 관측은 그대로 보존했다. 이 배치 변경을 이번 작업의 변경으로 주장하지 않는다.
- **사냥터 이동 정체:** 보존 실행 `m5-bot-fjf3jx2r/result.json`은 이동209회·처치1회 뒤 줍기937회가 실패했다. `epochs[0].before_quit.world.pickup_errors`의 실제 거절은 `items.210: kind/duplicate`다. 픽업이 `load_m1()`을 호출할 때 당시 아이템 표 검증에서 막힌 것이며 이동 경로 결함으로 확인되지 않았다. 현재 디스크에서는 `load_m1()`이 아이템567종·몬스터177종을 정상 로드하고 item210은 Ice Lance book misc 하나다. 기존 중복은 현재 조합에서 해소돼 데이터·보상 코어·봇 경로를 추가 변경하지 않았다. 과거 `starter_fields` AttributeError 실행과도 구별한다.

변경 파일은 `data/m4/town_npcs.json`의60007 외형 metadata, `data/m5/npc_menus.json`의60007 binding, 새 `world_m5_gludin_regression_tests.py`다. 기존 `world_m5_tests.py` 기대값과 `hunt_bot_m5.py`·`world_feature_m5.py`, 핀 대상 실행 파일은 수정하지 않았다.

60007 등록 직접 회귀는 PASS다(`runs/m5-fix-gludin-unit-retry2-20261028.log`). 엔티티 발급·SPR143·native template null·기존 LOCAL 좌표와 원좌표 보존·통행 판정·storage source 연결을 확인했다. 직접 구성 단위시험이며 로그인·패킷·원본 렌더 PASS로 확대하지 않는다. 최초 전체 시험의 정적8개는 통과했으나 패킷은 `alignment catalog must cover current M1 monsters`로 요청0에서 실패했다(`runs/m5-fix-unittest-baseline-20261028.log`, `m5-bot-yafrveo2/result.json`). 다른 작업자의 몬스터/성향 표·registry 갱신 중 발생한 초기화 실패는 보존하고 해당 파일은 수정하지 않았다.

최종 재시도는 `SL_TEST_PORT_BASE=52000`(기존 매핑 listener52000/54030)과 `SL_TEST_TIME_SCALE=10`으로 순차 실행했다. 원본 클라이언트는 실행하지 않았다. 최초 alignment 불일치는 후속 준비 확인에서 해소됐지만, 별도 몬스터 스킬 작업의 registry가 먼저 반영돼 다음 startup 오류로 막혔다. 금지된 몬스터·전투 파일이나 registry를 우회 수정하지 않았다.

| 검증 | 실제 결과·원로그 (`runs/` 기준) |
|---|---|
| 기본6마을 봇 첫 시도 | FAIL·요청0·cleanup=true. `world_feature_monster_skills` 모듈 부재. `m5-fix-six-towns-attempt1-20261028.log`, `m5-bot-5xqevsoi/result.json` |
| 기본6마을 봇 마지막 재시도 | FAIL·요청0·cleanup=true. 모듈 생성 뒤 `data/m1/monster_skills.json` 부재. `m5-fix-six-towns-attempt2-20261028.log`, `m5-bot-6s5wgllg/result.json` |
| 기존 world_m5_tests 마지막 재시도 | **정적8개PASS·packet1개FAIL**, 위 JSON 부재로 요청0·cleanup=true. `m5-fix-unittest-attempt2-20261028.log`, `m5-bot-8fzc8gc3/result.json` |

추가30초 준비 확인에서도 해당 JSON이 없어 세 번째 실행은 시작하지 않았다. 종료 뒤52000/54030 listener 없음. realm.py/CP57 해시 오류는 이번 첫 실패가 아니었다. **기본6마을 전체PASS와 world_m5_tests 전체PASS는 미완이며, 아래 재실행이 필요하다.** 원본 렌더·버튼·입력·공식 identity/외형·공식 NPC 배치는 미확인이다.

통합 담당이 `world_feature_monster_skills`의 소비 데이터 준비를 마친 뒤 프로젝트 루트에서 순차 실행한다. 이 명령은 준비 상태를 우회하거나 기대값을 바꾸지 않는다.

```powershell
$env:SL_TEST_PORT_BASE='52000'
$env:SL_TEST_TIME_SCALE='10'
python -X utf8 -B -m unittest tools.local_original_session.world_m5_gludin_regression_tests
python -X utf8 -B C:\Users\Chansol\AppData\Local\Temp\claude\D--claude\0483de89-75e7-4b94-84b8-fb31fe00f575\scratchpad\fastbot\run_fast.py hunt_bot_m5 --navigation-timeout 900 --hunt-timeout 900
python -X utf8 -B -c "from tools.local_original_session import fast_clock; fast_clock.enable_from_env(); import unittest; r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName('tools.local_original_session.world_m5_tests')); raise SystemExit(not r.wasSuccessful())"
```

## 원본에서 확인할 것

NPC별 실제 외형·표시명·방향·입력과 메뉴 대응, 판매·매입 구성 및 가격·세금, 텔레포트 목록·요금·응답/화면 전환, 창고 목록·수량 입력·계정 범위, 여관 방 대여·열쇠·입장·반환/회복 계약, 지역 경계에서의 귀환·사망 복귀, 주변 몬스터의 실제 분포·전투·드롭을 확인해야 한다.

직접 패킷 봇의 성공은 로컬 서버의 디코더·라우터·핸들러·저장 경로 검증이다. Native 화면·버튼·입력 동등성, 공식 규칙 동등성 및 30분 원본 플레이 성공으로 확대하지 않는다. 개발 시작 저장이나 직접 사망 유도는 해당 범위를 명시한다.
