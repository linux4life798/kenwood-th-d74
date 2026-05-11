"""Built-in TH-D74 jump-pad update payload."""

from __future__ import annotations

import struct

from firmware import FirmwareDescriptor
import fldm

SPECIAL_WORD = "jump"

MAIN_FIRMWARE_FLASH_ADDR = 0x6020_0000
MAIN_FIRMWARE_ERASE_LENGTH = 0x0028_0000
FINAL_ZZZ_FLASH_ADDR = 0x6020_0040
FINAL_ZZZ_DATA = b"ZZzo..(-_- ) EX-4420 2013-04-01\x00"
FINAL_ZZZ_CHECKSUM = 0xC7A8

# BootInitializeAndDispatch reads this record at 0x602000c0. With copy length
# zero, it skips the main-firmware copy and branches directly to dwLoadAddress.
MAIN_FIRMWARE_DESCRIPTOR_FLASH_ADDR = 0x6020_00C0
DESCRIPTOR_DW_FLASH_START = 0x6020_0000
DESCRIPTOR_DW_FLASH_LIMIT = 0x6100_0000
DESCRIPTOR_DW_IMAGE_SPAN = 0x0050_0000
DESCRIPTOR_DW_RESERVED14 = 0xFFFF_FFFF
DESCRIPTOR_DW_RESERVED18 = 0xFFFF_FFFF
DESCRIPTOR_DW_RESERVED1C = 0xFFFF_FFFF
JUMP_LOAD_ADDRESS = 0x6000_C9BC
JUMP_COPY_LENGTH = 0x0000_0000

type JumpUpdate = tuple[FirmwareDescriptor, tuple[fldm.Segment, ...]]


def build() -> JumpUpdate:
    """Build a bad-style update that also restores the main jump descriptor."""
    wipe_data = b"\x00\x00"
    wipe_verify_data = wipe_data + b"\xff" * (
        MAIN_FIRMWARE_ERASE_LENGTH - len(wipe_data)
    )
    wipe_checksum = fldm.fldm_sum16(wipe_verify_data)
    descriptor_data = build_main_firmware_descriptor(
        # dwLoadAddress=JUMP_LOAD_ADDRESS,
        dwLoadAddress=0x0,
        dwCopyLength=JUMP_COPY_LENGTH,
    )

    return (
        FirmwareDescriptor(),
        (
            fldm.Segment(
                descriptor=fldm.SegmentDescriptor(
                    flash_start_addr=MAIN_FIRMWARE_FLASH_ADDR,
                    data_length=len(wipe_data),
                    erase_length=MAIN_FIRMWARE_ERASE_LENGTH,
                    expected_before_checksum=wipe_checksum,
                    expected_after_checksum=wipe_checksum,
                    checksum_start_offset=0,
                    checksum_length=MAIN_FIRMWARE_ERASE_LENGTH,
                    final_version_offset=0,
                    expected_final_version_string=b"",
                    erase_wait_seconds=6,
                    checksum_wait_seconds=10,
                ),
                data=wipe_data,
                index=0,
                label="FIRMWARE",
            ),
            fldm.Segment(
                descriptor=fldm.SegmentDescriptor(
                    flash_start_addr=MAIN_FIRMWARE_DESCRIPTOR_FLASH_ADDR,
                    data_length=len(descriptor_data),
                    erase_length=0,
                    expected_before_checksum=fldm.fldm_sum16(descriptor_data),
                    expected_after_checksum=fldm.fldm_sum16(descriptor_data),
                    checksum_start_offset=0,
                    checksum_length=0,
                    final_version_offset=0,
                    expected_final_version_string=b"",
                    erase_wait_seconds=0,
                    checksum_wait_seconds=10,
                ),
                data=descriptor_data,
                index=1,
                label="MAIN_FIRMWARE_DESCRIPTOR",
            ),
            fldm.Segment(
                descriptor=fldm.SegmentDescriptor(
                    flash_start_addr=FINAL_ZZZ_FLASH_ADDR,
                    data_length=len(FINAL_ZZZ_DATA),
                    erase_length=0,
                    expected_before_checksum=FINAL_ZZZ_CHECKSUM,
                    expected_after_checksum=FINAL_ZZZ_CHECKSUM,
                    checksum_start_offset=0,
                    checksum_length=0,
                    final_version_offset=0,
                    expected_final_version_string=b"",
                    erase_wait_seconds=0,
                    checksum_wait_seconds=10,
                ),
                data=FINAL_ZZZ_DATA,
                index=2,
                label="FINAL_ZZZ",
            ),
        ),
    )


def build_main_firmware_descriptor(
    *,
    dwLoadAddress: int,
    dwCopyLength: int,
) -> bytes:
    """Pack the descriptor fields that BootInitializeAndDispatch actually uses.

    The FLDM Loader only seems to reads `dwLoadAddress` and `dwCopyLength`
    from this flash record. For the jump mode, `dwLoadAddress=0x6000c9bc`
    enters the bootloader helper that loads the FLDM loader, and
    `dwCopyLength=0` prevents the normal main-firmware copy before that jump.
    """
    return struct.pack(
        "<IIIIIIII",
        DESCRIPTOR_DW_FLASH_START,
        DESCRIPTOR_DW_FLASH_LIMIT,
        dwLoadAddress,
        DESCRIPTOR_DW_IMAGE_SPAN,
        dwCopyLength,
        DESCRIPTOR_DW_RESERVED14,
        DESCRIPTOR_DW_RESERVED18,
        DESCRIPTOR_DW_RESERVED1C,
    )
