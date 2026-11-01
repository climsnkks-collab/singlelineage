# 아이템·소모품 확장

## 2차: 남은 18종

이 절이 현재 구현 상태다. 아래 1차 범위·결과는 당시 기록으로 보존하며, 그중 18종 미구현·지혜 무소비 문구는 이 절로 대체한다. 1차 파랑/속도 효과의 세션 수명 정책은 그대로다.

변경 파일은 `world_item_effects.py`, `world_item_effects_tests.py`, `data/m1/item_effects.json`, `data/m1/items_ext/consumables.json`, `hunt_bot_consumables.py`, 이 문서다. 모두 기존 파일의 국소 변경이며 금지된 공용 모듈·사용자 프로필·ACTIVE_TASK·원본 클라이언트는 수정하지 않는다. `manual-play/start-manual-play.ps1`의 핀 대상에는 이번 변경 파일이 없어 핀 갱신은 필요 없다. 커밋 없음.

| ID | 실제 처리와 경계 |
| --- | --- |
| 9/10/37/43/55/59/60/82/83/362 | 영양 각각 5/10/5/8/5/8/20/5/8/3. 포만 상한225, 가득 차면 무소비 거절. 포만3 이상이면 기존 자연 HP 회복 임계가 실제 실행됐을 때 +1HP, live300초마다 포만1 감소. 별도 회복 타이머·오프라인 회복 없음. |
| 22 | 소유 대상의 확인 상태와 `확인됨` 표시. 미확인·숨은 능력 모델은 만들지 않는다. raw0은 현재 양수 보유품 전체, targeted 요청은 해당 소유 UID만 표시한다(LOCAL). 저장 원명·강화 표기는 보존하고 표시용0965 f18만 전송하며 재진입 때 재투영한다. |
| 24 | 실제 착용한 소유 UID의 LOCAL 저주 상태를 제거해 `can_unequip=true`. 해당 저주가 없으면 무소비 거절. 기존 장비 모듈에는 저주 잠금이 없어 원본 장비 해제 행동까지 구현했다고 주장하지 않는다. |
| 297 | 마법사 전용 SP+2, 300초. 타 직업은 `WISDOM_MAGE_REQUIRED` 무소비 거절. 직업마법 연계에서 등록형 `spell_power` 훅으로 단일·범위·흡혈 피해의 기존 `magic_damage(item_sp=2)` 소비자에 연결했다. 회복량은 SP를 사용하지 않는다. |
| 417/418 | 수중 호흡 상태·조회 각각1800/600초. LOCAL 갱신은 기존 만료와 새 만료 중 큰 값으로, 짧은 비늘이 에바 효과를 줄이지 않는다. 수중 환경·익사 피해 소비자는 현재 없다. |
| 806 | `CLAN_MEMBERSHIP_AND_HOME_DESTINATION_UNSUPPLIED`: 혈맹 권한·성/아지트 목적지가 없어 무소비 거절. |
| 15400/15410 | `TOWER_FLOOR1_DESTINATION_AND_ENTRY_UNSUPPLIED` / `TOWER_FLOOR11_DESTINATION_AND_ENTRY_UNSUPPLIED`: 층별 목적지·입장 계약이 없어 무소비 거절. |

새 효과15종의 주 출처는 공식 효과 의미5/15(33.33%:22/24/297/417/418), L1J 영양 참고9/15(60%), 근거 없는 영양 LOCAL fallback1/15(6.67%:9)이다. 수치14셀(영양10·SP1·기간3)만 세면 공식4/14(28.57%), L1J9/14(64.29%), LOCAL1/14(7.14%)다. 포만 상한·영양 변환은 L1J 참고 LOCAL 정책이며, 추가 회복+1·live300초 감소·표시·상태 저장·갱신 정책은 별도 LOCAL이다. 1차 데이터351셀 비율과 분모를 섞지 않는다.

공식 원문은 기존 `work/official_data/raw/item/{22,24,297,417,418}.json`을 재사용했다. 영양 참고는 `D:/SingleLineageRef/l1j-en-classic/db/l1jdb_m10.sql:16510-16526`, 변환·상한은 `src/l1j/server/server/clientpackets/C_ItemUSe.java:1570-1585`다. 정확한 원문 위치와 LOCAL 구분은 효과 데이터 행에도 남겼다.

새 상태는 시험/제품 프로필 옆 `consumable-effects.json`에 UID별로 저장한다. SP/호흡은 남은 시간과 저장 시각을 기록해 재접속·서버 재시작 때 실제 오프라인 경과만큼 차감한다. 음식·확인·저주는 유지하고 사망 시 SP/호흡은 제거한다. 효과 순수 로직과 선택적 adapter는 `world_item_effects.py`에만 있으며 다른 기능의 ctx 메서드를 호출하거나 공통 코어 필수 호출·동명 METHODS 덮어쓰기를 추가하지 않았다.

기존 inventory CAS와 atomic JSON writer를 재사용해 pending intent→수량 CAS→효과 저장→intent 종료 순서로 진행한다. 저장 중단은 시작 시 정확한 before/after에서만 앞으로 복구하며 중복 소모·환불하지 않는다. Q0행은 남겨 기존 장비 anchor를 보존한다. 단위시험에서 교체 후 예외 복구·다른 current와 충돌 시 원상 보존을 확인했다.

검증: 기존 영향4모듈49개와 magic/companion_revive/world78개, 합계127개 성공. 효과 단위25개는49개에 포함한다. 첫 봇 실패의 착용 저장 연결 수정 후 직접 영향32개만 다시 성공했고 나머지17+78개는 직전 성공을 재사용했다(재실행을 합계에 중복 가산하지 않음).

```text
python -B -m unittest tools.local_original_session.world_item_effects_tests tools.local_original_session.world_effect_map_contract_tests tools.local_original_session.world_handler_adapter_tests tools.local_original_session.world_handlers_tests
# 49 tests, OK, 1.684s
python -B -m unittest tools.local_original_session.world_magic_tests tools.local_original_session.world_companion_revive_tests tools.local_original_session.world_tests
# 78 tests, OK, 12.582s
python -B -m unittest tools.local_original_session.world_item_effects_tests tools.local_original_session.world_handler_adapter_tests
# 최종 착용 저장 fallback 반영 후 32 tests, OK, 1.694s
```

실제 봇 명령: `$env:SL_TEST_PORT_BASE='20000'; python -X utf8 -B -m tools.local_original_session.hunt_bot_consumables --scenario consumables`.

최종 [summary](../runs/hunt-consumables-ja1ol41i/summary.json): **SUCCESS 30항목**, 신규 대표5종10/22/24/417/418 각각Q2→1·저장/0965 일치. 기존279/492/495도 각1개 소비해 총8회이며, 기사의297은 명시적 클래스 거절로Q2 보존했다. 정상 Quit→fresh FIRST에서 포만10·identified65537·curses빈집합·수중 잔여1799.914→1798.213초·수량·MP8을 복원했다. 22 표시용0965는 사용 직후와 재접속 때 수신했으며 canonical 이름을 보존했다. fixture의 후행0964가 표시를 덮을 수 있어 최종 native 표시는 미확인이다. 초기 저주는 FIRST 전 선언한 LOCAL 시험 상태이며 실제 저주 장비의 원본 잠금/해제 시험은 아니다.

두 epoch 모두 failure=null·handler_errors=[]·cleanup_complete=true, 영향 Source26개 변경0. 시험 worker 하나가20000/22030을 순차 소유했고 시작 전/종료 후 listener 없음·타 프로세스 종료 없음. [최종 stdout](../runs/consumables-second-20261028-socket-retry.log)은 UTF-8이다. 최종 효과 소스 SHA256은 `72678c5a46c71ba8065bda38728a2784cbba7e46e5ab5851e54d723c52c2005d`, 효과 데이터는 `502e0696ba85e1c8ed975411e6367d6f44582e301c50971f5993b1a6abe86db9`다.

최초 [실패 summary](../runs/hunt-consumables-qrer4bqu/summary.json)와 [stdout](../runs/consumables-second-20261028-socket.log)을 보존했다. 시험 host가 interactive equipment owner를 만들지 않아24가 `NO_OWNED_CURSED_ITEM`으로 무소비 거절·응답 대기 timeout했다. 원 finally·정상 종료·cleanup을 마친 뒤, 실제 저장된 기존 EquipmentStore의 착용 상태를 읽는 선택적 fallback으로 수정하고 새 독립 시험 저장에서 재실행했다. 최초 실패의 소모·저장을 되감거나 성공으로 소급하지 않았고 다른 Source의 결과를 합산하지 않았다.

원본으로 남은 확인은 확인 표기의 실제 최종 표시, 포만 UI·회복량·감소 주기, 공식 SP 피해 공식·native 표시, 수중 환경 소비, 저주 장비 해제 입력·표시다. 로컬 SP 피해 소비 연결은 아래 직업마법 연계 결과를 따른다. 원본 LC 실행·화면 캡처를 하지 않으며 원본 동등성·30분 플레이 완료로 확대하지 않는다.

### 직업마법 연계: 지혜 SP 실제 소비

공식 item297의 SP+2·300초와 마법사 제한, 기존 소모·저장·오프라인 만료·사망 제거를 유지한다. `world_item_effects._world_consumable_spell_power`가 공개 등록 훅으로 값을 기여하고, `world_feature_magic`이 빈 누적값0에서 읽어 기존 `world_combat.magic_damage(..., item_sp=...)`에 전달한다. 상대 기능 메서드·private 상태를 직접 읽지 않는다. `items`를 제거하면 provider도 제거되고, `magic`을 제거하면 소비자가 제거된다.

INT+extraSP의 L1J `L1Magic.java` 계수는 별도 LOCAL backend 정책이며 공식 Classic 계산식으로 주장하지 않는다. 같은 RNG로 SP0/2 피해 증가, 단일·범위·흡혈 전달, 회복 공식에 SP 미전달, 300초 만료와 provider 제외 시0을 기존 마법 단위시험에서 확인한다. 실제 봇은 별도 법사 프로필에서 SP0 시전→수신 UID의297 실제 사용/Q2→1 저장→SP2 실제 피해→정상 Quit/fresh FIRST 복원을 수행한다. 결과 위치는 [CLASS_SPELLS_DATA](CLASS_SPELLS_DATA.md)의 최종 검증 절에 함께 기록한다. 아래1차의 'SP 상태/소비 미연결'은 당시 결과로 보존한다.

## 1차 기록: 범위와 출처

기존 파이썬 서버의 데이터 표와 소모품 효과를 확장한다. 원본 클라이언트·사용자 저장·공용 item-use 계약은 이 시험에서 수정하지 않는다. `data/m1/items.json`의 아이템 등록과 `data/m1/item_effects.json`의 사용 효과 지원은 별도다. 등록만 된 항목을 사용 가능으로 세지 않는다.

추가 데이터는 `items_ext/consumables.json` 29행이며 기존61행을 변경하지 않았다(소모품 범위 합계90행). 이름·클래식 template ID·아이콘·토큰·raw 무게는 확보한 클라이언트 자료를 사용한다. 29행 모두 보관된 공식 item API 응답에서 실제 존재를 확인했다. 공식 API의 URL 형식은 `https://api-goats.plaync.com/linclassic/v2.0/game/item/<ID>?locale=ko-KR`이며 실제 응답과 출처 필드는 기존 `work/official_data/raw/item/` 및 데이터 행에 보존한다. stackable과 교차 버전 L1J ID 대응은 공식 수치로 주장하지 않는 별도 LOCAL 정책이다.

필드 출처351셀 기준 client145(41.31%), official8(2.28%), local_policy198(56.41%), 직접 l1j0이다. 이 비율은 행의 공식 실존 확인29/29(100%)과 다른 분모다. L1J SQL stack 참고26/29(89.66%)도 LOCAL 정책 출처에 포함되며 ID9/15400/15410은 대응 SQL 없이 기존 true 정책을 명시했다. 아이콘·바닥 gfx는 별도 `item_gfx_ext/consumables.json` 29행이다. 기존 kit schema 분류는 potion22(음식10 포함)/scroll5/ammo2이며 실제 효과 종류가 아니다.

| 추가 ID | 이름·분류 | 효과 구현 경계 |
| --- | --- | --- |
| 9, 10, 37, 43, 55, 59, 60, 82, 83, 362 | 괴물 눈 고기, 고기, 당근, 달걀, 레몬, 오렌지, 팬케익, 사과, 바나나, 사탕 | 음식 데이터 등록. 포만감 효과 미구현 |
| 15, 130, 279 | 주홍 물약, 맑은 물약, 엔트의 열매 | 공식 HP 범위 26–68 / 44–107 / 44–107. 범위 안 균등 정수 추첨은 LOCAL 정책 |
| 16, 22, 24 | 불투명 물약, 확인 주문서, 저주 풀기 주문서 | 16은 기존 PlayerMagic blind 상태·server sight=1 소비자에 실제 연결. 22/24는 표시·상태 소비 계약 미연결, 소비0 |
| 126, 248 | 비취 물약, 엔트의 줄기 | 실제 PcAilments.poison 및 PlayerMagic PC poison 상태를 제거하고 기존 저장에 반영. native 독 해제 표시·sound 미확인 |
| 297 | 지혜의 물약 | 공식 SP +2, 300초. SP 실제 소비자 미구현으로 사용 성공·소비를 주장하지 않음 |
| 86, 417, 418, 495, 1408 | 엘븐 와퍼, 에바의 축복, 인어의 비늘, 강화 초록 물약, 악마의 피 | 공식 지속시간 각각 480 / 1800 / 600 / 1800 / 600초. 86/495/1408은 기존 speed 경로, 417/418은 수중 소비자 부재로 소비0 |
| 68, 258 | 은 화살, 미스릴 화살 | 공식 탄약 수치 7/6 및 10/9. potion 효과 범위 밖 |
| 806, 15400, 15410 | 혈맹 귀환, 오만 1층·11층 이동 주문서 | 혈맹 권한·목적지·입장조건·이동 소비 계약 미연결, 소비0 |

지혜의 물약은 데이터 등록만 완료한다. `world_combat.companion_magic_damage`는 extraSP=0을 전제로 하는 기존 계산식이며 이 작업에서 `world_feature_magic`의 SP 소비자를 추가하지 않는다. 마나 즉시회복 물약이라는 별도 아이템은 확인하지 않았다. 파란 물약492의 공식 name2는 “마력 회복 물약”이며, 12119는 퀘스트 재료로 확인되어 일반 소비품으로 추가하지 않았다. 파란 물약492는 기존 아이템의 신규 MP 재생 효과이며, 강화 초록 물약495는 신규 아이템이 기존 haste 효과를 재사용한다. 신규 아이템의 실제 사용 두 종은 495와279로 확인했다.

**효과 미구현18종은 완료가 아니다.** 음식10종, 확인22, 저주풀기24, 지혜297, 에바417, 비늘418, 혈맹귀환806, 오만15400/15410은 `dispatch_owner=unsupported` 등록과 사용 시 무소비 거절만 구현했다.

## 1차 기록: 실제 시험 경계

`tools/local_original_session/hunt_bot_consumables.py`는 기존 `hunt_bot`, `hunt_bot_scenarios.build_epoch`, 저장 kit CAS 및 종료를 재사용한다. 새로운 독립 `runs/hunt-consumables-*` 프로필만 사용한다. 시험 전용 초기값은 `test_knight` kit와 장비, 492/297/495/279 각 수량2, HP1/200·MP1/200, 기존 마을 respawn 좌표이다. 실제 월드 진입 후 HP·MP·시계·UID·준비 상태를 강제하지 않는다.

정상 FIRST → 로그인 → 캐릭터 선택 → 월드 → 서버가 전송한 inventory UID의 CS0960 → 실제 decoder/router → 저장 수량과 응답 → 정상 Quit → fresh FIRST 재접속을 확인한다. 원본 LC 실행·화면·입력·30분 수동 플레이는 실행하지 않으며 이 결과로 원본 화면 동등성을 주장하지 않는다.

파랑 재생의 현재 정책은 기존 자연 MP 회복 임계값·속도를 유지하고 실제 자연 회복 틱에서 보너스를 더한다. 기본 600초·누적 상한1200초와 추가량 `max(WIS,11)-5`는 L1J 참고 LOCAL 정책이다. 강화 초록은 기존 haste interval factor와 4E5B를 사용한다. 파랑·속도 지속효과는 기존 speed와 같은 세션 수명으로 Quit 후 제거되며 현재 MP와 소비 수량만 기존 owner가 저장한다. 이 효과들의 오프라인 지속효과 복원은 구현하지 않는다. 불투명·해독은 기존 PlayerMagic 상태·저장 owner를 사용한다.

## 1차 기록: 검증 결과

단일 시험 worker가 `SL_TEST_PORT_BASE=20000`의 20000/22030 포트를 순차 소유했다. 시작 전·종료 후 listener 없음, 타 프로세스 종료 없음. `--help`는 포트를 열지 않고 성공했다.

실행 명령: PowerShell에서 `$env:SL_TEST_PORT_BASE='20000'` 후 `python -X utf8 -B -m tools.local_original_session.hunt_bot_consumables --scenario consumables`.

결과: **SUCCESS, 15항목, cleanup_complete=true**, 두 epoch의 broker failure null. [summary.json](../runs/hunt-consumables-tx2jitn2/summary.json)과 [stdout 원문](../runs/consumables-ext-20261028-socket.log)을 보존했다(stdout은 PowerShell UTF-16, summary는 UTF-8). 첫 실패·재시도·강제 정리 없음.

| 실제 socket 행동 | 실제 소비·효과·저장 결과 |
| --- | --- |
| 엔트의 열매279 / UID65575 | Q2→1, 저장·0965 일치. HP1→103(+102), 공식 범위44–107 안이며 4E38 수신 |
| 파란 물약492 / UID65572 | Q2→1 저장·0965 일치. 실제16.164초 자연 회복 틱에서 MP1→8=기본1+추가6, 4E38 수신. 월드 진입 후 MP/회복점수/시계 변경 없음 |
| 강화 초록495 / UID65574 | Q2→1 저장·0965 일치. haste 남은1799.998초, combat interval factor1→0.745, 4E5B key0/key1=34. 실제 공격 cadence·native 움직임은 미확인 |
| 지혜의 물약297 / UID65573 | `ITEM_EFFECT_UNSUPPORTED:297`으로 거절, 전체 bag과 Q2 불변, 같은 socket 정상 alive 응답 |
| 정상 Quit → fresh FIRST/로그인/선택/월드 | HP103/MP8·소비된 세 물약Q1·지혜Q2 복원. 기존 세션 지속효과 제거. 두 epoch handler_errors[]·정상 정리 확인 |

이번 영향 소스26개 조합은 `summary.json`의 `source_sha256_start`와 `source_sha256`에 기록했으며 `source_changes_during_run=[]`이다. 핵심 효과 소스는 `world_item_effects.py` SHA256 `14be6af9e54fd07cfe7daf1ca2b16aec81731049729925f8d0a1dd90571cb1a2`, `data/m1/item_effects.json` `36dc0b1274cb17b650654aa12823fccf35952cafebdaade99ff7572d3b41c3f5`이다. 원본 catalog 전수 해시를 추가하지 않았다.

관련 단위119개도 성공했다. 아래 두 명령 결과는 main/구현 worker의 stdout 도구 기록에 있고 별도 로그 파일은 없다. 41개 명령은 main이 같은 소스로 독립 실행한 1.529초 결과를 사용하며 중복41개를119개에 다시 더하지 않는다.

```text
python -B -m unittest tools.local_original_session.world_item_effects_tests tools.local_original_session.world_effect_map_contract_tests tools.local_original_session.world_handler_adapter_tests tools.local_original_session.world_handlers_tests
# 41 tests, OK, 1.529s
python -B -m unittest tools.local_original_session.world_magic_tests tools.local_original_session.world_companion_revive_tests tools.local_original_session.world_tests
# 78 tests, OK, 11.324s
```

수명·중첩·만료·death/leave·재바인드·기존 natural threshold 중복 없음은 개발 단위시험 범위다. 실제 소켓에서600/1800초 자연 만료까지 기다리지는 않았다. 원본에서 확인한 것은 클라이언트 ID·토큰·아이콘/gfx 번호와 공식 API의 존재·표기 수치다. native 아이콘 실표시·화면·입력·가속 cadence·공식 HP 회복의 확률분포는 미확인이다. 파랑·속도 지속효과의 오프라인 복원은 미구현이며, 원본 함수 동등성과 마일스톤 30분 플레이를 통과한 결과가 아니다.
