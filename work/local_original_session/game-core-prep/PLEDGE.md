# 혈맹 기본

원본 기준은 고정 클라이언트 `26.09.29.2001`과 [요청 지도](REQUEST_COVERAGE_MAP.md)의 보존 정적 분석이다. 원본 함수·필드 확인, 로컬 서버 구현, 소켓 시험, 원본 창 확인을 구분한다. 이번 작업에서 원본 클라이언트는 실행하지 않는다.

## 규칙과 출처

- [공식 혈맹 가이드](https://lineageclassic.plaync.com/ko-kr/guidebook/view?title=%ED%98%88%EB%A7%B9): 미가입 군주, 레벨 5 이상, 창설 비용 1,000아데나. 이 조건을 L1J보다 우선한다.
- L1J 참고: `D:/SingleLineageRef/l1j-en-classic/src/l1j/server/server/clientpackets/C_CreateClan.java`. 군주·미가입·중복 이름 검사 참고이며 이 버전의 비용·레벨 조건 근거로 사용하지 않는다.
- 공식 해산 제한에는 혈맹 창고 물품, 성·아지트 소유, 선포한 공성 상태가 포함된다. 해당 시스템이 없는 이번 기본 혈맹을 성·아지트·공성 구현 완료로 해석하지 않는다.

## 원본 필드와 소비 경계

CS 스키마·opcode는 [요청 지도 JSON](REQUEST_COVERAGE_MAP.json), 추가 SC 7종·중첩 DTO 2종·43필드는 [SC 스키마](pledge-evidence/sc-schema.json), 필요한 native 소비자는 [소비 계약과 RVA 원문 위치](pledge-evidence/consumer-contracts.json)에 보존한다. 대상은 고정 분석 carrier `DERIVED_RESTORED_ANALYSIS_ONLY.exe`, SHA256 `c822838351d774a2022af434829a36dbd9bee030bf22182b834ca4e8659701a9`다. 분석 carrier를 무수정 온라인 원본으로 주장하지 않는다.

| 요청 / 응답 | 확인 사실과 제한 |
|---|---|
| CREATE `071B` / `071C` | CS f1 문자열, f2 enum은 원 sender에서 0 설정. f3/f4 문자열 확장은 지원하지 않는다. SC f1=true와 f2 혈맹명이 창설 완료 문구84로 연결된다. |
| JOIN `0709` / `070A` | CS f1 혈맹명으로 싱글 즉시가입 처리. f2 bool은 UI의 부재/defaultfalse 및 전달 경로를 확인했으나 의미는 UNKNOWN. f3 암호 확장은 미지원이다. SC enum0은 가입완료·INFO0722 자동요청, 1은 가입신청완료이므로 거절로 쓰지 않는다. 미존재4·가입불가7을 소비 문구로 확인했다. |
| INFO `0722` / `0723`, 구성원 `0724` | INFO f1→model+20→LEAVE CS f1과 actor+A8의 동일 혈맹 문자열 연결. 멤버 목록 f1은 총페이지수, f2는 0기반 페이지로 단일 페이지는 `(1,0)`. MemberInfo f4 uint64는 합친 목록의 중복 제거 키다. f1 문자열·계급/직업 필드의 정확한 원 이름과 enum은 별도 미확인이다. |
| LEAVE `0715` / `0716` | CS f1은 model+20의 혈맹 문자열. 싱글에서는 구성원이면 탈퇴, 군주이면 해산한다. SC f1 bool 형식은 확인했으나 native 후속 UI 소비는 미확인이다. |
| UPDATE_NOTICE `0727` / `072B` | 원 sender는 textbox 200자 검사를 거쳐 f1에 텍스트를 넣는다. ACK f1과 INFO f7이 같은 model+98 문자열에 들어가는 연결을 확인했다. notice/소개 명칭 및 최종 위젯 표시 의미는 미확인이다. |
| LIST `071E` / `071F` | 요청·응답 형식은 확인되지만 f1의 원 검색/필터 의미와 응답 DTO 의미는 별도 미확인이다. 지원 범위는 구현 결과에 구분한다. |

compiled descriptor는 타입·필드번호 근거이며 원 `.proto` 이름·requiredness·공식 서버의 전체 응답 의무를 복원한 것은 아니다. 타입만 알려진 필드를 임의 enum으로 채워 전체 혈맹 창 완료로 주장하지 않는다.

## 범위와 다음 단계

`tools/local_character_creation/realm.py`의 기존 계정 문서에 선택 루트 필드 `pledges`를 추가한다. 예전 저장은 필드 없이 그대로 읽으며 기존 캐릭터·기억 장소·UID를 보존한다. 혈맹 ID·군주 UID·구성원 UID·공지의 소유자는 혈맹이다. 같은 계정 캐릭터만 가입시키는 현재 싱글 정책이며 계정 슬롯 수 제한을 공식 최대 혈맹원 수로 주장하지 않는다.

창설 비용과 계정 저장은 서로 다른 파일이다. 혈맹 선택 필드의 `pending_creation`에 실제 인벤토리 before/after와 창설 대상을 먼저 기록하고 기존 인벤토리 CAS로 비용을 저장한 뒤 활성 혈맹으로 확정한다. 같은 정상 CREATE 재요청에서 현재 인벤토리가 before이면 비용을 저장하고, after이면 재차감 없이 확정한다. 제3상태면 미완 기록을 보존하고 거절하며 임의 되감기·환불·성공 처리를 하지 않는다. 단위 시험은 비용 저장 전 실패와 비용 저장 후 최종 계정 쓰기 실패를 주입해 이 경계를 확인한다. 프로세스 강제 종료 시험과 동일한 증거로 확대하지 않는다.

혈맹 소유 데이터에 같은 계정 캐릭터의 가입 관계를 저장한다. 동료 파일과 동료 런타임은 수정하지 않는다. 동료 머리 위 혈맹명·문장 표시, 동료 UI의 가입 상태 연동은 다음 단계다. actor f19/f20 접점은 [동료 표시 근거](COMPANION_DISPLAY_EVIDENCE.md)에 보존되어 있으며 임의 ID 주입으로 표시 완료를 주장하지 않는다.

동맹과 opcode 미결속 요청 11종은 계속 UNKNOWN이다. 기본 공지 `UPDATE_NOTICE`와 미결속 `UPDATE_ENTER_NOTICE`를 혼동하지 않는다.

## 소모품 3종 연결 검토

| 아이템 | 근거와 결과 |
|---|---|
| 806 혈맹 귀환 주문서 | `tools/local_original_session/data/official/items.json`의 공식 설명은 성·아지트를 소유한 혈맹원의 해당 거점 귀환이다. 기본 혈맹만 생겼다고 임의 마을로 보내거나 소비하지 않는다. 성·아지트 소유 관계와 정상 목적지·이동 소비 계약이 필요하다. |
| 15400 오만 1층 이동 주문서 | `data/m6/map_expansion4.json`에는 map101~105 지형·계단이 있고 `world_maps.load_dungeon_policy`가 읽는다. 이것은 주문서 목적지·입장·이동 소비 연결의 증거가 아니다. 혈맹과 별개인 해당 계약을 연결해야 하며 가입으로 해금하지 않는다. |
| 15410 오만 11층 이동 주문서 | 위 오만 확장에 11층 map111은 없다. 목적지·입장·이동 소비 계약이 필요하다. 기존 무소비 미지원 처리를 유지한다. |

[소모품 확장](ITEMS_CONSUMABLES_EXT.md)과 [보류 목록](DEFERRED_BACKLOG.md)의 기존 실패·보류 근거를 보존한다.
현 소비자 `tools/local_original_session/world_item_effects.py`의 세 아이템 분기는 여전히 명시적 무소비 미지원이다. 이 검토에서 해당 파일은 수정하지 않았다.

## 확인 범위

원본 창의 버튼 입력·공지 갱신·멤버 목록 표시·응답 소비는 실제 원본으로 후속 확인해야 한다. INFO 군주명, 구성원 계급·직업·레벨 필드는 의미 미확정으로 송신하지 않는다. 구성원 이름은 DTO f1 문자열, 저장 캐릭터 UID는 중복 제거 f4의 명시적 LOCAL projection이다. LIST의 부분문자열 검색과 DTO f1 혈맹명도 LOCAL이다. INFO 무가입 상태의 빈 문자열·목록과 LEAVE bool의 실제 창 초기화는 원본으로 확인해야 한다. 서버·직접 패킷 성공은 이 화면 동등성의 증거가 아니다.

## 변경 파일과 검증 결과

- 새 코드: `tools/local_original_session/world_feature_pledge.py`, `world_pledge.py`, `world_pledge_tests.py`, `hunt_bot_pledge.py`.
- 기존 코드의 국소 변경: `tools/local_original_session/world_handlers.py` 선택 기능 등록 한 줄, `tools/local_character_creation/realm.py` 선택 `pledges` 저장과 혈맹 데이터 API. 기존 다른 작업자의 기억 장소 변경을 보존했다.
- 문서: 이 문서, `REQUEST_COVERAGE_MAP.md/json`, `DEFERRED_BACKLOG.md`, `pledge-evidence/`의 부족 SC·소비자 근거.
- 통합자가 핀을 갱신할 기존 수정 파일은 `tools/local_character_creation/realm.py`, `tools/local_original_session/world_handlers.py`다. 새 네 코드 파일도 추가 의존 대상이다. `start-manual-play.ps1`·`launcher.py`는 수정하지 않았다. 커밋 없음.

단위·직접 저장 회귀 명령:

```powershell
python -X utf8 -B -m unittest tools.local_original_session.world_pledge_tests tools.local_original_session.world_bookmark_tests -v
```

혈맹9개·기존 기억 장소16개, 총25개 OK. 창설·직업/레벨/잔액/이름 조건 거절·정보 wire·가입·공지 권한·탈퇴·해산·저장 복원·선택 기능 제외·비용 저장 전후 실패 복구·서로 다른 멤버 UID를 확인했다. 원본 UI 시험이 아니다.

소켓 봇 명령(저장소 루트):

```powershell
$env:SL_TEST_PORT_BASE='46000'
$env:SL_TEST_TIME_SCALE='10'
python -X utf8 -B C:\Users\Chansol\AppData\Local\Temp\claude\D--claude\0483de89-75e7-4b94-84b8-fb31fe00f575\scratchpad\fastbot\run_fast.py hunt_bot_pledge
```

결과: [최종 summary](../runs/hunt-pledge-r17co5vc/summary.json) **SUCCESS, 48체크, 21혈맹 요청, 3접속, cleanup_complete=true**. 기반46000의 기존 논리 endpoint 매핑은 물리46000/48030이며 새 포트 매핑을 만들지 않았다. 가상시간10배, 약20초. source SHA256 조합14개, 실제 starting-fixture와 요청/응답 ordinal·에포크별 FIRST/close 결과는 같은 디렉터리에 보존한다. 기준 HEAD는 `f599fd7af903e0724999fff110601c8a724d52f0`의 공동 미커밋 작업판이며 정확한 시험 조합은 summary가 우선한다.

새 소유 시험 저장은 FIRST 전 군주 `SoloMonarch` UID1/Lv5/3000아데나와 같은 계정 법사 `PledgeMage` UID2를 공급한다. 이후 기존 소켓 도구로 정상 FIRST→로그인→목록/캐릭터 선택→월드/인벤토리→혈맹 요청→Quit/close를 따른다. 군주3000→2000의 실제 비용·0965 수신·저장 일치, 조건 거절 후 연결 생존, 공지·INFO·LOCAL LIST, 법사 실제선택 후 JOIN→2행/서로 다른 UID→탈퇴→재가입, 군주 재접속 후2명/공지/잔액 유지, 군주 해산과 next_id2 보존을 확인했다. 사용자 저장·원본 실행·동료 런타임은 사용하지 않았다.

앞선 실패도 보존했다. [첫 시도](../runs/hunt-pledge-6kokct9o/failure.txt)는 FIRST 전 봇 fixture의 Creation 타입 불일치, [두 번째](../runs/hunt-pledge-w3t5yglj/failure.txt)는 군주 월드 진입 후 봇 기록 인자의 이름 충돌이었다. 둘 다 정상 정리했고 봇만 고쳐 같은46000에서 순차 재실행했다. 공용 alignment 초기화 실패는 발생하지 않았다. 실패 결과를 최종 성공에 합산하지 않는다.

기존 단일 큐 helper로 구현 `PLEDGE-basic-20261028-r17co5vc`와 시험 결과 `PLEDGE-basic-test-20261028-r17co5vc`를 등록했다. 다른 작업자의 항목은 변경하지 않았다.
