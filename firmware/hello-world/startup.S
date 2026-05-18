.section .text.startup, "ax"
.arm

.global ResetHandler
.global _start
ResetHandler:
_start:
    @ Normal Flow
    ldr sp, =__stack_top

    ldr r0, =__bss_start
    ldr r1, =__bss_end
    mov r2, #0

clear_bss:
    cmp r0, r1
    bhs bss_done
    str r2, [r0], #4
    b clear_bss

bss_done:
    bl main

hang:
    b hang

.global UndefinedInstructionHandler
UndefinedInstructionHandler:
    b unhandled_exception

.global SoftwareInterruptHandler
SoftwareInterruptHandler:
    b unhandled_exception

.global PrefetchAbortHandler
PrefetchAbortHandler:
    b unhandled_exception

.global DataAbortHandler
DataAbortHandler:
    b unhandled_exception

.global ReservedVectorHandler
ReservedVectorHandler:
    b unhandled_exception

.global IrqHandler
IrqHandler:
    b unhandled_exception

.global FiqHandler
FiqHandler:
    b unhandled_exception


unhandled_exception:
    b unhandled_exception
