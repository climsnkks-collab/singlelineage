# Classic job spell data expansion

## Scope and sources

`tools/local_original_session/data/m3/player_spells.json` now includes the job specific Classic spells missing from the existing mage centered catalog. The 41 additions are keyed to the fixed client spell ID and exact name mapping in `tools/local_original_session/data/official/spells.json`:

| Job | New spells |
| --- | ---: |
| Knight | 5 |
| Elf | 31 |
| Prince | 5 |
| **Total** | **41** |

The existing 39 spell records remain in place. Their official learning rows already include eligible Prince, Knight, and Elf levels for shared magic. The expanded catalog has 80 unique spell keys.

Official spell stage, required level, MP cost, target text, duration, textbook ID/name, and description are sourced per record from the preserved NC Lineage Classic official dictionary snapshots in `tools/local_original_session/data/official/spells.json`, collected from `https://api-goats.plaync.com/linclassic/v2.0/game/spell/{id}?locale=ko-KR`. The source file retains the official raw path, collection time, and SHA-256. Client ID/name mapping uses the fixed client dump recorded in that source file. Textbook item IDs and graphics for the missing books are in `data/m1/items_ext/spellbooks.json` and `data/m1/item_gfx_ext/spellbooks.json`; those rows cross-reference the official textbook data and fixed client item catalog.

## Effect classification (1차 기록)

The 41 source records remain unchanged and data only. `world_magic.runtime_spell()` overlays the seven closed effects below in memory; the remaining 34 retain unsupported learning/casting. The `effects.kind` source classification alone is not a runtime claim.

| Effect data key | Count | Meaning |
| --- | ---: | --- |
| `buff` | 19 | Fits the existing buff family |
| `status` | 5 | Fits the existing status family |
| `heal` | 2 | Fits the existing healing family |
| `damage` | 1 | Fits the existing damage family |
| `CAST_UNSUPPORTED` | 14 | Needs the named effect below |

| Spell key | Spell | Required effect |
| ---: | --- | --- |
| 86 | 쇼크 스턴 | `stun` |
| 90 | 카운터 배리어 | `counter_attack` |
| 112 | 트루 타겟 | `tracking_mark` |
| 115 | 콜 클랜 | `clan_member_summon` |
| 117 | 런 클랜 | `clan_teleport` |
| 129 | 바디 투 마인드 | `hp_to_mp_conversion` |
| 130 | 텔레포트 투 마더 | `world_tree_teleport` |
| 131 | 트리플 애로우 | `multi_hit_arrow` |
| 144 | 리턴 투 네이쳐 | `summon_dismissal` |
| 145 | 블러드 투 소울 | `hp_to_mp_conversion` |
| 153 | 서먼 레서 엘리멘탈 | `elemental_summon` |
| 160 | 에이리어 오브 사일런스 | `area_silence` |
| 161 | 서먼 그레이터 엘리멘탈 | `greater_elemental_summon` |
| 169 | 워터 라이프 | `heal_amplification` |

## Unknowns and validation

At the original data-collection stage, official reuse was absent, HP cost remained null when omitted, numeric ranges were text-derived candidates, and nonnumeric/self ranges remained null. Those source fields remain intact; omission is not treated as zero. The original stackability of spellbook IDs 1492–1496 is unconfirmed and remains `local_policy`. At that stage effect behavior, learning, casting and visuals were untested. The runtime/socket subset below supersedes only that subset's untested status; original-client equivalence remains unverified.

Validated with:

```powershell
python -X utf8 -B -c "from tools.local_original_session import game_data, world_magic; m1=game_data.load_m1(); c=world_magic.load_catalog(); m=world_magic.PlayerMagic(c); print(len(m1.items), len(m.spells), len(m.books))"
```

Historical data-load result: `475 80 80`. This was catalog loading only, before the runtime subset below.

## 직업 마법 런타임 지원 범위 (2026-10-28)

| 직업 | 신규 지원 키 | 실제 소비 | 신규 미지원 키·이유 |
| --- | --- | --- | --- |
| 기사 | 87 리덕션 아머, 88 바운스 어택 | 87은 NPC 물리/마법 피해를 HP 차감 전에 감소, 88은 기존 stats→combat profile의 근접 명중+5 | 86 스턴: 무기 조건·확률/지속 선택 근거 미완. 89 ER: ER 실제 회피 소비자 없음. 90 카운터: 양손검 판정·반격 계약 미완 |
| 요정 | 128 레지스트 매직, 129 바디 투 마인드, 136 클리어 마인드, 137 레지스트 엘리멘트, 145 블러드 투 소울 | MR+10, WIS+3와 자연회복/파생MR, 전속성 저항+10, HP8→MP2 및 HP50→MP15. MP 상한 clamp·fullMP/치명적 HP 비용 무소비 거절 | 130 세계수 목적지, 131 실제 연사/탄약, 144 소환 해제, 146 소속 속성, 147–151/154–158/162/163/165/167/169–174 속성 선택·파티·전용 소비 계약, 152 1회 MR 소비, 153/161 정령 소환, 160 범위 침묵/채팅 계약 미완 |
| 군주 | 기존 공유 마법의 공식 직업/레벨 허용을 재사용 | 대표 Shield2 학습→자기 AC-2 시전 | 전용112 표식 wire/추적 소비 없음, 113/116은 파티 모델 없음(자기 버프로 축소하지 않음), 115/117 혈맹원·이동/소환 계약 없음 |

신규 전용 14개 중 닫힌 계약은 HP→MP 변환129/145 두 개다. 나머지12개는 무소비 미지원이다. 정령 속성을 임의 선택하거나 파티/혈맹 효과를 자기 효과로 대체하지 않았다. 새7개와 기존38개를 합쳐 런타임 지원은45개이며 원본 동등성 판정이 아니다.

공식/고정 클라이언트 원문은 보관된 `data/official/spells.json`의 각 ID·`source_snapshot`과 API `/spell/{87,88,128,129,136,137,145}` 응답을 재사용했다. 공식 직업/학습레벨·기본MP·명시HP·지속시간·효과 수치를 우선한다. 공식에 없는 HP/MP·재료 없음·재사용은 `D:/SingleLineageRef/l1j-en-classic/db/l1jdb_m10.sql`의 **이름 일치 행** 88/89/129/130/137/138/146을 LOCAL backend 정책으로 쓴다. Classic spell ID와 SQL ID가1 차이나며 item UID로 쓰지 않는다. 공식 무HP 표기를0으로 간주하지 않으며, 리덕션HP50·바운스HP120은 SQL의 명시적 별도 LOCAL fallback이다. 공식 소비가 있는 MP10/10/10/0/10/5/0·변환HP8/50·정령옥 각1은 SQL과 달라도 공식 값을 사용한다.

재사용은 SQL의 3000/5000/0/400/0/0/1200ms를 적용하며0 세 항목은 기존 서버의 LOCAL 기본1초를 사용한다. 공식 재사용이 확인됐다는 뜻은 아니다. 지속효과는 같은 키 갱신, 중첩 없음, 기존 magic.json 남은시간/실시간 저장·복원·사망/만료/정리 소유자를 사용한다. 테스트만 기존10초 override를 사용한다.

책 raw 무게는 기존 M1 로더·고정 dump를 확인했다. 1861/1862는7000 (`native-dump-v1.jsonl:1517/1518`), 570/571/573/574/576은5000(1341/1342/1344/1345/1347행)이다. `data/catalog/items_all.json`과 `ITEM_WEIGHT.md`의 기존 f10 LOCAL 무게 정책을 재사용한다. 정령옥569의 이름·ID·f10=781은1340행이며, 공식 `itemName=정령옥,itemCount=1`과 이름으로 연결해 기존 kit CAS에서 실제1개씩 소모한다. 새 아이템 행이나 test_knight 책을 추가하지 않았다.

지혜297은 `items`의 등록형 `spell_power` 훅으로 SP2를 제공하며 `magic_damage(..., item_sp=...)`의 기존 L1J LOCAL INT+extraSP 계수에 연결했다. 단일·범위·흡혈 마법 피해에 적용하며 회복 공식에는 넣지 않는다. 기능을 빼면 해당 등록/소비도 사라지고 빈 fold 기본은0이다. 원본SP 피해 공식·native 표시/시전 입력·정령/파티 기능은 미확인이다.

### 최종 검증

```powershell
python -X utf8 -B -m unittest tools.local_original_session.world_magic_tests tools.local_original_session.world_item_effects_tests
$env:SL_TEST_TIME_SCALE='10'
$env:SL_TEST_PORT_BASE='59000'
python -X utf8 -B C:\Users\Chansol\AppData\Local\Temp\claude\D--claude\0483de89-75e7-4b94-84b8-fb31fe00f575\scratchpad\fastbot\run_fast.py hunt_bot_magic --scenario jobs
```

단위시험 **89개 OK, exit0, 13.884초**. [원로그](../runs/class-magic-unit-20261028-current.log). 마법63개와 현재 소모품26개이며 합계를 중복 가산하지 않는다. 새 검사는 overlay 원문 보존·직업/레벨·fullMP/HP 무소비 거절·HP→MP 상한·실 stats MR/WIS/저항/근접명중·리덕션 치명타 전 HP 소비·SP 단일/범위/흡혈 전달·동일 RNG 피해 증가·회복 미적용·만료·provider 제외를 포함한다.

최종 직접 패킷 봇은 **SUCCESS63체크/10시전, 독립4프로필/8epoch**, 모든 broker failure/close code null·cleanup true·broker exception0·`source_changes_during_run=[]`이다. [summary](../runs/hunt-magic-21ezz2pb/summary.json), [stdout](../runs/class-magic-jobs-20261028-stable.log). 이 파일의 `source_sha256_start/source_sha256`가 정확한 조합이며 JSON 원데이터 SHA256 `76605b8adb810e31a8e1d6c9479185463d4d3a6cd9d812f2b20dabf604c653b2`는 불변이다. 새 클래스별 `--scenario knight/elf/prince/wisdom`도 같은 fixture·코드를 사용하며 `jobs`가 이를 순서대로 실행한다.

| 프로필 | 관측한 행동 |
| --- | --- |
| 기사 | 87/88 실제 책 UID 학습·수량 저장·4E60→시전. MP100→90→80, LOCAL HP비용50/120. 정상 Quit→fresh FIRST/로그인/선택/월드에서 학습 키 복원 |
| 요정 | 128/129/136/137/145 실제 학습/시전. 129는 HP8·MP90→92,145는 HP50·MP77→92. 136/137 각각정령옥1개 kit CAS·수신/저장 일치. 정상 재접속 학습 키 복원 |
| 군주 | 공식 허용 공유 Shield2 실제 학습/시전·MP100→98·정상 재접속 학습 키 복원. 전용5개 성공으로 확대하지 않음 |
| 법사 지혜 | Energy Bolt SP0 시전·물약297 실제 UID Q2→1 수신/저장·다음 실제 피해의 event.item_sp=2·양의 피해·정상 재접속 학습 키 복원. 같은 두 시전 피해량 비교는 RNG가 달라 증가 증명이 아니며, 증가 자체는 동일 RNG 단위시험으로 판정 |

시험 전용 fixture는 각 fresh 프로필의 Lv30·HP300/300·MP100/200 및 해당 책/정령옥/물약을 FIRST 전에 선언했다. 월드 진입 후 HP/MP·준비·시계·UID를 강제하지 않았고 매 행동이 실제 decoder/router를 통과했다. `test_knight` 제품 키트·사용자 프로필·ACTIVE_TASK·핀·원본 LC는 수정하지 않았다.

실패 원문도 보존한다. [첫 시도](../runs/hunt-magic-tum4u4or/summary.json)는 기사 통과 뒤 요정 fixture의 없는 갑옷 조회 실패, [두 번째](../runs/hunt-magic-zalipx0i/summary.json)는 실제 물약 소비 뒤 봇의 중첩0965 오독 timeout이다. 각각 fixture/봇 decoder만 고쳐 새 독립 사본에서 실행했다. [후속 성공](../runs/hunt-magic-1jl7yu8q/summary.json)은 당시 조합 성공, [현재 조합 전 시도](../runs/hunt-magic-odm4775b/summary.json)는 성공했으나 실행 중 타 writer의 `hunt_bot.py` 변경1건을 기록해 최종 판정에 합산하지 않았다. 기존 `--scenario all` 추가 회귀는 [UNCONFIRMED](../runs/hunt-magic-tcc3i8l5/summary.json): 기존 법사 사냥 중 자연사,91체크·15시전 뒤 `PLAYER_DIED:reuse_before_current_target_selection`, broker오류0·정상cleanup·source변경0. 기존38개 전체 소켓 성공으로 주장하지 않는다.

## 직업 마법 2차 — 현재 소스 통합 (2026-10-28)

보존한 [class-magic2-staged.patch](class-magic2-staged.patch)를 qMagicHooks 후속이 있는 현재 소스에 국소 통합했다. 공유 NPC 마나 소유자·`npc_magic_target` 등록형 동료 adapter·NPC 주문 선택/피격·표시 경로를 보존했다. 신규 상태·효과는 magic 기능의 기존 인스턴스 wrapper와 등록형 선택 이벤트를 사용한다. 원패치와 공식/고정 클라이언트 원데이터는 수정하지 않았다.

아래 표는 현재 통합 소스의 효과 구현과 선택 입력의 운영 가능 여부다. 고정 클라이언트/공식 원문 `data/m3/player_spells.json`은 불변이다. 1차7개에 2차11개가 추가됐다. 총 전용41개 중 속성 입력 없이 운영 가능한9개, 선택 속성 입력이 필요한 조건부9개, 보류23개다. 기존 공유38개를 포함한 런타임 효과 구현은56개이며 조건부9개를 포함한다. 선택 속성을 시전 주문에서 추론하거나 자동 변경하지 않는다.

| 직업 | 키·이름 | 효과 / 상태 |
| --- | --- | --- |
| 기사 | 86 쇼크 스턴 | MP12, 1칸의 현재 PC/NPC를 1–4초 기절. 실제 공격 준비·이동·NPC AI 행동을 정지. 공식 최대4초, 성공률/지속분포·무기 제한 없는 admission은 L1J LOCAL. 원본 무기 제한은 미확인 |
| 기사 | 89 솔리드 캐리지 | 보류: ER 수치의 실제 피격 회피 소비자가 없음 |
| 기사 | 90 카운터 배리어 | 보류: 양손검 조건·근접 회피·반격 대미지/공격의 등록형 서비스가 없음 |
| 요정 | 146 프로텍션 프롬 엘리멘트 | 선택한 자기 속성 저항+50. 속성 저장이 없는 기존 프로필은 무소비 거절 |
| 요정 | 147 파이어 웨폰 / 162 버닝 웨폰 | 불: 근접 대미지+3 / +5·명중+3. 같은 공격 계열 교체, 실제 근접 combat profile에서 소비 |
| 요정 | 148 윈드 샷 / 165 스톰 샷 | 바람: 원거리 명중+5 / 대미지+4·명중+2. 근접에는 미적용, 같은 공격 계열 교체 |
| 요정 | 150 어스 스킨 / 167 아이언 스킨 | 땅: AC-4 / -7. 방어 마법 계열 교체, 실제 피격 profile·4E38에 반영 |
| 요정 | 151 인탱글 | 땅: 실제 이동 간격2배. 공격 간격은 유지. 확률은 L1J 레벨차 계산 LOCAL |
| 요정 | 152 이레이즈 매직 | 공통: 다음 적대 마법 시도의 MR을 절반으로 계산한 뒤1회 소비. 실제 확률·NPC/PC 마법 피해 소비자에 연결. 실패/카운터 시도도 소비, 스턴/이레이즈는 제외하는 것은 L1J LOCAL |
| 요정 | 169 워터 라이프 | 물: 대상 PC의 힐 마법1.5배, HP 상한 적용. 1회 소비는 공식 문구가 아닌 L1SkillUse LOCAL. 물약·자연회복에는 적용하지 않음 |
| 요정 | 130 텔레포트 투 마더 | 보류: 현재 맵/지형에서 근거 있는 세계수 목적지 미확보 |
| 요정 | 131 트리플 애로우 | 보류: 화살3개와 실제3회 공격을 원자적으로 준비·소비하는 등록형 서비스가 없음. 다른 기능 private 메서드로 우회하지 않음 |
| 요정 | 144 리턴 투 네이쳐 / 153 서먼 레서 / 161 서먼 그레이터 | 보류: 현재 companion/pet은 자기 기능 소환을 소유하며 정령 종별 소환·테이밍 해제용 등록 훅은 없음. 필요한 계약은 소속속성·주인 EntityRef·종별 데이터·시간·해제/죽음/맵이동 수명 |
| 요정 | 149 윈드 워크 | 보류: 이동만 가속하는 실제 admission/원본 속도 표시 계약 없음. 기존 공격 공속을 함께 변경하는 방식은 사용하지 않음 |
| 요정 | 154 브레스 오브 파이어 / 155 아이 오브 스톰 / 158 블레스 오브 어스 / 163 네이쳐스 블레싱 | 보류: 파티원 소유/반경/수신자 provider 없음. 자기 버프/자기 힐로 축소하지 않음 |
| 요정 | 156 어스 바인드 | 보류: 모든 피해 면역과 모든 행동 정지를 완결하는 등록형 계약 없음 |
| 요정 | 157 네이쳐스 터치 | 보류: 공식은 순간 대량 HP회복이나 SQL158은320초, L1NaturesTouch는 주기 회복. 공식 순간 회복 수치·공식식 미확인으로 임의 회복량을 만들지 않음 |
| 요정 | 160 에이리어 오브 사일런스 | 보류: 채팅과 모든 PC/NPC 마법의 침묵 소비 훅 없음 |
| 요정 | 172 폴루트 워터 | 보류: 고정·범위 회복 물약 전체의 받는 회복량을 변환하는 등록형 훅 없음. 힐만 절반으로 만든 부분 지원을 전체 지원으로 표시하지 않음 |
| 요정 | 173 스트라이커 게일 | 보류: ER 실제 피격 소비자 없음 |
| 요정 | 174 소울 오브 프레임 | 보류: 근접 무기의 최대 주사위·손상 방지를 함께 소비하는 등록 서비스 없음 |
| 군주 | 112 트루 타겟 | 보류: 현재 대상을 따라가는 표식 wire/추적 소비자 미확인 |
| 군주 | 113 글로잉 오라 / 116 브레이브 오라 | 보류: 파티원 provider 없음 |
| 군주 | 115 콜 클랜 / 117 런 클랜 | 보류: 혈맹원 식별·접속/소유·수락·정상 이동/소환 provider 없음 |

### 속성 선택과 수명

`magic.json` 각 캐릭터 행의 선택 필드 `elf_element`는 earth/fire/water/wind를 보존하며 기존 저장에는 없어도 된다. 등록 이벤트 `elf_element_selected(uid, element)`는 마법 소유자의 선택/저장을 연결하는 소비자다. 현재 원본 선택 입력을 생산하는 메뉴/패킷은 없으므로 속성9개(146과 불/바람/땅/물8개)는 **조건부 구현·운영 선택 보류**다. `152`와 `86`은 속성 입력이 필요 없다. 실제 입력 생산자는 인증한 현재 요정과 선택값을 기존 월드 잠금 안에서 이 이벤트로 전달해야 한다. 다른 기능의 private 상태를 읽지 않는다. 선택 변경은 해당 속성 버프를 해제하며, 주문 시전으로 속성이 바뀌지 않는다.

새 상태는 기존 남은시간/벽시각 저장·오프라인 만료·동일 키 갱신·사망 해제·NPC EntityRef 수명·퇴장/종료 정리를 재사용한다. 원본 없는 속성 선택을 가짜 성공으로 만들지 않는다. 시험은 FIRST 전에 명시한 각 속성의 독립 저장 프로필을 사용하며, 이것은 원본 선택 입력의 검증이 아니다.

### 근거와 LOCAL 경계

학습 클래스/레벨·MP/명시HP·재료·목표·지속·보너스는 각 키의 보존 공식 `/spell/{id}?locale=ko-KR`를 우선한다. 147/148의 공식 목표는 술자다. 공식 버닝+5/명중3·스톰+4/명중2·어스AC-4·아이언AC-7·워터라이프1.5배는 오래된 L1J 값과 달라도 공식 값을 쓴다. API 재조회 시도는 웹 도구에서 접근 실패하여 고정 공식 snapshot을 재사용했다.

`D:/SingleLineageRef/l1j-en-classic/db/l1jdb_m10.sql` skills87/147–149/151–153/163/166/168/170을 이름으로 연결한다(Classic key=SQL ID-1). 공식 누락 HP/재료 없음은 해당 SQL의 명시0, reuse87=1500ms와 나머지0→기존 LOCAL 기본1초다. `L1SkillUse.java:180–181`의 상호배타 버프 집합, `2097–2122`의 스턴 지속 분포, `L1Magic.java:278–296`의 레벨차 확률, `L1SkillUse.java:1684/1700`의 이레이즈 소비와 `1933–1940`의 워터라이프 힐 소비는 LOCAL backend 정책이다. 원본 Classic 서버의 공식 확률/재사용·스턴 무기 제한은 미확인이다.

스턴86의 보존 공식 원문에는 무기 조건이 없고, 참조 `C_UseSkill.java`와 `L1SkillUse.java`의 사용 admission에도 SHOCK_STUN 무기 검사가 없다. 현재 무기 제한 없음은 이 참조를 따른 명시적 LOCAL 정책이며 원본 무제약의 증명으로 표시하지 않는다.

기존 `world_combat.magic_damage(mr=...)`에 현재 대상의 보존 NPC MR을 실제 전달한다. 보존 표에 없는 NPC는 기존 LOCAL MR0이다. 이레이즈는 확률 계산과 실제 피해에서 감소한 MR을 쓰며, 매 요청의 유효 대상·자원 검증 뒤 소비한다. 기존 전체 피해 기대의 직접 영향 회귀를 함께 확인한다. 기존 바운스88도 stats에만 투영하던 +5를 실제 근접 `profile_modifiers`로 연결한다. qMagicHooks NPC 선택 주문에서 Counter Magic에 막힌 경우도 자원 소비 후 이레이즈를1회 소비하도록 같은 저장/아이콘 경계에 연결했다. 일반 NPC 주문은 기존 `npc_magic_swing` wrapper가 감소 MR과 소비를 맡는다.

### 2차 검증

준비한 feature preview를 원래 모듈 이름으로 독립 Python 프로세스에 주입한 조합에서 `world_magic_tests` **75개 OK, 16.058초**. [staged 원로그](../runs/class-magic2-staged-unit-final.log). 실제 근접/원거리 profile 소비·스턴 공격 준비·이동/공격 인탱글 분리·이레이즈 PC→NPC 피해/확률·NPC→PC MR·워터라이프 HP 상한/1회 소비·선택속성 저장·원래 장비 armor20과 skin/shield 상호배타 보존을 확인했다. 첫 staged 실행의 slow28 시험 전용 재료 DTO 누락 오류는 [원로그](../runs/class-magic2-staged-unit.log)에 보존했고 시험 fixture만 수정했다. live1차 복구 후 회귀는 **65개 OK**이며 [복구 원로그](../runs/class-magic2-restored-live-unit-clean.log)에 보존한다. 앞 staged 로그의 PowerShell `NativeCommandError` 포장은 unittest stderr 리다이렉션에서 발생했으며 마지막 unittest 결과는75 OK다. 복구 회귀는 subprocess에서 stdout/stderr를 파일로 직접 저장하고 Python 종료값을 반환했다.

현재 통합은 `world_magic.py`, `world_magic_status.py`, `world_feature_magic.py`, `world_magic_tests.py`, `hunt_bot_magic.py`의 국소 변경이다. 원패치 적용 전 `git apply --check`는 exit0이었다. 원본 클라이언트·사용자 프로필·ACTIVE_TASK·금지 파일·핀·커밋은 건드리지 않았다.

통합 후 `world_magic_tests`는 **75개 OK, exit0, 15.092초**다. [현재 단위시험 원로그](../runs/class-magic2-integrated-unit-20261028.log). 기존 incoming-NPC-erase 시험에 실제 NPC 주문 선택→Counter Magic→HP 불변·이레이즈/카운터1회 소비를 확인하는 분기를 포함했다. 위 staged75·복구65는 과거 조합으로 보존하며 현재 판정에 합산하지 않는다.

```powershell
python -X utf8 -B -m unittest tools.local_original_session.world_magic_tests
$env:SL_TEST_TIME_SCALE='10'
$env:SL_TEST_PORT_BASE='22000'
python -X utf8 -B C:\Users\Chansol\AppData\Local\Temp\claude\D--claude\0483de89-75e7-4b94-84b8-fb31fe00f575\scratchpad\fastbot\run_fast.py hunt_bot_magic --scenario jobs
```

직접 패킷 `jobs`는 **SUCCESS, exit0, 208체크·26시전·독립8프로필·16epoch, 실제70.728초**다. [최종 summary](../runs/hunt-magic-v4hlnebv/summary.json), [stdout 원로그](../runs/class-magic2-jobs-integrated-retry2-20261028.log). 모든 epoch의 failure/close code는 null, cleanup_complete는 true, broker exception은0, `source_changes_during_run=[]`이다. 정확한 소스 조합은 summary의 `source_sha256_start/source_sha256`에 있다.

기사/공통요정/불/물/바람/땅/군주/지혜 모두 FIRST→로그인→선택→월드→실제 책·시전 요청→정상 Quit→fresh FIRST/재접속의 학습·선택속성 복원을 통과했다. 152→실제 피해 후 이레이즈1회 소비, 169→힐1.5배·1회 소비, 근접/원거리 profile 보너스·AC와 수신4E38 f14의 부호 반영을 확인했다. 미지원23키는 실제 책 요청에서 인벤토리·학습·MP·재사용 무변경 거절을 확인했다. 속성은 FIRST 전 독립 시험 저장에 명시한 Lv60·HP500/1000·MP500/600·책·정령옥 fixture다. 이는 원본 속성 선택 입력의 검증이 아니다.

통합 첫 시도 포트20000은 기사·공통요정 통과 후 첫 속성 fixture가 runtime_started 전의 미연결 MagicStore를 호출해 실패했다. [실패 summary](../runs/hunt-magic-0x3my19t/summary.json), [stdout](../runs/class-magic2-jobs-integrated-20261028.log). FIRST 전 기존 `MagicStore(self.store).save`로 저장하도록 fixture만 수정했다. 포트21000은 땅150의 실제 시전 후 봇이 negated-AC wire와 profile AC를 같은 부호로 비교해 실패했다. [실패 summary](../runs/hunt-magic-07ocs_tl/summary.json), [stdout](../runs/class-magic2-jobs-integrated-retry1-20261028.log). 기존 armor20 기대와 같은 `wire=-profile.ac`로 봇만 고쳤다. 두 실패와 소비/저장/정리는 그대로 보존하며 최종 판정에 합산하지 않는다.

잔여23개는 현 등록형 계약을 다시 확인했으나 추가로 닫힌 효과는 없다. `prepare_attack`은 단일 화살 비용, ER은 실제 원거리 피격 회피 소비자가 없고, 물약은 `combat.heal` 고정 회복과 `world_item_effects`의 범위 회복 직접 HP 변경으로 나뉘어 공통 받은회복 훅이 없다. 파티·혈맹·정령 provider, 모든 피해 면역/침묵 소비, 세계수 목적지, 최대 무기 주사위·내구도 서비스도 부족하다. 다른 선택기능의 private 호출이나 자기효과 축소로 대체하지 않았다. native 선택 입력·표시/아이콘 시간단위·원본 확률/공식 계산식·지원 보류 효과는 여전히 미확인이다.

## 마법서 학습 metadata와 기존 소비 경로 (2026-10-28)

`data/m1/items_ext/spellbooks.json` 37권과 `misc.json`의 마법서8권에 현재 학습 상태를 명시했다. 기존 `PlayerMagic.learn`과 `world_feature_magic._world_magic_frame`이 직업/레벨·선택속성·중복 검사, 책1개 CAS 소비와 magic 저장, 저장 후4E60 전송까지 이미 소유하므로 runtime 두 파일은 수정하지 않았다. `use_enabled`와 `learning_policy`는 그 계약을 설명하는 metadata이며 새 dispatcher나 효과를 만들지 않는다.

| 범위 | 변경 전 명시 metadata | 변경 후 | 실제 runtime 전후 |
| --- | --- | --- | --- |
| spellbooks37권 | use_enabled37권 모두 없음 | 일반 지원14·조건부8은 true, 보류15는 false | 기존 학습 가능22·보류15 유지 |
| misc 마법서8권 | false8 | false8·보류 사유/공식 키 명시 | runtime catalog 밖8 유지 |
| 전체 player_spells80 | 대상45권과 별도 집계 | 지원 효과를 추가하지 않음 | 지원56(조건부9 포함)·미지원24 유지 |

대상45권의 지원 키/책ID 매핑은 다음과 같다. 보류 사유는 위2차 효과 표와 JSON 각 `learning_policy.value.reason`에 있다.

| 상태 | 주문 키→책ID |
| --- | --- |
| 일반 지원14 | 16→189,17→190,18→191,19→192,20→193,21→519,22→600,32→199,37→521,38→603,128→570,129→571,136→573,137→574 |
| 조건부8 | 146→577,147→578,148→579,150→581,162→592,165→595,167→597,169→1493 |
| 기존 직업 보류15 | 90→1492,112→675,113→676,115→713,116→1221,117→1295,130→572,131→1296,153→584,160→590,161→591,163→593,172→1494,173→1495,174→1496 |
| 상위 마법 보류8 | 49→210 아이스 랜스,56→214 풀 힐,58→216 블리자드,64→219 라이트닝 스톰,65→220 포그 오브 슬리핑,68→223 매스 텔레포트,69→525 파이어 스톰,73→225 미티어 스트라이크 |

조건부8권은 저장된 `elf_element`가 있어야 학습하며 속성 전용 주문은 일치해야 한다.146은 선택한 어느 속성이든 허용한다. 원본 선택 입력 생산자가 없는 상태는 유지했다. 전체 조건부9개 중151은 이번 두 JSON 밖의 기존 책582이며 runtime 조건은 동일하다. 상위8개는 보존 `data/official/spells.json`의 정확한 textbook.id와 고정 client_id로 연결했지만 현재 `player_spells.json`에 효과/비용/목표/학습 계약이 없어 계속 비활성이다. 원문·아이콘·가격·스택·직업별 가방 보관 정책은 보존했다.

### 이번 검증과 미통과 경계

새 `spellbook_learning_tests.py`5개는 임시 실제 InventoryStore/MagicStore와 기존0960 handler를 사용한다. 대상 지원22권의 공식 직업/최소레벨 허용·저레벨/다른 직업 무소비 거절, 조건부 무선택 거절, Q1제거/Q2→1 소비, 저장 후4E60, 중복 거절, fresh 저장 복원을 확인했다. 대상 보류23권은 학습/소비 없음, 전체 조건부9개는 무선택 거절을 확인했다. readiness/소유·runtime dispatch는 단위 fixture 경계이므로 정상 로그인/소켓/원본 입력 PASS가 아니다.

```powershell
python -X utf8 -B -m unittest tools.local_original_session.spellbook_learning_tests tools.local_original_session.world_magic_tests.RulesTests tools.local_original_session.world_magic_tests.StatusAiConsumerTests tools.local_original_session.world_magic_tests.CodecTests tools.local_original_session.world_magic_tests.ResourceMutationTests tools.local_original_session.world_magic_tests.SaveTests tools.local_original_session.world_magic_tests.JobSecondRulesTests tools.local_original_session.misc_items_tests
$env:SL_TEST_TIME_SCALE='10'
$env:SL_TEST_PORT_BASE='45000'
python -X utf8 -B C:\Users\Chansol\AppData\Local\Temp\claude\D--claude\0483de89-75e7-4b94-84b8-fb31fe00f575\scratchpad\fastbot\run_fast.py hunt_bot_magic --scenario jobs
```

독립 단위 범위는 **44개 OK, exit0,5.826초**(신규5·기존 마법34·misc5). [최종 원로그](../runs/spellbook-learning-unit-final-20261028.log). 기존 전체 `world_magic_tests` 실행 시 `WorldConsumerTests`39개는 fixture 초기화에서 `FIXED_SELF_INFO_PROFILE_SOURCE_CHANGED`로 거절됐다. `tools/local_self_actor_profile/profile.py:109`가 검사하는 `SELF_INFO_SOURCE_PATH=tools/local_self_info_profile/source.py`와 기존 `SELF_INFO_SOURCE_SHA`의 불일치다. 검사와 핀은 수정/우회하지 않았다. [전체 시도 원로그](../runs/spellbook-learning-unit-20261028.log), [중간 fixture 수정·명령 오류 원로그](../runs/spellbook-learning-unit-retry-20261028.log)도 보존했다.

지정 `jobs`1회는 **FAILED, exit1**, 첫 오류 `ValueError: alignment catalog must cover current M1 monsters`다. [summary](../runs/hunt-magic-3em9r4ab/summary.json), [stdout 원로그](../runs/spellbook-learning-jobs-20261028.log). fixture 생성 전 실패하여0epoch·0시전·0로그인, `cleanup_complete=true`, `source_changes_during_run=[]`다. 정확한 runtime 소스 조합은 기존 봇 summary의 `source_sha256_start/source_sha256`에 보존했다. 통합 담당이 현재 몬스터와 alignment coverage 불일치 및 위 stale source pin을 각각 해결한 뒤 재시험해야 한다. 이 작업은 해당 금지 파일을 수정하지 않았다.

이전2차208체크 성공은 이전 조합의 기록이며 이번 실패를 대체하지 않는다. 이번 작업에서 원본 LC·입력·화면은 실행/확인하지 않았고, 정상 로그인→학습→재접속 전체 경로도 이번 조합에서는 미확인이다. 사용자/manual 프로필·launcher·ACTIVE_TASK·runtime 핀 대상·기존 tests/봇은 수정하지 않았다.
