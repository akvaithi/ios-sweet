#!/usr/bin/env python3
"""Retarget an upstream sweet XNU kernel to barbet (Pixel 5a) without a rebuild.

The only sweet-specific constants compiled into the kernel outside of
boot-arg-gated drivers (touch, keys, USB) are the early framebuffer at
0x9c000000 from patches 0010/0012. barbet's cont_splash_region is at
0xa0000000 with the same 1080x2400 BGRA layout. Every site is checked
against its expected old value before it is rewritten.

usage: barbet-patch-kernel.py KERNEL_IN KERNEL_OUT
"""
import struct
import subprocess
import sys

OLD_FB, NEW_FB = 0x9C000000, 0xA0000000


def segments(path):
    out = subprocess.run(["otool", "-l", path], capture_output=True, text=True, check=True).stdout
    segs, cur = [], {}
    for line in out.splitlines():
        f = line.split()
        if not f:
            continue
        if f[0] == "segname":
            cur = {"name": f[1]}
        elif f[0] in ("vmaddr", "vmsize", "fileoff", "filesize") and cur:
            cur[f[0]] = int(f[1], 0)
            if f[0] == "filesize":
                segs.append(cur)
                cur = {}
    return segs


def file_off(segs, va):
    for s in segs:
        if s["filesize"] and s["vmaddr"] <= va < s["vmaddr"] + s["filesize"]:
            return s["fileoff"] + va - s["vmaddr"]
    sys.exit(f"va {va:#x} is not file-backed")


def symbol(path, name):
    out = subprocess.run(["xcrun", "nm", path], capture_output=True, text=True, check=True).stdout
    for line in out.splitlines():
        f = line.split()
        if len(f) == 3 and f[2] == name:
            return int(f[0], 16)
    sys.exit(f"symbol {name} not found")


def movk_imm(word, imm):
    return (word & ~(0xFFFF << 5)) | (imm << 5)


def main():
    src, dst = sys.argv[1:3]
    d = bytearray(open(src, "rb").read())
    segs = segments(src)

    # MOVK ..., lsl #16 carrying the high half of the framebuffer address.
    # Found by disassembly: _arm_vm_init's FB block TTE and _start_first_cpu's
    # early painter (base and base + 2368 rows * 4320).
    sites = [
        (symbol(src, "_arm_vm_init") + 0xB18, 0x9C00, 0xA000),
        (symbol(src, "_start_first_cpu") + 0x18, 0x9C9C, 0xA09C),
        (symbol(src, "_start_first_cpu") + 0x254, 0x9C00, 0xA000),
    ]
    for va, old, new in sites:
        off = file_off(segs, va)
        w = struct.unpack_from("<I", d, off)[0]
        is_movk_lsl16 = (w & 0xFFE00000) == 0xF2A00000
        if not is_movk_lsl16 or (w >> 5) & 0xFFFF != old:
            sys.exit(f"{va:#x}: unexpected instruction {w:#010x}")
        struct.pack_into("<I", d, off, movk_imm(w, new))
        print(f"movk {va:#x}: {old:#06x} -> {new:#06x}")

    # static volatile uint32_t *early_fb (patch 0012)
    va = symbol(src, "_early_fb")
    off = file_off(segs, va)
    if struct.unpack_from("<Q", d, off)[0] != OLD_FB:
        sys.exit("early_fb: unexpected value")
    struct.pack_into("<Q", d, off, NEW_FB)
    print(f"early_fb {va:#x}: {OLD_FB:#x} -> {NEW_FB:#x}")

    open(dst, "wb").write(d)


if __name__ == "__main__":
    main()
