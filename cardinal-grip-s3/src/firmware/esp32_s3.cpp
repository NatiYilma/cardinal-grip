// src/firmware/esp32_s3.cpp

// Firmware entry for Adafruit Feather ESP32-S3.
// Uses shared logic from esp32_generic.*
//
// Build with env: esp32_s3

#include <Arduino.h>
#include "esp32_generic.h"

#ifndef BOARD_S3
#define BOARD_S3
#endif

// Adafruit ESP32-S3 Feather analog pin labels
// 1) A0 → GPIO18
// 2) A1 → GPIO17
// 3) A2 → GPIO16
// 4) A3 → GPIO15
// 5) A4 → GPIO14

const int fingerPins[NUM_FINGERS] = {18, 17, 16, 15};
// const int fingerPins[NUM_FINGERS] = {A0, A1, A2, A3};

static const uint32_t SAMPLE_INTERVAL_MS = 10;  // ~100 Hz

void setup() {
#if ENABLE_SERIAL
  // Give USB/host a moment on power/reset
  delay(2000);

  Serial.begin(115200);

  // // Optional: wait for host to open the port (helpful for debugging)
  // unsigned long start = millis();
  // while (!Serial && (millis() - start) < 8000UL) {
  //   delay(10);
  // }

  Serial.println();
  Serial.println(F("[BOOT] ESP32-S3 starting up..."));
  cg_printPartitions(); // Info/Debug Partitions

  Serial.println(F("ESP32-S3-Feather"));
#endif

  cg_initStatusLed();
  cg_setSamplingActive(true);   // fast blink = sampling active

  cg_initFsrPins();
  cg_initWiFi();
  cg_initBluetooth();
  cg_initOta();                 // requires Wi-Fi
}

void loop() {
  static uint32_t lastSampleMs = 0;
  const uint32_t now = millis();

  cg_tickTransports();
  cg_tickStatusLed();
  cg_handleOta();               // OTA + HTTP

  if (now - lastSampleMs >= SAMPLE_INTERVAL_MS) {
    lastSampleMs = now;

    FsrSample sample;
    cg_readFsrSample(sample);
    cg_sendSampleAllTransports(sample);
  }

  delay(1);
}