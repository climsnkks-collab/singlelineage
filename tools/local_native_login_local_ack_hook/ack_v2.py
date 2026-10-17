"""ACK0 on the existing verified own-consumption extension path."""
import hashlib
import importlib.util
import sys
from pathlib import Path

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
PARENT=ROOT/'tools/local_native_login_runtime_hook/hook-consumption.py'
PARENT_SHA='d8506198222868a6ebb41f68135cb11454cee869061717821173a9342feeacd1'
if hashlib.sha256(PARENT.read_bytes()).hexdigest()!=PARENT_SHA:
    raise ValueError('FROZEN_OWN_CONSUMPTION_SOURCE_REQUIRED')
spec=importlib.util.spec_from_file_location('_local_ack_frozen_consumption',PARENT)
parent=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=parent
spec.loader.exec_module(parent)
need=parent.need
identity=parent.identity
ACK_FRAME=b'\x08\x00\x64\x02\x08\x00\x00\x00'
need(len(ACK_FRAME)==8 and int.from_bytes(ACK_FRAME[:2],'little')==8
     and int.from_bytes(ACK_FRAME[2:4],'little')==0x264
     and ACK_FRAME[4:]==b'\x08\x00\x00\x00','EXACT_LOCAL_ACK0_FRAME')

def input_paths():
    return list(dict.fromkeys([*parent.input_paths(),Path(__file__).resolve()]))

class LocalConsumption(parent.ConsumptionExtension):
    def bind(self,game):
        registry,writer=game.registry,game.connection
        need(registry.resolve(writer) is game,'REGISTERED_OWN_SESSION_REQUIRED')
        need(0x263 not in game.routes,'OWN_LOGIN_ROUTE_ALREADY_REGISTERED')
        consumed=False
        async def receive(payload):
            nonlocal consumed
            need(registry.resolve(writer) is game,'REGISTERED_OWN_SESSION_REQUIRED')
            need(not consumed and not game.list_sent and game.selection is None,'OWN_LOGIN_ORDER_OR_REPLAY')
            request=parent.parent.route.codec.parse(payload)
            need(request.guest_uuid==self.expected_uuid and request.issuer=='standalone.local',
                 'OWN_LOGIN_IDENTITY_MISMATCH')
            need(request.guest_uuid not in self.receipts,'OWN_UUID_ALREADY_CONSUMED')
            consumed=True;self.receipts[request.guest_uuid]=True
            return (ACK_FRAME,)
        game.routes[0x263]=receive

def attach_consumption(serve,expected_uuid):
    adapter=serve.owned_game_adapter
    need(not isinstance(adapter.registry,parent.parent.route.LoginRegistry),
         'OWN_LOGIN_ALREADY_ATTACHED')
    need(not adapter.registry._sessions,'ATTACH_BEFORE_CONNECTIONS_REQUIRED')
    extension=LocalConsumption(expected_uuid)
    adapter.registry=parent.parent.route.LoginRegistry(adapter.registry,extension)
    return extension

class LocalReceiptRegistry(parent.parent.ReceiptRegistry):
    def register_own(self,writer,config,*,on_selection=None):
        game=self.registry.register_own(writer,config,on_selection=on_selection)
        original=game.routes[0x263]
        async def receive(payload):
            need(self.registry.resolve(writer) is game,'REGISTERED_OWN_WRITER_REQUIRED')
            owner=self.owners.get(id(writer))
            need(owner is not None and owner[0] is writer,'EXACT_ADMITTED_CONNECTION_REQUIRED')
            replies=await original(payload)
            need(replies==(ACK_FRAME,),'EXACT_LOCAL_ACK0_ONLY_REQUIRED')
            self.sink({'success':True,'opcode':0x263,'connection_id':owner[1]})
            return replies
        game.routes[0x263]=receive
        return game

def expected_review(proof,binding,approved_config):
    row=parent.expected_review(proof,binding,approved_config)
    row.update(schema='native-own-login-local-ack-review-v2',
               ack_roster_response='LOCAL_ONLY_0264_RESULT0_EXPERIMENT',
               source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in input_paths()})
    return row

base_operation=parent.namespace['bind_serve_both']

def pin_context(ctx):
    parent.pin_context(ctx)
    backing=parent.parent.base.backing_context(ctx)
    with backing.lock:
        need(getattr(ctx,'scope',None) is None,'LOCAL_ACK_PIN_BEFORE_SCOPE_REQUIRED')
        path=Path(__file__).resolve()
        pin=backing.b.a.add(path)
        backing.pinned_hashes[path]=pin.digest()
        ctx.verify_sources()

def bind_serve_both(prepared,ctx,approved_config,*,binding,root_review,receipt_sink):
    need(callable(receipt_sink),'PUBLIC_RECEIPT_SINK_REQUIRED')
    def public(row):
        need(set(row)=={'success','opcode','connection_id'},
             'EXACT_PUBLIC_CONSUMPTION_RECEIPT_REQUIRED')
        receipt_sink({**row,'address_semantics':'UNKNOWN','login_authorized':False})
    # Keep the frozen binder's exact mutable globals. Its runtime patches the
    # prepared source API before this call; a copied globals dictionary would
    # lose those bindings and fail its prepared-function identity check.
    names={'input_paths':input_paths,'_attach_consumption':attach_consumption,
           'ReceiptRegistry':LocalReceiptRegistry,'expected_review':expected_review}
    prior={name:parent.namespace[name] for name in names}
    try:
        parent.namespace.update(names)
        return base_operation(prepared,ctx,approved_config,binding=binding,
                              root_review=root_review,receipt_sink=public)
    finally:
        parent.namespace.update(prior)
