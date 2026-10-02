#!/usr/bin/env python3
"""Dieu phoi: prepare | predict | backtest | check.  Moi output la file .txt."""
import argparse, os, random, sys
from collections import Counter, defaultdict
from mega_lib import *

def cmd_prepare(a):
    d=load_draws(a.data)[-a.window:]
    os.makedirs('work',exist_ok=True)
    with open('work/draws.txt','w') as f:
        for i,_,n in d: f.write(f"{i} {rank(n)}\n")
    print(f"prepare: {len(d)} ky ({d[0][0]}..{d[-1][0]})")

def load_hits(path):
    h=defaultdict(set)
    for line in open(path):
        p=line.split()
        if len(p)==2: h[int(p[0])].add(int(p[1]))
    return h

def consensus(tickets):
    v=Counter(x for t in tickets for x in t)
    return sorted([x for x,_ in sorted(v.items(),key=lambda a:(-a[1],a[0]))[:6]])

def cmd_predict(a):
    draws=load_draws(a.data); hits=load_hits(a.hits); nxt=draws[-1][0]+1
    seeds=set()
    for d in range(nxt-a.recent,nxt): seeds|=hits.get(d,set())
    tk=[ticket(s,nxt) for s in sorted(seeds)]
    os.makedirs('predict/history',exist_ok=True)
    lines=[f"DU DOAN MEGA 6/45 - KY {nxt:05d}",
           f"Nguon: seed trung >=1 trong {a.recent} ky gan nhat (ky {nxt-a.recent}..{nxt-1}); so seed: {len(seeds)}",
           "LUU Y: moi ky doc lap; seed 'trung' qua khu khong co gia tri du doan. File nay chi de thu nghiem.",""]
    if tk:
        ct=consensus(tk); lines.append("VE DONG THUAN (6 so duoc nhieu seed chon nhat): "+"-".join(f"{x:02d}" for x in ct))
        lines.append(""); lines.append("10 VE SEED DAU TIEN:")
        for s in sorted(seeds)[:10]: lines.append(f"  seed {s}: "+"-".join(f"{x:02d}" for x in ticket(s,nxt)))
    else: lines.append("Khong co seed nao -> tang --count hoac --recent.")
    txt="\n".join(lines); open('predict/next_draw_predict.txt','w').write(txt)
    open(f'predict/history/{nxt:05d}.txt','w').write(txt); print(txt)

def cmd_backtest(a):
    draws=load_draws(a.data); hits=load_hits(a.hits); rng=random.Random(1)
    last=draws[-1][0]; res=[]; rows=[]
    for dr,date,nums in draws[-a.k:]:
        seeds=set()
        for d in range(dr-a.recent,dr): seeds|=hits.get(d,set())
        if not seeds: continue
        tk=[ticket(s,dr) for s in seeds]; act=set(nums)
        ct=consensus(tk); m=len(set(ct)&act)
        avg=sum(len(set(t)&act) for t in tk)/len(tk)
        rnd=sum(len(set(rng.sample(range(1,46),6))&act) for _ in range(200))/200
        res.append((m,avg,rnd)); rows.append(f"ky {dr:05d} {date}: seed={len(seeds):4d} | dong thuan {m}/6 | TB moi seed {avg:.2f} | ngau nhien {rnd:.2f}")
    n=len(res)
    if not n: print("khong du hit de backtest"); return
    out=[f"BACKTEST QUET SEED MEGA 6/45 (walk-forward, {n} ky, cua so {a.recent} ky)",
         f"Ky vong ngau nhien: {36/45:.3f} so trung / ve",
         f"Ve dong thuan   : TB {sum(r[0] for r in res)/n:.3f} | co >=3 so: {sum(r[0]>=3 for r in res)} ky",
         f"TB moi seed     : {sum(r[1] for r in res)/n:.3f}",
         f"Ngau nhien (mo phong): {sum(r[2] for r in res)/n:.3f}",
         "Neu 3 so tren xap xi nhau -> khong co loi the so voi ngau nhien.",""]+rows
    os.makedirs('backtest',exist_ok=True); open('backtest/backtest.txt','w').write("\n".join(out)); print("\n".join(out[:6]))

def cmd_check(a):
    draws={i:n for i,_,n in load_draws(a.data)}; lines=[]
    for fn in sorted(os.listdir('predict/history')):
        k=int(fn[:5])
        if k in draws:
            t=open('predict/history/'+fn).read()
            for l in t.splitlines():
                if l.startswith('VE DONG THUAN'):
                    p=[int(x) for x in l.split(': ')[1].split('-')]
                    lines.append(f"ky {k:05d}: du doan {p} | ket qua {draws[k]} | trung {len(set(p)&set(draws[k]))}/6")
    os.makedirs('results',exist_ok=True); open('results/check.txt','w').write("\n".join(lines) or "chua co ky nao de doi chieu"); print("\n".join(lines[-10:]))

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('cmd',choices=['prepare','predict','backtest','check'])
    p.add_argument('--data',default='data/all.txt'); p.add_argument('--hits',default='results/hits.txt')
    p.add_argument('--window',type=int,default=60); p.add_argument('--recent',type=int,default=20); p.add_argument('--k',type=int,default=40)
    a=p.parse_args(); globals()['cmd_'+a.cmd](a)
