"""High-level protocol handling for Carlo Gavazzi EM meters."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from .const import (
    CONF_DETECTED_TRANSPORT_MODE,
    CONF_DISCOVERY_PASSES,
    CONF_HOST,
    CONF_PORT,
    CONF_REQUEST_RETRIES,
    CONF_SCAN_END,
    CONF_SCAN_START,
    CONF_TRANSPORT_MODE,
    DEFAULT_DISCOVERY_PASSES,
    DEFAULT_PORT,
    DEFAULT_REQUEST_RETRIES,
    DEFAULT_SCAN_END,
    DEFAULT_SCAN_START,
    IDENTIFICATION_ADDRESS,
    MAX_MODBUS_READ_WORDS,
    PRODUCTION_YEAR_ADDRESS,
    SECONDARY_ADDRESS_START,
    SERIAL_NUMBER_START,
    SERIAL_NUMBER_WORDS,
    VERSION_ADDRESS,
    MeterInfo,
    TransportMode,
)
from .modbus import (
    ModbusGatewayClient,
    ModbusGatewayError,
    decode_ascii_serial,
    decode_uint16,
    decode_uint32_lsw_msw,
    is_missing_32,
)
from .registers import (
    IDENTIFICATION_CODES,
    SENSOR_DESCRIPTIONS,
    RegisterSensorDescription,
)

_LOGGER = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int, int, int, str, int], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class ReadBlock:
    """One contiguous Modbus read and its contained sensor descriptions."""

    address: int
    count: int
    descriptions: tuple[RegisterSensorDescription, ...]


def _build_read_blocks() -> tuple[ReadBlock, ...]:
    """Group adjacent variables without exceeding the protocol's 18-word limit."""
    descriptions = sorted(SENSOR_DESCRIPTIONS, key=lambda item: item.address)
    blocks: list[ReadBlock] = []
    current: list[RegisterSensorDescription] = []
    block_start = 0
    block_end = 0

    for description in descriptions:
        description_end = description.address + description.words
        if (
            current
            and description.address == block_end
            and description_end - block_start <= MAX_MODBUS_READ_WORDS
        ):
            current.append(description)
            block_end = description_end
            continue

        if current:
            blocks.append(
                ReadBlock(
                    address=block_start,
                    count=block_end - block_start,
                    descriptions=tuple(current),
                )
            )
        current = [description]
        block_start = description.address
        block_end = description_end

    if current:
        blocks.append(
            ReadBlock(
                address=block_start,
                count=block_end - block_start,
                descriptions=tuple(current),
            )
        )
    return tuple(blocks)


READ_BLOCKS = _build_read_blocks()


class CarloGavazziAPI:
    """Communicate with all meters behind one gateway."""

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config
        requested = TransportMode(config.get(CONF_TRANSPORT_MODE, TransportMode.AUTO))
        detected = config.get(CONF_DETECTED_TRANSPORT_MODE)
        initial_mode = (
            TransportMode(detected)
            if requested is TransportMode.AUTO and detected
            else requested
        )
        if initial_mode is TransportMode.AUTO:
            initial_mode = TransportMode.SOCKET
        self.client = ModbusGatewayClient(config, initial_mode)
        self._requested_transport = requested
        self._detected_transport: TransportMode | None = (
            TransportMode(detected)
            if requested is TransportMode.AUTO and detected
            else requested
            if requested is not TransportMode.AUTO
            else None
        )

    @property
    def detected_transport_mode(self) -> str:
        """Return the framing mode selected for actual communication."""
        if self._detected_transport is not None:
            return self._detected_transport.value
        return self.client.transport_mode.value

    async def async_close(self) -> None:
        """Close the gateway connection."""
        await self.client.async_close()

    def _mode_for_discovery_pass(self, pass_index: int) -> TransportMode:
        """Choose framing for a pass and keep it once a meter responds."""
        if self._requested_transport is not TransportMode.AUTO:
            return self._requested_transport
        if self._detected_transport is not None:
            return self._detected_transport
        return TransportMode.RTU_OVER_TCP if pass_index == 1 else TransportMode.SOCKET

    async def async_discover_meters(
        self,
        progress_callback: ProgressCallback | None = None,
    ) -> list[MeterInfo]:
        """Scan slave IDs three times, skipping devices already found."""
        start = int(self._config.get(CONF_SCAN_START, DEFAULT_SCAN_START))
        end = int(self._config.get(CONF_SCAN_END, DEFAULT_SCAN_END))
        passes = int(self._config.get(CONF_DISCOVERY_PASSES, DEFAULT_DISCOVERY_PASSES))
        found: dict[int, MeterInfo] = {}
        addresses = list(range(start, end + 1))

        if not await self.client.async_connect():
            raise ModbusGatewayError("Unable to connect to gateway")

        for pass_index in range(passes):
            mode = self._mode_for_discovery_pass(pass_index)
            await self.client.async_set_transport_mode(mode)

            for slave_id in addresses:
                if progress_callback is not None:
                    await progress_callback(
                        pass_index + 1,
                        passes,
                        slave_id,
                        len(addresses),
                        mode.value,
                        len(found),
                    )
                if slave_id in found:
                    continue

                identification = await self._async_probe_identification(slave_id)
                if identification is None:
                    continue

                if self._detected_transport is None:
                    self._detected_transport = mode
                    _LOGGER.debug("Detected %s framing", mode.value)

                meter = await self.async_read_meter_info(slave_id, identification)
                if meter is not None:
                    found[slave_id] = meter

        return [found[slave_id] for slave_id in sorted(found)]

    async def _async_probe_identification(self, slave_id: int) -> int | None:
        registers = await self.client.async_read_holding_registers(
            slave_id,
            IDENTIFICATION_ADDRESS,
            1,
            attempts=1,
        )
        if not registers:
            return None
        code = decode_uint16(registers)
        return code if code in IDENTIFICATION_CODES else None

    async def async_read_meter_info(
        self,
        slave_id: int,
        identification: int,
    ) -> MeterInfo | None:
        """Read static metadata used by the Home Assistant device registry."""
        attempts = max(
            1,
            int(self._config.get(CONF_REQUEST_RETRIES, DEFAULT_REQUEST_RETRIES)) + 1,
        )
        # The protocol requires these metadata words to be read one at a time.
        version_word = await self.client.async_read_holding_registers(
            slave_id,
            VERSION_ADDRESS,
            1,
            attempts=attempts,
        )
        revision_word = await self.client.async_read_holding_registers(
            slave_id,
            VERSION_ADDRESS + 1,
            1,
            attempts=attempts,
        )
        serial_block = await self.client.async_read_holding_registers(
            slave_id,
            SERIAL_NUMBER_START,
            SERIAL_NUMBER_WORDS + 1,
            attempts=attempts,
        )
        secondary_block = await self.client.async_read_holding_registers(
            slave_id,
            SECONDARY_ADDRESS_START,
            2,
            attempts=attempts,
        )

        version_code = _optional_uint16(version_word, 0)
        revision_code = _optional_uint16(revision_word, 0)
        model_family = _model_family(identification, version_code)
        firmware_version = _firmware_version(
            model_family,
            version_code,
            revision_code,
        )
        model_name = _model_name(identification, model_family)

        serial_number: str | None = None
        production_year: int | None = None
        if serial_block:
            serial_number = (
                decode_ascii_serial(serial_block[:SERIAL_NUMBER_WORDS]) or None
            )
            production_year = _optional_uint16(
                serial_block,
                PRODUCTION_YEAR_ADDRESS - SERIAL_NUMBER_START,
            )

        secondary_address = (
            decode_uint32_lsw_msw(secondary_block)
            if secondary_block and not is_missing_32(secondary_block)
            else None
        )
        gateway_key = (
            f"{str(self._config[CONF_HOST]).strip().lower()}:"
            f"{int(self._config.get(CONF_PORT, DEFAULT_PORT))}"
        )
        device_uid = (
            f"serial:{serial_number}"
            if serial_number
            else f"gateway:{gateway_key}:slave:{slave_id}"
        )

        return MeterInfo(
            slave_id=slave_id,
            identification_code=identification,
            model_name=model_name,
            model_family=model_family,
            serial_number=serial_number,
            device_uid=device_uid,
            firmware_version=firmware_version,
            production_year=production_year,
            secondary_address=secondary_address,
        )

    async def async_fetch_all_meter_data(
        self,
        meters: list[MeterInfo],
    ) -> dict[str, dict[str, Any]]:
        """Read all documented values using contiguous blocks."""
        attempts = max(
            1,
            int(self._config.get(CONF_REQUEST_RETRIES, DEFAULT_REQUEST_RETRIES)) + 1,
        )
        data: dict[str, dict[str, Any]] = {}
        any_success = False

        for meter in meters:
            values: dict[str, list[int] | None] = {
                description.key: None for description in SENSOR_DESCRIPTIONS
            }
            successful_blocks = 0

            for block in READ_BLOCKS:
                registers = await self.client.async_read_holding_registers(
                    meter.slave_id,
                    block.address,
                    block.count,
                    attempts=attempts,
                )
                if registers is None:
                    continue
                successful_blocks += 1
                any_success = True
                for description in block.descriptions:
                    offset = description.address - block.address
                    values[description.key] = registers[
                        offset : offset + description.words
                    ]

            data[meter.unique_key] = {
                "available": successful_blocks > 0,
                "successful_blocks": successful_blocks,
                "total_blocks": len(READ_BLOCKS),
                "values": values,
            }

        if not any_success:
            raise ModbusGatewayError("No meter returned any register data")
        return data


def _optional_uint16(registers: list[int] | None, index: int) -> int | None:
    """Return a metadata word unless it contains a missing sentinel."""
    if registers is None or index >= len(registers):
        return None
    value = decode_uint16(registers[index : index + 1])
    return None if value == 0xFFFF else value


def _model_family(identification: int, version_code: int | None) -> str:
    """Infer the EM270 X/W branch from the documented firmware branches."""
    if identification >= 280:
        return "em280"
    if version_code == 1:
        return "em270_x"
    if version_code == 2:
        return "em270_w"
    return "em270"


def _model_name(identification: int, model_family: str) -> str:
    base = IDENTIFICATION_CODES.get(identification, f"Unknown model {identification}")
    if model_family == "em270_x":
        return f"{base}X"
    if model_family == "em270_w":
        return f"{base}W"
    if model_family == "em270":
        return f"{base}X/W"
    return base


def _firmware_version(
    model_family: str,
    version_code: int | None,
    revision_code: int | None,
) -> str | None:
    if version_code is None or revision_code is None or not 0 <= version_code <= 25:
        return None
    letter = chr(ord("A") + version_code)
    if model_family == "em270_x":
        letter = letter.lower()
    return f"r.{letter}{revision_code}"
