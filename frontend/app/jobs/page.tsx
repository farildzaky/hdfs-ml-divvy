"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { stageLabel } from "@/lib/labels";
import type { Job } from "@/lib/types";

const STATUS_COLOR: Record<string, string> = {
  completed: "text-emerald-500", failed: "text-rose-500", running: "text-amber-500",
};

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const load = () => api.jobs().then(setJobs).catch((e) => setErr(e.message));
    load();
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, []);

  if (err) return <div className="card text-rose-500">Tidak bisa memuat jobs: {err}</div>;
  if (!jobs) return <div className="card animate-pulse">Memuat…</div>;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Riwayat Import</h1>
      {jobs.length === 0 && <div className="card">Belum ada import.</div>}
      <div className="space-y-2">
        {jobs.map((jb) => (
          <Link key={jb.id} href={`/jobs/${jb.id}`}
            className="card flex items-center justify-between hover:border-brand/50">
            <div>
              <div className="font-medium">{jb.files.map((f) => f.name).join(", ")}</div>
              <div className="text-sm">{new Date(jb.created_at * 1000).toLocaleString("id-ID")}</div>
            </div>
            <div className="text-right">
              <div className={`text-sm font-medium ${STATUS_COLOR[jb.status] || ""}`}>{jb.status === "failed" ? "Gagal" : stageLabel(jb.stage)}</div>
              <div className="h-1.5 w-32 overflow-hidden rounded bg-slate-200 dark:bg-white/10">
                <div className="h-full bg-brand" style={{ width: `${(jb.progress || 0) * 100}%` }} />
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
