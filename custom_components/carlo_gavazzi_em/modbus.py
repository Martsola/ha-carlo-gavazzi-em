"""Low-level Modbus helpers for Carlo Gavazzi EM meters."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.framer import FramerType

from .const import (
    CONF_DELAY_BETWEEN_REQUESTS_MS,
    CONF_HOST,
    CONF_PORT,
    CONF_TIMEOUT,
    DEFAULT_DELAY_BETWEEN_REQUESTS_MS,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    MAX_MODBUS_READ_WORDS,
    MISSING_LSW,
    MISSING_NOT_MANAGED_MSW,
    MISSING_OVERFLOW_MSW,
    MISSING_TCD_MSW,
    TransportMode,
)

_LOGGER = logging.getLogger(__name__)


class ModbusGatewayError(Exception):
    """Base exception for gateway communication failures."""


class ModbusGatewayClient:
    """Serialize access to one Modbus RTU-to-TCP gateway."""

    def __init__(self, config: dict[str, Any], transport_mode: str) -> None:
        self._config = config
        self._client: AsyncModbusTcpClient | None = None
        self._lock = asyncio.Lock()
        self._delay = (
            int(
                config.get(
                    CONF_DELAY_BETWEEN_REQUESTS_MS,
                    DEFAULT_DELAY_BETWEEN_REQUESTS_MS,
                )
            )
            / 1000
        )
        self._transport_mode = TransportMode(transport_mode)

    @property
    def transport_mode(self) -> TransportMode:
        """Return the active framing mode."""
        return self._transport_mode

    async def async_set_transport_mode(self, mode: str | TransportMode) -> None:
        """Change framing mode and reconnect on the next request."""
        mode = TransportMode(mode)
        if mode is TransportMode.AUTO:
            raise ValueError("AUTO is not a wire framing mode")
        if mode == self._transport_mode:
            return
        await self.async_close()
        self._transport_mode = mode

    @property
    def _framer(self) -> FramerType:
        return (
            FramerType.RTU
            if self._transport_mode is TransportMode.RTU_OVER_TCP
            else FramerType.SOCKET
        )

    async def async_connect(self) -> bool:
        """Connect to the gateway if necessary."""
        if self._client is not None and self._client.connected:
            return True

        self._client = AsyncModbusTcpClient(
            host=str(self._config[CONF_HOST]),
            port=int(self._config.get(CONF_PORT, DEFAULT_PORT)),
            timeout=float(self._config.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)),
            retries=0,
            framer=self._framer,
        )
        return bool(await self._client.connect())

    async def async_close(self) -> None:
        """Close the current TCP connection."""
        if self._client is not None:
            self._client.close()
            self._client = None

    async def async_read_holding_registers(
        self,
        slave_id: int,
        address: int,
        count: int,
        *,
        attempts: int = 1,
    ) -> list[int] | None:
        """Read holding registers, returning None after all attempts fail."""
        if not 1 <= slave_id <= 247:
            raise ValueError(f"Invalid Modbus slave ID: {slave_id}")
        if not 1 <= count <= MAX_MODBUS_READ_WORDS:
            raise ValueError(
                f"Read count must be between 1 and {MAX_MODBUS_READ_WORDS}"
            )

        for attempt in range(max(1, attempts)):
            try:
                async with self._lock:
                    if not await self.async_connect():
                        raise ModbusGatewayError("Unable to connect to gateway")

                    assert self._client is not None
                    response = await self._client.read_holding_registers(
                        address=address,
                        count=count,
                        device_id=slave_id,
                    )
                    if self._delay:
                        await asyncio.sleep(self._delay)
            except (TimeoutError, OSError, ModbusGatewayError) as err:
                _LOGGER.debug(
                    "Read attempt %s/%s failed for slave %s at 0x%04X: %s",
                    attempt + 1,
                    max(1, attempts),
                    slave_id,
                    address,
                    err,
                )
                await self.async_close()
                continue
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug(
                    "Unexpected Modbus read failure for slave %s at 0x%04X: %s",
                    slave_id,
                    address,
                    err,
                )
                await self.async_close()
                continue

            if response is None or response.isError():
                _LOGGER.debug(
                    "Modbus exception response from slave %s at 0x%04X",
                    slave_id,
                    address,
                )
                continue

            registers = getattr(response, "registers", None)
            if registers is None or len(registers) != count:
                _LOGGER.debug(
                    "Unexpected register count from slave %s at 0x%04X",
                    slave_id,
                    address,
                )
                continue
            return [int(register) for register in registers]

        return None


def decode_uint16(registers: list[int]) -> int:
    """Decode one unsigned 16-bit register."""
    return registers[0]


def decode_int16(registers: list[int]) -> int:
    """Decode one signed 16-bit register."""
    raw = registers[0]
    return raw - 0x10000 if raw & 0x8000 else raw


def decode_int32_lsw_msw(registers: list[int]) -> int:
    """Decode a signed 32-bit value using the meter's LSW/MSW word order."""
    raw = (registers[1] << 16) | registers[0]
    return raw - 0x100000000 if raw & 0x80000000 else raw


def decode_uint32_lsw_msw(registers: list[int]) -> int:
    """Decode an unsigned 32-bit value using LSW/MSW word order."""
    return (registers[1] << 16) | registers[0]


def decode_ascii_serial(registers: list[int]) -> str:
    """Decode and validate the 13-character ASCII serial-number field."""
    raw_bytes: list[int] = []
    for index, register in enumerate(registers):
        raw_bytes.append((register >> 8) & 0xFF)
        if index < len(registers) - 1:
            raw_bytes.append(register & 0xFF)

    if any(byte not in range(0x20, 0x7F) for byte in raw_bytes):
        return ""
    return bytes(raw_bytes).decode("ascii").strip()


def is_missing_32(registers: list[int]) -> bool:
    """Return true for overflow, unsupported, or missing-TCD sentinels."""
    return (
        len(registers) == 2
        and registers[0] == MISSING_LSW
        and registers[1]
        in {
            MISSING_NOT_MANAGED_MSW,
            MISSING_TCD_MSW,
            MISSING_OVERFLOW_MSW,
        }
    )
