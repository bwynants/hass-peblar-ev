"""Building the Modbus connection this integration owns.

Home Assistant has no shared `modbus_connection` integration yet - the Modbus
modernization blog post asks integrations to hold off on wiring one up - so the
charger's link is created and owned here, exactly as the reference
implementation does it.

The connection is built but deliberately *not* opened: `modbus-connection`
connects on first use and reconnects on its own, so a charger that is asleep or
rebooting at Home Assistant start does not fail the config entry.

Isolating this in one module is the point. Whenever the shared integration does
land, borrowing a unit from it replaces this file and nothing else.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal, cast

from modbus_connection import ModbusTcpParams
from modbus_connection.pymodbus import ModbusConnection

from .const import CONF_FRAMER, CONF_HOST, CONF_PORT, DEFAULT_FRAMER, DEFAULT_PORT


def build_modbus_params(data: Mapping[str, Any]) -> ModbusTcpParams:
    """Build backend-neutral connection parameters from the config entry."""
    framer = cast(
        Literal["socket", "rtu"], str(data.get(CONF_FRAMER, DEFAULT_FRAMER))
    )
    return ModbusTcpParams(
        host=str(data[CONF_HOST]),
        port=int(data.get(CONF_PORT, DEFAULT_PORT)),
        framer=framer,
    )


def create_modbus_connection(data: Mapping[str, Any]) -> ModbusConnection:
    """Create the charger's connection without opening it."""
    return ModbusConnection(build_modbus_params(data))
