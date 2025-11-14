// firmware/esp32_grip_serial.ino
// Board-agnostic FSR streaming over Serial as CSV: v1,v2,v3,v4

#include <Arduino.h>

// ------------------------------
// SELECT BOARD HERE
// ------------------------------
// Uncomment exactly ONE of these:

// #define BOARD_FEATHER_S3
#define BOARD_GENERIC_ESP32

// ------------------------------
// PIN MAPPING
// ------------------------------

// How many FSR channels you want to read
const int NUM_FINGERS = 4;

#if defined(BOARD_FEATHER_S3)

// Panas: Adafruit Feather ESP32-S3
// FSRs wired to A0..A3
const int fingerPins[NUM_FINGERS] = {A0, A1, A2, A3};

#elif defined(BOARD_GENERIC_ESP32)

// You: generic ESP32 dev board
// FSRs wired to 34, 35, 32, 33 (all ADC-capable)
const int fingerPins[NUM_FINGERS] = {34, 35, 32, 33};

#else
#error "You must define a board type at top of file."
#endif

// ------------------------------
// SERIAL SETTINGS
// ------------------------------
const long BAUD = 115200;   // both of you can use 115200, just match in Python
const unsigned long SAMPLE_INTERVAL_MS = 10;  // ~100 Hz

void setup() {
  Serial.begin(BAUD);
  // Give USB some time on some boards (Feathers/ S3, etc.)
  delay(1000);

  Serial.println(F("# Cardinal Grip FSR streamer"));
  Serial.print(F("# Baud: ")); Serial.println(BAUD);
  Serial.print(F("# Pins: "));
  for (int i = 0; i < NUM_FINGERS; ++i) {
    Serial.print(fingerPins[i]);
    if (i < NUM_FINGERS - 1) Serial.print(",");
  }
  Serial.println();

  // Ensure pins are ready for analog
  for (int i = 0; i < NUM_FINGERS; ++i) {
    pinMode(fingerPins[i], INPUT);
  }
}

void loop() {
  static unsigned long lastSample = 0;
  unsigned long now = millis();

  if (now - lastSample >= SAMPLE_INTERVAL_MS) {
    lastSample = now;

    // Read all FSRs
    int vals[NUM_FINGERS];
    for (int i = 0; i < NUM_FINGERS; ++i) {
      vals[i] = analogRead(fingerPins[i]);  // 0–4095
    }

    // Stream as CSV: "v1,v2,v3,v4"
    for (int i = 0; i < NUM_FINGERS; ++i) {
      Serial.print(vals[i]);
      if (i < NUM_FINGERS - 1) Serial.print(',');
    }
    Serial.println();
  }
}