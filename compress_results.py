#!/usr/bin/env python3
"""Nen gzip cac file results/final_j1_2plus_*_*.json (noi dung giu nguyen 100%).
  python3 compress_results.py            # tao .json.gz, giu file goc
  python3 compress_results.py --delete   # tao .json.gz, kiem tra giai nen == goc, roi xoa file .json goc
"""
import glob, gzip, os, sys
tot_a = tot_b = 0
for f in sorted(glob.glob("results/final_j1_2plus_*_*.json")):
    raw = open(f, "rb").read()
    out = f + ".gz"
    with open(out, "wb") as fh:
        with gzip.GzipFile(filename="", mode="wb", fileobj=fh, compresslevel=9, mtime=0) as gz:
            gz.write(raw)
    assert gzip.open(out, "rb").read() == raw, f
    tot_a += len(raw); tot_b += os.path.getsize(out)
    if "--delete" in sys.argv: os.remove(f)
print(f"{tot_a/1e6:.1f} MB -> {tot_b/1e6:.1f} MB")
