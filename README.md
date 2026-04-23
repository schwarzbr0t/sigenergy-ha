# Sigenergy Cloud — Home Assistant Integration

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![GitHub Release](https://img.shields.io/github/v/release/schwarzbr0t/sigenergy-ha)](https://github.com/schwarzbr0t/sigenergy-ha/releases)
[![HACS Action](https://github.com/schwarzbr0t/sigenergy-ha/actions/workflows/validate.yaml/badge.svg)](https://github.com/schwarzbr0t/sigenergy-ha/actions/workflows/validate.yaml)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-kevinschwarz-ffdd00?logo=buymeacoffee&logoColor=black)](https://buymeacoffee.com/kevinschwarz)

Home Assistant custom integration for **Sigenergy** solar inverters, batteries, and energy storage systems via the Sigenergy Cloud OpenAPI.

## Features

- **Real-time energy flow**: PV power, grid import/export, battery charge/discharge, home load, EV charger, heat pump
- **Battery monitoring**: State of charge (%), stored energy (kWh), and total capacity (kWh)
- **Energy generation statistics**: Daily, monthly, annual, and lifetime PV generation
- **Device-level monitoring**: Per-inverter and per-meter data — voltages, currents, power factor, temperature, frequency
- **Operating mode control**: Switch between Maximum Self-Consumption and Fully Feed-in to Grid
- **Multi-system support**: All systems linked to your account are discovered automatically
- **Smart caching**: System and device lists are cached after the first fetch — no rate-limit issues on HA restart
- **HA Energy Dashboard compatible**: Proper device classes for seamless Energy Dashboard integration

## Prerequisites

A **Sigenergy account** (username + password) for an installation where you are the account owner or have monitoring access.

> The integration uses the Sigenergy Cloud OpenAPI. Access is available to account owners.

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the three dots → **Custom repositories**
3. Add `https://github.com/schwarzbr0t/sigenergy-ha` as an **Integration**
4. Click **Download**
5. Restart Home Assistant

### Manual

1. Copy `custom_components/sigenergy` to your `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Sigenergy Cloud**
3. Select your **region** and enter your **username and password**
4. The integration discovers your systems and devices automatically

## Entities

### System-Level Sensors

| Sensor | Unit | Description |
|--------|------|-------------|
| PV Power | kW | Current solar generation |
| Grid Power | kW | Positive = import, negative = export to grid |
| Battery Power | kW | Positive = charging, negative = discharging |
| Load Power | kW | Current household consumption |
| EV Charger Power | kW | EV charging power |
| Heat Pump Power | kW | Heat pump power |
| Battery State of Charge | % | Current battery charge level |
| Battery Stored Energy | kWh | Computed: capacity × SOC |
| Battery Total Capacity | kWh | Rated total battery capacity |
| Daily PV Generation | kWh | Energy generated today |
| Monthly PV Generation | kWh | Energy generated this month |
| Annual PV Generation | kWh | Energy generated this year |
| Lifetime PV Generation | kWh | Total lifetime generation |
| Operating Mode | — | Current system operating mode |
| Last Sync | timestamp | Time of last successful data fetch |

### Inverter Sensors (per device)

Active power, PV power, battery power, battery SOC, phase voltages (A/B/C), phase currents (A/B/C), grid frequency, power factor, internal temperature, daily/total PV energy, battery charging/discharging energy today and total.

### Meter / Gateway Sensors (per device)

Active power, phase voltages (A/B/C), phase currents (A/B/C), grid frequency, power factor.

### Controls

| Entity | Type | Description |
|--------|------|-------------|
| Operating Mode | Select | Switch between Maximum Self-Consumption and Fully Feed-in to Grid |

## Regions

Select the region matching your Sigenergy account during setup:

| Region | Description |
|--------|-------------|
| Europe | EU |
| Asia Pacific & Middle Asia | AP |
| Middle East & Africa | MEA (routes via EU endpoint) |
| Chinese Mainland | CN |
| Australia & New Zealand | ANZ |
| Latin America | LA (routes via US endpoint) |
| North America | NA |
| Japan | JP |

## API Rate Limits

The Sigenergy Cloud API allows **1 request per endpoint per 5 minutes**. The integration polls every 5 minutes and caches the system/device list so restarts don't trigger extra API calls.

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| "Rate limit reached" | API called too frequently | Wait a few minutes — HA retries automatically |
| "Authentication failed" | Wrong credentials or expired token | Reconfigure via Settings → Devices & Services |
| No devices / entities | System not yet discovered | Check HA logs; delete and re-add the integration |
| New system not showing up | System list is cached after first fetch | Call the `sigenergy.refresh_systems` service (see below) |

### Discovering a newly-added system

If you added a system to your Sigenergy account **after** setting up the integration,
it will not appear automatically — the system list is cached to avoid hitting the
1-request-per-5-minute rate limit on every HA restart.

To force re-discovery, call the **`sigenergy.refresh_systems`** service from
**Developer Tools → Services**:

```yaml
service: sigenergy.refresh_systems
# entry_id is optional — omit to refresh all Sigenergy entries
```

The service clears the cached system/device list and reloads the integration,
which triggers a fresh API call for your full system inventory.

## Support

If this integration is useful to you, consider supporting development:

[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-kevinschwarz-ffdd00?logo=buymeacoffee&logoColor=black)](https://buymeacoffee.com/kevinschwarz)

## License

MIT License
