#!/usr/bin/env python3
from __future__ import annotations
import argparse, re, time
from pathlib import Path
import serial
# import dnfile
from dataclasses import dataclass

SYNC = b"\xab\xab"
MAGIC = b"FPROMOD"
MAGIC_REPLY = b"\x16\x06"
HEX_RE = re.compile(r"^[0-9A-Fa-f]+$")

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

def send(ser: serial.Serial, data: bytes):
    print(f"TX {data.hex(' ')}")
    ser.write(data)
    ser.flush()

def send_frame(ser: serial.Serial, frame: FldmFrame):
    send(ser, frame.to_bytes())

def _recv_exact(ser: serial.Serial, n: int, timeout: float) -> bytes:
    out = bytearray()
    deadline = time.monotonic() + timeout
    while len(out) < n:
        left = deadline - time.monotonic()
        if left <= 0:
            raise TimeoutError("timeout reading frame")
        ser.timeout = min(left, 0.25)
        chunk = ser.read(n - len(out))
        if chunk:
            out.extend(chunk)
    return bytes(out)

def recv_frame(
    ser: serial.Serial,
    timeout: float = 2.0,
    *,
    xor_key: int = 0,
    max_payload: int = 4096,
) -> FldmFrame:
    if not 0 <= xor_key <= 0xFF:
        raise ValueError("xor_key must fit in one byte")

    wire_sync = _xor(SYNC, xor_key)

    # Find sync, XORed if encrypted mode is active.
    # This will ignore any remnant bytes that are not sync words.
    window = bytearray()
    while True:
        window = (window + _recv_exact(ser, 1, timeout))[-2:]
        if bytes(window) == wire_sync:
            break

    # Header after sync: header:u8 + body_len:u32le + verb:u8.
    raw_head = _recv_exact(ser, 6, timeout)
    head = _xor(raw_head, xor_key)

    header = head[0]
    body_len = int.from_bytes(head[1:5], "little")
    if body_len < 1:
        raise ValueError(f"invalid body length {body_len}")
    if body_len > max_payload + 1:
        raise ValueError(f"unreasonable body length {body_len}")

    # Remaining bytes are payload plus checksum.
    tail = _xor(_recv_exact(ser, body_len, timeout), xor_key)
    payload = tail[:-1]
    checksum = tail[-1]

    expected = sum(head + payload) & 0xFF
    if checksum != expected:
        raise ValueError(f"bad checksum: got 0x{checksum:02x}, expected 0x{expected:02x}")

    verb = head[5]
    return FldmFrame(verb=verb, payload=payload, header=header)


def recv_all(ser: serial.Serial, timeout: float) -> bytes | None:
    start = time.monotonic()
    end = start + timeout
    out = bytearray()
    while time.monotonic() < end:
        chunk = ser.read_all()
        if chunk:
            now = time.monotonic()
            print(f"RX +{now - start:.3f}s {chunk.hex(' ')}")
            out.extend(chunk)
        else:
            time.sleep(0.01)
    return bytes(out) if out else None

# def extract_script(exe: Path) -> list[str]:
#     pe = dnfile.dnPE(str(exe))
#     for r in pe.net.resources:
#         if str(r.name).endswith("TH-D74_Firm_E.txt"):
#             return list(decode_lines(r.data))
#     raise RuntimeError("resource TH-D74_Firm_E.txt not found")

def run(port: str, baud: int, reply_timeout: float = 2.0):
    ser: serial.Serial = serial.Serial(port=port, baudrate=baud, bytesize=8, parity="N", stopbits=1, timeout=0.25, write_timeout=1)
    ser.reset_input_buffer()
    ser.reset_output_buffer()

    # Start unencrypted program mode.
    print("# Starting unencrypted program mode.")
    send(ser, MAGIC)
    # reply = ser.read_all()
    reply = recv_all(ser, 1) # takes slightly longer at about 0.1s
    print(f"RX {reply.hex(' ') if reply else None}")

    time.sleep(0.250)

    print("# Send start-program command.")
    # The 1 byte payload must be 0, any other value will trigger an error in firmware.
    start_program = FldmFrame(verb=0x30, payload=b"\x00")
    send_frame(ser, start_program)
    reply = recv_frame(ser, reply_timeout)
    # maybe_recv_reply(ser, True, reply_timeout)
    reply = recv_all(ser, 0.250)
    print(f"RX {reply.hex(' ') if reply else None}")

    time.sleep(0.250)

    # This starts a watchdog timer in firmware for 5 seconds.
    # It feeds the watchdog on each subsequent programmer command, but if 5
    # seconds is reach, it will error out the programming and show "Error\nData Error!!"
    print("# Send token/session command.")
    token = FldmFrame(verb=0xA0)
    send_frame(ser, token)
    # maybe_recv_reply(ser, True, reply_timeout)
    reply = recv_all(ser, 0.250)
    print(f"RX {reply.hex(' ') if reply else None}")

    time.sleep(0.250)
    print("# Send status query command.")
    status_query = FldmFrame(verb=0x31)
    send_frame(ser, status_query)
    # maybe_recv_reply(ser, True, reply_timeout)
    reply = recv_all(ser, 0.250)
    print(f"RX {reply.hex(' ') if reply else None}")

    time.sleep(0.250)
    print("# Send complete command.")
    # This 2 byte completion code payload is not used in firmware and can be anything.
    # complete = make_frame(0x50, b'\xB6\xCD')
    complete = FldmFrame(verb=0x50, payload=b'\x00\x00')
    send_frame(ser, complete)
    reply = recv_all(ser, 0.250)
    print(f"RX {reply.hex(' ') if reply else None}")

    if ser:
        ser.close()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/ttyACM0")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--reply-timeout", type=float, default=2.0)
    a = ap.parse_args()

    run(a.port, a.baud, a.reply_timeout)


if __name__ == "__main__":
    main()
