import pandas as pd
import sqlite3
import numpy as np
from scipy.spatial import cKDTree

print("🚀 Starting full ETL script with routes and metadata...", flush=True)

# 1. Load CSVs
print("Attempting to load actual flights CSV...", flush=True)
actual_df = pd.read_csv("flights_anonymized.csv", low_memory=False)
print(f"Loaded actual flights: {len(actual_df):,} rows", flush=True)

print("Attempting to load planned flights CSV...", flush=True)
planned_df = pd.read_csv("planned_flights_anonymized.csv", low_memory=False)
print(f"Loaded planned flights: {len(planned_df):,} rows", flush=True)

print("Attempting to load metadata flights CSV...", flush=True)
meta_df = pd.read_csv("flights.csv", low_memory=False)

print("Attempting to load airports CSV...", flush=True)
airports_df = pd.read_csv("airports.csv", low_memory=False)

print("Attempting to load FIRs CSV...", flush=True)
fir_df = pd.read_csv("fir.csv", low_memory=False)

print("Attempting to load Routes CSV...", flush=True)
routes_df = pd.read_csv("routes.csv", low_memory=False)
print(f"Loaded Route points: {len(routes_df):,} rows", flush=True)

# Clean column whitespace
for df in [actual_df, planned_df, meta_df, airports_df, fir_df, routes_df]:
    df.columns = [c.strip() for c in df.columns]

# Convert datetimes
print("Converting datetimes...", flush=True)
actual_df['Time Over'] = pd.to_datetime(actual_df['Time Over'], format='%d-%m-%Y %H:%M:%S')
planned_df['Time Over'] = pd.to_datetime(planned_df['Time Over'], format='%d-%m-%Y %H:%M:%S')

# 2. Process Airports for Spatial Matching
print("Building spatial index for airports...", flush=True)
airports_df = airports_df.dropna(subset=['latitude_deg', 'longitude_deg']).copy()
airport_tree = cKDTree(np.radians(airports_df[['latitude_deg', 'longitude_deg']].values))

def find_nearest_airports(lat_lons):
    if len(lat_lons) == 0:
        return [], []
    rads = np.radians(lat_lons)
    _, indices = airport_tree.query(rads, k=1)
    return airports_df.iloc[indices]['ident'].values, airports_df.iloc[indices]['name'].values

print("Extracting flight metrics and delays...", flush=True)

# 3. Extract Actual Flight Summaries
actual_starts = actual_df.loc[actual_df.groupby('ECTRL ID')['Sequence Number'].idxmin()].copy()
actual_ends = actual_df.loc[actual_df.groupby('ECTRL ID')['Sequence Number'].idxmax()].copy()

actual_summary = actual_df.groupby('ECTRL ID').agg(
    actual_dep_time=('Time Over', 'min'),
    actual_arr_time=('Time Over', 'max'),
    max_actual_fl=('Flight Level', 'max'),
    actual_waypoints=('Sequence Number', 'count')
).reset_index()

actual_summary['dep_lat'] = actual_starts.set_index('ECTRL ID')['Latitude'].reindex(actual_summary['ECTRL ID']).values
actual_summary['dep_lon'] = actual_starts.set_index('ECTRL ID')['Longitude'].reindex(actual_summary['ECTRL ID']).values
actual_summary['arr_lat'] = actual_ends.set_index('ECTRL ID')['Latitude'].reindex(actual_summary['ECTRL ID']).values
actual_summary['arr_lon'] = actual_ends.set_index('ECTRL ID')['Longitude'].reindex(actual_summary['ECTRL ID']).values

dep_idents, dep_names = find_nearest_airports(np.nan_to_num(actual_summary[['dep_lat', 'dep_lon']].values, nan=0.0))
arr_idents, arr_names = find_nearest_airports(np.nan_to_num(actual_summary[['arr_lat', 'arr_lon']].values, nan=0.0))

actual_summary['origin_airport'] = dep_idents
actual_summary['origin_name'] = dep_names
actual_summary['destination_airport'] = arr_idents
actual_summary['destination_name'] = arr_names

# 4. Extract Planned Flight Summaries & Merge Metadata
planned_summary = planned_df.groupby('ECTRL ID').agg(
    planned_dep_time=('Time Over', 'min'),
    planned_arr_time=('Time Over', 'max'),
    max_planned_fl=('Flight Level', 'max'),
    planned_waypoints=('Sequence Number', 'count')
).reset_index()

flight_summary = pd.merge(actual_summary, planned_summary, on='ECTRL ID', how='left')
flight_summary = pd.merge(flight_summary, meta_df, on='ECTRL ID', how='left')

flight_summary['dep_delay_mins'] = (
    (flight_summary['actual_dep_time'] - pd.to_datetime(flight_summary['FILED OFF BLOCK TIME'], format='mixed', dayfirst=True)).dt.total_seconds() / 60
).round(1).fillna(0)

flight_summary['arr_delay_mins'] = (
    (flight_summary['actual_arr_time'] - pd.to_datetime(flight_summary['FILED ARRIVAL TIME'], format='mixed', dayfirst=True)).dt.total_seconds() / 60
).round(1).fillna(0)

flight_summary['deviation_pct'] = (
    (flight_summary['actual_waypoints'] - flight_summary['planned_waypoints']).abs() 
    / flight_summary['planned_waypoints'].clip(lower=1) * 100
).round(1)

flight_summary = flight_summary.sort_values('actual_dep_time').reset_index(drop=True)

# 5. Save to SQLite
print("Saving processed data into SQLite database (flights.db)...", flush=True)
conn = sqlite3.connect("flights.db")

actual_df.to_sql("actual_flights", conn, if_exists="replace", index=False)
planned_df.to_sql("planned_flights", conn, if_exists="replace", index=False)
flight_summary.to_sql("flight_summary", conn, if_exists="replace", index=False)
fir_df.to_sql("firs_raw", conn, if_exists="replace", index=False)
routes_df.to_sql("routes_raw", conn, if_exists="replace", index=False)
airports_df.to_sql("airports_db", conn, if_exists="replace", index=False)

print("Creating database indices...", flush=True)
conn.execute("CREATE INDEX IF NOT EXISTS idx_actual_id ON actual_flights('ECTRL ID');")
conn.execute("CREATE INDEX IF NOT EXISTS idx_summary_id ON flight_summary('ECTRL ID');")
conn.execute("CREATE INDEX IF NOT EXISTS idx_reg ON flight_summary('AC Registration');")

conn.close()
print("✅ Full ETL Pipeline complete with Routes! 'flights.db' is ready.")