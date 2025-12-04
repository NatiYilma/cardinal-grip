// src/firmware/esp32_generic.cpp
// ================================

#include "esp32_generic.h"
#include <esp_partition.h>

#if ENABLE_WIFI
  #include "credentials.h"
  #include <WiFi.h>
  #include <WebServer.h>
  #include <WebSocketsServer.h>
  #include <ESPmDNS.h>
  #include <Update.h>
  #include <ArduinoOTA.h>
  #include <Preferences.h>
  static const char* cg_wifi_ssid     = CG_WIFI_SSID;
  static const char* cg_wifi_password = CG_WIFI_PASSWORD;
#endif

#if ENABLE_BT && defined(BOARD_S3)
  #include <BLEDevice.h>
  #include <BLEServer.h>
  #include <BLEUtils.h>
  #include <BLE2902.h>

  // Very simple BLE-UART style setup for S3-only build

  static BLEServer*         cg_bleServer       = nullptr;
  static BLECharacteristic* cg_bleTxChar       = nullptr;
  static bool               cg_bleConnected    = false;
  static bool               cg_bleWasConnected = false;

  // Custom UUIDs (Can be changed)
  static constexpr char CG_BLE_SERVICE_UUID[] = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E";
  static constexpr char CG_BLE_TX_CHAR_UUID[] = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"; // notify-only

  class CgBleServerCallbacks : public BLEServerCallbacks {
  public:
    void onConnect(BLEServer* /*pServer*/) override {
      cg_bleConnected = true;
    }
    void onDisconnect(BLEServer* /*pServer*/) override {
      cg_bleConnected = false;
    }
  };
#endif

// ==========================================================
// BOARD / PARTITION INFO (debug helper)
// ==========================================================
void cg_printPartitions() {
#if ENABLE_SERIAL
  const esp_partition_t *p = nullptr;

  Serial.println();
  Serial.println(F("===== App partitions ====="));
  esp_partition_iterator_t it_app =
    esp_partition_find(ESP_PARTITION_TYPE_APP,
                       ESP_PARTITION_SUBTYPE_ANY,
                       nullptr);

  while (it_app) {
    p = esp_partition_get(it_app);
    Serial.printf("  label=%s type=%d subtype=%d addr=0x%06lx size=%lu bytes\n",
                  p->label,
                  p->type,
                  p->subtype,
                  (unsigned long)p->address,
                  (unsigned long)p->size);
    it_app = esp_partition_next(it_app);
  }
  esp_partition_iterator_release(it_app);

  Serial.println(F("===== Data partitions ====="));
  esp_partition_iterator_t it_data =
    esp_partition_find(ESP_PARTITION_TYPE_DATA,
                       ESP_PARTITION_SUBTYPE_ANY,
                       nullptr);

  while (it_data) {
    p = esp_partition_get(it_data);
    Serial.printf("  label=%s type=%d subtype=%d addr=0x%06lx size=%lu bytes\n",
                  p->label,
                  p->type,
                  p->subtype,
                  (unsigned long)p->address,
                  (unsigned long)p->size);
    it_data = esp_partition_next(it_data);
  }
  esp_partition_iterator_release(it_data);

  Serial.println();
#endif
}

// ==========================================================
// STATUS LED IMPLEMENTATION
// ==========================================================
#if ENABLE_STATUS_LED

// Adjust these if the boards use different LED pins
#if defined(BOARD_32D)
static const int STATUS_LED_PIN = 2;     // typical ESP32 devkit LED
#elif defined(BOARD_S3)
static const int STATUS_LED_PIN = 13;    // Feather ESP32-S3 "LED" pin
#else
static const int STATUS_LED_PIN = -1;    // no LED
#endif

static bool     g_samplingActive    = true;   // fast (true) vs slow (false) blink
static uint32_t g_ledLastToggleMs   = 0;
static bool     g_ledIsOn           = false;

// Simple helper for "event" patterns (Wi-Fi / BT / OTA / error)
static void cg_ledBlinkNTimes(uint8_t n, uint16_t onMs, uint16_t offMs) {
  if (STATUS_LED_PIN < 0) return;
  for (uint8_t i = 0; i < n; ++i) {
    digitalWrite(STATUS_LED_PIN, HIGH);
    delay(onMs);
    digitalWrite(STATUS_LED_PIN, LOW);
    delay(offMs);
  }
}

#endif  // ENABLE_STATUS_LED

void cg_initStatusLed() {
#if ENABLE_STATUS_LED
  if (STATUS_LED_PIN >= 0) {
    pinMode(STATUS_LED_PIN, OUTPUT);
    digitalWrite(STATUS_LED_PIN, LOW);
    g_ledLastToggleMs = millis();
    g_ledIsOn = false;
  }
#endif
}

void cg_setSamplingActive(bool active) {
#if ENABLE_STATUS_LED
  g_samplingActive = active;
#else
  (void)active;
#endif
}

void cg_tickStatusLed() {
#if ENABLE_STATUS_LED
  if (STATUS_LED_PIN < 0) return;

  const uint32_t now      = millis();
  const uint32_t interval = g_samplingActive ? 200u : 800u;  // fast vs slow

  if (now - g_ledLastToggleMs >= interval) {
    g_ledLastToggleMs = now;
    g_ledIsOn = !g_ledIsOn;
    digitalWrite(STATUS_LED_PIN, g_ledIsOn ? HIGH : LOW);
  }
#endif
}

// ==========================================================
// WIFI / WEBSOCKET / HTTP SERVER / OTA CONFIG
// ==========================================================
#if ENABLE_WIFI

// ---- Wi-Fi credentials ----
//
// 1) Compile-time defaults from credentials.h
// 2) Optional stored credentials in NVS ("wifi" namespace)
//    - If present, we prefer stored over compile-time.
//    - You can change them from the /wifi config page.

static const char* cg_default_wifi_ssid     = CG_WIFI_SSID;
static const char* cg_default_wifi_password = CG_WIFI_PASSWORD;

// If STA fails, we fall back to AP mode with these:
static const char* cg_ap_ssid       = "CardinalGrip_AP";
static const char* cg_ap_password   = "SqueezyPeasy1";   // 8+ chars required

// WebSocket for streaming sample data
static WebSocketsServer cg_webSocket(81);   // ws://<ip>:81

// HTTP server for OTA web UI + Wi-Fi config
static WebServer cg_httpServer(80);

// Track whether Wi-Fi is up (STA or AP)
static bool cg_wifi_ready = false;

// NVS storage for Wi-Fi credentials
static Preferences cg_wifiPrefs;
static bool        cg_haveStoredWifi = false;
static String      cg_storedSsid;
static String      cg_storedPass;

// Forward declarations for HTTP handlers
static void cg_handleHttpRoot();
static void cg_handleHttpUpdatePage();
static void cg_handleHttpUpdatePost();
static void cg_handleHttpUpdateUpload();

// Wi-Fi config HTML handlers
static void cg_handleHttpWifiPage();
static void cg_handleHttpWifiPost();
static void cg_handleHttpWifiForget();

// JSON API endpoints for Qt / PC integration
static void cg_handleApiWifiStatus();
static void cg_handleApiWifiScan();
static void cg_handleApiWifiConfig();
static void cg_handleApiWifiForget();

// WebSocket event (extend later for commands if needed)
static void cg_webSocketEvent(uint8_t num, WStype_t type,
                              uint8_t * payload, size_t length) {
  (void)num;
  (void)type;
  (void)payload;
  (void)length;
}

// ----------------------------------------------------------
// Wi-Fi event logger (AP STA connect/disconnect etc.)
// ----------------------------------------------------------
static void cg_wifiEvent(WiFiEvent_t event) {
#if ENABLE_SERIAL
  switch (event) {
    case ARDUINO_EVENT_WIFI_AP_START:
      Serial.println(F("[WiFi] EVENT: AP started"));
      break;
    case ARDUINO_EVENT_WIFI_AP_STOP:
      Serial.println(F("[WiFi] EVENT: AP stopped"));
      break;
    case ARDUINO_EVENT_WIFI_AP_STACONNECTED:
      Serial.println(F("[WiFi] EVENT: Station connected to AP"));
      break;
    case ARDUINO_EVENT_WIFI_AP_STADISCONNECTED:
      Serial.println(F("[WiFi] EVENT: Station disconnected from AP"));
      break;
    case ARDUINO_EVENT_WIFI_AP_PROBEREQRECVED:
      Serial.println(F("[WiFi] EVENT: AP probe request received"));
      break;
    default:
      Serial.print(F("[WiFi] EVENT: "));
      Serial.println((int)event);
      break;
  }
#endif
}

// ----------------------------------------------------------
// Stored Wi-Fi helpers
// ----------------------------------------------------------
static void cg_loadStoredWifi() {
  cg_haveStoredWifi = false;
  cg_storedSsid = "";
  cg_storedPass = "";

  if (!cg_wifiPrefs.begin("wifi", false)) {
#if ENABLE_SERIAL
    Serial.println(F("[WiFi] Preferences begin() failed"));
#endif
    return;
  }

  cg_storedSsid = cg_wifiPrefs.getString("ssid", "");
  cg_storedPass = cg_wifiPrefs.getString("pass", "");

  // Close the namespace so later begin() calls (save/clear) succeed
  cg_wifiPrefs.end();

  cg_haveStoredWifi = (cg_storedSsid.length() > 0);

#if ENABLE_SERIAL
  if (cg_haveStoredWifi) {
    Serial.print(F("[WiFi] Found stored SSID: "));
    Serial.println(cg_storedSsid);
  } else {
    Serial.println(F("[WiFi] No stored Wi-Fi credentials"));
  }
#endif
}

static void cg_saveStoredWifi(const String& ssid, const String& pass) {
  if (!cg_wifiPrefs.begin("wifi", false)) {
#if ENABLE_SERIAL
    Serial.println(F("[WiFi] Preferences begin() failed (save)"));
#endif
    return;
  }

  cg_wifiPrefs.putString("ssid", ssid);
  cg_wifiPrefs.putString("pass", pass);
  cg_wifiPrefs.end();

#if ENABLE_SERIAL
  Serial.print(F("[WiFi] Saved Wi-Fi SSID: "));
  Serial.println(ssid);
#endif
}

static void cg_clearStoredWifi() {
  if (!cg_wifiPrefs.begin("wifi", false)) {
#if ENABLE_SERIAL
    Serial.println(F("[WiFi] Preferences begin() failed (clear)"));
#endif
    return;
  }

  cg_wifiPrefs.clear();
  cg_wifiPrefs.end();

  cg_haveStoredWifi = false;
  cg_storedSsid = "";
  cg_storedPass = "";

#if ENABLE_SERIAL
  Serial.println(F("[WiFi] Cleared stored Wi-Fi credentials"));
#endif
}

// ==========================================================
// WIFI INIT – AP always on, STA best-effort
// Priority:
//   1) Stored credentials in NVS (user-provided)
//   2) Compile-time defaults (DEV ONLY, optional)
//   3) AP-only if nothing to try
// Also starts WebSocket, HTTP server, and mDNS.
// ==========================================================
void cg_initWiFi() {
#if ENABLE_WIFI
  cg_wifi_ready = false;

#if ENABLE_SERIAL
  Serial.println(F("[WiFi] === WIFI INIT (AP + optional STA) ==="));
#endif

  // Log AP/STA events
  WiFi.onEvent(cg_wifiEvent);

  // Clean slate
  WiFi.persistent(false);
  WiFi.disconnect(true, true);

  // AP + STA
  WiFi.mode(WIFI_AP_STA);

  // ---------- Start AP (always) ----------
#if ENABLE_SERIAL
  Serial.print(F("[WiFi] Starting AP: "));
  Serial.println(cg_ap_ssid);
#endif

  // Channel 1, visible SSID, up to 4 clients
  bool ap_ok = WiFi.softAP(cg_ap_ssid, cg_ap_password, 1, 0, 4);
  if (!ap_ok) {
#if ENABLE_SERIAL
    Serial.println(F("[WiFi] softAP() FAILED; Wi-Fi will be unavailable."));
#endif
    return;  // nothing else to do
  }

  delay(300);

#if ENABLE_SERIAL
  Serial.print(F("[WiFi] AP IP: "));
  Serial.println(WiFi.softAPIP());
#endif

  // ---------- Decide which STA credentials to try ----------
  cg_loadStoredWifi();   // may set cg_haveStoredWifi + cg_storedSsid/pass

  String staSsid;
  String staPass;

  if (cg_haveStoredWifi) {
    // 1) User-provided, stored in NVS
    staSsid = cg_storedSsid;
    staPass = cg_storedPass;
#if ENABLE_SERIAL
    Serial.print(F("[WiFi] Using STORED SSID: "));
    Serial.println(staSsid);
#endif
  } else {
    // 2) DEV-ONLY fallback: compile-time defaults
    //    For production builds, you can set these to template values
    //    so this branch effectively does nothing.
    if (cg_default_wifi_ssid && strlen(cg_default_wifi_ssid) > 0 &&
        strcmp(cg_default_wifi_ssid, "YOUR_WIFI_SSID_HERE") != 0) {
      staSsid = String(cg_default_wifi_ssid);
      staPass = String(cg_default_wifi_password);
#if ENABLE_SERIAL
      Serial.print(F("[WiFi] Using DEFAULT compile-time SSID (DEV): "));
      Serial.println(staSsid);
#endif
    } else {
#if ENABLE_SERIAL
      Serial.println(F("[WiFi] No stored creds and no valid dev default; STA will be skipped."));
#endif
    }
  }

  // ---------- Try STA connect (if we have something to try) ----------
  if (staSsid.length() > 0) {
#if ENABLE_SERIAL
    Serial.print(F("[WiFi] Connecting as STA to SSID: "));
    Serial.println(staSsid);
#endif

    WiFi.begin(staSsid.c_str(), staPass.c_str());

    unsigned long start      = millis();
    const unsigned long tout = 8000UL;   // 8s max

    while (WiFi.status() != WL_CONNECTED && (millis() - start) < tout) {
      delay(250);
#if ENABLE_SERIAL
      Serial.print('.');
#endif
    }

#if ENABLE_SERIAL
    Serial.println();
    wl_status_t st = WiFi.status();
    Serial.print(F("[WiFi] STA status after attempt: "));
    Serial.print((int)st);
    Serial.print(F(" ("));
    switch (st) {
      case WL_IDLE_STATUS:     Serial.print(F("IDLE")); break;
      case WL_NO_SSID_AVAIL:   Serial.print(F("NO SSID")); break;
      case WL_SCAN_COMPLETED:  Serial.print(F("SCAN COMPLETE")); break;
      case WL_CONNECTED:       Serial.print(F("CONNECTED")); break;
      case WL_CONNECT_FAILED:  Serial.print(F("CONNECT FAILED")); break;
      case WL_CONNECTION_LOST: Serial.print(F("CONNECTION LOST")); break;
      case WL_DISCONNECTED:    Serial.print(F("DISCONNECTED")); break;
      default:                 Serial.print(F("UNKNOWN")); break;
    }
    Serial.println(F(")"));

    Serial.println(F("[WiFi] WiFi.printDiag():"));
    WiFi.printDiag(Serial);
#endif
  } else {
#if ENABLE_SERIAL
    Serial.println(F("[WiFi] Skipping STA connect (no credentials)."));
#endif
  }

  // At this point AP is definitely up; STA may or may not be.
  cg_wifi_ready = true;

  // ---------- Start WebSocket + HTTP server ----------
  cg_webSocket.begin();
  cg_webSocket.onEvent(cg_webSocketEvent);

  cg_httpServer.on("/", HTTP_GET, cg_handleHttpRoot);
  cg_httpServer.on("/update", HTTP_GET, cg_handleHttpUpdatePage);
  cg_httpServer.on("/update", HTTP_POST,
                   cg_handleHttpUpdatePost,
                   cg_handleHttpUpdateUpload);

  // Wi-Fi config endpoints (HTML portal)
  cg_httpServer.on("/wifi",        HTTP_GET,  cg_handleHttpWifiPage);
  cg_httpServer.on("/wifi",        HTTP_POST, cg_handleHttpWifiPost);
  cg_httpServer.on("/wifi/forget", HTTP_POST, cg_handleHttpWifiForget);

  // JSON Wi-Fi API for Qt / PC app
  cg_httpServer.on("/api/wifi/status", HTTP_GET,  cg_handleApiWifiStatus);
  cg_httpServer.on("/api/wifi/scan",   HTTP_GET,  cg_handleApiWifiScan);
  cg_httpServer.on("/api/wifi/config", HTTP_POST, cg_handleApiWifiConfig);
  cg_httpServer.on("/api/wifi/forget", HTTP_POST, cg_handleApiWifiForget);

  cg_httpServer.onNotFound([]() {
    cg_httpServer.send(404, "text/plain", "Not found");
  });

  cg_httpServer.begin();

#if ENABLE_SERIAL
  Serial.println(F("[WiFi] HTTP/WebSocket servers started"));
#endif

  // ---------- mDNS (only if STA connected) ----------
  if (WiFi.status() == WL_CONNECTED) {
    if (MDNS.begin("cardinal-grip")) {
#if ENABLE_SERIAL
      Serial.println(F("[mDNS] Service started as cardinal-grip.local"));
#endif
      MDNS.addService("http",    "tcp", 80);
      MDNS.addService("ws",      "tcp", 81);
      MDNS.addService("arduino", "tcp", 3232);
    } else {
#if ENABLE_SERIAL
      Serial.println(F("[mDNS] Failed to start mDNS (STA)"));
#endif
    }
  } else {
#if ENABLE_SERIAL
    Serial.println(F("[mDNS] Skipping mDNS (STA not connected)"));
#endif
  }

#if ENABLE_SERIAL
  Serial.println(F("[WiFi] === WIFI INIT COMPLETE ==="));
#endif

#endif // ENABLE_WIFI
}

// (Old cg_initWiFi() retained here as commented reference)
// void cg_initWiFi() {
//   ...
// }

// ==========================================================
// HTTP HANDLERS (WEB-BASED OTA UI + Wi-Fi config)
// ==========================================================

// Simple landing page
static void cg_handleHttpRoot() {
  String page =
    "<!DOCTYPE html><html><head><title>Cardinal Grip</title></head><body>"
    "<h1>Cardinal Grip ESP32</h1>"
    "<p>Firmware streaming is active.</p>";

  // Show Wi-Fi status
  if (WiFi.getMode() & WIFI_STA) {
    if (WiFi.status() == WL_CONNECTED) {
      page += "<p>Mode: STA, SSID: " + WiFi.SSID() + "</p>";
      page += "<p>IP: " + WiFi.localIP().toString() + "</p>";
    } else {
      page += "<p>Mode: STA, not connected</p>";
    }
  }
  if (WiFi.getMode() & WIFI_AP) {
    page += "<p>AP SSID: ";
    page += cg_ap_ssid;
    page += " (IP: ";
    page += WiFi.softAPIP().toString();
    page += ")</p>";
  }

  page +=
    "<p><a href=\"/wifi\">Wi-Fi Setup</a></p>"
    "<p><a href=\"/update\">Firmware Update</a></p>"
    "</body></html>";

  cg_httpServer.send(200, "text/html", page);
}

// Firmware update form
static void cg_handleHttpUpdatePage() {
  String page =
    "<!DOCTYPE html><html><head><title>OTA Update</title></head><body>"
    "<h1>Firmware OTA Update</h1>"
    "<form method='POST' action='/update' enctype='multipart/form-data'>"
    "<input type='file' name='firmware'>"
    "<input type='submit' value='Update'>"
    "</form>"
    "<p><a href=\"/\">Back</a></p>"
    "</body></html>";
  cg_httpServer.send(200, "text/html", page);
}

// Called after upload end
static void cg_handleHttpUpdatePost() {
  bool ok = !Update.hasError();
  cg_httpServer.sendHeader("Connection", "close");
  cg_httpServer.send(200, "text/plain", ok ? "OK" : "FAIL");

#if ENABLE_SERIAL
  Serial.println(ok ? F("[HTTP OTA] Update successful, restarting soon")
                    : F("[HTTP OTA] Update failed"));
#endif

#if ENABLE_STATUS_LED
  if (ok) {
    cg_ledBlinkNTimes(2, 160, 160);
  } else {
    cg_ledBlinkNTimes(5, 80, 80);
  }
#endif

  // Allow some time for client to receive response
  delay(1000);
  if (ok) {
    ESP.restart();
  }
}

// Upload handler
static void cg_handleHttpUpdateUpload() {
  HTTPUpload& upload = cg_httpServer.upload();

  if (upload.status == UPLOAD_FILE_START) {
#if ENABLE_SERIAL
    Serial.printf("[HTTP OTA] Upload start: %s\n", upload.filename.c_str());
#endif
#if ENABLE_STATUS_LED
    cg_ledBlinkNTimes(4, 80, 80);   // indicate OTA start
#endif

    // Compute max available space for new sketch
    size_t maxSketchSpace = (ESP.getFreeSketchSpace() - 0x1000) & 0xFFFFF000;
    if (!Update.begin(maxSketchSpace)) {
#if ENABLE_SERIAL
      Serial.println(F("[HTTP OTA] Update.begin() failed"));
#endif
    }
  } else if (upload.status == UPLOAD_FILE_WRITE) {
    // Flash write
    if (Update.write(upload.buf, upload.currentSize) != upload.currentSize) {
#if ENABLE_SERIAL
      Serial.println(F("[HTTP OTA] Write error"));
#endif
    }
  } else if (upload.status == UPLOAD_FILE_END) {
    if (Update.end(true)) {
#if ENABLE_SERIAL
      Serial.printf("[HTTP OTA] Update Success: %u bytes\n", upload.totalSize);
#endif
    } else {
#if ENABLE_SERIAL
      Serial.println(F("[HTTP OTA] Update.end() failed"));
#endif
    }
  } else if (upload.status == UPLOAD_FILE_ABORTED) {
    Update.end();
#if ENABLE_SERIAL
    Serial.println(F("[HTTP OTA] Upload aborted"));
#endif
#if ENABLE_STATUS_LED
    cg_ledBlinkNTimes(5, 80, 80);
#endif
  }
}

// ----------------------------------------------------------
// Wi-Fi config portal handlers (HTML)
// ----------------------------------------------------------

// Show scan results + form
static void cg_handleHttpWifiPage() {
  String page =
    "<!DOCTYPE html><html><head><title>Wi-Fi Setup</title></head><body>"
    "<h1>Wi-Fi Setup</h1>";

  // Current status
  if (WiFi.getMode() & WIFI_STA) {
    if (WiFi.status() == WL_CONNECTED) {
      page += "<p>Current STA: " + WiFi.SSID() + " (";
      page += WiFi.localIP().toString();
      page += ")</p>";
    } else {
      page += "<p>STA not connected.</p>";
    }
  }

  // Scan for networks
  page += "<h2>Available Networks</h2>";
  int n = WiFi.scanNetworks();
  if (n <= 0) {
    page += "<p>No networks found (try again).</p>";
  } else {
    page += "<form method='POST' action='/wifi'>";
    page += "<p>Select SSID:</p>";
    for (int i = 0; i < n; ++i) {
      String s = WiFi.SSID(i);
      int32_t rssi = WiFi.RSSI(i);
      page += "<label>";
      page += "<input type='radio' name='ssid' value='" + s + "'>";
      page += s + " (RSSI " + String(rssi) + " dBm)";
      if (WiFi.encryptionType(i) != WIFI_AUTH_OPEN) {
        page += " 🔒";
      }
      page += "</label><br>";
    }
    page += "<p>Password: <input type='password' name='password'></p>";
    page += "<p><input type='submit' value='Save & Reboot'></p>";
    page += "</form>";
  }

  // Forget stored creds
  page += "<h2>Stored Credentials</h2>";
  if (cg_haveStoredWifi) {
    page += "<p>Stored SSID: " + cg_storedSsid + "</p>";
    page += "<form method='POST' action='/wifi/forget'>"
            "<input type='submit' value='Forget Stored Wi-Fi'>"
            "</form>";
  } else {
    page += "<p>No stored Wi-Fi.</p>";
  }

  page += "<p><a href=\"/\">Back</a></p>";
  page += "</body></html>";

  cg_httpServer.send(200, "text/html", page);
}

// Handle "Save & Reboot"
static void cg_handleHttpWifiPost() {
  String ssid     = cg_httpServer.arg("ssid");
  String password = cg_httpServer.arg("password");

  if (ssid.length() == 0) {
    cg_httpServer.send(400, "text/plain", "SSID required");
    return;
  }

  cg_saveStoredWifi(ssid, password);

  cg_httpServer.send(
    200,
    "text/html",
    "<!DOCTYPE html><html><body>"
    "<p>Saved Wi-Fi credentials for SSID: " + ssid + "</p>"
    "<p>Device will reboot and try to connect.</p>"
    "</body></html>"
  );

  delay(1000);
  ESP.restart();
}

// Handle "Forget"
static void cg_handleHttpWifiForget() {
  cg_clearStoredWifi();
  cg_httpServer.send(
    200,
    "text/html",
    "<!DOCTYPE html><html><body>"
    "<p>Stored Wi-Fi credentials cleared.</p>"
    "<p><a href=\"/wifi\">Back to Wi-Fi Setup</a></p>"
    "</body></html>"
  );
}

// ----------------------------------------------------------
// JSON Wi-Fi API for Qt / desktop app
// ----------------------------------------------------------

// Helper to JSON-encode a string without quotes escaping (simplified).
// NOTE: SSIDs with quotes are rare; if you hit one, this may break JSON.
static String cg_jsonEscape(const String &s) {
  String out;
  out.reserve(s.length() + 4);
  for (size_t i = 0; i < s.length(); ++i) {
    char c = s[i];
    if (c == '"' || c == '\\') {
      out += '\\';
      out += c;
    } else if (c == '\n') {
      out += "\\n";
    } else if (c == '\r') {
      out += "\\r";
    } else {
      out += c;
    }
  }
  return out;
}

// GET /api/wifi/status
static void cg_handleApiWifiStatus() {
  uint8_t mode = WiFi.getMode();
  String modeStr;
  if (mode == WIFI_OFF)          modeStr = "off";
  else if (mode == WIFI_STA)     modeStr = "sta";
  else if (mode == WIFI_AP)      modeStr = "ap";
  else if (mode == WIFI_AP_STA)  modeStr = "ap_sta";
  else                           modeStr = "unknown";

  bool staConnected = (WiFi.status() == WL_CONNECTED);

  String json = "{";
  json += "\"mode\":\"" + modeStr + "\"";
  json += ",\"sta_connected\":"; json += staConnected ? "true" : "false";

  if (staConnected) {
    json += ",\"sta_ssid\":\"" + cg_jsonEscape(WiFi.SSID()) + "\"";
    json += ",\"sta_ip\":\"" + WiFi.localIP().toString() + "\"";
  }

  if (mode & WIFI_AP) {
    json += ",\"ap_ssid\":\"" + cg_jsonEscape(String(cg_ap_ssid)) + "\"";
    json += ",\"ap_ip\":\"" + WiFi.softAPIP().toString() + "\"";
  }

  if (cg_haveStoredWifi) {
    json += ",\"stored_ssid\":\"" + cg_jsonEscape(cg_storedSsid) + "\"";
  } else {
    json += ",\"stored_ssid\":null";
  }

  json += "}";
  cg_httpServer.send(200, "application/json", json);
}

// GET /api/wifi/scan
static void cg_handleApiWifiScan() {
  int n = WiFi.scanNetworks();
  String json = "[";

  for (int i = 0; i < n; ++i) {
    if (i > 0) json += ",";
    String ssid = WiFi.SSID(i);
    int32_t rssi = WiFi.RSSI(i);
    wifi_auth_mode_t enc = WiFi.encryptionType(i);

    json += "{";
    json += "\"ssid\":\"" + cg_jsonEscape(ssid) + "\"";
    json += ",\"rssi\":" + String(rssi);
    json += ",\"secure\":"; json += (enc == WIFI_AUTH_OPEN ? "false" : "true");
    json += "}";
  }

  json += "]";
  cg_httpServer.send(200, "application/json", json);
}

// POST /api/wifi/config  (form fields: ssid, password)
static void cg_handleApiWifiConfig() {
  String ssid     = cg_httpServer.arg("ssid");
  String password = cg_httpServer.arg("password");

  if (ssid.length() == 0) {
    cg_httpServer.send(
      400, "application/json",
      "{\"status\":\"error\",\"error\":\"ssid_required\"}"
    );
    return;
  }

  cg_saveStoredWifi(ssid, password);

  String json = "{\"status\":\"ok\",\"ssid\":\"";
  json += cg_jsonEscape(ssid);
  json += "\"}";

  cg_httpServer.send(200, "application/json", json);

#if ENABLE_SERIAL
  Serial.print(F("[WiFi] API config: saved SSID: "));
  Serial.println(ssid);
#endif

  delay(800);
  ESP.restart();
}

// POST /api/wifi/forget
static void cg_handleApiWifiForget() {
  cg_clearStoredWifi();
  cg_httpServer.send(200, "application/json", "{\"status\":\"ok\"}");

#if ENABLE_SERIAL
  Serial.println(F("[WiFi] API forget: cleared stored Wi-Fi"));
#endif
}

#endif  // ENABLE_WIFI

// ==========================================================
// BLUETOOTH CONFIG
// ==========================================================
#if ENABLE_BT && defined(BOARD_32D)
// 32D -> Bluetooth Classic (SPP) only, used for streaming CSV for now.
static BluetoothSerial SerialBT;
#endif

// ==========================================================
// FSR PINS INIT
// ==========================================================
void cg_initFsrPins() {
  for (int i = 0; i < NUM_FINGERS; ++i) {
    pinMode(fingerPins[i], INPUT);
  }
}

// ==========================================================
// BLUETOOTH INIT (BLE)
// ==========================================================
void cg_initBluetooth() {
#if ENABLE_BT && defined(BOARD_S3)
  // Initialize BLE stack
  BLEDevice::init("CardinalGrip_S3");

  cg_bleServer = BLEDevice::createServer();
  cg_bleServer->setCallbacks(new CgBleServerCallbacks());

  BLEService* service = cg_bleServer->createService(CG_BLE_SERVICE_UUID);

  cg_bleTxChar = service->createCharacteristic(
    CG_BLE_TX_CHAR_UUID,
    BLECharacteristic::PROPERTY_NOTIFY
  );

  // Add CCC descriptor so clients can enable notifications
  cg_bleTxChar->addDescriptor(new BLE2902());

  service->start();

  BLEAdvertising* advertising = BLEDevice::getAdvertising();
  advertising->addServiceUUID(CG_BLE_SERVICE_UUID);
  advertising->setScanResponse(true);
  advertising->setMinPreferred(0x06);
  advertising->setMaxPreferred(0x12);
  advertising->start();

#if ENABLE_SERIAL
  Serial.println(F("[BLE] S3 BLE UART started (CardinalGrip_S3)"));
#endif
#if ENABLE_STATUS_LED
  // Triple blink to indicate BT/BLE is ready
  cg_ledBlinkNTimes(3, 120, 120);
#endif
#else
  // BT disabled or not S3; do nothing
#endif
}

// ==========================================================
// OTA INIT (ArduinoOTA + HTTP-based OTA)
// ==========================================================
void cg_initOta() {
#if ENABLE_WIFI
  if (!cg_wifi_ready) {
#if ENABLE_SERIAL
    Serial.println(F("[OTA] Skipping OTA init (no Wi-Fi)."));
#endif
    return;
  }

#if ENABLE_SERIAL
  Serial.println(F("[OTA] Initializing ArduinoOTA..."));
#endif

  ArduinoOTA.setHostname("cardinal-grip");

  ArduinoOTA.onStart([]() {
#if ENABLE_SERIAL
    Serial.println(F("[OTA] Start"));
#endif
#if ENABLE_STATUS_LED
    // Indicate OTA start: 4 quick blinks
    cg_ledBlinkNTimes(4, 80, 80);
#endif
  });

  ArduinoOTA.onEnd([]() {
#if ENABLE_SERIAL
    Serial.println(F("\n[OTA] End"));
#endif
#if ENABLE_STATUS_LED
    // 2 slower blinks to indicate successful OTA completion
    cg_ledBlinkNTimes(2, 160, 160);
#endif
  });

  ArduinoOTA.onError([](ota_error_t error) {
#if ENABLE_SERIAL
    Serial.printf("[OTA] Error[%u]: ", error);
    if      (error == OTA_AUTH_ERROR)    Serial.println("Auth Failed");
    else if (error == OTA_BEGIN_ERROR)   Serial.println("Begin Failed");
    else if (error == OTA_CONNECT_ERROR) Serial.println("Connect Failed");
    else if (error == OTA_RECEIVE_ERROR) Serial.println("Receive Failed");
    else if (error == OTA_END_ERROR)     Serial.println("End Failed");
#endif
#if ENABLE_STATUS_LED
    // Error: rapid 5-blink
    cg_ledBlinkNTimes(5, 80, 80);
#endif
  });

  ArduinoOTA.begin();

#if ENABLE_SERIAL
  Serial.println(F("[OTA] ArduinoOTA ready"));
#endif

#else
  // OTA over Wi-Fi not available if Wi-Fi is disabled
#endif
}

// ==========================================================
// TRANSPORT LOOP TICK
// ==========================================================
void cg_tickTransports() {
#if ENABLE_WIFI
  cg_webSocket.loop();
#endif

#if ENABLE_BT && defined(BOARD_S3)
  // Simple reconnect logic: restart advertising after disconnect
  if (!cg_bleConnected && cg_bleWasConnected && cg_bleServer) {
    delay(500);
    BLEDevice::getAdvertising()->start();
    cg_bleWasConnected = cg_bleConnected;
  }
  if (cg_bleConnected && !cg_bleWasConnected) {
    cg_bleWasConnected = cg_bleConnected;
  }
#endif
}

// ==========================================================
// OTA LOOP HANDLER (ArduinoOTA + HTTP server)
// ==========================================================
void cg_handleOta() {
#if ENABLE_WIFI
  if (!cg_wifi_ready) return;
  ArduinoOTA.handle();
  cg_httpServer.handleClient();
#else
  // No Wi-Fi = no OTA
#endif
}

// ==========================================================
// SAMPLE READING
// ==========================================================
void cg_readFsrSample(FsrSample &sample) {
  sample.timestamp_ms = millis();
  for (int i = 0; i < NUM_FINGERS; ++i) {
    sample.values[i] = analogRead(fingerPins[i]);
  }
}

// ==========================================================
// SEND HELPERS
// ==========================================================
void cg_sendSampleSerial(const FsrSample &sample) {
#if ENABLE_SERIAL
  // Match the Python fsr_reader.py file(s): CSV values only
  for (int i = 0; i < NUM_FINGERS; ++i) {
    Serial.print(sample.values[i]);
    if (i < NUM_FINGERS - 1) Serial.print(',');
  }
  Serial.println();
#else
  (void)sample;
#endif
}

void cg_sendSampleWebSocket(const FsrSample &sample) {
#if ENABLE_WIFI
  String msg;
  msg.reserve(NUM_FINGERS * 6);

  msg += sample.values[0];
  for (int i = 1; i < NUM_FINGERS; ++i) {
    msg += ",";
    msg += sample.values[i];
  }

  cg_webSocket.broadcastTXT(msg);
#else
  (void)sample;
#endif
}

void cg_sendSampleBluetooth(const FsrSample &sample) {
#if ENABLE_BT && defined(BOARD_S3)
  if (!cg_bleConnected || !cg_bleTxChar) {
    return;
  }

  // Format as CSV: v0,v1,v2,v3
  char buf[64];
  int  len = 0;

  for (int i = 0; i < NUM_FINGERS; ++i) {
    int written = snprintf(
      buf + len,
      sizeof(buf) - len,
      (i == 0) ? "%d" : ",%d",
      sample.values[i]
    );
    if (written < 0) break;
    len += written;
    if (len >= (int)sizeof(buf)) {
      len = sizeof(buf) - 1;
      break;
    }
  }

  cg_bleTxChar->setValue((uint8_t*)buf, len);
  cg_bleTxChar->notify();
#else
  (void)sample;
#endif
}

void cg_sendSampleAllTransports(const FsrSample &sample) {
  cg_sendSampleSerial(sample);
  cg_sendSampleWebSocket(sample);
  cg_sendSampleBluetooth(sample);
}
