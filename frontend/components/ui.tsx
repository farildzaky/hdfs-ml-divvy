"use client";
import React from "react";

export function StatTile({ label, value, sub }: { label: string; value: React.ReactNode; sub?: string }) {
  return (
    <div className="kpi">
      <div className="text-sm text-slate-700 dark:text-slate-200">{label}</div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
      {sub && <div className="mt-0.5 text-sm text-slate-700 dark:text-slate-200">{sub}</div>}
    </div>
  );
}

export function Section({ title, children, right }: { title: string; children: React.ReactNode; right?: React.ReactNode }) {
  return (
    <div className="card">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="font-semibold">{title}</h3>
        {right}
      </div>
      {children}
    </div>
  );
}

export function SimpleTable({ cols, rows }: { cols: string[]; rows: (string | number)[][] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-left text-sm text-slate-700 dark:border-white/10 dark:text-slate-200">
            {cols.map((c) => <th key={c} className="px-2 py-2 font-medium">{c}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-slate-100 last:border-0 dark:border-white/5">
              {r.map((c, j) => <td key={j} className="px-2 py-1.5 tabular-nums">{c}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Badge({ children, color = "slate" }: { children: React.ReactNode; color?: string }) {
  const map: Record<string, string> = {
    emerald: "bg-emerald-500/15 text-emerald-500", amber: "bg-amber-500/15 text-amber-600",
    rose: "bg-rose-500/15 text-rose-500", indigo: "bg-indigo-500/15 text-indigo-400",
    slate: "bg-slate-500/15 text-slate-400",
  };
  return <span className={`rounded px-2 py-0.5 text-xs font-medium ${map[color]}`}>{children}</span>;
}
