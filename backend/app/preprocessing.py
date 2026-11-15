"""Pembersihan data, berjalan SEBELUM HDFS.

Membaca satu file perjalanan (.csv), membersihkannya, mencatat jumlah baris yang
dibuang per aturan, lalu menulis parquet per bulan. File diproses satu per satu,
jadi memori paling besar sebesar satu file.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from app import config

REQUIRED = ["ride_id", "rideable_type", "started_at", "ended_at",
            "start_station_name", "start_station_id", "end_station_name",
            "end_station_id", "start_lat", "start_lng", "end_lat", "end_lng",
            "member_casual"]
RIDER_TYPES = {"member", "casual"}
TEXT_COLS = ["ride_id", "rideable_type", "start_station_name", "start_station_id",
             "end_station_name", "end_station_id", "member_casual"]

SCHEMA = pa.schema([
    ("ride_id", pa.string()), ("rideable_type", pa.string()),
    ("started_at", pa.timestamp("us")), ("ended_at", pa.timestamp("us")),
    ("start_station_name", pa.string()), ("start_station_id", pa.string()),
    ("end_station_name", pa.string()), ("end_station_id", pa.string()),
    ("start_lat", pa.float64()), ("start_lng", pa.float64()),
    ("end_lat", pa.float64()), ("end_lng", pa.float64()),
    ("member_casual", pa.string()), ("duration_min", pa.float64()),
    ("distance_km", pa.float64()),
])


class InvalidFile(ValueError):
    """The uploaded file cannot be used; the message is shown to the user."""


def _norm(col) -> str:
    return str(col).strip().lower() if col is not None else ""


def _check_header(columns: List[str], where: str) -> None:
    missing = [c for c in REQUIRED if c not in columns]
    if missing:
        raise InvalidFile(f"{where}: kolom wajib tidak ada: {', '.join(missing)}")


def _read_csv(path: Path, display: str, nrows: "int | None" = None) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, keep_default_na=False, nrows=nrows)
    df.columns = [_norm(c) for c in df.columns]
    _check_header(list(df.columns), display)
    return df


def validate(path: Path, display: str) -> None:
    """Cek cepat saat upload, supaya file yang salah ditolak sebelum masuk antrean."""
    if path.suffix.lower() != ".csv":
        raise InvalidFile(f"{display}: hanya file .csv yang didukung.")
    try:
        _read_csv(path, display, nrows=1)
    except InvalidFile:
        raise
    except Exception as e:  # file kosong, encoding salah, atau file biner yang diberi nama .csv
        raise InvalidFile(f"{display}: file tidak bisa dibaca ({type(e).__name__}).")


def haversine_km(lat1, lng1, lat2, lng2):
    lat1, lng1, lat2, lng2 = map(np.radians, (lat1, lng1, lat2, lng2))
    a = (np.sin((lat2 - lat1) / 2) ** 2
         + np.cos(lat1) * np.cos(lat2) * np.sin((lng2 - lng1) / 2) ** 2)
    return 6371.0 * 2 * np.arcsin(np.sqrt(a))


def assign_months(started: pd.Series) -> pd.Series:
    """Label bulan per baris. Baris spill-over digabung ke bulan utama terdekat,
    supaya import Desember tidak menimpa November hanya karena ada perjalanan
    yang mulai beberapa menit sebelum tengah malam 30 November."""
    periods = started.dt.to_period("M")
    shares = periods.value_counts(normalize=True)
    major = sorted(shares[shares >= config.SPILL_SHARE].index)
    if not major:
        major = [shares.idxmax()]
    mapping = {p: min(major, key=lambda m: abs((m - p).n)) for p in shares.index}
    return periods.map(mapping).astype(str)


def clean(df: pd.DataFrame) -> "tuple[pd.DataFrame, list]":
    steps = []

    def drop(mask, step, label):
        nonlocal df
        steps.append({"step": step, "label": label, "rows_removed": int(mask.sum())})
        df = df[~mask]

    df = df[REQUIRED].copy()
    for c in TEXT_COLS:
        df[c] = df[c].where(df[c].notna() & (df[c].astype(str).str.strip() != ""), None)

    drop(df["ride_id"].isna(), "require_id", "ID perjalanan kosong")
    drop(df.duplicated("ride_id"), "drop_duplicates", "ID perjalanan ganda")

    df["started_at"] = pd.to_datetime(df["started_at"], errors="coerce", format="ISO8601")
    df["ended_at"] = pd.to_datetime(df["ended_at"], errors="coerce", format="ISO8601")
    drop(df["started_at"].isna() | df["ended_at"].isna(), "parse_time", "Waktu mulai atau selesai tidak terbaca")

    drop(~df["member_casual"].isin(RIDER_TYPES), "rider_type",
         "Jenis pengguna bukan member atau casual")

    minutes = (df["ended_at"] - df["started_at"]).dt.total_seconds() / 60.0
    df["duration_min"] = minutes
    drop((minutes < config.MIN_DURATION_MIN) | (minutes > config.MAX_DURATION_MIN),
         "duration", "Durasi kurang dari 1 menit atau lebih dari 24 jam")

    for c in ["start_lat", "start_lng", "end_lat", "end_lng"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    drop(df["start_lat"].isna() | df["start_lng"].isna(), "start_coords",
         "Lokasi awal kosong")

    df["distance_km"] = haversine_km(df["start_lat"], df["start_lng"],
                                     df["end_lat"], df["end_lng"])
    drop(df["distance_km"] > config.MAX_DISTANCE_KM, "distance", "Jarak lebih dari 100 km")

    drop(df["started_at"] < pd.Timestamp(config.DATA_MIN_DATE), "too_old",
         f"Sebelum {config.DATA_MIN_DATE}")
    return df, steps


def process_file(path: Path, display: str, out_dir: Path, part: int) -> dict:
    """Bersihkan satu file, tulis ke ``out_dir/month=YYYY-MM/part-N.parquet``."""
    raw = _read_csv(path, display)
    rows_in = len(raw)
    df, steps = clean(raw)
    del raw
    if df.empty:
        raise InvalidFile(f"{display}: tidak ada baris yang lolos pembersihan. Data yang diterima mulai {config.DATA_MIN_DATE}.")

    no_station = int((df["start_station_name"].isna() | df["end_station_name"].isna()).sum())
    months = assign_months(df["started_at"])
    written = {}
    for month, group in df.groupby(months):
        target = out_dir / f"month={month}" / f"part-{part:03d}.parquet"
        target.parent.mkdir(parents=True, exist_ok=True)
        table = pa.Table.from_pandas(group, schema=SCHEMA, preserve_index=False)
        pq.write_table(table, target)
        written[month] = len(group)
    return {"name": display, "rows_input": rows_in, "rows_output": len(df),
            "rows_without_station": no_station, "months": written, "steps": steps}


def run_all(files: List[dict], out_dir: Path) -> dict:
    """``files``: list of {"path": Path, "name": display name}."""
    reports = [process_file(Path(f["path"]), f["name"], out_dir, i)
               for i, f in enumerate(files)]
    months: dict = {}
    for r in reports:
        for m, n in r["months"].items():
            months[m] = months.get(m, 0) + n
    return {"files": reports, "months": dict(sorted(months.items())),
            "rows_input": sum(r["rows_input"] for r in reports),
            "rows_output": sum(r["rows_output"] for r in reports),
            "data_min_date": config.DATA_MIN_DATE}
