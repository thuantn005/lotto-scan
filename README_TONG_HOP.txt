GHI CHU - BAN VA CUOI CUNG (AI + Consensus + Backtest, da don gian hoa pipeline)
==========================================================================

CACH AP DUNG: giai nen DE LEN thu muc goc cua repo lotto-scan (ghi de
10 file .py + 1 file .yml duoi day), roi commit + push binh thuong.
Khong dong cham gi den du lieu (data/, l1_*, l2_*, once*_seed_state.json...).

=== TOM TAT PIPELINE SAU CUNG ===

Chuoi push tuan tu trong scan_v2_auto.yml (da BO chien luoc "base"):
  predict_next_app -> predict_next_ai -> predict_next_ai2
  -> predict_next_ai3 -> predict_next_consensus -> predict_consensus
  (bao cao tong hop) -> cleanup_l1

Con 5 chien luoc dang chay: app, ai (Gemini), ai2 (Groq), ai3
(OpenRouter), consensus. Da BO han chien luoc "base" (predict_next.py
van con trong repo, chi khong con duoc goi tu workflow nua - co the
xoa file nay neu muon, hoac giu lai de chay tay/doi chieu rieng).

1. lotto_common.py - khong doi gi them so voi ban truoc (van giu cac
   ham get_gaps_from_l2_file/dir tu ban vá AI dau tien, du hien AI
   khong con dung chung nua - xem muc 3).

2. predict_next_draw.py (chien luoc "base") - VAN con fix bug
   random.Random(tuple) tu truoc, nhung KHONG con duoc goi trong
   workflow (da bo job predict_next). Neu muon xoa han khoi repo, tu
   xoa file nay + xoa job "check_prediction" NEU no chi phu thuoc
   base (thuc ra check_prediction_result.py doc TAT CA chien luoc qua
   glob nen van giu duoc, khong can sua).

3. predict_next_draw_ai.py / ai2.py / ai3.py (Gemini / Groq / OpenRouter)
   - THAY DOI QUAN TRONG: KHONG con dung co che "khoang cach trung
     binh" (avg_gap) nua. Gio dung LAI CHINH co che cua chien luoc
     "consensus" (import truc tiep tu predict_next_draw_consensus.py):
     voi moi model, lay cac VE dat MUC DO DONG THUAN 5, 6, 7 (so seed
     doc lap cung cho ra 1 ve) lam UNG VIEN, roi GUI CHO AI CHON 1 ve
     + giai thich - thay vi AI tu "bia" tu candidate rieng le nhu ban
     truoc.
   - Ham dung chung moi: collect_candidates_for_ai(),
     build_ai_prompt_levels() (dinh nghia trong
     predict_next_draw_consensus.py, muc 4).
   - ENV moi: LEVELS (mac dinh "5,6,7"), TICKETS_PER_LEVEL_AI (mac
     dinh 3 - so ve toi da lay lam ung vien MOI muc, truoc khi loai
     trung). Khong con GAP_SMOOTH_WINDOW/CANDIDATES_PER_MODEL/L2_DIR
     kieu cu (L2_DIR van con dung de tim file L2 tuong ung tung
     model).
   - Van can 1 trong 3 secret: GEMINI_API_KEY / GROQ_API_KEY /
     OPENROUTER_API_KEY.

4. predict_next_draw_consensus.py (chien luoc "consensus" + ham dung
   chung cho AI)
   - Moi model, MOI muc dong thuan trong danh sach cua model do sinh
     ra TICKETS_PER_LEVEL (mac dinh 2) VE RIENG (KHONG con "chon 1 ve
     tot nhat trong khoang").
   - DEM DUNG theo SEED DOC LAP (da khu trung seed truoc khi tinh
     hash) - FIX BUG quan trong: truoc day 1 seed L2 co 2+ lan trung
     se bi dem THUA thanh 2+ "seed" khac nhau.
   - Muc mac dinh DA GIAM (theo yeu cau): PREFERRED_LEVELS mac dinh
     chi con "4" (da bo 5,6,7 - nhung 5,6,7 van dung o cho AI, xem
     muc 3). MODEL_LEVELS mac dinh:
       {"682305800400": [2], "1903987714639": [2, 3, 4]}
   - MOI: MIN_MODEL_SEEDS (mac dinh 100000) - TU DONG BO QUA model co
     qua it du lieu (vi du model moi chi co 1 ky nhu
     1825099814639 - se bi loai, khong sinh du doan "rac" tu du lieu
     qua it).
   - MOI: neu 1 muc phai fallback (khong dat dung yeu cau) VA ket qua
     TRUNG Y HET 1 ve fallback DA IN TRUOC DO cho model nay, se BO QUA
     khong in lap lai (tranh hien thi 2+ "ve" giong het nhau gay hieu
     lam nhu bug da phat hien truoc).
   - Ham moi cho AI dung: collect_candidates_for_ai(l1_fp, l2_fp,
     seed_start, next_draw_id, rank_to_mask, levels, tickets_per_level)
     va build_ai_prompt_levels(...) - xem muc 3.
   - Ghi vao predict/next_draw_predict_consensus.txt +
     predict/history/{ky}_consensus.txt (dung chuan de
     check_prediction_result.py/dashboard tu nhan dien).

5. find_consensus_tickets.py, backtest_consensus_batch.py - cong cu
   phan tich/backtest phien ban DAU (1 ve/muc, argmax/top). Van giu
   nguyen, dung de doi chieu/tham khao.

6. backtest_consensus_levels_batch.py - backtest MO PHONG DUNG logic
   san xuat hien tai cua predict_next_draw_consensus.py (nhieu
   muc/model, 2 ve/muc, dem theo seed doc lap DA khu trung, GOP DUNG
   ca L1+L2). Da toi uu tot do: khu trung 1 LAN duy nhat luc load
   (khong lap lai moi ky) - full backtest ~894 ky chay trong ~5 phut.
   KET QUA DA CHAY (xem predict/backtest_consensus_levels_v2_*.csv):
   894 ky, 18.706 ve, trung binh 0.7250/5 (ngau nhien ~0.7143/5), 1
   lan trung tuyet doi (ky 392) - DA XAC MINH day CHI la 1 seed DUY
   NHAT may man (n_seed_actual=1, matched_exact=False, KHONG PHAI 5
   seed dong thuan that nhu nhan "muc 5" gay hieu lam luc dau) - xem
   giai thich chi tiet trong lich su chat.

7. backtest_coverage_batch.py - MOI: model "PHU RONG" - moi model moi
   ky lay TOP-N ve KHAC NHAU (N cau hinh qua N_LIST, vi du
   10/50/200/1000), CHUNG MINH BANG SO LIEU THAT rang tang N (mua
   nhieu ve hon) KHONG lam tang ty le trung mot cach "thong minh" -
   chi la phep toan phu so hoc thuan tuy (xac suat trung tang tuyen
   tinh theo N/3.895.584, DA kiem chung: ca N=10 va N=1000 deu chi co
   DUNG 1 lan trung tuyet doi - CHINH LA lan trung ngau nhien o ky 392
   noi tren, khong co lan nao THEM du N tang gap 100 lan).

8. .github/workflows/scan_v2_auto.yml
   - BO HAN job "predict_next" (chien luoc base).
   - Giu/khoi phuc du 3 job predict_next_ai/ai2/ai3 (dung co che moi -
     candidates tu muc 5,6,7 cua consensus, xem muc 3).
   - Giu job predict_next_consensus (chien luoc consensus, dung
     PREFERRED_LEVELS/MODEL_LEVELS moi - muc 4).
   - Chuoi needs day du (da kiem tra bang PyYAML, 19 job hop le):
     predict_next_app -> predict_next_ai -> predict_next_ai2 ->
     predict_next_ai3 -> predict_next_consensus -> predict_consensus
     -> cleanup_l1

DA KIEM TRA TRUOC KHI GIAO (tren dung du lieu ban vua upload gan nhat -
ky 00895):
  - Cu phap Python ca 10 file .py: OK (ast.parse).
  - Cu phap + so luong job (19) trong .yml: OK (PyYAML).
  - predict_next_draw_consensus.py: chay dung, tu dong loai model
    1825099814639 (du lieu qua it), chi con muc 2/3/4, khong con vé
    trung lap.
  - predict_next_draw_ai.py (test khong goi API that): thu thap ung
    vien muc 5,6,7 thanh cong tren ca 6 model, build prompt hop le
    (~17.860 ky tu voi 6 model), import ai2.py/ai3.py khong loi.
  - backtest_consensus_levels_batch.py + backtest_coverage_batch.py:
    da chay FULL tren 894 ky, ket qua nhu muc 6-7 o tren.

CHUA kiem tra duoc (can ban tu chay tren GitHub Actions, vi phai goi
API that): dinh dang JSON thuc te Gemini/Groq/OpenRouter tra ve co
dung {"picks": [...]} voi "seed" nam trong danh sach ung vien MOI
(list seed/ve, khong con 1-seed-1-candidate nhu truoc) hay khong -
neu AI tra loi 1 seed khong khop bat ky ve nao, script se bo qua pick
do (khong crash).
