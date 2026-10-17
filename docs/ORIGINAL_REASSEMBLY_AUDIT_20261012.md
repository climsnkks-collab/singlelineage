# 원본 재조립 기준과 전체 제품 코드 감사

현재 제품은 사용자가 요구한 원본 클라이언트 전체 재조립 기준을 충족하지 않는다. 원본 자원과 일부 복원 수식을 새 단독 호스트에 연결했지만, 입력 상태·애니메이션·프레임 이벤트·캐릭터 식별·콘텐츠 소비 경로에는 대체 구현과 누락이 남아 있다. 원본과 관련된 전체 함수와 상태 전이를 이식하고 동작을 대조해야 한다.

2026-10-12 사용자의 최신 지시는 기능의 일부만 구현하거나 임의로 적당히 채우지 말고, 지금까지 작성한 전체 제품 코드와 프레임·버튼 움직임 등 관련 동작을 원본에 맞추라는 것이다. 이 기준을 [AGENTS.md](../AGENTS.md)와 [구현 완료 계획](IMPLEMENTATION_COMPLETION_PLAN.md)에 반영했다. 단독 기동과 자체 검사 통과는 중간 검증이며 전체 완료 기준이 아니다.

## 검토한 제품과 범위

기준본은 사용자가 확인한 실행 파일 `a5d597f2d481f245b6a4a17105e2f8599e48b0ec6b8170814490bf2c9209ffdc`와 `D:/CodexArtifacts/single-lineage-corrected-icons-1301bb579ebb/staging`이다. 진행 중인 Source5와 새로운 원본 UI 조사 결과를 이 실행본의 기능으로 합산하지 않는다.

| 범위 | 현물 목록 | 검토 기록 |
|---|---:|---|
| UI·시작·입력·HUD·선택 데이터 | 47파일 / 7,343줄 | [UI 감사](../work/original_reassembly_audit_20261012/ui/REPORT.md) |
| 모션·액션·프레임·렌더 자원 | 52파일 / 4,071줄 | [모션 감사](../work/original_reassembly_audit_20261012/motion/REPORT.md) |
| 게임·상태·아이템·스킬·지도·저장 | 107파일 / 34,969줄 | [게임 감사](../work/original_reassembly_audit_20261012/gameplay/REPORT.md) |
| 전체 제품 코드 후보 | 206파일 / 46,383줄 | [파일별 목록](../work/original_reassembly_audit_20261012/root/CURRENT_CODE_INVENTORY.csv) |

제품 코드 후보에는 패키지에 보존된 이전 소비자도 포함했다. 현재 수동 작성 본문 171개는 전체 본문과 제어 흐름을 검토했고, 생성 자료 35개는 구조·참조·소비 코드와 원문 데이터 검토를 구분했다. 큰 client_scene.cpp/h와 이전 client.cpp는 [독립 전량 검토](../work/original_reassembly_audit_20261012/ui/client_scene_review/FULL_BODY_REVIEW.json)로 보완했다. 원본 모든 함수의 의미 대조와 현재 코드 본문 검토는 별개다. 수동으로 모든 생성 상수의 원본 의미를 대조한 것처럼 표시하지 않는다. 각 ledger의 실제 검토 수준을 따른다. Root가 206개 파일 신원·누락 0, 보완 검토의 연속 구간·해시, 152개 현재 코드 인용의 줄과 신원을 다시 확인했다. [검토 범위 확인](../work/original_reassembly_audit_20261012/root/REVIEW_COVERAGE_VERIFIED.json), [인용 확인](../work/original_reassembly_audit_20261012/root/CURRENT_FINDING_CITATIONS_VERIFIED.json)

패키지의 테스트/CLI 60개와 작성·동결 도구 108개는 별도 목록이다. 프로젝트 `tools/`·`work/`의 과거 분석·검사·복사본 경로도 별도 [전체 경로 목록](../work/original_reassembly_audit_20261012/root/WORKSPACE_CODE_PATHS.txt)에 남겼다. 이 보존 자료 전체의 함수 의미를 검토했다는 뜻은 아니다.

실제 빌드의 재사용 객체 96개와 product-main의 `sourceDependencies`를 읽어 실제 Source와 Includes를 현재 패키지에 대조했다. 현재 코드 199개가 그 입력에 연결되고 바이트 차이는 0이다. 나머지 7개는 이전 client/input_state/profile/authority/rules 파일이다. 최신 qualification의 일부 입력 목록만 보고 모듈이 미링크라고 판단하지 않았으며, 별도 보존 stage에서 컴파일된 commerce/travel/normal_visual/triangles의 실제 본문까지 재확인했다. [빌드 소비 근거](../work/original_reassembly_audit_20261012/root/ACTUAL_BUILD_SOURCE_COVERAGE.json)

이 정적 감사에서 제품 코드 변경·새 컴파일·native 실행·화면 입력은 하지 않았다. 자체 검증 수나 과거 성공 기록을 원본 동등성으로 재해석하지 않는다.

## 확인된 차이와 필요한 이식 범위

각 감사의 FINDINGS.json에는 현재 경로·정확한 줄·원본 자원 또는 함수 근거·일반 조작의 도달 경로·미확인 경계·수정과 검증 범위를 기록했다.

| 영역 | 현재 구현의 차이 | 원본에 맞춰 복원할 전체 경로 |
|---|---|---|
| 버튼과 입력 | down 즉시 실행, 눌림 자원과 up·hover·cancel·capture 상태 미연결 | 원본 control 생성·enable·focus·입력 상태·클릭 callback·취소·화면 전환·해제 |
| 선택·생성 초상화 | 원본 FX를 PNG 한 장으로 대체 | 초기 state·frame, state 전환, timeline·scheduler·texture 소비·완료 callback·자원 수명 |
| 캐릭터 선택과 저장 | 세 슬롯은 세션 로컬; 같은 선택값의 다른 이름이 같은 저장 프로필로 연결 | 원본 catalog·character UID·생성/선택/삭제 요청과 응답·preview·단독 backend의 고유 저장 식별 |
| 삭제·주사위·이름 입력 | 버튼 caller 누락, 이름 길이와 EDIT는 호스트 정책 | 실제 등록된 callback·유효 상태·이름 validation·IME·focus·요청 실패와 복구 |
| 채팅·메뉴·단축칸 | 정적 표시가 많고 주문 입력은 고정 F1 | control·슬롯 DTO·배치/선택·키와 포커스 routing·명령·응답·tooltip·영속 |
| 패널과 목록 | 일부 패널만 고정 표시; 드래그·handle·wheel·상세 정보 누락 | panel factory·parent transform·clip·scroll·drag·item/장비/능력치 consumer·닫기와 해제 |
| 무기와 액션 | 공격 action1 고정, alternate/weapon/special/shadow 모드 거부 | 장착 ItemID의 원본 namespace·selector·resource·FPS/속도 producer·action 시작/전환/완료 |
| 프레임 이벤트 | annotation·End·시체 이벤트가 metadata로 끝남 | 실제 발생 프레임·event dispatch·FX/소리·완료 callback·중단과 해제 |
| NPC 공격 표시 | 정상 canonical 경로는 npc_enabled=false를 유지해 accepted Attack의 start_npc가 거절됨 | canonical 생성/복원·receipt·힌트·액션 admission·tick·render·피격/사망/해제를 추적하고 이전 fixture 전용 switch와 분리 |
| 표시한 월드의 클릭 | hit cache는 Scene::render에서 publish하고 실제 paint된 world serial과 별도 연결이 없음 | render→실제 present/paint→입력 좌표/actor lifetime 연결·전환/실패/resize. 화면과 cache 불일치의 실제 메시지 순서 검증 필요 |
| 스케줄러·이동 | 일부 복원된 계산과 호스트 scheduling을 조합 | 실제 flags·clock 생산·속도축·Next/queue·wrap/commit·피격/사망 중단·cold/restore |
| 카메라·깊이·표시 | 호스트 follow/clamp, 제한된 SPX 처리와 painter 정렬 | 원본 camera setter·행렬·FOV·visit/draw/submit/present·occlusion·shadow·filter·색/alpha·resize/focus |
| 스킬·장비 | 데이터 목록과 실제 effect capability가 다르고 장비에 따라 시전 경로 제한 | 원본 skill/item 역할·대상·원가·효과·buff·애니메이션·UI 선택·실패 응답의 전체 연결 |
| 월드와 게임 상태 | 제한된 actor/map provider와 별도 단독 규칙 | 원본 actor/template/resource 대응·지도 loading/streaming·AI/전투/성장·회복/food/상태 consumer |

정상 canonical NPC 공격 표시의 비활성 guard는 현재 소스의 전체 생성·Spawn/restore·hint·start·tick·render·death 경로에서 확인한 정적 통합 오류다. 피해/사망의 canonical 검사 성공을 NPC 공격 표시 성공으로 볼 수 없다. 실제 paint와 hit cache 문제는 코드의 게시 경계가 분리됐다는 사실을 확인한 것이며, 사용자에게 잘못된 대상이 선택되는 실제 재현 검사는 아직 하지 않았다. [추가 Scene 감사](../work/original_reassembly_audit_20261012/ui/client_scene_review/FINDINGS.json)

같은 선택값 슬롯의 저장 공유는 저장이 켜진 경로의 정적 코드에서 확인했다. 사용자에게 표시했던 `--no-save` 실행에서는 그 저장 공유가 발생하지 않는다. 이름만 profile 해시에 넣는 수정으로 원본 catalog·UID·생성·선택·삭제 흐름 전체를 완료 처리하지 않는다. 기존 저장은 보존한다.

원본 raw에 버튼·아이템·주문·액션이 있다는 사실과 기능이 실행된다는 사실도 구별한다. 예를 들어 pressed 이미지가 확인되었다고 해서 원본이 release에서 실행하는지, drag-out 취소와 capture를 어떻게 처리하는지까지 확인된 것은 아니다. 확인하지 않은 runtime 규칙을 일반적인 UI 관행으로 채우지 않는다.

## 원본 근거와 완료 판단

원본 CONTROL의 현재 SHA256 `9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af`를 재확인했다. 원본 CSB·SPR·SPX·data와 복원된 함수의 바이트 근거는 감사별로 연결했다. 동일 바이트는 해당 근거의 신원이며 전체 호출 경로의 의미 동등성은 아니다. 현재 진행 중인 선택·생성/animation/render 원본 조사도 간접 호출과 caller/producer가 열려 있으므로 전체 이식 완료로 표시하지 않는다.

기능을 완료 처리하려면 다음 연결이 모두 필요하다.

1. 원본에서 기능의 진입·입력 상태·내부 caller/callee·간접 호출·resource/field producer·전환·취소·해제를 추적한다.
2. 각 원본 동작을 실제 제품 소비 코드에 대응시킨다. 원본 클라이언트에서 빠진 분기나 호스트 대체는 열린 항목으로 유지한다.
3. 고정 소스의 실제 빌드와 일반 사용자 입력 경로를 연결해 검증한다. fixture 전용 API에서만 성공한 기능은 일반 플레이 구현으로 합산하지 않는다.
4. 원본과 같은 입력·상태·경과 시간을 공급해 frame/texture/position·버튼 상태·callback/event 순서와 전환/취소/해제를 비교한다. 실제 연속 표시·resize·focus·재기동까지 해당 범위에 포함한다.
5. 미확인 producer·간접 호출·원본 동작·미지원 콘텐츠를 별도로 공개하고, 그 항목이 열려 있는 동안 전체 원본 재조립 완료를 주장하지 않는다.

원본 resource의 `+0x90` 필드와 literal 90FPS, 애니메이션 C/FPS와 서버 공격 간격은 같은 개념이 아니다. 원본 producer가 확인되지 않은 FPS나 타이밍을 숫자 추측으로 교체하지 않는다.

이전 사용자가 승인한 공개 서버 참고는 출처 있는 별도 단독 backend 정책이다. 그 승인은 frontend의 상태·버튼·프레임·자원 소비를 임의로 바꿀 허가가 아니다. 확인할 수 없는 원본 서버 값은 계속 차이로 명시하며 원본 동일로 표시하지 않는다.

## 통합 순서

현재 [원본 기능 전체 이식](ORIGINAL_FEATURE_PORT_20261012.md)의 선택/생성 흐름·애니메이션·렌더 조사에 이 감사의 누락 목록을 연결한다. 우선 버튼과 초상화의 state/clock/consumer 및 캐릭터 identity를 같은 시작 흐름 안에서 복원한다. 다음으로 HUD·패널·단축칸과 무기·스킬·프레임 이벤트·월드 소비를 같은 기준으로 확장한다.

원본 근거가 확보된 primitive와 parser·자산·수식은 재사용하되, 새 호스트의 대체 동작을 원본이라고 재명명하지 않는다. 기존 원본·보관·저장·고정 빌드와 병행 작업을 유지하고, 새 이식 소스에서 관련 흐름 전체를 검토·검증한다.

전체 원본 재조립과 전체 게임 완료는 아직 미완료다.
