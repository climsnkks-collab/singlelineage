> 2026-10-15 사용자 결정: 기존 자체 단독앱은 폐기되었으며 아래 앱 구현·빌드·실행 계획은 과거 기록입니다. 현재 소스·실행본 삭제와 검증 사본 기록보존을 적용하며 기존 앱을 재사용하지 않습니다. 최신 방향은 [재조립 방식 검토](REASSEMBLY_STRATEGY_REVIEW_20261015.md)와 [현재 상태](ACTIVE_TASK.md)를 따릅니다.

# 원본 재이식: 첫 통합본 검증 기록

사용자 지시 “재이식 시작해”에 따라 전체 코드 감사에서 확인한 결함을 실제 C++ 코드에 반영했다. **첫 통합본은 검증했으며, 원본 전체 재조립은 미완료다.** 단독 기동·검사 통과를 원본의 버튼·움직임·모든 기능 동등성으로 확대하지 않는다.

## 실제 변경

| 범위 | 반영한 코드와 이유 | 확인 범위 |
|---|---|---|
| NPC 공격 표시·수명 | 정상 Controller의 승인된 공격 receipt가 기존 fixture의 `npc_enabled=false` 때문에 거절되던 경로를 분리했다. 원본 raw Attack/Breath 자원과 타이밍을 검증한 canonical admission만 허용하며, 추가 host AttackClock으로 피해·난수·반복 공격을 만들지 않는다. | 네 직업 공격 프레임·positive tail·메타데이터·원본 단계 복귀, 피격/Death, 플레이어 치명타와 Return, 저장/cold restore, Remove/새 lifetime respawn, legacy 선택, stale/rollback |
| 이벤트 적용 순서 | Inventory·SkillStatus·HealthChanged가 같은 배치 뒤의 최종 사망 값을 먼저 읽어 실제 Attack을 거절하던 결함을 수정했다. 생산 당시 DTO를 순서대로 적용하고, 마지막에 Ref/life/HP/MP/target을 대조한다. 생략된 summary 보완은 후속 full DTO가 작성하면 해제한다. | 실제 치명타 World event14와 Scene event6의 실패를 보존하고, 수정 후 전체 승인·cursor ack·Death 소유권·Return 확인. Death 없는 숨긴 최종 snapshot은 거절하고 candidate를 되돌림 |
| 제시된 화면과 입력 | Scene owner·Registry·lifetime·pose·카메라를 가진 immutable frame을 캡처했다. 전체 scratch composition·BitBlt·GdiFlush·EndPaint가 성공한 뒤 월드·인벤토리·상점·HUD 정보와 입력 권위를 함께 게시한다. 포커스/app/window activation/minimize/visibility 인자는 독립적으로 관리한다. | 생성 N+1과 실제 제시 N 구분, 상태 변경 뒤 재클릭 거절, 혼합/재귀 메시지, 부분/실패/빈/손상 이미지, HUD 게시, 실제 640×480/1920×1440 GDI 출력과 inverse, 실제 cold shop/quote/Buy·Sell 표시. 숨김 HWND와 소유 메모리 DIB 검사이며 원본의 실제 표시 cadence 인증은 아님 |
| 원본 무기 액션 기초 | 원본 component38/3C/40, action bank·variant cursor, Player의 +1/+4 선택과 원문 shared RNG primitive를 이식했다. numeric1008의 실제 기록 위치 +B8과 Start 기본 FPS +90=24를 분리했다. proto/wrapper 위치와 UID 폭을 구분하고 Wield→ShopAction→전역 helper→DefaultAction 순서를 typed effect plan으로 작성했다. | selector 15,090개, restart plan 17개 검사. **일반 제품은 실제 장착→원본 Wield 값/공유 RNG를 아직 공급하지 않으므로 기존 action1 정책을 사용한다. DefaultAction 실제 설치·네트워크 송신은 미이식이다.** |

원본 자료를 덮어쓰지 않고 새 D 소스에서 병합했다. 표시 기준 패키지와 비교해 기존 제품 코드 6파일 변경, 신규 코드/검사 10파일이다. 주요 코드는 [client_scene.cpp](D:/CodexArtifacts/single-lineage-reimplant-20261012-f38/verified-wave1/staging/tools/source_play_client/client_scene.cpp), [driver_impl.inc](D:/CodexArtifacts/single-lineage-reimplant-20261012-f38/verified-wave1/staging/tools/source_single_app_20261010/driver_impl.inc), [single_main.cpp](D:/CodexArtifacts/single-lineage-reimplant-20261012-f38/verified-wave1/staging/tools/source_single_app_20261010/single_main.cpp), [presented_frame.inc](D:/CodexArtifacts/single-lineage-reimplant-20261012-f38/verified-wave1/staging/tools/source_single_app_20261010/presented_frame.inc), [weapon_selector.cpp](D:/CodexArtifacts/single-lineage-reimplant-20261012-f38/verified-wave1/staging/tools/source_weapon_selector/weapon_selector.cpp), [wield_restart.cpp](D:/CodexArtifacts/single-lineage-reimplant-20261012-f38/verified-wave1/staging/tools/source_weapon_restart/wield_restart.cpp)에 있다.

## 실제 검증 결과

최종 Root 통합 실행은 strict `/W4 /WX /fp:strict /Brepro`, assertions 활성 상태에서 **5개 링크와 12개 native 실행을 모두 통과**했다. 헤더를 바꾼 최초 통합에서 실제 의존 소비자 28개를 포함해 33개 TU를 새로 컴파일했다. 최종 빌드의 재사용은 실제 compiler Source+Includes·현재 바이트·COFF를 대조했으며, Root가 2,378핀과 프로젝트 dependency 209개를 다시 확인했다. 이 수치는 원본 전체 함수 동등성 인증이 아니다.

| 검사 | 결과 |
|---|---|
| NPC canonical 공격·피격·사망·Return·cold corpse·Remove/respawn·rollback·legacy | 6,110개 PASS |
| Runtime 실제 제시 frame·입력·축척·상점/가격/수량/수명·실패 재시도 | 212개 PASS |
| 원문 액션 선택·variant·RNG primitive | 15,090개 PASS |
| Wield namespace·helper·DefaultAction 순서 계획 | 17개 PASS |
| Royal/Knight/Elf/Wizard 각각 남/여 | 8개 headless 기동·종료 PASS |
| 새 보존 패키지의 `--stage` 없는 자동 경로 탐색·단독 기동 | PASS |

공유 serial native lease를 독점 생성한 동안만 실행했고 다른 세션이 사용 중일 때는 대기했다. 실제 화면 표시창·하드웨어 입력·UAC·공식 클라이언트/로그인 실행은 0이다. controlled HP/snapshot와 숨김 HWND/memory DIB는 검사 자료다. 실제 상점 거래 성공이나 자연스러운 캐릭터 성장 전체를 이 검사로 주장하지 않는다.

검증한 실행 파일은 [새 product.exe](D:/CodexArtifacts/single-lineage-reimplant-20261012-f38/verified-wave1/staging/tools/source_single_app_20261010/bin/product.exe)이며 SHA256은 `feb1335b7b33f864e7b440d2082a281d62869e4361eecbf7e81b4d52375c0bcf`이다. 같은 패키지의 소스·데이터 1,550개는 최종 검증 소스와 동일하고, 이전 a5d597f2 실행 파일은 기존 고정본에 보존했다. 새 패키지에서도 전체 원본 UI·모션 완료를 기대할 수 있는 단계는 아니다.

근거: [최종 실행·원로그 핀](D:/CodexArtifacts/ri-f38-integrated-b5/RESULT.json), [Root 실제 build 검토](D:/CodexArtifacts/ri-f38-integrated-b5/ROOT_ACTUAL_BUILD_REVIEW.json), [패키지 핀](D:/CodexArtifacts/single-lineage-reimplant-20261012-f38/verified-wave1/PACKAGE.json), [자동 경로 기동](D:/CodexArtifacts/ri-f38-package-auto1/RESULT.json).

## 실패를 보존하고 교정한 항목

최초 NPC 검사기는 같은 배치의 Death가 `last_damage`를 0으로 덮는 것을 피해 없음으로 오인했다. 실제 HP 감소·공격 cycle·cause/lifetime·ack를 대조하도록 교정했다. 다음 치명타 실패는 실제 제품의 event 순서 오류였고 제품 코드를 수정했다. artificial corpse는 authority만 사망으로 바꾸고 Composite의 drop/share once 상태를 만들지 않아 검증에서 거절됐다. 실제 전투→사망·보상·drop→checkpoint→소유자 파괴→cold restore로 교체하고, 실제 50초 제거 뒤 60~119초 respawn에서 검사 상한을 유도했다.

화면 검사기의 Target 선택은 source geometry/Registry를 바꾸지 않을 수 있다. source 위치 유효성과 바뀐 canonical 권위를 구분해 실제 두 번째 클릭 거절을 검사했다. merchant UID0인 채 상점 mode만 대입한 검사도 실제 merchant guard의 정상 거절이었다. 실제 판매자 근처의 검증된 별도 snapshot과 cold restore·typed quote·열기·키·paint 경로로 검사했다. restart 검사기 1곳의 optional→bool C2664는 명시적 변환만 고쳤다. 제품 guard나 assertions를 완화하지 않았다. 이전 소스·실패·저장·원로그는 모두 보존했다.

## 다음 원본 재이식 범위

완료 기준은 [전체 코드 감사](ORIGINAL_REASSEMBLY_AUDIT_20261012.md)와 [원본 관련 동작 전체 이식 기준](ORIGINAL_FEATURE_PORT_20261012.md)을 유지한다.

1. 버튼 down/up/hover/pressed/capture/취소·포커스·전환, 캐릭터창 상태·프레임·timeline·callback·수명 전체. 다른 채팅이 추적하는 원본 UI/animation/full renderer 후보는 아직 검토·통합 전이며 여기서는 읽기만 했다.
2. 실제 장착 instance/catalog identity→원본 Wield bank 생산자, 원본 공유 RNG 획득·다른 소비자 순서, DefaultAction queue/Start/getter/cancel/release. 공용 아이템4와 원본4는 다른 아이템이다. 원본41/$70의 단검은 내용 대응 후보이며 장착 bank 증명은 아니다.
3. weapon bank/variant/alias/alternate/SPX·FPS override/+4D/속도·parameter·shadow 자원의 실제 load/draw/lifecycle. 기록한 214개 bank record와 2,592개 missing-group 언급은 누락 **파일 수**가 아니다.
4. frame annotation의 FX/사운드/End callback·해제, 원본 matrix/filter/color/alpha/dirty/visit/present·연속 표시와 frame 예산. 현재 own GDI 축척과 receipt 검증을 원본 렌더 전체 또는 깜빡임 해결로 확대하지 않는다.
5. 감사에서 남긴 캐릭터 저장 identity/슬롯, HP/Food/장비 bonus·회복, Elf 활, 자연 책 획득·나머지 마법/시전, 맵·NPC·콘텐츠 등 전체 누락. 현재 구현된 한 경로의 검사 성공으로 주변 기능을 생략하지 않는다.

원본·보관·기존 저장·이전 표시 패키지·worker 고정본·peer 소스는 변경하지 않았다. 전체 원본 재조립·전체 독립 게임 완료 표시는 하지 않는다.
