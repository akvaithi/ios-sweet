#!/bin/bash
# Build the shim and wrap it in a boot.img v2 for barbet (Pixel 5a) ABL.
# Host: macOS with brew aarch64-elf-gcc/binutils and gawk.
set -euo pipefail
cd "$(dirname "$0")"
CROSS=${CROSS:-aarch64-elf-}
CC=${CROSS}gcc
OBJCOPY=${CROSS}objcopy
MKBOOTIMG=${MKBOOTIMG:-../../tools-ext/mkbootimg/mkbootimg.py}
DTB=${DTB:-../../device/factory/img/vb_unpacked/dtb}
CFLAGS="-O2 -ffreestanding -nostdlib -fno-pic -mgeneral-regs-only -mstrict-align -fno-stack-protector -Wall -Wextra ${EXTRA_CFLAGS:-}"
mkdir -p out
for f in start.S shim.c console.c mmu.c fdt.c loader.c ufs.c; do
	$CC $CFLAGS -c $f -o out/${f%.*}.o
done
# The image runs wherever ABL puts it with no relocation pass: only the
# header's image_size (start.o, linked at 0) may be an absolute address.
abs=$(${CROSS}readelf -r out/shim.o out/console.o out/mmu.o out/fdt.o out/loader.o out/ufs.o | grep -c ABS64 || true)
[ "$abs" = 0 ] || { echo "error: $abs absolute relocations in C objects" >&2; exit 1; }
$CC $CFLAGS -static -T shim.ld -Wl,--build-id=none -Wl,--no-warn-rwx-segments -Wl,-N \
	out/start.o out/shim.o out/console.o out/mmu.o out/fdt.o out/loader.o out/ufs.o -o out/shim.elf
$OBJCOPY -O binary out/shim.elf out/Image
# ABL copies the file; pad to image_size so .bss/stacks exist as zeroed bytes.
size=$(${CROSS}nm out/shim.elf | gawk '$3=="_end"{print strtonum("0x"$1)}')
truncate -s "$size" out/Image
# barbet ABL only takes a compressed kernel, as stock ships it: LZ4 frame format.
lz4 -12 -f -q out/Image out/Image.lz4
# Ramdisk: an xnu payload (tools/mkpayload.py) if given as $1, else an empty
# newc cpio (ABL dislikes a zero-size ramdisk on some builds) -> diagnostics.
if [ -n "${1:-}" ]; then
	cp "$1" out/ramdisk.bin
else
	(cd out && rm -rf rd && mkdir rd && cd rd && find . | cpio -o -H newc --quiet | gzip -9 > ../ramdisk.bin)
fi
# barbet ABL rejects v2 ("Unsupported"). v3: DTB and the vendor ramdisk come
# from the phone's vendor_boot; ABL puts the vendor ramdisk first, so the
# loader has to look for the payload magic past it.
python3 "$MKBOOTIMG" --header_version ${HDR:-3} --kernel out/Image.lz4 --ramdisk out/ramdisk.bin \
	--os_version 14.0.0 --os_patch_level 2024-08 --cmdline "console=null" \
	-o out/shim-boot.img
# Host render of the console layout.
cc -O1 -Wall -o out/host_test console.c host_test.c && ./out/host_test
ls -l out/Image out/shim-boot.img
# barbet ABL refuses a boot.img without an AVB footer ("Unsupported"), even
# unlocked. Mirror the stock footer: 100 MiB, hash descriptor, build props.
AVBTOOL=${AVBTOOL:-../../tools-ext/avb/avbtool.py}
python3 "$AVBTOOL" add_hash_footer --image out/shim-boot.img --partition_name boot \
	--partition_size 100663296 --algorithm SHA256_RSA4096 \
	--key ../../tools-ext/avb/test/data/testkey_rsa4096.pem \
	--prop com.android.build.boot.os_version:14 \
	--prop com.android.build.boot.fingerprint:google/barbet/barbet:14/AP2A.240805.005.S4/12281092:user/release-keys \
	--prop com.android.build.boot.security_patch:2024-08-05
ls -l out/shim-boot.img
