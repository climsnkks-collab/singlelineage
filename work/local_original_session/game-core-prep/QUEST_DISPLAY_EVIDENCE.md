# 퀘스트 진행·완료 표시 REA 근거

2026-10-27 · run405 · 정적 조사. **진행 통지 패킷의 opcode·wire 형식은 확정했다. 실제 퀘스트 저널/목표 카운터/완료 체크의 소비, 젬 완료 보상 순서와 재접속 복원 계약은 미확정이다.** 양성 UI 경로는 퀘스트 안내 통지의 GameTipsLayout 제출이다. 게임·서버·포트 실행, 제품 코드 수정, 원본/저장 수정, git commit은 하지 않았다.

근거 루트 `R/`는 `work/local_server_rea_20261016/`이다. 주소는 선호 base `0x140000000`의 **RVA**, opcode도 **16진수**다. 상세 분석과 선정 원문은 [run405 packets](../../local_server_rea_20261016/run405_quest_state_display/packets.md), [UI/resources](../../local_server_rea_20261016/run405_quest_state_display/ui_resources.md)에 있다. 기존 run403·run30/41·run383/392·shared-api/HANDOFF와 M2_NPC_MENUS·M1_REWARD_PACKETS를 먼저 재사용했다.

## 출발점: 젬 대사는 legacy 메뉴 계약이다

run403의 정확한 판정은 **questcomplete만 전용 local handler**라는 것이다. queststart는 초기 등록29개에 없어 generic HACTION fallback 후보다. 실제 런타임 추가 등록 여부는 UNKNOWN이다. 전용 `5C5950`도 `4ED4`를 보내며 f1은 현재 UML 문맥, f2는 action, f4/f5는 좌표다. 비어있지 않은 resolved cookie만 `DF660`의 반환 AL로 변환하여 **길이1 f3**에 넣는다. 그 byte의 업무 의미는 미확정이며 quest ID로 해석하지 않는다. 근거: `R/run403_service_npc_dialogs/quest_resources.md:29`, `:35`, `:37` 및 `quest_native.json:387`, `:415`, `:495`.

`jem1/9` 수락, `jem3/4` 반납과 `jem8/10` 결과 대사는 원 자원으로 확인됐다. 이는 서버가 실제로 발급한 단계/보상/저장 결과의 관측이 아니다. **아래 05xx 진행 체계와 이 젬/군터 4ED4 메뉴를 잇는 caller/응답은 아직 없다.**

## 진행·완료 패킷: 존재와 필드는 확정, 화면 소비는 별도

등록 상수→factory→publisher→typed wrapper→parser/IsInitialized를 추적했다. R=required, O=optional이다. u32/i64/enum/bool은 wire0, message는 wire2이며 i64는 int64로 zigzag가 아니다. 아래 필드 의미를 ID·시간·완료 여부로 추측하여 확정하지 않는다.

| S2C opcode / 타입 | 확정 wire 구조 | 원 접점 |
|---|---|---|
| `0579 SC_QUEST_PROGRESS_ACK` | f1 repeated QuestProgress; outer required scalar 없음. 각 child 초기화 검사 | registry `293AF9`, parser `2E2940`, schema `15FDD80`, init `73C9D0` |
| `057A SC_QUEST_PROGRESS_UPDATE_NOTI` | f1 R QuestProgress | registry `293B1D`, parser `2E2550`, schema `15FDD20`, init `73CD70` |
| `057C SC_QUEST_REVEAL_ACK` | f1 R enum, f2 R u32 | registry `293B41`, schema `15FE3E8` |
| `057E SC_QUEST_START_ACK` | f1 R enum, f2 R u32 | registry `293B65`, schema `15FE310` |
| `0580 SC_QUEST_FINISH_ACK` | f1 R enum, f2 R u32 | registry `293B89`, schema `15FE220` |
| `0581 SC_QUEST_FINISH_NOTI` | f1 R u32 | registry `293BAD`, schema `15FE1C8` |
| `0583 SC_QUEST_TELEPORT_ACK` | f1 R enum, f2 R u32 | registry `293BD1`, schema `15FE0F0` |
| `0585 SC_QUEST_SHOW_IN_WINDOW_ACK` | f1 R enum, f2 R u32, f3 O bool | registry `293BF5`, schema `15FE720` |
| `0588 SC_QUEST_DIALOG_NOTI` | f1 R u32, f2 R u32 | registry `293C3D`, publisher `3102A0`, event `17F70C0`, schema `15FE658` |

**QuestProgress** (`15FDDE0`): f1 R u32, f2 R int64, f3 O int64, f4 repeated ObjectiveProgress, f5 O bool. init `73C5B0`의 mask5는 f1/f2만 요구한다. **ObjectiveProgress** (`15FDF28`): f1 R u32, f2 O u32, f3 O u32; init `73C170`은 bit0만 요구한다. 숫자 형식·presence는 확정했지만 f1=퀘스트ID, f2/3=시작/완료시각, f5=완료마크, child f2/3=현재/목표량이라는 의미 대응은 **UNKNOWN**이다. 빈0579의 clear/replace 의미도 미확정이다.

정확 원문: `R/run405_quest_state_display/packets.md:15`, `:37`, `:47`; `packets_traces.json`, `packets_schemas.json`, `packets_schema-15fdde0.json`, `packets_schema-15fdf28.json`. 0588 외8종은 복원 code의 exact RIP event 참조 검색에서 constructor/publisher/destructor만 회수했다. 간접/동적 등록을 배제하지 않으며 **패킷 존재를 현재 진행창 표시 성공으로 확대하지 않는다**.

## 실제로 연결된 UI

`0588 → event17F70C0 → 4E93F0 GameTipSubsystem 구독 → callback4E9AC0 → f2(raw24) → GameTipsLayout(문자열1199010) → 4E9EC4/3E00D0(operation1)`까지 정적 연결했다. 옵션/상태/ContentEntry의 원 조건을 거치며 못 여는 분기는 receiver+20 메모리 큐에 보류한다. **ContentEntry 제출 확인이며 렌더·입력 성공은 UNRUN**이다. 근거: `R/run405_quest_state_display/ui_resources.md:11`, `ui_dialog_subscriber.json:246`, `ui_dialog_callback.json:283`, `:1350`, `:1635`.

current catalog의 `gametips/gametipslayout.csb`·`gametipslayoutscene.csb`는 기존 identical 판정이다(`work/asset_data_analysis/current/catalog.tsv:1393`, `:1394`). 별도 퀘스트 목록/진행 창은 확보한 자원명·RTTI 및 위 소비 경계에서 **미입증**이며 전역 부재를 뜻하지 않는다. `SHOW_IN_WINDOW_ACK`라는 이름만으로 창 존재를 확정하지 않는다.

`lyraEv5.uml:8`의 `misc_quest_receipt`는 `A463C0/A49048`에서 동적 영수증을 만들고 `A49557`의 현지화11734 보수 문구를 소비한다. 대사 안 영수증이며 젬/군터의 저널·목표량 표시와 연결되지 않았다(`ui_resources.md:27`). `item_usage_display`의 quest 분류도 퀘스트 아이템 분류이며 캐릭터 진행 기록이 아니다.

## 완료 보상 표시와 순서

| 표시 | 확정된 소비 | 아직 확정하지 못한 것 |
|---|---|---|
| 신규 아이템 `0964` | outer f1 repeated ItemInfo, f2 O bool, f3 O u32. ItemInfo f1 R u32 UID, f2 O i32 template, f4 O u64 수량. InventorySubsystem의 append 분기 `4F6227→509390→3DF600` | protobuf 최소와 표시 가능한 ItemInfo 최소는 다르다. 퀘스트별 보상 template·수량·완료 ACK와의 순서는 UNKNOWN |
| 기존 스택 `0965` | f1 R u32 기존 UID, f4 O u64 새 절대잔량. 없는 UID는 skip. 제거는 별도0978 | 신규 보상도 항상0964라는 규칙은 아님. 퀘스트 완료와의 순서는 UNKNOWN |
| 경험치·레벨 `4E38 SC_STATUS` | f26 O double(wire1)은 EXP 퍼센트→보호 status+18→HUD 소수4자리/게이지. f2 R i32 레벨 비교가 상승 효과2127/Level_XXX 경로를 시작 | 누적 raw EXP가 아니며 전체 required status를 보존해야 함. 공식 퀘스트 EXP 계산식·보상 순서는 UNKNOWN |
| 코드형 메시지 `4EEA` | f1 R i32 메시지ID, f2 repeated 인자, f3 O enum, f4 O length-delimited, f5 O i32. `46A700/469A50→46B920`에서 현지화·인자 치환 후 채팅 목록 | 완료 메시지ID/인자 및 앞뒤 패킷 순서는 UNKNOWN. f4를 자유 본문으로 확정하지 않음 |

근거: `R/run405_quest_state_display/packets.md:55`, `:57`, `:58`; 기존 `R/run30_inventory_first_wire/findings.md:24`, `R/run41_inventory_update/findings.md:21`, `M1_REWARD_PACKETS.md:11`, `CHAT_EVIDENCE.md:60`.

**`0964 → 4E38 → 4EEA`를 강제하는 퀘스트 완료 소비 계약은 회수하지 못했다.** 각 통지는 독립 decoder/event/소비 경로이며 이것만으로 임의 재정렬의 안전성도 증명되지 않는다. 현재 로컬 GET·kill 순서는 해당 backend 계보의 정책이다. `tools/local_original_session/world_feature_quest.py:58`은 완료를 `QUEST_REWARD_AND_CLASS_STATE_ATOMIC_OWNER_UNRESOLVED`로 거절하므로 로컬 실제 완료 순서도 이번 조사 근거가 아니다.

## 저장·복원 기대 형태와 남은 계약

클라이언트에는 위 QuestProgress wire 구조가 있지만 **이를 그대로 서버 저장 형식으로 써야 한다는 근거는 없다**. 재접속 때0579 목록이 오는지,057A 증분을 언제 적용하는지, 완료0581 뒤 제거/표시가 어떻게 바뀌는지와 젬 상태의 관계는 UNKNOWN이다. `imported/bin/quest.bin`은 정적 정의 자료이며 per-character 진행 저장 근거가 아니다. QuestDBInfoT RTTI나 GameTip의 메모리 큐도 디스크 저장 형식의 증거가 아니다(`ui_resources.md:35`).

클라이언트 로컬 디스크의 진행 저장·writer·복원 reader는 선택 경로에서 미회수다. 서버가 권위 있는 수락/목표/완료 상태를 저장하고 원 응답으로 복원하는 방향은 **구현 추론**이며 Classic의 정확 저장 schema·로그인 replay 순서로 확정하지 않는다. 현재 메뉴 수락 preview도 로컬 정책이다.

## 근거 계보·검토 범위

CONTROL inherited SHA `9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`와 UI/legacy c822 restored SHA `c822838351d774a2022af434829a36dbd9bee030bf22182b834ca4e8659701a9`를 구분했다. `packets_identity_selected.json`의 **19선정창**(9종 registry,0588 publisher,0579/057A/0588 wrapper·proto vtable·schema metadata)은 두 carrier에서 동일했다. 이는 선정창 동일성뿐이며 전체 parser/이미지·현재 런타임 동등성은 아니다. metadata를 exec-only buffer에서 읽은 무효 비교6건은 원오류로 보존했고 PE section 매핑으로 바로잡았다.

기존 source reader/스크립트·보존 section·PData·capstone을 재사용했다. 새 guard/검증 도구·전수 hash 검사는 만들지 않았다. 메인 검토는 작성된 패킷/UI 문서·schema 원문·19선정창 결과와 참조를 확인했다. 원본 실행·화면·정식 PASS는 없으며 미확정의 원인은 필요한 소비 경로/실행 입력 부재다. 쓰기는 run405와 이 문서뿐이다.

## 사용자 화면 실험안 — 미실행

후속 시험 담당 한 명이 정상 직업·상태의 **젬 한 의뢰**를 선택→실제4E43/4E44 stem→수락입력4ED4→정상 목표 획득→반납입력으로 진행한다. 같은 build/session에서 전체 S2C ordinal, inventory UID/수량, full4E38.f2/f26,4EEA ID/인자, 대사/게임팁/목록/카운터/완료 화면을 함께 대응한다. 특히0579/057A/0580/0581/0588이 실제 오는지 확인한다. 실제 메뉴 문맥·cookie를 보존하고 임의 quest/tip ID·상태 강제를 쓰지 않는다.

정상 종료/FIRSTclose 후 같은 캐릭터 재접속에서 초기 RX 순서·NPC 발급 stem·재료·진행/완료 표시를 비교한다. 게임은 기존 owned non-input desktop/Job에서 한 번에 하나만 실행하며 사용자 포커스·커서·전역 입력에 간섭하지 않는다. 실패·미표시·UNKNOWN을 그대로 남긴다. 이 실험은 이번에 실행하지 않았다.
