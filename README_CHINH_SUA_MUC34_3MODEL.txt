CHINH SUA (ban rut gon): chi giu du doan muc 3 va 4, chi 3 model.

Model giu lai: 682305800400, 108477750639, 1903987714639.

Da lam:
- predict/consensus/: chi con file cua 3 model tren; moi file chi giu du doan muc 3 va muc 4.
- predict/next_draw_predict_consensus.txt: loc con 3 model, chi muc 3/4.
- Da xoa: predict/history/ (lich su khong ghi muc nen khong loc theo muc duoc),
  predict/next_draw_predict_app.txt, predict/next_draw_consensus.txt (bao cao tong hop).
- l1_merged/: chi giu merged_seed cua 3 model (da xoa 900477750639, 2261277038639, 2682875614639).
- predict_next_draw_consensus.py: PREFERRED_LEVELS mac dinh doi thanh "3,4".
- .github/workflows/scan_v2_auto.yml: job predict_next_consensus them PREFERRED_LEVELS: "3,4".

Khong dong den: cac script khac, workflow khac, l1_chunks_*, file state, data/.
Luu y: cac workflow scan/merge co the tao lai file l1_merged cua model da xoa.

BO SUNG (lan sua thu 2):
- HUONG_DAN_VE_DONG_THUAN.txt: giai thich co che ve dong thuan (danh cho nguoi/AI doc zip lan sau).
- explain_consensus_ticket.py: script doc-only de kiem chung/liet ke ve dong thuan theo model + ky.
- Dashboard (docs/index.html): moi ve du doan hien "Model {seed_start}", "muc N", "seed" tren MOI man hinh
  (truoc day seed bi an tren dien thoai) va danh sach seed dong thuan (bam de mo).
- predict/history/00905_consensus.txt khoi phuc lai (chi 6 ve muc 3/4 cua 3 model) o dinh dang 7 truong
  (them muc dong thuan + danh sach seed@ky); docs/data.json sinh lai tu file nay.
- lotto_common.py: save/load_prediction_history nhan them 2 truong tuy chon (tuong thich file 5 truong cu).
- predict_next_draw_consensus.py: ghi them level + seeds_detail vao lich su. generate_dashboard_data.py: dua chung vao data.json.

BO SUNG (lan sua thu 3): QUET L1 LEN 1000 KY, MODEL 682305800400 LEN 10 TY SEED, L2 LUU SEED THEO KY
- .github/workflows/scan_v2_auto.yml:
    FIXED_SEED_COUNT 1.557.775.799 -> 10.000.000.000 (model 682305800400, quet toan bo CSV ~904+ ky).
    ONCE/ONCE2/ONCE3/ONCE4/ONCE5_LAST_N_DRAWS: 60 (ONCE5: 1) -> 1000.
    timeout job model chinh 180 -> 350 phut (lan dau phai quet lai ca dai 10 ty: ~9e12 phep hash).
    prune_merged_seed.py: tran file model chinh 5MB -> 90MB; them buoc tia 90MB truoc "Commit ket qua" cua 5 job merge_once*
    (1000 ky x ~8.000 seed/ky ~ 110MB > gioi han 100MB cua GitHub; neu vuot se tia ky cu nhat).
- .github/workflows/scan_per_draw.yml (chay tay): cung FIXED_SEED_COUNT 10 ty, timeout 350.
- scan_per_draw.cpp: neu dai seed (seed_start/seed_end) cua file cu KHAC dai hien tai thi BO file cu va quet lai TAT CA ky
  (truoc day chi quet ky moi -> cac ky cu se khong co seed o phan dai moi mo rong, sai lech). Da kiem tra bien dich (g++ -fsyntax-only).
- check_l1_merged.py: file L2 (l2_merged/promoted_seed{X}.json) them "draws" = chi muc THEO KY (ky -> seed L2 trung), giu nguyen
  "promoted" (seed -> ky). Da test tren ban sao: 59 seed / 118 luot khop 2 chieu; predict_next_draw_consensus.load_l2_file van doc duoc.
  LUU Y: workflow hien KHONG goi check_l1_merged.py (xem README_SCAN_WINDOW.txt) nen L2 chi duoc tao khi ban chay script nay.
CHUA LAM (khong the lam o day): chua quet lai du lieu. Cac file l1_merged/ trong zip van la ban quet cu.
  Lan chay workflow dau tien se quet lai (model chinh ~2-6 gio; cac job chunk moi job ~1,5e12 phep hash).
LUU Y: app (github_seed_source.dart) doc THANG file model chinh qua CDN; file model chinh se tang tu ~5MB len ~30MB+.
LUU Y: model tu noi tiep (ONCE4/ONCE5) tao file MOI moi lan chay -> moi lan them ~90MB vao lich su git.
