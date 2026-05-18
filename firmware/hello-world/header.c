#include "bootloader.h"
#include "linker_const.h"

// __attribute__((section(".firmware_header.header"), used, aligned(4)))
// struct firmware_image_header firmware_image_header = {
//     .finalization = {
//         .final_zzz_str = "ZZzo..(-_- ) EX-4420 2013-04-01",
//         .complete_word = 0xffff,
//         .checkword = 0xb6cd,
//     },
//     .name = "Hello World Demo",
//     .version = "V1.00.000",
//     .descriptor_primary = {
//         .flash_start_addr = 0x60200000, // Unused by bootloader.
//         .flash_limit_addr = 0x61000000, // Unused by bootloader.
//         .load_address = LINKER_SYMBOL_U32(__ddr_start),
//         .image_length = 0, // Unused by bootloader.
//         .copy_length = LINKER_SYMBOL_U32(__copy_length),
//     },
//     // .descriptor_secondary = firmware_image_descriptor_secondary,
// };


__attribute__((section(".firmware_header.header"), used, aligned(4)))
struct firmware_image_version firmware_image_version = {
    .name = "Hello World Demo",
    .version = "V1.00.000",
};

__attribute__((section(".firmware_header.header"), used, aligned(4)))
struct firmware_image_descriptor firmware_image_descriptor_primary = {
    .flash_start_addr = 0x60200000, // Unused by bootloader.
    .flash_limit_addr = 0x61000000, // Unused by bootloader.
    .load_address = LINKER_SYMBOL_U32(__ddr_start),
    .image_length = 0, // Unused by bootloader.
    .copy_length = LINKER_SYMBOL_U32(__copy_length),
};
