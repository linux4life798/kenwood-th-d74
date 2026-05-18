CROSS_COMPILE ?= arm-none-eabi-
CC := $(CROSS_COMPILE)gcc
OBJCOPY := $(CROSS_COMPILE)objcopy

TARGET = firmware
LDSCRIPT = $(LIB_DIR)/l138-ddr.ld
OBJS = $(addprefix $(LIB_DIR)/, $(lib-objs-y)) main.o

CFLAGS += -mcpu=arm926ej-s -marm
CFLAGS += -ffreestanding -fno-builtin -fno-unwind-tables -fno-asynchronous-unwind-tables
CFLAGS += -Wall -Wextra
# CFLAGS += -Os
CFLAGS += -g
CFLAGS += -O0

ASFLAGS += $(CFLAGS)

LDFLAGS = -nostdlib -T $(LDSCRIPT) -Wl,-Map,$(TARGET).map

LIB_DIR = ../lib
CFLAGS += -I$(LIB_DIR)
include $(LIB_DIR)/build.mk

all: $(TARGET).elf $(TARGET).bin

$(TARGET).elf $(TARGET).map: $(OBJS) $(LDSCRIPT)
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $(OBJS)

$(TARGET).bin: $(TARGET).elf
	$(OBJCOPY) -O binary $< $@

flash: $(TARGET).bin
	uv run openwood $(TARGET).bin

clean:
	$(RM) $(OBJS) $(TARGET).elf $(TARGET).bin $(TARGET).map

.PHONY: all clean flash
