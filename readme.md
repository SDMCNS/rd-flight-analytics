# ✈️ Eurocontrol R&D Flight Analysis & Visualization Dashboard

<img width="1000" height="400" alt="Screenshot 2026-11-05 151217" src="https://github.com/user-attachments/assets/80234ae7-f203-43bf-811b-df0cb6b35888" />


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
  * **Network, City Pairs & Fleet Inferences**: Analyze high-density city pairs, airline route dominance, and estimated passenger and cargo throughput based on aircraft capacity mappings

<img width="400" height="250" alt="Screenshot 2026-11-05 151419" src="https://github.com/user-attachments/assets/0a727b3f-4c6c-4a42-878f-12c65ffa919f" />
<img width="400" height="250" alt="Screenshot 2026-11-05 151336" src="https://github.com/user-attachments/assets/6d3c38b4-f7d3-43fa-8591-9a81522d324a" />
<img width="400" height="250" alt="Screenshot 2026-11-05 151326" src="https://github.com/user-attachments/assets/eecdeb82-8958-41b4-9df1-421e6b8403fa" />
<img width="400" height="250" alt="Screenshot 2026-11-05 151251" src="https://github.com/user-attachments/assets/6d67ba54-e139-400b-86e0-6215e88ee1b6" />
<img width="400" height="250" alt="Screenshot 2026-11-05 151217" src="https://github.com/user-attachments/assets/52c6f5e7-8f97-4d22-9642-80bec069f7d6" />
<img width="400" height="250" alt="Screenshot 2026-11-05 180446" src="https://github.com/user-attachments/assets/f9e6400d-e0ee-485a-b1c4-c822fae5c2b6" />
<img width="400" height="250" alt="Screenshot 2026-11-05 180441" src="https://github.com/user-attachments/assets/bd69367e-24d5-4c0e-8f27-3c212f1bd868" />
<img width="400" height="250" alt="Screenshot 2026-11-05 180437" src="https://github.com/user-attachments/assets/c681edbb-deb2-4a22-8cac-8f750b4b920b" />



---

## 📁 Project Structure

```text
├── prepare.py            # Extracts .gz archives and standardizes input CSVs
├── etl.py                # ETL pipeline, spatial indexing, and SQLite ingestion
├── app2.py               # Streamlit interactive web dashboard
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

Download a dataset from "https://ext.eurocontrol.int/prisme_data_provision_hmi/" (registration  and access request neeeded)
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
streamlit run app2.py
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
