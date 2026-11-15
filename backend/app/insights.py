"""Plain-language findings. Every sentence is filled from computed numbers, so
the text cannot drift from the data. Findings describe patterns, not causes."""
from __future__ import annotations


def _pct(x) -> str:
    return f"{x * 100:.1f}%"


def _peak(rows: list, who: str):
    best = max(rows, key=lambda r: r[who])
    return best["hour"], best[who]


def build(kpis: dict, analytics: dict, model: dict, stations: dict) -> list:
    out = []
    riders = {r["member_casual"]: r for r in analytics["by_rider"]}
    m, c = riders.get("member"), riders.get("casual")
    if m and c:
        ratio = c["median_duration"] / m["median_duration"] if m["median_duration"] else 0
        out.append({
            "title": "Pengguna biasa bersepeda lebih lama",
            "detail": f"Median durasi casual {c['median_duration']:.1f} menit, member {m['median_duration']:.1f} menit ({ratio:.2f} kali).",
            "recommendation": "Tawarkan paket berbasis durasi untuk casual, dan paket perjalanan singkat harian untuk member.",
        })
        out.append({
            "title": "Member lebih terikat jam kerja",
            "detail": f"{_pct(m['commute_peak_share'])} perjalanan member terjadi pada jam sibuk hari kerja, dibanding {_pct(c['commute_peak_share'])} pada casual. Porsi akhir pekan: member {_pct(m['weekend_share'])}, casual {_pct(c['weekend_share'])}.",
            "recommendation": "Fokuskan pemindahan sepeda di jam sibuk pada stasiun komuter, dan kapasitas akhir pekan pada stasiun rekreasi.",
        })
    wk = analytics["weekday_hourly"]
    if wk:
        hm, _ = _peak(wk, "member")
        hc, _ = _peak(wk, "casual")
        out.append({
            "title": "Jam tersibuk hari kerja",
            "detail": (f"Pada hari kerja, puncak member dan casual sama-sama pukul {hm:02d}.00." if hm == hc
                       else f"Pada hari kerja, puncak member pukul {hm:02d}.00 dan puncak casual pukul {hc:02d}.00."),
            "recommendation": "Jadwalkan pengisian stasiun sebelum jam puncak tersebut.",
        })
    monthly = analytics["monthly"]
    if len(monthly) >= 2:
        total = [(r["month"], r["member"] + r["casual"]) for r in monthly]
        hi, lo = max(total, key=lambda x: x[1]), min(total, key=lambda x: x[1])
        out.append({
            "title": "Jumlah perjalanan sangat berbeda antarbulan",
            "detail": f"Bulan tersibuk {hi[0]} dengan {hi[1]:,} perjalanan, tersepi {lo[0]} dengan {lo[1]:,} perjalanan ({hi[1] / lo[1]:.1f} kali lipat).",
            "recommendation": "Jadwalkan perawatan armada pada bulan sepi dan tambah kapasitas sebelum bulan puncak.",
        })
    out.append({
        "title": "Sepeda listrik dan perjalanan tanpa stasiun",
        "detail": f"{_pct(kpis['electric_share'])} perjalanan memakai sepeda listrik, dan {_pct(kpis['without_station_share'])} perjalanan tidak punya stasiun awal atau akhir.",
        "recommendation": "Data tanpa stasiun tetap dipakai untuk analisis waktu, tetapi tidak dihitung pada analisis per stasiun. Perlu ditelusuri bersama pengelola agar pencatatannya lebih lengkap.",
    })
    if stations and stations.get("clusters"):
        largest = max(stations["clusters"], key=lambda x: x["size"])
        busiest = max(stations["clusters"], key=lambda x: x["avg_rides"])
        out.append({
            "title": f"{stations['stations_clustered']:,} stasiun terbagi menjadi {stations['chosen_k']} kelompok",
            "detail": f"Kelompok terbesar: {largest['label']} ({largest['size']:,} stasiun). Rata-rata perjalanan tertinggi: {busiest['label']} ({busiest['avg_rides']:,.0f} per stasiun).",
            "recommendation": busiest["recommendation"],
        })
    if model and model.get("test_metrics"):
        tm = model["test_metrics"]
        gain = tm["accuracy"] - tm["baseline_accuracy"]
        strength = ("kuat membedakan" if tm["auc_roc"] >= 0.85 else
                    "cukup membedakan" if tm["auc_roc"] >= 0.75 else "hanya sebagian membedakan")
        out.append({
            "title": f"Pola perjalanan {strength} member dan casual",
            "detail": f"Model yang belajar dari {model['split']['train'][0]} sampai {model['split']['train'][-1]} diuji pada {model['split']['test']}: model menebak benar {_pct(tm['accuracy'])} perjalanan. Tanpa model, selalu menebak jenis pengguna yang paling banyak hanya benar {_pct(tm['baseline_accuracy'])}, jadi model unggul {gain * 100:+.1f} poin.",
            "recommendation": "Gunakan model untuk memetakan pola per stasiun, bukan untuk menilai pengguna perorangan (data memang tidak memuat identitas).",
        })
    return out
