# ✈️ Eurocontrol R&D Flight Analysis & Visualization Dashboard

An end-to-end Python and Streamlit pipeline designed to parse, spatially index, and visualize periodic flight data provided for researchers by **Eurocontrol ARCHIVE Data for R&D** (https://ext.eurocontrol.int/prisme_data_provision_hmi/).

This project provides multi-view analytics, single flight deep-dives, fleet registration tracking, spatial FIR boundary checks, and route analytics using an optimized SQLite backend.

---

## 🌟 Key Features

* **Automated Data Preparation (`prepare.py`)**: Automatically detects, extracts `.gz` archives, and standardizes variable Eurocontrol dataset file names.
* **Spatial & Relational ETL (`etl.py`)**: Ingests actual/planned trajectory points, metadata, airports, FIR polygons, and routes into an optimized SQLite database (`flights.db`) using `scipy.spatial.cKDTree` and `Shapely`.
* **Multi-View Streamlit Dashboard (`app_sqlite.py`)**:
  * **Single Flight Analysis**: Interactive map comparing actual vs. planned routes, time-based vertical altitude profiles with dotted FIR boundary crossing markers, delay metrics, and full metadata inspection.
  * **Aircraft Registration Tracker**: Track individual aircraft tail numbers across your dataset timeframe, view flight frequency, and map cumulative fleet movements.
  * **FIR & Route Analytics**: Explore Flight Information Regions, toggle map layers between enclosed airports and intersecting routes, and analyze traffic volume breakdowns (weekday and hourly distributions).

---

## 📁 Project Structure

```text
├── prepare.py            # Extracts .gz archives and standardizes input CSVs
├── etl.py                # ETL pipeline, spatial indexing, and SQLite ingestion
├── app_sqlite.py         # Streamlit interactive web dashboard
├── requirements.txt      # Python dependencies
└── README.md             # Project documentation
```

---

## 🛠️ Prerequisites & Installation

Ensure you have Python 3.8+ installed, then install the required dependencies:

```bash
pip install streamlit pandas numpy scipy shapely folium streamlit-folium plotly
```

---

## 🚀 Usage Guide

Place your raw Eurocontrol data files (`.gz` archives or extracted CSVs) into the root project directory, then follow these three steps:

### Step 1: Prepare and Standardize Data
Run the preparation script to automatically extract compressed files and standardize filenames for the ETL pipeline:
```bash
python prepare.py
```

### Step 2: Run the ETL Pipeline
Process the standardized CSV files, build spatial indexes, compute flight summaries, and generate `flights.db`:
```bash
python etl.py
```

### Step 3: Launch the Streamlit Dashboard
Start the interactive web application:
```bash
streamlit run app_sqlite.py
```

---

## 📊 Data Sources & Attribution

* **Actual Flight Points**: `Flight_Points_Actual_*.csv` (or `.gz`) — Provided by Eurocontrol ARCHIVE Data for R&D.
* **Planned Flight Points**: `Flight_Points_Filed_*.csv` (or `.gz`) — Provided by Eurocontrol ARCHIVE Data for R&D.
* **Flight Metadata**: `Flights_YYYYMMDD_YYYYMMDD.csv` — Provided by Eurocontrol ARCHIVE Data for R&D.
* **Routes**: `Route_*.csv` — Provided by Eurocontrol ARCHIVE Data for R&D.
* **Airports**: `airports.csv` — Airport database sourced with thanks from [OpenFlights](https://openflights.org/).
* **FIR Boundaries**: `fir.csv` — Provided by Eurocontrol ARCHIVE Data for R&D.

---

## 📄 License
Research and educational use referencing Eurocontrol ARCHIVE data guidelines.