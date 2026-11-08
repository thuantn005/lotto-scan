#!/usr/bin/env python3
"""Doi chieu 100 ve du doan (du_doan/<game>_<ky>.txt) voi ket qua that, LUU VE TRUNG. Chi doi chieu moi ky 1 lan.
Luu: ve_trung/<game>_<ky>.txt (cac ve trung >= MIN_MATCH so chinh, mac dinh 3) + ve_trung/tong_ket_<game>.txt|.jsonl (moi ky 1 dong).
  python3 luu_ve_trung.py            (xu ly ca lotto535 va mega; chi doi chieu LAST ky cuoi, mac dinh 5)"""
import os, csv, json, re, glob
from math import comb
MINM = int(os.environ.get('MIN_MATCH') or 3); LAST = int(os.environ.get('SAVE_LAST') or 5)
def load(game):
    R = {}
    f = 'data/all.csv' if game == 'lotto535' else 'data/mega_all.csv'
    if not os.path.exists(f): return R
    for r in csv.DictReader(open(f, encoding='utf-8', newline='')):
        if not (r.get('draw_id') or '').isdigit() or (game == 'lotto535' and r.get('product') != 'lotto535'): continue
        j = json.loads(r['result_json']); R[int(r['draw_id'])] = (set(j['numbers']), (j.get('special_numbers') or [0])[0], r['draw_date'])
    return R
# xac suat ngau nhien cua 1 ve trung >= 3 so chinh
P3 = {'lotto535': (comb(5, 3) * comb(30, 2) + comb(5, 4) * 30 + 1) / comb(35, 5), 'mega': (comb(6, 3) * comb(39, 3) + comb(6, 4) * comb(39, 2) + comb(6, 5) * 39 + 1) / comb(45, 6)}
os.makedirs('ve_trung', exist_ok=True)
for game in ('lotto535', 'mega'):
    R = load(game); lf = f've_trung/tong_ket_{game}.jsonl'
    log = [json.loads(l) for l in open(lf)] if os.path.exists(lf) else []; done = {r['ky'] for r in log}
    for D in sorted(R)[-LAST:]:
        f = f'du_doan/{game}_{D}.txt'
        if D in done or not os.path.exists(f): continue
        nums, sp, date = R[D]; tickets = []
        for l in open(f):
            if l.startswith('#') or not l.strip(): continue
            p = [x.strip() for x in l.rstrip('\n').split(' | ')]
            main = {int(x) for x in re.findall(r'\d+', p[0].split('+')[0])}; dbm = '+' in p[0] and int(p[0].split('+')[1]) == sp
            tickets.append((p[0], p[1] if len(p) > 1 else '', p[2] if len(p) > 2 else '', len(main & nums), dbm))
        tally = {}
        for t in tickets: tally[(t[3], t[4] and game == 'lotto535')] = tally.get((t[3], t[4] and game == 'lotto535'), 0) + 1
        win = sorted([t for t in tickets if t[3] >= MINM], key=lambda t: (-t[3], not t[4]))
        res = '-'.join(f'{x:02d}' for x in sorted(nums)) + (f' + {sp:02d}' if game == 'lotto535' else '')
        rec = {'ky': D, 'ngay': date, 'ket_qua': res, 'so_ve': len(tickets), 'trung_ge3': sum(1 for t in tickets if t[3] >= 3),
               'trung_ge4': sum(1 for t in tickets if t[3] >= 4), 'trung_5_hoac_6': sum(1 for t in tickets if t[3] >= (5 if game == 'lotto535' else 6)),
               'J1': sum(1 for t in tickets if (t[3] == 5 and t[4]) ) if game == 'lotto535' else sum(1 for t in tickets if t[3] == 6),
               'ky_vong_ge3': round(len(tickets) * P3[game], 2)}
        log.append(rec)
        with open(f've_trung/{game}_{D}.txt', 'w') as o:
            o.write(f'# Ky {D} ({date}) ket qua {res} | {len(tickets)} ve du doan | trung >=3 so: {rec["trung_ge3"]} (ky vong ngau nhien ~{rec["ky_vong_ge3"]}) | >=4: {rec["trung_ge4"]} | J: {rec["J1"]}\n# ve | nguon | chi tiet | so chinh khop\n')
            for t in win: o.write(f'{t[0]} | {t[1]} | {t[2]} | {t[3]}' + (' +DB' if t[4] and game == 'lotto535' else '') + '\n')
    log.sort(key=lambda r: r['ky'])
    with open(lf, 'w') as o:
        for r in log: o.write(json.dumps(r, ensure_ascii=False) + '\n')
    with open(f've_trung/tong_ket_{game}.txt', 'w') as o:
        o.write('# ky | ngay | ket qua | so ve | trung >=3 (ky vong) | >=4 | 5/6 so | J (5 so+DB lotto, 6 so mega)\n')
        for r in log: o.write(f"{r['ky']} | {r['ngay']} | {r['ket_qua']} | {r['so_ve']} | {r['trung_ge3']} ({r['ky_vong_ge3']}) | {r['trung_ge4']} | {r['trung_5_hoac_6']} | {r['J1']}\n")
    print(f'{game}: {len(log)} ky da doi chieu (moi {len(log) - len(done)})')
# giu lai chi tiet ve trung moi ky (nho); khong gioi han
