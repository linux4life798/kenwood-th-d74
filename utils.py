"""Shared utility helpers for Openwood modules."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field


# Fields annotated with these aliases are still plain `int` values at runtime.
# The extra annotation data is read by validation code when parsing inputs or
# constructing models, so values outside the matching C-style uint range are
# rejected up front.
type UInt8 = Annotated[int, Field(strict=True, ge=0, le=0xFF)]
type UInt16 = Annotated[int, Field(strict=True, ge=0, le=0xFFFF)]
type UInt32 = Annotated[int, Field(strict=True, ge=0, le=0xFFFF_FFFF)]
type UInt64 = Annotated[int, Field(strict=True, ge=0, le=0xFFFF_FFFF_FFFF_FFFF)]


def validate_uint(name: str, value: int, bits: int) -> None:
    """Validate that a value fits in an unsigned integer bit width."""
    if bits <= 0:
        raise ValueError("bits must be positive")
    if not 0 <= value < (1 << bits):
        raise ValueError(f"{name} must fit in uint{bits}")


def hex_fmt(value: int, width: int = 8) -> str:
    """Format an integer as grouped hex, e.g. `0x1234_abcd`."""
    validate_uint("value", value, width * 4)
    digits = f"{value:0{width}x}"
    groups: list[str] = []
    while digits:
        groups.append(digits[-4:])
        digits = digits[:-4]
    return "0x" + "_".join(reversed(groups))
