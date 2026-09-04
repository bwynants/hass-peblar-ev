"""The parsed, engineering-unit snapshot of the charger."""

from __future__ import annotations

from dataclasses import dataclass

from .components import PeblarMeasurements, PeblarSettings
from .enums import CpState, CurrentLimitSource


@dataclass(frozen=True, slots=True)
class PeblarData:
    """An immutable snapshot, produced by ``PeblarModbusDevice.async_update()``.

    Numeric members are ``None`` when the charger did not return a decodable
    value, so a consumer can show "unknown" rather than a fabricated zero. The
    two state enums always carry a value, falling back to their ``UNKNOWN``
    member.
    """

    energy: float | None  # Wh, lifetime
    power: float | None  # W, total active
    current: float | None  # A, line current L1
    wlan_signal: int | None  # dBm
    lock_state: int | None  # socket lock; always 0 on fixed-cable models
    cp_state: CpState  # SAE J1772 control-pilot state
    current_limit_source: CurrentLimitSource  # which source binds the limit
    current_limit_actual: float | None  # A, what the charger actually applies
    charge_current_limit: float | None  # A, our commanded limit, read back
    force_1_phase: bool | None
    alive_timeout: int | None  # s; 0 = watchdog disarmed
    fallback_current: float | None  # A, applied when the watchdog expires

    @property
    def watchdog_armed(self) -> bool:
        """Whether the charger's AliveTimeout watchdog is currently active."""
        return bool(self.alive_timeout)

    @classmethod
    def from_components(
        cls, measurements: PeblarMeasurements, settings: PeblarSettings
    ) -> PeblarData:
        """Build a snapshot from the two freshly-read components."""
        return cls(
            energy=_as_float(measurements.energy_total),
            power=_as_float(measurements.power_total),
            current=_as_float(measurements.current_l1),
            wlan_signal=_as_int(measurements.wlan_signal),
            lock_state=_as_int(measurements.lock_state),
            cp_state=CpState.from_letter(_pilot_letter(measurements.cp_state_raw)),
            current_limit_source=(
                measurements.current_limit_source or CurrentLimitSource.UNKNOWN
            ),
            current_limit_actual=_as_float(measurements.current_limit_actual),
            charge_current_limit=_as_float(settings.charge_current_limit),
            force_1_phase=settings.force_1_phase,
            alive_timeout=_as_int(settings.alive_timeout),
            fallback_current=_as_float(settings.fallback_current),
        )


def _pilot_letter(raw: str | None) -> str | None:
    """The control-pilot letter from the CP-state string.

    The charger reports two characters and the pilot letter is the last one;
    taking it from the end survives the leading NUL being stripped during
    decoding.
    """
    return raw[-1] if raw else None


def _as_float(value: float | int | None) -> float | None:
    """Widen a decoded number to float, preserving ``None``."""
    return None if value is None else float(value)


def _as_int(value: float | int | None) -> int | None:
    """Narrow a decoded number to int, preserving ``None``."""
    return None if value is None else int(value)
