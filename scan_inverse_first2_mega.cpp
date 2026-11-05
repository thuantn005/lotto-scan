// scan_inverse_first2_mega.cpp - Mega 6/45: tim MOI seed 64-bit co J1 (6 so) dau tien = D1, thu hai = D2 (D1 < D2)
// ve(seed, d): combined = seed*M1 + d*M2 ; mixed = mix64(combined) ; rank = mixed % C  (C = C(45,6) = 8145060, colex rank)
// Khong co so dac biet. Voi D1 cho truoc: mixed = r1 + C*k, k = 0..K-1 -> seed = (inv_mix(mixed) - D1*M2) * M1^-1.
// K_total = ceil((2^64 - r1)/C) ~ 2.26e12. Moi ung vien kiem tra tiep ky D2 (qua ~1/8.1 trieu), song sot -> dem hit tren TAT CA ky.
// => 1 cap (d1,d2) cho ~2^64/C^2 = ~278 nghin seed.
// Dung: ./scan_inverse_first2_mega DRAWS_RANK.txt D1 D2 K_BEGIN K_END THREADS OUT.txt [MIN_HITS=2]
//   DRAWS_RANK.txt: moi dong "draw_id rank sp" (sp bo qua)
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <vector>
#include <thread>
#include <atomic>
#include <mutex>
#include <chrono>
#include <fstream>
#include <map>
#include <algorithm>
using u64 = uint64_t;
constexpr u64 M1 = 0x9E3779B97F4A7C15ULL, M2 = 0xD1B54A32D192ED03ULL, M3 = 0xBF58476D1CE4E5B9ULL, M4 = 0x94D049BB133111EBULL;
constexpr u64 C = 8145060ULL;
static inline u64 mix64(u64 x) { x ^= x >> 30; x *= M3; x ^= x >> 27; x *= M4; x ^= x >> 31; return x; }
static u64 inv_mul(u64 a) { u64 x = a; for (int i = 0; i < 6; i++) x *= 2 - a * x; return x; }
static inline u64 inv_xs(u64 y, int s) { u64 x = y; for (int t = s; t < 64; t += s) x ^= y >> t; return x; }  // (I+S)^-1 = I+S+S^2+...
static u64 M3I, M4I, M1I;
static inline u64 inv_mix(u64 y) { y = inv_xs(y, 31); y *= M4I; y = inv_xs(y, 27); y *= M3I; y = inv_xs(y, 30); return y; }
struct Draw { int id; u64 rank; int sp; };
int main(int argc, char** argv) {
    if (argc < 8) { fprintf(stderr, "Dung: %s DRAWS_RANK.txt D1 D2 K_BEGIN K_END THREADS OUT.txt [MIN_HITS=2]\n", argv[0]); return 1; }
    M3I = inv_mul(M3); M4I = inv_mul(M4); M1I = inv_mul(M1);
    for (u64 t : {1ULL, 12345ULL, 0xDEADBEEFCAFEBABEULL, ~0ULL}) {
        if (inv_mix(mix64(t)) != t || mix64(inv_mix(t)) != t) { fprintf(stderr, "LOI phep dao mix64\n"); return 2; }
        if (t * M1 * M1I != t) { fprintf(stderr, "LOI nghich dao M1\n"); return 2; }
    }
    std::vector<Draw> draws; std::map<int, Draw> byid;
    { std::ifstream f(argv[1]); Draw d; while (f >> d.id >> d.rank >> d.sp) { draws.push_back(d); byid[d.id] = d; } }
    int D1 = atoi(argv[2]), D2 = atoi(argv[3]);
    u64 kb = strtoull(argv[4], 0, 10), ke = strtoull(argv[5], 0, 10); int nt = atoi(argv[6]);
    int minhits = argc > 8 ? atoi(argv[8]) : 2;
    if (D1 >= D2) { fprintf(stderr, "Can D1 < D2\n"); return 1; }
    std::sort(draws.begin(), draws.end(), [](const Draw& x, const Draw& y) { return x.id < y.id; });
    Draw a = byid.at(D1), b = byid.at(D2);
    u64 Ktot = (~0ULL - a.rank) / C + 1;
    if (ke == 0 || ke > Ktot) ke = Ktot;
    fprintf(stderr, "d1=%d (rank %llu) d2=%d (rank %llu) | K_total=%llu | chay k=[%llu,%llu)\n", D1, (unsigned long long)a.rank, D2,
            (unsigned long long)b.rank, (unsigned long long)Ktot, (unsigned long long)kb, (unsigned long long)ke);
    const u64 off12 = (u64)(D2 - D1) * M2, offd1 = (u64)D1 * M2;
    std::atomic<u64> next(kb), surv(0), rej(0); std::mutex mu; std::ofstream out(argv[7]);
    std::map<int, u64> hist; const u64 CH = 1 << 22; auto t0 = std::chrono::steady_clock::now();
    auto work = [&]() {
        u64 ls = 0, lrej = 0; std::map<int, u64> lh;
        for (;;) {
            u64 s = next.fetch_add(CH); if (s >= ke) break; u64 e = s + CH < ke ? s + CH : ke;
            for (u64 k = s; k < e; k++) {
                u64 comb = inv_mix(a.rank + C * k);                 // = seed*M1 + d1*M2
                if (mix64(comb + off12) % C != b.rank) continue;     // ky d2
                ls++;
                u64 seed = (comb - offd1) * M1I; int hits = 0; std::vector<int> hl; bool ok = true;
                for (auto& d : draws) {
                    if (mix64(seed * M1 + (u64)d.id * M2) % C == d.rank) {
                        if (d.id < D2 && d.id != D1) { ok = false; break; }
                        hits++; hl.push_back(d.id);
                    }
                }
                if (!ok) { lrej++; continue; }
                lh[hits]++;
                if (hits >= minhits) {
                    std::lock_guard<std::mutex> g(mu);
                    out << seed << " " << hits << " "; for (size_t i = 0; i < hl.size(); i++) out << (i ? "," : "") << hl[i]; out << "\n"; out.flush();
                }
            }
        }
        surv += ls; rej += lrej; std::lock_guard<std::mutex> g(mu); for (auto& p : lh) hist[p.first] += p.second;
    };
    std::vector<std::thread> th; for (int i = 0; i < nt; i++) th.emplace_back(work); for (auto& t : th) t.join();
    double sec = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
    printf("k=[%llu,%llu) | song sot (trung ca d1,d2): %llu | loai (co hit truoc d1 / giua d1,d2): %llu | %.1fs (%.2f trieu k/s)\n",
           (unsigned long long)kb, (unsigned long long)ke, (unsigned long long)surv.load(), (unsigned long long)rej.load(), sec, (ke - kb) / sec / 1e6);
    printf("Phan bo so hit (tren %zu ky) cua cac seed hop le:", draws.size()); for (auto& p : hist) printf(" %d:%llu", p.first, (unsigned long long)p.second); printf("\n");
    return 0;
}
