# PC 변신 외형 — SC_POLYMORPH_NOTI 4E5C 정적 계약

2026-10-26. **전용 서버 알림은 `SC_POLYMORPH_NOTI`, opcode `0x4E5C`다. `f1=Actor UID`, `f2=외형 key(sprite)`, `f3=자세 입력`을 기존 Actor에 적용하는 경로를 확인했다.** 자기 ActorNotify4E96 재송신도 새 외형 생성 경로에 도달하지만 기존 Actor를 퇴역하고 다시 생성한다. 연속 외형 갱신과 같은 동작으로 취급하지 않는다.

**주의: 4E5C f3를 정규화한 값이 0이면 기존 `ActionComponent+40`을 덮지 않는다. `f3=0`으로 맨손 복원을 완결한다는 주장은 불가하다.** 원 sprite·원 nonzero 자세 재적용은 정적 연결이며 실제 변신·해제 화면, 정식 패킷 PASS, 주문서 소비·서버 타이머·저장은 이번에 확인하지 않았다. 제품 STOPPED는 유지하며 게임·서버·포트·live attach·UI 입력·REA 전역 target 변경·제품 코드 수정·commit은 0이다.

## 고정 기준과 재사용

- 버전 `26.09.29.2001`, 상속 CONTROL SHA256 `9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`, CODE record `a49e798ded9ed540abb2c6848fdd678cb1a2a12fc3ec243f301f69348bfb4b24`다. 식별자는 [기존 정규화 계약](../../local_actor_state_translation/source-contract.json):3–6 및 run380 recovery metadata에서 재사용했다. 이번 전수 해시 검사0이다.
- 실제 입력은 기존 `C:/Users/Chansol/Documents/Codex/2026-09-07/d-lineage-classic/work/current_client_key_mapping/recovery.json`과 selector0 record다. [run390 seeds](../../local_server_rea_20261016/run390_polymorph_visual/seeds.json)에 경로·크기·상속 record hash를 남겼다. run380 `f2_research.py:View`/PData/Capstone 방식으로 파일만 읽었다. 새 guard·검사기·시험 suite를 만들지 않았다.
- **주소는 모두 복원 CONTROL RVA다.** [run380 f2_identity](../../local_server_rea_20261016/run380_map_transition_receive/f2_identity.json)의 `LC.guard.exe` disk 짧은 anchor 불일치를 보존한다. 이 결과는 현재 disk나 실행 프로세스와 같은 bytes/VA라는 증명이 아니다. REA 스킬의 관측·추론·미확정 분리를 적용했으며 새 native MCP session/Evidence ID는 없다.
- 먼저 [run385 무기 자세](WEAPON_STANCE_EVIDENCE.md), [Actor3/4 계약](../../online_actor_template_source/README.md), `local_actor_state_translation`, [run380 같은 UID 수명](MAP_TRANSITION_EVIDENCE.md), 기존 REA HANDOFF·shared-api를 검색했다. 별도 변신 wire/해제 완결 계약은 이 검색에서 발견하지 못했다. 원문은 보존했다.

이번 새 원문은 [source-excerpts.txt](../../local_server_rea_20261016/run390_polymorph_visual/source-excerpts.txt)다. 아래 **발췌L**은 이 파일의 실제 줄이며 RVA와 작은 명령 bytes, 부모 JSON 이름이 함께 있다. 전체 선택 함수는 같은 [run390 폴더](../../local_server_rea_20261016/run390_polymorph_visual/)의 JSON에 있다. 정적 연결은 원 함수 실행 관측과 구별한다.

## wire와 기본값

raw proto vptr `11E4668` → COL`13078A0` → TD`1681318`은 원문 `.?AVSC_POLYMORPH_NOTI@LIN@@`다. virtual40 getter`74C850`→compiled descriptor`15FBB60`, field record offset`B4`,7필드다. [schema.json](../../local_server_rea_20261016/run390_polymorph_visual/schema.json):2–115. parser object 안에 raw proto가 **+8**에 들어 있으므로 handler offset과 혼동하지 않는다.

| field | wire/type | required | raw offset / handler wrapper | 초기·Clear 기본값 | 정적 의미·사용 |
|---|---|---|---|---|---|
| f1 | signed int32 varint, wire0; zigzag 아님 | 예 | `20 / 28` |0(누락 유효값 아님) | `51102 movsxd`→signed64 UID; `627B0`의 actor slot8 UID 비교 |
| f2 | signed int32 varint, wire0 | 예 | `24 / 2C` |0(누락 유효값 아님) | 외형 key→Action+38 선기록; queued action Start에서+3C 현재 lookup key 갱신 |
| f3 | signed int32 varint, wire0 | 예 | `28 / 30` |0(누락 유효값 아님) | `B40EE0` 정규화→Context+3C→D+34→**nonzero일 때만**Action+40 |
| f4 | length-delimited 8-bit 문자열 저장, wire2; 선언상 string/bytes 구분·UTF-8 검증 UNKNOWN | 아니오 | `18 / 20` | empty 문자열 저장, absent | hasbit0 조건으로 문자열 가공·Actor 조회·`42EC0` component+40 갱신/`621F0` 호출. 공식 field 이름 UNKNOWN |
| f5 | signed int32 varint, wire0 | 아니오 | `2C / 34` |0, absent | handler가 local copy하지만 `55370`에 전달하지 않음; 의미 UNKNOWN |
| f6 | signed int32 varint, wire0 | 아니오 | `30 / 38` |0, absent | 위와 같음; 의미 UNKNOWN |
| f7 | signed int32 varint, wire0 | 아니오 | `34 / 3C` |0, absent | 위와 같음; 의미 UNKNOWN |

required 판정은 descriptor만으로 정하지 않았다. `74CBA0`은 `~hasbits &0E ==0`을 반환하므로 bits1/2/3, 즉f1/2/3가 필수다(발췌L97). new`6FE770`은 hasbits와 scalar6개를0으로 만들고 empty 문자열 포인터를 넣는다. Clear`74C800`도 scalar6개를0·hasbits0으로 되돌린다(발췌L104–123; 전체 receive.json). `74C990`의 여섯 `movsxd`와 serializer`74C860`/`1023F0`의 signed-extension→7-bit varint를 대조했다. 예를 들어 음수int32는 sign-extended varint이며 sint32 zigzag로 바꾸지 않는다(발췌L125–145, scalar_size.json).

실제 parser도 `2C4345→DEFFF0`가 Clear 후 mode1로`DEF620`을 부르고, compiled parser virtual40 다음`DEFAF0`가 virtual20(required check)을 부른다(발췌L58–102). **실패가 무조건 게시 차단이라는 뜻은 아니다.** `2C434A`의 false는 오류 로그 경로 뒤 정리로 합류하고, constructor/publisher는 이어서 event를 호출한다. handler51060은 f1/2/3의 개별 presence를 재검사하지 않고 기본화된 copy를 읽는다. 정상 wire 후보에는 required3개를 모두 명시해야 하며 이 오류 경로를 누락 허용 근거로 삼지 않는다.

## dispatch → actor → 실제 외형·자세 소비

1. **opcode 등록:** `294C8D lea factory11A9358`, `294C94 mov edx,4E5C`, `294CAC→292F80`. factory+10의 VA64 cell`11A9368`은 publisher`305BE0`다(factory_pointers.json, factory_registry.json, 발췌L4–12). 이름만 보고 opcode를 추정하지 않았다.
2. **decode·publish·subscriber:** `305C54→31DBB0`는 parser vptr`11A4D68`, embedded proto`11E4668`을 설치하고`31DC2E→2C4300`으로 수신 body를 파싱한다. `305C81`은 event`17FC7C0`, `305C88→2770B0`. `5FD54`는 handler`51060`을 R8에, 동일 event를RCX에 놓아`55AC0`으로 등록한다(발췌L14–63,L147–151). 등록/게시가 실제 runtime에 관측됐다는 뜻은 아니다.
3. **UID와 기존 Actor:** `51102`의 f1 signed64→R15, `51109` f2→R12D, `51111` f3→R13D. `51330→627B0`로 기존 Actor를 찾고`3ED20`(RTTI ActionComponent) 결과가 있으면`51350 [Action+38]=f2`다. `513B8–513C1`은 `(UID,f2,f3)`로`55370`을 부른다(발췌L153–185). `627B0`은 ActorSubsystem의`8A8/8B0`, `8C0/8C8`, `8D8/8E0`의 shared-pair 목록을 순서대로 순회하며 virtual8 UID를 비교한다. 자기 UID 전용 예외·ownUID 비교가 이 경로에는 없고 같은 lookup/update를 쓴다. 부재 actor를 새로 만드는 경로는 아니다(update_dispatch.json#/functions/4).
4. **외형+자세 action 준비:** `55370`은 같은UID를 다시 조회하고 ActionComponent/TransformComponent를 얻는다. `55417`이 Transform+88을 읽어 Context+28에 보존하고, `55442`는 Context+38=f2, `55449→B40EE0`, `5544E`는 Context+3C=normalized(f3)다. `5546A→977F0(Action,mode1,ContextCopy)`가 DefaultAction을 만들어 queue에 넣는다(발췌L187–223). context를 새 외형이라고 뭉뚱그려 현재 방향/동작 등 기존값을 누락하지 않는다.
5. **queue와 action Start:** `98170`의 action virtual30=`907F0`은 Context+38/+3C를 D+30/+34에 복사한다(`90877–90880`). `9817E→9C010` queue 소유권 이전 뒤 DefaultAction Start`92D10→8F9A0`에서 실제 적용한다(발췌L305–351). `8F9C2`는 D+30이-1이 아니면`96FA0`으로 Action+3C를 바꾸고, 이 함수는 key가 바뀔 때 기존+58 resource state를 정리한 뒤+908 SPR metadata lookup을 갱신한다. **f2는 수신 즉시 픽셀 교체가 아니라 queued Start 경로다.**
6. **현재 외형에서 실제 entry 조회:** `8FA12`가 Action+3C로 metadata를 찾고, `8FA6D/8FA70`가 D+10/action ID·D+14/variant를`348C80`에 전달한다(발췌L353–396). 이후 entry 단계와 `98F60` resource/group cache·`35B190` 로딩 연결은 기존 run385 source-excerpts:L208–238,L431–506을 재사용한다. 실행 렌더·자원 로딩 성공은 UNKNOWN이다.
7. **Interaction 후처리:** `554ED→586E0`의 InteractionComponent가 있으면 새 f2 metadata`34A160` 결과+5C를 Interaction+80에 넣고`B8980/B8C60`을 부른다(발췌L225–243). 이 값의 공식 의미와 두 후처리의 전체 부작용은 UNKNOWN이다. action만 바꾸는 임의 함수 호출로 이 경로를 생략하지 않는다.

### 자세0과 해제의 정확한 한계

`8F9D3 mov ecx,[D+34] →8F9D6 test ecx,ecx →8F9D8 je8F9E1`; nonzero만`8F9DE [Action+40]=ECX`다(발췌L347–351). 따라서4E5C의f3=0·1·2·3 또는 B40EE0에서0이 되는 값은 **이 store에서 기존 자세를 유지**한다. 기존 ActorNotify4E96 일반 초기화의`973AA [Action+40]=EAX`와 다르다. 외형 변경 때f3가 같은 자세의 재전달·유지·제한을 뜻하는 공식 서버 정책까지 확정한 것은 아니다.

mode1 DefaultAction의 D+10은`9783F`에서 읽은 **종전 Action+40**으로 초기화되고,`980AE–980BB`에서 종전 외형 첫 entry+종전 자세로 정해질 수 있다. Context의 새 f2/f3는 이후 D+30/+34로 들어간다. 현재 action ID와 후속 A+40 state를 같은 숫자로 단순화하면 안 된다. 바뀐 외형에 해당 entry가 없을 때의 최종 화면·fallback, busy queue 지연·attack 중단과 입력 복구는 이번 미확인이다.

| 해제 질문 | 판정 |
|---|---|
| 원 sprite·원 nonzero 자세를 같은 4E5C로 재적용 | 동일 UID lookup→동일 action override 경로의 **정적 연결 확인**. 별도 cancel-bit가 필요하다는 증거는 없음. 공식 해제 packet 순서·실행 성공은 UNKNOWN |
| 원 자세 0(기본/맨손)으로 완전 복원 | 위 0-store skip 때문에 **UNKNOWN**. f3=0만으로 기존 A+40을 0으로 만드는 경로를 입증하지 못함 |
| f2=0 또는 -1을 ‘변신 해제’ sentinel로 사용 | 근거 없음. 0은 실제 appearance key일 수 있고, -1은 `8F9C5/8F9C8`의 D+30 override skip 값이다. 원 class/sprite 복원값으로 임의 사용 금지 |
| 시간 만료·주문서 소모·비용·장비해제·저장복원 | 서버 계약은 이번 미분석/UNKNOWN. 별도 typed effect/timer나 지속시간을4E5C f5..7에 추정 배정하지 않음 |

## ActorNotify4E96 재전송과 L1J 구분

기존 ActorNotify4E96의 f3/f4는 각각 외형/자세 초기화 입력이며, 같은 UID여도 `60BA9→61650`으로 기존 Actor를 퇴역한 뒤 `60BB5→45550` factory와 `60C1E→66C80`로 새 Pair를 게시한다(발췌L398–417; run380 flow_camera_callback.json). 자기이면 MyPlayer의 Camera 통지까지 별도 새 객체 계보다. **외형만 바꿀 때 4E96 재송신을 ‘현재 Actor 보존 갱신’으로 채택하지 않는다.** 선택·입력·효과·current 수명 동등성이 미확인이다. 새 정상 spawn의 완전한 필드를 보존해야 하며 f3만의 축약 body로 보내는 계약도 아니다.

L1J 참조는 `D:/SingleLineageRef/l1j-en-classic/src/l1j/server/server/`의 구세대 코드다. `serverpackets/S_ChangeShape.java:37–42`는 opcode byte+objId dword+polyId word+`weaponTakeoff?0:29` word이며, 그 29를 현재 f3나 무기 자세로 이식하지 않는다. `model/L1PolyMorph.java:277–289`의 undoPoly는 classId로 S_ChangeShape를 보내고 무기가 있으면 `S_CharVisualUpdate`를 추가한다. 후자는 `serverpackets/S_CharVisualUpdate.java:30–32`에서 UID와 currentWeapon byte를 보낸다. **구세대 설계 참고**이며 현재 4E5C에는 위 원본 descriptor·등록·consumer를 직접 근거로 쓴다. 구세대 opcode·field 폭·classId/sprite 대응과 추가 무기 packet 필요성을 현재판으로 확정하지 않았다.

## 미확정과 최소 화면 관측안

정상온라인 기록 후보는 `work/normal_online*`, `online_public_session*`, `online_intro*`, `online_world_packet_source`, `online_login_packet_source`의 md/json/jsonl/txt에서 정확한 `SC_POLYMORPH_NOTI`/`0x4E5C`/opcode20060을 검색했다. 양성 원packet을 발견하지 못했다. 전체 저장소·binary capture 부재 증명은 아니다. 공식f4..7의이름·값·presence, 자기·타인 정상패킷과 해제 wire는 UNKNOWN이다.

후속 사용자 화면 시험은 **설계만** 남긴다. 기존 정상 로그인→자기 Actor가 있는 owned non-input 시험 경로에서, 유효성이 이미 확인된 다른 sprite 하나와 현재 nonzero 자세로 `4E5C {f1:현재UID,f2:선정sprite,f3:자세}`를 보내고 정지/이동/공격 한 번씩 본다. 같은 UID·Actor 객체/Pair 유지, Action+38/+3C/+40, 표시·입력·자원 정리를 확인한 뒤 원 sprite·원 nonzero 자세를 같은 알림으로 재적용한다. f3=0 복원은 별도 UNKNOWN 사례로 기록하며, 필요하면 기존 정상 무기 해제 경로가 0을 실제 기록하는지 최소 관측한다. 임의 packet·forced ready·강제 상태로 성공을 만들지 않는다. 이번 실행은 0이다.

현재 판정은 **원문 확인 + dispatch/consumer 정적 연결 확인**이다. 사용자 화면·실동작·전체원본동등성·변신해제완료 PASS는 없다. 쓰기는 run390 산출물과 이 문서뿐이며 기존제품·다른run·저장·실패원문을 보존했다.
