"""The Peblar register map, as ``modbus_connection.model`` components.

Two components, one per register space, so each is planned and read on its own
function code:

* :class:`PeblarMeasurements` - input registers (FC04), read-only telemetry.
* :class:`PeblarSettings`     - holding registers (FC03/FC06/FC16), the
  setpoints and watchdog configuration this library may write.

Addresses are the raw Modbus addresses on the wire (no 3x/4x data-model
offset), per the Peblar Modbus API (https://developer.peblar.com/modbus-api)
and confirmed against a working charger.

``register_ranges`` deliberately declares only the spans the datapoints
actually occupy. The planner merges reads *within* a range and never bridges
across a gap, so a poll issues one block read per contiguous run and never
touches an address the charger may not answer. Registers 30110..30114 and
40050..40053 are contiguous runs and therefore collapse into a single read
each. If the charger turns out to answer the gaps too, widening these ranges
is the one-line change that trades over-reading for fewer round trips.
"""

from __future__ import annotations

from modbus_connection.model import (
    Component,
    Range,
    boolean,
    enum,
    int32,
    int64,
    integer,
    string,
    uint32,
)

from .enums import CurrentLimitSource
from .validators import (
    validate_alive_timeout,
    validate_charge_current,
    validate_fallback_current,
)


class PeblarMeasurements(Component):
    """Read-only telemetry from the charger's input registers (FC04)."""

    register_space = "input"
    register_ranges: tuple[Range, ...] = (
        (30000, 30003),  # energy_total, int64
        (30014, 30015),  # power_total, int32
        (30022, 30023),  # current_l1, int32
        (30086, 30087),  # wlan_signal, int32
        (30110, 30114),  # cp_state .. current_limit_actual (one contiguous run)
    )

    energy_total = int64(30000, unit="Wh")
    power_total = int32(30014, unit="W")
    current_l1 = int32(30022, scale=0.001, unit="A")
    wlan_signal = int32(30086, unit="dBm")
    # Two ASCII characters in one register; the meaningful control-pilot letter
    # is the last one (the first is a NUL on the chargers seen so far).
    cp_state_raw = string(30110, 1)
    # Fixed-cable chargers report 0 here permanently; surfaced for socket models.
    lock_state = integer(30111, signed=False)
    current_limit_source = enum(30112, CurrentLimitSource)
    current_limit_actual = uint32(30113, scale=0.001, unit="A")


class PeblarSettings(Component):
    """Setpoints and watchdog configuration in the holding registers."""

    register_space = "holding"
    register_ranges: tuple[Range, ...] = (
        (40000, 40002),  # charge_current_limit + force_1_phase
        (40050, 40053),  # alive_timeout + fallback_current
    )

    # 0 A pauses charging; otherwise 6..32 A. Written as FC16 (two registers),
    # matching what the charger expects for a uint32 setpoint.
    charge_current_limit = uint32(
        40000, scale=0.001, unit="A", writable=validate_charge_current
    )
    # Single register: forced to FC16 so every write to this device uses the
    # same function code as the multi-register setpoints.
    force_1_phase = boolean(40002, writable=True, force_fc16=True)
    # 0 disarms the watchdog; any positive value arms it.
    alive_timeout = uint32(40050, unit="s", writable=validate_alive_timeout)
    # What the charger falls back to when the watchdog expires. 0 = safe stop.
    fallback_current = int32(
        40052, scale=0.001, unit="A", writable=validate_fallback_current
    )
