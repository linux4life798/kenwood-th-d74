#ifndef ROM_HELPERS_H
#define ROM_HELPERS_H

#include <stdbool.h>

/**
 * Initializes the ROM boot peripherals used by this library.
 *
 * Starts timer3, applies the ROM pinmux tables, initializes and clears the LCD
 * panel, initializes IC730 display/key-scanner sideband support over I2C0,
 * enables the LCD controller, and selects the ROM boot text layout.
 */
void InitializePeripherals(void);
void DisplayClear(void);
void DisplayRenderText(char *text);

/**
 * Returns 1 when the boot ROM's programming-mode button condition is active.
 *
 * Call InitializePeripherals() before this so IC730/key-scanner support is ready.
 */
bool ButtonCheckProgrammingModePressed(void);

#endif // ROM_HELPERS_H
