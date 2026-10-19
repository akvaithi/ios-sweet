/*
 * QEMU stand-in for what barbet's ABL leaves behind: a UFS host that is
 * enabled with the link up and a running transfer list. qemu-sweet.py
 * loads this at STUB_PA and patches params (offset 0x20) with boot_args
 * and the xnu entry point. MMU off, EL1, no stack until set below.
 */
	.section .text.head, "ax"
	.globl	_start
_start:
	adr	x9, params
	ldr	x19, [x9]		/* boot_args PA */
	ldr	x20, [x9, #8]		/* xnu entry PA */
	adr	x9, stack_top
	mov	sp, x9
	bl	qemu_ufs_init
	mov	x0, x19
	br	x20
	.balign	8
params:
	.quad	0, 0
