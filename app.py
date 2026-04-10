import io
import json
import zipfile
from pathlib import Path
from urllib.request import urlopen

import pandas as pd
import plotly.express as px
import streamlit as st


st.set_page_config(
    page_title="National Health Facility Map",
    layout="wide",
    page_icon="map",
)


DATA_DIR = Path(r"C:\Users\hari\OneDrive\Desktop\Functional PHF")
MASTER_CSV_PATH = DATA_DIR / "master_health_facilities.csv"
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
    if name is None:
        return ""
    cleaned = str(name).strip()
    return STATE_NAME_MAP.get(cleaned, cleaned)


def resolve_master_csv_path():
    preferred = DATA_DIR / "master_health_facilities.csv"
    if preferred.exists():
        return preferred

    candidates = sorted(
        DATA_DIR.glob("master_health_facilities.*"),
        key=lambda p: p.suffix.lower(),
    )
    for candidate in candidates:
        if candidate.suffix.lower() in [".csv", ".xlsx", ".xls"]:
            return candidate
    return None


@st.cache_data
def load_geojson():
    with urlopen(GEOJSON_URL) as response:
        return json.load(response)


@st.cache_data
def load_master_data(path_str, signature):
    path = Path(path_str)
    if not path.exists():
        return pd.DataFrame()
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    else:
        df = pd.read_excel(path)
    if "Name of State/UTs" in df.columns:
        df["Name of State/UTs"] = df["Name of State/UTs"].map(normalize_state_name)
    return df


@st.cache_data
def geojson_state_list():
    geojson = load_geojson()
    states = sorted({feature["properties"]["ST_NM"] for feature in geojson["features"]})
    return states


@st.cache_data
def state_file_map():
    result = {}
    for file_path in DATA_DIR.glob("*"):
        if not file_path.is_file():
            continue
        if file_path.name.lower() == "master_health_facilities.csv":
            continue
        if file_path.suffix.lower() not in [".xlsx", ".xls", ".csv"]:
            continue
        state_name = normalize_state_name(file_path.stem)
        result[state_name] = file_path
    return result


@st.cache_data
def load_state_file(path_str):
    path = Path(path_str)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    return pd.read_excel(path)


@st.cache_data
def build_state_files_zip():
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(DATA_DIR.glob("*")):
            if not file_path.is_file():
                continue
            if file_path.name.lower() == "master_health_facilities.csv":
                continue
            if file_path.suffix.lower() not in [".xlsx", ".xls", ".csv"]:
                continue
            zf.write(file_path, arcname=file_path.name)
    zip_buffer.seek(0)
    return zip_buffer.getvalue()


def format_breakdown(group):
    counts = group.value_counts().head(8)
    return ", ".join([f"{k}: {v}" for k, v in counts.items()])


resolved_master_path = resolve_master_csv_path()
if resolved_master_path and resolved_master_path.exists():
    file_signature = f"{resolved_master_path.stat().st_mtime_ns}-{resolved_master_path.stat().st_size}"
    master_df = load_master_data(str(resolved_master_path), file_signature)
else:
    master_df = pd.DataFrame()

if master_df.empty:
    st.error(
        f"Master dataset not found in: {DATA_DIR}. Expected master_health_facilities.csv (or xlsx/xls)."
    )
    st.stop()

if "Name of Facility" not in master_df.columns or "Type of Facility (Category)" not in master_df.columns:
    st.error(
        "Required columns missing in master CSV. Needed: 'Name of Facility' and "
        "'Type of Facility (Category)'."
    )
    st.stop()


india_geojson = load_geojson()
all_geojson_states = geojson_state_list()
state_files = state_file_map()

st.title("National Health Facility Explorer")

st.sidebar.header("Filter Details")
available_states = sorted(master_df["Name of State/UTs"].dropna().astype(str).unique())
selected_state = st.sidebar.selectbox("Select State", ["All India"] + available_states)

filtered_df = (
    master_df if selected_state == "All India" else master_df[master_df["Name of State/UTs"] == selected_state]
)

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

if selected_state == "All India":
    received_states = set(state_files.keys())
    received_count = sum(1 for state in all_geojson_states if state in received_states)
    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("State/UT Data Received", f"{received_count} / 36")
    with m2:
        st.metric("Total Facilities", f"{total_facilities}")
    with m3:
        st.metric("Total Districts", f"{total_districts}")
else:
    m1, m2 = st.columns(2)
    with m1:
        st.metric("Total Facilities", f"{total_facilities}")
    with m2:
        st.metric("Total Districts", f"{total_districts}")

st.download_button(
    label="Download master_health_facilities.csv",
    data=resolved_master_path.read_bytes(),
    file_name=resolved_master_path.name,
    mime="text/csv" if resolved_master_path.suffix.lower() == ".csv" else "application/octet-stream",
)

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
map_data["Facility Breakup"] = map_data["Facility Breakup"].fillna("No data received")
map_data["Received"] = map_data["State"].isin(state_files.keys())
map_data["MapValue"] = map_data.apply(
    lambda row: max(int(row["Total Facilities"]), 1) if row["Received"] else 0,
    axis=1,
)

map_max = max(int(map_data["MapValue"].max()), 1)
red_green_scale = [
    [0.0, "#d32f2f"],
    [0.000001, "#d32f2f"],
    [0.05, "#c8e6c9"],
    [0.30, "#81c784"],
    [0.60, "#43a047"],
    [1.00, "#1b5e20"],
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
        "Received": True,
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
    st.info("District column not found, so pivot table with district breakdown is skipped.")

st.markdown("#### Raw Data Table")
if selected_state == "All India":
    raw_df = master_df
else:
    state_path = state_files.get(selected_state)
    if state_path and state_path.exists():
        raw_df = load_state_file(str(state_path))
    else:
        raw_df = filtered_df
        st.warning(f"State source file not found for {selected_state} in {DATA_DIR}")
st.dataframe(raw_df, width='stretch')

if selected_state == "All India":
    st.download_button(
        label="Download all state-wise files (original folder ZIP)",
        data=build_state_files_zip(),
        file_name="state_wise_files.zip",
        mime="application/zip",
    )
else:
    state_path = state_files.get(selected_state)
    if state_path and state_path.exists():
        st.download_button(
            label=f"Download {state_path.name}",
            data=state_path.read_bytes(),
            file_name=state_path.name,
            mime="application/octet-stream",
        )

st.subheader("Facility-wise Charts")

if selected_state == "All India":
    pie_data = (
        master_df["Type of Facility (Category)"]
        .fillna("Unknown")
        .astype(str)
        .str.strip()
        .replace("", "Unknown")
        .value_counts()
        .reset_index()
    )
    pie_data.columns = ["Facility Type", "Count"]

    stacked_state_df = (
        master_df.assign(
            FacilityType=master_df["Type of Facility (Category)"]
            .fillna("Unknown")
            .astype(str)
            .str.strip()
            .replace("", "Unknown")
        )
        .groupby(["Name of State/UTs", "FacilityType"], as_index=False)["Name of Facility"]
        .count()
        .rename(columns={"Name of State/UTs": "State", "Name of Facility": "Count"})
    )

    col1, col2 = st.columns(2)
    with col1:
        pie_fig = px.pie(
            pie_data,
            names="Facility Type",
            values="Count",
            title="All India: Facility Type Breakup",
        )
        st.plotly_chart(pie_fig, width='stretch')
    with col2:
        state_stack_fig = px.bar(
            stacked_state_df,
            x="State",
            y="Count",
            color="FacilityType",
            title="All India: State-wise Stacked Facility Breakup",
        )
        state_stack_fig.update_layout(barmode="stack", xaxis_tickangle=-45)
        st.plotly_chart(state_stack_fig, width='stretch')
else:
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

    if "District" not in filtered_df.columns:
        pie_fig = px.pie(
            pie_data,
            names="Facility Type",
            values="Count",
            title=f"{selected_state}: Facility Type Breakup",
        )
        st.plotly_chart(pie_fig, width='stretch')
        st.info("District column not found, so district-wise stacked chart cannot be shown.")
    else:
        district_stack_df = (
            filtered_df.assign(
                FacilityType=filtered_df["Type of Facility (Category)"]
                .fillna("Unknown")
                .astype(str)
                .str.strip()
                .replace("", "Unknown")
            )
            .groupby(["District", "FacilityType"], as_index=False)["Name of Facility"]
            .count()
            .rename(columns={"Name of Facility": "Count"})
        )

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
            district_stack_fig = px.bar(
                district_stack_df,
                x="District",
                y="Count",
                color="FacilityType",
                title=f"{selected_state}: District-wise Stacked Facility Breakup",
            )
            district_stack_fig.update_layout(barmode="stack", xaxis_tickangle=-45)
            st.plotly_chart(district_stack_fig, width='stretch')