"""Write-value validation for the Peblar charger.

A ``WriteValidator`` runs inside ``Component.write`` *before* the value is
scaled and encoded, so these functions see (and return) engineering units:
Amperes for currents, seconds for timeouts. Returning a value lets a validator
normalise as well as reject; raising rejects the write before any Modbus
traffic happens.
"""

from __future__ import annotations

from .exceptions import PeblarValueError

# Charging must be 0 (pause) or 6..32 A. Values between 0 and 6 A are not
# supported by EN-IEC 61851-1 and the charger would treat them as a pause -
# reject them so callers are explicit about pausing.
CHARGE_CURRENT_MIN = 6.0
CHARGE_CURRENT_MAX = 32.0  # 22 kW Peblar (32 A/phase); 16 A for an 11 kW model


def validate_charge_current(value: float) -> float:
    """Validate the commanded charge current limit in Amperes."""
    amps = float(value)
    if amps == 0:
        return 0.0
    if not CHARGE_CURRENT_MIN <= amps <= CHARGE_CURRENT_MAX:
        raise PeblarValueError(
            f"charge_current_limit must be 0 or "
            f"{CHARGE_CURRENT_MIN}..{CHARGE_CURRENT_MAX} A, got {amps}"
        )
    return amps


def validate_alive_timeout(value: float) -> int:
    """Validate the watchdog AliveTimeout in seconds (0 disarms it)."""
    seconds = int(value)
    if seconds < 0:
        raise PeblarValueError(f"alive_timeout must be >= 0 s, got {seconds}")
    return seconds


def validate_fallback_current(value: float) -> float:
    """Validate the watchdog fallback current in Amperes."""
    amps = float(value)
    if amps < 0:
        raise PeblarValueError(f"fallback_current must be >= 0 A, got {amps}")
    return amps
