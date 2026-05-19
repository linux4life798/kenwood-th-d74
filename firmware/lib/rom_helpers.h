#ifndef ROM_HELPERS_H
#define ROM_HELPERS_H

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

#endif // ROM_HELPERS_H
