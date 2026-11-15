# Bike Share Analytics: HDFS + Spark MLlib + Next.js

Website untuk mengimport data perjalanan sepeda sewa dari CSV, menyimpannya di HDFS,
lalu menganalisisnya dengan Spark dan machine learning. Laporan tugas ada di
[docs/LAPORAN.md](docs/LAPORAN.md).

```
CSV -> validasi -> pembersihan -> HDFS (per bulan) -> Spark membaca semua bulan
  -> analitik -> muat model yang sudah jadi -> uji tiap bulan
  -> pengelompokan stasiun -> dashboard
```

## Menjalankan

Prasyarat: Docker Desktop dengan memori minimal 8 GB.

```bash
docker compose up -d --build
```

| Alamat | Fungsi |
|---|---|
| http://localhost:3000 | Dashboard dan import |
| http://localhost:8000/api/health | Status API |
| http://localhost:9870 | HDFS NameNode UI |
| http://localhost:8080 | Spark Master UI |

Import file `.csv` dari `data/raw/csv/` lewat halaman utama. Upload tidak melatih model. Model GBT sudah
dilatih sekali dari data Januari–Desember 2025 dan tersimpan di `model/gbt-2025/`. Upload pertama
menyimpannya ke HDFS sebagai versi 1, lalu semua bulan yang diupload dibaca dari HDFS dan dipakai untuk mengujinya.

Untuk melatih ulang, taruh file latih di `data/raw/training/`, kosongkan data, lalu jalankan:

```
docker compose exec -e DATA_MIN_DATE=2025-01-01 -e SPARK_MASTER='local[*]' -e SPARK_DRIVER_MEMORY=4g backend python -m app.train_model
```

Untuk mengosongkan seluruh data aplikasi tanpa menghapus file sumber dan model, jalankan `scripts/reset_data.sh`.

## Menyiapkan data

Data tidak disertakan karena lisensinya melarang distribusi ulang sebagai dataset mandiri.

Unduh `YYYYMM-divvy-tripdata.zip` dari https://divvy-tripdata.s3.amazonaws.com/ lalu ekstrak CSV-nya ke `data/raw/csv/`.

## Aturan import

- Format `.csv`, dengan 13 kolom standar data perjalanan.
- Bulan baru ditambahkan. Bulan yang sudah ada diganti, sehingga data tidak berlipat.
- Perjalanan sebelum `DATA_MIN_DATE` (default `2026-01-01`) dibuang, jadi file 2025 tidak bisa diupload.

## HDFS

| Path | Isi |
|---|---|
| `/bikeshare/raw/{job}/` | File asli |
| `/bikeshare/clean/month=YYYY-MM/` | Parquet bersih per bulan |
| `/bikeshare/models/vNNNN/` | Setiap versi model |
| `/bikeshare/results/{job}/summary.json` | Hasil analitik |

## Test

```bash
docker compose exec backend sh -c "cd /opt/app && python -m pytest tests -q"
```

## Struktur

- `backend/app/preprocessing.py`: pembaca CSV dan aturan pembersihan
- `backend/app/pipeline.py`: urutan seluruh tahap saat upload
- `backend/app/train_model.py`: melatih model sekali, di luar website
- `model/gbt-2025/`: model yang sudah jadi
- `backend/app/spark_jobs/`: `analytics.py`, `rider_model.py`, `stations.py`
- `backend/app/insights.py`: teks insight yang diisi dari angka hasil hitungan
- `frontend/`: dashboard Next.js

## Lisensi data

Data dari Bikeshare (Divvy) mengikuti [Data License Agreement](https://divvybikes.com/data-license-agreement).
Proyek ini akademik dan non-komersial, tidak berafiliasi dengan penyedia data, dan tidak mencoba mengidentifikasi pengguna.
