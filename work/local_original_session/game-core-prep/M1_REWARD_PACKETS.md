# M1 보상 패킷 — broker 연결 준비

2026-10-26 · 기존 기록·현재 코드의 읽기 전용 조사. 문서 작성 외 변경·새 역분석·게임·서버·시험 실행 없음. 아래는 클래식 클라이언트의 정적 소비 근거와 기존 로컬 구현을 구분한 결과이며 M1 플레이 PASS가 아니다.

경로 약칭: `T/`=`tools/local_original_session/`, `C/`=`work/local_original_session/implementation-5/combat-adjudication/`, `R/`=`work/local_server_rea_20261016/`, `A/`=`work/local_original_session/shared-api/`. `fN`은 protobuf 필드 번호이며 중첩 필드는 별도 표기한다. u32/u64/i32는 uint32/uint64/int32다. 프레임은 기존 `<u16LE 길이,u16LE opcode> + protobuf + 00 00`을 재사용한다(`T/inventory_update.py:152–157`).

## 1쪽 — 경험치·레벨업

### (1) 경험치 변화·레벨 표시

**별도 EXP 패킷을 추정할 필요 없이, 확인된 표시 경로는 `S2C 4E38 SC_STATUS`의 f26 double이다.** 선택 필드(presence bit23)이며 EXP 텍스트 `{:.4f}%`와 상한100 게이지로 소비된다. 누적 raw EXP나 필요 경험치 배열이 아니다. f2는 required i32 레벨이다. f3 optional int64를 누적 EXP로 명명할 **근거 없음**.

- 근거: `work/core_rule_research/progression/report.json:123–129,150–162,166–174,206–222`; 요약 `docs/CORE_RULE_DATA_VALUE.md:28–36`. f26은 proto+90→protected status+18→EXP HUD로 연결된다. required mask7FFFD 밖이지만 handler는 객체 멤버를 무조건 복사하므로 **누락을 기존 EXP 표시 보존으로 가정할 수 없다**.
- 재사용: `C/progression-owner-v1/progression_owner.py:339`의 `ProgressionOwner.award_kill_locked()`는 genuine kill의 누적 EXP·성장 저장 접점이다. `C/progression-kill-delivery-v1/progression_kill_delivery.py:21`의 `after_death_drained_locked()`가 Death drain 후 이를 소비한다. 다만 비레벨업 kill은 `progression_owner.py:420–425`에서 `delivery=None`이다.
- 연결 공백: `tools/local_world_protocol/model.py:33,49–52`는 f26의 type-card `0x18d3`을 unsupported fixed scalar로 거절한다. 선정된 기성 성장 codec도 f26을 갱신하지 않는다(아래 (2)). **매 kill EXP 퍼센트 송신 구현·화면 확인은 근거 없음**. 서버가 퍼센트를 계산하는 원본 수식도 미확정이다. `T/world_reward.py:63–64`의 EXP 필드 미확정 주석은 누적 EXP와 이미 확인된 표시 퍼센트를 구별해야 한다.

### (2) 레벨업 시 최대 HP/MP·능력치 갱신

동일한 **full `4E38`**을 사용한다. f1=u64 ActorUID; f2=i32 레벨; f4..9=i32 STR/DEX/INT/WIS/CON/CHA; f10..13=i32 현재HP/최대HP/현재MP/최대MP; f14=i32 음수 AC. 전부 필요한 기존 full-status 필드를 보존해야 하며 이 부분 필드만 보내는 계약이 아니다. 의미 대응은 `tools/local_self_info_profile/model.py:84–89`, wire 타입·required는 `work/online_world_packet_source/world-notify-contract.json`의 opcode20024 항목에 있다.

- 재사용 후보는 공용 T에 통합된 것으로 간주하지 않는다: `C/progression-level-delivery-v1/candidate/tools/local_original_session/hp_resource_owner.py:408`의 `progression_operation()`이 f2·f4..14를 구성(`:438`), `:454`의 `project_progression_committed()`가 공동 commit 후 투영한다. 같은 후보 `hp_status.py:239`의 `Service.project_progression_commit()`과 `:39`의 `frame()`이 full-status delivery를 만든다. 허용 변경 집합은 `hp_status.py:248`의 `{2,4..14}`이며 **f26은 제외**된다.
- 기존 로컬 순서: `C/progression-kill-delivery-v1/progression_kill_delivery.py:21,99–103`의 Death4E39 DRAINED→award→성장 delivery `_send(...status_operation=...)`. 공식 서버의 필수 패킷 순서와는 구별한다.
- 실행 근거: `C/HANDOFF.md:137–138`의 actual163은 EXP125/Lv2→35 kill→EXP300/Lv3, 새 성장4E38 native DRAINED와 fresh 저장·상태 일치 PASS다. 게임 UI·레벨업 연출은 미관측이며 별도 연출 opcode **근거 없음**. 영구 능력치 배분도 이 경로가 구현한 것으로 볼 수 없다(`C/progression-owner-v1/progression_document.py:114`).

## 2쪽 — 바닥 아이템·인벤토리·아데나

### (3) 표시·제거·줍기

| 방향·opcode | 필드와 확인 범위 | 근거·재사용 함수 |
|---|---|---|
| S2C `4E96` 바닥 Item 생성 | f1=u32 packed좌표, f2=u32 ActorUID, f3=i32 appearance, f4=i32 action, f5=i32 direction, f7=u64 Q, f16=bool false. required는 **f1..24·27·28** 전체이며 나머지를 임의 생략하면 안 된다. present f39=i32≥0, present f69=i32는 appearance override. | `R/run101_item14_local_spawn_contract/spawn_recipe/findings.md:13–24`; 전체 타입 `T/item_ground_wire.py:43–52`. 같은 파일 `build_candidate():248`, `parse_candidate():290`. `local_candidate():213`는 template1→LOCAL appearance14 전용이다. |
| S2C `4E40` 바닥 제거 | f1=required u64 ActorUID. 정상 등록된 same UID Item의 actor·선택·event·component 제거 경로이며 HP0/Death gate 불필요. | `R/run98_item_drop_pickup_contract/findings.md:18,30–34`; `T/item_ground.py:248–260`의 `GroundRegistry._prepare()` pickup 분기, `prepare_pickup_locked():275`. |
| C2S `4E3E CS_GET_ITEM_REQ` | outer f1=required singular message. child f1=x i32, f2=y i32, f3=UID u64, f4=Q u64, 모두 required/wire0. | 같은 run98 `:15–20`; `T/item_transfer_protocol.py:79–100,138–174`. `build_get_payload():184`, `parse_get_payload():223`, `parse_get_frame():247`. |
| 로컬 GET 응답 | 기존 구현은 custody commit 뒤 **4E40→0964** ordered drain. DROP4E3F는 같은 child를 outer repeated f1으로 받고 **0978→4E96**을 보낸다. 별도 GET 성공 ACK는 확인하지 못했다. | `T/item_transfer_session.py:385–412`의 `ItemTransferSession.handle():348`, `inventory_return_b():490`. account-v5 접점은 `A/account-v5-packet-transfer/packet_transfer_owner.py:PacketTransferOwner.prepare_received_locked()`이며 계약은 같은 폴더 `API.md:9–21`. |

Item 생성에는 full payload 외에도 **f16=false·명시 f39≥0·loaded Sprite subtype9·483F0=false**라는 원 분기 조건이 있다(run101 `:3`). subtype9는 appearance 번호9가 아니다. InventoryUID32, GET/제거 UID64, spawn UID32→ActorUID64는 별도 계약이며 같은 schema가 UID 동일성을 보장하지 않는다(run98 `:34`). 일반 드롭·부분 줍기·다중 아이템 완료로 확대할 수 없다. 기존 T transfer의 한 왕복·동일 타일·수량 제약은 별도 연결 작업이다(`work/local_original_session/game-core-prep/REUSE_TABLE.md:18,25`).

### (4) 인벤 추가·수량 증가와 아데나

| opcode | 필드·소비 | 재사용·근거 |
|---|---|---|
| `S2C 0964` 추가 | outer f1=repeated ItemInfo, f2=optional bool(**명시 false가 append**), f3=optional u32/의미 미확정. ItemInfo f1=required u32 UID, f2=optional i32 template, f4=optional u64 Q. 빈 목록은 clear가 아니다. | `R/run30_inventory_first_wire/findings.md:24–50`; `T/inventory.py:265` `build_add()`, `:920` `build_collection_add()`, `:934` `build_current_collection()`. |
| `S2C 0965` 수량 변경 | outer f1=repeated ItemInfo, 0964의 outer bool 없음. f1=required u32 **기존** UID, f4=optional u64 **새 절대 잔량**. 없는 UID는 append 없이 skip; Q0도 제거 아님. 선택 갱신 필드 f18=string, f7/f5=i32. | `R/run41_inventory_update/findings.md:15,21–36`; run98 `:34`. `T/inventory_update.py:160` `build_update({1:uid,4:new_total})`, `:166` `validate_frame()`. |
| `S2C 0978` 인벤 제거 | f1=required u64 UID. 0965 Q0 또는 빈0964/0965와 구별한다. | run98 `:17,34`; `T/item_transfer_protocol.py:256` `build_remove()`. |

**아데나는 별도 화폐 opcode 대신 template7 인벤 아이템 경로를 재사용할 수 있다.** 기존 보유 UID 증가는0965, 신규 정당 발급 UID 추가는0964로 구분한다. `work/local_original_session/spellbook/adena-normal-acquisition-v1/adena_credit_source.py:33–47`의 `definition()`·`prototype()`은 template7/Q/f5=0 ADD 후보를 만든다. prototype UID는 실제 발급 UID가 아니다. 같은 폴더 `character_scope.py:66`의 `adena_held_frame()`·`:85`의 `current_adena_frame()`이 실제 held 조회 접점이다. 클래식7↔L1J40308은 대응된 번호이고, L1J 유래 무게0·stackable·invgfx5/grdgfx7·수량 상한은 **LOCAL 정책**이다(같은 폴더 `API.md:7–11`; 이 문서와 같은 폴더 `MAPPING_SCOPE.md:17`). ground graphics7의 실제 rendering은 미검증이다(`A/account-v5-packet-transfer/whole-account-packet-scenario-v1/API.md:13,32–33`).

## 3쪽 — 몹 HP 바·사망 EXP 손실과 연결 판정

### (5) 몹 머리 위 HP 바

**`4EC8 SC_INSTANCE_HP_NOTI`의 f1=i32/f2=bool/f3=i32는 전부 required(mask7)지만 업무 의미는 여전히 UNKNOWN이다.** UID·현재HP·최대HP·비율로 명명하거나 값을 넣을 근거 없음. 기존 `R/run29_instance_hp_consumer/findings.md:9,40–42`의 wrapper+20/+24/+28→event17FFB80→generic callback virtual+10까지가 확인 범위다.

후속 근거도 결론을 바꾸지 않는다. `R/run103_i2_005_hp4ec8_subscriber/notify_consumer_actual257/resume_source_path/hp_consumer_chain/typed_ui_binding/findings.md:3,69`는 별도 **4F1A SC_HIT_RATIO_NOTI→MonsterActorHud HP debug Text**를 연결했지만 일반 gameplay HP 바·4EC8과의 동일성은 미확정이다. `R/run323_energybolt_s2c_success_hp_contract/contract.md:20–24`도 같은 한계를 유지한다.

재사용 가능한 것은 `T/hp4ec8_subscribers.py`의 `Observation` 관측 경로뿐이며 HP바 송신 builder가 아니다. **확정된 몹 HP바 패킷·필드·송신 함수는 근거 없음.** 로컬 서버 HP 계산·4E39 사망·4E40 제거 성공을 HP바 표시 근거로 전용하지 않는다.

### (6) 사망 시 경험치 손실 표시

**전용 opcode·손실 수치 필드·팝업·실제 사망 손실 표시 근거 없음.** `4E38.f26`이 일반 EXP 퍼센트를 표시한다는 사실은 확인됐지만 이를 사망 손실 통지 계약으로 입증한 기록은 찾지 못했다. 손실을 레벨·퍼센트 감소로 환산하는 원본 규칙도 미확정이다.

`R/run102_own_player_death_recovery/findings.md:54`는 공식 death penalty/수식·통지 순서를 UNKNOWN으로 남긴다. `T/player_life_codec.py:30–53`의 `death()`(4E39), `ack()`(4EED), `init()`(4F16), `full_status()`(4E38)는 사망·복구 wire 재사용 접점이며 EXP 손실 처리를 제공하지 않는다. 기성 progression owner는 **after.exp≥before.exp, after.level≥before.level**를 요구하므로 감소를 지원하지 않는다(`C/progression-owner-v1/progression_document.py:106–119`).

### broker에 넘길 결론

- 재사용할 경로: genuine kill 저장·성장 full4E38, ground4E96/4E40·GET4E3E, inventory0964/0965/0978. 기존 custody/current·발급 UID·commit/drain 수명을 그대로 연결해야 한다.
- 미완: **f26 double codec·표시퍼센트 생산/매 kill 알림**, 일반 몹 HP바, 사망 EXP 감소/표시. 계산 전용 `T/world_reward.py:1–14,119–127`의 `on_kill()` 결과는 해당 저장·전송 완료가 아니다.
- 이번 검증은 `rg -n --no-ignore`·`Get-Content -Encoding UTF8`로 기존 근거·함수·필드 대조만 수행했다. actual163의 제한된 패킷/저장 PASS 외에 화면·M1 30분·현재 공용 broker 통합은 확인하지 않았다. 게임·서버·순수 모듈 시험은 실행하지 않았다.

## REA 결과 — 경험치 표시와 레벨업 조건 (run383 · 2026-10-26)

이번 한정 후속은 기존 `work/core_rule_research/progression/`의 함수·스키마·CONTROL 복원 view를 재사용한 **정적 분석**이다. 기준은 기존 CONTROL SHA256 `9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`의 저장 기록이며 현재 실행 메모리나 화면 관측이 아니다. 신규 추출·원문은 `R/run383_exp_percent_display/`에만 보존했다([상세 결과](../../local_server_rea_20261016/run383_exp_percent_display/findings.md), [주소별 원문](../../local_server_rea_20261016/run383_exp_percent_display/selected-disassembly.txt)). 앞 절의 과거 연결 공백 기록과 이번에 읽은 현재 서버 코드는 시점을 구분한다.

### 확정: f26은 0..100 단위의 표시 퍼센트

- `4E38.f26`의 double(proto+0x90)은 handler `RVA 0x113601→0x113612`에서 보호 double로 인코딩되어 status+0x18, 즉 CharacterDataSubsystem+0x6F0에 저장된다. HUD `0x9A9154→0x4220B0`은 이를 디코딩하고 **원 double을 `{:.4f}%`로 포맷**하여 `0x9A91CE→0xBF9ED0`으로 EXP 텍스트에 전달한다. 이 경로에는 누적 경험치·레벨표 조회·구간 나눗셈·100배 환산이 없다. 따라서 `12.3456`은 `12.3456%`, `0.25`는 `0.2500%`에 해당한다. 근거: `R/run383_exp_percent_display/selected-disassembly.txt:43–45,472–476,1339–1362`; format 원문 `data-11b95a8.bin`.
- 같은 값의 **게이지만** double→float 변환 뒤 `min(100,max(0,value))` 범위로 제한한다(`0x9A9266..0x9A927A`; 유한값 기준). 텍스트에 이 clamp를 적용하는 흐름은 없다. 근거: 같은 원문 `:1398–1407`, float100 원문 `data-126ed50.bin`. 이는 화면 최종 픽셀·게이지 애니메이션 관측이 아니다.
- f26은 optional이지만 handler의 복사는 무조건 수행된다. 누락을 이전 EXP 보존으로 사용하지 않는다. 기존 required mask와 presence 근거는 `work/core_rule_research/progression/report.json:150–174`를 재사용한다.
- **현재 서버의 ‘현재 레벨 구간 진행률(%)’은 클라이언트의 수신 단위와 일치한다.** `T/world_progress.py:45–52`의 `100*(exp-low)/(high-low)` 및 0..100 제한은 LOCAL 정책이며 공식 원서버 계산식을 회수한 것은 아니다. `T/world_status_frames.py:68–102`는 매 kill의 최종 f2와 전달받은 f26을 full4E38로 구성하고, `:45–49`가 f26을 wire1 little-endian double로 인코딩한다. 이번에는 서버 코드를 수정하거나 이 송신의 실제 화면 반영을 시험하지 않았다.

### 확정: 상승 연출은 f2와 이전 레벨 캐시의 비교로 시작

handler는 f2를 보호 정수 status+0x08(Subsystem+0x6E0)에 저장하고 status publisher `0x11A8F0`을 호출한 뒤 다음 순서로 처리한다. `old = D[0x834]`, `new = decode(D+0x6E0)`, **`D[0x834] = new`를 먼저 저장**, 이어 **`old > 0 && new > old`**일 때 상승 분기로 들어간다(`0x114188..0x1141E5`; 원문 `:639–658`). **f26의 100 도달·증가·리셋은 이 판정에 참여하지 않는다.** 같은 레벨 재통지·레벨 하락은 이 상승 분기를 실행하지 않는다.

- 상승 분기는 ActorSubsystem의 현재 Effect 목록(+0x8C0..+0x8C8)을 검사한다. Effect+0x3C가 **0x84F=2127**인 항목이 이미 있으면 `0x1142A0→0x11442A→0x114B4C`로 아래 상승 처리를 건너뛴다. 캐시는 이미 new로 바뀌므로 같은 f2를 재전송해도 해당 상승을 재시도하지 않는다. 근거: 원문 `:669–710,787–794`.
- 이 중복 항목이 없고 원 자기 actor 취득 경로가 유효하면 `0x114360`이 ID2127을 넣어 `0xCCF30`으로 Effect 요청을 구성하고 자기 ActorUID를 결합해 `0x11438F→0x61530`에 전달한다. `0x61530→0xC1340`의 원 클래스는 vtable0x11817A0→COL0x127B968→TD0x166A588 RTTI `.?AVEffect@lineage@@`로 확인했고 ActorSubsystem 목록에 등록된다. actor가 없으면 Effect 생성만 생략하고 key/event 경로로 이어진다. 실제 효과 자원·수명과 화면 표시 성공은 별도다. 근거: 원문 `:716–752` 및 같은 파일의 `FUNCTION 0x61530`, `FUNCTION 0xc1340`; `selected-data.json`의 `rtti`.
- 상승 분기는 신규 레벨을 인자로 **`Level_{:03d}`** 키를 포맷해 `0x114732→0x12D7A0`에 제출하고, `0x1147EB→0x423580`에 신규 레벨을 담은 event를 보낸다. 실제 번역 문구·toast/팝업 종류·최종 화면은 미확정이다. 근거: 원문 `:929–979`, `data-1185380.bin`의 RVA0x11853C0 문자열. 다중 레벨 상승도 이 handler 안에서는 최종 new로 한 번 처리한다.
- 최초 캐시 **old==0 && new==1**에는 별도 초기 경로가 있어 `Level_001`을 `0x114B15→0x12D7A0`에 제출한다. 이 경로는 위 ID2127 생성·상승 event와 다르므로 ‘최초 수신은 아무 연출도 없다’고 확대하지 않는다. 근거: 원문 `:1014–1017,1117–1132`. old==0/new>1은 위 상승 분기에 들어가지 않는다.
- 이 handler의 상승 분기에는 별도 S2C 레벨업 opcode를 받는 선행조건이 없다. full4E38의 f2 비교가 직접 위 경로를 만든다. 다른 opcode·연출의 전역 부재나 공식 서버 패킷 순서까지 확정한 것은 아니다.

### 미확정과 사용자 화면 실험안

공식 원서버의 누적 EXP→퍼센트 계산식·레벨표 값, Effect2127의 실제 외형·음향·완주·정리, `Level_XXX` 제출 뒤의 최종 UI는 미관측이다. 이 결과는 패킷 실행·게임 화면·M1 플레이 PASS가 아니다.

추후 허용된 정상 로그인→캐릭터 선택→월드 진입에서 (1) 같은 레벨의 실제 처치 전후 full4E38.f26과 HUD의 소수4자리/게이지만 비교, (2) 다음 레벨 문턱을 넘는 실제 처치에서 f2 상승·f26 구간 리셋·효과/문구를 함께 기록, (3) 같은 레벨의 다음 통지에서 연출 재발 여부와 기존 Effect2127의 종료를 관측한다. 최초 Lv1 진입과 저장된 Lv2 이상 재접속은 별도 비교한다. 필드 단위를 추가로 분리해야 할 때만 시험 저장 사본의 전체 상태를 보존해 f2 고정/f26=12.3456인 full4E38 한 건을 비교하며, 이는 개발용 화면 실험으로 구분한다. **이번 작업에서는 게임·서버·포트 실행, 제품 수정, commit을 하지 않았다.**
