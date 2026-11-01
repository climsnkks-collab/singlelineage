# 버프 HUD·잔여시간 / 낮밤 게임시간 원본 근거

2026-10-26 정적 REA 분석과 2026-10-29 소모품 HUD 후속 조사 기록이다. 아래 날짜별 범위를 구별한다. 원본 게임·포트 시험·live attach는 실행하지 않았으며 화면·입력·실제 동작 PASS가 아니다.

## 마법 HUD 기본 송신 (2026-10-29 후속)

**지원 마법 28개의 positive CommonSpell.f3와 실제 SpellIcon atlas frame을 연결해 4E91을 기본 송신한다.** `world_feature_magic.py:28`의 명시 매핑만 쓰며 임의 transient K를 발급하지 않는다. `:112`는 기본 on이고 `SL_PLAYER_MAGIC_BUFF_UI=0`으로만 명시 비활성화한다. 아래의 옛 소모품 조사 및 `PLAYER_MAGIC_EVIDENCE.md:173,193`의 마법 HUD opt-in/transient K 설명은 당시 보존 기록이며, 현재 구현은 이 절로 대체한다. 기존 저장 형식·지속시간·오프라인 차감 정책은 그대로다.

근거는 W68의 **CommonSpell+50(f3)와 수신 Buff row+10 비교**(`44378C..443797`, `443889..443890`), 수신 f4→config+10→row+10(`462BD3..462BE6`, `46024C..46024F`), positive f4→K(`462D20..462D2C`)다. 이는 아래 소모품 후속 절에 보존된 원 분석이며 새 live 관측이 아니다. **추론:** 같은 CommonSpell/f4 숫자 namespace를 마법 catalog의 positive f3에도 적용한다. 공식 서버의 주문별 실제 발급 record/전체 optional 조합 복원으로 주장하지 않는다. K→HUD→FrameCache 및 정상 loader의 SpellIcon 등록은 아래 `4E91 → Buff model → HUD`와 W68 loader `35A6E8→35C7B0→35CB20→BD8679 BDA290`를 재사용한다. CommonSpell.f4의 미확정 의미를 근거로 삼지 않았다.

다음 줄은 `work/source_game_data/native-dump-v1.jsonl`의 spell 행과 `work/local_resource_provider/assets/icon/spellicon/spellicon_00.plist`의 exact `<key>K.png</key>` 행이다. **28은 매핑 행 수이며 28종의 실제 발급/화면 성공 개수가 아니다.** 기존 buffs/effects authority에 없는 항목은 만들지 않는다. 예컨대 catalog10은 별도 poison authority이므로 이 sync가 poison을 임의로 key10 버프로 재발급하지 않는다. 이 매핑 안에 K 중복은 없고 현재 소모품 481/486/5399/484와도 겹치지 않는다. 현재 PlayerMagic에 없는 haste42는 추가하지 않았다. 향후 같은 K를 쓰는 주문을 추가하면 공통 icon 수명을 먼저 연결해야 한다.

| catalog | K=f3 | dump 행 | plist 행 |
|---:|---:|---:|---:|
| 2 | 485 | 2220 | 2581 |
| 7 | 777 | 2225 | 3660 |
| 10 | 5319 | 2228 | 2672 |
| 11 | 5265 | 2229 | 2620 |
| 13 | 757 | 2231 | 3400 |
| 19 | 5318 | 2237 | 2659 |
| 20 | 5316 | 2238 | 2646 |
| 25 | 483 | 2242 | 2555 |
| 28 | 480 | 2245 | 2516 |
| 30 | 748 | 2247 | 3296 |
| 31 | 795 | 2248 | 3751 |
| 32 | 5270 | 2249 | 2633 |
| 39 | 751 | 2256 | 3335 |
| 86 | 1626 | 2287 | 267 |
| 87 | 1889 | 2288 | 462 |
| 88 | 1883 | 2289 | 423 |
| 128 | 813 | 2297 | 3894 |
| 136 | 745 | 2301 | 3257 |
| 137 | 804 | 2302 | 3855 |
| 147 | 774 | 2306 | 3621 |
| 148 | 855 | 2307 | 4102 |
| 150 | 763 | 2309 | 3478 |
| 151 | 766 | 2310 | 3517 |
| 152 | 1834 | 2311 | 371 |
| 162 | 738 | 2320 | 3218 |
| 165 | 827 | 2322 | 3985 |
| 167 | 783 | 2323 | 3686 |
| 169 | 1758 | 2324 | 358 |

송신은 `world_feature_magic.py:500`의 기존 sync에서 살아 있는 buffs/effects의 **실제 deadline-now**를 공용 encoder의 ceil 초로 투영한다. catalog positive f3가 없는 Light 등은 생략하며 HUD만 독립 생성하지 않는다. tick `:480`, enter `:696`, detach `:730`, death `:767`의 기존 소유 경로를 재사용한다. 만료/해제/사망은 같은 K remove, 재시작/복원은 authority에 남은 시간만 다시 보낸다. HUD는 받은 PC 자신의 outbox에만 보낸다.

### 여전히 보류한 시전·대상 효과·인챈트

- `SPELL_DISPLAY_EVIDENCE.md:45`의 주문별 action18/19 선택은 UNKNOWN이고 `:49,50,54` 표의 Heal0→744/ExtraHeal18→829/Shield2→221은 자원 이름에 근거한 LOCAL 후보다. `SL_SPELL_EXP` 기본 off를 유지한다. gated 후보만 `world_feature_magic.py:785`에서 own f13=true로 보완했다(REA399 `attack/findings.md:29`, own false/absent 생략). ExtraHeal은 file744를 공유해도 sprite829로 보내며, 다른 heal/shield key에 744/221을 kind로 상속하지 않는다. 공격 projectile f6/f7·raw 좌표도 보류한다. uint32 대상 UID 절단은 하지 않는다.
- 동료의 동일 후보 송신은 기존 `world_feature_companion.py`의 display gate 안에 있고 이번 쓰기 범위 밖이다. 기본 주변 효과 송신 완료로 표시하지 않는다. 마법 HUD를 동료의 주인 HUD에 대신 발급하지 않았다.
- 인챈트 0967은 기존 [run393 source-index.json](../../local_server_rea_20261016/run393_item_target_use/source-index.json:377)의 consumer UNKNOWN을 유지한다. 부모의 이번 read-only 추가 조회에서도 event `17F9940..17F9A00` direct RIP 후보는 init8AA0/publish30B500/destructor10944D0뿐이었다. dispatch2770B0는 node+58 callback→vptr+10 간접 호출(`27713C..27714F`)이며 실제 callback RVA와 required f1..5 의미·성공/실패 enum이 첫 부족 입력이다. 현대 메시지 ID도 미확정이므로 기본 결과 안내를 발급하지 않는다.

### 이번 검증의 원결과

지정 명령 1회 `python -X utf8 -B -m unittest tools.local_original_session.world_magic_tests tools.local_original_session.world_item_effects_tests`: **121 tests / 18.513초 / failures=7, errors=18 / exit1**. Temp의 magic/consumable pending 파일 생성 PermissionError 및 cleanup WinError5, 저장 후속 assertion 실패가 포함됐다. 새 기본설정 시험 fixture의 `_world_magic_combat_profile` AttributeError도 1개 포함되므로 전부 환경 오류라고 설명하지 않는다.

부모의 추가 시험 금지 메시지가 도착하기 전에 새 직접 영향 메모리 시험 6개를 실행했다: **6 tests / 2.085초 / errors=1 / exit1**. key refresh/remove, mapping 충돌, 실제 tick/death/restart/복원 잔여, status 제거/미매핑 생략, gated own f13·ExtraHeal829 범위 5개가 통과했다. 기본설정 fixture는 모듈 전역 `_world_magic_consumers`를 mock하지 않아 실패했고 fixture를 수정했으나 **수정 후 재실행하지 않았다**. Temp 경로/권한 우회·파일 시험 재시도·추가 게임/포트 실행은 없다. 전체 통과·저장 성공·원본 화면 PASS가 아니다.

## PC 소모품 재접속 잔여시간 저장 (2026-10-29)

`world_item_effects.py`의 기존 `ConsumableState` / `ConsumableStore`에 소모품 잔여시간을 연결했다. 아래 참고 L1J의 저장 대상과 오프라인 처리만 backend 정책으로 재사용하며 원본 클라이언트 서버 정책으로 주장하지 않는다. 동료·launcher·시험 프로필·원본 자원·사용자 저장은 수정하지 않았다.

### L1J 원문 확인

이 절의 기준 루트는 `D:/SingleLineageRef/l1j-en-classic/src/l1j/server/server/`다.

- `datatables/CharBuffTable.java:83-97`의 `buffSkill`에는 `1000`, `1001`, `STATUS_ELFBRAVE`, `1002`가 있다. `model/skill/L1SkillId.java:423-431,455`는 각각 brave1000·haste1001·blue1002·elfbrave1016, wisdom1004를 정의한다. **wisdom1004는 이 whitelist에 없다.** 따라서 기존 Python 지혜 저장을 L1J와 동일한 저장 대상이라고 설명하지 않는다.
- `CharBuffTable.java:138-147`은 `getSkillEffectTimeSec`가 양수인 항목만 저장한다. `:105-109`는 `char_obj_id / skill_id / remaining_time / poly_id`를 INSERT한다. `network/Client.java:224-226`은 logout에서 DeleteBuff→SaveBuff→clearSkillEffectTimer 순서다.
- `clientpackets/C_LoginToServer.java:598-624`는 저장 `remaining_time`을 그대로 읽고 brave/elfbrave/haste의 속도 상태·패킷과 `remaining_time * 1000` 타이머를 재설정하며 blue도 같은 남은 시간으로 복원한다. 이 선택된 저장·로그인 경로에는 로그아웃 시각 차감이 없다. **새 speed/blue 저장의 오프라인 잔여시간 정지 정책**은 이 원문에 근거한다.
- 기존 명시 매핑은 초록17→40013, 강화495→40018, 용기296→40014, 파랑492→40015다. `C_ItemUSe.java:2718,2799`는 haste, `:2810-2815,2910,2926`은 brave/elfbrave와 잔여시간, `:2937,2954`는 blue 상태다. 이미 지원하던 요정 와퍼86→40068과 악마의 피1408→40031도 `model/item/L1ItemId.java:90-92`, `C_ItemUSe.java:2826-2829,2858-2859,2905-2926`에서 같은 저장 whitelist의 elfbrave/brave 경로를 사용하므로 저장한다. 이 둘에 용기296의 HUD K를 대신 발급하지 않는다.

### Python 연결과 호환성

- 기존 `consumable-effects.json` version1 행에 optional `potion_remaining`을 추가했다. 키는 실제 사용 template의 십진 문자열이고 값은 양수 남은 초다. 예전 행·pending intent도 그대로 읽으며 새 UID·kit·CAS·비용 계약을 만들지 않는다. 신규 필드를 모르는 과거 코드로 되돌리는 호환성은 제공하지 않는다.
- before_leave에서 combat binding이 살아 있을 때 직렬화해 기존 atomic writer로 저장한다. `before_pc_leave` 등록 이벤트는 combat state가 제거되기 전에 메모리 잔여시간을 정지한다. runtime stop에서도 아직 선택된 PC를 저장한 뒤 기존 tick/event를 해제한다. 사망·이미 만료된 항목은 저장·복원하지 않는다.
- 서버 시작 시 저장 행을 읽어도 새 potion 시간은 정지 상태로 둔다. 실제 PC binding 뒤 after_enter에서 한 번만 복원한다. 속도는 기존 `WorldView.apply_buff`의 class/rate/expiry scheduler를 사용하고 최종 합성 `4E5B`를 보낸다. blue는 새 PcState와 기존 자연 MP regen handle에 연결해 기존 소비자만 사용한다. inventory_delivered의 반복 호출은 잔여시간을 재충전하지 않는다.
- W69의 기존 `4E91` helper로 초록/강화/용기/파랑의 실제 남은 시간과 기존 지혜를 owner에게 재송신한다. 원 사용 사운드를 재생하거나 새 HUD mapping을 만들지 않는다.
- 기존 지혜·수중호흡의 `saved_at` walltime 차감은 유지했다. 지혜/호흡은 서버 시작 이후 대기 시간에도 계속 만료되며 새 speed/blue의 오프라인 정지 정책과 구별한다.
- 기존 items registry가 before_leave를 NONCRITICAL로 분류하므로 저장 실패는 `_world_hook_errors`에 기록되고 logout은 진행한다(`world_feature_items.py:560`, `world_registry.py:121-128`). 이 정책을 변경하지 않았으며 파일 저장 실패 시 내구성 성공을 주장하지 않는다. 강제 프로세스 종료 직전 효과까지 저장된다는 보장도 추가하지 않았다.

### 개발 시험과 제한

비파일 관련 회귀 **47개 / 3.034초 / OK**: snapshot 구/신 schema, 새 PC binding에 속도 두 종류·blue 잔여시간 복원, 서버 시작 후 10,000초 대기, 반복 enter 무충전, 기존 speed scheduler 만료·HUD 제거, 복원 blue의 자연 MP bonus, 사망·만료·부적합 class 비복원을 포함한다. 함수 직접 호출의 개발 시험이며 정상 로그인부터의 게임 PASS가 아니다.

```text
python -m unittest -f tools.local_original_session.world_item_effects_tests.BuffIconFrameTests tools.local_original_session.world_item_effects_tests.ItemEffectsTests tools.local_original_session.world_item_effects_tests.BlueRecoveryTests tools.local_original_session.play_feedback_fix_tests.EffectFrameTests tools.local_original_session.play_feedback_fix_tests.DisplayProjectionTests tools.local_original_session.play_feedback_fix_tests.ItemUseProbeTests tools.local_original_session.play_feedback_fix_tests.SettingsAndLoginTests tools.local_original_session.play_feedback_fix_tests.StanceRefreshTests
```

요청한 전체 모듈 실행은 각각 `-f`로 첫 권한 오류에서 중지했다. Temp 경로 변경·권한 상승·우회·해당 파일 시험 재시도는 하지 않았다. 새 fresh-store 디스크 roundtrip 시험은 앞선 기존 파일 시험에서 중지되어 미실행이다.

```text
python -m unittest -f tools.local_original_session.world_item_effects_tests
# 16 tests / 2 errors / exit1. test_commit_and_fresh_store_restore_canonical_name_and_state:
# %LOCALAPPDATA%/Temp/tmpvuusrr5x/.consumable-effects-pending-*.tmp 생성 Errno13,
# 같은 TemporaryDirectory cleanup WinError5.

python -m unittest -f tools.local_original_session.play_feedback_fix_tests
# 수정 전 첫 실행: 6 tests / 1 error; 비물약 icon 제안에서 mock combat.pcs 조회 결함 발견·수정.
# 수정 뒤: 10 tests / 2 errors / exit1. PublishedStartTests setup의
# %LOCALAPPDATA%/Temp/tmpkiwobdn6/characters.json 생성 Errno13, cleanup WinError5.
```

게임·socket·port·live attach·commit은 실행하지 않았다. 전체 파일 저장 회귀와 fresh-process 디스크 재접속은 권한 오류로 미검증이며 전체 통과로 확대하지 않는다.

## 소모품 HUD 후속 조사 (2026-10-29)

**W68 후속 소비 경로 조사로 다섯 소모품의 catalog→수신 f4→K→atlas 연결을 확인해 PC 4E91 발행을 연결했다.** 공식 서버가 실제 보낸 record, 현재 실행의 atlas 등록·HUD 픽셀은 미확인이다. 이 구분 아래 고정 클라이언트 소비에 맞춘 최소 패킷을 사용하며 L1J 전용 wire나 지혜의 time/4를 전용하지 않는다.

### L1J 소모품 아이콘과 시간

이 절의 L1J 경로 기준은 `D:/SingleLineageRef/l1j-en-classic/src/l1j/server/server/`다. 이 참고 서버의 계산·패킷은 확보 클라이언트의 원 wire가 아니다.

| 소모품 | 아이콘 송신·시간 원문 | 갱신·종료 원문 |
|---|---|---|
| 초록 40013 | `clientpackets/C_ItemUSe.java:2722` 일반 300초/축복 350초; `:2796` `S_SkillHaste(id,1,time)`; `:2799` 서버 타이머 `time*1000` | `:2718` 잔여 초, `:2742` STACKING 합산/교체, `:2793` 일반 상한 1800초(usedBGHaste 예외); `model/skill/L1SkillStop.java:555` `S_SkillHaste(id,0,0)` |
| 강화 초록 40018 | `C_ItemUSe.java:2726` 1800초, 같은 `:2796` Haste 경로 | 같은 가속 갱신·종료 경로 |
| 용기 40014 | `C_ItemUSe.java:2819` 일반 300초/축복 350초; `:2922` `S_SkillBrave(id,1,time)`; `:2926` 서버 타이머 `time*1000` | `:2809` 잔여 초, `:2895` 합산 상한 1800초/교체; `L1SkillStop.java:538` 종료 분기 → `:542` `S_SkillBrave(id,0,0)` |
| 파랑 40015 | `C_ItemUSe.java:2941` 일반 600초/축복 700초; `:2951` `S_SkillIconGFX(34,time)`; `:2954` 서버 타이머 `time*1000` | `:2937` 잔여 초, `:2949` 합산 상한 1200초/교체; `L1SkillStop.java:559` 종료 분기는 비어 있음. 클라이언트 자체 아이콘 만료 제거 여부는 미확인 |
| 지혜 40016 | `C_ItemUSe.java:2967` 일반 300초/축복 360초; `:2979` `S_SkillIconWisdomPotion(time/4)`; `:2982` 서버 타이머 `time*1000` | `:2963` 잔여 초, `:2973` 합산 상한 900초/교체; `L1SkillStop.java:565` 종료 분기 → `:569` `S_SkillIconWisdomPotion(0)` |

`serverpackets/S_SkillHaste.java:27`와 `S_SkillBrave.java:27`은 `opcode + D(object id) + C(type) + H(duration)`을 기록한다. `S_SkillIconGFX.java:28`은 `opcode + C(icon id) + H(duration)`이다. `S_SkillIconWisdomPotion.java:27`은 `SKILLICONGFX + C(0x39) + C(0x2c) + H(time)`이며, 호출부의 초÷4와 함께 해석하면 이 전용 duration은 4초 단위다. 이를 4E91 f3의 단위로 전용하지 않는다.

재접속 재송신은 `clientpackets/C_LoginToServer.java:608` 용기, `:618` 가속, `:623` 파랑의 remaining_time에서 확인된다. 이 원문은 이번 Python 서버의 저장·복원 구현 완료를 뜻하지 않는다.

`model/skill/L1SkillUse.java:1284`의 HASTE/GREATER_HASTE는 `:1286`에서 초록 물약과 같은 `S_SkillHaste(id,1,buffIconDuration)`를 보낸다. **L1J에서 같은 아이콘을 사용한다는 추론**을 지지한다. 공식 plaync 도메인의 초록 물약/헤이스트/아이콘 검색에서는 동일 아이콘을 확인할 공식 페이지를 확보하지 못했다. 확보 원본 클라이언트의 동일 K·실제 그림은 UNKNOWN이다.

### 고정 클라이언트 catalog·아이콘과 K 연결

다음 원문 줄은 [native-dump-v1.jsonl](../../source_game_data/native-dump-v1.jsonl)의 실제 item/spell 행이다. 앞선 조사의 숫자 대응 추론은 W68의 `441ABB GetItem → 441AC6 [item+12C](f41) → 441AD8 443590 → 4435C7 GetSpell(370350)` 소비 경로로 보강됐다. 기존 [item/README.md](../../all_table_semantics/item/README.md):48의 UNKNOWN 기록 자체는 보존한다.

| 소모품 | item 원문 행·f41 | 같은 번호 spell 원문 행·f3/f4·f6 | atlas frame 원문 행 |
|---|---|---|---|
| 초록 17 | 968행, 223 | 2330행, 481/481, 300초 | `481.png`, plist 2529행 |
| 강화 초록 495 | 1299행, 226 | 2333행, 481/481, 1800초 | `481.png`, plist 2529행 |
| 용기 296 | 1192행, 224 | 2331행, 486/486, 300초 | `486.png`, plist 2594행 |
| 지혜 297 | 1193행, 231 | 2338행, 484/484, 300초 | `484.png`, plist 2568행 |
| 파랑 492 | 1298행, 232 | 2339행, 5399/5399, 600초 | `5399.png`, plist 2685행 |

atlas 목록은 [spellicon_00.plist](../../local_resource_provider/assets/icon/spellicon/spellicon_00.plist), 그림은 같은 폴더의 `spellicon_00.png`다. 각 이름은 atlas frame이며 별도 PNG 파일이 있다는 뜻은 아니다. 원문 spell42 헤이스트는 dump 2259행에서 f3/f4=481, f6=1200, f7=849다. spell223도 f3/f4=481·f7=849이므로 초록과 헤이스트의 동일 아이콘 **후보**를 지지한다. dump 2268행의 spell51은 홀리 워크(f3/f4=1561)이며 헤이스트로 혼동하지 않는다.

[spell_token/README.md](../../all_table_semantics/spell_token/README.md):9는 CommonSpell f3→`decimal(f3)+".png"` 소비를 **EventPassLayout::CheckGradeBuffSlot**에서만 확인한다. f4 의미는 같은 파일 10행에서 UNKNOWN이다. 이를 일반 4E91 K 생산자로 확대하지 않는다. [REA104 buff_optional_semantics/findings.md](../../local_server_rea_20261016/run104_skill_buff_contract/buff_optional_semantics/findings.md):5와 [REA201 MAIN_REVIEW.md](../../local_server_rea_20261016/run201_buff_wire_identity_frame_key/MAIN_REVIEW.md):3,5,7은 child f1 catalog와 별도의 f4/f5 K를 구별한다. K 선택·원 HUD 소비 RVA는 아래 기존 분석을 재사용한다.

W68은 별도로 `44378C..443797`, `443889..443890`에서 CommonSpell+50(f3)와 현재 Buff row+10 비교를 확인했다. 수신 child f4는 `462BD3..462BE6 → config+10 → 46024C..46024F Row+10`으로 이어지고, `462D20..462D2C`에서 위 양수 값은 K=f4로 선택된다. HUD는 K의 십진 문자열로 SpriteFrameCache map `C+50`을 조회한다(`BFED40 → BD6390`, `BDA150`). 정상 loader는 `35A6E8 → 35C7B0 → 35CB20 → BD8679 BDA290`에서 동일 map에 위 atlas frame 이름을 등록한다. CommonSpell.f4 의미를 근거로 삼은 결론이 아니다. 원 조사: `C:/Users/Chansol/AppData/Local/Temp/claude/D--claude/d2e6d25b-5490-4381-89b5-3fba6fdf4077/scratchpad/w68_result.md` (c822 carrier·보존 exec-buffer의 RVA; live 관측 없음).

### 이번 변경과 미완 계약

- `tools/local_original_session/world_item_effects.py`의 공용 `buff_icon_frame`은 add/update `outer f1=1`, child `{f1:catalog, f2:1, f3:ceil(실제 남은 simulation 초), f4:K}`를 생성한다. child f5~15는 생략하며 부재 시 -1인 필드를 0으로 채우지 않는다. remove는 `outer f1=3`, child `{f4:K}`만 보낸다. `world_feature_magic.py:33`도 같은 helper를 재사용한다.
- 기존 마법 HUD도 확정된 K를 쓰는 선례가 아니다. `world_feature_magic.py:494`의 `_world_magic_sync_icons`는 스펠 key를 catalog로, `:107`의 `0x31000000`부터 할당한 LOCAL transient 값을 f4 K로 보낸다. `world_magic.py:460`의 `data/m3/player_spells.json` 로더와 `:170`의 Spell 생성은 원 K 생산자를 제공하지 않는다. 기존 `SL_PLAYER_MAGIC_BUFF_UI` opt-in과 마법 수명 정책은 유지하며, 이 후보를 원본 아이콘 성공으로 주장하지 않는다.
- PC template별로만 17→223/481, 495→226/481, 296→224/486, 492→232/5399, 297→231/484를 연결했다. 사용 결과와 기존 kit 속도 lane은 주인 송신만 하고, tick 만료·death는 같은 주인의 outbox에 remove한다. published identity는 현재 PcState binding에 묶어 UID 재사용에 옛 정리를 보내지 않는다. 지혜의 저장 전 proposal에는 HUD tracker를 기록하지 않고 기존 commit 성공 뒤 기록한다.
- 재접속은 살아있는 기존 효과 authority의 남은 시간만 재송신한다. 지혜는 기존 ConsumableStore의 offline elapsed 적용 후 남은 deadline을 사용한다. 속도 buff와 파랑 PendingPotion은 기존 leave/rebind에서 사라지는 세션 효과이므로 이번에는 저장 형식을 추가하거나 HUD만 부활시키지 않았다. 지혜의 기존 mage-only admission도 유지한다.
- 동료 `_publish_use`는 공유 `item_use_effect_frame`으로 4ED8과 필요 시 4E5B만 발행한다. PC HUD helper를 호출하지 않는다. 같은 speed kind의 요정 와퍼86·악마의 피1408도 매핑 근거가 없으므로 296의 HUD를 대신 발행하지 않는다.
- 기존 효과 정의는 바꾸지 않았다. 기본 초록300/강화1800/용기300/파랑600/지혜300초는 L1J 일반 물약과 차이가 없다. 초록·용기의 합산 상한1800, 파랑1200도 유지한다. 지혜는 기존 새 300초 refresh이며 L1J의 STACKING 최대900 정책이나 축복 물약 별도 시간을 추가하지 않았다. 4E91 f3는 갱신·재접속 당시 실제 남은 초이고 지혜도 time/4를 적용하지 않는다.
- 순수 wire, 실제 효과 적용·갱신·만료·death·재접속 송신, 실제 kit 속도 송신 lane, 저장 전 proposal 비공개, 실제 동료 `_publish_use`의 HUD 제외를 포함한 비파일 시험 **31개 OK**다. 게임·픽셀·입력 PASS는 없다. 최초 전체 실행은 session_id를 보관하지 않아 최종 결과를 회수하지 못했다. 원인 확인을 위한 coordinator의 동일 명령 재실행은 **126개 / 21.041초 / failures=7, errors=21 / exit 1**이었다. 저장·복원·loopback 준비 시험에서 `%LOCALAPPDATA%/Temp/tmp*` 파일 생성·정리에 `PermissionError [Errno 13] / [WinError 5]`가 확인됐고 저장 후속 assertion 실패도 발생했다. 전체 통과로 판정하지 않으며, 권한 오류 확인 뒤 temp 경로 변경·권한 우회·추가 재시험은 하지 않았다.

전체 회귀 명령(위 권한 오류로 미통과):

```text
python -m unittest tools.local_original_session.world_item_effects_tests tools.local_original_session.world_magic_tests tools.local_original_session.play_feedback_fix_tests
```

파일 접근 없는 관련 시험 확인(31개, 2.247초, OK):

```text
python -m unittest tools.local_original_session.world_item_effects_tests.BuffIconFrameTests tools.local_original_session.world_item_effects_tests.ItemEffectsTests tools.local_original_session.world_item_effects_tests.BlueRecoveryTests
```

## 2026-10-26 정적 분석 결론

- `4E5B SC_SPEED_BONUS_NOTI`는 actor 속도 성분을 갱신한다. 선택한 원 수신 경로에는 HUD 아이콘·잔여시간 필드/소비가 없다. 버프 아이콘은 별도 `4E91 SC_BUFF_ICON_NOTI`다.
- `4E91`의 outer `f1=1/2`는 add/upsert, `3`은 같은 K 제거다. required outer `f2`는 `BuffIconInfo` 메시지다. 이 child의 `f1` catalog, `f2` duration 표시 방식, `f3` 잔여시간, `f4/f5` instance/image K를 구별해야 한다.
- 원 HUD 아이콘은 선택한 **K의 signed 십진수 + `.png`**다. `f1 catalog`나 별도 spell metadata icon을 자동으로 이미지 K에 대입하는 계약이 아니다. 헤이스트/용기의 정당 원 발급 K·현재 atlas frame 대응은 이번 입력에서 확정하지 못했다.
- 남은 시간은 원 `Row+74`에서 실제 tooltip 문자열 생산자로 이어진다. `BuffIconInfo.f2=1`은 남은 시간을 일/시/분/초로 만드는 formatter를 선택한다. 상시 숫자 label·실제 픽셀·tooltip 재갱신 주기는 미관측이다.
- 낮밤 시각은 **`4E49 SC_WORLD_STATUS_NOTI`의 optional `f1:int64 varint`**다. 원 `WorldEnvironmentSubsystem`은 값을 `_gmtime64_s`에 그대로 전달하고 UTC 시·분으로 광도 계수를 계산한다. 따라서 이 consumer의 입력 단위는 **Unix epoch seconds 호환값**이며, 클라이언트 소비식에 L1J의 6배·3초 정렬은 없다.

## 기준 Source와 재사용

새 file-only 추출은 [run391/static_extract.py](../../local_server_rea_20261016/run391_buff_icon_gametime/static_extract.py)의 reader·PData·Capstone을 [followup_v2.py](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2.py)에서 재사용했다. 원 script/산출물은 보존하고 `followup_v2/`에 추가했다.

기준 carrier는 `work/rea_lineage_resume_20261013/main-gameplay/audit/metadata-v2/DERIVED_RESTORED_ANALYSIS_ONLY.exe`, image base `140000000`, inherited SHA256 `c822838351d774a2022af434829a36dbd9bee030bf22182b834ca4e8659701a9`, 26,021,376 bytes다. 원 LC·자원·저장에는 쓰지 않았고 전체 해시를 다시 계산하지 않았다. 실제 loaded image와의 동등성은 주장하지 않는다.

REA104의 `accepted-cache.json` 중 `4627E0/45FD40/4623B0`는 원 CONTROL `9ffc…` 분석 캐시의 재사용이다. 새 c822 함수와 정체를 합치지 않고 `cached-*.json`에 출처/원 pointer를 남겼다. REA104의 wire metadata·REA115/119·REA158/189/199/201·REA206/324의 한계와 source 정정을 그대로 재사용한다.

## 4E91 → Buff model → HUD

원 dispatch는 REA104 [wire packet](../../local_server_rea_20261016/run104_skill_buff_contract/wire_schema/packet.json)의 `responses[5]`에 고정되어 있다: outer schema `15ED770`, typed `SC_BUFF_ICON_NOTI`, event `17FDFC0`, captured `466C30 → 463960 → 4627E0`. required fields는 `f1`과 `f2`이며 outer f1은 closed enum이다. `1/2/3`의 wire 수용과 native 분기는 REA104의 [enum 근거](../../local_server_rea_20261016/run104_skill_buff_contract/wire_schema/buff_enum_validator/packet.json)를 재사용한다. 이 값들이 전체 유효 enum 범위라는 뜻은 아니다.

| BuffIconInfo child | 원 raw offset | 형식 | 확인된 소비 |
|---|---:|---|---|
| f1 | 30 | uint32 varint | Row04 catalog, static spell lookup의 별도 입력 |
| f2 | 34 | closed enum varint | duration formatter 선택. 부재 default는 0 |
| f3 | 38 | uint32 varint | bits를 signed32로 해석 → Row08 → F32 Row74 |
| f4 / f5 | 3C / 40 | uint32 varint | signed 조건으로 K 선택 → Row00·map identity·HUD frame key |

child의 required field는 없다. 전체 15개 필드의 원 schema와 wire type은 REA104 [packet.json](../../local_server_rea_20261016/run104_skill_buff_contract/wire_schema/packet.json)의 `nested_schemas[1]`을 따른다. f3를 float/fixed32 wire나 ms deadline으로 바꾸지 않는다. f10/f14/f15 및 다른 필드의 전체 역할은 이번 범위에서 새로 확정하지 않았다.

K 선택은 `i32(f4)>0 || i32(f5)<=0`이면 `f4 bits`, 그 외에는 `f5 bits`다. 같은 K의 add/upsert는 기존 row를 지운 뒤 새 row를 넣는다. `ready B+280=0`일 때 owned packet이 pending queue에 보관되고 정상 ready callback `462750`이 재생한다. 임의 ready 강제를 전제하지 않는다.

원 Row add event `B+20` → `149030/9A23E0/9A3390`의 `HudBuffLayout` 가입 → `9A46D0/9A0870` → `917AC0 BuffSlot`이다. Row00/08/0C가 Slot18/1C/20으로 전달된다. `Icon` child에 signedDecimal(Slot18)+`.png`가 전달되고, base Sprite `BFED40 → BDA150`은 현재 cache exact frame/한 단계 alias를 찾으며 첫 miss에 `0.png`를 다시 조회한다. 근거: [REA158](../../local_server_rea_20261016/run158_buff_effect_consumer/static-recovery/findings.md), [REA189](../../local_server_rea_20261016/run189_buff_hud_slot_producer_lifetime/MAIN_REVIEW.md), [REA199](../../local_server_rea_20261016/run199_buff_icon_resource_lookup_fallback/MAIN_REVIEW.md), [REA201](../../local_server_rea_20261016/run201_buff_wire_identity_frame_key/MAIN_REVIEW.md).

예를 들어 K65538이면 원 입력은 `65538.png`이며 catalog2/icon385로 자동 정규화되지 않는다. `4E91` 수용·row 생성·fallback 그림은 의도 버프 아이콘의 성공과 구별한다. 헤이스트/용기의 packet 발급·K·선택 frame·pixels를 이번에 관측하지 않았다. 기존 `LOCAL_ITEM_ORIGIN:HASTE`, item17/495와 spell51/53 합성 정책은 로컬 저장/속도 모델이며 원 icon K의 증거가 아니다. [기성 합성 계약](../implementation-3/skill-buff/item-origin-speed-composition-v1/API.md)도 수치/정책·실 delivery 미공급 경계를 명시한다.

## 잔여시간의 실제 문자열 소비

`f3 → signed Row08 → F32 Row74`와 normal update `4623B0`의 `remaining -= XMM1`은 REA104/115를 재사용했다. REA119의 원 frame caller `B539E0 → ED500 → F6F50 → v28 → 4623B0`는 scheduler timescale을 포함한 **simulation seconds**다. 실제 timescale·walltime 1:1은 미관측이며, 별도 `4E41` absolute deadline/held-context epoch 경로를 ordinary f3와 합치지 않는다. [REA119 findings](../../local_server_rea_20261016/run119_buff_delta_normal_caller/worker/findings.md).

새 선택 원문과 캐시를 연결하면 다음과 같다.

1. `462B66..462B77`: child f2가 있을 때 raw34 값을 local `rbp+90`에 복사한다. `462FB3..462FE0`은 그 값을 분기해 formatter를 선택한다. [cached-4627e0.txt](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/cached-4627e0.txt).
2. f2=1 → vtable `11BB500`, invoke slot10=`45EC80`. 입력 i64가 음수이면 별도 localized branch, 0 이상이면 86400/3600/60으로 분해해 숫자와 localized 단위를 조합한다. 최대 두 단위까지 조합하고 남은 초도 읽는 원 분기다. f2=0/2 → `11BB4C8/45F470`, 입력 duration을 사용하지 않는 localized 문구. switch default → `11BB490/45EC00`, 빈 문자열. 이 native default 분기는 임의 enum 값의 wire 수용 증명이 아니다. [rtti-171d5a0.json](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/rtti-171d5a0.json), [function-45ec80.txt](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/function-45ec80.txt), [function-45f470.txt](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/function-45f470.txt), [function-45ec00.txt](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/function-45ec00.txt).
3. `45FE01..45FE4A`: 선택 formatter를 Row+D0 storage/Row+108 callable에 원 clone/move 방식으로 보관한다. [cached-45fd40.txt](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/cached-45fd40.txt).
4. REA189의 `918540` 원 Widget callback은 같은 Slot18 K로 현재 RowPair를 찾고 TooltipContent 생산 callback `1213290`을 `B27DA0`에 넘겨 원 manager `B28EC0`에 게시한다. `1213290` RTTI가 `BuffSlot::Init`의 `TooltipContent` lambda이고 slot10=`918840`인 것을 새로 확인했다. [vtable-1213290.json](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/vtable-1213290.json), [REA189 source-918540.json](../../local_server_rea_20261016/run189_buff_hud_slot_producer_lifetime/ctor_change/source-918540.json).
5. `918840 → 70120 → sameK 460B50 → 460310`: 매 생산 호출에서 현재 Row를 다시 찾는다. `460349`는 현재 Row74 F32를 i64 trunc하고 `460353..460371`은 Row108.v10에 그 값을 전달한다. 만들어진 description+duration 문자열은 `9188B9..9188BF`의 `4E29E0` TooltipContent 생성으로 소비된다. [function-918840.txt](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/function-918840.txt), [function-460310.txt](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/function-460310.txt).

따라서 **아이콘 + 남은 시간 tooltip에 필요한 별도 패킷/필드는 4E91의 K/f3/f2와 원 HUD 소비**다. f3만 넣고 f2를 생략하면 이 선택 경로는 default0 formatter를 쓰므로 숫자 잔여시간 문구를 기대할 근거가 없다. 표시 형식의 정확 한국어·상시 숫자 overlay·tooltip timer 재호출 주기·현재 frame/Widget·입력/픽셀은 이번 정적 분석에서 미관측이다. 원 row/manager/Widget 수명·정상 제거·close는 REA189의 기존 경계를 유지한다.

`4E5B`의 registry `293570/294C70 → 305D50 → 31DC80 → event17FC700 → 4E850`은 Actor UID로 SpeedComponent를 골라 signed q→F32(q)/100을 기존 key에 교체한다. move key0/attack key1은 interval=base/(1+b)를 소비한다. 이 callback에 icon K·duration·TooltipContent 갱신은 없다. 전체 client의 임의 side effect 부재를 주장하는 것이 아니라 **이 선택된 수신 소비는 별개**라는 결론이다. [REA206 contract](../../local_server_rea_20261016/run206_multi_buff_speed_meditation_contract/worker/contract.md), [REA324 contract](../../local_server_rea_20261016/run324_windwalk_speed_field_semantics/contract.md).

## 4E49 게임시간 wire / dispatch

`294BB5`가 factory table `11A9598`을 고르고 `294BBC`가 `edx=4E49`를 원 registrar `292F80`에 준다. table+10의 실제 publisher는 `306480`이다. [xrefs-11a9598.json](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/xrefs-11a9598.json), [game-time-selected-v2.json](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/game-time-selected-v2.json).

`306480 → 31E070`이 RTTI `SC_WORLD_STATUS_NOTI` vptr `11E3AA0`의 wrapper를 만들고 `2C5A00 → DEFFF0`으로 원 message parse를 수행한다. `306521..306528`은 event `17FC340`으로 publish한다. [function-306480.txt](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/function-306480.txt), [function-31e070.txt](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/function-31e070.txt), [기존 rtti-1681508.json](../../local_server_rea_20261016/run391_buff_icon_gametime/rtti-1681508.json).

| SC_WORLD_STATUS_NOTI | 원 raw / wrapper | 형식 | 확인된 의미 |
|---|---|---|---|
| f1 optional | 18 / 20 | signed int64, protobuf varint, tag08 | WorldEnvironment 시각. gmtime64_s 입력 seconds |
| f2 optional | 20 / 28 | signed int32, protobuf varint, tag10 | 의미 UNKNOWN. 선택한 WorldEnvironment callback은 복사만 하고 적용하지 않음 |

원 schema=`15FCCB0`, typecard f1=`10D1`/f2=`1091`, presence bit0/1, IsInitialized=`753FB0`는 무조건 true이므로 required 필드가 없다. [schema-11e3aa0.json](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/schema-11e3aa0.json), [leaf-753fb0.txt](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/leaf-753fb0.txt). typecard의 int64/int32 해석은 REA104 [fast_wire_proof.py](../../local_server_rea_20261016/run104_skill_buff_contract/wire_schema/fast_wire_proof.py)의 같은 family를 재사용했다. 선정 fastslot tag08/10도 JSON에 보존했다. 4E49라는 숫자나 이름만으로 필드 의미를 부여하지 않았다.

## 시각 → 낮밤 consumer

`546A70` 생성자의 vptr `11C84C0` RTTI는 `WorldEnvironmentSubsystem`이다. `546B60..546B71`은 callback `547620`을 event17FC340에 구독한다. callback은 wrapper f1 presence를 검사한 뒤 **64비트 전체를 WorldEnvironment+28에 저장**하고 `547AD0`을 부른다. f1 부재면 이 store/update를 건너뛴다. [vtable-11c84c0.json](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/vtable-11c84c0.json), [function-546a70.txt](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/function-546a70.txt), [function-547620.txt](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/function-547620.txt).

`547AD6..547AFF`: +28 값의 주소를 IAT `10B78D8`에 그대로 준다. restored IAT cell은 hint/name RVA `15BA8DC`, 문자열 `_gmtime64_s`다. 따라서 표준 CRT binding 조건에서 Unix epoch seconds의 UTC `tm`을 얻는다. live IAT/CRT 구현이나 invalid/범위초과 입력 동작은 관측하지 않았다. [imports-selected.json](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/imports-selected.json).

`547B47..547BD5`는 `m = UTC.hour*60 + UTC.minute`와 아래 level을 만들고 `a = night_base + ((level-1)/14)*(1-night_base)`를 `WorldEnvironment+30`에 저장한다. `night_base`는 같은 객체+34이며 ctor 초기값은 float≈0.258(3E841893)이다. float 상수1·14의 원 RVA는126EAB4/126ECBC다.

| 분 m | level |
|---|---|
| m≤360(06:00), m≥1240(20:40) | 1 |
| 360<m<400(06:40) | min(15, trunc((m-360)*15/40)+1) |
| 400≤m≤1200(20:00) | 15 |
| 1200<m<1240 | min(15, trunc((1240-m)*15/40)+1) |

별도 현재 객체+890==1 조건은 계수를0으로 만든다. 그 필드의 의미와 화면 최종 셰이더/픽셀은 이번 선정 범위에서 확정하지 않았다. [function-547ad0.txt](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/function-547ad0.txt), [leaf-547be4.txt](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/leaf-547be4.txt). 후자는 PData 분리 tail의 normal release/RET이고 전체 EH·동시 close 보장은 아니다.

같은 event의 `CharacterDataSubsystem` callback `1153E0`은 f1 low32를+780 protected integer로 보관하고 기존 event를 통지한다. 이 사실을 낮밤 consumer의64비트 절단으로 오해하지 않는다. [vtable-1185340.json](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/vtable-1185340.json), [function-1153e0.txt](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/function-1153e0.txt).

같은 객체의 다른 원 event callback `547540`에도 presence bit4000인 qword가+28→547AD0으로 이어진다. 이 callback의 상위 message 정체/전체 snapshot 필드는 이번에 확정하지 않았다.4E49가 같은 저장/광도 계산을 갱신하는 경로는 확인됐지만 공식 server 발급 주기·클라이언트 독립 ticking은 미관측이다. [function-547540.txt](../../local_server_rea_20261016/run391_buff_icon_gametime/followup_v2/function-547540.txt).

L1J `D:/SingleLineageRef/l1j-en-classic/src/l1j/server/server/serverpackets/S_GameTime.java:33`은 1-byte opcode + writeD(time)인 다른 프로토콜이다. 이 참고 서버의 6배 clock·3초 정렬·낮밤 정책을 클래식4E49의 wire·소비 규칙으로 전용하지 않는다. 실제 클래식 발급 정책은 별도 미확정이다.

## 사용자 직접 화면 실험안 — 이번에는 실행하지 않음

1. 정상 로그인/캐릭터 선택/월드 진입의 같은 Source·시험 저장에서 현재 속도·아이콘·tooltip을 먼저 기록한다. 정당한 헤이스트/용기 적용에 대해 4E5B와4E91 수신, 4E91의 catalog/f2/f3/f4/f5, 선택K·현재 frame/alias·HUD Slot/현재Row를 함께 확인한다. 다른 버프 metadata로 K를 대체하지 않는다.
2. 해당 아이콘의 원 입력으로 tooltip을 열어 초/분 경계와 원 f2=1 formatter 결과·만료 제거를 확인한다. 상시 숫자 overlay가 실제 존재하는지도 구분해 기록한다. 익명 callback 직접 호출이나 ready 강제로 화면 성공을 만들지 않는다.
3. 시험 서버의 같은 정상 월드에서4E49 f1을 각각 UTC05:59/06:20/06:40/20:20/20:40을 나타내는 seconds로 변화시키고 원 WorldEnvironment+28/+30과 화면 변화를 함께 비교한다. 공식 원 서버의 주기/epoch 정책을 확정하려면 정상 온라인 수신을 별도로 관측한다. 임의 시험값을 공식 정책으로 채택하지 않는다.

2026-10-26 분석의 남은 미확정: 헤이스트/용기별 원 catalog→K→frame mapping·정당 발급 wire, 현재 atlas/current HUD 동작, 상시 숫자 label·tooltip 재갱신 주기,4E49 f2 의미·공식 초기/갱신 주기·최종 렌더러. 당시 분석에서는 서버 제품 코드를 변경하지 않았다.
