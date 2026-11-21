"use client";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api, fmtNum } from "@/lib/api";
import type { StoredMonth } from "@/lib/types";
import { Badge, Section, SimpleTable } from "@/components/ui";

const ACCEPTED = [".csv"];

export default function ImportPage() {
  const router = useRouter();
  const [files, setFiles] = useState<File[]>([]);
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [months, setMonths] = useState<StoredMonth[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.months().then(setMonths).catch(() => {});
  }, []);

  const add = (list: FileList | null) => {
    if (!list) return;
    const all = Array.from(list);
    const ok = all.filter((x) => ACCEPTED.some((e) => x.name.toLowerCase().endsWith(e)));
    setErr(ok.length < all.length ? "File selain .csv dilewati." : null);
    setFiles((f) => [...f, ...ok]);
  };

  const submit = async () => {
    setBusy(true); setErr(null);
    try {
      const { job_id } = await api.upload(files);
      router.push(`/jobs/${job_id}`);
    } catch (e: any) { setErr(e.message); setBusy(false); }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Import data perjalanan sepeda</h1>

      <div
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); add(e.dataTransfer.files); }}
        onClick={() => inputRef.current?.click()}
        className={`grid cursor-pointer place-items-center rounded-2xl border-2 border-dashed p-12 text-center transition
          ${drag ? "border-brand bg-brand/5" : "border-slate-300 dark:border-white/15"}`}
      >
        <input ref={inputRef} type="file" accept=".csv" multiple hidden
          onChange={(e) => add(e.target.files)} />
        <div className="text-5xl">⬆︎</div>
        <p className="mt-3 font-medium">Tarik file CSV ke sini, atau klik untuk memilih file</p>
      </div>

      {err && <div className="rounded-lg bg-rose-500/10 px-3 py-2 text-sm text-rose-500">{err}</div>}

      {files.length > 0 && (
        <div className="card space-y-3">
          <div className="text-sm font-medium">{files.length} file dipilih</div>
          {files.map((f, i) => (
            <div key={i} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 dark:bg-white/5">
              <span className="text-sm">{f.name}</span>
              <div className="flex items-center gap-3 text-sm">
                <span>{fmtNum(Math.round(f.size / 1024 / 1024))} MB</span>
                <button onClick={() => setFiles((x) => x.filter((_, j) => j !== i))}
                  className="text-rose-500 hover:underline">hapus</button>
              </div>
            </div>
          ))}
          <button className="btn" disabled={busy} onClick={submit}>
            {busy ? "Mengunggah file…" : "Mulai import dan analisis"}
          </button>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        <Section title="Data di HDFS" right={<Badge color="indigo">{months.length} bulan</Badge>}>
          {months.length === 0 ? <p className="text-sm">Belum ada data.</p> : (
            <SimpleTable cols={["Bulan"]} rows={months.map((m) => [m.month])} />
          )}
        </Section>
      </div>
    </div>
  );
}
