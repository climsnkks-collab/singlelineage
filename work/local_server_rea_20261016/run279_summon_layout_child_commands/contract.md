# REA279 SummonLayout 버튼·패킷 계약

source-only / UNRUN / test_ready:false. 기존270·274·277의4F13 요청/4F14 응답과 child required mask0x22F를 재사용한다. 화면 버튼 좌표는 이 계약이나 직접 패킷 시험의 입력이 아니다.

SummonedMonsterStatusLayout(TD16930F8)→COL13620B0→vptr1235920, factory54E0D0(240B instance), 같은 instance v8 B20280/v10 143370 및 실제8개 widget callable 전달을 확인했다. B38B00의 이름→이 factory/current instance 선택·현재 event 설치는 별도 미공급이다. 정적 연결을 실제 열린 UI로 보고하지 않는다.

다섯 버튼은 원 invoke→Minion54C460→27D620으로 **CS_PET_COMMAND_REQ, C2S0x4F02**를 만든다. opcode는54C4DE의 실제 즉치다.

| 버튼 | f1 명령 값 |
|---|---:|
| AttackStance / 공격 태세 |2|
| DefendStance / 방어 태세 |3|
| Rest / 휴식 |4|
| Spread / 산개 |7|
| Alert / 경계 |5|

| wire 필드 | 형식 | 이 producer의 값 |
|---|---|---|
| f1 | closed-enum i32,wire0 | 명령 값; required mask0x2 |
| f2 | repeated string,wire2 | 빈 목록으로 생성 |
| f3 | uint32,wire0 | Minion+198의 lowDWORD; schema상 optional이지만 이 builder는 항상 present |

B215D0은 ACK 상위f1을 layout+B8/Minion+198에 저장하고627B0에서 Actor UID로 소비한다. 다섯 invoke는 캡처 layout의 UID 대신 global Minion Pair의 현재 저장 값을 읽고 producer 반환까지 Pair를 유지한다. 이는 원4F13 요청UID echo·서버 권위/current generation·실제 성공 관측이 아니다. 임의 UID/0 채움 payload를 만들지 않는다.

Targeting은54C380→15FA80 model→1689D0 UI command4로 추가 선택에 넘긴다. 다음 실제 selected target/UID와 C2S는 미공급이다. Dismiss는resource0x1C5/config2/C12358E8→B9840/471950의 확인 경계까지이며, 확인 결과와 그 뒤 C2S는 미공급이다. mode6을 추정해 보내지 않는다. Bt_Close는B22460에서 raw layout.v70(DL0)로 tailcall하며 전체 close/무패킷은 미확정이다.

수신 child의 표시는 f3/f2→0x1642, f5/f4→0x1643 및 format `{}: {}/{}`다. pinned bank26.09.29.2001의 KR 라벨은 HP/MP이며 current/max 이름·공식 수치·활성 언어는 별도 미공급이다. child.f1=1..8은 공격 목표 지정·공격 태세·방어 태세·휴식·경계·수집·산개·해산 resource로 분기한다. child.f6은 필수 복제에 포함되나 선정 표시 body의 직접 scalar read는 없어 업무 의미는 미공급이다. 송신4F02.f1 mode와 수신4F14.f2 layoutkind/child.f1 표시 enum, UI command4/config2는 별개다.

main은 기존10개 bank ID 외0x2CF2(ID11506) 원문 KR `현재 상태: `, TW `目前狀態： `의 끝 공백을 그대로 추가 확인했다. 338FF0 resolver→이 bank/version/locale 결속은 미공급이며 문자열을 임의 정규화하지 않았다.

원본 서버의 same4F13→4F14 정상 record·실제 child 수치·4F02 응답/상태, 실제 window/current binding·UI owner thread·설치 해제/retirement·inflight drain은 미공급이다. raw capture·임시 clone/delete·정상 Pair release를 이 근거로 대체하지 않는다.

신규 CODE 물리8691B/고유8675B/선정8486B·2238행, PData696B, 고정 DATA 물리965B(기존 inline32B 포함997B), exact native query20. main이21개 CODE와 명령 DATA22구간의 원바이트 SHA를 대조했다. 네 하위 source 묶음12파일은 RELEASED 그대로 보존하고 이 root3만 결합했다. 실제 패킷/UI/game/runtime·제품/shared/ACTIVE/Test/포트저장/Pro/큐 변경0. 정상 세션·실 UID/앞 응답·상태를 쓰는 시나리오/caller/RUN_COMMAND는 구현 main 소유이며 다른 ready 시험의 gate가 아니다.
