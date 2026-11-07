"""Spatial helpers: FIR polygons, route lines, crossings and distances."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import pandas as pd
from geopy.distance import geodesic
from shapely import contains_xy
from shapely.geometry import LineString, Polygon


def build_fir_polygons(firs_raw: pd.DataFrame) -> Dict[str, dict]:
    """Build valid FIR polygons from ordered ``Airspace ID, Latitude, Longitude`` rows."""
    out = {}
    for airspace_id, grp in firs_raw.groupby("Airspace ID"):
        coords = list(zip(grp["Latitude"], grp["Longitude"]))
        if len(coords) < 3:
            continue
        try:
            poly = Polygon([(lon, lat) for lat, lon in coords])
        except Exception:
            continue
        if poly.is_valid:
            out[airspace_id] = {"latlon": coords, "shape": poly}
    return out


def build_route_lines(routes_raw: pd.DataFrame) -> Dict[str, dict]:
    """Build route LineStrings from ordered ``Route ID, Latitude, Longitude`` rows."""
    out = {}
    for route_id, grp in routes_raw.groupby("Route ID"):
        coords = list(zip(grp["Longitude"], grp["Latitude"]))
        if len(coords) < 2:
            continue
        try:
            out[route_id] = {"latlon": [(lat, lon) for lon, lat in coords], "shape": LineString(coords)}
        except Exception:
            continue
    return out


def path_distance_nm(points: pd.DataFrame) -> float:
    """Sum of geodesic segment lengths (nm) along a Latitude/Longitude path."""
    if points is None or len(points) < 2:
        return 0.0
    coords = list(zip(points["Latitude"], points["Longitude"]))
    return float(sum(geodesic(a, b).nautical for a, b in zip(coords[:-1], coords[1:])))


def great_circle_nm(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return float(geodesic(a, b).nautical)


def fir_crossings(points: pd.DataFrame, firs: Dict[str, dict]) -> List[Tuple[str, pd.Timestamp]]:
    """FIRs a flight passes through with first entry time, sorted by time.

    ``points`` needs ``Latitude``, ``Longitude`` and ``Time Over`` columns.
    """
    if points.empty:
        return []
    lon = points["Longitude"].to_numpy()
    lat = points["Latitude"].to_numpy()
    times = points["Time Over"].to_numpy() if "Time Over" in points else None
    out = []
    for fir_id, data in firs.items():
        inside = contains_xy(data["shape"], lon, lat)
        if inside.any():
            out.append((fir_id, times[inside].min() if times is not None else None))
    return sorted(out, key=lambda x: (x[1] is None, x[1]))


def firs_passed(points: pd.DataFrame, firs: Dict[str, dict]) -> List[str]:
    return [f for f, _ in fir_crossings(points, firs)]


def airports_in_fir(fir_shape: Polygon, airports: pd.DataFrame) -> pd.DataFrame:
    mask = contains_xy(fir_shape, airports["longitude_deg"].to_numpy(), airports["latitude_deg"].to_numpy())
    return airports[mask].reset_index(drop=True)


def routes_in_fir(fir_shape: Polygon, routes: Dict[str, dict]) -> List[str]:
    return [rid for rid, r in routes.items() if fir_shape.intersects(r["shape"])]


def flight_efficiency(
    actual: pd.DataFrame,
    planned: pd.DataFrame,
    origin: Optional[Tuple[float, float]],
    destination: Optional[Tuple[float, float]],
) -> dict:
    """Ideal (great-circle) vs planned vs actual distance; efficiency = ideal / flown * 100."""
    ideal = great_circle_nm(origin, destination) if origin and destination else 0.0
    act = path_distance_nm(actual)
    plan = path_distance_nm(planned) if planned is not None and not planned.empty else 0.0
    return {
        "ideal_nm": ideal,
        "planned_nm": plan,
        "actual_nm": act,
        "planned_efficiency_pct": ideal / plan * 100 if plan > 0 else 0.0,
        "actual_efficiency_pct": ideal / act * 100 if act > 0 else 0.0,
    }

