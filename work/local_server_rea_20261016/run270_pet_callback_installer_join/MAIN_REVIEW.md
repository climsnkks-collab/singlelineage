# REA270 — 원 Pet/Summoned 클릭의 실제 요청 확인

**Pet/Summoned 정상 생성→실제 Interaction 콜백→4F13 `LIN::CS_SUMMON_STAT_REQ` 송신 호출을 연결했다. 요청은 필수 f1 uint32 한 개로 대상 actor UID의 low32를 담는다. 별도 동작번호·좌표 필드는 없다.** 원 코드의 조건부 송신 경로이며 현재 실행·서버 응답·메뉴 표시 성공은 미확인이다.

main은 세 Sol6.1/high worker의 결과와 실제 핵심 원문을 단1 비작성 검토했다. 원45550의 Info78 비0 분기·Pet48A40/C2350 및 Summoned48940 생성·공통46393..46399의 sameActor/sameInfo→41DB0를 확인했다. 새 ctor의 실제 타입 vptr·공통40ED0 Interaction11815A8/+8=sameActor 등록과 초기80=1도 검토했다. 기성 B6C10 전체265B의 같은Info78 비0→Interaction80=20 override→B8980/B8C60를 읽어 초기값과 최종 선택을 구별했다. Pet/Summoned 두 분기는 이 source 조건으로 결속되며 원본의 모든 Minion/새 동료 Player 타입에 자동 확대하지 않는다.

B8C60 후속 switch는 CODE와 점프표 DATA를 분리했다. case20의42EC0 결과/+98 조건을 통과한 설치 경로가 B8710이다. B93D0 완전375B의 F=Interaction+38, active F+38=Interaction+70과 실제 B99A0 clone6행·B9990 invoke를 검토했다. wrapper+8은 함수 포인터이며 actor/UID capture가 아니다. B6D20이 현재 Interaction+8 actor를 넘기는 원 계약은267을 재사용했다. 로컬 Interaction7C=3을 패킷 동작값으로 전용하지 않는다.

새 B8710 원행의 current객체·target42EC0 결과·문자열 길이/내용 비교와 B8815..B883E의 target actor.slot8 EAX→request raw18을 확인했다. B8870 EDX4F13/B8879 CALL27D620이 실제 송신 호출이다. B92C0의 optional MinionSubsystem Pair는 원 hold/release이며 새 nonnull gate를 추가하지 않는다. 문자열 비교를 서버 ownerUID 검사로 이름 붙이거나 UID/currentgeneration 권위를 발급하지 않는다. guard 실패 skip과 송신 분기는 구별한다.

원 RTTI raw1741C38의 이름을 직접 읽어 CS_SUMMON_STAT_REQ를 확인했고, schema accessor76FAF0→15EC5D0과76FC50의 byte10&1 필수mask를 검토했다. maximum/count1·raw18 f1의 card0891은 기존 world-notify tables1/fields1과 run22 selected_fields1의 동일uint32 계약을 직접 대조했다. 필드 타입만 재사용했으며 다른 필드의 의미를 빌리지 않았다. 이 요청에는 별도 행동·수량·좌표 필드가 없다.

**첫 미공급은 이4F13과 명시적으로 연결된 S2C 응답·메뉴 consumer·정상 다음 요청이다.** 기존6캐시의 opcode 및 SUMMON_STAT 이름 회수는 그 상관을 공급하지 않았다. 4F14 인접번호·별도4EF3 SC_REQUEST_SUMMON_NOTI·guard skip을 응답/무응답으로 대입하지 않는다. 기능 main이 정상 세션·실UID/current·소유권과 실행 가능한 시나리오/caller/RUN_COMMAND를 결속하며, REA는 test_ready·실행 발주를 대신하지 않는다.

선정 source 결속만 주장하며 legacyCONTROL/frozen104/c822 전체 image·현재 runtime 동일성을 확정하지 않는다. installer 고유CODE1138B/337행·PData420B·DATA984B, actor 고유CODE1275B/352행·PData1500B·DATA120B이며 actor querycontext43B/10행은 overlap으로 분리했다. installer의 첫 실패 read204B/복구중복과 partial decode UNKNOWN은 refs에 보존했다. 새 provider/target open·runtime/RPM/UI/socket/game/build/test·제품/공용/ACTIVE/포트/저장·geometry/Camera0이다. 최종 root3·installer3·actor3·reply1의 10핀/JSON을 확인했다. 전원 reader/writer RELEASED.

| 최종 결합 파일 | bytes | SHA256 |
|---|---:|---|
| source/contract.md | 4553 | 714ace46da3c7b5eb8f8b38911cfff76034231d3b9a26774a153fe4b39156db1 |
| source/source-refs.json | 9182 | 12055146ba86aed66dc1d5d0047b461897bffd70b4c4480b32d9b559a1df28af |
| source/selected-evidence.json | 26388 | 6b366724c61a9767e3d3bf0d8bc61e36c25456bdc3b10bce9febdeeb3d3165c7 |

정확 하위 파일 핀·원 instruction pointer는 최종 refs/selected에 있다. 기존 ledger/HANDOFF에 기록하고 companion 질문자에게 계약 답 한 번만 전달한다. Root/Test 일반 알림·ACK·통합 큐 등록·시험 발주0이다. 동료 기능 활성과 별도 Pro/브라우저 자동화 보류를 구별한다.
