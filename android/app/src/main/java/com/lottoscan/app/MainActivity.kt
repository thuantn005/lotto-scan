package com.lottoscan.app

import android.app.Activity
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.graphics.Typeface
import android.os.Bundle
import android.text.InputType
import android.util.TypedValue
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import org.json.JSONArray
import java.io.BufferedReader
import java.io.File
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URL
import java.util.Random
import kotlin.concurrent.thread

private val TICKET = Regex("""\d{2}(?:-\d{2}){4} \+ \d{2}""")
private const val POOL_SIZE = 40000          // so ve lay mau ngau nhien (reservoir) tu danh sach con lai de chon
private const val TOTAL = 3895584L           // to hop Lotto 5/35 + DB

private class Cand(val text: String, val mask: Long)

class MainActivity : Activity() {
    private lateinit var etOwner: EditText
    private lateinit var etRepo: EditText
    private lateinit var etBranch: EditText
    private lateinit var etToken: EditText
    private lateinit var etCount: EditText
    private lateinit var tvOut: TextView
    private lateinit var tvStatus: TextView
    private var lastResult: String = ""

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val prefs = getSharedPreferences("cfg", Context.MODE_PRIVATE)
        val pad = dp(14)

        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(pad, pad, pad, pad) }
        fun label(t: String) = TextView(this).apply { text = t; setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f) }
        fun edit(hint: String, value: String, pwd: Boolean = false) = EditText(this).apply {
            this.hint = hint; setText(value); setSingleLine(true)
            if (pwd) inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
        }
        fun btn(t: String, action: () -> Unit) = Button(this).apply { text = t; setOnClickListener { action() } }

        root.addView(TextView(this).apply { text = "Lotto 5/35 - Vé còn lại"; setTextSize(TypedValue.COMPLEX_UNIT_SP, 20f); setTypeface(null, Typeface.BOLD) })
        root.addView(label("Chủ repo GitHub (owner)")); etOwner = edit("vd: ten-tai-khoan", prefs.getString("owner", "") ?: ""); root.addView(etOwner)
        root.addView(label("Tên repo")); etRepo = edit("lotto-scan", prefs.getString("repo", "lotto-scan") ?: "lotto-scan"); root.addView(etRepo)
        root.addView(label("Nhánh")); etBranch = edit("main", prefs.getString("branch", "main") ?: "main"); root.addView(etBranch)
        root.addView(label("Token (chỉ cần nếu repo private)")); etToken = edit("ghp_...", prefs.getString("token", "") ?: "", true); root.addView(etToken)
        root.addView(label("Số vé muốn dự đoán")); etCount = edit("100", prefs.getString("count", "100") ?: "100")
        etCount.inputType = InputType.TYPE_CLASS_NUMBER; root.addView(etCount)

        root.addView(btn("1. Tải vé còn lại mới nhất từ GitHub") { saveCfg(); downloadPool() })
        root.addView(btn("2. Dự đoán từ vé còn lại") { saveCfg(); predict() })
        root.addView(btn("Xem 100 vé hệ thống đã chọn") { saveCfg(); showSystemTickets() })
        root.addView(btn("Xem báo cáo tóm tắt") { saveCfg(); showReport() })
        root.addView(btn("Sao chép kết quả") { copy() })

        tvStatus = TextView(this).apply { setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f); setPadding(0, dp(8), 0, dp(4)) }
        root.addView(tvStatus)
        tvOut = TextView(this).apply { typeface = Typeface.MONOSPACE; setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f); setTextIsSelectable(true) }
        root.addView(tvOut)
        root.addView(TextView(this).apply {
            text = "Lưu ý: loại seed / chọn từ vé còn lại chỉ là bộ lọc, KHÔNG làm tăng xác suất trúng. Mỗi vé vẫn là 1/3.895.584."
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 12f); setPadding(0, dp(12), 0, 0)
        })

        setContentView(ScrollView(this).apply {
            layoutParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
            addView(root)
        })
        showPoolInfo()
    }

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()

    private fun saveCfg() {
        getSharedPreferences("cfg", Context.MODE_PRIVATE).edit()
            .putString("owner", etOwner.text.toString().trim()).putString("repo", etRepo.text.toString().trim())
            .putString("branch", etBranch.text.toString().trim()).putString("token", etToken.text.toString().trim())
            .putString("count", etCount.text.toString().trim()).apply()
    }

    private fun status(t: String) = runOnUiThread { tvStatus.text = t }
    private fun out(t: String) { lastResult = t; runOnUiThread { tvOut.text = t } }

    // ---------- GitHub API ----------
    private fun conn(path: String, json: Boolean): HttpURLConnection {
        val o = etOwner.text.toString().trim(); val r = etRepo.text.toString().trim(); val b = etBranch.text.toString().trim().ifEmpty { "main" }
        require(o.isNotEmpty() && r.isNotEmpty()) { "Chưa nhập owner / repo" }
        val c = URL("https://api.github.com/repos/$o/$r/contents/$path?ref=$b").openConnection() as HttpURLConnection
        c.setRequestProperty("Accept", if (json) "application/vnd.github+json" else "application/vnd.github.raw+json")
        c.setRequestProperty("User-Agent", "LottoConLaiApp")
        val tk = etToken.text.toString().trim()
        if (tk.isNotEmpty()) c.setRequestProperty("Authorization", "Bearer $tk")
        c.connectTimeout = 20000; c.readTimeout = 180000
        if (c.responseCode != 200) throw Exception("GitHub trả về HTTP ${c.responseCode} cho $path (kiểm tra owner/repo/nhánh/token)")
        return c
    }

    /** Tim file moi nhat trong thu muc theo ky: ten khop regex, nhom 1 = so ky. */
    private fun latest(dir: String, regex: Regex): Pair<Int, String>? {
        val c = conn(dir, true)
        val arr = JSONArray(c.inputStream.bufferedReader().readText())
        var best = -1; var bn = ""
        for (i in 0 until arr.length()) {
            val n = arr.getJSONObject(i).getString("name")
            val m = regex.matchEntire(n) ?: continue
            val k = m.groupValues[1].toInt()
            if (k > best) { best = k; bn = n }
        }
        return if (best < 0) null else Pair(best, bn)
    }

    private fun bg(task: () -> Unit) = thread {
        try { task() } catch (e: Exception) { status("Lỗi: ${e.message}") }
    }

    // ---------- 1. tai ve con lai ----------
    private fun downloadPool() = bg {
        status("Đang tìm file vé còn lại mới nhất...")
        val f = latest("du_doan", Regex("""con_lai_lotto535_(\d+)\.txt""")) ?: throw Exception("Không thấy con_lai_lotto535_*.txt trong du_doan/")
        val ky = f.first
        status("Đang tải ${f.second} (có thể ~25 MB)...")
        val c = conn("du_doan/${f.second}", false)
        val rnd = Random(ky.toLong())
        val pool = ArrayList<String>(POOL_SIZE)
        var n = 0L; var header = ""
        BufferedReader(InputStreamReader(c.inputStream, "UTF-8"), 1 shl 16).use { rd ->
            while (true) {
                val line = rd.readLine() ?: break
                if (line.startsWith("#")) { if (header.isEmpty()) header = line; continue }
                val m = TICKET.find(line) ?: continue
                n++
                if (pool.size < POOL_SIZE) pool.add(m.value)
                else { val j = (rnd.nextDouble() * n).toLong(); if (j < POOL_SIZE) pool[j.toInt()] = m.value }
                if (n % 200000L == 0L) status("Đã đọc ${"%,d".format(n)} vé...")
            }
        }
        if (n == 0L) throw Exception("File không có vé nào")
        File(filesDir, "pool.txt").writeText("$ky\n$n\n$header\n" + pool.joinToString("\n"))
        status("Xong: kỳ $ky, còn lại ${"%,d".format(n)} vé (${"%.2f".format(n * 100.0 / TOTAL)}% tổ hợp). Đã lấy mẫu ${pool.size} vé để chọn.")
        out(if (header.isNotEmpty()) header else "")
    }

    private fun showPoolInfo() {
        val f = File(filesDir, "pool.txt")
        if (!f.exists()) { status("Chưa tải vé còn lại. Nhập owner/repo rồi bấm nút 1."); return }
        val l = f.readLines()
        status("Đã có dữ liệu kỳ ${l[0]}: còn lại ${"%,d".format(l[1].toLong())} vé.")
    }

    // ---------- 2. du doan ----------
    private fun predict() = bg {
        val f = File(filesDir, "pool.txt")
        if (!f.exists()) throw Exception("Chưa tải vé còn lại (bấm nút 1 trước)")
        val l = f.readLines()
        val ky = l[0].toLong(); val total = l[1].toLong()
        val pool = l.drop(3).filter { TICKET.matches(it) }
        val need = (etCount.text.toString().trim().toIntOrNull() ?: 100).coerceIn(1, 1000)
        val sel = pick(pool, need, ky)
        val sb = StringBuilder("Kỳ $ky - ${sel.size} vé chọn từ ${"%,d".format(total)} vé còn lại\n(lọc ít người chọn + phủ đều, cố định theo kỳ)\n\n")
        sel.forEachIndexed { i, t -> sb.append("%3d. %s\n".format(i + 1, t)) }
        out(sb.toString()); status("Đã chọn ${sel.size} vé.")
    }

    private fun parse(t: String): IntArray = t.substring(0, 14).split("-").map { it.toInt() }.toIntArray()

    /** Chon `need` ve: bo ve dang ngay sinh / day lien tiep / cap so cong; 2 ve chung toi da 2 (noi dan 3, 4) so; moi so khong qua nhieu. */
    private fun pick(pool: List<String>, need: Int, seed: Long): List<String> {
        val shuffled = pool.shuffled(Random(seed))
        val good = ArrayList<Cand>()
        for (t in shuffled) {
            val a = parse(t)
            val diffs = (1..4).map { a[it] - a[it - 1] }
            val ap = diffs.toSet().size == 1
            val run = diffs.count { it == 1 } >= 2
            if (a[4] >= 32 && !ap && !run) good.add(Cand(t, a.fold(0L) { m, x -> m or (1L shl x) }))
        }
        val cap = (need * 5 / 35.0 * 1.8).toInt() + 1
        val sel = ArrayList<Cand>(); val usage = IntArray(36); val used = HashSet<String>()
        for (ov in intArrayOf(2, 3, 4)) {
            for (c in good) {
                if (sel.size >= need) break
                if (c.text in used) continue
                if (sel.any { java.lang.Long.bitCount(it.mask and c.mask) > ov }) continue
                val nums = parse(c.text)
                if (nums.any { usage[it] >= cap }) continue
                sel.add(c); used.add(c.text); nums.forEach { usage[it]++ }
            }
            if (sel.size >= need) break
        }
        val res = ArrayList(sel.map { it.text })
        if (res.size < need) for (t in shuffled) { if (res.size >= need) break; if (t !in used) { res.add(t); used.add(t) } }
        return res.sorted()
    }

    // ---------- 100 ve he thong / bao cao ----------
    private fun showSystemTickets() = bg {
        status("Đang tải vé hệ thống...")
        val f = latest("du_doan", Regex("""lotto535_(\d+)\.txt""")) ?: throw Exception("Không thấy lotto535_*.txt trong du_doan/")
        val txt = conn("du_doan/${f.second}", false).inputStream.bufferedReader().readText()
        out(txt); status("Vé hệ thống kỳ ${f.first}.")
    }

    private fun showReport() = bg {
        status("Đang tải báo cáo...")
        val txt = conn("bao_cao/tom_tat_lotto535.txt", false).inputStream.bufferedReader().readText()
        out(txt); status("Báo cáo tóm tắt.")
    }

    private fun copy() {
        if (lastResult.isEmpty()) { status("Chưa có gì để sao chép"); return }
        (getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager).setPrimaryClip(ClipData.newPlainText("lotto", lastResult))
        status("Đã sao chép.")
    }
}
