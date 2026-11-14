#!/usr/bin/env python3
# QUET CAP TREN MAY CUA BAN (khong dung GitHub-hosted runner) -> gz -> (tuy chon) up Release.
#   python3 quet_local.py lotto535|mega D1 D2 [--chunks 20] [--upload TAG] [--min-hits 2] [--kmax K]   (--kmax chi de thu nhanh)
# Dung dung scan_inverse_first2(.mega).cpp; chay lan luot tung phan bang TAT CA nhan CPU, co the dung lai: phan nao xong thi bo qua (thu muc quet_tmp/).
# Mot cap Lotto ~25 gio-CPU, Mega ~1,5 gio-CPU (ky 1587). Co the chay song song nhieu may bang cach chia cap khac nhau.
import sys, os, subprocess, argparse, gzip, shutil
ap = argparse.ArgumentParser(); ap.add_argument('game', choices=['lotto535', 'mega']); ap.add_argument('d1', type=int); ap.add_argument('d2', type=int)
ap.add_argument('--chunks', type=int, default=20); ap.add_argument('--min-hits', type=int, default=2); ap.add_argument('--upload'); ap.add_argument('--kmax', type=int, default=0)
a = ap.parse_args(); LOTTO = a.game == 'lotto535'
src = 'scan_inverse_first2.cpp' if LOTTO else 'scan_inverse_first2_mega.cpp'; exe = os.path.abspath('scanner_' + a.game)
rank = os.path.join('data', 'draws_rank.txt' if LOTTO else 'draws_rank_mega.txt')
subprocess.run([sys.executable, 'make_draws_rank.py' if LOTTO else 'make_draws_rank_mega.py'], check=True, stdout=subprocess.DEVNULL)
if not os.path.exists(exe) or os.path.getmtime(exe) < os.path.getmtime(src):
    subprocess.run(['g++', '-O3', '-march=native', '-pthread', '-std=c++17', src, '-o', exe], check=True)
rows = {int(l.split()[0]): int(l.split()[1]) for l in open(rank) if l.strip()}
assert a.d1 in rows and a.d2 in rows, 'chua co ket qua ky d1/d2'
K = (2 ** 64 - 1 - rows[a.d1]) // (324632 if LOTTO else 8145060) + 1
if a.kmax: K = min(K, a.kmax)
tmp = f'quet_tmp/{a.game}_{a.d1}_{a.d2}'; os.makedirs(tmp, exist_ok=True); nproc = os.cpu_count() or 1
for P in range(a.chunks):
    out = f'{tmp}/out_{P}.txt'
    if os.path.exists(out + '.done'): print('phan', P, 'da xong, bo qua'); continue
    kb, ke = K * P // a.chunks, K * (P + 1) // a.chunks
    print(f'phan {P + 1}/{a.chunks}: k [{kb}, {ke})', flush=True)
    with open(f'{tmp}/summary_{P}.txt', 'w') as sm:
        subprocess.run([exe, rank, str(a.d1), str(a.d2), str(kb), str(ke), str(nproc), out, str(a.min_hits)], check=True, stdout=sm)
    open(out + '.done', 'w').close()
lines = []
for P in range(a.chunks): lines += open(f'{tmp}/out_{P}.txt').read().splitlines()
lines = [l for l in lines if l.strip()]; lines.sort(key=lambda l: -int(l.split()[1]))
name = f'first2_{"" if LOTTO else "mega_"}{a.d1}_{a.d2}.txt.gz'
with gzip.open(name, 'wt', compresslevel=9) as g: g.write('\n'.join(lines) + '\n')
print(f'{len(lines):,} seed -> {name}')
if a.upload:
    subprocess.run(f'gh release view {a.upload} >/dev/null 2>&1 || gh release create {a.upload} --title "{a.game} inverse archive" --notes "first2 gz"', shell=True, check=True)
    subprocess.run(['gh', 'release', 'upload', a.upload, name, '--clobber'], check=True); print('da up Release', a.upload)
shutil.rmtree(tmp, ignore_errors=True)
