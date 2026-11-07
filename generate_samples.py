"""Generate sample PNG screenshots for each visualization element in ectl_flights.viz."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

from ectl_flights import FlightDB, analytics, geo, viz

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
OUTPUT_DIR = Path("samples").resolve()
TEMP_DIR = OUTPUT_DIR / "temp_html"


def html_to_png(html_file: Path, png_file: Path, width: int = 1280, height: int = 720, delay_ms: int = 4000):
    """Use Chrome headless to render an HTML file and capture a PNG screenshot."""
    cmd = [
        CHROME_PATH,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        f"--window-size={width},{height}",
        f"--virtual-time-budget={delay_ms}",
        f"--screenshot={png_file}",
        f"file:///{html_file.as_posix()}",
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    print("Connecting to flights.db...", flush=True)
    db_path = "flights.db" if Path("flights.db").exists() else "data/flights.db"
    db = FlightDB(db_path)
    summary = db.summary()

    # 1. Single Flight Trajectory Map (Actual, Planned, Ideal, Passed FIRs)
    print("\n1. Generating sample_flight_trajectory_map.png...", flush=True)
    sample_fid = 202007029  # KORD -> LFPG transatlantic flight
    actual = db.actual_points(sample_fid)
    planned = db.planned_points(sample_fid)
    flight_row = db.flight(sample_fid)
    orig_coords = db.airport_coords(flight_row["origin_airport"])
    dest_coords = db.airport_coords(flight_row["destination_airport"])
    ideal = (orig_coords, dest_coords) if orig_coords and dest_coords else None

    m_flight = viz.flight_map(actual, planned, db.firs, ideal=ideal, zoom_start=4)
    html_flight_map = TEMP_DIR / "flight_map.html"
    png_flight_map = OUTPUT_DIR / "sample_flight_trajectory_map.png"
    m_flight.save(str(html_flight_map))
    html_to_png(html_flight_map, png_flight_map, width=1280, height=720, delay_ms=5000)
    print(f"   Created {png_flight_map.name} ({png_flight_map.stat().st_size:,} bytes)")

    # 2. Single Flight Vertical Altitude Profile with FIR Crossings
    print("\n2. Generating sample_flight_vertical_profile.png...", flush=True)
    fig_vert = viz.vertical_profile(actual, planned, db.firs, height=500)
    html_vert = TEMP_DIR / "vertical_profile.html"
    png_vert = OUTPUT_DIR / "sample_flight_vertical_profile.png"
    fig_vert.write_html(str(html_vert))
    html_to_png(html_vert, png_vert, width=1280, height=600, delay_ms=3000)
    print(f"   Created {png_vert.name} ({png_vert.stat().st_size:,} bytes)")

    # 3. Aircraft Registration Tracker / Multi-Flight Movement Map
    print("\n3. Generating sample_fleet_movement_map.png...", flush=True)
    sample_reg = None
    for reg, grp in summary.groupby("AC Registration"):
        if 5 <= len(grp) <= 8:
            pts = [db.actual_points(fid) for fid in grp["ECTRL ID"]]
            if all(len(p) > 10 for p in pts):
                sample_reg = reg
                break

    if not sample_reg:
        sample_reg = summary["AC Registration"].dropna().iloc[0]

    reg_flights = db.flights_for_registration(sample_reg)
    paths = [
        (
            f"Flight {f['ECTRL ID']}: {f['origin_airport']} -> {f['destination_airport']}",
            db.actual_points(f["ECTRL ID"]),
        )
        for _, f in reg_flights.iterrows()
    ]
    mean_lat = float(sum(p[1]["Latitude"].mean() for p in paths) / len(paths))
    mean_lon = float(sum(p[1]["Longitude"].mean() for p in paths) / len(paths))

    m_reg = viz.multi_flight_map(paths, color="purple", location=(mean_lat, mean_lon), zoom_start=4)
    html_reg = TEMP_DIR / "fleet_movement.html"
    png_reg = OUTPUT_DIR / "sample_fleet_movement_map.png"
    m_reg.save(str(html_reg))
    html_to_png(html_reg, png_reg, width=1280, height=720, delay_ms=5000)
    print(f"   Created {png_reg.name} ({png_reg.stat().st_size:,} bytes) for registration {sample_reg}")

    # 4. FIR Spatial Map: Enclosed Airports
    print("\n4. Generating sample_fir_airports_map.png...", flush=True)
    fir_id = "LWSSFIR"
    fir_data = db.firs[fir_id]
    contained_airports = geo.airports_in_fir(fir_data["shape"], db.airports)
    m_fir_apts = viz.fir_map(fir_id, fir_data, airports=contained_airports)
    html_fir_apts = TEMP_DIR / "fir_airports.html"
    png_fir_apts = OUTPUT_DIR / "sample_fir_airports_map.png"
    m_fir_apts.save(str(html_fir_apts))
    html_to_png(html_fir_apts, png_fir_apts, width=1280, height=720, delay_ms=5000)
    print(f"   Created {png_fir_apts.name} ({png_fir_apts.stat().st_size:,} bytes)")

    # 5. FIR Spatial Map: Associated / Intersecting Routes
    print("\n5. Generating sample_fir_routes_map.png...", flush=True)
    intersecting_routes = geo.routes_in_fir(fir_data["shape"], db.routes)
    m_fir_routes = viz.fir_map(fir_id, fir_data, routes=db.routes, route_ids=intersecting_routes)
    html_fir_routes = TEMP_DIR / "fir_routes.html"
    png_fir_routes = OUTPUT_DIR / "sample_fir_routes_map.png"
    m_fir_routes.save(str(html_fir_routes))
    html_to_png(html_fir_routes, png_fir_routes, width=1280, height=720, delay_ms=5000)
    print(f"   Created {png_fir_routes.name} ({png_fir_routes.stat().st_size:,} bytes)")

    # 6. Plotly Bar Chart: Top City Pairs
    print("\n6. Generating sample_top_city_pairs_bar.png...", flush=True)
    df_inf = analytics.add_capacity_estimates(summary)
    top_pairs = analytics.top_city_pairs(df_inf, n=10)
    fig_pairs = viz.bar(
        top_pairs["City_Pair"],
        top_pairs["Flight_Count"],
        horizontal=True,
        color="royalblue",
        xaxis_title="Number of Flights",
        height=450,
    )
    html_pairs = TEMP_DIR / "top_pairs.html"
    png_pairs = OUTPUT_DIR / "sample_top_city_pairs_bar.png"
    fig_pairs.write_html(str(html_pairs))
    html_to_png(html_pairs, png_pairs, width=1000, height=500, delay_ms=3000)
    print(f"   Created {png_pairs.name} ({png_pairs.stat().st_size:,} bytes)")

    # 7. Plotly Bar Chart: Hourly Departure Traffic Distribution
    print("\n7. Generating sample_hourly_traffic_bar.png...", flush=True)
    hr_counts = analytics.traffic_by_hour(summary)
    fig_hr = viz.bar(
        hr_counts["Dep_Hour"],
        hr_counts["Flights"],
        horizontal=False,
        color="indianred",
        xaxis_title="Hour of Day (UTC)",
        yaxis_title="Flight Count",
        height=400,
    )
    html_hr = TEMP_DIR / "hourly_traffic.html"
    png_hr = OUTPUT_DIR / "sample_hourly_traffic_bar.png"
    fig_hr.write_html(str(html_hr))
    html_to_png(html_hr, png_hr, width=1000, height=500, delay_ms=3000)
    print(f"   Created {png_hr.name} ({png_hr.stat().st_size:,} bytes)")

    # Clean up temporary HTML directory
    shutil.rmtree(TEMP_DIR, ignore_errors=True)

    print(f"\n All sample PNG files generated successfully in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

