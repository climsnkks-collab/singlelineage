"""World feature: alignment. Existing packet/store operations, unchanged."""
from __future__ import annotations



def _world_alignment_kill(self, event):
    """Existing kill-once callback; L1J calculation, run395 full SelfInfo f18."""
    from tools.local_original_session import world_alignment
    world, uid = self._world, event.pc_uid
    state = world.combat.pcs.get(uid)
    if state is None or event.template_id not in self._world_alignment_catalog:
        return  # M1 table only; no guessed lawful for dungeon templates.
    change = world_alignment.on_kill(self._world_lawful.get(uid, state.status_fields[18]),
        world.data.monsters[event.template_id], catalog=self._world_alignment_catalog,
        pc_dead=state.dead)
    self._world_lawful[uid] = change.new_lawful
    state.status_fields[18] = change.new_lawful  # _reward queues the complete status next.
    from tools.local_original_session.world_progress import Progress
    world.progress_dirty[uid] = Progress(world.exp[uid], state.profile.level,
                                         state.max_hp, state.max_mp, change.new_lawful)
    self._world_alignment_changes = (self._world_alignment_changes + [dict(
        uid=uid, npc_uid=event.npc_uid, delta=change.delta, lawful=change.new_lawful)])[-16:]


METHODS = (
    _world_alignment_kill,
)
HOOKS = {'after_kill': ('_world_alignment_kill',)}


def setup_alignment(self):
    from tools.local_original_session import world_alignment
    self._world_alignment_catalog = world_alignment.load_alignment_catalog()
    self._world_lawful, self._world_alignment_changes = {}, []
    self._world_death_risks = []
    self._world.combat.on_kill = lambda event: self.run_sync_hooks('after_kill', event)
