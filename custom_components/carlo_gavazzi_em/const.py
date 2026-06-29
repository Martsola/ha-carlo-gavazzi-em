"""Constants and data models for the Carlo Gavazzi EM integration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from homeassistant.const import Platform

DOMAIN = "carlo_gavazzi_em"
PLATFORMS: tuple[Platform, ...] = (Platform.SENSOR,)

CONF_HOST = "host"
CONF_PORT = "port"
CONF_TIMEOUT = "timeout"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_SCAN_START = "scan_start"
CONF_SCAN_END = "scan_end"
CONF_TRANSPORT_MODE = "transport_mode"
CONF_DETECTED_TRANSPORT_MODE = "detected_transport_mode"
CONF_DISCOVERY_PASSES = "discovery_passes"
CONF_REQUEST_RETRIES = "request_retries"
CONF_DELAY_BETWEEN_REQUESTS_MS = "delay_between_requests_ms"
CONF_METERS = "meters"

DEFAULT_PORT = 502
DEFAULT_TIMEOUT = 0.75
DEFAULT_UPDATE_INTERVAL = 10
DEFAULT_SCAN_START = 1
DEFAULT_SCAN_END = 247
DEFAULT_DISCOVERY_PASSES = 3
DEFAULT_REQUEST_RETRIES = 2
DEFAULT_DELAY_BETWEEN_REQUESTS_MS = 10
MIN_UPDATE_INTERVAL = 5
MAX_MODBUS_READ_WORDS = 18

IDENTIFICATION_ADDRESS = 0x000B
VERSION_ADDRESS = 0x0302
REVISION_ADDRESS = 0x0303
LOCK_STATUS_ADDRESS = 0x0304
MEASURING_SYSTEM_ADDRESS = 0x1002
CT_PRIMARY_ADDRESS = 0x1003
CT_PRIMARY_2_ADDRESS = 0x1004
VT_RATIO_ADDRESS = 0x1005
SUM_VIRTUAL_ADDRESS = 0x1007
DMD_INTEGRATION_ADDRESS = 0x1010
TON_TIME_ADDRESS = 0x1012
KWH_PER_PULSE_OUT1_ADDRESS = 0x1020
KWH_PER_PULSE_OUT2_ADDRESS = 0x1022
EC_MODE_ADDRESS = 0x1103
TCD_PHASE_ORDER_A1_ADDRESS = 0x1300
TCD_PHASE_ORDER_A2_ADDRESS = 0x1302
RS485_ADDRESS_ADDRESS = 0x2000
RS485_BAUD_ADDRESS = 0x2001
RS485_PARITY_ADDRESS = 0x2002
SERIAL_NUMBER_START = 0x5000
SERIAL_NUMBER_WORDS = 7
PRODUCTION_YEAR_ADDRESS = 0x5007
SECONDARY_ADDRESS_START = 0x5100

MISSING_NOT_MANAGED_MSW = 0x7FFD
MISSING_TCD_MSW = 0x7FFE
MISSING_OVERFLOW_MSW = 0x7FFF
MISSING_LSW = 0xFFFF

GATEWAY_TITLE_PREFIX = "Carlo Gavazzi EM Gateway"


class TransportMode(StrEnum):
    """Supported Modbus TCP framing modes."""

    AUTO = "auto"
    SOCKET = "socket"
    RTU_OVER_TCP = "rtu_over_tcp"


@dataclass(frozen=True, slots=True)
class MeterInfo:
    """Static metadata read from a discovered meter."""

    slave_id: int
    identification_code: int
    model_name: str
    model_family: str
    serial_number: str | None
    device_uid: str
    firmware_version: str | None
    production_year: int | None
    secondary_address: int | None

    @property
    def unique_key(self) -> str:
        """Return the Home Assistant device identifier component."""
        return self.device_uid

    @property
    def device_name(self) -> str:
        """Return a useful default device name."""
        return f"{self.model_name} (address {self.slave_id})"
