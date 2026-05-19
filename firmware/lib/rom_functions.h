#ifndef ROM_FUNCTIONS_H
#define ROM_FUNCTIONS_H

/**
 * @file rom_functions.h
 *
 * ROM functions are callable entry points in the XIP 0x60000000 early
 * bootloader code section. These declarations let replacement firmware call
 * those existing bootloader routines directly.
 */

#include <stdint.h>

typedef struct {
    uint16_t *pixels;
    uint16_t width;
    uint16_t height;
    uint32_t pixel_offset;
    uint8_t flags;
    uint8_t reserved0;
    uint8_t reserved1;
    uint8_t reserved2;
} LcdBlitFrame;

typedef struct {
    uint16_t left;
    uint16_t top;
    uint16_t width;
    uint16_t height;
} LcdWindowRect;

/**
 * ROM panic display path: reinitializes the display and shows one text line.
 *
 * Calling this repeatedly will redraw the display, but it will also
 * cause a full initialization of the display each time.
 */
void PanicDisplayRenderText(char *text);

/**
 * ROM panic display path: reinitializes the display and shows Init Error [n].
 *
 * Calling this repeatedly will redraw the display, but it will also
 * cause a full initialization of the display each time.
 */
void PanicDisplayInitErrorNumber(uint32_t error_number);

/**
 * Stops a ROM timer. Always call as TimerStop(3, 0) for timer3.
 */
void TimerStop(uint32_t timer_index, int32_t timer_half);

/**
 * Reads a ROM timer counter. Always call as TimerCounterRead(3) for timer3.
 */
uint64_t TimerCounterRead(uint32_t timer_index);

/**
 * Busy-waits using timer3 ticks. Assumes timer3 is already running.
 */
void TimerDelayTicks(uint32_t ticks);

/**
 * Busy-waits using timer3. Assumes timer3 is already running.
 */
void TimerDelayMilliseconds(uint32_t milliseconds);

/**
 * Checks the IC730 key-scanner FIFO for the boot ROM's programming-mode key.
 *
 * Returns 1 when raw key code 3 is observed, 0 otherwise. The caller must
 * initialize the display/IC730 path first. This does not check PTT.
 */
uint32_t BootKeyCheckProgramModeKey(void);

/**
 * Fills the active LCD panel with one 16-bit pixel value.
 *
 * Assumes the LCD controller has already been selected/initialized. Call with
 * LcdControllerFillScreen(0) to clear the screen.
 */
void LcdControllerFillScreen(uint32_t color);

/**
 * Returns a 16-bit pixel pointer inside the ROM boot framebuffer.
 *
 * Assumes DisplaySelectBootLayoutAndResetTextState() has selected a layout.
 */
uint16_t *DisplayFramebufferGetPixelAddress(uint32_t row, uint32_t column);

/**
 * Draws one glyph into the ROM boot framebuffer and returns its pixel width.
 *
 * Assumes the framebuffer area being drawn into has already been cleared.
 */
uint8_t DisplayDrawGlyphToFramebuffer(uint8_t *character, uint32_t column, uint32_t top_margin);

/**
 * Blits a framebuffer region to the LCD panel.
 *
 * Assumes the LCD controller has already been selected/initialized.
 */
uint32_t DisplayBlitRegion(LcdBlitFrame *frame, LcdWindowRect *window);

/******************************************************************************/
/* The following functions are used by rom_helpers and should not be called
 directly. */
/******************************************************************************/

/**
 * Initializes the active LCD panel, clears it, then waits briefly.
 *
 * Assumes timer3 is already running.
 */
void DisplayInitializePanelAndClear(void);

/**
 * Applies the ROM pinmux tables used by the boot/display paths.
 */
void SystemApplyPinmuxTables(void);

/**
 * Initializes IC730 display/key sideband support over I2C0.
 *
 * Assumes timer3 is running and I2C0/pinmux are usable.
 */
void DisplayInitializeIoExpanderSupport(void);

/**
 * Enables or disables the active LCD controller display flag.
 *
 * Assumes the LCD controller has already been selected/initialized.
 */
void LcdControllerSetDisplayEnableFlag(uint32_t enable);

/**
 * Selects the ROM boot text layout and resets text rendering state.
 */
uint32_t DisplaySelectBootLayoutAndResetTextState(void);

/**
 * Initializes a ROM timer. Always call as TimerInitialize(3, 0) for timer3.
 */
void TimerInitialize(uint32_t timer_index, int32_t timer_half);


#endif // ROM_FUNCTIONS_H
