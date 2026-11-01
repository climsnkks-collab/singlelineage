# 클래식 방어구 확장 데이터

지정 방어구 데이터 추가 작업. 전체 제품 중지 상태를 해제하지 않는다.

## 반영 범위

2026-10-28. 기존 `items.json`의 ID·값을 변경하지 않고 아래 확장 파일만 추가했다. 서버·시험 코드·저장·프로필·기동 파일은 변경하지 않았다.

| 파일 | 수량 | 상태 |
|---|---:|---|
| `tools/local_original_session/data/m1/items_ext/armor.json` | 116 | 기존 `_items_dir` → `_items` → `ItemDef` 로드 |
| `tools/local_original_session/data/m1/item_gfx_ext/armor.json` | 116 | 기존 `world_visibility.item_gfx()` 로드 |
| `tools/local_original_session/data/m1/items_ext_pending/accessories.json` | 56 | 제품 미로드, 슬롯 확장 대기 원문 |

신규 방어구는 투구26·갑옷40·티셔츠1·망토8·장갑10·부츠14·방패17이다. 기존 7부위 방어구16개와 ID가 겹치지 않는다. 같은 이름의 서로 다른 클래식 ID(투구90/229, 사슬 갑옷96/167 등)는 공식 ID와 native 이름이 일치하는 별도 템플릿으로 유지한다. 축복·저주 인스턴스 등급을 템플릿에서 만들어 내지 않았다.

보류56개는 반지17·목걸이18·벨트21이다. 귀걸이는 수집된 공식 사전에 0개여서 생성하지 않았다. 55개는 고정 native와 일치하며, **해골 목걸이614 한 개는 공식 전용, client_id=null**이다. 이 경우 공식 ID를 클라이언트 ID로 전용하지 않고 원문만 보존했다. 이름이 ‘에이션트 자이언트의 반지’인744는 공식 `categoryName=벨트`를 따랐다.

## 선정·출처

고정 `data/catalog/items_all.json`의 native 원문과 `data/official/items.json`의 `exact_id_and_name` 대응을 재사용했다. 공식 원문은 각 행의 `work/official_data/raw/item/{id}.json`이며 API URL과 수집 시각·해시는 기존 공식 테이블에 있다. 새 외부 API 수집이나 L1J fallback은 하지 않았다. 액세서리는 필요한 공식 원문과 source 메타데이터를 pending 안에도 보존했다.

- 신규116개 모두 AC·안전 한계/인챈트 불가가 공식 원문이고, ID·이름·아이콘·바닥 그래픽·raw 무게는 native다. 슬롯은 공식 부위와 기존 `slot_keys`를 연결한 `local_policy`이며 native f17의 새 의미 증명이 아니다. catalog 부위와도116개 전부 일치한다.
- 직업은 공식86개(74.14%), 기본정책30개(25.86%)다. 후자는 공식 `classNames`와 native f13이 모두 부재하여 기존 M1의 전직업 기본값 `[0,1,2,3]`을 `local_policy`로 표시했다. 원문에 전직업 명시가 있는 것으로 주장하지 않는다. 번호는0 군주/1 기사/2 요정/3 마법사다.
- 로드되는13필드×116행=1508셀 기준 출처는 client580(38.46%)·official434(28.78%)·local_policy494(32.76%)·l1j0이다. 방어구 비중첩·무기피해 없음·즉시회복 미사용도 기존 backend 기본정책으로 구별했다. `note`에 보존한 능력치 원문은 이 로드 셀 집계에 포함하지 않았다.
- 기존 `items.json`의 방어구16개는 중복 제외했다. 공식에는 있으나 고정 native에 없는 방어구14개는 제외했다: 611,1286–1291,1449,1487,1488,12652–12655. 그래픽·클라이언트 ID 대응을 임의 생성하지 않았다.
- native 단독 방어구/액세서리19개도 제외했다: GM156/240/288/10002, 이름 부재10023, `%i` 변형12037–12040, 황금알 모자12193/12194, 기간제12471/12472/12582/12583, 청명한 비늘 갑옷12605–12608. 앞쪽 GM·기간제·익명 항목은 일반 클래식 장비로 넣지 않았고, 나머지는 공식 사전 대응·일반 입수 여부가 미확인이다. 자료 부재만으로 모든 항목을 이벤트/캐시라고 확정하지 않는다. 일반·퀘스트·보스 장비는 포함하되 이 파일이 입수/드롭/상점 판매를 추가하지는 않는다.

## 단위와 실제 소비

`weight.value`는 **item.bin f10 raw 정수**다. 1000raw=부담1이며 신규116개 모두 `f10 == 공식 weight×1000`이다. `ITEM_WEIGHT.md`는2026-10-26 이전 L1J fallback 설명이다. 이번에는 최신 사용자 지정과 현 `items.json`의 native f10 정책을 우선했다. `world_weight`의 인스턴스 수량 곱셈 후 나눗셈·최소1 등 기존 backend 계산정책은 변경하지 않았다. f15/f26을 무게나 stackable 근거로 새로 해석하지 않았다.

공식 `ac.origin`의 부호를 반전해 서버의 음수 AC 기여로 넣었다(전부 enchantLevel0, extra0). `world_stats.calculate_stats`는 장착 방어구 AC와 기존 강화 AC를 소비한다. `classes`는 기존 장착 직업 제한, `icon`은 인벤토리, `weight`는 기존 부담 계산에 쓰인다. `kind/slot/stackable/weapon/heal_hp`도 기존 `_items` 필수 형식이다.

`safe_enchant`는105개에 숫자,11개에 null이다. null11개(644,651,654–657,667–670,12118)는 공식 **인챈트 불가**이며 안전0과 다르다. 안전0인 해골투구320·골각방패326·뼈갑옷331는0을 유지했다. 현재 `world_feature_items`의 강화 caller는 `ItemDef.safe_enchant`를 `EnchantTarget`에 전달하지 않고, 신규116개가 `enchant.json`에도 없다. 따라서 **현재 caller 형태에서116개 전부 `unresolved_target_safety`로 거절**된다. 숫자가 로드되었다고 신규 장비 강화가 연결된 것은 아니다. 확률·특수 스크롤 허용·재료·자격정책은 추가하지 않았다.

그래픽은 native f5/f6을 그대로 기록했다. f5는 기존 인벤 아이콘 계약, f6은 기존 아탐14를 기준으로 쓰던 바닥 appearance 후보다. 로더의116개 값 일치는 확인했지만 이116종의 화면·바닥 렌더링은 **UNKNOWN**이다.

## 스키마 확장이 필요한 능력치

공식 `options`가 있는44행, `set`이 있는38행, `description`이 있는34행은 각 행 `note` 문자열 안에 원문 JSON으로 보존했다. 추가 능력치를 임의0으로 평탄화하거나 AC에 합산하지 않았다. 원문 부재는 효과가 없다는 증명이 아니다.

현재 `ItemDef`와 방어구 소비에는 다음 계약이 없다.

- STR/CON/DEX/INT/WIS/CHA, 최대HP/MP, HP/MP회복, MR·직업조건 MR/회복, 4속성저항, 대미지감소.
- 근거리/원거리 명중, 장비별 헤이스트, 반사, 수중호흡, 투명, 투구를 통한 마법/MP할인, 정화 머리띠의 특수 가시성.
- 세트 구성·필요 개수·AC/HP/MP/회복 보너스·세트 변신, 공식 `equipLevel` 제한(양수19행).
- 반지 좌우/목걸이/귀걸이/벨트 슬롯 키, 중복 착용 규칙, 장착/해제·저장/복원·능력치 수명. pending56개는 이 작업이 먼저 필요하다. native 미대응614에는 별도 클라이언트 대응도 필요하다.

`hit/dmg_bonus`는 `_items`가 읽을 수 있지만 `world_stats`/전투는 선택 무기의 값만 사용하므로 방어구 추가 명중·피해를 그 필드에 억지로 넣지 않았다. `note`는 `_items`가 읽거나 Source로 보존하지 않는 원문 자료다. 현재 방어구는 기본 AC와 위에서 구별한 지원 필드만 동작하며 완전한 클래식 장비 효과로 표시하지 않는다. 이번에는 서버 스키마를 변경하지 않았다.

## 실행 검증

게임·클라이언트·서버·포트·캡처는 실행하지 않았다. 기존 순수 단위시험만 실행했으며 테스트 파일은 수정하지 않았다.

```powershell
python -X utf8 -B -m unittest tools.local_original_session.game_data_tests tools.local_original_session.world_weight_tests tools.local_original_session.world_stats_tests tools.local_original_session.world_enchant_tests
```

실제 결과: **47 tests, OK**(0.239s).

```powershell
python -X utf8 -B -m unittest tools.local_original_session.world_ground_items_tests tools.local_original_session.world_visibility_regression_tests
```

실제 결과: **21 tests, OK**(0.162s). 합계68개다. 별도 검사기·guard·새 시험 파일은 만들지 않았다.

한 번의 `python -X utf8 -B -` stdin 관측으로 `game_data.load_m1()`와 `world_visibility.item_gfx()`를 읽어 신규116개 로드·부위/직업/AC/raw무게·그래픽116개 일치·pending 미로드를 확인했다. 같은 관측에서 현 caller와 같은 `EnchantTarget(id,'armor',0)`의116개 거절 사유가 모두 `unresolved_target_safety`였다. 동시 다른 확장 작업을 포함한 당시 전체 로드 수는279개이며 이 작업의 고정 수량은116개다. 이는 파일 로딩·기존 순수 계산·거절 범위의 확인이며 로그인·입수·착용 패킷·실제 능력치·저장·화면의 정식 PASS가 아니다.
