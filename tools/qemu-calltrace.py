#!/usr/bin/env python3
"""Find the call that never returns: hardware breakpoints after every bl/blr
in the given kernel functions, QEMU gdb stub, hits logged in order.

  qemu-calltrace.py [--skip=N] PAYLOAD KERNEL OUTDIR SECS FUNC [FUNC ...]

QEMU allows few hardware breakpoints (aarch64: 16), so keep FUNC lists short;
each breakpoint is removed after its first hit to free the slot.
Needs lldb (Xcode) and tools/qemu-sweet.py.
"""
import os, re, subprocess, sys, time

args = sys.argv[1:]
skip = 0
if args[0].startswith('--skip='):
    skip = int(args.pop(0).split('=')[1])
payload, kernel, out, secs, *funcs = args
secs = int(secs)
here = os.path.dirname(os.path.abspath(__file__))
os.makedirs(out, exist_ok=True)

dis = subprocess.run(['xcrun', 'llvm-objdump', '-d', '--no-show-raw-insn', kernel],
                     capture_output=True, text=True).stdout
sites = []	# (addr after the call, description)
for f in funcs:
    m = re.search(rf'^([0-9a-f]+) <{re.escape(f)}>:\n(.*?)\n\n', dis, re.S | re.M)
    if not m:
        sys.exit(f'{f}: not found')
    sites.append((int(m.group(1), 16), f'enter {f}'))
    for line in m.group(2).splitlines():
        mm = re.match(r'\s*([0-9a-f]+):\s+(bl|blr)\s+(.*)', line)
        if mm:
            sites.append((int(mm.group(1), 16) + 4, f'{f}: back from {mm.group(3).strip()}'))
sites = sites[skip:]
if len(sites) > 16:
    print(f'warning: {len(sites)} sites, only the first 16 get breakpoints', file=sys.stderr)
    sites = sites[:16]

cmds = os.path.join(out, 'trace.lldb')
with open(cmds, 'w') as c:
    c.write(f'target create --arch arm64 {kernel}\ngdb-remote localhost:1234\n')
    for a, d in sites:
        # one-shot, auto-continue; the echo marks the hit in lldb's output
        c.write(f'breakpoint set -H -o true -a {a:#x} -C "script print(\'HIT {a:#x} {d}\')" -G true\n')
    c.write('process continue\n')
q = subprocess.Popen([sys.executable, os.path.join(here, 'qemu-sweet.py'), payload, os.path.join(out, 'q'), '--gdb'],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(3)
log = open(os.path.join(out, 'lldb.txt'), 'w')
lp = subprocess.Popen(['lldb', '-s', cmds], stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT)
time.sleep(secs)
lp.kill()
q.terminate()
subprocess.run(['pkill', '-f', 'qemu-system-aarch64'])
hits = [l for l in open(os.path.join(out, 'lldb.txt')) if l.startswith('HIT')]
open(os.path.join(out, 'hits.txt'), 'w').writelines(hits)
print(''.join(hits) or 'no hits')
