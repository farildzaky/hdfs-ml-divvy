"use client";
import { useEffect, useState } from "react";
import { api, fmtNum, pct } from "@/lib/api";
import { bikeLabel, featureLabel, stageLabel } from "@/lib/labels";
import type { Job, Summary } from "@/lib/types";
import { BarX, CurveX, MonthlyTestChart, PALETTE, RiderBars, RiderLines, StationMap } from "@/components/charts";
import { Badge, Section, SimpleTable, StatTile } from "@/components/ui";

const STAGES = ["preprocessing", "uploading_hdfs", "reading_hdfs", "spark_analytics", "loading_model", "monthly_test",
  "clustering", "completed"];
const TABS = ["Insight", "Ringkasan", "Analisis", "Model", "Stasiun", "Pre-processing", "Info teknis"];

export default function JobDetail({ params }: { params: { id: string } }) {
  const id = params.id;
  const [job, setJob] = useState<Job | null>(null);
  const [sum, setSum] = useState<Summary | null>(null);
  const [tab, setTab] = useState(0);

  useEffect(() => {
    let timer: any;
    const poll = async () => {
      try {
        const j = await api.job(id);
        setJob(j);
        if (j.status === "completed" && !sum) api.results(id).then(setSum).catch(() => {});
        if (j.status !== "completed" && j.status !== "failed") timer = setTimeout(poll, 2000);
      } catch { timer = setTimeout(poll, 2000); }
    };
    poll();
    return () => clearTimeout(timer);
  }, [id, sum]);

  if (!job) return <div className="card animate-pulse">Memuat…</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <h1 className="truncate text-xl font-semibold">Hasil import</h1>
          <div className="truncate text-sm">{job.files.map((f) => f.name).join(", ")}</div>
        </div>
        <Badge color={job.status === "completed" ? "emerald" : job.status === "failed" ? "rose" : "amber"}>
          {job.status === "failed" ? "Gagal" : stageLabel(job.stage)}
        </Badge>
      </div>

      <Stepper job={job} />

      {job.status === "failed" && (
        <div className="card border-rose-500/40">
          <h3 className="mb-2 font-semibold text-rose-500">Gagal pada tahap: {stageLabel(job.stage)}</h3>
          <pre className="overflow-x-auto whitespace-pre-wrap text-xs text-rose-400">{job.error}</pre>
        </div>
      )}

      {sum && (
        <>
          <div className="flex gap-1 overflow-x-auto border-b border-slate-200 pb-2 dark:border-white/10">
            {TABS.map((t, i) => (
              <button key={t} className={`tab ${tab === i ? "tab-active" : ""}`} onClick={() => setTab(i)}>{t}</button>
            ))}
          </div>
          {tab === 0 && <Insight s={sum} />}
          {tab === 1 && <Ringkasan s={sum} />}
          {tab === 2 && <Analisis s={sum} />}
          {tab === 3 && <Model s={sum} />}
          {tab === 4 && <Stasiun s={sum} />}
          {tab === 5 && <Preprocessing s={sum} />}
          {tab === 6 && <InfoTeknis id={id} s={sum} />}
        </>
      )}
    </div>
  );
}

function Stepper({ job }: { job: Job }) {
  const curIdx = STAGES.indexOf(job.stage);
  return (
    <div className="flex items-center gap-1 overflow-x-auto">
      {STAGES.map((s, i) => {
        const done = job.status === "completed" || (curIdx > i && curIdx >= 0);
        const failed = job.status === "failed" && curIdx === i;
        const active = curIdx === i && job.status === "running";
        return (
          <div key={s} className="flex items-center">
            <div className={`flex items-center gap-2 whitespace-nowrap rounded-lg px-2.5 py-1.5 text-xs font-medium
              ${failed ? "bg-rose-500/15 text-rose-500" : done ? "bg-emerald-500/15 text-emerald-500" : active ? "bg-amber-500/15 text-amber-600"
                : "bg-slate-200/50 text-slate-600 dark:bg-white/5 dark:text-slate-300"}`}>
              <span>{failed ? "✕" : done ? "✓" : active ? "●" : "○"}</span>{stageLabel(s)}
            </div>
            {i < STAGES.length - 1 && <span className="px-1">→</span>}
          </div>
        );
      })}
    </div>
  );
}

function Insight({ s }: { s: Summary }) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {s.insights.map((it) => (
        <div key={it.title} className="card">
          <h3 className="font-semibold">{it.title}</h3>
          <p className="mt-2 text-sm">{it.detail}</p>
          <p className="mt-3 rounded-lg bg-brand/10 px-3 py-2 text-sm"><b>Rekomendasi:</b> {it.recommendation}</p>
        </div>
      ))}
    </div>
  );
}

function Ringkasan({ s }: { s: Summary }) {
  const k = s.kpis;
  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
      <StatTile label="Total perjalanan" value={fmtNum(k.rides)} />
      <StatTile label="Perjalanan oleh member" value={pct(k.member_share)} sub={`Casual ${pct(1 - k.member_share)}`} />
      <StatTile label="Jumlah stasiun awal" value={fmtNum(k.stations)} />
      <StatTile label="Jumlah bulan yang dianalisis" value={fmtNum(k.months)} />
      <StatTile label="Durasi tengah (median)" value={`${k.median_duration_min.toFixed(1)} menit`} sub={`Rata-rata ${k.avg_duration_min.toFixed(1)} menit`} />
      <StatTile label="Memakai sepeda listrik" value={pct(k.electric_share)} />
      <StatTile label="Terjadi saat akhir pekan" value={pct(k.weekend_share)} />
      <StatTile label="Periode data" value={<span className="text-sm">{k.date_from}</span>} sub={`sampai ${k.date_to}`} />
    </div>
  );
}

function Analisis({ s }: { s: Summary }) {
  const a = s.analytics;
  const bikes = a.by_bike.map((r: any) => ({ ...r, rideable_type: bikeLabel(r.rideable_type) }));
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Section title="Jumlah perjalanan per bulan"><RiderBars data={a.monthly} x="month" stacked /></Section>
      <Section title="Jumlah perjalanan per hari"><RiderBars data={a.by_dow} x="day" /></Section>
      <Section title="Jumlah perjalanan per jam, hari kerja"><RiderLines data={a.weekday_hourly} x="hour" /></Section>
      <Section title="Jumlah perjalanan per jam, akhir pekan"><RiderLines data={a.weekend_hourly} x="hour" /></Section>
      <Section title="Jumlah perjalanan per jenis sepeda"><RiderBars data={bikes} x="rideable_type" /></Section>
      <Section title="Perbandingan member dan casual">
        <SimpleTable cols={["Pengguna", "Perjalanan", "Durasi tengah", "Jarak rata-rata", "Saat akhir pekan", "Saat jam sibuk", "Kembali ke stasiun awal"]}
          rows={a.by_rider.map((r) => [r.member_casual === "member" ? "Member" : "Casual", fmtNum(r.rides), `${r.median_duration.toFixed(1)} menit`, `${r.avg_distance.toFixed(2)} km`,
            pct(r.weekend_share), pct(r.commute_peak_share), pct(r.round_trip_share)])} />
      </Section>
      <Section title="Stasiun awal paling ramai">
        <SimpleTable cols={["Stasiun", "Perjalanan", "Oleh casual"]}
          rows={a.top_stations.map((r) => [r.station, fmtNum(r.rides), pct(r.casual_share)])} />
      </Section>
      <Section title="Rute paling ramai">
        <SimpleTable cols={["Dari", "Ke", "Perjalanan"]}
          rows={a.top_routes.map((r) => [r.from, r.to, fmtNum(r.rides)])} />
      </Section>
    </div>
  );
}

function Model({ s }: { s: Summary }) {
  const m = s.model;
  if (!m.available) return <div className="card">{m.reason}</div>;
  const t = m.test_metrics;
  const cm = m.confusion_matrix;
  const months = m.split.test_months;
  const majority = t.casual_share > 0.5 ? "casual" : "member";
  const features = m.feature_importance.slice(0, 12).map((f: any) => ({ ...f, feature: featureLabel(f.feature) }));
  return (
    <div className="space-y-4">
      <Section title="Model menebak: perjalanan ini oleh member atau casual?" right={
        <div className="flex gap-2">
          <Badge color="emerald">Versi {m.model_version}</Badge>
          <Badge>Tidak dilatih saat upload</Badge>
        </div>}>
        <div className="grid gap-3 text-sm md:grid-cols-3">
          <StatTile label="Algoritma" value="Gradient Boosted Trees" />
          <StatTile label="Data untuk belajar" value={`${m.split.train.length} bulan`} sub={`${m.split.train[0]} sampai ${m.split.train[m.split.train.length - 1]}`} />
          <StatTile label="Data untuk menguji" value={`${months.length} bulan`} sub={`${months[0]} sampai ${months[months.length - 1]}`} />
        </div>
      </Section>

      <Section title="Hasil uji tiap bulan">
        <MonthlyTestChart data={m.monthly_tests} />
        <div className="mt-4">
          <SimpleTable cols={["Bulan", "Perjalanan diuji", "Tebakan benar", "Tebakan salah", "Akurasi model", "Akurasi tanpa model", "Selisih", "Casual yang ditemukan"]}
            rows={m.monthly_tests.map((r) => [r.month, fmtNum(r.rows), fmtNum(r.correct), fmtNum(r.wrong), pct(r.accuracy), pct(r.baseline_accuracy),
              `${((r.accuracy - r.baseline_accuracy) * 100).toFixed(1)} poin`, pct(r.recall)])} />
        </div>
      </Section>

      <div className="grid gap-4 md:grid-cols-2">
        <Section title={`Rincian bulan terbaru, ${m.split.test}`}>
          <div className="grid grid-cols-2 gap-3">
            <StatTile label="Akurasi model" value={pct(t.accuracy)} />
            <StatTile label={`Akurasi jika selalu menebak ${majority}`} value={pct(t.baseline_accuracy)} />
            <StatTile label="Tebakan casual yang benar (precision)" value={pct(t.precision)} />
            <StatTile label="Casual yang berhasil ditemukan (recall)" value={pct(t.recall)} />
            <StatTile label="Kemampuan membedakan (AUC-ROC, 0,5 sampai 1)" value={t.auc_roc.toFixed(3)} />
            <StatTile label="Skor gabungan precision dan recall (F1)" value={t.f1.toFixed(3)} />
          </div>
        </Section>
        <Section title="Tebakan model dibanding kenyataan">
          <div className="grid grid-cols-2 gap-2 text-center">
            <div className="rounded-lg bg-emerald-500/10 p-4"><div className="text-sm">Casual, ditebak casual (benar)</div><div className="text-xl font-semibold">{fmtNum(cm.tp)}</div></div>
            <div className="rounded-lg bg-rose-500/10 p-4"><div className="text-sm">Member, ditebak casual (salah)</div><div className="text-xl font-semibold">{fmtNum(cm.fp)}</div></div>
            <div className="rounded-lg bg-rose-500/10 p-4"><div className="text-sm">Casual, ditebak member (salah)</div><div className="text-xl font-semibold">{fmtNum(cm.fn)}</div></div>
            <div className="rounded-lg bg-emerald-500/10 p-4"><div className="text-sm">Member, ditebak member (benar)</div><div className="text-xl font-semibold">{fmtNum(cm.tn)}</div></div>
          </div>
        </Section>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Section title="Kurva ROC"><CurveX data={m.roc_curve} x="fpr" y="tpr" /></Section>
        <Section title="Kurva Precision-Recall"><CurveX data={m.pr_curve} x="recall" y="precision" color="#ec4899" /></Section>
      </div>

      <Section title="Data yang paling memengaruhi tebakan model">
        <BarX data={features} x="feature" y="importance" name="Pengaruh" height={320} />
      </Section>
    </div>
  );
}

function Stasiun({ s }: { s: Summary }) {
  const st = s.stations;
  return (
    <div className="space-y-4">
      <Section title={`${fmtNum(st.stations_clustered)} stasiun terbagi menjadi ${st.chosen_k} kelompok (KMeans, skor silhouette ${st.silhouette})`}>
        <StationMap points={st.points} clusters={st.clusters} />
      </Section>
      <div className="grid gap-4 md:grid-cols-2">
        {st.clusters.map((c) => (
          <div key={c.cluster} className="card">
            <div className="mb-2 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="h-3 w-3 rounded-full" style={{ background: PALETTE[c.cluster % PALETTE.length] }} />
                <h4 className="font-semibold">{c.label}</h4>
              </div>
              <Badge>{fmtNum(c.size)} stasiun</Badge>
            </div>
            <SimpleTable cols={["Ciri kelompok", "Nilai"]} rows={[
              ["Rata-rata perjalanan per stasiun", fmtNum(Math.round(c.avg_rides))],
              ["Perjalanan oleh casual", pct(c.casual_share)],
              ["Perjalanan saat jam sibuk", pct(c.commute_share)],
              ["Perjalanan saat akhir pekan", pct(c.weekend_share)],
              ["Durasi rata-rata", `${c.avg_duration.toFixed(1)} menit`],
              ["Memakai sepeda listrik", pct(c.electric_share)],
            ]} />
            <p className="mt-3 text-sm"><b>Rekomendasi:</b> {c.recommendation}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function Preprocessing({ s }: { s: Summary }) {
  const r = s.preprocessing_report;
  const noStation = r.files.reduce((n, f) => n + f.rows_without_station, 0);
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatTile label="Baris dalam file" value={fmtNum(r.rows_input)} />
        <StatTile label="Baris setelah dibersihkan" value={fmtNum(r.rows_output)} />
        <StatTile label="Tanpa nama stasiun, tetap disimpan" value={fmtNum(noStation)} />
        <StatTile label="Jumlah bulan yang diimport" value={fmtNum(s.months_imported.length)} />
      </div>
      {r.files.map((f) => (
        <Section key={f.name} title={f.name}
          right={<Badge color="indigo">{fmtNum(f.rows_input)} → {fmtNum(f.rows_output)} baris</Badge>}>
          <SimpleTable cols={["Aturan pembersihan", "Baris dihapus"]}
            rows={f.steps.map((st) => [st.label, fmtNum(st.rows_removed)])} />
        </Section>
      ))}
    </div>
  );
}

function InfoTeknis({ id, s }: { id: string; s: Summary }) {
  const paths = s.preprocessing_report.hdfs_paths;
  return (
    <div className="space-y-4">
      <Section title="Lama tiap tahap">
        <SimpleTable cols={["Tahap", "Detik"]} rows={Object.entries(s.timings).map(([k, v]) => [stageLabel(k), v])} />
      </Section>
      <Section title="Lokasi penyimpanan">
        <SimpleTable cols={["Isi", "Lokasi"]} rows={[
          ["ID import", id],
          ["File asli di HDFS", String(paths.raw)],
          ["Data bersih di HDFS", String(paths.clean)],
          ["Hasil analisis di HDFS", String(paths.results)],
          ...(s.model.available ? [["Model di HDFS", s.model.model_path]] : []),
          ["Bulan di HDFS", s.months_in_store.join(", ")],
        ]} />
        <div className="mt-3 flex gap-3 text-sm">
          <a className="btn" href="http://localhost:9870/explorer.html#/bikeshare" target="_blank" rel="noreferrer">Buka HDFS</a>
          <a className="btn" href="http://localhost:8080" target="_blank" rel="noreferrer">Buka Spark</a>
        </div>
      </Section>
    </div>
  );
}
