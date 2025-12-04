# Cardinal Grip

Cardinal Grip is a force-sensing glove system designed for finger individuation, motor control training, and stroke-oriented rehabilitation.

The project is split into:

- A **desktop application (UI/UX)** for visualization, calibration, and interaction.
- An **embedded backend (ESP32-S3)** for sensor acquisition and communication over Bluetooth, Wi-Fi, or Serial.

---

## Repository Structure

```text
cardinal-grip/
├─ gui/                      # Desktop UI/UX (front-end app)
├─ ...                       # Other app modules
├─ cardinal-grip-s3/         # ESP32-S3 backend (PlatformIO project)
│  ├─ platformio.ini
│  ├─ src/
│  │  ├─ main.cpp
│  │  └─ firmware/...
│  ├─ include/
│  ├─ .pio/                  # Build artifacts (ignored)
│  └─ .gitignore             # Ignores .pio and credentials.h
└─ README.md
