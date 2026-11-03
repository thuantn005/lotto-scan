"""Ham dung chung cho Mega 6/45: doc du lieu, rank/unrank colex, sinh ve tu seed."""
import csv, json
from math import comb
M1=0x9E3779B97F4A7C15; M2=0xD1B54A32D192ED03; M3=0xBF58476D1CE4E5B9; M4=0x94D049BB133111EB
MASK=(1<<64)-1; C=comb(45,6)

def mix64(x):
    x&=MASK; x^=x>>30; x=(x*M3)&MASK; x^=x>>27; x=(x*M4)&MASK; x^=x>>31; return x

def load_draws(path):
    out=[]
    with open(path,encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            try:
                nums=sorted(json.loads(r['result_json'])['numbers'])
                if len(nums)==6 and all(1<=x<=45 for x in nums) and len(set(nums))==6:
                    out.append((int(r['draw_id']),r['draw_date'],nums))
            except Exception: continue
    out.sort(); return out

def rank(nums):
    return sum(comb(x-1,i+1) for i,x in enumerate(sorted(nums)))

def unrank(r):
    res=[]; rem=r
    for k in range(6,0,-1):
        x=k-1
        while comb(x+1,k)<=rem: x+=1
        res.append(x+1); rem-=comb(x,k)
    return sorted(res)

def ticket(seed,draw_id):
    m=mix64((seed*M1+draw_id*M2)&MASK)
    return unrank(m%C)
