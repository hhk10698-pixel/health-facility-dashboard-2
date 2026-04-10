import json
from urllib.request import urlopen

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="National Health Facility Map",
    layout="wide",
    page_icon="map",
)

GEOJSON_URL = (
    "https://gist.githubusercontent.com/jbrobst/56c13bbbf9d97d187fea01ca62ea5112/"
    "raw/e388c4cae20aa53cb5090210a42ebb9b765c0a36/india_states.geojson"
)

STATE_NAME_MAP = {
    "Arunachal": "Arunachal Pradesh",
    "DNH &DD": "Dadra and Nagar Haveli and Daman and Diu",
    "Jammu and Kashmir": "Jammu & Kashmir",
    "UP Health Facility Data": "Uttar Pradesh",
    "Chattisgarh": "Chhattisgarh",
    "Andaman and Nicobar Islands": "Andaman & Nicobar",
    "Andaman & Nicobar Islands": "Andaman & Nicobar",
}

def normalize_state_name(name):
    if pd.isna(name):
        return ""
    cleaned = str(name).strip()
    return STATE_NAME_MAP.get(cleaned, cleaned)

@st.cache_data
def load_geojson():
    with urlopen(GEOJSON_URL) as response:
        return json.load(response)

@st.cache_data
def geojson_state_list():
    geojson = load_geojson()
    states = sorted({feature["properties"]["ST_NM"] for feature in geojson["features"]})
    return states

def format_breakdown(group):
    counts = group.value_counts().head(8)
    return ", ".join([f"{k}: {v}" for k, v in counts.items()])

# --- App UI & Data Loading ---
st.title("National Health Facility Explorer")

st.sidebar.header("1. Upload Data")
uploaded_file = st.sidebar.file_uploader(
    "Upload master_health_facilities (CSV or Excel)", 
    type=["csv", "xlsx", "xls"]
)

if uploaded_file is None:
    st.info("👋 Welcome! Please upload your master dataset in the sidebar to begin.")
    st.stop()

# Read uploaded file
try:
    if uploaded_file.name.lower().endswith(".csv"):
        master_df = pd.read_csv(uploaded_file)
    else:
        master_df = pd.read_excel(uploaded_file)
except Exception as e:
    st.error(f"Error reading file: {e}")
    st.stop()

# Validate columns
if "Name of Facility" not in master_df.columns or "Type of Facility (Category)" not in master_df.columns:
    st.error("Required columns missing. Ensure your file has 'Name of Facility' and 'Type of Facility (Category)'.")
    st.stop()

# Clean state names
if "Name of State/UTs" in master_df.columns:
    master_df["Name of State/UTs"] = master_df["Name of State/UTs"].apply(normalize_state_name)

# --- Filtering ---
st.sidebar.markdown("---")
st.sidebar.header("2. Filter Details")
available_states = sorted(master_df["Name of State/UTs"].dropna().astype(str).unique())
selected_state = st.sidebar.selectbox("Select State", ["All India"] + available_states)

filtered_df = (
    master_df if selected_state == "All India" else master_df[master_df["Name of State/UTs"] == selected_state]
)

# --- Metrics ---
total_facilities = int(filtered_df["Name of Facility"].count())
filtered_for_pivot = filtered_df.copy()

if "District" in filtered_for_pivot.columns:
    filtered_for_pivot["District"] = (
        filtered_for_pivot["District"]
        .astype("string")
        .str.strip()
        .replace("", pd.NA)
    )
    filtered_for_pivot = filtered_for_pivot.dropna(subset=["District"])
    
    if selected_state == "All India":
        total_districts = int(
            filtered_for_pivot[["Name of State/UTs", "District"]]
            .drop_duplicates()
            .shape[0]
        )
    else:
        total_districts = int(filtered_for_pivot["District"].nunique())
else:
    total_districts = 0

india_geojson = load_geojson()
all_geojson_states = geojson_state_list()

m1, m2 = st.columns(2)
with m1:
    st.metric("Total Facilities", f"{total_facilities:,}")
with m2:
    st.metric("Total Districts", f"{total_districts:,}")

# --- Map Generation ---
type_breakdown_df = (
    master_df.groupby("Name of State/UTs")["Type of Facility (Category)"]
    .apply(format_breakdown)
    .reset_index(name="Facility Breakup")
)

state_counts_df = (
    master_df.groupby("Name of State/UTs", as_index=False)["Name of Facility"]
    .count()
    .rename(columns={"Name of State/UTs": "State", "Name of Facility": "Total Facilities"})
)

map_data = pd.DataFrame({"State": all_geojson_states})
map_data = map_data.merge(state_counts_df, on="State", how="left")
map_data = map_data.merge(
    type_breakdown_df.rename(columns={"Name of State/UTs": "State"}),
    on="State",
    how="left",
)
map_data["Total Facilities"] = map_data["Total Facilities"].fillna(0).astype(int)
map_data["Facility Breakup"] = map_data["Facility Breakup"].fillna("No data")
map_data["MapValue"] = map_data["Total Facilities"]

map_max = max(int(map_data["MapValue"].max()), 1)
red_green_scale = [
    [0.0, "#f5f5f5"],     # Very light grey for 0
    [0.000001, "#c8e6c9"], # Light green for > 0
    [0.30, "#81c784"],
    [0.60, "#43a047"],
    [1.00, "#1b5e20"],     # Dark green for max
]

map_fig = px.choropleth(
    map_data,
    geojson=india_geojson,
    featureidkey="properties.ST_NM",
    locations="State",
    color="MapValue",
    color_continuous_scale=red_green_scale,
    range_color=(0, map_max),
    hover_name="State",
    hover_data={
        "Total Facilities": True,
        "Facility Breakup": True,
        "MapValue": False,
        "State": False,
    },
)
map_fig.update_geos(fitbounds="locations", visible=False)
map_fig.update_layout(height=680, margin={"r": 0, "t": 0, "l": 0, "b": 0})

if selected_state == "All India":
    st.subheader("India Facility Density Map")
    st.plotly_chart(map_fig, width='stretch')
    st.markdown("---")

# --- Tables and Charts ---
st.subheader(f"Facility Distribution: {selected_state}")

if "District" in filtered_for_pivot.columns:
    pivot_df = pd.pivot_table(
        filtered_for_pivot,
        values="Name of Facility",
        index=["Name of State/UTs", "District"],
        columns="Type of Facility (Category)",
        aggfunc="count",
        fill_value=0,
        margins=True,
        margins_name="Grand Total",
    )
    st.dataframe(pivot_df, width='stretch')
else:
    st.info("District column not found; skipping pivot table.")

st.markdown("#### Raw Data Table")
st.dataframe(filtered_df, width='stretch')

st.subheader("Facility-wise Charts")

pie_data = (
    filtered_df["Type of Facility (Category)"]
    .fillna("Unknown")
    .astype(str)
    .str.strip()
    .replace("", "Unknown")
    .value_counts()
    .reset_index()
)
pie_data.columns = ["Facility Type", "Count"]

if selected_state == "All India":
    stacked_df = (
        filtered_df.assign(
            FacilityType=filtered_df["Type of Facility (Category)"]
            .fillna("Unknown").astype(str).str.strip().replace("", "Unknown")
        )
        .groupby(["Name of State/UTs", "FacilityType"], as_index=False)["Name of Facility"]
        .count()
        .rename(columns={"Name of State/UTs": "Location", "Name of Facility": "Count"})
    )
    chart_title = "All India: State-wise Breakdown"
    x_axis = "Location"
else:
    if "District" in filtered_df.columns:
        stacked_df = (
            filtered_df.assign(
                FacilityType=filtered_df["Type of Facility (Category)"]
                .fillna("Unknown").astype(str).str.strip().replace("", "Unknown")
            )
            .groupby(["District", "FacilityType"], as_index=False)["Name of Facility"]
            .count()
            .rename(columns={"Name of Facility": "Count", "District": "Location"})
        )
        chart_title = f"{selected_state}: District-wise Breakdown"
        x_axis = "Location"
    else:
        stacked_df = pd.DataFrame() # Fallback if no district

col1, col2 = st.columns(2)
with col1:
    pie_fig = px.pie(
        pie_data,
        names="Facility Type",
        values="Count",
        title=f"{selected_state}: Facility Type Breakup",
    )
    st.plotly_chart(pie_fig, width='stretch')

with col2:
    if not stacked_df.empty:
        stack_fig = px.bar(
            stacked_df,
            x=x_axis,
            y="Count",
            color="FacilityType",
            title=chart_title,
        )
        stack_fig.update_layout(barmode="stack", xaxis_tickangle=-45)
        st.plotly_chart(stack_fig, width='stretch')
    else:
        st.info("Not enough location data to generate stacked bar chart.")