#include <stdint.h>

#include "rom_functions.h"
#include "rom_helpers.h"

int main(void)
{
    InitializePeripherals();
    DisplayRenderText("Hello World!");

    for (;;)
        ;
}
