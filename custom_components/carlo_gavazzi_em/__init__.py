"""Carlo Gavazzi EM270/EM280 integration."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_DETECTED_TRANSPORT_MODE,
    CONF_METERS,
    DOMAIN,
    PLATFORMS,
    MeterInfo,
)

if TYPE_CHECKING:
    from .api import CarloGavazziAPI
    from .coordinator import CarloGavazziCoordinator


type CarloGavazziRuntimeData = dict[str, Any]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up one Modbus RTU-to-TCP gateway."""
    # Keep these imports out of package initialization so Home Assistant can always
    # load the config flow and display its first form independently of pymodbus.
    from .api import CarloGavazziAPI
    from .coordinator import CarloGavazziCoordinator

    config = {**entry.data, **entry.options}
    api: CarloGavazziAPI = CarloGavazziAPI(config)
    meters = [MeterInfo(**meter) for meter in entry.data.get(CONF_METERS, [])]

    try:
        if not meters:
            meters = await api.async_discover_meters()
            hass.config_entries.async_update_entry(
                entry,
                data={
                    **entry.data,
                    CONF_METERS: [asdict(meter) for meter in meters],
                    CONF_DETECTED_TRANSPORT_MODE: api.detected_transport_mode,
                },
            )

        coordinator: CarloGavazziCoordinator = CarloGavazziCoordinator(
            hass,
            entry,
            api,
            meters,
        )
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        await api.async_close()
        raise

    runtime: CarloGavazziRuntimeData = {
        "api": api,
        "coordinator": coordinator,
        "meters": meters,
    }
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a gateway config entry."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False

    runtime = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if runtime is not None:
        await runtime["api"].async_close()
    return True
