# 맵 전환·같은 맵 순간이동 패킷 근거

2026-10-26. **원본의 완전한 전송 순서와 4E95.f2 정상값은 기존 자료만으로 확정되지 않았다.** 확정된 것은 메시지 형식·일부 소비 순서·자기 UID 조건이다. L1J는 같은 맵에서도 MapID와 자기 Actor를 다시 보내지만, 이를 클래식의 wire 계약으로 옮길 근거는 없다. 따라서 현재 broker의 던전 전환 보류와 같은 맵 Restart→재선택 대체를 해제할 근거는 아직 부족하다.

이번 요청의 근거 정리만 수행했다. 제품·저장·큐·기존 근거를 수정하지 않았고 게임·서버·L1J·새 REA를 실행하지 않았다. 아래 `확정`은 원문/현 코드 확인을 뜻하며 화면·입력 동작 PASS를 뜻하지 않는다. 기존 자료의 기준은 클래식 26.09.29.2001, retained CONTROL `9ffc24fe…b7af`다. run273의 4F3650은 frozen104 CODE와 복원 PData의 선정 근거이며 현재 실행 전체의 동일성을 새로 입증한 것이 아니다.

## 1. 재사용한 근거와 판정

| 근거 | 확인한 범위 | 남은 한계 |
| --- | --- | --- |
| [run273 수신 계약](../../local_server_rea_20261016/run273_map_transition_contract/source/receive/contract.md):3–13 및 [선정 원문](../../local_server_rea_20261016/run273_map_transition_contract/source/receive/selected-evidence.json)의 `/consumer_contract`, `/first_unknowns` | 4E95→typed event→Map receiver, Actor 정리/보존, map alias, changed-map dispatcher | 서버의 f2 생산자·정상값, 실제 전환 순서·current Player 완료 미공급 |
| [run273 전체 계약](../../local_server_rea_20261016/run273_map_transition_contract/source/contract.md):3–15 | 일반 dialog→조건부 HACTION4ED4와 수신 계약을 분리 | 특정 teleport NPC·목적지 row·action/cookie·요청과 응답의 인과 미확정 |
| [run287 계약](../../local_server_rea_20261016/run287_temple4_77_return_map0_contract/source/contract.md):3–15 | 선정 11파일의 Temple4/77→0 귀환 입력 결손 | TeleportBook destination4·EnterMap destination0 후보만으로 귀환 경로를 만들 수 없음. region literal map77은 오렌 상아탑 3층이며 namespace 동일성 미확정 |
| [월드 계약](../../online_world_packet_source/world-notify-contract.json)의 `/tables/2`, `/field_consumers`, `/ordering` 및 [설명](../../online_world_packet_source/README.md):7–27 | 4E95 필수성, SelfInfo/ActorNotify UID와 Player subtype 조건 | 전체 월드 초기화·전환 순서를 보장하지 않음 |
| [BOOK 비0맵 API](../shared-api/book-saved-map-world-source/API.md):9–27 및 [원문 묶음](../shared-api/book-saved-map-world-source/original-source/evidence.json)의 `/observed` 아래 `MAP_FIELD3_4`, `MAP_LIFETIME` 항목 | f1 raw/resolved 구별, f2 CharacterData 소비, f3/f4 환경 소비 | 비0맵의 authoritative producer와 f2/f3/f4 정상값 미공급 |
| [현재 broker](../../../tools/local_original_session/broker.py):442–477,578–602,4282–4288,4372–4415 | map0 선택 알림, 맵 전환 빈 응답, 같은 맵 Restart 대체 | 구현 존재와 원본 순간이동 성공은 별개 |
| [아이템 요구 계약](../../../tools/local_original_session/world_item_effects.py):126–134,196–198 | teleport wire UNKNOWN, 목적지만 제안 | 4E2C 보행·4EE0 보정을 teleport로 채택하지 않음 |
| [던전 자료](M3_DUNGEON_DATA.md):47–69, [번호 대응](MAPPING_SCOPE.md):3장 | 원본 정적 입구 목적지와 L1J 계단 후보를 분리 | 계단의 실제 클래식 trigger·요청/응답 관측은 없음 |

추가 검색은 shared-api API/HANDOFF, implementation 1–5·integration-1 관련 Markdown, consumables·manual/runs 기록과 현 소비 코드로 제한했다. 이 범위에서 같은 맵 원본 순간이동의 양성 런타임 기록을 추가로 찾지 못했다. 일부 임시 폴더는 접근이 거부됐으며 전체 저장소/게임에 해당 경로가 없다는 주장이 아니다.

## 2. 다른 맵으로 이동할 때: 확정 필드와 순서의 경계

### 4E95 MapNotify 값

형식의 기준은 `world-notify-contract.json#/tables/2`, 타입 해석은 [world codec](../../../tools/local_world_protocol/model.py):31–47이다. 필수 필드는 **값이 0/false라도 presence가 있어야 한다.** 파서 생성자의 0 초기화는 정상 서버값을 입증하지 않는다.

현재 S2C frame은 `u16LE(payload길이+6) + u16LE(opcode) + protobuf payload + trailer 2B`다(`broker._frames_for():473–477`의 로컬 trailer는 `00 00`). 기존 encoder/writer를 사용하며 아래 UNKNOWN 자리를 임의 0으로 채운 프레임을 확정안으로 만들지 않는다.

| 필드 | 타입·필수성 / raw Proto offset | 실제 소비·전송값 판정 |
| --- | --- | --- |
| f1 | int32, 필수 / +0x38 | Map+0x71C에 raw ID 저장 → 선택적 alias `3DA970` → resolved Map+0x718·tile header. 목적지 map의 **wire raw ID**가 필요하다. 현재 map0 baseline은 0. 저장 map_id와 raw f1의 일반적 동일성·비0맵 alias 공급은 미입증이므로 목적지 map1이라고 f1=1을 원본 확정값으로 선언하지 않는다. |
| f2 | int32, 필수 / +0x3C | `53266A`에서 CharacterData+0x568에 저장. 업무 의미·정상값 UNKNOWN. 두 번째 map ID·층수·수중 플래그·0 상수 어느 것으로도 확정할 수 없다. |
| f3 | bool, 필수 / +0x48 | 환경 event `5478F0`에서 WorldEnvironment+0x88 소비. 정확한 게임 의미·정상 목적지 값 UNKNOWN. |
| f4 | bool, 필수 / +0x49 | 같은 환경 event에서 WorldEnvironment+0x38 소비. 정확한 게임 의미·정상 목적지 값 UNKNOWN. |
| f5, f6 | uint32, 선택 / +0x40,+0x44 | 정상 전환 시 존재 여부·값·업무 의미 UNKNOWN. |
| f7, f8 | message / repeated message, 선택 / +0x30,+0x18 | nested schema와 전환 시 필요성 미확정. 현재 scalar codec의 지원 범위 밖이다. |
| f9, f10 | bool, 선택 / +0x4A,+0x4B | 정상 전환 시 존재 여부·값·전체 효과 UNKNOWN. |

[baseline.json](../../../tools/local_native_login_map_notify_hook/baseline.json)은 `{1:0,2:0,3:false,4:false}`, `EXPLICIT_LOCAL_SOURCE_BASELINE`, `normal_server_values_proven=false`다. map0 최초 선택용 로컬 값이지 비0맵·다른 환경의 전환값을 공급하는 자료가 아니다. f3/f4를 이전 맵에서 그대로 복사하는 규칙도 입증되지 않았다.

### SelfInfo4E38·ActorNotify4E96 값

- SelfInfo.f1은 현재 플레이어의 u64 public Actor UID다. 자기 Actor 생성 시 ActorNotify.f2의 u32를 zero-extend한 값과 같아야 한다. UID를 임의 변경하거나 큰 u64를 잘라 맞추지 않는다. `455F4`에서 비교할 때 SelfInfo UID가 이미 소비돼 있어야 한다.
- ActorNotify.f1은 목적지 grid의 packed u32다. 기존 로컬 좌표 포장은 `word0=x`, `word1=y`, `(y << 16) | x`다([pack_grid](../../../tools/local_movement_authority/model.py):23–32). heading을 바꿀 때 현 broker는 Actor.f5에 반영한다. 원본 template/Player subtype 및 필수 필드 `1..24,27,28`도 충족해야 한다.
- SelfInfo에는 grid 필드가 없다. SelfInfo는 기존 current 상태·HP/MP·능력치에서 만들고, 이동 좌표를 임의 필드에 넣지 않는다. Actor의 나머지 필드도 기존 정상 캐릭터 자원·외형·stance·상태를 유지한다. UID 일치와 필수성만으로 자기 Actor/current lookup 복원 성공이 보장되지는 않는다.
- 매 전환마다 SelfInfo를 다시 보내야 하는지, 이미 설치된 self UID를 유지할 수 있는지는 미확정이다. `SelfInfo → 자기 Actor`는 **새 자기 Actor를 만드는 시점의 UID 선행 조건**이며 모든 teleport의 고정 프레임 목록은 아니다.

### 지금 확정할 수 있는 전송 관계

현재 최초 선택 구현은 `C2S 4E28 → S2C 4E29 → 4E95 → 4E38 → 4E96(자기) → 선정 주변 Actor`다. `broker.select()` 반환과 `_frames_for()`에서 확인되지만 이는 **선택/재선택의 로컬 구현 순서**다.

맵 전환에 대해 확정된 것은 다음 부분 관계다.

1. 4E95 receiver는 **맵 변경 여부 비교 전에** `63200`으로 Actor vector를 정리한다. Actor+0x10!=0 Pair는 보존/재삽입하므로 모든 Actor를 삭제한다고 단정하지 않는다.
2. 그 뒤 raw f1→alias→resolved map을 반영하고, changed-map이면 tile context 및 `4F3650`으로 이어진다. `4F36FD`의 node+0x58 callable.virtual10 실체·등록과 mapdata/currentPlayer 완료는 미공급이다.
3. 정리 이후 Actor를 새로 게시하는 설계라면 그 Actor 알림은 해당 정리 뒤에 있어야 한다. 자기 Actor를 새로 만들면 그보다 먼저 올바른 self UID가 설치돼 있어야 한다. 보존된 Actor에 대한 별도 갱신 방식은 여기서 확정되지 않는다.

따라서 **검증할 후보**는 `4E95(목적지의 실제 f1..4 및 필요한 optional) → [필요 시 4E38 current] → 4E96(자기 목적 좌표) → 목적지 시야 Actor`다. 이는 기존 소비 조건과 L1J에서 얻은 후보이며, 원본의 확정된 완전 순서/구현 가능한 값 세트가 아니다. 추가 effect·remove·환경·resource 알림의 유무, 동기화 요청 및 대기 시점도 UNKNOWN이다. 송신 drain이나 dispatcher RET를 map 준비 완료로 삼을 수 없다.

4E29는 최초 선택 ACK이며 맵 전환 ACK라는 근거가 없다. `03EB USER_START_DONE`도 map ACK가 아니다. 4ED4 f4/f5는 일반 HACTION producer의 추가 int32이며 목적지 x/y로 명명할 수 없다. NPC 대화와 보행 계단의 요청 producer도 구분한다(run273/run287).

## 3. 같은 맵 순간이동: 생략 가능한 프레임은 아직 확정되지 않음

**현재 원본 근거에는 같은 맵 순간이동의 확정 프레임 목록/순서가 없다.** 같은 맵이므로 4E95를 생략한다는 규칙도, 무조건 보낸다는 규칙도 확정하지 않는다.

| 방식 | 순서·효과 | 근거 수준 |
| --- | --- | --- |
| 현 Restart 대체 | 아이템 소비 응답 및 기존 Restart 흐름 → 현재 WORLD 이탈 → 캐릭터 재선택 → `4E29/4E95/4E38/4E96`로 재진입. 목적지는 `_world_relocations`에 보관하고 재선택/정리 때 저장 반영 | 현 코드 확인. `WORLD_ITEM_RESTART_SAME_MAP_FALLBACK_REQUIRED`로 같은 맵만 허용한다. 이 방식의 화면 성공이나 원본 제자리 teleport를 이번에 검증한 것은 아님 |
| MapNotify로 재게시하는 후보 | `4E95(같은 raw map, 실제 환경값) → [필요 시 4E38] → 4E96(목적 grid) → 새 시야 Actor` | L1J와 기존 consumer에서 얻는 실험 후보. 같은 resolved map이면 map-dependent 분기는 건너뛰어도 앞선 Actor 정리는 실행되므로 단순한 무효 알림이 아님 |
| MapNotify 없이 제자리 재배치 | 원본 relocation/effect 알림·자기/주변 Actor·입력 복구 순서 | producer/opcode/수명·순서 UNKNOWN. 미확정 opcode를 임의로 채울 수 없음 |

`4E2C`는 기존 Transform 기준 방향 상대 이동이다. 자기에게 보행 성공 ACK처럼 반사하면 추가 한 걸음/CS4E2B 재송신이 발생할 수 있다. `4EE0`는 required int32 f1=word0/f2=word1을 받는 **MovingBackAction 좌표 보정**이며 Start에서 current/target과 Navigation을 정리한다. 이 소비 사실만으로 teleport effect·camera·Actor 수명·시야 복원까지 입증되지 않는다([기존 이동/보정 근거](../../local_server_rea_20261016/self_response_findings.md):10–14,44–84). 보정으로 이동해 보이는 화면과 원본 순간이동을 구분한다.

## 4. L1J 대조: 디자인 참고이며 클래식 wire 매핑이 아님

이 절의 파일은 모두 읽기 전용 `D:/SingleLineageRef/l1j-en-classic/` 기준이다. 아래 `src/`는 `src/l1j/server/server/`다.

**같은 맵/다른 맵의 teleport 후 자기 클라이언트 전송은 공통이다.** `src/utils/Teleportation.java:98–116`에서 visible map 이동 → 위치/방향 적용 → **S_MapID → S_OwnCharPack → known objects 비우기 → teleport visual 복원 → updateObject의 주변 재인지 → S_CharVisualUpdate**다. 사이의 S_OtherCharPacks는 주변 사용자용 broadcast다. 같은 맵에서는 `L1World.java:172–180`의 visible map 컨테이너 이동만 생략되며 위 패킷 전송·known reset을 생략하는 분기는 없다.

| L1J 메시지/단계 | 원문 필드·순서 | 클래식에 대해 확정할 수 없는 것 |
| --- | --- | --- |
| S_MapID | `src/serverpackets/S_MapID.java:27–34`: `C opcode, H mapid, C underwater?1:0, C0,H0,C0,D0`. underwater는 목적지 `pc.getMap().isUnderwater()` | 클래식은 protobuf 필수 i32/i32/bool/bool이다. L1J의 두 번째 데이터 항목을 4E95.f2로 대응할 근거 없음. light 필드는 이 L1J MapID에 없음 |
| S_OwnCharPack | `src/serverpackets/S_OwnCharPack.java:62–103`: x/y, objectId, gfx, dead status 또는 weapon, heading, **ownLight**, moveSpeed, exp/lawful, name/title/status/clan/party HP 등 | 단일 옛 CharPack을 클래식 SelfInfo·ActorNotify 중 하나와 동일시할 수 없음. ownLight를 클래식 f2/f3/f4로 옮길 근거 없음 |
| S_Teleport | `src/serverpackets/S_Teleport.java:31–35`: `C opcode,C0,C0x40,D pcId`이며 map·좌표 없음 | 목적지 패킷이 아님. 대응 클래식 opcode/ACK 미확정 |
| 선행 효과·handshake | `src/model/L1Teleport.java:69–89`: S_Paralysis teleport unlock → 효과가 있으면 S_SkillSound와 예약 지연 → 목적지 저장 → 설정에 따라 S_Teleport 또는 즉시 Teleportation | 클래식에 같은 unlock·effect·196ms·C2S 확인 패킷이 있다는 증거 아님 |
| S_Teleport 사용 설정 | 보관 `config/server.properties:165`는 `SendPacketBeforeTeleport=True`; Config.java:739–740 기본값은 False. True 경로는 `src/clientpackets/C_Teleport.java:31–36` 수신 뒤 Teleportation 실행. 지연 효과도 `L1PcInstance.java:151–190`에서 같은 분기를 사용 | L1J 설정을 읽었다는 사실이며 실행 관측 아님. 클래식 03EB를 이 확인 패킷으로 대체할 수 없음 |
| known objects | `src/model/L1Character.java:592–595`의 서버 known 목록 clear → `L1PcInstance.java:3401–3418`의 미인지 object.onPerceive. clear 함수 자체는 개별 remove를 보내지 않음 | 클래식 Map receiver의 client Actor 정리와 서버 known 목록 clear는 서로 다른 수명 작업 |
| 보행 계단 | `src/clientpackets/C_MoveChar.java:100–117`은 다음 칸 적용 전 Dungeon/DungeonRandom 검사. `src/model/Dungeon.java:61–72,144–203`은 DB 출발칸→목적지로 L1Teleport(false) 호출 | 클래식 계단이 HACTION4ED4를 쓴다는 근거 아님. L1J SQL의 출발/도착칸은 로컬 정책 후보 |

기본 TELEPORT 효과는 SPR169, 기준280ms×0.7=196ms다(`L1Teleport.java:40–42,79`). 클래식 공속·이펙트·대기시간으로 채택하지 않는다. L1J opcode도 S_MAPID=73/S_CHARPACK=1/S_TELEPORT=11/C_TELEPORT=79이며 클래식 4E95/4E38/4E96과 byte 단위 호환되지 않는다(`src/encryptions/Opcodes.java:82,120,130,188`).

## 5. 미확정 입력과 사용자가 화면으로 확인할 최소 실험안

다음은 **후속 실험 설계이며 이번에는 실행하지 않았다.** 우선 원본 정상 동작 한 건에서 값을 얻고, 그 기록을 받은 뒤 로컬 후보를 한 번 실행하는 순서다. 화면만으로 f2나 패킷 presence를 판정하지 않는다.

| 단계 | 정상 동작·화면 확인 | 같은 operation에서 확보할 최소 데이터 |
| --- | --- | --- |
| A. 같은 맵 원본 1건 | map0의 안전한 위치에서 정상 귀환/순간이동 하나. 원거리 목적지로 바뀌며 선택 화면 없이 자기 캐릭터·지형·주변 객체가 표시되는지, 끝난 뒤 한 칸 걷기 입력이 되는지 확인 | 실제 아이템/메뉴 요청부터 첫 정상 후속 요청까지의 양방향 순서. 4E95 존재 여부와 모든 필드 presence/값, 4E38 재전송 여부, 자기 UID의 4E96·remove/effect·기타 알림, 전후 raw/resolved map·grid·current Player/Actor |
| B. 다른 맵 원본 1건 | 말하는 섬 던전 입구에서 정상 보행 입장. 층/지형·캐릭터가 바뀌고 중복/잔상/검은 화면 없이 한 칸 이동되는지 확인 | 요청 시작칸·방향·실제 도착칸, 4E95 f1..10의 존재/값과 4E38/4E96 앞뒤 순서, old Actor 보존/퇴역과 current 재수립, 실제 다음 C2S. 가상의 ACK를 선발송하지 않음 |
| C. 원본 역방향 1건 | 같은 입구로 정상 퇴장해 map0로 돌아옴. 지형/주변 객체·다음 입력 복원을 확인 | B와 동일한 짧은 기록. map0 초기 baseline과 **실제 map0 복귀값**을 비교해 f2/f3/f4 및 optional의 방향 의존성을 확인 |
| D. 확보한 기록의 로컬 적용 1건 | 같은 조건의 시험 저장 사본에서 정상 로그인→캐릭터 선택→월드 진입 후 A 또는 B 한 시나리오만 실행. 사용자는 제공된 화면으로 도착지·단일 자기 Actor·이동/선택/공격 입력과 시야 갱신을 확인 | 기존 broker writer/decoder/router와 관측 경로 사용. 전후 저장 위치·아이템 소비·UID/current·Actor 퇴역/새 시야를 같은 실행에 결속. drain·메모리·화면·후속 입력 결과를 각각 기록 |

기록은 기존 관측/패킷 경로를 재사용한다. 그 경로가 해당 수신 DTO·필드나 current를 제공하지 않으면 바로 그 항목을 UNKNOWN으로 남기며 새 수집기·guard·해시 검사·파일 판독 대기를 만들지 않는다. 포인터 주소는 과거 기록에서 재사용하지 않고 해당 실행의 기존 관측으로 확인한다. 화면 관측은 배경/캐릭터/입력 결과를 확인하는 것이며 `4F36FD` handler의 정체를 자동으로 입증하지 않는다.

입구의 **관측 위치 후보**는 L1J `0(32477,32851)→1(32669,32802),h4` 및 역방향 `1(32669,32802)→0(32477,32853),h4`다. 클래식 입구 목적지 자료 `0(32477,32853)`와 EnterMap 후보 `0(32478,32853)`를 출발 trigger로 바꿔 쓰지 않는다. 실제 원본 입력에서 다른 위치/목적지면 그 관측을 따른다. map1 f1·f2·환경값은 이 좌표표로 채울 수 없다.

후속 실험의 실행 담당은 기존 일회성 시험 worker 하나이며 게임/포트는 한 번에 하나, 로컬 시험은 owned non-input desktop/Job과 시험 저장 사본을 사용한다. 선정 Source를 FIRST/close까지 고정하고 기존 finally·정상 종료/강제 정리 및 실패/부분 저장 기록을 보존한다. 사용자 포커스·커서·전역 입력을 자동 조작하지 않는다. 정상 원본 조작은 사용자가 수행하고, 관측된 준비/전환 상태는 기존 메모리 관측으로 확인한다. 이번 문서 작성은 게임/서버 실행 권한이나 다른 동결 작업 재개로 확대되지 않는다.

실험을 구현 가능한 입력으로 바꾸기 위해 필요한 것은 **목적지 wire raw f1/alias, 같은 operation의 f2/f3/f4 및 optional presence, 원본 relocation/동기화 메시지의 순서, old/new Actor/current 및 다음 입력**이다. 이 입력이 없을 때는 재선택 순서나 L1J 값을 원본 정답으로 승격하지 않고 현재 보류를 유지한다. PositionStore의 같은 맵 계약과 기존 저장/수명 조건을 삭제하는 것은 이 결손의 해결이 아니다.

## 6. 이번 확인 결과

프로젝트 루트에서 고정 Python `C:\Users\Chansol\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`로 기존 순수 시험만 실행했다.

```text
python.exe -X utf8 -B -m tools.local_original_session.world_maps_tests
Ran 5 tests — OK, exit 0
python.exe -X utf8 -B -m tools.local_original_session.world_item_effects_tests
Ran 11 tests — OK, exit 0
```

5개는 계단 로컬 정책/실 지형 자료, 11개는 소모품의 목적지 제안·UNKNOWN 전송 계약 등을 확인한다. 새 시험/검증기를 만들지 않았고 임시폴더 권한 오류는 없었다. broker 시험·원본 맵 전환·같은 맵 제자리 teleport·Restart 대체의 화면/입력·저장 완료는 이번에 실행/검증하지 않았다. 현재 main의 기존 미커밋/미추적 변경은 그대로 두고 이 문서만 새로 작성했으며 commit하지 않았다.

## 7. run380 추가 수신 분석 결과 — 2026-10-26

**f2 저장까지의 분기, f9/f10의 실제 소비, 같은 UID 4E96의 교체 경로를 추가 확인했다. f2 정상 서버값과 원본의 완전한 전환 순서는 여전히 미확정이다.** 상세는 [run380 계약](../../local_server_rea_20261016/run380_map_transition_receive/source/contract.md), [선정 원문](../../local_server_rea_20261016/run380_map_transition_receive/source/selected-evidence.json), [원본 위치](../../local_server_rea_20261016/run380_map_transition_receive/source/source-refs.json)에 있다. 이 절은 위 1–6절의 과거 기록을 보존하면서 정적 확인 범위를 보완한다.

### f2와 추가 필드 소비

`53262C`는 f2를 EBX에 읽고 `53266A`는 **32비트 그대로 CharacterData+568에 저장**한다. 이 구간에는 f2의 0 검사·범위 검사·enum 분기·bool 변환이 없다. `53276B`에서 EBX는 old resolved map으로 덮이며, 맵 변경 비교 `532791`은 **resolved f1 ↔ 이전 Map+718**이다. 따라서 f2가 이 비교의 두 번째 map ID이거나 0/1 분기 flag라는 근거는 없다. 다른 CharacterData+568 reader/간접 callee의 의미까지 닫힌 것은 아니므로 f2가 무의미하다고 판단하지 않는다. 생성자 0과 로컬 baseline 0은 정상 서버값의 증거가 아니다.

| 필드 | 이번에 구체화한 소비 | 남은 미확정 |
| --- | --- | --- |
| f3 | presence bit5→`54793C` Environment+88→`547F10`; 렌더 설정 객체의 bool로 전달 | 수중/암흑 등 게임 이름·정상 목적지 값 |
| f4 | presence bit6→`54795F` Environment+38 | 게임 이름·정상값 |
| f9 | raw+4A→`53262F..532633` **Map+760**, 이 저장에는 presence 분기 없음 | flag 이름·후속 게임 효과·정상 presence/값 |
| f10 | presence bit8→`54796B..547973` **Environment+39**, absent이면 fallback literal | 이름·정상값, retained 원문이 가린 fallback 숫자 |
| f5/f6/f7/f8 | 기존 scalar/nested/repeated DTO 복사는 확인. 선정 Map/Environment receiver에서 f5/f6의 직접 사용은 확인되지 않음 | 다른 subscriber·nested schema·정상 presence와 효과. 미사용 필드라고 확정하지 않음 |

f1/f2/f3/f4 필수 presence는 그대로다. `Map+6E0`가 없으면 Actor 정리·f2/raw f1 저장은 실행한 뒤 resolved/map-dependent 작업을 건너뛴다. 같은 resolved map이면 map-dependent reset/MapChanged만 건너뛴다. receiver 반환은 준비 완료가 아니다.

### 프레임 순서·누락과 같은 맵 이동

- **다른 맵의 부분 순서:** 새로 게시할 Actor는 4E95의 Actor 정리 뒤, 새 자기 Player factory는 올바른 self UID 설치 뒤에 있어야 한다. `4E95 → [필요한 4E38] → 자기 4E96 → 주변 Actor`는 이 조건을 만족시키는 실험 후보이며 완전한 원본 순서가 아니다. 4F36FD의 실제 subscriber·mapdata/current/camera 완료는 아직 미공급이다.
- **4E95 생략:** 이 경로로 목적지 raw/resolved map·tile header가 설치되지 않는다. **4E38 생략:** cold/잘못된 UID면 `455F4` 비교가 불일치해 MyPlayer 대신 remote Player 분기로 간다. 이미 맞는 UID가 유지된다면 이 비교만으로 재전송을 강제하지는 않는다. **자기 4E96 생략:** 이전 자기 Actor가 정리된 경우 이 경로로 새 자기 Actor가 생기지 않는다. 특정 검은 화면·입력 실패의 실제 양상은 관측하지 않았다.
- **같은 UID 4E96의 추가 확인:** `60B50`은 기존 UID 일치 시 `60BA9→61650` 퇴역을 호출하고 반환 결과 검사 없이 `60BB5→45550` fresh factory로 이어진다. 새 Pair가 있으면 `60C1E→66C80`에 게시한다. 즉 **4E95 없이 같은 UID 자기 4E96를 받아 객체를 교체하는 정적 경로는 존재**한다. 제자리 필드 갱신·원자적 교체·current/selection 수명 연속·완전한 순간이동 성공을 뜻하지 않는다. 기존 [run185](../../local_server_rea_20261016/run185_ground_spawn_duplicate_quantity/worker/findings.md)의 일반 factory 이전 분기를 재사용했다.
- **같은 맵 4E95도 무효 통지가 아니다:** map 비교 전 Actor 정리는 여전히 실행된다. 재전송이 반드시 필요하다는 증명과 생략해도 된다는 증명 모두 아직 없다.
- **위치만 바꾸는 별도 프레임:** 4EE0는 required int32 f1=word0/f2=word1이며 기존 MyPlayer의 MovingBackAction→`95544→C0E90`을 통해 Transform 현재+38/목표+60을 함께 바꾸고 Navigation을 중단한다. Actor 부재 시 적용되지 않고 queue/busy에 따라 지연될 수 있다. 이 보정 경로를 teleport 효과·시야/camera·입력 복구 전체로 확대하지 않는다.

### 최소 후속 실험 3개와 실행 한계

1. **정상 원본 같은 맵 이동 1건:** 안전한 map0에서 귀환/순간이동하고 사용자가 도착·자기 Actor 하나·주변 갱신·다음 한 칸 이동을 확인한다. 같은 operation의 기존 관측으로 4E95/4E38 유무, f1..10 presence/값, 4E96/4EE0/효과·remove 순서를 확보한다.
2. **정상 원본 던전 왕복 1회:** 실제 입구로 입장·퇴장하고 양방향 화면/다음 이동과 각 전환의 짧은 패킷·map/grid/current 기록을 묶는다. map0 복귀 f2와 로컬 초기 baseline을 비교하되 두 값의 일치를 모든 맵 상수로 일반화하지 않는다.
3. **확보한 같은 맵 기록의 로컬 기준/생략 비교:** 후속 시험 담당이 정상 기록 적용 기준 1회를 먼저 성공시킨 뒤 **4E95만 생략**한 비교 1회에서 같은 UID 자기 4E96의 current/selection·배경·주변 잔상·다음 입력을 확인한다. 기준이 실패하면 첫 실패에서 멈춘다. 이번에는 서버/호출부를 만들거나 수정하지 않았다.

화면만으로 f2·wire 순서를 확정할 수 없다. 기존 관측에서 값이 나오지 않으면 UNKNOWN으로 남긴다. f2를 임의 0/1로 바꾸어 화면이 나온다는 사실도 정상 서버값의 근거가 아니다. 위 실험은 설계만 했고 실행하지 않았다.

지정 deps의 `from capstone import Cs, CS_ARCH_X86, CS_MODE_64`는 `ImportError: cannot import name 'Cs' from 'capstone' (unknown location)`, 해당 `capstone/__init__.py` 접근은 **PermissionError [WinError 5]**였다. 사용자 지시대로 기존 정적 JSON으로만 진행했다. REA 스킬을 적용했고 `binary_session({})`에서 열린 대상이 없음을 확인했으며 새 대상을 열지 않았다. 이번에는 전체 바이너리 동일성·현재 실행 주소를 새로 확인하지 않았다.

실행 명령: 프로젝트 루트에서 `"C:\Users\Chansol\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -X utf8 -B work/local_server_rea_20261016/run380_map_transition_receive/research.py` — **exit 0, 기존 원문 658행 선정**, 생성 JSON 재파싱·핵심 주소 확인. 이는 분석 산출물 생성 확인이며 게임/패킷 시험 PASS가 아니다. 새 검사기·해시 검사·native decode·게임/서버/broker 시험·서버 코드 수정·커밋은 0이다. 위 6절의 5+11개 시험은 과거 실행 기록이며 이번에 재실행하지 않았다.


## 8. 전체 권한 Capstone 후속 결과 — 2026-10-26

**새로 확정한 것은 f3의 수중 후처리, f10 absent 기본값 0, MapChanged의 직접 소비자 2건, 자기 4E96의 Camera 재통지다. f2의 후속 소비자·정상 서버값과 원본의 완전한 wire 순서는 이번 정적 추적 후에도 미확정이다.** 이 절이 7절의 도구 접근 실패와 그때 미연결이었던 경계를 보완한다. 과거 원문·실패 기록은 수정하지 않았다.

상세 결과와 명령어 원문은 run380의 [f2 결과](../../local_server_rea_20261016/run380_map_transition_receive/f2_findings.md)·[핵심 선정](../../local_server_rea_20261016/run380_map_transition_receive/f2_key_evidence.json), [필드 결과](../../local_server_rea_20261016/run380_map_transition_receive/fields_findings.md)·[필드 디스어셈블](../../local_server_rea_20261016/run380_map_transition_receive/fields_disasm.json), [전환 흐름 결과](../../local_server_rea_20261016/run380_map_transition_receive/flow_findings.md)에 있다. 로컬 JSON의 항목명은 이번 정적 증거 식별자이며 REA MCP Evidence ID나 실행 관측이 아니다.

### 입력·도구와 동일성 한계

지정 deps 접근과 Capstone import는 성공했다. 실제 Python binding은 **5.0.7**, core는 `(5, 0, 1280)`이다. 기존 REA의 section frame+12 / .pdata / x86-64 디스어셈블 방식을 재사용했고, 실제 입력은 기존 `C:/Users/Chansol/Documents/Codex/2026-09-07/d-lineage-classic/work/current_client_key_mapping/recovery.json` 및 `selector_0_record_*.bin`이다. CONTROL `9ffc24fe…b7af`는 기존 manifest에서 상속한 출처 라벨이다.

주소는 **복원 CONTROL의 RVA**다. `LC.guard.exe`의 PE 매핑으로 53262C/53266A/3EB60/10FB4C의 짧은 4개 window를 대조했으나 복원 기록과 모두 달랐다([대조 결과](../../local_server_rea_20261016/run380_map_transition_receive/f2_identity.json)). 그러므로 이 결과를 현재 디스크 파일의 평문 코드나 현재 프로세스 VA 관측으로 주장하지 않는다. 원본 LC·자원·복원 record는 변경하지 않았다.

### f2 소비자 추적의 결과

- `532654→3EB60`의 dynamic_cast R9 RTTI는 `16698F0 / CharacterDataSubsystem`이다. 저장 대상은 이름·형식 계보까지 확인했다. `53262C`의 f2는 `53266A`에서 **CharacterData+568의 32비트 전체**에 저장된다. 이 경로에는 f2의 0/범위/enum/bool 검사가 없다.
- `53276B`에서 EBX는 이전 resolved map으로 덮인다. 새 resolved f1 저장 `532772` 뒤 실제 비교 `532791 cmp ebx,[r13+718]`는 이전·새 resolved **f1** 비교다. f2가 map-changed 분기를 고른다는 해석은 배제된다.
- exact +568 후보 85개에 더해 +568..56B와 겹치는 넓은 access 29개, 주소 노출 26개·immediate 연산 3개, typed getter의 direct call 337개를 좁혔다. `514CE1`은 stack local, `8F64AC/8F9EC8`은 ATSSubsystem vector로 확인해 제외했다. **CharacterData의 실제 reader/후속 분기는 확정하지 못했다.** 계산된 alias·bulk copy·간접 호출·비정상 경계 후보는 남아 있다.
- 생성자 `10FB4C`가 +564 qword를 0으로 만드는 것은 f2의 초기값만 설명한다. **f2=0/항상 0/미사용/즉시 전환 flag 중 어느 것도 원본 정상 계약으로 확정하지 않는다.** 필요한 최소 추가 입력은 정상 4E95 후 이 객체 +568..56B를 읽는 실제 지점 또는 그 alias가 연결된 정적 caller다.

### 각 필드의 갱신된 계약

f1/f2/f3/f4는 기존 schema15F55E0의 required 필드다. 0/false라도 presence를 생략할 수 없다. 아래 기본값과 fallback은 공식 서버의 목적지별 전송값과 구별한다.

| 필드 | 이번까지 확인한 소비 | 정상값 판정 |
| --- | --- | --- |
| f1 | raw Map+71C → 선택적 alias3DA970 → resolved Map+718·tile header. changed-map 판단의 입력 | 목적지 wire raw ID가 필요하다. saved map_id와의 일반적 동일성·alias 범위는 미확정 |
| f2 | typed CharacterData+568에 무분기 32비트 저장 | 업무 이름·후속 소비·정상 서버값 UNKNOWN |
| f3 | Env+88 → graphics singleton+3D8의 **UnderWater** 객체+18/+10. RTTI16DEFB8/vft118BA38, 렌더2158E9에서 false면 본문 생략 | **수중 렌더 후처리 활성 bool**. 호흡/피해 등 서버 규칙은 아님. 목적지별 정상 전송값 UNKNOWN |
| f4 | Env+38. 실제 Env getter2154C0→214950의 214D10 분기에서 렌더 scalar +34/+30 선택 | required bool. receiver fallback은 0이나 업무 명칭·정상 서버값 UNKNOWN |
| f5/f6 | DTO scalar +40/+44 복사. 확인한 direct DTO consumer 3개에서 새 직접 업무 소비는 미식별 | optional uint32. 생성 기본값 0은 공식 presence/값의 증거가 아님 |
| f7 | presence 기반 nested deep-copy52F962→65A1E0→68C5F0 | optional message. nested wire schema·업무 소비·정상 presence UNKNOWN |
| f8 | **581330** subscriber가 nested 사각형을 `(x0,y0,x1-x0,y1-y0)` float vector(owner+6A0)로 재구축하고 580F30 호출. 빈 목록이면 기존 vector를 비움 | 실제 소비 확인. 영역의 게임 이름·정상 목록·최종 효과 UNKNOWN |
| f9 | raw+4A → Map+760 무분기 저장 | Proto 생성 기본값 0까지 확인. 후속 소비·정상 sender 값 UNKNOWN |
| f10 | Env+39 → 214D0A의 렌더 scalar 선택 분기 | **absent fallback=0**:547966 `mov ecx,0`. optional bool의 공식 presence/값·업무 명칭 UNKNOWN |

기존 `work/online_game_owner_coverage/source-contract.json`의 `WorldEnvironment.typed_getter=445470`는 RTTI상 **PolymorphSubsystem**을 반환하는 잘못된 메타데이터였다. 실제 Environment getter는 `2154C0`(215514→RTTI1673298)이다. 위 f4/f10 reader는 이 올바른 객체 계보로 확인했다. 범위 밖의 기존 메타데이터·서버 코드는 수정하지 않았다.

### 다른 맵 전환: 더 닫힌 부분순서와 프레임 누락

MapChanged의 미확정 간접 경계 중 직접 설치 2건을 연결했다. Map getter406F0의 반환에 +198을 더해 등록하는 **MapBackgroundNode**(20B44D→1EE3E0, callback1EC190)와 **ShipSubsystem**(577EDC→57B8F0, callback57A020)이다. 전자는 맵별 배경 설정을 적용하고, 후자는 조건에 맞는 local ship Actor를 퇴역/생성한다. 모든 subscriber 목록이나 타일 완료 receipt는 아니다.

자기 Actor는 별도 경로로 camera에 연결된다. Camera 초기화1D4020이 CharacterData+198에 callback1D3A70을 등록한다. 자기 4E96의 fresh MyPlayer 게시 후 `60DE4→67BA0`가 이를 통지하고, callback은 Actor UID를 **Camera+150**에 쓰며 mode4 전환1D3ED0을 시작한다. 원문 확인한 부분순서는 다음과 같다.

```text
4E95 Actor 정리 → 목적맵 자기/주변 4E96 생성·게시
이미 유효하거나 4E38로 설치한 self UID → 자기 4E96의 MyPlayer factory
자기 MyPlayer 게시 → CharacterData Actor delegate → 설치된 Camera callback
resolved f1 변경 → map-dependent 처리 → 설치된 MapChanged subscriber
```

factory의 실제 target은 `455F9→48420→C26C0(MyPlayer)`, remote는 `45614→48510→C24A0`이다. 앞 절의 주소 축약을 이 원문으로 보완한다.

| 생략·역순 | 원문으로 확인한 영향 |
| --- | --- |
| 다른 resolved map인데 4E95 생략 | 이 경로의 목적지 map/tile header 갱신·map-dependent 처리·MapChanged 통지가 없음. 4E96 좌표만으로 대체된다는 근거 없음 |
| cold/wrong UID 상태에서 4E38 생략 | 자기4E96 factory의 UID 비교가 맞지 않으면 remote Player 분기로 간다. MyPlayer 전용 Camera 통지를 기대할 수 없음 |
| 이미 같은 self UID인 상태에서 4E38 생략 | 이 UID 비교 자체는 반복 전송을 요구하지 않음. 다른 SelfInfo 상태·전체 전환에서 생략 가능하다는 증명은 아님 |
| 4E95 뒤 자기4E96 생략 | 이전 자기 Actor가 정리됐다면 fresh MyPlayer/그 Camera 통지가 생기지 않음. Actor+10 보존 조건 때문에 무조건 모든 자기 Actor 제거라고 단정하지 않음 |
| 자기/주변4E96 먼저, 4E95 나중 | 뒤의63200이 flag10=0인 새 Actor도 정리할 수 있음 |
| 목적지 주변4E96 생략 | 해당 spawn 경로의 주변 서버 Actor가 생성되지 않음. 배경/ship callback이 이를 대신하지 않음 |

**실험 후보** `4E95 → [필요한4E38] → 자기4E96 → 주변4E96`는 위 의존을 만족한다. 공식 total order·추가 effect/remove/환경 프레임·수신 큐 직렬성·비동기 타일 준비·최종 camera/입력 완료는 여전히 미확정이다. Map+6E0이 null이면 4E95는 resolved/map-dependent 처리를 건너뛴다. receiver나 delegate의 RET를 준비 완료로 쓰지 않는다.

### 같은 맵 순간이동

- 같은 resolved map의 **4E95도 Actor 정리를 먼저 실행**한다. 생략되는 것은 changed-map reset/MapChanged이며, 따라서 재전송을 단순 무효 알림으로 취급할 수 없다.
- **4E95 없이 같은 UID 자기4E96**을 받으면 기존 객체 퇴역→새 factory/게시→MyPlayer인 경우 Camera 재통지까지 정적 연결이 있다. 이전의 camera 연결 미확정은 이 범위에서 해소됐다. 좌표만 제자리 수정하는 방식은 아니며, 주변 시야·효과·선택/current 수명·입력 복구 전체의 동등성은 입증하지 않았다.
- 별도 위치 프레임 **4EE0**는 기존 MyPlayer의 MovingBackAction→95544→C0E90으로 현재/목표 좌표를 함께 보정하고 Navigation을 중단한다. Actor가 없으면 복원하지 못하며 queue/busy에 따라 지연된다. 원본 순간이동용으로 채택할 근거는 없다.
- 따라서 같은 맵 순간이동의 4E95 재전송 필요성·최종 필수 프레임 목록은 아직 UNKNOWN이다. Restart 대체·map guard·서버 코드는 변경하지 않았다.

### 남은 항목을 답할 최소 실험 3개 — 이번에는 설계만

1. **정상 원본 map0 같은 맵 귀환/순간이동 1회:** 기존 관측으로 행동 직전부터 정상 다음 C2S까지 4E95 유무·f1..10 presence/값, 4E38 반복, 자기4E96/4EE0·effect/remove 순서를 남긴다. 사용자는 자기 1명·주변 갱신·선택 화면 없는 도착·다음 한 칸 이동을 확인한다. 같은 operation의 f2를 얻되 모든 맵 상수로 일반화하지 않는다.
2. **정상 원본 말하는 섬 던전 입장/퇴장 1왕복:** 각 방향의 같은 짧은 프레임 기록과 raw/resolved map·grid/current·Camera UID를 기존 경로로 묶는다. 사용자는 양방향 지형·자기 1명·도착 후 이동을 확인한다. map0 복귀값을 로컬 최초 baseline과 비교한다. 실제 관측 없는 ACK나 대기는 추가하지 않는다.
3. **정상 같은 맵 기록 확보 후 로컬 기준/4E95 생략 비교:** 시험 담당이 정상 로그인→선택→월드의 시험 저장 사본에서 기록 그대로 기준 1회를 먼저 성공시킨 뒤, 동일 self UID/목적지/환경/Actor 목록으로 **4E95만 생략**한 비교 1회를 수행한다. 사용자는 배경·주변 잔상·자기 1명과 다음 이동/선택을 비교한다. 기준이 실패하면 첫 실패에서 멈춘다. 이 결과는 그 조건의 생략 가능성만 답하며 f2 정상값을 추정하는 실험은 아니다.

화면만으로 wire 값/presence/순서를 읽을 수 없다. 기존 관측에 그 입력이 없으면 UNKNOWN을 유지한다. 위 실험은 수행하지 않았고, 실행 도구·서버 패치를 만들지 않았다.

### 실행 결과와 제한

프로젝트 루트에서 지정 Python으로 아래 정적 분석을 실행했으며 생성 명령은 exit 0이었다. 산출 JSON의 핵심 명령어·RTTI·getter·delegate 연결은 다시 읽어 확인했다.

```powershell
$mapPython = 'C:\Users\Chansol\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$mapRun = 'work\local_server_rea_20261016\run380_map_transition_receive'
& $mapPython -X utf8 -B $mapRun\f2_research.py           # overlap / calls 3eb60 / identity / focused도 실행
& $mapPython -X utf8 -B $mapRun\fields_research.py 546a70 580f30 65a1e0 78d5e0 95ed0 708420 72a5a0 57df00
& $mapPython -X utf8 -B $mapRun\flow_extract.py functions flow_camera_callback.json 1d3a70 60b50 67ba0
```

새 guard/검사기·검사 범위 확대는 없다. 단, flow 초기 4개 추출은 기존 Restored loader를 재사용해 **그 loader의 기존 전 record 해시 초기검사**가 실행됐다. 이후 추출은 f2 View의 no-hash reader로 전환했고 초기 결과도 보존했다. 이를 해시검사 0으로 기록하지 않는다. 새 서버/게임/포트/broker/패킷 시험·원본/저장/큐/서버 코드 변경·커밋은 없다. 이번 결과는 정적 SOURCE 확인이며 맵 전환·화면·입력 PASS가 아니다.

## 9. run389 같은 맵 먼 이동: 4EE0 카메라 소비와 주변 Actor — 2026-10-26

**기존 MyPlayer·self UID·Camera key4가 유효하면, 4EE0는 자기4E96 재생성 없이 좌표와 카메라 위치를 갱신할 정적 경로가 있다.** 기존 E3의 미확정 `95595→1D3B20`을 닫았다. `1D3B6B`는 CameraSubsystem+150 UID, `1D3B76→627B0`는 Actor lookup, `1D3BE8→C0CF0`는 Transform 현재 Coordinate, `1D3C78`는 **1D3160(key4)가 반환한 카메라 객체.virtual88** 위치 설정이다. 기존 vptr1237FB0에서는 `B56BA0→B56BC0`으로 XY를 카메라+3C/+40에 쓰고 dirty flag를 세운다. 같은 Float2의 CameraSubsystem+20 delegate 발행은 `1D3D19`이며 모든 실제 subscriber의 효과는 미확정이다. Action busy/queue에 따른 Start 지연과 key4/UID 전제는 그대로다.

상세 원문·후보·실험안은 [run389 결과](../../local_server_rea_20261016/run389_same_map_teleport/findings.md), [Action/카메라](../../local_server_rea_20261016/run389_same_map_teleport/action_camera.json), [최종 좌표 쓰기](../../local_server_rea_20261016/run389_same_map_teleport/camera_position_leaf.json)에 있다. 이 결과는 자기좌표·카메라의 정적 연결이며, 원본 귀환/순간이동 용도·효과·공식 total order·최종 배경/입력 성공을 입증하지 않는다. 일반 per-frame camera update를 UID→Transform 매프레임 추적으로 확정하지 않았다.

4EE0의 C0E90은 자기 현재/목표 및 두 위치 색인을 바꾸지만 확인한 직접 경로에 주변의61650/63200 퇴역이나4E96 게시가 없다. 자기4E96도 그 UID만 교체한다. **4E40는 SC_REMOVE_OBJECT_NOTI, required f1 uint64 UID**이며 `17FBF80→4E700→61650`이 첫 UID 일치를 퇴역한다. 숫자/schema 원 출처는 run75 `source-evidence.json#/bindings/1`(opcode20032, schema15FCD20, field1 descriptor15FCD64/required mask1), 타입/수명은 run272 `source/registry/registry-contract.md:5`다. 5FEF0 tick의 `60122→6013D→6064D`는 component+49 표식 UID를 모아 퇴역하며, 거리가 멀어지면 자동으로 표식된다는 연결은 확보하지 못했다. 화면 culling과 논리 퇴역을 구분한다.

| 같은 map·정상 current에서의 최소 후보 | 판정 범위 |
| --- | --- |
| 자기 4EE0(f1=x,f2=y) | 기존 자기좌표·Navigation·결속된 카메라의 정적 경로. 주변 변화가 없을 때 가장 작은 비교 후보이며 cold 자기Actor/카메라를 만들지 못함 |
| old-only 주변4E40 → 자기4EE0 → new-only 주변4E96 | 자기 제외 `O∖N` 제거 / `N∖O` 게시 후보. 자기UID는 remove에서 제외. 유지할`O∩N`에는 불필요한 remove/reappear를 강제하지 않되 필요한 좌표/상태는 기존 정상 알림으로 갱신 |
| old-only4E40 → 같은UID 자기4E96 → new-only4E96 | 기존 객체 퇴역→fresh MyPlayer→카메라 재통지의 대안. 4EE0와 action/selection/객체 수명이 다르며 자기4E40 선행은 필수 아님 |
| 같은맵4E95 → [필요한4E38] → 자기/목적주변4E96 | 63200 bulk정리 대안. 실제 환경/presence가 필요하며 정리된Actor는 다시 게시. 4E95 재전송 필수 여부·정상값은 여전히 미확정 |

**화면 실험안은 미실행:** 정상 원본 같은맵 먼 이동1건의 실제프레임·Actor/current/Camera·다음입력을 먼저 확보하고, local 정상기준1회 뒤 위4EE0 최소후보를 비교한다. 사용자는 자기1명·지형·old-only 소멸/intersection 유지/new-only 출현·다음걷기/선택을 확인한다. old-only는 화면밖 비표시와 정상lookup 부재를 분리한다. 기준이 실패하면 첫실패를 보존한다. 실제 원본 메시지/순서와 같은 operation의 상태/다음입력이 최소 부족입력이며 새수집기·ACK·guard를 만들지 않는다.

run380 f2 View의 no-hash 복원 reader와 지정Python/Capstone으로 run389 선택정적추출을 실행했고 명령은 exit0, JSON 핵심명령 재독 확인을 마쳤다. 현재디스크/프로세스 동일성은 미확정이다. 변경은 새run389와 이 끝절뿐이며 기존원문·제품코드·저장·큐는 보존했다. 게임/서버/포트/패킷/화면/입력 실행·새검증기/guard·hash재계산·commit은 0이다. SOURCE_ONLY이고 화면/입력 PASS가 아니다.
