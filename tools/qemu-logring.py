#!/usr/bin/env python3
"""Read the kernel's persistent console ring (xnu 0047, sweetlog=1) straight
from a QEMU UFS disk built by mkdisk-gpt.py: last 1025 blocks of userdata.

  qemu-logring.py DISK.raw [OUT.txt]
"""
import struct, sys
BLK, FIRST = 4096, 256
disk = sys.argv[1]
with open(disk, 'rb') as f:
    mbr = f.read(BLK); hdr = f.read(BLK)
    ent = f.read(BLK)
    first, last = struct.unpack_from('<QQ', ent, 32)
    f.seek((last + 1 - 1025) * BLK)
    magic, ver, size, total, seq = struct.unpack_from('<8sIIQQ', f.read(BLK))
    assert magic == b'SWEETLOG', magic
    ring = f.read(size)
n = min(total, size)
txt = bytes(ring[(total - n + i) % size] for i in range(n))
print(f'total {total} bytes, flush {seq}', file=sys.stderr)
(open(sys.argv[2], 'wb') if len(sys.argv) > 2 else sys.stdout.buffer).write(txt)
