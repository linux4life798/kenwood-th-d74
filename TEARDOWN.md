# Hardware Connected to the OMAP L138

The main CPU is a TI OMAP L138, specifically the `OMAPL138EZCEA3`.
* This is the slower 375MHz variant, not the 456MHz.

## Oscillations, Clocks, and PLLs

* Main CPU is connected to `19.2 MHz TCXO` and a `32.768 kHz crystal` for RTC.
* ~Service manual says the core clock rate of `139.2 MHz` for the ARM and DSP cores.~
* The main cores run at 278.4 MHz and peripherals run at 92.8 MHz (like timers).

## Memory and Flash

* `Winbond W949D6KBHX5I` - 512 Mbit Mobile LPDDR SDRAM
   - 64MiB
   - Mapped to 0xC000_0000 - 0xC400_0000
* `Spansion GL256S10DHI02` - S29GL256S 256 Mbit GL-S parallel NOR flash.
   - 32 MiB
   - Connected to EMFIA CS2 and available directly at 0x6000_0000 - 0x6200_0000.

## Peripherals

* The display seems to be similar to a [`Himax HX8347-D/T`] color TFT controller,
  based on protocol.
  - The resolution is `240 x 180`.
  - It is connected via a 16-bit 8080/I80-style parallel bus.
  - Connected to EMFIA CS4 and available directly at 0x6400_0000 - 0x6600_0000.
  - `0x6400_0000` - 16bit command / index selector.
  - `0x6500_0000` - 16bit parameters
  - https://github.com/torvalds/linux/blob/master/drivers/staging/fbtft/fb_hx8347d.c
  - https://github.com/STMicroelectronics/stm32-hx8347d
  - https://github.com/moononournation/Arduino_GFX/wiki/Display-Class

* The Keyscan / IO-Expander module seems to be an [`LM8325-1`].
  - I2C connected module.
  - Interfaces with the buttons and keypad.
  - Controls the display backlight.


[`Himax HX8347-D/T`]: https://www.displayfuture.com/Display/datasheet/controller/HX8347-D.pdf
[`LM8325-1`]: https://www.ti.com/product/LM8325-1
