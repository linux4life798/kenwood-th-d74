#!/usr/bin/env python3
"""Serial client helpers for the TH-D74 FLDM firmware loader protocol."""

from __future__ import annotations

import argparse
import os
import struct
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from types import TracebackType

import serial

SYNC = b"\xab\xab"
MAGIC = b"FPROMOD"

CMD_START_PROGRAM = 0x30
CMD_QUERY_TARGET_PROFILE = 0x31
CMD_BAUD_TRANSFER_MODE_SELECT = 0x33
CMD_SEGMENT_SETUP = 0x40
CMD_BEGIN_TRANSFER = 0x42
CMD_DATA_PACKET = 0x43
CMD_TRANSFER_END = 0x44
CMD_SEGMENT_DONE = 0x45
CMD_COMPLETE = 0x50
CMD_START_TIMED_SESSION = 0xA0
CMD_TARGET_UNIT = 0xA3  # Only exists in the official updater. DNE in firmware.

VERB_OK = 0x06
VERB_BUSY = 0x11
VERB_ERROR = 0x15
VERB_UNLOCK_ACK = 0x16
"""Followed by one-byte error code, VERB_ERROR_CODES."""
VERB_ERROR_CODES = {
    0x01: "unsupported command",
    0x02: "invalid start-program payload",
    0x03: "data packet/write rejected",
    0x04: "command already active",  # Busy doing flash operation.
}

DEFAULT_COMPLETE_CODE = 0xBC15
SEGMENT_DESCRIPTOR_PREFIX_SIZE = 0x34
SEGMENT_DESCRIPTOR_SIZE = 0x58
MAX_DATA_CHUNK_SIZE = 0x800
DEFAULT_DATA_CHUNK_SIZE = 0x400
_ANSI_LIGHT_GREY = "\x1b[90m"
_ANSI_RESET = "\x1b[0m"


class FLDMBaudMode(Enum):
    """Official TH-D74 FLDM baud/transfer-mode selections."""

    # The official updater's shared baud-code helper recognizes all of the
    # following baud rates. However, the ones that are currently uncommented
    # are considered the active TH-D74 modes, from the `#BR` metadata. Only
    # these modes actually provide the extra data-packet ACK policy / boolean.
    # B600 = (600, 0x00, False)
    # B1200 = (1200, 0x01, False)
    # B2400 = (2400, 0x02, False)
    # B4800 = (4800, 0x03, False)
    # B9600 = (9600, 0x04, False)
    # B14400 = (14400, 0x05, False)
    # B19200 = (19200, 0x06, False)
    # B28800 = (28800, 0x07, False)
    # B38400 = (38400, 0x08, False)
    B57600 = (57600, 0x09, False)
    B115200 = (115200, 0x0A, False)
    # B128000 = (128000, 0x0B, False)
    # B144000 = (144000, 0x0C, False)
    # B164571 = (164571, 0x0D, False)
    # B192000 = (192000, 0x0E, False)
    # B230400 = (230400, 0x0F, False)
    # B288000 = (288000, 0x10, False)
    # B384000 = (384000, 0x11, False)
    B576000 = (576000, 0x12, True)
    # Mode code 0x13 was not present in the updater's generic mapping, but it
    # would probably be 768000.
    B1152000 = (1152000, 0x14, True)

    def __init__(self, baud: int, baud_code: int, ack_each_data_packet: bool) -> None:
        """Store one `#BR` table entry from the official updater metadata.

        Args:
            baud: Real host serial baud rate value.
            baud_code: The smaller code used to represent the baud rate.
            ack_each_data_packet: Whether accepted data transfer packets are ACKed.
        """
        self.baud = baud
        self.mode_code = baud_code
        self.ack_each_data_packet = ack_each_data_packet

    @classmethod
    def from_baud(cls, baud: int) -> FLDMBaudMode:
        """Return the official FLDM mode for a baud rate.

        Args:
            baud: Host serial baud rate/CDC line-coding value.

        Returns:
            Matching FLDM baud mode.

        Raises:
            ValueError: If the baud rate is not present in the updater metadata.
        """
        for mode in cls:
            if mode.baud == baud:
                return mode
        raise ValueError(f"unsupported TH-D74 FLDM baud rate {baud}")


def _xor(data: bytes, key: int) -> bytes:
    """Return data XORed with the one-byte FLDM key.

    Args:
        data: Bytes to transform.
        key: One-byte XOR key. Zero leaves data unchanged.

    Returns:
        Transformed bytes.
    """
    return data if key == 0 else bytes(b ^ key for b in data)


def _validate_uint(name: str, value: int, bits: int) -> None:
    """Validate that a value fits in an unsigned integer bit width.

    Args:
        name: Field name used in the exception message.
        value: Integer value to validate.
        bits: Unsigned integer bit width.

    Raises:
        ValueError: If value is outside the selected unsigned range.
    """
    if bits <= 0:
        raise ValueError("bits must be positive")
    if not 0 <= value < (1 << bits):
        raise ValueError(f"{name} must fit in uint{bits}")


def fldm_sum16(data: bytes) -> int:
    """Calculate the FLDM additive halfword sum used for segment verification.

    Use this when preparing `SegmentDescriptor.expected_after_checksum` from
    incoming firmware bytes, or `SegmentDescriptor.expected_before_checksum`
    when you have bytes for the expected pre-write flash contents.

    Args:
        data: Bytes to sum as little-endian 16-bit words. An odd trailing byte is
            ignored, matching the firmware implementation.

    Returns:
        The low 16 bits of the additive halfword sum.
    """
    total = 0
    data = bytes(data)
    for offset in range(0, len(data) & ~1, 2):
        total = (total + int.from_bytes(data[offset : offset + 2], "little")) & 0xFFFF
    return total


@dataclass(frozen=True, slots=True)
class FLDMFrame:
    """Decoded FLDM frame.

    Attributes:
        verb: One-byte command or response verb.
        payload: Command or response payload bytes.
        header: One-byte reserved header. The firmware stores but does not
            validate this byte; it must still be included in the checksum.
    """

    verb: int
    payload: bytes = b""
    header: int = 0

    def __post_init__(self) -> None:
        """Normalize payload bytes and validate fixed-width fields."""
        _validate_uint("header", self.header, 8)
        _validate_uint("verb", self.verb, 8)
        object.__setattr__(self, "payload", bytes(self.payload))

    @property
    def body_len(self) -> int:
        """Return the firmware body length: one verb byte plus payload bytes."""
        return 1 + len(self.payload)

    @property
    def checksum(self) -> int:
        """Return the frame checksum byte."""
        return sum(self._body_without_checksum()) & 0xFF

    def _body_without_checksum(self) -> bytes:
        """Return the frame body bytes covered by the checksum."""
        return (
            bytes([self.header])
            + self.body_len.to_bytes(4, "little")
            + bytes([self.verb])
            + self.payload
        )

    def to_bytes(self, *, xor_key: int = 0) -> bytes:
        """Encode the frame for transmission.

        Args:
            xor_key: Session XOR key. Use zero for cleartext `FPROMOD` mode.

        Returns:
            The raw bytes to write to the serial port.
        """
        _validate_uint("xor_key", xor_key, 8)
        frame = SYNC + self._body_without_checksum() + bytes([self.checksum])
        return _xor(frame, xor_key)


@dataclass(frozen=True, slots=True)
class FLDMTargetProfile:
    """Loader target profile returned before segment programming starts.

    Attributes:
        target_variant_mask: Target variant bits selected by the loader.
        loader_profile_mask: Additional loader profile bits. This firmware
            initializes the value to 2 and only returns it in this response.
        status_code: Trailing status byte. This firmware writes zero.
    """

    target_variant_mask: int
    loader_profile_mask: int
    status_code: int

    @classmethod
    def from_payload(cls, payload: bytes) -> FLDMTargetProfile:
        """Decode the loader's target-profile payload.

        Args:
            payload: The 17-byte payload returned by the loader.

        Returns:
            Parsed target-profile values.

        Raises:
            ValueError: If the payload has the wrong length.
        """
        if len(payload) != 17:
            raise ValueError(
                f"target profile payload must be 17 bytes, got {len(payload)}"
            )
        return cls(
            target_variant_mask=int.from_bytes(payload[0:8], "little"),
            loader_profile_mask=int.from_bytes(payload[8:16], "little"),
            status_code=payload[16],
        )


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
        allowed_target_variant_mask: Target compatibility mask from the updater
            metadata `TT` field.
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

    flash_start_addr: int
    data_length: int
    erase_length: int
    expected_before_checksum: int
    expected_after_checksum: int
    checksum_start_offset: int
    checksum_length: int
    final_version_offset: int
    expected_final_version_string: bytes = b""
    allowed_target_variant_mask: int = 0x0F
    erase_wait_seconds: int = 0
    checksum_wait_seconds: int = 0x0A

    def __post_init__(self) -> None:
        """Validate fixed-width fields and normalize the final version string."""
        for name in (
            "flash_start_addr",
            "data_length",
            "erase_length",
            "checksum_start_offset",
            "checksum_length",
            "final_version_offset",
            "erase_wait_seconds",
            "checksum_wait_seconds",
        ):
            _validate_uint(name, getattr(self, name), 32)
        _validate_uint(
            "allowed_target_variant_mask", self.allowed_target_variant_mask, 64
        )
        _validate_uint("expected_before_checksum", self.expected_before_checksum, 16)
        _validate_uint("expected_after_checksum", self.expected_after_checksum, 16)

        expected_final_version_string = bytes(self.expected_final_version_string)
        max_expected_final_version_string = (
            SEGMENT_DESCRIPTOR_SIZE - SEGMENT_DESCRIPTOR_PREFIX_SIZE
        )
        if len(expected_final_version_string) > max_expected_final_version_string:
            raise ValueError(
                "expected_final_version_string must be at most "
                f"{max_expected_final_version_string} bytes, "
                f"got {len(expected_final_version_string)}"
            )
        object.__setattr__(
            self, "expected_final_version_string", expected_final_version_string
        )

    def to_payload(self) -> bytes:
        """Serialize this descriptor into the loader's setup payload.

        Returns:
            The descriptor prefix plus its expected final version string.
        """
        descriptor = struct.pack(
            "<4IQIHH5I",
            self.flash_start_addr,
            self.data_length,
            self.erase_length,
            0,
            self.allowed_target_variant_mask,
            self.erase_wait_seconds,
            self.expected_before_checksum,
            self.expected_after_checksum,
            self.checksum_start_offset,
            self.checksum_length,
            self.checksum_wait_seconds,
            self.final_version_offset,
            len(self.expected_final_version_string),
        )
        return descriptor + self.expected_final_version_string


@dataclass(frozen=True, slots=True)
class SegmentSetupResult:
    """Decision returned after the loader checks the target segment.

    Attributes:
        code: One-byte firmware result. `0` means current flash matched the
            descriptor checks; `1` means update required or setup check failed.
    """

    code: int

    def __post_init__(self) -> None:
        """Validate the one-byte setup result code."""
        _validate_uint("code", self.code, 8)
        if self.code not in (0, 1):
            raise ValueError(f"unexpected segment setup result 0x{self.code:02x}")

    @property
    def current_matches(self) -> bool:
        """Return true when the current flash already matches the descriptor."""
        return self.code == 0

    @property
    def update_required(self) -> bool:
        """Return true when the host should write the segment."""
        return self.code == 1


@dataclass(frozen=True, slots=True)
class SegmentVerifyResult:
    """Result of the loader's final segment verification pass.

    Attributes:
        code: One-byte firmware result. `0` means final verification succeeded;
            `1` means final verification failed.
    """

    code: int

    def __post_init__(self) -> None:
        """Validate the one-byte final verification result code."""
        _validate_uint("code", self.code, 8)
        if self.code not in (0, 1):
            raise ValueError(f"unexpected segment verify result 0x{self.code:02x}")

    @property
    def verified(self) -> bool:
        """Return true when the segment final sum matched."""
        return self.code == 0


class FLDMCommandError(RuntimeError):
    """Raised when the loader returns an error frame (`0x15`)."""

    def __init__(self, code: int, frame: FLDMFrame) -> None:
        """Create an exception for a firmware error response.

        Args:
            code: First payload byte from the error response.
            frame: Full error response frame.
        """
        self.code = code
        self.frame = frame
        description = VERB_ERROR_CODES.get(code, "unknown error")
        super().__init__(f"FLDM error 0x{code:02x}: {description}")


class FLDMLoader:
    """Serial client for the TH-D74 FLDM firmware loader."""

    def __init__(
        self,
        port: str,
        *,
        baud: int = 115200,
        reply_timeout: float = 2.0,
        xor_key: int = 0,
        max_payload: int = 4096,
        verbose: bool = False,
    ) -> None:
        """Open a serial connection to the FLDM loader.

        Args:
            port: Serial device path.
            baud: Host serial baud rate/CDC line-coding value. The USB CDC
                loader does not use this to change firmware transport speed;
                command `0x33` records the derived baud-mode code.
            reply_timeout: Default reply timeout for public command helpers.
                Long segment operations add this as margin to the wait time
                declared by the segment descriptor.
            xor_key: Initial XOR key. Use zero for cleartext unlock.
            max_payload: Maximum accepted response payload length.
            verbose: Print raw TX/RX bytes as they are written or received.
        """
        _validate_uint("xor_key", xor_key, 8)
        self.baud_mode = FLDMBaudMode.from_baud(baud)

        self.reply_timeout = reply_timeout
        self.xor_key = xor_key
        self.max_payload = max_payload
        self.verbose = verbose
        self._use_ansi_color = _stdout_supports_ansi_color()
        self._rx_log_start: float | None = None
        self._rx_log_line_open = False
        self._serial_port: serial.Serial = serial.Serial(
            port=port,
            baudrate=self.baud_mode.baud,
            bytesize=8,
            parity="N",
            stopbits=1,
            timeout=0.25,
            write_timeout=1,
        )
        self._serial_port.reset_input_buffer()
        self._serial_port.reset_output_buffer()

    def __enter__(self) -> FLDMLoader:
        """Return this client for use as a context manager."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the serial connection on context-manager exit."""
        self.close()

    @staticmethod
    def calculate_xor_key(magic: bytes) -> int:
        """Calculate the keyed unlock XOR value from an 11-byte magic packet.

        Args:
            magic: Full keyed unlock packet. Bytes `9` and `10` are used.

        Returns:
            The XOR key used for framed traffic.

        Raises:
            ValueError: If `magic` is shorter than 11 bytes.
        """
        if len(magic) < 11:
            raise ValueError("keyed unlock magic must contain at least 11 bytes")
        key = ((-(magic[9] + magic[10])) ^ 0xB8) & 0xFF
        return 0x74 if key == 0 else key

    def close(self) -> None:
        """Close the serial connection."""
        if self._serial_port and self._serial_port.is_open:
            self._serial_port.close()

    def send_raw(self, data: bytes) -> None:
        """Write raw bytes to the serial port.

        Args:
            data: Bytes to write without FLDM framing.
        """
        self._log_tx_bytes(data)
        self._serial_port.write(data)
        self._serial_port.flush()

    def recv_raw(self, timeout: float | None = None) -> bytes | None:
        """Read all raw bytes available until timeout.

        Args:
            timeout: Timeout in seconds. Uses `reply_timeout` when omitted.

        Returns:
            Bytes read, or `None` if no bytes arrived.
        """
        with self.log_rx_window():
            end = time.monotonic() + (
                self.reply_timeout if timeout is None else timeout
            )
            out = bytearray()
            while time.monotonic() < end:
                chunk = self._serial_port.read_all()
                if chunk:
                    self._log_rx_bytes(chunk)
                    out.extend(chunk)
                else:
                    time.sleep(0.01)
            return bytes(out) if out else None

    def send_frame(self, frame: FLDMFrame) -> None:
        """Send an already constructed FLDM frame.

        Args:
            frame: Frame to encode and transmit.
        """
        self.send_raw(frame.to_bytes(xor_key=self.xor_key))

    def recv_frame(self, timeout: float | None = None) -> FLDMFrame:
        """Receive and decode one framed FLDM response.

        Args:
            timeout: Timeout in seconds. Uses `reply_timeout` when omitted.

        Returns:
            Decoded frame.

        Raises:
            TimeoutError: If a complete frame is not received in time.
            ValueError: If the frame has an invalid length or checksum.
        """
        _validate_uint("xor_key", self.xor_key, 8)

        timeout = self.reply_timeout if timeout is None else timeout
        wire_sync = _xor(SYNC, self.xor_key)
        with self.log_rx_window():
            # Find sync, XORed if encrypted mode is active.
            # This will ignore any remnant bytes that are not sync words.
            window = bytearray()
            while True:
                raw_byte = self._recv_exact(1, timeout)
                window = (window + raw_byte)[-2:]
                if bytes(window) == wire_sync:
                    break

            # Header after sync: header:u8 + body_len:u32le + verb:u8.
            raw_head = self._recv_exact(6, timeout)
            head = _xor(raw_head, self.xor_key)

            header = head[0]
            body_len = int.from_bytes(head[1:5], "little")
            if body_len < 1:
                raise ValueError(f"invalid body length {body_len}")
            if body_len > self.max_payload + 1:
                raise ValueError(f"unreasonable body length {body_len}")

            # Remaining bytes are payload plus checksum.
            tail = _xor(self._recv_exact(body_len, timeout), self.xor_key)
            payload = tail[:-1]
            checksum = tail[-1]

            expected = sum(head + payload) & 0xFF
            if checksum != expected:
                raise ValueError(
                    f"bad checksum: got 0x{checksum:02x}, expected 0x{expected:02x}"
                )

            return FLDMFrame(verb=head[5], payload=payload, header=header)

    @contextmanager
    def log_rx_window(self) -> Iterator[None]:
        """Open a verbose RX logging window for the enclosed receive work."""
        if not self.verbose:
            yield
            return

        self._rx_log_start = time.monotonic()
        self._rx_log_line_open = False
        try:
            yield
        finally:
            if self._rx_log_line_open:
                print(flush=True)
            self._rx_log_start = None
            self._rx_log_line_open = False

    def _log_rx_bytes(self, data: bytes) -> None:
        """Print received bytes immediately inside the current RX window."""
        if not self.verbose or not data:
            return
        start = self._rx_log_start
        if start is None:
            return
        if not self._rx_log_line_open:
            print("RX", end="", flush=True)
            self._rx_log_line_open = True
        timestamp = f"+{time.monotonic() - start:.3f}s"
        if self._use_ansi_color:
            timestamp = f"{_ANSI_LIGHT_GREY}{timestamp}{_ANSI_RESET}"
        print(
            f" {timestamp} {data.hex(' ')}",
            end="",
            flush=True,
        )

    def _log_tx_bytes(self, data: bytes) -> None:
        """Print transmitted bytes immediately."""
        if self.verbose:
            print(f"TX {data.hex(' ')}", flush=True)

    def _recv_exact(self, n: int, timeout: float) -> bytes:
        """Read an exact byte count from the serial port.

        Args:
            n: Number of bytes to read.
            timeout: Total timeout in seconds.

        Returns:
            Exactly `n` bytes.

        Raises:
            TimeoutError: If the requested bytes are not received in time.
        """
        out = bytearray()
        deadline = time.monotonic() + timeout
        while len(out) < n:
            left = deadline - time.monotonic()
            if left <= 0:
                raise TimeoutError("timeout reading frame")
            self._serial_port.timeout = min(left, 0.25)
            chunk = self._serial_port.read(n - len(out))
            if chunk:
                self._log_rx_bytes(chunk)
                out.extend(chunk)
        return bytes(out)

    def send_packet(self, verb: int, payload: bytes = b"", *, header: int = 0) -> None:
        """Send one framed FLDM command without reading a response.

        Args:
            verb: One-byte command verb.
            payload: Command payload.
            header: Reserved frame header byte.
        """
        self.send_frame(FLDMFrame(verb=verb, payload=payload, header=header))

    def unlock(self) -> None:
        """Enter cleartext FLDM programming mode.

        Raises:
            RuntimeError: If the raw unlock replies are not `0x16` then `0x06`.
        """
        self.send_raw(MAGIC)
        self._read_unlock_replies(self.reply_timeout)
        self.xor_key = 0

    def unlock_keyed(self, magic: bytes) -> int:
        """Enter keyed FLDM programming mode.

        Args:
            magic: Full 11-byte keyed unlock packet.

        Returns:
            The XOR key calculated from `magic` and stored on this client.

        Raises:
            RuntimeError: If the raw unlock replies are not `0x16` then `0x06`.
            ValueError: If `magic` is not an 11-byte keyed unlock packet.
        """
        magic = bytes(magic)
        if len(magic) != 11:
            raise ValueError("keyed unlock magic must be exactly 11 bytes")
        if magic[2:9] != b"Thd74tw":
            raise ValueError('keyed unlock magic must contain b"Thd74tw" at bytes 2..8')

        key = self.calculate_xor_key(magic)
        self.send_raw(magic)
        self._read_unlock_replies(self.reply_timeout)
        self.xor_key = key
        return key

    def start_programming(self) -> FLDMFrame:
        """Put the loader into its active programming state.

        The handheld display will start flashing the "PROGRAM" message.

        Returns:
            The acknowledged loader response.
        """
        return self._send_and_expect_ok(CMD_START_PROGRAM, b"\x00")

    def select_target_unit(
        self,
        target_unit: int = 1,
    ) -> FLDMFrame:
        """Select the updater target profile before starting a session.

        This is unsupported on the TH-D74 firmware.

        Args:
            target_unit: Target unit value from the updater metadata.

        Returns:
            The acknowledged loader response.
        """
        _validate_uint("target_unit", target_unit, 32)
        return self._send_and_expect_ok(
            CMD_TARGET_UNIT,
            target_unit.to_bytes(4, "little"),
        )

    def start_timed_session(self) -> FLDMFrame:
        """Start the loader's timed programming session.

        This enables the loader timeout window used during firmware update
        traffic. It does not authenticate the host or exchange a token.

        Returns:
            The acknowledged loader response.
        """
        return self._send_and_expect_ok(CMD_START_TIMED_SESSION)

    def query_target_profile(self) -> FLDMTargetProfile:
        """Read the loader's target/profile compatibility bits.

        Returns:
            Parsed loader target-profile fields.
        """
        frame = self._send_and_expect_reply_frame(CMD_QUERY_TARGET_PROFILE)
        return FLDMTargetProfile.from_payload(frame.payload)

    def set_baud_transfer_mode(self) -> FLDMFrame:
        """Apply this client's configured baud transfer policy to the loader.

        This step tells the loader which official updater baud rate is in use
        and whether accepted data chunks should be acknowledged. On the USB CDC
        loader, the baud code is recorded as protocol metadata; it does not
        reconfigure the transport speed.

        In the official updater, this is actually called rather late, just
        before the segment setup command.

        Returns:
            The acknowledged loader response.
        """
        mode = self.baud_mode
        payload = bytes(
            [
                mode.mode_code,
                1 if mode.ack_each_data_packet else 0,
            ]
        )
        frame = self._send_and_expect_ok(
            CMD_BAUD_TRANSFER_MODE_SELECT,
            payload,
        )
        return frame

    def setup_segment(
        self,
        descriptor: SegmentDescriptor,
    ) -> SegmentSetupResult:
        """Prepare one segment and learn whether it already matches flash.

        Args:
            descriptor: Segment metadata and validation information.

        Returns:
            Parsed setup result. `current_matches` means the segment can be
            skipped by host policy; `update_required` means write the segment.
        """
        # Add reply_timeout as host-side margin; callers can increase it for
        # unknown circumstances.
        timeout = descriptor.checksum_wait_seconds + self.reply_timeout
        frame = self._send_and_expect_reply_frame(
            CMD_SEGMENT_SETUP,
            descriptor.to_payload(),
            payload_len=1,
            timeout=timeout,
        )
        return SegmentSetupResult(frame.payload[0])

    def begin_transfer(self, descriptor: SegmentDescriptor) -> FLDMFrame:
        """Erase the active segment and wait until it is ready for data.

        Args:
            descriptor: Active segment metadata that provides the erase wait.

        Returns:
            The acknowledged loader response after erase completion.
        """
        self.send_packet(CMD_BEGIN_TRANSFER)
        # Add reply_timeout as host-side margin; callers can increase it for
        # unknown circumstances.
        timeout = descriptor.erase_wait_seconds + self.reply_timeout
        frame = self._recv_until_not_busy(timeout=timeout)
        return self._expect_ok(frame)

    def send_data_packet(
        self,
        segment_offset: int,
        data: bytes,
    ) -> FLDMFrame | None:
        """Write one chunk into the active segment transfer buffer.

        Args:
            segment_offset: Offset from the active descriptor base address.
            data: Chunk bytes. Keep chunks at or below `0x800` bytes.

        Returns:
            The acknowledged loader response when ACKs are enabled, otherwise `None`.
        """
        payload = self.build_data_packet(segment_offset, data)
        self.send_packet(CMD_DATA_PACKET, payload)

        if self.baud_mode.ack_each_data_packet:
            return self._expect_ok(self._recv_command_frame())
        return None

    def end_transfer(self) -> FLDMFrame:
        """Tell the loader that all data for the active segment has been sent.

        Returns:
            The acknowledged loader response.
        """
        return self._send_and_expect_ok(CMD_TRANSFER_END)

    def verify_segment_done(self, descriptor: SegmentDescriptor) -> SegmentVerifyResult:
        """Ask the loader to verify the programmed segment contents.

        Args:
            descriptor: Active segment metadata that provides the checksum wait.

        Returns:
            Parsed verification result. `verified` must be true for a successful
            updater flow.
        """
        # Add reply_timeout as host-side margin; callers can increase it for
        # unknown circumstances.
        timeout = descriptor.checksum_wait_seconds + self.reply_timeout
        frame = self._send_and_expect_reply_frame(
            CMD_SEGMENT_DONE,
            payload_len=1,
            timeout=timeout,
        )
        return SegmentVerifyResult(frame.payload[0])

    def complete(
        self,
        code: int | bytes = DEFAULT_COMPLETE_CODE,
    ) -> FLDMFrame:
        """Finish the programming session and let the device leave loader mode.

        The handheld display will show the "Complete" message.

        Args:
            code: Four-byte completion code from the updater metadata, or an
                integer encoded little-endian.

        Returns:
            The acknowledged loader response.
        """
        if isinstance(code, int):
            _validate_uint("code", code, 32)
            payload = code.to_bytes(4, "little")
        else:
            payload = bytes(code)
            if len(payload) != 4:
                raise ValueError("complete code must be four bytes")
        return self._send_and_expect_ok(CMD_COMPLETE, payload)

    def program_segment(
        self,
        descriptor: SegmentDescriptor,
        data: bytes,
        *,
        skip_if_current: bool = True,
        chunk_size: int = DEFAULT_DATA_CHUNK_SIZE,
    ) -> SegmentVerifyResult | SegmentSetupResult:
        """Run the standard setup, erase, write, end, and verify flow.

        Args:
            descriptor: Segment metadata and validation information.
            data: Complete segment data to write.
            skip_if_current: When true, return after setup if current flash
                already matches the descriptor.
            chunk_size: Maximum data bytes per transfer chunk.

        Returns:
            `SegmentSetupResult` when skipped, otherwise `SegmentVerifyResult`.

        Raises:
            RuntimeError: If final verification returns failure.
        """
        if chunk_size <= 0 or chunk_size > MAX_DATA_CHUNK_SIZE:
            raise ValueError(f"chunk_size must be 1..{MAX_DATA_CHUNK_SIZE}")
        if not self.baud_mode.ack_each_data_packet:
            raise RuntimeError(
                "program_segment() requires a baud mode with data-packet ACKs enabled"
            )
        data = bytes(data)
        if len(data) != descriptor.data_length:
            raise ValueError(
                f"data length {len(data)} does not match descriptor data_length "
                f"{descriptor.data_length}"
            )

        setup = self.setup_segment(descriptor)
        if setup.current_matches and skip_if_current:
            return setup

        self.begin_transfer(descriptor)
        for offset in range(0, len(data), chunk_size):
            self.send_data_packet(offset, data[offset : offset + chunk_size])
        self.end_transfer()
        verify = self.verify_segment_done(descriptor)
        if not verify.verified:
            raise RuntimeError("segment verification failed")
        return verify

    @staticmethod
    def build_data_packet(segment_offset: int, data: bytes) -> bytes:
        """Package one segment chunk in the loader's expected data layout.

        Args:
            segment_offset: Offset from the active segment base.
            data: Non-empty data chunk, at most `0x800` bytes.

        Returns:
            Chunk payload bytes ready to frame and transmit.
        """
        _validate_uint("segment_offset", segment_offset, 32)
        data = bytes(data)
        if not data:
            raise ValueError("data packet must not be empty")
        if len(data) > MAX_DATA_CHUNK_SIZE:
            raise ValueError(f"data packet must be at most {MAX_DATA_CHUNK_SIZE} bytes")
        return struct.pack("<II", segment_offset, len(data)) + data

    def _read_unlock_replies(self, timeout: float) -> None:
        """Read and validate the two raw unlock response bytes.

        Args:
            timeout: Timeout for each raw byte.

        Raises:
            RuntimeError: If either unlock response byte is unexpected.
        """
        with self.log_rx_window():
            # 0x16 means the ROM/loader accepted the raw unlock token and will
            # continue the mode-entry handshake. This byte is raw/unframed and
            # is not XORed, even when the caller used keyed unlock.
            unlock_ack = self._recv_exact(1, timeout)[0]
            if unlock_ack != VERB_UNLOCK_ACK:
                raise RuntimeError(
                    f"unexpected unlock ACK 0x{unlock_ack:02x}, "
                    f"expected 0x{VERB_UNLOCK_ACK:02x}"
                )

            # 0x06 is the final OK status from mode entry: the loader has
            # entered the caller-selected programming mode and is ready for
            # framed FLDM commands.
            mode_ok = self._recv_exact(1, timeout)[0]
            if mode_ok != VERB_OK:
                raise RuntimeError(
                    f"unexpected mode-change OK 0x{mode_ok:02x}, "
                    f"expected 0x{VERB_OK:02x}"
                )

    def _send_and_expect_ok(
        self,
        verb: int,
        payload: bytes = b"",
        *,
        timeout: float | None = None,
    ) -> FLDMFrame:
        """Send a command and validate an empty OK response.

        Args:
            verb: Command verb.
            payload: Command payload.
            timeout: Optional response timeout.

        Returns:
            The validated OK frame.
        """
        self.send_packet(verb, payload)
        return self._expect_ok(self._recv_command_frame(timeout=timeout))

    def _send_and_expect_reply_frame(
        self,
        verb: int,
        payload: bytes = b"",
        *,
        payload_len: int | None = None,
        timeout: float | None = None,
    ) -> FLDMFrame:
        """Send a command and validate its command-specific reply frame.

        Command-specific reply frames use the command verb plus one. Generic
        status frames such as OK, BUSY, and ERROR are handled by other helpers.

        Args:
            verb: Command verb.
            payload: Command payload.
            payload_len: Required response payload length when provided.
            timeout: Optional response timeout.

        Returns:
            The validated response frame.
        """
        self.send_packet(verb, payload)
        frame = self._recv_command_frame(timeout=timeout)
        self._expect_verb(frame, verb + 1)
        if payload_len is not None and len(frame.payload) != payload_len:
            raise RuntimeError(
                f"expected response payload length {payload_len}, got {len(frame.payload)}"
            )
        return frame

    def _recv_command_frame(self, timeout: float | None = None) -> FLDMFrame:
        """Receive one response frame and raise on firmware error frames.

        Args:
            timeout: Optional response timeout.

        Returns:
            The decoded non-error response frame.

        Raises:
            FLDMCommandError: If firmware returns response verb `0x15`.
        """
        frame = self.recv_frame(timeout=timeout)
        if frame.verb == VERB_ERROR:
            code = frame.payload[0] if frame.payload else 0
            raise FLDMCommandError(code, frame)
        return frame

    def _recv_until_not_busy(self, timeout: float | None = None) -> FLDMFrame:
        """Receive frames until the loader stops reporting BUSY.

        Args:
            timeout: Optional timeout for each frame.

        Returns:
            The first non-BUSY response frame.

        Raises:
            RuntimeError: If a BUSY response unexpectedly carries payload bytes.
        """
        while True:
            frame = self._recv_command_frame(timeout=timeout)
            if frame.verb != VERB_BUSY:
                return frame
            if frame.payload:
                raise RuntimeError("busy frame unexpectedly included payload")

    def _expect_ok(self, frame: FLDMFrame) -> FLDMFrame:
        """Validate that a response frame is an empty OK frame.

        Args:
            frame: Response frame to validate.

        Returns:
            The same response frame.
        """
        self._expect_verb(frame, VERB_OK)
        if frame.payload:
            raise RuntimeError(
                f"OK frame unexpectedly included {len(frame.payload)} payload bytes"
            )
        return frame

    @staticmethod
    def _expect_verb(frame: FLDMFrame, expected_verb: int) -> None:
        """Validate the response verb.

        Args:
            frame: Response frame to validate.
            expected_verb: Required response verb.

        Raises:
            RuntimeError: If the response verb differs.
        """
        if frame.verb != expected_verb:
            raise RuntimeError(
                f"unexpected response verb 0x{frame.verb:02x}, expected 0x{expected_verb:02x}"
            )


def run(
    port: str,
    baud: int,
    reply_timeout: float = 2.0,
    *,
    verbose: bool = False,
) -> None:
    """Run a minimal cleartext FLDM command smoke test."""
    with FLDMLoader(
        port,
        baud=baud,
        reply_timeout=reply_timeout,
        verbose=verbose,
    ) as fldm:
        print("# Starting unencrypted program mode.")
        fldm.unlock()

        print("# Send start-program command.")
        print(fldm.start_programming())
        time.sleep(2)  # Show the flashing PROGRAM on display.

        # print("# Select updater target profile.")
        # print(fldm.select_target_unit())

        print("# Start timed programming session.")
        print(fldm.start_timed_session())

        print("# Query target profile.")
        print(fldm.query_target_profile())

        print("# Select baud/transfer mode.")
        print(fldm.set_baud_transfer_mode())

        # TODO: Setup firmware segments.
        # TODO: Send the firmware segments.

        print("# Send complete command.")
        print(fldm.complete())


def main() -> None:
    """Parse command-line arguments and run the smoke test."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="/dev/ttyACM0")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--reply-timeout", type=float, default=2.0)
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="print raw TX/RX bytes"
    )
    args = parser.parse_args()

    run(args.port, args.baud, args.reply_timeout, verbose=args.verbose)


def _stdout_supports_ansi_color() -> bool:
    """Return true when stdout should receive ANSI color codes."""
    if os.environ.get("NO_COLOR") is not None:
        return False
    if not sys.stdout.isatty():
        return False
    if os.name != "nt":
        return True
    if os.environ.get("WT_SESSION") or os.environ.get("ANSICON"):
        return True
    if os.environ.get("ConEmuANSI", "").upper() == "ON":
        return True
    term = os.environ.get("TERM", "")
    return bool(term and term.lower() != "dumb")


if __name__ == "__main__":
    main()
