"""Benchmark nhanh tốc độ thật trên GitHub Actions runner."""
import csv, json, os, time
from math import comb

M1,M2=0x9E3779B97F4A7C15,0xD1B54A32D192ED03
M3,M4=0xBF58476D1CE4E5B9,0x94D049BB133111EB
MASK=(1<<64)-1
C=comb(35,5)

def _mix(x):
    z=x&MASK; z^=z>>30; z=(z*M3)&MASK; z^=z>>27; z=(z*M4)&MASK; return z^(z>>31)
def _unrank(r):
    out,rem=[],r
    for k in range(5,0,-1):
        x=k-1
        while comb(x+1,k)<=rem: x+=1
        out.append(x+1); rem-=comb(x,k)
    return sorted(out)
def ticket(seed,d): return _unrank(_mix(seed*M1+d*M2)%C)

res={}
with open("data/all.csv", newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        try:
            d=int(row["draw_id"]); rj=json.loads(row["result_json"])
            res[d]=sorted(rj["numbers"])
        except: continue

draw_ids=sorted(res.keys())
n=len(draw_ids)
print(f"n_draws={n}")

t0=time.time()
TEST_SEEDS=20000
for seed in range(1,TEST_SEEDS+1):
    for d in draw_ids:
        ticket(seed,d)
elapsed=time.time()-t0
rate=TEST_SEEDS*n/elapsed
print(f"Rate: {rate:,.0f} checks/s")
print(f"Seeds/s: {TEST_SEEDS/elapsed:,.0f}")
