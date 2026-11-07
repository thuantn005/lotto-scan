#!/usr/bin/env python3
"""Doi chieu ve MEGA con lai (ve_con_lai_mega/ve_con_lai_mega_<ky>.txt) voi ket qua that trong data/mega_all.csv.
Luu: ve_trung_mega/ve_trung_mega_<ky>.txt (ve trung >= MIN_MATCH so, mac dinh 4), ve_trung_mega/doi_chieu_mega.jsonl|.txt (moi ky 1 dong, chi doi chieu 1 lan).
Chi doi chieu MEGA_LAST (3) ky cuoi. Neu khong co file danh sach (con lai > 400000 ve) thi bo qua ky do."""
import os, csv, json
import numpy as np
CSV = os.environ.get('CSV', 'data/mega_all.csv'); OUT = 've_trung_mega'
MINM = int(os.environ.get('MIN_MATCH') or 4); LAST = int(os.environ.get('MEGA_LAST') or 3)
R = {}
for r in csv.DictReader(open(CSV, encoding='utf-8', newline='')):
    if (r.get('draw_id') or '').isdigit():
        R[int(r['draw_id'])] = (sorted(json.loads(r['result_json'])['numbers']), r['draw_date'])
os.makedirs(OUT, exist_ok=True)
logf = f'{OUT}/doi_chieu_mega.jsonl'
rows = [json.loads(l) for l in open(logf)] if os.path.exists(logf) else []
done = {r['ky'] for r in rows}
for D in sorted(R)[-LAST:]:
    f = f've_con_lai_mega/ve_con_lai_mega_{D}.txt'
    if D in done or not os.path.exists(f): continue
    nums, date = R[D]
    A = np.array([[int(x) for x in l.split('-')] for l in open(f) if l.strip() and not l.startswith('#')], dtype=np.int16)
    m = np.isin(A, np.array(nums, dtype=np.int16)).sum(axis=1)
    res = '-'.join(f'{x:02d}' for x in nums)
    rec = {'ky': D, 'ngay': date, 'ket_qua': res, 've': int(len(A)), 'J': int((m == 6).sum()), 'hit5': int((m == 5).sum()),
           'hit4': int((m == 4).sum()), 'hit3': int((m == 3).sum()), 'min_match': MINM}
    rows.append(rec)
    sel = np.flatnonzero(m >= MINM)
    with open(f'{OUT}/ve_trung_mega_{D}.txt', 'w') as o:
        o.write(f'# Ky {D} ({date}) ket qua {res}: ve con_lai trung >= {MINM} so (tong {len(A)} ve, J={rec["J"]}, 5 so={rec["hit5"]}, 4 so={rec["hit4"]}, 3 so={rec["hit3"]})\n# ve | so trung\n')
        for i in sel[np.argsort(-m[sel], kind='stable')]: o.write('-'.join(f'{x:02d}' for x in A[i]) + f' | {int(m[i])}\n')
with open(logf, 'w') as o:
    for r in rows: o.write(json.dumps(r, ensure_ascii=False) + '\n')
with open(f'{OUT}/doi_chieu_mega.txt', 'w') as o:
    o.write('# ky | ngay | ket qua | so ve con lai | J (6 so) | 5 so | 4 so | 3 so\n')
    for r in rows: o.write(f"{r['ky']} | {r['ngay']} | {r['ket_qua']} | {r['ve']:,} | {r['J']} | {r['hit5']} | {r['hit4']} | {r['hit3']}\n")
print(f'doi chieu Mega: {len(rows)} ky (moi: {len(rows) - len(done)})')
