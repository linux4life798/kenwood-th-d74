"""Decode Kenwood updater executable firmware resources."""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from enum import IntEnum, unique
from pathlib import Path
from typing import Self

import fldm
from pydantic.dataclasses import dataclass
import thd75_fw.file_cipher
import thd75_fw.intel_hex
import thd75_fw.resource

from firmware import BaudOption, FirmwareDescriptor
import utils

type GlobalMetadata = dict[str, list[str]]
type SegmentMetadata = dict[str, str]
type RawMetadataBlock = tuple[bytes, ...]


@unique
class D74OfficialFirmwareSections(IntEnum):
    """Known TH-D74 flash section base addresses (SA values from updater metadata).

    These are local labels for known TH-D74 flash addresses. The updater EXE
    metadata does have comments explaining each section, but they are in
    Japanese.
    """

    FIRMWARE = 0x6020_0000  # ARM program write data block
    IMAGE_DATA = 0x6060_0000  # Portable Image program write data block
    DSP_PRGM = 0x60E0_0000  # DSP program write data block
    VOICE_DATA = 0x6100_0000  # Voice Announce write data block
    FONT_DATA = 0x6150_0000  # Font write data block
    CHECKBYTES = 0x6020_0062  # Checksum write data block
    FINAL_ZZZ = 0x6020_0040  # Magic-word program write data block

    @property
    def label(self) -> str:
        """Short English label (same as the enum member name)."""
        return self.name

    @classmethod
    def label_for_flash_start_addr(cls, flash_start_addr: int) -> str:
        """Resolve a segment label from flash start address (SA)."""
        try:
            return cls(flash_start_addr).label
        except ValueError:
            return f"UNKNOWN_{utils.hex_fmt(flash_start_addr)}"


@dataclass(frozen=True, slots=True)
class UpdateExe:
    """Decoded firmware payload from a Kenwood updater executable."""

    exe_path: Path
    resource_chars: int
    firmware_descriptor: FirmwareDescriptor
    segments: tuple[fldm.Segment, ...]
    segment_comments: tuple[tuple[str, ...], ...]

    @classmethod
    def from_exe(cls, exe_path: Path) -> Self:
        """Load, decrypt, and parse the firmware resource in an updater EXE."""
        exe_path = Path(exe_path)
        firmware_resource = thd75_fw.resource.load(exe_path)
        decrypted_resource = thd75_fw.file_cipher.decrypt_resource(firmware_resource)
        raw_metadata_blocks = _decrypt_metadata_blocks(firmware_resource)
        firmware_descriptor = _parse_firmware_descriptor(decrypted_resource.metadata)
        segments = tuple(
            _parse_segment(index, block)
            for index, block in enumerate(decrypted_resource.blocks)
        )
        if len(raw_metadata_blocks) != len(segments):
            raise ValueError(
                "raw metadata block count does not match decoded segment count: "
                f"{len(raw_metadata_blocks)} != {len(segments)}"
            )
        segment_comments = tuple(
            _extract_segment_comments(block) for block in raw_metadata_blocks
        )
        segment_count = firmware_descriptor.segment_count
        if segment_count is not None and segment_count != len(segments):
            raise ValueError(
                f"firmware descriptor declares {segment_count} segments, "
                f"but decoded {len(segments)}"
            )

        return cls(
            exe_path=exe_path,
            resource_chars=len(firmware_resource),
            firmware_descriptor=firmware_descriptor,
            segments=segments,
            segment_comments=segment_comments,
        )

    def print(self) -> None:
        """Print the parsed updater object in a readable form."""
        print(f"Updater: {self.exe_path}")
        print(f"Resource chars: {self.resource_chars:,} bytes")
        print("FirmwareDescriptor:")
        print(f"  {self.firmware_descriptor!r}")
        print("Segments:")
        for segment, comments in zip(
            self.segments,
            self.segment_comments,
            strict=True,
        ):
            for comment in comments:
                print(f"  [{segment.index}] comment: {comment}")
            segment.print_dry_run(compatible=True)


def is_windows_exe(program: Path) -> bool:
    """Return true when the input looks like a Windows updater executable."""
    with program.open("rb") as fp:
        return fp.read(2) == b"MZ"


def load(program: Path) -> tuple[FirmwareDescriptor, tuple[fldm.Segment, ...]]:
    """Load firmware metadata and segments from a Windows updater executable."""
    update_exe = UpdateExe.from_exe(program)
    return update_exe.firmware_descriptor, update_exe.segments


def _parse_firmware_descriptor(
    metadata: tuple[str, ...],
) -> FirmwareDescriptor:
    """Parse global `#` metadata into readable firmware fields."""
    global_metadata = _extract_global_metadata(metadata)
    return FirmwareDescriptor(
        hardware_version=_first_metadata_int(global_metadata, "HV"),
        target_unit=_first_metadata_int(global_metadata, "TU"),
        baud_options=_parse_baud_options(global_metadata.get("BR", ())),
        updater_flag=_first_metadata_int(global_metadata, "AF"),
        target_type_mask=_first_target_type_mask(global_metadata, "TT"),
        start_program_code=_first_metadata_int(global_metadata, "TC"),
        completion_code=_first_metadata_int(global_metadata, "FC"),
        firmware_version=_first_metadata_value(global_metadata, "FV") or "",
        segment_count=_first_metadata_int(global_metadata, "DN"),
    )


def _parse_segment(
    index: int,
    block: thd75_fw.file_cipher.DecryptedBlock,
) -> fldm.Segment:
    """Parse one decrypted block into a firmware segment."""
    metadata = _extract_segment_metadata(block.metadata)
    descriptor = _parse_segment_descriptor(metadata)
    parsed = thd75_fw.intel_hex.parse(block.data)
    if parsed.errors:
        raise ValueError(f"segment {index} Intel HEX parse errors: {parsed.errors}")
    return fldm.Segment(
        descriptor=descriptor,
        data=_segment_data(index, descriptor, bytes(parsed.data)),
        index=index,
        label=D74OfficialFirmwareSections.label_for_flash_start_addr(
            descriptor.flash_start_addr
        ),
    )


def _parse_segment_descriptor(metadata: SegmentMetadata) -> fldm.SegmentDescriptor:
    """Build a loader segment descriptor from official `$` metadata keys."""
    version_bytes = _metadata_bytes(metadata, "VA", b"")
    version_length = _metadata_int(metadata, "VL")
    erase_wait_seconds = _metadata_int(metadata, "ET")
    checksum_wait_seconds = _metadata_int(metadata, "CT")
    if version_length is not None and version_length != len(version_bytes):
        raise ValueError(
            "segment metadata VL does not match VA length: "
            f"VL=0x{version_length:08x}, VA={len(version_bytes)} bytes"
        )

    return fldm.SegmentDescriptor(
        flash_start_addr=_required_metadata_int(metadata, "SA"),
        data_length=_required_metadata_int(metadata, "DL"),
        erase_length=_required_metadata_int(metadata, "EL"),
        expected_before_checksum=_required_metadata_int(metadata, "CB"),
        expected_after_checksum=_required_metadata_int(metadata, "CA"),
        checksum_start_offset=_required_metadata_int(metadata, "CS"),
        checksum_length=_required_metadata_int(metadata, "CL"),
        final_version_offset=_required_metadata_int(metadata, "VS"),
        expected_final_version_string=version_bytes,
        target_type_mask=_metadata_target_type_mask(metadata, "TT"),
        erase_wait_seconds=0 if erase_wait_seconds is None else erase_wait_seconds,
        checksum_wait_seconds=(
            0x0A if checksum_wait_seconds is None else checksum_wait_seconds
        ),
    )


def _segment_data(
    index: int,
    descriptor: fldm.SegmentDescriptor,
    parsed_data: bytes,
) -> bytes:
    """Return data trimmed to the updater-declared segment length."""
    data_length = descriptor.data_length
    if len(parsed_data) < data_length:
        raise ValueError(
            f"segment {index} data is shorter than declared DL: "
            f"got 0x{len(parsed_data):08x}, expected 0x{data_length:08x}"
        )
    extra = parsed_data[data_length:]
    if any(byte != 0xFF for byte in extra):
        raise ValueError(
            f"segment {index} has non-padding data beyond declared DL: "
            f"got 0x{len(parsed_data):08x}, expected 0x{data_length:08x}"
        )
    return parsed_data[:data_length]


def _extract_global_metadata(metadata: tuple[str, ...]) -> GlobalMetadata:
    """Return global `#` metadata from decrypted updater metadata lines."""
    globals_: dict[str, list[str]] = {}
    for line in metadata:
        stripped = line.strip()
        if not stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped[1:].split("=", 1)
        globals_.setdefault(key, []).append(_clean_metadata_value(value))
    return globals_


def _extract_segment_metadata(metadata: tuple[str, ...]) -> SegmentMetadata:
    """Return one segment's `$` metadata fields."""
    segment: dict[str, str] = {}
    for line in metadata:
        stripped = line.strip()
        if not stripped.startswith("$") or "=" not in stripped:
            continue
        key, value = stripped[1:].split("=", 1)
        segment[key] = _clean_metadata_value(value)
    return segment


def _decrypt_metadata_blocks(resource_text: str) -> tuple[RawMetadataBlock, ...]:
    """Decrypt per-segment metadata while preserving original comment bytes."""
    state = thd75_fw.file_cipher.RollingKeyState()
    blocks: list[RawMetadataBlock] = []
    current_meta: list[bytes] = []
    has_data = False

    for line in resource_text.split("\n"):
        line = line.strip("\r").strip()
        if not line:
            continue

        line_type, decrypted = thd75_fw.file_cipher.decrypt_line(line, state)

        if line_type == "$":
            if has_data:
                blocks.append(tuple(current_meta))
                current_meta.clear()
                has_data = False
            current_meta.append(decrypted)
        elif line_type == "D":
            has_data = True

    if has_data:
        blocks.append(tuple(current_meta))

    return tuple(blocks)


def _extract_segment_comments(metadata: RawMetadataBlock) -> tuple[str, ...]:
    """Return the updater comment block immediately before one segment."""
    pending_comments: list[bytes] = []
    for line in metadata:
        stripped = line.strip()
        if stripped == b"$ST":
            return tuple(
                comment
                for line in pending_comments
                if (comment := _decode_comment_bytes(line))
            )
        if stripped.startswith(b";"):
            pending_comments.append(stripped)
        else:
            pending_comments.clear()
    return ()


def _decode_comment_bytes(line: bytes) -> str:
    """Decode an updater comment without replacing unknown bytes."""
    comment = line[1:].strip()
    for encoding in ("utf-8", "cp932", "shift_jis"):
        try:
            return comment.decode(encoding)
        except UnicodeDecodeError:
            pass
    return comment.decode("latin-1")


def _clean_metadata_value(value: str) -> str:
    """Remove updater-script string quotes around a metadata value."""
    value = value.strip()
    return (
        value[1:-1]
        if len(value) >= 2 and value.startswith('"') and value.endswith('"')
        else value
    )


def _first_metadata_value(
    metadata: GlobalMetadata,
    key: str,
) -> str | None:
    """Return the first global metadata value for a key."""
    return values[0] if (values := metadata.get(key)) else None


def _first_metadata_int(
    metadata: GlobalMetadata,
    key: str,
) -> int | None:
    """Parse the first integer global metadata value for a key."""
    value = _first_metadata_value(metadata, key)
    return None if value is None else _parse_int(value)


def _first_target_type_mask(
    metadata: GlobalMetadata,
    key: str,
) -> int | None:
    """Parse the first global target-type mask for a key."""
    value = _first_metadata_value(metadata, key)
    return None if value is None else _parse_target_type_mask(value)


def _parse_baud_options(values: Iterable[str]) -> tuple[BaudOption, ...]:
    """Parse all `#BR` baud/ACK metadata entries."""
    baud_options: list[BaudOption] = []
    for value in values:
        parts = [part.strip() for part in value.split(",")]
        if len(parts) != 2:
            raise ValueError(f"BR metadata must be baud,ack: {value!r}")
        ack = _parse_int(parts[1])
        if ack not in (0, 1):
            raise ValueError(f"BR ACK flag must be 0 or 1: {value!r}")
        baud_options.append(
            BaudOption(
                baud=_parse_int(parts[0]),
                ack_each_data_packet=bool(ack),
            )
        )
    return tuple(baud_options)


def _required_metadata_int(metadata: SegmentMetadata, key: str) -> int:
    """Parse a required integer segment metadata field."""
    value = _metadata_int(metadata, key)
    if value is None:
        raise ValueError(f"missing required segment metadata ${key}")
    return value


def _metadata_int(
    metadata: SegmentMetadata,
    key: str,
) -> int | None:
    """Parse one integer metadata field if present."""
    return None if (value := metadata.get(key)) is None else _parse_int(value)


def _metadata_target_type_mask(metadata: SegmentMetadata, key: str) -> int:
    """Parse one target-type mask metadata field."""
    value = metadata.get(key)
    if value is None:
        raise ValueError(f"missing required segment metadata ${key}")
    return _parse_target_type_mask(value)


def _metadata_bytes(metadata: SegmentMetadata, key: str, default: bytes) -> bytes:
    """Encode one ASCII metadata string as bytes."""
    return default if (value := metadata.get(key)) is None else value.encode("ascii")


def _parse_int(value: str) -> int:
    """Parse decimal or `0x` integer metadata."""
    return int(value, 16 if value.lower().startswith("0x") else 10)


def _parse_target_type_mask(value: str) -> int:
    """Parse an updater target-type mask from integer or byte-string syntax."""
    compact = "".join(value.split())
    if not compact.lower().startswith("0x") and len(compact) % 2 == 0:
        try:
            return int.from_bytes(bytes.fromhex(compact), "little")
        except ValueError:
            pass
    return _parse_int(value)


def main() -> None:
    """Parse arguments and print decoded updater firmware objects."""
    parser = argparse.ArgumentParser()
    parser.add_argument("exe", type=Path, help="path to the Kenwood updater .exe")
    args = parser.parse_args()
    UpdateExe.from_exe(args.exe).print()


if __name__ == "__main__":
    main()
