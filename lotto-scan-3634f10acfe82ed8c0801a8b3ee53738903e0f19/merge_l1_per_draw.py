#!/usr/bin/env python3
"""
merge_l1_per_draw.py — Gop tat ca file per-draw (batch_ky{draw_id}_seed{X}.json)
trong thu muc l1/ thanh MOT file JSON duy nhat.

Khong dong vao thu muc l1/ (giu nguyen 850 file rieng le de check_l1 van hoat dong
binh thuong). File gop duoc ghi ra thu muc rieng (mac dinh: l1_merged/).

Dinh dang moi file nguon (l1/batch_ky{draw_id}_seed{seed_start}.json):
    {"draw_id":N,"draw_date":"YYYY-MM-DD","seed_start":S,"seed_end":E,"found":F,"seeds":[...]}

Dinh dang file gop (l1_merged/merged_seed{seed_start}.json):
    {
      "seed_start": S,
      "seed_end": E,
      "total_draws": 850,
      "total_found": <tong so luot trung tat ca ky>,
      "draws": [
        {"draw_id":N,"draw_date":"...","found":F,"seeds":[...]},
        ...
      ]
    }

ENV:
    L1_DIR      - thu muc chua cac file per-draw (mac dinh: l1)
    OUT_DIR     - thu muc ghi file gop (mac dinh: l1_merged)
    OUT_NAME    - ten file gop (mac dinh: tu dong theo seed_start neu phat hien duoc)
"""

import json
import os
import glob
import sys

def main():
    l1_dir = os.environ.get("L1_DIR", "l1")
    out_dir = os.environ.get("OUT_DIR", "l1_merged")
    out_name_override = os.environ.get("OUT_NAME", "")

    files = sorted(glob.glob(os.path.join(l1_dir, "batch_ky*.json")))
    if not files:
        print(f"Khong tim thay file batch_ky*.json nao trong {l1_dir}/", file=sys.stderr)
        sys.exit(1)

    print(f"Tim thay {len(files)} file trong {l1_dir}/, dang gop...", file=sys.stderr)

    draws = []
    seed_start_set = set()
    seed_end_set = set()
    total_found = 0
    skipped = 0

    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                d = json.load(f)
        except Exception as e:
            print(f"  Bo qua file loi: {fp} ({e})", file=sys.stderr)
            skipped += 1
            continue

        required = {"draw_id", "draw_date", "seed_start", "seed_end", "found", "seeds"}
        if not required.issubset(d.keys()):
            print(f"  Bo qua file sai dinh dang: {fp}", file=sys.stderr)
            skipped += 1
            continue

        seed_start_set.add(d["seed_start"])
        seed_end_set.add(d["seed_end"])
        total_found += d["found"]

        draws.append({
            "draw_id": d["draw_id"],
            "draw_date": d["draw_date"],
            "found": d["found"],
            "seeds": d["seeds"],
        })

    draws.sort(key=lambda x: x["draw_id"])

    seed_start = seed_start_set.pop() if len(seed_start_set) == 1 else sorted(seed_start_set)[0]
    seed_end = seed_end_set.pop() if len(seed_end_set) == 1 else sorted(seed_end_set)[-1]

    if len(seed_start_set) > 1 or len(seed_end_set) > 1:
        print(f"  CANH BAO: cac file co seed_start/seed_end KHONG dong nhat "
              f"({len(seed_start_set)} gia tri start, {len(seed_end_set)} gia tri end). "
              f"Dung gia tri dau tien/cuoi cung theo thu tu sap xep.", file=sys.stderr)

    merged = {
        "seed_start": seed_start,
        "seed_end": seed_end,
        "total_draws": len(draws),
        "total_found": total_found,
        "draws": draws,
    }

    os.makedirs(out_dir, exist_ok=True)
    out_name = out_name_override or f"merged_seed{seed_start}.json"
    out_path = os.path.join(out_dir, out_name)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, separators=(",", ":"))

    print(f"\nDa gop {len(draws)} ky (bo qua {skipped} file loi) -> {out_path}", file=sys.stderr)
    print(f"Tong luot trung J1: {total_found}", file=sys.stderr)
    print(f"MERGED_FILE={out_path}")
    print(f"TOTAL_DRAWS={len(draws)}")
    print(f"TOTAL_FOUND={total_found}")


if __name__ == "__main__":
    main()
