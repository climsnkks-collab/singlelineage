# Own adapter control-flow excerpt; abstract dependencies, not executable.
# No original client code, ABI, offsets or live data.
async def outer_loop(owner, broker, feature, monitor, scenario):
    while not scenario.stop.is_set():
        if not owner.tick():
            monitor.tick(state="NATIVE_EXIT", force=True)
            break
        if broker_failed():
            monitor.tick(state="BROKER_FAILURE", force=True)
            break
        health_ready()
        result = await feature.poll(monitor)
        if not frozen_typed_item_scope(feature, monitor):
            monitor.tick(broker)
        existing_controls_stop_sleep()

async def runner_poll(self, monitor):
    try:
        result = await self.original.poll(monitor)
        await self.start_once_after_actual_add_if_needed()
        await self.poll_ground_retirement(monitor)
        self.capture_in_memory_progress()
        if not frozen_typed_item_scope(self, monitor):
            self.scenario.save_output_only_json_fsync()
        return result
    except CancelledError:
        self.copy_cached_diagnostics_only()
        self.scenario.fail_and_save_then_stop("CANCELLED")
        raise
    except Exception as error:
        self.original.ui.close()
        self.copy_cached_diagnostics_only()
        self.scenario.fail_and_save_then_stop(error)

async def ui_poll(self):
    self.check_original_clock_once()  # now - phase_started < original 10s
    context = await self.fresh_context_under_current_row_lock()
    if self.phase == "DROP_ENTRY_WAIT":
        value = self.original_entry.collect()
        if value.status == "WAITING":
            return self.report()
        require_original_normal_return(value)
        if self.quantity == 1:
            self.phase = "DROP_BACKEND"  # preserves SAME phase_started
        else:
            self.original_popup.submit()
            self.start_phase("DROP_POPUP_WAIT")
        return self.report()  # earlier context is not reused as post-RET authority
    if self.phase == "DROP_BACKEND":
        if context.snapshot.phase != "DROPPED" or context.session.phase != "DROPPED":
            return self.report()
        require(context.owner == "GROUND" and context.membership == "DRAINED")
        require(context.pending is None and context.equipment == self.equipment)
        after = await self.fresh_context_under_current_row_lock()
        require_same_current_operation(context, after)
        self.begin_original_client_inventory_observer(after)
        self.phase = "DROP_CLIENT"  # preserves SAME phase_started
        return self.report()
    if self.phase == "DROP_CLIENT":
        if not await self.fresh_original_client_A_only_observation(context):
            return self.report()
        self.original_entry.submit_get()
        self.start_phase("GET_ENTRY_WAIT")

async def server_drop_handler(self, accepted_original_request):
    context = self.validate_current_owned_operation(accepted_original_request)
    self.commit_ground_custody_cas(context)
    await self.send_remove_and_spawn_with_current_owner_checks(context)
    self.complete_ground_registration(context)
    self.mark_membership_drained_and_session_dropped_clear_pending(context)
    return  # next inbound frame on this connection is processed after this return
