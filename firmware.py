"""Shared firmware metadata models for TH-D74 updater resources."""

from __future__ import annotations

from pydantic.dataclasses import dataclass

import utils


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


