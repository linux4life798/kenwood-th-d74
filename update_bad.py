"""Built-in intentionally bad TH-D74 update payload."""

from __future__ import annotations

import fldm
from firmware import FirmwareDescriptor

SPECIAL_WORD = "bad"

type BadUpdate = tuple[FirmwareDescriptor, tuple[fldm.Segment, ...]]


def build() -> BadUpdate:
    """Build an intentionally bad update for the TH-D74."""
    wipe_data = b"\x00\x00"
    wipe_length = 0x0028_0000
    wipe_verify_data = wipe_data + b"\xff" * (wipe_length - len(wipe_data))
    wipe_checksum = fldm.fldm_sum16(wipe_verify_data)
    final_zzz_data = b"ZZzo..(-_- ) EX-4420 2013-04-01\x00"
    final_zzz_checksum = 0xC7A8

    return (
        FirmwareDescriptor(),
        (
            fldm.Segment(
                descriptor=fldm.SegmentDescriptor(
                    flash_start_addr=0x6020_0000,
                    data_length=len(wipe_data),
                    erase_length=wipe_length,
                    expected_before_checksum=wipe_checksum,
                    expected_after_checksum=wipe_checksum,
                    checksum_start_offset=0,
                    checksum_length=wipe_length,
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
                    flash_start_addr=0x6020_0040,
                    data_length=len(final_zzz_data),
                    erase_length=0,
                    expected_before_checksum=final_zzz_checksum,
                    expected_after_checksum=final_zzz_checksum,
                    checksum_start_offset=0,
                    checksum_length=0,
                    final_version_offset=0,
                    expected_final_version_string=b"",
                    erase_wait_seconds=0,
                    checksum_wait_seconds=10,
                ),
                data=final_zzz_data,
                index=1,
                label="FINAL_ZZZ",
            ),
        ),
    )
