# REA272 — 발급 UID/LOCAL generation와 native 수명 계약 검토

**원본의 생성·게시·조회·제거와 callback 프레임의 메모리 수명은 연결했다. LOCAL generation을 현재 동일 native Player/Interaction에 결속하는 producer/소비 receipt와 이미 진입한 invoke의 퇴역 완료는 미공급이다.** 따라서 안전한 외부 per-instance 등록·해제 계약이 완성됐다고 판정하지 않는다. 전체 구현 불가능이나 원 protocol 전체의 generation 부재를 주장하는 결과도 아니다.

main은 세 Sol6.1/high worker의 결과와 핵심 실제 원문을 단1 비작성 검토했다. 원4B690의4B8C5..4B8E7이 현재 ActorSubsystem을 얻어60B50에 같은SpawnInfo를 전달하는 행, 60B50의 UID 비교→기존 첫 일치61650→45550 생성→60C17/66C80 게시를 확인했다. Player C24A0·초기화는271을 재사용했다. 627B0 원문은 +8A8/+8C0/+8D8에서 첫 UID 일치 Pair를 retain한다. 이는 객체 메모리 수명을 확보하는 조회이며 조회 이후 invoke까지 현재등록/LOCAL generation이 보장됐다는 뜻은 아니다.

원4E40 typed binding은 **SC_REMOVE_OBJECT_NOTI, 필수 f1 uint64 UID**다. 4E700→61650은 현재 subsystem에서 첫 UID 일치를 제거한다. 같은UID 새 게시와 old Pair 잔존은 구분하며 전체 vector/모든 중복의 부재로 확대하지 않는다. 원61F37..61F47의 component.virtual20 loop와 Interaction slot20=40C50을 결속했다. 새5B/2행은 byte[I+30]=0;RET다. **I30의 업무 의미는 미확정이며 이 leaf는 I70를 clear하지 않는다.** 별도 B6BA0 최종파괴의 old callable.virtual20→I70=0은271을 재사용했다. 제거의 다른 event·관계 callee가 무효과라는 주장도 하지 않는다.

원 A0D60의 target lookup/Interaction/ownActor Pair 보유→A0E1C B6D20 호출→정상 반환 뒤 own/Interaction/target release를 직접 확인했다. B6D20은 raw I70 callable을 읽어 virtual10을 호출하며, B9990의 codepointer tailcall은 정상 B6D4D로 복귀한다. Pair는 Actor/Interaction을 map 제거 뒤에도 살려 둘 수 있다. raw callable의 별도 retain·ownerthread 직렬화·이미 진입한 invoke의 drain은 선정 source가 공급하지 않는다. I70 clear나 제거 반환을 callback 반환 완료로 취급하지 않는다.

LOCAL source는 private v1→releasedv2의 정확9파일 회수다. 두 manifest는 SOURCE_ONLY/UNRUN/test_ready:false이고 공용 current cohort는 미공급이다. main은 v2 allied_player_publication.py의 원288..305 및391..399를 확인했다. 발급 UID/f16True의 Player DTO를4E96으로 encode하고 **299/300행에서 wire를 만든 뒤301행에서 generation=object()를 생성**한다. 이 선택 emitter의 그 토큰은 이미 만든 wire에 실리지 않는다. record의 generation/selection/row/lease는 서버 current proof다. ActorSnapshot pose=None과 snapshot()의 명시적 None 반환은 native 관측이 아니다. 서버 DRAINED·4E40 tombstone/absent=False도 native 생성·제거 소비나 invoke 완료 receipt가 아니다.

구현 main에 넘길 최소 결속 조건은 다음과 같다. 현재 source가 이 조건을 구현했다는 의미는 아니다.

1. 원 생성·초기화·게시 이후의 실제 Player/Interaction object/control과 현재 registry를 발급 UID/LOCAL generation/owner의 같은 record에 연결해야 한다. UID 또는 주소 일치만으로 old/new 객체를 치환하지 않는다. 이 publication binding/소비 receipt가 첫 결손이다.
2. 해당 원 실행 frame에서 callback 선택·교체와 raw callable 진입을 어떻게 직렬화하는지, code/receiver 수명이 정상 반환까지 어떻게 유지되는지 확인해야 한다. 원 B93D0 기계 ABI와 Pair retain만으로 이 결속을 대체하지 않는다. 일반 Player의 I88/fallback 제약은271 그대로이며 I70 교체만으로 설정 callback 도달을 보장하지 않는다.
3. 퇴역도 같은 record/객체에 귀속하고 registry 제거·남은 Pair·이미 시작한 invoke 완료·개별 callback 정리를 구분해야 한다. 현재 source에는 이 native retirement/drain receipt가 없다. 서버 drain을 그 완료로 대신하지 않는다.

위 조건은 신규 binder/hook/관측기·대형 시험체계의 설계나 추가 승인 gate가 아니다. 현재 확정한 원 순서와 결손을 전달하는 범위이며 기능 main의 독립 서버/정책·정상 패킷 시나리오는 계속할 수 있다. runtime/port/globalhook/geometry/ATS UI·제품/공용/ACTIVE 변경0이다. 새 source 읽기는 CODE물리17B/고유16B/중복1B·decode5B2행·PData192B16cell뿐이다. invoke 원194행과 기존 결과를 재사용했고 새 DATA/xref/provider/실행0이다.

최종 root3/registry3/invoke3/local-generation1의10핀·JSON을 확인했다. main은 RELEASED 뒤 과거 companionHELD 상태 문구만 현재 동료기능ACTIVE/별도Pro·브라우저 보류로 정정했다. source 사실·하위 파일은 바꾸지 않았다. 전원 reader/writer RELEASED다.

| 최종 결합 파일 | bytes | SHA256 |
|---|---:|---|
| source/contract.md | 4388 | 579dcd205eaecadf2b9034c0aebc5eedbf62656c6e4909bfc5a8f3ad06e1c87d |
| source/source-refs.json | 5296 | 77c3f4bfc5221135477637bbcfc07c272c5ffa79450a797abc460830b15eaff2 |
| source/selected-evidence.json | 4729 | 7c1b94b4981a1342679e4a9367c232913fea509961b35ce383d71f8742bd3fff |

정확 원문 locator와 하위 완료 핀은 refs/selected에 있다. 기존 REA ledger/HANDOFF에 보존하고 관련 질문자에게 계약 답1회만 전달한다. Root/Test 일반 알림·ACK·통합 큐·실행 발주·test_ready 주장0이다.
