# 원본 무기 자세와 120의 정적 근거

2026-10-26 사용자에게 명시 승인된 **이번 정적 분석만** 수행했다. 전체 제품 STOPPED는 유지한다. 게임·서버·네이티브 원본 코드 실행, 제품 코드 수정, 저장·원본·다른 run 수정, commit은 없다. 판정은 **무기 동작군 이름과 정적 선택 연결 확인 / 현재 PC 화면·실행 결과 미관측**이다.

**지팡이 동작군은 50이다.** 원본 `list.spr`에 `50.walk staff`, `51.attack staff`, `52.damage staff`, `53.breath staff`가 직접 적혀 있다. **120을 staff로 연결하는 원본 근거는 없다.** 120 자체의 명시 이름은 일부 외형의 `walk sky`/`walksky`/`walk fly`이고, 120–123군에는 외형에 따라 비행·숨은 상태 등의 동작이 있다. 970B0의 입력120에는 일반 무기 자세와 다른 특수 처리도 있다.

## 고정 비교 기준과 재사용

- 원본 버전 `26.09.29.2001`, CONTROL `9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`, CODE record `a49e798ded9ed540abb2c6848fdd678cb1a2a12fc3ec243f301f69348bfb4b24`. [기존 정규화 계약](../../local_actor_state_translation/source-contract.json):3–6의 식별자를 재사용했다.
- 원본 자료 [list.spr](../../source_actor_sprite/raw/data/list.spr)는 `data_0.lcx` 유래, 971,536B, SHA-256 `a3e184ed84af2b1e7d429461c555b281aaf9d8858cdced22b9dd0d708921fa44`다. 버전·인증·readback은 [기존 provenance](../../source_actor_sprite/provenance.json):2–14 및 proof에 있다. 이번에 원본을 다시 추출하거나 바꾸지 않았다.
- 기존 [Actor f3/f4 계약](../../online_actor_template_source/README.md):12–21, [정규화 분석](../../local_actor_state_translation/report.md), [run102 resource 계약](../../local_server_rea_20261016/run102_own_player_death_recovery/resource_input_delta/findings.md):9–28, [SPR 소비 원문](../../source_actor_sprite/source.json)을 먼저 재사용했다. shared-api·game-core-prep·REA HANDOFF의 같은 주제 검색에서 무기 이름을 확정한 별도 계약은 찾지 못했다.
- REA 스킬과 native guide를 적용했다. `binary_session({})`의 `open=false`를 확인했고 target을 열거나 실행하지 않았다. 추가 범위는 기존 고정 CONTROL reader와 이미 설치된 Capstone으로 파일만 읽어 해독했다. 새 guard·검사기·시험 suite는 만들지 않았다. REA native dossier를 새로 발행한 결과가 아니므로 새 REA Evidence ID는 없다.

검토용 원문은 [source-excerpts.txt](../../local_server_rea_20261016/run385_weapon_stance_table/source-excerpts.txt), [spr-excerpts.txt](../../local_server_rea_20261016/run385_weapon_stance_table/spr-excerpts.txt)다. 각 발췌에 부모 파일/JSON pointer 또는 원본 SPR 행을 적었다. 아래 `코드 L`/`SPR 발췌 L`은 이 두 파일의 실제 행이다. 모든 코드 주소는 CONTROL **RVA**이며 현재 프로세스 주소가 아니다.

## 값별 판정

각 base의 +0/+1/+2/+3은 원문상 walk/attack/damage/breath다. 일반 정규화 입력 구간과 나중에 선택되는 개별 애니메이션 ID를 구분한다. 예를 들어 wire f4=51도 일반 경로에서는 base50이 되며, 그 패킷만으로 공격51을 실행했다고 할 수 없다.

| Action+40 base | 일반 B40EE0 입력 구간 | 원본 SPR 이름 | 원본 #0 행 / 발췌 행 | 판정·제한 |
|---:|---:|---|---|---|
| 0 | 아래 구간 밖의 모든 u32 | walk / attack / damage / breath | 3–6 / L5–8 | 기본 동작군. 원문에 무기명은 없으며 ‘맨손’ 화면은 이번 미확인 |
| 30 | 30–33 | onehandsword | 7–10 / L9–12 | 한손검 동작군, 정적 명시. 사용자 ‘검’ 관측과 일치 |
| 35 | 35–38 | axe | 12–15 / L13–16 | 도끼 동작군, 정적 명시. 사용자 ‘도끼/둔기’ 중 둔기 item 분류와의 대응은 별도 |
| 40 | 40–43 | bow | 20–23 / L17–20 | 활 동작군, 정적 명시. 사용자 관측과 일치 |
| 45 | 45–48 | spear | 24–27 / L21–24 | 창 동작군, 정적 명시. 사용자 관측과 일치 |
| **50** | **50–53** | **staff** | **28–31 / L25–28** | **지팡이 동작군, 정적 명시.** 화면상 도끼처럼 보였다는 관측과 모순되지 않음 |
| 55 | 55–58 | dagger | 32–35 / L29–32 | 단검 동작군, 정적 명시. 사용자 관측과 일치 |
| 60 | 60–63 | largesword | 36–39 / L33–36 | 원문 largesword 동작군. 사용자 ‘양손검’ 관측과 대응. 별도 아이템 장착 분류 전체는 미추적 |
| 120 | 120–123 | 외형별 별도 동작군, 아래 참조 | #0에 없음 / L169–193 | staff 아님. raw120 특수 분기와 일반 정규화 결과120을 구분 |

표의 무기명은 다른 게임이나 L1J에서 가져오지 않고 이 고정 원본의 이름에서 읽었다. 사용자 관측은 요청문에 제공된 기록이며 이번 worker가 화면을 재확인한 결과가 아니다. 원문의 `17.wand`는 별도의 단발 행동 이름이며 staff base50과 번호 공간을 섞지 않는다(`list.spr`:17).

명시적으로 추가 발췌한 PC 외형은 #0 prince, #1 princess, #61 knight, #138 elf male, #734 wizard pc male뿐이다. #0/#1/#61에는 위 일곱 무기군이 있고 #138/#734에는 이 발췌 범위에서 60–63이 없다. 이 부재를 모든 외형의 장착 제한이나 런타임 fallback 규칙으로 확대하지 않는다. 모든 PC·변신·자원군 전수 지원은 판정하지 않았다.

## 생산자부터 실제 애니메이션 표 소비까지

표기: A=ActionComponent, D=현재 만들거나 시작하는 ActionBase 파생 객체, R=현재 외형의 Sprite metadata record. A와 D는 다른 객체다.

1. **wire 입력과 정규화:** 정상 ActorNotify(4E96) f4 i32는 기존 계약에서 Proto+84→SpawnInfo+10이다. `CD10F`가 Info+10에 저장하고 `96E66`이 R8D로 읽어 `96E70→970B0`에 전달한다(코드 L4–11). 970C4가 ESI에 보존한다. 일반 경로는 `973A3 ECX=ESI →973A5 B40EE0 →973AA [A+40]=EAX`다(코드 L115–117). B40EE0은 비교/상수 반환뿐인 123B leaf이며 위 8개 base 또는0을 돌려준다(코드 L13–59). 입력30–33 등이 같은 base가 되는 이유까지 확인했지만 역사 wire 입력의 고유 복원은 불가능하다.
2. **A+40을 동작 선택 키로 소비:** 일반 초기화는 `973D7→977F0(A,mode1,context)`를 호출한다(코드 L124–128). `9783F`가 A+40을 읽고 `97FDB`에서 D+10에 저장한다. mode1은 vtable1180938/RTTI `DefaultAction`을 만든다. 현재 외형 metadata가 있으면 `980AE–980BB`에서 첫 entry ID+A+40으로 D+10을 다시 정한다(코드 L131–180). ‘정규화 직후 값이 언제나 최종 애니메이션 ID’라고 단순화하면 이 덧셈을 놓친다.
3. **후속 동작의 base+offset:** `9A0C0`의 `9A104–9A108`은 `action_id=A+40+R8D`를 계산한다. +0/+1/+2/+3 생성 분기가 D+10에 이 action_id를 보관한다(코드 L294–349). 원문 SPR에서 50/51/52/53 등의 이름이 walk/attack/damage/breath로 나뉜다. 이번에는 모든 상위 입력 caller·공격 특수 variant(+4)·전체 전환 수명까지 복원하지 않았다.
4. **D에서 실제 Sprite entry 선택:** action은 `9C010`의 queue에 소유권 이동된다(코드 L351–361). DefaultAction의 Start92D10은 ActionBase Start8F9A0을 부른다(코드 L363–367). ActionBase vtable1180C08의 Start도8F9A0이다([action-types.json](../../local_server_rea_20261016/run385_weapon_stance_table/action-types.json)). `8FA6D/8FA70`이 D+10/action ID, D+14/variant를 `348C80`에 전달한다. 그 함수는 R+10/+18의 0x28-byte entry 배열에서 entry+0의 ID를 비교하거나, variant가 있으면 R+28/+30 배열에서 ID와 entry+4를 함께 비교한다(코드 L208–238, L431–451). **따라서 숫자는 이름 표만 있는 장식값이 아니라 실제 entry 조회 키다.**
5. **원본 SPR 숫자와 entry의 연결:** 원 파서 `3473D3`이 action 번호를 읽어 R14에 놓고 `34798E→34799B`에서347F50에 넘긴다. `347F9E`가 entry+0에 그 번호를 저장한다. `3484C7–3484EF`는 A.B:C를 단계+0/+4/+8에 보관한다(코드 L369–415). 영어 동작 이름은 사람이 읽는 원본 라벨 근거이고 실행 selector는 이 숫자다.
6. **선택된 entry에서 자원 group으로:** 8F9A0은 선택된 단계 A에 mode에 따른 facing delta를 더해98F60에 넘긴다. **단계 A=-1일 때만**8FB4E가 A+40을 대신 쓴다(코드 L453–463). 이 fallback을 모든 무기 애니메이션의 주 선택식으로 오해하지 않는다. #0 staff50은 실제 A232 등을 사용하므로 앞의 D+10/348C80 경로가 이름 연결의 핵심이다. 98F60은 현재 Sprite R+C의 signed-positive resource alias 또는 R+0을 고르고, resource/group을 cache key로 조회한 뒤 miss면35B190을 호출한다(코드 L465–506). 실제 로딩 성공·픽셀·화면은 정적 연결과 별개로 이번 미관측이다.

8F9A0의 D+30 appearance override와 D+34!=0의 A+40 덮어쓰기도 있다(코드 L417–429). A+48 resource-only branch와 Effect/Projectile/InteractiveNPC/DestructibleDoor/SegmentProp 타입 분기는 기존 정규화 계약을 유지한다. 따라서 어떤 actor든 f4를 보내면 반드시 위 일반 경로가 실행된다고 주장하지 않는다.

## 왜 50이 도끼처럼 보이는가

#0 prince의 axe35–38과 staff50–53은 같은 A/B/C 프레임과 group을 재사용한다. walk는 둘 다 `232.0:4 …232.3:4`, damage는240/256, breath는240을 쓴다. attack36/51의 A/B/C 및 annotation도 같지만 **axe36에만 `**1052**`가 있고 staff51에는 없다.** 따라서 동일 모양이라는 설명과 동일 속도·전체 상태라는 주장은 다르다(SPR 발췌 L13–16, L25–28).

#1 princess도 해당 프레임 재사용을 보이지만 전 외형에 일반화할 수 없다. #61 knight는 attack의 annotation도 다르고, #734 wizard는 axe walk35의 A272와 staff walk50의 A144가 다르다(SPR 발췌 L83–98, L148–163). 사용자의50 관측 외형이 무엇이었는지는 이번에 확인하지 않았다.

## 120의 확인된 의미와 남은 범위

970B0이 raw ESI=120을 받으며 앞선 flag/type 전용 경로로 빠지지 않은 경우, `972DA A+40=120 →972FF EDX=123 →97307 977A0`을 수행한다(코드 L79–92). 977A0은123을 9AA20의 action ID로 넘긴다. 123은9AA20의 switch 범위8–118 밖이라 기본 ActionBase를 만들고 D+10=123을 저장한 뒤9C010으로 넘긴다(코드 L194–206, L240–275). 즉 **입력120에서 곧바로 고른 동작은123**이다.

이후 `9730C–9731D`는 Actor 경유586E0으로 얻은 **InteractionComponent+89**를1로 쓴다. Action+89가 아니다. 586E0의 RTTI 대상은 RVA166A058, 원문 이름 `.?AVInteractionComponent@lineage@@`다(코드 L93–97, L277–292). 이 byte의 공식 이름과 전체 후속 동작은 미추적이며, 이를 독립적으로 ‘비행 플래그’ 또는 ‘은신 플래그’라고 확정하지 않는다.

고정 list.spr 전체에서 **명시적인 action120–123 줄**을 골랐으며 12줄이다. 이것은 텍스트상의 명시 정의 범위이지 alias·상속·fallback까지 전개한 전체 런타임 지원 범위가 아니다.

| 원본 외형 header | 명시 ID와 이름 | 원본 행 / SPR 발췌 행 |
|---|---|---|
| #49 golem | 122 hide damage, 123 hide breath | 332–333 / L169–171 |
| #145 spartoi | 122 hide damage, 123 hide breath | 827–828 / L173–175 |
| #1024 harphy | 120 walk sky, 123 breath sky | 3262–3263 / L177–179 |
| #1245 antharas | 123 hide breath | 4202 / L181–182 |
| #2353 griffon | 120 walksky, 123 breathsky | 7753,7758 / L184–186 |
| #2363 harphy | 120 walk fly, 123 breathsky | 7843,7850 / L188–190 |
| #8126 sea harphy | 123 breathsky | 14173 / L192–193 |

121의 명시 정의는 이 파일에서 없고, 위 PC 표본에는120–123 명시 정의가 없다. **120 자체를 무기종류로 명명하거나120군 전체를 비행 하나로 명명할 수 없다.** 보수적 해석은 ‘외형별 특수 동작군 base120; 명시120은 공중 이동, 122/123에는 숨은 상태 동작도 있음’이다. 이 그룹 전체의 원래 enum 이름은 UNKNOWN이다. 실제 자기 PC에120을 준 화면·실루엣·빈 entry 처리의 최종 결과는 이번 미확인이다.

`B40EE0(121/122/123)=120`의 일반 계산과 **raw120에만 있는 위 직접 저장/123 action/Interaction+89 처리**는 동일 동작이 아니다. 121을 보내면120의 특수 분기가 재현된다고 할 수 없다. 특수 actor 타입이나 A+48 branch도 앞에서 가로챌 수 있다.

## 로컬 설정과 후속 최소 관측

현재 로컬 `staff=120`은 [기존 triage](FAILING_TESTS_TRIAGE.md):82 및 로컬 자세 데이터/시험이 서로 맞는다는 기록일 뿐이다. 이 분석의 **원본 staff 동작군50**과 충돌한다. `template230=참나무 지팡이`의 item/resource 대응([ITEM_WEIGHT](ITEM_WEIGHT.md):55)은 별도 아이템 이름 근거이며, 그 자체로 Actor f4=120의 근거가 되지 않는다. 이번 소유 범위에는 제품 설정 수정이 없어 그대로 보존했다. ‘모든 지팡이 아이템의 정상 서버 송신값까지 복원’한 것은 아니다.

남은 화면 질문을 위한 최소 실험안은 [기존 별도 재기동 방법](USER_TEST_CHECKLIST.md):42–46의 `-TestKnight -Stance`를 그대로 사용해, 정상 Quit 후50·35·120을 각각 따로 기동하고 같은 외형/방향에서 정지·이동·공격 한 번씩 비교하는 것이다. 이 문서의 staff50 근거가 체크리스트42행의 이전 ‘120 후보’를 대체하며, 체크리스트 파일과 제품값은 이번에 수정하지 않았다. `-Stance`는 무기와 무관한 자기 자세 강제이므로 정상 지팡이 장착 시험 성공과 구분한다.

#0/#1/#61처럼 자원을 재사용하면 같은 모양만으로 분류를 판정하지 말고50의 원문 staff 이름과 함께 기록한다. wizard734는 원문 group이 다른 참고 표본일 뿐이며 현재 실제 외형과의 대응·기동 방법은 확인하지 않아 새 실행법을 제안하지 않는다. 120에서는 초기123 선택·정지/이동·공격 상태와 정상 Quit 복구 결과를 기록한다. 현재 원본 게임은 실행하지 않았고 이 실험의 결과는 UNKNOWN이다. 화면 비교에 쓰인 f4와 실제 A+40/D+10을 구별해야 한다.

새 테스트 PASS나 화면 동등성 PASS는 선언하지 않는다. 확인한 것은 기존 고정 자료의 원문 재사용, 파일 기반 정적 해독, 표본 SPR 라벨 및 실제 소비 명령 연결이다. 분석 산출물은 [run385](../../local_server_rea_20261016/run385_weapon_stance_table/) 안에만 추가했다.
