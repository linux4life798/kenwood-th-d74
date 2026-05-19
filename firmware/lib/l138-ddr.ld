ENTRY(__vector_table)

MEMORY
{
    FLASH     (rx)  : ORIGIN = 0x60200000, LENGTH = 0x00300000 /* 3 MiB - Main firmware image slot */
    DDR       (rwx) : ORIGIN = 0xc0000000, LENGTH = 0x04000000 /* 64 MiB */
    LOCAL_RAM (rwx) : ORIGIN = 0xffff0000, LENGTH = 0x00002000 /* 8 KiB */
}

SECTIONS
{
    . = ORIGIN(DDR);

    __ddr_start = ORIGIN(DDR);
    __ddr_end = ORIGIN(DDR) + LENGTH(DDR);

    .firmware_header :
    {
        FILL(0xFF)
        KEEP(*(.firmware_header.vectors))
        . = ORIGIN(DDR) + 0x40;
        /* Marker bytes written by the firmware updater */
        . = ORIGIN(DDR) + 0x80;
        /* Version and Descriptors */
        KEEP(*(.firmware_header.header))
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
