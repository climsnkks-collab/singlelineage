# 퀘스트 전수 목록과 실행 연결

## 기사30·45 작업과 현재 미완 계약 (2026-10-29)

**전체 완료가 아니다.** 고정판의 재료·보상과 출처 있는 LOCAL 단계 정책을 연결하는 작업이며, 발톱121·비늘686·피12112의 정상 생산과 map237 정상 입장에 필요한 입력이 부족하다. 게임 클라이언트는 실행하지 않았다. 아래 단위 계산·데이터 연결을 정상 로그인부터의 사냥/획득·원본 화면 성공으로 확대하지 않는다.

| 단계/NPC | 조건 | 실제 소비 재료와 얻는 경로 | 보상 | 출처 | 상태 |
|---|---|---|---|---|---|
| 선행 리키1000 → 아논1001 | 기사15,1000 완료 뒤1001 | 흑기사15의639 서약서·633 문서 각5%; 터틀 드래곤520의650 껍질5%; 리키가 준651도 아논에서 소비 | 651 → 652 | 고정 QuestT1000/1001, SQL5133/5134/5754, Quest.xml131–143 | 해당 드롭4개 중3개 연결; 정상 사냥→선행 저장 전체는 미시험 |
| 마크1002 수락 | 기사30,1001 완료; LOCAL Level30 시작 | 재료 발급 없음 | 수락/진행 상태 | 고정1002 mark1/mark2, Quest.xml144–148 | 1001 선행 보존; L1J 단계 정책과 고정 action 구분 |
| 군터1003 | 기사30,1001 완료와 정상 진행 | 121 셸로브 발톱×1; 생산 경로 **OPEN** | 123 붉은 기사의 검×1 | 고정1003, gunterkE1/E2, Quest.xml149–162 | 교환 계약만 연결; 다른 종40590 드롭을 차용하지 않음 |
| 게라드1004 | 1003 완료 | 686 라미아 비늘×1; 일반 라미아와 전용81107의 대응 **OPEN** | 687 환생의 물약×1 | 고정1004, gerardkE1/E2, Quest.xml164–176 | 교환 계약만 연결; 전용종의 확률을 일반종에 대입하지 않음 |
| 게라드1005 수락 → 짐1002 정산 | 1004 완료, LOCAL Level30=6, 현재 해골2374 | 실제 앞 보상687×1+707 비밀방 열쇠×1; 열쇠는 기존 버그베어33에서2% | 688 감사의 편지×1 | 고정1002/1005, SQL5614/17009, L1MerchantInstance.java372–383 | 고정1002의 두 재료 소비 유지; 정상 map237 접근 미완 |
| 게라드1005 완료 | 실제 짐 교환 뒤 LOCAL Level30=7 | 688 감사의 편지×1 | 666 붉은 기사의 방패×1, LOCAL Level30 End | 고정1005, Quest.xml187–194 | 정상 전체 계보·저장 실행 미검증 |
| 줄리1010 | 기사45,1005 완료 | 335 고급피혁×20+334 벨트×1+12112 사이클롭스 피×1; 피 생산 경로 **OPEN** | 770 용기의 벨트×1 | 고정1010/ladark UML, native NPC303/f2=706 | 고정 교환식 유지; L1J 마샤45 사슬 미이식 |

드롭은 `data/m1/drops.json`의15→633/639·520→650과 `data/m4/drops.json`의33→707만 추가했다. 기존 보류 원문은 `resolved_unresolved_history`에 남겼다. 이름토큰·아이콘·등급·교환 역할을 대조했으며 고정판과 SQL의 무게/바닥 그래픽 차이를 보존했다. 확률·수량은 자기 NPC의 L1J 행을 참고한 **LOCAL backend 정책**이다. 순수 시험2개는 원확률 RNG→소유 ground UID→pickup과 전체 로더 조합/기존 스폰을 확인했다([로그](../../../_work/knight-material-drop-final.log)); 인벤 저장·직접 패킷 사냥 성공은 아니다.

기존 퀘스트·던전 관련96개 시험은 기본 Temp에서 오류100개로 실패했다([첫 로그](../../../_work/knight-quests/unittest-01.log)). 지시대로 `TMP/TEMP=_work/tmp`로 재시도해도96개/오류100개, PermissionError/WinError5였다([재시도](../../../_work/knight-quests/unittest-02.log)). 더는 Temp 우회나 저장 fixture 실행을 반복하지 않는다. Temp 없는 기존 계산·던전·맵52개는 통과했다([로그](../../../_work/knight-quests/pure-unittest-01.log)). 새 기사 저장 fixture의 실행 결과와는 구분한다.

map3/237 지형·전이·귀환 및 보류는 [DUNGEON_MAPS](DUNGEON_MAPS.md)의 기사 지도 절을 따른다. 추가 자원 추출과 정상 클릭용 공용 대화 훅은 사용자 지정 쓰기 범위 밖이어서 별도 허용 응답 없이 수정하지 않는다. 필요한 최소 입력은 (1) 고정121/686/12112의 생산자·자기 드롭/발급 근거, (2) 현 map13 입구에서 열쇠 사용 구역까지의 원본 이동 계약, (3) 두 범위 확장 결정과 저장 fixture를 실행할 수 있는 환경이다.

### 기사 최종 변경·검증과 클라이언트 없는 확인 절차

정의는10→15개다. `data/m2/quests.json`에1002/1003/1004/1005/1010, 고정 NPC/재료/보상 kit 정책과 UML 페이지를 추가했다. `world_quest.py`는 수락 전/수락 후/완료 필요 단계를 분리한 optional 정의 필드만 추가했다. `world_feature_quest.py`는 기존 QuestStore 인벤·진행도·퀘스트 transaction/CAS로 단계와 교환을 함께 제안한다. **world_quest_store.py 및 저장 형식은 변경하지 않았다.** Jim의 현재gfx는 코어 `realm._actor_for`→등록 actor projection으로 읽으며 다른 선택 기능의 private 변신 상태를 직접 읽지 않는다. 변신 만료는 기존 appearance 소유자·scheduler 책임이다. 기사 페이지 링크를 기사 NPC에 한정해 기존 라이라 재수락 commit을 보존했다.

`world_quest_tests.py`의 정의 수/새 군터 연결 기대를 갱신했고, 신규 `world_knight_quest_tests.py`에 순수8개와 저장 fixture3개를 작성했다. fixture는 시작 재료·레벨·외형을 명시 공급하며 정상 사냥/변신/최초 메뉴 선택을 증명하지 않는다. 기존 계산17+신규 기사8+드롭2+지도7+기존 던전/맵35 = **69개/30.130초 OK(exit0)**다([최종 로그](../../../_work/knight-quests/pure-unittest-final.log)). 단계/재료 누락·선행1001·기사45/1005·Jim 해골/step6·재완료 거절·라이라 갱신을 확인했다. 저장 fixture3개는 Temp 실패 후 사용자 지시대로 **실행하지 않았다**. 실제 기사30/45 저장·재수령 방지까지 통과했다는 판정은 하지 않는다.

최초 NPC 클릭은 기존 공용 `world_handlers.HostContext.dialogue_for`가 static initial을 선택한다. 군터의 직업/진행별 페이지, Jim의 허용 페이지, 줄리 수락 이후 완료 페이지 선택은 추가 대화 훅 없이 연결되지 않는다. `world_handlers.py`는 허용 쓰기 목록 밖이라 수정하지 않았다. fixture가 직접 페이지를 고르는 개발 시험을 정상 클릭 성공으로 세지 않는다.

아래는 클라이언트·소켓을 열지 않는 최종 순수시험 재현 명령이다. 지도 시험은 이번 인증 추출 `_work/knight-maps/assets/map` 또는 추후 정식 배치된 두 canonical 자원이 필요하다.

```powershell
$env:SL_TEST_TIME_SCALE='10'
python -X utf8 -B -m unittest tools.local_original_session.world_quest_tests.QuestTests tools.local_original_session.world_knight_quest_tests.KnightPureTests tools.local_original_session.knight_material_drop_tests tools.local_original_session.world_knight_maps_tests tools.local_original_session.world_dungeon_maps_tests tools.local_original_session.world_dungeon_terrain_tests tools.local_original_session.world_dungeon_talkscroll_maps_tests tools.local_original_session.hunt_bot_dungeons_tests tools.local_original_session.world_maps_tests
```

저장 권한 문제가 해결된 환경에서 다음 명령으로 기존 퀘스트 저장/라우터와 새 기사 저장 fixture를 함께 실행한다. 이 명령은 **안내만 남기며 이번에 재시도하지 않았다**. 단계별 완료→실제 중간보상 소진→방패→줄리 벨트→새 저장 소유자로 복원→재수령 거절, Jim 저장 중단 후 forward 복구·다른 캐릭터 보존을 확인한다.

```powershell
$env:SL_TEST_TIME_SCALE='10'
$env:TMP=Join-Path (Get-Location) '_work/tmp'
$env:TEMP=$env:TMP
python -X utf8 -B -m unittest tools.local_original_session.world_quest_tests tools.local_original_session.world_quest_store_tests tools.local_original_session.world_quest_expansion_tests tools.local_original_session.world_knight_quest_tests -v *> _work/knight-quests/store-unittest-next.log
```

이후 부족 생산자/이동/최초 메뉴 계약이 닫혀야 기존 FIRST/login/character/world 봇에서 정상 선행1001→실제 재료 사냥/ground UID 줍기→기사30→줄리45→Quit/FIRST 저장 복원을 한 계보로 확인할 수 있다. 현재 실행한 봇·게임·listener는 없으며62,000대 포트를 사용한 실행 결과도 없다. 원본 화면/버튼/입력 확인은 현재 클라이언트 실행 금지 범위에 포함되어 보류한다.

## 오스 선택보상 연결과 현재 검증 범위 (2026-10-29)

요정15 오스는 `elf_oth_orc_spellbooks` **단일 퀘스트**로 등록했다. `oth1/queststart` 수락→`oth3/questcomplete`에서640~643 각1개 소진→631 또는632 중1개 지급→`oth6`이다. 두 선택은 같은 완료 상태와 요정 `Level15=255`를 공유하므로 선택별 재수령 경로가 없다. 저장 형식은 추가하지 않고 기존 QuestStore 인벤·진행도·퀘스트 forward transaction/CAS와 재시작 복구를 그대로 사용한다. 미선택·잘못된 값·ASCII `0`/`1`은 소비·저장 전에 거절한다. worn 재료는 기존 공통 인벤 조회에서 제외한다. 정의는9→10개, 대화는7→8개다. 추가EXP0·메뉴 발급·외형/배치는 출처를 구분한 LOCAL 정책이다.

### cookie 원문과 전송값

- 복호 UML 루트는 `C:/Users/Chansol/Documents/Codex/2026-09-07/d-lineage-classic/outputs/decrypted-pack/data_0/data/uml/`이다. `oth3.uml:13`은 `questcomplete cookie="0"`와 `$7`, `:14`는 `cookie="1"`과 `$8`이다. 고정 `dialogue.csv:653/654`는 각각 민첩함/체력 투구 요구이며, QuestT2000의 f8 후보631/632 각1과 대응한다. `oth1.uml:11`은 실제 `queststart`다.
- run403 `quest_native.json`의 `5C5950` 원문은 `5C5A16`에서 event+40 문자열을 DF660에 넘기고 `5C5A25`에서 반환 AL을 저장하며 `5C5A93..5C5A9E`에서 길이1 f3을 만든다. 기존 보고의 변환 의미 UNKNOWN을 이번에 닫았다. 새 정적 디코드 [body-df660.json](../../../_work/quest-choice/body-df660.json)은 DF685의 base10, DF699의 `strtol` 간접 호출, 변환 실패/범위 오류 검사 뒤 결과 반환을 확인한다. 따라서 문자열 `0`→숫자0→f3 **00**, 문자열 `1`→숫자1→f3 **01**이다. 일반 퀘스트 ID 또는 ASCII 문자 전송으로 해석하지 않는다.
- 보존 c822 carrier는 기존 run403의 legacy 분석 Source이며 현재 실행영상과 동일하다는 새 주장은 하지 않는다. 선택한 DF660 114바이트 SHA256 `add107ada2cb7f7688b4c1bedfed961562b9bb54c4c062550f31732c7168e85e`, sender5C5950 717바이트 SHA256 `e5f1d688645607238454b9597c343e82b7ae56d9a000bb0b0d1e530e366c6fba`는 기존 CONTROL 정적 Source의 같은 범위와 각각 동일하다. 그 Source의 IAT10B7410=`strtol`,10B7628=`_errno`를 [정적 대응 결과](../../../_work/quest-choice/df660-control-imports.json)에 보존했다. 범위 동일성과 import 연결만 사용했으며 전영상/런타임 동일성으로 확대하지 않는다.

L1J `Quest.xml:273–293`도 두 선택이 같은 Level15 End를 쓰고 네 마법서를 각1 소비함을 뒷받침한다. L1J action 문자열은 고정 UML action을 대체하지 않는다. 오스의 고정 native NPC 신원은 현재 dump에서 확보하지 못해, 기존 젬과 같은 명시 LOCAL actor70826/gfx916을 사용한다. SQL22472/49213과 고정 `list.spr:2814`의916 레코드가 근거이며, 이것을 원래 오스 외형으로 확정하지 않는다. SQL 배치map4/32745,32452는 현 S32에서 통행 가능하다. 등록은 기존 퀘스트 town_setup 훅과 지형 검사를 따른다.

기존 `data/m4/drops.json:3850,4187,4495,4782`와 M1→M4 로더를 정적으로 확인했다. map4 실제 spawn이 있는 간디94→642, 두다마라93→640, 아투바91→643, 네루가92→641이 각각20%·1개 LOCAL 드롭으로 로드되며 해당 unresolved는0이다. 재료/보상 kit 정책6개만 보완했고 드롭·확률·배치는 수정하지 않았다. **생산 데이터 연결 확인이며, 사냥·줍기·교환 동작 확인은 아니다.**

### 이번 시험 결과와 후속 실행

Temp가 필요 없는 기존 순수 계산17개와 신규 오스 계산1개는 **18/18 통과**했다([최종 로그](../../../_work/quest-choice/pure-unittest-02.log)). 오스의 valid0/1 각각 네 재료 소비·단일 보상·완료·양 선택 재완료 거절, missing/잘못된 값 거절을 확인했다. 네 Python AST와 JSON 읽기도 성공했다. 원본 클라이언트·게임·서버·소켓은 실행하지 않았다.

실제 저장 fixture·정상 메뉴 decoder/router·복원/재수령·worn·저장 실패 forward recovery를 기존 퀘스트 unittest에 추가했으나 **실행 검증은 미완**이다. `TMP/TEMP=<프로젝트>/_work/tmp`를 명시한 첫 실행과 새 프로세스 재시도 모두 Python TemporaryDirectory 생성 뒤 파일 쓰기/cleanup이 PermissionError13/WinError5로 거부됐다. [첫 실패](../../../_work/quest-choice/unittest-01.log)와 [재시도](../../../_work/quest-choice/unittest-02.log)를 보존했다. 재시도는67개/fixture와 cleanup 오류100개이며 제품 성공으로 세지 않는다. 권한 변경·fixture 대체·오류 무시로 우회하지 않았다. Temp 없는18개 성공을 저장/패킷 성공으로 합산하지 않는다.

실행 가능한 환경에서 다음 명령으로 저장·라우터 시험을 수행한다. 이는 소켓·게임을 실행하지 않는다.

```powershell
$env:SL_TEST_TIME_SCALE='10'
$env:TMP=Join-Path (Get-Location) '_work/tmp'
$env:TEMP=$env:TMP
python -m unittest tools.local_original_session.world_quest_tests tools.local_original_session.world_quest_store_tests tools.local_original_session.world_quest_expansion_tests -v
```

그 뒤 기존 FIRST/login/character/world 봇 클라이언트로 새 요정15 시험 사본에서 오스 수락→실제 기존 오크 사냥/4종 ground UID 줍기→선택00 또는01→재료 소진/단일 투구·완료 저장→정상Quit/FIRST 복원→반대 선택 재수령 거절을 한 계보로 확인해야 한다. 재료·완료·보상 주입은 정상 획득 PASS가 아니다. 두 보상은 독립 시험 사본으로 확인하고 서버·포트 소유를 단일 시험 worker에 모은다. 원본 화면·버튼·입력 검증은 그 이후 별도 헤드리스 원본 관측이며 이번 게임 실행 금지를 해제한 것으로 해석하지 않는다.

### 클래식 4직업 ×15/30/45/50 — 16단계 현재 판정

공식 시작/보상은 [QUEST_OFFICIAL_GUIDE](QUEST_OFFICIAL_GUIDE.md:22), 세부 key/원값은 [QUEST_CATALOGUE](QUEST_CATALOGUE.md)의41단계 표를 대조했다. 공식16단계와 고정 중간단계를 합산하지 않는다. **이번에 추가한 완결 계약은 오스 선택 교환1개이며, 저장 동작/정상획득 검증까지 완료한 직업 단계는0개다.** 나머지는 현재 자료/실행 연결만으로 아래 부족 계약을 추정 없이 닫을 수 없어 새 정의를 추가하지 않았다. 공개 서버 규칙으로 빈칸을 채우지 않는다.

| 직업·레벨 | 고정 단계·기존 연결 | 현재 판정 / 다음 최소 계약 |
|---|---|---|
| 군주15 | 제로1 교환 구현, 군터2 계산 후보 | 전체 보류.636 정상 생산/획득 미연결, 군터map3 접근·제로 이후 정상 수락 전이 미완.677의 기존 골렘 드롭만으로 둘을 완료한 것이 아님. |
| 군주30 | 아리아/문지기개미3 | 보류.2 완료 선행,689 생산·수령 NPC 전이/소비가 미완. |
| 군주45 | 데이먼10→변장 경비11→이올라12 | 보류.10/11의 type3 목표 의미·소매치기/유품 생산·정상 전이 미확정. 결과756/676/1295 원값만으로 등록하지 않음. |
| 군주50 | 리차드5/6→맥7→브레드8→맥9→마샤4 | 보류.대화 목표/문장조각 발급·생산·소비·혈맹 정원 효과 미완.고정4의level45와 공식50 차이도 미해결. |
| 기사15 | 리키1000→아논1001 교환/저장 선행 구현 | 639/633/650 정상 드롭3개를 연결했으며 순수 생산/ground/줍기 확인. 정상 사냥부터 선행 저장까지 전체는 미시험. |
| 기사30 | 마크1002 수락→군터1003→게라드1004→짐1002→게라드1005 | 고정 교환/LOCAL 단계·현재 해골 조건 구현.열쇠707 드롭 연결.발톱/비늘 생산·237접근·최초 메뉴·실제 저장 검증은 보류.1002의1001 선행 유지. |
| 기사45 | 줄리1010,335×20+334×1+12112×1→770 | 선행1005·교환·재완료 거절 계산 구현.피 정상 생산·최초 메뉴/저장 실행은 보류.L1J의다른45단계는 미이식. |
| 기사50 | 라즐로스1007→타라스1008→마샤1006 | 보류.1010 완료·조사서3종 정상 발급/소비/저장 미완.고정1006 level45/공식50 차이 보존. |
| 요정15 | 오스2000,640~643각1→631/632 중1 | 선택 교환 구현.기존 정상 드롭/배치 정적 연결 확인; 순수18개 통과.저장/라우터·실사냥/줍기·네이티브 화면은 미검증. |
| 요정30 | 숲의어머니2001→정령서2002 | 보류.2001 type3 전이 의미,693 정상 생산,티셔츠705/수정584 지급까지 미완. |
| 요정45 | 정령정화2008→바실리스크2009 | 보류.2002 선행·정화머리띠12118 실제 발급 UID/회수와4원소 수정/비늘 생산 미완.고정level50/공식45 차이 보존. |
| 요정50 | 헤이트2004→세피아2005→헤이트2006/2007→마샤2003 | 보류.2009 선행·플룻/하프 생산·소라 교환/이동,주머니774에서부츠12351 연결 미완. |
| 법사15 | 젬3000→3001,644 실제 중간보상→645 교환 구현 | 정상 경로 보류.과거 소켓 결과는 합성648/649/647 시작재료 범위이며 정상 사냥/획득부터의 동일 계보 완료 아님. |
| 법사30 | 게렝3002→3003,710 실제 중간보상→711 교환 구현 | 정상 경로 보류.3001 완료 저장 선행은 있으나690/709 정상 생산·획득 미연결. |
| 법사45 | 젬3006→게렝/젬3007 | 보류.3003 선행·특수물약12119/12120·지팡이12121 정상 생산·단계/소비 미완. |
| 법사50 | 신비한바위3005→타라스3004 | 보류.3007 선행·757/761 생산/전달·주머니778에서부츠12352 연결과원래 타라 시작 전이 미완. |

## 연결 2차 (2026-10-28)

고정75레코드와 공식29행을 다시 대조해, 기존 리키→아논과 같은 **출처를 구분한 LOCAL 교환·선행·저장 연결**을 우선한다. 아래 과거 실행은 각각 당시 소스와 시작 저장에 한정되며 이번 조합의 성공으로 합산하지 않는다.

| 이번 연결 대상 | 고정 근거와 LOCAL 실행 계약 | 남은 경계 |
|---|---|---|
| `royal_zero_search_document` 제로 수색문서 | QuestT1, zero1 queststart→zero3 questcomplete→zero7. 수색문서636×1 소진→붉은 망토646×1. 군주15, native NPC747/sprite971, L1J70554 배치 참고. | 재료 정상 획득·공식 scalar 소비 의미·원본 메뉴/화면 미확인. 뒤 군터까지 완료한 것으로 확대하지 않음. |
| `wizard_gereng_undead_bone` 게렝 언데드의 뼈 | QuestT3002, gerengt1→gerengt2→gerengt3. 기존 젬 마력서 완료를 저장 선행으로 검사, 뼈690×1 소진→신비한 지팡이710×1. 법사30, native NPC44/sprite237, L1J70009 배치 참고. | L1J의 옛 뼛조각/타라스 교환과 고정판이 달라 그대로 복사하지 않음. 재료 생산자·원본 UI 미확인. |
| `wizard_gereng_crystal_staff` 게렝 수정 지팡이 | QuestT3003, gerengt3→gerengt4→gerengt5. 앞 게렝 완료를 저장 선행으로 검사, 수정구709×1과 실제 앞 보상710×1 소진→수정 지팡이711×1. | 정상 수정구 획득·공식 추가EXP 미확인. 추가EXP0은 LOCAL 정책. |

고정 목표/보상 ID·수량 후보는 [QUEST_CATALOGUE](QUEST_CATALOGUE.md)의 B 근거이고, 공식 직업 레벨/보상 종류는 [QUEST_OFFICIAL_GUIDE](QUEST_OFFICIAL_GUIDE.md)의 A 근거다. 실제 소진·현재 메뉴 선택·저장 정책은 별도 LOCAL 구현이며, 아이템 원값 확인만으로 공식 서버 동작을 확정하지 않는다.

이전 보류 중 기사 군터1003→게라드1004→짐1002→게라드1005→줄리1010은 고정 재료·보상 대응이 있지만 군터 집map3와 짐 비밀방map237의 현재 던전 정책/이동 경로가 없다. 줄리 NPC303·보상770 미대응이라는 옛 사유는 해소됐으나 앞 사슬과 정상 생산자는 OPEN이다. 군주 제로 이후 군터2도 같은 map3 접근 문제가 남는다. 오스2000의 당시 UNKNOWN이었던cookie 변환은 위10/29 정적 근거로 해소해 단일 선택 퀘스트로 연결했다. 나머지 상위 단계의 선행/다단계/선택 계약, 무대화34개의 수락·게임플레이 의미도 미확정이다. 공식 해적섬6은 고정판 이후 자료, 카리프6은 종료 행사·소비수량 미확정으로 보류한다. 공식 직업16행은 고정 세부 단계와 중복되므로 합산하지 않는다.

### 라이라 시간 초과 조사

무수정 재실행 [quest-bot-tkzddtrf/result.json](../runs/quest-bot-tkzddtrf/result.json)은 **36체크 PASS**, 461요청·가상192.175초, 실제1처치·198이동·30공격·1줍기·서버 오류0·정상cleanup이다. [콘솔](../runs/quest-lyra-repro-20261028-01/console.log). 토템 재료·퀘스트 상태를 공급하지 않은 새 Lv12 기사 시험 저장에서, 서버 발급 ground UID268435643/source UID268435635·generation2·owner1의 아투바 토템157×1을 실제 획득→소진→200아데나(1000→1200) 정산→정상Quit/FIRST 재접속 복원을 확인했다. 초기 성장·공개 맵 진입은 시험 범위 밖이다.

기존 실패 `quest-bot-odw5deqe`의7처치·9ground·0pickup 기록에는 지상 아이템 종류와 필터 탈락 이유가 없어, 무드롭 RNG인지 안전/목표 선택 문제인지 소급 확정할 수 없다. 이번에는 수집 중 왕복 뒤 실제 전투·획득으로 회복돼 시간 초과가 재현되지 않았다. 과거와 현재의 선정 소스도 다르므로 동일 소스 재현 성공으로 주장하지 않는다. M5와 다른 봇 안전정책은 의심점이며 원인 확정이 아니다. **이번 작업에서 라이라 봇·몬스터 배치·드롭 확률·전투는 수정하지 않았다. 시간 초과 원인은 UNKNOWN이다.**

현재 조합은 옛 퀘스트 추가분149–153뿐 아니라 `data/m4/drops.json`의91–95→157–161도 공급한다. m4의 드롭 확률은 각각300000/1000000, 수량1이며, roll 출처는 LOCAL L1J droplist4973/5186/4903/4509/4729다. 아이템 신원은 고정 native dump1074–1078이다. 이번 성공 기록에는 source UID/generation은 있지만 producer template이 없어157 생산자를91 또는149 중 하나로 단정할 수 없다. 공식 variant와 LOCAL 확률의 근거를 섞지 않는다.

### 2차 최종 검증

정의는6→9개, 대화는5→7개다. 변경 파일은 `data/m2/quests.json`, `world_feature_quest.py`, 신규 `hunt_bot_quest_expansion.py`, 신규 `world_quest_expansion_tests.py`와 이 문서다. 고정 출처는 `QUEST_CATALOGUE.csv:2,36,37`, `dialogue.csv:522–561,1090–1099`, 해당 UML, item native dump1387/1395/1426/1434–1436, NPC dump397/33이다. 제로·게렝 배치는 L1J SQL49205/49191을 LOCAL 정책으로 사용했다. 젬의 추가 LOCAL 외형·배치 경계는 아래에 구분했다. 수동 실행 핀 파일·기존 시험·공유 코어·다른 기능·원본·사용자 저장은 수정하지 않았고 커밋하지 않았다.

제로 최초 소켓 실행 [quest-expansion-bot-z4f90eo2/result.json](../runs/quest-expansion-bot-z4f90eo2/result.json)은5체크·11요청 뒤 `received_zero1` 실패로 종료됐으며, 실제 수신은 기존 마을 기본 페이지zero2였다. 서버 오류0·정상cleanup이다. 퀘스트 등록 훅에서 **자기 퀘스트 NPC와 같은 placement_key의 메뉴만 치환**해 zero1을 공급하도록 수정했다. NPC/UID/배치를 바꾸지 않았고 다른 키 메뉴는 유지한다. 기존 실패는 보존했다.

최종 조합의 [통합 퀘스트 시험 로그](../runs/quest-expansion2-20261028/unittest-final-01.log)는 **61개 중59통과·2실패**,14.908초/exit1이다. 신규7개는 선행 거절, 실제 젬/게렝 중간보상 생산·소진·복원, 제로 직업/레벨·재수령 거절, 같은 키 메뉴 치환, 실지형을 통과하는 젬 등록·4E96 생성을 통과했다. 남은2개는 `world_quest_tests.py:36`의 정의6개 고정 기대(실제9개), `:366`의 젬 단독 공급자 고정 기대(실제 게렝70009/87502 추가)다. **전체 시험 통과가 아니며**, 사용자 지시대로 기존 `*_tests.py` 기대값은 수정하지 않고 통합 담당에게 이관한다. 제품 로더나 시험 선택으로 실패를 숨기지 않았다. 앞선59/60/61개 중간 실행 로그도 같은 폴더에 보존했다.

게렝 선행 젬의 첫 두 실행은 [y9_s48i6](../runs/quest-expansion-bot-y9_s48i6/result.json)·[qg8o2405](../runs/quest-expansion-bot-qg8o2405/result.json)에 `M5 current NPC70531 unavailable` SKIP/정상cleanup으로 보존했다. 첫 접점은 후보·외형 미선정이었고, 기존 리키와 같은 **명시 LOCAL L1J gfx1307**을 퀘스트 runtime에 등록했다. fixed NPC 신원은null·원본 외형은UNKNOWN을 유지한다. 다음 접점은 원 SQL49190의map0/32587,32927이 실제 WorldTerrain에서 막힌 칸이라 정상 NPC 등록이 거절된 것이었다. 원 SQL 좌표는 `spawns`/`reference_original_spawn`에 보존하고, 최근접 통행 가능 칸인 **map0/32587,32926(북1칸)**만 LOCAL 적응 배치로 선택했다. 후보·UID·가시성·지형 검사를 우회하지 않았으며 봇에서 NPC를 직접 생성하지 않았다. 실지형 passable을 사용하는 등록·4E96 시험으로 신규 시험1개를 확인했다.

신규 소켓 시나리오의 시작 재료 공급은 정식 PASS가 아닌 교환·선행·저장 범위의 소켓 개발검증으로 구분한다.

| 최종 동일 제품 조합의 시나리오 | 결과·실제 확인 | 원결과 / 콘솔 |
|---|---|---|
| `royal_zero` | **PASS 11체크·22요청**, 가상8.105초. fresh 군주Lv15/UID2에636×1만 공급→정상 로그인/선택/월드→제로 수락→636소진/646지급→Quit/FIRST 완료·인벤 복원. | [결과](../runs/quest-expansion-bot-uzx73x85/result.json) / [콘솔](../runs/quest-expansion2-20261028/royal-zero-final-03.log) |
| `wizard_gereng` | **PASS 29체크·391요청**, 가상143.86초·실제180이동. fresh 법사Lv30/UID2에648/649/647/690/709 각1개만 공급→젬2교환으로644/645 생산→게렝690소진/710지급→709와실제710소진/711지급→Quit/FIRST 네 완료 상태·인벤 복원. | [결과](../runs/quest-expansion-bot-8ws8ufmi/result.json) / [콘솔](../runs/quest-expansion2-20261028/wizard-gereng-final-03.log) |
| `lyra` | **PASS 36체크·389요청**, 가상166.141초·1처치/152이동/33공격/1줍기. 재료·퀘스트 상태 공급 없이 실제 두다-마라 토템159×1(ground268435646/source268435639·generation2·owner1) 획득→소진/50아데나(1000→1050) 정산→Quit/FIRST 상태·인벤·위치 복원. | [결과](../runs/quest-bot-9e2nm3hv/result.json) / [콘솔](../runs/quest-expansion2-20261028/lyra-final-01.log) |

세 실행 모두 서버 오류0·정상cleanup이며, 시간은10배 가상시간이다. 신규봇 시작 재료/성장/위치는 명시적인 폐기 가능 시험 저장이며 완료 상태·중간/최종 보상을 주입하지 않았다. 최초 레벨업·공개 지역 이동·신규 재료 정상 획득·원본 클라이언트 입력/렌더링은 검증 범위 밖이다. 최종 제품 조합의 JSON/quest feature 식별값은 각 콘솔과 기존 source 기록에 보존했다. 라이라 시간 초과는 최종 실행에서도 재현되지 않았으며 원인 UNKNOWN을 유지한다.

```powershell
$env:SL_TEST_PORT_BASE='60000'
$env:SL_TEST_TIME_SCALE='10'
python -X utf8 -B -m unittest tools.local_original_session.world_quest_tests tools.local_original_session.world_quest_store_tests tools.local_original_session.world_quest_expansion_tests
python -X utf8 -B C:/Users/Chansol/AppData/Local/Temp/claude/D--claude/0483de89-75e7-4b94-84b8-fb31fe00f575/scratchpad/fastbot/run_fast.py hunt_bot_quest_expansion --scenario royal_zero
python -X utf8 -B C:/Users/Chansol/AppData/Local/Temp/claude/D--claude/0483de89-75e7-4b94-84b8-fb31fe00f575/scratchpad/fastbot/run_fast.py hunt_bot_quest_expansion --scenario wizard_gereng
python -X utf8 -B C:/Users/Chansol/AppData/Local/Temp/claude/D--claude/0483de89-75e7-4b94-84b8-fb31fe00f575/scratchpad/fastbot/run_fast.py hunt_bot_quest --scenario lyra
```

## 1차 조사 범위와 연결 결과

기존 내부 후보5개를 넘어 고정 버전 **26.09.29.2001**의 전체 자료를 목록화했다. [전수 목록](QUEST_CATALOGUE.md)과 [행별 근거 CSV](QUEST_CATALOGUE.csv)는 QuestT75개(대화 단계41·무대화34), UML1,131개와 대사 포함1,257stem, native 제작식154개·NPC29개/185대응을 담는다. 대화3,617행·이름/설명30,697행도 대조했다. CSV1,642행은 동일 의뢰의 여러 자료를 포함한 인덱스이며 독립 퀘스트 수가 아니다. A=공식 명시, B=고정 구조/대사/조작, C=이름/단서만, D=일반 서비스/결과로 구분했다. raw scalar의 서버 소비 의미는 여전히 별도 확인 대상이다.

[공식 가이드 대조](QUEST_OFFICIAL_GUIDE.md)는 전체12분류·61가이드 본문을 확인해 직업 단계16·토템1·해적섬6·카리프6의29행을 정리했다. 공식 자료가 주지 않은 수량·상태·생산자를 추정하지 않았다. 해적섬은 고정 버전 이후 자료, 카리프는 종료된 행사와 소비 수량 미확정 때문에 연결하지 않았다. 동적 제작 목록을 고정 보상 의뢰로 바꾸지 않았으며, 이번 두 아이템 교환은 **퀘스트 엔진**으로 연결했다. `world_feature_craft.py`와 제작 데이터는 수정하지 않았다.

등록 정의는 기존4개에서 **6개**, 대화 정의는3개에서 **5개**로 늘었다. 계산/저장/훅 엔진의 기존 가변 정산·소유 인벤·선행조건·forward transaction을 재사용했다. 새 전달/고정 처치수 의뢰는 완결 근거가 없어0개다.

| 새 연결 | 고정 근거·실제 계약 | 남은 경계 |
|---|---|---|
| `knight_riky_pledge` 리키 서약서 | QuestT1000, CSV605–636, riky1 queststart→riky3 questcomplete→riky5. 서약서639/1개 소진→기사의 두건651/1개. 수량은 고정 원값과 L1J Quest.xml128–148을 교차대조한 LOCAL 실행 정책. 기사15 조건은 공식 레벨 가이드와 대조. | 고정 NPC 신원/외형 미대응. L1J70798·gfx2337·map4/33127,33366을 명시 LOCAL 배치로 사용. 정상 재료 획득 경로 미연결. |
| `knight_aanon_red_hood` 아논 붉은 두건 | QuestT1001, CSV424–437, aanon4 queststart→aanon5 questcomplete→aanon6. 낡은 문서633/1·껍질650/1·두건651/1 소진→붉은 기사의 두건652/1. 리키 완료를 실제 저장 선행으로 검사. 고정 NPC200/sprite986, L1J70802 LOCAL 배치. | 633/650의 정상 생산자 미연결. 원본 메뉴 조건·입력·렌더링·추가 경험치 미확인(LOCAL 추가EXP0). |

공식 토템 가이드는 라이라의 수락→수집→정산→계약 유지/종료와 종료 후 재수락 및 단가200/100/50/30/50을 명시한다. 아래 옛 기록의 “반복/종료는 L1J만 참고” 경계는 이 공식 근거로 보강됐다. 현재 제품149–153 variant의 드롭 확률과 배치·영수증 UI까지 공식으로 확인된 것은 아니다.

줄리는 QuestT1010의 julie↔ladark와 고정 NPC303, 보상770을 확보해 이전 NPC/보상 미대응 일부가 해소됐다. 이올라도 QuestT12의 보상756/676/1295를 확보했다. 군터 기사30은 QuestT1003의121→123 대응이 있다. 이들은 선행/생산자/정상 전이가 남아 있으며 아래 이전 검토의 미확정 문구보다 전수 목록의 새 근거가 우선한다. 직업이나 교환형이라는 이유로 제외하지 않았다.

## 1차 검증

최종 조합의 기존 퀘스트 시험은 **54 tests OK / 12.343초**다. [원로그](../runs/quest-catalogue-20261028/unittest-final.log). 신규 정의 등록에 직접 대응하는 `world_quest_tests.py`의 정의 개수4→6 한 줄만 갱신했고, 기존 행위·수량·저장 실패 기대는 바꾸지 않았다.

```powershell
$env:SL_TEST_PORT_BASE='60000'
$env:SL_TEST_TIME_SCALE='10'
python -X utf8 -B -m unittest tools.local_original_session.world_quest_tests tools.local_original_session.world_quest_store_tests
python -X utf8 -B C:/Users/Chansol/AppData/Local/Temp/claude/D--claude/0483de89-75e7-4b94-84b8-fb31fe00f575/scratchpad/fastbot/run_fast.py hunt_bot_quest --scenario knight_exchange
```

신규 시나리오 [원결과](../runs/quest-bot-_7hbarn3/result.json), [콘솔](../runs/quest-catalogue-20261028/knight-final.log)은 **소켓 개발검증 PASS**,18체크·135요청·가상48.868초·실제16.685초, 서버 실패0·정상cleanup이다. fresh Lv15 기사 시험 저장에 **합성 시작 재료639/633/650 각1개**만 공급했다. 퀘스트 상태·중간보상651·최종보상652는 주입하지 않았다. 정상 로그인→선택→월드→리키 수락/보유 진행→639소진/651지급→실제 이동/아논 수락/선행검사→633/650/651소진/652지급→정상Quit/FIRST재접속 뒤 두 완료 상태와 인벤 복원을 확인했다. 선정 퀘스트 소스 조합은 결과의 `selected_source_sha256`에 있다. 시작 재료를 정상 플레이로 얻은 저장이 아니므로 **정식 PASS나 전체 직업 퀘스트 완료가 아니다**. 현재 엔진의 교환·선행·저장 연결만 확인한 결과다.

최초 기존 라이라 실행은 정상 로그인·수락 이후 `LYRA_NORMAL_TOTEM_DROP_PICKUP_DEADLINE`으로 실패했다. [원결과](../runs/quest-bot-odw5deqe/result.json), [콘솔](../runs/quest-catalogue-20261028/lyra-initial.log):1,250요청·70체크·가상611.846초, 실제7처치·544이동·줍기0, 서버 실패0·정상cleanup. 초기화 오류가 아니라 실제 수집 단계 실패이며 원실패·시험 저장을 보존했다. 토템 지상 관측/소유/안전 필터 중 어느 단계가 막혔는지는 이 로그만으로 UNKNOWN이다. 제품 몬스터·드롭·RNG·전투를 바꾸지 않았으며, 아래 옛 라이라 성공을 이번 조합의 성공으로 합산하지 않는다. 재실행은 위 환경과 runner에서 마지막 인자만 `--scenario lyra`로 지정한다. 실제 listener는 기존 매핑상60000/62030, 논리endpoint12000/14030이다.

변경 파일은 `data/m2/quests.json`, `hunt_bot_quest.py`, `world_quest_tests.py`, 이 문서와 `QUEST_CATALOGUE.md/.csv`, `QUEST_OFFICIAL_GUIDE.md`다. 원문 수집/시험 결과는 기존 `runs/quest-catalogue-20261028/`와 위 봇 시험 폴더에 보존했다. 퀘스트 엔진 코드·다른 기능·원본·사용자 저장·ACTIVE_TASK·수동 실행 스크립트는 수정하지 않았다. 변경된 파일 중 확인한 수동 실행 핀 대상은 없으며 커밋은 하지 않았다.

원본으로 남은 확인은 리키 NPC의 고정 외형/신원, 실제 시작 메뉴 조건·버튼/선택·보상 프레임/영수증 소비·퀘스트 진행 UI·정상 재료 획득이다. 이번 요청에서는 원본 클라이언트를 실행하지 않았다.

## 이전 내부5후보 검토와 실행 이력

아래는 이번 전수 조사 이전의 근거·실행 이력이다. 과거 성공은 그때 선정 Source/저장에 한정되며 이번 조합의 성공으로 합산하지 않는다.

2026-10-28 검토 후보 **5개 중 라이라 1개를 실행 LOCAL 정책으로 승격**했다. 등록 정의는 기존 젬2·군터1을 포함해4개, native dialogue는3개다. 라이라는 현재 보유한 종류만 전량 소비해 단가별 아데나를 정산하고 재계약/종료한다. 배달·고정 처치수·선행 상태를 처리하는 기반은 구현했으나 출처가 닫힌 신규 의뢰를 확보하지 못해 그 종류의 등록 수는0이다. 남은 후보4개는 아래 재조사에서 신규0개 승격으로 마감했고, 이전 직업 후보2개와 함께 실행하지 않는다. 기존 `candidates_not_loaded`의 라이라 행은 승격 이력으로 보존하고 실제 실행 데이터는 `quests`에 둔다.

## 확인 범위와 실제 지원

- 우선 자료: `work/local_resource_provider/assets/data/dialogue.csv`·UML, `work/source_game_data/native-dump-v1.jsonl`. `string.csv`는 이름/토큰 자료이며 퀘스트 규칙의 근거로 쓰지 않았다.
- 보존 공식 자료: `tools/local_original_session/data/official/items.json` 및 거기에 연결된 `work/official_data/raw/item/{id}.json`. 여기의 아이템 설명과 클라이언트 ID 대응을 사용했다. 이번 재조사는 오늘 갱신된 `work/official_data_refresh_20261028/raw/item/{id}.json`도 대조했다. 공식 사이트 한정 웹검색은4개 NPC의 추가 규칙을 찾지 못했으며, 미색인을 규칙 부재로 판정하지 않는다.
- 참고 backend: `D:/SingleLineageRef/l1j-en-classic/`. 수량·조건·배치·정산 방식은 별도 `local_policy` 참고이며 공식 Classic 계약으로 채택하지 않았다.
- 로더는 `quests`만 읽는다. 기존 젬은 저장·수집·반납 runtime, 군터는 공유 단계/수락/배치가 미완인 계산 후보라는 기존 차이를 유지한다.
- `world_quest.py`는 collect/deliver/kill/talk 계산, 가변 정산, 선행 완료 검사, 반복 회차를 지원한다. `world_feature_quest.py`는 수락·현재 인벤 진행·반납, 실제 발급 UID 저장/수신 NPC 검사/소진, 코어 `after_kill` 구독을 연결한다. 다른 선택 기능의 메서드를 호출하지 않는다. 장비 참조는 기존 `world_core_kit`이 공유하는 broker 장비 소유자 재사용이다. 실제 talk 이벤트 발행은 미연결이다.
- `QuestStore`의 기존 forward intent/CAS로 퀘스트·인벤·경험치·필요 장비 anchor를 저장/복원한다. 새 optional `cycles`/`issued`/`closed` 필드는 과거 V1 저장/intent를 읽으며, 발급은 정상 UID allocator를 쓰고 동일 template의 다른 UID로 배달을 대체할 수 없다. 응답은 저장 뒤 발행한다. 반복 완료 횟수와 종료 상태는 재접속에도 남는다.

## 라이라 실행 정책과 원본 미확인 경계

- 단가: Classic CSV2492의 아투바200/네루가100/두다-마라50/간디30/로바50. L1J `C_NPCAction.java:1322-1408`의 전량 정산/계약 흐름만 참고한다. L1J 코드의 Gandi/Rova 단가는 SQL 이름과 Classic CSV에 비해 뒤바뀌어 있으므로 복사하지 않았다.
- NPC90·sprite796·토템157–161·icon258–262는 native dump57/1074–1078. 배치32745,32428/map4/heading4는 SQL49164의 **LOCAL 배치**다. 직업4종/min1·현재 저장에 따른 메뉴 선택·추가 EXP0도 LOCAL 정책이다.
- 현재 제품 오크149–153은 기존 m6 데이터가 L1J45149/45171/45143/45098/45127에 대응시킨 별도 variant다. 그 오크의 토템 드롭은 SQL4973/5186/4903/4509/4729의30%·1개를 채택한 **LOCAL backend 정책**이다. 공식91–95는 각 토템을 명시하지만 공식149–153에는 토템이 없다. 공식91–95의 드롭을 제품149–153에 대한 공식 근거로 확장하지 않는다. 몬스터 생성·능력치·RNG·배치는 이번 변경에서 조정하지 않았다.
- UML `lyraEv1` queststart, `lyraEv4` questExchange, `lyraEv5` questcomplete와 CSV2498의 lyraEv8 link를 사용한다. 반복 수락·계약 종료·빈 재료 응답은 기존 페이지로 연결한 LOCAL 메뉴 정책이다. `misc_quest_receipt` dynamiclist·공식 메뉴 조건·보상 프레임 순서는 UNKNOWN이며 일반 인벤 quantity/add/remove로만 반영한다.

## 후보와 부족한 계약

| 지역·후보 | 확인한 원문·ID | 등록하지 않은 이유·다음 최소 입력 |
|---|---|---|
| 화전민·라이라 토템 | CSV:2488–2502, 특히2492 단가,2494 현재 보유 토템 정산. UML lyraEv1:10 queststart, lyraEv4:10 questExchange, lyraEv5:8 dynamiclist·:13 questcomplete. dump:57 NPC90,1074–1078 item157–161. 공식 items157–161도 라이라 교환 명시. | **실행 LOCAL 정책1개 승격.** 보유한 종류만 전량 정산·재계약/종료·저장/복원을 연결했다. 고정1개 퀘스트5개로 축약하지 않았다. Classic 영수증·메뉴 조건·공식 variant별 드롭은 미확인. |
| 기란·이올라 유품 | CSV:2728 목걸이1/반지1,2729–2730 산적/서큐버스,2737 보상은 아끼는 물건. iolap9:10 queststart, iolap6:9 questcomplete. dump:246 NPC415,1675–1676 item12110/12111. 공식 items12110/12111은 기란 이올라 명시. | **보상·선행 생산자 미연결.** 오늘 공식 raw12110/12111도 이올라 반환처만 명시한다. L1J70625는 L1Npc 카탈로그 행만 확인했고 일치하는 npcaction70625/Classic `iolap`의 보상·데이먼/변장 소매치기 전이를 확보하지 못했다. CSV의 별도 `iola1` 그렘린 설명을 그 매핑으로 사용하지 않았다. 군주라는 이유로 제외한 것이 아니며, 정상 수락 전이와 보상 전후 인벤 ID/수량·진행도 및 도난물 생산자 확보가 최소 입력이다. |
| 은기사·줄리 가죽 제작 | 공식 item12112 설명은 줄리에게 사이클롭스 피로 장비 제작. CSV ladark4_1:2772는 고급피혁20/벨트1/피1. dump:1219–1220,1677은334/335/12112. ladark3:10·ladark7:8에 start/complete. | **NPC·결과 대응 미확인.** 제작도 이번 검토 대상이나, 오늘 공식 raw12112는 줄리의 특별 장비라고만 한다. ladark7 complete 이후 결과 ID/수량과 줄리 template/stem이 필요하다. native181의 라다르300/$1053 및 L1J70523의 ladar1/ladarC1은 다른 이름의 옛 경로여서 줄리로 대체하지 않았다. |
| 기란 후보·모리아 재료 연구 | CSV:280–282 연구 답례로 모자·옷 제작. dump:204 NPC346,1242–1243 item385/386. L1J SQL:22251 NPC70598,23858 moria1,49094 map4/33404,32834는 LOCAL 배치 참고. | **동적 제작 선택·소비 미연결.** 오늘 공식 raw385/386은 제작처 모리아를 명시한다. L1J ItemMaking.xml:502–522에 모자/옷 각1의 제작식2개도 확보했으나 수량은 LOCAL 참고다. Classic moria1:8 craft_output→moria2:8 craft_input/:9 request_craft의 서버 발급 recipe reference·요청 payload·소비가 현재 엔진에 없다. 정상 목록 선택→재료 표시→제작 요청·인벤 전후가 최소 관측이며 queststart 의뢰로 바꾸지 않는다. |
| 집시촌 후보·헤이트 플룻 | CSV:2442–2452 요정 호칭과 플룻 반환. dump:1461–1462 item762/763. L1J Quest.xml:322–338 Elf45·공유Level45·플룻1→소라1/step3. | **공유단계·플룻 생산자 미연결.** CSV2452가 보상 소라763을 직접 명시한다. L1J 정상 경로는 요정45+Level30완료→Masha가 Level45=1 생산→Heit=2→Sepia/map302·Sin of Sepia45301 처치/플룻→Heit교환=3이다. 현재 데이터에는 그 선행·이동·몬스터·드롭이 없어 강제 상태 주입 없이 닫히지 않는다. 직업이라는 이유의 제외가 아니며 정상 전이/획득/교환 한 계보 확보가 최소 입력이다. |

조사 이력은 기존 직업 후보2개를 포함해 `candidates_not_loaded`7행으로 보존한다. 그중 라이라1행에는 승격된 quest ID를 명시했다. 은기사 줄리의 NPC 대응을 확정하지 않았고, 모리아/헤이트의 본토 위치는 명시한 출처 범위만 사용한다.

## 남은4개 재조사 결론

신규 승격은 **0개**다. 제작·직업을 금지로 재적용하지 않고 현재 생산자→정상 메뉴→소비→보상→저장 계약이 닫히는지 판단했다. `candidates_not_loaded`4행에는 새 분류·출처·최소 관측을 반영했고, `quests`4개/`native_dialogues`3개와 엔진 계산·저장 형식은 유지했다. 모리아2제작식은 결과385/386 대응과 함께 LOCAL 참고로 보존했다. 재료 수량을 공식 Classic 제작식으로 표시하지 않는다.

헤이트의 출처는 `L1MerchantInstance.java:185–201,438–449`, `Quest.xml:308–338`, `L1TeleporterInstance.java:111–119`, SQL6427/19423/20895/44944다. `request mystery shell` XML 자체에는 Class=E만 있고 QuestId/QuestStep/Level 제한은 없다(`L1NpcXmlAction.java:127–135`는 QuestId 없으면 true). 정상 메뉴·Sepia 경로의 선행과 XML 교환의 무제한 조건을 구별했으며, 임의 guard를 원본 규칙으로 만들거나 교환만으로 전체 퀘스트를 완료 처리하지 않았다.

## 일반 배달·처치 및 지역별 남은 자료

- 말하는 섬/글루디오·글루딘/켄트/우드벡에서 확인한 군터·리키·아논·제로·아리아·짐 관련 의뢰는 기존 또는 직업/공유단계 경로다. 새 일반 의뢰로 등록하지 않았다. 군터 CSV:672의 훗날 편지 요청은 발급물·수신 상태·보상 계약이 없어 배달로 구현하지 않았다.
- 화전민 라이라의 일반 수집·가변 정산/계약은 LOCAL 정책으로 연결했다. 기란은 이올라의 실제 보상·선행이 부족하고 모리아는 동적 제작 선택/소비 접점이 미연결이다. 은기사는 줄리 제작의 NPC/결과 대응이 부족하다. 제작·직업이라는 분류 자체는 이번 승격의 금지 조건이 아니다.
- 하이네·그 밖의 본토 일반 배달/고정 처치수 의뢰는 이번 확인 자료에서 발급 NPC·목표 수/물품·수신 NPC·보상까지 갖춘 계약을 확보하지 못했다. 해당 퀘스트가 없다는 결론이나 전 지역 전수 조사 완료를 뜻하지 않는다.
- 일반 배달을 추가하려면 정상 발급물의 UID/소유·수신 NPC·소진·보상 저장/복원, 처치형을 추가하려면 출처 있는 대상과 횟수·보상 및 실제 committed kill 이벤트 소비가 필요하다. 수집물의 드롭 설명을 고정 처치수로 바꾸지 않았다.

## 검증·변경 경계

변경은 퀘스트 코드/기존 시험/실행 데이터/기존 봇과 이 문서로 한정한다. ACTIVE_TASK·manual-user-play/manual-test-knight·사용자 저장·원본은 수정하지 않는다. 수동 실행 스크립트의 핀 대상에 퀘스트 파일은 없으므로 핀 수정은 없다. 커밋과 원본 클라이언트 실행은 하지 않는다.

검증 명령은 `python -X utf8 -B -m unittest tools.local_original_session.world_quest_tests tools.local_original_session.world_quest_store_tests` — **54 tests OK**, 최종8.610초/exit0. 기존 임시 저장과 실제 디코더/라우터 시험을 유지하고, 발급 UID 바꿔치기 거절·수신 NPC·소진/복원·2회 정산/종료복원·선행 재검사·등록 after_kill 처리·optional 상태의 중단복구를 확인했다. 달성된 kill/talk 목표는 다음 kill의 event ID를 계속 누적하지 않는다. 이 synthetic 계약들은 신규 의뢰 등록 수에 합산하지 않는다.

실행 명령(PowerShell):

```powershell
$env:SL_TEST_TIME_SCALE='10'
$env:SL_TEST_PORT_BASE='32000'
python -X utf8 -B C:/Users/Chansol/AppData/Local/Temp/claude/D--claude/0483de89-75e7-4b94-84b8-fb31fe00f575/scratchpad/fastbot/run_fast.py hunt_bot_quest --scenario lyra
```

최종 결과: [quest-bot-x5zs2e2e/result.json](../runs/quest-bot-x5zs2e2e/result.json) **PASS**,25 checks·253 requests·가상92.424초·실제21.437초, server failure0·cleanup complete. 새 보존 시험 저장의 Lv12 기사로 정상 로그인/선택/월드 진입 → 라이라 수락 → 실제 이동103/공격10/처치1 → 서버 소유 ground UID로 간디 토템160/1개 획득 → 현재 보유분 소진/30아데나 정산(1000→1030) → 정상 Quit/FIRST 재접속 뒤 상태·인벤·위치 복원을 확인했다. 선정된 퀘스트 코드/데이터 해시는 결과의 `selected_source_sha256`에 있다. 반복 두 번째 정산·종료 및 일반 배달/고정 처치수/선행은 위 개발 시험 범위이고 이번 소켓 시나리오의 PASS에 합산하지 않는다.

시작 저장은 기존 test_knight fixture와 pre-login 순수 성장 API로 준비했다. 처음 성장/공개 경로의 화전민 이동은 제외한다. 기존 봇 시작칸32746,32429가 실제 S32에서8방향 blocked인 결함을32744,32429로 정정했으며, 몹/드롭 생성·보상·퀘스트 상태·현재 HP·RNG 주입은 없다. 사냥 중 제품의 LOCAL 드롭을 실제 소비한 시험이며 공식 variant별 드롭·원본 입력·렌더링·영수증 화면의 검증이 아니다.

실패도 모두 보존했다. [quest-bot-c59h7bhi/result.json](../runs/quest-bot-c59h7bhi/result.json)은 Lyra NPC row의 `l1j_impl` 누락으로 수락 클릭에서 `KeyError`/SERVER_EOF, [quest-bot-ggijthrd/result.json](../runs/quest-bot-ggijthrd/result.json)와 [quest-bot-upt2edr5/result.json](../runs/quest-bot-upt2edr5/result.json)는 위 blocked 시작칸 때문에 이동0/사냥 deadline 실패다. 둘째 실패 진단 중 경로 탐색 확대를 시도했으나 효과가 없어 최종 코드에서는 제거했다. 모두 정상 finally/cleanup과 원실패·시험 저장을 보존했다. 첫 명령의 모듈명을 전체경로로 준 import-only 오류(`No module named 'tools.local_original_session.tools'`)는 서버/포트 시작 전 콘솔 오류이며 basename 호출로 정정했다.

## 후보4개 재조사 후 회귀 결과

2026-10-28 신규0승격/기존 실행 정의4개를 대상으로 기존 퀘스트 시험 **54 tests OK**,10.225초를 확인했다. 명령은 위 unittest와 같고 `SL_TEST_PORT_BASE=54000`을 사용했다. 로그는 [quest-candidates-review-20261028/unittest.log](../runs/quest-candidates-review-20261028/unittest.log)에 보존했다. 기존 시험 기대값은 수정하지 않았다.

위 라이라 명령을 같은 runner·`SL_TEST_TIME_SCALE=10`·`SL_TEST_PORT_BASE=54000`으로 실행했다. 기존 `test_ports` mapping의 실제 listener는 **54000/56030**이며 논리 endpoint는12000/14030이다. [quest-bot-dv5kv1z3/result.json](../runs/quest-bot-dv5kv1z3/result.json)은 **PASS**,32 checks/314 requests·가상122.717초·실제41.094초, server failure0/cleanup complete다. Lv12 기사 정상 로그인→선택→월드→라이라 수락→실제 처치/서버 소유 ground UID로 간디 토템160x1 획득→전량 소진/아데나1000→1030→정상Quit/FIRST 재접속의 상태·인벤·위치 복원을 확인했다. 시작 저장은 기존 test_knight/pre-login 성장·saved-map fixture로, 최초 성장/공개 이동은 범위 밖이다. 실행 당시 선정 소스7개의 SHA256은 해당 결과 `selected_source_sha256`에 있다. 실행 후 JSON의 이올라 L1J 설명에서 미확정 iola1 연결을 제거한 metadata 문구만 정정했으며 실행 정의·계산·시험 입력은 바꾸지 않았다. 신규4후보를 실행한 결과나 원본 화면/입력 PASS로 확대하지 않는다.

첫 실행 [quest-bot-z95a3jot/result.json](../runs/quest-bot-z95a3jot/result.json)은 requests0에서 상속된 M5 `instrument()`의 `seed_fixture` 누락으로 FAIL했고 cleanup complete다. `hunt_bot_quest.py.open()`에 부모의 기존 seed 플래그 전달1줄을 연결한 뒤 위 재실행이 통과했다. 수량·UID·보상·상태·RNG 주입은 추가하지 않았다. 첫 실패와 두 콘솔 로그도 [quest-candidates-review-20261028](../runs/quest-candidates-review-20261028)에 보존했다. PowerShell은 runner의 stderr FAST_CLOCK 요약을 NativeCommandError 형식으로 기록했으나 실제 재실행 python exit는0이다.

이번 변경 파일은 `data/m2/quests.json` 후보 metadata4행, `hunt_bot_quest.py` fixture 연결1줄, 기존 `QUEST_EXPANSION.md`/`DEFERRED_BACKLOG.md` 퀘스트 문장이다. 엔진3파일·기존 시험·다른 기능·원본·사용자 저장·manual 프로필·launcher/start-manual-play는 수정하지 않았다. 수동 실행 핀 변경은 없으며 핀 검토 대상은 위 JSON·봇2파일이다.
