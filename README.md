<p align="center">
  <img src="custom_components/kollektivtrafik_sverige/brand/icon.png" width="150" height="150" style="display: block; margin: 0 auto;" alt="Kollektivtrafik Sverige Logo">
  <h1 align="center">Kollektivtrafik Sverige</h1>
  <p align="center">
    <b>Home Assistant integration for Swedish public transport realtime departures.</b><br>
    Powered by the Trafiklab Realtime APIs.
  </p>
</p>

<p align="center">
  <img src="https://img.shields.io/github/v/release/19E71/Kollektivtrafik_Sverige?style=flat-square" alt="Version">
  <img src="https://img.shields.io/badge/license-MPL--2.0-green?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/HACS-Custom-orange?style=flat-square" alt="HACS">
  <img src="https://img.shields.io/badge/code%20style-ruff-000000.svg?style=flat-square" alt="Code Style: Ruff">
  <img src="https://img.shields.io/github/last-commit/19E71/Kollektivtrafik_Sverige?style=flat-square" alt="Last Updated">
  <img src="https://img.shields.io/github/issues/19E71/Kollektivtrafik_Sverige?style=flat-square" alt="Issues">
</p>

---

## 🚍 Features

- **Realtime departures** from any Trafiklab-supported stop in Sweden.
- **Five departure sensors per stop** (next 5 departures).
- **Line filtering** (e.g., `1, 4, 42X`).
- **Direction filtering** (`0`, `1`, or empty for both).
- **Optional time windows** (e.g., `06:00-10:00, 16:00-22:00`).
- **Modern Home Assistant** — No YAML required.

---

## 📦 Installation

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=19E71&repository=https%3A%2F%2Fgithub.com%2F19E71%2Fkollektivtrafik_sverige)

### HACS

1. Open **HACS → Integrations**.
2. Click the three dots in the top right and select **Custom Repositories**.
3. Add `https://github.com/19E71/Kollektivtrafik_Sverige` with category **Integration**.
4. Search for **Kollektivtrafik Sverige** and install.
5. **Restart** Home Assistant.

---

## 🔑 Getting Your Trafiklab API Key

1. **Create a project:** Sign up/in at [Trafiklab Project List](https://developer.trafiklab.se/project/list).
2. **Generate Key:** Inside your project, click **Create Key** and select **Trafiklab Realtime APIs**.
3. **Save:** This is the key you will enter during the Home Assistant setup.

---

## 🆔 Finding Your Stop ID

Use the official [Stop Lookup tool](https://www.trafiklab.se/api/our-apis/trafiklab-realtime-apis/stop-lookup):

1. Enter a stop name (e.g., “Sundsvall”, “Stockholm”).
2. Enter your API key and click **Try it out**.
3. Open the generated URL and copy the **`stop_group -> id`** value (e.g., `"740098000"`).

---

## ⚙️ Configuration (UI)

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **Kollektivtrafik Sverige**.
3. Enter your **API key** and **Stop ID**.
4. Configure optional filters and **Time Windows**.

The integration creates **six sensors**:

- `sensor.[stop_name]_1` ... to `_5` (Names update dynamically based on the bus line).
- `sensor.[stop_name]_api_quota_usage` (Tracks your daily API spend)

---

## ⏱️ Sensor Behavior

**State:** Minutes until departure (integer) or a Timestamp (ISO string).
**Attributes:**

- `line`, `destination`, `direction`: Current trip details.
- `scheduled_time`, `expected_time`: Planned vs. estimated times.
- `transport_mode`, `deviations`: Type of vehicle and any active delays/notices.
- `next_poll_seconds`: Seconds until the next scheduled API refresh.
- `api_quota_usage`: (Only on Quota sensor) Percentage of daily allowance used.
- `throttle_factor`: Current polling speed multiplier (e.g., `1.5` means polling is slowed down to save budget).

---

## 🏗️ Architecture & Quotas

This integration uses a multi-layered polling strategy to manage the Trafiklab Bronze Tier (100k monthly calls) automatically.

- **Dynamic Budgeting:** Calculates a daily "fair share" per stop based on the 3,300 total daily call limit.
- **Throttling:** If usage exceeds the fair share, the polling interval is automatically doubled until the budget recovers.
- **Reactive Polling:** Speeds up when a departure is within 5 minutes and slows down during long service gaps.
- **Time Windows:** Completely pauses API requests outside of user-defined hours.
- **Efficiency:** A single API request updates all 5 departure sensors and the quota sensor simultaneously.

---

## 🛠️ Troubleshooting

- **"Invalid API key":** Ensure it is specifically for the *Trafiklab Realtime API*.
- **"Invalid stop ID":** Ensure you used the *stop_group ID*, not a child/platform ID.
- **No departures shown:** Check your filters or verify the stop on the Trafiklab status page.
- **Status "Unavailable":** Likely a quota limit or temporary network issue; it will recover automatically.

---

## 📄 License

  This project is licensed under the **Mozilla Public License 2.0 (MPL‑2.0)**.
See the `LICENSE` file for details.
