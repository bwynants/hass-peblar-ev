"""Enumerations used by the Peblar Modbus device model."""

from __future__ import annotations

from enum import IntEnum, StrEnum


class CpState(StrEnum):
    """SAE J1772 control-pilot state, derived from the CP-state register (30110).

    The Peblar reports a 2-character string; the meaningful pilot letter is the
    second character (index 1). We map that letter to a human-readable state.
    """

    DISCONNECTED = "disconnected"  # A - no vehicle
    CONNECTED = "connected"  # B - vehicle connected, not charging
    CHARGING = "charging"  # C - charging
    CHARGING_VENTILATION = "charging_ventilation"  # D - charging (ventilation)
    ERROR = "error"  # E
    FAULT = "fault"  # F
    UNKNOWN = "unknown"

    @classmethod
    def from_letter(cls, letter: str | None) -> "CpState":
        """Map a single CP letter (A-F) to a CpState."""
        return {
            "A": cls.DISCONNECTED,
            "B": cls.CONNECTED,
            "C": cls.CHARGING,
            "D": cls.CHARGING_VENTILATION,
            "E": cls.ERROR,
            "F": cls.FAULT,
        }.get((letter or "").upper(), cls.UNKNOWN)

    @property
    def is_connected(self) -> bool:
        """Vehicle plugged in (B/C/D)."""
        return self in (self.CONNECTED, self.CHARGING, self.CHARGING_VENTILATION)

    @property
    def is_charging(self) -> bool:
        """Actively charging (C/D)."""
        return self in (self.CHARGING, self.CHARGING_VENTILATION)


class CurrentLimitSource(IntEnum):
    """Which source is currently the binding current limit (register 30112).

    The charger applies the *minimum* of all active sources; this reports which
    one is binding right now. Values per the Peblar Modbus documentation.
    """

    UNKNOWN = 0
    FIXED_CABLE = 1
    THERMAL = 2
    CONFIGURATION = 3
    BOP = 4
    LOAD_BALANCING = 5
    USER_CABLE = 6
    OVERCURRENT_PROTECTION = 7
    HARDWARE_LIMIT = 8
    POWER_FACTOR = 9
    OCPP = 10
    PHASE_IMBALANCE = 11
    SCHEDULED_CHARGING = 12
    SOLAR_CHARGING = 13
    CURRENT_SLIDER = 14
    REST_API = 15
    MODBUS_API = 16
    POWER_LIMIT_INPUT = 17
    HOUSEHOLD_POWER_LIMIT = 18
    INTERNAL_POWER_LIMITER = 20

    @classmethod
    def from_raw(cls, value: int | None) -> "CurrentLimitSource":
        """Map a raw register value to the enum, defaulting to UNKNOWN."""
        try:
            return cls(int(value))  # type: ignore[arg-type]
        except (ValueError, TypeError):
            return cls.UNKNOWN
