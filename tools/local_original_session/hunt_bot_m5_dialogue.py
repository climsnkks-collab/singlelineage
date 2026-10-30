"""M5 original dialogue/menu packet flow on a fresh, retained LOCAL save.

No original game process or client-local HTML navigation is executed. Reuses
M5 FIRST/login/select/world, movement, inventory operations and finally/close.
"""
from __future__ import annotations

import asyncio
from collections import Counter
import json
from pathlib import Path
import tempfile

from tools.local_original_session import hunt_bot as hb
from tools.local_original_session import hunt_bot_m5 as m5
from tools.local_original_session import hunt_bot_play_matrix as matrix


class DialogueScenario(m5.M5Scenario):
    def __init__(self, args, directory):
        super().__init__(args, directory)
        self.map_start = (4, 33438, 32796)
        self.town_id = 'giran'

    async def click_dialogue(self, npc_id, expected):
        self.stage = f'dialogue_{npc_id}'
        npc = await self.approach(npc_id)
        batch = await self.bot.peer.request(0x4e43, hb.uint(1, npc.uid),
            check=lambda frames: hb.find(frames, 0x4e44), label='M5_DIALOGUE_CLICK')
        menu = hb.find(batch, 0x4e44).values
        self.record(f'original_menu_{npc_id}', hb.scalar(menu, 2) == expected.encode()
            and hb.scalar(menu, 1) & 0xffffffff == npc.uid,
            npc_id=npc_id, uid=npc.uid, stem=expected,
            scope='actual 4E43 decoder/router to 4E44 current original resource stem; native rendering/input unverified')
        return menu

    async def refuse_unimplemented(self, npc_id, stem, action):
        menu = await self.click_dialogue(npc_id, stem)
        position, saved = self.position_snapshot(), self.store.restore(self.bot.self_uid)
        previous = list(self.broker._world_handler_errors)
        batch = await self.barrier(0x4ed4, hb.uint(1, hb.scalar(menu, 1))
            + hb.pb.encode_bytes(2, action.encode()) + hb.uint(4, 0) + hb.uint(5, 0),
            label='M5_UNIMPLEMENTED_' + action.upper())
        self.record(f'unsupported_{npc_id}_{action}_has_no_service_effect',
            self.broker._world_handler_errors == previous + ['M5_DIALOGUE_ACTION_NOT_READY']
            and saved == self.store.restore(self.bot.self_uid) and position == self.position_snapshot()
            and hb.find(batch, 0x4e44) is None,
            action=action, errors=self.broker._world_handler_errors,
            scope='expected backend refusal; no fabricated quest completion or paid teleport')

    def binding_counts(self):
        from tools.local_original_session import world_town
        from tools.local_original_session.world_shop_menu import MenuSource
        keys=set(world_town.load_town(Path(__file__).resolve().parent/'data/m5').placements)
        sources=self.broker._world_handler_bindings.sources
        roles=Counter(('shop' if isinstance(source,MenuSource) else source.service_kind or 'external')
            for key,source in sources.items() if key in keys)
        prepared_ids={key[0] for key in sources if key in keys}
        live_ids=set()
        live=Counter()
        for ref,npc,_ in self.broker._world.town._owned.values():
            if npc.key not in keys or npc.key not in sources:continue
            live_ids.add(npc.npc_id)
            source=sources[npc.key]
            live['shop' if isinstance(source,MenuSource) else source.service_kind or 'external']+=1
        return dict(prepared_npc_count=len(prepared_ids),prepared_placements=dict(roles),
            live_npc_count=len(live_ids),live_actors=dict(live),
            boundary='M5 source placements only; count0, blocked centres and unavailable visuals remain excluded; not original screen verification')

    async def m5(self):
        self.fixture_notes.append(dict(pre_login_saved_position=self.map_start,
            scope='fresh Lv5 test_knight Giran development fixture; no original/user save or client execution'))
        self.binding_summary=self.binding_counts()
        await self.click_dialogue(70028,'randal1')
        await self.click_dialogue(60008,'nodim')
        await self.town_warehouse(60008)
        await self.click_dialogue(70641,'herbert1')
        await self.click_dialogue(70034,'vincent1')
        self.record('client_local_guide_links_preserved_as_local',True,
            links={'herbert1':'herbert2','vincent1':'vincent2'},
            scope='retained original link metadata only; link is client-local and issues no server packet; screen transition UNRUN')
        await self.teleport(50036,'giran-oren','oren')
        await self.refuse_unimplemented(70751,'brad1','queststart')
        await self.teleport(50051,'oren-giran','giran')
        await self.teleport(50036,'giran-kent','kent')
        await self.teleport(50020,'kent-gludin','gludin')
        await self.teleport(50024,'gludin-woods','windawood')
        await self.click_dialogue(70070,'inn')
        self.record('only_expected_unimplemented_action_refusal',
            self.broker._world_handler_errors == ['M5_DIALOGUE_ACTION_NOT_READY']
            and not any(value for key,value in self.error_codes().items()
                        if key != '_world_handler_errors'),errors=self.error_codes())


def parser():
    result=m5.parser()
    result.description=__doc__
    return result


async def run(args):
    root=Path(__file__).resolve().parents[2]/'work/local_original_session/runs'
    directory=Path(tempfile.mkdtemp(prefix='m5-dialogue-bot-',dir=root))
    scene=DialogueScenario(args,directory)
    with matrix.environment(SL_EXPERIMENT_MAP=2,SL_EXPERIMENT_M5=1,
            SL_EXPERIMENT_SHOP=1,SL_EXPERIMENT_WAREHOUSE=1,
            SL_WORLD_TOWN_CANDIDATES='',SL_COMPANION=0,SL_SPELL_EXP=0,
            SL_COMPANION_PET_UI=0,SL_COMPANION_REVIVE_EXP=0):
        result=await scene.run_matrix()
    result['dialogue_bindings']=getattr(scene,'binding_summary',None)
    result['native_scope']='Original process, rendering, clicks and client-local link transitions UNRUN'
    (directory/'result.json').write_text(json.dumps(matrix.safe(result),ensure_ascii=False,indent=2),encoding='utf-8')
    return result


def main(argv=None):
    result=asyncio.run(run(parser().parse_args(argv)))
    print(json.dumps({key:result[key] for key in ('status','directory','failure','gaps','requests','cleanup_complete','dialogue_bindings')},ensure_ascii=False,indent=2))
    return 0 if result['status']=='PASS' else 1


if __name__=='__main__':
    raise SystemExit(main())
