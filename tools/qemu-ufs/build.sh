#!/bin/bash
# Build stub.bin (flat binary at 0x40200000) for qemu-sweet.py --ufs.
set -euo pipefail
cd "$(dirname "$0")"
CROSS=${CROSS:-aarch64-elf-}
F="-O2 -ffreestanding -nostdlib -mgeneral-regs-only -mstrict-align -fno-stack-protector -Wall"
${CROSS}gcc $F -c start.S -o start.o
${CROSS}gcc $F -c ufs.c -o ufs.o
${CROSS}gcc $F -static -T link.ld -Wl,--build-id=none start.o ufs.o -o stub.elf
${CROSS}objcopy -O binary --pad-to=$(${CROSS}nm stub.elf | gawk '$3=="stack_top"{print "0x"$1}') stub.elf stub.bin
${CROSS}nm stub.elf | grep -E ' (params|_start)$'
