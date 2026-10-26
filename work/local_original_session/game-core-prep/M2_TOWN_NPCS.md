# M2 말하는 섬 마을 비판매 NPC 자료

2026-10-26. 지정된 `tools/local_original_session/data/m2/town_npcs.json`과 이 문서만 작성한다. L1J는 읽기 전용 참고 자료이며 클래식 기준은 `MAPPING_SCOPE.md`의 **26.09.29.2001**이다. 자료의 원문 확인과 교차 버전 대응 후보를 기록한 것이며, 제품 로딩·NPC 표시·클릭·서비스의 실행 완료 판정은 아니다.

## 자료 범위와 판정

**마을 27 NPC ID·38배치 행(활성35, count0 비활성3)을 준비했다.** 일반 NPC는 `npcs` 24종, 비활성 Harbor Master·Oasis Stuff·게시판은 `special_npcs` 3종이다. 경계 밖 map0 자료 10배치는 `adjacent_npcs`로 분리했다. 이 배열에는 마을 서쪽·남쪽·북쪽 외곽도 포함하며 마을 배치 수에 합산하지 않는다. 기본 DB map0의 전체 54배치 중 상품 보유 NPC 6배치를 제외한 48배치를 이 세 배열에 보존했다.

경계는 클래식 `work/local_resource_provider/assets/data/region.jsonc:3`의 map0, **x32543..32671/y32905..32987**(중심 좌표, 양 끝 포함)이다. 원문은 `D:/SingleLineageRef/l1j-en-classic/db/l1jdb_m10.sql`의 `spawnlist_npc`·`npc`·`npcaction`이며 열 정의는 각각 1917·1544·1616행이다. JSON `reference_paths`의 약어와 각 `source_ref`가 정확한 파일/줄을 가리킨다. 별도 `etc/name_id_test` 표는 섞지 않았다.

기존 `shop_npcs.json`의 **판매 상품 없는 L1Merchant 서비스 17종도 포함**했다. impl 이름만으로 상인으로 제외하면 여관·안내·제작 등 요청 대상이 빠진다. JSON의 `existing_shop_npcs_cross_reference`가 기존 행을 교차 참조한다. 상품이 있는 Pandora·Cole·항구 배표 상인·호박 상인(마을4)과 외곽 상품 상인2는 `excluded_shop_npcs`에 원문 참조로만 남겼다. `shop_npcs.json`은 변경하지 않았다.

| 요청한 종류 | L1J ID / 중심 좌표 / 기본 normal·caotic stem | 확인 범위 |
|---|---|---|
| 경비병 | 60501 궁수 후보·60502 경비, 각각 마을6배치 / `patguard`·`patguard` | 좌표·heading은 JSON에 모두 보존. 클래식 template 후보는 양쪽 모두 10/58/68이고 선택하지 않음. |
| 텔레포터 | Lucas50015 / 32583,32922 / `teleisland1`·`teleisland1` | L1J 역할·배치 원문. 클래식 template는 미확정. |
| 초보 섬 텔레포터 | Zeno50016 / 32600,32914 / `zeno`·`zeno` | spawn50059=count0,90067=count1의 서로 다른 원행을 유지. |
| 텔레포터·퀘스트 이동 | Keith50017 / 32577,32957 / `telefire1`·`telefire2`; Serian50112 / 32600,32916 / `orenb1`·`orenb1` | 메뉴·실제 이동/비용은 L1J 참고 후보. |
| 창고 | Dorin60001 / 32575,32946 / `dorin`·`dorinl` | L1J 역할·배치·대사 종류. 클래식 이름/외형 선택은 미확정. |
| 여관 메뉴 후보 | Selena70012 / 32596,32929 / `inn`·`Inn1` | 원문 대소문자 유지. 기존 무상품 L1Merchant와 교차 참조. 여관 서비스를 Python에 추가하지 않음. |
| 마을 안내·관리 | 시장 비서70534 / 32588,32952 / `secretary1`·`secretary1`; Village Manager70528 / 32588,32953 / `othertown`·`othertown` | impl의 분기를 근거로 분류. 일반 초보 안내 NPC 전체를 찾았다고 확대하지 않음. |
| 제작·퀘스트·주민·혈맹 | 나머지 일반 NPC는 JSON의 `classification`·`classification_basis`·`behavior_source_refs` 참조 | 상품 표가 없는 NPC에게 상품을 만들지 않았고, 역할 미확정은 그대로 표시. |

`normal_action/caotic_action`과 별도로 `teleport_url/teleport_urla` 네 열을 원문 그대로 보존했다. 기본 행이 없으면 null과 `npcaction_row_present=false`, 존재하는 행의 빈 문자열이면 `""`로 구분한다. 실제 대사는 Java/XML에서 레벨·직업·퀘스트·성향 등에 따라 override될 수 있다. 비활성3행은 Zeno의 옛 행·Liri·몬스터형 Harbor Master이며 임의 활성화하지 않는다. 같은 좌표32575,32946의 Dorin·주민4명도 서로 다른 원행으로 보존했다. 랜덤 반경·이동 범위·겹친 위치의 클래식 통행/점유는 미확인이다.

### 클래식 catalog 대응

`MAPPING_SCOPE.md` 3장의 이름 토큰→한국어 이름·변종→f2/SPR 이름 방식으로 좁혔다. **원문 대응 확정7종, 경비 다중 후보2종, 토큰 대응 미확정18종**이다. `confirmed_catalog_correspondence_only`는 아래 dump 행과 SPR 자료의 대응만 뜻한다. 배치·대사·교차 버전의 실제 동일 NPC·화면 동작은 이 판정에 포함하지 않는다.

| L1J ID / 이름 토큰 | 클래식 template / 한국어 이름 / f2 SPR | 클래식 원문 |
|---|---|---|
| 70523 / $1053 | 300 / 가죽 세공사 라다르 / 988 | native-dump:181, sprites:593 |
| 70525 / $1055 | 302 / 뼈 세공사 라이엔 / 981 | native-dump:183, sprites:586 |
| 70100 / $454 | 82 / 렝고 / 704 | native-dump:51, sprites:379 |
| 70101 / $455 | 83 / 휜 / 705 | native-dump:52, sprites:380 |
| 70102 / $456 | 84 / 쥬디스 / 706 | native-dump:53, sprites:381 |
| 70529 / $862 | 322 / 모나 / 234 | native-dump:189, sprites:220 |
| 70538 / $2238 | 984 / 혈맹 집행인 엘도린 / 949 | native-dump:536, sprites:570 |

`native-dump`는 `work/source_game_data/native-dump-v1.jsonl`, `sprites`는 `work/asset_link_audit_20261007/sprite/current-parsed.jsonl`이다. 위7종은 L1J gfxid도 f2와 일치한다. 경비 $240의 클래식10은 SPR51, 58/68은 둘 다 SPR335다. L1J60501의 gfx335만으로 58/68을 고를 수 없고, 60502의 gfx148은 이 세 후보 f2와 다르므로 별도 후보로만 남겼다. template 미확정인 항목도 같은 번호 SPR이 있으면 이름·type·원문을 기록했으며 이를 선택된 외형으로 승격하지 않았다. `?????????` 토큰·빈 토큰도 원문대로 유지했다.

외곽 자료의 대응3종(파린301/SPR983·토마89/727·게렝44/237)은 마을 확정7종에 합산하지 않았다. 모든 배치는 여전히 **출처 있는 L1J 위치 후보**다.

## 출현 패킷 재사용 결론

**4E96 Actor 형식과 기존 인코더·프레이밍은 재사용할 수 있다. 현재 `world_visibility.spawn_frame()` / `npc.NpcSpawn`에 마을 자료를 그대로 넣는 것은 불가능하다.**

| 접점 | 확보된 근거와 적용 범위 |
|---|---|
| 기존 M1 경로 | `tools/local_original_session/world_visibility.py:81`의 `monster_fields()`가 f1 좌표, f2 UID, f3 SPR, f5 방향, f9 이름, f39 M1 template를 채운다. `:88`의 `spawn_frame()`은 `npc.NpcSpawn(..., policy=WORLD_POLICY)`를 쓴다. |
| 현재 허용 범위 | `tools/local_original_session/npc.py:26`은 `(SPR,template)` 네 쌍 `(56,0)/(57,1)/(1022,245)/(33,8)`만 허용한다. `:83`은 f16=false/f21=빈값을, `:85`는 해당 쌍을 검사한다. 이 준비 작업은 이 범위를 변경하지 않는다. |
| 공통 wire | `npc.py:97`의 `encode()`는 기존 `session.world.encode_payload(0x4e96, fields)`와 `u16LE(body+6) + u16LE(4E96) + body + trailer2B`를 사용한다. Actor required 필드는 1..24,27,28이다. map은 별도 기존 4E95/WORLD 컨텍스트이며 Actor에 새 map 필드를 만들지 않는다. |
| 기존 일반 NPC 경로 | `implementation-4/shop-quest/dialogue-contract/normal-npc-target/normal_npc_source.py:41`의 `NormalSpawn`과 `:60`의 `frame()`이 같은 world codec·4E96 형식을 쓴다. 원문 연결은 `run106_shop_dialog_contract/normal-npc-spawn-main-review.json:34`의 4E96→factory→InteractiveNPC→Interaction→4E43이다. |
| 일반 클릭 가능 subset | 위 run106 `:363`은 effective SPR(f69가 present면 f69, 아니면 f3)의 실제 type15, f16=false, 명시 f39>=0, present 빈 f21을 충분 조건인 로컬 subset으로 구분한다. 모든 NPC 외형을 type15로 취급하거나 SPR 값을 강제로 바꾸는 근거가 아니다. 경비·특수 객체의 다른 타입을 동일한 대화 경로로 간주하지 않는다. |
| template와 wire f39 구분 | `run143_normal_npc_f39_template/main-review.json:104` 이하에서 일반 NPC 경로의 f39는 scalar 저장→Actor3C까지만 확인됐다. 이 일반 경로에서 CommonNpc/template 조회가 입증되지 않았으므로 JSON의 클래식 catalog template ID를 자동으로 wire f39의 정당 값으로 삼지 않는다. Monster의 별도 template 소비 근거와도 구분한다. |

위 implementation 경로의 기준은 `work/local_original_session/`, run* 경로는 `work/local_server_rea_20261016/`이다. 실제 적용 시 기존 일반 NPC 생산자와 UID·map·known-set·제거 수명을 연결할 작업이 남아 있다. JSON만으로 원본 외형/분기·실제 생성·클릭이 확인되지는 않는다.

이번 자료에서 읽은 SPR type은 경비5, 대응된 서비스7종6, 게시판14다. **특히 서비스의 type6을 위 type15 subset과 같다고 확인하지 않았다.** 기존 4E96 형식은 공통으로 재사용하되 해당 실제 타입의 생성·정상 입력 분기는 기존 분석의 정확한 소비 경로와 연결해야 한다. 클릭을 만들기 위해 외형이나 type을 임의 변경하지 않는다.

## 클릭과 대사창의 기존 근거

**새 opcode 분석은 필요하지 않다. 클릭 요청 4E43, 대사창 응답 4E44, 메뉴 행동 요청 4ED4의 기존 source·codec이 있다.**

| 기존 자료 | 재사용할 내용과 한계 |
|---|---|
| `run106_shop_dialog_contract/dialog-request-main-review.json:29` | `LIN::CS_DIALOG_REQ` / C2S4E43, required signed int32 f1 하나. 원 입력 Actor slot8 qword의 low32 비트를 signed int32로 보낸다. 서버 catalog ID나 L1J npcid를 대신 넣지 않는다. 실제 선택 NPC와 현재 서버 UID의 대응은 기존 target resolver의 책임이다. |
| `run106_shop_dialog_contract/dialogue-contract.json:98` 및 `dialogue-contract/INTEGRATION.md:13` | S2C4E44=`SC_HYPERTEXT_NOTI`: required int32 f1·string f2, optional string f3·repeated f5. 입력형 4E45=`SC_HYPERTEXT_INPUT_NOTI`도 별도 schema가 있으나 단순 대화의 임의 대체 응답이 아니다. |
| `dialogue-contract/hypertext-field4/INTEGRATION.md:14` | 4E44 f4는 후속 확정된 repeated signed int64, tag20/wire0, 일반 two's-complement varint다. 옛 INTEGRATION의 f4 UNSUPPORTED는 이 확장 이전 기록이다. 값의 업무 의미나 임의 기본값은 공급하지 않는다. |
| `run122_dialogue_resource_link/main-filename-review.json:16` 및 `menu-resource-stem-v1/INSTALL_API.md:5` | 최신 filename 계약은 **`data/uml/` + 4E44.f2 stem + `.uml`**이다. 예: `pixel`→`data/uml/pixel.uml`. 옛 fullkey `pixel.uml`을 넣으면 `.uml.uml`이 된다. run120의 중간 설명 대신 이 후속 교정을 사용한다. f3는 별도 optional payload이며 HTML 본문이라고 확정하지 않는다. |
| `dialogue-contract/INTEGRATION.md:17` 이후 | C2S4ED4=`CS_HACTION_REQ`: required signed int32 f1·string f2, optional string f3·int32 f4/f5. 기존 정상 producer는 좌표 둘을 present로 쓰며 좌표 입력이 없으면 0/0이다. action literal·인자를 현재 메뉴 자원과 연결해야 한다. |
| `menu-resource-stem-v1/INSTALL_API.md:17` | 기존 `NormalSpawn`→WORLD publication→4E43→4E44 stem→원본 자원/버튼→4ED4→기존 소비 경로와 cleanup을 재사용할 위치다. 이 작업에서 설치하거나 실행하지 않았다. |
| `integration-1/packet-shop-actual-v4/shop-result.json` | 과거 정상 패킷 경로의 대화·거래·저장 복원 근거가 있다. 해당 결과도 `native_game=false`, `native_ui=UNKNOWN`, `client_ui_claim=false`다. 이를 이번 마을 NPC 외형·대사창 표시 성공으로 확대하지 않는다. |

L1J `npcaction.normal_action/caotic_action/teleport_url/teleport_urla`는 **L1J의 대사/메뉴 종류·stem 원문**이다. 클래식 `data/uml/<stem>.uml`의 존재·본문/현지화·현재 NPC 문맥과 대응하지 않은 값을 4E44로 바로 보내지 않는다. `npcaction` SQL은 `NPCTalkDataTable.java:57-65`가 읽으며, 이름이 비슷한 `NpcActionTable.java`는 별도 XML 행동 로더다. 각 NPC Java/XML의 조건부 override도 표의 기본 stem과 구분한다.

## 확인 범위

지정 Python `C:/Users/Chansol/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe -X utf8 -B -`에 일회성 stdin 코드를 전달했다. JSON 재읽기, 경계 분리·배치 ID 중복·상품 제외를 확인했고, 별도 원문 대조에서 마을 선정 SQL38행과 JSON38행의 집합이 일치(누락0/추가0), 포함된 마을·외곽48배치의 좌표/count/heading/반경/이동 범위 및 npcaction 네 열·줄 번호 일치를 확인했다. 클래식 후보13개(마을 대응7+경비 후보3+외곽 대응3)의 실제 dump ID·토큰·한국어 이름·f2 및 SPR ID/type도 일치했다. 문서는 UTF-8 재읽기로 확인했다. 최종 JSON은 119,384바이트다. 영구 검사기 파일은 만들지 않았다.

L1J·게임·서버·broker 실행은 하지 않았다. 새 추출기·검증기·guard·pin·해시 검사·제품 코드·저장·큐·commit을 추가하지 않았다. 데이터의 SQL/클래식 원문 대조와 JSON 파싱만 이 준비 범위의 확인이다. 실제 표시·입력·창고·텔레포트·여관 등 서비스와 30분 플레이는 **UNRUN**이다.

## M2 template·sprite 추가 대조 결과

2026-10-26 지정 데이터 조사 후속. 이 절은 위 최초 준비 결과에 추가하며, 이번에는 `town_npcs.json`과 `shop_npcs.json`의 기존 값·근거를 함께 수정했다. **새 template 확정0종, 마을 기존 확정7종·경비 후보2종·미확정18종, 상품 보유 상인4명 미확정 유지**다. 경비60501은 두 template58/68의 공통 외형 후보 SPR335로 좁혔다. 선택된 template/sprite는 새로 채우지 않았다. 기존 배치·대사·후보 배열·상품 수·구조·summary는 보존했다.

아래 `native-dump`·`sprites`·`l1jdb`는 위와 같은 정확한 파일 약어다. 부재 판정은 저장된 native NPC951행(`native-dump:1–951`)의 `name.reference`와 f2 및 SPR2976행(`sprites:1–2976`)을 읽은 범위다. L1J 이름의 한국어 번역을 지어내거나 같은 그래픽의 다른 이름을 동일인으로 취급하지 않았다. blank/`?????????`는 이름 키가 아니다.

| 마을 미확정 L1J ID·이름·토큰 / NPC 원문 | 동일 번호 SPR 원문 / native f2 대조 | 남은 입력 |
|---|---|---|
| 50015 Lucas `$829` / `l1jdb:21734` | SPR6377 없음; 같은 f2의 native NPC 없음 | 현재 이름·변종→classic template/f2 연결 부재. SPR 번호도 부재. |
| 50016 Zeno `$1418` / `l1jdb:21735` | SPR1510 없음; 같은 f2의 native NPC 없음 | 현재 이름·변종→classic template/f2 연결 부재. SPR 번호도 부재. |
| 50017 Keith `$1068` / `l1jdb:21736` | SPR984 `glen` (`sprites:589`); 같은 f2의 native NPC 없음 | 현재 이름·변종→classic template/f2 연결 부재. 같은 SPR 존재만으로 확정 불가. |
| 60001 Dorin `$309` / `l1jdb:21952` | SPR143 `dorin` (`sprites:135`); 같은 f2의 native NPC 없음 | 현재 이름·변종→classic template/f2 연결 부재. 같은 SPR 존재만으로 확정 불가. |
| 70012 Selena `$955` / `l1jdb:22067` | SPR695 `ysorya` (`sprites:370`); 612 데일리 (`native-dump:350`) | 현재 이름·변종→classic template/f2 연결 부재. 같은 SPR 존재만으로 확정 불가. |
| 70526 Raidar `$2883` / `l1jdb:22183` | SPR1278 `npc wanderer` (`sprites:826`); 352 잭 (`native-dump:210`), 544 데릭 (`native-dump:305`), 715 로터스 (`native-dump:379`), 720 로쿠 (`native-dump:383`) | 현재 이름·변종→classic template/f2 연결 부재. 같은 SPR 존재만으로 확정 불가. |
| 70524 Lavienue `$2690` / `l1jdb:22181` | SPR1307 `npc alchemist` (`sprites:851`); 346 마법 연금술사^모리아 (`native-dump:204`), 719 티파니 (`native-dump:382`) | 현재 이름·변종→classic template/f2 연결 부재. 같은 SPR 존재만으로 확정 불가. |
| 70520 Alchemist `$3480` / `l1jdb:22177` | SPR2090 `varyeth` (`sprites:1429`); 697 바뤼에스 (`native-dump:362`) | 현재 이름·변종→classic template/f2 연결 부재. 같은 SPR 존재만으로 확정 불가. |
| 70531 Jem `$1928` / `l1jdb:22188` | SPR1307 `npc alchemist` (`sprites:851`); 346 마법 연금술사^모리아 (`native-dump:204`), 719 티파니 (`native-dump:382`) | 현재 이름·변종→classic template/f2 연결 부재. 같은 SPR 존재만으로 확정 불가. |
| 50111 Liri `$3318` / `l1jdb:21804` | SPR940 `Teleporter` (`sprites:561`); 721 타우스 (`native-dump:384`) | 현재 이름·변종→classic template/f2 연결 부재. 같은 SPR 존재만으로 확정 불가. |
| 70099 Kuper `$2344` / `l1jdb:22154` | SPR792 `Ofo` (`sprites:451`); 104 오포 (`native-dump:64`), 423 알드레드 (`native-dump:254`) | 현재 이름·변종→classic template/f2 연결 부재. 같은 SPR 존재만으로 확정 불가. |
| 50112 Serian `$3317` / `l1jdb:21805` | SPR940 `Teleporter` (`sprites:561`); 721 타우스 (`native-dump:384`) | 현재 이름·변종→classic template/f2 연결 부재. 같은 SPR 존재만으로 확정 불가. |
| 70534 Secratary to the Mayor `$2170` / `l1jdb:22191` | SPR460 `ishmael` (`sprites:301`); 874 마샤 (`native-dump:462`) | 현재 이름·변종→classic template/f2 연결 부재. 같은 SPR 존재만으로 확정 불가. |
| 70528 Village Manager `$2171` / `l1jdb:22185` | SPR971 `steward` (`sprites:576`); 747 제로 (`native-dump:397`) | 현재 이름·변종→classic template/f2 연결 부재. 같은 SPR 존재만으로 확정 불가. |
| 81200 Unknown `?????????` / `l1jdb:23225` | SPR1768 `dwarf master` (`sprites:1131`); 605 대장장이^이벨빈 (`native-dump:348`), 1367 보석 연구가^카리프 (`native-dump:551`) | 현재 이름·변종→classic template/f2 연결 부재. 같은 SPR 존재만으로 확정 불가. |
| 81000 Harbor Master `$320` / `l1jdb:23065` | SPR148 `kent castle guard` (`sprites:140`); 86 근위병 (`native-dump:54`) | 현재 이름·변종→classic template/f2 연결 부재. 같은 SPR 존재만으로 확정 불가. |
| 80001 Oasis Stuff `` / `l1jdb:22910` | SPR2299 없음; 같은 f2의 native NPC 없음 | 현재 이름·변종→classic template/f2 연결 부재. SPR 번호도 부재. |
| 80006 Message Board `$1385` / `l1jdb:22915` | SPR1546 `board b` (`sprites:947`); 같은 f2의 native NPC 없음 | 현재 이름·변종→classic template/f2 연결 부재. 같은 SPR 존재만으로 확정 불가. |

경비60501은 `l1jdb:21989` $240/gfx335와 `native-dump:37/:43`의58/68 $240/경비병/f2=335, `sprites:265`의 `guard archer`가 맞는다. 기존10 후보(`native-dump:10`, f2=51, `sprites:48 guard`)는 토큰만 맞는 외형 변종으로 표시했다.58/68을 가를 현재 식별/배치 근거는 없다. f23의60/8은 검증된 레벨이 아니므로 선택 근거로 쓰지 않았다(`docs/NPC_FIELD_SEMANTICS.md:5`). 경비60502(`l1jdb:21990`)는 $240/gfx148인데 토큰 후보10/58/68의 f2가 모두 다르다. gfx148의 실제 native 대응86/$475/근위병(`native-dump:54`, `sprites:140 kent castle guard`)도 이름 토큰이 충돌해 선택하지 않았다.

| 상품 보유 상인 | 근거와 결론 |
|---|---|
| 70014 Pandora `$269` (`l1jdb:22069`) | SPR98 `pandora` (`sprites:94`); 해당 f2의 native NPC 없음. 해당 토큰 native NPC 부재; template는 미확정. |
| 70013 Cole `$1637` (`l1jdb:22068`) | SPR725 `citizen girl` (`sprites:398`); 동일 f2는 134/루카 (`native-dump:83`), 429/어니스트 (`native-dump:260`), 915/제시카 (`native-dump:483`), 916/미사 (`native-dump:484`)로 이름이 다름. 해당 토큰 native NPC 부재; template는 미확정. |
| 70011 Harbor Master `$320` (`l1jdb:22066`) | SPR148 `kent castle guard` (`sprites:140`); 동일 f2는 86/근위병 (`native-dump:54`)로 이름이 다름. 해당 토큰 native NPC 부재; template는 미확정. |
| 81123 Pumpkin Trader `$2063` (`l1jdb:23171`) | SPR2499 기록 없음. 해당 토큰 native NPC 부재; template는 미확정. |

기존 출현 자료도 이 빈칸을 채우지 않는다. `implementation-2/npc-motion-goal/packet-static-npc-navigation-v1/API.md:23–25`의 static SHOP는 선정 NormalSpawn publication의 UID·위치·현재 수명 소비다. `implementation-2/npc-motion-goal/normal-npc-publication-source-v1/CONTACT.md:11–15`도 제공된 NormalSpawn의 frame/publication을 identity 생산자로 보지 않는다. `implementation-4/shop-quest/merchant-source-input-v1/API.md:21–23`, `:38`의 SPR1552는 auction board의 명시 LOCAL 선택이며 Pandora 등 위 상인에 대한 catalog 대응이 아니다. 이 경로들은 `work/local_original_session/` 아래다.

`work/local_server_rea_20261016/run106_shop_dialog_contract/normal-npc-spawn-main-review.json:45`의 factory category 허용 집합은 {4,6,7,8,14,15}다. type6 서비스가 존재할 수 있는 원문 사실을 type15 입력 성공이나 특정 NPC 식별 증거로 확대하지 않았다. `run122_dialogue_resource_link/main-filename-review.json:16`, `:31`은 UML stem→파일명 계약만 닫으며 NPC identity/실제 load·render는 닫지 않는다. `run143_normal_npc_f39_template/main-review.json:104–114`의 f39 scalar 저장·선정 경로 CommonNpc 조회 미입증도 유지한다. catalog template, wire f39, runtime 표시·입력은 별개다.

검증: 지정 Python `C:/Users/Chansol/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe -X utf8 -B -` 일회성 stdin으로 JSON 재읽기·기존 중첩 key/배열 길이 보존·배치/대사/선택/summary 불변·남은 catalog 후보의 실제 ID/토큰/f2/SPR 원문 대조 PASS. town18행의 basis/sprite note, 경비2행의 basis/sprite note와 기존 후보6개의 field_status, shop4행의 mapping_status와 존재하는 SPR3개의 status만 바꿨다. 이 자료 변경을 시험하는 지정 순수모듈 시험은 없고 제품 코드도 변경하지 않아 별도 제품 suite는 실행하지 않았다. 새 분석/검증 도구·guard·pin/hash 검사·commit 없음. 게임·서버·L1J 실행 및 실제 NPC 표시·입력·서비스는 **UNRUN**.

다음에 필요한 최소 입력은 각 미확정 이름의 현재 classic NPC 이름/변종→template/f2 기록 또는 이미 확보한 source-bound identity 대응이다. 경비58/68은 같은 이름·외형을 구별하는 현재 변종/배치 근거가 필요하다. 새 원본 확보·재역분석·실행은 이번 범위에서 수행하지 않았다.
