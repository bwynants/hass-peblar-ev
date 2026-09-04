# Peblar EV (Modbus)

Home Assistant custom integration for the **Peblar** EV charger over Modbus TCP (1 Fase only).

## Installation

### Prerequisites

- Home Assistant 2026.8.0 or newer
- A Peblar charger reachable over **Modbus TCP** (enable the Modbus TCP server in
  the charger's web interface, default port 502)

### HACS (recommended)

1. In HACS, open the overflow menu -> **Custom repositories**.
2. Add `https://github.com/bwynants/hass-peblar-ev` with type **Integration**.
3. Install **Peblar EV (Modbus)** and restart Home Assistant.

### Manual installation

1. Copy `custom_components/peblar_ev/` into your HA `config/custom_components/`
   directory:
   ```
   config/
   └── custom_components/
       └── peblar_ev/
           ├── __init__.py
           ├── manifest.json
           ├── config_flow.py
           ├── connection.py
           ├── coordinator.py
           ├── const.py
           ├── entity.py
           ├── sensor.py
           ├── binary_sensor.py
           ├── number.py
           ├── switch.py
           └── peblar_modbus/
               ├── __init__.py
               ├── components.py
               ├── device.py
               ├── model.py
               ├── enums.py
               ├── validators.py
               └── exceptions.py
   ```
2. Restart Home Assistant.

### Setup

Go to **Settings -> Devices & Services -> Add Integration** and search for
**Peblar EV (Modbus)**.

## Layout

```
peblar_ev/
└── peblar_modbus/     vendored device library (imported at runtime)
```

`peblar_modbus/` is not published on PyPI, so it ships inside the integration
rather than being declared as a requirement. It imports nothing from Home
Assistant, so it can be exercised on its own.

The only PyPI requirement is `modbus-connection[pymodbus]`.

## Connection ownership

Home Assistant has no shared `modbus_connection` integration yet — the
[Modbus modernization post](https://developers.home-assistant.io/blog/2026/07/05/modernizing-modbus/)
asks integrations to hold off on wiring one up — so this integration owns the charger's
link itself, in `connection.py`. It is built lazily and reconnects on its own, so a
charger that is rebooting at Home Assistant start does not fail setup.

That file is the whole coupling. When the shared integration lands, borrowing a unit
from it replaces `connection.py` and nothing else.

## What lives where

* **Library** — the register map, decoding, scaling and write validation. No policy, no
  Home Assistant.
* **`coordinator.py`** — all charging policy, and the only place that writes: the
  effective current limit (request folded with charge-enable, debounced), the
  watchdog arm/disarm, the heartbeat, sync-off, and link health.
* **Platforms** — views of the coordinator.

## Entities

Named so the entity ids come out as `sensor.peblar_power`, `binary_sensor.peblar_charging`
and so on, matching the YAML package this replaces.

| Entity | Purpose |
| --- | --- |
| `number.peblar_charge_current_limit` | Requested current (A). The request, not the command. |
| `switch.peblar_charge_enable` | On: follow the request. Off: pause at 0 A. |
| `switch.peblar_watchdog` | Arm the charger's Alive/Fallback watchdog. |
| `sensor.peblar_power` / `_current` / `_energy` | Live measurements. |
| `sensor.peblar_charge_state` | Control-pilot state (A–F), as an enum. |
| `sensor.peblar_current_limit_actual` / `_source` | What the charger applies, and what is binding it. |
| `binary_sensor.peblar_charging` / `_connected` | Derived from the pilot state. |
| `binary_sensor.peblar_modbus_down` | Link down for over 2 minutes. Stays available during an outage. |

## Safety model

The charger's watchdog is what makes this safe: with it armed, the charger falls back to
`fallback_current` (0 A by default — a safe stop) if Home Assistant stops writing. The
heartbeat only feeds it *while charging*, so a pause is allowed to time out to that
fallback rather than being held open by a stream of 0 A writes.

Home Assistant is the boss: on setup and after every reconnect the watchdog registers are
forced to match the switch, so a charger reboot cannot leave the watchdog disarmed
behind our back.

Pausing more often than the configured limit logs a relay-wear warning but still pauses —
refusing would leave the charger drawing current against an explicit instruction.

## Enabling debug logging

```yaml
logger:
  logs:
    custom_components.peblar_ev: debug
    peblar_modbus: debug
    modbus_connection: debug
```

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
