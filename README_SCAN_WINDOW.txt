GHI CHU - GIAM CUA SO QUET XUONG 60 KY + BO THANG HANG
==========================================================================

CACH AP DUNG: giai nen DE LEN .github/workflows/scan_v2_auto.yml (ghi
de file nay), roi commit + push. KHONG can sua scan_per_draw.cpp hay
check_l1_merged.py - ca 2 file nay giu NGUYEN, khong thay doi.

VAN DE GOC: full_scan/check_l1_merged lam viec voi TOAN BO lich su +
TOAN BO seed da tich luy - cang ve sau cang cham va "qua nhieu seed de
chon" (birthday paradox voi pool khong ngung phinh to). Giai phap: thu
hep cua so quet + bo han buoc thang hang.

1. Giam cua so quet tu 500 xuong 60 ky:
   ONCE_LAST_N_DRAWS:  500 -> 60
   ONCE2_LAST_N_DRAWS: 500 -> 60
   ONCE3_LAST_N_DRAWS: 500 -> 60
   ONCE4_LAST_N_DRAWS: 500 -> 60
   (ONCE5_LAST_N_DRAWS giu nguyen = 1, khong doi - day la model rieng
   chi quet 1 ky/lan, khong lien quan)

   scan_per_draw.cpp DA CO SAN co che nay (tham so LAST_N_DRAWS, xem
   docstring dau file) - chi can doi gia tri bien moi truong, KHONG
   can sua code C++. Da kiem chung THAT: khi co ky moi can quet, file
   l1_merged se TU DONG cat tia ve dung 60 ky gan nhat (khong con phinh
   to vo han theo thoi gian) - xem chi tiet trong lich su chat.

2. Bo han 6 buoc "Thang hang (promote) seed... sang l2_merged" (goi
   check_l1_merged.py) khoi TAT CA cac job trong workflow (predict
   scripts van doc l2_merged neu co, nhung se KHONG CON du lieu MOI
   duoc them vao nua tu day tro di - du lieu l2_merged hien co van con
   nguyen nhu lich su cu, chi khong tang truong them).

KET QUA MONG DOI:
  - File l1_merged/*.json se on dinh o quy mo ~60 ky (thay vi 500+ ky
    nhu truoc), giam manh so luong seed tich luy => giam "qua nhieu
    seed de chon", giam thoi gian cac buoc predict/backtest xu ly.
  - Khong con file l2_merged/*.json moi duoc tao/cap nhat - cac chien
    luoc du doan/backtest (consensus, ai/ai2/ai3) van hoat dong binh
    thuong vi da co san logic fallback khi khong co L2 (chi dung L1).

LUU Y: sau khi ap dung, LAN CHAY DAU TIEN cua moi model (once/once2/
once3/once4) se PHAI QUET LAI toan bo 60 ky (vi file l1_merged hien
tai dang co du lieu cua cua so 500 ky cu, khong khop cua so 60 ky
moi) - day la hanh vi BINH THUONG, chi xay ra 1 lan, sau do se on
dinh nhu thiet ke.
