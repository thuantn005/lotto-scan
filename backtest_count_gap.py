#!/usr/bin/env python3
"""
backtest_count_gap.py - causal walk-forward backtest for the 11-hit rule.

For every target draw T:
  snapshot = seed history through T-1
  rank Count DESC, GAP ASC, Seed ASC
  generate tickets with draw_id=T
  compare against actual data/all.csv

This prevents target leakage in the ranking stage.
"""
import argparse,csv,os
from collections import defaultdict
from lotto_common import build_binom,build_rank_to_mask,predict_ticket,load_all_actual_results

def load_hist(path):
    d=defaultdict(set)
    with open(path,encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):
            try:d[int(r["draw_id"])].add(int(r["seed"]))
            except:pass
    return d

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--history",default="data/seed_history.csv")
    ap.add_argument("--results",default="data/all.csv")
    ap.add_argument("--start",type=int,default=2)
    ap.add_argument("--end",type=int,default=None)
    ap.add_argument("--top",type=int,default=10)
    ap.add_argument("--out",default="backtest_count_gap.csv")
    a=ap.parse_args()
    hist=load_hist(a.history); actual=load_all_actual_results(a.results)
    end=a.end or max(actual)
    counts={}; last={}
    lut=build_rank_to_mask(build_binom()); rows=[]
    for t in range(1,end+1):
        for s in hist.get(t,set()):
            counts[s]=counts.get(s,0)+1; last[s]=t
        target=t+1
        if target<a.start or target>end: continue
        ranked=sorted(((s,c,t-last[s]) for s,c in counts.items()),
                      key=lambda x:(-x[1],x[2],x[0]))[:a.top]
        act=actual.get(target)
        if not act: continue
        nums_actual,sp_actual,_=act
        best=0; j1=0
        for rank,(s,c,g) in enumerate(ranked,1):
            nums,sp=predict_ticket(s,target,lut)
            m=len(set(nums)&set(nums_actual))
            hit=int(m==5 and sp==sp_actual)
            best=max(best,m)
            j1=max(j1,hit)
            rows.append([target,rank,s,c,g,"-".join(map(str,nums)),sp,m,int(sp==sp_actual),hit])
    os.makedirs(os.path.dirname(a.out) or ".",exist_ok=True)
    with open(a.out,"w",encoding="utf-8",newline="") as f:
        w=csv.writer(f); w.writerow(["draw","rank","seed","count","gap","numbers","special","matches","special_hit","j1"]);w.writerows(rows)
    draws=sorted(set(r[0] for r in rows))
    for k in [1,3,5,10]:
        hits=sum(any(r[0]==d and r[1]<=k and int(r[7])==5 for r in rows) for d in draws)
        j1s=sum(any(r[0]==d and r[1]<=k and int(r[9])==1 for r in rows) for d in draws)
        print(f"Top-{k}: 5/5 draws={hits}, J1 draws={j1s}")
    print("OUT=",a.out)

if __name__=="__main__":main()
