# 동료법사 actor 클릭 진입 v1

사용자의 새 요구는 테이밍 펫·서먼처럼 동료법사 actor를 클릭해 동료 설정 화면에 들어가는 것이다. 기존 v5의 단축키 진입과 별도 설정 상태를 만들지 않도록 `CompanionHost.open_from_actor_click`을 같은 패널 open 본문에 연결했다. 공용 파일과 현재 Test 선정판은 변경하지 않았다.

## 구현·정확 부모

- 부모: 수용 v5 `companion_host.py` SHA256 `de95a7766f7725670f9c76e03aeece7d58bac371b94cd39fb8664b89eafcc3cf`.
- 후손: `tools/local_original_session/companion_host.py` SHA256 `591c4b189a7d5b9b86943baf637a72cac5bb423fe4d84bfb6deb1ab24cce9846` (이 폴더 아래). 변경은 42행 추가·12행 교체다.
- 실제 server actor/current 재조회는 기존 `CompanionController.experience_participant()`를 재사용한다. actor UID·generation identity·owner writer·별도 법사 캐릭터 lease를 확인한 뒤 기존 panel과 command epoch를 공유한다. 잘못된 UID, 이전 generation, dismiss 후 클릭은 패널을 열지 않는다.
- 원래 단축키 경로는 공통 `_open_panel_locked`로만 옮겼다. 새 opcode, client callback, actor 발급, NPC 대화 전용 `4E43` 송신은 만들지 않았다.

## 최소 확인

`python -m py_compile` 후 v5 host fixture 5건과 새 current/다른 actor/퇴역 actor 2건이 통과했다. 검사는 private 후손을 우선 import하고 v5 추출본의 나머지 부모 모듈·기존 fixture를 사용했다. 이는 소스/수명 검사이며 원클라이언트 클릭·ATS 표시·패킷 시험이 아니다.

## 실제 플레이·시험 경계

정상 로그인→캐릭터 선택→WORLD→실제 법사 summon·server actor 등록/드레인 뒤, 플레이어가 화면의 법사 actor를 클릭한다. 클릭이 원래 무패킷인지, 어떤 actor 선택 callback을 제공하는지는 아직 미확인이다. 실제 클릭 source가 보유한 actor UID와 **그 세대**를 같은 writer의 `open_from_actor_click`으로 전달해야 한다. 이후 같은 설정 패널에서 follow/station/support 등을 선택하고 실제 저장·응답을 단계별로 판정한다. 무패킷 클릭이라면 그 단계를 시나리오에 기록하고 다음 명령의 target에 실제 법사 UID가 반영됐는지 확인한다.

펫/서먼 HUD 타입과 일반 NPC의 조건부 action15→`4E43` 경로는 확인됐지만 펫/서먼 클릭의 실제 callback·packet 여부는 확인되지 않았다. 원 ATS 창 create/callback/close와 UI thread owner도 미공급이다. 그러므로 `test_ready=false`: source-only 입력으로 큐에 넘길 수 있으나 클릭 기능 시험을 발주할 수 없다. 실제 actor/appearance·Factory도 별도 미완성이다. 다른 기능의 Test는 계속한다.
