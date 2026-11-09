#!/usr/bin/env bash
# Tai dataset NhanAZ-Data (all.csv) bang NHIEU cach, tranh CDN cache cua raw.githubusercontent.com (cache ~5 phut, thuong gay 'dataset co ky moi ma tai ve chua co').
#   bash fetch_dataset.sh lotto535|mega645 DUONG_DAN_RA        (can GH_TOKEN neu muon dung GitHub API)
set -u
P="$1"; OUT="$2"; REPO="NhanAZ-Data/vietlott-research"; FILE="datasets/draws/$P/all.csv"; TMP="$(mktemp)"
valid() { [ -s "$1" ] && head -1 "$1" | grep -q "draw_id" && [ "$(wc -l < "$1")" -gt 100 ]; }
report() { python3 - "$1" "$2" <<'PY'
import csv, sys
rows = [r for r in csv.DictReader(open(sys.argv[1], encoding="utf-8", newline="")) if (r.get("draw_id") or "").isdigit()]
print(f"  -> nguon {sys.argv[2]}: {len(rows)} ky, moi nhat ky {max(int(r['draw_id']) for r in rows)} ngay {max(r['draw_date'] for r in rows)}")
PY
}
rm -f "$OUT"
# thong tin do moi cua dataset (commit gan nhat cua file)
if command -v gh >/dev/null 2>&1 && [ -n "${GH_TOKEN:-}" ]; then
  gh api "repos/$REPO/commits?path=$FILE&per_page=1" -q '.[0] | "dataset commit gan nhat: " + .sha[0:7] + " luc " + .commit.committer.date' 2>/dev/null || echo "(khong doc duoc commit gan nhat)"
fi
# 1) GitHub API (khong qua CDN)
if command -v gh >/dev/null 2>&1 && [ -n "${GH_TOKEN:-}" ]; then
  if gh api -H "Accept: application/vnd.github.raw" "repos/$REPO/contents/$FILE?ref=main" > "$TMP" 2>/dev/null && valid "$TMP"; then cp "$TMP" "$OUT"; report "$OUT" "GitHub API"; rm -f "$TMP"; exit 0; fi
  echo "  GitHub API that bai/khong hop le, thu cach khac"
fi
# 2) raw.githubusercontent voi cache-bust
for i in 1 2 3; do
  if curl -fsSL --connect-timeout 15 -H "Cache-Control: no-cache" -H "Pragma: no-cache" "https://raw.githubusercontent.com/$REPO/main/$FILE?cb=$(date +%s)$RANDOM" -o "$TMP" && valid "$TMP"; then cp "$TMP" "$OUT"; report "$OUT" "raw (cache-bust)"; rm -f "$TMP"; exit 0; fi
  sleep 5
done
# 3) git clone nong (khong co cache)
D="$(mktemp -d)"
if git clone -q --depth 1 --filter=blob:none --sparse "https://github.com/$REPO.git" "$D" 2>/dev/null && (cd "$D" && git sparse-checkout set "datasets/draws/$P" >/dev/null 2>&1) && valid "$D/$FILE"; then cp "$D/$FILE" "$OUT"; report "$OUT" "git clone"; rm -rf "$D" "$TMP"; exit 0; fi
rm -rf "$D" "$TMP"
echo "::warning::Khong tai duoc dataset $P bang bat ky cach nao (hoac file doi duong dan/ten) - dung file hien co + fallback cao"
: > "$OUT"; exit 0
