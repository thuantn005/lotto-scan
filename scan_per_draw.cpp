// scan_per_draw.cpp — Quet 1 dai seed CO DINH cho TAT CA cac ky trong CSV,
// moi ky ghi ra 1 file rieng dang batch_ky{draw_id}_seed{seed_start}.json
// (giong dung dinh dang batch_ky850_seed93466548001.json ma nguoi dung da co).
//
// Thuat toan giu nguyen 100% tu scan_v2.cpp (da kiem chung khop voi du lieu mau):
//   ticket(seed, draw_id) = unrank_colex( splitmix64_mix(seed*M1 + draw_id*M2) mod C(35,5) )
//   special = splitmix64_mix(mixed) mod 12 + 1
//
// ENV:
//   CSV_PATH     - duong dan file CSV cac ky quay (mac dinh data/all.csv)
//   OUT_DIR      - thu muc ghi file ket qua (mac dinh per_draw_scan)
//   SEED_START   - diem bat dau dai seed (mac dinh 682305800400)
//   SEED_COUNT   - so seed can quet (mac dinh 1557775799)
//   NUM_THREADS  - so luong thread (mac dinh = so core)

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <vector>
#include <string>
#include <fstream>
#include <sstream>
#include <chrono>
#include <algorithm>
#include <filesystem>
#include <thread>
#include <mutex>
#include <atomic>

namespace fs = std::filesystem;
using u64 = uint64_t;

constexpr u64 M1 = 0x9E3779B97F4A7C15ULL;
constexpr u64 M2 = 0xD1B54A32D192ED03ULL;
constexpr u64 M3 = 0xBF58476D1CE4E5B9ULL;
constexpr u64 M4 = 0x94D049BB133111EBULL;
constexpr int64_t C = 324632;

static int64_t BINOM[36][6];
static std::vector<int64_t> RANK_TO_MASK;

void build_binom() {
    for (int n = 0; n <= 35; n++)
        for (int k = 0; k <= 5; k++) {
            if (k == 0) { BINOM[n][k] = 1; continue; }
            if (k > n) { BINOM[n][k] = 0; continue; }
            int64_t num = 1, den = 1;
            for (int i = 0; i < k; i++) { num *= (n - i); den *= (i + 1); }
            BINOM[n][k] = num / den;
        }
}
inline int64_t rank_mask_calc(int64_t r) {
    int64_t mask = 0, rem = r;
    for (int k = 5; k >= 1; k--) {
        int x = k - 1;
        while (BINOM[x + 1][k] <= rem) x++;
        mask |= (1LL << x); rem -= BINOM[x][k];
    }
    return mask;
}
void build_lut() { RANK_TO_MASK.resize(C); for (int64_t r=0;r<C;r++) RANK_TO_MASK[r]=rank_mask_calc(r); }

inline u64 mix64(u64 x) {
    x ^= x >> 30; x *= M3; x ^= x >> 27; x *= M4; x ^= x >> 31;
    return x;
}

struct Draw { u64 draw_id; std::string date; int64_t mask; int special; };

std::string json_escape(const std::string& s) {
    std::string out;
    for (char c : s) { if (c=='"'||c=='\\') out+='\\'; out+=c; }
    return out;
}

std::vector<Draw> load_csv(const std::string& csv_path) {
    std::vector<Draw> draws;
    std::ifstream f(csv_path);
    if (!f) { fprintf(stderr, "Khong mo duoc %s\n", csv_path.c_str()); exit(1); }
    std::string line;
    std::getline(f, line);
    while (std::getline(f, line)) {
        std::vector<std::string> fields;
        std::string cur; bool in_quotes = false;
        for (size_t i = 0; i < line.size(); i++) {
            char c = line[i];
            if (c == '"') { if (in_quotes && i+1<line.size() && line[i+1]=='"') { cur+='"'; i++; } else in_quotes=!in_quotes; }
            else if (c == ',' && !in_quotes) { fields.push_back(cur); cur.clear(); }
            else cur += c;
        }
        fields.push_back(cur);
        if (fields.size() < 5) continue;
        u64 draw_id;
        try { draw_id = std::stoull(fields[1]); } catch (...) { continue; }
        std::string draw_date = fields.size() > 2 ? fields[2] : "";
        std::string rj = fields[4];
        auto extract_nums = [](const std::string& s, const std::string& key) -> std::vector<int> {
            std::vector<int> out;
            size_t p = s.find(key); if (p==std::string::npos) return out;
            p = s.find('[', p); size_t q = s.find(']', p);
            if (p==std::string::npos || q==std::string::npos) return out;
            std::string inner = s.substr(p+1, q-p-1);
            std::stringstream ss(inner); std::string tok;
            while (std::getline(ss, tok, ',')) { try { out.push_back(std::stoi(tok)); } catch (...) {} }
            return out;
        };
        std::vector<int> nums = extract_nums(rj, "\"numbers\"");
        std::vector<int> spv  = extract_nums(rj, "\"special_numbers\"");
        if (nums.size() != 5 || spv.empty()) continue;
        int64_t mask = 0;
        for (int nn : nums) mask |= (1LL << (nn-1));
        draws.push_back({draw_id, draw_date, mask, spv[0]});
    }
    std::sort(draws.begin(), draws.end(), [](const Draw&a, const Draw&b){return a.draw_id<b.draw_id;});
    return draws;
}

inline bool check_j1(u64 seed, const Draw& draw) {
    u64 combined = seed * M1 + draw.draw_id * M2;
    u64 mixed = mix64(combined);
    int64_t rank = (int64_t)(mixed % (u64)C);
    int64_t mask = RANK_TO_MASK[rank];
    u64 mixed2 = mix64(mixed);
    int sp = (int)(mixed2 % 12) + 1;
    return (mask == draw.mask) && (sp == draw.special);
}

int main() {
    build_binom(); build_lut();

    auto getenv_str = [](const char* name, const char* def) -> std::string {
        const char* v = std::getenv(name); return v ? std::string(v) : std::string(def);
    };
    auto getenv_u64 = [&](const char* name, u64 def) -> u64 {
        std::string s = getenv_str(name, ""); return s.empty() ? def : std::stoull(s);
    };

    std::string csv_path = getenv_str("CSV_PATH", "data/all.csv");
    std::string out_dir  = getenv_str("OUT_DIR", "l1");
    u64 seed_start = getenv_u64("SEED_START", 682305800400ULL);
    u64 seed_count = getenv_u64("SEED_COUNT", 1557775799ULL);
    u64 seed_end = seed_start + seed_count - 1;

    std::vector<Draw> draws = load_csv(csv_path);
    int n = (int)draws.size();
    fprintf(stderr, "Loaded %d ky. Dai seed: %llu -> %llu (%llu seed)\n",
            n, (unsigned long long)seed_start, (unsigned long long)seed_end, (unsigned long long)seed_count);
    if (n == 0) { fprintf(stderr, "Khong co du lieu\n"); return 1; }
    unsigned int num_threads = std::thread::hardware_concurrency();
    if (num_threads == 0) num_threads = 4;
    {
        std::string nt = getenv_str("NUM_THREADS", "");
        if (!nt.empty()) num_threads = (unsigned int)std::stoul(nt);
    }
    if (num_threads < 1) num_threads = 1;

    fs::create_directories(out_dir);

    auto t0 = std::chrono::steady_clock::now();

    // Moi thread giu ma tran ket qua rieng: results[tid][draw_idx] = vector cac seed trung
    std::vector<std::vector<std::vector<u64>>> thread_results(
        num_threads, std::vector<std::vector<u64>>(n));

    std::atomic<u64> checked_total{0};

    u64 chunk = seed_count / num_threads;
    u64 remainder = seed_count % num_threads;

    auto worker = [&](unsigned int tid, u64 range_start, u64 range_count) {
        auto& local = thread_results[tid];
        u64 local_checked = 0;
        for (u64 seed = range_start; seed < range_start + range_count; seed++) {
            for (int di = 0; di < n; di++) {
                if (check_j1(seed, draws[di])) {
                    local[di].push_back(seed);
                }
            }
            local_checked++;
            if ((local_checked & 0xFFFFF) == 0) {
                checked_total.fetch_add(0x100000, std::memory_order_relaxed);
            }
        }
        checked_total.fetch_add(local_checked & 0xFFFFF, std::memory_order_relaxed);
    };

    std::vector<std::thread> threads;
    u64 offset = 0;
    for (unsigned int t = 0; t < num_threads; t++) {
        u64 this_count = chunk + (t < remainder ? 1 : 0);
        threads.emplace_back(worker, t, seed_start + offset, this_count);
        offset += this_count;
    }

    std::atomic<bool> done{false};
    std::thread monitor([&]() {
        auto last_log = t0;
        while (!done.load()) {
            std::this_thread::sleep_for(std::chrono::milliseconds(500));
            auto now = std::chrono::steady_clock::now();
            if (std::chrono::duration<double>(now - last_log).count() >= 15.0) {
                double elapsed = std::chrono::duration<double>(now - t0).count();
                u64 c = checked_total.load(std::memory_order_relaxed);
                fprintf(stderr, "  checked~=%llu/%llu seed (%.0f/s, %u threads)\n",
                        (unsigned long long)c, (unsigned long long)seed_count,
                        elapsed > 0 ? c/elapsed : 0.0, num_threads);
                last_log = now;
            }
        }
    });

    for (auto& th : threads) th.join();
    done.store(true);
    monitor.join();

    fprintf(stderr, "Quet xong, dang gop ket qua va ghi %d file...\n", n);

    // Gop ket qua tu tat ca thread cho tung ky, ghi ra file rieng
    u64 total_found = 0;
    for (int di = 0; di < n; di++) {
        std::vector<u64> seeds_for_draw;
        for (unsigned int t = 0; t < num_threads; t++) {
            auto& v = thread_results[t][di];
            seeds_for_draw.insert(seeds_for_draw.end(), v.begin(), v.end());
        }
        std::sort(seeds_for_draw.begin(), seeds_for_draw.end());
        total_found += seeds_for_draw.size();

        const Draw& d = draws[di];
        std::string batch_file = out_dir + "/batch_ky" + std::to_string(d.draw_id) +
                                  "_seed" + std::to_string(seed_start) + ".json";
        FILE* f = fopen(batch_file.c_str(), "w");
        fprintf(f, "{\"draw_id\":%llu,\"draw_date\":\"%s\",\"seed_start\":%llu,\"seed_end\":%llu,\"found\":%zu,\"seeds\":[",
                (unsigned long long)d.draw_id, json_escape(d.date).c_str(),
                (unsigned long long)seed_start, (unsigned long long)seed_end, seeds_for_draw.size());
        for (size_t i = 0; i < seeds_for_draw.size(); i++) {
            if (i) fprintf(f, ",");
            fprintf(f, "%llu", (unsigned long long)seeds_for_draw[i]);
        }
        fprintf(f, "]}");
        fclose(f);
    }

    auto t1 = std::chrono::steady_clock::now();
    double elapsed = std::chrono::duration<double>(t1-t0).count();
    fprintf(stderr, "\nXong: %d file ghi vao %s/, tong %llu luot trung J1, %.0fs (%u threads)\n",
            n, out_dir.c_str(), (unsigned long long)total_found, elapsed, num_threads);
    printf("TOTAL_FILES=%d\n", n);
    printf("TOTAL_FOUND=%llu\n", (unsigned long long)total_found);

    return 0;
}
