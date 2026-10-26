# COMPANION-MAGE account legacy input close ordering v2

WRITER_RELEASED / source_ready:true / test_ready:true / run_ready:true / runtime UNRUN. actual82 실패는 그대로 보존하며 아직 해결 성공을 주장하지 않는다. 부모 v1 caller의 정상 client FIN 뒤 **그 실제 accepted WORLD row.task 종료를 한 번 bounded shield-await**하고, 실제 EOF/join/failed=false를 확인한 다음 기존 explicit server.close를 호출하는 한 hunk만 추가했다. sleep/retry/상태수정·handler호출은 없다. 원 product184/Scope/Core/Store/Peer/Server 및 원strictclose 판정은 그대로다.

## 비교와 첫 접점

actual82 result48f015c82b7a6272ffc7108ac2cf31f04b36d58ed68042c6eb46290b98799441은 첫 MAGE WORLD/RESOURCE/0964·양legacybytes와v5 memberguard까지 관측했다. beforeclose failureNone/completedWORLD_DRAINED였고 afterclose connection3 completedERROR/BATCH_CURRENT_CONNECTION_ROW/cleanfalse다. ROOT/fresh0·partialcanonical5와8파일을 보존한다. 첫서버오류에는 code/message만 있고 callee stack이 없으므로 동적정확callsite를 관측한 것으로 쓰지 않는다.

accepted actual55와 product184 selection, client33155, Scopebf419, 원close/finalfault block이 동일하다. actual55도 beforeclose connection3 eofFalse/joinedFalse였고 afterclose eofFalse/joinedTrue/WORLD_DRAINED로 마감했다. 그 PASS가 새입력의 타이밍을 보장하지 않는다. 입력 차이는 child equipment159B 추가, root/child characters.json과childinventory 세SHA 변경이다. rootinventoryd9f9와 나머지 원파일은 같다. legacy159B가 실패원인이라는 근거는 없다.

확인한 source 노출은 Broker.close_without_server_menu가 _closing=True를 설정한 뒤 _close_resources의 sleep(0)을 거쳐 _serve task를 cancel하는 순서다. 이미 READ_WAIT 중인 _serve가 client FIN으로 먼저 깨어나면 원 _row_operation→BrokerProvider.connection_operation→_connection(nonterminal)의 `not broker._closing` guard에 도달할 수 있다. guard는 같은행/원claims/failed/eof/joined도 검사한다. 이 생존조건을 없애거나 terminal=True로 전환하지 않았다. 새caller는 원client FIN과 원server task 종료를 명시적으로 연결하여 이 경쟁을 시작하기 전에 자연EOF를 서버가 처리하도록 한다. 서버가 실패·타임아웃하면 그대로 실패다.

main이 제시한 complete_request→poll runtime 가설도 실제 SKU에서 확인했다. selected Peer는 _packet_runtime=None으로 시작하고 poll_packet_session은 hookNone이면 즉시 return한다. RESOURCE-only actual82 caller는 register_packet_runtime을 호출하지 않으며 optional NPC input/runtime도 설치하지 않는다. 따라서 해당hook이 Batchcurrent를 실행했다는 근거가 없다. complete_request를 poll 뒤로 옮기는 공통Broker patch는 이 실패근거로 정당화하지 않았다. 공통/제품source 변경0이다. 새진짜serverstack이 다른접점을 보이면 해당owner가 source수정 범위를 정해야 한다.

## 실제 waiter와 판정

PacketFlowClient.close의 CLIENT_SOCKET_CLOSED는 client transport 종료 관측이며 server EOF/join을 뜻하지 않는다. v2는 client.world_entry가 있는 실WORLD owner에만, client.row가 같은broker claims의실행이며 connection_id가 일치하는지 확인한 뒤 원 row['task']를 기다린다. 이 Task는 원Broker._accept가 _serve로 생성·보관하고 _joined done_callback을 등록한 바로 그 객체다. asyncio.wait_for(asyncio.shield(task), timeout=client.timeout)로 시간 한계만 두며 timeout에 서버task를 cancel하지 않는다. 실제 Task exception은 원문대로 기록한다. 원row eofTrue/joinedTrue/failedFalse 및 broker closingFalse를 확인해야 world_eof_join 양성이 된다. callback/close/handler를 직접 호출하거나 joined/eof를 대입하지 않는다.

waiter 실패는 WORLD_EOF_JOIN cleanup원문/stack으로 남고 부모의 firsterror 보존/strict serverfault 판정을 통과할 수 없다. explicitserverclose는 실패시에도 원자원정리를 수행한다. 기존 firsterror가 있으면 덮지 않으며 다음owner/fresh를 중단한다. client closed/server joined를 정상Quit/Native UI 성공으로 확대하지 않는다.

## Test 실행

원actual75 class3+same-profile equipment 결과f675의 **보존된 original whole8 source**에서 Test가 새로운 전체사본을 준비한다. input-source/scenario/cohort/loader/dependencies/RUN_COMMAND는 v1과byte동일이다. failed82 partialcopy를 재실행·recopy/rollback/reset하지 않는다. Test만12000/14030·FIRST/result/부분Store/close를 소유한다.

```powershell
& "C:\Users\Chansol\Documents\ChatGPT\싱글리니지\work\local_original_session\implementation-companion\companion-account-mage-equipment-close-v2\RUN_COMMAND.ps1" -AccountCopy "<NEW_ORIGINAL75_WHOLE8_COPY_ABSOLUTE>" -AccountResult "<RESULT_ABSOLUTE>"
```

MAGE→ROOT→MAGE_FRESH의 기존 정상protocol/current/Store·legacybytes/memberguards·원7파일preservation은 그대로다. 이SKU는 Resource-only이며 장비restore/FullGear·동료소환/AI/UI는 시험하지 않는다. actual75 topbusiness_passfalse도 원근거 그대로다.

## 확인과 소유

verify_close.py 15 focused checks PASS: 한insert외caller전체byte동일, clientclose→실taskwait→serverclose 순서, strictfinalfaultblockbyte동일, exactmetadata/sourceparent, 실제82/55 근거핀. asyncio원Task의정상반환/원exception관측 및 shieldtimeout이 소유Task를 cancel하지 않음만 따로 확인했다. 이는 primitive seam이며 실제serverclose성공이 아니다. 새게임/서버/포트/사본/제품import/원저장·ITEM·공용·Test·부모·큐 변경0이다. sourcepins/evidence/caller.diff에 정확접점과한계를 보존했다.
