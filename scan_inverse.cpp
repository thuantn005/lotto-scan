// scan_inverse.cpp - TIM SEED TRUNG J1 NHIEU LAN bang cach DAO ham hash (khong quet mu).
//
// ve(seed, d): combined = seed*M1 + d*M2 ; mixed = mix64(combined) ; rank = mixed % C ; special = mix64(mixed) % 12 + 1
// mix64 va phep nhan voi M1 deu KHAC 0 va kha nghich (mod 2^64) => voi 1 ky d1 cho truoc, MOI seed trung ky d1
// deu liet ke truc tiep duoc: mixed = r1 + C*k (k = 0..K-1), loc dac biet (1/12), roi suy nguoc ra seed.
// So seed trong KHONG GIAN 64-bit trung ky d1 la ~2^64/3.9tr = 4.7e12 (thay vi quet 1e19 seed).
// Moi ung vien da trung d1 -> kiem tra tiep ky d2 (1 lan hash, qua 1/3.9tr) -> song sot -> dem so ky trung tren TAT CA ky.
// => Voi 1 cap (d1,d2): tim DUOC MOI seed 64-bit trung ca d1 va d2 (~1.2 trieu seed) roi dem hit tren 971 ky.
//    Neu ham hash nay la bo sinh that voi seed 64-bit, seed that se co ~971 hit va phai nam trong tap nay.
//
// Dung: ./scan_inverse DRAWS_RANK.txt D1 D2 K_BEGIN K_END THREADS OUT.txt [MIN_HITS=3]
//   DRAWS_RANK.txt: moi dong "draw_id rank special" (data/draws_rank.txt)
//   k chay trong [K_BEGIN, K_END); K_total = ceil((2^64 - r1)/C) ~ 5.68e13 (in ra khi chay voi K_END=0)
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
using u64 = uint64_t;
constexpr u64 M1 = 0x9E3779B97F4A7C15ULL, M2 = 0xD1B54A32D192ED03ULL, M3 = 0xBF58476D1CE4E5B9ULL, M4 = 0x94D049BB133111EBULL;
constexpr u64 C = 324632;

static inline u64 mix64(u64 x) { x ^= x >> 30; x *= M3; x ^= x >> 27; x *= M4; x ^= x >> 31; return x; }
static u64 inv_mul(u64 a) { u64 x = a; for (int i = 0; i < 6; i++) x *= 2 - a * x; return x; }  // nghich dao mod 2^64 (a le)
static inline u64 inv_xs(u64 y, int s) { u64 x = y; for (int i = 0; i < 64 / s + 1; i++) x = y ^ (x >> s); return x; }
static u64 M3I, M4I, M1I;
static inline u64 inv_mix(u64 y) { y = inv_xs(y, 31); y *= M4I; y = inv_xs(y, 27); y *= M3I; y = inv_xs(y, 30); return y; }

struct Draw { int id; u64 rank; int sp; };

int main(int argc, char** argv) {
    if (argc < 8) { fprintf(stderr, "Dung: %s DRAWS_RANK.txt D1 D2 K_BEGIN K_END THREADS OUT.txt [MIN_HITS=3]\n", argv[0]); return 1; }
    M3I = inv_mul(M3); M4I = inv_mul(M4); M1I = inv_mul(M1);
    // tu kiem tra phep dao
    for (u64 t : {1ULL, 12345ULL, 0xDEADBEEFCAFEBABEULL, ~0ULL}) {
        if (inv_mix(mix64(t)) != t || mix64(inv_mix(t)) != t) { fprintf(stderr, "LOI phep dao mix64\n"); return 2; }
        if (t * M1 * M1I != t) { fprintf(stderr, "LOI nghich dao M1\n"); return 2; }
    }
    std::vector<Draw> draws; std::map<int, Draw> byid;
    { std::ifstream f(argv[1]); Draw d; while (f >> d.id >> d.rank >> d.sp) { draws.push_back(d); byid[d.id] = d; } }
    int D1 = atoi(argv[2]), D2 = atoi(argv[3]);
    u64 kb = strtoull(argv[4], 0, 10), ke = strtoull(argv[5], 0, 10); int nt = atoi(argv[6]);
    int minhits = argc > 8 ? atoi(argv[8]) : 3;
    Draw a = byid.at(D1), b = byid.at(D2);
    u64 Ktot = (~0ULL - a.rank) / C + 1;              // so k hop le: a.rank + C*k <= 2^64-1
    if (ke == 0 || ke > Ktot) ke = Ktot;
    fprintf(stderr, "d1=%d (rank %llu, sp %d) d2=%d | K_total=%llu | chay k=[%llu,%llu)\n", D1, (unsigned long long)a.rank, a.sp, D2,
            (unsigned long long)Ktot, (unsigned long long)kb, (unsigned long long)ke);
    const u64 off12 = (u64)(D2 - D1) * M2, offd1 = (u64)D1 * M2;
    std::atomic<u64> next(kb), cand(0), surv(0); std::mutex mu; std::ofstream out(argv[7]);
    std::map<int, u64> hist; const u64 CH = 1 << 22; auto t0 = std::chrono::steady_clock::now();
    auto work = [&]() {
        u64 lc = 0, ls = 0; std::map<int, u64> lh;
        for (;;) {
            u64 s = next.fetch_add(CH); if (s >= ke) break; u64 e = s + CH < ke ? s + CH : ke;
            for (u64 k = s; k < e; k++) {
                u64 mixed = a.rank + C * k;
                if (mix64(mixed) % 12 != (u64)(a.sp - 1)) continue;          // dac biet ky d1
                lc++;
                u64 comb = inv_mix(mixed);                                    // = seed*M1 + d1*M2
                u64 m2 = mix64(comb + off12);                                 // ky d2
                if (m2 % C != b.rank) continue;
                if (mix64(m2) % 12 != (u64)(b.sp - 1)) continue;
                ls++;
                u64 seed = (comb - offd1) * M1I; int hits = 0; std::vector<int> hl;
                for (auto& d : draws) {
                    u64 mx = mix64(seed * M1 + (u64)d.id * M2);
                    if (mx % C == d.rank && mix64(mx) % 12 == (u64)(d.sp - 1)) { hits++; hl.push_back(d.id); }
                }
                lh[hits]++;
                if (hits >= minhits) {
                    std::lock_guard<std::mutex> g(mu);
                    out << seed << " " << hits << " "; for (size_t i = 0; i < hl.size(); i++) out << (i ? "," : "") << hl[i]; out << "\n"; out.flush();
                }
            }
        }
        cand += lc; surv += ls; std::lock_guard<std::mutex> g(mu); for (auto& p : lh) hist[p.first] += p.second;
    };
    std::vector<std::thread> th; for (int i = 0; i < nt; i++) th.emplace_back(work); for (auto& t : th) t.join();
    double sec = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
    printf("k=[%llu,%llu) | ung vien trung d1: %llu | song sot (trung ca d1,d2): %llu | %.1fs (%.1f trieu k/s)\n",
           (unsigned long long)kb, (unsigned long long)ke, (unsigned long long)cand.load(), (unsigned long long)surv.load(), sec, (ke - kb) / sec / 1e6);
    printf("Phan bo so hit (tren %zu ky) cua cac seed song sot:", draws.size()); for (auto& p : hist) printf(" %d:%llu", p.first, (unsigned long long)p.second); printf("\n");
    return 0;
}
