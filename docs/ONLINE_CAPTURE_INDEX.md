# 정상 온라인 관찰 자료

2026-10-05. 클라이언트 `26.09.29.2001`, 원본 EXE SHA256 `9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af` 기준이다. 후속 구현에서 사용할 실제 값과 해당 값을 읽는 코드 근거를 보존했다. 온라인 관찰 성공과 로컬 단독 접속 완료는 별개의 상태다.

## 바로 사용할 자료

- [최신 수집 목록](../work/online_collection_manifest_v6/collected-game-data.json):8보고서/1934표본. 보고서별 실제 값, 중복 횟수, 최초·마지막 관찰 시간, 필드 위치·형식, 소스 계약·해시. 캐릭터 이름과 혈맹 표시 문자열은 이 로컬 JSON에만 들어 있다. 이전6·7보고서 목록도 그대로 보존했다.
- [수집 범위](../work/online_collection_manifest_v6/coverage-ledger.json): 자료별 표본 수·필드 수, 미확인 영역.
- [최신 독립 검증](../work/online_collection_manifest_v6/root-review.json): 이전87·35개 확인에 더해 최종 보고서·표본·상태·Actor/Action 집계40개 확인,15tests PASS.
- [현재 리소스·테이블 목록](ASSET_DATA_ANALYSIS.md): 인증한 자원 목록 및 아이템·NPC·마법·퀘스트·제작 데이터. 메모리 관찰 결과와 자료 종류·버전을 구분한다.

## 실제 수집 범위

| 범위 | 보존·검증 결과 |
|---|---|
| 캐릭터 선택 | 132개 유효 표본. 캐릭터 1행, 표시 슬롯 3, 선택 인덱스 0. 종료 때 미확인 표본 2개도 그대로 보존 |
| 게임 장면 | 재접속 후 네 차례 각 300개 표본에서 Land5 확인. 첫 표본부터 Land이므로 진입 순간을 포착한 것은 아님 |
| 캐릭터 표시 정보 | 이름·혈맹 표시, 클래스·성별, 필드6~22. HP/MP/AC/Level/STR/DEX/CON/WIS/CHA/INT/Alignment 등의 의미13개는 UI 소비 코드와 자원으로 연결 |
| 내 플레이어 | ActorID233372726, 좌표 word pair32772/32760, MapSubsystem718/header0=4. 좌표 축·맵 숫자의 전체 의미는 별도 미확정 |
| SelfUID | 캐릭터 데이터의 SelfActorUID와 월드 MyPlayer ActorID가 V4 300개 표본 모두 일치 |
| 인벤토리 | 고유 항목 6개. 아이템 UID·템플릿ID·field18/28/30 보존. field28의 수량 관련 UI 소비를 확인했지만 모든 동작 의미를 확대하지 않음 |
| 스킬 | 두 tree의 읽힌 키는 빈 목록. 읽지 못함과 정상 빈 목록을 구분하고 다른 캐릭터에 일반화하지 않음 |
| 환경 | Source로 확인한5개 필드, 각100개 표본. field28 변화와 field30=1.0, 세 bool=false 보존. 시간 단위·기능 의미는 추정하지 않음 |
| 등록 시스템 | Source 후보59종 중 실제 등록58종을100개 표본에서 확인. owner 존재와 내부 데이터 수집 완료를 구분 |
| 주변 객체 | V5에서 고유26개(MyPlayer1/Player19/Item3/Monster3)의 ID·좌표 확인. 타입 미확정 행203개는 미확인으로 남김 |
| 장비 | map25회에서 숫자 쌍2개를 보존. 별도 event set25회는 빈 목록. 슬롯·ID의 일반 의미는 별도 미확정 |
| 버프 | 50회에서 ID20034/kind7/remaining−1.0/deadline0 한 행 확인. 음수 값을 임의로0으로 바꾸지 않음 |
| 최종 주변 객체 | V6에서 고유41개 ID와7종 실제 타입 확인. 그중37개 좌표 확인. 타입 미확인 행0,읽기 예산상 좌표137행 미확인은 보존 |
| 현재 동작 값 | Action378행 확인/148행 예산상 미확인. 내 캐릭터의 현재 조회 키138·상태 word40. 원본 Actor3/4 입력이나 sprite/class/gender로 고유 복원하지 않음 |

전체8개 원본 보고서에 총1934개 표본이 있다. 이 합계에는 최초 캐선의 미확인 표본2개, V5·V6의 부분 확인 각1개, 표본0개인 최초 식별 거절 보고서도 포함된다. 각 수집 프로필의 Source·계약·reader 이력은 보존했으며, 프로필에 없거나 일정상 보류된 필드를 실제 값0으로 취급하지 않는다.

## 코드 근거와 남은 작업

- [캐릭터 필드 의미](../work/online_character_field_meaning/source-contract.json), [수치 해석](../work/online_character_numeric_source/source-contract.json), [Player·좌표·맵](../work/online_world_public_source/), [인벤토리·스킬](../work/online_inventory_skill_source/).
- [로그인·목록 통신](../work/online_login_packet_source/review.md): KEY→VERSION4E34→COUNTS4F3D 경로와 NUM/INFO 처리 조건을 확인했다. 캐릭터 목록 요청2종의 숫자 opcode는 아직 미확정이다.
- [월드 진입 통신](../work/online_world_packet_source/): Map4E95/Actor4E96과 SelfInfo4E38의 소스 연결을 조사하고 있다. 실제 데이터와 필수 필드를 연결한 뒤 로컬 응답을 구현해야 한다.
- [주변 Actor 구조](../work/online_actor_data_source/source-contract.json)는 Actor/Player/MyPlayer/Item/Monster5종의 ID와 공통 Transform 좌표 경로를 확인했다. [독립 검증](../work/online_actor_data_source/root-review.json)에서50개 명령·5개 타입 table/상속 구조·3개 함수·전체 계약 재현과9개 시험이 통과했다. 이 자료는 읽는 방법의 근거이며, 주변 객체의 실제 값은 다음 수집 대상이다. HP·템플릿ID·상호작용 필드는 미확정이다.
- 추가13개 Actor 타입의 코드 근거와 현재 동작 조회 키를 읽는 Source를 확인했다. V6 실제 자료와 [독립 집계](../work/online_public_session-v6/root-memory-proof.json)를 연결했다. 전체18개 Source 타입이 실제로 모두 존재한 것은 아니다.
- 이전 월드 계약의 `+98` 자원 포인터 해석은 [새 근거](../work/online_actor_template_source/root-review.json)로 정정했다. 실제로는 Actor protobuf 복사본이며, `+AA`는 Actor 필드16의 Player분기 bool이다.
- [캐릭터 wire V2](../tools/local_character_wire_v2/README.md)와 [월드 wire](../tools/local_world_protocol/README.md)는 Source에 맞는 입력을 검증하는 순수 인코더다. 실제 서버 응답·접속 완료를 대신하지 않는다.

실제 로컬 캐릭터 진입은 아직 미완료다. 현재 로컬 연결 후보는 [독립 파일 검증](../work/local_endpoint_bridge/root-review.json)에서7개 복원 record·28개 소스 명령·정적 해석 시험8개를 통과했다. 실제 연결은 후속 시험 대상이다. 정상 온라인 분석 중에는 원본을 종료하거나 도우미의 방화벽 복구를 실행하지 않는다.
