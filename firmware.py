"""Shared firmware metadata models for TH-D74 updater resources."""

from __future__ import annotations

import struct

from pydantic import Field
from pydantic.dataclasses import dataclass

import utils

DEFAULT_TARGET_TYPE_MASK = 0x0F
"""
Target variant compatibility mask, decoded as a little-endian 8-byte value.
Firmware update files provide a value like the following:
`$TT="0F 00 00 00 00 00 00 00"`
This is decoded as 0x0F, which is then considered compatible with devices
whose returned target variant is 0x1, 0x2, 0x4, or 0x8.
"""

SEGMENT_DESCRIPTOR_PREFIX_SIZE = 0x34
SEGMENT_DESCRIPTOR_SIZE = 0x58


def fldm_sum16(data: bytes) -> int:
    """Calculate the FLDM additive halfword sum used for segment verification.

    Use this when preparing `SegmentDescriptor.expected_after_checksum` from
    incoming firmware bytes, or `SegmentDescriptor.expected_before_checksum`
    when you have bytes for the expected pre-write flash contents.
    """
    total = 0
    data = bytes(data)
    for offset in range(0, len(data) & ~1, 2):
        total = (total + int.from_bytes(data[offset : offset + 2], "little")) & 0xFFFF
    return total


@dataclass(frozen=True, slots=True)
class BaudOption:
    """One baud/transfer option from a `#BR` metadata line."""

    baud: utils.UInt32
    ack_each_data_packet: bool


@dataclass(frozen=True, slots=True)
class FirmwareDescriptor:
    """High-level metadata for a firmware updater resource."""

    hardware_version: utils.UInt32 | None = None
    target_unit: utils.UInt32 | None = None
    baud_options: tuple[BaudOption, ...] = ()
    updater_flag: utils.UInt32 | None = None
    target_type_mask: utils.UInt64 | None = None
    start_program_code: utils.UInt32 | None = None
    completion_code: utils.UInt32 | None = None
    firmware_version: str = ""
    segment_count: utils.UInt32 | None = None


@dataclass(frozen=True, slots=True)
class SegmentDescriptor:
    """Description of one flash region to validate, erase, and program.

    The loader consumes the updater's `DataBlockInfo` prefix followed by the
    optional expected final version string. The field order matches the
    official updater's marshaled structure.

    Attributes:
        flash_start_addr: Memory-mapped flash address, usually
            `0x60000000 + offset`.
        data_length: Total number of data bytes expected for the segment.
        erase_length: Number of bytes to erase from `flash_start_addr`.
        target_type_mask: Target variant compatibility mask, decoded as a
            little endian 8-byte value. Firmware update files provide values
            like `$TT="0F 00 00 00 00 00 00 00"`, which decodes as `0x0f` and
            is compatible with devices whose returned target variant is `0x1`,
            `0x2`, `0x4`, or `0x8`.
        erase_wait_seconds: Segment erase wait time in seconds.
        expected_before_checksum: Halfword checksum expected from current flash
            before writing. If the final-version marker matches during setup,
            the firmware calculates the checksum range from current flash and
            compares it with this value before returning the setup decision.
        expected_after_checksum: Halfword checksum expected after writing. The
            firmware calculates the same checksum range after transfer
            completion and compares it with this value for final verification.
            This is not assumed to equal `expected_before_checksum`; official
            updater metadata can and does provide different values.
        checksum_start_offset: Offset from `flash_start_addr` for the checksum
            range.
        checksum_length: Number of bytes in the checksum range.
        checksum_wait_seconds: Final checksum wait time in seconds.
        final_version_offset: Offset from `flash_start_addr` where this version
            string should reside after programming. Setup uses the same location
            to decide whether current flash already contains the requested
            version.
        expected_final_version_string: Version text from the updater metadata.
            During setup, the firmware treats this as an already-installed
            marker: if the bytes at `flash_start_addr + final_version_offset`
            and the before-write checksum both match, the segment can be
            skipped. The handheld also displays this string during the update.
    """

    flash_start_addr: utils.UInt32
    data_length: utils.UInt32
    erase_length: utils.UInt32
    expected_before_checksum: utils.UInt16
    expected_after_checksum: utils.UInt16
    checksum_start_offset: utils.UInt32
    checksum_length: utils.UInt32
    final_version_offset: utils.UInt32
    expected_final_version_string: bytes = Field(
        default=b"",
        max_length=SEGMENT_DESCRIPTOR_SIZE - SEGMENT_DESCRIPTOR_PREFIX_SIZE,
    )
    target_type_mask: utils.UInt64 = DEFAULT_TARGET_TYPE_MASK
    erase_wait_seconds: utils.UInt32 = 0
    checksum_wait_seconds: utils.UInt32 = 0x0A

    def to_payload(self) -> bytes:
        """Serialize this descriptor into the loader's setup payload."""
        descriptor = struct.pack(
            "<III4xQIHHIIIII",
            self.flash_start_addr,
            self.data_length,
            self.erase_length,
            # 4 padding bytes
            self.target_type_mask,
            self.erase_wait_seconds,
            self.expected_before_checksum,
            self.expected_after_checksum,
            self.checksum_start_offset,
            self.checksum_length,
            self.checksum_wait_seconds,
            self.final_version_offset,
            len(self.expected_final_version_string),
        )
        descriptor += self.expected_final_version_string
        return descriptor


@dataclass(frozen=True, slots=True, repr=False)
class Segment:
    """One firmware segment plus its updater metadata."""

    descriptor: SegmentDescriptor
    data: bytes
    index: int = 0
    label: str = ""

    def __post_init__(self) -> None:
        """Validate that segment bytes match the descriptor length."""
        if len(self.data) != self.descriptor.data_length:
            raise ValueError(
                "segment data length does not match descriptor data_length "
                f"0x{self.descriptor.data_length:08x}: got 0x{len(self.data):08x}"
            )

    def print_dry_run(self, *, compatible: bool) -> None:
        """Print the flash operations that would be attempted for this segment."""
        descriptor = self.descriptor
        erase_range = self._format_addr_range(descriptor.erase_length)
        write_range = self._format_addr_range(descriptor.data_length)
        print(
            f"  [{self.index}] {self.label} "
            f"compatible={compatible} "
            f"erase={erase_range} "
            f"write={write_range} "
            f"data_length={utils.hex_fmt(descriptor.data_length)} "
            f"({descriptor.data_length:,}) "
            f"expected_before_checksum="
            f"{utils.hex_fmt(descriptor.expected_before_checksum, width=4)} "
            f"expected_after_checksum="
            f"{utils.hex_fmt(descriptor.expected_after_checksum, width=4)}"
        )

    def _format_addr_range(self, length: int) -> str:
        """Format a half-open address range starting at this segment base."""
        start_addr = self.descriptor.flash_start_addr
        return f"{utils.hex_fmt(start_addr)}..{utils.hex_fmt(start_addr + length)}"

    def __repr__(self) -> str:
        """Return a compact representation that does not dump segment bytes."""
        preview = self.data[:16].hex(" ")
        return (
            "Segment("
            f"index={self.index!r}, "
            f"label={self.label!r}, "
            f"descriptor={self.descriptor!r}, "
            f"data_len={len(self.data)}, "
            f"data_preview={preview!r}"
            ")"
        )
