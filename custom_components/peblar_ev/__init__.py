"""The Peblar EV (Modbus) integration.

Borrows a unit on a Modbus connection the Modbus integration shares between
integrations (see `connection.py`), wraps it in the vendored `peblar_modbus`
device library, and adds the charging policy the device library deliberately
does not have.
"""

from __future__ import annotations

import logging

from homeassistant.components.modbus import async_get_unit
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryError,
    ConfigEntryNotReady,
    HomeAssistantError,
)

from .connection import build_modbus_params
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
        params = build_modbus_params(settings)
        unit_id = int(settings.get(CONF_UNIT_ID, DEFAULT_UNIT_ID))
    except (KeyError, TypeError, ValueError) as err:
        raise ConfigEntryNotReady(
            f"The Peblar config entry has no usable connection data: {err}"
        ) from err

    # The Modbus integration owns the connection: it opens on first use, is
    # shared with any other integration describing the same device, and
    # closes when the last config entry holding a unit on it unloads. The
    # release is registered on this entry by async_get_unit itself, so there
    # is nothing to close here.
    try:
        unit = async_get_unit(hass, entry, params, unit_id)
    except HomeAssistantError as err:
        # Another entry holds this device over different link settings. That
        # is a configuration clash, not a transient fault: it wants a
        # reconfiguration rather than a retry.
        raise ConfigEntryError(str(err)) from err

    coordinator = PeblarCoordinator(hass, entry, PeblarModbusDevice(unit))
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # The link dropping invalidates the policy we asserted on the charger. The
    # connection is shared and reconnects on its own, so the entry is NOT
    # reloaded for it (that would churn a connection other integrations may
    # hold); the coordinator re-asserts the policy once polling succeeds again.
    entry.async_on_unload(unit.on_connection_lost(coordinator.mark_connection_lost))

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
