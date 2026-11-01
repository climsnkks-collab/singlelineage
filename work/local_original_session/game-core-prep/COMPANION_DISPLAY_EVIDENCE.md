# 동료를 다른 플레이어형 actor로 표시하는 계약

2026-10-27. run398의 표시 계약에 run404의 **다른 Player 사망·시체·부활·클릭** 정적 분석을 추가했다. 이번 쓰기는 `work/local_server_rea_20261016/run404_remote_death_revive/`와 이 문서뿐이다. 게임·서버·포트·원 함수 실행, 서버 제품 코드·원본·저장·공식 큐 수정과 git commit은 하지 않았다. 제품의 일반 중지·동료 구현 동결은 그대로다.

**법사 동료는 `4E96.f16=true`와 자기 PC와 다른 `f2 UID`로 원본의 다른 Player 생성 경로에 들어간다.** 외형은 f3, 무기 동작군은 f4로 별도 지정한다. 이동·공격에는 공통 actor 경로가 있지만, 기존 동료 패킷 시험은 실제 LC 표시를 확인하지 않았다. 다른 Player의 일반 머리 위 HP바는 확인한 초기화에서 숨겨지며, HP debug 텍스트와 구분해야 한다.

표기: **확정**은 보존 원문/정적 연결의 확인이다. **LOCAL**은 기존 서버가 선택한 정책, **미확정**은 소비 연결 또는 실행 근거가 부족한 범위다. 화면 PASS를 뜻하지 않는다. `R/`=`work/local_server_rea_20261016/`, `L/`=`work/local_original_session/`이며 주소는 고정 복원 CONTROL의 **RVA**다.

## 비교 기준과 기존 작업 재사용

- 기준은 기존 원본 `26.09.29.2001`, CONTROL SHA256 `9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`다. 이번에 원본이나 자원을 다시 만들지 않았다. 원문은 [run398 selected-disassembly.txt](../../local_server_rea_20261016/run398_companion_actor_display/selected-disassembly.txt), 출처/함수 범위/해시는 [selected-source.json](../../local_server_rea_20261016/run398_companion_actor_display/selected-source.json)에 있다.
- [COMPANION_AUDIT_CODEX.md](COMPANION_AUDIT_CODEX.md):68–69, [COMPANION_AUDIT_CLAUDE.md](COMPANION_AUDIT_CLAUDE.md), 동료 HANDOFF·`allied-publication-source-v2`·`local-allied-*`, [run271](../../local_server_rea_20261016/run271_allied_player_click_registration/source/contract.md)·[run272](../../local_server_rea_20261016/run272_allied_uid_native_lifecycle/source/contract.md)에서 출발했다. 그 세션의 과거 writer·runtime 상태를 이번 권한이나 현재 관측으로 옮기지 않았다.
- REA 스킬의 native 절차를 적용했다. MCP는 `open=false`, retained 분석 record는 0이었다. 기존 저장 disassembly와 run395의 파일 전용 복원 섹션/Capstone reader를 재사용했다. 새 REA target·현재 프로세스는 열지 않았고 새 Evidence ID도 없다. 새 guard·검증 도구는 만들지 않았다.

## 1. 4E96 출현 필드

기존 schema의 required 필드는 **1..24, 27, 28**이다. 아래는 그중 이번 질문에 필요한 필드와 optional override를 정리한 표이며, 이 일부만으로 완전한 출현 메시지가 되지 않는다. f9/f10/f20/f21은 native 문자열로 소비되지만 wire schema는 **bytes**이므로 protobuf string의 인코딩 규칙을 그대로 선언하지 않는다.

| 항목 | 정적 확인 / 필요한 값 | 남은 경계 |
|---|---|---|
| 배우 UID | **f2 required uint32** → SpawnInfo+0 → Actor UID. f16=true일 때 self UID와 비교하여 MyPlayer/다른 Player로 분기한다. | 자기 UID를 바꾸어 쓰거나 자기 Actor 프레임을 복제하는 계약이 아니다. 기존 동료 `0x30000000..0x3000ffff`는 LOCAL 할당 대역이다. |
| 다른 PC 구분 | **f16 required bool=true + nonself UID** → `45550→48510→C24A0`의 Player. false 쪽은 sprite metadata·f39·소유 문자열·f67 등의 추가 조건으로 비Player 종류를 선택한다. | SPR 번호만으로 Player/Monster/NPC가 정해지지 않는다. `f65=2`는 Player의 usershop 특수 상태이며 법사 class3/동료 표식이 아니다. |
| 법사 외형 | **f3 int32** → SpawnInfo+8/+C, optional **f69 int32가 present면 +8을 override** → Action+3C의 effective sprite 조회 키. 원본 `list.spr`:2156에 **734=wizard pc male**, :4002에 **1186=sorceress** 명칭이 있다. | 저장 캐릭터 class3/gender→이 두 번호의 기존 producer 매핑은 명시 LOCAL 정책이다. f69가 있는 DTO는 f3만 바꿔도 effective 외형이 바뀌지 않을 수 있다. 공식 서버 송신·현재 LC 픽셀은 미관측이다. |
| 무기 자세 | **f4 int32** → SpawnInfo+10 → `970B0→B40EE0` → 일반 Action+40 동작군. staff는 **50**이고 50..53은 일반 경로에서 base50으로 정규화된다. | 120을 지팡이로 쓰는 근거는 없다. f4=51도 출현 즉시 공격 재생을 뜻하지 않는다. 실제 SPR의 해당 action row·상태가 필요하다. |
| 이름 | **f9 bytes** → `4B80B/CD0B0` → SpawnInfo+40 → `B5B90` → Description+40. 기존 이름 getter41610과 연결된다. | 정상 인코딩·이름 표시 옵션·현재 화면은 별도다. |
| 칭호 후보 | **f10 bytes** → Description+C8. | 문자열 복사는 확인했지만 최종 라벨 의미/칭호 표시의 끝까지 연결은 미확정이다. |
| 혈맹 관련 입력 | **f19 uint64 → Description+130 → B68F0→648E0→PledgeSubsystem**, **f20 bytes → Description+A8**. 혈맹 식별/문자열 관련 접점이다. | f19의 공식 ID 도메인·서버 캐시 공급, f20의 최종 표시 라벨·문장/색 전체는 미확정이다. 임의 혈맹ID가 실재 혈맹을 만드는 계약은 아니다. |
| 성향/이름색 후보 | **f32 int32 → Description+38** 저장까지 확인했다. 별도 Player HUD 색 경로는 `998660→979D60→1D0470`이며 음수/0..500/>500에 따라 색을 고른다. | **Description+38→HUD+2C writer가 미결속**이므로 f32=최종 이름색/공식 성향 수치라고 확정하지 않는다. RGB wire 필드로 바꾸지도 않는다. |

원문: [run398 상세 결론](../../local_server_rea_20261016/run398_companion_actor_display/README.md), [Actor f3/f4·f16 ownership](../../online_actor_template_source/README.md):7–21, [무기 자세](WEAPON_STANCE_EVIDENCE.md):18–40. 새 발췌의 `SOURCE` 행은 원파일을 식별하며 새 해독과 기존 해독 재사용을 구분한다.

`f16=false, f67=1/2`의 Pet/Summoned 경로는 별개다. 선행 subtype/소유 문자열 조건을 생략하고 법사 sprite를 Pet으로 강제하는 방법은 입증되지 않았다. 반면 최신 [PET_EVIDENCE.md](PET_EVIDENCE.md)의 run400 결과에는 **Player를 유지한 채** f21 nonempty·현재 MyPlayer 이름과 정확 일치·f65!=2일 때 원 펫 클릭 요청으로 이어질 조건부 경로가 있다. 이 조사에서 명령 UI나 그 화면 실행을 새로 시험하지 않았다.

## 2. 다른 Player의 이동과 속도

**SC4E2C는 PC형 actor에도 들어가는 공통 이동 통지다.** required 필드는 **f1 uint32 actor UID, f2 uint32 packed grid, f3 int32 방향**이고 속도 필드는 없다. `4BD3D→627B0`으로 현재 actor를 찾고 공통 ActionComponent에서 MovingAction을 만든다. 원본에서 존재하는 nonself Player가 이 분기에 들어갈 정적 연결이며 NPC 전용 패킷이라는 근거는 없다.

`94570 Start`는 당시 Transform 현재 좌표와 방향 delta로 목표를 계산한다(`94725/94733`). `94E1D→C0E90`은 End에서 current/target을 기록하며 이 쓰기는 self/remote 분기보다 앞이다. remote는 `94842→908A0`의 자기 이동 C2S4E2B 재송신을 건너뛴다. action queue·원 actor 존재·중간 교체 없음 등의 조건은 유지된다.

**f2가 원 송신자의 출발/도착 중 어느 좌표인지는 UNKNOWN이다.** 이 MovingAction loader는 f2 Coordinate를 직접 읽지 않지만, 수신 뒤 별도 좌표 event 소비가 있어 무시해도 된다는 뜻은 아니다. 기존 `local-allied-motion-*`의 PRESTEP은 명시 LOCAL 정책이다. 원 서버의 송신 convention으로 확정하지 않는다.

MovingAction의 frame 간격은 `94A0E..94A70`에서 **같은 owner actor의 SpeedComponent**를 `58190`으로 얻어 `C0210(key0)`에 넘기며 receiver+50/+40/+68을 읽는다. 이 자리에 Speed null 대체값은 없다([run77 consumer](../../local_server_rea_20261016/run77_npc_motion_components/consumer/findings.md):24). 값의 생산자·공식 수치/단위와 현재 동료의 실제 값은 미확정이다.

패킷 송신 간격과 원본 애니메이션 재생 속도는 다른 문제다. 실제 이동 duration/가감속·동료 자신의 유효 속도와 원 서버 cadence는 확인된 생산값/관측이 필요하다. 주인 PC의 속도, 임의 100~200ms 틱 또는 f2 값을 동료의 원본 속도로 쓰지 않는다. 상세 기존 근거는 [run314 계약](../../local_server_rea_20261016/run314_sc4e2c_player_position_commit/contract.md):3–26과 run398의 속도 판정을 따른다.

## 3. 동료의 공격과 피격 대상 표시

**4E31 SC_ATTACK_NOTI의 f2 uint64는 공격자 UID, f3 uint64는 대상 UID다.** 따라서 실제 등록된 동료 UID를 f2, 현재 몹 UID를 f3에 넣는 원본 공통 actor 경로가 있다. 기본공격 kind1은 공격자의 ActionComponent→975D0(type1)→AttackAction으로 이어진다. f1(kind)·f4(raw effect)·f5(direction)도 required이며, f2/f3만 바꾼 불완전 메시지를 완성 계약으로 보지 않는다.

공격 action owner는 f2로 찾은 배우다. action의 +88로 다시 찾는 배우는 f3 피격 대상이다. 동료가 nonself이면 own+f13=false의 자기 공격 생략 조건에 해당하지 않는다. 기존 확인된 kind와 해당 법사 SPR action row·ActionComponent admission에 따라 공격/시전 동작을 선택하며, 기본 물리 공격과 kind18/19 SpellAction을 섞지 않는다.

피격 쪽은 raw f4가 **양수**일 때만 해당 effect branch에 진입한다. token bit·대상 존재·Interaction 및 Action+46/+47 등의 조건 뒤 기본 DamagedAction 또는 DamagedEffectDataTable 레코드 method로 간다. **f4=0이면 이 양성 피격 branch를 건너뛴다. f4를 공식 HP 피해량/HP바 값으로 확정할 근거는 없다.** 서버가 HP를 줄였다는 사실도 이 연출의 실제 소비나 화면 반응을 대신하지 않는다.

근거: [run27 공격자/대상 및 피격 gate](../../local_server_rea_20261016/run27_attack_effect/findings.md):7–45, [SPELL_DISPLAY_EVIDENCE.md](SPELL_DISPLAY_EVIDENCE.md):11–23, run398 상세의 공통 공격 경로. 공격자 동작·대상 피격·서버 HP 변경은 각각 판정한다.

## 4. 다른 Player의 HP 표시

**다른 Player의 일반 HP·MP바는 확인한 생성 초기화에서 숨겨진다.** PlayerActorHud 초기화995C60은 actor UID와 자기 UID의 일치 bool을 HP `996099→9937E0`, MP `996275→993910`에 전달한다. 두 setter는 그 bool이 false면 Node visibility를 false로 한다. 이는 생성 시의 확정된 동작이며 이후 모든 writer·파티·다른 상태에서도 영구히 표시 불가능하다는 결론은 아니다.

**4F1A에는 Player용 debug current/max 텍스트 경로가 별도로 있다.** 공통 수신9832F0의 PlayerActorHud cast→995A00은 f4/f5를 debug Text에 소비한다. 이를 원본 일반 HPbar% setter로 쓰지 않는다. Pet/Summon의 f2 HP%→9829D0→LoadingBar_HP는 해당 HUD cast가 필요하므로 보통 Player에 같은 bar 효과가 난다는 근거가 아니다. required f3의 정상값·업무 의미는 여전히 UNKNOWN이다.

4E38 f10/f11은 자기 CharacterData/HP HUD용이다. 동료 HP를 알리려고 자기 상태 프레임을 보내는 방법은 채택하지 않는다. 4EC8의 익명 세 필드도 동료 UID/current/max로 재명명하지 않는다. 상세 원문은 run398의995C60/9937E0/993910/995A00과 [Pet HP 소비](../../local_server_rea_20261016/run396_pet_control/spawn_hp/findings.md):35–45다.

## 5. 다른 Player 사망·시체·부활·클릭 — run404

**다른 Player도 `4E39` raw8의 공통 DeathAction 경로에 들어가고, 같은 UID를 유지하는 전용 부활 통지 `4F16`이 있다.** `4E96` 재출현과 서로 다른 계약이다. 아래는 run102의 자기 PC 분석을 다른 UID 분기에 대조한 정적 결과이며, 법사 동료의 실제 사망·일어서기 화면을 관측한 결과가 아니다. 원문과 출처는 [run404 발췌](../../local_server_rea_20261016/run404_remote_death_revive/selected-disassembly.txt), [선정 색인](../../local_server_rea_20261016/run404_remote_death_revive/selected-source.json), [상세 결론](../../local_server_rea_20261016/run404_remote_death_revive/README.md)에 있다. 주소는 같은 고정 CONTROL의 RVA다.

### HP0와 사망 동작

`4E39 SC_ACTION_NOTI`의 **required f1 uint64=대상 UID, f2 int32=8**, optional 반복 f3은 최소 사망 subset에서 생략 가능하다. `4EB20→627B0→3ED20→977A0→9AA20/9AC68`은 DestructibleDoor/SegmentProp 특수 분기 밖의 공통 Actor/Action 경로이며 Monster·self 전용 gate가 없다. 정상 등록된 nonself Player도 같은 경로를 쓴다. `9C010` admission과 원 자원·update 조건은 유지되므로 수신만으로 진행 중인 이동/공격의 즉시 선점이나 Death Start를 보장하지 않는다.

동료의 서버 HP0는 별도 권한 상태다. `4E38.f10=0`은 자기 CharacterData용이며 동료 UID의 사망 통지로 전용하지 않는다. `4F1A` debug HP 숫자나 `4E31.f4` 피격 연출만으로 DeathAction이 자동 실행된다는 근거도 없다. **서버 HP 감소·행동 정지와 클라이언트 사망 표시는 각각 연결해야 한다.** 원 공식 HP→사망 통지 순서·피해 수식은 이번에 확인하지 않았다.

### 시체 유지와 자기 PC 차이

Death Start `923A0→8F9A0` 뒤 **ActionComponent+46=0**이다. eligible Next `923D0`의 첫 animation wrap은 `994F0`을 호출하고 DeathAction+80의 corpse latch를 세운다. 그 뒤 이 경로는 프레임 진행을 멈추며 **finished=false**를 유지한다. +46이 true가 되면 eligible Next에서 finished→정상 End로 이어질 수 있다. 고정 시간 뒤 스스로 없어지는 정책은 이 선정 경로에서 확인되지 않았다. 다른 event·제거·맵 전환까지 포함한 영구 잔존 보장은 아니다.

`994F0`은 먼저 actor 사망 event `ActorSubsystem+260→679F0`을 통지한다. 이어 `995DC/995DF`에서 사망 actor UID와 현재 ownUID를 비교하고 **nonself이면 `99C14`로 건너뛴다.** 따라서 자기 PC용 Restart UI/요청 producer를 동료 사망에 적용하지 않는다. 사망 event나 corpse latch는 registry 제거가 아니며, `4E40` 제거와 구별한다.

### 같은 UID의 전용 부활 통지

`4F16 SC_RESURRECTION_NOTI`는 **required f1..4 uint32, optional f5 uint32**다. `52E20`은 f1 UID를 `627B0`으로 찾고, **`52FAF/52FB6`의 ownUID 불일치는 자기 UI 처리만 건너뛰어 `530A1`의 공통 복원으로 진입한다.** 다른 Player도 이 복원의 대상이다. 자기 PC의 `4EEC/4EED` Restart 요청/ACK를 동료 부활의 선행 요청으로 복제하는 계약은 아니다.

공통 복원은 +47 정리, current가 **AppearDeadBody일 때만** 직접 End/clear, **`531F6`의 +46=true**, `96FA0`, Action+38/+40 설정, `977F0(kind1)` admission으로 이어진다. 여기서 **f2→Action+40, f3→Action+38 및 기본96FA0 입력, f5 present이면96FA0 입력만 override**한다. f4는 presence가 필수지만 선정 직접 복원에서 추가 소비는 미확인이다. 실제 원 초기화·자원에 맞는 f2/f3(/f5)를 확보해야 하며 공식값이나 임의0을 추측하지 않는다. 이 통지에는 HP 필드가 없으므로 서버 HP 회복·저장 완료를 뜻하지 않는다.

이번 좁은 factory 추적에서 `977F0(kind1)→97FC3→9802A/98031`은 **vptr1180938, RTTI DefaultAction**을 만든다. `4E31 kind1`의 AttackAction과 다르다. **부활 전용 일어서기 Action·효과나 실제 법사 SPR의 일어서는 프레임은 미확인**이다. DeathAction은 이 handler 반환 순간 바로 삭제되는 것이 아니라 +46 전환 뒤 정상 Next/End와 구분한다.

### 재출현·클릭과 남은 경계

같은 UID의 `4E96`은 `60B50`에서 기존 actor를 `61650`으로 제거하고 새 Player를 생성·게시하는 경로다([run272 계약](../../local_server_rea_20261016/run272_allied_uid_native_lifecycle/source/contract.md):5). **기존 시체의 제자리 복원과 제거 후 재출현을 같은 부활 성공으로 기록하지 않는다.** 관리 NPC로 부활시키는 제품 정책과 원 클라이언트의 어느 통지를 소비할지는 구별한다. 기존 동료 구현에서 사망·부활이 완성됐다는 근거는 없다.

일반 클릭 `AB790`의 `AC60B/AC60F`는 **선택한 대상 actor**의 Action+46이 nonzero일 때만 뒤의 일반 공격/Interaction 검사로 진행한다. 0이면 `AC615`로 내려가 **`AC660→414A0(target)`의 좌표를 `AC682→A2C50` 이동 command로 전달**한다([run404 발췌](../../local_server_rea_20261016/run404_remote_death_revive/selected-disassembly.txt):930–1014). 정상 Death Start 뒤의 대상은 이 일반 공격 경로에 들어가지 않는다. 실제 도착이나 화면 클릭 성공을 관측한 것은 아니며, 이를 모든 hover·hit-test·선택·시체 대상 마법·펫 창 클릭이 불가능하다는 뜻으로 확대하지 않는다. 특히 f21 소유 문자열에 따른 Player의 조건부 펫 요청은 [run400 별도 계약](../../local_server_rea_20261016/run400_pet_command_target/player/findings.md)을 유지하며 사망 상태에서 그 요청이 호출되는지는 미확인이다.

**화면 실험안(UNRUN):** 정상 WORLD의 현재 nonself 법사 UID 한 개에서 정상 피해로 HP0→complete `4E39(raw8)`→사망 동작·시체 정지·주인 Restart UI 불발을 차례로 관측한다. 시체를 일반 클릭/공격 선택했을 때의 이동·요청 유무를 기록한다. 이어 같은 객체에 정상 초기화/자원 입력을 갖춘 `4F16`을 적용하는 안과, 별도 기준 실행에서 제거·complete `4E96` 재출현하는 안을 비교한다. 일어서기 프레임·효과·동료 이름/무기 자세·이후 이동/공격·HP/저장을 각각 판정한다. 원 부활 마법의 시체 선택은 정상 학습·시전 입력이 확보된 별도 관측이며 관리 NPC 부활의 선행조건이 아니다. 새 게임·송신·저장 변경이나 실험 도구는 이번에 만들지 않았다.

## 기존 실제 송신 기록의 범위

| 실행 | 확인된 결과 | 확인되지 않은 결과 |
|---|---|---|
| actual157 | 정상 WORLD→LOCAL F101→**4E96 DRAINED**, Restart4E33→**4E40+4E3B DRAINED**. actor805306368의 서버 tombstone·lease 해제·fresh 읽기 기록. | `native_game=false`, `business_pass=false`, native absence UNSUPPLIED. 원본 LC 출현/이동/공격/제거 화면이 아니다. |
| actual265 | 정상 WORLD→F101 ord5→**4E96 DRAINED1**, actor805306368/member2·서버 pose map0/32577,32945. | Restart ord6 전에 sample297ms>250ms로 실패. **4E40 송신/제거 성공 기록 없음**. removal WRITE_ATTEMPTED/UNKNOWN·lease retained·native false를 보존한다. |

원결과: [actual157 zero-watermark-result.json](../integration-1/packet-companion-zero-watermark-v10-actual-v1/zero-watermark-result.json):961–1060 및1950–1951, [actual265 test-summary.json](../integration-1/packet-comp01-actor-port-binding-v3-actual/test-summary.json):5·39·350–351. 서로 다른 Source·저장의 성공을 합산하지 않았다. 기존 계보·UIDburn을 초기화하거나 재소비하지 않았다.

## 사용자 화면 실험안 — 이번에는 실행하지 않음

아래는 남은 가설을 가르는 후속 실험안이며 구현·송신·게임 기동을 수행한 결과가 아니다. 기존 정상 로그인→캐릭터 선택→WORLD 이후, 같은 현재 맵에서 정당하게 할당된 동료 UID와 현재 몹 UID를 쓴다. 사용자 포커스·커서·전역 입력을 자동 조작하지 않는다. 가설 패킷으로 만든 화면은 공식 정상 payload/원본 서버 정책 PASS와 구분한다.

| 단계 | 고정/변화 | 화면 판정 |
|---|---|---|
| 출현 | complete 4E96의 f16=true·nonself f2, f3=734/1186을 한 외형씩 비교하고 f69가 present면 effective key도 맞춘다. 이름은 실제 저장 이름. 무기군 f4=0/50을 따로 비교. self 프레임과 required 필드는 보존한다. | 주인과 별개 Player로 법사 외형·이름·방향이 보이는지, staff 동작군이 자원에 맞는지. 출현 송신과 실제 표시를 각각 기록한다. |
| 혈맹·성향 후보 | 먼저 혈맹 없는 기준. 정당한 기존 혈맹 자료가 있으면 f19/f20만 대조. f32는 signed 음수/0/양수 후보를 **표시 가설**로 한 값씩 비교한다. | 혈맹 문자열/표식과 이름색 중 무엇이 변하는지. f32 무반응은 연결 부재 증명이 아니며 HUD writer/설정 미확정을 남긴다. 공식 성향 산식으로 승격하지 않는다. |
| 한 칸 이동 | 같은 actor에 공통4E2C. 우선 기존 LOCAL PRESTEP을 명시하고 한 방향 한 칸 후 정지, 이어 같은 외형·자세의 연속 이동을 비교한다. | 한 칸 애니메이션·끝 위치·순간이동/되튐·중첩/멈춤을 관측한다. f2 출발/도착 convention과 원본 이동속도는 별도 미확정으로 남긴다. |
| 공격/피격 | 기존 complete4E31에서 f2=동료/f3=몹. 같은 상황에서 raw f4=0과 양성 후보를 대조하되 실제 HP 계산·소비를 가짜 연출로 바꾸지 않는다. | 동료가 움직이는지, 몹이 맞는 동작을 보이는지, 주인에게 잘못 재생되는지 각각 확인한다. 법사 시전은 별도 kind18/19 근거를 따른다. |
| HP/제거 | Player 기본 HP바 유무를 먼저 관찰. 정상 f3를 확보한 경우4F1A f4/f5 debug 텍스트와 f2 percent 후보를 분리해 비교한다. 마지막은 기존4E40으로 같은 actor를 제거한다. | text/bar 각각의 변화, 주인 HP HUD 불변, 제거 직후 화면 잔존 여부를 기록한다. 텍스트 성공을 HP바 성공으로, 송신 drain을 native 파괴 완료로 확대하지 않는다. |

최소 기록은 현재 UID·f16/f3/f4·실제 송신 필드·전후 화면·공격자/피격자·text/bar 구분·정상 종료/강제 정리 여부다. 새 hook·검사기·상시 polling·전수 해시 대조를 실험 전제에 넣지 않는다.

## 완료 범위

기존 1~4절의 표시·이동·공격·HP와 이번 5절의 다른 Player 사망·시체·부활·클릭에 기존 근거와 좁은 파일 기반 정적 해독을 대조했다. 결과는 **정적 원문/연결 확인 및 미확정 정리**이며 화면·입력·서버 행동·저장/복원 전체의 완료는 아니다. 이번 worker는 run404만, 통합자는 이 문서만 작성했고 실제 발췌를 검토했다. 제품 테스트나 새 게임 실행은 하지 않았다.
