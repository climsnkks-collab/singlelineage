# 기억(책갈피) 근거와 연결 경계

2026-10-28. **1차 LOCAL 직접 패킷27검사 성공, 2차 기본30·지역9/5검사 성공 / 원본 UI·입력 미검증.** 최신 변경과 미지원 계약은 아래 「2차」 절을 따른다. 정적 원문 확인·로컬 연결·직접 패킷 성공을 구별한다. 기존 요청 지도 필드 번호·타입·opcode를 보존하며, 원래 필드명과 정책을 추측으로 복원하지 않는다.

## 공식 규칙

- [NC 클래식 기억 가이드](https://lineageclassic.plaync.com/ko-kr/guidebook/view?title=%EA%B8%B0%EC%96%B5)의 검색 인덱스 본문을 확인했다. 직접 HTTP 열기는 SPA shell만 반환했다. 기본 저장 **50개**, 이름 한글16자/영문·숫자32자, 던전·공성 지역 등 특정 장소의 저장 불가를 명시한다. 구체적인 모든 금지 map ID 목록은 제공하지 않는다.
- 같은 가이드는 `/기억 장소` 또는 행동창(Ctrl+D)의 기억 입력으로 현재 위치 저장, 리스트 선택 후 Delete로 삭제, 리스트 더블클릭 후 이름 수정, 축복 주문서 또는 조종 반지 착용+일반 주문서/텔레포트 마법으로 기억창 열기, 이동할 리스트 더블클릭으로 장소 이동을 설명한다. 기억창이 열린 상태에서 다시 주문서/마법을 쓰면 랜덤 텔레포트한다.
- 공식 수집 원문은 `tools/local_original_session/data/official/items.json`의 official_id/client_id **23** 및 **64**에 있다. [아이템23 API](https://api-goats.plaync.com/linclassic/v2.0/game/item/23?locale=ko-KR)는 일반 주문서의 무작위 이동, 조종 반지와 함께 사용 시 지정 이동, 축복 주문서는 반지 없이 기억 장소 이동을 설명한다. [아이템64 API](https://api-goats.plaync.com/linclassic/v2.0/game/item/64?locale=ko-KR)도 주문서+반지의 기억 장소 이동을 설명한다. 보존 raw: `work/official_data_refresh_20261028/raw/item/23.json`(수집04:42:37Z), `64.json`(04:43:15Z). 본문을 직접 읽었으며 새 API 호출은 하지 않았다.
- **공식 미확인:** 주문서 소비 수량·소비 시점, 메뉴 취소·목적지/출발지 거절 시 소비, 모든 저장 금지 지역의 map ID, 슬롯 확장 비용·상한. 공식 설명을 이런 세부 규칙의 증거로 확대하지 않는다.

## 고정 원본과 조사 방법

버전26.09.29.2001, 원본 CONTROL SHA-256 `9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`(기존 복구 메타데이터 상속). 요청 지도는 파생 metadata-v2 carrier SHA `c822838351d774a2022af434829a36dbd9bee030bf22182b834ca4e8659701a9`를 사용한다. 이번 추가 확인은 기존 `work/local_server_rea_20261016/run392_chat_system_message/extract.py`의 RTTI/descriptor/Capstone 해석과 `run380_map_transition_receive/f2_research.py`의 `View`를 재사용했다. View는 기존 `C:/Users/Chansol/Documents/Codex/2026-09-07/d-lineage-classic/work/current_client_key_mapping/recovery.json` 및 section record를 읽는다. 현재 disk 실행파일·실행 RAM과의 전체 동등성은 주장하지 않는다.

`sys.dont_write_bytecode=True` 후 extract.py를 importlib로 불러 `m.save=lambda name,obj:None`으로 기존 원문 폴더 쓰기를 막았다. `m.rtti(TD+16)`, `m.schema(RVA)`, `m.v.function(RVA)['instructions']`, `m.calls(RVA)`로 아래 범위만 읽었다. 새 코드 파일·추출 체계·게임·서버·포트 실행은 만들지 않았다. RVA 기준이며 preferred base는140000000이다. REA 연결 결과가 아니라 기존 로컬 정적 reader 결과다.

## 요청 스키마와 발신값

| 요청 | 보존 스키마 | 추가 정적 확인 / 제한 |
|---|---|---|
| `4E4A CS_ADD_BOOKMARK_REQ` | f1 string_or_bytes, raw+18; getter763CE0/schema15E9EE0 | sender913F20→914139 CALL27D620. 이름 문자열의 정확 UI 발신 인코딩·현재 입력 동작은 미관측 |
| `4E4B CS_UPDATE_BOOKMARK_REQ` | f1 string_or_bytes raw+18, f2 u64 raw+20; schema15EA900 | `917344 movsxd r12,[rdi+8]`의 signed32 row 식별키로 map 조회, `917541` 문자열 복사, `91754A`에서 f2로 sign-extended key, `917587` 송신. 새 이름은 sender 입력 문자열. 원필드명은 UNKNOWN |
| `4E4C CS_DELETE_BOOKMARK_REQ` | f1 string_or_bytes raw+18, f2 u64 raw+20; schema15EA890 | `4591AA movsxd rdi,edx` 키로 map 조회, 찾은 row+28 문자열→f1(`45928C..295`), key→f2(`45929F`), `4592DE` 송신. 이어 local row를 제거한다. 임의 전체u64 키가 native row에서 보존된다고 주장하지 않음 |
| `4F5F CS_BOOKMARK_EXTENSION_ADD_REQ` | 필드0개; schema15EA750 | sender916B70→916BDD. 확장 아이템·비용·성공 규칙은 미확인 |
| `4E41 CS_TELEPORT_REQ` | f1 i32 raw+18, f2 u32 raw+1C, f3 u32 raw+20; schema15EF130 | `5B5690`은 입력 struct+0/+4/+8을 세 필드로 복사하고 `5B5713` 송신. caller5B54A0은 EDX/R8D/R9D를 struct에 저장. **기억 선택 요청이라고 확정하지 않음**; 좌표/명령 의미는 별도 sender 조사 대상 |

UPDATE/DELETE의 f2를 서버의 안정 식별자로 쓰는 것은 위 native 키 소비와 연결할 수 있다. native map 키는 low32이며 요청 송신은 signed32 확장이다. 로컬이 양의int31 범위를 선택하면 **local_policy**로 표시한다.

## 수신 스키마와 소비자

| 메시지 / 정적 등록 opcode | 실제 protobuf vtable / getter / schema | 필드·초기화 |
|---|---|---|
| SC_ADD_BOOKMARK_NOTI /4E4D | 11E5AB8 /764910 /15EA6D0 | f1 i32 raw30 bit0 필수; f2 repeated child raw18; child schema15EA798. `764C10`은 f1 presence와 child IsInitialized를 검사 |
| SC_BOOKMARK_EXTENSION_ADD_ACK /4F60 | 11E7450 /764E60 /15EA678 | f1 i32 raw18 bit0 필수; `764F90: movzx eax,[rcx+10]; and al,1; ret` |
| SC_BOOKMARK_STORE_NOTI /C371 | 11E5640 /782AF0 /15F0B30 | f1 repeated child raw10; child schema15F0A38. `782DA0`은 모든 child 초기화 검사. 빈 repeated 목록 자체는 허용 |

두 child schema15EA798/15F0A38는 같은 형태다. header max5/skipFFFFFFE0/descriptor_offsetB4/count5/aux0이며 descriptor는 순서대로 `(raw offset,presence,aux,type_card)`:

| 필드 | descriptor | wire / native row 소비 |
|---|---|---|
| f1 | `(20,129,0,08D1)` | u64 varint, decoderDEC8D0. ADD459A56은 qword를 읽지만459A96..99에서 low32를 map key row+10에 보존. STORE45A0D1은 low32를 읽음 |
| f2 | `(18,128,0,0815)` | string_or_bytes, wire2, decoderDEA360; 문자열→map row+28 / 목록 row+18 |
| f3 | `(28,130,0,1091)` | i32 varint, decoderDEC430; map row+18→목록 row+8 |
| f4 | `(2C,131,0,1091)` | i32 varint; map row+1C→목록 row+C |
| f5 | `(30,132,0,1091)` | i32 varint; map row+20→목록 row+10 |

`764840` 및 `782A20`: `mov eax,[rcx+10]; not eax; test al,1F; sete al; ret`이므로 두 child의5필드는 모두 필수다. **f3/f4/f5를 map/x/y라고 확정할 소비자는 아직 미확인**이다. 이 범위에서는 세 값의 복사만 관측했다. 임의 순서를 native 원본 값이라고 주장하지 않는다.

SC_ADD의 f1과 EXT_ACK의 f1은 **성공/실패 코드가 아니라 최대 기억 수 표시값**이다. 근거:

- BookmarkSubsystem TD168C6A0/vtable11BB360. constructor4584C0은 `458569→459870`, `45857F→459DE0`, `458595→459EE0` callback을 등록한다. callback에서 복사하는 protobuf vtable가 각각11E5AB8/11E7450/11E5640과 일치한다.
- ADD handler `459943 mov r8d,[rbx+38]`(wrapper+8이므로 rawf1+30), `459D24 mov [r15+1D8],r8d`. EXT handler459DE0은 f1을 같은 subsystem+1D8에 저장(`459E6D`)한다.
- UI9152C0은458BB0으로 얻은 목록의38B 행 수를 첫 인수, subsystem+1D8을 둘째 인수로 `{} / {}`(문자열RVA118B7D8)에 전달(`91533E/91534A/915350/915396..9153A6`)하고 BF9ED0으로 텍스트를 설정한다. 이를 임의 result=0 ACK로 만들면 최대값0 표시가 된다.
- ADD handler459870은 child를 기존 map에 추가하고 같은 키 중복은 새 row를 해제한다. 따라서 ADD를 같은key의 이름/좌표 덮어쓰기용으로 쓰지 않는다. UPDATE/DELETE는 송신 직후 client local map을 rename/delete하며, 현재 별도의 SC ACK 스키마를 찾지 못했다. 원 요청마다 특정 ACK가 필수라는 원서버 인과는 미관측이다.
- **STORE C371은 일반 기억 목록의 authoritative refresh가 아니다.** handler459EE0은 임시map(`RBP+20`)에 child들을 넣고458BB0으로 임시 목록을 만든다. `45AA5D CALL45BAE0`의 getter는 `45BC0D LEA R9→TD168CB98`, RTTI `.?AVBookmarkCrystalLayout@ui@lineage@@`를 사용하고 `45BCC7 CALL[vtable+98]`한다. main subsystem+198 map을 clear/swap하는 소비는 확인되지 않았다. C371을 UPDATE/DELETE 후 전체목록 갱신용으로 보내면 별도 구슬창 경로를 건드리므로 그렇게 연결하지 않는다.

0960 params f18의 기존 [ENCHANT_USE_EVIDENCE](ENCHANT_USE_EVIDENCE.md)91행 및 run293/source3/contract.md는 BookmarkSubsystem 보유dword 목록→repeated i32임을 확인한다. writer4596E0의 caller9125E0/912F70은 BookmarkCrystalLayout 쪽이다. 이 근거만으로 일반 순간이동 주문서의 장소 선택 필드라고 확정하지 않는다.

구현 worker의 같은 고정 View 추가 분석: `915510 BookmarkLayout`의 mode1(`subsystem+1DC==1`) 선택은 rowkey(EDX)→45BE10(mainmap+198 조회)→row value의 첫3dword→UseItemReqParam **f8/f9/f10**(raw50/54/58)이다. f1=1, presence bits15/7/8/9만 설정하고, layout+B8 signed32 사용UID를 `91581C→4FE630`으로 보낸다. params TD1739D60/vtable11DE028/getter6C1F50/schema15D81F0. 이것은 위 SC childf3/f4/f5의 **불투명 세 값 왕복**을 닫으며 원 map/x/y 순서명을 복원한 것은 아니다. 서버가 발급한 자기row 세 값과 실제 요청값을 대조하고 그 저장row의 서버 위치로 이동할 수 있다. 로컬 생산순서를 map/x/y로 정하면 local_policy로 구분한다. 별도4E41의 caller4942E0은 문자열2/3개 parse 경로이며 기억 선택과 동일시하지 않는다.

## L1J 참고와 local_policy

로컬 참조 `D:/SingleLineageRef/l1j-en-classic`의 origin은 [l1j-en/classic](https://github.com/l1j-en/classic), 확인 HEAD는 `103e6f6c9dd83545959d8e87d3f59f8de1f40ef0`이다. 아래는 이 소스의 backend 정책이며 공식 클래식 원본 규칙이 아니다.

- `src/l1j/server/server/templates/L1BookMark.java:70`: map.isMarkable, 최대100개(`size>99`), 중복 이름 거절, 서버 현재map/x/y와 발급id를 character_teleport에 INSERT. 삭제는 자기 목록에서 이름을 찾고id로 DELETE.
- `clientpackets/C_AddBookmark.java:46`: ghost 거절, isMarkable 검사 및 성 전쟁 지역/집 내부 저장 거절(GM 예외). 모든 던전을 임의 map번호 규칙으로 정하지 않고 map 데이터 flag를 사용한다.
- `clientpackets/C_ItemUSe.java:1188`: 140100/40100 등 주문서가 자기 bookmark id를 찾으면 출발map.isEscapable 성공 시 이동 뒤 아이템1개 제거. 해당bookmark가 없으면 map.isTeleportable 성공 시 random 이동 후1개 제거. 거절 분기에는 제거가 없다. **미지정·잘못된id를 random으로 바꾸는 L1J 분기를 로컬에 그대로 넣을 근거는 아님**이다.
- 공식50개가 확인됐으므로 L1J100개를 공식 저장 한도로 사용하지 않는다. 공식에 없는 성공 시1개 소비/거절 시보존, map별 세부 금지는 채택 시 local_policy라고 표시한다. 현 원본의0960 params/typed응답은 L1J의 구형 readS/readD 패킷과 별도다.

## 미완과 검증 범위

구현 worker의 결과와 실제 파일을 대조했다. `world_feature_bookmark.py`는 선택 기능으로 등록됐고, `world_bookmark.py`가 typed 요청/4E4D encoder·50개 모델을, `tools/local_character_creation/realm.py`가 캐릭터별 optional bookmarks 저장/재열기를 담당한다. 등록은 `world_handlers.py:883`이다. ADD는 새row만4E4D로 보내고 월드 진입/재접속에는 전체4E4D를 보낸다. UPDATE/DELETE는 원 optimistic client 처리와 맞춰 추가 ACK를 만들지 않는다. C371·4F60 송신은0개다.

LOCAL 정책은 이름의 혼합문자 폭(ASCII1/비ASCII2·32단위), UTF-8 입력, 양의int31 row key, 중복 이름/동일 좌표 거절, 저장 가능map0/4, 서버 발급opaque triple(map/x/y 순) 및 자기 저장row exact match다. 순간이동은 현재 보유item23의 실제 grade0(축복) 또는 grade1+착용item64를 확인한 뒤 기존 kit1개 소비→core relocate를 사용한다. 직접 목적지 좌표를 권한으로 쓰지 않는다. 일반 raw0는 기존 무작위 이동 경로에 남긴다. 거절·저장 실패는 성공형 알림을 만들지 않는다. 출발map escapable의 공용 정책과 공성 런타임은 아직 없어 원본 전체 지역 제한을 구현했다고 주장하지 않는다. 원 client의 optimistic rename/delete가 서버 거절 뒤 복구되는지는 미검증이다.

worker는 `python -m unittest tools.local_original_session.world_bookmark_tests tools.local_character_creation.tests -q`에서 신규10개+기존3개, 총13개 단위시험 성공을 보고했다(포트/게임0). 기존 registry의 optional omission/core defaults2개와 실제 core+features·bookmark제외·모든optional제외 구성의 등록 존재/부재도 확인했다고 보고했다. 이는 함수·시험사본 기반 개발 검증이다. 본 문서 담당자는 코드와 등록·저장 경로를 읽었고 같은 단위시험을 중복 실행하지 않았다. 일반 기억 선택의0960 f8/f9/f10은 정적으로 연결됐고, childf3~5 업무명 미확정은 불투명 왕복 경계로 남긴다. 소비/금지지역의 공식 세부값은 미확인이다.

최초 socket성공 이후 shared `realm.py`에 다른 작업자의 optional pledge저장필드가 추가됐다. 이 변경은 책갈피 담당자가 수정하지 않았다. main은 변경된 저장조합에서 `python -X utf8 -B -m unittest tools.local_original_session.world_bookmark_tests tools.local_character_creation.tests -q`를 다시 실행해13개OK(0.300초)를 확인했다. 이는 새 저장형식 변경 이후의 재확인이며 이전Source의 성공을 새Source에 합산하지 않는다. 최신조합의 후속socket결과는 아래에서 별도로 기록한다.

확장 최소조회: 공식 기억가이드와613개 공식 아이템 이름/설명, `site:lineageclassic.plaync.com 기억 확장` 및 NC 라운지의 클래식 기억확장 검색, L1J src/config의 bookmark extension/extend/expand 검색에서 비용·증가량 근거를 확보하지 못했다. 이는 위 검색 범위의 미확인이며 원본에 확장이 없다는 증명이 아니다. 수집된 기억 관련 아이템12458은 '케플리샤의 기억 저장 구슬'로 설명이 기억을 구슬에 담는 기능이며 슬롯확장 비용이 아니다. **4F5F는 비용/확장 계약이 없어 미지원으로 남긴다. 무료증설·현capacity 재전송ACK를 원본 확장 완료로 표시하지 않는다.**

## 실제 직접 패킷 결과

[최신조합 최종 summary](../runs/hunt-bookmark-nb9t5jqb/summary.json)를 직접 열어 statusSUCCESS·27검사 전부SUCCESS·두epoch failure_code/close_code null·cleanup_complete true·handler/hook/bookmark errors빈목록·실행 중source변경없음을 확인했다. 게임을 띄우지 않은 로컬 socket/실 decoder/router/handler/저장 시험이다. 원본 client UI·키/클릭·카메라·native 축복grade표시·원서버응답 전체동등성 PASS는 아니다.

이 최종실행은 shared realm.py의 외부 pledge저장필드 추가 뒤 수행했다. 최신 realm SHA는 `9f8d436855ed4a68505d04ba339f3bd106959607de9160fcdee1bc81f4ae5b50`이다. [최초 dlfpaync 성공](../runs/hunt-bookmark-dlfpaync/summary.json)은 당시 realm SHA `91cfbade7845273e8fa971c063acc9ac8e19e23ed848115a3074c6637863307a`에 귀속해 그대로 보존한다. bot·feature·model·registry의 아래 해시는 두실행에서 같지만, 성공을 합산하거나 옛결과의Source를 수정하지 않았다.

시작은 새 owned `test_knight` 시험사본의 마을map0/(32578,32946)이다. 기존 일반item23×10을 보존하고 pre-FIRST 저장API로 LOCAL grade0 축복주문서×2를 공급했다. 실제 첫0964에서 받은UID65572를 사용했다. 원본/user save를 변경하지 않았다. `time_scale=10`, `port_base=60000`/물리60000·62030, LOCAL MapExp2, 기존catalog 불일치의 `world_feature_alignment`와 동시등록 모듈부재의 `world_feature_monster_skills`는 제외했다. 이 조건 외 소스의 통과로 합산하지 않는다.

최종 실행명령(시험worker 단독실행, companion0):

```powershell
$env:SL_TEST_PORT_BASE='60000'; $env:SL_TEST_TIME_SCALE='10'; python -X utf8 -B C:/Users/Chansol/AppData/Local/Temp/claude/D--claude/0483de89-75e7-4b94-84b8-fb31fe00f575/scratchpad/fastbot/run_fast.py hunt_bot_bookmark --timeout 30
```

- 두 번 모두 정상FIRST→로그인→캐릭터선택→월드진입. ADD id1→UPDATE(추가ACK없음)→DELETE(추가ACK없음)→reADD id2로 저장하고 정상Quit. 새broker는 `seed=False`로 같은 시험저장을 열어 두번째4E4D에서 id2와 이름·triple을 복원했다.
- 실제4E2B 이동1칸으로(32578,32945)에 간 뒤 수신row의triple `(0,32578,32946)`을0960 params `{1:1,8:0,9:32578,10:32946}`로 보냈다. UID·triple을 임의로 대체하지 않았다.
- 실제수신0965 ordinal62에서 수량2→1, 이어4E95 ordinal65→4E38 ordinal66→자기4E96 ordinal67을 확인했다. wire/권위/저장 위치가 모두(0,32578,32946)이며 실제inventory저장도1개다. 마지막 정상Quit 뒤 장소·소모·책갈피를 보존했다.

선정 Source 해시 전체는 같은 summary의 `source_sha256_start`/`source_sha256`에 있다. 주요 파일은 bot `13cee67724d7657ebabab874d92616285aad40e2fb9ba60fb9f22ac838ebefc2`, feature `f28954eb608c5badbd1e1703e56a8f2b1345bd9d98d450fc909cf6464b950c9f`, model `304138f555b5e5b3adc7aae1ead8f134c5c6efff21db07a77ac428595982c0d3`, registry `260f7914f8913142377a8fb2b8f1ffe63cf523b9b1eb4ce73ad57e077fef8b33`다. `source_changes_during_run=[]`이다.

이전5회 결과를 그대로 보존했다: [vqdyk4fk](../runs/hunt-bookmark-vqdyk4fk/summary.json)는 기존일반주문서 발견으로UNCONFIRMED, [ux9owmh2](../runs/hunt-bookmark-ux9owmh2/summary.json)/[r1xu7e9h](../runs/hunt-bookmark-r1xu7e9h/summary.json)는 alignment catalog 오류FAILED, [n0oli9i7](../runs/hunt-bookmark-n0oli9i7/summary.json)는 monster_skills 모듈부재FAILED, [h2hkg95n](../runs/hunt-bookmark-h2hkg95n/summary.json)은 봇의이동후4EE0기대timeout으로FAILED다. 최종봇은 실제0965·4E95·4E38·자기4E96을 기다렸다. 옛실패를 소급성공으로 바꾸지 않았다. C371 구슬창은 미송신·미검증이며4F5F 확장/4F60 ACK·4E41 좌표명령은 미지원이다. 출발지역 escapable제한의 공용정책은 미연결이다. 일반scroll+반지실행·금지출발지역·실제native 화면도 이27검사의 통과범위 밖이다.

## 2차: 출발 지역 제한과 미지원 계약의 무부작용 거절

`world_bookmark.location_allowed`에 현재 로컬 맵과 별도 금지 참고map70의 **59개 LOCAL markable/escapable 정책**을 명시했다. 출처는 고정 L1J `D:/SingleLineageRef/l1j-en-classic/db/l1jdb_m10.sql`의 DDL1471~1473, mapids19191~19293이다. map0/4는 둘 다1, map1/2 및 현재 지원 던전·선박은markable0/escapable1, map37/70은 둘 다0이다. 예를 들어19193의map2는 `(markable,teleportable,escapable)=(0,0,1)`,19228의map37은`(0,0,0)`이다. **랜덤 이동불가와 기억 목적지 탈출불가는 같은 값이 아니다.** ADD는markable을, 선택된0960은소비 전 출발map의escapable을 확인한다. 누락map은`BOOKMARK_LOCATION_POLICY_UNKNOWN`으로 남기며 허용으로 보충하지 않는다. 목적지는 종전 자기저장row exact match·서버 위치·지형·served map 조건을 유지한다. JSON 저장형식·기본50개·기존row/next_id는 바꾸지 않았다. 다른 선택 기능의 상태/메서드는 읽지 않는다.

[공식 기억 가이드](https://lineageclassic.plaync.com/ko-kr/guidebook/view?title=%EA%B8%B0%EC%96%B5)를 웹 검색 인덱스로 재확인했다. 기본50개와 던전·공성지역 저장불가 설명은 같으며, 개별map escapable·슬롯확장 비용/증가량·구슬의 서버 저장/소비는 설명하지 않는다. `site:lineageclassic.plaync.com "기억" "확장" "50"`와 구슬 정확명 검색에서는 추가 계약을 얻지 못했다. 이는 제한된 검색 결과이며 기능 부재의 증명이 아니다. map별 숫자는 공식 규칙이 아닌 위 L1J의 별도 backend 정책이다. 공성 진행상태·집 내부의 런타임 제한과 공식 전체 지역목록은 아직 없다.

`reverse-engineer-anything` 지침에 따라 기존 고정 View/reader를 재사용해 다음 원문만 추가 확인했다. `save`는 no-op으로 덮어 원정적자료를 수정하지 않았고, 새게임/attach/원본실행은0이다. 새 REA provider Evidence를 얻었다는 뜻은 아니다.

| 경로 | 추가 원문과 구현 경계 | 최소 부족 입력 |
|---|---|---|
| 슬롯4F5F/4F60 | `916B70..916BDD`는 필드 없는4F5F 송신이다. 4F60f1은 앞서 확인한 최대표시값이다. 기존 `BOOKMARK_EXTENSION_COST_AND_INCREMENT_UNKNOWN` 거절을 유지하며 capacity50 재전송·무료증설·임의0ACK를 만들지 않는다. | 확장 전후 최대값, 비용의 생산자/실제 차감, 실패/상한을 묶은 원서버 응답 또는 고정서버 계약 |
| 별도4E41 | `4942E0`의2/3문자열 숫자 parse→`494678/4946FE CALL5B54A0`. 3개는첫값EDX·둘째R8D·셋째R9D,2개는EDX를로컬객체+718에서가져온다(`494562`). 입력복사 외 서버권한·map/x/y 업무명은미확정이다. 종전미지원 거절을 유지한다. | 명령 등록/허용권한과 정상 송신→원서버 응답·실제위치 관측. 사용자 좌표를 일반기억 권한으로 바꾸지 않음 |
| 구슬12458/C371 | `912F9E..912FCB`의layout+E8 조건·D0 선택목록→`4596E0`, 이어확인팝업(`91308D`type2)을확인했다. `9125E0`은목록삭제 후같은writer를호출한다. `4596EA..459728`은선택수·buffer준비까지만확인됐다. 공식raw12458은기억을구슬에담는다는설명뿐이다. 소유12458의0960은명시적`BOOKMARK_CRYSTAL_STORAGE_AND_USE_CONTRACT_UNKNOWN`으로거절해일반아이템처리로넘기지않는다. C371 encoder는일반4E4D와별도인상태를유지하고송신하지않는다. | 실제초기사용/확인/취소의0960 params·발급item UID와구슬안row의저장생산자·재사용/거래수명·소비시점. 임의params의무소비거절시험은정상구슬기능 PASS가아님 |

단위 명령 `python -X utf8 -B -m unittest tools.local_original_session.world_bookmark_tests -q`는 **16개OK**다. 신규6개는map2 저장불가/탈출가능 분리, map37·UNKNOWN출발지 보존,4E41 임의좌표 거절, 소유구슬 무소비, C371/4E4D schema분리 및 미송신 경계다. 기존10개 기대는 일괄수정하지 않았다.

최종 동일 조합의 순차 직접 패킷 결과:

| 실행 | 결과와 범위 |
|---|---|
| [j2fhl7qv](../runs/hunt-bookmark-j2fhl7qv/summary.json) | **30검사SUCCESS**, 정상FIRST/로그인/선택/월드2회·ADD/rename/delete·저장재접속·축복UID의실제소비/이동을유지하고,4F5F·4E41·구슬UID의무소비/무ACK/무C371거절3개추가. 기본마을사본에pre-FIRST구슬1개를공급하고실제0964 UID를사용 |
| [79h1p1_y](../runs/hunt-bookmark-79h1p1_y/summary.json) | **9검사SUCCESS**, fresh pre-FIRST map2/(32665,32789)·마을bookmark1개·축복주문서2개의LOCAL시작저장. 실제4E4D수신row,ADD저장거절,선택0960→1개소비→map0마을이동/위치저장/정상Quit. 초기bookmark생성·던전도달은시험범위밖 |
| [2qcc206f](../runs/hunt-bookmark-2qcc206f/summary.json) | **5검사SUCCESS**, fresh pre-FIRST map37/(32667,32868)의같은정책fixture. 실제로그인·월드·수신row후ADD거절 및선택0960탈출거절,주문서수량·위치·저장row불변·정상Quit. 안타라스던전도달/사냥시험이아님 |

세summary에서모두failure_code/close_code null·cleanup_complete true·handler/hook오류0·`source_changes_during_run=[]`를직접확인했다. `bookmark_errors`의3/1/2개는각각명시적으로보낸거절요청의예상사유다. `SL_TEST_TIME_SCALE=10`으로실행했으며짧은왕복시험의실측speedup은약1.02~1.04배다. base60000→물리60000/62030,지역순차시험base61000→61000/63030이다. 원본클라이언트·포커스·입력·사용자저장은건드리지않았다.

정확 재실행 명령(각명령은앞실행close후하나씩):

```powershell
$env:SL_TEST_TIME_SCALE='10'
$env:SL_TEST_PORT_BASE='60000'
python -X utf8 -B C:/Users/Chansol/AppData/Local/Temp/claude/D--claude/0483de89-75e7-4b94-84b8-fb31fe00f575/scratchpad/fastbot/run_fast.py hunt_bot_bookmark --timeout 30
$env:SL_TEST_PORT_BASE='61000'
python -X utf8 -B C:/Users/Chansol/AppData/Local/Temp/claude/D--claude/0483de89-75e7-4b94-84b8-fb31fe00f575/scratchpad/fastbot/run_fast.py hunt_bot_bookmark --scenario bookmark_region --departure-map 2 --timeout 30
python -X utf8 -B C:/Users/Chansol/AppData/Local/Temp/claude/D--claude/0483de89-75e7-4b94-84b8-fb31fe00f575/scratchpad/fastbot/run_fast.py hunt_bot_bookmark --scenario bookmark_region --departure-map 37 --timeout 30
```

선정해시는각summary가전체목록을보존한다. 공통bot`377eaa317ade7a39e127ae297c26b8f4a43686abec7a01827a35e77292a5e75e`,feature`216220773fb8c88f0a7bca64d5cb9ef35fe5b4fe070079a762f02a26a468972b`,model`50f0b415a8a6d0e0bdc0bcb31225c7157725e154e942b4bb14580e00e5a30eb1`,외부공유realm`77c66fa74825df905fe367c614b2088bf128d7bc1e127daa54dbe1a845297ce5`다. realm은이번담당자가수정하지않았다. 초기성공4z2tleof/fgwh9gym/ypxlh754는당시Source로그대로보존하고최종Source와합산하지않는다. 실패 [5mg7obcr](../runs/hunt-bookmark-5mg7obcr/summary.json)는pre-FIRST준비에서transition인수누락, [pu0mh2qv](../runs/hunt-bookmark-pu0mh2qv/summary.json)는공용봇의옛map(0,1,2)기대실패다. 준비단계는기존PositionStore의transitionAPI를,봇기대는기존map_expansion2의정확시작위치/실수신상태확인을재사용해수정했다. guard·저장형식·공용봇은바꾸지않았다. 이번6개소유파일외수정·커밋·브랜치이동·수동실행핀갱신은하지않았다.
