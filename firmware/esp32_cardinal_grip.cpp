// firmware/esp32_cardinal_grip.cpp
// FUTURE VERSION: Wi-Fi + WebSocket streaming, not used for USB serial demo.

#include <Arduino.h>
#include <WiFi.h>
#include <WebSocketsServer.h>

const char* ssid     = "YOUR_SSID";
const char* password = "YOUR_PASSWORD";

WebSocketsServer webSocket(81);  // ws://<IP>:81

const int NUM_FINGERS = 4;
// const int fingerPins[NUM_FINGERS] = {34, 35, 32, 33}; // adjust later
const int fingerPins[NUM_FINGERS] ={A0, A1, A2, A3};

void webSocketEvent(uint8_t num, WStype_t type, uint8_t * payload, size_t length) {
  // no-op for now
}

void setup() {
  Serial.begin(115200);

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  Serial.print("Connecting to Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());

  webSocket.begin();
  webSocket.onEvent(webSocketEvent);
}

void loop() {
  webSocket.loop();

  int vals[NUM_FINGERS];
  for (int i = 0; i < NUM_FINGERS; i++) {
    vals[i] = analogRead(fingerPins[i]);
  }

  String msg = String(vals[0]);
  for (int i = 1; i < NUM_FINGERS; i++) {
    msg += ",";
    msg += String(vals[i]);
  }

  webSocket.broadcastTXT(msg);
  delay(20);  // ~50 Hz
}
