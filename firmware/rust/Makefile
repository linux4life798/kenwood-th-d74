CROSS_COMPILE ?= arm-none-eabi-
CC := $(CROSS_COMPILE)gcc
OBJCOPY := $(CROSS_COMPILE)objcopy
RUSTC ?= rustc

TARGET := firmware-rust
LDSCRIPT := l138-ddr.ld
OBJS := header.o startup.o main.o rom_functions.o

CFLAGS := -mcpu=arm926ej-s -marm
CFLAGS += -ffreestanding -fno-builtin -fno-unwind-tables -fno-asynchronous-unwind-tables
CFLAGS += -Wall -Wextra -O0

ASFLAGS := $(CFLAGS)
RUSTFLAGS := --target armv5te-none-eabi -C panic=abort -C opt-level=0 --emit=obj
LDFLAGS := -nostdlib -T $(LDSCRIPT) -Wl,-Map,$(TARGET).map

all: $(TARGET).elf $(TARGET).bin

$(TARGET).elf $(TARGET).map: $(OBJS) $(LDSCRIPT)
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $(OBJS)

$(TARGET).bin: $(TARGET).elf
	$(OBJCOPY) -O binary $< $@

header.o: ../header.S
	$(CC) $(ASFLAGS) -c -o $@ $<

startup.o: ../startup.S
	$(CC) $(ASFLAGS) -c -o $@ $<

rom_functions.o: ../rom_functions.S
	$(CC) $(ASFLAGS) -c -o $@ $<

main.o: main.rs
	$(RUSTC) $(RUSTFLAGS) -o $@ $<

clean:
	$(RM) $(OBJS) $(TARGET).elf $(TARGET).bin $(TARGET).map

.PHONY: all clean
