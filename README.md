# Count-Gap Top-3 (model du doan them vao lotto-scan)

Lay snapshot MOI NHAT trong `data/candidate_scores_and_tickets.csv` (ky t), xep hang:
`COUNT giam dan -> GAP tang dan -> SEED tang dan`, lay Top-3 seed, sinh ve cho ky t+1
bang `lotto_common.predict_ticket(seed, draw_id, rank_to_mask)` cua repo (KHONG sua lotto_common.py).
Khong dung cot ket qua (target_mask, matches, j1...) khi xep hang.

Output: `predict/next_top3.csv`

## File
- predict_count_gap_top3.py            - script du doan
- .github/workflows/count_gap_top3_after_scan_v2.yml - tu chay sau Scan V2
- data/candidate_scores_and_tickets.csv - baseline den snapshot #922
- predict/next_top3.csv                 - ket qua mau (ky #923)

## Gioi han can biet
1. Repo chua co buoc nao cap nhat candidate_scores_and_tickets.csv (chi toi #922, repo da toi #927).
   Cac seed trong CSV KHONG phai seed trong l1-2/ (da kiem tra: 0 trung) va `count` khong tai tao duoc tu l1-2,
   nen khong the tu sinh lai CSV tu du lieu hien co. Can nguon sinh CSV goc.
2. Vi vay workflow dat STRICT_FRESH=1: neu CSV cu hon data/all.csv thi KHONG commit du doan cu
   (chi bao warning). Chay local khong co STRICT_FRESH thi chi in canh bao.
3. Nhu cac backtest truoc: moi cach chon seed deu chi ngang xac suat ngau nhien.
