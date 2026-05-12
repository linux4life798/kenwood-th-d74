"""Build Openwood update segments from a flat binary image."""

from __future__ import annotations

from pathlib import Path

from firmware import FirmwareDescriptor
import fldm

MAIN_FIRMWARE_FLASH_ADDR = 0x6020_0000
MAIN_FIRMWARE_SLOT_SIZE = 0x0030_0000
FINAL_ZZZ_FLASH_ADDR = 0x6020_0040
FINAL_ZZZ_DATA = b"ZZzo..(-_- ) EX-4420 2013-04-01\x00"
FINAL_ZZZ_CHECKSUM = 0xC7A8

type FlatUpdate = tuple[FirmwareDescriptor, tuple[fldm.Segment, ...]]


def build(program: Path) -> FlatUpdate:
    """Build a firmware update from a raw binary image for the first firmware slot."""
    data = program.read_bytes()
    if not data:
        raise ValueError(f"flat binary is empty: {program}")
    # For now, we limit the firmware size to the official main firmware slot,
    # but there is no real reason why we can't expand past this.
    if len(data) > MAIN_FIRMWARE_SLOT_SIZE:
        raise ValueError(
            "flat binary is too large for the first firmware slot: "
            f"0x{len(data):08x} > 0x{MAIN_FIRMWARE_SLOT_SIZE:08x}"
        )
    if len(data) % 2:
        raise ValueError(
            "flat binary length must be even for 16-bit flash programming: "
            f"0x{len(data):08x}"
        )

    checksum_data = data + b"\xff" * (MAIN_FIRMWARE_SLOT_SIZE - len(data))
    firmware_checksum = fldm.fldm_sum16(checksum_data)

    return (
        FirmwareDescriptor(),
        (
            fldm.Segment(
                descriptor=fldm.SegmentDescriptor(
                    flash_start_addr=MAIN_FIRMWARE_FLASH_ADDR,
                    data_length=len(data),
                    erase_length=MAIN_FIRMWARE_SLOT_SIZE,
                    expected_before_checksum=firmware_checksum,
                    expected_after_checksum=firmware_checksum,
                    checksum_start_offset=0,
                    checksum_length=MAIN_FIRMWARE_SLOT_SIZE,
                    final_version_offset=0,
                    expected_final_version_string=b"",
                    erase_wait_seconds=6,
                    checksum_wait_seconds=10,
                ),
                data=data,
                index=0,
                label="FLAT_BINARY_FIRMWARE",
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
                index=1,
                label="FINAL_ZZZ",
            ),
        ),
    )
