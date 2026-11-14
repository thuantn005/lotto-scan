#!/usr/bin/env python3
# QUET HET cap con thieu tren MAY CUA BAN (khong dung GitHub-hosted runner): doc danh sach gz tren Release, quet cap thieu tu moi -> cu, up Release tung cap.
#   python3 quet_het_local.py lotto535|mega [--tag TAG] [--limit N] [--dry-run] [--list-file FILE]
# Cap thieu = (a, a+1) voi a = ky moi nhat-1, -3, -5 ... xuong 1 (cach 2 ky) chua co gz tren Release. Cap moi nhat (neu da co ket qua) duoc quet truoc.
# Dung lai/chay lai an toan: cap nao da co tren Release thi bo qua. Moi cap goi quet_local.py (Mega ~2 gio-nhan, Lotto ~50 gio-nhan).
import sys, os, re, subprocess, argparse
ap = argparse.ArgumentParser(); ap.add_argument('game', choices=['lotto535', 'mega']); ap.add_argument('--tag'); ap.add_argument('--limit', type=int, default=0)
ap.add_argument('--dry-run', action='store_true'); ap.add_argument('--list-file'); a = ap.parse_args()
LOTTO = a.game == 'lotto535'; tag = a.tag or ('lotto535-inverse-archive' if LOTTO else 'mega-inverse-archive')
subprocess.run([sys.executable, 'make_draws_rank.py' if LOTTO else 'make_draws_rank_mega.py'], check=True, stdout=subprocess.DEVNULL)
latest = max(int(l.split()[0]) for l in open(os.path.join('data', 'draws_rank.txt' if LOTTO else 'draws_rank_mega.txt')) if l.strip())
txt = open(a.list_file).read() if a.list_file else subprocess.run(['gh', 'release', 'view', tag, '--json', 'assets', '-q', '.assets[].name'], capture_output=True, text=True, check=True).stdout
pat = re.compile(r'first2_(?:mega_)?(\d+)_(\d+)\.txt\.gz'); have = {(int(m.group(1)), int(m.group(2))) for m in pat.finditer(txt)}
todo = [(x, x + 1) for x in range(latest - 1, 0, -2) if (x, x + 1) not in have]
print(f'{a.game}: ky moi nhat {latest}, co {len(have)} cap tren Release, thieu {len(todo)} cap (vd: {todo[:3]})')
if a.limit: todo = todo[:a.limit]
for d1, d2 in todo:
    if a.dry_run: print('se quet', d1, d2); continue
    subprocess.run([sys.executable, 'quet_local.py', a.game, str(d1), str(d2), '--upload', tag], check=True)
