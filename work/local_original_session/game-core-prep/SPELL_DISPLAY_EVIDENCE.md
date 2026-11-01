# 마법 시전·이펙트 gfx 대응 근거 — REA399 / REA401

2026-10-27. **다른 actor의 시전 동작은 `4E31 SC_ATTACK_NOTI`의 kind18/19→실제 `SpellAction`, 대상 효과는 `4ED8 SC_EFFECT_NOTI`로 연결된다.** 두 패킷은 서로 다른 입력을 받는다. `4E31`에는 시전자/대상 UID가 있고, `4ED8`에는 대상 UID와 graphic ID만 있다. 요청 스킬 키를 graphic ID 자리에 넣는 계약이 아니다.

판정은 **보존 원문 확인·정적 연결 확인 / 화면 UNRUN**이다. REA401에서 저레벨 스킬 표·native-dump 전체 schema와 볼트 비행/callback을 추가 조사했다. 스킬 키와 SPR 내부 관계는 확인했지만 공식 서버의 주문별18/19 선택·gfx·송신 조합/순서와 실제 표시 성공은 미확정이다. 이번 지정 분석 외 제품 중지는 유지하며 게임·서버·포트 실행, 서버 제품 코드·원본·자원·저장·큐 수정 및 git commit은 하지 않았다.

## 패킷과 직접 소비

주소는 보존 분석의 RVA이며 현재 프로세스 VA가 아니다. 기존 framing은 `<u16 total_length><u16 opcode><protobuf body><2-byte tail>`이다.

| 패킷 | 필드와 정적 소비 | 다른 actor에 관한 판정 |
|---|---|---|
| **4E31 SC_ATTACK_NOTI** | required f1=int32 kind, f2=uint64 caster UID, f3=uint64 target UID, f4=int32 raw effect, f5=int32 direction. optional f6..14는 아래 참조. kind18/19→977A0→9AA20 selector3→9ABAC→vptr1180B30 **SpellAction** | f2가 자기 PC UID와 다르면 own/f13=false 조기 반환 조건에 해당하지 않는다. 실제 Actor 조회·공통 action admission·SPR action row는 여전히 필요하다. |
| **4ED8 SC_EFFECT_NOTI** | **required f1=uint32 target UID, f2=int32 graphic ID**, 둘 다 wire0. 시전자/스킬 키/좌표 필드 없음. handler4FE90→627B0 대상 Actor→414A0 좌표→CCF30 효과 설정→61530 등록 | 일반 대상 경로에 self-only 제한이 없다. self+gfx169 특수 분기는 일반 힐/Shield 계약으로 전용하지 않는다. 대상의 정상 UID가 uint32에 표현되어야 하며 uint64를 임의 절단하지 않는다. |
| **4ED9 SC_EFFECT_LOCATION_NOTI** | required f1/f2=uint32 좌표 DWORD, f3=int32 graphic ID, f4=int32 추가 입력. 대상/시전자 UID 없음 | 좌표 효과용 별도 경로다. 좌표 단위·f4의 해석은 하위 원문 결과의 확인 범위만 따른다. 이번 힐/Shield 대상 효과를 위해 이 패킷을 추가할 필요는 입증하지 않았다. |
| 4E91 SC_BUFF_ICON_NOTI | required outer f1=closed enum/f2=BuffIconInfo. HUD 슬롯·아이콘·시간 계열의 별도 계약 | caster animation이나 대상 sprite effect를 대신하지 않는다. 수신 PC의 HUD 표시와 월드 Actor 효과를 구별한다. |
| 4EE6 CS_USE_SPELL_REQ | required f1=uint32 spell key, optional f2=UseSpellParam | **C2S 요청**이다. 동료 표시를 위해 내 PC가 이 요청을 보낸 것처럼 만들 근거가 없다. |

4E31의 `kind4`는 기존 결과대로 **AttackAction**이다. kind18/19의 SpellAction 확인을 kind4의 재명명이나 공식 마법 성공/HP 소비 증명으로 확대하지 않는다.

## 시전자 동작과 투사체

SpellAction은 queue에서 currentAction에 설치된 뒤 Start(vslot8=8F9A0)로 연결된다. Start는 **시전자 자신의 visual SPR**와 action18/19를 이용해 `34A160→348C80`에서 action row를 고르고 frame/timing·direction 입력을 소비한다. frame 자원 조회·cache 경로도 확인했다. 따라서 내 PC의 local cast 입력 없이 remote Actor의 native action을 구동할 정적 경로는 존재한다. 실제 row 부재 시 sentinel/기본 action fallback이 있으므로 임의 NPC SPR에서 마법 동작이 재생된다고 보장하지 않는다.

kind18/19는 같은 SpellAction class를 만들지만 **서로 다른 resource action key**다. Energy Bolt의 request key3, Heal0, Shield2를 이 kind 값과 혼동하지 않는다. 어떤 caster SPR에서 어느 action을 쓸지는 해당 SPR row와 정상 관측을 따른다.

| 4E31 optional 필드 | 확인한 역할·경계 |
|---|---|
| f6=int32 | presence 필요. descriptor+0의 sign-extended 식별자→Projectile Actor UID 입력. 일반 화살66의 native UID 대체 계약을 마법에 그대로 적용하지 않는다. |
| f7=int32 | presence 필요. graphic table key→factory subtype 선택. **f6/f7 모두 present일 때** 별도 projectile postlude에 들어간다. |
| f8=int32 | LightComponent 입력. 비행속도나 피해량으로 확인한 값이 아니다. |
| f9/f10=int32 | descriptor 좌표쌍 A. native raw Coordinate 입력이며 server tile 좌표를 그대로 대입하지 않는다. |
| f11/f12=int32 | projectile record 좌표쌍 B. 실제 출발/목표 fallback의 전체 우선순위·현재 subcell 입력은 미확정이다. |
| f13=bool | own caster이고 false일 때 action/projectile을 생략하는 조건. remote caster는 이 own 조건 대상이 아니다. |
| f14=enum | 허용1/2, 생략 기본1. **SPR167 subtype4는 f14=1일 때 f6 UID를 유지하고, f14=2일 때 native UID 대체 분기**에 들어간다. 공식 Energy Bolt의 presence/값은 미관측이다. |

f4 raw effect는 대상 반응 입력이며 공식 HP damage로 확정하지 않았다. 투사체 생성, 시전자 animation, 대상 HP 갱신, 효과 종료는 각각의 소비 경로다. 공식 필수 cross-packet 순서는 UNKNOWN이다.

SPR167의 link219는 base Projectile+108에 저장된다. REA401은 `C45A0 launch→BFA50/BFDB0 이동→BC680→C6290→C6484→C4D20` 좌표 callback과 linked gfx 소비를 연결했다. `C4D20`은 Component+78/+7C의 **B raw(f11/f12)**와 incoming raw가 같은 조건 및 `+108>=0`에서 `CCF30(gfx=219)→61530`으로 별도 효과를 만든다. launch도 현재좌표로 C4D20을 즉시 부르므로 **현재좌표=B이면 발사 때부터219가 생성될 수 있다.** 무조건 명중/도착 효과로 해석하지 않는다. 비행을 만드는 것은4E31 f6/f7이며4ED8은 대상 위치의 별도 effect다. linked219를 위해4ED8 gfx219를 추가할 필요는 입증되지 않았다.

종료 event의 `C4D20→679F0→6C840→63000→3ED20 getter의 component+49=1`까지 확인했다. 종료 요청 표식이라는 해석은 추론이며 실제 container 제거/free·linked effect 수명은 UNKNOWN이다. target-vector가 비면 incoming 좌표를 쓰며 +100의 targetUID를 여기서 직접 읽지 않는다. 같은 f3와 vector의 결속·BattleComponent queue의 발사 프레임·실화면도 미확정이다. 원문은 [REA401 route](../../local_server_rea_20261016/run401_spell_gfx_table/route/findings.md:22)에 있다.

## 저레벨 마법 key·시전 동작·gfx 대응표 — REA401

행 번호는 `work/all_table_semantics/inputs/data/spell_list.jsonc`와 같은 폴더의 `list.spr` 기준이다. **아래 gfx는 자원 식별/내부 관계는 확인했으나 spell key→공식 송신 연결은 미확정인 후보**다. 주문별 cast action도 모두 UNKNOWN이다. direction=true를 wire18로, 미기재를 false/19로 확정하지 않는다.

| 주문 | 확정 key / spell_list 행 | direction 원문 | gfx 자원 후보 / list.spr 행 | 자원 자체·투사체 판정 |
|---|---|---|---|---|
| **Heal** | **0** / :20 | 미기재 | **744 heal** / :2198 | fire 효과 행.4ED8 대상효과의 LOCAL 후보; 공식 매핑 미확정 |
| **Shield** | **2** / :28 | 미기재 | **221 shield** / :1168;220 shield hit / :1164 | 두 효과는 별도.23 shield는 type9 아이템이므로 제외. 공식221/220 선택 미확정 |
| **Energy Bolt** | **3** / :32 | true | **167 energy bolt** / :921;219 take water / :1160 | `effect(4 219)`→EnergyBolt family/base Projectile/link219 소비 확인. 비행 입력은4E31 f6/f7 |
| **Ice Dagger** | **5** / :40 | true | **1797 icedagger shooting** / :5901;1798 bomb / :5906 | 명시 `effect(5 1798)` / :5904. 같은 subtype5 factory 계약상 base Projectile 후보; 공식 key5 연결/실비행 미관측 |
| **Lightning** | **16** / :94 | true | **170 lightning bolt** / :935 | action0.lightning, 명시1009.effect 없음. 최종 subtype·비행 여부 UNKNOWN |
| **Extra Heal** | **18** / :102 | 미기재 | **829 extra heal** / :2515 | **sprite829/file744 공유**(`#829 1=744`), 자체 fire row·sound114. gfx744로 치환하지 않음.4ED8 LOCAL 후보 |
| **Call Lightning** | **33** / :173 | true | **10 lightning** / :110는 추가 이름 후보 | 명시 `effect(2 -1)` / :114. key33→10/170 선택 UNKNOWN; Lightning16과 구별 |
| **Cone of Cold** | **37** / :190 | true | **1809 coneofcold shooting** / :5946;1810 bomb / :5951 | `effect(5 1810)`→native Fireball family/base Projectile/link1810. 공식 key37 연결 미확정 |

Light는 **key1**(:24)이다. “콜드”는 Ice Dagger5와 Cone of Cold37, “라이트닝”은 Lightning16과 Call Lightning33을 구분한다. native family 이름 Fireball이 주문명을 뜻하지 않는다. 정확 선정 원문과 전체 표는 [REA401 table](../../local_server_rea_20261016/run401_spell_gfx_table/table/findings.md:9), [SPR 원문](../../local_server_rea_20261016/run401_spell_gfx_table/table/sprite-candidates-original.txt:1)에 있다.

spell_list 전체113행(정의112/empty1)의 명명 필드에는 gfx/projectile/cast-action이 없다. icon/quickuseicon은 UI 번호다. 보존 row converter5A6360의 직접 scalar 생산 경로에서도 위 sprite를 주문에 연결하지 못했고 helper 전체·direction 소비는 미확정이다. 따라서 이 표는 **원리소스에 근거한 LOCAL 화면 실험 후보표**이며 공식 ready-to-send recipe가 아니다.

`native-dump-v1.jsonl`은 원 LC 메모리 덤프가 아니라 보존 C++ decoder의 NPC/item/spell/token 네 표 출력이다. spell433행과 CommonSpellInfo schema13필드를 확인했다. **f3는 버프 PNG 아이콘, f7은 tooltip 참조이며 f4 의미는 UNKNOWN**이다. Heal0/ExtraHeal18은 ID 외 f2/f3/f4/f5/f6/f10=0, 위 다섯 공격 주문도 같은 scalar0/f13=10으로 ID 외 값이 같다. 서로 다른 gfx를 이 값들에서 직접 읽어낼 수 없다. Shield2의485/853을 월드gfx로 전용하지 않는다. [native schema·소비 근거](../../local_server_rea_20261016/run401_spell_gfx_table/table/findings.md:32).

catalog131,889경로 이름과 기존51표/603 text경로 조사에서 별도 명명된 skill→gfx 구조표를 찾지 못했다. **f4·미선정 ID별 코드 lookup·opaque 자원 내부는 미확정**이며 클라이언트 전체에 매핑표가 없다는 단정은 하지 않는다. bounded 검색 범위는 [REA401 table:58](../../local_server_rea_20261016/run401_spell_gfx_table/table/findings.md:58)에 있다.

## 최소 사용자 화면 실험안 — 이번 실행 없음

1. 다음에 게임 실행이 별도로 허용되면 기존 정상 로그인→캐릭터 선택→월드 진입 및 시험 저장을 재사용한다. 화면 안에 이미 발급·등록된 remote caster와 대상 Actor를 둔다. 정상 UID, caster SPR의 action18/19 row, 현재 direction을 보존하며 새 지급/저장 초기화로 준비하지 않는다.
2. **동작만** 확인: remote f2 UID를 쓰는 4E31 kind18 또는19를 해당 SPR row에 맞춰 한 번 보낸다. f6/f7을 생략해 투사체를 분리한다. cast frame→기본 자세 복귀→후속 행동 가능을 관찰한다. f4는 기존 의미를 보존하며 임의 damage로 해석하지 않는다.
3. **힐/익스트라 힐/Shield 대상 효과**: 각각 별도 case에서4ED8의 f1=정상 targetUID32, f2=744/829/221을 LOCAL 후보로 한 번 적용한다. Heal/ExtraHeal은 remote caster→내 PC, Shield는 자원의 targetself에 맞춰 remote caster→그 자신을 구분해 효과 위치·소리·재생·소멸을 관찰한다. 파일744를 공유해도 ExtraHeal의 sprite829를 치환하지 않는다. generic 수신 경로로 Shield의 정상 대상 규칙을 확대하지 않는다. HP 회복·AC/지속시간·HUD 아이콘은 별도 상태 계약이며 반짝임만으로 회복/버프 성공이라 하지 않는다.
4. **에너지 볼트 투사체**: 선행 입력은 정상 projectile f6 식별자/f14 정책과 정확한 A/B raw좌표다. 이 입력을 확보한 뒤에만 f7=167 후보로 **현재위치와 B가 분리된 거리**에서 발사→비행→좌표도달/link219→소멸·다음 행동을 관찰한다. 화살의 f6=0 후보나 tile 좌표를 그대로 대입하지 않는다. 별도4ED8 gfx219를 덧붙여 중복 효과를 만들지 않는다. IceDagger1797/ConeOfCold1809 후보도 같은 방식으로 분리하며 Lightning170은 정상 원필드 확보 전 비행형으로 단정하지 않는다.
5. 공식 대응 확정이 목적이면 고정 버전의 정상 시전 한 건씩에서 **실제 spell key·caster/target·S2C raw fields/presence·보존 stream 순서**를 대조한다. LOCAL 후보의 표시 성공은 그 후보의 표시 결과이며 공식 발행 정책의 증거는 아니다. packet 수신/객체 등록만으로 화면 PASS를 만들지 않는다.

## 근거와 재사용 경계

- [REA401 분석 입구](../../local_server_rea_20261016/run401_spell_gfx_table/findings.md): 저레벨 대응표·native-dump/schema·볼트 비행/종료 표식·미확정 검색 범위. main이 선정 원문과 소비 asm을 대조했다. 이 run과 본 문서 외 쓰기0, 실행·새 guard/검증 도구0이다.
- [run399 분석 입구](../../local_server_rea_20261016/run399_spell_cast_display/findings.md): worker별 원문·주소·분석 입력과 마감 검토.
- [시전자/투사체](../../local_server_rea_20261016/run399_spell_cast_display/attack/findings.md), [대상·좌표 효과](../../local_server_rea_20261016/run399_spell_cast_display/heal_buff/findings.md), [spell/SPR 대응](../../local_server_rea_20261016/run399_spell_cast_display/resources/findings.md).
- [공식 큐 발췌](../../local_server_rea_20261016/run399_spell_cast_display/queue-excerpts.json): 읽은 revision5132의 기존 관련7항목. 직접 공격 키3/5/6/33/37/44/45는 비용·HostilePolicy/서버 계산 Source이며 표시 gfx·원서버 응답 근거가 아니다. 큐는 수정하지 않았다.
- 기존 [REA283 LOS 계약](../../local_server_rea_20261016/run283_energybolt3_projectile_los/source/contract.md:3), [REA323 성공/HP 경계](../../local_server_rea_20261016/run323_energybolt_s2c_success_hp_contract/contract.md:5), [RANGED_ATTACK_EVIDENCE](RANGED_ATTACK_EVIDENCE.md:22), [기존 wire 계약](../../local_server_rea_20261016/run104_skill_buff_contract/wire_schema/findings.md:7)을 재사용했다. 시전 요청·서버 계산·LOS·HUD·표시·실제 HP를 합쳐 전체 PASS로 부르지 않는다.

native 주 분석은 기존 `tools/local_movement_contract/source.py`의 restored-record reader와 보존 snapshot을 재사용했다. recovery의 역사적 CONTROL source hash `9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`를 현재 loaded image hash로 부르지 않는다. resource parser의 기존 frozen104 exec-buffer 근거는 별도 domain이며 결합 runtime 관측이 아니다. 상세 carrier/record·구간 provenance와 한계는 각 worker 산출물에 남긴다. 새 REA runtime 세션·현재 RPM·게임 관측은 없다.
