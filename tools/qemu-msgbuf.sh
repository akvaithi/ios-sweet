#!/bin/bash
# Full kernel message buffer from a QEMU run (fb.txt is only the last screen).
#   qemu-msgbuf.sh PAYLOAD KERNEL OUTDIR [SECS]
# Same inputs give the same addresses, so two short runs find msgbufp ->
# struct msgbuf -> bufc, and the real run memsaves the buffer (NOTES.md:140).
set -euo pipefail
payload=$1 kernel=$2 out=$3 secs=${4:-150}
here=$(cd "$(dirname "$0")" && pwd)
q() { python3 "$here/qemu-sweet.py" "$payload" "$1" --secs "$2" "${@:3}" >/dev/null 2>&1 || true; }
hx() { awk -v c="$2" 'f && /^[0-9a-f]+:/ {print $2; exit} index($0, c) {f=1}' "$1/regs.txt"; }

p=$(nm "$kernel" | awk '$3=="_msgbufp"{print "0x"$1}')
q "$out.a" 20 --hmp "x /1gx $p"
s=$(hx "$out.a" "x /1gx $p")
q "$out.b" 20 --hmp "x /3gx $s"
# HMP prints two quads per line: bufc (the 3rd) is the first word of line 2.
bufc=$(awk -v c="x /3gx $s" 'f && /^[0-9a-f]+:/ {n++; if (n == 2) {print $2; exit}} index($0, c) {f=1}' "$out.b/regs.txt")
echo "msgbufp $p -> struct $s -> bufc $bufc" >&2
q "$out" "$secs" --kernel "$kernel" --hmp "memsave $bufc 0x20000 \"$out/msgbuf.raw\""
tr -d '\0' < "$out/msgbuf.raw" > "$out/msgbuf.txt"
rm -rf "$out.a" "$out.b"
wc -l "$out/msgbuf.txt" >&2
