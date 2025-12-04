// src/firmware/credentials_template.h
#pragma once

// ---------------------------------------------------------------------------
// TEMPLATE ONLY
// ---------------------------------------------------------------------------
// 1. Copy this file to: src/firmware/credentials.h
// 2. Replace the placeholder SSID/password with your real dev network
// 3. Make sure src/firmware/credentials.h is listed in .gitignore
//
// Your code should always:
//   #include "credentials.h"
// and then use CG_WIFI_SSID / CG_WIFI_PASSWORD (or cg_wifi_ssid wrapper).
// ---------------------------------------------------------------------------

#define CG_WIFI_SSID      "YOUR_WIFI_SSID_HERE"
#define CG_WIFI_PASSWORD  "YOUR_WIFI_PASSWORD_HERE"
