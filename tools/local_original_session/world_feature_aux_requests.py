"""Native auxiliary requests with deliberately limited LOCAL behavior.

03EB: run164_opcode03eb_worldready/worker/findings.md:7-35 and packet.json:
USER_START_DONE -> 4C99F0 -> 4C9E80 sends required enum f1=0/f2=0,
no f3 strings. Registrar 293A28 binds SC_EXCLUDE_LIST_NOTI to 03EE;
IsInitialized 737000 permits empty rows plus required int32 f2=0 (10 00).
Only that bootstrap gets an empty LOCAL exclusion list. Named mutations have
no backend state implementation and receive no fabricated success.

072E: REQUEST_COVERAGE_MAP.json:13749-13907: CS_BLOOD_PLEDGE_EMBLEM_INFO_REQ,
f1 int32/wire0, f2 uint64/wire0; sender 566EB0 -> send 56736A.
SC_BLOOD_PLEDGE_EMBLEM_INFO_ACK/072F is a naming candidate, not a recovered
response contract. Exact UI trigger, field names and response body are UNKNOWN.
L1J C_Clan.java:35-41 reads a clan ID and returns S_Emblem, whose :38-49
reads a saved emblem file. This supports the semantic inference only: its
legacy wire is not this client's protobuf. 072E is received/logged only.

All evidence paths above are under work/local_server_rea_20261016 or
work/local_original_session/game-core-prep; L1J under
D:/SingleLineageRef/l1j-en-classic/src/l1j/server/server/{client,server}packets.
No persistent exclusion or emblem state, timers or client callbacks are added.
"""
from __future__ import annotations

from tools.local_entry_server import protobuf as pb
from tools.local_original_session.world_bridge import need

EXCLUDE, EXCLUDE_LIST, EMBLEM_INFO = 0x03EB, 0x03EE, 0x072E


def parse_request(opcode, payload):
    """Validate recovered wire shapes; return bounded metadata, never names."""
    schema = {1: 0, 2: 0, 3: 2} if opcode == EXCLUDE else {1: 0, 2: 0}
    need(opcode in (EXCLUDE, EMBLEM_INFO), 'AUX_OPCODE_UNSUPPORTED')
    with pb.parse_message(payload, schema=schema) as parsed:
        fields = {}
        for number in (1, 2):
            entries = parsed.occurrences(number)
            need(len(entries) <= 1, 'AUX_DUPLICATE_SCALAR')
            if entries:
                fields[number] = entries[0].value
        names = parsed.occurrences(3)
        if opcode == EXCLUDE:
            need(set(fields) == {1, 2}, 'EXCLUDE_REQUIRED_ENUMS')
            need(all(value in (0, 1, 2) for value in fields.values()),
                 'EXCLUDE_ENUM_RANGE')
            # Compiled schema and run164 sender establish strings, not opaque
            # account identifiers. Validate without retaining their contents.
            for entry in names:
                bytes(entry.value).decode('utf-8')
        return dict(scalars={str(number): value for number, value in fields.items()},
                    string_count=len(names),
                    string_bytes=sum(entry.value_length for entry in names))


def empty_exclusion_frame():
    body = pb.encode_uint32(2, 0)
    return ((len(body) + 6).to_bytes(2, 'little')
            + EXCLUDE_LIST.to_bytes(2, 'little') + body + b'\0\0')


def _aux_requests_initialize(ctx):
    ctx._aux_request_events = []


async def _aux_requests_request(ctx, writer, row, game, frame, operation_lock):
    if frame.opcode not in (EXCLUDE, EMBLEM_INFO):
        return False
    if not ctx._world_bound(writer) or ctx._world_ready(writer, game) is None:
        return False

    def receive():
        position = ctx.realm.service(writer).snapshot()
        need(ctx.selected_session(writer) is game and ctx.owner_current(writer, row, position),
             'AUX_CURRENT_SELECTED_PC_REQUIRED')
        event = dict(uid=position.uid, opcode=f'{frame.opcode:04X}',
                     payload_bytes=len(frame.payload), status='received', response='none')
        try:
            event.update(parse_request(frame.opcode, frame.payload))
        except (ValueError, pb.WireError, UnicodeError) as error:
            event.update(status='invalid', error=str(error)[:96])
        else:
            bootstrap = (frame.opcode == EXCLUDE and event['scalars'] == {'1': 0, '2': 0}
                         and event['string_count'] == 0)
            event['status'] = ('local_empty_exclusion_list' if bootstrap else
                               'unsupported_exclusion_operation' if frame.opcode == EXCLUDE else
                               'emblem_response_contract_unknown')
        ctx._aux_request_events = (ctx._aux_request_events + [event])[-16:]
        return event

    event = await ctx.world.runtime.dispatch_now(receive)
    if event['status'] == 'local_empty_exclusion_list':
        event['response'] = 'attempted'
        await ctx._world_send(writer, row, (empty_exclusion_frame(),), operation_lock)
        event['response'] = 'drained'
    return True


def _aux_requests_report(ctx, result):
    result['auxiliary_requests'] = dict(events=[dict(event) for event in ctx._aux_request_events],
        exclusion_policy='LOCAL_EMPTY_BOOTSTRAP_ONLY',
        emblem_response='UNKNOWN_NOT_SENT')


METHODS = (_aux_requests_initialize, _aux_requests_request, _aux_requests_report)
HOOKS = {'initialize': ('_aux_requests_initialize',), 'report': ('_aux_requests_report',)}
FRAMES = {EXCLUDE: ('_aux_requests_request',), EMBLEM_INFO: ('_aux_requests_request',)}
OUTGOING_OPCODES = (EXCLUDE_LIST,)
