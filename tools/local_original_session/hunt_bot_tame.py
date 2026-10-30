"""Focused LOCAL food-taming lifecycle using the existing owned socket fixture.

FIRST/login/select/world, attacks, food, collar, follow and pet-window requests
all pass through the real socket decoder/router. Fresh declared startup resources
and retained saves are inherited from hunt_bot_pet; native UI remains unverified.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

from tools.local_original_session import hunt_bot as hb
from tools.local_original_session import hunt_bot_pet as hp


class TameScenario(hp.PetScenario):
    async def tame(self):
        self.stage = 'natural_wild_tame_' + self.args.species
        from tools.local_original_session.world_pet import load_pets
        species = load_pets().species[self.args.species]
        # Restrict only the bot's choice of an actually received wild actor.
        # The existing attack/feed flow supplies real live HP and current UIDs.
        await self.damage_wild_for_taming(
            time.monotonic() + self.args.navigation_timeout,
            set(species.classic_candidates))
        self.record('requested_species_tamed',
            self.member.equipment['_pet']['species'] == self.args.species,
            requested_species=self.args.species,
            actual_species=self.member.equipment['_pet']['species'])

    async def all(self):
        await self.tame()
        await self.collar()
        self.stage = 'tamed_pet_follow'
        # Hold through a real window command, walk away through ordinary movement,
        # then request follow. A received pet movement is the completion evidence.
        await self.command(4)
        start, actor_uid = self.member_position(), self.actor.ref.uid
        await self.owner_separate()
        marker = await self.command(2)
        await self.wait_current('tamed_pet_follow_received', lambda:
            self.member_position() != start and
            bool(self.frames(marker, 0x4e2c, **{'1': actor_uid})),
            timeout=15, member_required=True, marker=marker)
        await self.wait_current('tamed_pet_reached_owner', lambda:
            hb.distance(self.bot.position, self.member_position()) <= 2,
            timeout=15, member_required=True, marker=marker)
        self.record('tamed_pet_follows_owner_with_received_motion',
            self.member.movement_mode == 'FOLLOW' and
            self.member.combat_mode == 'ASSIST' and
            bool(self.frames(marker, 0x4e2c, **{'1': actor_uid})),
            actor_uid=actor_uid, start=start, finish=self.member_position(),
            owner_position=self.bot.position)
        self.stage = 'tamed_pet_window_and_saved_reconnect'
        await self.pet_status()
        await self.reconnect()


def parser():
    result = hp.parser()
    result.description = __doc__
    next(action for action in result._actions if action.dest == 'scenario').choices = ('all',)
    result.add_argument('--species', choices=('wolf', 'shepherd', 'doberman'), default='wolf',
                        help='choose a current LOCAL runtime wild species without altering its spawn or HP')
    return result


async def run(args):
    root = Path(__file__).resolve().parents[2] / 'work/local_original_session/runs'
    root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='hunt-tame-', dir=root))
    names = ('hunt_bot_tame.py', 'hunt_bot_pet.py', 'hunt_bot.py',
        'hunt_bot_scenarios.py', 'hunt_bot_companion.py', 'world_pet.py',
        'world_feature_pet.py', 'world_handlers.py', 'world_companion.py',
        'world_feature_companion.py', 'companion_ai.py', 'npc_ai.py',
        'world_visibility.py', 'world_combat.py', 'world_reward.py',
        'world_bridge.py', 'world_persist.py', 'inventory.py',
        'inventory_store.py', 'equipment_store.py', 'broker.py',
        'data/m1/pets.json', 'data/m1/pet_runtime.json')
    def sources():
        return {name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
                for name in names if (Path(__file__).parent / name).exists()}
    started = sources()
    with hp.test_environment(companion=args.with_companion):
        scenario = TameScenario(args, directory)
        result = await scenario.run()
    result.update(scope='owned fresh test profile; real FIRST/login/select/world/socket decoder/router; '
        'LOCAL food-taming policy and Classic candidate wire; native input/rendering unverified',
        fixture=scenario.fixture, pet_epochs=scenario.pet_epochs,
        test_configuration=dict(species=args.species, with_companion=args.with_companion,
            time_scale=os.environ.get('SL_TEST_TIME_SCALE', '1'),
            port_base=os.environ.get('SL_TEST_PORT_BASE', '12000'),
            listener_ports=hp.test_ports.listener_ports()),
        navigation_failure=scenario.navigation_failure,
        broker_exception_observations=scenario.broker_exception_observations,
        source_sha256_start=started, source_sha256=sources())
    result['source_changes_during_run'] = [name for name in names
        if started.get(name) != result['source_sha256'].get(name)]
    (directory / 'summary.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    return result


def main(argv=None):
    cli = parser()
    args = cli.parse_args(argv)
    if args.potion_threshold > 1:
        cli.error('--potion-threshold must be in (0, 1]')
    result = asyncio.run(run(args))
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result['status'] == 'SUCCESS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
