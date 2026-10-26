# 원거리 공격 표시 — 고정 클라이언트 정적 근거

2026-10-26 / run384. **SC_ATTACK_NOTI 0x4E31에는 실제 Projectile을 만드는 optional f6/f7 경로가 있다. 현재 kind1/f1..5/f13만 보내는 frame은 이 경로에 들어가지 않는다.** kind를 다른 숫자로 바꾸는 해법이나 별도 DRAW packet이 반드시 필요하다는 결론은 근거가 없다. 활·오크 궁수의 정확한 화살 graphic key와 전체 비행/도착 실행은 UNKNOWN이다.

범위: 기존 pinned CONTROL snapshot의 읽기 전용 Capstone 분석과 이 문서/지정 run384 작성. 게임·서버·포트·원본 LC·자원·저장·제품코드·큐·git commit 변경/실행 0. 제품 중지는 유지한다. `reverse-engineer-anything` 스킬의 기존 native snapshot 재사용 방식이며 새 REA 세션/Evidence ID는 없다. 원문 관찰·연결 확인과 화면 실행을 구분한다.

## 결과와 근거 위치

| 질문 | 판정 |
|---|---|
| 4E31로 투사체 생성이 가능한가 | **정적 연결 확인.** f6와 f7의 presence가 모두 있으면 CD0B0→60FF0→45550의 Projectile factory로 간다. kind1도 해당한다. |
| 지금 PC 활/NPC 궁수 frame의 부족 | `world_combat.py:212-217`은 kind1/f1..5/f13만 구성한다. f6/7을 생략하므로 4CFFA의 첫 gate에서 투사체 경로를 생략한다. |
| native 자세/공격 애니메이션만으로 화살이 생기는가 | **이 4E31 handler에서는 자동 생성 아님.** 일반 AttackAction enqueue와 투사체 후처리는 별개다. 전체 다른 native 경로의 부재 증명은 아니다. |
| 별도 packet | **0xC373 SC_PROJECTILE_DRAW_NOTI**의 opcode/8-field schema는 정적 확인. 실제 subscriber/화면 소비는 미결속. 4E31을 대체해야 한다고 판정하지 않는다. |
| 활/오크 궁수 화살 graphic 번호 | **UNKNOWN.** 오크 궁수 actor SPR57·L1J actor gfx3860, 활 자세40·item11·ammo29는 projectile graphic key의 근거가 아니다. |
| 비행 시작·도착·정리 전체/화면 | **UNKNOWN / UNRUN.** native factory·component·Transform까지 연결했으나 실제 token 소비/launch/도착·종료 수명과 화면은 미관측. |

상세 원문·주소·필드 표와 별도 DRAW 한계는 [run384 결과](../../local_server_rea_20261016/run384_ranged_attack_display/findings.md)에 있다. 주소는 모두 CONTROL image의 RVA이며 현재 프로세스 VA가 아니다. CONTROL 식별 SHA256은 `9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`이다.

## 확정된 wire와 조건

기존 framing은 `<u16 total_length><u16 opcode><protobuf body><2-byte tail>`이다. 4E31 f1..5는 required, f6..14는 optional이며 모두 wire0 varint다. f2/f3는 uint64, f13은 bool, f14는 enum, 나머지는 signed int32(zigzag 아님). f6/f7은 **값이 양수인지가 아니라 presence**를 검사한다. 누락 기본값0으로 원래 화살을 대체할 수 없다.

| field | 확인한 직접 소비 |
|---|---|
| 1 | kind. 일반0..4는 modulo5 action selector, kind1→AttackAction. `kind6=화살` 근거 없음. |
| 2 / 3 | attacker UID / target UID. projectile record+0/+8에도 각각 복사. |
| 4 | raw effect. 일반 AttackAction 대상 효과의 양수 gate이며 공식 damage/HP 아님. 투사체 생성 postlude의 직접 gate는 f4가 아니다. |
| 5 | action 방향 및 descriptor+1C 방향. |
| **6** | sign-extend int32→descriptor+0 qword 식별자 입력. factory의 일부 type/enum은 별도 음수 ID를 생산하므로 모든 경우 server projectile UID와 동일하다고 단정하지 않는다. |
| **7** | descriptor+8/+C→native sprite/graphic table key. **화살 graphic의 실제 값은 미확정.** |
| 8 | projectile record+18→LightComponent+38, <=0이면 component+3C 기본값 사용. 비행속도·damage 아님. |
| 9 / 10 | descriptor+14/+18의 좌표쌍 A. mode5 `52F320`은 입력을 Coordinate+8에 보관하고 cell=trunc(raw/64)+0x7E00으로 만든다. |
| 11 / 12 | projectile record+10/+14의 좌표쌍 B→ProjectileComponent 초기 Coordinate+70 및 Transform. 같은 raw/64 변환. |
| 13 | actor가 존재하는 self attacker이고 false면 4C7FD→4D86E로 반환하여 action과 projectile postlude 모두 생략. true여도 공통 admission/factory 성공 보장은 아니다. remote attacker는 이 self gate 대상 아님. |
| 14 | projectile record+28 enum. factory type/추가 분기에 영향; enum 의미/정상 활 값 UNKNOWN. |

A/B 좌표의 **server 타일좌표를 그대로 넣으면 안 된다.** 확인된 단위는 native Coordinate+8/+C의 raw index다. `(tile-32256)*64`는 cell 변환의 한 역상일 뿐 현재 actor의 정확한 subcell·중심·방향 값이라는 증거가 아니다. A/B의 모든 factory subtype별 출발/목표·UID lookup fallback 우선순위는 아직 UNKNOWN이다.

## 최소 화면 실험안 — 이번 실행 없음

1. 다음에 별도로 실행이 허용될 때 정상 로그인→선택→월드 진입을 쓰고 기존 시험 저장을 보존한다. 먼저 현재 frame 그대로 PC 활1발과 remote 오크 궁수1타의 자세·화살 유무를 각각 기록한다. 기존 키트는 활11/화살29 각1이므로 PC 한 발 한계가 있고, 준비물이 없으면 미확인으로 남긴다. 저장 삭제·재지급·재화 수정으로 준비하지 않는다.
2. 수정 실험의 **선행 최소 입력**은 이 고정 클라이언트의 정상 화살 graphic key 하나와 그 sprite row, 정상 projectile f6 식별자·f14 의미 및 A/B raw coordinate producer다. 정상 온라인 원패킷/기존 capture 또는 고정 테이블+해당 정상 producer에서 얻는다. L1J 숫자를 대입하거나 opcode/필드를 무작위 순회하지 않는다.
3. 이 입력이 확보된 뒤에만 같은 서버판의 단일 선택 실험으로 kind1/f1..5/f13을 유지하고 f6..12/필요f14를 추가한다. PC own은 명시 f13=true case, NPC remote는 별도 case로 분리한다. raw f4는 기존 값을 보존해 피해 변화와 표시 변경을 섞지 않는다.
4. 각 case에서 **발사 자세→공중 이동→목표 도착→피격 표시→투사체 소멸/후속 공격 가능**을 한 번 관찰한다. 가능하면 같은 source·저장 계보의 프레임 또는 영상으로 남긴다. packet 수신/메모리 객체 존재만으로 화면 PASS라 하지 않는다. factory null·정지·도착 실패·강제 정리는 실제대로 기록한다.

현재 자료만으로는 2번 입력이 부족하여 ready-to-send 패킷이나 제품 변경을 공급하지 않았다. 0xC373은 별도 subscriber·업무 의미가 닫히기 전 이 실험에 넣지 않는다.

## run386 추가 결과 — 일반 화살66 / f6·f14 정적 계약

2026-10-26. **고정 클라이언트의 일반 화살 graphic key는66이다.** 위 run384의 화살 번호·f14 기본값 UNKNOWN은 이번에 아래 범위까지 좁혔다. 기존 결과는 당시 이력으로 보존한다. 제품 중지 유지, 게임·서버·포트·온라인 실행·제품 코드·원본·자원·저장·큐·commit 변경0이다. 공식 정상 원패킷의 값과 화면은 이번에도 관측하지 않았다.

현재 `list.spr:486-489`/`current-parsed.jsonl:63`에 `#66 8 arrow`, `0.fly(1 3,0.2:1 0.0:1 0.1:1)`, `1002.type(9)`, **`1009.effect(3 -1)`**이 있다. native integer parser **34C9E0**는 effect 두 값을 parser+B0/B4, 즉 sprite row+88/+8C에 기록한다.4E31 factory **458F6→34A160(f7)→45930**은 이 row+88을 읽고, subtype3은 jump table46760[3]→**45A03**에서 native label **`Arrow`(117E1FC)**를 선택한다. ctor jump table4679C[3]→**460BD→490B0→C42C0(r8=0)**은 기본 `Projectile`을 만든다. 따라서66은 actor SPR57·활 자세40·item11/29에서 추측한 값이 아니라 **실제 Arrow factory를 고르는 현재 자원 key**다.

PC 일반 활은 현재 SPR40/41 bow군과 item29 화살→graphic66 대응을 가진다. 오크 궁수는 native NPC template1/$267/actor57 및 SPR57의 action1 `attack bow`다. L1J도 `L1Attack.java:1289`의 PC bow 분기에66을 쓰고, NPC45019의 `bowActId=66`을 원거리에서 전달한다(SQL:1601/20640, L1Attack:1329-1340). **현재 SPR/native에서66을 독립 확인한 뒤 비교한 L1J 참고**이며, L1J actor3860·aid21·light127·tile좌표를 현재4E31로 이식하지 않는다. PC/오크의 실제 공식 f7 선택 관측과 특수 화살 전체는 미확인이다.

**f14의 허용 enum은1·2, 생략 기본값은1이다.** generated ctor7036FA/Clear75E0FF/default instance164C3E4와 handler local4C4B4=1→presence copy75E6CB가 일치한다. parser aux15EF070의 start1/count2 및 DEA870/generic fallback도 domain을 확인한다. 원래 enum symbolic 이름은 UNKNOWN이다. **gfx66/subtype3은45C85→45C97에서 f14 읽기를 건너뛴다.**

**f6는 Projectile Actor 자신의 UID 입력이지만, 일반 화살66에서는 native local UID로 교체된다.** descriptor+0→40F00→Actor+18→vslot8 getter40C00이 연결되고, Arrow subtype3은45C97..45CC2에서 global17B0040의 감소 카운터 기반 UID로 덮는다. 이 handler의 descriptor+98=0이므로 일반 factory의 config 조건부 ownUID 비교를 f6 요구값으로 적용하지 않는다. **공식 PC/오크 화살의 f6 숫자·f14 presence/value는 UNKNOWN**이다. f6=0은 아래에서 대체되는 presence용 로컬 후보일 뿐 공식 정상값이 아니다.

| 4E31 필드 | PC own 일반 활 | remote 오크 궁수 | 판정·범위 |
|---|---|---|---|
| f1 | 기존 kind1 | 기존 kind1 | 일반 AttackAction 유지. L1J aid21 이식0. |
| f2/f3 | 실제 PC UID/선택 대상 UID | 실제 오크 UID/PC UID | 기존 서버 발급·선택 권위 유지. |
| f4/f5 | 기존 raw_effect/현재 방향 | 동일 | 표시 실험으로 피해·방향을 바꾸지 않는다. |
| **f6** | **present int32; 공식 숫자 UNKNOWN, 로컬 후보0** | **동일** | 누락은 생성 gate를 닫는다.66에서는 ctor 전에 native UID로 교체. |
| **f7** | **66** | **66** | 현재 일반 화살 row→native Arrow 정적 연결. 공식 wire·화면 관측은 아님. |
| f8 | 생략→0 또는 정상 관측값 | 동일 |0은 LightComponent 기본값 선택. 공식 빛 값 UNKNOWN. |
| f9/f10 | A의 정확 raw 좌표쌍 필요 | 동일 | descriptor+14/+18. 실제 producer·우선순위 미완. |
| f11/f12 | B의 정확 raw 좌표쌍 필요 | 동일 | ProjectileComponent+70 저장까지 확인. target/current fallback 전체 미완. |
| **f13** | **true 명시** | 기존 값 유지; own false gate 대상 아님 | PC own false는 action과 projectile을 모두 생략. |
| **f14** | **생략(default1) 또는 명시1** | **동일** | 클라이언트 domain/default 확인. 공식 화살 wire값 미관측.0은 domain 밖. |

이 표는 정적 계약과 **향후 로컬 실험 후보**이며 ready-to-send 패킷이 아니다. f9..12 생략은 기본raw0을 전달하며 cell32256으로 변환된다. 현재 위치 fallback으로 간주하거나 `(tile-32256)*64`의 한 역상을 정확 subcell/current로 확정하지 않는다. f14=2를 화살 필수로 바꾸거나 송신 f6를 최종 화살 UID로 저장할 근거도 없다.

남은 최소 입력은 현재 PC·NPC·대상의 **Coordinate+8/+C raw쌍과 대응 타일**, 이번 Arrow의 A/B 출발·목표 소비 관측이다. 다음에 실행이 별도로 허용되면 이 값만 닫고 같은 source에서 PC1발/remote오크1타에 f7=66·f6 present0(LOCAL 후보)·f14 omit(default1)·f8 omit(기본값 후보)을 적용해 발사→비행→도착→피격→소멸/후속 공격을 관찰한다. 공식 wire 복원이 목적이면 정상 PC1발·remote1타의4E31 body를 먼저 대조한다. 저장·준비물·UID·수명 guard를 보존하고 실패/강제 정리는 실제대로 남긴다.0xC373은 추가하지 않는다.

선택 원문·source 파일:줄·native 주소와 한계는 [run386 결과](../../local_server_rea_20261016/run386_arrow_projectile_gfx/findings.md), [원문 발췌](../../local_server_rea_20261016/run386_arrow_projectile_gfx/source-excerpts.txt), [sprite/native 선택행](../../local_server_rea_20261016/run386_arrow_projectile_gfx/sprite-evidence.json), [f6/f14 직접 근거](../../local_server_rea_20261016/run386_arrow_projectile_gfx/field_contract/findings.md)에 있다. 비행·도착·종료 전체와 실화면은 **UNKNOWN / UNRUN**을 유지한다.
