# REA 미확인 필드 판정 — 2026-10-28

## 서버 권고 값과 확인 수준

**일반 화살66의 f6는 클라이언트가 내부 UID로 교체하는 입력이다. 맵 f2와 펫 HP f3의 업무 의미·공식 정상값은 확보한 정적 근거로 확정할 수 없다.** 세 필드 모두 현재 서버의 명시적 0을 유지하되, 아래 서로 다른 근거 수준을 보존한다. 이 문서는 서버 코드를 변경하지 않는다.

| 필드 | 확인된 의미·소비 | 서버에 반영할 값 | 판정 |
|---|---|---|---|
| `4E95.f2` required int32 | `CharacterDataSubsystem+0x568`에 저장. 실제 reader·업무 의미는 미확인 | **현재 `f2=0` 유지, 필수 presence 유지.** 목적지 map ID·층수·수중 flag로 대체하지 않음 | **UNKNOWN / LOCAL 잠정값.** 정상값으로 확인된 0이 아님. 비0맵 일반화 근거 없음 |
| `4E31.f6` optional int32 | Projectile Actor UID 입력. **일반 화살 `f7=66`/subtype3에서는 ctor 전에 client-local UID로 덮임** | **명시 `f6=0` 유지.** `f7=66`과 함께 presence 필요. 서버가 별도 화살 UID를 발급해 넣을 필요 근거 없음 | **정적 소비 확인 / LOCAL 권고0.** 공식 서버의 실제 f6 숫자는 미확인. 다른 projectile subtype에 일반화 금지 |
| `4F1A.f3` required int32 | 확인한 두 receiver에서 local에 복사만 함. Pet HP event에는 f1·f2만 전달 | **명시 `f3=0` 유지.** MP%·100·표시 flag로 변경하거나 생략하지 않음 | **copy-only 소비 확인 / 업무 의미 UNKNOWN / LOCAL 잠정값0.** 전역 미사용 증명 아님 |

현재 적용 위치는 `tools/local_original_session/world_core_maps.py:272`의 map notify f2=0, `world_combat.py:318`의 `attack_frame(..., arrow_id=0)` 및 ranged f6 인코딩, `world_feature_pet.py:47`의 `pet_hp()` f3=0이다. 이 위치는 이번에 읽은 상태이며 다른 작업자의 이후 변경을 포함하지 않는다. **이번 판정으로 바꿀 제품 값은 없다.** 화살의 값 무관성과 나머지 두 필드의 값 미확정을 동일한 근거로 취급하지 않는다.

## 분석 기준과 범위

기존 [맵](MAP_TRANSITION_EVIDENCE.md), [원거리 공격](RANGED_ATTACK_EVIDENCE.md), [펫](PET_EVIDENCE.md) 문서와 `work/local_server_rea_20261016/`의 보존 원문을 재사용했다. `reverse-engineer-anything` 스킬에 따라 정적 관찰·추론·미확인을 구분했다. 아래 `R/`는 `work/local_server_rea_20261016/`이며 주소는 **복원 CONTROL RVA**다.

기준 CONTROL SHA256은 `9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`다. 신원·carrier 한계는 [TARGET_IDENTITY](../../local_server_rea_20261016/TARGET_IDENTITY.md)에 따른다. 현재 실행 LC와의 동일성을 새로 검증하지 않았고, run380/402가 기록한 현재 디스크 코드 창 불일치·복원 범위 한계도 승계한다. 새 REA 세션·공식 웹 자료·L1J 추정값을 추가하지 않았다. 원본 클라이언트·서버·봇·포트·원 함수 실행, 저장·큐·핀·기존 근거 변경, commit은 없다.

## 1. 4E95 맵 알림 f2

### 원문에서 확인한 것

`4E95.f2`는 raw proto `+0x3C`의 required int32다. 맵 수신 경로의 `532654→3EB60`이 반환한 CharacterData 객체에 **`53266A: mov dword ptr [rax+0x568],ebx`**로 32비트 전체를 저장한다. 저장 자체에는 f2 값 분기가 없다. 생성자의 **`10FB4C: mov qword ptr [r15+0x564],rbp`**는 RBP=0으로 +568..56B까지 초기화한다. 둘 다 write이며 소비 의미를 알려주는 read가 아니다.

근거: [run402 f2 결과](../../local_server_rea_20261016/run402_map_notify_f2_consumer/f2_findings.md)의 「getter → alias → callee 결과」 및 [alias 원문](../../local_server_rea_20261016/run402_map_notify_f2_consumer/f2_alias_flow.json). RTTI/기반 형식은 [f2_type_lineage.json](../../local_server_rea_20261016/run402_map_notify_f2_consumer/f2_type_lineage.json)이다.

기존 추적은 getter 직접 참조337곳/owner291개, primary virtual9개·생성자 callback29개에서 같은 객체 alias를 연결했다. 782 context/617함수 안에서 f2 바이트와 겹치는 확인된 접근은 위 두 write뿐이었다. **인접 +564의 signed load, +570/+578 vector, 정렬 NOP를 f2 read로 세지 않는다.** 반환 후보13개도 실제 pointer 반환·소비로 확인되지 않았다([return check](../../local_server_rea_20261016/run402_map_notify_f2_consumer/f2_return_check.json)).

이번에는 기존 alias 추적의 member 재로드 경계를 하나 더 따라갔다. ctor `10F608: mov [rcx+8],rcx`의 self backpointer는 cleanup의 `110BF2: lea rcx,[rdi+8] → 110C05: jmp45190 → 451AD: mov rdi,[rbx]`로 재로드된다. 기존 [f2_alias_flow.json](../../local_server_rea_20261016/run402_map_notify_f2_consumer/f2_alias_flow.json):209,16265,21109가 이 경로의 출발점이다. 보존 record에서 `45190..45424` 전체187명령을 재디코드한 결과, self 값은 pointer-key hash·동일성 비교에 쓰이며 +568 직접 read는 없다. **`45346: mov rdx,rdi → 45349: call [rax+8]`의 registry callable 간접 경계는 미확정**이다. 따라서 자기참조 우회를 새 reader로 세거나 전체 경로가 닫혔다고 주장하지 않는다.

또한 [수신 원문](../../local_server_rea_20261016/run380_map_transition_receive/f2_key_evidence.json):284 이후에서 `53276B`는 EBX를 이전 resolved map으로 덮고 `532791`은 새 Map+718과 비교한다. 이 changed-map 비교를 앞서 EBX에 있던 f2의 분기로 해석하지 않는다.

### 값 판정

현재의 0은 [baseline.json](../../../tools/local_native_login_map_notify_hook/baseline.json)의 `EXPLICIT_LOCAL_SOURCE_BASELINE`, `normal_server_values_proven=false`를 승계한다. 생성자 0 초기화는 정상 송신값의 증거가 아니다. 온라인 V4/V5/V6의 기존 reader도 +55C..567과 +570 이후만 읽어 **+568..56B는 수집하지 않았다**([run402 기존 관측 검토](../../local_server_rea_20261016/run402_map_notify_f2_consumer/findings.md), 「정상값·실제 순서의 기존 관측」).

따라서 **현재 LOCAL 0을 유지**하되 업무 이름·비0맵 정상값을 확정하지 않는다. 해당 필드만으로 맵 전환 전체의 준비/화면/입력/수명 성공을 선언할 수 없다. 기존 alias 추적에는 member/global로 탈출한 pointer, 반환 alias, stack 인자·간접 호출·동적 코드의 미해결 경계가 있다. 실제 reader가 없다는 전역 결론은 불가하다.

## 2. 4E31 화살 원거리 공격 f6

### presence → descriptor → 최종 Actor UID

1. `4CFFA..4D010`은 f6/f7 **presence**를 검사한다. 값0과 생략은 다르며, 어느 하나가 없으면 해당 projectile 생성 후처리를 생략한다. [handler 원문](../../local_server_rea_20261016/run384_ranged_attack_display/function-4c440.asm):778 이후.
2. `4D1AD: movsxd rdx,dword ptr [rbp+0x44]`로 f6를 signed64로 확장하고 `CD104: mov qword ptr [rcx],rdx`로 descriptor+0에 넣는다. f2 attacker UID/f3 target UID와 별도다. [handler](../../local_server_rea_20261016/run384_ranged_attack_display/function-4c440.asm):870, [descriptor](../../local_server_rea_20261016/run384_ranged_attack_display/function-cd0b0.asm):20.
3. 일반 Actor ctor `40F00/40F03`은 descriptor+0을 Actor+18에 복사하고 vslot8 getter `40C00`은 이를 반환한다. 따라서 f6 자리의 역할은 **생성 Actor 자신의 UID 입력**이다. [ctor](../../local_server_rea_20261016/run386_arrow_projectile_gfx/field_contract/function-40ed0.asm):17, [getter](../../local_server_rea_20261016/run386_arrow_projectile_gfx/field_contract/window-40be0-40c70.asm):20.
4. 자원66의 `1009.effect(3 -1)`→row+88=3→factory subtype3→native `Arrow` 분기가 연결된다. [run386 자원·factory 결과](../../local_server_rea_20261016/run386_arrow_projectile_gfx/findings.md), [sprite 근거](../../local_server_rea_20261016/run386_arrow_projectile_gfx/sprite-evidence.json).
5. subtype3은 **`45C85 cmp esi,3 → 45C88 je 45C97`**로 f14 판정을 건너뛴다. `45C97..45CC2`는 global17B0040의 감소 카운터에서 `counter'=counter-1; effectiveUID=counter'-100`을 만들어 **descriptor+0을 덮는다.** 이후 ctor가 소비하는 값은 incoming f6가 아니다. [factory 원문](../../local_server_rea_20261016/run384_ranged_attack_display/function-45550.asm):404 이후, [직접 필드 계약](../../local_server_rea_20261016/run386_arrow_projectile_gfx/field_contract/findings.md) 2장.

### 덮어쓰기 전에 f6=0이 다른 조건에 걸리는가

이번에는 이 경계도 기존 전체 함수 원문에서 대조했다. handler의 해당 f6 local 읽기는 `4D1AD`이며 `CD0B0`은 descriptor+0에 저장한 뒤 UID 값으로 admission을 검사하지 않는다. handler는 descriptor+A0의 kind8 record를 만들고 `60FF0→45550`으로 전달한다([60FF0](../../local_server_rea_20261016/run384_ranged_attack_display/function-60ff0.asm):22).

factory 앞쪽의 ownUID 비교 `455D7`은 config+98이 있을 때만 도달한다. 이 handler는 `4D146`에서 descriptor+98을0으로 초기화하므로 **`455BF→458DE`**로 건너뛴다. descriptor+A0가 없는 별도 경로의 UID sign 검사도 이번 kind8 record 경로에는 적용되지 않는다. Arrow66의 `458DE→45930→45A03→45C10→45C85→45CC2`에서 lookup key는 f7이며, incoming f6를 UID 충돌 검사에 사용하는 경로를 확인하지 않았다. 이는 **해당 고정 Arrow 경로의 정적 판단**이다.

따라서 f6=0을 단순히 공식 숫자 미확인 후보로만 남기기보다, **이 소비 경로를 만족하는 명시적 LOCAL 값으로 권고**한다. f6에 attacker/target UID, 임의 음수(-101 등), 서버 발급 projectile UID를 넣어야 할 근거는 없다. native 카운터의 시작값은 기존 restored snapshot에서 unmapped여서 최종 실제 UID 숫자는 미확인이다.

적용 조건은 `f7=66`/subtype3 및 해당 handler admission 통과다. own PC의 f13=true 요구, native factory 성공, 좌표 f9..12·발사/비행/도착/정리는 별도다. f14는 domain1/2·생략 기본1이며 이 subtype의 UID 교체 분기에서는 읽지 않는다. 다른 effect/subtype에 같은 f6=0 규칙을 확대하지 않는다. **공식 PC·오크 궁수의 송신 f6=0을 관측했다는 뜻은 아니다.**

## 3. 4F1A 펫 HP f3

### required 조건과 실제 두 receiver

f3는 required int32, proto+20/wrapper+28이다([기존 ratio 판정](../../local_server_rea_20261016/run381_mob_hpbar_receive/ratio_findings.md):23). `7713C0..7713CA`의 `not eax; test al,7; sete al`은 f1..3의 **presence만 검사**한다. 값 비교가 없다는 사실은 생략 가능하다는 뜻이 아니다.

| 수신 경로 | f3 직접 접근 | 그 뒤 실제 소비 |
|---|---|---|
| Minion `54C230` | `54C2A0 test cl,4` → `54C2A5 [rdx+28]` → `54C2A8 [rbp-20]` 저장 | 전체 본문에서 그 local 재독출 없음. `54C301..54C31D`는 f1을 UID64로 zero-extend하고 **f2만** Minion+18→56710에 전달 |
| ActorHudManager `9832F0` | `983370 test cl,4` → `983375 [rdx+28]` → `983378 [rbp+17]` 저장 | 전체 본문에서 그 local 재독출 없음. 다른 HUD/debug 경로의 `98349E/9834A2` 인수는 **f5/f4**이며 f3가 아님 |

두 complete receiver와 required 판정 원문: [f3_gate_selected.txt](../../local_server_rea_20261016/run381_mob_hpbar_receive/f3_gate_selected.txt):9,15,56,143,207,254,286,402. 원 JSON 위치는 [f3_gate_sources.json](../../local_server_rea_20261016/run381_mob_hpbar_receive/f3_gate_sources.json)에 보존돼 있다. 이번에는 projection 원문과 해당 필드의 저장·후속 전달을 재검토했으며 새 실행 결과로 주장하지 않는다.

실제 Pet/Summon HP 게이지는 별도 **f2**를 `9829D0→Pet/SummonedMonsterActorHud→clamp(float(signed f2),0,100)→LoadingBar_HP+704→C1E820`으로 소비한다([ratio 결과](../../local_server_rea_20261016/run381_mob_hpbar_receive/ratio_findings.md):13–17). f3는 이 event 인수가 아니므로 **확인한 경로에서 f3를 HP 표시/선택 gate 또는 MP%로 명명할 근거가 없다.**

### 값 판정

현재 `pet_hp()`가 보내는 **명시 LOCAL f3=0을 유지**한다. f3 생략은 required 계약을 깨며, 100이나 MP%로 바꾸는 것도 새 추측이다. 두 receiver에서 값이 사용되지 않는다는 사실은 이 범위의 0 선택을 지지하지만, 전체 subscriber의 미사용·임의값 안전·공식 정상값0을 입증하지 않는다. 업무 의미는 UNKNOWN으로 남긴다.

## 검증과 남은 입력

읽기 확인은 `Get-Content -Encoding UTF8 <위 근거 파일>`과 `rg -n <필드/주소> <해당 폴더>`로 수행했다. 주요 명령어·분기·local 저장과 후속 호출은 위 asm/complete receiver 원문 및 기존 JSON과 대조했다. 문서 변경에는 링크 대상 존재와 diff 공백 검사를 수행했다. 제품 코드 변경이 없어 봇·서버 시험은 실행하지 않았다. 이 결과는 정적 계약 판정이며 원본 화면·입력·전체 수명 PASS가 아니다.

추가 f2 경로 확인 명령은 아래와 같다. **exit0**, owner `0x45190..0x45424`,187명령을 확인했다. `View`는 기존 `recovery.json`과 `selector_0_record_*.bin`을 읽으며 원 분석 스크립트의 main/save는 실행하지 않는다. 새 분석 파일은 만들지 않았다.

```powershell
@'
import sys
from pathlib import Path
sys.path.insert(0,str(Path('work/local_server_rea_20261016/run380_map_transition_receive').resolve()))
from f2_research import View
v=View()
f=v.function(0x45190)
print('RVA',f['rva'],f['end'],'instructions',len(f['instructions']))
for row in f['instructions']:
    print(row['rva'],row['instruction'])
'@ | python -X utf8 -B -
```

| 아직 닫히지 않은 것 | 다음에 필요한 최소 원본 근거 — 이번에는 실행하지 않음 |
|---|---|
| 맵 f2의 업무 의미·정상값 | 버전이 맞는 정상 4E95의 f2 presence/값과, 같은 CharacterData+568..56B를 읽는 실제 PC/caller 또는 대응 서버 producer. 정상값 한 건만으로 의미·모든 맵 값을 확정하지 않음 |
| 공식 화살 f6 숫자·실제 동작 | 정상 PC 활1발/remote 궁수1타의 4E31 body와 f7=66 결속. 로컬 값0의 화면 검증은 발사→비행→도착→소멸/후속 공격 및 native UID 소비를 해당 한 발에서 확인 |
| 펫 f3의 업무 의미·공식값 | 버전이 맞는 서버 producer 또는 정상 4F1A 값·상황에 연결된 실제 f3 read/다른 subscriber. HP바가 보인다는 사실만으로 f3 의미를 역산하지 않음 |

**마감 범위:** 필드별 소비 판정과 현 서버 권고 값은 위 표로 정리했다. 업무 의미까지 확인된 것은 화살 f6이며, 맵 f2와 펫 f3는 미확정을 보존한다. 기존 증거보다 강한 공식값 결론을 만들지 않는다.
