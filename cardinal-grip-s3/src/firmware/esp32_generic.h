// src/firmware/esp32_generic.h

#pragma once

#include <Arduino.h>

// ------------------------------
// Debug / inspection helpers
// ------------------------------
void cg_printPartitions();

// ------------------------------
// FSR CONFIG
// ------------------------------

// Allow override from board files; default to 4 channels
#ifndef NUM_FINGERS
#define NUM_FINGERS 4
#endif

// Each board file must define this:
extern const int fingerPins[NUM_FINGERS];

// ------------------------------
// Feature toggles (can also be set via build_flags if you want)
// ------------------------------
#ifndef ENABLE_SERIAL
#define ENABLE_SERIAL 1
#endif

#ifndef ENABLE_WIFI
#define ENABLE_WIFI 1
#endif

#ifndef ENABLE_BT
#define ENABLE_BT 1
#endif

// Optional status LED (onboard)
#ifndef ENABLE_STATUS_LED
#define ENABLE_STATUS_LED 1
#endif

// ------------------------------
// Data structures
// ------------------------------
struct FsrSample {
  uint32_t timestamp_ms;
  int16_t  values[NUM_FINGERS];
};

// ------------------------------
// Shared API implemented in esp32_generic.cpp
// ------------------------------

// Hardware init
void cg_initFsrPins();
void cg_initWiFi();
void cg_initBluetooth();

// Status LED
void cg_initStatusLed();
void cg_tickStatusLed();
void cg_setSamplingActive(bool active);   // true = fast blink, false = slow

// Per-loop maintenance (e.g. WebSocket loop, OTA, HTTP)
void cg_tickTransports();
void cg_initOta();
void cg_handleOta();

// Sampling + send
void cg_readFsrSample(FsrSample &sample);
void cg_sendSampleSerial(const FsrSample &sample);
void cg_sendSampleWebSocket(const FsrSample &sample);
void cg_sendSampleBluetooth(const FsrSample &sample);
void cg_sendSampleAllTransports(const FsrSample &sample);
