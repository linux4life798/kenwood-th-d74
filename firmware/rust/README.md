# Rust firmware example

Minimal bare-metal Rust example mirroring `firmware/main.c`.

## Files

- `main.rs`: `no_std`/`no_main` Rust entrypoint.
- `Makefile`: builds a firmware ELF and BIN using `rustc` + `arm-none-eabi-gcc`.
- `l138-ddr.ld`: linker script matching the base firmware memory layout.

## Build

```bash
make -C firmware/rust
```

Build output:

- `firmware-rust.elf`
- `firmware-rust.bin`

This uses the existing assembly support files from `firmware/` (`header.S`,
`startup.S`, and `rom_functions.S`) and links them with the Rust `main.rs`.
