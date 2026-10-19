#!/usr/bin/env python3
"""Live window onto a running qemu-sweet.py guest: the phone screen, the
kernel log from the disk's console ring, and a stuck detector.

  qemu-live.py RUNDIR DISK KERNEL [--port 8765] [--every 10]

RUNDIR is qemu-sweet.py's OUTDIR (mon.sock), DISK the --ufs disk, KERNEL the
matching Mach-O (PC -> symbol). Open http://localhost:PORT/.

Stuck verdicts: the CPU parked in halt_all_cpus (reboot/halt requested), a
panic in the log, or neither log nor screen changing for --quiet seconds.
"""
import argparse, bisect, hashlib, http.server, importlib.util, json, os, socket
import struct, subprocess, threading, time, zlib

here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('qs', os.path.join(here, 'qemu-sweet.py'))
qs = importlib.util.module_from_spec(spec); spec.loader.exec_module(qs)

ap = argparse.ArgumentParser()
ap.add_argument('rundir'); ap.add_argument('disk'); ap.add_argument('kernel')
ap.add_argument('--port', type=int, default=8765)
ap.add_argument('--every', type=float, default=10)
ap.add_argument('--quiet', type=float, default=300, help='seconds without log or screen change before "maybe stuck"')
ap.add_argument('--fb', type=lambda v: int(v, 0), default=0xa0000000)
a = ap.parse_args()
a.rundir, a.disk, a.kernel = map(os.path.abspath, (a.rundir, a.disk, a.kernel))
web = os.path.join(a.rundir, 'live')
os.makedirs(web, exist_ok=True)

syms = []
for line in subprocess.run(['nm', '-n', a.kernel], capture_output=True, text=True).stdout.splitlines():
    f = line.split()
    if len(f) == 3 and f[1] in 'tTsS':
        syms.append((int(f[0], 16), f[2]))
addrs = [s[0] for s in syms]

def symbolize(pc):
    i = bisect.bisect_right(addrs, pc) - 1
    return f'{syms[i][1]}+{pc - syms[i][0]:#x}' if i >= 0 and pc - syms[i][0] < 0x100000 else hex(pc)

class QMP:
    def __init__(self, path):
        self.s = socket.socket(socket.AF_UNIX); self.s.connect(path); self.f = self.s.makefile('rw')
        self.f.readline(); self.cmd('qmp_capabilities')
    def cmd(self, c, **args):
        self.f.write(json.dumps({'execute': c, **({'arguments': args} if args else {})}) + '\n'); self.f.flush()
        while True:
            r = json.loads(self.f.readline())
            if 'return' in r or 'error' in r:
                return r
    def hmp(self, line):
        return self.cmd('human-monitor-command', **{'command-line': line}).get('return', '')

def ring(disk):
    BLK = 4096
    with open(disk, 'rb') as f:
        f.seek(2 * BLK); first, last = struct.unpack_from('<QQ', f.read(BLK), 32)
        f.seek((last + 1 - 1025) * BLK)
        magic, _, size, total, seq = struct.unpack_from('<8sIIQQ', f.read(BLK))
        if magic != b'SWEETLOG':
            return 0, b''
        n = min(total, 64 * 1024)
        start = (total - n) % size
        f.seek((last + 1 - 1024) * BLK + start)
        tail = f.read(min(n, size - start))
        if len(tail) < n:
            f.seek((last + 1 - 1024) * BLK); tail += f.read(n - len(tail))
    return total, tail

def png_half(raw):	# 540x1200: every other pixel
    W, H, S = qs.FB_W, qs.FB_H, qs.FB_STRIDE
    rows = []
    for y in range(0, H, 2):
        line = raw[y * S:(y + 1) * S]
        px = bytearray(W // 2 * 3)
        px[0::3], px[1::3], px[2::3] = line[2::8], line[1::8], line[0::8]
        rows.append(b'\0' + bytes(px))
    ch = lambda t, d: struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d))
    return (b'\x89PNG\r\n\x1a\n' + ch(b'IHDR', struct.pack('>IIBBBBB', W // 2, H // 2, 8, 2, 0, 0, 0))
            + ch(b'IDAT', zlib.compress(b''.join(rows), 3)) + ch(b'IEND', b''))

state = {'started': time.time()}

def monitor():
    q = QMP(os.path.join(a.rundir, 'mon.sock'))
    last_total, last_shot, last_change = None, None, time.time()
    while True:
        t0 = time.time()
        raw_path = os.path.join(web, 'fb.raw')
        q.cmd('pmemsave', val=a.fb, size=qs.FB_STRIDE * qs.FB_H, filename=raw_path)
        time.sleep(0.3)
        raw = open(raw_path, 'rb').read()
        shot = hashlib.sha1(raw).hexdigest()
        open(os.path.join(web, 'live.png.tmp'), 'wb').write(png_half(raw))
        os.replace(os.path.join(web, 'live.png.tmp'), os.path.join(web, 'live.png'))
        regs = q.hmp('info registers')
        pc = next((int(l.split('PC=')[1].split()[0], 16) for l in regs.splitlines() if 'PC=' in l), 0)
        where = symbolize(pc)
        total, tail = ring(a.disk)
        lines = tail.decode('utf-8', 'replace').splitlines()[-80:]
        if total != last_total or shot != last_shot:
            last_change = time.time()
        last_total, last_shot = total, shot
        quiet = time.time() - last_change
        text = '\n'.join(lines)
        if 'halt_all_cpus' in where or 'Debugger' in where:
            verdict = f'STUCK: CPU parked in {where.split("+")[0]} (halt/reboot or panic)'
        elif 'panic(' in text[-4000:] or 'Kernel panic' in text[-4000:]:
            verdict = 'STUCK: panic in the log'
        elif quiet > a.quiet:
            verdict = f'maybe stuck: no log or screen change for {quiet:.0f}s'
        else:
            verdict = 'running'
        state.update(time=time.strftime('%H:%M:%S'), uptime=int(time.time() - state['started']),
                     pc=hex(pc), where=where, log_bytes=total, quiet=int(quiet), verdict=verdict,
                     swaps=text.count('SWEET FB: swap'), springboard='exec SpringBoard' in text,
                     log='\n'.join(lines[-40:]))
        json.dump(state, open(os.path.join(web, 'status.json.tmp'), 'w'))
        os.replace(os.path.join(web, 'status.json.tmp'), os.path.join(web, 'status.json'))
        print(f"{state['time']} {verdict} | {where} | log {total}", flush=True)
        time.sleep(max(0, a.every - (time.time() - t0)))

PAGE = '''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>barbet live</title><style>
body{margin:0;background:#111;color:#ddd;font:13px ui-monospace,Menlo,monospace;display:flex;gap:16px;padding:16px}
#phone{border:10px solid #000;border-radius:36px;box-shadow:0 0 0 2px #333;width:330px;height:733px;object-fit:contain;background:#000}
#side{flex:1;min-width:0} #v{font-size:16px;font-weight:600;padding:8px 10px;border-radius:6px;margin-bottom:8px}
.ok{background:#12351f;color:#7ee2a0}.warn{background:#3a3110;color:#f2d16b}.bad{background:#401616;color:#ff8a8a}
pre{background:#000;padding:10px;border-radius:6px;white-space:pre-wrap;word-break:break-all;height:560px;overflow:auto;margin:8px 0 0}
</style></head><body><img id="phone" src="live.png"><div id="side"><div id="v">connecting...</div>
<div id="m"></div><pre id="log"></pre></div><script>
async function tick(){try{const s=await (await fetch('status.json?'+Date.now())).json();
const v=document.getElementById('v');v.textContent=s.verdict;
v.className=s.verdict.startsWith('STUCK')?'bad':s.verdict.startsWith('maybe')?'warn':'ok';
document.getElementById('m').textContent=`${s.time}  up ${s.uptime}s  pc ${s.where}  log ${s.log_bytes} B  quiet ${s.quiet}s  swaps ${s.swaps}  SpringBoard ${s.springboard?'yes':'no'}`;
const l=document.getElementById('log');const atEnd=l.scrollTop+l.clientHeight>=l.scrollHeight-20;l.textContent=s.log;if(atEnd)l.scrollTop=l.scrollHeight;
document.getElementById('phone').src='live.png?'+Date.now();}catch(e){}}
setInterval(tick,3000);tick();</script></body></html>'''
open(os.path.join(web, 'index.html'), 'w').write(PAGE)

threading.Thread(target=monitor, daemon=True).start()
os.chdir(web)
http.server.ThreadingHTTPServer(('127.0.0.1', a.port),
    lambda *x: http.server.SimpleHTTPRequestHandler(*x, directory=web)).serve_forever()
