"""Synthetic protocol and owned ephemeral loopback only; never game port12000."""
import asyncio
import contextlib
import io
import json
from pathlib import Path
import socket
import struct
import tempfile
import unittest
from unittest.mock import patch

from . import cli,counts
from .codecs import ClientPlaintextDecoder,FrameError,ServerPlaintextDecoder
from .counts import CountRow,counts_frame,encode_counts,response_opcode_allowed
from .protobuf import encode_bytes,encode_message,encode_uint32,parse_message
from .server import Limits,LoopbackServer,MetadataLog

def client_frame(opcode,payload=b'',sequence=1,mode='present_disabled'):
    unpadded=10+len(payload)
    total=unpadded if mode=='null' else ((unpadded+1)&~3)+2
    declared=total-2 if mode=='null' else total
    return struct.pack('<HIHH',declared,sequence,opcode,len(payload))+payload+b'\xa5'*(total-unpadded)

def version_payload(build=26092901):
    return encode_message([encode_uint32(1,52),encode_uint32(2,949),encode_uint32(3,7),
        encode_uint32(4,build),encode_bytes(6,b'SYNTHETIC_PRIVATE_VALUE_NO_LOG')])

async def read_response(reader):
    header=await asyncio.wait_for(reader.readexactly(2),2)
    length=struct.unpack('<H',header)[0]
    return header+await asyncio.wait_for(reader.readexactly(length-2),2)

class CodecTests(unittest.TestCase):
    def test_both_layouts_fragmentation_and_multiple_frames(self):
        for mode in ('null','present_disabled'):
            wire=client_frame(0x4e34,version_payload(),mode=mode)+client_frame(0x4f3d,sequence=2,mode=mode)
            decoder=ClientPlaintextDecoder(cipher_pointer=mode);frames=[]
            for byte in wire:frames.extend(decoder.feed(bytes((byte,))))
            decoder.finish()
            self.assertEqual([row.opcode for row in frames],[0x4e34,0x4f3d])
            second=ClientPlaintextDecoder(cipher_pointer=mode)
            self.assertEqual([row.opcode for row in second.feed(wire)],[0x4e34,0x4f3d])
            second.finish()

    def test_exact_empty_ack_and_initialized_nested_schema(self):
        self.assertEqual(counts_frame(),b'\x06\x00\x3e\x4f\x00\x00')
        self.assertTrue(response_opcode_allowed(counts_frame()))
        payload=encode_counts((CountRow(10000,-1,-2,True),))
        with parse_message(payload,schema={1:2}) as outer:
            nested=outer.occurrences(1)[0].value
            with parse_message(nested,schema={1:0,2:0,3:0,4:0}) as row:
                self.assertEqual([field.number for field in row.fields],[1,2,3,4])
                self.assertEqual(row.occurrences(2)[0].value,(1<<64)-1)
        self.assertFalse(response_opcode_allowed(struct.pack('<HH',len(payload)+6,0x4f3e)+payload+b'\0\0'))

    def test_bounds_and_unsupported_cipher_reject(self):
        with self.assertRaises(ValueError):ClientPlaintextDecoder(cipher_pointer='enabled')
        with self.assertRaises(FrameError):ClientPlaintextDecoder().feed(b'\x01\x00')
        decoder=ServerPlaintextDecoder();decoder.feed(b'\x06\x00\x3e')
        with self.assertRaises(FrameError):decoder.finish()

    def test_default_plan_opens_no_socket_and_private_log_filter(self):
        output=io.StringIO()
        with patch.object(socket,'socket',side_effect=AssertionError('Plan must not bind')),contextlib.redirect_stdout(output):
            self.assertEqual(cli.main([]),0)
        self.assertFalse(json.loads(output.getvalue())['socket_opened'])
        safe=cli.safe_event({'event':'protobuf_message','opcode':0x4e34,
            'payload':b'PRIVATE','sequence':42,'field_number':6,'nonce':'PRIVATE'})
        self.assertEqual(safe,{'event':'protobuf_message','opcode':0x4e34,'parsed_known':True})

    def test_contract_binding_tamper_rejects(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)
            for name in ('counts-contract.json','counts-proof.json'):
                (path/name).write_bytes((counts.HERE/name).read_bytes())
            (path/'counts-proof.json').write_text('{}',encoding='utf-8')
            with patch.object(counts,'HERE',path):
                with self.assertRaisesRegex(ValueError,'counts_proof_binding'):
                    counts.CountsPlan.from_contract({})

class TransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.events=[]
        self.server=LoopbackServer(host='127.0.0.1',port=0,
            decoder_factory=lambda:ClientPlaintextDecoder(cipher_pointer='present_disabled'),
            mode='reviewed_counts',initial_plan=cli.load_plan(),
            limits=Limits(max_connections=1,idle_timeout=2,session_timeout=5),
            log=MetadataLog(sink=lambda row:self.events.append(cli.safe_event(row))))
        await self.server.start()
        self.assertNotEqual(self.server.bound_port,12000)
        self.reader,self.writer=await asyncio.open_connection('127.0.0.1',self.server.bound_port)
        self.key=await read_response(self.reader)
        self.assertEqual(struct.unpack_from('<H',self.key,2)[0],0x4e20)

    async def asyncTearDown(self):
        self.writer.close()
        await self.writer.wait_closed()
        await self.server.close()

    async def handshake(self,coalesced=False):
        version=client_frame(0x4e34,version_payload())
        request=client_frame(0x4f3d,sequence=2)
        if coalesced:
            self.writer.write(version+request);await self.writer.drain()
        else:
            for byte in version:
                self.writer.write(bytes((byte,)));await self.writer.drain()
        reply=await read_response(self.reader)
        self.assertEqual(reply,b'\x08\x00\x35\x4e\x08\x00\x00\x00')
        if not coalesced:self.writer.write(request);await self.writer.drain()
        self.assertEqual(await read_response(self.reader),counts_frame())

    async def test_real_owned_fragmented_roundtrip_and_no_private_log(self):
        await self.handshake()
        self.assertTrue(any(row and row['event']=='counts_ack_sent' for row in self.events))
        self.assertNotIn('SYNTHETIC_PRIVATE_VALUE_NO_LOG',json.dumps(self.events))
        self.assertFalse(any(row and 'processed' in row for row in self.events))

    async def test_coalesced_requests_then_unknown_opcode_closes_without_reply(self):
        await self.handshake(coalesced=True)
        self.writer.write(client_frame(0x4e28,b'',sequence=3));await self.writer.drain()
        self.assertEqual(await asyncio.wait_for(self.reader.read(1),2),b'')
        self.assertTrue(any(row and row['event']=='post_counts_c2s_observed' and row['opcode']==0x4e28 for row in self.events))

    async def test_duplicate_counts_no_second_ack(self):
        await self.handshake()
        self.writer.write(client_frame(0x4f3d,sequence=3));await self.writer.drain()
        self.assertEqual(await asyncio.wait_for(self.reader.read(1),2),b'')

    async def test_wrong_build_refuses_before_version_reply(self):
        self.writer.write(client_frame(0x4e34,version_payload(1)));await self.writer.drain()
        self.assertEqual(await asyncio.wait_for(self.reader.read(1),2),b'')
        self.assertFalse(any(row and row['event']=='counts_ack_sent' for row in self.events))

    async def test_nonempty_counts_request_refuses_without_ack(self):
        self.writer.write(client_frame(0x4e34,version_payload()));await self.writer.drain()
        await read_response(self.reader)
        self.writer.write(client_frame(0x4f3d,encode_uint32(1,1),sequence=2));await self.writer.drain()
        self.assertEqual(await asyncio.wait_for(self.reader.read(1),2),b'')
        self.assertFalse(any(row and row['event']=='counts_ack_sent' for row in self.events))

    async def test_occupied_owned_port_refuses_and_original_listener_survives(self):
        other=LoopbackServer(host='127.0.0.1',port=self.server.bound_port)
        with self.assertRaises(OSError):await other.start()
        self.assertIsNone(other._server)
        self.assertIsNotNone(self.server._server)
        if hasattr(socket,'SO_EXCLUSIVEADDRUSE'):
            self.assertEqual(self.server._server.sockets[0].getsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE),1)
        await self.handshake()

    async def test_second_connection_rejected_without_extra_key(self):
        reader,writer=await asyncio.open_connection('127.0.0.1',self.server.bound_port)
        try:self.assertEqual(await asyncio.wait_for(reader.read(1),2),b'')
        finally:writer.close();await writer.wait_closed()

if __name__=='__main__':unittest.main()
