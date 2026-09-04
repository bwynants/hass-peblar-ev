"""Sensor platform for Peblar EV (Modbus)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PeblarConfigEntry
from .coordinator import PeblarCoordinator
from .entity import PeblarEntity
from .peblar_modbus import CpState, CurrentLimitSource, PeblarData


@dataclass(frozen=True, kw_only=True)
class PeblarSensorDescription(SensorEntityDescription):
    """A sensor with a value extractor."""

    value_fn: Callable[[PeblarData], float | int | str | None]


SENSORS: tuple[PeblarSensorDescription, ...] = (
    PeblarSensorDescription(
        key="power",
        translation_key="power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda data: data.power,
    ),
    PeblarSensorDescription(
        key="current",
        translation_key="current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_fn=lambda data: data.current,
    ),
    PeblarSensorDescription(
        key="energy",
        translation_key="energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        value_fn=lambda data: data.energy,
    ),
    PeblarSensorDescription(
        key="charge_state",
        translation_key="charge_state",
        device_class=SensorDeviceClass.ENUM,
        options=[state.value for state in CpState],
        value_fn=lambda data: data.cp_state.value,
    ),
    PeblarSensorDescription(
        key="current_limit_actual",
        translation_key="current_limit_actual",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_fn=lambda data: data.current_limit_actual,
    ),
    PeblarSensorDescription(
        key="current_limit_source",
        translation_key="current_limit_source",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=[source.name.lower() for source in CurrentLimitSource],
        value_fn=lambda data: data.current_limit_source.name.lower(),
    ),
    PeblarSensorDescription(
        key="wlan_signal",
        translation_key="wlan_signal",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.wlan_signal,
    ),
    PeblarSensorDescription(
        key="alive_timeout",
        translation_key="alive_timeout",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda data: data.alive_timeout,
    ),
    PeblarSensorDescription(
        key="fallback_current",
        translation_key="fallback_current",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_fn=lambda data: data.fallback_current,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PeblarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    coordinator = entry.runtime_data
    async_add_entities(PeblarSensor(coordinator, desc) for desc in SENSORS)


class PeblarSensor(PeblarEntity, SensorEntity):
    """A Peblar measurement or diagnostic sensor."""

    entity_description: PeblarSensorDescription

    def __init__(
        self, coordinator: PeblarCoordinator, description: PeblarSensorDescription
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | int | str | None:
        """The sensor's current value."""
        return self.entity_description.value_fn(self.coordinator.data)
