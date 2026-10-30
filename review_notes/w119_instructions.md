<task>
싱글리니지 (작업 폴더 C:\Users\Chansol\Documents\ChatGPT\싱글리니지). 사용자가 아침에 직접 플레이 테스트한다. 그 전에 오늘 바뀐 기능 전부를 실제 플레이하듯 헤드리스 시나리오로 돌리고 단계별 캡처로 확인해 둔다. 순서대로 한다.

1. 단위 시험 실패 3건 수정
   tools/local_original_session/world_maps_tests.py:199 test_same_and_cross_map_replay_speed_item_and_spell_icons_without_state_change
   AttributeError: 'types.SimpleNamespace' object has no attribute '_world_magic_replay_invisible'
   (world_feature_magic.py:704 _world_magic_after_relocate 가 새로 부르는 메서드를 시험 fixture 의 ctx 가 모름)
   시험 fixture 를 새 계약에 맞춘다. 운영 코드에 getattr 가드를 넣지 않는다.
   그 다음 python -m unittest 로 tools/local_original_session 의 *_tests.py 전체(약 1138개)를 돌려 0 실패 확인.

2. 핀 갱신
   오늘 DLL 이 다시 빌드됐다. work/local_original_session/manual-play/start-manual-play.ps1 의 $pins 와 bridgeCandidateHash,
   launcher.py PRODUCTS['sibling-manual-play-companion-nopatch'] 의 DLL 해시를 현재 파일 sha256 으로 맞춘다.
   launcher.py 를 고쳤으면 start-manual-play.ps1 안의 launcher.py 핀도 갱신. (ps1 은 utf-8-sig 유지)
   검증: start-manual-play.ps1 의 핀 검사 부분만 돌려 PLAY_SOURCE_CHANGED / CP69_BRIDGE_REQUIRED 가 없는지. 게임 자체는 띄우지 않는다.

3. 헤드리스 플레이 시나리오 (work/local_original_session/companion-bridge/run_verify_fresh_capture.ps1, verify_ncg_waitonly.py)
   한 번에 게임 하나만. 각 실행마다 단계별 캡처를 직접 열어 보고 판정한다. 결과가 기대와 다르면 원인을 고치고 다시 돌린다.
   a. play_smoke → play_smoke_reconnect: 물약(용기·초록) 먹고 재접속 후에도 버프 아이콘·남은시간 유지, 순간이동 주문서 텔레포트 후에도 유지, 텔레포트 이펙트 보임.
   b. talkscroll_teleport_capture: 말하는 두루마리로 말섬 던전 1층 이동, 맵 깨짐 없음.
   c. pet_window_toggle: Ctrl+E 로 동료 창 열기/닫기, 동료가 멀리(화면 밖) 있을 때도 열림. 남아 있는 observer 문제(matches=0, 단일 노드 판정 실패)를 고쳐 시나리오가 OBSERVED 로 판정되게.
   d. companion_head_mp: 동료 머리 위 MP 바가 0 이 아닌 값으로 보이는지 (MP 회복 장비 착용 상태에서 충분히 기다리거나 시험 전용 시작 MP 로).
   e. ats_window_heal, ats_window_reset_dragoff 회귀.
   f. 장비 창 빈 칸에 마우스 올려도 클라이언트가 안 꺼지는지 (오늘 0x40982 크래시 고친 것) + 가방 아이템 hover 상세 툴팁.
   g. 상태 이상 시나리오 신규: 기사에게 마비(가능하면 석화·기절·독도)를 서버 시험 경로로 걸고 캡처로 확인.
      - 채팅창 안내 문구, 디버프 아이콘, 캐릭터 색 변화, 이동 입력을 넣어도 실제로 안 움직이고 되돌아가는 떨림도 없어야 함, 풀린 뒤 다시 이동 가능.
      사용자가 직접 지적한 문제라 꼭 화면으로 확인한다. 안 되면 원인을 고친다 (서버/DLL).
</task>
<scope>
수정 가능: tools/local_original_session/** (서버·시험), work/local_original_session/companion-bridge/** (시나리오, DLL 소스·빌드), start-manual-play.ps1, launcher.py 핀, validation-profiles/manual-test-knight (백업 후만).
건드리지 말 것: manual-user-play 저장 데이터, hunt_bot 실행, 보이는 창 실행, 커밋.
</scope>
<rules>
- 헤드리스만. 게임은 한 번에 하나. 좌표는 HEADLESS_COORDINATE_RULES.md 의 검증된 방법만 쓴다 (먼저 읽는다).
- DLL 에 인라인 훅 금지 (원본 함수 호출·콜백 교체·노드 조작만). 새 guard·중복 검사 추가 금지.
- 기준은 리니지 클래식 클라이언트 동작. 
- 임시 파일은 _work/tmp. 끝나면 LC 프로세스와 12000/14030 포트 정리, DLL 바꿨으면 2번 핀 다시 갱신.
- 막혀도 다른 항목은 계속 진행하고 막힌 것만 보고.
</rules>
<output_contract>
- 항목별(1, 2, 3a~g): 통과/실패, 실행 이름(runs 폴더), 판정에 쓴 캡처 경로 2~3개
- 고친 파일과 요지
- 최종 단위 시험 결과 숫자, 최종 DLL sha256 과 핀 갱신 여부
- 확인 못 한 것
</output_contract>
