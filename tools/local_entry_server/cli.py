"""Default Plan; explicit --run owns only fixed IPv4 loopback port12000."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import sys

from .codecs import ClientPlaintextDecoder
from .counts import CountsPlan
from .server import Limits, LoopbackServer, MetadataLog

HERE=Path(__file__).resolve().parent
BASE_CONTRACT_SHA='ec2414490536bf7fbe24dccbdbcd535f99f7657a8d2e6bc8a5bcf81ec00bb7bb'
TARGET_SHA='9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af'
PUBLIC_EVENTS=frozenset(('listening','connected','reply_sent','counts_ack_sent',
    'frame_decoded','session_transition','post_counts_c2s_observed','protobuf_message',
    'disconnected','connection_rejected'))

def load_plan():
    raw=(HERE/'contract.json').read_bytes()
    if len(raw)>65536 or hashlib.sha256(raw).hexdigest()!=BASE_CONTRACT_SHA:
        raise ValueError('base_contract_binding')
    return CountsPlan.from_contract(json.loads(raw))

def safe_event(row):
    """Never export protobuf field values, strings, sequences, peers or secrets."""
    if row['event'] not in PUBLIC_EVENTS:return None
    safe={'event':row['event']}
    if 'opcode' in row:safe['opcode']=row['opcode']
    if 'wire_bytes' in row:safe['frame_size']=row['wire_bytes']
    elif 'reply_bytes' in row and row['event'] in ('reply_sent','counts_ack_sent'):
        safe['frame_size']=row['reply_bytes']
    if 'stage' in row:safe['status']=row['stage']
    elif 'reason' in row:safe['status']=row['reason']
    if row['event']=='protobuf_message':safe['parsed_known']=True
    return safe

async def run_fixed(plan):
    done=asyncio.Event()
    outcome={'counts_ack_written':False,'close_reason':None}
    def emit(row):
        safe=safe_event(row)
        if safe:print(json.dumps(safe,separators=(',',':')),flush=True)
        if row['event']=='counts_ack_sent':outcome['counts_ack_written']=True
        if row['event']=='disconnected':
            outcome['close_reason']=row.get('reason')
            done.set()
    server=LoopbackServer(host='127.0.0.1',port=12000,
        decoder_factory=lambda:ClientPlaintextDecoder(cipher_pointer='present_disabled'),
        mode='reviewed_counts',initial_plan=plan,
        limits=Limits(max_connections=1,idle_timeout=15,session_timeout=120),
        log=MetadataLog(sink=emit))
    try:
        await server.start()
        print(json.dumps({'status':'LISTENING','endpoint':'127.0.0.1:12000',
            'exclusive_bind':True,'character_entry_proven':False}),flush=True)
        try:await asyncio.wait_for(done.wait(),300)
        except TimeoutError:print(json.dumps({'status':'STOPPED','reason':'listener_lifetime_bound'}),flush=True)
    finally:await server.close()
    print(json.dumps({'status':'SUBSET_OBSERVED' if outcome['counts_ack_written'] else 'INCOMPLETE_PROTOCOL',
        **outcome,'ack_processing_proven':False,'character_entry_proven':False}),flush=True)
    return 0 if outcome['counts_ack_written'] and outcome['close_reason'] in ('eof','idle_timeout','session_timeout') else 2

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true',help='Run the reviewed empty-counts profile on fixed exclusive loopback12000.')
    args=parser.parse_args(argv)
    try:
        plan=load_plan()
        if not args.run:
            print(json.dumps({'status':'PLAN','bind':'127.0.0.1:12000','target_sha256':TARGET_SHA,
                'target_version':'26.09.29.2001','outbound_opcodes':['0x4e20','0x4e35','0x4f3e'],
                'cipher_profile':'present_disabled','resource_map13':'omitted_unavailable',
                'game_or_sdk_started':False,'socket_opened':False,'character_entry_proven':False}),flush=True)
            return 0
        return asyncio.run(run_fixed(plan))
    except OSError:
        print(json.dumps({'status':'REFUSED','reason':'fixed_endpoint_unavailable_no_retry_or_foreign_process_control'}),flush=True)
        return 2
    except (ValueError,TypeError,KeyError):
        print(json.dumps({'status':'REFUSED','reason':'reviewed_contract_or_mode_invalid'}),flush=True)
        return 2
    except KeyboardInterrupt:
        print(json.dumps({'status':'STOPPED','reason':'operator_interrupt'}),flush=True)
        return 0

if __name__=='__main__':sys.exit(main())
