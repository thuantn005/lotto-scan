J2SCAN - Quet seed trung >= 2 ky 5/5 SO CHINH (khong can DB), 20 job tren GitHub Actions
=========================================================================================

KHONG GHI DE FILE GOC: toan bo nam trong thu muc moi j2scan/ va 1 workflow moi
.github/workflows/j2scan_bands.yml. Khong sua, khong ghi de bat ky file nao cua repo.
Ket qua quet ghi vao j2scan/out/ (thu muc moi).

NOI DUNG
  .github/workflows/j2scan_bands.yml   Workflow 20 job song song
  j2scan/scan_j2.cpp                   Bo quet toi uu (~498k seed/s/nhan do tren may thu; scan_j1.cpp goc: 82k)
  j2scan/gen_exclusion.py              Sinh ve loai / ve con lai cho 1 ky tu cac seed da quet
  j2scan/data_frozen.csv               Ban sao dong bang cua data/all.csv (den ky #00932), de cac dai quet dong nhat

CAI DAT
  1. Giai nen vao THU MUC GOC repo (cac duong dan deu moi, khong trung file cu).
  2. Repo phai CONG KHAI (runner mien phi 4 vCPU). Repo private chi co 2000 phut/thang -> khong du.
  3. Tab Actions -> "J2SCAN - Scan J2 (5 so chinh, 2 lan) - 20 job" -> Run workflow, chi can first_band = 0
     (cac tham so khac giu mac dinh):
       band_size = 249244128000 (8 x 31,16 ty), bands = 1, min_hits = 2, auto_next = true, last_band = 4
  4. Chay noi tiep tung dai: xong 20 job cua dai N -> tu kich hoat dai N+1 den last_band.
     Moi dai commit 1 file j2scan/out/j2_b<N>_<N>.txt (moi dong: "seed so_ky_trung").
     Loi giua chung: chain dung; xem j2scan/out/j2_missing_*.txt; chay lai voi first_band = N.

SO LIEU (ly thuyet, kiem chung 40 trieu seed dau: 164 seed so voi 165 ky vong)
  Dai 249,2 ty ~ 1.025.000 seed trung >= 2 ky 5/5 so chinh; moi job ~ 160 phut (uoc tinh, chua do tren runner that).
  Muc loai (324.632 to hop 5 so): 50% = 1 dai | 90% = 1 | 99% = 2 (last_band=1) | 100% = 5 (last_band=4) ; 5 dai noi tiep ~ 14 gio.
  Gioi han an toan: bands*band_size/20 <= 19 ty seed/job. GIU NGUYEN band_size trong 1 chuoi quet.

SINH VE LOAI CHO MOT KY (vi du ky 934)
  python3 j2scan/gen_exclusion.py --draw 934 --remaining j2scan/out/con_lai_934.txt
  -> loai_ve_934.txt (ve bi loai, ghi o thu muc hien tai; dung --out de doi), con_lai_934.txt (to hop con lai)

LUU Y
  - Seed trung 2 lan chi la tinh co; loai ve theo cach nay KHONG tang xac suat trung (1/324.632 moi ve).
  - Loai 100% to hop thi khong con ve nao de chon. Cac chu so thoi gian/chi phi chi la uoc tinh.
