"""peblar-modbus: a backend-neutral device library for the Peblar EV charger.

Built on ``modbus-connection``: the library models the charger and nothing
else, so it runs over pymodbus, tmodbus, or the in-memory mock, and carries no
Home Assistant dependency. Charging *policy* belongs to the consumer.
"""

from __future__ import annotations

from .components import PeblarMeasurements, PeblarSettings
from .device import PeblarModbusDevice
from .enums import CpState, CurrentLimitSource
from .exceptions import (
    PeblarConnectionError,
    PeblarModbusError,
    PeblarValueError,
)
from .model import PeblarData
from .validators import CHARGE_CURRENT_MAX, CHARGE_CURRENT_MIN

__version__ = "0.2.0"

__all__ = [
    "CHARGE_CURRENT_MAX",
    "CHARGE_CURRENT_MIN",
    "CpState",
    "CurrentLimitSource",
    "PeblarConnectionError",
    "PeblarData",
    "PeblarMeasurements",
    "PeblarModbusDevice",
    "PeblarModbusError",
    "PeblarSettings",
    "PeblarValueError",
    "__version__",
]
