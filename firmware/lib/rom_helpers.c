#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#include "rom_helpers.h"
#include "rom_functions.h"

typedef struct {
    uint16_t left;
    uint16_t top;
    uint16_t width;
    uint16_t height;
    uint8_t max_chars;
    uint8_t font_size_code;
    uint16_t reserved;
} BootDisplayLayout;

#define BOOT_DISPLAY_MODE ((volatile uint8_t *)0xffff01cbu)
#define BOOT_DISPLAY_LAYOUTS ((const BootDisplayLayout *)0x6000db80u)

#define GPIO_BANK01_INPUT_DATA ((volatile uint32_t *)0x01e26020u)
#define PTT_BUTTON_GPIO_MASK (1u << 7)

static const BootDisplayLayout *DisplayGetCurrentLayout(void)
{
    return &BOOT_DISPLAY_LAYOUTS[*BOOT_DISPLAY_MODE];
}

static void DisplayBuildBlitDescriptors(LcdBlitFrame *frame, LcdWindowRect *window)
{
    const BootDisplayLayout *layout = DisplayGetCurrentLayout();

    frame->pixels = DisplayFramebufferGetPixelAddress(0, 0);
    frame->width = layout->width;
    frame->height = layout->height;
    frame->pixel_offset = 0;
    frame->flags = 0;
    frame->reserved0 = 0;
    frame->reserved1 = 0;
    frame->reserved2 = 0;

    window->left = layout->left;
    window->top = layout->top;
    window->width = layout->width;
    window->height = layout->height;
}

void InitializePeripherals(void)
{
    TimerInitialize(3, 0);
    SystemApplyPinmuxTables();
    DisplayInitializePanelAndClear();
    DisplayInitializeIoExpanderSupport();
    LcdControllerSetDisplayEnableFlag(1);
    DisplaySelectBootLayoutAndResetTextState();
}

void DisplayClear(void)
{
    LcdControllerFillScreen(0);
}

void DisplayRenderText(char *text)
{
    LcdBlitFrame frame;
    LcdWindowRect window;
    const BootDisplayLayout *layout;
    uint32_t pixel_count;
    uint32_t pixel_index;
    uint32_t column;
    uint16_t char_count;
    uint8_t glyph_width;

    if (text == NULL) {
        text = "";
    }

    DisplayBuildBlitDescriptors(&frame, &window);
    if (frame.pixels == 0) {
        return;
    }

    pixel_count = (uint32_t)frame.width * (uint32_t)frame.height;
    for (pixel_index = 0; pixel_index < pixel_count; pixel_index++) {
        frame.pixels[pixel_index] = 0;
    }

    layout = DisplayGetCurrentLayout();
    column = 0;
    char_count = 0;
    while ((char_count < layout->max_chars) && (*text != '\0')) {
        glyph_width = DisplayDrawGlyphToFramebuffer((uint8_t *)text, column & 0xffffu, 0);
        column += glyph_width;
        text++;
        char_count++;
    }

    DisplayBlitRegion(&frame, &window);
}

bool ButtonCheckProgrammingModePressed(void)
{
    uint32_t dwGpioInData01 = *GPIO_BANK01_INPUT_DATA;
    uint32_t dwOneKeyPressed = BootKeyCheckProgramModeKey();

    if (((dwGpioInData01 & PTT_BUTTON_GPIO_MASK) == 0) && (dwOneKeyPressed == 1)) {
        return 1;
    }

    return 0;
}
