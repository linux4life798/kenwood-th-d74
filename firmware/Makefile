CROSS_COMPILE ?= arm-none-eabi-
CC := $(CROSS_COMPILE)gcc
OBJCOPY := $(CROSS_COMPILE)objcopy

TARGET := firmware
LDSCRIPT := l138-ddr.ld
OBJS := header.o startup.o main.o

CFLAGS := -mcpu=arm926ej-s -marm -ffreestanding -fno-builtin -fno-unwind-tables -fno-asynchronous-unwind-tables -Wall -Wextra
# CFLAGS += -Os
CFLAGS += -O0
LDFLAGS := -nostdlib -T $(LDSCRIPT) -Wl,-Map,$(TARGET).map

all: $(TARGET).elf $(TARGET).bin

$(TARGET).elf: $(OBJS) $(LDSCRIPT)
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $(OBJS)

$(TARGET).bin: $(TARGET).elf
	$(OBJCOPY) -O binary $< $@

%.o: %.c
	$(CC) $(CFLAGS) -c -o $@ $<

%.o: %.S
	$(CC) $(CFLAGS) -c -o $@ $<

clean:
	rm -f $(OBJS) $(TARGET).elf $(TARGET).bin $(TARGET).map

.PHONY: all clean
