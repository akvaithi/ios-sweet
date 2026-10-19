ENTRY(_start)
SECTIONS
{
	. = 0x40200000;
	.text : { *(.text.head) *(.text*) }
	.rodata : { *(.rodata*) }
	.data : { *(.data*) }
	.bss : { *(.bss*) *(COMMON) }
	. = ALIGN(16);
	. += 0x4000;
	stack_top = .;
	/DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
