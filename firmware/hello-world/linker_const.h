#ifndef LINKER_CONST_H
#define LINKER_CONST_H

extern char __copy_length[];
extern char __ddr_start[];

#define LINKER_SYMBOL_U32(sym) ((uint32_t)(uintptr_t)(sym))

#endif
