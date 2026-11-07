"""Tabular analytics on the flight summary DataFrame."""

from __future__ import annotations

from datetime import date
from typing import Dict, Iterable, Optional, Tuple

import pandas as pd

#: ICAO type -> average seats and cargo capacity (tonnes).
AC_CAPACITY: Dict[str, Dict[str, float]] = {
    "A319": {"seats": 140, "cargo": 3.5},
    "A320": {"seats": 180, "cargo": 4.0},
    "A321": {"seats": 220, "cargo": 5.0},
    "A332": {"seats": 250, "cargo": 25.0},
    "A333": {"seats": 277, "cargo": 30.0},
    "A359": {"seats": 315, "cargo": 35.0},
    "A388": {"seats": 500, "cargo": 40.0},
    "B737": {"seats": 160, "cargo": 3.5},
    "B738": {"seats": 189, "cargo": 4.0},
    "B752": {"seats": 200, "cargo": 15.0},
    "B763": {"seats": 269, "cargo": 22.0},
    "B772": {"seats": 314, "cargo": 25.0},
    "B77W": {"seats": 365, "cargo": 30.0},
    "B788": {"seats": 242, "cargo": 20.0},
    "B789": {"seats": 290, "cargo": 25.0},
    "E145": {"seats": 50, "cargo": 1.0},
    "E190": {"seats": 100, "cargo": 2.0},
    "F50": {"seats": 50, "cargo": 1.0},
}
DEFAULT_CAPACITY = {"seats": 150, "cargo": 5.0}
FREIGHTER_CARGO_FACTOR = 2.5


def filter_flights(
    summary: pd.DataFrame,
    date_range: Optional[Tuple[date, date]] = None,
    origins: Optional[Iterable[str]] = None,
    destinations: Optional[Iterable[str]] = None,
    fl_range: Optional[Tuple[float, float]] = None,
    operators: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    """Filter the summary by departure date, airports, max FL and operator."""
    df = summary
    dep = pd.to_datetime(df["actual_dep_time"]).dt.date
    mask = pd.Series(True, index=df.index)
    if date_range:
        mask &= (dep >= date_range[0]) & (dep <= date_range[1])
    if origins:
        mask &= df["origin_airport"].isin(list(origins))
    if destinations:
        mask &= df["destination_airport"].isin(list(destinations))
    if fl_range:
        mask &= df["max_actual_fl"].between(fl_range[0], fl_range[1])
    if operators:
        mask &= df["AC Operator"].isin(list(operators))
    return df[mask]


def add_capacity_estimates(summary: pd.DataFrame, capacity: Dict[str, Dict[str, float]] = AC_CAPACITY) -> pd.DataFrame:
    """Add ``Est_Passengers``, ``Est_Cargo_Tonnes`` and ``City_Pair`` columns."""
    df = summary.copy()
    types = df["AC Type"].astype(str).str.upper()
    df["Est_Passengers"] = types.map(lambda t: capacity.get(t, DEFAULT_CAPACITY)["seats"]).astype(float)
    df["Est_Cargo_Tonnes"] = types.map(lambda t: capacity.get(t, DEFAULT_CAPACITY)["cargo"]).astype(float)
    cargo = df["STATFOR Market Segment"].str.contains("Cargo", case=False, na=False)
    df.loc[cargo, "Est_Passengers"] = 0
    df.loc[cargo, "Est_Cargo_Tonnes"] *= FREIGHTER_CARGO_FACTOR
    df["City_Pair"] = df["origin_airport"].astype(str) + " ➔ " + df["destination_airport"].astype(str)
    return df


def _safe_mode(x: pd.Series):
    m = x.mode()
    return m.iloc[0] if not m.empty else "N/A"


def _with_pairs(df: pd.DataFrame) -> pd.DataFrame:
    if "City_Pair" not in df:
        df = df.assign(City_Pair=df["origin_airport"].astype(str) + " ➔ " + df["destination_airport"].astype(str))
    return df


def top_city_pairs(summary: pd.DataFrame, n: int = 15) -> pd.DataFrame:
    return (
        _with_pairs(summary).groupby("City_Pair").agg(
            Flight_Count=("ECTRL ID", "count"),
            Avg_Delay_Mins=("dep_delay_mins", "mean"),
            Primary_Aircraft=("AC Type", _safe_mode),
        ).reset_index().sort_values("Flight_Count", ascending=False).head(n)
    )


def airline_routes(summary: pd.DataFrame, operator: Optional[str] = None) -> pd.DataFrame:
    out = (
        _with_pairs(summary).groupby(["AC Operator", "City_Pair"]).agg(
            Flight_Count=("ECTRL ID", "count"),
            Avg_Distance_Nm=("Actual Distance Flown (nm)", "mean"),
        ).reset_index().sort_values("Flight_Count", ascending=False)
    )
    return out[out["AC Operator"] == operator] if operator else out


def operator_throughput(summary: pd.DataFrame) -> pd.DataFrame:
    df = summary if "Est_Passengers" in summary else add_capacity_estimates(summary)
    return df.groupby("AC Operator").agg(
        Total_Flights=("ECTRL ID", "count"),
        Est_Passengers=("Est_Passengers", "sum"),
        Est_Cargo_Tonnes=("Est_Cargo_Tonnes", "sum"),
    ).reset_index().sort_values("Est_Passengers", ascending=False)


def flights_touching_airports(summary: pd.DataFrame, idents: Iterable[str]) -> pd.DataFrame:
    idents = list(idents)
    return summary[summary["origin_airport"].isin(idents) | summary["destination_airport"].isin(idents)]


def traffic_by_weekday(summary: pd.DataFrame) -> pd.DataFrame:
    dep = pd.to_datetime(summary["actual_dep_time"])
    return dep.dt.day_name().value_counts().rename_axis("Weekday").reset_index(name="Flights")


def traffic_by_hour(summary: pd.DataFrame) -> pd.DataFrame:
    dep = pd.to_datetime(summary["actual_dep_time"])
    return dep.dt.hour.value_counts().sort_index().rename_axis("Dep_Hour").reset_index(name="Flights")

