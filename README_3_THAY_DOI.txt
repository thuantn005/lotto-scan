GHI CHU - 3 THAY DOI (khong lien quan nhau, giai nen de len dung vi tri)
==========================================================================

1. predict_next_draw_consensus.py
   - MOI MODEL 1 FILE RIENG (thay vi 1 file gop chung):
     predict/consensus/next_draw_predict_{seed_start}.txt
     Vi du: predict/consensus/next_draw_predict_682305800400.txt
   - FIX BUG: xoa 1 dong in trung lap (lines_out.append(line) bi lap 2
     lan) tu ban truoc.
   - Logic du doan (muc dong thuan linh hoat 2-7, moi muc 1 ve, chi giu
     ve thu 2 trong 2 ve boc duoc, tu dong bo model it du lieu...)
     KHONG doi gi them so voi ban truoc.

2. .github/workflows/scan_v2_auto.yml
   - Giam cua so quet ONCE/ONCE2/ONCE3/ONCE4_LAST_N_DRAWS: 500 -> 60
     (ONCE5 giu nguyen = 1).
   - Xoa 6 buoc "Thang hang (promote)... sang l2_merged" (goi
     check_l1_merged.py) - KHONG con thang hang L1->L2 nua.
   - scan_per_draw.cpp/check_l1_merged.py giu NGUYEN, khong sua code -
     scan_per_draw.cpp da co san co che LAST_N_DRAWS, da kiem chung
     THAT: khi co ky moi, file se TU DONG cat tia ve dung 60 ky gan
     nhat.
   - LUU Y: lan chay dau tien sau khi ap dung se phai quet lai het 60
     ky (vi file hien tai dang khop cua so 500 ky cu) - chi xay ra 1
     lan, sau do on dinh.

3. docs/index.html
   - FIX loi "du lieu cu, phai tai lai trang moi thay du lieu moi" (o
     lan tai dau tien sau khi co ky moi/du doan moi): them cache-busting
     query param (?v=timestamp) vao URL fetch('./data.json') - vi
     'cache: no-store' cua trinh duyet KHONG chan duoc CDN cua GitHub
     Pages (Fastly) van co the phuc vu ban data.json CU trong vai phut
     sau khi deploy, do URL khong doi. Them query param ep CDN coi day
     la 1 URL KHAC, buoc phai lay ban moi nhat.

DA KIEM TRA:
  - predict_next_draw_consensus.py: cu phap OK, chay thu tren du lieu
    that (ky 899), ra dung 6 file rieng trong predict/consensus/, ten
    file dung dinh dang yeu cau.
  - scan_v2_auto.yml: YAML hop le (19 job), da test THAT hanh vi cat
    tia 60 ky cua scan_per_draw.cpp tren du lieu that (khong sua code).
  - docs/index.html: cu phap JS OK (node --check).
