# 0 송신 미확인 필드 — 정적 분석

2026-10-28 · SOURCE_ONLY. 제품 코드·서버 값·원본·저장·핀·큐 변경 없음. 게임·게임 서버·봇·게임 포트 시험·live attach·온라인 접속은 실행하지 않았다. 주소는 고정 CONTROL의 **RVA**이며 preferred VA는 `0x140000000 + RVA`다. 명령·객체 offset은 16진수다.

## 결론과 서버 값 제안

**`4E31.f6`는 Projectile 자신의 UID 입력이며 일반 Arrow66에서는 클라이언트 UID로 교체된다. `4E95.f2`와 `4F1A.f3`의 업무 의미·공식 정상값은 여전히 UNKNOWN이다.** 현재 명시적 0을 바꿀 근거는 없다. 화살 카탈로그의 f6=66은 별도 필드이므로 함께 구분한다.

근거 등급: **A** = 정적 원명령·형식·값 연결 확인, **B** = A에 근거한 한정 해석/LOCAL 구현 제안, **U** = 소비 또는 의미 미결속. A도 실제 실행·화면·공식 서버 송신을 입증하지 않는다.

| 필드 | reader / 확인된 사용 | 의미·근거 등급 | 서버가 보낼 값 제안 |
|---|---|---|---|
| `4E95.f2` required int32 | DTO reader `53262C`, 저장 `53266A → CharacterData+568`. 저장 이후 reader 미확인 | A: 저장 위치. U: 업무 의미·화면 영향·공식값 | **명시 `f2=0` 유지**. LOCAL 잠정값이며 정상값0의 증거 없음. 필수 presence 유지 |
| `4F1A.f3` required int32 | `54C2A5`, `983375`가 각각 local에 복사. 확인한 두 receiver에서 이후 값 사용 없음 | A: 복사·required 검사. U: 업무 의미·공식값 | **명시 `f3=0` 유지**. MP%·100·표시 flag로 바꾸거나 생략하지 않음 |
| 화살 카탈로그 `CommonItemInfo.f6` | generated copy `68FA71`, serializer `68DBA3`; native item29 값66. 화면 reader 미확인 | A: uint32/+D4/실제66. B: 자원66 대응 후보. U: 업무 의미·최종 표시 소비 | **원본 카탈로그66 보존**. 별도 packet f6=0 송신은 찾지 못함. 이66을 `4E31.f6`에 넣지 않음 |
| `4E31.f6` optional int32 | generated copy `75E65F`, handler `4D1AD → CD104 → descriptor+0`; Arrow66의 `45CC2`에서 UID 교체 | A: Projectile UID 입력·교체. B: 해당 경로의 LOCAL 값0. U: 공식 송신 숫자 | **일반 `f7=66`/subtype3에서 present `f6=0` 유지**. 다른 subtype에 일반화하지 않음 |

`DEFERRED_BACKLOG.md:74`의 “화살 f6 값”은 메시지명이 없는 축약이다. [CHAT_ATTACK_CONTRACTS](CHAT_ATTACK_CONTRACTS.md):150–151은 이를 `4E31.f6`로 구체화한다. 사용자 목록에 두 표현이 있으므로 카탈로그 f6도 따로 조사했다. 현재 명시0 송신은 [world_combat.py](../../../tools/local_original_session/world_combat.py):319–336의 `arrow_id=0 → 4E31.f6`다. **카탈로그 f6와 packet f6는 같은 번호라는 이유로 연결할 수 없다.**

## 분석 기준과 재사용

- 고정 버전 `26.09.29.2001`; inherited CONTROL SHA256 `9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`.
- 분석 carrier [DERIVED_RESTORED_ANALYSIS_ONLY.exe](../../rea_lineage_resume_20261013/main-gameplay/audit/metadata-v2/DERIVED_RESTORED_ANALYSIS_ONLY.exe); 이번 REA open과 일치한 SHA256 `c822838351d774a2022af434829a36dbd9bee030bf22182b834ca4e8659701a9`. header·bootstrap·보호 상태를 복원한 실행파일이 아니다. [TARGET_IDENTITY](../../local_server_rea_20261016/TARGET_IDENTITY.md)의 한계를 승계한다.
- [FIELD_RESOLVE_20261028](FIELD_RESOLVE_20261028.md), run380/402 맵, run381 HP, run384/386 공격, all_table_semantics/item 원문을 재사용했다. 새 전수 해시 검사는 하지 않았다. 현재 disk LC.guard.exe나 현재 실행과의 전체 동등성을 주장하지 않는다.
- 이번 선택 코드창 7개에서 carrier와 보존 CONTROL record의 byte 일치를 직접 확인했다: `532629+47h`, `54C29A+15h`, `983370+Bh`, `4D1AD+18h`, `45C85+40h`, `11A07E+11h`, `59A60+12h`. 이 확인은 해당 창에만 유효하다.

## 1. 4E95 f2 — 저장은 확인, 이후 reader UNKNOWN

### reader와 사용처

형식은 required int32, raw proto+3C다. 맵 consumer 함수 **`5325C0`**의 `53262C: mov ebx,[rbp+0C]`가 DTO의 f2를 읽는다. `532654 → 3EB60`은 typed `CharacterDataSubsystem` pair를 얻고, **`53266A: mov [rax+568],ebx`**가 전체32비트를 저장한다. 분기 없이 저장한다는 사실은 값의 업무 의미를 설명하지 않는다.

원문: [run380/f2_key_evidence.json](../../local_server_rea_20261016/run380_map_transition_receive/f2_key_evidence.json):17,73; raw 형식은 [run380/fields_findings.md](../../local_server_rea_20261016/run380_map_transition_receive/fields_findings.md).

기존 [run402/f2_findings.md](../../local_server_rea_20261016/run402_map_notify_f2_consumer/f2_findings.md)는 getter 직접 참조337곳/owner291개와 primary virtual9개·ctor callback29개를 출발점으로 782 context/617함수를 추적했다. f2 바이트 `+568..56B`와 겹치는 확인된 접근은 두 write다.

- `10FB4C: mov qword ptr [r15+564],rbp`, RBP=0: 생성자 초기화.
- `53266A`: 수신 f2 저장.

인접 `+564`의 4바이트 read, `+570/+578` vector, alignment NOP는 f2 reader가 아니다. `53276B`가 EBX를 이전 map으로 덮은 뒤의 changed-map 비교도 f2 분기로 세지 않는다. 원문: [f2_alias_flow.json](../../local_server_rea_20261016/run402_map_notify_f2_consumer/f2_alias_flow.json), [f2_return_check.json](../../local_server_rea_20261016/run402_map_notify_f2_consumer/f2_return_check.json).

### 이번에 좁힌 간접 경계

기존 FIELD_RESOLVE의 `45349: call [rax+8]` 미확정 중 **ctor의 `119FF0` 등록군이 만든 취소객체**는 더 좁힐 수 있다. `11A07E LEA → 11A085`가 vptr `117E5C8`을 설치한다. 같은 vtable slot8은 **`59A60: add rcx,8 → jmp 5A7C0`**이며 보존 본문은 등록 receiver를 key로 연결을 해제하는 취소 경로다. 이 등록군의 간접 호출을 새 f2 read로 볼 근거는 없다.

출처: [source_hp_binding/source.json](../../source_hp_binding/source.json):3185,3190,3270; [source_hit_ratio_registration/source-evidence.json](../../local_server_rea_20261016/run103_i2_005_hp4ec8_subscriber/notify_consumer_actual257/resume_source_path/hp_consumer_chain/registration_chain/source_hit_ratio_registration/source-evidence.json):11610,11616,13796,13803. 이 결속은 같은 owner key에 다른 경로로 등록된 모든 callable까지 닫지 않는다.

### 의미·화면·값 제안

**U:** 업무 이름·저장 이후 read·화면 효과·공식 sender 값은 찾지 못했다. 기존 분석은 global/member로 탈출한 pointer, stack 인자, 계산 주소, 간접 호출, 반환 alias, non-pdata·동적 코드까지 완결하지 못했다. 따라서 전역 미사용/항상0이라고 결론 내릴 수 없다. 기존 온라인 관측도 `+568..56B`를 수집하지 않았다.

**B:** 현재 `f2=0`을 유지한다. [baseline.json](../../../tools/local_native_login_map_notify_hook/baseline.json)의 `EXPLICIT_LOCAL_SOURCE_BASELINE`, `normal_server_values_proven=false`와 같은 수준이다. 초기화0은 정상 송신0의 증거가 아니다. map ID·층수·수중 여부 등으로 이름을 붙이거나 비0값을 만들 근거가 없다. 현재 송신: [world_core_maps.py](../../../tools/local_original_session/world_core_maps.py):272.

## 2. 4F1A f3 — 두 receiver에서 copy-only

### reader와 사용처

required int32, raw proto+20 / wrapper+28. **`7713C0..7713CA`**의 `not eax; test al,7; sete al`은 f1..3 **presence** 검사이며 f3 값 비교가 아니다.

| receiver | f3 read·local 저장 | 이후 확인한 값 사용 |
|---|---|---|
| Minion `54C230` | `54C2A0 test cl,4 → 54C2A5 [rdx+28] → 54C2A8 [rbp-20]` | complete body에서 이 local을 다시 읽지 않음. `54C301..54C31D → 56710`은 UID f1과 f2만 전달 |
| ActorHudManager `9832F0` | `983370 test cl,4 → 983375 [rdx+28] → 983378 [rbp+17]` | complete body에서 이 local을 다시 읽지 않음. `98349E/9834A2 → 990C20` 및 `9834CF/9834D3 → 995A00`의 값 인수는 f5/f4 |

원문: [f3_gate_selected.txt](../../local_server_rea_20261016/run381_mob_hpbar_receive/f3_gate_selected.txt):9,58,146,256,294; [f3_gate_sources.json](../../local_server_rea_20261016/run381_mob_hpbar_receive/f3_gate_sources.json).

이번에는 기존 View로 두 complete pdata body도 재디코드했다: `54C230..54C378` 105명령, `9832F0..983584` 197명령. 각 f3 stack 영역과 겹치는 직접 RBP operand는 복사 전 vector 초기화와 위 f3 저장뿐이며, 저장 이후 직접 read는 없었다. 이 점검만으로 callee·간접 alias의 전역 부재를 주장하지 않는다.

같은 event1802100의 보존 직접 RIP 참조도 대조했다. [render_hit_event_refs.json](../../local_server_rea_20261016/run381_mob_hpbar_receive/render_hit_event_refs.json):6,46,134,200,293의 LEA5곳은 초기화 `AC94`, publisher `2FB171`, 두 등록 `54A9A5/B33AE4`, 정리 `1097D7A`다. 해당 주소의 직접 RIP LEA/MOV만 재확인한 범위에서 새 receiver 후보는 없었다. event+8·member/global alias·간접 등록·non-pdata·동적 코드는 미완이므로 두 receiver가 전부라는 증명은 아니다.

실제 Pet/Summon HP 게이지 경로는 **별도 f2**다. `54C230 → 56710 → 9829D0`이 signed f2를 `clamp(float(f2),0,100)`으로 바꿔 `LoadingBar_HP+704`에 저장하고 `C1E820`이 폭을 갱신한다. f3는 그 event 인수가 아니다. 출처: [ratio_findings.md](../../local_server_rea_20261016/run381_mob_hpbar_receive/ratio_findings.md):11–25, [render_findings.md](../../local_server_rea_20261016/run381_mob_hpbar_receive/render_findings.md).

### 의미·화면·값 제안

**A:** 확인한 두 receiver의 f3 숫자는 HP/MP 표시·선택 gate로 사용되지 않는다. **U:** 이것은 모든 subscriber의 미사용 증명이나 공식값0의 증명이 아니다. HP%는 f2이고 f3=MP%라는 해석은 근거가 없다. 실제 f3 read→표시 분기 또는 서버 producer가 없어서 업무 의미를 확정하지 못했다.

**B:** [world_feature_pet.py](../../../tools/local_original_session/world_feature_pet.py):47–51의 명시 LOCAL `f3=0`을 유지한다. required이므로 생략하지 않는다. f3만의 화면 영향은 미결속이며 이번에 화면을 실행하지 않았다.

## 3. 화살/탄약 f6 — 카탈로그와 inventory packet 구분

### CommonItemInfo item29.f6

[native-dump-v1.jsonl](../../source_game_data/native-dump-v1.jsonl):978의 item29/$61/화살은 **실제 f6=66**이다. `CommonItemInfo.f6`는 uint32, object+D4, presence bit8(abs136), unset default0이다. default0과 이 행의 실제66은 다르다.

| 위치 | 정적 역할 |
|---|---|
| `15E13C0` | 필드 descriptor 데이터 주소. 실행 reader 함수가 아님 |
| parser `68D9D0`, fast table `15E11D0 → DEC430` | tag `30h`(field6/wire0)를 object+D4에 읽음 |
| copy `68F830`의 **`68FA71`** | `[rdi+D4]` read → `68FA77 [rbx+D4]` write |
| serializer `68D9E0`의 **`68DBA3`** | `[r15+D4]` read → `68DBAA`의 tag30h 직렬화 |

출처: [item/fields.json](../../all_table_semantics/item/fields.json):1072–1177; [item/report.json](../../all_table_semantics/item/report.json):5491,13180. generated parse/copy/serialize는 업무상 reader나 화면 consumer의 증거를 대신하지 않는다. 기존 field ledger의 `consumer_evidence`와 `consumer_candidates`는 비어 있다.

**B:** raw66과 `list.spr #66 arrow`의 자원 대응은 후보 근거다. **U:** CommonItemInfo+D4를 읽어 ground graphics 또는 projectile graphic을 선택하는 실제 consumer는 찾지 못했다. item11의 f6=12도 있으므로 모든 f6를 “탄약 ID”로 명명하지 않는다. [CATALOG_BINDING](../integration-1/item-ground-input-search/CATALOG_BINDING.md):8 및 [run100/worker/findings.md](../../local_server_rea_20261016/run100_item1_ground_graphics_producer/worker/findings.md):37도 catalog f6→ground appearance producer 미결속을 남긴다.

**값 제안:** 원본 item29의66을 보존한다. 이를 0으로 교체하거나 `4E31.f6` UID로 전송할 근거가 없다. 아래 `4E31.f7=66`은 sprite factory consumer가 직접 확인된 별도 계약이며, item f6→packet f7 자동 생산은 미확인이다.

### 별도 “ammo packet f6=0” 여부

현재 [world_ammo.py](../../../tools/local_original_session/world_ammo.py)는 실제 stack UID/template/count를 받아 비용을 제안하며 packet을 생성하지 않는다. [world_core_kit.py](../../../tools/local_original_session/world_core_kit.py):34–60의 소비 통지는 `0965` f1=UID/f4=잔량 또는 `0978` 제거다.

Inventory의 별도 `ItemInfo.f6`는 optional uint64/object+88인 다른 필드다([run30/source-evidence.json](../../local_server_rea_20261016/run30_inventory_first_wire/source-evidence.json):5444–5452). 현재 [inventory.py](../../../tools/local_original_session/inventory.py):28–30의 kit subset 및 [world_handlers.py](../../../tools/local_original_session/world_handlers.py):415–420에는 f6가 없다. 따라서 이 범위에서 **화살 재고의 f6는 생략되며, 명시0 송신 필드를 따로 찾지 못했다.** 생략을 wire0 송신으로 세지 않는다. 이 선택 필드의 업무 의미도 이번 자료로 확정하지 않는다.

## 4. 4E31 f6 — Projectile UID 입력, Arrow66에서는 교체

### reader·UID 소비

1. generated copy **`75E65F`**가 presence bit20h일 때 proto+34의 f6를 복사한다. [function-75e610.asm](../../local_server_rea_20261016/run386_arrow_projectile_gfx/field_contract/function-75e610.asm):25–28.
2. handler **`4C440`**의 **`4D1AD: movsxd rdx,[rbp+44]`**가 f6 int32를 signed64로 읽는다. `CD0B0`의 **`CD104`**가 descriptor+0에 저장한다. [function-4c440.asm](../../local_server_rea_20261016/run384_ranged_attack_display/function-4c440.asm):870, [function-cd0b0.asm](../../local_server_rea_20261016/run384_ranged_attack_display/function-cd0b0.asm):20.
3. base ctor **`40F00 → 40F03`**은 descriptor+0을 Actor+18에 복사하고 **`40C00`**은 Actor+18 UID를 반환한다. handler **`4D673 → 4D682 → 4B140`**은 생성 객체의 최종 UID를 attacker BattleComponent에 전달한다. [function-40ed0.asm](../../local_server_rea_20261016/run386_arrow_projectile_gfx/field_contract/function-40ed0.asm):17–18, [window-40be0-40c70.asm](../../local_server_rea_20261016/run386_arrow_projectile_gfx/field_contract/window-40be0-40c70.asm):20, 앞 handler:1146–1151.

따라서 **A: 생성 Projectile 자신의 UID 입력**이다. f2 attacker UID, f3 target UID, 실제 탄약 stack UID와 구별된다.

### Arrow66 교체와 admission

`f7=66`은 `#66 arrow → effect(3 -1) → row+88=3 → native Arrow factory`를 선택한다. factory **`45550`**의 **`45C85 cmp esi,3 → 45C88 je 45C97`**는 subtype3에서 f14 읽기를 건너뛴다. **`45C97..45CC2`**가 global17B0040의 감소 카운터로 `counter'=counter-1; effectiveUID=counter'-100`을 만들고 **descriptor+0을 덮는다**. 이 경로에서 ctor가 받는 최종 UID는 incoming f6가 아니다.

출처: [run386/findings.md](../../local_server_rea_20261016/run386_arrow_projectile_gfx/findings.md):28–35, [function-45550.asm](../../local_server_rea_20261016/run384_ranged_attack_display/function-45550.asm):404–417, [field_contract/findings.md](../../local_server_rea_20261016/run386_arrow_projectile_gfx/field_contract/findings.md):23–31.

덮기 전 f6 값 admission도 대조했다. handler **`4D146`**은 descriptor+98을0으로 초기화하므로 factory **`455B5 → 455BF`**가 config 조건부 ownUID 비교 `455D7`을 건너뛴다. record+A0 없는 별도 `46370` 경로도 이번 kind8에는 적용되지 않는다. 고정 Arrow 경로에서 incoming f6=0을 거절하는 검사는 확인하지 않았다. 카운터의 시작값은 snapshot에서 unmapped라 실제 생성 UID 숫자는 UNKNOWN이다.

### 화면 영향·값 제안

**`4CFFA..4D010`은 f6/f7 둘의 presence를 검사한다.** f6 생략은 projectile 후처리를 건너뛰지만 **present0**은 이 검사를 통과한다. 다만 own self의 f13=true 등 앞 admission, 실제 좌표, factory 성공과 발사→비행→도착→피격→정리는 별도 조건이다. 이번에 해당 화면·입력·수명을 관측하지 않았다.

**B:** 일반 Arrow66/subtype3에 한해 명시 `f6=0` 유지. attacker/target/item UID, 임의 -101 또는 새 서버 projectile UID로 바꿀 근거가 없다. 다른 subtype은 incoming UID를 보존할 수 있어 이 제안을 일반화하지 않는다. f14는 enum1/2·생략 기본1이며 subtype3의 UID 교체에서는 읽지 않는다. **U:** 공식 PC/remote 궁수의 실제 f6 숫자·presence·최종 화면은 미확인이다.

## 검증·남은 최소 입력

읽기 확인은 `Get-Content -Encoding UTF8 <근거>`, `rg -n <주소/필드> <범위>` 및 기존 `f2_research.View`의 선택 byte 재디코드로 수행했다. `python -X utf8 -B -`의 선택7개 창 carrier/record 비교는 전부 True, exit0이었다. 같은 방식의 문서 링크 점검도45개/누락0, exit0이었다. `git -c core.autocrlf=false diff --no-index --check -- NUL <이 문서>`는 공백 진단 출력0이며 exit1은 NUL과 새 파일의 차이를 뜻한다. 서버 코드 변경이 없어서 봇·서버 시험은 수행하지 않았다.

### 추가 REA 반환과 종료 — 완료

REA6.4.0/Ghidra12.1.4 지속 세션에 초기화 제한 `REA_GHIDRA_STARTUP_TIMEOUT_MS=1800000`과 호출 대기1900초를 적용했다. 분석 프로세스 환경만 설정했으며 함수별 새 timeout 인수나 게임 실행 설정이 아니다. **첫 함수는1378.195초(약23분)에 반환**, 나머지3개 함수와 xref도 성공했다. [server.stderr.log](C:/Users/Chansol/AppData/Local/Temp/unknown_fields_rea_20261028_143659/server.stderr.log)에 각 호출 `status=ok`가 남아 있다. [close.json](C:/Users/Chansol/AppData/Local/Temp/unknown_fields_rea_20261028_143659/close.json)의 정상 반환과 로그의 close350.04ms를 확인했고, 해당 Ghidra PID81168도 종료됐다. 시간초과·함수 null·재시도는 없었다.

공통 analysis-profile digest는 `249564812a8d83b9b3f461098fc485ccde60c516d4497547a124081c91d654bf`다. 아래 ID는 이번 반환의 Evidence ID이며 원 JSON을 Temp에 보존했다.

| 조회·원 JSON | Evidence ID | 기존 원문과 대조한 결과 |
|---|---|---|
| [54C230 pseudocode](C:/Users/Chansol/AppData/Local/Temp/unknown_fields_rea_20261028_143659/pseudo_0x54c230.json) | `ev_299cf4cd9dcbf0ded0207ddbac0b9d50c1df36110a0da7cdc239bb167ec67a62` | pseudocode43행은 f3를 `uStack_3c` 상위32비트에 복사한다. 64–65행의56710 인수는 하위32비트 f2다. f3 업무 의미 추가확정 없음 |
| [9832F0 pseudocode](C:/Users/Chansol/AppData/Local/Temp/unknown_fields_rea_20261028_143659/pseudo_0x9832f0.json) | `ev_02a3812735219c13c596edc03f5e3f2f9c2da4b4d3a96755b907d6a0a60c4f53` | f3는 `uStack_4c` 상위32비트. 114/118행의 HUD 인수는 다른 `uStack_44`의 f4/f5다. 새 표시 소비 없음 |
| [5325C0 pseudocode](C:/Users/Chansol/AppData/Local/Temp/unknown_fields_rea_20261028_143659/pseudo_0x5325c0.json) | `ev_3b41093a959c2ec5fcbbdecd9cbab814b4a7cb41815204fedbe3774cbe4a3665` | 69–71행에 typed getter→object+568 저장 재확인. 이후 reader·업무 의미는 제공하지 않음 |
| [45550 pseudocode](C:/Users/Chansol/AppData/Local/Temp/unknown_fields_rea_20261028_143659/pseudo_0x45550.json) | `ev_898d445002cfa6ab98ebc1a554ea22847171075560c1a454052ff6db06472a08` | 323–329행 `subtype==3 || f14==2`, `UID=oldCounter-65h`, `counter--`, `*descriptor=UID`. 기존 `counter'-100`과 같은 식 |
| [event1802100 xrefs](C:/Users/Chansol/AppData/Local/Temp/unknown_fields_rea_20261028_143659/xref_event1802100.json) | `ev_7017d53d23966c0238f717d768b2566a35d4a44ca25bc872f729876f6c57a385` | `AC94/ACAE/2FB171/54A9A5/B33AE4/1097D6B/1097D7A` 총7곳. 앞서 대조한 LEA5+vptr MOV2와 일치. 추가 subscriber 후보 없음 |

**디컴파일 한계도 보존한다.** Ghidra는 `532F26→44C70`, `46759→4A450`을 no-return으로 보고 fallthrough를 제외한다. `983583` terminal call의 callee/no-return 근거도 UNKNOWN이다. 이는 provider의 분석 가정이며 실제 비복귀 증명이 아니다. stack 합성(`CONCAT44`)·복원 인수·`local_9c` 같은 표현을 원래 소스 타입으로 채택하지 않았다. 필드 출처·presence·정확 명령은 보존 asm과 이번 byte 대조를 기준으로 삼았다. REA xrefs도 참조 kind를 노출하지 않아 그 자체를 등록 증거로 세지 않았다. **추가 REA는 기존 결론을 교차확인했으며 f2/f3/카탈로그 f6의 UNKNOWN을 해소하지 못했다.**

| 미확인 | 다음에 필요한 최소 원본 근거 — 이번에는 실행하지 않음 |
|---|---|
| 4E95.f2 의미·정상값·화면 | 같은 버전의 정상 f2 presence/value와 CharacterData+568..56B의 실제 read/caller, 또는 대응 서버 producer. 값 한 건만으로 전체 맵 의미를 확정하지 않음 |
| 4F1A.f3 의미·정상값 | 다른 subscriber의 실제 f3 read→조건/표시 연결 또는 대응 서버 producer. HP바 표시만으로 f3를 역산하지 않음 |
| CommonItemInfo.f6 업무 의미 | GetItem 결과+D4 read에서 실제 graphics 선택·화면까지 이어지는 caller/callee. 숫자66 일치만으로 packet 생산자를 확정하지 않음 |
| 공식 4E31.f6 숫자·실제 Arrow | 같은 버전 정상 활1발/remote 궁수1타의 body와 sprite66 결속. 로컬 화면은 실제 한 발의 생성·비행·도착·소멸 및 후속 공격 확인 |

프로젝트 변경 파일은 이 문서 하나다. 다른 작업자의 기존 dirty/untracked 변경은 포함·정리하지 않았다. 커밋하지 않았다.
