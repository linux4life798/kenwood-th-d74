.section .firmware_header, "ax"
.arm

.equ FLDM_LOADER_ADDRESS, 0x6000c9bc

.global __firmware_header_start
__firmware_header_start:
    @ The following does not work:
    @ ldr pc, reset_handler
    @ The following works:
    @ ldr pc, =FLDM_LOADER_ADDRESS
    b FLDM_LOADER_ADDRESS
    @ b ResetHandler
    ldr pc, undefined_instruction_handler
    ldr pc, [pc, #0x18]
    ldr pc, [pc, #0x18]
    ldr pc, [pc, #0x18]
    ldr pc, [pc, #0x18]
    ldr pc, [pc, #0x18]
    ldr pc, [pc, #0x18]

reset_handler:
    @ .word ResetHandler
    .word FLDM_LOADER_ADDRESS
undefined_instruction_handler:
    .word UndefinedInstructionHandler
    .word SoftwareInterruptHandler
    .word PrefetchAbortHandler
    .word DataAbortHandler
    .word ReservedVectorHandler
    .word IrqHandler
    .word FiqHandler

    .org 0x40, 0xff
    .ascii "ZZzo..(-_- ) EX-4420 2013-04-01\0"

    .org 0x60, 0xff
    .hword 0xffff
    .hword 0xb6cd

    .org 0x80, 0xff
    .ascii "EX-4409 Firmware\0"

    .org 0xa0, 0xff
    .ascii "CraigV1        \0"
    .byte 0

    .org 0xc0, 0xff
    @ .word __flash_start     @ Flash Start
    @ .word __flash_image_end @ Flash Limit
    .word 0                 @ Flash Start
    .word 0                 @ Flash Limit
    @ .word __ddr_start       @ Load Address
    .word __firmware_header_start @ Load Address
    @ .word FLDM_LOADER_ADDRESS @ Load Address
    .word __copy_length     @ Image Span
    .word __copy_length     @ Copy Length
    .word 0xffffffff        @ Reserved 14
    .word 0xffffffff        @ Reserved 18
    .word 0xffffffff        @ Reserved 1c

    .org 0x200, 0xff
