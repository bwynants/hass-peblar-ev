"""Exceptions for the peblar-modbus device library.

Transport failures surface as :class:`PeblarConnectionError`, which subclasses
``modbus_connection.ModbusError`` as well - so a consumer that already catches
the neutral Modbus hierarchy (as the Home Assistant coordinator does) catches
these without knowing about this library's own types.
"""

from __future__ import annotations

from modbus_connection import ModbusError


class PeblarModbusError(Exception):
    """Base error for the Peblar Modbus device library."""


class PeblarConnectionError(PeblarModbusError, ModbusError):
    """Communication with the charger failed."""


class PeblarValueError(PeblarModbusError, ValueError):
    """A value to write is outside the allowed range or option set."""
