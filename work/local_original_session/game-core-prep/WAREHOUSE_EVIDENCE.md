# 창고 원본 UI·패킷 계약 근거

2026-10-26 사용자 지정 read-only 정적 조사. **보유품에서 맡길 행을 고르는 A 모델의 수신은 S2C `4ED2`(SC_WAREHOUSE_ITEM_COUNT_NOTI)다. `0971`은 발급된 보관 행을 고르는 B 모델이며, `0973` INFO를 맡김 목록으로 대입할 근거는 없다.** 기존 run295/298/304와 run388의 자료·방법을 재사용하고, 빠져 있던 COUNT 등록→A 모델→4ED1 연결과 각 메시지 required mask를 추가했다. SOURCE_ONLY / 화면·입력·송수신·현재 서버·저장 시험 UNRUN. 일반 중지·기존 실패·저장·UIDburn은 유지한다.

## 기준과 원문 위치

새 산출물의 기준은 `work/local_server_rea_20261016/run394_warehouse_ui/`(아래 `R/`)다. `extract.py:10`의 기존 run380 `View`를 import하여 보존 CONTROL selector 파일의 섹션·PData와 Capstone만 읽었다. RVAs는 복원 영상 기준이며 preferred VA=`0x140000000+RVA`다. inherited 원본 SHA256=`9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`; 원본 LC·현재 프로세스·공유 REA active target을 열거나 실행하지 않았다. input record 경로와 기존 해시는 각 JSON의 `source_records`에 있다. 전체 carrier 재해시는 하지 않았다.

`R/reuse_comparison.json`에서 run304의 LIST handler `5C0470`, confirm `B1CCD0`, LIST model constructor `5BE550`, close sender `5C1860`, close serializer `7B2E20`의 선정 원문 총4,320B가 현재 reader의 같은 RVA bytes와 일치했다. 이는 이 다섯 구간의 재사용 근거이며 전체 carrier 동일성·runtime·옛 PASS 이전을 뜻하지 않는다. `source_excerpts.md`는 아래 JSON의 원 줄 번호·RVA·명령을 모은 발췌다.

## NPC 클릭·대사·action

| 단계 | 확인된 원 계약 | 경계 |
|---|---|---|
| 클릭 C2S4E43 | required f1 signed i32, 현재 Actor slot8 UID의 low32 | NPC template/L1J ID가 아니다. `M2_NPC_MENUS.md:11`, run106 `dialog-request-main-review.json:29` 재사용 |
| 대사 S2C4E44 | required f1 i32/f2 string, optional f3 string, repeated f4 i64/f5 string | f2=`storage`가 `data/uml/storage.uml`을 찾는 stem 후보다. NPC별 실제 발급은 미관측. `M2_NPC_MENUS.md:12`·`:40` |
| 메뉴 C2S4ED4 | required f1 i32/f2 action string; optional f3 string/f4·f5 i32 | f1은 수신 메뉴 UML+38 echo이며 최초 NPC UID와 자동 동치가 아니다. normal writer의 f4/f5는 present0/0 또는 event 좌표. cookie는 실제 event+40에서 온다 |

보존 원 `storage.uml`에는 개인 `deposit`·`retrieve`, 별도 `deposit-pledge`·`retrieve-pledge`·`history`가 있다. 원문은 run298 `contract.md:3`·`:7`, 동일 자원 회수는 `M2_NPC_MENUS.md:40`을 재사용한다. `<a>`에 argument 속성이 없다는 사실만으로 wire f3 부재를 확정하지 않는다. local action lookup 이후 fallback HACTION이라는 기존 경계도 유지한다. **action 두 개와 아래 A/B native 모델은 각각 source 사실이지만, 공식 서버가 특정 action에 발급한 응답·nativekind·현재 context를 이번 정적 자료로 관측하지는 않았다.** `deposit→4ED2`, `retrieve→0971`은 모델이 사용하는 행의 성격에 맞는 연결 추론이며 화면 실험에서 확인할 항목이다.

## S2C4ED2: COUNT가 만드는 A 모델

숫자 opcode는 이름으로 추정하지 않았다. `R/count_factory_pointer.json:3`의 publisher pointer11A79E8과 table11A79D8을 `count_registration.json:4`의 **29573D LEA→295744 MOV EDX4ED2→29575C CALL292F80**에 연결했다. `count_publisher.json:117`의 2FEF14→31A110 생성자 호출, `count_constructor.json:73`의 31A146→vft11F2F30, `storage_handler_types.json:3`의 COL130EEF0/TD1683E88가 정확 SC_WAREHOUSE_ITEM_COUNT_NOTI를 결속한다. publisher2FEF41→event18000C0, `storage_handlers.json:5310`의 5BEDC2 R8=5BFD20/5BEDCC RCX=같은 event/5BEDD3 CALL5C21F0이 실제 A handler를 지정한다.

| field | protobuf type / wire | required 여부 | 원 소비 |
|---|---|---|---|
| f1 | u32 /0 varint | required | raw+18(wrapper+20)→A model+8 DWORD |
| f2 | enum int32 저장 /0 | required | raw+1C(wrapper+24)→A model+0 nativekind |
| f3 | u32 /0 | required | raw+20(wrapper+28)→A model+C DWORD |
| f4 | u32 /0 | optional schema | raw+24(wrapper+2C)→StorageSubsystem+18 context→4ED1.f1 |

descriptor16048F0/field records는 `R/count_schema.json:18`, actual virtual20 IsInitialized7B2380의 `~hasbits &7`은 `required_presence.json:4`다. f4까지 required로 바꾸지 않는다. 다만 actual server issuer의 명시 context가 필요한 업무와 protobuf optional은 별개다. f1·f3의 current-count/capacity 같은 업무 이름·정상값은 UNKNOWN이다.

handler5BFD20은 각 presence bit를 검사해 네 DWORD를 복사한다(`storage_handlers.json:133`). 5BFE52의54DE50으로 얻은 현재 보유품을 필터링하고, 5BFEEC의 local detach 뒤 5BFEF1..5BFF59에서 context·kind·두 DWORD를 복사하며, 5C00C8에서 **Subsystem+28에 A 모델**을 설치한다(`:533`, `:605`, `:989`). 서버가 deposit 행 전체를 `0971`로 보내야 A가 만들어지는 구조가 아니다. 필터 함수4EF780·36FE00의 의미를 원정책으로 새로 명명하지 않았다.

## S2C0971: LIST가 만드는 B 모델

기존 run304 등록·typed event·handler와 row 복사 근거를 재사용한다. 새 `R/list_nested_schema.json:18` 및 actual IsInitialized7B2D30(`required_presence.json:586`)이 scalar requiredness를 추가 확정한다.

| field | protobuf type / wire | required 여부 | 원 소비 |
|---|---|---|---|
| f1 | u32 /0 | required | Subsystem+18 context→4ED1.f1 echo |
| f2 | u32 /0 | required | B model+8; 업무 이름 UNKNOWN |
| f3 | enum int32 저장 /0 | required | B model+4 nativekind→확정 mode 분기 |
| f4 | u32 /0 | required | B model+10, 후속 lookup 입력; 정확 업무 이름 UNKNOWN |
| f5 | u64 /0 | required | low32→B model+14·표시 합산. 공식 fee라는 근거 없음 |
| f6 | u32 /0 | required | B model+C; 업무 이름 UNKNOWN |
| f7 | repeated WarehouseItemInfo /2 length-delimited | 0개 이상, 각 행 validation | child **required f1:u32 opaque entrykey**, **required f2:full ItemInfo message** |
| f8 | bool /0 | optional | local active/표시 flag. business 성공 ACK가 아님 |

outer raw offsets30/34/38/3C/40/48/18/4C, nested offsets20/18은 `list_nested_schema.json:18`·`:96`에 있다. actual outer mask `0x3F`는 f1..6만 필요로 하며 f8은 검사하지 않는다. row7B2660은 mask3 및 ItemInfo7A2280의 초기화까지 검사한다(`nested_required_and_confirm.json:4`). ItemInfo의 원 필드·unknown metadata를 보존한다. entrykey는 ItemInfo.f1의 원 item UID와 별개이며 template·배열 index·새 UID로 바꾸지 않는다.

5C0470은 기존 B 모델이 있고 아직 active=false면 행을5BE630으로 갱신하며, 그렇지 않으면 detach→5BE550 생성→Subsystem+38 설치를 수행한다. f8=true일 때 B.active를1로 만들어 표시 경로를 진행한다(`storage_handlers.json:2468`·`:2576`). 이 갱신 분기가 존재한다는 사실은 공식 서버의 거래 후 LIST 재발급 순서를 증명하지 않는다.

## S2C0973 INFO는 별도 schema

기존 run295 INFO0973 등록→30A810 publisher→17FA000 event를 재사용했다. 정확 outervft11E6680/TD16823E8와 nestedvft11EECF8의 metadata를 추가했다(`R/info_schema.json:18`·`:60`).

| 메시지 | 필드 | requiredness |
|---|---|---|
| INFO0973 outer | f1:i32, f2:i32, repeated f3:Item | f1/f2 required; 각 child 초기화 검사 |
| Item | f1..f4:i32, f5:string | 다섯 필드 모두 required |

모든 i32는 wire0 varint, string/nested는 wire2다. INFO Item.f5를 수량/u64로 해석하지 않는다. actual723A60의 mask3·child723630 호출, child723630의 mask1F로 확인했다(`R/required_presence.json:232`·`:366`). byte 길이·signedness와 업무 의미는 구분한다. 각 필드의 업무 이름, INFO가 개인·혈맹 어느 창에 쓰이는지, 실제 subscriber는 UNKNOWN이다. `info_event_refs.json`의 bounded RIP-reference 조사에서 발행/초기화 외 concrete receiver는 확인되지 않았다. computed alias·비PData·다른 주소 구성의 전역 부재는 주장하지 않는다.

## C2S4ED1 확정·수량·닫기

원 senderB1CCD0의 동일 Subsystem에서 context를 읽는 run304 계약과 새 원문을 함께 사용한다(`R/nested_required_and_confirm.json:272`·`:1336`).

| 현재 native 모델 | 정확 kind 조건 | 4ED1.f2 | child.f1의 출처 |
|---|---|---|---|
| A=COUNT4ED2→Subsystem+28 | DWORD model+0가1 또는3 | 1 | 현재 Inventory lookup에 쓰는 selected node+28 key |
| 같은 A | kind2 | 3 | 같은 Inventory key |
| A 없고 B=LIST0971→Subsystem+38 | DWORD model+4가1 또는3 | 2 | 선택된 server-issued node+1C entrykey |
| 같은 B | kind2 | 4 | 같은 entrykey |

**kind1/2/3의 개인/혈맹/요정 enum 이름은 아직 확정하지 않았다.** kind1과3이 같은 request mode로 합쳐지는 사실을 이유로 scope를 합치지 않는다. A/B·kind를 서버가 발급하고 같은 current 목록/행에 결속해야 한다.

4ED1은 기존 CS_BUYSELL_REQ를 재사용한다: required f1:u32 context, required f2:enum, repeated f3 `{required f1:u32 key, required f2:u64 quantity}`, optional schema f4/f5:i32. **창고 normal writer는 f4/f5를 둘 다 present0/0으로 보낸다.** 상점 BUY5/SELL6의 null 좌표-2/-2와 다르다. 실제 선택 수량은 model의 positive signed i32를 u64로 sign-extend하므로 normal 범위는1..2,147,483,647이다. 전부0이면 warning2FD2→close만 하고4ED1은 없다. packetless 행·수량 선택은 다음 f3에 반영된다. wire에는 row count 대신 repeated f3가 있으며, 슬롯 상한/최대 선택 행수는 이 sender만으로 확정되지 않는다.

원 native는 4ED1 전송 직후5C1860을 호출한다(`R/nested_required_and_confirm.json:1140`·`:1756`); 서버 ACK를 기다리지 않는다. 5C1790은 context·A/B/기타 모델을 detach/정리하고,5C1860은097B(CS_CLOSE_WAREHOUSE_NOTI)를 보낸다. 기존 run304 close_serialization의 normal unset enum/tagclear 경로는 **protobuf body0B**다. schema는 optional enumf1 한 필드이며 “항상 schema가 빈 메시지”라는 뜻이 아니다. local close/097B는 서버 lease·CAS·저장·업무 성공의 증명이 아니다.

위 표의 순서는 필드 번호/normal writer의 논리 순서다. protobuf scalar는 fixed-width 정수가 아니며, 필드 번호·wiretype·presence와 데이터 폭을 지킨다. 순서 자체를 모든 protobuf 입력의 새 수신 제약으로 만들지 않는다.

## 결과 Inventory·목록 갱신과 기존 실행 근거

원 generic Inventory 수신 계약은 run388 `CONTRACT.md`의 “확정 요청과 후속 통지”와 기성 codec을 재사용한다: 기존 UID 수량 변경은 S2C0965 `{f1:[ItemInfo{f1:u32 UID,f4:u64 newQ}]}`(`tools/local_original_session/inventory_update.py:42`, `:151`), 새 UID 추가는 완전한 ItemInfo의0964(`inventory.py:303`), 제거는0978.f1 UID(`item_transfer_protocol.py:39`, `:262`)다. UPDATE0이 행 제거를 자동 뜻하지 않으며, generic UPDATE는 없는 UID를 새로 생성하지 않는다. 화폐도 같은 Inventory 자산으로 다루는 기존 LOCAL backend 계약을 재사용한다.

**공식 창고 성공 뒤 Inventory/COUNT/LIST/INFO가 어떤 순서·부분집합으로 오는지는 UNKNOWN이다.** 4ED1/097B 다음에0973을 가짜 성공 ACK로 만들거나 COUNT를 “거래 완료”로 처리할 근거가 없다. 기성 SHOP의 REMOVE→UPDATE→ADD 순서는 LOCAL projection이며, 창고 공식 순서로 이전하지 않는다.

이전 `warehouse-business-v1-final/API.md:7`·`:23`은 v22 입고/v24 출고/v25 fresh의 packet·native CAS·저장 결과와 **두 action 뒤 LIST0971→확정→full0964**라는 당시 LOCAL 흐름을 기록한다. 이 실행 성공은 보존한다. 그러나 문서 자체가 화면/input을 입증하지 않는다고 한정하며, 이번에 확인한 COUNT→A native UI를 그 시험이 통과했다고 소급하지 않는다. 이번에는 해당 runnable·Store·savedata·packet client를 import/실행하지 않았다.

`world_town_services.py:43`–`:52`의 personal150/player180슬롯·level≥5·무료 입고·서로 다른 출고 UID당30A·batch all-or-nothing은 현재 **LOCAL backend 정책**이다. 과거 L1J100슬롯/순차 commit이나 보존 원30A 안내문과 구분하며, 이번 wire/메뉴 조사로 공식 수치·경제 정책을 확정하지 않았다.

## 미확정과 최소 화면 실험안 — 미실행

남은 입력은 (1) 실제 창고 NPC의 현재 UID→4E44.storage/action 발생, (2) 개인 deposit/retrieve에 대응해 공식/선정 로컬 서버가 발급하는4ED2·0971의 context/kind와 f1/f3·f2/f4/f5/f6 값, (3) INFO의 실제 사용처, (4) 원 UI 실제 수량 선택/확정/창 닫힘·후속 Inventory와 정당 저장/복원이다. 단일 response occurrence의 숫자값은 보편 슬롯·수수료 규칙이 아니다.

향후 실행이 허용된 **시험 worker 하나**가 owned non-input desktop/Job와 정상 시험 저장에서 수행할 최소 실험은 다음과 같다. 기존 사용자 포커스·커서·전역 입력은 건드리지 않는다.

1. 정상 로그인→캐릭터→월드→실제 창고 NPC 클릭→4E43→4E44 stem/context→실제 `deposit`4ED4를 기록한다. 서버가 발급한 COUNT4ED2와 그 current context/kind를 확인한다. LOCAL 후보 실험이라면 숫자 kind의 출처를 명시하고 개인 scope 확정으로 표시하지 않는다.
2. COUNT 뒤 원 보유품 목록이 생기는지, 선택 전/후 수량 및 항목이 실제4ED1의 Inventory key·Q·mode·0/0에 반영되는지 확인한다. 정상 확정→원 즉시 close097B와 실제 backend/Inventory 결과를 별도로 기록한다.
3. 정상 다시 열기→`retrieve`4ED4→실제0971 issued entry/fullItemInfo→선택→4ED1의 entrykey·Q·mode를 확인한다. 개인 kind1/3 명명, 기존 UID 합침/새 UID/전체소진 갱신은 관측한 범위만 판정한다. 정상 Quit·저장·fresh readback과 원 finally/FIRSTclose까지 기록하며 첫 실패/AV/강제 정리는 그대로 보존한다.

이번 확인은 file-only decode·descriptor/required mask·다섯 선정 구간의 byte 재사용까지다. 게임/서버/포트/live attach/REA target lifecycle/제품 코드/큐/공용 API/git commit 변경0. PData 없는 vtable leaf의96B 문맥은 첫 RET까지의 명령만 기능 근거로 쓰며 뒤 이웃 코드를 같은 함수로 해석하지 않았다. 초기 `initialized_checks.json`은 잘못 고른 virtual50 cached-size getter를 보존한 조사 산출물이며 IsInitialized 근거로 쓰지 않았다. 정확 virtual20은 `required_presence.json`이다. close raw 파일 첫 literal-path miss와 올바른 파일명의 후속 대조도 `reuse_comparison.json`에 함께 보존했다.
