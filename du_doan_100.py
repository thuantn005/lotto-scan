#!/usr/bin/env python3
"""Chon DUNG 100 ve du doan cho ky tiep theo (Lotto 5/35 hoac Mega 6/45) va luu vao du_doan/<game>_<ky>.txt.
  python3 du_doan_100.py GAME THU_MUC_GZ        GAME = lotto535 | mega      (so ve: env TARGET_N, mac dinh 100)
Thu tu uu tien (dedupe, du 100 thi dung):
  1) ve sinh tu seed THEO MUC (seed da du doan dung nhieu lan nhat truoc; muc 3+, 2, 1; doc seed_state/hits_<game>.tsv do seed_levels.py ghi)
  2) ve CON LAI (khong seed nao tren cac cap dang dung sinh ra); neu nhieu hon can -> lay mau co dinh theo ky (rng seed = ky)
  3) ve it seed nhat (do boi 1 seed, roi 2 seed, ...), theo thu tu ma ve
Luon xuat DU TARGET_N ve. Muc/seed chi la thong ke: moi ve van chi co xac suat ngau nhien."""
import os, sys, re, glob, json, csv
import numpy as np, pandas as pd
from math import comb
game, gzdir = sys.argv[1], sys.argv[2]
LOTTO = game == 'lotto535'; NEED = int(os.environ.get('TARGET_N') or 100); USE = int(os.environ.get('USE_PAIRS') or (47 if LOTTO else 0))
KEEP = int(os.environ.get('KEEP_DU_DOAN') or 30)
MOD = 324632 if LOTTO else 8145060; CT = MOD * 12 if LOTTO else MOD
M1 = np.uint64(0x9E3779B97F4A7C15); M2 = 0xD1B54A32D192ED03; M3 = np.uint64(0xBF58476D1CE4E5B9); M4 = np.uint64(0x94D049BB133111EB)
def _mix(x):
    x = x ^ (x >> np.uint64(30)); x = x * M3; x = x ^ (x >> np.uint64(27)); x = x * M4; return x ^ (x >> np.uint64(31))
def tid(s, d):
    with np.errstate(over='ignore'):
        m = _mix(s * M1 + np.uint64((d * M2) & ((1 << 64) - 1))); r = (m % np.uint64(MOD)).astype(np.int64)
        return r * 12 + (_mix(m) % np.uint64(12)).astype(np.int64) if LOTTO else r
if LOTTO:
    import lotto_common as LC
    _lut = LC.build_rank_to_mask(LC.build_binom())
    def dec(v):
        r, sp = divmod(int(v), 12); m = _lut[r]
        return '-'.join(f'{x:02d}' for x in range(1, 36) if m >> (x - 1) & 1) + f' + {sp + 1:02d}'
else:
    _T = [np.array([comb(i, j) if i >= j else 0 for i in range(46)], dtype=np.int64) for j in range(7)]
    def dec(v):
        r = int(v); out = []
        for j in range(6, 0, -1):
            x = int(np.searchsorted(_T[j], r, side='right')) - 1; out.append(x + 1); r -= int(_T[j][x])
        return '-'.join(f'{x:02d}' for x in sorted(out))
csvf = 'data/all.csv' if LOTTO else 'data/mega_all.csv'
ids = [int(r['draw_id']) for r in csv.DictReader(open(csvf, encoding='utf-8', newline='')) if (r.get('draw_id') or '').isdigit() and (not LOTTO or r.get('product') == 'lotto535')]
N = max(ids) + 1
pat = re.compile(r'first2_(?:mega_)?(\d+)_(\d+)\.txt\.gz$'); files = []
for f in glob.glob(os.path.join(gzdir, '*.txt.gz')):
    m = pat.search(f)
    if m: files.append((int(m.group(1)), int(m.group(2)), f))
files.sort(key=lambda p: -p[0])
if USE > 0: files = files[:USE]
cnt = np.zeros(CT, dtype=np.int32); nseed = 0
for a, b, f in files:
    s = pd.read_csv(f, sep=' ', header=None, usecols=[0], dtype={0: np.uint64}, engine='c')[0].to_numpy()
    nseed += len(s); cnt += np.bincount(tid(s, N), minlength=CT).astype(np.int32)
chosen = []; used = set()
def add(v, src, det):
    if len(chosen) < NEED and int(v) not in used: used.add(int(v)); chosen.append((int(v), src, det))
# 1) seed theo muc
lv = []
hf = f'seed_state/hits_{game}.tsv'
if os.path.exists(hf):
    for l in open(hf):
        a = l.rstrip('\n').split('\t')
        if len(a) != 3: continue
        ks = sorted(int(x) for x in a[2].split(',') if x and int(x) < N)
        if ks: lv.append((-len(ks), int(a[0]), a[1], ks))
lv.sort()
if lv:
    t = tid(np.array([x[1] for x in lv], dtype=np.uint64), N)
    for (nl, sd, pr, ks), v in zip(lv, t): add(v, f'muc{min(-nl, 3)}', f'seed {sd} cap {pr} dung {len(ks)} lan: {",".join(map(str, ks))}')
n_muc = len(chosen)
# 2) ve con lai
rem = np.flatnonzero(cnt == 0); n_rem_total = int(len(rem)); need = NEED - len(chosen)
if need > 0 and len(rem):
    pick = np.sort(rem if len(rem) <= need else np.random.default_rng(N).choice(rem, size=need, replace=False))
    for v in pick: add(v, 'con_lai', 'khong seed nao sinh ra')
n_rem = len(chosen) - n_muc
# 3) ve it seed nhat
c = 1
while len(chosen) < NEED and c <= 200:
    for v in np.flatnonzero(cnt == c)[:NEED]: add(v, 'it_seed', f'{c} seed')
    c += 1
os.makedirs('du_doan', exist_ok=True)
out = f'du_doan/{game}_{N}.txt'
with open(out, 'w') as o:
    o.write(f'# Ky {N} ({game}): {len(chosen)} ve du doan | {len(files)} cap, {nseed:,} seed | ve con lai (khong seed nao sinh): {n_rem_total:,}\n')
    o.write(f'# nguon: muc (seed da du doan dung) {n_muc} | con_lai {n_rem} | it_seed {len(chosen) - n_muc - n_rem}. Moi ve chi co xac suat ngau nhien 1/{CT:,}.\n# ve | nguon | chi tiet\n')
    for v, src, det in chosen: o.write(f'{dec(v)} | {src} | {det}\n')
# danh sach VE CON LAI day du (neu <= CON_LAI_MAX, mac dinh 500 - Lotto thuong chi vai ve; Mega thi qua nhieu nen chi ghi so luong trong header)
CLMAX = int(os.environ.get('CON_LAI_MAX') or 500)
if 0 < n_rem_total <= CLMAX:
    with open(f'du_doan/con_lai_{game}_{N}.txt', 'w') as o:
        o.write(f'# Ky {N} ({game}): {n_rem_total} ve CON LAI (khong seed nao tren {len(files)} cap sinh ra)\n')
        for v in rem: o.write(dec(v) + '\n')
# giu KEEP file gan nhat
for pre in (f'du_doan/{game}_*.txt', f'du_doan/con_lai_{game}_*.txt'):
    fs = sorted(glob.glob(pre), key=lambda p: int(re.search(r'_(\d+)\.txt$', p).group(1)))
    for p in fs[:-KEEP]: os.remove(p)
print(f'{game} ky {N}: {len(chosen)} ve (muc {n_muc}, con_lai {n_rem}, it_seed {len(chosen) - n_muc - n_rem}) | con lai tong {n_rem_total:,} -> {out}')
