import streamlit as st
import sqlite3
import pandas as pd
import folium
from streamlit_folium import st_folium
import plotly.graph_objects as go
from shapely.geometry import Point, Polygon, LineString

st.set_page_config(page_title="Advanced Flight & Fleet Explorer", layout="wide")

st.title("✈️ Flight vs. Plan & Fleet Explorer")

@st.cache_resource
def get_connection():
    return sqlite3.connect("flights.db", check_same_thread=False)

conn = get_connection()

@st.cache_data
def load_summary():
    return pd.read_sql('SELECT * FROM flight_summary ORDER BY actual_dep_time', conn)

@st.cache_data
def load_firs():
    firs_raw = pd.read_sql('SELECT "Airspace ID", Latitude, Longitude FROM firs_raw ORDER BY "Airspace ID", "Sequence Number"', conn)
    fir_polygons = {}
    for airspace_id, group in firs_raw.groupby('Airspace ID'):
        coords = list(zip(group['Latitude'], group['Longitude']))
        if len(coords) >= 3:
            poly_coords = [(lon, lat) for lat, lon in coords]
            try:
                poly = Polygon(poly_coords)
                if poly.is_valid:
                    fir_polygons[airspace_id] = {'latlon': coords, 'shape': poly}
            except Exception:
                pass
    return fir_polygons

@st.cache_data
def load_routes():
    routes_raw = pd.read_sql('SELECT "Route ID", Latitude, Longitude FROM routes_raw ORDER BY "Route ID", "Sequence Number"', conn)
    route_lines = {}
    for route_id, group in routes_raw.groupby('Route ID'):
        coords = list(zip(group['Longitude'], group['Latitude']))
        if len(coords) >= 2:
            try:
                line = LineString(coords)
                route_lines[route_id] = {'latlon': [(lat, lon) for lon, lat in coords], 'shape': line}
            except Exception:
                pass
    return route_lines

@st.cache_data
def load_airports_master():
    return pd.read_sql('SELECT ident, name, latitude_deg, longitude_deg FROM airports_db WHERE latitude_deg IS NOT NULL AND longitude_deg IS NOT NULL', conn)

try:
    summary_df = load_summary()
    fir_dict = load_firs()
    route_dict = load_routes()
    airports_df = load_airports_master()
except Exception as e:
    st.error(f"Error loading database tables. Did you run `etl.py`? Details: {e}")
    st.stop()

summary_df['actual_dep_time'] = pd.to_datetime(summary_df['actual_dep_time'])
min_date = summary_df['actual_dep_time'].min().date()
max_date = summary_df['actual_dep_time'].max().date()

# --- SESSION STATE & MODE SELECTOR ---
if "app_mode" not in st.session_state:
    st.session_state.app_mode = "Single Flight Analysis"
if "target_reg" not in st.session_state:
    st.session_state.target_reg = None

app_mode = st.sidebar.radio(
    "Select Dashboard Mode", 
    ["Single Flight Analysis", "Aircraft Registration Tracker", "FIR & Route Analytics"],
    index=0 if st.session_state.app_mode == "Single Flight Analysis" else (1 if st.session_state.app_mode == "Aircraft Registration Tracker" else 2)
)
st.session_state.app_mode = app_mode

if app_mode == "Single Flight Analysis":
    st.markdown("### 🔍 Single Flight Analysis & Route Profiling")
    
    all_origins = sorted([str(x) for x in summary_df['origin_airport'].dropna().unique() if x])
    all_destinations = sorted([str(x) for x in summary_df['destination_airport'].dropna().unique() if x])

    st.sidebar.header("Filters")
    date_range = st.sidebar.date_input("Start Date Range", value=[min_date, max_date], min_value=min_date, max_value=max_date)
    selected_origins = st.sidebar.multiselect("Departure Airport(s)", options=all_origins, default=[])
    selected_destinations = st.sidebar.multiselect("Arrival Airport(s)", options=all_destinations, default=[])

    min_fl, max_fl = int(summary_df['max_actual_fl'].min()), int(summary_df['max_actual_fl'].max())
    fl_range = st.sidebar.slider("Max Flight Level Range", min_value=min_fl, max_value=max_fl, value=(min_fl, max_fl))
    
    filtered_summary = summary_df.copy()
    if len(date_range) == 2:
        filtered_summary = filtered_summary[(filtered_summary['actual_dep_time'].dt.date >= date_range[0]) & (filtered_summary['actual_dep_time'].dt.date <= date_range[1])]
    if selected_origins:
        filtered_summary = filtered_summary[filtered_summary['origin_airport'].isin(selected_origins)]
    if selected_destinations:
        filtered_summary = filtered_summary[filtered_summary['destination_airport'].isin(selected_destinations)]
    
    filtered_summary = filtered_summary[(filtered_summary['max_actual_fl'] >= fl_range[0]) & (filtered_summary['max_actual_fl'] <= fl_range[1])]
    filtered_flight_ids = filtered_summary['ECTRL ID'].tolist()

    st.sidebar.markdown(f"**Matching Flights:** {len(filtered_flight_ids):,}")

    if not filtered_flight_ids:
        st.warning("No flights match your filter criteria.")
    else:
        selected_flight_id = st.selectbox("Select Flight (ECTRL ID)", options=filtered_flight_ids)
        
        if selected_flight_id:
            actual_data = pd.read_sql(f'SELECT * FROM actual_flights WHERE "ECTRL ID" = {selected_flight_id} ORDER BY "Sequence Number"', conn)
            planned_data = pd.read_sql(f'SELECT * FROM planned_flights WHERE "ECTRL ID" = {selected_flight_id} ORDER BY "Sequence Number"', conn)
            row_stat = filtered_summary.loc[filtered_summary['ECTRL ID'] == selected_flight_id].iloc[0]

            reg_val = str(row_stat.get('AC Registration', 'N/A'))

            with st.expander("📋 Filed Flight Plan & Aircraft Metadata", expanded=True):
                col_meta, col_link = st.columns([4, 1])
                with col_meta:
                    m1, m2, m3, m4, m5 = st.columns(5)
                    m1.metric("Operator", str(row_stat.get('AC Operator', 'N/A')))
                    m2.metric("Aircraft Type", str(row_stat.get('AC Type', 'N/A')))
                    m3.metric("Registration", reg_val)
                    m4.metric("Requested FL", f"FL {row_stat.get('Requested FL', 0)}")
                    m5.metric("Market Segment", str(row_stat.get('STATFOR Market Segment', 'N/A')))
                with col_link:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button(f"🎯 Track Reg {reg_val}"):
                        st.session_state.app_mode = "Aircraft Registration Tracker"
                        st.session_state.target_reg = reg_val
                        st.rerun()

            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Route", f"{row_stat['origin_airport']} ➔ {row_stat['destination_airport']}")
            c2.metric("Dep Delay", f"{row_stat['dep_delay_mins']} mins")
            c3.metric("Arr Delay", f"{row_stat['arr_delay_mins']} mins")
            c4.metric("Max FL Reached", f"FL {row_stat['max_actual_fl']}")
            c5.metric("Distance Flown", f"{row_stat.get('Actual Distance Flown (nm)', 0)} nm")

            st.markdown("---")

            st.subheader("🗺️ Flight Path & FIR Boundaries (Full Width)")
            mean_lat, mean_lon = actual_data['Latitude'].mean(), actual_data['Longitude'].mean()
            m = folium.Map(location=[mean_lat, mean_lon], zoom_start=4)

            passed_firs = set()
            flight_pts = [Point(lon, lat) for lat, lon in zip(actual_data['Latitude'], actual_data['Longitude'])]
            for fir_id, data in fir_dict.items():
                if any(data['shape'].contains(pt) for pt in flight_pts):
                    passed_firs.add(fir_id)
                    folium.Polygon(locations=data['latlon'], color="green", weight=2, fill=True, fill_color="lightgreen", fill_opacity=0.2, tooltip=f"Passed FIR: {fir_id}").add_to(m)

            if not planned_data.empty:
                folium.PolyLine(list(zip(planned_data['Latitude'], planned_data['Longitude'])), color="darkorange", weight=3, dash_array="6, 6", tooltip="Planned Path").add_to(m)

            actual_pts = list(zip(actual_data['Latitude'], actual_data['Longitude']))
            folium.PolyLine(actual_pts, color="royalblue", weight=4, tooltip="Actual Path").add_to(m)
            folium.Marker(actual_pts[0], icon=folium.Icon(color="green", icon="plane-departure", prefix="fa")).add_to(m)
            folium.Marker(actual_pts[-1], icon=folium.Icon(color="red", icon="plane-arrival", prefix="fa")).add_to(m)

            st_folium(m, width=1200, height=500)

            st.markdown("---")

# --- FULL WIDTH VERTICAL PROFILE SECTION ---
            # --- FULL WIDTH VERTICAL PROFILE SECTION WITH FIR CROSSINGS ---
            st.subheader("📈 Vertical Altitude Profile Over Time with FIR Crossings (Full Width)")
            
            # Compute FIR entry timestamps for the selected flight
            fir_crossings = []
            flight_pts_with_time = list(zip(actual_data['Latitude'], actual_data['Longitude'], actual_data['Time Over']))

            for fir_id, data in fir_dict.items():
                poly = data['shape']
                entering_times = [t for lat, lon, t in flight_pts_with_time if poly.contains(Point(lon, lat))]
                if entering_times:
                    entry_time = min(entering_times)
                    fir_crossings.append((fir_id, entry_time))

            fig = go.Figure()
            
            if not planned_data.empty:
                fig.add_trace(go.Scatter(
                    x=planned_data['Time Over'], 
                    y=planned_data['Flight Level'], 
                    name='Planned FL', 
                    line=dict(color='darkorange', dash='dash', width=3)
                ))
            
            fig.add_trace(go.Scatter(
                x=actual_data['Time Over'], 
                y=actual_data['Flight Level'], 
                name='Actual FL', 
                line=dict(color='royalblue', width=4)
            ))

            # Add vertical dotted lines for each FIR entry boundary crossing
            for fir_id, entry_time in fir_crossings:
                fig.add_vline(
                    x=entry_time,
                    line_width=2,
                    line_dash="dot",
                    line_color="green",
                    annotation_text=f"FIR: {fir_id}",
                    annotation_position="top left"
                )
            
            fig.update_layout(
                xaxis_title="Time (UTC)",
                yaxis_title="Flight Level (FL)",
                margin=dict(l=20, r=20, t=30, b=20),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                height=450
            )
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("---")

            st.subheader("📋 Waypoint Route Data Tables")
            tab_actual, tab_planned = st.tabs(["Actual Route Waypoints", "Planned Route Waypoints"])
            with tab_actual:
                st.dataframe(actual_data[['Sequence Number', 'Time Over', 'Flight Level', 'Latitude', 'Longitude']], use_container_width=True)
            with tab_planned:
                if not planned_data.empty:
                    st.dataframe(planned_data[['Sequence Number', 'Time Over', 'Flight Level', 'Latitude', 'Longitude']], use_container_width=True)
                else:
                    st.info("No planned flight record found for this ECTRL ID.")

elif app_mode == "Aircraft Registration Tracker":
    st.subheader("🔍 Aircraft Registration & Fleet Movement Tracker")
    all_regs = sorted([str(x) for x in summary_df['AC Registration'].dropna().unique() if x])
    
    default_idx = 0
    if st.session_state.target_reg in all_regs:
        default_idx = all_regs.index(st.session_state.target_reg)

    selected_reg = st.sidebar.selectbox("Select Aircraft Registration", options=all_regs, index=default_idx)
    st.session_state.target_reg = selected_reg

    if selected_reg:
        reg_flights = summary_df[summary_df['AC Registration'] == selected_reg].sort_values('actual_dep_time')
        
        st.markdown(f"### Tracking Aircraft Registration: **{selected_reg}**")
        r1, r2, r3 = st.columns(3)
        r1.metric("Total Recorded Flights", len(reg_flights))
        r2.metric("Operator", str(reg_flights.iloc[0].get('AC Operator', 'N/A')))
        r3.metric("Aircraft Type", str(reg_flights.iloc[0].get('AC Type', 'N/A')))

        st.dataframe(reg_flights[['ECTRL ID', 'origin_airport', 'destination_airport', 'actual_dep_time', 'actual_arr_time', 'dep_delay_mins', 'max_actual_fl']], use_container_width=True)

        st.markdown("---")
        st.subheader(f"🗺️ Combined Movement Map for Registration {selected_reg} (Full Width)")
        
        m_reg = folium.Map(location=[35.0, -40.0], zoom_start=3)
        for _, flight in reg_flights.iterrows():
            f_id = flight['ECTRL ID']
            f_act = pd.read_sql(f'SELECT Latitude, Longitude FROM actual_flights WHERE "ECTRL ID" = {f_id} ORDER BY "Sequence Number"', conn)
            if not f_act.empty:
                pts = list(zip(f_act['Latitude'], f_act['Longitude']))
                folium.PolyLine(pts, color="purple", weight=3, opacity=0.8, tooltip=f"Flight {f_id}: {flight['origin_airport']} ➔ {flight['destination_airport']}").add_to(m_reg)

        st_folium(m_reg, width=1200, height=600)

elif app_mode == "FIR & Route Analytics":
    st.subheader("🌐 FIR & Route Spatial Analytics")
    st.markdown("Explore Flight Information Regions, toggle between airport and route map layers, and analyze route usage.")

    all_firs = sorted(list(fir_dict.keys()))
    selected_fir = st.sidebar.selectbox("Select FIR Airspace", options=all_firs)

    if selected_fir:
        fir_data = fir_dict[selected_fir]
        fir_poly = fir_data['shape']

        contained_airports = []
        for _, apt in airports_df.iterrows():
            if fir_poly.contains(Point(apt['longitude_deg'], apt['latitude_deg'])):
                contained_airports.append(apt)
        contained_apt_df = pd.DataFrame(contained_airports)

        intersecting_routes = []
        for r_id, r_info in route_dict.items():
            if fir_poly.intersects(r_info['shape']):
                intersecting_routes.append(r_id)

        st.markdown(f"### FIR Analysis: **{selected_fir}**")
        f_col1, f_col2 = st.columns(2)
        f_col1.metric("Enclosed Airports", len(contained_apt_df))
        f_col2.metric("Intersecting Routes", len(intersecting_routes))

        st.markdown("---")
        
        map_layer = st.radio(
            "🗺️ Select FIR Map Layer View:",
            ["Airports Inside FIR", "Associated Routes in FIR"],
            horizontal=True
        )

        mean_lat = sum([pt[0] for pt in fir_data['latlon']]) / len(fir_data['latlon'])
        mean_lon = sum([pt[1] for pt in fir_data['latlon']]) / len(fir_data['latlon'])
        m_fir = folium.Map(location=[mean_lat, mean_lon], zoom_start=5)

        folium.Polygon(
            locations=fir_data['latlon'],
            color="red",
            weight=3,
            fill=True,
            fill_color="pink",
            fill_opacity=0.15,
            tooltip=f"FIR: {selected_fir}"
        ).add_to(m_fir)

        if map_layer == "Airports Inside FIR":
            if not contained_apt_df.empty:
                for _, apt in contained_apt_df.iterrows():
                    folium.Marker(
                        location=[apt['latitude_deg'], apt['longitude_deg']],
                        popup=f"Airport: {apt['ident']} ({apt['name']})",
                        icon=folium.Icon(color="blue", icon="plane", prefix="fa")
                    ).add_to(m_fir)
        else:
            for r_id in intersecting_routes:
                r_info = route_dict[r_id]
                folium.PolyLine(
                    locations=r_info['latlon'],
                    color="purple",
                    weight=3,
                    opacity=0.8,
                    tooltip=f"Route ID: {r_id}"
                ).add_to(m_fir)

        st_folium(m_fir, width=1200, height=550)

        st.markdown("---")
        st.subheader("📋 FIR Traffic, Airports & Route Usage")

        tab_apt, tab_rt = st.tabs(["Enclosed Airports & Traffic", "Associated Routes Usage Table"])

        with tab_apt:
            if not contained_apt_df.empty:
                st.dataframe(contained_apt_df[['ident', 'name', 'latitude_deg', 'longitude_deg']], use_container_width=True)
            else:
                st.info(f"No airports found strictly within the polygon boundary for {selected_fir}.")

            apt_idents = contained_apt_df['ident'].tolist() if not contained_apt_df.empty else []
            fir_flights = summary_df[summary_df['origin_airport'].isin(apt_idents) | summary_df['destination_airport'].isin(apt_idents)]

            if not fir_flights.empty:
                st.markdown("#### 📊 Departure & Arrival Traffic Breakdown")
                fir_flights['Dep_Hour'] = fir_flights['actual_dep_time'].dt.hour
                
                t_week, t_hour = st.tabs(["📅 Weekday Traffic View", "⏰ Hourly Traffic View"])
                
                with t_week:
                    wk_counts = fir_flights.groupby(fir_flights['actual_dep_time'].dt.day_name()).size().reset_index(name='Flights')
                    fig_wk = go.Figure([go.Bar(x=wk_counts['actual_dep_time'], y=wk_counts['Flights'], marker_color='royalblue')])
                    fig_wk.update_layout(xaxis_title="Weekday", yaxis_title="Flight Count", height=350)
                    st.plotly_chart(fig_wk, use_container_width=True)

                with t_hour:
                    hr_counts = fir_flights.groupby('Dep_Hour').size().reset_index(name='Flights')
                    fig_hr = go.Figure([go.Bar(x=hr_counts['Dep_Hour'], y=hr_counts['Flights'], marker_color='indianred')])
                    fig_hr.update_layout(xaxis_title="Hour of Day (UTC)", yaxis_title="Flight Count", height=350)
                    st.plotly_chart(fig_hr, use_container_width=True)

        with tab_rt:
            if intersecting_routes:
                route_usage_data = []
                for r_id in intersecting_routes:
                    route_usage_data.append({
                        "Route ID": r_id,
                        "FIR Airspace": selected_fir,
                        "Waypoints Count": len(route_dict[r_id]['latlon']),
                        "Status": "Active Intersecting Route"
                    })
                st.dataframe(pd.DataFrame(route_usage_data), use_container_width=True)
            else:
                st.info("No predefined routes intersect this FIR polygon.")