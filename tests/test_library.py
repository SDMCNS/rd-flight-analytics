"""Unit and integration tests for ectl_flights."""

import sqlite3
import pandas as pd
import pytest
from shapely.geometry import Polygon

from ectl_flights import FlightDB, analytics, geo, prepare, viz
from ectl_flights.etl import NearestAirport, build_flight_summary


def test_nearest_airport():
    airports = pd.DataFrame([
        {"ident": "EGLL", "name": "London Heathrow", "latitude_deg": 51.4700, "longitude_deg": -0.4543},
        {"ident": "LFPG", "name": "Paris Charles de Gaulle", "latitude_deg": 49.0097, "longitude_deg": 2.5479},
    ])
    finder = NearestAirport(airports)
    # Query point close to Heathrow
    idents, names = finder.query([[51.48, -0.45]])
    assert idents[0] == "EGLL"
    assert names[0] == "London Heathrow"

    # Query point close to CDG
    idents, names = finder.query([[49.01, 2.55]])
    assert idents[0] == "LFPG"


def test_build_flight_summary():
    actual = pd.DataFrame([
        {"ECTRL ID": 1001, "Sequence Number": 1, "Time Over": pd.Timestamp("2026-11-01 10:00:00"), "Latitude": 51.47, "Longitude": -0.45, "Flight Level": 10},
        {"ECTRL ID": 1001, "Sequence Number": 2, "Time Over": pd.Timestamp("2026-11-01 11:00:00"), "Latitude": 49.01, "Longitude": 2.55, "Flight Level": 250},
    ])
    planned = pd.DataFrame([
        {"ECTRL ID": 1001, "Sequence Number": 1, "Time Over": pd.Timestamp("2026-11-01 09:55:00"), "Latitude": 51.47, "Longitude": -0.45, "Flight Level": 10},
        {"ECTRL ID": 1001, "Sequence Number": 2, "Time Over": pd.Timestamp("2026-11-01 10:55:00"), "Latitude": 49.01, "Longitude": 2.55, "Flight Level": 260},
    ])
    meta = pd.DataFrame([
        {"ECTRL ID": 1001, "AC Operator": "BAW", "AC Type": "A320", "AC Registration": "G-EUUI",
         "FILED OFF BLOCK TIME": "01-11-2026 09:50:00", "FILED ARRIVAL TIME": "01-11-2026 10:55:00",
         "STATFOR Market Segment": "Traditional Scheduled"}
    ])
    airports = pd.DataFrame([
        {"ident": "EGLL", "name": "London Heathrow", "latitude_deg": 51.47, "longitude_deg": -0.45},
        {"ident": "LFPG", "name": "Paris CDG", "latitude_deg": 49.01, "longitude_deg": 2.55},
    ])

    summary = build_flight_summary(actual, planned, meta, airports)
    assert len(summary) == 1
    row = summary.iloc[0]
    assert row["origin_airport"] == "EGLL"
    assert row["destination_airport"] == "LFPG"
    assert row["max_actual_fl"] == 250
    assert row["dep_delay_mins"] == 10.0
    assert row["arr_delay_mins"] == 5.0


def test_geo_fir_and_efficiency():
    # Square FIR: lon 0 to 5, lat 45 to 55
    fir_poly = Polygon([(0, 45), (5, 45), (5, 55), (0, 55)])
    firs = {"TESTFIR": {"latlon": [(45, 0), (45, 5), (55, 5), (55, 0)], "shape": fir_poly}}

    points = pd.DataFrame([
        {"Sequence Number": 1, "Latitude": 48.0, "Longitude": 2.0, "Time Over": pd.Timestamp("2026-11-01 10:00:00")},
        {"Sequence Number": 2, "Latitude": 52.0, "Longitude": 3.0, "Time Over": pd.Timestamp("2026-11-01 11:00:00")},
    ])
    crossings = geo.fir_crossings(points, firs)
    assert len(crossings) == 1
    assert crossings[0][0] == "TESTFIR"
    assert crossings[0][1] == pd.Timestamp("2026-11-01 10:00:00")

    # Path distance & efficiency
    dist = geo.path_distance_nm(points)
    assert dist > 0

    eff = geo.flight_efficiency(points, points, (48.0, 2.0), (52.0, 3.0))
    assert 99.0 <= eff["actual_efficiency_pct"] <= 101.0


def test_analytics_functions():
    summary = pd.DataFrame([
        {"ECTRL ID": 1, "origin_airport": "EGLL", "destination_airport": "LFPG", "AC Operator": "BAW", "AC Type": "A320",
         "actual_dep_time": pd.Timestamp("2026-11-01 10:00:00"), "dep_delay_mins": 5.0, "max_actual_fl": 320,
         "STATFOR Market Segment": "Traditional Scheduled", "Actual Distance Flown (nm)": 200},
        {"ECTRL ID": 2, "origin_airport": "EGLL", "destination_airport": "LFPG", "AC Operator": "AFR", "AC Type": "A321",
         "actual_dep_time": pd.Timestamp("2026-11-01 14:00:00"), "dep_delay_mins": 15.0, "max_actual_fl": 340,
         "STATFOR Market Segment": "Traditional Scheduled", "Actual Distance Flown (nm)": 210},
    ])

    enriched = analytics.add_capacity_estimates(summary)
    assert "Est_Passengers" in enriched.columns
    assert "City_Pair" in enriched.columns
    assert enriched.iloc[0]["Est_Passengers"] == 180  # A320

    top_pairs = analytics.top_city_pairs(enriched)
    assert len(top_pairs) == 1
    assert top_pairs.iloc[0]["Flight_Count"] == 2

    throughput = analytics.operator_throughput(enriched)
    assert len(throughput) == 2

    hr = analytics.traffic_by_hour(summary)
    assert set(hr["Dep_Hour"]) == {10, 14}


def test_viz_components():
    actual = pd.DataFrame([
        {"Latitude": 51.5, "Longitude": -0.1, "Flight Level": 100, "Time Over": pd.Timestamp("2026-11-01 10:00:00")},
        {"Latitude": 48.8, "Longitude": 2.3, "Flight Level": 250, "Time Over": pd.Timestamp("2026-11-01 11:00:00")},
    ])
    planned = actual.copy()
    fir_poly = Polygon([(-2, 45), (5, 45), (5, 55), (-2, 55)])
    firs = {"SAMPLE": {"latlon": [(45, -2), (45, 5), (55, 5), (55, -2)], "shape": fir_poly}}

    # Test Folium Map
    m = viz.flight_map(actual, planned, firs)
    assert m is not None

    # Test Vertical Profile
    fig = viz.vertical_profile(actual, planned, firs)
    assert fig is not None

    # Test Bar
    fig_bar = viz.bar(["A", "B"], [10, 20])
    assert fig_bar is not None


def test_flight_db_live(tmp_path):
    # Test FlightDB on a minimal temporary sqlite db
    db_file = tmp_path / "test.db"
    conn = sqlite3.connect(db_file)
    conn.execute("CREATE TABLE flight_summary ('ECTRL ID' INT, actual_dep_time TEXT, 'AC Registration' TEXT, origin_airport TEXT, destination_airport TEXT);")
    conn.execute("INSERT INTO flight_summary VALUES (1, '2026-11-01 10:00:00', 'G-TEST', 'EGLL', 'LFPG');")
    conn.execute("CREATE TABLE actual_flights ('ECTRL ID' INT, 'Sequence Number' INT, Latitude REAL, Longitude REAL);")
    conn.execute("INSERT INTO actual_flights VALUES (1, 1, 51.5, -0.1);")
    conn.execute("CREATE TABLE planned_flights ('ECTRL ID' INT, 'Sequence Number' INT, Latitude REAL, Longitude REAL);")
    conn.execute("CREATE TABLE firs_raw ('Airspace ID' TEXT, 'Sequence Number' INT, Latitude REAL, Longitude REAL);")
    conn.execute("CREATE TABLE routes_raw ('Route ID' TEXT, 'Sequence Number' INT, Latitude REAL, Longitude REAL);")
    conn.execute("CREATE TABLE airports_db (ident TEXT, name TEXT, latitude_deg REAL, longitude_deg REAL);")
    conn.commit()
    conn.close()

    with FlightDB(db_file) as db:
        summary = db.summary()
        assert len(summary) == 1
        assert summary.iloc[0]["AC Registration"] == "G-TEST"
        assert len(db.actual_points(1)) == 1
        assert len(db.flights_for_registration("G-TEST")) == 1

