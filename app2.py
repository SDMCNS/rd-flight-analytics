from pathlib import Path

import streamlit as st
import pandas as pd
from streamlit_folium import st_folium

from ectl_flights import FlightDB, analytics, geo, viz

st.set_page_config(page_title="Advanced Flight & Fleet Explorer", layout="wide")

st.title("✈️ Flight vs. Plan & Fleet Explorer")

WAYPOINT_COLS = ['Sequence Number', 'Time Over', 'Flight Level', 'Latitude', 'Longitude']


@st.cache_resource
def get_db():
    for p in ("flights.db", "data/flights.db"):
        if Path(p).exists():
            return FlightDB(p)
    return FlightDB("flights.db")


try:
    db = get_db()
    summary_df = db.summary()
    fir_dict = db.firs
    route_dict = db.routes
    airports_df = db.airports
except Exception as e:
    st.error(f"Error loading database tables. Did you run `ectl etl`? Details: {e}")
    st.stop()

min_date = summary_df['actual_dep_time'].min().date()
max_date = summary_df['actual_dep_time'].max().date()

# --- SESSION STATE & MODE SELECTOR ---
MODES = ["Single Flight Analysis", "Aircraft Registration Tracker", "FIR & Route Analytics", "Network & Fleet Inferences"]
if "app_mode" not in st.session_state:
    st.session_state.app_mode = MODES[0]
if "target_reg" not in st.session_state:
    st.session_state.target_reg = None

app_mode = st.sidebar.radio("Select Dashboard Mode", MODES, index=MODES.index(st.session_state.app_mode))
st.session_state.app_mode = app_mode

if app_mode == "Single Flight Analysis":
    st.markdown("### 🔍 Single Flight Analysis & Route Profiling")

    all_origins = sorted(str(x) for x in summary_df['origin_airport'].dropna().unique() if x)
    all_destinations = sorted(str(x) for x in summary_df['destination_airport'].dropna().unique() if x)

    st.sidebar.header("Filters")
    date_range = st.sidebar.date_input("Start Date Range", value=[min_date, max_date], min_value=min_date, max_value=max_date)
    selected_origins = st.sidebar.multiselect("Departure Airport(s)", options=all_origins, default=[])
    selected_destinations = st.sidebar.multiselect("Arrival Airport(s)", options=all_destinations, default=[])

    min_fl, max_fl = int(summary_df['max_actual_fl'].min()), int(summary_df['max_actual_fl'].max())
    fl_range = st.sidebar.slider("Max Flight Level Range", min_value=min_fl, max_value=max_fl, value=(min_fl, max_fl))

    filtered_summary = analytics.filter_flights(
        summary_df,
        date_range=tuple(date_range) if len(date_range) == 2 else None,
        origins=selected_origins, destinations=selected_destinations, fl_range=fl_range,
    )
    filtered_flight_ids = filtered_summary['ECTRL ID'].tolist()

    st.sidebar.markdown(f"**Matching Flights:** {len(filtered_flight_ids):,}")

    if not filtered_flight_ids:
        st.warning("No flights match your filter criteria.")
    else:
        selected_flight_id = st.selectbox("Select Flight (ECTRL ID)", options=filtered_flight_ids)

        if selected_flight_id:
            actual_data = db.actual_points(selected_flight_id)
            planned_data = db.planned_points(selected_flight_id)
            row_stat = db.flight(selected_flight_id)

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
            st_folium(viz.flight_map(actual_data, planned_data, fir_dict), width=1200, height=500)

            st.markdown("---")
            st.subheader("📈 Vertical Altitude Profile Over Time with FIR Crossings (Full Width)")
            st.plotly_chart(viz.vertical_profile(actual_data, planned_data, fir_dict), use_container_width=True)

            st.markdown("---")
            st.subheader("📋 Waypoint Route Data Tables")
            tab_actual, tab_planned = st.tabs(["Actual Route Waypoints", "Planned Route Waypoints"])
            with tab_actual:
                st.dataframe(actual_data[WAYPOINT_COLS], use_container_width=True)
            with tab_planned:
                if not planned_data.empty:
                    st.dataframe(planned_data[WAYPOINT_COLS], use_container_width=True)
                else:
                    st.info("No planned flight record found for this ECTRL ID.")

elif app_mode == "Aircraft Registration Tracker":
    st.subheader("🔍 Aircraft Registration & Fleet Movement Tracker")
    all_regs = sorted(str(x) for x in summary_df['AC Registration'].dropna().unique() if x)

    default_idx = all_regs.index(st.session_state.target_reg) if st.session_state.target_reg in all_regs else 0
    selected_reg = st.sidebar.selectbox("Select Aircraft Registration", options=all_regs, index=default_idx)
    st.session_state.target_reg = selected_reg

    if selected_reg:
        reg_flights = db.flights_for_registration(selected_reg)

        st.markdown(f"### Tracking Aircraft Registration: **{selected_reg}**")
        r1, r2, r3 = st.columns(3)
        r1.metric("Total Recorded Flights", len(reg_flights))
        r2.metric("Operator", str(reg_flights.iloc[0].get('AC Operator', 'N/A')))
        r3.metric("Aircraft Type", str(reg_flights.iloc[0].get('AC Type', 'N/A')))

        st.dataframe(reg_flights[['ECTRL ID', 'origin_airport', 'destination_airport', 'actual_dep_time',
                                  'actual_arr_time', 'dep_delay_mins', 'max_actual_fl']], use_container_width=True)

        st.markdown("---")
        st.subheader(f"🗺️ Combined Movement Map for Registration {selected_reg} (Full Width)")
        paths = (
            (f"Flight {f['ECTRL ID']}: {f['origin_airport']} ➔ {f['destination_airport']}", db.actual_points(f['ECTRL ID']))
            for _, f in reg_flights.iterrows()
        )
        st_folium(viz.multi_flight_map(paths), width=1200, height=600)

elif app_mode == "Network & Fleet Inferences":
    st.subheader("🌐 Network, City Pairs & Fleet Inferences")
    st.markdown("Analyze high-density city pairs, airline route dominance, and estimated passenger and cargo throughput based on aircraft capacity mappings.")

    df_inf = analytics.add_capacity_estimates(summary_df)

    tab_pairs, tab_airline, tab_capacity = st.tabs(["🏙️ Top City Pairs", "🏢 Airline Route Dominance", "📦 Passenger & Cargo Inferences"])

    with tab_pairs:
        st.markdown("### Most Common Airport Pairings (Origin ➔ Destination)")
        top_pairs = analytics.top_city_pairs(df_inf, n=15)
        st.dataframe(top_pairs, use_container_width=True)
        top10 = top_pairs.head(10)
        st.plotly_chart(viz.bar(top10['City_Pair'], top10['Flight_Count'], horizontal=True,
                                xaxis_title="Number of Flights"), use_container_width=True)

    with tab_airline:
        st.markdown("### Airline Network & Route Dominance")
        selected_operator = st.selectbox("Filter by Airline Operator",
                                         options=["All Operators"] + sorted(df_inf['AC Operator'].dropna().unique().tolist()))
        routes_tbl = analytics.airline_routes(df_inf, None if selected_operator == "All Operators" else selected_operator)
        st.dataframe(routes_tbl.head(20), use_container_width=True)

    with tab_capacity:
        st.markdown("### Estimated Fleet Passenger & Cargo Throughput")
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Estimated Passengers", f"{df_inf['Est_Passengers'].sum():,.0f}")
        c2.metric("Total Estimated Cargo", f"{df_inf['Est_Cargo_Tonnes'].sum():,.1f} tonnes")
        c3.metric("Average Flight Distance", f"{df_inf['Actual Distance Flown (nm)'].mean():.0f} nm")
        st.dataframe(analytics.operator_throughput(df_inf), use_container_width=True)

elif app_mode == "FIR & Route Analytics":
    st.subheader("🌐 FIR & Route Spatial Analytics")
    st.markdown("Explore Flight Information Regions, toggle between airport and route map layers, and analyze route usage.")

    selected_fir = st.sidebar.selectbox("Select FIR Airspace", options=sorted(fir_dict.keys()))

    if selected_fir:
        fir_data = fir_dict[selected_fir]
        contained_apt_df = geo.airports_in_fir(fir_data['shape'], airports_df)
        intersecting_routes = geo.routes_in_fir(fir_data['shape'], route_dict)

        st.markdown(f"### FIR Analysis: **{selected_fir}**")
        f_col1, f_col2 = st.columns(2)
        f_col1.metric("Enclosed Airports", len(contained_apt_df))
        f_col2.metric("Intersecting Routes", len(intersecting_routes))

        st.markdown("---")
        map_layer = st.radio("🗺️ Select FIR Map Layer View:", ["Airports Inside FIR", "Associated Routes in FIR"], horizontal=True)

        if map_layer == "Airports Inside FIR":
            m_fir = viz.fir_map(selected_fir, fir_data, airports=contained_apt_df)
        else:
            m_fir = viz.fir_map(selected_fir, fir_data, routes=route_dict, route_ids=intersecting_routes)
        st_folium(m_fir, width=1200, height=550)

        st.markdown("---")
        st.subheader("📋 FIR Traffic, Airports & Route Usage")
        tab_apt, tab_rt = st.tabs(["Enclosed Airports & Traffic", "Associated Routes Usage Table"])

        with tab_apt:
            if not contained_apt_df.empty:
                st.dataframe(contained_apt_df[['ident', 'name', 'latitude_deg', 'longitude_deg']], use_container_width=True)
            else:
                st.info(f"No airports found strictly within the polygon boundary for {selected_fir}.")

            fir_flights = analytics.flights_touching_airports(summary_df, contained_apt_df['ident'])

            if not fir_flights.empty:
                st.markdown("#### 📊 Departure & Arrival Traffic Breakdown")
                t_week, t_hour = st.tabs(["📅 Weekday Traffic View", "⏰ Hourly Traffic View"])
                with t_week:
                    wk = analytics.traffic_by_weekday(fir_flights)
                    st.plotly_chart(viz.bar(wk['Weekday'], wk['Flights'], xaxis_title="Weekday",
                                            yaxis_title="Flight Count", height=350), use_container_width=True)
                with t_hour:
                    hr = analytics.traffic_by_hour(fir_flights)
                    st.plotly_chart(viz.bar(hr['Dep_Hour'], hr['Flights'], color='indianred',
                                            xaxis_title="Hour of Day (UTC)", yaxis_title="Flight Count", height=350),
                                    use_container_width=True)

        with tab_rt:
            if intersecting_routes:
                st.dataframe(pd.DataFrame([
                    {"Route ID": r_id, "FIR Airspace": selected_fir,
                     "Waypoints Count": len(route_dict[r_id]['latlon']), "Status": "Active Intersecting Route"}
                    for r_id in intersecting_routes
                ]), use_container_width=True)
            else:
                st.info("No predefined routes intersect this FIR polygon.")
