#!/bin/bash
# QEMU smoke test of one kernel: payload with the QEMU ADT, full msgbuf.
#   qemu-try.sh KERNEL ADT OUTDIR "CMDLINE" [SECS] [--ramdisk IMAGE]
set -euo pipefail
kernel=$1 adt=$2 out=$3 cmdline=$4 secs=${5:-200}
shift $(( $# < 5 ? $# : 5 ))
here=$(cd "$(dirname "$0")" && pwd)
rm -rf "$out"
mkdir -p "$out"
python3 "$here/mkpayload.py" "$kernel" "$adt" "$out/payload.bin" --cmdline "$cmdline" "$@" >/dev/null
"$here/qemu-msgbuf.sh" "$out/payload.bin" "$kernel" "$out/run" "$secs" 2>/dev/null
echo "== $(basename "$(dirname "$kernel")"): $(wc -l < "$out/run/msgbuf.txt") lines, last:"
tail -3 "$out/run/msgbuf.txt"
