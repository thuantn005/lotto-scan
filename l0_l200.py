#!/usr/bin/env python3
"""l0_l200.py - ho tro cho predict_l1_3_gap.py

l0/   : to hop TOAN BO ve J1 (C(35,5) x 12 = 3,895,584 ve) cua ky ke tiep, LOAI cac ve do seed trong
        results/ (J1 trung 2 lan, 3 lan, >=4 lan) sinh ra cho ky do. CHI ghi VE CON LAI (nen gzip,
        ~3.74 trieu dong).
l200/ : DOI CHIEU ve trung (ket qua J1 thuc te) cua ky vua quay voi file l0 cua ky do (ve con lai)
        va ghi ket qua + du doan da ghi truoc do (neu co). Moi ky 1 file nho.
"""
import glob, gzip, itertools, json, os, re, shutil
from collections import defaultdict

TOTAL = 324632 * 12


def _open(fp):
    return gzip.open(fp, "rt", encoding="utf-8") if fp.endswith(".gz") else open(fp, encoding="utf-8")


def load_result_seeds(pattern="results/final_j1_*plus*.json*"):
    """{seed: j1_count lon nhat} tu results/final_j1_2plus_*.json(.gz) + final_j1_3plus + final_j1_4plus."""
    out = {}
    for fp in sorted(glob.glob(pattern)):
        for r in json.load(_open(fp)).get("results", []):
            s = int(r["seed"]); c = int(r.get("j1_count", 0))
            if c > out.get(s, 0): out[s] = c
    return out


def build_excluded(draw_id, seeds, predict_ticket, rank_to_mask):
    """{(numbers_tuple, special): [j1_count lon nhat, so seed sinh ra ve nay]}"""
    ex = {}
    for s, c in seeds.items():
        nums, sp = predict_ticket(s, draw_id, rank_to_mask)
        k = (tuple(nums), sp)
        if k in ex:
            ex[k][0] = max(ex[k][0], c); ex[k][1] += 1
        else:
            ex[k] = [c, 1]
    return ex


def fmt(nums, sp):
    return "-".join(f"{n:02d}" for n in nums) + f" + {sp}"


def write_l0(l0_dir, draw_id, seeds, excluded, chosen=None):
    os.makedirs(l0_dir, exist_ok=True)
    by = defaultdict(int)
    for c, _ in excluded.values(): by[min(c, 4)] += 1
    sc = defaultdict(int)
    for c in seeds.values(): sc[min(c, 4)] += 1
    remain = TOTAL - len(excluded)
    tag = f"ky{draw_id:05d}"
    # VE CON LAI: tat ca to hop (tang dan) tru ve bi loai. Nen gzip (mtime=0), giai nen: gunzip -k <file>
    n = 0
    with open(os.path.join(l0_dir, f"{tag}_ve_con_lai.txt.gz"), "wb") as fh:
        with gzip.GzipFile(filename="", mode="wb", fileobj=fh, compresslevel=9, mtime=0) as gz:
            buf = []
            for nums in itertools.combinations(range(1, 36), 5):
                pre = "-".join(f"{x:02d}" for x in nums) + " + "
                for sp in range(1, 13):
                    if (nums, sp) in excluded: continue
                    buf.append(pre + str(sp)); n += 1
                if len(buf) >= 50000:
                    gz.write(("\n".join(buf) + "\n").encode()); buf = []
            if buf: gz.write(("\n".join(buf) + "\n").encode())
    assert n == remain, (n, remain)
    return remain


def lookup_l0(l0_dir, draw_id, ticket_str):
    """Doi chieu 1 ve voi l0/kyNNNNN_ve_con_lai.txt.gz. Tra ve ('con_lai', dong, tong) | ('khong_co', 0, tong) | None neu khong co file l0."""
    fc = os.path.join(l0_dir, f"ky{draw_id:05d}_ve_con_lai.txt.gz")
    if not os.path.exists(fc): return None
    total = 0; found = 0
    with gzip.open(fc, "rt", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            total = i
            if line.rstrip("\n") == ticket_str: found = i
    return ("con_lai", found, total) if found else ("khong_co", 0, total)


def clear_dir(d):
    if os.path.isdir(d):
        for e in os.listdir(d):
            p = os.path.join(d, e)
            shutil.rmtree(p) if os.path.isdir(p) and not os.path.islink(p) else os.remove(p)


def read_old_prediction(history_dir, draw_id):
    """Doc du doan cu cua draw_id trong history (truoc khi bi xoa). Tra ve list (nums, sp, seed)."""
    out = []
    for fp in sorted(glob.glob(os.path.join(history_dir, f"{draw_id:05d}_*.txt"))):
        for line in open(fp, encoding="utf-8"):
            p = line.strip().split("|")
            if len(p) >= 4:
                try: out.append(([int(x) for x in p[2].split(",")], int(p[3]), p[1]))
                except ValueError: pass
    return out


def record_l200(l200_dir, draw_id, actual, excluded, old_pred, l0_dir="l0"):
    """actual = (frozenset nums, special, date). Doi chieu ve trung voi l0/ cua ky do; ghi l200/kyNNNNN.txt
    (khong ghi de neu da co). Neu khong con file l0 cua ky do thi tinh lai tu results."""
    os.makedirs(l200_dir, exist_ok=True)
    path = os.path.join(l200_dir, f"ky{draw_id:05d}.txt")
    if os.path.exists(path): return None
    nums, sp, date = actual
    win = tuple(sorted(nums)); ws = fmt(win, sp)
    r = lookup_l0(l0_dir, draw_id, ws)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"KY {draw_id:05d} ({date}) - VE TRUNG J1\n")
        f.write(f"Ve trung: {ws}\n")
        if r and r[0] == "con_lai":
            f.write(f"DOI CHIEU l0 ky {draw_id:05d}: CO trong VE CON LAI (dong {r[1]:,}/{r[2]:,})\n")
        elif r:
            f.write(f"DOI CHIEU l0 ky {draw_id:05d}: KHONG co trong VE CON LAI ({r[2]:,} ve) => ve trung da bi loai\n")
        else:
            hit = excluded.get((win, sp))
            f.write(f"DOI CHIEU: khong co file l0 ky {draw_id:05d} -> tinh lai tu results: "
                    f"{'BI LOAI (J1x%d, %d seed)' % tuple(hit) if hit else 'CON LAI'}\n")
        f.write(f"Tap l0 ky nay: bi loai {len(excluded):,} | con lai {TOTAL - len(excluded):,} / {TOTAL:,}\n")
        if old_pred:
            for nm, s2, seed in old_pred:
                m = len(set(nm) & set(win))
                f.write(f"Du doan da ghi: {fmt(nm, s2)} (seed {seed}) -> trung {m}/5 so chinh, DB {'dung' if s2 == sp else 'sai'}"
                        f"{' => J1' if (m == 5 and s2 == sp) else ''}\n")
        else:
            f.write("Du doan da ghi: (khong co)\n")
    return path
