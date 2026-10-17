#pragma once
#include <cstdint>
#include <cstddef>
enum class ForwardRole:uint32_t { Connect,Sender,Selected,Init,Constructor,Task,Close,KeyTask,KeyVersion,Count };
struct NativeProbeFrame {
    uintptr_t rcx,rdx,r8,r9,original_return,actual_leaf,native_original_target;
};
static_assert(sizeof(NativeProbeFrame)==56 && offsetof(NativeProbeFrame,native_original_target)==48,"guarded leaf ABI");
// Guard entry RSP=S. push RBP/push FLAGS/sub E8 => current RSP=S-F8.
// RBP=S-8=current RSP+F0. Frame lives at current RSP+20.
// Saved original FLAGS is current RSP+E8; original return is current RSP+F8.
// Caller shadow S+8 is writable callee-owned scratch on native fallback only.
// Return S and argument5 S+28 upward are never written.
// Second scalar is exact per-edge record_id0..8, not an object-kind guess.
extern "C" uintptr_t OwnForwardProbe(const NativeProbeFrame*,uint32_t record_id) noexcept;

extern "C" void OwnForwardKeyTaskShim();extern "C" void OwnForwardKeyTaskShimEnd();
extern "C" void OwnForwardKeyVersionShim();extern "C" void OwnForwardKeyVersionShimEnd();
