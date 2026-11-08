#!/usr/bin/env python3
"""MUC cua seed = so LAN seed DA DU DOAN DUNG ve ket qua THAT (theo doi tung lan du doan) + du doan theo muc.
  python3 seed_levels.py GAME THU_MUC_GZ        GAME = lotto535 | mega
Dinh nghia:
  * Moi seed thuoc 1 cap (d1,d2). Ky d1, d2 la ky seed duoc CHON vi trung (trong mau, khong tinh la du doan).
  * 'Du doan' cua seed cho ky D (D > d2) = ve seed sinh ra cho ky D. Neu trung ve ket qua that cua ky D (Lotto: 5 so + DB; Mega: 6 so) -> du doan DUNG.
  * MUC = so ky D > d2 ma seed du doan dung. Muc 0 = chua tung dung (hau het seed); muc 1, 2, 3+ = da dung 1, 2, 3+ lan.
Moi lan chay:
  1) Nap seed muc >= 1 tu cot 'cac ky' cua gz (ky > d2 da trung luc quet) + state seed_state/.
  2) Voi MOI ky co ket qua chua xu ly (toi da LEVEL_LAST ky cuoi; dat lon de BACKFILL lan dau): quet TOAN BO seed (USE_PAIRS cap moi nhat, d2 < ky,
     cong seed da luu trong state) -> seed trung ky D duoc +1 muc. Ghi HO SO: truoc ky D, seed muc >=L co bao nhieu, bao nhieu dung ky D (so voi ngau nhien).
  3) Du doan ky tiep theo THEO MUC: ve_theo_muc/<game>_muc1|muc2|muc3_<ky>.txt (ve sinh tu seed muc dung 1, dung 2, 3 tro len).
State (nho, commit): seed_state/hits_<game>.tsv (seed \\t cap \\t cac ky du doan dung), levels_log_<game>.jsonl, ho_so_<game>.txt."""
import os, sys, re, glob, json, csv
import numpy as np, pandas as pd
from math import comb
game, gzdir = sys.argv[1], sys.argv[2]
LOTTO = game == 'lotto535'
USE = int(os.environ.get('USE_PAIRS') or 47); LAST = int(os.environ.get('LEVEL_LAST') or 3); MAXLEV = int(os.environ.get('MAX_LEVEL_FILE') or 20000)
MOD = 324632 if LOTTO else 8145060; CT = MOD * 12 if LOTTO else MOD
M1 = np.uint64(0x9E3779B97F4A7C15); M2 = 0xD1B54A32D192ED03; M3 = np.uint64(0xBF58476D1CE4E5B9); M4 = np.uint64(0x94D049BB133111EB)
def _mix(x):
    x = x ^ (x >> np.uint64(30)); x = x * M3; x = x ^ (x >> np.uint64(27)); x = x * M4; return x ^ (x >> np.uint64(31))
def tid(s, d):
    with np.errstate(over='ignore'):
        m = _mix(s * M1 + np.uint64((d * M2) & ((1 << 64) - 1))); r = (m % np.uint64(MOD)).astype(np.int64)
        return r * 12 + (_mix(m) % np.uint64(12)).astype(np.int64) if LOTTO else r
def rank_of(nums): return sum(comb(n - 1, i + 1) for i, n in enumerate(sorted(nums)))
def load_results():
    R = {}
    if LOTTO:
        for r in csv.DictReader(open('data/all.csv', encoding='utf-8', newline='')):
            if r.get('product') == 'lotto535' and (r.get('draw_id') or '').isdigit():
                j = json.loads(r['result_json']); R[int(r['draw_id'])] = (rank_of(j['numbers']) * 12 + j['special_numbers'][0] - 1, r['draw_date'])
    else:
        for r in csv.DictReader(open('data/mega_all.csv', encoding='utf-8', newline='')):
            if (r.get('draw_id') or '').isdigit():
                j = json.loads(r['result_json']); R[int(r['draw_id'])] = (rank_of(j['numbers']), r['draw_date'])
    return R
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
ST = 'seed_state'; os.makedirs(ST, exist_ok=True)
WRITE_FILES = os.environ.get('LEVEL_FILES', '0') == '1'
hf, lf, pf_ = f'{ST}/hits_{game}.tsv', f'{ST}/levels_log_{game}.jsonl', f'{ST}/ho_so_{game}.txt'
preds = {}; pair_of = {}          # seed -> set(ky du doan dung) ; seed -> d2 cua cap
if os.path.exists(hf):
    for l in open(hf):
        a = l.rstrip('\n').split('\t')
        if len(a) == 3: pair_of[int(a[0])] = int(a[1].split('_')[1]); preds[int(a[0])] = {int(x) for x in a[2].split(',') if x}
log = [json.loads(l) for l in open(lf)] if os.path.exists(lf) else []
done = {r['ky'] for r in log}
pat = re.compile(r'first2_(?:mega_)?(\d+)_(\d+)\.txt\.gz$'); files = []
for f in glob.glob(os.path.join(gzdir, '*.txt.gz')):
    m = pat.search(f)
    if m: files.append((int(m.group(1)), int(m.group(2)), f))
files.sort(key=lambda p: -p[0])
if USE > 0: files = files[:USE]
pairname = {}
# 1) nap seed cua so + seed da du doan dung luc quet (ky > d2 trong cot 'cac ky')
Ss, Es = [], []
for a, b, f in files:
    d = pd.read_csv(f, sep=' ', header=None, usecols=[0, 1, 2], dtype={0: np.uint64, 1: np.int32, 2: str}, engine='c')
    s = d[0].to_numpy(); Ss.append(s); Es.append(np.full(len(s), b, dtype=np.int32))
    h = d[d[1] >= 3]
    for sd, ks in zip(h[0].to_numpy(), h[2].to_numpy()):
        post = {int(x) for x in str(ks).split(',') if x.strip().isdigit() and int(x) > b}
        if post: preds.setdefault(int(sd), set()).update(post); pair_of[int(sd)] = b; pairname[int(sd)] = f'{a}_{b}'
    del d
S = np.concatenate(Ss) if Ss else np.array([], dtype=np.uint64); E = np.concatenate(Es) if Es else np.array([], dtype=np.int32); del Ss, Es
R = load_results()
todo = [D for D in sorted(R)[-LAST:] if D not in done] if LAST > 0 else []
for D in todo:
    actual, date = R[D]
    if len(S) == 0: break
    elig = E < D                                  # chi seed cua cap da biet TRUOC ky D
    if not elig.any(): continue
    hit_seeds = set(int(x) for x in S[elig][tid(S[elig], D) == actual])
    old = [sd for sd in preds if sd not in hit_seeds and pair_of.get(sd, 10**9) < D]
    if old:
        arr = np.array(old, dtype=np.uint64); hit_seeds.update(int(x) for x in arr[tid(arr, D) == actual])
    before = {sd: {k for k in ks if k < D} for sd, ks in preds.items()}
    nel = int(elig.sum())
    rec = {'ky': D, 'ngay': date, 'seed_du_doan': nel, 'dung_ky_nay': len(hit_seeds), 'ky_vong_ngau_nhien': round(nel / CT, 2), 'theo_muc': {}}
    for L in (1, 2, 3):
        pool = [sd for sd, ks in before.items() if len(ks) >= L and pair_of.get(sd, 10**9) < D]
        rec['theo_muc'][f'>={L}'] = {'seed': len(pool), 'dung_ky_nay': sum(1 for sd in pool if sd in hit_seeds), 'ky_vong': round(len(pool) / CT, 4)}
    for sd in hit_seeds:
        preds.setdefault(sd, set()).add(D)
        if sd not in pair_of:
            i = np.flatnonzero(S == np.uint64(sd))
            pair_of[sd] = int(E[i[0]]) if len(i) else 0
    log.append(rec)
# luu state (chi seed muc >= 1)
log.sort(key=lambda r: r['ky'])
inv = {}
for a, b, f in files: inv[b] = a
with open(hf, 'w') as o:
    for sd in sorted(preds):
        if preds[sd]: o.write(f"{sd}\t{inv.get(pair_of.get(sd, 0), 0)}_{pair_of.get(sd, 0)}\t{','.join(map(str, sorted(preds[sd])))}\n")
with open(lf, 'w') as o:
    for r in log: o.write(json.dumps(r, ensure_ascii=False) + '\n')
with open(pf_, 'w') as o:
    o.write(f'# HO SO MUC SEED ({game}). Muc = so lan seed du doan DUNG ket qua that (ky > d2 cua cap). Moi ky: seed muc>=L truoc ky do co bao nhieu, dung ky do bao nhieu (vong = ky vong NGAU NHIEN = so seed / {CT:,})\n')
    for r in log:
        t = ' | '.join(f"muc>={k[2:]}: {v['dung_ky_nay']}/{v['seed']} (vong {v['ky_vong']})" for k, v in r['theo_muc'].items())
        o.write(f"ky {r['ky']} {r['ngay']} | tat ca: {r['dung_ky_nay']}/{r['seed_du_doan']:,} (vong {r['ky_vong_ngau_nhien']}) | {t}\n")
# 3) du doan ky tiep theo THEO MUC
N = max(R) + 1; lv = {}
if WRITE_FILES: os.makedirs('ve_theo_muc', exist_ok=True)
for sd, ks in preds.items():
    n = len({k for k in ks if k < N})
    if n >= 1: lv.setdefault(min(n, 3), []).append(sd)
for pre in (glob.glob(f've_theo_muc/{game}_muc*_*.txt') if WRITE_FILES else []):
    if not pre.endswith(f'_{N}.txt'): os.remove(pre)
for L in ((1, 2, 3) if WRITE_FILES else ()):
    sds = sorted(lv.get(L, [])); name = f've_theo_muc/{game}_muc{L}_{N}.txt'
    t = tid(np.array(sds, dtype=np.uint64), N) if sds else np.array([], dtype=np.int64)
    with open(name, 'w') as o:
        o.write(f'# Ky {N}: ve sinh tu seed muc {"3 tro len" if L == 3 else "dung " + str(L)} = da du doan DUNG {"3+" if L == 3 else L} lan ({len(sds)} seed, {len(set(t.tolist()))} ve phan biet).\n# ve | seed | muc | cac ky da du doan dung\n')
        for sd, v in list(zip(sds, t))[:MAXLEV]:
            ks = sorted(k for k in preds[sd] if k < N); o.write(f'{dec(v)} | {sd} | {len(ks)} | {",".join(map(str, ks))}\n')
print(f'{game}: {len(log)} ky ho so (moi {len(todo)}) | seed muc>=1: {sum(len(v) for v in lv.values())} (1:{len(lv.get(1,[]))} 2:{len(lv.get(2,[]))} 3+:{len(lv.get(3,[]))}) | du doan ky {N}')
