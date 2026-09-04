"""Number platform: the requested charge current limit."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import UnitOfElectricCurrent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import PeblarConfigEntry
from .const import DEFAULT_MIN_CURRENT
from .coordinator import PeblarCoordinator
from .entity import PeblarEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PeblarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the number."""
    async_add_entities([PeblarCurrentLimitNumber(entry.runtime_data)])


class PeblarCurrentLimitNumber(PeblarEntity, NumberEntity, RestoreEntity):
    """The requested charge current in Amperes.

    This is the request, not the command: the value actually written folds in
    the charge-enable switch, so turning that off pauses the charger without
    losing the number the user picked.
    """

    _attr_translation_key = "charge_current_limit"
    _attr_native_min_value = DEFAULT_MIN_CURRENT
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: PeblarCoordinator) -> None:
        """Initialize the number."""
        super().__init__(coordinator, "charge_current_limit")

    @property
    def native_max_value(self) -> float:
        """The configured maximum current."""
        return self.coordinator.max_current

    @property
    def native_value(self) -> float:
        """The requested current."""
        return self.coordinator.requested_current

    async def async_set_native_value(self, value: float) -> None:
        """Set the requested current."""
        await self.coordinator.async_set_requested_current(value)

    async def async_added_to_hass(self) -> None:
        """Restore the requested current into the coordinator."""
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            try:
                self.coordinator.requested_current = float(last.state)
            except (TypeError, ValueError):
                pass
        # Debounced, so this and the switch's restore settle into one correct
        # write whatever order the platforms happen to set up in.
        self.coordinator.schedule_effective_write()
