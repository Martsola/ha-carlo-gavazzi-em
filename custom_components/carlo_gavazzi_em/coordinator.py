"""Data update coordinator for Carlo Gavazzi EM."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CarloGavazziAPI
from .const import (
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    MeterInfo,
)
from .modbus import ModbusGatewayError

_LOGGER = logging.getLogger(__name__)


class CarloGavazziCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Coordinate polling for all meters behind a gateway."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: CarloGavazziAPI,
        meters: list[MeterInfo],
    ) -> None:
        self.api = api
        self.meters = meters
        update_interval = entry.options.get(
            CONF_UPDATE_INTERVAL,
            entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=int(update_interval)),
            always_update=False,
        )

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            return await self.api.async_fetch_all_meter_data(self.meters)
        except ModbusGatewayError as err:
            raise UpdateFailed(str(err)) from err
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Unexpected polling error: {err}") from err
