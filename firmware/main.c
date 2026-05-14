#include <stdint.h>
#include "rom_functions.h"

#define FLASH_BASE ((volatile const uint32_t *)0x60200000u)

int main(void)
{
    volatile uint32_t dwCount;
    void (*pBootLoaderEntry)(void) = (void (*)(void))0x6000c9bcu;
    void (*pDisplayShowInitError)(uint32_t) = (void (*)(uint32_t))0x6000cb30u;
    // void (*pDisplayRenderText)(char *) = (void (*)(char *))0x6000cb00u;

    // pDisplayRenderText("Hello Craig!");
    PanicDisplayRenderText("Hello Craig!");

    // pDisplayShowInitError(0x1);

    // for (dwCount = 0; dwCount < 1000000u; dwCount++) {
    // }

    // pDisplayShowInitError(0x0);

    // Doesn't work.
    // pBootLoaderEntry();

    for (;;) {
    }
}
