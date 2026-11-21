// TypeScript types mirroring backend summary.json

export interface JobFile { name: string; type: string; bytes?: number; }

export interface Job {
  id: string;
  status: string;
  stage: string;
  progress: number;
  files: JobFile[];
  error?: string | null;
  timings: Record<string, number>;
  results_path?: string | null;
  created_at: number;
}

export interface StoredMonth { month: string; }

export interface PreprocStep { step: string; label: string; rows_removed: number; }
export interface PreprocFile {
  name: string; rows_input: number; rows_output: number; rows_without_station: number;
  months: Record<string, number>; steps: PreprocStep[];
}
export interface RiderRow { member: number; casual: number; [k: string]: any; }
export interface MonthlyTest {
  month: string; rows: number; correct: number; wrong: number; accuracy: number; baseline_accuracy: number;
  precision: number; recall: number; f1: number; auc_roc: number; casual_share: number;
}
export interface ModelSection {
  available: boolean;
  reason?: string;
  target: string;
  algorithm: string;
  split: { train: string[]; test_months: string[]; test: string };
  test_metrics: Record<string, number>;
  confusion_matrix: { tp: number; fp: number; tn: number; fn: number };
  roc_curve: { fpr: number; tpr: number }[];
  pr_curve: { recall: number; precision: number }[];
  feature_importance: { feature: string; importance: number }[];
  monthly_tests: MonthlyTest[];
  model_path: string;
}
export interface StationCluster {
  cluster: number; label: string; recommendation: string; size: number; avg_rides: number;
  casual_share: number; weekend_share: number; commute_share: number; avg_duration: number;
  round_trip_share: number; electric_share: number;
}
export interface StationPoint { station: string; lat: number; lng: number; rides: number; cluster: number; casual_share: number; }

export interface Summary {
  job_id: string;
  months_in_store: string[];
  months_imported: string[];
  preprocessing_report: {
    files: PreprocFile[]; months: Record<string, number>; rows_input: number; rows_output: number;
    data_min_date: string; cross_file_duplicates_removed: number; hdfs_paths: Record<string, string>;
  };
  kpis: {
    rides: number; stations: number; months: number; member_share: number; electric_share: number;
    without_station_share: number; weekend_share: number; avg_duration_min: number;
    median_duration_min: number; date_from: string; date_to: string;
  };
  analytics: {
    monthly: RiderRow[]; weekday_hourly: RiderRow[]; weekend_hourly: RiderRow[]; by_dow: RiderRow[]; by_bike: RiderRow[];
    by_rider: { member_casual: string; rides: number; avg_duration: number; median_duration: number; avg_distance: number; weekend_share: number; round_trip_share: number; commute_peak_share: number }[];
    top_stations: { station: string; rides: number; casual_share: number }[];
    top_routes: { from: string; to: string; rides: number }[];
  };
  model: ModelSection;
  stations: {
    chosen_k: number; silhouette: number; silhouette_by_k: Record<string, number>;
    min_station_rides: number; stations_clustered: number; clusters: StationCluster[]; points: StationPoint[];
  };
  insights: { title: string; detail: string; recommendation: string }[];
  timings: Record<string, number>;
  hdfs_results_path: string;
}
