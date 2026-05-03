#!/usr/bin/env python3
from __future__ import annotations
import argparse, time
from types import TracebackType
import serial
from dataclasses import dataclass

SYNC = b"\xab\xab"
MAGIC = b"FPROMOD"
MAGIC_UNLOCK_ACK = b"\x16"
MAGIC_MODE_OK = b"\x06"
MAGIC_REPLY = MAGIC_UNLOCK_ACK + MAGIC_MODE_OK


def _xor(data: bytes, key: int) -> bytes:
    return data if key == 0 else bytes(b ^ key for b in data)


@dataclass(frozen=True, slots=True)
class FldmFrame:
    verb: int
    payload: bytes = b""
    header: int = 0
    """
    header: this is not used in firmware, but it must be included in checksum calculation
    """

    def __post_init__(self) -> None:
        if not 0 <= self.header <= 0xFF:
            raise ValueError("header must fit in one byte")
        if not 0 <= self.verb <= 0xFF:
            raise ValueError("verb must fit in one byte")
        object.__setattr__(self, "payload", bytes(self.payload))

    @property
    def body_len(self) -> int:
        return 1 + len(self.payload)

    @property
    def checksum(self) -> int:
        return sum(self._body_without_checksum()) & 0xFF

    def _body_without_checksum(self) -> bytes:
        return (
            bytes([self.header])
            + self.body_len.to_bytes(4, "little")
            + bytes([self.verb])
            + self.payload
        )

    def to_bytes(self, *, xor_key: int = 0) -> bytes:
        if not 0 <= xor_key <= 0xFF:
            raise ValueError("xor_key must fit in one byte")

        frame = SYNC + self._body_without_checksum() + bytes([self.checksum])
        return _xor(frame, xor_key)


class Fldm:
    def __init__(
        self,
        port: str,
        *,
        baud: int = 115200,
        reply_timeout: float = 2.0,
        xor_key: int = 0,
        max_payload: int = 4096,
    ) -> None:
        if not 0 <= xor_key <= 0xFF:
            raise ValueError("xor_key must fit in one byte")

        self.reply_timeout = reply_timeout
        self.xor_key = xor_key
        self.max_payload = max_payload
        self.ser: serial.Serial = serial.Serial(
            port=port,
            baudrate=baud,
            bytesize=8,
            parity="N",
            stopbits=1,
            timeout=0.25,
            write_timeout=1,
        )
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()

    def __enter__(self) -> Fldm:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.Close()

    def Close(self) -> None:
        if self.ser and self.ser.is_open:
            self.ser.close()

    def SendRaw(self, data: bytes) -> None:
        print(f"TX {data.hex(' ')}")
        self.ser.write(data)
        self.ser.flush()

    def RecvRaw(self, timeout: float | None = None) -> bytes | None:
        start = time.monotonic()
        end = start + (self.reply_timeout if timeout is None else timeout)
        out = bytearray()
        while time.monotonic() < end:
            chunk = self.ser.read_all()
            if chunk:
                now = time.monotonic()
                print(f"RX +{now - start:.3f}s {chunk.hex(' ')}")
                out.extend(chunk)
            else:
                time.sleep(0.01)
        return bytes(out) if out else None

    def SendFrame(self, frame: FldmFrame) -> None:
        self.SendRaw(frame.to_bytes(xor_key=self.xor_key))

    def RecvFrame(self, timeout: float | None = None) -> FldmFrame:
        if not 0 <= self.xor_key <= 0xFF:
            raise ValueError("xor_key must fit in one byte")

        timeout = self.reply_timeout if timeout is None else timeout
        wire_sync = _xor(SYNC, self.xor_key)

        # Find sync, XORed if encrypted mode is active.
        # This will ignore any remnant bytes that are not sync words.
        window = bytearray()
        while True:
            window = (window + self._RecvExact(1, timeout))[-2:]
            if bytes(window) == wire_sync:
                break

        # Header after sync: header:u8 + body_len:u32le + verb:u8.
        raw_head = self._RecvExact(6, timeout)
        head = _xor(raw_head, self.xor_key)

        header = head[0]
        body_len = int.from_bytes(head[1:5], "little")
        if body_len < 1:
            raise ValueError(f"invalid body length {body_len}")
        if body_len > self.max_payload + 1:
            raise ValueError(f"unreasonable body length {body_len}")

        # Remaining bytes are payload plus checksum.
        tail = _xor(self._RecvExact(body_len, timeout), self.xor_key)
        payload = tail[:-1]
        checksum = tail[-1]

        expected = sum(head + payload) & 0xFF
        if checksum != expected:
            raise ValueError(
                f"bad checksum: got 0x{checksum:02x}, expected 0x{expected:02x}"
            )

        verb = head[5]
        return FldmFrame(verb=verb, payload=payload, header=header)

    def _RecvExact(self, n: int, timeout: float) -> bytes:
        out = bytearray()
        deadline = time.monotonic() + timeout
        while len(out) < n:
            left = deadline - time.monotonic()
            if left <= 0:
                raise TimeoutError("timeout reading frame")
            self.ser.timeout = min(left, 0.25)
            chunk = self.ser.read(n - len(out))
            if chunk:
                out.extend(chunk)
        return bytes(out)

    def SendPacket(self, verb: int, payload: bytes = b"", *, header: int = 0) -> None:
        self.SendFrame(FldmFrame(verb=verb, payload=payload, header=header))

    def Unlock(self, timeout: float = 1.0) -> None:
        self.SendRaw(MAGIC)
        unlock_ack = self._RecvExact(1, timeout)
        if unlock_ack != MAGIC_UNLOCK_ACK:
            raise RuntimeError(
                f"unexpected unlock ACK {unlock_ack.hex(' ')}, expected {MAGIC_UNLOCK_ACK.hex(' ')}"
            )

        mode_ok = self._RecvExact(1, timeout)
        if mode_ok != MAGIC_MODE_OK:
            raise RuntimeError(
                f"unexpected mode-change OK {mode_ok.hex(' ')}, expected {MAGIC_MODE_OK.hex(' ')}"
            )

    def StartProgramming(self) -> None:
        # The one-byte payload must be zero; any other value errors in firmware.
        self.SendPacket(0x30, b"\x00")

    def StartSession(self) -> None:
        # Starts the firmware watchdog timer; later commands feed it.
        self.SendPacket(0xA0)

    def QueryStatus(self) -> FldmFrame:
        self.SendPacket(0x31)
        return self.RecvFrame()

    def Complete(self, code: bytes = b"\x00\x00") -> None:
        if len(code) != 2:
            raise ValueError("complete code must be two bytes")
        self.SendPacket(0x50, code)


def run(port: str, baud: int, reply_timeout: float = 2.0):
    with Fldm(port, baud=baud, reply_timeout=reply_timeout) as f:
        # Start unencrypted program mode.
        print("# Starting unencrypted program mode.")
        f.Unlock()

        time.sleep(0.250)

        print("# Send start-program command.")
        f.StartProgramming()
        print(f.RecvFrame())

        time.sleep(0.250)

        print("# Send token/session command.")
        f.StartSession()
        print(f.RecvFrame())

        time.sleep(0.250)
        print("# Send status query command.")
        f.SendPacket(0x31)
        print(f.RecvFrame())

        time.sleep(0.250)
        print("# Send complete command.")
        f.Complete()
        print(f.RecvFrame())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/ttyACM0")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--reply-timeout", type=float, default=2.0)
    a = ap.parse_args()

    run(a.port, a.baud, a.reply_timeout)


if __name__ == "__main__":
    main()
