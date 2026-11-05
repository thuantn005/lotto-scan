#!/usr/bin/env python3
"""Loai ve Mega 6/45 cho ky tiep theo, doc streaming tung file gz (it RAM, hop 100+ trieu seed).
Dung (o goc repo, can mega_lib.py): python3 ve_con_lai_mega_release.py THU_MUC_GZ NEXT_DRAW_ID [MAX_LIST=300000]
Ghi ve_con_lai_mega_summary_<ky>.txt (luon) va ve_con_lai_mega_<ky>.txt (neu so ve con lai <= MAX_LIST)."""
import sys, glob, os, re
import numpy as np, pandas as pd
from math import comb
from mega_lib import C, M1, M2
d, nxt = sys.argv[1], int(sys.argv[2]); maxl = int(sys.argv[3]) if len(sys.argv) > 3 else 300000
M3 = np.uint64(0xBF58476D1CE4E5B9); M4 = np.uint64(0x94D049BB133111EB)
add = np.uint64((nxt * M2) & ((1 << 64) - 1)); m1 = np.uint64(M1)
mask = np.ones(C, bool); nseed = 0; pairs = []
files = sorted(glob.glob(os.path.join(d, 'first2_mega_*_*.txt.gz')))
for f in files:
    s = pd.read_csv(f, sep=' ', header=None, usecols=[0], dtype={0: np.uint64}, engine='c')[0].to_numpy()
    nseed += len(s)
    with np.errstate(over='ignore'):
        x = s * m1 + add
        x ^= x >> np.uint64(30); x *= M3; x ^= x >> np.uint64(27); x *= M4; x ^= x >> np.uint64(31)
    mask[(x % np.uint64(C)).astype(np.int64)] = False
    pairs.append(re.search(r'first2_mega_(\d+_\d+)', f).group(1))
rem = np.nonzero(mask)[0]
msg = f'cap: {len(files)} | seed: {nseed:,} | ve bi loai: {C-len(rem):,} | ve con lai cho ky {nxt}: {len(rem):,} / {C:,}'
print(msg)
open(f've_con_lai_mega_summary_{nxt}.txt', 'w').write(msg + '\n')
if len(rem) <= maxl:
    T = [np.array([comb(i, k) if i >= k else 0 for i in range(46)], dtype=np.int64) for k in range(7)]
    r = rem.copy(); cols = []
    for k in range(6, 0, -1):
        xx = np.searchsorted(T[k], r, side='right') - 1
        cols.append(xx + 1); r = r - T[k][xx]
    A = np.sort(np.stack(cols, 1), axis=1)
    with open(f've_con_lai_mega_{nxt}.txt', 'w') as o:
        for row in A: o.write('-'.join(f'{v:02d}' for v in row) + '\n')
    print(f'da ghi ve_con_lai_mega_{nxt}.txt')
