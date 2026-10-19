"""REQ96/run102 wire subset; local choices are not original server rules."""
import hashlib
from tools.local_original_session import attack, observe
from tools.local_game_session import session

need = observe.need
SOURCE_PINS = {
    'findings.md': 'a4cfa1ef1f6ec58b6c5c9c9594e5608640f2f749ad31bfba14c7bd27b5941b6b',
    'implementation-conditions.md': '213b7b4ea107d00977bcff8b03a37a8d35958629096f13fecd83cf0525c5a30e',
    'source-evidence.json': '9033940db85d8098bba4fb8b09990fc664746e77ec9e1c3b799929c9d4699823',
    'main-review.json': '4bd03ac8456d4cefcb9e576e4694d91d515eee1d3ccdb4a4277996e8e71a4bf8',
}

def source_ready():
    root = observe.ROOT / 'work/local_server_rea_20261016/run102_own_player_death_recovery'
    for name, expected in SOURCE_PINS.items():
        raw = observe.ordinary(root/name).read_bytes()
        need(0 < len(raw) <= 1048576 and hashlib.sha256(raw).hexdigest() == expected,
             'PLAYER_LIFE_SOURCE_CHANGED')

def u32(value):
    need(type(value) is int and 0 <= value <= 0xffffffff, 'PLAYER_LIFE_UINT32_REQUIRED')
    return value

def frame(opcode, fields):
    body = attack.pb.encode_message(tuple(attack._field(k, v) for k, v in fields))
    return (len(body)+6).to_bytes(2, 'little') + opcode.to_bytes(2, 'little') + body + b'\0\0'

def death(uid):
    need(type(uid) is int and 0 < uid <= 0xffffffffffffffff, 'PLAYER_LIFE_OWN_UID_REQUIRED')
    return frame(0x4e39, ((1, uid), (2, 8)))

def ack(success):
    need(type(success) is bool, 'PLAYER_LIFE_ACK_BOOL_REQUIRED')
    return frame(0x4eed, ((1, int(success)),))

def init(uid, f2, f3):
    need(u32(uid) > 0, 'PLAYER_LIFE_OWN_UID_UINT32_REQUIRED')
    return frame(0x4f16, ((1, uid), (2, u32(f2)), (3, u32(f3)), (4, 0)))

def full_status(fields):
    # HP0 is accepted only here, never by the ordinary positive HP validator.
    need(type(fields[10]) is type(fields[11]) is int
         and 0 <= fields[10] <= fields[11] <= 0x7fffffff and fields[11] > 0,
         'PLAYER_LIFE_NONNEGATIVE_FULL_STATUS_REQUIRED')
    body = session.world.encode_payload(0x4e38, fields)
    need(session.world.decode_payload(0x4e38, body) == dict(fields),
         'PLAYER_LIFE_EXACT_FULL_STATUS_REQUIRED')
    return (len(body)+6).to_bytes(2, 'little')+b'\x38\x4e'+body+b'\0\0'

def dead_request(payload):
    need(type(payload) is bytes and payload == b'', 'PLAYER_LIFE_FIELDLESS_DEAD_REQUEST_REQUIRED')
