# REVIEW EXCERPTS ONLY, NOT AN EXECUTABLE MODULE
# Original: work/local_original_session/shared-api/npc-postreply-drain-current/broker.py
# Full original SHA256: 8b289b8bdc71e2c4139429028a1ea6a9b21587367225e9ad7a26cbec9aa09a89

# Original lines 2077-2106: _row_operation
    @asynccontextmanager
    async def _row_operation(self, writer, row):
        provider = self._canonical_provider
        if provider is None:
            async with row['operation_lock']:
                yield
        else:
            # This REPLACES the real outer acquisition, including preselection,
            # read-poll and EOF. It never adopts/reacquires a held legacy lock.
            task = asyncio.current_task()
            need(self._canonical_operation_task is not task,
                 'BATCH_OPERATION_SCOPE_ALREADY_ACTIVE')
            async with self._canonical_operation_gate:
                need(self._canonical_operation_task is None and self._canonical_provider is provider,
                     'RESOURCE_SAME_CANONICAL_PROVIDER_REQUIRED')
                # A queued server-owned row task may resume after close begins.
                # Cancel that task; foreign callers still face the original guard.
                if self._closing and row.get('task') is task:
                    raise asyncio.CancelledError()
                self._canonical_operation_task = task
                try:
                    async with provider.connection_operation(writer, row):
                        try:
                            yield
                        finally:
                            controller=getattr(self,'_character_scopes',None)
                            if controller is not None:
                                controller.source.check().finish_scope_chunk(self,provider,writer,row)
                finally:
                    self._canonical_operation_task = None

# Original lines 3279-3282: attack_player_repeated
    async def attack_player_repeated(self, writer, *, expected_context, raw_effect, direction, policy, retaliation_lease=None, continuous_lease=None):
        service = self._npc_player_hit_repeated_service(policy)
        return await self._attack_player_current(writer, service=service, expected_context=expected_context,
            raw_effect=raw_effect, direction=direction, repeated=True, retaliation_lease=retaliation_lease,continuous_lease=continuous_lease)

# Original lines 3302-3306: attack_player_once
    async def attack_player_once(self, writer, *, expected_context, raw_effect, direction, policy):
        from tools.local_original_session import npc_player_hit
        service = self._npc_player_hit_service(policy)
        return await self._attack_player_current(writer, service=service, expected_context=expected_context,
            raw_effect=raw_effect, direction=direction, repeated=False)

# Original lines 3308-3395: _attack_player_current
    async def _attack_player_current(self, writer, *, service, expected_context, raw_effect, direction, repeated, retaliation_lease=None, continuous_lease=None):
        from tools.local_original_session import npc_player_hit
        rows = [r for values in self._claims.values() for r in values if r['writer'] is writer]
        need(len(rows) == 1, 'NPC_PLAYER_HIT_CURRENT_ROW_REQUIRED')
        row, = rows
        operation = None
        async with self._row_operation(writer, row):
            if self._hp_resource_owner is not None:
                self._hp_resource_owner.require_hp_quiescent(writer)
            # Invalid/stale requests do not consume a different active request.
            service.validate_locked(writer, expected_context)
            if retaliation_lease is not None:
                from tools.local_original_session import npc_retaliation
                need(repeated is True, 'RETALIATION_REPEATED_PRODUCER_REQUIRED')
                npc_retaliation.validate(self,writer,row,retaliation_lease,expected_context)
            if continuous_lease is not None:
                from tools.local_original_session import npc_continuous_retaliation
                need(repeated is True, 'RETALIATION_REPEATED_PRODUCER_REQUIRED')
                npc_continuous_retaliation.validate(self,writer,row,continuous_lease,expected_context)
            if repeated:
                service.require_repeated_ready(writer, row, expected_context.snapshot,source_uid=expected_context.source_uid)
            else:
                need(id(writer) not in service._operations, 'NPC_PLAYER_HIT_ONCE_REQUEST_REQUIRED')
            await self._checkpoint(writer, row)
            service.validate_locked(writer, expected_context)
            need(id(writer) not in service.status._operations, 'HP_STATUS_CURRENT_SNAPSHOT_ONCE_REQUIRED')
            if retaliation_lease is not None:
                npc_retaliation.validate(self,writer,row,retaliation_lease,expected_context)
            if continuous_lease is not None:
                npc_continuous_retaliation.validate(self,writer,row,continuous_lease,expected_context)
            operation = service.prepare_locked(writer, expected_context=expected_context)
            try:
                if retaliation_lease is not None:
                    npc_retaliation.validate(self,writer,row,retaliation_lease,expected_context).bind_operation_locked(
                        writer,row,retaliation_lease,expected_context,operation)
                if continuous_lease is not None:
                    npc_continuous_retaliation.validate(self,writer,row,continuous_lease,expected_context).bind_operation_locked(
                        writer,row,continuous_lease,expected_context,operation)
                wire = service.build_locked(writer, operation, raw_effect=raw_effect, direction=direction)
                await self._send(writer, row, (wire,), game=True, operation_lock=row['operation_lock'],
                                 npc_player_hit_operation=operation,retaliation_lease=retaliation_lease,continuous_lease=continuous_lease)
                service.validate_locked(writer, expected_context)
                if retaliation_lease is not None:
                    npc_retaliation.validate(self,writer,row,retaliation_lease,expected_context,operation)
                if continuous_lease is not None:
                    npc_continuous_retaliation.validate(self,writer,row,continuous_lease,expected_context,operation)
                before = expected_context.snapshot
                decision = service.decision_locked(writer,operation)
                if decision.damage == 0:
                    result=npc_player_hit.Result(before,before,expected_context.source_uid,service,operation)
                    operation.result,operation.phase=result,'COMMITTED'
                    operation.hp_transport='NOT_REQUIRED'
                    service.last_result=result.metadata()
                    return result
                if decision.damage >= before.current_hp:
                    need(operation.adjudication is not None,'COMBAT_LETHAL_DECISION_REQUIRED')
                    inputs=await service.adjudicator.prepare_recovery_inputs_locked(writer,service,operation)
                    operation.life_result=await self._player_life.lethal_adjudicated_locked(
                        writer,operation,inputs,continuous_context=continuous_lease,
                        expected_context=getattr(inputs,'_context',None))
                    operation.phase='LETHAL_COMMITTED'
                    return operation.life_result
                if repeated:
                    from tools.local_original_session import hp_status
                    status = service.status.prepare_repeated(writer, row, expected_snapshot=before,
                        expected_revision=before.revision, policy=hp_status.REPEATED_POLICY,
                        current_hp=before.current_hp-decision.damage)
                else:
                    status = service.status.prepare(writer, row, current_hp=before.current_hp-decision.damage,
                        maximum_hp=before.maximum_hp, expected_snapshot=before, expected_revision=before.revision)
                operation.hp_operation, operation.phase, operation.hp_transport = status, 'STATUS', 'PREPARED'
                service.remember(operation)
                await self._send(writer, row, (status.wire,), game=True, operation_lock=row['operation_lock'],
                                 status_operation=status, npc_player_hit_operation=operation,retaliation_lease=retaliation_lease,continuous_lease=continuous_lease)
                result = npc_player_hit.Result(before, status.result.after, expected_context.source_uid,
                                               service, operation)
                operation.result = result
                operation.phase = 'COMMITTED'
                service.last_result = result.metadata()
                return result
            except BaseException as error:
                if self._hp_resource_owner is not None:
                    try: self._hp_resource_owner.fail_active_hp(writer,error)
                    except BaseException: pass
                service.terminal(operation)  # Preserve both partial transports and committed HP.
                row['failed'] = True
                self._fail('NPC_PLAYER_HIT_OUTCOME_UNKNOWN')
                raise

# Original lines 1085-1104: normal-life route guard
                return ()
            game.routes[0x4ed4]=action_request
        for opcode, handler in tuple(game.routes.items()):
            async def terminal_guard(payload, operation=handler, route_opcode=opcode):
                need(not self._settings_failed, 'SETTINGS_PERSISTENCE_FATAL')
                if id(writer) in self._quit and route_opcode == QUIT_REQUEST:
                    return await duplicate_quit(payload)
                need(id(writer) not in self._quit, 'QUIT_TERMINAL_SESSION')
                life_broker = getattr(self,'_player_life_broker',None)
                if life_broker is not None and route_opcode not in (0x4eec,QUIT_REQUEST,ALIVE_REQUEST,settings.OPCODE):
                    life_broker._player_life.check_normal_locked(writer)
                return await operation(payload)
            game.routes[opcode] = terminal_guard
        return game

    def bound_account(self, writer, game):
        bound = self._account_bound.get(id(writer))
        need(self.registry.resolve(writer) is game
             and bound is not None and bound[0] is writer and bound[1] is game and game.list_sent,
             'SAME_0263_BOUND_ACCOUNT_WRITER_REQUIRED')

# Original lines 4833-4852: normal-life route guard
            life,player_life_operation = lethal,npc_player_lethal_operation
        if player_life_operation is not None:
            need(life is not None and game is True and len(replies) == 1
                 and operation_lock is row['operation_lock'] and operation_lock.locked()
                 and status_operation is None, 'PLAYER_LIFE_ORIGINAL_LOCKED_SEND_REQUIRED')
            life.validate(writer,row,replies[0],player_life_operation,'PREPARED')
        elif life is not None and game and not (status_operation is not None and status_operation.life_context is not None):
            # Empty route replies (including the already-sent dead ACK) emit nothing.
            if replies and not all(type(wire) is bytes and wire in (QUIT_SUCCESS_FRAME,ALIVE_FRAME)
                                   for wire in replies):
                life.check_normal_locked(writer)
        status_service = getattr(self, '_hp_status', None)
        player_hit = getattr(self, '_npc_player_hit', None) if npc_player_hit_operation is not None else None
        if npc_player_hit_operation is not None:
            need(player_hit is not None and player_hit is self.realm._npc_player_hit and game is True
                 and len(replies) == 1 and operation_lock is row['operation_lock'] and operation_lock.locked(),
                 'NPC_PLAYER_HIT_ORIGINAL_LOCKED_SEND_REQUIRED')
            player_hit.validate_delivery(writer, row, replies[0], npc_player_hit_operation)
        world_status = (status_service.begin_world(writer, row, replies)
                        if game and status_service is not None and status_operation is None and skill_operation is None and readonly is None and trade_delivery is None and transfer_delivery is None else None)

# Original lines 4997-5016: normal-life route guard
                    current = self._packet_inventory.current(writer, row, world_required=True)
                    sample = self._packet_inventory.owner_checkpoint_sync(writer, row,
                        self._inventory_service, current, wire, True, operation_lock,
                        item_transfer_operation=transfer_delivery)
                if skill_operation is not None:
                    skill_operation.before_write_checkpoint(writer, row, wire)
                if player_life_operation is not None:
                    life.validate(writer,row,wire,player_life_operation,'RESERVED')
                elif life is not None and game and not (status_operation is not None and status_operation.life_context is not None):
                    if not (type(wire) is bytes and wire in (QUIT_SUCCESS_FRAME,ALIVE_FRAME)):
                        life.check_normal_locked(writer)
                if player_hit is not None:
                    player_hit.validate_delivery(writer, row, wire, npc_player_hit_operation)
                    if retaliation_lease is not None:
                        from tools.local_original_session import npc_retaliation
                        npc_retaliation.validate(self,writer,row,retaliation_lease,npc_player_hit_operation.context,npc_player_hit_operation)
                    if continuous_lease is not None:
                        from tools.local_original_session import npc_continuous_retaliation
                        npc_continuous_retaliation.validate(self,writer,row,continuous_lease,npc_player_hit_operation.context,npc_player_hit_operation)
                opcode = int.from_bytes(wire[2:4], 'little')
