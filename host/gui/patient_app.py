# host/gui/patient_app.py

import os
import sys
import time
from collections import deque

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

    # --- session state setup ---
    if "reader" not in st.session_state:
        st.session_state["reader"] = None
    if "values" not in st.session_state:
        # keep only the most recent 200 samples
        st.session_state["values"] = deque(maxlen=200)

    col1, col2 = st.columns(2)
    status_placeholder = col1.empty()
    value_placeholder = col2.empty()
    chart_placeholder = st.empty()
    band_info = st.empty()

    start = st.button("Start")
    stop = st.button("Stop")

    # --- connect / disconnect controls ---
    if start and st.session_state["reader"] is None:
        try:
            st.session_state["reader"] = FSRReader(port=port, baud=baud)
            status_placeholder.success(f"Connected to {port} at {baud} baud.")
        except Exception as e:
            status_placeholder.error(f"Failed to open {port}: {e}")
            st.session_state["reader"] = None

    if stop and st.session_state["reader"] is not None:
        st.session_state["reader"].close()
        st.session_state["reader"] = None
        status_placeholder.info("Stopped streaming.")

    reader = st.session_state["reader"]

    # --- streaming loop ---
    if reader is not None:
        band_info.markdown(
            f"Target band: **{target_min}–{target_max}** ADC units. "
            "Try to hold your squeeze in this range."
        )

        for _ in range(20):  # small loop each rerun
            val = reader.read()
            if val is not None:
                st.session_state["values"].append(val)

                value_placeholder.metric("Current force (ADC units)", val)

                if target_min <= val <= target_max:
                    status_placeholder.success("In target zone ✅")
                else:
                    status_placeholder.warning("Outside target zone")

                chart_placeholder.line_chart(list(st.session_state["values"]))

            time.sleep(0.01)

        # trigger another pass to keep streaming
        st.rerun()


if __name__ == "__main__":
    main()