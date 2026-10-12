M3DSCAN - Quet seed trung >= 2 ky J1 MAX 3D PRO (giong j2scan, 20 job GitHub Actions)
=====================================================================================
GIA DINH: bo sinh ve = rank = mix64(seed*M1 + draw_id*M2) % 1.000.000 -> a = rank/1000, b = rank%1000
(giong lotto-scan). Neu app Max 3D Pro sinh khac thi ket qua khong dung.
MODE=ordered : trung khi (a,b) = (s1,s2) [Dac biet]        MODE=either : them (s2,s1) [Dac biet phu]

FILE: .github/workflows/m3dscan_bands.yml | m3dscan/scan_m3d.cpp | m3dscan/gen_exclusion_m3d.py | m3dscan/data_special.txt (755 ky, den #755 (21/07/2026))
CAI DAT: giai nen vao goc repo CONG KHAI -> Actions -> "M3DSCAN" -> Run workflow: first_band=0, min_hits=2, mode=either,
  last_band=50 (either, phu het ~51 dai) hoac mode=ordered, last_band=203 (~204 dai). Cac dai chay noi tiep tu dong.
SO LIEU (ly thuyet, 755 ky, dai 249,2 ty seed): ordered ~70.900 seed trung/dai; either ~283.800 seed trung/dai.
  Do thuc: ~560k seed/s/nhan (1 nhan, 755 ky); 3 trieu seed dau: 2.267 seed >=1 ky (ordered, ky vong 2.265), 4.497 (either, ky vong 4.530).
  UOC TINH (chua do tren runner): ~93 phut/dai (20 job x 4 vCPU) -> either ~3,3 ngay, ordered ~13 ngay.
SINH VE: python3 m3dscan/gen_exclusion_m3d.py --draw 756 --remaining con_lai_756.txt
LUU Y: loai/phu khong tang xac suat trung (1/1.000.000 moi ve moi ky).
