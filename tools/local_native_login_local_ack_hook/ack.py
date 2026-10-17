"""Local-only ACK0 experiment for an exact owned 0263 request."""
import ast, hashlib, importlib.util, sys, types, uuid
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
FROZEN_SHA='f47960d34721f8c0dad103ed9186ed54614430c37b146b165efed727dd5889b7'
p=ROOT/'tools/local_native_login_runtime_hook/hook.py';raw=p.read_bytes()
if hashlib.sha256(raw).hexdigest()!=FROZEN_SHA:raise ValueError('FROZEN_NATIVE_LOGIN_HOOK_CHANGED')
spec=importlib.util.spec_from_file_location('_frozen_native_login_consumption_parent',p)
parent=importlib.util.module_from_spec(spec);sys.modules[spec.name]=parent;spec.loader.exec_module(parent)
need=parent.need
ACK_FRAME=b'\x08\x00\x64\x02\x08\x00\x00\x00'
need(len(ACK_FRAME)==8 and int.from_bytes(ACK_FRAME[:2],'little')==8
     and int.from_bytes(ACK_FRAME[2:4],'little')==0x264
     and ACK_FRAME[4:]==b'\x08\x00\x00\x00','EXACT_LOCAL_ACK0_FRAME')
def identity(binding):
    need(type(binding) is dict and set(binding)=={'candidate_sha256','expected_own_uuid'},'EXPLICIT_CONSUMPTION_BINDING_REQUIRED')
    h=binding['candidate_sha256']
    need(type(h) is str and len(h)==64 and all(c in '0123456789abcdef' for c in h),'EXPLICIT_CANDIDATE_SHA_REQUIRED')
    text=binding['expected_own_uuid']
    try:value=uuid.UUID(text)
    except (ValueError,TypeError,AttributeError):raise ValueError('EXPLICIT_OWN_UUID_REQUIRED') from None
    need(type(text) is str and value.version==4 and value.variant==uuid.RFC_4122 and str(value)==text,'CANONICAL_OWN_UUID4_REQUIRED')
    return text
def input_paths():return list(dict.fromkeys([*parent.input_paths(),p,Path(__file__).resolve()]))
class ConsumptionExtension:
    def __init__(self,expected_uuid):self.expected_uuid=expected_uuid;self.receipts={}
    def bind(self,game):
        registry,writer=game.registry,game.connection
        need(registry.resolve(writer) is game,'REGISTERED_OWN_SESSION_REQUIRED')
        need(0x263 not in game.routes,'OWN_LOGIN_ROUTE_ALREADY_REGISTERED')
        consumed=False
        async def receive(payload):
            nonlocal consumed
            need(registry.resolve(writer) is game,'REGISTERED_OWN_SESSION_REQUIRED')
            need(not consumed and not game.list_sent and game.selection is None,'OWN_LOGIN_ORDER_OR_REPLAY')
            request=parent.route.codec.parse(payload)
            # The unchanged parser validates required uint32 address, canonical
            # own UUID, own issuer, and optional typed string. Address value is
            # neither guessed nor copied into an expected DTO; semantics remain
            # UNKNOWN and this route does not authorize login.
            need(request.guest_uuid==self.expected_uuid and request.issuer=='standalone.local','OWN_LOGIN_IDENTITY_MISMATCH')
            need(request.guest_uuid not in self.receipts,'OWN_UUID_ALREADY_CONSUMED')
            consumed=True;self.receipts[request.guest_uuid]=True
            return (ACK_FRAME,)
        game.routes[0x263]=receive
def attach_consumption(serve,expected_uuid):
    adapter=serve.owned_game_adapter
    need(not isinstance(adapter.registry,parent.route.LoginRegistry),'OWN_LOGIN_ALREADY_ATTACHED')
    need(not adapter.registry._sessions,'ATTACH_BEFORE_CONNECTIONS_REQUIRED')
    extension=ConsumptionExtension(expected_uuid)
    adapter.registry=parent.route.LoginRegistry(adapter.registry,extension)
    return extension
# Derive only two frozen named functions: the public review/bind function
# continues its actual serve path, original current-owner/IO/Source guards,
# constructor subclass, receipt lifetime, and all existing pin requirements.
tree=ast.parse(raw,str(p));bind=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='bind_serve_both')
calls=[n for n in ast.walk(bind) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
       and isinstance(n.func.value,ast.Name) and n.func.value.id=='route' and n.func.attr=='attach']
need(len(calls)==1,'EXACT_OWN_ROUTE_ATTACH_CALL_REQUIRED')
calls[0].func=ast.Name(id='_attach_consumption',ctx=ast.Load())
review=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='expected_review')
returns=[n for n in ast.walk(review) if isinstance(n,ast.Return) and isinstance(n.value,ast.Dict)]
need(len(returns)==1,'EXACT_REVIEW_RETURN_REQUIRED')
d=returns[0].value
for i,key in enumerate(d.keys):
    if isinstance(key,ast.Constant) and key.value=='schema':d.values[i]=ast.Constant('native-own-login-local-ack-review-v1')
    if isinstance(key,ast.Constant) and key.value=='ack_roster_response':d.values[i]=ast.Constant('LOCAL_ONLY_0264_RESULT0_EXPERIMENT')
    if isinstance(key,ast.Constant) and key.value=='receipt_fields':
        d.values[i]=ast.List(elts=[ast.Constant(x) for x in ('success','opcode','connection_id','address_semantics','login_authorized')],ctx=ast.Load())
compiled=compile(ast.fix_missing_locations(tree),str(p),'exec')
namespace=dict(parent.__dict__)
class LocalReceiptRegistry(parent.ReceiptRegistry):
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
        game.routes[0x263]=receive;return game
namespace.update(expectation=identity,input_paths=input_paths,_attach_consumption=attach_consumption,
                 ReceiptRegistry=LocalReceiptRegistry)
for name in ('expected_review','bind_serve_both'):
    code=next(c for c in compiled.co_consts if isinstance(c,types.CodeType) and c.co_name==name)
    fn=types.FunctionType(code,namespace,name,getattr(parent,name).__defaults__)
    fn.__kwdefaults__=getattr(parent,name).__kwdefaults__;namespace[name]=fn
expected_review=namespace['expected_review']
def pin_context(ctx):
    parent.pin_context(ctx);backing=parent.base.backing_context(ctx)
    with backing.lock:
        need(getattr(ctx,'scope',None) is None,'OWN_LOGIN_PIN_BEFORE_SCOPE_REQUIRED')
        pin=backing.b.a.add(Path(__file__).resolve())
        backing.pinned_hashes[Path(__file__).resolve()]=pin.digest();ctx.verify_sources()
def bind_serve_both(prepared,ctx,approved_config,*,binding,root_review,receipt_sink):
    need(callable(receipt_sink),'PUBLIC_RECEIPT_SINK_REQUIRED')
    def public(row):
        need(set(row)=={'success','opcode','connection_id'},'EXACT_PUBLIC_CONSUMPTION_RECEIPT_REQUIRED')
        receipt_sink({**row,'address_semantics':'UNKNOWN','login_authorized':False})
    return namespace['bind_serve_both'](prepared,ctx,approved_config,binding=binding,root_review=root_review,receipt_sink=public)
