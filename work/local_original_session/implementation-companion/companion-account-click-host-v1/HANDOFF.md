# COMPANION-MAGE account click Host/Feature v1

WRITER_RELEASED / source_ready:true (bounded source component) / run_ready:false / test_ready:false / runtime:UNRUN.

## 정확 변경

- Host 부모 `companion-account-fresh-host-v1/companion_host.py` SHA `15d378ba09a3ede059b8692928df1e5c58a123c928d7e3979eaf73b89e30d0ab` → 새 Host SHA `5c56104199997441567e7078b8e3f9fc9f8f2e22fd18d39fffc737d489d02731` (36010 bytes). 공개 `open_from_actor_click`에서 원 row operation을 한 번 획득하고 새 synchronous `_open_from_actor_click_locked`에 위임한다. 두 메서드는 검토된 locked-v2 Host ed866의 해당 AST와 정확히 같다.
- Feature 부모 `companion-click-router-v2/companion_actor_click.py` SHA `7aa733dfbdd2052bc543dfcbe2590bcb275a19c5854a255c025d8402c705728c` → 이 폴더 새 typed Feature. HOST/PUBLICATION의 exact seals를 새 Host5c56/계정 Alliedd149로 선정하고, 계정 click Broker3c7b에 exact SourceSeal을 추가했다. 실제 PersistentBroker/LocalRealm/_TransportPolicy nominal class 및 동일 Host.broker와 nonclosed Host를 설치/요청 때 확인한다.
- 원 Feature strict f1 nonzero uint32 parser, header/dispatch 메서드는 부모 AST와 같다. LOCAL의 field/size/extra/duplicate 거부와 `return ()` 무선응답 의미를 유지한다. 4F14/응답 child/성공코드/Native Player 송신·ATS interface/panel/소환을 생성하지 않았다.

정확 부모·참조·ITEM 제약 pin은 parents.json, 실제 변경은 companion_host.py.diff와 companion_actor_click.py.diff다. Broker/Factory/Allied/Scope/actor-config/공용/ITEM/Test copy/원계정/queue는 수정하지 않았다.

## 계정 수명과 잠금 보존

Host의 변경을 되돌리면 전체 module AST가 부모와 같다. 새 callback-pair producer/CONSTRUCTING/ATTACHING/원 Scope/current/Shared/default/close/retirement 코드는 모두 그대로다. 기존 `_open_panel_locked`/shortcut/command/epoch stale callback도 그대로다. helper는 재획득·await·yield 없이 같은 supplied row와 실제 participant의 writer/actor UID/generation/별도 lease를 확인한 뒤 이 원 panel 함수를 호출한다. interface None이면 원 `COMPANION_ISOLATED_ATS_WINDOW_CONTRACT_UNAVAILABLE`를 유지한다.

Feature는 동일 typed AlliedPlayerPort/RootPlayers/PlayerRegistration, 원 `root.current(record)`를 그대로 소비한다. 계정 Allied의 원 operation은 실제 selected binding/provider current·canonical task·같은 row lock·root namespace·실제 lease/current RESOURCE를 검증한다. 그 다음 원 Feature의 DRAINED/no removal/owner writer/selection/row/lease/UID/generation 검사를 모두 유지한다. dispatch는 이 검증과 Host helper 사이에 await하지 않는다. packet 값에서 generation·record·owner를 발급하지 않는다.

## 구체적인 미완료 계약

1. **실제 interface가 없다.** Feature 생성은 원래와 같이 실제 unstarted Host에 non-None interface와 실제 Allied port가 이미 있어야 한다. 가짜 interface나 UI는 제공하지 않았다. source pin이 맞아도 설치 성공을 의미하지 않는다.
2. **계정 전이의 Feature successor 계약이 없다.** 원 account Scope._construct_graph(825/849/850/858)은 genuine CONSTRUCTING에서 fresh configuration을 만들고 ATTACHING에서 새 Host를 붙인다. 기존 Feature는 시작 전 Host 하나를 보유하며 설치 조건은 not-started, no sessions, 두 Feature slot None이다. cold Feature를 설치했다면 원 초기 선택/후속 계정 전이는 old Host를 닫아 새 Host로 바꾸므로 현재 Feature는 `COMPANION_CLICK_SAME_NATIVE_HOST_ROW_REQUIRED`로 거부한다. 새 Host에는 이 조건으로 Feature를 재설치할 수 없다. 원 Host.closed는 Feature 슬롯을 퇴역/대체하지 않으며 이번 허용 범위는 그 retirement 코드를 보존한다.

따라서 이 결과는 **잠금 내부 클릭 helper와 정확 typed callee source 준비**다. 계정 선택 뒤 작동하는 Feature 설치/소환/메뉴의 완성품이 아니다. 다음 product attempt에는 원 token이 소유하는 새 Feature 수명·정상 route 교체/퇴역 계약이 필요하다. old Feature.host를 바꾸거나 슬롯을 지우거나 가짜 token으로 기존 single install/세션 guard를 우회하지 않는다. exact blocker/source line은 blockers.json이다.

## 후속 선정 제약

기존 fresh actor-config f8b2는 아직 Host15d/Broker934/Allied4d를 고정한다. 새 coherent 후손은 Host5c56/Broker3c7b/Alliedd149와 별도 검토된 actor-only Factoryc79를 **명시적으로** 결속해야 한다. 이번 task는 그 파일들을 수정하지 않는다. 이 폴더 cohort는 cold import만 위한 185행 selection이고 runnable 설치로 쓰지 않는다.

수용된 ITEM target-view source4d2844/manifest ea7e50은 Host219/Core86을 고정한다. 새 Host5c56을 자동 대체하거나 interface가 설치됐다고 주장하지 않는다. ITEM port의 최종 typed interface SourceModule/실제 panel·lease·actor binding과 equipment state는 후속 검토 대상이며 native_opened/action_admitted:false 경계도 유지한다.

## 최소 확인과 실행 경계

```powershell
python -B work/local_original_session/implementation-companion/companion-account-click-host-v1/verify_source.py
```

45개 bounded assertion PASS: 부모 pin 12개, Host 전체 보존/검토 reference exact AST/동기 helper, Feature 실제 변경 2메서드·원 parser/header/dispatch·전체 current predicates/원 root.current 호출, exact diffs·compile, 실제185행/183 module cold import·모든 pin과 nominal Feature·4 source seals, Broker/Peer/Server 원 sibling filename, 원 decoder의 uint32 경계5개와 거부 shape9개. Runtime object/Host/Plan/Root/owner/lease/Store/Feature 생성·설치, fake registration, 실제 Scope transition, 서버/소켓/포트/패킷 송수신/저장·소환·REA는 실행하지 않았다. SourceSeal 객체는 실제 cold modules에만 생성했다. 기존 runtime tests/전체 Host fixture는 같은 source AST이므로 반복하지 않았다.

verification.json은 clock/실행시각 없이 결정적 결과다. 두 번 연속 실행 시 같은 bytes/hash인 것을 확인했다. manifest.json은 제품·부모·diff·cold evidence·blocker/HANDOFF pin을 기록한다.

실행 caller/RUN_COMMAND는 아직 제공할 수 없으므로 runtime_command:null/test_ready:false다. 다음 실제 시험의 순서는 공용 packet-test-client-v5로 정상 login/roster/root UID1 WORLD/current → source-backed 실제 summon/발급 UID·generation·등록 drain → 명시 LOCAL 4F13 f1 실제 UID → 같은 원 panel → 원 Store/strict close다. 앞의 실제 interface/summon/Feature 전이 계약이 미공급이므로 최종 클릭을 선송하지 않는다. Native Player callback/UI/4F14 응답 업무 결속은 UNKNOWN이다. 이번 마감은 source-only이며 main이 실제 delta/핀을 검토해 후속 범위를 정한다.
