#!/usr/bin/env python3
"""
Tia bot cac ky QUA CU trong `l1_merged/merged_seed*.json` de giu file duoi
1 gioi han kich thuoc co dinh (mac dinh 5MB) - file nay app doc THANG qua
CDN (khong phan trang), nen phai chan dung khong cho phinh to vo han theo
thoi gian (moi ky quay them ~5-6KB).

QUAN TRONG - vi sao khong duoc tia "vo tu": app dung file nay theo 1 CUA SO
truot (xem `github_seed_source.dart`): sinh so cho ky N chi dung seed cua
cac ky trong [N-699, N-200]. Nghia la ky CU NHAT con can cho tuong lai gan
la (ky moi nhat hien co - 699). Script nay UU TIEN xoa nhung ky CU HON muc
do (khong con ky nao trong tuong lai gan can toi), chi khi xoa het cac ky
"khong con can" ma van vuot gioi han thi moi buoc phai xoa tiep vao vung
"con can" (in canh bao ro rang khi xay ra truong hop nay).

Cach dung:
  python3 prune_merged_seed.py --file l1_merged/merged_seed682305800400.json
"""
import argparse
import json
import sys
from pathlib import Path

# Phai khop CHINH XAC voi hang so trong github_seed_source.dart (gapDraws +
# windowDraws) - doi ben nao thi doi ca 2 noi.
GAP_DRAWS = 200
WINDOW_DRAWS = 500
KEEP_MIN_DRAWS = GAP_DRAWS + WINDOW_DRAWS  # = 700

DEFAULT_CAP_BYTES = 5 * 1024 * 1024


def dump_size(merged: dict) -> int:
    return len(json.dumps(merged, separators=(",", ":")).encode("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--cap-bytes", type=int, default=DEFAULT_CAP_BYTES)
    args = ap.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"Khong tim thay {args.file}, bo qua.", file=sys.stderr)
        return 0

    merged = json.loads(path.read_text(encoding="utf-8"))
    draws = merged.get("draws", [])
    if not draws:
        return 0

    draws.sort(key=lambda d: d["draw_id"])
    before_count = len(draws)
    before_size = dump_size(merged)

    if before_size <= args.cap_bytes:
        print(f"{args.file}: {before_size} bytes, chua vuot {args.cap_bytes} - khong can tia.",
              file=sys.stderr)
        return 0

    latest_id = draws[-1]["draw_id"]
    min_needed_id = latest_id - KEEP_MIN_DRAWS + 1  # ky cu nhat con co the can

    warned_into_needed_range = False
    while dump_size(merged) > args.cap_bytes and len(draws) > 1:
        oldest = draws[0]
        if oldest["draw_id"] >= min_needed_id and not warned_into_needed_range:
            print(
                f"CANH BAO: {args.file} van vuot {args.cap_bytes} bytes sau khi da xoa "
                f"het cac ky KHONG CON CAN (< ky {min_needed_id}). Buoc phai xoa tiep vao "
                f"vung du lieu ma cua so 500 ky con can toi - anh huong chat luong pool seed "
                f"cho vai ky toi. Can xem lai gioi han kich thuoc hoac giam WINDOW_DRAWS.",
                file=sys.stderr,
            )
            warned_into_needed_range = True
        draws.pop(0)

    merged["draws"] = draws
    merged["total_draws"] = len(draws)
    merged["total_found"] = sum(d.get("found", 0) for d in draws)

    path.write_text(json.dumps(merged, separators=(",", ":")), encoding="utf-8")

    after_size = dump_size(merged)
    print(
        f"{args.file}: da tia {before_count - len(draws)} ky cu nhat "
        f"({before_size} -> {after_size} bytes, con {len(draws)} ky, tu ky "
        f"{draws[0]['draw_id']} den {draws[-1]['draw_id']}).",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
