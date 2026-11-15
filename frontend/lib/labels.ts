const STAGES: Record<string, string> = {
  queued: "Menunggu giliran",
  preprocessing: "Membersihkan data",
  uploading_hdfs: "Menyimpan ke HDFS",
  reading_hdfs: "Membaca dari HDFS",
  spark_analytics: "Analisis dengan Spark",
  loading_model: "Memuat model",
  monthly_test: "Menguji tiap bulan",
  clustering: "Mengelompokkan stasiun",
  completed: "Selesai",
};

const BIKES: Record<string, string> = {
  electric_bike: "Sepeda listrik",
  classic_bike: "Sepeda biasa",
  electric_scooter: "Skuter listrik",
};

const FEATURES: Record<string, string> = {
  hour: "Jam mulai",
  day_of_week: "Hari",
  month_num: "Bulan",
  is_weekend: "Akhir pekan",
  is_commute_peak: "Jam sibuk hari kerja",
  duration_min: "Durasi",
  distance_km: "Jarak",
  speed_kmh: "Kecepatan rata-rata",
  start_casual_history: "Riwayat casual stasiun awal",
  end_casual_history: "Riwayat casual stasiun tujuan",
  is_round_trip: "Kembali ke stasiun awal",
  start_lat: "Lokasi awal (lintang)",
  start_lng: "Lokasi awal (bujur)",
  has_start_station: "Mulai dari stasiun",
  has_end_station: "Selesai di stasiun",
};

export const stageLabel = (s: string) => STAGES[s] ?? s;
export const bikeLabel = (b: string) => BIKES[b] ?? b;
export const featureLabel = (f: string) =>
  f.startsWith("rideable_type=") ? bikeLabel(f.slice("rideable_type=".length)) : FEATURES[f] ?? f;
