# 아이템 전량 대응 카탈로그

2026-10-26. 고정 클래식 **26.09.29.2001**의 `native-dump-v1.jsonl` item **1,266행 전부**를 보존한 데이터 준비 자료다. 제품 로더·m1·요청 경로·저장·큐를 변경하지 않았으며 게임·서버·L1J를 실행하지 않았다.

산출물은 `tools/local_original_session/data/catalog/items_all.json`이다. `loaded_by_product=false`이며 현재 `game_data.py`의 허용 종류·slot·weapon_type와 직접 호환한다고 주장하지 않는다. 메타데이터는 들여쓰기하고 item은 한 행씩 저장했다.

## 대응 방법과 출처

`MAPPING_SCOPE.md` 3장, `docs/ALL_TABLE_SEMANTICS.md` → `work/all_table_semantics/item/README.md`의 기존 의미 판정만 재사용했다. SQL 원문은 `D:/SingleLineageRef/l1j-en-classic/db/l1jdb_m10.sql`이다. weapon/armor/etcitem의 CREATE/INSERT 행을 열 이름으로 읽었고 각 후보에 양측 ID·SQL 줄·원문 이름·종류·등급·무게·그래픽을 남겼다.

1. identified/unidentified 이름토큰이 클래식 토큰과 같은 L1J 행을 모은다. 토큰 변경은 기존 `m1/items.json`과 `m2/shop_sales.json`의 명시 이름 대응만 추가하고 SQL 이름·type가 같은 등급 변형도 보존한다. 그래픽만 같은 행은 새 후보로 넣지 않는다.
2. 한국어/클라이언트 EN과 SQL EN을 나란히 보존한다. 기존 M1/M2 대응 또는 EN 완전 일치는 `name_check`에 출처를 표시한다. 그 외 토큰 일치는 독립 이름 확인이 아니므로 `unreviewed_bilingual_pair`로 남긴다. 종류 충돌은 `rejected_kind_conflict`, 그래픽·수치·토큰 차이는 `comparison.conflicts`에 남긴다.
3. 이번 사용자 기준에 따라 **이름 토큰·종류 호환·f10 원시 수치·f5/f6 양쪽 그래픽이 모두 같은 기존 후보가 있는 227행을 confirmed로 올렸다.** 대응 링크는 292개다. `mapping.confirmation`과 각 후보의 `correspondence`에 통과 기준·확정 후보를 기록했다. 여기서 무게 비교는 f10 원시값과 SQL weight의 수치 일치이고, 인간용 무게 의미·단위까지 증명한 것은 아니다. 종류는 기존 분류의 호환 범위다.
4. **네 요소 대응의 확정과 축복/일반/저주 변형 선택은 별개다.** `mapping.variant_resolution`은 unknown, `selected_l1j`는 null, native grade는 unknown으로 유지한다. 확정 227행 중 단일 통과 SQL 행은 169행, 복수 통과 변형은 58행이다. 복수 후보·동명 client ID·기존 후보 648개와 그 원문·피해·AC·출처를 보존했다. 기존 후보의 `state`는 이전 검토 상태이며 이번 대응 판정은 `correspondence.status`에서 읽는다.

## 필드 사용법과 한계

기존 M1의 `value/source/ref` 구조를 재사용했다. `id/name_token/name_ko/icon/raw_kind`는 supplied dump의 사실이며 아이콘은 **항상 f5**다. `kind/slot`은 카탈로그 정리용 로컬 분류이고 원본 enum 의미 확정이 아니다. 무기·방어구 외 소모품·이벤트·퀘스트·미명명·기타도 포함한다. `client_original`에는 원문 줄·이름 전체·원시 fields(반복/부재/숫자/wire/bytes 길이)·named_attributes를 보존했다. 해시·강화 표시토큰 메타데이터는 중복 복사하지 않고 기존 dump의 해당 줄을 재사용한다. 출처의 줄 번호는 모두 1기준이다.

**후보 수치는 `items[].mapping.candidates[].stats`에서 읽는다.** weapon.small/large/hit/damage, ac, weight, slot, weapon_type, classes, stackable, min_lvl/max_lvl/safenchant/armor_grade/bless를 각각 value/source/ref로 담았다. `raw_sql`은 추가 클래스 플래그와 모든 원열을 보존한다. UI 직업 번호는 0군주/1기사/2요정/3법사다. heal_hp는 SQL 열이 없으므로 null/unknown이며 이름만으로 핸들러 값을 만들지 않았다. 본 행의 weapon/ac/weight/classes/stackable/heal_hp/grade는 null/unknown이다. 후보 원값은 후속 개별 검토에 활용할 수 있지만 원본 계산·소비 확정값이나 성장 밸런스 티어가 아니다.

기존 원문 확인은 `f15`가 수량 집계 인수이고 `f26`이 128 보정 boolean이라는 범위다. `f10`은 기존 분석에서 price/value 후보이며 인간용 weight 의미는 미확정이다. client f10과 SQL weight가 같아도 **원시 수치 일치**로만 비교한다. f15/f26도 raw로 남기고 SQL 무게 단위와 임의 변환하지 않는다. f26을 stackable의 증명으로 쓰지 않는다. f4/f17/f32/f46 의미도 새로 확정하지 않았다. L1J armor.grade와 bless는 서로 다른 열이다. native slot은 기존 M1 후보 mask 1/2/4/8/32/64/256만 재사용하며 그 외 장신구 mask는 unknown이다.

각 필드에 `status/scope`를 추가했다. 이름 토큰·한국어 이름·아이콘·ID는 공급된 값이 있는 경우 client/confirmed이고, 이름 부재 25행은 absent다. `client_facts`에서 f45의 검증된 분류 enum 코드 900행과 f15 수량 집계 인수 1,266행을 confirmed로 기록한다. f13 반복값 172행·f17 원시값 206행·f10 원시값 1,266행은 confirmed_raw다. 이는 저장된 값의 확인이며 **착용 직업·부위·무게 의미 확정이 아니다.** 의미 상태는 각각 unknown/candidate로 구분했다. f26은 654행에만 공급되며 부재를 false·자유 착용·기본 직업으로 채우지 않는다. 읽기 쉬운 `kind/slot`은 local_policy 분류로 유지한다. 피해·AC 수치는 계속 후보의 L1J 출처를 사용한다.

## 통계

- client 1266행: **confirmed 227, candidate 258, unmapped 781**; 이름 없음 25행.
- 기존 candidate 485행 중 227행 승격, 확정 대응 292링크. 고유 L1J 선택 0행·native 등급 의미 확정 0행.
- 후보 연결 648개: 종류 호환 645, 종류 충돌 거절 3; 복수 후보 client 108행.
- 원 SQL 행: weapon 331, armor 624, etcitem 1861.

| 정리용 종류 | 전체 | confirmed | candidate | unmapped |
|---|---:|---:|---:|---:|
| ammo | 9 | 0 | 5 | 4 |
| armor | 206 | 96 | 56 | 54 |
| container | 294 | 0 | 3 | 291 |
| currency | 1 | 1 | 0 | 0 |
| etc | 370 | 10 | 90 | 270 |
| food | 11 | 8 | 1 | 2 |
| light | 3 | 3 | 0 | 0 |
| potion | 84 | 0 | 16 | 68 |
| scroll | 64 | 0 | 8 | 56 |
| spellbook | 110 | 53 | 50 | 7 |
| wand | 9 | 0 | 2 | 7 |
| weapon | 105 | 56 | 27 | 22 |

종류별 합계는 1,266행이다. family는 f48=1 무기105, f17존재 방어구/장신구206, 기타955행으로 정리했다. f48=0 탄약9행은 무기와 구분한다. etc는 미해독·기타 분류를 포함하며 임의로 소모품 의미를 부여하지 않았다.

## 미대응 781행의 원인 분류

`mapping.unmapped_diagnosis`에 아래 코드를 기록했다. 기존 미대응은 모두 미대응으로 유지하며 새 후보를 만들지 않았다.

| 코드 | 행 수 | 확인한 사실 |
|---|---:|---|
| token_absent_no_structural_peer | 741 | 공급된 SQL 2,816행에 같은 이름 토큰이 없고 같은 잠정 family·f10·f5·f6 조합도 없음 |
| token_absent_structural_peer | 13 | 이름 토큰은 없지만 같은 잠정 family·f10·f5·f6 조합이 있음; 토큰 불일치 진단용이며 동일 아이템으로 확정하지 않음 |
| client_name_token_unavailable | 25 | 공급된 클라이언트 이름 토큰이 없어 토큰 대응 불가 |
| token_present_kind_conflict | 2 | 같은 토큰 SQL 행은 있으나 기존 종류 분류와 충돌 |

**클래식 전용인지, L1J에 해당 아이템 자체가 없는지는 unknown이다.** 고정 L1J 자료에서 토큰이 없다는 사실만으로 버전 전용이나 아이템 부재를 단정하지 않았다. 구조가 같은 행도 이름·효과가 다를 수 있으므로 진단에만 남겼다.

## 주요 대응과 미확정

- 오크족 단검40/$13은 weapon1과 저주형200001을 보존한다. client1은 아탐이며 weapon1로 바꾸지 않는다.
- 장검3·빨간 물약14의 토큰 변경은 기존 명시 대응만 재사용했다. 가죽 재킷103의 클래식 icon62와 L1J invgfx1196 차이를 보존한다.
- 화살29/30 및 같은 토큰의 추가 행은 각각 별도 행이다. 토큰·그래픽이 같아도 무게 원시값·등급 미확정 때문에 한 ID로 합치지 않는다.
- 흑단 막대21과 Wand of Blink40009는 그래픽118/28만 같고 토큰·이름·효과가 다르므로 그래픽 fallback으로 연결하지 않는다.
- 이름 미검토 후보는 한국어↔영문 이름·효과 확인이 남았다. 네 요소 대응이 confirmed여도 독립 번역·효과·native 등급은 확인된 것으로 확대하지 않는다. native 등급 생산자·소비자 관측은 고유 변형 선택에 필요한 별도 입력이다. 이번에는 새 RE나 게임 실행을 하지 않았다.

## 재현 가능한 짧은 인라인 점검

프로젝트 루트 PowerShell에서 실행한다. 영구 추출기·guard·검증 도구를 만들지 않았다. 생성 방법은 위 규칙과 JSON `method/grouping_policy/reference_paths`에 남겼다.

```powershell
$OutputEncoding=[System.Text.UTF8Encoding]::new($false)
@"
import json, collections
from pathlib import Path
x=json.loads(Path('tools/local_original_session/data/catalog/items_all.json').read_text(encoding='utf-8'))
rows=x['items']
src=[json.loads(s) for s in Path(x['reference_paths']['native-dump']).read_text(encoding='utf-8').splitlines() if json.loads(s)['table']=='item']
assert len(rows)==len(src)==1266 and len({r['id']['value'] for r in rows})==1266
for r,original in zip(rows,src):
 raw=r['client_original']
 assert raw['id']==original['id'] and raw['name']==original.get('name')
 assert raw['fields']==[{k:v for k,v in f.items() if k!='sha256'} for f in original['fields']]
 assert r['icon']['value']==next(f['scalar'] for f in raw['fields'] if f['number']==5)
print(collections.Counter(r['mapping']['status'] for r in rows))
for cid in [1,3,7,14,29,30,40,103]:
 r=next(r for r in rows if r['id']['value']==cid)
 print(cid,r['name_ko']['value'],r['icon']['value'],[(c['l1j_table'],c['l1j_id'],c['stats']['bless']['value']) for c in r['mapping']['candidates']])
"@ | & C:/Users/Chansol/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe -X utf8 -B -
```

기존 일회성 데이터 점검 결과는 JSON `verification.prior_verification`에 보존했다. 이번 변경 후 같은 지정 Python의 `-X utf8 -B -` 인라인 점검은 **PASS_DATA_CHECK_ONLY**였다. 변경 전 deep-copy 대비 원문1,266행·기존 후보648개·raw SQL·피해/AC·출처 불변을 확인했다. 별도 독립 점검에서도 원문 ID/이름/fields/named_attributes, f5/f10/f13/f15/f17/f45 값, f5/f6/f10 SQL 비교, 확정 조건과 전행 상태의 동치, 292링크·227/258/781 집계·미대응 분류 합계, 피해/AC의 L1J 값과 출처, selected_l1j/grade 미확정 유지를 확인했다.

지정 Python으로 `-X utf8 -B -m tools.local_original_session.game_data_tests` 실행 결과 **5 tests OK**였다. 게임·서버·실제 전투·아이템 소비·패킷·저장 시험은 **UNRUN**이며 데이터 대응을 플레이 PASS로 표시하지 않는다. 제품 로더는 이 카탈로그를 아직 읽지 않는다.
