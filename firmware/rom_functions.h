#ifndef ROM_FUNCTIONS_H
#define ROM_FUNCTIONS_H

/**
 * Reinitializes the display to show exactly one text line.
 *
 * Calling this repeatedly will redraw the display, but it will also
 * cause a full initialization of the display each time.
 */
void PanicDisplayRenderText(char *text);

#endif // ROM_FUNCTIONS_H
