# host/gui/clinician_app.py

import os
import sys
import csv
from statistics import mean

import streamlit as st

# Add parent folder ("host") to import path if we ever want shared utils
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.append(ROOT)


def list_session_files(data_dir):
    if not os.path.isdir(data_dir):
        return []
    return sorted(
        [
            f
            for f in os.listdir(data_dir)
            if f.startswith("session_") and f.endswith(".csv")
        ]
    )


def load_session_csv(path):
    times = []
    values = []
    with open(path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                t = float(row["time_s"])
                v = float(row["force_adc"])
            except (KeyError, ValueError):
                continue
            times.append(t)
            values.append(v)
    return times, values


def main():
    st.set_page_config(page_title="Cardinal Grip – Clinician GUI", layout="wide")
    st.title("Cardinal Grip – Clinician Dashboard (Analysis)")

    # Same target band idea as patient view
    target_min = st.sidebar.slider("Target band (min)", 0, 4095, 1200)
    target_max = st.sidebar.slider("Target band (max)", 0, 4095, 2000)

    # Where patient / firmware code should be saving session CSVs
    data_dir = os.path.join(os.path.dirname(ROOT), "data", "logs")
    st.sidebar.markdown(f"**Data folder:** `{data_dir}`")

    files = list_session_files(data_dir)
    if not files:
        st.warning(
            "No session CSV files found.\n\n"
            "Make sure your patient/recording code saves files like "
            "`session_YYYYMMDD_HHMMSS.csv` into `data/logs/`."
        )
        return

    selected_file = st.selectbox("Select a session file", files)

    full_path = os.path.join(data_dir, selected_file)
    st.write(f"**Selected file:** `{full_path}`")

    times, values = load_session_csv(full_path)

    if not values:
        st.error("No valid data in this CSV (check file format).")
        return

    # Plot force trace
    st.subheader("Force over time")
    st.line_chart(values)

    # Summary statistics
    max_force = max(values)
    avg_force = mean(values)
    in_band = [v for v in values if target_min <= v <= target_max]
    pct_in_band = 100 * len(in_band) / len(values)

    st.subheader("Summary metrics")
    st.markdown(
        f"""
        * **Samples:** `{len(values)}`  
        * **Max force:** `{max_force:.0f}` ADC units  
        * **Mean force:** `{avg_force:.0f}` ADC units  
        * **Time in target band ({target_min}–{target_max}):** `{pct_in_band:.1f}%`  
        """
    )

    # Optional: show a small table of first few rows
    if st.checkbox("Show raw data (first 20 rows)"):
        st.table(
            {
                "time_s": [f"{t:.2f}" for t in times[:20]],
                "force_adc": [f"{v:.0f}" for v in values[:20]],
            }
        )


if __name__ == "__main__":
    main()