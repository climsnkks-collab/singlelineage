"""World feature: alignment. Existing packet/store operations, unchanged."""
from __future__ import annotations



def _world_alignment_kill(self, event):
    """Existing kill-once callback; L1J calculation, run395 full SelfInfo f18."""
    from tools.local_original_session import world_alignment
    world, uid = self._world, event.pc_uid
    state = world.combat.pcs.get(uid)
    if state is None or event.template_id not in self._world_alignment_catalog:
        return  # M1 table only; no guessed lawful for dungeon templates.
    change = world_alignment.on_kill(world.progress.lawful_of(uid, state.status_fields[18]),
        world.data.monsters[event.template_id], catalog=self._world_alignment_catalog,
        pc_dead=state.dead)
    world.progress.set_lawful(uid, change.new_lawful)
    self._world_alignment_changes = (self._world_alignment_changes + [dict(
        uid=uid, npc_uid=event.npc_uid, delta=change.delta, lawful=change.new_lawful)])[-16:]


def setup_alignment(self):
    from tools.local_original_session import world_alignment
    self._world_alignment_catalog = world_alignment.load_alignment_catalog()
    self._world_alignment_changes = []
    self._world_death_risks = []


def _world_alignment_death(self, uid):
    from tools.local_original_session import world_alignment
    state = self.world.combat.pcs[uid]
    lawful = self.world.progress.lawful_of(uid, state.status_fields[18])
    self._world_death_risks = (self._world_death_risks + [dict(uid=uid, lawful=lawful,
        chance_per_mille=world_alignment.death_drop_chance(lawful),
        max_attempts=world_alignment.death_drop_max_attempts(lawful),
        applied=False, reason='CALCULATION_ONLY_DEATH_CONTEXT_UNRESOLVED')])[-16:]


def _world_alignment_report(self, result):
    result['alignment_changes'] = list(self._world_alignment_changes)
    result['death_drop_risks'] = list(self._world_death_risks)


METHODS = (_world_alignment_kill, setup_alignment, _world_alignment_report,
           _world_alignment_death)
HOOKS = {'initialize': ('setup_alignment',),
         'after_kill': ('_world_alignment_kill',),
         'after_death': ('_world_alignment_death',),
         'report': ('_world_alignment_report',)}
NONCRITICAL_HOOKS = ('report',)
