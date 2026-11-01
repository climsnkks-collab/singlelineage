# 동료 법사 PetStatusLayout 편집 가능성

2026-10-27 조사 착수 / 2026-10-28 문서 마감 · **조사·문서만. 게임·서버·포트·원 함수 실행·화면 캡처·패킷 송신·커밋 없음. 코드·리소스·저장·프로필·ACTIVE_TASK는 수정하지 않았다.** 이번 직접 요청의 조사 범위만 수행했으며 제품 중지와 기능 동결은 유지한다.

## 결론

**기존 행의 문구·배치와 클릭 기능을 바꿔 쓰는 것은 조건부 가능하다.** 다만 `work/local_resource_provider/assets/data/string.csv` 하나를 고치면 자동 반영되는 구조는 아니다. 추출 파일→실행 클론의 raw 파일→클라이언트 로더라는 별도 공급 단계가 있고, 기존 배치 도구는 원문과 다른 파일을 거부한다. 동료만 바꾸려면 전역 문자열 교체보다 **현재 동료의 PetStatusLayout instance에 한정한 문구·callback 변경**이 적합하다.

**서버만으로 가능한 것은 이미 도착하는 요청을 다른 LOCAL 행동으로 해석하는 범위다.** 해산 확인창, 이름 입력창, 목표 선택 대기와 로컬 닫기는 서버 처리 전에 클라이언트가 수행하므로 서버에서 제거할 수 없다. ATS/동료 가방 열기는 목적창의 모델·현재 대상·저장 소비까지 연결해야 한다. 기존 `ui_open_bridge.hpp`는 그 클릭 hook과 목적창 명령을 아직 제공하지 않는다.

| 요청 항목 | 판정 | 실제 변경 후보·조건 |
|---|---|---|
| 명령 문구 교체 | 조건부 가능 | 실행 클론의 `data/string.csv` 또는 동료 instance의 Text 값. ID 공유와 번역·캐시 주의 |
| 기존 항목 순서·간격 변경 | 조건부 가능 | `Pet/PetLayout.csb`의 기존 노드 이름을 유지해 재배치. 실행용 raw 공급·재생성 필요 |
| 항목 숨김·감소 | 조건부 가능 | 해당 노드의 visibility/입력/리스트 간격을 함께 처리. 텍스트만 공백으로 만드는 것은 숨김이 아님 |
| 새 항목 추가 | CSB만으로 기능 추가 불가 | 노드 추가와 별개로 native callback·대상/수명·서버 행동을 연결해야 함 |
| 배고픔·성향치 의미 교체 | 조건부 가능 | 실제 갱신 라벨·formatter·`4F14` 필드 소비를 함께 변경. initial CSB text_id만 바꾸면 갱신 때 덮임 |
| 서버에서 mode5/7 재해석 | 조건부 가능 | 동료 전용 LOCAL 분기. 일반 펫·소환수의 기존 명령 의미 보존 |
| 해산8·이름9를 서버만으로 일반 버튼화 | 불가 | 클라이언트 확인/입력 절차가 먼저 발생. callback 단계 변경 필요 |
| Pet 클릭→ATS/동료 가방 | 설계 가능·현재 미구현 | 현재 instance callback과 목적창 owning model/API 연결. 창 표시만으로 동료 설정/가방 완결 아님 |

## 기준·근거와 신뢰 범위

고정 기준은 LC **26.09.29.2001**, CONTROL SHA256 `9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`다. 기존 [TARGET_IDENTITY](../../local_server_rea_20261016/TARGET_IDENTITY.md)와 복원 metadata의 신원을 승계한다. 주소는 **RVA**, preferred VA=`0x140000000+RVA`이며 현재 프로세스 주소가 아니다. 파생 정적 carrier는 `work/rea_lineage_resume_20261013/main-gameplay/audit/metadata-v2/DERIVED_RESTORED_ANALYSIS_ONLY.exe`다. 이 파일을 실행하지 않았다.

주요 재사용 근거는 [PET_EVIDENCE](PET_EVIDENCE.md), [COMPANION_EQUIPMENT_EVIDENCE](COMPANION_EQUIPMENT_EVIDENCE.md), [UI_OPEN_EVIDENCE](UI_OPEN_EVIDENCE.md), `work/local_server_rea_20261016/run279_summon_layout_child_commands/`, `run396_pet_control/`, 목표 지정 후속 `run400_pet_command_target/`다. 이후 추가된 [ATS_COMPANION_EVIDENCE](ATS_COMPANION_EVIDENCE.md)와 [WAREHOUSE_EVIDENCE](WAREHOUSE_EVIDENCE.md)도 재사용한다.

**확인[정적]**은 원문·파일·디스어셈블리의 연결이고, **조건부/제안**은 그 근거에 따른 구현 설계다. **UNKNOWN**은 실행 관측이나 필요한 계약의 미확인이다. 사용자 제공 사실인 “SoloMage 클릭→원 PetStatusLayout 표시”를 출발점으로 사용했으며 이번에 화면을 재검증하지 않았다. 출처 비중은 명령/필드/노드 계약은 클라이언트 원문, 공급/현재 지원 범위는 로컬 도구 소스다. 이 조사에서 공식 API·L1J를 원본 UI 계약에 채택한 비율은 **0**, 새 게임 실행 근거도 **0**이다. 추천 의미 변경은 별도 LOCAL 설계다.

## 1. 문자열과 실제 공급 경로

### 추출 제공자와 실행 클론은 별개다

1. `tools/local_resource_provider/provider.py:99–113,149–177`은 서명된 catalog·AEAD·크기/SHA를 대조해 plaintext를 읽고 `work/local_resource_provider/assets/`에 저장하는 **오프라인 추출 도구**다. 수정 파일을 재사용하는 API가 아니다. 다른 기존 출력이면 `existing_asset_not_identical`을 거부한다. [README](../../../tools/local_resource_provider/README.md)의 “not mounted”는 이 provider 자체의 경계다.
2. 후속 `tools/local_asset_slot/materialize.py:10–15,69–87,198–202`는 검증된 67개를 `work/standalone_boot/current-unmodified-clone/`에 별도 복사한다. 원본과 다른 source는 `source_asset_hash_size_mismatch`, 다른 destination은 `destination_conflict_no_overwrite`로 거부한다. **provider assets만 수정하고 이 도구를 재실행하는 방법으로는 편집판을 배치할 수 없다.** 기존 보존·검증 경로를 우회하거나 성공 기록을 고쳐 쓰는 안은 제안하지 않는다.
3. `tools/root_mount_startup_trial/README.md:19–21`의 후속 root-mount 후보는 Native root를 module directory의 `/`로 바꾸고, 없는 파일/읽기 실패는 기존 pack으로 fallback한다. `/memory/`, `/pack/`의 우선 prefix는 남는다. `work/local_native_login_candidate/manifest-final.json:28–68`은 frozen root-mount 6구간 계보를 남기고, 현재 `tools/local_original_session/launcher.py:46–105`의 sibling 계열은 실행 클론을 `resource_directory`로 사용한다. 따라서 provider의 과거 “미탑재” 문구만으로 현재 raw 공급 경로가 없다고 결론내리면 틀린다.

세부 정적 경로는 `work/local-provider-consumer.py:24–58`의 Native `B74A20` stream resolver다. prefix를 제거하고 root와 결합하며 raw TryLoadUIFile은 size==read 성공을 사용한다. `launcher.py:617–658`의 `GenuineConversations`와 `tools/preserved_pack_bootstrap/session_adapter.py:11–12,26–38`은 clone pack 식별에 맞춘 VERSION 자원을 공급하며, 매번 assets의 CSV를 송신하는 bridge가 아니다. 조사한 이 경로에서 CSV 전용 HTTP URL은 확인하지 못했다. 현 후보 바이너리의 frozen 6구간을 새로 해독하거나 실제 file open을 관측하지는 않았다.

조사 때 provider와 클론의 `data/string.csv`는 각각 **637926B**, SHA256 `aab0a19b92d349724672695ebd9ea8aba00df3559bbbaa3f76ace198172f50af`로 같았다. 현재 catalog는 `work/asset_data_analysis/current/catalog.tsv:139`, archive=`data_0.lcx`다. 클론 `data/string.csv`가 실제 읽기 대상이 되는 **정적 공급 경로는 있다.** 다만 이번에는 그 파일 open/선택 locale/화면 변경을 관측하지 않았으므로 “수정하면 반드시 바뀐다”는 실행 확정은 아니다.

수정판을 실험할 때의 후보는 원문 assets와 공식 pack을 보존한 **별도 편집용 raw `data/string.csv` 또는 instance-local Text adapter**다. 실행 후보가 실제 이 root-mount 계보인지, 더 높은 memory/pack 요청을 쓰는지, 문자열 bank가 이미 초기화됐는지 확인해야 한다. 새 배치/검사 도구는 이번에 만들지 않았다.

### 무결성·캐시를 나눠 판단한다

| 층 | 확인한 것 | 확인하지 못한 것 |
|---|---|---|
| 오프라인 provider | catalog Ed25519/AEAD, plaintext hash/size, 보존 cache38 검증·다른 출력 거부 | 편집본 허용/동적 공급 기능 없음 |
| 고정67 배치 도구 | metadata 및 source/destination 동일성 확인, 덮어쓰기 거부 | 편집판 배포 계약 없음 |
| 클라이언트 Native root | raw 경로와 pack fallback 후보 | 선택한 raw CSV/CSB의 runtime 무결성 검사 유무를 전역적으로 확정하지 못함 |
| 문자열·레이아웃 객체 | native는 resolver `338FF0`와 현재 layout 객체를 사용 | CSV 재읽기 시점·hot reload·모든 cache 무효화/레이아웃 재생성 정책 UNKNOWN |

따라서 “암호화 pack의 무결성 때문에 무조건 편집 불가”와 “raw 파일이면 검사·캐시가 전혀 없다” 모두 근거 부족이다. 런타임 파일 수정만으로 현재 열린 창이 즉시 갱신된다고 주장하지 않는다.

### 명령 ID와 공유 위험

현재 CSV는 UTF-8-SIG, 열은 `ID,EP,TYPE,KR,TW,JP,EN`이다. ID와 물리 행 번호를 혼동하지 않는다.

| 항목 | string.csv ID / 행 | CSB 이름 |
|---|---|---|
| 공격 목표 지정 | 11497 / 11498 | Targeting |
| 공격 태세 | 11498 / 11499 | AttackStance |
| 방어 태세 | 11499 / 11500 | DefendStance |
| 휴식 | 11500 / 11501 | Rest |
| 산개 | 11501 / 11502 | Spread |
| 경계 | 11502 / 11503 | Alert |
| 수집 | 11503 / 11504 | Gather |
| 해산 | 11504 / 11505 | Dismiss |
| 이름 정하기 | 11505 / 11506 | Name |

`TYPE=UI_PET`는 다른 용례가 없다는 보장이 아니다. **ID11497..11504는 펫의 현재 상태 표시와 Summon 상태 표시에서도 재사용**된다(`run396/commands/pet-update.txt:630–711`, `run279/.../source/commands/contract.md`). 예를 들어 ID11501을 “동료 가방”으로 바꾸면 산개 버튼뿐 아니라 같은 상태값의 표시에도 그 문구가 들어갈 수 있다. 동료와 일반 펫은 같은 PetLayout을 쓰므로 전역 CSV/CSB 수정의 영향도 함께 받는다. 펫 보관소 `dick1/depositpet/retrievepet`는 별도 UML 경로다([PET_EVIDENCE](PET_EVIDENCE.md)의 보관소 절). 이것만으로 펫 상점·보관소를 포함한 모든 native/CSB 용례가 독립적이라고 판정하지 않는다. 전체 문자열 ID 용례의 전수 폐쇄는 미확인이다.

보존 CSB의 좁힌 검색에서도 ID11497은 `Summon/SummonLayout.csb`와 Purple Summon판에 있고, 11497..11512는 `Purple/Purple_Pet/Purple_PetLayout.csb`에도 있다. 따라서 표시 공유는 native 상태 분기뿐 아니라 authored CSB에서도 확인된다. **펫 상점의 추가 native ID 공유 여부는 UNKNOWN**이다.

## 2. 각 항목 클릭과 서버 재해석의 한계

`PetStatusLayout` factory=`3F5830`, Initialize=`A81400..A82974`다. 실제 `Root.Pet_Main.ListviewScroll.ListView.*` 노드를 이름으로 찾고 widget+`4F0`에 `A5C1E0`로 callable을 등록한다. 공통 `54C460`은 `4F02 CS_PET_COMMAND_REQ`를 만든다. required closed-enum **f1**, repeated string **f2**, optional u32 **f3**이며 이 producer는 f3에 **현재 Minion+198 low32 UID를 실제 present**로 쓴다. 조종 대상과 공격할 적 UID를 혼동하지 않는다.

| 항목 | 원 경로·실제 요청 | 서버만 재해석할 때 남는 동작 |
|---|---|---|
| 공격 목표 지정 | `A84480→54C380→1689D0(command4)`로 선택 대기. 다음 actor 클릭의 `163F90`이 **f1=1, f2=[공격대상 UID 10진 문자열], f3=펫UID** 송신 | 누르는 즉시 mode1이 오는 버튼이 아님. 대상 선택·취소 흐름이 먼저 남음 |
| 공격 태세 | `A843A0→54C460`, **f1=2**, f2=[] | 선정 invoke의 후속은 Pair 정리. 별도 확인창/직접 close는 확인되지 않음 |
| 방어 태세 | `A842C0→54C460`, **f1=3**, f2=[] | 위와 같음 |
| 휴식 | `A841E0→54C460`, **f1=4**, f2=[] | 위와 같음. 현재 동료 서버는 HOLD/PASSIVE로 바꾸므로 새 용도라면 기존 상태 변경도 분리해야 함 |
| 산개 | `A84100→54C460`, **f1=7**, f2=[] | 선정 invoke에는 확인창/직접 close 없음. 새 용도의 후보 |
| 경계 | `A84020→54C460`, **f1=5**, f2=[] | 위와 같음. 새 용도의 후보 |
| 수집 | `A83F40→54C460`, **f1=6**, f2=[] | 일반 펫의 실제 수집 기능과 충돌하므로 동료 전용 구분 필요 |
| 해산 | `A83D30`이 bank0 **ID453**의 확인용 입력(config2)을 열고, 확인용 `A848E0`이 **f1=8**, f2=[] 송신 | 서버 수신 전에 확인 절차가 있음. callback 뒤 `560F0→3EF2A0(command1)`로 PetLayout hide를 요청함. 서버가 가방으로 해석해도 이 절차는 없어지지 않음 |
| 이름 정하기 | `A83B20`이 bank0 **ID325**의 입력창(config0)을 열고, `A84680`이 **f1=9, f2=[입력 이름], f3=현재 MinionUID low32** 송신 | 입력창이 먼저 남음. 이름을 입력하지 않는 일반 기능 버튼으로 만들려면 클릭 callback 단계에서 교체해야 함 |

목표 지정은 `run400_pet_command_target/target/selected.txt:82–159`, 일반 명령은 `run396_pet_control/commands/pet-commands.txt:31–222`, 해산은 같은 `pet-update.txt:1–81`과 `dismiss.txt`가 직접 근거다. 이름9는 이번 추가 정적 조사로 보강했다. **9라는 정수만 보고 기존 서버가 허용한다고 판단하지 않는다.**

추가 원문은 [selected-static.json](pet-window-static/selected-static.json) **38394B**에 보존했다. `:11`은 Name invoke, `:122`는 mode9 producer, `:297`은 config2 submit, `:512`는 cancel, `:729`는 PetLayout 명령 dispatcher다. 기존 `work/local_server_rea_20261016/run101_item14_local_spawn_contract/ui_acquisition/source-evidence.json`과 같은 폴더 `findings.md:23–27`의 공통 popup 경로를 재사용하고 누락 구간은 같은 파생 carrier의 pefile/Capstone 정적 읽기로 보강했다.

특히 config2의 **`9B7E30`은 원 입력 문자열을 ASCII 소문자화하고 정확한 `y`, `yes`, UTF-8 `ㅛ`와 비교한 뒤에만 primary callback을 실행**한다. 단순 버튼명만 보고 무조건 mode8 송신이라고 해석하지 않는다. 취소 `9B7CA0`는 optional secondary만 호출하고, 선정 Pet Dismiss의 secondary는 초기 zero여서 이 경로로 primary mode8을 실행하지 않는다. 실제 UI 입력·키 이벤트·창 외형은 관측하지 않았다. `A848E0`은 서버 ACK를 기다리지 않고 명령8 뒤 로컬 hide 명령을 실행하며, child 상태를 로컬에서8로 쓰는 경로는 아니다.

창 X는 `A84550→layout.v70(false)`다(`selected-static.json:285`). 실제 PetStatusLayout v70=`A10BB0`의 선정 prefix는 node.v148(false)와 layout+70=false를 확인한다(`:893`). 전체 함수/창의 최종 파괴·Minion UID 초기화·배우 제거까지 입증하지 않는다. 이름 callback 선정 body에서는 요청 뒤 Pair/string/protobuf 정리를 확인했으며 PetLayout hide 직접 호출은 확인하지 못했다. 공통 입력창 자체의 최종 닫기와 실패/취소 체감은 별도 UNKNOWN이다.

현재 로컬 동료 handler `tools/local_original_session/world_feature_companion.py:628–638,739–770`은 mode **1/2/3/4/8만 허용**하고, mode 변경 뒤 `4F14` 상태 갱신을 붙인다. 이름9·경계5·수집6·산개7은 이 동료 handler가 현재 지원하는 기능이 아니다. 일반 펫 `world_feature_pet.py:536–555`는 1..7을 실제 AI 정책에 사용한다. 같은 opcode 전체를 바꾸지 말고 기존 동료 actor/소유 분기 안에서 선택한 LOCAL 동작만 연결해야 한다.

모드 수신만으로 클라이언트가 새 창을 스스로 고르는 계약은 없다. 실제 상태 문구는 `4F14.child.f1`이 결정하므로, 명령값을 설정/가방으로 재사용해도 그 값을 그대로 상태로 echo하면 기존 상태 문구와 어긋난다. 새 기능 진입과 실제 동료 전투/이동 상태를 분리해야 한다. 명령 뒤 `4F14`를 항상 보내야 한다는 공식 규칙이나 별도 명령 ACK 전체는 UNKNOWN이다.

## 3. 레이아웃 파일·재배치·증설

실제 일반판 파일은 **`Pet/PetLayout.csb`**이며 현재 catalog 표기는 lowercase `pet/petlayout.csb`다. 14228B, SHA256 `6ffe969da4839b0ed5a4452989aa2002bf37afef45328e8462b1d9fb3013d40c`, `data_u.lcx`, current-vs-preserved=`identical`(`catalog.tsv:4478`)이다. 함께 `pet/petlayoutline.csb`(:4479), `petlayoutscene.csb`(:4482), 별도 Purple판 `purple/purple_pet/purple_petlayout.csb`(:4571), `purple_petlayoutscene.csb`(:4638)가 있다. 소스 이름/확장자만으로 Cocos editor 원프로젝트가 확보됐다고 보지 않는다.

보존 plaintext의 위치는 `C:/Users/Chansol/Documents/Codex/2026-09-07/d-lineage-classic/outputs/decrypted-pack/data_u/Pet/PetLayout.csb`다. 이 조사에서 실행 클론과 provider assets에 해당 Pet CSB raw 사본은 없었다. 따라서 현재는 pack fallback 후보이며 **별도 raw CSB를 실제 요청 경로에 공급하는 작업이 먼저 필요**하다. 복호화 archive나 원본 파일을 직접 고치는 안은 권장하지 않는다. 일반/Purple 중 실제 선택 자원과 raw 우선 소비는 실행 미확인이다.

CSB는 기존 `tools/local_character_creation_source/parse_login_csb.py`의 `Flat` reader로 읽기만 했다. byte offset10224에는 `{"text_id":11497}`,9812에는11498,6584에는11506,6220에는11507,5832에는11508,5492에는11509,5152에는11510,4800에는11511,4452에는11512가 있다. 노드 트리·text_id의 실물 근거이며 현재 실행에서 이 bytes를 소비했다는 관측은 아니다.

확인한 ListView authored 자식 순서:

```text
MyPet → Targeting → AttackStance → DefendStance → Rest → Spread
→ Alert → Gather → Dismiss → Name → Blank_00
→ Status → Hunger → HP → MP → Level → Exp → Alignment
```

기존 노드의 이름을 유지하면 native lookup 연결을 보존한 채 순서·위치·크기·text_id를 바꾸는 후보가 된다. 반면 이름을 바꾸면 `A81400`의 lookup/callback/상태 receiver가 끊어질 수 있다. ListView 자동 정렬·컨텐츠 크기·터치 영역·숨김 행의 빈 공간은 실제 renderer에서 별도 확인해야 한다.

**10번째 기능 행을 CSB에 추가해도 원 native init은 그 새 이름을 알지 못한다.** click callback 등록, 현재 대상 값, 서버/목적창 소비를 추가해야 실제 기능이 된다. `4F02`의 f1도 closed enum이므로 임의의10/11을 새 명령으로 만들어 보내는 방식을 원본 확장 계약으로 취급하지 않는다. 새 client-local callback이 기존 목적창 API로 연결되는 방식은 가능성 있는 별도 구현이다. binary CSB의 문자열 길이를 바꾸는 단순 hex 덮어쓰기보다 구조를 보존하는 writer/원 authoring 자료가 필요하며, 이번에는 writer나 편집본을 만들지 않았다.

## 4. 상태 라벨·값 바꾸기와 숨김

`4F14` 상위 f2=1이 PetLayout을 고르고, `54D660→A82980`의 property1이 **`A82DD0`**으로 child를 전달한다. 여기서 실제 Text 값을 매번 갱신하므로 초기 CSB 문자열과 갱신 라벨을 구분한다.

| 행 | 초기 CSB text_id | 실제 native 갱신 입력·라벨 |
|---|---:|---|
| 현재 상태 | 11506 | child.f1=1..8→명령 문자열ID11497..11504 선택, 라벨 **11506**과 결합 |
| 배고픔 | 11507 | **child.f8 i32**, 라벨 **5713**. 값은 bank1 ID608..612의5단계로 변환 |
| HP | 11508 | **child.f3/f2**, 라벨 **5698**, `{}: {}/{}` |
| MP | 11509 | **child.f5/f4**, 라벨 **5699**, `{}: {}/{}` |
| 레벨 | 11510 | **child.f6 u32**, 라벨 **3549** |
| 경험치 | 11511 | **child.f10 double**, 라벨 **8225**, `{}: {:.4f}%` |
| 성향치 | 11512 | **child.f9 i32**, 라벨 **3550**, `{}: {}` |

직접 근거는 `run396_pet_control/commands/pet-update.txt:130–252,291–320,359–387,426–453,492–519,558–584,630–711`이다. 배고픔은 0..20/21..40/41..60/61..80/>80으로 범주화한다. 음수는 **범주 문자열만 공백**으로 남고 이후 `A8301A`부터 라벨5713·formatter·Text setter `BF9ED0`가 실행된다. **음수로 행 전체를 숨길 수 없다.** bank1은 UI CSV의 ID11513..11517와 별도 resolver 선택이므로 숫자가 비슷하다고 그5행을 소비한다고 단정하지 않는다.

child **f1..f6 required**, f7..f10 optional이다. optional f8/f9를 생략하는 것은 visibility 명령이 아니다. 현재 동료 `_companion_status_frame`은 f8/f9를 생산하지 않는다. 이를 숨김 지원이라고 해석하지 않는다. 소비자는 해당 scalar를 읽으며 기본값에 따른 내용이 표시될 수 있다.

문구만 바꾸려면 초기 text_id뿐 아니라 실제 갱신에 사용하는 ID도 고려한다. 예를 들어 CSB의 성향치 text_id11512만 바꿔도 다음4F14에서 ID3550 라벨로 다시 쓰인다. 허기·성향을 다른 상태로 재사용하려면 각각 **5단계 범주·signed 정수라는 소비 제약** 안에서 LOCAL 의미를 정하거나 instance의 formatter를 바꿔야 한다. 자유 문자열을 f8/f9에 넣을 수 없다.

숨김은 대상 Text/행 노드의 visibility와 리스트 높이·입력을 함께 처리하는 방식이 후보다. receiver 포인터가 계속 갱신되므로 노드 삭제는 raw pointer 수명 확인 전에는 피해야 한다. 라벨을 공백으로 하면 콜론·수치·빈 행이 남을 수 있다. 전역 라벨/범주 bank 교체는 일반 펫·다른 UI에도 영향을 줄 수 있어 동료 instance 단위 처리를 권장한다.

## 5. 브리지로 클릭을 다른 창에 연결하기

현재 `tools/local_original_session/native/ui_open_bridge.hpp:12–17,79–122`의 명령은 **마법 toggle, 스탯 toggle, 실제 actor 조회→펫 상태 요청, unsupported hotbar**다. `LC-Owned-UIOpen-v1` custom window-message를 owned UI thread에서 처리하며 PetStatus 항목 callback을 가로채는 코드가 아니다. 기존 `own-login-bridge`라는 DLL 이름만으로 ATS·창고 열기나 클릭 hook이 구현됐다고 판단하지 않는다. 반환도 `window_state/effect=UNKNOWN`이다.

| 경로 | 현재 확인한 기반 | 추가로 연결할 것·위험 |
|---|---|---|
| 기존 행 callback 교체 | `A81400`의 named widget lookup·`A5C1E0` 등록, 각 invoke RVA 확보 | 실제 current layout/widget을 원 소유 아래 얻기, 기존 callback 수명/복구, 같은 UI thread에서 실행, 닫힘·재소환·로그아웃 시 진입 중 호출 정리. `54C460`/공통 send 전역 hook은 일반 펫·Summon까지 영향 |
| ATS 설정 열기 | `ATSLayout` TD1670ED0/vptr120F308/ctor8E3E60/init8E5F40, PCImpl TD1755E00/vptr1210E88/factory8FCFE0/init8FBFE0 확보 | current manager의 owning get/create caller와 대상 model 연결. 사용자가 말한 `atSettingsLayout`을 확인된 native 클래스명으로 단정하지 않음 |
| 창고 UI 재사용 | `4ED2 COUNT` A 모델, `0971 LIST` B 모델, `4ED1` 선택·확정, `097B` close의 정적 계약 | 동료 bag의 양방향 이동/착용·현재 actor/영구 캐릭터ID·entrykey/context·저장/복원 결속. 창 열기만으로 가방 기능 완성 아님 |

**ATS는 기존 마법/스탯 toggle을 복사하면 안 된다.** 최신 `ats-evidence/ui2_vtables.json:108,233`, `ui2_base_event_methods.json:243` 이후에서 ATS v98=`8E6550`은 command0→v70(true), command1→v70(false), **command2→v88 표시상태 조회**다. 기존 `A11810`의 command2 toggle과 다르다. 정상 owning ATS instance를 얻은 뒤 command0의 show 경로를 쓰는 것이 후보이며, factory 주소를 무작정 호출하거나 raw 포인터를 재사용하지 않는다.

ATS 창은 기본적으로 **현재 PC의 가방·배운 마법·설정**을 사용한다. 기사 접속 상태에서 창만 열면 SoloMage 편집 모델로 바뀐다는 근거는 없다. 동료 설정 진입은 [ATS_COMPANION_EVIDENCE](ATS_COMPANION_EVIDENCE.md)의 B안처럼 편집 대상/학습/가방 view·Save 귀속을 추가 연결해야 한다. 직접 법사로 접속해 설정한 뒤 같은 영구ID의 동료가 사용하는 A안은 별도 우선 후보다. 과거 run278의 창 identity 미확인을 최신 결과보다 우선하지 않는다.

동료 bag 데이터는 이미 `world_feature_trade.py:18,119,154`, `world_feature_companion.py:419–424` 등에 존재한다. 누락은 원 가방 UI와 그 데이터/소비의 연결이다. 현재 창고 경로 `world_feature_town.py:63–108`은 NPC interaction reference와 발급한 context/row를 사용하므로, 가방 진입에 기존 NPC 문맥을 위조하거나 검사를 삭제해 통과시키면 안 된다. 동료 문맥으로 실제 producer→list→선택→소비를 연결해야 한다. `4F09 CS_PET_WAREHOUSE_REQ`는 별도 PetStorageLayout의 **펫 맡기기/찾기** 요청이며 동료 아이템 가방 opcode라는 근거가 아니다.

서버에서 mode5/7을 받고 정상 창고 S2C 모델을 발급하는 경로는 client callback hook 없이 가능한 **조건부 후보**다. 그 경우에도 버튼 문구·상태 문구와 동료 context·뒤의4ED1 소비를 연결해야 한다. ATS는 현재 확인된 서버 명령만으로 임의 창을 여는 계약이 없어 client adapter가 필요하다. UI thread에서 서버 async handler를 직접 호출하는 방식 대신 기존 broker eventloop/명령 전달 경계를 재사용해야 한다.

## 추천안과 후속 최소 확인

추천은 **9개를 유지한 채 동료 instance에서 필요한 행만 재사용**하는 것이다. 먼저 산개7을 “동료 가방”, 경계5를 “동료 설정” 후보로 삼으면 현재 동료의1/2/3/4/8 동작과 직접 충돌이 적다. 나머지 불필요한 휴식·해산·이름은 기능을 정하기 전 숨김 후보로 두고, 해산8/이름9를 그대로 일반 버튼처럼 재해석하지 않는다. 이는 구현안 제안이며 사용자 결정이나 완료된 기능이 아니다.

전역 CSV는 일반 펫·Summon과 상태 표시까지 바꿀 수 있으므로 동료 전용 Text/행 adapter를 우선한다. CSB 전역 변경이 허용될 때만 기존 키를 유지한 배치를 별도 편집용 raw 자원으로 공급한다. 새 행 증설·공식 archive 재포장·자체 GDI 패널은 이번 추천의 선행조건이 아니다.

이후 별도 구현·실행 단계에서 원본으로 확인할 최소 항목은 다음과 같다. 이번에는 모두 **UNRUN**이다.

1. 선택된 실행 후보의 root 요청·실제 `data/string.csv`/Pet CSB open 경로·locale를 확인하고, 편집용 사본의 한 문구가 재시작/창 재생성 후 바뀌는지 본다. 일반 펫·Summon·펫 보관소의 같은 ID 영향도 비교한다.
2. 해산 취소/수락과 이름 취소/확정을 나누어 실제 요청·창 닫힘을 확인한다. 목표 지정은 다음 적 클릭→mode1/f2 대상UID 흐름과 취소를 확인한다. 다음 행동은 앞 상태/응답 뒤에 수행한다.
3. 바꾼 행 하나에서 원 callback이 중복 실행되지 않는지, 실제 target·원래 전투 상태가 유지되는지,4F14 갱신이 문구/visibility를 되돌리지 않는지 본다.
4. ATS는 SoloMage의 설정·학습·가방을 편집하고 기사 설정을 덮지 않는지 확인한다. 가방은 목록 표시→선택→실제 양쪽 수량/장비/저장→재접속 복원까지 확인한다. 닫힘·제거·재소환·로그아웃 후의 stale callback/UID도 확인한다.

## 조사 검증과 남은 UNKNOWN

이번 검증은 `git status --short --branch`, `git branch --sort=-committerdate`, `git worktree list`, 관련 경로의 `rg -n`/`rg --files`, UTF-8 원문 읽기, 현재 CSV2개 해시/크기 비교, 보존 CSB의 구조 읽기, 선택 native 함수의 정적 분석이다. 게임·서버·포트 시험이나 제품 단위시험은 실행하지 않았다. 새 guard·핀·검사기를 추가하지 않았다.

REA MCP는 시작 `binary_session open:false`를 확인하고 파생 carrier의 focused analyze를 시도했으나 provider 초기 분석이 끝나기 전에 취소했다. **새 analyze 결과/Evidence ID는 없다.** 이를 성공한 REA dossier로 표시하지 않고 위 파일 기반 원문을 근거로 쓴다. 새 session은 `close_binary` 정상 반환 후 `binary_session open:false`를 확인했다. 실패한 도구 호출을 클라이언트 기능 실패로 취급하지 않는다.

작성 후 `python -X utf8 -B -`의 일회성 읽기 검사로 문서 UTF-8 decode·대체문자0·로컬 링크 **10개 전부 존재**, 신규 JSON parse·schema/runtime=false·선정 함수 **8개**를 확인했다. 신규 파일은 이 문서와 `pet-window-static/selected-static.json`뿐이며 코드·리소스 파일 변경은 없다. `git diff --check -- <문서>`도 exit0이지만 work 산출물의 Git 추적 밖 상태 때문에 이를 본문 검사 근거로 대신하지 않았다.

남은 UNKNOWN은 실제 raw 리소스 선택/캐시·무결성 전체, 전체 문자열ID 공유 범위, 일반/Purple의 현재 선택, renderer의 순서/숨김/새 행 동작, 실제 클릭·모달/창 종료, callback 설치/퇴역·목적창 owning caller, 동료 ATS view/저장 귀속, 가방 UI의 끝까지 이어지는 실제 소비·저장이다. 정적 연결을 화면·입력·전체 원본 동등성 PASS로 확대하지 않는다.
