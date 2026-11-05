#!/usr/bin/env python3
"""Tu dong: loai ve Lotto 5/35 bang cac seed inverse (inverse/first2_*.txt.gz + seed 4 hit) cho ky tiep theo.
Ghi vao ve_con_lai/: con_lai_<ky>.txt, 1_2_seed_<ky>.txt, thong_ke_<ky>.txt (+ loai_<ky>.txt.gz neu EXPORT_LOAI=true).
Neu con lai > TARGET: de xuat hang doi cap quet them (GITHUB_OUTPUT: next_queue).
Bien moi truong: DRAW (de trong = tu tinh ky sap quay), TARGET (mac dinh 1), MAX_PAIRS (12), EXPORT_LOAI (false), KEEP (10)."""
import os, re, glob, gzip, math, datetime as dt
import numpy as np, pandas as pd
import lotto_common as LC

M1 = np.uint64(0x9E3779B97F4A7C15); M2 = np.uint64(0xD1B54A32D192ED03)
M3 = np.uint64(0xBF58476D1CE4E5B9); M4 = np.uint64(0x94D049BB133111EB)
C = 324632; N = C * 12; PER_PAIR = 1_215_000
TARGET = int(os.environ.get('TARGET') or 1); MAX_PAIRS = int(os.environ.get('MAX_PAIRS') or 12)
EXPORT = (os.environ.get('EXPORT_LOAI') or 'false').lower() == 'true'; KEEP = int(os.environ.get('KEEP') or 10)

def next_draw():
    d = (os.environ.get('DRAW') or '').strip()
    if d: return int(d)
    # Lotto 5/35: 2 ky/ngay luc 13:00 va 21:00 (gio VN). Moc: ky 989 luc 13:00 05/11/2026.
    vn = dt.timezone(dt.timedelta(hours=7)); now = dt.datetime.now(vn)
    anchor = dt.datetime(2026, 11, 5, 13, 0, tzinfo=vn); k = 989
    n = math.floor((now - anchor).total_seconds() / (8 * 3600))   # buoc 8h/ky khong dung -> tinh theo lich
    # dem so ky da quay den now theo lich 13:00, 21:00
    slots = 0; t = anchor
    day = anchor.date()
    while True:
        for h in (13, 21):
            s = dt.datetime(day.year, day.month, day.day, h, 0, tzinfo=vn)
            if s <= anchor: continue
            if s <= now: slots += 1
            else: return max(k + slots + 1, LC.get_next_draw_id('data/all.csv'))
        day += dt.timedelta(days=1)

def mix(x):
    x = x ^ (x >> np.uint64(30)); x = x * M3; x = x ^ (x >> np.uint64(27)); x = x * M4; return x ^ (x >> np.uint64(31))
def tid(s, d):
    with np.errstate(over='ignore'):
        m = mix(s * M1 + np.uint64(d) * M2)
        return (m % np.uint64(C)).astype(np.int64) * 12 + (mix(m) % np.uint64(12)).astype(np.int64)

D = next_draw(); print('Ky tiep theo:', D)
b = LC.build_binom(); lut = LC.build_rank_to_mask(b)
def dec(v):
    mk = lut[v // 12]; return '-'.join(f'{x:02d}' for x in range(1, 36) if mk >> (x - 1) & 1) + f' + {v % 12 + 1:02d}'

files = sorted(glob.glob('inverse/first2_*_*.txt.gz'))
pairs = []; data = {}; cnt = np.zeros(N, np.int32); nseed = 0
for f in files:
    a, bb = [int(x) for x in re.search(r'first2_(\d+)_(\d+)', f).groups()]; pairs.append((a, bb))
    s = pd.read_csv(f, sep=' ', header=None, usecols=[0], dtype={0: np.uint64})[0].to_numpy()
    data[(a, bb)] = s; nseed += len(s); cnt += np.bincount(tid(s, D), minlength=N).astype(np.int32)
S4 = set()
for f in glob.glob('inverse/all_*_r*_*[0-9].txt'):
    for l in open(f):
        p = l.split()
        if len(p) == 3 and p[0].isdigit(): S4.add(int(p[0]))
excl = cnt > 0
if S4: excl[tid(np.array(sorted(S4), dtype=np.uint64), D)] = True
rem = np.nonzero(~excl)[0]; R = len(rem)
os.makedirs('ve_con_lai', exist_ok=True)
with open(f've_con_lai/con_lai_{D}.txt', 'w') as o:
    for v in rem: o.write(dec(int(v)) + '\n')
sel = np.nonzero((cnt >= 1) & (cnt <= 2))[0]; found = {}
for pr, s in data.items():
    t = tid(s, D); m = np.isin(t, sel)
    for sd, tt in zip(s[m], t[m]): found.setdefault(int(tt), []).append((f'{pr[0]}:{pr[1]}', int(sd)))
with open(f've_con_lai/1_2_seed_{D}.txt', 'w') as o:
    o.write('# ve | so seed | cap:seed (chi ve do 1 hoac 2 seed sinh ra)\n')
    for v in sel: o.write(dec(int(v)) + f' | {int(cnt[v])} | ' + ' ; '.join(f'{t}:{sd}' for t, sd in found[int(v)]) + '\n')
if EXPORT:
    with gzip.open(f've_con_lai/loai_{D}.txt.gz', 'wt') as o:
        for v in np.nonzero(excl)[0]: o.write(dec(int(v)) + '\n')
# de xuat quet them
queue = ''
if R > TARGET:
    extra = N * math.log(R / TARGET); need = max(1, min(MAX_PAIRS, math.ceil(extra / PER_PAIR)))
    done = set(pairs); low = [a for a, _ in pairs if a >= 100]; m = min(low) if low else 0
    cand = []; d = m - 2
    while len(cand) < need and d >= 17:
        if (d, d + 1) not in done: cand.append(f'{d}:{d+1}')
        d -= 2
    queue = ','.join(cand)
exp = N * math.exp(-(nseed + len(S4)) / N)
txt = [f'Ky {D} | {len(pairs)} cap | {nseed + len(S4):,} seed (gom {len(S4)} seed 4 hit)',
       f'Ve bi loai: {int(excl.sum()):,} / {N:,} | CON LAI: {R:,} (ky vong theo cong thuc ~{exp:.1f})',
       f've 1-2 seed: {len(sel)} | cap quet them de xuat: {queue or "khong can (da <= " + str(TARGET) + " ve)"}',
       'Luu y: ve con lai la ngau nhien, khong co xac suat trung cao hon ve khac (1/3.895.584 moi ve).']
open(f've_con_lai/thong_ke_{D}.txt', 'w').write('\n'.join(txt) + '\n'); print('\n'.join(txt))
# don file cu
for pre in ('con_lai_', '1_2_seed_', 'thong_ke_', 'loai_'):
    fs = sorted(glob.glob(f've_con_lai/{pre}*'), key=lambda x: int(re.search(r'_(\d+)\.', x).group(1)))
    for f in fs[:-KEEP]: os.remove(f)
go = os.environ.get('GITHUB_OUTPUT')
if go:
    with open(go, 'a') as o: o.write(f'draw={D}\nremaining={R}\nnext_queue={queue}\n')
