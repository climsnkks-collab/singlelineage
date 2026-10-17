"""Plan default. Genuine preserved original pack, fixed local bootstrap subset."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import argparse,asyncio,ctypes as C,hashlib,json,os,socket,time
HERE=Path(__file__).absolute().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE));sys.path.insert(0,str(ROOT))
import session_adapter as adapter
from tools.local_entry_server.cli import load_plan,safe_event
from tools.local_entry_server.counts import CountsSession
from tools.local_entry_server.handshake import Stage,HandshakeError
from tools.local_entry_server.codecs import ClientPlaintextDecoder,FrameError
from tools.local_entry_server.server import Session,MetadataLog
SOURCES=('broker.py','session_adapter.py','tests.py')
PROTOCOL=ROOT/'tools/local_entry_server'
PROTOCOL_FILES=('cli.py','counts.py','handshake.py','codecs.py','protobuf.py','server.py','contract.json','counts-contract.json','counts-proof.json')
REVIEW=HERE/'root-review.json'
SOURCE_CONTRACT=ROOT/'work/local_bootstrap_completion/source-contract.json'
CLIENT=ROOT/'work/standalone_boot/current-unmodified-clone/LC.exe'
CLIENT_SHA='374691bc3b302adae799398747788dac22d4d186a2c4042f596b013843c0f1c4'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def own_hashes():return {n:sha((HERE/n).read_bytes())for n in SOURCES}
def protocol_hashes():return {n:sha((PROTOCOL/n).read_bytes())for n in PROTOCOL_FILES}
def approved():
    adapter.require(REVIEW.stat().st_size<=32768,'root_review_bound');row=json.loads(REVIEW.read_bytes())
    required={'schema':'lc-preserved-original-resource-bootstrap-review-v1','reviewed':True,'allow_run':True,
        'source_sha256':own_hashes(),'proof_source_sha256':adapter.proof_hashes(),'protocol_sha256':protocol_hashes(),
        'source_contract_sha256':sha(SOURCE_CONTRACT.read_bytes()),'client_sha256':CLIENT_SHA,
        'preserved_archive_sha256':adapter.ARCHIVE_SHA,'selected_authenticated_resources':38,
        'endpoint':{'host':'127.0.0.1','port':12000},'max_clients':1,'max_c2s_frames':2,'max_s2c_frames':3,
        'key_mode':'PLAIN_USER_AUTHORIZED','plaintext_key_storage_user_authorized':True,
        'key_or_packet_values_logged':False,'ZIP_or_manifest_writes':False,'SDK_auth_or_ready_mutation':False}
    adapter.require(row==required,'fixed_preserved_broker_review_required')
    adapter.require(sha(CLIENT.read_bytes())==CLIENT_SHA,'exact_route_rootmount_client_required');return row
class ReadPins:
    """Fixed input read pins. Key file is read but never copied to output or argv."""
    def __enter__(self):
        adapter.require(os.name=='nt','Windows_fixed_broker_required');from ctypes import wintypes as W
        self.k=C.WinDLL('kernel32',use_last_error=True);self.handles=[]
        self.k.CreateFileW.argtypes=(W.LPCWSTR,W.DWORD,W.DWORD,C.c_void_p,W.DWORD,W.DWORD,W.HANDLE);self.k.CreateFileW.restype=W.HANDLE
        self.k.CloseHandle.argtypes=(W.HANDLE,);self.k.GetFileInformationByHandle.argtypes=(W.HANDLE,C.c_void_p)
        self.k.GetFinalPathNameByHandleW.argtypes=(W.HANDLE,W.LPWSTR,W.DWORD,W.DWORD);self.k.GetFinalPathNameByHandleW.restype=W.DWORD
        paths=[HERE/n for n in SOURCES]+[PROTOCOL/n for n in PROTOCOL_FILES]+[adapter.PROOF/n for n in adapter.PROOF_SOURCES]
        paths += [adapter.PRODUCER/n for n in adapter.PRODUCER_PINS]+[REVIEW,SOURCE_CONTRACT,CLIENT,adapter.KEY,adapter.METADATA]
        paths += [adapter.PACK/n for n in ('manifest.json','manifest.sig','resource.key','rc.dat','rc.sig','data_0.lcx')]
        seen=set()
        try:
            for file in paths:
                for path in reversed((file,*file.parents)):
                    if str(path).casefold()in seen:continue
                    seen.add(str(path).casefold());info=path.lstat()
                    adapter.require(not path.is_symlink()and not getattr(info,'st_file_attributes',0)&0x400,'source_reparse_refused')
                    directory=path.is_dir();h=self.k.CreateFileW(str(path),0 if directory else 0x80000000,3 if directory else 1,None,3,0x2200000 if directory else 0x200080,None)
                    adapter.require(h!=C.c_void_p(-1).value,'fixed_read_pin_required');self.handles.append(h)
                    buffer=C.create_string_buffer(52);adapter.require(self.k.GetFileInformationByHandle(h,buffer),'source_native_info')
                    attrs=int.from_bytes(buffer.raw[:4],'little');adapter.require(not attrs&0x400 and bool(attrs&0x10)==directory,'source_native_type')
                    if not directory:adapter.require(int.from_bytes(buffer.raw[40:44],'little')==1,'source_multiple_links')
                    final=C.create_unicode_buffer(32768);n=self.k.GetFinalPathNameByHandleW(h,final,32768,0)
                    adapter.require(0<n<32768 and final.value.removeprefix('\\\\?\\').casefold()==str(path).casefold(),'native_canonical_path')
            return self
        except BaseException:self.__exit__();raise
    def __exit__(self,*_):
        for h in self.handles:self.k.CloseHandle(h)
        self.handles=[]
class PreservedConversation(CountsSession):
    def __init__(self,plan,state,log,resource):super().__init__(plan,state,log);self.resource=resource;self.frames=0
    async def received(self,frame):
        self.frames+=1;adapter.require(self.frames<=2,'two_client_frames_only')
        first=self.stage==Stage.WAIT_VERSION and frame.opcode==0x4e34
        replies=await super().received(frame)
        if first and self.stage==Stage.VERSION_REPLIED:
            adapter.require(len(replies)==1,'exact_version_reply');return (self.resource.version_frame(),)
        return replies
async def serve_authenticated_session(resource,plan,event=print):
    """Internal Root-only serving; no game start, authentication relay or ZIP writes."""
    done=asyncio.Event();accepted=False;tasks=set();outcome={'counts_ack_sent':False,'close_reason':None}
    def emit(row):
        safe=safe_event(row)
        if safe:event(json.dumps(safe,separators=(',',':')))
    async def connection(reader,writer):
        nonlocal accepted
        if accepted:writer.close();return
        accepted=True;decoder=ClientPlaintextDecoder(cipher_pointer='present_disabled')
        conv=PreservedConversation(plan,Session(1,'reviewed_counts'),MetadataLog(sink=emit),resource)
        deadline=time.monotonic()+120;received=sent=0;reason='eof'
        async def send(replies):
            nonlocal sent
            for wire in replies:
                sent+=1;adapter.require(sent<=3 and type(wire)in(bytes,bytearray)and 6<=len(wire)<=65535,'reply_shape_bound')
                opcode=int.from_bytes(wire[2:4],'little');adapter.require(opcode in(0x4e20,0x4e35,0x4f3e),'reply_opcode_whitelist')
                try:writer.write(wire);await asyncio.wait_for(writer.drain(),2)
                finally:adapter.wipe(wire)
                emit({'event':'reply_sent','opcode':opcode,'reply_bytes':len(wire)})
                if opcode==0x4f3e:outcome['counts_ack_sent']=True
        try:
            emit({'event':'connected'});await send(await conv.opened())
            while time.monotonic()<deadline:
                try:raw=await asyncio.wait_for(reader.read(4096),min(15,max(.001,deadline-time.monotonic())))
                except TimeoutError:reason='idle_timeout';break
                if not raw:decoder.finish();break
                received+=len(raw);adapter.require(received<=65536,'input_byte_bound')
                for frame in decoder.feed(raw):
                    emit({'event':'frame_decoded','opcode':frame.opcode,'wire_bytes':frame.wire_length})
                    await send(await conv.received(frame))
            else:reason='session_timeout'
        except (ValueError,HandshakeError,FrameError):reason='source_or_protocol_refused'
        except (OSError,TimeoutError):reason='io_failed_or_timeout'
        finally:
            writer.close();outcome['close_reason']=reason;emit({'event':'disconnected','reason':reason});done.set()
            try:await asyncio.wait_for(writer.wait_closed(),2)
            except (OSError,TimeoutError,asyncio.CancelledError):pass
    def accepted_client(reader,writer):
        task=asyncio.create_task(connection(reader,writer));tasks.add(task);task.add_done_callback(tasks.discard)
    listener=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    try:
        adapter.require(hasattr(socket,'SO_EXCLUSIVEADDRUSE'),'exclusive_windows_endpoint_required')
        listener.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        listener.bind(('127.0.0.1',12000));listener.listen(1);listener.setblocking(False)
        server=await asyncio.start_server(accepted_client,sock=listener,reuse_address=False,reuse_port=False,limit=8192)
        event(json.dumps({'status':'LISTENING','endpoint':'127.0.0.1:12000','selected_authenticated_resources':38,
            'key_mode':'PLAIN_USER_AUTHORIZED','ZIP_or_manifest_writes':False}))
        async with server:
            try:await asyncio.wait_for(done.wait(),300)
            except TimeoutError:outcome['close_reason']='accept_lifetime_bound'
    finally:
        listener.close()
        for task in tuple(tasks):task.cancel()
        if tasks:await asyncio.gather(*tuple(tasks),return_exceptions=True)
    return outcome
def run_actual():
    with ReadPins():
        approved();plan=load_plan()
        with adapter.load_preserved_session()as resource:
            resource.verify_preserved_pack()
            print(json.dumps({'status':'PRESERVED_PACK_AUTH38','selected':38,'key_mode':'PLAIN_USER_AUTHORIZED',
                'key_or_packet_values_logged':False,'ZIP_or_manifest_writes':False}),flush=True)
            result=asyncio.run(serve_authenticated_session(resource,plan,lambda text:print(text,flush=True)))
            print(json.dumps({'status':'SUBSET_OBSERVED'if result['counts_ack_sent']else'INCOMPLETE_PROTOCOL',**result,
                'ACK_processing_proven':False,'resource_consumer_ready_proven':False,'character_entry_proven':False}),flush=True)
            return 0 if result['counts_ack_sent']else 2
def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',action='store_true');args=parser.parse_args(argv)
    try:
        if not args.run:
            print(json.dumps({'status':'PLAN','endpoint':'127.0.0.1:12000','key_mode':'PLAIN_USER_AUTHORIZED',
                'source_sha256':own_hashes(),'selected_resources':38,'ZIP_or_manifest_writes':False,
                'socket_or_key_load_performed':False,'actual_game_entry':False}));return 0
        return run_actual()
    except Exception as error:
        print(json.dumps({'status':'REFUSED','reason_type':type(error).__name__,'game_start_or_UAC':False,
            'key_or_packet_values_logged':False}),flush=True);return 2
if __name__=='__main__':raise SystemExit(main())
