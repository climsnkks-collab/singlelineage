# 동일 Pro v3 보완 요청

기준은 companion-webpro-review-v3/review.md a46b1523의 단1 비작성 증분검토다. 아래는 그 두 항목을 필요한 caller와 직접 대조한 자체 요약이다. 로컬 제품 변경·적용·import·실행·검사재생·성능측정은0이다. 구현·수정은 계속 같은 Pro가 소유한다.

## 1. 확정 OPEN — actual393 canonical alias와 loader 계약

대상: tools/local_original_session/companion_source_selection.py:132–138, :235. 원393 loader cohort_loader.py:28은 canonical_skill을 buff_lifecycle/buff_skill_document보다 먼저 install하고, :21–24는 새로 적재하는 원모듈을 tools.local_original_session.<alias>와 package에 결속한다. 이 묶음의 raw/cohort_loader.py가 manifest의 정확 bec48f6a 원문이다.

최소 정적 반례: 원 cohort10b0a630·manifest74217e4d와 정상11후손 경로를 선택한다. 원 selected68에는 canonical_skill(c1ef77e4)이 있고 canonical_batch는 없다. select393:235가 value.selected(cohort['selected'])를 실행하면, :137의 canonical_skill 부재 조건이 거짓이므로 COMPANION_SELECTION_CANONICAL_BASE_ALIAS_REQUIRES_LOADER_CONTRACT로 issue/Factory 전에 거부된다. 이는 코드와 exact metadata로 확인한 반례이며 select393를 실제 실행한 결과로 표시하지 않는다.

기대: 실제 nominal canonical_skill alias와 lifecycle.canonical이 같은 selected module/baseclass/Rule 객체를 소비하는 명시 loader/issuer 후손을 제공한다. 실제 SourceModule·원 경로/SHA·class-space 검사를 보존하고 root가 새 결과핀을 수용해야 한다. 실제: guard가 이 부모를 막으므로 wholecohort 선택은 OPEN이다. canonical_batch의 aggregate loader 경계도 보존한다. alias 삭제·원 map 은폐·guard 완화·기존 파일 전체 덮기는 해결로 취급하지 않는다.

제공 문맥: selected393-source-descriptor.json의 정확68 alias와 원핀, raw/cohort_loader.py, raw/canonical_skill.py. descriptor는 경로만 정규화한 읽기용 파생자료이며 원 cohort/manifest를 대체하지 않는다. 원10b0/7421 파일과 고정핀은 로컬 그대로 있고 Pro root resolver가 해당 원본을 소비해야 한다.

## 2. P2 — 같은 cold 경계 안의 중복 static stat/read/hash

대상: companion_source_selection.py:103–112(check), :141–147(core/check_loaded), :173–183(late_sources/check_plan). caller는 patches/playable_mage_companion/selected393-runtime-input.patch:29–37(_selection_current), :83–89(Issued.recheck), :124–129(issue late_sources)다. 이는 patch 파일 행 번호이며 적용 후 runtime 파일의 행 번호라고 주장하지 않는다.

최소 정적 반례: 선택이 있는 Issued.recheck → _selection_current → Selection.check 뒤 같은 호출의 check_plan → check_loaded → check, 이어 core → check가 반복된다. issue의 late_sources → check_loaded와 core 및 load_cohort/selected에도 중첩이 있다. check 한 번은 metadata2와 child11을 다시 stat/read/hash한다. 실제: 같은 cold 경계의 동일 고정 바이트가 여러 겹으로 재확인된다. 매 tick/poll에 추가된 검사는 아니며 지연 수치는 측정·주장하지 않는다.

기대: 외곽 cold 선택과 기존 SourceModule의 실제 source 검증 경계에서 필요한 파일/핀 검증을 수행하고, 동일 호출의 issued witness·same-module/baseclass/Rule/plan identity 확인은 그 결과를 재사용한다. 경계를 넘는 stale/current·권한·SourceModule 검사는 계속 보존한다. 새 캐시 서비스·검증 프레임워크·perf 검사·전체 suite·게임을 추가할 필요는 없다. 기존 권한 검사 삭제와 중복 검증 축소를 혼동하지 않는다.

이 두 항목의 보완과 native 미공급 포트는 별개다. 받은 버프 source 변경분 수용을 source selector 완료·실동료 SKU/게임완료로 확대하지 않는다. 같은 Pro가 정확후손/부모핀/변경분과 직접 영향받는 최소 확인을 제출하면 root가 통합·실행 소유 경계를 따라 검토한다.
