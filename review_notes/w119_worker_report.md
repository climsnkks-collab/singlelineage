vel_tests.py`, `world_polymorph_tests.py` — 새 계약·시험 데이터·격리 수정.
- `world_feature_magic.py`, `world_magic_status_feedback_tests.py` — 원본 문자열 ID로 상태 발생·해제 안내 게시 및 회귀 검증.
- `companion5_ats_window.hpp` — 복제돼 남는 회복 아이콘을 기존 remove/release 경로로 정리.
- `build-nopatch.cmd` — 기존 검증된 GLFW 입력 빌드 옵션 포함.
- `verify_ncg_waitonly.py`, `status_feedback_scenario.py`, `run_verify_ncg_waitonly.ps1` — observer 수정, 빈칸 식별, 상태 이상 시나리오.
- `run_verify_fresh_capture.ps1` — 기존 캡처 삭제 제거.
- `launcher.py`, `start-manual-play.ps1` — 최종 핀 갱신, PS1 작업 경로·BOM 수정.

미확인은 **텔레포트 SPR169의 실제 재생·수명 연결**, 일부 run의 정상 Quit입니다. 해당 run은 강제 정리 한계를 그대로 남겼습니다. 단위 시험 skip 2개는 별도 opt-in 동료·펫 통합시험입니다.

최종 **LC/LC.guard 0, 12000·14030 LISTEN 0**, 원래 DLL 슬롯과 Capture 12개 복원을 확인했습니다. 사용자 저장 변경·보이는 창 실행·커밋은 없었습니다.
tokens used
815,683
**텔레포트 시각효과 1건이 미확인으로 남았습니다. b~g는 각 시나리오 범위에서 통과했습니다.**

1. 단위 시험: 승인하신 두 모듈을 제외한 **2,461개, 실패 0·오류 0·skip 2**. 이후 서버 수정에 대한 최종 관련 **201개도 실패 0**입니다. [전체 로그](/C:/Users/Chansol/Documents/ChatGPT/싱글리니지/_work/tmp/unittest_fixture_contract_excluding_slow_fixed_20261030.log) · [최종 관련 로그](/C:/Users/Chansol/Documents/ChatGPT/싱글리니지/_work/tmp/headless-20261030/final-status-teleport-tests.log)
2. 핀 갱신·검사 통과. `$pins`, `bridgeCandidateHash`, launcher 제품 해시와 launcher 핀을 맞췄고 PS1은 UTF-8 BOM을 유지했습니다. 두 핀 오류 모두 없었습니다. [검사 로그](/C:/Users/Chansol/Documents/ChatGPT/싱글리니지/_work/tmp/manual_pins_check_20261030-final.log)

최종 DLL SHA256:
`13ed7d7dbaa99fc0620b4321cdc745b6094ae7a3e61b6bab58131ebf40a63695`

모든 run은 `work/local_original_session/runs/` 아래입니다. 캡처를 직접 열어 판정했습니다.

| 항목 | 판정·실행 폴더 | 대표 캡처 |
|---|---|---|
| 3a | **미통과: 효과 UNKNOWN**. 버프·시간 복원 확인. `glfw135-reconnect-final-20261030-a`, `glfw137-teleport-dungeon-20261030-a`¹ | [초록 시간](/C:/Users/Chansol/Documents/ChatGPT/싱글리니지/work/local_original_session/runs/glfw135-reconnect-final-20261030-a/play-reconnect-buff-tooltip-2.png) · [용기 시간](/C:/Users/Chansol/Documents/ChatGPT/싱글리니지/work/local_original_session/runs/glfw135-reconnect-final-20261030-a/play-reconnect-buff-tooltip-3.png) · [텔레포트 직후](/C:/Users/Chansol/Documents/ChatGPT/싱글리니지/work/local_original_session/runs/glfw137-teleport-dungeon-20261030-a/after-play-use-teleport.png) |
| 3b | **통과**. map0→말섬 던전 1층, 맵 정상. `glfw147-talkscroll-original-order-final-20261030-b` | [이동 전](/C:/Users/Chansol/Documents/ChatGPT/싱글리니지/work/local_original_session/runs/glfw147-talkscroll-original-order-final-20261030-b/after-talkscroll-double-click.png) · [이동 후](/C:/Users/Chansol/Documents/ChatGPT/싱글리니지/work/local_original_session/runs/glfw147-talkscroll-original-order-final-20261030-b/after-talkscroll-first-hunting-click.png) |
| 3c | **통과·전 단계 OBSERVED**. 화면 밖 동료도 Ctrl+E 열닫. `glfw140-pet-final-order-20261030-c` | [근처 창](/C:/Users/Chansol/Documents/ChatGPT/싱글리니지/work/local_original_session/runs/glfw140-pet-final-order-20261030-c/pet-toggle-held-menu-before-close.png) · [원거리 조건](/C:/Users/Chansol/Documents/ChatGPT/싱글리니지/work/local_original_session/runs/glfw140-pet-final-order-20261030-c/pet-toggle-remote-before-key.png) · [원거리 창](/C:/Users/Chansol/Documents/ChatGPT/싱글리니지/work/local_original_session/runs/glfw140-pet-final-order-20261030-c/pet-toggle-remote-menu-open.png) |
| 3d | **통과**. 양수 MP 바·서버/native 값 일치. `glfw141-head-bags-gear-final-20261030-df` | [머리 MP](/C:/Users/Chansol/Documents/ChatGPT/싱글리니지/work/local_original_session/runs/glfw141-head-bags-gear-final-20261030-df/companion-head-mp-world-and-party.png) · [후속 화면](/C:/Users/Chansol/Documents/ChatGPT/싱글리니지/work/local_original_session/runs/glfw141-head-bags-gear-final-20261030-df/owner-bag-initial.png) |
| 3e | **통과**. 회복 설정 저장·재열기, Reset·드래그 이탈. `glfw133-ats-clone-fix-20261030-e`, `glfw142-ats-heal-final-20261030-e` | [HP 30%](/C:/Users/Chansol/Documents/ChatGPT/싱글리니지/work/local_original_session/runs/glfw142-ats-heal-final-20261030-e/after-companion-heal-percent30.png) · [재열기](/C:/Users/Chansol/Documents/ChatGPT/싱글리니지/work/local_original_session/runs/glfw142-ats-heal-final-20261030-e/after-companion-heal-reopen-tab.png) · [드래그 후 빈칸](/C:/Users/Chansol/Documents/ChatGPT/싱글리니지/work/local_original_session/runs/glfw133-ats-clone-fix-20261030-e/ats-clear-heal-dragoff-confirmed.png) |
| 3f | **통과**. 상세 툴팁·빈칸 hover·재열기, 크래시 없음. `glfw141-head-bags-gear-final-20261030-df` | [가방 상세](/C:/Users/Chansol/Documents/ChatGPT/싱글리니지/work/local_original_session/runs/glfw141-head-bags-gear-final-20261030-df/self_bag-hover-after.png) · [빈 목걸이 hover](/C:/Users/Chansol/Documents/ChatGPT/싱글리니지/work/local_original_session/runs/glfw141-head-bags-gear-final-20261030-df/companion_equipment_empty-hover-after.png) · [장비 재열기](/C:/Users/Chansol/Documents/ChatGPT/싱글리니지/work/local_original_session/runs/glfw141-head-bags-gear-final-20261030-df/reopened-companion_equipment-hover-after.png) |
| 3g 마비 | **통과**. 채팅·아이콘·회색, 차단 중 요청/교정 0·좌표 고정, 해제 후 이동. `glfw143-paralyze-final-20261030-g` | [마비](/C:/Users/Chansol/Documents/ChatGPT/싱글리니지/work/local_original_session/runs/glfw143-paralyze-final-20261030-g/status-active-before-move.png) · [입력 후 고정](/C:/Users/Chansol/Documents/ChatGPT/싱글리니지/work/local_original_session/runs/glfw143-paralyze-final-20261030-g/status-active-still-held.png) · [해제 후 이동](/C:/Users/Chansol/Documents/ChatGPT/싱글리니지/work/local_original_session/runs/glfw143-paralyze-final-20261030-g/status-released-after-move.png) |
| 3g 기절 | **통과**. 안내·아이콘·이동 잠금/해제. `glfw144-stun-final-20261030-g` | [기절](/C:/Users/Chansol/Documents/ChatGPT/싱글리니지/work/local_original_session/runs/glfw144-stun-final-20261030-g/status-active-before-move.png) · [해제 후 이동](/C:/Users/Chansol/Documents/ChatGPT/싱글리니지/work/local_original_session/runs/glfw144-stun-final-20261030-g/status-released-after-move.png) |
| 3g 독 | **통과한 범위: 안내·HP 색·자연 만료**. `glfw146-poison-solo-final-20261030-g` | [독 활성](/C:/Users/Chansol/Documents/ChatGPT/싱글리니지/work/local_original_session/runs/glfw146-poison-solo-final-20261030-g/status-poison-active.png) · [만료 후](/C:/Users/Chansol/Documents/ChatGPT/싱글리니지/work/local_original_session/runs/glfw146-poison-solo-final-20261030-g/status-poison-cleared.png) |

¹ 3a는 중간 서버 Source의 범위별 관측입니다. 미입증 송신 순서 변경은 복원했으며, 최종 원복 Source 전체 통과로 합산하지 않았습니다.

수정 파일과 요지는 다음과 같습니다.

- 시험 fixture 5개: `world_maps_tests.py`, `accessory_packet_tests.py`, `stack_merge_tests.py`, `world_delevel_tests.py`, `world_polymorph_tests.py` — 새 계약·시험 데이터·격리 수정.
- `world_feature_magic.py`, `world_magic_status_feedback_tests.py` — 원본 문자열 ID로 상태 발생·해제 안내 게시 및 회귀 검증.
- `companion5_ats_window.hpp` — 복제돼 남는 회복 아이콘을 기존 remove/release 경로로 정리.
- `build-nopatch.cmd` — 기존 검증된 GLFW 입력 빌드 옵션 포함.
- `verify_ncg_waitonly.py`, `status_feedback_scenario.py`, `run_verify_ncg_waitonly.ps1` — observer 수정, 빈칸 식별, 상태 이상 시나리오.
- `run_verify_fresh_capture.ps1` — 기존 캡처 삭제 제거.
- `launcher.py`, `start-manual-play.ps1` — 최종 핀 갱신, PS1 작업 경로·BOM 수정.

미확인은 **텔레포트 SPR169의 실제 재생·수명 연결**, 일부 run의 정상 Quit입니다. 해당 run은 강제 정리 한계를 그대로 남겼습니다. 단위 시험 skip 2개는 별도 opt-in 동료·펫 통합시험입니다.

최종 **LC/LC.guard 0, 12000·14030 LISTEN 0**, 원래 DLL 슬롯과 Capture 12개 복원을 확인했습니다. 사용자 저장 변경·보이는 창 실행·커밋은 없었습니다.
