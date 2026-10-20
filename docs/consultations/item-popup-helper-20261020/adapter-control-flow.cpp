// CONSULTATION ONLY: abstract project-authored control flow, NOT exact product source.
// Not compilable or a public runtime reproducer. No ABI/layout/constants provided.
// Opaque predicates preserve the listed short-circuit order only; implementations
// and owner/capture/text details are intentionally withheld. No new runtime fields.

struct HelperTrace { unsigned seq=0,phase=0,state=0,step=0,falsecode=0; };
thread_local HelperTrace trace;
void Reset(unsigned requestSequence,unsigned phase) {
    trace={requestSequence,phase,0,0,0};
}
bool Check(unsigned step,bool existingPredicateResult) {
    trace.step=step; trace.state=existingPredicateResult?2u:4u;
    if(!existingPredicateResult) trace.falsecode=step;
    return existingPredicateResult;  // never authority, retry, or an added memory read
}

// All upper-case calls below are OPAQUE roles, not recovered functions or fields.
bool Snapshot(AbstractRequest request,AbstractFlight& flight,bool initial) {
    Reset(SEQUENCE(request),initial?1u:2u); trace.state=1;
    REASON(flight)=Changed;
    if(TERMINAL() || !OWNED_NOW() || !MODAL_CURRENT(request,flight)) return false;
    REASON(flight)=Pc;
    if(!CURRENT_REGISTERED_HELD_PC_AND_MAP(request,flight,initial)) return false;
    REASON(flight)=Helper;
    Opaque helper,callback,submit,cancel,table,target,owner;
    if(!Check(1,READ_INSTALLED_HELPER(flight,helper)) ||
       !Check(2,HELPER_READABLE_SPAN(helper)) ||
       !Check(3,READ_CALLBACK(helper,callback)) || !Check(4,NONNULL(callback)) ||
       !Check(5,READ_SUBMIT(helper,submit)) || !Check(6,NONNULL(submit)) ||
       !Check(7,READ_OPTIONAL_CANCEL(helper,cancel))) return false;
    if(!Check(8,READ_CALLABLE_TABLE(submit,table)) ||
       !Check(9,IS_EXPECTED_SUBMIT_TABLE(table)) ||
       !Check(10,READ_SELECTED_ENTRY(table,target)) ||
       !Check(11,IS_EXPECTED_SUBMIT_ENTRY(target)) ||
       !Check(12,READ_CAPTURED_OWNER(submit,owner)) ||
       !Check(13,SAME_IDENTITY(owner,helper))) return false;
    if(NONNULL(cancel) &&
       (!Check(14,READ_CALLABLE_TABLE(cancel,table)) ||
        !Check(15,IS_EXPECTED_CANCEL_TABLE(table)) ||
        !Check(16,READ_SELECTED_ENTRY(table,target)) ||
        !Check(17,IS_EXPECTED_CANCEL_ENTRY(target)) ||
        !Check(18,READ_CAPTURED_OWNER(cancel,owner)) ||
        !Check(19,SAME_IDENTITY(owner,helper)))) return false;
    trace.state=3;
    // Omitted product capture/text stages set their own reasons before returning.
    if(!BOUND_CAPTURE_AND_CURRENT_WIDGET_GETTER(request,flight,callback)) return false;
    if(initial) CAPTURE_INITIAL_IDENTITIES(flight,helper,callback,submit,cancel);
    else {
        REASON(flight)=Helper;
        if(!Check(20,SAME_WITH_BOUND_HELPER(flight,helper)) ||
           !Check(21,SAME_WITH_BOUND_CALLBACK(flight,callback)) ||
           !Check(22,SAME_WITH_BOUND_SUBMIT(flight,submit)) ||
           !Check(23,SAME_WITH_BOUND_CANCEL(flight,cancel))) return false;
        trace.state=3;
        if(!CURRENT_WIDGET_GETTER_AND_BOUND_CAPTURE(flight)) return false;
    }
    return true;
}

// Reset is also done on Process entry, Native entry, acquire entry and current
// entry BEFORE early deadline/claim checks. Snapshot resets again on its entry.
// current selects executing-vs-pending deadline according to setter mutation;
// failure before Snapshot leaves state/step/falsecode zero for this attempt.

Reply SubmitPath(AbstractRequest request,AbstractFlight& flight) {
    if(!ACQUIRE(request,flight) || !CURRENT(request,flight))
        return {REFUSED,REASON(flight),false}; // Helper => 42005, before setter
    if(!BEGIN_EXISTING_CLAIM()) return {REFUSED,Changed,false};
    MARK_MUTATED(flight); ORIGINAL_QUANTITY_SETTER(request,flight);
    if(!CURRENT(request,flight) || !ORIGINAL_READBACK(request,flight) ||
       !CURRENT(request,flight)) return {UNKNOWN,Changed,false}; // 42008
    bool enabled=ORIGINAL_GUARD(request,flight);
    if(!CURRENT(request,flight)) return {UNKNOWN,Changed,false};
    if(!EXECUTING_EXISTING_CLAIM()) return {UNKNOWN,Changed,false};
    if(!enabled) { ORIGINAL_HELD_PC_FALLBACK(flight); return {UNKNOWN,Guard,true}; }
    // Entire original entry; protected dispatch implementation intentionally absent.
    bool submitted=ORIGINAL_WHOLE_SUBMIT(request,flight);
    if(SUBMIT_PREFLIGHT_REFUSED(flight)) return {REFUSED,Changed,false};
    if(!submitted) {
        if(EXECUTING_EXISTING_CLAIM()) ORIGINAL_HELD_PC_FALLBACK(flight);
        return {UNKNOWN,OriginalFalse,true};
    }
    // Normal callback can retire helper/capture: no raw helper reads after RET.
    return {RETURNED,0,true};
}
// Product cancellation, invalid-request path, formatting, exceptions and original
// cleanup wrappers are omitted here, not removed from the actual implementation.
// Product clean releases retained PC then parent owners; ambiguous invocation or
// failed cleanup remains terminal UNKNOWN/no retry. RET is not backend authority.

void ExistingOutputPath(AbstractRequest request,Reply reply) {
    // Original context authentication remains opaque and required.
    if(!GUARD_TRACE_ACTIVE() || reply.status!=REFUSED ||
       (reply.reason!=Code && reply.reason!=Helper) || reply.invoked ||
       !ORIGINAL_OUTPUT_CONTEXT_MATCHES(request)) return;
    HelperTrace output=trace.seq==SEQUENCE(request)?trace:HelperTrace{};
    // Append only these integers to the existing bounded output path.
    // Existing source guard fields retained; CREATE_NEW and IO failures leave
    // authoritative result/calls/cache unchanged. No new collector or parser.
    EXISTING_BEST_EFFORT_OUTPUT(output.seq,output.phase,output.state,
                                output.step,output.falsecode);
}
