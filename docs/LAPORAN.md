# Laporan Analitik Perjalanan Sepeda Sewa dengan HDFS dan Spark

Semua angka berasal dari pengujian seluruh file Januari–September 2026 yang diupload ke HDFS, memakai model GBT 2025 yang sama.
Dashboard baru menampilkan hasil setelah file diupload, pada tab Insight, Analisis, Model, dan Stasiun.

## 1. Sumber data

| Item | Keterangan |
|---|---|
| Dataset | Divvy Trip Data, data perjalanan sepeda sewa di Chicago |
| Penyedia | Lyft Bikes and Scooters, LLC, operator Divvy |
| Unduhan | https://divvy-tripdata.s3.amazonaws.com/ |
| Dokumentasi | https://divvybikes.com/system-data |
| Lisensi | https://divvybikes.com/data-license-agreement |
| Jenis data | Data nyata per perjalanan, dianonimkan oleh penyedia |
| Data aktual (diupload di website) | 1 Januari sampai 30 September 2026: 5.028.584 baris mentah, 4.895.578 baris bersih |
| Data latih model (di luar website) | Januari sampai Desember 2025: 5.552.994 baris mentah, 5.399.955 baris bersih |

Data diunduh pada 5 dan 7 November 2026. Seluruh data aktual berumur kurang dari 1 tahun pada tanggal tersebut. Sebagian data latih lebih tua dari 1 tahun, dan hanya dipakai untuk melatih model supaya semua musim tercakup.

Kolom utamanya adalah jenis sepeda, waktu mulai dan selesai, stasiun awal dan akhir, koordinat, serta jenis pengguna (`member` atau `casual`).

## 2. Kenapa topik ini menarik

- **Berkaitan dengan masalah kota:** sepeda sewa menyentuh kemacetan, transportasi ramah lingkungan, dan perencanaan kota.
- **Masalah operasionalnya nyata:** sepeda harus tersedia di stasiun yang tepat pada jam yang tepat, padahal permintaannya berubah menurut jam, hari, dan musim.
- **Ada nilai bisnisnya:** memahami perbedaan member dan casual membantu menentukan lokasi promosi keanggotaan.
- **Cocok untuk Big Data:** datanya jutaan baris dan bertambah setiap bulan, sehingga pas untuk HDFS, Spark, dan import incremental.

## 3. Manajemen data

**Alur**

1. **Training (sekali, di luar website):** 12 file 2025 dibersihkan dengan aturan yang sama, lalu model Gradient Boosted Trees (100 pohon, kedalaman 7) dilatih dengan Spark MLlib dari sampel sekitar 2 juta baris. Pengaturan ini dipilih dengan menyisihkan satu dari lima hari tiap bulan 2025 sebagai data validasi. Data latih tidak masuk ke HDFS.
2. **Import:** file CSV per bulan diunggah lewat website, lalu kolomnya divalidasi.
3. **Pembersihan:** data dibersihkan dengan pandas, dan jumlah baris yang dibuang dicatat untuk setiap aturan.
4. **Penyimpanan:** file asli dan Parquet bersih disimpan di HDFS, dengan data bersih dipartisi per bulan.
5. **Pemrosesan:** Spark membaca semua bulan yang sudah diupload langsung dari HDFS untuk analitik dan pengujian model.
6. **Model:** upload pertama menyalin model yang sudah jadi ke HDFS di `/bikeshare/models/gbt-2025`. Upload berikutnya memakai model yang sama.

**Hasil pembersihan data aktual**

| Langkah | Baris |
|---|---:|
| Data mentah | 5.028.584 |
| Durasi di luar 1 menit sampai 24 jam | -132.958 |
| Sebelum 1 Januari 2026 | -20 |
| Duplikat antarfile (`ride_id` sama) | -28 |
| **Data bersih** | **4.895.578** |

Tidak ada baris yang terbuang karena ID kosong, duplikat dalam satu file, waktu tidak terbaca, jenis pengguna tidak valid, koordinat awal kosong, atau jarak tidak wajar.

Sebanyak 1.588.466 baris (32,4%) tidak punya stasiun awal atau akhir. Baris ini tetap disimpan untuk analisis waktu, tetapi tidak dihitung pada analisis per stasiun yang membutuhkan nama stasiun.

**Import incremental**

- **Bulan baru:** hanya file bulan itu yang dibersihkan dan ditambahkan ke HDFS. Spark tetap membaca semua bulan yang sudah ada.
- **Import ulang:** bulan yang sama diganti, bukan ditambah.
- **File 2025 ditolak:** website hanya menerima data mulai 1 Januari 2026, karena data sebelumnya sudah dipakai untuk melatih model.
- **Model tidak dilatih saat upload:** model hanya dimuat, lalu diuji pada bulan yang baru diupload dan bulan terbaru. Hasil bulan lain memakai hasil sebelumnya.
- **Waktu proses di Mac 16 GB:** upload pertama (September) 70 detik, Januari sesudahnya 46 detik, 7 file sekaligus (Februari–Agustus) 194 detik, dan upload ulang September saat 9 bulan sudah ada 84 detik.

**Privasi dan lisensi**

Data tidak memuat nama atau identitas pengguna, dan proyek ini tidak mencoba mengidentifikasi pengguna. Sesuai lisensi, data mentah tidak boleh didistribusikan ulang sebagai dataset mandiri, jadi jangan unggah folder `data/` ke repository publik.

## 4. Insight baru

**a. Musim mengubah volume sekaligus komposisi pengguna.** Perjalanan naik 6,3 kali lipat dari 133.730 pada Januari menjadi 846.610 pada Agustus. Porsi casual juga naik dari 17,9% pada Januari menjadi 40,8% pada Juli.

**b. Casual lebih lama di jalan, tetapi jarak antara titik awal dan akhirnya hampir sama.** Median durasi casual 11,4 menit dan member 8,8 menit, sedangkan jarak rata-ratanya 2,24 km dan 2,30 km. Jarak ini berupa garis lurus, bukan rute sebenarnya, jadi belum tentu jarak tempuhnya sama. Perjalanan kembali ke stasiun awal juga lebih umum pada casual (5,0%) dibanding member (1,5%).

**c. Member mengikuti jam kerja, sedangkan casual lebih condong ke akhir pekan.**
- 38,6% perjalanan member terjadi pada jam sibuk hari kerja, dibanding 25,0% pada casual.
- Akhir pekan mencakup 37,3% perjalanan casual dan 23,5% perjalanan member.
- Pada hari kerja, member punya dua puncak yang jelas, yaitu pukul 08.00 dan 17.00.
- Pada akhir pekan, jumlah perjalanan keduanya hampir setara, misalnya 56.439 member dan 55.899 casual pada pukul 15.00.

**d. Sebagian besar perjalanan memakai sepeda listrik, dan banyak yang tanpa stasiun.** Sepeda listrik mencakup 71,2% perjalanan, dan 32,4% perjalanan tidak mencatat stasiun awal atau akhir. Keterbatasan ini membuat analisis per stasiun tidak mencakup seluruh perjalanan.

**e. Stasiun terbagi menjadi tiga kelompok (KMeans, k=3, silhouette 0,442).**

| Kelompok | Stasiun | Rata-rata perjalanan | Porsi casual | Jam sibuk | Akhir pekan | Durasi rata-rata |
|---|---:|---:|---:|---:|---:|---:|
| Campuran (sedang) | 561 | 5.781 | 32,0% | 35,5% | 26,5% | 13,5 menit |
| Rekreasi (sedang) | 157 | 3.257 | 49,4% | 25,7% | 33,3% | 21,4 menit |
| Lokal (sepi) | 179 | 701 | 41,3% | 29,9% | 28,8% | 13,1 menit |

Nama kelompok dibuat otomatis oleh aturan sederhana. Sistem memakai k=3, dan hanya mencoba k yang lebih besar jika salah satu kelompok terlalu kecil. Pembagian ini berasal dari 897 stasiun dengan minimal 200 perjalanan.

**f. Pola perjalanan hanya sebagian membedakan member dan casual.** Model Gradient Boosted Trees belajar dari Januari–Desember 2025, lalu diuji tanpa dilatih ulang pada bulan-bulan 2026 yang belum pernah dilihatnya.

| Metrik pada bulan terbaru (September 2026) | Nilai |
|---|---:|
| Akurasi | 70,0% |
| Akurasi jika selalu menebak kelas terbanyak | 62,3% |
| AUC-ROC | 0,729 |
| Precision untuk casual | 68,6% |
| Recall untuk casual | 37,5% |

Model masih melewatkan sekitar 62% perjalanan casual. Data yang paling berpengaruh adalah kecepatan rata-rata, bulan, jam, dan riwayat porsi casual di stasiun awal. Riwayat stasiun dihitung dari data 2025 saja, sehingga tidak membocorkan data uji.

**g. Keunggulan model bergantung pada musim.** Semua bulan diuji dengan model yang sama.

| Bulan uji | Akurasi model | Tebak kelas terbanyak | Selisih | Recall casual |
|---|---:|---:|---:|---:|
| Januari 2026 | 82,7% | 82,2% | +0,5 poin | 9,7% |
| Februari 2026 | 81,0% | 79,7% | +1,3 poin | 12,5% |
| Maret 2026 | 76,4% | 72,5% | +4,0 poin | 28,1% |
| April 2026 | 74,8% | 70,8% | +4,0 poin | 26,4% |
| Mei 2026 | 71,0% | 62,8% | +8,2 poin | 40,8% |
| Juni 2026 | 69,7% | 60,0% | +9,7 poin | 48,6% |
| Juli 2026 | 69,0% | 59,2% | +9,8 poin | 47,6% |
| Agustus 2026 | 69,3% | 60,4% | +8,8 poin | 45,4% |
| September 2026 | 70,0% | 62,3% | +7,7 poin | 37,5% |

Akurasi musim dingin terlihat paling tinggi, tetapi keunggulannya paling kecil, karena hampir semua perjalanannya dilakukan member dan menebak "member" saja sudah benar sekitar 80%. Karena itu, akurasi perlu selalu dibandingkan dengan tebakan kelas terbanyak. Model paling berguna pada Mei–September, dengan keunggulan 8–10 poin.

## 5. Rekomendasi ke depan

**Untuk operator**

1. **Sesuaikan armada dengan musim.** Jadwalkan perawatan besar pada Desember–Februari, dan siapkan kapasitas sebelum puncak Juni–September.
2. **Pisahkan strategi menurut kelompok stasiun.** Untuk kelompok Campuran yang porsi jam sibuknya tinggi, utamakan pemindahan sepeda sebelum pukul 08.00 dan 17.00 pada hari kerja. Untuk kelompok Rekreasi, utamakan kapasitas akhir pekan.
3. **Telusuri perjalanan tanpa stasiun.** Dengan porsi 32,4%, perlu dipastikan apakah ini memang pola parkir sepeda listrik atau ada celah pencatatan.

**Untuk pengembangan sistem**

1. **Pantau hasil uji tiap bulan.** Kalau keunggulan model dibanding tebakan kelas terbanyak terus mengecil, latih model baru dengan data yang lebih baru.
2. **Tambah data cuaca dan hari libur.** Keduanya berpotensi menjelaskan sebagian perubahan permintaan dan memperbaiki model.
3. **Coba prediksi permintaan per stasiun.** Target ini lebih langsung membantu pemindahan sepeda daripada menebak jenis pengguna.
4. **Bandingkan dengan konteks Indonesia.** Metode yang sama bisa diterapkan bila tersedia data serupa dari kota di Indonesia.

## Keterbatasan

- **Lokasi:** data berasal dari Chicago, jadi hasilnya tidak bisa langsung diterapkan ke kota lain.
- **Tidak ada ID pengguna:** analisis dilakukan per perjalanan, jadi jumlah pengguna dan churn tidak bisa dihitung.
- **Korelasi, bukan sebab-akibat:** temuan ini menunjukkan pola. Rekomendasinya belum diuji di lapangan.
- **Umur data latih:** sebagian data latih lebih tua dari 1 tahun. Data aktual yang dianalisis dan dipakai menguji model tetap berumur kurang dari 1 tahun.
- **Training di luar HDFS:** model dilatih sekali dengan Spark dari file lokal, supaya upload tetap cepat dan data latih tidak muncul di website. HDFS menyimpan data aktual dan model yang sudah jadi.
- **Sampel model:** agar sanggup dijalankan di laptop, training dibatasi sekitar 2 juta baris dan pengujian tiap bulan sekitar 300 ribu baris.
- **Pemilihan pengaturan:** fitur dan ukuran model dipilih dari validasi 2025, tetapi ide fitur bulan muncul setelah melihat hasil Januari–Februari 2026.
- **Algoritma:** proyek ini langsung memakai Gradient Boosted Trees, yang unggul saat dibandingkan dengan tiga algoritma lain pada pengujian sebelumnya.
- **Periode:** data aktual mencakup 9 bulan, sehingga Oktober–Desember 2026 belum teruji.
- **Koordinat:** contoh baris tanpa stasiun memakai koordinat yang dibulatkan, jadi jarak pada baris seperti ini kurang presisi.
