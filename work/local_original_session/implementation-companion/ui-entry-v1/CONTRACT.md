# 동료법사 UI 진입 계약 확인 v1

판정: **기존 source만으로 native UI adapter 구현 불가, test_ready:false.** 제품 변경은 없으며 이 폴더는 source 계약 보고서다. REA 실행·게임·패킷·포트·브라우저·원본 저장 변경은 없다. 기존 통과 검사를 반복하지 않았다.

## 정확한 부모와 재사용 접점

- 수용 v5 host: `work/local_original_session/integration-1/companion-webpro-review-v5/extracted/tools/local_original_session/companion_host.py`, SHA256 `de95a7766f7725670f9c76e03aeece7d58bac371b94cd39fb8664b89eafcc3cf`.
- private actor-click host: `work/local_original_session/implementation-companion/actor-click-v1/tools/local_original_session/companion_host.py`, SHA256 `591c4b189a7d5b9b86943baf637a72cac5bb423fe4d84bfb6deb1ab24cce9846`.
- 해당 host 343행 `open_from_actor_click`는 같은 writer의 operation 안에서 실제 participant의 actor UID·generation identity·owner·character lease를 확인한다. 367행 `_open_panel_locked`는 단축키와 같은 panel/epoch를 사용하며, interface가 없으면 `COMPANION_ISOLATED_ATS_WINDOW_CONTRACT_UNAVAILABLE`로 중단한다. 이 경계를 재구현하거나 caller 없이 성공 처리하지 않는다.
- host 377행 `interface.open(namespace, layout='ATS', model, on_command, character_uid)`와 render/close/bind_hotkey/unbind_hotkey는 주입 계약이다. v5 `tests/test_companion_host.py:65`의 `InterfaceFixture`는 callback scope 기록만 하며 native ATS를 구현하지 않는다고 명시한다.

## 기존 원본 계약이 확정하는 범위

| 근거 | 확정 | 연결할 수 없는 경계 |
|---|---|---|
| REA216 `ui_source/contract.md:9-11` | Inventory shortcut 15EDF0/15ECF0 → current manager strong Pair → 159A20(command2, empty any64); Inventory close A0CF40 → command1 | Inventory registry DWORD 8/20084는 physical key나 ATS shortcut이 아니다. Inventory get-or-create를 ATS 생성으로 대입할 수 없다. |
| 같은 계약 12-13행 | ATSSubsystem getter644B0, vptr11B9C58 slot2=429D50, delegate1A8 및 configured rows438/440 | subsystem/row processor는 창 layout·create·callback·close를 제공하지 않는다. 441890 manual UI caller/등록도 UNKNOWN이다. |
| REA267 `source/selection/selection-contract.md` | 일반 선택 fullUID→627B0, 실제 byte88 분기→A07C0→A4340; targetUID command18/ownUID command10; 현재 Interaction+70 callable.virtual10 | 실제 Pet/Summoned callable·request builder가 이 dispatcher에 결속되지 않았다. command UID 저장은 비동기 current generation을 발급하지 않는다. |
| REA267 `source/contract.md` | Pet/Summoned HUD ctor 991BF0/99A2A0 및 HUD actor Pair retain | HP 표시·UID lookup은 버튼 요청/target 발급 근거가 아니다. packet 종류·action 값·정상 순서·packetless 여부는 UNKNOWN이다. |

REA216/267의 pin과 정확 원행 참조는 `evidence.json`에 경로·SHA256으로 고정했다. 기존 분석 계약을 재사용했으며 raw decode나 새 source graph 탐색은 하지 않았다. 확인 범위는 명시된 source/evidence와 bounded ATS/entry 검색이다. 저장소 전체에 구현이 없다는 주장은 하지 않는다.

## 다음에 필요한 최소 입력

1. 원 ATS window의 실제 layout/registry identity와 create/get-or-create, callback 등록·호출 ABI, render/update, close/destructor·UI thread 소유/수명. 자동사냥 설정·executor와 별도 인스턴스로 사용할 근거가 필요하다.
2. 실제 Pet/Summoned actor 클릭의 concrete Interaction callable/receiver 또는 request builder. 선택 actor fullUID가 어떤 요청 인수/동작값으로 들어가는지와 packetless 단계 여부를 확인해야 한다. generic NPC action15→4E43으로 대체하지 않는다.
3. 그 실제 callback에서 동일 owner/writer와 retained actor/current generation을 위 private host에 전달하고, retirement 후 callback을 해제할 수 있는 원 호출 수명. UID 숫자만으로 generation을 만들지 않는다.

기존 Inventory 진입·타캐릭터 ITEM 화면을 이 단위에서 복제하지 않는다. `open_items`의 별도 allied-character target 권위는 REA216에서 미공급으로 남으며 다른 담당 기능을 막는 새 gate로 추가하지 않는다. actor publication writer 파일도 수정하지 않았다.

## 시험 준비 상태와 다음 실행 경계

실행 caller/RUN_COMMAND는 **미제공**이며 `test_ready:false`다. 가짜 callback·packet·좌표를 넣은 대체 caller는 만들지 않았다. 기존 actor-click fixture 성공은 source scope 검사로 재사용하며 native UI 성공으로 확대하지 않는다.

필요 계약이 공급되면 기능 담당이 기존 packet-test-client-v5/API와 통과 flow를 재사용해 정상 로그인→선택→WORLD→정당한 법사 summon/실 actor 등록·drain→원 actor 선택 단계→동일 패널 명령→필요 Store/fresh→원 close 순서의 실행 가능한 caller를 준비한다. 클릭이 무패킷이면 단계로 기록하고 다음 실제 요청에 같은 UID가 반영되는지 확인한다. 실제 wire/current/발급/저장 상태를 조작하지 않으며 첫 실패 원문·부분 저장·정리를 보존한다. 이번 보고서는 시험 발주·공용 변경·큐 등록이 아니다.

검증: 입력 파일 존재와 SHA256, 부모 manifest pin 일치, bounded source 접점 확인. 새 제품 코드가 없어 compile/runtime 시험은 수행하지 않았다. 정확 실행 명령과 결과는 `evidence.json`에 기록했다. Reader/writer RELEASED.
