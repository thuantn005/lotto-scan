#!/usr/bin/env python3
"""
scan_j1_triple.py — quét seed tìm J1 >= MIN_J1 lần.
Ghi checkpoint định kỳ để không mất data khi bị timeout/kill giữa chừng.
Tương thích với scan_auto v2: luôn ghi "scanned" = số seed thực tế đã quét,
để bước Validate của workflow biết chunk có quét đủ hay bị cắt ngang.
"""
import csv, json, os, sys, time
from math import comb
from pathlib import Path

CSV_PATH = os.environ.get("CSV_PATH", "data/all.csv")
OUT_PATH = os.environ.get("OUT_PATH", "results/chunk.json")
START    = int(os.environ.get("SCAN_START", "1"))
END      = int(os.environ.get("SCAN_END",   "500000000"))
MIN_J1   = int(os.environ.get("MIN_J1",     "3"))
CHECKPOINT_SEC = 30

M1,M2=0x9E3779B97F4A7C15,0xD1B54A32D192ED03
M3,M4=0xBF58476D1CE4E5B9,0x94D049BB133111EB
MASK=(1<<64)-1; C=comb(35,5)

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
def special(seed,d): return _mix(_mix(seed*M1+d*M2))%12+1

res={}; spc={}; dates={}
with open(CSV_PATH,newline="",encoding="utf-8") as f:
    for row in csv.DictReader(f):
        try:
            d=int(row["draw_id"]); rj=json.loads(row["result_json"])
            res[d]=sorted(rj["numbers"]); spc[d]=rj["special_numbers"][0]
            dates[d]=row.get("draw_date","")
        except: continue

draw_ids=sorted(res.keys())
n=len(draw_ids)
print(f"Loaded {n} ky. Quet seed {START:,} -> {END:,}, MIN_J1={MIN_J1}", flush=True)

Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)

# Nếu SCAN_START > SCAN_END (chunk ngoài total_target), workflow tự xử lý
# trước khi gọi script này — nhưng phòng hờ vẫn ghi file hợp lệ.
if START > END:
    payload = {
        "status": "empty",
        "scan_start": START, "scan_end": END,
        "scanned": 0, "completed": True, "min_j1": MIN_J1,
        "results": [],
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print("Range rong -- da ghi file empty.")
    sys.exit(0)

def save_checkpoint(scanned_count, found, done=False):
    """
    scanned_count: SỐ SEED THỰC TẾ ĐÃ QUÉT (không phải seed cuối cùng)
    -- đây là field workflow v2 dùng để validate chunk có quét đủ hay bị cắt.
    """
    tmp_path = OUT_PATH + ".tmp"
    payload = {
        "status": "completed" if done else "partial",
        "scan_start": START,
        "scan_end": END,
        "scanned": scanned_count,
        "completed": done,
        "min_j1": MIN_J1,
        "found": len(found),
        "results": sorted(found, key=lambda x: -x["j1_count"]),
    }
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    os.replace(tmp_path, OUT_PATH)

found=[]
t0=time.time(); last_log=t0; last_checkpoint=t0
scanned_count=0

try:
    for seed in range(START,END+1):
        j2_hits=[]
        for d in draw_ids:
            if ticket(seed,d)==res[d]:
                j2_hits.append(d)

        if len(j2_hits)>=MIN_J1:
            j1_hits=[d for d in j2_hits if special(seed,d)==spc[d]]
            if len(j1_hits)>=MIN_J1:
                entry={
                    "seed": seed,
                    "j1_count": len(j1_hits),
                    "j2_count": len(j2_hits),
                    "jackpot1_hits": [
                        {"draw_id":d,"draw_date":dates[d],"numbers":res[d],"special":spc[d]}
                        for d in j1_hits
                    ],
                    "jackpot2_hits": j2_hits,
                }
                found.append(entry)
                print(f"HIT seed={seed} J1={len(j1_hits)}x J2={len(j2_hits)}x ky={j1_hits}", flush=True)

        scanned_count += 1
        now=time.time()
        if now-last_checkpoint>=CHECKPOINT_SEC:
            save_checkpoint(scanned_count, found, done=False)
            last_checkpoint=now

        if now-last_log>=15:
            rate=scanned_count/(now-t0)
            remaining=(END-START+1)-scanned_count
            eta=remaining/rate if rate>0 else 0
            print(f"  scanned={scanned_count:,}/{END-START+1:,} ({rate:,.0f}/s) ETA {eta/3600:.2f}h found={len(found)}", flush=True)
            last_log=now

    # Quét xong toàn bộ range -- BẮT BUỘC scanned == expected để Validate pass
    save_checkpoint(scanned_count, found, done=True)
    elapsed=time.time()-t0
    print(f"\nXong: {scanned_count:,} seed / {elapsed:.0f}s. Tim thay {len(found)} seed J1>={MIN_J1}")

except KeyboardInterrupt:
    # Bị kill giữa chừng (SIGINT) -- ghi checkpoint với completed=False,
    # scanned < expected -- Validate của workflow sẽ tự phát hiện và fail đúng
    save_checkpoint(scanned_count, found, done=False)
    print(f"\nBi ngat tai scanned={scanned_count:,} -- da luu checkpoint (chua du)")
    sys.exit(1)

print(f"Saved -> {OUT_PATH}")
