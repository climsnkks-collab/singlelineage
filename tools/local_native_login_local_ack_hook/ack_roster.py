"""Local ACK0 plus an empty roster on the port-adapted own-consumption hook."""
import hashlib
import ast
import sys
import types
from pathlib import Path

SELF=Path(__file__).resolve()
ROOT=SELF.parents[2]
CONNECTION=ROOT/'tools/local_game_session/connection.py'
CONNECTION_SHA='bb50d27c2070505e2b1d6c4a12a29cff72c08520a14a5b1a2a7905533595072e'
ACK_FRAME=b'\x08\x00\x64\x02\x08\x00\x00\x00'
if len(ACK_FRAME)!=8 or int.from_bytes(ACK_FRAME[:2],'little')!=8 or int.from_bytes(ACK_FRAME[2:4],'little')!=0x264:
    raise ValueError('EXACT_LOCAL_ACK0_FRAME')

def wrap(base):
    """Preserve the supplied port hook's exact compiler and source guards."""
    need=base.need
    if not hasattr(base,'namespace') or not hasattr(base,'ConsumptionExtension'):
        raise ValueError('PORT_CONSUMPTION_HOOK_REQUIRED')

    def transport():
        raw=CONNECTION.read_bytes()
        need(hashlib.sha256(raw).hexdigest()==CONNECTION_SHA,'FROZEN_OWNED_CONNECTION_REQUIRED')
        tree=ast.parse(raw,str(CONNECTION));count=0
        for node in ast.walk(tree):
            if isinstance(node,ast.If) and isinstance(node.test,ast.Name) and node.test.id=='game_reply':
                need(ast.unparse(node.body[0])=='decoded = session.wire.validate_frame(wire)' and
                     ast.unparse(node.body[1])=="session.need(decoded.kind in ('NUM', 'INFO'), 'WORLD_OR_ACK_REPLY_UNBOUND')",
                     'EXACT_GAME_REPLY_VALIDATOR_REQUIRED')
                original=node.body[:2]
                selected=ast.parse("if opcode==0x264:\n session.need(wire==ACK_FRAME,'EXACT_LOCAL_ACK0_REPLY')\nelse:\n pass").body[0]
                selected.orelse=original
                node.body[:2]=[selected]
                count+=1
        need(count==1,'ONE_EXACT_ACK_TRANSPORT_EXTENSION')
        module=types.ModuleType('_local_ack_port_connection')
        module.__file__=str(CONNECTION)
        module.ACK_FRAME=ACK_FRAME
        sys.modules[module.__name__]=module
        exec(compile(ast.fix_missing_locations(tree),str(CONNECTION),'exec'),module.__dict__)
        return module

    def maker(owners,cls,*args,**kwargs):
        need(cls.__name__=='OwnedGameAdapter','EXACT_ORIGINAL_ADAPTER_CONSTRUCTOR_REQUIRED')
        adapted=transport()
        class Adapter(adapted.OwnedGameAdapter):
            def grant(self,writer,peer):
                cid=peer.get('connection_id')
                need(type(cid)is int and cid in (1,2,3,4),'EXACT_CONNECTION_ID_REQUIRED')
                need(id(writer)not in owners,'OWN_WRITER_REUSE_REFUSED')
                owners[id(writer)]=(writer,cid)
                try:return super().grant(writer,peer)
                except BaseException:owners.pop(id(writer),None);raise
        return Adapter(*args,**kwargs)

    def input_paths():
        return list(dict.fromkeys([*base.input_paths(),SELF]))

    class LocalConsumption(base.ConsumptionExtension):
        def bind(self,game):
            registry,writer=game.registry,game.connection
            need(registry.resolve(writer) is game,'REGISTERED_OWN_SESSION_REQUIRED')
            need(0x263 not in game.routes,'OWN_LOGIN_ROUTE_ALREADY_REGISTERED')
            consumed=False
            async def receive(payload):
                nonlocal consumed
                need(registry.resolve(writer) is game,'REGISTERED_OWN_SESSION_REQUIRED')
                need(not consumed and not game.list_sent and game.selection is None,
                     'OWN_LOGIN_ORDER_OR_REPLAY')
                request=base.parent.route.codec.parse(payload)
                need(request.guest_uuid==self.expected_uuid and request.issuer=='standalone.local',
                     'OWN_LOGIN_IDENTITY_MISMATCH')
                need(request.guest_uuid not in self.receipts,'OWN_UUID_ALREADY_CONSUMED')
                consumed=True;self.receipts[request.guest_uuid]=True
                need(not game.list_sent and len(game.roster.frames)==1,
                     'EXACT_INITIAL_EMPTY_ROSTER_REQUIRED')
                game.list_sent=True
                return (ACK_FRAME,)+game.roster.frames
            game.routes[0x263]=receive

    def attach_consumption(serve,expected_uuid):
        adapter=serve.owned_game_adapter
        need(not isinstance(adapter.registry,base.parent.route.LoginRegistry),
             'OWN_LOGIN_ALREADY_ATTACHED')
        need(not adapter.registry._sessions,'ATTACH_BEFORE_CONNECTIONS_REQUIRED')
        extension=LocalConsumption(expected_uuid)
        adapter.registry=base.parent.route.LoginRegistry(adapter.registry,extension)
        return extension

    class LocalReceiptRegistry(base.parent.ReceiptRegistry):
        def register_own(self,writer,config,*,on_selection=None):
            game=self.registry.register_own(writer,config,on_selection=on_selection)
            original=game.routes[0x263]
            async def receive(payload):
                need(self.registry.resolve(writer) is game,'REGISTERED_OWN_WRITER_REQUIRED')
                owner=self.owners.get(id(writer))
                need(owner is not None and owner[0] is writer,'EXACT_ADMITTED_CONNECTION_REQUIRED')
                replies=await original(payload)
                need(replies==(ACK_FRAME,)+game.roster.frames,
                     'EXACT_LOCAL_ACK0_ROSTER_REQUIRED')
                self.sink({'success':True,'opcode':0x263,'connection_id':owner[1]})
                return replies
            game.routes[0x263]=receive
            return game

    def expected_review(proof,binding,approved_config):
        row=base.expected_review(proof,binding,approved_config)
        row.update(schema='native-own-login-local-ack-roster-review-v1',
                   ack_roster_response='LOCAL_ONLY_0264_RESULT0_THEN_EMPTY_NUM',
                   exact_local_ack_transport_extension=True,
                   source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in input_paths()})
        return row

    def pin_context(ctx):
        base.pin_context(ctx)
        backing=base.parent.base.backing_context(ctx)
        with backing.lock:
            need(getattr(ctx,'scope',None) is None,'LOCAL_ACK_PIN_BEFORE_SCOPE_REQUIRED')
            pin=backing.b.a.add(SELF)
            backing.pinned_hashes[SELF]=pin.digest()
            ctx.verify_sources()

    def bind_serve_both(prepared,ctx,approved_config,*,binding,root_review,receipt_sink):
        need(callable(receipt_sink),'PUBLIC_RECEIPT_SINK_REQUIRED')
        def public(row):
            need(set(row)=={'success','opcode','connection_id'},
                 'EXACT_PUBLIC_CONSUMPTION_RECEIPT_REQUIRED')
            receipt_sink({**row,'address_semantics':'UNKNOWN','login_authorized':False})
        names={'input_paths':input_paths,'_attach_consumption':attach_consumption,
               'ReceiptRegistry':LocalReceiptRegistry,'expected_review':expected_review,
               '_maker':maker}
        prior={name:base.namespace[name] for name in names}
        try:
            base.namespace.update(names)
            return base.namespace['bind_serve_both'](prepared,ctx,approved_config,
                      binding=binding,root_review=root_review,receipt_sink=public)
        finally:
            base.namespace.update(prior)

    return types.SimpleNamespace(identity=base.identity,input_paths=input_paths,
       expected_review=expected_review,pin_context=pin_context,
       bind_serve_both=bind_serve_both,port_adapted_base=base,
       transport=transport)
