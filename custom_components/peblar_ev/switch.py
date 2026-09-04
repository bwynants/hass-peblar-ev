"""Switch platform: charge enable and watchdog.

Both restore their state across restarts and push the restored value into the
coordinator, which is the source of truth. The watchdog's restore also
re-asserts the charger's watchdog registers.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import PeblarConfigEntry
from .coordinator import PeblarCoordinator
from .entity import PeblarEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PeblarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the switches."""
    coordinator = entry.runtime_data
    async_add_entities(
        [PeblarChargeEnableSwitch(coordinator), PeblarWatchdogSwitch(coordinator)]
    )


class PeblarChargeEnableSwitch(PeblarEntity, SwitchEntity, RestoreEntity):
    """On: the current follows the slider. Off: pause the charger (0 A)."""

    _attr_translation_key = "charge_enable"
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(self, coordinator: PeblarCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, "charge_enable")

    @property
    def is_on(self) -> bool:
        """Whether charging is enabled."""
        return self.coordinator.charge_enable

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable charging."""
        await self.coordinator.async_set_charge_enable(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Pause charging."""
        await self.coordinator.async_set_charge_enable(False)

    async def async_added_to_hass(self) -> None:
        """Restore the charge-enable flag into the coordinator."""
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        self.coordinator.charge_enable = bool(last and last.state == "on")
        # Debounced, so it coalesces with the number's restore into one write.
        self.coordinator.schedule_effective_write()


class PeblarWatchdogSwitch(PeblarEntity, SwitchEntity, RestoreEntity):
    """On: arm the Alive/Fallback watchdog, so the charger stops if HA goes quiet."""

    _attr_translation_key = "watchdog"
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: PeblarCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, "watchdog")

    @property
    def is_on(self) -> bool:
        """Whether the watchdog is armed."""
        return self.coordinator.watchdog

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Arm the watchdog."""
        await self.coordinator.async_set_watchdog(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disarm the watchdog."""
        await self.coordinator.async_set_watchdog(False)

    async def async_added_to_hass(self) -> None:
        """Restore the flag and force the charger to match it."""
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        self.coordinator.watchdog = bool(last and last.state == "on")
        await self.coordinator.async_apply_watchdog()
