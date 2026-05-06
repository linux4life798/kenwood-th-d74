# TH-D74 Flash and DDR Memory Layout

This document describes the hardware and software memory model used by the
TH-D74 bootloader, FLDM loader, and main firmware. Addresses are absolute
CPU-visible addresses.

The first 4 bytes of NOR flash contains TI OMAP boot configuration word.
In this case that value is `0x00000011`, which tells the TI bootloader to do a
`Direct NOR Boot` using full 16-bit word EMIFA accesses.
This means that the bootloader will branch directly to `0x60000004` (after
config word), in the flash backed region.

## Hardware Memory Map

The firmware uses these CPU-visible memory ranges:


| Region                   | Address range            | Length                | Notes                                                                       |
| ------------------------ | ------------------------ | --------------------- | --------------------------------------------------------------------------- |
| NOR flash address window | `0x60000000..0x62000000` | `32 MiB / 0x02000000` | 32 MiB S29GL256S flash image range.                                         |
| DDR                      | `0xc0000000..0xc4000000` | `64 MiB / 0x04000000` | 64 MiB DDR working RAM.                                                     |
| ARM local RAM            | `0xffff0000..0xffff2000` | `8 KiB / 0x2000`      | Boot scratch/local RAM area. Used during early bootloader as general stack. |


## Boot Copy Map

These copies are explicit in the bootloader code. They are the strongest
anchors for separating bootloader, loader, and app images.

The initial bootloader is the decision-maker. It executes in place from flash,
initializes the board and DDR, then copies exactly one runtime image to
`0xc0000000`: the FLDM loader when loader-entry conditions are true, otherwise
the main firmware image. The FLDM loader and main firmware are therefore
alternative DDR occupants, not simultaneous regions.

The initial bootloader loads the FLDM Loader code when any early boot predicate says
recovery is needed. This occurs when PTT + 1 keys are active, or a mismatch
between the flash FINAL_ZZZ marker at `0x60200040` and the compiled expected
marker. Otherwise, the bootloader continues to boot the main firmware.


| Component                  | Flash source range       | DDR/runtime destination  | Length                        | Entry                                                   | Meaning                                                |
| -------------------------- | ------------------------ | ------------------------ | ----------------------------- | ------------------------------------------------------- | ------------------------------------------------------ |
| Initial bootloader         | `0x60000000..0x60020000` | executes in place        | `128 KiB / 0x20000` byte slot | `0x60000000` boot config word; ARM code at `0x60000004` | Boot-critical first-stage loader and handoff selector. |
| FLDM loader                | `0x60020000..0x60060000` | `0xc0000000..0xc0040000` | `256 KiB / 0x40000` bytes     | `0xc0000000` vector table                               | Recovery/programming loader.                           |
| Main firmware copied image | `0x60200000..0x60500000` | `0xc0000000..0xc0300000` | `3 MiB / 0x300000` bytes      | `0xc0000000` vector table                               | Normal application image.                              |
