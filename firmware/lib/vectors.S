.section .firmware_header.vectors, "ax"
.arm

.global __vector_table
.type __vector_table, %object

__vector_table:
    ldr pc, reset_handler
    ldr pc, undefined_instruction_handler
    ldr pc, software_interrupt_handler
    ldr pc, prefetch_abort_handler
    ldr pc, data_abort_handler
    ldr pc, reserved_vector_handler
    ldr pc, irq_handler
    ldr pc, fiq_handler

reset_handler:
    .word ResetHandler
undefined_instruction_handler:
    .word UndefinedInstructionHandler
software_interrupt_handler:
    .word SoftwareInterruptHandler
prefetch_abort_handler:
    .word PrefetchAbortHandler
data_abort_handler:
    .word DataAbortHandler
reserved_vector_handler:
    .word ReservedVectorHandler
irq_handler:
    .word IrqHandler
fiq_handler:
    .word FiqHandler

.size __vector_table, . - __vector_table
