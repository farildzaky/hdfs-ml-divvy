import "./globals.css";
import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Bike Share Analytics",
  description: "Analitik perjalanan sepeda sewa dengan HDFS dan Spark MLlib",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id" className="dark">
      <body>
        <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/80 backdrop-blur dark:border-white/10 dark:bg-ink/80">
          <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-3">
            <Link href="/" className="flex items-center gap-2 font-semibold">
              <span className="grid h-7 w-7 place-items-center rounded-lg bg-brand-600 text-white">◆</span>
              Bike Share Analytics
            </Link>
            <nav className="flex gap-1 text-sm">
              <Link href="/" className="tab">Import</Link>
              <Link href="/jobs" className="tab">Riwayat Import</Link>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-7xl px-5 py-8">{children}</main>
      </body>
    </html>
  );
}
