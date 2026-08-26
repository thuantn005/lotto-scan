// scan_v2.cpp — Mo hinh moi: 2 lan/ngay, quet seed tiep noi, check ky moi nhat,
// full-scan verify neu trung, phan loai vao l1 (J1=1) hoac bo qua (J1>=2).
//
// Che do hoat dong (ENV MODE):
//   MODE=scan_new   -- quet seed tiep noi tu STATE_SEED_NEXT, check ky moi nhat,
//                       full-scan verify seed trung, ghi l1/ neu J1=1
//   MODE=check_l1   -- doc lai tat ca batch trong l1/, full-scan lai xem con
//                       dung J1=1 khong (vi co the co ky moi lam tang count).
//                       Neu seed nao gio J1>=2 -> xoa batch, ghi seed vao l2/
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
#include <set>
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
inline int popcount64(int64_t x) { return __builtin_popcountll((u64)x); }

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

// Tinh ve (mask + special) cho 1 seed tai 1 ky, tra ve true neu trung J1
inline bool check_j1(u64 seed, const Draw& draw) {
    u64 combined = seed * M1 + draw.draw_id * M2;
    u64 mixed = mix64(combined);
    int64_t rank = (int64_t)(mixed % (u64)C);
    int64_t mask = RANK_TO_MASK[rank];
    u64 mixed2 = mix64(mixed);
    int sp = (int)(mixed2 % 12) + 1;
    return (mask == draw.mask) && (sp == draw.special);
}

// Full-scan: dem tong so ky seed nay trung J1 trong TOAN BO lich su
int full_scan_count(u64 seed, const std::vector<Draw>& draws, std::vector<u64>* hit_draw_ids = nullptr) {
    int cnt = 0;
    for (auto& d : draws) {
        if (check_j1(seed, d)) {
            cnt++;
            if (hit_draw_ids) hit_draw_ids->push_back(d.draw_id);
        }
    }
    return cnt;
}

int main() {
    build_binom(); build_lut();

    auto getenv_str = [](const char* name, const char* def) -> std::string {
        const char* v = std::getenv(name); return v ? std::string(v) : std::string(def);
    };
    auto getenv_u64 = [&](const char* name, u64 def) -> u64 {
        std::string s = getenv_str(name, ""); return s.empty() ? def : std::stoull(s);
    };

    std::string mode = getenv_str("MODE", "scan_new");
    std::string csv_path = getenv_str("CSV_PATH", "data/all.csv");
    std::string l1_dir = getenv_str("L1_DIR", "l1");
    std::string l2_dir = getenv_str("L2_DIR", "l2");

    std::vector<Draw> draws = load_csv(csv_path);
    int n = draws.size();
    fprintf(stderr, "Loaded %d ky. MODE=%s\n", n, mode.c_str());
    if (n == 0) { fprintf(stderr, "Khong co du lieu\n"); return 1; }

    const Draw& latest = draws[n-1];
    fprintf(stderr, "Ky moi nhat: #%llu %s\n", (unsigned long long)latest.draw_id, latest.date.c_str());

    if (mode == "scan_new") {
        u64 seed_start = getenv_u64("SEED_START", 1);
        u64 seed_count = getenv_u64("SEED_COUNT", 100000000ULL); // so seed quet lan nay

        unsigned int num_threads = std::thread::hardware_concurrency();
        if (num_threads == 0) num_threads = 4;
        {
            std::string nt = getenv_str("NUM_THREADS", "");
            if (!nt.empty()) num_threads = (unsigned int)std::stoul(nt);
        }
        if (num_threads < 1) num_threads = 1;

        fs::create_directories(l1_dir);

        auto t0 = std::chrono::steady_clock::now();

        // Moi thread co vector rieng, khong can lock khi push (chi merge o cuoi).
        std::vector<std::vector<u64>> thread_results(num_threads);
        std::atomic<u64> checked_total{0};
        std::mutex log_mutex;

        u64 chunk = seed_count / num_threads;
        u64 remainder = seed_count % num_threads;

        auto worker = [&](unsigned int tid, u64 range_start, u64 range_count) {
            u64 local_checked = 0;
            std::vector<u64>& local_found = thread_results[tid];
            for (u64 seed = range_start; seed < range_start + range_count; seed++) {
                if (check_j1(seed, latest)) {
                    int total_j1 = full_scan_count(seed, draws);
                    if (total_j1 == 1) {
                        local_found.push_back(seed);
                        std::lock_guard<std::mutex> lk(log_mutex);
                        fprintf(stderr, "[t%u] J1=1 XAC NHAN: seed=%llu\n", tid, (unsigned long long)seed);
                    } else {
                        std::lock_guard<std::mutex> lk(log_mutex);
                        fprintf(stderr, "[t%u] seed=%llu trung ky moi nhung J1 thuc te=%d (>=2, KHONG luu)\n",
                                tid, (unsigned long long)seed, total_j1);
                    }
                }
                local_checked++;
                if ((local_checked & 0xFFFFF) == 0) { // cap nhat moi ~1M seed de khong tranh chap qua nhieu
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

        // Thread giam sat tien do, in log moi 15s tu main thread.
        std::atomic<bool> done{false};
        std::thread monitor([&]() {
            auto last_log = t0;
            while (!done.load()) {
                std::this_thread::sleep_for(std::chrono::milliseconds(500));
                auto now = std::chrono::steady_clock::now();
                if (std::chrono::duration<double>(now - last_log).count() >= 15.0) {
                    double elapsed = std::chrono::duration<double>(now - t0).count();
                    u64 c = checked_total.load(std::memory_order_relaxed);
                    fprintf(stderr, "  checked~=%llu/%llu (%.0f/s, %u threads)\n",
                            (unsigned long long)c, (unsigned long long)seed_count,
                            elapsed > 0 ? c/elapsed : 0.0, num_threads);
                    last_log = now;
                }
            }
        });

        for (auto& th : threads) th.join();
        done.store(true);
        monitor.join();

        // Merge ket qua tu tat ca thread, sap xep lai theo seed cho de doc.
        std::vector<u64> j1_1_seeds;
        for (auto& v : thread_results) j1_1_seeds.insert(j1_1_seeds.end(), v.begin(), v.end());
        std::sort(j1_1_seeds.begin(), j1_1_seeds.end());

        u64 checked = seed_count;
        u64 seed_end = seed_start + seed_count - 1;

        // Ghi batch moi vao l1/
        std::string batch_file = l1_dir + "/batch_ky" + std::to_string(latest.draw_id) +
                                  "_seed" + std::to_string(seed_start) + ".json";
        FILE* f = fopen(batch_file.c_str(), "w");
        fprintf(f, "{\"draw_id\":%llu,\"draw_date\":\"%s\",\"seed_start\":%llu,\"seed_end\":%llu,\"found\":%zu,\"seeds\":[",
                (unsigned long long)latest.draw_id, json_escape(latest.date).c_str(),
                (unsigned long long)seed_start, (unsigned long long)seed_end, j1_1_seeds.size());
        for (size_t i = 0; i < j1_1_seeds.size(); i++) {
            if (i) fprintf(f, ",");
            fprintf(f, "%llu", (unsigned long long)j1_1_seeds[i]);
        }
        fprintf(f, "]}");
        fclose(f);

        // Ghi state: seed_next de lan sau tiep noi
        std::string state_file = getenv_str("STATE_FILE", "l1_state.json");
        FILE* sf = fopen(state_file.c_str(), "w");
        fprintf(sf, "{\"seed_next\":%llu,\"last_draw_id\":%llu}",
                (unsigned long long)(seed_end + 1), (unsigned long long)latest.draw_id);
        fclose(sf);

        auto t1 = std::chrono::steady_clock::now();
        double elapsed = std::chrono::duration<double>(t1-t0).count();
        fprintf(stderr, "\nXong scan_new: %llu seed / %.0fs (%.0f/s, %u threads). J1=1 tim duoc: %zu\n",
                (unsigned long long)checked, elapsed, elapsed>0?checked/elapsed:0.0, num_threads, j1_1_seeds.size());
        printf("BATCH_FILE=%s\n", batch_file.c_str());
        printf("FOUND_COUNT=%zu\n", j1_1_seeds.size());

    } else if (mode == "check_l1") {
        // Doc tat ca batch trong l1/, full-scan lai tung seed
        fs::create_directories(l2_dir);

        std::vector<std::string> batch_files;
        if (fs::exists(l1_dir)) {
            for (auto& entry : fs::directory_iterator(l1_dir)) {
                if (entry.path().extension() == ".json") batch_files.push_back(entry.path().string());
            }
        }
        std::sort(batch_files.begin(), batch_files.end());

        int total_promoted = 0, total_removed_batches = 0;

        for (auto& bf : batch_files) {
            std::ifstream f(bf);
            std::stringstream buf; buf << f.rdbuf();
            std::string content = buf.str();

            // Parse tho: tim "seeds":[...]
            size_t p = content.find("\"seeds\":[");
            if (p == std::string::npos) continue;
            p += 9;
            size_t q = content.find(']', p);
            std::string inner = content.substr(p, q-p);
            std::vector<u64> seeds;
            std::stringstream ss(inner); std::string tok;
            while (std::getline(ss, tok, ',')) {
                try { seeds.push_back(std::stoull(tok)); } catch (...) {}
            }

            bool any_promoted = false;
            std::vector<u64> promoted_seeds;
            std::vector<int> promoted_counts;

            for (u64 seed : seeds) {
                int cnt = full_scan_count(seed, draws);
                if (cnt >= 2) {
                    any_promoted = true;
                    promoted_seeds.push_back(seed);
                    promoted_counts.push_back(cnt);
                    fprintf(stderr, "PROMOTE: seed=%llu J1=%d (tu batch %s)\n",
                            (unsigned long long)seed, cnt, bf.c_str());
                }
            }

            if (any_promoted) {
                // Ghi cac seed promoted vao l2/
                std::string l2_file = l2_dir + "/promoted_" + fs::path(bf).stem().string() + ".json";
                FILE* f2 = fopen(l2_file.c_str(), "w");
                fprintf(f2, "{\"source_batch\":\"%s\",\"promoted\":[", bf.c_str());
                for (size_t i = 0; i < promoted_seeds.size(); i++) {
                    if (i) fprintf(f2, ",");
                    fprintf(f2, "{\"seed\":%llu,\"j1_count\":%d}",
                            (unsigned long long)promoted_seeds[i], promoted_counts[i]);
                }
                fprintf(f2, "]}");
                fclose(f2);

                // Xoa CA BATCH khoi l1/
                fs::remove(bf);
                total_removed_batches++;
                total_promoted += promoted_seeds.size();
                fprintf(stderr, "Da xoa batch %s (co %zu seed thang hang)\n", bf.c_str(), promoted_seeds.size());
            }
        }

        // Gioi han l1/ toi da 20 batch (xoa batch cu nhat neu vuot)
        batch_files.clear();
        if (fs::exists(l1_dir)) {
            for (auto& entry : fs::directory_iterator(l1_dir)) {
                if (entry.path().extension() == ".json") batch_files.push_back(entry.path().string());
            }
        }
        std::sort(batch_files.begin(), batch_files.end());
        int removed_old = 0;
        while ((int)batch_files.size() > 20) {
            fs::remove(batch_files.front());
            fprintf(stderr, "Xoa batch cu (vuot 20): %s\n", batch_files.front().c_str());
            batch_files.erase(batch_files.begin());
            removed_old++;
        }

        fprintf(stderr, "\nXong check_l1: %d batch xoa (thang hang), %d seed promoted, %d batch xoa (qua cu)\n",
                total_removed_batches, total_promoted, removed_old);
        printf("PROMOTED_COUNT=%d\n", total_promoted);
        printf("REMOVED_BATCHES=%d\n", total_removed_batches);

    } else {
        fprintf(stderr, "MODE khong hop le: %s\n", mode.c_str());
        return 1;
    }

    return 0;
}
