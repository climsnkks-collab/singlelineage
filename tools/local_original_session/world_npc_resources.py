"""Shared, generation-bound NPC MP for serialized world consumers.

This service owns current MP and cumulative drained MP, independently of any
optional spell/weapon feature. Call only under the existing world runtime lock.
The drain ceiling is local_policy from L1J Config.java:570 and
L1NpcInstance.java:2094-2104 (40 per NPC life), not an official Classic formula.
NPC resources are transient; PC MP and persistence remain with WorldCombat.
"""
from __future__ import annotations

from dataclasses import dataclass

from tools.local_original_session.world_entities import Kind

EXTENSION_KEY = 'npc_resources'
NPC_DRAIN_LIMIT = 40
# Explicit L1J backend policy shared by ordinary PCs and saved companions.
# L1Attack.java:1208-1221 requests, :1442-1453 pays the attacker;
# Config.java:570-572 caps, L1NpcInstance.java:2094-2104 bounds actual drain.
# L1PcInstance.java:2167-2182 gates on hit, including zero damage.
# L1ItemId.java:108-109 uses 126/127; local Classic342 is identified by
# data/m1/items_ext/weapons.json:11811. No local mapping for 127 is assumed.
MANA_DRAIN_POLICY = 'local_policy:L1J_STAFF_OF_MANA'
STAFF_OF_MANA = 342
PER_HIT_CAP = 9


def mana_drain_roll(enchant, rng):
    """L1J uniform 1..enchant+3, at most nine; <=0 is a LOCAL safe zero.

    That nonpositive case differs from L1J's invalid nextInt(0) call.
    L1WeaponSkill.java:220-231 is item286, not this weapon's producer.
    """
    sides = enchant + 3
    return 0 if sides <= 0 else min(PER_HIT_CAP, rng.randint(1, sides))


@dataclass
class _Mana:
    current: int
    drained: int = 0


class NpcResources:
    def __init__(self, entities):
        self.entities = entities
        self._mana = {}

    def _current(self, ref, initial_mp):
        target = self.entities.resolve(ref)
        if target is None or not target.alive or target.kind is not Kind.NPC:
            return None
        return self._mana.setdefault(ref, _Mana(max(0, int(initial_mp))))

    def mana_of(self, ref, initial_mp):
        row = self._current(ref, initial_mp)
        return 0 if row is None else row.current

    def spend_mana(self, ref, initial_mp, requested):
        """Pay a whole spell cost without consuming the separate drain ceiling."""
        row = self._current(ref, initial_mp)
        cost = max(0, int(requested))
        if row is None or row.current < cost:
            return False
        row.current -= cost
        return True

    def drain_mana(self, ref, initial_mp, requested):
        """Debit once and return the actual drain, including the shared life cap."""
        row = self._current(ref, initial_mp)
        if row is None:
            return 0
        amount = min(max(0, int(requested)), row.current,
                     max(0, NPC_DRAIN_LIMIT - row.drained))
        row.current -= amount
        row.drained += amount
        return amount

    def forget(self, uid, *_):
        for ref in tuple(self._mana):
            if ref.uid == uid:
                del self._mana[ref]

    def prune(self, *_):
        for ref in tuple(self._mana):
            target = self.entities.resolve(ref)
            if target is None or not target.alive:
                del self._mana[ref]

    def clear(self):
        self._mana.clear()


def install(world):
    """Obtain the shared owner; safe for several optional consumers at startup."""
    if EXTENSION_KEY not in world.extensions:
        owner = NpcResources(world.entities)
        world.extensions[EXTENSION_KEY] = owner
        world.events.add(EXTENSION_KEY, 'npc_died', owner.forget)
        world.events.add(EXTENSION_KEY, 'tick', owner.prune)
        world.events.add(EXTENSION_KEY, 'close', owner.clear)
    return world.extensions[EXTENSION_KEY]
