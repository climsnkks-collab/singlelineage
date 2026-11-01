# 말하는 두루마리: 원 로컬 목록창과 선택 요청

2026-10-29 현재: **원표 11그룹704행/목적지569개를 보존했다. 이번 추가 개방0개, 그룹1–5/7의234개는 원 UI 진입 미확보로 전부 보류다.** 같은 f53 숫자의 변신 주문서·막대를 두루마리로 오인하지 않았다. 기존 연결268개는 새 시험저장에서 회귀 SUCCESS(280 checks), 맵미지원57개·좌표막힘10개는 그대로 보류다. 원 비용/레벨은 UNKNOWN, 현재 LOCAL 비용0·제한없음이다. 마지막 절에 이번 근거·그룹별 판정·실제 시험을 기록했으며 이전 실행 계보는 보존한다.

2026-10-27 정적 확인: raw133 사용은 클라이언트 로컬 TeleportBookLayout을 열고, 선택 후 CS0960에 목적지의 zero-based ordinal을 보낸다. ID12273 및 같은 이름의 7개 아이템은 catalog.f53=10이므로 group10을 사용한다. group1 사냥터를 이 아이템의 원 목록이라고 바꾸어 쓰면 안 된다. 원본 게임 실행/캡처·화면/입력 PASS는 없다.

정적 분석 worker는 이 파일만 작성했다. 그 분석 단계에서는 원본·제품·저장·큐·프로필·기존 분석 파일을 변경하지 않았고 게임·서버·포트·live attach를 실행하지 않았다. 이후 별도 구현·패킷 시험 결과는 마지막 절에 구분했다. `reverse-engineer-anything` 스킬의 관찰/추정/UNKNOWN 구분을 적용했다. 기존 원문과 cache를 우선 읽었으며 REA 공용 target/provider도 열지 않았다.

## 신원과 재사용

고정 자원 버전은26.09.29.2001. [TARGET_IDENTITY](../../local_server_rea_20261016/TARGET_IDENTITY.md)의 CONTROL `9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af` 및 파생 carrier `c822838351d774a2022af434829a36dbd9bee030bf22182b834ca4e8659701a9`의 기존 신원/한계를 승계한다. 새로 읽은 code는 기존 `run104_skill_buff_contract/wire_schema/exec-buffer.bin`(RVA1000 기준, 기존 pin `b6f4bce4c4901eaddc964f6d0e8049c7595d5e6851817fd139df3667f4ba35fa`), RTTI는 보존 carrier다. 전파일 해시 검사를 반복하지 않았다. 아래 주소는 RVA이며 VA=imagebase140000000+RVA다. 현재 LC.guard·실행 메모리 동일성을 주장하지 않는다.

재사용 원문: [run37](../../local_server_rea_20261016/run37_item_command_sender/worker/source-evidence.json)의 schema/default sender, [run39](../../local_server_rea_20261016/run39_item_ui_producer/worker/source-evidence.json)의 PC UI→UID→raw switch, [run41](../../local_server_rea_20261016/run41_inventory_update/worker/findings.md)의 ItemInfo 소비, [travel_review](../../all_table_semantics/travel_review/README.md)의 TeleportBook typed target join 및 [원표](../../all_table_semantics/travel_review/teleport-ui-joins.json). 후자는 11group/704행을 보존하며 destination/network mapping의 과거 UNKNOWN은 아래 새 선택 producer 관찰 범위에서만 좁혔다.

## 아이템과 원 자원

[items_all.json](../../../tools/local_original_session/data/catalog/items_all.json)의 `items[].id.value`로 찾는다. 원문 위치는 `work/source_game_data/native-dump-v1.jsonl`다.

| ID | native-dump 줄 | catalog.f4 | f5 icon | f53 group |
|---|---:|---:|---:|---:|
|12273|1816|133|20256|10|
|12366|1909|133|20256|10|
|12367|1910|133|20256|10|
|12368|1911|133|20018|10|
|12369|1912|133|20018|10|
|12370|1913|133|20018|10|
|12416|1957|133|20256|10|

공통 name-token `$16673`, KR `말하는 두루마리`, catalog.f6=2878/f9=5/f10=1000/f15=1/f24=1. f10을 구매가격으로, f15를 소모수량으로 해석하지 않는다. 클래스/기간/stackability는 이 raw 숫자만으로 확정하지 않는다.

상자12278(native-dump1821)와12413(1954)는 token`$16977`, **f4=91/f45=1008**, icon20078, f51=3088/3140다. 두루마리 raw133과 다른 경로이며 개봉 내용·소모·지급UID·기간생성은 이번 미지원/UNKNOWN이다.

[official/items.json](../../../tools/local_original_session/data/official/items.json)의610행에서 이 이름/ID는 확인되지 않았다. 이 파일에 없다는 사실은 게임 전체/공식 문서 부재의 증거가 아니다. 카탈로그7개와상자2개 모두 기존 L1J token correspondence는 `unmapped`, 후보0이다.

`work/asset_data_analysis/current/catalog.tsv:126875..126877`에는 `talkingscroll/talkingscroll_list.csb`, `talkingscroll/talkingscrolllayout.csb`, `talkingscrollscene.csb`가 있고 Purple판도4601/4602/4651에 있다. 기존 `comparison=identical`을 재사용했다. `work/local_resource_provider/assets/data/string.csv:11880..11883,11890`은 UI_talkingscroll 직업4종11934..11937·공통제목11944다. 파일명만으로 창/서버 계약을 추정하지 않고 아래 code로 연결했다.

## raw133 첫 사용은 원 로컬 창

**catalog CommonItemInfo.f5(icon)와 network ItemInfo.f5(raw interaction)는 서로 다른 필드다.** run41의 `4F77BF` presence mask100 →`4F77C8` DTO+90 읽기→`4F77CE` Entity+50 DWORD write가 원문으로 확인된다. run39 `4FD347`이 같은 Entity+50을 switch key로 사용한다.

| 원 경로 | 새로 확인한 정확 사실 |
|---|---|
|PC 입력|기존 run39 A0C0B0의 SlotNode shared model UID→4FD260 lookup. UID를 임의1로 고정하는 경로가 아니다.|
|raw133 switch|4FE2B8[133]=15, jump DWORD4FE264+15*4=4FE125. `4FE125 mov [r13+578],r14`로 실제 사용UID를 보유한 뒤 `4FE12F call5027B0`.|
|창 전달|5027FB UID→payload 첫qword. 50291C의 TD1691810은 `TeleportBookLayout`; 5029FF가 layout.vslot+A0을 호출한다.|
|실제 command|layout vtable1235BD0의+A0=B23B10. B23B5E command0→B23B89 payload UID→B23B8F B23D30(layout,UID,true). B23D8F가 UID를layout+C8에 저장한다.|

이 선택된 **첫 사용 분기에는 기본0960 sender 호출이 없으며**, 서버4E44 응답을 기다려 목록을 여는 구조로 바꾸지 않는다. 하위 모든 함수의 모든 네트워크 부작용 부재나 게임 전체의 전용목록수신 opcode 부재를 증명한 것은 아니다. 목록의 실공급은 아래 고정 클라이언트 table다. packet bot는 이를 `STATIC_CLIENT_LIST`/LOCAL peer 메타데이터 단계로 기록하고 실제 수신목록이라고 표시하지 않는다.

**UNKNOWN:** 정상 공식 서버가7개 아이템의 실제 ItemInfo.f5에133을 보내는 실제 패킷은 미관측. catalog.f4=133과 server ItemInfo.f5의 일반적 자동 동일성을 증명하지 않았다. 원 로컬 UI를 여는 `ItemInfo.f5=133` 공급은 이 정적 분기에 근거한 LOCAL 연결 후보다. 창 열림·렌더·선택·원 finally는 미시험이다.

## group10과 원 ordinal

[item/fields.json](../../all_table_semantics/item/fields.json)의 `type=CommonItemInfo,field=53`은 signed int32/offset14C, metadata15E15F4다. B23D30은 current scrollUID→4FF8E0 row→`row+10` template→36FE00 GetItem→**B24423 `[CommonItem+14C]`를R14D로 읽는다.** B248AB..B248EF가 layout+E0의 group tree에서이 키를 찾는다. 따라서 위7개는 모두 group10이다.

group vector를 B24B3B..B24B87에서 EBX=0부터 전체순회하며 B24B63 `R8D=EBX`→B25560 MakeTeleportItemSlot에 넘긴다. B25C4B `[groupNode+20]`를capture+10(group ID), B25C62 R12D를capture+14(**zero-based ordinal**)로 복사한다. B25CAF..B25CBD가 callback을실제 Button+4F0에 설치한다. vtable1235AF0의+10=B26810이며 RTTI에는 `MakeTeleportItemSlot@TeleportBookLayout`과 `TeleportBookTargetInfo`가 명시된다. heading도 원 배열의 ordinal을 차지하므로 heading 제거 후 재번호를 매기면 안 된다.

원표 `teleport-ui-joins.json`은 JSON list이며 `group_id==10`을 선택한다. 키는 `ordinal/is_heading/f1_signed_destination_key/f2_x_candidate/f3_y_candidate/f4_desc_ID/f4_KR/f5_KR_explicit/effective_secondary_desc_ID`. group10은95행이고 group.f3=true다. 표 안좌표·map의 업무명은 typed UI와자료 join으로 강하게 뒷받침되며 실제 teleport 성공은 별도다.

| group10 ordinal | 원 label / secondarydesc | map 후보 | x,y |
|---:|---|---:|---|
|0|[말하는 섬] /16363|heading -1|좌표 없음·선택 불가|
|1|창고지기 /17030|0|32573,32946|
|2|여관 /17031|0|32599,32931|
|3|텔레포터 /17032|0|32580,32929|
|4|잡화 상인 /17033|0|32642,32949|
|5|마법서 상인 /17034|0|32560,33088|
|6|펫 관리인 /17035|0|32447,32993|
|7|말하는 섬 선착장 /17036|0|32632,32962|
|8|허수아비 수련장 /17037|0|32525,32832|

group1의ordinal11 말섬던전입구(32477,32853),12북섬(32662,32846),13중앙사냥터(32412,33020),14동쪽사냥터(32574,33100)는 기존 자원에는 있지만 **ID12273의group10 목록에 없다.** f53변경·원자원변경 없이 group1의사냥터4개가 해당원창에뜬다고 주장할 수 없다. 별도 LOCAL 메뉴/키트 변경은 그 정책으로 구별한다.

## 실제 선택 → CS0960

callback B26810..B26D09에서 layout+112=false인 일반 선택은 B26AB0으로간다. true분기는 즐겨찾기 편집이며 사용요청과구별한다. child base=RSP+40, hasbits=RSP+50; 프레임의 RBP=RSP+100이다.

| message | 타입/presence | 정확 producer |
|---|---|---|
|outer f1|required uint64|B26B87..B26B97 layout+C8의 실제 scrollUID→4FE630. 원lookup·소유UID를 유지한다.|
|outer f2|required UseItemReqParam|B26B8B R8=&child→기존4FE630→기존default52A410→0960. 선택아이템7개는52B260의특수template분기에없어default후보다. 실제4FE630 gates/pending은 기존계약유지.|
|child f1|optional int32, **present1**|B26AF1 child+70=1; B26AF8 hasbits8800의bit15.|
|child f13|optional int32, **present ordinal**|B26B01 capture+14→B26B04 child+60; hasbit11. map/x/y나group ID가아니다.|
|child f15/f16|optional int32, **둘다present**|sender Button+448/+44C float→B26B66/B26B75 cvttss2si→child+64/+68. B26B6D adds3000; 최종hasbits=B800.|
|그외 child|absent/empty|f2(targetUID),f3,f17(enum),f18목록을추가하지않는다. 초기rawbool+74=1도bit16이없어f14 present가아니다.|

f15/16은 대상grid가아닌 UI 메타다. Button cast실패의원fallback은-1/-1, 두float가0/0이면-2/0이된다(원상수126EE68=-1.0,126EE74=-2.0). **bot의0/0은 원화면 관측값이아니라 서버에서미사용하는명시 LOCAL peer 메타데이터**로만줄수있다. 실제 사용순서·ownedUID·inventory·저장·현재위치 검사를대체하지 않는다.

callback은4FE630뒤560F0→503B00(command1)으로원창닫기요청, child/generated container와sharedpairs를정상release한다. 이정적순서를 실제 정상close/정리성공으로 확대하지 않는다. 소비 후 위치반영은 기존같은맵 이동·시야/관심재계산·저장계약을사용하며 [MAP_TRANSITION_EVIDENCE](MAP_TRANSITION_EVIDENCE.md)의과거보류와 run389의후속범위를구별한다.

## 공식/L1J와 정책 경계

공식 웹검색과 공식페이지를읽었다. 웹reader는guide페이지/API본문을노출하지못했지만 공개HTTP GET은200이었다. 페이지가직접포함한 `window.guidebook.apiDomain` 및공식 `assets.playnccdn.com/uikit/guidebook/2.1.2/js/view.js`의 `/api/v2/{service}/guide/{title}`구성을따라동일공개API를읽었다. 게임접속·로그인·계정변경은없다.

- [공식초보자가이드](https://lineageclassic.plaync.com/ko-kr/guidebook/view?title=%EC%B4%88%EB%B3%B4%EC%9E%90%20%EA%B0%80%EC%9D%B4%EB%93%9C), [공식공개API](https://lineageclassic.plaync.com/api/v2/lineageclassic/guide/%EC%B4%88%EB%B3%B4%EC%9E%90%20%EA%B0%80%EC%9D%B4%EB%93%9C?gwLocale=ko_KR): `paragraphList["1"]` ID24649/name말하는두루마리/updateTime2026-02-06T04:49:41Z는지정지역즉시이동, 사용횟수제한없음, 기간만료삭제를설명한다. 짧은원문: **“특히 사용 횟수에 제한이 없어”**. 최신guide의일반설명이며고정7개template각각의기간규칙이나특정9월패킷을증명하지않는다.
- [L1J원Teleporter.xml](https://github.com/l1j-en/classic/blob/master/data/xml/NpcActions/Teleporter.xml):126부근NPC50015의`teleport island-gludin`/1500A는NPC이동정책이다. [C_NPCAction.java](https://github.com/l1j-en/classic/blob/master/src/l1j/server/server/clientpackets/C_NPCAction.java):886..954의`talking scroll trade`는NPC50112..50117·item40641 퀘스트교환이다. 클래식12273 편의텔레포트와동일시하지않는다. 기존카탈로그의token불일치를L1J전체부재라고확대하지않는다.
- `teleportURL`은[run382](../../local_server_rea_20261016/run382_npc_dialog_menu/handler_trace.md)의initializer29키에없어일반4ED4 fallback후보다. [M2_NPC_MENUS](M2_NPC_MENUS.md)와run403의lucas2는고정글루딘/말섬던전label+요금var다. 두버튼을임의사냥터로재명명하면안된다. 일반UML전체가동적action+label임의목록을표시한다는근거는확보하지않았다. raw133전용창대신NPC대화를채택할이유는없다.

**정책 판정:** 공식설명과맞추려면기본두루마리는반복사용·수량유지다. 매이동1개소모는공식설명과다른LOCAL선택이며사용자의별도요구없이원본정책으로주장하지않는다. 개별만료기간/비용/레벨/map제한·아이템획득/상자개봉은UNKNOWN이다. LOCAL can_stand/can_step검사는현맵데이터에서의사용가능판정이지원본정밀충돌/화면PASS가아니다. group10의비0맵행이원목록에존재해도현재서버지원이없으면이동전거절해야한다.

## 새 원문 조각과 남은 확인

원문검토를재사용할수있도록새조각SHA256만남긴다. 해당savedcode의offset은RVA-1000이며binary를문서에복제하지않았다.

| RVA [start,end) | SHA256 |
|---|---|
|4FE125..4FE139|278d345ce9d339e66fee2a00b933128a0d8712251915cf73479fdc2a346c286a|
|5027B0..502A06|f03cc2187b50f20ae766ade89d6b310c5f64e0d4564085436b8458e8f2650628|
|B243A0..B2442A|975190ece74cc583ff36be56d00d91c4abe3689479e41b229a056c9a2634b2e3|
|B248AB..B248F5|e01349da4609eccd37ae3c0c27670976cc111acdf174e68d6678e91f3b7496e3|
|B24B3B..B24B88|68da71474e108447de09f80af8d3e8a536622f93001402ca3bb2052ff1ab3ab6|
|B25C4B..B25C6A|964d45fe41393a497b8961cc1edf22a0802e008587f1c8a3f63bd439360d6cb2|
|B26810..B26D09 whole callback|939446288171f879aff5017a11b06721fd04ceb453cd33a152b648349fae8134|

**확인:** raw133로컬창, f53group10, 원95행과말섬시설8개, ordinalcapture,0960.f1/f13/f15/f16, 원close호출. **UNKNOWN:** 실제공식ItemInfo.f5,원창표시/입력/실송수신,정확기간·획득·상자개봉,공식서버선택검증/전환순서. 후속로컬packet시험은정상서버발급UID→STATIC_CLIENT_LIST확인→ordinal선택→실제0960라우터→이동/원수량유지→저장/재접속으로판정하고화면PASS로확대하지않는다. 원본게임실행/캡처금지는유지한다.

## 구현·패킷 시험 결과

`world_feature_talkscroll.py`와 `world_talkscroll.py`를 등록했고 `data/m2/talkscroll.json`에 원 group10의95행을 그대로 담았다. test_knight 최초 키트에12273×20을 추가하며 기존 저장은 보충하지 않는다. 기본은 raw133 로컬 창→0960.f13 선택→기존 이동·위치 저장 경로, 공식 안내에 따라 소모0이다. `SL_EXPERIMENT_TALKSCROLL=npc`는 기존 lucas1→teleportURL→lucas2의 실제 던전 버튼만 처리하는 별도 실험이며 임의 사냥터 목록이 아니다.

- [창고1→선착장7 봇](../runs/hunt-talkscroll-q1hvdjpr/summary.json): SL_TEST_PORT_BASE=20000, 정상 FIRST/로그인/기사 선택, 서버 발급UID65571·수량20, 잘못된 ordinal999999 요청만 거절한 뒤 같은 연결로 두 목적지 이동·각1칸 걷기, 같은UID·전체 가방/수량 유지, 정상 Quit와 fresh FIRST 재접속·위치/가방 복원까지13개 검사 SUCCESS. 두 epoch cleanup_complete=true, 실행 중 선정 소스 변경 없음. 클라이언트 로컬 목록은 정적 원문 메타데이터이며 실제 창 수신/클릭 성공이 아니다.
- [첫 허수아비8 실패](../runs/hunt-talkscroll-mkcp__e6/summary.json): 위치32525,32832 저장 뒤 기존 `NPC_EXPLICIT_SPR56_TEMPLATE0_ONLY` 오류로 응답 TIMEOUT. 확장된 M1 몬스터7종이 기존 npc.py의4쌍 허용 목록에 없어 시야 게시와 npc_ai에서 실패했다. 부분 위치 저장·원오류·실패 사본을 보존했다. npc.py는 사용자 허용 파일 밖이므로 수정하지 않았으며 이 목적지는 미완이다.
- [봇 자체 오류](../runs/hunt-talkscroll-aj3dx1i2/summary.json): 창고 도착 후 결과 기록 키 `name` 충돌로 실패. 봇 키를 수정한 뒤 위 별도 새 사본에서 재시험했으며 원실패를 보존했다.
- 관련 회귀: [10모듈108개 실행](../runs/talkscroll-20261027-related-unittest.stderr.log)은107개 통과·기존 town import격리 시험1개가 같은 프로세스의 선행 import 때문에 실패했다. [town 독립 실행14개](../runs/talkscroll-20261027-town-isolated.stderr.log)는 모두 통과했고 기존 시험을 수정하지 않았다. [기존 통합/맵 회귀15개](../runs/talkscroll-20261027-integration.stderr.log)도 통과했다. 신규 단위시험7개는 위108개에 포함된다. 모든 서버 시험은 단일 worker가 포트20000/22030에서 순차 실행했으며 소유 서버를 종료했다.

**당시 미완(2026-10-27):** 요청의 사냥터2곳은 해당 원본 아이템 목록과 달랐다. 사냥터용 LOCAL 연결의 후속 승인은 아래 2026-10-29 요청으로 받았고 별도 UI 대신 원 group8 아이템을 사용한다. npc.py의 당시 오류/실패 결과는 이번 수정이나 시험으로 해결됐다고 주장하지 않는다. 기간 만료 삭제·상자 개봉·원본 창/입력/정상 닫기는 미검증/미지원이며 원본 클라이언트 실행·캡처는 수행하지 않았다.

## 2026-10-29 전체 그룹 조사와 사냥터 연결

사용자 요청: 주요 사냥터를 포함한 기존 TeleportBook 그룹을 찾아 기사 키트의 두루마리에 연결한다. 원본 실행·커밋 없이 기존 추출 자료와 단위시험만 사용한다. 다음은 [teleport-ui-joins.json](../../all_table_semantics/travel_review/teleport-ui-joins.json)의 `group_id`별 집계이며, 종류는 `f4_KR` label을 요약한 분류다. [report.json:265](../../all_table_semantics/travel_review/report.json:265)의 전체 11그룹/704행/heading135/좌표569와 일치한다. 시작 줄부터 다음 그룹 직전까지가 각 그룹이다.

| 그룹 | 전체 / heading / 목적지 | 목적지 종류(label 요약) | 원표 시작 줄 |
|---:|---:|---|---:|
|1|63 / 12 / 51|마을 시설·말섬/본토 필드·던전 입구|3|
|2|60 / 10 / 50|시설·필드·던전 입구|1074|
|3|62 / 12 / 50|요정숲/화전민 등 시설·필드·던전 입구|2094|
|4|56 / 10 / 46|시설·필드·던전 입구|3148|
|5|9 / 0 / 9|마을 도착점|4100|
|6|7 / 0 / 7|개미굴·글루디오·기란·말섬·사막·요정숲·용계 던전 입구|4253|
|7|36 / 8 / 28|시설·북섬·던전 입구·공통 필드|4372|
|8|258 / 51 / 207|마을·필드·던전 실층·퀘스트/PC방/QA/운영자 맵 혼합|4984|
|9|55 / 9 / 46|주요 던전 실층·풍룡/황혼/용계/화룡 입구·몽환|9370|
|10|95 / 22 / 73|마을 서비스 중심|10305|
|11|3 / 1 / 2|오만의 탑 1층·11층|11920|

아래는 [items_all.json](../../../tools/local_original_session/data/catalog/items_all.json)의 raw `f4=133` 항목에 한정한 아이템→f53 대응이다. 다른 raw의 f53 숫자를 TeleportBook 그룹으로 해석하지 않았다. group1–5·7을 여는 raw133 아이템은 이 고정 카탈로그에서 발견되지 않았다(해당 카탈로그 범위의 부재).

| ID / 원명 | f5 icon | f53 | 카탈로그 줄 |
|---|---:|---:|---:|
|12086 / 이름 미확인 `desc16352`|20063|6|929|
|12163 / 슬기로운 두루마리|20018|8|982|
|12183, 12280 / 던전 기억책|3789|9|1002, 1089|
|12273, 12366, 12367, 12416 / 말하는 두루마리|20256|10|1082, 1175, 1176, 1223|
|12368, 12369, 12370 / 말하는 두루마리|20018|10|1177–1179|
|12454 / 픽시의 두루마리|20256|10|1260|
|15396 / 오만의 탑 이동 기억책|20625|11|1417|

공식 `work/official_data_refresh_20261028/raw/item/*.json` 613개에서는 위 두루마리/기억책 이름·ID의 직접 설명을 찾지 못했다. 수집 범위는 [OFFICIAL_VS_M1_DIFF.md:22](../../official_data_refresh_20261028/OFFICIAL_VS_M1_DIFF.md:22)와 [manifest.json:24287](../../official_data_refresh_20261028/manifest.json:24287)에 한정된다. 따라서 지정 폴더만으로 개별 기간·소비·획득 정책을 공식 대응할 수 없다. 기존 공식 초보자 가이드의 말하는 두루마리 일반 설명은 위 ‘공식/L1J와 정책 경계’ 절에 보존한다. 12163의 무소모/기간 없음은 이번 LOCAL 정책이며 공식 아이템 설명으로 확정하지 않는다.

**선정 근거(정책 판단/추론):** group8은 원표 ordinal165–168의 말섬 던전 입구·북섬·중앙·동쪽 사냥터(:7789–7840), ordinal177–179의 해골밭·포도밭·구울밭(:7993–8027), ordinal253–256의 수수밭·윈다우드 북쪽·용계 입구/던전 입구(:9285–9336), 실층인 말섬1층(ordinal13/map1, :5205)·글루디오1층(ordinal19/map7, :5307)을 포함한다. group9에는 위 말섬 필드·해골/포도/구울밭이 없어 사용자 목표의 넓은 필드 이동에는 group8이 더 적합하다.

**연결 경계:** RVA B24423/B248AB–B248EF의 template→f53→group 조회 때문에 서버의 목적지 표만 group8로 바꿔서는 원 UI가 바뀌지 않는다. 기사 첫 지급을12163으로 대체하고 템플릿별로 원그룹의 ordinal을 해석한다. group10의 기존 API/7종 아이템과 법사 지급은 유지한다. 기존 저장의12273은 그대로 group10이며 이 변경으로 자동 전환되지 않는다. heading도 ordinal을 차지하므로 원행을 삭제하거나 재번호하지 않는다. 원 좌표·맵은 보정하지 않는다.

미지원 맵은 기존 `realm.serves_map`, 맵 변경 시 `MapExp2`, 기존 `terrain.can_stand is True`를 모두 만족해야 허용한다([DUNGEON_MAPS.md:63](DUNGEON_MAPS.md:63)). 새 맵·스폰·이동 소유자는 추가하지 않는다. QA map18(원표:5494), 운영자 map668 등 미지원 목적지는 이동/소모/저장 전에 거절한다. 안내는 [CHAT_EVIDENCE.md:112](CHAT_EVIDENCE.md:112)의 source 지원 후보 `4EEA f1=12066/f2=본문1개`와 기존 [world_core_inventory.py:1021](../../../tools/local_original_session/world_core_inventory.py:1021)의 인코딩 패턴을 재사용하며 talkscroll 자체 outgoing 등록으로 소유한다. 실제 한국어 표시·하단 HUD 성공은 미검증이다.

**미확정:** group8 flag3/flag4=1/1(원표:4996–4997), group10=1/null(:10317–10318)이고 [fields.json:349](../../all_table_semantics/travel_review/fields.json:349)의 group.f4 의미는 UNKNOWN이다. 이번 표 연결로 원창 표시/입력·공식 발급 ItemInfo.f5·화면 이동·정상 close·기간/상자 개봉의 성공을 주장하지 않는다. 기존 지도 판정은 LOCAL 정적 지형이며 원본 충돌 전체가 아니다.

### 이번 구현과 단위시험 결과

변경은 `data/m2/talkscroll.json`(group8 원258행 추가/기존 group10 원95행 유지), `world_talkscroll.py`(템플릿별 group/ordinal 조회), `world_feature_talkscroll.py`(기존 이동 경로·거절 안내), `data/m1/starter.json`의 기사 두루마리 한 항목, 관련 `world_talkscroll_tests.py`/`hunt_bot_talkscroll.py` 및 이 문서에 한정했다. 금지 파일·원본 자원·사용자 저장·기존 실행 결과·커밋은 변경하지 않았다. group8의 207개 선택 행 모두를 사용 가능하다고 주장하지 않는다.

실행: `python -X utf8 -B -m unittest tools.local_original_session.world_talkscroll_tests -v` → **12 tests / 0.821s / OK, exit0**. 초기 구현 시험 12개도 OK였으며 최종 결과는 봇 기대값 수정 이후의 실행이다. [시험 코드](../../../tools/local_original_session/world_talkscroll_tests.py)는 실제 protobuf 파서와 S32 판정을 사용하되 HostContext/이동 확정/송신은 시험 대역이다. 따라서 선택 요청의 개발 단위시험이며 정식 패킷·화면 PASS가 아니다.

- group8 ordinal166/167/168/165 → `(0,32662,32846)` / `(0,32412,33020)` / `(0,32574,33100)` / `(0,32477,32853)` 이동 호출과 수량1 보존.
- MapExp0/1/3에서 다른 맵 거절; MapExp2 + 서비스 지원 + 실제 S32 통행 가능 시 ordinal19 → `(7,32802,32727)`, ordinal32 → `(19,32767,32767)` 이동 호출.
- 같은 ordinal0을 원12273/group10은 heading으로 거절하고12163/group8은 `(0,32573,32946)`으로 해석. 기존 group10 ordinal8/7과 NPC fallback 정책 회귀 유지.
- heading·알 수 없는 행·미지원 QA map18·원 group8 ordinal22/23의 실제 정적 통행 불가(map10 `32793,32764`, map11 `32743,32765`)는 안내만 생성하고 drain/이동/수량/위치 변경 없음. 원 좌표를 보정하지 않았다.
- 저장 실패 예외 전파와 가방 보존, 기사12163×1/raw133/icon20018 지급 및 법사12273×1 유지 확인.

봇은 새12163/group8/기본 ordinal166·167/안내 수신 기대값으로 수정했고 AST 구문검사 OK다. **봇·서버·포트·원본 게임은 이번 작업에서 실행하지 않았다.** 앞 절의 2026-10-27 패킷 성공은 당시 group10 소스/저장에만 귀속하며 이번 group8의 통합 성공으로 이전하지 않는다. 기존 저장의12273을 새12163으로 교체하는 마이그레이션도 수행하지 않았다.


## 2026-10-29 전체 목적지 개방과 실제 패킷 검증 마감

원표 **11그룹704행(heading135/목적지569)** 전부를 `talkscroll.json.native_destinations`에 원순서·원명·원맵·원좌표 그대로 보존했다. 원 raw133 아이템13종의 f53으로 그룹6/8/9/10/11을 연결했다. 그룹1–5/7은 대응 원 raw133 아이템이 없어 UI 진입을 발명하지 않는다. 기존 NPC fallback의 미확정 (0,32478,32853)은 원표 group8 ordinal165의 **(0,32477,32853)**으로 정리했다. 원 LC/자원/기존 사용자 저장/starter 지급목록은 변경하지 않았다.

실제 MapExp2 서버의 `realm.serves_map`과 그 서버의 `terrain.can_stand` 판정은 **open502 / map_not_served57 / coordinate_blocked10 / coordinate_data_missing0**, heading135다. open502 중 UI 아이템 연결268, 아이템 미확보234다. 후자를 실제 이동 PASS에 합산하지 않는다. 기존 이동·저장·소유·생존 guard를 유지했고 막힌 원좌표를 보정하지 않았다.

**비용·레벨:** TeleportBookTargetT f1..f5/원표에는 비용·레벨 피연산자가 없고 group.f3/f4 의미도 미확정이다. 원 비용/최저레벨은 **UNKNOWN/UNKNOWN**으로 보존한다. 동형 두루마리의 L1J 근거가 없어 기존 **LOCAL 비용0아데나·소모0·최저레벨없음**을 유지했다. NPC 텔레포터의1500아데나 등 별개 규칙을 옮기지 않았다. 아래 `U/U;0/none`은 원 비용/레벨 UNKNOWN/UNKNOWN; 현재 LOCAL 비용0/최저레벨없음이다. 만료/획득/상자/원 UI·입력·정상 close는 미확정이다.

### 실제 시험과 보존 범위

- [최종 summary](../../../_work/talkscroll/hunt-talkscroll-0dfbf4a51b7d/summary.json), [로그](../../../_work/talkscroll/bot-run13.log): **SUCCESS, 280 checks**. 같은 Source/시험저장 계보에서 연결268행 전체(그룹6:7, 8:140, 9:46, 10:73, 11:2) 이동 후 원 group8 ordinal166으로 정상 귀환1회, 총269회. 정상 FIRST/로그인/기사선택/월드→서버수신UID→실제0960 디코더/라우터/핸들러→wire/current/entity/저장 위치 일치→말섬 걷기→정상 Quit→fresh FIRST 재접속·위치/가방복원. 양 epoch cleanup_complete=true, 선정 소스 변경없음.
- 시작 저장은 새 시험기사이며 기존 kit append CAS로 각 원 그룹 대표1개를 pre-login 공급했다. 기존 던전 봇의 정상 성장 계산/저장(level60)을 재사용했다. 기존 키트의 다음UID를 저장하고 실제 수신UID로만 요청했다. live HP/피해/RNG·current/소유/거래/저장 guard를 조작하지 않았다. 자연획득/native inventory-memory는 미검증이다.
- 매 이동 전후 전체 저장 가방과 전체 wire 가방의 원문 불변을 각각 확인했다. 저장↔wire 의미비교는 기존 표시투영 f5(강화주문서0→7)/f18(수량문구)을 분리하고 나머지를 비교했다. 두루마리 raw133/icon/수량은 별도 수신검사했다. 실제 비용0은 아데나 포함 가방불변, 소모0은 같은UID/수량1 유지로 확인했다. 원 비용/레벨 UNKNOWN을 해소하는 근거는 아니다.
- [단위시험 최종 로그](../../../_work/talkscroll/unittest-final.log): **12 tests / 0.896s / OK**. 실제 protobuf/S32와 시험 대역을 사용하는 개발 검증이며 별도 UI PASS가 아니다. 최종 봇 역시 로컬 서버 소켓 행동 범위만 입증한다. 원본 클라이언트 전체 동등성/30분 milestone PASS는 없다.
- 이전 실패 run1..12의 `_work/talkscroll/bot-runN.log`와 시험사본은 보존했다. run1은 TMP/TEMP=_work/tmp 지정 뒤에도 Python3.13 mkdtemp private ACL로 summary 쓰기 실패, 소유 폴더 생성만 일반 mkdir로 수정했다. run2–4는 grant가 새 저장만 허용하는 API를 잘못 쓴 시험공급 오류를 기존 append CAS로 수정했다. run5–9는 f5/f18 표시투영/미디코드4EEA 비교를 수정했다. run10은 level1 기사72회 이동 후 실제 사망(LIVING_PC_REQUIRED), run11은259회 뒤 봇 과속(RATE_BOUND), run12는268회 뒤 공용 봇의 저장맵111 재로그인 허용맵 검사 실패다. 이를 소급 PASS로 바꾸지 않았다. summary가 있는 모든 실행은 cleanup_complete=true다.

실행 명령(PowerShell; 포트46000/48030, 실제 게임 클라이언트 실행없음):

```powershell
$env:TMP=(Resolve-Path _work/tmp).Path
$env:TEMP=$env:TMP
python -X utf8 -B -m unittest tools.local_original_session.world_talkscroll_tests -v
$env:SL_TEST_TIME_SCALE='10'
$env:SL_TEST_PORT_BASE='46000'
python -X utf8 -B tools/local_original_session/run_fast.py hunt_bot_talkscroll
```

[전체 JSON](../../../_work/talkscroll/destinations.json), [CSV](../../../_work/talkscroll/destinations.csv), [맵미지원57행/현재 자원확인](../../../_work/talkscroll/maps-not-served.json). 다음 목록의 `map_not_served`는 **서버 등록 미지원**이지 자원 부재 판정이 아니다. S32 자원이 이미 있으면 원좌표만 기존 parser로 읽었고, 자료가 없으면 can_stand는 UNKNOWN이다. 서버 등록과 원좌표 can_stand=True가 모두 필요하므로 “맵 데이터만 있으면 열린다”고 보장하지 않는다.

### 맵미지원57행의 이름·ID와 필요한 입력

|그룹/ordinal|원명|맵|현재 S32 chunk|원좌표 can_stand|필요 조건|
|---|---|---:|---:|---|---|
|8/15|군터의 집|3|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/27|켄트 내성|15|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/28|하딘의 연구소|16|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/29|네루파의 방|17|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/30|QA용 테스트맵 1|18|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/52|기란 내성|52|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/65|지저 내성|66|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/66|발라카스 둥지|67|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/81|무한대전 기란 제1경기장|90|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/82|무한대전 기란 제2경기장|91|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/83|무한대전 기란 제3경기장|92|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/84|무한대전 기란 제4경기장|93|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/85|무한대전 기란 제5경기장|94|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/86|무한대전 기란 제6경기장|95|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/87|무한대전 기란 제7경기장|96|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/88|무한대전 기란 제8경기장|97|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/89|무한대전 기란 제9경기장|98|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/90|무한대전 기란 제10경기장|99|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/92|언데드의 던전 (법사 30 퀘스트)|201|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/93|가짜 다크마르 은신처 (요정 30 퀘스트)|209|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/94|다크마르 은신처 (요정 30 퀘스트)|213|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/95|변종 거대 개미 던전 (군주 30 퀘스트)|217|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/96|시련의 던전 (기사 30 퀘스트)|221|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/97|비밀의 방 (기사 30 퀘스트)|237|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/98|정령의 심연 (요정 신규 45 퀘스트)|238|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/99|세피아의 정신 세계 (요정 50 퀘스트)|302|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/102|오염된 축복의 땅|244|35|True|서버 등록|
|8/103|타락한 축복의 땅|245|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/104|PC방 전용 오염된 축복의 땅|246|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/105|PC방 전용 타락한 축복의 땅|247|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/106|타락한 축복의 땅 : 봄|2450|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/107|타락한 축복의 땅(PC) : 봄|2451|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/108|타락한 축복의 땅 : 가을|2452|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/109|타락한 축복의 땅(PC) : 가을|2453|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/110|타락한 축복의 땅 : 겨울|2454|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/111|타락한 축복의 땅(PC) : 겨울|2455|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/113|지옥|666|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/114|감옥|667|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/115|운영자의 방|668|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/133|버림받은 자들의 땅|777|64|True|서버 등록|
|8/134|버림받은 자들의 땅:심연|779|16|True|서버 등록|
|8/135|버림받은 자들의 땅(PC)|778|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/136|버림받은 자들의 땅:심연(PC)|780|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/138|PC방 전용 던전 : 말섬 1층|7770|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/139|PC방 전용 던전 : 말섬 2층|7771|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/140|PC방 전용 던전 : 글루디오 던전 1층|7772|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/141|PC방 전용 던전 : 글루디오 던전 2층|7773|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/142|PC방 전용 던전 : 글루디오 던전 3층|7774|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/143|PC방 전용 던전 : 글루디오 던전 4층|7775|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/144|PC방 전용 던전 : 글루디오 던전 5층|7776|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/145|PC방 전용 던전 : 글루디오 던전 6층|7777|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/146|PC방 전용 던전 : 글루디오 던전 7층|7778|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/147|PC방 전용 던전 : 사막 던전 1층|7779|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/148|PC방 전용 던전 : 사막 던전 2층|7780|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/149|PC방 전용 던전 : 사막 던전 3층|7781|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/150|PC방 전용 던전 : 사막 던전 4층|7782|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|
|8/152|이벤트 화이트데이|10006|0|UNKNOWN|원맵 자원+서버 등록+원좌표 통행확인|

### 전체 원행 대조표

원순서·heading·원명을 보존했다. 공백명만 `(blank)`로 표시한다. UI 숫자는 해당 원 f53 그룹의 대표 template, `none`은 대응아이템 미확보다. heading은 선택/보류 수에 넣지 않는다. 상태 enum은 위 정의를 따른다.

|그룹|ordinal|원명|맵|x|y|지도 판정|UI|원 비용/레벨; LOCAL|
|---:|---:|---|---:|---:|---:|---|---|---|
|1|0|[말하는 섬]|-1|-|-|heading|none|-|
|1|1|여관|0|32599|32931|open|none|U/U;0/none|
|1|2|창고지기|0|32573|32946|open|none|U/U;0/none|
|1|3|혈맹 집행인|0|32579|32926|open|none|U/U;0/none|
|1|4|잡화 상인|0|32642|32949|open|none|U/U;0/none|
|1|5|오크족 상인|0|32432|32985|open|none|U/U;0/none|
|1|6|마법서 상인|0|32560|33088|open|none|U/U;0/none|
|1|7|펫 관리인|0|32447|32993|open|none|U/U;0/none|
|1|8|콜롯세움|0|32579|33004|open|none|U/U;0/none|
|1|9|말하는 섬 선착장|0|32632|32962|open|none|U/U;0/none|
|1|10|허수아비 수련장|0|32525|32832|open|none|U/U;0/none|
|1|11|말하는 섬 던전 입구|0|32477|32853|open|none|U/U;0/none|
|1|12|북섬|0|32662|32846|open|none|U/U;0/none|
|1|13|중앙 사냥터|0|32412|33020|open|none|U/U;0/none|
|1|14|동쪽 사냥터|0|32574|33100|open|none|U/U;0/none|
|1|15|(blank)|-1|-|-|heading|none|-|
|1|16|[글루딘 마을]|-1|-|-|heading|none|-|
|1|17|여관|4|32629|32751|open|none|U/U;0/none|
|1|18|창고지기|4|32603|32767|open|none|U/U;0/none|
|1|19|잡화 상인|4|32600|32751|open|none|U/U;0/none|
|1|20|콜롯세움|4|32573|32756|open|none|U/U;0/none|
|1|21|슬라임 경기장|4|32613|32699|open|none|U/U;0/none|
|1|22|글루디오 던전 입구|4|32717|32931|open|none|U/U;0/none|
|1|23|해골밭|4|32879|32653|open|none|U/U;0/none|
|1|24|포도밭|4|32865|32810|open|none|U/U;0/none|
|1|25|구울밭|4|32804|32921|open|none|U/U;0/none|
|1|26|(blank)|-1|-|-|heading|none|-|
|1|27|[기란 마을]|-1|-|-|heading|none|-|
|1|28|창고지기|4|33428|32815|open|none|U/U;0/none|
|1|29|잡화 상인|4|33444|32822|open|none|U/U;0/none|
|1|30|무기 상인|4|33388|32672|open|none|U/U;0/none|
|1|31|방어구 상인|4|33427|32755|open|none|U/U;0/none|
|1|32|물약 상인|4|33374|32731|open|none|U/U;0/none|
|1|33|대장장이|4|33470|32779|open|none|U/U;0/none|
|1|34|마법 연금술사|4|33397|32834|open|none|U/U;0/none|
|1|35|신녀|4|33451|32796|open|none|U/U;0/none|
|1|36|콜롯세움|4|33474|32727|open|none|U/U;0/none|
|1|37|기란 던전 입구|4|33316|33061|open|none|U/U;0/none|
|1|38|(blank)|-1|-|-|heading|none|-|
|1|39|[켄트 마을]|-1|-|-|heading|none|-|
|1|40|창고지기|4|33050|32788|open|none|U/U;0/none|
|1|41|잡화 상인|4|33062|32739|open|none|U/U;0/none|
|1|42|펫 관리인|4|33040|32749|open|none|U/U;0/none|
|1|43|(blank)|-1|-|-|heading|none|-|
|1|44|[우드벡 마을]|-1|-|-|heading|none|-|
|1|45|여관|4|32619|33174|open|none|U/U;0/none|
|1|46|창고지기|4|32624|33183|open|none|U/U;0/none|
|1|47|잡화 상인|4|32629|33200|open|none|U/U;0/none|
|1|48|펫 관리인|4|32607|33199|open|none|U/U;0/none|
|1|49|(blank)|-1|-|-|heading|none|-|
|1|50|[공통]|-1|-|-|heading|none|-|
|1|51|15레벨 퀘스트|4|33045|32755|open|none|U/U;0/none|
|1|52|30레벨 퀘스트|4|32645|33206|open|none|U/U;0/none|
|1|53|라우풀 신전|4|33117|32937|open|none|U/U;0/none|
|1|54|카오틱 신전|4|32664|32303|open|none|U/U;0/none|
|1|55|사막 오아시스|4|32860|33253|open|none|U/U;0/none|
|1|56|사막 던전 입구|4|32977|33508|open|none|U/U;0/none|
|1|57|축복의 땅|4|32626|32818|open|none|U/U;0/none|
|1|58|오크 숲 수수밭|4|32758|32374|open|none|U/U;0/none|
|1|59|윈다우드 성 북쪽 사냥터|4|32750|33397|open|none|U/U;0/none|
|1|60|용의 계곡 입구|4|33239|32453|open|none|U/U;0/none|
|1|61|용의 계곡 던전 입구|4|33411|32414|open|none|U/U;0/none|
|1|62|(blank)|-1|-|-|heading|none|-|
|2|0|[은기사 마을]|-1|-|-|heading|none|-|
|2|1|여관|4|33113|33381|open|none|U/U;0/none|
|2|2|창고지기|4|33074|33402|open|none|U/U;0/none|
|2|3|허수아비 수련장|4|33104|33332|open|none|U/U;0/none|
|2|4|잡화 상인|4|33094|33391|open|none|U/U;0/none|
|2|5|무기 방어구 상인|4|33092|33407|open|none|U/U;0/none|
|2|6|게라드|4|33098|33360|open|none|U/U;0/none|
|2|7|콜롯세움|4|33055|33362|open|none|U/U;0/none|
|2|8|(blank)|-1|-|-|heading|none|-|
|2|9|[말하는 섬]|-1|-|-|heading|none|-|
|2|10|여관|0|32599|32931|open|none|U/U;0/none|
|2|11|창고지기|0|32573|32946|open|none|U/U;0/none|
|2|12|잡화 상인|0|32642|32949|open|none|U/U;0/none|
|2|13|오크족 상인|0|32432|32985|open|none|U/U;0/none|
|2|14|마법서 상인|0|32560|33088|open|none|U/U;0/none|
|2|15|펫 관리인|0|32447|32993|open|none|U/U;0/none|
|2|16|콜롯세움|0|32579|33004|open|none|U/U;0/none|
|2|17|말하는 섬 선착장|0|32632|32962|open|none|U/U;0/none|
|2|18|허수아비 수련장|0|32525|32832|open|none|U/U;0/none|
|2|19|말하는 섬 던전 입구|0|32477|32853|open|none|U/U;0/none|
|2|20|북섬|0|32662|32846|open|none|U/U;0/none|
|2|21|중앙 사냥터|0|32412|33020|open|none|U/U;0/none|
|2|22|동쪽 사냥터|0|32574|33100|open|none|U/U;0/none|
|2|23|(blank)|-1|-|-|heading|none|-|
|2|24|[글루딘 마을]|-1|-|-|heading|none|-|
|2|25|여관|4|32629|32751|open|none|U/U;0/none|
|2|26|창고지기|4|32603|32767|open|none|U/U;0/none|
|2|27|잡화 상인|4|32600|32751|open|none|U/U;0/none|
|2|28|콜롯세움|4|32573|32756|open|none|U/U;0/none|
|2|29|슬라임 경기장|4|32613|32699|open|none|U/U;0/none|
|2|30|글루디오 던전 입구|4|32717|32931|open|none|U/U;0/none|
|2|31|해골밭|4|32879|32653|open|none|U/U;0/none|
|2|32|포도밭|4|32865|32810|open|none|U/U;0/none|
|2|33|구울밭|4|32804|32921|open|none|U/U;0/none|
|2|34|(blank)|-1|-|-|heading|none|-|
|2|35|[기란 마을]|-1|-|-|heading|none|-|
|2|36|창고지기|4|33428|32815|open|none|U/U;0/none|
|2|37|잡화 상인|4|33444|32822|open|none|U/U;0/none|
|2|38|무기 상인|4|33388|32672|open|none|U/U;0/none|
|2|39|방어구 상인|4|33427|32755|open|none|U/U;0/none|
|2|40|물약 상인|4|33374|32731|open|none|U/U;0/none|
|2|41|대장장이|4|33470|32779|open|none|U/U;0/none|
|2|42|마법 연금술사|4|33397|32834|open|none|U/U;0/none|
|2|43|신녀|4|33451|32796|open|none|U/U;0/none|
|2|44|콜롯세움|4|33474|32727|open|none|U/U;0/none|
|2|45|기란 던전 입구|4|33316|33061|open|none|U/U;0/none|
|2|46|(blank)|-1|-|-|heading|none|-|
|2|47|[공통]|-1|-|-|heading|none|-|
|2|48|15레벨 퀘스트|4|33125|33368|open|none|U/U;0/none|
|2|49|30레벨 퀘스트|4|32859|33248|open|none|U/U;0/none|
|2|50|라우풀 신전|4|33117|32937|open|none|U/U;0/none|
|2|51|카오틱 신전|4|32664|32303|open|none|U/U;0/none|
|2|52|사막 오아시스|4|32860|33253|open|none|U/U;0/none|
|2|53|사막 던전 입구|4|32977|33508|open|none|U/U;0/none|
|2|54|축복의 땅|4|32626|32818|open|none|U/U;0/none|
|2|55|오크 숲 수수밭|4|32758|32374|open|none|U/U;0/none|
|2|56|윈다우드 성 북쪽 사냥터|4|32750|33397|open|none|U/U;0/none|
|2|57|용의 계곡 입구|4|33239|32453|open|none|U/U;0/none|
|2|58|용의 계곡 던전 입구|4|33411|32414|open|none|U/U;0/none|
|2|59|(blank)|-1|-|-|heading|none|-|
|3|0|[요정 숲 마을]|-1|-|-|heading|none|-|
|3|1|창고지기|4|33065|32340|open|none|U/U;0/none|
|3|2|세계수|4|33049|32338|open|none|U/U;0/none|
|3|3|정령 마법|4|33077|32336|open|none|U/U;0/none|
|3|4|요정 숲 던전 입구|4|32938|32281|open|none|U/U;0/none|
|3|5|(blank)|-1|-|-|heading|none|-|
|3|6|[말하는 섬]|-1|-|-|heading|none|-|
|3|7|여관|0|32599|32931|open|none|U/U;0/none|
|3|8|창고지기|0|32573|32946|open|none|U/U;0/none|
|3|9|잡화 상인|0|32642|32949|open|none|U/U;0/none|
|3|10|오크족 상인|0|32432|32985|open|none|U/U;0/none|
|3|11|마법서 상인|0|32560|33088|open|none|U/U;0/none|
|3|12|펫 관리인|0|32447|32993|open|none|U/U;0/none|
|3|13|콜롯세움|0|32579|33004|open|none|U/U;0/none|
|3|14|말하는 섬 선착장|0|32632|32962|open|none|U/U;0/none|
|3|15|허수아비 수련장|0|32525|32832|open|none|U/U;0/none|
|3|16|말하는 섬 던전 입구|0|32477|32853|open|none|U/U;0/none|
|3|17|북섬|0|32662|32846|open|none|U/U;0/none|
|3|18|중앙 사냥터|0|32412|33020|open|none|U/U;0/none|
|3|19|동쪽 사냥터|0|32574|33100|open|none|U/U;0/none|
|3|20|(blank)|-1|-|-|heading|none|-|
|3|21|[글루딘 마을]|-1|-|-|heading|none|-|
|3|22|여관|4|32629|32751|open|none|U/U;0/none|
|3|23|창고지기|4|32603|32767|open|none|U/U;0/none|
|3|24|잡화 상인|4|32600|32751|open|none|U/U;0/none|
|3|25|콜롯세움|4|32573|32756|open|none|U/U;0/none|
|3|26|슬라임 경기장|4|32613|32699|open|none|U/U;0/none|
|3|27|글루디오 던전 입구|4|32717|32931|open|none|U/U;0/none|
|3|28|해골밭|4|32879|32653|open|none|U/U;0/none|
|3|29|포도밭|4|32865|32810|open|none|U/U;0/none|
|3|30|구울밭|4|32804|32921|open|none|U/U;0/none|
|3|31|(blank)|-1|-|-|heading|none|-|
|3|32|[기란 마을]|-1|-|-|heading|none|-|
|3|33|창고지기|4|33428|32815|open|none|U/U;0/none|
|3|34|잡화 상인|4|33444|32822|open|none|U/U;0/none|
|3|35|무기 상인|4|33388|32672|open|none|U/U;0/none|
|3|36|방어구 상인|4|33427|32755|open|none|U/U;0/none|
|3|37|물약 상인|4|33374|32731|open|none|U/U;0/none|
|3|38|대장장이|4|33470|32779|open|none|U/U;0/none|
|3|39|마법 연금술사|4|33397|32834|open|none|U/U;0/none|
|3|40|신녀|4|33451|32796|open|none|U/U;0/none|
|3|41|콜롯세움|4|33474|32727|open|none|U/U;0/none|
|3|42|기란 던전 입구|4|33316|33061|open|none|U/U;0/none|
|3|43|(blank)|-1|-|-|heading|none|-|
|3|44|[화전민 마을]|-1|-|-|heading|none|-|
|3|45|창고지기|4|32737|32446|open|none|U/U;0/none|
|3|46|잡화 상인|4|32752|32432|open|none|U/U;0/none|
|3|47|펫 관리인|4|32762|32450|open|none|U/U;0/none|
|3|48|(blank)|-1|-|-|heading|none|-|
|3|49|[공통]|-1|-|-|heading|none|-|
|3|50|15레벨 퀘스트|4|32744|32451|open|none|U/U;0/none|
|3|51|30레벨 퀘스트|4|33051|32340|open|none|U/U;0/none|
|3|52|라우풀 신전|4|33117|32937|open|none|U/U;0/none|
|3|53|카오틱 신전|4|32664|32303|open|none|U/U;0/none|
|3|54|사막 오아시스|4|32860|33253|open|none|U/U;0/none|
|3|55|사막 던전 입구|4|32977|33508|open|none|U/U;0/none|
|3|56|축복의 땅|4|32626|32818|open|none|U/U;0/none|
|3|57|오크 숲 수수밭|4|32758|32374|open|none|U/U;0/none|
|3|58|윈다우드 성 북쪽 사냥터|4|32750|33397|open|none|U/U;0/none|
|3|59|용의 계곡 입구|4|33239|32453|open|none|U/U;0/none|
|3|60|용의 계곡 던전 입구|4|33411|32414|open|none|U/U;0/none|
|3|61|(blank)|-1|-|-|heading|none|-|
|4|0|[말하는 섬]|-1|-|-|heading|none|-|
|4|1|여관|0|32599|32931|open|none|U/U;0/none|
|4|2|창고지기|0|32573|32946|open|none|U/U;0/none|
|4|3|잡화 상인|0|32642|32949|open|none|U/U;0/none|
|4|4|오크족 상인|0|32432|32985|open|none|U/U;0/none|
|4|5|마법서 상인|0|32560|33088|open|none|U/U;0/none|
|4|6|펫 관리인|0|32447|32993|open|none|U/U;0/none|
|4|7|콜롯세움|0|32579|33004|open|none|U/U;0/none|
|4|8|말하는 섬 선착장|0|32632|32962|open|none|U/U;0/none|
|4|9|허수아비 수련장|0|32525|32832|open|none|U/U;0/none|
|4|10|말하는 섬 던전 입구|0|32477|32853|open|none|U/U;0/none|
|4|11|북섬|0|32662|32846|open|none|U/U;0/none|
|4|12|중앙 사냥터|0|32412|33020|open|none|U/U;0/none|
|4|13|동쪽 사냥터|0|32574|33100|open|none|U/U;0/none|
|4|14|(blank)|-1|-|-|heading|none|-|
|4|15|[글루딘 마을]|-1|-|-|heading|none|-|
|4|16|여관|4|32629|32751|open|none|U/U;0/none|
|4|17|창고지기|4|32603|32767|open|none|U/U;0/none|
|4|18|잡화 상인|4|32600|32751|open|none|U/U;0/none|
|4|19|콜롯세움|4|32573|32756|open|none|U/U;0/none|
|4|20|슬라임 경기장|4|32613|32699|open|none|U/U;0/none|
|4|21|글루디오 던전 입구|4|32717|32931|open|none|U/U;0/none|
|4|22|해골밭|4|32879|32653|open|none|U/U;0/none|
|4|23|포도밭|4|32865|32810|open|none|U/U;0/none|
|4|24|구울밭|4|32804|32921|open|none|U/U;0/none|
|4|25|(blank)|-1|-|-|heading|none|-|
|4|26|[기란 마을]|-1|-|-|heading|none|-|
|4|27|창고지기|4|33428|32815|open|none|U/U;0/none|
|4|28|잡화 상인|4|33444|32822|open|none|U/U;0/none|
|4|29|무기 상인|4|33388|32672|open|none|U/U;0/none|
|4|30|방어구 상인|4|33427|32755|open|none|U/U;0/none|
|4|31|물약 상인|4|33374|32731|open|none|U/U;0/none|
|4|32|대장장이|4|33470|32779|open|none|U/U;0/none|
|4|33|마법 연금술사|4|33397|32834|open|none|U/U;0/none|
|4|34|신녀|4|33451|32796|open|none|U/U;0/none|
|4|35|콜롯세움|4|33474|32727|open|none|U/U;0/none|
|4|36|기란 던전 입구|4|33316|33061|open|none|U/U;0/none|
|4|37|(blank)|-1|-|-|heading|none|-|
|4|38|[화전민 마을]|-1|-|-|heading|none|-|
|4|39|창고지기|4|32737|32446|open|none|U/U;0/none|
|4|40|잡화 상인|4|32752|32432|open|none|U/U;0/none|
|4|41|펫 관리인|4|32762|32450|open|none|U/U;0/none|
|4|42|(blank)|-1|-|-|heading|none|-|
|4|43|[공통]|-1|-|-|heading|none|-|
|4|44|15레벨 퀘스트|0|32585|32929|open|none|U/U;0/none|
|4|45|30레벨 퀘스트|0|32560|33088|open|none|U/U;0/none|
|4|46|라우풀 신전|4|33117|32937|open|none|U/U;0/none|
|4|47|카오틱 신전|4|32664|32303|open|none|U/U;0/none|
|4|48|사막 오아시스|4|32860|33253|open|none|U/U;0/none|
|4|49|사막 던전 입구|4|32977|33508|open|none|U/U;0/none|
|4|50|축복의 땅|4|32626|32818|open|none|U/U;0/none|
|4|51|오크 숲 수수밭|4|32758|32374|open|none|U/U;0/none|
|4|52|윈다우드 성 북쪽 사냥터|4|32750|33397|open|none|U/U;0/none|
|4|53|용의 계곡 입구|4|33239|32453|open|none|U/U;0/none|
|4|54|용의 계곡 던전 입구|4|33411|32414|open|none|U/U;0/none|
|4|55|(blank)|-1|-|-|heading|none|-|
|5|0|글루딘 마을|4|32603|32767|open|none|U/U;0/none|
|5|1|기란 마을|4|33428|32815|open|none|U/U;0/none|
|5|2|말하는 섬 마을|0|32573|32946|open|none|U/U;0/none|
|5|3|요정 숲 마을|4|33049|32338|open|none|U/U;0/none|
|5|4|우드벡 마을|4|32624|33183|open|none|U/U;0/none|
|5|5|은기사 마을|4|33074|33402|open|none|U/U;0/none|
|5|6|켄트 마을|4|33050|32788|open|none|U/U;0/none|
|5|7|화전민 마을|4|32737|32446|open|none|U/U;0/none|
|5|8|하이네 마을|4|33612|33234|open|none|U/U;0/none|
|6|0|개미굴 던전|4|32851|33288|open|12086|U/U;0/none|
|6|1|글루디오 던전|4|32720|32937|open|12086|U/U;0/none|
|6|2|기란 던전|4|33317|33061|open|12086|U/U;0/none|
|6|3|말하는 섬 던전|0|32477|32853|open|12086|U/U;0/none|
|6|4|사막 던전|4|32977|33508|open|12086|U/U;0/none|
|6|5|요정 숲 던전|4|32938|32281|open|12086|U/U;0/none|
|6|6|용의 계곡 던전|4|33365|32385|open|12086|U/U;0/none|
|7|0|[말하는 섬]|-1|-|-|heading|none|-|
|7|1|여관|0|32599|32931|open|none|U/U;0/none|
|7|2|창고지기|0|32573|32946|open|none|U/U;0/none|
|7|3|텔레포터|0|32580|32929|open|none|U/U;0/none|
|7|4|잡화 상인|0|32642|32949|open|none|U/U;0/none|
|7|5|오크족 상인|0|32432|32985|open|none|U/U;0/none|
|7|6|마법서 상인|0|32560|33088|open|none|U/U;0/none|
|7|7|말하는 섬 던전 입구|0|32477|32853|open|none|U/U;0/none|
|7|8|북섬|0|32662|32846|open|none|U/U;0/none|
|7|9|(blank)|-1|-|-|heading|none|-|
|7|10|[글루딘 마을]|-1|-|-|heading|none|-|
|7|11|여관|4|32629|32751|open|none|U/U;0/none|
|7|12|창고지기|4|32603|32767|open|none|U/U;0/none|
|7|13|텔레포터|4|32614|32729|open|none|U/U;0/none|
|7|14|잡화 상인|4|32600|32751|open|none|U/U;0/none|
|7|15|슬라임 경기장|4|32613|32699|open|none|U/U;0/none|
|7|16|글루디오 던전 입구|4|32717|32931|open|none|U/U;0/none|
|7|17|(blank)|-1|-|-|heading|none|-|
|7|18|[기란 마을]|-1|-|-|heading|none|-|
|7|19|창고지기|4|33428|32815|open|none|U/U;0/none|
|7|20|텔레포터|4|33437|32798|open|none|U/U;0/none|
|7|21|잡화 상인|4|33444|32822|open|none|U/U;0/none|
|7|22|무기 상인|4|33388|32672|open|none|U/U;0/none|
|7|23|방어구 상인|4|33427|32755|open|none|U/U;0/none|
|7|24|물약 상인|4|33374|32731|open|none|U/U;0/none|
|7|25|기란 던전 입구|4|33316|33061|open|none|U/U;0/none|
|7|26|용의 계곡 입구|4|33239|32453|open|none|U/U;0/none|
|7|27|용의 계곡 던전 입구|4|33411|32414|open|none|U/U;0/none|
|7|28|(blank)|-1|-|-|heading|none|-|
|7|29|[공통]|-1|-|-|heading|none|-|
|7|30|라우풀 신전|4|33117|32937|open|none|U/U;0/none|
|7|31|카오틱 신전|4|32664|32303|open|none|U/U;0/none|
|7|32|사막 오아시스|4|32860|33253|open|none|U/U;0/none|
|7|33|사막 던전 입구|4|32977|33508|open|none|U/U;0/none|
|7|34|축복의 땅|4|32626|32818|open|none|U/U;0/none|
|7|35|(blank)|-1|-|-|heading|none|-|
|8|0|말하는 섬 마을|0|32573|32946|open|12163|U/U;0/none|
|8|1|글루디오 마을|4|32615|32786|open|12163|U/U;0/none|
|8|2|기란 마을|4|33429|32816|open|12163|U/U;0/none|
|8|3|오렌 마을|4|34044|32278|open|12163|U/U;0/none|
|8|4|아덴 마을|4|33925|33351|open|12163|U/U;0/none|
|8|5|요정숲|4|33048|32347|open|12163|U/U;0/none|
|8|6|우즈벡 마을|4|32636|33201|open|12163|U/U;0/none|
|8|7|웰던 마을|4|33715|32501|open|12163|U/U;0/none|
|8|8|은기사 마을|4|33107|33358|open|12163|U/U;0/none|
|8|9|켄트 마을|4|33057|32762|open|12163|U/U;0/none|
|8|10|하이네 마을|4|33607|33239|open|12163|U/U;0/none|
|8|11|화전민 마을|4|32741|32449|open|12163|U/U;0/none|
|8|12|(blank)|-1|-|-|heading|12163|-|
|8|13|말하는섬 던전 1층|1|32669|32811|open|12163|U/U;0/none|
|8|14|말하는섬 던전 2층|2|32745|32843|open|12163|U/U;0/none|
|8|15|군터의 집|3|32670|32789|map_not_served|12163|U/U;0/none|
|8|16|말하는섬 행 배 내부|5|32736|32798|coordinate_blocked|12163|U/U;0/none|
|8|17|글루디오 행 배 내부|6|32733|32794|open|12163|U/U;0/none|
|8|18|(blank)|-1|-|-|heading|12163|-|
|8|19|글루디오 던전 1층|7|32802|32727|open|12163|U/U;0/none|
|8|20|글루디오 던전 2층|8|32736|32777|open|12163|U/U;0/none|
|8|21|글루디오 던전 3층|9|32751|32739|open|12163|U/U;0/none|
|8|22|글루디오 던전 4층|10|32793|32764|coordinate_blocked|12163|U/U;0/none|
|8|23|글루디오 던전 5층|11|32743|32765|coordinate_blocked|12163|U/U;0/none|
|8|24|글루디오 던전 6층|12|32802|32728|open|12163|U/U;0/none|
|8|25|글루디오 던전 7층|13|32724|32786|open|12163|U/U;0/none|
|8|26|(blank)|-1|-|-|heading|12163|-|
|8|27|켄트 내성|15|32738|32783|map_not_served|12163|U/U;0/none|
|8|28|하딘의 연구소|16|32730|32788|map_not_served|12163|U/U;0/none|
|8|29|네루파의 방|17|32741|32787|map_not_served|12163|U/U;0/none|
|8|30|QA용 테스트맵 1|18|32729|32806|map_not_served|12163|U/U;0/none|
|8|31|(blank)|-1|-|-|heading|12163|-|
|8|32|요정 던전 1층|19|32767|32767|open|12163|U/U;0/none|
|8|33|요정 던전 2층|20|32767|32767|open|12163|U/U;0/none|
|8|34|요정 던전 3층|21|32767|32767|open|12163|U/U;0/none|
|8|35|(blank)|-1|-|-|heading|12163|-|
|8|36|사막 던전 1층|25|32767|32768|open|12163|U/U;0/none|
|8|37|사막 던전 2층|26|32799|32799|open|12163|U/U;0/none|
|8|38|사막 던전 3층|27|32799|32799|open|12163|U/U;0/none|
|8|39|사막 던전 4층|28|32799|32799|open|12163|U/U;0/none|
|8|40|윈다우드 내성|29|32737|32783|open|12163|U/U;0/none|
|8|41|(blank)|-1|-|-|heading|12163|-|
|8|42|용의 계곡 던전 1층|30|32735|32735|coordinate_blocked|12163|U/U;0/none|
|8|43|용의 계곡 던전 2층|31|32735|32735|coordinate_blocked|12163|U/U;0/none|
|8|44|용의 계곡 던전 3층|32|32671|32799|open|12163|U/U;0/none|
|8|45|용의 계곡 던전 4층|33|32671|32799|coordinate_blocked|12163|U/U;0/none|
|8|46|용의 계곡 던전 5층|35|32671|32799|open|12163|U/U;0/none|
|8|47|용의 계곡 던전 6층|36|32671|32799|open|12163|U/U;0/none|
|8|48|(blank)|-1|-|-|heading|12163|-|
|8|49|개미굴 던전 1층|43|32767|32767|coordinate_blocked|12163|U/U;0/none|
|8|50|개미굴 던전 2층|51|32671|32799|open|12163|U/U;0/none|
|8|51|(blank)|-1|-|-|heading|12163|-|
|8|52|기란 내성|52|32732|32789|map_not_served|12163|U/U;0/none|
|8|53|기란 던전 1층|53|32799|32799|open|12163|U/U;0/none|
|8|54|기란 던전 2층|54|32799|32799|open|12163|U/U;0/none|
|8|55|기란 던전 3층|55|32735|32735|open|12163|U/U;0/none|
|8|56|기란 던전 4층|56|32799|32799|open|12163|U/U;0/none|
|8|57|(blank)|-1|-|-|heading|12163|-|
|8|58|지하 수로 1층|59|32736|32862|open|12163|U/U;0/none|
|8|59|지하 수로 2층|60|32736|32862|open|12163|U/U;0/none|
|8|60|지하 수로 3층|61|32736|32862|open|12163|U/U;0/none|
|8|61|에바의 성지|62|32741|32814|open|12163|U/U;0/none|
|8|62|에바왕국|63|32799|32896|open|12163|U/U;0/none|
|8|63|파푸리온 둥지|65|32795|32813|open|12163|U/U;0/none|
|8|64|(blank)|-1|-|-|heading|12163|-|
|8|65|지저 내성|66|32865|32808|map_not_served|12163|U/U;0/none|
|8|66|발라카스 둥지|67|32705|32828|map_not_served|12163|U/U;0/none|
|8|67|(blank)|-1|-|-|heading|12163|-|
|8|68|얼음 수정 동굴 1층|72|32767|32831|open|12163|U/U;0/none|
|8|69|얼음 수정 동굴 2층|73|32767|32831|coordinate_blocked|12163|U/U;0/none|
|8|70|얼음 수정 동굴 3층|74|32767|32895|open|12163|U/U;0/none|
|8|71|(blank)|-1|-|-|heading|12163|-|
|8|72|상아탑 1층|75|32765|32866|open|12163|U/U;0/none|
|8|73|상아탑 2층|76|32793|32811|open|12163|U/U;0/none|
|8|74|상아탑 3층|77|32769|32796|open|12163|U/U;0/none|
|8|75|상아탑 4층|78|32895|32767|open|12163|U/U;0/none|
|8|76|상아탑 5층|79|32767|32831|open|12163|U/U;0/none|
|8|77|상아탑 6층|80|32767|32831|coordinate_blocked|12163|U/U;0/none|
|8|78|상아탑 7층|81|32767|32831|coordinate_blocked|12163|U/U;0/none|
|8|79|상아탑 8층|82|32703|32832|open|12163|U/U;0/none|
|8|80|(blank)|-1|-|-|heading|12163|-|
|8|81|무한대전 기란 제1경기장|90|33498|32727|map_not_served|12163|U/U;0/none|
|8|82|무한대전 기란 제2경기장|91|33498|32727|map_not_served|12163|U/U;0/none|
|8|83|무한대전 기란 제3경기장|92|33498|32727|map_not_served|12163|U/U;0/none|
|8|84|무한대전 기란 제4경기장|93|33498|32727|map_not_served|12163|U/U;0/none|
|8|85|무한대전 기란 제5경기장|94|33498|32727|map_not_served|12163|U/U;0/none|
|8|86|무한대전 기란 제6경기장|95|33498|32727|map_not_served|12163|U/U;0/none|
|8|87|무한대전 기란 제7경기장|96|33498|32727|map_not_served|12163|U/U;0/none|
|8|88|무한대전 기란 제8경기장|97|33498|32727|map_not_served|12163|U/U;0/none|
|8|89|무한대전 기란 제9경기장|98|33498|32727|map_not_served|12163|U/U;0/none|
|8|90|무한대전 기란 제10경기장|99|33498|32727|map_not_served|12163|U/U;0/none|
|8|91|(blank)|-1|-|-|heading|12163|-|
|8|92|언데드의 던전 (법사 30 퀘스트)|201|32873|32912|map_not_served|12163|U/U;0/none|
|8|93|가짜 다크마르 은신처 (요정 30 퀘스트)|209|32736|32797|map_not_served|12163|U/U;0/none|
|8|94|다크마르 은신처 (요정 30 퀘스트)|213|32727|32790|map_not_served|12163|U/U;0/none|
|8|95|변종 거대 개미 던전 (군주 30 퀘스트)|217|32740|32795|map_not_served|12163|U/U;0/none|
|8|96|시련의 던전 (기사 30 퀘스트)|221|32775|32777|map_not_served|12163|U/U;0/none|
|8|97|비밀의 방 (기사 30 퀘스트)|237|32745|32806|map_not_served|12163|U/U;0/none|
|8|98|정령의 심연 (요정 신규 45 퀘스트)|238|32767|32767|map_not_served|12163|U/U;0/none|
|8|99|세피아의 정신 세계 (요정 50 퀘스트)|302|32742|32872|map_not_served|12163|U/U;0/none|
|8|100|(blank)|-1|-|-|heading|12163|-|
|8|101|몽환의 섬|303|32797|32843|open|12163|U/U;0/none|
|8|102|오염된 축복의 땅|244|32987|32811|map_not_served|12163|U/U;0/none|
|8|103|타락한 축복의 땅|245|32987|32811|map_not_served|12163|U/U;0/none|
|8|104|PC방 전용 오염된 축복의 땅|246|32987|32811|map_not_served|12163|U/U;0/none|
|8|105|PC방 전용 타락한 축복의 땅|247|32987|32811|map_not_served|12163|U/U;0/none|
|8|106|타락한 축복의 땅 : 봄|2450|32987|32811|map_not_served|12163|U/U;0/none|
|8|107|타락한 축복의 땅(PC) : 봄|2451|32987|32811|map_not_served|12163|U/U;0/none|
|8|108|타락한 축복의 땅 : 가을|2452|32987|32811|map_not_served|12163|U/U;0/none|
|8|109|타락한 축복의 땅(PC) : 가을|2453|32987|32811|map_not_served|12163|U/U;0/none|
|8|110|타락한 축복의 땅 : 겨울|2454|32987|32811|map_not_served|12163|U/U;0/none|
|8|111|타락한 축복의 땅(PC) : 겨울|2455|32987|32811|map_not_served|12163|U/U;0/none|
|8|112|(blank)|-1|-|-|heading|12163|-|
|8|113|지옥|666|32776|32759|map_not_served|12163|U/U;0/none|
|8|114|감옥|667|32766|32808|map_not_served|12163|U/U;0/none|
|8|115|운영자의 방|668|32744|32792|map_not_served|12163|U/U;0/none|
|8|116|(blank)|-1|-|-|heading|12163|-|
|8|117|[켄트성]|-1|-|-|heading|12163|-|
|8|118|켄트성 남문|4|33100|32772|open|12163|U/U;0/none|
|8|119|켄트성 동문|4|33152|32808|open|12163|U/U;0/none|
|8|120|켄트성 내성문(수호탑)|4|33170|32769|open|12163|U/U;0/none|
|8|121|(blank)|-1|-|-|heading|12163|-|
|8|122|[윈다우드성]|-1|-|-|heading|12163|-|
|8|123|윈다우드성 남문|4|32579|33411|open|12163|U/U;0/none|
|8|124|윈다우드성 동문|4|32625|33437|open|12163|U/U;0/none|
|8|125|윈다우드성 내성문(수호탑)|4|32675|33402|open|12163|U/U;0/none|
|8|126|(blank)|-1|-|-|heading|12163|-|
|8|127|[오크요새]|-1|-|-|heading|12163|-|
|8|128|오크요새 남문|4|32782|32333|open|12163|U/U;0/none|
|8|129|오크요새 북문|4|32829|32291|open|12163|U/U;0/none|
|8|130|오크요새 내성문(수호탑)|4|32803|32279|open|12163|U/U;0/none|
|8|131|(blank)|-1|-|-|heading|12163|-|
|8|132|[시간제 던전]|-1|-|-|heading|12163|-|
|8|133|버림받은 자들의 땅|777|32554|32952|map_not_served|12163|U/U;0/none|
|8|134|버림받은 자들의 땅:심연|779|32554|32952|map_not_served|12163|U/U;0/none|
|8|135|버림받은 자들의 땅(PC)|778|32554|32952|map_not_served|12163|U/U;0/none|
|8|136|버림받은 자들의 땅:심연(PC)|780|32554|32952|map_not_served|12163|U/U;0/none|
|8|137|(blank)|-1|-|-|heading|12163|-|
|8|138|PC방 전용 던전 : 말섬 1층|7770|32669|32811|map_not_served|12163|U/U;0/none|
|8|139|PC방 전용 던전 : 말섬 2층|7771|32745|32843|map_not_served|12163|U/U;0/none|
|8|140|PC방 전용 던전 : 글루디오 던전 1층|7772|32802|32727|map_not_served|12163|U/U;0/none|
|8|141|PC방 전용 던전 : 글루디오 던전 2층|7773|32736|32777|map_not_served|12163|U/U;0/none|
|8|142|PC방 전용 던전 : 글루디오 던전 3층|7774|32751|32739|map_not_served|12163|U/U;0/none|
|8|143|PC방 전용 던전 : 글루디오 던전 4층|7775|32793|32764|map_not_served|12163|U/U;0/none|
|8|144|PC방 전용 던전 : 글루디오 던전 5층|7776|32743|32765|map_not_served|12163|U/U;0/none|
|8|145|PC방 전용 던전 : 글루디오 던전 6층|7777|32802|32728|map_not_served|12163|U/U;0/none|
|8|146|PC방 전용 던전 : 글루디오 던전 7층|7778|32724|32786|map_not_served|12163|U/U;0/none|
|8|147|PC방 전용 던전 : 사막 던전 1층|7779|32767|32768|map_not_served|12163|U/U;0/none|
|8|148|PC방 전용 던전 : 사막 던전 2층|7780|32799|32799|map_not_served|12163|U/U;0/none|
|8|149|PC방 전용 던전 : 사막 던전 3층|7781|32799|32799|map_not_served|12163|U/U;0/none|
|8|150|PC방 전용 던전 : 사막 던전 4층|7782|32799|32799|map_not_served|12163|U/U;0/none|
|8|151|(blank)|-1|-|-|heading|12163|-|
|8|152|이벤트 화이트데이|10006|32707|32959|map_not_served|12163|U/U;0/none|
|8|153|(blank)|-1|-|-|heading|12163|-|
|8|154|[말하는 섬]|-1|-|-|heading|12163|-|
|8|155|여관|0|32599|32931|open|12163|U/U;0/none|
|8|156|창고지기|0|32573|32946|open|12163|U/U;0/none|
|8|157|혈맹 집행인|0|32579|32926|open|12163|U/U;0/none|
|8|158|잡화 상인|0|32642|32949|open|12163|U/U;0/none|
|8|159|오크족 상인|0|32432|32985|open|12163|U/U;0/none|
|8|160|마법서 상인|0|32560|33088|open|12163|U/U;0/none|
|8|161|펫 관리인|0|32447|32993|open|12163|U/U;0/none|
|8|162|콜롯세움|0|32579|33004|open|12163|U/U;0/none|
|8|163|말하는 섬 선착장|0|32632|32962|open|12163|U/U;0/none|
|8|164|허수아비 수련장|0|32525|32832|open|12163|U/U;0/none|
|8|165|말하는 섬 던전 입구|0|32477|32853|open|12163|U/U;0/none|
|8|166|북섬|0|32662|32846|open|12163|U/U;0/none|
|8|167|중앙 사냥터|0|32412|33020|open|12163|U/U;0/none|
|8|168|동쪽 사냥터|0|32574|33100|open|12163|U/U;0/none|
|8|169|(blank)|-1|-|-|heading|12163|-|
|8|170|[글루딘 마을]|-1|-|-|heading|12163|-|
|8|171|여관|4|32629|32751|open|12163|U/U;0/none|
|8|172|창고지기|4|32603|32767|open|12163|U/U;0/none|
|8|173|잡화 상인|4|32600|32751|open|12163|U/U;0/none|
|8|174|콜롯세움|4|32573|32756|open|12163|U/U;0/none|
|8|175|슬라임 경기장|4|32613|32699|open|12163|U/U;0/none|
|8|176|글루디오 던전 입구|4|32717|32931|open|12163|U/U;0/none|
|8|177|해골밭|4|32879|32653|open|12163|U/U;0/none|
|8|178|포도밭|4|32865|32810|open|12163|U/U;0/none|
|8|179|구울밭|4|32804|32921|open|12163|U/U;0/none|
|8|180|(blank)|-1|-|-|heading|12163|-|
|8|181|[기란 마을]|-1|-|-|heading|12163|-|
|8|182|창고지기|4|33428|32815|open|12163|U/U;0/none|
|8|183|잡화 상인|4|33444|32822|open|12163|U/U;0/none|
|8|184|무기 상인|4|33388|32672|open|12163|U/U;0/none|
|8|185|방어구 상인|4|33427|32755|open|12163|U/U;0/none|
|8|186|물약 상인|4|33374|32731|open|12163|U/U;0/none|
|8|187|대장장이|4|33470|32779|open|12163|U/U;0/none|
|8|188|마법 연금술사|4|33397|32834|open|12163|U/U;0/none|
|8|189|신녀|4|33451|32796|open|12163|U/U;0/none|
|8|190|콜롯세움|4|33474|32727|open|12163|U/U;0/none|
|8|191|기란 던전 입구|4|33316|33061|open|12163|U/U;0/none|
|8|192|(blank)|-1|-|-|heading|12163|-|
|8|193|[오렌 마을]|-1|-|-|heading|12163|-|
|8|194|창고지기|4|34052|32285|open|12163|U/U;0/none|
|8|195|여관|4|34063|32256|open|12163|U/U;0/none|
|8|196|텔레포터|4|34061|32280|open|12163|U/U;0/none|
|8|197|잡화 상인|4|34055|32297|open|12163|U/U;0/none|
|8|198|무기 방어구 상인|4|34064|32307|open|12163|U/U;0/none|
|8|199|펫 관리인|4|34076|32296|open|12163|U/U;0/none|
|8|200|(blank)|-1|-|-|heading|12163|-|
|8|201|[켄트 마을]|-1|-|-|heading|12163|-|
|8|202|창고지기|4|33050|32788|open|12163|U/U;0/none|
|8|203|잡화 상인|4|33062|32739|open|12163|U/U;0/none|
|8|204|펫 관리인|4|33040|32749|open|12163|U/U;0/none|
|8|205|(blank)|-1|-|-|heading|12163|-|
|8|206|[우드벡 마을]|-1|-|-|heading|12163|-|
|8|207|여관|4|32619|33174|open|12163|U/U;0/none|
|8|208|창고지기|4|32624|33183|open|12163|U/U;0/none|
|8|209|잡화 상인|4|32629|33200|open|12163|U/U;0/none|
|8|210|펫 관리인|4|32607|33199|open|12163|U/U;0/none|
|8|211|(blank)|-1|-|-|heading|12163|-|
|8|212|[은기사 마을]|-1|-|-|heading|12163|-|
|8|213|여관|4|33113|33381|open|12163|U/U;0/none|
|8|214|창고지기|4|33074|33402|open|12163|U/U;0/none|
|8|215|허수아비 수련장|4|33104|33332|open|12163|U/U;0/none|
|8|216|잡화 상인|4|33094|33391|open|12163|U/U;0/none|
|8|217|무기 방어구 상인|4|33092|33407|open|12163|U/U;0/none|
|8|218|게라드|4|33098|33360|open|12163|U/U;0/none|
|8|219|콜롯세움|4|33055|33362|open|12163|U/U;0/none|
|8|220|(blank)|-1|-|-|heading|12163|-|
|8|221|[요정 숲 마을]|-1|-|-|heading|12163|-|
|8|222|창고지기|4|33065|32340|open|12163|U/U;0/none|
|8|223|세계수|4|33049|32338|open|12163|U/U;0/none|
|8|224|정령 마법|4|33077|32336|open|12163|U/U;0/none|
|8|225|요정 숲 던전 입구|4|32938|32281|open|12163|U/U;0/none|
|8|226|(blank)|-1|-|-|heading|12163|-|
|8|227|[화전민 마을]|-1|-|-|heading|12163|-|
|8|228|창고지기|4|32737|32446|open|12163|U/U;0/none|
|8|229|잡화 상인|4|32752|32432|open|12163|U/U;0/none|
|8|230|펫 관리인|4|32762|32450|open|12163|U/U;0/none|
|8|231|(blank)|-1|-|-|heading|12163|-|
|8|232|[하이네 마을]|-1|-|-|heading|12163|-|
|8|233|창고지기|4|33601|33231|open|12163|U/U;0/none|
|8|234|여관|4|33596|33276|open|12163|U/U;0/none|
|8|235|텔레포터|4|33614|33252|open|12163|U/U;0/none|
|8|236|잡화 상인|4|33637|33287|open|12163|U/U;0/none|
|8|237|무기 방어구 상인|4|33622|33287|open|12163|U/U;0/none|
|8|238|펫 관리인|4|33646|33410|open|12163|U/U;0/none|
|8|239|(blank)|-1|-|-|heading|12163|-|
|8|240|[웰던 마을]|-1|-|-|heading|12163|-|
|8|241|창고지기|4|33726|32487|open|12163|U/U;0/none|
|8|242|텔레포터|4|33707|32497|open|12163|U/U;0/none|
|8|243|잡화 상인|4|33738|32496|open|12163|U/U;0/none|
|8|244|무기 상인|4|33710|32518|open|12163|U/U;0/none|
|8|245|펫 관리인|4|33692|32501|open|12163|U/U;0/none|
|8|246|(blank)|-1|-|-|heading|12163|-|
|8|247|[공통]|-1|-|-|heading|12163|-|
|8|248|라우풀 신전|4|33117|32937|open|12163|U/U;0/none|
|8|249|카오틱 신전|4|32664|32303|open|12163|U/U;0/none|
|8|250|사막 오아시스|4|32860|33253|open|12163|U/U;0/none|
|8|251|사막 던전 입구|4|32977|33508|open|12163|U/U;0/none|
|8|252|축복의 땅|4|32626|32818|open|12163|U/U;0/none|
|8|253|오크 숲 수수밭|4|32758|32374|open|12163|U/U;0/none|
|8|254|윈다우드 성 북쪽 사냥터|4|32750|33397|open|12163|U/U;0/none|
|8|255|용의 계곡 입구|4|33239|32453|open|12163|U/U;0/none|
|8|256|용의 계곡 던전 입구|4|33411|32414|open|12163|U/U;0/none|
|8|257|(blank)|-1|-|-|heading|12163|-|
|9|0|풍룡의 둥지 입구|4|34114|32887|open|12183|U/U;0/none|
|9|1|황혼의 산맥 입구|4|34269|33090|open|12183|U/U;0/none|
|9|2|용의 계곡 입구|4|33239|32453|open|12183|U/U;0/none|
|9|3|화룡의 둥지 입구|4|33696|32421|open|12183|U/U;0/none|
|9|4|말하는 섬 던전 입구|0|32477|32853|open|12183|U/U;0/none|
|9|5|상아탑 4층 |78|32894|32776|open|12183|U/U;0/none|
|9|6|(blank)|-1|-|-|heading|12183|-|
|9|7|몽환의 섬 바람 지역|303|32635|32817|open|12183|U/U;0/none|
|9|8|몽환의 섬 물 지역|303|32667|32637|open|12183|U/U;0/none|
|9|9|몽환의 섬 불 지역|303|32840|32762|open|12183|U/U;0/none|
|9|10|몽환의 섬 땅 지역|303|32730|32750|open|12183|U/U;0/none|
|9|11|(blank)|-1|-|-|heading|12183|-|
|9|12|글루디오 던전 1층|7|32812|32727|open|12183|U/U;0/none|
|9|13|글루디오 던전 2층|8|32750|32799|open|12183|U/U;0/none|
|9|14|글루디오 던전 3층|9|32798|32754|open|12183|U/U;0/none|
|9|15|글루디오 던전 4층|10|32764|32774|open|12183|U/U;0/none|
|9|16|글루디오 던전 5층|11|32729|32724|open|12183|U/U;0/none|
|9|17|(blank)|-1|-|-|heading|12183|-|
|9|18|용의 계곡 던전 1층|30|32725|32726|open|12183|U/U;0/none|
|9|19|용의 계곡 던전 2층|31|32761|32751|open|12183|U/U;0/none|
|9|20|용의 계곡 던전 3층|32|32706|32820|open|12183|U/U;0/none|
|9|21|용의 계곡 던전 4층|33|32667|32869|open|12183|U/U;0/none|
|9|22|용의 계곡 던전 5층|35|32745|32800|open|12183|U/U;0/none|
|9|23|용의 계곡 던전 6층|36|32665|32847|open|12183|U/U;0/none|
|9|24|(blank)|-1|-|-|heading|12183|-|
|9|25|지하 수로 1층|59|32711|32789|open|12183|U/U;0/none|
|9|26|지하 수로 2층|60|32744|32859|open|12183|U/U;0/none|
|9|27|지하 수로 3층|61|32727|32808|open|12183|U/U;0/none|
|9|28|에바왕국|63|32805|32869|open|12183|U/U;0/none|
|9|29|(blank)|-1|-|-|heading|12183|-|
|9|30|사막 던전 1층|25|32807|32809|open|12183|U/U;0/none|
|9|31|사막 던전 2층|26|32804|32813|open|12183|U/U;0/none|
|9|32|사막 던전 3층|27|32808|32811|open|12183|U/U;0/none|
|9|33|사막 던전 4층|28|32799|32798|open|12183|U/U;0/none|
|9|34|(blank)|-1|-|-|heading|12183|-|
|9|35|기란 던전 1층|53|32808|32732|open|12183|U/U;0/none|
|9|36|기란 던전 2층|54|32808|32794|open|12183|U/U;0/none|
|9|37|기란 던전 3층|55|32734|32730|open|12183|U/U;0/none|
|9|38|기란 던전 4층|56|32768|32733|open|12183|U/U;0/none|
|9|39|(blank)|-1|-|-|heading|12183|-|
|9|40|요정숲 던전 1층|19|32804|32725|open|12183|U/U;0/none|
|9|41|요정숲 던전 2층|20|32766|32797|open|12183|U/U;0/none|
|9|42|요정숲 던전 3층|21|32729|32736|open|12183|U/U;0/none|
|9|43|(blank)|-1|-|-|heading|12183|-|
|9|44|개미굴 던전 1층 - 1|43|32786|32749|open|12183|U/U;0/none|
|9|45|개미굴 던전 1층 - 2|44|32800|32752|open|12183|U/U;0/none|
|9|46|개미굴 던전 1층 - 3|45|32778|32730|open|12183|U/U;0/none|
|9|47|개미굴 던전 1층 - 4|46|32789|32794|open|12183|U/U;0/none|
|9|48|개미굴 던전 1층 - 5|47|32795|32744|open|12183|U/U;0/none|
|9|49|개미굴 던전 1층 - 6|48|32796|32743|open|12183|U/U;0/none|
|9|50|개미굴 던전 1층 - 7|49|32802|32781|open|12183|U/U;0/none|
|9|51|개미굴 던전 1층 - 8|50|32770|32803|open|12183|U/U;0/none|
|9|52|(blank)|-1|-|-|heading|12183|-|
|9|53|라우풀 신전|4|33117|32937|open|12183|U/U;0/none|
|9|54|카오틱 신전|4|32664|32303|open|12183|U/U;0/none|
|10|0|[말하는 섬]|-1|-|-|heading|12273|-|
|10|1|창고지기|0|32573|32946|open|12273|U/U;0/none|
|10|2|여관|0|32599|32931|open|12273|U/U;0/none|
|10|3|텔레포터|0|32580|32929|open|12273|U/U;0/none|
|10|4|잡화 상인|0|32642|32949|open|12273|U/U;0/none|
|10|5|마법서 상인|0|32560|33088|open|12273|U/U;0/none|
|10|6|펫 관리인|0|32447|32993|open|12273|U/U;0/none|
|10|7|말하는 섬 선착장|0|32632|32962|open|12273|U/U;0/none|
|10|8|허수아비 수련장|0|32525|32832|open|12273|U/U;0/none|
|10|9|(blank)|-1|-|-|heading|12273|-|
|10|10|[기란 마을]|-1|-|-|heading|12273|-|
|10|11|창고지기|4|33427|32816|open|12273|U/U;0/none|
|10|12|여관|4|33430|32789|open|12273|U/U;0/none|
|10|13|텔레포터|4|33437|32798|open|12273|U/U;0/none|
|10|14|잡화 상인|4|33444|32822|open|12273|U/U;0/none|
|10|15|무기 상인|4|33388|32672|open|12273|U/U;0/none|
|10|16|방어구 상인|4|33427|32755|open|12273|U/U;0/none|
|10|17|물약 상인|4|33374|32731|open|12273|U/U;0/none|
|10|18|북편 시장|4|33474|32743|open|12273|U/U;0/none|
|10|19|동편 시장|4|33479|32810|open|12273|U/U;0/none|
|10|20|펫 관리인|4|33343|32721|open|12273|U/U;0/none|
|10|21|대장장이|4|33470|32778|open|12273|U/U;0/none|
|10|22|마법 연금술사|4|33397|32834|open|12273|U/U;0/none|
|10|23|(blank)|-1|-|-|heading|12273|-|
|10|24|[글루딘 마을]|-1|-|-|heading|12273|-|
|10|25|창고지기|4|32603|32767|open|12273|U/U;0/none|
|10|26|여관|4|32629|32751|open|12273|U/U;0/none|
|10|27|텔레포터|4|32614|32729|open|12273|U/U;0/none|
|10|28|잡화 상인|4|32600|32751|open|12273|U/U;0/none|
|10|29|슬라임 경기장|4|32613|32699|open|12273|U/U;0/none|
|10|30|(blank)|-1|-|-|heading|12273|-|
|10|31|[오렌 마을]|-1|-|-|heading|12273|-|
|10|32|창고지기|4|34052|32285|open|12273|U/U;0/none|
|10|33|여관|4|34063|32256|open|12273|U/U;0/none|
|10|34|텔레포터|4|34061|32280|open|12273|U/U;0/none|
|10|35|잡화 상인|4|34055|32297|open|12273|U/U;0/none|
|10|36|무기 방어구 상인|4|34064|32307|open|12273|U/U;0/none|
|10|37|펫 관리인|4|34076|32296|open|12273|U/U;0/none|
|10|38|(blank)|-1|-|-|heading|12273|-|
|10|39|[은기사 마을]|-1|-|-|heading|12273|-|
|10|40|창고지기|4|33074|33402|open|12273|U/U;0/none|
|10|41|여관|4|33113|33381|open|12273|U/U;0/none|
|10|42|텔레포터|4|33077|33388|open|12273|U/U;0/none|
|10|43|잡화 상인|4|33094|33391|open|12273|U/U;0/none|
|10|44|무기 방어구 상인|4|33092|33407|open|12273|U/U;0/none|
|10|45|게라드|4|33098|33360|open|12273|U/U;0/none|
|10|46|허수아비 수련장|4|33104|33332|open|12273|U/U;0/none|
|10|47|(blank)|-1|-|-|heading|12273|-|
|10|48|[켄트 마을]|-1|-|-|heading|12273|-|
|10|49|창고지기|4|33058|32785|open|12273|U/U;0/none|
|10|50|텔레포터|4|33053|32780|open|12273|U/U;0/none|
|10|51|잡화 상인|4|33062|32739|open|12273|U/U;0/none|
|10|52|무기 방어구 상인|4|33066|32760|open|12273|U/U;0/none|
|10|53|펫 관리인|4|33040|32749|open|12273|U/U;0/none|
|10|54|(blank)|-1|-|-|heading|12273|-|
|10|55|[우드벡 마을]|-1|-|-|heading|12273|-|
|10|56|창고지기|4|32624|33183|open|12273|U/U;0/none|
|10|57|여관|4|32619|33174|open|12273|U/U;0/none|
|10|58|텔레포터|4|32644|33200|open|12273|U/U;0/none|
|10|59|잡화 상인|4|32629|33200|open|12273|U/U;0/none|
|10|60|펫 관리인|4|32607|33199|open|12273|U/U;0/none|
|10|61|(blank)|-1|-|-|heading|12273|-|
|10|62|[화전민 마을]|-1|-|-|heading|12273|-|
|10|63|창고지기|4|32737|32446|open|12273|U/U;0/none|
|10|64|잡화 상인|4|32752|32432|open|12273|U/U;0/none|
|10|65|펫 관리인|4|32762|32450|open|12273|U/U;0/none|
|10|66|축복의 땅|4|32760|32451|open|12273|U/U;0/none|
|10|67|(blank)|-1|-|-|heading|12273|-|
|10|68|[하이네 마을]|-1|-|-|heading|12273|-|
|10|69|창고지기|4|33601|33231|open|12273|U/U;0/none|
|10|70|여관|4|33596|33276|open|12273|U/U;0/none|
|10|71|텔레포터|4|33614|33252|open|12273|U/U;0/none|
|10|72|잡화 상인|4|33637|33287|open|12273|U/U;0/none|
|10|73|무기 방어구 상인|4|33622|33287|open|12273|U/U;0/none|
|10|74|펫 관리인|4|33646|33410|open|12273|U/U;0/none|
|10|75|(blank)|-1|-|-|heading|12273|-|
|10|76|[웰던 마을]|-1|-|-|heading|12273|-|
|10|77|창고지기|4|33726|32487|open|12273|U/U;0/none|
|10|78|텔레포터|4|33707|32497|open|12273|U/U;0/none|
|10|79|잡화 상인|4|33738|32496|open|12273|U/U;0/none|
|10|80|무기 상인|4|33710|32518|open|12273|U/U;0/none|
|10|81|펫 관리인|4|33692|32501|open|12273|U/U;0/none|
|10|82|(blank)|-1|-|-|heading|12273|-|
|10|83|[아덴 마을]|-1|-|-|heading|12273|-|
|10|84|아덴 광장|4|33928|33341|open|12273|U/U;0/none|
|10|85|여관|4|33988|33314|open|12273|U/U;0/none|
|10|86|텔레포터|4|33961|33256|open|12273|U/U;0/none|
|10|87|잡화 상인|4|34150|33129|open|12273|U/U;0/none|
|10|88|무기 상인|4|34004|33119|open|12273|U/U;0/none|
|10|89|방어구 상인|4|34151|33114|open|12273|U/U;0/none|
|10|90|물약 상인|4|34122|33149|open|12273|U/U;0/none|
|10|91|펫 관리인|4|33921|33177|open|12273|U/U;0/none|
|10|92|성당|4|33957|33364|open|12273|U/U;0/none|
|10|93|집시촌|4|33979|32927|open|12273|U/U;0/none|
|10|94|(blank)|-1|-|-|heading|12273|-|
|11|0|오만의 탑 1층|101|32726|32798|open|15396|U/U;0/none|
|11|1|오만의 탑 11층|111|32669|32814|open|15396|U/U;0/none|
|11|2|(blank)|-1|-|-|heading|15396|-|

## 2026-10-29 잔여 그룹1–5/7의 UI 진입 재조사

**추가 개방0, 잔여234 전부 보류.** 고정 native-dump의 item1266행·기존 카탈로그·원704행과 run37/39/41, run382/403을 재사용했다. 새 정적 원문은 [remaining-group-static.json](../../../_work/talkscroll/remaining-group-static.json), 일회성 재현은 [remaining_group_probe.py](../../../_work/talkscroll/remaining_group_probe.py)다. 기존 CONTROL reader로 저장 code만 읽었고 REA target·원본 LC·화면·입력은 실행하지 않았다. 아래 `확정`은 데이터/정적 사실이며 UI/공식 발급 성공이 아니다.

|그룹|원 목적지/현 좌표 가능|확정된 f53 숫자 일치 아이템(raw f4)|원문 native-dump 줄|UI 진입/선택 consumer 판정|
|---:|---:|---|---:|---|
|1|51/51|20 단풍나무 막대(39)|970|미확정·보류51|
|2|50/50|12083 샤르나의 변신 주문서(16)|1661|미확정·보류50|
|3|50/50|12140 병오년 변신 주문서(16)|1697|미확정·보류50|
|4|46/46|12244 바포메트 변신 주문서(16)|1791|미확정·보류46|
|5|9/9|12245 커츠 변신 주문서(16)|1792|미확정·보류9|
|7|28/28|12247 다크엘프 변신 주문서(16)|1794|미확정·보류28|

각 그룹의 원 행·heading·ordinal·좌표·이름은 위 전체표 그대로다. 원 비용/최저레벨은 모두 UNKNOWN이며 이번에 새 LOCAL 비용/제한을 만들지 않았다. **표의6종은 추가할 두루마리 후보가 아니다.** catalog.f4와 실제 수신 ItemInfo.f5는 다른 필드이므로 공식 raw 공급을 추정하지 않으며, f53 숫자만으로 이 아이템에 raw133을 공급하거나 그룹을 바꾸지 않았다.

- **아이템 경로:** 원 switch는 raw16→index7/4FDB2E→5689D0, raw39→index1/4FDB56으로 raw133→index15/4FE125→5027B0와 다르다. 순간이동 주문서23/12044/12174/12302/12327은 raw6·f53 absent, 잊혀진 섬12445/12447은 raw142/9·f53 absent, 기억 저장 구슬12458은 raw143·f53 absent다. 던전 기억책12183/12280은 raw133·group9, 오만 기억책15396은 raw133·group11로 이미 연결돼 있다. 상자12182/12279는 raw91이며 새 그룹 진입 증거가 아니다. 이름/숫자 일치만으로 다른 UI를0960.f13에 연결하지 않았다.
- **추가 caller:** 5027B0의 CODE 직접 E8/E9 caller는 raw133의4FE12F와 창 상태에 따른 재호출502742(owner502600)다. B23D30의 직접 caller는 command0의B23B8F와 즐겨찾기 편집 후B26A9B다. 후자는 `layout+C8`의 같은 보유UID와 R8=false를 넘기지만 B243A0부터 UID→Item→B24423 f53→B248AB group 조회로 합류한다. false를 별도 그룹/직업/NPC 모드로 해석하지 않았다. owner 명령 경계로 확인한 직접 caller 범위이며 간접 호출·다른 버전·공식 발급 전체 부재를 증명하지 않는다.
- **NPC 경로:** [run382](../../local_server_rea_20261016/run382_npc_dialog_menu/handler_trace.md)와 [run403](../../local_server_rea_20261016/run403_service_npc_dialogs/service_resources.md)의4E44 stem→원 UML action→4ED4.f2 문자열 경로는 raw133 선택과 다르다. lucas2는 `island-gludin`/`island-dungeon`, keith3는 `firefieldtown`과 요금변수이며 그룹1–5/7 또는234행 ordinal을 생산한다는 근거가 없다. 원 버튼을 재명명하거나 요금·좌표를 전용하지 않았다.

**추가 필요 목록:** 그룹1/2/3/4/5/7 각각에 대해 실제 템플릿ID·이름·원 use 경로·group 생산자(또는 NPC의 정확 stem/action/목적지 계약)가 필요하다. 현재 확정된 신규 추가 아이템ID는 **0종**이다. 가장 작은 후속 입력은 고정 버전의 해당 item row와 원 UI 호출의 template→group 연결, 또는 보존된 정상 발급 ItemInfo/메뉴 응답과 선택 요청 한 쌍이다. 서버 정의가 없는 실제 아이템이 확인되면 그 정의 추가는 별도 담당 범위로 보고해야 한다. 이번에는 아이템 정의·starter·제품 코드를 수정하거나 가짜UID를 발급하지 않았다.

**요청 회귀:** TMP/TEMP=`_work/tmp`, `PYTHONUTF8=1`, `PYTHONDONTWRITEBYTECODE=1`로 다음을 순차 실행했다. 권한 오류는 없었다.

1. `python -B -m unittest tools.local_original_session.world_talkscroll_tests -v` → [로그](../../../_work/talkscroll/remaining-groups-unittest.log): **12 tests / 0.941s / OK**.
2. `SL_TEST_TIME_SCALE=10 SL_TEST_PORT_BASE=46000 python -X utf8 -B tools/local_original_session/run_fast.py hunt_bot_talkscroll` → [로그](../../../_work/talkscroll/remaining-groups-bot.log), [새 summary](../../../_work/talkscroll/hunt-talkscroll-49f916a39446/summary.json): **SUCCESS,280 checks,269회 이동(기존 연결268행+귀환1)**. 정상 FIRST/로그인/선택/월드→서버수신UID→0960→wire/current/entity/저장 일치→Quit→fresh FIRST 복원, 양 epoch cleanup_complete=true, 실행 중 source 변경없음. 전용 포트46000/48030, 원본 클라이언트 실행0. 새 시험저장의 기존 append CAS 공급/성장 준비와 자연획득 미검증 경계는 위 봇 설명과 같다.

이번 봇은 현재 Source/새 저장의 기존268행 회귀다. 이전0dfbf4a51b7d와는 `world_handlers.py` 해시가 다르며 두 실행의 PASS를 합산하지 않는다. 두루마리 제품 파일은 바뀌지 않았고 **이번234행의 UI·이동·저장 PASS는0개**다. 변경은 이 문서와 `_work/talkscroll`의 정적 발췌·시험 출력뿐이다.
