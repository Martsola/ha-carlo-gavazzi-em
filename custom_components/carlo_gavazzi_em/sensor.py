"""Sensor platform for Carlo Gavazzi EM."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MeterInfo
from .coordinator import CarloGavazziCoordinator
from .modbus import (
    decode_int16,
    decode_int32_lsw_msw,
    decode_uint16,
    decode_uint32_lsw_msw,
    is_missing_32,
)
from .registers import (
    SENSOR_DESCRIPTIONS,
    SENSOR_DESCRIPTIONS_EM24,
    RegisterSensorDescription,
    map_option,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up every documented sensor for every discovered meter."""
    runtime = hass.data[DOMAIN][entry.entry_id]
    coordinator: CarloGavazziCoordinator = runtime["coordinator"]
    meters: list[MeterInfo] = runtime["meters"]

    async_add_entities(
        CarloGavazziSensor(coordinator, meter, description)
        for meter in meters
        for description in (
            SENSOR_DESCRIPTIONS_EM24
            if meter.model_family == "em24"
            else SENSOR_DESCRIPTIONS
        )
    )


class CarloGavazziSensor(CoordinatorEntity[CarloGavazziCoordinator], SensorEntity):
    """One register-backed meter sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CarloGavazziCoordinator,
        meter: MeterInfo,
        description: RegisterSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._meter = meter
        self._attr_unique_id = f"{meter.unique_key}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, meter.unique_key)},
            name=meter.device_name,
            manufacturer="Carlo Gavazzi",
            model=meter.model_name,
            model_id=str(meter.identification_code),
            serial_number=meter.serial_number,
            sw_version=meter.firmware_version,
        )

    @property
    def available(self) -> bool:
        """Return true only when this variable returned a valid value."""
        return super().available and self._decoded_value is not None

    @property
    def native_value(self) -> Any:
        """Return the decoded native value."""
        return self._decoded_value

    @property
    def _decoded_value(self) -> Any:
        if not self.coordinator.data:
            return None
        meter_data = self.coordinator.data.get(self._meter.unique_key, {})
        registers = meter_data.get("values", {}).get(self.entity_description.key)
        if registers is None:
            return None
        return decode_sensor_value(
            self.entity_description,
            registers,
            self._meter.model_family,
        )


def decode_sensor_value(
    description: RegisterSensorDescription,
    registers: list[int],
    model_family: str,
) -> Any:
    """Decode and scale one sensor value."""
    if description.words == 2:
        if len(registers) != 2 or is_missing_32(registers):
            return None
        raw = (
            decode_int32_lsw_msw(registers)
            if description.signed
            else decode_uint32_lsw_msw(registers)
        )
        value = raw / description.scale
        if description.maximum is not None and abs(value) > description.maximum:
            return None
        return round(value, 6) if description.scale != 1 else raw

    if len(registers) != 1:
        return None
    if description.signed:
        raw = decode_int16(registers)
        value = raw / description.scale
        if description.maximum is not None and abs(value) > description.maximum:
            return None
        return round(value, 6) if description.scale != 1 else raw
    raw = decode_uint16(registers)
    if raw == 0xFFFF:
        return None
    mapped = map_option(description, raw, model_family)
    if isinstance(mapped, str):
        return mapped
    value = mapped / description.scale
    return round(value, 6) if description.scale != 1 else mapped
