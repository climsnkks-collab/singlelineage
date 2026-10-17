"""Generate a CP49 diagnostic-only include overlay; never load or run native code."""
from __future__ import annotations
import argparse
import ast
import hashlib
import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'tools/local_native_login_state5_ack_bridge'
OUT = ROOT / 'work/local_original_session/native-build'
PINS = {
    'binding.hpp': '608cf4ec8c562f01fb725c563dd70f3702694eec4427481b98f72d4778389c96',
    'probe.cpp': 'f38f610ae5cf10a218a4d72df3b5837688df1e35a731a353246553444f868701',
    'abi_bridge_v2.cpp': '5a5a788e7f584a232bdc2c67e27a9f72ffafac2100326d31cb3da365e7efff5f',
    'build.cmd': 'a1d46e0541598beebe0e8b134bc86aaa7d30fc7774ad5c69e1b8f2c8bb4c574f',
    'guard_template.asm': 'e68ef03caaea3f4b91be4823828aca5b7817b8fc4dfd41e46ab971532d0698e7',
    'bridge.def': '3fe728c862b4277498a079704aaf9dcf05c816c9e1d86cfeaa9b06555a560925',
}


def need(value, reason):
    if not value:
        raise ValueError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def replace_once(text, old, new, changes):
    need(text.count(old) == 1, 'EXACT_SINGLE_SOURCE_ANCHOR_REQUIRED')
    changes.append((old, new))
    return text.replace(old, new, 1)


def lifecycle_overlay(guard, command):
    gc, cc = [], []
    guard = replace_once(guard, '#include <type_traits>',
        '#include <type_traits>\n#include "tools/local_original_session/native/lifecycle_diagnostics.hpp"', gc)
    guard = replace_once(guard, '    if(result!=NO_ERROR) {\n        const LONG rollback=api.abort();',
        '    if(result==NO_ERROR)result=owned_lifecycle::Enlist(remove,api.attach,api.detach);\n'
        '    if(result!=NO_ERROR) {\n        const LONG rollback=api.abort();', gc)
    guard = replace_once(guard, '    // No runtime unload: the trampolines/wrappers must outlive every caller,',
        '    if(!owned_lifecycle::Prepare(entries,count))return fail(Admission::InvalidRegion,ERROR_NOT_SUPPORTED);\n'
        '    // No runtime unload: the trampolines/wrappers must outlive every caller,', gc)
    guard = replace_once(guard, '    if(!protections_restored()) {',
        '    if(!protections_restored() || !owned_lifecycle::ProtectionsRestored()) {', gc)
    guard = replace_once(guard, '    installed=true; failed_stage=static_cast<LONG>(Stage::Ready); failed_entry_index=-1;',
        '    owned_lifecycle::Installed();\n    installed=true; failed_stage=static_cast<LONG>(Stage::Ready); failed_entry_index=-1;', gc)
    command = replace_once(command, '\\\"blocked_input_calls\\\":%lld}\\n',
        '\\\"blocked_input_calls\\\":%lld,\\\"lifecycle_installed\\\":%s,\\\"lifecycle_hooks_count\\\":%u}\\n', cc)
    command = replace_once(command, 'guard.blocked_display_calls,guard.blocked_input_calls);',
        'guard.blocked_display_calls,guard.blocked_input_calls,owned_lifecycle::installed?"true":"false",owned_lifecycle::installed?3u:0u);', cc)
    command = replace_once(command, 'namespace internal_command {',
        'namespace internal_command {\nnamespace quit_detail {extern thread_local unsigned diagnostic_phase,diagnostic_step;extern thread_local uintptr_t diagnostic_anchor;}', cc)
    command = replace_once(command, '\\\"invoked\\\":%s}\\n',
        '\\\"invoked\\\":%s,\\\"quit_phase\\\":%u,\\\"quit_anchor_rva\\\":%llu,\\\"quit_source_step\\\":%u}\\n', cc)
    command = replace_once(command, 'reply.invoked?"true":"false");',
        'reply.invoked?"true":"false",r.command==3?quit_detail::diagnostic_phase:0u,\n'
        '        static_cast<unsigned long long>(r.command==3?quit_detail::diagnostic_anchor:0),r.command==3?quit_detail::diagnostic_step:0u);', cc)
    return guard, command, gc, cc


def quit_diagnostic_overlay(text):
    changes=[];phases={}
    text=replace_once(text,'namespace quit_detail {','namespace quit_detail {\n'
        'inline thread_local unsigned diagnostic_phase=0,diagnostic_step=0;\n'
        'inline thread_local uintptr_t diagnostic_anchor=0;',changes)
    start=text.index('inline bool Read(Proof& p) noexcept {');stop=text.index('template<class Code,class Copy>',start)
    old=text[start:stop];new=old.replace('    p={};','    diagnostic_anchor=0;diagnostic_step=0;\n    p={};',1)
    index=10
    def mark(match):
        nonlocal index
        phase=index;index+=1;phases[phase]=new[max(0,match.start()-240):match.end()].splitlines()[-4:]
        return '{diagnostic_phase=%du;return false;}'%phase
    new=re.sub(r'return false;',mark,new)
    text=replace_once(text,old,new,changes)
    text=replace_once(text,'const unsigned route=Route(p.sceneKind);if(!route)return false;',
        'diagnostic_anchor=0;diagnostic_step=0;const unsigned route=Route(p.sceneKind);if(!route){diagnostic_phase=80;return false;}',changes)
    text=replace_once(text,'        if(!code(address,a.size)||!copy(bytes,reinterpret_cast<void*>(address),a.size)||memcmp(bytes,a.bytes,a.size))return false;',
        '        diagnostic_anchor=a.rva;\n'
        '        if((diagnostic_step=1,!code(address,a.size))||(diagnostic_step=2,!copy(bytes,reinterpret_cast<void*>(address),a.size))||\n'
        '           (diagnostic_step=3,memcmp(bytes,a.bytes,a.size))){diagnostic_phase=81;return false;}',changes)
    text=replace_once(text,'    return held && Read(current) && Same(p,current) && Source(current);',
        '    if(!held){diagnostic_phase=100;return false;}\n'
        '    if(!Read(current))return false;\n'
        '    if(!Same(p,current)){diagnostic_phase=101;return false;}\n'
        '    return Source(current);',changes)
    text=replace_once(text,'    return Read(last)&&Same(p,last);',
        '    if(!Read(last))return false;\n    if(!Same(p,last)){diagnostic_phase=121;return false;}return true;',changes)
    text=replace_once(text,'    Proof before,current;\n    if(!prepare(before) || !Route(before.sceneKind) || !fresh(current) || !Same(before,current))return {"REFUSED",6,false};\n    const bool returned=invoke(current);',
        '    diagnostic_phase=diagnostic_step=0;diagnostic_anchor=0;Proof before,current;\n'
        '    if(!prepare(before) || (diagnostic_phase=201,!Route(before.sceneKind)) || !fresh(current) ||\n'
        '       (diagnostic_phase=202,!Same(before,current)))return {"REFUSED",6,false};\n'
        '    diagnostic_phase=210;const bool returned=invoke(current);diagnostic_phase=returned?211u:212u;',changes)
    phases.update({80:'unsupported source route',81:'source anchor failed; step1 Executable,2 SafeCopy,3 memcmp',
        100:'strong pair retention failed',101:'proof changed while bridge strong pairs held',
        121:'borrowed proof changed after source verification',201:'unsupported route after Prepare',
        202:'proof changed after bridge-owned references released',210:'original callback entered',
        211:'original callback returned',212:'original callback fault contained'})
    return text,changes,phases


def quit_retry_overlay(text,command):
    qc,cc=[],[]
    text=replace_once(text,'inline bool Source(const Proof& p) noexcept {return SourceProof(p,Executable,SafeCopy);}',
        '#include "tools/local_original_session/native/quit_source_retry.hpp"',qc)
    text=replace_once(text,'inline bool Prepare(Proof& p) noexcept {','inline bool Prepare(Proof& p,PageBudget& budget) noexcept {',qc)
    text=replace_once(text,'    return Source(current);','    return Source(current,budget);',qc)
    text=replace_once(text,'inline bool Fresh(Proof& p) noexcept {','inline bool Fresh(Proof& p,PageBudget& budget) noexcept {',qc)
    text=replace_once(text,'if(!Read(p)||!Source(p))','if(!Read(p)||!Source(p,budget))',qc)
    text=replace_once(text,'inline Reply Execute() noexcept {return Run(Prepare,Fresh,Invoke);}',
        'inline Reply Execute() noexcept {\n'
        '    PageBudget budget;retry_query={};retry_query_anchor=retry_pages=0;retry_attempted=retry_full_verified=false;\n'
        '    const auto reply=Run([&](Proof& p) noexcept {return Prepare(p,budget);},\n'
        '        [&](Proof& p) noexcept {return Fresh(p,budget);},\n'
        '        [&](const Proof& p) noexcept {budget.full_guard=true;return Invoke(p);});\n'
        '    retry_pages=budget.used;retry_attempted=budget.used!=0;retry_full_verified=retry_attempted&&budget.full_guard;return reply;\n}',qc)
    command=replace_once(command,'namespace quit_detail {extern thread_local unsigned diagnostic_phase,diagnostic_step;extern thread_local uintptr_t diagnostic_anchor;}',
        'namespace quit_detail {extern thread_local unsigned diagnostic_phase,diagnostic_step;extern thread_local uintptr_t diagnostic_anchor;\n'
        'extern thread_local source_diagnostic::Query retry_query;extern thread_local uintptr_t retry_query_anchor;\n'
        'extern thread_local unsigned retry_pages;extern thread_local bool retry_attempted,retry_full_verified;}',cc)
    command=replace_once(command,'char text[768]{};','char text[1024]{};',cc)
    command=replace_once(command,'\\\"quit_source_step\\\":%u}\\n',
        '\\\"quit_source_step\\\":%u,\\\"quit_query_state\\\":%lu,\\\"quit_query_protect\\\":%lu,\\\"quit_query_type\\\":%lu,'
        '\\\"quit_query_category\\\":%u,\\\"quit_query_returned\\\":%llu,\\\"quit_query_span\\\":%llu,\\\"quit_query_region_size\\\":%llu,'
        '\\\"quit_query_anchor_rva\\\":%llu,\\\"quit_retry_attempted\\\":%s,\\\"quit_retry_pages\\\":%u,\\\"quit_retry_full_verified\\\":%s}\\n',cc)
    command=replace_once(command,'r.command==3?quit_detail::diagnostic_step:0u);',
        'r.command==3?quit_detail::diagnostic_step:0u,\n'
        '        r.command==3?quit_detail::retry_query.state:0,r.command==3?quit_detail::retry_query.protect:0,r.command==3?quit_detail::retry_query.type:0,\n'
        '        r.command==3?quit_detail::retry_query.category:0u,static_cast<unsigned long long>(r.command==3?quit_detail::retry_query.returned:0),\n'
        '        static_cast<unsigned long long>(r.command==3?quit_detail::retry_query.span:0),static_cast<unsigned long long>(r.command==3?quit_detail::retry_query.region_size:0),\n'
        '        static_cast<unsigned long long>(r.command==3?quit_detail::retry_query_anchor:0),r.command==3&&quit_detail::retry_attempted?"true":"false",\n'
        '        r.command==3?quit_detail::retry_pages:0u,r.command==3&&quit_detail::retry_full_verified?"true":"false");',cc)
    return text,command,qc,cc


def integrity_overlay(guard,command,details=False,pre_self=False):
    gc,cc=[],[]
    guard=replace_once(guard,'#include "tools/local_original_session/native/lifecycle_diagnostics.hpp"',
        '#define OWN_LIFECYCLE_INTEGRITY 1\n#include "tools/local_original_session/native/lifecycle_diagnostics.hpp"',gc)
    guard=replace_once(guard,'    return api.commit();',
        '    const LONG committed=api.commit();\n'
        '    if(committed==NO_ERROR&&!remove)owned_lifecycle::CaptureAfterCommit(list,size);\n    return committed;',gc)
    command=replace_once(command,'    const auto hook=autoOkHook.load();',
        '    const auto hook=autoOkHook.load();\n    if(code>=0&&remove==PM_REMOVE)owned_lifecycle::MaybeHealth();',cc)
    command=replace_once(command,'    AtomicOutput(context,L"command-bridge.json",text,n);SetLastError(before);',
        '    AtomicOutput(context,L"command-bridge.json",text,n);\n'
        '    if(autoOkHook.load())owned_lifecycle::StartHealth();\n    SetLastError(before);',cc)
    command=replace_once(command,'\\\"lifecycle_hooks_count\\\":%u}\\n',
        '\\\"lifecycle_hooks_count\\\":%u,\\\"lifecycle_logical_exports\\\":8}\\n',cc)
    command=replace_once(command,'owned_lifecycle::installed?3u:0u);','owned_lifecycle::installed?owned_lifecycle::physical_count:0u);',cc)
    if details:
        guard=replace_once(guard,'#define OWN_LIFECYCLE_INTEGRITY 1',
            '#define OWN_LIFECYCLE_INTEGRITY 1\n#define OWN_LIFECYCLE_DETAILS 1',gc)
        guard=replace_once(guard,'    const HMODULE user=GetModuleHandleW(L"user32.dll");',
            '    const HMODULE user=GetModuleHandleW(L"user32.dll");\n    owned_lifecycle::RememberUserModule(user);',gc)
    if pre_self:
        need(details,'PRE_SELF_REQUIRES_DETAILS')
        guard=replace_once(guard,'#define OWN_LIFECYCLE_DETAILS 1',
            '#define OWN_LIFECYCLE_DETAILS 1\n#define OWN_LIFECYCLE_PRE_SELF 1',gc)
        guard=replace_once(guard,'    LONG result=api.begin(); if(result!=NO_ERROR) return result;',
            '    if(!remove)owned_lifecycle::CaptureBeforeInstall(list,size);\n'
            '    LONG result=api.begin(); if(result!=NO_ERROR) return result;',gc)
    return guard,command,gc,cc


def virtual_protect_overlay(guard,command,relative):
    gc,cc=[],[]
    guard=replace_once(guard,'#include "tools/local_original_session/native/lifecycle_diagnostics.hpp"',
        '#include "tools/local_original_session/native/lifecycle_diagnostics.hpp"\n#include "'+relative+'/virtual_protect_callers.hpp"',gc)
    guard=replace_once(guard,'    InterlockedExchange(&admission,static_cast<LONG>(Admission::Installed)); return true;',
        '    virtual_protect_callers::InstallOptional(pinned_self);\n    InterlockedExchange(&admission,static_cast<LONG>(Admission::Installed)); return true;',gc)
    command=replace_once(command,'    if(autoOkHook.load())owned_lifecycle::StartHealth();',
        '    if(autoOkHook.load()){virtual_protect_callers::Disarm();virtual_protect_callers::GuardedPublish(context);}\n'
        '    if(autoOkHook.load())owned_lifecycle::StartHealth();',cc)
    return guard,command,gc,cc


def immutable_results_overlay(command,relative):
    changes=[]
    start='inline void Output(const forward_diagnostic::Context& c,const Request& r,const Reply& reply) noexcept {'
    need(command.count(start)==1,'IMMUTABLE_EXACT_OUTPUT_REQUIRED')
    begin=command.index(start);end=command.index('\nstruct Pins',begin);block=command[begin:end]
    need(sha(block.encode())=='1852ee8cf8dd4085f64447435d3b930a51528744d7f80fbd8aa281f285754dbd','IMMUTABLE_OUTPUT_BODY_PIN')
    call='    AtomicOutput(c,L"command-result.json",text,n);'
    need(block.count(call)==1,'IMMUTABLE_SINGLE_OUTPUT_CALL_REQUIRED')
    replacement=block.replace(call,'    immutable_command_results::Win32Ops op;\n    immutable_command_results::Publish(op,c.directory,r.seq,text,n);',1)
    text=replace_once(command,block,replacement,changes)
    lines=[line for line in text.splitlines() if 'own-internal-command-bridge-v1' in line]
    need(len(lines)==1 and sha(lines[0].encode())=='032b55f3280b2f7e00e6a49166ca80621483fa6cc6062a708e5bf1341340a54f','IMMUTABLE_CAPABILITY_FORMAT_PIN')
    old=r'\"lifecycle_logical_exports\":8}\n'
    need(lines[0].count(old)==1,'IMMUTABLE_SINGLE_CAPABILITY_TAIL_REQUIRED')
    fresh=lines[0].replace(old,r'\"lifecycle_logical_exports\":8,\"command_result_mode\":\"immutable-sequence-v1\"}\n',1)
    text=replace_once(text,lines[0],fresh,changes)
    text=replace_once(text,'namespace internal_command {',
        '#include "'+relative+'/immutable_command_results.hpp"\n\nnamespace internal_command {',changes)
    verify_inverse(command,text,changes)
    return text,changes


def binding_overlay(original):
    changes = []
    text = replace_once(original, 'enum class BindReason:uint32_t',
        '// Diagnostic step: 0=not checked/invalid anchor, 1=Executable, 2=SafeCopy, 3=memcmp.\n'
        '// passed is true only after all three existing checks completed successfully.\n'
        'namespace source_diagnostic {inline thread_local unsigned step=0;inline thread_local bool passed=false;}\n'
        'enum class BindReason:uint32_t', changes)
    old = '''    if(!api.code(f.native_original_target,r.anchor_size) || !api.copy(original,reinterpret_cast<void*>(f.native_original_target),r.anchor_size) ||
       memcmp(original,r.anchor,r.anchor_size)){out.reason=BindReason::OriginalSourceMismatch;return out;}'''
    new = '''    source_diagnostic::passed=false;
    if((source_diagnostic::step=1,!api.code(f.native_original_target,r.anchor_size)) ||
       (source_diagnostic::step=2,!api.copy(original,reinterpret_cast<void*>(f.native_original_target),r.anchor_size)) ||
       (source_diagnostic::step=3,memcmp(original,r.anchor,r.anchor_size))){out.reason=BindReason::OriginalSourceMismatch;return out;}
    source_diagnostic::passed=true;'''
    text = replace_once(text, old, new, changes)
    return text, changes


def probe_overlay(original):
    changes = []
    text = replace_once(original,
        '    forward_diagnostic::binding_stage=0;forward_diagnostic::failed_record_id=-1;',
        '    forward_diagnostic::binding_stage=0;forward_diagnostic::failed_record_id=-1;\n'
        '    source_diagnostic::step=0;source_diagnostic::passed=false;', changes)
    old = '''                if(!r.anchor_size || r.anchor_size>32 || !Executable(p,r.anchor_size) || !SafeCopy(code,reinterpret_cast<void*>(p),r.anchor_size) || memcmp(code,r.anchor,r.anchor_size)) {
                    result.wrapper=0;result.reason=BindReason::OriginalSourceMismatch;forward_diagnostic::binding_stage=2;forward_diagnostic::failed_record_id=static_cast<int>(i);break;
                }'''
    new = '''                source_diagnostic::step=0;source_diagnostic::passed=false;
                if(!r.anchor_size || r.anchor_size>32 ||
                   (source_diagnostic::step=1,!Executable(p,r.anchor_size)) ||
                   (source_diagnostic::step=2,!SafeCopy(code,reinterpret_cast<void*>(p),r.anchor_size)) ||
                   (source_diagnostic::step=3,memcmp(code,r.anchor,r.anchor_size))) {
                    result.wrapper=0;result.reason=BindReason::OriginalSourceMismatch;forward_diagnostic::binding_stage=2;forward_diagnostic::failed_record_id=static_cast<int>(i);break;
                }
                source_diagnostic::passed=true;'''
    text = replace_once(text, old, new, changes)
    text = replace_once(text, 'char text[620]{};', 'char text[768]{};', changes)
    text = replace_once(text, 'char text[650]{};', 'char text[800]{};', changes)
    text = replace_once(text,
        r'\"bound_check_bits\":%u}\n',
        r'\"bound_check_bits\":%u,\"source_check_step\":%u,\"source_check_passed\":%s}\n', changes)
    text = replace_once(text,
        'forward_diagnostic::binding_stage,forward_diagnostic::failed_record_id,boundCheckBits);',
        'forward_diagnostic::binding_stage,forward_diagnostic::failed_record_id,boundCheckBits,\n'
        '                source_diagnostic::step,source_diagnostic::passed?"true":"false");', changes)
    text = replace_once(text,
        r'\"source_mismatch_override\":%s}\n',
        r'\"source_mismatch_override\":%s,\"source_check_step\":%u,\"source_check_passed\":%s}\n', changes)
    text = replace_once(text,
        'networkMatch?"true":"false",sourceOverride?"true":"false");',
        'networkMatch?"true":"false",sourceOverride?"true":"false",\n'
        '                source_diagnostic::step,source_diagnostic::passed?"true":"false");', changes)
    return text, changes


def verify_inverse(original, modified, changes):
    restored = modified
    for old, new in reversed(changes):
        need(restored.count(new) == 1, 'ONE_INVERSE_DELTA_REQUIRED')
        restored = restored.replace(new, old, 1)
    need(restored == original, 'UNDECLARED_SOURCE_CHANGE')


def connect_role_overlay(binding, probe):
    """Keep all9 publication; do not revoke a freshly verified Connect for another role."""
    bc, pc = [], []
    binding = replace_once(binding,
        'namespace source_diagnostic {inline thread_local unsigned step=0;inline thread_local bool passed=false;}',
        'namespace source_diagnostic {inline thread_local unsigned step=0;inline thread_local bool passed=false;\n'
        'inline thread_local bool current_original_verified=false,prior_all_roles_verified=false,connect_role_revalidated=false;}', bc)
    binding = replace_once(binding,
        'SRWLOCK lock=SRWLOCK_INIT;std::atomic<uintptr_t> base{0};std::array<std::atomic<uintptr_t>,9> originals{};',
        'SRWLOCK lock=SRWLOCK_INIT;std::atomic<uintptr_t> base{0};std::array<std::atomic<uintptr_t>,9> originals{};\n'
        '    // Set only after the existing complete all9 check and seven-target publication.\n'
        '    std::atomic<uintptr_t> all_roles_verified_base{0};', bc)
    binding = replace_once(binding,
        '    uintptr_t target(ForwardRole role) const noexcept',
        '''    bool allow_current_connect(const BindingResult& fresh,const BindingResult& failed,
                               uint32_t record,uint32_t stage,int failed_record) noexcept {
        if(record!=0 || !fresh.wrapper || fresh.reason!=BindReason::Bound || !fresh.base || !fresh.original ||
           failed.wrapper || failed.reason!=BindReason::OriginalSourceMismatch || stage!=2 ||
           failed_record<=0 || failed_record>=9)return false;
        AcquireSRWLockShared(&lock);
        const auto proof=all_roles_verified_base.load(std::memory_order_acquire);
        const bool allowed=proof && proof==fresh.base && base.load(std::memory_order_acquire)==fresh.base &&
            originals[static_cast<unsigned>(ForwardRole::Connect)].load(std::memory_order_acquire)==fresh.original;
        ReleaseSRWLockShared(&lock);return allowed;
    }
    uintptr_t target(ForwardRole role) const noexcept''', bc)
    probe = replace_once(probe, 'NativeProbeFrame frame{};BindingResult result;',
                         'NativeProbeFrame frame{};BindingResult result,currentVerified;', pc)
    probe = replace_once(probe,
        '    forward_diagnostic::binding_stage=0;forward_diagnostic::failed_record_id=-1;\n'
        '    source_diagnostic::step=0;source_diagnostic::passed=false;',
        '    forward_diagnostic::binding_stage=0;forward_diagnostic::failed_record_id=-1;\n'
        '    source_diagnostic::step=0;source_diagnostic::passed=false;\n'
        '    source_diagnostic::current_original_verified=false;source_diagnostic::prior_all_roles_verified=false;\n'
        '    source_diagnostic::connect_role_revalidated=false;', pc)
    probe = replace_once(probe,
        '        if(supplied && SafeCopy(&frame,supplied,sizeof(frame)))result=VerifyOriginal(frame,record,layout,api);',
        '        if(supplied && SafeCopy(&frame,supplied,sizeof(frame)))result=VerifyOriginal(frame,record,layout,api);\n'
        '        currentVerified=result;source_diagnostic::current_original_verified=result.wrapper!=0;\n'
        '        const auto priorAll=forwardBinding.all_roles_verified_base.load(std::memory_order_acquire);\n'
        '        source_diagnostic::prior_all_roles_verified=priorAll && priorAll==forwardBinding.base.load(std::memory_order_acquire);', pc)
    publication = 'forwardBinding.base.store(result.base,std::memory_order_release);}'
    probe = replace_once(probe, publication,
        'forwardBinding.base.store(result.base,std::memory_order_release);\n'
        '                    forwardBinding.all_roles_verified_base.store(result.base,std::memory_order_release);}', pc)
    anchor = '''        if(result.wrapper) {
            probeRecord=record;target=result.wrapper;'''
    replacement = '''        // Only a fresh valid current Connect can survive another role's all9 refusal.
        // Use the already published identical Connect; publish no new callable here.
        if(forwardBinding.allow_current_connect(currentVerified,result,record,
                forward_diagnostic::binding_stage,forward_diagnostic::failed_record_id)) {
            result.wrapper=currentVerified.wrapper;source_diagnostic::connect_role_revalidated=true;
            source_diagnostic::prior_all_roles_verified=true;
        }
        if(result.wrapper) {
            probeRecord=record;target=result.wrapper;'''
    probe = replace_once(probe, anchor, replacement, pc)
    probe = replace_once(probe,
        r'\"bound_check_bits\":%u,\"source_check_step\":%u,\"source_check_passed\":%s}\n',
        r'\"bound_check_bits\":%u,\"source_check_step\":%u,\"source_check_passed\":%s,\"current_original_verified\":%s,\"prior_all_roles_verified\":%s,\"connect_role_revalidated\":%s}\n', pc)
    probe = replace_once(probe,
        '                source_diagnostic::step,source_diagnostic::passed?"true":"false");\n            if(n>0)selected_diagnostic::output(context,leaf,text,n);\n        }\n    }\n    SetLastError(before);\n}\nstatic void RecordSenderProbe',
        '                source_diagnostic::step,source_diagnostic::passed?"true":"false",\n'
        '                source_diagnostic::current_original_verified?"true":"false",\n'
        '                source_diagnostic::prior_all_roles_verified?"true":"false",\n'
        '                source_diagnostic::connect_role_revalidated?"true":"false");\n'
        '            if(n>0)selected_diagnostic::output(context,leaf,text,n);\n        }\n    }\n    SetLastError(before);\n}\nstatic void RecordSenderProbe', pc)
    probe = replace_once(probe, 'char text[768]{};', 'char text[960]{};', pc)
    return binding, probe, bc, pc


def write_new(path, text):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(text)


def memory_query_overlay(binding, probe):
    """Observe the existing query only; preserve the Connect-fix admission rules."""
    bc, pc = [], []
    anchor = 'inline thread_local bool current_original_verified=false,prior_all_roles_verified=false,connect_role_revalidated=false;}'
    binding = replace_once(binding, anchor, anchor[:-1] + '''
// Failure: 0=not observed, 1=empty span, 2=span overflow, 3=query failed,
// 4=not committed, 5=guard, 6=noaccess, 7=region overflow, 8=outside region,
// 9=protection excluded, 10=pass. No address or original bytes are retained.
struct Query {bool observed=false,region_observed=false,range_checked=false,span_in_region=false;
    unsigned category=0;SIZE_T returned=0,span=0,region_size=0;DWORD error=0,state=0,protect=0,type=0;};
inline thread_local Query query{};
}''', bc)
    old = '''inline bool Executable(uintptr_t p,std::size_t n) noexcept {
    MEMORY_BASIC_INFORMATION m{};
    if(!n || p>UINTPTR_MAX-n || !VirtualQuery(reinterpret_cast<void*>(p),&m,sizeof(m)) || m.State!=MEM_COMMIT ||
       m.Protect&(PAGE_GUARD|PAGE_NOACCESS))return false;
    const auto start=reinterpret_cast<uintptr_t>(m.BaseAddress);
    if(start>UINTPTR_MAX-m.RegionSize || p+n>start+m.RegionSize)return false;
    const DWORD protection=m.Protect&0xff;
    return protection==PAGE_EXECUTE_READ || protection==PAGE_EXECUTE_READWRITE || protection==PAGE_EXECUTE_WRITECOPY;
}'''
    new = '''inline bool Executable(uintptr_t p,std::size_t n) noexcept {
    auto& q=source_diagnostic::query;q={};q.span=n;
    MEMORY_BASIC_INFORMATION m{};
    if(!n){q.category=1;return false;}
    if(p>UINTPTR_MAX-n){q.category=2;return false;}
    q.observed=true;q.returned=VirtualQuery(reinterpret_cast<void*>(p),&m,sizeof(m));
    if(!q.returned){q.error=GetLastError();q.category=3;return false;}
    q.region_observed=true;q.state=m.State;q.protect=m.Protect;q.type=m.Type;q.region_size=m.RegionSize;
    if(m.State!=MEM_COMMIT){q.category=4;return false;}
    if(m.Protect&(PAGE_GUARD|PAGE_NOACCESS)){q.category=(m.Protect&PAGE_GUARD)?5u:6u;return false;}
    const auto start=reinterpret_cast<uintptr_t>(m.BaseAddress);
    q.range_checked=true;
    if(start>UINTPTR_MAX-m.RegionSize){q.category=7;return false;}
    if(p+n>start+m.RegionSize){q.category=8;return false;}
    q.span_in_region=true;
    const DWORD protection=m.Protect&0xff;
    const bool result=protection==PAGE_EXECUTE_READ || protection==PAGE_EXECUTE_READWRITE || protection==PAGE_EXECUTE_WRITECOPY;
    q.category=result?10u:9u;return result;
}'''
    binding = replace_once(binding, old, new, bc)
    binding = replace_once(binding, '    source_diagnostic::passed=false;\n    if((source_diagnostic::step=1,',
        '    source_diagnostic::passed=false;source_diagnostic::query={};\n    if((source_diagnostic::step=1,', bc)
    probe = replace_once(probe, '                source_diagnostic::step=0;source_diagnostic::passed=false;',
        '                source_diagnostic::step=0;source_diagnostic::passed=false;source_diagnostic::query={};', pc)
    helper = r'''// Separate claims retain the current Selected refusal even after a constructor failure.
static std::atomic<bool> sourceFirstClaim{false},sourceSelectedClaim{false};
static void RecordSourceCheckFailure(uint32_t record,BindReason reason,uint32_t stage,int failed) noexcept {
    if(reason!=BindReason::OriginalSourceMismatch || (stage!=1 && stage!=2))return;
    const auto q=source_diagnostic::query;const unsigned step=source_diagnostic::step;
    const DWORD before=GetLastError();forward_diagnostic::Context c{};
    if(selected_diagnostic::valid_context(c)) {
        bool expected=false;const bool first=sourceFirstClaim.compare_exchange_strong(expected,true);
        expected=false;const bool selected=record==2 && sourceSelectedClaim.compare_exchange_strong(expected,true);
        if(first || selected) {
            FILETIME now{};GetSystemTimeAsFileTime(&now);
            const auto time=(static_cast<uint64_t>(now.dwHighDateTime)<<32)|now.dwLowDateTime;
            char returned[32]="null",error[32]="null",state[32]="null",protect[32]="null",type[32]="null",region[32]="null";
            if(q.observed)sprintf_s(returned,"%llu",static_cast<unsigned long long>(q.returned));
            if(q.observed && !q.returned)sprintf_s(error,"%lu",q.error);
            if(q.region_observed){sprintf_s(state,"%lu",q.state);sprintf_s(protect,"%lu",q.protect);sprintf_s(type,"%lu",q.type);sprintf_s(region,"%llu",static_cast<unsigned long long>(q.region_size));}
            char text[1536]{};
            const int n=sprintf_s(text,"{\"schema\":\"own-source-check-query-v1\",\"pid\":%lu,\"birth\":%llu,\"candidate_sha256\":\"%s\",\"filetime\":%llu,\"thread_id\":%lu,\"record_id\":%u,\"binding_reason\":%u,\"binding_stage\":%u,\"failed_record_id\":%d,\"source_check_step\":%u,\"source_check_passed\":false,\"query_observed\":%s,\"failure_category\":%u,\"query_returned_size\":%s,\"query_failure_error\":%s,\"memory_state\":%s,\"memory_protect\":%s,\"memory_type\":%s,\"span_bytes\":%llu,\"region_bytes\":%s,\"range_checked\":%s,\"span_in_region\":%s}\n",
                c.pid,static_cast<unsigned long long>(c.birth),OWN_EXPECTED_PROGRAM_SHA,static_cast<unsigned long long>(time),GetCurrentThreadId(),
                record,static_cast<unsigned>(reason),stage,failed,step,q.observed?"true":"false",q.category,returned,error,state,protect,type,
                static_cast<unsigned long long>(q.span),region,q.range_checked?"true":"false",q.range_checked?(q.span_in_region?"true":"false"):"null");
            if(n>0){if(first)selected_diagnostic::output(c,L"source-check-first-failure.json",text,n);
                if(selected)selected_diagnostic::output(c,L"selected-source-check-failure.json",text,n);}
        }
    }
    SetLastError(before);
}
'''
    signature = 'extern "C" uintptr_t OwnForwardProbe(const NativeProbeFrame* supplied,uint32_t record) noexcept {'
    probe = replace_once(probe, signature, helper + signature, pc)
    probe = replace_once(probe,
        '        if(!result.wrapper){forward_diagnostic::binding_stage=1;forward_diagnostic::failed_record_id=static_cast<int>(record);}',
        '        if(!result.wrapper){forward_diagnostic::binding_stage=1;forward_diagnostic::failed_record_id=static_cast<int>(record);\n'
        '            RecordSourceCheckFailure(record,result.reason,1,static_cast<int>(record));}', pc)
    probe = replace_once(probe,
        'result.wrapper=0;result.reason=BindReason::OriginalSourceMismatch;forward_diagnostic::binding_stage=2;forward_diagnostic::failed_record_id=static_cast<int>(i);break;',
        'result.wrapper=0;result.reason=BindReason::OriginalSourceMismatch;forward_diagnostic::binding_stage=2;forward_diagnostic::failed_record_id=static_cast<int>(i);\n'
        '                    RecordSourceCheckFailure(record,result.reason,2,static_cast<int>(i));break;', pc)
    return binding, probe, bc, pc


def sibling_candidate():
    """Reuse CP72's exact byte-delta validator with only its destination name changed."""
    recipe = ROOT / 'tools/local_native_cp72_product_binding/prepare.py'
    raw = recipe.read_bytes()
    need(sha(raw) == '9581103af0e42e2a6b967c3c147e0ac7cda9ae8c994693d43df11bc3d42634ea',
         'EXACT_CP72_IMPORT_DELTA_SOURCE_REQUIRED')
    tree = ast.parse(raw, str(recipe))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'import_delta')
    destination = [n for n in ast.walk(fn) if isinstance(n, ast.Constant) and
                   n.value == b'own-login-bridge-cp72.dll\0']
    need(len(destination) == 1, 'ONE_CP72_DESTINATION_LITERAL_REQUIRED')
    destination[0].value = b'own-login-bridge-dg49.dll\0'
    namespace = {'need': need, 'sha': sha}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])), str(recipe), 'exec'), namespace)
    parent_path = ROOT / 'work/local_native_login_state5_ack_candidate/native-login.candidate.bin'
    parent = parent_path.read_bytes()
    parent_sha = '656a64e7c686144615f473902590e23ce0024b907e96ad905f42e84084e8da9d'
    need(sha(parent) == parent_sha, 'EXACT_CP69_PARENT_REQUIRED')
    candidate = bytearray(parent)
    name = b'own-login-bridge-dg49.dll\0'
    for at in (39145184, 39146224):
        candidate[at:at+len(name)] = name
    delta = namespace['import_delta'](parent, candidate)
    pe_path = ROOT / 'tools/local_native_login_candidate/pe.py'
    need(sha(pe_path.read_bytes()) == '357bca0e4b263d2b7d9b9de9437555e129402cfb17c4855082638ddfeca15f70',
         'EXACT_EXISTING_PE_LAYOUT_READER_REQUIRED')
    spec = importlib.util.spec_from_file_location('_diagnostic_sibling_pe', pe_path)
    pe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pe)
    old_pe, new_pe = pe.PE(parent), pe.PE(candidate)
    need(old_pe.sections == new_pe.sections and old_pe.directories == new_pe.directories and
         old_pe.imports() == new_pe.imports(), 'CP72_OUTER_LAYOUT_PRESERVED')
    return bytes(candidate), delta


def prepare(sibling_product=False, connect_role_fix=False, memory_query_diagnostics=False, source_read_retry=False, verified_duplicate=False, duplicate_diagnostics=False, verified_socket_duplicate=False, command_bridge=False, command_quit=False, lifecycle_diagnostics=False, quit_source_retry=False, lifecycle_integrity=False, lifecycle_details=False, lifecycle_pre_self=False, immutable_command_results=False, virtual_protect_callers=False):
    need(not connect_role_fix or sibling_product, 'CONNECT_FIX_REQUIRES_SIBLING_PRODUCT')
    need(not memory_query_diagnostics or connect_role_fix, 'QUERY_DIAGNOSTICS_REQUIRE_CONNECT_FIX')
    need(not immutable_command_results or lifecycle_pre_self,'IMMUTABLE_RESULTS_REQUIRE_EXPLICIT_PRE_SELF_PROFILE')
    if virtual_protect_callers:
        need(lifecycle_pre_self and not immutable_command_results,'VIRTUAL_PROTECT_REQUIRES_PRE_SELF_WITHOUT_IMMUTABLE')
    abi_overlay_enabled = verified_duplicate or verified_socket_duplicate
    out = ROOT / 'work/native-lifecycle-integrity' if lifecycle_integrity else (ROOT / 'work/native-quit-source-retry' if quit_source_retry else (ROOT / 'work/native-lifecycle-diagnostic' if lifecycle_diagnostics else (ROOT / 'work/local_original_session/native-command-quit' if command_quit else (ROOT / 'work/local_original_session/native-command-bridge' if command_bridge else (
        ROOT / 'work/local_original_session/native-verified-socket-duplicate' if verified_socket_duplicate else (
        ROOT / 'work/local_original_session/native-duplicate-diagnostics' if duplicate_diagnostics else (
        ROOT / 'work/local_original_session/native-verified-duplicate' if verified_duplicate else (
        ROOT / 'work/local_original_session/native-source-retry' if source_read_retry else (
        ROOT / 'work/local_original_session/native-memory-query' if memory_query_diagnostics else (
        ROOT / 'work/local_original_session/native-connect-fix' if connect_role_fix else (
        ROOT / 'work/local_original_session/native-sibling' if sibling_product else OUT)))))))))))
    out_relative = out.relative_to(ROOT).as_posix()
    if lifecycle_details:
        need(lifecycle_integrity,'DETAILS_REQUIRE_INTEGRITY')
        out=ROOT/('work/native-lifecycle-pre-self' if lifecycle_pre_self else 'work/native-lifecycle-details')
        out_relative=out.relative_to(ROOT).as_posix()
    if immutable_command_results:
        out=ROOT/'work/native-immutable-sequence'
        out_relative=out.relative_to(ROOT).as_posix()
    if virtual_protect_callers:
        out=ROOT/'work/native-virtual-protect-callers-new-protect'
        out_relative=out.relative_to(ROOT).as_posix()
    source = {}
    for name, pin in PINS.items():
        raw = (BASE / name).read_bytes()
        need(sha(raw) == pin, 'FROZEN_CP49_SOURCE_CHANGED:' + name)
        source[name] = raw.decode('utf-8')
    need(not out.exists(), 'NEW_DIAGNOSTIC_BUILD_DIRECTORY_REQUIRED')
    # In-memory TextIO normalization matches the frozen file's logical lines.
    binding = source['binding.hpp'].replace('\r\n', '\n')
    probe = source['probe.cpp'].replace('\r\n', '\n')
    binding_new, binding_changes = binding_overlay(binding)
    probe_new, probe_changes = probe_overlay(probe)
    if connect_role_fix:
        binding_new, probe_new, bc, pc = connect_role_overlay(binding_new, probe_new)
        binding_changes += bc
        probe_changes += pc
    if memory_query_diagnostics:
        binding_new, probe_new, bc, pc = memory_query_overlay(binding_new, probe_new)
        binding_changes += bc
        probe_changes += pc
    if source_read_retry:
        from source_retry import overlay
        binding_new, probe_new, bc, pc = overlay(binding_new, probe_new, replace_once)
        binding_changes += bc
        probe_changes += pc
    abi = source['abi_bridge_v2.cpp'].replace('\r\n', '\n')
    abi_new, abi_changes = abi, []
    if verified_duplicate:
        from verified_duplicate import overlay
        probe_new, abi_new, pc, ac = overlay(probe_new, abi_new, replace_once)
        probe_changes += pc
        abi_changes += ac
        verify_inverse(abi, abi_new, abi_changes)
    if duplicate_diagnostics:
        from duplicate_diagnostics import overlay
        probe_new, abi_new, pc, ac = overlay(probe_new, abi_new, replace_once)
        probe_changes += pc
        abi_changes += ac
        verify_inverse(abi, abi_new, abi_changes)
    if verified_socket_duplicate:
        from socket_duplicate import overlay
        probe_new, abi_new, pc, ac = overlay(probe_new, abi_new, replace_once)
        probe_changes += pc
        abi_changes += ac
        verify_inverse(abi, abi_new, abi_changes)
    automatic_new = None
    if command_bridge:
        from command_overlay import overlay
        automatic_raw = (BASE / 'auto_ok.hpp').read_bytes()
        need(sha(automatic_raw) == 'e7d348e8609e2c958e8c0d09b6a9c4bf5d6d6b60fd2d352427f265529553cb38',
             'FROZEN_AUTO_CALLBACK_HELPERS_CHANGED')
        automatic = automatic_raw.decode('utf-8').replace('\r\n', '\n')
        abi_new, automatic_new, ac, uc = overlay(abi_new, automatic, replace_once)
        abi_changes += ac
        verify_inverse(abi, abi_new, abi_changes)
        verify_inverse(automatic, automatic_new, uc)
    verify_inverse(binding, binding_new, binding_changes)
    verify_inverse(probe, probe_new, probe_changes)
    sibling = None
    if sibling_product:
        candidate, delta = sibling_candidate()
        identity_raw = (BASE / 'bridge_candidate_v2.hpp').read_bytes()
        need(sha(identity_raw) == 'e63c79e0eeffd51d119bbe3824ebbca99c119efb455845ba4a5265ac0355a394',
             'EXACT_CP49_IDENTITY_HEADER_REQUIRED')
        old_sha = '656a64e7c686144615f473902590e23ce0024b907e96ad905f42e84084e8da9d'
        identity = identity_raw.decode('utf-8')
        need(identity.count(old_sha) == 1, 'ONE_CANDIDATE_SHA_LITERAL_REQUIRED')
        identity_new = identity.replace(old_sha, sha(candidate), 1)
        need(identity_new.replace(sha(candidate), old_sha, 1) == identity, 'IDENTITY_ONLY_SHA_DELTA')
        sibling = {'candidate_sha256': sha(candidate), 'candidate_size': len(candidate),
                   'candidate_path': str(out / 'native-login.candidate.bin'),
                   'dll_basename': 'own-login-bridge-dg49.dll', 'import_delta': delta,
                   'outer_layout_import_descriptors_preserved': True}
    out.mkdir(parents=True, exist_ok=False)
    write_new(out / 'binding.hpp', binding_new)
    write_new(out / 'probe.cpp', probe_new)
    if abi_overlay_enabled:
        write_new(out / 'abi_bridge_v2.cpp', abi_new)
    if command_bridge:
        write_new(out / 'auto_ok.hpp', automatic_new)
    if lifecycle_diagnostics:
        native=Path(__file__).parent
        guard=(native/'background_guard.hpp').read_text(encoding='utf-8')
        need(sha((native/'background_guard.hpp').read_bytes())=='b161ea36c2a8c33c5f383c8820a2955da51a965a8b36854256af134785cf8c9d','LIFECYCLE_BASE_GUARD_PIN')
        command=(native/'command_bridge.hpp').read_text(encoding='utf-8')
        if immutable_command_results:
            need(sha((native/'command_bridge.hpp').read_bytes())=='2d341306836f31d567cee31542b1ccb92efb966fa80914801b6ff7a6f2dede71','IMMUTABLE_EXACT_LIVE_COMMAND_SOURCE_REQUIRED')
        guard_new, command_new, gc, cc=lifecycle_overlay(guard,command)
        verify_inverse(guard,guard_new,gc);verify_inverse(command,command_new,cc)
        quit_original=(native/'quit_command.hpp').read_text(encoding='utf-8')
        quit_new,qc,quit_phases=quit_diagnostic_overlay(quit_original)
        verify_inverse(quit_original,quit_new,qc)
        if quit_source_retry:
            quit_retry,command_retry,qrc,crc=quit_retry_overlay(quit_new,command_new)
            verify_inverse(quit_new,quit_retry,qrc);verify_inverse(command_new,command_retry,crc)
            quit_new,command_new=quit_retry,command_retry
            quit_phases.update({82:'bounded retry SafeCopy failed',83:'current typed proof changed before/after retry'})
        if lifecycle_integrity:
            integrity_guard,integrity_command,igc,icc=integrity_overlay(guard_new,command_new,lifecycle_details,lifecycle_pre_self)
            verify_inverse(guard_new,integrity_guard,igc);verify_inverse(command_new,integrity_command,icc)
            guard_new,command_new=integrity_guard,integrity_command
            write_new(out/'baseline-lifecycle_diagnostics.hpp',(native/'lifecycle_diagnostics.hpp').read_text(encoding='utf-8'))
        if immutable_command_results:
            helper=(native/'immutable_command_results.hpp').read_bytes()
            with (out/'immutable_command_results.hpp').open('xb') as stream:stream.write(helper)
            command_new,immutable_changes=immutable_results_overlay(command_new,out_relative)
            write_new(out/'immutable-overlay.json',json.dumps({'inverse_identical':True,'output_block_occurrences':1,'capability_format_occurrences':1,'helper_sha256':sha(helper),'overlay_order':['lifecycle','quit_source_retry','integrity_pre_self','immutable_results'],'changes':immutable_changes},indent=2)+'\n')
        if virtual_protect_callers:
            need(sha((native/'vendor/detours/src/detours.cpp').read_bytes())=='df415e05f985afe88f4b03ba34d6f5abce47edda11cd66d4f72902b801113eb7','VIRTUAL_PROTECT_PINNED_DETOURS_X64_REQUIRED')
            with (out/'virtual_protect_callers.hpp').open('xb') as stream:stream.write((native/'virtual_protect_callers.hpp').read_bytes())
            vg,vc,vgc,vcc=virtual_protect_overlay(guard_new,command_new,out_relative)
            verify_inverse(guard_new,vg,vgc);verify_inverse(command_new,vc,vcc)
            guard_new,command_new=vg,vc
            write_new(out/'observer-overlay.json',json.dumps({'guard_changes':vgc,'command_changes':vcc,'inverse_identical':True},indent=2)+'\n')
        write_new(out/'background_guard.hpp',guard_new);write_new(out/'command_bridge.hpp',command_new)
        write_new(out/'quit_command.hpp',quit_new)
        write_new(out/'quit-phases.json',json.dumps(quit_phases,indent=2)+'\n')
    # MSVC aliases route every nested quoted include to these two overlays;
    # all remaining implementation, headers, ASM and .def stay at frozen paths.
    wrapper = '''#pragma include_alias("binding.hpp", "work/local_original_session/native-build/binding.hpp")
#pragma include_alias("probe.cpp", "work/local_original_session/native-build/probe.cpp")
#include "tools/local_native_login_state5_ack_bridge/abi_bridge_v2.cpp"
'''
    wrapper = wrapper.replace('work/local_original_session/native-build', out_relative)
    if abi_overlay_enabled:
        wrapper = wrapper.replace('tools/local_native_login_state5_ack_bridge/abi_bridge_v2.cpp',
                                  out_relative + '/abi_bridge_v2.cpp')
    if command_bridge:
        wrapper = '#pragma include_alias("auto_ok.hpp", "' + out_relative + '/auto_ok.hpp")\n' + wrapper
    if lifecycle_diagnostics:
        wrapper = ('#pragma include_alias("tools/local_original_session/native/background_guard.hpp", "'+out_relative+'/background_guard.hpp")\n'
            '#pragma include_alias("tools/local_original_session/native/quit_command.hpp", "'+out_relative+'/quit_command.hpp")\n'
            '#pragma include_alias("tools/local_original_session/native/command_bridge.hpp", "'+out_relative+'/command_bridge.hpp")\n'+wrapper)
    if lifecycle_details:
        # Pin the shared header inside this artifact; future source changes do not
        # silently change a rebuild of this candidate.
        write_new(out/'snapshot-lifecycle_diagnostics.hpp',(ROOT/'tools/local_original_session/native/lifecycle_diagnostics.hpp').read_text(encoding='utf-8'))
        wrapper=('#pragma include_alias("tools/local_original_session/native/lifecycle_diagnostics.hpp", "'+out_relative+'/snapshot-lifecycle_diagnostics.hpp")\n'+wrapper)
    if sibling_product:
        with (out / 'native-login.candidate.bin').open('xb') as stream:
            stream.write(candidate)
        write_new(out / 'bridge_candidate_v2.hpp', identity_new)
        wrapper = ('#pragma include_alias("bridge_candidate_v2.hpp", "' + out_relative +
                   '/bridge_candidate_v2.hpp")\n' + wrapper)
        write_new(out / 'bridge.def', source['bridge.def'].replace('LIBRARY own-login-bridge-cp49',
                                                                  'LIBRARY own-login-bridge-dg49', 1))
    write_new(out / 'diagnostic.cpp', wrapper)
    recipe = source['build.cmd'].replace('\r\n', '\n')
    recipe = recipe.replace('work\\local_native_login_state5_ack_bridge\\',
                            'work\\local_original_session\\native-build\\')
    recipe = recipe.replace('tools\\local_native_login_state5_ack_bridge\\abi_bridge_v2.cpp',
                            'work\\local_original_session\\native-build\\diagnostic.cpp')
    recipe = recipe.replace(' /LD ', ' /LD /I. /Itools\\local_native_login_state5_ack_bridge ')
    # Same existing MSVC flags, ASM source and .def; only outputs and TU differ.
    need('tools\\local_native_login_state5_ack_bridge\\guard_template.asm' in recipe and
         '/def:tools\\local_native_login_state5_ack_bridge\\bridge.def' in recipe and
         recipe.count('/I.') == 1, 'PRESERVED_CP49_RECIPE_REQUIRED')
    recipe = recipe.replace('work\\local_original_session\\native-build', out_relative.replace('/', '\\'))
    if sibling_product:
        recipe = recipe.replace('own-login-bridge-cp49', 'own-login-bridge-dg49')
        recipe = recipe.replace('/def:tools\\local_native_login_state5_ack_bridge\\bridge.def',
                                '/def:' + out_relative.replace('/', '\\') + '\\bridge.def')
    if command_bridge:
        recipe = recipe.replace('/I. ', '/I. /Itools\\local_original_session\\native\\vendor\\detours\\src ')
        recipe = recipe.replace('user32.lib /link',
            'user32.lib tools\\local_original_session\\native\\vendor\\detours\\lib.X64\\detours.lib /link')
    write_new(out / 'build.cmd', recipe)
    abi_include = out_relative + '/abi_bridge_v2.cpp' if abi_overlay_enabled else (
        'tools/local_native_login_state5_ack_bridge/abi_bridge_v2.cpp')
    fixture_aliases = wrapper.split('#include ', 1)[0] + (
        '#pragma include_alias("abi_bridge_v2.cpp", "' + abi_include + '")\n')
    write_new(out / 'fixture-aliases.hpp', fixture_aliases)
    fixture_recipe = '''@echo off
call "C:\\Program Files\\Microsoft Visual Studio\\2022\\Community\\VC\\Auxiliary\\Build\\vcvars64.bat" >nul
if errorlevel 1 exit /b 2
cl /nologo /std:c++17 /utf-8 /W4 /WX /EHsc /O2 /MD /c /I. /Itools\\local_native_login_state5_ack_bridge /FIwork\\local_original_session\\native-build\\fixture-aliases.hpp /Fo:work\\local_original_session\\native-build\\key_mock.obj tools\\local_native_login_key_invoke_boundary\\key_mock.cpp
exit /b %errorlevel%
'''
    fixture_recipe = fixture_recipe.replace('work\\local_original_session\\native-build',
                                            out_relative.replace('/', '\\'))
    if command_bridge:
        fixture_recipe = fixture_recipe.replace('/I. ', '/I. /Itools\\local_original_session\\native\\vendor\\detours\\src ')
    write_new(out / 'compile-fixture.cmd', fixture_recipe)
    if connect_role_fix:
        write_connect_fixture(out)
    if source_read_retry:
        from source_retry import write_fixture
        write_fixture(out, out_relative, write_new)
    if verified_duplicate:
        from verified_duplicate import write_fixture
        write_fixture(out, out_relative, write_new)
    if verified_socket_duplicate:
        from socket_duplicate import write_fixture
        write_fixture(out, out_relative, write_new)
    if lifecycle_pre_self:
        write_pre_self_fixture(out,out_relative)
    elif lifecycle_details:
        write_details_fixture(out,out_relative)
    elif lifecycle_integrity:
        write_integrity_fixture(out,out_relative)
    elif quit_source_retry:
        write_quit_retry_fixture(out,out_relative)
    elif lifecycle_diagnostics:
        write_lifecycle_fixture(out, out_relative)
    elif command_quit:
        from quit_fixture import write_fixture
        write_fixture(out, out_relative, write_new)
    elif command_bridge:
        from command_overlay import write_fixture
        write_fixture(out, out_relative, write_new)
    if immutable_command_results:
        write_immutable_fixture(out,out_relative)
    if virtual_protect_callers:
        write_virtual_protect_fixture(out,out_relative)
    report = {
        'schema': 'cp49-source-check-diagnostic-build-v1', 'status': 'SOURCE_PREPARED_NO_NATIVE_EXECUTION',
        'frozen_source_sha256': PINS, 'source_inverse_identical': True,
        'existing_check_order': ['Executable', 'SafeCopy', 'memcmp'],
        'guard_outcome_or_publication_changed': connect_role_fix, 'additional_memory_reads': 0,
        'diagnostic_fields': {'source_check_step': [0, 1, 2, 3], 'source_check_passed': 'boolean'},
        'sibling_product': sibling,
        'connect_role_fix': connect_role_fix,
        'memory_query_diagnostics': memory_query_diagnostics,
        'source_read_retry': source_read_retry,
        'verified_duplicate': verified_duplicate,
        'duplicate_diagnostics': duplicate_diagnostics,
        'verified_socket_duplicate': verified_socket_duplicate,
        'command_bridge': command_bridge,
        'command_quit': command_quit,
        'lifecycle_diagnostics': lifecycle_diagnostics,
        'quit_source_retry': quit_source_retry,
        'lifecycle_integrity': lifecycle_integrity,
        'lifecycle_details': lifecycle_details,
        'lifecycle_pre_self': lifecycle_pre_self,
        'additional_callable_publication': 0,
        'generated_sha256': {p.name: sha(p.read_bytes()) for p in out.iterdir() if p.is_file()},
    }
    if connect_role_fix:
        report['diagnostic_fields'].update(current_original_verified='boolean',
            prior_all_roles_verified='boolean', connect_role_revalidated='boolean')
    if memory_query_diagnostics:
        report.update(diagnostic_delta_guard_outcome_changed=False,
            additional_virtual_queries=0, diagnostic_additional_game_memory_reads=0,
            source_query_outputs=['source-check-first-failure.json', 'selected-source-check-failure.json'],
            query_failure_categories={0: 'not observed', 1: 'empty span', 2: 'span overflow',
                3: 'VirtualQuery failed', 4: 'not committed', 5: 'guard', 6: 'noaccess',
                7: 'region end overflow', 8: 'span outside region', 9: 'protection excluded', 10: 'pass'},
            source_delta_counts={'binding.hpp': len(binding_changes), 'probe.cpp': len(probe_changes)})
    if source_read_retry:
        report.update(diagnostic_delta_guard_outcome_changed=True,
            source_retry_requires_full_validation=True, connect_only_preservation_enabled=True,
            source_retry_additional_read_budget='one per unique prior-verified original span per probe invocation',
            additional_game_memory_reads='bounded source retry only; zero when strict eligibility fails',
            additional_virtual_queries='only the bounded repeat of existing validation',
            no_new_original_callable=True, protection_writes=0)
    if verified_duplicate:
        report.update(fresh_verified_duplicate=True,
            verified_task_borrow='only within original Task call; existing Held pair; nested/exception restore',
            legacy_duplicate_and_source_override_preserved=True)
        report['source_delta_counts']['abi_bridge_v2.cpp'] = len(abi_changes)
    if duplicate_diagnostics:
        report.update(duplicate_diagnostic_guard_delta=False, duplicate_diagnostic_additional_game_memory_reads=0,
            duplicate_diagnostic_additional_queries=0, existing_duplicate_fixture_result_reused=True,
            duplicate_diagnostic_fields=['fresh_duplicate_reason', 'fresh_duplicate_owner_bits',
                'fresh_duplicate_input_port', 'verified_task_scope_present'],
            task_diagnostic_maximum_each=8)
    if verified_socket_duplicate:
        report.update(fresh_verified_socket_duplicate=True,
            basis='existing legacy owned-connected socket predicate plus full current Connect and prior all9 proof',
            additional_task_scope_or_getter=False, legacy_duplicate_and_source_override_preserved=True)
        report['source_delta_counts']['abi_bridge_v2.cpp'] = len(abi_changes)
    if command_bridge:
        report.update(internal_command_schema='own-internal-command-v1', command_message='LC-Owned-Internal-Command-v1',
            command_supported=[1,2,4], command_quit_contract='UNKNOWN_UNSUPPORTED',
            background_guard='DETOURS_PUBLIC_USER32_EXPORTS_REQUIRES_MAIN_REVIEW', actual_game_execution_permitted=False,
            automatic_callback_inverse_identical=True, legacy_pointer_messages_installed=False,
            additional_game_memory_reads='bounded UI-thread scene/object/source/window validation and existing source retry',
            protection_writes='official Detours public User32 exports only; original game protection writes zero',
            additional_original_game_callable_publication=0,
            command_guard_metadata=['background_guard_installed','hooks_count','protected_exports','blocked_display_calls','blocked_input_calls'],
            facade_source_sha256={p.name: sha(p.read_bytes()) for p in (
                Path(__file__).parent/'command_bridge.hpp', Path(__file__).parent/'background_guard.hpp')})
    if command_quit:
        from quit_anchors import generate
        anchor_text, anchor_proof = generate()
        need(anchor_text == (Path(__file__).parent/'quit_source_anchors.hpp').read_text(encoding='utf-8'), 'QUIT_SOURCE_ANCHOR_GENERATOR_MATCH')
        report.update(command_supported=[1,2,3,4],command_quit_contract='SOURCE_BOUND_SCENE_SPECIFIC_ORIGINAL_CALLBACK',
            quit_formal_abi_inference='general/Land callbacks use nullptr unused arguments; full callback bodies source-verified',
            quit_final_live_callable_required=True, quit_after_callback_game_reads_or_releases=0, quit_anchor_proof=anchor_proof)
    if lifecycle_diagnostics:
        report.update(lifecycle_api_targets=['Kernel32!CreateProcessW','Kernel32!CreateProcessA','Kernel32!ExitProcess'],
            lifecycle_event_limit=16,lifecycle_exit_reserved_slot=15,lifecycle_passthrough=True,
            lifecycle_argument_content_persisted=False,lifecycle_separate_transaction=False,
            background_guard_logical_exports_unchanged=18,lifecycle_hooks_count=3)
    if immutable_command_results:
        report.update(immutable_command_results=True,command_result_mode='immutable-sequence-v1',immutable_helper_sha256=sha(helper),live_command_source_modified=False)
    if virtual_protect_callers:
        report.update(virtual_protect_callers=True,optional_transaction=True,core_failure_policy_unchanged=True,actual_game_execution_permitted=False)
    write_new(out / 'source-report.json', json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'directory': str(out),
                      'changed_source_files': ['binding.hpp', 'probe.cpp'] + (['abi_bridge_v2.cpp'] if abi_overlay_enabled else []),
                      'source_inverse_identical': True, 'sibling_product': sibling}))


def write_connect_fixture(out):
    """Five assertions against the actual production helper; no game or arbitrary calls."""
    relative = out.relative_to(ROOT).as_posix()
    fixture = '''#include "OUTPUT/binding.hpp"
#include <cstdio>
int main() {
    OriginalForwardBinding b;
    BindingResult fresh;fresh.wrapper=0x2000;fresh.base=0x100000;fresh.original=0x103000;fresh.reason=BindReason::Bound;
    BindingResult failed;failed.base=fresh.base;failed.reason=BindReason::OriginalSourceMismatch;
    b.base=fresh.base;b.originals[0]=fresh.original;b.all_roles_verified_base=fresh.base;
    unsigned checks=0;
    if(!b.allow_current_connect(fresh,failed,0,2,2))return 1;++checks;
    b.all_roles_verified_base=0;b.originals[7]=0x107000;b.originals[8]=0x108000;
    if(b.allow_current_connect(fresh,failed,0,2,2))return 2;++checks;
    b.all_roles_verified_base=fresh.base;auto own_failed=fresh;own_failed.wrapper=0;own_failed.reason=BindReason::OriginalSourceMismatch;
    if(b.allow_current_connect(own_failed,failed,0,1,0))return 3;++checks;
    b.base=fresh.base+0x100000;
    if(b.allow_current_connect(fresh,failed,0,2,2))return 4;++checks;
    b.base=fresh.base;b.originals[0]=fresh.original+8;
    if(b.allow_current_connect(fresh,failed,0,2,2))return 5;++checks;
    std::printf("{\\"status\\":\\"PASS\\",\\"checks\\":%u,\\"game_access\\":false}\\n",checks);
    return 0;
}
'''.replace('OUTPUT', relative)
    write_new(out / 'connect_role_mock.cpp', fixture)
    recipe = '''@echo off
call "C:\\Program Files\\Microsoft Visual Studio\\2022\\Community\\VC\\Auxiliary\\Build\\vcvars64.bat" >nul
if errorlevel 1 exit /b 2
cl /nologo /std:c++17 /utf-8 /W4 /WX /EHsc /O2 /MD /I. /Itools\\local_native_login_state5_ack_bridge /Fe:OUTPUT\\connect_role_mock.exe /Fo:OUTPUT\\connect_role_mock.obj OUTPUT\\connect_role_mock.cpp
exit /b %errorlevel%
'''.replace('OUTPUT', relative.replace('/', '\\'))
    write_new(out / 'build-connect-fixture.cmd', recipe)


def write_lifecycle_fixture(out, relative):
    source=r'''#define OWN_SELECTED_HOST_TEST
#define OWN_KEY_HOST_TEST
#include "OUTPUT/abi_bridge_v2.cpp"
#include <cstdio>
namespace selected_diagnostic {ContextFn test_context=nullptr;OutputFn test_output=nullptr;}
namespace key_diagnostic {void(*test_output)(const char*,const char*,int) noexcept=nullptr;}
uintptr_t test_key_version_return=0;
static owned_lifecycle::Event seen{};static unsigned events=0,originals=0,order=0;static bool exact=false,success=false;
static DWORD enteredError=0;static UINT exitedCode=0;
static void TestSink(const owned_lifecycle::Event& event) noexcept {seen=event;++events;order=1;SetLastError(9999);}
static void FaultSink(const owned_lifecycle::Event&) noexcept {RaiseException(0xe0424242,0,0,nullptr);}
static BOOL WINAPI W(LPCWSTR a,LPWSTR b,LPSECURITY_ATTRIBUTES c,LPSECURITY_ATTRIBUTES d,BOOL e,DWORD f,LPVOID g,LPCWSTR h,LPSTARTUPINFOW i,LPPROCESS_INFORMATION j){
    ++originals;enteredError=GetLastError();exact=a==reinterpret_cast<LPCWSTR>(1)&&b==reinterpret_cast<LPWSTR>(2)&&c==reinterpret_cast<LPSECURITY_ATTRIBUTES>(3)&&d==reinterpret_cast<LPSECURITY_ATTRIBUTES>(4)&&e==7&&f==8&&g==reinterpret_cast<void*>(9)&&h==reinterpret_cast<LPCWSTR>(10)&&i==reinterpret_cast<LPSTARTUPINFOW>(11)&&j;
    SetLastError(4321);return success?TRUE:FALSE;
}
static BOOL WINAPI A(LPCSTR a,LPSTR b,LPSECURITY_ATTRIBUTES c,LPSECURITY_ATTRIBUTES d,BOOL e,DWORD f,LPVOID g,LPCSTR h,LPSTARTUPINFOA i,LPPROCESS_INFORMATION j){
    ++originals;enteredError=GetLastError();exact=a==reinterpret_cast<LPCSTR>(1)&&b==reinterpret_cast<LPSTR>(2)&&c==reinterpret_cast<LPSECURITY_ATTRIBUTES>(3)&&d==reinterpret_cast<LPSECURITY_ATTRIBUTES>(4)&&e==7&&f==8&&g==reinterpret_cast<void*>(9)&&h==reinterpret_cast<LPCSTR>(10)&&i==reinterpret_cast<LPSTARTUPINFOA>(11)&&j;
    SetLastError(4321);return success?TRUE:FALSE;
}
static VOID WINAPI Exit(UINT code){++originals;exitedCode=code;enteredError=GetLastError();if(order==1)order=2;}
static unsigned begins=0,updates=0,attaches=0,detaches=0,commits=0,aborts=0,failAt=0;
static LONG WINAPI Begin(){++begins;return 0;}static LONG WINAPI Update(HANDLE){++updates;return 0;}
static LONG WINAPI Attach(PVOID*,PVOID){++attaches;return failAt==attaches?87:0;}
static LONG WINAPI Detach(PVOID*,PVOID){++detaches;return 0;}
static LONG WINAPI Commit(){++commits;return 0;}static LONG WINAPI Abort(){++aborts;return 0;}
int main(){using namespace owned_lifecycle;unsigned checks=0;real_CreateProcessW=W;real_CreateProcessA=A;real_ExitProcess=Exit;sink=TestSink;
    PROCESS_INFORMATION pi{};pi.dwProcessId=77;
    for(unsigned kind=1;kind<=2;++kind)for(unsigned result=0;result<=1;++result){success=result!=0;SetLastError(1234);exact=false;
        const BOOL returned=kind==1?create_w(reinterpret_cast<LPCWSTR>(1),reinterpret_cast<LPWSTR>(2),reinterpret_cast<LPSECURITY_ATTRIBUTES>(3),reinterpret_cast<LPSECURITY_ATTRIBUTES>(4),7,8,reinterpret_cast<void*>(9),reinterpret_cast<LPCWSTR>(10),reinterpret_cast<LPSTARTUPINFOW>(11),&pi):
            create_a(reinterpret_cast<LPCSTR>(1),reinterpret_cast<LPSTR>(2),reinterpret_cast<LPSECURITY_ATTRIBUTES>(3),reinterpret_cast<LPSECURITY_ATTRIBUTES>(4),7,8,reinterpret_cast<void*>(9),reinterpret_cast<LPCSTR>(10),reinterpret_cast<LPSTARTUPINFOA>(11),&pi);
        if(!exact||enteredError!=1234||GetLastError()!=4321||returned!=(success?TRUE:FALSE)||seen.kind!=kind||seen.result!=returned||seen.error!=4321||seen.child_pid!=(success?77u:0u)||seen.child_birth||!seen.caller||!seen.filetime)return 1;++checks;}
    SetLastError(555);order=0;exit_process(1);if(order!=2||enteredError!=555||exitedCode!=1||seen.kind!=3||seen.exit_code!=1)return 2;++checks;
    launch_claims=exit_claim=0;for(int i=0;i<15;++i){if(Claim(1)!=i)return 3;++checks;}
    if(Claim(2)!=-1||Claim(3)!=15||Claim(3)!=-1||Claim(1)!=-1)return 4;++checks;
    char name[129]{};Basename(L"C:\\private\\a\"b.exe",name);if(strcmp(name,"a_b.exe"))return 5;++checks;
    Event noChild;noChild.result=FALSE;Child(noChild,reinterpret_cast<PROCESS_INFORMATION*>(1));if(noChild.child_pid)return 6;++checks;
    PVOID first=nullptr,second=nullptr;owned_background_guard::Entry guards[2]={{"a",&first,nullptr,nullptr,nullptr,{}},{"b",&second,nullptr,nullptr,nullptr,{}}};
    const owned_background_guard::TransactionApi api={Begin,Update,Attach,Detach,Commit,Abort};
    if(owned_background_guard::transact(api,guards,2,false)||begins!=1||updates!=1||attaches!=5||commits!=1||aborts)return 7;++checks;
    begins=updates=attaches=commits=aborts=0;failAt=2;
    if(owned_background_guard::transact(api,guards,2,false)!=87||attaches!=2||commits||aborts!=1)return 8;++checks;
    begins=updates=attaches=commits=aborts=0;failAt=4;
    if(owned_background_guard::transact(api,guards,2,false)!=87||attaches!=4||commits||aborts!=1)return 9;++checks;
    failAt=0;detaches=commits=0;if(owned_background_guard::transact(api,guards,2,true)||detaches!=5||commits!=1)return 10;++checks;
    if(originals!=5||events!=5)return 11;++checks;
    sink=FaultSink;success=false;SetLastError(1234);
    if(create_w(reinterpret_cast<LPCWSTR>(1),reinterpret_cast<LPWSTR>(2),reinterpret_cast<LPSECURITY_ATTRIBUTES>(3),reinterpret_cast<LPSECURITY_ATTRIBUTES>(4),7,8,reinterpret_cast<void*>(9),reinterpret_cast<LPCWSTR>(10),reinterpret_cast<LPSTARTUPINFOW>(11),&pi)||originals!=6||enteredError!=1234||GetLastError()!=4321)return 12;++checks;
    SetLastError(555);exit_process(7);if(originals!=7||enteredError!=555||exitedCode!=7)return 13;++checks;
    internal_command::quit_detail::Proof qp;qp.sceneKind=3;qp.base=0x100000;
    const auto copy=[](void* dst,const void*,size_t size)noexcept{memset(dst,0,size);return true;};
    if(internal_command::quit_detail::SourceProof(qp,[](uintptr_t,size_t)noexcept{return false;},copy)||internal_command::quit_detail::diagnostic_phase!=81||internal_command::quit_detail::diagnostic_step!=1||internal_command::quit_detail::diagnostic_anchor!=0x944b80)return 14;++checks;
    if(internal_command::quit_detail::SourceProof(qp,[](uintptr_t,size_t)noexcept{return true;},[](void*,const void*,size_t)noexcept{return false;})||internal_command::quit_detail::diagnostic_step!=2)return 15;++checks;
    if(internal_command::quit_detail::SourceProof(qp,[](uintptr_t,size_t)noexcept{return true;},copy)||internal_command::quit_detail::diagnostic_step!=3)return 16;++checks;
    internal_command::Request quit;quit.command=3;const auto refusal=internal_command::Execute(quit);
    if(refusal.invoked||refusal.reason!=6||internal_command::quit_detail::diagnostic_phase!=10||internal_command::quit_detail::diagnostic_anchor||internal_command::quit_detail::diagnostic_step)return 17;++checks;
    std::printf("{\"status\":\"PASS\",\"checks\":%u,\"game_or_desktop_operations\":false,\"actual_process_create_or_exit\":false}\n",checks);return 0;
}
'''.replace('OUTPUT',relative)
    write_new(out/'lifecycle_mock.cpp',source)
    recipe='''@echo off
call "C:\\Program Files\\Microsoft Visual Studio\\2022\\Community\\VC\\Auxiliary\\Build\\vcvars64.bat" >nul
if errorlevel 1 exit /b 2
cl /nologo /std:c++17 /utf-8 /W4 /WX /EHsc /O2 /MD /I. /Itools\\local_native_login_state5_ack_bridge /Itools\\local_original_session\\native\\vendor\\detours\\src /FIOUTPUT\\fixture-aliases.hpp /Fe:OUTPUT\\lifecycle_mock.exe /Fo:OUTPUT\\lifecycle_mock.obj OUTPUT\\lifecycle_mock.cpp OUTPUT\\guard.obj user32.lib tools\\local_original_session\\native\\vendor\\detours\\lib.X64\\detours.lib
exit /b %errorlevel%
'''.replace('OUTPUT',relative.replace('/','\\'))
    write_new(out/'build-lifecycle-fixture.cmd',recipe)


def write_quit_retry_fixture(out,relative):
    source=r'''#define OWN_SELECTED_HOST_TEST
#define OWN_KEY_HOST_TEST
#include "OUTPUT/abi_bridge_v2.cpp"
#include <cstdio>
namespace selected_diagnostic {ContextFn test_context=nullptr;OutputFn test_output=nullptr;}
namespace key_diagnostic {void(*test_output)(const char*,const char*,int) noexcept=nullptr;}
uintptr_t test_key_version_return=0;
int main(){namespace qd=internal_command::quit_detail;using internal_command::internal_quit_source::anchors;
    unsigned checks=0,reads=0,freshCalls=0,mode=0;bool cold[2]={true,true},copyFail=false,mismatch=false,hydrate=true;
    qd::Proof proof;proof.base=0x100000;proof.sceneKind=5;uintptr_t allowed[2]{};
    if(qd::RoutePages(2,allowed)!=2||allowed[0]!=0xacb000||allowed[1]!=0x13c000)return 1;++checks;
    const auto reset=[&](){reads=freshCalls=mode=0;cold[0]=cold[1]=true;copyFail=mismatch=false;hydrate=true;};
    const auto code=[&](uintptr_t address,size_t size)noexcept{
        const uintptr_t rva=address-proof.base,page=rva&~uintptr_t(0xfff);const unsigned index=page==allowed[0]?0u:1u;
        if(!cold[index])return true;
        source_diagnostic::Query q;q.observed=q.region_observed=true;q.returned=sizeof(MEMORY_BASIC_INFORMATION);q.span=size;
        q.region_start=proof.base+page;q.region_size=0x1000;q.allocation_base=proof.base;q.category=6;q.state=MEM_COMMIT;q.type=MEM_IMAGE;q.protect=PAGE_NOACCESS;
        switch(mode){case 1:q.type=MEM_PRIVATE;break;case 2:q.state=MEM_RESERVE;break;case 3:q.protect=PAGE_EXECUTE_READ;break;
          case 4:q.protect=PAGE_NOACCESS|PAGE_GUARD;break;case 5:++q.allocation_base;break;case 6:q.category=9;break;
          case 7:++q.span;break;case 8:--q.returned;break;case 9:q.region_size=rva-page;break;
          case 10:q.region_start=UINTPTR_MAX-1;q.region_size=0x1000;break;}
        source_diagnostic::query=q;return false;
    };
    const auto copy=[&](void* to,const void* from,size_t size)noexcept{
        const uintptr_t rva=reinterpret_cast<uintptr_t>(from)-proof.base,page=rva&~uintptr_t(0xfff);const unsigned index=page==allowed[0]?0u:1u;
        const bool retry=cold[index];if(retry){++reads;if(copyFail)return false;if(hydrate)cold[index]=false;}
        for(const auto& a:anchors)if(a.route==2&&a.rva==rva&&a.size==size){memcpy(to,a.bytes,size);if(mismatch&&!retry)*static_cast<unsigned char*>(to)^=1;return true;}
        return false;
    };
    const auto fresh=[&](const qd::Proof&)noexcept{++freshCalls;return true;};
    qd::PageBudget budget;reset();
    if(!qd::VerifySourceRetry(proof,budget,code,copy,fresh)||budget.used!=2||reads!=2||freshCalls!=4)return 2;++checks;
    if(!qd::VerifySourceRetry(proof,budget,code,copy,fresh)||reads!=2||budget.used!=2)return 3;++checks;
    cold[0]=true;if(qd::VerifySourceRetry(proof,budget,code,copy,fresh)||reads!=2)return 4;++checks;
    for(unsigned bad=1;bad<=10;++bad){reset();mode=bad;qd::PageBudget denied;
        if(qd::VerifySourceRetry(proof,denied,code,copy,fresh)||reads||denied.used)return 10+static_cast<int>(bad);++checks;}
    reset();copyFail=true;qd::PageBudget failed;
    if(qd::VerifySourceRetry(proof,failed,code,copy,fresh)||reads!=1||failed.used!=1||qd::diagnostic_phase!=82)return 21;++checks;
    reset();mismatch=true;qd::PageBudget different;
    if(qd::VerifySourceRetry(proof,different,code,copy,fresh)||reads!=1||different.used!=1||qd::diagnostic_step!=3)return 22;++checks;
    reset();hydrate=false;qd::PageBudget notExecutable;
    if(qd::VerifySourceRetry(proof,notExecutable,code,copy,fresh)||reads!=1||notExecutable.used!=1)return 23;++checks;
    reset();qd::PageBudget stale;
    if(qd::VerifySourceRetry(proof,stale,code,copy,[](const qd::Proof&)noexcept{return false;})||reads||stale.used)return 24;++checks;
    reset();qd::PageBudget changed;
    if(qd::VerifySourceRetry(proof,changed,code,copy,[&](const qd::Proof&)noexcept{return ++freshCalls==1;})||reads!=1||changed.used!=1)return 25;++checks;
    reset();qd::PageBudget owner;owner.owner_set=true;owner.owner=proof;owner.owner.root=1;
    if(qd::VerifySourceRetry(proof,owner,code,copy,fresh)||reads||owner.used||qd::diagnostic_phase!=83)return 26;++checks;
    reset();qd::PageBudget full;full.used=2;
    if(qd::VerifySourceRetry(proof,full,code,copy,fresh)||reads)return 27;++checks;
    reset();const auto saved=proof;proof.sceneKind=7;qd::PageBudget unknown;
    if(qd::VerifySourceRetry(proof,unknown,code,copy,fresh)||reads)return 28;++checks;proof=saved;
    std::printf("{\"status\":\"PASS\",\"checks\":%u,\"game_or_desktop_operations\":false,\"actual_source_reads\":false}\n",checks);return 0;
}
'''.replace('OUTPUT',relative)
    write_new(out/'quit_retry_mock.cpp',source)
    recipe='''@echo off
call "C:\\Program Files\\Microsoft Visual Studio\\2022\\Community\\VC\\Auxiliary\\Build\\vcvars64.bat" >nul
if errorlevel 1 exit /b 2
cl /nologo /std:c++17 /utf-8 /W4 /WX /EHsc /O2 /MD /I. /Itools\\local_native_login_state5_ack_bridge /Itools\\local_original_session\\native\\vendor\\detours\\src /FIOUTPUT\\fixture-aliases.hpp /Fe:OUTPUT\\quit_retry_mock.exe /Fo:OUTPUT\\quit_retry_mock.obj OUTPUT\\quit_retry_mock.cpp OUTPUT\\guard.obj user32.lib tools\\local_original_session\\native\\vendor\\detours\\lib.X64\\detours.lib
exit /b %errorlevel%
'''.replace('OUTPUT',relative.replace('/','\\'))
    write_new(out/'build-quit-retry-fixture.cmd',recipe)


def write_integrity_fixture(out,relative):
    source=r'''#define OWN_SELECTED_HOST_TEST
#define OWN_KEY_HOST_TEST
#include "OUTPUT/abi_bridge_v2.cpp"
#include <cstdio>
namespace selected_diagnostic {ContextFn test_context=nullptr;OutputFn test_output=nullptr;}
namespace key_diagnostic {void(*test_output)(const char*,const char*,int) noexcept=nullptr;}
uintptr_t test_key_version_return=0;
static unsigned originals=0,events=0;static DWORD errorIn=0;static HANDLE handleIn=nullptr;static bool unknownSeen=false;
static BOOL WINAPI W(LPCWSTR,LPWSTR,LPSECURITY_ATTRIBUTES,LPSECURITY_ATTRIBUTES,BOOL,DWORD,LPVOID,LPCWSTR,LPSTARTUPINFOW,LPPROCESS_INFORMATION){++originals;errorIn=GetLastError();SetLastError(456);return FALSE;}
static BOOL WINAPI A(LPCSTR,LPSTR,LPSECURITY_ATTRIBUTES,LPSECURITY_ATTRIBUTES,BOOL,DWORD,LPVOID,LPCSTR,LPSTARTUPINFOA,LPPROCESS_INFORMATION){++originals;errorIn=GetLastError();SetLastError(456);return FALSE;}
static VOID WINAPI X(UINT){++originals;errorIn=GetLastError();}
static BOOL WINAPI T(HANDLE handle,UINT){++originals;errorIn=GetLastError();handleIn=handle;SetLastError(456);return FALSE;}
static void FaultSink(const owned_lifecycle::Event& event)noexcept{++events;if(event.kind>=7&&!event.target_known)unknownSeen=true;SetLastError(999);RaiseException(0xe0424242,0,0,nullptr);}
int main(){using namespace owned_lifecycle;unsigned checks=0,reads=0;uintptr_t bad=0,changed=0;
    struct Fake {PVOID code;};Fake guards[17]{},life[8]{};
    for(unsigned i=0;i<17;++i)guards[i].code=reinterpret_cast<PVOID>(uintptr_t(0x10000+i*32));
    for(unsigned i=0;i<8;++i)life[i].code=reinterpret_cast<PVOID>(uintptr_t(0x20000+i*32));
    const auto read=[&](PVOID address,unsigned char* bytes)noexcept{++reads;const auto value=reinterpret_cast<uintptr_t>(address);if(value==bad)return false;
        for(unsigned i=0;i<16;++i)bytes[i]=static_cast<unsigned char>((value>>5)+i+(value==changed?1:0));return true;};
    Baseline state;if(!RecordBaseline(state,guards,17,life,8,read)||reads!=25||!state.captured)return 1;++checks;
    changed=reinterpret_cast<uintptr_t>(guards[0].code);if(!RecordBaseline(state,guards,17,life,8,read)||reads!=25)return 2;++checks;changed=0;
    auto totals=Compare(state.guard,17,read);if(totals.matched!=17||totals.mismatched||totals.unknown)return 3;++checks;
    changed=reinterpret_cast<uintptr_t>(guards[0].code);totals=Compare(state.guard,17,read);if(totals.matched!=16||totals.mismatched!=1||totals.unknown)return 4;++checks;
    changed=0;bad=reinterpret_cast<uintptr_t>(guards[1].code);totals=Compare(state.guard,17,read);if(totals.matched!=16||totals.mismatched||totals.unknown!=1)return 5;++checks;
    Baseline unreadable;RecordBaseline(unreadable,guards,17,life,8,read);bad=0;totals=Compare(unreadable.guard,17,read);if(totals.unknown!=1||totals.matched!=16)return 6;++checks;
    Baseline overflow;if(RecordBaseline(overflow,guards,19,life,8,read)||overflow.captured)return 7;++checks;
    unsigned char local[16]{},copy[16]{};if(!Read16(local,copy)||Read16(nullptr,copy))return 8;++checks;
    HealthClock clock;if(Due(clock,20000))return 9;++checks;clock.ready=500;clock.started=1;
    if(Due(clock,10499)||!Due(clock,10500)||Due(clock,10501)||clock.late!=1)return 10;++checks;
    Entry list[8]{},selected[8]{};for(unsigned i=0;i<8;++i){list[i]=entries[i];list[i].target=list[i].code=reinterpret_cast<PVOID>(uintptr_t(0x30000+i*0x100));}
    unsigned size=0,aliases=0;if(!SelectPhysical(list,8,selected,size,aliases)||size!=8||aliases)return 11;++checks;
    for(unsigned i=3;i<=5;++i)list[i].target=list[i].code=list[i-3].code;list[7].target=list[7].code=list[6].code;
    if(!SelectPhysical(list,8,selected,size,aliases)||size!=4||aliases!=184)return 12;++checks;
    list[1].code=list[0].code;if(SelectPhysical(list,8,selected,size,aliases))return 13;++checks;
    list[1].code=list[1].target;list[3].code=reinterpret_cast<PVOID>(0x90000);if(SelectPhysical(list,8,selected,size,aliases))return 14;++checks;
    real_CreateProcessW=real_KB_CreateProcessW=W;real_CreateProcessA=real_KB_CreateProcessA=A;real_ExitProcess=real_KB_ExitProcess=X;real_TerminateProcess=real_KB_TerminateProcess=T;sink=FaultSink;
    for(unsigned i=0;i<8;++i){SetLastError(123);const unsigned before=originals;BOOL result=FALSE;
        switch(i){case 0:result=create_w(nullptr,nullptr,nullptr,nullptr,FALSE,0,nullptr,nullptr,nullptr,nullptr);break;
        case 1:result=create_a(nullptr,nullptr,nullptr,nullptr,FALSE,0,nullptr,nullptr,nullptr,nullptr);break;case 2:exit_process(1);break;
        case 3:result=kb_create_w(nullptr,nullptr,nullptr,nullptr,FALSE,0,nullptr,nullptr,nullptr,nullptr);break;
        case 4:result=kb_create_a(nullptr,nullptr,nullptr,nullptr,FALSE,0,nullptr,nullptr,nullptr,nullptr);break;case 5:kb_exit_process(1);break;
        case 6:result=terminate_process(GetCurrentProcess(),1);break;case 7:result=kb_terminate_process(reinterpret_cast<HANDLE>(1),1);break;}
        const DWORD after=GetLastError();if(originals!=before+1||errorIn!=123||result||entered[i]!=1||(i!=2&&i!=5&&after!=456))return 20+static_cast<int>(i);++checks;}
    if(!unknownSeen||handleIn!=reinterpret_cast<HANDLE>(1)||events!=10||statistics[6]!=10)return 29;++checks;
    std::printf("{\"status\":\"PASS\",\"checks\":%u,\"game_or_desktop_operations\":false,\"actual_process_create_or_exit\":false}\n",checks);return 0;
}
'''.replace('OUTPUT',relative)
    write_new(out/'integrity_mock.cpp',source)
    recipe='''@echo off
call "C:\\Program Files\\Microsoft Visual Studio\\2022\\Community\\VC\\Auxiliary\\Build\\vcvars64.bat" >nul
if errorlevel 1 exit /b 2
cl /nologo /std:c++17 /utf-8 /W4 /WX /EHsc /O2 /MD /I. /Itools\\local_native_login_state5_ack_bridge /Itools\\local_original_session\\native\\vendor\\detours\\src /FIOUTPUT\\fixture-aliases.hpp /Fe:OUTPUT\\integrity_mock.exe /Fo:OUTPUT\\integrity_mock.obj OUTPUT\\integrity_mock.cpp OUTPUT\\guard.obj user32.lib tools\\local_original_session\\native\\vendor\\detours\\lib.X64\\detours.lib
exit /b %errorlevel%
'''.replace('OUTPUT',relative.replace('/','\\'))
    write_new(out/'build-integrity-fixture.cmd',recipe)


def write_details_fixture(out,relative):
    source=r'''#define OWN_SELECTED_HOST_TEST
#define OWN_KEY_HOST_TEST
#include "OUTPUT/abi_bridge_v2.cpp"
#include <cstdio>
namespace selected_diagnostic {ContextFn test_context=nullptr;OutputFn test_output=nullptr;}
namespace key_diagnostic {void(*test_output)(const char*,const char*,int) noexcept=nullptr;}
uintptr_t test_key_version_return=0;
#define CHECK(value) do {if(!(value))return static_cast<int>(checks+1);++checks;} while(false)
int main(){using namespace owned_lifecycle;unsigned checks=0;
    MEMORY_BASIC_INFORMATION info{};info.BaseAddress=info.AllocationBase=reinterpret_cast<PVOID>(0x1000);
    info.RegionSize=0x1000;info.State=MEM_COMMIT;info.Type=MEM_IMAGE;info.Protect=PAGE_EXECUTE_READ;
    CHECK(DetailSpan(info,0x1ff0,16,true));CHECK(!DetailSpan(info,0x1ff1,16,true));CHECK(!DetailSpan(info,0xfff,16,true));
    CHECK(!DetailSpan(info,UINTPTR_MAX-4,16,true));info.RegionSize=SIZE_MAX;CHECK(!DetailSpan(info,0x1000,16,true));info.RegionSize=0x1000;
    info.State=MEM_RESERVE;CHECK(!DetailSpan(info,0x1000,16,true));info.State=MEM_COMMIT;
    info.Type=MEM_PRIVATE;CHECK(!DetailSpan(info,0x1000,16,true));info.Type=MEM_IMAGE;
    info.Protect=PAGE_NOACCESS;CHECK(!DetailSpan(info,0x1000,16,true));CHECK(DetailSpan(info,0x1000,1,true,false));info.Protect=PAGE_EXECUTE_READ|PAGE_GUARD;
    CHECK(!DetailSpan(info,0x1000,16,true));info.Protect=PAGE_EXECUTE_READ;
    unsigned char a[16]{},b[16]{};CHECK(DifferenceMask(a,b)==0);b[0]=1;b[15]=1;CHECK(DifferenceMask(a,b)==32769);
    b[0]=0;CHECK((DifferenceMask(a,b)&31)==0);uintptr_t target=0;
    CHECK(RelativeTarget(0x1000,5,-5,target)&&target==0x1000);CHECK(!RelativeTarget(UINTPTR_MAX-3,5,0,target));
    CHECK(!RelativeTarget(0,2,-3,target));CHECK(!RelativeTarget(UINTPTR_MAX-5,5,1,target));
    a[0]=0xe9;int32_t rel=-10;memcpy(a+1,&rel,4);auto branch=FirstBranch(0x1000,a);CHECK(branch.kind==1&&branch.known&&branch.target==0xffb);
    a[0]=0xeb;a[1]=0xfe;branch=FirstBranch(0x1000,a);CHECK(branch.kind==2&&branch.known&&branch.target==0x1000);
    memset(a,0,16);a[0]=0xff;a[1]=0x25;rel=2;memcpy(a+2,&rel,4);target=0x5678;memcpy(a+8,&target,sizeof(target));
    branch=FirstBranch(0x1000,a);CHECK(branch.kind==3&&branch.known&&branch.target==0x5678);
    rel=3;memcpy(a+2,&rel,4);branch=FirstBranch(0x1000,a);CHECK(branch.kind==3&&!branch.known);
    memset(a,0,16);CHECK(FirstBranch(0x1000,a).kind==0);CHECK(!strcmp(KnownModule(reinterpret_cast<PVOID>(0x1234)),"UNKNOWN"));
    char text[256]{},row[129]{};size_t used=0;CHECK(AppendDetail(text,sizeof(text),used,row,128)&&used==128);
    CHECK(!AppendDetail(text,sizeof(text),used,row,1)&&used==128);
    forward_diagnostic::Context first{},second{};first.pid=second.pid=1;first.birth=second.birth=2;
    CHECK(SameDetailContext(first,second));second.birth=3;CHECK(!SameDetailContext(first,second));
    struct Fake {PVOID code;const char* name;Region regions[4];};Fake entry{};entry.code=reinterpret_cast<PVOID>(0x1120);entry.name="fixture";entry.regions[2].allocation=reinterpret_cast<PVOID>(0x1000);
    Signature signature;signature.address=entry.code;BaselineIdentity(signature,entry);
    CHECK(signature.allocation==entry.regions[2].allocation&&signature.rva==0x120&&!strcmp(signature.module,"UNKNOWN"));
    std::printf("{\"status\":\"PASS\",\"checks\":%u,\"game_or_desktop_operations\":false,\"actual_entry_reads_or_queries\":false}\n",checks);return 0;
}
'''.replace('OUTPUT',relative)
    write_new(out/'details_mock.cpp',source)
    recipe='''@echo off
call "C:\\Program Files\\Microsoft Visual Studio\\2022\\Community\\VC\\Auxiliary\\Build\\vcvars64.bat" >nul
if errorlevel 1 exit /b 2
cl /nologo /std:c++17 /utf-8 /W4 /WX /EHsc /O2 /MD /I. /Itools\\local_native_login_state5_ack_bridge /Itools\\local_original_session\\native\\vendor\\detours\\src /FIOUTPUT\\fixture-aliases.hpp /Fe:OUTPUT\\details_mock.exe /Fo:OUTPUT\\details_mock.obj OUTPUT\\details_mock.cpp OUTPUT\\guard.obj user32.lib tools\\local_original_session\\native\\vendor\\detours\\lib.X64\\detours.lib
exit /b %errorlevel%
'''.replace('OUTPUT',relative.replace('/','\\'))
    write_new(out/'build-details-fixture.cmd',recipe)


def write_pre_self_fixture(out,relative):
    source=r'''#define OWN_SELECTED_HOST_TEST
#define OWN_KEY_HOST_TEST
#include "OUTPUT/abi_bridge_v2.cpp"
#include <cstdio>
namespace selected_diagnostic {ContextFn test_context=nullptr;OutputFn test_output=nullptr;}
namespace key_diagnostic {void(*test_output)(const char*,const char*,int) noexcept=nullptr;}
uintptr_t test_key_version_return=0;
#define CHECK(value) do {if(!(value))return static_cast<int>(checks+1);++checks;} while(false)
int main(){using namespace owned_lifecycle;unsigned checks=0,reads=0;unsigned char current[16]{};
    struct Fake {PVOID code;const char* name;Region regions[4];};Fake guards[17]{},life[8]{};
    for(unsigned i=0;i<17;++i){guards[i].code=reinterpret_cast<PVOID>(uintptr_t(0x10000+i*32));guards[i].name="guard";guards[i].regions[2].allocation=reinterpret_cast<PVOID>(0x1000);}
    for(unsigned i=0;i<8;++i){life[i].code=reinterpret_cast<PVOID>(uintptr_t(0x20000+i*32));life[i].name="life";life[i].regions[2].allocation=reinterpret_cast<PVOID>(0x1000);}
    const auto read=[&](PVOID,unsigned char* bytes)noexcept{++reads;memcpy(bytes,current,16);return true;};
    Baseline before,after;CHECK(RecordBaseline(before,guards,17,life,8,read)&&reads==25);
    for(unsigned i=0;i<5;++i)current[i]=0xe9; // Simulated first self-install target write, after pre capture.
    CHECK(RecordBaseline(after,guards,17,life,8,read)&&reads==50);
    auto result=ComparePreSelf(&before.guard[0],guards[0].code,guards[0].regions[2].allocation,current,true);
    CHECK(result.known&&result.identity_same&&result.compared&&result.mask==31&&before.guard[0].bytes[0]==0&&after.guard[0].bytes[0]==0xe9);
    CHECK(Compare(after.guard,17,read).matched==17); // Existing after-commit criterion is independent.
    const unsigned preReads=reads;CHECK(RecordBaseline(before,guards,17,life,8,read)&&reads==preReads&&before.guard[0].bytes[0]==0);
    memset(current,0,16);result=ComparePreSelf(&before.guard[0],guards[0].code,guards[0].regions[2].allocation,current,true);
    CHECK(result.compared&&result.mask==0&&Compare(after.guard,17,read).mismatched==17);
    result=ComparePreSelf(nullptr,guards[0].code,guards[0].regions[2].allocation,current,true);CHECK(!result.known&&!result.compared&&!result.identity_known);
    result=ComparePreSelf(&before.guard[0],guards[0].code,nullptr,current,true);CHECK(result.known&&!result.identity_known&&!result.compared);
    result=ComparePreSelf(&before.guard[0],guards[0].code,reinterpret_cast<PVOID>(0x2000),current,true);CHECK(result.identity_known&&!result.identity_same&&!result.compared);
    result=ComparePreSelf(&before.guard[0],guards[1].code,guards[0].regions[2].allocation,current,true);CHECK(result.identity_known&&!result.identity_same&&!result.compared);
    result=ComparePreSelf(&before.guard[0],guards[0].code,guards[0].regions[2].allocation,nullptr,false);CHECK(result.known&&result.identity_same&&!result.compared);
    Baseline partial;unsigned partialReads=0;const auto fail=[&](PVOID,unsigned char* bytes)noexcept{++partialReads;memcpy(bytes,current,3);return false;};
    CHECK(RecordBaseline(partial,guards,17,life,8,fail)&&partialReads==25&&!partial.guard[0].known);
    result=ComparePreSelf(&partial.guard[0],guards[0].code,guards[0].regions[2].allocation,current,true);CHECK(!result.known&&result.identity_same&&!result.compared);
    const unsigned oldReads=reads;CHECK(RecordBaseline(partial,guards,17,life,8,read)&&reads==oldReads&&!partial.guard[0].known);
    Baseline oversized;CHECK(!RecordBaseline(oversized,guards,19,life,8,read)&&!oversized.captured&&reads==oldReads);
    std::printf("{\"status\":\"PASS\",\"checks\":%u,\"game_or_desktop_operations\":false,\"actual_entry_reads_or_queries\":false,\"simulated_self_write_only\":true}\n",checks);return 0;
}
'''.replace('OUTPUT',relative)
    write_new(out/'pre_self_mock.cpp',source)
    recipe='''@echo off
call "C:\\Program Files\\Microsoft Visual Studio\\2022\\Community\\VC\\Auxiliary\\Build\\vcvars64.bat" >nul
if errorlevel 1 exit /b 2
cl /nologo /std:c++17 /utf-8 /W4 /WX /EHsc /O2 /MD /I. /Itools\\local_native_login_state5_ack_bridge /Itools\\local_original_session\\native\\vendor\\detours\\src /FIOUTPUT\\fixture-aliases.hpp /Fe:OUTPUT\\pre_self_mock.exe /Fo:OUTPUT\\pre_self_mock.obj OUTPUT\\pre_self_mock.cpp OUTPUT\\guard.obj user32.lib tools\\local_original_session\\native\\vendor\\detours\\lib.X64\\detours.lib
exit /b %errorlevel%
'''.replace('OUTPUT',relative.replace('/','\\'))
    write_new(out/'build-pre-self-fixture.cmd',recipe)


def write_immutable_fixture(out,relative):
    source=r'''#include "OUTPUT/immutable_command_results.hpp"
#include <cstdio>
#include <cwchar>
struct Mock {
    bool exists=false,writes=true,partial=false,closes=true;unsigned opened=0,written=0,closed=0;DWORD error=0;wchar_t path[600]{};
    DWORD Error()const noexcept{return error;}void Error(DWORD value)noexcept{error=value;}
    HANDLE Open(const wchar_t* name)noexcept{++opened;wcscpy_s(path,name);if(exists){error=ERROR_FILE_EXISTS;return INVALID_HANDLE_VALUE;}return reinterpret_cast<HANDLE>(1);}
    bool Write(HANDLE,const char*,DWORD n,DWORD& result)noexcept{++written;result=writes?n-(partial?1u:0u):0;if(!writes)error=ERROR_DISK_FULL;return writes;}
    bool Close(HANDLE)noexcept{++closed;if(!closes)error=ERROR_ACCESS_DENIED;return closes;}
};
#define CHECK(value) do{if(!(value))return static_cast<int>(checks+1);++checks;}while(false)
int main(){using namespace immutable_command_results;unsigned checks=0;wchar_t path[600]{};
    CHECK(Path(L"C:\\owned",1,path)&&!wcscmp(path,L"C:\\owned\\command-result-1.json"));
    CHECK(Path(L"C:\\owned\\",2147483647u,path)&&!wcscmp(path,L"C:\\owned\\command-result-2147483647.json"));
    CHECK(!Path(L"C:\\owned",0,path));CHECK(!Path(L"C:\\owned",2147483648u,path));
    wchar_t directory[601]{};directory[0]=L'C';directory[1]=L':';directory[2]=L'\\';for(unsigned i=3;i<568;++i)directory[i]=L'a';
    CHECK(Path(directory,2147483647u,path)&&wcslen(path)==599);directory[568]=L'a';CHECK(!Path(directory,2147483647u,path));
    for(unsigned i=569;i<600;++i)directory[i]=L'a';CHECK(!Path(directory,1,path));CHECK(!Path(L"relative",1,path));
    char payload[1025]{};Mock normal;CHECK(Publish(normal,L"C:\\owned",1,payload,1)&&normal.opened==1&&normal.written==1&&normal.closed==1);
    Mock maximum;CHECK(Publish(maximum,L"C:\\owned",2,payload,1024)&&maximum.opened==1&&maximum.written==1&&maximum.closed==1);
    Mock invalid;CHECK(!Publish(invalid,L"C:\\owned",3,payload,0)&&!invalid.opened);CHECK(!Publish(invalid,L"C:\\owned",3,payload,1025)&&!invalid.opened);
    CHECK(!Publish(invalid,L"C:\\owned",3,nullptr,1)&&!invalid.opened);CHECK(!Publish(invalid,L"C:\\owned",0,payload,1)&&!invalid.opened);
    CHECK(!Publish(invalid,L"C:\\owned",2147483648u,payload,1)&&!invalid.opened);CHECK(!Publish(invalid,nullptr,3,payload,1)&&!invalid.opened);
    Mock collision;collision.exists=true;CHECK(!Publish(collision,L"C:\\owned",4,payload,1)&&collision.opened==1&&!collision.written&&!collision.closed&&collision.error==ERROR_FILE_EXISTS);
    Mock writeFail;writeFail.writes=false;writeFail.closes=false;CHECK(!Publish(writeFail,L"C:\\owned",5,payload,1)&&writeFail.closed==1&&writeFail.error==ERROR_DISK_FULL);
    Mock partial;partial.partial=true;CHECK(!Publish(partial,L"C:\\owned",6,payload,2)&&partial.closed==1&&partial.error==ERROR_WRITE_FAULT);
    Mock closeFail;closeFail.closes=false;CHECK(!Publish(closeFail,L"C:\\owned",7,payload,1)&&closeFail.written==1&&closeFail.closed==1&&closeFail.error==ERROR_ACCESS_DENIED);
    std::printf("{\"status\":\"PASS\",\"checks\":%u,\"game_or_desktop_operations\":false,\"actual_file_operations\":false}\n",checks);return 0;
}
'''.replace('OUTPUT',relative)
    write_new(out/'immutable_mock.cpp',source)
    recipe='''@echo off
call "C:\\Program Files\\Microsoft Visual Studio\\2022\\Community\\VC\\Auxiliary\\Build\\vcvars64.bat" >nul
if errorlevel 1 exit /b 2
cl /nologo /std:c++17 /utf-8 /W4 /WX /EHsc /O2 /MD /I. OUTPUT\\immutable_mock.cpp /Fe:OUTPUT\\immutable_mock.exe /Fo:OUTPUT\\immutable_mock.obj
exit /b %errorlevel%
'''.replace('OUTPUT',relative.replace('/','\\'))
    write_new(out/'build-immutable-fixture.cmd',recipe)


def write_virtual_protect_fixture(out,relative):
    source=r'''#define OWN_SELECTED_HOST_TEST
#define OWN_KEY_HOST_TEST
#include "OUTPUT/abi_bridge_v2.cpp"
#include <cstdio>
namespace selected_diagnostic {ContextFn test_context=nullptr;OutputFn test_output=nullptr;}
namespace key_diagnostic {void(*test_output)(const char*,const char*,int) noexcept=nullptr;}
uintptr_t test_key_version_return=0;
using namespace virtual_protect_callers;
static unsigned originals=0,poisons=0;static DWORD incoming=0;static LPVOID seenBase=nullptr;static SIZE_T seenSize=0;static DWORD seenProtection=0;static PDWORD seenOld=nullptr;static bool recursive=false;
static BOOL WINAPI Original(LPVOID b,SIZE_T n,DWORD p,PDWORD old){++originals;incoming=GetLastError();seenBase=b;seenSize=n;seenProtection=p;seenOld=old;
    if(recursive){recursive=false;HookEntry(b,n,p,old);}SetLastError(456);return TRUE;}
static BOOL WINAPI Poison(LPVOID,SIZE_T,DWORD,PDWORD){++poisons;return FALSE;}
static BOOL WINAPI Raising(LPVOID,SIZE_T,DWORD,PDWORD){++originals;RaiseException(0xe0424242,0,0,nullptr);return FALSE;}
static bool Raised()noexcept{__try{HookEntry(reinterpret_cast<LPVOID>(0x20004),8,77,reinterpret_cast<PDWORD>(1));return false;}
    __except(GetExceptionCode()==0xe0424242?EXCEPTION_EXECUTE_HANDLER:EXCEPTION_CONTINUE_SEARCH){return true;}}
static void Reset()noexcept{state=virtual_protect_callers::State{};prepared.store(&Original);original_slot=&Poison;inside=false;originals=poisons=0;recursive=false;
    state.targets[0]={0x20000,0,0};state.targets[1]={0x20008,1,0};state.count=2;state.self=0x40000;state.self_end=0x41000;state.armed=1;}
struct Ops {LONG begin=0,update=0,attach=0,commit=0,abort=0;bool nonnull=true,flush=true,preparedBeforeCommit=false;unsigned aborted=0,committed=0;SIZE_T flushed=0;
    LONG Begin()noexcept{return begin;}LONG Update()noexcept{return update;}
    LONG Attach(PVOID* out)noexcept{*out=nonnull?reinterpret_cast<PVOID>(&Original):nullptr;return attach;}
    bool Flush(PVOID p,SIZE_T n)noexcept{flushed=n;return flush&&p==reinterpret_cast<PVOID>(&Original);}
    LONG Commit()noexcept{++committed;preparedBeforeCommit=prepared.load()==&Original;return commit;}
    LONG Abort()noexcept{++aborted;return abort;}DWORD Error()noexcept{return ERROR_ACCESS_DENIED;}};
#define CHECK(v) do{if(!(v))return static_cast<int>(checks+1);++checks;}while(false)
int main(){unsigned checks=0;Reset();const auto match=Find(state,0x20004,8);
    CHECK(match.valid&&match.count==2&&match.group==0&&match.offset==4&&match.length==8);
    CHECK(Find(state,0x30000,16).valid&&!Find(state,0x30000,16).count);
    CHECK(!Span(UINTPTR_MAX-4,16)&&!Span(0x20000,0)&&!Span(0x20000,0x40000001ULL));
    SetLastError(123);CHECK(HookEntry(reinterpret_cast<LPVOID>(0x20004),8,77,reinterpret_cast<PDWORD>(1))&&originals==1&&poisons==0&&incoming==123&&GetLastError()==456);
    CHECK(seenBase==reinterpret_cast<LPVOID>(0x20004)&&seenSize==8&&seenProtection==77&&seenOld==reinterpret_cast<PDWORD>(1)&&state.records[0].state==2&&state.records[0].matches==2&&state.records[0].new_protect==77);
    Reset();state.armed=0;HookEntry(reinterpret_cast<LPVOID>(0x20004),8,0,nullptr);CHECK(originals==1&&!state.claims);
    Reset();inside=true;HookEntry(reinterpret_cast<LPVOID>(0x20004),8,0,nullptr);CHECK(originals==1&&!state.claims&&inside);inside=false;
    Reset();recursive=true;HookEntry(reinterpret_cast<LPVOID>(0x20004),8,0,nullptr);CHECK(originals==2&&state.claims==1&&!inside&&!state.active);
    Reset();HookEntry(reinterpret_cast<LPVOID>(0x30000),8,0,nullptr);CHECK(originals==1&&!state.claims);
    Reset();HookEntry(reinterpret_cast<LPVOID>(UINTPTR_MAX-4),16,0,nullptr);CHECK(originals==1&&state.invalid==1&&!state.claims);
    Reset();state.self=1;state.self_end=0x800000000000ULL;HookEntry(reinterpret_cast<LPVOID>(0x20004),8,0,nullptr);CHECK(originals==1&&!state.claims);
    Reset();for(unsigned i=0;i<5;++i)HookEntry(reinterpret_cast<LPVOID>(0x20004),8,0,nullptr);CHECK(originals==5&&state.claims==4&&state.dropped==1&&state.records[3].state==2);
    Reset();prepared.store(&Raising);CHECK(Raised()&&originals==1&&!inside&&!state.active&&state.records[0].state==1&&!state.completions);
    Reset();Disarm();HookEntry(reinterpret_cast<LPVOID>(0x20004),8,0,nullptr);CHECK(originals==1&&!state.claims);
    Reset();prepared.store(nullptr);state.armed=0;Ops success;InstallTransaction(success);CHECK(state.install==Installed&&state.armed&&success.preparedBeforeCommit&&success.flushed==96&&success.committed==1&&!success.aborted);
    Reset();prepared.store(nullptr);state.armed=0;Ops attachError;attachError.attach=5;InstallTransaction(attachError);CHECK(state.install==AttachFailed&&attachError.aborted==1&&!attachError.committed&&!prepared.load());
    Reset();prepared.store(nullptr);state.armed=0;Ops null;null.nonnull=false;InstallTransaction(null);CHECK(state.install==NullTrampoline&&null.aborted==1&&!prepared.load());
    Reset();prepared.store(nullptr);state.armed=0;Ops cache;cache.flush=false;InstallTransaction(cache);CHECK(state.install==CacheFailed&&cache.aborted==1&&!cache.committed&&!prepared.load());
    Reset();prepared.store(nullptr);state.armed=0;Ops commitError;commitError.commit=ERROR_INVALID_DATA;InstallTransaction(commitError);CHECK(state.install==CommitPrepatchFailed&&commitError.preparedBeforeCommit&&!commitError.aborted&&!prepared.load());
    Reset();prepared.store(nullptr);state.armed=0;Ops updateError;updateError.update=5;InstallTransaction(updateError);CHECK(state.install==UpdateFailed&&updateError.aborted==1&&!prepared.load());
    Reset();prepared.store(nullptr);state.armed=0;Ops beginError;beginError.begin=5;InstallTransaction(beginError);CHECK(state.install==BeginFailed&&!beginError.aborted&&!prepared.load());
    Reset();prepared.store(nullptr);state.armed=0;Ops abortError;abortError.attach=5;abortError.abort=5;InstallTransaction(abortError);CHECK(state.install==AbortUnknown&&!prepared.load());
    std::printf("{\"status\":\"PASS\",\"checks\":%u,\"game_or_desktop_operations\":false,\"actual_virtual_protect_or_detours_calls\":false}\n",checks);return 0;
}
'''.replace('OUTPUT',relative)
    write_new(out/'virtual_protect_mock.cpp',source)
    recipe='''@echo off
call "C:\\Program Files\\Microsoft Visual Studio\\2022\\Community\\VC\\Auxiliary\\Build\\vcvars64.bat" >nul
if errorlevel 1 exit /b 2
cl /nologo /std:c++17 /utf-8 /W4 /WX /EHsc /O2 /MD /I. /Itools\\local_native_login_state5_ack_bridge /Itools\\local_original_session\\native\\vendor\\detours\\src /FIOUTPUT\\fixture-aliases.hpp /Fe:OUTPUT\\virtual_protect_mock.exe /Fo:OUTPUT\\virtual_protect_mock.obj OUTPUT\\virtual_protect_mock.cpp OUTPUT\\guard.obj user32.lib tools\\local_original_session\\native\\vendor\\detours\\lib.X64\\detours.lib
exit /b %errorlevel%
'''.replace('OUTPUT',relative.replace('/','\\'))
    write_new(out/'build-virtual-protect-fixture.cmd',recipe)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--sibling-product', action='store_true')
    mode.add_argument('--connect-role-fix', action='store_true')
    mode.add_argument('--memory-query-diagnostics', action='store_true')
    mode.add_argument('--source-read-retry', action='store_true')
    mode.add_argument('--verified-connected-duplicate', action='store_true')
    mode.add_argument('--duplicate-diagnostics', action='store_true')
    mode.add_argument('--verified-socket-duplicate', action='store_true')
    mode.add_argument('--command-bridge', action='store_true')
    mode.add_argument('--command-quit', action='store_true')
    mode.add_argument('--lifecycle-diagnostics', action='store_true')
    mode.add_argument('--quit-source-retry', action='store_true')
    mode.add_argument('--lifecycle-integrity', action='store_true')
    mode.add_argument('--lifecycle-details', action='store_true')
    mode.add_argument('--lifecycle-pre-self', action='store_true')
    parser.add_argument('--immutable-command-results', action='store_true')
    parser.add_argument('--virtual-protect-callers', action='store_true')
    args = parser.parse_args()
    details=args.lifecycle_details or args.lifecycle_pre_self
    if details:
        args.lifecycle_integrity=True
    socket_mode=args.verified_socket_duplicate or args.command_bridge or args.command_quit or args.lifecycle_diagnostics or args.quit_source_retry or args.lifecycle_integrity
    prepare(args.sibling_product or args.connect_role_fix or args.memory_query_diagnostics or args.source_read_retry or args.verified_connected_duplicate or args.duplicate_diagnostics or socket_mode,
            args.connect_role_fix or args.memory_query_diagnostics or args.source_read_retry or args.verified_connected_duplicate or args.duplicate_diagnostics or socket_mode,
            args.memory_query_diagnostics or args.source_read_retry or args.verified_connected_duplicate or args.duplicate_diagnostics or socket_mode,
            args.source_read_retry or args.verified_connected_duplicate or args.duplicate_diagnostics or socket_mode,
            args.verified_connected_duplicate or args.duplicate_diagnostics, args.duplicate_diagnostics, socket_mode, args.command_bridge or args.command_quit or args.lifecycle_diagnostics or args.quit_source_retry or args.lifecycle_integrity, args.command_quit or args.lifecycle_diagnostics or args.quit_source_retry or args.lifecycle_integrity, args.lifecycle_diagnostics or args.quit_source_retry or args.lifecycle_integrity,args.quit_source_retry or args.lifecycle_integrity,args.lifecycle_integrity,details,args.lifecycle_pre_self,args.immutable_command_results,args.virtual_protect_callers)


if __name__ == '__main__':
    main()

