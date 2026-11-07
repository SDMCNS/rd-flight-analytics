"""Folium maps and Plotly figures. Requires ``pip install ectl-flights[viz]``."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd

try:
    import folium
    import plotly.graph_objects as go
except ImportError as e:  # pragma: no cover
    raise ImportError("ectl_flights.viz requires extras: pip install 'ectl-flights[viz]'") from e

from . import geo


def flight_map(
    actual: pd.DataFrame,
    planned: Optional[pd.DataFrame] = None,
    firs: Optional[Dict[str, dict]] = None,
    ideal: Optional[Tuple[Tuple[float, float], Tuple[float, float]]] = None,
    zoom_start: int = 4,
) -> "folium.Map":
    """Actual (blue) and planned (orange) paths, crossed FIRs and optional great-circle line."""
    m = folium.Map(location=[actual["Latitude"].mean(), actual["Longitude"].mean()], zoom_start=zoom_start)
    if firs:
        for fir_id in geo.firs_passed(actual, firs):
            folium.Polygon(firs[fir_id]["latlon"], color="green", weight=2, fill=True,
                           fill_color="lightgreen", fill_opacity=0.2, tooltip=f"Passed FIR: {fir_id}").add_to(m)
    if ideal:
        folium.PolyLine(list(ideal), color="gray", weight=2, dash_array="3, 3",
                        tooltip="Ideal Direct Path (Great Circle)").add_to(m)
    if planned is not None and not planned.empty:
        folium.PolyLine(list(zip(planned["Latitude"], planned["Longitude"])), color="darkorange",
                        weight=3, dash_array="6, 6", tooltip="Planned Path").add_to(m)
    pts = list(zip(actual["Latitude"], actual["Longitude"]))
    folium.PolyLine(pts, color="royalblue", weight=4, tooltip="Actual Path").add_to(m)
    folium.Marker(pts[0], icon=folium.Icon(color="green", icon="plane-departure", prefix="fa")).add_to(m)
    folium.Marker(pts[-1], icon=folium.Icon(color="red", icon="plane-arrival", prefix="fa")).add_to(m)
    return m


def multi_flight_map(paths: Iterable[Tuple[str, pd.DataFrame]], color: str = "purple",
                     location=(35.0, -40.0), zoom_start: int = 3) -> "folium.Map":
    """Overlay several flight paths; ``paths`` yields ``(tooltip, points_df)``."""
    m = folium.Map(location=list(location), zoom_start=zoom_start)
    for tip, df in paths:
        if not df.empty:
            folium.PolyLine(list(zip(df["Latitude"], df["Longitude"])), color=color,
                            weight=3, opacity=0.8, tooltip=tip).add_to(m)
    return m


def fir_map(fir_id: str, fir: dict, airports: Optional[pd.DataFrame] = None,
            routes: Optional[Dict[str, dict]] = None, route_ids: Optional[List[str]] = None) -> "folium.Map":
    """FIR polygon with optional airport markers and/or route lines."""
    ll = fir["latlon"]
    m = folium.Map(location=[sum(p[0] for p in ll) / len(ll), sum(p[1] for p in ll) / len(ll)], zoom_start=5)
    folium.Polygon(ll, color="red", weight=3, fill=True, fill_color="pink",
                   fill_opacity=0.15, tooltip=f"FIR: {fir_id}").add_to(m)
    if airports is not None:
        for _, a in airports.iterrows():
            folium.Marker([a["latitude_deg"], a["longitude_deg"]], popup=f"Airport: {a['ident']} ({a['name']})",
                          icon=folium.Icon(color="blue", icon="plane", prefix="fa")).add_to(m)
    if routes and route_ids:
        for rid in route_ids:
            folium.PolyLine(routes[rid]["latlon"], color="purple", weight=3, opacity=0.8,
                            tooltip=f"Route ID: {rid}").add_to(m)
    return m


def vertical_profile(actual: pd.DataFrame, planned: Optional[pd.DataFrame] = None,
                     firs: Optional[Dict[str, dict]] = None, height: int = 450) -> "go.Figure":
    """Flight level vs time, with dotted lines at FIR entry times."""
    fig = go.Figure()
    if planned is not None and not planned.empty:
        fig.add_trace(go.Scatter(x=planned["Time Over"], y=planned["Flight Level"], name="Planned FL",
                                 line=dict(color="darkorange", dash="dash", width=3)))
    fig.add_trace(go.Scatter(x=actual["Time Over"], y=actual["Flight Level"], name="Actual FL",
                             line=dict(color="royalblue", width=4)))
    if firs:
        for fir_id, t in geo.fir_crossings(actual, firs):
            fig.add_vline(x=pd.Timestamp(t), line_width=2, line_dash="dot", line_color="green",
                          annotation_text=f"FIR: {fir_id}", annotation_position="top left")
    fig.update_layout(xaxis_title="Time (UTC)", yaxis_title="Flight Level (FL)",
                      margin=dict(l=20, r=20, t=30, b=20), height=height,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig


def bar(x, y, horizontal: bool = False, color: str = "royalblue", xaxis_title: str = "",
        yaxis_title: str = "", height: int = 400) -> "go.Figure":
    fig = go.Figure(go.Bar(x=y if horizontal else x, y=x if horizontal else y,
                           orientation="h" if horizontal else "v", marker_color=color))
    fig.update_layout(xaxis_title=xaxis_title, yaxis_title=yaxis_title, height=height,
                      margin=dict(l=20, r=20, t=20, b=20))
    if horizontal:
        fig.update_yaxes(autorange="reversed")
    return fig

