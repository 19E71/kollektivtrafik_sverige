<p align="center">
  <img src="custom_components/kollektivtrafik_sverige/brand/icon.png" width="128" height="128" alt="Kollektivtrafik Sverige Logo">
</p>

<h1 align="center">Kollektivtrafik Sverige</h1>

<p align="center">
  <b>Advanced Home Assistant integration for real-time Swedish public transport.</b><br>
  <i>Powered by the Trafiklab Unified Realtime API v1.</i>
</p>

<p align="center">
  <a href="https://github.com/19E71/Kollektivtrafik_Sverige/releases"><img src="https://img.shields.io/github/v/release/19E71/Kollektivtrafik_Sverige?style=for-the-badge&color=blue" alt="Version"></a>
  <a href="https://opensource.org/licenses/MPL-2.0"><img src="https://img.shields.io/badge/License-MPL--2.0-brightgreen?style=for-the-badge" alt="License"></a>
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Custom-orange?style=for-the-badge" alt="HACS"></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/badge/Code%20Style-Ruff-000000?style=for-the-badge" alt="Code Style: Ruff"></a>
</p>

---

## 🚍 Overview

**Kollektivtrafik Sverige** brings real-time departures from virtually any public transport stop in Sweden directly into your Home Assistant dashboard. Whether it's a bus in Kiruna or a subway in Stockholm, this integration provides precise timing, dynamic updates, and intelligent API quota management.

### ✨ Key Features

- ⏱️ **Real-time Departures**: Up to 5 live departure sensors per stop, sorted by proximity.
- 🏷️ **Dynamic Naming**: Sensors automatically rename themselves to show the line and destination (e.g., `1. (4 - Gullmarsplan)`).
- 🔍 **Flexible Filtering**: Filter by Line ID or Direction to see exactly what you need.
- 🛡️ **Quota Watchdog**: Intelligent logic that automatically throttles polling to stay within the Trafiklab Bronze Tier limits.
- 🌓 **Time Windows**: Define active hours to pause polling and save API budget during the night or while you're at work.
- 📊 **Global Diagnostics**: Integration-wide sensors for API usage, throttle factors, and service gaps.

---

## 📦 Installation

### Option 1: HACS (Recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=19E71&repository=https%3A%2F%2Fgithub.com%2F19E71%2Fkollektivtrafik_sverige)

1. Open **HACS** in your Home Assistant instance.
2. Click the three dots in the top right corner and select **Custom Repositories**.
3. Paste `https://github.com/19E71/Kollektivtrafik_Sverige` and select **Integration** as the category.
4. Click **Add**, then search for **Kollektivtrafik Sverige** and click **Download**.
5. **Restart** Home Assistant.

### Option 2: Manual

1. Download the latest release.
2. Copy the `custom_components/kollektivtrafik_sverige` folder into your Home Assistant `custom_components` directory.
3. **Restart** Home Assistant.

---

## 🚀 Setup Guide

### 1. Get your API Key

1. Sign up at [Trafiklab](https://developer.trafiklab.se/).
2. Create a project and generate a key for the **Trafiklab Unified Realtime API v1**.
   > [!NOTE]
   > Ensure you are using the "Trafiklab Realtime APIs", not the older "SL" specific APIs.

### 2. Find your Stop ID

Use the official [Stop Lookup tool](https://www.trafiklab.se/api/our-apis/trafiklab-realtime-apis/stop-lookup):

1. Enter your API key and search for your stop.
2. Look for the `stop_group -> id` (usually a 9-digit number starting with `74`).

### 3. Add the Integration

1. In Home Assistant, go to **Settings → Devices & Services**.
2. Click **Add Integration** and search for **Kollektivtrafik Sverige**.
3. Enter your **API Key** and **Stop ID**.
4. (Optional) Configure **Line Filters** (e.g., `1, 4, 172`) or **Time Windows**.

---

## 🛠️ How it Works: Smart Polling

This integration is designed to be "set and forget." It manages your API quota automatically:

| Mode             | Description                                                      |
| :--------------- | :--------------------------------------------------------------- |
| **Normal**       | High-precision updates when departures are imminent.             |
| **Conservative** | Polling slowed down by 50% as you approach hourly budget limits. |
| **Throttled**    | Polling slowed down by 100% if the daily budget is at risk.      |
| **Low Power**    | API calls are paused outside of your defined **Time Windows**.   |

### Global Diagnostics Device

The integration creates a special **Global Diagnostics** device that tracks the health and usage of the entire integration across all configured stops.

- **Global API Quota Usage**: A sensor showing the percentage of your daily allowance used.
- **Attributes**: Displays active stop count, aggregate throttle factor, and service gap detection.

---

## 📋 Sensor Attributes

Every departure sensor provides rich metadata for your cards:

- `line`: The bus/train line number.
- `destination`: Final stop of the trip.
- `expected_time`: The real-time estimated departure.
- `scheduled_time`: The planned time according to the timetable.
- `deviations`: Detailed list of any delays or service changes.
- `transport_mode`: Icon-compatible vehicle type (BUS, TRAIN, METRO, etc.).

---

## 🤝 Contributing

Contributions are welcome! If you find a bug or have a feature request, please open an issue or a pull request.

---

## 📄 License

This project is licensed under the **Mozilla Public License 2.0 (MPL‑2.0)**. See the [LICENSE](LICENSE) file for details.

---

<p align="center">
  <i>Developed with ❤️ for the Home Assistant community.</i>
</p>
