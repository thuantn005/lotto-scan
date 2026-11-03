#!/usr/bin/env python3
"""Loai ve Mega 6/45 cho ky tiep theo bang cac seed inverse (inverse_mega/first2_mega_*.txt.gz).
Dung: python3 ve_con_lai_mega.py NEXT_DRAW_ID [MAX_LIST=300000]
Ghi ve_con_lai_mega_<ky>.txt khi so ve con lai <= MAX_LIST (neu lon hon chi in so ve)."""
import sys, gzip, glob
import numpy as np
from math import comb
from mega_lib import C, M1, M2
nxt = int(sys.argv[1]); maxl = int(sys.argv[2]) if len(sys.argv) > 2 else 300000
S = set()
for f in sorted(glob.glob('inverse_mega/first2_mega_*_*.txt.gz')):
    with gzip.open(f, 'rt') as g:
        for l in g:
            p = l.split()
            if len(p) >= 3 and p[0].isdigit(): S.add(int(p[0]))
s = np.array(sorted(S), dtype=np.uint64)
M3 = np.uint64(0xBF58476D1CE4E5B9); M4 = np.uint64(0x94D049BB133111EB)
with np.errstate(over='ignore'):
    x = s * np.uint64(M1) + np.uint64((nxt * M2) & ((1 << 64) - 1))
    x ^= x >> np.uint64(30); x *= M3; x ^= x >> np.uint64(27); x *= M4; x ^= x >> np.uint64(31)
rk = (x % np.uint64(C)).astype(np.int64)
mask = np.ones(C, bool); mask[rk] = False
rem = np.nonzero(mask)[0]
print(f'seed: {len(s):,} | ve bi loai: {C-len(rem):,} | ve con lai cho ky {nxt}: {len(rem):,} / {C:,}')
if len(rem) <= maxl:
    T = [np.array([comb(i, k) if i >= k else 0 for i in range(46)], dtype=np.int64) for k in range(7)]
    r = rem.copy(); cols = []
    for k in range(6, 0, -1):
        xx = np.searchsorted(T[k], r, side='right') - 1      # lon nhat x: C(x,k) <= r
        cols.append(xx + 1); r = r - T[k][xx]
    A = np.sort(np.stack(cols, 1), axis=1)
    with open(f've_con_lai_mega_{nxt}.txt', 'w') as o:
        for row in A: o.write('-'.join(f'{v:02d}' for v in row) + '\n')
    print(f'da ghi ve_con_lai_mega_{nxt}.txt')
