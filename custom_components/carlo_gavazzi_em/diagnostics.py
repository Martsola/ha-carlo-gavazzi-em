"""Diagnostics support for Carlo Gavazzi EM."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_HOST, DOMAIN

TO_REDACT = {CONF_HOST, "device_uid", "serial_number"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return redacted gateway, meter, and coordinator diagnostics."""
    runtime = hass.data[DOMAIN][entry.entry_id]
    coordinator = runtime["coordinator"]
    meters = runtime["meters"]
    coordinator_data = coordinator.data or {}

    poll_data = {
        f"slave_{meter.slave_id}": coordinator_data.get(meter.unique_key)
        for meter in meters
    }
    diagnostics = {
        "entry": {
            "title": entry.title,
            "data": {
                key: value for key, value in entry.data.items() if key != "meters"
            },
            "options": dict(entry.options),
        },
        "meters": [asdict(meter) for meter in meters],
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_exception": (
                str(coordinator.last_exception)
                if coordinator.last_exception is not None
                else None
            ),
            "data_by_slave": poll_data,
        },
    }
    return async_redact_data(diagnostics, TO_REDACT)
