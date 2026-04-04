# Sigenergy Cloud - Home Assistant Integration

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![GitHub Release](https://img.shields.io/github/v/release/schwarzbr0t/sigenergy-ha)](https://github.com/schwarzbr0t/sigenergy-ha/releases)

Home Assistant custom integration for **Sigenergy** solar inverters, batteries, and energy storage systems via the Sigenergy Cloud OpenAPI.

## Features

- **Real-time energy flow monitoring**: PV power, grid power, battery power, load power, EV charger power, heat pump power
- **Battery state of charge** (SOC)
- **Energy generation statistics**: Daily, monthly, annual, and lifetime PV generation
- **Device-level monitoring**: Inverter, battery, gateway, and meter real-time data (voltages, currents, temperatures, frequencies)
- **Operating mode control**: Switch between Maximum Self-Consumption and Fully Feed-in to Grid modes
- **Multi-system support**: Automatically discovers all systems linked to your account
- **HA Energy Dashboard compatible**: Sensors use proper device classes for seamless Energy Dashboard integration

## Prerequisites

You need one of the following:

1. **Sigenergy Account**: Username and password for your Sigenergy account
2. **Developer API Key**: App Key and App Secret from the [Sigenergy Developer Portal](https://developer.sigencloud.com)

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the three dots in the top right corner
3. Select "Custom repositories"
4. Add `https://github.com/schwarzbr0t/sigenergy-ha` as an **Integration**
5. Click "Download"
6. Restart Home Assistant

### Manual

1. Copy the `custom_components/sigenergy` folder to your Home Assistant `custom_components` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings** > **Devices & Services** > **Add Integration**
2. Search for "Sigenergy Cloud"
3. Choose your authentication method:
   - **Sigen Account**: Enter your username and password
   - **App Key & Secret**: Enter your App Key and App Secret
4. The integration will automatically discover your systems and devices

## Sensors

### System-Level Sensors

| Sensor | Unit | Description |
|--------|------|-------------|
| PV Power | kW | Current solar generation |
| Grid Power | kW | Grid import (negative) / export (positive) |
| Battery Power | kW | Charging (positive) / discharging (negative) |
| Load Power | kW | Current household consumption |
| EV Charger Power | kW | EV charging power |
| Heat Pump Power | kW | Heat pump consumption |
| Battery SOC | % | Battery state of charge |
| Daily PV Generation | kWh | Energy generated today |
| Monthly PV Generation | kWh | Energy generated this month |
| Annual PV Generation | kWh | Energy generated this year |
| Lifetime PV Generation | kWh | Total energy generated |
| Operating Mode | - | Current operating mode |

### Device-Level Sensors (Inverter)

Phase voltages, currents, active/reactive power, grid frequency, PV power, battery power, internal temperature, insulation resistance, daily/total energy counters.

### Device-Level Sensors (Meter/Gateway)

Phase voltages, currents, active/reactive power, grid frequency, power factor.

## Controls

| Entity | Type | Description |
|--------|------|-------------|
| Operating Mode Control | Select | Switch between MSC and FFG modes |

## API Rate Limits

The Sigenergy Cloud API enforces rate limits of **1 request per endpoint per 5 minutes**. The integration respects this with a default polling interval of 5 minutes.

## Troubleshooting

- **"Access restriction" errors**: The API rate limit has been hit. The integration will retry on the next polling cycle.
- **"Authentication failed" errors**: Check your credentials. Tokens expire after 12 hours and are automatically refreshed.
- **Missing devices**: Only devices that are online and have completed the onboard process are visible.

## License

MIT License
