# host/gui/patient_app.py

import os
import sys
import time
import csv
from collections import deque
from datetime import datetime

import streamlit as st

# Add parent folder ("host") to import path
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.append(ROOT)

from fsr_reader import FSRReader  # noqa: E402


def main():
    st.set_page_config(page_title="Cardinal Grip – Patient GUI", layout="centered")
    st.title("Cardinal Grip – Patient View")

    port = st.sidebar.text_input("Serial port", "/dev/cu.usbserial-0001")
    baud = st.sidebar.number_input("Baud rate", value=115200, step=1200)
    target_min = st.sidebar.slider("Target band (min)", 0, 4095, 1200)
    target_max = st.sidebar.slider("Target band (max)", 0, 4095, 2000)

    # Folder where we will save session CSVs
    data_dir = os.path.join(os.path.dirname(ROOT), "data", "logs")
    os.makedirs(data_dir, exist_ok=True)

    # ---- session state setup ----
    if "reader" not in st.session_state:
        st.session_state["reader"] = None
    if "values" not in st.session_state:
        st.session_state["values"] = deque(maxlen=2000)
    if "times" not in st.session_state:
        st.session_state["times"] = deque(maxlen=2000)
    if "start_time" not in st.session_state:
        st.session_state["start_time"] = None
    if "last_csv_path" not in st.session_state:
        st.session_state["last_csv_path"] = None

    col1, col2 = st.columns(2)
    status_placeholder = col1.empty()
    value_placeholder = col2.empty()
    chart_placeholder = st.empty()
    band_info = st.empty()
    csv_info = st.empty()

    # ---- control buttons ----
    start = st.button("Start streaming")
    stop = st.button("Stop")
    reset = st.button("Reset session")
    save_csv = st.button("Save session as CSV")

    # ---- handle reset ----
    if reset:
        st.session_state["values"].clear()
        st.session_state["times"].clear()
        st.session_state["start_time"] = None
        st.session_state["last_csv_path"] = None
        status_placeholder.info("Session reset.")

    # ---- connect / disconnect ----
    if start and st.session_state["reader"] is None:
        try:
            st.session_state["reader"] = FSRReader(port=port, baud=baud)
            st.session_state["values"].clear()
            st.session_state["times"].clear()
            st.session_state["start_time"] = time.time()
            status_placeholder.success(f"Connected to {port} at {baud} baud.")
        except Exception as e:
            status_placeholder.error(f"Failed to open {port}: {e}")
            st.session_state["reader"] = None

    if stop and st.session_state["reader"] is not None:
        st.session_state["reader"].close()
        st.session_state["reader"] = None
        status_placeholder.info("Stopped streaming.")

    reader = st.session_state["reader"]

    # ---- handle CSV save (does NOT affect streaming loop) ----
    if save_csv:
        if st.session_state["values"] and st.session_state["times"]:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_path = os.path.join(data_dir, f"session_{ts}.csv")
            try:
                with open(csv_path, "w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(["time_s", "force_adc"])
                    for t, v in zip(st.session_state["times"], st.session_state["values"]):
                        writer.writerow([t, v])
                st.session_state["last_csv_path"] = csv_path
                csv_info.success(f"Saved session to `{csv_path}`")
            except Exception as e:
                csv_info.error(f"Failed to save CSV: {e}")
        else:
            csv_info.warning("No data to save yet. Squeeze the device first.")

    # ---- streaming loop (same basic structure as earlier fast version) ----
    if reader is not None:
        band_info.markdown(
            f"Target band: **{target_min}–{target_max}** ADC units. "
            "Try to hold your squeeze in this range."
        )

        if st.session_state["start_time"] is None:
            st.session_state["start_time"] = time.time()

        # small chunk each rerun to keep UI responsive
        for _ in range(10):
            val = reader.read()
            if val is not None:
                t = time.time() - st.session_state["start_time"]
                st.session_state["times"].append(t)
                st.session_state["values"].append(val)

                value_placeholder.metric("Current force (ADC units)", val)

                if target_min <= val <= target_max:
                    status_placeholder.success("In target zone ✅")
                else:
                    status_placeholder.warning("Outside target zone")

                # Re-draw full window; slightly heavier but stable
                chart_placeholder.line_chart(list(st.session_state["values"]))

            time.sleep(0.01)  # ~100 Hz polling

        st.rerun()

    # If not streaming but we have a last CSV path, remind the user
    if st.session_state["last_csv_path"] is not None and reader is None:
        csv_info.markdown(
            f"Last saved session: `{st.session_state['last_csv_path']}`"
        )


if __name__ == "__main__":
    main()