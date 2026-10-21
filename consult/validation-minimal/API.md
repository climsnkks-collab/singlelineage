# 동기 source 계약 재사용

`inventory.run_source_contract(callback, *args, **kwargs)`는 명시적인 동기 호출 포트다. 정상 반환값/예외를 보존하며, coroutine/generator 함수와 awaitable/generator 결과는 거부한다. 반환된 coroutine/동기 generator는 닫고 scope를 퇴역시킨다. async generator는 실행·await하지 않고 거부하며 동기 포트가 비동기 cleanup 완료를 주장하지 않는다. await를 가로질러 사용하지 않는다. wire가 원 prepare/commit/validate/selected_ready의 no-await 구간에 명시적으로 연결한다. Root producer의 직접 caller/locals는 바꾸지 않는다.

입장과 정상·예외 퇴장에 원 `_source_documents`의 **19파일 ordinary/크기/실 bytes/SHA** 검사와 원 `_source` metadata assertions를 수행한다. 본문은 이름/자료 인자 분리 외 AST 불변이다. 같은 검증 자료의 원 `_freeze_static` 지문을 비교하며, 중첩 `_source`/`_source_documents`는 private 불변 자료에서 원 dict 순서/정확 타입을 보존한 새 복사본을 반환한다. keys는 frozenset이다. 메타데이터 값·핀·원 reader·검사를 삭제하거나 완화하지 않는다.

재사용 범위는 실제 thread/Task/동기 run frame/동일 token 객체다. 중첩 포트는 같은 외부 검증을 공유하지만 동일 callback 재진입은 거부한다. 원 함수/코드·메서드·source constants·외부 reader bindings를 검사한다. 퇴장 checker/code/need/불변 seal은 실제 run frame의 local로 보존하므로 callback의 guard 교체를 허용하지 않는다. 예외 뒤 token은 먼저 제거한다. 다른 thread/나중 Task에는 token이 전달되지 않고 원 전체 검사를 수행한다. stale token 조회는 거부한다.

이 포트는 정적 source 증거만 재사용한다. 실제 Root 등록/current record/Binding·issued op/Position/장비/Store raw CAS는 각 원 경로에서 계속 조회한다. 현재 성공 bool/TTL·권위·등록·allocator·metadata cache를 만들지 않는다. 실제 profile/게임/공용 소스와 동결 부모는 수정하지 않았다.

## 정확 선택

| 파일 | 정확 부모 | 현재 SHA256 |
| --- | --- | --- |
| inventory.py | 51361aa704507014ecbeb20fbb0fb5648563648dd9453e806f7fcb73788eac1e | 51787127e681eee95b315cab7471828cdb43b6deb75cdfe4da0966bb660c0da7 |
| inventory_store.py | ff343309eca2d7957cb04aaecf756e5c8645547758936f81e5ffce1cb3f04f3a | 3d69189b3880eeac3956d08d80e9e7024d52411339775c44ecb46889c62f7d76 |
| inventory_observe.py | 3c4aaa068b606015827b14352d375bc649efbfbeb8e6796e3c874b241088c2a7 | 674d1d62b33577f346c465685e12119763ec706ee4a011b060842032011b7223 |
| ground_client_retirement.py | caa7cf6a9d3b09a47c9208c46bb66b299664faf8624ac3fe6b8a449e9573a613 | f957ea157e31c325463fa0ee30f7dccfb5eab6ac859b500c9ef7ad68c12ee1c9 |

아래 세 소비자는 inventory SHA literal 한 곳만 바꾸었으며 raw 역복원이 정확하다. SourceModule/cohort도 이 네 파일을 같은 모듈 그래프로 선택해야 한다. policy a934/bridge f469/facts8838과 원 부모는 동결 상태다. `source-proof.json`/`inventory.diff`는 source/reader assertions 원문과 원 클래스/다른 함수 전체 AST 보존을 검증한다.

직접 반례 6개와 변경 영향 order2/scope1/checker1의 기존 성공을 재사용한다. 복제한 19개 byte-identical source의 변조만 시험했으며 원 metadata는 쓰지 않았다. 세부 log는 manifest에 연결한다. 기존 profile의 65/71초는 계측값이며 일반 제품 시간으로 단정하지 않는다. 중간 ffc source에 대한 `measure-result.json`도 계측 오버헤드가 있는 정적 자료 참고값이며 최종/게임 latency 근거가 아니다. 최종 actual graph/시간 검증은 wire 담당이 소유한다.

상태: **WRITER_RELEASED**. 최종 source517/Store3d 이후 제품 파일 추가 변경은 실제 결함에 한정한다. main 비작성 위험검토와 wire의 원 caller 소비 결과가 남아 있다.
