#!/usr/bin/env python3
"""Tao data/draws_rank.txt (draw_id rank special) tu data/all.csv cho scan_inverse.cpp."""
import os
from lotto_common import build_binom, build_rank_to_mask, load_all_actual_results
csv = os.environ.get("CSV_PATH", "data/all.csv"); out = os.environ.get("OUT", "data/draws_rank.txt")
b = build_binom(); lut = build_rank_to_mask(b); rows = []
for d, (n, sp, _) in sorted(load_all_actual_results(csv).items()):
    p = sorted(x - 1 for x in n); r = sum(b[p[k - 1]][k] for k in range(1, 6))
    assert lut[r] == sum(1 << (x - 1) for x in n)
    rows.append(f"{d} {r} {sp}")
open(out, "w").write("\n".join(rows) + "\n"); print(f"{len(rows)} ky -> {out}")
