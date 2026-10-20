# 현재 막힌 Drop/Popup/Get 접근의 돌파 상담

## 이번 상담의 범위

현재 구현 세션에서 반복 막힌 **원 Drop action→실제 Drop 요청→Ground 생성·소비→원 Get 및 정리**의 접근을 판단한다. 프로젝트 전체 노선, 다른 기능, 장기 복원 계획은 이번 질문에서 제외한다. 함수 하나나 포인터 읽기 하나의 진단으로도 축소하지 않는다.

## 목표와 현재 접근

원본 클라이언트가 원 선택·action·요청과 응답 소비를 수행하고, 기존 로컬 handler가 아이템 소유 및 저장을 처리하는 정상 Drop/Get을 완성하려 한다. bridge는 실제 현재 선택된 B와 owner·등록·frame을 확인하고, 현재 등록된 원 Drop callback의 body를 한 번 호출한다. 원 호출/소유 pair/point 인자·반환·frame 정리 전체를 보존하며 known ABI 결손은 아직 없다. 호출 반환은 backend 성공으로 취급하지 않는다.

원본 근거에는 수량과 별도의 operation mode에 따른 직접 송신/Popup 분기가 있다. 현재 source의 실제 수량이 하나면 직접 분기를 탈 수 있으므로, Host가 수량 하나에서도 무조건 Popup을 제출하던 두 후속 분기만 기존 backend wait로 이었다. 원 stage 시작시각과 기한, 실제 Store/session/GROUND/PLAYER/drain/pending/장비/frame/revision 판정은 보존했다. source가 다수수량인 경우의 Popup은 별도 미완료다.

## 확인된 경계와 반복 실패

1. 기존 다수수량 source: 실제 선택/원 Entry/Drop body가 정상 반환했지만 후속 Popup 어댑터는 필요한 callable이 NULL이라 거부했다. setter/readback/원 Submit/Drop handler/Ground/Get에는 도달하지 않았다. callable의 누락·잘못된 분기·시점·퇴역 중 어느 원인인지 아직 확정하지 못했다.
2. 정상 Q1 source: 보존된 저장과 분리된 새 Q1 초기 입력을 원 Store 생성·migration·restore와 같은 Factory 설정으로 확인했고, 실제 게임에서도 현재 B/수량 하나·point·원 Entry/body 정상 반환·원 frame release와 정리를 통과했다. 이어 backend wait에서 원 stage 기한이 끝났다. 실제 Drop/Get 요청은 관측되지 않았고 Store는 초기 PLAYER/READY 상태로 보존됐다. Ground/Get은 미완료다.
3. 다수수량과 Q1 실행의 일반 RX 종류·길이 순서는 같았다. 마지막 일반 RX 한 프레임을 Drop 송신이나 새 Q1의 효과로 연결할 근거는 없다. 프레임 정체도 현재 미확인이다.
4. 현재 Native가 출력하는 입력 subsystem mode 값은 원 Drop 분기의 operation mode 값과 다른 위치/의미다. 따라서 그 값이 zero라는 사실로 원 직접 송신 분기 진입을 입증할 수 없다. 실제 operation mode 생산자·필수 상위 Drop caller와 현재 등록 callback의 관계가 열린 핵심이다.

backend handler/Store/session 왕복은 실제 handler와 명시 Native IO fixture에서 별도로 검증됐지만, 이것은 원 클라이언트의 실제 Drop 송신이나 Ground→원 Get 소비를 증명하지 않는다. 최초 입력 검사가 Q1을 거부하던 시험 조건은 이미 수정돼 현재 실패 위치가 원 Entry 반환 이후로 이동했다. 같은 초기화·입력·frame 보호·정상 반환 검사를 다시 반복하지 않는다.

## 이미 시도한 것과 지킬 경계

- 원 whole-call, 실제 선택/owner/point/frame 보존과 original cleanup을 연결했다. 과거 보호/수명·초기 입력 실패가 이번 실행의 첫 실패는 아니다.
- 원 수량 하나 분기를 보존하는 Host 후속 변경과 coherent Q1 입력으로 실제 시도했다. Q1은 현재 source 수량 하나이며, 다수 스택 중 한 개를 인위적으로 요청한 것이 아니다.
- NULL callback을 가짜로 채우거나 operation mode/상태를 강제로 쓰지 않았다. Popup을 추측 호출하거나 dispatcher 재호출, 임의 protocol sender, 기한 연장, 같은 후보의 재실행은 하지 않는다.
- 기한 실패 후 기존 Quit admission이 정상 반환된 어댑터의 정리 상태를 보존하지 못해 정상 Quit에 진입하지 못했다. 실제 강제 정리를 정상 종료로 보고하지 않는다. 별도 통합 담당이 같은 동작의 종료 수명을 보완하며 다음 기능 시험에 합친다. Quit만 확인하는 별도 게임은 만들지 않는다.

## 판단할 대안

A. 현 등록 Drop entry를 유지하고, 정상 원 action이 준비해야 하는 operation mode/producer·owner/caller 전제를 연결한다. 현재 body가 정말 해당 원 Drop action의 충분한 경계인지 입증해야 한다.

B. 필수 전제를 자연스럽게 소유하는 가장 가까운 원 상위 UI Drop action으로 이동한다. 후보의 입력·등록·한 번의 호출·부작용·소유와 종료 계약이 확인될 때만 선택한다.

C. 원 필수 caller/callee의 경계를 다시 잡아 현재 단위에서 실제 요청 생산까지 포함한다. 결과를 맞추기 위한 강제 상태/가짜 callback/별도 sender는 대안으로 사용하지 않는다.

## Pro에 묻는 판단

- 이 실패 패턴에서 현재 접근을 계속하는 것이 타당한가? 가장 먼저 의심하고 검증할 잘못된 가정은 무엇인가?
- A/B/C 중 돌파 가능성과 변경 위험을 기준으로 우선순위를 정하고, 선택을 가를 최소 원 계약·관측 근거를 제시해 달라.
- 다음 작업 단위를 원 action 준비→원 호출→실제 송신→서버/Ground→원 Get·정리까지 어떻게 묶어야 같은 미세진단을 반복하지 않는가?
- 그 변경을 판정할 다음 최소 실제 실행 하나에서 무엇을 성공·실패로 볼 것인가? 기존 성공은 재사용하고, 현재 첫 미확인 경계를 바꾸지 못하는 재기동·새 collector는 제안하지 말라.
- 제공된 사실만으로 확정할 수 없는 원인과, 추가 증거가 있어야 선택할 대안을 구분해 달라.
