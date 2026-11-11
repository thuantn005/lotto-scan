#!/usr/bin/env python3
"""Chon DUNG 100 ve du doan cho ky tiep theo (Lotto 5/35 hoac Mega 6/45) va luu vao du_doan/<game>_<ky>.txt.
  python3 du_doan_100.py GAME THU_MUC_GZ        GAME = lotto535 | mega      (so ve: env TARGET_N, mac dinh 100)
Thu tu uu tien (dedupe, du 100 thi dung):
  1) THEO TUNG CAP, CHIA THEO SO LIEU seed_state/hits_<game>.tsv (SPLIT=prob, mac dinh; SPLIT=equal de chia deu): so ve cua cap ~ (so seed muc>=1 cua cap trong tsv) / (seed cua cap x ky da qua sau d2).
     CHON SEED THEO MUC: chi lay ve do DUNG MUC seed cua cap cung sinh ra (env MUC, mac dinh 1; MUC=0 de khong loc theo muc). Thong ke muc (47 cap, moi ky sau cap toi ky 1000): ve trung that o muc 1 = 1,07x ngau nhien (khong co y nghia thong ke).
     Trong cap lay NGAU NHIEN (co dinh theo ky) trong cac seed CHI HIT DUNG 2 KY (cap d1,d2) thoa muc tren; seed trung them bat ky ky nao sau d2 (vd 995) bi LOAI - kiem tra truc tiep voi ket qua that
     (gz + scan_state cho so ky luc quet). Ve trung giua cac cap -> lay ve ke tiep cua cap. Env PER_PAIR (150) = so ung vien du phong/cap.
  2) neu thieu: ve CON LAI (khong seed nao tren cac cap dang dung sinh ra); lay mau co dinh theo ky (rng seed = ky)
  3) neu van thieu: ve it seed nhat (do boi 1 seed, roi 2 seed, ...)
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
def _rank(nums): return sum(comb(n - 1, i + 1) for i, n in enumerate(sorted(nums)))
RES = {}                                         # ky -> id ve KET QUA THAT (de loai seed da trung them sau cap)
for r in csv.DictReader(open(csvf, encoding='utf-8', newline='')):
    if (r.get('draw_id') or '').isdigit() and (not LOTTO or r.get('product') == 'lotto535'):
        try:
            j = json.loads(r['result_json']); rk = _rank(j['numbers'])
            RES[int(r['draw_id'])] = rk * 12 + int(j['special_numbers'][0]) - 1 if LOTTO else rk
        except Exception: pass
SCAN_N = {}                                      # cap -> so ky luc quet (gz chi biet hit toi ky do)
for fn in glob.glob('scan_state/first2_*.txt'):
    mm = re.search(r'first2_(?:mega_)?(\d+)_(\d+)\.txt$', fn)
    if mm:
        for l in open(fn, encoding='utf-8', errors='ignore'):
            q = re.search(r'tren (\d+) ky', l)
            if l.startswith('Phan bo so hit') and q: SCAN_N[(int(mm.group(1)), int(mm.group(2)))] = int(q.group(1)); break
nlate = 0
pat = re.compile(r'first2_(?:mega_)?(\d+)_(\d+)\.txt\.gz$'); files = []
for f in glob.glob(os.path.join(gzdir, '*.txt.gz')):
    m = pat.search(f)
    if m: files.append((int(m.group(1)), int(m.group(2)), f))
files.sort(key=lambda p: -p[0])
if USE > 0: files = files[:USE]
cnt = np.zeros(CT, dtype=np.int32); nseed = 0; nseed2 = 0
PERPAIR = int(os.environ.get('PER_PAIR') or 150); percand = []
later = np.array([], dtype=np.uint64)   # seed da trung them sau d2 (hit >= 3) theo seed_state
MUC = int(os.environ.get('MUC') or 1); tsvn = {}   # tsvn: cap -> so seed muc>=1 trong hits tsv (so lieu chia ve)
hf0 = f'seed_state/hits_{game}.tsv'
if os.path.exists(hf0):
    later = np.array([int(l.split('\t')[0]) for l in open(hf0) if l.count('\t') == 2 and l.rstrip('\n').split('\t')[2].strip()], dtype=np.uint64)
    for l in open(hf0):
        a_ = l.rstrip('\n').split('\t')
        if len(a_) == 3 and a_[2].strip(): tsvn[a_[1]] = tsvn.get(a_[1], 0) + 1
for a, b, f in files:
    d = pd.read_csv(f, sep=' ', header=None, usecols=[0, 1], dtype={0: np.uint64, 1: np.int32}, engine='c')
    s = d[0].to_numpy(); h = d[1].to_numpy(); t = tid(s, N)
    nseed += len(s); cp = np.bincount(t, minlength=CT); cnt += cp.astype(np.int32)   # cp = so seed CUA CAP sinh tung ve (muc)
    nl_pair = 0
    m2 = h == 2                                  # seed chi hit dung 2 ky (cap d1,d2) tinh den luc quet
    if len(later): m2 &= ~np.isin(s, later)
    for D in range(max(SCAN_N.get((a, b), b), b) + 1, N):          # seed TRUNG THEM ky nao tu sau luc quet toi nay (vd 995) -> LOAI
        if D in RES and m2.any():
            ix_ = np.flatnonzero(m2); hit_ = tid(s[ix_], D) == RES[D]; m2[ix_[hit_]] = False; nlate += int(hit_.sum()); nl_pair += int(hit_.sum())
    ix = np.flatnonzero(m2); nseed2 += len(ix)
    if MUC > 0: ix = ix[cp[t[ix]] == MUC]          # CHON SEED THEO MUC: chi ve do dung MUC seed cua cap sinh ra
    if len(ix):                                    # ung vien RIENG CUA CAP nay: lay NGAU NHIEN deu trong cac seed hit dung 2 ky (giong cach seed len hit 3: roi ngau nhien)
        rg = np.random.default_rng((N * 1000003 + a * 1009 + b) & 0xFFFFFFFF)
        pk = rg.choice(ix, size=min(len(ix), PERPAIR), replace=False)
        nconv = tsvn.get(f'{a}_{b}', 0) if tsvn else int((h >= 3).sum()) + nl_pair   # so seed muc>=1 cua cap (theo hits tsv)
        percand.append((f'{a}_{b}', [(int(t[q]), len(ix), int(s[q])) for q in pk], nconv, nconv / (len(s) * max(1, N - 1 - b))))   # so seed cua cap da len >= 3 hit (luc quet + trung them sau do)
chosen = []; used = set()
nrej = 0
def valid(sd, pr):                                 # KIEM TRA CUOI: seed sinh ve phai hit DUNG 2 ky (d1,d2 cua cap) tren TOAN BO ket qua that; hit 3, 4.. ky -> bo
    global nrej
    if not sd: return True
    a_, b_ = (int(x) for x in pr.split('_')); arr = np.array([sd], dtype=np.uint64)
    hits = {D for D, r_ in RES.items() if D < N and int(tid(arr, D)[0]) == r_}
    if hits == {x for x in (a_, b_) if x in RES}: return True     # ky khong co trong csv thi khong kiem tra duoc ky do
    nrej += 1; return False
def add(v, src, det):
    if len(chosen) < NEED and int(v) not in used: used.add(int(v)); chosen.append((int(v), src, det))
# 1) CHON THEO TUNG CAP: vong 1 lay ve dung dau cua moi cap (cap moi nhat truoc), vong 2 lay ve thu 2 cua moi cap, ... den du NEED
# tieu chi cap: chi cap DA CO seed muc>=1 trong hits tsv, ti le cao nhat truoc, bang nhau thi cap moi hon; PAIR_CRIT=all de dung moi cap
if os.environ.get('PAIR_CRIT', 'conv') == 'conv': percand = [x for x in percand if x[2] > 0]      # CHI lay cap DA CO seed len >= 3 hit
percand.sort(key=lambda x: (-x[3], -int(x[0].split('_')[0])) if os.environ.get('PAIR_CRIT', 'conv') == 'conv' else -int(x[0].split('_')[0]))
# CHIA DEU: moi cap cung so ve (NEED // so cap, phan du chia cho cac cap moi nhat); ve trung giua cac cap thi lay ve ke tiep cua cap do
P = len(percand)
if P:
    # CHIA THEO XAC SUAT: ti le cua cap = so seed len >= 3 hit / (so seed cua cap x so ky da qua sau d2); so ve cua cap ~ ti le (lam tron lon nhat, tong = NEED)
    if os.environ.get('SPLIT', 'prob') == 'prob' and sum(x[3] for x in percand) > 0:
        tw = sum(x[3] for x in percand); raw = [NEED * x[3] / tw for x in percand]
        quota = [int(r_) for r_ in raw]
        for k in sorted(range(P), key=lambda k: -(raw[k] - quota[k]))[:NEED - sum(quota)]: quota[k] += 1
    else:
        base, extra = divmod(NEED, P); quota = [base + (1 if k < extra else 0) for k in range(P)]
    for k, (pr, lst, nconv, rate) in enumerate(percand):
        q = quota[k]; got = 0
        for v, nsd, sd in lst:
            if got >= q: break
            if v not in used and valid(sd, pr): add(v, 'seed2hit', f'cap {pr} (da co {nconv} seed muc>=1, ti le {rate * CT:.2f}x ngau nhien, {q} ve): muc {MUC}, ngau nhien trong {nsd:,} seed hit dung 2 ky (seed {sd})'); got += 1
    for rd in range(PERPAIR):                      # con thieu (do trung ve) -> bo sung vong tron
        if len(chosen) >= NEED: break
        for pr, lst, nconv, rate in percand:
            if rd < len(lst) and lst[rd][0] not in used and valid(lst[rd][2], pr): add(lst[rd][0], 'seed2hit', f'cap {pr}: ngau nhien trong {lst[rd][1]:,} seed hit dung 2 ky cua cap (seed {lst[rd][2]})')
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
    o.write(f'# Ky {N} ({game}): {len(chosen)} ve du doan | {len(files)} cap, {nseed:,} seed ({nseed2:,} seed hit dung 2 ky, loai {nlate} seed trung them, {nrej} seed bi loai o buoc kiem tra cuoi) | ve con lai (khong seed nao sinh): {n_rem_total:,}\n')
    o.write(f'# nguon: seed 2 hit {n_muc} | con_lai {n_rem} | it_seed {len(chosen) - n_muc - n_rem}. Moi ve chi co xac suat ngau nhien 1/{CT:,}.\n# ve | nguon | chi tiet\n')
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
