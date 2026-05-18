#ifndef DESCRIPTOR_H
#define DESCRIPTOR_H

#include <stdint.h>

/**
 * The only fields used by the bootloader is the load_address and copy_length.
 */
struct __attribute__((packed)) firmware_image_descriptor
{
    /** The starting address in flash of the image.
     * Unused by bootloader.
     * Example: 0x6020_0000 */
    uint32_t flash_start_addr;
    /** The ending address in flash of the image (not inclusive).
     * Unused by bootloader.
     * Example: 0x6100_0000 */
    uint32_t flash_limit_addr;
    /** The address where firmware will be copied to AND execution from.
     *
     * This is the destination of the code copy and then the start address
     * for execution. If the copy_length is 0, then the bootloader will
     * skip copying and simply jump  to this address. */
    uint32_t load_address;
    /** The full length of the firmware image.
     * Unused by bootloader.
     * Example: 0x50_0000
     */
    uint32_t image_length;
    /** The length of the firmware image to copy to the load_address.
     * Example: 0x30_0000
     */
    uint32_t copy_length;

    /* Possibly 3 more reserved 32bit words. */
    uint32_t _reserved[3];
};

/**
 * This region is expected to be manually written by additional firmware update
 * steps and not part of the main firmware image itself.
 */
struct __attribute__((packed)) firmware_image_finalization {
    /** The early bootloader will verify this value before attempting to load
     * main firmware, otherwise FLDM loader will be started. It is expected that
     * a dedicated firmware update step will write this value separately, once
     * all other sections have been written. The final updater step is the
     * checkword.
     *
     * Ultimately, it must match the following string:
     * "ZZzo..(-_- ) EX-4420 2013-04-01" (with 1 null terminator) */
    char final_zzz_str[32];
    /** The firmware updater's "complete" command writes 0xFFFF to this space
     * upon firmware update completion. This doesn't make any sense to me, since
     * the erased value is already 0xFFFF.
     * Unused by bootloader. */
    uint16_t complete_word;
    /** Dedicated 2 byte checksum word that is written by the updater as the
     * very last step, after the final zzz string. It doesn't appear to be used,
     * though. Unused by bootloader. */
    uint16_t checkword;

    /** Empty 28 bytes. This entire structure, with these trailing empty bytes,
     *  is 32 bytes total. */
    uint8_t _reserved[28];
};

struct __attribute__((packed)) firmware_image_version {
    /** The name of teh firmware image.
     * Unused by bootloader.
     * Example: "EX-4409 Firmware"
     */
    char name[32];
    /** The version that will appear on the FLDM UI during update.
     * The expected format is `V-.--.---`. The loader will auto truncate
     * `.000` suffix, if present.
     * That being said, you can still use any version string that is at most
     * 9 chars long. */
    char version[32];
};

struct __attribute__((packed)) firmware_image_header {
    /** Data expected to be written into flash in later update steps to mark
     * the firmware as complete. */
    struct firmware_image_finalization finalization;
    /** The version of the firmware image. */
    struct firmware_image_version version;
    /** The primary firmware image descriptor used by the early bootloader. */
    struct firmware_image_descriptor descriptor_primary;
    /** A secondary firmware image descriptor observed in existing main firmware
     * images.
     * Unused by bootloader. */
    // struct firmware_image_descriptor descriptor_secondary;
};

#endif
