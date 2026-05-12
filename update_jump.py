"""Built-in TH-D74 jump-pad update payload."""

from __future__ import annotations

import struct
from typing import ClassVar

from pydantic.dataclasses import dataclass

from firmware import FirmwareDescriptor
import fldm
import utils

SPECIAL_WORD = "jump"

MAIN_FIRMWARE_FLASH_ADDR = 0x6020_0000
MAIN_FIRMWARE_ERASE_LENGTH = 0x0028_0000
FINAL_ZZZ_FLASH_ADDR = 0x6020_0040
FINAL_ZZZ_DATA = b"ZZzo..(-_- ) EX-4420 2013-04-01\x00"
FINAL_ZZZ_CHECKSUM = 0xC7A8

type JumpUpdate = tuple[FirmwareDescriptor, tuple[fldm.Segment, ...]]


@dataclass(frozen=True, slots=True)
class MainFirmwareDescriptor:
    """Descriptor record read by BootInitializeAndDispatch at 0x602000c0.

    The FLDM Loader only seems to read `load_address` and `copy_length` from
    this flash record. For the jump mode, `load_address=0x6000c9bc` enters the
    bootloader helper that loads the FLDM loader, and `copy_length=0` prevents
    the normal main-firmware copy before that jump.
    """

    FLASH_ADDR: ClassVar[int] = 0x6020_00C0
    STRUCT: ClassVar[struct.Struct] = struct.Struct("<IIIIIIII")

    flash_start: utils.UInt32 = 0x6020_0000
    flash_limit: utils.UInt32 = 0x6100_0000
    load_address: utils.UInt32 = 0x6000_C9BC
    image_span: utils.UInt32 = 0x0050_0000
    copy_length: utils.UInt32 = 0x0000_0000
    reserved14: utils.UInt32 = 0xFFFF_FFFF
    reserved18: utils.UInt32 = 0xFFFF_FFFF
    reserved1c: utils.UInt32 = 0xFFFF_FFFF

    def pack(self) -> bytes:
        return self.STRUCT.pack(
            self.flash_start,
            self.flash_limit,
            self.load_address,
            self.image_span,
            self.copy_length,
            self.reserved14,
            self.reserved18,
            self.reserved1c,
        )


def build() -> JumpUpdate:
    """Build a bad-style update that also restores the main jump descriptor."""
    wipe_data = b"\x00\x00"
    wipe_verify_data = wipe_data + b"\xff" * (
        MAIN_FIRMWARE_ERASE_LENGTH - len(wipe_data)
    )
    wipe_checksum = fldm.fldm_sum16(wipe_verify_data)
    descriptor_data = MainFirmwareDescriptor(
        # load_address=0x6000_C9BC,
        load_address=0x0,
    ).pack()

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
                    flash_start_addr=MainFirmwareDescriptor.FLASH_ADDR,
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
