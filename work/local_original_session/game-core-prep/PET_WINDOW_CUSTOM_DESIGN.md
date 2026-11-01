# 동료 PetStatusLayout 맞춤화 — 브리지 DLL 구현 설계

2026-10-28 · **정적 분석·설계만 수행. 게임·서버·포트·원 함수 실행·live attach·스크린샷·커밋 없음. 이 문서만 신규 작성하며 제품 코드·핀 대상 DLL·원본·자원·저장·프로필·ACTIVE_TASK는 수정하지 않는다.** 이번 직접 요청의 분석 범위이며 제품 일반 중지나 다른 기능 동결의 해제가 아니다.

## 1. 구현 방향과 확인 수준

**원본 클라이언트에 넣는 브리지 DLL에서 PetStatusLayout의 동료 instance만 꾸미고, 원본 클릭 진입점과 목적창 모델을 연결한다.** 원본 Text·스킨·장면·입력 및 창 소유 체계를 재사용한다. 전역 string.csv/CSB 변경이나 폐기한 Win32/GDI UI 복귀는 필요하지 않다. 설정은 ATS 안에 DLL이 추가하는 **동료 탭**, 가방은 **창고 UI의 A/B 모델 재사용을 우선**, 인벤토리 UI를 별도 동료 view로 만드는 대안도 아래에 설계한다.

| 표시 순서 | 재사용 원 노드 / 원 invoke RVA | 동료에서의 새 동작 | 일반 펫·소환수 |
|---|---|---|---|
| 1 공격 목표 지정 | `Targeting` / `A84480` | 원 target-selection→실제 적 클릭→4F02 mode1 유지 | 원 동작 |
| 2 공격 태세 | `AttackStance` / `A843A0` | 원 mode2, 실제 동료 전투 상태 갱신 | 원 동작 |
| 3 방어 태세 | `DefendStance` / `A842C0` | 원 mode3, 실제 동료 전투 상태 갱신 | 원 동작 |
| 4 동료 설정 | `Spread` / `A84100` | 원 invoke를 소비하고 ATS 동료 탭 열기 | 산개 mode7 |
| 5 동료 가방 | `Alert` / `A84020` | 원 invoke를 소비하고 동료 가방의 꺼내기/주기 view 열기 | 경계 mode5 |
| 6 따라오기/대기 | `Gather` / `A83F40` | 이동 상태 FOLLOW/HOLD 전환 요청. 전투 태세는 유지 | 수집 mode6 |

`Rest`·`Dismiss`·`Name`은 표시와 입력에서 제외한다. 배고픔 `Hunger`도 제외한다. `MyPet` 이름·현재 상태·HP·MP·레벨·경험치·실제 성향은 유지한다. 원 행 노드를 삭제하지 않고 재사용/복구하므로 원 갱신기와 소멸자의 수신 포인터를 보존한다. 이 6행 구성은 사용자 결정이며, 새 동작의 wire 의미는 아래 **LOCAL 설계**다.

**확인[정적]**은 보존 원문·복원 carrier·CSB·현재 서버 코드의 사실이다. **설계[LOCAL]**은 DLL/서버에 추가할 계약이다. **UNKNOWN**은 정확 API/ABI 또는 실행 관측의 미확인이다. 이번 결과를 주입·창 표시·클릭·거래·저장 성공으로 부르지 않는다.

기준은 LC **26.09.29.2001**, CONTROL SHA256 `9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`. 주소는 모두 **RVA**, 실행 주소는 `현재 모듈 base + RVA`; preferred VA만 `0x140000000 + RVA`다. 파생 분석 carrier는 `work/rea_lineage_resume_20261013/main-gameplay/audit/metadata-v2/DERIVED_RESTORED_ANALYSIS_ONLY.exe`, 기존 SHA256 `c822838351d774a2022af434829a36dbd9bee030bf22182b834ca4e8659701a9`다. 원본 실행파일과 carrier를 같은 파일로 취급하지 않는다. 신원은 [TARGET_IDENTITY](../../local_server_rea_20261016/TARGET_IDENTITY.md)와 기존 manifest에서 승계했으며 전파일 재해시는 하지 않았다.

출처는 **로컬 원본 코드·자원 및 현 서버 소스 100%, 신규 외부 웹·공식 API·L1J 채택 0%**다. 기능의 원본 동등성 비율이 아니다. 추가한 내용은 아래 instance 분기·후킹·ATS 동료 탭·가방 두 안·LOCAL 패킷/모델 계약·구현/검증 순서다. 새 의미와 서버 정책은 원본 사실로 섞지 않는다.

## 2. 재사용 근거와 이번 보강

| 근거 | 이번 설계에서 쓰는 범위 |
|---|---|
| [앞선 편집 조사](PET_WINDOW_EDIT_EVIDENCE.md), [Pet 계약](PET_EVIDENCE.md) | 9행·명령·팝업·4F14 필드, CSB 공유와 갱신 덮어쓰기 |
| [REA396 pet-init](../../local_server_rea_20261016/run396_pet_control/commands/pet-init.txt), [pet-commands](../../local_server_rea_20261016/run396_pet_control/commands/pet-commands.txt), [pet-update](../../local_server_rea_20261016/run396_pet_control/commands/pet-update.txt) | 원 named lookup/callable 등록·Minion UID·Text 갱신·child 수명 |
| [팝업 보강 원문](pet-window-static/selected-static.json), [REA400 target](../../local_server_rea_20261016/run400_pet_command_target/target/selected.txt) | 해산·이름·닫힘과 목표 지정의 후속 actor 클릭 |
| [ATS 조사](ATS_COMPANION_EVIDENCE.md), [ATS 추가 원문](ats-evidence/ui2_findings.md) | 실제 ATS 클래스/탭·Show·PC model·Save/4ED6·학습/가방 연결 한계 |
| [창고 조사](WAREHOUSE_EVIDENCE.md), [REA394 발췌](../../local_server_rea_20261016/run394_warehouse_ui/source_excerpts.md) | COUNT/LIST→A/B→선택·수량→4ED1→즉시 close/097B |
| [UI 진입 조사](UI_OPEN_EVIDENCE.md), [동료 장비 조사](COMPANION_EQUIPMENT_EVIDENCE.md) | owned UI thread·Actor lookup·현재 PC inventory UI·장비/주기 |
| [기존 bridge](../../../tools/local_original_session/native/ui_open_bridge.hpp), [현재 동료 handler](../../../tools/local_original_session/world_feature_companion.py), [가방 소유자](../../../tools/local_original_session/world_feature_trade.py) | 현재 구현 범위와 추가가 필요한 서버/브리지 경계 |

이번 새 정적 읽기는 설치된 `pefile.PE.get_data`+Capstone으로 해당 carrier의 선택 RVA만 해석했다. 새 분석 DB·검사기·실행 도구·별도 보고서 파일은 만들지 않았다. REA MCP는 `binary_session`에서 `open:false`를 읽었으며 target을 열거나 분석 프로세스를 실행하지 않았다. 새 REA function Evidence ID는 없다. 아래 신규 짧은 원문을 이 문서 안에 보존한다.

### 기존 ATS 해석 정정

앞선 PET_WINDOW_EDIT/ATS/UI_OPEN 문서의 `A117D0` 해석은 이 설계에서 정정한다. `.pdata` 끝 `A117E5`만 읽으면 함수가 잘리지만, 실제 분기와 RET까지 해석하면 **표시상태를 반전해 v70에 쓰는 toggle**이다. ATS command2→v88을 상태 조회로 취급하거나 `A117D0`을 bool getter로 호출하면 안 된다. command0 show 설계에는 영향이 없다.

```text
A117D6 mov rdi,rcx             A117D9 mov rcx,[rcx+30]
A117E2 mov rax,[rdi]           A117EA mov rbx,[rax+70]
A117EE mov rax,[rcx]           A117F1 call [rax+150]
A117F7 test al,al              A117F9 mov rcx,rdi
A117FC sete dl                A117FF call rbx
A11806 add rsp,20             A1180A pop rdi; A1180B ret
8E6550 test edx,edx            8E6552 je 8E6571
8E6554 sub edx,1               8E6557 je 8E6568
8E6559 cmp edx,1               8E6561 jmp [rax+88] ; command2
8E656B xor edx,edx             8E656D jmp [rax+70] ; command1 hide
8E6574 mov dl,1                8E6576 jmp [rax+70] ; command0 show
```

## 3. 동료 instance 판별·UI thread·DLL 장착

### 판별 위치

**확인[정적]:** `4F14→54BDF0→54D660→A82980`에서 f2=1이면 PetLayout이다. property0의 **`A82C30(layout* RCX, uint64 UID RDX)`**가 `layout+B8`와 **`B92C0`의 Minion+198**에 같은 UID64를 저장한다. property1은 `A82DD0`으로 child를 전달한다. PetLayout f2=1·Minion UID·법사 sprite·이름 어느 하나도 동료 전용 식별자는 아니다. 다른 Player가 원 Pet 클릭 경로를 쓰는 조건도 이미 [Player 표시 조사](COMPANION_DISPLAY_EVIDENCE.md)에 있다.

**설계[LOCAL]:** 서버가 실제 소유 관계를 판정한 `runtime actor UID + actor generation/ref + owner + 영구 member character ID`의 현재 매핑을 기존 owned bridge 명령 payload로 공급한다. DLL은 `A82C30` 후 layout+B8와 매핑을 연결하고 **layout 주소와 해당 수명**에 `CompanionViewContext`를 붙인다. UID 숫자 대역만으로 판단하지 않는다. generation은 원 wire의 새 필드라고 주장하지 않으며 서버/브리지의 로컬 수명 정보다. 표시용 member ID를 명령 권한으로 신뢰하지 않고 서버가 f3의 현재 actor를 다시 자기 registry에서 해석한다.

일반 펫 UID로 전환되면 저장한 원 Text/visible/touch/geometry/행 순서를 복구하고 모든 원 invoke로 통과시킨다. 매핑이 아직 오지 않으면 동료라고 추측해 버튼을 바꾸지 않는다. 기존 4F14 child.f7 또는 출현 f65에 임의 표식을 끼워 넣지 않는다. 별도 일반 Player를 가방/동료로 오인하지 않는 것이 판별의 완료 조건이다.

### 장착 경로와 설치 방식

현재 `ui_open_bridge.hpp`는 `LC-Owned-UIOpen-v1`을 retained **owned WH_GETMESSAGE/UI thread**에서 처리한다. 기존 [auto_ok dispatcher](../ui-open-bridge/auto_ok.hpp)가 이 handler를 부모에 연결한다. Actor lookup ABI는 `627B0(ActorsSubsystem*, Pair16*out, uint64 fullUID)→out`, 펫 상태 요청은 `B8710(실제 Actor*)`다. 현재 명령에는 magic/stats toggle·pet request·unsupported hotbar만 있고 아래 후킹은 미구현이다.

후속 DLL은 이 loader/dispatcher·소유 Job·종료 경로를 재사용한 **별도 시험 후보**로 빌드한다. 이미 복원된 실행 후보의 base를 사용하고 실행 초기에 UI thread에서 기능을 설치한다. DllMain에서 UI/게임 객체 생성이나 긴 분석을 하지 않는다. 현재 핀 DLL을 덮어써 설치하지 않는다. 이번 문서는 빌드/장착하지 않는다.

추천은 기존 Detours 계열의 **함수 entry detour + trampoline**, 조건은 `captured layout의 CompanionViewContext`다. 원 callable의 MSVC `std::function` 객체/vtable을 DLL의 임의 객체로 바꾸지 않는다. 일반 instance는 원 trampoline으로 보낸다. 같은 entry에 이미 후킹이 있으면 기존 hook owner와 한 곳에서 합성한다. overwrite 바이트 수·trampoline 명령 재배치·현재 메모리의 해당 구간 상태는 **아직 미확인**이며 RVA만 보고 5/14바이트를 잘라 쓰지 않는다. 시작 때 선정 구간을 해석하고 기존 install/rollback 계약으로 적용한다. 요청마다 핀/해시/추가 guard를 넣지 않는다.

UI callback 안에서 서버 async handler를 직접 호출하거나 기다리지 않는다. UI→게임 요청은 기존 protobuf sender, 서버→UI의 소유 매핑/모델 반영은 기존 bridge command serial slot을 확장한다. 원 `busy/sequence`·current owner·FIRST/close를 재사용하고 새 포트·진행 폴링·중복 큐를 만들지 않는다. 현재 bridge parser는 **512B**이므로 registry 소형 payload와 별개로 ATS/가방 snapshot의 payload 전달 형식·상한은 후보 구현에서 명시적으로 확장해야 한다. 기존 코드가 이미 큰 모델을 전달한다고 주장하지 않는다.

## 4. 행 텍스트·숨김·재배치·상태 갱신 후킹

**확인[정적]:** `A81400`은 root=`layout+30` 아래 경로를 lookup한다. 원 명령9행은 모두 **Text 자체**이고 자식 label이 아니다. `A56810(out NodeRef*, rootRef*, native String32*)`→widget cast→Text+4F0에 `A5C1E0`으로 callable을 등록한다. callable+8은 captured layout이다(`pet-init.txt:325` 부근의 `A818E3`, :742 부근의 `A81F42`). 상태 Text는 `8F1BC0(out TextRef*, rootRef*, path String32*)→479670`으로 layout+C0..F8에 보관한다.

| 대상 | 정확 접점/ABI | DLL 적용 방식 |
|---|---|---|
| init/재생성 | `A81400(layout RCX, init-param EDX)` post-hook | 원 init 성공 후 named Text refs와 원 properties를 instance에 보관. 아직 UID가 없으면 외형 변경 대기 |
| 대상 전환 | `A82C30(layout RCX, UID64 RDX)` post-hook | 원 UID 저장 뒤 registry 연결·일반/동료 외형 적용 |
| 문자열 | `BF9ED0(Text* RCX, const MSVC String32* RDX)`; getter `BF9F90` | 동료 Text에 UTF-8 문구를 native String32 ABI로 전달. `char*`/`wchar_t*`를 직접 넘기지 않음 |
| 표시 | Text v148=`B58030(this,bool DL)`, v150=`B58020` getter | Rest/Dismiss/Name/Hunger false. 노드 삭제 없음 |
| 터치 | Text v530=`BF6030(this,bool DL)` | 숨긴 행 false, 보이는6행은 원 입력 성질 유지. 텍스트 공백만으로 입력을 막지 않음 |
| 위치 | Text v80=`B57E60(this,float XMM1,float XMM2)` | 리스트 배치 계약 아래 지정한 순서의 좌표 적용 |
| 크기 | Text v138=`BF5740(this,const Vec2* RDX)`, v140=`B580F0` | 원 행 폭/높이·긴 한국어 hit 영역 반영. 반환 bool/성공을 임의 가정하지 않음 |
| 리스트 refresh | ListView primary v650=`C09330(whole ListView* RCX)` | 행 높이 변경 뒤 원 다음 layout pass를 요청. `this+E20=1` |
| 상태 갱신 | `A82DD0(layout RCX,child RDX)` post-hook | 원 child 보관/전체 갱신 후 동료 라벨·상태·Hunger 숨김 재적용 |
| 퇴역 | `A81270` 실제 dtor, `A81230` deleting dtor | 해당 instance의 DLL ref/snapshot 퇴역. 원 dtor와 원 Text/child 정리는 실행 |

Text RTTI=`TD1686E38`, complete-object `COL136B3F0→vptr1240D70`를 확인했다. vtable slot은 **바이트 offset**이다. 신규 선택 원문: `B58038 [RCX+1F9]=DL`, `B57E7A/+7F`가 x/y를 `+3C/+40`에 저장, `BF57AE/+B8`가 크기 `+6C/+70`을 쓰고 `BF57F3/+FB`가 `+408/+404`를 갱신, `BF6053` 비교 뒤 `BF6067 [this+3EC]=DL` 및 입력 dispatcher 경로다. 필드를 직접 쓰는 대신 원 setter를 호출해 dirty/입력 후속을 유지한다.

### 6행 배치와 원 ListView refresh

보존 CSB의 authored 순서는 `MyPet→Targeting→AttackStance→DefendStance→Rest→Spread→Alert→Gather→Dismiss→Name→Blank_00→Status→Hunger→HP→MP→Level→Exp→Alignment`다. Spread/Alert/Gather를 새4/5/6행으로 쓰면 **보이는 명령끼리의 원 순서는 이미 목표와 같아 item reorder가 필요하지 않다.** 숨긴 Rest/Dismiss/Name/Hunger의 contentSize.height를0으로 접고 원 ListView refresh를 요청하는 것이 1차 구현이다. 원 크기는 일반 펫 복구 때 되돌린다. 이름·원 상태 receiver 노드를 삭제/reparent하지 않는다.

`BF9ED0`의 Text 갱신으로 크기가 다시 잡힐 수 있으므로 `A82DD0` 원 갱신 **뒤** 숨김·touch-off·height0를 재적용하고 refresh를 요청한다. init 한 번만 적용하는 구현으로 끝내지 않는다.

이번 후속 정적 읽기로 **ListView TD1686E90, complete COL136BC50→primary vptr1243828**과 refresh **v650=`C09330`**을 확보했다. 원 실제 layout pass **`C09340`의 this는 whole ListView+700 interface subobject**이며, 그 vptr1243FE0의 v20가 C09340이다. whole pointer로 C09340을 직접 호출하면 안 된다. DLL은 whole.v650으로 dirty를 요청하고 다음 원 layout pass에 맡긴다. 단순 setPosition을 계속 덮어쓰는 방식이 아니다.

```text
C09330 mov byte ptr [rcx+E20],1   C09337 ret ; whole this
C0934A cmp byte ptr [rcx+720],0  ; subobject this=whole+700
C093BA call [rax+788]            ; whole.v788=C08BE0, item layout param
C093DD call [rax+790]            ; whole.v790=C08A50, inner size
C093ED call [rax+648]            ; innerContainer 원 layout
C093FD mov byte ptr [rdi+720],0  ; dirty clear
C08A80 mov rdi,[rsi+DE0]         C08A87 mov rbx,[rsi+DD8] ; items
C08AC9 vmulss xmm2,xmm0,[rsi+DFC] ; (itemCount-1)*margin
C08AF6 call [rax+140]            ; 각 item contentSize
C08B68 vmulss xmm2,xmm0,[rsi+DFC] ; 반대 방향 분기도 margin 합산
C08B96 call [rax+140]
```

**조건부 경계:** `C08A50`는 숨김 여부만으로 item 수를 줄이지 않고 각 item 크기와 `(전체 itemCount-1)*margin` 및 padding을 합산한다. 따라서 height0이어도 margin이 양수면 빈 간격이 남는다. ctor `C08770`의 margin+DFC와 padding+E00/E04/E08/E0C는0 초기화지만 **실제 Pet CSB 적용 뒤 값0은 미확인**이다. 현재 owning ListView의 이5개 float를 읽는 것이 최소 다음 관측이며 이번에는 게임을 실행/읽지 않았다. 값0이면 위 크기0+refresh로 진행하고, 비0이면 원 margin setter/각 item spacing 조정 접점을 좁혀 동료 instance만 보완한다. 이 setter RVA와 authored ListView 전용 margin schema는 아직 UNKNOWN이다. 필요할 때만 원 root 아래 추가 Cocos container로 배치하는 대안을 쓴다. 현재 결과는 refresh 연결의 확인이며 실제6행·스크롤/hit 영역 성공은 UNRUN이다.

### 상태 줄·실제 성향

`A82DD0`는 child를 복사하여 `layout+100/+108`에 보관하므로 함수를 통째로 생략하면 안 된다(`pet-update.txt:75–129`). 원 갱신 후 **현재 상태 Text=C8, Hunger=D0, HP=D8, MP=E0, Level=E8, Exp=F0, Alignment=F8**을 동료 외형에 맞춘다. 상태 라벨은 서버의 실제 전투 태세와 이동 상태를 사용해 표시하고, 가방/설정 진입 때문에 원 상태 enum7/5를 echo하지 않는다. 필요하면 `상태: 공격 / 따라오기`처럼 두 축을 표시하는 LOCAL formatter를 쓴다.

성향은 **4F14.child.f9 signed i32**다. `A835CC mov ebx,[child+40]→A835D0 layout+F8`, label3550, `A83648→BF9ED0`으로 숫자가 들어간다. 초기 CSB text_id11512를 고치는 것으로 끝나지 않는다. label을 바꾸려면 post-update에서 해당 Text에만 쓴다. Hunger는 f8 생략/음수와 무관하게 위 표의 노드 숨김·입력·배치로 제거한다.

현재 `_companion_status_frame`은 f1..6·f10만 쓰며 **f9가 없다**(`world_feature_companion.py:735` 이후). `CompanionRecord`에도 lawful 필드가 없고 주인의 `_world_lawful`은 동료 값이 아니다. 실제 값의 원장은 동료 **영구 character ID의 progression.lawful** 또는 그 값에서 로드한 단일 동료 진행 모델이어야 한다([world_progress.py](../../../tools/local_original_session/world_progress.py):43,136). 저장·현재 동료 진행의 동기화 접점을 연결하고 status 생산자가 f9를 명시하도록 후속 국소 수정한다. 새 기능이 없을 때도 기존 서버는 동작하도록 optional data provider/기존 진행 Store API를 사용하고 다른 feature의 ctx 메서드를 직접 호출하지 않는다. 레거시 저장의0·fresh 기본500을 실제 읽기 없이 임의로 표시하지 않는다. 동료 값 로드/유지가 미결이면 **성향 실값 연결 UNKNOWN**으로 남기며 주인 수치를 대신 넣지 않는다.

## 5. 클릭·54C460·모달 우회

### 동료 전용 클릭 분기

invoke detour의 RCX callable에서 captured layout(+8)을 받아 scoped context를 찾는다. 일반 instance는 원 invoke에 그대로 보낸다. 동료 instance의 Spread/Alert/Gather에서는 **원 invoke를 호출하지 않고** 새 작업 한 번만 실행한다. 숨긴 Rest/Dismiss/Name 진입도 소비하여 원 팝업·요청이 생기지 않게 한다. mode2/3 및 Targeting은 원 입력 흐름을 보존한다.

`A84480→54C380→1689D0(command4)`는 대상 선택 대기이며 이때 즉시 mode1을 보내지 않는다. 다음 실제 actor 클릭의 `163F90`이 `4F02 f1=1, f2=[공격 대상 UID의 10진 문자열], f3=조종 동료UID low32`를 만든다. 취소는 명령 송신과 별도로 확인한다. f3를 적 UID로 바꾸거나 UI 클릭 순간 최종 행동을 선발송하지 않는다.

**`54C460(Minion* RCX,int mode EDX)`**의 원 생산은 `4F02{required closed-enum f1, repeated string f2=[], optional u32 f3=Minion+198 low32 present}`다. 이 entry detour는 현재 Minion UID에 결속된 동료 context에만 적용한다. 원2/3은 trampoline, 동료의 원 휴식4/산개7/경계5/수집6/해산8이 숨긴 이전 callback 등에서 들어오면 새 UI 동작과 중복 실행되지 않도록 그 요청만 소비한다. 원 전투 명령/목표 지정과 LOCAL 메시지의 producer는 구분한다. 전역 `27D620` 송신 hook으로 모든 펫 요청을 바꾸는 설계는 필요하지 않다.

### 해산·이름 창을 띄우지 않는 접점

| 접점 | 원 동작 | 동료 분기 |
|---|---|---|
| `A83D30` 클릭 | bank0 ID453/config2 확인 입력창 생성 | **생성 이전 entry에서 반환**, mode8 및 창 hide도 없음 |
| `A848E0` 확인 callback | mode8 송신 후 `560F0→3EF2A0(command1)`으로 PetLayout hide | 동료 origin callback은 소비. 가방 열기에 이 callback을 재사용하지 않음 |
| `A83B20` 클릭 | bank0 ID325/config0 이름 입력창 생성 | **생성 이전 entry에서 반환** |
| `A84680` submit | mode9·f2=[입력 이름]·현재 Minion f3 송신 | 동료 origin callback은 소비. 새 일반 버튼용 producer로 호출하지 않음 |

모달 생성 entry 후킹이 1차이며 submit 두 곳은 이미 예약된 callback의 동료 출처를 추적할 때만 처리하는 보완 접점이다. 현재 Minion 숫자만 보고 과거 팝업의 출처를 바꿔 해석하지 않는다. config2 `9B7E30`의 y/yes/ㅛ 검사나 공통 입력창 전체는 바꾸지 않아 일반 펫 확인/이름 입력이 유지된다. 실패/취소 시 다른 기능을 terminal로 만들지 않고 해당 동료 UI 요청의 미완으로 남긴다.

X=`A84550→captured layout.v70(false)`. `A10BB0`의 확인 prefix는 root.v148(false)와 layout+70=false이며 hide가 destroy/UID reset은 아니다. hide 때 DLL의 활성 편집/입력을 중단하고, dtor 때 참조를 퇴역한다. `A81270`은 child Pair와 C0..F8 Text intrusive refs를 정리하므로 원 소멸자를 유지한다.

## 6. LOCAL 요청과 서버 처리 순서

**설계[LOCAL], 공식 명령 확장으로 주장하지 않음:** 임의 enum10/11이나 미확인 opcode를 만들지 않고, DLL 전용 요청은 이미 유효한 **4F02 enum7**을 carrier로 사용한다. f2의 정확 marker와 operation으로 원 산개와 구분한다.

```text
C2S 4F02
  f1 = 7                                  # 원 enum 안의 carrier
  f2 = ["LOCAL_COMPANION_UI_V1", operation, args...]
  f3 = 현재 조종 동료 actor UID low32       # member character ID 아님

operation 후보:
  settings-load / settings-save / settings-reset
  bag-open-take / bag-open-give
  movement-follow / movement-hold
```

이 포맷은 **새 구현 계약**이며 원 `54C460`은 f2를 비우므로 marker를 생산하지 못한다. DLL에 원 protobuf 객체/serializer 및 `27D620`을 사용하는 **별도 producer**를 추가한다. 그 객체 constructor/field setter/수명 ABI는 아직 미확정이다. 기존 이름 submit의 문자열 저장/serializer 구조는 참고하되 이름 callback을 호출하여 우회하지 않는다. 먼저 local codec로 field/presence를 검증하고 실제 원 serializer ABI를 닫는다. 사용자 문자열을 실행 코드/서버 메서드명으로 사용하지 않는다.

새 optional `world_feature_companion_ui.py`는 고유 METHODS/FRAMES를 쓰고 **FEATURE_MODULES에서 `world_feature_pet`보다 먼저 한 줄 등록**한다. 현재는 pet가 첫 번째이고 companion이 후순위다([world_handlers.py](../../../tools/local_original_session/world_handlers.py):838,880). companion 앞에만 넣으면 pet가 먼저 소비할 수 있다. marker 없는 요청은 False로 넘기고, marker를 가진 요청은 이 모듈에서 처리/거절을 끝내어 원 Spread로 fallthrough하지 않는다. 일반 펫·소환수 요청에는 새 의미를 적용하지 않는다.

현재 companion parser는 body4096B/fields4/field2048B의 기존 한계를 갖는다(:775 부근). LOCAL 반복 f2를 그대로 그 handler에 흘리면 실패한다. 새 모듈이 marker만 먼저 분리하고 기존 원 요청의 검사를 약화하지 않는다. 큰 ATS 설정은 전체 원 CharacterConfig blob을 싣기보다 동료 탭의 typed 설정만 직렬화한다. 정확 payload 크기/행 정원은 서버·DLL 모델을 맞춰 정하며 원의 closed-enum 범위를 늘리지 않는다.

서버가 현재 writer/owner·해당 actorRef·동료 영구ID를 기존 소유 계약으로 resolve하고 기존 world runtime 직렬화/저장 API를 사용한다. `ctx._다른feature함수()` 호출이나 같은 METHODS 이름 덮어쓰기는 하지 않는다. 없는 optional 연결은 그 기능 요청만 미지원 처리한다. 모듈을 빼면 기존 서버·펫·상점/창고가 그대로 기동해야 한다([WORLD_FEATURE_GUIDE](WORLD_FEATURE_GUIDE.md)).

FOLLOW/HOLD는 절대값 요청으로 보내고 서버 응답의 상태를 표시한다. 빠른 중복 클릭에 blind toggle을 재실행하지 않는다. 기존 mode4는 **HOLD+PASSIVE**, mode1/2/3은 FOLLOW로 바꾸므로(:866) 이를 따라오기/대기의 구현으로 호출하지 않는다. 새 이동 요청은 combat_mode를 유지하고 기존 `set_commands`/AI deadline 정리 API를 사용한다. 기존 mode2/3의 실제 이동 변화는 원 현재 서버 동작으로 보존하고 UI에 표시한다.

S2C 상태는 원 **4F14**를 유지한다: outer required f1=actorUID/f2=1/f3=child, child required f1..6, optional f7..10. f9=실제 성향, f10=double 경험치 백분율. 설정/가방/이동의 LOCAL 결과·모델은 기존 bridge 명령의 payload로 UI thread에 반영한다. **이 역방향 model 게시와 기존 bridge serial slot의 연결은 새 구현 항목**이며 현재 broker가 이미 지원한다는 뜻이 아니다. startup에서 optional publisher를 연결하고 같은 기존 command owner가 맡도록 하며 common core/broker의 새 필수 호출로 만들지 않는다. 매핑 게시→UI 적용 완료→해당4F14 표시의 순서를 후보 시나리오에서 맞춘다.

## 7. ATS 창의 동료 탭

### 원 창을 얻고 표시하는 경로

**확인[정적]:** `ATSLayout` base vptr120F308, PC primary vptr1210E88, factory `8FCFE0`, init `8FBFE0`, base ctor `8E3E60`/init `8E5F40`. 이번에 좁힌 owning 경로는 **`560F0(out manager Pair)→15AE90(manager,command,&any64)`**다. manager의 public cache를 조회하거나 `15B850→B38B00`으로 만들고 RTTI cast/strong Pair를 보유하여 실제 layout.v98을 호출한 뒤 정리한다. command0을 전달하면 show다. `15D660()`은 같은 경로에 command2를 넣는 원 ATS whole **toggle** shortcut이다. 동료 설정은 이미 열린 창을 닫지 않도록 show0을 쓴다.

원 show v70=`8E6A80`은 `644B0→42BAA0/42BD30`, ATS의 PC draft/cache·`8EC100/8ED160/8EEF00` population과 원 탭 선택을 사용한다. **현재 PC ATSSubsystem을 동료 값으로 잠깐 덮어쓴 뒤 show하는 방법은 채택하지 않는다.** raw factory 직접 호출로 원 manager의 cache/Pair 수명을 건너뛰지도 않는다.

새 owning 경로의 선택 원문은 다음과 같다. 기존 `run380_map_transition_receive/f2_research.py`의 읽기 전용 View와 carrier를 사용했다. 반환/정리는 원 함수를 유지하고 empty any64는 원 caller처럼 64B zero/type tag 정리 계약을 따른다. 아래 RIP-relative LEA의 `[주소]`는 해석된 목적지의 요약 표기다.

```text
253D7 lea rcx,[12110C8]        ; factory callable vptr, invoke8FCFE0
253E3 mov dword [rsp+68],4     ; capture
253FC call 59C70              ; ATSLayout registry 등록
15AEA7 mov r13,r8             15AEAA mov r12d,edx
15AEAD mov r15,rcx            15AFDE call FA1AD3 ; RTTI cast
15AFF4 lock inc dword [rax+8] ; strong retain
15B01E mov rcx,r15            15B021 call 15B850 ; cache miss
15B07B mov r8,r13             15B07E mov edx,r12d
15B081 mov rcx,r14            15B084 call [rax+98]
15B850 ...                    ; RCX=manager,RDX=Pair*out
15B8B2 lea r8,[rsp+48]        ; ATSLayout String32
15B8BC call B38B00            15B8DB call FA1AD3
15B8E9 mov [rdi],rax          15B8F0 mov [rdi+8],rax ; control 재로드 뒤
15B985 mov rax,rdi            15B9A6 ret
15D66F call 560F0             15D675 mov rcx,[rax]
15D688 lea r8,[rsp+30]        15D68D mov edx,2
15D695 call 15AE90            15D70E ret ; any/Pair 정리 포함
```

### 동료 탭의 추가 코드

DLL이 원 ATS root의 Tab 옆에 **`Bt_Companion`과 별도 `Panel_Companion`**을 생성한다. 원 Buff/Combat/Option/Help와 스킨/레이아웃 구성요소를 재사용하고, DLL의 `CompanionSettingsViewModel(memberCharacterID,actorRef,settings,learnedSpells,bagSnapshot)`을 붙인다. native `ATS+284`의 탭 index에 임의4를 쓰지 않고 DLL 자체 active-view로 선택한다. 원 show가 끝난 뒤 companion panel을 선택하여 PC panel을 일시 숨기고, PC 탭으로 돌아가면 원 panel/input을 복구한다.

동료 패널의 아이템/마법 선택기는 **동료의 실제 학습 목록과 가방 snapshot**에서 만든다. 현재 PC 마법창/인벤토리 drag source를 그대로 법사의 것으로 취급하지 않는다. 원 slot 컴포넌트의 view/skin은 재사용할 수 있지만 payload의 memberID/itemUID/spellID 귀속은 동료 모델에서 결정한다. 원 도움말의 회복 칸은 아이템용이다. 주인 HP 기준 Heal 같은 추가 정책은 LOCAL 동료 옵션으로 명시하며 원 슬롯이 이를 원래 허용한다고 주장하지 않는다.

| 동료 탭 작업 | 원 접점 | 동료에서의 분기/서버 계약 |
|---|---|---|
| 표시/탭 선택 | `15AE90` show0, `8E6A80` show, 원 탭 전환 `8E78A0` | 원 show 뒤 DLL 동료 panel 활성화. 원 PC model 유지 |
| Save | 원 invoke **`8F6450..8F769C`**, delegate `8F7569→436900` | 동료 tab이면 DLL draft를 settings-save로 보냄. 원 Save 호출/PC 설정 오염 없음 |
| Reset | 원 Reset 버튼의 실제 callback ABI는 후속 확인 | 동료 draft/서버 동료 설정만 초기화. PC 원 Reset은 실행하지 않음 |
| Play | 원 invoke `8F6390→644B0→42AC10`, 원 C2S4F36/4F38 | 동료 탭에서는 원 PC ATS 시작/종료를 호출하지 않음. 필요 동료 support 설정은 별도 LOCAL model |
| 원 PC 탭 Save | Config `104EA0..10530E→4ED6` | 원 기능 그대로. 동료 탭의 Save와 분리 |

원 **4ED6**은 f1=CharacterConfig/f2=ATSConfig의 wire2 blob이며 타캐릭터ID 필드가 없다. **4ED7**도 PC 설정 수신이다. 기사 접속 중 이를 동료 설정 저장/로드로 전용하지 않는다. 원 ATS4F36/4F38과 ACK4F37/4F39, 시간4F45..47을 동료용으로 가짜 성공시키지 않는다. 동료 설정 저장은 영구 memberID에 귀속된 LOCAL typed 설정을 기존 저장 경계 아래에 두고 현재 CompanionRecord의 movement/combat/support_enabled/mp_reserve/learned_spells 등과 일치시킨다. 설정 Load→편집→Save 성공→닫기→다시 열기→재접속 복원까지 연결해야 완결이다.

**UNKNOWN:** 신규 Tab/Panel node 생성·button 등록 ABI, 원 Reset callback, 동료 source picker의 payload/실제 drop 소비, PC↔동료 탭 전환 후 초점/drag 복구. 원 클래스와 owning show 경로를 찾은 것은 이 UI 추가 코드가 이미 구현됐다는 뜻이 아니다.

## 8. 동료 가방 A안 — 원 창고 UI 재사용(우선)

하나의 원 StorageLayout을 동료 가방 view로 쓰고 **꺼내기/주기 두 버튼 또는 탭**을 DLL이 연결한다. 동료 context 동안 제목을 `동료 가방 — <이름>`으로 바꾸며 개인/혈맹창고 문구·수수료를 동료 거래에 적용하지 않는다. 일반 창고 context로 돌아가면 원 제목과 동작을 복구한다. 원 wire에는 동료ID가 없으므로 **서버가 발급한 context의 scope가 동료를 가리키는 LOCAL 확장**이다.

### 원 owning UI/모델 접점

**`3F0C20(current manager RCX,command EDX,borrowed any R8)`**는 key `StorageLayout`(문자열 RVA11B5D30)으로 **NPCStorageLayout TD16888E8**의 owning Pair를 얻어 실제 v98로 보낸다. primary vptr **1234CF8**, v98=`B1A440`, vA0=`B1A470`, v70=`B19340`. offsetB8의 secondary vptr1234CC8과 혼동하지 않는다. command0은 v70(true), command1은 v70(false), command2는 v88로 간다. 이번 primary vtable+88을 직접 읽어 **A117D0** 연결도 확인했으므로 command2는 toggle이다.

**`5C24D0`**는 같은 owning layout에 `NPCStorageCommand TD1697130` typed any를 만들어 vA0로 보낸다. 정상 COUNT의 `5C0133`, LIST의 `5C065D`는 `3F0C20 command0`을 요청하고 이후 `5C24D0`으로 COUNT command1/LIST command2 및 command4를 전달한다. 따라서 직접 show만 호출하는 것보다 **실제 S2C 모델 수신→원 subscriber→표시**를 기본 경로로 쓴다.

```text
3F0C32 mov r13,r8             3F0C35 mov r12d,edx
3F0C38 mov r14,rcx            3F0D72 call FA1AD3 ; NPCStorageLayout cast
3F0D88 lock inc dword [rax+8] 3F0DB5 call 3F2C50 ; miss get/create
3F0E0F mov r8,r13             3F0E12 mov edx,r12d
3F0E15 mov rcx,r14            3F0E18 call [rax+98]
5C24E9 mov r13,r8             5C24EC mov r12d,edx
5C26E7 mov [rsp+70],r12d      5C26EC lea rcx,[1697130]
5C26F3 mov [rsp+A8],rcx       5C26FE lea rdx,[rsp+70]
5C2709 call [rax+A0]          ; typed NPCStorageCommand
```

위 LEA 목적지도 해석된 RVA의 요약 표기다. 정상 모델 쪽 기존 원문은 `run394_warehouse_ui/storage_handlers.json:1114,1230,1346,2625,2765,2897`에 있다. UISubsystem show command와 typed NPCStorageCommand의 command 번호는 별개다.

| 작업 | 방향/opcode·필드 | 원 소비/후킹 |
|---|---|---|
| 주기 목록 | S2C **4ED2 COUNT**: required f1:u32/f2:enum/f3:u32, optional f4:u32 context | `5BFD20`이 `54DE50`의 현재 PC 보유품을 필터하여 A 모델, StorageSubsystem+28에 설치. A는 서버가 동료 아이템을 넣는 목록이 아님 |
| 꺼내기 목록 | S2C **0971 LIST**: required f1..6, repeated f7 `{entrykey:u32,full ItemInfo}`, optional f8:bool | `5C0470→5BE550/5BE630`→B 모델(+38). f8=true의 표시 분기. f1=context, f3=nativekind |
| 선택·수량 확정 | C2S **4ED1** required f1=context/f2=mode, repeated f3 `{f1:key,f2:u64 quantity}`, optional f4/f5 normal **present0/0** | `B1CCD0`가 선택행에서 실제 key/Q를 읽음. mode와 key domain은 아래 표 |
| 닫기 | C2S **097B**; normal body0B, schema는 optional enumf1 | `B1CCD0` 송신 직후 `5C1860→5C1790` detach/정리·097B. 성공 ACK 아님 |

원 A/B nativekind와 mode 매핑은 다음과 같다. **kind1/2/3의 공식 개인/혈맹/요정 이름은 미확정**이다. 동료 scope는 kind 숫자에서 추정하지 않고 issued context에 둔다.

| 모델 | kind | 4ED1.f2 | 선택 key의 원 domain |
|---|---|---|---|
| A=COUNT | 1 또는3 | 1 | 현재 PC inventory lookup key(selected+28) |
| A=COUNT | 2 | 3 | 같은 PC key |
| B=LIST | 1 또는3 | 2 | 서버가 발급한 warehouse entrykey(selected+1C) |
| B=LIST | 2 | 4 | 같은 entrykey |

### 실제 꺼내기/주기 흐름

1. **꺼내기:** Alert의 동료 클릭→LOCAL bag-open-take(f3=동료actorUID)→서버가 현재 owner/member의 bag·장비를 읽어 context와 opaque entrykey→실제 동료 itemUID 매핑을 발급→0971 full ItemInfo 목록→원 B view→사용자 행/수량→원4ED1(mode2 또는4, issued key/Q)→서버가 해당 동료에서 주인으로 실제 이동/저장→주인 Inventory 결과. 4ED1 wire에 memberID를 임의 추가하지 않는다.
2. **주기:** DLL의 주기 탭→LOCAL bag-open-give→동료 scope의 context를 가진4ED2→원 A view의 **주인 보유품** 선택→원4ED1(mode1 또는3, PC key/Q)→서버가 주인→해당 동료로 실제 이동/저장. 기존 NPC 메뉴/창고 context를 위조하지 않는다.
3. 원 confirm은 서버 결과 전에 닫히고097B를 보낸다. 서버는 **4ED1의 이미 수락된 commit을097B로 취소하지 않는다.** 실패/부분 commit/닫기 수명을 기존 저장 owner 아래 기록한다. UI를 다시 보여야 하면 완료 결과 뒤 새 context/모델을 정당 발급한다. 자동 재전송/거래 replay는 하지 않는다.

서버의 issued context에는 기존 거래 수명 형식으로 `ownerRef/memberCharacterID/actorRef/방향/양쪽 실제 bag snapshot와 row mapping`을 결속한다. 새로운 일반 검증 체계를 만들지 않고 기존 owner/current/CAS·row 소비를 이 scope에 적용한다. marker 없는 개인/혈맹창고 context는 기존 handler로 통과시킨다. **0973 INFO는 A 목록도 거래 성공 ACK도 아니며, 4F09는 펫 맡기기/찾기이므로 아이템 가방에 쓰지 않는다.**

COUNT f1/f3 및 LIST f2/f4/f5/f6의 업무 이름/정상 초기값은 아직 UNKNOWN이다. 숫자들을 슬롯수/수수료라고 임의 명명하거나0으로 채워 완성 패킷이라 하지 않는다. 구현 시 현재 원 producer 계약에서 실제 소비하는 값을 확보해 LOCAL 의미를 명시하고, kind1 등 UI 후보 사용도 공식 개인창고 enum의 확정과 구분한다. 양방향 UI의 item filtering·장착 표식·무게·수량상한·제목 lookup은 후속 원본 화면 검증 항목이다.

## 9. 동료 가방 B안 — 원 인벤토리 UI를 동료 view로 재사용

창고안과 별개의 유효한 구현 경로다. **현재 PC 인벤토리의 전역 모델을 동료 데이터로 바꿔치기하지 않고**, 원 inventory 레이아웃/SlotNode·아이콘·수량 표시를 별도 동료 owning view로 재사용한다. 원 생성자가 현재 PC subscriber를 자동 등록한다면 생성 후 덮어쓰는 대신 그 adapter 생성/바인딩 경계에서 view별 모델을 넣는다. PC 인벤토리와 동시에 열어도 UID·장비·드래그가 섞이지 않아야 한다.

| 확보한 접점 | 원 현재 PC 연결 | 동료 view에서 필요한 hook/추가 코드 |
|---|---|---|
| `15EDF0`/`15ECF0→159A20` | 원 PC 가방 shortcut/dispatcher. actor/member 인수 없음. shortcut은 command2 toggle | 원 창을 toggle하는 것으로 끝내지 않고 동료 view를 owning manager/별도 cache key 아래 관리. common dispatcher의 command0은 show |
| InventoryAdapter `A060B0→A00850` | `77340`의 현재 Inventory+3D8/+3E0 rows를 읽음 | companion view context일 때 서버가 보낸 해당 member rows로 adapter population 분기 |
| row `B03780` | itemUID 등의 slot metadata 구성 | 원 ItemInfo 메타데이터 보존, 동료 view에만 귀속된 row 모델과 UID domain |
| `C05A40→9FFD80→B042D0` | adapter의 row를 SlotNode+808/+810 metadata owning Pair로 게시. model+0=UID, +C0=index | 별도 slot event/drop/수량 선택이 같은 동료 view를 가리키도록 유지 |
| 사용 `A0BF80→95C4C0` 등록→`953890→A0C0B0` | callback의 **RDX는 `&Node*` cell**, model+B0==2이면 `77340→4FD260`으로 현재 PC item use | 동료 view에서는 PC UseItem 호출을 소비하고 꺼내기/LOCAL 장착 등 명시 작업으로 연결. PC 슬롯 원 동작 유지 |
| 원 drag `A0ADB0→627B0→586E0→B7690→3D0F0` | 실제 targetActor와 현재 PC item/Q로 GIVE | source bag이 동료인 view에서는 그대로 호출하지 않고 동료 row 거래로 분리 |

원 InventoryLayoutPCImpl은 **TD1771848 / primary vptr12228D8 / COL1349C80**, v98=`A11810`, v70=`A096C0`, v88=`A117D0`이다. adapter vptr1221E28은 InventoryAdapter다. source 근거는 [REA61 population](../../local_server_rea_20261016/run61_useitem_model_population/worker/findings.md):16–69, [REA63 use dispatcher](../../local_server_rea_20261016/run63_useitem_ui_dispatcher/open-worker/findings.md):15–58, [REA48 row caller](../../local_server_rea_20261016/run48_inventory_slot_caller/findings.md):9–15와 [REA55 PC receiver](../../local_server_rea_20261016/run55_current_pc_receiver/findings.md):9–34다.

이 안은 동료 슬롯→주인으로 **꺼내기**, 주인 슬롯→선택 동료로 **주기**를 DLL이 명시된 수량 선택과 연결한다. 주기에는 원 **4EF5 GIVE** 경로를 재사용할 수 있다. 기존 `world_feature_trade.py`가 실제 4EF5를 동료 소유 분기에서 처리하고 `CompanionInventory.give`로 양쪽 저장/CAS·자동장착을 연결한다. **반대 꺼내기는 현재 구현에 없다.** 동료가 PC처럼 임의4EF5를 보내게 하거나 source UID를 주인 UID로 위조하지 않고 LOCAL 요청/issued 동료 row mapping으로 서버가 source bag을 결정한다.

원 **4EF5**는 required `f1:u32 targetActorUID, f2:u32 PCitemUID, f3:u64 quantity`(wire0, mask7)다. **`3D0F0(RCX=target,RDX=item,R8=Q)→3D661/3D676/3D665` field 저장→`3D6A4→27D620`**이며, source 캐릭터를 wire로 지정하는 필드는 없다([REA406 trade](../../local_server_rea_20261016/run406_companion_equipment/trade/findings.md):16–30,44–56). 원 target/local actor·action·거리 조건을 보존한다. 4ED1 normal 수량은1..2,147,483,647의 원 positive signed32 선택값을 u64로 보내지만, 이를4EF5의 wire64 전체에 같은 원본 상한이라고 옮기지 않는다.

가방 창의 버튼/선택 후 소비는 A안의4ED1 context 거래 코어를 공통으로 써도 된다. 그러면 inventory view는 같은 issued rows를 다른 UI로 보여 주고 동일 source/destination commit을 사용한다. 별도 가방 원장이나 두 번째 저장 포맷은 만들지 않는다. 새 UID 추가/합침·장비 해제·중량·자동착용의 현재 정책을 동일 거래 서비스에 모은다. `A00850`/slot callbacks의 전체 ABI·별도 inventory view factory/manager key·drag/drop source와 꺼내기 수량 popup 접점은 **아직 미확정**이다. 이미 확보한 원 PC shortcut을 동료 가방 open API라고 부르지 않는다.

## 10. 아이템 이동·소비·저장·클라이언트 갱신

실제 가방 데이터는 [CompanionInventory](../../../tools/local_original_session/world_feature_trade.py)의 member별 `frames/states`와 기존 PC InventoryStore/EquipmentStore를 쓴다. 같은 캐릭터가 다시 직접 접속했을 때도 같은 아이템/장비여야 한다. CompanionRecord.equipment에 별도 items 사본을 넣지 않는다. 기존 GIVE의 `companion-transfer.json` intent와 기존 warehouse atomic writer의 **앞으로 복구**를 재사용/확장하며 실패한 debit/credit을 rollback·재소비로 숨기지 않는다. 현재 기성 구현은 **durable intent + debit-before-credit의 두 CAS**이며 두 캐릭터를 동시에 한 CAS로 바꾸는 구현이 아니다. AI의 물약 소비도 같은 bag을 쓰므로 열린 목록의 과거 수량을 확정값으로 삼지 않는다.

꺼내기에서는 source=member, destination=owner인 역방향 실제 거래를 추가한다. source의 장착 아이템은 현재 public equipment/transfer API로 먼저 정당 해제하거나 해당 요청을 거절하는 명시 LOCAL 정책을 택한다. 초기 구현은 장착품 꺼내기 거절, 동료 view의 별도 해제 후 꺼내기를 추천한다. 주기 후 자동착용은 현재 기성 정책을 재사용한다. 메타데이터 전체가 같은 stack만 합치고, 다른 강화/속성/UID provenance를 지키며, 양쪽 bag 변경과 장비 anchor·중량·현재 actor appearance 갱신까지 기존 commit 소유자가 맡는다. 이 정책을 원본 공식 펫 경제 규칙이라고 부르지 않는다.

| 결과 통지 | 사용 범위 |
|---|---|
| S2C **0965** `f1:[ItemInfo{f1=UID,f4=newQ}]` | 주인의 이미 존재하는 UID 수량 변경. 없는 UID를 만드는 용도로 쓰지 않음 |
| S2C **0964** full ItemInfo | 주인의 새 UID 추가. 원 필수/미확인 ItemInfo 메타데이터 보존 |
| S2C **0978** f1=UID | 주인 인벤토리 행 제거. UPDATE0과 구분 |
| 동료 목록/모델 | A안은 새0971/4ED2 current 모델, B안은 companion snapshot을 해당 view adapter에 전달 |
| 장비/태세 | 기존 장비 저장·refresh·원 appearance 통지 경로 재사용. 동료 item을 자기 PC0964로 넣어 가짜 공유 가방을 만들지 않음 |

공식 창고 후속 통지 순서는 UNKNOWN이다. 위는 현재 LOCAL 거래 결과 projection이며, 기존 SHOP PASS를 동료 가방 UI/꺼내기 PASS로 옮기지 않는다. 4ED1 전송 반환·097B 닫기·서버 응답·양쪽 저장·원본 화면·fresh restore를 각각 판정한다.

## 11. 후킹 목록과 구현 단위

| 단계 | DLL 범위 | 서버 범위 | 완료 판단 |
|---|---|---|---|
| 1. instance·행 | A81400/A82C30/A82DD0 post, Text 크기0/숨김, ListView.v650 C09330 refresh, callable origin, dtor 퇴역. 실제 margin 확인 | 현재 동료 mapping과 실제 lawful의 읽기 원장 연결 | 일반/동료 전환을 구분하며6행·Hunger 숨김이 갱신 후에도 유지 |
| 2. 클릭·모달 | A84100/A84020/A83F40 분기, A83D30/A83B20 생성 전 우회, 필요 A848E0/A84680 출처 처리,54C460 scoped hook | marker 전용 optional feature·동료 상태/이동 처리 | 중복 mode/popup/해산/hide 없음, 목표 지정·원 태세 유지 |
| 3. ATS | 560F0→15AE90 show0, 별도 동료 Tab/Panel·source picker·Save 분기 | 영구 member 설정 load/save/reset·응답 snapshot | 기사 설정 불변, 해당 법사 설정만 저장/복원 |
| 4A. 창고 가방 | 원4ED2/0971 subscriber→StorageLayout·동료 제목/방향 UI | issued context/rows,4ED1/097B scoped 처리·양방향 거래 | 목록→행/수량→commit→양쪽 실제 저장→재접속 일치 |
| 4B. 인벤 가방 대안 | A00850/B03780/SlotNode/Use·drag 분리·별도 owning view | 같은 거래 서비스/실제 bag,4EF5 주기 재사용 | PC bag/use 오염 없음, 동료 rows의 양방향 이동 |
| 5. 수명·통합 | 숨김/일반 Pet 복구·ATS PC 탭 복구·despawn/logout/재소환·원 hook detach | current context 퇴역·실패 intent 보존/정당 복구 | stale callback/UID 재결속 없음, 원 finally/FIRSTclose |

이번 산출물은 **설계 단계까지**다. 4B를 선행 구현할 필요는 없으며4A를 먼저 끝내면 사용자 가방 기능을 충족할 수 있다. 각 후속 worker는 해당 단계의 소유 파일과 한 번의 실행을 따로 지정받는다. 이번에는 기존 feature/공유 core/핀 파일의 국소 패치조차 하지 않았다.

## 12. 위험·검증 방법·남은 UNKNOWN

| 위험 | 구현 시 확인/검증 방법 |
|---|---|
| 전역 hook가 일반 펫·소환수 변경 | 동료/일반 펫/소환수 세 instance를 차례로 열어 명령9행·모달·4F02를 대조. 같은 instance의 대상 전환 복구 포함 |
| 자동배치가6행을 덮거나 숨긴 입력이 살아 있음 | C09330 refresh와 실제 margin을 확인한 뒤 scroll·resize·재생성·4F14 반복 갱신의 화면과 hit 영역 확인. 숨긴 위치에서 명령/모달0 |
| ABI/수명 오류 | 정확 this/Pair16·intrusive TextRef·String32·any64를 구분, 원 callback 진입/종료·dtor/재진입 확인. 참조를 파괴 뒤 해제하거나 원 노드를 삭제하지 않음 |
| 설정이 기사 PC에 저장됨 | companion Save 때 PC4ED6/PC ATS 시작 패킷이 안 나오는지, 기사와 법사의 실제 저장 전후·Load·재접속 비교 |
| 가방이 UI에만 보이고 이동하지 않음 | 실제 양쪽 UID/Q·장비·중량·CAS·파일·fresh restore 대조. 목록/확정/닫기만으로 성공 판정하지 않음 |
| 097B가 commit 수명과 충돌 | 정상 confirm 직후close·수동X·취소·중복close·부분 저장 실패를 분리. 이미 시작된 거래의 원오류/intent 보존 |
| 동료 제거/재소환 뒤 이전 view 사용 | actorRef 세대 전환·map departure·사망·logout의 원 정리를 따라 callback/모델 퇴역. 같은 숫자 UID라도 과거 view 재사용 금지 |
| 파생 carrier의 주소가 실행 후보와 다름 | 후속 후보의 선택 함수/원 loaded mapping에서 시작 시 주소·ABI를 확인. 광범위 재해시·요청 중 검사 추가는 하지 않음 |

**향후 실행 단계의 원본 검증**은 기존 owned non-input desktop/Job와 원 `OriginalScreenshot`의 파일 PNG를 써도 된다. 별도 실행 승인이 있는 시험 worker 하나만 게임/서버/포트·시험 저장 사본을 소유하고, 앞 상태/응답 뒤 다음 행동을 수행한다. 사용자 포커스·커서·전역 입력에는 간섭하지 않는다. 원본 화면 캡처 허용을 이번 실행 지시로 해석하지 않았으며 **이번 캡처는0**이다.

최소 실제 순서는 정상 로그인→캐릭터 선택→월드→동료 클릭→같은UID4F13/4F14→6행 스크린샷→목표 지정/적 클릭·공격2·방어3→설정 동료 탭/Save·재열기→가방 꺼내기/주기 실제 수량→FOLLOW/HOLD 양쪽→동료 창 닫기/재열기→일반 펫·소환수 대조→재소환/재접속 복원→원 Quit/FIRSTclose다. 패킷 봇은 서버 거래/저장 범위, native callback 호출은 개발 접점, 헤드리스 PNG는 원 UI 외형 범위로 각각 구분한다. 실제 원 입력의 caller→producer 확인 없이 callback 반환을 클릭 PASS로 확대하지 않는다.

남은 **구현 전 UNKNOWN**은 (1) 실제 ListView margin/padding과 비0일 때의 setter 또는 추가 container API, (2) detour overwrite/trampoline 범위와 현재 loaded 코드, (3) LOCAL4F02 문자열 producer의 정확 protobuf C++ ABI, (4) 기존 bridge slot의 optional model publisher·큰 payload 연결, (5) ATS 새 node/동료 source picker·Reset callback, (6) COUNT/LIST의 미명명 scalar를 채우는 실제 producer 값, (7) 독립 inventory view/drag/수량 callback ABI, (8) 동료 lawful의 단일 현재 진행 원장 연결이다. 각 항목은 위 단계의 해당 consumer 한 접점으로 좁혀 확인한다. 추가 UI 코드로 실현할 경로와 확인할 입력을 남겼으며 전체 UI 복원을 선행조건으로 삼지 않는다.

이번 검증은 기존 원문 대조·선정 carrier 정적 decode와 문서 UTF-8/로컬 링크/내용 검토다. `python -X utf8 -B -`의 일회성 읽기 확인에서 UTF-8 decode 성공·대체문자0·로컬 링크28개 전부 존재·행 끝 공백0이었다. 같은 명령 방식으로 A117D0/8E6550/15D660, Text visibility/position, ListView C09330/C09340/C08A50 및 ATS/Storage dispatcher 인수, primary/subobject vtable의 실제 slot을 읽어 신규 결론을 대조했다. 원본 함수는 호출하지 않았다. `git diff --check -- <이 문서>`는 exit0이나 `git check-ignore`가 이 work 문서를 표시하므로 본문 검증은 위 직접 읽기 결과로 판단한다.

제품 단위시험·컴파일·주입·게임 화면·클릭·서버 거래·저장은 **UNRUN**이다. 기존 dirty 변경은 이 문서의 변경으로 포함하지 않으며 커밋하지 않았다.
