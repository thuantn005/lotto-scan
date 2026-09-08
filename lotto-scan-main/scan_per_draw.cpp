// scan_per_draw.cpp — Quet 1 dai seed CO DINH cho TAT CA cac ky trong CSV,
// GHI RA 1 FILE DUY NHAT (khong con tao 850 file rieng le nua).
//
// Thuat toan giu nguyen 100% tu scan_v2.cpp (da kiem chung khop voi du lieu mau):
//   ticket(seed, draw_id) = unrank_colex( splitmix64_mix(seed*M1 + draw_id*M2) mod C(35,5) )
//   special = splitmix64_mix(mixed) mod 12 + 1
//
// Neu file dau ra (OUT_FILE) da ton tai, chuong trinh se DOC lai cac ky da co,
// CHI QUET cac ky moi (chua co trong file), roi GOP ket qua vao cung 1 file
// (khong can flag rieng, luon tu dong "skip cac ky da xong").
//
// ENV:
//   CSV_PATH     - duong dan file CSV cac ky quay (mac dinh data/all.csv)
//   OUT_DIR      - thu muc chua file ket qua (mac dinh l1_merged)
//   OUT_NAME     - ten file ket qua (mac dinh: merged_seed{SEED_START}.json)
//   SEED_START   - diem bat dau dai seed (mac dinh 682305800400)
//   SEED_COUNT   - so seed can quet (mac dinh 1557775799)
//   NUM_THREADS  - so luong thread (mac dinh = so core)
//   FORCE_RESCAN - "1" = bo qua file cu, quet lai TAT CA tu dau (mac dinh "0")
//   LAST_N_DRAWS - > 0: chi quet N ky MOI NHAT theo draw_id, bo qua cac ky con lai
//                  (mac dinh 0 = quet toan bo CSV nhu truoc)

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <vector>
#include <string>
#include <unordered_set>
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
struct DrawResult { u64 draw_id; std::string date; std::vector<u64> seeds; };

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

// Doc file merged cu (neu co), tra ve danh sach DrawResult da co san
std::vector<DrawResult> load_existing_merged(const std::string& path, u64& out_seed_start, u64& out_seed_end) {
    std::vector<DrawResult> existing;
    std::ifstream f(path);
    if (!f) return existing;
    std::stringstream buf; buf << f.rdbuf();
    std::string content = buf.str();
    if (content.empty()) return existing;

    auto extract_u64_field = [&](const std::string& key) -> u64 {
        size_t p = content.find("\"" + key + "\":");
        if (p == std::string::npos) return 0;
        p += key.size() + 3;
        size_t q = content.find_first_of(",}", p);
        try { return std::stoull(content.substr(p, q-p)); } catch (...) { return 0; }
    };
    out_seed_start = extract_u64_field("seed_start");
    out_seed_end = extract_u64_field("seed_end");

    // Tim mang "draws":[ ... ] va parse tho tung object {draw_id,draw_date,found,seeds:[...]}
    size_t draws_pos = content.find("\"draws\":[");
    if (draws_pos == std::string::npos) return existing;
    size_t pos = draws_pos + 9;

    while (true) {
        size_t obj_start = content.find('{', pos);
        if (obj_start == std::string::npos) break;
        // Tim vi tri ket thuc object nay: tim "]}" gan nhat sau "seeds":[
        size_t seeds_key = content.find("\"seeds\":[", obj_start);
        if (seeds_key == std::string::npos) break;
        size_t seeds_arr_start = seeds_key + 9;
        size_t seeds_arr_end = content.find(']', seeds_arr_start);
        size_t obj_end = content.find('}', seeds_arr_end);
        if (obj_end == std::string::npos) break;

        std::string obj = content.substr(obj_start, obj_end - obj_start + 1);

        auto extract_field_str = [&](const std::string& key) -> std::string {
            size_t p = obj.find("\"" + key + "\":");
            if (p == std::string::npos) return "";
            p += key.size() + 3;
            if (obj[p] == '"') {
                size_t q = obj.find('"', p+1);
                return obj.substr(p+1, q-p-1);
            }
            size_t q = obj.find_first_of(",}", p);
            return obj.substr(p, q-p);
        };

        DrawResult dr;
        try { dr.draw_id = std::stoull(extract_field_str("draw_id")); } catch (...) { pos = obj_end+1; continue; }
        dr.date = extract_field_str("draw_date");

        std::string inner = content.substr(seeds_arr_start, seeds_arr_end - seeds_arr_start);
        if (!inner.empty()) {
            std::stringstream ss(inner); std::string tok;
            while (std::getline(ss, tok, ',')) {
                try { dr.seeds.push_back(std::stoull(tok)); } catch (...) {}
            }
        }
        existing.push_back(std::move(dr));
        pos = obj_end + 1;

        // Kiem tra da het mang draws chua (gap "]" dong mang truoc "}" dong object ngoai)
        size_t next_brace = content.find_first_not_of(" \t\n,", pos);
        if (next_brace != std::string::npos && content[next_brace] == ']') break;
    }
    return existing;
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
    std::string out_dir  = getenv_str("OUT_DIR", "l1_merged");
    u64 seed_start = getenv_u64("SEED_START", 682305800400ULL);
    u64 seed_count = getenv_u64("SEED_COUNT", 1557775799ULL);
    u64 seed_end = seed_start + seed_count - 1;
    bool force_rescan = getenv_str("FORCE_RESCAN", "0") == "1";
    // LAST_N_DRAWS > 0: chi quet N ky MOI NHAT (theo draw_id) thay vi toan bo CSV.
    // Dung cho cac lan quet "1 lan" pham vi hep (vd 10/20 ky gan nhat) tren dai seed lon.
    u64 last_n_draws = getenv_u64("LAST_N_DRAWS", 0ULL);

    std::string out_name = getenv_str("OUT_NAME", "");
    if (out_name.empty()) out_name = "merged_seed" + std::to_string(seed_start) + ".json";
    std::string out_path = out_dir + "/" + out_name;

    std::vector<Draw> draws_all = load_csv(csv_path);
    if (last_n_draws > 0 && draws_all.size() > last_n_draws) {
        // draws_all da duoc sap xep tang dan theo draw_id (xem load_csv) -> lay N phan tu cuoi
        draws_all.erase(draws_all.begin(), draws_all.end() - (long)last_n_draws);
        fprintf(stderr, "LAST_N_DRAWS=%llu -> chi giu %zu ky gan nhat (draw_id %llu..%llu)\n",
                (unsigned long long)last_n_draws, draws_all.size(),
                (unsigned long long)draws_all.front().draw_id,
                (unsigned long long)draws_all.back().draw_id);
    }
    int n_all = (int)draws_all.size();
    fprintf(stderr, "Loaded %d ky can quet. Dai seed: %llu -> %llu (%llu seed)\n",
            n_all, (unsigned long long)seed_start, (unsigned long long)seed_end, (unsigned long long)seed_count);
    if (n_all == 0) { fprintf(stderr, "Khong co du lieu\n"); return 1; }

    // Doc file merged cu (neu co va khong force_rescan)
    std::vector<DrawResult> existing_results;
    if (!force_rescan) {
        u64 old_start=0, old_end=0;
        existing_results = load_existing_merged(out_path, old_start, old_end);
        if (!existing_results.empty()) {
            fprintf(stderr, "Doc duoc file cu %s: %zu ky da co san\n", out_path.c_str(), existing_results.size());
        }
    }

    std::unordered_set<u64> existing_draw_ids;
    for (auto& dr : existing_results) existing_draw_ids.insert(dr.draw_id);

    std::vector<Draw> draws; // chi cac ky MOI can quet
    for (auto& d : draws_all) {
        if (existing_draw_ids.find(d.draw_id) == existing_draw_ids.end()) draws.push_back(d);
    }

    int n = (int)draws.size();
    fprintf(stderr, "%d/%d ky da co san, con %d ky moi can quet\n",
            n_all - n, n_all, n);

    if (n == 0) {
        fprintf(stderr, "Khong co ky moi can quet. Da xong (file van giu nguyen).\n");
        printf("TOTAL_FILES=1\n");
        printf("NEW_DRAWS=0\n");
        printf("TOTAL_FOUND=0\n");
        return 0;
    }

    unsigned int num_threads = std::thread::hardware_concurrency();
    if (num_threads == 0) num_threads = 4;
    {
        std::string nt = getenv_str("NUM_THREADS", "");
        if (!nt.empty()) num_threads = (unsigned int)std::stoul(nt);
    }
    if (num_threads < 1) num_threads = 1;

    fs::create_directories(out_dir);

    auto t0 = std::chrono::steady_clock::now();

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

    fprintf(stderr, "Quet xong %d ky moi, dang gop vao file...\n", n);

    u64 total_found_new = 0;
    std::vector<DrawResult> new_results;
    for (int di = 0; di < n; di++) {
        std::vector<u64> seeds_for_draw;
        for (unsigned int t = 0; t < num_threads; t++) {
            auto& v = thread_results[t][di];
            seeds_for_draw.insert(seeds_for_draw.end(), v.begin(), v.end());
        }
        std::sort(seeds_for_draw.begin(), seeds_for_draw.end());
        total_found_new += seeds_for_draw.size();

        DrawResult dr;
        dr.draw_id = draws[di].draw_id;
        dr.date = draws[di].date;
        dr.seeds = std::move(seeds_for_draw);
        new_results.push_back(std::move(dr));
    }

    // Gop existing + new, sap xep theo draw_id
    std::vector<DrawResult> all_results = existing_results;
    for (auto& dr : new_results) all_results.push_back(std::move(dr));
    std::sort(all_results.begin(), all_results.end(),
              [](const DrawResult&a, const DrawResult&b){ return a.draw_id < b.draw_id; });

    u64 total_found_all = 0;
    for (auto& dr : all_results) total_found_all += dr.seeds.size();

    // Ghi ra 1 file DUY NHAT
    FILE* f = fopen(out_path.c_str(), "w");
    fprintf(f, "{\"seed_start\":%llu,\"seed_end\":%llu,\"total_draws\":%zu,\"total_found\":%llu,\"draws\":[",
            (unsigned long long)seed_start, (unsigned long long)seed_end,
            all_results.size(), (unsigned long long)total_found_all);
    for (size_t i = 0; i < all_results.size(); i++) {
        if (i) fprintf(f, ",");
        auto& dr = all_results[i];
        fprintf(f, "{\"draw_id\":%llu,\"draw_date\":\"%s\",\"found\":%zu,\"seeds\":[",
                (unsigned long long)dr.draw_id, json_escape(dr.date).c_str(), dr.seeds.size());
        for (size_t j = 0; j < dr.seeds.size(); j++) {
            if (j) fprintf(f, ",");
            fprintf(f, "%llu", (unsigned long long)dr.seeds[j]);
        }
        fprintf(f, "]}");
    }
    fprintf(f, "]}");
    fclose(f);

    auto t1 = std::chrono::steady_clock::now();
    double elapsed = std::chrono::duration<double>(t1-t0).count();
    fprintf(stderr, "\nXong: ghi vao %s (%zu ky tong cong, %d ky moi quet lan nay, tong %llu luot trung J1), %.0fs (%u threads)\n",
            out_path.c_str(), all_results.size(), n, (unsigned long long)total_found_all, elapsed, num_threads);
    printf("TOTAL_FILES=1\n");
    printf("NEW_DRAWS=%d\n", n);
    printf("TOTAL_FOUND=%llu\n", (unsigned long long)total_found_all);
    printf("OUT_PATH=%s\n", out_path.c_str());

    return 0;
}
