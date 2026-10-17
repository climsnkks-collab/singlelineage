# npc.bin 전체 필드 의미 추적

2026-10-09 현재 `CommonNPCInfo`의 **26개 필드 모두 저장 타입·오프셋·parser·serializer·copy·기본값을 추적**했다. 실제 소비 코드로 새로 연결한 것은 표시 이름 `f3`, 자동 대상 우선순위 `f22`, 자동 선제 대상 제한 `f26`이다. 다른 필드는 공식 자료·현재 자산·명명된 구버전 자료의 대조 근거를 별도로 기록한다. 모든 필드의 원래 proto 이름을 복원한 것은 아니다.

현재 `npc.bin`은 951레코드/14,201필드다. `f4~18`은 모든 현재 NPC 레코드에서 미기록이다. C++ 생성 코드의 초기값 0/null은 실제 몬스터 능력치 0이라는 뜻이 아니다. HP·MP·AC·MR·EXP·레벨·피해 공식을 이 슬롯에 임의 배정하지 않는다.

## 전체 26개

오프셋은 파일 위치가 아니라 **디코딩된 CommonNPCInfo 객체 기준**이다. `코드 확인`은 지정한 코드 경로의 기능, `강한 대조`는 데이터 대응으로 지지되는 해석, `후보`는 아직 의미가 확정되지 않은 가설이다.

| 필드 | 객체 오프셋 | 저장 타입 | 현재 기록 NPC 수 | 의미·판정 |
|---|---:|---|---:|---|
| f1 | +40 | uint32 | 951 | NPC 템플릿/카탈로그 ID. 현재 951개에서 wrapper key와 동일. 실제 조회는 Monster 템플릿 ID→wrapper key이며 raw f1 소비와 구분 |
| f2 | +44 | uint32 | 951 | **외형/SPR ID 강한 대조**. 951/951이 현재 SPR ID에 존재. f2→실제 world appearance/draw 경로는 미확정 |
| f3 | +30 | string | 951 | **표시 이름 참조 코드 확인**. `$59`→오크 등. 아이템 추가 설명·소환 몬스터 목록에서 소비 |
| f4 | +48 | int32 | 0 | 의미 미확정, 현재 미기록 |
| f5 | +4C | int32 | 0 | 의미 미확정, 현재 미기록 |
| f6 | +50 | int32 | 0 | 의미 미확정, 현재 미기록 |
| f7 | +54 | int32 | 0 | 의미 미확정, 현재 미기록 |
| f8 | +58 | uint32 | 0 | 의미 미확정, 현재 미기록 |
| f9 | +5C | uint32 | 0 | 의미 미확정, 현재 미기록 |
| f10 | +60 | uint32 | 0 | 의미 미확정, 현재 미기록 |
| f11 | +64 | uint32 | 0 | 의미 미확정, 현재 미기록 |
| f12 | +68 | uint32 | 0 | 의미 미확정, 현재 미기록 |
| f13 | +6C | uint32 | 0 | 의미 미확정, 현재 미기록 |
| f14 | +70 | int32 | 0 | 의미 미확정, 현재 미기록 |
| f15 | +74 | int32 | 0 | 의미 미확정, 현재 미기록 |
| f16 | +78 | int32 | 0 | 의미 미확정, 현재 미기록. f19와 다른 슬롯 |
| f17 | +7C | int32 | 0 | 의미 미확정, 현재 미기록 |
| f18 | +38 | message | 0 | **ElementalResistance 클래스 확인**. 속성저항 메시지, 자식 4개. 원소 순서·전투 소비는 미확정 |
| f19 | +80 | int32 | 951 | **lawful/성향 강한 대조**. 부호 타입은 코드 확인. AC·레벨 의미는 확인되지 않음 |
| f20 | +8C | bool | 951 | **큰 몬스터 여부 강한 대조**. 공식 `big` 14/14 일치 |
| f21 | +18 | repeated message | 449 | **CommonNPCInfo_DropItemT 클래스 확인**. 4,691개 드롭 아이템 항목; 자식 의미 아래 기록 |
| f22 | +84 | enum int32 | 951 | **자동 대상 선택 우선순위 코드 확인**. 허용값 0/1/2. 설정 +59C 활성화 시 2를 우선; enum 이름은 미확정 |
| f23 | +88 | int32 | 951 | 종족/계열/그룹 분류 후보. 공식 레벨과 4/333만 일치하므로 레벨로 쓰지 않음 |
| f24 | +8D | bool | 951 | **보스 표시 후보**. true 39개가 보스 이름 군에 집중. 실제 소비·원래 이름은 미확정 |
| f25 | +8E | bool | 951 | **공식 사전의 언데드 표시와 강한 대조**. 정확 대응 333/333 일치(언데드 38) |
| f26 | +8F | bool | 951 | **자동 선제 공격 대상 제한 코드 확인**. 최근 자신을 공격한 대상은 이 제한의 예외. true 29개 |

## 자식 필드

`f18`의 RTTI는 `ElementalResistance`다. 자식 f1/f2/f3/f4는 각각 객체 +18/+1C/+20/+24의 int32다. 현재 NPC 파일에는 부모 자체가 없어 값 표본이 없으며, 어느 자식이 불·물·바람·땅인지는 확인하지 못했다.

`f21`의 RTTI는 `CommonNPCInfo_DropItemT`다.

| 자식 | 자식 객체 오프셋 | 타입 | 의미·근거 |
|---|---:|---|---|
| f21.f1 | +18 | uint32 | 아이템 ID 강한 대조. 4,691/4,691개가 현재 item.bin에 존재 |
| f21.f2 | +1C | int32 | **0=축복, 1=일반, 2=저주 강한 대조**. 공식 상세 14개/127드롭 표시 항목에서 아이템 ID·등급 조합 집합이 모두 일치 |

원문 중복을 보존한다. 데스나이트는 현재 48항목/고유 ID·등급 조합 41개, 공식 상세는 41항목/41조합이다. 중복 수를 드롭 확률이나 수량으로 해석할 근거는 없다. 자식 f2는 signed32 저장 필드이며 enum 이름이 코드에 남아 있다는 뜻은 아니다. 공식 자료는 [데스나이트 상세 응답](https://api-goats.plaync.com/linclassic/v2.0/game/monster/63?locale=ko-KR)과 저장된 13개 추가 상세 원문을 사용했다.

## 실제 소비 코드

### 조회와 이름

`GetNpc` RVA 3722B0의 ABI는 RCX=카탈로그, RDX=16바이트 shared_ptr 결과 저장소, R8D=템플릿 ID다. RAX는 결과 저장소 주소이며, 첫 qword가 실제 CommonNPCInfo다. raw 객체 주소를 RAX와 혼동한 오프셋 검색은 의미 근거로 쓰지 않는다. 로더는 wrapper key를 map에 삽입하고 현재 f1은 이 key와 951/951 동일하다.

`f3`(+30)을 읽는 실제 소비자는 `ItemExtraDescDataTable`의 527A20→527C15→527C52와 `SummonedMonsterListLayout`의 B1E4F0→B1F4C9→B1F509다. 문자열 참조를 formatter 339AB0에 전달한다. 모든 Actor HUD 이름이 이 필드에서 온다는 확대 해석은 하지 않는다.

### f22: 자동 대상 우선순위

43BCA0은 HUD가 아니라 `lineage::bt::FindTarget`으로 이어지는 ATS 대상 선택 경로다. 43BCDC의 ATS 설정 +59C가 켜지면, 43BEAD에서 NPC+84가 2인지 비교하고 43BEBC에서 candidate+A를 기록한다. 허용 enum 범위는 parser DEA6D0과 보조 범위 15E1B50의 0..2로 확인했다.

이 후보는 43D441의 정렬 경로로 들어가며 comparator 445AE0/446779에서 **아이템 우선 → 최근 공격자 → 설정이 켜진 f22=2 → 거리 제곱** 순으로 비교된다. 값 2의 인간용 이름, 0과 1의 차이는 미확정이다. 구버전 agro와도 상관은 있지만 이것만으로 현재 0=비선공/1=동족선공/2=선공 같은 이름을 부여하지 않는다.

### f26: 자동 선제 공격 후보 제한

43BE85→42B950은 대상 UID가 최근 자신을 공격했는지 검사한다. 43BEC0/43BEC7에서 **최근 공격자가 아니고 NPC+8F가 true이면** candidate+10을 0으로 기록한다. 43D29D/43D2A2는 이 후보의 자동 대상 큐 삽입을 건너뛴다.

최근 공격 기록은 ATSSubsystem 429D50이 등록한 `SC_ATTACK_NOTI` 처리기 42DDA0에서 출발한다. 통지 source UID(f2/+18)의 target UID(f3/+28)가 로컬 CharacterDataSubsystem UID(+6D8)와 같을 때만, ATS+338 map에 공격자 UID와 시각을 기록한다. 42B950은 나노초 차이를 정수 밀리초로 바꿔 **5,000ms 이하**인지 검사한다(상수 126EC70의 double 5000.0). 따라서 약 5초 이내 공격자는 f26 제한을 통과하며 이후 조건을 검사한다.

별도 조건으로 `ActionComponent+40 != 0x78`도 검사한다. 이 component의 타입은 ActionComponent이며 값 0x78의 동작 이름은 미확정이다. 이 분석은 **클라이언트 ATS 자동 대상 선택 규칙**을 확인한 것이며 수동 공격 금지나 서버 NPC의 선공 AI 전체를 복원한 것은 아니다.

HUD 이름 표시 설정은 ActorHudManager 9861E0의 `_hoverNpcDesc`, `_inDoorNpcDesc`, `_alwaysVisibleMonsterDesc` 경로에 있다. f26을 HUD 이름 표시 플래그로 붙일 코드 근거는 없다.

## 자료 대조의 한계

f19의 signed32는 parser·copy·MOVSXD serializer로 확인했다. 오크/해골/데스나이트의 -2/-12/-120은 [핀 고정 L1J DB](https://github.com/l1j-en/classic/blob/103e6f6c9dd83545959d8e87d3f59f8de1f40ef0/db/l1jdb_m10.sql)의 lawful과 일치하고 AC=10/3/-67과 다르다. 공유 표시 토큰 703개에서 any-lawful 368개, any-AC 49개다. 이 명명 자료는 구버전 서버 구현으로, 현재 NC 코드의 원래 속성명·계산식을 확정하지 않는다. [f19 상세 추적](NPC_F19_SEMANTICS.md)에 버전차·동일 토큰 복수 후보를 보존했다.

f20은 공식 상세 `big`와 14/14, `damageable`과 11/14 일치한다. 곰·오염된 엔트·셸로브는 big=true, damageable=false여서 두 해석을 구분할 수 있다. f25는 공식 ID·한국어 이름 정확 대응 333개에서 `formName==언데드`와 333/333 일치한다. 데스나이트는 이 표시와 f25가 모두 false다. 표시 분류를 턴 언데드 성공식·은 무기 추가 피해 규칙까지 확대하지 않는다. 공식 원문은 [몬스터 목록 응답](https://api-goats.plaync.com/linclassic/v2.0/dict/search/monster?searchKeyword=&locale=ko-KR&page=1&size=30)과 저장된 전량 351레코드를 사용했다.

f23의 계열 후보는 과거 family 이름과 일부 군집 대응이 있지만 기본값 1에 여러 종류가 섞인다. f24의 보스 후보도 명명된 목록의 집중에 근거하며 실제 소비 코드는 아직 없다. 구버전 hard·pickup 필드와의 단순 일치율은 false=0 표본이 많아 과대평가되므로 f24=hard, f26=pickup으로 확정하지 않는다.

## 검증과 산출물

[Root 독립 검토](../work/npc_field_semantics/root-review.json)는 **25,113검사 PASS**, 원본 명령어/블록 9,146개, raw NPC951·item1266·드롭4691·공식 정확대응333·상세14개를 재검사했다. parser tag·offset·storage type과 RTTI/vtable을 실제 복구 바이트에서 다시 읽고, 현재 파일의 census·이름·드롭 ID/등급 대응을 별도 wire parser로 검증했다. 입력 핀 전후 불변이다. 게임 실행·프로세스 조작·RAM·UAC·제품/서버 룰 변경은 없다.

- [전체 저장 구조·생성 코드](../work/npc_field_semantics/layout/report.json), [26필드 저장 표](../work/npc_field_semantics/layout/field-table.md)
- [실제 소비 역할](../work/npc_field_semantics/consumers/fields.json), [소비 그래프](../work/npc_field_semantics/consumers/graph.json), [명령어 창](../work/npc_field_semantics/consumers/windows.json)
- [공식·구버전 대조](../work/npc_field_semantics/hypotheses/summary.json), [대조 가설 26필드](../work/npc_field_semantics/hypotheses/all26-hypotheses.json)
- [독립 검토 도구](../tools/npc_field_semantics/review.py)

남은 의미 추적은 미기록 f4~17의 비생성/inlined/virtual 소비, f18 자식의 원소 순서, f2 실제 외형 전달, f19/f20/f23/f24/f25 비생성 소비다. 이번에 닫은 3개의 GetNpc direct caller 밖 모든 경로가 없다고 주장하지 않는다. 현재 HP/MP/AC/MR/EXP/레벨 기본값과 전투·드롭 생성식은 여전히 미확정이다.
