#!/usr/bin/env python3
"""
predict_next_draw_ai2.py - Du doan ky KE TIEP bang cach GOI GROQ API
(MIEN PHI VINH VIEN, khong can the thanh toan - lay API key tai
console.groq.com), DOC LAP HOAN TOAN voi predict_next_draw.py,
predict_next_draw_ml.py va predict_next_draw_ai.py (Gemini) - khong sua,
khong goi, khong dung chung file ket qua voi bat ky script nao khac.

Cung logic nhu predict_next_draw_ai.py (liet ke seed ung vien moi model
tu L1, gui cho AI kem tom tat lich su gan day, de AI chon 1 seed/model +
giai thich), nhung goi Groq (model mo, chay tren phan cung LPU toc do
cao) thay vi Gemini - de co 1 "y kien" thu 3 doc lap, khong dung L2.

Ghi ra file RIENG: predict/next_draw_predict_ai2.txt

Can bien moi truong GROQ_API_KEY (API key MIEN PHI VINH VIEN, lay tai
https://console.groq.com/keys, khong can the tin dung, luu duoi dang
GitHub Secret).

ENV:
    CSV_PATH         - file CSV cac ky quay (mac dinh data/all.csv)
    L1_GLOB          - pattern glob cac file L1 (mac dinh l1_merged/merged_seed*.json)
    OUT_PATH         - file .txt ket qua rieng (mac dinh predict/next_draw_predict_ai2.txt)
    CANDIDATES_PER_MODEL - so seed ung vien gui cho AI moi model (mac dinh 15)
    GROQ_MODEL       - model Groq dung de goi (mac dinh openai/gpt-oss-120b, mien phi, khuyen nghi thay the llama-3.3-70b-versatile da bi khai tu)
"""

import csv
import glob
import json
import os
import re
import sys
from pathlib import Path

import requests

M1 = 0x9E3779B97F4A7C15
M2 = 0xD1B54A32D192ED03
M3 = 0xBF58476D1CE4E5B9
M4 = 0x94D049BB133111EB
MASK64 = 0xFFFFFFFFFFFFFFFF
C = 324632  # C(35,5)


def build_binom():
    binom = [[0] * 6 for _ in range(36)]
    for n in range(36):
        for k in range(6):
            if k == 0:
                binom[n][k] = 1
            elif k > n:
                binom[n][k] = 0
            else:
                num, den = 1, 1
                for i in range(k):
                    num *= (n - i)
                    den *= (i + 1)
                binom[n][k] = num // den
    return binom


def build_rank_to_mask(binom):
    lut = [0] * C
    for r in range(C):
        mask, rem = 0, r
        for k in range(5, 0, -1):
            x = k - 1
            while binom[x + 1][k] <= rem:
                x += 1
            mask |= (1 << x)
            rem -= binom[x][k]
        lut[r] = mask
    return lut


def mix64(x):
    x &= MASK64
    x ^= (x >> 30)
    x = (x * M3) & MASK64
    x ^= (x >> 27)
    x = (x * M4) & MASK64
    x ^= (x >> 31)
    return x


def predict_ticket(seed, draw_id, rank_to_mask):
    combined = (seed * M1 + draw_id * M2) & MASK64
    mixed = mix64(combined)
    rank = mixed % C
    mask = rank_to_mask[rank]
    mixed2 = mix64(mixed)
    special = (mixed2 % 12) + 1
    numbers = [i + 1 for i in range(35) if mask & (1 << i)]
    return numbers, special


def get_next_draw_id(csv_path):
    max_id = 0
    with open(csv_path, "r", encoding="utf-8") as f:
        next(f, None)
        for line in f:
            parts = line.split(",", 2)
            if len(parts) < 2:
                continue
            try:
                did = int(parts[1])
            except ValueError:
                continue
            if did > max_id:
                max_id = did
    return max_id + 1


def load_recent_draws_summary(csv_path, last_k=15):
    """Tra ve list [(draw_id, [5 so], dac biet)] cua last_k ky GAN NHAT,
    dung lam ngu canh cho AI (khong dung de tinh toan chinh xac gi)."""
    rows = []
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            if len(row) < 5:
                continue
            try:
                draw_id = int(row[1])
            except ValueError:
                continue
            result_json = row[4]
            nums_match = re.search(r'"numbers"\s*:\s*\[([^\]]*)\]', result_json)
            sp_match = re.search(r'"special_numbers"\s*:\s*\[([^\]]*)\]', result_json)
            if not nums_match or not sp_match:
                continue
            numbers = sorted(int(x) for x in nums_match.group(1).split(",") if x.strip() != "")
            specials = [int(x) for x in sp_match.group(1).split(",") if x.strip() != ""]
            if len(numbers) != 5 or not specials:
                continue
            rows.append((draw_id, numbers, specials[0]))
    rows.sort(key=lambda r: r[0])
    return rows[-last_k:]


def collect_candidates_per_model(fp, next_draw_id, rank_to_mask, top_k):
    try:
        data = json.loads(Path(fp).read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Bo qua {fp}: {e}")
        return None

    seed_weight = {}
    for d in data.get("draws", []):
        for s in d.get("seeds", []):
            seed_weight[s] = seed_weight.get(s, 0) + 1

    if not seed_weight:
        return None

    top_seeds = sorted(seed_weight.keys(), key=lambda s: (-seed_weight[s], s))[:top_k]
    candidates = []
    for s in top_seeds:
        numbers, special = predict_ticket(s, next_draw_id, rank_to_mask)
        candidates.append({
            "seed": s,
            "weight": seed_weight[s],
            "numbers": numbers,
            "special": special,
        })
    return {
        "file": fp,
        "seed_start": data.get("seed_start"),
        "total_seeds_in_model": len(seed_weight),
        "candidates": candidates,
    }


def build_prompt(next_draw_id, recent_draws, models):
    lines = []
    lines.append(f"Ban dang phan tich du lieu NGHIEN CUU THONG KE cho xo so Lotto 5/35 Viet Nam "
                 f"(du an mang tinh hoc thuat, KHONG khuyen khich co bac). Ky can du doan la ky {next_draw_id:05d}.")
    lines.append("")
    lines.append(f"{len(recent_draws)} ky GAN NHAT (draw_id, 5 so chinh, dac biet):")
    for draw_id, numbers, special in recent_draws:
        lines.append(f"  ky {draw_id:05d}: {numbers} + DB {special}")
    lines.append("")
    lines.append("Co nhieu 'model' (dai seed khac nhau) dang duoc quet doc lap. Voi MOI model, "
                 "duoi day la mot vai seed ung vien (da tung khop ket qua o cac ky truoc do trong "
                 "qua khu) kem ve du doan cua tung seed NEU dung lai cho ky sap toi:")
    for i, m in enumerate(models):
        lines.append(f"\nModel {i} (seed_start={m['seed_start']}, tong {m['total_seeds_in_model']} seed trong L1):")
        for c in m["candidates"]:
            lines.append(f"  seed={c['seed']} (tung trung {c['weight']} lan) -> "
                         f"{c['numbers']} + DB {c['special']}")
    lines.append("")
    lines.append("Voi MOI model, hay chon DUNG 1 seed ung vien (trong danh sach da cho, KHONG duoc "
                 "bia ra seed moi) ma ban cho la 'dang chu y' nhat de theo doi, va giai thich NGAN "
                 "GON (1-2 cau) tai sao. Luu y ro rang day chi la BAI TAP THONG KE/nghien cuu, ban "
                 "KHONG the du doan chinh xac ket qua xo so that su.")
    lines.append("")
    lines.append("Tra loi CHI DUOI DANG JSON (khong markdown, khong giai thich ngoai JSON), dinh dang:")
    lines.append('{"picks": [{"model_index": 0, "seed": 123, "reasoning": "..."}]}')
    return "\n".join(lines)


def call_groq(prompt, api_key, model):
    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    choices = data.get("choices", [])
    if not choices:
        raise RuntimeError(f"Groq khong tra ve choice nao: {data}")
    return choices[0].get("message", {}).get("content", "")


def main():
    csv_path = os.environ.get("CSV_PATH", "data/all.csv")
    l1_glob = os.environ.get("L1_GLOB", "l1_merged/merged_seed*.json")
    out_path = os.environ.get("OUT_PATH", "predict/next_draw_predict_ai2.txt")
    top_k = int(os.environ.get("CANDIDATES_PER_MODEL", "15"))
    model_name = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("LOI: thieu bien moi truong GROQ_API_KEY (lay mien phi tai "
              "https://console.groq.com/keys)", file=sys.stderr)
        sys.exit(1)

    next_draw_id = get_next_draw_id(csv_path)
    recent_draws = load_recent_draws_summary(csv_path, last_k=15)
    files = sorted(glob.glob(l1_glob))
    print(f"[AI2/Groq] Ky ke tiep can du doan: {next_draw_id:05d}")
    print(f"[AI2/Groq] So file model L1 tim thay: {len(files)}")

    binom = build_binom()
    rank_to_mask = build_rank_to_mask(binom)

    models = []
    for fp in files:
        m = collect_candidates_per_model(fp, next_draw_id, rank_to_mask, top_k)
        if m:
            models.append(m)

    if not models:
        print("[AI2/Groq] Khong co model nao co seed trong L1, dung.")
        return

    prompt = build_prompt(next_draw_id, recent_draws, models)
    raw_response = call_groq(prompt, api_key, model_name)

    cleaned = raw_response.strip()
    cleaned = re.sub(r"^```(json)?|```$", "", cleaned.strip(), flags=re.MULTILINE).strip()
    try:
        parsed = json.loads(cleaned)
        picks = parsed.get("picks", [])
    except json.JSONDecodeError as e:
        print(f"[AI2/Groq] Khong parse duoc JSON tu Groq: {e}\nRaw response:\n{raw_response}", file=sys.stderr)
        picks = []

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"DU DOAN KY {next_draw_id:05d} - PHIEN BAN AI2/GROQ (doc lap voi predict_next_draw.py, predict_next_draw_ml.py va predict_next_draw_ai.py)\n")
        f.write(f"Model AI su dung (Groq, mien phi vinh vien): {model_name}\n")
        f.write("Luu y: day la bai tap thong ke/nghien cuu, KHONG co gia tri du doan chinh xac.\n\n")

        for pick in picks:
            idx = pick.get("model_index")
            seed = pick.get("seed")
            reasoning = pick.get("reasoning", "")
            if idx is None or idx >= len(models):
                continue
            m = models[idx]
            cand = next((c for c in m["candidates"] if c["seed"] == seed), None)
            if cand is None:
                continue
            nums_str = "-".join(f"{n:02d}" for n in cand["numbers"])
            f.write(f"--- Model (l1_merged file: {m['file']}) ---\n")
            f.write(f"  seed_start cua model: {m['seed_start']}\n")
            f.write(f"  seed AI chon: {seed}\n")
            f.write(f"  ly do AI dua ra: {reasoning}\n")
            f.write(f"  DU DOAN ky {next_draw_id:05d}: {nums_str} + DAC BIET {cand['special']}\n\n")

        if not picks:
            f.write("(Groq khong tra ve ket qua hop le lan nay, xem log de biet chi tiet.)\n")

    print(f"[AI2/Groq] Da ghi {len(picks)} du doan vao {out_path}")
    print(f"NEXT_DRAW_ID={next_draw_id}")


if __name__ == "__main__":
    main()
