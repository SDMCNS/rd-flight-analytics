"""Read access to a database produced by :func:`ectl_flights.etl.run_etl`."""

from __future__ import annotations

import sqlite3
from functools import cached_property
from pathlib import Path
from typing import Union

import pandas as pd

from . import geo


class FlightDB:
    """Convenience wrapper around the flights SQLite database.

    Heavy/static tables (summary, FIRs, routes, airports) are cached on first use.
    """

    def __init__(self, path: Union[str, Path] = "flights.db"):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(f"{self.path} not found - run `ectl etl` first")
        self.conn = sqlite3.connect(self.path, check_same_thread=False)

    def close(self) -> None:
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def query(self, sql: str, params=()) -> pd.DataFrame:
        return pd.read_sql(sql, self.conn, params=params)

    # --- cached tables -------------------------------------------------
    @cached_property
    def _summary(self) -> pd.DataFrame:
        df = self.query("SELECT * FROM flight_summary ORDER BY actual_dep_time")
        for col in ("actual_dep_time", "actual_arr_time", "planned_dep_time", "planned_arr_time"):
            if col in df:
                df[col] = pd.to_datetime(df[col])
        return df

    def summary(self) -> pd.DataFrame:
        """Per-flight summary (copy, safe to mutate)."""
        return self._summary.copy()

    @cached_property
    def airports(self) -> pd.DataFrame:
        return self.query(
            "SELECT ident, name, latitude_deg, longitude_deg FROM airports_db "
            "WHERE latitude_deg IS NOT NULL AND longitude_deg IS NOT NULL"
        )

    @cached_property
    def firs(self) -> dict:
        """``{airspace_id: {'latlon': [...], 'shape': Polygon}}``"""
        raw = self.query(
            'SELECT "Airspace ID", Latitude, Longitude FROM firs_raw '
            'ORDER BY "Airspace ID", "Sequence Number"'
        )
        return geo.build_fir_polygons(raw)

    @cached_property
    def routes(self) -> dict:
        """``{route_id: {'latlon': [...], 'shape': LineString}}``"""
        raw = self.query(
            'SELECT "Route ID", Latitude, Longitude FROM routes_raw '
            'ORDER BY "Route ID", "Sequence Number"'
        )
        return geo.build_route_lines(raw)

    # --- per-flight ----------------------------------------------------
    def actual_points(self, ectrl_id: int) -> pd.DataFrame:
        return self.query(
            'SELECT * FROM actual_flights WHERE "ECTRL ID" = ? ORDER BY "Sequence Number"',
            (int(ectrl_id),),
        )

    def planned_points(self, ectrl_id: int) -> pd.DataFrame:
        return self.query(
            'SELECT * FROM planned_flights WHERE "ECTRL ID" = ? ORDER BY "Sequence Number"',
            (int(ectrl_id),),
        )

    def flight(self, ectrl_id: int) -> pd.Series:
        """Summary row for one flight."""
        s = self._summary
        rows = s[s["ECTRL ID"] == int(ectrl_id)]
        if rows.empty:
            raise KeyError(ectrl_id)
        return rows.iloc[0]

    def flights_for_registration(self, registration: str) -> pd.DataFrame:
        s = self._summary
        return s[s["AC Registration"] == registration].sort_values("actual_dep_time")

    def airport_coords(self, ident: str):
        """``(lat, lon)`` for an airport ident, or ``None``."""
        row = self.airports[self.airports["ident"] == ident]
        if row.empty:
            return None
        return float(row.iloc[0]["latitude_deg"]), float(row.iloc[0]["longitude_deg"])

