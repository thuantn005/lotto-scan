#!/usr/bin/env python3
"""
predict_next_draw_ai3.py - Du doan ky KE TIEP bang cach GOI OPENROUTER API
(MIEN PHI - dung router "openrouter/free" tu dong chon 1 model mien phi
dang co san, khong can the thanh toan - lay API key tai
openrouter.ai/keys), DOC LAP HOAN TOAN voi predict_next_draw.py,
predict_next_draw_ml.py, predict_next_draw_ai.py (Gemini) va
predict_next_draw_ai2.py (Groq) - khong sua, khong goi, khong dung chung
file ket qua voi bat ky script nao khac.

Cung logic nhu predict_next_draw_ai.py / predict_next_draw_ai2.py (liet
ke seed ung vien moi model tu L1, gui cho AI kem tom tat lich su gan
day, de AI chon 1 seed/model + giai thich), nhung goi OpenRouter (API
tuong thich OpenAI, mac dinh dung model router mien phi "openrouter/free"
- OpenRouter se tu dong chon 1 trong cac model dang mien phi tai thoi
diem goi) thay vi Gemini/Groq - de co 1 "y kien" thu 4 doc lap. KHONG
dung L2 lam input.

Luu y: day la 1 lop "y kien" bo sung mang tinh nghien cuu/thu nghiem -
xo so la ngau nhien that su, cau tra loi cua AI khong co gia tri du doan
chinh xac, chi de tham khao/so sanh voi cac phuong phap khac.

Ghi ra file RIENG: predict/next_draw_predict_ai3.txt. Chien luoc nay duoc
danh dau la "ai3" trong lich su du doan (predict/history/{draw_id}_ai3.txt),
doc lap voi base/ml/ai/ai2.

Can bien moi truong OPENROUTER_API_KEY (API key MIEN PHI, lay tai
https://openrouter.ai/keys, khong can the tin dung, luu duoi dang
GitHub Secret).

ENV:
    CSV_PATH         - file CSV cac ky quay (mac dinh data/all.csv)
    L1_GLOB          - pattern glob cac file L1 (mac dinh l1_merged/merged_seed*.json)
    OUT_PATH         - file .txt ket qua rieng cua AI3 (mac dinh predict/next_draw_predict_ai3.txt)
    HISTORY_DIR      - thu muc luu lich su du doan (mac dinh predict/history)
    CANDIDATES_PER_MODEL - so seed ung vien THUC SU gui cho OpenRouter moi
                        model (mac dinh 200) - anh huong truc tiep kich
                        thuoc request goi API, KHONG co bang chung tang
                        so nay giup AI chon dung hon (xem
                        backtest_predictions.py), chi de AI co nhieu lua
                        chon da dang hon de so sanh.
    CANDIDATE_POOL_SIZE - do SAU cua vong quet/khu trung lap NOI BO moi
                        model (mac dinh 10000, >= CANDIDATES_PER_MODEL).
                        KHONG anh huong prompt goi AI (chi lay top
                        CANDIDATES_PER_MODEL tu pool nay) - dung de luu
                        pool day du ra predict/candidate_pool_ai3/ phuc
                        vu phan tich/backtest sau nay.
    OPENROUTER_MODEL - model OpenRouter dung de goi (mac dinh openrouter/free
                        - router tu dong chon model MIEN PHI dang co san;
                        co the doi sang slug cu the co duoi ":free" neu muon,
                        vd "deepseek/deepseek-chat-v3.1:free")
"""

import glob
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

from lotto_common import (
    build_binom,
    build_rank_to_mask,
    predict_ticket,
    get_next_draw_id,
    load_recent_draws_summary,
    save_prediction_history,
    collect_ai_candidates_per_model,
    build_ai_prompt,
)

STRATEGY = "ai3"


def build_prompt(next_draw_id, recent_draws, models):
    return build_ai_prompt(next_draw_id, recent_draws, models)


def call_openrouter(prompt, api_key, model, max_retries=3):
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "content-type": "application/json",
                    "HTTP-Referer": "https://github.com/thuantn005/lotto-scan",
                    "X-Title": "lotto-scan predict_next_draw_ai3",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=60,
            )
            if resp.status_code in (429, 500, 502, 503, 504):
                last_error = requests.exceptions.HTTPError(
                    f"{resp.status_code} tam thoi (lan {attempt}/{max_retries})", response=resp)
                print(f"[AI3/OpenRouter] Loi {resp.status_code}, thu lai... "
                      f"(lan {attempt}/{max_retries})", file=sys.stderr)
                time.sleep(5 * attempt)
                continue
            resp.raise_for_status()
            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                raise RuntimeError(f"OpenRouter khong tra ve choice nao: {data}")
            return choices[0].get("message", {}).get("content", "")
        except requests.exceptions.RequestException as e:
            last_error = e
            print(f"[AI3/OpenRouter] Loi goi OpenRouter (lan {attempt}/{max_retries}): {e}", file=sys.stderr)
            time.sleep(5 * attempt)
    raise last_error


def main():
    csv_path = os.environ.get("CSV_PATH", "data/all.csv")
    l1_glob = os.environ.get("L1_GLOB", "l1_merged/merged_seed*.json")
    out_path = os.environ.get("OUT_PATH", "predict/next_draw_predict_ai3.txt")
    history_dir = os.environ.get("HISTORY_DIR", "predict/history")
    send_k = int(os.environ.get("CANDIDATES_PER_MODEL", "200"))
    pool_size = int(os.environ.get("CANDIDATE_POOL_SIZE", "10000"))
    pool_out_dir = os.environ.get("CANDIDATE_POOL_DIR", "predict/candidate_pool_ai3")
    model_name = os.environ.get("OPENROUTER_MODEL", "openrouter/free")

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("LOI: thieu bien moi truong OPENROUTER_API_KEY (lay mien phi tai "
              "https://openrouter.ai/keys)", file=sys.stderr)
        sys.exit(1)

    next_draw_id = get_next_draw_id(csv_path)
    recent_draws = load_recent_draws_summary(csv_path, last_k=15)
    files = sorted(glob.glob(l1_glob))
    print(f"[AI3/OpenRouter] Ky ke tiep can du doan: {next_draw_id:05d}")
    print(f"[AI3/OpenRouter] So file model L1 tim thay: {len(files)}")

    binom = build_binom()
    rank_to_mask = build_rank_to_mask(binom)

    models = []
    for fp in files:
        m = collect_ai_candidates_per_model(
            fp, next_draw_id, rank_to_mask, send_k,
            pool_size=pool_size, pool_out_dir=pool_out_dir,
        )
        if m:
            models.append(m)

    if not models:
        print("[AI3/OpenRouter] Khong co model nao co seed trong L1, dung.")
        return

    prompt = build_prompt(next_draw_id, recent_draws, models)
    raw_response = call_openrouter(prompt, api_key, model_name)

    cleaned = raw_response.strip()
    cleaned = re.sub(r"^```(json)?|```$", "", cleaned.strip(), flags=re.MULTILINE).strip()
    try:
        parsed = json.loads(cleaned)
        picks = parsed.get("picks", [])
    except json.JSONDecodeError as e:
        print(f"[AI3/OpenRouter] Khong parse duoc JSON tu OpenRouter: {e}\nRaw response:\n{raw_response}", file=sys.stderr)
        picks = []

    predictions = []
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"DU DOAN KY {next_draw_id:05d} - PHIEN BAN AI3/OPENROUTER (doc lap voi predict_next_draw.py, "
                f"predict_next_draw_ml.py, predict_next_draw_ai.py va predict_next_draw_ai2.py)\n")
        f.write(f"Model AI su dung (OpenRouter, mien phi): {model_name}\n")
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
            predictions.append({
                "seed_start": m["seed_start"],
                "seed": seed,
                "numbers": cand["numbers"],
                "special": cand["special"],
                "file": m["file"],
            })

        if not picks:
            f.write("(OpenRouter khong tra ve ket qua hop le lan nay, xem log de biet chi tiet.)\n")

    hpath = save_prediction_history(history_dir, next_draw_id, STRATEGY, predictions)

    print(f"[AI3/OpenRouter] Da ghi {len(picks)} du doan vao {out_path}")
    print(f"[AI3/OpenRouter] Da luu lich su du doan ({STRATEGY}) vao {hpath}")
    print(f"NEXT_DRAW_ID={next_draw_id}")


if __name__ == "__main__":
    main()
