#!/usr/bin/env python3
"""Raw image -> Android sparse image (what AOSP img2simg does), for macOS
where platform-tools ships no img2simg and fastboot refuses a 16 GiB raw file.
All-zero 4 KiB blocks become DONT_CARE chunks.

usage: img2simg.py RAW OUT.simg
"""
import os
import struct
import sys

BLK = 4096
MAGIC, RAW, DONT_CARE = 0xED26FF3A, 0xCAC1, 0xCAC3
ZERO = bytes(BLK)


def main():
    src, dst = sys.argv[1:3]
    size = os.path.getsize(src)
    if size % BLK:
        sys.exit("size is not a multiple of 4096")
    total = size // BLK
    chunks = []	# (type, first block, count)
    with open(src, "rb") as f:
        for b in range(total):
            kind = DONT_CARE if f.read(BLK) == ZERO else RAW
            if chunks and chunks[-1][0] == kind:
                chunks[-1][2] += 1
            else:
                chunks.append([kind, b, 1])
        with open(dst, "wb") as o:
            o.write(struct.pack("<IHHHHIIII", MAGIC, 1, 0, 28, 12, BLK, total, len(chunks), 0))
            for kind, first, n in chunks:
                data = n * BLK if kind == RAW else 0
                o.write(struct.pack("<HHII", kind, 0, n, 12 + data))
                if kind == RAW:
                    f.seek(first * BLK)
                    for _ in range(n):
                        o.write(f.read(BLK))
    raw = sum(c[2] for c in chunks if c[0] == RAW)
    print(f"{total} blocks, {len(chunks)} chunks, {raw * BLK >> 20} MiB data")


if __name__ == "__main__":
    main()
