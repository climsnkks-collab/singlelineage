# 리니지 클래식 공식 몬스터 자료 확인

2026-10-09 전체 비교 후속: [공식351개 레벨과 언팩 숫자 필드 비교](MONSTER_LEVEL_COMPARISON.md)에서 ID·이름 완전일치333개 중 f23과 공식레벨 일치는4개뿐이었다. 아래3표본의 f23=레벨 후보 추정은 철회하며 f23의 실제 의미는 미확정으로 유지한다. 공식 사전의 레벨 값과 현재 원시 숫자값은 별도로 보존한다.

2026-10-09 19:03 KST 확인. **공식 홈페이지의 사전 → 몬스터에 자료가 있다.** [몬스터 사전](https://lineageclassic.plaync.com/ko-kr/info/monster)은 몬스터명·출현 지역·드롭 아이템으로 검색하는 공식 자료다. 공개 목록 응답은 현재 351개 엔트리를 선언한다. 전체를 수집한 결과나 서로 다른 몬스터 종류 351종이라는 뜻은 아니다.

## 실제 공개 범위와 표본

공식 페이지가 로드하는 JavaScript와 한국어 표시 문구를 읽고, 그 페이지의 로그인 없는 공개 상세 응답 3개를 직접 확인했다. Root도 3개 응답을 새로 받아 저장된 원문과 같음을 독립 대조했다. 실제 브라우저 화면의 픽셀을 관찰한 것은 아니다.

| 공식 이름/사전 ID | 몬스터 레벨 | 크기 | 속성 | 출현 지역 예 | 드롭 목록 항목 수 |
|---|---:|---|---|---|---:|
| [오크 / 0](https://lineageclassic.plaync.com/ko-kr/info/monster?detail=monster_0_2_0) | 2 | 작은 몬스터 | 해당 필드 없음 | 말하는 섬·말하는 섬 던전 1층 등 | 7 |
| [해골 / 25](https://lineageclassic.plaync.com/ko-kr/info/monster?detail=monster_25_10_0) | 10 | 작은 몬스터 | 언데드 | 말하는 섬 던전 2층 | 12 |
| [데스나이트 / 63](https://lineageclassic.plaync.com/ko-kr/info/monster?detail=monster_63_52_0) | 52 | 작은 몬스터 | 해당 필드 없음 | 글루디오 던전 5·6·7층 | 41 |

드롭은 아이템 ID·이름 및 분류별 목록이다. 오크에는 오크족 단검·창·검·투구·고리 갑옷, 아데나, 동물가죽이 있다. 표의 수는 원문 목록 항목 수이며, 데스나이트의 41항목에는 중복 ID가 있어 고유 ID는 35개다. 41종의 서로 다른 아이템, 드롭 확률, 수량, 반드시 드롭되는 아이템으로 바꾸어 읽지 않는다. 오크 지역 원문에는 말하는 섬이 중복되어 있고, 화면 소비 코드는 지역 이름을 중복 제거하여 표시한다.

확인한 몬스터 상세 응답 및 화면 소비 코드의 공개 항목은 이름·이미지·레벨·크기·일부 속성(언데드/데몬)·출현 지역·드롭 목록이다. `damageable`은 한국어 표시 문구 **손상 몬스터**의 조건이다. 공격 가능/피해 가능 여부나 구체적인 무기 손상 판정 공식으로 확정하지 않는다.

**확인한 상세 응답과 사전 표시 항목에는 HP·MP·AC·MR·경험치·이동속도·공격속도·드롭 확률/수량이 없다.** 공식 홈페이지의 모든 문서나 다른 API에도 없다고 단정한 것은 아니다. 이 사전만으로 몬스터 전투 공식을 채울 수는 없지만 레벨·크기·속성·서식지·드롭 구성의 공식 대조 자료가 된다.

오크 ID0과156, 해골 ID25와29처럼 이름이 같은 별도 엔트리가 있으며 출현 지역·드롭이 다르다. 이름만으로 합치지 않는다. 사전 ID를 클라이언트의 sprite/appearance/template/spawn ID와 동일하다고 확정하거나 로컬 서버에 적용하지 않았다.

## 2026-10-09 후속: 언팩 자료에는 없는가?

언팩 전체에서 없다고 결론낼 수 없다. 현재 `npc.bin` 77,703B/SHA `89abe49be400908c5270c6be06894fc7063ca59e7d8609fb0ece35d814dac5f6`의 951레코드·14,201개 필드를 다시 읽었다. 실제 기록된 정수 필드 9종과 f21의 반복 숫자 쌍 4,691개가 있고, 숫자 상당수의 의미가 미해석 상태다. 원본 CommonNPCInfo serializer에는 f1~26의 저장 슬롯이 있으나 현재 파일에는 f4~18이 기록되지 않는다. 이 미기록 슬롯의 의미를 HP/MP/공식이라고 추정하지 않는다.

| 언팩 레코드 이름/ID | f19의 부호 정수 해석 | 미해석 f23 | 공식 레벨 |
|---|---:|---:|---:|
| 오크 / 0 | -2 | 2 | 2 |
| 해골 / 25 | -12 | 16 | 10 |
| 데스나이트 / 63 | -120 | 52 | 52 |

f19를 AC로, f23을 레벨로 확정하지 않았다. f19 전체 부호 해석 범위는 -1,000~10,000이어서 일부 음수 표본만으로 의미를 정하면 안 된다. 세 표본의 이름은 현재 desc.csv로 확인했고 아이템 ID 집합은 공식 자료와 각각7/12/35개가 일치한다. 이는 표본 대응의 근거지만 버전 일치·전역 ID 대응·미해석 필드의 의미까지 증명하지 않는다. 해골의 f23과 공식 레벨 차이는 버전이나 다른 의미의 가능성을 미확정으로 유지한다.

현재 HP·MP·AC·MR·EXP를 몬스터 기본값으로 명명해 연결한 필드는 아직 없다. 아이템·스킬의 HP/MP 보너스와 별도 런타임 HUD의 현재/최대 HP 구조는 존재하지만 NPC 정적 기본 능력치와 구분한다. [이동·공격의 동작 시간](CLIENT_SPEED_RESEARCH.md)은 `list.spr`와 원본 소비 코드에서 이미 확인되어 있으므로 속도 정보까지 없다고 말하지 않는다.

[숫자 전체 census·표본](../work/npc_stat_presence_research/data/findings.md), [원본 serializer/HP 표시 정적 재검사](../work/npc_stat_presence_research/code/report.json), [Root 독립 대조1,066개 PASS](../work/npc_stat_presence_research/root-review.json). 현재 NPC raw 구조·공식 드롭 ID 집합3표본·기존23함수와 serializer/HP 명령 바이트를 Root가 다시 대조했으며 제품·원본·게임·메모리·UAC 변경은 없었다.

## 보조 공식 가이드

[가이드 → 사냥터 → 던전](https://lineageclassic.plaync.com/ko-kr/guidebook/view?title=%EB%8D%98%EC%A0%84)에도 보스 출현층·주요 보상 표와 몬스터 사전 링크가 있다. 데스나이트의 글루디오 던전 5~7층 출현이 상세 응답과 일치한다. 카스파 패밀리 3~4층, 네크로맨서 6층 등도 안내한다.

던전 문서의 API 수정시각은 2026-09-15 23:01:21 KST이다. 개별 몬스터 사전 데이터의 수정시각은 응답에서 확인되지 않았다. 가이드의 권장 사냥 레벨은 플레이어 권장 레벨이므로 몬스터 레벨과 구분한다. 글루디오 보스 표의 주요 드롭 열은 행 병합되어 있어 특정 보스 전용 드롭으로 임의 분리하지 않는다.

## 출처·검증

- 공식 HTML: `https://lineageclassic.plaync.com/ko-kr/info/monster`
- HTML이 로드하는 공개 JS: `https://assets.playnccdn.com/plaync/gameinfo/2.2.0/js/itemdict.js`, 해당 클래식 상세 모듈 `241.js`. 한국어 번역과 실제 source substring도 검증했다.
- 검색 응답: `https://api-goats.plaync.com/linclassic/v2.0/dict/search/monster?searchKeyword=&locale=ko-KR&page=1&size=30`
- 상세 응답: `https://api-goats.plaync.com/linclassic/v2.0/game/monster/0?locale=ko-KR`, ID25/63도 같은 경로. 공식 HTML→JS→엔드포인트 소비 관계를 확인했으며 인증 정보는 사용하지 않았다.
- 원문·조회 시각·크기·SHA: [API fetch receipts](../work/official_monster_research/api/fetch-index.json), [화면 소비 코드](../work/official_monster_research/api/consumer-evidence.json), [가이드 자료](../work/official_monster_research/guides/findings.md).
- Root의 응답 핀·실제 새 공개 응답 3개·표본 수치·목록/상세 일치·JS substring·번역·공식 던전 링크 등 71검사 PASS, 24JSON parse PASS: [root-review.json](../work/official_monster_research/root-review.json).

초기 `query=` 검색은 사이트의 실제 `searchKeyword=`와 달라 필터링되지 않은 응답이었다. 해당 원문은 실패 경위를 보존하기 위해 남겼으며 정상 검색 3건과 빈 검색을 따로 확인했다. 전체 페이지 크롤링·게임 실행·메모리·UAC·원본/보관/후보 변경·서버 룰 적용은 없었다.
