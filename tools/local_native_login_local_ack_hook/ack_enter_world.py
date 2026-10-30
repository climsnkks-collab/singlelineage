"""Owned-local creation and source-bounded Login READ_NEWS consumption."""
import hashlib
import ast
import importlib.util
import sys
import types
from pathlib import Path

SELF=Path(__file__).resolve()
ROOT=SELF.parents[2]
CONNECTION=ROOT/'tools/local_game_session/connection.py'
CONNECTION_SHA='bb50d27c2070505e2b1d6c4a12a29cff72c08520a14a5b1a2a7905533595072e'
REALM_PATH=ROOT/'tools/local_character_creation/realm.py'
REALM_SHA='b594d067f844a5140fd8cab77e4a53f6eb2056fd4abdcd85ea3d421fdf14a80e'
STORE_PATH=ROOT/'work/standalone_boot/owned-local-profile/characters.json'
ACK_FRAME=b'\x08\x00\x64\x02\x08\x00\x00\x00'
if len(ACK_FRAME)!=8 or int.from_bytes(ACK_FRAME[:2],'little')!=8 or int.from_bytes(ACK_FRAME[2:4],'little')!=0x264:
    raise ValueError('EXACT_LOCAL_ACK0_FRAME')

# realm.py source hash pin removed (Python source pins reduced); REALM_SHA kept for reference only.
spec=importlib.util.spec_from_file_location('_owned_local_character_creation',REALM_PATH)
realm=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=realm
spec.loader.exec_module(realm)
ENTER_ACK_FRAME=realm.wire.state5_request_ack(field2=3)
if realm.wire.validate_frame(ENTER_ACK_FRAME).kind!='ACK':
    raise ValueError('EXACT_LOCAL_ENTER_ACK3_FRAME')

def wrap(base):
    """Preserve the supplied port hook's exact compiler and source guards."""
    need=base.need
    if not hasattr(base,'namespace') or not hasattr(base,'ConsumptionExtension'):
        raise ValueError('PORT_CONSUMPTION_HOOK_REQUIRED')

    def transport():
        raw=CONNECTION.read_bytes()
        need(hashlib.sha256(raw).hexdigest()==CONNECTION_SHA,'FROZEN_OWNED_CONNECTION_REQUIRED')
        tree=ast.parse(raw,str(CONNECTION));count=0;idle_count=0
        for node in ast.walk(tree):
            if isinstance(node,ast.If) and isinstance(node.test,ast.Name) and node.test.id=='game_reply':
                need(ast.unparse(node.body[0])=='decoded = session.wire.validate_frame(wire)' and
                     ast.unparse(node.body[1])=="session.need(decoded.kind in ('NUM', 'INFO'), 'WORLD_OR_ACK_REPLY_UNBOUND')",
                     'EXACT_GAME_REPLY_VALIDATOR_REQUIRED')
                original=node.body[:2]
                selected=ast.parse("if opcode==0x264:\n session.need(wire==ACK_FRAME,'EXACT_LOCAL_ACK0_REPLY')\nelif opcode==0x4e25:\n session.need(wire==CREATE_ACK_FRAME,'EXACT_LOCAL_CREATE_ACK0_REPLY')\nelif opcode==0x4e29:\n session.need(wire==ENTER_ACK_FRAME,'EXACT_LOCAL_ENTER_ACK3_REPLY')\nelse:\n pass").body[0]
                selected.orelse[0].orelse[0].orelse=original
                node.body[:2]=[selected]
                count+=1
            if (isinstance(node,ast.Assign) and len(node.targets)==1 and
                    isinstance(node.targets[0],ast.Name) and node.targets[0].id=='raw'):
                need(ast.unparse(node.value)==
                     'await asyncio.wait_for(reader.read(4096), min(15, max(0.001, deadline - time.monotonic())))',
                     'EXACT_OWNED_READ_TIMEOUT_REQUIRED')
                node.value=ast.parse('await asyncio.wait_for(reader.read(4096), min(45 if game is not None else 15, max(0.001, deadline - time.monotonic())))',mode='eval').body
                idle_count+=1
        need(count==1,'ONE_EXACT_ACK_TRANSPORT_EXTENSION')
        need(idle_count==1,'ONE_OWNED_INTERACTIVE_IDLE_EXTENSION')
        module=types.ModuleType('_local_ack_port_connection')
        module.__file__=str(CONNECTION)
        module.ACK_FRAME=ACK_FRAME
        module.CREATE_ACK_FRAME=realm.create_ack(0)
        module.ENTER_ACK_FRAME=ENTER_ACK_FRAME
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
        return list(dict.fromkeys([*base.input_paths(),REALM_PATH,SELF]))

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
                need(not game.list_sent and 1<=len(game.roster.frames)<=realm.MAX_CHARACTERS+1,
                     'EXACT_OWNED_ROSTER_REQUIRED')
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
            store=realm.CharacterStore(STORE_PATH)
            roster,references=store.snapshot()
            game.roster=type(game.roster)(roster.frames,references)
            original=game.routes[0x263]
            async def receive(payload):
                need(self.registry.resolve(writer) is game,'REGISTERED_OWN_WRITER_REQUIRED')
                owner=self.owners.get(id(writer))
                need(owner is not None and owner[0] is writer,'EXACT_ADMITTED_CONNECTION_REQUIRED')
                replies=await original(payload)
                need(replies==(ACK_FRAME,)+game.roster.frames,
                     'EXACT_LOCAL_ACK0_SAVED_ROSTER_REQUIRED')
                self.sink({'success':True,'opcode':0x263,'connection_id':owner[1]})
                return replies
            game.routes[0x263]=receive
            need(realm.CREATE_OPCODE not in game.routes,'CREATE_ROUTE_ALREADY_REGISTERED')
            async def create(payload):
                need(self.registry.resolve(writer) is game,'REGISTERED_OWN_WRITER_REQUIRED')
                owner=self.owners.get(id(writer))
                need(owner is not None and owner[0] is writer and game.list_sent
                     and game.selection is None,'CREATE_OWN_SESSION_ORDER_REQUIRED')
                request=realm.decode_creation(payload)
                store.create(request)
                updated,references=store.snapshot()
                game.roster=type(game.roster)(updated.frames,references)
                return (realm.create_ack(0),)+updated.frames
            game.routes[realm.CREATE_OPCODE]=create
            need(0x4e28 in game.routes,'SOURCE_BOUND_ENTER_ROUTE_REQUIRED')
            prior_select=game.routes[0x4e28]
            async def select(payload):
                need(self.registry.resolve(writer) is game,'REGISTERED_OWN_WRITER_REQUIRED')
                owner=self.owners.get(id(writer))
                need(owner is not None and owner[0] is writer and game.list_sent
                     and game.selection is None,'ENTER_OWN_SESSION_ORDER_REQUIRED')
                replies=await prior_select(payload)
                need(replies==() and game.selection is not None,
                     'EXACT_OWNED_SELECTION_REQUIRED')
                store.select(game.selection.reference)
                return (ENTER_ACK_FRAME,)
            game.routes[0x4e28]=select
            need(0x267 not in game.routes,'READ_NEWS_ROUTE_ALREADY_REGISTERED')
            read_news_seen=False
            async def read_news(payload):
                nonlocal read_news_seen
                need(self.registry.resolve(writer) is game,'REGISTERED_OWN_WRITER_REQUIRED')
                owner=self.owners.get(id(writer))
                need(owner is not None and owner[0] is writer and game.list_sent
                     and game.selection is None and not read_news_seen,
                     'READ_NEWS_OWN_SESSION_ORDER_REQUIRED')
                with realm.pb.parse_message(payload,schema={1:0,2:0,3:0},
                     limits=realm.pb.WireLimits(max_body=64,max_fields=3,max_field_bytes=64)) as parsed:
                    need(len(parsed.occurrences(1))<=1
                         and all(len(parsed.occurrences(n))==1 for n in (2,3)),
                         'READ_NEWS_SOURCE_FIELDS_REQUIRED')
                    if parsed.occurrences(1):
                        need(parsed.occurrences(1)[0].value in (0,1),
                             'READ_NEWS_BOOL_REQUIRED')
                    for n in (2,3):
                        realm._i32(parsed.occurrences(n)[0].value)
                read_news_seen=True
                return ()
            game.routes[0x267]=read_news
            return game

    def expected_review(proof,binding,approved_config):
        row=base.expected_review(proof,binding,approved_config)
        row.update(schema='native-own-login-local-character-create-review-v1',
                   ack_roster_response='LOCAL_ONLY_0264_RESULT0_THEN_SAVED_NUM_INFO',
                   create_request_opcode=realm.CREATE_OPCODE,
                   create_ack_opcode=realm.CREATE_ACK_OPCODE,
                   create_ack_field1_local_value=0,
                   selected_enter_ack_field2_local_value=3,
                   read_news_request_opcode=0x267,
                   read_news_schema_rva='0x15ecba0',
                   read_news_source_fields=[1,2,3],
                   read_news_response='NONE_LOCAL',
                   owned_interactive_idle_seconds=45,
                   owned_store_path=str(STORE_PATH),
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
            realm_pin=backing.b.a.add(REALM_PATH)
            backing.pinned_hashes[REALM_PATH]=realm_pin.digest()
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
