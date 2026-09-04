"""The Peblar EV (Modbus) integration.

Owns a Modbus connection to the charger (see `connection.py`), wraps a unit
handle in the vendored `peblar_modbus` device library, and adds the charging
policy the device library deliberately does not have.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .connection import create_modbus_connection
from .const import CONF_UNIT_ID, DEFAULT_UNIT_ID
from .coordinator import PeblarCoordinator
from .peblar_modbus import PeblarModbusDevice

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]

type PeblarConfigEntry = ConfigEntry[PeblarCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: PeblarConfigEntry) -> bool:
    """Set up Peblar EV from a config entry."""
    settings = {**entry.data, **entry.options}
    try:
        connection = create_modbus_connection(settings)
        unit = connection.for_unit(int(settings.get(CONF_UNIT_ID, DEFAULT_UNIT_ID)))
    except (KeyError, TypeError, ValueError) as err:
        raise ConfigEntryNotReady(
            f"The Peblar config entry has no usable connection data: {err}"
        ) from err

    # Closing the link is the last thing to happen on unload, after the
    # platforms and the coordinator have stopped using it.
    entry.async_on_unload(connection.close)

    coordinator = PeblarCoordinator(hass, entry, PeblarModbusDevice(unit))
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # The link dropping invalidates the policy we asserted on the charger, so
    # reload to re-assert it once the connection is back.
    entry.async_on_unload(
        unit.on_connection_lost(
            lambda: hass.config_entries.async_schedule_reload(entry.entry_id)
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Feed the watchdog (only acts while armed and charging).
    coordinator.start_heartbeat()

    entry.async_on_unload(entry.add_update_listener(_async_reload_on_options))
    return True


async def _async_reload_on_options(
    hass: HomeAssistant, entry: PeblarConfigEntry
) -> None:
    """Re-apply options by reloading the entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: PeblarConfigEntry) -> bool:
    """Tear down."""
    entry.runtime_data.stop_heartbeat()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
