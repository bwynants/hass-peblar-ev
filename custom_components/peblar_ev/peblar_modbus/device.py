"""The Peblar Modbus device.

Wraps a ``modbus_connection.ModbusUnit`` - the handle a consumer gets from a
connection it owns, or borrows from a shared one - and presents the charger as
a device rather than a register map::

    device = PeblarModbusDevice(unit)
    data = await device.async_update()               # -> PeblarData
    await device.async_set_charge_current(16.0)      # Amps

The two components are pooled behind one ``ComponentGroup`` so a poll issues
the fewest block reads the declared ranges allow, instead of one round trip per
datapoint.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from modbus_connection import ModbusError
from modbus_connection.model import ComponentGroup

from .components import PeblarMeasurements, PeblarSettings
from .exceptions import PeblarConnectionError
from .model import PeblarData

if TYPE_CHECKING:
    from modbus_connection import ModbusUnit

# The register a probe reads: total active power, present on every model.
PROBE_ADDRESS = 30014
PROBE_COUNT = 2


class PeblarModbusDevice:
    """A Peblar EV charger reachable over Modbus."""

    def __init__(self, unit: ModbusUnit) -> None:
        """Bind the device to a unit handle on an open connection."""
        self._unit = unit
        self.measurements = PeblarMeasurements(unit)
        self.settings = PeblarSettings(unit)
        self._group = ComponentGroup(unit, [self.measurements, self.settings])

    @staticmethod
    async def async_probe(unit: ModbusUnit) -> None:
        """Check that a Peblar charger answers on this unit.

        Reads one known input register, so a config flow can tell "wrong host,
        port or unit id" from a working charger without a full poll.

        Raises :class:`PeblarConnectionError` if the charger does not answer.
        """
        try:
            await unit.read_input_registers(PROBE_ADDRESS, PROBE_COUNT)
        except ModbusError as err:
            raise PeblarConnectionError(f"no Peblar charger answered: {err}") from err

    async def async_update(self) -> PeblarData:
        """Read the whole charger and return a snapshot.

        Raises :class:`PeblarConnectionError` if the charger could not be read.
        """
        try:
            await self._group.async_update()
        except ModbusError as err:
            raise PeblarConnectionError(f"reading the charger failed: {err}") from err
        return PeblarData.from_components(self.measurements, self.settings)

    # -- writes --------------------------------------------------------------
    async def async_set_charge_current(self, amps: float) -> None:
        """Set the charge current limit in Amperes; 0 pauses charging."""
        await self._write("charge_current_limit", amps)

    async def async_set_alive_timeout(self, seconds: int) -> None:
        """Set the watchdog AliveTimeout in seconds; 0 disarms the watchdog."""
        await self._write("alive_timeout", seconds)

    async def async_set_fallback_current(self, amps: float) -> None:
        """Set the current the charger falls back to when the watchdog expires."""
        await self._write("fallback_current", amps)

    async def async_set_force_1_phase(self, enabled: bool) -> None:
        """Force single-phase charging."""
        await self._write("force_1_phase", enabled)

    async def _write(self, field: str, value: float | int | bool) -> None:
        """Write one settings field, normalising transport errors.

        The field's validator runs first and raises ``PeblarValueError`` for an
        out-of-range value, before any Modbus traffic.
        """
        try:
            await self.settings.write(field, value)
        except ModbusError as err:
            raise PeblarConnectionError(f"writing {field} failed: {err}") from err
