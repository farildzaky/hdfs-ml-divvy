import type { Job, ModelVersion, StoredMonth, Summary } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

async function j<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

export const api = {
  jobs: () => j<Job[]>("/jobs"),
  job: (id: string) => j<Job>(`/jobs/${id}`),
  results: (id: string) => j<Summary>(`/jobs/${id}/results`),
  months: () => j<StoredMonth[]>("/months"),
  models: () => j<ModelVersion[]>("/models"),
  async upload(files: File[]) {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    const r = await fetch(`${BASE}/upload`, { method: "POST", body: fd });
    if (!r.ok) throw new Error((await r.json()).detail || "upload gagal");
    return r.json() as Promise<{ job_id: string; files: { name: string; type: string; bytes: number }[] }>;
  },
};

export const fmtNum = (n: number) => new Intl.NumberFormat("id-ID").format(n || 0);
export const pct = (n: number) => `${((n || 0) * 100).toFixed(1)}%`;
