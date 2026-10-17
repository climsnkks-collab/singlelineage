option casemap:none
EXTERN OwnForwardProbe:PROC
EXTERN OwnLoginConnectBridge:PROC
EXTERN OwnLoginSenderBridge:PROC
EXTERN OwnLoginSelectedBridge:PROC
EXTERN OwnLoginInitBridge:PROC
EXTERN OwnLoginConstructorBridge:PROC
EXTERN OwnLoginSelectedTaskBridge:PROC
EXTERN OwnLoginCloseBridge:PROC
EXTERN OwnKeyTaskBridge:PROC
EXTERN OwnKeyVersionBridge:PROC
SHIM MACRO procName:req, endName:req, caseId:req, wrapper:req
    LOCAL native_original,bound_slot
.const
bound_slot QWORD wrapper
.code
PUBLIC procName
PUBLIC endName
procName PROC FRAME
    push rbp
    .pushreg rbp
    pushfq
    .allocstack 8
    sub rsp, 0E8h
    .allocstack 0E8h
    lea rbp, [rsp+0F0h]
    .setframe rbp, 0F0h
    .endprolog
    mov [rsp+058h], rax
    mov [rsp+060h], r10
    mov [rsp+068h], r11
    mov [rsp+020h], rcx
    mov [rsp+028h], rdx
    mov [rsp+030h], r8
    mov [rsp+038h], r9
    mov rax, [rsp+0F8h]
    mov [rsp+040h], rax
    mov rax, [rsp+068h]
    mov [rsp+048h], rax
    mov rax, [rsp+060h]
    mov [rsp+050h], rax
    movdqu [rsp+080h], xmm0
    movdqu [rsp+090h], xmm1
    movdqu [rsp+0A0h], xmm2
    movdqu [rsp+0B0h], xmm3
    movdqu [rsp+0C0h], xmm4
    movdqu [rsp+0D0h], xmm5
    lea rcx, [rsp+020h]
    mov edx, caseId
    call OwnForwardProbe
    test rax, rax
    jz native_original
    movdqu xmm0, [rsp+080h]
    movdqu xmm1, [rsp+090h]
    movdqu xmm2, [rsp+0A0h]
    movdqu xmm3, [rsp+0B0h]
    movdqu xmm4, [rsp+0C0h]
    movdqu xmm5, [rsp+0D0h]
    mov rcx, [rsp+020h]
    mov rdx, [rsp+028h]
    mov r8, [rsp+030h]
    mov r9, [rsp+038h]
    mov rax, [rsp+058h]
    mov r10, [rsp+060h]
    mov r11, [rsp+068h]
    push qword ptr [rsp+0E8h]
    popfq
    lea rsp, [rbp]
    pop rbp
    jmp qword ptr [bound_slot]
native_original:
    mov rax, [rsp+050h]
    mov [rbp+010h], rax
    movdqu xmm0, [rsp+080h]
    movdqu xmm1, [rsp+090h]
    movdqu xmm2, [rsp+0A0h]
    movdqu xmm3, [rsp+0B0h]
    movdqu xmm4, [rsp+0C0h]
    movdqu xmm5, [rsp+0D0h]
    mov rcx, [rsp+020h]
    mov rdx, [rsp+028h]
    mov r8, [rsp+030h]
    mov r9, [rsp+038h]
    mov r10, [rsp+060h]
    mov r11, [rsp+068h]
    lea rax, [rbp+010h]
    push qword ptr [rsp+0E8h]
    popfq
    lea rsp, [rbp]
    pop rbp
    jmp qword ptr [rax]
procName ENDP
endName LABEL BYTE
ENDM
SHIM OwnForwardConnectShim,OwnForwardConnectShimEnd,0,OwnLoginConnectBridge
SHIM OwnForwardSenderShim,OwnForwardSenderShimEnd,1,OwnLoginSenderBridge
SHIM OwnForwardSelectedShim,OwnForwardSelectedShimEnd,2,OwnLoginSelectedBridge
SHIM OwnForwardInitShim,OwnForwardInitShimEnd,3,OwnLoginInitBridge
SHIM OwnForwardConstructor0Shim,OwnForwardConstructor0ShimEnd,4,OwnLoginConstructorBridge
SHIM OwnForwardConstructor1Shim,OwnForwardConstructor1ShimEnd,5,OwnLoginConstructorBridge
SHIM OwnForwardConstructor2Shim,OwnForwardConstructor2ShimEnd,6,OwnLoginConstructorBridge
SHIM OwnForwardTaskShim,OwnForwardTaskShimEnd,7,OwnLoginSelectedTaskBridge
SHIM OwnForwardCloseShim,OwnForwardCloseShimEnd,8,OwnLoginCloseBridge
SHIM OwnForwardKeyTaskShim,OwnForwardKeyTaskShimEnd,9,OwnKeyTaskBridge
SHIM OwnForwardKeyVersionShim,OwnForwardKeyVersionShimEnd,10,OwnKeyVersionBridge
END
