# SelfInfo 능력치·AC·성향·보너스 배분 필드

2026-10-26 · run395 · **실행 없는 CONTROL 복원 코드 정적 분석**. 서버 제품 코드·저장·원본 바이너리 수정, 게임·서버·포트 실행, commit 없음.

**장비·레벨·성향 표시의 확인된 입력은 4E38의 전체 상태 교체다. 변경 필드만 담은 partial 4E38은 정상 parser의 필수 검사에 실패한다.** 여기서 전체란 26필드를 모두 보내라는 뜻이 아니라 **required 18개와 보존할 optional 값**을 함께 보내라는 뜻이다. 필드 미전송을 기존 값 유지로 사용하지 않는다. 보너스 능력치 배분 창에는 별도 **4F0F(남은 점수) → 사용자 선택 4F10** 경로가 있다. 능력치의 별도 delta opcode가 클라이언트 전체에 없다는 결론은 내리지 않았다.

## 기준과 재사용 범위

기준은 고정 CONTROL SHA256 `9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`, `C:/Users/Chansol/Documents/Codex/2026-09-07/d-lineage-classic/work/current_client_key_mapping/recovery.json`의 저장 section 기록이다. 주소는 복원 CONTROL의 RVA다. 현재 디스크의 packed `LC.guard.exe` 파일 오프셋·현재 메모리 주소가 아니다. 기존 run380의 `f2_identity.json`은 네 개 창에서 packed 디스크와 복원 바이트가 다름을 기록한다. 그 기록을 재사용했으며 이번에 현재 디스크 전체 동일성·현재 실행 버전을 검증하지 않았다.

기존 `tools/local_self_info_profile/source.py`, `model.py`, `work/online_world_packet_source/`의 schema·binding·receiver, run383 EXP 근거를 출발점으로 사용했다. run325는 당시 선정 자료에서 world STR/DEX 연결을 닫지 못한 결과다. 이번에는 이후 존재하던 world UI reader를 원 writer와 직접 대조했으며, roster INFO 번호를 world 필드로 전용하지 않았다.

신규 원문: [selected-disassembly.txt](../../local_server_rea_20261016/run395_selfinfo_stats_fields/selected-disassembly.txt), 구조화 결과·명칭 literal/enum: [selected-source.json](../../local_server_rea_20261016/run395_selfinfo_stats_fields/selected-source.json). 추출은 기존 run380의 section/PData/Capstone 방식이며 공유 REA target/session을 변경하지 않았다. PData owner가 없는 leaf는128바이트 고정 창을 사용하므로 `FUNCTION` 표제가 항상 실제 함수 끝을 뜻하지 않는다(예:B41AD0의 실제 return은B41AED). 결론은 인용한 RVA 명령에 한정한다. 새 guard·검증기는 만들지 않았다.

## decoder → receiver → CharacterData

기존 binding은 `factory 11AB0F8 → publisher 307170 → event 17FBC80 → CharacterDataSubsystem 113540`이다(`work/online_world_packet_source/self-info-4e38-binding.json:3–9`). handler는 payload wrapper의 proto를 `10DC20`으로 복사하고, `RDI = subsystem+6D8`를 원 `ActorStatusInfo`로 사용한다. 아래 `info+`는 이 RDI 기준이다. 보호 정수는 논리값 하나를 세 dword에 저장한다. 그 내부 표현을 일반 int32 메모리 한 칸으로 대체하지 않는다.

schema는 `world-notify-contract.json:6–278`의 parse method75F400/schema15EE848이다. presence 위치는 proto+10 dword의 **0부터 시작하는 bit**다(기존 descriptor의128을 뺀 값). f19는 repeated라 singular Has bit가 없다.

| f | wire 타입 | 필수 / bit | proto+ | info+ / subsystem+ | 확인된 의미 |
|---|---|---|---|---|---|
| 1 | u64, wire0 | required /0 |28|00 /6D8|자기 ActorUID|
| 2 | i32, wire0 | required /2 |38|08 /6E0|레벨|
| 3 | i64, wire0 | optional /1 |30|이번 handler의 사용 미확인|누적 EXP로 명명하지 않음|
| 4 | i32, wire0 | required /3 |3C|30 /708|STR|
| 5 | i32, wire0 | required /4 |40|54 /72C|DEX|
| 6 | i32, wire0 | required /5 |44|3C /714|INT|
| 7 | i32, wire0 | required /6 |48|48 /720|WIS|
| 8 | i32, wire0 | required /7 |4C|60 /738|CON|
| 9 | i32, wire0 | required /8 |50|6C /744|CHA|
| 10,11 | i32, wire0 | required /9,10 |54,58|78,84 /750,75C|현재/최대 HP|
| 12,13 | i32, wire0 | required /11,12 |5C,60|90,9C /768,774|현재/최대 MP|
| 14 | i32, wire0 | required /13 |64|108 /7E0|**표시 AC의 부호 반전값**|
| 15 | i64, wire0 | required /14 |68|A8 /780|기존 달력 초 경로. handler에서는 하위32bit를 보호 정수로 투영|
| 16 | i32, wire0 | required /15 |70|B4 /78C|기존 Hungry|
| 17 | i32, wire0 | required /16 |74|C0 /798|기존 Weight. 이번 분석은 공식 무게 스케일을 확정하지 않음|
| 18 | i32, wire0 | required /17 |78|CC /7A4|성향(Alignment)|
| 19 | repeated32 scalar(card10A1), packing 미판정 | repeated |18|130 /808의 map|1부터 시작하는 key로 새 map 구성. 각 원소 업무 의미 미확정|
| 20 | i32, wire0 | required /18 |7C|D8 /7B0|업무 의미 미확정. bonus 점수로 명명하지 않음|
| 21,22,23 | i32, wire0 | optional /19,20,21 |80,84,88|E4,F0,FC /7BC,7C8,7D4|업무 의미 미확정. Has 체크는 아래 교체 계약 참조|
| 24 | i32, wire0 | optional /22 |8C|114 /7EC|업무 의미 미확정|
| 25 | i32, wire0 | optional /24 |98|120 /7F8|업무 의미 미확정|
| 26 | double, wire1 | optional /23 |90|18 /6F0|EXP 표시 퍼센트. run383 결과 재사용|

f4..9의 순서는 STR/DEX/**INT/WIS/CON/CHA**다. `world_stats.self_info_fields()`의 f4 STR/f5 DEX/f6 INT/f7 WIS/f8 CON/f9 CHA 대응은 원문과 일치한다. 서버 계산식·레벨별 증가량이 원본과 같다는 증거는 아니다.

원문 연결: proto 복사 `10DC9D..10DCC0`(원문5030행), f4/6/7/5/8/9 로드 `113617/113653/11368F/1136CB/113707/113743`(46–111행), 보호값의 info+30/3C/48/54/60/6C 쓰기 `113DE5..113E96`(476행부터). f18 로드11391B→info+CC 쓰기113F97(213,551행), f14 로드113A2C→info+108 쓰기11405A(272,581행). 이 순서는 명칭을 숫자 인접성으로 추정한 결과가 아니다.

## 원 UI의 실제 소비와 갱신

원 stat 화면의 `91C340`은 전달받은 info를 R13에 두고 각 **named widget**에 값을 쓴다. 명칭 literal은 구조화 결과의 `bonus_strings` 및 기존 `source.py:42–49`, 값 reader는 이번 원문에서 대조했다.

| 표시 | named widget | info reader RVA → 텍스트 setter |
|---|---|---|
| STR | Root.StatNum.StatNum_Str.Tx_Str |91D10A info+30 →91F990→BF9ED0|
| DEX | Root.StatNum.StatNum_Dex.Tx_Dex |91D2C8 info+54 →같은 경로|
| CON | Root.StatNum.StatNum_Con.Tx_Con |91D3ED info+60 →같은 경로|
| INT | Root.StatNum.StatNum_Int.Tx_Int |91D512 info+3C →같은 경로|
| WIS | Root.StatNum.StatNum_Wis.Tx_Wis |91D60E info+48 →같은 경로|
| CHA | Root.StatNum.StatNum_Cha.Tx_Cha |91D70A info+6C →같은 경로|
| AC | Root.StatNum.StatNum_ArmorClass.Tx_ArmorClass |91CC02→91A8B0(info+108)→3DA150→BF9ED0|
| 성향 | Root.StatNum.StatNum_Alignment.Tx_Alignment |91DA11 info+CC→91F990→BF9ED0, 이후 색·stage 소비|

원문 위치는 각각2195,2319,2396,2473,2538,2603,1849,2801행이다. `91F990`의 보호 정수 decode는 `mixed-base`이고, AC 전용 `91A8B0`는 **`base-mixed`**다(`5DCAA`7597행/`91A8F7`4428행). 따라서 표시 AC10→wire-10, 표시 AC-5→wire+5다. f14를 ‘항상 음수’라고 설명하면 틀린다. `world_stats`의 `14:-calculated.ac`는 이 표시 부호 관계와 일치한다.

수신 뒤 `114178..114183`은 subsystem+D8의 OnChangeStatus에 info를 전달한다(639행). stat layout의 원 생성 경로 `91A900`은 같은 subsystem+D8에서 `91C340` member를 연결한다(`91A98D..91A9BE`,7890행 부근). 초기화 `91B671..91B6CE`도 현재 subsystem+6D8을 복사해 같은 함수를 호출한다. 따라서 화면을 처음 열 때와 원 status 신호를 받을 때의 source 연결이 있다. **현재 실행의 살아 있는 layout/연결/텍스트·최종 픽셀 성공은 관측하지 않았다.**

성향은 숫자 외에도 `91DA46→1D0470` 색과 `91DB40/91DC07/91DCC4→B41AD0`의 stage 표시를 사용한다. **클라이언트 stage 경계는 음수→2, 0..500(500 포함)→1, 500 초과→3**다(`B41ADA`5658행). 색 경계도 `1D04A8 cmp500; jg`로 같다(5634행). 원 UI 분기는 stage2/3/1에 맞는 노드를 보인다. 현재 `world_alignment.display_stage()`의 L1J 채택 정책은 **500부터 lawful**이므로 정확히500에서 이 클라이언트 분류와 다르다. 정책 출처와 클라 관측을 구분하고 서버 코드는 이번에 바꾸지 않았다. 일반 월드 이름색 전체의 동일성으로 확대하지 않는다.

## partial / omission / reset 계약

1. 정상 `DEFFF0`는 parseflag1로 검증하며 `DEFB17..DEFB28`이 IsInitialized virtual+20을 호출한다. `760100..76010D`는 `(~has & 0x7FFFD)==0`을 요구한다(원문12794행). required는 **1,2,4..18,20, 총18개**다. AC나 STR/성향 하나만 있는 4E38은 정상 메시지로 성립하지 않는다. 개발용 partial-parse 플래그·handler 직접 호출을 정상 수신 계약으로 전용하지 않는다.
2. 새 parser 객체 `31E7B1..31E7D8`은 has와 scalar 영역을0으로 초기화한다(1197행). `10DC20`은 has와 scalar 블록을 복사한다. handler는 required 값과 f24/f25/f26을 무조건 새 상태로 만든다. **optional f26 누락은 EXP0, f24/f25 누락은 논리0으로 교체**된다. 과거 값 유지가 아니다.
3. f21..23에는 `113B2A..113C06`의 Has bit19/20/21 분기가 실제로 있다(324행). 그러나 그 앞 `113993..113A25`에서 세 임시 보호값을0으로 만들고, 분기 뒤 `113FDE..11404D`에서 새 값을 모두 저장한다. **Has=false도 기존값 보존이 아니라 새0을 저장**한다. 이 Has 분기만 보고 delta 계약으로 판단하면 안 된다.
4. f19는 이번 메시지의 repeated 목록으로 새 map을 구성한다(`113C65..113D7C`). 이후 기존 info+130 map을 지우고 교체한다(`1140C8..11415D`). 빈 목록은 기존 map 보존이 아니다. f3은 이번 선정 receiver에서 업무 사용을 확인하지 못했으며 값을 임의로 누적 EXP라고 명명하지 않는다.
5. 그러므로 장비 교체·버프·레벨업·성향 갱신은 **권위 있는 최신 full snapshot**의 필요한 값을 바꿔 기존 encoder로 보내는 경로가 source와 맞는다. identity/HP/MP/EXP/기타 상태를 임의0이나 오래된 snapshot으로 채우지 않는다. 미확정 optional을 단순히 추가하는 것도 원서버 정상값 증명이 아니다. **18필드 형식 충족과 화면 동등성은 별도**다.

별도 일반 능력치 delta opcode의 존재·부재는 이번 좁은 경로만으로 판정하지 않았다. 아래4F0F는 새 능력치 값 delta가 아니라 보너스 배분 잔여 점수다.

## 보너스 능력치 창: 4F0F → 4F10

**S2C 4F0F SC_BONUS_ATTR_NOTI**의 f1은 required i32/wire0, proto+18, has bit0, mask1이다. schema15EC760는 최대필드1·descriptor `[24,128,0,0x1091]`; parser76F1F0·IsInitialized76F320이 이를 확인한다. `295C05..295C24`가 factory11A8518을 opcode4F0F에 등록한다(12047행). factory+10의2FBDC0→318680이 proto를 파싱하고,2FBE61→event1801A40으로 게시한다. `10FDD8..10FDE9`가 같은 event에117060을 등록한다.

`1170CE`에서 wrapper+20의 f1을 받아 **subsystem+8E4에 수신한 남은 점수를 그대로 저장**한다(`117102`,8578–8590행). 값>0이고 현재 GameState==5일 때만(`11710E`,`117180`,8623행) `StatsLayout`을 취득/생성해 `LevelUpStatCommand` raw0과 int 점수를 virtual+A0에 전달한다(`1171AA..1173C3`,8633–8766행). `LevelUpStatLayout` vtable1214470의+A0는92BB00이다. 이 함수는 int를 layout+B8에 저장하고, >0이면+BC=1로 선택을 열며 UI 경로3ED100에 raw0을 전달한다(`92BB8E..92BBCD`,8469행부터). 창 열림/입력 성공은 정적 호출 관계이고 실제 화면 미실행이다.

원 `LevelUpStatLayout::AddStatClickFunc`는 named 자식과 enum을 다음처럼 연결한다. **4E38 필드번호와 다른 namespace**다. 문자열의 RIP load와 동일 분기에서의 R8 값을 직접 대조했다(`selected-source.json#/levelup_enum_name_loads`, `#/levelup_enum_mapping`).

| 선택 | 4F10.f1 enum | 이름 load RVA / enum 전달 RVA |
|---|---|---|
| STR / Strength |0|92B231 /92B259|
| INT / Intelligence |1|92B582 /92B659|
| WIS / Wisdom |2|92B6DA /92B7AF|
| DEX / Dexterity |3|92B2DB /92B3B3|
| CON / Constitution |4|92B42F /92B506|
| CHA / Charisma |5|92B82B /92B8F7|

사용자 클릭 callback92C120은 +BC가true일 때 이를false로 잠그고, 선택 enum을 **C2S4F10 CS_RAISE_ATTR_REQ.f1**에 담아27D620으로 보낸다(`92C149..92C1AF`,7451행). schema15EC708/max필드1/descriptor`[24,128,0,0x1091]`이며 f1 required i32/wire0,mask1이다. 송신 호출 뒤 로컬 잔여+B8을1 줄이고,0이하면3ED100에 raw1로 닫는 경로를 보낸다(`92C1EC..92C226`,7473행부터). 이 로컬 감소는 서버의 저장·능력치 적용·성공 ACK 증거가 아니다. **능력치 표시의 확인된 값 반영은 앞의4E38**이다. 서버가 실제 승인/배분 후4E38과 잔여4F0F를 어떤 순서로 보내는지는 미관측이다.

보너스 점수는 이 수신 경로에서 서버가 보낸 값이다. 이번 코드에는 이를 level-50·f20·f21..25로 계산하는 접점이 없으며, 그 필드를 임의 명명하지 않았다. 다른 능력치 초기화/재분배 기능은 별도 범위다.

## 남은 확인과 사용자 화면 실험안

- 이번 결과는 decoder/type·writer·named UI 소비·status 신호·보너스 창 요청의 **정적 연결**이다. 실제 게임·패킷·화면 PASS, 원서버 공식 수치/공식 증가량/보너스 지급 레벨·저장 규칙은 아니다.
- 다음 허용된 정상 로그인→캐릭터 선택→월드 진입에서 stat 창을 연 채 실제 장비 교체를 한 번 수행해 full4E38의 f14/영향 능력치와 화면을 함께 비교한다. 표시AC10→wire-10 및 음수AC 장비의 반대 부호를 구분한다. 같은레벨 재통지와 실제 레벨업은 기존 run383의 캐시/연출 조건을 재사용한다.
- 성향은 시험 저장 사본의 권위 상태를 보존해 full4E38의 -1/0/500/501을 비교하면 정확 경계를 분리할 수 있다. 이 수치 주입은 개발용 화면 실험으로 구분한다. 현재 제품의 실 kill·저장·재접속 확인과 합산하지 않는다.
- 보너스 창은 원조건이 충족된 시험 사본에서4F0F의 양수 잔여→실제 한 능력 선택→4F10의 enum→정상 서버 반영/저장→다음4E38·4F0F→화면·잔여·재접속을 관측한다. 선택 전 최종 요청을 미리 보내거나 client-local remaining 감소를 서버 성공으로 대신하지 않는다.

실행 소유는 이번에 취득하지 않았다. 제품 STOPPED의 다른 범위·원본·원로그·실패·저장/UID 보존 경계는 유지한다.
