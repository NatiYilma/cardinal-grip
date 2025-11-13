# host/gui/clinician_app.py

import os
import sys
import time
import csv
from datetime import datetime
from statistics import mean

import streamlit as st

# Add parent folder ("host") to import path
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.append(ROOT)

from fsr_reader import FSRReader  # noqa: E402


def main():
    st.set_page_config(page_title="Cardinal Grip – Clinician GUI", layout="wide")
    st.title("Cardinal Grip – Clinician Dashboard")

    # ---- Sidebar configuration ----
    port = st.sidebar.text_input("Serial port", "/dev/cu.usbserial-0001")
    baud = st.sidebar.number_input("Baud rate", value=115200, step=1200)
    session_duration = st.sidebar.number_input(
        "Session duration (seconds)", value=20, min_value=5, max_value=300
    )
    target_min = st.sidebar.slider("Target band (min)", 0, 4095, 1200)
    target_max = st.sidebar.slider("Target band (max)", 0, 4095, 2000)

    data_dir = os.path.join(os.path.dirname(ROOT), "data", "logs")
    os.makedirs(data_dir, exist_ok=True)

    # ---- Initialize session_state ----
    if "reader" not in st.session_state:
        st.session_state["reader"] = None
    if "recording" not in st.session_state:
        st.session_state["recording"] = False
    if "start_time" not in st.session_state:
        st.session_state["start_time"] = None
    if "times" not in st.session_state:
        st.session_state["times"] = []
    if "values" not in st.session_state:
        st.session_state["values"] = []
    if "last_csv_path" not in st.session_state:
        st.session_state["last_csv_path"] = None

    col1, col2 = st.columns(2)
    status_placeholder = col1.empty()
    summary_placeholder = col2.empty()
    chart_placeholder = st.empty()

    st.markdown(
        """
        **Clinician workflow:**  
        1. Set duration & target band in the sidebar.  
        2. Click **Start session**.  
        3. Patient performs the grip task for the specified time.  
        4. Review summary metrics and CSV log.
        """
    )

    start_btn = st.button("Start session")
    stop_btn = st.button("Stop session")

    # ---- Handle Start ----
    if start_btn and not st.session_state["recording"]:
        # reset data
        st.session_state["times"] = []
        st.session_state["values"] = []
        st.session_state["last_csv_path"] = None

        # open serial
        try:
            st.session_state["reader"] = FSRReader(port=port, baud=baud)
            status_placeholder.success(f"Connected to {port} at {baud} baud.")
            st.session_state["recording"] = True
            st.session_state["start_time"] = time.time()
        except Exception as e:
            status_placeholder.error(f"Failed to open {port}: {e}")
            st.session_state["reader"] = None
            st.session_state["recording"] = False

    # ---- Handle Stop ----
    if stop_btn and st.session_state["recording"]:
        st.session_state["recording"] = False
        if st.session_state["reader"] is not None:
            st.session_state["reader"].close()
            st.session_state["reader"] = None
        status_placeholder.info("Session manually stopped.")

    # ---- Live recording / update ----
    reader = st.session_state["reader"]
    recording = st.session_state["recording"]

    if recording and reader is not None:
        elapsed = time.time() - st.session_state["start_time"]

        # Check if session duration reached
        if elapsed >= session_duration:
            # End session
            st.session_state["recording"] = False
            reader.close()
            st.session_state["reader"] = None
            status_placeholder.success("Session completed ✅")

            # Save CSV and compute summary
            save_and_summarize(
                st.session_state["times"],
                st.session_state["values"],
                target_min,
                target_max,
                data_dir,
                summary_placeholder,
            )

        else:
            # Read one sample
            v = reader.read()
            t = elapsed
            if v is not None:
                st.session_state["times"].append(t)
                st.session_state["values"].append(v)

            # Update chart with all collected values
            if st.session_state["values"]:
                chart_placeholder.line_chart(st.session_state["values"])

            status_placeholder.info(
                f"Recording… {elapsed:.1f}/{session_duration:.1f} s"
            )

            # Rerun soon to get next sample
            time.sleep(0.01)
            st.rerun()

    else:
        # Not currently recording; if we have data from last session, show summary
        if st.session_state["values"]:
            # Ensure chart shows the last session values
            chart_placeholder.line_chart(st.session_state["values"])

            # If we already saved CSV, remind where it is
            if st.session_state["last_csv_path"] is not None:
                summary_placeholder.markdown(
                    f"Last session CSV: `{st.session_state['last_csv_path']}`"
                )


def save_and_summarize(times, values, target_min, target_max, data_dir, summary_placeholder):
    """Save current session to CSV and show summary metrics."""
    if not values:
        summary_placeholder.warning("No valid data captured.")
        return

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(data_dir, f"session_{ts}.csv")

    # Write CSV
    try:
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["time_s", "force_adc"])
            for t, v in zip(times, values):
                writer.writerow([t, v])
    except Exception as e:
        summary_placeholder.error(f"Failed to save CSV: {e}")
        return

    max_force = max(values)
    avg_force = mean(values)
    in_band = [v for v in values if target_min <= v <= target_max]
    pct_in_band = 100 * len(in_band) / len(values)

    # Remember path in session_state
    st.session_state["last_csv_path"] = csv_path

    summary_placeholder.markdown(
        f"""
        ### Session Summary

        * **Samples:** `{len(values)}`  
        * **Max force:** `{max_force}` ADC units  
        * **Mean force:** `{int(avg_force)}` ADC units  
        * **Time in target band ({target_min}–{target_max}):** `{pct_in_band:.1f}%`  
        * **Saved file:** `{csv_path}`
        """
    )


if __name__ == "__main__":
    main()