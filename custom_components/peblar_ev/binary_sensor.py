"""Binary sensor platform: charging, connected, and link health."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PeblarConfigEntry
from .coordinator import PeblarCoordinator
from .entity import PeblarEntity
from .peblar_modbus import PeblarData


@dataclass(frozen=True, kw_only=True)
class PeblarBinaryDescription(BinarySensorEntityDescription):
    """A binary sensor with a value extractor."""

    value_fn: Callable[[PeblarData], bool]


BINARY_SENSORS: tuple[PeblarBinaryDescription, ...] = (
    PeblarBinaryDescription(
        key="charging",
        translation_key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=lambda data: data.cp_state.is_charging,
    ),
    PeblarBinaryDescription(
        key="connected",
        translation_key="connected",
        device_class=BinarySensorDeviceClass.PLUG,
        value_fn=lambda data: data.cp_state.is_connected,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PeblarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        [PeblarBinarySensor(coordinator, desc) for desc in BINARY_SENSORS]
        + [PeblarLinkProblem(coordinator)]
    )


class PeblarBinarySensor(PeblarEntity, BinarySensorEntity):
    """A binary sensor derived from the charger's state."""

    entity_description: PeblarBinaryDescription

    def __init__(
        self, coordinator: PeblarCoordinator, description: PeblarBinaryDescription
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Whether the sensor is on."""
        return self.entity_description.value_fn(self.coordinator.data)


class PeblarLinkProblem(PeblarEntity, BinarySensorEntity):
    """Reports a sustained Modbus outage.

    Unlike the other entities this one must survive the coordinator failing,
    so it is always available and reads the coordinator's link state rather
    than its data.
    """

    _attr_translation_key = "modbus_down"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: PeblarCoordinator) -> None:
        """Initialize the link problem sensor."""
        super().__init__(coordinator, "modbus_down")

    @property
    def available(self) -> bool:
        """Always available: it reports the outage the others go missing for."""
        return True

    @property
    def is_on(self) -> bool:
        """Whether the link has been down for longer than the grace period."""
        return self.coordinator.link_down
