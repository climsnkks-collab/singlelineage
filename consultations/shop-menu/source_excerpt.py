"""PARTIAL EXCERPTS of our authored Python adapters, not original client code.
Origins below are relative to the SHOP feature directory. Method excerpts are
removed from their owning class indentation; omitted dependencies/guards remain
in the actual product. This file is not a runnable replacement or complete owner.
No binary analysis, machine code, addresses, saves or runtime logs are included.
"""

# Actual excerpt: dialogue-contract/dialogue_target.py::SourceTargetResolver.
# Constructor/interface and Binding requirement only. The actual validation body
# is omitted; this excerpt does not supply any of the six source adapters.
class SourceTargetResolver:
    def __init__(self,bindings,*,sent_input,current_sent,read_current_actor,current_read,
                 observed_origin,current_origin):
        adapters=(sent_input,current_sent,read_current_actor,current_read,observed_origin,current_origin)
        need(all(callable(f) for f in adapters),'CURRENT_SOURCE_OWNER_ADAPTERS_REQUIRED')
        self.bindings=bindings
        self.sent_input,self.current_sent=sent_input,current_sent
        self.read_current_actor,self.current_read=read_current_actor,current_read
        self.observed_origin,self.current_origin=observed_origin,current_origin

    def _scope(self,selection,binding):
        actual,session=self.bindings._session(selection.writer)
        need(actual is selection and session.port._binding(selection) is binding,'SAME_ITEM_OWNED_BINDING_REQUIRED')
        return self.bindings.broker.realm


# Actual excerpt, dedented method:
# haction-list-ingress-v1/candidate/tools/local_original_session/dialogue_send.py
# ::Feature.dispatch_locked. This shows the current first-Binding boundary.
async def dispatch_locked(self,writer,opcode,payload):
    need(self.attached and not self.closed and opcode==route.OPCODE,'ACTIVE_INGRESS')
    route.decode_request(payload)
    selection,session=self.bindings.actual._session(writer); binding=session.port._binding(selection)
    need(id(writer) not in self.ingress,'INGRESS_REENTRY')
    self.ingress[id(writer)]={'selection':selection,'binding':binding,'payload':payload,'issued':False}
    try: return await self.route.dispatch_locked(writer,opcode,payload)
    finally: self.ingress.pop(id(writer),None)


# Actual excerpt, nested closure dedented:
# haction-list-ingress-v1/candidate/tools/local_original_session/broker.py
# ::LocalRealm.grant::action_request. Opcode registration is omitted.
async def action_request(payload):
    provider=self._canonical_provider
    need(provider is not None,'HACTION_CANONICAL_CONNECTION_SCOPE')
    binding=provider.bind_selected(writer)
    await action.dispatch_locked(binding,payload)
    provider.current(binding)
    return ()


# NORMALIZED FLOW SKETCH, NOT implemented source or an invented completed bridge:
# owned connection/row scope
#   -> actual decoded request + received ordinal + private ADMITTED receipt
#   -> [MISSING: Binding-free real target/menu source verification]
#   -> if previous accepted Use: original source/projection + exact intent check
#   -> original release, only when this request has supersession authority
#   -> first general Binding
#   -> existing dialogue/action route + source-reviewed response body
#   -> original guarded frame/write/drain
#   -> independent detached server menu/list generation
#   -> existing atomic trade route
# Whether the missing stage needs a client-side historical send/current Actor
# bridge, or can be a narrower server-owned interaction authority, is a question
# for this consultation. No fake implementation or successful UI claim is here.
