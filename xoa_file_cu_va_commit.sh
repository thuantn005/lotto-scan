#!/bin/sh
# Chay tai thu muc goc repo SAU khi giai nen de len. Xoa file cu (da duoc thay).
git rm -q --ignore-unmatch results/final_j1_2plus_*_*.json   # ban .json.gz da co trong zip
git rm -q --ignore-unmatch predict/count_gap_history/00927_count_gap.csv
git rm -q --ignore-unmatch predict/count_gap_history/00928_count_gap.csv
git rm -q --ignore-unmatch predict/history/00913_gap.txt
git rm -q --ignore-unmatch predict/history/00914_gap.txt
git rm -q --ignore-unmatch predict/history/00915_gap.txt
git rm -q --ignore-unmatch predict/history/00916_gap.txt
git rm -q --ignore-unmatch predict/history/00917_gap.txt
git rm -q --ignore-unmatch predict/history/00918_gap.txt
git rm -q --ignore-unmatch predict/history/00919_gap.txt
git rm -q --ignore-unmatch predict/history/00920_gap.txt
git rm -q --ignore-unmatch predict/history/00921_gap.txt
git rm -q --ignore-unmatch predict/history/00922_gap.txt
git rm -q --ignore-unmatch predict/history/00923_gap.txt
git rm -q --ignore-unmatch predict/history/00924_gap.txt
git rm -q --ignore-unmatch predict/history/00925_gap.txt
git rm -q --ignore-unmatch predict/history/00926_gap.txt
git rm -q --ignore-unmatch predict/history/00927_gap.txt
git rm -q --ignore-unmatch predict/history/00928_gap.txt
git rm -q --ignore-unmatch predict/history/00929_gap.txt
git rm -q --ignore-unmatch predict/history/00930_gap.txt
git rm -q --ignore-unmatch predict/history/00931_gap.txt
git rm -q --ignore-unmatch predict/history/00932_gap.txt
git rm -q --ignore-unmatch predict/history/00933_gap.txt
git rm -q --ignore-unmatch predict/history/00948_gap.txt
git rm -q --ignore-unmatch predict/history/00949_gap.txt
git rm -q --ignore-unmatch predict/history/00950_gap.txt
git rm -q --ignore-unmatch predict/history/00958_gap_l1_3.txt
git rm -q --ignore-unmatch predict/history/00959_gap_l1_3.txt
git rm -q --ignore-unmatch predict/history/00960_gap_l1_3.txt
git rm -q --ignore-unmatch predict/history/00961_gap_l1_3.txt
git rm -q --ignore-unmatch predict/history/00962_gap_l1_3.txt
git rm -q --ignore-unmatch predict/history/00963_gap_l1_3.txt
git rm -q --ignore-unmatch predict/history/00964_gap_l1_3.txt
git rm -q --ignore-unmatch predict/history/00965_gap_l1_3.txt
git rm -q --ignore-unmatch predict/history/00966_gap_l1_3.txt
git rm -q --ignore-unmatch predict/history/00967_gap_l1_3.txt
git rm -q --ignore-unmatch predict/history/00968_gap_l1_3.txt
git rm -q --ignore-unmatch predict/history/00969_gap_l1_3.txt
git rm -q --ignore-unmatch predict/history/00970_gap_l1_3.txt
git rm -q --ignore-unmatch predict/history/00971_gap_l1_3.txt
git rm -q --ignore-unmatch predict/history/00972_gap_l1_3.txt
git rm -q --ignore-unmatch predict/history/01571.txt
git rm -q --ignore-unmatch predict/history/01572.txt
git rm -q --ignore-unmatch predict/history/01573.txt
git rm -q --ignore-unmatch predict/next_draw_predict.txt
git rm -q --ignore-unmatch predict/next_draw_predict_count_gap.csv
git rm -q --ignore-unmatch predict/next_top3.csv
git rm -q --ignore-unmatch predict/strategy_stats.json
git add -A .github l0 l200 predict results compress_results.py l0_l200.py predict_l1_3_gap.py
git commit -m "nen results gzip, l0/l200, 1 du doan ngau nhien tu ve con lai" && git push
