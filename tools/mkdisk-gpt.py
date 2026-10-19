#!/usr/bin/env python3
"""Wrap a raw HFS+ root image in a GPT disk with one partition named
"userdata", the way the phone's LUN 0 looks to bsd/dev/sweet_ufs.c.
4 KiB logical blocks (UFS). The output is sparse: all-zero blocks of the
image are skipped, so an 11 GiB-used 16 GiB root costs ~11 GiB.

  mkdisk-gpt.py ROOT.img DISK.raw
"""
import os, struct, sys, uuid, zlib

BLK = 4096
FIRST = 256			# partition start: 1 MiB
NENT, ESZ = 128, 128		# entries x size: 16 KiB = 4 blocks at LBA 2
ZERO = bytes(BLK)
BASIC_DATA = uuid.UUID('ebd0a0a2-b9e5-4433-87c0-68b6b72699c7')

src, dst = sys.argv[1:3]
size = os.path.getsize(src)
assert size % BLK == 0
nblk = size // BLK
last_part = FIRST + nblk - 1
total = last_part + 1 + 5 + 1	# backup entries + backup header

ent = bytearray(NENT * ESZ)
struct.pack_into('<16s16sQQQ', ent, 0, BASIC_DATA.bytes_le, uuid.uuid4().bytes_le, FIRST, last_part, 0)
name = 'userdata'.encode('utf-16-le')
ent[56:56 + len(name)] = name
ecrc = zlib.crc32(ent)

def header(my, alt, entries_lba):
    h = bytearray(92)
    struct.pack_into('<8sIIIIQQQQ16sQIII', h, 0, b'EFI PART', 0x10000, 92, 0, 0,
                     my, alt, 6, total - 7, uuid.uuid4().bytes_le, entries_lba, NENT, ESZ, ecrc)
    struct.pack_into('<I', h, 16, zlib.crc32(h))
    return bytes(h) + bytes(BLK - 92)

mbr = bytearray(BLK)
struct.pack_into('<BBBBBBBBII', mbr, 446, 0, 0, 2, 0, 0xEE, 0xFF, 0xFF, 0xFF, 1, min(total - 1, 0xFFFFFFFF))
mbr[510:512] = b'\x55\xaa'

with open(dst, 'wb') as o, open(src, 'rb') as i:
    o.truncate(total * BLK)
    o.write(mbr + header(1, total - 1, 2) + ent)
    data = 0
    for b in range(nblk):
        blk = i.read(BLK)
        if blk != ZERO:
            o.seek((FIRST + b) * BLK)
            o.write(blk)
            data += 1
    o.seek((total - 6) * BLK)
    o.write(ent)
    o.write(header(total - 1, 1, total - 6))
print(f'{dst}: {total * BLK >> 20} MiB, userdata at LBA {FIRST}, {data * BLK >> 20} MiB data')
