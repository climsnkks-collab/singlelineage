"""Only request ownership/order and actual stream dispatch checks; no sockets."""
import asyncio, importlib.util, struct, sys, unittest
from pathlib import Path
from types import SimpleNamespace as NS
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('_game_connection_tests', Path(__file__).with_name('connection.py'))
c = importlib.util.module_from_spec(spec);sys.modules[spec.name] = c;spec.loader.exec_module(c)
s = c.session

def config():
    # Synthetic complete DTO used solely in this test; never runtime defaults.
    row = {n: n for n in range(1, 22)}
    row.update({1: 'synthetic-owned', 2: '', 4: -1, 19: 0xffffffff, 21: (1 << 40) + 9})
    return {'schema': 'lc-owned-local-core-roster-v1', 'realm': 'owned-local',
        'source_provenance': 'explicit_local_game_configuration', 'expected_count': 1,
        'display_slots': 1, 'rows': [{str(n): v for n, v in row.items()}],
        'existing_rows': [], 'mode': 'initial', 'allow_expected_growth': False}

def select_body(reference='synthetic-owned'):
    return s.pb.encode_message([s.pb.encode_bytes(1, reference.encode()),
        s.pb.encode_uint32(2, 7), s.pb.encode_uint32(3, 8)])

class Tests(unittest.TestCase):
    def test_owned_request_updates_storage_and_unknown_values_emit_nothing(self):
        r = s.Registry();connection = object();game = r.register_own(connection, config())
        self.assertEqual(game.opened(), ())
        with self.assertRaises(s.Refused):asyncio.run(game.received(NS(opcode=0x4e28, payload=select_body())))
        replies = game.list_request(source_kind='CS_CHAR_LIST_ENTER_REQ', payload=b'')
        self.assertEqual([s.wire.validate_frame(f).kind for f in replies], ['NUM', 'INFO'])
        self.assertEqual(asyncio.run(game.received(NS(opcode=0x4e28, payload=select_body()))), ())
        self.assertEqual(r.selected['synthetic-owned'].field2, 7)
        r.close(connection);self.assertIn('synthetic-owned', r.selected)
        with self.assertRaises(s.Refused):asyncio.run(game.received(NS(opcode=0x4e28, payload=select_body())))

    def test_missing_dto_foreign_reference_replay_and_unknown_opcode_refused(self):
        cfg = config();del cfg['rows'][0]['4']
        with self.assertRaises(ValueError):s.Registry().register_own(object(), cfg)
        r = s.Registry();game = r.register_own(object(), config())
        game.list_request(source_kind='CS_CHAR_LIST_ENTER_REQ', payload=b'')
        for frame in (NS(opcode=0x4e28, payload=select_body('foreign')),
                      NS(opcode=0x0267, payload=b''), NS(opcode=0x026b, payload=b'')):
            with self.assertRaises(ValueError):asyncio.run(game.received(frame))
        with self.assertRaises(ValueError):s.selection_request(select_body() + s.pb.encode_uint32(2, 2))
        self.assertEqual(r.selected, {})

    def test_third_frame_enters_real_dispatch_instead_of_subset_close(self):
        class Writer:
            def __init__(self):self.output=[]
            def write(self, value):self.output.append(bytes(value))
            async def drain(self):pass
            def close(self):pass
            async def wait_closed(self):pass
        class Reader:
            def __init__(self):self.chunks=[b'synthetic-frames', b'']
            async def read(self, n):return self.chunks.pop(0)
        class Decoder:
            def feed(self, chunk):return [NS(opcode=0x4e34,payload=b'',wire_length=10),
                NS(opcode=0x4f3d,payload=b'',wire_length=10),
                NS(opcode=0x4e28,payload=select_body(),wire_length=30)]
            def finish(self):pass
        class Bootstrap:
            ack_prepared=False
            async def opened(self):return (b'fixed-key',)
            async def received(self, frame):
                if frame.opcode==0x4e34:return(bytearray(struct.pack('<HH',76,0x4e35)+bytes(72)),)
                self.ack_prepared=True;return(b'\x06\0\x3e\x4f\0\0',)
        class Trace:
            def __init__(self):self.endpoints={14000:{}};self.rows=[]
            def emit(self, row):self.rows.append(row)
            @staticmethod
            def validate_timing(row):return row
        async def check():
            w=Writer();r=s.Registry();admitted=[]
            def grant(writer, peer):
                admitted.append(peer['connection_id'])
                g=r.register_own(writer,config())
                # This test supplies an already classified typed LIST request;
                # production numeric list IDs remain deliberately unbound.
                g.list_request(source_kind='CS_CHAR_LIST_ENTER_REQ',payload=b'')
            base=NS(KEY12=b'fixed-key',Trace=Trace);trace=Trace()
            first={'peer':{'connection_id':4},'write_started_monotonic_ns':1}
            first['peer']['accepted_monotonic_ns']=1
            hook=c.connection_handler(base,r,grant_own=grant)
            await hook(Reader(),w,14000,trace,Decoder,lambda _:Bootstrap(),lambda:None,
                       lambda _:None,NS(check=lambda:None),first,lambda _:True)
            self.assertIn('synthetic-owned',r.selected)
            self.assertEqual(admitted,[4])
            self.assertTrue(all(row['allowed']is True for row in trace.rows if row['event']=='owner_admission'))
            self.assertEqual(trace.endpoints[14000]['frames'],3)
            self.assertEqual([int.from_bytes(f[2:4],'little')for f in w.output],[0x4e35,0x4f3e])
        asyncio.run(check())

if __name__=='__main__':unittest.main()
