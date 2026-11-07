#!/usr/bin/env python3
"""Doi chieu ve du doan (ve_con_lai/con_lai_<ky>.txt, ve_con_lai/1_2_seed_<ky>.txt) voi ket qua that trong data/all.csv.
Ghi: ve_trung/ve_trung_<ky>.txt (ve trong danh sach trung >= 3 so chinh), ve_trung/doi_chieu.jsonl (log may), ve_trung/doi_chieu.txt (de doc + tong ket).
Moi ky chi doi chieu 1 lan (theo doi_chieu.jsonl).
THEM: doi chieu MUC 1 / MUC 2 THEO TUNG CAP voi cac cap seed (inverse/first2_*.txt.gz, chi cap co d2 < ky, USE_PAIRS cap moi nhat): luu ve_trung/muc_trung_<ky>.txt
(ve muc 1/2 trung >= MIN_MATCH so chinh + ve J1 trung dung + cap/seed sinh ra no) va muc_doi_chieu.jsonl/.txt."""
import os, re, json, glob
import lotto_common as LC
N = 324632 * 12
CSV = os.environ.get('CSV', 'data/all.csv'); OUT = 've_trung'
R = LC.load_all_actual_results(CSV)
os.makedirs(OUT, exist_ok=True)
logf = f'{OUT}/doi_chieu.jsonl'
rows = [json.loads(l) for l in open(logf)] if os.path.exists(logf) else []
done = {r['ky'] for r in rows}

def parse(path):
    out = []
    if not os.path.exists(path): return out
    for l in open(path):
        l = l.strip()
        if not l or l.startswith('#'): continue
        m = re.match(r'^([\d-]+) \+ (\d+)', l)
        if m: out.append((frozenset(int(x) for x in m.group(1).split('-')), int(m.group(2)), m.group(1) + ' + ' + m.group(2)))
    return out

def label(m, sp): return f'{m}' + ('+DB' if sp else '')
for D in sorted(R):
    if D in done: continue
    f1, f2 = f've_con_lai/con_lai_{D}.txt', f've_con_lai/1_2_seed_{D}.txt'
    if not (os.path.exists(f1) or os.path.exists(f2)): continue
    nums, sp, date = R[D]
    res = '-'.join(f'{x:02d}' for x in sorted(nums)) + f' + {sp:02d}'
    rec = {'ky': D, 'ngay': date, 'ket_qua': res}
    hits = []
    for name, path in (('con_lai', f1), ('1_2_seed', f2)):
        L = parse(path); rec[name] = len(L)
        j1 = False
        for n, s, txt in L:
            m = len(n & nums)
            if m == 5 and s == sp: j1 = True
            if m >= 3: hits.append((name, txt, label(m, s == sp)))
        rec[name + '_J1'] = j1
        rec[name + '_hit3'] = sum(1 for h in hits if h[0] == name)
    rows.append(rec)
    if hits:
        with open(f'{OUT}/ve_trung_{D}.txt', 'w') as o:
            o.write(f'# Ky {D} ({date}) ket qua {res}: ve du doan trung >= 3 so chinh\n# danh sach | ve | muc (so chinh+DB)\n')
            for h in hits: o.write(' | '.join(h) + '\n')
with open(logf, 'w') as o:
    for r in rows: o.write(json.dumps(r, ensure_ascii=False) + '\n')
with open(f'{OUT}/doi_chieu.txt', 'w') as o:
    o.write('# ky | ngay | ket qua | con_lai (so ve, ve J1 trong danh sach?, so ve trung >=3 so) | 1_2_seed (nhu tren)\n')
    for r in rows:
        c = lambda k: f"{r.get(k,0)} ve, J1={'CO' if r.get(k+'_J1') else 'khong'}, >=3 so: {r.get(k+'_hit3',0)}"
        o.write(f"{r['ky']} | {r['ngay']} | {r['ket_qua']} | con_lai: {c('con_lai')} | 1_2_seed: {c('1_2_seed')}\n")
    n = len(rows)
    if n:
        s = sum(1 for r in rows if r.get('con_lai_J1')); e = sum(r.get('con_lai', 0) for r in rows) / N
        o.write(f"\nTONG KET {n} ky: ve J1 nam trong danh sach con_lai {s} ky (ky vong ngau nhien ~{e:.4f} ky)\n")
print(f'da doi chieu {n if rows else 0} ky (moi: {len(rows) - len(done)})')


# ======================= MUC 1 / MUC 2 THEO TUNG CAP: LUU VE TRUNG =======================
import numpy as np, pandas as pd
USE = int(os.environ.get('USE_PAIRS') or 47); MINM = int(os.environ.get('MIN_MATCH') or 4); LAST = int(os.environ.get('MUC_LAST') or 3)
C = 324632
M1 = np.uint64(0x9E3779B97F4A7C15); M2 = 0xD1B54A32D192ED03; M3 = np.uint64(0xBF58476D1CE4E5B9); M4 = np.uint64(0x94D049BB133111EB)
def _mix(x):
    x = x ^ (x >> np.uint64(30)); x = x * M3; x = x ^ (x >> np.uint64(27)); x = x * M4; return x ^ (x >> np.uint64(31))
def _tid(s, d):
    with np.errstate(over='ignore'):
        m = _mix(s * M1 + np.uint64((d * M2) & ((1 << 64) - 1)))
        return (m % np.uint64(C)).astype(np.int64) * 12 + (_mix(m) % np.uint64(12)).astype(np.int64)
_PC = np.array([bin(i).count('1') for i in range(4096)], dtype=np.int8)
def _pop(a): return _PC[a & np.uint64(4095)] + _PC[(a >> np.uint64(12)) & np.uint64(4095)] + _PC[(a >> np.uint64(24)) & np.uint64(4095)]
mlog = f'{OUT}/muc_doi_chieu.jsonl'
mrows = [json.loads(l) for l in open(mlog)] if os.path.exists(mlog) else []
mdone = {r['ky'] for r in mrows}
pf = []
for f in glob.glob('inverse/first2_*_*.txt.gz'):
    a, b = [int(x) for x in re.search(r'first2_(\d+)_(\d+)', f).groups()]; pf.append((a, b, f))
lutarr = None
for D in sorted(R)[-LAST:]:
    if D in mdone: continue
    use = sorted([p for p in pf if p[1] < D], key=lambda p: -p[0])[:USE]       # chi cap da biet TRUOC ky D, USE cap moi nhat
    if not use: continue
    if lutarr is None: lutarr = np.array(LC.build_rank_to_mask(LC.build_binom()), dtype=np.uint64)
    nums, sp, date = R[D]; am = np.uint64(sum(1 << (x - 1) for x in nums))
    rk = sorted(nums)
    res = '-'.join(f'{x:02d}' for x in rk) + f' + {sp:02d}'
    lines = []; per = []
    for a, b, f in sorted(use):
        s = pd.read_csv(f, sep=' ', header=None, usecols=[0], dtype={0: np.uint64})[0].to_numpy()
        t = _tid(s, D); c = np.bincount(t, minlength=C * 12)
        idx = np.flatnonzero((c == 1) | (c == 2))
        mt = _pop(lutarr[idx // 12] & am); ok = mt >= MINM
        sel = idx[ok]; msel = mt[ok]
        n1 = int((c[idx] == 1).sum()); n2 = int((c[idx] == 2).sum())
        h3 = int((mt >= 3).sum())
        per.append({'cap': f'{a}:{b}', 'muc1': n1, 'muc2': n2, 'hit3': h3, 'hit_min': int(len(sel))})
        if len(sel):
            m = np.isin(t, sel); ts, ss = t[m], s[m]
            for v, mm in zip(sel, msel):
                sd = ss[ts == v]; spm = (int(v) % 12 + 1 == sp)
                mk_ = lutarr[int(v) // 12]; txt = '-'.join(f'{x:02d}' for x in range(1, 36) if int(mk_) >> (x - 1) & 1) + f' + {int(v) % 12 + 1:02d}'
                lines.append(f'{a}:{b} | muc{int(c[v])} | {txt} | {int(mm)} so chinh' + ('+DB' if spm else '') + ' | seed ' + ','.join(str(int(x)) for x in sd))
    with open(f'{OUT}/muc_trung_{D}.txt', 'w') as o:
        o.write(f'# Ky {D} ({date}) ket qua {res}: ve MUC 1 / MUC 2 (tinh rieng tung cap, {len(use)} cap moi nhat co d2 < {D}) trung >= {MINM} so chinh\n# cap | muc | ve | khop | seed\n')
        for l in lines: o.write(l + '\n')
    rec = {'ky': D, 'ngay': date, 'ket_qua': res, 'so_cap': len(use), 'min_match': MINM, 'tong_ve_luu': len(lines),
           'muc1': sum(p['muc1'] for p in per), 'muc2': sum(p['muc2'] for p in per), 'hit3': sum(p['hit3'] for p in per),
           'J1': sum(1 for l in lines if '| 5 so chinh+DB |' in l), 'theo_cap': per}
    mrows.append(rec)
with open(mlog, 'w') as o:
    for r in mrows: o.write(json.dumps(r, ensure_ascii=False) + '\n')
with open(f'{OUT}/muc_doi_chieu.txt', 'w') as o:
    o.write('# ky | ngay | ket qua | so cap | ve muc1 | ve muc2 | ve trung >=3 so | ve luu (>=MIN_MATCH so) | J1 (5 so+DB)\n')
    for r in mrows: o.write(f"{r['ky']} | {r['ngay']} | {r['ket_qua']} | {r['so_cap']} | {r['muc1']:,} | {r['muc2']:,} | {r['hit3']:,} | {r['tong_ve_luu']} | {r['J1']}\n")
print(f'muc doi chieu: {len(mrows)} ky (moi: {len(mrows) - len(mdone)})')
