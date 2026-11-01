# 요청 지도 — 리니지 클래식 26.09.29.2001

2026-10-28 · 초기 지도는 정적 분석·서버 코드 조사다. 이후 요청별 보완·단위/봇 시험은 아래 「자주 쓰지만 일부 처리인 요청」에 구분한다. 원본 클라이언트 실행·캡처·커밋 없음.

**발견한 CS 타입의 스키마 전수 목록은 작성했지만, 모든 발신 opcode·UI·응답 계약을 확인한 완전한 wire 명세는 아니다.** opcode 미확인 항목도 전체 JSON에 남겼다. 현재 dirty working tree의 읽은 소스 기준이며 동시 작업자의 이후 변경은 포함하지 않는다.

[전체 표](REQUEST_COVERAGE_MAP.json)의 `rows`는 독립 요청 후보, `nested_types`는 중첩 DTO다. `expected_s2c`에서 원문 소비 계약·이름 후보·현재 서버 송신 목록을 분리했다.

## 추출 범위와 확인률

- CS RTTI 233개 → 최상위 요청 후보 221개 + CS 중첩 DTO 12개. 추가 중첩 타입 16개. 총 재귀 필드 571개.
- 최상위 스키마 221/221 확인. opcode 136/221 (61.5%) 결속, 85개 미확인. 원래 `.proto` 필드명은 미복원하며 f번호·형식·중첩 구조를 제공한다.
- UI/상황의 기존 문서 근거는 21/221. 버전 요청 1개는 정적 생성→queue 연결을 추가했지만 정확한 UI는 UNKNOWN이다. 그 밖의 UI 설명은 이름 기반 추정이며 **플레이 빈도는 전부 추정**이다. 미결속 85개의 빈도는 해당 기능을 실제 발신할 수 있다고 확인한 값이 아니다.
- S→C 수신 등록 354건은 opcode→factory→publisher→typed RTTI까지 연결했다. 요청과 같은 이름의 ACK/NOTI 대응은 별도의 추정이며 필수 응답으로 확정하지 않았다.
- 출처: 로컬 원본 분석 carrier·기존 REA·현 서버 코드 100%, 신규 공식 API/웹/L1J 조회 0%. 이 비율은 기능 완성률이 아니다.

| 서버 처리 상태 | 요청 후보 수 |
|---|---:|
| 처리함 | 11 |
| 일부 | 11 |
| 안 함 | 110 |
| 실험 스위치 뒤 | 4 |
| 미확인 | 85 |

`처리함`은 정적 구현 경로 확인이며 전체 원본 동등성/동작 PASS가 아니다. `일부`는 분기·대상·설정 제한, `실험 스위치 뒤`는 기본 비활성 경로다. opcode가 없으면 서버 상태를 null/미확인으로 두었으며 안 함에 합산하지 않았다.

## 미처리 중 자주 쓰는 요청 우선 목록

일반 사냥에서 해당 입력을 쓰는 경우의 조건부 우선순위다. 원본의 현재 UI가 실제로 발신하는지는 별도 확인해야 한다.

| 순위 | 요청 | 상황/빈도 | 서버 조사 결과 |
|---:|---|---|---|
| 1 | `0x4E42 CS_ATTACK_CONTINUE_REQ` | 연속 공격 상태/대상 유지 요청 후보. 실제 자동공격 입력·반복 주기는 미확인 / 자주(추정) | 안 함: FRAMES/HANDLERS/game.routes/수신 확장에 연속 공격 요청 경로 없음. 임의 응답 없음. |
| 2 | `0x4EE1 CS_FAR_ATTACK_NOTI` | 원거리 공격 알림 후보. 현재 활 공격 UI가 이 요청을 쓰는지, 4E30을 쓰는지 미확인 / 자주(추정) | 안 함: FRAMES/HANDLERS/game.routes/수신 확장에 원거리 공격 알림 경로 없음. 임의 응답 없음. |

**일반 채팅은 별도 우선 공백이다.** 확인한 Mobile/PC normal0 UI는 `PurpleCommunityChatAPI::SendMessage`로 간다. 게임 소켓용 일반 채팅 opcode는 미확인이다. `4F2D CS_CAN_WHISPER_TO_REQ`는 귓속말 선검사이며 일반 채팅 송신이 아니다. [CHAT_EVIDENCE](CHAT_EVIDENCE.md:9)

연속 공격의 응답 **후보**는 `4F32 SC_ATTACK_CONTINUE_ACK`다. 이 수신 타입과 opcode는 확인했지만, `4E42`마다 반드시 답해야 하는지와 응답 순서는 미확인이다. `4EE1`의 응답 계약은 미확인이다. 일반 공격 경로 `4E30→4E31`의 근거를 원거리 전용 알림에 그대로 적용하지 않는다.

## 자주 쓰지만 일부 처리인 요청

표를 위에서부터 보존 원문과 현재 서버에 대조했다. **스키마에 있는 필드, 실제 sender가 설정하는 값, 해당 template의 효과 계약은 서로 구별한다.** 아래의 수용은 디코더/서버 범위이며 원본 화면·입력 PASS가 아니다. 다섯 요청의 전체 상태는 계속 `일부`다.

| 요청 | 실제 발신 인수의 정적 근거 | 처리 전 | 처리 후 / 잔여 |
|---|---|---|---|
| `0x0960 CS_USE_ITEM_REQ` | outer f1=u64 사용UID, f2=UseItemReqParam. `52A410`은 원 params를 복사하고 부재 f15/f16만 0으로 설정. `52A820`은 `{1:1,2:대상UID64,3:0,15:0,16:0}`. `52AC90`은 f1=현재 행 Q의 low32, f6=상위 입력값, f17=1, f15/f16=0. `A23510`은 별도 MailLayout callback으로 f11 하위 객체의 문자열 네 개와 f15/f16=0을 설정. | raw0 `{1:1,15:0,16:0}`, 확인된 targeted 형태와 명시 template만 처리. | 알려진 raw0/targeted는 기존 처리 재사용. **추가 template 0개.** f17=1 경로의 실제 UI 대상·template·효과는 미확인. 메일은 f11 typed graph와 처리·응답 계약부터 미지원이다. 임의로 물약/장착 효과에 연결하지 않았다. 장착·소모품·마법서·강화·귀환·변신·펫의 개별 제한은 유지. |
| `0x4E2B CS_MOVE_NOTI` | `94570→948C6→27D620`: f1=u32 출발 packed grid, f2=i32 방향. 정상 방향0..7, UID 필드 없음. | 일반 이동·위치 소유·시야 갱신, 수락된 자기 이동 echo 없음. | 실제 확인한 발신형은 이미 수용하므로 구현 변경 없음. 층/다른 맵 전이는 기존 실험 설정 의존. 현재 근거에서 추가할 미지원 발신형은 확인하지 못함. |
| `0x4E30 CS_ATTACK_NOTI` | `A38E0→A3970`: 대상UID와 대상 현재X/Y를 설정, `A3C34→27D620`. 별도 sentinel -1은 UID0으로 변환. | 현재 월드 몬스터 공격·거리·LOS·속도·탄약 검증. | 정상 UID+X/Y는 기존 수용. 월드 경로는 좌표를 파싱하고 UID의 서버 위치로 판정한다. UID0 actor 공격은 미지원. 효과 계약이 없고 전투 파일이 이번 수정 금지 범위이므로 변경 없음. LOCAL/L1J 계산·원거리 표시/HP바 실험은 원본 전체 규칙이 아님. |
| `0x4E3E CS_GET_ITEM_REQ` | `3CD90→3CE6A→27D620`: singular f1.child=`i32 x/y, u64 ground UID/Q`. 즉시 분기는 Item+38의 Q. popup `B9A10..B9ADF`는 nonzero u64 입력을 상한 clamp 없이 전달. | 0 또는 바닥Q 초과 요청을 **바닥 전체Q로 치환**하여 획득. 정상 수량은 기존 저장/응답 처리. | **요청Q를 기존 GroundItems 수량 판정에 그대로 전달하도록 수정.** 초과Q·0은 그 요청만 거절하고 저장·바닥을 보존. 정상 partial/all·저장 재열기·중복방지·CAS 실패 보존 확인. 이 거절은 기존 LOCAL 정책이며 원서버 규칙으로 확정하지 않음. 비월드 transfer 경로는 유지. |
| `0x4EE6 CS_USE_SPELL_REQ` | key만/child 부재=`5B5E48..7C`; key+child 좌표f3/f4=`1632D7..2F7`; key+child 대상f1+좌표=`5B650B..6544`; 공통 `5B755B EDX=4EE6→5B7568→27D620`. | catalog·학습·직업·레벨·비용·재사용·대상·범위·LOS·무게 제한. | 세 실제 발신형 모두 기존 decoder 수용. 대상 부재는 비공격성 주문의 LOCAL self 기본값, 명시0은 UID0 조회로 구별. 지점형 공격/범위마법·NPC 회복·타인 대상 자기전용 버프는 미지원. 정확한 원 spell key/효과 계약 부족 및 마법 파일 수정 금지로 변경 없음. 다른 optional은 실제 발신 미확인. |

원문과 소비 경로:

- `0960`: [run37 sender](../../local_server_rea_20261016/run37_item_command_sender/findings.md), [raw0 계약](../../local_server_rea_20261016/run286_hp15_130_use_param_family/source/contract.md), [targeted 원문](../../local_server_rea_20261016/run393_item_target_use/body-52a820.json), [run393 caller 원문](../../local_server_rea_20261016/run393_item_target_use/body-529480.json), [52AC90 vtable](../../local_server_rea_20261016/run393_item_target_use/tables-52ac90.json), [메일 원문](../../local_server_rea_20261016/run393_item_target_use/body-a23510.json). `529549/54C→529552 CALL[vtable+18]`까지 연결했으나 f6의 업무 의미를 actor UID로 확정하지 않았다.
- `4E2B`: [movement contract](../../local_movement_contract/contract.json), [action followup](../../local_move_action_followup/contract.json), [보존 명령](../../local_server_rea_20261016/input_evidence/retained_instructions.md):1087–1118.
- `4E30`: [run24 findings](../../local_server_rea_20261016/run24_normal_attack/findings.md), [원문 S4/S6](../../local_server_rea_20261016/run24_normal_attack/source-evidence.json). 생산자 `A3902/A3910`, sentinel 변환 `A3BE4..BEC`, 송신 `A3C2B/A3C34`.
- `4E3E`: [run98 findings §3](../../local_server_rea_20261016/run98_item_drop_pickup_contract/worker/findings.md), [원문](../../local_server_rea_20261016/run98_item_drop_pickup_contract/worker/source-evidence.json):4424,6594,7685; [수정 소비자](../../../tools/local_original_session/world_visibility.py) `pc_pickup`, [새 시험](../../../tools/local_original_session/move_pickup_coverage_tests.py). Q0은 방어 동작 시험이며 실제 popup 발신값으로 확인한 것이 아니다.
- `4EE6`: [key-only 원문](../../local_server_rea_20261016/run134_spell_selection_caller/worker/tail-5b5a70.json), [run104 producer 원문](../../local_server_rea_20261016/run104_skill_buff_contract/spell_input/source-evidence.json), [wire 계약](../../local_server_rea_20261016/run104_skill_buff_contract/wire_schema/cast_4ee6/packet.json). `5B5F80/B1FE10`의 다른 sender는 타입/opcode 결속만 확인했고 실제 인수·UI는 미확인이다.

단위 시험: `python -m unittest tools.local_original_session.move_pickup_coverage_tests tools.local_original_session.movement_tests tools.local_original_session.world_ground_items_tests -v` → **26 OK**. 새 4건은 초과Q/u64 상한/0 거절·저장/바닥 보존, 정상3+7 부분/최종 획득·저장 재열기·0965/4E40·타이머, 전량 후 중복 요청, CAS 실패를 확인한다. 직접 함수 기반 개발 시험이며 로그인/월드 진입 PASS로 확대하지 않는다.

아이템 기존 회귀: `python -X utf8 -B -m unittest tools.local_original_session.item_use_tests tools.local_original_session.world_item_effects_tests tools.local_original_session.world_enchant_inventory_tests` → **59 OK**. 공격/마법 codec·요청 및 pickup/visibility/ground 영향 범위의 별도 실행은 **54 OK**다(일부 모듈 중복이므로 합산하지 않음).

봇은 사용자 지정 `C:/Users/Chansol/AppData/Local/Temp/claude/D--claude/0483de89-75e7-4b94-84b8-fb31fe00f575/scratchpad/fastbot/run_fast.py`와 `SL_TEST_TIME_SCALE=10`을 사용했고 포트 실행을 겹치지 않았다. base는 `SL_TEST_PORT_BASE` 값이며 기존 두 endpoint의 +2030 매핑을 유지했다.

| 명령 (`python -X utf8 -B <위 wrapper>` 뒤 인수) | 결과와 경계 |
|---|---|
| base45000 `hunt_bot_consumables --scenario consumables` | 최초 startup의 `Material(l1j_item_id=...)` TypeError, FIRST 이전 실패·cleanup=true. 다른 writer가 제작 로더를 수정한 뒤 재시도는 정상 FIRST/login/world와 올바른 `WISDOM_MAGE_REQUIRED` 거절까지 도달했으나 인벤 전체 동등성 체크에서 FAILED. 저장 frame은 시작 fixture와 동일. canonical/표시 행 차이가 원인 후보이며 실제 wire snapshot 차이는 미확인. 기대값/제품 수정으로 통과시키지 않았다. |
| base46000 `hunt_bot_scenarios --scenario all --navigation-timeout 900` | 최초5개 모두 bind `WinError10048`·cleanup=true. 포트 해제 후 재시도는 **25/25 SUCCESS**(death4/reconnect6/town2/items4/combat9), 6 epochs failure/close=null·cleanup=true. 다만 실행 중 다른 writer의 `data/crafting.json` 변경이 있어 고정 Source 정식 PASS로 확대하지 않음. |
| base45000 `hunt_bot_request_coverage --minutes 2 --timeout 15` | 새 [직접 GET 봇](../../../tools/local_original_session/hunt_bot_request_coverage.py)은 기존 loopback/HuntBot으로 정상 로그인→자연 처치·수신 ground UID/Q→Q+1 거절→정상Q 획득→Quit/디스크 재열기를 확인하도록 작성했다. 문법 검사만 통과. 실행은 **import 단계 FAILED**: `ack_enter_world.py:21 EXACT_CHARACTER_CREATION_REALM_REQUIRED`. 다른 writer가14:27:18에 변경한 realm SHA `91cfbade…`와 기존 요구 `b594d067…`가 다르다. 포트/프로필/GET 미진입이므로 요청 쌍·초과Q 보존·정상Q 획득·Quit 저장은 미확인. 범위 밖 원문/기존 핀을 수정하거나 우회하지 않았다. |

원문: [첫 실패 로그](../runs/request-coverage-20261028/raw-142154/), [재시도 로그·메타](../runs/request-coverage-20261028/raw-retry-142429/), [직접 GET import 실패 traceback·메타](../runs/request-coverage-20261028/raw-get-142804/). 보존 사본: [소모품 재시도](../runs/hunt-consumables-v19_8rba/), [일반 시나리오 재시도](../runs/hunt-scenarios-avq_q9w7/). 이 일반 봇 결과만으로 초과Q 분기를 검증했다고 주장하지 않는다. 마감 시 소유 포트는 해제됐다.

**마감 기준은 일부 미달이다.** 전/후 표·원문 인수 확인·GET 수정·단위 시험·지도 갱신은 수행했다. 새 template 처리는 근거 부족으로 추가하지 않았고, 초과Q 분기의 소켓 봇 PASS는 기존 realm/pin 결속이 통합된 뒤 위 명령으로 다시 확인해야 한다. 단위/일반 봇은 realm 변경 전 실행 기록이며 현재 시작 조합의 성공으로 옮기지 않는다. 핀 갱신 담당에게 전달할 이번 제품 변경 파일은 `tools/local_original_session/world_visibility.py`다.

원본으로 남은 확인: 각 UI→template/실제 인수, 원서버의 수량 거절 응답, 부분 획득 뒤 ground 표시 갱신, UID0 공격 및 지점형 마법의 정확한 의미·필수 응답. 원본 클라이언트는 실행하지 않았다.

## 기본 경로와 실험 분기

같은 opcode 안에 정상 처리와 실험 분기가 섞여 있다. 아래 요약을 기능 전체 미구현/전체 지원으로 확대하지 않는다.

| 요청 | 상태·스위치 |
|---|---|
| `0x0960 CS_USE_ITEM_REQ` | 일부; SL_PET=1; default 0; SL_EXPERIMENT_TALKSCROLL unset: native; npc: old menu experiment; cross-map requires SL_EXPERIMENT_MAP=2; SL_EXPERIMENT_ENCHANT default off controls only 0967, not enchant mutation; SL_EXPERIMENT_POLY default empty; required selected form; KIT_POLICY + world selected owner; cross-map requires MapExp2; SL_COMPANION=1; default unset/off; SL_COMPANION_REVIVE_EXP=1 only in-place 4F16; default same-UID spawn; world magic store requires KIT_POLICY + inventory store; owned selected world + consumable store; item-use session / equipment effect explicit source-bound policy |
| `0x4E2B CS_MOVE_NOTI` | 일부; world selected live PC; magic status can reject movement; SL_EXPERIMENT_MAP default 0; cross-map/stair=2 |
| `0x4E30 CS_ATTACK_NOTI` | 일부; SL_EXPERIMENT_ARROW default f6=0,f14=1; literal arrow candidate; SL_EXPERIMENT_HPBAR default off; only hpbar frames gated |
| `0x4E33 CS_RESTART_REQ` | 일부; restart_policy / restart_enabled default constructor False |
| `0x4E3E CS_GET_ITEM_REQ` | 일부; world selected ready + compatible inventory store |
| `0x4E3F CS_DROP_ITEM_REQ` | 일부; item_transfer explicit switch/service; default False |
| `0x4E43 CS_DIALOG_REQ` | 일부; SL_WORLD_TOWN_CANDIDATES default confirmed IDs only; SL_PET default0 for trainer branch; external prepared resource/menu source or startup JSON source required |
| `0x4ED1 CS_BUYSELL_REQ` | 일부; shop default needs explicit prepared external source or ShopExp; warehouse branch requires WarehouseExp |
| `0x4ED4 CS_HACTION_REQ` | 일부; SL_EXPERIMENT_SHOP default None/off;1 supplies LOCAL 7/0/0/0; SL_EXPERIMENT_WAREHOUSE default empty/off |
| `0x4ED6 CS_SAVE_SETTINGS_REQ` | 처리함; explicit settings storage |
| `0x4EE6 CS_USE_SPELL_REQ` | 일부; KIT_POLICY + inventory store; not SL_SPELL_EXP for numerical effects; SL_SPELL_EXP default off; controls candidate4E31/4ED8 display; supported 28 catalog 4E91 icons default on, SL_PLAYER_MAGIC_BUFF_UI=0 disables; SL_PLAYER_MAGIC_BUFF_SECONDS unset normal; only explicit10 test override permitted |
| `0x4EEC CS_DEAD_RESTART_REQ` | 일부; player_life service OR (world + restart_policy); no enabled implicit default |
| `0x4EF5 CS_GIVE_REQ` | 실험 스위치 뒤; SL_COMPANION=1 and companion inventory exists; default off |
| `0x4EF8 CS_ENTER_SHIP_REQ` | 실험 스위치 뒤; SL_EXPERIMENT_MAP=2; default0 off |
| `0x4F02 CS_PET_COMMAND_REQ` | 실험 스위치 뒤; SL_PET=1 OR (SL_COMPANION=1 AND SL_COMPANION_PET_UI=1); defaults off |
| `0x4F13 CS_SUMMON_STAT_REQ` | 실험 스위치 뒤; SL_PET=1 OR (SL_COMPANION=1 AND SL_COMPANION_PET_UI=1); defaults off |

## 근거와 재현 경계

- 원본 CONTROL·분석 carrier 신원: [TARGET_IDENTITY](../../local_server_rea_20261016/TARGET_IDENTITY.md:7). SHA256은 기성 신원을 승계하며 새 전수 해시 검사를 하지 않았다. carrier는 원본 실행파일 자체가 아니다.
- [ATS_COMPANION_EVIDENCE](ATS_COMPANION_EVIDENCE.md:70)의 `0x293570`은 **S→C 수신 등록**이다. 이것을 C→S 등록표로 뒤집어 세지 않았다.
- carrier의 모든 `.?AVCS_...` RTTI → COL/vtable → vtable+0x40 schema getter → compiled descriptor를 읽었다. 필드 수/번호, typecard, raw offset, aux의 child default instance→RTTI/schema를 연결했다. JSON에 TD/vtable/schema RVA를 보존한다.
- C→S `0x27D620` 직접 E8 190곳 중 189곳은 opcode EDX 및 R8 stack slot/CS vptr를 결속했다. 남은 `5B7520` wrapper는 typed caller `5B5E7C`의 R8 객체가 보존되어 `5B7568`로 전달됨을 추가 결속했다. 별도 버전 송신은 아래 공통 `26DA90` queue 경로다. `opcode_static_proofs`에 각 인수·callsite·vptr 근거를 담았으며 간접/computed 경로 전체를 복원한 것은 아니다.
- 같은 함수 안에 있다는 이유만의 매칭은 `opcode_candidate`/candidate 근거로 보존했으며 확정 opcode로 승격하지 않았다.
- 서버는 broker admission → world feature dispatch → base route의 순서, FRAMES.update·METHODS override·실험 기본값까지 읽었다. 서버의 현 응답은 원서버의 필수 응답 증거가 아니며 이름이 같은 SC_ACK도 후보일 뿐이다.

## opcode 미결속 후속 조사

기존 86개 중 `CS_CLIENT_VERSION_INFO` **1개를 `0x4E34`에 추가 결속**했다. 나머지 85개는 opcode를 null로 보존했다. 같은 타입 생성/삭제 코드가 존재한다는 사실을 현재 UI의 실제 발신 가능성으로 해석하지 않는다.

- 버전 메시지: owner `26E160`, `26E1F6`의 vptr `11E3B70` → `26E1FD [rbp+20]`. `26E8D3 R8D=4E34`, `26E8D9 R9=&[rbp+20]`, `26E8E0 CALL26DA90`을 연결했다. 이 지점은 **27D620 직접 호출이 아니다**.
- 공통 queue의 소비: `26DAA2 R14=R9`, `26DAA5 EBP=R8W`, `26DB30` opcode 저장, `26DB32..26DB4A` typed 객체의 virtual New/copy. 일반 adapter도 `27D650 EDI=DX` → `27D65F R9=R8` → `27D662 R8D=DI` → `27D66D CALL26DA90`을 사용한다.
- 기존 `CS_USE_SPELL_REQ=4EE6`의 남은 direct wrapper: `5B5E5D` vptr `11E3B08` → `5B5E64 [rsp+30]` → `5B5E74 R8=&[rsp+30]` → `5B5E7C CALL5B7520`. helper의 `5B752A RBX=R8`, `5B755B EDX=4EE6`, `5B7560 R8=RBX`, `5B7568 CALL27D620`으로 연결했다. 새 opcode/요청 행을 늘린 것은 아니다.
- 미결속 85개: executable `.rea1`의 typed-vptr RIP materialization → PData owner → 직접 E8 caller, 전체 6개 section의 절대 VA64 vptr/static default instance 및 해당 instance의 common scalar RIP code 참조를 조사했다. 관측된 vptr 경로는 protobuf New/할당·삭제 함수였으며 그 밖의 실제 typed 발신 생산자는 찾지 못했다. 각 행의 `static_path_investigation`에 주소·검색 경계·다음 필요 관측을 남겼다.
- 전체 section에서 `27D620` rel32 E8는 기존 190곳, E9는 0곳이었다. `27D620/26DA90` 절대 VA64 pointer도 찾지 못했다. 이 bounded negative는 computed/간접/virtual/default-instance 선택 경로의 부재·미사용·서버 미지원 증명이 아니다. 그 경로 또는 생산자가 포함된 다른 보존 artifact가 필요하다.

버전 요청의 UI는 owner 호출 조건까지 미확인이다. 빈도는 이름과 초기화 경로에 근거한 **접속/부트 시 후보**이며 접속당 1회·재시도 횟수는 관측하지 않았다. 현재 로컬 서버는 `WAIT_VERSION`/build 필드를 검증하고 `plan.version_response_allowed`일 때 `4E35`를 반환한다. preserved 경로는 기존 `resource.version_frame()`을 사용한다. 이 한정된 부트 계약을 `처리함`으로 옮겼고 기존 server-only `4E34`와 중복 집계하지 않았다. 85개는 **opcode 미결속/미확인**이며 `안 함` 110개에 합산하지 않았다.

앞선 시도의 근거: 고정 carrier SHA256 `c822838351d774a2022af434829a36dbd9bee030bf22182b834ca4e8659701a9`의 로컬 byte/Capstone 정적 인수 경로. 당시 REA Ghidra는 carrier 신원 확인에 사용했으며 지연된 provider 함수 응답을 성공 근거로 삼지 않았다. 이번 REA 반환 결과는 아래 재시도 절에 구분했다. 실행·화면·네트워크 관측은 없다. 서버 원문은 [handshake.py](../../../tools/local_entry_server/handshake.py:152), [preserved broker](../../../tools/preserved_pack_bootstrap/broker.py:65), [connection.py](../../../tools/local_game_session/connection.py:55), 기존 bootstrap route [session.py](../../../tools/local_game_session/session.py:175)다.

## 1800초·메시지별 재시도 (2026-10-28)

**추가 opcode 결속 0개: 136/221 유지, 85개 UNKNOWN. 일반 채팅 opcode도 미확인이다. 완료 기준인 결속 수 증가는 달성하지 못했다.** REA 재시도 자체는 반환·종료까지 완료했으며 새 wire 결속이나 runtime PASS로 세지 않았다.

- REA6.4.0/Ghidra12.1.4의 `REA_GHIDRA_STARTUP_TIMEOUT_MS=1800000`을 **분석용 프로세스 환경에만** 적용했다. 이는 import/전체 자동 분석의 초기화 제한이며 함수별 MCP 인수는 아니다. 지속 MCP 세션에서 우선 UI 16종부터 나머지까지 vtable xrefs 85회, `26DA90/27D620/26E160/9B5370/472380` 함수 dossier 5회를 받았고 close까지 완료했다. 초기 분석을 포함한 첫 xref는 **1212.95초**, 나머지 조회는 같은 세션을 재사용했다. 처음 CLI 환경 누락 실패와 지속 세션 전환을 위한 수동 중단은 별도 보존했으며 시간 초과/성공으로 바꾸지 않았다.
- **REA xref 477개:** 기존 typed-vptr materialization196 + 기존 default-instance85 + 추가 source196. 추가196개는 전부 기존 New/delete owner 안의 동일 레지스터 vptr 저장 MOV(LEA+7:176, +10:20)였으며 새 송신 생산자·미분류 참조는 0개다. xrefs 자체에는 reference-kind가 없어 MOV 판정은 고정 carrier byte/Capstone으로 보강했다. 각 행의 `REA_xrefs_retry`에 전체 정규 주소·짝 LEA·근거 ID를 남겼다. 대표 PARTY Evidence는 `ev_2d01773a5992158960c6b1302c41e12a745a924261f0db48804ff603a17b7caf`다.
- REA queue dossier도 `26DA90`의 caller를 기존 `26E160/27D620` 두 곳으로 반환했고 opcode `R8W` 저장과 typed `R9`의 virtual `+10 New/+30 copy`를 확인했다(Evidence `ev_b5705b67177df9fd9e76493467a43e916c8b54b5c84797be9a2d0033f806eac1`). **27D620/472380 high-pcode는 truncated**이며 완전한 value-flow 복원으로 표시하지 않는다. `26E160` recovered pseudocode는 queue 호출을 인수1개로 잘못 축약하므로, 버전 결속은 원 assembly `26E8D3 R8D=4E34 /26E8D9 R9=&[RBP+20]`을 사용한다. PC 및 공통 채팅 Evidence는 `ev_5283a8f330f4ac8ae945e77f577fac9756e17c8681ebaef06eb92d15ee198314`, `ev_622163fdf92dc9d144500de78ecd6b22d2375db14adada3010cec057deb8353b`다. 원문 응답은 JSON의 `opcode_retry_20261028.REA.raw_evidence_directory`에 보존했다.
- 우선 16종(혈맹 11·파티 mark·GET/SET toggle·EQUIPSET·ITEM_EXCHANGE), 이어 미결속 85종 전체의 vtable `+0..+58` 중 타입 고유 method 850개를 역추적했다. `.rea1` E8/E9 직접 소비 0, vtable 밖 literal absolute64 method/schema pointer 0. common scalar RIP schema 참조 85개는 각 generated dispatch 한 곳뿐이다. 계산 주소·동적 간접·generic default-instance 선택은 미확인이다. JSON 각 행의 `static_path_investigation.method_schema_retry`에 주소/경계를 보존했다.
- `26DA90` 직접 E8 호출은 `26E8E0`(기존 CLIENT_VERSION `4E34`)와 `27D66D`(기존 adapter) 두 곳이다. 추가 E9·literal absolute64 pointer는 관측하지 못했다. `27D650 EDI=DX → 27D65F R9=R8 → 27D662 R8D=DI → 27D66D CALL26DA90`이며, 원 DX opcode가 DI를 거친다는 중간 명령을 명시했다. `26E8E0`은 버전 요청 한 callsite이며 모든 메시지가 지나는 별도 큐 entry가 아니다.
- 우선 16종의 default-instance를 향한 데이터→데이터 참조도 추가 조사했다. absolute64 참조 16개는 전부 compiled schema `+20` 포인터(예 PARTY `15F44F8→164CEF0`, ITEM_EXCHANGE `15F9910→164D360`)다. 해당 slot의 다음 데이터 포인터·code scalar RIP 소비·instance RVA32 literal은 0건이다. slot/slot+4 relative32 산술 후보17개(직전 zero padding12개 및 미결속 packed-data 후보5개)는 실제 참조로 결속하지 못했다. 임의 table-base/addend·계산 인덱싱은 미확인이다.
- **일반 채팅 PC 추가 결속:** PC RTTI/vptr `121D2D0`의 `+E8` slot `121D3B8→9B5370`. prefix 분석 `9B53F7→473A90`에서 일반0이 유지되어 `9B5754/9B575B→472380`, 기존 `4727CA/CE→472E2F..E40→481510→482280 Purple SendMessage`로 합류한다. 추가 caller `91A7BE EDX=0→91A7C3 CALL472380`의 UI 소속은 미확인이다. 근거는 [PC 함수 원문](../../local_server_rea_20261016/run392_chat_system_message/fn-9b5370.txt), 기존 [CHAT_EVIDENCE](CHAT_EVIDENCE.md)다. c822 carrier와 restored의 PC slot8B·PC 함수1207B·공통 함수2975B·Purple 함수3954B가 같은 것은 확인했지만 전체 artifact/현재 실행 동등성으로 확대하지 않는다.
- restored 6개 section 및 c822 carrier의 exact `CS_CHAT` 문자열과 `CHAT`을 포함한 CS RTTI 이름은 0건이다. 이름의 bounded negative이며 raw/간접 송신 opcode가 없다는 증명이 아니다. `4F2D`는 계속 귓속말 선검사다.

요청한 UI 영역의 **이미 결속된 opcode**도 함께 재사용한다. 미결속 85개 전체가 이 UI의 모든 요청이라는 뜻은 아니다.

| 영역 | 기존 결속 재사용 / 이번 잔여 |
|---|---|
| 채팅 | 일반0 game opcode UNKNOWN; `4F2D`는 귓속말 가능 여부 선검사 |
| 파티 | `08A4 CS_PARTY_CONTROL_REQ`, `08A6 CS_PARTY_LEAVE_REQ`; MEMBER_MARK_CHANGE는 UNKNOWN |
| 혈맹 | 선택 기능 `world_feature_pledge`: JOIN `0709`, CREATE `071B`, INFO `0722`, LEAVE `0715`, UPDATE_NOTICE `0727`, LIST `071E`를 계정 혈맹 저장에 연결. 기본 정보·구성원·공지의 LOCAL 표시 projection이며 native 전체 창은 미검증. 동맹/일부 notice·memo 등 11종 UNKNOWN. [PLEDGE](PLEDGE.md) |
| 거래 | ADD_ITEM `4EFA`, ASK `4EFB`, ACCEPT `4EFC`, CANCEL `4EFE`; 별도 ITEM_EXCHANGE 타입은 UNKNOWN |
| 상점·창고 | BUYSELL `4ED1`, HACTION `4ED4`, CLOSE_WAREHOUSE `097B`; 개인상점 `4E8E/4E8F/C357` |
| 마법·스킬 | `4EE6 CS_USE_SPELL_REQ`; 원 UI/전체 skill 의미와 응답 의무는 기존 범위 밖 |
| 펫 | COMMAND `4F02`, WAREHOUSE `4F09` |
| ATS | START `4F36`, FINISH `4F38`, TIME_CHECK `4F45` |
| 설정 | SAVE `4ED6`, SAVE_SERVER `4F3C`; GET/SET toggle·EQUIPSET은 UNKNOWN |

## 기억 요청의 추가 정적 근거

`4E4A ADD /4E4B UPDATE /4E4C DELETE /4F5F EXTENSION`의 기존 opcode·필드번호·타입을 보존했다. [BOOKMARK](BOOKMARK.md)에 공식50개·이름·저장 금지 장소의 확인 수준, L1J와의 차이, 원 SC 스키마와 native 소비자를 기록했다. ADD4E4D와 EXT_ACK4F60의 f1은 **최대 기억 수 표시값**으로 결속되며 성공코드0이 아니다. STORE는C371이고 별도 스키마로 repeated row를 수신한다. ADD/STORE child는 required u64/string/i32/i32/i32이며 key는 native map에서 low32로 보존된다. UPDATE/DELETE f2는 그 signed32 key의 sign-extension이다.

`4E41 CS_TELEPORT_REQ`를 기억 선택 요청으로 확정하지 않는다. 별도 선택 sender의0960 f8/f9/f10으로 되돌아오는 세 int 값은 child f3/f4/f5와 연결되지만 원래 map/x/y 순서명은 미확인이다. C371은 `BookmarkCrystalLayout` 소비자로 일반목록 refresh에 쓰지 않는다.

현재 ADD/UPDATE/DELETE는 선택 기능 `world_feature_bookmark.py`로 구현돼 JSON 해당 행을 `일부`로 바꿨다. 캐릭터별저장·4E4D 초기/추가 알림·native optimistic rename/delete·소유자 triple 대조 순간이동을 연결한다. 단위13개는 개발 검증이며, [최신조합socket결과](../runs/hunt-bookmark-nb9t5jqb/summary.json)는 정상FIRST/로그인/선택/월드2회·저장/재접속·수신된축복주문서UID의0960 사용/1개소비/위치저장27검사SUCCESS다. 두epoch 정상close/cleanup, source변경0을 확인했다. shared realm.py의 외부pledge저장필드 추가 뒤 재확인했고, 최초dlfpaync성공은 당시Source로 보존했다. alignment/monster_skills제외·LOCAL MapExp2 시험사본에 한정하며 원본native UI·출발지역제한은 미검증/미연결이다. C371은미송신,4F5F확장/4F60ACK는 비용·증가량미확인으로미지원,4E41좌표명령도미지원이다. [BOOKMARK](BOOKMARK.md)의 정확실행명령·Source/fixture·실패5개보존·LOCAL정책과 JSON 각 해당 요청의 `bookmark_analysis`를 함께 본다. 지도 전체 집계는 기존 정적 snapshot이며 이번 국소 구현 결과를 전체 완성률로 확대하지 않는다.

기억 2차는 위 1차 결과에 이어 `world_bookmark.py`의 명시적 LOCAL markable/escapable 정책으로 현재 지원 지역의 저장 금지·출발 탈출 제한을 연결했다. L1J `mapids`에서 map2는 저장 불가/탈출 가능, map37은 둘 다 불가이며, 누락 map은 UNKNOWN으로 거절한다. 슬롯4F5F/4F60은 비용·증가량·상한, 별도4E41은 명령 권한, 구슬12458/C371은 사용 params·구슬 내부 저장/소비 계약이 부족해 성공 처리를 추가하지 않았다. 소유 구슬 요청은 명시적으로 무소비 거절하며 일반 목록을 C371로 바꾸지 않는다. 신규 6개를 포함한 단위16개 OK; 최종 10배 시간 설정 직접 패킷 [기본30검사](../runs/hunt-bookmark-j2fhl7qv/summary.json)·[map2 9검사](../runs/hunt-bookmark-79h1p1_y/summary.json)·[map37 5검사](../runs/hunt-bookmark-2qcc206f/summary.json)가 각각 SUCCESS, 정상 close/cleanup·handler/hook 오류0·실행 중 Source 변경0이다. 지역 시험은 fresh pre-FIRST 시작 저장의 해당 행동만 판정하며 원본 UI/입력·던전 도달·공성 런타임·확장/좌표/구슬 정상 사용은 미검증이다. 정확 출처·추가 정적 RVA·부족 입력·실패 보존·재실행 명령은 [BOOKMARK의 2차 절](BOOKMARK.md#2차-출발-지역-제한과-미지원-계약의-무부작용-거절)에 있다. 기존 JSON 정적 snapshot과 전체 집계는 수정하지 않았다.

## 혈맹 기본의 국소 구현

[PLEDGE](PLEDGE.md)에 공식 미가입 군주·레벨5·1000아데나, L1J와 다른 점, 저장 실패 후 같은 CREATE 재요청의 비용 중복 방지, 같은 계정의 오프라인 캐릭터 가입, 동료 표시의 다음 단계를 기록했다. 동료 파일은 수정하지 않았다. SC 스키마7종·DTO2종·43필드와 필요한 원본 소비를 [pledge-evidence](pledge-evidence/consumer-contracts.json)에 보존한다.

서버는 CREATE·JOIN·INFO·LEAVE(군주는 해산)·NOTICE·LIST를 선택 기능으로 처리한다. `0723`의 혈맹 문자열/공지와 `0724`의 단일 페이지 `(1,0)`를 제공하며 구성원 이름·실제 저장UID는 명시적 LOCAL projection이다. 확인하지 못한 군주명·계급·직업·레벨 필드는 임의 enum으로 채우지 않는다. LIST 검색도 LOCAL 부분문자열 정책이며 원 UI 검색 의미 확정이 아니다. 저장 선택 필드와 소켓 시험 결과·명령·미확인은 PLEDGE에 마감한다.

이 보완은 초기 전수 지도 이후의 국소 구현이다. 위 전수 집계·opcode 미결속85개를 전체 최신 완성률로 해석하지 않는다. 혈맹 기본만으로 806 귀환의 성/아지트 목적지나15400/15410 오만 주문서의 입장·이동 소비 계약을 만들어내지 않으며 세 아이템은 무소비 미지원으로 유지한다.

## 원본으로 확인할 것 / 미확인

1. opcode 미결속 요청의 실제 sender/등록을 연결한다. 타입이 남아 있다는 사실만으로 현재 UI에서 발신 가능하다고 판정하지 않는다.
2. 연속·원거리 공격의 실제 발신 여부와 자동 반복 입력, 일반 채팅의 PURPLE 없는 전달 계약을 확인한다.
3. 각 UI/키→정확한 요청값·조건과 S→C 응답 순서/필수 여부를 연결한다. 이름 후보 ACK를 정답으로 사용하지 않는다.
4. `required:null`, 원래 필드명, enum 의미·단위·문자 인코딩·닫히지 않은 문자열/string-vs-bytes 의미를 확인한다.
5. 현재 disk 클라이언트와 이 carrier의 버전·패치 결속, 실제 입력·화면·저장·정리 동작은 이번 조사에서 미확인이다.

## 검증

- 기존 `$env:TEMP/validate_request_map.py`는 bound 고정 기대값 135만 메모리에서 136으로 맞춰 재사용했다. JSON·221행/28중첩·136개 opcode 유일성·571필드·nested 참조 검사는 통과했으나 handler 참조 503곳 중 **기존 9곳의 현재 파일 줄 범위가 유효하지 않아 최종 assertion은 실패**했다. 같은 9곳은 수정 전 baseline에도 있으며 이번 추가 5곳은 정상이다. 기존 행/스키마/필드/중첩 구조 보존과 신규 결속 정합은 별도 확인했다. 이번 실행을 `VALIDATION_OK`로 표시하지 않는다.
- 제품 테스트·게임 실행은 요청에 따라 수행하지 않았다. 기존 성공을 이번 정적 지도 전체의 PASS로 사용하지 않는다.

- 이번 재시도 검증: 기존 TEMP `validate_request_map.py`의 bound 기대값만 136으로 맞춰 재사용했다. 221행/28중첩/571필드·opcode 유일성·nested 연결은 통과했고, 기존 handler 참조 9곳의 줄 범위 오류로 최종 assertion은 실패했다. 변경 전후 opcode/필드/schema/server 및 통계는 그대로이며, 85행의 새 조사 근거와 PC 경로만 보강했다. 제품 코드·원본 클라이언트/서버 실행·커밋은 없다.

## 원본 응답 체크리스트 (1차 · 2026-10-29)

22개 동작·70개 응답 하위행을 정적 대조했다. **L1J는 별도 backend 참고 구현이며 확보한 공식 26.09.29.2001 서버의 실제 응답 묶음·필수 순서라는 증거가 아니다.** 초기 지도에 적힌 L1J 조회 0%는 초기 요청 추출의 이력이며 이 절은 새 L1J 대조다.

보냄은 선택 경로의 큐·송신 연결 확인이다. 안 보냄은 적은 recipient·기본 설정·handler 범위에 한정한다. 대응 미확인은 opcode/의미/필수성 근거 부족이며 미송신에 합산하지 않는다. 기본 gate off는 안 보냄으로 적고 on일 때의 송신은 비고에 구분했다. 창고 등 선택 구성의 보냄도 해당 gate 범위에 한정한다. **1차는 정적 대조였고, 2026-10-29 후속에서 서버 recipient 연결 6행과 개발 시험을 추가했다. 게임·포트·스크린샷·커밋 없음. 화면 확인분은 0개이며 기존 사이드 항목의 최종 완료 기준은 미달이다.**

현재 dirty working tree를 읽었다. 다른 writer의 후속 변경은 포함하지 않으며 파일:줄은 조사/마감 읽기 시점 기준이다. 고정 Source 정식 PASS나 전체 원본 동등성으로 확대하지 않는다.

### 근거 경로와 실제 송신의 경계

| 약어 | 경로 |
|---|---|
| J/ | D:/SingleLineageRef/l1j-en-classic/src/l1j/server/server/ |
| T/ | tools/local_original_session/ |
| R/ | work/local_server_rea_20261016/ |
| E/ | work/local_original_session/game-core-prep/ |

모든 아래 근거는 파일:줄이다. 같은 줄에서 시작하는 함수·조건 분기를 함께 읽는다. 현대 opcode 의미는 해당 encoder/기존 REA를 근거로 한 **역할 대응**이며 L1J opcode 숫자를 복사한 것이 아니다. 공통 월드 송신은 ［T/world_core_session.py:23］ _world_send→:26 self.send, 큐 flush는 :118→:126, 최종 transport는 ［T/broker.py:1899］ writer.write→:1901 drain이다. 각 행동의 큐/직접 send 호출은 하위행에 별도로 적었다.

### 동작별 요약

동작 전체에 한 가지 완료 판정을 붙이지 않는다. 숫자는 아래 하위행의 상태 개수이며 기능 완성률이 아니다.

| ID | 동작 | 보냄 | 안 보냄 | 대응 미확인 |
|---|---|---:|---:|---:|
| R01 | 이동 | 2 | 0 | 1 |
| R02 | 근접 공격 | 2 | 0 | 1 |
| R03 | 피격 | 2 | 0 | 1 |
| R04 | 사망 | 3 | 0 | 0 |
| R05 | 재시작·죽음 버튼 | 1 | 0 | 2 |
| R06 | 줍기 | 3 | 0 | 1 |
| R07 | 버리기 | 2 | 1 | 0 |
| R08 | 물약(회복·가속·용기·기타 지속) | 5 | 1 | 1 |
| R09 | 주문서(인챈트·감정·저주해제) | 1 | 1 | 1 |
| R10 | 귀환 주문서 | 1 | 0 | 1 |
| R11 | 순간이동 주문서 | 1 | 0 | 1 |
| R12 | 부활 아이템 | 1 | 1 | 0 |
| R13 | 장비 착용 | 3 | 0 | 0 |
| R14 | 장비 해제 | 3 | 0 | 0 |
| R15 | 마법 시전(자기 Heal/Shield) | 2 | 3 | 0 |
| R16 | 마법 시전(대상 Heal·공격) | 2 | 1 | 1 |
| R17 | 상점 구매 | 2 | 1 | 1 |
| R18 | 상점 판매 | 2 | 0 | 1 |
| R19 | 창고 맡김·찾기 | 2 | 0 | 1 |
| R20 | 파티 | 1 | 1 | 0 |
| R21 | 일반·파티 채팅 | 1 | 1 | 0 |
| R22 | 레벨업 | 2 | 1 | 0 |

### 응답 신호별 대조

현재 이미 존재하는 **줍기 4E39 get15**, **물약 4ED8**, **지원 물약 4E91 기간/만료**를 과거 누락으로 재등록하지 않았다. 근거는 R06/R08에 있다. 마법의 별도 실험 gate와 물약의 지원 catalog를 혼동하지 않는다.

#### R01 이동

| 응답·수신자 | L1J C_*→callee→S_* 근거 | 현대 대응·우리 송신 근거 | 판정·범위 |
|---|---|---|---|
| R01.1 S_MoveCharPacket → 주변 | ［J/clientpackets/C_MoveChar.java:125］<br>［J/model/L1Character.java:136］ | 4E2C<br>［T/world_core_session.py:106］<br>［T/world_core_maps.py:141］<br>［T/world_visibility.py:358］<br>［T/world_visibility.py:480］<br>［T/world_visibility.py:527］ | **보냄** · realm의 완전한 self Actor DTO를 pc_actors에 등록하고 별도 pc_known으로 상호 소개/화면 경계/맵 전이/퇴장을 연결. 기존에 보던 같은 맵 PC에만 정상 한 칸 이동의 pre-step 4E2C를 큐에 넣고 새 recipient에는 최종 Actor를 보냄. self 정상 ACK 추가 없음. 운영 broker 단일 PC 제한은 유지하므로 다중 PC는 개발 시험 범위. |
| R01.2 L1Teleport 경유 보정 → 본인 | ［J/clientpackets/C_MoveChar.java:80］ | 4EE0<br>［T/movement.py:61］<br>［T/movement.py:397］<br>［T/world_handlers.py:303］ | **보냄** · blocked/stale LOCAL correction. L1J 속도초과 teleport와 일대일 동등성은 미확인. 원 소비 R/run389_same_map_teleport/findings.md:17 |
| R01.3 S_MoveCharPacket(findinvis) → 조건부 주변 | ［J/clientpackets/C_MoveChar.java:121］<br>［J/model/L1Character.java:150］ | 대응 opcode 미확인<br>［T/world_visibility.py:419］ | **대응 미확인** · GM/ghost/invis recipient 분기 전수 대조 안 함 |

#### R02 근접 공격

| 응답·수신자 | L1J C_*→callee→S_* 근거 | 현대 대응·우리 송신 근거 | 판정·범위 |
|---|---|---|---|
| R02.1 S_AttackPacket / S_AttackMissPacket → 본인+주변 | ［J/clientpackets/C_Attack.java:124］<br>［J/model/Instance/L1MonsterInstance.java:247］<br>［J/model/L1Attack.java:1302］<br>［J/model/L1Attack.java:1306］ | 4E31<br>［T/world_visibility.py:689］<br>［T/world_visibility.py:693］<br>［T/world_core_session.py:203］ | **보냄** · 명중 raw positive/빗나감0. R/run24_normal_attack/findings.md:46. f4를 공식 피해량으로 확정하지 않음 |
| R02.2 S_DoActionGFX(ACTION_Damage) → target 주변 중 추가 수신자 | ［J/model/L1Attack.java:1313］ | 4E31 target-effect 결합<br>［T/world_visibility.py:693］ | **보냄** · 별도 4E39 부재를 피격 누락으로 세지 않음. 현대 DamagedAction 근거 R/run94_player_hit_status/findings.md:30. L1J의 attacker 시야 밖 recipient까지 동등한지는 미확인 |
| R02.3 S_ServerMessage(110) / 허공 S_AttackPacket → 본인 / 본인+주변 | ［J/clientpackets/C_Attack.java:68］<br>［J/clientpackets/C_Attack.java:125］ | 대응 opcode 미확인<br>［T/world_visibility.py:656］<br>［T/world_core_session.py:205］ | **대응 미확인** · 과중량 안내·UID0·fallback attack-session 전체 미조사 |

#### R03 피격

| 응답·수신자 | L1J C_*→callee→S_* 근거 | 현대 대응·우리 송신 근거 | 판정·범위 |
|---|---|---|---|
| R03.1 S_AttackPacketForNpc / S_AttackMissPacket / S_UseAttackSkill → NPC 주변(피격 본인 포함) | ［J/model/L1Attack.java:1319］<br>［J/model/L1Attack.java:1361］ | 4E31<br>［T/world_visibility.py:589］<br>［T/world_visibility.py:603］ | **보냄** · 일반 NPC attack. 원 소비 R/run94_player_hit_status/findings.md:13. 장거리·모든 gfx 분기 동일성은 미확인 |
| R03.2 S_HPUpdate → 본인 | ［J/model/L1Attack.java:1438］<br>［J/model/Instance/L1PcInstance.java:2388］<br>［J/model/Instance/L1PcInstance.java:2796］ | 4E38 f10/f11<br>［T/world_visibility.py:606］<br>［T/world_combat.py:371］<br>［T/world_combat.py:615］ | **보냄** · 원 소비 R/run102_own_player_death_recovery/findings.md:11 |
| R03.3 S_HPMeter → 파티 | ［J/model/Instance/L1PcInstance.java:2798］<br>［J/model/L1Party.java:121］ | 대응 opcode 미확인<br>［T/world_visibility.py:589］<br>［T/world_feature_companion.py:1965］ | **대응 미확인** · 동료 owner 08A3은 존재하나 일반 PC 파티 HP 방송과 동일하지 않음. 4EC8 NPC HP바로 대체 금지 |

#### R04 사망

| 응답·수신자 | L1J C_*→callee→S_* 근거 | 현대 대응·우리 송신 근거 | 판정·범위 |
|---|---|---|---|
| R04.1 S_HPUpdate + S_DoActionGFX(ACTION_Die) → 본인 | ［J/model/Instance/L1PcInstance.java:208］<br>［J/model/Instance/L1PcInstance.java:244］ | 4E38 HP0 + 4E39 raw8<br>［T/world_visibility.py:606］<br>［T/world_visibility.py:535］<br>［T/player_life_codec.py:29］ | **보냄** · HP0과 죽음 동작 별도. 원 소비 R/run102_own_player_death_recovery/findings.md:11 |
| R04.2 S_DoActionGFX(ACTION_Die) → 주변 PC | ［J/model/Instance/L1PcInstance.java:244］ | 4E39 raw8<br>［T/world_visibility.py:640］<br>［T/world_visibility.py:647］ | **보냄** · 기존 HP0/자기 raw8 순서를 유지하고 같은 death wire를 pc_known의 주변 PC에 큐. out-of-view/다른 맵에는 미송신. 다중 WorldView 개발 시험 통과; 운영 단일 PC 제한 유지, 원본 화면 미확인. |
| R04.3 S_Exp / S_OwnCharStatus(levelDown 경유) → 본인 | ［J/model/Instance/L1PcInstance.java:252］<br>［J/model/Instance/L1PcInstance.java:1261］<br>［J/model/Instance/L1PcInstance.java:2196］ | 4E38 level/EXP<br>［T/world_core_life.py:15］<br>［T/world_core_life.py:28］ | **보냄** · LOCAL 사망 패널티 반영. 공식 손실 수식·PK/duel/아이템 손실 분기는 미확인 |

#### R05 재시작·죽음 버튼

| 응답·수신자 | L1J C_*→callee→S_* 근거 | 현대 대응·우리 송신 근거 | 판정·범위 |
|---|---|---|---|
| R05.1 S_MapID / S_OwnCharPack / S_CharVisualUpdate / S_Weather / S_OtherCharPacks → 본인+주변, 패킷별 다름 | ［J/clientpackets/C_Restart.java:58］<br>［J/clientpackets/C_Restart.java:75］ | 대응 opcode 미확인<br>［T/world_core_life.py:90］<br>［T/world_core_lifecycle.py:641］ | **대응 미확인** · L1J C_Restart는 죽음→월드 복귀. 현대 4E33→4E3B 선택화면 전환과 다름. 현대 restart ACK는 restart.py:22 및 world_core_lifecycle.py:650에서 보냄. R/run34_cs4e33/findings.md:7 |
| R05.2 부활 복원에 대응하는 현대 응답 → 본인 | ［J/clientpackets/C_Restart.java:58］ | 4EED / 4F16 / 4E38<br>［T/broker.py:675］<br>［T/player_life.py:326］<br>［T/player_life.py:343］ | **보냄** · player-life 구성의 4EEC ACK와 recover는 별도 단계. world-only 4EEC는 선택화면 복귀 구성. R/run102_own_player_death_recovery/findings.md:13. 동일 월드 부활 PASS로 합산 금지 |
| R05.3 S_ServerMessage(77) / S_SkillSound(830) / S_HPUpdate / S_MPUpdate → 본인(초보맵 조건) | ［J/clientpackets/C_Restart.java:81］<br>［J/clientpackets/C_Restart.java:88］ | 대응 opcode 미확인<br>［T/world_core_life.py:90］ | **대응 미확인** · map68/69 refill 분기. 현대 버튼 구성부터 다르므로 필수 누락으로 확정하지 않음 |

#### R06 줍기

| 응답·수신자 | L1J C_*→callee→S_* 근거 | 현대 대응·우리 송신 근거 | 판정·범위 |
|---|---|---|---|
| R06.1 S_AddItem / S_ItemAmount / S_ItemStatus / S_ItemName → 본인 | ［J/clientpackets/C_PickUpItem.java:156］<br>［J/model/L1PcInventory.java:179］<br>［J/model/L1PcInventory.java:246］ | 0964 / 0965<br>［T/world_core_reward.py:54］<br>［T/world_core_reward.py:105］<br>［T/inventory_update.py:27］ | **보냄** · 신규/합산 재고. L1J와 현대 packet 경계는 1:1 아님 |
| R06.2 S_RemoveObject → 물건이 보이는 PC | ［J/model/L1GroundInventory.java:112］ | 4E40<br>［T/world_visibility.py:376］<br>［T/world_visibility.py:382］<br>［T/world_visibility.py:409］ | **보냄** · 최종 전량 pickup 지상 제거. 부분 잔량 표시 동등성은 미확인 |
| R06.3 S_AttackPacket(ACTION_Pickup) → 본인+주변 | ［J/clientpackets/C_PickUpItem.java:179］<br>［J/clientpackets/C_PickUpItem.java:182］ | 4E39 selector15<br>［T/world_visibility.py:121］<br>［T/world_visibility.py:131］<br>［T/world_visibility.py:410］<br>［T/world_core_reward.py:105］ | **보냄** · 현재 이미 구현. generic ACTION의 get15 적용은 LOCAL 선택; native admission/렌더 미관측은 함수 주석에 명시 |
| R06.4 S_PacketBox(WEIGHT) → 본인 | ［J/model/L1PcInventory.java:181］ | 대응 opcode 미확인<br>［T/world_core_stats.py:96］ | **대응 미확인** · 무게 계산 존재만으로 pickup 직후 대응 wire 확인 아님 |

#### R07 버리기

| 응답·수신자 | L1J C_*→callee→S_* 근거 | 현대 대응·우리 송신 근거 | 판정·범위 |
|---|---|---|---|
| R07.1 S_DeleteInventoryItem → 본인 | ［J/clientpackets/C_DropItem.java:170］<br>［J/model/L1PcInventory.java:414］ | 0978<br>［T/item_transfer_session.py:391］<br>［T/item_transfer_session.py:412］<br>［T/item_transfer_protocol.py:39］ | **보냄** · 같은 선택 whole unequipped B만 허용하는 sibling transfer 범위(item_ground.py:232). 일반 부분 스택 drop 전체 지원 아님 |
| R07.2 S_DropItem → 본인 | ［J/model/L1GroundInventory.java:94］ | 4E96 ground Actor 후보<br>［T/item_ground_wire.py:43］<br>［T/item_ground.py:241］<br>［T/item_transfer_session.py:394］<br>［T/item_transfer_session.py:412］ | **보냄** · LOCAL 지상 actor 투영. 원본 드롭 전체 동등성 미확인 |
| R07.3 S_DropItem → 주변 PC | ［J/model/L1GroundInventory.java:94］ | 4E96 ground Actor 후보<br>［T/item_transfer_session.py:391］<br>［T/item_transfer_session.py:413］ | **안 보냄** · sibling whole-item drop만 여전히 안 보냄. item_transfer_session.handle의 custody 저장→정확 wire drain→registry.complete는 독립 GroundRegistry/단일 generation에 결속하고 world ground EntityRef/item_known 및 recipient 결속이 없음. 기존 수명을 우회해 WorldView에 복제하면 pickup/실패/퇴장 시 이중 소유가 생김. world registry로 정식 이관하는 저장/회수 계약을 함께 마련해야 하며 이번에는 미수정. |

#### R08 물약(회복·가속·용기·기타 지속)

| 응답·수신자 | L1J C_*→callee→S_* 근거 | 현대 대응·우리 송신 근거 | 판정·범위 |
|---|---|---|---|
| R08.1 S_SkillSound + S_ItemAmount / S_DeleteInventoryItem → 본인 | ［J/clientpackets/C_ItemUSe.java:2701］<br>［J/clientpackets/C_ItemUSe.java:2744］<br>［J/clientpackets/C_ItemUSe.java:2952］<br>［J/clientpackets/C_ItemUSe.java:409］<br>［J/model/L1PcInventory.java:246］<br>［J/model/L1PcInventory.java:414］ | 4ED8 + 0965/0978<br>［T/world_status_frames.py:71］<br>［T/world_feature_items.py:354］<br>［T/world_feature_items.py:371］<br>［T/world_feature_items.py:395］<br>［T/world_feature_items.py:398］<br>［T/world_core_kit.py:54］ | **보냄** · 현재 사용 효과 있음. heal·buff 지원 template 범위 |
| R08.2 S_HPUpdate → 본인 | ［J/clientpackets/C_ItemUSe.java:2707］<br>［J/model/Instance/L1PcInstance.java:2796］ | 4E38<br>［T/world_combat.py:371］<br>［T/world_feature_items.py:364］<br>［T/world_feature_items.py:371］ | **보냄** · 회복 후 full status. 회복 효과와 별개 |
| R08.3 S_SkillHaste / S_SkillBrave / S_SkillIconGFX / S_SkillIconWisdomPotion / S_SkillIconBlessOfEva → 본인 | ［J/clientpackets/C_ItemUSe.java:2796］<br>［J/clientpackets/C_ItemUSe.java:2898］<br>［J/clientpackets/C_ItemUSe.java:2951］<br>［J/clientpackets/C_ItemUSe.java:2979］<br>［J/clientpackets/C_ItemUSe.java:3006］ | 4E5B + 4E91<br>［T/world_feature_items.py:386］<br>［T/world_feature_items.py:388］<br>［T/world_feature_items.py:398］<br>［T/world_item_effects.py:330］<br>［T/world_item_effects.py:456］<br>［T/world_item_effects.py:500］<br>［T/world_item_effects.py:1063］ | **보냄** · 지원 catalog의 속도·기간 upsert와 만료 remove. 마법 buff UI gate와 혼동 금지 |
| R08.4 S_SkillSound → 주변 PC | ［J/clientpackets/C_ItemUSe.java:2701］<br>［J/clientpackets/C_ItemUSe.java:2745］ | 4ED8<br>［T/world_feature_items.py:342］<br>［T/world_feature_items.py:367］<br>［T/world_feature_items.py:395］<br>［T/world_item_effects.py:1056］<br>［T/world_visibility.py:346］ | **보냄** · 기존 사용/저장 성공 이후 세 물약 lane과 durable consumable lane에서 4ED8만 현재 pc_known recipient에 전달. HP/재고/4E91 HUD는 본인에만 유지. 거절/저장 실패 전에는 방송하지 않음. 다중 PC 개발 시험 범위. |
| R08.5 S_SkillHaste / S_SkillBrave → 주변 PC | ［J/clientpackets/C_ItemUSe.java:2797］<br>［J/clientpackets/C_ItemUSe.java:2899］ | 4E5B<br>［T/world_feature_items.py:395］<br>［T/world_visibility.py:369］<br>［T/world_visibility.py:631］ | **보냄** · 적용 성공한 4E5B와 실제 만료 reset을 pc_known 주변에 전달. 새로 보이는 PC에는 현재 유효 속도를 소개 뒤 보냄. 소모/중첩/기간/아이콘 정책은 기존 값 그대로. 다중 PC 개발 시험 범위. |
| R08.6 S_HPMeter / poison 표시 → 파티 / 본인·주변 | ［J/model/Instance/L1PcInstance.java:2798］<br>［J/model/L1Party.java:121］<br>［J/clientpackets/C_ItemUSe.java:476］ | 대응 opcode 미확인<br>［T/world_feature_items.py:371］<br>［T/world_item_effects.py:655］ | **대응 미확인** · 독해제 use sound는 존재; 독 상태 표시 및 일반 파티 HP 대응 별도 |
| R08.7 S_ServerMessage(77/1007) → 본인 | ［J/clientpackets/C_ItemUSe.java:2703］<br>［J/clientpackets/C_ItemUSe.java:2956］ | 4EEA 코드문구 계열 후보<br>［T/world_feature_items.py:354］<br>［T/world_feature_items.py:398］ | **안 보냄** · 이 반환 묶음에는 해당 문구 없음. 77은 옵션. 현대 번호 동일성 미확인; 일반 수신 근거 E/CHAT_EVIDENCE.md:63 |

#### R09 주문서(인챈트·감정·저주해제)

| 응답·수신자 | L1J C_*→callee→S_* 근거 | 현대 대응·우리 송신 근거 | 판정·범위 |
|---|---|---|---|
| R09.1 S_ItemAmount / S_ItemName / S_DeleteInventoryItem / S_OwnCharStatus / S_SPMR → 본인 | ［J/clientpackets/C_ItemUSe.java:319］<br>［J/model/Enchant.java:439］<br>［J/model/Enchant.java:493］<br>［J/model/Enchant.java:295］ | 0965 / 0978 / 4E38 (+097A)<br>［T/world_enchant_inventory.py:206］<br>［T/world_feature_items.py:88］<br>［T/world_feature_items.py:95］<br>［T/world_feature_items.py:98］ | **보냄** · 소비/이름/파괴·능력 갱신. 재고 변화가 결과 안내를 대신하지 않음 |
| R09.2 S_ServerMessage(160/161/164) → 본인 | ［J/model/Enchant.java:220］<br>［J/model/Enchant.java:263］<br>［J/model/Enchant.java:445］ | 4EEA 안내 계열 / 0967 별도 결과 후보<br>［T/world_enchant_inventory.py:137］<br>［T/world_feature_items.py:65］<br>［T/world_feature_items.py:95］ | **안 보냄** · 기본 experiment=None이면 0967 없음. L1J 결과 안내문도 이 send 묶음에 없음. 현대 문구 ID 미확인. 첫 부족 입력은 0967 event17F9940의 실제 callback RVA와 required f1..5 의미·성공/실패 enum. ［R/run393_item_target_use/source-index.json:377］ |
| R09.3 S_IdentifyDesc / S_ItemStatus / S_ItemColor / S_ServerMessage(155) → 본인 | ［J/clientpackets/C_ItemUSe.java:620］<br>［J/clientpackets/C_ItemUSe.java:614］<br>［J/clientpackets/C_ItemUSe.java:619］ | 0965 label 투영만 확인<br>［T/world_item_effects.py:874］<br>［T/world_item_effects.py:903］<br>［T/world_item_effects.py:1050］<br>［T/world_item_effects.py:1063］ | **대응 미확인** · 감정·저주해제 소비/재고 송신은 존재. 상세 감정창·공식 color/template·155 안내와 동일한 대응은 미확인; 155 문구는 이 반환에 없음 |

#### R10 귀환 주문서

| 응답·수신자 | L1J C_*→callee→S_* 근거 | 현대 대응·우리 송신 근거 | 판정·범위 |
|---|---|---|---|
| R10.1 S_ItemAmount / S_DeleteInventoryItem + teleport 이동 → 본인 | ［J/clientpackets/C_ItemUSe.java:1123］<br>［J/clientpackets/C_ItemUSe.java:1128］<br>［J/model/L1Teleport.java:72］<br>［J/model/L1PcInventory.java:246］<br>［J/model/L1PcInventory.java:414］ | 0965/0978 + 4EE0 또는 map reset/Actor<br>［T/world_feature_items.py:315］<br>［T/world_feature_items.py:342］<br>［T/world_feature_items.py:350］<br>［T/world_core_maps.py:165］<br>［T/world_core_maps.py:215］ | **보냄** · LOCAL relocation·선택 구성의 송신. 4EE0이 검증된 공식 teleport 생산자라는 뜻 아님 |
| R10.2 S_Paralysis / S_SkillSound → 본인 / 본인+주변 | ［J/model/L1Teleport.java:72］<br>［J/model/L1Teleport.java:75］ | 대응 opcode 미확인<br>［T/world_core_maps.py:167］<br>［T/world_core_maps.py:241］<br>［T/world_item_effects.py:299］ | **대응 미확인** · 잠금해제·sound·지연 순서 미결속. 다른 물약의 4ED8 존재를 귀환 sound로 확대하지 않음 |

#### R11 순간이동 주문서

| 응답·수신자 | L1J C_*→callee→S_* 근거 | 현대 대응·우리 송신 근거 | 판정·범위 |
|---|---|---|---|
| R11.1 S_ItemAmount / S_DeleteInventoryItem + S_MapID / S_OtherCharPacks / S_OwnCharPack / S_CharVisualUpdate → 본인+주변(패킷별 다름) | ［J/clientpackets/C_ItemUSe.java:1188］<br>［J/utils/Teleportation.java:101］<br>［J/utils/Teleportation.java:108］<br>［J/utils/Teleportation.java:112］<br>［J/utils/Teleportation.java:116］<br>［J/model/L1PcInventory.java:246］<br>［J/model/L1PcInventory.java:414］ | 0965/0978 + 4EE0 또는 4E95/4E38/4E96<br>［T/world_feature_items.py:315］<br>［T/world_feature_items.py:350］<br>［T/world_core_maps.py:215］<br>［T/world_core_maps.py:245］ | **보냄** · 일반 random LOCAL 이동. map f2=0·순서는 원본 미확인. bookmark/혈맹 동반 분기 전수 아님 |
| R11.2 S_Paralysis / S_SkillSound 및 혈맹 동반 → 본인+조건부 혈맹원 | ［J/model/L1Teleport.java:72］<br>［J/model/L1Teleport.java:75］<br>［J/clientpackets/C_ItemUSe.java:1201］ | 대응 opcode 미확인<br>［T/world_core_maps.py:167］<br>［T/world_item_effects.py:299］ | **대응 미확인** · 귀환과 같은 teleport 신호 미결속. 동반/모든 bookmark 분기는 이번 1차 미검토 |

#### R12 부활 아이템

| 응답·수신자 | L1J C_*→callee→S_* 근거 | 현대 대응·우리 송신 근거 | 판정·범위 |
|---|---|---|---|
| R12.1 S_Message_YN(321/322) → 동의 후 S_Resurrection → 대상 PC / 대상+주변 | ［J/clientpackets/C_ItemUSe.java:985］<br>［J/clientpackets/C_ItemUSe.java:991］<br>［J/clientpackets/C_Attr.java:238］<br>［J/clientpackets/C_Attr.java:262］ | 대응 opcode 미확인<br>［T/world_feature_companion.py:55］<br>［T/world_feature_companion.py:88］ | **안 보냄** · 현재 owned companion 한정; PC 동의/승인 부활 경로 없음. 현대 Y/N·공식 부활 packet 일대일 대응은 미확인 |
| R12.2 S_RemoveObject + updateObject(NPC resurrect) + S_ItemAmount / S_DeleteInventoryItem → 주변 | ［J/clientpackets/C_ItemUSe.java:1015］<br>［J/model/L1Character.java:59］<br>［J/clientpackets/C_ItemUSe.java:1028］<br>［J/model/L1PcInventory.java:246］<br>［J/model/L1PcInventory.java:414］ | 4E96 재표시 / 실험 4F16 + 0965/0978<br>［T/world_feature_companion.py:41］<br>［T/world_feature_companion.py:98］<br>［T/world_feature_companion.py:1073］<br>［T/world_feature_companion.py:1137］ | **보냄** · 동료 소비·watchers 큐. 기본은 동일UID Actor 재표시. 실험 4F16을 기본 송신으로 표시하지 않음 |

#### R13 장비 착용

| 응답·수신자 | L1J C_*→callee→S_* 근거 | 현대 대응·우리 송신 근거 | 판정·범위 |
|---|---|---|---|
| R13.1 S_ItemName + S_HPUpdate/S_MPUpdate/S_OwnCharStatus/S_OwnCharAttrDef/S_SPMR → 본인 | ［J/model/L1PcInventory.java:448］<br>［J/model/L1PcInventory.java:450］<br>［J/clientpackets/C_ItemUSe.java:3368］ | 097A + 4E38<br>［T/equipment_change.py:11］<br>［T/item_equipment_effect.py:436］<br>［T/item_equipment_effect.py:455］<br>［T/world_core_stats.py:181］ | **보냄** · 장착 표시·능력치 투영. 각 L1J packet과 현대 1:1 동일성 미확인 |
| R13.2 S_CharVisualUpdate → 본인 | ［J/model/L1PcInventory.java:453］ | 4E96 self Actor<br>［T/item_equipment_effect.py:456］<br>［T/world_core_kit.py:112］<br>［T/world_core_kit.py:129］ | **보냄** · 무기 외형 변동 때 self refresh; 불변이면 생략 |
| R13.3 S_CharVisualUpdate → 주변 | ［J/model/L1PcInventory.java:454］ | Actor 외형 갱신 후보<br>［T/item_equipment_effect.py:455］<br>［T/world_core_kit.py:129］<br>［T/world_core_kit.py:131］<br>［T/world_visibility.py:335］ | **보냄** · 기존 저장/097A와 self Actor drain 후 publish_pc_actor가 같은 완전한 DTO를 pc_known 주변에 전달. 외형 불변이면 self/peer 모두 생략. 다중 PC 개발 시험 범위; 원본 렌더 미확인. |

#### R14 장비 해제

| 응답·수신자 | L1J C_*→callee→S_* 근거 | 현대 대응·우리 송신 근거 | 판정·범위 |
|---|---|---|---|
| R14.1 S_ItemName + S_HPUpdate/S_MPUpdate/S_OwnCharStatus/S_OwnCharAttrDef/S_SPMR → 본인 | ［J/model/L1PcInventory.java:448］<br>［J/model/L1PcInventory.java:450］<br>［J/clientpackets/C_ItemUSe.java:3368］<br>［J/clientpackets/C_ItemUSe.java:3399］ | 097A + 4E38<br>［T/equipment_change.py:11］<br>［T/item_equipment_effect.py:436］<br>［T/item_equipment_effect.py:455］<br>［T/world_core_stats.py:181］ | **보냄** · 장착 표시·능력치 투영. 각 L1J packet과 현대 1:1 동일성 미확인; 동일 toggle 경로의 equipped=False |
| R14.2 S_CharVisualUpdate → 본인 | ［J/model/L1PcInventory.java:453］<br>［J/clientpackets/C_ItemUSe.java:3399］ | 4E96 self Actor<br>［T/item_equipment_effect.py:456］<br>［T/world_core_kit.py:112］<br>［T/world_core_kit.py:129］ | **보냄** · 무기 외형 변동 때 self refresh; 불변이면 생략; 동일 toggle 경로의 equipped=False |
| R14.3 S_CharVisualUpdate → 주변 | ［J/model/L1PcInventory.java:454］<br>［J/clientpackets/C_ItemUSe.java:3399］ | Actor 외형 갱신 후보<br>［T/item_equipment_effect.py:455］<br>［T/world_core_kit.py:129］<br>［T/world_core_kit.py:131］<br>［T/world_visibility.py:335］ | **보냄** · R13.3과 같은 장착 toggle 경로. 해제 후 self Actor drain 다음 완전한 DTO를 pc_known 주변에 전달. 외형 불변이면 생략. 다중 PC 개발 시험 범위; 원본 렌더 미확인. |

#### R15 마법 시전(자기 Heal/Shield)

| 응답·수신자 | L1J C_*→callee→S_* 근거 | 현대 대응·우리 송신 근거 | 판정·범위 |
|---|---|---|---|
| R15.1 S_HPUpdate / S_MPUpdate → 본인 | ［J/clientpackets/C_UseSkill.java:184］<br>［J/model/skill/L1SkillUse.java:1121］<br>［J/model/skill/L1SkillUse.java:1137］<br>［J/model/skill/L1SkillUse.java:1140］<br>［J/model/Instance/L1PcInstance.java:2796］<br>［J/model/Instance/L1PcInstance.java:2812］ | 4E38 f10..13<br>［T/world_feature_magic.py:979］<br>［T/world_feature_magic.py:1135］<br>［T/world_feature_magic.py:1145］<br>［T/world_feature_magic.py:1236］ | **보냄** · HP/MP 비용·Heal. 원 소비 E/PLAYER_MAGIC_EVIDENCE.md:83 |
| R15.2 S_DoActionGFX(시전) → 본인+주변 | ［J/model/skill/L1SkillUse.java:1428］<br>［J/model/skill/L1SkillUse.java:1429］ | 기존 4E31 f1..5/f13=true<br>［T/world_feature_magic.py:_world_magic_display］ | **기본 보냄** · 사용자 승인 L1J skills.action_id를 콘텐츠로 채택. 지원 56종의 SQL 원행·gfx/SPR/catalog 존재표는 T/data/m1/spell_display.json. SL_SPELL_EXP=0만 명시 off. magic_cast_display 등록형 hook도 같은 경로 사용. 공식 송신 정책·원본 화면 미확인. 기존 BUFF_GAMETIME_EVIDENCE:48의 기본 off 판단을 이 범위에서 대체. |
| R15.3 S_SkillSound → 본인+주변 | ［J/model/skill/L1SkillUse.java:1449］<br>［J/model/skill/L1SkillUse.java:1455］ | 기존 4ED8 target UID32/gfx<br>［T/world_feature_magic.py:_world_magic_display］<br>［T/world_status_frames.py:effect_frame］ | **기본 보냄** · 승인 L1J skills.castgfx로 지원 56종 전부 현재 SPR·SPX catalog 존재 확인(자원 부재 보류 0). castgfx2는 전부0. sprite829/830의 file744 alias와 gfx 식별을 구분. 고정 클라이언트26.09.29.2001 inventory 범위이며 실제 SPX 픽셀·소리·수명은 헤드리스 미확인. |
| R15.4 S_SkillIconShield(type5,duration) → 효과 받은 본인 | ［J/model/skill/L1SkillUse.java:1226］<br>［J/model/skill/L1SkillUse.java:1231］<br>［J/serverpackets/S_SkillIconShield.java:29］ | 4E91 fixed catalog/K/remaining<br>［T/world_feature_magic.py:28］<br>［T/world_feature_magic.py:112］<br>［T/world_feature_magic.py:500］ | **보냄** · 지원28 catalog의 positive CommonSpell.f3+SpellIcon frame만 기본 on. Shield2→K485, 실제 잔여초·갱신/만료/사망 remove·재접속 기존 authority. SL_PLAYER_MAGIC_BUFF_UI=0이면 off. K namespace의 마법 적용은 명시 정적 추론이며 공식 record/픽셀 미확인. ［E/BUFF_GAMETIME_EVIDENCE.md:5］ |
| R15.5 S_ServerMessage(HP279/MP278/실패·발생) → 해당 PC | ［J/model/skill/L1SkillUse.java:1093］<br>［J/model/skill/L1SkillUse.java:1098］<br>［J/model/skill/L1SkillUse.java:3052］ | 4EEA 계열; 4F25 ACK 별도 미확인<br>［T/world_feature_magic.py:1153］<br>［T/world_feature_magic.py:1236］ | **안 보냄** · 이 handler send 묶음에 4EEA 없음. 현대 메시지 번호·4F25 정상값/필수성 미확인. E/CHAT_EVIDENCE.md:63 |

#### R16 마법 시전(대상 Heal·공격)

| 응답·수신자 | L1J C_*→callee→S_* 근거 | 현대 대응·우리 송신 근거 | 판정·범위 |
|---|---|---|---|
| R16.1 S_HPUpdate / S_MPUpdate / S_OwnCharStatus / 재료 inventory → 대상 PC·시전자 각각 | ［J/model/skill/L1SkillUse.java:3035］<br>［J/model/skill/L1SkillUse.java:3049］<br>［J/model/Instance/L1PcInstance.java:2796］<br>［J/model/Instance/L1PcInstance.java:2812］ | 4E38 + 0965/0978<br>［T/world_feature_magic.py:976］<br>［T/world_feature_magic.py:1029］<br>［T/world_feature_magic.py:1135］<br>［T/world_feature_magic.py:1145］<br>［T/world_feature_magic.py:1236］ | **보냄** · Heal 대상/시전자 비용·drain 자원. 공격대상별 모든 부가 응답은 아님 |
| R16.2 S_UseAttackSkill / S_DoActionGFX(피격 추가) → 본인+주변+추가 target 주변 | ［J/model/skill/L1SkillUse.java:1397］<br>［J/model/skill/L1SkillUse.java:1401］<br>［J/serverpackets/S_UseAttackSkill.java:81］ | 기존 4E31 f1..5/f13=true<br>［T/world_feature_magic.py:_world_magic_display］ | **시전 동작 기본 보냄** · 지원 56종 L1J action_id 콘텐츠만 채택. projectile UID·f6/f7·raw f9..12와 피격 추가 동작을 만들지 않음. 투사체 비행/linked effect는 별도 미확인. ［E/SPELL_DISPLAY_EVIDENCE.md:25］ |
| R16.3 대상 S_SkillSound / S_SkillIconShield → 대상 본인+주변 / 대상 본인 | ［J/model/skill/L1SkillUse.java:1231］<br>［J/model/skill/L1SkillUse.java:1449］ | 기존 4ED8 / 4E91<br>［T/world_feature_magic.py:_world_magic_display］<br>［T/world_feature_magic.py:_world_magic_sync_icons］ | **기본 보냄** · 4ED8은 지원56종 콘텐츠 gfx를 target 위치로 발행하고 4E91의 기존 catalog/수명은 유지. projectile SPR을 target 위치 효과로 보내는 것은 비행 재현이 아니며 헤드리스 실제 표시·수명 확인 필요. 공유 magic_cast_display hook 제공; 동료 caller 파일 연결은 이번 범위 밖이라 미적용. |
| R16.4 S_ServerMessage / 현대 SC_USE_SPELL_ACK 후보 → 해당 PC | ［J/model/skill/L1SkillUse.java:1010］<br>［J/model/skill/L1SkillUse.java:3052］ | 4EEA / 4F25<br>［T/world_feature_magic.py:1153］<br>［T/world_feature_magic.py:1236］ | **대응 미확인** · L1J식 문구는 위 자기 마법 경로와 같이 미송신. 4F25 필요성·enum은 E/PLAYER_MAGIC_EVIDENCE.md:82에서 UNKNOWN |

#### R17 상점 구매

| 응답·수신자 | L1J C_*→callee→S_* 근거 | 현대 대응·우리 송신 근거 | 판정·범위 |
|---|---|---|---|
| R17.1 S_ShopSellList(상인 관점) → 본인 | ［J/clientpackets/C_NPCAction.java:240］<br>［J/serverpackets/S_ShopSellList.java:86］ | 4E48 BUY_LIST<br>［T/world_handlers.py:46］<br>［T/world_handlers.py:267］<br>［T/world_handlers.py:806］ | **보냄** · 현재 목록 제공 메뉴/설정 범위. 원 소비 E/M2_NPC_MENUS.md:176 |
| R17.2 S_AddItem / S_ItemAmount / S_DeleteInventoryItem → 본인 | ［J/clientpackets/C_Result.java:119］<br>［J/model/shop/L1Shop.java:245］<br>［J/model/shop/L1Shop.java:260］<br>［J/model/L1PcInventory.java:179］<br>［J/model/L1PcInventory.java:246］<br>［J/model/L1PcInventory.java:414］ | 0964 / 0965 / 0978<br>［T/world_handlers.py:293］<br>［T/world_handlers.py:297］<br>［T/world_handlers.py:673］<br>［T/world_handlers.py:682］<br>［T/world_handlers.py:695］ | **보냄** · 화폐 차감·신규/stack delta; codec inventory.py:20, inventory_update.py:27, item_transfer_protocol.py:39 |
| R17.3 S_ServerMessage(904/189/82/263) / S_SystemMessage(수량제한) → 본인 | ［J/model/shop/L1Shop.java:130］<br>［J/model/shop/L1Shop.java:134］<br>［J/model/shop/L1Shop.java:139］<br>［J/model/shop/L1Shop.java:154］<br>［J/clientpackets/C_Result.java:124］ | 4EEA / 4E52 계열 후보<br>［T/world_handlers.py:274］<br>［T/world_handlers.py:300］<br>［T/world_handlers.py:673］ | **안 보냄** · 해당 trade/commit에 문구 생성 없음. 성공 때 항상 완료 문구가 있다는 주장은 아님. 현대 번호/자유문자 type 미확인 |
| R17.4 S_PacketBox(WEIGHT) → 본인 | ［J/model/L1PcInventory.java:181］<br>［J/model/L1PcInventory.java:256］ | 대응 opcode 미확인<br>［T/world_handlers.py:673］<br>［T/world_core_stats.py:96］ | **대응 미확인** · 계산과 거래 직후 표시 wire는 구별 |

#### R18 상점 판매

| 응답·수신자 | L1J C_*→callee→S_* 근거 | 현대 대응·우리 송신 근거 | 판정·범위 |
|---|---|---|---|
| R18.1 S_ShopBuyList(상인 관점) → 본인 | ［J/clientpackets/C_NPCAction.java:283］<br>［J/serverpackets/S_ShopBuyList.java:56］ | 4EE7 SELL_LIST<br>［T/world_handlers.py:46］<br>［T/world_handlers.py:267］ | **보냄** · 원 소비 E/M2_NPC_MENUS.md:178 |
| R18.2 S_ItemAmount / S_DeleteInventoryItem / S_AddItem → 본인 | ［J/clientpackets/C_Result.java:138］<br>［J/model/shop/L1Shop.java:331］<br>［J/model/L1PcInventory.java:179］<br>［J/model/L1PcInventory.java:246］<br>［J/model/L1PcInventory.java:414］ | 0965 / 0978 / 0964<br>［T/world_handlers.py:295］<br>［T/world_handlers.py:300］<br>［T/world_handlers.py:673］<br>［T/world_handlers.py:682］ | **보냄** · 상품 감소·화폐 증가 |
| R18.3 서비스 오류문구 / weight → 본인 | ［J/model/L1PcInventory.java:256］<br>［J/model/shop/L1Shop.java:331］ | 대응 opcode 미확인<br>［T/world_handlers.py:274］<br>［T/world_handlers.py:300］ | **대응 미확인** · 판매 성공 때 필수 문구 근거 없음. 이 commit에 4EEA/4E52 없음만 확인; weight 원본 대응도 미확인 |

#### R19 창고 맡김·찾기

| 응답·수신자 | L1J C_*→callee→S_* 근거 | 현대 대응·우리 송신 근거 | 판정·범위 |
|---|---|---|---|
| R19.1 S_RetrieveList / S_Deposit(혈맹 cdeposit 별도) → 본인 | ［J/clientpackets/C_NPCAction.java:285］<br>［J/clientpackets/C_NPCAction.java:452］<br>［J/serverpackets/S_RetrieveList.java:32］ | 4ED2 deposit COUNT / 0971 retrieve LIST<br>［T/world_feature_town.py:58］<br>［T/world_feature_town.py:60］<br>［T/world_feature_town.py:76］<br>［T/world_feature_town.py:85］ | **보냄** · WAREHOUSEEXP gate 켜진 구성에 한정. off는 미송신. 개인 deposit과 L1J cdeposit 합치지 않음. E/WAREHOUSE_EVIDENCE.md:25 |
| R19.2 S_AddItem / S_ItemAmount / S_DeleteInventoryItem → 본인 | ［J/clientpackets/C_Result.java:201］<br>［J/clientpackets/C_Result.java:235］<br>［J/model/L1PcInventory.java:179］<br>［J/model/L1PcInventory.java:246］<br>［J/model/L1PcInventory.java:414］ | 0964 / 0965 / 0978<br>［T/world_feature_town.py:177］<br>［T/world_feature_town.py:184］<br>［T/world_feature_town.py:193］ | **보냄** · 선택된 창고 gate 구성에서 실제 commit delta+수수료 송신. E/WAREHOUSE_EVIDENCE.md:87 |
| R19.3 S_ServerMessage(189/270) 및 거래 후 목록/ACK 요구 여부 → 본인 | ［J/clientpackets/C_Result.java:248］<br>［J/clientpackets/C_Result.java:252］ | 4EEA 계열 / 추가 ACK 미확인<br>［T/world_feature_town.py:177］<br>［T/world_feature_town.py:193］ | **대응 미확인** · 이 함수에 문구·추가 LIST/성공ACK 없음. L1J가 항상 추가 LIST/ACK를 보내는지 근거 없으므로 필수 누락으로 세지 않음 |

#### R20 파티

| 응답·수신자 | L1J C_*→callee→S_* 근거 | 현대 대응·우리 송신 근거 | 판정·범위 |
|---|---|---|---|
| R20.1 S_Message_YN(953) → 가입 / S_Party HTML → 피초대 PC / 요청 본인 | ［J/clientpackets/C_CreateParty.java:64］<br>［J/clientpackets/C_Attr.java:413］<br>［J/clientpackets/C_Party.java:41］<br>［J/serverpackets/S_Party.java:31］ | 08A0..08A6 수신 계열; 제어 enum 미확인<br>［T/world_handlers.py:856］<br>［T/world_handlers.py:891］<br>［T/world_feature_companion.py:1860］<br>［T/world_feature_companion.py:1960］ | **안 보냄** · 일반 PC 초대·수락 handler가 조사한 등록 범위에 없음. 동료 owner 08A0 projection은 보냄. E/PARTY_COMPANION_EVIDENCE.md:35 및 :66. 정상 제어 매핑 미확인 |
| R20.2 S_HPMeter(가입·HP변경·탈퇴) → 파티 | ［J/model/L1Party.java:105］<br>［J/model/L1Party.java:116］<br>［J/model/L1Party.java:125］ | 08A0 / 08A1 / 08A3 (동료 투영)<br>［T/world_feature_companion.py:1893］<br>［T/world_feature_companion.py:1960］<br>［T/world_feature_companion.py:1965］ | **보냄** · 동료→owner 목록/HP·MP%/제거 한정. 일반 PC 파티의 동등성은 미확인. E/PARTY_COMPANION_EVIDENCE.md:77. L1J에 없는 파티 MP를 누락으로 세지 않음 |

#### R21 일반·파티 채팅

| 응답·수신자 | L1J C_*→callee→S_* 근거 | 현대 대응·우리 송신 근거 | 판정·범위 |
|---|---|---|---|
| R21.1 S_ChatPacket → 주변+송신 본인 / 파티 | ［J/clientpackets/C_Chat.java:35］<br>［J/clientpackets/C_Chat.java:128］<br>［J/clientpackets/C_Chat.java:159］<br>［J/serverpackets/S_ChatPacket.java:76］ | 4E52 SC_CHAT_ACK 수신<br>［T/world_handlers.py:856］<br>［T/world_handlers.py:891］ | **안 보냄** · 현재 조사한 registry/송신 코드에 normal/party echo 없음. 확인된 normal0 UI는 Purple 송신이고 socket C2S 미확인. E/CHAT_EVIDENCE.md:9 및 :39. 4F2D는 whisper 선검사 |
| R21.2 S_ServerMessage / S_SystemMessage → 해당 본인 | ［J/serverpackets/S_ServerMessage.java:64］<br>［J/serverpackets/S_SystemMessage.java:37］ | 4EEA ID12066+arg<br>［T/world_feature_companion.py:33］<br>［T/world_feature_companion_bridge.py:238］<br>［T/world_feature_talkscroll.py:19］ | **보냄** · 일부 동료/두루마리 안내만. 일반 채팅·모든 오류 안내 구현 아님. E/CHAT_EVIDENCE.md:63, :117. 4E52 자유 시스템 type와 한국어 화면 미확인 |

#### R22 레벨업

| 응답·수신자 | L1J C_*→callee→S_* 근거 | 현대 대응·우리 송신 근거 | 판정·범위 |
|---|---|---|---|
| R22.1 S_OwnCharStatus / S_Exp → 본인 | ［J/model/Instance/L1PcInstance.java:2195］<br>［J/model/Instance/L1PcInstance.java:2200］<br>［J/model/Instance/L1PcInstance.java:3569］ | 4E38 level/EXP/maxHP/maxMP<br>［T/world_visibility.py:614］<br>［T/world_visibility.py:642］<br>［T/world_core_session.py:211］<br>［T/world_status_frames.py:114］ | **보냄** · E/M1_REWARD_PACKETS.md:83의 level 비교가 Effect2127/Level key/event 요청. 별도 레벨업 이펙트 packet 부재를 누락으로 세지 않음 |
| R22.2 S_HPUpdate / S_MPUpdate(refill) → 본인 | ［J/model/Instance/L1PcInstance.java:3566］<br>［J/model/Instance/L1PcInstance.java:3567］ | 4E38 현재 HP/MP는 유지<br>［T/world_visibility.py:638］<br>［T/world_status_frames.py:95］ | **안 보냄** · 새 refill 값 미송신: LOCAL no-level-up-refill 정책. full status 부재가 아니며 공식 클라이언트 결함 확정 아님; 신호 누락 top10과 분리 |
| R22.3 S_bonusstats → 조건부 본인 | ［J/model/Instance/L1PcInstance.java:3560］ | 4F0F 잔여점수<br>［T/world_feature_bonus_stat.py:49］<br>［T/world_feature_bonus_stat.py:69］<br>［T/world_feature_bonus_stat.py:74］ | **보냄** · feature 활성·notice 호출 때. 정확 reward hook→notice 실호출은 미확인. E/BONUS_STATS.md:18 / E/SELFINFO_FIELDS_EVIDENCE.md:83 |

### 남은 주요 미송신 (서버 후속 반영)

1차 상위10개에서 R01.1/R04.2/R08.4/R08.5/R13.3(R14.3)을 서버 경로에 연결했다. 남은 순서는 이전 시각적 영향 추정을 유지하며 화면 관측이 아니다.

| 순위 | 응답 공백 | 범위·근거 하위행 |
|---:|---|---|
| 1 | 자기·대상 마법 시전 동작(기본 설정) | R15.2 · SL_SPELL_EXP=1에서만 후보 송신 |
| 2 | Heal·Shield 대상 이펙트(기본 설정) | R15.3 · 같은 실험 gate에서만 송신 |
| 3 | 미매핑 마법 HUD·실제 화면 확인 | R15.4 지원28 catalog는 기본 송신으로 해소; positive f3/atlas가 없는 catalog와 픽셀은 보류 |
| 4 | 버린 물건 표시의 주변 전달 | R07.3 · sibling whole-item drop 경로 한정 |
| 5 | 인챈트 결과 안내(기본 설정) | R09.2 · 재고 변화는 보냄; 현대 0967 의미·메시지 ID는 미확인 |

그 밖의 scoped 미송신은 PC 부활 동의(R12.1), 일반 PC 파티 초대/수락(R20.1), 일반/파티 채팅 echo(R21.1), 일부 서비스 오류문구(R08.7/R15.5/R17.3)다. 현대 제어/입력/메시지 ID 미확정과 분리해 본다. 공격 주문 projectile 필드 공급 부족은 R16.2에 별도로 남겼다.

### 확인 못 한 것과 누락에서 제외한 것

- 공식 서버의 동작별 실제 묶음·순서·recipient 및 현재 클라이언트 화면/입력 반영은 실행하지 않아 미확인.
- 마법 4F25 정상 enum·필수성, 0967 인챈트 결과 필드, L1J 메시지 번호의 현대 동등 ID와 자유문자 시스템 type/한국어 표시.
- teleport S_Paralysis/S_SkillSound·지연·잠금해제의 현대 인과 및 map 4E95 f2/정상 순서; 모든 bookmark/혈맹 동반 분기.
- 즉시 무게 갱신 wire, 부분 pickup 뒤 ground 표시, 감정 상세창·독 상태 표시·공식 curse color/template.
- 일반 PC 파티 초대/수락 제어 enum·HP 갱신과 동료 projection의 동등성; 일반채팅 socket C2S/SDK transport.
- 창고 거래 후 별도 LIST/성공 ACK 필요성. 현 handler에 없음만으로 필수 누락으로 세지 않음.
- 사망 PK/duel·cancellation/변신·아이템 손실, 모든 반사/무기효과·invis 이동 recipient, 레벨업 bonus notice의 정확 reward hook.
- 전체 아이템·전 주문·전 상점·전 창고 분기를 전수 조사하지 않음. 버리기/부활/이동은 표의 제한된 LOCAL 경로만 비교.

- 제외: 이동 자기 정상 ACK: L1J 정상 이동은 주변 방송이며 자기 ACK 요구 근거 없음.
- 제외: 독립 피격 packet: 4E31 target-effect가 DamagedAction을 요청할 수 있어 4E39 추가 부재만으로 누락 아님.
- 제외: 독립 레벨업 effect packet: full4E38 level 비교의 기존 클라이언트 효과 소비 경로가 있음.
- 제외: 레벨업 HP/MP refill은 L1J와 LOCAL 정책 차이이며 공식 필수 응답 결함으로 확정하지 않음.

사이드 메모의 03EB는 기존 정적 이름이 CS_EXCLUDE_REQ(［E/REQUEST_COVERAGE_MAP.json:10836］), 072E는 CS_BLOOD_PLEDGE_EMBLEM_INFO_REQ(［E/REQUEST_COVERAGE_MAP.json:13749］)다. 실제 플레이 중 해당 요청이 나온 원인·UI·필수 응답은 이름만으로 확정하지 않았고 이번 22동작에 임의 연결하지 않았다.

기계 판독판은 [REQUEST_COVERAGE_MAP.json](REQUEST_COVERAGE_MAP.json)의 새 root 칸 original_response_checklist_v1에 추가했다. 기존 221개 rows·통계·요청 처리 판정은 변경하지 않았다.
JSON은 1차 snapshot이며 이번 마법 HUD 후속의 판정 변경은 이 Markdown에만 반영했다.

1차 문서 검증: 당시 JSON 파싱·22동작/70하위행/상위10개 연결을 확인했다. 새 root 칸을 제외한 기존 JSON의 정규화 해시는 변경 전후 동일하다. 고유 근거 314개의 파일 존재·줄 범위를 확인했으며 이는 원문 지지 여부나 실행 성공을 대신하지 않는다. 1차 당시 제품 시험은 수행하지 않았다. 후속 개발 시험은 아래에 구분했다.

### 서버 recipient 연결 후속 (2026-10-29)

R01.1/R04.2/R08.4/R08.5/R13.3/R14.3은 기존 realm self Actor DTO·기존 4E2C/4E39/4ED8/4E5B/4E96 생산자를 재사용했다. 별도 `pc_known`은 NPC known과 섞지 않고 실제 소개한 PC만 받게 한다. 양쪽 화면 진입/퇴장, 맵 전이/reset, 로그아웃, own outbox 정리와 재접속 시 새 DTO를 연결했다. 한 칸 순간이동은 destination heading의 최종 Actor이며 정상 걸음으로 방송하지 않는다. 저장→응답 순서와 기존 row/world 잠금·drain 경로를 유지한다.

**운영 경계:** ［T/broker.py:464］ `MOVEMENT_SESSION_LIMIT`과 realm의 단일 profile 제한을 유지했다. 따라서 다중 PC 주변은 개발용 WorldView/송신 lane 시험까지이며 실제 동시 로그인·화면 동작을 확인한 결과가 아니다. self의 정상 ACK를 추가하거나 단일 PC guard를 풀지 않았다.

마법 HUD 후속 당시에는 지원28 catalog의 4E91만 기본 활성화했다(［E/BUFF_GAMETIME_EVIDENCE.md:5］). 현재 R15/R16의 B5 후속은 사용자 결정에 따라 L1J action_id/castgfx를 콘텐츠로 채택하고 지원56종의 시전 동작·대상 효과를 기본 송신한다(SL_SPELL_EXP=0만 명시 off). 과거 PLAYER_MAGIC_EVIDENCE.md:173의 opt-in/transient K와 BUFF_GAMETIME_EVIDENCE의 표시 보류는 당시 기록이다. 공식 producer·projectile 입력·현대0967 callback/필드/enum의 미확정은 유지하며 원본 화면 확인은 0개다. SL_EXPERIMENT_ENCHANT는 변경하지 않았다.

B5 표시 후속 시험: 표시 전용 5개 통과(1.605초). 지정 두 모듈은 124 tests / failures7 / errors17(20.588초)로 실패했다. TMP/TEMP를 `_work/tmp`로 지정해도 임시파일 생성 PermissionError와 저장 후속 assertion 실패가 남았다. [원로그](../runs/magic-display-followup-unittest-20261029.log). 전체 회귀 통과·원본 화면 PASS가 아니다.

마법 후속 지정 시험은 121 tests / failures7 / errors18 / exit1(18.513초)이었다. Temp 생성/정리 권한 오류·후속 저장 assertion 외에 새 기본설정 시험 fixture 오류1도 포함됐다. 추가 시험 금지 메시지 전 시작한 직접 영향 메모리 6개는 5개 성공/fixture 오류1(2.085초)이며 fixture 수정 후 미재시험이다. 경로/권한 우회나 게임/포트 실행은 없다. 정확한 범위·보류는 ［E/BUFF_GAMETIME_EVIDENCE.md:53］ 이후에 기록했다.

남긴 항목: R07.3은 독립 sibling custody/ground 수명의 WorldView 이관·pickup/실패/퇴장 결속이 필요하다(［T/item_transfer_session.py:391］ 저장 계획, :407 commit, :412 send, :416 complete). 표시만 복제하지 않았다. R12.1은 PC 동의/승인 부활, R20.1은 일반 PC 파티 제어, R21.1은 Purple/socket 입력 결속, R08.7/R15.5/R17.3은 현대 문구 ID가 부족하다. R22.2는 기존 LOCAL no-level-up-refill 정책이므로 변경하지 않았다. 이 목록과 위 gate 목록이 기존 모든 안 보냄 행의 재검토 결과다.

개발 검증: `python -m unittest tools.local_original_session.world_pc_response_tests tools.local_original_session.world_refactor_review_tests tools.local_original_session.world_decoupling_tests tools.local_original_session.world_visibility_regression_tests tools.local_original_session.world_item_effects_tests.ItemEffectsTests tools.local_original_session.world_item_effects_tests.BlueRecoveryTests tools.local_original_session.world_item_effects_tests.BuffIconFrameTests` **84개 통과**(새 시험 16개 포함, 이 한 묶음의 중복 없는 개수). [실행 원문](../runs/response-server-20261029/memory-tests.txt). 새 시험은 self/보이는 PC/시야 밖/다른 맵, 거절 시 무방송, 실제 stance refresh의 self drain 후 peer 전달·외형 불변 시 무송신을 확인한다.

저장 회귀는 `world_integration_tests.InjectedBrokerTests` 8개와 `world_item_effects_tests.ConsumableStoreTests` 5개를 기본 Temp 및 workspace 임시 경로로 재시도했으나 `characters.json.*.tmp`/`.consumable-effects-*.tmp` 생성 PermissionError, 정리 WinError5가 재현됐다. workspace 재시도는 13 tests / 3 failures / 23 errors이며 [전체 원문](../runs/response-server-20261029/saved-tests.txt)을 보존한다. 저장 guard/기대값은 바꾸지 않았다. `stance_tests.StanceSendTests.test_equipping_and_unequipping_send_same_self_through_production_lane`도 기존 fixture의 `item_equipment_effect.py:436` context['items'] 누락→:222 `_operation` 누락으로 변경 함수 호출(:456) 전에 실패했다. 이번 변경 경로는 새 StanceLaneTests로 직접 확인했다. 정식 패킷/원본 화면 PASS는 아니다.
