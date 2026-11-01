# 미확인·보류 작업 목록 (오케스트레이터 관리)

사용자 지시 (2026-10-28): 확인 안 된 것을 그냥 넘기지 말고 확인해서 작업한다. 의존성 때문에 당장 못 하면 여기 적어 두고 적절한 시기에 투입한다.
각 항목: 무엇 / 왜 보류 / 풀리는 조건 / 상태. 작업을 투입하면 상태를 바꾸고, 끝나면 완료로 옮긴다.

## 다음 구현 (예약)
| 항목 | 상태 |
|---|---|
| **[10-30 첫 작업]** 동료 ATS 창 분리(COMPANION_IMPLEMENTATION_PLAN.md 9단계) + 버프·힐 마법을 다양하게 넣어 저장·재열기·동료 시전/재시전 시험 | 사용자 지시 2026-10-29 밤: 다음 날 첫 번째 작업. 공유 창 + W50·loadable_ats 보정은 분리 완료 후 제거 |
| [사이드 메모] 서버 미연결 요청 0x072e, 0x03eb가 실제 플레이·두루마리 사용 중 들어옴(GAME_OPCODE_UNBOUND, runs/glfw30-talkscroll_open, manual-test-knight-20261029-020113). 응답 체크리스트 작업 때 같이 정체 확인 | 미확인 |
| **[사이드, 상시]** 요청별 원본 응답 체크리스트: L1J 처리 코드(C_* → S_* 송신 묶음)로 자주 쓰는 동작의 응답 신호(동작·이펙트·버프 아이콘/시간·HP/MP·파티 갱신 등)를 REQUEST_COVERAGE_MAP에 칸으로 붙이고 우리 서버 누락을 대조. 완료는 헤드리스 스크린샷 확인분만. | 사용자 지시 2026-10-29: 따로 큰 작업으로 하지 말고 다른 구현 작업에 적당히 묶어서 같이 갱신. 계기: 줍기 동작·물약 이펙트·버프 시간 누락이 지도 "처리함"인데도 빠져 있었음 |

### 사이드: 원본 응답 체크리스트 1차 (2026-10-29)

[동작별 표·파일:줄 근거](REQUEST_COVERAGE_MAP.md#원본-응답-체크리스트-1차--2026-10-29) / JSON 새 칸 original_response_checklist_v1. **22동작·70신호 대조 후 서버 recipient 6행 연결·개발 시험 84개 통과. 화면 확인 0개, 게임·포트 실행·커밋 없음.** L1J는 참고 backend이며 공식 원서버 필수 응답이라는 확정이 아니다. 아래는 눈에 띄는 정도의 추정 순서다. 현재 줍기 동작·물약 효과·지원 물약 기간 송신은 존재하므로 다시 누락으로 적지 않는다.

| 순위 | 무엇 / 왜 보류 | 풀리는 조건·근거 / 상태 |
|---:|---|---|
| 1 | 주변 PC 이동 방송 · 화면 내 다른 PC 위치가 멈출 수 있음 | R01.1; ［T/world_core_session.py:106］<br>［T/world_core_maps.py:141］<br>［T/world_visibility.py:358］<br>［T/world_visibility.py:480］<br>［T/world_visibility.py:527］; L1J ［J/clientpackets/C_MoveChar.java:125］<br>［J/model/L1Character.java:136］ · **서버 연결·개발 시험 확인, 화면 미확인**. realm의 완전한 self Actor DTO를 pc_actors에 등록하고 별도 pc_known으로 상호 소개/화면 경계/맵 전이/퇴장을 연결. 기존에 보던 같은 맵 PC에만 정상 한 칸 이동의 pre-step 4E2C를 큐에 넣고 새 recipient에는 최종 Actor를 보냄. self 정상 ACK 추가 없음. 운영 broker 단일 PC 제한은 유지하므로 다중 PC는 개발 시험 범위. |
| 2 | 주변 PC 사망 동작 · 다른 PC의 사망 표시가 빠질 수 있음 | R04.2; ［T/world_visibility.py:640］<br>［T/world_visibility.py:647］; L1J ［J/model/Instance/L1PcInstance.java:244］ · **서버 연결·개발 시험 확인, 화면 미확인**. 기존 HP0/자기 raw8 순서를 유지하고 같은 death wire를 pc_known의 주변 PC에 큐. out-of-view/다른 맵에는 미송신. 다중 WorldView 개발 시험 통과; 운영 단일 PC 제한 유지, 원본 화면 미확인. |
| 3 | 자기·대상 마법 시전 동작(기본 설정) · SL_SPELL_EXP=1에서만 후보 송신 | R15.2; ［T/world_feature_magic.py:780］<br>［T/world_feature_magic.py:789］<br>［T/world_feature_magic.py:798］; L1J ［J/model/skill/L1SkillUse.java:1428］<br>［J/model/skill/L1SkillUse.java:1429］ · **기본 gate 유지**. PLAYER_MAGIC_EVIDENCE.md:171/173의 공식 시전·gfx/순서·임의 K 결속 UNKNOWN. 정상 소비 관측 후 활성화 |
| 4 | Heal·Shield 대상 이펙트(기본 설정) · 같은 실험 gate에서만 송신 | R15.3; ［T/world_feature_magic.py:781］<br>［T/world_feature_magic.py:790］<br>［T/world_feature_magic.py:800］<br>［T/world_status_frames.py:71］; L1J ［J/model/skill/L1SkillUse.java:1449］<br>［J/model/skill/L1SkillUse.java:1455］ · **기본 gate 유지**. PLAYER_MAGIC_EVIDENCE.md:171/173의 공식 시전·gfx/순서·임의 K 결속 UNKNOWN. 정상 소비 관측 후 활성화 |
| 5 | 마법 버프 아이콘·남은 시간(기본 설정) · SL_PLAYER_MAGIC_BUFF_UI=1에서만 송신 | R15.4; ［T/world_feature_magic.py:105］<br>［T/world_feature_magic.py:494］<br>［T/world_feature_magic.py:506］<br>［T/world_feature_magic.py:516］; L1J ［J/model/skill/L1SkillUse.java:1226］<br>［J/model/skill/L1SkillUse.java:1231］<br>［J/serverpackets/S_SkillIconShield.java:29］ · **기본 gate 유지**. PLAYER_MAGIC_EVIDENCE.md:171/173의 공식 시전·gfx/순서·임의 K 결속 UNKNOWN. 정상 소비 관측 후 활성화 |
| 6 | 물약 사용 이펙트의 주변 전달 · 본인 효과는 이미 보냄 | R08.4; ［T/world_feature_items.py:342］<br>［T/world_feature_items.py:367］<br>［T/world_feature_items.py:395］<br>［T/world_item_effects.py:1056］<br>［T/world_visibility.py:346］; L1J ［J/clientpackets/C_ItemUSe.java:2701］<br>［J/clientpackets/C_ItemUSe.java:2745］ · **서버 연결·개발 시험 확인, 화면 미확인**. 기존 사용/저장 성공 이후 세 물약 lane과 durable consumable lane에서 4ED8만 현재 pc_known recipient에 전달. HP/재고/4E91 HUD는 본인에만 유지. 거절/저장 실패 전에는 방송하지 않음. 다중 PC 개발 시험 범위. |
| 7 | 가속·용기 물약 속도의 주변 전달 · 본인 속도·기간은 이미 보냄 | R08.5; ［T/world_feature_items.py:395］<br>［T/world_visibility.py:369］<br>［T/world_visibility.py:631］; L1J ［J/clientpackets/C_ItemUSe.java:2797］<br>［J/clientpackets/C_ItemUSe.java:2899］ · **서버 연결·개발 시험 확인, 화면 미확인**. 적용 성공한 4E5B와 실제 만료 reset을 pc_known 주변에 전달. 새로 보이는 PC에는 현재 유효 속도를 소개 뒤 보냄. 소모/중첩/기간/아이콘 정책은 기존 값 그대로. 다중 PC 개발 시험 범위. |
| 8 | 장착·해제 외형의 주변 전달 · R14.3도 같은 경로; self Actor는 보냄 | R13.3; ［T/item_equipment_effect.py:455］<br>［T/world_core_kit.py:129］<br>［T/world_core_kit.py:131］<br>［T/world_visibility.py:335］; L1J ［J/model/L1PcInventory.java:454］ · **서버 연결·개발 시험 확인, 화면 미확인**. 기존 저장/097A와 self Actor drain 후 publish_pc_actor가 같은 완전한 DTO를 pc_known 주변에 전달. 외형 불변이면 self/peer 모두 생략. 다중 PC 개발 시험 범위; 원본 렌더 미확인. |
| 9 | 버린 물건 표시의 주변 전달 · sibling whole-item drop 경로 한정 | R07.3; ［T/item_transfer_session.py:391］<br>［T/item_transfer_session.py:413］; L1J ［J/model/L1GroundInventory.java:94］ · **보류 유지**. 독립 sibling custody 저장→정확 wire drain→registry.complete 수명에 world EntityRef/recipient 결속 없음. pickup/실패/퇴장까지 정식 이관 계약을 마련한 뒤 연결 |
| 10 | 인챈트 결과 안내(기본 설정) · 재고 변화는 보냄; 현대 0967 의미·메시지 ID는 미확인 | R09.2; ［T/world_enchant_inventory.py:137］<br>［T/world_feature_items.py:65］<br>［T/world_feature_items.py:95］; L1J ［J/model/Enchant.java:220］<br>［J/model/Enchant.java:263］<br>［J/model/Enchant.java:445］ · **기본 gate 유지**. 현대 0967 필드/문구 ID가 미확정. 정상 결과 소비 계약 후 연결 |

운영 broker의 단일 PC 제한(［T/broker.py:464］)은 유지했다. 주변 전달은 다중 WorldView 개발 시험 범위이며 실제 동시 접속·원본 화면 PASS가 아니다. 새 PC 소개/제거·화면 경계/맵 reset/로그아웃·거절 시 무방송·장착 self drain 후 전달을 확인했다. 저장 회귀 13개는 기본/프로젝트 임시 경로 모두 PermissionError로 미완이다. [서버 후속·시험·보류 사유](REQUEST_COVERAGE_MAP.md#서버-recipient-연결-후속-2026-10-29)와 실행 원문을 따른다.

이 표의 T/J 약어는 [요청 지도 근거 경로](REQUEST_COVERAGE_MAP.md#근거-경로와-실제-송신의-경계)를 따른다. 실험 gate 항목은 스위치를 무조건 켜라는 지시가 아니며 native 인수·이미지 키·수신 계약 확인 후 해당 구현에서 다룬다.

기타 scoped 미송신: PC 부활 동의(R12.1), 일반 파티 초대/수락(R20.1), 일반/파티 채팅 echo(R21.1), 서비스 오류 문구(R08.7/R15.5/R17.3). 현대 Y/N/파티 제어·채팅 입력·문구 ID는 미확정이므로 해당 계약과 함께 착수한다.

**미확인으로 보류:** teleport sound/잠금해제·순서, 즉시 weight wire, 감정 상세·독 표시, 일반 PC 파티 HP 갱신, 마법4F25/인챈트0967 의미, 거래 후 창고 LIST/ACK 필요성, 부분 pickup 표시. 상세는 요청 지도 「확인 못 한 것」에 둔다. 원서버 패킷·클라이언트 소비 원문 등 해당 연결 근거 확보 후 판정하며 미확인을 미송신으로 합산하지 않는다. 레벨업 refill은 LOCAL/L1J 정책 차이로 따로 기록했다(R22.2).


## 진행 중 (이미 투입)
| 항목 | 상태 |
|---|---|
| 속성 저항: 장비 저항 집계·피해식 완료(ELEMENT_RESIST.md). 몬스터 속성 공격 생산자·봇 확인 | 진행 중 (Codex) |
| 속성 저항: 동료가 받는 마법 피격 연결 | 완료(2026-10-28): 기존 장비 profile→등록 npc_magic_target→공유 NPC 마법식·동료 HP 소비 연결 확인, world_companion_equipment_tests 통과 |
| 주문서 사용 불가·아데나 수량·바닥 "수량 이름"·소모품 사용 이펙트·사망 후 단축키 설정 초기화·무입력 자동 종료·접속 시 인벤 지연·걷다 밀림 | 수정 완료(시험 15개·play_matrix 통과) — 헤드리스 화면 확인 남음 |
| 동료 서버 규칙·창·설정 연결·걷기 속도 | 기존 동료 봇 78개 검사 범위 유지. 10-28 후속: 08A0 게시→08A3 자원 갱신·actor 재게시·서버 캐시 정리 연결(키 값 LOCAL, 정상 원 서버 값·원본 화면 미확인). 파티 행 제거는 08A1 enum·탈퇴/해산 순서·08A0 snapshot 의미 미확정으로 보류. 제거 근거 확보 후 연결·화면 확인 필요. 귀환은 일반 목적지 훅·PositionStore 연결, mode8 무시 유지. 관련 저장 시험은 샌드박스 임시 파일 PermissionError로 Claude 실행 필요. 학습은 MagicStore→등록형 훅→AI·ATS record 조회 투영으로 연결(기존 companion.json 학습을 권위로 올리지 않음); spellbook_learning_tests.LearningHandlerTests.test_companion_learning_uses_magic_store_after_direct_learning_and_reload는 임시 characters.json 생성 PermissionError로 Claude 실행 필요. 마법 재사용·MP 회복 중 근접 접근·칼질 차단 해제: world_companion_magic_tests 14개 개발 시험 통과(원본 화면·정식 플레이 PASS 아님). |
| 동료 ATS 설정 → AI 적용 | 구현: 설정 없음·빈 선택·해석 불가는 자동 소비/마법 없음, 자기 조건·칸 순서·순서 실패/초기화·선택 버프 갱신·회복 묶음 소진 비대체. 주인/긴급 힐·기본 마법/물약·힐 MP 비축/회복 대기 삭제. 이전 W34 개발 시험 53개 통과(52개 묶음+opaque64 1개, 원본 화면·정식 플레이 PASS 아님). ATS 저장 2개·회복 저장 4개·장비 마법 1개·학습 1개는 임시 저장 PermissionError로 Claude 실행 필요. W36 정적 조사로 CONDITION_PREDICATES의 f1=1..6(%·초·회), 동료 자기 HP/MP float 비교, spellRowID별 AND·최초 평가 시각 유지·시전 성공 후 횟수/시각 갱신, 대상 변경·재소환·재접속 초기화를 연결. 범위 밖 f1은 false. 이번 관련 개발 시험 34개 통과(원본 게임·통합 회귀 미실행). W34 회복 시험 test_recovery_slot_order_and_self_threshold / test_recovery_slots_precede_bag_order_and_depleted_stack_never_substitutes의 fixture를 기존 f3·순서 불변/새 UID append=True 계약에 맞게 수정했으며 제품 저장 무결성 검사는 유지. 두 시험은 기본 Temp와 프로젝트 runs 임시 경로 모두 characters.json 임시 파일 생성 PermissionError(정리도 WinError5)로 막혀 Claude 실행 필요. 근거 RVA·원본 초기화 UNKNOWN과 사용자 LOCAL 정책 구분은 ATS_COMPANION_TOGGLE_DESIGN 2.2절. 전투 칸은 blob 순서를 보존하며 native 화면 순서 대조는 미확인. item f7 문자열 비교 의미와 기존 3종 외 주문 소비는 미확인/미지원으로 기록·보류. f4/f5/f6 복합값은 유일한 묶음만 조회. 기존 socket magic의 옛 주인/긴급 힐·MP 비축 기대는 ATS 선택 기반으로 수정했으나 이번에는 실행하지 않음. |
| 동료 F4 같이 줍기 + 동료 속성 피격 | 투입됨 (Codex qF4) |
| 던전 전 층 봇 | 완료(DUNGEON_MAPS.md) | — |
| 통합 정리(진행 중, Claude): start-manual-play 핀 불일치(inventory.py·item_equipment_effect.py), launcher_tests INVENTORY_OBSERVE_PARENT_SOURCE_CHANGED(소스 해시 핀 — 제거 방침), world_integration 마을 NPC 70012 불일치, hunt_bot_pet 불안정 | 대기: 지금 도는 작업들 끝난 직후 통합 회귀 |
| 걷다가 뒤로 밀림: 원인 = 내 캐릭터 4E96 재전송(자세 불변이어도 보냄) | 수정 투입(자세 불변이면 생략) |
| 뒤로 밀림 2차: 무기 교체 시 좌표 없는 4E5C로 자세만 바꾸기 | 클라이언트가 4E5C f3를 자세로 반영하는지 미확인 | 헤드리스/사용자 시험 |
| 뒤로 밀림 3차: 4E96 직후 STALE 시작 칸을 서버 위치로 채택 | 사용자 승인 — 수정 투입 | — |
| 슬로우·마비 4EE0을 보정 카운터에 포함(진단용) | 마법 작업 중 | qMagic 끝난 뒤 |
| 상점 품목 갱신(옛 문서 때문에 거부 → 재지시) | 진행 중 (Codex) |
| 변신 런타임 승격 재대조(catalog85) | 조사 완료: 신규0·SPR3개 보완(78/85).22항목별 부족 계약·특수9개 item identity/API 보존. 첫 변신8체크 성공(설명metadata변경1개). 최종고정판·enchant_poly는 공용realm 기존SHA불일치 import실패/요청0, 소유자 정리 후 재시험 |
| 퀘스트 엔진 확장(가변 정산·전달물·처치 이벤트·선행 조건) + 후보 5개 승격 | 엔진·라이라1개 완료. 남은4개 재조사 완료/신규0개(QUEST_EXPANSION.md), 실제 미완 계약은 대기 행 |
| 본토 NPC 외형 선택94→132/184 (직접 client27·LOCAL105) | 기존 본토5마을 scoped PASS·기본6마을60007 SKIP 원결과 보존. 60007 누락 runtime binding과 LOCAL 창고 외형143 보완·등록 단위PASS. 본토184종 선택 수 불변; 기본6마을 최종 재시험은 통합 startup 문제와 분리 판정([M5 상세](M5_MAINLAND_TOWNS.md#기본-6마을-npc60007사냥-정체-원인-수정-2026-10-28)) |
| 미확인 요청 번호 86→85 (REA 심층 호출 시간 초과) | 대기: REA 실행 시간 늘려 재시도 |
| 새 몬스터 87종 출현 확인 | 완료: 87종·323그룹 생성 확인, 218조합 중 204 처치 |
| 경험치·성장표 Lv30 상한 버그(사망 경험치 오류) + 몬스터 수치 대조 + 보스 처치 확인 | 진행 중 (Codex) |
| map2·map13 일반 8조합 봇 접근 실패(봇 경로 문제 추정) | 대기: 봇 경로 개선 묶음 |

## 오늘 결과
| 항목 | 상태 |
|---|---|
| 오늘 오후 Codex 결과 요약(14:10~14:40) | 강화 30→203종, 아이템 475→567, 몬스터 119→277(+드롭610), 드롭 +20, NPC 외형 +38, 맵 3차(9맵)·4차(오만 2~5층), 테이밍 3종, 제작 18식, 상점 가격 +56종·매입 +168행, 무기 발동 5종. 대부분 봇 검증은 공용 핀 정리 후 통합 일괄 실행에서 재확인 | 통합 정리 결과 |

## 대기 (풀리는 조건 있음)
| 항목 | 왜 보류 | 풀리는 조건 / 투입 시기 |
|---|---|---|
| 동료 DLL(companion4) 원본 설치 실패: 훅 대상 코드 페이지가 런타임에 PAGE_NOACCESS(NC 보호, 첫 훅 pet_initialize 0xA81400). 펫 창 7행·동료 가방/장비·ATS 동료 편집 전부 미적용 | 인라인 패치 방식이 보호 페이지와 충돌 — 설계 필요(첫 실행 후 복호화 시점 훅, VEH/하드웨어 BP 방식 등) | Claude 설계(+Pro 교차검증) 후 Codex 구현, 헤드리스 확인 |
| 장비 최대 HP/MP 보너스 | 성장 저장에 누적될 위험 | 저장 구조 확인 후 — 성장 저장과 장비 보너스 분리 설계 |
| 귀걸이 칸 | 원본 칸 키 근거 없음 | REA로 장비 창 칸 목록 확인 |
| 방어구 추가 능력치·세트 효과·특수 효과 | 서버 스키마 없음 | 장신구·속성 저항 끝난 뒤 스키마 확장 |
| 직업 마법 1차(7종) + 지혜 물약 SP | 완료 | — |
| 직업 마법 2차 | 완료: 지원 9·속성 선택 조건부 9 (시험 75·봇 208체크) / 보류 23(계약 근거 없음) | 보류 23은 원본 시전 요청 동적 관측 때 |
| 동료 자연 속성 피격·마나 드레인↔무기 MP 공유·슬로우/마비 보정 카운터 | 투입됨 (qMagicHooks) | — |
| 맵 확장 2차 사냥맵 11개·화룡의 둥지 몬스터 | 투입됨 (qMapMon) | — |
| 봇 경로 개선 | 완료: 8조합 처치 | — |
| hunt_bot_scenarios 회귀 2건(death 이동 정체, reconnect 인벤토리 raw 비교) | 다른 작업(0964 이름 투영 등) 동시 변경 영향 추정 | 통합 회귀 |
| 공식 데이터 재수집·본토 NPC 대화 연결 | 투입됨 (qOfficial, qM5Menu) | — |
| 동료 F4 같이 줍기 | 완료(봇 7체크) | — |
| 4E95 f2·4F1A f3 의미 | 정적 분석으로 reader 미확인, 0 유지 | 헤드리스 동적 관측 |
| 테이밍 몬스터 | 늑대·세퍼드·도베르만 완료(봇 12/12). 원본 고기 제공 요청 미확인 | 헤드리스 |
| 변신 보류22형태(정책/identity 부족15 + 정책 있는 특수형태7; 전용 주문서9개) | 재대조 신규0. 치파오남/여·한복여SPR3개 보완. 특수9개 client item identity 확인/API HTTP200 빈객체. 전용 지속시간/등급·신규형태 무기 mask 등 항목별 부족 계약은 POLYMORPH_UPDATE.md 및 polymorph.json에 보존 | XML→SPR/무기 정책·주문서별 지속시간/등급 근거 확보 때. 현재 일반299는 raw16/정확 XML이름 선택 기본 경로이며 원본 창/입력/렌더는 미확인; 목록 창만으로 서버 정책까지 확정하지 않음 |
| 퀘스트 후보 4개(이올라·줄리·모리아·헤이트) | 재조사 완료/신규0개. 이올라 보상·선행, 줄리 NPC/결과, 모리아 동적 제작 선택/소비, 헤이트 Masha/Level45·Sepia/플룻 생산자 미연결. 제작/직업 자체는 제외 사유 아님 | QUEST_EXPANSION.md의 후보별 최소 관측 확보 뒤 해당 접점 작업. JSON에 출처/모리아2제작식/헤이트 보상 identity 보존 |
| 확장 회귀 2건: companion_signals 선언 추출, 장신구 HP+30 기대값 | 동료·장비 작업 진행 중 | 동료 작업·장비 추가 능력치 작업 끝난 뒤 통합 회귀 |
| 저주 장비 상태·저주 해제 | 투입됨 (Codex qCurse) | — |
| 물속 소비품 | 수중 환경 없음 | 수중 맵 지원 때 |
| 장신구 상점 판매 | 가격 근거가 L1J GM상점뿐 — 클래식은 주로 드롭 획득이라 상점 판매 안 함(오케스트레이터 판단) | 공식 상점 근거가 나오면 |
| world_m5_tests 사냥터 이동 정체 | 원인 확인: m5-bot-fjf3jx2r는209이동·1처치 후 픽업937회 실패, 실제 오류 items.210: kind/duplicate. 현 load_m1 정상·중복 해소, 봇 경로 무수정 | 정적8개PASS. packet은 별도 통합 startup 누락 파일로 요청0 실패; 최종 결과·재실행 명령은 [M5 상세](M5_MAINLAND_TOWNS.md#기본-6마을-npc60007사냥-정체-원인-수정-2026-10-28) |
| 혈맹·오만 관련 소모품 3종(806·15400·15410) | [PLEDGE](PLEDGE.md)에서 재검토: 806은 공식상 성/아지트 소유 혈맹의 귀환이며 기본 혈맹만으로 목적지가 생기지 않음. 오만2종은 혈맹과 별개 | 806: 성/아지트 소유·귀환 목적지·이동 소비 계약. 15400/15410: 오만1층/11층 목적지·입장·이동 소비 계약 확보 때. 현재 무소비 미지원 유지 |
| 드롭 잔여 40조합(옛61줄/선정60조합) | 동일 NPC·등급 확률 행 부재 또는 아이템 대응 부족 | [FILL_DROPS](FILL_DROPS.md) qDrops의 개별 사유 참고 |
| 여관(말섬·본토) 동작 | 미구현 | 동료 작업 뒤 마을 서비스 묶음 |
| M5 켄트 외 마을 직접 방문·거래 봇 확인 | 기존 본토5마을 scoped PASS, m5-bot-h36ltsch/result.json(201checks/1626requests) 보존. 신규 외형 개별렌더·원본입력은 미검증 | 60007 등록 데이터 보완·단위PASS. 기본6마을 최종 결과는 [M5 상세](M5_MAINLAND_TOWNS.md#기본-6마을-npc60007사냥-정체-원인-수정-2026-10-28) |
| 펫 동반 실제 순간이동 경로 봇 확인 | 투입됨 (Codex qPetTp) | — |
| 공식 최대 레벨·성장 공식(Lv99는 L1J 기반 임시) | 공식 근거 없음 | 공식 자료 나올 때 |
| NPC MR·대형 몬스터 피해 연결 | 완료(2026-10-28): 플레이어 119종·199행, 동료 energy_bolt→공유 magic_damage에 MonsterDef.mr 전달, world_companion_equipment_tests·magic_tests 27개 통과 | — |
| 공식 몬스터 미등록종 | 119→277종·드롭 610조합(FILL_MONSTERS.md). 수치 근거 부족 66·클라 미대응 23 | — |
| 신규 몬스터 158종 출현(spawn) | 맵 4차 작업이 맵 파일 수정 중 | qMaps4 끝난 뒤 FILL_MONSTERS_POPULATION.md 근거로 투입 |
| 몬스터 속성(약점)을 속성 무기·마법 피해에 연결 | world_combat.py 를 무기 효과 2차가 수정 중 | qWeaponFx2 끝난 뒤 |
| 몬스터 특수 행동 | 투입됨 (Codex qMonSkill, fast) | — |
| 드롭 보류 40조합 | 공식·L1J 근거 없음(FILL_DROPS.md) | 추가 자료 |
| 일반 채팅·GM 명령(.item 등) | 채팅은 게임 소켓이 아니라 Purple 커뮤니티 송신 경로로 감(REQUEST_COVERAGE_MAP) → DLL로 Purple 송신을 후킹해 GM 명령 가로채기 필요 | 동료 DLL 4차(진행 중) 끝난 뒤 DLL 5차 |
| 미확인 요청 번호 85개 | 1800초 REA로도 새 송신자 없음 | 다른 방식(동적 관측: 헤드리스에서 UI 조작 시 실제 송신) |
| 마나 드레인 마법 ↔ 무기 마나 흡수 MP 공유 | 마법 작업(qMagic) 진행 중 | qMagic 끝난 뒤 |
| 드롭 보류 60줄 재대조 | 20조합 LOCAL 승격/40조합 보류; 보류 원문35행 해결→활성34행 | 드롭48시험 OK·3분 봇13처치/17줍기 OK. 원본 화면·확률 미확인. [FILL_DROPS](FILL_DROPS.md) |
| 본토 NPC 외형 미선택52종 | 고정 SPR 부재12·전용 이름/약칭 연결 없음37·원이름 Unknown3. 전원 목록과 원문 줄은 M5_MAINLAND_TOWNS.md | 고정 client 이름→SPR/공식 외형·이름 alias 또는 객체/배치 identity 근거 확보 때; 번호 존재만으로 승격 금지 |
| 여관 방 내부 맵 입퇴장 | 내부 맵 미지원 | 맵 확장 때 |
| 무기 6칸 미확인 수치, 3018 양손 여부, 마나 흡수 등 무기 마법 효과 | 데이터 조사 완료: 기존4셀 재사용·10종 효과 note 구조화, 단위40/342봇/equip_all 통과 ([상세](ITEMS_WEAPONS_EXT.md#qweapon-데이터-한정-재조사-2026-10-28)) | 3018 두 수치·양손/발동률·피해는 근거 부족 유지, 코드 필요 효과 계약은 상세 문서에 보존 |
| 헤드리스 실행 가끔 로비 정체(약 2/8회): 로그인 bridge의 DTO setter 실행 가능성 검사 실패(dto-readiness.json 동일 상태), 동료 DLL 무관·수동 DLL에도 같은 검사 | 2026-10-29 W43 조사(runs/glfw8-ats_edit_save-claude-20261029 등). 시험 래퍼가 steps_done False를 성공(exit 0)으로 넘기는 문제도 있음 | 로그인 bridge 작업 때: 실패 순간 setter 질의 사유·보호값 기록 → 준비 시점 수정; 래퍼 종료 코드에 done 반영 |
| 동료 창 제목에 동료 이름 | DLL 미구현 | DLL 4차 |
| ATS 도움말 탭 "동료: 이름" 글자가 탭 폭에서 잘림 | 완료 | 동료·나·전환 중·대상 미확인으로 표시; 두 DLL 빌드 통과, 화면 확인 미실시 |
| 무입력 종료 원인 기록 장치(동료 DLL)를 수동 실행에 연결 | 동료 DLL 스위치 미연결 | 동료 작업의 -CompanionBridge 스위치 |
| 15분 무입력 유지 헤드리스 시험 | 사용자 지시로 미룸 | 다음 헤드리스 확인 |
| 4E95 f2, 화살 f6 값, 공식 몬스터 드롭 확률 | 근거 없음 | REA·공식 추가 조사 |
| ATS 사용 시간 정책(동료 적용 여부) | 미결정 | ATS 동료 연결 후 |
| 동료 공격 조건 칸: 원작 6개 풀다운·수치 연결 + "주변 적 n마리" 같은 새 조건 | 사용자 결정: 당장 공격 마법 안 씀(2026-10-30) | 동료 공격 마법 쓸 때 |

## 사용자 보류 (사용자 결정 대기)
| 항목 |
|---|
| 멀리 떨어진 동료 순간이동 |
