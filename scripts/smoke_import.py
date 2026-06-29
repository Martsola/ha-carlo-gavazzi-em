"""Smoke-test the real config-flow manager, imports, schemas, and helpers."""

from __future__ import annotations

import asyncio
import shutil
import sys
import tempfile
from importlib import import_module
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


async def _async_test_flow_manager() -> None:
    """Start the integration through Home Assistant's actual flow manager."""
    from homeassistant import loader
    from homeassistant.config_entries import SOURCE_USER, ConfigEntries
    from homeassistant.core import HomeAssistant

    with tempfile.TemporaryDirectory() as temp_dir:
        config_dir = Path(temp_dir)
        custom_components = config_dir / "custom_components"
        custom_components.mkdir()
        shutil.copytree(
            ROOT / "custom_components" / "carlo_gavazzi_em",
            custom_components / "carlo_gavazzi_em",
        )

        hass = HomeAssistant(temp_dir)
        loader.async_setup(hass)
        hass.config_entries = ConfigEntries(hass, {})
        try:
            result = await hass.config_entries.flow.async_init(
                "carlo_gavazzi_em",
                context={"source": SOURCE_USER},
            )
            assert result["type"] == "form"
            assert result["step_id"] == "user"
            assert result.get("errors") in (None, {})
            assert result.get("data_schema") is not None

            flow_id = result["flow_id"]
            result = await hass.config_entries.flow.async_configure(
                flow_id,
                {
                    "host": "127.0.0.1",
                    "port": 502,
                    "update_interval": 10,
                    "advanced_settings": True,
                    "limit_scan_range": True,
                },
            )
            assert result["type"] == "form"
            assert result["step_id"] == "advanced"

            result = await hass.config_entries.flow.async_configure(
                flow_id,
                {
                    "timeout": 0.75,
                    "request_retries": 2,
                    "delay_between_requests_ms": 10,
                    "transport_mode": "auto",
                },
            )
            assert result["type"] == "form"
            assert result["step_id"] == "scan_range"

            result = await hass.config_entries.flow.async_configure(
                flow_id,
                {"scan_start": 3, "scan_end": 1},
            )
            assert result["type"] == "form"
            assert result["step_id"] == "scan_range"
            assert result["errors"] == {"base": "invalid_range"}
        finally:
            await hass.async_stop(force=True)


async def _async_test_discovery_logic() -> None:
    """Exercise auto framing, model discovery, and skip-on-found behavior."""
    api_module = import_module("custom_components.carlo_gavazzi_em.api")
    const = import_module("custom_components.carlo_gavazzi_em.const")

    class FakeClient:
        def __init__(self) -> None:
            self.transport_mode = const.TransportMode.SOCKET
            self.identification_reads: list[tuple[str, int]] = []

        async def async_connect(self) -> bool:
            return True

        async def async_close(self) -> None:
            return None

        async def async_set_transport_mode(self, mode: object) -> None:
            self.transport_mode = const.TransportMode(mode)

        async def async_read_holding_registers(
            self,
            slave_id: int,
            address: int,
            count: int,
            *,
            attempts: int = 1,
        ) -> list[int] | None:
            del attempts
            if address == const.IDENTIFICATION_ADDRESS:
                self.identification_reads.append((self.transport_mode.value, slave_id))
                if (
                    self.transport_mode is const.TransportMode.RTU_OVER_TCP
                    and slave_id == 2
                ):
                    return [270]
                return None
            if slave_id != 2:
                return None
            if address == const.VERSION_ADDRESS and count == 1:
                return [1]
            if address == const.REVISION_ADDRESS and count == 1:
                return [4]
            if address == const.SERIAL_NUMBER_START and count == 8:
                raw = b"ABCDEFGHIJKLM"
                words = [
                    (raw[index] << 8) | raw[index + 1] for index in range(0, 12, 2)
                ]
                words.append(raw[12] << 8)
                return [*words, 2026]
            if address == const.SECONDARY_ADDRESS_START and count == 2:
                return [1, 0]
            return None

    integration_api = api_module.CarloGavazziAPI(
        {
            const.CONF_HOST: "127.0.0.1",
            const.CONF_PORT: 502,
            const.CONF_SCAN_START: 1,
            const.CONF_SCAN_END: 3,
            const.CONF_DISCOVERY_PASSES: 3,
            const.CONF_TRANSPORT_MODE: const.TransportMode.AUTO.value,
        }
    )
    fake_client = FakeClient()
    integration_api.client = fake_client
    meters = await integration_api.async_discover_meters()

    assert len(meters) == 1
    assert meters[0].slave_id == 2
    assert meters[0].serial_number == "ABCDEFGHIJKLM"
    assert meters[0].model_name == "EM27072DMV53X2SX"
    assert integration_api.detected_transport_mode == const.TransportMode.RTU_OVER_TCP
    assert fake_client.identification_reads.count(("socket", 2)) == 1
    assert fake_client.identification_reads.count(("rtu_over_tcp", 2)) == 1

    explicit_api = api_module.CarloGavazziAPI(
        {
            const.CONF_HOST: "127.0.0.1",
            const.CONF_TRANSPORT_MODE: const.TransportMode.SOCKET.value,
            const.CONF_DETECTED_TRANSPORT_MODE: (
                const.TransportMode.RTU_OVER_TCP.value
            ),
        }
    )
    assert explicit_api.detected_transport_mode == const.TransportMode.SOCKET.value


def _test_imports_schemas_and_protocol_helpers() -> None:
    """Run checks that catch import-time and basic protocol regressions."""
    flow = import_module("custom_components.carlo_gavazzi_em.config_flow")
    api = import_module("custom_components.carlo_gavazzi_em.api")
    const = import_module("custom_components.carlo_gavazzi_em.const")
    modbus = import_module("custom_components.carlo_gavazzi_em.modbus")
    registers = import_module("custom_components.carlo_gavazzi_em.registers")
    import_module("custom_components.carlo_gavazzi_em.coordinator")
    import_module("custom_components.carlo_gavazzi_em.diagnostics")
    import_module("custom_components.carlo_gavazzi_em.sensor")

    user_defaults = flow._user_schema({})({})
    advanced_defaults = flow._advanced_schema({})({})
    range_defaults = flow._scan_range_schema({})({})

    assert flow.CarloGavazziConfigFlow.VERSION == 1
    assert user_defaults[flow.CONF_HOST] == ""
    assert user_defaults[flow.CONF_PORT] == flow.DEFAULT_PORT
    assert user_defaults[flow.CONF_UPDATE_INTERVAL] == flow.DEFAULT_UPDATE_INTERVAL
    assert advanced_defaults[flow.CONF_TIMEOUT] == flow.DEFAULT_TIMEOUT
    assert advanced_defaults[flow.CONF_TRANSPORT_MODE] == flow.TransportMode.AUTO.value
    assert range_defaults[flow.CONF_SCAN_START] == flow.DEFAULT_SCAN_START
    assert range_defaults[flow.CONF_SCAN_END] == flow.DEFAULT_SCAN_END

    descriptions = registers.SENSOR_DESCRIPTIONS
    assert descriptions
    assert len({description.key for description in descriptions}) == len(descriptions)
    assert max(block.count for block in api.READ_BLOCKS) <= const.MAX_MODBUS_READ_WORDS
    assert modbus.decode_int32_lsw_msw([0xFFFF, 0xFFFF]) == -1
    assert modbus.decode_uint32_lsw_msw([0x5678, 0x1234]) == 0x12345678
    assert api._model_name(270, "em270_x") == "EM27072DMV53X2SX"
    assert api._model_name(270, "em270_w") == "EM27072DMV53X2SW"
    assert api._firmware_version("em270_x", 1, 4) == "r.b4"
    assert api._firmware_version("em270_w", 2, 0) == "r.C0"
    assert api._firmware_version("em280", 4, 3) == "r.E3"


def main() -> None:
    """Run all smoke checks."""
    asyncio.run(_async_test_flow_manager())
    asyncio.run(_async_test_discovery_logic())
    _test_imports_schemas_and_protocol_helpers()
    print("Home Assistant flow manager, imports, schemas, and helpers: OK")


if __name__ == "__main__":
    main()
