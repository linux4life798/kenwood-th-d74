#ifndef ROM_FUNCTIONS_H
#define ROM_FUNCTIONS_H

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

#endif // ROM_FUNCTIONS_H
