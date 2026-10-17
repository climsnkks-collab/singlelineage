# 언팩 에셋·게임 데이터 분석

2026-10-09 전수 필드 후속: [전체 테이블 의미·소비 코드 분석](ALL_TABLE_SEMANTICS.md)은 현재 바이너리19종·명명 텍스트31개·SPR1 총51자료를 같은 기준으로 추적했다. 생성 schema와 실제 소비·ID 사전·데이터 대조·unknown을 구분하며 [전체 색인](../work/all_table_semantics/index.json)에 표별 모든 필드 경로와 근거를 연결했다. 아래 초기 조사 이력의 “필드 정의 미확보”는 최신 결과를 대신하지 않는다. NPC 드롭 자식의0축복/1일반/2저주 대응, 아이템·마법 구조, 제작/퀘스트/확률표·소환/이동·명명 설정표 소비의 최신 판정은 새 보고서를 따른다. 전체 서버 전투·확률·퀘스트 공식을 확정한 것은 아니다.

2026-10-09 후속: [이동·공격 속도와 프레임 조사](CLIENT_SPEED_RESEARCH.md)에서 현재 원본 SPR 소비 코드까지 확인했다. `A.B:C`의 C는 단계 시간 가중치이고 기본 재생률은 24, 양수 `**N**`은 보정 전 한 동작의 N ms 지정 시간이다. 이동·공격은 각자 속도 보정축을 적용한다. 아래 10월 7일의 시간 의미 미확정 문구는 당시 조사 이력이며, SPX 픽셀·실제 화면 프레임·서버 공격 간격은 여전히 별도 검증 대상이다.

## 2026-10-07 독립 클라이언트용 연결 정보 확인

사용자 지시에 따라 이미 추출된 평문과 목록에서 연결 정보를 조사했다. **캐릭터 동작 목록·UI 이미지·지역과 맵 파일 사이의 연결은 있다. 필드 캐릭터 픽셀과 실제 지형·충돌까지 바로 재생할 수 있는 완성된 형식 해석은 아직 아니다.** 원본 클라이언트 수정·통신 분석과 분리된 자산 조사이며 새 게임 구현은 시작하지 않았다.

| 대상 | 이번에 실제로 확인한 연결 | 남은 해석 |
|---|---|---|
| 캐릭터·애니메이션 | `list.spr` 엔티티 ID → 별도 이미지 ID → 동작 → 순서 있는 숫자 토큰 → SPX 파일명 후보. 구버전 2,693개 정의/9,497개 동작, 현재 평문 2,976개 정의/10,664개 동작 | SPX 픽셀·내부 프레임, 방향 순서, 시간 단위, 효과/타격 표식. 정의 수를 캐릭터 종류 수로 보지 않는다. |
| 지도·지역 | 현재 region 226행의 맵 번호 169종 모두 현재 catalog의 `map/<번호>/`와 대응. 말하는 섬 던전 1층(region22→map1)의 실제 청크 12개는 현재 catalog SHA·크기와 모두 일치 | `.s32` 청크 좌표·레이어·타일 참조, `.til` 픽셀, 충돌·이동 가능 정보 |
| UI atlas | 구버전 plist29개 → 실제 PNG29개, 총4,014개 frame의 회전 반영 좌표·PNG 크기 검사 통과 | CSB node/timeline/event 구조와 실제 렌더 |
| 지도 화면 | 지도 UI ID → region ID → 맵 번호, 이미지 이름 → atlas frame → PNG. 현재 지도 이미지 이름159종 중142종이 구버전 atlas/파일에 대응 | 최신 변경/추가 이미지17종, 일부 region 참조, 좌표 변환식. UI 지도 번호와 실제 맵 번호는 다르다. |

구체적으로 `list.spr`의 `#0 312=3225 prince`는 엔티티0을 이미지 묶음3225에 연결한다. walk의 group0은 실제 `data_1/sprite/3000/3225-0.spx`, HD는 `data_4/sprite_hd/3000/3225-0.spx`에 대응한다. 일반 파일 후보 연결은 구버전13,555/13,584개, 현재 catalog15,250/15,274개다. 액션별 group 중복을 제거한 참조 횟수이며 고유 파일 수가 아니다. 현재 SPX 전체가 추출됐다는 뜻도 아니다. `A.B:C`의 내부 frame·시간 의미는 미확정이다.

재사용할 때 버전을 고정해야 한다. 현재67개 선별 자원에는 Characters_F·Outgames·Common PNG가 없다. 앞의 두 이미지는 구버전 현물과 현재 catalog SHA·크기가 같지만 **Common은 다르므로 현재 plist와 구버전 PNG를 섞으면 안 된다.** `782-0.spx`와 `782-00.spx`처럼 숫자로 합치면 충돌하는 서로 다른 파일도 있어 실제 경로를 보존해야 한다.

지도 UI의 `_id:1`은 실제 map1이 아니라 region0/21을 거쳐 map0에 대응한다. map1은 말하는 섬 던전 1층이며 실제 `.s32`12개/1,377,930B를 확인했다. `tile/list.til`은 구버전에서 ASCII `5066` 한 값뿐이므로 타일 배치표가 아니다. region의 bounds도 충돌 격자를 대신하지 않는다.

다음 자산 작업은 **캐릭터 표본의 SPX 내부 프레임·픽셀 해석**, 이어서 **한 맵의 S32→타일 배치와 TIL 픽셀 해석**이다. 그 결과로 방향·렌더 좌표를 검증한 뒤 이동 가능 정보와 연결해야 한다. 이번 요청은 연결 조사까지이며 새 엔진 구현·화면 재현 완료로 표시하지 않는다.

근거: [캐릭터·애니메이션](../work/asset_link_audit_20261007/sprite/report.md), [지도·타일](../work/asset_link_audit_20261007/map/report.md), [UI·atlas](../work/asset_link_audit_20261007/ui/report.md), [Root의 실제 표본·해시 독립 대조13개 PASS](../work/asset_link_audit_20261007/root-review.json). Sprite 산출물 대조25개도 PASS이며, 픽셀 렌더 검증은 포함하지 않는다. 소스 에셋·원본·보관 자료는 변경하지 않았다.

## 2026-10-05 기존 조사 이력

분석일: 2026-10-05. 구버전 `26.08.28.2002` 실제 평문 전체와 현재 `26.09.29.2001`의 인증 catalog·선별 평문을 구분했다.

**그래픽·음향뿐 아니라 아이템, NPC, 마법·효과, 퀘스트, 제작, 확률 안내 자료가 실제로 있다.** 핵심 데이터는 `imported/bin/*.bin`의 protobuf wire 형식이다. 현재 버전 바이너리 19개를 인증·복호화해 별도로 보존하고 레코드 구조·문자열·ID 관계까지 확인했다. 원본 `.proto`와 소비 코드의 필드 정의는 아직 확보하지 않아, 모든 숫자를 HP·가격·드롭률 등으로 이름 붙이지는 않았다.

## 조사 범위와 버전

| 자료 | 실제 확인한 범위 |
|---|---|
| 구버전 전체 평문 | **115,547개 / 7,735,421,268B**. 전체 SHA256·크기를 다시 읽어 과거 추출 기록과 대조, 불일치·누락·추가·읽기 오류 0 |
| 현재 전체 catalog | **131,889개 / 선언 평문 8,749,171,609B**. 서명·AEAD 인증 성공. 전체 현재 파일을 언팩한 결과는 아님 |
| 기존 현재 복호화 cache | 리소스 **38개 / 11,289,702B**, 전부 현재 catalog SHA·크기 재대조. `validation.json`까지 세면 디스크 파일은 39개 |
| 기존 local provider 자원 | 선별 **67개 / 13,752,916B**. 위 38개를 포함하므로 별도 67개를 더 확보한 것으로 합산하지 않음 |
| 이번 추가 현재 표본 | `imported/bin/*.bin` **19개 / 535,248B**와 새 CSV **1개 / 185B**, 실제 인증·저장·readback 완료 |

구버전 실제 평문과 현재 catalog의 동일 상대 경로·평문 SHA256·크기를 대조했다. **동일 114,934개, 변경 597개, 현재 추가 16,358개, 구버전에만 16개**다. archive가 바뀌어도 같은 자원 경로로 비교한다. 언팩 트리의 `data_0/` 등은 보관 archive 구분이며, 게임 자원 경로는 그 다음부터다.

## 핵심 바이너리 테이블

| 파일 | 구버전 레코드 | 현재 레코드 | 실제 내용에서 확인한 것 |
|---|---:|---:|---|
| `item.bin` | 1,116 | **1,266** | 아이템 ID, `$설명ID`, 중첩 효과/수치, `meleeDmg`, `rangeDmg` 등의 속성 이름 |
| `npc.bin` | 778 | **951** | NPC ID, 이름/설명 참조, 아이템 ID와 숫자의 목록 |
| `spell.bin` | 361 | **433** | 마법·효과 관련 ID와 `acBonus`, `meleeHit`, `dexBonus` 등 속성/효과 문자열 |
| `quest.bin` | 75 | **75** | ID별 중첩 구조, NPC 대화 문서명·action 문자열, 조건/보상으로 해석할 여지가 있는 수치 |
| `craft.bin` | 150 | **154** | 제작 ID, 재료/결과로 보이는 중첩 아이템 ID·설명 참조 |
| `DescToken.bin` | 1,410 | **1,419** | 숫자 ID에 대응하는 `gender`, `class`, `sprite`, `mana`, `align` 등 설명 token 사전 |
| `copyMapList.bin` | 22 | 26 | ID별 맵 관련 중첩 자료. 정확한 소비 의미는 미확정 |
| `entermaps.bin` | 31 | 29 | 맵·NPC/문서명 문자열과 중첩 자료 |
| `teleportbooks.bin` | 10 | 11 | 이동 관련 묶음과 설명 ID |
| `summonmonster.bin` | 14 | 14 | 소환 관련 ID별 수치 자료 |
| `shipInfo.bin` | 4 | 4 | 선박 관련 ID별 자료 |
| `indun.bin` | 없음 | 1 | 현재 신규 바이너리. 필드의 정확한 의미는 미확정 |

위 수량은 반복된 **map entry 레코드 수**다. `spell.bin`의 433개를 모두 사용 가능한 별개의 마법으로 간주하지 않는다. 모든 구버전 18개·현재 19개 파일은 tag/wire/길이 검사를 통과하고 파일 끝까지 정확히 읽혔다. 대부분 `field 2 반복 → field 1 key / field 2 value-message` 구조다.

그 밖에 `npcCraftList.bin`, `skin.bin`, `battlePass.bin`, `ingame_prob_attendance.bin`, `ingame_prob_attendance2.bin`, `ingame_prob_enchant.bin`, `ingame_prob_treasure.bin`이 있다. 단일 최상위 entry 안에 여러 중첩 자료가 있으므로 entry 1개를 내용 1개로 해석하지 않는다. 강화/보상 관련 파일에는 **성공·파괴, 보통·축복, 아이템·몬스터** 등의 문자열과 수치가 있다. 정확한 확률 단위·계산식·서버 적용 여부는 필드 정의가 필요하다.

현재 19개 중 구버전과 동일한 파일은 6개, 변경된 파일은 12개, 신규 파일은 `indun.bin` 1개다. 현재 평문은 [binary-assets](../work/asset_data_analysis/current/binary-assets/)에 저장했다.

## 확인한 데이터 관계

- 현재 아이템의 이름/설명 `$ID` **1,241개 전부**가 `desc.csv`에 대응한다. NPC 이름 `$ID`도 **906개 전부** 대응한다. 전체 레코드 수와 참조 수는 다르며, 이름 참조 없는 레코드도 있다.
- 현재 NPC의 `value.field21`에 들어 있는 아이템 ID/숫자 쌍 **4,691개 전부**가 `item.bin` key에 대응한다. 오크 예시에는 오크족 고리 갑옷·단검·검·창·투구, 동물가죽, 아데나가 연결된다. **NPC와 아이템의 연관 목록은 확인됐지만 숫자가 수량·확률인지, 표시·드롭 소비인지 아직 확정하지 않았다.**
- 제작 자료의 재료 후보 ID **520개**, 결과 후보 ID **154개**는 모두 아이템 key에 대응한다. 내장 설명과 아이템 기본 설명의 원문 차이 55개 중 접두사를 제외하고 `$ID` 자체가 다른 경우는 7개다. 정확한 제작 의미를 확정하기 전에 변형/별도 명칭 규칙을 확인해야 한다. 결과 속성의 token ID **1,712개 전부**가 `DescToken`에 대응하며 material/weight/warehouseDeposit/maxLev/ac 같은 이름을 확인했다.
- 퀘스트 안의 문자열 666개 중 350개가 기존 NPC 대화 `.uml` 문서명과 정확히 일치한다. 문자열/파일 연결 증거이며 완전한 퀘스트 진행 로직 검증은 아니다.
- 현재 지도 UI 설명 참조 **294개**, 변신 이름/설명 참조 **87개**는 전부 `desc.csv`에 대응한다.
- `spell_list.jsonc`의 ID 있는 행 112개 중 **110개 전부**가 `spell.bin` key에 대응하고 나머지 2개는 `-1` sentinel이다. 둘의 범위와 실제 소비 의미를 동일하다고 단정하지 않는다.

## 텍스트 테이블·설정

| 자료 | 구버전 → 현재 수량 | 내용 |
|---|---|---|
| `desc.csv` | 17,616 → **17,949행** | 아이템·NPC·지역 등의 이름/설명 ID 사전. `ID,EP,KR,TW,JP,EN` |
| `dialogue.csv` | 3,499 → **3,617행** | NPC 이름, update tag, 언어별 대사 |
| `string.csv` | 12,672 → **12,748행** | UI/시스템 문자열 ID, 종류, 언어별 텍스트 |
| `spelldesc.csv` | 230 → **230행** | 마법 설명·추가 설명 |
| `spell_list.jsonc` | 113칸 → 113칸 | **ID 있는 112행(이 중 `-1` 2행) + `@empty` 자리표시 1행**. 클래스/등급, MP·HP, 촉매, 대상, 범위, 아이콘 |
| `item_extra_desc.jsonc` | 66 → 71개 | 아이템 속성 설명의 tag·표시 방식 규칙 |
| `item_usage_display.jsonc` | 165 → 188개 | 아이템 사용 표시/동작 관련 자료 |
| `item_cooldown.jsonc` | 5 → 5개 | 사용 cooldown 표시 규칙 |
| `class_info/class_status.jsonc` | 4 → 4개 | 클래스별 STR·DEX·CON·INT·WIS·CHA 최소·최대 |
| `class_info/char_attr_type.jsonc` | 16 → 16개 | 클래스별 능력치 조합/표시 자료 |
| `region.jsonc` | 192 → **226개** | 지역·영역·좌표 자료 |
| `map_view_data.jsonc` | 상세 지도 30 → **34개** | 월드/상세 지도 이미지, 좌표 변환, 지역·NPC 표시·링크·툴팁 |
| `polymorph_list.xml` | 변신 후보 79 → **87개** | 변신 그룹·레벨·클래스·성별·이름/설명 참조 |
| `server_settings.jsonc` | 39 → 39개 | 서버 ID·이름 문자열 ID·접속 주소·포트·종류. 실제 접속 가능 여부는 조회하지 않음 |
| `ship_data.jsonc` | 4 → 4개 | 배/선착장의 sprite·world·좌표·port 표시/배치 |
| `behavior_list.jsonc` | 21 → 21개 | Loot/SocialAction 등 동작·아이콘·tooltip·delay·sound |

`ats_basic.jsonc`에는 Root/Parallel/Selector/Sequence, FindTarget/MoveToTarget/Interact 등 동작 트리가 있다. 자동 동작·타깃 상호작용 자료로 읽히며, 일반 몬스터 전투 AI 전체로 확정하지 않았다.

`sound_music_config`, `sound_env_config`, `sound_item_config`, `sound_mixing_rules`는 지도·좌표·주야간·아이템 재질·이벤트별 음원 선택, 음량·우선순위·동시 재생·ducking 규칙을 담는다.

NPC 대화 `.uml`은 구버전 **1,131개**, 현재 catalog **1,239개**다. `<dialog>`, `<var>`, `<a>`, `<button action>` 등의 문서이며 상점·퀘스트 관련 action도 있다. 상점 가격/재고나 퀘스트 서버 구현을 이 문서만으로 확정하지 않는다. `list.spr`는 sprite ID·이름, walk/attack/damage/breath 등의 애니메이션 명령이 있는 텍스트다.

신규 `map/20001/npclists.csv`는 Class/Name/Category/Sprite/PositionX/PositionY/Territory/Transform 계열 **header만 있고 데이터 행은 0개**다. 이를 확보된 NPC 스폰 목록으로 보고하지 않는다.

## 그래픽·지도·음향 에셋

현재 수량은 인증 catalog 목록이며, 대표 형식 구조는 구버전 실제 파일에서 조사했다.

| 종류 | 구버전 실제 파일 → 현재 catalog | 확인한 내용 |
|---|---|---|
| sprite/HD sprite `.spx` | **96,544 → 111,910개** | 숫자 ID·변형 기반 이름, 일반/HD 경로. 바이너리 디코딩·방향·애니메이션 state 매핑은 미완료 |
| 지형 `.til` | **4,907 → 4,913개** | 지형 경로의 바이너리와 text list가 공존. 타일 schema는 미확정 |
| 지도 조각 `.s32` | **2,659 → 2,953개** | 숫자 map 폴더·hex 형태 조각 이름. 충돌·좌표·출구 규칙은 아직 해석하지 않음 |
| 지도 `.seg` | 1 → 1개 | 별도 지도 바이너리 |
| UI 레이아웃 `.csb` | **415 → 418개** | 표본의 FlatBuffer-compatible root/vtable 구조. 로그인·캐릭터 생성·인벤토리·상점·창고·파티·혈맹 등 UI |
| PNG | 96 → 101개 | cursor, icon, atlas texture, UI 이미지. 구버전 전수 PNG signature 확인 |
| atlas `.plist` | 29 → 33개 | frame rectangle·offset·rotated·sourceSize와 texture 참조. 캐릭터 atlas 표본 100frames |
| Ogg | **9,642 → 9,958개** | 구버전 전수 Ogg signature, 대표 Vorbis mono 22,050Hz |
| MP3 | 56 → 58개 | music 경로 음원. 전 파일 재생/codec 검증은 하지 않음 |
| WAV | 없음 → 235개 | 현재 catalog 신규/추가 음원 종류. 전체 payload 디코딩은 하지 않음 |
| 폰트 TTF | 2 → 2개 | ElaraFont, NotoSansMonoCJKkr-VF. 실제 sfnt table·variable-font tag 확인 |

sprite 파일 수는 캐릭터/몬스터 종류 수가 아니고, map 조각 수는 맵 종류 수가 아니다. `.spx`를 확장자만 보고 Speex 음원으로 분류하지 않았다.

## 남은 해석과 활용

싱글 게임 구현에 앞서 기존 **아이템·NPC·효과·퀘스트·제작 데이터와 ID 사전부터 재사용할 수 있는 구조**를 확인했다. 후속 분석은 protobuf field 정의를 소비 코드/descriptor로 연결하고, NPC↔아이템 목록의 숫자 의미와 제작 설명 차이, sprite/animation 연결, 지도 타일·충돌 구조를 좁히는 순서가 적절하다.

현재 전체 팩 추출, 전체 그래픽 렌더, 게임 진입, 서버의 실제 전투·드롭·퀘스트 동작은 이번 데이터 조사에서 검증한 항목이 아니다. 정확한 경험치/성장·전투 계산식이나 HP/드롭률 필드도 이번 결과만으로 확정하지 않는다.

## 근거 파일

Root의 독립 **310개 확인 항목이 전부 PASS**다. 산출물 집계와 실제 source 표본 SHA, 현재 cache38 전체 SHA, 현재19bin SHA·양 버전 wire 레코드 수, token index와 신규 CSV를 교차검증했다. 테이블 JSON18개도 정상 파싱됐다.

- [전체 파일 inventory 및 형식 표본](../work/asset_data_analysis/inventory/findings.md), [파일 목록 TSV](../work/asset_data_analysis/inventory/files.tsv)
- [현재 catalog 및 버전 차이](../work/asset_data_analysis/current/findings.md), [전체 catalog TSV](../work/asset_data_analysis/current/catalog.tsv), [구버전 실제 SHA 목록](../work/asset_data_analysis/current/old_actual_plaintext.tsv)
- [텍스트 테이블 구조](../work/asset_data_analysis/tables/findings.md), [현재 텍스트 schema](../work/asset_data_analysis/tables/current-tables.json)
- [현재 바이너리 구조·관계](../work/asset_data_analysis/tables/current-binary-findings.md), [현재 바이너리 field 구조](../work/asset_data_analysis/tables/current-binary-probes.json), [현재 ID 관계](../work/asset_data_analysis/tables/current-binary-relations.json)
- [현재 설명 token ID 사전](../work/asset_data_analysis/tables/current-description-token-index.json)
- [현재 바이너리 19개 인증 근거](../work/asset_data_analysis/current/binary-read-proof.json), [새 CSV 인증 근거](../work/asset_data_analysis/current/extra-read-proof.json)
- [Root 독립 교차검증](../work/asset_data_analysis/root-review.json)

분석 코드는 `tools/asset_data_analysis/`에 있다. 이전 원본·보관·팩·게임·SDK는 수정하지 않았으며, 자원 master-key 파일·계정 자료를 읽거나 관리자/UAC·게임 실행·네트워크 작업을 수행하지 않았다. 새 파일은 분석 코드·보고서·선별 인증 평문이다.
