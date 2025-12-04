## Repository Structure

This repo has two main components:

- **Desktop app (UI/UX)** – primary application code (Python / Qt, etc.)
- **Embedded backend (ESP32-S3)** – firmware and communication pipeline in `cardinal-grip-s3/`

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
