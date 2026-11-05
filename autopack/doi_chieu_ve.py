#!/usr/bin/env python3
"""Doi chieu ve du doan (ve_con_lai/con_lai_<ky>.txt, ve_con_lai/1_2_seed_<ky>.txt) voi ket qua that trong data/all.csv.
Ghi: ve_trung/ve_trung_<ky>.txt (ve trong danh sach trung >= 3 so chinh), ve_trung/doi_chieu.jsonl (log may), ve_trung/doi_chieu.txt (de doc + tong ket).
Moi ky chi doi chieu 1 lan (theo doi_chieu.jsonl)."""
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
