.arm

.global PanicDisplayRenderText
.equ PanicDisplayRenderText, 0x6000cb00
.global PanicDisplayInitErrorNumber
.equ PanicDisplayInitErrorNumber, 0x6000cb30

.global SystemApplyPinmuxTables
.equ SystemApplyPinmuxTables, 0x6000b610

.global DisplayInitializePanelAndClear
.equ DisplayInitializePanelAndClear, 0x6000d6cc
.global DisplayInitializeIoExpanderSupport
.equ DisplayInitializeIoExpanderSupport, 0x6000d790

.global BootKeyCheckProgramModeKey
.equ BootKeyCheckProgramModeKey, 0x6000c8ec

.global LcdControllerSetDisplayEnableFlag
.equ LcdControllerSetDisplayEnableFlag, 0x6000d7b0
.global DisplaySelectBootLayoutAndResetTextState
.equ DisplaySelectBootLayoutAndResetTextState, 0x6000d7dc
.global DisplayFramebufferGetPixelAddress
.equ DisplayFramebufferGetPixelAddress, 0x6000daf0
.global DisplayDrawGlyphToFramebuffer
.equ DisplayDrawGlyphToFramebuffer, 0x6000d94c
.global DisplayBlitRegion
.equ DisplayBlitRegion, 0x6000d6e4
.global LcdControllerFillScreen
.equ LcdControllerFillScreen, 0x6000a55c

.global TimerInitialize
.equ TimerInitialize, 0x6000c3c0
.global TimerStop
.equ TimerStop, 0x6000c4b8
.global TimerCounterRead
.equ TimerCounterRead, 0x6000c2fc


.global TimerDelayTicks
.equ TimerDelayTicks, 0x60000050
.global TimerDelayMilliseconds
.equ TimerDelayMilliseconds, 0x6000b3d8
