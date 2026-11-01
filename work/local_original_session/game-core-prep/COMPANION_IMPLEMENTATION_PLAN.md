# 동료 법사 구현 계획 (2026-10-28)

결정 원문: [COMPANION_DESIGN_DECISION.md](COMPANION_DESIGN_DECISION.md) "사용자 결정 2차~4차". 원칙: **동료 법사 = 일반 캐릭터와 동일**, 동료는 여러 명으로 늘릴 수 있는 구조, 클라이언트 UI 한계는 브리지 DLL 후킹으로 해결.

근거 문서:
- 펫 창: [PET_WINDOW_EDIT_EVIDENCE.md](PET_WINDOW_EDIT_EVIDENCE.md), [PET_WINDOW_CUSTOM_DESIGN.md](PET_WINDOW_CUSTOM_DESIGN.md)
- ATS: [ATS_COMPANION_EVIDENCE.md](ATS_COMPANION_EVIDENCE.md), [ATS_COMPANION_TOGGLE_DESIGN.md](ATS_COMPANION_TOGGLE_DESIGN.md) (설정 blob 초안 `ats-toggle-analysis/`)
- 줍기: [F4_PICKUP_EVIDENCE.md](F4_PICKUP_EVIDENCE.md)
- 파티 창: [PARTY_COMPANION_EVIDENCE.md](PARTY_COMPANION_EVIDENCE.md)
- 소환 아이템: [COMPANION_TOKEN.md](COMPANION_TOKEN.md) (완료: 2070 신성한 유니콘의 뿔)
- UI 창 열기: [UI_OPEN_EVIDENCE.md](UI_OPEN_EVIDENCE.md)

## 순서

리팩터링(Pro, `refactor/decoupling-20261027`)을 받아 병합한 뒤 서버 쪽을 시작한다. 브리지 DLL(C++)과 독립 변환기는 리팩터링과 겹치지 않으므로 먼저 준비한다.

| 단계 | 내용 | 쪽 | 선행 |
|---|---|---|---|
| 0 | 리팩터링 구조에 맞춰 동료를 독립 기능 모듈로 정리. 동료 정의를 직업 무관 데이터로(여러 명·다른 직업 확장). | 서버 | 리팩터링 병합 |
| 1 | 서버 규칙: 접속 시 자동 재소환, 태세(공격/방어/목표 지정) 확정 의미, 따라오기·대기 = 버프·힐만, 바짝 따라붙기, 주인 사망 시 동료가 자기 귀환 주문서 사용, 동료 사망 경험치 손실(일반 캐릭터 규칙), 사망 아이템 드롭 전역 없음 확인 | 서버 | 0 |
| 2 | 브리지 DLL: 동료 펫 창 7행(공격 목표 지정/공격 태세/방어 태세/동료 설정/동료 가방/동료 장비/따라오기·대기), 해산·이름 모달 우회, 배고픔 줄 제거·성향 실제값 | DLL | 지금 준비 가능 |
| 3 | 브리지 DLL + 서버: ATS 도움말 탭 → "나/동료" 전환, 4ED7 재공급·창 reload, Save(4ED6) 귀속 | DLL+서버 | 2와 병행 |
| 4 | 동료 가방 = 원본 인벤토리 창, 동료 장비 = 원본 장비 창(사용자 결정: 창고 창 재사용 안 함). 인벤토리·장비 창을 동료 모델로 여는 후킹 REA 필요 | DLL+서버 | REA |
| 5 | F4: DLL이 F4 처리를 가로채 "F4 줍기" 신호 → 서버가 동료 주변 줍기(동료 가방·무게·소유권·중복) | DLL+서버 | 0 |
| 6 | 파티 창: 동료를 파티원으로 표시, 08A2/08A3 HP%·MP% 갱신 | 서버 | 0 |
| 7 | ATS 설정 → 동료 AI 적용: 회복 칸(동료 물약 HP/MP%), 기능 아이템(가속 등), 버프 칸(유지 버프), 전투 순차·조건(조건은 동료 자신 기준, ATS 설정만 따름 — 2026-10-28 결정), 옵션(탐색 범위·줍기 무게) | 서버 | 3 |
| 8 | 검증: 봇 시나리오 + 헤드리스 원본 스크린샷(펫 창 7행, ATS 전환, 가방·장비 창, 파티 창), 애매한 것만 사용자 확인 | 전체 | 1~7 |
| 9 | **동료 ATS 창 분리 (다음 구현, 사용자 결정 2026-10-29)**: 기사 ATS는 원본 창 그대로 두고, 동료는 같은 모양의 별도 창을 띄운다. 동료 창은 자기 데이터 모델·동료 가방 아이템 연결·동료 전용 저장 신호를 쓰고 기사 설정(4ED6 f1/f2)은 전혀 건드리지 않는다. 이유: 원본 ATS 모델은 캐릭터 하나용이라 공유 창에 동료 내용을 바꿔 넣고 되돌리는 동안 저장 없음·복원 대기·기사 물약 연결(f1 필드 2 uid) 소실·장비창 닫힘 꺼짐이 계속 나왔다. 필요: ATS 레이아웃 두 번째 인스턴스 생성, 별도 모델, 칸↔동료 가방 연결, 저장 경로 REA. 3단계 공유 창 방식(W50까지)은 분리 완료 후 제거. 검증 때 버프 칸에 여러 버프 마법(동료가 배운 것 여럿, 유지 시간 다른 것)을 넣어 저장·재열기·동료 재시전까지 확인(사용자 2026-10-29). | DLL+서버 | 3·W50 |

## 보류
- 멀리 떨어진 동료 순간이동(사용자 검토 중).
- 기사 접속 중 동료 ATS 편집(2차), 탭 분리 방식(불편하면 전환).
- 더 좋은 법사 무기(마나의 지팡이 등) 아이템 데이터 추가, GM `.item` 채팅 연결.

## Lv30 동료 ATS 서버 조합 시험·수정 (2026-10-29)

기준은 `validation-profiles/manual-test-knight`를 읽기만 한 snapshot이다. SoloMage는 level30, HP317/MP314, 학습38개(실제 `magic.json`의 목록), 능력치8/7/16/18/8/18이다. 원본 프로필·브리지 DLL·launcher·다른 기능 파일은 바꾸지 않았다.

- 원인: AI 시전 소비자가 힐/실드/에너지 볼트만 허용했고, 나머지 ATS kind1 마법은 저장·표시만 됐다. 힐은 자신만 대상으로 했고, 추가 버프의 실제 장비·무게·전투 소비가 없었다.
- 변경: `world_feature_companion.py`에서 기존 `world_magic.PlayerMagic` catalog/계산기를 재사용해 요청17종을 연결했다. 실제 MP 차감·range/LOS·재사용·학습·현재 actor/target 검증과 ATS 칸 순서를 유지한다. 물리 공격/피격, monster-skill physical, 실제 가방 calculated의 DEX/AC/무게, 장비 UID binding을 연결했다. 버프 snapshot은 기존 동료 equipment 메타데이터에 저장하며, 사망에 해제하고 맵이동/재소환/복원에는 남은 기한과 cooldown을 유지한다.
- 힐의 HP 조건은 이번 사용자 요청에 따라 자신/기사 각각에 평가한다. MP/시간/횟수 조건은 기존 동료 자신 기준이다. 둘 다 해당하면 낮은 HP%부터, 동률이면 자신부터 선택하며 거리/LOS 밖 대상 때문에 가능한 다른 회복 대상이 막히지 않는다. 기존 자기대상 전용 기대4개를 이 변경에 맞춰 갱신했다.
- **LOCAL 정책: 홀리 웨폰과 인챈트 웨폰이 버프 칸에 함께 있으면 마지막 무기 버프만 유지한다.** L1J `L1ItemInstance.java:1075-1120`의 같은 아이템 enchant timer 교체 근거를 사용하며 무한 상호 재시전을 막는다. 두 마법은 각각 단독 시험도 통과했다.
- **LOCAL 정책: 큰 피해에서 상위 힐은 사용자가 정한 칸 순서/HP 조건으로 선택한다.** 예: 그레이터 힐 HP<=20 → 익스트라 힐 HP<=50 → 힐 HP<=80. 선택하지 않은 마법을 자동으로 넣지 않는다.
- `hunt_bot_companion.py`의 임시 실행 폴더만 기존 runs 아래 UUID + 일반 `Path.mkdir`로 만들도록 고쳤다. Windows Store Python3.13 `mkdtemp(mode0700)`의 신규 폴더 ACL 때문에 sandbox가 하위 파일을 쓰지 못한 환경 실패를 회피한다. 기존/실패 폴더의 ACL은 바꾸지 않았다. magic 시나리오의 힐 대상 검증도 현재 자신/기사 정책에 맞췄다.

수치 근거는 기존 `data/m3/player_spells.json`의 공식/LOCAL 표기를 유지한다. L1J SQL의 다른 MP·HP·지속시간으로 덮어쓰지 않았다. L1J 참조는 `D:/SingleLineageRef/l1j-en-classic`의 `skills`/`L1SkillUse`/`L1ItemInstance`다. cure_poison은 독이 있을 때만, remove_curse는 독 또는 기존 CURSES 효과가 있을 때만 소비한다. blind 등을 CURSES로 다루는 범위는 기존 player와 같은 LOCAL 확장이다.

### 조합 결과 (단위 fixture 시간 초, 직접 함수/상태 입력)

다음은 원본 프로필 snapshot을 사용한 **단위/개발 검증**이다. 실제 화면·입력이나17종 전체의 socket gameplay PASS를 뜻하지 않는다. `world_companion_spell_matrix_tests.py`에서 kind1 codec을 그대로 읽고 기존 실제 WorldView/장비/맵 이동 경로를 소비했다. 상세 출력은 `runs/companion-all-unit-20261029-cold-final.log`다.

| 버프 | 대상 | 성공시각 / 횟수 | MP |
|---|---|---|---|
| 실드 | 자신 |10,1209,2411 /3|2|
| 블레스드 아머 | 자신 현재 몸통 장비 |10,1809,3611 /3|20|
| 인챈트 덱스터리티 | 자신 |10,1209,2411 /3|35|
| 홀리 웨폰 | 자신 현재 무기 |10,1209,2411 /3|10|
| 인챈트 웨폰 | 자신 현재 무기 |10,1809,3611 /3|20|
| 디크리즈 웨이트 | 자신 |10,1809,3611 /3|10|

각 버프는 첫시전/지속중 미재시전/기존 refresh lead10초 밖 미재시전/만료1초 전 갱신/갱신 효과 만료 후 시전/MP0 미시전을 확인했다. 실제 장비 계산은 DEX+5, 무게 한도+180, 실드+아머 AC-5를 확인했고, NPC/monster-skill 양쪽에서 AC-5가 한 번만 적용됐다. 장비 UID가 바뀌면 기존 무기/아머 효과가 적용되지 않으며, MP가 부족한 앞 버프를 건너뛰고 뒤 힐은 실행된다.

| 힐 | 기사 시각/횟수 | 자신 시각/횟수 | 조건 |
|---|---|---|---|
| 힐 |11/1|14/1|HP<=50|
| 익스트라 힐 |21/1|24/1|HP<=50|
| 그레이터 힐 |31/1|34/1|HP<=50|

임계 초과에서 미시전, 임계 이하에서 실제 HP 회복·MP 차감, 기사/자신 중 가능한 낮은 HP% 대상, 먼 기사 대신 자신 회복을 확인했다. 큰피해 기사HP10에서 설정된 앞 칸 그레이터 힐은50초에1회, 힐만 선택했을 때는51초에 힐1회였다.

| 공격 | 대상 | 성공시각/횟수 | 최대거리 / MP / 재사용 |
|---|---|---|---|
| 에너지 볼트 | 실제 fixture monster |10,11/2|10 /3 /1초|
| 아이스 대거 | 동일 |15,16/2|10 /3 /1초|
| 파이어 애로우 | 동일 |20,21/2|10 /3 /1초|
| 라이트닝 | 동일 |25,26/2|6 /13 /1초|
| 파이어볼 | 동일 |30,31/2|6 /16 /1초|
| 콘 오브 콜드 | 동일 |35,36/2|6 /21 /1초|

모두 거리+1/MP비용-1/재사용0.5초에 미시전, 경계거리/충분MP/재사용1초에 시전했다.6칸 순서는50~55초에 설정 순서대로 각각1회, 파이어볼은60초에 반경 안 실제 monster2개를 소비했다(기존 catalog의 라이트닝 radius3/파이어볼 radius2).

조건 칸 cure_poison은 독 없음0회→자신 독11초1회→해제 후0회, remove_curse는 저주 없음0회→자신 저주21초1회→해제 후0회였다. 별도 조건 칸 remove_curse는 자신 독만10초/독+저주13초, 기사 독만20초/독+저주23초에 각각1회이며 후속 요청은 미시전했다. 실제 core cross-map relocation 후3버프 deadline/미재시전을 확인했다. 사망 hook에서 전체 버프를 해제한 뒤 정상 manager.revive API로 되살린 새 life에서36초 실드1회(만료1236)를 확인했다. cold snapshot은 모든 성공시전의1초 reuse를 저장하고 wall0.25초 경과 복원 시0.75초 남음을 지켜20.74초 미시전/20.75초 힐 시전했다.

### 실행·한계

전체 동료 단위13 suites **252 tests OK, skipped1**. skip은 `SL_RUN_COMPANION_INTEGRATION=1`이 필요한 별도 opt-in socket lifecycle이며, 같은 서버 흐름은 아래 기존 봇으로 따로 실행했다. 로그의 `FIRST_STARTUP_ERROR` traceback은 기존 실패보존 시험이 의도적으로 주입한 입력이고 suite 결과는 OK다.

PowerShell 재현(단위에만 신규 mode0700 mkdir를0777로 바꾸는 프로세스 내 실행 shim; plain `-m unittest`가 통과했다고 표시하지 않음):

```powershell
$env:TEMP=(Resolve-Path work/local_original_session/runs).Path
$env:TMP=$env:TEMP
$env:SL_TEST_PORT_BASE='47100'
python -X utf8 -B -c "import os,runpy,sys; from pathlib import Path; original=os.mkdir; os.mkdir=lambda path,mode=0o777,**kwargs: original(path,0o777 if mode==0o700 else mode,**kwargs); root=Path('tools/local_original_session'); names=sorted({p.stem for p in root.glob('*tests.py') if p.stem.startswith(('world_companion','companion_ai','companion_ats','ats_config_codec'))}); print('SUITES '+','.join(names),flush=True); sys.argv=['unittest']+['tools.local_original_session.'+n for n in names]; runpy.run_module('unittest',run_name='__main__')"
```

봇은 shim 없이 기존 wrapper로 실행했다. FIRST/login/캐릭터 선택/월드 진입/실제 decoder-router-handler 순서와 원 finally/close를 유지한 신규 시험 프로필이다.

```powershell
$env:SL_TEST_TIME_SCALE='10'
$env:SL_TEST_PORT_BASE='47100'
python -X utf8 -B tools/local_original_session/run_fast.py hunt_bot_companion --scenario all
```

첫 전체 봇은 `runs/hunt-companion-89cb191f6639/summary.json` **SUCCESS91/cleanup_complete=true**, 별도 ATS창 프로필29도 SUCCESS였다. 원로그는 `runs/companion-bot-all-20261029.log`. 이후 cold restore/reuse 보완의 최종 봇 결과는 아래에 기록한다.

미확인: 클라이언트/화면/드래그/새 마법 아이콘·이펙트 소비는 실행하지 않았다. 단위17종 통과를 전체 원본 동등성으로 확대하지 않는다. 실제학습38 중 이번 요청17종만 AI 시전 지원이며 다른 선택은 unresolved다. SoloMage를 직접 선택한 ordinary player MagicStore와 autonomous 동료의 버프 snapshot을 상호 이관하는 계약은 이번 knight 기준 범위에서 연결하지 않았다. 원본/사용자 저장은 보존했다.

최종 제품 소스 전체 봇: `runs/hunt-companion-c4aae2c4c31f/summary.json` **SUCCESS91/cleanup_complete=true**, 별도 ATS창 `runs/hunt-companion-2ecf5755c90c/summary.json` **SUCCESS29/cleanup_complete=true**. 로그는 `runs/companion-bot-all-final-20261029.log`. 이후 magic-only fixture 보완은 아래 추가 시험에 해당하며 전체 봇 경로는 바꾸지 않았다.

추가 기존 `--scenario magic` socket smoke의 최종 결과는 `runs/hunt-companion-fb848cdae980/summary.json` **SUCCESS5/cleanup_complete=true**,3개 epoch 모두 failure_code/close_code 없음이다. 로그는 `runs/companion-bot-magic-verified-20261029.log`; 위 봇 명령의 `--scenario all`을 `--scenario magic`으로 바꾸면 재현한다. 실제 실드는21211.316초 MP52→50/1회, 기사 힐은21212.329/21213.434/21214.540초 대상UID1/3회(MP50→46→42→38, HP실회복17/14/8), 에너지 볼트는21230.524초 대상UID268435474/1회(MP38→35, 피해21)였다. 힐이 실제1회 이상 존재함과 소유한 자신/기사 대상만 시전함을 함께 검증해 빈 집합 성공을 막았다.

이 smoke의 기존 fixture 결함도 제품 guard를 바꾸지 않고 고쳤다: 사전 학습3개를 현재 권한원 `MagicStore.save`로 준비, 초기 HOLD 뒤 target 탐색 전에 기존 `movement-follow` socket 신호, 새 기사 힐 비용을 수용할 정상 계산 maxMP52를 FIRST 전에 준비한다. 초기 `learned[]`에 의한 UNCONFIRMED(`633cfd6b26d6`), 멀어진 HOLD 동료 재조회에 대한 정상 visible guard 실패(`c4594e58d803`, `52625894b7d3`), 기존 MP14가 기사 힐로 소진되고 food0 재생 차단된 bolt timeout(`b9872ab5164e`)을 모두 보존했고 각각 cleanup_complete=true였다. 수정 후 첫 성공 `f673d3d41c38`도 별도 보존했다. 이 준비는 level5/학습3개의 기존 smoke용이며 level30/학습38 단위 결과와 합산하지 않는다.

정확한 소스 SHA256: 제품 `world_feature_companion.py`=`31C873E1CD2FCBEEB7A9E2DB95DB236B3ECD47EFBA4DE7B41891394D9606387B`; 전체91 당시 harness `hunt_bot_companion.py`=`31CA37FFCC7DE470B7D41C1B9994B0E2BC0C1B91E26F8B7A0065AC3861A80225`; magic-only fixture 보완 후 현재 harness=`6249D8114C0F24971E356E8E8A130A973FB22EC3A828476A9F018A21F26AA914`. 전체252 당시 `world_companion_magic_tests.py`=`D961786AE5DAA3A01B162D01429306A71F6DA10EF71873419342847E26954604`, 신규 matrix=`1A556426C2208A3391AF31F91C4FF6BECA0AD655DE5E324E7F1CDFDA4C6CD00D`. 이후 제품 소스 수정은 없다. 다른 dirty 파일·브랜치·커밋은 건드리지 않았다.
