ENTRY(__firmware_header_start)

MEMORY
{
    FLASH (rx)  : ORIGIN = 0x60200000, LENGTH = 0x00300000
    DDR   (rwx) : ORIGIN = 0xc0000000, LENGTH = 0x04000000
}

SECTIONS
{
    . = ORIGIN(DDR);

    __ddr_start = ORIGIN(DDR);
    __ddr_end = ORIGIN(DDR) + LENGTH(DDR);

    .firmware_header :
    {
        KEEP(*(.firmware_header))
    } > DDR

    . = ORIGIN(DDR) + 0x200;

    .text :
    {
        __image_start = .;
        *(.text*)
        *(.rodata*)
        . = ALIGN(4);
    } > DDR

    .data :
    {
        *(.data*)
        . = ALIGN(4);
    } > DDR

    __image_end = .;
    __copy_length = __image_end - ORIGIN(DDR);
    __flash_image_end = ORIGIN(FLASH) + __copy_length;

    .bss (NOLOAD) :
    {
        . = ALIGN(4);
        __bss_start = .;
        *(.bss*)
        *(COMMON)
        . = ALIGN(4);
        __bss_end = .;
    } > DDR

    __stack_top = ORIGIN(DDR) + LENGTH(DDR);
}
