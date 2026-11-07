"""Load standardised CSVs, compute per-flight summaries and write to SQLite."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Dict, Union

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

log = logging.getLogger(__name__)
PathLike = Union[str, Path]

TIME_FORMAT = "%d-%m-%Y %H:%M:%S"

#: logical name -> (standard csv filename, sqlite table name)
SOURCES = {
    "actual": ("flights_anonymized.csv", "actual_flights"),
    "planned": ("planned_flights_anonymized.csv", "planned_flights"),
    "meta": ("flights.csv", None),
    "airports": ("airports.csv", "airports_db"),
    "firs": ("fir.csv", "firs_raw"),
    "routes": ("routes.csv", "routes_raw"),
}


def load_raw(data_dir: PathLike = ".") -> Dict[str, pd.DataFrame]:
    """Read all standardised CSVs into DataFrames (column names stripped)."""
    data_dir = Path(data_dir)
    frames = {}
    for key, (fname, _) in SOURCES.items():
        log.info("Loading %s", fname)
        df = pd.read_csv(data_dir / fname, low_memory=False)
        df.columns = [c.strip() for c in df.columns]
        frames[key] = df
        log.info("  %s: %s rows", fname, f"{len(df):,}")

    for key in ("actual", "planned"):
        frames[key]["Time Over"] = pd.to_datetime(frames[key]["Time Over"], format=TIME_FORMAT)
    frames["airports"] = frames["airports"].dropna(subset=["latitude_deg", "longitude_deg"]).copy()
    return frames


class NearestAirport:
    """KD-tree lookup of the nearest airport to lat/lon points."""

    def __init__(self, airports: pd.DataFrame):
        self.airports = airports.reset_index(drop=True)
        self.tree = cKDTree(np.radians(self.airports[["latitude_deg", "longitude_deg"]].values))

    def query(self, lat_lons) -> tuple[np.ndarray, np.ndarray]:
        lat_lons = np.asarray(lat_lons, dtype=float)
        if len(lat_lons) == 0:
            return np.array([]), np.array([])
        _, idx = self.tree.query(np.radians(np.nan_to_num(lat_lons, nan=0.0)), k=1)
        rows = self.airports.iloc[idx]
        return rows["ident"].values, rows["name"].values


def build_flight_summary(
    actual: pd.DataFrame,
    planned: pd.DataFrame,
    meta: pd.DataFrame,
    airports: pd.DataFrame,
) -> pd.DataFrame:
    """One row per flight: times, levels, inferred airports, delays, deviation."""
    g = actual.groupby("ECTRL ID")
    starts = actual.loc[g["Sequence Number"].idxmin()].set_index("ECTRL ID")
    ends = actual.loc[g["Sequence Number"].idxmax()].set_index("ECTRL ID")

    summary = g.agg(
        actual_dep_time=("Time Over", "min"),
        actual_arr_time=("Time Over", "max"),
        max_actual_fl=("Flight Level", "max"),
        actual_waypoints=("Sequence Number", "count"),
    ).reset_index()
    ids = summary["ECTRL ID"]
    summary["dep_lat"] = starts["Latitude"].reindex(ids).values
    summary["dep_lon"] = starts["Longitude"].reindex(ids).values
    summary["arr_lat"] = ends["Latitude"].reindex(ids).values
    summary["arr_lon"] = ends["Longitude"].reindex(ids).values

    finder = NearestAirport(airports)
    summary["origin_airport"], summary["origin_name"] = finder.query(summary[["dep_lat", "dep_lon"]].values)
    summary["destination_airport"], summary["destination_name"] = finder.query(summary[["arr_lat", "arr_lon"]].values)

    planned_summary = planned.groupby("ECTRL ID").agg(
        planned_dep_time=("Time Over", "min"),
        planned_arr_time=("Time Over", "max"),
        max_planned_fl=("Flight Level", "max"),
        planned_waypoints=("Sequence Number", "count"),
    ).reset_index()

    fs = summary.merge(planned_summary, on="ECTRL ID", how="left").merge(meta, on="ECTRL ID", how="left")

    def _delay(actual_col, filed_col):
        filed = pd.to_datetime(fs[filed_col], format="mixed", dayfirst=True)
        return ((fs[actual_col] - filed).dt.total_seconds() / 60).round(1).fillna(0)

    fs["dep_delay_mins"] = _delay("actual_dep_time", "FILED OFF BLOCK TIME")
    fs["arr_delay_mins"] = _delay("actual_arr_time", "FILED ARRIVAL TIME")
    fs["deviation_pct"] = (
        (fs["actual_waypoints"] - fs["planned_waypoints"]).abs()
        / fs["planned_waypoints"].clip(lower=1) * 100
    ).round(1)
    return fs.sort_values("actual_dep_time").reset_index(drop=True)


def write_database(frames: Dict[str, pd.DataFrame], summary: pd.DataFrame, db_path: PathLike) -> None:
    """Write raw tables, summary and indices to a SQLite database."""
    log.info("Writing %s", db_path)
    with sqlite3.connect(db_path) as conn:
        for key, (_, table) in SOURCES.items():
            if table:
                frames[key].to_sql(table, conn, if_exists="replace", index=False)
        summary.to_sql("flight_summary", conn, if_exists="replace", index=False)
        conn.execute('CREATE INDEX IF NOT EXISTS idx_actual_id ON actual_flights("ECTRL ID")')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_planned_id ON planned_flights("ECTRL ID")')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_summary_id ON flight_summary("ECTRL ID")')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_reg ON flight_summary("AC Registration")')


def run_etl(data_dir: PathLike = ".", db_path: PathLike = "flights.db") -> pd.DataFrame:
    """Full pipeline: load CSVs from ``data_dir``, build summary, write ``db_path``."""
    frames = load_raw(data_dir)
    summary = build_flight_summary(frames["actual"], frames["planned"], frames["meta"], frames["airports"])
    write_database(frames, summary, db_path)
    log.info("ETL complete: %s flights", f"{len(summary):,}")
    return summary

