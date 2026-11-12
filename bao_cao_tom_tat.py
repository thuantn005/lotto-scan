#!/usr/bin/env python3
"""BAO CAO TOM TAT MOI KY - Lotto 5/35 -> bao_cao/tom_tat_lotto535.txt (+ lich su bao_cao/lich_su_lotto535.jsonl, giu vinh vien).
Moi ky: con lai bao nhieu ve (% to hop), dung bao nhieu cap/seed (ke ca seed hit>=3 ky giu lai), 100 ve lay tu dau;
voi cac ky DA QUAY: ve trung that CON LAI hay BI LOAI (doi chieu), 100 ve trung bao nhieu.  python3 bao_cao_tom_tat.py"""
import os, re, glob, json
CT = 324632 * 12
os.makedirs('bao_cao', exist_ok=True); HF = 'bao_cao/lich_su_lotto535.jsonl'
hist = {}
if os.path.exists(HF):
    for l in open(HF):
        try: r = json.loads(l); hist[r['ky']] = r
        except Exception: pass
num = lambda x: int(x.replace(',', ''))
for f in glob.glob('du_doan/lotto535_*.txt'):          # header moi ky du doan -> lich su (idempotent)
    L = open(f, encoding='utf-8', errors='ignore').read().splitlines()[:3]
    h = L[0] if L else ''; g = L[1] if len(L) > 1 else ''
    m = re.match(r'# Ky (\d+) .*?\| (\d+) cap, ([\d,]+) seed.*?: ([\d,]+)\s*$', h)
    if not m: continue
    k34 = re.search(r'giu de loai: ([\d,]+)', g); ng = re.search(r'seed 2 hit (\d+) \| con_lai (\d+) \| it_seed (\d+)', g)
    ky = int(m.group(1)); rem = num(m.group(4))
    hist[ky] = {'ky': ky, 'con_lai': rem, 'ty_le': round(rem / CT, 4), 'so_cap': int(m.group(2)), 'so_seed': num(m.group(3)),
                'seed_hit34': num(k34.group(1)) if k34 else 0, 'nguon': {'seed': int(ng.group(1)), 'con_lai': int(ng.group(2)), 'it_seed': int(ng.group(3))} if ng else {}}
with open(HF, 'w') as o:
    for ky in sorted(hist): o.write(json.dumps(hist[ky], ensure_ascii=False) + '\n')
dc = {}
if os.path.exists('ve_trung/doi_chieu_con_lai.jsonl'):
    for l in open('ve_trung/doi_chieu_con_lai.jsonl'):
        try: r = json.loads(l); dc[r['ky']] = r
        except Exception: pass
tk = {}
if os.path.exists('ve_trung/tong_ket_lotto535.txt'):
    for l in open('ve_trung/tong_ket_lotto535.txt'):
        a = [x.strip() for x in l.split('|')]
        if len(a) >= 6 and a[0].isdigit():
            m = re.match(r'(\d+)', a[4]); tk[int(a[0])] = {'ngay': a[1], 'kq': a[2], 'sove': int(a[3]) if a[3].isdigit() else 100, 'tr3': int(m.group(1)) if m else 0, 'tr4': a[5]}
n34 = sum(1 for l in open('seed_state/keep34_lotto535.txt') if l.strip()) if os.path.exists('seed_state/keep34_lotto535.txt') else 0
npair = len(glob.glob('inverse/first2_*_*.txt.gz'))
out = ['BAO CAO TOM TAT LOTTO 5/35', f'to hop {CT:,} ve | kho seed hit>=3 ky giu vinh vien: {n34:,} seed | cap gz dang giu: {npair}', '']
if hist:
    ky = max(hist); r = hist[ky]; nx = ky
    out += [f'== KY DU DOAN GAN NHAT: {ky} ==',
            f"Ve con lai: {r['con_lai']:,} / {CT:,} ({r['con_lai'] / CT:.2%}) | bi loai: {CT - r['con_lai']:,} ({1 - r['con_lai'] / CT:.2%})",
            f"Nguon loai: {r['so_cap']} cap lien tiep ({r['so_seed']:,} seed) + {r['seed_hit34']:,} seed hit>=3 ky giu lai"]
    if r['nguon']: out.append(f"100 ve chon: {r['nguon'].get('con_lai', 0)} tu ve con lai, {r['nguon'].get('seed', 0)} tu seed hit, {r['nguon'].get('it_seed', 0)} it seed")
    out.append('')
out += ['== TUNG KY (moi nhat truoc) ==', 'ky | ngay | ve con lai (% to hop) | cap | ve THAT: con lai hay bi loai | 100 ve trung>=3 so']
rows = sorted(set(hist) | set(dc) | set(tk), reverse=True)
USE = int(os.environ.get('USE_PAIRS') or 4)
kc = ke = 0.0; nk = 0; pl = []; skipped = 0
for ky in rows:
    h = hist.get(ky); d = dc.get(ky); t = tk.get(ky)
    ngay = (t or {}).get('ngay') or (d or {}).get('ngay') or ''
    cl = f"{h['con_lai']:,} ({h['con_lai'] / CT:.1%})" if h else '-'
    cap = (h or {}).get('so_cap', (d or {}).get('so_cap', '-'))
    if d:
        st = 'CON LAI' if d['ve_that_con_lai'] else 'BI LOAI'
        if d['so_cap'] >= USE: nk += 1; kc += d['ve_that_con_lai']; ke += d['xs_con_lai_ngau_nhien']; pl.append(d['xs_con_lai_ngau_nhien'])
        else: st += f" (chi {d['so_cap']}/{USE} cap - khong tinh vao tong ket)"; skipped += 1
    else: st = '(chua quay/chua doi chieu)'
    if h and h['so_cap'] < USE: cl += ' *thieu cap*'
    out.append(f"{ky} | {ngay} | {cl} | {cap} | {st} | {(t or {}).get('tr3', '-')}")
out.append('')
if nk:
    # kiem dinh: so ky ve that BI LOAI (X) theo Poisson-binomial, xac suat bi loai moi ky = 1 - xs_con_lai; p thap = bi loai IT hon ngau nhien, p cao = bi loai NHIEU hon
    q = [1 - x for x in pl]; dist = [1.0]
    for qi in q:
        nd = [0.0] * (len(dist) + 1)
        for k, v in enumerate(dist): nd[k] += v * (1 - qi); nd[k + 1] += v * qi
        dist = nd
    X = nk - int(kc); p_le = sum(dist[:X + 1]); p_ge = sum(dist[X:])
    out += ['== TONG KET (chi tinh ky du %d cap) ==' % USE,
            f'Doi chieu {nk} ky: ve that CON LAI {int(kc)} ky ({kc / nk:.1%}), BI LOAI {X} ky; ngau nhien ky vong con lai {ke:.2f} ky ({ke / nk:.1%}).',
            f'Kiem dinh: P(bi loai <= {X} ky | ngau nhien) = {p_le:.3f} ; P(bi loai >= {X} ky) = {p_ge:.3f}.']
    if skipped: out.append(f'Bo qua {skipped} ky vi thieu cap (khong so sanh ngang duoc).')
    if nk < 20: out.append(f'KET LUAN: moi {nk} ky, chua du (can >= 20-30 ky) de noi loai seed co tac dung hay khong.')
    elif p_le < 0.05: out.append('KET LUAN: ve that bi loai it hon ngau nhien (p < 0.05) - can them ky de xac nhan, tranh nhieu phep thu.')
    else: out.append('KET LUAN: khong khac biet co y nghia so voi ngau nhien.')
    out.append('Moi ve van chi co xac suat 1/%s.' % f'{CT:,}')
if tk:
    s3 = sum(v['tr3'] for v in tk.values()); out.append(f'Ve du doan: {len(tk)} ky, tong ve trung>=3 so = {s3} (ky vong ngau nhien ~{sum(0.013866 * v['sove'] for v in tk.values()):.1f}).')
open('bao_cao/tom_tat_lotto535.txt', 'w').write('\n'.join(out) + '\n')
print('\n'.join(out))
