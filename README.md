# Carlo Gavazzi EM for Home Assistant

A local, read-only Home Assistant custom integration for Carlo Gavazzi **EM270 X**, **EM270 W**, and **EM280** energy meters connected through a transparent Modbus RTU-to-Modbus TCP gateway.

> [!IMPORTANT]
> `v1.0.0` is a clean rebuild intended to replace the earlier prototype repository. The code has been reviewed against the supplied EM270/EM280 communication protocol and includes automated import, lint, HACS, and hassfest checks, but it still needs testing with physical meters and a real gateway.

## Features

- UI setup through a Home Assistant config flow.
- One config entry per TCP gateway and one Home Assistant device per discovered meter.
- Full slave-address scan from **1–247** by default, with an optional restricted range.
- Three discovery passes; passes two and three skip addresses already discovered.
- Live discovery progress showing the pass, current address, framing mode, and number of meters found.
- Automatic probing of standard Modbus TCP and RTU-over-TCP framing, or an explicit user-selected mode.
- Automatic EM270/EM280 model identification.
- Serial number, model, model ID, and firmware stored as Home Assistant device information rather than duplicate sensors.
- All documented read-only measurement and diagnostic registers exposed as sensors.
- Configurable update interval, timeout, retry count, and delay between requests.
- Contiguous reads limited to the protocol maximum of 18 registers.
- LSW/MSW 32-bit decoding and handling for the documented unsupported, overflow, and missing-TCD values.
- Reconfigure/rescan flow and automatically reloading options flow.
- Redacted diagnostics.
- No write, reset, or programming commands.

## Requirements

- Home Assistant **2026.2.3** or newer.
- A transparent RTU-to-TCP gateway reachable from Home Assistant.
- The gateway serial port already configured to match the RS485 bus.

A generic transparent gateway does not expose a standard Modbus method for changing its own baud, parity, or stop-bit settings. The integration can read the meter's serial settings after communication succeeds, but it cannot configure the gateway itself.

## Installation with HACS

1. Open **HACS → Integrations**.
2. Open the three-dot menu and choose **Custom repositories**.
3. Add `https://github.com/bfulham/ha-carlo-gavazzi-em` as an **Integration** repository.
4. Install **Carlo Gavazzi EM**.
5. Restart Home Assistant.
6. Open **Settings → Devices & services → Add integration** and search for **Carlo Gavazzi EM**.

## Manual installation

Copy:

```text
custom_components/carlo_gavazzi_em
```

into:

```text
/config/custom_components/carlo_gavazzi_em
```

Restart Home Assistant before opening the config flow.

## Setup

The first page asks for:

- gateway host or IP address;
- TCP port, normally `502`;
- polling interval;
- whether to show advanced settings; and
- whether to restrict the default `1–247` scan.

Advanced settings provide:

- request timeout;
- retries after the first polling attempt;
- delay between requests; and
- Auto detect, Modbus TCP, or RTU-over-TCP framing.

A full scan can take several minutes because unused RTU addresses may each wait for the configured timeout. Restrict the range when the expected slave IDs are known.

## Device and entity behaviour

Each discovered meter is represented as its own Home Assistant device. The meter serial number is used as device metadata and as the stable device identifier when available. A gateway/address fallback identifier is used when the serial number cannot be read.

The complete documented read-only entity set is created for every meter. Variables that are unavailable for a specific model, firmware, measuring system, TCD arrangement, or SUM/Virtual configuration remain unavailable instead of reporting a false value.

## Reconfigure and options

Use **Reconfigure** on the integration entry to change the gateway address, framing mode, scan range, or to rescan the RTU bus.

Use **Configure** to change the normal update interval, timeout, retry count, and request delay without rescanning.

## Gateway preparation

Before setup, configure the gateway serial side to match the meters:

- baud rate;
- parity;
- stop bits;
- RS485 two-wire mode; and
- a suitable RTU response timeout.

Also verify RS485 A/B polarity, termination, and unique slave addresses.

## Troubleshooting

### Config flow does not open

Confirm that `/config/custom_components/carlo_gavazzi_em/manifest.json` reports the expected version, then perform a full Home Assistant restart. The repository CI includes a config-flow import test against Home Assistant 2026.6.1 to catch import-time failures.

### No meters found

1. Confirm the gateway host and TCP port are reachable from Home Assistant.
2. Confirm gateway baud, parity, stop bits, and RTU mode match the meter bus.
3. Check A/B polarity, common reference, termination, and slave addresses.
4. Try explicitly selecting **Modbus TCP** or **RTU over TCP**.
5. Increase the request timeout and inter-request delay.
6. Restrict the scan to the known address range while testing.

### Reporting an issue

Download diagnostics from the integration entry and attach them to a GitHub issue. Remove any network information you do not want to publish.

## Supported identification values

| Code | Model |
|---:|---|
| 270 | EM27072DMV53X2SX or EM27072DMV53X2SW |
| 271 | EM27072DMV53XOSX or EM27072DMV53XOSW |
| 272 | EM27072DMV63X2SX or EM27072DMV63X2SW |
| 273 | EM27072DMV63XOSX or EM27072DMV63XOSW |
| 280 | EM28072DMV53X2SX |
| 281 | EM28072DMV53XOSX |
| 282 | EM28072DMV63X2SX |
| 283 | EM28072DMV63XOSX |

EM270 X and W share identification codes 270–273. The integration uses the documented firmware branch to distinguish them when possible and otherwise labels the model as X/W.

## Development

```bash
python -m pip install -r requirements-dev.txt
ruff format --check .
ruff check .
python -m compileall -q custom_components/carlo_gavazzi_em scripts
```

GitHub Actions additionally run Home Assistant hassfest, HACS validation, and a real config-flow import smoke test.

## License

MIT. This project is not affiliated with or endorsed by Carlo Gavazzi.
