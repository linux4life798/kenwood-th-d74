# TH-D74 FLDM Serial Protocol

This document describes the firmware update protocol implemented by the TH-D74
firmware FLDM loader, named `EX-4420 FldmLoader`. It is intentionally written
as a host-side implementation guide.

*All byte values are hex unless stated otherwise. Multi-byte integer fields are
little-endian unless stated otherwise.*

Keywords:
* `EX-4409 Boot Program`
* `EX-4420 FldmLoader`
* `EX-4409 Firmware`

## 1) Unlock the Loader

Before framed commands, unlock the loader with the following raw byte sequences:

```text
Cleartext: 46 50 52 4f 4d 4f 44              "FPROMOD"
Encrypted: xx xx 54 68 64 37 34 74 77 yy zz  "..Thd74tw.."
```

* **Cleartext** unlock checks the first seven bytes for `FPROMOD`; send exactly
  those seven bytes. Communication after this unlock is not obfuscated,
  effectively XOR key `00`.
* **Encrypted** unlock must be 11 bytes. The firmware checks bytes `2..8` for
  `Thd74tw`; the two `xx` bytes are ignored. `yy` and `zz` are byte values used
  to derive the XOR key as follows:

  ```python
  xor_key = ((-(yy + zz)) ^ 0xb8) & 0xff
  if xor_key == 0:
      xor_key = 0x74
  ```

On accepted unlock, the firmware emits two separate raw one-byte replies:

```text
16  unlock ACK: the magic sequence was accepted
06  mode change OK: the loader entered its programming control mode
```

*These bytes are emitted at different times and indicate different things,
although they should always be in order.*

These replies are unframed and are not XORed. Rejected unlock does not appear to
send a serial error byte.

## 2) Framed Commands

* After unlock, **all outgoing messages** and **replies with payloads** adhere
  to the following framing pattern:

  ```text
  SYNC SYNC HH LL LL LL LL VV PP... CC
  ab   ab   00 01 00 00 00 31       32
  ```

  *No trailing CR/LF.*

  The fields are as follows:

  ```text
  SYNC SYNC  fixed sync bytes ab ab
  HH         header/reserved byte; firmware transmits 00
             receive does not validate it
  LL..LL     little-endian body length = 1 + payload length
  VV         one-byte command or response verb
  PP...      optional payload bytes
  CC         checksum = sum(HH, LL..LL, VV, PP...) & 0xff
  ```

  The checksum excludes `SYNC SYNC` and excludes `CC`. Firmware-generated frames
  always use `HH = 00`, but in the opposite direction `HH` can be anything.
  Encrypted framed traffic is XORed byte-for-byte with the key in the unlocking
  procedure, including `ab ab`. Cleartext traffic is not XORed.
* Commands that return payloads will use the same framing, but the returned verb
  (VV) will be the outgoing verb number plus one.
* Simple commands will only receive a one- or two-byte status-style response,
  without framing:

  ```text
  06     OK/ACK
  11     BUSY
  15 xx  ERROR/NAK with one-byte error code
  ```

  Known `15 xx` error codes:

  ```text
  15 01  unsupported command
  15 02  invalid start-program payload
  15 03  data packet/write rejected
  15 04  another command is already active
  ```

  Command response table:

  | Verb | Function | Params | Expected response |
  | --- | --- | --- | --- |
  | `30` | Enter programming state | `00` | `06` |
  | `31` | Query target profile | empty | `32` + 17-byte payload |
  | `33` | Select transfer mode | `mode:u8`, `ack:u8` | `06` |
  | `40` | Set up segment | `SegmentDescriptor` | `41` + result |
  | `42` | Begin segment transfer | empty | `11` until `06` |
  | `43` | Send data chunk | `offset:u32`, data | if ACKs: `06` |
  | `44` | End segment transfer | empty | `06` |
  | `45` | Verify segment | empty | `46` + result |
  | `50` | Complete update | `code:u32` | `06` |
  | `a0` | Start timed session | empty | `06` |
  | `a3` | Select target unit | `target_unit:u32` | unsupported |

  Command/Verb `40` uses these `SegmentDescriptor` params:

  | Type | Field | Tag |
  | --- | --- | --- |
  | `u32` | `flash_start_addr` | `$SA` |
  | `u32` | `data_length` | `$DL` |
  | `u32` | `erase_length` | `$EL` |
  | `u32` | `padding` | `0` |
  | `u64` | `target_type_mask` | `$TT` |
  | `u32` | `erase_wait_seconds` | `$ET` |
  | `u16` | `expected_before_checksum` | `$CB` |
  | `u16` | `expected_after_checksum` | `$CA` |
  | `u32` | `checksum_start_offset` | `$CS` |
  | `u32` | `checksum_length` | `$CL` |
  | `u32` | `checksum_wait_seconds` | `$CT` |
  | `u32` | `version_start_offset` | `$VS` |
  | `u32` | `version_length` | `$VL` |
  | `u8[]` | `version/check bytes` | `$VA` |
