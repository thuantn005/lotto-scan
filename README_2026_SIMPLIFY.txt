GHI CHU - DON GIAN HOA LON (2026-09)
=====================================

YEU CAU: bo tat ca model L1 quet, chi giu 2 model (900477750639 va
682305800400), moi ky 1 file (khong gop nua); L2 van la noi luu "ky ma
seed quet trung" (khong doi vai tro); phan du doan tinh lai theo khoang
cach GIUA CAC KY TRUNG, va SEED chon trong ky do CUNG chon theo khoang
cach (khong con random).

=== DA XOA ===
- Model: 108477750639, 1903987714639, 2932119742639, 2510521166639, va 2
  model seed-noi-tiep (once4/once5). Kem theo: l1_chunks_once/,
  l1_chunks_once2/, once_seed_state.json, once4_seed_state.json,
  once5_seed_state.json, cac file l1_merged/merged_seed{X}.json tuong ung.
- Chien luoc du doan: base, app, ai (Gemini), ai2 (Groq), ai3 (OpenRouter),
  consensus, ml, random, seed - XOA HET cac file predict_next_draw*.py +
  predict_consensus.py + ml_scoring.py tuong ung. CHI CON 1 chien luoc:
  predict_next_draw_gap.py ("gap").

=== MODEL GIU LAI ===
- l1-1/  (seed_start 900477750639) - quet L1_1_LAST_N_DRAWS=200 ky gan
  nhat, song song 20 chunk (persist tai l1-1_chunks/).
- l1-2/  (seed_start 682305800400) - quet TOAN BO lich su CSV, 1 job don.

=== KIEN TRUC L1 MOI: MOI KY 1 FILE, KHONG GOP ===
l1-1/{draw_id}.json va l1-2/{draw_id}.json la DELIVERABLE thuc su (moi ky
1 file rieng, dinh dang giong batch_ky cu):
    {"draw_id":N,"draw_date":"...","seed_start":S,"seed_end":E,
     "found":F,"seeds":[...]}

l1_cache/merged_seed{X}.json CHI la cache noi bo (1 file gop) - can thiet
vi scan_per_draw.cpp doc lai file nay de biet ky nao DA quet (quet GIA
TANG, chi quet ky moi moi lan). Ngay sau khi scan xong, split_l1_per_draw.py
TACH cache thanh l1-1//l1-2/ (moi ky 1 file) - MOI script khac (thang hang
L2, du doan) chi doc tu l1-1/l1-2/, khong bao gio doc thang tu l1_cache/.

check_l1_per_draw.py thay the check_l1_merged.py: lam viec tren THU MUC
per-draw thay vi 1 file gop, nhung logic thang hang (weight >= 2) va vai
tro cua L2 GIU NGUYEN 100% - l2_merged/promoted_seed{X}.json van la noi
luu KY MA SEED DA QUET TRUNG (>=2 lan), khong lien quan gi den du doan.

=== CHIEN LUOC DU DOAN MOI: "gap" (predict_next_draw_gap.py) ===
Buoc 1 - CHON KY: tinh avg_draw_gap = trung binh khoang cach (so ky) GIUA
2 LAN TRUNG LIEN TIEP cua cac seed da thang hang (L2). Voi tung seed con
cho trong L1, tinh gap = ky_sap_toi - lan_trung_gan_nhat. Chon NHOM gap
GAN avg_draw_gap NHAT.

Buoc 2 - CHON SEED (MOI - truoc day la random deu): trong nhom gap da
chon, tinh avg_seed_gap = trung binh khoang cach GIUA CAC GIA TRI SEED
(khong phai giua ky) da thang hang, sap tang dan. Voi tung seed ung vien,
tinh khoang cach toi seed da thang hang GAN NHAT, chon seed co khoang
cach GAN avg_seed_gap NHAT. Hoan toan xac dinh (deterministic), khong con
buoc nao dung random.

CANH BAO: day van CHI la gia thuyet thong ke, khong co bao dam gi ve
tuong lai.

=== CAC FILE KHONG DUNG NUA (con lai trong repo, MO CO) ===
find_consensus_tickets.py, explain_consensus_ticket.py,
backtest_consensus_batch.py, backtest_consensus_levels_batch.py,
backtest_coverage_batch.py, backtest_predictions.py - deu doc file
l1_merged/l2_merged theo dinh dang GOP CU, gio khong con dung nua vi
l1_merged/ da bi xoa va l2_merged/ gio dung dinh dang moi hon (van tuong
thich mot phan). CHUA XOA (de tham khao/doi chieu), nhung se loi neu chay
truc tiep - xoa hoac viet lai neu can dung tiep.

check_l1_merged.py, merge_l1_per_draw.py, prune_merged_seed.py van con
(dung boi workflow rieng scan_per_draw.yml - workflow_dispatch thu cong,
khong lien quan pipeline chinh). prune_merged_seed.py con duoc scan_v2_auto.yml
moi tai su dung de gioi han dung luong CACHE (l1_cache/).
