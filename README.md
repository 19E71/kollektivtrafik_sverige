# Kollektivtrafik Sverige – Home Assistant Integration

![Version](https://img.shields.io/github/v/release/19E71/Kollektivtrafik_Sverige)
![License](https://img.shields.io/badge/license-MPL--2.0-green)
![HACS](https://img.shields.io/badge/HACS-Custom-orange)
![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)
![Last Updated](https://img.shields.io/github/last-commit/19E71/Kollektivtrafik_Sverige)
![Issues](https://img.shields.io/github/issues/19E71/Kollektivtrafik_Sverige)
![Stars](https://img.shields.io/github/stars/19E71/Kollektivtrafik_Sverige)

A clean, modern Home Assistant integration for **Swedish public transport realtime departures**, powered by the **Trafiklab Realtime APIs**.  
Designed for simplicity, reliability, and nationwide coverage — without the legacy complexity of older HASL‑style integrations.

This integration is **community‑developed** and not affiliated with Trafiklab or Samtrafiken.

---

# 🚍 Features

- **Realtime departures** from any Trafiklab-supported stop in Sweden  
- **Five departure sensors per stop** (next 5 departures)  
- **Line filtering** (e.g., `1, 4, 42X`)  
- **Direction filtering** (`0`, `1`, or empty for both)  
- **Optional time windows** (e.g., `06:00-10:00, 16:00-22:00`)  
- **Minimal API usage** (safe for Trafiklab quotas)  
- **Modern Home Assistant config flow**  
- **Clean, predictable entity naming**  
- **No YAML required**  
- **No arrivals, no ResRobot, no stop lookup service, no bloat**  

---

# 📦 Installation

## HACS (Recommended)

1. Open **HACS → Integrations**
2. Add this repository as a **Custom Repository**
3. Search for **Kollektivtrafik Sverige**
4. Install
5. Restart Home Assistant

## Manual Installation

1. Copy the folder: **custom_components/kollektivtrafik_sverige** into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.

---

# 🔑 Getting Your Trafiklab API Key

You need a **Trafiklab Realtime API key**.

### Step 1 — Create a Trafiklab project  
https://developer.trafiklab.se/project/list

### Step 2 — Inside your project, create an API key  
After creating a project:

1. Open your project  
2. Scroll to **API Keys**  
3. Click **Create Key**  
4. Select **Trafiklab Realtime APIs**  
5. Save the key

This is the key you enter in Home Assistant.

### Step 3 — (Optional) Read about the API  
Documentation only (not where you create keys):  
https://www.trafiklab.se/api/our-apis/trafiklab-realtime-apis/

---

# 🆔 Finding Your Stop ID

Use the official Stop Lookup tool:

https://www.trafiklab.se/api/our-apis/trafiklab-realtime-apis/stop-lookup

Scroll down to the **Lookup** section:

1. Enter a stop name (e.g., “Sundsvall”, “Stockholm”, “Uppsala”)  
2. Enter your API key  
3. Click **Try it out**  
4. Open the generated URL in your browser  
5. Copy the **stop_group → id** value

Example: **"id": "740098000"**
This is the Stop ID you enter in Home Assistant.

---

# ⚙️ Configuration (Home Assistant UI)

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Kollektivtrafik Sverige**
3. Enter your **API key**
4. Enter your **Stop ID**
5. Configure optional filters:
   - **Line Filter** (e.g., `1, 4, 42X`)
   - **Direction Filter** (`0`, `1`, or empty)
6. Configure optional **Time Windows**: 06:00-10:00, 16:00-22:00
7. Finish setup

The integration creates **five sensors**:

- sensor.kollektivtrafik_sverige_departure_1
- sensor.kollektivtrafik_sverige_departure_2
- sensor.kollektivtrafik_sverige_departure_3
- sensor.kollektivtrafik_sverige_departure_4
- sensor.kollektivtrafik_sverige_departure_5

Each sensor represents one upcoming departure.

---

# ⏱️ Sensor Behavior

### **State**
Minutes until departure (integer)

### **Attributes**
- `line`
- `destination`
- `direction`
- `scheduled_time`
- `expected_time`
- `real_time`
- `transport_mode`
- `deviations`

Example:

```yaml
line: "1"
destination: "Bergsåker"
scheduled_time: "2026-05-03T14:32:00"
expected_time: "2026-05-03T14:33:00"
real_time: true
transport_mode: "BUS"



How It Works (Architecture Overview)
This integration is built for robustness and minimal API usage.

1. Polling Engine
Ensures predictable update intervals and prevents overlapping requests.

2. Request Queue
Prevents API spam and protects your Trafiklab quota.

3. Coordinator
Stores the latest departures and exposes them to sensors.

4. Parser
Normalizes Trafiklab’s JSON into clean, predictable fields.

5. Filters
Applies:

line filter

direction filter

time windows

6. Sensors
Each sensor reads one departure from the coordinator.

📉 API Quota Considerations
Trafiklab’s free tier has limited monthly calls.

This integration is designed to be safe:

One API call per update interval

Five sensors share the same data

Time windows reduce unnecessary polling

No ResRobot (which is expensive)

No arrivals (cuts API usage in half)

Recommended update interval: 300 seconds (5 minutes)

🛠️ Troubleshooting
“Invalid API key”
Ensure you created a project

Ensure you created a key inside the project

Ensure the key is for Trafiklab Realtime APIs

“Invalid stop ID”
Use the Stop Lookup tool

Copy the stop_group → id value

Do NOT use child stop IDs

No departures shown
Check your line filter

Check your direction filter

Check your time windows

Check Trafiklab status page

Sensor shows “unavailable”
Temporary API outage

Network issues

Quota exceeded

The integration will recover automatically.

📄 License
This project is licensed under the Mozilla Public License 2.0 (MPL‑2.0).
See the LICENSE file for details.



