"""Coordinator and policy engine for the Peblar EV (Modbus) integration.

The device library stays pure; ALL charging policy lives here, and this is the
single place that issues writes, so nothing races:

  * effective current-limit write (requested folded with charge-enable), with a
    debounce and the relay-protection pause guard
  * watchdog arm/disarm (AliveTimeout / FallbackCurrent)
  * heartbeat feeding the watchdog while charging
  * Home-Assistant-is-boss assert of the watchdog on setup and reconnect
  * sync-off: drop charge-enable if the charger stops externally
  * link health, for the connectivity sensor
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ALIVE_TIMEOUT,
    CONF_FALLBACK_CURRENT,
    CONF_HEARTBEAT,
    CONF_MAX_CURRENT,
    CONF_PAUSE_LIMIT,
    DEFAULT_ALIVE_TIMEOUT,
    DEFAULT_FALLBACK_CURRENT,
    DEFAULT_HEARTBEAT,
    DEFAULT_MAX_CURRENT,
    DEFAULT_MIN_CURRENT,
    DEFAULT_PAUSE_LIMIT,
    DOMAIN,
    LINK_DOWN_GRACE,
    PAUSE_WINDOW,
    SYNC_OFF_DEBOUNCE,
    UPDATE_INTERVAL,
    WRITE_DEBOUNCE_SECONDS,
)
from .peblar_modbus import PeblarData, PeblarModbusDevice, PeblarModbusError

_LOGGER = logging.getLogger(__name__)


class PeblarCoordinator(DataUpdateCoordinator[PeblarData]):
    """Poll the charger and own all write policy."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, device: PeblarModbusDevice
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            config_entry=entry,
        )
        self.device = device
        self._options = {**entry.data, **entry.options}

        # Policy state. This is the source of truth; entities are views of it
        # and push their restored values back into it.
        self.requested_current: float = DEFAULT_MIN_CURRENT
        self.charge_enable: bool = False
        self.watchdog: bool = False

        # Write serialization, debounce and the pause guard.
        self._write_lock = asyncio.Lock()
        self._debounce_cancel = None
        self._pause_times: deque[datetime] = deque()
        self._actual_zero_since: datetime | None = None
        self._heartbeat_cancel = None
        self._last_success: datetime | None = None

    # -- tunables -----------------------------------------------------------
    @property
    def max_current(self) -> float:
        """The charger's maximum current in Amperes."""
        return float(self._options.get(CONF_MAX_CURRENT, DEFAULT_MAX_CURRENT))

    @property
    def heartbeat_seconds(self) -> int:
        """How often to feed the charger's watchdog."""
        return int(self._options.get(CONF_HEARTBEAT, DEFAULT_HEARTBEAT))

    @property
    def alive_timeout_seconds(self) -> int:
        """The watchdog timeout to arm the charger with."""
        return int(self._options.get(CONF_ALIVE_TIMEOUT, DEFAULT_ALIVE_TIMEOUT))

    @property
    def fallback_current_a(self) -> float:
        """The current the charger falls back to when the watchdog expires."""
        return float(
            self._options.get(CONF_FALLBACK_CURRENT, DEFAULT_FALLBACK_CURRENT)
        )

    @property
    def pause_limit(self) -> int:
        """How many pauses per 10 minutes the relay-protection guard allows."""
        return int(self._options.get(CONF_PAUSE_LIMIT, DEFAULT_PAUSE_LIMIT))

    # -- link health ---------------------------------------------------------
    @property
    def link_down(self) -> bool:
        """Whether the Modbus link has been down long enough to report it.

        A brief flap self-heals and should not raise an alarm, so this only
        turns true once polling has been failing for the whole grace period.
        """
        if self.last_update_success:
            return False
        if self._last_success is None:
            return True
        return dt_util.utcnow() - self._last_success >= LINK_DOWN_GRACE

    # -- polling ------------------------------------------------------------
    async def _async_update_data(self) -> PeblarData:
        """Read the charger."""
        try:
            data = await self.device.async_update()
        except PeblarModbusError as err:
            raise UpdateFailed(str(err)) from err
        self._last_success = dt_util.utcnow()
        self._check_sync_off(data)
        return data

    # -- effective current limit -------------------------------------------
    def _effective_current(self) -> float:
        """The current to command: the request when enabled, else 0 (pause)."""
        if self.charge_enable and self.requested_current > 0:
            return min(self.requested_current, self.max_current)
        return 0.0

    @callback
    def schedule_effective_write(self) -> None:
        """Debounce writes triggered by requested/charge-enable changes."""
        if self._debounce_cancel is not None:
            self._debounce_cancel()

        async def _fire(_now) -> None:
            self._debounce_cancel = None
            await self.async_write_effective()

        self._debounce_cancel = async_call_later(
            self.hass, WRITE_DEBOUNCE_SECONDS, _fire
        )

    async def async_write_effective(self) -> None:
        """Write the effective current limit to the charger."""
        amps = self._effective_current()
        if amps == 0 and not self._allow_pause():
            # Warn but still write: refusing to pause would leave the charger
            # drawing current against the user's explicit instruction, which is
            # worse than the relay wear this guard is watching for.
            _LOGGER.warning(
                "Peblar: more than %s pauses in 10 min - relay protection; "
                "writing anyway",
                self.pause_limit,
            )
        async with self._write_lock:
            try:
                await self.device.async_set_charge_current(amps)
            except PeblarModbusError as err:
                _LOGGER.error("Peblar: writing the current limit failed: %s", err)

    def _allow_pause(self) -> bool:
        """Track pause (0 A) writes in a rolling 10-minute window."""
        now = dt_util.utcnow()
        while self._pause_times and now - self._pause_times[0] > PAUSE_WINDOW:
            self._pause_times.popleft()
        self._pause_times.append(now)
        return len(self._pause_times) <= self.pause_limit

    # -- watchdog -----------------------------------------------------------
    async def async_apply_watchdog(self) -> None:
        """Force the charger's watchdog registers to match our flag."""
        async with self._write_lock:
            try:
                if self.watchdog:
                    await self.device.async_set_alive_timeout(
                        self.alive_timeout_seconds
                    )
                    await self.device.async_set_fallback_current(
                        self.fallback_current_a
                    )
                else:
                    await self.device.async_set_alive_timeout(0)
            except PeblarModbusError as err:
                _LOGGER.error("Peblar: applying the watchdog failed: %s", err)

    # -- heartbeat ----------------------------------------------------------
    def start_heartbeat(self) -> None:
        """Start feeding the charger's watchdog."""
        self._schedule_heartbeat()

    def _schedule_heartbeat(self) -> None:
        self._heartbeat_cancel = async_call_later(
            self.hass, self.heartbeat_seconds, self._heartbeat_tick
        )

    async def _heartbeat_tick(self, _now) -> None:
        # Only feed the watchdog while armed AND actually charging, so a pause
        # is allowed to time out to the safe fallback instead of being held
        # open by a stream of 0 A writes.
        if self.watchdog and self._effective_current() > 0:
            await self.async_write_effective()
        self._schedule_heartbeat()

    def stop_heartbeat(self) -> None:
        """Stop the heartbeat and cancel any pending debounced write."""
        if self._heartbeat_cancel is not None:
            self._heartbeat_cancel()
            self._heartbeat_cancel = None
        if self._debounce_cancel is not None:
            self._debounce_cancel()
            self._debounce_cancel = None

    # -- sync-off -----------------------------------------------------------
    def _check_sync_off(self, data: PeblarData) -> None:
        """Drop charge-enable if the charger stopped on its own.

        Only ever turns charging off, never on: adopting the charger's state
        upwards would let it restart a charge the user did not ask for.
        """
        actual = data.current_limit_actual
        if actual is None or actual >= 1 or not self.charge_enable:
            self._actual_zero_since = None
            return
        now = dt_util.utcnow()
        if self._actual_zero_since is None:
            self._actual_zero_since = now
        elif now - self._actual_zero_since >= SYNC_OFF_DEBOUNCE:
            self._actual_zero_since = None
            _LOGGER.info("Peblar: the charger stopped externally - disabling charge")
            self.hass.async_create_task(self.async_set_charge_enable(False))

    # -- setters used by entities ------------------------------------------
    async def async_set_requested_current(self, amps: float) -> None:
        """Set the requested charge current."""
        self.requested_current = amps
        self.async_update_listeners()
        self.schedule_effective_write()

    async def async_set_charge_enable(self, enabled: bool) -> None:
        """Enable or pause charging."""
        self.charge_enable = enabled
        self.async_update_listeners()
        self.schedule_effective_write()

    async def async_set_watchdog(self, enabled: bool) -> None:
        """Arm or disarm the charger's watchdog."""
        self.watchdog = enabled
        self.async_update_listeners()
        await self.async_apply_watchdog()
