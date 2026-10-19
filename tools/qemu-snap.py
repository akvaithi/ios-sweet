#!/usr/bin/env python3
"""Screenshot a running qemu-sweet.py guest over its QMP socket.

  qemu-snap.py OUTDIR PNG [FB_PA]     (FB_PA default 0xa0000000, barbet)
"""
import importlib.util, json, os, socket, sys, time
here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('qs', os.path.join(here, 'qemu-sweet.py'))
qs = importlib.util.module_from_spec(spec); spec.loader.exec_module(qs)
out, png = sys.argv[1], sys.argv[2]
fb = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0xa0000000
s = socket.socket(socket.AF_UNIX); s.connect(os.path.join(out, 'mon.sock')); f = s.makefile('rw')
def cmd(c, **a):
    f.write(json.dumps({'execute': c, **({'arguments': a} if a else {})}) + '\n'); f.flush()
    while True:
        r = json.loads(f.readline())
        if 'return' in r or 'error' in r:
            return r
f.readline(); cmd('qmp_capabilities')
raw = os.path.abspath(png) + '.raw'
r = cmd('pmemsave', val=fb, size=qs.FB_STRIDE * qs.FB_H, filename=raw)
for _ in range(50):
    if os.path.exists(raw) and os.path.getsize(raw) == qs.FB_STRIDE * qs.FB_H:
        break
    time.sleep(0.1)
qs.write_png(png, open(raw, 'rb').read()); os.unlink(raw)
print(png, r)
