# Exact readonly source excerpts for actual265

## BROKER_SAMPLE_AND_EXISTING_REFRESH
Source: C:\Users\Chansol\Documents\ChatGPT\싱글리니지\work\local_original_session\implementation-companion\local-packet-settings-core6041-world-v4\broker.py
SHA256: 6e703872e79a8b15e9ef9c92442521d93b6ff5c30091c0dd11068bc6f6976a2f

```text
2415:     async def _sample(self, row, *, synchronous_exact=False):
2416:         need(type(synchronous_exact) is bool, 'OWNER_SAMPLE_MODE_REQUIRED')
2417:         if self._packet_peer_mode is not None:
2418:             self.source_guard()
2419:             return self._packet_peer_mode.sample(row, Peer)
2420:         if synchronous_exact:
2421:             # The actual launcher binds NativeOwner.guard, an async wrapper whose
2422:             # whole body calls this same synchronous guard. After an expensive
2423:             # source validation, obtain a NEW exact tuple/handle/Job result with
2424:             # no event-loop yield between that result and policy consumption.
2425:             from tools.local_original_session.launcher import NativeOwner
2426:             owner, guard = self.policy.owner, self.owner_guard
2427:             direct = getattr(owner, 'guard_exact_sync', None)
2428:             need(type(owner) is NativeOwner and getattr(guard, '__self__', None) is owner
2429:                  and getattr(guard, '__func__', None) is NativeOwner.guard
2430:                  and getattr(direct, '__self__', None) is owner
2431:                  and getattr(direct, '__func__', None) is NativeOwner.guard_exact_sync
2432:                  and self.policy.handle is owner.owner_handle
2433:                  and self.policy.job is owner.owner_job
2434:                  and row['operation_lock'].locked(),
2435:                  'OWNER_EXACT_SYNC_SOURCE_REQUIRED')
2436:             result = direct(dict(row['peer']))
2437:         else:
2438:             result = self.owner_guard(dict(row['peer']))
2439:         if inspect.isawaitable(result):
2440:             result = await asyncio.wait_for(result, 1.5)
2441:         if result is not True:
2442:             self._owner_failure(row, 'CALLBACK_FALSE' if result is False else 'CALLBACK_UNKNOWN')
2443:         need(result is True, 'CURRENT_OWNER_REQUIRED')
2444:         self.source_guard()
2445:         p = row['peer']
2446:         peer = Peer(p['server_port'], p['client_port'], p['accepted_monotonic_ns'])
2447:         return OwnerSample(self.policy.owner, self.policy.handle, self.policy.job,
2448:                            peer, time.monotonic_ns(), True, True)
2449: 
2450:     async def _world_post_drain_checkpoint(self, writer, row, sample):
2451:         """Requery only an exact owner sample that aged out before consumption."""
2452:         policy, policy_row = self.policy, row['policy_row']
2453:         now = time.monotonic_ns()
2454:         if self._packet_peer_mode is not None:
2455:             if type(sample) is PacketSample and now - sample.observed_ns >= policy.FRESH_NS:
2456:                 sample = await self._sample(row, synchronous_exact=True)
2457:             self._policy_sample(row, policy.checkpoint, writer, sample, time.monotonic_ns())
2458:             return sample
2459:         if (type(sample) is OwnerSample and policy_row is not None
2460:                 and sample.owner is policy.owner and sample.handle is policy.handle
2461:                 and sample.job is policy.job and sample.peer == policy_row.peer
2462:                 and sample.exact_identity_and_tuple is True and sample.alive is True
2463:                 and type(sample.observed_ns) is int
2464:                 and 0 < sample.observed_ns <= now
2465:                 and now - sample.observed_ns >= policy.FRESH_NS):
2466:             sample = await self._sample(row, synchronous_exact=True)
2467:         self._policy_sample(row, policy.checkpoint, writer, sample, time.monotonic_ns())
2468:         return sample
2469: 
2470:     async def _book_post_drain_sample(self, writer, row, operation, wire, sample):
```

## BROKER_PREBEGIN_NATIVE_PARENT_REFRESH_ALREADY_PRESENT
Source: C:\Users\Chansol\Documents\ChatGPT\싱글리니지\work\local_original_session\implementation-companion\local-packet-settings-core6041-world-v4\broker.py
SHA256: 6e703872e79a8b15e9ef9c92442521d93b6ff5c30091c0dd11068bc6f6976a2f

```text
5258:                         context.authority,wire,True,operation_lock,item_transfer_operation=item_transfer_operation)
5259:                 if allied is not None and wire is allied_player_operation.frame:
5260:                     allied_current = self._hp_resource_owner.begin_same_frame_resource_current(
5261:                         writer, row, allied_player_operation, wire)
5262:                 elif allied is not None and wire is allied_player_operation.removal:
5263:                     allied_current = self._hp_resource_owner.begin_same_frame_removal_resource_current(
5264:                         writer, row, allied_player_operation, wire)
5265:                     sample = await self._world_post_drain_checkpoint(writer, row, sample)
5266:                 if motion is not None:
5267:                     task = asyncio.current_task()
5268:                     if task is not None and task.cancelling(): raise asyncio.CancelledError()
5269:                     motion.begin(motion.planned)
5270:                 self.policy._skill_write_operation = skill_operation
5271:                 if trade_delivery is not None:
5272:                     self._policy_sample(row,self.policy.begin_write,writer,sample,opcode,len(wire),
5273:                         writer.transport.get_write_buffer_size(),time.monotonic_ns(),trade_delivery_part=trade_delivery_part)
5274:                     trade_delivery.reserved(trade_delivery_part,writer,row,wire)
5275:                 elif allied is not None and wire is allied_player_operation.removal:
5276:                     self._policy_sample(row, self.policy.begin_write, writer, sample, opcode, len(wire),
5277:                         writer.transport.get_write_buffer_size(), time.monotonic_ns(),
5278:                         allied_removal=(allied_player_operation, wire))
5279:                 elif readonly is not None:
5280:                     self._policy_sample(row, self.policy.begin_write, writer, sample, opcode, len(wire),
5281:                         writer.transport.get_write_buffer_size(), time.monotonic_ns(),
5282:                         **({"action_list_send_operation":readonly_operation} if action is not None
5283:                            else {"dialogue_send_operation":readonly_operation}))
5284:                     readonly.reserved(readonly_operation, writer, row, wire)
5285:                 else:
5286:                     self._policy_sample(row, self.policy.begin_write, writer, sample, opcode, len(wire),
5287:                                             writer.transport.get_write_buffer_size(), time.monotonic_ns())
5288:                 if allied_current is not None: allied_current.consume('BEGIN_WRITE')
5289:                 if update_state is not None:
```

## BROKER_WRITE_ATTEMPT_AND_FIRST_POSTDRAIN_NATIVE_READ
Source: C:\Users\Chansol\Documents\ChatGPT\싱글리니지\work\local_original_session\implementation-companion\local-packet-settings-core6041-world-v4\broker.py
SHA256: 6e703872e79a8b15e9ef9c92442521d93b6ff5c30091c0dd11068bc6f6976a2f

```text
5388:                     packet_inventory_pending = (row['policy_row'], row['policy_row'].drain_started_ns)
5389:                 if allied is not None:allied.send_phase(writer,row,wire,'WRITE_ATTEMPTED')
5390:                 if motion is not None:
5391:                     task = asyncio.current_task()
5392:                     if task is not None and task.cancelling(): raise asyncio.CancelledError()
5393:                     motion.attempt(writer, row, wire)
5394:                 if trade_delivery is not None:trade_delivery.write(trade_delivery_part,writer,row,wire)
5395:                 else:writer.write(wire)
5396:                 row['await_phase'] = 'WRITE_DRAIN' 
5397:                 await asyncio.wait_for(writer.drain(), self.policy.DRAIN_NS / 1e9)
5398:                 if allied_current is not None: allied_current.consume('DRAIN_PENDING')
5399:                 if trade_delivery is not None:
5400:                     trade_delivery.validate(trade_delivery_part,writer,row,wire,'DRAIN_PENDING')
5401:                 if hp_source_read is not None: hp_source_read.consume('DRAIN_PENDING')
5402:                 hp_owner = self._hp_resource_owner
5403:                 if status_operation is not None and hp_owner is not None and hp_owner._hp_effect is not None:
5404:                     hp_owner._hp_effect.drain_returned()
5405:                 if world_status is not None:
5406:                     world_status['resource_drain_returned'] = True
5407:                 if transfer_delivery is not None:
5408:                     transfer_delivery.drain_returned(writer, row, wire)
```

## BROKER_NEW_POSTDRAIN_SAMPLE_THEN_NATIVE_CURRENT
Source: C:\Users\Chansol\Documents\ChatGPT\싱글리니지\work\local_original_session\implementation-companion\local-packet-settings-core6041-world-v4\broker.py
SHA256: 6e703872e79a8b15e9ef9c92442521d93b6ff5c30091c0dd11068bc6f6976a2f

```text
5430:                     transfer.validate_wire(writer,row,wire,item_transfer_operation)
5431:                 try:
5432:                     row['await_phase'] = 'POST_DRAIN_OWNER'
5433:                     # Buff's original pending receipt validation can outlive a
5434:                     # sample. For that exact delivery, check the receipt first
5435:                     # and take the existing synchronous owner proof immediately
5436:                     # before policy consumption below.
5437:                     sample = None if buff_reply else await self._sample(row)
5438:                     if allied_current is not None: allied_current.consume('DRAIN_PENDING')
5439:                     if readonly is not None:
5440:                         readonly.validate(readonly_operation, writer, row, wire)
5441:                 except ValueError as error:
5442:                     if not quit_reply or error.args != ('CURRENT_OWNER_REQUIRED',):
```

## BROKER_FAILING_ALLIED_DRAIN_PENDING_CHECKPOINT
Source: C:\Users\Chansol\Documents\ChatGPT\싱글리니지\work\local_original_session\implementation-companion\local-packet-settings-core6041-world-v4\broker.py
SHA256: 6e703872e79a8b15e9ef9c92442521d93b6ff5c30091c0dd11068bc6f6976a2f

```text
5597:                     if allied is not None:
5598:                         while True:
5599:                             if allied_current is not None: allied_current.consume('DRAIN_PENDING')
5600:                             allied.validate(writer,wire)
5601:                             need(row['policy_row'].pending_opcode==opcode
5602:                                  and row['policy_row'].pending_size==len(wire)
5603:                                  and row['policy_row'].drain_started_ns is not None,
5604:                                  'ALLIED_SAME_PENDING_POLICY_DRAIN_REQUIRED')
5605:                             self._policy_sample(row,self.policy.checkpoint,writer,sample,time.monotonic_ns())
5606:                             queued=writer.transport.get_write_buffer_size()
5607:                             need(type(queued) is int and 0<=queued<=self.policy.WRITE_HIGH,
5608:                                  'ALLIED_CURRENT_DRAIN_QUEUE_REQUIRED')
5609:                             if queued==0:break
5610:                             await asyncio.sleep(0)
5611:                             if allied_current is not None: allied_current.consume('DRAIN_PENDING')
5612:                             sample=await self._sample(row)
5613:                     if motion is not None:
5614:                         while True:
```

## BROKER_POLICY_DRAINED_AND_NATIVE_AFTERDRAIN
Source: C:\Users\Chansol\Documents\ChatGPT\싱글리니지\work\local_original_session\implementation-companion\local-packet-settings-core6041-world-v4\broker.py
SHA256: 6e703872e79a8b15e9ef9c92442521d93b6ff5c30091c0dd11068bc6f6976a2f

```text
5633:                         sample = await (self._healing_post_drain_sample if healing_reply else self._book_post_drain_sample)(
5634:                             writer, row, skill_operation, wire, sample)
5635:                     if buff_reply:
5636:                         sample = await self._buff_post_drain_policy(
5637:                             writer, row, skill_operation, wire, sample, queued=queued)
5638:                     else:
5639:                         self._policy_sample(row, self.policy.drained, writer, sample, queued, time.monotonic_ns())
5640:                         if allied_current is not None: allied_current.consume('AFTER_DRAIN')
5641:                         if motion is not None:
5642:                             task = asyncio.current_task()
5643:                             if task is not None and task.cancelling(): raise asyncio.CancelledError()
5644:                             motion.drained(writer, row, wire)
```

## BROKER_ORIGINAL_SEND_FINALLY
Source: C:\Users\Chansol\Documents\ChatGPT\싱글리니지\work\local_original_session\implementation-companion\local-packet-settings-core6041-world-v4\broker.py
SHA256: 6e703872e79a8b15e9ef9c92442521d93b6ff5c30091c0dd11068bc6f6976a2f

```text
5741:                 if world_status is not None:
5742:                     status_service.world_frame_drained(writer, row, wire, world_status, queued)
5743:             except BaseException as error:
5744:                 if motion is not None: motion.fail(type(error).__name__)
5745:                 if inventory_service is not None:
5746:                     try: self._record_inventory_failure(error, 'SEND_BEFORE_FAILURE_CALLBACKS')
5747:                     except BaseException: pass  # Preserve primary/finally/cleanup.
5748:                 if hp_source_read is not None and hasattr(hp_source_read,'failed'):
5749:                     try: hp_source_read.failed(error)
5750:                     except BaseException: pass
5751:                 hp_owner = self._hp_resource_owner
5752:                 if status_operation is not None and hp_owner is not None and hp_owner._hp_effect is not None:
5753:                     try: hp_owner._hp_effect.failed(error)
5754:                     except BaseException: pass  # Preserve original send/cancel exception.
5755:                 if transfer_delivery is not None:
5756:                     transfer_delivery.failed(error)
5757:                 if skill_operation is not None:
5758:                     skill_operation.failed(error)
5759:                 if player_life_operation is not None: life.terminal(writer)
5760:                 if player_hit is not None:
5761:                     player_hit.terminal(npc_player_hit_operation)
5762:                 if status_service is not None and (world_status is not None or status_operation is not None):
5763:                     status_service.release(writer)
5764:                 if notification_service is not None:
5765:                     self._attack_session.fail()
5766:                 if restart_state is not None:
5767:                     restart_state['phase'] = 'TERMINAL'
5768:                 if feedback_service is not None:
5769:                     feedback_service.fail()  # Once-only ambiguous/cancelled frame is terminal.
5770:                 raise
5771:             finally:
5772:                 if allied_current is not None:
5773:                     primary_error = sys.exception()
5774:                     try: allied_current.retire()
5775:                     except BaseException as cleanup_error:
5776:                         if primary_error is None: raise
5777:                         primary_error.add_note('Allied same-frame retirement: '
5778:                             + type(cleanup_error).__name__ + ': ' + str(cleanup_error))
5779:                 if hp_source_read is not None: hp_source_read.retire()
5780:                 self.policy._skill_write_operation = None
5781:                 if isinstance(wire, bytearray):
5782:                     wire[:] = b'\0' * len(wire)
```

## BROKER_POLICY_PACKET_SAMPLE_VALIDATOR
Source: C:\Users\Chansol\Documents\ChatGPT\싱글리니지\work\local_original_session\implementation-companion\local-packet-settings-core6041-world-v4\broker.py
SHA256: 6e703872e79a8b15e9ef9c92442521d93b6ff5c30091c0dd11068bc6f6976a2f

```text
189:         self.npc_death, self.npc_remove = npc_death, npc_remove
190: 
191:     def _owner(self, sample, peer):
192:         if self._packet_peer_mode is None:
193:             return super()._owner(sample, peer)
194:         return self._packet_peer_mode.validate_sample(sample, peer, self.now, self.FRESH_NS)
```

## PEER_AUTHENTIC_NEW_SAMPLE_AND_CURRENT_VALIDATOR
Source: C:\Users\Chansol\Documents\ChatGPT\싱글리니지\work\local_original_session\implementation-companion\local-packet-settings-core6041-world-v4\packet_peer.py
SHA256: da88f68297f80061e718fc965bdac1f1821da91ebef3b8ceede7f38b12eaafe0

```text
302:     def _accepted_current(self, row):
303:         broker = self.broker
304:         need(broker is not None and broker._packet_peer_mode is self
305:              and not broker._closing and not broker.failure.is_set(),
306:              'PACKET_SERVER_LIFETIME_REQUIRED')
307:         writer = row['writer']
308:         saved = self._accepted.get(id(writer))
309:         need(saved is not None and saved[0] is row and saved[2] is writer
310:              and any(r is row for r in broker._claims[row['peer']['endpoint_port']])
311:              and accepted_row_open(row)
312:              and saved[3] is writer.transport and not writer.is_closing()
313:              and not saved[3].is_closing() and saved[4].fileno() >= 0
314:              and writer.get_extra_info('socket') is saved[4]
315:              and saved[4].getsockname() == ('127.0.0.1', row['peer']['endpoint_port'])
316:              and saved[4].getpeername() == ('127.0.0.1', row['peer']['client_port'])
317:              and saved[5] == tuple(sorted(row['peer'].items())),
318:              'PACKET_ACCEPTED_AUTHORITY_CHANGED')
319:         return saved
320: 
321:     def sample(self, row, peer_type):
322:         saved = self._accepted_current(row)
323:         p = row['peer']
324:         sample = PacketSample(self, row, saved[2], saved[3], saved[4],
325:             peer_type(p['server_port'], p['client_port'], p['accepted_monotonic_ns']),
326:             time.monotonic_ns())
327:         self._samples[id(row)] = sample
328:         return sample
329: 
330:     def validate_sample(self, sample, peer, now, fresh_ns):
331:         need(type(sample) is PacketSample and sample.issuer is self
332:              and self._samples.get(id(sample.row)) is sample,
333:              'PACKET_ISSUED_SAMPLE_REQUIRED')
334:         saved = self._accepted_current(sample.row)
335:         need(sample.writer is saved[2] and sample.transport is saved[3]
336:              and sample.accepted_socket is saved[4] and sample.peer == peer
337:              and type(sample.observed_ns) is int
338:              and peer.accepted_ns <= sample.observed_ns <= now
339:              and now - sample.observed_ns <= fresh_ns,
340:              'PACKET_CURRENT_SAMPLE_REQUIRED')
341: 
```

## SERVER_SOURCE_MAP_AND_METHOD_CURRENT
Source: C:\Users\Chansol\Documents\ChatGPT\싱글리니지\work\local_original_session\implementation-companion\local-allied-repeated-motion-trial-v1\packet_server.py
SHA256: 84348db869f3a55b91b15202b499d9351c15a9f14fef3a3baa3c7502d14a17d4

```text
50: class _Sources:
51:     def __init__(self):
52:         from source_loader import load_sources, SELECTED, EXTERNAL
53:         loaded, _ = load_sources()  # one cold graph selection; no second file scan
54:         self.selected = SELECTED
55:         self.modules = {module.__name__: module for module in loaded.values()}
56:         self.modules.update(EXTERNAL)
57:         self.broker = self.modules['tools.local_original_session.broker']
58:         self.launcher = self.modules['tools.local_original_session.launcher']
59:         self.methods = (self.broker.PersistentBroker._accept,
60:                         self.broker.PersistentBroker._sample,
61:                         self.broker.PersistentBroker._serve,
62:                         self.broker.PersistentBroker._send,
63:                         self.broker.PersistentBroker._local_companion_summon_locked,
64:                         self.launcher.GenuineConversations.conversation,
65:                         self.broker._TransportPolicy._owner,
66:                         self.broker._TransportPolicy.begin_write,
67:                         PacketPeerMode.sample, PacketPeerMode.current,
68:                         PacketPeerMode.current_for, PacketPeerMode.check_current,
69:                         PacketPeerMode.selection_for, PacketPeerMode.check_selection,
70:                         PacketPeerMode.register_packet_runtime, PacketPeerMode.poll_packet_session)
71: 
72:     def check(self):
73:         for name, module in self.modules.items():
74:             need(sys.modules.get(name) is module, 'PACKET_SOURCE_MODULE_CHANGED')
75:         need(self.methods == (self.broker.PersistentBroker._accept,
76:                               self.broker.PersistentBroker._sample,
77:                               self.broker.PersistentBroker._serve,
78:                               self.broker.PersistentBroker._send,
79:                               self.broker.PersistentBroker._local_companion_summon_locked,
80:                               self.launcher.GenuineConversations.conversation,
81:                               self.broker._TransportPolicy._owner,
82:                               self.broker._TransportPolicy.begin_write,
83:                               PacketPeerMode.sample, PacketPeerMode.current,
84:                               PacketPeerMode.current_for, PacketPeerMode.check_current,
85:                               PacketPeerMode.selection_for, PacketPeerMode.check_selection,
86:                               PacketPeerMode.register_packet_runtime, PacketPeerMode.poll_packet_session),
87:              'PACKET_SOURCE_METHOD_CHANGED')
88: 
```

## SERVER_CHECK_SOURCES
Source: C:\Users\Chansol\Documents\ChatGPT\싱글리니지\work\local_original_session\implementation-companion\local-allied-repeated-motion-trial-v1\packet_server.py
SHA256: 84348db869f3a55b91b15202b499d9351c15a9f14fef3a3baa3c7502d14a17d4

```text
203:     def check_sources(self):
204:         need(not self.closed and self.sources is not None
205:              and self.conversations is not None, 'PACKET_RESOURCE_LIFETIME_REQUIRED')
206:         self.sources.check()
207:         self.conversations.check()
208: 
```

## RESOURCE_PARENT_NATIVE_CURRENT_CONSUME
Source: C:\Users\Chansol\Documents\ChatGPT\싱글리니지\work\local_original_session\implementation-5\combat-adjudication\same-frame-resource-removal-v3\candidate\tools\local_original_session\hp_resource_owner.py
SHA256: 90e71a9649fc0636267a048f4c1fb67a28c55e0c523be0f26070048cc16d7b40

```text
1716:     def consume(self, phase):
1717:         p = self.proof()
1718:         need(self.cap is not None and phase in ('BEFORE_WRITE_CHECKPOINT', 'BEGIN_WRITE',
1719:                                                'DRAIN_PENDING', 'AFTER_DRAIN'),
1720:              'RESOURCE_SAME_FRAME_ISSUED_CAP_PHASE_REQUIRED')
1721:         need((self.phase == 'BEFORE_WRITE_CHECKPOINT' and phase in ('BEFORE_WRITE_CHECKPOINT', 'BEGIN_WRITE'))
1722:              or (self.phase == 'DRAIN_PENDING' and phase in ('DRAIN_PENDING', 'AFTER_DRAIN'))
1723:              or (self.phase == phase == 'AFTER_DRAIN'),
1724:              'RESOURCE_SAME_FRAME_ORDERED_PHASE_REQUIRED')
1725:         # SKILL, when present, is sealed by this same native cap/callback too.
1726:         row = p.owner.store.participant_for_projection(self.cap, 'RESOURCE', participant=self,
1727:             index=0, wire=p.wire, phase=phase)
1728:         need(p.owner.batch.encoded(row) == p.owner.batch.encoded(
1729:              json.loads(p.participants_raw)['RESOURCE']), 'RESOURCE_SAME_FRAME_RESOURCE_CHANGED')
1730:         self.phase = 'DRAIN_PENDING' if phase == 'BEGIN_WRITE' else phase
1731:         return p.snapshot
1732: 
```

## RESOURCE_PARENT_REMOVAL_NATIVE_PHASE_RULES
Source: C:\Users\Chansol\Documents\ChatGPT\싱글리니지\work\local_original_session\implementation-5\combat-adjudication\same-frame-resource-removal-v3\candidate\tools\local_original_session\hp_resource_owner.py
SHA256: 90e71a9649fc0636267a048f4c1fb67a28c55e0c523be0f26070048cc16d7b40

```text
1699: 
1700:     def _validate_removal_memory(self, p, binding, *, participants, index, wire, phase):
1701:         need(p.owner.store._delivery_validating is True
1702:              and binding is p.binding and type(index) is int and index == 0 and wire is p.wire
1703:              and p.owner.batch.encoded(participants) == p.participants_raw
1704:              and phase in ('BEFORE_RESERVE', 'BEFORE_WRITE_CHECKPOINT', 'BEGIN_WRITE', 'DRAIN_PENDING', 'AFTER_DRAIN'),
1705:              'RESOURCE_REMOVAL_EXACT_NATIVE_PROJECTION_REQUIRED')
1706:         need((phase in ('BEFORE_RESERVE', 'BEFORE_WRITE_CHECKPOINT', 'BEGIN_WRITE')
1707:               and p.part.removal_phase == 'RESERVED')
1708:              or (phase == 'DRAIN_PENDING' and p.part.removal_phase in ('RESERVED', 'WRITE_ATTEMPTED'))
1709:              or (phase == 'AFTER_DRAIN' and p.part.removal_phase in ('WRITE_ATTEMPTED', 'DRAINED')),
1710:              'RESOURCE_REMOVAL_ORIGINAL_PART_PHASE_REQUIRED')
1711:         if phase in ('BEGIN_WRITE', 'DRAIN_PENDING', 'AFTER_DRAIN'):
1712:             need(p.read._parent is self and p.read._cap is self.cap and self.cap is not None,
1713:                  'RESOURCE_REMOVAL_ATTACHED_NATIVE_READER_REQUIRED')
1714:         return True
```

## PUBLICATION_CURRENT_VALIDATE_AND_WRITE_PHASE_MARK
Source: C:\Users\Chansol\Documents\ChatGPT\싱글리니지\work\local_original_session\implementation-companion\local-allied-publication-core6041-motion-v2\allied_player_publication.py
SHA256: 37a8ecfdc587a67b64c6ce464c63b4f1b1993ec91ee65aadc212a12aea933897

```text
512:     def validate(self, writer, wire):
513:         record = self.for_frame(writer, wire)
514:         phase = record.phase if wire is record.frame else record.removal_phase
515:         need(phase in ('REGISTERED', 'RESERVED', 'WRITE_ATTEMPTED'), 'ALLIED_SINGLE_DELIVERY_REQUIRED')
516:         return record
517: 
518:     def send_phase(self, writer, row, wire, phase, *, queued=None):
519:         record = self.validate(writer, wire)
520:         removal = wire is record.removal
521:         current = record.removal_phase if removal else record.phase
522:         expected = {'RESERVED': 'REGISTERED', 'WRITE_ATTEMPTED': 'RESERVED', 'DRAINED': 'WRITE_ATTEMPTED'}
523:         need(row is record.row and current == expected[phase], 'ALLIED_ORDERED_ORIGINAL_SEND_REQUIRED')
524:         policy = row['policy_row']
525:         if phase == 'RESERVED':
526:             record.policy_row, record.sent_before = policy, policy.sent
527:         else:
528:             need(policy is record.policy_row, 'ALLIED_SAME_POLICY_ROW_REQUIRED')
529:         if phase == 'WRITE_ATTEMPTED':
530:             need(policy.pending_opcode == int.from_bytes(wire[2:4], 'little')
531:                  and policy.pending_size == len(wire) and policy.drain_started_ns is not None
532:                  and policy.sent == record.sent_before, 'ALLIED_ORIGINAL_PENDING_WRITE_REQUIRED')
533:             record.drain_started = policy.drain_started_ns
534:         if phase == 'DRAINED':
535:             need(policy.sent == record.sent_before + 1 and queued == 0 and row['policy_row'].pending_opcode is None
536:                  and row['policy_row'].drain_started_ns is None,
537:                  'ALLIED_ORIGINAL_POLICY_DRAIN_REQUIRED')
538:         if removal:
539:             record.removal_phase = phase
540:         else:
541:             record.phase = phase
542: 
```

## CALLER_CURRENT_SCOPE_ENDS_BEFORE_RESTART_REQUEST
Source: C:\Users\Chansol\Documents\ChatGPT\싱글리니지\work\local_original_session\implementation-companion\plan-comp01-actor-port-binding-v3\run_account_scope.py
SHA256: 47eb70deab644791f3d59f14920304e12d1ca6fb96030b783afdc2784d9a7810

```text
473: 
474:                         # Read the original WORLD DATA and position under their original row.
475:                         # No settings write or movement is needed for first summon.
476:                         async with current.broker._row_operation(current.writer,current.row):
477:                             need(server.check_current(current) is current,
478:                                  'COMP01_ORIGINAL_POST_SUMMON_CURRENT_REQUIRED')
479:                             need(host.actor_port.validate_server_pose(owner=registration.owner, actor=actor) is True,
480:                                  'COMP01_ORIGINAL_TYPED_SERVER_POSE_REQUIRED')
481:                             meta['server_pose_current'] = dict(actor_uid=actor.actor_uid,
482:                                 map_id=actor.map_id, grid=list(actor.grid), direction=actor.direction,
483:                                 alive=actor.alive, policy=actor.server_pose.policy, native_pose_observed=False)
484:                             world_data = current.broker._packet_peer_mode.world_frame_data_for(current)
485:                             need(world_data.frame.opcode == 0x4e28
486:                                  and world_data.completion['status'] == 'WORLD_DRAINED',
487:                                  'COMP01_ORIGINAL_WORLD_INPUT_REQUIRED')
488:                             carried = dict(owner_position=current.position.metadata(),
489:                                 positions_sha256=hashlib.sha256(current.broker.realm.positions.path.read_bytes()).hexdigest())
490:                             meta['carried_owner_position'] = dict(carried)
491:                             meta['original_world_input'] = dict(opcode=world_data.frame.opcode,
492:                                 received_ordinal=world_data.received_ordinal,
493:                                 status=world_data.completion['status'])
494: 
495:                         # Quit is refused by the original packet Policy. Existing
496:                         # empty Restart is source-bound and routed to the original
497:                         # _prepare_restart, whose first companion edge precedes ACK.
498:                         # One actual request only; no direct handler or clean-close
499:                         # assumption, and no next ready_current after an ERROR.
500:                         stage = 'LOCAL_RETIREMENT_ORIGINAL_RESTART'
501:                         client.packetless_step('EXISTING_RESTART_MENU_SELECTED', next_opcode=restart.REQUEST_OPCODE)
502:                         retirement = await client.send_request(restart.REQUEST_OPCODE, b'')
503:                         removal_frames = tuple(f for f in retirement.frames if f.opcode == 0x4E40)
504:                         emitted = []
505:                         for frame in removal_frames:
506:                             opcode, uid = modules['npc_death'].validate_frame(frame.wire)
507:                             emitted.append(dict(opcode=opcode, actor_uid=uid, bytes=len(frame.wire),
508:                                 sha256=hashlib.sha256(frame.wire).hexdigest(), s2c_ordinal=frame.s2c_ordinal))
509:                         # Retained original results/receipt reads only; no new
```

## PUBLICATION_REMOVAL_CURRENT_NATIVE_READ
Source: C:\Users\Chansol\Documents\ChatGPT\싱글리니지\work\local_original_session\implementation-companion\local-allied-publication-core6041-motion-v2\allied_player_publication.py
SHA256: 37a8ecfdc587a67b64c6ce464c63b4f1b1993ec91ee65aadc212a12aea933897

```text
386:     def removal_current(self, record):
387:         """Admit only a drained registration in a fresh, same-selection scope.
388: 
389:         Binding identity remains send-scoped for publication. Retirement may
390:         acquire a later operation, but cannot adopt a different selection,
391:         writer, row, lease, Host or account RESOURCE owner. Never rebind the
392:         retained publication record or infer native absence from this check.
393:         """
394:         need(type(record) is PlayerRegistration and self.records.get(record.uid) is record
395:              and record.issuer is self and reserved(record.uid)
396:              and record.phase == 'DRAINED', 'ALLIED_DRAINED_TYPED_RETIREMENT_REQUIRED')
397:         owner = self.removal_operation_owner(record)
398:         state, row, binding, _ = self.operation(record.host, owner, record.lease)
399:         original = record.selected_binding
400:         need(state.selection is record.selection and row is record.row
401:              and binding.generation is original.generation
402:              and binding.writer is original.writer is record.owner.connection
403:              and binding.uid == original.uid == record.owner.character_uid
404:              and binding.operation_lock is original.operation_lock is row['operation_lock'],
405:              'ALLIED_SAME_SELECTED_RETIREMENT_REQUIRED')
406:         # Original _resource checks live Root/Host/current leases, exact Core,
407:         # provider/Store/source/locks/path, nonpending account and RESOURCE uid,
408:         # document digest/revision under the original locks. A valid resource
409:         # may have changed since publication; the saved digest is not current.
410:         policy = row['policy_row']
411:         if policy.pending_opcode == 0x4e40:
412:             read = self._removal_reads.get(id(record))
413:             need(type(read) is RemovalResourceRead, 'ALLIED_ISSUED_REMOVAL_READ_REQUIRED')
414:             read.validate_pending(record, binding)
415:         else:
416:             path, _, _ = self._resource(record.host, owner, record.lease)
417:             need(path == record.resource_path, 'ALLIED_SAME_RETIREMENT_RESOURCE_PATH_REQUIRED')
418:         return record
```

## PUBLICATION_PENDING_READER_NATIVE_CURRENT
Source: C:\Users\Chansol\Documents\ChatGPT\싱글리니지\work\local_original_session\implementation-companion\local-allied-publication-core6041-motion-v2\allied_player_publication.py
SHA256: 37a8ecfdc587a67b64c6ce464c63b4f1b1993ec91ee65aadc212a12aea933897

```text
649:     def validate_pending(self, record, binding):
650:         p = self._anchors(record, binding)
651:         parent, cap = self._parent, self._cap
652:         module = sys.modules[type(p.hp).__module__]
653:         need(type(parent) is module.SameFrameResourceCurrent and p.hp._same_frame_current is parent
654:              and parent.cap is cap and parent.writer is binding.writer
655:              and parent.phase == 'DRAIN_PENDING' and record.removal_phase in ('RESERVED', 'WRITE_ATTEMPTED')
656:              and record.row['policy_row'] is p.policy and p.policy.sent == p.sent
657:              and p.policy.pending_opcode == 0x4e40 and p.policy.pending_size == len(p.wire)
658:              and p.policy.drain_started_ns is not None,
659:              'ALLIED_REMOVAL_EXACT_PENDING_PARENT_REQUIRED')
660:         with p.store_lock, p.character_lock, p.realm_lock:
661:             # Keep original operation/Host/status/lease checks. The Resource native
662:             # parent serves direct status.current; no Store._current is invoked here.
663:             _, row, actual, _ = p.issuer.operation(record.host, p.operation_owner, record.lease)
664:             need(actual is binding and row is record.row, 'ALLIED_REMOVAL_CURRENT_OPERATION_CHANGED')
665:             native, value, _ = p.store._delivery_current(cap, parent, 0, p.wire, 'DRAIN_PENDING')
666:             resource = value['participants'].get('RESOURCE:' + str(record.lease.uid))
667:             need(native['kind'] == 'PROJECTION' and native['raw'] == p.store_raw == p.store._raw
668:                  and native['sent'] == p.sent and cap.binding is binding and cap.parent is parent
669:                  and cap.frames[0] is p.wire and cap.transport is p.transport and cap.task is p.task
670:                  and p.api.encoded(resource) == p.resource_raw
671:                  and resource['revision'] == p.revision and resource['digest'] == p.digest
672:                  and p.hp.status.current(binding.writer) is p.snapshot,
673:                  'ALLIED_REMOVAL_SEALED_RESOURCE_CHANGED')
674:             p.issuer.operation(record.host, p.operation_owner, record.lease)
675:         return True
676: 
677:     def retire(self):
```
