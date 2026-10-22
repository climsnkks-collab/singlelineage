# NPC 두 적 기능 접근 상담 — 실제 선택 소스 검토 요청

원본 클라이언트+자체 로컬 서버의 명시 LOCAL 두 적 순차 교전이다. 기존 원본/저장/공용 소스를 보존한다. 기능 메인이 상담하고 현재 구현도 소유한다. 웹 Pro의 동료 법사 구현과 별도이며 여기서는 법사/전투수치/프로젝트 노선 변경을 다루지 않는다.

## 완료와 반복 실패

- NPC 한 마리의 원 Attack→지속 추적/정상 player Move→원 NPC MOVE/엄격한 현재 pose/idle→도착 뒤 새 typed 반격 HP17→16·Attack/HP drain 성공. 선택 해제의 원 SourceRestart→ACK drain→선택 life/goal 정리도 성공.
- 연속 정상 Move 두 번→최신 현재 player goal로 교체→NPC 도착→그 이후 새 반격도 실제 성공했다. 이를 재생하지 않는다.
- 두 적 source는 player1/enemy2+명시 LOCAL enemy3, 같은 SPR56/template0/map·enemy2 x+1/samey, 각 NPC Hp(2,2)/Hit(True,1). 플레이어 HP20과 별개다. single/default는 보존한다.
- 395: 반복 반격 constructor의 len(spawns)==1 거부. v19에서 원single 또는 명시ordered2,3만 허용. 새입력/가짜dependency/새정책은 없다.
- 395-v2: world/select route가 ENTER_ACK1+world3+NPC2=6을 반환하지만 _send의 일반상한MAX_CHARACTERS3+2=5에서 거부.
- 395-v3: v20의 samecurrent/sourceowned exact6 helper를 _send에 연결해 위 guard를 통과했으나 Canonical BatchStore.open_projection_read의 frame tuple<=5가 다시 거부. WAIT_LAND, 실제Attack0/두 NPC 효과0/Restart미도달. 단계가 앞으로 갔지만 두 적의 완결world 진입 성공은 아직 없다.

## 현재 접근과 소스

source-manifest.json의 exact bytes가 실제395-v3 선정이다. broker.py는 v20(3d994575...), canonical_batch.py는 core1844456802...다. 최신 trusted inputs는934c784c...이며 원JSON 단일 Features를 cold issue에서만 immutable 두 spawn/HP rows로 복제하고, 기존 CharacterStore.snapshot UID 집합을 단1cold경계에서 소비해3충돌을 거부한다. 현재 namespace Root defaultNone이며 영구UID allocator/동료UID 선점은 아니다.

UID별 stable frame component/mover/generation/HP/tombstone/respawn 정리를 연결하고 단1 active target/goal을 유지한다. A→B 원 accepted/drained 입력에서 A lease/goal을 퇴역한 뒤 B를 발급한다. source_uid는 Context/Life/lethal까지 전달한다. A만 respawn하면 B의 frame/generation/HP/tombstone/현재intent를 보존한다. 공개 receipt의 old global edge 권위는 그대로 퇴역하며 historical HP/currentNPC 검사는 그 권위를 재사용하지 않는다.

normal select→hp_status.begin_world→hp_resource_owner.open_world_projection→store.open_projection_read→registered owner validate_projection_read→_send 각frame 예약/write/drain→world finish→A/B caller/target수명을 한 작업 단위로 완결하려 한다. 원 open_delivery(쓰기 cap)의<=5는 별도이며 무조건 확장하면 안 된다. core source path/SHA는 npc_continuous_retaliation_inputs.issue에 고정되어 있다. 원 저장·definitions·정책 선언 provenance를 runtime후손 선택 때문에 바꾸면 안 된다.

## 질문

GitHub 연결 앱으로 정확 branch/commit의 실제 파일을 먼저 읽고, 읽은 repo/ref/path와 blob SHA 또는 구체 원문 함수 근거를 제시해 주세요. 일반 비공개 URL 웹 열람으로 대체하지 마세요. 필수 첫 파일은 canonical_batch.py, broker.py, hp_status.py, hp_resource_owner.py, npc_continuous_retaliation_inputs.py이며 필요한 bootstrap/aggregate/A-B 소비자도 이어 읽어 주세요.

1. 현재 접근을 계속하는 것이 맞는가? 단1 NPC 가정이 count guard 여러 곳에 남아 한 조각씩 통과시키는 구조에서 어떤 핵심 가정/소유 경계가 빠졌는가?
2. 원single/default 일반상한5와 write delivery cap은 보존하면서, 기존 v20 exact6 current bundle proof를 canonical WORLD projection의 실제 binding/registered owner에서 재사용하는 최소 완결 수정은 무엇인가? source ready/default None·cap발급/현재task·동일frame순서·각drain/finish·재선택/목표수명까지 직접 필요한 caller/callee를 한 묶음으로 제시해 주세요.
3. core private후손과 input issuer의 core_path/SHA를 고르면 immutable existing store/provenance/동일classnamespace를 어떻게 유지해야 하는가? snapshot source를 읽어 실제 문제가 있는 다른 single/count 접점도 이번 기능의 직접 영향 안에서만 지적해 주세요.
4. 다음 한 번의 최소 실구현/시험을 무엇으로 정할까? world원6응답 발급/각drain/finish→A normal attack/pose/freshcounter→B로실제전환/자기HP·mover·counter→원selection release까지. 이전387/389/392·19hit/DEAD·종료만용별도기동·전체protocol/성능/새observer/검증framework는 반복하지 않는다.

추정과 확인된 source 사실을 분리하고, 일반 guard를 제거하거나 len 상한만 전체적으로 6으로 높이는 답은 피해주세요. 함수 하나/메모리 한 필드 진단으로 줄이지 말고 두 적의 완결기능 접근과 바로 적용할 최소 대안을 우선순위로 주세요.
