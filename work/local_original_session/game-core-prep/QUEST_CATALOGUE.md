# 고정 클라이언트 퀘스트·교환 후보 전수 인덱스

2026-10-28. 고정 버전 **26.09.29.2001**의 보존 자료를 전량 읽어 만든 후보 목록이다. 실행 연결/시험 결과는 [QUEST_EXPANSION](QUEST_EXPANSION.md), 현재 공식 가이드와 시점 차이는 [QUEST_OFFICIAL_GUIDE](QUEST_OFFICIAL_GUIDE.md)에서 구별한다. 이 목록의 B/C는 실행 완료나 공식 서버 규칙의 확정을 뜻하지 않는다.

## 오스2000 현재 연결 (2026-10-29)

`oth3.uml:13/14`의 cookie 문자열0/1은 `dialogue.csv:653/654`에서 각각 민첩함/체력 투구 요구다. run403 sender5C5950은 DF660 반환 AL을 길이1 f3으로 보내며, 새 DF660 원문은 base10 `strtol`임을 확인했다. 따라서 요청 f3은 **00→631**, **01→632**이고 ASCII `0`/`1`이 아니다. 선택 함수114바이트와 sender717바이트는 c822 보존 Source/CONTROL 정적 Source에서 각각 동일하며 CONTROL IAT가 변환 함수를 식별한다. [본문·원문/해시 근거](../../../_work/quest-choice/body-df660.json), [import/동일 범위 대응](../../../_work/quest-choice/df660-control-imports.json), 실행 경계와 전체 [16단계 판정표](QUEST_EXPANSION.md)를 따른다. 현재 게임영상과의 동일성·원본 입력/화면을 입증한 것은 아니다.

`elf_oth_orc_spellbooks` 단일 정의에640~643 각1 소비·631/632 중1 지급·같은 완료/요정Level15 End 저장을 연결했다. 기존 map4 오크91/92/93/94의 정상 마법서 드롭/배치는 로더에서 확인했고 수정하지 않았다. 고정 오스 native NPC 신원은 미확보라 LOCAL L1J70826/gfx916/SQL49213 배치임을 명시한다. 순수 계산18개는 통과했으나 실제 저장/라우터 시험은 `_work/tmp` PermissionError 재시도로 실행하지 못했다. 정상 사냥/줍기부터의 완료·원본 화면도 미검증이며, 후보41개 또는 공식16단계가 완성됐다고 확대하지 않는다.

## 기사30·45 연결 근거와 보류 (2026-10-29)

고정1002의 선행1001과 재료687 환생의 물약·707 비밀방 열쇠를 모두 유지한다. L1J `Quest.xml:144–194`의 단계·짐 조건은 별도 LOCAL 정책 근거이며 고정 재료식을 대체하지 않는다. 고정1010은 줄리에서335×20+334×1+12112×1을 소비하고770×1을 받으며1005가 선행이다. L1J `Quest.xml:196–228`의 마샤·짐·거인 사슬은 이식하지 않는다.

줄리의 고정 native NPC303/$1056 외형은 `native-dump-v1.jsonl:184`의 **f2=706**이다. L1J70805의gfx1509는 별도 버전 값으로, 고정판 줄리 외형의 근거로 사용하지 않는다. 비밀방 열쇠는 같은 dump1433의707/$2022와 L1J SQL17009의40555/$2022가 대응한다.

정상 재료 생산 및 지도 접근까지 완결된 판정은 아니다. 셸로브 발톱121을 다른 종의 L1J40590 드롭으로 대체하지 않으며, 퀘스트 전용 라미아81107의 비늘을 일반 라미아에 임의 추가하지 않는다. 고정 사이클롭스의 피12112의 정상 생산 근거도 부족하다. map13의 기존 입구에서 L1J 열쇠 사용 구역까지 현 S32 보행 연결이 없어 map237은 전이표만으로 정상 접근 완료가 되지 않는다. 구현·시험 범위와 최소 후속은 [QUEST_EXPANSION](QUEST_EXPANSION.md)을 따른다.

## 범위와 근거 등급

- `quest.bin` **75/75 record**: 대화 문자열이 있는 클래식 단계41개, 대화 문자열 없는34개. QuestT의 prerequisite/objective/reward/optional-reward/exchange 자식 타입은 기존 [생성 schema 분석](../../all_table_semantics/remaining/quest/README.md)이 확인했다. 개별 scalar·enum의 실제 서버 소비 의미는 미확정이다.
- 복호 UML **1,131/1,131 파일**, `dialogue.csv` **3,617행**의 모든 stem을 대조했다. UML 없는 대사 stem도 버리지 않고 포함해 총 **1,257 stem**. queststart42/questcomplete28/questExchange1 = **71 action**이며 questteleport6도 포함했다. action 단순 검색 결과만 전수 목록으로 사용하지 않았다.
- 동적 craft와 교환을 별도 스캔했다. 고정 `craft.bin` **154/154 recipe**, `npccraftlist.bin` **29/29 NPC 행·185 대응**을 원값별로 CSV에 추가했다. 현재 `crafting.json` **106 NPC-제작식 대응**을 CSV에 행별 수록했다. 재료→보상 의뢰를 craft 구현으로 새 연결한 것은 없다. 이미 존재하는 동적 제작 route는 후보로 보존했고, 실제 선택·서버 발급 reference·소비 계약이 닫혀야 퀘스트 의뢰로 바꿀 수 있다.
- `string.csv` 12,748행·`desc.csv` 17,949행도 전량 읽었다. quest 유형/퀘스트/심부름 라벨을 CSV의 `string_token` 행에 별도로 보존했다. 이름/토큰은 독립 퀘스트의 근거가 아니다. 아이템/NPC 이름은 native dump 전체의 해당 table을 대조했다. 아이템 설명만으로 성립하는 후보는 C이며 수량/보상/수락을 보충하지 않는다.

| 등급 | 의미 |
|---|---|
| A | 공식 가이드가 명시하는 시작 NPC/보상/기간. 고정 클라이언트의 실제 wire·서버 계약과는 별도 |
| B | 고정 QuestT/UML/대사가 명시하는 단계·action·대상 또는 교환 recipe. 숫자는 아래에 raw candidate로 기록 |
| C | 이름/설명/이벤트 대사 또는 무대화 QuestT만 확인. 의뢰 성립·생산자·정산 연결 부족 |
| D | 전체 인덱스에 남긴 일반 대화·결과·상점·보관·이동·성·고용. 독립 퀘스트 수에서 제외 |

전체 원문 위치·대사 ID/line·모든 action/custom/link·원시 objective/reward/prerequisite는 [QUEST_CATALOGUE.csv](QUEST_CATALOGUE.csv)에 **1,642행**으로 보존했다. 이 수는 퀘스트 개수가 아니다. raw native recipe154행/NPC목록29행과 기존 실행 데이터106대응은 서로 중복되며 합산할 수 없다. kind가 `quest.bin`인75행만 QuestT record 수이며, 같은 의뢰의 여러 단계·UML·recipe는 중복 계수하지 않는다.

전체 stem 분류: QuestT 대화168·추가 quest action8·동적 교환/제작53·본문 단서12·이벤트 교환5·별도 서비스/lore11·기타 action215·문맥/결과785. 이 분류는 모든1,257stem을 합산하며, 같은 퀘스트 단계의 여러 stem을 독립 퀘스트로 늘리지 않는다.

## 클래식 QuestT 41개 단계

표제에는 레벨을 넣지 않았다. 예를 들어 마샤 record4/1006의 f4 level 원값45와 공식 가이드 군주/기사50, 요정2008/2009의 원값50과 공식45가 다르다. 두 자료를 섞어 선행 레벨을 확정하지 않는다. 원값 level/class는 CSV prerequisites에 그대로 보존한다.

아래 아이템×수량은 **B 원값 후보**다. objective의 f4/f5, reward의 f2/f3를 이름 table과 대조해 표시했고, phase·조건 enum·선택·재료 소진·드롭 확률·실제 지급의 증거로 확장하지 않는다. f4 prerequisite도 class/level/required 자식 내부 원값이며 표의 class0/1/2/3 의미는 실제 클래스 catalog와 별도 대조가 필요하다.

| key | 의뢰/단계 | 목표 원값 후보 | 보상 원값 후보 | 선행 key 원값 | 연결 문서 |
|---:|---|---|---|---|---|
|1|군주 제로 수색문서|636 수색문서 ×1|f7:646 붉은 망토 ×1 (type=1)|기록 없음|zero6, zero1, zero3, zero5, zero7|
|2|군주 군터 생명의 비밀|677 생명의 비밀 ×1|f7:675 마법서 (트루 타겟) ×1 (type=1)|1|gunterp9, gunterp1, gunterp10, gunterp11|
|3|군주 아리아·문지기개미 주민 유품|689 마을 주민들의 유품 ×1|f7:706 군주의 위엄 ×1 (type=1); f7:713 마법서 (콜 클랜) ×1 (type=1)|2|ants3, aria1, aria2, ants1, aria3, ants4|
|4|군주 마샤 거대한 존재|753 왕가의 문장 조각 ×1; 754 왕가의 문장 조각 ×1|f7:1221 마법서 (브레이브 오라) ×1 (type=1); f7:12349 신의의 부츠 ×1 (type=1); f7:? ×20 (type=7)|12|masha, masha1, masha2, masha3, masha4|
|5|군주 리차드 왕가의 문장 전반|753 왕가의 문장 조각 ×1|기록 없음|12|richard3, richard1, richard2|
|6|군주 리차드 문장 조각 후반|type=3/target=None ×1|기록 없음|5|richard2, richard4|
|7|군주 맥 빼앗긴 영혼 전반|type=3/target=None ×1|기록 없음|6|meg4, meg1, meg2|
|8|군주 브레드·스빈 빼앗긴 물건|750 영혼의 편지 ×1; 751 영혼의 편지 ×1; 752 영혼의 편지 ×1|기록 없음|7|brad4, brad1, brad2|
|9|군주 맥 영혼의 편지|type=3/target=None ×1|f6:754 왕가의 문장 조각 ×1 (type=1)|8|meg2, meg3|
|10|군주 데이먼 소매치기 조사|type=3/target=None ×1|기록 없음|3|damon1, damonp1, damonp2|
|11|군주 변장 경비병 소매치기|type=3/target=None ×1|기록 없음|10|mysterious guard1, mysterious guard2, mysterious guard5|
|12|군주 이올라 유품 반환|12110 도난당한 목걸이 ×1; 12111 도난당한 반지 ×1|f7:756 수호자의 반지 ×1 (type=1); f7:676 마법서 (글로잉 오라) ×1 (type=1); f7:1295 마법서 (런 클랜) ×1 (type=1)|11|iolap1, iolap2, iolap5, iolap6, iolap8, iolap4, iolap7|
|1000|기사 리키 서약서|639 흑기사의 서약서 ×1|f7:651 기사의 두건 ×1 (type=1)|기록 없음|riky1, riky3, riky5|
|1001|기사 아논 두건 개량|633 낡은 거래 문서 ×1; 650 터틀 드래곤의 껍질 ×1; 651 기사의 두건 ×1|f7:652 붉은 기사의 두건 ×1 (type=1)|1000|aanon9, aanon4, aanon5, aanon7, aanon6|
|1002|기사 마크·짐 언데드의 키|687 환생의 물약 ×1; 707 비밀방 열쇠 ×1|f7:688 감사의 편지 ×1 (type=1)|1001|jim4, mark1, mark2, jim2, mark4, jim5|
|1003|기사 군터 셸로브 발톱|121 셸로브 발톱 ×1|f7:123 붉은 기사의 검 ×1 (type=1)|1001|gunterk9, gunterkE1, gunterkE2, gunterkE3|
|1004|기사 게라드 라미아 시련|686 라미아의 비늘 ×1|f7:687 환생의 물약 ×1 (type=1)|1003|gerardk1, qguard1, gerardkE1, gerardkE2, qguard2, gerardkE3, qguard4|
|1005|기사 게라드 감사의 편지|688 감사의 편지 ×1|f7:666 붉은 기사의 방패 ×1 (type=1)|1004|gerardkE3, gerardkE4, gerardkEcg|
|1006|기사 마샤 조사원 수색|12353 찢어진 조사서 조각(1) ×1; 12354 찢어진 조사서 조각(2) ×1; 12355 찢어진 조사서 조각(3) ×1|f7:12350 용기의 부츠 ×1 (type=1)|1010|masha, mashak1, mashak2, mashak3|
|1007|기사 라즐로스 조사서|12353 찢어진 조사서 조각(1) ×1|기록 없음|1010|lazloth1, lazlothk1, lazlothk2, lazlothk3|
|1008|기사 타라스 조사서|12354 찢어진 조사서 조각(2) ×1; 12355 찢어진 조사서 조각(3) ×1|기록 없음|1007|talass, talass1, talassk1, talassk2, talassk3|
|1010|기사 줄리 용기의 벨트|335 고급피혁 ×20; 334 벨트 ×1; 12112 사이클롭스의 피 ×1|f7:770 용기의 벨트 ×1 (type=1)|1005|ladar1, ladark1, ladark5, ladark6, ladark4, ladark8|
|2000|요정 오스 오크 마법서|640 두다 마라 오크 마법서 ×1; 641 네루가 오크 마법서 ×1; 642 간디 오크 마법서 ×1; 643 아투바 오크 마법서 ×1|f8:631 민첩함의 투구 ×1 (type=1); f8:632 체력의 투구 ×1 (type=1)|기록 없음|oth1, oth3, oth5, oth6|
|2001|요정 숲의어머니 성인식 안내|type=3/target=None ×1|기록 없음|2000|mothere1, motherEE1, motherEE2|
|2002|요정 페어리프린세스·다크마르 정령서|693 저주 받은 정령서 ×1|f7:705 요정족 티셔츠 ×1 (type=1); f7:584 정령의 수정 (서먼 레서 엘리멘탈) ×1 (type=1)|2001|motherEE2, fairyp1, fairyp2, motherEEE1, mothere1, fairyp4, fairyp3, motherEEE2|
|2003|요정 마샤 조사|771 고대의 하프 ×1; 763 신비한 소라 껍데기 ×1|f7:774 마샤의 주머니 ×1 (type=1)|2009|masha, mashae1, mashae2, mashae3|
|2004|요정 헤이트 플룻 의뢰|type=3/target=None ×1|기록 없음|2009|heit4, heit1, heit2|
|2005|요정 세피아의 죄|762 파란색 플룻 ×1|기록 없음|2004|sepia2, sepia4, sepia1|
|2006|요정 헤이트 플룻 반환|type=3/target=None ×1|f6:763 신비한 소라 껍데기 ×1 (type=1)|2005|heit2, heit3|
|2007|요정 헤이트 소라 후속|771 고대의 하프 ×1|기록 없음|2006|heit3, heit5|
|2008|요정 숲의어머니 오염된 정령|12113 오염된 정령의 수정(물) ×1; 12114 오염된 정령의 수정(불) ×1; 12115 오염된 정령의 수정(땅) ×1; 12116 오염된 정령의 수정(바람) ×1; 12118 정화의 머리띠 ×1|f6:12118 정화의 머리띠 ×1 (type=1); f7:768 보호 장갑 ×1 (type=1)|2002|mothere1, arachne1, mothere11, mothere14, arachnee11, arachnee12, mothere13, mothere15|
|2009|요정 숲의어머니 바실리스크|12117 바실리스크의 비늘 ×1|f7:591 정령의 수정 (서먼 그레이터 엘리멘탈) ×1 (type=1)|2008|mothere1, mothere21, mothere23, mothere22, mothere24|
|3000|법사 젬 뼈 세트|648 구울의 손톱 ×1; 649 구울의 이빨 ×1|f7:644 저주받은 마법서 ×1 (type=1)|기록 없음|jem1, jem3, jem9, jem8|
|3001|법사 젬 좀비의 키|647 해골의 두개골 ×1; 644 저주받은 마법서 ×1|f7:645 마력서 ×1 (type=1)|3000|jem9, jem4, jem6, jem10|
|3002|법사 게렝·디롱 언데드의 뼈|690 언데드의 뼈 ×1|f7:710 신비한 지팡이 ×1 (type=1)|3001|gerengw1, dilong4, gerengt1, gerengt2, dilong1, gerengt3, dilong3|
|3003|법사 게렝 신비한 수정구|709 신비한 수정구 ×1; 710 신비한 지팡이 ×1|f7:711 수정 지팡이 ×1 (type=1)|3002|gerengt3, gerengt4, gerengw1, gerengt5|
|3004|법사 타라스 조사결과|761 고대의 악마에 대한 기록서 ×1|f7:778 타라스의 마법 주머니 ×1 (type=1)|3007|talass, talass1, talassmq1, talassmq2, talassmq3|
|3005|법사 신비한바위 저주 연구|757 도펠갱어의 체액 ×1; 201 마법서 (그레이터 힐) ×1|f7:761 고대의 악마에 대한 기록서 ×1 (type=1)|3007|stoenm4, stoenm1, stoenm2, stoenm3|
|3006|법사 젬 마력 주입 전반|12119 신비한 마나 회복 물약 ×1; 12120 신비한 지혜의 물약 ×1; 231 마법사의 지팡이 ×1|f7:769 마나 망토 ×1 (type=1)|3003|jem6, jemw1, jemw3, jemw4, jemw9, jemw2, jemw5|
|3007|법사 게렝·젬 특수 지팡이|12121 서큐버스 퀸의 신비한 지팡이 ×1|f7:342 마나의 지팡이 ×1 (type=1)|3006|gerengw1, jem2, gerengw11, jemw9, gerengw13, jemw6, gerengw14, jemw7, jem6, gerengw12, jemw8|
|9000|라이라 오크 토템 전량 정산|type=3/target=None ×1|기록 없음|기록 없음|lyra1, lyraEv1, lyraEv4, lyraEv3, lyraEv7, lyraEv5, lyraEv6|

동일 record1010 안에서 `julie`와 `ladar1/ladark*`가 연결된다. native NPC303은 가죽 세공사^줄리, 공식 기사 보상은 용기의 벨트다. 이전의 “줄리 NPC/stem 미대응”은 이 범위에서 해소된다. 다만1005→1004 선행, 조사서/피 생산자, 실제 메뉴·소비가 모두 닫혔다는 뜻은 아니다.

## 대화 없는 QuestT 34개

이들은 f2=true·직업/레벨형 숫자 목표와 f6 RewardList를 가지지만, 명칭·수락 NPC·메뉴·게임플레이 의미를 자료가 직접 주지 않는다. 튜토리얼/레벨업 보상이라고 추정하여 구현하거나 클래식 NPC 의뢰 수에 합산하지 않는다.

| key | prerequisite level/class 원값 | 목표 raw | f6/f7/f8 보상 원값 후보 |
|---:|---|---|---|
|10000|[1]/[0]|[{"1":1,"3":3,"5":1}]|f6:12071 이름 대응 미확인 ×수량 미기록 (type=8)|
|10001|[1]/[1]|[{"1":1,"3":3,"5":1}]|f6:12072 전투 강화 주문서 ×수량 미기록 (type=8)|
|10002|[1]/[2]|[{"1":1,"3":3,"5":1}]|f6:12073 전투 강화 주문서 상자 ×수량 미기록 (type=8)|
|10003|[1]/[3]|[{"1":1,"3":3,"5":1}]|f6:12074 속죄의 성서 상자 ×수량 미기록 (type=8)|
|10010|[5]/[0]|[{"1":1,"3":3,"5":5}]|f6:12077 2단 가속 선택 주머니 ×수량 미기록 (type=8)|
|10011|[5]/[1]|[{"1":1,"3":3,"5":5}]|f6:12078 이름 대응 미확인 ×수량 미기록 (type=8)|
|10012|[5]/[2]|[{"1":1,"3":3,"5":5}]|f6:12079 이름 대응 미확인 ×수량 미기록 (type=8)|
|10013|[5]/[3]|[{"1":1,"3":3,"5":5}]|f6:12080 이름 대응 미확인 ×수량 미기록 (type=8)|
|10020|[6]/[]|[{"1":1,"3":3,"5":6}]|f6:12075 픽시의 모래시계 상자 ×수량 미기록 (type=8)|
|10030|[7]/[]|[{"1":1,"3":3,"5":7}]|f6:12081 헤이스트 부적 ×수량 미기록 (type=8)|
|10040|[8]/[]|[{"1":1,"3":3,"5":8}]|f6:12076 이름 대응 미확인 ×수량 미기록 (type=8); f6:12124 이름 대응 미확인 ×수량 미기록 (type=8)|
|10050|[9]/[]|[{"1":1,"3":3,"5":9}]|f6:12122 이름 대응 미확인 ×수량 미기록 (type=8)|
|10060|[10]/[]|[{"1":1,"3":3,"5":10}]|f6:12082 이름 대응 미확인 ×수량 미기록 (type=8)|
|10065|[11]/[]|[{"1":1,"3":3,"5":11}]|f6:12401 데몬의 물약 선택 주머니 ×수량 미기록 (type=8)|
|10070|[12]/[]|[{"1":1,"3":3,"5":12}]|f6:12123 이름 대응 미확인 ×수량 미기록 (type=8)|
|10090|[15]/[0]|[{"1":1,"3":3,"5":15}]|f6:12083 샤르나의 변신 주문서 ×수량 미기록 (type=8)|
|10091|[15]/[1]|[{"1":1,"3":3,"5":15}]|f6:12084 빨간 물약 주머니 ×수량 미기록 (type=8)|
|10092|[15]/[2]|[{"1":1,"3":3,"5":15}]|f6:12085 이름 대응 미확인 ×수량 미기록 (type=8)|
|10093|[15]/[3]|[{"1":1,"3":3,"5":15}]|f6:12086 desc16352 ×수량 미기록 (type=8)|
|10100|[17]/[]|[{"1":1,"3":3,"5":17}]|f6:12125 이름 대응 미확인 ×수량 미기록 (type=8)|
|10110|[20]/[]|[{"1":1,"3":3,"5":20}]|f6:12126 가벼운 용기의 물약 ×수량 미기록 (type=8)|
|10120|[25]/[]|[{"1":1,"3":3,"5":25}]|f6:12127 가벼운 엘븐 와퍼 ×수량 미기록 (type=8)|
|10125|[27]/[]|[{"1":1,"3":3,"5":27}]|f6:12402 데몬의 2단 가속 선택 주머니 ×수량 미기록 (type=8)|
|10130|[28]/[]|[{"1":1,"3":3,"5":28}]|f6:12128 가벼운 지혜의 물약 ×수량 미기록 (type=8)|
|10140|[30]/[0]|[{"1":1,"3":3,"5":30}]|f6:12100 이름 대응 미확인 ×수량 미기록 (type=8); f6:12087 desc16353 ×수량 미기록 (type=8)|
|10141|[30]/[1]|[{"1":1,"3":3,"5":30}]|f6:12101 이름 대응 미확인 ×수량 미기록 (type=8); f6:12087 desc16353 ×수량 미기록 (type=8)|
|10142|[30]/[2]|[{"1":1,"3":3,"5":30}]|f6:12102 이름 대응 미확인 ×수량 미기록 (type=8); f6:12087 desc16353 ×수량 미기록 (type=8)|
|10143|[30]/[3]|[{"1":1,"3":3,"5":30}]|f6:12103 이름 대응 미확인 ×수량 미기록 (type=8); f6:12087 desc16353 ×수량 미기록 (type=8)|
|10150|[34]/[]|[{"1":1,"3":3,"5":34}]|f6:12403 데몬의 변신 주문서 상자 ×수량 미기록 (type=8)|
|10160|[40]/[]|[{"1":1,"3":3,"5":40}]|f6:12088 캐릭터 서버 이전권 ×수량 미기록 (type=8)|
|10170|[45]/[0]|[{"1":1,"3":3,"5":45}]|f6:12404 데몬의 행운 상자 ×수량 미기록 (type=8)|
|10171|[45]/[1]|[{"1":1,"3":3,"5":45}]|f6:12405 마나의 반지 ×수량 미기록 (type=8)|
|10172|[45]/[2]|[{"1":1,"3":3,"5":45}]|f6:12406 메티스의 2단 가속 선택 주머니 ×수량 미기록 (type=8)|
|10173|[45]/[3]|[{"1":1,"3":3,"5":45}]|f6:12407 이름 대응 미확인 ×수량 미기록 (type=8)|

## 교환·제작과 본문 단서

QuestT에 없는 stem도 custom craft_output/input, request_craft*, 대사의 반환·재료·답례·심부름 단서와 모든 링크를 함께 대조했다. 다음 표는 QuestT 단계 밖에서 추가로 검토할 입력이다. 전체 craft 106대응과 전체 stem의 제외 사유는 CSV에 있다. “동적 목록”을 고정 수량 퀘스트로 축약하지 않으며, 단일 재료 교환형이 의뢰로 닫힐 때는 퀘스트 엔진으로 처리한다.

| stem | 등급·종류 | 실제 action/custom 또는 대사 근거 | 남은 계약/분류 |
|---|---|---|---|
|aanon10|C quest_or_exchange_text|fix|대사만으로 수락·수량·보상 확정 불가; CSV 원문/링크 재사용|
|arachneE1|B dynamic_craft_or_exchange|custom:craft_output|동적 목록의 recipe reference/소비 연결 필요|
|arachneE2|B dynamic_craft_or_exchange|request_craft; custom:craft_input|동적 목록의 recipe reference/소비 연결 필요|
|bran1|B dynamic_craft_or_exchange|custom:craft_output|동적 목록의 recipe reference/소비 연결 필요|
|bran2|B dynamic_craft_or_exchange|request_craft; custom:craft_input|동적 목록의 recipe reference/소비 연결 필요|
|daisy_ev1|C event_exchange_text|buy; sell|기간·획득처·재료/보상·수락 계약 필요|
|doilEv1|C event_exchange_text|buy; sell|기간·획득처·재료/보상·수락 계약 필요|
|easterbarnaby1|C event_exchange_text|buy; sell|기간·획득처·재료/보상·수락 계약 필요|
|easterhazel1|B dynamic_craft_or_exchange|custom:craft_output|동적 목록의 recipe reference/소비 연결 필요|
|easterhazel2|B dynamic_craft_or_exchange|request_craft; custom:craft_input|동적 목록의 recipe reference/소비 연결 필요|
|entE1|B dynamic_craft_or_exchange|custom:craft_output|동적 목록의 recipe reference/소비 연결 필요|
|eveurol1|B dynamic_craft_or_exchange|custom:craft_output|동적 목록의 recipe reference/소비 연결 필요|
|eveurol5|B dynamic_craft_or_exchange|request_craft; custom:craft_input|동적 목록의 recipe reference/소비 연결 필요|
|evmy1|C event_exchange_text|buy; sell|기간·획득처·재료/보상·수락 계약 필요|
|fairyE1|B dynamic_craft_or_exchange|custom:craft_output|동적 목록의 recipe reference/소비 연결 필요|
|fairyE2|B dynamic_craft_or_exchange|request_craft; custom:craft_input|동적 목록의 recipe reference/소비 연결 필요|
|fairyqE1|B dynamic_craft_or_exchange|custom:craft_output|동적 목록의 recipe reference/소비 연결 필요|
|fairyqE2|B dynamic_craft_or_exchange|request_craft; custom:craft_input|동적 목록의 recipe reference/소비 연결 필요|
|farlin1|B dynamic_craft_or_exchange|custom:craft_output|동적 목록의 recipe reference/소비 연결 필요|
|farlin2|B dynamic_craft_or_exchange|request_craft; custom:craft_input|동적 목록의 recipe reference/소비 연결 필요|
|hector1|B dynamic_craft_or_exchange|fix; custom:craft_output|동적 목록의 recipe reference/소비 연결 필요|
|hector2|B dynamic_craft_or_exchange|request_craft; custom:craft_input|동적 목록의 recipe reference/소비 연결 필요|
|herbert1|B dynamic_craft_or_exchange|custom:craft_output|동적 목록의 recipe reference/소비 연결 필요|
|herbert2|B dynamic_craft_or_exchange|request_craft; custom:craft_input|동적 목록의 recipe reference/소비 연결 필요|
|horunc1|B dynamic_craft_or_exchange|custom:craft_output|동적 목록의 recipe reference/소비 연결 필요|
|horunc2|B dynamic_craft_or_exchange|request_craft; custom:craft_input|동적 목록의 recipe reference/소비 연결 필요|
|horunev1|C quest_or_exchange_text|dialogue.csv:2603 horunev1_3 요정숲에서 얻을 수 있는 다양한 재료를 저에게 주신다면 마법책을 건네드릴 수 있어요. 다른 방법이라면 말하는 섬 게랭님의 조수를 찾아가보세요. 가지고 있는 마법책을 나눠주실지도 모르겠네요. |대사만으로 수락·수량·보상 확정 불가; CSV 원문/링크 재사용|
|horunev4|C quest_or_exchange_text|dialogue.csv:2609 horunev4_1 1레벨 마법을 배우는 것이라면 <font fg="ffffff">아라크네의 거미줄 1타래</font>나 <font fg="ffffff">미스릴 50개</font>, <font fg="ffffff">페어리 더스트 100개</font>, <font fg="ffffff">판의 갈기털 10뭉치</font> 중 한종류만 가져다 주시면 되요.|대사만으로 수락·수량·보상 확정 불가; CSV 원문/링크 재사용|
|ivelviin1|B dynamic_craft_or_exchange|fix; custom:craft_output|동적 목록의 recipe reference/소비 연결 필요|
|ivelviin2|B dynamic_craft_or_exchange|request_craft; custom:craft_input|동적 목록의 recipe reference/소비 연결 필요|
|jaderabbit1|C quest_or_exchange_text|dialogue.csv:3615 jaderabbit1_1 달과자를 교환하러 오셨나요?<br/>전 평범한 달과자를 고소한 달과자와 달콤한 달과자로 바꿔드리고 있어요, 뿅!|대사만으로 수락·수량·보상 확정 불가; CSV 원문/링크 재사용|
|joewoogolem2|B dynamic_craft_or_exchange|custom:craft_output|동적 목록의 recipe reference/소비 연결 필요|
|joewoogolem3|B dynamic_craft_or_exchange|request_craft; custom:craft_input|동적 목록의 recipe reference/소비 연결 필요|
|karif2|B dynamic_craft_or_exchange|request_craft; custom:craft_input|동적 목록의 recipe reference/소비 연결 필요|
|karif5|B dynamic_craft_or_exchange|custom:craft_output|동적 목록의 recipe reference/소비 연결 필요|
|ladar2|B dynamic_craft_or_exchange|request_craft; custom:craft_input|동적 목록의 recipe reference/소비 연결 필요|
|lien1|B dynamic_craft_or_exchange|custom:craft_output|동적 목록의 recipe reference/소비 연결 필요|
|lien2|B dynamic_craft_or_exchange|request_craft; custom:craft_input|동적 목록의 recipe reference/소비 연결 필요|
|luudiel1|B dynamic_craft_or_exchange|custom:craft_output|동적 목록의 recipe reference/소비 연결 필요|
|luudiel2|B dynamic_craft_or_exchange|request_craft; custom:craft_input|동적 목록의 recipe reference/소비 연결 필요|
|lyraEv8|C quest_or_exchange_text|dialogue.csv:2502 lyraEv8_1 감사합니다. 앞으로도 잘 부탁드립니다.|대사만으로 수락·수량·보상 확정 불가; CSV 원문/링크 재사용|
|moonrabbit1|C quest_or_exchange_text|dialogue.csv:3614 moonrabbit1_4 평범한 달과자를 먹어도 힘이 나지만, 옆에 있는 옥토끼는 좀 더 특별한 달과자를 갖고 있어! 달과자를 여러 개 모았다면 <font fg="ffafff">옥토끼하고 교환</font>해보는 건 어때?|대사만으로 수락·수량·보상 확정 불가; CSV 원문/링크 재사용|
|moria1|B dynamic_craft_or_exchange|custom:craft_output|동적 목록의 recipe reference/소비 연결 필요|
|moria2|B dynamic_craft_or_exchange|request_craft; custom:craft_input|동적 목록의 recipe reference/소비 연결 필요|
|moria2_s|C quest_or_exchange_text|dialogue.csv:282 moria2_s_1 연구에 기여해 주신 보답입니다. 잘 사용하세요.|대사만으로 수락·수량·보상 확정 불가; CSV 원문/링크 재사용|
|narhen1|B dynamic_craft_or_exchange|custom:craft_output|동적 목록의 recipe reference/소비 연결 필요|
|narhen2|B dynamic_craft_or_exchange|request_craft; custom:craft_input|동적 목록의 recipe reference/소비 연결 필요|
|nerupaE1|B dynamic_craft_or_exchange|custom:craft_output|동적 목록의 recipe reference/소비 연결 필요|
|nerupaE2|B dynamic_craft_or_exchange|request_craft; custom:craft_input|동적 목록의 recipe reference/소비 연결 필요|
|newyearcook|C event_exchange_text|buy; sell|기간·획득처·재료/보상·수락 계약 필요|
|panE1|B dynamic_craft_or_exchange|custom:craft_output|동적 목록의 recipe reference/소비 연결 필요|
|panE2|B dynamic_craft_or_exchange|request_craft; custom:craft_input|동적 목록의 recipe reference/소비 연결 필요|
|panE2_f|C quest_or_exchange_text|custom:craft_fail|대사만으로 수락·수량·보상 확정 불가; CSV 원문/링크 재사용|
|panEflute|B dynamic_craft_or_exchange|request_craft_flute|동적 목록의 recipe reference/소비 연결 필요|
|paulo1|B dynamic_craft_or_exchange|custom:craft_output|동적 목록의 recipe reference/소비 연결 필요|
|paulo2|B dynamic_craft_or_exchange|request_craft; custom:craft_input|동적 목록의 recipe reference/소비 연결 필요|
|riky4|C quest_or_exchange_text|dialogue.csv:636 riky4_8 그를 도와준다면 아논 역시 자네에게 보답을 해 줄 걸세.|대사만으로 수락·수량·보상 확정 불가; CSV 원문/링크 재사용|
|robinwood1|B dynamic_craft_or_exchange|custom:craft_output|동적 목록의 recipe reference/소비 연결 필요|
|robinwood2|B dynamic_craft_or_exchange|request_craft; custom:craft_input|동적 목록의 recipe reference/소비 연결 필요|
|ryumiel1|B dynamic_craft_or_exchange|custom:craft_output|동적 목록의 recipe reference/소비 연결 필요|
|ryumiel2|B dynamic_craft_or_exchange|request_craft; custom:craft_input|동적 목록의 recipe reference/소비 연결 필요|
|sebas1|B dynamic_craft_or_exchange|custom:craft_output|동적 목록의 recipe reference/소비 연결 필요|
|sebas2|B dynamic_craft_or_exchange|request_craft; custom:craft_input|동적 목록의 recipe reference/소비 연결 필요|
|shamid1|B dynamic_craft_or_exchange|custom:craft_output|동적 목록의 recipe reference/소비 연결 필요|
|shamid2|B dynamic_craft_or_exchange|request_craft; custom:craft_input|동적 목록의 recipe reference/소비 연결 필요|
|talassM3|C quest_or_exchange_text|dialogue.csv:3164 talassM3_7 조사 결과를 건네 준다|대사만으로 수락·수량·보상 확정 불가; CSV 원문/링크 재사용|
|talassM4|C quest_or_exchange_text|dialogue.csv:3165 talassM4_1 자네는 아직 내 부탁을 들어줄만한 실력은 아닌 것 같군.|대사만으로 수락·수량·보상 확정 불가; CSV 원문/링크 재사용|
|vincent1|B dynamic_craft_or_exchange|custom:craft_output|동적 목록의 recipe reference/소비 연결 필요|
|vincent2|B dynamic_craft_or_exchange|request_craft; custom:craft_input|동적 목록의 recipe reference/소비 연결 필요|
|ysorya1|C quest_or_exchange_text|buy; sell; asktax; asknpctax|대사만으로 수락·수량·보상 확정 불가; CSV 원문/링크 재사용|

### 서비스 제외를 퀘스트 부재로 해석하지 않음

| stem | 현 자료의 분류 |
|---|---|
|ant1|aria 연결 lore/문지기 소개|
|colos1_giran|경기 서비스 설명|
|doett2|제작처 안내|
|hunt4|일반 대화/청상어단 소개|
|moor1|일반 상인 lore|
|randal1|매입상 서비스|
|seghem9|용병 고용 서비스|
|sharon|서버 이전 교환권 상점|
|PcMerchant1|황금픽시깃털 상점|
|pixel|픽시깃털 기간상점|
|gear|반짝이는 코인 상점|

UML의 buy/sell, deposit/retrieve, teleportURL/지역이동, 성문/세금, 고용 action은 원문대로 CSV에 남기고 별도 서비스로 분류했다. 결과 문서·링크 대사에는 단계 목적을 잃지 않도록 원문을 모두 보존했다. 이 제외는 미색인 NPC나 신규 의뢰의 부재를 단정하지 않는다.

## 공식 목록 대조와 버전 경계

- 공식 가이드 “레벨 퀘스트”는 4직업×15/30/45/50의16행이다. 위41개는 그 의뢰들의 세부 단계와 라이라 등이며,16+41로 독립 의뢰를 합산하지 않는다. 공식 시작 NPC/보상16행은 [공식 가이드 목록](QUEST_OFFICIAL_GUIDE.md)을 따른다.
- 공식 “토템 수집”은 라이라와 대응한다. 단가/현재 product variant 드롭/실행 LOCAL 정책은 QUEST_EXPANSION의 기존 경계를 유지한다.
- 공식 해적섬6종은2026-10-20 게시로 고정9/29 클라이언트 이후 자료다. NPC/아이템/맵이 고정 자료에 없으면 고정판에 임의 생성하지 않고 이후 버전 후보로 보존한다. 상세 의뢰명·보상·출처는 공식 가이드 목록에 있다.
- 공식 카리프 보석연구6교환은3등급×붉은/푸른의6종이며8/12~8/26 기간이 명시된다. 기간 이벤트의 교환식을 상시 퀘스트로 확정하지 않는다. 고정 `karif*` dynamic craft와 동일한 실제 서버 계약임도 미확정이다.

## 연결 판정과 최소 후속

이 절은 **목록화 시점의 근거 계약**만 다룬다. 현재 runtime 연결·성공/실패 판정은 [QUEST_EXPANSION](QUEST_EXPANSION.md)의 최종 실행 결과가 우선한다.

- 후보의 필수 사슬은 실제 대상 NPC/배치→정상 수락→재료/전달물/처치의 정상 생산→선행조건→정산→저장/복원이다. 한 구간의 원값·공식 이름 확인으로 전체를 완료하지 않는다.
- 직업/교환형을 금지 사유로 쓰지 않는다. 개별 선행·생산자·정산이 부족한 항목은 그 입력만 OPEN으로 남긴다. 전체 QuestT 기본 등록·초기 단계 강제·미존재 몬스터/드롭 발명은 하지 않는다.
- 전수 **파일/record 목록화는 완료**했으며, 모든 scalar의 원본 동작 의미 복원이나 고정판 전체 퀘스트 구현을 완료한 것은 아니다. 새 연결/소켓 및 기존 시험 판정은 QUEST_EXPANSION의 실제 결과를 따른다.

## 재현 메모

보존 QuestT는 기존 `tools.asset_data_analysis.binary.parse`로 protobuf field2 wrapper→field1 key/field2 body를 읽었다. 새 parser·guard·해시 검사·게임 실행은 추가하지 않았다. 전체75 wrapper를 빠짐없이 읽고, 문자열/설명 표30,697행을 읽었으며, UML 모든 파일의 action/custom/link 및 dialogue 모든 row를 CSV에 기록했다. 작업 범위는 이 MD와 CSV뿐이다.
