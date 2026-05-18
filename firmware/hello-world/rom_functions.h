#ifndef ROM_FUNCTIONS_H
#define ROM_FUNCTIONS_H

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
 * Reinitializes the display and show exactly one text line.
 *
 * Calling this repeatedly will redraw the display, but it will also
 * cause a full initialization of the display each time.
 */
void PanicDisplayRenderText(char *text);

/**
 * Reinitializes the display and show Init Error [n] message
 *
 * Calling this repeatedly will redraw the display, but it will also
 * cause a full initialization of the display each time.
 */
void PanicDisplayInitErrorNumber(uint32_t error_number);


void DisplayInitializePanelAndClear(void);
void SystemApplyPinmuxTables(void);
void DisplayInitializeIoExpanderSupport(void);
void LcdControllerSetDisplayEnableFlag(uint32_t enable);
uint32_t DisplaySelectBootLayoutAndResetTextState(void);

/**
 * Call with LcdControllerFillScreen(0) to clear the screen.
 */
void LcdControllerFillScreen(uint32_t color);

uint16_t *DisplayFramebufferGetPixelAddress(uint32_t row, uint32_t column);
uint8_t DisplayDrawGlyphToFramebuffer(uint8_t *character, uint32_t column, uint32_t top_margin);
uint32_t DisplayBlitRegion(LcdBlitFrame *frame, LcdWindowRect *window);

/**
 * Always call as TimerInitialize(3, 0) to initialize timer3.
 */
void TimerInitialize(uint32_t timer_index, int32_t timer_half);

/**
 * Always call as TimerStop(3, 0) to stop timer3.
 */
void TimerStop(uint32_t timer_index, int32_t timer_half);

/**
 * Always call as TimerCounterRead(3) to read timer3.
 */
uint64_t TimerCounterRead(uint32_t timer_index);

/**
 * Relies on timer 3.
 */
void TimerDelayTicks(uint32_t ticks);

/**
 * Relies on timer 3.
 */
void TimerDelayMilliseconds(uint32_t milliseconds);

#endif // ROM_FUNCTIONS_H
