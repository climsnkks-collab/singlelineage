# REA271 — 개별 allied Player 클릭 등록 source 검토

**원본의 개별 Interaction 콜백 교체·clear·파괴 접점은 있다. 특정 발급 alliedUID/LOCALgeneration을 현재 동일 nativePlayer에 결속해 설정 콜백을 등록·퇴역시키는 producer는 미공급이다.** Player 특수 클릭은 사용자 상점 경로이며 Pet/Summoned 요청이나 동료 설정 경로로 자동 승계하지 않는다.

main은 두 Sol6.1/high worker의 계약과 핵심 원문을 단1 비작성 검토했다. 원 C24A0의 40ED0 호출·Player11819B8 설치·초기Player38=0 및 copiedproto11C→Player38 load/store를 확인했다. 원 world-notify descriptor의 optional field65/raw11C/card1091과 대조했다. 값을 class·동료 표시·권한으로 명명하지 않는다. 실제 C2490의3B는 movAL1/RET이다. Info78==0인 정상 Player 초기화는 기성 B6C10의 selector5로 이어지고, Player38!=2이면 기성 B8C60이 I88false/새설치 없음으로 간다. 원 AB790은 false88에서 별도 fallback을 선택하므로 **I70 포인터만 바꿔도 설정 콜백에 도달한다고 보장할 수 없다.** 이전 active가 이 분기만으로 clear된다는 주장도 하지 않는다.

Player38==2 특수분기의 B7850 전체971B를 선정했고 main은 입력actor→RSI·sameActor.slot8 fullUID→3DCD0 반환state+2C0·17B 문자열 생성→B8EB0/5CC3A0의 핵심 실제 행을 검토했다. raw17B는 정확히 `data/uml/usershop`이다. 기존 5CC3A0 원 소비행의 resource/flag/out 인수도 대조했다. 이는 원 current/map/state guard 아래 usershop resource로 전달하는 경로이며 ATS·동료 설정·화면 표시 성공이 아니다. 직접send가 보이지 않는다고 packetless로 판정하거나 후속UML/통신 그래프를 추가하지 않는다. f65=2나 Pet selector20을 강제하지 않는다.

개별 등록 기계 ABI는 기성 B93D0(RCX=F=Interaction+38,RDX=&codepointer,RAX=F)이며 F+38은 I70이다. wrapper는 codepointer만 보관하고 UID/generation을 capture하지 않는다. clone/exchange/old.virtual20 정리와 empty/clear는270 검토를 재사용했다. 새 B6BA0 전체110B/30행은 nonnull active.virtual20→I70=0→base/string 정리→deletingflag에 따른0x90B free/RET를 실제 확인했다. destructor를 외부 unregister 대용으로 호출하도록 제안하지 않는다. 원 초기화가 다시 실행돼 callback을 재선정할 수 있음도 보존한다. B8980의 선정 직접84 설정을 전이적 무효과로 확대하지 않는다.

첫 미공급은 **서버발급 alliedUID/LOCALgeneration→같은 current nativePlayer/Interaction 및 원 owner/thread·현재callback 교체·퇴역·이미 진입한 invoke 정리 구간을 연결하는 producer/record**다. per-instance 보관공간이나 동일 UID/주소·rawActor 재조회만으로 이 결속을 대신하지 않는다. 이는 전체 구현 불가능 판정이나 다른 서버 구현을 막는 승인 gate가 아니다. Pet 변환·전역 훅·좌표/Camera·ATS 창 생성은 수행하지 않았다.

Player 새CODE974B/279행·PData156B·DATA17B, lifetime 새CODE110B/30행·PData180B다. 새 provider/target open·runtime/RPM/UI/socket/game/build/test·제품/공용/ACTIVE/포트/저장0이며 원자료의 선정 접점만 결속하고 전체image/currentruntime 동일성을 주장하지 않는다. 최종 root3/player3/lifetime3의9핀·JSON을 확인했고 전원 reader/writer RELEASED다. 실행 가능한 시나리오/caller/RUN_COMMAND는 기능main 소유이며 이번 분석은 test_ready/실행 발주가 아니다.

| 최종 결합 파일 | bytes | SHA256 |
|---|---:|---|
| source/contract.md | 4269 | 343437ee9777b3bbe486cf9fb32967596082dbc372fa2770ad984d71c3a83256 |
| source/source-refs.json | 5397 | 191b81ec68c7b21d036efff11b36a5120af5aa94fdcd574854429a0242de8d35 |
| source/selected-evidence.json | 12407 | 6f66adf9e847a91dcb7564fb0ba7e7ae3b68e8a8d5a83129e62e4dda7584e4b6 |

정확 원문 locator와 하위 완료 핀은 refs/selected에 있다. 기존 REA ledger/HANDOFF에 보존하고 관련 companion 질문자에게 계약 답1회만 전달한다. Root/Test 일반 알림·ACK·통합 큐 등록·시험 발주0이다.
