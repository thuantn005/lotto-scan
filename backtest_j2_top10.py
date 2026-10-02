#!/usr/bin/env python3
"""
Leakage-safe walk-forward backtest for L1-1 exact consensus-2 tickets.

Target range: 724..921
Window: dynamic, capped at 200 completed draws before target
Consensus key: exact 5 main numbers + special
Consensus level: exactly 2 distinct seeds
J2: 5/5 main numbers correct, special number wrong
"""

from __future__ import annotations
import argparse, csv, json, math
from collections import defaultdict
from pathlib import Path

M1=0x9E3779B97F4A7C15
M2=0xD1B54A32D192ED03
M3=0xBF58476D1CE4E5B9
M4=0x94D049BB133111EB
MASK64=0xFFFFFFFFFFFFFFFF
C=324632

def mix64(x):
    x &= MASK64
    x ^= x >> 30
    x = (x * M3) & MASK64
    x ^= x >> 27
    x = (x * M4) & MASK64
    x ^= x >> 31
    return x & MASK64

def unrank_colex(rank, n=35, k=5):
    out=[]
    r=rank
    x=n
    for i in range(k,0,-1):
        while math.comb(x,i) > r:
            x-=1
        out.append(x)
        r-=math.comb(x,i)
        x-=1
    return tuple(sorted(out))

def ticket(seed, draw_id):
    mixed=mix64((seed*M1 + draw_id*M2) & MASK64)
    rank=mixed % C
    nums=unrank_colex(rank)
    special=mix64(mixed) % 12 + 1
    return nums, special

def read_rows(path):
    rows=[]
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            d=int(r.get("draw_id") or r.get("draw") or r.get("id"))
            seed=int(r["seed"])
            nums=tuple(sorted(int(x) for x in (r.get("numbers") or r.get("main_numbers")).replace(","," ").split()))
            sp=int(r.get("special") or r.get("special_number"))
            rows.append((d,seed,nums,sp))
    return rows

def discover_rows(root):
    candidates=list(Path(root).rglob("*.csv"))
    rows=[]
    for p in candidates:
        try:
            rr=read_rows(p)
            if rr and any(700 <= x[0] <= 1000 for x in rr):
                rows.extend(rr)
        except Exception:
            pass
    if not rows:
        raise SystemExit("Không tìm thấy CSV L1-1. Hãy đặt dữ liệu CSV vào data/ hoặc l1-1/.")
    return rows

def build_seed_history(rows):
    # seed -> sorted draws where it appears
    h=defaultdict(list)
    for d,s,_,_ in rows:
        h[s].append(d)
    for s in h:
        h[s]=sorted(set(h[s]))
    return h

def available_seeds(rows, target, window=200):
    draws=sorted({d for d,_,_,_ in rows if d < target})
    draws=draws[-window:]
    return draws

def consensus2(rows, target, window=200):
    draws=available_seeds(rows,target,window)
    seed_rows=[x for x in rows if x[0] in set(draws)]
    # Each seed counts once in the consensus pool.
    by_seed={}
    for d,s,_,_ in seed_rows:
        by_seed.setdefault(s,d)
    groups=defaultdict(list)
    for s in by_seed:
        nums,sp=ticket(s,target)
        groups[(nums,sp)].append(s)
    out=[]
    for key,seeds in groups.items():
        if len(seeds)==2:
            ages=sorted([target-max(build_seed_history(rows)[s]) for s in seeds])
            out.append((key,seeds,ages))
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--data",default=".")
    ap.add_argument("--start",type=int,default=724)
    ap.add_argument("--end",type=int,default=921)
    ap.add_argument("--window",type=int,default=200)
    ap.add_argument("--top",type=int,default=10)
    ap.add_argument("--out",default="j2_top10_results")
    args=ap.parse_args()

    rows=discover_rows(args.data)
    actual={d:(nums,sp) for d,_,nums,sp in rows if args.start<=d<=args.end}
    hist=build_seed_history(rows)

    # The ranking below is intentionally deterministic and uses only pre-target
    # information. It prioritizes recent seed recurrence and special recurrence.
    # It is a filter to be backtested, not trained on the target J2 label.
    results=[]
    ticket_rows=[]

    for target in range(args.start,args.end+1):
        if target not in actual:
            continue
        pool=consensus2(rows,target,args.window)
        ranked=[]
        for (nums,sp),seeds,ages in pool:
            last_special_draw=max(
                [d for d,_,_,s in rows if d < target and s == sp] or [0]
            )
            special_age=target-last_special_draw if last_special_draw else 10**9
            special_gap=0
            prev=[d for d,_,_,s in rows if d < target and s == sp]
            if len(prev)>=2:
                special_gap=prev[-1]-prev[-2]
            age_sum=sum(ages)
            # Deterministic, pre-target score. Lower is earlier in ranking.
            score=(age_sum, max(ages), special_age, special_gap, nums, sp)
            ranked.append((score,nums,sp,seeds,ages,special_age,special_gap))
        ranked.sort(key=lambda x:x[0])
        top=ranked[:args.top]
        an,asp=actual[target]
        j2hits=[]
        for rank,(score,nums,sp,seeds,ages,sage,sgap) in enumerate(top,1):
            main_hit=(nums==an)
            j1=main_hit and sp==asp
            j2=main_hit and sp!=asp
            if j2:
                j2hits.append(rank)
            ticket_rows.append({
                "draw":target,"rank":rank,
                "numbers":"-".join(f"{x:02d}" for x in nums),
                "special":sp,
                "seed1":seeds[0],"seed2":seeds[1],
                "age1":ages[0],"age2":ages[1],
                "special_age":sage,"special_gap":sgap,
                "j1":int(j1),"j2":int(j2)
            })
        results.append({
            "draw":target,
            "actual_numbers":"-".join(f"{x:02d}" for x in an),
            "actual_special":asp,
            "consensus2_count":len(pool),
            "top10_j2_ranks":",".join(map(str,j2hits)),
            "j2_hit":int(bool(j2hits)),
            "j1_hit":int(any(r["j1"] for r in ticket_rows if r["draw"]==target))
        })

    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    with open(out/"per_draw.csv","w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=results[0].keys()); w.writeheader(); w.writerows(results)
    with open(out/"top10_tickets.csv","w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=ticket_rows[0].keys()); w.writeheader(); w.writerows(ticket_rows)
    summary={
        "draws_tested":len(results),
        "j2_draws_hit":sum(x["j2_hit"] for x in results),
        "j2_hit_rate":sum(x["j2_hit"] for x in results)/len(results) if results else 0,
        "j1_draws_hit":sum(x["j1_hit"] for x in results),
        "range":[args.start,args.end],
        "window":args.window,
        "consensus_level":2,
        "special_in_key":True
    }
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
