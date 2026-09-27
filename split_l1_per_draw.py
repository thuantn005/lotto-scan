#!/usr/bin/env python3
"""
split_l1_per_draw.py - Tach 1 file cache GOP (do scan_per_draw.cpp ghi ra,
dung de quet GIA TANG cho nhanh - xem comment trong scan_v2_auto.yml) thanh
NHIEU FILE RIENG, MOI KY 1 FILE, trong thu muc dich (l1-1/ hoac l1-2/).

Ly do can file cache GOP: scan_per_draw.cpp doc lai file cu de biet ky nao
DA quet roi (chi quet ky MOI moi lan) - can 1 file duy nhat de doc nhanh.
Nhung DU LIEU dua cho cac buoc sau (thang hang L2, du doan) phai la MOI KY
1 FILE RIENG (khong gop) theo dung yeu cau - nen file cache CHI la dinh dang
TRUNG GIAN noi bo, khong phai "ket qua L1" nguoi dung/script khac nen dung.

Moi file dich (OUT_DIR/{draw_id}.json) co dinh dang:
    {"draw_id":N,"draw_date":"...","seed_start":S,"seed_end":E,
     "found":F,"seeds":[...]}

Tu dong XOA cac file {draw_id}.json trong OUT_DIR ma draw_id KHONG CON
trong cache nua (vi du da bi prune ra khoi cua so LAST_N_DRAWS/gioi han
dung luong) - giu OUT_DIR luon dong bo 1-1 voi cache.

ENV:
    CACHE_FILE  - duong dan file cache gop (bat buoc)
    OUT_DIR     - thu muc dich, moi ky 1 file (bat buoc)
"""
import json
import os
import sys
from pathlib import Path


def main():
    cache_file = os.environ.get("CACHE_FILE", "")
    out_dir = os.environ.get("OUT_DIR", "")
    if not cache_file or not out_dir:
        print("Thieu CACHE_FILE hoac OUT_DIR", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(cache_file):
        print(f"Khong tim thay {cache_file}, bo qua (chua co gi de tach).", file=sys.stderr)
        print("SPLIT_COUNT=0")
        return

    data = json.loads(Path(cache_file).read_text(encoding="utf-8"))
    seed_start = data.get("seed_start")
    seed_end = data.get("seed_end")
    draws = data.get("draws", [])

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    current_ids = set()
    for d in draws:
        did = d["draw_id"]
        current_ids.add(did)
        payload = {
            "draw_id": did,
            "draw_date": d.get("draw_date"),
            "seed_start": seed_start,
            "seed_end": seed_end,
            "found": len(d.get("seeds", [])),
            "seeds": d.get("seeds", []),
        }
        (out / f"{did}.json").write_text(
            json.dumps(payload, separators=(",", ":")), encoding="utf-8"
        )

    removed = 0
    for fp in out.glob("*.json"):
        try:
            did = int(fp.stem)
        except ValueError:
            continue
        if did not in current_ids:
            fp.unlink()
            removed += 1

    print(f"Da ghi {len(draws)} file ky vao {out_dir} (xoa {removed} file ky cu khong con trong cua so).",
          file=sys.stderr)
    print(f"SPLIT_COUNT={len(draws)}")
    print(f"REMOVED_STALE={removed}")


if __name__ == "__main__":
    main()
