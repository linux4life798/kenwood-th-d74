CROSS_COMPILE ?= arm-none-eabi-
CC := $(CROSS_COMPILE)gcc
LD := $(CROSS_COMPILE)ld
OBJCOPY := $(CROSS_COMPILE)objcopy

STARTERWARE := starterware
BUILD_DIR := build
OBJ_DIR := $(BUILD_DIR)/obj

TARGET := usb_dev_serial
OUT := $(BUILD_DIR)/$(TARGET).out
BIN := $(BUILD_DIR)/$(TARGET).bin
MAP := $(BUILD_DIR)/$(TARGET).map
LDSCRIPT := $(STARTERWARE)/build/armv5/gcc/omapl138/lcdkOMAPL138/usb_dev_serial/usb_dev_serial.lds

LIB_C ?= $(dir $(shell $(CC) -print-file-name=libc.a))
LIB_GCC ?= $(dir $(shell $(CC) -print-file-name=libgcc.a))

CPUFLAGS ?=
CPPFLAGS := -Dgcc -Domapl138 -DlcdkOMAPL138
CPPFLAGS += -I$(STARTERWARE)/include
CPPFLAGS += -I$(STARTERWARE)/include/hw
CPPFLAGS += -I$(STARTERWARE)/include/armv5
CPPFLAGS += -I$(STARTERWARE)/include/armv5/omapl138
CPPFLAGS += -I$(STARTERWARE)/usblib/include

USB_FORCE_FULL_SPEED ?= 1
ifeq ($(USB_FORCE_FULL_SPEED),1)
CPPFLAGS += -DUSB_MODE_HS_DISABLE
endif

CFLAGS := $(CPUFLAGS) -fdata-sections -ffunction-sections -Wall
# CFLAGS += -g -O2
CFLAGS += -g -O0
ASFLAGS := $(CFLAGS)
DEPFLAGS := -MMD -MP
LDFLAGS := -e Entry -u Entry -u __aeabi_uidiv -u __aeabi_idiv --gc-sections

SRCS := \
	drivers/psc.c \
	drivers/timer.c \
	drivers/uart.c \
	drivers/usb.c \
	drivers/usbphyGS60.c \
	examples/lcdkOMAPL138/usb_dev_serial/Usb_dev_serial.c \
	examples/lcdkOMAPL138/usb_dev_serial/usb_serial_structs.c \
	platform/lcdkOMAPL138/syscfg.c \
	platform/lcdkOMAPL138/sysdelay.c \
	platform/lcdkOMAPL138/uart.c \
	platform/lcdkOMAPL138/usb.c \
	system_config/armv5/gcc/cpu.c \
	system_config/armv5/gcc/init.S \
	system_config/armv5/omapl138/gcc/exceptionhandler.S \
	system_config/armv5/omapl138/interrupt.c \
	system_config/armv5/omapl138/startup.c \
	usblib/device/usbdcdc.c \
	usblib/device/usbdcdesc.c \
	usblib/device/usbdconfig.c \
	usblib/device/usbdenum.c \
	usblib/device/usbdhandler.c \
	usblib/usbbuffer.c \
	usblib/usbdesc.c \
	usblib/usbringbuf.c \
	usblib/usbtick.c \
	utils/delay.c

OBJS := $(patsubst %.c,$(OBJ_DIR)/%.o,$(filter %.c,$(SRCS)))
OBJS += $(patsubst %.S,$(OBJ_DIR)/%.o,$(filter %.S,$(SRCS)))
DEPS := $(OBJS:.o=.d)

.PHONY: all clean flash

all: $(OUT) $(BIN)

$(BIN): $(OUT)
	$(OBJCOPY) -O binary $< $@

$(OUT): $(OBJS) $(LDSCRIPT)
	@mkdir -p $(dir $@)
	$(LD) $(LDFLAGS) -L$(LIB_C) -L$(LIB_GCC) -o $@ -Map $(MAP) $(OBJS) -T $(LDSCRIPT) -lc -lgcc -lc -lgcc

$(OBJ_DIR)/usblib/%.o: CPPFLAGS += -DDMA_MODE
$(OBJ_DIR)/%.o: $(STARTERWARE)/%.c
	@mkdir -p $(dir $@)
	$(CC) $(CPPFLAGS) $(CFLAGS) $(DEPFLAGS) -c $< -o $@

$(OBJ_DIR)/%.o: $(STARTERWARE)/%.S
	@mkdir -p $(dir $@)
	$(CC) $(CPPFLAGS) $(ASFLAGS) $(DEPFLAGS) -x assembler-with-cpp -c $< -o $@

flash: $(BIN)
	uv run openwood $(BIN)

clean:
	$(RM) -r $(BUILD_DIR)

-include $(DEPS)
