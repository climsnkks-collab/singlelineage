# REA273 — MAP-TRANSITION 정상 요청·월드 재수립 계약

- 목표: teleport NPC 선택→dialog/menu→목적지 선택→확정의 실제 C2S와 S2C 맵 전환 뒤 world/current 재수립을 확인한다.
- 재사용: run122 HACTION4ED4/action-cookie·4E95 MapNotify receive schema/72A690 및 map_hook49–59를 재사용하고 특정 NPC/목적지 미공급을 추정으로 채우지 않는다.
- 소유: dialog worker는 source/dialog/와 최종 source3파일, receive worker는 source/receive/, catalog worker는 source/destination.json, main은 MAIN/기존 ledger/HANDOFF·공식 큐 helper enqueue만 쓴다.
- 경계: 03EB USER_START_DONE은 mapACK로 쓰지 않고 island-gludin4/32612/32732는 미선정, PositionStore same-mapguard 유지·제품/공용/Test/실행/포트/저장/geometry/Pro자동화0이다.
- 마감: 확인/첫 미공급과 정상 단계별 계약을 별도 REA source에 보존하고 NPC main 직접 완료 답1회+공식 같은 큐에 test_ready:false로 등록한다. Root 진행·ACK·시험 발주0이다.
