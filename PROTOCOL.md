# TH-D74 FLDM Serial Protocol

All byte values are hex unless stated otherwise.

## 1) Unlock the Loader

Before framed commands, unlock the loader with one of these raw byte sequences:

```text
Cleartext: 46 50 52 4f 4d 4f 44              "FPROMOD"
Encrypted: xx xx 54 68 64 37 34 74 77 yy zz  "..Thd74tw.."
```

* **Cleartext** unlock checks the first seven bytes for `FPROMOD`; send exactly
  those seven bytes. Communication after this unlock is not obfuscated,
  effectively XOR key `0x00`.
* **Encrypted** unlock must be 11 bytes. The firmware checks bytes `2..8` for
  `Thd74tw`; the two `xx` bytes are ignored. `yy` and `zz` are byte values used
  to derive the XOR key: `((-(yy + zz)) ^ 0xb8) & 0xff`. If that result is
  `0x00`, the firmware uses `0x74`.

On accepted unlock, the firmware emits two separate raw one-byte replies:

```text
16  unlock ACK: the magic sequence was accepted
06  mode change OK: the loader entered its programming control mode
```

*These bytes are emitted at different times and indicate different things,
although they should always be in order.*

These replies are unframed and are not XORed. Rejected unlock does not appear to
send a serial error byte.

## 2) Framed Wire Format

After unlock, framed messages in both directions use the following pattern:

```text
SYNC SYNC HH LL LL LL LL VV PP... CC
ab   ab   00 01 00 00 00 31       32
```

*No trailing CR/LF.*

Fields:

```text
SYNC SYNC  fixed sync bytes: ab ab
HH         header/reserved byte, normally 00, but this is unchecked in firmware
LL..LL     little-endian body length = 1 + payload length
VV         one-byte command or response verb
PP...      optional payload bytes
CC         checksum: sum(HH, LL..LL, VV, PP...) & 0xff
```

The checksum excludes `SYNC SYNC` and excludes `CC`. Firmware-generated frames
always use `HH = 00`, but in the opposite direction `HH` can be anything.
Encrypted framed traffic is XORed byte-for-byte with the key in the unlocking
procedure, including `ab ab`. Cleartext traffic is not XORed.
