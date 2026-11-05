import glob
import gzip
import shutil
import os

print("🔍 Searching and extracting dataset files...", flush=True)

# 1. Automatically extract any .gz files in the directory
for gz_file in glob.glob("*.gz"):
    output_file = gz_file[:-3]  # Remove .gz extension
    if not os.path.exists(output_file):
        print(f"📦 Extracting {gz_file} ➔ {output_file}...", flush=True)
        with gzip.open(gz_file, 'rb') as f_in:
            with open(output_file, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)

# 2. Map standard target filenames to exact search patterns
mappings = {
    "flights_anonymized.csv": "Flight_Points_Actual_*.csv",
    "planned_flights_anonymized.csv": "Flight_Points_Filed_*.csv",
    "routes.csv": "Route_*.csv",
    "airports.csv": "airports*.csv",
    "fir.csv": "fir*.csv"
}

for target, pattern in mappings.items():
    matches = glob.glob(pattern)
    if matches:
        source_file = matches[0]
        if source_file != target:
            shutil.copy(source_file, target)
        print(f"✅ Standardized: {source_file} ➔ {target}", flush=True)
    else:
        print(f"⚠️ Warning: No file matching pattern '{pattern}' found for target '{target}'.", flush=True)

# 3. Metadata flights CSV (Flights_YYYYMMDD_YYYYMMDD.csv - excluding points files)
meta_matches = [f for f in glob.glob("Flights_*.csv") if "Points" not in f and f != "flights.csv"]
if meta_matches:
    shutil.copy(meta_matches[0], "flights.csv")
    print(f"✅ Standardized metadata: {meta_matches[0]} ➔ flights.csv", flush=True)
else:
    print("⚠️ Warning: No metadata flights file matching 'Flights_*.csv' found.", flush=True)

print("🚀 Preparation complete! You can now run `python etl.py`.", flush=True)