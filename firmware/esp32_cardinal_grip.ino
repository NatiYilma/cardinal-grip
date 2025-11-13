// firmware/esp32_fsr_serial.ino
// Simple ESP32 + FSR test: prints ADC value over Serial.

const int FSR_PIN = 34;   // analog input pin (GPIO34)
const int NUM_SAMPLES = 5;

void setup() {
  Serial.begin(115200);
  delay(1000);            // allow serial to come up
  analogReadResolution(12);   // 0–4095
}

void loop() {
  // simple smoothing
  long sum = 0;
  for (int i = 0; i < NUM_SAMPLES; i++) {
    sum += analogRead(FSR_PIN);
    delay(2);
  }
  int avg = sum / NUM_SAMPLES;

  Serial.println(avg);    // ONE integer per line

  delay(20);              // ~50 Hz
}
