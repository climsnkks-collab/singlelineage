"""Synthetic secret frames and mocked protocol only; no socket or real key load."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import asyncio,base64,contextlib,io,json,struct,unittest
from unittest.mock import patch
import broker as b
import session_adapter as a
from tools.local_entry_server.codecs import Frame
from tools.local_entry_server.protobuf import encode_message,encode_uint32
class OriginalFixture:
    source_archive={'name':'data_0.lcx','sha256':a.ARCHIVE_SHA,'size':a.ARCHIVE_SIZE}
    closed=False;calls=0
    def verify_preserved_pack(self):
        if self.closed:raise ValueError('closed_fixture')
        return {'authenticated':38}
    def version_frame(self):
        self.calls+=1
        # Synthetic 32-byte material, never read from the game's key file.
        encoded=base64.b64encode(bytes(range(32)))
        payload=b'\x08\0\x6a\x44\x0a\x12CONTENT_MASTER_KEY\x12\x2c'+encoded
        return bytearray(struct.pack('<HH',len(payload)+6,0x4e35)+payload+b'\0\0')
    def close(self):self.closed=True
class AdapterTests(unittest.TestCase):
    def test_same_original_pack_verified_before_each_emit_and_wire_is_mutable(self):
        original=OriginalFixture();session=a.Session(original);wire=session.version_frame()
        self.assertEqual(len(wire),76);self.assertIsInstance(wire,bytearray);self.assertEqual(original.calls,1)
        a.wipe(wire);self.assertEqual(wire,bytes(76))
        with self.assertRaises(ValueError):session.version_frame()
        session.close();self.assertTrue(original.closed)
    def test_foreign_archive_and_closed_key_refuse(self):
        original=OriginalFixture();original.source_archive=dict(original.source_archive,sha256='0'*64)
        with self.assertRaises(ValueError):a.Session(original).version_frame()
        original=OriginalFixture();session=a.Session(original);session.close()
        with self.assertRaises(ValueError):session.version_frame()
    def test_default_plan_no_key_socket_or_native_load(self):
        output=io.StringIO()
        with (patch.object(b,'ReadPins',side_effect=AssertionError('no native')),
                patch.object(a,'load_preserved_session',side_effect=AssertionError('no key')),
                patch.object(b.socket,'socket',side_effect=AssertionError('no socket')),
                contextlib.redirect_stdout(output)):
            self.assertEqual(b.main([]),0)
        row=json.loads(output.getvalue());self.assertFalse(row['socket_or_key_load_performed']);self.assertEqual(row['key_mode'],'PLAIN_USER_AUTHORIZED')
    def test_cli_no_generic_key_path_port_or_credentials(self):
        with contextlib.redirect_stderr(io.StringIO()):
            for option in ('--key','--path','--host','--port','--pid','--credentials'):
                with self.assertRaises(SystemExit):b.main([option,'foreign'])
class ConversationTests(unittest.IsolatedAsyncioTestCase):
    def version(self):return Frame(encode_message([encode_uint32(1,52),encode_uint32(2,949),encode_uint32(3,0),encode_uint32(4,26092901)]),0x4e34,30)
    def conversation(self,resource):return b.PreservedConversation(b.load_plan(),b.Session(1,'reviewed_counts'),b.MetadataLog(),resource)
    async def test_key_version_counts_exact_whitelist_then_third_request_refused(self):
        original=OriginalFixture();resource=a.Session(original);conv=self.conversation(resource)
        key=await conv.opened();self.assertEqual(int.from_bytes(key[0][2:4],'little'),0x4e20)
        version=await conv.received(self.version());self.assertEqual(len(version[0]),76);a.wipe(version[0])
        ack=await conv.received(Frame(b'',0x4f3d,10));self.assertEqual(ack[0],struct.pack('<HH',6,0x4f3e)+b'\0\0')
        with self.assertRaises(ValueError):await conv.received(Frame(b'',0x1234,10))
        self.assertEqual(original.calls,1)
    async def test_wrong_version_unknown_or_counts_before_version_never_emit_resource(self):
        for frame in (Frame(b'',0x1234,10),Frame(b'',0x4f3d,10),Frame(b'\x08\x01',0x4e34,12)):
            original=OriginalFixture();conv=self.conversation(a.Session(original));await conv.opened()
            with self.assertRaises(ValueError):await conv.received(frame)
            self.assertEqual(original.calls,0)
    async def test_resource_auth_refusal_never_produces_version(self):
        class Denied:
            def version_frame(self):raise ValueError('preserved_auth_failed')
        conv=self.conversation(Denied());await conv.opened()
        with self.assertRaises(ValueError):await conv.received(self.version())
    async def test_trace_contains_only_metadata_no_secret_frame(self):
        events=[];conv=b.PreservedConversation(b.load_plan(),b.Session(1,'reviewed_counts'),b.MetadataLog(sink=events.append),a.Session(OriginalFixture()))
        await conv.opened();reply=await conv.received(self.version());a.wipe(reply[0])
        exported=json.dumps([b.safe_event(e)for e in events if b.safe_event(e)])
        self.assertNotIn(base64.b64encode(bytes(range(32))).decode(),exported);self.assertNotIn('CONTENT_MASTER_KEY',exported)
if __name__=='__main__':unittest.main()
