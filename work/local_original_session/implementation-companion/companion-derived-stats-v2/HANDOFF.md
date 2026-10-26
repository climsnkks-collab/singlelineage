# COMPANION-MAGE 같은 동료 derived_stats v2

WRITER_RELEASED · private source_ready/cold_ready true · run_ready/test_ready false · runtime UNRUN.

`companion_derived_stats.py`에 실제 동료의 저장 캐릭터·인벤토리·장비·canonical SKILL/Buff를 읽는 callback을 구현했다. v1의 직접 선택 전용 `SelectedStatsSource` 한계는 유지하며 해당 source나 owner stats를 사용하지 않는다. 기존 GearStore의 상속 공개 `restore(uid,frame)`와 `current_members`가 실제 같은 캐릭터 장비 상태·원 Definition을 읽을 수 있으므로, 매번 원 lock 안에서 읽어 계산하는 방식으로 연결했다. 별도 live GearFact·cache·refresh writer는 만들지 않았다.

입력은 실제 현재 companion binding/lease와 설치된 SharedSupport에 결속한다. 실제 GearConsumer가 소유한 같은 InventoryStore의 GearStore만 읽고 생성/초기화/이관/저장하지 않는다. sidecar가 없으면 `COMPANION_STATS_MISSING_GEAR_IS_UNKNOWN`으로 거부한다. 실제 저장 level1/class3 attributes를 original INFO와 같은 순서로 변환하며, 장비의 기존 base-reference 정책과 실제 SKILL 활성 Buff를 각각 한 번만 적용한다. level2 이상·미지원 장비/instance·unknown Buff 등은 거부한다. 본 callback은 지원 configuration의 `derived_stats`로 직접 공급하며 네 정책을 명시해야 한다.

원본 `companion-cohort-v2` 선정 소스 18개와 cohort/loader/dependencies/v1 부모·새 제품 SHA256은 `manifest.json`에 있다. 기존 SourceModule graph에 새 모듈과 해당 의존을 함께 capture해야 한다. 공용 source·v1·다른 담당 경로를 수정하지 않았다.

`python -B work/local_original_session/implementation-companion/companion-derived-stats-v2/verify_cold.py` PASS. 기존 선정 graph의 cold import와 실제 callback constructor, 순수 DTO의 비대칭 attributes 순서·원 Ring496/Shield 단회 반영·만료 Buff 제외 및 missing/다른 UID/성장/unknown Buff 거부를 최소 확인했다. 순수 DTO는 런타임 권위/저장/Host/라이브 callback에 공급하지 않았다. 실제 binding→원 Store 읽기는 UNRUN이며 packet/native UI 성공을 주장하지 않는다.

전체 지원 configuration의 target/catalog/range·실제 동료 획득/장비 저장 입력·healing 정책/RNG/lawful는 본 source 범위 밖이다. packet caller/RUN_COMMAND 없음, test_ready false. Test client/API·실행/포트/저장 사본·큐를 변경하지 않았다. 후속 담당은 계약 파일의 정확 call chain과 기존 준비 시나리오를 재사용한다.
