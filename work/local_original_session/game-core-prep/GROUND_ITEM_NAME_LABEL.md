# 바닥 아이템 이름의 캐릭터·몬스터 가림 조사

2026-10-31 / 서버·클라이언트 정적 조사와 오프라인 단위 시험만 수행.

**원인 판정: 미확정. 클라이언트 고유 Item HUD 표시 경로가 유력하지만, 공식 서버의 동일 사건 패킷·겹침 화면이 없어 원본 동등성을 확정하지 못했다. 서버 수정 없음.**

서버가 이름을 보내는 경로는 확인했다. 그러나 잘못된 ‘이름 항상 표시’ 플래그·높이·레이어 값을 원본과 다르게 보낸다는 근거는 확보하지 못했다. 반대로 원본 클라이언트에는 **‘드롭 아이템(ALT)’ 옵션 → 설정 bool → ItemActorHud 표시**의 연결이 있다. 이 사실만으로 지금 사용자 화면의 겹침까지 원본과 같다고 단정하지 않는다. 근거 없는 필드 변경, 이름 삭제, 송신 순서 변경은 적용하지 않았다.

## 1. 서버에서 실제 보내는 값

생산자는 [world_visibility.py:191](../../../tools/local_original_session/world_visibility.py:191)의 `ground_frame`이다. [item_ground.py:19](../../../tools/local_original_session/item_ground.py:19)의 기존 local14 profile에서 f9만 실제 이름으로 교체하고 UID·좌표·그래픽·수량을 채운다. 이 profile 자체는 **로컬 선택값**([item_ground.py:18](../../../tools/local_original_session/item_ground.py:18))이며 공식 서버 캡처가 아니다.

| 필드 | 지상 Item | 몬스터 / PC와 비교 | 확인 범위 |
| --- | --- | --- | --- |
| f1 / f2 | packed 타일 좌표 / 월드 UID | 몬스터도 동일 종류의 좌표·UID. PC는 보유 actor_fields에서 좌표 갱신 | 화면 높이·z-order가 아니라 기존 위치·식별 계약 |
| f3 | `item_gfx[item_id].ground` (누락 시 기존 fallback22) | 몬스터 sprite_id, PC는 보유 appearance | appearance. 아이템 이름의 레이어 값으로 확인되지 않음 |
| f4 / f5 | action0 / direction0 | 몬스터 action0 / 실제 방향, PC 보유 action / 실제 방향 | f4는 action 입력. 높이·정렬로 바꿀 근거 없음 |
| f7 | 실제 수량 | 몬스터 기본0, PC 보유값 | Item+38 수량 계약 |
| f9 | canonical 인벤 f18 이름이 있으면 보존, 없으면 catalog 이름. 여러 개는 `수량 이름` | 몬스터도 f9에 이름, PC는 보유 이름 | 실제 텍스트의 공급원. ‘항상 표시’ bool은 아님 |
| f16 | false | 몬스터 false, 검증된 자기 PC profile은 true | Player/비Player 분기. 이름 표시 플래그로 변경하면 다른 actor 종류를 만들 위험 |
| f21 | 빈 bytes present | 몬스터 빈 문자열, PC 보유값 | Item admission gate가 아님 |
| f39 | 명시0 | 몬스터 template_id, PC 보유값 | 비Player의 signed 비음수 gate. 지상 아이템의 template나 레이어로 명명하지 않음 |
| f44 / f69 | 둘 다 omit | PC는 보유 optional 값 | f44는 nested Item 상태, f69는 optional appearance override. 레이어로 확인되지 않음 |
| 그 외 required | f6/8/11/12/13/19/22/23/24/27/28=0, f14/15/17/18=false, f10/20=빈 bytes | 몬스터 기본 profile과 같은 값. PC는 보유값 | 원서버 생산 규칙이 미확정인 필드를 포함. 전부 원본과 같거나 표시와 무관하다고 입증한 것은 아님 |

비교 근거: [world_visibility.py:71](../../../tools/local_original_session/world_visibility.py:71), [world_visibility.py:106](../../../tools/local_original_session/world_visibility.py:106), [world_visibility.py:201](../../../tools/local_original_session/world_visibility.py:201), [world_visibility.py:321](../../../tools/local_original_session/world_visibility.py:321), [actor_profile.py:93](../../../tools/local_native_login_spawn_render_retry_runtime/actor_profile.py:93). PC 프레임은 새 ground profile을 복사하지 않고 기존 선택 actor_fields를 재사용한다.

원 소비 계약의 f4 action / f7 수량 / f16·39 Item 분기 / 미해결 필드는 [run101 spawn_recipe/findings.md:16](../../local_server_rea_20261016/run101_item14_local_spawn_contract/spawn_recipe/findings.md:16) 및 [같은 문서:26](../../local_server_rea_20261016/run101_item14_local_spawn_contract/spawn_recipe/findings.md:26)에 구분되어 있다. 따라서 미해결 scalar를 임의 ‘높이’나 ‘draw order’로 바꾸지 않았다.

`item_known`은 PC별로 게시된 UID 집합이다. [world_visibility.py:415](../../../tools/local_original_session/world_visibility.py:415)는 시야 진입·이탈을 계산하고, [world_visibility.py:429](../../../tools/local_original_session/world_visibility.py:429)는 새 Item을 게시한다. 이 경로에는 별도의 label 레이어 필드가 없다. `_refresh`는 몬스터→Item→PC 순으로 메시지를 조합하지만([world_visibility.py:406](../../../tools/local_original_session/world_visibility.py:406)), **송신 순서가 최종 그리기 순서를 결정한다는 원 소비 근거는 없다.**

## 2. 원본 데이터·패킷 근거와의 대조

- [native-dump-v1.jsonl:952](../../source_game_data/native-dump-v1.jsonl:952)의 item1은 `$14 / 아탐`, item table f5=8 / f6=14이다. [같은 파일:965](../../source_game_data/native-dump-v1.jsonl:965)의 item14는 빨간 물약, f5=80 / f6=45이다. 서버는 이러한 catalog 이름·ground 그래픽 자료를 재사용한다. **item table의 f6과 SC4E96의 f6은 다른 schema**다.
- 해당 dump는 npc951 / item1266 / spell433 / token1419개 catalog 레코드다. 공식 지상 Actor 수신 캡처가 아니므로 SC4E96의 bool·높이·레이어 값을 직접 대조할 수 없다.
- f9는 원 sparse schema에서 bytes이다. 원 `4B690 → CD0B0` 경로의 이름 전달 및 Item 분기는 [ITEM_INFO_EVIDENCE.md:32](ITEM_INFO_EVIDENCE.md:32)에 있다. **기존 local14의 빈 f9와 지금 이름 있는 f9의 차이는 확인되지만, 그것을 공식 서버와의 차이라고 부를 수 없다.**
- 기존 원본 조사도 동일 template1 DROP에 결속된 authoritative SC4E96 한 건이 부족하다고 명시한다([run100 worker/findings.md:39](../../local_server_rea_20261016/run100_item1_ground_graphics_producer/worker/findings.md:39)). 이번에도 동일 사건 원본 패킷을 확보한 것으로 표시하지 않는다.

따라서 ‘원본은 f9가 비어 있다’, ‘f14를 켜면 가림이 해소된다’, ‘f6을 음수로 내리면 된다’ 등의 수정 근거가 없다. 특히 f9를 비우는 방법은 이름을 없애는 로컬 동작 변경이지 원본 레이어 복원이 아니다.

## 3. 클라이언트 옵션과 이름 HUD

기준 CONTROL SHA256은 `9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`이다([item_ground_wire.py:29](../../../tools/local_original_session/item_ground_wire.py:29)). 신규 정적 읽기는 기존 분석용 파생 PE `work/rea_lineage_resume_20261013/main-gameplay/audit/metadata-v2/DERIVED_RESTORED_ANALYSIS_ONLY.exe`를 대상으로 했다. 그 SHA256은 `c822838351d774a2022af434829a36dbd9bee030bf22182b834ca4e8659701a9`이다. 실행 메모리·현재 사용자 설정을 읽은 것이 아니다. 아래 주소는 이 PE의 **RVA**다.

확인한 원 자원/경로:

- 문자열 [string.csv:6361](../../local_resource_provider/assets/data/string.csv:6361), ID6360 = **드롭 아이템(ALT)**. 옵션 기본 키 Ctrl+V는 [ORIGINAL_HOTKEYS.md:24](ORIGINAL_HOTKEYS.md:24)의 정적 등록 근거를 재사용했다.
- 보존 자원 `C:/Users/Chansol/Documents/Codex/2026-09-07/d-lineage-classic/outputs/decrypted-pack/data_u/Option/OptionLayout.csb`의 node offset `0x9234`: `Node/Root/Options/ListviewScroll/ListView/Interface/DroppedItems`. SHA256 `22183550ccd01747d06bd7a25f88a4dbe2d6a5f6a7e14e664fbd0d538f6659f8`.
- 같은 보존 자원의 `ActorHud/HudItemLayout.csb`에는 `Root/Text_Name`과 `Root/Image_NameBorder`가 있다. 문자열뿐 아니라 기존 FlatBuffer node parser로 계층을 읽었다.
- 보존 option CSB와 current catalog의 option CSB는 changed다([catalog.tsv:4456](../../asset_data_analysis/current/catalog.tsv:4456)). [string.csv의 색인:139](../../asset_data_analysis/current/catalog.tsv:139)도 changed다. 두 자원 시점을 동일하다고 합산하지 않는다. 기존 보존 자원과 고정 PE의 **DroppedItems 식별자·실제 콜백** 연결을 아래에서 별도로 확인했다.

| 파생 PE RVA | 직접 관찰한 연결 |
| --- | --- |
| `A6259B..A626DB` | `DroppedItems` 문자열 `122A770`으로 옵션 node를 조회하고, 표시값·클릭 callback을 연결 |
| `A6D3A8` / vtable `1229E30+10` | 해당 클릭 함수 객체의 invoke는 `A761B0` |
| `A761CE..A761F0` | CharacterConfig 전역 `163AFA0` → `F8960` → `F8000`; SystemOption의 hasbits에 `0x100` 설정, **+2C bool을 반전** |
| `A761F3..A76203` | ConfigSubsystem getter `11B7F0` → `105310` 호출. 설정 변경 통지/저장 계열 연결이며 저장 완료 관측은 아님 |
| `A64EFF..A64F47` | 같은 +2C bool을 읽어 문자열 ID567(`0x237`) / 568(`0x238`) 중 선택. 옵션 표시값의 소비 |
| `F8960` / `F8000` | CharacterConfig의 +30 child → 해당 child의 +20 SystemOption. vptr `1184890`의 RTTI는 `CharacterConfig_SystemOptionSection`, `1183F38`은 `CharacterConfig_SystemOption` |
| `FB615..FB624` | SystemOption serializer는 +2C bool을 tag `0x20`, 즉 **해당 nested message의 f4 bool**로 기록. presence bit8을 wire f9로 오독하면 안 됨 |
| `98EED0..98F71C` | `ItemActorHud::Init` 문자열을 가진 생성/초기화. vptr `121AA70`; `98EF9C..98EFAA`는 Actor 이름 getter `41610` 결과를 `98F8F0`에 전달해 HUD 이름 저장 |
| `98F81D..98F89E` | 같은 CharacterConfig 전역 +30/+20 child를 선택하고 `FB9B0`로 설정 복사. **SystemOption+2C 값**을 읽어 inherited HUD 표시 함수에 bool로 전달 |
| `979288..9792A2` | 위 표시 함수의 분기와 UI node virtual+148 호출. 설정 bool→HUD 표시 경로의 끝. 전체 렌더 pass·다른 actor와의 가림 해결까지 확인한 것은 아님 |

**관찰:** 서버 Actor 이름과 별개로 원 클라이언트가 Item 전용 HUD와 표시 옵션을 소유한다. **추론:** 이름이 스프라이트를 가리는 문제는 이 HUD의 배치·합성 규칙일 가능성이 높다. **미확인:** PC/몬스터를 포함한 최종 합성 순서, 다른 SC4E96 미해결 필드의 간접 영향, 공식 온라인의 동일 겹침 화면.

Alt의 누름 유지/해제/토글 의미는 [ORIGINAL_HOTKEYS.md:38](ORIGINAL_HOTKEYS.md:38)과 마찬가지로 미확인이다. 옵션 문구만으로 ‘Alt가 반드시 토글이다’ 또는 ‘Alt를 누르는 동안만 표시한다’고 안내하지 않는다.

## 4. 설정 저장 위치

위 옵션은 **CharacterConfig → SystemOptionSection → SystemOption+2C**에 있다. ATS 설정으로 오인하지 않는다. 기존 Config 저장은 CharacterConfig를 직렬화·변환해 `CS_SAVE_SETTINGS_REQ/4ED6.f1`으로 보내고, 별도 ATSConfig는 f2로 보낸다([storage_findings.md:11](ats-evidence/storage_findings.md:11)). 서버 수신은 `4ED7` 계열이다.

싱글리니지의 로컬 저장은 launcher가 선택된 `args.store`와 같은 디렉터리의 **`account-settings.bin`**을 지정한다([launcher.py:5396](../../../tools/local_original_session/launcher.py:5396)). [settings.py:55](../../../tools/local_original_session/settings.py:55)의 SettingsStore가 계정 sidecar로 보존하고 [settings.py:138](../../../tools/local_original_session/settings.py:138)의 `noti_frame`이 저장값을 복귀 알림으로 만든다. 이 sidecar를 공식 클라이언트의 원래 로컬 설정 파일 경로라고 주장하지 않는다. 공식 서버의 내구 저장 위치·별도 로컬 cache 경로는 미확인이다.

사용자 저장 파일을 열거나 설정을 바꾸지 않았다. 현재 옵션이 켜져 있는지, 끈 값의 저장·재접속 복구가 실제로 성공하는지는 확인하지 않았다.

## 5. 가능한 대응과 비용·위험

| 방법 | 비용 | 효과·위험·한계 |
| --- | --- | --- |
| Ctrl+V → 환경 설정/인터페이스의 ‘드롭 아이템(ALT)’ 표시를 끄는 원 옵션 사용 | 코드 변경 없음; 이후 수동 플레이 확인 필요 | 이름 상시 표시를 줄일 수 있는 정적 연결이 있다. 사람·몹과 겹친 이름만 골라 숨기는 기능은 확인되지 않았다. 바닥 이름 전체가 안 보일 수 있음. Alt의 정확 동작은 별도 확인 필요 |
| DLL에서 기존 Item HUD 표시 조건을 조절해 hover/키 입력 시만 이름 표시 | 중간: 정확한 HUD owner·callback·설정·종료 수명과 입력 회귀 분석 필요 | 원 자원·이름은 유지 가능하나 hover/줍기 hit 영역·옵션과 충돌하거나 재생성 후 값이 복귀할 수 있음. 미구현 |
| DLL에서 PC/몬스터 화면 영역과 겹친 Item HUD만 숨기거나 위치 조정 | 높음: 화면 좌표·글자 경계·actor 위치·프레임 동기화·선택 판정 필요 | 과도한 숨김, 빠른 이동 중 깜박임, 조밀한 드롭의 위치 진동, 보이는 이름과 클릭 대상 불일치 위험. 미구현 |
| DLL에서 이름을 actor 뒤로 합성 | 높음: HUD와 월드 sprite의 합성/정렬 경계·가림 처리 변경 및 화면 회귀 필요 | 단순 패킷 순서 변경으로 보장 못 함. 이름·픽업 UI·다른 HUD 레이어·자원 수명에 영향 가능. 미구현 |

이는 공수의 상대 평가이며 구현 견적·완료 보장이 아니다. 이번에는 DLL·서버 코드·데이터를 변경하지 않았다.

## 6. 검증 결과와 남은 최소 입력

2026-10-31 실행 명령(모두 오프라인; 소켓을 여는 BrokerWorldTests는 선택하지 않음):

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:TEMP=(Resolve-Path _work/tmp).Path
$env:TMP=$env:TEMP
python -m unittest tools.local_original_session.world_ground_items_tests tools.local_original_session.world_visibility_regression_tests tools.local_original_session.world_spawn_tests.VisibilityTests tools.local_original_session.world_spawn_tests.SpawnerTests tools.local_original_session.world_iteminfo_tests.DisplayTests tools.local_original_session.play_feedback_fix_tests.DisplayProjectionTests tools.local_original_session.move_pickup_coverage_tests -v
```

**66 tests / 6.011초 / 실패0 / 오류0 / OK.** 원로그: `_work/tmp/ground-item-name-tests.txt`. 지상 수량·이름 프레임, 시야 진입·이탈, 드롭·줍기·만료·저장 실패 보존의 기존 단위 시험이다. 코드 변경이 없어 변경 모듈의 추가 시험은 없다. 이 결과는 화면 가림 해소나 정식 플레이 PASS가 아니다.

게임·헤드리스·포트 서버 실행, launcher_tests, manual_move_commands_tests, DLL 수정, 사용자 저장 수정, 커밋은 하지 않았다. REA는 위 파생 PE의 경로·해시를 확인했지만 `search_strings`는 **300초 timeout**으로 근거를 반환하지 못했다. 재시도/설정 수리 없이 분석 세션을 닫았고, 표의 신규 관찰은 로컬 PE mapping·Capstone 정적 읽기다. 임시 코드·node 목록·선택 disassembly는 모두 `_work/tmp`에 있다.

남은 최소 입력은 **같은 고정 원본에서 (1) 이름 있는 지상 Item SC4E96 한 건의 전체 필드·presence, (2) 사람/몬스터와 겹친 화면, (3) ‘드롭 아이템’ 옵션 변경 전후 및 Alt 눌림/해제 상태**다. 이 입력이 있어야 서버 값 차이와 원본 고유 겹침을 확정 분리할 수 있다. 이번 실행 금지 범위에서 새 캡처를 시도하지 않았다.
